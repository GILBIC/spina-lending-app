from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from typing import Iterable


MONEY = Decimal("0.01")
ZERO = Decimal("0.00")
COMPLETION_TOLERANCE = Decimal("0.004")
THOUSAND = Decimal("1000")
SEVEN_BY_SEVEN_OPERATIONAL_POLICY = "seven_by_seven_operational_allocator_v2"


class SevenBySevenAllocationError(ValueError):
    """Raised when 7x7 operational cash cannot be allocated without guessing."""


@dataclass(frozen=True, slots=True)
class SevenBySevenCashEvent:
    """One authoritative positive operational cash event for a 7x7 loan."""

    event_id: str
    collection_date: date
    amount: Decimal


@dataclass(frozen=True, slots=True)
class SevenBySevenAllocationLine:
    event_id: str
    sequence: int
    collection_date: date
    source_cash_amount: Decimal
    fixed_daily_interest: Decimal
    gap_days: int
    interest_days: int
    interest_holiday_days: int
    opening_remaining_principal: Decimal
    opening_interest_arrears: Decimal
    interest_due: Decimal
    interest_paid: Decimal
    principal_paid: Decimal
    unallocated_cash: Decimal
    closing_remaining_principal: Decimal
    closing_interest_arrears: Decimal
    event_applied: bool
    status: str


@dataclass(frozen=True, slots=True)
class SevenBySevenAllocationResult:
    policy: str
    original_principal: Decimal
    daily_interest_per_1000: Decimal
    fixed_daily_interest: Decimal
    payment_start: date
    closing_remaining_principal: Decimal
    closing_interest_arrears: Decimal
    total_interest_paid: Decimal
    total_principal_paid: Decimal
    total_unallocated_cash: Decimal
    complete: bool
    allocations: tuple[SevenBySevenAllocationLine, ...]


def money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def fixed_daily_interest_for_original_principal(
    *,
    original_principal: Decimal | int | str,
    daily_interest_per_1000: Decimal | int | str,
) -> Decimal:
    """Return the fixed 7x7 daily interest from original principal only.

    Every started PHP 1,000 of original principal carries the configured daily
    amount. The result is calculated once from original principal; later
    principal reductions never change it.
    """

    principal = money(original_principal)
    daily_rate = money(daily_interest_per_1000)
    if principal <= ZERO:
        raise SevenBySevenAllocationError("Original principal must be greater than zero.")
    if daily_rate <= ZERO:
        raise SevenBySevenAllocationError(
            "7x7 daily interest per 1,000 must be greater than zero."
        )

    started_thousands = (principal / THOUSAND).to_integral_value(rounding=ROUND_CEILING)
    return money(started_thousands * daily_rate)


