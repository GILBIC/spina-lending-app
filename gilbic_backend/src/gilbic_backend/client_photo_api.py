from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from starlette.concurrency import run_in_threadpool

from .account_repository import AccountContext, PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .client_photo_repository import (
    ALLOWED_CONTENT_TYPES,
    MAX_PHOTO_BYTES,
    ClientPhotoConflict,
    ClientPhotoForbidden,
    ClientPhotoNotFound,
    InvalidClientPhoto,
    PostgresClientPhotoRepository,
    can_upload,
    prepare_photo,
)
from .office_review_evidence_route import PrivateOfficeRoute
from .request_auth import authenticated_device_context


def client_photo_repository_dependency() -> PostgresClientPhotoRepository:
    return PostgresClientPhotoRepository()


def _actor(
    auth: Annotated[SupabaseAuthClient, Depends(auth_client_dependency)],
    accounts: Annotated[
        PostgresAccountRepository, Depends(account_repository_dependency)
    ],
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> AccountContext:
    return authenticated_device_context(
        authorization=authorization,
        device_identifier=x_device_id,
        auth=auth,
        accounts=accounts,
    )


Actor = Annotated[AccountContext, Depends(_actor)]
Photos = Annotated[
    PostgresClientPhotoRepository, Depends(client_photo_repository_dependency)
]


def _call(operation, **values):
    try:
        return operation(**values)
    except ClientPhotoNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except ClientPhotoForbidden as exc:
        raise HTTPException(403, str(exc)) from exc
    except ClientPhotoConflict as exc:
        raise HTTPException(409, str(exc)) from exc


def create_client_photo_router() -> APIRouter:
    router = APIRouter(tags=["client photos"], route_class=PrivateOfficeRoute)

    @router.get("/api/v1/clients/{client_id}/photo")
    @router.get("/api/mobile/v1/clients/{client_id}/photo", include_in_schema=False)
    def metadata(
        client_id: UUID,
        actor: Actor,
        photos: Photos,
    ):
        return {
            "success": True,
            "data": _call(photos.get, actor=actor, client_id=client_id),
        }

    @router.get("/api/v1/clients/{client_id}/photo/content")
    @router.get(
        "/api/mobile/v1/clients/{client_id}/photo/content", include_in_schema=False
    )
    def content(
        client_id: UUID,
        photo_id: UUID,
        actor: Actor,
        photos: Photos,
    ):
        data, media_type = _call(
            photos.content, actor=actor, client_id=client_id, photo_id=photo_id
        )
        return Response(
            data,
            media_type=media_type,
            headers={
                "X-Content-Type-Options": "nosniff",
                "Content-Disposition": 'inline; filename="client-photo.jpg"',
                "Content-Security-Policy": "default-src 'none'; sandbox",
                "X-Frame-Options": "DENY",
            },
        )

    @router.post("/api/v1/clients/{client_id}/photo")
    @router.post("/api/mobile/v1/clients/{client_id}/photo", include_in_schema=False)
    async def upload(
        request: Request,
        client_id: UUID,
        request_id: UUID,
        expected_version: Annotated[int, Query(ge=0, le=2147483646)],
        actor: Actor,
        photos: Photos,
    ):
        if not can_upload(actor):
            raise HTTPException(
                403, "Office CIF permission is required to upload client photos."
            )
        media_type = (
            request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        )
        if media_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(415, "Choose a JPEG or PNG client photo.")
        raw_length = request.headers.get("content-length")
        if raw_length and (not raw_length.isdecimal() or len(raw_length) > 10):
            raise HTTPException(400, "Invalid Content-Length.")
        if raw_length and int(raw_length) > MAX_PHOTO_BYTES:
            raise HTTPException(413, "Choose a photo up to 5 MB.")
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_PHOTO_BYTES:
                raise HTTPException(413, "Choose a photo up to 5 MB.")
            body.extend(chunk)
        try:
            prepared = await run_in_threadpool(prepare_photo, bytes(body), media_type)
        except InvalidClientPhoto as exc:
            raise HTTPException(400, str(exc)) from exc
        result = await run_in_threadpool(
            _call,
            photos.upload,
            actor=actor,
            client_id=client_id,
            request_id=request_id,
            expected_version=expected_version,
            prepared=prepared,
        )
        return {"success": True, "data": result}

    return router
