from __future__ import annotations

from datetime import date
from typing import Iterable

from .no_collection_schedule import (
    NoCollectionScheduleError,
    OperationalInstallment,
    ScheduleShift,
    plan_no_collection_shift,
)


class SevenBySevenNoCollectionCompletionScheduleError(ValueError):
    """Raised when one NC shift cannot be removed from verified 7x7 history."""

    code = "seven_by_seven_no_collection_completion_schedule_conflict"


def plan_seven_by_seven_no_collection_completion_restoration(
    *,
    installments: Iterable[OperationalInstallment],
    active_no_collection_dates: Iterable[date],
    source_no_collection_date: date,
) -> tuple[ScheduleShift, ...]:
    """Remove one completed 7x7 No Collection shift without inventing a reversal.

    ``active_no_collection_dates`` must be supplied in operational-adjustment
    order. The helper first replays every active Management No Collection date
    from immutable contractual dates and proves that the result still matches
    the current operational schedule. It then replays the same history with only
    ``source_no_collection_date`` omitted.

    This preserves earlier and later No Collection shifts, including consecutive
    holidays. The source Management declaration remains historical evidence; the
    returned rows describe only the operational-date changes required by the
    borrower's separate full-voluntary-completion adjustment.

    This helper is deliberately 7x7/daily only. Any unexplained schedule drift,
    duplicate holiday date, missing source holiday, or replay conflict fails
    closed for Management review rather than guessing a new schedule.
    """

    rows = tuple(installments)
    if not rows:
        raise SevenBySevenNoCollectionCompletionScheduleError(
            "The verified 7x7 schedule has no installments to restore."
        )

    ids = [row.installment_id for row in rows]
    if len(set(ids)) != len(ids):
        raise SevenBySevenNoCollectionCompletionScheduleError(
            "The verified 7x7 schedule contains duplicate installment identifiers."
        )

    active_dates = tuple(active_no_collection_dates)
    if len(set(active_dates)) != len(active_dates):
        raise SevenBySevenNoCollectionCompletionScheduleError(
            "Active No Collection history contains a duplicate date and requires Management review."
        )
    if active_dates.count(source_no_collection_date) != 1:
        raise SevenBySevenNoCollectionCompletionScheduleError(
            "The source No Collection date is not active exactly once."
        )

    expected_current = _replay_daily_no_collection_history(
        rows=rows,
        active_no_collection_dates=active_dates,
    )
    expected_current_by_id = {
        row.installment_id: row.effective_due_date for row in expected_current
    }
    for row in rows:
        if row.effective_due_date != expected_current_by_id[row.installment_id]:
            raise SevenBySevenNoCollectionCompletionScheduleError(
                "The current operational 7x7 schedule no longer matches active No Collection history. Management reconciliation is required."
            )

    remaining_dates = tuple(
        value for value in active_dates if value != source_no_collection_date
    )
    restored = _replay_daily_no_collection_history(
        rows=rows,
        active_no_collection_dates=remaining_dates,
    )
    restored_by_id = {row.installment_id: row for row in restored}

    changes: list[ScheduleShift] = []
    for row in sorted(
        rows,
        key=lambda item: (
            item.installment_number,
            item.contractual_due_date,
            item.installment_id,
        ),
    ):
        target = restored_by_id[row.installment_id]
        if row.effective_due_date == target.effective_due_date:
            continue
        changes.append(
            ScheduleShift(
                installment_id=row.installment_id,
                installment_number=row.installment_number,
                contractual_due_date=row.contractual_due_date,
                prior_effective_due_date=row.effective_due_date,
                new_effective_due_date=target.effective_due_date,
                contractual_amount=row.contractual_amount,
            )
        )

    if not changes:
        raise SevenBySevenNoCollectionCompletionScheduleError(
            "Removing the source No Collection would not change the operational schedule. Management review is required."
        )
    return tuple(changes)


def _replay_daily_no_collection_history(
    *,
    rows: tuple[OperationalInstallment, ...],
    active_no_collection_dates: tuple[date, ...],
) -> tuple[OperationalInstallment, ...]:
    replayed = tuple(
        OperationalInstallment(
            installment_id=row.installment_id,
            installment_number=row.installment_number,
            contractual_due_date=row.contractual_due_date,
            effective_due_date=row.contractual_due_date,
            contractual_amount=row.contractual_amount,
            allocated_amount=row.allocated_amount,
        )
        for row in rows
    )
    blocked_dates: list[date] = []

    for no_collection_date in active_no_collection_dates:
        try:
            shifts = plan_no_collection_shift(
                installments=replayed,
                no_collection_date=no_collection_date,
                payment_frequency="daily",
                blocked_dates=tuple(blocked_dates),
            )
        except NoCollectionScheduleError as error:
            raise SevenBySevenNoCollectionCompletionScheduleError(
                "Active No Collection history cannot be replayed safely against the signed 7x7 schedule."
            ) from error

        shifted_dates = {
            shift.installment_id: shift.new_effective_due_date for shift in shifts
        }
        replayed = tuple(
            OperationalInstallment(
                installment_id=row.installment_id,
                installment_number=row.installment_number,
                contractual_due_date=row.contractual_due_date,
                effective_due_date=shifted_dates.get(
                    row.installment_id,
                    row.effective_due_date,
                ),
                contractual_amount=row.contractual_amount,
                allocated_amount=row.allocated_amount,
            )
            for row in replayed
        )
        blocked_dates.append(no_collection_date)

    return replayed
