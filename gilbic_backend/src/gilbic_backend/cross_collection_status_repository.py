from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection


@dataclass(frozen=True, slots=True)
class CrossCollectionStatusRecord:
    transaction_id: UUID
    receipt_number: str
    client_id: UUID
    client_name: str
    loan_id: UUID
    loan_type: str
    area: str
    assigned_collector_user_id: UUID | None
    assigned_collector_name: str
    collection_date: date
    entry_type: str
    amount: Decimal
    accepted_at: datetime
    is_locked: bool
    remittance_id: UUID | None
    remittance_number: str
    custody_status: str
    remittance_recipient_user_id: UUID | None
    remittance_recipient_name: str
    submitted_at: datetime | None
    received_at: datetime | None


class PostgresCrossCollectionStatusRepository:
    def list_for_collector(
        self,
        *,
        collector_user_id: UUID,
        collection_date: date | None = None,
        limit: int = 500,
    ) -> tuple[CrossCollectionStatusRecord, ...]:
        safe_limit = max(1, min(limit, 1000))
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        transaction.id as transaction_id,
                        transaction.receipt_number,
                        transaction.client_id,
                        client.full_name as client_name,
                        transaction.loan_id,
                        loan_type.name as loan_type,
                        coalesce(client.area, '') as area,
                        transaction.assigned_collector_user_id,
                        coalesce(assigned.full_name, 'Unassigned')
                            as assigned_collector_name,
                        transaction.collection_date,
                        transaction.entry_type,
                        transaction.amount,
                        transaction.accepted_at,
                        transaction.is_locked,
                        remittance.id as remittance_id,
                        coalesce(remittance.remittance_number, '')
                            as remittance_number,
                        case
                            when remittance.id is null then 'not_remitted'
                            when remittance.status = 'received' then 'accepted'
                            else 'awaiting_acceptance'
                        end as custody_status,
                        remittance.recipient_user_id
                            as remittance_recipient_user_id,
                        coalesce(recipient.full_name, '')
                            as remittance_recipient_name,
                        remittance.submitted_at,
                        remittance.received_at
                    from lending.collection_transactions transaction
                    join lending.clients client
                      on client.id = transaction.client_id
                    join lending.loans loan
                      on loan.id = transaction.loan_id
                    join lending.loan_types loan_type
                      on loan_type.id = loan.loan_type_id
                    left join core.users assigned
                      on assigned.id = transaction.assigned_collector_user_id
                    left join lending.collection_remittances remittance
                      on remittance.id = transaction.remittance_id
                    left join core.users recipient
                      on recipient.id = remittance.recipient_user_id
                    where transaction.collector_user_id = %s
                      and transaction.collection_origin = 'cross_collector'
                      and transaction.is_voided = false
                      and (%s::date is null or transaction.collection_date = %s)
                    order by
                        transaction.collection_date desc,
                        lower(coalesce(assigned.full_name, '')),
                        lower(coalesce(client.area, '')),
                        transaction.accepted_at desc,
                        transaction.id desc
                    limit %s
                    """,
                    (
                        collector_user_id,
                        collection_date,
                        collection_date,
                        safe_limit,
                    ),
                )
                rows = cursor.fetchall()

        return tuple(
            CrossCollectionStatusRecord(
                transaction_id=row["transaction_id"],
                receipt_number=str(row["receipt_number"]),
                client_id=row["client_id"],
                client_name=str(row["client_name"]),
                loan_id=row["loan_id"],
                loan_type=str(row["loan_type"]),
                area=str(row["area"] or ""),
                assigned_collector_user_id=row["assigned_collector_user_id"],
                assigned_collector_name=str(row["assigned_collector_name"]),
                collection_date=row["collection_date"],
                entry_type=str(row["entry_type"]),
                amount=Decimal(row["amount"]),
                accepted_at=row["accepted_at"],
                is_locked=bool(row["is_locked"]),
                remittance_id=row["remittance_id"],
                remittance_number=str(row["remittance_number"] or ""),
                custody_status=str(row["custody_status"]),
                remittance_recipient_user_id=row["remittance_recipient_user_id"],
                remittance_recipient_name=str(
                    row["remittance_recipient_name"] or ""
                ),
                submitted_at=row["submitted_at"],
                received_at=row["received_at"],
            )
            for row in rows
        )
