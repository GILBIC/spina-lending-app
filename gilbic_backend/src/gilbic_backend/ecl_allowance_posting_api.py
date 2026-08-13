from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .ecl_allowance_posting_repository import (
    EclAllowancePosting,
    EclAllowancePostingBlocked,
    EclAllowancePostingError,
    EclAllowancePostingNotFound,
    EclAllowancePostingQueueItem,
    EclAllowancePreparation,
    PostgresEclAllowancePostingRepository,
)
from .request_auth import authenticated_device_context


PREPARE_PERMISSION = "accounting.ecl.allowance.prepare"
POST_PERMISSION = "accounting.ecl.allowance.post"


class StrictAllowanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PrepareEclAllowanceRequest(StrictAllowanceRequest):
    preparation_review_token: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_calculation_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_ecl_amount: Decimal = Field(gt=0)
    expected_posting_date: date
    expected_fiscal_period_id: UUID
    expected_credit_loss_expense_account_id: UUID
    expected_allowance_account_id: UUID
    expected_prior_allowance_balance: Decimal = Decimal("0.00")

    @field_validator("expected_ecl_amount", "expected_prior_allowance_balance")
    @classmethod
    def exact_currency_cents(cls, value: Decimal) -> Decimal:
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("ECL allowance amounts must use exact currency-cent precision.")
        return value

    @field_validator("expected_prior_allowance_balance")
    @classmethod
    def initial_balance_only(cls, value: Decimal) -> Decimal:
        if value != Decimal("0.00"):
            raise ValueError("A4 only permits the initial allowance from prior balance 0.00; use A5 for remeasurement.")
        return value


class PostEclAllowanceRequest(StrictAllowanceRequest):
    posting_review_token: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_measurement_id: UUID
    expected_calculation_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_journal_entry_id: UUID
    expected_source_event_key: str = Field(min_length=1, max_length=200)
    expected_preparation_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_posting_date: date
    expected_fiscal_period_id: UUID
    expected_credit_loss_expense_account_id: UUID
    expected_allowance_account_id: UUID
    expected_allowance_amount: Decimal = Field(gt=0)
    expected_prior_allowance_balance: Decimal = Decimal("0.00")

    @field_validator("expected_allowance_amount", "expected_prior_allowance_balance")
    @classmethod
    def exact_currency_cents(cls, value: Decimal) -> Decimal:
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("ECL allowance amounts must use exact currency-cent precision.")
        return value

    @field_validator("expected_prior_allowance_balance")
    @classmethod
    def initial_balance_only(cls, value: Decimal) -> Decimal:
        if value != Decimal("0.00"):
            raise ValueError("A4 only permits the initial allowance from prior balance 0.00; use A5 for remeasurement.")
        return value


def ecl_allowance_posting_repository_dependency() -> PostgresEclAllowancePostingRepository:
    return PostgresEclAllowancePostingRepository()


