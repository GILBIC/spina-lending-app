"""Bound incoming bodies before JSON parsing without buffering another copy."""

from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Includes a 10 MiB support file encoded as base64 plus its JSON metadata.
# Individual upload routes keep their existing, smaller limits.
MAX_REQUEST_BYTES = 16 * 1024 * 1024
TOO_LARGE = "Request body must contain at most 16 MiB."


class RequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        lengths = [
            value
            for key, value in scope.get("headers", [])
            if key.lower() == b"content-length"
        ]
        if len(lengths) > 1 or (lengths and not lengths[0].isdigit()):
            await JSONResponse({"detail": "Invalid Content-Length."}, status_code=400)(
                scope, receive, send
            )
            return
        if lengths:
            length = lengths[0].lstrip(b"0") or b"0"
            ceiling = str(MAX_REQUEST_BYTES).encode("ascii")
            # Compare decimal digits without parsing an unbounded integer.
            if len(length) > len(ceiling) or (
                len(length) == len(ceiling) and length > ceiling
            ):
                await JSONResponse({"detail": TOO_LARGE}, status_code=413)(
                    scope, receive, send
                )
                return
            # Keep existing route-specific integer parsing bounded as well.
            if length != lengths[0]:
                scope["headers"] = [
                    (key, length if key.lower() == b"content-length" else value)
                    for key, value in scope["headers"]
                ]

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > MAX_REQUEST_BYTES:
                    # FastAPI preserves HTTPException raised while reading JSON;
                    # a generic exception would instead become a misleading 400.
                    raise HTTPException(status_code=413, detail=TOO_LARGE)
            return message

        await self.app(scope, limited_receive, send)
