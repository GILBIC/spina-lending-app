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
from .v1_tax_recoverable_refund_repository import (
    PostgresV1TaxRecoverableRefundRepository,
    V1TaxRecoverableRefundBlocked,
    V1TaxRecoverableRefundError,
    V1TaxRecoverableRefundItem,
)


EVIDENCE_PERMISSION = "accounting.tax.recoverable_refund_evidence.record"
REFUND_PREPARE_PERMISSION = "accounting.tax.recoverable_refund.prepare"
REFUND_POST_PERMISSION = "accounting.tax.recoverable_refund.post"


class StrictV1TaxRecoverableRefundRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RecordV1TaxRecoverableRefundEvidenceRequest(StrictV1TaxRecoverableRefundRequest):
    idempotency_key: UUID
    adjustment_posting_id: UUID
    refund_date: date
    cash_account_code: Literal["1010", "1030"]
    refund_reference: str = Field(min_length=1, max_length=240)
    authority_reference: str = Field(min_length=1, max_length=500)
    evidence_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    evidence_note: str = Field(min_length=20, max_length=4000)

    @field_validator("refund_reference", "authority_reference", "evidence_note")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Required Tax Recoverable refund evidence text cannot be blank.")
        return normalized


class PrepareV1TaxRecoverableRefundRequest(StrictV1TaxRecoverableRefundRequest):
    confirm: bool = False


class PostV1TaxRecoverableRefundRequest(StrictV1TaxRecoverableRefundRequest):
    confirm: bool = False
    confirmation_token: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_evidence_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_refund_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    expected_cash_account_code: Literal["1010", "1030"]
    expected_tax_recoverable_account_code: Literal["1130"]
    expected_posting_date: date
    expected_fiscal_period_id: UUID

    @field_validator("expected_refund_amount")
    @classmethod
    def exact_currency_cents(cls, value: Decimal) -> Decimal:
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("Expected Tax Recoverable refund amount must use exact currency-cent precision.")
        return value


def v1_tax_recoverable_refund_repository_dependency() -> PostgresV1TaxRecoverableRefundRepository:
    return PostgresV1TaxRecoverableRefundRepository()


def _item_payload(item: V1TaxRecoverableRefundItem) -> dict[str, object]:
    return {
        "refund_evidence_id": str(item.refund_evidence_id),
        "adjustment_posting_id": str(item.adjustment_posting_id),
        "adjustment_evidence_id": str(item.adjustment_evidence_id),
        "tax_type": item.tax_type,
        "source_id": str(item.source_id),
        "loan_id": str(item.loan_id),
        "client_id": str(item.client_id),
        "refund_amount": format(item.refund_amount, ".2f"),
        "refund_date": item.refund_date.isoformat(),
        "cash_account_id": str(item.cash_account_id),
        "cash_account_code": item.cash_account_code,
        "cash_account_name": item.cash_account_name,
        "refund_reference": item.refund_reference,
        "authority_reference": item.authority_reference,
        "evidence_digest": item.evidence_digest,
        "recorded_by_user_id": str(item.recorded_by_user_id),
        "recorded_at": item.recorded_at.isoformat(),
        "preparation_id": str(item.preparation_id) if item.preparation_id else None,
        "journal_entry_id": str(item.journal_entry_id) if item.journal_entry_id else None,
        "journal_status": item.journal_status,
        "entry_number": item.entry_number,
        "fiscal_period_id": str(item.fiscal_period_id) if item.fiscal_period_id else None,
        "tax_recoverable_account_id": (
            str(item.tax_recoverable_account_id) if item.tax_recoverable_account_id else None
        ),
        "tax_recoverable_account_code": item.tax_recoverable_account_code,
        "tax_recoverable_account_name": item.tax_recoverable_account_name,
        "prepared_by_user_id": str(item.prepared_by_user_id) if item.prepared_by_user_id else None,
        "prepared_at": item.prepared_at.isoformat() if item.prepared_at else None,
        "refund_posting_id": str(item.refund_posting_id) if item.refund_posting_id else None,
        "confirmation_digest": item.confirmation_digest,
        "posted_by_user_id": str(item.posted_by_user_id) if item.posted_by_user_id else None,
        "posted_at": item.posted_at.isoformat() if item.posted_at else None,
        "refund_status": item.refund_status,
        "refund_blocker": item.refund_blocker,
        "tax_recoverable_refund_realization_enabled": item.tax_recoverable_refund_realization_enabled,
        "tax_recoverable_credit_application_enabled": item.tax_recoverable_credit_application_enabled,
        "automatic_source_posting": item.automatic_source_posting,
    }


def _summary_payload(summary: dict[str, object]) -> dict[str, object]:
    return {
        key: format(value, "f") if isinstance(value, Decimal) else value
        for key, value in summary.items()
    }


