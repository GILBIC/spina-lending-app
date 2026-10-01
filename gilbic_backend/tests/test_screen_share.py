from __future__ import annotations

import struct
import time
import zlib
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from gilbic_backend.main import create_app


def png(width=1, height=1, raster=b"\0" * 5):
    def chunk(kind, data):
        return (
            struct.pack("!I", len(data))
            + kind
            + data
            + struct.pack("!I", zlib.crc32(kind + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack("!IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raster))
        + chunk(b"IEND", b"")
    )


def test_share_targets_requires_authentication_and_is_not_cacheable():
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/screen-shares/targets")
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"


def test_png_rejects_corruption_dimensions_and_trailing_payload():
    from gilbic_backend.screen_share_frames import ScreenShareError, validate_png

    validate_png(png())
    for payload in (png(1025), png() + b"secret", png()[:-1], b"<svg/>"):
        with pytest.raises(ScreenShareError) as error:
            validate_png(payload)
        assert error.value.status_code == 422
    with pytest.raises(ScreenShareError) as error:
        validate_png(b"x" * 524289)
    assert error.value.status_code == 413


def test_frames_are_actively_evicted_without_reads():
    from gilbic_backend.screen_share_frames import FrameCache

    cache = FrameCache()
    key = uuid4()
    try:
        cache.put(key, 1, 1, png())
        assert cache.retained_bytes > 0
        # Observing retained_bytes must not itself purge expired frames.
        time.sleep(3.1)
        assert cache.retained_bytes == 0
    finally:
        cache.close()


def test_frame_cache_replaces_only_latest_and_clear_removes_bytes():
    from gilbic_backend.screen_share_frames import FrameCache

    cache = FrameCache()
    key = uuid4()
    try:
        cache.put(key, 1, 1, png())
        cache.put(key, 1, 2, png())
        assert cache.retained_bytes == len(png())
        assert cache.get(key).sequence == 2
        cache.clear(key)
        assert cache.get(key) is None and cache.retained_bytes == 0
    finally:
        cache.close()


def test_database_operation_lock_does_not_delay_image_eviction():
    from gilbic_backend.screen_share_repository import PostgresScreenShareRepository

    repo = PostgresScreenShareRepository()
    try:
        repo.cache.put(uuid4(), 1, 1, png())
        with repo._lock:
            time.sleep(3.1)
            assert repo.cache.retained_bytes == 0
    finally:
        repo.cache.close()


def test_valid_png_structure_cannot_hide_short_or_excess_raster():
    from gilbic_backend.screen_share_frames import ScreenShareError, validate_png

    for image in (png(2, 2), png(raster=b"\0" * 6), png(raster=b"\5" + b"\0" * 4)):
        with pytest.raises(ScreenShareError):
            validate_png(image)  # Short/excess raster or invalid PNG filter.


def test_streamed_image_limit_and_pre_body_participant_authorization():
    from gilbic_backend.screen_share_api import (
        screen_share_actor,
        screen_share_repository,
    )
    from gilbic_backend.screen_share_frames import ScreenShareError

    class Repository:
        denied = False

        def check_upload(self, *args):
            if self.denied:
                raise ScreenShareError(404, "Not found")

        def upload(self, *args):
            raise AssertionError("Rejected image reached publication")

    repo = Repository()
    app = create_app()
    app.dependency_overrides[screen_share_actor] = lambda: object()
    app.dependency_overrides[screen_share_repository] = lambda: repo
    headers = {
        "Content-Type": "image/png",
        "X-Screen-Share-Generation": "1",
        "X-Screen-Share-Sequence": "1",
    }
    with TestClient(app) as client:
        response = client.put(
            "/api/v1/screen-shares/" + str(uuid4()) + "/frame",
            headers=headers,
            content=iter([b"x" * 262144, b"x" * 262145]),
        )
        assert (
            response.status_code == 413
            and response.headers["cache-control"] == "no-store"
        )
        repo.denied = True
        response = client.put(
            "/api/v1/screen-shares/" + str(uuid4()) + "/frame",
            headers=headers,
            content=b"not PNG",
        )
        assert (
            response.status_code == 404
            and response.headers["cache-control"] == "no-store"
        )


@pytest.mark.parametrize("kind", [b"acTL", b"fcTL", b"fdAT", b"UNKN"])
def test_png_rejects_animation_and_unknown_critical_chunks(kind):
    from gilbic_backend.screen_share_frames import ScreenShareError, validate_png

    source = png()
    payload = b"\0" * 8
    chunk = (
        struct.pack("!I", len(payload))
        + kind
        + payload
        + struct.pack("!I", zlib.crc32(kind + payload))
    )
    with pytest.raises(ScreenShareError):
        validate_png(source[:33] + chunk + source[33:])


def test_frame_response_exposes_only_latest_sequence_and_disables_caching():
    from gilbic_backend.screen_share_api import (
        screen_share_actor,
        screen_share_repository,
    )
    from gilbic_backend.screen_share_frames import Frame

    class Repository:
        def frame(self, *args):
            return Frame(2, 7, png(), time.monotonic() + 3)

    app = create_app()
    app.dependency_overrides[screen_share_actor] = lambda: object()
    app.dependency_overrides[screen_share_repository] = Repository
    with TestClient(app) as client:
        response = client.get("/api/v1/screen-shares/" + str(uuid4()) + "/frame")
        assert response.status_code == 200
        assert response.content == png()
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-screen-share-generation"] == "2"
        assert response.headers["x-screen-share-sequence"] == "7"
        invalid = client.post(
            "/api/v1/screen-shares/" + str(uuid4()) + "/ready",
            json={"generation": "private-input"},
        )
        assert invalid.status_code == 422 and "private-input" not in invalid.text
        assert invalid.headers["cache-control"] == "no-store"


def test_device_readiness_endpoint_replaces_per_view_consent_endpoint():
    from gilbic_backend.screen_share_api import (
        screen_share_actor,
        screen_share_repository,
    )

    calls = []

    class Repository:
        def ready(self, actor, sid, generation):
            calls.append((actor, sid, generation))
            return {"id": str(sid), "state": "active", "generation": generation}

    actor = object()
    app = create_app()
    app.dependency_overrides[screen_share_actor] = lambda: actor
    app.dependency_overrides[screen_share_repository] = Repository
    sid = uuid4()
    with TestClient(app) as client:
        result = client.post(
            f"/api/v1/screen-shares/{sid}/ready", json={"generation": 1}
        )
        assert result.status_code == 200
        assert result.json()["state"] == "active"
        assert result.headers["cache-control"] == "no-store"
        assert calls == [(actor, sid, 1)]
        assert (
            client.post(
                f"/api/v1/screen-shares/{sid}/accept", json={"generation": 1}
            ).status_code
            == 404
        )
        assert calls == [(actor, sid, 1)]
