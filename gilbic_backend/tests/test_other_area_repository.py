from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
from uuid import UUID

from gilbic_backend import other_area_repository as module
from gilbic_backend.other_area_repository import PostgresOtherAreaRepository


COLLECTOR_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
RECORDER_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
ASSIGNED_COLLECTOR_USER_ID = UUID("33333333-3333-4333-8333-333333333333")
CLIENT_ID = UUID("44444444-4444-4444-8444-444444444444")
LOAN_ID = UUID("55555555-5555-4555-8555-555555555555")


class FakeCursor:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.executions: list[tuple[str, tuple[object, ...]]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def execute(self, query: str, parameters: tuple[object, ...]) -> None:
        self.executions.append((query, parameters))

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = FakeCursor(
            [
                {
                    "route_entry_id": LOAN_ID,
                    "client_id": CLIENT_ID,
                    "loan_id": LOAN_ID,
                    "client_name": "Ana Client",
                    "client_code": "C-1001",
                    "phone_number": "09170000000",
                    "area": "CARDONA › LOOC",
                    "loan_type": "Regular",
                    "calculation_mode": "regular",
                    "daily_amount": Decimal("200.00"),
                    "remaining_balance": Decimal("4800.00"),
                    "pass_count": 0,
                    "collection_status": "Recorded today",
                    "state_version": 4,
                    "is_reconciled": True,
                    "mobile_collections_enabled": True,
                    "mobile_seven_by_seven_enabled": False,
                    "mobile_balance_mode": "direct_remaining_balance",
                    "assigned_collector_user_id": ASSIGNED_COLLECTOR_USER_ID,
                    "assigned_collector_name": "Collector Two",
                    "processed_today": True,
                    "today_entry_type": "payment",
                    "today_collector_user_id": RECORDER_USER_ID,
                    "today_collector_name": "Collector Three",
                    "today_amount": Decimal("200.00"),
                    "today_is_locked": False,
                }
            ]
        )

    def cursor(self, **kwargs):
        return self.cursor_instance


@contextmanager
def fake_open_connection(connection: FakeConnection):
    yield connection


def test_search_returns_latest_same_day_collection_status(monkeypatch) -> None:
    connection = FakeConnection()
    monkeypatch.setattr(
        module,
        "open_connection",
        lambda: fake_open_connection(connection),
    )

    records = PostgresOtherAreaRepository().search(
        collector_user_id=COLLECTOR_USER_ID,
        query="Ana",
        limit=25,
    )

    assert len(records) == 1
    record = records[0]
    assert record.status == "Recorded today"
    assert record.processed_today is True
    assert record.today_entry_type == "payment"
    assert record.today_collector_user_id == RECORDER_USER_ID
    assert record.today_collector_name == "Collector Three"
    assert record.today_amount == Decimal("200.00")
    assert record.today_is_locked is False
    assert record.can_enter_payment is False
    assert record.collection_message == "Already recorded today by Collector Three."

    query, parameters = connection.cursor_instance.executions[0]
    assert "left join lateral (" in query
    assert "from lending.collection_transactions transaction" in query
    assert (
        "(current_timestamp at time zone 'Asia/Manila')::date"
        in query
    )
    assert "and transaction.is_voided = false" in query
    assert "order by transaction.accepted_at desc, transaction.id desc" in query
    assert "today.entry_type is not null as processed_today" in query
    assert parameters == (
        COLLECTOR_USER_ID,
        "%Ana%",
        "%Ana%",
        "%Ana%",
        "%Ana%",
        25,
    )
