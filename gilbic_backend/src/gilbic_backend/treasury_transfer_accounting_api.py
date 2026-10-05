"""Private explicit review and confirmation of actual owned-wallet transfer legs."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from .office_review_evidence_route import PrivateOfficeRoute
from .treasury_api import call
from .treasury_receipt_accounting_api import receipt_accounting_actor
from .treasury_transfer_accounting_repository import (
    PostgresTreasuryTransferAccountingRepository,
)


class TransferPrepareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    leg: Literal["source", "destination"]
    source_mapping_id: UUID
    destination_mapping_id: UUID
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_id: UUID


class TransferPostRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmation_token: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirm: StrictBool = False


def treasury_transfer_accounting_repository_dependency():
    return PostgresTreasuryTransferAccountingRepository()


def create_treasury_transfer_accounting_router():
    router = APIRouter(
        tags=["management financial accounting"], route_class=PrivateOfficeRoute
    )
    actor_dependency = Depends(receipt_accounting_actor)
    repository_dependency = Depends(treasury_transfer_accounting_repository_dependency)

    def review(
        transfer_id: UUID,
        leg: Literal["source", "destination"],
        source_mapping_id: UUID,
        destination_mapping_id: UUID,
        actor=actor_dependency,
        repository=repository_dependency,
    ):
        return call(
            lambda: repository.review(
                actor,
                transfer_id=transfer_id,
                leg=leg,
                source_mapping_id=source_mapping_id,
                destination_mapping_id=destination_mapping_id,
            )
        )

    def prepare(
        transfer_id: UUID,
        body: TransferPrepareRequest,
        actor=actor_dependency,
        repository=repository_dependency,
    ):
        return call(
            lambda: repository.prepare(
                actor, transfer_id=transfer_id, **body.model_dump()
            )
        )

    def read_preparation(
        preparation_id: UUID, actor=actor_dependency, repository=repository_dependency
    ):
        return call(
            lambda: repository.read_preparation(actor, preparation_id=preparation_id)
        )

    def post(
        preparation_id: UUID,
        body: TransferPostRequest,
        actor=actor_dependency,
        repository=repository_dependency,
    ):
        if not body.confirm:
            raise HTTPException(
                409,
                detail={
                    "code": "transfer_accounting_confirmation_required",
                    "message": "Explicit confirmation of the retained transfer accounting review is required.",
                },
            )
        return call(
            lambda: repository.post(
                actor,
                preparation_id=preparation_id,
                **body.model_dump(exclude={"confirm"}),
            )
        )

    for prefix in (
        "/api/v1/management/financial-accounting/treasury",
        "/api/mobile/v1/management/financial-accounting/treasury",
    ):
        for path, endpoint, method in (
            ("/transfers/{transfer_id}/review", review, "GET"),
            ("/transfers/{transfer_id}/prepare", prepare, "POST"),
            ("/transfer-preparations/{preparation_id}", read_preparation, "GET"),
            ("/transfer-preparations/{preparation_id}/post", post, "POST"),
        ):
            router.add_api_route(
                prefix + path,
                endpoint,
                methods=[method],
                include_in_schema="/mobile/" not in prefix,
            )
    return router
