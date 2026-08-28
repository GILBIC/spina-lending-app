from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, NoReturn
from uuid import UUID

from .seven_by_seven_operational_allocator import ZERO, money


class ExtraPrincipalReconciliationError(RuntimeError):
    code = "seven_by_seven_extra_principal_reconciliation_failed"


@dataclass(frozen=True, slots=True)
class ExtraPrincipalReconciliation:
    cash_received: Decimal
    receipt_total: Decimal
    interest_contribution: Decimal
    principal_contribution: Decimal
    adjustment_principal: Decimal
    future_principal: Decimal
    removed_future_interest: Decimal
    retained_advance: Decimal
    refund_due: Decimal
    operational_version: int
    accounting_status: str
    audit_present: bool
    operational_state_digest: str


def reconcile_persisted_extra_principal(
    cursor: Any,
    *,
    transaction_id: UUID,
    adjustment_id: UUID,
) -> ExtraPrincipalReconciliation:
    """Reload and cross-check every persisted forward bridge coordinate."""

    cursor.execute(
        """
        select
            transaction.id as transaction_id,
            transaction.loan_id as receipt_loan_id,
            transaction.amount as cash_received,
            transaction.applied_amount,
            transaction.unallocated_amount,
            transaction.allocation_state,
            transaction.entry_type,
            transaction.is_voided,
            transaction.previous_balance,
            transaction.official_balance,
            transaction.details ->> 'payment_allocation_intent'
                as receipt_intent,
            coalesce(
                nullif(transaction.details ->> 'interest_contribution', ''),
                transaction.details ->> 'seven_by_seven_interest_paid'
            ) as receipt_interest_contribution,
            coalesce(
                nullif(transaction.details ->> 'principal_extra_amount', ''),
                transaction.details ->> 'seven_by_seven_principal_paid'
            ) as receipt_principal_contribution,
            transaction.details ->> 'operational_state_digest'
                as receipt_operational_state_digest,
            adjustment.id as adjustment_id,
            adjustment.loan_id as adjustment_loan_id,
            adjustment.principal_reduction,
            adjustment.prior_future_principal,
            adjustment.resulting_future_principal,
            adjustment.removed_future_interest,
            adjustment.advance_refund_due as adjustment_refund_due,
            adjustment.resulting_operational_version,
            state.remaining_balance as state_balance,
            coalesce((
                select sum(refund.amount_due)
                from lending.loan_unused_advance_refund_dues refund
                where refund.adjustment_id = adjustment.id
            ), 0)::numeric(18,2) as refund_due_total,
            (
                select count(*)
                from core.audit_logs audit
                where audit.target_type = 'collection_transaction'
                  and audit.target_id = transaction.id
                  and audit.action = 'collection.7x7.extra_principal.recorded'
            )::integer as audit_count,
            readiness.source_evidence_ready,
            readiness.accounting_status,
            readiness.automatic_source_posting
        from lending.collection_transactions transaction
        join lending.seven_by_seven_extra_principal_adjustments adjustment
          on adjustment.transaction_id = transaction.id
         and adjustment.id = %s
        join lending.loan_collection_state state
          on state.loan_id = transaction.loan_id
        left join accounting.seven_by_seven_extra_principal_accounting_readiness readiness
          on readiness.adjustment_id = adjustment.id
        where transaction.id = %s
        """,
        (adjustment_id, transaction_id),
    )
    header = cursor.fetchone()
    if header is None:
        _fail("receipt")

    cursor.execute(
        """
        select
            count(*)::integer as item_count,
            coalesce(sum(
                item.prior_operational_principal_component
                - item.new_operational_principal_component
            ), 0)::numeric(18,2) as item_principal_reduction,
            coalesce(sum(item.new_operational_principal_component), 0)
                ::numeric(18,2) as item_resulting_future_principal,
            coalesce(sum(
                item.prior_operational_interest_component
                - item.new_operational_interest_component
            ), 0)::numeric(18,2) as item_removed_future_interest,
            coalesce(sum(item.advance_retained_after), 0)::numeric(18,2)
                as retained_advance,
            coalesce(sum(item.advance_refund_due), 0)::numeric(18,2)
                as item_refund_due,
            count(*) filter (
                where operational.installment_id = item.installment_id
                  and operational.operational_amount = item.new_operational_amount
                  and operational.operational_principal_component
                      = item.new_operational_principal_component
                  and operational.operational_interest_component
                      = item.new_operational_interest_component
                  and operational.removed_from_operational_schedule
                      = item.removed_from_operational_schedule
                  and operational.last_extra_principal_adjustment_id
                      = item.adjustment_id
            )::integer as operational_exact_count
        from lending.seven_by_seven_extra_principal_adjustment_items item
        left join lending.loan_installment_operational_amounts operational
          on operational.installment_id = item.installment_id
        where item.adjustment_id = %s
        """,
        (adjustment_id,),
    )
    items = cursor.fetchone()
    if items is None or int(items["item_count"] or 0) <= 0:
        _fail("operational_row")

    cash_received = _money_field(header, "cash_received", "receipt")
    applied_amount = _money_field(header, "applied_amount", "receipt")
    unallocated_amount = _money_field(header, "unallocated_amount", "receipt")
    previous_balance = _money_field(header, "previous_balance", "receipt")
    official_balance = _money_field(header, "official_balance", "receipt")
    state_balance = _money_field(header, "state_balance", "receipt")
    interest_contribution = _money_field(
        header, "receipt_interest_contribution", "receipt"
    )
    principal_contribution = _money_field(
        header, "receipt_principal_contribution", "receipt"
    )
    adjustment_principal = _money_field(header, "principal_reduction", "receipt")
    prior_future_principal = _money_field(header, "prior_future_principal", "receipt")
    future_principal = _money_field(header, "resulting_future_principal", "receipt")
    removed_future_interest = _money_field(header, "removed_future_interest", "receipt")
    adjustment_refund_due = _money_field(header, "adjustment_refund_due", "refund_due")
    refund_due_total = _money_field(header, "refund_due_total", "refund_due")

    if (
        header["transaction_id"] != transaction_id
        or header["adjustment_id"] != adjustment_id
        or header["receipt_loan_id"] != header["adjustment_loan_id"]
        or str(header["entry_type"]) != "payment"
        or bool(header["is_voided"])
        or str(header["allocation_state"]) != "fully_allocated"
        or str(header["receipt_intent"]) != "extra_as_principal_reduction"
        or applied_amount != cash_received
        or unallocated_amount != ZERO
        or interest_contribution != ZERO
        or principal_contribution != cash_received
        or adjustment_principal != cash_received
        or previous_balance - official_balance != cash_received
        or state_balance != official_balance
        or prior_future_principal - future_principal != adjustment_principal
    ):
        _fail("receipt")

    item_count = int(items["item_count"])
    if (
        int(items["operational_exact_count"] or 0) != item_count
        or _money_field(items, "item_principal_reduction", "operational_row")
        != adjustment_principal
        or _money_field(
            items,
            "item_resulting_future_principal",
            "operational_row",
        )
        != future_principal
        or _money_field(items, "item_removed_future_interest", "operational_row")
        != removed_future_interest
    ):
        _fail("operational_row")

    item_refund_due = _money_field(items, "item_refund_due", "refund_due")
    if (
        adjustment_refund_due != item_refund_due
        or adjustment_refund_due != refund_due_total
    ):
        _fail("refund_due")

    audit_present = int(header["audit_count"] or 0) == 1
    if not audit_present:
        _fail("audit")

    accounting_status = str(header["accounting_status"] or "")
    if (
        not bool(header["source_evidence_ready"])
        or bool(header["automatic_source_posting"])
        or accounting_status
        not in {
            "management_accounting_review_required",
            "ready_for_management_draft",
            "prepared_not_posted",
            "posted",
        }
    ):
        _fail("accounting_readiness")

    digest = str(header["receipt_operational_state_digest"] or "")
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        _fail("operational_row")

    return ExtraPrincipalReconciliation(
        cash_received=cash_received,
        receipt_total=money(applied_amount + unallocated_amount),
        interest_contribution=interest_contribution,
        principal_contribution=principal_contribution,
        adjustment_principal=adjustment_principal,
        future_principal=future_principal,
        removed_future_interest=removed_future_interest,
        retained_advance=_money_field(items, "retained_advance", "refund_due"),
        refund_due=refund_due_total,
        operational_version=int(header["resulting_operational_version"]),
        accounting_status=accounting_status,
        audit_present=audit_present,
        operational_state_digest=digest,
    )


def _money_field(row: dict[str, object], field: str, fault: str) -> Decimal:
    try:
        value = row[field]
        if value is None:
            raise InvalidOperation
        return money(Decimal(str(value)))
    except (InvalidOperation, KeyError, TypeError, ValueError) as error:
        raise ExtraPrincipalReconciliationError(
            f"{fault}: persisted money coordinate {field} is invalid."
        ) from error


def _fail(fault: str) -> NoReturn:
    raise ExtraPrincipalReconciliationError(
        f"{fault}: persisted 7x7 Extra Principal coordinates do not reconcile."
    )
