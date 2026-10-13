"""Explicit Management review and confirmation of actual dated assessment proof."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictStr,
    field_validator,
)

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .request_auth import authenticated_device_context
from .retained_cutoff_assessment_repository import (
    CutoffAssessmentConflict,
    CutoffAssessmentDenied,
    CutoffAssessmentError,
    PostgresRetainedCutoffAssessmentRepository,
)


class AssessmentIdentityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_book_id: UUID
    source_digest: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")


class AssessmentPreparationRequest(AssessmentIdentityRequest):
    review_rationale: StrictStr = Field(min_length=20, max_length=2000)

    @field_validator("review_rationale")
    @classmethod
    def substantive_rationale(cls, value: str) -> str:
        if len(value.strip()) < 20 or value != value.strip():
            raise ValueError("An exact substantive review rationale is required.")
        return value


class AssessmentConfirmationRequest(AssessmentIdentityRequest):
    confirm: StrictBool = False


def retained_cutoff_assessment_repository_dependency() -> (
    PostgresRetainedCutoffAssessmentRepository
):
    return PostgresRetainedCutoffAssessmentRepository()


Auth = Annotated[SupabaseAuthClient, Depends(auth_client_dependency)]
Accounts = Annotated[PostgresAccountRepository, Depends(account_repository_dependency)]
Assessments = Annotated[
    PostgresRetainedCutoffAssessmentRepository,
    Depends(retained_cutoff_assessment_repository_dependency),
]
Authorization = Annotated[str | None, Header(alias="Authorization")]
Device = Annotated[str | None, Header(alias="X-Device-Id")]


def _actor(authorization, device, auth, accounts, permission):
    actor = authenticated_device_context(
        authorization=authorization,
        device_identifier=device,
        auth=auth,
        accounts=accounts,
        permission=permission,
        permission_error="Current accounting permission is required.",
    )
    if actor.status != "active" or "management" not in actor.roles:
        raise HTTPException(
            status_code=403,
            detail="Active Management access is required for dated assessment evidence.",
        )
    return actor


def _exception(error: CutoffAssessmentError) -> HTTPException:
    status = (
        403
        if isinstance(error, CutoffAssessmentDenied)
        else 409
        if isinstance(error, CutoffAssessmentConflict)
        else 503
    )
    return HTTPException(
        status_code=status, detail={"code": error.code, "message": str(error)}
    )


def create_retained_cutoff_assessment_router() -> APIRouter:
    router = APIRouter(tags=["management financial accounting"])
    base = "/api/v1/management/financial-accounting/period-assessments"
    mobile = "/api/mobile/v1/management/financial-accounting/period-assessments"

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
        body: AssessmentPreparationRequest,
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
                **body.model_dump(),
            )
        except CutoffAssessmentError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"preparation_id": str(result)}}

    @router.post(base + "/preparations/{preparation_id}/confirm")
    @router.post(
        mobile + "/preparations/{preparation_id}/confirm", include_in_schema=False
    )
    def confirm(
        preparation_id: UUID,
        body: AssessmentConfirmationRequest,
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
                    "code": "cutoff_assessment_confirmation_required",
                    "message": "Explicit confirmation of the exact prepared source digest is required.",
                },
            )
        try:
            result = assessments.confirm(
                preparation_id=preparation_id,
                actor_user_id=actor.user_id,
                **body.model_dump(exclude={"confirm"}),
            )
        except CutoffAssessmentError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"confirmation_id": str(result)}}

    return router
