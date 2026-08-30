from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .ecl_a5_accounting_repository import (
    EclA5AccountingBlocked,
    EclA5AccountingError,
    EclA5Action,
    PostgresEclA5AccountingRepository,
)
from .request_auth import authenticated_device_context


REMEASUREMENT_PERMISSION = "accounting.ecl.remeasurement.post"
WRITEOFF_PERMISSION = "accounting.ecl.writeoff.post"
RECOVERY_REVIEW_PERMISSION = "accounting.ecl.recovery.review"
RECOVERY_POST_PERMISSION = "accounting.ecl.recovery.post"


class StrictA5Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RemeasureEclAllowanceRequest(StrictA5Request):
    review_token: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_calculation_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_prior_allowance: Decimal = Field(ge=0)
    expected_target_allowance: Decimal = Field(ge=0)
    expected_posting_date: date
    expected_fiscal_period_id: UUID
    expected_credit_loss_expense_account_id: UUID
    expected_allowance_account_id: UUID

    @field_validator("expected_prior_allowance", "expected_target_allowance")
    @classmethod
    def exact_currency_cents(cls, value: Decimal) -> Decimal:
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("A5 allowance amounts must use exact currency-cent precision.")
        return value


class PostFullWriteoffRequest(StrictA5Request):
    review_token: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_credit_risk_review_id: int = Field(ge=1)
    expected_measurement_id: UUID
    expected_calculation_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_loan_component: Decimal = Field(ge=0)
    expected_accrued_interest_component: Decimal = Field(ge=0)
    expected_gross_carrying_amount: Decimal = Field(gt=0)
    expected_allowance_balance: Decimal = Field(gt=0)
    expected_loan_receivable_account_id: UUID
    expected_accrued_interest_account_id: UUID
    expected_allowance_account_id: UUID
    expected_posting_date: date
    expected_fiscal_period_id: UUID

    @field_validator(
        "expected_loan_component",
        "expected_accrued_interest_component",
        "expected_gross_carrying_amount",
        "expected_allowance_balance",
    )
    @classmethod
    def exact_currency_cents(cls, value: Decimal) -> Decimal:
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("A5 write-off amounts must use exact currency-cent precision.")
        return value

    @model_validator(mode="after")
    def exact_full_cover(self) -> "PostFullWriteoffRequest":
        if self.expected_gross_carrying_amount != (
            self.expected_loan_component + self.expected_accrued_interest_component
        ):
            raise ValueError("Gross carrying amount must equal the exact loan plus accrued-interest components.")
        if self.expected_allowance_balance != self.expected_gross_carrying_amount:
            raise ValueError("V1 full write-off requires exact allowance equal to gross carrying amount.")
        return self


class ReviewPostWriteoffRecoveryRequest(StrictA5Request):
    review_token: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_recovery_transaction_id: UUID
    expected_recovery_amount: Decimal = Field(gt=0)
    evidence_reference: str = Field(min_length=1, max_length=500)
    review_note: str = Field(min_length=20, max_length=4000)

    @field_validator("expected_recovery_amount")
    @classmethod
    def exact_currency_cents(cls, value: Decimal) -> Decimal:
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("A5 recovery amount must use exact currency-cent precision.")
        return value


class PostPostWriteoffRecoveryRequest(StrictA5Request):
    review_token: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_recovery_transaction_id: UUID
    expected_recovery_amount: Decimal = Field(gt=0)
    expected_posting_date: date
    expected_fiscal_period_id: UUID
    expected_cash_account_id: UUID
    expected_credit_loss_expense_account_id: UUID

    @field_validator("expected_recovery_amount")
    @classmethod
    def exact_currency_cents(cls, value: Decimal) -> Decimal:
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("A5 recovery amount must use exact currency-cent precision.")
        return value


def ecl_a5_accounting_repository_dependency() -> PostgresEclA5AccountingRepository:
    return PostgresEclA5AccountingRepository()


