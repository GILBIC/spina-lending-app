"""Read-only Annex A projection of existing signed 7x7 installment rows.

This module checks supplied rows and terms, not their database provenance,
borrower ownership, approval, pricing legality or signature. The caller must
supply one authorized contractual version. It does not generate a schedule,
allocate payments, accrue charges, render a PDF or write to any record.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, DecimalException, Inexact, localcontext

from .seven_by_seven_signed_schedule import SevenBySevenSignedInstallment


CENT = Decimal("0.01")
ZERO = Decimal("0.00")


class AnnexAProjectionError(ValueError):
    """The supplied contractual data cannot be projected without guessing."""


@dataclass(frozen=True, slots=True)
class AnnexAInstallment:
    installment_number: int
    due_date: date
    contractual_amount: Decimal
    principal_component: Decimal
    interest_component: Decimal
    scheduled_remaining_principal: Decimal


@dataclass(frozen=True, slots=True)
class AnnexAScheduleProjection:
    rows: tuple[AnnexAInstallment, ...]
    maturity_date: date
    total_principal: Decimal
    total_interest: Decimal
    total_due: Decimal
    balance_label: str = "Scheduled Remaining Principal"


def _require_money(value: Decimal, field: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value < ZERO:
        raise AnnexAProjectionError(f"{field} must be a finite nonnegative Decimal.")
    # Validate cents; do not normalize or round the source value for display.
    if value != value.quantize(CENT):
        raise AnnexAProjectionError(f"{field} must contain exact cents.")
    return value


def project_seven_by_seven_annex_a(
    *,
    original_principal: Decimal,
    installments: Sequence[SevenBySevenSignedInstallment],
    expected_installment_count: int,
    expected_first_due_date: date,
    expected_maturity_date: date,
    expected_total_payable: Decimal,
) -> AnnexAScheduleProjection:
    """Copy a complete daily contractual schedule and add its principal balance.

    Scheduled Remaining Principal assumes every contractual installment is paid
    fully and on time; it excludes interest, fees and penalties. It is neither a
    live account balance nor a payoff quote. Invalid inputs are rejected, never
    sorted, filled, clamped or silently rounded. No contractual rows are changed.
    """

    if type(expected_installment_count) is not int or expected_installment_count <= 0:
        raise AnnexAProjectionError(
            "A positive expected installment count is required."
        )
    if (
        type(expected_first_due_date) is not date
        or type(expected_maturity_date) is not date
    ):
        raise AnnexAProjectionError(
            "Exact contractual first and maturity dates are required."
        )
    if not isinstance(installments, Sequence):
        raise AnnexAProjectionError(
            "The complete contractual installment sequence is required."
        )
    source_rows = tuple(installments)
    if len(source_rows) != expected_installment_count:
        raise AnnexAProjectionError(
            "Installment count does not match the approved terms."
        )

    try:
        # Fail closed if the Decimal context cannot represent a result exactly.
        # This is validation/projection, not the loan engine's rounding policy.
        with localcontext() as context:
            context.traps[Inexact] = True
            principal = _require_money(original_principal, "Original principal")
            expected_total = _require_money(expected_total_payable, "Expected total")
            if principal <= ZERO or expected_total <= ZERO:
                raise AnnexAProjectionError(
                    "Original principal and expected total must be positive."
                )

            total_principal = ZERO
            total_interest = ZERO
            total_due = ZERO
            previous_date: date | None = None
            projected: list[AnnexAInstallment] = []

            for number, source in enumerate(source_rows, start=1):
                if not isinstance(source, SevenBySevenSignedInstallment):
                    raise AnnexAProjectionError(
                        "Every row must be a signed-schedule installment."
                    )
                if (
                    type(source.installment_number) is not int
                    or source.installment_number != number
                ):
                    raise AnnexAProjectionError(
                        "Installment numbers must be consecutive and ordered."
                    )
                if type(source.due_date) is not date:
                    raise AnnexAProjectionError(
                        "Every installment requires an exact due date."
                    )
                if previous_date is None:
                    if source.due_date != expected_first_due_date:
                        raise AnnexAProjectionError(
                            "First due date does not match the approved terms."
                        )
                elif (source.due_date - previous_date).days != 1:
                    raise AnnexAProjectionError(
                        "The daily contractual schedule contains a date gap or reorder."
                    )

                row_principal = _require_money(
                    source.principal_component, "Scheduled principal"
                )
                row_interest = _require_money(
                    source.interest_component, "Scheduled interest"
                )
                row_total = _require_money(source.contractual_amount, "Contractual amount")
                if row_total != row_principal + row_interest:
                    raise AnnexAProjectionError(
                        "The contractual amount does not match its components."
                    )

                total_principal += row_principal
                total_interest += row_interest
                total_due += row_total
                remaining = principal - total_principal
                if remaining < ZERO:
                    raise AnnexAProjectionError(
                        "Scheduled principal exceeds original principal."
                    )

                projected.append(
                    AnnexAInstallment(
                        installment_number=source.installment_number,
                        due_date=source.due_date,
                        contractual_amount=source.contractual_amount,
                        principal_component=source.principal_component,
                        interest_component=source.interest_component,
                        scheduled_remaining_principal=remaining,
                    )
                )
                previous_date = source.due_date

            if total_principal != principal:
                raise AnnexAProjectionError(
                    "Scheduled principal does not reconcile to original principal."
                )
            if total_due != expected_total:
                raise AnnexAProjectionError(
                    "Scheduled total does not match the approved total payable."
                )
            if previous_date != expected_maturity_date:
                raise AnnexAProjectionError(
                    "Last installment date does not match contractual maturity."
                )

            return AnnexAScheduleProjection(
                rows=tuple(projected),
                maturity_date=expected_maturity_date,
                total_principal=total_principal,
                total_interest=total_interest,
                total_due=total_due,
            )
    except DecimalException as error:
        raise AnnexAProjectionError(
            "Money must be representable exactly in cents without rounding."
        ) from error
