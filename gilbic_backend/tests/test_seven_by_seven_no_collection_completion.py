from datetime import date
from decimal import Decimal

import pytest

from gilbic_backend.no_collection_schedule import OperationalInstallment
from gilbic_backend.seven_by_seven_no_collection_completion import (
    SevenBySevenNoCollectionCompletionScheduleError,
    plan_seven_by_seven_no_collection_completion_restoration,
)


def _row(number: int, contractual_day: int, effective_day: int) -> OperationalInstallment:
    return OperationalInstallment(
        installment_id=number,
        installment_number=number,
        contractual_due_date=date(2026, 8, contractual_day),
        effective_due_date=date(2026, 8, effective_day),
        contractual_amount=Decimal("50.00"),
    )


def test_full_voluntary_completion_removes_only_source_no_collection_shift() -> None:
    rows = (
        _row(1, 17, 18),
        _row(2, 18, 19),
        _row(3, 19, 20),
    )

    planned = plan_seven_by_seven_no_collection_completion_restoration(
        installments=rows,
        active_no_collection_dates=(date(2026, 8, 17),),
        source_no_collection_date=date(2026, 8, 17),
    )

    assert [item.installment_number for item in planned] == [1, 2, 3]
    assert [item.prior_effective_due_date for item in planned] == [
        date(2026, 8, 18),
        date(2026, 8, 19),
        date(2026, 8, 20),
    ]
    assert [item.new_effective_due_date for item in planned] == [
        date(2026, 8, 17),
        date(2026, 8, 18),
        date(2026, 8, 19),
    ]


def test_removing_first_of_two_consecutive_holidays_preserves_second_shift() -> None:
    rows = (
        _row(1, 17, 19),
        _row(2, 18, 20),
        _row(3, 19, 21),
    )

    planned = plan_seven_by_seven_no_collection_completion_restoration(
        installments=rows,
        active_no_collection_dates=(
            date(2026, 8, 17),
            date(2026, 8, 18),
        ),
        source_no_collection_date=date(2026, 8, 17),
    )

    assert [item.new_effective_due_date for item in planned] == [
        date(2026, 8, 17),
        date(2026, 8, 19),
        date(2026, 8, 20),
    ]


def test_removing_second_consecutive_holiday_preserves_first_shift() -> None:
    rows = (
        _row(1, 17, 19),
        _row(2, 18, 20),
        _row(3, 19, 21),
    )

    planned = plan_seven_by_seven_no_collection_completion_restoration(
        installments=rows,
        active_no_collection_dates=(
            date(2026, 8, 17),
            date(2026, 8, 18),
        ),
        source_no_collection_date=date(2026, 8, 18),
    )

    assert [item.new_effective_due_date for item in planned] == [
        date(2026, 8, 18),
        date(2026, 8, 19),
        date(2026, 8, 20),
    ]


def test_restoration_fails_closed_when_current_schedule_has_unexplained_drift() -> None:
    rows = (
        _row(1, 17, 18),
        _row(2, 18, 20),
        _row(3, 19, 21),
    )

    with pytest.raises(
        SevenBySevenNoCollectionCompletionScheduleError,
        match="no longer matches active No Collection history",
    ):
        plan_seven_by_seven_no_collection_completion_restoration(
            installments=rows,
            active_no_collection_dates=(date(2026, 8, 17),),
            source_no_collection_date=date(2026, 8, 17),
        )


def test_restoration_requires_one_active_source_holiday() -> None:
    rows = (
        _row(1, 17, 17),
        _row(2, 18, 18),
    )

    with pytest.raises(
        SevenBySevenNoCollectionCompletionScheduleError,
        match="not active exactly once",
    ):
        plan_seven_by_seven_no_collection_completion_restoration(
            installments=rows,
            active_no_collection_dates=(date(2026, 8, 18),),
            source_no_collection_date=date(2026, 8, 17),
        )


def test_restoration_rejects_duplicate_active_no_collection_dates() -> None:
    rows = (
        _row(1, 17, 19),
        _row(2, 18, 20),
    )

    with pytest.raises(
        SevenBySevenNoCollectionCompletionScheduleError,
        match="duplicate date",
    ):
        plan_seven_by_seven_no_collection_completion_restoration(
            installments=rows,
            active_no_collection_dates=(
                date(2026, 8, 17),
                date(2026, 8, 17),
            ),
            source_no_collection_date=date(2026, 8, 17),
        )
