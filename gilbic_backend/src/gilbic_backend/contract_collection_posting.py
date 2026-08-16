from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from spina_mobile_collections.contracts import (
    ActorContext,
    CollectionCommand,
    CollectionEntryType,
    PostedCollection,
)
from spina_mobile_collections.service import CollectionConflict, CollectionRejected

from .contract_schedule_engine import AllocationInstruction
from .contract_schedule_service import (
    ContractPaymentAllocationConflict,
    ContractScheduleNotReady,
    allocate_collection_transaction,
)
from .cross_collector_posting import CrossCollectorCollectionPostingBridge


CONTRACT_ALLOCATION_SETTING = "mobile_contract_schedule_allocation_enabled"


@dataclass(frozen=True, slots=True)
class ContractCollectionGate:
    loan_id: UUID
    schedule_id: UUID
    schedule_version: int
    payment_frequency: str
    contract_reference: str
    remaining_balance: Decimal
    unpaid_contractual_amount: Decimal


class ContractAwareCrossCollectorCollectionPostingBridge(
    CrossCollectorCollectionPostingBridge
):
    """Feature-gated contractual allocation around the official collection write.

    The normal posting bridge remains authoritative for device, route, balance,
    receipt, audit, and idempotency rules. Contract allocation is activated only
    when the loan type explicitly enables it and the active schedule is both
    evidence-verified and DPD-ready. The wrapper runs inside the executor's same
    PostgreSQL transaction, so any contract failure rolls the official write back.
    """

    def __init__(self) -> None:
        self._contract_mode = False

    def post_collection(
        self,
        connection: Connection[Any],
        actor: ActorContext,
        command: CollectionCommand,
    ) -> PostedCollection:
        gate = self._load_contract_gate(connection, command=command)
        if gate is None:
            return self._post_official_collection(connection, actor, command)

        if command.entry_type is CollectionEntryType.ADVANCE:
            self._verify_contract_advance(connection, gate=gate, command=command)
        elif command.entry_type is CollectionEntryType.PASS:
            self._verify_contract_pass_due(connection, gate=gate, command=command)

        self._contract_mode = True
        try:
            posted = self._post_official_collection(connection, actor, command)
        finally:
            self._contract_mode = False

        self._finalize_contract_effects(
            connection,
            actor=actor,
            command=command,
            gate=gate,
            posted=posted,
        )
        return posted

    def _post_official_collection(
        self,
        connection: Connection[Any],
        actor: ActorContext,
        command: CollectionCommand,
    ) -> PostedCollection:
        return super().post_collection(connection, actor, command)

    def _covered_dates(self, command: CollectionCommand) -> tuple[date, ...]:
        if not self._contract_mode:
            return super()._covered_dates(command)
        # A normal cash payment follows the oldest unpaid contractual installment,
        # even when the app sent today's date under the legacy collection contract.
        if command.entry_type is CollectionEntryType.PAYMENT:
            return ()
        # ADV is accepted only with exact contractual dates validated below. Do
        # not expand first/last bounds into calendar dates for weekly/monthly loans.
        if command.entry_type is CollectionEntryType.ADVANCE:
            return tuple(sorted(set(command.covered_dates)))
        return ()

    def _load_contract_gate(
        self,
        connection: Connection[Any],
        *,
        command: CollectionCommand,
    ) -> ContractCollectionGate | None:
        loan_id = self._uuid(command.loan_id, "loan")
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                select
                    lower(coalesce(
                        loan_type.settings->>%s,
                        ''
                    )) in ('true', '1', 'yes', 'on') as allocation_enabled,
                    coalesce(state.remaining_balance, loan.principal)::numeric(18,2)
                        as remaining_balance,
                    assessment.schedule_id,
                    assessment.schedule_version,
                    assessment.payment_frequency,
                    assessment.contract_reference,
                    assessment.dpd_data_status,
                    assessment.contractual_schedule_total,
                    assessment.allocated_schedule_total,
                    assessment.automatic_default_label_written,
                    assessment.ecl_included,
                    assessment.ecl_amount,
                    assessment.ready_to_post,
                    registration.id as registration_id
                from lending.loans loan
                join lending.loan_types loan_type
                  on loan_type.id = loan.loan_type_id
                left join lending.loan_collection_state state
                  on state.loan_id = loan.id
                left join accounting.loan_contract_dpd_assessment assessment
                  on assessment.loan_id = loan.id
                left join lending.loan_contract_schedule_registrations registration
                  on registration.schedule_id = assessment.schedule_id
                where loan.id = %s
                """,
                (CONTRACT_ALLOCATION_SETTING, loan_id),
            )
            row = cursor.fetchone()

        # Let the official bridge produce its existing loan-not-found response.
        if row is None or not bool(row["allocation_enabled"]):
            return None
        if row["schedule_id"] is None or row["registration_id"] is None:
            raise CollectionRejected(
                "Contract-schedule collection is enabled, but this loan has no "
                "verified active signed-contract schedule. Ask Management to review it.",
                code="contract_schedule_not_verified",
            )
        if str(row["dpd_data_status"]) != "ready":
            raise CollectionRejected(
                "This loan's contractual schedule is not ready for automatic payment "
                "allocation. Ask Management to reconcile its schedule and prior payments.",
                code="contract_schedule_allocation_not_ready",
            )
        if (
            bool(row["automatic_default_label_written"])
            or bool(row["ecl_included"])
            or row["ecl_amount"] is not None
            or bool(row["ready_to_post"])
        ):
            raise CollectionRejected(
                "The contractual collection gate detected an unsafe accounting state.",
                code="contract_schedule_accounting_guard",
            )

        remaining_balance = self._money(row["remaining_balance"])
        unpaid_contractual_amount = self._money(
            Decimal(row["contractual_schedule_total"])
            - Decimal(row["allocated_schedule_total"])
        )
        if remaining_balance != unpaid_contractual_amount:
            raise CollectionRejected(
                "The operational balance does not match the unpaid signed-contract "
                "schedule. Reconcile the loan before enabling contractual collection.",
                code="contract_balance_not_reconciled",
            )

        return ContractCollectionGate(
            loan_id=loan_id,
            schedule_id=row["schedule_id"],
            schedule_version=int(row["schedule_version"]),
            payment_frequency=str(row["payment_frequency"]),
            contract_reference=str(row["contract_reference"]),
            remaining_balance=remaining_balance,
            unpaid_contractual_amount=unpaid_contractual_amount,
        )

    def _verify_contract_advance(
        self,
        connection: Connection[Any],
        *,
        gate: ContractCollectionGate,
        command: CollectionCommand,
    ) -> None:
        selected_dates = tuple(sorted(set(command.covered_dates)))
        if not selected_dates:
            raise CollectionRejected(
                "Choose the exact contractual installment dates covered by this ADV payment.",
                code="contract_advance_dates_required",
            )
        if (
            command.advance_from != selected_dates[0]
            or command.advance_until != selected_dates[-1]
        ):
            raise CollectionRejected(
                "The ADV first/last dates must match the exact contractual dates selected.",
                code="contract_advance_bounds_mismatch",
            )

        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                select
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
                  and installment.effective_due_date = any(%s)
                group by
                    installment.id,
                    installment.effective_due_date,
                    installment.contractual_amount
                order by installment.effective_due_date
                """,
                (gate.schedule_id, list(selected_dates)),
            )
            rows = cursor.fetchall()

        found_dates = tuple(row["effective_due_date"] for row in rows)
        if found_dates != selected_dates:
            raise CollectionRejected(
                "Every ADV date must be an exact contractual installment date.",
                code="contract_advance_invalid_date",
            )

        selected_remaining = Decimal("0.00")
        for row in rows:
            remaining = self._money(
                Decimal(row["contractual_amount"]) - Decimal(row["allocated_amount"])
            )
            if remaining <= Decimal("0.00"):
                raise CollectionRejected(
                    f"{row['due_date'].isoformat()} is already fully covered.",
                    code="contract_advance_date_already_covered",
                )
            selected_remaining = self._money(selected_remaining + remaining)

        amount = self._money(command.amount or Decimal("0.00"))
        if amount != selected_remaining:
            raise CollectionRejected(
                "An ADV payment must fully cover the selected contractual installments. "
                "Use Manual amount for a partial payment.",
                code="contract_advance_amount_mismatch",
            )

    def _verify_contract_pass_due(
        self,
        connection: Connection[Any],
        *,
        gate: ContractCollectionGate,
        command: CollectionCommand,
    ) -> None:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                select exists (
                    select 1
                    from lending.loan_contract_installments_operational installment
                    left join lending.loan_installment_payment_allocations allocation
                      on allocation.installment_id = installment.id
                    left join lending.collection_transactions allocation_transaction
                      on allocation_transaction.id = allocation.transaction_id
                    where installment.schedule_id = %s
                      and installment.effective_due_date = %s
                    group by
                        installment.id,
                        installment.contractual_amount
                    having coalesce(sum(allocation.amount_applied) filter (
                        where allocation_transaction.is_voided = false
                    ), 0) < installment.contractual_amount
                ) as has_unpaid_due
                """,
                (gate.schedule_id, command.collection_date),
            )
            row = cursor.fetchone()
        if row is None or not bool(row["has_unpaid_due"]):
            raise CollectionRejected(
                "No unpaid contractual installment is due today. Do not record "
                "Unable to pay for an ADV-covered or non-scheduled day.",
                code="contract_pass_not_due",
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
        transaction_id = self._uuid(posted.server_transaction_id, "collection transaction")
        actor_user_id = self._uuid(actor.account_id, "authenticated collector")
        with connection.cursor(row_factory=dict_row) as cursor:
            self._verify_gate_unchanged(cursor, gate=gate)

            plan: tuple[AllocationInstruction, ...] = ()
            fully_paid_dates: tuple[date, ...] = ()
            if command.entry_type is not CollectionEntryType.PASS:
                explicit_dates = (
                    tuple(sorted(set(command.covered_dates)))
                    if command.entry_type is CollectionEntryType.ADVANCE
                    else ()
                )
                try:
                    plan = allocate_collection_transaction(
                        cursor,
                        transaction_id=transaction_id,
                        explicit_covered_dates=explicit_dates,
                    )
                except ContractScheduleNotReady as error:
                    raise CollectionRejected(
                        str(error),
                        code="contract_schedule_not_ready",
                    ) from error
                except ContractPaymentAllocationConflict as error:
                    raise CollectionRejected(
                        str(error),
                        code="contract_payment_allocation_conflict",
                    ) from error

                fully_paid_dates = self._fully_paid_touched_dates(cursor, plan=plan)
                if command.entry_type is CollectionEntryType.ADVANCE:
                    selected = tuple(sorted(set(command.covered_dates)))
                    if fully_paid_dates != selected:
                        raise CollectionRejected(
                            "The ADV payment did not fully cover every selected contractual date.",
                            code="contract_advance_incomplete",
                        )
                else:
                    self._insert_fully_covered_dates(
                        cursor,
                        loan_id=gate.loan_id,
                        transaction_id=transaction_id,
                        covered_dates=fully_paid_dates,
                    )

            self._record_contract_audit(
                cursor,
                actor_user_id=actor_user_id,
                transaction_id=transaction_id,
                gate=gate,
                command=command,
                plan=plan,
                fully_paid_dates=fully_paid_dates,
            )
            self._verify_contract_postcondition(cursor, gate=gate)

    @staticmethod
    def _verify_gate_unchanged(cursor: Any, *, gate: ContractCollectionGate) -> None:
        cursor.execute(
            """
            select assessment.schedule_id, registration.id as registration_id
            from accounting.loan_contract_dpd_assessment assessment
            left join lending.loan_contract_schedule_registrations registration
              on registration.schedule_id = assessment.schedule_id
            where assessment.loan_id = %s
            """,
            (gate.loan_id,),
        )
        row = cursor.fetchone()
        if (
            row is None
            or row["schedule_id"] != gate.schedule_id
            or row["registration_id"] is None
        ):
            raise CollectionConflict(
                "The verified contract schedule changed while this payment was being saved. "
                "Refresh the route and try again.",
                code="contract_schedule_changed",
            )

    def _fully_paid_touched_dates(
        self,
        cursor: Any,
        *,
        plan: tuple[AllocationInstruction, ...],
    ) -> tuple[date, ...]:
        if not plan:
            return ()
        installment_ids = [instruction.installment_id for instruction in plan]
        cursor.execute(
            """
            select
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
            where installment.id = any(%s)
            group by
                installment.id,
                installment.effective_due_date,
                installment.contractual_amount
            order by installment.effective_due_date, installment.installment_number
            """,
            (installment_ids,),
        )
        fully_paid = []
        for row in cursor.fetchall():
            if self._money(row["allocated_amount"]) >= self._money(
                row["contractual_amount"]
            ):
                fully_paid.append(row["effective_due_date"])
        return tuple(sorted(set(fully_paid)))

    @staticmethod
    def _insert_fully_covered_dates(
        cursor: Any,
        *,
        loan_id: UUID,
        transaction_id: UUID,
        covered_dates: tuple[date, ...],
    ) -> None:
        if not covered_dates:
            return
        cursor.execute(
            """
            select covered_date, transaction_id
            from lending.collection_covered_dates
            where loan_id = %s
              and covered_date = any(%s)
              and transaction_id <> %s
            order by covered_date
            limit 1
            """,
            (loan_id, list(covered_dates), transaction_id),
        )
        conflict = cursor.fetchone()
        if conflict is not None:
            raise CollectionConflict(
                f"{conflict['covered_date'].isoformat()} is already tied to another payment.",
                code="contract_covered_date_conflict",
            )
        for covered_date in covered_dates:
            cursor.execute(
                """
                insert into lending.collection_covered_dates (
                    transaction_id, loan_id, covered_date
                ) values (%s, %s, %s)
                on conflict (transaction_id, covered_date) do nothing
                """,
                (transaction_id, loan_id, covered_date),
            )

    @staticmethod
    def _record_contract_audit(
        cursor: Any,
        *,
        actor_user_id: UUID,
        transaction_id: UUID,
        gate: ContractCollectionGate,
        command: CollectionCommand,
        plan: tuple[AllocationInstruction, ...],
        fully_paid_dates: tuple[date, ...],
    ) -> None:
        allocation_payload = [
            {
                "installment_number": instruction.installment_number,
                "due_date": instruction.due_date.isoformat(),
                "amount_applied": str(instruction.amount_applied),
                "allocation_basis": instruction.allocation_basis,
            }
            for instruction in plan
        ]
        contract_payload = {
            "enabled": True,
            "schedule_id": str(gate.schedule_id),
            "schedule_version": gate.schedule_version,
            "payment_frequency": gate.payment_frequency,
            "contract_reference": gate.contract_reference,
            "entry_type": command.entry_type.value,
            "allocations": allocation_payload,
            "fully_covered_dates": [
                value.isoformat() for value in fully_paid_dates
            ],
        }
        cursor.execute(
            """
            update lending.collection_transactions
            set details = coalesce(details, '{}'::jsonb) || %s
            where id = %s and is_locked = false
            """,
            (Jsonb({"contract_schedule_allocation": contract_payload}), transaction_id),
        )
        cursor.execute(
            """
            insert into core.audit_logs (
                actor_user_id,
                action,
                target_type,
                target_id,
                details,
                created_at
            ) values (
                %s,
                %s,
                'collection_transaction',
                %s,
                %s,
                now()
            )
            """,
            (
                actor_user_id,
                (
                    "collection.contract_schedule.pass_validated"
                    if command.entry_type is CollectionEntryType.PASS
                    else "collection.contract_schedule.allocated"
                ),
                transaction_id,
                Jsonb(contract_payload),
            ),
        )

    def _verify_contract_postcondition(
        self,
        cursor: Any,
        *,
        gate: ContractCollectionGate,
    ) -> None:
        cursor.execute(
            """
            select
                assessment.schedule_id,
                assessment.dpd_data_status,
                assessment.contractual_schedule_total,
                assessment.allocated_schedule_total,
                assessment.automatic_default_label_written,
                assessment.ecl_included,
                assessment.ecl_amount,
                assessment.ready_to_post,
                state.remaining_balance
            from accounting.loan_contract_dpd_assessment assessment
            join lending.loan_collection_state state
              on state.loan_id = assessment.loan_id
            where assessment.loan_id = %s
            """,
            (gate.loan_id,),
        )
        row = cursor.fetchone()
        if row is None or row["schedule_id"] != gate.schedule_id:
            raise CollectionConflict(
                "The contractual schedule changed before collection verification finished.",
                code="contract_schedule_changed",
            )
        if str(row["dpd_data_status"]) != "ready":
            raise CollectionRejected(
                "The payment could not be fully reconciled to the contractual schedule.",
                code="contract_allocation_postcondition_failed",
            )
        unpaid_contractual_amount = self._money(
            Decimal(row["contractual_schedule_total"])
            - Decimal(row["allocated_schedule_total"])
        )
        if self._money(row["remaining_balance"]) != unpaid_contractual_amount:
            raise CollectionRejected(
                "The payment would leave the operational and contractual balances out of sync.",
                code="contract_balance_postcondition_failed",
            )
        if (
            bool(row["automatic_default_label_written"])
            or bool(row["ecl_included"])
            or row["ecl_amount"] is not None
            or bool(row["ready_to_post"])
        ):
            raise CollectionRejected(
                "Collection allocation unexpectedly crossed an accounting safety boundary.",
                code="contract_schedule_accounting_guard",
            )
