from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection


OperationEntryStatus = Literal[
    "all",
    "unremitted",
    "submitted",
    "received",
    "voided",
]


@dataclass(frozen=True, slots=True)
class ManagementOperationsSummary:
    latest_collection_date: date | None
    latest_day_amount: Decimal
    latest_day_payment_count: int
    latest_day_unable_to_pay_count: int
    unremitted_amount: Decimal
    unremitted_entry_count: int
    pending_remittance_amount: Decimal
    pending_remittance_count: int
    received_remittance_amount: Decimal
    received_remittance_count: int
    correction_count: int
    void_count: int


@dataclass(frozen=True, slots=True)
class ManagementOperationEntry:
    transaction_id: UUID
    receipt_number: str
    collection_date: date
    accepted_at: datetime
    client_code: str
    client_name: str
    loan_number: str
    loan_type_name: str
    collector_name: str
    entry_type: str
    amount: Decimal
    official_balance: Decimal
    covered_dates: tuple[date, ...]
    edit_version: int
    status: str
    remittance_number: str | None
    void_reason: str | None


@dataclass(frozen=True, slots=True)
class ManagementOperationAudit:
    event_id: UUID
    event_type: str
    happened_at: datetime
    transaction_id: UUID
    receipt_number: str
    client_name: str
    loan_number: str
    actor_name: str
    reason: str


@dataclass(frozen=True, slots=True)
class ManagementOperationsOverview:
    summary: ManagementOperationsSummary
    entries: tuple[ManagementOperationEntry, ...]
    audits: tuple[ManagementOperationAudit, ...]


