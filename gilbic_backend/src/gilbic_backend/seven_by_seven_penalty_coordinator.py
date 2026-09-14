from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID

from .seven_by_seven_advance_activation import (
    SevenBySevenAdvanceActivationError,
    replay_verified_seven_by_seven_financial_state,
)
from .seven_by_seven_operational_allocator import (
    SevenBySevenAllocationError,
    SevenBySevenCashEvent,
    allocate_seven_by_seven_payments,
)
from .seven_by_seven_post_maturity_penalty import (
    PenaltyBaseSegment,
    SevenBySevenPenaltyError,
    project_seven_by_seven_post_maturity_penalty,
)


ZERO = Decimal("0.00")
CENT = Decimal("0.01")
PROBE_CASH = Decimal("0.01")
APPROVED_CONTRACTUAL_MONTHLY_RATE = Decimal("0.030000")
APPROVED_PRORATION_DAYS = 30


class SevenBySevenPenaltyCoordinatorError(RuntimeError):
    """Raised when penalty evidence cannot be coordinated deterministically."""

    code = "seven_by_seven_penalty_coordinator_conflict"


@dataclass(frozen=True, slots=True)
class SevenBySevenPenaltyState:
    loan_id: UUID
    schedule_id: UUID | None
    pricing_compliance_review_id: int | None
    terms_fingerprint: str
    contractual_maturity: date | None
    as_of_date: date
    status: str
    projected_penalty: Decimal
    assessed_penalty_balance: Decimal
    penalty_base: Decimal
    remaining_cost_headroom: Decimal
    effective_monthly_rate: Decimal
    management_review_required_reason: str = ""
    projection_start_date: date | None = None
    opening_penalty_base: Decimal = ZERO
    theoretical_penalty_exact: Decimal = Decimal("0")
    contractual_monthly_rate: Decimal = Decimal("0")
    legal_rate_ceiling: Decimal = Decimal("0")
    penalty_proration_days: int = 0
    lifetime_nonprincipal_cost_ceiling: Decimal = ZERO
    cumulative_counted_nonprincipal_charges: Decimal = ZERO
    base_segments: tuple[PenaltyBaseSegment, ...] = ()


@dataclass(frozen=True, slots=True)
class _LoanScheduleAuthority:
    loan_id: UUID
    principal: Decimal
    date_released: date
    daily_interest_per_1000: Decimal
    schedule_id: UUID
    schedule_settings: dict[str, object]
    contractual_maturity: date


@dataclass(frozen=True, slots=True)
class _PenaltyAuthority:
    review_id: int
    terms_fingerprint: str
    policy_version: str
    contractual_monthly_rate: Decimal
    proration_days: int
    legal_rate_ceiling: Decimal
    lifetime_nonprincipal_cost_ceiling: Decimal
    counted_nonprincipal_cost_at_contract_lock: Decimal