def _money(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


def _action_payload(item: EclA5Action) -> dict[str, object]:
    return {
        "loan_id": str(item.loan_id),
        "loan_number": item.loan_number,
        "loan_status": item.loan_status,
        "calculation_mode": item.calculation_mode,
        "credit_risk_review_id": item.credit_risk_review_id,
        "stage_label": item.stage_label,
        "default_label": item.default_label,
        "write_off_label": item.write_off_label,
        "recovery_label": item.recovery_label,
        "measurement_id": str(item.measurement_id) if item.measurement_id else None,
        "measurement_version": item.measurement_version,
        "measurement_date": item.measurement_date.isoformat() if item.measurement_date else None,
        "calculation_digest": item.calculation_digest,
        "measurement_status": item.measurement_status,
        "authoritative_ecl_amount": _money(item.authoritative_ecl_amount),
        "current_allowance_balance": _money(item.current_allowance_balance),
        "loan_receivable_account_id": (
            str(item.loan_receivable_account_id) if item.loan_receivable_account_id else None
        ),
        "loan_receivable_system_key": item.loan_receivable_system_key,
        "accrued_interest_account_id": (
            str(item.accrued_interest_account_id) if item.accrued_interest_account_id else None
        ),
        "loan_component": _money(item.loan_component),
        "accrued_interest_component": _money(item.accrued_interest_component),
        "gross_carrying_amount": _money(item.gross_carrying_amount),
        "writeoff_id": str(item.writeoff_id) if item.writeoff_id else None,
        "recovery_transaction_id": (
            str(item.recovery_transaction_id) if item.recovery_transaction_id else None
        ),
        "recovery_amount": _money(item.recovery_amount),
        "recovery_candidate_transaction_id": (
            str(item.recovery_candidate_transaction_id)
            if item.recovery_candidate_transaction_id
            else None
        ),
        "recovery_candidate_amount": _money(item.recovery_candidate_amount),
        "recovery_candidate_collection_date": (
            item.recovery_candidate_collection_date.isoformat()
            if item.recovery_candidate_collection_date
            else None
        ),
        "posting_date": item.posting_date.isoformat() if item.posting_date else None,
        "fiscal_period_id": str(item.fiscal_period_id) if item.fiscal_period_id else None,
        "credit_loss_expense_account_id": (
            str(item.credit_loss_expense_account_id)
            if item.credit_loss_expense_account_id
            else None
        ),
        "allowance_account_id": (
            str(item.allowance_account_id) if item.allowance_account_id else None
        ),
        "cash_account_id": str(item.cash_account_id) if item.cash_account_id else None,
        "a5_status": item.a5_status,
        "protected_a5_accounting_enabled": item.protected_a5_accounting_enabled,
        "automatic_source_posting": item.automatic_source_posting,
    }


def _exception(error: EclA5AccountingError) -> HTTPException:
    return HTTPException(
        status_code=409 if isinstance(error, EclA5AccountingBlocked) else 500,
        detail={"code": error.code, "message": str(error)},
    )


def _require_management(actor) -> None:
    if "management" not in actor.roles:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "management_role_required",
                "message": "Management access is required for protected A5 ECL accounting.",
            },
        )


def _require_permission(actor, permission: str) -> None:
    _require_management(actor)
    if permission not in actor.permissions:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "ecl_a5_permission_required",
                "message": f"Protected A5 permission {permission} is required.",
            },
        )


