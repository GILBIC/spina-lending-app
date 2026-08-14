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
from .period_close_repository import (
    PeriodCloseBlocked,
    PeriodCloseError,
    PeriodCloseItem,
    PostgresPeriodCloseRepository,
)
from .request_auth import authenticated_device_context


CLOSE_PREPARE_PERMISSION = "accounting.period.close.prepare"
CLOSE_POST_PERMISSION = "accounting.period.close.post"


class StrictPeriodCloseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PreparePeriodCloseRequest(StrictPeriodCloseRequest):
    confirm: bool = False


class PostPeriodCloseRequest(StrictPeriodCloseRequest):
    confirm: bool = False
    confirmation_token: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_close_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_net_income: Decimal = Field(max_digits=18, decimal_places=2)
    expected_retained_earnings_account_code: Literal["3100"]
    expected_period_end_date: date

    @field_validator("expected_net_income")
    @classmethod
    def exact_currency_cents(cls, value: Decimal) -> Decimal:
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("Expected period profit or loss must use exact currency-cent precision.")
        return value


def period_close_repository_dependency() -> PostgresPeriodCloseRepository:
    return PostgresPeriodCloseRepository()


def _item_payload(item: PeriodCloseItem) -> dict[str, object]:
    return {
        "fiscal_period_id": str(item.fiscal_period_id),
        "label": item.label,
        "start_date": item.start_date.isoformat(),
        "end_date": item.end_date.isoformat(),
        "fiscal_period_status": item.fiscal_period_status,
        "closed_by_user_id": str(item.closed_by_user_id) if item.closed_by_user_id else None,
        "closed_at": item.closed_at.isoformat() if item.closed_at else None,
        "preparation_id": str(item.preparation_id) if item.preparation_id else None,
        "journal_entry_id": str(item.journal_entry_id) if item.journal_entry_id else None,
        "temporary_account_count": item.temporary_account_count,
        "net_income": format(item.net_income, ".2f") if item.net_income is not None else None,
        "retained_earnings_balance_before": (
            format(item.retained_earnings_balance_before, ".2f")
            if item.retained_earnings_balance_before is not None
            else None
        ),
        "close_digest": item.close_digest,
        "close_posting_id": str(item.close_posting_id) if item.close_posting_id else None,
        "closing_entry_number": item.closing_entry_number,
        "retained_earnings_balance_after": (
            format(item.retained_earnings_balance_after, ".2f")
            if item.retained_earnings_balance_after is not None
            else None
        ),
        "close_status": item.close_status,
        "close_blocker": item.close_blocker,
        "protected_period_close_enabled": item.protected_period_close_enabled,
        "retained_earnings_close_enabled": item.retained_earnings_close_enabled,
        "closed_period_posting_protection_enabled": item.closed_period_posting_protection_enabled,
        "period_reopen_enabled": item.period_reopen_enabled,
        "automatic_source_posting": item.automatic_source_posting,
    }


def _summary_payload(summary: dict[str, object]) -> dict[str, object]:
    return {
        key: format(value, "f") if isinstance(value, Decimal) else value
        for key, value in summary.items()
    }


def _exception(error: PeriodCloseError) -> HTTPException:
    return HTTPException(
        status_code=409 if isinstance(error, PeriodCloseBlocked) else 500,
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
                "message": "Management access is required for protected formal period close.",
            },
        )
    return actor


def _require_permission(actor, permission: str) -> None:
    if permission not in actor.permissions:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "period_close_permission_required",
                "message": f"Protected formal period-close permission {permission} is required.",
            },
        )


def _require_confirmation(confirm: bool, action: str) -> None:
    if not confirm:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "period_close_confirmation_required",
                "message": f"Explicit Management confirmation is required before {action}.",
            },
        )


def create_period_close_router() -> APIRouter:
    router = APIRouter(tags=["management financial accounting"])

    @router.get("/api/v1/management/financial-accounting/period-close")
    def list_period_close_items(
        close_status: Literal[
            "all",
            "ready_for_review",
            "ready_to_prepare",
            "prepared",
            "closed",
            "blocked",
        ] = Query(default="all"),
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        close: PostgresPeriodCloseRepository = Depends(period_close_repository_dependency),
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
                "summary": _summary_payload(close.summary()),
                "items": [
                    _item_payload(item)
                    for item in close.list_items(status=close_status, limit=limit, offset=offset)
                ],
                "permissions": {
                    "close_prepare": CLOSE_PREPARE_PERMISSION in actor.permissions,
                    "close_post": CLOSE_POST_PERMISSION in actor.permissions,
                },
                "notice": (
                    "A formal V1 period close requires the accounting period to be placed in review after all drafts are resolved. "
                    "Review freezes ordinary journal activity. The protected close snapshots exact posted income/expense balances, transfers exact period profit or loss to 3100 Retained Earnings, then atomically closes the period. "
                    "Closed periods cannot reopen in V1 and automatic source posting remains disabled."
                ),
            },
        }

    @router.post(
        "/api/v1/management/financial-accounting/period-close/{fiscal_period_id}/prepare"
    )
    def prepare_period_close(
        fiscal_period_id: UUID,
        body: PreparePeriodCloseRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        close: PostgresPeriodCloseRepository = Depends(period_close_repository_dependency),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_permission(actor, CLOSE_PREPARE_PERMISSION)
        _require_confirmation(body.confirm, "preparing the immutable formal period-close snapshot")
        try:
            close.prepare(fiscal_period_id=fiscal_period_id, actor_user_id=actor.user_id)
            item = close.get_item(fiscal_period_id)
        except PeriodCloseError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"item": _item_payload(item)}}

    @router.post(
        "/api/v1/management/financial-accounting/period-close/{fiscal_period_id}/post"
    )
    def post_period_close(
        fiscal_period_id: UUID,
        body: PostPeriodCloseRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        close: PostgresPeriodCloseRepository = Depends(period_close_repository_dependency),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_permission(actor, CLOSE_POST_PERMISSION)
        _require_confirmation(body.confirm, "posting retained earnings and closing the accounting period")
        try:
            close.post(
                fiscal_period_id=fiscal_period_id,
                actor_user_id=actor.user_id,
                confirmation_token=body.confirmation_token.lower(),
                expected_close_digest=body.expected_close_digest.lower(),
                expected_net_income=body.expected_net_income,
                expected_retained_earnings_account_code=body.expected_retained_earnings_account_code,
                expected_period_end_date=body.expected_period_end_date,
            )
            item = close.get_item(fiscal_period_id)
        except PeriodCloseError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"item": _item_payload(item)}}

    return router
