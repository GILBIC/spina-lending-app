from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Header, Query

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .other_area_repository import OtherAreaLoanRecord, PostgresOtherAreaRepository
from .request_auth import authenticated_device_context


def other_area_repository_dependency() -> PostgresOtherAreaRepository:
    return PostgresOtherAreaRepository()


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def _payload(record: OtherAreaLoanRecord) -> dict[str, object]:
    return {
        "route_entry_id": str(record.route_entry_id),
        "client_id": str(record.client_id),
        "loan_id": str(record.loan_id),
        "client_name": record.client_name,
        "client_code": record.client_code,
        "phone_number": record.phone_number,
        "area": record.area,
        "loan_type": record.loan_type,
        "daily_amount": _money(record.daily_amount),
        "remaining_balance": _money(record.remaining_balance),
        "pass_count": record.pass_count,
        "status": record.status,
        "route_revision": record.route_revision,
        "can_collect_mobile": record.can_collect_mobile,
        "can_enter_payment": record.can_enter_payment,
        "collection_message": record.collection_message,
        "assigned_collector_user_id": (
            str(record.assigned_collector_user_id)
            if record.assigned_collector_user_id
            else None
        ),
        "assigned_collector_name": record.assigned_collector_name,
        "is_other_area": True,
    }


def create_other_area_router() -> APIRouter:
    router = APIRouter(tags=["other area collections"])

    @router.get("/api/v1/collector/other-area-clients/search")
    @router.get(
        "/api/mobile/v1/collector/other-area-clients/search",
        include_in_schema=False,
    )
    def search_other_area_clients(
        q: str = Query(min_length=2, max_length=120),
        limit: int = Query(default=25, ge=1, le=50),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        other_areas: PostgresOtherAreaRepository = Depends(
            other_area_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="collection.create",
            permission_error="Collection permission is required.",
        )
        records = other_areas.search(
            collector_user_id=actor.user_id,
            query=q,
            limit=limit,
        )
        return {
            "success": True,
            "data": [_payload(record) for record in records],
        }

    return router
