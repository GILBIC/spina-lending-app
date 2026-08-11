from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from .eir_cash_allocation import (
    EirCashAllocation,
    EirCashSourceEvent,
    EirCutoverState,
    EirDailyAccrual,
    allocate_event_date_eir_cash,
    money,
)


ZERO = Decimal("0.00")
GREENFIELD_REGULAR_RENEWAL_ROLLFORWARD_POLICY_VERSION = (
    "greenfield_regular_renewal_rollforward_v1"
)


@dataclass(frozen=True, slots=True)
class GreenfieldRegularRenewalRollForward:
    loan_id: UUID
    anchor_date: date
    target_date: date
    contractual_due_date: date
    daily_eir: Decimal
    initial_gross_carrying_amount: Decimal
    initial_accrued_interest_component: Decimal
    initial_loan_component: Decimal
    source_event_count: int
    allocation_count: int
    disposition: str
    blocker_code: str | None
    message: str
    total_effective_interest_accrued: Decimal
    tail_effective_interest_accrued: Decimal
    gross_carrying_amount_at_target: Decimal | None
    accrued_interest_component_at_target: Decimal | None
    loan_component_at_target: Decimal | None
    allocations: tuple[EirCashAllocation, ...]
    tail_daily_accruals: tuple[EirDailyAccrual, ...]
    measurement_preview_ready: bool
    accounting_carrying_amount_ready: bool
    journal_lines_enabled: bool
    automatic_source_posting: bool
    policy_version: str = GREENFIELD_REGULAR_RENEWAL_ROLLFORWARD_POLICY_VERSION


def _blocked(
    *,
    loan_id: UUID,
    anchor_date: date,
    target_date: date,
    contractual_due_date: date,
    daily_eir: Decimal,
    initial_gross_carrying_amount: Decimal,
    initial_accrued_interest_component: Decimal,
    initial_loan_component: Decimal,
    source_event_count: int,
    blocker_code: str,
    message: str,
    allocations: tuple[EirCashAllocation, ...] = (),
) -> GreenfieldRegularRenewalRollForward:
    return GreenfieldRegularRenewalRollForward(
        loan_id=loan_id,
        anchor_date=anchor_date,
        target_date=target_date,
        contractual_due_date=contractual_due_date,
        daily_eir=Decimal(daily_eir),
        initial_gross_carrying_amount=money(initial_gross_carrying_amount),
        initial_accrued_interest_component=money(
            initial_accrued_interest_component
        ),
        initial_loan_component=money(initial_loan_component),
        source_event_count=source_event_count,
        allocation_count=len(allocations),
        disposition="greenfield_regular_renewal_rollforward_preview_blocked",
        blocker_code=blocker_code,
        message=message,
        total_effective_interest_accrued=ZERO,
        tail_effective_interest_accrued=ZERO,
        gross_carrying_amount_at_target=None,
        accrued_interest_component_at_target=None,
        loan_component_at_target=None,
        allocations=allocations,
        tail_daily_accruals=(),
        measurement_preview_ready=False,
        accounting_carrying_amount_ready=False,
        journal_lines_enabled=False,
        automatic_source_posting=False,
    )


