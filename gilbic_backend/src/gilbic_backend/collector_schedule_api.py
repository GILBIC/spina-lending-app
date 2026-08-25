from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .collector_schedule_repository import (
    CollectorScheduleError,
    CollectorScheduleNotFound,
    CollectorScheduleRecord,
    CollectorScheduleRowRecord,
    CollectorScheduleUnavailable,
    PostgresCollectorScheduleRepository,
)
from .request_auth import authenticated_device_context


PHILIPPINES_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Manila")


def collector_schedule_repository_dependency() -> PostgresCollectorScheduleRepository:
    return PostgresCollectorScheduleRepository()


def _row_payload(row: CollectorScheduleRowRecord) -> dict[str, object]:
    return {
        "kind": row.kind,
        "date": row.schedule_date.isoformat(),
        "status": row.status,
        "amount": format(row.amount, "f"),
        "contractual_amount": format(row.contractual_amount, "f"),
        "paid_amount": format(row.paid_amount, "f"),
        "prepaid_amount": format(row.prepaid_amount, "f"),
        "remaining_amount": format(row.remaining_amount, "f"),
        "installment_id": row.installment_id,
        "installment_number": row.installment_number,
        "contractual_due_date": (
            row.contractual_due_date.isoformat()
            if row.contractual_due_date is not None
            else None
        ),
        "principal_component": (
            format(row.principal_component, "f")
            if row.principal_component is not None
            else None
        ),
        "interest_component": (
            format(row.interest_component, "f")
            if row.interest_component is not None
            else None
        ),
        "principal_reduction_amount": format(row.principal_reduction_amount, "f"),
        "past_due_reason_code": row.past_due_reason_code,
        "past_due_reason_note": row.past_due_reason_note,
        "promised_for_date": (
            row.promised_for_date.isoformat()
            if row.promised_for_date is not None
            else None
        ),
        "promise_remaining_amount": format(row.promise_remaining_amount, "f"),
        "promise_status": row.promise_status,
        "no_collection_reason": row.no_collection_reason,
    }


def _schedule_payload(schedule: CollectorScheduleRecord) -> dict[str, object]:
    return {
        "loan_id": str(schedule.loan_id),
        "loan_number": schedule.loan_number,
        "client_id": str(schedule.client_id),
        "client_name": schedule.client_name,
        "loan_type": schedule.loan_type,
        "calculation_mode": schedule.calculation_mode,
        "is_7x7": schedule.calculation_mode == "seven_by_seven",
        "schedule_id": str(schedule.schedule_id),
        "schedule_version": schedule.schedule_version,
        "payment_frequency": schedule.payment_frequency,
        "contract_reference": schedule.contract_reference,
        "as_of_date": schedule.as_of_date.isoformat(),
        "read_only": True,
        "rows": [_row_payload(row) for row in schedule.rows],
    }


def _raise_schedule_error(error: CollectorScheduleError) -> None:
    status = 404 if isinstance(error, CollectorScheduleNotFound) else 409
    if isinstance(error, CollectorScheduleUnavailable):
        status = 409
    raise HTTPException(
        status_code=status,
        detail={"code": error.code, "message": str(error)},
    ) from error


def create_collector_schedule_router() -> APIRouter:
    router = APIRouter(tags=["collector schedules"])

    @router.get("/api/v1/collector/loans/{loan_id}/schedule")
    @router.get(
        "/api/mobile/v1/collector/loans/{loan_id}/schedule",
        include_in_schema=False,
    )
    def view_schedule(
        loan_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        schedules: PostgresCollectorScheduleRepository = Depends(
            collector_schedule_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="route.view",
            permission_error="Collector route permission is required.",
        )
        try:
            schedule = schedules.get_schedule(
                collector_user_id=actor.user_id,
                loan_id=loan_id,
                as_of_date=datetime.now(PHILIPPINES_TIMEZONE).date(),
            )
        except CollectorScheduleError as error:
            _raise_schedule_error(error)
        return {"success": True, "data": _schedule_payload(schedule)}

    return router
