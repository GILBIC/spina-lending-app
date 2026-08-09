from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import pytest

from gilbic_backend.contract_schedule_engine import (
    AllocationInstruction,
    ContractInstallment,
    OutstandingInstallment,
    PaymentAllocationError,
    generate_contract_installments,
    plan_payment_allocation,
)


MONEY = Decimal("0.01")


@dataclass
class SyntheticLoan:
    """Stateful fake loan that exercises the production contract engine.

    No database writes or live borrower data are used. Each payment is planned by
    the same production allocation function used by the contractual collection
    service. Voiding a synthetic receipt removes its allocations from the next
    outstanding-state calculation, mirroring the production void semantics.
    """

    name: str
    installments: tuple[ContractInstallment, ...]
    activated: bool = False
    allocations_by_transaction: dict[str, tuple[AllocationInstruction, ...]] = field(
        default_factory=dict
    )
    voided_transactions: set[str] = field(default_factory=set)

    def outstanding(self) -> tuple[OutstandingInstallment, ...]:
        allocated_by_installment: dict[int, Decimal] = {
            row.installment_number: Decimal("0.00") for row in self.installments
        }
        for transaction_id, allocations in self.allocations_by_transaction.items():
            if transaction_id in self.voided_transactions:
                continue
            for allocation in allocations:
                number = int(allocation.installment_number)
                allocated_by_installment[number] = (
                    allocated_by_installment[number] + allocation.amount_applied
                ).quantize(MONEY)

        return tuple(
            OutstandingInstallment(
                installment_id=row.installment_number,
                installment_number=row.installment_number,
                due_date=row.due_date,
                contractual_amount=row.contractual_amount,
                allocated_amount=allocated_by_installment[row.installment_number],
            )
            for row in self.installments
        )

    def pay(
        self,
        transaction_id: str,
        amount: Decimal,
        *,
        covered_dates: tuple[date, ...] = (),
    ) -> tuple[AllocationInstruction, ...]:
        if transaction_id in self.allocations_by_transaction:
            raise AssertionError("Synthetic transaction ids must be unique")
        plan = plan_payment_allocation(
            transaction_amount=amount,
            installments=self.outstanding(),
            explicit_covered_dates=covered_dates,
        )
        self.allocations_by_transaction[transaction_id] = plan
        return plan

    def void(self, transaction_id: str) -> None:
        if transaction_id not in self.allocations_by_transaction:
            raise AssertionError("Cannot void a synthetic transaction that was not posted")
        self.voided_transactions.add(transaction_id)

    def unpaid_on(self, due_date: date) -> Decimal:
        return sum(
            (row.remaining_amount for row in self.outstanding() if row.due_date == due_date),
            Decimal("0.00"),
        ).quantize(MONEY)

    def unpaid_total(self) -> Decimal:
        return sum(
            (row.remaining_amount for row in self.outstanding()),
            Decimal("0.00"),
        ).quantize(MONEY)

    def no_cash_classification(self, collection_date: date) -> str:
        """Model the collector decision after schedule coverage is known.

        A day with no unpaid contractual installment is normal no-cash activity;
        it must not become PASS. If an installment is actually due and unpaid,
        the collector must use Unable to pay/PASS instead.
        """

        return "pass_required" if self.unpaid_on(collection_date) > 0 else "no_cash"


def make_loan(
    name: str,
    *,
    payment_frequency: str,
    total: str,
    first_due_date: date | None = None,
    installment_count: int | None = None,
    installment_amount: str | None = None,
    semi_monthly_days: tuple[int, int] = (15, 30),
    custom_installments: tuple[tuple[date, Decimal], ...] = (),
) -> SyntheticLoan:
    return SyntheticLoan(
        name=name,
        installments=generate_contract_installments(
            payment_frequency=payment_frequency,  # type: ignore[arg-type]
            contractual_total=Decimal(total),
            first_due_date=first_due_date,
            installment_count=installment_count,
            regular_installment_amount=(
                Decimal(installment_amount) if installment_amount is not None else None
            ),
            semi_monthly_days=semi_monthly_days,
            custom_installments=custom_installments,
        ),
    )


