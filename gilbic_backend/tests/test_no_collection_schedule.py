from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from gilbic_backend.no_collection_schedule import (
    NoCollectionScheduleError,
    OperationalInstallment,
    plan_no_collection_shift,
)


def _row(number: int, due: date, *, allocated: str = "0.00") -> OperationalInstallment:
    return OperationalInstallment(
        installment_id=number,
        installment_number=number,
        contractual_due_date=due,
        effective_due_date=due,
        contractual_amount=Decimal("200.00"),
        allocated_amount=Decimal(allocated),
    )


def test_daily_no_collection_moves_target_and_every_later_installment_one_slot() -> None:
    rows = tuple(
        _row(index, date(2026, 8, 15 + index))
        for index in range(1, 5)
    )

    shifts = plan_no_collection_shift(
        installments=rows,
        no_collection_date=date(2026, 8, 17),
        payment_frequency="daily",
    )

    assert [item.installment_number for item in shifts] == [2, 3, 4]
    assert [item.prior_effective_due_date for item in shifts] == [
        date(2026, 8, 17),
        date(2026, 8, 18),
        date(2026, 8, 19),
    ]
    assert [item.new_effective_due_date for item in shifts] == [
        date(2026, 8, 18),
        date(2026, 8, 19),
        date(2026, 8, 20),
    ]


def test_consecutive_no_collection_uses_current_effective_dates_without_rewriting_contract() -> None:
    rows = (
        OperationalInstallment(
            installment_id=1,
            installment_number=1,
            contractual_due_date=date(2026, 8, 16),
            effective_due_date=date(2026, 8, 16),
            contractual_amount=Decimal("200.00"),
        ),
        OperationalInstallment(
            installment_id=2,
            installment_number=2,
            contractual_due_date=date(2026, 8, 17),
            effective_due_date=date(2026, 8, 18),
            contractual_amount=Decimal("200.00"),
        ),
        OperationalInstallment(
            installment_id=3,
            installment_number=3,
            contractual_due_date=date(2026, 8, 18),
            effective_due_date=date(2026, 8, 19),
            contractual_amount=Decimal("200.00"),
        ),
    )

    shifts = plan_no_collection_shift(
        installments=rows,
        no_collection_date=date(2026, 8, 18),
        payment_frequency="daily",
        blocked_dates=(date(2026, 8, 17),),
    )

    assert [item.contractual_due_date for item in shifts] == [
        date(2026, 8, 17),
        date(2026, 8, 18),
    ]
    assert [item.prior_effective_due_date for item in shifts] == [
        date(2026, 8, 18),
        date(2026, 8, 19),
    ]
    assert [item.new_effective_due_date for item in shifts] == [
        date(2026, 8, 19),
        date(2026, 8, 20),
    ]


def test_weekly_no_collection_preserves_weekly_cadence() -> None:
    rows = (
        _row(1, date(2026, 8, 7)),
        _row(2, date(2026, 8, 14)),
        _row(3, date(2026, 8, 21)),
    )

    shifts = plan_no_collection_shift(
        installments=rows,
        no_collection_date=date(2026, 8, 14),
        payment_frequency="weekly",
    )

    assert [item.new_effective_due_date for item in shifts] == [
        date(2026, 8, 21),
        date(2026, 8, 28),
    ]


def test_semi_monthly_no_collection_uses_the_loan_collection_days() -> None:
    rows = (
        _row(1, date(2026, 8, 10)),
        _row(2, date(2026, 8, 25)),
        _row(3, date(2026, 9, 10)),
    )

    shifts = plan_no_collection_shift(
        installments=rows,
        no_collection_date=date(2026, 8, 25),
        payment_frequency="semi_monthly",
        semi_monthly_days=(10, 25),
    )

    assert [item.new_effective_due_date for item in shifts] == [
        date(2026, 9, 10),
        date(2026, 9, 25),
    ]


