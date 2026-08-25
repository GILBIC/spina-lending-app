from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from .seven_by_seven_operational_allocator import (
    fixed_daily_interest_for_original_principal,
    money,
)


ZERO = Decimal("0.00")


class SevenBySevenSignedScheduleError(ValueError):
    """Raised when signed 7x7 schedule terms are incomplete or contradictory."""


@dataclass(frozen=True, slots=True)
class SevenBySevenSignedInstallment:
    """One immutable row from the borrower-approved 7x7 base schedule.

    ``contractual_amount`` is the agreed daily payment shown to the borrower.
    Interest/principal components are evidence underneath that amount; they do
    not replace the agreed daily-payment obligation used for Past Due and
    rolling-schedule decisions.
    """

    installment_number: int
    due_date: date
    contractual_amount: Decimal
    principal_component: Decimal
    interest_component: Decimal


def generate_signed_seven_by_seven_schedule(
    *,
    original_principal: Decimal | int | str,
    agreed_daily_payment: Decimal | int | str,
    daily_interest_per_1000: Decimal | int | str,
    first_due_date: date,
) -> tuple[SevenBySevenSignedInstallment, ...]:
    """Generate the immutable base 7x7 schedule from approved signed terms.

    The fixed daily interest is calculated with the same canonical rule used by
    the protected 7x7 operational allocator: every started PHP 1,000 of the
    original principal carries the configured daily interest amount. The agreed
    daily payment must exceed that fixed interest so each normal scheduled row
    contains a principal component.

    Normal rows equal the agreed daily payment. The final row is reduced only
    when the remaining principal is smaller than the normal scheduled principal
    component, keeping the principal total cent-exact. This function builds the
    signed/base schedule only; later rolling extension, catch-up restoration,
    Advance, Principal Reduction, and payoff are separate operational effects.
    """

    principal = money(original_principal)
    daily_payment = money(agreed_daily_payment)
    if principal <= ZERO:
        raise SevenBySevenSignedScheduleError(
            "Original 7x7 principal must be greater than zero."
        )
    if daily_payment <= ZERO:
        raise SevenBySevenSignedScheduleError(
            "The agreed 7x7 daily payment must be greater than zero."
        )

    try:
        fixed_interest = fixed_daily_interest_for_original_principal(
            original_principal=principal,
            daily_interest_per_1000=daily_interest_per_1000,
        )
    except ValueError as error:
        raise SevenBySevenSignedScheduleError(str(error)) from error

    if daily_payment <= fixed_interest:
        raise SevenBySevenSignedScheduleError(
            "The agreed 7x7 daily payment must be greater than the fixed daily interest."
        )

    scheduled_principal = money(daily_payment - fixed_interest)
    full_row_count = int(principal // scheduled_principal)
    principal_in_full_rows = money(scheduled_principal * full_row_count)
    final_principal = money(principal - principal_in_full_rows)

    rows: list[SevenBySevenSignedInstallment] = []
    for index in range(full_row_count):
        rows.append(
            SevenBySevenSignedInstallment(
                installment_number=index + 1,
                due_date=first_due_date + timedelta(days=index),
                contractual_amount=daily_payment,
                principal_component=scheduled_principal,
                interest_component=fixed_interest,
            )
        )

    if final_principal > ZERO:
        rows.append(
            SevenBySevenSignedInstallment(
                installment_number=full_row_count + 1,
                due_date=first_due_date + timedelta(days=full_row_count),
                contractual_amount=money(fixed_interest + final_principal),
                principal_component=final_principal,
                interest_component=fixed_interest,
            )
        )

    if not rows:
        raise SevenBySevenSignedScheduleError(
            "The approved 7x7 terms did not produce a contractual schedule."
        )
    if money(sum((row.principal_component for row in rows), ZERO)) != principal:
        raise SevenBySevenSignedScheduleError(
            "The generated 7x7 schedule does not reconcile to original principal."
        )
    return tuple(rows)
