from datetime import date
from decimal import Decimal

import pytest

from gilbic_backend.seven_by_seven_operational_allocator import (
    SEVEN_BY_SEVEN_OPERATIONAL_POLICY,
    SevenBySevenAllocationError,
    SevenBySevenCashEvent,
    allocate_seven_by_seven_payments,
    fixed_daily_interest_for_original_principal,
)


def _event(event_id: str, day: int, amount: str) -> SevenBySevenCashEvent:
    return SevenBySevenCashEvent(
        event_id=event_id,
        collection_date=date(2026, 8, day),
        amount=Decimal(amount),
    )


def test_fixed_daily_interest_uses_every_started_thousand_of_original_principal() -> None:
    assert fixed_daily_interest_for_original_principal(
        original_principal=Decimal("3000.00"),
        daily_interest_per_1000=Decimal("7.00"),
    ) == Decimal("21.00")
    assert fixed_daily_interest_for_original_principal(
        original_principal=Decimal("3000.01"),
        daily_interest_per_1000=Decimal("7.00"),
    ) == Decimal("28.00")


def test_first_cash_uses_payment_start_minus_one_and_accrues_calendar_gap_first() -> None:
    result = allocate_seven_by_seven_payments(
        original_principal=Decimal("3000.00"),
        daily_interest_per_1000=Decimal("7.00"),
        payment_start=date(2026, 8, 1),
        events=(_event("cash-1", 2, "50.00"),),
    )

    assert result.policy == SEVEN_BY_SEVEN_OPERATIONAL_POLICY
    assert result.fixed_daily_interest == Decimal("21.00")
    row = result.allocations[0]
    assert row.gap_days == 2
    assert row.interest_days == 2
    assert row.interest_holiday_days == 0
    assert row.interest_due == Decimal("42.00")
    assert row.interest_paid == Decimal("42.00")
    assert row.principal_paid == Decimal("8.00")
    assert row.closing_remaining_principal == Decimal("2992.00")
    assert row.closing_interest_arrears == Decimal("0.00")


def test_interest_arrears_carry_forward_and_cash_is_interest_first() -> None:
    result = allocate_seven_by_seven_payments(
        original_principal="3000.00",
        daily_interest_per_1000="7.00",
        payment_start=date(2026, 8, 1),
        events=(
            _event("cash-1", 1, "10.00"),
            _event("cash-2", 2, "25.00"),
        ),
    )

    first, second = result.allocations
    assert first.interest_due == Decimal("21.00")
    assert first.interest_paid == Decimal("10.00")
    assert first.principal_paid == Decimal("0.00")
    assert first.closing_interest_arrears == Decimal("11.00")

    assert second.opening_interest_arrears == Decimal("11.00")
    assert second.interest_due == Decimal("32.00")
    assert second.interest_paid == Decimal("25.00")
    assert second.principal_paid == Decimal("0.00")
    assert second.closing_interest_arrears == Decimal("7.00")


def test_distinct_same_day_receipts_share_one_days_interest_without_becoming_duplicates() -> None:
    result = allocate_seven_by_seven_payments(
        original_principal="3000.00",
        daily_interest_per_1000="7.00",
        payment_start=date(2026, 8, 1),
        events=(
            _event("collector-a-receipt", 1, "10.00"),
            _event("collector-b-receipt", 1, "50.00"),
        ),
    )

    first, second = result.allocations
    assert first.gap_days == 1
    assert first.interest_due == Decimal("21.00")
    assert first.interest_paid == Decimal("10.00")
    assert first.closing_interest_arrears == Decimal("11.00")

    assert second.gap_days == 0
    assert second.interest_days == 0
    assert second.opening_interest_arrears == Decimal("11.00")
    assert second.interest_due == Decimal("11.00")
    assert second.interest_paid == Decimal("11.00")
    assert second.principal_paid == Decimal("39.00")
    assert second.closing_remaining_principal == Decimal("2961.00")
    assert result.total_interest_paid == Decimal("21.00")
    assert result.total_principal_paid == Decimal("39.00")


def test_principal_reduction_never_changes_fixed_daily_interest() -> None:
    result = allocate_seven_by_seven_payments(
        original_principal="3000.00",
        daily_interest_per_1000="7.00",
        payment_start=date(2026, 8, 1),
        events=(
            _event("cash-1", 1, "1021.00"),
            _event("cash-2", 2, "21.00"),
        ),
    )

    first, second = result.allocations
    assert first.interest_paid == Decimal("21.00")
    assert first.principal_paid == Decimal("1000.00")
    assert first.closing_remaining_principal == Decimal("2000.00")

    assert second.fixed_daily_interest == Decimal("21.00")
    assert second.interest_due == Decimal("21.00")
    assert second.interest_paid == Decimal("21.00")
    assert second.principal_paid == Decimal("0.00")


def test_overpayment_is_unallocated_and_later_cash_is_not_reapplied_after_payoff() -> None:
    result = allocate_seven_by_seven_payments(
        original_principal="3000.00",
        daily_interest_per_1000="7.00",
        payment_start=date(2026, 8, 1),
        events=(
            _event("payoff", 1, "4000.00"),
            _event("late-extra", 2, "100.00"),
        ),
    )

    payoff, later = result.allocations
    assert payoff.interest_paid == Decimal("21.00")
    assert payoff.principal_paid == Decimal("3000.00")
    assert payoff.unallocated_cash == Decimal("979.00")
    assert payoff.status == "desktop_allocator_unallocated_overpayment"
    assert payoff.closing_remaining_principal == Decimal("0.00")
    assert result.complete is True

    assert later.event_applied is False
    assert later.gap_days == 0
    assert later.interest_paid == Decimal("0.00")
    assert later.principal_paid == Decimal("0.00")
    assert later.unallocated_cash == Decimal("100.00")
    assert later.status == "desktop_allocator_would_stop_before_event"
    assert result.total_unallocated_cash == Decimal("1079.00")


