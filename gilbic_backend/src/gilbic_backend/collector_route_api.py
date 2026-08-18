from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .collector_route_cross_status_repository import (
    CollectorRouteCrossStatusRecord,
    PostgresCollectorRouteCrossStatusRepository,
)
from .collector_route_repository import (
    CollectorRouteEntryRecord,
    CollectorRouteReceiptRecord,
    CollectorRouteRecord,
    PostgresCollectorRouteRepository,
)
from .request_auth import authenticated_device_context
from .seven_by_seven_collector_route import (
    SevenBySevenGatedPostgresCollectorRouteRepository,
)


PHILIPPINES_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Manila")


def collector_route_repository_dependency() -> PostgresCollectorRouteRepository:
    return SevenBySevenGatedPostgresCollectorRouteRepository()


def collector_route_cross_status_repository_dependency(
) -> PostgresCollectorRouteCrossStatusRepository:
    return PostgresCollectorRouteCrossStatusRepository()


def _is_seven_by_seven_loan_type(value: str) -> bool:
    normalized = value.lower().replace(" ", "")
    return "7x7" in normalized or "7×7" in normalized


def _receipt_payload(receipt: CollectorRouteReceiptRecord) -> dict[str, object]:
    return {
        "transaction_id": str(receipt.transaction_id),
        "receipt_number": receipt.receipt_number,
        "amount": str(receipt.amount),
        "entry_type": receipt.entry_type,
        "collector_user_id": str(receipt.collector_user_id),
        "collector_name": receipt.collector_name,
        "is_locked": receipt.is_locked,
        "note": receipt.note,
        "covered_dates": [value.isoformat() for value in receipt.covered_dates],
        "accepted_at": receipt.accepted_at.isoformat() if receipt.accepted_at else None,
    }


def _cross_collection_message(
    entry: CollectorRouteEntryRecord,
    status: CollectorRouteCrossStatusRecord,
) -> str:
    recorder = status.recorder_name or entry.today_collector_name or "Collector"
    origin = status.collection_origin.strip().lower()
    if origin == "management_direct":
        return (
            f"Recorded by: {recorder}. This was a direct Management collection; "
            "the assigned Collector route is read-only for this receipt."
        )
    if origin != "cross_collector":
        return (
            f"Recorded by: {recorder}. This receipt was created by another "
            "authorized account and is read-only from this route."
        )

    if status.custody_status == "no_cash":
        if status.remittance_number:
            return (
                f"Recorded by: {recorder}. No cash custody applies to this "
                f"unable-to-pay entry. Remittance {status.remittance_number} is "
                f"{_remittance_state_label(status)}."
            )
        return (
            f"Recorded by: {recorder}. No cash custody applies to this "
            "unable-to-pay entry. It is not yet remitted."
        )

    if status.custody_status == "accepted":
        holder = status.cash_holder_name or status.remittance_recipient_name
        remittance = (
            f" Remittance {status.remittance_number} was accepted."
            if status.remittance_number
            else " Remittance was accepted."
        )
        return (
            f"Recorded by: {recorder}. Cash with: {holder or 'remittance recipient'}."
            f"{remittance}"
        )

    if status.custody_status == "awaiting_acceptance":
        recipient = status.remittance_recipient_name or "the remittance recipient"
        remittance = (
            f"Remittance {status.remittance_number}"
            if status.remittance_number
            else "Remittance"
        )
        return (
            f"Recorded by: {recorder}. Cash with: "
            f"{status.cash_holder_name or recorder}. {remittance} is awaiting "
            f"acceptance by {recipient}."
        )

    return (
        f"Recorded by: {recorder}. Cash with: "
        f"{status.cash_holder_name or recorder}. Not yet remitted."
    )


def _cross_status_suffix(status: CollectorRouteCrossStatusRecord) -> str:
    if status.custody_status == "no_cash":
        return "No cash"
    if status.custody_status == "accepted":
        holder = status.cash_holder_name or status.remittance_recipient_name
        return f"Cash with: {holder or 'recipient'} • Accepted"
    if status.custody_status == "awaiting_acceptance":
        holder = status.cash_holder_name or status.recorder_name or "Collector"
        return f"Cash with: {holder} • Awaiting acceptance"
    holder = status.cash_holder_name or status.recorder_name or "Collector"
    return f"Cash with: {holder} • Not yet remitted"


def _remittance_state_label(status: CollectorRouteCrossStatusRecord) -> str:
    if status.custody_status == "accepted":
        return "accepted"
    if status.custody_status == "awaiting_acceptance":
        return "awaiting acceptance"
    return "not yet remitted"


