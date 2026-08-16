from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Sequence
from uuid import UUID

from .contract_schedule_engine import (
    AllocationInstruction,
    ContractInstallment,
    OutstandingInstallment,
    PaymentAllocationError,
    PaymentFrequency,
    plan_payment_allocation,
)


class ContractAutomationError(RuntimeError):
    code = "contract_automation_error"


class ContractScheduleNotReady(ContractAutomationError):
    code = "contract_schedule_not_ready"


class ContractScheduleConflict(ContractAutomationError):
    code = "contract_schedule_conflict"


class ContractPaymentAllocationConflict(ContractAutomationError):
    code = "contract_payment_allocation_conflict"


def store_contract_schedule(
    cursor: Any,
    *,
    loan_id: UUID,
    payment_frequency: PaymentFrequency,
    contract_reference: str,
    contract_signed_date: date | None,
    effective_from: date,
    grace_days: int,
    installments: Sequence[ContractInstallment],
    created_by_user_id: UUID | None = None,
    supersede_active: bool = False,
) -> UUID:
    """Persist one exact signed-contract schedule in the caller's transaction.

    Existing active schedules are never silently replaced. A restructure or
    renewal must explicitly request supersession so the old schedule remains
    preserved as evidence.
    """

    reference = contract_reference.strip()
    if not reference:
        raise ContractScheduleConflict("Contract reference is required.")
    if grace_days < 0:
        raise ContractScheduleConflict("Contractual grace days cannot be negative.")
    if not installments:
        raise ContractScheduleConflict("At least one contractual installment is required.")

    cursor.execute(
        "select id from lending.loans where id = %s for update",
        (loan_id,),
    )
    if cursor.fetchone() is None:
        raise ContractScheduleNotReady("The loan does not exist.")

    cursor.execute(
        """
        select id, schedule_version
        from lending.loan_contract_schedules
        where loan_id = %s and status = 'active'
        for update
        """,
        (loan_id,),
    )
    active = cursor.fetchone()
    supersedes_schedule_id: UUID | None = None
    if active is not None:
        if not supersede_active:
            raise ContractScheduleConflict(
                "This loan already has an active contractual schedule."
            )
        supersedes_schedule_id = active[0]
        schedule_version = int(active[1]) + 1
        cursor.execute(
            """
            update lending.loan_contract_schedules
            set status = 'superseded'
            where id = %s and status = 'active'
            """,
            (supersedes_schedule_id,),
        )
    else:
        schedule_version = 1

    cursor.execute(
        """
        insert into lending.loan_contract_schedules (
            loan_id,
            schedule_version,
            status,
            payment_frequency,
            contract_reference,
            contract_signed_date,
            effective_from,
            grace_days,
            supersedes_schedule_id,
            created_by_user_id
        )
        values (%s, %s, 'active', %s, %s, %s, %s, %s, %s, %s)
        returning id
        """,
        (
            loan_id,
            schedule_version,
            payment_frequency,
            reference,
            contract_signed_date,
            effective_from,
            grace_days,
            supersedes_schedule_id,
            created_by_user_id,
        ),
    )
    schedule_id = cursor.fetchone()[0]

    for installment in installments:
        cursor.execute(
            """
            insert into lending.loan_contract_installments (
                schedule_id,
                installment_number,
                due_date,
                contractual_amount
            )
            values (%s, %s, %s, %s)
            """,
            (
                schedule_id,
                installment.installment_number,
                installment.due_date,
                installment.contractual_amount,
            ),
        )
    return schedule_id


