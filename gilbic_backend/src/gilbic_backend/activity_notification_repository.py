from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection


class ActivityNotificationError(RuntimeError):
    code = "activity_notification_error"


class ActivityNotificationNotFound(ActivityNotificationError):
    code = "activity_notification_not_found"


@dataclass(frozen=True, slots=True)
class ActivityNotificationRecord:
    notification_id: UUID
    recipient_user_id: UUID
    sender_user_id: UUID
    sender_name: str
    notification_type: str
    title: str
    message: str
    transaction_id: UUID | None
    remittance_id: UUID | None
    client_id: UUID | None
    metadata: dict[str, Any]
    is_read: bool
    created_at: datetime
    read_at: datetime | None


class PostgresActivityNotificationRepository:
    def list_for_user(
        self,
        *,
        recipient_user_id: UUID,
        limit: int = 100,
    ) -> tuple[ActivityNotificationRecord, ...]:
        safe_limit = max(1, min(limit, 200))
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        notification.id as notification_id,
                        notification.recipient_user_id,
                        notification.sender_user_id,
                        coalesce(
                            nullif(btrim(sender.full_name), ''),
                            nullif(btrim(sender.username), ''),
                            'SPINA'
                        ) as sender_name,
                        notification.notification_type,
                        notification.title,
                        notification.message,
                        notification.transaction_id,
                        notification.remittance_id,
                        notification.client_id,
                        notification.metadata,
                        notification.is_read,
                        notification.created_at,
                        notification.read_at
                    from core.activity_notifications notification
                    join core.users sender
                      on sender.id = notification.sender_user_id
                    where notification.recipient_user_id = %s
                    order by
                        notification.is_read,
                        notification.created_at desc,
                        notification.id desc
                    limit %s
                    """,
                    (recipient_user_id, safe_limit),
                )
                rows = cursor.fetchall()
        return tuple(self._from_row(row) for row in rows)

    def mark_read(
        self,
        *,
        notification_id: UUID,
        recipient_user_id: UUID,
    ) -> ActivityNotificationRecord:
        with open_connection() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        update core.activity_notifications
                        set is_read = true,
                            read_at = coalesce(read_at, %s)
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
                        raise ActivityNotificationNotFound(
                            "Activity notification was not found."
                        )
        return self.get_for_user(
            notification_id=notification_id,
            recipient_user_id=recipient_user_id,
        )

    def get_for_user(
        self,
        *,
        notification_id: UUID,
        recipient_user_id: UUID,
    ) -> ActivityNotificationRecord:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        notification.id as notification_id,
                        notification.recipient_user_id,
                        notification.sender_user_id,
                        coalesce(
                            nullif(btrim(sender.full_name), ''),
                            nullif(btrim(sender.username), ''),
                            'SPINA'
                        ) as sender_name,
                        notification.notification_type,
                        notification.title,
                        notification.message,
                        notification.transaction_id,
                        notification.remittance_id,
                        notification.client_id,
                        notification.metadata,
                        notification.is_read,
                        notification.created_at,
                        notification.read_at
                    from core.activity_notifications notification
                    join core.users sender
                      on sender.id = notification.sender_user_id
                    where notification.id = %s
                      and notification.recipient_user_id = %s
                    """,
                    (notification_id, recipient_user_id),
                )
                row = cursor.fetchone()
        if not row:
            raise ActivityNotificationNotFound(
                "Activity notification was not found."
            )
        return self._from_row(row)

    @staticmethod
    def _from_row(row) -> ActivityNotificationRecord:
        metadata = row["metadata"] if isinstance(row["metadata"], dict) else {}
        return ActivityNotificationRecord(
            notification_id=row["notification_id"],
            recipient_user_id=row["recipient_user_id"],
            sender_user_id=row["sender_user_id"],
            sender_name=str(row["sender_name"]),
            notification_type=str(row["notification_type"]),
            title=str(row["title"]),
            message=str(row["message"]),
            transaction_id=row["transaction_id"],
            remittance_id=row["remittance_id"],
            client_id=row["client_id"],
            metadata=metadata,
            is_read=bool(row["is_read"]),
            created_at=row["created_at"],
            read_at=row["read_at"],
        )