def test_monthly_no_collection_preserves_original_anchor_after_clamping() -> None:
    rows = (
        _row(1, date(2026, 1, 31)),
        _row(2, date(2026, 2, 28)),
    )

    shifts = plan_no_collection_shift(
        installments=rows,
        no_collection_date=date(2026, 2, 28),
        payment_frequency="monthly",
    )

    assert shifts[0].new_effective_due_date == date(2026, 3, 31)


def test_no_collection_moves_fully_prepaid_future_installment_with_its_evidence() -> None:
    rows = (
        _row(1, date(2026, 8, 16)),
        _row(2, date(2026, 8, 17), allocated="200.00"),
        _row(3, date(2026, 8, 18)),
    )

    shifts = plan_no_collection_shift(
        installments=rows,
        no_collection_date=date(2026, 8, 16),
        payment_frequency="daily",
    )

    assert [item.installment_id for item in shifts] == [1, 2, 3]
    assert shifts[1].prior_effective_due_date == date(2026, 8, 17)
    assert shifts[1].new_effective_due_date == date(2026, 8, 18)


def test_no_collection_moves_partly_prepaid_future_installment_without_reshaping_amount() -> None:
    rows = (
        _row(1, date(2026, 8, 16)),
        _row(2, date(2026, 8, 17), allocated="120.00"),
        _row(3, date(2026, 8, 18)),
    )

    shifts = plan_no_collection_shift(
        installments=rows,
        no_collection_date=date(2026, 8, 16),
        payment_frequency="daily",
    )

    assert shifts[1].installment_id == 2
    assert shifts[1].contractual_amount == Decimal("200.00")
    assert shifts[1].new_effective_due_date == date(2026, 8, 18)


def test_no_collection_moves_fully_prepaid_target_with_its_advance_evidence() -> None:
    rows = (
        _row(1, date(2026, 8, 16), allocated="200.00"),
        _row(2, date(2026, 8, 17)),
    )

    shifts = plan_no_collection_shift(
        installments=rows,
        no_collection_date=date(2026, 8, 16),
        payment_frequency="daily",
    )

    assert [item.installment_id for item in shifts] == [1, 2]
    assert shifts[0].prior_effective_due_date == date(2026, 8, 16)
    assert shifts[0].new_effective_due_date == date(2026, 8, 17)


def test_no_collection_keeps_partial_target_attached_and_shifts_its_remainder() -> None:
    rows = (
        _row(1, date(2026, 8, 16), allocated="120.00"),
        _row(2, date(2026, 8, 17)),
    )

    shifts = plan_no_collection_shift(
        installments=rows,
        no_collection_date=date(2026, 8, 16),
        payment_frequency="daily",
    )

    assert shifts[0].installment_id == 1
    assert shifts[0].contractual_amount == Decimal("200.00")
    assert shifts[0].prior_effective_due_date == date(2026, 8, 16)
    assert shifts[0].new_effective_due_date == date(2026, 8, 17)


def test_no_collection_fails_closed_if_allocation_exceeds_contractual_row() -> None:
    rows = (
        _row(1, date(2026, 8, 16)),
        _row(2, date(2026, 8, 17), allocated="200.01"),
    )

    with pytest.raises(NoCollectionScheduleError, match="beyond its contractual amount"):
        plan_no_collection_shift(
            installments=rows,
            no_collection_date=date(2026, 8, 16),
            payment_frequency="daily",
        )


def test_custom_and_balloon_schedules_fail_closed() -> None:
    rows = (_row(1, date(2026, 8, 16)),)

    for frequency in ("custom", "balloon"):
        with pytest.raises(NoCollectionScheduleError, match="explicit Management date adjustment"):
            plan_no_collection_shift(
                installments=rows,
                no_collection_date=date(2026, 8, 16),
                payment_frequency=frequency,
            )


def test_previously_blocked_last_target_is_skipped_again() -> None:
    rows = (
        _row(1, date(2026, 8, 16)),
        _row(2, date(2026, 8, 17)),
    )

    shifts = plan_no_collection_shift(
        installments=rows,
        no_collection_date=date(2026, 8, 17),
        payment_frequency="daily",
        blocked_dates=(date(2026, 8, 18),),
    )

    assert shifts[0].new_effective_due_date == date(2026, 8, 19)
