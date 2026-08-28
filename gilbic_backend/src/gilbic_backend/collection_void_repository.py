from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .database import open_connection

if TYPE_CHECKING:
    from .seven_by_seven_extra_principal_reversal import (
        ExtraPrincipalReversalRequestResult,
    )


MONEY = Decimal("0.01")


class CollectionVoidError(RuntimeError):
    code = "collection_void_error"


class CollectionVoidNotFound(CollectionVoidError):
    code = "collection_void_not_found"


class CollectionVoidLocked(CollectionVoidError):
    code = "collection_void_locked"


class CollectionVoidConflict(CollectionVoidError):
    code = "collection_void_conflict"


class CollectionVoidInvalid(CollectionVoidError):
    code = "collection_void_invalid"


@dataclass(frozen=True, slots=True)
class CollectionVoidCandidate:
    transaction_id: UUID
    receipt_number: str
    client_id: UUID
    client_code: str
    client_name: str
    loan_id: UUID
    loan_type: str
    collector_name: str
    collection_date: date
    entry_type: str
    amount: Decimal
    covered_dates: tuple[date, ...]
    previous_balance: Decimal
    official_balance: Decimal
    is_locked: bool
    is_voided: bool


@dataclass(frozen=True, slots=True)
class CollectionVoidRecord:
    transaction_id: UUID
    receipt_number: str
    client_id: UUID
    client_code: str
    client_name: str
    loan_id: UUID
    collector_user_id: UUID
    collector_name: str
    collection_date: date
    entry_type: str
    amount: Decimal
    covered_dates: tuple[date, ...]
    restored_balance: Decimal
    state_version: int
    reason: str
    voided_at: datetime


