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
from .request_auth import authenticated_device_context
from .v1_tax_liability_repository import (
    PostgresV1TaxLiabilityRepository,
    V1TaxLiabilityBlocked,
    V1TaxLiabilityError,
    V1TaxLiabilityItem,
)


LIABILITY_PREPARE_PERMISSION = "accounting.tax.liability.prepare"
LIABILITY_POST_PERMISSION = "accounting.tax.liability.post"
TaxType = Literal["documentary_stamp_tax", "percentage_tax_lending"]


class StrictV1TaxLiabilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PrepareV1TaxLiabilityRequest(StrictV1TaxLiabilityRequest):
    confirm: bool = False


class PostV1TaxLiabilityRequest(StrictV1TaxLiabilityRequest):
    confirm: bool = False
    confirmation_token: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_evidence_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_tax_due: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    expected_expense_account_code: str = Field(min_length=1, max_length=20)
    expected_tax_payable_account_code: str = Field(min_length=1, max_length=20)
    expected_posting_date: date
    expected_fiscal_period_id: UUID

    @field_validator("expected_tax_due")
    @classmethod
    def exact_currency_cents(cls, value: Decimal) -> Decimal:
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("Tax liability amount must use exact currency-cent precision.")
        return value

    @field_validator(
        "expected_expense_account_code",
        "expected_tax_payable_account_code",
    )
    @classmethod
    def normalize_account_code(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Expected tax account code cannot be blank.")
        return normalized


def v1_tax_liability_repository_dependency() -> PostgresV1TaxLiabilityRepository:
    return PostgresV1TaxLiabilityRepository()


def _item_payload(item: V1TaxLiabilityItem) -> dict[str, object]:
    return {
        "tax_type": item.tax_type,
        "evidence_id": str(item.evidence_id),
        "evidence_version": item.evidence_version,
        "source_id": str(item.source_id),
        "loan_id": str(item.loan_id),
        "client_id": str(item.client_id),
        "recognition_date": item.recognition_date.isoformat(),
        "tax_due": format(item.tax_due, ".2f"),
        "evidence_digest": item.evidence_digest,
        "evidence_status": item.evidence_status,
        "evidence_blocker": item.evidence_blocker,
        "expense_account_code": item.expense_account_code,
        "expense_account_name": item.expense_account_name,
        "tax_payable_account_code": item.tax_payable_account_code,
        "tax_payable_account_name": item.tax_payable_account_name,
        "preparation_id": str(item.preparation_id) if item.preparation_id else None,
        "journal_entry_id": str(item.journal_entry_id) if item.journal_entry_id else None,
        "journal_status": item.journal_status,
        "entry_number": item.entry_number,
        "fiscal_period_id": str(item.fiscal_period_id) if item.fiscal_period_id else None,
        "prepared_by_user_id": (
            str(item.prepared_by_user_id) if item.prepared_by_user_id else None
        ),
        "prepared_at": item.prepared_at.isoformat() if item.prepared_at else None,
        "posting_id": str(item.posting_id) if item.posting_id else None,
        "confirmation_digest": item.confirmation_digest,
        "posted_by_user_id": str(item.posted_by_user_id) if item.posted_by_user_id else None,
        "posted_at": item.posted_at.isoformat() if item.posted_at else None,
        "accounting_status": item.accounting_status,
        "accounting_blocker": item.accounting_blocker,
        "protected_tax_liability_posting_enabled": (
            item.protected_tax_liability_posting_enabled
        ),
        "tax_settlement_enabled": item.tax_settlement_enabled,
        "tax_adjustment_reversal_enabled": item.tax_adjustment_reversal_enabled,
        "automatic_source_posting": item.automatic_source_posting,
    }


def _summary_payload(summary: dict[str, object]) -> dict[str, object]:
    return {
        key: format(value, "f") if isinstance(value, Decimal) else value
        for key, value in summary.items()
    }


def _exception(error: V1TaxLiabilityError) -> HTTPException:
    return HTTPException(
        status_code=409 if isinstance(error, V1TaxLiabilityBlocked) else 500,
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
                "message": "Management access is required for protected V1 tax-liability accounting.",
            },
        )
    return actor


def _require_permission(actor, permission: str) -> None:
    if permission not in actor.permissions:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "v1_tax_liability_permission_required",
                "message": f"Protected V1 tax-liability permission {permission} is required.",
            },
        )


def _require_confirmation(confirm: bool, action: str) -> None:
    if not confirm:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "v1_tax_liability_confirmation_required",
                "message": f"Explicit Management confirmation is required before {action}.",
            },
        )


def create_v1_tax_liability_router() -> APIRouter:
    router = APIRouter(tags=["management financial accounting"])

    @router.get("/api/v1/management/financial-accounting/tax/liabilities")
    def list_v1_tax_liabilities(
        accounting_status: Literal[
            "all", "ready", "prepared", "posted", "adjustment_review", "blocked"
        ] = Query(default="all"),
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        tax: PostgresV1TaxLiabilityRepository = Depends(
            v1_tax_liability_repository_dependency
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
                        status=accounting_status,
                        limit=limit,
                        offset=offset,
                    )
                ],
                "permissions": {
                    "liability_prepare": LIABILITY_PREPARE_PERMISSION in actor.permissions,
                    "liability_post": LIABILITY_POST_PERMISSION in actor.permissions,
                },
                "notice": (
                    "V1 tax liabilities reuse the protected General Journal and require exact current evidence plus explicit Management confirmation. "
                    "Automatic source posting is disabled. Tax settlement and protected tax adjustment/reversal remain separate later A6.2 controls."
                ),
            },
        }

    @router.post(
        "/api/v1/management/financial-accounting/tax/liabilities/{tax_type}/{evidence_id}/prepare"
    )
    def prepare_v1_tax_liability(
        tax_type: TaxType,
        evidence_id: UUID,
        body: PrepareV1TaxLiabilityRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        tax: PostgresV1TaxLiabilityRepository = Depends(
            v1_tax_liability_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_permission(actor, LIABILITY_PREPARE_PERMISSION)
        _require_confirmation(body.confirm, "preparing the protected tax-liability journal")
        try:
            tax.prepare(
                tax_type=tax_type,
                evidence_id=evidence_id,
                actor_user_id=actor.user_id,
            )
            item = tax.get_item(tax_type=tax_type, evidence_id=evidence_id)
        except V1TaxLiabilityError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"item": _item_payload(item)}}

    @router.post(
        "/api/v1/management/financial-accounting/tax/liabilities/{tax_type}/{evidence_id}/post"
    )
    def post_v1_tax_liability(
        tax_type: TaxType,
        evidence_id: UUID,
        body: PostV1TaxLiabilityRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        tax: PostgresV1TaxLiabilityRepository = Depends(
            v1_tax_liability_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_permission(actor, LIABILITY_POST_PERMISSION)
        _require_confirmation(body.confirm, "posting the protected tax liability")
        try:
            tax.post(
                tax_type=tax_type,
                evidence_id=evidence_id,
                actor_user_id=actor.user_id,
                confirmation_token=body.confirmation_token.lower(),
                expected_evidence_digest=body.expected_evidence_digest.lower(),
                expected_tax_due=body.expected_tax_due,
                expected_expense_account_code=body.expected_expense_account_code,
                expected_tax_payable_account_code=body.expected_tax_payable_account_code,
                expected_posting_date=body.expected_posting_date,
                expected_fiscal_period_id=body.expected_fiscal_period_id,
            )
            item = tax.get_item(tax_type=tax_type, evidence_id=evidence_id)
        except V1TaxLiabilityError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"item": _item_payload(item)}}

    return router
