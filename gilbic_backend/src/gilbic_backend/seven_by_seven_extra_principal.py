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
    """Future signed-row state needed for Extra Principal tail recalculation.

    The signed row itself remains immutable. ``advance_allocated`` is existing
    verified Advance already attached to this exact installment.
    """

    installment_id: int
    installment_number: int
    effective_due_date: date
    contractual_amount: Decimal
    principal_component: Decimal
    interest_component: Decimal
    advance_allocated: Decimal = ZERO


@dataclass(frozen=True, slots=True)
class ExtraPrincipalInstallmentProjection:
    installment_id: int
    installment_number: int
    effective_due_date: date
    signed_contractual_amount: Decimal
    signed_principal_component: Decimal
    signed_interest_component: Decimal
    operational_principal_component: Decimal
    operational_amount: Decimal
    advance_allocated: Decimal
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
    """Project borrower-directed 7x7 Extra Principal against the future tail.

    Extra Principal removes future *principal*, never unearned future interest.
    Starting from the latest future signed row, principal is shortened from the
    tail until the requested reduction is exhausted. A surviving boundary row
    keeps its fixed daily interest and only its operational principal component
    is reduced. Fully removed rows carry no future interest because principal
    will already be zero before those dates.

    Existing verified Advance stays attached to surviving immutable installment
    identity. Advance on a fully removed row becomes Unused Advance refund due.
    If a partially shortened boundary row already contains more Advance than its
    new operational amount, this planner fails closed because the approved
    product decisions do not yet define that partial-boundary refund split.
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

    normalized = tuple(_normalize_row(row) for row in future_installments)
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
            row_refund_due = row.advance_allocated
            removed_interest = money(removed_interest + row.interest_component)
            refund_due = money(refund_due + row_refund_due)
        else:
            operational_amount = money(row.interest_component + resulting_principal)
            row_refund_due = ZERO
            if row.advance_allocated > operational_amount:
                raise SevenBySevenExtraPrincipalError(
                    "A shortened 7x7 boundary installment already has more Advance than its new operational amount. Management review is required before posting Extra Principal.",
                    code="seven_by_seven_extra_principal_boundary_advance_review_required",
                )

        projections_by_id[row.installment_id] = ExtraPrincipalInstallmentProjection(
            installment_id=row.installment_id,
            installment_number=row.installment_number,
            effective_due_date=row.effective_due_date,
            signed_contractual_amount=row.contractual_amount,
            signed_principal_component=row.principal_component,
            signed_interest_component=row.interest_component,
            operational_principal_component=resulting_principal,
            operational_amount=operational_amount,
            advance_allocated=row.advance_allocated,
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


def _normalize_row(
    row: FutureInstallmentPrincipalState,
) -> FutureInstallmentPrincipalState:
    contractual = money(row.contractual_amount)
    principal = money(row.principal_component)
    interest = money(row.interest_component)
    advance = money(row.advance_allocated)

    if row.installment_id <= 0 or row.installment_number <= 0:
        raise SevenBySevenExtraPrincipalError(
            "Future 7x7 installment identity is invalid.",
            code="seven_by_seven_extra_principal_installment_invalid",
        )
    if principal <= ZERO or interest < ZERO or contractual <= ZERO:
        raise SevenBySevenExtraPrincipalError(
            "Future 7x7 installment components are invalid.",
            code="seven_by_seven_extra_principal_installment_invalid",
        )
    if money(principal + interest) != contractual:
        raise SevenBySevenExtraPrincipalError(
            "Future 7x7 signed installment components do not reconcile to its contractual amount.",
            code="seven_by_seven_extra_principal_installment_invalid",
        )
    if advance < ZERO or advance > contractual:
        raise SevenBySevenExtraPrincipalError(
            "Existing 7x7 Advance on a future installment is invalid.",
            code="seven_by_seven_extra_principal_advance_invalid",
        )

    return FutureInstallmentPrincipalState(
        installment_id=row.installment_id,
        installment_number=row.installment_number,
        effective_due_date=row.effective_due_date,
        contractual_amount=contractual,
        principal_component=principal,
        interest_component=interest,
        advance_allocated=advance,
    )
