from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from uuid import UUID

from gilbic_backend import collector_route_repository as module
from gilbic_backend.collector_route_repository import (
    CollectorRouteEntryRecord,
    PostgresCollectorRouteRepository,
)


COLLECTOR_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_COLLECTOR_USER_ID = UUID("55555555-5555-4555-8555-555555555555")
CLIENT_ID = UUID("22222222-2222-4222-8222-222222222222")
LOAN_ID = UUID("33333333-3333-4333-8333-333333333333")
TRANSACTION_ID = UUID("44444444-4444-4444-8444-444444444444")


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
                    "last_payment_date": date(2026, 8, 1),
                    "advance_until": date(2026, 8, 3),
                    "collection_status": "Recorded today",
                    "note": "Morning visit",
                    "state_version": 7,
                    "is_reconciled": True,
                    "mobile_collections_enabled": True,
                    "mobile_balance_mode": "direct_remaining_balance",
                    "contract_allocation_enabled": False,
                    "contract_schedule_version": 2,
                    "contract_payment_frequency": "weekly",
                    "contract_reference": "CTR-2026-001",
                    "contract_grace_days": 0,
                    "contract_dpd_status": "ready",
                    "contract_days_past_due": 0,
                    "contract_schedule_total": Decimal("5000.00"),
                    "contract_allocated_total": Decimal("200.00"),
                    "contract_automatic_default": False,
                    "contract_ecl_included": False,
                    "contract_ecl_amount": None,
                    "contract_ready_to_post": False,
                    "contract_schedule_verified": True,
                    "contract_today_installment_count": 1,
                    "contract_today_scheduled_amount": Decimal("200.00"),
                    "contract_today_unpaid_amount": Decimal("0.00"),
                    "contract_next_unpaid_date": date(2026, 8, 8),
                    "contract_next_unpaid_amount": Decimal("200.00"),
                    "processed_today": True,
                    "today_entry_type": "advance",
                    "today_collector_name": "Collector One",
                    "today_transaction_id": TRANSACTION_ID,
                    "today_collector_user_id": COLLECTOR_USER_ID,
                    "today_assigned_collector_user_id": COLLECTOR_USER_ID,
                    "today_collection_origin": "assigned_route",
                    "today_is_locked": False,
                    "today_amount": Decimal("600.00"),
                    "today_note": "Selected dates only",
                    "today_covered_dates": (
                        date(2026, 8, 1),
                        date(2026, 8, 3),
                    ),
                    "today_receipts": [],
                    "covered_dates": (
                        date(2026, 8, 1),
                        date(2026, 8, 3),
                    ),
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


def _load_route(monkeypatch, connection: FakeConnection):
    monkeypatch.setattr(
        module,
        "open_connection",
        lambda: fake_open_connection(connection),
    )
    # These tests isolate the established route query and edit-authority behavior.
    # Active-promise lookup has its own focused tests and requires a different
    # cursor shape, so keep it out of this older repository fake rather than
    # weakening the production lookup.
    monkeypatch.setattr(
        PostgresCollectorRouteRepository,
        "_active_promise_summaries",
        staticmethod(lambda connection, *, client_ids: {}),
    )
    return PostgresCollectorRouteRepository().get_today_route(
        collector_user_id=COLLECTOR_USER_ID,
        collector_name="Collector One",
        route_date=date(2026, 8, 1),
    )


