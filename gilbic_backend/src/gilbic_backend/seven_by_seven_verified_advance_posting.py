from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

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

from .collection_posting import DIRECT_BALANCE_MODE
from .seven_by_seven_advance_schedule_allocation import (
    plan_verified_seven_by_seven_advance,
    store_verified_seven_by_seven_advance_allocations,
)
from .seven_by_seven_collection_posting import (
    SEVEN_BY_SEVEN_MOBILE_SETTING,
    SevenBySevenAwarePerLoanContractCollectionPostingBridge,
)
from .seven_by_seven_operational_allocator import (
    SEVEN_BY_SEVEN_OPERATIONAL_POLICY,
    SevenBySevenAllocationError,
    SevenBySevenCashEvent,
    allocate_seven_by_seven_payments,
)
from .seven_by_seven_schedule_allocation import (
    SevenBySevenScheduleAllocationError,
    SevenBySevenVerifiedScheduleNotFound,
)


ZERO = Decimal("0.00")
FUTURE_ADVANCE_BASIS = "future_advance_oldest_first"


class VerifiedAdvanceSevenBySevenCollectionPostingBridge(
    SevenBySevenAwarePerLoanContractCollectionPostingBridge
):
    """Post verified 7x7 Advance as future-row prepayment evidence.

    A protected Advance receipt is cash/custody evidence today, but its signed
    principal and interest components are not earned or reduced today. The cash
    is attached to the oldest unpaid future signed rows and financial activation
    is deferred to each row's effective due date.

    Until that due-date activation slice is implemented, a later normal payment
    fails closed once one of these prepaid rows has matured. This prevents the
    legacy source-event replay from silently recognizing Advance cash too early.
    """

    def _post_seven_by_seven_collection(
        self,
        connection: Connection[Any],
        actor: ActorContext,
        command: CollectionCommand,
    ) -> PostedCollection:
        if command.entry_type is not CollectionEntryType.ADVANCE:
            return super()._post_seven_by_seven_collection(connection, actor, command)
        return self._post_verified_seven_by_seven_advance(connection, actor, command)

    def _post_verified_seven_by_seven_advance(
        self,
        connection: Connection[Any],
        actor: ActorContext,
        command: CollectionCommand,
    ) -> PostedCollection:
        collector_user_id = self._uuid(actor.account_id, "authenticated collector")
        registered_device_id = self._uuid(actor.storage_device_id, "registered device")
        loan_id = self._uuid(command.loan_id, "loan")
        client_id = self._uuid(command.client_id, "client")
        route_entry_id = self._uuid(command.route_entry_id, "route entry")
        covered_dates = self._seven_by_seven_covered_dates(command)

        if route_entry_id != loan_id:
            raise CollectionRejected(
                "This route entry no longer matches the loan. Refresh the route.",
                code="route_entry_changed",
            )
        if not (command.route_revision or "").strip():
            raise CollectionRejected(
                "Refresh the route before saving this entry.",
                code="route_revision_required",
            )

        with connection.cursor(row_factory=dict_row) as cursor:
            self._lock_device_sequence(
                cursor,
                registered_device_id=registered_device_id,
                device_sequence=command.device_sequence,
            )
            self._lock_loan_date(
                cursor,
                loan_id=loan_id,
                collection_date=command.collection_date,
            )
            self._verify_device(
                cursor,
                collector_user_id=collector_user_id,
                registered_device_id=registered_device_id,
            )
            self._verify_device_sequence_available(
                cursor,
                registered_device_id=registered_device_id,
                device_sequence=command.device_sequence,
            )

            cursor.execute(
                """
                insert into lending.loan_collection_state (
                    loan_id, remaining_balance, is_reconciled
                )
                select id, principal, false
                from lending.loans
                where id = %s
                on conflict (loan_id) do nothing
                """,
                (loan_id,),
            )
            cursor.execute(
                """
                select
                    loan.id as loan_id,
                    loan.client_id,
                    loan.status as loan_status,
                    loan.principal,
                    loan.daily_amount,
                    loan.date_released,
                    client.status as client_status,
                    client.area,
                    loan_type.code as loan_type_code,
                    loan_type.name as loan_type_name,
                    loan_type.calculation_mode,
                    loan_type.daily_interest_per_1000,
                    loan_type.settings,
                    state.remaining_balance,
                    state.pass_count,
                    state.last_payment_date,
                    state.advance_until,
                    state.note,
                    state.is_reconciled,
                    state.state_version
                from lending.loans loan
                join lending.clients client on client.id = loan.client_id
                join lending.loan_types loan_type on loan_type.id = loan.loan_type_id
                join lending.loan_collection_state state on state.loan_id = loan.id
                where loan.id = %s and client.id = %s
                for update of loan, client, state, loan_type
                """,
                (loan_id, client_id),
            )
            loan = cursor.fetchone()
            if not loan:
                raise CollectionRejected(
                    "This loan could not be found. Refresh the route.",
                    code="loan_not_found",
                )

            self._validate_loan_and_route(
                cursor,
                loan=loan,
                collector_user_id=collector_user_id,
                command=command,
            )
            self._revalidate_seven_by_seven_mode(loan)

            previous_balance = self._money(loan["remaining_balance"])
            if previous_balance <= ZERO:
                raise CollectionRejected(
                    "This loan is already fully paid.",
                    code="loan_already_paid",
                )

            current_revision = self._route_revision(
                loan_id=loan_id,
                state_version=int(loan["state_version"]),
            )
            if command.route_revision != current_revision:
                raise CollectionConflict(
                    "The loan changed after this route was loaded. Refresh the route "
                    "and review the entry.",
                    code="route_revision_changed",
                )

            self._verify_seven_by_seven_date_available(
                cursor,
                loan_id=loan_id,
                collection_date=command.collection_date,
                entry_type=command.entry_type,
            )

            amount = self._money(command.amount or ZERO)
            if amount <= ZERO:
                raise CollectionRejected(
                    "Enter a 7x7 payment amount greater than zero.",
                    code="invalid_collection_amount",
                )

            self._validate_seven_by_seven_advance(command, covered_dates)
            try:
                schedule_instructions = plan_verified_seven_by_seven_advance(
                    cursor,
                    loan_id=loan_id,
                    collection_date=command.collection_date,
                    transaction_amount=amount,
                )
            except SevenBySevenVerifiedScheduleNotFound as error:
                raise CollectionRejected(str(error), code=error.code) from error
            except SevenBySevenScheduleAllocationError as error:
                raise CollectionRejected(str(error), code=error.code) from error

            planned_dates = tuple(
                instruction.effective_due_date for instruction in schedule_instructions
            )
            if covered_dates != planned_dates:
                raise CollectionRejected(
                    "The selected 7x7 Advance dates no longer match the oldest unpaid "
                    "future signed rows. Refresh the schedule and try again.",
                    code="seven_by_seven_advance_coverage_changed",
                )

            official_balance = previous_balance
            pass_count_after = 0
            last_payment_date = command.collection_date
            latest_planned = planned_dates[-1]
            existing_advance_until = loan["advance_until"]
            advance_until_after = (
                max(existing_advance_until, latest_planned)
                if existing_advance_until is not None
                else latest_planned
            )

            note_after = command.note.strip() or str(loan["note"] or "")
            next_version = int(loan["state_version"]) + 1
            next_revision = self._route_revision(loan_id=loan_id, state_version=next_version)
            accepted_at = datetime.now(timezone.utc)
            transaction_id = uuid4()
            receipt_number = self._next_receipt_number(
                cursor,
                collection_date=command.collection_date,
            )

            cursor.execute(
                """
                update lending.loan_collection_state
                set remaining_balance = %s,
                    pass_count = %s,
                    last_payment_date = %s,
                    advance_until = %s,
                    note = %s,
                    state_version = %s,
                    updated_at = %s
                where loan_id = %s
                """,
                (
                    official_balance,
                    pass_count_after,
                    last_payment_date,
                    advance_until_after,
                    note_after,
                    next_version,
                    accepted_at,
                    loan_id,
                ),
            )

            planned_rows = [
                {
                    "installment_id": instruction.installment_id,
                    "installment_number": instruction.installment_number,
                    "effective_due_date": instruction.effective_due_date.isoformat(),
                    "amount_applied": str(instruction.amount_applied),
                }
                for instruction in schedule_instructions
            ]
            details = {
                "source": "gilbic_mobile",
                "loan_type_code": str(loan["loan_type_code"]),
                "loan_type_name": str(loan["loan_type_name"]),
                "calculation_mode": "seven_by_seven",
                "mobile_balance_mode": DIRECT_BALANCE_MODE,
                "state_version_before": int(loan["state_version"]),
                "state_version_after": next_version,
                "covered_dates": [value.isoformat() for value in planned_dates],
                "seven_by_seven_policy": SEVEN_BY_SEVEN_OPERATIONAL_POLICY,
                "seven_by_seven_mobile_feature": SEVEN_BY_SEVEN_MOBILE_SETTING,
                "seven_by_seven_schedule_allocation_state": "verified_future_rows_allocated",
                "seven_by_seven_advance_financial_state": "deferred_until_effective_due_date",
                "seven_by_seven_advance_rows": planned_rows,
            }
            cursor.execute(
                """
                insert into lending.collection_transactions (
                    id,
                    idempotency_key,
                    loan_id,
                    client_id,
                    collector_user_id,
                    registered_device_id,
                    route_entry_id,
                    collection_date,
                    entry_type,
                    amount,
                    advance_from,
                    advance_until,
                    recorded_at,
                    accepted_at,
                    device_sequence,
                    note,
                    route_revision,
                    previous_balance,
                    official_balance,
                    pass_count_after,
                    advance_until_after,
                    receipt_number,
                    details
                ) values (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s
                )
                """,
                (
                    transaction_id,
                    command.idempotency_key,
                    loan_id,
                    client_id,
                    collector_user_id,
                    registered_device_id,
                    route_entry_id,
                    command.collection_date,
                    command.entry_type.value,
                    amount,
                    planned_dates[0],
                    planned_dates[-1],
                    command.recorded_at,
                    accepted_at,
                    command.device_sequence,
                    command.note.strip(),
                    command.route_revision,
                    previous_balance,
                    official_balance,
                    pass_count_after,
                    advance_until_after,
                    receipt_number,
                    Jsonb(details),
                ),
            )

            store_verified_seven_by_seven_advance_allocations(
                cursor,
                transaction_id=transaction_id,
                actor_user_id=collector_user_id,
                instructions=schedule_instructions,
            )

            # collection_covered_dates is retained only as compatibility evidence.
            # Verified installment allocations are now authoritative, so a second
            # partial receipt may legitimately touch the same future signed row.
            for covered_date in planned_dates:
                cursor.execute(
                    """
                    insert into lending.collection_covered_dates (
                        transaction_id, loan_id, covered_date
                    ) values (%s, %s, %s)
                    on conflict (loan_id, covered_date) do nothing
                    """,
                    (transaction_id, loan_id, covered_date),
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
                ) values (%s, %s, 'collection_transaction', %s, %s, %s)
                """,
                (
                    collector_user_id,
                    "collection.mobile.advance",
                    transaction_id,
                    Jsonb(
                        {
                            "loan_id": str(loan_id),
                            "client_id": str(client_id),
                            "idempotency_key": str(command.idempotency_key),
                            "receipt_number": receipt_number,
                            "amount": str(amount),
                            "official_balance": str(official_balance),
                            "seven_by_seven_policy": SEVEN_BY_SEVEN_OPERATIONAL_POLICY,
                            "seven_by_seven_schedule_allocation_state": (
                                "verified_future_rows_allocated"
                            ),
                            "seven_by_seven_advance_financial_state": (
                                "deferred_until_effective_due_date"
                            ),
                            "covered_dates": [
                                value.isoformat() for value in planned_dates
                            ],
                        }
                    ),
                    accepted_at,
                ),
            )

        return PostedCollection(
            server_transaction_id=str(transaction_id),
            receipt_number=receipt_number,
            official_balance=official_balance,
            accepted_at=accepted_at,
            route_revision=next_revision,
            message=self._success_message(command.entry_type),
        )

    def _allocate_seven_by_seven_pending_event(
        self,
        cursor: Any,
        *,
        loan: dict[str, Any],
        command: CollectionCommand,
        amount: Decimal,
        previous_balance: Decimal,
    ):
        # Future Advance receipts are intentionally absent from the legacy
        # source-event replay. Once a prepaid row reaches its effective due date,
        # fail closed until the separate due-date activation slice has reconciled
        # its signed principal/interest components.
        cursor.execute(
            """
            select 1
            from lending.loan_installment_payment_allocations allocation
            join lending.collection_transactions advance_transaction
              on advance_transaction.id = allocation.transaction_id
            join lending.loan_contract_installments_operational installment
              on installment.id = allocation.installment_id
            where advance_transaction.loan_id = %s
              and advance_transaction.is_voided = false
              and allocation.allocation_basis = %s
              and installment.effective_due_date <= %s
            limit 1
            """,
            (loan["loan_id"], FUTURE_ADVANCE_BASIS, command.collection_date),
        )
        if cursor.fetchone() is not None:
            raise CollectionRejected(
                "A prepaid 7x7 Advance row has reached its effective due date, "
                "but its financial activation is not reconciled yet. Ask Management "
                "to refresh the 7x7 source-of-truth state before collecting more cash.",
                code="seven_by_seven_advance_activation_pending",
            )

        cursor.execute(
            """
            select transaction.id, transaction.collection_date, transaction.amount
            from lending.collection_transactions transaction
            where transaction.loan_id = %s
              and transaction.is_voided = false
              and transaction.amount > 0
              and (
                    transaction.entry_type = 'payment'
                    or (
                        transaction.entry_type = 'advance'
                        and not exists (
                            select 1
                            from lending.loan_installment_payment_allocations allocation
                            where allocation.transaction_id = transaction.id
                              and allocation.allocation_basis = %s
                        )
                    )
              )
            order by transaction.collection_date, transaction.accepted_at, transaction.id
            """,
            (loan["loan_id"], FUTURE_ADVANCE_BASIS),
        )
        rows = cursor.fetchall()
        historical_events = tuple(
            SevenBySevenCashEvent(
                event_id=str(row["id"]),
                collection_date=row["collection_date"],
                amount=self._money(row["amount"]),
            )
            for row in rows
        )
        payment_start = loan["date_released"] + __import__("datetime").timedelta(days=1)
        try:
            historical = allocate_seven_by_seven_payments(
                original_principal=self._money(loan["principal"]),
                daily_interest_per_1000=self._money(loan["daily_interest_per_1000"]),
                payment_start=payment_start,
                events=historical_events,
            )
        except SevenBySevenAllocationError as error:
            raise CollectionRejected(
                "Existing 7x7 collection history is not safe for mobile allocation. "
                "Use SPINA desktop and ask Management to reconcile it.",
                code="seven_by_seven_history_not_ready",
            ) from error

        if historical.closing_remaining_principal != previous_balance:
            raise CollectionRejected(
                "The 7x7 operational balance does not match the protected Desktop-parity "
                "allocation. Use SPINA desktop and ask Management to reconcile it.",
                code="seven_by_seven_balance_not_reconciled",
            )
        if historical.complete:
            raise CollectionRejected(
                "This 7x7 loan is already fully paid. Refresh the route.",
                code="loan_already_paid",
            )

        pending_event = SevenBySevenCashEvent(
            event_id=f"pending:{command.idempotency_key}",
            collection_date=command.collection_date,
            amount=amount,
        )
        try:
            result = allocate_seven_by_seven_payments(
                original_principal=self._money(loan["principal"]),
                daily_interest_per_1000=self._money(loan["daily_interest_per_1000"]),
                payment_start=payment_start,
                events=(*historical_events, pending_event),
            )
        except SevenBySevenAllocationError as error:
            raise CollectionRejected(
                "This 7x7 entry cannot be allocated without changing the protected "
                "Desktop order. Refresh the route and review the date.",
                code="seven_by_seven_allocation_conflict",
            ) from error
        return result, result.allocations[-1]
