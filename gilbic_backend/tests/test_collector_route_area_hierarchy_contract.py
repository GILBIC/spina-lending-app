from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

from gilbic_backend import collector_route_repository as repository_module
from gilbic_backend.collector_route_api import _route_payload
from gilbic_backend.collector_route_repository import (
    CollectorRouteEntryRecord,
    CollectorRouteRecord,
    PostgresCollectorRouteRepository,
)


COLLECTOR_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
CLIENT_ID = UUID("22222222-2222-4222-8222-222222222222")
LOAN_ID = UUID("33333333-3333-4333-8333-333333333333")
CARDONA_AREA_UID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1")
CALAHAN_AREA_UID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2")
BALAYONG_AREA_UID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3")
MABINI_AREA_UID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa4")
AGUHO_AREA_UID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa5")
NIA_AREA_UID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa6")


def _route_row(*, area_uid: UUID = MABINI_AREA_UID) -> dict[str, object]:
    return {
        "route_entry_id": LOAN_ID,
        "client_id": CLIENT_ID,
        "loan_id": LOAN_ID,
        "client_name": "Ana Client",
        "area": "Cardona › Calahan › Balayong › Mabini St.",
        "area_uid": area_uid,
        "loan_type": "Regular",
        "daily_amount": Decimal("200.00"),
        "remaining_balance": Decimal("4800.00"),
        "pass_count": 0,
        "last_payment_date": None,
        "advance_until": None,
        "collection_status": "Pending",
        "note": "",
        "state_version": 3,
        "is_reconciled": True,
        "mobile_collections_enabled": True,
        "mobile_balance_mode": "direct_remaining_balance",
        "contract_allocation_enabled": False,
        "contract_schedule_version": None,
        "contract_payment_frequency": "",
        "contract_reference": "",
        "contract_grace_days": 0,
        "contract_dpd_status": "contract_schedule_required",
        "contract_days_past_due": None,
        "contract_schedule_total": Decimal("0.00"),
        "contract_allocated_total": Decimal("0.00"),
        "contract_automatic_default": False,
        "contract_ecl_included": False,
        "contract_ecl_amount": None,
        "contract_ready_to_post": False,
        "contract_schedule_verified": False,
        "contract_today_installment_count": 0,
        "contract_today_scheduled_amount": Decimal("0.00"),
        "contract_today_unpaid_amount": Decimal("0.00"),
        "contract_next_unpaid_date": None,
        "contract_next_unpaid_amount": Decimal("0.00"),
        "processed_today": False,
        "today_entry_type": "",
        "today_collector_name": "",
        "today_transaction_id": None,
        "today_collector_user_id": None,
        "today_assigned_collector_user_id": None,
        "today_collection_origin": "",
        "today_is_locked": False,
        "today_amount": Decimal("0.00"),
        "today_note": "",
        "today_covered_dates": (),
        "today_receipts": [],
        "covered_dates": (),
    }


AREA_NODE_ROWS = [
    {
        "area_uid": CARDONA_AREA_UID,
        "parent_area_uid": None,
        "name": "Cardona",
        "full_path": "Cardona",
        "depth": 0,
        "sort_order": 0,
        "is_legacy_unmapped": False,
    },
    {
        "area_uid": CALAHAN_AREA_UID,
        "parent_area_uid": CARDONA_AREA_UID,
        "name": "Calahan",
        "full_path": "Cardona › Calahan",
        "depth": 1,
        "sort_order": 0,
        "is_legacy_unmapped": False,
    },
    {
        "area_uid": BALAYONG_AREA_UID,
        "parent_area_uid": CALAHAN_AREA_UID,
        "name": "Balayong",
        "full_path": "Cardona › Calahan › Balayong",
        "depth": 2,
        "sort_order": 0,
        "is_legacy_unmapped": False,
    },
    {
        "area_uid": MABINI_AREA_UID,
        "parent_area_uid": BALAYONG_AREA_UID,
        "name": "Mabini St.",
        "full_path": "Cardona › Calahan › Balayong › Mabini St.",
        "depth": 3,
        "sort_order": 0,
        "is_legacy_unmapped": False,
    },
    {
        "area_uid": AGUHO_AREA_UID,
        "parent_area_uid": CALAHAN_AREA_UID,
        "name": "Aguho",
        "full_path": "Cardona › Calahan › Aguho",
        "depth": 2,
        "sort_order": 1,
        "is_legacy_unmapped": False,
    },
]


class HierarchyCursor:
    def __init__(self, connection: "HierarchyConnection") -> None:
        self.connection = connection
        self.rows: list[object] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def execute(
        self,
        query: str,
        parameters: tuple[object, ...] = (),
    ) -> None:
        self.connection.executions.append((query, parameters))
        if "from lending.clients c" in query:
            self.rows = [_route_row()]
        elif (
            "from lending.collector_area_assignments" in query
            and "select area" in query
        ):
            self.rows = [("Cardona › Calahan",)]
        elif "lending.area_nodes" in query:
            # Deliberately non-alphabetic sibling order: Balayong before Aguho.
            # NIA belongs to another Collector and is intentionally absent.
            self.rows = list(AREA_NODE_ROWS)
        else:
            self.rows = []

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class HierarchyConnection:
    def __init__(self) -> None:
        self.executions: list[tuple[str, tuple[object, ...]]] = []

    def cursor(self, **kwargs):
        return HierarchyCursor(self)


