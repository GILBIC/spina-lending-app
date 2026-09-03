from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from gilbic_backend.collection_past_due_capture import CollectionPastDueCapture
from gilbic_backend.concurrent_receipt_collection_posting import (
    ConcurrentReceiptSafeCollectionPostingBridge,
)
from gilbic_backend.past_due_promise_progress import (
    PastDuePromiseProgress,
    promise_deadline_status,
)
from gilbic_backend.voluntary_extra_collection_posting import (
    VoluntaryExtraAwareCollectionPostingBridge,
)
from spina_mobile_collections.contracts import (
    ActorContext,
    CollectionCommand,
    CollectionEntryType,
    PostedCollection,
)


LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
COLLECTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
DEVICE_ID = UUID("22222222-2222-4222-8222-222222222222")
TRANSACTION_ID = UUID("55555555-5555-4555-8555-555555555555")
KEY = UUID("66666666-6666-4666-8666-666666666666")


def _actor() -> ActorContext:
    return ActorContext(
        account_id=str(COLLECTOR_ID),
        device_id="promise-progress-device",
        registered_device_id=str(DEVICE_ID),
        permissions=frozenset({"collection.create"}),
    )


def _command() -> CollectionCommand:
    return CollectionCommand(
        idempotency_key=KEY,
        route_entry_id=str(LOAN_ID),
        client_id=str(CLIENT_ID),
        loan_id=str(LOAN_ID),
        collection_date=date(2026, 8, 25),
        entry_type=CollectionEntryType.PAYMENT,
        amount=Decimal("50.00"),
        recorded_at=datetime(2026, 8, 25, 1, 0, tzinfo=timezone.utc),
        device_id="promise-progress-device",
        device_sequence=1,
        route_revision=f"loan:{LOAN_ID}:v0",
    )


def _posted() -> PostedCollection:
    return PostedCollection(
        server_transaction_id=str(TRANSACTION_ID),
        receipt_number="GBC-20260825-00000001",
        official_balance=Decimal("950.00"),
        accepted_at=datetime(2026, 8, 25, 1, 1, tzinfo=timezone.utc),
        route_revision=f"loan:{LOAN_ID}:v1",
        message="Payment saved.",
    )


def test_promise_deadline_status_is_kept_only_when_fully_satisfied() -> None:
    assert promise_deadline_status(
        promised_amount=Decimal("200.00"),
        remaining_amount=Decimal("0.00"),
    ) == "kept"
    assert promise_deadline_status(
        promised_amount=Decimal("200.00"),
        remaining_amount=Decimal("100.00"),
    ) == "partially_kept"
    assert promise_deadline_status(
        promised_amount=Decimal("200.00"),
        remaining_amount=Decimal("200.00"),
    ) == "not_kept"


def test_outer_collection_bridge_reconciles_existing_promise_before_new_past_due_capture(
    monkeypatch,
) -> None:
    events: list[str] = []
    command = _command()
    posted = _posted()

    monkeypatch.setattr(
        ConcurrentReceiptSafeCollectionPostingBridge,
        "_prepare_same_day_payment_revision",
        lambda self, connection, *, actor, command: command,
    )
    monkeypatch.setattr(
        VoluntaryExtraAwareCollectionPostingBridge,
        "post_collection",
        lambda self, connection, actor, command: events.append("posted") or posted,
    )
    monkeypatch.setattr(
        PastDuePromiseProgress,
        "apply",
        lambda self, connection, *, transaction_id, collection_date: (
            events.append("promise_progress"),
            transaction_id == TRANSACTION_ID,
            collection_date == command.collection_date,
        ),
    )
    monkeypatch.setattr(
        CollectionPastDueCapture,
        "apply",
        lambda self, connection, *, actor, command, posted: events.append(
            "new_past_due_capture"
        ),
    )

    result = ConcurrentReceiptSafeCollectionPostingBridge().post_collection(
        object(),
        _actor(),
        command,
    )

    assert result == posted
    assert events == ["posted", "promise_progress", "new_past_due_capture"]
