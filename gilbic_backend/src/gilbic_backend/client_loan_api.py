from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .client_loan_repository import (
    ClientBorrowerNotLinked,
    ClientLoanPortfolio,
    ClientLoanRecord,
    PostgresClientLoanRepository,
)
from .request_auth import authenticated_device_context


def client_loan_repository_dependency() -> PostgresClientLoanRepository:
    return PostgresClientLoanRepository()


def _decimal(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


def _loan_payload(record: ClientLoanRecord) -> dict[str, object]:
    return {
        "loan_id": str(record.loan_id),
        "loan_number": record.loan_number,
        "loan_type_code": record.loan_type_code,
        "loan_type_name": record.loan_type_name,
        "principal": _decimal(record.principal),
        "daily_amount": _decimal(record.daily_amount),
        "interest_rate": _decimal(record.interest_rate),
        "date_released": (
            record.date_released.isoformat() if record.date_released else None
        ),
        "due_date": record.due_date.isoformat() if record.due_date else None,
        "status": record.status,
        "remaining_balance": _decimal(record.remaining_balance),
        "paid_amount": _decimal(record.paid_amount),
        "pass_count": record.pass_count,
        "last_payment_date": (
            record.last_payment_date.isoformat()
            if record.last_payment_date
            else None
        ),
        "advance_until": (
            record.advance_until.isoformat() if record.advance_until else None
        ),
        "state_version": record.state_version,
        "payment_count": record.payment_count,
    }


def _portfolio_payload(portfolio: ClientLoanPortfolio) -> dict[str, object]:
    return {
        "client": {
            "client_id": str(portfolio.client_id),
            "client_code": portfolio.client_code,
            "client_name": portfolio.client_name,
            "area": portfolio.area,
            "status": portfolio.client_status,
        },
        "loans": [_loan_payload(record) for record in portfolio.loans],
    }


def create_client_loan_router() -> APIRouter:
    router = APIRouter(tags=["client loans"])

    @router.get("/api/v1/client/loans")
    @router.get("/api/mobile/v1/client/loans", include_in_schema=False)
    def list_client_loans(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        loans: PostgresClientLoanRepository = Depends(
            client_loan_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        if "client" not in actor.roles:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "client_role_required",
                    "message": "Only a linked client account can view My Loans.",
                },
            )
        try:
            portfolio = loans.list_for_user(user_id=actor.user_id)
        except ClientBorrowerNotLinked as error:
            raise HTTPException(
                status_code=404,
                detail={"code": error.code, "message": str(error)},
            ) from error
        return {"success": True, "data": _portfolio_payload(portfolio)}

    return router
