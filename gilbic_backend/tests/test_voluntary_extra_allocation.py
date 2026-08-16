from datetime import date
from decimal import Decimal

import pytest

from gilbic_backend.contract_schedule_engine import (
    OutstandingInstallment,
    PaymentAllocationError,
    plan_scheduled_or_voluntary_extra_allocation,
)


def _installment(number: int, amount: str = "100.00") -> OutstandingInstallment:
    return OutstandingInstallment(
        installment_id=number,
        installment_number=number,
        due_date=date(2026, 8, 15 + number),
        contractual_amount=Decimal(amount),
    )


def test_exact_or_partial_payment_stays_on_current_scheduled_installment() -> None:
    installments = (_installment(1), _installment(2), _installment(3))

    partial = plan_scheduled_or_voluntary_extra_allocation(
        transaction_amount=Decimal("60.00"),
        installments=installments,
        voluntary_extra=False,
    )
    assert [(row.installment_number, row.amount_applied, row.allocation_basis) for row in partial] == [
        (1, Decimal("60.00"), "oldest_due_first"),
    ]

    exact = plan_scheduled_or_voluntary_extra_allocation(
        transaction_amount=Decimal("100.00"),
        installments=installments,
        voluntary_extra=False,
    )
    assert [(row.installment_number, row.amount_applied, row.allocation_basis) for row in exact] == [
        (1, Decimal("100.00"), "oldest_due_first"),
    ]


def test_extra_cash_requires_explicit_intent_instead_of_becoming_advance() -> None:
    with pytest.raises(PaymentAllocationError, match="Choose Voluntary extra"):
        plan_scheduled_or_voluntary_extra_allocation(
            transaction_amount=Decimal("200.00"),
            installments=(_installment(1), _installment(2), _installment(3)),
            voluntary_extra=False,
        )


def test_regular_100_due_200_received_keeps_tomorrow_due_and_reduces_tail() -> None:
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

    assert [(row.installment_number, row.amount_applied, row.allocation_basis) for row in plan] == [
        (1, Decimal("100.00"), "oldest_due_first"),
        (4, Decimal("100.00"), "voluntary_extra_tail"),
    ]
    assert 2 not in {row.installment_number for row in plan}
    assert 3 not in {row.installment_number for row in plan}


def test_large_voluntary_extra_shortens_from_end_without_covering_next_date() -> None:
    plan = plan_scheduled_or_voluntary_extra_allocation(
        transaction_amount=Decimal("250.00"),
        installments=(
            _installment(1),
            _installment(2),
            _installment(3),
            _installment(4),
        ),
        voluntary_extra=True,
    )

    assert [(row.installment_number, row.amount_applied, row.allocation_basis) for row in plan] == [
        (1, Decimal("100.00"), "oldest_due_first"),
        (4, Decimal("100.00"), "voluntary_extra_tail"),
        (3, Decimal("50.00"), "voluntary_extra_tail"),
    ]
    assert 2 not in {row.installment_number for row in plan}


def test_voluntary_extra_cannot_exceed_exact_remaining_contract_balance() -> None:
    with pytest.raises(PaymentAllocationError, match="exact payoff"):
        plan_scheduled_or_voluntary_extra_allocation(
            transaction_amount=Decimal("401.00"),
            installments=(
                _installment(1),
                _installment(2),
                _installment(3),
                _installment(4),
            ),
            voluntary_extra=True,
        )
