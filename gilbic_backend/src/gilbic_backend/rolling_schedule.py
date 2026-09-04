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
class RollingScheduleShift:
    installment_id: int
    installment_number: int
    contractual_due_date: date
    prior_effective_due_date: date
    new_effective_due_date: date


@dataclass(frozen=True, slots=True)
class RollingScheduleDayClose:
    business_date: date
    scheduled_count: int
    incomplete_count: int
    shortfall_amount: Decimal
    extension_slots_added: int
    close_status: str


@dataclass(frozen=True, slots=True)
class RollingScheduleProjection:
    base_maturity: date | None
    updated_maturity: date | None
    extension_slots: int
    past_due_count: int
    past_due_amount: Decimal
    projection_status: str
    finalized_through_date: date | None = None


def finalize_rolling_schedule_day(
    *,
    installments: Iterable[RollingScheduleInstallment],
    business_date: date,
) -> RollingScheduleDayClose:
    """Finalize one authoritative collection day from aggregate row state.

    Same-day receipts are deliberately not interpreted one-by-one here. The
    caller supplies the current remaining amount after every accepted receipt for
    the official business date. Only the final aggregate remainder can create a
    borrower-caused rolling extension slot.

    This function is pure decision logic. It does not rewrite signed schedule
    evidence or receipt history; persistence/audit wiring can store the returned
    close result separately.
    """

    due_rows = tuple(
        sorted(
            (
                row
                for row in installments
                if row.effective_due_date == business_date
            ),
            key=lambda row: (row.installment_number, row.installment_id),
        )
    )
    if not due_rows:
        return RollingScheduleDayClose(
            business_date=business_date,
            scheduled_count=0,
            incomplete_count=0,
            shortfall_amount=ZERO,
            extension_slots_added=0,
            close_status="no_scheduled_obligation",
        )

    incomplete = tuple(
        row for row in due_rows if _money(row.remaining_amount) > ZERO
    )
    shortfall = _money(
        sum((_money(row.remaining_amount) for row in incomplete), ZERO)
    )
    if not incomplete:
        return RollingScheduleDayClose(
            business_date=business_date,
            scheduled_count=len(due_rows),
            incomplete_count=0,
            shortfall_amount=ZERO,
            extension_slots_added=0,
            close_status="complete",
        )

    return RollingScheduleDayClose(
        business_date=business_date,
        scheduled_count=len(due_rows),
        incomplete_count=len(incomplete),
        shortfall_amount=shortfall,
        extension_slots_added=len(incomplete),
        close_status="shortfall",
    )


