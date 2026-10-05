"""Management evidence registration over already posted liability control lines."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictStr,
    field_validator,
    model_validator,
)

from .account_repository import AccountContext, PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .liability_control_repository import (
    LiabilityControlConflict,
    LiabilityControlDenied,
    LiabilityControlError,
    PostgresLiabilityControlRepository,
)
from .request_auth import authenticated_device_context

ControlCode = Literal["2000", "2300", "2310", "2320", "2330", "2340"]


class LiabilitySourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    expected_book_id: UUID
    journal_line_id: UUID
    expected_account_code: ControlCode
    expected_amount: StrictStr = Field(pattern=r"^(0|[1-9][0-9]{0,15})\.[0-9]{2}$")
    expected_posting_date: date
    expected_source_type: Literal["manual", "opening_balance", "reversal"]
    expected_source_reference: StrictStr | None
    evidence_reference: StrictStr = Field(min_length=1, max_length=1000)
    evidence_digest: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    reviewed: StrictBool = False

    @field_validator("expected_amount")
    @classmethod
    def positive_amount(cls, value: str) -> str:
        if Decimal(value) <= 0:
            raise ValueError("A liability line must have a positive exact-cent amount.")
        return value

    @field_validator("evidence_reference")
    @classmethod
    def exact_evidence(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError(
                "Retained evidence reference must have exact nonblank text."
            )
        return value


class RegisterLiabilityRequest(LiabilitySourceRequest):
    kind: Literal[
        "trade_payable",
        "borrowing_external",
        "borrowing_owner",
        "interest",
        "wages",
        "contrib",
    ]
    counterparty: StrictStr = Field(min_length=1, max_length=200)
    due_date: date | None

    @field_validator("counterparty")
    @classmethod
    def exact_counterparty(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("Retained counterparty must have exact nonblank text.")
        return value


class LiabilityMovementRequest(LiabilitySourceRequest):
    kind: Literal["settlement", "reversal"]
    reverses_claim_id: UUID | None = None

    @model_validator(mode="after")
    def exact_reversal_reference(self) -> Self:
        if (self.kind == "reversal") != (self.reverses_claim_id is not None):
            raise ValueError(
                "Only a reversal must name the exact original liability claim."
            )
        return self


def liability_control_repository_dependency() -> PostgresLiabilityControlRepository:
    return PostgresLiabilityControlRepository()


AuthDependency = Annotated[SupabaseAuthClient, Depends(auth_client_dependency)]
AccountsDependency = Annotated[
    PostgresAccountRepository, Depends(account_repository_dependency)
]
LiabilitiesDependency = Annotated[
    PostgresLiabilityControlRepository, Depends(liability_control_repository_dependency)
]
AuthorizationHeader = Annotated[str | None, Header(alias="Authorization")]
DeviceHeader = Annotated[str | None, Header(alias="X-Device-Id")]


def _actor(
    authorization: str | None,
    device_id: str | None,
    auth: SupabaseAuthClient,
    accounts: PostgresAccountRepository,
    permission: str,
) -> AccountContext:
    actor = authenticated_device_context(
        authorization=authorization,
        device_identifier=device_id,
        auth=auth,
        accounts=accounts,
        permission=permission,
        permission_error="Current accounting permission is required.",
    )
    if actor.status != "active" or "management" not in actor.roles:
        raise HTTPException(
            status_code=403,
            detail="Active Management access is required for liability control evidence.",
        )
    return actor


def _exception(error: LiabilityControlError) -> HTTPException:
    status = (
        403
        if isinstance(error, LiabilityControlDenied)
        else 409
        if isinstance(error, LiabilityControlConflict)
        else 503
    )
    return HTTPException(
        status_code=status, detail={"code": error.code, "message": str(error)}
    )


def _reviewed_payload(body: LiabilitySourceRequest) -> dict[str, object]:
    if not body.reviewed:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "liability_review_required",
                "message": "Explicit review of this exact posted source line and retained evidence is required.",
            },
        )
    return body.model_dump(mode="json", exclude={"request_id", "expected_book_id"})


def create_liability_control_router() -> APIRouter:
    router = APIRouter(tags=["management financial accounting"])

    @router.get("/api/v1/management/financial-accounting/liabilities")
    @router.get(
        "/api/mobile/v1/management/financial-accounting/liabilities",
        include_in_schema=False,
    )
    def get_liability_schedule(
        auth: AuthDependency,
        accounts: AccountsDependency,
        liabilities: LiabilitiesDependency,
        as_of: Annotated[date | None, Query()] = None,
        authorization: AuthorizationHeader = None,
        x_device_id: DeviceHeader = None,
    ) -> dict[str, object]:
        actor = _actor(authorization, x_device_id, auth, accounts, "accounting.view")
        try:
            schedule = liabilities.load_schedule(
                actor_user_id=actor.user_id, as_of=as_of
            )
        except LiabilityControlError as error:
            raise _exception(error) from error
        return {"success": True, "data": schedule}

    @router.post("/api/v1/management/financial-accounting/liabilities")
    @router.post(
        "/api/mobile/v1/management/financial-accounting/liabilities",
        include_in_schema=False,
    )
    def register_liability(
        body: RegisterLiabilityRequest,
        auth: AuthDependency,
        accounts: AccountsDependency,
        liabilities: LiabilitiesDependency,
        authorization: AuthorizationHeader = None,
        x_device_id: DeviceHeader = None,
    ) -> dict[str, object]:
        actor = _actor(
            authorization, x_device_id, auth, accounts, "accounting.journal.manage"
        )
        payload = _reviewed_payload(body)
        try:
            obligation_id = liabilities.register_obligation(
                request_id=body.request_id,
                expected_book_id=body.expected_book_id,
                payload=payload,
                actor_user_id=actor.user_id,
            )
        except LiabilityControlError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"obligation_id": str(obligation_id)}}

    @router.post(
        "/api/v1/management/financial-accounting/liabilities/{obligation_id}/movements"
    )
    @router.post(
        "/api/mobile/v1/management/financial-accounting/liabilities/{obligation_id}/movements",
        include_in_schema=False,
    )
    def record_liability_movement(
        obligation_id: UUID,
        body: LiabilityMovementRequest,
        auth: AuthDependency,
        accounts: AccountsDependency,
        liabilities: LiabilitiesDependency,
        authorization: AuthorizationHeader = None,
        x_device_id: DeviceHeader = None,
    ) -> dict[str, object]:
        actor = _actor(
            authorization, x_device_id, auth, accounts, "accounting.journal.manage"
        )
        payload = _reviewed_payload(body) | {"obligation_id": str(obligation_id)}
        try:
            claim_id = liabilities.record_movement(
                request_id=body.request_id,
                expected_book_id=body.expected_book_id,
                payload=payload,
                actor_user_id=actor.user_id,
            )
        except LiabilityControlError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"claim_id": str(claim_id)}}

    return router