def build_greenfield_regular_renewal_rollforward(
    *,
    loan_id: UUID,
    anchor_date: date,
    target_date: date,
    contractual_due_date: date,
    daily_eir: Decimal,
    initial_gross_carrying_amount: Decimal,
    initial_accrued_interest_component: Decimal,
    initial_loan_component: Decimal,
    source_events: tuple[EirCashSourceEvent, ...],
) -> GreenfieldRegularRenewalRollForward:
    """Roll one protected greenfield Regular anchor to a renewal date.

    This is a Stage 5D.26 read-only measurement preview. It intentionally uses
    the already-proven event-date EIR cash allocator for every pre-renewal cash
    boundary, then accrues the final no-cash tail to the renewal business date.
    It does not claim the result is an authoritative ledger carrying amount;
    protected accrual/collection journals must be connected in a later stage.
    """

    opening_gross = money(initial_gross_carrying_amount)
    opening_accrued = money(initial_accrued_interest_component)
    opening_loan = money(initial_loan_component)
    rate = Decimal(daily_eir)

    supported = tuple(
        event
        for event in source_events
        if not event.is_voided
        and event.entry_type in {"payment", "advance"}
        and money(event.amount) > ZERO
        and event.collection_date <= target_date
    )

    if target_date <= anchor_date:
        return _blocked(
            loan_id=loan_id,
            anchor_date=anchor_date,
            target_date=target_date,
            contractual_due_date=contractual_due_date,
            daily_eir=rate,
            initial_gross_carrying_amount=opening_gross,
            initial_accrued_interest_component=opening_accrued,
            initial_loan_component=opening_loan,
            source_event_count=len(supported),
            blocker_code="renewal_execution_after_anchor_required",
            message="The renewal target must be after the protected greenfield release anchor.",
        )
    if target_date > contractual_due_date:
        return _blocked(
            loan_id=loan_id,
            anchor_date=anchor_date,
            target_date=target_date,
            contractual_due_date=contractual_due_date,
            daily_eir=rate,
            initial_gross_carrying_amount=opening_gross,
            initial_accrued_interest_component=opening_accrued,
            initial_loan_component=opening_loan,
            source_event_count=len(supported),
            blocker_code="post_maturity_review_required",
            message="The original Regular EIR schedule is not extrapolated beyond contractual maturity.",
        )
    if rate <= 0:
        return _blocked(
            loan_id=loan_id,
            anchor_date=anchor_date,
            target_date=target_date,
            contractual_due_date=contractual_due_date,
            daily_eir=rate,
            initial_gross_carrying_amount=opening_gross,
            initial_accrued_interest_component=opening_accrued,
            initial_loan_component=opening_loan,
            source_event_count=len(supported),
            blocker_code="verified_contract_eir_required",
            message="A positive daily EIR from the verified signed contract is required.",
        )
    if min(opening_gross, opening_accrued, opening_loan) < ZERO:
        return _blocked(
            loan_id=loan_id,
            anchor_date=anchor_date,
            target_date=target_date,
            contractual_due_date=contractual_due_date,
            daily_eir=rate,
            initial_gross_carrying_amount=opening_gross,
            initial_accrued_interest_component=opening_accrued,
            initial_loan_component=opening_loan,
            source_event_count=len(supported),
            blocker_code="greenfield_anchor_components_invalid",
            message="Protected greenfield carrying components cannot be negative.",
        )
    if opening_accrued + opening_loan != opening_gross:
        return _blocked(
            loan_id=loan_id,
            anchor_date=anchor_date,
            target_date=target_date,
            contractual_due_date=contractual_due_date,
            daily_eir=rate,
            initial_gross_carrying_amount=opening_gross,
            initial_accrued_interest_component=opening_accrued,
            initial_loan_component=opening_loan,
            source_event_count=len(supported),
            blocker_code="greenfield_anchor_not_reconciled",
            message="Protected greenfield loan and accrued-interest components do not reconcile to gross carrying amount.",
        )
    if any(event.collection_date <= anchor_date for event in supported):
        return _blocked(
            loan_id=loan_id,
            anchor_date=anchor_date,
            target_date=target_date,
            contractual_due_date=contractual_due_date,
            daily_eir=rate,
            initial_gross_carrying_amount=opening_gross,
            initial_accrued_interest_component=opening_accrued,
            initial_loan_component=opening_loan,
            source_event_count=len(supported),
            blocker_code="greenfield_anchor_boundary_review",
            message="Only cash strictly after the protected release anchor can enter this roll-forward.",
        )
    if any(event.collection_date == target_date for event in supported):
        return _blocked(
            loan_id=loan_id,
            anchor_date=anchor_date,
            target_date=target_date,
            contractual_due_date=contractual_due_date,
            daily_eir=rate,
            initial_gross_carrying_amount=opening_gross,
            initial_accrued_interest_component=opening_accrued,
            initial_loan_component=opening_loan,
            source_event_count=len(supported),
            blocker_code="same_day_renewal_collection_ordering_review",
            message=(
                "Cash exists on the renewal business date. Stage 5D.26 does not "
                "guess whether that cash belongs before or after renewal execution."
            ),
        )

    pre_target_events = tuple(
        event for event in supported if event.collection_date < target_date
    )
    state = EirCutoverState(
        loan_id=loan_id,
        calculation_mode="fixed_daily",
        cutover_date=anchor_date,
        due_date=contractual_due_date,
        measurement_status="measured",
        daily_eir=rate,
        loan_component=opening_loan,
        accrued_interest_component=opening_accrued,
        gross_carrying_amount=opening_gross,
    )
    allocation = allocate_event_date_eir_cash(state, pre_target_events)
    if allocation.status != "allocation_reference_ready":
        return _blocked(
            loan_id=loan_id,
            anchor_date=anchor_date,
            target_date=target_date,
            contractual_due_date=contractual_due_date,
            daily_eir=rate,
            initial_gross_carrying_amount=opening_gross,
            initial_accrued_interest_component=opening_accrued,
            initial_loan_component=opening_loan,
            source_event_count=len(pre_target_events),
            blocker_code=allocation.status,
            message=allocation.message,
            allocations=allocation.allocations,
        )

    if (
        allocation.closing_gross_carrying_amount is None
        or allocation.closing_accrued_interest_component is None
        or allocation.closing_loan_component is None
    ):
        return _blocked(
            loan_id=loan_id,
            anchor_date=anchor_date,
            target_date=target_date,
            contractual_due_date=contractual_due_date,
            daily_eir=rate,
            initial_gross_carrying_amount=opening_gross,
            initial_accrued_interest_component=opening_accrued,
            initial_loan_component=opening_loan,
            source_event_count=len(pre_target_events),
            blocker_code="greenfield_rollforward_closing_state_missing",
            message="The protected event-date allocator did not produce a complete closing state.",
            allocations=allocation.allocations,
        )

    last_boundary = (
        allocation.allocations[-1].collection_date
        if allocation.allocations
        else anchor_date
    )
    loan_raw = Decimal(allocation.closing_loan_component)
    accrued_raw = Decimal(allocation.closing_accrued_interest_component)
    tail_raw = Decimal("0")
    tail_daily: list[EirDailyAccrual] = []

    current_date = last_boundary + timedelta(days=1)
    while current_date <= target_date:
        opening_raw = loan_raw + accrued_raw
        daily_interest = opening_raw * rate
        accrued_raw += daily_interest
        tail_raw += daily_interest
        tail_daily.append(
            EirDailyAccrual(
                accrual_date=current_date,
                opening_gross_carrying_raw=opening_raw,
                effective_interest_raw=daily_interest,
                closing_gross_carrying_raw=loan_raw + accrued_raw,
            )
        )
        current_date += timedelta(days=1)

    target_gross = money(loan_raw + accrued_raw)
    target_accrued = money(max(accrued_raw, Decimal("0")))
    target_loan = money(target_gross - target_accrued)
    tail_interest = money(tail_raw)
    total_interest = money(
        allocation.total_effective_interest_accrued + tail_interest
    )

    if min(target_gross, target_accrued, target_loan) < ZERO:
        return _blocked(
            loan_id=loan_id,
            anchor_date=anchor_date,
            target_date=target_date,
            contractual_due_date=contractual_due_date,
            daily_eir=rate,
            initial_gross_carrying_amount=opening_gross,
            initial_accrued_interest_component=opening_accrued,
            initial_loan_component=opening_loan,
            source_event_count=len(pre_target_events),
            blocker_code="greenfield_rollforward_target_components_invalid",
            message="The measured target carrying components cannot be negative.",
            allocations=allocation.allocations,
        )
    if target_accrued + target_loan != target_gross:
        return _blocked(
            loan_id=loan_id,
            anchor_date=anchor_date,
            target_date=target_date,
            contractual_due_date=contractual_due_date,
            daily_eir=rate,
            initial_gross_carrying_amount=opening_gross,
            initial_accrued_interest_component=opening_accrued,
            initial_loan_component=opening_loan,
            source_event_count=len(pre_target_events),
            blocker_code="greenfield_rollforward_target_not_reconciled",
            message="The measured target carrying components do not reconcile exactly.",
            allocations=allocation.allocations,
        )

    return GreenfieldRegularRenewalRollForward(
        loan_id=loan_id,
        anchor_date=anchor_date,
        target_date=target_date,
        contractual_due_date=contractual_due_date,
        daily_eir=rate,
        initial_gross_carrying_amount=opening_gross,
        initial_accrued_interest_component=opening_accrued,
        initial_loan_component=opening_loan,
        source_event_count=len(pre_target_events),
        allocation_count=len(allocation.allocations),
        disposition="greenfield_regular_renewal_rollforward_preview_ready",
        blocker_code=None,
        message=(
            "Read-only Regular EIR roll-forward reaches the authoritative renewal "
            "business date from the protected greenfield release anchor. The result "
            "is still a measurement preview, not an authoritative ledger carrying "
            "amount, until protected accrual/collection accounting is connected."
        ),
        total_effective_interest_accrued=total_interest,
        tail_effective_interest_accrued=tail_interest,
        gross_carrying_amount_at_target=target_gross,
        accrued_interest_component_at_target=target_accrued,
        loan_component_at_target=target_loan,
        allocations=allocation.allocations,
        tail_daily_accruals=tuple(tail_daily),
        measurement_preview_ready=True,
        accounting_carrying_amount_ready=False,
        journal_lines_enabled=False,
        automatic_source_posting=False,
    )
