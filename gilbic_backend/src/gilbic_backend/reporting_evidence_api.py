"""Explicit retention of reviewed reporting basis, notes and cash classifications."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .reporting_evidence_repository import (
    PostgresReportingEvidenceRepository,
    ReportingEvidenceError,
)
from .request_auth import authenticated_device_context


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_reference: StrictStr = Field(min_length=1, max_length=1000)
    evidence_digest: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")


class ReportingNote(Evidence):
    title: StrictStr = Field(min_length=1, max_length=200)
    text: StrictStr = Field(min_length=1, max_length=20000)


class ReportingPolicyRequest(Evidence):
    request_id: UUID
    book_id: UUID
    period_id: UUID
    expected_version: StrictInt = Field(ge=0)
    cash_account_codes: list[Literal["1010", "1020", "1030"]] = Field(
        min_length=1, max_length=3
    )
    framework_label: StrictStr = Field(min_length=1, max_length=200)
    notes: list[ReportingNote] = Field(min_length=1, max_length=50)
    reviewed: StrictBool = False


class CashAllocation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Literal["operating", "investing", "financing", "internal"]
    amount: StrictStr = Field(pattern=r"^-?(0|[1-9][0-9]{0,15})\.[0-9]{2}$")


class CashClassificationRequest(Evidence):
    request_id: UUID
    book_id: UUID
    policy_id: UUID
    journal_line_id: UUID
    expected_version: StrictInt = Field(ge=0)
    expected_amount: StrictStr = Field(pattern=r"^-?(0|[1-9][0-9]{0,15})\.[0-9]{2}$")
    allocations: list[CashAllocation] = Field(min_length=1, max_length=20)
    reviewed: StrictBool = False


def reporting_evidence_repository_dependency():
    return PostgresReportingEvidenceRepository()


Auth = Annotated[SupabaseAuthClient, Depends(auth_client_dependency)]
Accounts = Annotated[PostgresAccountRepository, Depends(account_repository_dependency)]
Reports = Annotated[
    PostgresReportingEvidenceRepository,
    Depends(reporting_evidence_repository_dependency),
]
Authorization = Annotated[str | None, Header(alias="Authorization")]
Device = Annotated[str | None, Header(alias="X-Device-Id")]


def actor(auth, accounts, authorization, device, permission):
    context = authenticated_device_context(
        authorization=authorization,
        device_identifier=device,
        auth=auth,
        accounts=accounts,
        permission=permission,
        permission_error="Current accounting access is required.",
    )
    if context.status != "active" or "management" not in context.roles:
        raise HTTPException(
            status_code=403, detail="Active Management access is required."
        )
    return context


def reviewed(body):
    if not body.reviewed:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "reporting_review_required",
                "message": "Review the exact reporting evidence before retaining it.",
            },
        )


def create_reporting_evidence_router():
    router = APIRouter(tags=["management financial statements"])

    @router.get("/api/v1/management/financial-accounting/statements/reporting-policy")
    @router.get(
        "/api/mobile/v1/management/financial-accounting/statements/reporting-policy",
        include_in_schema=False,
    )
    def get_policy(
        auth: Auth,
        accounts: Accounts,
        reports: Reports,
        period_id: Annotated[UUID, Query()],
        authorization: Authorization = None,
        x_device_id: Device = None,
    ):
        context = actor(auth, accounts, authorization, x_device_id, "accounting.view")
        try:
            policy = reports.load_policy(
                period_id=period_id, actor_user_id=context.user_id
            )
        except ReportingEvidenceError as error:
            raise HTTPException(status_code=error.status, detail=str(error)) from error
        return {"success": True, "data": {"policy": policy}}

    @router.post("/api/v1/management/financial-accounting/statements/reporting-policy")
    @router.post(
        "/api/mobile/v1/management/financial-accounting/statements/reporting-policy",
        include_in_schema=False,
    )
    def retain_policy(
        body: ReportingPolicyRequest,
        auth: Auth,
        accounts: Accounts,
        reports: Reports,
        authorization: Authorization = None,
        x_device_id: Device = None,
    ):
        context = actor(
            auth, accounts, authorization, x_device_id, "accounting.journal.manage"
        )
        reviewed(body)
        try:
            identity = reports.retain_policy(
                request_id=body.request_id,
                book_id=body.book_id,
                period_id=body.period_id,
                expected_version=body.expected_version,
                payload=body.model_dump(
                    mode="json",
                    exclude={"request_id", "book_id", "period_id", "expected_version"},
                ),
                actor_user_id=context.user_id,
            )
        except ReportingEvidenceError as error:
            raise HTTPException(status_code=error.status, detail=str(error)) from error
        return {"success": True, "data": {"policy_id": str(identity)}}

    @router.post(
        "/api/v1/management/financial-accounting/statements/cash-flow-classifications"
    )
    @router.post(
        "/api/mobile/v1/management/financial-accounting/statements/cash-flow-classifications",
        include_in_schema=False,
    )
    def retain_classification(
        body: CashClassificationRequest,
        auth: Auth,
        accounts: Accounts,
        reports: Reports,
        authorization: Authorization = None,
        x_device_id: Device = None,
    ):
        context = actor(
            auth, accounts, authorization, x_device_id, "accounting.journal.manage"
        )
        reviewed(body)
        try:
            identity = reports.retain_classification(
                request_id=body.request_id,
                book_id=body.book_id,
                policy_id=body.policy_id,
                payload=body.model_dump(
                    mode="json", exclude={"request_id", "book_id", "policy_id"}
                ),
                actor_user_id=context.user_id,
            )
        except ReportingEvidenceError as error:
            raise HTTPException(status_code=error.status, detail=str(error)) from error
        return {"success": True, "data": {"classification_id": str(identity)}}

    return router
