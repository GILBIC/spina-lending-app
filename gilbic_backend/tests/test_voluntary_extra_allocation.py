from datetime import date
from decimal import Decimal

import pytest

from gilbic_backend.contract_schedule_engine import (
    OutstandingInstallment,
    PaymentAllocationError,
    plan_protected_regular_allocation,
    plan_scheduled_or_voluntary_extra_allocation,
)


def _installment(
    number: int,
    *,
    due_date: date | None = None,
    amount: str = "100.00",
    allocated: str = "0.00",
) -> OutstandingInstallment:
    return OutstandingInstallment(
        installment_id=number,
        installment_number=number,
        due_date=due_date or date(2026, 8, 15 + number),
        contractual_amount=Decimal(amount),
        allocated_amount=Decimal(allocated),
    )


def test_partial_payment_stays_on_oldest_due_obligation() -> None:
    plan = plan_protected_regular_allocation(
        transaction_amount=Decimal("60.00"),
        collection_date=date(2026, 8, 18),
        installments=(
            _installment(1, due_date=date(2026, 8, 16)),
            _installment(2, due_date=date(2026, 8, 17)),
            _installment(3, due_date=date(2026, 8, 18)),
        ),
    )

    assert [
        (row.installment_number, row.amount_applied, row.allocation_basis)
        for row in plan
    ] == [(1, Decimal("60.00"), "oldest_due_first")]


def test_required_cash_clears_all_past_due_then_due_today_before_extra() -> None:
    plan = plan_protected_regular_allocation(
        transaction_amount=Decimal("220.00"),
        collection_date=date(2026, 8, 18),
        installments=(
            _installment(1, due_date=date(2026, 8, 16), allocated="50.00"),
            _installment(2, due_date=date(2026, 8, 17)),
            _installment(3, due_date=date(2026, 8, 18)),
            _installment(4, due_date=date(2026, 8, 19)),
        ),
    )

    assert [
        (row.installment_number, row.amount_applied, row.allocation_basis)
        for row in plan
    ] == [
        (1, Decimal("50.00"), "oldest_due_first"),
        (2, Decimal("100.00"), "oldest_due_first"),
        (3, Decimal("70.00"), "oldest_due_first"),
    ]


def test_true_extra_cash_requires_advance_or_principal_reduction_choice() -> None:
    with pytest.raises(
        PaymentAllocationError,
        match="Choose Advance or Principal Reduction",
    ):
        plan_protected_regular_allocation(
            transaction_amount=Decimal("350.00"),
            collection_date=date(2026, 8, 18),
            installments=(
                _installment(1, due_date=date(2026, 8, 16)),
                _installment(2, due_date=date(2026, 8, 17)),
                _installment(3, due_date=date(2026, 8, 18)),
                _installment(4, due_date=date(2026, 8, 19)),
            ),
        )


def test_explicit_principal_reduction_uses_contractual_tail() -> None:
    plan = plan_protected_regular_allocation(
        transaction_amount=Decimal("200.00"),
        collection_date=date(2026, 8, 16),
        extra_choice="principal_reduction",
        installments=(
            _installment(1, due_date=date(2026, 8, 16)),
            _installment(2, due_date=date(2026, 8, 17)),
            _installment(3, due_date=date(2026, 8, 18)),
            _installment(4, due_date=date(2026, 8, 19)),
        ),
    )

    assert [
        (row.installment_number, row.amount_applied, row.allocation_basis)
        for row in plan
    ] == [
        (1, Decimal("100.00"), "oldest_due_first"),
        (4, Decimal("100.00"), "voluntary_extra_tail"),
    ]
    assert 2 not in {row.installment_number for row in plan}
    assert 3 not in {row.installment_number for row in plan}


def test_explicit_advance_uses_oldest_future_obligation_without_skipping() -> None:
    plan = plan_protected_regular_allocation(
        transaction_amount=Decimal("250.00"),
        collection_date=date(2026, 8, 16),
        extra_choice="advance",
        installments=(
            _installment(1, due_date=date(2026, 8, 16)),
            _installment(2, due_date=date(2026, 8, 17)),
            _installment(3, due_date=date(2026, 8, 18)),
            _installment(4, due_date=date(2026, 8, 19)),
        ),
    )

    assert [
        (row.installment_number, row.amount_applied, row.allocation_basis)
        for row in plan
    ] == [
        (1, Decimal("100.00"), "oldest_due_first"),
        (2, Decimal("100.00"), "future_advance_oldest_first"),
        (3, Decimal("50.00"), "future_advance_oldest_first"),
    ]


def test_extra_choice_cannot_exceed_exact_remaining_contract_balance() -> None:
    with pytest.raises(PaymentAllocationError, match="exact payoff"):
        plan_protected_regular_allocation(
            transaction_amount=Decimal("401.00"),
            collection_date=date(2026, 8, 16),
            extra_choice="principal_reduction",
            installments=(
                _installment(1, due_date=date(2026, 8, 16)),
                _installment(2, due_date=date(2026, 8, 17)),
                _installment(3, due_date=date(2026, 8, 18)),
                _installment(4, due_date=date(2026, 8, 19)),
            ),
        )


def test_legacy_wrapper_remains_compatible_during_migration() -> None:
    plan = plan_scheduled_or_voluntary_extra_allocation(
        transaction_amount=Decimal("200.00"),
        installments=(
            _installment(1),
            _installment(2),
            _installment(3),
            _installment(4),
        ),
        voluntary_extra=True,
    )
    assert [row.installment_number for row in plan] == [1, 4]


def test_normal_cash_uses_active_extension_as_catch_up_before_true_extra() -> None:
    plan = plan_protected_regular_allocation(
        transaction_amount=Decimal("200.00"),
        collection_date=date(2026, 9, 6),
        active_borrower_extension_slots=1,
        installments=(
            _installment(5, due_date=date(2026, 9, 6)),
            _installment(6, due_date=date(2026, 9, 7)),
            _installment(7, due_date=date(2026, 9, 8)),
        ),
    )

    assert [
        (row.installment_number, row.amount_applied, row.allocation_basis)
        for row in plan
    ] == [
        (5, Decimal("100.00"), "oldest_due_first"),
        (6, Decimal("100.00"), "borrower_catch_up_oldest_first"),
    ]
