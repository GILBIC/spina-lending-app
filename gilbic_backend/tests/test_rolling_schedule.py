from __future__ import annotations

from datetime import date
from decimal import Decimal

from gilbic_backend.rolling_schedule import (
    RollingScheduleInstallment,
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
        semi_monthly_days=(10, 25),
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
