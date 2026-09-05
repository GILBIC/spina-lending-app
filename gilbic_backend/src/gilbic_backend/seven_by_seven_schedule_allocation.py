from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID


MONEY = Decimal("0.01")
ZERO = Decimal("0.00")
FUTURE_ADVANCE_BASIS = "future_advance_oldest_first"
DUE_BASIS = "oldest_due_first"
BORROWER_CATCH_UP_BASIS = "borrower_catch_up_oldest_first"


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
    allocation_basis: str = DUE_BASIS


def money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def plan_verified_seven_by_seven_scheduled_payment(
    cursor: Any,
    *,
    loan_id: UUID,
    collection_date: date,
    transaction_amount: Decimal | int | str,
    active_borrower_extension_slots: int = 0,
) -> tuple[SevenBySevenInstallmentAllocationInstruction, ...]:
    """Plan one normal 7x7 receipt against due rows plus approved catch-up capacity.

    Signed installment evidence stays immutable. Current collection capacity uses
    the operational amount overlay created by audited schedule adjustments. For
    prepayment, immutable gross Advance allocations remain audit evidence while
    only the active amount (gross Advance less Refund Due classifications) counts
    as current installment satisfaction.

    Normal cash first clears unpaid rows whose effective due date is on or before
    the collection date, oldest first. When borrower-caused extension slots are
    active, normal non-ADV cash may then fill the same number of oldest unpaid
    future operational rows as catch-up. Any amount beyond due + catch-up capacity
    remains true extra and requires explicit Advance or Extra Principal intent.
    """

    amount = money(transaction_amount)
    if amount <= ZERO:
        raise SevenBySevenScheduleAllocationConflict(
            "A scheduled 7x7 payment must be greater than zero."
        )
    if active_borrower_extension_slots < 0:
        raise SevenBySevenScheduleAllocationConflict(
            "Active borrower extension slots cannot be negative."
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

    unpaid_rows: list[tuple[int, int, date, Decimal, Decimal]] = []
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
                    "A removed 7x7 operational row still has a collectible amount. Management review is required."
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
        if remaining > ZERO:
            unpaid_rows.append(
                (
                    installment_id,
                    installment_number,
                    effective_due_date,
                    operational_amount,
                    remaining,
                )
            )

    due_rows = [row for row in unpaid_rows if row[2] <= collection_date]
    future_rows = [row for row in unpaid_rows if row[2] > collection_date]
    catchup_rows = future_rows[:active_borrower_extension_slots]

    due_capacity = money(sum((row[4] for row in due_rows), ZERO))
    catchup_capacity = money(sum((row[4] for row in catchup_rows), ZERO))
    normal_capacity = money(due_capacity + catchup_capacity)
    if due_capacity <= ZERO and catchup_capacity <= ZERO:
        raise SevenBySevenExtraAllocationChoiceRequired(
            "No unpaid 7x7 scheduled amount is due through this date. Use Details for an Advance or Extra Principal instruction."
        )
    if amount > normal_capacity:
        extra = money(amount - normal_capacity)
        boundary = (
            "Past Due, Due Today, and borrower catch-up"
            if catchup_capacity > ZERO
            else "Past Due and Due Today"
        )
        raise SevenBySevenExtraAllocationChoiceRequired(
            f"This payment includes {extra} beyond {boundary}. The borrower must choose Advance or Extra Principal."
        )

    amount_left = amount
    instructions: list[SevenBySevenInstallmentAllocationInstruction] = []
    for basis, planned_rows in (
        (DUE_BASIS, due_rows),
        (BORROWER_CATCH_UP_BASIS, catchup_rows),
    ):
        for installment_id, installment_number, effective_due_date, _operational, remaining in planned_rows:
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
                    allocation_basis=basis,
                )
            )
            amount_left = money(amount_left - applied)
        if amount_left <= ZERO:
            break

    if amount_left != ZERO:
        raise SevenBySevenScheduleAllocationConflict(
            "The 7x7 scheduled payment could not be fully allocated to due/catch-up rows."
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
            ) values (%s, %s, %s, %s, %s, %s)
            """,
            (
                instruction.installment_id,
                transaction_id,
                instruction.amount_applied,
                instruction.allocation_basis,
                f"seven-by-seven-scheduled:{transaction_id}",
                actor_user_id,
            ),
        )
