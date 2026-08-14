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
from .v1_tax_adjustment_repository import (
    PostgresV1TaxAdjustmentRepository,
    V1TaxAdjustmentBlocked,
    V1TaxAdjustmentError,
    V1TaxAdjustmentItem,
)


EVIDENCE_PERMISSION = "accounting.tax.adjustment_evidence.record"
ADJUSTMENT_PREPARE_PERMISSION = "accounting.tax.adjustment.prepare"
ADJUSTMENT_POST_PERMISSION = "accounting.tax.adjustment.post"
AdjustmentKind = Literal[
    "reverse_unsettled_liability",
    "recognize_settled_tax_recoverable",
]


class StrictV1TaxAdjustmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RecordV1TaxAdjustmentEvidenceRequest(StrictV1TaxAdjustmentRequest):
    idempotency_key: UUID
    tax_liability_posting_id: UUID
    replacement_evidence_id: UUID
    adjustment_kind: AdjustmentKind
    adjustment_date: date
    adjustment_reference: str = Field(min_length=1, max_length=240)
    evidence_reference: str = Field(min_length=1, max_length=500)
    evidence_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    evidence_note: str = Field(min_length=20, max_length=4000)

    @field_validator("adjustment_reference", "evidence_reference", "evidence_note")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Required tax adjustment evidence text cannot be blank.")
        return normalized


class PrepareV1TaxAdjustmentRequest(StrictV1TaxAdjustmentRequest):
    confirm: bool = False


class PostV1TaxAdjustmentRequest(StrictV1TaxAdjustmentRequest):
    confirm: bool = False
    confirmation_token: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_evidence_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_original_tax_due: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    expected_replacement_tax_due: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    expected_adjustment_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    expected_debit_account_code: str = Field(min_length=1, max_length=20)
    expected_credit_account_code: str = Field(min_length=1, max_length=20)
    expected_posting_date: date
    expected_fiscal_period_id: UUID

    @field_validator(
        "expected_original_tax_due",
        "expected_replacement_tax_due",
        "expected_adjustment_amount",
    )
    @classmethod
    def exact_currency_cents(cls, value: Decimal) -> Decimal:
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("Expected tax adjustment amounts must use exact currency-cent precision.")
        return value

    @field_validator("expected_debit_account_code", "expected_credit_account_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Expected tax adjustment account code cannot be blank.")
        return normalized


def v1_tax_adjustment_repository_dependency() -> PostgresV1TaxAdjustmentRepository:
    return PostgresV1TaxAdjustmentRepository()


def _item_payload(item: V1TaxAdjustmentItem) -> dict[str, object]:
    return {
        "adjustment_evidence_id": str(item.adjustment_evidence_id),
        "adjustment_kind": item.adjustment_kind,
        "tax_type": item.tax_type,
        "tax_liability_posting_id": str(item.tax_liability_posting_id),
        "original_evidence_id": str(item.original_evidence_id),
        "replacement_evidence_id": str(item.replacement_evidence_id),
        "source_id": str(item.source_id),
        "loan_id": str(item.loan_id),
        "client_id": str(item.client_id),
        "original_tax_due": format(item.original_tax_due, ".2f"),
        "replacement_tax_due": format(item.replacement_tax_due, ".2f"),
        "adjustment_amount": format(item.adjustment_amount, ".2f"),
        "adjustment_date": item.adjustment_date.isoformat(),
        "adjustment_reference": item.adjustment_reference,
        "evidence_reference": item.evidence_reference,
        "evidence_digest": item.evidence_digest,
        "recorded_by_user_id": str(item.recorded_by_user_id),
        "recorded_at": item.recorded_at.isoformat(),
        "settlement_posting_id": str(item.settlement_posting_id) if item.settlement_posting_id else None,
        "original_settlement_journal_entry_id": (
            str(item.original_settlement_journal_entry_id)
            if item.original_settlement_journal_entry_id
            else None
        ),
        "preparation_id": str(item.preparation_id) if item.preparation_id else None,
        "journal_entry_id": str(item.journal_entry_id) if item.journal_entry_id else None,
        "journal_status": item.journal_status,
        "entry_number": item.entry_number,
        "fiscal_period_id": str(item.fiscal_period_id) if item.fiscal_period_id else None,
        "debit_account_id": str(item.debit_account_id) if item.debit_account_id else None,
        "debit_account_code": item.debit_account_code,
        "debit_account_name": item.debit_account_name,
        "credit_account_id": str(item.credit_account_id) if item.credit_account_id else None,
        "credit_account_code": item.credit_account_code,
        "credit_account_name": item.credit_account_name,
        "prepared_by_user_id": str(item.prepared_by_user_id) if item.prepared_by_user_id else None,
        "prepared_at": item.prepared_at.isoformat() if item.prepared_at else None,
        "adjustment_posting_id": str(item.adjustment_posting_id) if item.adjustment_posting_id else None,
        "confirmation_digest": item.confirmation_digest,
        "posted_by_user_id": str(item.posted_by_user_id) if item.posted_by_user_id else None,
        "posted_at": item.posted_at.isoformat() if item.posted_at else None,
        "adjustment_status": item.adjustment_status,
        "adjustment_blocker": item.adjustment_blocker,
        "tax_settlement_enabled": item.tax_settlement_enabled,
        "tax_adjustment_reversal_enabled": item.tax_adjustment_reversal_enabled,
        "automatic_source_posting": item.automatic_source_posting,
    }


def _summary_payload(summary: dict[str, object]) -> dict[str, object]:
    return {
        key: format(value, "f") if isinstance(value, Decimal) else value
        for key, value in summary.items()
    }


