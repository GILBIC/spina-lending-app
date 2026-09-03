from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from .seven_by_seven_schedule_allocation import (
    FUTURE_ADVANCE_BASIS,
    ZERO,
    SevenBySevenInstallmentAllocationInstruction,
    SevenBySevenScheduleAllocationConflict,
    SevenBySevenVerifiedScheduleNotFound,
    money,
)


class SevenBySevenAdvanceRequiresCurrentSchedule(SevenBySevenScheduleAllocationConflict):
    """Raised when Past Due or Due Today is still unpaid."""

    code = "seven_by_seven_advance_requires_current_schedule"


class SevenBySevenAdvanceCapacityExceeded(SevenBySevenScheduleAllocationConflict):
    """Raised when requested Advance is beyond remaining future operational rows."""

    code = "seven_by_seven_advance_capacity_exceeded"


def plan_verified_seven_by_seven_advance(
    cursor: Any,
    *,
    loan_id: UUID,
    collection_date: date,
    transaction_amount: Decimal | int | str,
) -> tuple[SevenBySevenInstallmentAllocationInstruction, ...]:
    """Plan 7x7 Advance against current future operational row capacity only.

    Signed schedule rows and historical Advance allocations remain immutable.
    Current capacity uses the operational amount after audited Extra Principal
    shortening and counts only active Advance (gross verified Advance less any
    amount already classified as Refund Due). Removed tail rows have zero current
    capacity and can never receive a new Advance.
    """

    amount = money(transaction_amount)
    if amount <= ZERO:
        raise SevenBySevenAdvanceCapacityExceeded(
            "A 7x7 Advance amount must be greater than zero."
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
            installment.operational_amount,
            installment.operational_principal_component,
            installment.operational_interest_component,
            (
                coalesce(sum(allocation.amount_applied) filter (
                    where allocation_transaction.is_voided = false
                      and allocation.allocation_basis <> %s
                ), 0)
                + coalesce(active_advance.active_advance_allocated, 0)
            )::numeric(18,2) as allocated_amount,
            installment.removed_from_operational_schedule
        from lending.loan_contract_installments_operational installment
        left join lending.loan_installment_payment_allocations allocation
          on allocation.installment_id = installment.id
        left join lending.collection_transactions allocation_transaction
          on allocation_transaction.id = allocation.transaction_id
        left join lending.loan_installment_active_advance active_advance
          on active_advance.installment_id = installment.id
        where installment.schedule_id = %s
        group by
            installment.id,
            installment.installment_number,
            installment.effective_due_date,
            installment.operational_amount,
            installment.operational_principal_component,
            installment.operational_interest_component,
            installment.removed_from_operational_schedule,
            active_advance.active_advance_allocated
        order by installment.effective_due_date, installment.installment_number
        """,
        (FUTURE_ADVANCE_BASIS, schedule_id),
    )
    rows = cursor.fetchall()
    if not rows:
        raise SevenBySevenScheduleAllocationConflict(
            "The active verified 7x7 schedule has no installment rows."
        )

    outstanding_due = ZERO
    future_rows: list[tuple[int, int, date, Decimal]] = []
    for row in rows:
        if isinstance(row, dict):
            installment_id = int(row["id"])
            installment_number = int(row["installment_number"])
            effective_due_date = row["effective_due_date"]
            operational_amount = money(row["operational_amount"])
            principal_component = row["operational_principal_component"]
            interest_component = row["operational_interest_component"]
            allocated_amount = money(row["allocated_amount"])
            removed = bool(row["removed_from_operational_schedule"])
        else:
            installment_id = int(row[0])
            installment_number = int(row[1])
            effective_due_date = row[2]
            operational_amount = money(row[3])
            principal_component = row[4]
            interest_component = row[5]
            allocated_amount = money(row[6])
            removed = bool(row[7])

        if removed:
            if operational_amount != ZERO:
                raise SevenBySevenScheduleAllocationConflict(
                    "A removed 7x7 operational row still has Advance capacity. Management review is required."
                )
            continue
        if principal_component is None or interest_component is None:
            raise SevenBySevenScheduleAllocationConflict(
                "The active 7x7 schedule is missing operational principal/interest evidence."
            )
        if money(principal_component) + money(interest_component) != operational_amount:
            raise SevenBySevenScheduleAllocationConflict(
                "A 7x7 operational row does not reconcile its principal and interest components."
            )
        if allocated_amount > operational_amount:
            raise SevenBySevenScheduleAllocationConflict(
                "A 7x7 operational row is over-allocated after Advance/Refund Due reconciliation. Management review is required."
            )

        remaining = money(operational_amount - allocated_amount)
        if remaining <= ZERO:
            continue
        if effective_due_date <= collection_date:
            outstanding_due = money(outstanding_due + remaining)
        else:
            future_rows.append(
                (
                    installment_id,
                    installment_number,
                    effective_due_date,
                    remaining,
                )
            )

    if outstanding_due > ZERO:
        raise SevenBySevenAdvanceRequiresCurrentSchedule(
            f"Clear {outstanding_due} of Past Due and Due Today before recording 7x7 Advance."
        )

    future_capacity = money(sum((row[3] for row in future_rows), ZERO))
    if future_capacity <= ZERO:
        raise SevenBySevenAdvanceCapacityExceeded(
            "This 7x7 schedule has no unpaid future operational capacity available for Advance."
        )
    if amount > future_capacity:
        excess = money(amount - future_capacity)
        raise SevenBySevenAdvanceCapacityExceeded(
            f"This Advance exceeds remaining future 7x7 capacity by {excess}."
        )

    amount_left = amount
    instructions: list[SevenBySevenInstallmentAllocationInstruction] = []
    for installment_id, installment_number, effective_due_date, remaining in future_rows:
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
            "The 7x7 Advance could not be fully allocated to future operational rows."
        )
    return tuple(instructions)


def store_verified_seven_by_seven_advance_allocations(
    cursor: Any,
    *,
    transaction_id: UUID,
    actor_user_id: UUID,
    instructions: tuple[SevenBySevenInstallmentAllocationInstruction, ...],
) -> None:
    """Persist chronological future-row Advance evidence."""

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
            ) values (%s, %s, %s, 'future_advance_oldest_first', %s, %s)
            """,
            (
                instruction.installment_id,
                transaction_id,
                instruction.amount_applied,
                f"seven-by-seven-advance:{transaction_id}",
                actor_user_id,
            ),
        )
