from datetime import date
from decimal import Decimal

import pytest

from gilbic_backend.contract_schedule_engine import (
    ContractScheduleError,
    OutstandingInstallment,
    PaymentAllocationError,
    generate_contract_installments,
    plan_payment_allocation,
)


def test_daily_and_weekly_schedules_follow_contract_dates() -> None:
    daily = generate_contract_installments(
        payment_frequency="daily",
        contractual_total=Decimal("270.00"),
        first_due_date=date(2026, 8, 10),
        installment_count=3,
        regular_installment_amount=Decimal("90.00"),
    )
    assert [row.due_date for row in daily] == [
        date(2026, 8, 10),
        date(2026, 8, 11),
        date(2026, 8, 12),
    ]
    assert [row.contractual_amount for row in daily] == [
        Decimal("90.00"),
        Decimal("90.00"),
        Decimal("90.00"),
    ]

    weekly = generate_contract_installments(
        payment_frequency="weekly",
        contractual_total=Decimal("1500.00"),
        first_due_date=date(2026, 8, 14),
        installment_count=3,
        regular_installment_amount=Decimal("500.00"),
    )
    assert [row.due_date for row in weekly] == [
        date(2026, 8, 14),
        date(2026, 8, 21),
        date(2026, 8, 28),
    ]


def test_semi_monthly_15_30_clamps_to_month_end() -> None:
    rows = generate_contract_installments(
        payment_frequency="semi_monthly",
        contractual_total=Decimal("4000.00"),
        first_due_date=date(2027, 1, 15),
        installment_count=4,
        regular_installment_amount=Decimal("1000.00"),
        semi_monthly_days=(15, 30),
    )
    assert [row.due_date for row in rows] == [
        date(2027, 1, 15),
        date(2027, 1, 30),
        date(2027, 2, 15),
        date(2027, 2, 28),
    ]


def test_monthly_month_end_and_balloon_are_exact() -> None:
    monthly = generate_contract_installments(
        payment_frequency="monthly",
        contractual_total=Decimal("3000.00"),
        first_due_date=date(2027, 1, 31),
        installment_count=3,
        regular_installment_amount=Decimal("1000.00"),
    )
    assert [row.due_date for row in monthly] == [
        date(2027, 1, 31),
        date(2027, 2, 28),
        date(2027, 3, 31),
    ]

    balloon = generate_contract_installments(
        payment_frequency="balloon",
        contractual_total=Decimal("10000.00"),
        first_due_date=date(2027, 6, 30),
        installment_count=1,
    )
    assert len(balloon) == 1
    assert balloon[0].due_date == date(2027, 6, 30)
    assert balloon[0].contractual_amount == Decimal("10000.00")


def test_equal_distribution_keeps_cent_exact_total() -> None:
    rows = generate_contract_installments(
        payment_frequency="weekly",
        contractual_total=Decimal("1000.00"),
        first_due_date=date(2026, 8, 14),
        installment_count=3,
    )
    assert [row.contractual_amount for row in rows] == [
        Decimal("333.33"),
        Decimal("333.33"),
        Decimal("333.34"),
    ]
    assert sum(row.contractual_amount for row in rows) == Decimal("1000.00")


def test_custom_schedule_requires_exact_increasing_contract_rows() -> None:
    rows = generate_contract_installments(
        payment_frequency="custom",
        contractual_total=Decimal("700.00"),
        custom_installments=(
            (date(2026, 8, 20), Decimal("200.00")),
            (date(2026, 9, 5), Decimal("500.00")),
        ),
    )
    assert [row.contractual_amount for row in rows] == [
        Decimal("200.00"),
        Decimal("500.00"),
    ]

    with pytest.raises(ContractScheduleError):
        generate_contract_installments(
            payment_frequency="custom",
            contractual_total=Decimal("701.00"),
            custom_installments=(
                (date(2026, 8, 20), Decimal("200.00")),
                (date(2026, 9, 5), Decimal("500.00")),
            ),
        )


def test_payment_today_when_today_is_already_covered_moves_to_next_unpaid_contract_date() -> None:
    installments = (
        OutstandingInstallment(
            installment_id=1,
            installment_number=1,
            due_date=date(2026, 8, 14),
            contractual_amount=Decimal("90.00"),
            allocated_amount=Decimal("90.00"),
        ),
        OutstandingInstallment(
            installment_id=2,
            installment_number=2,
            due_date=date(2026, 8, 15),
            contractual_amount=Decimal("90.00"),
        ),
        OutstandingInstallment(
            installment_id=3,
            installment_number=3,
            due_date=date(2026, 8, 16),
            contractual_amount=Decimal("90.00"),
        ),
    )
    plan = plan_payment_allocation(
        transaction_amount=Decimal("90.00"),
        installments=installments,
    )
    assert len(plan) == 1
    assert plan[0].installment_id == 2
    assert plan[0].due_date == date(2026, 8, 15)
    assert plan[0].allocation_basis == "oldest_due_first"


def test_weekly_advance_allocates_next_weekly_contract_dates_not_calendar_days() -> None:
    installments = tuple(
        OutstandingInstallment(
            installment_id=index,
            installment_number=index,
            due_date=due,
            contractual_amount=Decimal("500.00"),
        )
        for index, due in enumerate(
            (date(2026, 8, 14), date(2026, 8, 21), date(2026, 8, 28)),
            start=1,
        )
    )
    plan = plan_payment_allocation(
        transaction_amount=Decimal("1000.00"),
        installments=installments,
    )
    assert [row.due_date for row in plan] == [date(2026, 8, 14), date(2026, 8, 21)]
    assert [row.amount_applied for row in plan] == [Decimal("500.00"), Decimal("500.00")]


def test_partial_payment_keeps_same_contract_installment_partially_unpaid() -> None:
    plan = plan_payment_allocation(
        transaction_amount=Decimal("40.00"),
        installments=(
            OutstandingInstallment(
                installment_id=1,
                installment_number=1,
                due_date=date(2026, 8, 1),
                contractual_amount=Decimal("100.00"),
            ),
        ),
    )
    assert plan[0].amount_applied == Decimal("40.00")


def test_explicit_advance_dates_must_be_real_unpaid_contract_due_dates() -> None:
    installments = (
        OutstandingInstallment(
            installment_id=1,
            installment_number=1,
            due_date=date(2026, 8, 15),
            contractual_amount=Decimal("90.00"),
        ),
        OutstandingInstallment(
            installment_id=2,
            installment_number=2,
            due_date=date(2026, 8, 16),
            contractual_amount=Decimal("90.00"),
        ),
    )
    plan = plan_payment_allocation(
        transaction_amount=Decimal("90.00"),
        installments=installments,
        explicit_covered_dates=(date(2026, 8, 16),),
    )
    assert plan[0].installment_id == 2
    assert plan[0].allocation_basis == "exact_covered_date"

    with pytest.raises(PaymentAllocationError):
        plan_payment_allocation(
            transaction_amount=Decimal("90.00"),
            installments=installments,
            explicit_covered_dates=(date(2026, 8, 17),),
        )


def test_payment_cannot_silently_exceed_remaining_contractual_balance() -> None:
    with pytest.raises(PaymentAllocationError):
        plan_payment_allocation(
            transaction_amount=Decimal("200.00"),
            installments=(
                OutstandingInstallment(
                    installment_id=1,
                    installment_number=1,
                    due_date=date(2026, 8, 15),
                    contractual_amount=Decimal("90.00"),
                ),
            ),
        )
