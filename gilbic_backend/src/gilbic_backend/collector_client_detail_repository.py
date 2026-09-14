from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from psycopg.rows import dict_row

from .area_management_repository import apply_due_client_area_transfers
from .database import open_connection


_MANILA_TZ = ZoneInfo("Asia/Manila")


@dataclass(frozen=True, slots=True)
class CollectorClientDetailRecord:
    client_id: UUID
    collection_location_status: Literal["verified", "not_verified"]
    display_address: str | None = None
    landmark: str | None = None
    photo_url: str | None = None
    verified_at: datetime | None = None


class PostgresCollectorClientDetailRepository:
    """Read collection-location detail only within current server route scope.

    No authoritative verified collection-location store exists on this branch.
    An authorized Client therefore returns an explicitly unverified record. Do
    not substitute an operational Area, residence address, or KYC evidence.
    A future verified read source belongs here, behind the same scope check.
    """

    def get_collection_location(
        self,
        *,
        collector_user_id: UUID,
        client_id: UUID,
    ) -> CollectorClientDetailRecord | None:
        with open_connection() as connection:
            apply_due_client_area_transfers(
                connection,
                as_of_date=datetime.now(_MANILA_TZ).date(),
            )
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select client.id as client_id
                    from lending.clients client
                    left join lending.area_nodes node
                      on node.area_uid = client.area_uid
                    where client.id = %s
                      and client.status = 'active'
                      and (client.area_uid is null or node.is_active = true)
                      and (
                          lending.collector_area_owner(
                              coalesce(node.full_path, client.area, '')
                          ) = %s
                          or lending.collector_has_active_delegated_area_access(
                              %s,
                              coalesce(node.full_path, client.area, ''),
                              now()
                          )
                      )
                    limit 1
                    """,
                    (client_id, collector_user_id, collector_user_id),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return CollectorClientDetailRecord(
            client_id=row["client_id"],
            collection_location_status="not_verified",
        )
