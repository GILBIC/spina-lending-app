from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from gilbic_backend.collection_posting import PostgresCollectionPostingBridge
from gilbic_backend.cross_collector_posting import CrossCollectorCollectionPostingBridge
from spina_mobile_collections.contracts import CollectionCommand, CollectionEntryType
from spina_mobile_collections.service import CollectionRejected


COLLECTOR_ID = UUID("11111111-1111-4111-8111-111111111111")


def command(collection_date: date) -> CollectionCommand:
    return CollectionCommand(
        idempotency_key=UUID("22222222-2222-4222-8222-222222222222"),
        route_entry_id="33333333-3333-4333-8333-333333333333",
        client_id="44444444-4444-4444-8444-444444444444",
        loan_id="33333333-3333-4333-8333-333333333333",
        collection_date=collection_date,
        entry_type=CollectionEntryType.PAYMENT,
        amount=Decimal("200.00"),
        recorded_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
        device_id="device-one",
        device_sequence=1,
        route_revision="loan:33333333-3333-4333-8333-333333333333:v1",
    )


def test_explicit_other_area_flow_ignores_only_route_assignment_rejection(
    monkeypatch,
) -> None:
    def reject_assignment(*args, **kwargs) -> None:
        raise CollectionRejected(
            "This client is not assigned to your route.",
            code="route_not_assigned",
        )

    monkeypatch.setattr(
        PostgresCollectionPostingBridge,
        "_validate_loan_and_route",
        staticmethod(reject_assignment),
    )

    CrossCollectorCollectionPostingBridge._validate_loan_and_route(
        object(),
        loan={"last_payment_date": date(2026, 8, 2)},
        collector_user_id=COLLECTOR_ID,
        command=command(date(2026, 8, 3)),
    )


def test_other_area_flow_preserves_latest_payment_date_guard(monkeypatch) -> None:
    def reject_assignment(*args, **kwargs) -> None:
        raise CollectionRejected("Not assigned", code="route_not_assigned")

    monkeypatch.setattr(
        PostgresCollectionPostingBridge,
        "_validate_loan_and_route",
        staticmethod(reject_assignment),
    )

    with pytest.raises(CollectionRejected) as caught:
        CrossCollectorCollectionPostingBridge._validate_loan_and_route(
            object(),
            loan={"last_payment_date": date(2026, 8, 4)},
            collector_user_id=COLLECTOR_ID,
            command=command(date(2026, 8, 3)),
        )

    assert caught.value.code == "collection_date_out_of_order"


def test_other_collection_rejections_are_not_bypassed(monkeypatch) -> None:
    def reject_state(*args, **kwargs) -> None:
        raise CollectionRejected("Loan not ready", code="loan_state_not_reconciled")

    monkeypatch.setattr(
        PostgresCollectionPostingBridge,
        "_validate_loan_and_route",
        staticmethod(reject_state),
    )

    with pytest.raises(CollectionRejected) as caught:
        CrossCollectorCollectionPostingBridge._validate_loan_and_route(
            object(),
            loan={"last_payment_date": None},
            collector_user_id=COLLECTOR_ID,
            command=command(date(2026, 8, 3)),
        )

    assert caught.value.code == "loan_state_not_reconciled"
