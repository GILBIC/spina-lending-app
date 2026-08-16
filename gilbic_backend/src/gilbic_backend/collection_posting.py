from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
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

from .receipt_application import (
    ReceiptApplicationError,
    ReceiptApplicationPlan,
    plan_receipt_application,
)


MONEY = Decimal("0.01")
DIRECT_BALANCE_MODE = "direct_remaining_balance"


class PostgresCollectionPostingBridge:
    """Apply one official collection inside the executor's transaction.

    The idempotency executor opens and owns the PostgreSQL transaction. This
    bridge locks the loan and device sequence, validates route ownership, updates
    the authoritative collection state, creates an immutable transaction and
    receipt, records exact covered dates and an audit event, and returns the
    replayable result. Any exception rolls every write back together.

    ``collection_transactions.amount`` is the real custody receipt. For normal
    PAYMENT, only the currently eligible scheduled amount reduces the loan; a
    legitimate excess receipt remains ``unallocated_amount`` instead of being
    rejected, discarded, or silently turned into ADV. Explicit voluntary-extra
    intent may apply beyond the current scheduled amount. Contract-aware
    subclasses override the scheduled-amount lookup with signed-schedule truth.
    """

    def post_collection(
        self,
        connection: Connection[Any],
        actor: ActorContext,
        command: CollectionCommand,
    ) -> PostedCollection:
        collector_user_id = self._uuid(actor.account_id, "authenticated collector")
        registered_device_id = self._uuid(
            actor.storage_device_id,
            "registered device",
        )
        loan_id = self._uuid(command.loan_id, "loan")
        client_id = self._uuid(command.client_id, "client")
        route_entry_id = self._uuid(command.route_entry_id, "route entry")
        covered_dates = self._covered_dates(command)

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
                    l.id as loan_id,
                    l.client_id,
                    l.status as loan_status,
                    l.principal,
                    l.daily_amount,
                    c.status as client_status,
                    c.area,
                    lt.code as loan_type_code,
                    lt.name as loan_type_name,
                    lt.calculation_mode,
                    lt.settings,
                    s.remaining_balance,
                    s.pass_count,
                    s.last_payment_date,
                    s.advance_until,
                    s.note,
                    s.is_reconciled,
                    s.state_version
                from lending.loans l
                join lending.clients c on c.id = l.client_id
                join lending.loan_types lt on lt.id = l.loan_type_id
                join lending.loan_collection_state s on s.loan_id = l.id
                where l.id = %s and c.id = %s
                for update of l, c, s
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

            previous_balance = self._money(loan["remaining_balance"])
            if previous_balance <= Decimal("0"):
                raise CollectionRejected(
                    "This loan is already fully paid.",
                    code="loan_already_paid",
                )

            settings = loan["settings"] if isinstance(loan["settings"], dict) else {}
            if not self._setting_enabled(settings.get("mobile_collections_enabled")):
                raise CollectionRejected(
                    "Mobile collection is not enabled for this loan type yet. "
                    "Please use the SPINA desktop app.",
                    code="loan_type_mobile_disabled",
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

            cash_amount = self._money(command.amount or Decimal("0"))
            applied_amount = Decimal("0.00")
            unallocated_amount = Decimal("0.00")
            allocation_state = "not_applicable"
            pass_count_after = int(loan["pass_count"])
            last_payment_date: date | None = loan["last_payment_date"]
            advance_until_after: date | None = loan["advance_until"]
            official_balance = previous_balance
            dates_to_mark_covered: tuple[date, ...] = ()

            if command.entry_type is CollectionEntryType.PASS:
                self._apply_pass_rules(
                    cursor,
                    loan_id=loan_id,
                    collection_date=command.collection_date,
                )
                pass_count_after += 1
            else:
                balance_mode = str(settings.get("mobile_balance_mode") or "").strip()
                if balance_mode != DIRECT_BALANCE_MODE:
                    raise CollectionRejected(
                        "This loan's payment calculation is not ready for mobile "
                        "collection. Please use the SPINA desktop app.",
                        code="loan_calculation_not_ready",
                    )

                if command.entry_type is CollectionEntryType.PAYMENT:
                    scheduled_remaining = self._scheduled_payment_remaining(
                        cursor,
                        loan=loan,
                        command=command,
                    )
                    maximum_immediately_applicable = (
                        previous_balance
                        if command.payment_allocation_intent
                        is PaymentAllocationIntent.VOLUNTARY_EXTRA
                        else min(previous_balance, scheduled_remaining)
                    )
                    plan = self._plan_receipt_application(
                        cash_amount=cash_amount,
                        maximum_immediately_applicable=maximum_immediately_applicable,
                        allocation_intent=(
                            "voluntary_extra"
                            if command.payment_allocation_intent
                            is PaymentAllocationIntent.VOLUNTARY_EXTRA
                            else "scheduled"
                        ),
                    )
                    applied_amount = plan.applied_amount
                    unallocated_amount = plan.unallocated_amount
                    allocation_state = plan.allocation_state
                    scheduled_target = min(previous_balance, scheduled_remaining)
                    if (
                        covered_dates
                        and scheduled_target > Decimal("0.00")
                        and applied_amount >= scheduled_target
                    ):
                        dates_to_mark_covered = covered_dates
                else:
                    if not covered_dates:
                        raise CollectionRejected(
                            "Choose at least one covered date.",
                            code="covered_date_required",
                        )
                    self._verify_covered_dates_available(
                        cursor,
                        loan_id=loan_id,
                        covered_dates=covered_dates,
                    )
                    plan = self._plan_receipt_application(
                        cash_amount=cash_amount,
                        maximum_immediately_applicable=previous_balance,
                        allocation_intent="advance",
                    )
                    applied_amount = plan.applied_amount
                    unallocated_amount = plan.unallocated_amount
                    allocation_state = plan.allocation_state
                    # Preserve the established legacy ADV coverage contract. The
                    # contract-aware path separately verifies exact contractual
                    # dates and amounts before it reaches this bridge.
                    dates_to_mark_covered = covered_dates

                official_balance = self._money(previous_balance - applied_amount)
                if applied_amount > Decimal("0.00"):
                    pass_count_after = 0
                    last_payment_date = command.collection_date
                    if command.entry_type is CollectionEntryType.ADVANCE:
                        latest_selected = covered_dates[-1]
                        advance_until_after = max(
                            date_value
                            for date_value in (loan["advance_until"], latest_selected)
                            if date_value is not None
                        )

            note_after = command.note.strip() or str(loan["note"] or "")
            next_version = int(loan["state_version"]) + 1
            next_revision = self._route_revision(
                loan_id=loan_id,
                state_version=next_version,
            )
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
            if official_balance == Decimal("0"):
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
                "calculation_mode": str(loan["calculation_mode"]),
                "mobile_balance_mode": str(settings.get("mobile_balance_mode") or ""),
                "state_version_before": int(loan["state_version"]),
                "state_version_after": next_version,
                "covered_dates": [value.isoformat() for value in dates_to_mark_covered],
                "payment_allocation_intent": command.payment_allocation_intent.value,
                "cash_received_amount": str(cash_amount),
                "applied_amount": str(applied_amount),
                "unallocated_amount": str(unallocated_amount),
                "allocation_state": allocation_state,
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
                    applied_amount,
                    unallocated_amount,
                    allocation_state,
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
                    %s, %s, %s, %s, %s, %s
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
                    cash_amount,
                    applied_amount,
                    unallocated_amount,
                    allocation_state,
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
            for covered_date in dates_to_mark_covered:
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
                            "amount": str(cash_amount),
                            "cash_received_amount": str(cash_amount),
                            "applied_amount": str(applied_amount),
                            "unallocated_amount": str(unallocated_amount),
                            "allocation_state": allocation_state,
                            "payment_allocation_intent": (
                                command.payment_allocation_intent.value
                            ),
                            "official_balance": str(official_balance),
                            "covered_dates": [
                                value.isoformat() for value in dates_to_mark_covered
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
            message=self._success_message(
                command.entry_type,
                unallocated_amount=unallocated_amount,
            ),
        )

    @staticmethod
    def _uuid(value: str, label: str) -> UUID:
        try:
            return UUID(str(value).strip())
        except (ValueError, AttributeError) as exc:
            raise CollectionRejected(
                f"The {label} information is invalid. Refresh and try again.",
                code="invalid_collection_reference",
            ) from exc

    @staticmethod
    def _money(value: Decimal | int | str) -> Decimal:
        return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)

    @staticmethod
    def _setting_enabled(value: object) -> bool:
        if value is True:
            return True
        return str(value or "").strip().lower() in {"true", "1", "yes", "on"}

    @staticmethod
    def _route_revision(*, loan_id: UUID, state_version: int) -> str:
        return f"loan:{loan_id}:v{state_version}"

    @staticmethod
    def _covered_dates(command: CollectionCommand) -> tuple[date, ...]:
        selected = tuple(sorted(set(command.covered_dates)))
        if selected:
            return selected
        if command.entry_type is CollectionEntryType.PAYMENT:
            return (command.collection_date,)
        if (
            command.entry_type is CollectionEntryType.ADVANCE
            and command.advance_from is not None
            and command.advance_until is not None
        ):
            days = (command.advance_until - command.advance_from).days
            return tuple(
                command.advance_from + timedelta(days=offset)
                for offset in range(days + 1)
            )
        return ()

    def _scheduled_payment_remaining(
        self,
        cursor: Any,
        *,
        loan: dict[str, Any],
        command: CollectionCommand,
    ) -> Decimal:
        """Return the legacy scheduled amount still eligible on this date.

        A completed covered-date claim means today's legacy obligation is already
        satisfied. Otherwise aggregate distinct partial PAYMENT receipts by their
        *applied* amount so a second real receipt can finish the same day without
        being treated as a duplicate. Contract-aware subclasses replace this with
        signed-installment truth.
        """

        cursor.execute(
            """
            select 1
            from lending.collection_covered_dates
            where loan_id = %s and covered_date = %s
            limit 1
            """,
            (loan["loan_id"], command.collection_date),
        )
        if cursor.fetchone():
            return Decimal("0.00")

        cursor.execute(
            """
            select coalesce(sum(applied_amount), 0)::numeric(18,2) as applied_amount
            from lending.collection_transactions
            where loan_id = %s
              and collection_date = %s
              and entry_type = 'payment'
              and is_voided = false
            """,
            (loan["loan_id"], command.collection_date),
        )
        row = cursor.fetchone()
        already_applied = self._money(
            row["applied_amount"] if row and row["applied_amount"] is not None else 0
        )
        scheduled = self._money(loan["daily_amount"])
        return max(Decimal("0.00"), self._money(scheduled - already_applied))

    @staticmethod
    def _plan_receipt_application(
        *,
        cash_amount: Decimal,
        maximum_immediately_applicable: Decimal,
        allocation_intent: str,
    ) -> ReceiptApplicationPlan:
        try:
            return plan_receipt_application(
                cash_received_amount=cash_amount,
                maximum_immediately_applicable=maximum_immediately_applicable,
                allocation_intent=allocation_intent,  # type: ignore[arg-type]
            )
        except ReceiptApplicationError as error:
            raise CollectionRejected(
                str(error),
                code="receipt_application_invalid",
            ) from error

    @staticmethod
    def _lock_device_sequence(
        cursor: Any,
        *,
        registered_device_id: UUID,
        device_sequence: int,
    ) -> None:
        cursor.execute(
            "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"gilbic-device-sequence:{registered_device_id}:{device_sequence}",),
        )

    @staticmethod
    def _lock_loan_date(
        cursor: Any,
        *,
        loan_id: UUID,
        collection_date: date,
    ) -> None:
        cursor.execute(
            "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"gilbic-loan-date:{loan_id}:{collection_date.isoformat()}",),
        )

    @staticmethod
    def _verify_device(
        cursor: Any,
        *,
        collector_user_id: UUID,
        registered_device_id: UUID,
    ) -> None:
        cursor.execute(
            """
            select 1
            from core.devices
            where id = %s and user_id = %s and status = 'active'
            """,
            (registered_device_id, collector_user_id),
        )
        if not cursor.fetchone():
            raise CollectionRejected(
                "This device is no longer approved. Sign in again or ask Management "
                "to review the device.",
                code="device_not_registered",
            )

    @staticmethod
    def _verify_device_sequence_available(
        cursor: Any,
        *,
        registered_device_id: UUID,
        device_sequence: int,
    ) -> None:
        cursor.execute(
            """
            select id
            from lending.collection_transactions
            where registered_device_id = %s and device_sequence = %s
            limit 1
            """,
            (registered_device_id, device_sequence),
        )
        if cursor.fetchone():
            raise CollectionConflict(
                "This device entry number was already used. Refresh the route and "
                "try again.",
                code="device_sequence_reused",
            )

    @staticmethod
    def _validate_loan_and_route(
        cursor: Any,
        *,
        loan: dict[str, Any],
        collector_user_id: UUID,
        command: CollectionCommand,
    ) -> None:
        if loan["loan_status"] != "active":
            raise CollectionRejected(
                "This loan is no longer active. Refresh the route.",
                code="loan_not_active",
            )
        if loan["client_status"] != "active":
            raise CollectionRejected(
                "This client is not active. Refresh the route.",
                code="client_not_active",
            )
        if not loan["is_reconciled"]:
            raise CollectionRejected(
                "This loan is still being checked against SPINA records. Please use "
                "the desktop app for now.",
                code="loan_state_not_reconciled",
            )
        cursor.execute(
            """
            select 1
            from lending.collector_area_assignments
            where collector_user_id = %s
              and is_active = true
              and lower(btrim(area)) = lower(btrim(%s))
            limit 1
            """,
            (collector_user_id, loan["area"] or ""),
        )
        if not cursor.fetchone():
            raise CollectionRejected(
                "This client is not assigned to your route. Refresh the route.",
                code="route_not_assigned",
            )
        last_payment_date: date | None = loan["last_payment_date"]
        if last_payment_date is not None and command.collection_date < last_payment_date:
            raise CollectionRejected(
                "This date is earlier than the latest recorded payment. Refresh the "
                "route and review the entry.",
                code="collection_date_out_of_order",
            )

    @staticmethod
    def _verify_covered_dates_available(
        cursor: Any,
        *,
        loan_id: UUID,
        covered_dates: tuple[date, ...],
    ) -> None:
        if not covered_dates:
            return
        cursor.execute(
            """
            select covered_date
            from lending.collection_covered_dates
            where loan_id = %s
              and covered_date = any(%s)
            order by covered_date
            limit 1
            """,
            (loan_id, list(covered_dates)),
        )
        overlap = cursor.fetchone()
        if overlap:
            value = overlap["covered_date"]
            raise CollectionConflict(
                f"{value.isoformat()} is already covered by another payment.",
                code="covered_date_already_used",
            )

    @staticmethod
    def _apply_pass_rules(
        cursor: Any,
        *,
        loan_id: UUID,
        collection_date: date,
    ) -> None:
        cursor.execute(
            """
            select transaction_id
            from lending.collection_covered_dates
            where loan_id = %s and covered_date = %s
            limit 1
            """,
            (loan_id, collection_date),
        )
        if cursor.fetchone():
            raise CollectionRejected(
                "This date is already covered by a payment, so unable-to-pay is not needed.",
                code="covered_date_already_used",
            )
        cursor.execute(
            """
            select id
            from lending.collection_transactions
            where loan_id = %s
              and collection_date = %s
              and entry_type = 'pass'
            limit 1
            """,
            (loan_id, collection_date),
        )
        if cursor.fetchone():
            raise CollectionConflict(
                "Unable-to-pay was already recorded for this client on this date.",
                code="pass_already_recorded",
            )

    @staticmethod
    def _next_receipt_number(cursor: Any, *, collection_date: date) -> str:
        cursor.execute("select nextval('lending.collection_receipt_sequence')")
        sequence = int(cursor.fetchone()["nextval"])
        return f"GBC-{collection_date:%Y%m%d}-{sequence:08d}"

    @staticmethod
    def _success_message(
        entry_type: CollectionEntryType,
        *,
        unallocated_amount: Decimal = Decimal("0.00"),
    ) -> str:
        if unallocated_amount > Decimal("0.00"):
            return (
                f"Payment saved. {unallocated_amount:.2f} is unallocated and needs review."
            )
        if entry_type is CollectionEntryType.ADVANCE:
            return "Covered-date payment saved."
        if entry_type is CollectionEntryType.PASS:
            return "Unable-to-pay reason saved."
        return "Payment saved."
