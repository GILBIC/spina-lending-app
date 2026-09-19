from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, StrictBool

from .office_review_evidence_api import _actor, _translate
from .office_review_evidence_route import PrivateOfficeRoute
from .office_review_evidence_repository import (
    OfficeReviewEvidenceAccessDenied,
    OfficeReviewEvidenceConflict,
)
from .privacy_record_repository import PostgresPrivacyRecordRepository, privacy_package


class PrivacyAcknowledgmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cif_version_id: UUID
    optional_service_communications: StrictBool = False
    evidence_reference: str


def privacy_repository_dependency():
    return PostgresPrivacyRecordRepository()


def create_privacy_record_router() -> APIRouter:
    router = APIRouter(
        prefix="/api/v1/management/clients/{client_id}/privacy",
        tags=["client-privacy"],
        route_class=PrivateOfficeRoute,
    )

    @router.get("/context")
    def context(
        client_id: UUID,
        cif_version_id: UUID,
        optional_service_communications: bool = False,
        actor=Depends(_actor),
        repository=Depends(privacy_repository_dependency),
    ):
        try:
            return repository.context(
                actor_user_id=actor.user_id,
                client_id=client_id,
                cif_version_id=cif_version_id,
                optional_service_communications=optional_service_communications,
            )
        except (
            OfficeReviewEvidenceAccessDenied,
            OfficeReviewEvidenceConflict,
        ) as error:
            _translate(error)

    @router.get("/documents/{kind}")
    def document(
        client_id: UUID,
        cif_version_id: UUID,
        kind: Literal["notice", "consent"],
        expected_sha256: str = Query(pattern="^[0-9a-f]{64}$"),
        actor=Depends(_actor),
        repository=Depends(privacy_repository_dependency),
    ):
        try:
            current = repository.context(
                actor_user_id=actor.user_id,
                client_id=client_id,
                cif_version_id=cif_version_id,
            )
            package = privacy_package()
            if not current["issuable"] or not package["issuable"]:
                raise OfficeReviewEvidenceConflict(current["detail"])
            item = package[kind]
            if (
                current["review_snapshot"][kind]["sha256"] != item["sha256"]
                or expected_sha256 != item["sha256"]
            ):
                raise OfficeReviewEvidenceConflict(
                    "Privacy document changed. Refresh the record."
                )
        except (
            OfficeReviewEvidenceAccessDenied,
            OfficeReviewEvidenceConflict,
        ) as error:
            _translate(error)
        return Response(
            content=item["content"],
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="privacy-{kind}.pdf"',
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "sandbox",
            },
        )

    @router.post("/acknowledgments", status_code=201)
    def acknowledge(
        client_id: UUID,
        request: PrivacyAcknowledgmentRequest,
        actor=Depends(_actor),
        repository=Depends(privacy_repository_dependency),
    ):
        try:
            return repository.confirm(
                actor_user_id=actor.user_id, client_id=client_id, **request.model_dump()
            )
        except (
            OfficeReviewEvidenceAccessDenied,
            OfficeReviewEvidenceConflict,
        ) as error:
            _translate(error)

    return router
