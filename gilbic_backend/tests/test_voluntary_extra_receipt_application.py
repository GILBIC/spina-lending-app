from __future__ import annotations

from datetime import date
from decimal import Decimal

from gilbic_backend.contract_schedule_engine import OutstandingInstallment
from gilbic_backend.voluntary_extra_collection_posting import (
    VoluntaryExtraAwareCollectionPostingBridge,
)


def installment(
    number: int,
    due: date,
    *,
    amount: str = "100.00",
    allocated: str = "0.00",
) -> OutstandingInstallment:
    return OutstandingInstallment(
        installment_id=number,
        installment_number=number,
        due_date=due,
        contractual_amount=Decimal(amount),
        allocated_amount=Decimal(allocated),
    )


def test_scheduled_payment_uses_only_due_installment() -> None:
    bridge = VoluntaryExtraAwareCollectionPostingBridge()
    plan = bridge._plan_applied_contract_payment(
        applied_amount=Decimal("100.00"),
        installments=(
            installment(1, date(2026, 8, 16)),
            installment(2, date(2026, 8, 17)),
            installment(3, date(2026, 8, 18)),
        ),
        collection_date=date(2026, 8, 16),
        voluntary_extra=False,
    )

    assert len(plan) == 1
    assert plan[0].installment_number == 1
    assert plan[0].amount_applied == Decimal("100.00")
    assert plan[0].allocation_basis == "oldest_due_first"


def test_voluntary_extra_after_today_due_allocates_from_contract_tail() -> None:
    bridge = VoluntaryExtraAwareCollectionPostingBridge()
    plan = bridge._plan_applied_contract_payment(
        applied_amount=Decimal("200.00"),
        installments=(
            installment(1, date(2026, 8, 16)),
            installment(2, date(2026, 8, 17)),
            installment(3, date(2026, 8, 18)),
        ),
        collection_date=date(2026, 8, 16),
        voluntary_extra=True,
    )

    assert [(row.installment_number, row.allocation_basis) for row in plan] == [
        (1, "oldest_due_first"),
        (3, "voluntary_extra_tail"),
    ]
    assert all(row.installment_number != 2 for row in plan)


def test_voluntary_extra_before_next_due_starts_at_tail_and_keeps_next_due_open() -> None:
    bridge = VoluntaryExtraAwareCollectionPostingBridge()
    plan = bridge._plan_applied_contract_payment(
        applied_amount=Decimal("100.00"),
        installments=(
            installment(1, date(2026, 8, 17)),
            installment(2, date(2026, 8, 18)),
            installment(3, date(2026, 8, 19)),
        ),
        collection_date=date(2026, 8, 16),
        voluntary_extra=True,
    )

    assert len(plan) == 1
    assert plan[0].installment_number == 3
    assert plan[0].allocation_basis == "voluntary_extra_tail"
    assert plan[0].due_date == date(2026, 8, 19)


def test_fully_unallocated_receipt_creates_no_contract_allocation() -> None:
    bridge = VoluntaryExtraAwareCollectionPostingBridge()
    plan = bridge._plan_applied_contract_payment(
        applied_amount=Decimal("0.00"),
        installments=(installment(1, date(2026, 8, 17)),),
        collection_date=date(2026, 8, 16),
        voluntary_extra=False,
    )

    assert plan == ()
