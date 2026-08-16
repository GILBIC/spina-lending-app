from decimal import Decimal

import pytest

from gilbic_backend.receipt_application import (
    ReceiptApplicationError,
    plan_receipt_application,
)


def test_scheduled_overpayment_preserves_real_cash_as_unallocated() -> None:
    plan = plan_receipt_application(
        cash_received_amount="200.00",
        maximum_immediately_applicable="100.00",
        allocation_intent="scheduled",
    )

    assert plan.cash_received_amount == Decimal("200.00")
    assert plan.applied_amount == Decimal("100.00")
    assert plan.unallocated_amount == Decimal("100.00")
    assert plan.allocation_state == "partially_allocated"
    assert plan.needs_review is True


def test_voluntary_extra_can_apply_more_without_covering_future_dates() -> None:
    plan = plan_receipt_application(
        cash_received_amount="200.00",
        maximum_immediately_applicable="500.00",
        allocation_intent="voluntary_extra",
    )

    assert plan.applied_amount == Decimal("200.00")
    assert plan.unallocated_amount == Decimal("0.00")
    assert plan.allocation_state == "fully_allocated"
    assert plan.needs_review is False


def test_cash_beyond_exact_remaining_balance_is_kept_for_review() -> None:
    plan = plan_receipt_application(
        cash_received_amount="600.00",
        maximum_immediately_applicable="500.00",
        allocation_intent="voluntary_extra",
    )

    assert plan.applied_amount == Decimal("500.00")
    assert plan.unallocated_amount == Decimal("100.00")
    assert plan.allocation_state == "partially_allocated"


def test_second_receipt_after_obligation_is_satisfied_is_not_a_duplicate() -> None:
    plan = plan_receipt_application(
        cash_received_amount="100.00",
        maximum_immediately_applicable="0.00",
        allocation_intent="scheduled",
    )

    assert plan.cash_received_amount == Decimal("100.00")
    assert plan.applied_amount == Decimal("0.00")
    assert plan.unallocated_amount == Decimal("100.00")
    assert plan.allocation_state == "unallocated"
    assert plan.needs_review is True


def test_advance_excess_does_not_spill_into_unnamed_future_dates() -> None:
    plan = plan_receipt_application(
        cash_received_amount="250.00",
        maximum_immediately_applicable="200.00",
        allocation_intent="advance",
    )

    assert plan.applied_amount == Decimal("200.00")
    assert plan.unallocated_amount == Decimal("50.00")
    assert plan.allocation_state == "partially_allocated"


def test_invalid_receipt_values_fail_closed() -> None:
    with pytest.raises(ReceiptApplicationError, match="greater than zero"):
        plan_receipt_application(
            cash_received_amount="0.00",
            maximum_immediately_applicable="100.00",
            allocation_intent="scheduled",
        )

    with pytest.raises(ReceiptApplicationError, match="cannot be negative"):
        plan_receipt_application(
            cash_received_amount="100.00",
            maximum_immediately_applicable="-1.00",
            allocation_intent="scheduled",
        )
