from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from gilbic_backend.concurrent_receipt_collection_posting import (
    ConcurrentReceiptSafeCollectionPostingBridge,
)
from gilbic_backend.voluntary_extra_collection_posting import (
    VoluntaryExtraAwareCollectionPostingBridge,
)
from spina_mobile_collections.contracts import (
    ActorContext,
    CollectionCommand,
    CollectionEntryType,
)


COLLECTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
DEVICE_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")
KEY = UUID("55555555-5555-4555-8555-555555555555")
COLLECTION_DATE = date(2026, 8, 16)


class FakeCursor:
    def __init__(
        self,
        *,
        current_version: int = 8,
        chain: tuple[tuple[int, int], ...] = (),
    ) -> None:
        self.current_version = current_version
        self.chain = chain
        self.executions: list[tuple[str, tuple[Any, ...] | None]] = []
        self._next: Any = None
        self._all: list[dict[str, int]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False

    def execute(self, statement: str, parameters: tuple[Any, ...] | None = None):
        self.executions.append((statement, parameters))
        normalized = " ".join(statement.lower().split())
        self._next = None
        self._all = []
        if "select state.state_version" in normalized:
            self._next = {"state_version": self.current_version}
        elif "from lending.collection_transactions receipt" in normalized:
            self._all = [
                {
                    "state_version_before": before,
                    "state_version_after": after,
                }
                for before, after in self.chain
            ]
        return self

    def fetchone(self):
        return self._next

    def fetchall(self):
        return self._all


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self.cursor_instance = cursor

    def cursor(self, **_: Any) -> FakeCursor:
        return self.cursor_instance


def actor() -> ActorContext:
    return ActorContext(
        account_id=str(COLLECTOR_ID),
        device_id="installation-one",
        registered_device_id=str(DEVICE_ID),
        permissions=frozenset({"collection.create"}),
    )


def command(
    *,
    revision: str = f"loan:{LOAN_ID}:v7",
    entry_type: CollectionEntryType = CollectionEntryType.PAYMENT,
) -> CollectionCommand:
    return CollectionCommand(
        idempotency_key=KEY,
        route_entry_id=str(LOAN_ID),
        client_id=str(CLIENT_ID),
        loan_id=str(LOAN_ID),
        collection_date=COLLECTION_DATE,
        entry_type=entry_type,
        amount=(None if entry_type is CollectionEntryType.PASS else Decimal("100.00")),
        recorded_at=datetime(2026, 8, 16, 4, 0, tzinfo=timezone.utc),
        device_id="installation-one",
        device_sequence=18,
        route_revision=revision,
    )


def capture_super_command(monkeypatch, captured: list[CollectionCommand]) -> object:
    sentinel = object()

    def fake_super(self, connection, actor_context, prepared_command):
        captured.append(prepared_command)
        return sentinel

    monkeypatch.setattr(
        VoluntaryExtraAwareCollectionPostingBridge,
        "post_collection",
        fake_super,
    )
    return sentinel


def test_one_intervening_same_day_payment_rebases_to_current_revision(monkeypatch) -> None:
    cursor = FakeCursor(current_version=8, chain=((7, 8),))
    captured: list[CollectionCommand] = []
    sentinel = capture_super_command(monkeypatch, captured)

    result = ConcurrentReceiptSafeCollectionPostingBridge().post_collection(
        FakeConnection(cursor),
        actor(),
        command(),
    )

    assert result is sentinel
    assert captured[0].route_revision == f"loan:{LOAN_ID}:v8"
    sql = "\n".join(statement for statement, _ in cursor.executions)
    assert "receipt.collection_date = %s" in sql
    assert "receipt.entry_type = 'payment'" in sql
    assert "receipt.is_voided = false" in sql


def test_multiple_contiguous_same_day_payments_can_rebase(monkeypatch) -> None:
    cursor = FakeCursor(current_version=10, chain=((7, 8), (8, 9), (9, 10)))
    captured: list[CollectionCommand] = []
    capture_super_command(monkeypatch, captured)

    ConcurrentReceiptSafeCollectionPostingBridge().post_collection(
        FakeConnection(cursor),
        actor(),
        command(),
    )

    assert captured[0].route_revision == f"loan:{LOAN_ID}:v10"


def test_revision_gap_is_not_rebased(monkeypatch) -> None:
    cursor = FakeCursor(current_version=9, chain=((8, 9),))
    captured: list[CollectionCommand] = []
    capture_super_command(monkeypatch, captured)
    stale = command()

    ConcurrentReceiptSafeCollectionPostingBridge().post_collection(
        FakeConnection(cursor),
        actor(),
        stale,
    )

    # The authoritative base bridge receives the stale revision unchanged and
    # therefore keeps its normal route_revision_changed conflict behavior.
    assert captured[0].route_revision == stale.route_revision


def test_non_unit_or_overlapping_revision_chain_is_not_rebased(monkeypatch) -> None:
    cursor = FakeCursor(current_version=9, chain=((7, 9),))
    captured: list[CollectionCommand] = []
    capture_super_command(monkeypatch, captured)
    stale = command()

    ConcurrentReceiptSafeCollectionPostingBridge().post_collection(
        FakeConnection(cursor),
        actor(),
        stale,
    )

    assert captured[0].route_revision == stale.route_revision


def test_pass_never_uses_same_day_payment_rebase(monkeypatch) -> None:
    cursor = FakeCursor(current_version=8, chain=((7, 8),))
    captured: list[CollectionCommand] = []
    capture_super_command(monkeypatch, captured)
    stale = command(entry_type=CollectionEntryType.PASS)

    ConcurrentReceiptSafeCollectionPostingBridge().post_collection(
        FakeConnection(cursor),
        actor(),
        stale,
    )

    assert captured[0] is stale
    assert not any(
        "select state.state_version" in statement.lower()
        for statement, _ in cursor.executions
    )


def test_wrong_loan_revision_is_never_rebased(monkeypatch) -> None:
    cursor = FakeCursor(current_version=8, chain=((7, 8),))
    captured: list[CollectionCommand] = []
    capture_super_command(monkeypatch, captured)
    other_loan = UUID("99999999-9999-4999-8999-999999999999")
    stale = command(revision=f"loan:{other_loan}:v7")

    ConcurrentReceiptSafeCollectionPostingBridge().post_collection(
        FakeConnection(cursor),
        actor(),
        stale,
    )

    assert captured[0].route_revision == stale.route_revision
    assert cursor.executions == []


def test_future_revision_is_not_rebased(monkeypatch) -> None:
    cursor = FakeCursor(current_version=8, chain=())
    captured: list[CollectionCommand] = []
    capture_super_command(monkeypatch, captured)
    future = command(revision=f"loan:{LOAN_ID}:v9")

    ConcurrentReceiptSafeCollectionPostingBridge().post_collection(
        FakeConnection(cursor),
        actor(),
        future,
    )

    assert captured[0].route_revision == future.route_revision