class PostgresManagementOperationsRepository:
    def load_overview(
        self,
        *,
        query: str,
        status: OperationEntryStatus,
        limit: int,
    ) -> ManagementOperationsOverview:
        normalized_query = " ".join(query.split())
        pattern = f"%{normalized_query}%"

        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select max(collection_date) as latest_collection_date
                    from lending.collection_transactions
                    where is_voided = false
                    """
                )
                latest_row = cursor.fetchone()
                latest_collection_date = latest_row["latest_collection_date"]

                cursor.execute(
                    """
                    select
                        coalesce(sum(t.amount) filter (
                            where t.is_voided = false
                              and t.entry_type <> 'pass'
                              and (%s::date is null or t.collection_date = %s::date)
                        ), 0) as latest_day_amount,
                        count(*) filter (
                            where t.is_voided = false
                              and t.entry_type <> 'pass'
                              and (%s::date is null or t.collection_date = %s::date)
                        ) as latest_day_payment_count,
                        count(*) filter (
                            where t.is_voided = false
                              and t.entry_type = 'pass'
                              and (%s::date is null or t.collection_date = %s::date)
                        ) as latest_day_unable_to_pay_count,
                        coalesce(sum(t.amount) filter (
                            where t.is_voided = false
                              and t.is_locked = false
                              and t.remittance_id is null
                              and t.entry_type <> 'pass'
                        ), 0) as unremitted_amount,
                        count(*) filter (
                            where t.is_voided = false
                              and t.is_locked = false
                              and t.remittance_id is null
                        ) as unremitted_entry_count
                    from lending.collection_transactions t
                    """,
                    (
                        latest_collection_date,
                        latest_collection_date,
                        latest_collection_date,
                        latest_collection_date,
                        latest_collection_date,
                        latest_collection_date,
                    ),
                )
                collection_summary = cursor.fetchone()

                cursor.execute(
                    """
                    select
                        coalesce(sum(total_amount) filter (
                            where status = 'submitted'
                        ), 0) as pending_remittance_amount,
                        count(*) filter (
                            where status = 'submitted'
                        ) as pending_remittance_count,
                        coalesce(sum(total_amount) filter (
                            where status = 'received'
                        ), 0) as received_remittance_amount,
                        count(*) filter (
                            where status = 'received'
                        ) as received_remittance_count
                    from lending.collection_remittances
                    """
                )
                remittance_summary = cursor.fetchone()

                cursor.execute(
                    """
                    select
                        (select count(*) from lending.collection_transaction_edits)
                            as correction_count,
                        (select count(*) from lending.collection_transaction_voids)
                            as void_count
                    """
                )
                audit_summary = cursor.fetchone()

                cursor.execute(
                    """
                    select
                        t.id as transaction_id,
                        t.receipt_number,
                        t.collection_date,
                        t.accepted_at,
                        client.client_code,
                        client.full_name as client_name,
                        loan.loan_number,
                        coalesce(nullif(btrim(loan_type.name), ''), 'Loan')
                            as loan_type_name,
                        coalesce(
                            nullif(btrim(collector.full_name), ''),
                            nullif(btrim(collector.username), ''),
                            'SPINA staff'
                        ) as collector_name,
                        t.entry_type,
                        t.amount,
                        t.official_balance,
                        coalesce(coverage.covered_dates, array[]::date[])
                            as covered_dates,
                        t.edit_version,
                        case
                            when t.is_voided then 'voided'
                            when remittance.status = 'received' then 'received'
                            when remittance.status = 'submitted' then 'submitted'
                            else 'unremitted'
                        end as operation_status,
                        remittance.remittance_number,
                        t.void_reason
                    from lending.collection_transactions t
                    join lending.clients client on client.id = t.client_id
                    join lending.loans loan on loan.id = t.loan_id
                    left join lending.loan_types loan_type
                      on loan_type.id = loan.loan_type_id
                    left join core.users collector
                      on collector.id = t.collector_user_id
                    left join lending.collection_remittances remittance
                      on remittance.id = t.remittance_id
                    left join lateral (
                        select array_agg(item.covered_date order by item.covered_date)
                            as covered_dates
                        from lending.collection_covered_dates item
                        where item.transaction_id = t.id
                    ) coverage on true
                    where (
                        %s = ''
                        or client.full_name ilike %s
                        or client.client_code ilike %s
                        or loan.loan_number ilike %s
                        or t.receipt_number ilike %s
                        or coalesce(collector.full_name, '') ilike %s
                        or coalesce(collector.username, '') ilike %s
                    )
                      and (
                        %s = 'all'
                        or (%s = 'voided' and t.is_voided = true)
                        or (%s = 'unremitted'
                            and t.is_voided = false
                            and t.remittance_id is null
                            and t.is_locked = false)
                        or (%s = 'submitted'
                            and t.is_voided = false
                            and remittance.status = 'submitted')
                        or (%s = 'received'
                            and t.is_voided = false
                            and remittance.status = 'received')
                      )
                    order by t.accepted_at desc, t.id desc
                    limit %s
                    """,
                    (
                        normalized_query,
                        pattern,
                        pattern,
                        pattern,
                        pattern,
                        pattern,
                        pattern,
                        status,
                        status,
                        status,
                        status,
                        status,
                        limit,
                    ),
                )
                entries = tuple(
                    self._entry_from_row(row) for row in cursor.fetchall()
                )

                cursor.execute(
                    """
                    select *
                    from (
                        select
                            edit.id as event_id,
                            'correction'::text as event_type,
                            edit.edited_at as happened_at,
                            t.id as transaction_id,
                            t.receipt_number,
                            client.full_name as client_name,
                            loan.loan_number,
                            coalesce(
                                nullif(btrim(actor.full_name), ''),
                                nullif(btrim(actor.username), ''),
                                'SPINA staff'
                            ) as actor_name,
                            edit.reason
                        from lending.collection_transaction_edits edit
                        join lending.collection_transactions t
                          on t.id = edit.transaction_id
                        join lending.clients client on client.id = t.client_id
                        join lending.loans loan on loan.id = t.loan_id
                        left join core.users actor
                          on actor.id = edit.edited_by_user_id

                        union all

                        select
                            void.id as event_id,
                            'void'::text as event_type,
                            void.voided_at as happened_at,
                            t.id as transaction_id,
                            t.receipt_number,
                            client.full_name as client_name,
                            loan.loan_number,
                            coalesce(
                                nullif(btrim(actor.full_name), ''),
                                nullif(btrim(actor.username), ''),
                                'SPINA staff'
                            ) as actor_name,
                            void.reason
                        from lending.collection_transaction_voids void
                        join lending.collection_transactions t
                          on t.id = void.transaction_id
                        join lending.clients client on client.id = t.client_id
                        join lending.loans loan on loan.id = t.loan_id
                        left join core.users actor
                          on actor.id = void.voided_by_user_id
                    ) activity
                    order by happened_at desc, event_id desc
                    limit 20
                    """
                )
                audits = tuple(
                    self._audit_from_row(row) for row in cursor.fetchall()
                )

        return ManagementOperationsOverview(
            summary=ManagementOperationsSummary(
                latest_collection_date=latest_collection_date,
                latest_day_amount=Decimal(
                    collection_summary["latest_day_amount"] or 0
                ),
                latest_day_payment_count=int(
                    collection_summary["latest_day_payment_count"] or 0
                ),
                latest_day_unable_to_pay_count=int(
                    collection_summary["latest_day_unable_to_pay_count"] or 0
                ),
                unremitted_amount=Decimal(
                    collection_summary["unremitted_amount"] or 0
                ),
                unremitted_entry_count=int(
                    collection_summary["unremitted_entry_count"] or 0
                ),
                pending_remittance_amount=Decimal(
                    remittance_summary["pending_remittance_amount"] or 0
                ),
                pending_remittance_count=int(
                    remittance_summary["pending_remittance_count"] or 0
                ),
                received_remittance_amount=Decimal(
                    remittance_summary["received_remittance_amount"] or 0
                ),
                received_remittance_count=int(
                    remittance_summary["received_remittance_count"] or 0
                ),
                correction_count=int(audit_summary["correction_count"] or 0),
                void_count=int(audit_summary["void_count"] or 0),
            ),
            entries=entries,
            audits=audits,
        )

    @staticmethod
    def _entry_from_row(row) -> ManagementOperationEntry:
        return ManagementOperationEntry(
            transaction_id=row["transaction_id"],
            receipt_number=str(row["receipt_number"]),
            collection_date=row["collection_date"],
            accepted_at=row["accepted_at"],
            client_code=str(row["client_code"]),
            client_name=str(row["client_name"]),
            loan_number=str(row["loan_number"]),
            loan_type_name=str(row["loan_type_name"]),
            collector_name=str(row["collector_name"]),
            entry_type=str(row["entry_type"]),
            amount=Decimal(row["amount"]),
            official_balance=Decimal(row["official_balance"]),
            covered_dates=tuple(row["covered_dates"] or ()),
            edit_version=int(row["edit_version"] or 0),
            status=str(row["operation_status"]),
            remittance_number=(
                str(row["remittance_number"])
                if row["remittance_number"]
                else None
            ),
            void_reason=(str(row["void_reason"]) if row["void_reason"] else None),
        )

    @staticmethod
    def _audit_from_row(row) -> ManagementOperationAudit:
        return ManagementOperationAudit(
            event_id=row["event_id"],
            event_type=str(row["event_type"]),
            happened_at=row["happened_at"],
            transaction_id=row["transaction_id"],
            receipt_number=str(row["receipt_number"]),
            client_name=str(row["client_name"]),
            loan_number=str(row["loan_number"]),
            actor_name=str(row["actor_name"]),
            reason=str(row["reason"]),
        )
