from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .database import open_connection
from .remittance_repository import (
    PostgresRemittanceRepository,
    RemittanceAlreadyReceived,
    RemittanceError,
    RemittanceItemRecord,
    RemittanceNotFound,
    RemittanceRecipientInvalid,
)


class RemittanceReviewRequired(RemittanceError):
    code = "remittance_review_required"


class RemittanceAlreadyRejected(RemittanceError):
    code = "remittance_already_rejected"


class RemittanceRejected(RemittanceError):
    code = "remittance_rejected"


class RemittanceRejectionReasonRequired(RemittanceError):
    code = "remittance_rejection_reason_required"


@dataclass(frozen=True, slots=True)
class RemittanceHistoryRecord:
    remittance_id: UUID
    remittance_number: str
    collector_user_id: UUID
    collector_name: str
    recipient_user_id: UUID
    recipient_name: str
    collection_date: date
    status: str
    transaction_count: int
    payment_count: int
    unable_to_pay_count: int
    covered_payment_count: int
    client_count: int
    total_amount: Decimal
    note: str
    submitted_at: datetime
    received_at: datetime | None
    items: tuple[RemittanceItemRecord, ...]
    reviewed_at: datetime | None = None
    reviewed_by_user_id: UUID | None = None
    rejected_at: datetime | None = None
    rejected_by_user_id: UUID | None = None
    rejection_reason: str = ""