def test_calendar_gaps_accrue_fixed_interest_without_synthetic_pass_cash() -> None:
    result = allocate_seven_by_seven_payments(
        original_principal="3000.00",
        daily_interest_per_1000="7.00",
        payment_start=date(2026, 8, 1),
        events=(
            _event("cash-1", 1, "21.00"),
            _event("cash-after-gap", 5, "84.00"),
        ),
    )

    first, after_gap = result.allocations
    assert first.gap_days == 1
    assert after_gap.gap_days == 4
    assert after_gap.interest_days == 4
    assert after_gap.interest_due == Decimal("84.00")
    assert after_gap.interest_paid == Decimal("84.00")
    assert after_gap.principal_paid == Decimal("0.00")


def test_no_collection_date_is_zero_interest_but_keeps_calendar_gap_evidence() -> None:
    result = allocate_seven_by_seven_payments(
        original_principal="3000.00",
        daily_interest_per_1000="7.00",
        payment_start=date(2026, 8, 1),
        events=(
            _event("cash-1", 1, "21.00"),
            _event("cash-after-holiday", 3, "21.00"),
        ),
        interest_holiday_dates=(date(2026, 8, 2),),
    )

    after_holiday = result.allocations[1]
    assert after_holiday.gap_days == 2
    assert after_holiday.interest_days == 1
    assert after_holiday.interest_holiday_days == 1
    assert after_holiday.interest_due == Decimal("21.00")
    assert after_holiday.interest_paid == Decimal("21.00")
    assert after_holiday.principal_paid == Decimal("0.00")


def test_consecutive_no_collection_dates_each_remove_one_interest_day() -> None:
    result = allocate_seven_by_seven_payments(
        original_principal="3000.00",
        daily_interest_per_1000="7.00",
        payment_start=date(2026, 8, 1),
        events=(
            _event("cash-1", 1, "21.00"),
            _event("cash-after-two-holidays", 4, "21.00"),
        ),
        interest_holiday_dates=(date(2026, 8, 2), date(2026, 8, 3)),
    )

    after_holidays = result.allocations[1]
    assert after_holidays.gap_days == 3
    assert after_holidays.interest_days == 1
    assert after_holidays.interest_holiday_days == 2
    assert after_holidays.interest_due == Decimal("21.00")


def test_no_collection_cash_can_clear_old_interest_without_earning_new_interest() -> None:
    result = allocate_seven_by_seven_payments(
        original_principal="3000.00",
        daily_interest_per_1000="7.00",
        payment_start=date(2026, 8, 1),
        events=(
            _event("short-day-1", 1, "10.00"),
            _event("holiday-catchup", 2, "11.00"),
        ),
        interest_holiday_dates=(date(2026, 8, 2),),
    )

    first, holiday = result.allocations
    assert first.closing_interest_arrears == Decimal("11.00")
    assert holiday.gap_days == 1
    assert holiday.interest_days == 0
    assert holiday.interest_holiday_days == 1
    assert holiday.interest_due == Decimal("11.00")
    assert holiday.interest_paid == Decimal("11.00")
    assert holiday.principal_paid == Decimal("0.00")
    assert holiday.closing_interest_arrears == Decimal("0.00")


def test_allocator_fails_closed_on_invalid_or_invented_event_order() -> None:
    with pytest.raises(SevenBySevenAllocationError, match="precede"):
        allocate_seven_by_seven_payments(
            original_principal="3000.00",
            daily_interest_per_1000="7.00",
            payment_start=date(2026, 8, 2),
            events=(_event("too-early", 1, "21.00"),),
        )

    with pytest.raises(SevenBySevenAllocationError, match="chronological"):
        allocate_seven_by_seven_payments(
            original_principal="3000.00",
            daily_interest_per_1000="7.00",
            payment_start=date(2026, 8, 1),
            events=(
                _event("cash-later", 3, "21.00"),
                _event("cash-earlier", 2, "21.00"),
            ),
        )

    with pytest.raises(SevenBySevenAllocationError, match="positive amount"):
        allocate_seven_by_seven_payments(
            original_principal="3000.00",
            daily_interest_per_1000="7.00",
            payment_start=date(2026, 8, 1),
            events=(_event("zero", 1, "0.00"),),
        )

    with pytest.raises(SevenBySevenAllocationError, match="unique"):
        allocate_seven_by_seven_payments(
            original_principal="3000.00",
            daily_interest_per_1000="7.00",
            payment_start=date(2026, 8, 1),
            events=(
                _event("duplicate", 1, "21.00"),
                _event("duplicate", 1, "21.00"),
            ),
        )


def test_allocator_requires_positive_principal_and_7x7_daily_rate() -> None:
    with pytest.raises(SevenBySevenAllocationError, match="Original principal"):
        allocate_seven_by_seven_payments(
            original_principal="0.00",
            daily_interest_per_1000="7.00",
            payment_start=date(2026, 8, 1),
            events=(),
        )

    with pytest.raises(SevenBySevenAllocationError, match="daily interest"):
        allocate_seven_by_seven_payments(
            original_principal="3000.00",
            daily_interest_per_1000="0.00",
            payment_start=date(2026, 8, 1),
            events=(),
        )