def _exception(error: V1TaxRecoverableRefundError) -> HTTPException:
    return HTTPException(
        status_code=409 if isinstance(error, V1TaxRecoverableRefundBlocked) else 500,
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
                "message": "Management access is required for protected V1 Tax Recoverable refund accounting.",
            },
        )
    return actor


def _require_permission(actor, permission: str) -> None:
    if permission not in actor.permissions:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "v1_tax_recoverable_refund_permission_required",
                "message": f"Protected V1 Tax Recoverable refund permission {permission} is required.",
            },
        )


def _require_confirmation(confirm: bool, action: str) -> None:
    if not confirm:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "v1_tax_recoverable_refund_confirmation_required",
                "message": f"Explicit Management confirmation is required before {action}.",
            },
        )


def create_v1_tax_recoverable_refund_router() -> APIRouter:
    router = APIRouter(tags=["management financial accounting"])

    @router.get("/api/v1/management/financial-accounting/tax/recoverable-refunds")
    def list_v1_tax_recoverable_refunds(
        refund_status: Literal["all", "ready", "prepared", "realized", "blocked"] = Query(default="all"),
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        tax: PostgresV1TaxRecoverableRefundRepository = Depends(
            v1_tax_recoverable_refund_repository_dependency
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
                    for item in tax.list_items(status=refund_status, limit=limit, offset=offset)
                ],
                "permissions": {
                    "refund_evidence_record": EVIDENCE_PERMISSION in actor.permissions,
                    "refund_prepare": REFUND_PREPARE_PERMISSION in actor.permissions,
                    "refund_post": REFUND_POST_PERMISSION in actor.permissions,
                },
                "notice": (
                    "V1 cash-refund realization requires separate retained authority/refund evidence for an exact posted 1130 Tax Recoverable. "
                    "The protected database derives the full refund amount from the immutable adjustment posting and posts only Dr approved 1010/1030 cash-bank / Cr 1130 Tax Recoverable. "
                    "Tax-credit application and partial recoverable realization remain disabled; automatic source posting remains disabled."
                ),
            },
        }

    @router.post(
        "/api/v1/management/financial-accounting/tax/recoverable-refunds/evidence",
        status_code=status.HTTP_201_CREATED,
    )
    def record_v1_tax_recoverable_refund_evidence(
        body: RecordV1TaxRecoverableRefundEvidenceRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        tax: PostgresV1TaxRecoverableRefundRepository = Depends(
            v1_tax_recoverable_refund_repository_dependency
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
                adjustment_posting_id=body.adjustment_posting_id,
                refund_date=body.refund_date,
                cash_account_code=body.cash_account_code,
                refund_reference=body.refund_reference,
                authority_reference=body.authority_reference,
                evidence_digest=body.evidence_digest.lower(),
                evidence_note=body.evidence_note,
            )
            item = tax.get_item(evidence_id)
        except V1TaxRecoverableRefundError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"item": _item_payload(item)}}

    @router.post(
        "/api/v1/management/financial-accounting/tax/recoverable-refunds/{refund_evidence_id}/prepare"
    )
    def prepare_v1_tax_recoverable_refund(
        refund_evidence_id: UUID,
        body: PrepareV1TaxRecoverableRefundRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        tax: PostgresV1TaxRecoverableRefundRepository = Depends(
            v1_tax_recoverable_refund_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_permission(actor, REFUND_PREPARE_PERMISSION)
        _require_confirmation(body.confirm, "preparing a protected Tax Recoverable refund journal")
        try:
            tax.prepare(refund_evidence_id=refund_evidence_id, actor_user_id=actor.user_id)
            item = tax.get_item(refund_evidence_id)
        except V1TaxRecoverableRefundError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"item": _item_payload(item)}}

    @router.post(
        "/api/v1/management/financial-accounting/tax/recoverable-refunds/{refund_evidence_id}/post"
    )
    def post_v1_tax_recoverable_refund(
        refund_evidence_id: UUID,
        body: PostV1TaxRecoverableRefundRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        tax: PostgresV1TaxRecoverableRefundRepository = Depends(
            v1_tax_recoverable_refund_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_permission(actor, REFUND_POST_PERMISSION)
        _require_confirmation(body.confirm, "posting a protected Tax Recoverable refund journal")
        try:
            tax.post(
                refund_evidence_id=refund_evidence_id,
                actor_user_id=actor.user_id,
                confirmation_token=body.confirmation_token.lower(),
                expected_evidence_digest=body.expected_evidence_digest.lower(),
                expected_refund_amount=body.expected_refund_amount,
                expected_cash_account_code=body.expected_cash_account_code,
                expected_tax_recoverable_account_code=body.expected_tax_recoverable_account_code,
                expected_posting_date=body.expected_posting_date,
                expected_fiscal_period_id=body.expected_fiscal_period_id,
            )
            item = tax.get_item(refund_evidence_id)
        except V1TaxRecoverableRefundError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"item": _item_payload(item)}}

    return router
