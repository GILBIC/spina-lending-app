"""Historical native reconciliation must be explicit and reachable in review."""

from decimal import Decimal

import pytest
from gilbic_backend.contract_collection_activation_api import _preview_payload
from test_contract_collection_activation import preview


def test_verified_native_reconciliation_is_available_without_claiming_it_happened():
    item = preview(
        collection_state_reconciled=False, native_reconciliation_available=True
    )
    payload = _preview_payload(item)
    assert item.can_activate
    assert not item.balance_reconciled
    assert payload["native_reconciliation_available"] is True
    assert payload["balance_reconciled"] is False
    assert payload["can_activate"] is True


@pytest.mark.parametrize(
    "change",
    [
        {"remaining_balance": Decimal("269.99")},
        {"registration_id": None},
        {"mobile_collections_enabled": False},
        {"dpd_data_status": "payment_allocation_required"},
        {"ecl_included": True},
    ],
)
def test_native_reconciliation_does_not_waive_other_activation_gates(change):
    item = preview(
        collection_state_reconciled=False,
        native_reconciliation_available=True,
        **change,
    )
    assert not item.can_activate
    assert item.blockers
