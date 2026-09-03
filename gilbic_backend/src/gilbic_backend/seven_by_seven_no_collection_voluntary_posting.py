from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
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
    PaymentAllocationIntent,
    PostedCollection,
)
from spina_mobile_collections.service import CollectionConflict, CollectionRejected

from .collection_posting import DIRECT_BALANCE_MODE
from .seven_by_seven_advance_activation import (
    SevenBySevenAdvanceActivationError,
    replay_verified_seven_by_seven_financial_state,
)
from .seven_by_seven_advance_activation_posting import (
    MaturingVerifiedAdvanceSevenBySevenCollectionPostingBridge,
)
from .seven_by_seven_collection_posting import SEVEN_BY_SEVEN_MOBILE_SETTING
from .seven_by_seven_no_collection_voluntary import (
    SevenBySevenNoCollectionVoluntaryError,
)
from .seven_by_seven_no_collection_voluntary_context import (
    NoCollectionVoluntaryPostingContext,
    SevenBySevenNoCollectionVoluntaryContextError,
    load_no_collection_voluntary_posting_context,
)
from .seven_by_seven_no_collection_voluntary_evidence import (
    SevenBySevenNoCollectionVoluntaryEvidenceError,
    plan_no_collection_completion_restoration_from_database,
    store_no_collection_voluntary_allocations,
    store_no_collection_voluntary_completion,
)
from .seven_by_seven_no_collection_voluntary_financial import (
    SevenBySevenNoCollectionVoluntaryFinancialError,
    project_no_collection_voluntary_financial_state,
)
from .seven_by_seven_operational_allocator import SEVEN_BY_SEVEN_OPERATIONAL_POLICY, ZERO
from .seven_by_seven_schedule_allocation import money


