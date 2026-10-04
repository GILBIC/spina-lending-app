"""Correlate requests without recording identities, payloads or URL parameters."""

from __future__ import annotations

import json
import logging
from time import perf_counter
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

LOGGER = logging.getLogger("gilbic.request")
METHODS = frozenset({"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"})


class _OfficeFinderAccessFilter(logging.Filter):
    """Redact Uvicorn's raw request-target before handlers can format it."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) == 5 and isinstance(args[2], str):
            target = args[2].split("?", 1)[0]
            base = "/api/v1/management/onboarding/applicants"
            if (
                target == base
                or target == base + "/"
                or target.startswith(base + "/by-reference/")
            ):
                if target.startswith(base + "/by-reference/"):
                    suffix = target.rsplit("/", 1)[-1]
                    suffix = (
                        suffix
                        if suffix in ("applications", "case", "cif-client")
                        else "read"
                    )
                    target = base + "/by-reference/{application_reference}/" + suffix
                record.args = (*args[:2], target, *args[3:])
        return True


class RequestObservabilityMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        logger = logging.getLogger("uvicorn.access")
        if not any(
            isinstance(item, _OfficeFinderAccessFilter) for item in logger.filters
        ):
            logger.addFilter(_OfficeFinderAccessFilter())

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        started = perf_counter()
        status = 500
        completed = False

        async def traced_send(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])
                headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != b"x-request-id"
                ]
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, traced_send)
            completed = True
        finally:
            route = getattr(scope.get("route"), "path", "unmatched")
            method = scope.get("method", "")
            LOGGER.info(
                json.dumps(
                    {
                        "event": "http_request",
                        "request_id": request_id,
                        "method": method if method in METHODS else "OTHER",
                        "route": route,
                        "status": status,
                        "duration_ms": round((perf_counter() - started) * 1000, 3),
                        "completed": completed,
                    },
                    separators=(",", ":"),
                )
            )
