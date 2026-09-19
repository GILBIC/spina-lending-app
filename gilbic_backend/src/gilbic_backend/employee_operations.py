"""Employee calculations, deliberately independent from transport and persistence."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

MANILA = ZoneInfo("Asia/Manila")
ZERO = Decimal("0")
CENT = Decimal("0.01")


class EmployeeConflict(ValueError):
    """A domain state/input needs correction, never a successful zero-pay fallback."""


def money(value: Decimal | str | int) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def money_text(value: Decimal | str | int) -> str:
    return format(money(value), ".2f")


def day_pay(
    *,
    daily_rate: Decimal,
    working_minutes: int,
    leave_minutes: int,
    day_kind: str = "ordinary",
    rest_day: bool = False,
    premium_pay_covered: bool = True,
    holiday_pay_covered: bool = True,
    unworked_holiday: bool = False,
) -> dict[str, Decimal]:
    if (
        working_minutes < 0
        or leave_minutes < 0
        or min(working_minutes, 480) + leave_minutes > 480
    ):
        raise EmployeeConflict(
            "Paid leave and working time overlap or exceed the ordinary day"
        )
    ordinary = min(working_minutes, 480)
    hourly = daily_rate / Decimal(8)
    base = daily_rate * Decimal(ordinary) / 480
    leave = daily_rate * Decimal(leave_minutes) / 480
    multiplier = Decimal(1)
    if holiday_pay_covered and day_kind in (
        "regular_holiday",
        "double_regular_holiday",
    ):
        multiplier = Decimal(2 if day_kind == "regular_holiday" else 3)
        if rest_day and premium_pay_covered:
            multiplier *= Decimal("1.3")
    elif premium_pay_covered:
        if day_kind == "special_nonworking":
            multiplier = Decimal("1.5") if rest_day else Decimal("1.3")
        elif rest_day:
            multiplier = Decimal("1.3")
    premium = base * (multiplier - 1)
    ot_multiplier = Decimal("1.25") if multiplier == 1 else Decimal("1.3")
    overtime = hourly * Decimal(max(working_minutes - 480, 0)) / 60
    overtime *= multiplier * ot_multiplier if premium_pay_covered else Decimal(1)
    if unworked_holiday:
        if (
            working_minutes
            or leave_minutes
            or not holiday_pay_covered
            or day_kind not in ("regular_holiday", "double_regular_holiday")
        ):
            raise EmployeeConflict(
                "Unworked holiday eligibility does not match the day's facts"
            )
        base = daily_rate * (2 if day_kind == "double_regular_holiday" else 1)
    return {
        "basic_pay": base,
        "leave_pay": leave,
        "premium_pay": premium,
        "overtime": overtime,
    }


def weekly_performance_benefit(
    working_minutes: list[int],
    *,
    confirmed_shortage: bool,
    partial_policy: str = "prorated",
) -> Decimal:
    if confirmed_shortage:
        return money(0)
    credits = sum(
        (
            Decimal(100)
            if partial_policy == "full_day" and n > 0
            else Decimal(100) * Decimal(min(max(n, 0), 480)) / 480
            for n in working_minutes
        ),
        ZERO,
    )
    return money(credits)


def principal_installment(
    agreed: Decimal, outstanding: Decimal, available_pay: Decimal
) -> Decimal:
    amount = min(agreed, outstanding)
    if amount < 0 or available_pay < amount:
        return money(0)
    return money(amount)


def leave_accrual_minutes(
    hire_date: date,
    as_of: date,
    *,
    annual_days: int = 5,
    eligible_from: date | None = None,
) -> int:
    # Anniversary years avoid leap-year drift. First year is not usable early.
    years = as_of.year - hire_date.year

    def anniversary(year: int) -> date:
        return date(
            year,
            hire_date.month,
            min(hire_date.day, calendar.monthrange(year, hire_date.month)[1]),
        )

    if as_of < anniversary(hire_date.year + years):
        years -= 1
    if years < 1 and (eligible_from is None or as_of < eligible_from):
        return 0
    years = max(0, years)
    last = anniversary(hire_date.year + years)
    following = anniversary(hire_date.year + years + 1)
    partial = Decimal((as_of - last).days) / Decimal((following - last).days)
    return int(Decimal(annual_days * 480) * (Decimal(years) + partial))


def weekly_tax(taxable: Decimal) -> Decimal:
    """BIR RR11-2018 weekly table effective 2023 onward; reviewed exemptions outside."""
    brackets = [
        (Decimal("153846"), Decimal("42259.50"), Decimal(".35")),
        (Decimal("38462"), Decimal("7644.30"), Decimal(".30")),
        (Decimal("15385"), Decimal("1875"), Decimal(".25")),
        (Decimal("7692"), Decimal("432.60"), Decimal(".20")),
        (Decimal("4808"), ZERO, Decimal(".15")),
    ]
    for threshold, base, rate in brackets:
        if taxable > threshold:
            return money(base + (taxable - threshold) * rate)
    return money(0)


def month_saturdays(month: date) -> list[date]:
    first = month.replace(day=1)
    count = calendar.monthrange(first.year, first.month)[1]
    return [
        first + timedelta(days=n)
        for n in range(count)
        if (first + timedelta(days=n)).weekday() == 5
    ]


def attendance_day(
    events: list[dict], work_date: date, *, now: datetime | None = None
) -> dict:
    now = now or datetime.now(timezone.utc)
    result = {
        "work_date": work_date.isoformat(),
        "working_minutes": 0,
        "unpaid_break_minutes": 0,
        "status": "accepted",
        "event_ids": [],
        "issues": [],
    }
    ordered = sorted(
        events, key=lambda row: (row["payload"]["captured_at"], str(row["id"]))
    )
    # Compare aware instants, not offset-bearing timestamp strings.
    ordered.sort(key=lambda row: datetime.fromisoformat(row["payload"]["captured_at"]))
    state = "off"
    previous = None
    started = None
    break_started = None
    work_seconds = Decimal(0)
    break_seconds = Decimal(0)
    for row in ordered:
        payload = row["payload"]
        stamp = datetime.fromisoformat(payload["captured_at"])
        result["event_ids"].append(str(row["id"]))
        if stamp.astimezone(MANILA).date() != work_date or stamp > now + timedelta(
            minutes=5
        ):
            result["issues"].append("Capture time needs review")
        if payload.get("previous_event_id") != previous:
            result["issues"].append("Missing, reordered or conflicting event chain")
        event = payload["event_type"]
        if event == "clock_in" and state == "off":
            state, started = "working", stamp
        elif event == "break_start" and state == "working":
            work_seconds += Decimal(str((stamp - started).total_seconds()))
            state, break_started = "break", stamp
        elif event == "break_end" and state == "break":
            duration = Decimal(str((stamp - break_started).total_seconds()))
            # Short rests remain paid; interrupted longer meal breaks use correction.
            if duration <= 1200:
                work_seconds += duration
            else:
                break_seconds += duration
            state, started = "working", stamp
        elif event == "clock_out" and state == "working":
            work_seconds += Decimal(str((stamp - started).total_seconds()))
            state = "finished"
        else:
            result["issues"].append("Duplicate or invalid attendance transition")
        previous = str(row["id"])
    if state != "finished":
        result["issues"].append(
            "Incomplete attendance; correction or remaining events required"
        )
    if work_seconds < 0 or work_seconds > 86400 or break_seconds < 0:
        result["issues"].append("Invalid attendance duration")
    result["working_minutes"] = max(0, int(work_seconds / 60))
    result["unpaid_break_minutes"] = max(0, int(break_seconds / 60))
    if result["issues"]:
        result["status"] = "pending_review"
    return result
