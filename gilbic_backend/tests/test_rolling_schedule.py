from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from gilbic_backend.rolling_schedule import (
    RollingScheduleError,
    RollingScheduleInstallment,
    finalize_rolling_schedule_day,
    project_rolling_schedule,
)


def _row(
    number: int,
    due_date: date,
    remaining: str,
) -> RollingScheduleInstallment:
    return RollingScheduleInstallment(
        installment_id=number,
        installment_number=number,
        contractual_due_date=due_date,
        effective_due_date=due_date,
        remaining_amount=Decimal(remaining),
    )


def test_partial_prior_day_adds_one_daily_extension_slot() -> None:
    projection = project_rolling_schedule(
        installments=(
            _row(1, date(2026, 8, 26), "10.00"),
            _row(2, date(2026, 8, 27), "50.00"),
            _row(3, date(2026, 8, 30), "50.00"),
        ),
        as_of_date=date(2026, 8, 27),
        payment_frequency="daily",
    )

    assert projection.past_due_amount == Decimal("10.00")
    assert projection.past_due_count == 1
    assert projection.extension_slots == 1
    assert projection.base_maturity == date(2026, 8, 30)
    assert projection.updated_maturity == date(2026, 8, 31)
    assert projection.projection_status == "extended"
    assert projection.finalized_through_date == date(2026, 8, 26)


def test_full_catch_up_restores_base_maturity() -> None:
    projection = project_rolling_schedule(
        installments=(
            _row(1, date(2026, 8, 26), "0.00"),
            _row(2, date(2026, 8, 27), "50.00"),
            _row(3, date(2026, 8, 30), "50.00"),
        ),
        as_of_date=date(2026, 8, 27),
        payment_frequency="daily",
    )

    assert projection.past_due_amount == Decimal("0.00")
    assert projection.past_due_count == 0
    assert projection.extension_slots == 0
    assert projection.base_maturity == date(2026, 8, 30)
    assert projection.updated_maturity == date(2026, 8, 30)
    assert projection.projection_status == "on_schedule"


def test_multiple_missed_rows_extend_and_skip_no_collection_dates() -> None:
    projection = project_rolling_schedule(
        installments=(
            _row(1, date(2026, 8, 25), "50.00"),
            _row(2, date(2026, 8, 26), "10.00"),
            _row(3, date(2026, 8, 27), "50.00"),
            _row(4, date(2026, 8, 30), "50.00"),
        ),
        as_of_date=date(2026, 8, 27),
        payment_frequency="daily",
        blocked_dates=(date(2026, 8, 31),),
    )

    assert projection.past_due_amount == Decimal("60.00")
    assert projection.past_due_count == 2
    assert projection.extension_slots == 2
    assert projection.updated_maturity == date(2026, 9, 2)


def test_seven_by_seven_uses_full_agreed_schedule_row_not_interest_only() -> None:
    projection = project_rolling_schedule(
        installments=(
            _row(1, date(2026, 8, 26), "10.00"),
            _row(2, date(2026, 8, 27), "50.00"),
            _row(3, date(2026, 9, 5), "50.00"),
        ),
        as_of_date=date(2026, 8, 27),
        payment_frequency="daily",
    )

    # Example product rule: agreed daily amount is 50. A prior-day payment of
    # 40 leaves 10 Past Due, so the schedule extends even if daily interest was
    # already fully covered underneath by the protected 7x7 allocator.
    assert projection.past_due_amount == Decimal("10.00")
    assert projection.extension_slots == 1
    assert projection.updated_maturity == date(2026, 9, 6)


def test_semi_monthly_extension_uses_configured_contract_days() -> None:
    projection = project_rolling_schedule(
        installments=(
            _row(1, date(2026, 8, 10), "100.00"),
            _row(2, date(2026, 8, 25), "100.00"),
        ),
        as_of_date=date(2026, 8, 25),
        payment_frequency="semi_monthly",
    )

    assert projection.extension_slots == 1
    assert projection.base_maturity == date(2026, 8, 25)
    assert projection.updated_maturity == date(2026, 9, 10)


def test_custom_schedule_extension_fails_closed_without_inventing_cadence() -> None:
    projection = project_rolling_schedule(
        installments=(
            _row(1, date(2026, 8, 20), "100.00"),
            _row(2, date(2026, 8, 30), "100.00"),
        ),
        as_of_date=date(2026, 8, 26),
        payment_frequency="custom",
    )

    assert projection.extension_slots == 1
    assert projection.updated_maturity is None
    assert projection.projection_status == "cadence_requires_management"


