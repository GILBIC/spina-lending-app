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
    plan_protected_regular_allocation,
)
from .seven_by_seven_multi_receipt_posting import (
    MultiReceiptSevenBySevenCollectionPostingBridge,
)


class VoluntaryExtraAwareCollectionPostingBridge(
    MultiReceiptSevenBySevenCollectionPostingBridge
):
    """Protect Regular cash allocation while preserving one real cash receipt.

    For an activated Regular contractual schedule, a PAYMENT clears every unpaid
    obligation due on or before the receipt date, oldest first. Only money left
    after Past Due and Due Today are fully satisfied is genuine extra cash.

    Genuine extra is never guessed. The borrower must explicitly direct it to
    Advance or Principal Reduction. Advance applies to the oldest unpaid future
    contractual obligation first; Principal Reduction applies from the
    contractual tail. The historical ``voluntary_extra_tail`` database label is
    retained for Principal Reduction compatibility.

    7x7 remains on its separate protected allocator.
    """

    _EXTRA_INTENTS = frozenset(
        {
            PaymentAllocationIntent.EXTRA_AS_ADVANCE,
            PaymentAllocationIntent.EXTRA_AS_PRINCIPAL_REDUCTION,
            PaymentAllocationIntent.VOLUNTARY_EXTRA,
        }
    )

    def post_collection(
        self,
        connection: Connection[Any],
        actor: ActorContext,
        command: CollectionCommand,
    ) -> PostedCollection:
        if (
            command.payment_allocation_intent in self._EXTRA_INTENTS
            and command.entry_type is not CollectionEntryType.PAYMENT
        ):
            raise CollectionRejected(
                "Regular extra allocation is a Payment choice. Unable to pay cannot contain money, and legacy ADV uses its own protected path.",
                code="regular_extra_entry_type_invalid",
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

        # Required cash is the complete unpaid amount already due, not merely
        # one row. This makes Past Due -> newer Past Due -> Due Today the hard
        # boundary before any cash can become genuine extra.
        cursor.execute(
            """
            with due_rows as (
                select
                    installment.id,
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
                group by installment.id, installment.contractual_amount
            )
            select coalesce(sum(greatest(contractual_amount - allocated_amount, 0)), 0)
                ::numeric(18,2) as due_remaining
            from due_rows
            """,
            (loan["loan_id"], command.collection_date),
        )
        row = cursor.fetchone()
        return self._money(row["due_remaining"] if row else Decimal("0.00"))

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
                allocation_intent=command.payment_allocation_intent,
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

            required_plan: tuple[AllocationInstruction, ...] = tuple(
                item for item in plan if item.allocation_basis == "oldest_due_first"
            )
            fully_paid_required_dates = self._fully_paid_touched_dates(
                cursor,
                plan=required_plan,
            )
            self._insert_fully_covered_dates(
                cursor,
                loan_id=gate.loan_id,
                transaction_id=transaction_id,
                covered_dates=fully_paid_required_dates,
            )
            self._record_contract_audit(
                cursor,
                actor_user_id=actor_user_id,
                transaction_id=transaction_id,
                gate=gate,
                command=command,
                plan=plan,
                fully_paid_dates=fully_paid_required_dates,
            )
            self._verify_contract_postcondition(cursor, gate=gate)

    def _plan_applied_contract_payment(
        self,
        *,
        applied_amount: Decimal,
        installments: tuple[OutstandingInstallment, ...],
        collection_date,
        allocation_intent: PaymentAllocationIntent = PaymentAllocationIntent.SCHEDULED,
        voluntary_extra: bool | None = None,
    ) -> tuple[AllocationInstruction, ...]:
        """Return the protected Regular allocation for one applied receipt.

        ``voluntary_extra`` is accepted only as a temporary test/caller
        compatibility argument. It never authorizes Principal Reduction; an
        explicit modern allocation intent is required for genuine extra cash.
        """

        amount = self._money(applied_amount)
        if amount <= Decimal("0.00"):
            return ()

        # Older direct unit callers may still pass the retired boolean. Preserve
        # parse compatibility but deliberately do not infer a borrower choice.
        del voluntary_extra

        if allocation_intent is PaymentAllocationIntent.EXTRA_AS_ADVANCE:
            extra_choice = "advance"
        elif allocation_intent is PaymentAllocationIntent.EXTRA_AS_PRINCIPAL_REDUCTION:
            extra_choice = "principal_reduction"
        else:
            # SCHEDULED and legacy VOLUNTARY_EXTRA are intentionally ambiguous
            # once genuine extra remains, so the protected planner fails closed.
            extra_choice = None

        try:
            return plan_protected_regular_allocation(
                transaction_amount=amount,
                installments=installments,
                collection_date=collection_date,
                extra_choice=extra_choice,
            )
        except PaymentAllocationError as error:
            message = str(error)
            code = (
                "extra_allocation_choice_required"
                if "Choose Advance or Principal Reduction" in message
                else "contract_payment_allocation_conflict"
            )
            raise CollectionRejected(message, code=code) from error

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
                select
                    transaction.amount,
                    transaction.applied_amount,
                    transaction.unallocated_amount,
                    transaction.allocation_state,
                    coalesce(sum(allocation.amount_applied) filter (
                        where allocation.allocation_basis = 'voluntary_extra_tail'
                    ), 0)::numeric(18,2) as principal_reduction_amount,
                    coalesce(sum(allocation.amount_applied) filter (
                        where allocation.allocation_basis = 'future_advance_oldest_first'
                    ), 0)::numeric(18,2) as advance_extra_amount
                from lending.collection_transactions transaction
                left join lending.loan_installment_payment_allocations allocation
                  on allocation.transaction_id = transaction.id
                where transaction.id = %s
                group by
                    transaction.id,
                    transaction.amount,
                    transaction.applied_amount,
                    transaction.unallocated_amount,
                    transaction.allocation_state
                """,
                (transaction_id,),
            )
            receipt = cursor.fetchone()
            principal_reduction_amount = self._money(
                receipt["principal_reduction_amount"] if receipt else Decimal("0.00")
            )
            advance_extra_amount = self._money(
                receipt["advance_extra_amount"] if receipt else Decimal("0.00")
            )
            cursor.execute(
                """
                update lending.collection_transactions
                set details = coalesce(details, '{}'::jsonb) || %s
                where id = %s and is_locked = false
                """,
                (
                    Jsonb(
                        {
                            "payment_allocation_intent": intent,
                            "non_advance_excess_policy": "explicit_borrower_choice",
                            "extra_allocation_policy": intent,
                            "principal_extra_amount": str(principal_reduction_amount),
                            "advance_extra_amount": str(advance_extra_amount),
                            "automatic_non_advance_principal_reduction": False,
                        }
                    ),
                    transaction_id,
                ),
            )
            if (
                principal_reduction_amount > Decimal("0.00")
                or advance_extra_amount > Decimal("0.00")
            ):
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
                        'collection.regular_extra.recorded',
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
                                "principal_reduction_amount": str(
                                    principal_reduction_amount
                                ),
                                "advance_extra_amount": str(advance_extra_amount),
                                "allocation_state": (
                                    str(receipt["allocation_state"]) if receipt else None
                                ),
                                "payment_allocation_intent": intent,
                                "automatic_non_advance_principal_reduction": False,
                            }
                        ),
                    ),
                )
