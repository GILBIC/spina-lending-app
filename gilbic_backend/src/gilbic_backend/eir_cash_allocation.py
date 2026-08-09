from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID


MONEY = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class EirCutoverState:
    loan_id: UUID
    calculation_mode: str
    cutover_date: date
    due_date: date
    measurement_status: str
    daily_eir: Decimal | None
    loan_component: Decimal | None
    accrued_interest_component: Decimal | None
    gross_carrying_amount: Decimal | None


@dataclass(frozen=True, slots=True)
class EirCashSourceEvent:
    transaction_id: UUID
    collection_date: date
    accepted_at: datetime
    entry_type: str
    amount: Decimal
    is_voided: bool = False


@dataclass(frozen=True, slots=True)
class EirCashAllocation:
    transaction_id: UUID
    source_event_key: str
    collection_date: date
    amount: Decimal
    effective_interest_accrued_since_prior_event: Decimal
    gross_carrying_before: Decimal
    accrued_interest_before: Decimal
    loan_component_before: Decimal
    cash_to_accrued_interest: Decimal
    cash_to_loan_component: Decimal
    gross_carrying_after: Decimal
    accrued_interest_after: Decimal
    loan_component_after: Decimal
    posting_eligible: bool
    disposition: str
    message: str


@dataclass(frozen=True, slots=True)
class EirAllocationResult:
    status: str
    message: str
    calculation_mode: str
    cutover_date: date
    due_date: date
    daily_eir: Decimal | None
    opening_gross_carrying_amount: Decimal | None
    opening_accrued_interest_component: Decimal | None
    opening_loan_component: Decimal | None
    total_effective_interest_accrued: Decimal
    closing_gross_carrying_amount: Decimal | None
    closing_accrued_interest_component: Decimal | None
    closing_loan_component: Decimal | None
    allocations: tuple[EirCashAllocation, ...]
    posting_eligible: bool


def _blocked(state: EirCutoverState, status: str, message: str) -> EirAllocationResult:
    return EirAllocationResult(
        status=status,
        message=message,
        calculation_mode=state.calculation_mode,
        cutover_date=state.cutover_date,
        due_date=state.due_date,
        daily_eir=state.daily_eir,
        opening_gross_carrying_amount=(
            money(state.gross_carrying_amount)
            if state.gross_carrying_amount is not None
            else None
        ),
        opening_accrued_interest_component=(
            money(state.accrued_interest_component)
            if state.accrued_interest_component is not None
            else None
        ),
        opening_loan_component=(
            money(state.loan_component) if state.loan_component is not None else None
        ),
        total_effective_interest_accrued=ZERO,
        closing_gross_carrying_amount=None,
        closing_accrued_interest_component=None,
        closing_loan_component=None,
        allocations=(),
        posting_eligible=False,
    )


