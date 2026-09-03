from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .initial_capital_funding_repository import (
    EligibleInitialCapitalCashAccount,
    InitialCapitalFundingBlocked,
    InitialCapitalFundingError,
    InitialCapitalFundingItem,
    InitialCapitalFundingSummary,
    PostgresInitialCapitalFundingRepository,
)
from .request_auth import authenticated_device_context


EVIDENCE_PERMISSION = "accounting.initial_capital.evidence.record"
PREPARE_PERMISSION = "accounting.initial_capital.prepare"
POST_PERMISSION = "accounting.initial_capital.post"


class StrictInitialCapitalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RecordInitialCapitalEvidenceRequest(StrictInitialCapitalRequest):
    idempotency_key: UUID
    funding_date: date
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    cash_account_code: str = Field(min_length=1, max_length=20)
    evidence_source: str = Field(min_length=1, max_length=120)
    evidence_reference: str = Field(min_length=1, max_length=240)
    evidence_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    evidence_note: str = Field(min_length=20, max_length=4000)

    @field_validator("amount")
    @classmethod
    def exact_currency_cents(cls, value: Decimal) -> Decimal:
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("Initial-capital amount must use exact currency-cent precision.")
        return value

    @field_validator(
        "cash_account_code",
        "evidence_source",
        "evidence_reference",
        "evidence_note",
    )
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Required initial-capital evidence text cannot be blank.")
        return normalized


class PrepareInitialCapitalRequest(StrictInitialCapitalRequest):
    confirm: bool = False


class PostInitialCapitalRequest(StrictInitialCapitalRequest):
    confirm: bool = False
    confirmation_token: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_evidence_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    expected_cash_account_code: str = Field(min_length=1, max_length=20)
    expected_posting_date: date
    expected_fiscal_period_id: UUID

    @field_validator("expected_amount")
    @classmethod
    def exact_currency_cents(cls, value: Decimal) -> Decimal:
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("Initial-capital amount must use exact currency-cent precision.")
        return value

    @field_validator("expected_cash_account_code")
    @classmethod
    def normalize_account_code(cls, value: str) -> str:
        return value.strip()


def initial_capital_repository_dependency() -> PostgresInitialCapitalFundingRepository:
    return PostgresInitialCapitalFundingRepository()


def _item_payload(item: InitialCapitalFundingItem) -> dict[str, object]:
    return {
        "evidence_id": str(item.evidence_id),
        "funding_date": item.funding_date.isoformat(),
        "amount": format(item.amount, ".2f"),
        "cash_account_code": item.cash_account_code,
        "cash_account_name": item.cash_account_name,
        "capital_account_code": item.capital_account_code,
        "evidence_source": item.evidence_source,
        "evidence_reference": item.evidence_reference,
        "evidence_digest": item.evidence_digest,
        "evidence_note": item.evidence_note,
        "recorded_by_user_id": str(item.recorded_by_user_id),
        "recorded_at": item.recorded_at.isoformat(),
        "journal_entry_id": str(item.journal_entry_id) if item.journal_entry_id else None,
        "journal_status": item.journal_status,
        "entry_number": item.entry_number,
        "fiscal_period_id": str(item.fiscal_period_id) if item.fiscal_period_id else None,
        "prepared_by_user_id": (
            str(item.prepared_by_user_id) if item.prepared_by_user_id else None
        ),
        "prepared_at": item.prepared_at.isoformat() if item.prepared_at else None,
        "confirmation_digest": item.confirmation_digest,
        "posted_by_user_id": str(item.posted_by_user_id) if item.posted_by_user_id else None,
        "posted_at": item.posted_at.isoformat() if item.posted_at else None,
        "accounting_status": item.accounting_status,
        "accounting_blocker": item.accounting_blocker,
        "protected_initial_capital_funding_enabled": (
            item.protected_initial_capital_funding_enabled
        ),
        "synthetic_opening_balance_required": item.synthetic_opening_balance_required,
        "automatic_source_posting": item.automatic_source_posting,
    }


def _summary_payload(summary: InitialCapitalFundingSummary) -> dict[str, object]:
    return {
        "evidence_count": summary.evidence_count,
        "evidence_ready_count": summary.evidence_ready_count,
        "prepared_not_posted_count": summary.prepared_not_posted_count,
        "posted_count": summary.posted_count,
        "blocked_no_open_period_count": summary.blocked_no_open_period_count,
        "total_amount": format(summary.total_amount, ".2f"),
        "posted_amount": format(summary.posted_amount, ".2f"),
    }


def _cash_account_payload(
    account: EligibleInitialCapitalCashAccount,
) -> dict[str, object]:
    return {"code": account.code, "name": account.name}


def _exception(error: InitialCapitalFundingError) -> HTTPException:
    return HTTPException(
        status_code=409 if isinstance(error, InitialCapitalFundingBlocked) else 500,
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
                "message": "Management access is required for protected initial-capital accounting.",
            },
        )
    return actor