def create_ecl_a5_accounting_router() -> APIRouter:
    router = APIRouter(tags=["management financial accounting"])

    @router.get("/api/v1/management/financial-accounting/ecl-a5")
    @router.get(
        "/api/mobile/v1/management/financial-accounting/ecl-a5",
        include_in_schema=False,
    )
    def list_a5_actions(
        status: Literal[
            "all",
            "remeasurement_required",
            "allowance_current",
            "writeoff_ready",
            "written_off",
            "recovery_review_required",
            "post_writeoff_recovery_ready",
            "blocked",
        ] = Query(default="all"),
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        accounting: PostgresEclA5AccountingRepository = Depends(
            ecl_a5_accounting_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_management(actor)
        return {
            "success": True,
            "data": {
                "items": [
                    _action_payload(item)
                    for item in accounting.list_actions(status=status, limit=limit, offset=offset)
                ],
                "summary": accounting.summary(),
                "filter": status,
                "limit": limit,
                "offset": offset,
                "permissions": {
                    "remeasurement_post": REMEASUREMENT_PERMISSION in actor.permissions,
                    "writeoff_post": WRITEOFF_PERMISSION in actor.permissions,
                    "recovery_review": RECOVERY_REVIEW_PERMISSION in actor.permissions,
                    "recovery_post": RECOVERY_POST_PERMISSION in actor.permissions,
                },
                "notice": (
                    "A5 actions require explicit Management confirmation from exact protected evidence. "
                    "Write-off support alone never derecognizes a loan; post-write-off recovery never recreates a receivable or allowance; automatic source posting remains disabled."
                ),
            },
        }

    @router.post(
        "/api/v1/management/financial-accounting/ecl-a5/measurements/{measurement_id}/remeasure"
    )
    @router.post(
        "/api/mobile/v1/management/financial-accounting/ecl-a5/measurements/{measurement_id}/remeasure",
        include_in_schema=False,
    )
    def post_remeasurement(
        measurement_id: UUID,
        request: RemeasureEclAllowanceRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        accounting: PostgresEclA5AccountingRepository = Depends(
            ecl_a5_accounting_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_permission(actor, REMEASUREMENT_PERMISSION)
        try:
            posting_id = accounting.post_remeasurement(
                measurement_id=measurement_id,
                actor_user_id=actor.user_id,
                review_token=request.review_token.lower(),
                expected_calculation_digest=request.expected_calculation_digest.lower(),
                expected_prior_allowance=request.expected_prior_allowance,
                expected_target_allowance=request.expected_target_allowance,
                expected_posting_date=request.expected_posting_date,
                expected_fiscal_period_id=request.expected_fiscal_period_id,
                expected_credit_loss_expense_account_id=request.expected_credit_loss_expense_account_id,
                expected_allowance_account_id=request.expected_allowance_account_id,
            )
        except EclA5AccountingError as error:
            raise _exception(error) from error
        return {
            "success": True,
            "data": {
                "remeasurement_id": str(posting_id),
                "automatic_source_posting": False,
            },
        }

    @router.post("/api/v1/management/financial-accounting/ecl-a5/loans/{loan_id}/writeoff")
    @router.post(
        "/api/mobile/v1/management/financial-accounting/ecl-a5/loans/{loan_id}/writeoff",
        include_in_schema=False,
    )
    def post_full_writeoff(
        loan_id: UUID,
        request: PostFullWriteoffRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        accounting: PostgresEclA5AccountingRepository = Depends(
            ecl_a5_accounting_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_permission(actor, WRITEOFF_PERMISSION)
        try:
            writeoff_id = accounting.post_full_writeoff(
                loan_id=loan_id,
                actor_user_id=actor.user_id,
                review_token=request.review_token.lower(),
                expected_credit_risk_review_id=request.expected_credit_risk_review_id,
                expected_measurement_id=request.expected_measurement_id,
                expected_calculation_digest=request.expected_calculation_digest.lower(),
                expected_loan_component=request.expected_loan_component,
                expected_accrued_interest_component=request.expected_accrued_interest_component,
                expected_gross_carrying_amount=request.expected_gross_carrying_amount,
                expected_allowance_balance=request.expected_allowance_balance,
                expected_loan_receivable_account_id=request.expected_loan_receivable_account_id,
                expected_accrued_interest_account_id=request.expected_accrued_interest_account_id,
                expected_allowance_account_id=request.expected_allowance_account_id,
                expected_posting_date=request.expected_posting_date,
                expected_fiscal_period_id=request.expected_fiscal_period_id,
            )
        except EclA5AccountingError as error:
            raise _exception(error) from error
        return {
            "success": True,
            "data": {
                "writeoff_id": str(writeoff_id),
                "automatic_source_posting": False,
            },
        }

    @router.post(
        "/api/v1/management/financial-accounting/ecl-a5/loans/{loan_id}/recovery-review"
    )
    @router.post(
        "/api/mobile/v1/management/financial-accounting/ecl-a5/loans/{loan_id}/recovery-review",
        include_in_schema=False,
    )
    def review_post_writeoff_recovery(
        loan_id: UUID,
        request: ReviewPostWriteoffRecoveryRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        accounting: PostgresEclA5AccountingRepository = Depends(
            ecl_a5_accounting_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_permission(actor, RECOVERY_REVIEW_PERMISSION)
        try:
            review_id = accounting.review_post_writeoff_recovery(
                loan_id=loan_id,
                actor_user_id=actor.user_id,
                review_token=request.review_token.lower(),
                expected_recovery_transaction_id=request.expected_recovery_transaction_id,
                expected_recovery_amount=request.expected_recovery_amount,
                evidence_reference=request.evidence_reference,
                review_note=request.review_note,
            )
        except EclA5AccountingError as error:
            raise _exception(error) from error
        return {
            "success": True,
            "data": {
                "credit_risk_review_id": review_id,
                "recovery_transaction_id": str(request.expected_recovery_transaction_id),
                "automatic_source_posting": False,
            },
        }

    @router.post(
        "/api/v1/management/financial-accounting/ecl-a5/reviews/{credit_risk_review_id}/recovery"
    )
    @router.post(
        "/api/mobile/v1/management/financial-accounting/ecl-a5/reviews/{credit_risk_review_id}/recovery",
        include_in_schema=False,
    )
    def post_post_writeoff_recovery(
        credit_risk_review_id: int,
        request: PostPostWriteoffRecoveryRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        accounting: PostgresEclA5AccountingRepository = Depends(
            ecl_a5_accounting_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_permission(actor, RECOVERY_POST_PERMISSION)
        try:
            recovery_id = accounting.post_recovery(
                credit_risk_review_id=credit_risk_review_id,
                actor_user_id=actor.user_id,
                review_token=request.review_token.lower(),
                expected_recovery_transaction_id=request.expected_recovery_transaction_id,
                expected_recovery_amount=request.expected_recovery_amount,
                expected_posting_date=request.expected_posting_date,
                expected_fiscal_period_id=request.expected_fiscal_period_id,
                expected_cash_account_id=request.expected_cash_account_id,
                expected_credit_loss_expense_account_id=request.expected_credit_loss_expense_account_id,
            )
        except EclA5AccountingError as error:
            raise _exception(error) from error
        return {
            "success": True,
            "data": {
                "recovery_id": str(recovery_id),
                "automatic_source_posting": False,
            },
        }

    return router
