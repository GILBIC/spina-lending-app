from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from gilbic_backend.collector_route_api import _entry_payload
from gilbic_backend.collector_route_cross_status_repository import (
    CollectorRouteCrossStatusRecord,
)
from gilbic_backend.collector_route_repository import CollectorRouteEntryRecord


OWNER = UUID("11111111-1111-4111-8111-111111111111")
VISITOR = UUID("22222222-2222-4222-8222-222222222222")
TX = UUID("33333333-3333-4333-8333-333333333333")
LOAN = UUID("44444444-4444-4444-8444-444444444444")
CLIENT = UUID("55555555-5555-4555-8555-555555555555")


def _entry(*, recorder: UUID) -> CollectorRouteEntryRecord:
    return CollectorRouteEntryRecord(
        route_entry_id=LOAN,
        client_id=CLIENT,
        loan_id=LOAN,
        client_name="Ana Client",
        area="CARDONA › LOOC",
        loan_type="Regular",
        daily_amount=Decimal("50.00"),
        remaining_balance=Decimal("4900.00"),
        pass_count=0,
        last_payment_date=None,
        advance_until=None,
        status="Recorded today",
        note="",
        is_reconciled=True,
        mobile_collections_enabled=True,
        mobile_balance_mode="direct_remaining_balance",
        processed_today=True,
        today_entry_type="payment",
        today_collector_name="Visiting Collector" if recorder == VISITOR else "Owner Collector",
        today_transaction_id=TX,
        today_collector_user_id=recorder,
        today_is_locked=True,
        can_edit_today=True,
        today_amount=Decimal("50.00"),
    )


def _status(custody: str) -> CollectorRouteCrossStatusRecord:
    return CollectorRouteCrossStatusRecord(
        transaction_id=TX,
        collection_origin="cross_collector",
        recorder_user_id=VISITOR,
        recorder_name="Visiting Collector",
        assigned_collector_user_id=OWNER,
        remittance_number=("REM-18" if custody != "not_remitted" else ""),
        remittance_status=("received" if custody == "accepted" else "submitted"),
        remittance_recipient_name="Owner Collector",
        custody_status=custody,
        cash_holder_name=("Owner Collector" if custody == "accepted" else "Visiting Collector"),
    )


def test_assigned_route_shows_visiting_recorder_and_pending_cash_custody() -> None:
    payload = _entry_payload(
        _entry(recorder=VISITOR),
        route_owner_user_id=OWNER,
        cross_status=_status("awaiting_acceptance"),
    )

    assert payload["today_recorded_by_other_user"] is True
    assert payload["can_edit_today"] is False
    assert "Recorded by: Visiting Collector" in str(payload["status"])
    assert "Cash with: Visiting Collector" in str(payload["status"])
    assert "Awaiting acceptance" in str(payload["status"])
    assert payload["today_remittance_number"] == "REM-18"
    assert payload["today_cash_holder_name"] == "Visiting Collector"


def test_assigned_route_shows_custody_transfer_only_after_acceptance() -> None:
    payload = _entry_payload(
        _entry(recorder=VISITOR),
        route_owner_user_id=OWNER,
        cross_status=_status("accepted"),
    )

    assert "Cash with: Owner Collector" in str(payload["status"])
    assert "Accepted" in str(payload["status"])
    assert payload["today_custody_status"] == "accepted"


def test_owners_own_receipt_keeps_normal_status_and_correction_flag() -> None:
    payload = _entry_payload(
        _entry(recorder=OWNER),
        route_owner_user_id=OWNER,
        cross_status=None,
    )

    assert "today_recorded_by_other_user" not in payload
    assert payload["status"] == "Recorded today"
    assert payload["can_edit_today"] is True
