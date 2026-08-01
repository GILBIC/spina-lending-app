from __future__ import annotations

from datetime import date, datetime, timezone
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
    PostedCollection,
)
from spina_mobile_collections.service import CollectionConflict, CollectionRejected


MONEY = Decimal("0.01")
DIRECT_BALANCE_MODE = "direct_remaining_balance"


class PostgresCollectionPostingBridge:
    """Apply one official collection inside the executor's transaction.

    The idempotency executor opens and owns the PostgreSQL transaction. This
    bridge locks the loan and device sequence, validates route ownership, updates
    the authoritative collection state, creates an immutable transaction and
    receipt, records an audit event, and returns the replayable result. Any
    exception rolls every write back together.
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

            amount = self._money(command.amount or Decimal("0"))
            pass_count_after = int(loan["pass_count"])
            last_payment_date: date | None = loan["last_payment_date"]
            advance_until_after: date | None = loan["advance_until"]
            official_balance = previous_balance

            if command.entry_type is CollectionEntryType.PASS:
                self._apply_pass_rules(
                    cursor,
                    loan_id=loan_id,
                    collection_date=command.collection_date,
                    advance_until=loan["advance_until"],
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
                if amount > previous_balance:
                    raise CollectionRejected(
                        "The amount is higher than the remaining balance. Refresh the "
                        "route and check the payment.",
                        code="amount_exceeds_balance",
                    )
                official_balance = self._money(previous_balance - amount)
                pass_count_after = 0
                last_payment_date = command.collection_date
                if command.entry_type is CollectionEntryType.ADVANCE:
                    if command.advance_until is None:
                        raise CollectionRejected(
                            "Choose the last date covered by ADV.",
                            code="advance_date_required",
                        )
                    advance_until_after = max(
                        date_value
                        for date_value in (loan["advance_until"], command.advance_until)
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
    def _apply_pass_rules(
        cursor: Any,
        *,
        loan_id: UUID,
        collection_date: date,
        advance_until: date | None,
    ) -> None:
        if advance_until is not None and advance_until >= collection_date:
            raise CollectionRejected(
                "This date is already covered by ADV, so PASS is not needed.",
                code="advance_already_covers_date",
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
                "PASS was already recorded for this client on this date.",
                code="pass_already_recorded",
            )

    @staticmethod
    def _next_receipt_number(cursor: Any, *, collection_date: date) -> str:
        cursor.execute("select nextval('lending.collection_receipt_sequence')")
        sequence = int(cursor.fetchone()["nextval"])
        return f"GBC-{collection_date:%Y%m%d}-{sequence:08d}"

    @staticmethod
    def _success_message(entry_type: CollectionEntryType) -> str:
        if entry_type is CollectionEntryType.ADVANCE:
            return "ADV saved."
        if entry_type is CollectionEntryType.PASS:
            return "PASS saved."
        return "Payment saved."