def test_synthetic_portfolio_supports_every_contract_frequency_without_inference() -> None:
    daily = make_loan(
        "Daily",
        payment_frequency="daily",
        total="270.00",
        first_due_date=date(2026, 8, 10),
        installment_count=3,
        installment_amount="90.00",
    )
    weekly = make_loan(
        "Weekly",
        payment_frequency="weekly",
        total="1500.00",
        first_due_date=date(2026, 8, 14),
        installment_count=3,
        installment_amount="500.00",
    )
    semi_monthly = make_loan(
        "15/30",
        payment_frequency="semi_monthly",
        total="4000.00",
        first_due_date=date(2027, 1, 15),
        installment_count=4,
        installment_amount="1000.00",
        semi_monthly_days=(15, 30),
    )
    monthly = make_loan(
        "Monthly",
        payment_frequency="monthly",
        total="3000.00",
        first_due_date=date(2027, 1, 31),
        installment_count=3,
        installment_amount="1000.00",
    )
    balloon = make_loan(
        "Balloon",
        payment_frequency="balloon",
        total="10000.00",
        first_due_date=date(2027, 6, 30),
        installment_count=1,
    )
    custom = make_loan(
        "Custom",
        payment_frequency="custom",
        total="700.00",
        custom_installments=(
            (date(2026, 8, 20), Decimal("200.00")),
            (date(2026, 9, 5), Decimal("500.00")),
        ),
    )

    assert [row.due_date for row in daily.installments] == [
        date(2026, 8, 10),
        date(2026, 8, 11),
        date(2026, 8, 12),
    ]
    assert [row.due_date for row in weekly.installments] == [
        date(2026, 8, 14),
        date(2026, 8, 21),
        date(2026, 8, 28),
    ]
    assert [row.due_date for row in semi_monthly.installments] == [
        date(2027, 1, 15),
        date(2027, 1, 30),
        date(2027, 2, 15),
        date(2027, 2, 28),
    ]
    assert [row.due_date for row in monthly.installments] == [
        date(2027, 1, 31),
        date(2027, 2, 28),
        date(2027, 3, 31),
    ]
    assert balloon.unpaid_total() == Decimal("10000.00")
    assert [row.contractual_amount for row in custom.installments] == [
        Decimal("200.00"),
        Decimal("500.00"),
    ]


def test_synthetic_daily_sequence_adv_no_cash_extra_partial_pass_and_finish() -> None:
    loan = make_loan(
        "Daily sequence",
        payment_frequency="daily",
        total="450.00",
        first_due_date=date(2026, 8, 10),
        installment_count=5,
        installment_amount="90.00",
    )

    # Aug 10: borrower pays two exact contractual dates in advance.
    adv = loan.pay(
        "ADV-1",
        Decimal("180.00"),
        covered_dates=(date(2026, 8, 10), date(2026, 8, 11)),
    )
    assert [row.due_date for row in adv] == [date(2026, 8, 10), date(2026, 8, 11)]
    assert loan.unpaid_on(date(2026, 8, 11)) == Decimal("0.00")

    # Aug 11: no new money is normal because ADV already covered today's due.
    assert loan.no_cash_classification(date(2026, 8, 11)) == "no_cash"

    # If the borrower still hands over another 90 on Aug 11, it moves to Aug 12.
    extra = loan.pay("PAY-EXTRA", Decimal("90.00"))
    assert [(row.due_date, row.amount_applied) for row in extra] == [
        (date(2026, 8, 12), Decimal("90.00"))
    ]
    assert loan.no_cash_classification(date(2026, 8, 12)) == "no_cash"

    # Aug 13: only 40 is paid. The installment remains partly unpaid, so PASS is
    # appropriate if no further cash is received that day.
    partial = loan.pay("PAY-PARTIAL", Decimal("40.00"))
    assert [(row.due_date, row.amount_applied) for row in partial] == [
        (date(2026, 8, 13), Decimal("40.00"))
    ]
    assert loan.unpaid_on(date(2026, 8, 13)) == Decimal("50.00")
    assert loan.no_cash_classification(date(2026, 8, 13)) == "pass_required"

    # Later payment first completes the same partial installment, then the next
    # payment advances to the following contractual due date.
    completion = loan.pay("PAY-COMPLETE", Decimal("50.00"))
    assert [(row.due_date, row.amount_applied) for row in completion] == [
        (date(2026, 8, 13), Decimal("50.00"))
    ]
    final = loan.pay("PAY-FINAL", Decimal("90.00"))
    assert [(row.due_date, row.amount_applied) for row in final] == [
        (date(2026, 8, 14), Decimal("90.00"))
    ]
    assert loan.unpaid_total() == Decimal("0.00")


