from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from uuid import UUID

from gilbic_backend import collector_route_repository as module
from gilbic_backend.collector_route_repository import PostgresCollectorRouteRepository


COLLECTOR_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
CLIENT_ID = UUID("22222222-2222-4222-8222-222222222222")
LOAN_ID = UUID("33333333-3333-4333-8333-333333333333")


class FakeCursor:
    def __init__(self, rows: list[object]) -> None:
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
        self.area_cursor = FakeCursor([("Cardona",), ("Taytay",)])
        self.entry_cursor = FakeCursor(
            [
                {
                    "route_entry_id": LOAN_ID,
                    "client_id": CLIENT_ID,
                    "loan_id": LOAN_ID,
                    "client_name": "Ana Client",
                    "area": "Cardona",
                    "loan_type": "Regular",
                    "daily_amount": Decimal("200.00"),
                    "remaining_balance": Decimal("4800.00"),
                    "pass_count": 2,
                    "last_payment_date": date(2026, 7, 30),
                    "advance_until": None,
                    "collection_status": "Recorded today",
                    "note": "Morning visit",
                    "state_version": 7,
                    "is_reconciled": True,
                    "mobile_collections_enabled": True,
                    "mobile_balance_mode": "direct_remaining_balance",
                    "processed_today": True,
                    "today_entry_type": "payment",
                    "today_collector_name": "Collector Two",
                }
            ]
        )
        self.calls = 0

    def cursor(self, **kwargs):
        self.calls += 1
        return self.area_cursor if self.calls == 1 else self.entry_cursor


@contextmanager
def fake_open_connection(connection: FakeConnection):
    yield connection


def test_repository_returns_assigned_areas_and_authoritative_state(monkeypatch) -> None:
    connection = FakeConnection()
    monkeypatch.setattr(
        module,
        "open_connection",
        lambda: fake_open_connection(connection),
    )
    route_date = date(2026, 8, 1)

    route = PostgresCollectorRouteRepository().get_today_route(
        collector_user_id=COLLECTOR_USER_ID,
        collector_name="Collector One",
        route_date=route_date,
    )

    assert route.route_date == route_date
    assert route.collector_name == "Collector One"
    assert route.areas == ("Cardona", "Taytay")
    assert route.expected_total == Decimal("200.00")
    assert len(route.entries) == 1
    entry = route.entries[0]
    assert entry.route_entry_id == LOAN_ID
    assert entry.remaining_balance == Decimal("4800.00")
    assert entry.pass_count == 2
    assert entry.status == "Recorded today"
    assert entry.note == "Morning visit"
    assert entry.route_revision == f"loan:{LOAN_ID}:v7"
    assert entry.can_collect_mobile is True
    assert entry.can_enter_payment is True
    assert entry.collection_message == "Today's collection has already been recorded."
    assert entry.processed_today is True
    assert entry.today_entry_type == "payment"
    assert entry.today_collector_name == "Collector Two"

    area_parameters = connection.area_cursor.executions[0][1]
    entry_parameters = connection.entry_cursor.executions[0][1]
    assert area_parameters == (COLLECTOR_USER_ID,)
    assert entry_parameters == (route_date, route_date, COLLECTOR_USER_ID)