def test_repository_returns_assigned_areas_and_authoritative_state(monkeypatch) -> None:
    connection = FakeConnection()
    route_date = date(2026, 8, 1)
    route = _load_route(monkeypatch, connection)

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
    assert entry.contract_schedule_verified is True
    assert entry.contract_payment_frequency == "weekly"
    assert entry.contract_schedule_version == 2
    assert entry.contract_balance_reconciled is True
    assert entry.contract_schedule_ready is True
    assert entry.contract_collection_ready is False
    assert entry.contract_today_scheduled_amount == Decimal("200.00")
    assert entry.contract_today_unpaid_amount == Decimal("0.00")
    assert entry.contract_today_already_covered is True
    assert entry.contract_next_unpaid_date == date(2026, 8, 8)
    assert entry.contract_next_unpaid_amount == Decimal("200.00")
    assert entry.processed_today is True
    assert entry.today_entry_type == "advance"
    assert entry.today_collector_name == "Collector One"
    assert entry.today_transaction_id == TRANSACTION_ID
    assert entry.today_amount == Decimal("600.00")
    assert entry.today_note == "Selected dates only"
    assert entry.today_covered_dates == (
        date(2026, 8, 1),
        date(2026, 8, 3),
    )
    assert entry.can_edit_today is True
    assert entry.today_is_locked is False

    area_parameters = connection.area_cursor.executions[0][1]
    entry_parameters = connection.entry_cursor.executions[0][1]
    assert area_parameters == (COLLECTOR_USER_ID,)
    assert entry_parameters == (
        module.CONTRACT_ALLOCATION_SETTING,
        COLLECTOR_USER_ID,
        route_date,
        route_date,
        route_date,
        route_date,
        COLLECTOR_USER_ID,
    )
    entry_query = connection.entry_cursor.executions[0][0]
    assert "contract_next.effective_due_date as contract_next_unpaid_date" in entry_query
    assert "contract_next.due_date as contract_next_unpaid_date" not in entry_query
    assert "lending.area_path_contains(" in entry_query
    assert "lending.collector_area_owner(coalesce(c.area, '')) = %s" in entry_query
    assert "char_length(lending.normalize_area_path(assignment.area)) desc" in entry_query
    assert "lower(btrim(c.area)) = lower(btrim(a.area))" not in entry_query


def test_assigned_owner_can_edit_latest_unlocked_cross_collector_receipt(monkeypatch) -> None:
    connection = FakeConnection()
    row = connection.entry_cursor.rows[0]
    assert isinstance(row, dict)
    row["today_collector_user_id"] = OTHER_COLLECTOR_USER_ID
    row["today_collector_name"] = "Collector Two"
    row["today_assigned_collector_user_id"] = COLLECTOR_USER_ID
    row["today_collection_origin"] = "cross_collector"
    row["today_is_locked"] = False

    route = _load_route(monkeypatch, connection)

    assert route.entries[0].can_edit_today is True
    assert route.entries[0].today_collector_name == "Collector Two"


def test_assigned_owner_cannot_edit_management_direct_receipt(monkeypatch) -> None:
    connection = FakeConnection()
    row = connection.entry_cursor.rows[0]
    assert isinstance(row, dict)
    row["today_collector_user_id"] = OTHER_COLLECTOR_USER_ID
    row["today_assigned_collector_user_id"] = COLLECTOR_USER_ID
    row["today_collection_origin"] = "management_direct"
    row["today_is_locked"] = False

    route = _load_route(monkeypatch, connection)

    assert route.entries[0].can_edit_today is False


def test_contract_setting_blocks_pay_until_verified_gate_is_ready() -> None:
    entry = CollectorRouteEntryRecord(
        route_entry_id=LOAN_ID,
        client_id=CLIENT_ID,
        loan_id=LOAN_ID,
        client_name="Ana Client",
        area="Cardona",
        loan_type="Regular",
        daily_amount=Decimal("200.00"),
        remaining_balance=Decimal("4800.00"),
        pass_count=0,
        last_payment_date=None,
        advance_until=None,
        status="Pending",
        note="",
        is_reconciled=True,
        mobile_collections_enabled=True,
        mobile_balance_mode="direct_remaining_balance",
        contract_allocation_enabled=True,
        contract_schedule_verified=True,
        contract_dpd_status="ready",
        contract_balance_reconciled=False,
    )

    assert entry.can_collect_mobile is True
    assert entry.can_enter_payment is False
    assert "does not match the operational balance" in entry.collection_message
