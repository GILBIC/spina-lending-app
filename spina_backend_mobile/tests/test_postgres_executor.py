from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from spina_mobile_collections.contracts import (
    ActorContext,
    CollectionCommand,
    CollectionEntryType,
    CollectionStatus,
    PostedCollection,
)
from spina_mobile_collections.postgres import PostgresCollectionExecutor
from spina_mobile_collections.service import CollectionRejected

KEY = UUID("6cb93829-dccd-4d43-a25c-a1f31859cc1b")


class FakeCursor:
    def __init__(self, existing: dict[str, Any] | None = None) -> None:
        self.existing = existing
        self.executed: list[tuple[str, tuple[Any, ...] | None]] = []

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        return False

    def execute(self, statement: str, parameters: tuple[Any, ...] | None = None) -> None:
        self.executed.append((statement, parameters))

    def fetchone(self) -> dict[str, Any] | None:
        return self.existing


class FakeTransaction:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def __enter__(self) -> FakeTransaction:
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        if exc_type is None:
            self.connection.committed = True
        else:
            self.connection.rolled_back = True
        return False


class FakeConnection:
    def __init__(self, existing: dict[str, Any] | None = None) -> None:
        self.cursor_instance = FakeCursor(existing)
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        self.closed = True
        return False

    def transaction(self) -> FakeTransaction:
        return FakeTransaction(self)

    def cursor(self, **_: Any) -> FakeCursor:
        return self.cursor_instance


class AcceptingBridge:
    def __init__(self) -> None:
        self.calls = 0

    def post_collection(
        self,
        connection: Any,
        actor: ActorContext,
        command: CollectionCommand,
    ) -> PostedCollection:
        del connection, actor, command
        self.calls += 1
        return posted_collection()


class RejectingBridge:
    def post_collection(
        self,
        connection: Any,
        actor: ActorContext,
        command: CollectionCommand,
    ) -> PostedCollection:
        del connection, actor, command
        raise CollectionRejected("The collection day is closed.", code="day_closed")


def actor() -> ActorContext:
    return ActorContext(
        account_id="collector-7",
        device_id="collector-phone-15",
        permissions=frozenset({"collection.create"}),
    )


def command() -> CollectionCommand:
    return CollectionCommand(
        idempotency_key=KEY,
        route_entry_id="route-entry-304",
        client_id="client-304",
        loan_id="loan-815",
        collection_date=date(2026, 7, 31),
        entry_type=CollectionEntryType.PAYMENT,
        amount=Decimal("200.00"),
        recorded_at=datetime(2026, 7, 31, 5, 15, tzinfo=timezone.utc),
        device_id="collector-phone-15",
        device_sequence=45,
        route_revision="route-v3",
    )


def posted_collection() -> PostedCollection:
    return PostedCollection(
        server_transaction_id="collection-9001",
        receipt_number="OR-00009001",
        official_balance=Decimal("4600.00"),
        accepted_at=datetime(2026, 7, 31, 5, 16, tzinfo=timezone.utc),
        route_revision="route-v4",
    )


def test_accepts_and_stores_result_in_one_transaction() -> None:
    connection = FakeConnection()
    bridge = AcceptingBridge()
    executor = PostgresCollectionExecutor(
        connection_factory=lambda: connection,
        posting_bridge=bridge,
    )

    outcome = executor.execute(
        actor=actor(),
        command=command(),
        canonical_payload=command().canonical_payload(),
        request_hash="a" * 64,
    )

    assert outcome.status is CollectionStatus.ACCEPTED
    assert outcome.posted.receipt_number == "OR-00009001"
    assert bridge.calls == 1
    assert connection.committed is True
    assert connection.rolled_back is False
    statements = "\n".join(item[0] for item in connection.cursor_instance.executed)
    assert "pg_advisory_xact_lock" in statements
    assert "INSERT INTO mobile.gilbic_collection_idempotency" in statements


def test_replays_existing_result_without_calling_bridge() -> None:
    connection = FakeConnection(
        {
            "collector_account_id": "collector-7",
            "registered_device_id": "collector-phone-15",
            "canonical_request_hash": "a" * 64,
            "server_transaction_id": "collection-9001",
            "receipt_number": "OR-00009001",
            "official_balance": Decimal("4600.00"),
            "accepted_at": datetime(2026, 7, 31, 5, 16, tzinfo=timezone.utc),
            "route_revision": "route-v4",
        }
    )
    bridge = AcceptingBridge()
    executor = PostgresCollectionExecutor(
        connection_factory=lambda: connection,
        posting_bridge=bridge,
    )

    outcome = executor.execute(
        actor=actor(),
        command=command(),
        canonical_payload=command().canonical_payload(),
        request_hash="a" * 64,
    )

    assert outcome.status is CollectionStatus.DUPLICATE
    assert outcome.posted.receipt_number == "OR-00009001"
    assert bridge.calls == 0
    assert connection.committed is True


def test_changed_request_hash_returns_conflict_without_posting() -> None:
    connection = FakeConnection(
        {
            "collector_account_id": "collector-7",
            "registered_device_id": "collector-phone-15",
            "canonical_request_hash": "b" * 64,
            "server_transaction_id": "collection-9001",
            "receipt_number": "OR-00009001",
            "official_balance": Decimal("4600.00"),
            "accepted_at": datetime(2026, 7, 31, 5, 16, tzinfo=timezone.utc),
            "route_revision": "route-v4",
        }
    )
    bridge = AcceptingBridge()
    executor = PostgresCollectionExecutor(
        connection_factory=lambda: connection,
        posting_bridge=bridge,
    )

    outcome = executor.execute(
        actor=actor(),
        command=command(),
        canonical_payload=command().canonical_payload(),
        request_hash="a" * 64,
    )

    assert outcome.status is CollectionStatus.CONFLICT
    assert outcome.code == "idempotency_mismatch"
    assert bridge.calls == 0


def test_business_rejection_rolls_back_transaction() -> None:
    connection = FakeConnection()
    executor = PostgresCollectionExecutor(
        connection_factory=lambda: connection,
        posting_bridge=RejectingBridge(),
    )

    outcome = executor.execute(
        actor=actor(),
        command=command(),
        canonical_payload=command().canonical_payload(),
        request_hash="a" * 64,
    )

    assert outcome.status is CollectionStatus.REJECTED
    assert outcome.code == "day_closed"
    assert connection.rolled_back is True
    assert connection.committed is False


def test_migration_has_global_unique_key_and_atomicity_comment() -> None:
    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "0001_gilbic_collection_idempotency.sql"
    ).read_text(encoding="utf-8")

    assert "UNIQUE (idempotency_key)" in migration
    assert "canonical_request_hash CHAR(64)" in migration
    assert "BEGIN;" in migration and "COMMIT;" in migration
    assert "same transaction as the official SPINA" in migration
