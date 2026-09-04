from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import Iterable, Literal, Sequence
from uuid import UUID


MONEY = Decimal("0.01")
PaymentFrequency = Literal[
    "daily",
    "weekly",
    "semi_monthly",
    "monthly",
    "balloon",
    "custom",
]
AllocationBasis = Literal[
    "oldest_due_first",
    "exact_covered_date",
    "voluntary_extra_tail",
    "future_advance_oldest_first",
    "borrower_catch_up_oldest_first",
]
ExtraAllocationChoice = Literal["advance", "principal_reduction"]
InstallmentId = int | UUID | str


class ContractScheduleError(ValueError):
    """Raised when contractual schedule inputs are incomplete or contradictory."""


class PaymentAllocationError(ValueError):
    """Raised when a payment cannot be applied safely to contractual installments."""


@dataclass(frozen=True, slots=True)
class ContractInstallment:
    installment_number: int
    due_date: date
    contractual_amount: Decimal


@dataclass(frozen=True, slots=True)
class OutstandingInstallment:
    installment_id: InstallmentId
    installment_number: int
    due_date: date
    contractual_amount: Decimal
    allocated_amount: Decimal = Decimal("0.00")

    @property
    def remaining_amount(self) -> Decimal:
        remaining = _money(self.contractual_amount) - _money(self.allocated_amount)
        if remaining < 0:
            raise PaymentAllocationError(
                "An installment is over-allocated and must be corrected before another payment is applied."
            )
        return remaining


@dataclass(frozen=True, slots=True)
class AllocationInstruction:
    installment_id: InstallmentId
    installment_number: int
    due_date: date
    amount_applied: Decimal
    allocation_basis: AllocationBasis


def generate_contract_installments(
    *,
    payment_frequency: PaymentFrequency,
    contractual_total: Decimal,
    first_due_date: date | None = None,
    installment_count: int | None = None,
    regular_installment_amount: Decimal | None = None,
    semi_monthly_days: tuple[int, int] = (15, 30),
    custom_installments: Sequence[tuple[date, Decimal]] = (),
) -> tuple[ContractInstallment, ...]:
    """Generate exact contractual due dates and cent-exact installment amounts.

    The caller supplies the terms from the signed contract. This function never
    derives a schedule from a generic SPINA product assumption.
    """

    total = _money(contractual_total)
    if total <= 0:
        raise ContractScheduleError("Contractual total must be greater than zero.")

    if payment_frequency == "custom":
        return _custom_installments(total=total, rows=custom_installments)

    if custom_installments:
        raise ContractScheduleError(
            "Custom installment rows may only be supplied for a custom schedule."
        )
    if first_due_date is None:
        raise ContractScheduleError("The first contractual due date is required.")
    if installment_count is None or installment_count <= 0:
        raise ContractScheduleError("Installment count must be greater than zero.")
    if payment_frequency == "balloon" and installment_count != 1:
        raise ContractScheduleError("A balloon schedule must contain exactly one installment.")

    due_dates = _generate_due_dates(
        payment_frequency=payment_frequency,
        first_due_date=first_due_date,
        installment_count=installment_count,
        semi_monthly_days=semi_monthly_days,
    )
    amounts = _generate_amounts(
        contractual_total=total,
        installment_count=installment_count,
        regular_installment_amount=regular_installment_amount,
    )
    return tuple(
        ContractInstallment(
            installment_number=index + 1,
            due_date=due_date,
            contractual_amount=amounts[index],
        )
        for index, due_date in enumerate(due_dates)
    )


def plan_payment_allocation(
    *,
    transaction_amount: Decimal,
    installments: Iterable[OutstandingInstallment],
    explicit_covered_dates: Sequence[date] = (),
) -> tuple[AllocationInstruction, ...]:
    """Allocate cash without guessing outside the contractual schedule.

    Without an explicit selection, cash goes to the oldest unpaid contractual
    installment, including the next future installment when earlier ones are
    already covered. With explicit covered dates, only those contractual due
    dates may receive the payment.

    This legacy/general planner remains available for protected callers that
    explicitly want oldest-first behavior. New Regular Collector payment flows
    should use :func:`plan_protected_regular_allocation` instead.
    """

    amount = _money(transaction_amount)
    if amount <= 0:
        raise PaymentAllocationError("Payment amount must be greater than zero.")

    rows = tuple(installments)
    if not rows:
        raise PaymentAllocationError("No contractual installments are available for allocation.")

    remaining_rows = [row for row in rows if row.remaining_amount > 0]
    if not remaining_rows:
        raise PaymentAllocationError("The contractual schedule is already fully paid.")

    if explicit_covered_dates:
        selected_dates = tuple(sorted(set(explicit_covered_dates)))
        selected = [
            row
            for row in remaining_rows
            if row.due_date in selected_dates
        ]
        selected_due_dates = {row.due_date for row in selected}
        invalid_dates = [value for value in selected_dates if value not in selected_due_dates]
        if invalid_dates:
            formatted = ", ".join(value.isoformat() for value in invalid_dates)
            raise PaymentAllocationError(
                "Selected covered date is not an unpaid contractual due date: " + formatted
            )
        candidates = sorted(
            selected,
            key=lambda row: (row.due_date, row.installment_number, str(row.installment_id)),
        )
        basis: AllocationBasis = "exact_covered_date"
    else:
        candidates = sorted(
            remaining_rows,
            key=lambda row: (row.due_date, row.installment_number, str(row.installment_id)),
        )
        basis = "oldest_due_first"

    amount_left = amount
    instructions: list[AllocationInstruction] = []
    for row in candidates:
        if amount_left <= 0:
            break
        applied = min(row.remaining_amount, amount_left)
        if applied <= 0:
            continue
        instructions.append(
            AllocationInstruction(
                installment_id=row.installment_id,
                installment_number=row.installment_number,
                due_date=row.due_date,
                amount_applied=_money(applied),
                allocation_basis=basis,
            )
        )
        amount_left = _money(amount_left - applied)

    if amount_left != Decimal("0.00"):
        raise PaymentAllocationError(
            "Payment exceeds the unpaid contractual amount selected for allocation."
        )
    return tuple(instructions)