def plan_borrower_shortfall_shift(
    *,
    installments: Iterable[RollingScheduleInstallment],
    business_date: date,
    payment_frequency: str,
    blocked_dates: Iterable[date] = (),
    semi_monthly_days: tuple[int, int] = (15, 30),
) -> tuple[RollingScheduleShift, ...]:
    """Move one unresolved operational date and every later row one slot.

    The planner is intentionally pure. It plans changes to current effective
    dates only and never rewrites contractual dates, installment identity, or
    payment allocation evidence. Interior rows inherit the next row's current
    effective date so existing operational spacing is preserved. Only the tail
    needs cadence arithmetic.
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
        return ()

    first_incomplete_index = next(
        (
            index
            for index, row in enumerate(rows)
            if row.effective_due_date == business_date
            and _money(row.remaining_amount) > ZERO
        ),
        None,
    )
    if first_incomplete_index is None:
        return ()

    frequency = payment_frequency.strip().lower()
    if frequency in {"balloon", "custom"}:
        raise RollingScheduleError(
            "Borrower shortfall shift requires a deterministic payment cadence."
        )

    blocked = set(blocked_dates)
    monthly_anchor_day = rows[0].contractual_due_date.day
    planned: list[RollingScheduleShift] = []

    for index in range(first_incomplete_index, len(rows)):
        row = rows[index]
        if index + 1 < len(rows):
            new_due_date = rows[index + 1].effective_due_date
        else:
            new_due_date = _advance_cadence(
                row.effective_due_date,
                payment_frequency=frequency,
                semi_monthly_days=semi_monthly_days,
                monthly_anchor_day=monthly_anchor_day,
            )
            while new_due_date in blocked:
                new_due_date = _advance_cadence(
                    new_due_date,
                    payment_frequency=frequency,
                    semi_monthly_days=semi_monthly_days,
                    monthly_anchor_day=monthly_anchor_day,
                )

        if new_due_date <= row.effective_due_date:
            raise RollingScheduleError(
                "Borrower shortfall shift must move every affected row forward."
            )

        planned.append(
            RollingScheduleShift(
                installment_id=row.installment_id,
                installment_number=row.installment_number,
                contractual_due_date=row.contractual_due_date,
                prior_effective_due_date=row.effective_due_date,
                new_effective_due_date=new_due_date,
            )
        )

    return tuple(planned)


def plan_borrower_catchup_contraction(
    *,
    installments: Iterable[RollingScheduleInstallment],
    active_extension_slots: int,
    completed_catchup_installment_ids: Iterable[int],
) -> tuple[RollingScheduleShift, ...]:
    """Contract only the still-remaining schedule after completed catch-up rows.

    Catch-up never rewrites already-reached/settled row history. Each additional
    future installment fully covered as normal catch-up removes one active
    borrower extension slot. Later remaining rows move backward by the same
    number of existing operational positions, preserving Management-adjusted and
    otherwise irregular operational spacing without inventing new dates.
    """

    if active_extension_slots < 0:
        raise RollingScheduleError("Active borrower extension slots cannot be negative.")

    completed_ids = tuple(dict.fromkeys(completed_catchup_installment_ids))
    if active_extension_slots == 0 or not completed_ids:
        return ()
    if len(completed_ids) > active_extension_slots:
        raise RollingScheduleError(
            "Catch-up cannot remove more borrower extension slots than are active."
        )

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
    positions_by_id = {row.installment_id: index for index, row in enumerate(rows)}
    try:
        completed_positions = tuple(positions_by_id[item_id] for item_id in completed_ids)
    except KeyError as error:
        raise RollingScheduleError(
            "Catch-up references an installment outside the current operational schedule."
        ) from error

    ordered_positions = tuple(sorted(completed_positions))
    if ordered_positions != tuple(
        range(ordered_positions[0], ordered_positions[0] + len(ordered_positions))
    ):
        raise RollingScheduleError(
            "Catch-up installments must be consecutive in operational order."
        )

    for position in ordered_positions:
        if _money(rows[position].remaining_amount) > ZERO:
            raise RollingScheduleError(
                "A borrower extension slot can contract only after the catch-up installment is fully covered."
            )

    slots_removed = len(ordered_positions)
    first_remaining_index = ordered_positions[-1] + 1
    planned: list[RollingScheduleShift] = []
    for index in range(first_remaining_index, len(rows)):
        row = rows[index]
        source_index = index - slots_removed
        if source_index < 0:
            raise RollingScheduleError(
                "Catch-up contraction cannot move before the current operational schedule."
            )
        new_due_date = rows[source_index].effective_due_date
        if new_due_date >= row.effective_due_date:
            raise RollingScheduleError(
                "Catch-up contraction must move every affected remaining row backward."
            )
        planned.append(
            RollingScheduleShift(
                installment_id=row.installment_id,
                installment_number=row.installment_number,
                contractual_due_date=row.contractual_due_date,
                prior_effective_due_date=row.effective_due_date,
                new_effective_due_date=new_due_date,
            )
        )

    return tuple(planned)


def project_rolling_schedule(
    *,
    installments: Iterable[RollingScheduleInstallment],
    as_of_date: date,
    payment_frequency: str,
    blocked_dates: Iterable[date] = (),
    semi_monthly_days: tuple[int, int] = (15, 30),
    finalized_through_date: date | None = None,
) -> RollingScheduleProjection:
    """Project SPINA's dynamic maturity extension without rewriting evidence.

    The signed/Management-adjusted installment dates remain the authoritative
    evidence for obligations already reached. Borrower-caused extension is based
    on an explicit official day-close boundary, not phone-local midnight and not
    the first partial receipt of a day.

    If ``finalized_through_date`` is omitted, the legacy read-only behavior is
    preserved by treating the day before ``as_of_date`` as finalized. A caller
    performing official day close should pass the exact authoritative business
    date; passing ``as_of_date`` is valid after that day has actually closed.

    When the borrower catches up and every finalized row is fully satisfied, the
    extension slot disappears automatically and maturity returns to the current
    operational schedule. This projection is intentionally derived instead of
    rewriting immutable Past Due or receipt history.
    """

    if finalized_through_date is None:
        finalized_through_date = as_of_date - timedelta(days=1)
    if finalized_through_date > as_of_date:
        raise RollingScheduleError(
            "Rolling schedule cannot finalize beyond the authoritative as-of date."
        )

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
            finalized_through_date=finalized_through_date,
        )

    past_due = tuple(
        row
        for row in rows
        if row.effective_due_date <= finalized_through_date
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
            finalized_through_date=finalized_through_date,
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
            finalized_through_date=finalized_through_date,
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
        finalized_through_date=finalized_through_date,
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