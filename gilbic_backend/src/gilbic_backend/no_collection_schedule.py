from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable


class NoCollectionScheduleError(ValueError):
    """Raised when a No Collection schedule shift cannot be planned safely."""


@dataclass(frozen=True, slots=True)
class OperationalInstallment:
    installment_id: int
    installment_number: int
    contractual_due_date: date
    effective_due_date: date
    contractual_amount: Decimal
    allocated_amount: Decimal = Decimal("0.00")


@dataclass(frozen=True, slots=True)
class ScheduleShift:
    installment_id: int
    installment_number: int
    contractual_due_date: date
    prior_effective_due_date: date
    new_effective_due_date: date
    contractual_amount: Decimal


def plan_no_collection_shift(
    *,
    installments: Iterable[OperationalInstallment],
    no_collection_date: date,
    payment_frequency: str,
    blocked_dates: Iterable[date] = (),
    semi_monthly_days: tuple[int, int] = (15, 30),
) -> tuple[ScheduleShift, ...]:
    """Move the affected installment and every later row one cadence slot.

    Signed contractual dates remain immutable evidence. This planner operates on
    current effective dates. Management No Collection is a pre-collection-day
    schedule decision, so an allocation already attached to an affected future
    installment is treated as prepayment evidence (Advance) and moves with that
    installment id instead of blocking the shift. The allocation itself is never
    rewritten or detached.

    A caller that attempts to declare No Collection after same-day collection has
    started violates the Management pre-declaration contract and must be rejected
    by the surrounding workflow/audit gate rather than reinterpreted here.
    """

    rows = tuple(
        sorted(
            installments,
            key=lambda item: (
                item.effective_due_date,
                item.installment_number,
                item.installment_id,
            ),
        )
    )
    if not rows:
        raise NoCollectionScheduleError(
            "The verified schedule has no installments to adjust."
        )

    for row in rows:
        if row.allocated_amount < Decimal("0.00"):
            raise NoCollectionScheduleError(
                "An installment allocation cannot be negative."
            )
        if row.allocated_amount > row.contractual_amount:
            raise NoCollectionScheduleError(
                "An installment is allocated beyond its contractual amount and requires Management reconciliation."
            )

    target_indexes = [
        index
        for index, row in enumerate(rows)
        if row.effective_due_date == no_collection_date
    ]
    if not target_indexes:
        raise NoCollectionScheduleError(
            "No installment is operationally due on the selected No Collection date."
        )
    if len(target_indexes) != 1:
        raise NoCollectionScheduleError(
            "The operational schedule has multiple installments on the selected date and requires Management review."
        )

    start = target_indexes[0]
    frequency = payment_frequency.strip().lower()
    if frequency in {"balloon", "custom"}:
        raise NoCollectionScheduleError(
            "This schedule needs an explicit Management date adjustment because its next cadence date cannot be inferred safely."
        )

    blocked = set(blocked_dates)
    blocked.add(no_collection_date)
    current_dates = [row.effective_due_date for row in rows]
    monthly_anchor_day = rows[0].contractual_due_date.day
    shifts: list[ScheduleShift] = []
    previous_new: date | None = None

    for index in range(start, len(rows)):
        row = rows[index]
        if index + 1 < len(rows):
            candidate = current_dates[index + 1]
        else:
            candidate = _advance_cadence(
                row.effective_due_date,
                payment_frequency=frequency,
                semi_monthly_days=semi_monthly_days,
                monthly_anchor_day=monthly_anchor_day,
            )

        while candidate in blocked:
            candidate = _advance_cadence(
                candidate,
                payment_frequency=frequency,
                semi_monthly_days=semi_monthly_days,
                monthly_anchor_day=monthly_anchor_day,
            )

        if candidate <= row.effective_due_date:
            raise NoCollectionScheduleError(
                "The adjusted date must be later than the current effective due date."
            )
        if previous_new is not None and candidate <= previous_new:
            raise NoCollectionScheduleError(
                "The adjusted schedule would lose installment order."
            )

        shifts.append(
            ScheduleShift(
                installment_id=row.installment_id,
                installment_number=row.installment_number,
                contractual_due_date=row.contractual_due_date,
                prior_effective_due_date=row.effective_due_date,
                new_effective_due_date=candidate,
                contractual_amount=row.contractual_amount,
            )
        )
        previous_new = candidate

    return tuple(shifts)


def _advance_cadence(
    anchor: date,
    *,
    payment_frequency: str,
    semi_monthly_days: tuple[int, int],
    monthly_anchor_day: int,
) -> date:
    if payment_frequency == "daily":
        return anchor + timedelta(days=1)
    if payment_frequency == "weekly":
        return anchor + timedelta(days=7)
    if payment_frequency == "monthly":
        return _next_monthly(anchor, monthly_anchor_day)
    if payment_frequency == "semi_monthly":
        return _next_semi_monthly(anchor, semi_monthly_days)
    raise NoCollectionScheduleError(
        f"Unsupported operational No Collection frequency: {payment_frequency}."
    )


def _next_monthly(anchor: date, day: int) -> date:
    if day < 1 or day > 31:
        raise NoCollectionScheduleError("Monthly collection day is invalid.")
    zero_based = anchor.year * 12 + (anchor.month - 1) + 1
    year, month_index = divmod(zero_based, 12)
    month = month_index + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last_day))


def _next_semi_monthly(anchor: date, days: tuple[int, int]) -> date:
    normalized = tuple(sorted(set(days)))
    if len(normalized) != 2 or any(day < 1 or day > 31 for day in normalized):
        raise NoCollectionScheduleError(
            "Semi-monthly schedule needs two valid collection day numbers."
        )

    year = anchor.year
    month = anchor.month
    for _ in range(0, 25):
        last_day = calendar.monthrange(year, month)[1]
        candidates = sorted(
            {
                date(year, month, min(day, last_day))
                for day in normalized
            }
        )
        for candidate in candidates:
            if candidate > anchor:
                return candidate
        month += 1
        if month == 13:
            month = 1
            year += 1
    raise NoCollectionScheduleError(
        "Could not resolve the next semi-monthly collection date."
    )