def _exception(error: V1TaxAdjustmentError) -> HTTPException:
    return HTTPException(
        status_code=409 if isinstance(error, V1TaxAdjustmentBlocked) else 500,
        detail={"code": error.code, "message": str(error)},
    )


def _actor(
    *,
    authorization: str | None,
    x_device_id: str | None,
    auth: SupabaseAuthClient,
    accounts: PostgresAccountRepository,
):
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
                "message": "Management access is required for protected V1 tax adjustment/reversal accounting.",
            },
        )
    return actor


def _require_permission(actor, permission: str) -> None:
    if permission not in actor.permissions:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "v1_tax_adjustment_permission_required",
                "message": f"Protected V1 tax adjustment permission {permission} is required.",
            },
        )


def _require_confirmation(confirm: bool, action: str) -> None:
    if not confirm:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "v1_tax_adjustment_confirmation_required",
                "message": f"Explicit Management confirmation is required before {action}.",
            },
        )


def create_v1_tax_adjustment_router() -> APIRouter:
    router = APIRouter(tags=["management financial accounting"])

    @router.get("/api/v1/management/financial-accounting/tax/adjustments")
    def list_v1_tax_adjustments(
        adjustment_status: Literal[
            "all", "ready", "prepared", "posted", "review", "blocked"
        ] = Query(default="all"),
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        tax: PostgresV1TaxAdjustmentRepository = Depends(
            v1_tax_adjustment_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        return {
            "success": True,
            "data": {
                "summary": _summary_payload(tax.summary()),
                "items": [
                    _item_payload(item)
                    for item in tax.list_items(
                        status=adjustment_status, limit=limit, offset=offset
                    )
                ],
                "permissions": {
                    "adjustment_evidence_record": EVIDENCE_PERMISSION in actor.permissions,
                    "adjustment_prepare": ADJUSTMENT_PREPARE_PERMISSION in actor.permissions,
                    "adjustment_post": ADJUSTMENT_POST_PERMISSION in actor.permissions,
                },
                "notice": (
                    "V1 tax corrections never rewrite posted liability or settlement history. "
                    "An unpaid stale liability can be fully reversed only while its original fiscal period remains open. "
                    "A fully settled stale liability with an exact supported tax decrease is corrected by Dr 1130 Tax Recoverable / Cr the original dedicated tax expense. "
                    "Additional-tax amendments and later refund/credit realization require separate retained evidence; automatic source posting remains disabled."
                ),
            },
        }

    @router.post(
        "/api/v1/management/financial-accounting/tax/adjustments/evidence",
        status_code=status.HTTP_201_CREATED,
    )
    def record_v1_tax_adjustment_evidence(
        body: RecordV1TaxAdjustmentEvidenceRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        tax: PostgresV1TaxAdjustmentRepository = Depends(
            v1_tax_adjustment_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_permission(actor, EVIDENCE_PERMISSION)
        try:
            evidence_id = tax.record_evidence(
                actor_user_id=actor.user_id,
                idempotency_key=body.idempotency_key,
                tax_liability_posting_id=body.tax_liability_posting_id,
                replacement_evidence_id=body.replacement_evidence_id,
                adjustment_kind=body.adjustment_kind,
                adjustment_date=body.adjustment_date,
                adjustment_reference=body.adjustment_reference,
                evidence_reference=body.evidence_reference,
                evidence_digest=body.evidence_digest.lower(),
                evidence_note=body.evidence_note,
            )
            item = tax.get_item(evidence_id)
        except V1TaxAdjustmentError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"item": _item_payload(item)}}

    @router.post(
        "/api/v1/management/financial-accounting/tax/adjustments/{adjustment_evidence_id}/prepare"
    )
    def prepare_v1_tax_adjustment(
        adjustment_evidence_id: UUID,
        body: PrepareV1TaxAdjustmentRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        tax: PostgresV1TaxAdjustmentRepository = Depends(
            v1_tax_adjustment_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_permission(actor, ADJUSTMENT_PREPARE_PERMISSION)
        _require_confirmation(body.confirm, "preparing a protected tax adjustment journal")
        try:
            tax.prepare(
                adjustment_evidence_id=adjustment_evidence_id,
                actor_user_id=actor.user_id,
            )
            item = tax.get_item(adjustment_evidence_id)
        except V1TaxAdjustmentError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"item": _item_payload(item)}}

    @router.post(
        "/api/v1/management/financial-accounting/tax/adjustments/{adjustment_evidence_id}/post"
    )
    def post_v1_tax_adjustment(
        adjustment_evidence_id: UUID,
        body: PostV1TaxAdjustmentRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        tax: PostgresV1TaxAdjustmentRepository = Depends(
            v1_tax_adjustment_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_permission(actor, ADJUSTMENT_POST_PERMISSION)
        _require_confirmation(body.confirm, "posting a protected tax adjustment journal")
        try:
            tax.post(
                adjustment_evidence_id=adjustment_evidence_id,
                actor_user_id=actor.user_id,
                confirmation_token=body.confirmation_token.lower(),
                expected_evidence_digest=body.expected_evidence_digest.lower(),
                expected_original_tax_due=body.expected_original_tax_due,
                expected_replacement_tax_due=body.expected_replacement_tax_due,
                expected_adjustment_amount=body.expected_adjustment_amount,
                expected_debit_account_code=body.expected_debit_account_code,
                expected_credit_account_code=body.expected_credit_account_code,
                expected_posting_date=body.expected_posting_date,
                expected_fiscal_period_id=body.expected_fiscal_period_id,
            )
            item = tax.get_item(adjustment_evidence_id)
        except V1TaxAdjustmentError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"item": _item_payload(item)}}

    return router
