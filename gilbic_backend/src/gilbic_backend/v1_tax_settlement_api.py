from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .request_auth import authenticated_device_context
from .v1_tax_settlement_repository import (
    PostgresV1TaxSettlementRepository,
    V1TaxSettlementBlocked,
    V1TaxSettlementError,
    V1TaxSettlementItem,
)


RETURN_PERMISSION = "accounting.tax.return_evidence.record"
PAYMENT_PERMISSION = "accounting.tax.payment_evidence.record"
SETTLEMENT_PREPARE_PERMISSION = "accounting.tax.settlement.prepare"
SETTLEMENT_POST_PERMISSION = "accounting.tax.settlement.post"
TaxType = Literal["documentary_stamp_tax", "percentage_tax_lending"]


class StrictV1TaxSettlementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RecordV1TaxReturnRequest(StrictV1TaxSettlementRequest):
    idempotency_key: UUID
    tax_type: TaxType
    return_period_start: date
    return_period_end: date
    filing_date: date
    declared_tax_due: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    return_reference: str = Field(min_length=1, max_length=240)
    evidence_reference: str = Field(min_length=1, max_length=500)
    evidence_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    evidence_note: str = Field(min_length=20, max_length=4000)
    liability_posting_ids: list[UUID] = Field(min_length=1, max_length=500)

    @field_validator("declared_tax_due")
    @classmethod
    def exact_currency_cents(cls, value: Decimal) -> Decimal:
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("Declared tax due must use exact currency-cent precision.")
        return value

    @field_validator("return_reference", "evidence_reference", "evidence_note")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Required tax return evidence text cannot be blank.")
        return normalized

    @field_validator("liability_posting_ids")
    @classmethod
    def unique_liability_postings(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("Tax return liability posting identifiers must be unique.")
        return value


class RecordV1TaxPaymentRequest(StrictV1TaxSettlementRequest):
    idempotency_key: UUID
    payment_date: date
    payment_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    cash_account_system_key: Literal["cash_office", "cash_bank_gcash"]
    payment_reference: str = Field(min_length=1, max_length=240)
    evidence_reference: str = Field(min_length=1, max_length=500)
    evidence_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    evidence_note: str = Field(min_length=20, max_length=4000)

    @field_validator("payment_amount")
    @classmethod
    def exact_currency_cents(cls, value: Decimal) -> Decimal:
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("Tax payment amount must use exact currency-cent precision.")
        return value

    @field_validator("payment_reference", "evidence_reference", "evidence_note")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Required tax payment evidence text cannot be blank.")
        return normalized


class PrepareV1TaxSettlementRequest(StrictV1TaxSettlementRequest):
    confirm: bool = False


class PostV1TaxSettlementRequest(StrictV1TaxSettlementRequest):
    confirm: bool = False
    confirmation_token: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_return_evidence_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_payment_evidence_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_payment_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    expected_tax_payable_account_code: str = Field(min_length=1, max_length=20)
    expected_cash_account_code: str = Field(min_length=1, max_length=20)
    expected_posting_date: date
    expected_fiscal_period_id: UUID

    @field_validator("expected_payment_amount")
    @classmethod
    def exact_currency_cents(cls, value: Decimal) -> Decimal:
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("Expected tax payment amount must use exact currency-cent precision.")
        return value

    @field_validator("expected_tax_payable_account_code", "expected_cash_account_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Expected tax settlement account code cannot be blank.")
        return normalized


def v1_tax_settlement_repository_dependency() -> PostgresV1TaxSettlementRepository:
    return PostgresV1TaxSettlementRepository()


def _item_payload(item: V1TaxSettlementItem) -> dict[str, object]:
    return {
        "tax_return_id": str(item.tax_return_id),
        "tax_type": item.tax_type,
        "return_period_start": item.return_period_start.isoformat(),
        "return_period_end": item.return_period_end.isoformat(),
        "filing_date": item.filing_date.isoformat(),
        "declared_tax_due": format(item.declared_tax_due, ".2f"),
        "return_reference": item.return_reference,
        "return_evidence_reference": item.return_evidence_reference,
        "return_evidence_digest": item.return_evidence_digest,
        "return_recorded_by_user_id": str(item.return_recorded_by_user_id),
        "return_recorded_at": item.return_recorded_at.isoformat(),
        "liability_count": item.liability_count,
        "current_exact_count": item.current_exact_count,
        "liability_total": format(item.liability_total, ".2f"),
        "payment_evidence_id": str(item.payment_evidence_id) if item.payment_evidence_id else None,
        "payment_date": item.payment_date.isoformat() if item.payment_date else None,
        "payment_amount": format(item.payment_amount, ".2f") if item.payment_amount is not None else None,
        "cash_account_system_key": item.cash_account_system_key,
        "cash_account_code": item.cash_account_code,
        "cash_account_name": item.cash_account_name,
        "payment_reference": item.payment_reference,
        "payment_evidence_reference": item.payment_evidence_reference,
        "payment_evidence_digest": item.payment_evidence_digest,
        "payment_recorded_by_user_id": str(item.payment_recorded_by_user_id) if item.payment_recorded_by_user_id else None,
        "payment_recorded_at": item.payment_recorded_at.isoformat() if item.payment_recorded_at else None,
        "preparation_id": str(item.preparation_id) if item.preparation_id else None,
        "journal_entry_id": str(item.journal_entry_id) if item.journal_entry_id else None,
        "journal_status": item.journal_status,
        "entry_number": item.entry_number,
        "fiscal_period_id": str(item.fiscal_period_id) if item.fiscal_period_id else None,
        "prepared_by_user_id": str(item.prepared_by_user_id) if item.prepared_by_user_id else None,
        "prepared_at": item.prepared_at.isoformat() if item.prepared_at else None,
        "settlement_posting_id": str(item.settlement_posting_id) if item.settlement_posting_id else None,
        "confirmation_digest": item.confirmation_digest,
        "posted_by_user_id": str(item.posted_by_user_id) if item.posted_by_user_id else None,
        "posted_at": item.posted_at.isoformat() if item.posted_at else None,
        "settlement_status": item.settlement_status,
        "settlement_blocker": item.settlement_blocker,
        "tax_settlement_enabled": item.tax_settlement_enabled,
        "tax_adjustment_reversal_enabled": item.tax_adjustment_reversal_enabled,
        "automatic_source_posting": item.automatic_source_posting,
    }


def _summary_payload(summary: dict[str, object]) -> dict[str, object]:
    return {
        key: format(value, "f") if isinstance(value, Decimal) else value
        for key, value in summary.items()
    }


def _exception(error: V1TaxSettlementError) -> HTTPException:
    return HTTPException(
        status_code=409 if isinstance(error, V1TaxSettlementBlocked) else 500,
        detail={"code": error.code, "message": str(error)},
    )


def _actor(*, authorization: str | None, x_device_id: str | None, auth: SupabaseAuthClient, accounts: PostgresAccountRepository):
    actor = authenticated_device_context(
        authorization=authorization,
        device_identifier=x_device_id,
        auth=auth,
        accounts=accounts,
    )
    if "management" not in actor.roles:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "management_role_required",
                "message": "Management access is required for protected V1 tax return/payment settlement accounting.",
            },
        )
    return actor


