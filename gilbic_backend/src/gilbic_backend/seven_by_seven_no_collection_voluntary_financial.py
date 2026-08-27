from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .seven_by_seven_advance_activation import SevenBySevenAdvanceFinancialReplay
from .seven_by_seven_no_collection_voluntary import NoCollectionVoluntaryPlan
from .seven_by_seven_operational_allocator import (
    ZERO,
    SevenBySevenAllocationError,
    SevenBySevenAllocationLine,
    SevenBySevenAllocationResult,
    SevenBySevenCashEvent,
    allocate_seven_by_seven_payments,
    money,
)


class SevenBySevenNoCollectionVoluntaryFinancialError(ValueError):
    """Raised when NC voluntary cash cannot reconcile to protected 7x7 replay."""

    code = "seven_by_seven_no_collection_voluntary_financial_conflict"


@dataclass(frozen=True, slots=True)
class NoCollectionVoluntaryFinancialProjection:
    result: SevenBySevenAllocationResult
    pending_line: SevenBySevenAllocationLine | None
    pending_event_id: str | None


def project_no_collection_voluntary_financial_state(
    *,
    baseline: SevenBySevenAdvanceFinancialReplay,
    plan: NoCollectionVoluntaryPlan,
    collection_date: date,
    original_principal: Decimal | int | str,
    daily_interest_per_1000: Decimal | int | str,
    payment_start: date,
    previous_balance: Decimal | int | str,
    affected_installment_id: int,
    affected_deferred_prepaid_amount: Decimal | int | str,
    pending_event_id: str,
) -> NoCollectionVoluntaryFinancialProjection:
    """Project the exact post-receipt 7x7 financial state before immutable writes.

    A partial NC receipt may contain custody cash that is intentionally deferred
    to the shifted signed installment. Only ``plan.immediate_financial_cash_amount``
    becomes a cash event today. If the current receipt fully completes the affected
    installment, the source NC holiday is removed and only *prior deferred* evidence
    is activated on the original NC date. Prior ordinary payment evidence is already
    present in ``baseline.historical_events`` and must never be counted twice.

    The caller writes the immutable receipt/evidence only after this projection
    succeeds, then performs a full database replay and requires an exact match.
    """

    prior_balance = money(previous_balance)
    if baseline.result.closing_remaining_principal != prior_balance:
        raise SevenBySevenNoCollectionVoluntaryFinancialError(
            "The stored 7x7 balance no longer matches protected financial replay before the No Collection receipt."
        )

    deferred_before = money(affected_deferred_prepaid_amount)
    prepaid_before = money(plan.affected_prepaid_before)
    if deferred_before < ZERO or deferred_before > prepaid_before:
        raise SevenBySevenNoCollectionVoluntaryFinancialError(
            "Deferred No Collection prepayment evidence does not reconcile to prior affected-installment payment evidence."
        )

    historical = tuple(baseline.historical_events)
    holidays = set(baseline.interest_holiday_dates)
    events: list[SevenBySevenCashEvent]

    if plan.status == "full_voluntary_completion":
        holidays.discard(collection_date)
        before_today = [event for event in historical if event.collection_date < collection_date]
        today = [event for event in historical if event.collection_date == collection_date]
        after_today = [event for event in historical if event.collection_date > collection_date]
        if after_today:
            raise SevenBySevenNoCollectionVoluntaryFinancialError(
                "Protected 7x7 replay contains future financial events beyond the receipt date."
            )
        events = before_today
        if deferred_before > ZERO:
            events.append(
                SevenBySevenCashEvent(
                    event_id=f"nc-completion-activation:{affected_installment_id}",
                    collection_date=collection_date,
                    amount=deferred_before,
                )
            )
        events.extend(today)
    else:
        events = list(historical)

    immediate_cash = money(plan.immediate_financial_cash_amount)
    effective_pending_event_id: str | None = None
    if immediate_cash > ZERO:
        effective_pending_event_id = pending_event_id
        events.append(
            SevenBySevenCashEvent(
                event_id=pending_event_id,
                collection_date=collection_date,
                amount=immediate_cash,
            )
        )

    try:
        result = allocate_seven_by_seven_payments(
            original_principal=original_principal,
            daily_interest_per_1000=daily_interest_per_1000,
            payment_start=payment_start,
            events=tuple(events),
            interest_holiday_dates=tuple(sorted(holidays)),
        )
    except SevenBySevenAllocationError as error:
        raise SevenBySevenNoCollectionVoluntaryFinancialError(
            "The No Collection voluntary receipt cannot be projected against protected 7x7 financial history."
        ) from error

    if result.total_unallocated_cash > ZERO:
        raise SevenBySevenNoCollectionVoluntaryFinancialError(
            "The No Collection voluntary receipt would leave unapplied financial cash. Refresh and review the exact payoff/extra disposition."
        )
    if result.closing_remaining_principal > prior_balance:
        raise SevenBySevenNoCollectionVoluntaryFinancialError(
            "The No Collection voluntary receipt would increase protected principal."
        )

    pending_line = None
    if effective_pending_event_id is not None:
        for line in result.allocations:
            if line.event_id == effective_pending_event_id:
                pending_line = line
                break
        if pending_line is None or not pending_line.event_applied:
            raise SevenBySevenNoCollectionVoluntaryFinancialError(
                "The No Collection voluntary receipt did not produce one protected financial allocation line."
            )

    return NoCollectionVoluntaryFinancialProjection(
        result=result,
        pending_line=pending_line,
        pending_event_id=effective_pending_event_id,
    )