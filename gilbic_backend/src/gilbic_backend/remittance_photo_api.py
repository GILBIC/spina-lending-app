from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .remittance_photo_repository import (
    PostgresRemittancePhotoRepository,
    RemittancePhotoError,
    RemittancePhotoForbidden,
    RemittancePhotoInvalid,
    RemittancePhotoLocked,
    RemittancePhotoNotFound,
    RemittancePhotoRecord,
)
from .request_auth import authenticated_device_context


def remittance_photo_repository_dependency() -> PostgresRemittancePhotoRepository:
    return PostgresRemittancePhotoRepository()


def _photo_payload(record: RemittancePhotoRecord) -> dict[str, object]:
    return {
        "photo_id": str(record.photo_id),
        "remittance_id": str(record.remittance_id),
        "version": record.version,
        "original_filename": record.original_filename,
        "content_type": record.content_type,
        "byte_size": record.byte_size,
        "sha256_hex": record.sha256_hex,
        "uploaded_at": record.uploaded_at.isoformat(),
        "photo_url": (
            f"/api/mobile/v1/remittances/{record.remittance_id}/handover-photo"
        ),
    }


def _raise_photo_error(error: RemittancePhotoError) -> None:
    if isinstance(error, RemittancePhotoNotFound):
        status = 404
    elif isinstance(error, RemittancePhotoForbidden):
        status = 403
    elif isinstance(error, RemittancePhotoInvalid):
        status = 422
    elif isinstance(error, RemittancePhotoLocked):
        status = 409
    else:
        status = 409
    raise HTTPException(
        status_code=status,
        detail={"code": error.code, "message": str(error)},
    ) from error


def create_remittance_photo_router() -> APIRouter:
    router = APIRouter(tags=["remittance handover photos"])

    @router.post("/api/v1/collector/remittances/{remittance_id}/handover-photo")
    @router.post(
        "/api/mobile/v1/collector/remittances/{remittance_id}/handover-photo",
        include_in_schema=False,
    )
    async def upload_handover_photo(
        remittance_id: UUID,
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        x_file_name: str | None = Header(default=None, alias="X-File-Name"),
        content_type: str | None = Header(default=None, alias="Content-Type"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        photos: PostgresRemittancePhotoRepository = Depends(
            remittance_photo_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="remittance.create",
            permission_error="Remittance creation permission is required.",
        )
        photo_data = await request.body()
        try:
            record = photos.upload(
                remittance_id=remittance_id,
                actor_user_id=actor.user_id,
                content_type=content_type or "application/octet-stream",
                original_filename=x_file_name or "handover-photo",
                photo_data=photo_data,
            )
        except RemittancePhotoError as error:
            _raise_photo_error(error)
        return {
            "success": True,
            "message": "Handover photo saved as permanent remittance evidence.",
            "data": _photo_payload(record),
        }

    @router.get("/api/v1/remittances/{remittance_id}/handover-photo")
    @router.get(
        "/api/mobile/v1/remittances/{remittance_id}/handover-photo",
        include_in_schema=False,
    )
    def view_handover_photo(
        remittance_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        photos: PostgresRemittancePhotoRepository = Depends(
            remittance_photo_repository_dependency
        ),
    ) -> Response:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="remittance.view",
            permission_error="Remittance view permission is required.",
        )
        try:
            record = photos.latest_for_actor(
                remittance_id=remittance_id,
                actor_user_id=actor.user_id,
                include_data=True,
            )
        except RemittancePhotoError as error:
            _raise_photo_error(error)
        filename = record.original_filename or f"{record.remittance_id}.jpg"
        safe_filename = filename.replace('"', "").replace("\r", "").replace("\n", "")
        return Response(
            content=record.photo_data or b"",
            media_type=record.content_type,
            headers={
                "Cache-Control": "private, no-store",
                "Content-Disposition": f'inline; filename="{safe_filename}"',
                "X-Photo-Version": str(record.version),
                "X-Photo-SHA256": record.sha256_hex,
            },
        )

    return router
