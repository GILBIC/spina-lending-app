from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable


MONEY = Decimal("0.01")
ZERO = Decimal("0.00")


class SevenBySevenNoCollectionVoluntaryError(ValueError):
    """Raised when an NC-day voluntary payment cannot be planned safely."""

    code = "seven_by_seven_no_collection_voluntary_conflict"


class SevenBySevenNoCollectionExtraChoiceRequired(
    SevenBySevenNoCollectionVoluntaryError
):
    """Raised when cash remains after Past Due and the affected NC row."""

    code = "seven_by_seven_no_collection_extra_choice_required"


@dataclass(frozen=True, slots=True)
class NoCollectionPastDueObligation:
    installment_id: int
    installment_number: int
    effective_due_date: date
    remaining_amount: Decimal


@dataclass(frozen=True, slots=True)
class NoCollectionAffectedInstallment:
    installment_id: int
    installment_number: int
    contractual_amount: Decimal
    prepaid_amount: Decimal = ZERO


@dataclass(frozen=True, slots=True)
class NoCollectionVoluntaryInstruction:
    installment_id: int
    installment_number: int
    target: str
    amount_applied: Decimal


@dataclass(frozen=True, slots=True)
class NoCollectionVoluntaryPlan:
    collection_date: date
    receipt_amount: Decimal
    past_due_cash_amount: Decimal
    affected_cash_amount: Decimal
    affected_prepaid_before: Decimal
    affected_total_after: Decimal
    immediate_financial_cash_amount: Decimal
    shifted_prepayment_amount: Decimal
    prior_advance_activation_amount: Decimal
    keep_interest_holiday: bool
    keep_no_collection_shift: bool
    status: str
    instructions: tuple[NoCollectionVoluntaryInstruction, ...]