def test_synthetic_weekly_void_reopens_installment_and_repost_uses_same_due_date() -> None:
    loan = make_loan(
        "Weekly void",
        payment_frequency="weekly",
        total="1500.00",
        first_due_date=date(2026, 8, 14),
        installment_count=3,
        installment_amount="500.00",
    )

    first = loan.pay("PAY-W1", Decimal("500.00"))
    assert first[0].due_date == date(2026, 8, 14)
    assert loan.unpaid_on(date(2026, 8, 14)) == Decimal("0.00")

    loan.void("PAY-W1")
    assert loan.unpaid_on(date(2026, 8, 14)) == Decimal("500.00")

    repost = loan.pay("PAY-W1-REPOST", Decimal("500.00"))
    assert repost[0].due_date == date(2026, 8, 14)
    assert loan.unpaid_on(date(2026, 8, 14)) == Decimal("0.00")
    assert loan.unpaid_total() == Decimal("1000.00")


def test_synthetic_exact_adv_rejects_calendar_date_that_is_not_a_contract_due_date() -> None:
    loan = make_loan(
        "Weekly exact ADV",
        payment_frequency="weekly",
        total="1500.00",
        first_due_date=date(2026, 8, 14),
        installment_count=3,
        installment_amount="500.00",
    )

    with pytest.raises(PaymentAllocationError):
        loan.pay(
            "BAD-ADV",
            Decimal("500.00"),
            covered_dates=(date(2026, 8, 15),),
        )

    good = loan.pay(
        "GOOD-ADV",
        Decimal("1000.00"),
        covered_dates=(date(2026, 8, 14), date(2026, 8, 21)),
    )
    assert [row.due_date for row in good] == [date(2026, 8, 14), date(2026, 8, 21)]


def test_synthetic_overpayment_is_blocked_instead_of_spilling_past_contract() -> None:
    loan = make_loan(
        "Overpayment guard",
        payment_frequency="monthly",
        total="1000.00",
        first_due_date=date(2026, 8, 31),
        installment_count=1,
    )

    with pytest.raises(PaymentAllocationError):
        loan.pay("TOO-MUCH", Decimal("1000.01"))

    assert loan.unpaid_total() == Decimal("1000.00")


def test_synthetic_per_loan_activation_state_is_independent() -> None:
    first = make_loan(
        "Pilot loan",
        payment_frequency="daily",
        total="180.00",
        first_due_date=date(2026, 8, 10),
        installment_count=2,
        installment_amount="90.00",
    )
    second = make_loan(
        "Other same-product loan",
        payment_frequency="daily",
        total="180.00",
        first_due_date=date(2026, 8, 10),
        installment_count=2,
        installment_amount="90.00",
    )

    assert not first.activated
    assert not second.activated
    first.activated = True

    # The key pilot property: activating one fake loan has no effect on another
    # loan even when both have identical product/frequency terms.
    assert first.activated is True
    assert second.activated is False
