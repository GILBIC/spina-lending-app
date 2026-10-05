"""Private explicit review and confirmation of actual protected loan payout stages."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from .loan_payout_accounting_repository import (
    PostgresLoanPayoutAccountingRepository,
)
from .office_review_evidence_route import PrivateOfficeRoute
from .treasury_api import call
from .treasury_receipt_accounting_api import receipt_accounting_actor


class PayoutPrepareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage: Literal["debit", "completion"]
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_id: UUID


class PayoutPostRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmation_token: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirm: StrictBool = False


def loan_payout_accounting_repository_dependency():
    return PostgresLoanPayoutAccountingRepository()


def create_loan_payout_accounting_router():
    router = APIRouter(
        tags=["management financial accounting"], route_class=PrivateOfficeRoute
    )
    actor_dependency = Depends(receipt_accounting_actor)
    repository_dependency = Depends(loan_payout_accounting_repository_dependency)

    def review(
        payout_id: UUID,
        stage: Literal["debit", "completion"],
        actor=actor_dependency,
        repository=repository_dependency,
    ):
        return call(
            lambda: repository.review(
                actor,
                payout_id=payout_id,
                stage=stage,
            )
        )

    def prepare(
        payout_id: UUID,
        body: PayoutPrepareRequest,
        actor=actor_dependency,
        repository=repository_dependency,
    ):
        return call(
            lambda: repository.prepare(actor, payout_id=payout_id, **body.model_dump())
        )

    def read_preparation(
        preparation_id: UUID, actor=actor_dependency, repository=repository_dependency
    ):
        return call(
            lambda: repository.read_preparation(actor, preparation_id=preparation_id)
        )

    def post(
        preparation_id: UUID,
        body: PayoutPostRequest,
        actor=actor_dependency,
        repository=repository_dependency,
    ):
        if not body.confirm:
            raise HTTPException(
                409,
                detail={
                    "code": "payout_accounting_confirmation_required",
                    "message": "Explicit confirmation of the retained payout accounting review is required.",
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
            ("/payouts/{payout_id}/review", review, "GET"),
            ("/payouts/{payout_id}/prepare", prepare, "POST"),
            ("/payout-preparations/{preparation_id}", read_preparation, "GET"),
            ("/payout-preparations/{preparation_id}/post", post, "POST"),
        ):
            router.add_api_route(
                prefix + path,
                endpoint,
                methods=[method],
                include_in_schema="/mobile/" not in prefix,
            )
    return router