def _require_permission(actor, permission: str) -> None:
    if permission not in actor.permissions:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "initial_capital_permission_required",
                "message": f"Protected initial-capital permission {permission} is required.",
            },
        )


def create_initial_capital_funding_router() -> APIRouter:
    router = APIRouter(tags=["management financial accounting"])

    @router.get(
        "/api/mobile/v1/management/financial-accounting/initial-capital-funding"
    )
    @router.get("/api/v1/management/financial-accounting/initial-capital-funding")
    def list_initial_capital_funding(
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        accounting: PostgresInitialCapitalFundingRepository = Depends(
            initial_capital_repository_dependency
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
                "items": [
                    _item_payload(item)
                    for item in accounting.list_items(limit=limit, offset=offset)
                ],
                "summary": _summary_payload(accounting.list_summary()),
                "cash_accounts": [
                    _cash_account_payload(account)
                    for account in accounting.list_eligible_cash_accounts()
                ],
                "permissions": {
                    "evidence_record": EVIDENCE_PERMISSION in actor.permissions,
                    "prepare": PREPARE_PERMISSION in actor.permissions,
                    "post": POST_PERMISSION in actor.permissions,
                },
                "limit": limit,
                "offset": offset,
                "protected_initial_capital_funding_enabled": True,
                "synthetic_opening_balance_required": False,
                "automatic_source_posting": False,
                "notice": (
                    "Initial capital is recorded only from retained explicit funding evidence. "
                    "The protected path reuses the General Journal, never requires a synthetic opening balance, and never posts automatically."
                ),
            },
        }

    @router.post(
        "/api/mobile/v1/management/financial-accounting/initial-capital-funding/evidence",
        status_code=status.HTTP_201_CREATED,
    )
    @router.post(
        "/api/v1/management/financial-accounting/initial-capital-funding/evidence",
        status_code=status.HTTP_201_CREATED,
    )
    def record_initial_capital_evidence(
        body: RecordInitialCapitalEvidenceRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        accounting: PostgresInitialCapitalFundingRepository = Depends(
            initial_capital_repository_dependency
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
            evidence_id = accounting.record_evidence(
                actor_user_id=actor.user_id,
                idempotency_key=body.idempotency_key,
                funding_date=body.funding_date,
                amount=body.amount,
                cash_account_code=body.cash_account_code,
                evidence_source=body.evidence_source,
                evidence_reference=body.evidence_reference,
                evidence_digest=body.evidence_digest.lower(),
                evidence_note=body.evidence_note,
            )
            item = accounting.get_item(evidence_id)
        except InitialCapitalFundingError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"item": _item_payload(item)}}

    @router.post(
        "/api/mobile/v1/management/financial-accounting/initial-capital-funding/{evidence_id}/prepare"
    )
    @router.post(
        "/api/v1/management/financial-accounting/initial-capital-funding/{evidence_id}/prepare"
    )
    def prepare_initial_capital(
        evidence_id: UUID,
        body: PrepareInitialCapitalRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        accounting: PostgresInitialCapitalFundingRepository = Depends(
            initial_capital_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_permission(actor, PREPARE_PERMISSION)
        if not body.confirm:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "initial_capital_prepare_confirmation_required",
                    "message": "Confirm preparation from the exact retained funding evidence before continuing.",
                },
            )
        try:
            accounting.prepare(evidence_id=evidence_id, actor_user_id=actor.user_id)
            item = accounting.get_item(evidence_id)
        except InitialCapitalFundingError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"item": _item_payload(item)}}

    @router.post(
        "/api/mobile/v1/management/financial-accounting/initial-capital-funding/{evidence_id}/post"
    )
    @router.post(
        "/api/v1/management/financial-accounting/initial-capital-funding/{evidence_id}/post"
    )
    def post_initial_capital(
        evidence_id: UUID,
        body: PostInitialCapitalRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        accounting: PostgresInitialCapitalFundingRepository = Depends(
            initial_capital_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_permission(actor, POST_PERMISSION)
        if not body.confirm:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "initial_capital_post_confirmation_required",
                    "message": "Confirm the exact funding evidence, amount, cash/bank account, date and fiscal period before posting.",
                },
            )
        try:
            accounting.post(
                evidence_id=evidence_id,
                actor_user_id=actor.user_id,
                confirmation_token=body.confirmation_token.lower(),
                expected_evidence_digest=body.expected_evidence_digest.lower(),
                expected_amount=body.expected_amount,
                expected_cash_account_code=body.expected_cash_account_code,
                expected_posting_date=body.expected_posting_date,
                expected_fiscal_period_id=body.expected_fiscal_period_id,
            )
            item = accounting.get_item(evidence_id)
        except InitialCapitalFundingError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"item": _item_payload(item)}}

    return router