def plan_seven_by_seven_no_collection_voluntary_payment(
    *,
    transaction_amount: Decimal | int | str,
    collection_date: date,
    no_collection_date: date,
    past_due_obligations: Iterable[NoCollectionPastDueObligation],
    affected_installment: NoCollectionAffectedInstallment,
) -> NoCollectionVoluntaryPlan:
    """Plan one explicit borrower-directed 7x7 payment on a No Collection day.

    This planner deliberately separates schedule satisfaction from financial
    activation. Older Past Due is always first. Cash left after Past Due may be
    directed to the installment that Management shifted for this No Collection
    date. A partial amount is future prepayment: the interest holiday and shift
    remain. If the affected installment becomes fully satisfied, the caller has
    the evidence needed for the approved full-voluntary exception: the NC date
    becomes interest-bearing for this loan and the one-slot NC shift must be
    removed through an audited operational adjustment.

    Existing Advance on the affected installment is preserved. If a new receipt
    completes a partly prepaid row, ``prior_advance_activation_amount`` identifies
    the earlier Advance value that must activate with the row on the original NC
    date; it must not be counted as new cash again.

    Cash beyond all older Past Due plus the remaining affected installment is
    genuine extra and is rejected here until the borrower chooses an eligible
    Advance/Extra Principal disposition. The planner never guesses that choice.
    """

    amount = _money(transaction_amount)
    if amount <= ZERO:
        raise SevenBySevenNoCollectionVoluntaryError(
            "A voluntary No Collection payment must be greater than zero."
        )
    if collection_date != no_collection_date:
        raise SevenBySevenNoCollectionVoluntaryError(
            "The voluntary No Collection payment must use the active No Collection date."
        )

    contractual = _money(affected_installment.contractual_amount)
    prepaid_before = _money(affected_installment.prepaid_amount)
    if contractual <= ZERO:
        raise SevenBySevenNoCollectionVoluntaryError(
            "The affected No Collection installment must have a positive contractual amount."
        )
    if prepaid_before < ZERO or prepaid_before > contractual:
        raise SevenBySevenNoCollectionVoluntaryError(
            "The affected No Collection installment has invalid prepayment evidence."
        )

    past_due = tuple(
        sorted(
            past_due_obligations,
            key=lambda row: (
                row.effective_due_date,
                row.installment_number,
                row.installment_id,
            ),
        )
    )
    for row in past_due:
        remaining = _money(row.remaining_amount)
        if row.effective_due_date >= collection_date:
            raise SevenBySevenNoCollectionVoluntaryError(
                "Only obligations before the No Collection date may enter Past Due priority."
            )
        if remaining < ZERO:
            raise SevenBySevenNoCollectionVoluntaryError(
                "A Past Due remaining amount cannot be negative."
            )

    cash_left = amount
    past_due_cash = ZERO
    instructions: list[NoCollectionVoluntaryInstruction] = []
    for row in past_due:
        remaining = _money(row.remaining_amount)
        if remaining <= ZERO or cash_left <= ZERO:
            continue
        applied = _money(min(cash_left, remaining))
        instructions.append(
            NoCollectionVoluntaryInstruction(
                installment_id=row.installment_id,
                installment_number=row.installment_number,
                target="past_due",
                amount_applied=applied,
            )
        )
        past_due_cash = _money(past_due_cash + applied)
        cash_left = _money(cash_left - applied)

    affected_remaining_before = _money(contractual - prepaid_before)
    affected_cash = ZERO
    if cash_left > ZERO:
        if affected_remaining_before <= ZERO:
            raise SevenBySevenNoCollectionExtraChoiceRequired(
                "The affected No Collection installment is already fully prepaid. Remaining cash is true extra and needs borrower direction."
            )
        affected_cash = _money(min(cash_left, affected_remaining_before))
        instructions.append(
            NoCollectionVoluntaryInstruction(
                installment_id=affected_installment.installment_id,
                installment_number=affected_installment.installment_number,
                target="affected_no_collection_installment",
                amount_applied=affected_cash,
            )
        )
        cash_left = _money(cash_left - affected_cash)

    if cash_left > ZERO:
        raise SevenBySevenNoCollectionExtraChoiceRequired(
            "Cash remains after all older Past Due and the affected No Collection installment. Choose an eligible extra disposition explicitly."
        )

    affected_total_after = _money(prepaid_before + affected_cash)
    affected_completed_now = (
        affected_cash > ZERO and affected_total_after == contractual
    )

    if affected_completed_now:
        return NoCollectionVoluntaryPlan(
            collection_date=collection_date,
            receipt_amount=amount,
            past_due_cash_amount=past_due_cash,
            affected_cash_amount=affected_cash,
            affected_prepaid_before=prepaid_before,
            affected_total_after=affected_total_after,
            immediate_financial_cash_amount=_money(past_due_cash + affected_cash),
            shifted_prepayment_amount=ZERO,
            prior_advance_activation_amount=prepaid_before,
            keep_interest_holiday=False,
            keep_no_collection_shift=False,
            status="full_voluntary_completion",
            instructions=tuple(instructions),
        )

    if affected_cash > ZERO:
        return NoCollectionVoluntaryPlan(
            collection_date=collection_date,
            receipt_amount=amount,
            past_due_cash_amount=past_due_cash,
            affected_cash_amount=affected_cash,
            affected_prepaid_before=prepaid_before,
            affected_total_after=affected_total_after,
            immediate_financial_cash_amount=past_due_cash,
            shifted_prepayment_amount=affected_cash,
            prior_advance_activation_amount=ZERO,
            keep_interest_holiday=True,
            keep_no_collection_shift=True,
            status="partial_shifted_prepayment",
            instructions=tuple(instructions),
        )

    return NoCollectionVoluntaryPlan(
        collection_date=collection_date,
        receipt_amount=amount,
        past_due_cash_amount=past_due_cash,
        affected_cash_amount=ZERO,
        affected_prepaid_before=prepaid_before,
        affected_total_after=prepaid_before,
        immediate_financial_cash_amount=past_due_cash,
        shifted_prepayment_amount=ZERO,
        prior_advance_activation_amount=ZERO,
        keep_interest_holiday=True,
        keep_no_collection_shift=True,
        status="past_due_only",
        instructions=tuple(instructions),
    )


def _money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)
