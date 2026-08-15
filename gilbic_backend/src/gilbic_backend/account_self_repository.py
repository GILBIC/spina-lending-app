from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from psycopg.rows import dict_row

from .account_repository import AccountNotFound
from .database import open_connection


@dataclass(frozen=True, slots=True)
class AccountDeviceRecord:
    id: UUID
    user_id: UUID
    platform: str
    app_version: str | None
    status: str
    registered_at: datetime
    last_seen_at: datetime | None


class PostgresSelfAccountRepository:
    """Read and revoke only devices owned by the authenticated account."""

    def list_devices(self, *, user_id: UUID) -> list[AccountDeviceRecord]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        id,
                        user_id,
                        platform,
                        app_version,
                        status,
                        registered_at,
                        last_seen_at
                    from core.devices
                    where user_id = %s
                    order by registered_at desc, id
                    """,
                    (user_id,),
                )
                rows = cursor.fetchall()
        return [self._record(row) for row in rows]

    def revoke_device(
        self,
        *,
        user_id: UUID,
        device_id: UUID,
    ) -> AccountDeviceRecord:
        with open_connection() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        update core.devices
                        set status = 'revoked'
                        where id = %s and user_id = %s
                        returning
                            id,
                            user_id,
                            platform,
                            app_version,
                            status,
                            registered_at,
                            last_seen_at
                        """,
                        (device_id, user_id),
                    )
                    row = cursor.fetchone()
        if row is None:
            raise AccountNotFound("That device is not registered to this account.")
        return self._record(row)

    @staticmethod
    def _record(row) -> AccountDeviceRecord:
        return AccountDeviceRecord(
            id=row["id"],
            user_id=row["user_id"],
            platform=str(row["platform"]),
            app_version=(str(row["app_version"]) if row["app_version"] else None),
            status=str(row["status"]),
            registered_at=row["registered_at"],
            last_seen_at=row["last_seen_at"],
        )