class PostgresReviewedRemittanceRepository(PostgresRemittanceRepository):
    """Adds recipient review/rejection evidence without rewriting payment history."""

    def list_for_user(
        self,
        *,
        actor_user_id: UUID,
    ) -> tuple[RemittanceHistoryRecord, ...]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        r.*,
                        collector.full_name as collector_name,
                        recipient.full_name as recipient_name,
                        review.reviewed_by_user_id,
                        review.reviewed_at,
                        rejection.rejected_by_user_id,
                        rejection.rejected_at,
                        coalesce(rejection.reason, '') as rejection_reason
                    from lending.collection_remittances r
                    join core.users collector on collector.id = r.collector_user_id
                    join core.users recipient on recipient.id = r.recipient_user_id
                    left join lending.collection_remittance_reviews review
                      on review.remittance_id = r.id
                    left join lending.collection_remittance_rejections rejection
                      on rejection.remittance_id = r.id
                    where r.collector_user_id = %s or r.recipient_user_id = %s
                    order by r.submitted_at desc, r.id desc
                    """,
                    (actor_user_id, actor_user_id),
                )
                rows = cursor.fetchall()
                records: list[RemittanceHistoryRecord] = []
                for row in rows:
                    items = self._remittance_items(cursor, row["id"])
                    records.append(self._history_record_from_row(row, items))
        return tuple(records)

    def confirm_received(
        self,
        *,
        remittance_id: UUID,
        recipient_user_id: UUID,
        review_acknowledged: bool = False,
    ) -> RemittanceHistoryRecord:
        self._require_review(review_acknowledged)
        with open_connection() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    row = self._locked_remittance(cursor, remittance_id)
                    self._verify_actionable_recipient(
                        row,
                        recipient_user_id=recipient_user_id,
                    )
                    if row["rejected_at"] is not None:
                        raise RemittanceRejected(
                            "This remittance was rejected and cannot be accepted."
                        )
                    if row["status"] == "received":
                        raise RemittanceAlreadyReceived(
                            "This remittance was already confirmed as received."
                        )

                    received_at = datetime.now(timezone.utc)
                    self._record_review(
                        cursor,
                        remittance_id=remittance_id,
                        recipient_user_id=recipient_user_id,
                        reviewed_at=received_at,
                    )
                    cursor.execute(
                        """
                        update lending.collection_remittances
                        set status = 'received',
                            received_at = %s,
                            received_by_user_id = %s,
                            updated_at = %s
                        where id = %s
                        """,
                        (
                            received_at,
                            recipient_user_id,
                            received_at,
                            remittance_id,
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
                        ) values (%s, 'remittance.received', 'collection_remittance', %s, %s, %s)
                        """,
                        (
                            recipient_user_id,
                            remittance_id,
                            Jsonb(
                                {
                                    "remittance_number": row["remittance_number"],
                                    "review_acknowledged": True,
                                }
                            ),
                            received_at,
                        ),
                    )
                    items = self._remittance_items(cursor, remittance_id)
                    updated = dict(row)
                    updated["status"] = "received"
                    updated["received_at"] = received_at
                    updated["reviewed_at"] = received_at
                    updated["reviewed_by_user_id"] = recipient_user_id
        return self._history_record_from_row(updated, items)

    def reject(
        self,
        *,
        remittance_id: UUID,
        recipient_user_id: UUID,
        reason: str,
        review_acknowledged: bool = False,
    ) -> RemittanceHistoryRecord:
        self._require_review(review_acknowledged)
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise RemittanceRejectionReasonRequired(
                "Enter a reason for rejecting this remittance."
            )

        with open_connection() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    row = self._locked_remittance(cursor, remittance_id)
                    self._verify_actionable_recipient(
                        row,
                        recipient_user_id=recipient_user_id,
                    )
                    if row["status"] == "received":
                        raise RemittanceAlreadyReceived(
                            "An accepted remittance cannot be rejected."
                        )
                    if row["rejected_at"] is not None:
                        raise RemittanceAlreadyRejected(
                            "This remittance was already rejected."
                        )

                    rejected_at = datetime.now(timezone.utc)
                    self._record_review(
                        cursor,
                        remittance_id=remittance_id,
                        recipient_user_id=recipient_user_id,
                        reviewed_at=rejected_at,
                    )
                    cursor.execute(
                        """
                        insert into lending.collection_remittance_rejections (
                            remittance_id,
                            rejected_by_user_id,
                            rejected_at,
                            reason
                        ) values (%s, %s, %s, %s)
                        """,
                        (
                            remittance_id,
                            recipient_user_id,
                            rejected_at,
                            normalized_reason,
                        ),
                    )

                    cursor.execute(
                        """
                        update lending.collection_transactions
                        set remittance_id = null,
                            is_locked = false,
                            locked_at = null,
                            locked_by_user_id = null,
                            updated_at = %s,
                            updated_by_user_id = %s
                        where remittance_id = %s
                          and is_locked = true
                        """,
                        (
                            rejected_at,
                            recipient_user_id,
                            remittance_id,
                        ),
                    )
                    if cursor.rowcount != int(row["transaction_count"]):
                        raise RemittanceError(
                            "The remittance contents changed while rejection was being recorded."
                        )

                    cursor.execute(
                        """
                        update core.user_notifications
                        set read_at = coalesce(read_at, %s)
                        where remittance_id = %s
                          and recipient_user_id = %s
                        """,
                        (rejected_at, remittance_id, recipient_user_id),
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
                        ) values (%s, 'remittance.rejected', 'collection_remittance', %s, %s, %s)
                        """,
                        (
                            recipient_user_id,
                            remittance_id,
                            Jsonb(
                                {
                                    "remittance_number": row["remittance_number"],
                                    "reason": normalized_reason,
                                    "review_acknowledged": True,
                                    "cash_responsibility_returned_to": str(
                                        row["collector_user_id"]
                                    ),
                                }
                            ),
                            rejected_at,
                        ),
                    )
                    items = self._remittance_items(cursor, remittance_id)
                    updated = dict(row)
                    updated["reviewed_at"] = rejected_at
                    updated["reviewed_by_user_id"] = recipient_user_id
                    updated["rejected_at"] = rejected_at
                    updated["rejected_by_user_id"] = recipient_user_id
                    updated["rejection_reason"] = normalized_reason
        return self._history_record_from_row(updated, items)

    @staticmethod
    def _require_review(review_acknowledged: bool) -> None:
        if not review_acknowledged:
            raise RemittanceReviewRequired(
                "Review the full client and payment list before continuing."
            )

    @staticmethod
    def _record_review(
        cursor,
        *,
        remittance_id: UUID,
        recipient_user_id: UUID,
        reviewed_at: datetime,
    ) -> None:
        cursor.execute(
            """
            insert into lending.collection_remittance_reviews (
                remittance_id,
                reviewed_by_user_id,
                reviewed_at
            ) values (%s, %s, %s)
            on conflict (remittance_id) do nothing
            """,
            (remittance_id, recipient_user_id, reviewed_at),
        )

    @staticmethod
    def _verify_actionable_recipient(row, *, recipient_user_id: UUID) -> None:
        if row["recipient_user_id"] != recipient_user_id:
            raise RemittanceRecipientInvalid(
                "Only the selected recipient can review this remittance."
            )

    @staticmethod
    def _locked_remittance(cursor, remittance_id: UUID):
        cursor.execute(
            """
            select
                r.*,
                collector.full_name as collector_name,
                recipient.full_name as recipient_name,
                review.reviewed_by_user_id,
                review.reviewed_at,
                rejection.rejected_by_user_id,
                rejection.rejected_at,
                coalesce(rejection.reason, '') as rejection_reason
            from lending.collection_remittances r
            join core.users collector on collector.id = r.collector_user_id
            join core.users recipient on recipient.id = r.recipient_user_id
            left join lending.collection_remittance_reviews review
              on review.remittance_id = r.id
            left join lending.collection_remittance_rejections rejection
              on rejection.remittance_id = r.id
            where r.id = %s
            for update of r
            """,
            (remittance_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise RemittanceNotFound("Remittance was not found.")
        return row

    @staticmethod
    def _history_record_from_row(
        row,
        items: tuple[RemittanceItemRecord, ...],
    ) -> RemittanceHistoryRecord:
        rejected_at = row.get("rejected_at")
        status = "rejected" if rejected_at is not None else str(row["status"])
        return RemittanceHistoryRecord(
            remittance_id=row["id"],
            remittance_number=str(row["remittance_number"]),
            collector_user_id=row["collector_user_id"],
            collector_name=str(row["collector_name"]),
            recipient_user_id=row["recipient_user_id"],
            recipient_name=str(row["recipient_name"]),
            collection_date=row["collection_date"],
            status=status,
            transaction_count=int(row["transaction_count"]),
            payment_count=int(row["payment_count"]),
            unable_to_pay_count=int(row["unable_to_pay_count"]),
            covered_payment_count=int(row["covered_payment_count"]),
            client_count=int(row["client_count"]),
            total_amount=Decimal(row["total_amount"]),
            note=str(row["note"] or ""),
            submitted_at=row["submitted_at"],
            received_at=row["received_at"],
            items=items,
            reviewed_at=row.get("reviewed_at"),
            reviewed_by_user_id=row.get("reviewed_by_user_id"),
            rejected_at=rejected_at,
            rejected_by_user_id=row.get("rejected_by_user_id"),
            rejection_reason=str(row.get("rejection_reason") or ""),
        )
