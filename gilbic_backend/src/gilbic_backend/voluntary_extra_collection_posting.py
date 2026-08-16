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
from .contract_schedule_engine import (
    AllocationInstruction,
    OutstandingInstallment,
    PaymentAllocationError,
    plan_scheduled_or_voluntary_extra_allocation,
)
from .seven_by_seven_multi_receipt_posting import (
    MultiReceiptSevenBySevenCollectionPostingBridge,
)


class VoluntaryExtraAwareCollectionPostingBridge(
    MultiReceiptSevenBySevenCollectionPostingBridge
):
    """Keep voluntary extra separate from ADV while preserving one cash receipt.

    For an activated Regular contractual schedule, a normal PAYMENT applies only
    to the oldest unpaid installment. Cash above that installment is rejected
    unless the client explicitly chose ``voluntary_extra``. Explicit voluntary
    extra is allocated from the contractual tail, shortening the loan without
    marking tomorrow as covered.

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
        amount = self._money(command.amount or Decimal("0.00"))

        with connection.cursor(row_factory=dict_row) as cursor:
            self._verify_gate_unchanged(cursor, gate=gate)
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

            try:
                plan = plan_scheduled_or_voluntary_extra_allocation(
                    transaction_amount=amount,
                    installments=outstanding,
                    voluntary_extra=(
                        command.payment_allocation_intent
                        is PaymentAllocationIntent.VOLUNTARY_EXTRA
                    ),
                )
            except PaymentAllocationError as error:
                raise CollectionRejected(
                    str(error),
                    code=(
                        "payment_allocation_intent_required"
                        if "Choose Voluntary extra" in str(error)
                        else "contract_payment_allocation_conflict"
                    ),
                ) from error

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
                                "payment_allocation_intent": intent,
                                "future_dates_marked_advance": False,
                            }
                        ),
                    ),
                )