def plan_protected_regular_allocation(
    *,
    transaction_amount: Decimal,
    installments: Iterable[OutstandingInstallment],
    collection_date: date,
    extra_choice: ExtraAllocationChoice | None = None,
    active_borrower_extension_slots: int = 0,
) -> tuple[AllocationInstruction, ...]:
    """Apply Regular cash using the protected SPINA allocation order.

    Cash first clears every unpaid operational obligation due on or before the
    collection date, oldest first. While borrower-caused extension slots remain,
    normal cash above the current due amount is catch-up and is applied to the
    same number of nearest future operational rows before any cash can become a
    genuine voluntary extra.

    Genuine extra is never guessed. The borrower must explicitly choose either
    ``advance`` (oldest future obligation first) or ``principal_reduction``
    (contractual tail first). Without that choice this function fails closed.
    """

    amount = _money(transaction_amount)
    if amount <= 0:
        raise PaymentAllocationError("Payment amount must be greater than zero.")
    if active_borrower_extension_slots < 0:
        raise PaymentAllocationError("Active borrower extension slots cannot be negative.")

    remaining = sorted(
        (row for row in installments if row.remaining_amount > 0),
        key=lambda row: (row.due_date, row.installment_number, str(row.installment_id)),
    )
    if not remaining:
        raise PaymentAllocationError("The contractual schedule is already fully paid.")

    amount_left = amount
    instructions: list[AllocationInstruction] = []
    due_rows = [row for row in remaining if row.due_date <= collection_date]
    future_rows = [row for row in remaining if row.due_date > collection_date]

    for row in due_rows:
        if amount_left <= 0:
            break
        applied = _money(min(row.remaining_amount, amount_left))
        if applied <= 0:
            continue
        instructions.append(
            AllocationInstruction(
                installment_id=row.installment_id,
                installment_number=row.installment_number,
                due_date=row.due_date,
                amount_applied=applied,
                allocation_basis="oldest_due_first",
            )
        )
        amount_left = _money(amount_left - applied)

    if amount_left <= 0:
        return tuple(instructions)

    catch_up_rows = future_rows[:active_borrower_extension_slots]
    for row in catch_up_rows:
        if amount_left <= 0:
            break
        applied = _money(min(row.remaining_amount, amount_left))
        if applied <= 0:
            continue
        instructions.append(
            AllocationInstruction(
                installment_id=row.installment_id,
                installment_number=row.installment_number,
                due_date=row.due_date,
                amount_applied=applied,
                allocation_basis="borrower_catch_up_oldest_first",
            )
        )
        amount_left = _money(amount_left - applied)

    if amount_left <= 0:
        return tuple(instructions)

    if extra_choice is None:
        raise PaymentAllocationError(
            "Payment includes extra cash after Past Due, Due Today, and borrower catch-up. Choose Advance or Principal Reduction."
        )

    catch_up_ids = {row.installment_id for row in catch_up_rows}
    remaining_future_rows = [
        row for row in future_rows if row.installment_id not in catch_up_ids
    ]
    if extra_choice == "advance":
        extra_candidates = remaining_future_rows
        extra_basis: AllocationBasis = "future_advance_oldest_first"
    elif extra_choice == "principal_reduction":
        extra_candidates = list(reversed(remaining_future_rows))
        extra_basis = "voluntary_extra_tail"
    else:
        raise PaymentAllocationError("Choose a valid extra allocation: Advance or Principal Reduction.")

    for row in extra_candidates:
        if amount_left <= 0:
            break
        applied = _money(min(row.remaining_amount, amount_left))
        if applied <= 0:
            continue
        instructions.append(
            AllocationInstruction(
                installment_id=row.installment_id,
                installment_number=row.installment_number,
                due_date=row.due_date,
                amount_applied=applied,
                allocation_basis=extra_basis,
            )
        )
        amount_left = _money(amount_left - applied)

    if amount_left != Decimal("0.00"):
        raise PaymentAllocationError(
            "Payment exceeds the remaining contractual balance. Use the exact payoff amount."
        )
    return tuple(instructions)


