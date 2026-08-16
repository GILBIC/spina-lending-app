from __future__ import annotations

from decimal import Decimal
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from spina_mobile_collections.contracts import (
    ActorContext,
    CollectionCommand,
    CollectionEntryType,
    PaymentAllocationIntent,
    PostedCollection,
)
from spina_mobile_collections.service import CollectionRejected

from .contract_collection_posting import ContractCollectionGate
from .contract_schedule_engine import AllocationInstruction, OutstandingInstallment
from .seven_by_seven_multi_receipt_posting import (
    MultiReceiptSevenBySevenCollectionPostingBridge,
)


class VoluntaryExtraAwareCollectionPostingBridge(
    MultiReceiptSevenBySevenCollectionPostingBridge
):
    """Keep voluntary extra separate from ADV while preserving one cash receipt.

    For an activated Regular contractual schedule, a normal PAYMENT can apply only
    to the oldest unpaid installment that is actually due on or before the receipt
    date. Cash above that eligible obligation remains an audited unallocated
    receipt unless the client explicitly chose ``voluntary_extra``.

    Explicit voluntary extra first satisfies the currently due scheduled amount,
    when one exists, then allocates from the contractual tail. If no installment
    is due yet, the entire applied voluntary-extra amount starts at the tail so the
    next normal collection date remains due. It is never silently converted to ADV.

    7x7 stays on its protected fixed-original-principal, interest-first allocator;
    the explicit intent is retained in the immutable transaction/audit evidence.
    """

    def post_collection(
        self,
        connection: Connection[Any],
        actor: ActorContext,
        command: CollectionCommand,
    ) -> PostedCollection:
        if (
            command.payment_allocation_intent is PaymentAllocationIntent.VOLUNTARY_EXTRA
            and command.entry_type is not CollectionEntryType.PAYMENT
        ):
            raise CollectionRejected(
                "Voluntary extra is a payment intent. ADV must use exact covered dates, and Unable to pay cannot contain money.",
                code="voluntary_extra_entry_type_invalid",
            )

        posted = super().post_collection(connection, actor, command)
        if command.entry_type is CollectionEntryType.PAYMENT:
            self._record_payment_intent(
                connection,
                actor=actor,
                command=command,
                posted=posted,
            )
        return posted

    def _scheduled_payment_remaining(
        self,
        cursor: Any,
        *,
        loan: dict[str, Any],
        command: CollectionCommand,
    ) -> Decimal:
        if not self._contract_mode:
            return super()._scheduled_payment_remaining(
                cursor,
                loan=loan,
                command=command,
            )

        cursor.execute(
            """
            select
                installment.contractual_amount,
                coalesce(sum(allocation.amount_applied) filter (
                    where allocation_transaction.is_voided = false
                ), 0)::numeric(18,2) as allocated_amount
            from accounting.loan_contract_dpd_assessment assessment
            join lending.loan_contract_installments_operational installment
              on installment.schedule_id = assessment.schedule_id
            left join lending.loan_installment_payment_allocations allocation
              on allocation.installment_id = installment.id
            left join lending.collection_transactions allocation_transaction
              on allocation_transaction.id = allocation.transaction_id
            where assessment.loan_id = %s
              and installment.effective_due_date <= %s
            group by
                installment.id,
                installment.installment_number,
                installment.effective_due_date,
                installment.contractual_amount
            having coalesce(sum(allocation.amount_applied) filter (
                where allocation_transaction.is_voided = false
            ), 0) < installment.contractual_amount
            order by
                installment.effective_due_date,
                installment.installment_number,
                installment.id
            limit 1
            """,
            (loan["loan_id"], command.collection_date),
        )
        row = cursor.fetchone()
        if row is None:
            return Decimal("0.00")
        return self._money(
            Decimal(row["contractual_amount"]) - Decimal(row["allocated_amount"])
        )

    def _finalize_contract_effects(
        self,
        connection: Connection[Any],
        *,
        actor: ActorContext,
        command: CollectionCommand,
        gate: ContractCollectionGate,
        posted: PostedCollection,
    ) -> None:
        if command.entry_type is not CollectionEntryType.PAYMENT:
            return super()._finalize_contract_effects(
                connection,
                actor=actor,
                command=command,
                gate=gate,
                posted=posted,
            )

        transaction_id = self._uuid(
            posted.server_transaction_id,
            "collection transaction",
        )
        actor_user_id = self._uuid(actor.account_id, "authenticated collector")

        with connection.cursor(row_factory=dict_row) as cursor:
            self._verify_gate_unchanged(cursor, gate=gate)
            cursor.execute(
                """
                select amount, applied_amount, unallocated_amount
                from lending.collection_transactions
                where id = %s
                for update
                """,
                (transaction_id,),
            )
            receipt = cursor.fetchone()
            if receipt is None:
                raise CollectionRejected(
                    "The saved collection receipt could not be reloaded for contractual allocation.",
                    code="contract_payment_receipt_missing",
                )
            cash_received = self._money(receipt["amount"])
            applied_amount = self._money(receipt["applied_amount"])
            unallocated_amount = self._money(receipt["unallocated_amount"])
            if applied_amount + unallocated_amount != cash_received:
                raise CollectionRejected(
                    "The receipt cash does not reconcile to applied plus unallocated amounts.",
                    code="contract_payment_receipt_mismatch",
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
                group by
                    installment.id,
                    installment.installment_number,
                    installment.effective_due_date,
                    installment.contractual_amount
                order by
                    installment.effective_due_date,
                    installment.installment_number,
                    installment.id
                """,
                (gate.schedule_id,),
            )
            outstanding = tuple(
                OutstandingInstallment(
                    installment_id=row["id"],
                    installment_number=int(row["installment_number"]),
                    due_date=row["effective_due_date"],
                    contractual_amount=self._money(row["contractual_amount"]),
                    allocated_amount=self._money(row["allocated_amount"]),
                )
                for row in cursor.fetchall()
            )

            plan = self._plan_applied_contract_payment(
                applied_amount=applied_amount,
                installments=outstanding,
                collection_date=command.collection_date,
                voluntary_extra=(
                    command.payment_allocation_intent
                    is PaymentAllocationIntent.VOLUNTARY_EXTRA
                ),
            )

            for instruction in plan:
                cursor.execute(
                    """
                    insert into lending.loan_installment_payment_allocations (
                        installment_id,
                        transaction_id,
                        amount_applied,
                        allocation_basis,
                        allocation_reference,
                        created_by_user_id
                    )
                    values (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        instruction.installment_id,
                        transaction_id,
                        instruction.amount_applied,
                        instruction.allocation_basis,
                        f"mobile-{command.payment_allocation_intent.value}:{transaction_id}",
                        actor_user_id,
                    ),
                )

            scheduled_plan: tuple[AllocationInstruction, ...] = tuple(
                item for item in plan if item.allocation_basis == "oldest_due_first"
            )
            fully_paid_scheduled_dates = self._fully_paid_touched_dates(
                cursor,
                plan=scheduled_plan,
            )
            self._insert_fully_covered_dates(
                cursor,
                loan_id=gate.loan_id,
                transaction_id=transaction_id,
                covered_dates=fully_paid_scheduled_dates,
            )
            self._record_contract_audit(
                cursor,
                actor_user_id=actor_user_id,
                transaction_id=transaction_id,
                gate=gate,
                command=command,
                plan=plan,
                fully_paid_dates=fully_paid_scheduled_dates,
            )
            self._verify_contract_postcondition(cursor, gate=gate)

    def _plan_applied_contract_payment(
        self,
        *,
        applied_amount: Decimal,
        installments: tuple[OutstandingInstallment, ...],
        collection_date,
        voluntary_extra: bool,
    ) -> tuple[AllocationInstruction, ...]:
        """Allocate only the amount already authorized to reduce the loan."""

        amount_left = self._money(applied_amount)
        if amount_left <= Decimal("0.00"):
            return ()

        remaining = sorted(
            (row for row in installments if row.remaining_amount > Decimal("0.00")),
            key=lambda row: (
                row.due_date,
                row.installment_number,
                str(row.installment_id),
            ),
        )
        if not remaining:
            raise CollectionRejected(
                "The contractual schedule is already fully paid. The receipt must remain unallocated for review.",
                code="contract_payment_allocation_conflict",
            )

        due_now = [row for row in remaining if row.due_date <= collection_date]
        instructions: list[AllocationInstruction] = []
        scheduled_row = due_now[0] if due_now else None
        if scheduled_row is not None:
            scheduled_applied = self._money(
                min(amount_left, scheduled_row.remaining_amount)
            )
            if scheduled_applied > Decimal("0.00"):
                instructions.append(
                    AllocationInstruction(
                        installment_id=scheduled_row.installment_id,
                        installment_number=scheduled_row.installment_number,
                        due_date=scheduled_row.due_date,
                        amount_applied=scheduled_applied,
                        allocation_basis="oldest_due_first",
                    )
                )
                amount_left = self._money(amount_left - scheduled_applied)

        if amount_left <= Decimal("0.00"):
            return tuple(instructions)
        if not voluntary_extra:
            raise CollectionRejected(
                "Applied scheduled cash exceeds the installment currently due. The excess receipt must stay unallocated unless the client explicitly chooses Voluntary extra or ADV.",
                code="contract_payment_allocation_conflict",
            )

        tail_candidates = [row for row in remaining if row is not scheduled_row]
        for row in reversed(tail_candidates):
            if amount_left <= Decimal("0.00"):
                break
            applied = self._money(min(row.remaining_amount, amount_left))
            if applied <= Decimal("0.00"):
                continue
            instructions.append(
                AllocationInstruction(
                    installment_id=row.installment_id,
                    installment_number=row.installment_number,
                    due_date=row.due_date,
                    amount_applied=applied,
                    allocation_basis="voluntary_extra_tail",
                )
            )
            amount_left = self._money(amount_left - applied)

        if amount_left != Decimal("0.00"):
            raise CollectionRejected(
                "Applied voluntary-extra cash exceeds the remaining contractual balance.",
                code="contract_payment_allocation_conflict",
            )
        return tuple(instructions)

    def _record_payment_intent(
        self,
        connection: Connection[Any],
        *,
        actor: ActorContext,
        command: CollectionCommand,
        posted: PostedCollection,
    ) -> None:
        transaction_id = self._uuid(
            posted.server_transaction_id,
            "collection transaction",
        )
        actor_user_id = self._uuid(actor.account_id, "authenticated collector")
        intent = command.payment_allocation_intent.value
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                select amount, applied_amount, unallocated_amount, allocation_state
                from lending.collection_transactions
                where id = %s
                """,
                (transaction_id,),
            )
            receipt = cursor.fetchone()
            cursor.execute(
                """
                update lending.collection_transactions
                set details = coalesce(details, '{}'::jsonb) || %s
                where id = %s and is_locked = false
                """,
                (Jsonb({"payment_allocation_intent": intent}), transaction_id),
            )
            if command.payment_allocation_intent is PaymentAllocationIntent.VOLUNTARY_EXTRA:
                cursor.execute(
                    """
                    insert into core.audit_logs (
                        actor_user_id,
                        action,
                        target_type,
                        target_id,
                        details,
                        created_at
                    )
                    values (
                        %s,
                        'collection.voluntary_extra.recorded',
                        'collection_transaction',
                        %s,
                        %s,
                        now()
                    )
                    """,
                    (
                        actor_user_id,
                        transaction_id,
                        Jsonb(
                            {
                                "loan_id": command.loan_id,
                                "collection_date": command.collection_date.isoformat(),
                                "amount": str(command.amount or Decimal("0.00")),
                                "cash_received_amount": (
                                    str(receipt["amount"]) if receipt else None
                                ),
                                "applied_amount": (
                                    str(receipt["applied_amount"]) if receipt else None
                                ),
                                "unallocated_amount": (
                                    str(receipt["unallocated_amount"]) if receipt else None
                                ),
                                "allocation_state": (
                                    str(receipt["allocation_state"]) if receipt else None
                                ),
                                "payment_allocation_intent": intent,
                                "future_dates_marked_advance": False,
                            }
                        ),
                    ),
                )
