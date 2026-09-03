from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .seven_by_seven_operational_allocator import ZERO, money


class SevenBySevenExtraPrincipalError(ValueError):
    """Raised when 7x7 Extra Principal cannot be projected without guessing."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class FutureInstallmentPrincipalState:
    """Current future operational row plus immutable signed-row evidence.

    ``contractual_amount`` / ``principal_component`` / ``interest_component``
    describe the *current operational* row before this Extra Principal action.
    For a row that has never been shortened, the optional ``signed_*`` values
    may be omitted and default to those same values. After a prior Extra
    Principal action, callers pass the original immutable signed components in
    ``signed_*`` while the current operational components remain reduced.

    ``advance_allocated`` is only the Advance still active on this installment
    after any previously-created Refund Due evidence. Historical receipt and
    installment-allocation evidence remains immutable outside this planner.
    """

    installment_id: int
    installment_number: int
    effective_due_date: date
    contractual_amount: Decimal
    principal_component: Decimal
    interest_component: Decimal
    advance_allocated: Decimal = ZERO
    signed_contractual_amount: Decimal | None = None
    signed_principal_component: Decimal | None = None
    signed_interest_component: Decimal | None = None


@dataclass(frozen=True, slots=True)
class ExtraPrincipalInstallmentProjection:
    installment_id: int
    installment_number: int
    effective_due_date: date
    signed_contractual_amount: Decimal
    signed_principal_component: Decimal
    signed_interest_component: Decimal
    prior_operational_principal_component: Decimal
    prior_operational_amount: Decimal
    operational_principal_component: Decimal
    operational_amount: Decimal
    advance_allocated: Decimal
    advance_retained: Decimal
    advance_refund_due: Decimal
    removed_from_operational_schedule: bool


@dataclass(frozen=True, slots=True)
class SevenBySevenExtraPrincipalPlan:
    principal_reduction: Decimal
    prior_future_principal: Decimal
    resulting_future_principal: Decimal
    removed_future_interest: Decimal
    advance_refund_due: Decimal
    installments: tuple[ExtraPrincipalInstallmentProjection, ...]

    @property
    def removed_installment_ids(self) -> tuple[int, ...]:
        return tuple(
            row.installment_id
            for row in self.installments
            if row.removed_from_operational_schedule
        )


def plan_seven_by_seven_extra_principal_tail(
    *,
    principal_reduction: Decimal | int | str,
    future_installments: tuple[FutureInstallmentPrincipalState, ...],
) -> SevenBySevenExtraPrincipalPlan:
    """Project borrower-directed 7x7 Extra Principal against the current tail.

    Extra Principal removes future *principal*, never already-earned interest.
    Starting from the latest current operational row, principal is shortened
    from the tail until the requested reduction is exhausted. A surviving
    boundary row keeps its fixed-original-principal daily interest and only its
    operational principal component is reduced. Fully removed rows carry no
    future interest because principal will already be zero before those dates.

    Immutable signed components are carried into every projection separately
    from prior/current operational components, so a later second Extra Principal
    action shortens the already-shortened tail without rewriting or forgetting
    the original signed schedule.

    Existing active Advance stays attached up to the new operational row amount.
    Any amount that is no longer needed becomes Unused Advance Refund Due. This
    includes both fully removed rows and excess Advance on a shortened boundary
    row. Refund Due is classification evidence only; it does not release cash or
    transfer the amount to another loan.
    """

    reduction = money(principal_reduction)
    if reduction <= ZERO:
        raise SevenBySevenExtraPrincipalError(
            "7x7 Extra Principal must be greater than zero.",
            code="seven_by_seven_extra_principal_amount_invalid",
        )
    if not future_installments:
        raise SevenBySevenExtraPrincipalError(
            "No future 7x7 principal remains for Extra Principal. Use the exact payoff flow.",
            code="seven_by_seven_extra_principal_no_future_rows",
        )

    normalized = tuple(
        normalize_future_installment_principal_state(row) for row in future_installments
    )
    ordered = tuple(
        sorted(
            normalized,
            key=lambda row: (
                row.effective_due_date,
                row.installment_number,
                row.installment_id,
            ),
        )
    )
    if len({row.installment_id for row in ordered}) != len(ordered):
        raise SevenBySevenExtraPrincipalError(
            "Future 7x7 installment identities must be unique.",
            code="seven_by_seven_extra_principal_duplicate_installment",
        )

    future_principal = money(sum((row.principal_component for row in ordered), ZERO))
    if reduction > future_principal:
        raise SevenBySevenExtraPrincipalError(
            "Extra Principal exceeds future scheduled principal. Use the exact payoff flow instead.",
            code="seven_by_seven_extra_principal_exceeds_future_principal",
        )

    amount_left = reduction
    projections_by_id: dict[int, ExtraPrincipalInstallmentProjection] = {}
    removed_interest = ZERO
    refund_due = ZERO

    for row in reversed(ordered):
        principal_removed = money(min(row.principal_component, amount_left))
        resulting_principal = money(row.principal_component - principal_removed)
        amount_left = money(amount_left - principal_removed)

        removed = resulting_principal == ZERO
        if removed:
            operational_amount = ZERO
            active_interest = ZERO
            advance_retained = ZERO
            row_refund_due = row.advance_allocated
            removed_interest = money(removed_interest + row.interest_component)
        else:
            active_interest = row.interest_component
            operational_amount = money(active_interest + resulting_principal)
            advance_retained = money(min(row.advance_allocated, operational_amount))
            row_refund_due = money(row.advance_allocated - advance_retained)

        refund_due = money(refund_due + row_refund_due)
        if money(advance_retained + row_refund_due) != row.advance_allocated:
            raise SevenBySevenExtraPrincipalError(
                "Extra Principal Advance split does not reconcile to the active Advance evidence.",
                code="seven_by_seven_extra_principal_reconciliation_failed",
            )

        projections_by_id[row.installment_id] = ExtraPrincipalInstallmentProjection(
            installment_id=row.installment_id,
            installment_number=row.installment_number,
            effective_due_date=row.effective_due_date,
            signed_contractual_amount=_signed_contractual_amount(row),
            signed_principal_component=_signed_principal_component(row),
            signed_interest_component=_signed_interest_component(row),
            prior_operational_principal_component=row.principal_component,
            prior_operational_amount=row.contractual_amount,
            operational_principal_component=resulting_principal,
            operational_amount=operational_amount,
            advance_allocated=row.advance_allocated,
            advance_retained=advance_retained,
            advance_refund_due=row_refund_due,
            removed_from_operational_schedule=removed,
        )

    if amount_left != ZERO:
        raise SevenBySevenExtraPrincipalError(
            "Extra Principal could not be reconciled to the future 7x7 principal tail.",
            code="seven_by_seven_extra_principal_reconciliation_failed",
        )

    projections = tuple(projections_by_id[row.installment_id] for row in ordered)
    resulting_future_principal = money(future_principal - reduction)
    projected_future_principal = money(
        sum((row.operational_principal_component for row in projections), ZERO)
    )
    if projected_future_principal != resulting_future_principal:
        raise SevenBySevenExtraPrincipalError(
            "Extra Principal projection does not reconcile to resulting future principal.",
            code="seven_by_seven_extra_principal_reconciliation_failed",
        )

    return SevenBySevenExtraPrincipalPlan(
        principal_reduction=reduction,
        prior_future_principal=future_principal,
        resulting_future_principal=resulting_future_principal,
        removed_future_interest=removed_interest,
        advance_refund_due=refund_due,
        installments=projections,
    )


def normalize_future_installment_principal_state(
    row: FutureInstallmentPrincipalState,
) -> FutureInstallmentPrincipalState:
    operational_amount = money(row.contractual_amount)
    operational_principal = money(row.principal_component)
    operational_interest = money(row.interest_component)
    advance = money(row.advance_allocated)
    signed_amount = money(
        row.signed_contractual_amount
        if row.signed_contractual_amount is not None
        else operational_amount
    )
    signed_principal = money(
        row.signed_principal_component
        if row.signed_principal_component is not None
        else operational_principal
    )
    signed_interest = money(
        row.signed_interest_component
        if row.signed_interest_component is not None
        else operational_interest
    )

    if row.installment_id <= 0 or row.installment_number <= 0:
        raise SevenBySevenExtraPrincipalError(
            "Future 7x7 installment identity is invalid.",
            code="seven_by_seven_extra_principal_installment_invalid",
        )
    if operational_principal <= ZERO or operational_interest < ZERO or operational_amount <= ZERO:
        raise SevenBySevenExtraPrincipalError(
            "Future 7x7 operational installment components are invalid.",
            code="seven_by_seven_extra_principal_installment_invalid",
        )
    if money(operational_principal + operational_interest) != operational_amount:
        raise SevenBySevenExtraPrincipalError(
            "Future 7x7 operational installment components do not reconcile.",
            code="seven_by_seven_extra_principal_installment_invalid",
        )
    if signed_principal <= ZERO or signed_interest < ZERO or signed_amount <= ZERO:
        raise SevenBySevenExtraPrincipalError(
            "Future 7x7 signed installment components are invalid.",
            code="seven_by_seven_extra_principal_installment_invalid",
        )
    if money(signed_principal + signed_interest) != signed_amount:
        raise SevenBySevenExtraPrincipalError(
            "Future 7x7 signed installment components do not reconcile.",
            code="seven_by_seven_extra_principal_installment_invalid",
        )
    if operational_principal > signed_principal or operational_amount > signed_amount:
        raise SevenBySevenExtraPrincipalError(
            "A future 7x7 operational row cannot exceed its immutable signed row.",
            code="seven_by_seven_extra_principal_installment_invalid",
        )
    if operational_interest != signed_interest:
        raise SevenBySevenExtraPrincipalError(
            "A surviving future 7x7 row must keep its signed fixed daily interest.",
            code="seven_by_seven_extra_principal_installment_invalid",
        )
    if advance < ZERO or advance > operational_amount:
        raise SevenBySevenExtraPrincipalError(
            "Active 7x7 Advance on a future installment is invalid.",
            code="seven_by_seven_extra_principal_advance_invalid",
        )

    return FutureInstallmentPrincipalState(
        installment_id=row.installment_id,
        installment_number=row.installment_number,
        effective_due_date=row.effective_due_date,
        contractual_amount=operational_amount,
        principal_component=operational_principal,
        interest_component=operational_interest,
        advance_allocated=advance,
        signed_contractual_amount=signed_amount,
        signed_principal_component=signed_principal,
        signed_interest_component=signed_interest,
    )


def _signed_contractual_amount(row: FutureInstallmentPrincipalState) -> Decimal:
    return money(
        row.signed_contractual_amount
        if row.signed_contractual_amount is not None
        else row.contractual_amount
    )


def _signed_principal_component(row: FutureInstallmentPrincipalState) -> Decimal:
    return money(
        row.signed_principal_component
        if row.signed_principal_component is not None
        else row.principal_component
    )


def _signed_interest_component(row: FutureInstallmentPrincipalState) -> Decimal:
    return money(
        row.signed_interest_component
        if row.signed_interest_component is not None
        else row.interest_component
    )
