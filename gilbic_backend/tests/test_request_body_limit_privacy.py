"""Size rejections preserve private-response policy before and during reads.

Exercise the actual middleware and private route in a small FastAPI stack.
No authentication, database, deployed-service or throughput acceptance implied.
"""

from __future__ import annotations

import asyncio
import json
import logging

import pytest
from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from gilbic_backend.office_review_evidence_route import PrivateOfficeRoute
from gilbic_backend.request_body_limit import RequestBodyLimitMiddleware
from gilbic_backend.request_observability import RequestObservabilityMiddleware

ORIGIN = b"https://spina.com.ph"
PRIVATE_MARKER = b"SYNTHETIC_PRIVATE_REQUEST_CONTENT"


def _app():
    app = FastAPI()
    # Same middleware order as create_app; no external services in this proof.
    app.add_middleware(RequestBodyLimitMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=[ORIGIN.decode()])
    app.add_middleware(RequestObservabilityMiddleware)
    router = APIRouter(route_class=PrivateOfficeRoute)

    @router.post("/private/raw")
    async def raw(request: Request):
        return {"bytes": len(await request.body())}

    @router.post("/private/json")
    async def structured(payload: dict[str, int]):
        return {"fields": len(payload)}

    app.include_router(router)
    return app


async def _invoke(app, *, path="/private/json", lengths=(), chunks=()):
    messages = []
    received = 0
    iterator = iter(chunks)

    async def receive():
        nonlocal received
        received += 1
        await asyncio.sleep(0)  # Permit real per-request interleaving.
        return next(iterator)

    async def send(message):
        messages.append(message)

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "https",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"private=" + PRIVATE_MARKER,
            "headers": [
                (b"content-type", b"application/json"),
                (b"origin", ORIGIN),
                (b"authorization", b"Bearer " + PRIVATE_MARKER),
                *((b"content-length", value) for value in lengths),
            ],
            "server": ("testserver", 443),
            "client": ("127.0.0.1", 12345),
        },
        receive,
        send,
    )
    starts = [m for m in messages if m["type"] == "http.response.start"]
    assert len(starts) == 1
    content = b"".join(m.get("body", b"") for m in messages)
    return starts[0]["status"], dict(starts[0]["headers"]), content, received


def _assert_private_response(result, expected_status, caplog):
    status, headers, body, _ = result
    assert status == expected_status
    assert headers[b"access-control-allow-origin"] == ORIGIN
    assert len(headers[b"x-request-id"]) == 32
    assert PRIVATE_MARKER not in body
    assert PRIVATE_MARKER.decode() not in caplog.text
    events = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "gilbic.request"
    ]
    assert any(
        event["request_id"] == headers[b"x-request-id"].decode()
        and event["status"] == expected_status
        and event["completed"]
        for event in events
    )
    assert headers.get(b"cache-control") == b"no-store"


@pytest.mark.parametrize(
    ("lengths", "status"),
    [([b"-1"], 400), ([b"1", b"2"], 400), ([b"16777217"], 413)],
)
def test_pre_read_rejection_preserves_private_headers(lengths, status, caplog):
    caplog.set_level(logging.INFO, logger="gilbic.request")
    result = asyncio.run(_invoke(_app(), lengths=lengths))
    assert result[3] == 0
    _assert_private_response(result, status, caplog)


@pytest.mark.parametrize("path", ["/private/raw", "/private/json"])
def test_streamed_rejection_preserves_private_headers_and_stops_reading(path, caplog):
    caplog.set_level(logging.INFO, logger="gilbic.request")
    chunks = [
        {"type": "http.request", "body": b" " * (1024 * 1024), "more_body": True}
    ] * 17
    chunks.append({"type": "http.request", "body": PRIVATE_MARKER})
    result = asyncio.run(_invoke(_app(), path=path, chunks=chunks))
    assert result[3] == 17
    _assert_private_response(result, 413, caplog)


@pytest.mark.parametrize("payload", [b"{}", b'{"field":"' + PRIVATE_MARKER + b'"}'])
def test_ordinary_private_success_and_validation_remain_unchanged(payload, caplog):
    caplog.set_level(logging.INFO, logger="gilbic.request")
    result = asyncio.run(
        _invoke(_app(), chunks=[{"type": "http.request", "body": payload}])
    )
    _assert_private_response(result, 200 if payload == b"{}" else 422, caplog)


def test_overlapping_requests_do_not_share_body_count_or_response_identity(caplog):
    caplog.set_level(logging.INFO, logger="gilbic.request")
    app = _app()
    large = [
        {"type": "http.request", "body": b" " * (1024 * 1024), "more_body": True}
    ] * 17
    small = [{"type": "http.request", "body": b"{}"}]

    async def overlap():
        return await asyncio.gather(
            _invoke(app, chunks=large), _invoke(app, chunks=small)
        )

    rejected, accepted = asyncio.run(overlap())
    assert rejected[3] == 17 and accepted[3] == 1
    assert rejected[1][b"x-request-id"] != accepted[1][b"x-request-id"]
    _assert_private_response(rejected, 413, caplog)
    _assert_private_response(accepted, 200, caplog)
