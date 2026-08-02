from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection


class NotificationError(RuntimeError):
    code = "notification_error"


class NotificationNotFound(NotificationError):
    code = "notification_not_found"


class NotificationForbidden(NotificationError):
    code = "notification_forbidden"


@dataclass(frozen=True, slots=True)
class RemittanceNotificationRecord:
    notification_id: UUID
    recipient_user_id: UUID
    sender_user_id: UUID
    remittance_id: UUID
    title: str
    message: str
    status: str
    created_at: datetime
    read_at: datetime | None
    accepted_at: datetime | None
    remittance_number: str
    collector_name: str
    total_amount: Decimal
    client_count: int
    transaction_count: int
    collection_date: date

    @property
    def is_pending(self) -> bool:
        return self.status == "pending"


class PostgresNotificationRepository:
    def list_for_user(
        self,
        *,
        recipient_user_id: UUID,
    ) -> tuple[RemittanceNotificationRecord, ...]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        notification.id as notification_id,
                        notification.recipient_user_id,
                        notification.sender_user_id,
                        notification.remittance_id,
                        notification.title,
                        notification.message,
                        notification.status,
                        notification.created_at,
                        notification.read_at,
                        notification.accepted_at,
                        remittance.remittance_number,
                        collector.full_name as collector_name,
                        remittance.total_amount,
                        remittance.client_count,
                        remittance.transaction_count,
                        remittance.collection_date
                    from core.user_notifications notification
                    join lending.collection_remittances remittance
                      on remittance.id = notification.remittance_id
                    join core.users collector
                      on collector.id = remittance.collector_user_id
                    where notification.recipient_user_id = %s
                    order by
                        case when notification.status = 'pending' then 0 else 1 end,
                        notification.created_at desc,
                        notification.id desc
                    """,
                    (recipient_user_id,),
                )
                rows = cursor.fetchall()
        return tuple(self._from_row(row) for row in rows)

    def get_for_user(
        self,
        *,
        notification_id: UUID,
        recipient_user_id: UUID,
    ) -> RemittanceNotificationRecord:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        notification.id as notification_id,
                        notification.recipient_user_id,
                        notification.sender_user_id,
                        notification.remittance_id,
                        notification.title,
                        notification.message,
                        notification.status,
                        notification.created_at,
                        notification.read_at,
                        notification.accepted_at,
                        remittance.remittance_number,
                        collector.full_name as collector_name,
                        remittance.total_amount,
                        remittance.client_count,
                        remittance.transaction_count,
                        remittance.collection_date
                    from core.user_notifications notification
                    join lending.collection_remittances remittance
                      on remittance.id = notification.remittance_id
                    join core.users collector
                      on collector.id = remittance.collector_user_id
                    where notification.id = %s
                    """,
                    (notification_id,),
                )
                row = cursor.fetchone()
        if not row:
            raise NotificationNotFound("Notification was not found.")
        if row["recipient_user_id"] != recipient_user_id:
            raise NotificationForbidden(
                "This remittance notification belongs to another account."
            )
        return self._from_row(row)

    def mark_read(
        self,
        *,
        notification_id: UUID,
        recipient_user_id: UUID,
    ) -> RemittanceNotificationRecord:
        with open_connection() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        update core.user_notifications
                        set read_at = coalesce(read_at, %s)
                        where id = %s
                          and recipient_user_id = %s
                        returning id
                        """,
                        (
                            datetime.now(timezone.utc),
                            notification_id,
                            recipient_user_id,
                        ),
                    )
                    if not cursor.fetchone():
                        raise NotificationNotFound("Notification was not found.")
        return self.get_for_user(
            notification_id=notification_id,
            recipient_user_id=recipient_user_id,
        )

    @staticmethod
    def _from_row(row) -> RemittanceNotificationRecord:
        return RemittanceNotificationRecord(
            notification_id=row["notification_id"],
            recipient_user_id=row["recipient_user_id"],
            sender_user_id=row["sender_user_id"],
            remittance_id=row["remittance_id"],
            title=str(row["title"]),
            message=str(row["message"]),
            status=str(row["status"]),
            created_at=row["created_at"],
            read_at=row["read_at"],
            accepted_at=row["accepted_at"],
            remittance_number=str(row["remittance_number"]),
            collector_name=str(row["collector_name"]),
            total_amount=Decimal(row["total_amount"]),
            client_count=int(row["client_count"]),
            transaction_count=int(row["transaction_count"]),
            collection_date=row["collection_date"],
        )
