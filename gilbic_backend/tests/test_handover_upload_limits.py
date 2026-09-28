"""Finite ASGI streams and blocking boundary doubles; no network or database."""

import asyncio
from contextlib import contextmanager
from threading import Event
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException
from gilbic_backend.auth_client import SupabaseAuthError
from gilbic_backend.remittance_photo_repository import PostgresRemittancePhotoRepository
from starlette.requests import Request

from gilbic_backend import remittance_photo_api as remittance
from gilbic_backend import renewal_workflow_api as renewal

USER_ID = UUID(int=1)
MIB = 1024 * 1024


@pytest.fixture(params=["remittance", "renewal"])
def upload(request):
    if request.param == "remittance":
        module, factory, limit = (
            remittance,
            remittance.create_remittance_photo_router,
            5 * MIB,
        )
        extra = {
            "remittance_id": UUID(int=2),
            "photos": PostgresRemittancePhotoRepository(),
        }
    else:
        module, factory, limit = (
            renewal,
            renewal.create_renewal_workflow_router,
            8 * MIB,
        )
        extra = {"request_id": UUID(int=2)}
    endpoint = next(
        route.endpoint
        for route in factory().routes
        if route.name == "upload_handover_photo"
    )
    return SimpleNamespace(module=module, endpoint=endpoint, limit=limit, extra=extra)


def synthetic_request(chunks, *, content_length=None):
    delivered = []
    headers = [(b"content-type", b"image/jpeg")]
    if content_length is not None:
        headers.append((b"content-length", str(content_length).encode()))

    async def receive():
        index = len(delivered)
        assert index < len(chunks), "Upload read past the supplied stream"
        delivered.append(len(chunks[index]))
        return {
            "type": "http.request",
            "body": chunks[index],
            "more_body": index + 1 < len(chunks),
        }

    return Request(
        {"type": "http", "method": "POST", "path": "/photo", "headers": headers},
        receive,
    ), delivered


async def invoke(upload, request, **overrides):
    arguments = dict(
        request=request,
        authorization="Bearer synthetic",
        x_device_id="device",
        x_file_name="handover.jpg",
        content_type="image/jpeg",
        auth=None,
        accounts=None,
        **upload.extra,
    )
    arguments.update(overrides)
    return await upload.endpoint(**arguments)


@pytest.mark.parametrize("content_length", [None, 1])
def test_chunked_upload_stops_at_limit_without_buffering_the_remaining_body(
    monkeypatch, upload, content_length
):
    monkeypatch.setattr(
        upload.module,
        "authenticated_device_context",
        lambda **kwargs: SimpleNamespace(user_id=USER_ID),
    )
    chunks = [b"x" * MIB] * (upload.limit // MIB + 3)
    request, delivered = synthetic_request(chunks, content_length=content_length)

    with pytest.raises(HTTPException) as error:
        asyncio.run(invoke(upload, request))

    assert error.value.status_code == 413
    assert sum(delivered) == upload.limit + MIB
    assert len(delivered) < len(chunks)
    assert not hasattr(request, "_body")


@pytest.mark.parametrize("declared_length", ["oversized", "invalid", "-1"])
def test_invalid_or_oversized_content_length_is_rejected_before_reading(
    monkeypatch, upload, declared_length
):
    monkeypatch.setattr(
        upload.module,
        "authenticated_device_context",
        lambda **kwargs: SimpleNamespace(user_id=USER_ID),
    )
    length = upload.limit + 1 if declared_length == "oversized" else declared_length
    request, delivered = synthetic_request([b""], content_length=length)

    with pytest.raises(HTTPException) as error:
        asyncio.run(invoke(upload, request))

    assert error.value.status_code == 413
    assert delivered == []


@pytest.mark.parametrize("boundary", ["auth", "storage"])
def test_other_tasks_progress_while_upload_waits_on_sync_services(
    monkeypatch, upload, boundary
):
    started, release = Event(), Event()
    progressed = []

    def blocking_boundary():
        started.set()
        progressed.append(release.wait(timeout=0.5))

    if boundary == "auth":

        def get_user(**kwargs):
            blocking_boundary()
            raise SupabaseAuthError(
                "Unavailable test identity service", status_code=503
            )

        overrides = {"auth": SimpleNamespace(get_user=get_user)}
        expected_status = 503
    else:
        monkeypatch.setattr(
            upload.module,
            "authenticated_device_context",
            lambda **kwargs: SimpleNamespace(user_id=USER_ID),
        )
        expected_status = 409
        overrides = {}
        if upload.module is remittance:

            def save(**kwargs):
                blocking_boundary()
                raise remittance.RemittancePhotoLocked("Already accepted")

            overrides["photos"] = SimpleNamespace(upload=save)
        else:

            @contextmanager
            def connect():
                blocking_boundary()
                raise HTTPException(
                    status_code=409, detail="Controlled database rejection"
                )
                yield

            monkeypatch.setattr(renewal, "open_connection", connect)

    async def exercise():
        async def other_request():
            while not started.is_set():
                await asyncio.sleep(0)
            release.set()

        other = asyncio.create_task(other_request())
        request, _ = synthetic_request([b"\xff\xd8\xffphoto"])
        try:
            with pytest.raises(HTTPException) as error:
                await invoke(upload, request, **overrides)
            assert error.value.status_code == expected_status
        finally:
            release.set()
            await other

    asyncio.run(exercise())
    assert progressed == [True], (
        "Upload blocked the event loop while a synchronous service waited"
    )


def test_renewal_upload_at_limit_retains_evidence_and_audit(monkeypatch):
    writes = []

    class Database:
        @contextmanager
        def cursor(self, **kwargs):
            yield self

        def execute(self, sql, params):
            writes.append((" ".join(sql.split()), params))

        def fetchone(self):
            return {"next_version": 2}

    @contextmanager
    def connect():
        yield Database()

    monkeypatch.setattr(renewal, "open_connection", connect)
    monkeypatch.setattr(
        renewal,
        "authenticated_device_context",
        lambda **kwargs: SimpleNamespace(user_id=USER_ID),
    )
    monkeypatch.setattr(
        renewal,
        "_renewal_row",
        lambda *args, **kwargs: {
            "assigned_collector_user_id": USER_ID,
            "cash_given_to_client_at": "2026-09-29",
        },
    )
    endpoint = next(
        route.endpoint
        for route in renewal.create_renewal_workflow_router().routes
        if route.name == "upload_handover_photo"
    )
    upload = SimpleNamespace(endpoint=endpoint, extra={"request_id": UUID(int=2)})
    payload = b"\xff\xd8\xff" + b"x" * (8 * MIB - 3)
    request, delivered = synthetic_request([payload], content_length=8 * MIB)

    result = asyncio.run(invoke(upload, request))

    assert result["success"] is True
    assert result["data"]["version"] == 2
    assert result["data"]["status"] == "under_review"
    assert delivered == [8 * MIB]
    insert = next(
        params
        for sql, params in writes
        if "insert into lending.renewal_handover_photos" in sql
    )
    assert insert[:6] == (
        UUID(int=2),
        2,
        USER_ID,
        "handover.jpg",
        "image/jpeg",
        8 * MIB,
    )
    assert insert[7] == payload
    assert result["data"]["sha256"] == insert[6]
    assert any(
        "set handover_proof_status='under_review'" in sql and params == (UUID(int=2),)
        for sql, params in writes
    )
    audit = next(
        params for sql, params in writes if "insert into core.audit_logs" in sql
    )
    assert audit[:3] == (USER_ID, "renewal.handover_proof.submitted", UUID(int=2))
    assert audit[3] == f"version=2;sha256={insert[6]}"
