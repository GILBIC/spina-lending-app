from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .collector_route_repository import (
    CollectorRouteEntryRecord,
    CollectorRouteRecord,
    PostgresCollectorRouteRepository,
)
from .request_auth import authenticated_device_context


PHILIPPINES_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Manila")


def collector_route_repository_dependency() -> PostgresCollectorRouteRepository:
    return PostgresCollectorRouteRepository()


def _entry_payload(entry: CollectorRouteEntryRecord) -> dict[str, object]:
    return {
        "route_entry_id": str(entry.route_entry_id),
        "client_id": str(entry.client_id),
        "loan_id": str(entry.loan_id),
        "client_name": entry.client_name,
        "area": entry.area,
        "loan_type": entry.loan_type,
        "daily_amount": str(entry.daily_amount),
        "remaining_balance": str(entry.remaining_balance),
        "pass_count": entry.pass_count,
        "last_payment_date": (
            entry.last_payment_date.isoformat() if entry.last_payment_date else None
        ),
        "advance_until": entry.advance_until.isoformat() if entry.advance_until else None,
        "status": entry.status,
        "note": entry.note,
        "route_revision": entry.route_revision,
        "can_collect_mobile": entry.can_collect_mobile,
        "can_enter_payment": entry.can_enter_payment,
        "collection_message": entry.collection_message,
        "processed_today": entry.processed_today,
        "today_entry_type": entry.today_entry_type,
        "today_collector_name": entry.today_collector_name,
    }


def _route_payload(route: CollectorRouteRecord) -> dict[str, object]:
    return {
        "route_date": route.route_date.isoformat(),
        "collector_name": route.collector_name,
        "areas": list(route.areas),
        "expected_total": str(route.expected_total),
        "entries": [_entry_payload(entry) for entry in route.entries],
    }


def create_collector_route_router() -> APIRouter:
    router = APIRouter(tags=["collector routes"])

    @router.get("/api/v1/collector/routes/today")
    @router.get(
        "/api/mobile/v1/collector/routes/today",
        include_in_schema=False,
    )
    def today_route(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        routes: PostgresCollectorRouteRepository = Depends(
            collector_route_repository_dependency
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
        route = routes.get_today_route(
            collector_user_id=actor.user_id,
            collector_name=actor.full_name,
            route_date=datetime.now(PHILIPPINES_TIMEZONE).date(),
        )
        return {"success": True, "data": _route_payload(route)}

    return router