def _money(value: Decimal | int | str | None) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def _decimal(value: object, *, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception as error:
        raise SevenBySevenPenaltyCoordinatorError(
            f"The signed 7x7 penalty {field} is invalid. Management review is required."
        ) from error


def _load_loan_schedule_authority(
    cursor: Any,
    *,
    loan_id: UUID,
) -> tuple[_LoanScheduleAuthority | None, str]:
    cursor.execute(
        """
        select
            loan.id,
            loan.principal,
            loan.date_released,
            loan_type.calculation_mode,
            loan_type.daily_interest_per_1000,
            schedule.id,
            schedule.payment_frequency,
            schedule.settings,
            max(installment.due_date) as contractual_maturity,
            count(installment.id)::integer as installment_count,
            exists (
                select 1
                from lending.loan_contract_schedule_registrations registration
                where registration.schedule_id = schedule.id
            ) as schedule_registered
        from lending.loans loan
        join lending.loan_types loan_type
          on loan_type.id = loan.loan_type_id
        join lending.loan_contract_schedules schedule
          on schedule.loan_id = loan.id
         and schedule.status = 'active'
        left join lending.loan_contract_installments installment
          on installment.schedule_id = schedule.id
        where loan.id = %s
        group by
            loan.id,
            loan.principal,
            loan.date_released,
            loan_type.calculation_mode,
            loan_type.daily_interest_per_1000,
            schedule.id,
            schedule.schedule_version,
            schedule.payment_frequency,
            schedule.settings
        order by schedule.schedule_version desc
        limit 1
        """,
        (loan_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None, "An active verified signed 7x7 schedule is required."

    (
        row_loan_id,
        principal,
        date_released,
        calculation_mode,
        daily_interest_per_1000,
        schedule_id,
        payment_frequency,
        settings,
        contractual_maturity,
        installment_count,
        schedule_registered,
    ) = row
    if str(calculation_mode or "") != "seven_by_seven":
        return None, "The selected loan is not a 7x7 loan."
    if str(payment_frequency or "") != "daily":
        return None, "The active verified 7x7 schedule is not daily."
    if not bool(schedule_registered):
        return None, "The active 7x7 schedule has no verified signed registration."
    if int(installment_count or 0) <= 0 or contractual_maturity is None:
        return None, "The active verified 7x7 schedule has no immutable contractual maturity."
    if not isinstance(settings, dict):
        settings = {}

    return (
        _LoanScheduleAuthority(
            loan_id=row_loan_id,
            principal=_money(principal),
            date_released=date_released,
            daily_interest_per_1000=_money(daily_interest_per_1000),
            schedule_id=schedule_id,
            schedule_settings=settings,
            contractual_maturity=contractual_maturity,
        ),
        "",
    )


def _load_penalty_authority(
    cursor: Any,
    *,
    loan: _LoanScheduleAuthority,
) -> tuple[_PenaltyAuthority | None, str]:
    snapshot = loan.schedule_settings.get("seven_by_seven_penalty_policy")
    if not isinstance(snapshot, dict):
        return None, "The signed 7x7 contract has no exact post-maturity penalty disclosure authority."

    try:
        review_id = int(snapshot["review_id"])
        policy_version = str(snapshot["policy_version"]).strip()
        terms_fingerprint = str(snapshot["terms_fingerprint"]).strip().lower()
        contractual_rate = _decimal(
            snapshot["contractual_monthly_rate"],
            field="contractual monthly rate",
        )
        proration_days = int(snapshot["proration_days"])
        legal_rate_ceiling = _decimal(
            snapshot["legal_rate_ceiling"],
            field="legal rate ceiling",
        )
        lifetime_ceiling = _decimal(
            snapshot["lifetime_nonprincipal_cost_ceiling"],
            field="lifetime non-principal cost ceiling",
        )
        counted_at_lock = _decimal(
            snapshot["counted_nonprincipal_cost_at_contract_lock"],
            field="counted non-principal cost at contract lock",
        )
    except (KeyError, TypeError, ValueError, SevenBySevenPenaltyCoordinatorError):
        return None, "The signed 7x7 penalty disclosure snapshot is incomplete or invalid."

    if (
        not policy_version
        or contractual_rate != APPROVED_CONTRACTUAL_MONTHLY_RATE
        or proration_days != APPROVED_PRORATION_DAYS
        or legal_rate_ceiling <= 0
        or lifetime_ceiling < 0
        or counted_at_lock < 0
        or counted_at_lock > lifetime_ceiling
        or len(terms_fingerprint) != 64
        or any(char not in "0123456789abcdef" for char in terms_fingerprint)
    ):
        return None, "The signed 7x7 penalty disclosure snapshot does not match the approved policy boundary."

    cursor.execute(
        """
        select
            id,
            loan_id,
            terms_fingerprint,
            applicability_review_ready,
            pricing_cap_review_ready,
            disclosure_ready,
            total_cost_cap_review_ready,
            penalty_policy_version,
            penalty_monthly_rate,
            penalty_proration_days,
            penalty_rate_ceiling,
            lifetime_nonprincipal_cost_ceiling,
            counted_nonprincipal_cost_at_contract_lock
        from lending.seven_by_seven_pricing_compliance_reviews
        where id = %s
          and loan_id = %s
        """,
        (review_id, loan.loan_id),
    )
    row = cursor.fetchone()
    if row is None:
        return None, "The signed 7x7 penalty disclosure references missing compliance evidence."

    (
        stored_review_id,
        stored_loan_id,
        stored_fingerprint,
        applicability_ready,
        pricing_ready,
        disclosure_ready,
        total_cost_ready,
        stored_policy_version,
        stored_contractual_rate,
        stored_proration_days,
        stored_legal_ceiling,
        stored_lifetime_ceiling,
        stored_counted_at_lock,
    ) = row

    complete_readiness = all(
        bool(value)
        for value in (
            applicability_ready,
            pricing_ready,
            disclosure_ready,
            total_cost_ready,
        )
    )
    if not complete_readiness:
        return None, "The exact terms-bound 7x7 pricing/compliance evidence is not ready."

    if (
        stored_loan_id != loan.loan_id
        or int(stored_review_id) != review_id
        or str(stored_fingerprint or "").lower() != terms_fingerprint
        or str(stored_policy_version or "").strip() != policy_version
        or stored_contractual_rate is None
        or Decimal(stored_contractual_rate) != contractual_rate
        or stored_proration_days is None
        or int(stored_proration_days) != proration_days
        or stored_legal_ceiling is None
        or Decimal(stored_legal_ceiling) != legal_rate_ceiling
        or stored_lifetime_ceiling is None
        or Decimal(stored_lifetime_ceiling) != lifetime_ceiling
        or stored_counted_at_lock is None
        or Decimal(stored_counted_at_lock) != counted_at_lock
    ):
        return None, "The signed 7x7 penalty disclosure no longer matches its exact terms-bound compliance evidence."

    return (
        _PenaltyAuthority(
            review_id=review_id,
            terms_fingerprint=terms_fingerprint,
            policy_version=policy_version,
            contractual_monthly_rate=contractual_rate,
            proration_days=proration_days,
            legal_rate_ceiling=legal_rate_ceiling,
            lifetime_nonprincipal_cost_ceiling=lifetime_ceiling,
            counted_nonprincipal_cost_at_contract_lock=counted_at_lock,
        ),
        "",
    )


def _assessment_rollup(
    cursor: Any,
    *,
    loan_id: UUID,
) -> tuple[Decimal, Decimal, Decimal, date | None]:
    cursor.execute(
        """
        select
            to_regclass('lending.seven_by_seven_penalty_assessments'),
            to_regclass('lending.seven_by_seven_penalty_payment_allocations')
        """
    )
    relation_row = cursor.fetchone()
    if relation_row is None or relation_row[0] is None or relation_row[1] is None:
        # Historical validators intentionally replay schemas older than migration
        # 0118. Such schemas cannot contain penalty evidence. Treat their rollup as
        # empty so pre-maturity behavior remains compatible; post-maturity still
        # fails closed because no exact signed penalty authority snapshot exists.
        return ZERO, ZERO, ZERO, None

    cursor.execute(
        """
        select
            coalesce((
                select sum(assessment.assessed_penalty_amount)
                from lending.seven_by_seven_penalty_assessments assessment
                where assessment.loan_id = %s
            ), 0)::numeric,
            coalesce((
                select sum(allocation.amount_applied)
                from lending.seven_by_seven_penalty_payment_allocations allocation
                join lending.collection_transactions transaction
                  on transaction.id = allocation.transaction_id
                where allocation.loan_id = %s
                  and transaction.is_voided = false
            ), 0)::numeric,
            (
                select max(assessment.assessed_through_date)
                from lending.seven_by_seven_penalty_assessments assessment
                where assessment.loan_id = %s
            )
        """,
        (loan_id, loan_id, loan_id),
    )
    row = cursor.fetchone()
    assert row is not None
    assessed = _money(row[0])
    paid = _money(row[1])
    outstanding = _money(max(ZERO, assessed - paid))
    return assessed, paid, outstanding, row[2]


def _historical_assessment_invalidation_reason(
    cursor: Any,
    *,
    loan_id: UUID,
    schedule_id: UUID,
) -> str:
    cursor.execute(
        """
        select 1
        from lending.seven_by_seven_penalty_assessments assessment
        join lending.collection_transactions source_transaction
          on source_transaction.id = assessment.source_transaction_id
        where assessment.loan_id = %s
          and source_transaction.is_voided = true
        limit 1
        """,
        (loan_id,),
    )
    if cursor.fetchone() is not None:
        return "A source transaction for immutable penalty evidence was voided after assessment. Management review is required."

    cursor.execute(
        """
        select 1
        from lending.seven_by_seven_penalty_assessments assessment
        join lending.collection_transactions transaction
          on transaction.loan_id = assessment.loan_id
        where assessment.loan_id = %s
          and transaction.is_voided = false
          and transaction.entry_type in ('payment', 'advance')
          and transaction.amount > 0
          and transaction.collection_date >= assessment.assessment_start_date
          and transaction.collection_date < assessment.assessed_through_date
          and coalesce(transaction.accepted_at, transaction.recorded_at)
              > assessment.created_at
        limit 1
        """,
        (loan_id,),
    )
    if cursor.fetchone() is not None:
        return "A later-accepted backdated cash event falls inside an already assessed penalty period. Management review is required."

    cursor.execute(
        """
        select 1
        from lending.seven_by_seven_penalty_assessments assessment
        join lending.loan_schedule_adjustments original
          on original.schedule_id = %s
         and original.adjustment_type = 'no_collection'
         and original.no_collection_date >= assessment.assessment_start_date
         and original.no_collection_date <= assessment.assessed_through_date
        join lending.loan_schedule_adjustments reversal
          on reversal.reverses_adjustment_id = original.id
         and reversal.adjustment_type = 'reversal'
        where assessment.loan_id = %s
          and reversal.created_at > assessment.created_at
        limit 1
        """,
        (schedule_id, loan_id),
    )
    if cursor.fetchone() is not None:
        return "A Management No Collection adjustment affecting an assessed penalty period was later reversed. Management review is required."
    return ""


def _opening_contractual_base(
    cursor: Any,
    *,
    loan: _LoanScheduleAuthority,
    penalty_day: date,
) -> Decimal:
    payment_start = loan.date_released + timedelta(days=1)
    try:
        baseline = replay_verified_seven_by_seven_financial_state(
            cursor,
            loan_id=loan.loan_id,
            original_principal=loan.principal,
            daily_interest_per_1000=loan.daily_interest_per_1000,
            payment_start=payment_start,
            through_date=penalty_day - timedelta(days=1),
            contractual_maturity=loan.contractual_maturity,
        )
        probe_id = f"penalty-opening-base-probe:{penalty_day.isoformat()}"
        result = allocate_seven_by_seven_payments(
            original_principal=loan.principal,
            daily_interest_per_1000=loan.daily_interest_per_1000,
            payment_start=payment_start,
            events=baseline.historical_events
            + (
                SevenBySevenCashEvent(
                    event_id=probe_id,
                    collection_date=penalty_day,
                    amount=PROBE_CASH,
                ),
            ),
            contractual_maturity=loan.contractual_maturity,
            interest_holiday_dates=baseline.interest_holiday_dates,
        )
    except (SevenBySevenAdvanceActivationError, SevenBySevenAllocationError) as error:
        raise SevenBySevenPenaltyCoordinatorError(
            "Protected 7x7 financial replay cannot establish the opening overdue contractual base."
        ) from error

    probe = result.allocations[-1]
    if probe.event_id != probe_id:
        raise SevenBySevenPenaltyCoordinatorError(
            "Protected 7x7 financial replay did not return the penalty opening-base probe."
        )
    return _money(probe.opening_remaining_principal + probe.interest_due)


def _management_no_collection_protected_amount(
    cursor: Any,
    *,
    loan_id: UUID,
    schedule_id: UUID,
    penalty_day: date,
) -> Decimal:
    cursor.execute(
        """
        with protected_installments as (
            select distinct item.installment_id
            from lending.loan_schedule_adjustments adjustment
            join lending.loan_schedule_adjustment_items item
              on item.adjustment_id = adjustment.id
            where adjustment.loan_id = %s
              and adjustment.schedule_id = %s
              and adjustment.adjustment_type = 'no_collection'
              and adjustment.no_collection_date <= %s
              and not exists (
                    select 1
                    from lending.loan_schedule_adjustments reversal
                    where reversal.reverses_adjustment_id = adjustment.id
              )
        )
        select coalesce(sum(
            greatest(
                installment.operational_amount
                - least(
                    installment.operational_amount,
                    coalesce(paid.allocated_before_day, 0)
                ),
                0
            )
        ), 0)::numeric(18,2)
        from protected_installments protected
        join lending.loan_contract_installments_operational installment
          on installment.id = protected.installment_id
        left join lateral (
            select coalesce(sum(allocation.amount_applied) filter (
                where transaction.is_voided = false
                  and transaction.collection_date < %s
                  and allocation.allocation_basis <> 'voluntary_extra_tail'
            ), 0)::numeric(18,2) as allocated_before_day
            from lending.loan_installment_payment_allocations allocation
            join lending.collection_transactions transaction
              on transaction.id = allocation.transaction_id
            where allocation.installment_id = installment.id
        ) paid on true
        where installment.schedule_id = %s
          and installment.removed_from_operational_schedule = false
          and %s <= installment.effective_due_date
        """,
        (
            loan_id,
            schedule_id,
            penalty_day,
            penalty_day,
            schedule_id,
            penalty_day,
        ),
    )
    row = cursor.fetchone()
    return _money(row[0] if row else ZERO)


def _eligible_base_for_day(
    cursor: Any,
    *,
    loan: _LoanScheduleAuthority,
    penalty_day: date,
) -> Decimal:
    contractual_base = _opening_contractual_base(
        cursor,
        loan=loan,
        penalty_day=penalty_day,
    )
    protected = _management_no_collection_protected_amount(
        cursor,
        loan_id=loan.loan_id,
        schedule_id=loan.schedule_id,
        penalty_day=penalty_day,
    )
    return _money(max(ZERO, contractual_base - min(contractual_base, protected)))


def _build_base_segments(
    cursor: Any,
    *,
    loan: _LoanScheduleAuthority,
    start_date: date,
    end_date: date,
) -> tuple[PenaltyBaseSegment, ...]:
    if start_date > end_date:
        return ()

    segments: list[PenaltyBaseSegment] = []
    day = start_date
    current_start = day
    current_base = _eligible_base_for_day(cursor, loan=loan, penalty_day=day)
    current_end = day
    day += timedelta(days=1)

    while day <= end_date:
        eligible_base = _eligible_base_for_day(cursor, loan=loan, penalty_day=day)
        if eligible_base == current_base:
            current_end = day
        else:
            segments.append(
                PenaltyBaseSegment(
                    start_date=current_start,
                    end_date=current_end,
                    eligible_base=current_base,
                )
            )
            current_start = day
            current_end = day
            current_base = eligible_base
        day += timedelta(days=1)

    segments.append(
        PenaltyBaseSegment(
            start_date=current_start,
            end_date=current_end,
            eligible_base=current_base,
        )
    )
    return tuple(segments)


def _review_required_state(
    *,
    loan_id: UUID,
    schedule_id: UUID | None,
    contractual_maturity: date | None,
    as_of_date: date,
    reason: str,
    assessed_penalty_balance: Decimal = ZERO,
    authority: _PenaltyAuthority | None = None,
) -> SevenBySevenPenaltyState:
    effective_rate = ZERO
    remaining_headroom = ZERO
    review_id: int | None = None
    fingerprint = ""
    contractual_rate = Decimal("0")
    legal_ceiling = Decimal("0")
    proration_days = 0
    lifetime_ceiling = ZERO
    cumulative_counted = ZERO
    if authority is not None:
        review_id = authority.review_id
        fingerprint = authority.terms_fingerprint
        contractual_rate = authority.contractual_monthly_rate
        legal_ceiling = authority.legal_rate_ceiling
        proration_days = authority.proration_days
        lifetime_ceiling = _money(authority.lifetime_nonprincipal_cost_ceiling)
        effective_rate = min(contractual_rate, legal_ceiling)
    return SevenBySevenPenaltyState(
        loan_id=loan_id,
        schedule_id=schedule_id,
        pricing_compliance_review_id=review_id,
        terms_fingerprint=fingerprint,
        contractual_maturity=contractual_maturity,
        as_of_date=as_of_date,
        status="management_review_required",
        projected_penalty=ZERO,
        assessed_penalty_balance=_money(assessed_penalty_balance),
        penalty_base=ZERO,
        remaining_cost_headroom=remaining_headroom,
        effective_monthly_rate=effective_rate,
        management_review_required_reason=reason,
        contractual_monthly_rate=contractual_rate,
        legal_rate_ceiling=legal_ceiling,
        penalty_proration_days=proration_days,
        lifetime_nonprincipal_cost_ceiling=lifetime_ceiling,
        cumulative_counted_nonprincipal_charges=cumulative_counted,
    )


def project_verified_seven_by_seven_penalty_state(
    cursor: Any,
    *,
    loan_id: UUID,
    as_of_date: date,
) -> SevenBySevenPenaltyState:
    """Project server-authoritative 7x7 post-maturity penalty without writing evidence."""

    loan, loan_reason = _load_loan_schedule_authority(cursor, loan_id=loan_id)
    if loan is None:
        return _review_required_state(
            loan_id=loan_id,
            schedule_id=None,
            contractual_maturity=None,
            as_of_date=as_of_date,
            reason=loan_reason,
        )

    total_assessed, _paid, assessed_outstanding, last_assessed_through = _assessment_rollup(
        cursor,
        loan_id=loan_id,
    )

    if as_of_date <= loan.contractual_maturity:
        return SevenBySevenPenaltyState(
            loan_id=loan_id,
            schedule_id=loan.schedule_id,
            pricing_compliance_review_id=None,
            terms_fingerprint="",
            contractual_maturity=loan.contractual_maturity,
            as_of_date=as_of_date,
            status="not_applicable",
            projected_penalty=ZERO,
            assessed_penalty_balance=assessed_outstanding,
            penalty_base=ZERO,
            remaining_cost_headroom=ZERO,
            effective_monthly_rate=ZERO,
        )

    authority, authority_reason = _load_penalty_authority(cursor, loan=loan)
    if authority is None:
        return _review_required_state(
            loan_id=loan_id,
            schedule_id=loan.schedule_id,
            contractual_maturity=loan.contractual_maturity,
            as_of_date=as_of_date,
            reason=authority_reason,
            assessed_penalty_balance=assessed_outstanding,
        )

    invalidation_reason = _historical_assessment_invalidation_reason(
        cursor,
        loan_id=loan_id,
        schedule_id=loan.schedule_id,
    )
    if invalidation_reason:
        return _review_required_state(
            loan_id=loan_id,
            schedule_id=loan.schedule_id,
            contractual_maturity=loan.contractual_maturity,
            as_of_date=as_of_date,
            reason=invalidation_reason,
            assessed_penalty_balance=assessed_outstanding,
            authority=authority,
        )

    cumulative_counted = authority.counted_nonprincipal_cost_at_contract_lock + total_assessed
    projection_start = max(
        loan.contractual_maturity + timedelta(days=1),
        (
            last_assessed_through + timedelta(days=1)
            if last_assessed_through is not None
            else loan.contractual_maturity + timedelta(days=1)
        ),
    )

    try:
        segments = _build_base_segments(
            cursor,
            loan=loan,
            start_date=projection_start,
            end_date=as_of_date,
        )
        current_base = _eligible_base_for_day(
            cursor,
            loan=loan,
            penalty_day=as_of_date,
        )
        projection = project_seven_by_seven_post_maturity_penalty(
            contractual_maturity=loan.contractual_maturity,
            as_of_date=as_of_date,
            base_segments=segments,
            contractual_monthly_rate=authority.contractual_monthly_rate,
            legal_rate_ceiling=authority.legal_rate_ceiling,
            proration_days=authority.proration_days,
            lifetime_nonprincipal_cost_ceiling=authority.lifetime_nonprincipal_cost_ceiling,
            cumulative_counted_nonprincipal_charges=cumulative_counted,
        )
    except (SevenBySevenPenaltyCoordinatorError, SevenBySevenPenaltyError) as error:
        return _review_required_state(
            loan_id=loan_id,
            schedule_id=loan.schedule_id,
            contractual_maturity=loan.contractual_maturity,
            as_of_date=as_of_date,
            reason=f"{error} Management review is required.",
            assessed_penalty_balance=assessed_outstanding,
            authority=authority,
        )

    projected = _money(projection.rounded_assessable_penalty)
    remaining_headroom = _money(projection.remaining_cost_headroom)
    opening_base = segments[0].eligible_base if segments else current_base
    if remaining_headroom <= ZERO and current_base > ZERO:
        status = "cap_exhausted"
    elif projected > ZERO:
        status = "projected"
    elif assessed_outstanding > ZERO:
        status = "penalty_outstanding"
    elif current_base <= ZERO:
        status = "settled"
    else:
        status = "current"

    return SevenBySevenPenaltyState(
        loan_id=loan_id,
        schedule_id=loan.schedule_id,
        pricing_compliance_review_id=authority.review_id,
        terms_fingerprint=authority.terms_fingerprint,
        contractual_maturity=loan.contractual_maturity,
        as_of_date=as_of_date,
        status=status,
        projected_penalty=projected,
        assessed_penalty_balance=assessed_outstanding,
        penalty_base=current_base,
        remaining_cost_headroom=remaining_headroom,
        effective_monthly_rate=projection.effective_monthly_rate,
        projection_start_date=projection_start,
        opening_penalty_base=opening_base,
        theoretical_penalty_exact=projection.theoretical_penalty,
        contractual_monthly_rate=authority.contractual_monthly_rate,
        legal_rate_ceiling=authority.legal_rate_ceiling,
        penalty_proration_days=authority.proration_days,
        lifetime_nonprincipal_cost_ceiling=_money(
            authority.lifetime_nonprincipal_cost_ceiling
        ),
        cumulative_counted_nonprincipal_charges=_money(cumulative_counted),
        base_segments=segments,
    )


def freeze_verified_seven_by_seven_penalty_assessment(
    cursor: Any,
    *,
    loan_id: UUID,
    through_date: date,
    source_transaction_id: UUID,
) -> SevenBySevenPenaltyState:
    """Freeze one positive aggregate assessment under the loan row lock."""

    cursor.execute(
        "select id from lending.loans where id = %s for update",
        (loan_id,),
    )
    if cursor.fetchone() is None:
        return _review_required_state(
            loan_id=loan_id,
            schedule_id=None,
            contractual_maturity=None,
            as_of_date=through_date,
            reason="The 7x7 loan no longer exists. Management review is required.",
        )

    cursor.execute(
        """
        select loan_id, entry_type, is_voided
        from lending.collection_transactions
        where id = %s
        """,
        (source_transaction_id,),
    )
    source = cursor.fetchone()
    if (
        source is None
        or source[0] != loan_id
        or str(source[1]) != "payment"
        or bool(source[2])
    ):
        return _review_required_state(
            loan_id=loan_id,
            schedule_id=None,
            contractual_maturity=None,
            as_of_date=through_date,
            reason="A non-voided same-loan Payment transaction is required before penalty assessment can be frozen.",
        )

    state = project_verified_seven_by_seven_penalty_state(
        cursor,
        loan_id=loan_id,
        as_of_date=through_date,
    )
    if state.status == "management_review_required" or state.projected_penalty <= ZERO:
        return state
    if (
        state.schedule_id is None
        or state.pricing_compliance_review_id is None
        or state.contractual_maturity is None
        or state.projection_start_date is None
    ):
        return _review_required_state(
            loan_id=loan_id,
            schedule_id=state.schedule_id,
            contractual_maturity=state.contractual_maturity,
            as_of_date=through_date,
            reason="Complete penalty assessment authority is unavailable. Management review is required.",
            assessed_penalty_balance=state.assessed_penalty_balance,
        )

    evidence = {
        "policy": "seven_by_seven_post_maturity_penalty_v1",
        "segments": [
            {
                "start_date": segment.start_date.isoformat(),
                "end_date": segment.end_date.isoformat(),
                "eligible_base": format(segment.eligible_base, "f"),
            }
            for segment in state.base_segments
        ],
        "payment_date_sequence": "opening_base_then_penalty_then_same_day_payment",
        "rounding": "exact_then_php_cent_round_half_up_at_financial_boundary",
    }
    cursor.execute(
        """
        insert into lending.seven_by_seven_penalty_assessments (
            loan_id,
            schedule_id,
            pricing_compliance_review_id,
            terms_fingerprint,
            assessment_start_date,
            assessed_through_date,
            opening_penalty_base,
            calculation_evidence,
            contractual_monthly_rate,
            legal_rate_ceiling,
            effective_monthly_rate,
            penalty_proration_days,
            theoretical_penalty_exact,
            opening_cost_headroom,
            assessed_penalty_amount,
            source_transaction_id
        ) values (
            %s, %s, %s, %s, %s, %s, %s, %s::jsonb,
            %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            loan_id,
            state.schedule_id,
            state.pricing_compliance_review_id,
            state.terms_fingerprint,
            state.projection_start_date,
            through_date,
            state.opening_penalty_base,
            json.dumps(evidence, sort_keys=True, separators=(",", ":")),
            state.contractual_monthly_rate,
            state.legal_rate_ceiling,
            state.effective_monthly_rate,
            state.penalty_proration_days,
            state.theoretical_penalty_exact,
            state.remaining_cost_headroom,
            state.projected_penalty,
            source_transaction_id,
        ),
    )
    return project_verified_seven_by_seven_penalty_state(
        cursor,
        loan_id=loan_id,
        as_of_date=through_date,
    )


def allocate_verified_seven_by_seven_penalty_cash(
    cursor: Any,
    *,
    loan_id: UUID,
    transaction_id: UUID,
    amount_applied: Decimal,
) -> Decimal:
    """Apply one aggregate payment amount to already assessed penalty evidence."""

    amount = _money(amount_applied)
    if amount <= ZERO:
        raise SevenBySevenPenaltyCoordinatorError(
            "Penalty cash allocation must be greater than zero."
        )

    cursor.execute(
        """
        select amount_applied
        from lending.seven_by_seven_penalty_payment_allocations
        where transaction_id = %s
        """,
        (transaction_id,),
    )
    existing = cursor.fetchone()
    if existing is not None:
        stored = _money(existing[0])
        if stored != amount:
            raise SevenBySevenPenaltyCoordinatorError(
                "The payment transaction already carries a different immutable penalty allocation."
            )
        return stored

    cursor.execute(
        """
        select loan_id, entry_type, is_voided
        from lending.collection_transactions
        where id = %s
        for update
        """,
        (transaction_id,),
    )
    transaction = cursor.fetchone()
    if (
        transaction is None
        or transaction[0] != loan_id
        or str(transaction[1]) != "payment"
        or bool(transaction[2])
    ):
        raise SevenBySevenPenaltyCoordinatorError(
            "Penalty cash requires a non-voided same-loan Payment transaction."
        )

    _assessed, _paid, outstanding, _through = _assessment_rollup(
        cursor,
        loan_id=loan_id,
    )
    if amount > outstanding:
        raise SevenBySevenPenaltyCoordinatorError(
            "Penalty cash allocation cannot exceed assessed penalty outstanding."
        )

    cursor.execute(
        """
        insert into lending.seven_by_seven_penalty_payment_allocations (
            loan_id, transaction_id, amount_applied
        ) values (%s, %s, %s)
        """,
        (loan_id, transaction_id, amount),
    )
    return amount