def plan_scheduled_or_voluntary_extra_allocation(
    *,
    transaction_amount: Decimal,
    installments: Iterable[OutstandingInstallment],
    voluntary_extra: bool,
) -> tuple[AllocationInstruction, ...]:
    """Compatibility wrapper for callers using the earlier extra-cash contract.

    New Collector flows must not use the ambiguous ``voluntary_extra`` concept.
    They should call :func:`plan_protected_regular_allocation` with an explicit
    borrower choice. This wrapper remains only while older internal callers are
    migrated.
    """

    remaining = sorted(
        (row for row in installments if row.remaining_amount > 0),
        key=lambda row: (row.due_date, row.installment_number, str(row.installment_id)),
    )
    if not remaining:
        raise PaymentAllocationError("The contractual schedule is already fully paid.")
    return plan_protected_regular_allocation(
        transaction_amount=transaction_amount,
        installments=remaining,
        collection_date=remaining[0].due_date,
        extra_choice="principal_reduction" if voluntary_extra else None,
    )


def _generate_due_dates(
    *,
    payment_frequency: PaymentFrequency,
    first_due_date: date,
    installment_count: int,
    semi_monthly_days: tuple[int, int],
) -> tuple[date, ...]:
    if payment_frequency == "daily":
        return tuple(first_due_date + timedelta(days=index) for index in range(installment_count))
    if payment_frequency == "weekly":
        return tuple(first_due_date + timedelta(days=7 * index) for index in range(installment_count))
    if payment_frequency == "monthly":
        return tuple(_add_months_clamped(first_due_date, index) for index in range(installment_count))
    if payment_frequency == "semi_monthly":
        return _semi_monthly_dates(
            first_due_date=first_due_date,
            installment_count=installment_count,
            semi_monthly_days=semi_monthly_days,
        )
    if payment_frequency == "balloon":
        return (first_due_date,)
    raise ContractScheduleError(f"Unsupported payment frequency: {payment_frequency}")


def _semi_monthly_dates(
    *,
    first_due_date: date,
    installment_count: int,
    semi_monthly_days: tuple[int, int],
) -> tuple[date, ...]:
    days = tuple(sorted(set(semi_monthly_days)))
    if len(days) != 2 or any(day < 1 or day > 31 for day in days):
        raise ContractScheduleError(
            "Semi-monthly terms require two distinct contractual day numbers from 1 to 31."
        )

    results: list[date] = []
    year = first_due_date.year
    month = first_due_date.month
    while len(results) < installment_count:
        last_day = calendar.monthrange(year, month)[1]
        for day in days:
            candidate = date(year, month, min(day, last_day))
            if candidate < first_due_date or candidate in results:
                continue
            results.append(candidate)
            if len(results) == installment_count:
                break
        month += 1
        if month == 13:
            month = 1
            year += 1
    return tuple(results)


def _add_months_clamped(anchor: date, months: int) -> date:
    zero_based = anchor.year * 12 + (anchor.month - 1) + months
    year, month_index = divmod(zero_based, 12)
    month = month_index + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(anchor.day, last_day))


def _generate_amounts(
    *,
    contractual_total: Decimal,
    installment_count: int,
    regular_installment_amount: Decimal | None,
) -> tuple[Decimal, ...]:
    if regular_installment_amount is not None:
        regular = _money(regular_installment_amount)
        if regular <= 0:
            raise ContractScheduleError("Regular installment amount must be greater than zero.")
        if installment_count == 1:
            return (contractual_total,)
        final_amount = _money(contractual_total - regular * (installment_count - 1))
        if final_amount <= 0:
            raise ContractScheduleError(
                "Regular installment amount and count exceed the contractual total."
            )
        return tuple([regular] * (installment_count - 1) + [final_amount])

    base = (contractual_total / installment_count).quantize(MONEY, rounding=ROUND_DOWN)
    if base <= 0:
        raise ContractScheduleError(
            "Contractual total is too small for the requested installment count."
        )
    final_amount = _money(contractual_total - base * (installment_count - 1))
    return tuple([base] * (installment_count - 1) + [final_amount])


def _custom_installments(
    *,
    total: Decimal,
    rows: Sequence[tuple[date, Decimal]],
) -> tuple[ContractInstallment, ...]:
    if not rows:
        raise ContractScheduleError("Custom schedules require explicit contractual installments.")

    installments: list[ContractInstallment] = []
    previous_due_date: date | None = None
    running_total = Decimal("0.00")
    for index, (due_date, amount_value) in enumerate(rows, start=1):
        amount = _money(amount_value)
        if amount <= 0:
            raise ContractScheduleError("Every custom contractual installment must be positive.")
        if previous_due_date is not None and due_date <= previous_due_date:
            raise ContractScheduleError(
                "Custom contractual due dates must be strictly increasing."
            )
        installments.append(
            ContractInstallment(
                installment_number=index,
                due_date=due_date,
                contractual_amount=amount,
            )
        )
        previous_due_date = due_date
        running_total = _money(running_total + amount)

    if running_total != total:
        raise ContractScheduleError(
            f"Custom installment total {running_total} does not equal contractual total {total}."
        )
    return tuple(installments)


def _money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)