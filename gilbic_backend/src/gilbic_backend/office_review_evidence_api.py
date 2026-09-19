from __future__ import annotations

from datetime import timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from starlette.concurrency import run_in_threadpool

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .client_cif_api import _office_cif_actor
from .office_review_evidence_repository import (
    OfficeReviewEvidenceAccessDenied,
    OfficeReviewEvidenceConflict,
    PostgresOfficeReviewEvidenceRepository,
)
from .office_review_evidence_storage import (
    EVIDENCE_MEDIA_TYPES,
    MAX_EVIDENCE_BYTES,
    EvidenceFileError,
    validate_evidence_content,
)


from .office_review_evidence_route import PrivateOfficeRoute

# Compatibility for protected route modules integrated before the shared class
# was extracted to avoid the CIF/evidence router import cycle.
_NoStoreRoute = PrivateOfficeRoute


def office_review_evidence_repository_dependency() -> (
    PostgresOfficeReviewEvidenceRepository
):
    return PostgresOfficeReviewEvidenceRepository()


def _source(
    purpose: Literal["cif_review", "application_review", "privacy_acknowledgment"],
    cif_version_id: UUID,
    application_id: UUID | None = None,
    application_version_id: UUID | None = None,
    optional_service_communications: bool = False,
) -> dict:
    return dict(
        purpose=purpose,
        cif_version_id=cif_version_id,
        application_id=application_id,
        application_version_id=application_version_id,
        optional_service_communications=optional_service_communications,
    )


def _actor(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
    auth: SupabaseAuthClient = Depends(auth_client_dependency),
    accounts: PostgresAccountRepository = Depends(account_repository_dependency),
):
    return _office_cif_actor(
        authorization=authorization,
        x_device_id=x_device_id,
        auth=auth,
        accounts=accounts,
    )


def _translate(error: Exception):
    if isinstance(error, OfficeReviewEvidenceAccessDenied):
        raise HTTPException(
            status_code=403, detail="An active authorized office account is required."
        ) from error
    if isinstance(error, OfficeReviewEvidenceConflict):
        raise HTTPException(status_code=409, detail=str(error)) from error
    raise HTTPException(
        status_code=503, detail="Private signed evidence storage is unavailable."
    ) from error


def create_office_review_evidence_router() -> APIRouter:
    router = APIRouter(tags=["office-review-evidence"], route_class=PrivateOfficeRoute)
    prefix = "/api/v1/management/clients/{client_id}/review-evidence"

    @router.get(prefix + "/context")
    def get_review_evidence_context(
        client_id: UUID,
        source: dict = Depends(_source),
        actor=Depends(_actor),
        repository=Depends(office_review_evidence_repository_dependency),
    ) -> dict:
        try:
            return repository.get_context(
                actor_user_id=actor.user_id, client_id=client_id, **source
            )
        except (
            OfficeReviewEvidenceAccessDenied,
            OfficeReviewEvidenceConflict,
            EvidenceFileError,
        ) as error:
            _translate(error)

    @router.post(prefix, status_code=201)
    async def capture_signed_review_evidence(
        client_id: UUID,
        request: Request,
        request_id: UUID,
        expected_snapshot_sha256: str = Query(pattern="^[0-9a-f]{64}$"),
        witnessed_wet_signature: Literal["true"] = Query(),
        source: dict = Depends(_source),
        actor=Depends(_actor),
        repository=Depends(office_review_evidence_repository_dependency),
    ) -> dict:
        media_type = (
            request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        )
        if media_type not in EVIDENCE_MEDIA_TYPES:
            raise HTTPException(
                status_code=415, detail="A signed PDF, PNG or JPEG scan is required."
            )
        length = request.headers.get("content-length")
        if length is not None and (
            not length.isdecimal() or int(length) > MAX_EVIDENCE_BYTES
        ):
            raise HTTPException(
                status_code=413, detail="Signed evidence must contain at most 10 MiB."
            )
        content = bytearray()
        async for chunk in request.stream():
            if len(content) + len(chunk) > MAX_EVIDENCE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail="Signed evidence must contain at most 10 MiB.",
                )
            content.extend(chunk)
        try:
            validate_evidence_content(bytes(content), media_type)
        except EvidenceFileError as error:
            raise HTTPException(status_code=415, detail=str(error)) from error
        try:
            record = await run_in_threadpool(
                repository.capture,
                actor_user_id=actor.user_id,
                client_id=client_id,
                request_id=request_id,
                expected_snapshot_sha256=expected_snapshot_sha256,
                content=bytes(content),
                media_type=media_type,
                **source,
            )
        except (
            OfficeReviewEvidenceAccessDenied,
            OfficeReviewEvidenceConflict,
            EvidenceFileError,
        ) as error:
            _translate(error)
        return {
            "evidence_id": str(record.id),
            "evidence_reference": record.evidence_reference,
            "client_id": str(record.client_id),
            "cif_version_id": str(record.cif_version_id),
            "application_id": None
            if record.application_id is None
            else str(record.application_id),
            "application_version_id": None
            if record.application_version_id is None
            else str(record.application_version_id),
            "purpose": record.purpose,
            "snapshot_sha256": record.snapshot_sha256,
            "content_sha256": record.content_sha256,
            "media_type": record.media_type,
            "byte_count": record.byte_count,
            "captured_by_user_id": str(record.captured_by_user_id),
            "captured_at": record.captured_at.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        }

    @router.get(prefix + "/{evidence_id}")
    def download_signed_review_evidence(
        client_id: UUID,
        evidence_id: UUID,
        actor=Depends(_actor),
        repository=Depends(office_review_evidence_repository_dependency),
    ) -> Response:
        try:
            record, content = repository.get_content(
                actor_user_id=actor.user_id,
                client_id=client_id,
                record_id=evidence_id,
            )
        except (
            OfficeReviewEvidenceAccessDenied,
            OfficeReviewEvidenceConflict,
            EvidenceFileError,
        ) as error:
            _translate(error)
        extension = {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg"}[
            record.media_type
        ]
        return Response(
            content=content,
            media_type=record.media_type,
            headers={
                "Content-Disposition": f'attachment; filename="review-evidence-{record.id}.{extension}"',
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "sandbox",
                "X-Frame-Options": "DENY",
            },
        )

    return router
