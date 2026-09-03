from datetime import date
from decimal import Decimal
from uuid import UUID

from gilbic_backend.collector_route_repository import (
    CollectorRouteEntryRecord,
    PostgresCollectorRouteRepository,
)


CLIENT_ID = UUID("11111111-1111-4111-8111-111111111111")
LOAN_ID = UUID("22222222-2222-4222-8222-222222222222")


def _entry(**overrides):
    values = {
        "route_entry_id": LOAN_ID,
        "client_id": CLIENT_ID,
        "loan_id": LOAN_ID,
        "client_name": "Promise Client",
        "area": "Area 1",
        "loan_type": "Regular",
        "daily_amount": Decimal("100.00"),
        "remaining_balance": Decimal("1000.00"),
        "pass_count": 1,
        "last_payment_date": None,
        "advance_until": None,
        "status": "Missed payment",
        "note": "",
        "is_reconciled": True,
        "mobile_collections_enabled": True,
        "mobile_balance_mode": "direct_remaining_balance",
    }
    values.update(overrides)
    return CollectorRouteEntryRecord(**values)


def test_active_pending_promise_is_shown_as_compact_route_reminder() -> None:
    entry = _entry(
        active_promise_date=date(2026, 8, 28),
        active_promise_remaining_amount=Decimal("200.00"),
        active_promise_status="pending",
    )

    assert entry.active_promise_message == (
        "Promise: 2026-08-28 · ₱200.00 remaining · Pending."
    )
    assert entry.collection_message.endswith(entry.active_promise_message)


def test_route_message_has_no_promise_text_when_client_has_no_active_promise() -> None:
    entry = _entry()

    assert entry.active_promise_message == ""
    assert "Promise:" not in entry.collection_message


class _MissingPromiseTableCursor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, statement, parameters=None):
        assert "to_regclass" in statement
        assert parameters is None
        return self

    def fetchone(self):
        return (None,)


class _MissingPromiseTableConnection:
    def cursor(self, **kwargs):
        assert kwargs == {}
        return _MissingPromiseTableCursor()


def test_route_reminder_is_schema_safe_before_0103_is_installed() -> None:
    summaries = PostgresCollectorRouteRepository._active_promise_summaries(
        _MissingPromiseTableConnection(),
        client_ids=(CLIENT_ID,),
    )

    assert summaries == {}
