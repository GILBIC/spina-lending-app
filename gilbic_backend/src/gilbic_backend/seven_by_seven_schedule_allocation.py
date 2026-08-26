from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID


MONEY = Decimal("0.01")
ZERO = Decimal("0.00")


class SevenBySevenScheduleAllocationError(ValueError):
    code = "seven_by_seven_schedule_allocation_error"


class SevenBySevenVerifiedScheduleNotFound(SevenBySevenScheduleAllocationError):
    """Raised when the loan has no active verified signed schedule yet."""

    code = "seven_by_seven_verified_schedule_required"


class SevenBySevenScheduleAllocationConflict(SevenBySevenScheduleAllocationError):
    code = "seven_by_seven_schedule_allocation_conflict"


class SevenBySevenExtraAllocationChoiceRequired(SevenBySevenScheduleAllocationError):
    code = "seven_by_seven_extra_allocation_choice_required"


@dataclass(frozen=True, slots=True)
class SevenBySevenInstallmentAllocationInstruction:
    installment_id: int
    installment_number: int
    effective_due_date: date
    amount_applied: Decimal


def money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def plan_verified_seven_by_seven_scheduled_payment(
    cursor: Any,
    *,
    loan_id: UUID,
    collection_date: date,
    transaction_amount: Decimal | int | str,
) -> tuple[SevenBySevenInstallmentAllocationInstruction, ...]:
    """Plan one normal 7x7 receipt against verified due schedule rows only.

    This is contractual schedule-completion evidence, not the interest/principal
    accounting allocator. The protected operational allocator remains the source
    for interest-first cash composition. Here, normal cash may clear only unpaid
    rows whose *effective* due date is on or before the collection date, oldest
    first. It never spills into future rows and therefore never silently creates
    an Advance.

    Multiple same-day receipts naturally accumulate because existing allocation
    evidence is included before planning the next receipt.
    """

    amount = money(transaction_amount)
    if amount <= ZERO:
        raise SevenBySevenScheduleAllocationConflict(
            "A scheduled 7x7 payment must be greater than zero."
        )

    cursor.execute(
        """
        select
            schedule.id,
            schedule.payment_frequency
        from lending.loan_contract_schedules schedule
        join lending.loan_contract_schedule_registrations registration
          on registration.schedule_id = schedule.id
        where schedule.loan_id = %s
          and schedule.status = 'active'
        order by registration.verified_at desc
        limit 1
        """,
        (loan_id,),
    )
    schedule = cursor.fetchone()
    if schedule is None:
        raise SevenBySevenVerifiedScheduleNotFound(
            "This 7x7 loan does not yet have an active verified signed schedule."
        )

    schedule_id = schedule[0] if not isinstance(schedule, dict) else schedule["id"]
    payment_frequency = (
        schedule[1] if not isinstance(schedule, dict) else schedule["payment_frequency"]
    )
    if str(payment_frequency) != "daily":
        raise SevenBySevenScheduleAllocationConflict(
            "The active verified 7x7 schedule is not daily. Management review is required."
        )

    cursor.execute(
        """
        select
            installment.id,
            installment.installment_number,
            installment.effective_due_date,
            installment.contractual_amount,
            installment.principal_component,
            installment.interest_component,
            coalesce(sum(allocation.amount_applied) filter (
                where allocation_transaction.is_voided = false
            ), 0)::numeric(18,2) as allocated_amount
        from lending.loan_contract_installments_operational installment
        left join lending.loan_installment_payment_allocations allocation
          on allocation.installment_id = installment.id
        left join lending.collection_transactions allocation_transaction
          on allocation_transaction.id = allocation.transaction_id
        where installment.schedule_id = %s
        group by
            installment.id,
            installment.installment_number,
            installment.effective_due_date,
            installment.contractual_amount,
            installment.principal_component,
            installment.interest_component
        order by installment.effective_due_date, installment.installment_number
        """,
        (schedule_id,),
    )
    rows = cursor.fetchall()
    if not rows:
        raise SevenBySevenScheduleAllocationConflict(
            "The active verified 7x7 schedule has no installment rows."
        )

    due_rows: list[tuple[int, int, date, Decimal, Decimal]] = []
    for row in rows:
        if isinstance(row, dict):
            installment_id = int(row["id"])
            installment_number = int(row["installment_number"])
            effective_due_date = row["effective_due_date"]
            contractual_amount = money(row["contractual_amount"])
            principal_component = row["principal_component"]
            interest_component = row["interest_component"]
            allocated_amount = money(row["allocated_amount"])
        else:
            installment_id = int(row[0])
            installment_number = int(row[1])
            effective_due_date = row[2]
            contractual_amount = money(row[3])
            principal_component = row[4]
            interest_component = row[5]
            allocated_amount = money(row[6])

        if principal_component is None or interest_component is None:
            raise SevenBySevenScheduleAllocationConflict(
                "The active 7x7 schedule is missing principal/interest row evidence."
            )
        if money(principal_component) + money(interest_component) != contractual_amount:
            raise SevenBySevenScheduleAllocationConflict(
                "A verified 7x7 schedule row does not reconcile its principal and interest components."
            )
        if allocated_amount > contractual_amount:
            raise SevenBySevenScheduleAllocationConflict(
                "A verified 7x7 schedule row is over-allocated. Management review is required."
            )
        remaining = money(contractual_amount - allocated_amount)
        if effective_due_date <= collection_date and remaining > ZERO:
            due_rows.append(
                (
                    installment_id,
                    installment_number,
                    effective_due_date,
                    contractual_amount,
                    remaining,
                )
            )

    due_capacity = money(sum((row[4] for row in due_rows), ZERO))
    if due_capacity <= ZERO:
        raise SevenBySevenExtraAllocationChoiceRequired(
            "No unpaid 7x7 scheduled amount is due through this date. Use Details for an Advance or Extra Principal instruction."
        )
    if amount > due_capacity:
        extra = money(amount - due_capacity)
        raise SevenBySevenExtraAllocationChoiceRequired(
            f"This payment includes {extra} beyond Past Due and Due Today. The borrower must choose Advance or Extra Principal."
        )

    amount_left = amount
    instructions: list[SevenBySevenInstallmentAllocationInstruction] = []
    for installment_id, installment_number, effective_due_date, _contractual, remaining in due_rows:
        if amount_left <= ZERO:
            break
        applied = money(min(amount_left, remaining))
        if applied <= ZERO:
            continue
        instructions.append(
            SevenBySevenInstallmentAllocationInstruction(
                installment_id=installment_id,
                installment_number=installment_number,
                effective_due_date=effective_due_date,
                amount_applied=applied,
            )
        )
        amount_left = money(amount_left - applied)

    if amount_left != ZERO:
        raise SevenBySevenScheduleAllocationConflict(
            "The 7x7 scheduled payment could not be fully allocated to due rows."
        )
    return tuple(instructions)


def store_verified_seven_by_seven_scheduled_payment_allocations(
    cursor: Any,
    *,
    transaction_id: UUID,
    actor_user_id: UUID,
    instructions: tuple[SevenBySevenInstallmentAllocationInstruction, ...],
) -> None:
    """Persist the already-planned contractual row applications."""

    for instruction in instructions:
        cursor.execute(
            """
            insert into lending.loan_installment_payment_allocations (
                installment_id,
                transaction_id,
                amount_applied,
                allocation_basis,
                allocation_reference,
                created_by_user_id
            ) values (%s, %s, %s, 'oldest_due_first', %s, %s)
            """,
            (
                instruction.installment_id,
                transaction_id,
                instruction.amount_applied,
                f"seven-by-seven-scheduled:{transaction_id}",
                actor_user_id,
            ),
        )
