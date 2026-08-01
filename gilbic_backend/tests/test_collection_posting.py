from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

from gilbic_backend.collection_posting import PostgresCollectionPostingBridge
from spina_mobile_collections.contracts import (
    ActorContext,
    CollectionCommand,
    CollectionEntryType,
)
from spina_mobile_collections.service import CollectionConflict, CollectionRejected


COLLECTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
DEVICE_RECORD_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")
KEY = UUID("55555555-5555-4555-8555-555555555555")


class FakeCursor:
    def __init__(self, loan: dict[str, Any]) -> None:
        self.loan = loan
        self.device_exists = True
        self.sequence_used = False
        self.assignment_exists = True
        self.pass_exists = False
        self.next_receipt = 42
        self.executions: list[tuple[str, tuple[Any, ...] | None]] = []
        self._next: Any = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False

    def execute(self, statement: str, parameters: tuple[Any, ...] | None = None):
        self.executions.append((statement, parameters))
        normalized = " ".join(statement.lower().split())
        self._next = None
        if "from core.devices" in normalized:
            self._next = {"exists": 1} if self.device_exists else None
        elif (
            "from lending.collection_transactions" in normalized
            and "registered_device_id = %s and device_sequence = %s" in normalized
        ):
            self._next = {"id": UUID(int=9)} if self.sequence_used else None
        elif "from lending.loans l" in normalized:
            self._next = self.loan
        elif "from lending.collector_area_assignments" in normalized:
            self._next = {"exists": 1} if self.assignment_exists else None
        elif (
            "from lending.collection_transactions" in normalized
            and "entry_type = 'pass'" in normalized
        ):
            self._next = {"id": UUID(int=10)} if self.pass_exists else None
        elif "nextval('lending.collection_receipt_sequence')" in normalized:
            self._next = {"nextval": self.next_receipt}
        return self

    def fetchone(self):
        return self._next


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self.cursor_instance = cursor

    def cursor(self, **_: Any) -> FakeCursor:
        return self.cursor_instance


def loan_row(**changes: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "loan_id": LOAN_ID,
        "client_id": CLIENT_ID,
        "loan_status": "active",
        "principal": Decimal("1000.00"),
        "daily_amount": Decimal("200.00"),
        "client_status": "active",
        "area": "Cardona",
        "loan_type_code": "REGULAR",
        "loan_type_name": "Regular",
        "calculation_mode": "fixed_daily",
        "settings": {
            "mobile_collections_enabled": True,
            "mobile_balance_mode": "direct_remaining_balance",
        },
        "remaining_balance": Decimal("1000.00"),
        "pass_count": 2,
        "last_payment_date": date(2026, 7, 31),
        "advance_until": None,
        "note": "Call before visiting",
        "is_reconciled": True,
        "state_version": 7,
    }
    row.update(changes)
    return row


def actor() -> ActorContext:
    return ActorContext(
        account_id=str(COLLECTOR_ID),
        device_id="gilbic-installation-one",
        registered_device_id=str(DEVICE_RECORD_ID),
        permissions=frozenset({"collection.create"}),
    )


def command(
    *,
    entry_type: CollectionEntryType = CollectionEntryType.PAYMENT,
    amount: Decimal | None = Decimal("200.00"),
    route_revision: str | None = f"loan:{LOAN_ID}:v7",
) -> CollectionCommand:
    return CollectionCommand(
        idempotency_key=KEY,
        route_entry_id=str(LOAN_ID),
        client_id=str(CLIENT_ID),
        loan_id=str(LOAN_ID),
        collection_date=date(2026, 8, 1),
        entry_type=entry_type,
        amount=amount,
        advance_from=(date(2026, 8, 1) if entry_type is CollectionEntryType.ADVANCE else None),
        advance_until=(date(2026, 8, 3) if entry_type is CollectionEntryType.ADVANCE else None),
        recorded_at=datetime(2026, 8, 1, 2, 29, tzinfo=timezone.utc),
        device_id="gilbic-installation-one",
        device_sequence=8,
        note="Paid at home",
        route_revision=route_revision,
    )