def _money(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


def _queue_payload(item: EclAllowancePostingQueueItem) -> dict[str, object]:
    return {
        "loan_id": str(item.loan_id),
        "loan_number": item.loan_number,
        "loan_status": item.loan_status,
        "loan_type_code": item.loan_type_code,
        "loan_type_name": item.loan_type_name,
        "calculation_mode": item.calculation_mode,
        "measurement_id": str(item.measurement_id) if item.measurement_id else None,
        "measurement_version": item.measurement_version,
        "measurement_date": item.measurement_date.isoformat() if item.measurement_date else None,
        "loss_horizon": item.loss_horizon,
        "calculation_digest": item.calculation_digest,
        "measurement_status": item.measurement_status,
        "authoritative_ecl_amount": _money(item.authoritative_ecl_amount),
        "preparation_id": str(item.preparation_id) if item.preparation_id else None,
        "journal_entry_id": str(item.journal_entry_id) if item.journal_entry_id else None,
        "source_event_key": item.source_event_key,
        "posting_date": item.posting_date.isoformat() if item.posting_date else None,
        "fiscal_period_id": str(item.fiscal_period_id) if item.fiscal_period_id else None,
        "credit_loss_expense_account_id": (
            str(item.credit_loss_expense_account_id)
            if item.credit_loss_expense_account_id else None
        ),
        "allowance_account_id": str(item.allowance_account_id) if item.allowance_account_id else None,
        "allowance_amount": _money(item.allowance_amount),
        "prior_allowance_balance": _money(item.prior_allowance_balance),
        "preparation_review_token": item.preparation_review_token,
        "preparation_digest": item.preparation_digest,
        "draft_policy_version": item.draft_policy_version,
        "journal_status": item.journal_status,
        "entry_number": item.entry_number,
        "posting_id": str(item.posting_id) if item.posting_id else None,
        "posting_review_token": item.posting_review_token,
        "posting_policy_version": item.posting_policy_version,
        "current_allowance_balance": _money(item.current_allowance_balance),
        "allowance_posting_status": item.allowance_posting_status,
        "protected_allowance_action_ready": item.protected_allowance_action_ready,
        "account_1190_posting_enabled": item.account_1190_posting_enabled,
        "automatic_source_posting": item.automatic_source_posting,
    }


def _preparation_payload(item: EclAllowancePreparation) -> dict[str, object]:
    return {
        "id": str(item.id),
        "measurement_id": str(item.measurement_id),
        "loan_id": str(item.loan_id),
        "client_id": str(item.client_id),
        "measurement_version": item.measurement_version,
        "measurement_date": item.measurement_date.isoformat(),
        "calculation_digest": item.calculation_digest,
        "journal_entry_id": str(item.journal_entry_id),
        "source_event_key": item.source_event_key,
        "posting_date": item.posting_date.isoformat(),
        "fiscal_period_id": str(item.fiscal_period_id),
        "credit_loss_expense_account_id": str(item.credit_loss_expense_account_id),
        "allowance_account_id": str(item.allowance_account_id),
        "allowance_amount": _money(item.allowance_amount),
        "prior_allowance_balance": _money(item.prior_allowance_balance),
        "preparation_review_token": item.preparation_review_token,
        "preparation_digest": item.preparation_digest,
        "draft_policy_version": item.draft_policy_version,
        "prepared_by_user_id": str(item.prepared_by_user_id),
        "prepared_at": item.prepared_at.isoformat(),
        "account_1190_posting_enabled": True,
        "automatic_source_posting": False,
    }


def _posting_payload(item: EclAllowancePosting) -> dict[str, object]:
    return {
        "id": str(item.id),
        "preparation_id": str(item.preparation_id),
        "measurement_id": str(item.measurement_id),
        "loan_id": str(item.loan_id),
        "client_id": str(item.client_id),
        "measurement_version": item.measurement_version,
        "calculation_digest": item.calculation_digest,
        "journal_entry_id": str(item.journal_entry_id),
        "source_event_key": item.source_event_key,
        "posting_date": item.posting_date.isoformat(),
        "fiscal_period_id": str(item.fiscal_period_id),
        "credit_loss_expense_account_id": str(item.credit_loss_expense_account_id),
        "allowance_account_id": str(item.allowance_account_id),
        "allowance_amount": _money(item.allowance_amount),
        "prior_allowance_balance": _money(item.prior_allowance_balance),
        "resulting_allowance_balance": _money(item.resulting_allowance_balance),
        "preparation_review_token": item.preparation_review_token,
        "preparation_digest": item.preparation_digest,
        "posting_review_token": item.posting_review_token,
        "draft_policy_version": item.draft_policy_version,
        "posting_policy_version": item.posting_policy_version,
        "entry_number": item.entry_number,
        "posted_by_user_id": str(item.posted_by_user_id),
        "posted_at": item.posted_at.isoformat(),
        "account_1190_posting_enabled": True,
        "automatic_source_posting": False,
    }


def _exception(error: EclAllowancePostingError) -> HTTPException:
    if isinstance(error, EclAllowancePostingNotFound):
        status_code = 404
    elif isinstance(error, EclAllowancePostingBlocked):
        status_code = 409
    else:
        status_code = 500
    return HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": str(error)},
    )


def _require_management(actor) -> None:
    if "management" not in actor.roles:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "management_role_required",
                "message": "Management access is required for protected ECL allowance posting.",
            },
        )


def _require_permission(actor, permission: str) -> None:
    _require_management(actor)
    if permission not in actor.permissions:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "ecl_allowance_permission_required",
                "message": f"Protected ECL allowance permission {permission} is required.",
            },
        )


