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
from .per_loan_contract_collection import (
    PerLoanContractAwareCrossCollectorCollectionPostingBridge,
)
from .seven_by_seven_operational_allocator import (
    SEVEN_BY_SEVEN_OPERATIONAL_POLICY,
    SevenBySevenAllocationError,
    SevenBySevenCashEvent,
    allocate_seven_by_seven_payments,
)


SEVEN_BY_SEVEN_MOBILE_SETTING = "mobile_seven_by_seven_enabled"
ZERO = Decimal("0.00")


class SevenBySevenAwarePerLoanContractCollectionPostingBridge(
    PerLoanContractAwareCrossCollectorCollectionPostingBridge
):
    """Route verified 7x7 mobile cash through the protected Desktop-parity allocator.

    Regular and already-established contractual collection paths are delegated to
    the existing bridge unchanged. A 7x7 loan enters this path only when both the
    normal mobile flag and the dedicated 7x7 feature flag are explicitly enabled.
    The complete active 7x7 cash history is replayed while the loan/state rows are
    locked, its closing principal must exactly match the reconciled operational
    balance, and the pending cash event is accepted only when the canonical
    fixed-original-principal, interest-first allocator can apply it without an
    overpayment residue.
    """

    def post_collection(
        self,
        connection: Connection[Any],
        actor: ActorContext,
        command: CollectionCommand,
    ) -> PostedCollection:
        if not self._requires_seven_by_seven_path(connection, command=command):
            return super().post_collection(connection, actor, command)
        return self._post_seven_by_seven_collection(connection, actor, command)

    def _requires_seven_by_seven_path(
        self,
        connection: Connection[Any],
        *,
        command: CollectionCommand,
    ) -> bool:
        loan_id = self._uuid(command.loan_id, "loan")
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                select loan_type.calculation_mode, loan_type.settings
                from lending.loans loan
                join lending.loan_types loan_type on loan_type.id = loan.loan_type_id
                where loan.id = %s
                """,
                (loan_id,),
            )
            row = cursor.fetchone()
        if row is None or str(row["calculation_mode"] or "") != "seven_by_seven":
            return False

        settings = row["settings"] if isinstance(row["settings"], dict) else {}
        if not self._setting_enabled(settings.get("mobile_collections_enabled")):
            raise CollectionRejected(
                "7x7 mobile collection is still disabled for this loan type. "
                "Use SPINA desktop until Management enables the protected 7x7 path.",
                code="seven_by_seven_mobile_disabled",
            )
        if not self._setting_enabled(settings.get(SEVEN_BY_SEVEN_MOBILE_SETTING)):
            raise CollectionRejected(
                "7x7 mobile collection is still disabled for this loan type. "
                "Use SPINA desktop until Management enables the protected 7x7 path.",
                code="seven_by_seven_mobile_disabled",
            )
        if str(settings.get("mobile_balance_mode") or "").strip() != DIRECT_BALANCE_MODE:
            raise CollectionRejected(
                "The protected 7x7 mobile allocator is not enabled for this balance mode.",
                code="seven_by_seven_mobile_not_ready",
            )
        return True

    def _post_seven_by_seven_collection(
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
            )

            amount = self._money(command.amount or ZERO)
            pass_count_after = int(loan["pass_count"])
            last_payment_date: date | None = loan["last_payment_date"]
            advance_until_after: date | None = loan["advance_until"]
            official_balance = previous_balance
            loan_fully_paid = False
            allocation_details: dict[str, object] = {
                "seven_by_seven_policy": SEVEN_BY_SEVEN_OPERATIONAL_POLICY,
                "seven_by_seven_mobile_feature": SEVEN_BY_SEVEN_MOBILE_SETTING,
            }

            if command.entry_type is CollectionEntryType.PASS:
                self._apply_pass_rules(
                    cursor,
                    loan_id=loan_id,
                    collection_date=command.collection_date,
                )
                pass_count_after += 1
            else:
                if amount <= ZERO:
                    raise CollectionRejected(
                        "Enter a 7x7 payment amount greater than zero.",
                        code="invalid_collection_amount",
                    )
                if command.entry_type is CollectionEntryType.ADVANCE:
                    self._validate_seven_by_seven_advance(command, covered_dates)
                self._verify_covered_dates_available(
                    cursor,
                    loan_id=loan_id,
                    covered_dates=covered_dates,
                )
                result, line = self._allocate_seven_by_seven_pending_event(
                    cursor,
                    loan=loan,
                    command=command,
                    amount=amount,
                    previous_balance=previous_balance,
                )
                if not line.event_applied:
                    raise CollectionRejected(
                        "This 7x7 loan is already fully paid. Refresh the route.",
                        code="loan_already_paid",
                    )
                if line.unallocated_cash > ZERO:
                    raise CollectionRejected(
                        "The amount is higher than the exact 7x7 payoff for this date. "
                        "Refresh the route and enter the exact amount received.",
                        code="amount_exceeds_seven_by_seven_payoff",
                    )

                official_balance = result.closing_remaining_principal
                loan_fully_paid = result.complete
                pass_count_after = 0
                last_payment_date = command.collection_date
                if command.entry_type is CollectionEntryType.ADVANCE:
                    latest_selected = covered_dates[-1]
                    advance_until_after = max(
                        value
                        for value in (loan["advance_until"], latest_selected)
                        if value is not None
                    )

                allocation_details.update(
                    {
                        "seven_by_seven_payment_start": result.payment_start.isoformat(),
                        "seven_by_seven_fixed_daily_interest": str(result.fixed_daily_interest),
                        "seven_by_seven_gap_days": line.gap_days,
                        "seven_by_seven_opening_principal": str(line.opening_remaining_principal),
                        "seven_by_seven_opening_interest_arrears": str(line.opening_interest_arrears),
                        "seven_by_seven_interest_due": str(line.interest_due),
                        "seven_by_seven_interest_paid": str(line.interest_paid),
                        "seven_by_seven_principal_paid": str(line.principal_paid),
                        "seven_by_seven_closing_principal": str(line.closing_remaining_principal),
                        "seven_by_seven_closing_interest_arrears": str(line.closing_interest_arrears),
                        "seven_by_seven_complete": result.complete,
                    }
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
            if loan_fully_paid:
                cursor.execute(
                    """
                    update lending.loans
                    set status = 'paid', updated_at = %s
                    where id = %s
                    """,
                    (accepted_at, loan_id),
                )

            details = {
                "source": "gilbic_mobile",
                "loan_type_code": str(loan["loan_type_code"]),
                "loan_type_name": str(loan["loan_type_name"]),
                "calculation_mode": "seven_by_seven",
                "mobile_balance_mode": DIRECT_BALANCE_MODE,
                "state_version_before": int(loan["state_version"]),
                "state_version_after": next_version,
                "covered_dates": [value.isoformat() for value in covered_dates],
                **allocation_details,
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
                    command.advance_from,
                    command.advance_until,
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
            for covered_date in covered_dates:
                cursor.execute(
                    """
                    insert into lending.collection_covered_dates (
                        transaction_id, loan_id, covered_date
                    ) values (%s, %s, %s)
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
                    f"collection.mobile.{command.entry_type.value}",
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
                            "covered_dates": [
                                value.isoformat() for value in covered_dates
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

    def _revalidate_seven_by_seven_mode(self, loan: dict[str, Any]) -> None:
        if str(loan["calculation_mode"] or "") != "seven_by_seven":
            raise CollectionConflict(
                "The loan type changed while this 7x7 collection was being saved. "
                "Refresh the route.",
                code="seven_by_seven_mode_changed",
            )
        settings = loan["settings"] if isinstance(loan["settings"], dict) else {}
        if not self._setting_enabled(settings.get("mobile_collections_enabled")) or not self._setting_enabled(
            settings.get(SEVEN_BY_SEVEN_MOBILE_SETTING)
        ):
            raise CollectionConflict(
                "7x7 mobile collection was disabled while this entry was being saved. "
                "Refresh the route.",
                code="seven_by_seven_mobile_disabled",
            )
        if str(settings.get("mobile_balance_mode") or "").strip() != DIRECT_BALANCE_MODE:
            raise CollectionConflict(
                "The 7x7 mobile balance mode changed. Refresh the route.",
                code="seven_by_seven_mobile_not_ready",
            )
        if self._money(loan["daily_interest_per_1000"]) <= ZERO:
            raise CollectionRejected(
                "The 7x7 daily interest basis is missing. Use SPINA desktop and ask "
                "Management to review this loan type.",
                code="seven_by_seven_interest_basis_missing",
            )

    @staticmethod
    def _seven_by_seven_covered_dates(command: CollectionCommand) -> tuple[date, ...]:
        if command.entry_type is CollectionEntryType.PASS:
            return ()
        selected = tuple(sorted(set(command.covered_dates)))
        if command.entry_type is CollectionEntryType.PAYMENT:
            if selected and selected != (command.collection_date,):
                raise CollectionRejected(
                    "A normal 7x7 payment may cover only its collection date. "
                    "Use exact covered-date payment for multiple dates.",
                    code="seven_by_seven_payment_coverage_invalid",
                )
            return (command.collection_date,)
        return selected

    @staticmethod
    def _validate_seven_by_seven_advance(
        command: CollectionCommand,
        covered_dates: tuple[date, ...],
    ) -> None:
        if not covered_dates:
            raise CollectionRejected(
                "Choose at least one exact covered date for this 7x7 payment.",
                code="covered_date_required",
            )
        if command.advance_from != covered_dates[0] or command.advance_until != covered_dates[-1]:
            raise CollectionRejected(
                "The first and last 7x7 covered dates must match the exact selected dates.",
                code="seven_by_seven_advance_bounds_mismatch",
            )

    @staticmethod
    def _verify_seven_by_seven_date_available(
        cursor: Any,
        *,
        loan_id: UUID,
        collection_date: date,
    ) -> None:
        cursor.execute(
            """
            select id, entry_type
            from lending.collection_transactions
            where loan_id = %s
              and collection_date = %s
              and is_voided = false
            order by accepted_at desc, id desc
            limit 1
            """,
            (loan_id, collection_date),
        )
        existing = cursor.fetchone()
        if existing is not None:
            raise CollectionConflict(
                "A 7x7 collection is already recorded for this loan on this date. "
                "Refresh the route instead of creating a second entry.",
                code="seven_by_seven_date_already_recorded",
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
        cursor.execute(
            """
            select id, collection_date, amount
            from lending.collection_transactions
            where loan_id = %s
              and is_voided = false
              and entry_type in ('payment', 'advance')
              and amount > 0
            order by collection_date, id
            """,
            (loan["loan_id"],),
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
