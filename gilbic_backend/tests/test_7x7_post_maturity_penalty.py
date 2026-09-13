from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from gilbic_backend.seven_by_seven_post_maturity_penalty import (
    PenaltyBaseSegment,
    SevenBySevenPenaltyError,
    project_seven_by_seven_post_maturity_penalty,
)


MATURITY = date(2099, 1, 30)
FIRST_PENALTY_DAY = MATURITY + timedelta(days=1)


def _project(
    *,
    as_of_date: date,
    segments: tuple[PenaltyBaseSegment, ...],
    legal_rate_ceiling: Decimal = Decimal("0.030000"),
    lifetime_ceiling: Decimal = Decimal("10000.00"),
    cumulative_counted_cost: Decimal = Decimal("0.00"),
):
    return project_seven_by_seven_post_maturity_penalty(
        contractual_maturity=MATURITY,
        as_of_date=as_of_date,
        base_segments=segments,
        contractual_monthly_rate=Decimal("0.030000"),
        legal_rate_ceiling=legal_rate_ceiling,
        proration_days=30,
        lifetime_nonprincipal_cost_ceiling=lifetime_ceiling,
        cumulative_counted_nonprincipal_charges=cumulative_counted_cost,
    )


def _segment(*, start: date, end: date, base: str) -> PenaltyBaseSegment:
    return PenaltyBaseSegment(
        start_date=start,
        end_date=end,
        eligible_base=Decimal(base),
    )


def test_no_penalty_on_or_before_signed_contractual_maturity() -> None:
    for as_of_date in (MATURITY - timedelta(days=1), MATURITY):
        projection = _project(as_of_date=as_of_date, segments=())
        assert projection.eligible_overdue_days == 0
        assert projection.theoretical_penalty == Decimal("0")
        assert projection.assessable_penalty == Decimal("0")
        assert projection.rounded_assessable_penalty == Decimal("0.00")


def test_first_penalty_day_is_calendar_day_after_signed_maturity() -> None:
    projection = _project(
        as_of_date=FIRST_PENALTY_DAY,
        segments=(
            _segment(
                start=FIRST_PENALTY_DAY,
                end=FIRST_PENALTY_DAY,
                base="1000.00",
            ),
        ),
    )

    assert projection.eligible_overdue_days == 1
    assert projection.effective_monthly_rate == Decimal("0.030000")
    assert projection.effective_daily_rate == Decimal("0.001000")
    assert projection.theoretical_penalty == Decimal("1.00000000")
    assert projection.rounded_assessable_penalty == Decimal("1.00")


@pytest.mark.parametrize(
    ("days", "expected"),
    [
        (10, Decimal("10.00")),
        (30, Decimal("30.00")),
    ],
)
def test_three_percent_monthly_uses_fixed_30_day_daily_proration(
    days: int,
    expected: Decimal,
) -> None:
    end = FIRST_PENALTY_DAY + timedelta(days=days - 1)
    projection = _project(
        as_of_date=end,
        segments=(
            _segment(start=FIRST_PENALTY_DAY, end=end, base="1000.00"),
        ),
    )

    assert projection.eligible_overdue_days == days
    assert projection.rounded_assessable_penalty == expected


def test_fractional_cent_penalty_is_not_rounded_daily() -> None:
    end = FIRST_PENALTY_DAY + timedelta(days=29)
    projection = _project(
        as_of_date=end,
        segments=(
            _segment(start=FIRST_PENALTY_DAY, end=end, base="333.33"),
        ),
    )

    assert projection.theoretical_penalty == Decimal("9.99990000")
    assert projection.rounded_assessable_penalty == Decimal("10.00")


def test_lower_terms_bound_legal_rate_ceiling_controls_effective_rate() -> None:
    end = FIRST_PENALTY_DAY + timedelta(days=29)
    projection = _project(
        as_of_date=end,
        legal_rate_ceiling=Decimal("0.020000"),
        segments=(
            _segment(start=FIRST_PENALTY_DAY, end=end, base="1000.00"),
        ),
    )

    assert projection.effective_monthly_rate == Decimal("0.020000")
    assert projection.rounded_assessable_penalty == Decimal("20.00")


