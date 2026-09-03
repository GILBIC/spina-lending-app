from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from uuid import UUID

import pytest
from gilbic_backend.seven_by_seven_extra_principal_reconciliation import (
    ExtraPrincipalReconciliationError,
    reconcile_persisted_extra_principal,
)

TRANSACTION_ID = UUID("b05aed91-ac05-42dc-a44d-535d7cf73508")
ADJUSTMENT_ID = UUID("93facb33-9c85-44c6-b9f5-540905fb2e74")


class FakeCursor:
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self._responses = iter(responses)
        self._current: dict[str, object] | None = None

    def execute(self, _statement: str, _parameters: tuple[object, ...]) -> None:
        self._current = next(self._responses)

    def fetchone(self) -> dict[str, object] | None:
        return self._current


def _header() -> dict[str, object]:
    return {
        "transaction_id": TRANSACTION_ID,
        "receipt_loan_id": UUID("b521e666-8196-4f44-807a-f3502a41236c"),
        "cash_received": Decimal("100.00"),
        "applied_amount": Decimal("100.00"),
        "unallocated_amount": Decimal("0.00"),
        "allocation_state": "fully_allocated",
        "entry_type": "payment",
        "is_voided": False,
        "previous_balance": Decimal("900.00"),
        "official_balance": Decimal("800.00"),
        "receipt_intent": "extra_as_principal_reduction",
        "receipt_interest_contribution": "0.00",
        "receipt_principal_contribution": "100.00",
        "receipt_operational_state_digest": "a" * 64,
        "adjustment_id": ADJUSTMENT_ID,
        "adjustment_loan_id": UUID("b521e666-8196-4f44-807a-f3502a41236c"),
        "principal_reduction": Decimal("100.00"),
        "prior_future_principal": Decimal("500.00"),
        "resulting_future_principal": Decimal("400.00"),
        "removed_future_interest": Decimal("21.00"),
        "adjustment_refund_due": Decimal("5.00"),
        "resulting_operational_version": 2,
        "state_balance": Decimal("800.00"),
        "refund_due_total": Decimal("5.00"),
        "audit_count": 1,
        "source_evidence_ready": True,
        "accounting_status": "management_accounting_review_required",
        "automatic_source_posting": False,
    }


def _items() -> dict[str, object]:
    return {
        "item_count": 3,
        "item_principal_reduction": Decimal("100.00"),
        "item_resulting_future_principal": Decimal("400.00"),
        "item_removed_future_interest": Decimal("21.00"),
        "retained_advance": Decimal("30.00"),
        "item_refund_due": Decimal("5.00"),
        "operational_exact_count": 3,
    }


def test_exact_persisted_coordinates_reconcile() -> None:
    result = reconcile_persisted_extra_principal(
        FakeCursor([_header(), _items()]),
        transaction_id=TRANSACTION_ID,
        adjustment_id=ADJUSTMENT_ID,
    )

    assert result.cash_received == Decimal("100.00")
    assert result.interest_contribution == Decimal("0.00")
    assert result.principal_contribution == Decimal("100.00")
    assert result.adjustment_principal == Decimal("100.00")
    assert result.future_principal == Decimal("400.00")
    assert result.retained_advance == Decimal("30.00")
    assert result.refund_due == Decimal("5.00")
    assert result.operational_version == 2
    assert result.accounting_status == "management_accounting_review_required"
    assert result.audit_present is True


@pytest.mark.parametrize(
    ("fault", "field", "value"),
    (
        ("receipt", "receipt_principal_contribution", "99.00"),
        ("audit", "audit_count", 0),
        ("refund_due", "refund_due_total", Decimal("4.00")),
        ("accounting_readiness", "source_evidence_ready", False),
        ("operational_row", "operational_exact_count", 2),
    ),
)
def test_any_persisted_mismatch_fails_closed(
    fault: str,
    field: str,
    value: object,
) -> None:
    header = deepcopy(_header())
    items = deepcopy(_items())
    target = items if field == "operational_exact_count" else header
    target[field] = value

    with pytest.raises(ExtraPrincipalReconciliationError) as captured:
        reconcile_persisted_extra_principal(
            FakeCursor([header, items]),
            transaction_id=TRANSACTION_ID,
            adjustment_id=ADJUSTMENT_ID,
        )

    assert captured.value.code == "seven_by_seven_extra_principal_reconciliation_failed"
    assert fault in str(captured.value)
