from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Sequence


_ZERO = Decimal("0")
_CENT = Decimal("0.01")
_APPROVED_PRORATION_DAYS = 30


class SevenBySevenPenaltyError(ValueError):
    """Raised when a post-maturity penalty projection is not deterministic."""


@dataclass(frozen=True, slots=True)
class PenaltyBaseSegment:
    start_date: date
    end_date: date
    eligible_base: Decimal


@dataclass(frozen=True, slots=True)
class SevenBySevenPenaltyProjection:
    contractual_maturity: date
    as_of_date: date
    effective_monthly_rate: Decimal
    effective_daily_rate: Decimal
    eligible_overdue_days: int
    theoretical_penalty: Decimal
    remaining_cost_headroom: Decimal
    assessable_penalty: Decimal
    rounded_assessable_penalty: Decimal


def _validate_projection_authority(
    *,
    contractual_monthly_rate: Decimal,
    legal_rate_ceiling: Decimal,
    proration_days: int,
    lifetime_nonprincipal_cost_ceiling: Decimal,
    cumulative_counted_nonprincipal_charges: Decimal,
) -> None:
    if contractual_monthly_rate < _ZERO:
        raise SevenBySevenPenaltyError("Contractual penalty rate cannot be negative.")
    if legal_rate_ceiling <= _ZERO:
        raise SevenBySevenPenaltyError(
            "A positive terms-bound legal penalty-rate ceiling is required."
        )
    if proration_days != _APPROVED_PRORATION_DAYS:
        raise SevenBySevenPenaltyError(
            "The approved 7x7 penalty proration basis is a fixed 30-day month."
        )
    if lifetime_nonprincipal_cost_ceiling < _ZERO:
        raise SevenBySevenPenaltyError(
            "Lifetime non-principal cost ceiling cannot be negative."
        )
    if cumulative_counted_nonprincipal_charges < _ZERO:
        raise SevenBySevenPenaltyError(
            "Cumulative counted non-principal charges cannot be negative."
        )


def _validate_segments(
    *,
    contractual_maturity: date,
    as_of_date: date,
    base_segments: Sequence[PenaltyBaseSegment],
) -> None:
    first_penalty_day = contractual_maturity + timedelta(days=1)
    previous_end: date | None = None

    for segment in base_segments:
        if segment.start_date > segment.end_date:
            raise SevenBySevenPenaltyError(
                "Penalty base segment start date cannot be after its end date."
            )
        if segment.eligible_base < _ZERO:
            raise SevenBySevenPenaltyError("Penalty base cannot be negative.")
        if segment.start_date < first_penalty_day:
            raise SevenBySevenPenaltyError(
                "Penalty base segments cannot begin on or before contractual maturity."
            )
        if segment.end_date > as_of_date:
            raise SevenBySevenPenaltyError(
                "Penalty base segment cannot extend beyond the projection date."
            )
        if previous_end is not None and segment.start_date <= previous_end:
            raise SevenBySevenPenaltyError(
                "Penalty base segments must be chronological and non-overlapping."
            )
        previous_end = segment.end_date


def project_seven_by_seven_post_maturity_penalty(
    *,
    contractual_maturity: date,
    as_of_date: date,
    base_segments: Sequence[PenaltyBaseSegment],
    contractual_monthly_rate: Decimal,
    legal_rate_ceiling: Decimal,
    proration_days: int,
    lifetime_nonprincipal_cost_ceiling: Decimal,
    cumulative_counted_nonprincipal_charges: Decimal,
) -> SevenBySevenPenaltyProjection:
    """Project simple, capped 7x7 penalty without persisting financial evidence."""

    _validate_projection_authority(
        contractual_monthly_rate=contractual_monthly_rate,
        legal_rate_ceiling=legal_rate_ceiling,
        proration_days=proration_days,
        lifetime_nonprincipal_cost_ceiling=lifetime_nonprincipal_cost_ceiling,
        cumulative_counted_nonprincipal_charges=cumulative_counted_nonprincipal_charges,
    )
    _validate_segments(
        contractual_maturity=contractual_maturity,
        as_of_date=as_of_date,
        base_segments=base_segments,
    )

    effective_monthly_rate = min(contractual_monthly_rate, legal_rate_ceiling)
    effective_daily_rate = effective_monthly_rate / Decimal(proration_days)
    remaining_cost_headroom = max(
        _ZERO,
        lifetime_nonprincipal_cost_ceiling
        - cumulative_counted_nonprincipal_charges,
    )

    if as_of_date <= contractual_maturity:
        return SevenBySevenPenaltyProjection(
            contractual_maturity=contractual_maturity,
            as_of_date=as_of_date,
            effective_monthly_rate=effective_monthly_rate,
            effective_daily_rate=effective_daily_rate,
            eligible_overdue_days=0,
            theoretical_penalty=_ZERO,
            remaining_cost_headroom=remaining_cost_headroom,
            assessable_penalty=_ZERO,
            rounded_assessable_penalty=Decimal("0.00"),
        )

    eligible_overdue_days = 0
    theoretical_penalty = _ZERO
    for segment in base_segments:
        day_count = (segment.end_date - segment.start_date).days + 1
        eligible_overdue_days += day_count
        theoretical_penalty += (
            segment.eligible_base * effective_daily_rate * Decimal(day_count)
        )

    assessable_penalty = min(theoretical_penalty, remaining_cost_headroom)
    rounded_assessable_penalty = assessable_penalty.quantize(
        _CENT,
        rounding=ROUND_HALF_UP,
    )

    return SevenBySevenPenaltyProjection(
        contractual_maturity=contractual_maturity,
        as_of_date=as_of_date,
        effective_monthly_rate=effective_monthly_rate,
        effective_daily_rate=effective_daily_rate,
        eligible_overdue_days=eligible_overdue_days,
        theoretical_penalty=theoretical_penalty,
        remaining_cost_headroom=remaining_cost_headroom,
        assessable_penalty=assessable_penalty,
        rounded_assessable_penalty=rounded_assessable_penalty,
    )
