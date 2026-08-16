from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from gilbic_backend.collector_route_api import _entry_payload
from gilbic_backend.collector_route_repository import (
    CollectorRouteEntryRecord,
    CollectorRouteReceiptRecord,
)


LOAN_ID = UUID("11111111-1111-4111-8111-111111111111")
CLIENT_ID = UUID("22222222-2222-4222-8222-222222222222")
COLLECTOR_A = UUID("33333333-3333-4333-8333-333333333333")
COLLECTOR_B = UUID("44444444-4444-4444-8444-444444444444")
TX_A = UUID("55555555-5555-4555-8555-555555555555")
TX_B = UUID("66666666-6666-4666-8666-666666666666")


def test_route_entry_payload_exposes_each_same_day_receipt() -> None:
    entry = CollectorRouteEntryRecord(
        route_entry_id=LOAN_ID,
        client_id=CLIENT_ID,
        loan_id=LOAN_ID,
        client_name="Ana Client",
        area="Cardona",
        loan_type="Regular",
        daily_amount=Decimal("200.00"),
        remaining_balance=Decimal("4850.00"),
        pass_count=0,
        last_payment_date=date(2026, 8, 16),
        advance_until=None,
        status="Recorded today",
        note="",
        processed_today=True,
        today_entry_type="payment",
        today_collector_name="Collector B",
        today_transaction_id=TX_B,
        today_collector_user_id=COLLECTOR_B,
        today_amount=Decimal("50.00"),
        today_receipts=(
            CollectorRouteReceiptRecord(
                transaction_id=TX_A,
                receipt_number="R-A100",
                amount=Decimal("100.00"),
                entry_type="payment",
                collector_user_id=COLLECTOR_A,
                collector_name="Collector A",
                is_locked=False,
                covered_dates=(date(2026, 8, 16),),
                accepted_at=datetime(2026, 8, 16, 1, 0, tzinfo=timezone.utc),
            ),
            CollectorRouteReceiptRecord(
                transaction_id=TX_B,
                receipt_number="R-B050",
                amount=Decimal("50.00"),
                entry_type="payment",
                collector_user_id=COLLECTOR_B,
                collector_name="Collector B",
                is_locked=True,
                covered_dates=(date(2026, 8, 16),),
                accepted_at=datetime(2026, 8, 16, 2, 0, tzinfo=timezone.utc),
            ),
        ),
    )

    payload = _entry_payload(entry)

    receipts = payload["today_receipts"]
    assert isinstance(receipts, list)
    assert receipts == [
        {
            "transaction_id": str(TX_A),
            "receipt_number": "R-A100",
            "amount": "100.00",
            "entry_type": "payment",
            "collector_user_id": str(COLLECTOR_A),
            "collector_name": "Collector A",
            "is_locked": False,
            "note": "",
            "covered_dates": ["2026-08-16"],
            "accepted_at": "2026-08-16T01:00:00+00:00",
        },
        {
            "transaction_id": str(TX_B),
            "receipt_number": "R-B050",
            "amount": "50.00",
            "entry_type": "payment",
            "collector_user_id": str(COLLECTOR_B),
            "collector_name": "Collector B",
            "is_locked": True,
            "note": "",
            "covered_dates": ["2026-08-16"],
            "accepted_at": "2026-08-16T02:00:00+00:00",
        },
    ]


def test_route_entry_payload_omits_receipt_history_when_empty() -> None:
    entry = CollectorRouteEntryRecord(
        route_entry_id=LOAN_ID,
        client_id=CLIENT_ID,
        loan_id=LOAN_ID,
        client_name="Ana Client",
        area="Cardona",
        loan_type="Regular",
        daily_amount=Decimal("200.00"),
        remaining_balance=Decimal("5000.00"),
        pass_count=0,
        last_payment_date=None,
        advance_until=None,
        status="Pending",
        note="",
    )

    assert "today_receipts" not in _entry_payload(entry)
