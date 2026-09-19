from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from .first_loan_api import first_loan_repository_dependency
from .first_loan_documents import render_packet
from .first_loan_repository import (
    APPROVE_PERMISSION,
    FirstLoanAccessDenied,
    FirstLoanConflict,
)
from .office_review_evidence_api import _actor
from .office_review_evidence_route import PrivateOfficeRoute
from .office_review_evidence_storage import EvidenceFileError


class IssuePacketRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    packet_hash: str = Field(pattern="^[0-9a-f]{64}$")


def create_first_loan_document_router() -> APIRouter:
    router = APIRouter(
        prefix="/api/v1/management/first-loans",
        tags=["first-loans"],
        route_class=PrivateOfficeRoute,
    )

    @router.post("/{loan_id}/documents", status_code=201)
    def issue(
        loan_id: UUID,
        request: IssuePacketRequest,
        actor=Depends(_actor),
        repository=Depends(first_loan_repository_dependency),
    ):
        if (
            "management" not in actor.roles
            or APPROVE_PERMISSION not in actor.permissions
            or actor.registered_device_id is None
        ):
            raise HTTPException(
                403,
                "Management exact-term approval permission is required to issue the packet.",
            )
        args = dict(
            loan_id=loan_id,
            actor_user_id=actor.user_id,
            registered_device_id=actor.registered_device_id,
        )
        try:
            record = repository.get(**args)
            if request.packet_hash != record["packet_hash"]:
                raise FirstLoanConflict(
                    "The packet changed. Load the authoritative record."
                )
            if record["document"] is not None:
                metadata, _ = repository.packet_document(**args)
                return metadata
            content = render_packet(record)
            return repository.register_packet_document(
                **args, packet_hash=request.packet_hash, content=content,
                expected_pricing_snapshot=record['pricing_snapshot']
            )
        except (FirstLoanConflict, FirstLoanAccessDenied, EvidenceFileError) as error:
            raise HTTPException(
                403 if isinstance(error, FirstLoanAccessDenied) else 409, str(error)
            ) from error

    @router.get("/{loan_id}/documents")
    def download(
        loan_id: UUID,
        actor=Depends(_actor),
        repository=Depends(first_loan_repository_dependency),
    ):
        if actor.registered_device_id is None:
            raise HTTPException(403, "An active registered device is required.")
        try:
            metadata, content = repository.packet_document(
                loan_id=loan_id,
                actor_user_id=actor.user_id,
                registered_device_id=actor.registered_device_id,
            )
        except (FirstLoanConflict, FirstLoanAccessDenied, EvidenceFileError) as error:
            raise HTTPException(
                403 if isinstance(error, FirstLoanAccessDenied) else 409, str(error)
            ) from error
        return Response(
            content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="loan-packet-{loan_id}.pdf"',
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "sandbox",
            },
        )

    return router
