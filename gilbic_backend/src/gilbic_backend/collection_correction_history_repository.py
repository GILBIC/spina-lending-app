from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from .collection_correction_repository import (
    CollectionCorrectionForbidden,
    CollectionCorrectionNotFound,
)
from .database import open_connection


@dataclass(frozen=True, slots=True)
class CollectionCorrectionHistoryRecord:
    edit_id: UUID
    transaction_id: UUID
    edit_version: int
    reason: str
    previous_snapshot: dict[str, Any]
    replacement_snapshot: dict[str, Any]
    previous_covered_dates: tuple[date, ...]
    replacement_covered_dates: tuple[date, ...]
    edited_by_user_id: UUID
    edited_by_name: str
    edited_at: datetime


class PostgresCollectionCorrectionHistoryRepository:
    """Read immutable correction evidence for a Collector-visible transaction."""

    def list_for_transaction(
        self,
        *,
        actor_user_id: UUID,
        transaction_id: UUID,
    ) -> tuple[CollectionCorrectionHistoryRecord, ...]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        collector_user_id,
                        assigned_collector_user_id
                    from lending.collection_transactions
                    where id = %s
                    """,
                    (transaction_id,),
                )
                transaction = cursor.fetchone()
                if transaction is None:
                    raise CollectionCorrectionNotFound(
                        "The collection entry was not found."
                    )

                allowed_user_ids = {
                    value
                    for value in (
                        transaction["collector_user_id"],
                        transaction.get("assigned_collector_user_id"),
                    )
                    if value is not None
                }
                if actor_user_id not in allowed_user_ids:
                    raise CollectionCorrectionForbidden(
                        "Only the recording or assigned Collector may view this collection correction history."
                    )

                cursor.execute(
                    """
                    select
                        edit.id as edit_id,
                        edit.transaction_id,
                        edit.edit_version,
                        edit.reason,
                        edit.previous_snapshot,
                        edit.replacement_snapshot,
                        edit.previous_covered_dates,
                        edit.replacement_covered_dates,
                        edit.edited_by_user_id,
                        coalesce(
                            nullif(btrim(actor.full_name), ''),
                            nullif(btrim(actor.username), ''),
                            'SPINA staff'
                        ) as edited_by_name,
                        edit.edited_at
                    from lending.collection_transaction_edits edit
                    left join core.users actor
                      on actor.id = edit.edited_by_user_id
                    where edit.transaction_id = %s
                    order by edit.edit_version desc, edit.edited_at desc
                    """,
                    (transaction_id,),
                )
                rows = cursor.fetchall()

        return tuple(self._record_from_row(row) for row in rows)

    @staticmethod
    def _record_from_row(row) -> CollectionCorrectionHistoryRecord:
        return CollectionCorrectionHistoryRecord(
            edit_id=row["edit_id"],
            transaction_id=row["transaction_id"],
            edit_version=int(row["edit_version"]),
            reason=str(row["reason"]),
            previous_snapshot=dict(row["previous_snapshot"] or {}),
            replacement_snapshot=dict(row["replacement_snapshot"] or {}),
            previous_covered_dates=tuple(row["previous_covered_dates"] or ()),
            replacement_covered_dates=tuple(row["replacement_covered_dates"] or ()),
            edited_by_user_id=row["edited_by_user_id"],
            edited_by_name=str(row["edited_by_name"]),
            edited_at=row["edited_at"],
        )
