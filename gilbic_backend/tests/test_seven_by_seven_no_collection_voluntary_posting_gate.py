from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, cast
from uuid import uuid4

import pytest

from gilbic_backend.seven_by_seven_multi_receipt_posting import (
    MultiReceiptSevenBySevenCollectionPostingBridge,
)
from gilbic_backend.seven_by_seven_no_collection_voluntary_posting import (
    NoCollectionVoluntarySevenBySevenCollectionPostingBridge,
)
from spina_mobile_collections.contracts import (
    ActorContext,
    CollectionCommand,
    CollectionEntryType,
    PaymentAllocationIntent,
)
from spina_mobile_collections.service import CollectionRejected


def _actor() -> ActorContext:
    return ActorContext(
        account_id=str(uuid4()),
        device_id="test-installation",
        registered_device_id=str(uuid4()),
        permissions=frozenset({"collection.create"}),
    )


def _command(*, entry_type: CollectionEntryType) -> CollectionCommand:
    loan_id = str(uuid4())
    return CollectionCommand(
        idempotency_key=uuid4(),
        route_entry_id=loan_id,
        client_id=str(uuid4()),
        loan_id=loan_id,
        collection_date=date(2097, 8, 10),
        entry_type=entry_type,
        recorded_at=datetime(2097, 8, 10, 8, 0, tzinfo=timezone.utc),
        device_id="test-installation",
        device_sequence=1,
        amount=Decimal("50.00"),
        route_revision="test-revision",
        payment_allocation_intent=PaymentAllocationIntent.NO_COLLECTION_VOLUNTARY,
    )


def test_production_multi_receipt_chain_includes_no_collection_voluntary_gate() -> None:
    assert (
        MultiReceiptSevenBySevenCollectionPostingBridge.__mro__[1]
        is NoCollectionVoluntarySevenBySevenCollectionPostingBridge
    )


def test_no_collection_voluntary_payment_fails_before_database_mutation() -> None:
    bridge = NoCollectionVoluntarySevenBySevenCollectionPostingBridge()

    with pytest.raises(CollectionRejected) as caught:
        bridge.post_collection(
            cast(Any, object()),
            _actor(),
            _command(entry_type=CollectionEntryType.PAYMENT),
        )

    assert caught.value.code == "seven_by_seven_no_collection_voluntary_posting_required"


def test_no_collection_voluntary_intent_rejects_non_payment_entry() -> None:
    bridge = NoCollectionVoluntarySevenBySevenCollectionPostingBridge()

    with pytest.raises(CollectionRejected) as caught:
        bridge.post_collection(
            cast(Any, object()),
            _actor(),
            _command(entry_type=CollectionEntryType.ADVANCE),
        )

    assert caught.value.code == "seven_by_seven_no_collection_voluntary_payment_required"