def test_same_day_partial_does_not_extend_before_official_close() -> None:
    rows = (
        _row(1, date(2026, 8, 26), "30.00"),
        _row(2, date(2026, 8, 27), "50.00"),
    )

    projection = project_rolling_schedule(
        installments=rows,
        as_of_date=date(2026, 8, 26),
        payment_frequency="daily",
    )

    assert projection.extension_slots == 0
    assert projection.past_due_amount == Decimal("0.00")
    assert projection.updated_maturity == date(2026, 8, 27)
    assert projection.finalized_through_date == date(2026, 8, 25)


def test_official_close_turns_only_final_same_day_shortfall_into_extension() -> None:
    rows = (
        _row(1, date(2026, 8, 26), "10.00"),
        _row(2, date(2026, 8, 27), "50.00"),
    )

    close = finalize_rolling_schedule_day(
        installments=rows,
        business_date=date(2026, 8, 26),
    )
    projection = project_rolling_schedule(
        installments=rows,
        as_of_date=date(2026, 8, 26),
        payment_frequency="daily",
        finalized_through_date=date(2026, 8, 26),
    )

    assert close.close_status == "shortfall"
    assert close.incomplete_count == 1
    assert close.shortfall_amount == Decimal("10.00")
    assert close.extension_slots_added == 1
    assert projection.extension_slots == 1
    assert projection.past_due_amount == Decimal("10.00")
    assert projection.updated_maturity == date(2026, 8, 28)


def test_split_receipts_that_complete_before_close_create_no_extension() -> None:
    rows = (
        _row(1, date(2026, 8, 26), "0.00"),
        _row(2, date(2026, 8, 27), "50.00"),
    )

    close = finalize_rolling_schedule_day(
        installments=rows,
        business_date=date(2026, 8, 26),
    )
    projection = project_rolling_schedule(
        installments=rows,
        as_of_date=date(2026, 8, 26),
        payment_frequency="daily",
        finalized_through_date=date(2026, 8, 26),
    )

    assert close.close_status == "complete"
    assert close.shortfall_amount == Decimal("0.00")
    assert close.extension_slots_added == 0
    assert projection.extension_slots == 0
    assert projection.updated_maturity == date(2026, 8, 27)


def test_catch_up_after_prior_close_removes_borrower_caused_extension() -> None:
    before_catch_up = project_rolling_schedule(
        installments=(
            _row(1, date(2026, 8, 26), "10.00"),
            _row(2, date(2026, 8, 27), "50.00"),
        ),
        as_of_date=date(2026, 8, 27),
        payment_frequency="daily",
        finalized_through_date=date(2026, 8, 26),
    )
    after_catch_up = project_rolling_schedule(
        installments=(
            _row(1, date(2026, 8, 26), "0.00"),
            _row(2, date(2026, 8, 27), "50.00"),
        ),
        as_of_date=date(2026, 8, 27),
        payment_frequency="daily",
        finalized_through_date=date(2026, 8, 26),
    )

    assert before_catch_up.extension_slots == 1
    assert before_catch_up.updated_maturity == date(2026, 8, 28)
    assert after_catch_up.extension_slots == 0
    assert after_catch_up.past_due_amount == Decimal("0.00")
    assert after_catch_up.updated_maturity == date(2026, 8, 27)


def test_day_close_with_no_scheduled_obligation_does_not_invent_extension() -> None:
    close = finalize_rolling_schedule_day(
        installments=(
            _row(1, date(2026, 8, 27), "50.00"),
        ),
        business_date=date(2026, 8, 26),
    )

    assert close.close_status == "no_scheduled_obligation"
    assert close.scheduled_count == 0
    assert close.shortfall_amount == Decimal("0.00")
    assert close.extension_slots_added == 0


def test_projection_rejects_finalization_beyond_authoritative_as_of_date() -> None:
    with pytest.raises(RollingScheduleError, match="cannot finalize beyond"):
        project_rolling_schedule(
            installments=(
                _row(1, date(2026, 8, 26), "10.00"),
            ),
            as_of_date=date(2026, 8, 26),
            payment_frequency="daily",
            finalized_through_date=date(2026, 8, 27),
        )
