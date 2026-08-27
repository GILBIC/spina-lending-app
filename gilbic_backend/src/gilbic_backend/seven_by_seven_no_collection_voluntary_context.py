from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from .seven_by_seven_no_collection_voluntary import (
    NoCollectionAffectedInstallment,
    NoCollectionPastDueObligation,
    NoCollectionVoluntaryPlan,
    SevenBySevenNoCollectionVoluntaryError,
    plan_seven_by_seven_no_collection_voluntary_payment,
)
from .seven_by_seven_schedule_allocation import money


class SevenBySevenNoCollectionVoluntaryContextError(ValueError):
    """Raised when the immutable NC posting context cannot be proven exactly."""

    code = "seven_by_seven_no_collection_voluntary_context_conflict"


@dataclass(frozen=True, slots=True)
class NoCollectionVoluntaryPostingContext:
    schedule_id: UUID
    source_no_collection_adjustment_id: UUID
    operational_version: int
    affected_installment: NoCollectionAffectedInstallment
    past_due_obligations: tuple[NoCollectionPastDueObligation, ...]
    plan: NoCollectionVoluntaryPlan


def load_no_collection_voluntary_posting_context(
    cursor: Any,
    *,
    loan_id: UUID,
    collection_date: date,
    transaction_amount: Decimal | int | str,
) -> NoCollectionVoluntaryPostingContext:
    """Lock and prove the source-of-truth context for one NC voluntary receipt.

    This function is deliberately read/lock-only. It proves the exact active
    verified daily schedule, exactly one active Management No Collection source
    for the receipt date, exactly one affected signed installment, all older
    Past Due capacity, and all existing non-voided allocation evidence before
    calling the pure voluntary-payment planner.

    The caller must still perform receipt, schedule-restoration, completion
    evidence, and financial replay writes atomically in the same transaction.
    """

    cursor.execute(
        """
        select
            schedule.id as schedule_id,
            schedule.payment_frequency
        from lending.loan_contract_schedules schedule
        join lending.loan_contract_schedule_registrations registration
          on registration.schedule_id = schedule.id
        where schedule.loan_id = %s
          and schedule.status = 'active'
        order by registration.verified_at desc
        limit 1
        for update of schedule
        """,
        (loan_id,),
    )
    schedule = cursor.fetchone()
    if schedule is None:
        raise SevenBySevenNoCollectionVoluntaryContextError(
            "This 7x7 loan does not have an active verified signed schedule."
        )
    if str(schedule["payment_frequency"]) != "daily":
        raise SevenBySevenNoCollectionVoluntaryContextError(
            "No Collection voluntary posting requires the verified daily 7x7 schedule."
        )

    schedule_id = schedule["schedule_id"]
    cursor.execute(
        """
        select operational_version
        from lending.loan_schedule_operational_state
        where schedule_id = %s
        for update
        """,
        (schedule_id,),
    )
    operational_state = cursor.fetchone()
    if operational_state is None:
        raise SevenBySevenNoCollectionVoluntaryContextError(
            "The verified 7x7 schedule has no operational No Collection state."
        )
    operational_version = int(operational_state["operational_version"])

    cursor.execute(
        """
        select adjustment.id
        from lending.loan_schedule_adjustments adjustment
        where adjustment.loan_id = %s
          and adjustment.schedule_id = %s
          and adjustment.adjustment_type = 'no_collection'
          and adjustment.no_collection_date = %s
          and not exists (
                select 1
                from lending.loan_schedule_adjustments reversal
                where reversal.adjustment_type = 'reversal'
                  and reversal.reverses_adjustment_id = adjustment.id
          )
          and not exists (
                select 1
                from lending.loan_no_collection_voluntary_completions completion
                where completion.no_collection_adjustment_id = adjustment.id
          )
        order by adjustment.resulting_operational_version
        for update of adjustment
        """,
        (loan_id, schedule_id, collection_date),
    )
    source_rows = cursor.fetchall()
    if len(source_rows) != 1:
        raise SevenBySevenNoCollectionVoluntaryContextError(
            "The active Management No Collection declaration for this loan/date is missing or ambiguous. Refresh and ask Management to reconcile it."
        )
    source_adjustment_id = source_rows[0]["id"]

    cursor.execute(
        """
        select
            item.installment_id,
            item.installment_number,
            item.contractual_amount,
            item.prior_effective_due_date,
            installment.effective_due_date,
            coalesce(sum(allocation.amount_applied) filter (
                where allocation_transaction.is_voided = false
            ), 0)::numeric(18,2) as allocated_amount
        from lending.loan_schedule_adjustment_items item
        join lending.loan_contract_installments_operational installment
          on installment.id = item.installment_id
        left join lending.loan_installment_payment_allocations allocation
          on allocation.installment_id = item.installment_id
        left join lending.collection_transactions allocation_transaction
          on allocation_transaction.id = allocation.transaction_id
        where item.adjustment_id = %s
          and item.prior_effective_due_date = %s
        group by
            item.installment_id,
            item.installment_number,
            item.contractual_amount,
            item.prior_effective_due_date,
            installment.effective_due_date
        """,
        (source_adjustment_id, collection_date),
    )
    affected_rows = cursor.fetchall()
    if len(affected_rows) != 1:
        raise SevenBySevenNoCollectionVoluntaryContextError(
            "The Management No Collection declaration does not identify exactly one affected signed installment."
        )
    affected_row = affected_rows[0]
    if affected_row["effective_due_date"] <= collection_date:
        raise SevenBySevenNoCollectionVoluntaryContextError(
            "The affected No Collection installment is not currently shifted to a future operational date."
        )

    affected_contractual = money(affected_row["contractual_amount"])
    affected_allocated = money(affected_row["allocated_amount"])
    if affected_allocated < Decimal("0.00") or affected_allocated > affected_contractual:
        raise SevenBySevenNoCollectionVoluntaryContextError(
            "The affected No Collection installment has inconsistent payment evidence."
        )
    affected_installment = NoCollectionAffectedInstallment(
        installment_id=int(affected_row["installment_id"]),
        installment_number=int(affected_row["installment_number"]),
        contractual_amount=affected_contractual,
        prepaid_amount=affected_allocated,
    )

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
          and installment.effective_due_date < %s
        group by
            installment.id,
            installment.installment_number,
            installment.effective_due_date,
            installment.contractual_amount
        order by installment.effective_due_date, installment.installment_number
        """,
        (schedule_id, collection_date),
    )
    past_due: list[NoCollectionPastDueObligation] = []
    for row in cursor.fetchall():
        contractual = money(row["contractual_amount"])
        allocated = money(row["allocated_amount"])
        if allocated < Decimal("0.00") or allocated > contractual:
            raise SevenBySevenNoCollectionVoluntaryContextError(
                "A verified 7x7 Past Due installment has inconsistent payment evidence."
            )
        remaining = money(contractual - allocated)
        if remaining <= Decimal("0.00"):
            continue
        past_due.append(
            NoCollectionPastDueObligation(
                installment_id=int(row["id"]),
                installment_number=int(row["installment_number"]),
                effective_due_date=row["effective_due_date"],
                remaining_amount=remaining,
            )
        )

    try:
        plan = plan_seven_by_seven_no_collection_voluntary_payment(
            transaction_amount=transaction_amount,
            collection_date=collection_date,
            no_collection_date=collection_date,
            past_due_obligations=tuple(past_due),
            affected_installment=affected_installment,
        )
    except SevenBySevenNoCollectionVoluntaryError:
        raise

    return NoCollectionVoluntaryPostingContext(
        schedule_id=schedule_id,
        source_no_collection_adjustment_id=source_adjustment_id,
        operational_version=operational_version,
        affected_installment=affected_installment,
        past_due_obligations=tuple(past_due),
        plan=plan,
    )
