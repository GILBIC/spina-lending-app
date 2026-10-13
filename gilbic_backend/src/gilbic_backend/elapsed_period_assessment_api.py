"""Explicit dated inputs and protected confirmation of historical assessments."""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr

from .elapsed_period_assessment_repository import (
    PostgresElapsedPeriodAssessmentRepository,
)
from .retained_cutoff_assessment_api import (
    Accounts,
    Auth,
    Authorization,
    Device,
    _actor,
    _exception,
)
from .retained_cutoff_assessment_repository import CutoffAssessmentError


class HistoricalRiskReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    as_of_date: date
    stage_label: Literal["stage_1_12_month"]
    default_label: StrictBool
    write_off_label: Literal["none"]
    recovery_label: Literal["none"]
    primary_evidence_basis: Literal["contractual_dpd"]
    evidence_reference: StrictStr = Field(min_length=3, max_length=1000)
    review_note: StrictStr = Field(min_length=20, max_length=2000)


class HistoricalCashReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cash_date: date
    amount: StrictStr = Field(pattern=r"^[0-9]{1,16}(\.[0-9]{1,2})?$", max_length=19)


class HistoricalScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario_key: StrictStr = Field(min_length=1, max_length=80)
    probability: StrictStr = Field(pattern=r"^(0|1)(\.[0-9]{1,12})?$", max_length=14)
    evidence_reference: StrictStr = Field(min_length=3, max_length=1000)
    management_rationale: StrictStr = Field(min_length=20, max_length=2000)
    forward_evidence_ids: list[UUID] = Field(min_length=1, max_length=100)
    expected_cash_flows: list[HistoricalCashReceipt] = Field(max_length=3660)


class ElapsedPreparationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_book_id: UUID
    source_digest: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    risk_review: HistoricalRiskReview
    scenarios: list[HistoricalScenario] = Field(min_length=2, max_length=20)
    review_rationale: StrictStr = Field(min_length=20, max_length=2000)


class ElapsedConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_book_id: UUID
    confirmation_digest: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    confirm: StrictBool = False


class SettledPreparationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_book_id: UUID
    source_digest: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    payoff_review_id: UUID
    review_rationale: StrictStr = Field(min_length=20, max_length=2000)
    confirm: StrictBool = False


class RiskPreparationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_book_id: UUID
    source_digest: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    credit_risk_review_id: StrictInt = Field(gt=0, le=9007199254740991)
    scenarios: list[HistoricalScenario] = Field(min_length=2, max_length=20)
    review_rationale: StrictStr = Field(min_length=20, max_length=2000)
    confirm: StrictBool = False


class RenewedPreparationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_book_id: UUID
    source_digest: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    renewal_review_id: UUID
    review_rationale: StrictStr = Field(min_length=20, max_length=2000)
    confirm: StrictBool = False


class ImpairedCashReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_book_id: UUID
    source_digest: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    scenarios: list[HistoricalScenario] = Field(min_length=2, max_length=20)
    review_rationale: StrictStr = Field(min_length=20, max_length=2000)
    confirm: StrictBool = False


def elapsed_period_assessment_repository_dependency() -> (
    PostgresElapsedPeriodAssessmentRepository
):
    return PostgresElapsedPeriodAssessmentRepository()


Assessments = Annotated[
    PostgresElapsedPeriodAssessmentRepository,
    Depends(elapsed_period_assessment_repository_dependency),
]


