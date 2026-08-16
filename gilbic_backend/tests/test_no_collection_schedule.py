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


def test_no_collection_refuses_to_move_a_paid_downstream_installment() -> None:
    rows = (
        _row(1, date(2026, 8, 16)),
        _row(2, date(2026, 8, 17), allocated="200.00"),
        _row(3, date(2026, 8, 18)),
    )

    with pytest.raises(NoCollectionScheduleError, match="already has payment allocation"):
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
