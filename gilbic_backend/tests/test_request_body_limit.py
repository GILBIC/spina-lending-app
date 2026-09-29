from __future__ import annotations

import asyncio
import json

import pytest
from fastapi import Request
from gilbic_backend.main import create_app


def invoke(app, *, path="/health/live", headers=(), chunks=(), method="GET"):
    messages = []
    received = 0
    iterator = iter(chunks)

    async def receive():
        nonlocal received
        received += 1
        return next(iterator)

    async def send(message):
        messages.append(message)

    asyncio.run(
        app(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": method,
                "scheme": "https",
                "path": path,
                "raw_path": path.encode(),
                "query_string": b"",
                "headers": list(headers),
                "server": ("testserver", 443),
                "client": ("127.0.0.1", 12345),
            },
            receive,
            send,
        )
    )
    start = next(m for m in messages if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in messages)
    return start["status"], dict(start["headers"]), body, received


def test_oversized_declared_body_is_rejected_before_receiving_any_bytes():
    status, headers, body, received = invoke(
        create_app(), headers=[(b"content-length", b"1073741824")]
    )
    assert status == 413
    assert received == 0
    assert headers[b"x-request-id"]
    assert json.loads(body)["detail"]


@pytest.mark.parametrize("declared_length", [None, b"1"])
@pytest.mark.parametrize("json_body", [False, True])
def test_streamed_body_limit_cannot_be_bypassed_by_missing_or_false_length(
    declared_length, json_body
):
    app = create_app()

    @app.post("/test/body")
    async def body(request: Request):
        return {"bytes": len(await request.body())}

    @app.post("/test/json")
    async def body_json(payload: dict):
        return {"keys": len(payload)}

    chunks = [
        {"type": "http.request", "body": b" " * 1024 * 1024, "more_body": True}
    ] * 17
    chunks.append({"type": "http.request", "body": b"{}", "more_body": False})
    headers = [(b"content-type", b"application/json")]
    if declared_length is not None:
        headers.append((b"content-length", declared_length))
    status, _, _, received = invoke(
        app,
        path="/test/json" if json_body else "/test/body",
        method="POST",
        headers=headers,
        chunks=chunks,
    )
    assert status == 413
    assert received == 17  # Stop at the offending chunk; never consume the rest.


def test_supported_ten_mib_base64_upload_fits_with_json_metadata():
    app = create_app()

    @app.post("/test/support")
    async def support(payload: dict):
        return {"encoded_bytes": len(payload["support_base64"])}

    payload = json.dumps(
        {"support_base64": "A" * 13_981_016, "rationale": "synthetic"}
    ).encode()
    status, _, body, _ = invoke(
        app,
        path="/test/support",
        method="POST",
        headers=[(b"content-type", b"application/json")],
        chunks=[{"type": "http.request", "body": payload, "more_body": False}],
    )
    assert status == 200
    assert json.loads(body) == {"encoded_bytes": 13_981_016}


@pytest.mark.parametrize("lengths", [[b"-1"], [b"oops"], [b"0", b"1"]])
def test_invalid_or_ambiguous_content_length_is_rejected(lengths):
    status, _, _, received = invoke(
        create_app(), headers=[(b"content-length", value) for value in lengths]
    )
    assert status == 400
    assert received == 0


def test_large_decimal_content_length_does_not_need_unbounded_integer_parsing():
    status, _, _, received = invoke(
        create_app(), headers=[(b"content-length", b"9" * 5000)]
    )
    assert status == 413
    assert received == 0


def test_rejection_preserves_allowed_cors_and_server_request_id(monkeypatch):
    from gilbic_backend.config import get_settings

    monkeypatch.setenv("GILBIC_CORS_ORIGINS", "https://spina.com.ph")
    get_settings.cache_clear()
    try:
        status, headers, _, _ = invoke(
            create_app(),
            headers=[
                (b"content-length", b"1073741824"),
                (b"origin", b"https://spina.com.ph"),
            ],
        )
        assert status == 413
        assert headers[b"access-control-allow-origin"] == b"https://spina.com.ph"
        assert headers[b"x-request-id"]
    finally:
        get_settings.cache_clear()


def test_exact_limit_is_accepted_independently_for_each_request():
    app = create_app()

    @app.post("/test/body")
    async def body(request: Request):
        return {"bytes": len(await request.body())}

    chunks = [
        {"type": "http.request", "body": b"x" * 1024 * 1024, "more_body": True}
    ] * 15
    chunks.append(
        {"type": "http.request", "body": b"x" * 1024 * 1024, "more_body": False}
    )
    for _ in range(2):
        status, _, response, _ = invoke(
            app,
            path="/test/body",
            method="POST",
            chunks=chunks,
            headers=[(b"content-length", b"00016777216")],
        )
        assert status == 200
        assert json.loads(response) == {"bytes": 16_777_216}


def test_valid_zero_prefixed_length_cannot_overflow_existing_upload_reader():
    from gilbic_backend.client_payment_proof_api import _upload_bytes

    app = create_app()

    @app.post("/test/upload")
    async def upload(request: Request):
        await _upload_bytes(request)

    status, _, _, _ = invoke(
        app,
        path="/test/upload",
        method="POST",
        headers=[
            (b"content-type", b"image/png"),
            (b"content-length", b"0" * 5000 + b"1"),
        ],
        chunks=[{"type": "http.request", "body": b"x", "more_body": False}],
    )
    assert status == 415  # Existing file validation, not integer parsing failure.
