from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from gilbic_backend.employee_operations import (
    EmployeeConflict,
    attendance_day,
    day_pay,
    leave_accrual_minutes,
    principal_installment,
    weekly_tax,
    weekly_performance_benefit,
)


def test_full_and_partial_day_are_exact_and_paid_leave_has_no_performance_credit():
    full = day_pay(daily_rate=Decimal("803.17"), working_minutes=480, leave_minutes=0)
    half = day_pay(daily_rate=Decimal("803.17"), working_minutes=240, leave_minutes=240)
    assert full["basic_pay"] == Decimal("803.17")
    assert half["basic_pay"] == Decimal("401.585")
    assert half["leave_pay"] == Decimal("401.585")
    assert weekly_performance_benefit([240], confirmed_shortage=False) == Decimal(
        "50.00"
    )
    assert weekly_performance_benefit([0], confirmed_shortage=False) == Decimal("0.00")


def test_confirmed_shortage_sets_benefit_zero_without_negative_deduction():
    assert weekly_performance_benefit([480] * 6, confirmed_shortage=True) == Decimal(
        "0.00"
    )
    assert weekly_performance_benefit([480] * 6, confirmed_shortage=False) == Decimal(
        "600.00"
    )


def test_overtime_is_paid_separately_and_leave_does_not_manufacture_overtime():
    value = day_pay(daily_rate=Decimal("800"), working_minutes=540, leave_minutes=0)
    assert value["basic_pay"] == Decimal("800")
    assert value["overtime"] == Decimal("125")
    with pytest.raises(EmployeeConflict, match="overlap"):
        day_pay(daily_rate=Decimal("800"), working_minutes=300, leave_minutes=240)


@pytest.mark.parametrize(
    "kind,rest,expected",
    [
        ("ordinary", True, "1040"),
        ("special_nonworking", False, "1040"),
        ("special_nonworking", True, "1200"),
        ("regular_holiday", False, "1600"),
        ("regular_holiday", True, "2080"),
        ("double_regular_holiday", False, "2400"),
    ],
)
def test_covered_day_premiums(kind, rest, expected):
    value = day_pay(
        daily_rate=Decimal("800"),
        working_minutes=480,
        leave_minutes=0,
        day_kind=kind,
        rest_day=rest,
    )
    assert value["basic_pay"] + value["premium_pay"] == Decimal(expected)


def test_principal_cap_and_insufficient_pay_do_not_create_negative_wages():
    assert principal_installment(
        Decimal("500"), Decimal("80"), Decimal("200")
    ) == Decimal("80")
    assert principal_installment(
        Decimal("500"), Decimal("800"), Decimal("200")
    ) == Decimal("0")


def test_ordinary_leave_is_unavailable_before_one_year_then_proportional():
    assert leave_accrual_minutes(date(2025, 1, 1), date(2025, 12, 31)) == 0
    assert leave_accrual_minutes(date(2025, 1, 1), date(2026, 1, 1)) == 2400
    assert leave_accrual_minutes(date(2025, 1, 1), date(2026, 7, 1)) > 2400


def test_weekly_tax_bracket_uses_decimal_and_does_not_repeat_monthly_amount():
    assert weekly_tax(Decimal("4808")) == Decimal("0.00")
    assert weekly_tax(Decimal("6000")) == Decimal("178.80")
    assert weekly_tax(Decimal("8000")) == Decimal("494.20")


def event(kind, hour, previous=None, identity="x"):
    return {
        "id": identity,
        "payload": {
            "event_type": kind,
            "captured_at": f"2026-09-19T{hour}:00+08:00",
            "previous_event_id": previous,
            "sequence": 1,
        },
    }


def test_attendance_orders_by_capture_and_flags_incomplete_or_ambiguous_entries():
    rows = [
        event("clock_out", "15:00", "c", "d"),
        event("clock_in", "06:00", None, "a"),
        event("break_start", "12:00", "a", "b"),
        event("break_end", "13:00", "b", "c"),
    ]
    result = attendance_day(
        rows, date(2026, 9, 19), now=datetime(2026, 9, 20, tzinfo=timezone.utc)
    )
    assert result["working_minutes"] == 480
    assert result["unpaid_break_minutes"] == 60
    assert result["status"] == "accepted"
    assert attendance_day(rows[:-1], date(2026, 9, 19))["status"] == "pending_review"


def test_future_capture_is_reviewed_not_accepted_as_work():
    result = attendance_day(
        [event("clock_in", "06:00", None, "a"), event("clock_out", "15:00", "a", "b")],
        date(2026, 9, 19),
        now=datetime(2026, 9, 18, tzinfo=timezone.utc),
    )
    assert result["status"] == "pending_review"