def executed_sql(cursor: FakeCursor) -> str:
    return "\n".join(statement for statement, _ in cursor.executions)


def test_payment_updates_state_receipt_audit_and_transaction_together() -> None:
    cursor = FakeCursor(loan_row())
    result = PostgresCollectionPostingBridge().post_collection(
        FakeConnection(cursor),
        actor(),
        command(),
    )

    assert result.official_balance == Decimal("800.00")
    assert result.receipt_number == "GBC-20260801-00000042"
    assert result.route_revision == f"loan:{LOAN_ID}:v8"
    assert result.message == "Payment saved."
    sql = executed_sql(cursor)
    assert "update lending.loan_collection_state" in sql
    assert "insert into lending.collection_transactions" in sql
    assert "insert into core.audit_logs" in sql

    state_update = next(
        parameters
        for statement, parameters in cursor.executions
        if "update lending.loan_collection_state" in statement
    )
    assert state_update is not None
    assert state_update[0] == Decimal("800.00")
    assert state_update[1] == 0
    assert state_update[5] == 8


def test_full_payment_marks_loan_paid() -> None:
    cursor = FakeCursor(loan_row(remaining_balance=Decimal("200.00")))
    result = PostgresCollectionPostingBridge().post_collection(
        FakeConnection(cursor),
        actor(),
        command(),
    )

    assert result.official_balance == Decimal("0.00")
    assert "set status = 'paid'" in executed_sql(cursor)


def test_stale_route_revision_requires_refresh() -> None:
    cursor = FakeCursor(loan_row())

    with pytest.raises(CollectionConflict) as caught:
        PostgresCollectionPostingBridge().post_collection(
            FakeConnection(cursor),
            actor(),
            command(route_revision=f"loan:{LOAN_ID}:v6"),
        )

    assert caught.value.code == "route_revision_changed"
    assert "Refresh the route" in caught.value.message


def test_pass_is_rejected_when_advance_already_covers_the_date() -> None:
    cursor = FakeCursor(loan_row(advance_until=date(2026, 8, 5)))

    with pytest.raises(CollectionRejected) as caught:
        PostgresCollectionPostingBridge().post_collection(
            FakeConnection(cursor),
            actor(),
            command(entry_type=CollectionEntryType.PASS, amount=None),
        )

    assert caught.value.code == "advance_already_covers_date"
    assert "already covered by ADV" in caught.value.message


def test_unreconciled_state_is_never_modified() -> None:
    cursor = FakeCursor(loan_row(is_reconciled=False))

    with pytest.raises(CollectionRejected) as caught:
        PostgresCollectionPostingBridge().post_collection(
            FakeConnection(cursor),
            actor(),
            command(),
        )

    assert caught.value.code == "loan_state_not_reconciled"
    assert "SPINA" in caught.value.message
    assert "update lending.loan_collection_state" not in executed_sql(cursor)


def test_payment_calculation_requires_explicit_server_configuration() -> None:
    cursor = FakeCursor(
        loan_row(
            calculation_mode="seven_by_seven",
            settings={"mobile_collections_enabled": True},
        )
    )

    with pytest.raises(CollectionRejected) as caught:
        PostgresCollectionPostingBridge().post_collection(
            FakeConnection(cursor),
            actor(),
            command(),
        )

    assert caught.value.code == "loan_calculation_not_ready"
    assert "SPINA desktop" in caught.value.message


def test_device_sequence_cannot_be_reused_with_a_new_transaction_key() -> None:
    cursor = FakeCursor(loan_row())
    cursor.sequence_used = True

    with pytest.raises(CollectionConflict) as caught:
        PostgresCollectionPostingBridge().post_collection(
            FakeConnection(cursor),
            actor(),
            command(),
        )

    assert caught.value.code == "device_sequence_reused"
    assert "Refresh the route" in caught.value.message