@contextmanager
def _open_hierarchy_connection(connection: HierarchyConnection):
    yield connection


def test_repository_returns_ordered_route_area_nodes_and_entry_area_uid(monkeypatch) -> None:
    connection = HierarchyConnection()
    monkeypatch.setattr(
        repository_module,
        "open_connection",
        lambda: _open_hierarchy_connection(connection),
    )
    monkeypatch.setattr(
        repository_module,
        "apply_due_client_area_transfers",
        lambda *args, **kwargs: 0,
    )
    monkeypatch.setattr(
        PostgresCollectorRouteRepository,
        "_active_promise_summaries",
        staticmethod(lambda connection, *, client_ids: {}),
    )

    route = PostgresCollectorRouteRepository().get_today_route(
        collector_user_id=COLLECTOR_USER_ID,
        collector_name="Collector One",
        route_date=date(2026, 9, 9),
    )

    # Legacy route fields stay available while stable hierarchy metadata is added.
    assert route.areas == ("Cardona › Calahan",)
    assert route.entries[0].area == "Cardona › Calahan › Balayong › Mabini St."

    assert route.entries[0].area_uid == MABINI_AREA_UID
    assert [node.area_uid for node in route.area_nodes] == [
        CARDONA_AREA_UID,
        CALAHAN_AREA_UID,
        BALAYONG_AREA_UID,
        MABINI_AREA_UID,
        AGUHO_AREA_UID,
    ]
    assert [node.name for node in route.area_nodes] == [
        "Cardona",
        "Calahan",
        "Balayong",
        "Mabini St.",
        "Aguho",
    ]
    assert NIA_AREA_UID not in {node.area_uid for node in route.area_nodes}

    all_queries = "\n".join(query for query, _ in connection.executions)
    assert "lending.collector_area_owner" in all_queries
    assert "lending.area_nodes" in all_queries


def _base_entry() -> CollectorRouteEntryRecord:
    return CollectorRouteEntryRecord(
        route_entry_id=LOAN_ID,
        client_id=CLIENT_ID,
        loan_id=LOAN_ID,
        client_name="Ana Client",
        area="Cardona › Calahan › Balayong",
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
    )


class EntryWithAreaUid:
    def __init__(self, entry: CollectorRouteEntryRecord, area_uid: UUID) -> None:
        self._entry = entry
        self.area_uid = area_uid

    def __getattr__(self, name: str):
        return getattr(self._entry, name)


class RouteWithAreaNodes:
    def __init__(self, route: CollectorRouteRecord) -> None:
        self._route = route
        self.area_nodes = (
            SimpleNamespace(
                area_uid=CARDONA_AREA_UID,
                parent_area_uid=None,
                name="Cardona",
                full_path="Cardona",
                depth=0,
                sort_order=0,
                is_legacy_unmapped=False,
            ),
            SimpleNamespace(
                area_uid=CALAHAN_AREA_UID,
                parent_area_uid=CARDONA_AREA_UID,
                name="Calahan",
                full_path="Cardona › Calahan",
                depth=1,
                sort_order=0,
                is_legacy_unmapped=False,
            ),
            SimpleNamespace(
                area_uid=BALAYONG_AREA_UID,
                parent_area_uid=CALAHAN_AREA_UID,
                name="Balayong",
                full_path="Cardona › Calahan › Balayong",
                depth=2,
                sort_order=0,
                is_legacy_unmapped=False,
            ),
        )

    def __getattr__(self, name: str):
        return getattr(self._route, name)


def test_route_payload_exposes_area_nodes_and_per_entry_stable_area_uid() -> None:
    entry = EntryWithAreaUid(_base_entry(), BALAYONG_AREA_UID)
    route = RouteWithAreaNodes(
        CollectorRouteRecord(
            route_date=date(2026, 9, 9),
            collector_name="Collector One",
            areas=("Cardona › Calahan",),
            entries=(entry,),
        )
    )

    payload = _route_payload(
        route,
        route_owner_user_id=COLLECTOR_USER_ID,
        cross_statuses={},
        renewals_by_client={},
    )

    assert payload["area_nodes"] == [
        {
            "area_uid": str(CARDONA_AREA_UID),
            "parent_area_uid": None,
            "name": "Cardona",
            "full_path": "Cardona",
            "depth": 0,
            "sort_order": 0,
            "is_legacy_unmapped": False,
        },
        {
            "area_uid": str(CALAHAN_AREA_UID),
            "parent_area_uid": str(CARDONA_AREA_UID),
            "name": "Calahan",
            "full_path": "Cardona › Calahan",
            "depth": 1,
            "sort_order": 0,
            "is_legacy_unmapped": False,
        },
        {
            "area_uid": str(BALAYONG_AREA_UID),
            "parent_area_uid": str(CALAHAN_AREA_UID),
            "name": "Balayong",
            "full_path": "Cardona › Calahan › Balayong",
            "depth": 2,
            "sort_order": 0,
            "is_legacy_unmapped": False,
        },
    ]
    assert payload["entries"][0]["area_uid"] == str(BALAYONG_AREA_UID)
    assert payload["areas"] == ["Cardona › Calahan"]
    assert payload["entries"][0]["area"] == "Cardona › Calahan › Balayong"
