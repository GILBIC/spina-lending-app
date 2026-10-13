"""Private explicit review and confirmation of actual protected loan payout stages."""

from datetime import date
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

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


class RenewalQualitativeAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cash_flow_terms_reviewed: StrictBool
    substantial_change_assessed: StrictBool
    signed_contract_reviewed: StrictBool
    decision_basis: str = Field(min_length=20, max_length=4000)

    @model_validator(mode="after")
    def require_review(self) -> Self:
        if (
            not self.cash_flow_terms_reviewed
            or not self.substantial_change_assessed
            or not self.signed_contract_reviewed
        ):
            raise ValueError(
                "Explicit review of the contractual and substantial changes is required."
            )
        return self


class RenewalMeasurementReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["modification_no_derecognition", "derecognition"]
    accounting_policy_reference: str = Field(min_length=1, max_length=1000)
    qualitative_assessment: RenewalQualitativeAssessment
    decision_rationale: str = Field(min_length=20, max_length=4000)
    settlement_consideration: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    settlement_rebate: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    settlement_basis: str = Field(min_length=20, max_length=4000)
    new_initial_fair_value: Decimal | None = Field(
        default=None, gt=0, max_digits=18, decimal_places=2
    )
    fair_value_effective_date: date | None = None
    fair_value_basis: str | None = Field(default=None, min_length=20, max_length=4000)
    day_one_difference_rationale: str | None = Field(
        default=None, min_length=20, max_length=4000
    )

    @model_validator(mode="after")
    def require_treatment_basis(self) -> Self:
        fields = (
            self.new_initial_fair_value,
            self.fair_value_effective_date,
            self.fair_value_basis,
            self.day_one_difference_rationale,
        )
        if self.decision == "derecognition" and any(value is None for value in fields):
            raise ValueError(
                "Derecognition requires explicit effective-date fair value and difference evidence."
            )
        if self.decision == "modification_no_derecognition" and any(
            value is not None for value in fields
        ):
            raise ValueError(
                "Modification preserves the original EIR measurement basis."
            )
        return self


class RenewalMeasurementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_id: UUID
    evidence_id: UUID
    review: RenewalMeasurementReview
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

    def renewal_review(
        payout_id: UUID, actor=actor_dependency, repository=repository_dependency
    ):
        return call(
            lambda: repository.renewal_measurement_review(actor, payout_id=payout_id)
        )

    def retain_renewal_review(
        payout_id: UUID,
        body: RenewalMeasurementRequest,
        actor=actor_dependency,
        repository=repository_dependency,
    ):
        if not body.confirm:
            raise HTTPException(
                409,
                detail={
                    "code": "renewal_measurement_confirmation_required",
                    "message": "Explicit confirmation of the renewal treatment and measurement is required.",
                },
            )
        return call(
            lambda: repository.retain_renewal_measurement(
                actor,
                payout_id=payout_id,
                source_digest=body.source_digest,
                request_id=body.request_id,
                evidence_id=body.evidence_id,
                review=body.review.model_dump(mode="json"),
            )
        )

    for prefix in (
        "/api/v1/management/financial-accounting/treasury",
        "/api/mobile/v1/management/financial-accounting/treasury",
    ):
        for path, endpoint, method in (
            ("/payouts/{payout_id}/renewal-measurement", renewal_review, "GET"),
            ("/payouts/{payout_id}/renewal-measurement", retain_renewal_review, "POST"),
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
