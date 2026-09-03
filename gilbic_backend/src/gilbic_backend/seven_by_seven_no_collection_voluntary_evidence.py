from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from .no_collection_schedule import OperationalInstallment, ScheduleShift
from .seven_by_seven_no_collection_completion import (
    SevenBySevenNoCollectionCompletionScheduleError,
    plan_seven_by_seven_no_collection_completion_restoration,
)
from .seven_by_seven_no_collection_voluntary import NoCollectionVoluntaryPlan
from .seven_by_seven_schedule_allocation import money


DEFERRED_BASIS = "future_advance_oldest_first"
IMMEDIATE_BASIS = "oldest_due_first"


class SevenBySevenNoCollectionVoluntaryEvidenceError(ValueError):
    """Raised when immutable NC voluntary evidence cannot be stored exactly."""

    code = "seven_by_seven_no_collection_voluntary_evidence_conflict"


def plan_no_collection_completion_restoration_from_database(
    cursor: Any,
    *,
    schedule_id: UUID,
    source_no_collection_date: date,
) -> tuple[ScheduleShift, ...]:
    """Load immutable schedule history and prove the one-shift restoration plan."""

    cursor.execute(
        """
        select
            installment.id,
            installment.installment_number,
            installment.contractual_due_date,
            installment.effective_due_date,
            installment.contractual_amount,
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
            installment.contractual_due_date,
            installment.effective_due_date,
            installment.contractual_amount
        order by installment.installment_number, installment.id
        """,
        (schedule_id,),
    )
    installments = tuple(
        OperationalInstallment(
            installment_id=int(row["id"]),
            installment_number=int(row["installment_number"]),
            contractual_due_date=row["contractual_due_date"],
            effective_due_date=row["effective_due_date"],
            contractual_amount=money(row["contractual_amount"]),
            allocated_amount=money(row["allocated_amount"]),
        )
        for row in cursor.fetchall()
    )

    cursor.execute(
        """
        select adjustment.no_collection_date
        from lending.loan_schedule_adjustments adjustment
        where adjustment.schedule_id = %s
          and adjustment.adjustment_type = 'no_collection'
          and not exists (
                select 1
                from lending.loan_schedule_adjustments reversal
                where reversal.adjustment_type = 'reversal'
                  and reversal.reverses_adjustment_id = adjustment.id
          )
          and not exists (
                select 1
                from lending.loan_no_collection_voluntary_completions completion
                join lending.collection_transactions completion_transaction
                  on completion_transaction.id = completion.transaction_id
                where completion.no_collection_adjustment_id = adjustment.id
                  and completion_transaction.is_voided = false
          )
        order by adjustment.resulting_operational_version, adjustment.id
        """,
        (schedule_id,),
    )
    active_dates = tuple(row["no_collection_date"] for row in cursor.fetchall())

    try:
        return plan_seven_by_seven_no_collection_completion_restoration(
            installments=installments,
            active_no_collection_dates=active_dates,
            source_no_collection_date=source_no_collection_date,
        )
    except SevenBySevenNoCollectionCompletionScheduleError as error:
        raise SevenBySevenNoCollectionVoluntaryEvidenceError(str(error)) from error


def store_no_collection_voluntary_allocations(
    cursor: Any,
    *,
    transaction_id: UUID,
    actor_user_id: UUID,
    source_no_collection_adjustment_id: UUID,
    plan: NoCollectionVoluntaryPlan,
) -> None:
    """Persist one complete schedule-allocation explanation for the cash receipt."""

    allocated = Decimal("0.00")
    for instruction in plan.instructions:
        basis = IMMEDIATE_BASIS
        if (
            instruction.target == "affected_no_collection_installment"
            and plan.status == "partial_shifted_prepayment"
        ):
            basis = DEFERRED_BASIS
        reference = (
            "seven_by_seven_no_collection_voluntary:"
            f"{source_no_collection_adjustment_id}:{plan.status}:{instruction.target}"
        )
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
                basis,
                reference,
                actor_user_id,
            ),
        )
        allocated = money(allocated + instruction.amount_applied)

    if allocated != money(plan.receipt_amount):
        raise SevenBySevenNoCollectionVoluntaryEvidenceError(
            "No Collection schedule allocation evidence does not reconcile to the full receipt amount."
        )


