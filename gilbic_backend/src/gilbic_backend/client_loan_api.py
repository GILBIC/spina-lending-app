from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

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
from .collector_schedule_repository import (
    CollectorScheduleRecord,
    CollectorScheduleRowRecord,
)
from .request_auth import authenticated_device_context


PHILIPPINES_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Manila")


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


def _client_schedule_row_payload(
    row: CollectorScheduleRowRecord,
) -> dict[str, object]:
    details: dict[str, object] = {
        "remaining_amount": format(row.remaining_amount, "f")
    }
    if row.no_collection_reason:
        details["note"] = row.no_collection_reason
    elif row.past_due_reason_note:
        details["note"] = row.past_due_reason_note
    return {
        "payment_date": row.schedule_date.isoformat(),
        "amount": format(row.amount, "f"),
        "status": row.status,
        "details": details,
    }


def _client_schedule_payload(
    schedule: CollectorScheduleRecord,
) -> dict[str, object]:
    return {
        "loan_id": str(schedule.loan_id),
        "loan_number": schedule.loan_number,
        "loan_type": schedule.loan_type,
        "calculation_mode": schedule.calculation_mode,
        "is_7x7": schedule.calculation_mode == "seven_by_seven",
        "payment_frequency": schedule.payment_frequency,
        "read_only": True,
        "past_due_amount": format(schedule.past_due_amount, "f"),
        "past_due_count": schedule.past_due_count,
        "schedule_extension_slots": schedule.schedule_extension_slots,
        "contractual_maturity": (
            schedule.base_maturity.isoformat()
            if schedule.base_maturity is not None
            else None
        ),
        "operational_maturity": (
            schedule.updated_maturity.isoformat()
            if schedule.updated_maturity is not None
            else None
        ),
        "maturity_status": schedule.maturity_projection_status,
        "rows": [_client_schedule_row_payload(row) for row in schedule.rows],
    }


def _client_actor(
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
    if "client" not in actor.roles:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "client_role_required",
                "message": "Only a linked client account can view My Loans.",
            },
        )
    return actor


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
        actor = _client_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        try:
            portfolio = loans.list_for_user(user_id=actor.user_id)
        except ClientBorrowerNotLinked as error:
            raise HTTPException(
                status_code=404,
                detail={"code": error.code, "message": str(error)},
            ) from error
        return {"success": True, "data": _portfolio_payload(portfolio)}

    @router.get("/api/v1/client/loans/{loan_id}/schedule")
    @router.get(
        "/api/mobile/v1/client/loans/{loan_id}/schedule",
        include_in_schema=False,
    )
    def view_client_schedule(
        loan_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        loans: PostgresClientLoanRepository = Depends(
            client_loan_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _client_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        try:
            schedule = loans.get_schedule_for_user(
                user_id=actor.user_id,
                loan_id=loan_id,
                as_of_date=datetime.now(PHILIPPINES_TIMEZONE).date(),
            )
        except ClientBorrowerNotLinked as error:
            raise HTTPException(
                status_code=404,
                detail={"code": error.code, "message": str(error)},
            ) from error
        return {"success": True, "data": _client_schedule_payload(schedule)}

    return router