def create_elapsed_period_assessment_router() -> APIRouter:
    router = APIRouter(tags=["management financial accounting"])
    base = "/api/v1/management/financial-accounting/period-elapsed-assessments"
    mobile = "/api/mobile/v1/management/financial-accounting/period-elapsed-assessments"

    @router.get(base + "/{period_id}/loans/{loan_id}")
    @router.get(mobile + "/{period_id}/loans/{loan_id}", include_in_schema=False)
    def candidate(
        period_id: UUID,
        loan_id: UUID,
        auth: Auth,
        accounts: Accounts,
        assessments: Assessments,
        authorization: Authorization = None,
        x_device_id: Device = None,
    ):
        actor = _actor(authorization, x_device_id, auth, accounts, "accounting.view")
        try:
            result = assessments.load_candidate(
                period_id=period_id, loan_id=loan_id, actor_user_id=actor.user_id
            )
        except CutoffAssessmentError as error:
            raise _exception(error) from error
        return {"success": True, "data": result}

    @router.post(base + "/{period_id}/loans/{loan_id}/prepare")
    @router.post(
        mobile + "/{period_id}/loans/{loan_id}/prepare", include_in_schema=False
    )
    def prepare(
        period_id: UUID,
        loan_id: UUID,
        body: ElapsedPreparationRequest,
        auth: Auth,
        accounts: Accounts,
        assessments: Assessments,
        authorization: Authorization = None,
        x_device_id: Device = None,
    ):
        actor = _actor(
            authorization,
            x_device_id,
            auth,
            accounts,
            "accounting.period.close.prepare",
        )
        try:
            result = assessments.prepare(
                period_id=period_id,
                loan_id=loan_id,
                actor_user_id=actor.user_id,
                expected_book_id=body.expected_book_id,
                source_digest=body.source_digest,
                risk_review=body.risk_review.model_dump(mode="json"),
                scenarios=[
                    scenario.model_dump(mode="json") for scenario in body.scenarios
                ],
                review_rationale=body.review_rationale,
            )
        except CutoffAssessmentError as error:
            raise _exception(error) from error
        return {"success": True, "data": result}

    @router.post(base + "/{period_id}/loans/{loan_id}/prepare-settled")
    @router.post(
        mobile + "/{period_id}/loans/{loan_id}/prepare-settled", include_in_schema=False
    )
    def prepare_settled(
        period_id: UUID,
        loan_id: UUID,
        body: SettledPreparationRequest,
        auth: Auth,
        accounts: Accounts,
        assessments: Assessments,
        authorization: Authorization = None,
        x_device_id: Device = None,
    ):
        actor = _actor(
            authorization,
            x_device_id,
            auth,
            accounts,
            "accounting.period.close.prepare",
        )
        if not body.confirm:
            raise HTTPException(
                409,
                detail={
                    "code": "settled_assessment_confirmation_required",
                    "message": "Confirm zero remaining contractual exposure and the exact retained payoff review.",
                },
            )
        try:
            result = assessments.prepare_settled(
                period_id=period_id,
                loan_id=loan_id,
                actor_user_id=actor.user_id,
                **body.model_dump(exclude={"confirm"}),
            )
        except CutoffAssessmentError as error:
            raise _exception(error) from error
        return {"success": True, "data": result}

    @router.post(base + "/{period_id}/loans/{loan_id}/prepare-renewed")
    @router.post(
        mobile + "/{period_id}/loans/{loan_id}/prepare-renewed", include_in_schema=False
    )
    def prepare_renewed(
        period_id: UUID,
        loan_id: UUID,
        body: RenewedPreparationRequest,
        auth: Auth,
        accounts: Accounts,
        assessments: Assessments,
        authorization: Authorization = None,
        x_device_id: Device = None,
    ):
        actor = _actor(
            authorization,
            x_device_id,
            auth,
            accounts,
            "accounting.period.close.prepare",
        )
        if not body.confirm:
            raise HTTPException(
                409,
                detail={
                    "code": "renewal_settled_assessment_confirmation_required",
                    "message": "Confirm the exact protected renewal and zero old-segment exposure.",
                },
            )
        try:
            result = assessments.prepare_renewed(
                period_id=period_id,
                loan_id=loan_id,
                actor_user_id=actor.user_id,
                **body.model_dump(exclude={"confirm"}),
            )
        except CutoffAssessmentError as error:
            raise _exception(error) from error
        return {"success": True, "data": result}

    @router.post(base + "/{period_id}/loans/{loan_id}/prepare-risk")
    @router.post(
        mobile + "/{period_id}/loans/{loan_id}/prepare-risk", include_in_schema=False
    )
    def prepare_risk(
        period_id: UUID,
        loan_id: UUID,
        body: RiskPreparationRequest,
        auth: Auth,
        accounts: Accounts,
        assessments: Assessments,
        authorization: Authorization = None,
        x_device_id: Device = None,
    ):
        actor = _actor(
            authorization,
            x_device_id,
            auth,
            accounts,
            "accounting.period.close.prepare",
        )
        if not body.confirm:
            raise HTTPException(
                409,
                detail={
                    "code": "risk_assessment_confirmation_required",
                    "message": "Confirm the retained risk review and explicit lifetime forecasts.",
                },
            )
        try:
            result = assessments.prepare_risk(
                period_id=period_id,
                loan_id=loan_id,
                actor_user_id=actor.user_id,
                expected_book_id=body.expected_book_id,
                source_digest=body.source_digest,
                credit_risk_review_id=body.credit_risk_review_id,
                scenarios=[
                    scenario.model_dump(mode="json") for scenario in body.scenarios
                ],
                review_rationale=body.review_rationale,
            )
        except CutoffAssessmentError as error:
            raise _exception(error) from error
        return {"success": True, "data": result}

    @router.get(base + "/{period_id}/loans/{loan_id}/impaired-cash/{application_id}")
    @router.get(
        mobile + "/{period_id}/loans/{loan_id}/impaired-cash/{application_id}",
        include_in_schema=False,
    )
    def impaired_cash_candidate(
        period_id: UUID,
        loan_id: UUID,
        application_id: UUID,
        auth: Auth,
        accounts: Accounts,
        assessments: Assessments,
        authorization: Authorization = None,
        x_device_id: Device = None,
    ):
        actor = _actor(authorization, x_device_id, auth, accounts, "accounting.view")
        try:
            result = assessments.load_impaired_cash(
                period_id=period_id,
                loan_id=loan_id,
                application_id=application_id,
                actor_user_id=actor.user_id,
            )
        except CutoffAssessmentError as error:
            raise _exception(error) from error
        return {"success": True, "data": result}

    @router.post(
        base + "/{period_id}/loans/{loan_id}/impaired-cash/{application_id}/review"
    )
    @router.post(
        mobile + "/{period_id}/loans/{loan_id}/impaired-cash/{application_id}/review",
        include_in_schema=False,
    )
    def review_impaired_cash(
        period_id: UUID,
        loan_id: UUID,
        application_id: UUID,
        body: ImpairedCashReviewRequest,
        auth: Auth,
        accounts: Accounts,
        assessments: Assessments,
        authorization: Authorization = None,
        x_device_id: Device = None,
    ):
        actor = _actor(
            authorization,
            x_device_id,
            auth,
            accounts,
            "accounting.period.close.prepare",
        )
        if not body.confirm:
            raise HTTPException(
                409,
                detail={
                    "code": "impaired_cash_review_confirmation_required",
                    "message": "Confirm the dated expected receipts supporting this impaired cash boundary.",
                },
            )
        try:
            result = assessments.review_impaired_cash(
                period_id=period_id,
                loan_id=loan_id,
                application_id=application_id,
                actor_user_id=actor.user_id,
                expected_book_id=body.expected_book_id,
                source_digest=body.source_digest,
                scenarios=[
                    scenario.model_dump(mode="json") for scenario in body.scenarios
                ],
                review_rationale=body.review_rationale,
            )
        except CutoffAssessmentError as error:
            raise _exception(error) from error
        return {"success": True, "data": result}

    @router.post(base + "/preparations/{preparation_id}/confirm")
    @router.post(
        mobile + "/preparations/{preparation_id}/confirm", include_in_schema=False
    )
    def confirm(
        preparation_id: UUID,
        body: ElapsedConfirmationRequest,
        auth: Auth,
        accounts: Accounts,
        assessments: Assessments,
        authorization: Authorization = None,
        x_device_id: Device = None,
    ):
        actor = _actor(
            authorization, x_device_id, auth, accounts, "accounting.period.close.post"
        )
        if not body.confirm:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "historical_assessment_confirmation_required",
                    "message": "Confirm the exact retained calculation digest.",
                },
            )
        try:
            posted = assessments.confirm(
                preparation_id=preparation_id,
                actor_user_id=actor.user_id,
                **body.model_dump(exclude={"confirm"}),
            )
        except CutoffAssessmentError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"posting_id": str(posted)}}

    return router