def store_no_collection_voluntary_completion(
    cursor: Any,
    *,
    loan_id: UUID,
    schedule_id: UUID,
    actor_user_id: UUID,
    source_no_collection_adjustment_id: UUID,
    no_collection_date: date,
    expected_operational_version: int,
    transaction_id: UUID,
    affected_installment_id: int,
    current_receipt_completion_amount: Decimal,
    prior_payment_evidence_amount: Decimal,
    restoration_shifts: tuple[ScheduleShift, ...],
) -> UUID:
    """Store immutable completion adjustment, restored dates, and link evidence."""

    if not restoration_shifts:
        raise SevenBySevenNoCollectionVoluntaryEvidenceError(
            "Full No Collection completion requires an exact operational restoration plan."
        )

    completion_adjustment_id = uuid4()
    resulting_operational_version = expected_operational_version + 1
    cursor.execute(
        """
        insert into lending.loan_schedule_adjustments (
            id,
            loan_id,
            schedule_id,
            adjustment_type,
            no_collection_date,
            reason,
            expected_operational_version,
            resulting_operational_version,
            actor_user_id
        ) values (%s, %s, %s, 'voluntary_completion', %s, %s, %s, %s, %s)
        """,
        (
            completion_adjustment_id,
            loan_id,
            schedule_id,
            no_collection_date,
            "Borrower fully completed the affected installment voluntarily on the declared No Collection date.",
            expected_operational_version,
            resulting_operational_version,
            actor_user_id,
        ),
    )

    for shift in restoration_shifts:
        cursor.execute(
            """
            insert into lending.loan_schedule_adjustment_items (
                adjustment_id,
                installment_id,
                installment_number,
                contractual_due_date,
                prior_effective_due_date,
                new_effective_due_date,
                contractual_amount
            ) values (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                completion_adjustment_id,
                shift.installment_id,
                shift.installment_number,
                shift.contractual_due_date,
                shift.prior_effective_due_date,
                shift.new_effective_due_date,
                shift.contractual_amount,
            ),
        )
        cursor.execute(
            """
            insert into lending.loan_installment_operational_dates (
                installment_id,
                effective_due_date,
                last_adjustment_id,
                updated_by_user_id
            ) values (%s, %s, %s, %s)
            on conflict (installment_id) do update
            set effective_due_date = excluded.effective_due_date,
                last_adjustment_id = excluded.last_adjustment_id,
                updated_by_user_id = excluded.updated_by_user_id,
                updated_at = now()
            """,
            (
                shift.installment_id,
                shift.new_effective_due_date,
                completion_adjustment_id,
                actor_user_id,
            ),
        )

    cursor.execute(
        """
        update lending.loan_schedule_operational_state
        set operational_version = %s,
            updated_by_user_id = %s,
            updated_at = now()
        where schedule_id = %s
          and operational_version = %s
        """,
        (
            resulting_operational_version,
            actor_user_id,
            schedule_id,
            expected_operational_version,
        ),
    )
    if cursor.rowcount != 1:
        raise SevenBySevenNoCollectionVoluntaryEvidenceError(
            "The operational schedule changed while voluntary completion was being stored."
        )

    cursor.execute(
        """
        insert into lending.loan_no_collection_voluntary_completions (
            adjustment_id,
            no_collection_adjustment_id,
            transaction_id,
            affected_installment_id,
            current_receipt_completion_amount,
            prior_advance_activation_amount
        ) values (%s, %s, %s, %s, %s, %s)
        """,
        (
            completion_adjustment_id,
            source_no_collection_adjustment_id,
            transaction_id,
            affected_installment_id,
            current_receipt_completion_amount,
            prior_payment_evidence_amount,
        ),
    )
    return completion_adjustment_id