def create_ecl_allowance_posting_router() -> APIRouter:
    router = APIRouter(tags=["management financial accounting"])

    @router.get("/api/v1/management/financial-accounting/ecl-allowance-posting")
    @router.get(
        "/api/mobile/v1/management/financial-accounting/ecl-allowance-posting",
        include_in_schema=False,
    )
    def list_allowance_posting_queue(
        status: Literal[
            "all",
            "measurement_not_authoritative",
            "no_allowance_required",
            "preparation_required",
            "posting_ready",
            "posted_current",
            "a5_remeasurement_required",
            "posting_audit_incomplete",
            "ready",
        ] = Query(default="all"),
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        allowance: PostgresEclAllowancePostingRepository = Depends(
            ecl_allowance_posting_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_management(actor)
        items = allowance.list_queue(status=status, limit=limit, offset=offset)
        summary = allowance.summary()
        return {
            "success": True,
            "data": {
                "items": [_queue_payload(item) for item in items],
                "summary": {
                    **summary,
                    "protected_allowance_balance_total": _money(
                        summary["protected_allowance_balance_total"]
                    ),
                },
                "filter": status,
                "limit": limit,
                "offset": offset,
                "prepare_permission": PREPARE_PERMISSION in actor.permissions,
                "post_permission": POST_PERMISSION in actor.permissions,
                "notice": (
                    "A4 permits only explicit Management-confirmed initial allowance posting from an exact current A3 measurement and prior allowance 0.00. "
                    "Remeasurement/reversal is A5. Automatic source posting remains disabled."
                ),
            },
        }

    @router.post(
        "/api/v1/management/financial-accounting/ecl-allowance-posting/{measurement_id}/prepare"
    )
    @router.post(
        "/api/mobile/v1/management/financial-accounting/ecl-allowance-posting/{measurement_id}/prepare",
        include_in_schema=False,
    )
    def prepare_allowance(
        measurement_id: UUID,
        request: PrepareEclAllowanceRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        allowance: PostgresEclAllowancePostingRepository = Depends(
            ecl_allowance_posting_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_permission(actor, PREPARE_PERMISSION)
        try:
            item = allowance.prepare(
                measurement_id=measurement_id,
                actor_user_id=actor.user_id,
                preparation_review_token=request.preparation_review_token.lower(),
                expected_calculation_digest=request.expected_calculation_digest.lower(),
                expected_ecl_amount=request.expected_ecl_amount,
                expected_posting_date=request.expected_posting_date,
                expected_fiscal_period_id=request.expected_fiscal_period_id,
                expected_credit_loss_expense_account_id=request.expected_credit_loss_expense_account_id,
                expected_allowance_account_id=request.expected_allowance_account_id,
                expected_prior_allowance_balance=request.expected_prior_allowance_balance,
            )
        except EclAllowancePostingError as error:
            raise _exception(error) from error
        return {"success": True, "data": _preparation_payload(item)}

    @router.post(
        "/api/v1/management/financial-accounting/ecl-allowance-posting/preparations/{preparation_id}/post"
    )
    @router.post(
        "/api/mobile/v1/management/financial-accounting/ecl-allowance-posting/preparations/{preparation_id}/post",
        include_in_schema=False,
    )
    def post_allowance(
        preparation_id: UUID,
        request: PostEclAllowanceRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        allowance: PostgresEclAllowancePostingRepository = Depends(
            ecl_allowance_posting_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_permission(actor, POST_PERMISSION)
        try:
            item = allowance.post(
                preparation_id=preparation_id,
                actor_user_id=actor.user_id,
                posting_review_token=request.posting_review_token.lower(),
                expected_measurement_id=request.expected_measurement_id,
                expected_calculation_digest=request.expected_calculation_digest.lower(),
                expected_journal_entry_id=request.expected_journal_entry_id,
                expected_source_event_key=request.expected_source_event_key,
                expected_preparation_digest=request.expected_preparation_digest.lower(),
                expected_posting_date=request.expected_posting_date,
                expected_fiscal_period_id=request.expected_fiscal_period_id,
                expected_credit_loss_expense_account_id=request.expected_credit_loss_expense_account_id,
                expected_allowance_account_id=request.expected_allowance_account_id,
                expected_allowance_amount=request.expected_allowance_amount,
                expected_prior_allowance_balance=request.expected_prior_allowance_balance,
            )
        except EclAllowancePostingError as error:
            raise _exception(error) from error
        return {"success": True, "data": _posting_payload(item)}

    return router
