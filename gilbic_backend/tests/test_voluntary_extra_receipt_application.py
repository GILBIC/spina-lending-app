from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from gilbic_backend.contract_schedule_engine import OutstandingInstallment
from gilbic_backend.voluntary_extra_collection_posting import (
    VoluntaryExtraAwareCollectionPostingBridge,
)
from spina_mobile_collections.contracts import PaymentAllocationIntent
from spina_mobile_collections.service import CollectionRejected


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


def test_scheduled_payment_uses_only_required_due_amount_when_exact() -> None:
    bridge = VoluntaryExtraAwareCollectionPostingBridge()
    plan = bridge._plan_applied_contract_payment(
        applied_amount=Decimal("100.00"),
        installments=(
            installment(1, date(2026, 8, 16)),
            installment(2, date(2026, 8, 17)),
            installment(3, date(2026, 8, 18)),
        ),
        collection_date=date(2026, 8, 16),
    )

    assert len(plan) == 1
    assert plan[0].installment_number == 1
    assert plan[0].amount_applied == Decimal("100.00")
    assert plan[0].allocation_basis == "oldest_due_first"


def test_scheduled_cash_clears_multiple_past_due_rows_before_today() -> None:
    bridge = VoluntaryExtraAwareCollectionPostingBridge()
    plan = bridge._plan_applied_contract_payment(
        applied_amount=Decimal("250.00"),
        installments=(
            installment(1, date(2026, 8, 14), allocated="50.00"),
            installment(2, date(2026, 8, 15)),
            installment(3, date(2026, 8, 16)),
            installment(4, date(2026, 8, 17)),
        ),
        collection_date=date(2026, 8, 16),
    )

    assert [
        (row.installment_number, row.amount_applied, row.allocation_basis)
        for row in plan
    ] == [
        (1, Decimal("50.00"), "oldest_due_first"),
        (2, Decimal("100.00"), "oldest_due_first"),
        (3, Decimal("100.00"), "oldest_due_first"),
    ]


def test_scheduled_payment_uses_active_extension_slot_as_normal_catchup() -> None:
    bridge = VoluntaryExtraAwareCollectionPostingBridge()
    plan = bridge._plan_applied_contract_payment(
        applied_amount=Decimal("200.00"),
        installments=(
            installment(1, date(2026, 8, 16)),
            installment(2, date(2026, 8, 17)),
            installment(3, date(2026, 8, 18)),
        ),
        collection_date=date(2026, 8, 16),
        active_borrower_extension_slots=1,
    )

    assert [
        (row.installment_number, row.amount_applied, row.allocation_basis)
        for row in plan
    ] == [
        (1, Decimal("100.00"), "oldest_due_first"),
        (2, Decimal("100.00"), "borrower_catch_up_oldest_first"),
    ]


def test_scheduled_extra_fails_closed_until_borrower_chooses() -> None:
    bridge = VoluntaryExtraAwareCollectionPostingBridge()
    with pytest.raises(CollectionRejected) as error:
        bridge._plan_applied_contract_payment(
            applied_amount=Decimal("200.00"),
            installments=(
                installment(1, date(2026, 8, 16)),
                installment(2, date(2026, 8, 17)),
                installment(3, date(2026, 8, 18)),
            ),
            collection_date=date(2026, 8, 16),
        )

    assert error.value.code == "extra_allocation_choice_required"
    assert "Advance or Principal Reduction" in str(error.value)


def test_explicit_principal_reduction_uses_contract_tail() -> None:
    bridge = VoluntaryExtraAwareCollectionPostingBridge()
    plan = bridge._plan_applied_contract_payment(
        applied_amount=Decimal("200.00"),
        installments=(
            installment(1, date(2026, 8, 16)),
            installment(2, date(2026, 8, 17)),
            installment(3, date(2026, 8, 18)),
        ),
        collection_date=date(2026, 8, 16),
        allocation_intent=PaymentAllocationIntent.EXTRA_AS_PRINCIPAL_REDUCTION,
    )

    assert [(row.installment_number, row.allocation_basis) for row in plan] == [
        (1, "oldest_due_first"),
        (3, "voluntary_extra_tail"),
    ]
    assert all(row.installment_number != 2 for row in plan)


def test_explicit_advance_uses_oldest_future_obligation() -> None:
    bridge = VoluntaryExtraAwareCollectionPostingBridge()
    plan = bridge._plan_applied_contract_payment(
        applied_amount=Decimal("250.00"),
        installments=(
            installment(1, date(2026, 8, 16)),
            installment(2, date(2026, 8, 17)),
            installment(3, date(2026, 8, 18)),
        ),
        collection_date=date(2026, 8, 16),
        allocation_intent=PaymentAllocationIntent.EXTRA_AS_ADVANCE,
    )

    assert [
        (row.installment_number, row.amount_applied, row.allocation_basis)
        for row in plan
    ] == [
        (1, Decimal("100.00"), "oldest_due_first"),
        (2, Decimal("100.00"), "future_advance_oldest_first"),
        (3, Decimal("50.00"), "future_advance_oldest_first"),
    ]


def test_payment_before_next_due_requires_explicit_extra_choice() -> None:
    bridge = VoluntaryExtraAwareCollectionPostingBridge()
    with pytest.raises(CollectionRejected) as error:
        bridge._plan_applied_contract_payment(
            applied_amount=Decimal("100.00"),
            installments=(
                installment(1, date(2026, 8, 17)),
                installment(2, date(2026, 8, 18)),
                installment(3, date(2026, 8, 19)),
            ),
            collection_date=date(2026, 8, 16),
        )

    assert error.value.code == "extra_allocation_choice_required"


def test_legacy_voluntary_extra_does_not_silently_mean_principal_reduction() -> None:
    bridge = VoluntaryExtraAwareCollectionPostingBridge()
    with pytest.raises(CollectionRejected) as error:
        bridge._plan_applied_contract_payment(
            applied_amount=Decimal("200.00"),
            installments=(
                installment(1, date(2026, 8, 16)),
                installment(2, date(2026, 8, 17)),
                installment(3, date(2026, 8, 18)),
            ),
            collection_date=date(2026, 8, 16),
            allocation_intent=PaymentAllocationIntent.VOLUNTARY_EXTRA,
        )

    assert error.value.code == "extra_allocation_choice_required"


def test_zero_applied_receipt_creates_no_contract_allocation() -> None:
    bridge = VoluntaryExtraAwareCollectionPostingBridge()
    plan = bridge._plan_applied_contract_payment(
        applied_amount=Decimal("0.00"),
        installments=(installment(1, date(2026, 8, 17)),),
        collection_date=date(2026, 8, 16),
    )

    assert plan == ()