class PostgresCollectionVoidRepository:
    def find_by_receipt(self, *, receipt_number: str) -> CollectionVoidCandidate:
        normalized_receipt = receipt_number.strip().upper()
        if not normalized_receipt:
            raise CollectionVoidInvalid("Enter a receipt number.")

        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        t.id as transaction_id,
                        t.receipt_number,
                        t.client_id,
                        c.client_code,
                        c.full_name as client_name,
                        t.loan_id,
                        lt.name as loan_type,
                        coalesce(
                            nullif(btrim(collector.full_name), ''),
                            nullif(btrim(collector.username), ''),
                            'Collector'
                        ) as collector_name,
                        t.collection_date,
                        t.entry_type,
                        t.amount,
                        t.previous_balance,
                        t.official_balance,
                        t.is_locked,
                        t.is_voided,
                        t.remittance_id,
                        coalesce(
                            array(
                                select cd.covered_date
                                from lending.collection_covered_dates cd
                                where cd.transaction_id = t.id
                                order by cd.covered_date
                            ),
                            ARRAY[]::date[]
                        ) as covered_dates
                    from lending.collection_transactions t
                    join lending.clients c on c.id = t.client_id
                    join lending.loans l on l.id = t.loan_id
                    join lending.loan_types lt on lt.id = l.loan_type_id
                    left join core.users collector on collector.id = t.collector_user_id
                    where upper(btrim(t.receipt_number)) = %s
                    limit 1
                    """,
                    (normalized_receipt,),
                )
                row = cursor.fetchone()

        if not row:
            raise CollectionVoidNotFound("Collection receipt was not found.")
        if row["is_voided"]:
            raise CollectionVoidConflict("This collection receipt was already voided.")
        if row["is_locked"] or row["remittance_id"] is not None:
            raise CollectionVoidLocked(
                "This collection is already included in a remittance and cannot be voided."
            )
        return self._candidate_from_row(row)

    def void_unremitted(
        self,
        *,
        actor_user_id: UUID,
        transaction_id: UUID,
        reason: str,
        idempotency_key: UUID | None = None,
    ) -> CollectionVoidRecord | ExtraPrincipalReversalRequestResult:
        normalized_reason = " ".join(reason.split())
        if len(normalized_reason) < 3:
            raise CollectionVoidInvalid(
                "Enter a clear reason for voiding the collection."
            )

        with open_connection() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    adjustment_row = cursor.execute(
                        """
                        select id
                        from lending.seven_by_seven_extra_principal_adjustments
                        where transaction_id = %s
                        """,
                        (transaction_id,),
                    ).fetchone()
                    reversal_request = None
                    if adjustment_row is not None:
                        from .seven_by_seven_extra_principal_reversal import (
                            begin_extra_principal_reversal_request,
                        )

                        reversal_request, replay = (
                            begin_extra_principal_reversal_request(
                                cursor,
                                idempotency_key=idempotency_key,
                                actor_user_id=actor_user_id,
                                transaction_id=transaction_id,
                                adjustment_id=adjustment_row["id"],
                                reason=normalized_reason,
                            )
                        )
                        if replay is not None:
                            return replay
                    else:
                        cursor.execute(
                            "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                            (f"gilbic-management-collection-void:{transaction_id}",),
                        )
                    cursor.execute(
                        """
                        select
                            t.*,
                            c.client_code,
                            c.full_name as client_name,
                            c.user_id as linked_client_user_id,
                            lt.name as loan_type,
                            coalesce(
                                nullif(btrim(collector.full_name), ''),
                                nullif(btrim(collector.username), ''),
                                'Collector'
                            ) as collector_name,
                            s.remaining_balance as state_remaining_balance,
                            s.pass_count as state_pass_count,
                            s.last_payment_date as state_last_payment_date,
                            s.advance_until as state_advance_until,
                            s.note as state_note,
                            s.state_version
                        from lending.collection_transactions t
                        join lending.clients c on c.id = t.client_id
                        join lending.loans l on l.id = t.loan_id
                        join lending.loan_types lt on lt.id = l.loan_type_id
                        join lending.loan_collection_state s on s.loan_id = t.loan_id
                        left join core.users collector on collector.id = t.collector_user_id
                        where t.id = %s
                        for update of t, l, s
                        """,
                        (transaction_id,),
                    )
                    transaction = cursor.fetchone()
                    if not transaction:
                        raise CollectionVoidNotFound(
                            "The collection entry was not found."
                        )
                    if transaction["is_voided"]:
                        raise CollectionVoidConflict(
                            "This collection receipt was already voided."
                        )
                    if (
                        transaction["is_locked"]
                        or transaction["remittance_id"] is not None
                    ):
                        raise CollectionVoidLocked(
                            "This collection is already included in a remittance and cannot be voided."
                        )

                    details = (
                        dict(transaction["details"])
                        if isinstance(transaction["details"], dict)
                        else {}
                    )
                    expected_state_version = details.get("state_version_after")
                    if expected_state_version is None or int(
                        expected_state_version
                    ) != int(transaction["state_version"]):
                        raise CollectionVoidConflict(
                            "The loan changed after this collection. Void only the latest loan entry."
                        )

                    if reversal_request is not None:
                        from .seven_by_seven_extra_principal_reversal import (
                            lock_released_refund_amount,
                            store_blocked_reversal_request,
                        )

                        released_refund_amount = lock_released_refund_amount(
                            cursor,
                            adjustment_id=reversal_request.adjustment_id,
                        )
                        if released_refund_amount > Decimal("0.00"):
                            return store_blocked_reversal_request(
                                cursor,
                                request=reversal_request,
                                released_refund_amount=released_refund_amount,
                            )

                    cursor.execute(
                        """
                        select covered_date
                        from lending.collection_covered_dates
                        where transaction_id = %s
                        order by covered_date
                        """,
                        (transaction_id,),
                    )
                    covered_dates = tuple(
                        row["covered_date"] for row in cursor.fetchall()
                    )

                    cursor.execute(
                        """
                        select
                            coalesce((
                                select previous.pass_count_after
                                from lending.collection_transactions previous
                                where previous.loan_id = %s
                                  and previous.is_voided = false
                                  and (previous.accepted_at, previous.id) < (%s, %s)
                                order by previous.accepted_at desc, previous.id desc
                                limit 1
                            ), 0) as pass_count_before,
                            (
                                select max(cd.covered_date)
                                from lending.collection_covered_dates cd
                                join lending.collection_transactions previous
                                  on previous.id = cd.transaction_id
                                where previous.loan_id = %s
                                  and previous.id <> %s
                                  and previous.is_voided = false
                            ) as advance_until_before,
                            (
                                select previous.collection_date
                                from lending.collection_transactions previous
                                where previous.loan_id = %s
                                  and previous.is_voided = false
                                  and previous.entry_type <> 'pass'
                                  and (previous.accepted_at, previous.id) < (%s, %s)
                                order by previous.accepted_at desc, previous.id desc
                                limit 1
                            ) as last_payment_date_before,
                            coalesce((
                                select previous.note
                                from lending.collection_transactions previous
                                where previous.loan_id = %s
                                  and previous.is_voided = false
                                  and (previous.accepted_at, previous.id) < (%s, %s)
                                order by previous.accepted_at desc, previous.id desc
                                limit 1
                            ), '') as note_before
                        """,
                        (
                            transaction["loan_id"],
                            transaction["accepted_at"],
                            transaction_id,
                            transaction["loan_id"],
                            transaction_id,
                            transaction["loan_id"],
                            transaction["accepted_at"],
                            transaction_id,
                            transaction["loan_id"],
                            transaction["accepted_at"],
                            transaction_id,
                        ),
                    )
                    restored = cursor.fetchone()
                    if restored is None:
                        raise CollectionVoidConflict(
                            "The prior collection state could not be reconstructed."
                        )

                    restored_balance = self._money(transaction["previous_balance"])
                    restored_pass_count = int(restored["pass_count_before"])
                    restored_advance_until = restored["advance_until_before"]
                    restored_last_payment_date = restored["last_payment_date_before"]
                    restored_note = str(restored["note_before"] or "")
                    voided_at = datetime.now(UTC)
                    next_state_version = int(transaction["state_version"]) + 1

                    transaction_snapshot = self._snapshot(
                        transaction,
                        covered_dates=covered_dates,
                    )
                    state_before = {
                        "remaining_balance": str(
                            transaction["state_remaining_balance"]
                        ),
                        "pass_count": int(transaction["state_pass_count"]),
                        "last_payment_date": (
                            transaction["state_last_payment_date"].isoformat()
                            if transaction["state_last_payment_date"]
                            else None
                        ),
                        "advance_until": (
                            transaction["state_advance_until"].isoformat()
                            if transaction["state_advance_until"]
                            else None
                        ),
                        "note": str(transaction["state_note"] or ""),
                        "state_version": int(transaction["state_version"]),
                    }
                    state_after = {
                        "remaining_balance": str(restored_balance),
                        "pass_count": restored_pass_count,
                        "last_payment_date": (
                            restored_last_payment_date.isoformat()
                            if restored_last_payment_date
                            else None
                        ),
                        "advance_until": (
                            restored_advance_until.isoformat()
                            if restored_advance_until
                            else None
                        ),
                        "note": restored_note,
                        "state_version": next_state_version,
                    }
                    prepared_void_record = CollectionVoidRecord(
                        transaction_id=transaction_id,
                        receipt_number=str(transaction["receipt_number"]),
                        client_id=transaction["client_id"],
                        client_code=str(transaction["client_code"]),
                        client_name=str(transaction["client_name"]),
                        loan_id=transaction["loan_id"],
                        collector_user_id=transaction["collector_user_id"],
                        collector_name=str(transaction["collector_name"]),
                        collection_date=transaction["collection_date"],
                        entry_type=str(transaction["entry_type"]),
                        amount=self._money(transaction["amount"]),
                        covered_dates=covered_dates,
                        restored_balance=restored_balance,
                        state_version=next_state_version,
                        reason=normalized_reason,
                        voided_at=voided_at,
                    )
                    collection_void_id = uuid4()

                    cursor.execute(
                        "delete from lending.collection_covered_dates where transaction_id = %s",
                        (transaction_id,),
                    )
                    cursor.execute(
                        """
                        insert into lending.collection_transaction_voids (
                            id,
                            transaction_id,
                            voided_by_user_id,
                            reason,
                            transaction_snapshot,
                            previous_covered_dates,
                            state_before,
                            state_after,
                            voided_at
                        ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            collection_void_id,
                            transaction_id,
                            actor_user_id,
                            normalized_reason,
                            Jsonb(transaction_snapshot),
                            list(covered_dates),
                            Jsonb(state_before),
                            Jsonb(state_after),
                            voided_at,
                        ),
                    )

                    if reversal_request is not None:
                        from .seven_by_seven_extra_principal_reversal import (
                            store_completed_reversal_request,
                        )

                        store_completed_reversal_request(
                            cursor,
                            request=reversal_request,
                            collection_void_id=collection_void_id,
                            collection_void=prepared_void_record,
                        )

                    updated_details = dict(details)
                    updated_details.update(
                        {
                            "voided": True,
                            "voided_at": voided_at.isoformat(),
                            "voided_by_user_id": str(actor_user_id),
                            "void_reason": normalized_reason,
                            "void_state_version_after": next_state_version,
                        }
                    )
                    cursor.execute(
                        """
                        update lending.collection_transactions
                        set is_voided = true,
                            voided_at = %s,
                            voided_by_user_id = %s,
                            void_reason = %s,
                            details = %s,
                            updated_at = %s,
                            updated_by_user_id = %s
                        where id = %s
                          and is_voided = false
                          and remittance_id is null
                          and is_locked = false
                        """,
                        (
                            voided_at,
                            actor_user_id,
                            normalized_reason,
                            Jsonb(updated_details),
                            voided_at,
                            actor_user_id,
                            transaction_id,
                        ),
                    )
                    if cursor.rowcount != 1:
                        raise CollectionVoidConflict(
                            "The collection changed while it was being voided. Refresh and try again."
                        )

                    if reversal_request is not None:
                        from .seven_by_seven_extra_principal_reversal import (
                            verify_completed_extra_principal_reversal,
                        )

                        verify_completed_extra_principal_reversal(
                            cursor,
                            adjustment_id=reversal_request.adjustment_id,
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
                            restored_balance,
                            restored_pass_count,
                            restored_last_payment_date,
                            restored_advance_until,
                            restored_note,
                            next_state_version,
                            voided_at,
                            transaction["loan_id"],
                        ),
                    )
                    cursor.execute(
                        """
                        update lending.loans
                        set status = %s, updated_at = %s
                        where id = %s
                        """,
                        (
                            "paid" if restored_balance == Decimal("0.00") else "active",
                            voided_at,
                            transaction["loan_id"],
                        ),
                    )

                    audit_details = {
                        "receipt_number": str(transaction["receipt_number"]),
                        "reason": normalized_reason,
                        "transaction": transaction_snapshot,
                        "state_before": state_before,
                        "state_after": state_after,
                    }
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
                            'collection.voided.unremitted',
                            'collection_transaction',
                            %s,
                            %s,
                            %s
                        )
                        """,
                        (
                            actor_user_id,
                            transaction_id,
                            Jsonb(audit_details),
                            voided_at,
                        ),
                    )

                    linked_client_user_id = transaction["linked_client_user_id"]
                    if linked_client_user_id is not None:
                        self._insert_notification(
                            cursor,
                            recipient_user_id=linked_client_user_id,
                            sender_user_id=actor_user_id,
                            notification_type="client_payment_voided",
                            title="Payment entry corrected",
                            message=(
                                f"Management voided receipt {transaction['receipt_number']} "
                                f"because it was posted incorrectly. Corrected remaining "
                                f"balance PHP {restored_balance:.2f}."
                            ),
                            transaction_id=transaction_id,
                            client_id=transaction["client_id"],
                            metadata={
                                "receipt_number": str(transaction["receipt_number"]),
                                "reason": normalized_reason,
                                "restored_balance": str(restored_balance),
                            },
                        )
                    if transaction["collector_user_id"] != actor_user_id:
                        self._insert_notification(
                            cursor,
                            recipient_user_id=transaction["collector_user_id"],
                            sender_user_id=actor_user_id,
                            notification_type="collector_payment_voided",
                            title="Collection entry voided",
                            message=(
                                f"Management voided receipt {transaction['receipt_number']} "
                                f"for {transaction['client_name']}."
                            ),
                            transaction_id=transaction_id,
                            client_id=transaction["client_id"],
                            metadata={
                                "receipt_number": str(transaction["receipt_number"]),
                                "reason": normalized_reason,
                            },
                        )

        return prepared_void_record

    @staticmethod
    def _money(value: Decimal | int | str) -> Decimal:
        return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)

    @staticmethod
    def _candidate_from_row(row) -> CollectionVoidCandidate:
        return CollectionVoidCandidate(
            transaction_id=row["transaction_id"],
            receipt_number=str(row["receipt_number"]),
            client_id=row["client_id"],
            client_code=str(row["client_code"]),
            client_name=str(row["client_name"]),
            loan_id=row["loan_id"],
            loan_type=str(row["loan_type"]),
            collector_name=str(row["collector_name"]),
            collection_date=row["collection_date"],
            entry_type=str(row["entry_type"]),
            amount=PostgresCollectionVoidRepository._money(row["amount"]),
            covered_dates=tuple(row["covered_dates"] or ()),
            previous_balance=PostgresCollectionVoidRepository._money(
                row["previous_balance"]
            ),
            official_balance=PostgresCollectionVoidRepository._money(
                row["official_balance"]
            ),
            is_locked=bool(row["is_locked"]),
            is_voided=bool(row["is_voided"]),
        )

    @staticmethod
    def _snapshot(
        transaction: dict[str, Any],
        *,
        covered_dates: tuple[date, ...],
    ) -> dict[str, object]:
        return {
            "transaction_id": str(transaction["id"]),
            "receipt_number": str(transaction["receipt_number"]),
            "client_id": str(transaction["client_id"]),
            "client_code": str(transaction["client_code"]),
            "client_name": str(transaction["client_name"]),
            "loan_id": str(transaction["loan_id"]),
            "collector_user_id": str(transaction["collector_user_id"]),
            "collector_name": str(transaction["collector_name"]),
            "collection_date": transaction["collection_date"].isoformat(),
            "entry_type": str(transaction["entry_type"]),
            "amount": str(transaction["amount"]),
            "previous_balance": str(transaction["previous_balance"]),
            "official_balance": str(transaction["official_balance"]),
            "pass_count_after": int(transaction["pass_count_after"]),
            "advance_until_after": (
                transaction["advance_until_after"].isoformat()
                if transaction["advance_until_after"]
                else None
            ),
            "covered_dates": [value.isoformat() for value in covered_dates],
            "note": str(transaction["note"] or ""),
            "accepted_at": transaction["accepted_at"].isoformat(),
            "edit_version": int(transaction["edit_version"]),
        }

    @staticmethod
    def _insert_notification(
        cursor,
        *,
        recipient_user_id: UUID,
        sender_user_id: UUID,
        notification_type: str,
        title: str,
        message: str,
        transaction_id: UUID,
        client_id: UUID,
        metadata: dict[str, object],
    ) -> None:
        cursor.execute(
            """
            insert into core.activity_notifications (
                id,
                recipient_user_id,
                sender_user_id,
                notification_type,
                title,
                message,
                transaction_id,
                client_id,
                metadata,
                is_read,
                created_at
            ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, false, now())
            """,
            (
                uuid4(),
                recipient_user_id,
                sender_user_id,
                notification_type,
                title,
                message,
                transaction_id,
                client_id,
                Jsonb(metadata),
            ),
        )
