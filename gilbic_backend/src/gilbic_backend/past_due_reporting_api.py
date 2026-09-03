from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .past_due_reporting_repository import (
    PastDueReasonReportRow,
    PostgresPastDueReportingRepository,
)
from .request_auth import authenticated_device_context


REASON_LABELS = {
    "no_cash": "No cash",
    "client_absent": "Client absent",
    "business_slow": "Business slow",
    "sick_hospital": "Sick/Hospital",
    "emergency": "Emergency",
    "promised_to_pay_later": "Promised to pay later",
    "other": "Other",
}
EVENT_KIND_LABELS = {
    "unable_to_pay": "Full Unable to Pay",
    "partial_payment": "Partial-payment Past Due",
}


def past_due_reporting_repository_dependency() -> PostgresPastDueReportingRepository:
    return PostgresPastDueReportingRepository()


def _row_payload(row: PastDueReasonReportRow) -> dict[str, object]:
    return {
        "client_id": str(row.client_id),
        "client_name": row.client_name,
        "collector_user_id": str(row.collector_user_id),
        "collector_name": row.collector_name,
        "area": row.area,
        "reason_code": row.reason_code,
        "reason_label": REASON_LABELS.get(row.reason_code, row.reason_code),
        "event_kind": row.event_kind,
        "event_kind_label": EVENT_KIND_LABELS.get(row.event_kind, row.event_kind),
        "event_count": row.event_count,
        "total_past_due_amount": str(row.total_past_due_amount),
        "remaining_past_due_amount": str(row.remaining_past_due_amount),
    }


def create_past_due_reporting_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/management/past-due", tags=["management"])

    @router.get("/reasons")
    def reason_report(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        start_date: date | None = Query(default=None),
        end_date: date | None = Query(default=None),
        client_id: UUID | None = Query(default=None),
        collector_user_id: UUID | None = Query(default=None),
        area: str | None = Query(default=None, max_length=200),
        reason_code: str | None = Query(default=None, max_length=80),
        event_kind: str | None = Query(default=None, max_length=80),
        limit: int = Query(default=500, ge=1, le=500),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        reports: PostgresPastDueReportingRepository = Depends(
            past_due_reporting_repository_dependency
        ),
    ) -> dict[str, object]:
        authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="management.dashboard.view",
            permission_error="Management permission is required.",
        )
        try:
            report = reports.report_reason_summary(
                start_date=start_date,
                end_date=end_date,
                client_id=client_id,
                collector_user_id=collector_user_id,
                area=area,
                reason_code=reason_code,
                event_kind=event_kind,
                limit=limit,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        total_events = sum(row.event_count for row in report.rows)
        total_amount = sum(
            (row.total_past_due_amount for row in report.rows),
            start=Decimal("0.00"),
        )
        remaining_amount = sum(
            (row.remaining_past_due_amount for row in report.rows),
            start=Decimal("0.00"),
        )
        return {
            "success": True,
            "data": {
                "schema_available": report.schema_available,
                "summary": {
                    "event_count": total_events,
                    "total_past_due_amount": str(total_amount),
                    "remaining_past_due_amount": str(remaining_amount),
                },
                "rows": [_row_payload(row) for row in report.rows],
            },
        }

    return router
