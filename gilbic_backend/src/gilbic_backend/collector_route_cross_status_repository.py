from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection


@dataclass(frozen=True, slots=True)
class CollectorRouteCrossStatusRecord:
    transaction_id: UUID
    collection_origin: str
    recorder_user_id: UUID
    recorder_name: str
    assigned_collector_user_id: UUID | None
    remittance_number: str
    remittance_status: str
    remittance_recipient_name: str
    custody_status: str
    cash_holder_name: str


class PostgresCollectorRouteCrossStatusRepository:
    """Read attribution/custody for transactions already present on one route.

    This repository never decides which clients belong to the route. The caller
    passes transaction IDs returned by the authoritative Collector route query,
    so this is only a display enrichment over existing transaction/remittance
    records.
    """

    def get_for_transactions(
        self,
        *,
        transaction_ids: tuple[UUID, ...],
    ) -> dict[UUID, CollectorRouteCrossStatusRecord]:
        if not transaction_ids:
            return {}

        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        transaction.id as transaction_id,
                        coalesce(transaction.collection_origin, '')
                            as collection_origin,
                        transaction.collector_user_id as recorder_user_id,
                        coalesce(
                            nullif(btrim(recorder.full_name), ''),
                            nullif(btrim(recorder.username), ''),
                            'Collector'
                        ) as recorder_name,
                        transaction.assigned_collector_user_id,
                        coalesce(remittance.remittance_number, '')
                            as remittance_number,
                        coalesce(remittance.status, '') as remittance_status,
                        coalesce(
                            nullif(btrim(recipient.full_name), ''),
                            nullif(btrim(recipient.username), ''),
                            ''
                        ) as remittance_recipient_name,
                        case
                            when transaction.entry_type = 'pass'
                                 or transaction.amount <= 0
                                then 'no_cash'
                            when remittance.id is null
                                then 'not_remitted'
                            when remittance.status = 'received'
                                then 'accepted'
                            else 'awaiting_acceptance'
                        end as custody_status,
                        case
                            when transaction.entry_type = 'pass'
                                 or transaction.amount <= 0
                                then ''
                            when remittance.id is not null
                                 and remittance.status = 'received'
                                then coalesce(
                                    nullif(btrim(recipient.full_name), ''),
                                    nullif(btrim(recipient.username), ''),
                                    'Remittance recipient'
                                )
                            else coalesce(
                                nullif(btrim(recorder.full_name), ''),
                                nullif(btrim(recorder.username), ''),
                                'Collector'
                            )
                        end as cash_holder_name
                    from lending.collection_transactions transaction
                    left join core.users recorder
                      on recorder.id = transaction.collector_user_id
                    left join lending.collection_remittances remittance
                      on remittance.id = transaction.remittance_id
                    left join core.users recipient
                      on recipient.id = remittance.recipient_user_id
                    where transaction.id = any(%s::uuid[])
                      and transaction.is_voided = false
                    """,
                    (list(transaction_ids),),
                )
                rows = cursor.fetchall()

        return {
            row["transaction_id"]: CollectorRouteCrossStatusRecord(
                transaction_id=row["transaction_id"],
                collection_origin=str(row["collection_origin"] or ""),
                recorder_user_id=row["recorder_user_id"],
                recorder_name=str(row["recorder_name"] or "Collector"),
                assigned_collector_user_id=row["assigned_collector_user_id"],
                remittance_number=str(row["remittance_number"] or ""),
                remittance_status=str(row["remittance_status"] or ""),
                remittance_recipient_name=str(
                    row["remittance_recipient_name"] or ""
                ),
                custody_status=str(row["custody_status"]),
                cash_holder_name=str(row["cash_holder_name"] or ""),
            )
            for row in rows
        }