def _require_permission(actor, permission: str) -> None:
    if permission not in actor.permissions:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "v1_tax_settlement_permission_required",
                "message": f"Protected V1 tax settlement permission {permission} is required.",
            },
        )


def _require_confirmation(confirm: bool, action: str) -> None:
    if not confirm:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "v1_tax_settlement_confirmation_required",
                "message": f"Explicit Management confirmation is required before {action}.",
            },
        )


def create_v1_tax_settlement_router() -> APIRouter:
    router = APIRouter(tags=["management financial accounting"])

    @router.get("/api/v1/management/financial-accounting/tax/settlements")
    def list_v1_tax_settlements(
        settlement_status: Literal[
            "all", "awaiting_payment", "ready", "prepared", "settled",
            "adjustment_review", "adjustment_in_progress", "adjusted", "blocked"
        ] = Query(default="all"),
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        tax: PostgresV1TaxSettlementRepository = Depends(v1_tax_settlement_repository_dependency),
    ) -> dict[str, object]:
        actor = _actor(authorization=authorization, x_device_id=x_device_id, auth=auth, accounts=accounts)
        return {
            "success": True,
            "data": {
                "summary": _summary_payload(tax.summary()),
                "items": [_item_payload(item) for item in tax.list_items(status=settlement_status, limit=limit, offset=offset)],
                "permissions": {
                    "return_evidence_record": RETURN_PERMISSION in actor.permissions,
                    "payment_evidence_record": PAYMENT_PERMISSION in actor.permissions,
                    "settlement_prepare": SETTLEMENT_PREPARE_PERMISSION in actor.permissions,
                    "settlement_post": SETTLEMENT_POST_PERMISSION in actor.permissions,
                },
                "notice": (
                    "Tax settlement is return/payment-evidence backed and separate from tax expense recognition. "
                    "The protected journal is Dr 2100 Tax Payables / Cr the exact approved Cash - Office or Cash - Bank / GCash account. "
                    "A later stale settled liability is never rewritten: the protected pre-close adjustment core can surface and post an exact supported Tax Recoverable correction while preserving the original settlement. "
                    "Additional-tax amendments and later refund/credit realization require separate retained evidence; automatic source posting remains disabled."
                ),
            },
        }

    @router.post(
        "/api/v1/management/financial-accounting/tax/settlements/returns",
        status_code=status.HTTP_201_CREATED,
    )
    def record_v1_tax_return(
        body: RecordV1TaxReturnRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        tax: PostgresV1TaxSettlementRepository = Depends(v1_tax_settlement_repository_dependency),
    ) -> dict[str, object]:
        actor = _actor(authorization=authorization, x_device_id=x_device_id, auth=auth, accounts=accounts)
        _require_permission(actor, RETURN_PERMISSION)
        try:
            return_id = tax.record_return_evidence(
                actor_user_id=actor.user_id,
                idempotency_key=body.idempotency_key,
                tax_type=body.tax_type,
                return_period_start=body.return_period_start,
                return_period_end=body.return_period_end,
                filing_date=body.filing_date,
                declared_tax_due=body.declared_tax_due,
                return_reference=body.return_reference,
                evidence_reference=body.evidence_reference,
                evidence_digest=body.evidence_digest.lower(),
                evidence_note=body.evidence_note,
                liability_posting_ids=tuple(body.liability_posting_ids),
            )
            item = tax.get_item(return_id)
        except V1TaxSettlementError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"item": _item_payload(item)}}

    @router.post(
        "/api/v1/management/financial-accounting/tax/settlements/returns/{tax_return_id}/payments",
        status_code=status.HTTP_201_CREATED,
    )
    def record_v1_tax_payment(
        tax_return_id: UUID,
        body: RecordV1TaxPaymentRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        tax: PostgresV1TaxSettlementRepository = Depends(v1_tax_settlement_repository_dependency),
    ) -> dict[str, object]:
        actor = _actor(authorization=authorization, x_device_id=x_device_id, auth=auth, accounts=accounts)
        _require_permission(actor, PAYMENT_PERMISSION)
        try:
            tax.record_payment_evidence(
                actor_user_id=actor.user_id,
                idempotency_key=body.idempotency_key,
                tax_return_id=tax_return_id,
                payment_date=body.payment_date,
                payment_amount=body.payment_amount,
                cash_account_system_key=body.cash_account_system_key,
                payment_reference=body.payment_reference,
                evidence_reference=body.evidence_reference,
                evidence_digest=body.evidence_digest.lower(),
                evidence_note=body.evidence_note,
            )
            item = tax.get_item(tax_return_id)
        except V1TaxSettlementError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"item": _item_payload(item)}}

    @router.post(
        "/api/v1/management/financial-accounting/tax/settlements/payments/{payment_evidence_id}/prepare"
    )
    def prepare_v1_tax_settlement(
        payment_evidence_id: UUID,
        body: PrepareV1TaxSettlementRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        tax: PostgresV1TaxSettlementRepository = Depends(v1_tax_settlement_repository_dependency),
    ) -> dict[str, object]:
        actor = _actor(authorization=authorization, x_device_id=x_device_id, auth=auth, accounts=accounts)
        _require_permission(actor, SETTLEMENT_PREPARE_PERMISSION)
        _require_confirmation(body.confirm, "preparing the protected tax settlement journal")
        try:
            tax.prepare(payment_evidence_id=payment_evidence_id, actor_user_id=actor.user_id)
            item = tax.get_item_by_payment(payment_evidence_id)
        except V1TaxSettlementError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"item": _item_payload(item)}}

    @router.post(
        "/api/v1/management/financial-accounting/tax/settlements/payments/{payment_evidence_id}/post"
    )
    def post_v1_tax_settlement(
        payment_evidence_id: UUID,
        body: PostV1TaxSettlementRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        tax: PostgresV1TaxSettlementRepository = Depends(v1_tax_settlement_repository_dependency),
    ) -> dict[str, object]:
        actor = _actor(authorization=authorization, x_device_id=x_device_id, auth=auth, accounts=accounts)
        _require_permission(actor, SETTLEMENT_POST_PERMISSION)
        _require_confirmation(body.confirm, "posting the protected tax settlement")
        try:
            tax.post(
                payment_evidence_id=payment_evidence_id,
                actor_user_id=actor.user_id,
                confirmation_token=body.confirmation_token.lower(),
                expected_return_evidence_digest=body.expected_return_evidence_digest.lower(),
                expected_payment_evidence_digest=body.expected_payment_evidence_digest.lower(),
                expected_payment_amount=body.expected_payment_amount,
                expected_tax_payable_account_code=body.expected_tax_payable_account_code,
                expected_cash_account_code=body.expected_cash_account_code,
                expected_posting_date=body.expected_posting_date,
                expected_fiscal_period_id=body.expected_fiscal_period_id,
            )
            item = tax.get_item_by_payment(payment_evidence_id)
        except V1TaxSettlementError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"item": _item_payload(item)}}

    return router
