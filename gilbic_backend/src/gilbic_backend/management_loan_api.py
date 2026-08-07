from __future__ import annotations

from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .management_loan_repository import (
    ManagementLoanPortfolio,
    ManagementLoanRecord,
    ManagementLoanSummary,
    PostgresManagementLoanRepository,
)
from .request_auth import authenticated_device_context


def management_loan_repository_dependency() -> PostgresManagementLoanRepository:
    return PostgresManagementLoanRepository()


def _decimal(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


def _summary_payload(summary: ManagementLoanSummary) -> dict[str, object]:
    return {
        "active_loan_count": summary.active_loan_count,
        "active_client_count": summary.active_client_count,
        "active_principal_total": _decimal(summary.active_principal_total),
        "active_remaining_total": _decimal(summary.active_remaining_total),
        "overdue_active_count": summary.overdue_active_count,
        "active_seven_by_seven_count": summary.active_seven_by_seven_count,
        "approved_renewal_count": summary.approved_renewal_count,
    }


def _loan_payload(record: ManagementLoanRecord) -> dict[str, object]:
    return {
        "loan_id": str(record.loan_id),
        "loan_number": record.loan_number,
        "client_id": str(record.client_id),
        "client_code": record.client_code,
        "client_name": record.client_name,
        "client_area": record.client_area,
        "client_status": record.client_status,
        "loan_type_code": record.loan_type_code,
        "loan_type_name": record.loan_type_name,
        "calculation_mode": record.calculation_mode,
        "principal": _decimal(record.principal),
        "daily_amount": _decimal(record.daily_amount),
        "interest_rate": _decimal(record.interest_rate),
        "remaining_balance": _decimal(record.remaining_balance),
        "paid_amount": _decimal(record.paid_amount),
        "paid_percent": _decimal(record.paid_percent),
        "date_released": (
            record.date_released.isoformat() if record.date_released else None
        ),
        "due_date": record.due_date.isoformat() if record.due_date else None,
        "loan_status": record.loan_status,
        "last_payment_date": (
            record.last_payment_date.isoformat()
            if record.last_payment_date
            else None
        ),
        "advance_until": (
            record.advance_until.isoformat() if record.advance_until else None
        ),
        "pass_count": record.pass_count,
        "payment_count": record.payment_count,
        "state_version": record.state_version,
        "renewal_request_status": record.renewal_request_status,
        "is_overdue": record.is_overdue,
    }


def _portfolio_payload(portfolio: ManagementLoanPortfolio) -> dict[str, object]:
    return {
        "summary": _summary_payload(portfolio.summary),
        "loans": [_loan_payload(record) for record in portfolio.loans],
        "notice": (
            "Loan Management is view-only in mobile. Loan creation, release, "
            "renewal completion, restructuring, and closing remain controlled "
            "SPINA office actions."
        ),
    }


def create_management_loan_router() -> APIRouter:
    router = APIRouter(tags=["management loans"])

    @router.get("/api/v1/management/loans")
    @router.get("/api/mobile/v1/management/loans", include_in_schema=False)
    def list_management_loans(
        q: str = Query(default="", max_length=120),
        loan_status: Literal["active", "paid", "all"] = Query(
            default="active", alias="status"
        ),
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        loans: PostgresManagementLoanRepository = Depends(
            management_loan_repository_dependency
        ),
    ) -> dict[str, object]:
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
                    "message": "Management access is required for Loan Management.",
                },
            )
        portfolio = loans.list_portfolio(
            query=q,
            status=loan_status,
            limit=limit,
            offset=offset,
        )
        return {"success": True, "data": _portfolio_payload(portfolio)}

    return router