def test_reduced_contractual_base_applies_only_to_later_days() -> None:
    day10 = FIRST_PENALTY_DAY + timedelta(days=9)
    day20 = FIRST_PENALTY_DAY + timedelta(days=19)
    projection = _project(
        as_of_date=day20,
        segments=(
            _segment(start=FIRST_PENALTY_DAY, end=day10, base="1000.00"),
            _segment(
                start=day10 + timedelta(days=1),
                end=day20,
                base="500.00",
            ),
        ),
    )

    assert projection.eligible_overdue_days == 20
    assert projection.rounded_assessable_penalty == Decimal("15.00")


def test_management_no_collection_protected_amount_can_be_excluded_from_base() -> None:
    end = FIRST_PENALTY_DAY + timedelta(days=9)
    projection = _project(
        as_of_date=end,
        segments=(
            _segment(start=FIRST_PENALTY_DAY, end=end, base="700.00"),
        ),
    )

    assert projection.rounded_assessable_penalty == Decimal("7.00")


def test_lifetime_cost_headroom_clamps_new_penalty() -> None:
    end = FIRST_PENALTY_DAY + timedelta(days=29)
    projection = _project(
        as_of_date=end,
        lifetime_ceiling=Decimal("100.00"),
        cumulative_counted_cost=Decimal("95.00"),
        segments=(
            _segment(start=FIRST_PENALTY_DAY, end=end, base="1000.00"),
        ),
    )

    assert projection.remaining_cost_headroom == Decimal("5.00")
    assert projection.theoretical_penalty == Decimal("30.00000000")
    assert projection.assessable_penalty == Decimal("5.00")
    assert projection.rounded_assessable_penalty == Decimal("5.00")


def test_exhausted_lifetime_cost_headroom_stops_new_penalty() -> None:
    projection = _project(
        as_of_date=FIRST_PENALTY_DAY,
        lifetime_ceiling=Decimal("100.00"),
        cumulative_counted_cost=Decimal("100.00"),
        segments=(
            _segment(
                start=FIRST_PENALTY_DAY,
                end=FIRST_PENALTY_DAY,
                base="1000.00",
            ),
        ),
    )

    assert projection.remaining_cost_headroom == Decimal("0.00")
    assert projection.assessable_penalty == Decimal("0.00")
    assert projection.rounded_assessable_penalty == Decimal("0.00")


def test_zero_contractual_base_creates_no_new_penalty() -> None:
    projection = _project(
        as_of_date=FIRST_PENALTY_DAY,
        segments=(
            _segment(
                start=FIRST_PENALTY_DAY,
                end=FIRST_PENALTY_DAY,
                base="0.00",
            ),
        ),
    )

    assert projection.rounded_assessable_penalty == Decimal("0.00")


@pytest.mark.parametrize(
    "segments",
    [
        (
            _segment(
                start=FIRST_PENALTY_DAY,
                end=FIRST_PENALTY_DAY - timedelta(days=1),
                base="1000.00",
            ),
        ),
        (
            _segment(
                start=FIRST_PENALTY_DAY,
                end=FIRST_PENALTY_DAY,
                base="-1.00",
            ),
        ),
        (
            _segment(
                start=FIRST_PENALTY_DAY,
                end=FIRST_PENALTY_DAY + timedelta(days=2),
                base="1000.00",
            ),
            _segment(
                start=FIRST_PENALTY_DAY + timedelta(days=2),
                end=FIRST_PENALTY_DAY + timedelta(days=3),
                base="500.00",
            ),
        ),
    ],
)
def test_invalid_or_overlapping_base_segments_fail_closed(
    segments: tuple[PenaltyBaseSegment, ...],
) -> None:
    with pytest.raises(SevenBySevenPenaltyError):
        _project(
            as_of_date=FIRST_PENALTY_DAY + timedelta(days=3),
            segments=segments,
        )
