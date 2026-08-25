from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable


MONEY = Decimal("0.01")
ZERO = Decimal("0.00")


class RollingScheduleError(ValueError):
    """Raised when rolling maturity cannot be projected without guessing."""


@dataclass(frozen=True, slots=True)
class RollingScheduleInstallment:
    installment_id: int
    installment_number: int
    contractual_due_date: date
    effective_due_date: date
    remaining_amount: Decimal


@dataclass(frozen=True, slots=True)
class RollingScheduleProjection:
    base_maturity: date | None
    updated_maturity: date | None
    extension_slots: int
    past_due_count: int
    past_due_amount: Decimal
    projection_status: str


def project_rolling_schedule(
    *,
    installments: Iterable[RollingScheduleInstallment],
    as_of_date: date,
    payment_frequency: str,
    blocked_dates: Iterable[date] = (),
    semi_monthly_days: tuple[int, int] = (15, 30),
) -> RollingScheduleProjection:
    """Project SPINA's dynamic maturity extension without rewriting evidence.

    The signed/Management-adjusted installment dates remain the authoritative
    evidence for obligations already reached. A scheduled row strictly before
    ``as_of_date`` that is still not fully satisfied contributes one rolling
    extension slot. This preserves the approved Collector behavior where a
    borrower can simultaneously have Past Due from yesterday and the normal
    scheduled amount Due Today.

    When the borrower catches up and every earlier row is fully satisfied, the
    extension slot disappears automatically and maturity returns to the current
    operational schedule. This projection is intentionally derived instead of
    persisted, so catch-up never requires rewriting immutable Past Due history.
    """

    rows = tuple(
        sorted(
            installments,
            key=lambda row: (
                row.effective_due_date,
                row.installment_number,
                row.installment_id,
            ),
        )
    )
    if not rows:
        return RollingScheduleProjection(
            base_maturity=None,
            updated_maturity=None,
            extension_slots=0,
            past_due_count=0,
            past_due_amount=ZERO,
            projection_status="no_current_installments",
        )

    past_due = tuple(
        row
        for row in rows
        if row.effective_due_date < as_of_date
        and _money(row.remaining_amount) > ZERO
    )
    extension_slots = len(past_due)
    past_due_amount = _money(
        sum((_money(row.remaining_amount) for row in past_due), ZERO)
    )
    base_maturity = max(row.effective_due_date for row in rows)

    if extension_slots == 0:
        return RollingScheduleProjection(
            base_maturity=base_maturity,
            updated_maturity=base_maturity,
            extension_slots=0,
            past_due_count=0,
            past_due_amount=ZERO,
            projection_status="on_schedule",
        )

    frequency = payment_frequency.strip().lower()
    if frequency in {"balloon", "custom"}:
        return RollingScheduleProjection(
            base_maturity=base_maturity,
            updated_maturity=None,
            extension_slots=extension_slots,
            past_due_count=extension_slots,
            past_due_amount=past_due_amount,
            projection_status="cadence_requires_management",
        )

    monthly_anchor_day = rows[0].contractual_due_date.day
    blocked = set(blocked_dates)
    updated_maturity = base_maturity
    for _ in range(extension_slots):
        updated_maturity = _advance_cadence(
            updated_maturity,
            payment_frequency=frequency,
            semi_monthly_days=semi_monthly_days,
            monthly_anchor_day=monthly_anchor_day,
        )
        while updated_maturity in blocked:
            updated_maturity = _advance_cadence(
                updated_maturity,
                payment_frequency=frequency,
                semi_monthly_days=semi_monthly_days,
                monthly_anchor_day=monthly_anchor_day,
            )

    return RollingScheduleProjection(
        base_maturity=base_maturity,
        updated_maturity=updated_maturity,
        extension_slots=extension_slots,
        past_due_count=extension_slots,
        past_due_amount=past_due_amount,
        projection_status="extended",
    )


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
    raise RollingScheduleError(
        f"Unsupported rolling schedule frequency: {payment_frequency}."
    )


def _next_monthly(anchor: date, day: int) -> date:
    if day < 1 or day > 31:
        raise RollingScheduleError("Monthly collection day is invalid.")
    zero_based = anchor.year * 12 + (anchor.month - 1) + 1
    year, month_index = divmod(zero_based, 12)
    month = month_index + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last_day))


def _next_semi_monthly(anchor: date, days: tuple[int, int]) -> date:
    normalized = tuple(sorted(set(days)))
    if len(normalized) != 2 or any(day < 1 or day > 31 for day in normalized):
        raise RollingScheduleError(
            "Semi-monthly schedule needs two valid collection day numbers."
        )

    year = anchor.year
    month = anchor.month
    for _ in range(25):
        last_day = calendar.monthrange(year, month)[1]
        candidates = sorted(
            {date(year, month, min(day, last_day)) for day in normalized}
        )
        for candidate in candidates:
            if candidate > anchor:
                return candidate
        month += 1
        if month == 13:
            month = 1
            year += 1
    raise RollingScheduleError(
        "Could not resolve the next semi-monthly collection date."
    )


def _money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)