def _entry_payload(
    entry: CollectorRouteEntryRecord,
    *,
    route_owner_user_id: UUID | None = None,
    cross_status: CollectorRouteCrossStatusRecord | None = None,
) -> dict[str, object]:
    seven_by_seven_mobile_enabled = (
        _is_seven_by_seven_loan_type(entry.loan_type)
        and entry.can_collect_mobile
        and entry.can_enter_payment
    )
    recorded_by_other = (
        route_owner_user_id is not None
        and entry.processed_today
        and entry.today_collector_user_id is not None
        and entry.today_collector_user_id != route_owner_user_id
    )
    display_status = entry.status
    collection_message = entry.collection_message
    if recorded_by_other:
        display_status = (
            f"{entry.status} • Recorded by: "
            f"{entry.today_collector_name or 'another authorized collector'}"
        )
        if cross_status is not None:
            display_status = f"{display_status} • {_cross_status_suffix(cross_status)}"
            collection_message = _cross_collection_message(entry, cross_status)
        else:
            collection_message = (
                f"Recorded by: {entry.today_collector_name or 'another authorized account'}. "
                "This receipt is read-only from the assigned Collector route."
            )

    payload: dict[str, object] = {
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
        "covered_dates": [value.isoformat() for value in entry.covered_dates],
        "status": display_status,
        "note": entry.note,
        "route_revision": entry.route_revision,
        "can_collect_mobile": entry.can_collect_mobile,
        "can_enter_payment": entry.can_enter_payment,
        "seven_by_seven_mobile_enabled": seven_by_seven_mobile_enabled,
        "collection_message": collection_message,
        "contract_allocation_enabled": entry.contract_allocation_enabled,
        "contract_schedule_verified": entry.contract_schedule_verified,
        "contract_dpd_status": entry.contract_dpd_status,
        "contract_payment_frequency": entry.contract_payment_frequency,
        "contract_reference": entry.contract_reference,
        "contract_schedule_version": entry.contract_schedule_version,
        "contract_grace_days": entry.contract_grace_days,
        "contract_balance_reconciled": entry.contract_balance_reconciled,
        "contract_schedule_ready": entry.contract_schedule_ready,
        "contract_collection_ready": entry.contract_collection_ready,
        "contract_days_past_due": entry.contract_days_past_due,
        "contract_today_scheduled_amount": str(entry.contract_today_scheduled_amount),
        "contract_today_unpaid_amount": str(entry.contract_today_unpaid_amount),
        "contract_today_already_covered": entry.contract_today_already_covered,
        "contract_next_unpaid_date": (
            entry.contract_next_unpaid_date.isoformat()
            if entry.contract_next_unpaid_date
            else None
        ),
        "contract_next_unpaid_amount": str(entry.contract_next_unpaid_amount),
        "contract_readiness_message": entry.contract_readiness_message,
        "processed_today": entry.processed_today,
        "today_entry_type": entry.today_entry_type,
        "today_collector_name": entry.today_collector_name,
        "today_transaction_id": (
            str(entry.today_transaction_id) if entry.today_transaction_id else None
        ),
        "today_is_locked": entry.today_is_locked,
        "can_edit_today": (
            entry.can_edit_today
            if route_owner_user_id is None
            else (
                entry.can_edit_today
                and entry.today_collector_user_id == route_owner_user_id
            )
        ),
        "today_amount": str(entry.today_amount),
        "today_note": entry.today_note,
        "today_covered_dates": [
            value.isoformat() for value in entry.today_covered_dates
        ],
    }
    if recorded_by_other:
        payload.update(
            {
                "today_collector_user_id": str(entry.today_collector_user_id),
                "today_recorded_by_other_user": True,
                "today_collection_origin": (
                    cross_status.collection_origin if cross_status else ""
                ),
                "today_custody_status": (
                    cross_status.custody_status if cross_status else ""
                ),
                "today_cash_holder_name": (
                    cross_status.cash_holder_name if cross_status else ""
                ),
                "today_remittance_number": (
                    cross_status.remittance_number if cross_status else ""
                ),
                "today_remittance_recipient_name": (
                    cross_status.remittance_recipient_name if cross_status else ""
                ),
            }
        )
    if entry.today_receipts:
        payload["today_receipts"] = [
            _receipt_payload(receipt) for receipt in entry.today_receipts
        ]
    return payload


def _route_payload(
    route: CollectorRouteRecord,
    *,
    route_owner_user_id: UUID,
    cross_statuses: dict[UUID, CollectorRouteCrossStatusRecord],
) -> dict[str, object]:
    return {
        "route_date": route.route_date.isoformat(),
        "collector_name": route.collector_name,
        "areas": list(route.areas),
        "expected_total": str(route.expected_total),
        "entries": [
            _entry_payload(
                entry,
                route_owner_user_id=route_owner_user_id,
                cross_status=(
                    cross_statuses.get(entry.today_transaction_id)
                    if entry.today_transaction_id
                    else None
                ),
            )
            for entry in route.entries
        ],
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
        cross_statuses: PostgresCollectorRouteCrossStatusRepository = Depends(
            collector_route_cross_status_repository_dependency
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
        transaction_ids = tuple(
            entry.today_transaction_id
            for entry in route.entries
            if entry.today_transaction_id is not None
            and entry.today_collector_user_id is not None
            and entry.today_collector_user_id != actor.user_id
        )
        status_by_transaction = (
            cross_statuses.get_for_transactions(transaction_ids=transaction_ids)
            if transaction_ids
            else {}
        )
        return {
            "success": True,
            "data": _route_payload(
                route,
                route_owner_user_id=actor.user_id,
                cross_statuses=status_by_transaction,
            ),
        }

    return router