def allocate_collection_transaction(
    cursor: Any,
    *,
    transaction_id: UUID,
    explicit_covered_dates: Sequence[date] = (),
) -> tuple[AllocationInstruction, ...]:
    """Apply one accepted receipt's applied cash to contractual installments.

    ``collection_transactions.amount`` is custody cash. Only ``applied_amount``
    may consume signed-contract installment capacity. This keeps a legitimate
    second receipt auditable even when some or all of its cash remains
    unallocated for later review.

    The collection transaction and its loan are locked before planning, so two
    concurrent receipts for the same loan cannot both consume the same unpaid
    installment. Re-running a fully allocated transaction is idempotent. Partial
    pre-existing installment rows are treated as a conflict rather than guessed
    or silently repaired. Allocations belonging to a voided collection remain
    immutable evidence but no longer consume installment capacity.
    """

    cursor.execute(
        """
        select
            loan_id,
            applied_amount,
            amount,
            unallocated_amount,
            entry_type,
            is_voided
        from lending.collection_transactions
        where id = %s
        for update
        """,
        (transaction_id,),
    )
    transaction = cursor.fetchone()
    if transaction is None:
        raise ContractScheduleNotReady("The collection transaction does not exist.")

    (
        loan_id,
        applied_amount,
        cash_received_amount,
        unallocated_amount,
        entry_type,
        is_voided,
    ) = transaction
    if bool(is_voided):
        raise ContractPaymentAllocationConflict(
            "A voided collection transaction cannot be contract-allocated."
        )
    if str(entry_type) not in {"payment", "advance"}:
        raise ContractPaymentAllocationConflict(
            "Only payment and advance transactions can be allocated to installments."
        )

    applied = Decimal(applied_amount)
    cash_received = Decimal(cash_received_amount)
    unresolved = Decimal(unallocated_amount)
    if applied < Decimal("0.00") or unresolved < Decimal("0.00"):
        raise ContractPaymentAllocationConflict(
            "Receipt application amounts are invalid. Management review is required."
        )
    if applied + unresolved != cash_received:
        raise ContractPaymentAllocationConflict(
            "Receipt cash does not reconcile to applied plus unallocated amounts."
        )

    # Serialize all automatic allocation planning for this loan. This prevents
    # two different collection transactions from reading the same outstanding
    # installment state at the same time.
    cursor.execute(
        "select id from lending.loans where id = %s for update",
        (loan_id,),
    )
    if cursor.fetchone() is None:
        raise ContractScheduleNotReady("The loan for this collection no longer exists.")

    cursor.execute(
        """
        select
            allocation.installment_id,
            installment.installment_number,
            installment.effective_due_date,
            allocation.amount_applied,
            allocation.allocation_basis
        from lending.loan_installment_payment_allocations allocation
        join lending.loan_contract_installments_operational installment
          on installment.id = allocation.installment_id
        where allocation.transaction_id = %s
        order by installment.effective_due_date, installment.installment_number
        """,
        (transaction_id,),
    )
    existing_rows = cursor.fetchall()
    if existing_rows:
        existing_total = sum((Decimal(row[3]) for row in existing_rows), Decimal("0.00"))
        if existing_total != applied:
            raise ContractPaymentAllocationConflict(
                "This transaction has incomplete pre-existing installment allocations."
            )
        return tuple(
            AllocationInstruction(
                installment_id=row[0],
                installment_number=int(row[1]),
                due_date=row[2],
                amount_applied=Decimal(row[3]),
                allocation_basis=str(row[4]),  # type: ignore[arg-type]
            )
            for row in existing_rows
        )

    if applied == Decimal("0.00"):
        return ()

    cursor.execute(
        """
        select id
        from lending.loan_contract_schedules
        where loan_id = %s and status = 'active'
        """,
        (loan_id,),
    )
    schedule = cursor.fetchone()
    if schedule is None:
        raise ContractScheduleNotReady(
            "The loan has no active signed-contract schedule for automatic allocation."
        )
    schedule_id = schedule[0]

    cursor.execute(
        """
        select
            installment.id,
            installment.installment_number,
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
            installment.effective_due_date,
            installment.contractual_amount
        order by installment.effective_due_date, installment.installment_number
        """,
        (schedule_id,),
    )
    outstanding = tuple(
        OutstandingInstallment(
            installment_id=row[0],
            installment_number=int(row[1]),
            due_date=row[2],
            contractual_amount=Decimal(row[3]),
            allocated_amount=Decimal(row[4]),
        )
        for row in cursor.fetchall()
    )

    try:
        plan = plan_payment_allocation(
            transaction_amount=applied,
            installments=outstanding,
            explicit_covered_dates=explicit_covered_dates,
        )
    except PaymentAllocationError as exc:
        raise ContractPaymentAllocationConflict(str(exc)) from exc

    for instruction in plan:
        cursor.execute(
            """
            insert into lending.loan_installment_payment_allocations (
                installment_id,
                transaction_id,
                amount_applied,
                allocation_basis,
                allocation_reference
            )
            values (%s, %s, %s, %s, %s)
            """,
            (
                instruction.installment_id,
                transaction_id,
                instruction.amount_applied,
                instruction.allocation_basis,
                f"auto-contract-allocation:{transaction_id}",
            ),
        )
    return plan