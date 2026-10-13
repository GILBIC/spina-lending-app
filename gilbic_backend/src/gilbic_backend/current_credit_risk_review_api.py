"""Explicit actual-cutoff risk decisions bound to the source shown to Management."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, StrictBool

from .current_credit_risk_review_repository import (
    PostgresCurrentCreditRiskReviewRepository,
)
from .ecl_credit_risk_label_api import (
    RecoveryLabel,
    ReviewEclCreditRiskLabelsRequest,
    WriteOffLabel,
)
from .office_review_evidence_route import PrivateOfficeRoute
from .retained_cutoff_assessment_api import (
    Accounts,
    AssessmentIdentityRequest,
    Auth,
    Authorization,
    Device,
    _actor,
    _exception,
)
from .retained_cutoff_assessment_repository import CutoffAssessmentError


class CurrentCreditRiskDecision(ReviewEclCreditRiskLabelsRequest):
    default_label: StrictBool
    write_off_label: WriteOffLabel = Field(...)
    recovery_label: RecoveryLabel = Field(...)
    sicr_backstop_rebutted: StrictBool = Field(...)
    default_backstop_rebutted: StrictBool = Field(...)


class CurrentCreditRiskReviewRequest(AssessmentIdentityRequest):
    confirm: StrictBool
    review: CurrentCreditRiskDecision


def current_credit_risk_review_repository_dependency() -> (
    PostgresCurrentCreditRiskReviewRepository
):
    return PostgresCurrentCreditRiskReviewRepository()


Reviews = Annotated[
    PostgresCurrentCreditRiskReviewRepository,
    Depends(current_credit_risk_review_repository_dependency),
]


def create_current_credit_risk_review_router() -> APIRouter:
    router = APIRouter(
        tags=["management financial accounting"], route_class=PrivateOfficeRoute
    )
    base = "/api/v1/management/financial-accounting/period-elapsed-assessments"
    mobile = "/api/mobile/v1/management/financial-accounting/period-elapsed-assessments"

    @router.get(base + "/{period_id}/loans/{loan_id}/risk-review")
    @router.get(
        mobile + "/{period_id}/loans/{loan_id}/risk-review", include_in_schema=False
    )
    def context(
        period_id: UUID,
        loan_id: UUID,
        auth: Auth,
        accounts: Accounts,
        reviews: Reviews,
        authorization: Authorization = None,
        x_device_id: Device = None,
    ):
        actor = _actor(authorization, x_device_id, auth, accounts, "accounting.view")
        try:
            result = reviews.load_context(
                period_id=period_id, loan_id=loan_id, actor_user_id=actor.user_id
            )
        except CutoffAssessmentError as error:
            raise _exception(error) from error
        return {"success": True, "data": result}

    @router.post(base + "/{period_id}/loans/{loan_id}/risk-review")
    @router.post(
        mobile + "/{period_id}/loans/{loan_id}/risk-review", include_in_schema=False
    )
    def retain(
        period_id: UUID,
        loan_id: UUID,
        body: CurrentCreditRiskReviewRequest,
        auth: Auth,
        accounts: Accounts,
        reviews: Reviews,
        authorization: Authorization = None,
        x_device_id: Device = None,
    ):
        actor = _actor(
            authorization,
            x_device_id,
            auth,
            accounts,
            "accounting.ecl.credit_risk_label.review",
        )
        if not body.confirm:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "current_risk_review_confirmation_required",
                    "message": "Explicit confirmation of the shown source and risk decision is required.",
                },
            )
        try:
            result = reviews.retain(
                period_id=period_id,
                loan_id=loan_id,
                actor_user_id=actor.user_id,
                expected_book_id=body.expected_book_id,
                source_digest=body.source_digest,
                review=body.review.model_dump(mode="json"),
            )
        except CutoffAssessmentError as error:
            raise _exception(error) from error
        return {"success": True, "data": result}

    return router
