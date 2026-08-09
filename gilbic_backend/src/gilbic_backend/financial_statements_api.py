from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .financial_statements_repository import (
    FinancialStatementLine,
    FinancialStatementPack,
    PostgresFinancialStatementsRepository,
    StatementPeriodNotFound,
)
from .request_auth import authenticated_device_context


def financial_statements_repository_dependency() -> PostgresFinancialStatementsRepository:
    return PostgresFinancialStatementsRepository()


def _decimal(value: Decimal) -> str:
    return format(value, ".2f")


def _line_payload(line: FinancialStatementLine) -> dict[str, object]:
    return {
        "account_code": line.account_code,
        "account_name": line.account_name,
        "amount": _decimal(line.amount),
    }


def _pack_payload(pack: FinancialStatementPack) -> dict[str, object]:
    return {
        "period": {
            "period_id": str(pack.period.period_id),
            "label": pack.period.label,
            "start_date": pack.period.start_date.isoformat(),
            "end_date": pack.period.end_date.isoformat(),
            "status": pack.period.status,
        },
        "profit_or_loss": {
            "income_lines": [_line_payload(line) for line in pack.income_lines],
            "expense_lines": [_line_payload(line) for line in pack.expense_lines],
            "total_income": _decimal(pack.total_income),
            "total_expenses": _decimal(pack.total_expenses),
            "net_income": _decimal(pack.net_income),
        },
        "financial_position": {
            "as_of_date": pack.period.end_date.isoformat(),
            "asset_lines": [_line_payload(line) for line in pack.asset_lines],
            "liability_lines": [_line_payload(line) for line in pack.liability_lines],
            "equity_lines": [_line_payload(line) for line in pack.equity_lines],
            "total_assets": _decimal(pack.total_assets),
            "total_liabilities": _decimal(pack.total_liabilities),
            "recorded_equity": _decimal(pack.recorded_equity),
            "unclosed_earnings_to_date": _decimal(pack.unclosed_earnings_to_date),
            "total_equity": _decimal(pack.total_equity),
            "total_liabilities_and_equity": _decimal(
                pack.total_liabilities_and_equity
            ),
            "balanced": pack.balanced,
        },
        "source": "posted_general_ledger_only",
        "notice": (
            "These statements are generated only from posted General Ledger entries. "
            "Draft journals are excluded. Opening-balance cutover, automatic lending "
            "posting, ECL posting, tax posting, and formal closing entries remain "
            "separate controlled accounting stages."
        ),
    }


def create_financial_statements_router() -> APIRouter:
    router = APIRouter(tags=["management financial statements"])

    @router.get("/api/v1/management/financial-accounting/statements")
    @router.get(
        "/api/mobile/v1/management/financial-accounting/statements",
        include_in_schema=False,
    )
    def financial_statements(
        period_id: UUID | None = Query(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        statements: PostgresFinancialStatementsRepository = Depends(
            financial_statements_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.view",
            permission_error="Financial Accounting view permission is required.",
        )
        if "management" not in actor.roles:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "management_role_required",
                    "message": "Management access is required for Financial Statements.",
                },
            )
        try:
            pack = statements.load_statement_pack(period_id=period_id)
        except StatementPeriodNotFound as error:
            raise HTTPException(
                status_code=404,
                detail={"code": error.code, "message": str(error)},
            ) from error
        return {"success": True, "data": {"statements": _pack_payload(pack)}}

    return router