def allocate_seven_by_seven_payments(
    *,
    original_principal: Decimal | int | str,
    daily_interest_per_1000: Decimal | int | str,
    payment_start: date,
    events: Iterable[SevenBySevenCashEvent],
    interest_holiday_dates: Iterable[date] = (),
) -> SevenBySevenAllocationResult:
    """Apply the protected Desktop 7x7 operational allocation rule.

    Contractual daily interest is fixed from original principal. For each cash
    event, elapsed calendar days are evaluated first, any prior interest arrears
    carry forward, cash settles interest before principal, and only the residual
    cash may reduce principal. This is an operational contractual allocator, not
    an accounting EIR allocator.

    Management-approved 7x7 No Collection dates may be supplied through
    ``interest_holiday_dates``. Those dates remain part of the elapsed calendar
    gap but contribute zero new daily interest. Existing interest arrears remain
    collectible on the holiday. The later full-voluntary-payment exception may
    explicitly remove a date from the holiday set before calling this allocator.

    Multiple distinct receipt events may occur on the same calendar date. The
    first event for that date evaluates the elapsed period; later same-day
    receipts accrue zero additional days and continue settling the same day's
    remaining interest/principal. The caller must keep authoritative receipt
    order within a date. Event ids still must be unique so an idempotent retry is
    never mistaken for a second receipt.
    """

    principal = money(original_principal)
    daily_rate = money(daily_interest_per_1000)
    fixed_daily_interest = fixed_daily_interest_for_original_principal(
        original_principal=principal,
        daily_interest_per_1000=daily_rate,
    )
    rows = tuple(events)
    holidays = frozenset(interest_holiday_dates)
    _validate_events(rows, payment_start=payment_start)

    remaining_principal = principal
    interest_arrears = ZERO
    previous_date = payment_start - timedelta(days=1)
    allocator_complete = False
    allocations: list[SevenBySevenAllocationLine] = []

    for sequence, event in enumerate(rows, start=1):
        amount = money(event.amount)
        opening_principal = remaining_principal
        opening_arrears = interest_arrears

        if allocator_complete:
            allocations.append(
                SevenBySevenAllocationLine(
                    event_id=event.event_id,
                    sequence=sequence,
                    collection_date=event.collection_date,
                    source_cash_amount=amount,
                    fixed_daily_interest=fixed_daily_interest,
                    gap_days=0,
                    interest_days=0,
                    interest_holiday_days=0,
                    opening_remaining_principal=opening_principal,
                    opening_interest_arrears=opening_arrears,
                    interest_due=opening_arrears,
                    interest_paid=ZERO,
                    principal_paid=ZERO,
                    unallocated_cash=amount,
                    closing_remaining_principal=remaining_principal,
                    closing_interest_arrears=interest_arrears,
                    event_applied=False,
                    status="desktop_allocator_would_stop_before_event",
                )
            )
            continue

        elapsed_days = max(0, (event.collection_date - previous_date).days)
        interest_days = _interest_bearing_days(
            previous_date=previous_date,
            current_date=event.collection_date,
            payment_start=payment_start,
            holidays=holidays,
        )
        holiday_days = max(0, elapsed_days - interest_days)
        interest_due = money(fixed_daily_interest * interest_days + interest_arrears)
        interest_paid = money(min(amount, interest_due))
        principal_paid = money(
            min(remaining_principal, max(ZERO, amount - interest_paid))
        )
        unallocated = money(max(ZERO, amount - interest_paid - principal_paid))

        remaining_principal = money(max(ZERO, remaining_principal - principal_paid))
        interest_arrears = money(max(ZERO, interest_due - interest_paid))

        if (
            remaining_principal <= COMPLETION_TOLERANCE
            and interest_arrears <= COMPLETION_TOLERANCE
        ):
            remaining_principal = ZERO
            interest_arrears = ZERO
            allocator_complete = True

        allocations.append(
            SevenBySevenAllocationLine(
                event_id=event.event_id,
                sequence=sequence,
                collection_date=event.collection_date,
                source_cash_amount=amount,
                fixed_daily_interest=fixed_daily_interest,
                gap_days=elapsed_days,
                interest_days=interest_days,
                interest_holiday_days=holiday_days,
                opening_remaining_principal=opening_principal,
                opening_interest_arrears=opening_arrears,
                interest_due=interest_due,
                interest_paid=interest_paid,
                principal_paid=principal_paid,
                unallocated_cash=unallocated,
                closing_remaining_principal=remaining_principal,
                closing_interest_arrears=interest_arrears,
                event_applied=True,
                status=(
                    "desktop_allocator_unallocated_overpayment"
                    if unallocated > ZERO
                    else "desktop_operational_allocation_reproduced"
                ),
            )
        )
        previous_date = event.collection_date

    return SevenBySevenAllocationResult(
        policy=SEVEN_BY_SEVEN_OPERATIONAL_POLICY,
        original_principal=principal,
        daily_interest_per_1000=daily_rate,
        fixed_daily_interest=fixed_daily_interest,
        payment_start=payment_start,
        closing_remaining_principal=remaining_principal,
        closing_interest_arrears=interest_arrears,
        total_interest_paid=money(sum((row.interest_paid for row in allocations), ZERO)),
        total_principal_paid=money(sum((row.principal_paid for row in allocations), ZERO)),
        total_unallocated_cash=money(
            sum((row.unallocated_cash for row in allocations), ZERO)
        ),
        complete=allocator_complete,
        allocations=tuple(allocations),
    )


def _interest_bearing_days(
    *,
    previous_date: date,
    current_date: date,
    payment_start: date,
    holidays: frozenset[date],
) -> int:
    if current_date <= previous_date:
        return 0
    cursor = max(previous_date + timedelta(days=1), payment_start)
    count = 0
    while cursor <= current_date:
        if cursor not in holidays:
            count += 1
        cursor += timedelta(days=1)
    return count


def _validate_events(
    events: tuple[SevenBySevenCashEvent, ...],
    *,
    payment_start: date,
) -> None:
    prior_date: date | None = None
    seen_ids: set[str] = set()
    for event in events:
        event_id = str(event.event_id).strip()
        if not event_id:
            raise SevenBySevenAllocationError("Every 7x7 cash event requires an event id.")
        if event_id in seen_ids:
            raise SevenBySevenAllocationError("7x7 cash event ids must be unique.")
        seen_ids.add(event_id)

        if money(event.amount) <= ZERO:
            raise SevenBySevenAllocationError(
                "Every 7x7 operational cash event must have a positive amount."
            )
        if event.collection_date < payment_start:
            raise SevenBySevenAllocationError(
                "A 7x7 cash event cannot precede the protected payment start date."
            )
        if prior_date is not None and event.collection_date < prior_date:
            raise SevenBySevenAllocationError(
                "7x7 cash events must be chronological. Same-day distinct receipts are allowed only in authoritative receipt order."
            )
        prior_date = event.collection_date