def allocate_event_date_eir_cash(
    state: EirCutoverState,
    events: tuple[EirCashSourceEvent, ...],
) -> EirAllocationResult:
    """Roll a measured Regular loan forward and split post-cutover cash.

    This is a read-only measurement helper. It mirrors the Stage 5D ordering:
    effective interest accrues once for each elapsed calendar day before that
    day's cash is applied. Multiple cash events on the same date share that one
    daily accrual and are then applied by accepted_at / transaction_id order.

    At every cash-event boundary, cents are reconciled using the Stage 5D.1
    convention: accrued EIR keeps its directly rounded amount and the loan
    component receives the cent residual so gross = accrued + loan exactly.

    The original EIR schedule is not extrapolated beyond contractual maturity.
    Post-maturity cash is blocked for separate credit-deterioration / accounting
    review rather than automatically accruing further interest.

    The returned split is not posting-ready. A later controlled stage must post
    the corresponding EIR accrual before a collection journal can clear account
    1120, and must separately prove fiscal-period / source-write concurrency.
    """

    if state.measurement_status != "measured":
        return _blocked(
            state,
            "cutover_measurement_required",
            "The loan does not have a measured cutover EIR state.",
        )
    if state.cutover_date > state.due_date:
        return _blocked(
            state,
            "post_maturity_review_required",
            "The protected cutover is after contractual maturity, so this roll-forward cannot use the original EIR schedule.",
        )
    if state.calculation_mode == "seven_by_seven":
        return _blocked(
            state,
            "seven_by_seven_policy_review",
            "7x7 cash can change the principal/prepayment profile. Post-cutover 7x7 EIR allocation remains blocked until that modification policy is validated.",
        )
    if state.calculation_mode != "fixed_daily":
        return _blocked(
            state,
            "unsupported_calculation_mode",
            "Only the measured Regular fixed-daily EIR roll-forward is supported by this stage.",
        )
    if (
        state.daily_eir is None
        or state.daily_eir <= 0
        or state.loan_component is None
        or state.accrued_interest_component is None
        or state.gross_carrying_amount is None
    ):
        return _blocked(
            state,
            "cutover_measurement_incomplete",
            "The measured cutover state is missing EIR or carrying-amount components.",
        )

    opening_gross = money(state.gross_carrying_amount)
    opening_accrued = money(state.accrued_interest_component)
    opening_loan = money(state.loan_component)
    if min(opening_gross, opening_accrued, opening_loan) < ZERO:
        return _blocked(
            state,
            "cutover_measurement_invalid",
            "Cutover carrying-amount components cannot be negative.",
        )
    if opening_accrued + opening_loan != opening_gross:
        return _blocked(
            state,
            "cutover_measurement_not_reconciled",
            "Cutover loan and accrued-interest components do not reconcile exactly to gross carrying amount.",
        )

    supported_events = tuple(
        event
        for event in events
        if not event.is_voided
        and event.entry_type in {"payment", "advance"}
        and money(event.amount) > ZERO
    )
    if any(event.collection_date <= state.cutover_date for event in supported_events):
        return _blocked(
            state,
            "cutover_boundary_review",
            "Event-date EIR allocation accepts only cash strictly after the protected cutover date.",
        )

    ordered = tuple(
        sorted(
            supported_events,
            key=lambda item: (item.collection_date, item.accepted_at, item.transaction_id),
        )
    )

    daily_eir = Decimal(state.daily_eir)
    loan_raw = Decimal(opening_loan)
    accrued_raw = Decimal(opening_accrued)
    last_accrual_date = state.cutover_date
    total_interest_raw = Decimal("0")
    allocations: list[EirCashAllocation] = []

    for event in ordered:
        if event.collection_date > state.due_date:
            gross_before = money(loan_raw + accrued_raw)
            accrued_before = money(max(accrued_raw, Decimal("0")))
            loan_before = money(gross_before - accrued_before)
            return EirAllocationResult(
                status="post_maturity_review_required",
                message="A cash event is after contractual maturity. Earlier allocation references are preserved, but the original EIR schedule is not extrapolated beyond maturity.",
                calculation_mode=state.calculation_mode,
                cutover_date=state.cutover_date,
                due_date=state.due_date,
                daily_eir=daily_eir,
                opening_gross_carrying_amount=opening_gross,
                opening_accrued_interest_component=opening_accrued,
                opening_loan_component=opening_loan,
                total_effective_interest_accrued=money(total_interest_raw),
                closing_gross_carrying_amount=gross_before,
                closing_accrued_interest_component=accrued_before,
                closing_loan_component=loan_before,
                allocations=tuple(allocations),
                posting_eligible=False,
            )

        accrued_since_prior = Decimal("0")
        next_day = last_accrual_date + timedelta(days=1)
        while next_day <= event.collection_date:
            daily_interest = (loan_raw + accrued_raw) * daily_eir
            accrued_raw += daily_interest
            accrued_since_prior += daily_interest
            total_interest_raw += daily_interest
            next_day += timedelta(days=1)
        last_accrual_date = event.collection_date

        gross_before = money(loan_raw + accrued_raw)
        accrued_before = money(max(accrued_raw, Decimal("0")))
        loan_before = money(gross_before - accrued_before)
        cash = money(event.amount)

        if cash > gross_before:
            allocations.append(
                EirCashAllocation(
                    transaction_id=event.transaction_id,
                    source_event_key=f"collection:{event.transaction_id}",
                    collection_date=event.collection_date,
                    amount=cash,
                    effective_interest_accrued_since_prior_event=money(accrued_since_prior),
                    gross_carrying_before=gross_before,
                    accrued_interest_before=accrued_before,
                    loan_component_before=loan_before,
                    cash_to_accrued_interest=ZERO,
                    cash_to_loan_component=ZERO,
                    gross_carrying_after=gross_before,
                    accrued_interest_after=accrued_before,
                    loan_component_after=loan_before,
                    posting_eligible=False,
                    disposition="cash_exceeds_carrying_review",
                    message="Cash exceeds the measured EIR gross carrying amount. Allocation stops for source review.",
                )
            )
            return EirAllocationResult(
                status="cash_exceeds_carrying_review",
                message="A collection exceeds the measured EIR carrying amount, so later allocations cannot be derived safely.",
                calculation_mode=state.calculation_mode,
                cutover_date=state.cutover_date,
                due_date=state.due_date,
                daily_eir=daily_eir,
                opening_gross_carrying_amount=opening_gross,
                opening_accrued_interest_component=opening_accrued,
                opening_loan_component=opening_loan,
                total_effective_interest_accrued=money(total_interest_raw),
                closing_gross_carrying_amount=gross_before,
                closing_accrued_interest_component=accrued_before,
                closing_loan_component=loan_before,
                allocations=tuple(allocations),
                posting_eligible=False,
            )

        to_accrued = min(cash, accrued_before)
        to_loan = money(cash - to_accrued)
        gross_after = money(gross_before - cash)
        accrued_after = money(accrued_before - to_accrued)
        loan_after = money(gross_after - accrued_after)

        allocations.append(
            EirCashAllocation(
                transaction_id=event.transaction_id,
                source_event_key=f"collection:{event.transaction_id}",
                collection_date=event.collection_date,
                amount=cash,
                effective_interest_accrued_since_prior_event=money(accrued_since_prior),
                gross_carrying_before=gross_before,
                accrued_interest_before=accrued_before,
                loan_component_before=loan_before,
                cash_to_accrued_interest=to_accrued,
                cash_to_loan_component=to_loan,
                gross_carrying_after=gross_after,
                accrued_interest_after=accrued_after,
                loan_component_after=loan_after,
                posting_eligible=False,
                disposition="allocation_reference_ready",
                message="Read-only EIR cash split is reconciled. Posting remains blocked until the related EIR accrual is posted through a separate protected accounting stage.",
            )
        )

        # Each source-cash boundary becomes the next exact cent ledger basis.
        # This applies the same Stage 5D.1 residual convention after cash.
        accrued_raw = Decimal(accrued_after)
        loan_raw = Decimal(loan_after)

    closing_gross = money(loan_raw + accrued_raw)
    closing_accrued = money(accrued_raw)
    closing_loan = money(closing_gross - closing_accrued)
    return EirAllocationResult(
        status="allocation_reference_ready",
        message="Regular post-cutover cash has a deterministic event-date EIR allocation reference. No journal is created or posted.",
        calculation_mode=state.calculation_mode,
        cutover_date=state.cutover_date,
        due_date=state.due_date,
        daily_eir=daily_eir,
        opening_gross_carrying_amount=opening_gross,
        opening_accrued_interest_component=opening_accrued,
        opening_loan_component=opening_loan,
        total_effective_interest_accrued=money(total_interest_raw),
        closing_gross_carrying_amount=closing_gross,
        closing_accrued_interest_component=closing_accrued,
        closing_loan_component=closing_loan,
        allocations=tuple(allocations),
        posting_eligible=False,
    )