class NoCollectionVoluntarySevenBySevenCollectionPostingBridge(
    MaturingVerifiedAdvanceSevenBySevenCollectionPostingBridge
):
    """Post an explicit borrower-directed 7x7 payment on a Management NC date.

    Non-NC intents delegate unchanged. The NC path repeats the normal protected
    Collector/device/route/state locks, proves the exact active Management No
    Collection source and signed installment, allocates older Past Due first,
    and then writes one immutable receipt plus complete installment evidence.

    Partial affected-installment cash is custody cash today but uses the existing
    protected future-prepayment basis so it remains financially deferred while the
    NC shift/interest holiday stays active. Full completion stores a separate
    immutable ``voluntary_completion`` adjustment, restores exactly that source
    NC shift, suppresses that one interest holiday, and preserves the original
    Management declaration as history.

    Before returning success, the entire verified 7x7 financial history is replayed
    inside the same database transaction. Any balance, holiday, or unapplied-cash
    mismatch raises and rolls the transaction back rather than accepting drift.
    """

    def post_collection(
        self,
        connection: Connection[Any],
        actor: ActorContext,
        command: CollectionCommand,
    ) -> PostedCollection:
        if (
            command.payment_allocation_intent
            is not PaymentAllocationIntent.NO_COLLECTION_VOLUNTARY
        ):
            return super().post_collection(connection, actor, command)

        if command.entry_type is not CollectionEntryType.PAYMENT:
            raise CollectionRejected(
                "No Collection voluntary intent is valid only for a Payment receipt.",
                code="seven_by_seven_no_collection_voluntary_payment_required",
            )

        if not self._requires_seven_by_seven_path(connection, command=command):
            raise CollectionRejected(
                "No Collection voluntary intent is valid only for a protected 7x7 loan.",
                code="seven_by_seven_no_collection_voluntary_loan_required",
            )

        return self._post_no_collection_voluntary(connection, actor, command)

    def _post_no_collection_voluntary(
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
            loan = self._lock_no_collection_loan(
                cursor,
                loan_id=loan_id,
                client_id=client_id,
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
                    "The loan changed after this route was loaded. Refresh the route and review the entry.",
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
                    "Enter a 7x7 voluntary No Collection amount greater than zero.",
                    code="invalid_collection_amount",
                )

            context = self._load_no_collection_context(
                cursor,
                loan_id=loan_id,
                command=command,
                amount=amount,
            )
            restoration_shifts = ()
            if context.plan.status == "full_voluntary_completion":
                try:
                    restoration_shifts = (
                        plan_no_collection_completion_restoration_from_database(
                            cursor,
                            schedule_id=context.schedule_id,
                            source_no_collection_date=command.collection_date,
                        )
                    )
                except SevenBySevenNoCollectionVoluntaryEvidenceError as error:
                    raise CollectionRejected(str(error), code=error.code) from error

            payment_start = loan["date_released"] + timedelta(days=1)
            try:
                baseline = replay_verified_seven_by_seven_financial_state(
                    cursor,
                    loan_id=loan_id,
                    original_principal=money(loan["principal"]),
                    daily_interest_per_1000=money(loan["daily_interest_per_1000"]),
                    payment_start=payment_start,
                    through_date=command.collection_date,
                )
            except SevenBySevenAdvanceActivationError as error:
                raise CollectionRejected(str(error), code=error.code) from error

            transaction_id = uuid4()
            try:
                projection = project_no_collection_voluntary_financial_state(
                    baseline=baseline,
                    plan=context.plan,
                    collection_date=command.collection_date,
                    original_principal=money(loan["principal"]),
                    daily_interest_per_1000=money(loan["daily_interest_per_1000"]),
                    payment_start=payment_start,
                    previous_balance=previous_balance,
                    affected_installment_id=context.affected_installment.installment_id,
                    affected_deferred_prepaid_amount=(
                        context.affected_deferred_prepaid_amount
                    ),
                    pending_event_id=str(transaction_id),
                )
            except SevenBySevenNoCollectionVoluntaryFinancialError as error:
                raise CollectionRejected(str(error), code=error.code) from error

            official_balance = projection.result.closing_remaining_principal
            loan_fully_paid = projection.result.complete
            pass_count_after = 0
            last_payment_date = command.collection_date
            advance_until_after: date | None = loan["advance_until"]
            note_after = command.note.strip() or str(loan["note"] or "")
            next_version = int(loan["state_version"]) + 1
            next_revision = self._route_revision(
                loan_id=loan_id,
                state_version=next_version,
            )
            accepted_at = datetime.now(timezone.utc)
            receipt_number = self._next_receipt_number(
                cursor,
                collection_date=command.collection_date,
            )

            allocation_details = self._allocation_details(
                loan=loan,
                context=context,
                projection=projection,
            )
            self._update_collection_state(
                cursor,
                loan_id=loan_id,
                official_balance=official_balance,
                pass_count_after=pass_count_after,
                last_payment_date=last_payment_date,
                advance_until_after=advance_until_after,
                note_after=note_after,
                next_version=next_version,
                accepted_at=accepted_at,
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
                "payment_allocation_intent": (
                    PaymentAllocationIntent.NO_COLLECTION_VOLUNTARY.value
                ),
                "covered_dates": [command.collection_date.isoformat()],
                **allocation_details,
            }
            self._insert_collection_transaction(
                cursor,
                transaction_id=transaction_id,
                command=command,
                loan_id=loan_id,
                client_id=client_id,
                collector_user_id=collector_user_id,
                registered_device_id=registered_device_id,
                route_entry_id=route_entry_id,
                amount=amount,
                accepted_at=accepted_at,
                previous_balance=previous_balance,
                official_balance=official_balance,
                pass_count_after=pass_count_after,
                advance_until_after=advance_until_after,
                receipt_number=receipt_number,
                details=details,
            )

            try:
                store_no_collection_voluntary_allocations(
                    cursor,
                    transaction_id=transaction_id,
                    actor_user_id=collector_user_id,
                    source_no_collection_adjustment_id=(
                        context.source_no_collection_adjustment_id
                    ),
                    plan=context.plan,
                )
            except SevenBySevenNoCollectionVoluntaryEvidenceError as error:
                raise CollectionRejected(str(error), code=error.code) from error

            completion_adjustment_id: UUID | None = None
            if context.plan.status == "full_voluntary_completion":
                try:
                    completion_adjustment_id = store_no_collection_voluntary_completion(
                        cursor,
                        loan_id=loan_id,
                        schedule_id=context.schedule_id,
                        actor_user_id=collector_user_id,
                        source_no_collection_adjustment_id=(
                            context.source_no_collection_adjustment_id
                        ),
                        no_collection_date=command.collection_date,
                        expected_operational_version=context.operational_version,
                        transaction_id=transaction_id,
                        affected_installment_id=(
                            context.affected_installment.installment_id
                        ),
                        current_receipt_completion_amount=(
                            context.plan.affected_cash_amount
                        ),
                        prior_payment_evidence_amount=(
                            context.plan.affected_prepaid_before
                        ),
                        restoration_shifts=restoration_shifts,
                    )
                except SevenBySevenNoCollectionVoluntaryEvidenceError as error:
                    raise CollectionRejected(str(error), code=error.code) from error

            cursor.execute(
                """
                insert into lending.collection_covered_dates (
                    transaction_id, loan_id, covered_date
                ) values (%s, %s, %s)
                on conflict (loan_id, covered_date) do nothing
                """,
                (transaction_id, loan_id, command.collection_date),
            )

            self._verify_post_write_replay(
                cursor,
                loan=loan,
                loan_id=loan_id,
                command=command,
                payment_start=payment_start,
                expected_balance=official_balance,
                keep_interest_holiday=context.plan.keep_interest_holiday,
            )
            self._insert_no_collection_audit(
                cursor,
                collector_user_id=collector_user_id,
                transaction_id=transaction_id,
                loan_id=loan_id,
                client_id=client_id,
                receipt_number=receipt_number,
                amount=amount,
                official_balance=official_balance,
                context=context,
                completion_adjustment_id=completion_adjustment_id,
                accepted_at=accepted_at,
            )

        return PostedCollection(
            server_transaction_id=str(transaction_id),
            receipt_number=receipt_number,
            official_balance=official_balance,
            accepted_at=accepted_at,
            route_revision=next_revision,
            message=self._success_message(command.entry_type),
        )

    @staticmethod
    def _load_no_collection_context(
        cursor: Any,
        *,
        loan_id: UUID,
        command: CollectionCommand,
        amount: Decimal,
    ) -> NoCollectionVoluntaryPostingContext:
        try:
            return load_no_collection_voluntary_posting_context(
                cursor,
                loan_id=loan_id,
                collection_date=command.collection_date,
                transaction_amount=amount,
            )
        except (
            SevenBySevenNoCollectionVoluntaryContextError,
            SevenBySevenNoCollectionVoluntaryError,
        ) as error:
            raise CollectionRejected(str(error), code=error.code) from error

    @staticmethod
    def _lock_no_collection_loan(
        cursor: Any,
        *,
        loan_id: UUID,
        client_id: UUID,
    ) -> dict[str, Any]:
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
        if loan is None:
            raise CollectionRejected(
                "This loan could not be found. Refresh the route.",
                code="loan_not_found",
            )
        return loan

    @staticmethod
    def _update_collection_state(
        cursor: Any,
        *,
        loan_id: UUID,
        official_balance: Decimal,
        pass_count_after: int,
        last_payment_date: date,
        advance_until_after: date | None,
        note_after: str,
        next_version: int,
        accepted_at: datetime,
    ) -> None:
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
        if cursor.rowcount != 1:
            raise CollectionRejected(
                "The 7x7 collection state could not be updated exactly once.",
                code="seven_by_seven_no_collection_voluntary_state_conflict",
            )

    @staticmethod
    def _insert_collection_transaction(
        cursor: Any,
        *,
        transaction_id: UUID,
        command: CollectionCommand,
        loan_id: UUID,
        client_id: UUID,
        collector_user_id: UUID,
        registered_device_id: UUID,
        route_entry_id: UUID,
        amount: Decimal,
        accepted_at: datetime,
        previous_balance: Decimal,
        official_balance: Decimal,
        pass_count_after: int,
        advance_until_after: date | None,
        receipt_number: str,
        details: dict[str, object],
    ) -> None:
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

    @staticmethod
    def _allocation_details(
        *,
        loan: dict[str, Any],
        context: NoCollectionVoluntaryPostingContext,
        projection: Any,
    ) -> dict[str, object]:
        details: dict[str, object] = {
            "seven_by_seven_policy": SEVEN_BY_SEVEN_OPERATIONAL_POLICY,
            "seven_by_seven_mobile_feature": SEVEN_BY_SEVEN_MOBILE_SETTING,
            "seven_by_seven_schedule_allocation_state": (
                "verified_no_collection_voluntary_allocated"
            ),
            "seven_by_seven_no_collection_plan_status": context.plan.status,
            "seven_by_seven_no_collection_source_adjustment_id": str(
                context.source_no_collection_adjustment_id
            ),
            "seven_by_seven_no_collection_schedule_id": str(context.schedule_id),
            "seven_by_seven_no_collection_operational_version_before": (
                context.operational_version
            ),
            "seven_by_seven_no_collection_past_due_cash": str(
                context.plan.past_due_cash_amount
            ),
            "seven_by_seven_no_collection_affected_cash": str(
                context.plan.affected_cash_amount
            ),
            "seven_by_seven_no_collection_affected_prepaid_before": str(
                context.plan.affected_prepaid_before
            ),
            "seven_by_seven_no_collection_deferred_prepaid_before": str(
                context.affected_deferred_prepaid_amount
            ),
            "seven_by_seven_no_collection_shifted_prepayment": str(
                context.plan.shifted_prepayment_amount
            ),
            "seven_by_seven_no_collection_keep_shift": (
                context.plan.keep_no_collection_shift
            ),
            "seven_by_seven_no_collection_keep_interest_holiday": (
                context.plan.keep_interest_holiday
            ),
            "seven_by_seven_payment_start": (
                loan["date_released"] + timedelta(days=1)
            ).isoformat(),
            "seven_by_seven_fixed_daily_interest": str(
                projection.result.fixed_daily_interest
            ),
            "seven_by_seven_complete": projection.result.complete,
        }
        line = projection.pending_line
        if line is not None:
            details.update(
                {
                    "seven_by_seven_gap_days": line.gap_days,
                    "seven_by_seven_opening_principal": str(
                        line.opening_remaining_principal
                    ),
                    "seven_by_seven_opening_interest_arrears": str(
                        line.opening_interest_arrears
                    ),
                    "seven_by_seven_interest_due": str(line.interest_due),
                    "seven_by_seven_interest_paid": str(line.interest_paid),
                    "seven_by_seven_principal_paid": str(line.principal_paid),
                    "seven_by_seven_closing_principal": str(
                        line.closing_remaining_principal
                    ),
                    "seven_by_seven_closing_interest_arrears": str(
                        line.closing_interest_arrears
                    ),
                }
            )
        return details

    @staticmethod
    def _verify_post_write_replay(
        cursor: Any,
        *,
        loan: dict[str, Any],
        loan_id: UUID,
        command: CollectionCommand,
        payment_start: date,
        expected_balance: Decimal,
        keep_interest_holiday: bool,
    ) -> None:
        try:
            replay = replay_verified_seven_by_seven_financial_state(
                cursor,
                loan_id=loan_id,
                original_principal=money(loan["principal"]),
                daily_interest_per_1000=money(loan["daily_interest_per_1000"]),
                payment_start=payment_start,
                through_date=command.collection_date,
            )
        except SevenBySevenAdvanceActivationError as error:
            raise CollectionRejected(str(error), code=error.code) from error

        if replay.result.closing_remaining_principal != expected_balance:
            raise CollectionRejected(
                "The written No Collection receipt does not exactly match protected 7x7 financial replay. The transaction was rejected.",
                code="seven_by_seven_no_collection_voluntary_post_write_mismatch",
            )
        holiday_active = command.collection_date in replay.interest_holiday_dates
        if holiday_active != keep_interest_holiday:
            raise CollectionRejected(
                "The written No Collection receipt does not match the required interest-holiday state. The transaction was rejected.",
                code="seven_by_seven_no_collection_voluntary_holiday_mismatch",
            )

    @staticmethod
    def _insert_no_collection_audit(
        cursor: Any,
        *,
        collector_user_id: UUID,
        transaction_id: UUID,
        loan_id: UUID,
        client_id: UUID,
        receipt_number: str,
        amount: Decimal,
        official_balance: Decimal,
        context: NoCollectionVoluntaryPostingContext,
        completion_adjustment_id: UUID | None,
        accepted_at: datetime,
    ) -> None:
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
                "collection.mobile.payment.no_collection_voluntary",
                transaction_id,
                Jsonb(
                    {
                        "loan_id": str(loan_id),
                        "client_id": str(client_id),
                        "receipt_number": receipt_number,
                        "amount": str(amount),
                        "official_balance": str(official_balance),
                        "plan_status": context.plan.status,
                        "source_no_collection_adjustment_id": str(
                            context.source_no_collection_adjustment_id
                        ),
                        "affected_installment_id": (
                            context.affected_installment.installment_id
                        ),
                        "past_due_cash_amount": str(
                            context.plan.past_due_cash_amount
                        ),
                        "affected_cash_amount": str(
                            context.plan.affected_cash_amount
                        ),
                        "shifted_prepayment_amount": str(
                            context.plan.shifted_prepayment_amount
                        ),
                        "completion_adjustment_id": (
                            str(completion_adjustment_id)
                            if completion_adjustment_id is not None
                            else None
                        ),
                    }
                ),
                accepted_at,
            ),
        )