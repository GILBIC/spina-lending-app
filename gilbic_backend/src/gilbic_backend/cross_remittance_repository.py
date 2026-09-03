from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .database import open_connection
from .remittance_repository import (
    PostgresRemittanceRepository,
    RemittanceEmpty,
    RemittanceError,
    RemittanceItemRecord,
    RemittanceRecord,
    RemittanceRecipientInvalid,
    RemittanceSummaryRecord,
)


ASSIGNED_COLLECTOR_CAPACITY = "assigned_collector"
MANAGEMENT_CAPACITY = "management"


@dataclass(frozen=True, slots=True)
class CrossRemittanceTargetRecord:
    recipient_user_id: UUID
    recipient_name: str
    transaction_count: int
    client_count: int
    total_amount: Decimal
    recipient_capacity: str = ASSIGNED_COLLECTOR_CAPACITY


class PostgresCrossRemittanceRepository:
    def list_targets(
        self,
        *,
        collector_user_id: UUID,
        collection_date: date,
    ) -> tuple[CrossRemittanceTargetRecord, ...]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        transaction.assigned_collector_user_id as recipient_user_id,
                        recipient.full_name as recipient_name,
                        count(*)::integer as transaction_count,
                        count(distinct transaction.client_id)::integer as client_count,
                        coalesce(
                            sum(transaction.amount)
                                filter (where transaction.entry_type <> 'pass'),
                            0
                        ) as total_amount
                    from lending.collection_transactions transaction
                    join core.users recipient
                      on recipient.id = transaction.assigned_collector_user_id
                     and recipient.status = 'active'
                    where transaction.collector_user_id = %s
                      and transaction.collection_date = %s
                      and transaction.collection_origin = 'cross_collector'
                      and transaction.assigned_collector_user_id is not null
                      and transaction.remittance_id is null
                      and transaction.is_locked = false
                      and transaction.is_voided = false
                    group by
                        transaction.assigned_collector_user_id,
                        recipient.full_name
                    order by
                        lower(recipient.full_name),
                        transaction.assigned_collector_user_id
                    """,
                    (collector_user_id, collection_date),
                )
                assigned_rows = cursor.fetchall()

                cursor.execute(
                    """
                    select
                        count(*)::integer as transaction_count,
                        count(distinct transaction.client_id)::integer as client_count,
                        coalesce(
                            sum(transaction.amount)
                                filter (where transaction.entry_type <> 'pass'),
                            0
                        ) as total_amount
                    from lending.collection_transactions transaction
                    where transaction.collector_user_id = %s
                      and transaction.collection_date = %s
                      and transaction.collection_origin = 'cross_collector'
                      and transaction.remittance_id is null
                      and transaction.is_locked = false
                      and transaction.is_voided = false
                    """,
                    (collector_user_id, collection_date),
                )
                management_summary = cursor.fetchone()

                management_rows = ()
                if management_summary and int(management_summary["transaction_count"]) > 0:
                    cursor.execute(
                        """
                        select distinct
                            user_account.id as recipient_user_id,
                            user_account.full_name as recipient_name
                        from core.users user_account
                        join core.user_roles user_role
                          on user_role.user_id = user_account.id
                        join core.roles role
                          on role.id = user_role.role_id
                        where user_account.status = 'active'
                          and user_account.id <> %s
                          and role.code = 'management'
                        order by lower(user_account.full_name), user_account.id
                        """,
                        (collector_user_id,),
                    )
                    management_rows = cursor.fetchall()

        targets = [
            CrossRemittanceTargetRecord(
                recipient_user_id=row["recipient_user_id"],
                recipient_name=str(row["recipient_name"]),
                transaction_count=int(row["transaction_count"]),
                client_count=int(row["client_count"]),
                total_amount=Decimal(row["total_amount"]),
                recipient_capacity=ASSIGNED_COLLECTOR_CAPACITY,
            )
            for row in assigned_rows
        ]
        if management_summary:
            targets.extend(
                CrossRemittanceTargetRecord(
                    recipient_user_id=row["recipient_user_id"],
                    recipient_name=str(row["recipient_name"]),
                    transaction_count=int(management_summary["transaction_count"]),
                    client_count=int(management_summary["client_count"]),
                    total_amount=Decimal(management_summary["total_amount"]),
                    recipient_capacity=MANAGEMENT_CAPACITY,
                )
                for row in management_rows
            )
        return tuple(targets)

    def preview(
        self,
        *,
        collector_user_id: UUID,
        recipient_user_id: UUID,
        collection_date: date,
        recipient_capacity: str = ASSIGNED_COLLECTOR_CAPACITY,
    ) -> RemittanceSummaryRecord:
        capacity = self._normalize_capacity(recipient_capacity)
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                collector_name = PostgresRemittanceRepository._user_name(
                    cursor,
                    collector_user_id,
                )
                self._verify_recipient(
                    cursor,
                    recipient_user_id=recipient_user_id,
                    recipient_capacity=capacity,
                )
                items = self._eligible_items(
                    cursor,
                    collector_user_id=collector_user_id,
                    recipient_user_id=recipient_user_id,
                    recipient_capacity=capacity,
                    collection_date=collection_date,
                    for_update=False,
                )
        return PostgresRemittanceRepository._summary(
            collector_user_id=collector_user_id,
            collector_name=collector_name,
            collection_date=collection_date,
            items=items,
        )

    def submit(
        self,
        *,
        collector_user_id: UUID,
        recipient_user_id: UUID,
        collection_date: date,
        note: str,
        recipient_capacity: str = ASSIGNED_COLLECTOR_CAPACITY,
    ) -> RemittanceRecord:
        capacity = self._normalize_capacity(recipient_capacity)
        if collector_user_id == recipient_user_id:
            raise RemittanceRecipientInvalid(
                "Choose another person to receive the remittance."
            )

        with open_connection() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                        (
                            f"gilbic-cross-remittance:{collector_user_id}:"
                            f"{collection_date}",
                        ),
                    )
                    collector_name = PostgresRemittanceRepository._user_name(
                        cursor,
                        collector_user_id,
                    )
                    recipient_name = self._verify_recipient(
                        cursor,
                        recipient_user_id=recipient_user_id,
                        recipient_capacity=capacity,
                    )
                    items = self._eligible_items(
                        cursor,
                        collector_user_id=collector_user_id,
                        recipient_user_id=recipient_user_id,
                        recipient_capacity=capacity,
                        collection_date=collection_date,
                        for_update=True,
                    )
                    summary = PostgresRemittanceRepository._summary(
                        collector_user_id=collector_user_id,
                        collector_name=collector_name,
                        collection_date=collection_date,
                        items=items,
                    )
                    if not summary.items:
                        if capacity == MANAGEMENT_CAPACITY:
                            message = (
                                "There are no unlocked other-area payments available "
                                "to remit to Management."
                            )
                        else:
                            message = (
                                "There are no unlocked other-area payments for this "
                                "assigned collector."
                            )
                        raise RemittanceEmpty(message)

                    submitted_at = datetime.now(timezone.utc)
                    remittance_id = uuid4()
                    remittance_number = PostgresRemittanceRepository._next_number(
                        cursor,
                        collection_date=collection_date,
                    )
                    normalized_note = note.strip()
                    cursor.execute(
                        """
                        insert into lending.collection_remittances (
                            id,
                            remittance_number,
                            collector_user_id,
                            recipient_user_id,
                            recipient_capacity,
                            collection_date,
                            status,
                            transaction_count,
                            payment_count,
                            unable_to_pay_count,
                            covered_payment_count,
                            client_count,
                            total_amount,
                            note,
                            submitted_at,
                            created_at,
                            updated_at
                        ) values (
                            %s, %s, %s, %s, %s, %s, 'submitted',
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        """,
                        (
                            remittance_id,
                            remittance_number,
                            collector_user_id,
                            recipient_user_id,
                            capacity,
                            collection_date,
                            summary.transaction_count,
                            summary.payment_count,
                            summary.unable_to_pay_count,
                            summary.covered_payment_count,
                            summary.client_count,
                            summary.total_amount,
                            normalized_note,
                            submitted_at,
                            submitted_at,
                            submitted_at,
                        ),
                    )

                    for item in summary.items:
                        cursor.execute(
                            """
                            insert into lending.collection_remittance_items (
                                remittance_id,
                                transaction_id,
                                client_id,
                                loan_id,
                                collection_date,
                                entry_type,
                                amount,
                                receipt_number,
                                transaction_snapshot
                            ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                remittance_id,
                                item.transaction_id,
                                item.client_id,
                                item.loan_id,
                                item.collection_date,
                                item.entry_type,
                                item.amount,
                                item.receipt_number,
                                Jsonb(
                                    PostgresRemittanceRepository._item_payload(item)
                                ),
                            ),
                        )

                    transaction_ids = [item.transaction_id for item in summary.items]
                    if capacity == ASSIGNED_COLLECTOR_CAPACITY:
                        cursor.execute(
                            """
                            update lending.collection_transactions
                            set remittance_id = %s,
                                is_locked = true,
                                locked_at = %s,
                                locked_by_user_id = %s,
                                updated_at = %s,
                                updated_by_user_id = %s
                            where id = any(%s)
                              and collector_user_id = %s
                              and assigned_collector_user_id = %s
                              and collection_origin = 'cross_collector'
                              and remittance_id is null
                              and is_locked = false
                              and is_voided = false
                            """,
                            (
                                remittance_id,
                                submitted_at,
                                collector_user_id,
                                submitted_at,
                                collector_user_id,
                                transaction_ids,
                                collector_user_id,
                                recipient_user_id,
                            ),
                        )
                    else:
                        cursor.execute(
                            """
                            update lending.collection_transactions
                            set remittance_id = %s,
                                is_locked = true,
                                locked_at = %s,
                                locked_by_user_id = %s,
                                updated_at = %s,
                                updated_by_user_id = %s
                            where id = any(%s)
                              and collector_user_id = %s
                              and collection_origin = 'cross_collector'
                              and remittance_id is null
                              and is_locked = false
                              and is_voided = false
                            """,
                            (
                                remittance_id,
                                submitted_at,
                                collector_user_id,
                                submitted_at,
                                collector_user_id,
                                transaction_ids,
                                collector_user_id,
                            ),
                        )
                    if cursor.rowcount != len(transaction_ids):
                        raise RemittanceError(
                            "An other-area payment changed while the remittance was being submitted. Refresh and review it."
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
                        ) values (
                            %s,
                            'remittance.cross_collector.submitted',
                            'collection_remittance',
                            %s,
                            %s,
                            %s
                        )
                        """,
                        (
                            collector_user_id,
                            remittance_id,
                            Jsonb(
                                {
                                    "remittance_number": remittance_number,
                                    "recipient_user_id": str(recipient_user_id),
                                    "recipient_capacity": capacity,
                                    "transaction_count": summary.transaction_count,
                                    "client_count": summary.client_count,
                                    "total_amount": str(summary.total_amount),
                                }
                            ),
                            submitted_at,
                        ),
                    )

        return RemittanceRecord(
            remittance_id=remittance_id,
            remittance_number=remittance_number,
            collector_user_id=collector_user_id,
            collector_name=collector_name,
            recipient_user_id=recipient_user_id,
            recipient_name=recipient_name,
            collection_date=collection_date,
            status="submitted",
            transaction_count=summary.transaction_count,
            payment_count=summary.payment_count,
            unable_to_pay_count=summary.unable_to_pay_count,
            covered_payment_count=summary.covered_payment_count,
            client_count=summary.client_count,
            total_amount=summary.total_amount,
            note=normalized_note,
            submitted_at=submitted_at,
            received_at=None,
            items=summary.items,
        )

    @staticmethod
    def _normalize_capacity(recipient_capacity: str) -> str:
        capacity = recipient_capacity.strip().lower()
        if capacity not in {ASSIGNED_COLLECTOR_CAPACITY, MANAGEMENT_CAPACITY}:
            raise RemittanceRecipientInvalid(
                "Choose either the assigned Collector or Management as the remittance recipient."
            )
        return capacity

    @classmethod
    def _verify_recipient(
        cls,
        cursor,
        *,
        recipient_user_id: UUID,
        recipient_capacity: str,
    ) -> str:
        if recipient_capacity == MANAGEMENT_CAPACITY:
            return cls._verify_management(
                cursor,
                recipient_user_id=recipient_user_id,
            )
        return cls._verify_assigned_collector(
            cursor,
            recipient_user_id=recipient_user_id,
        )

    @staticmethod
    def _verify_assigned_collector(cursor, *, recipient_user_id: UUID) -> str:
        cursor.execute(
            """
            select user_account.full_name
            from core.users user_account
            where user_account.id = %s
              and user_account.status = 'active'
              and exists (
                  select 1
                  from core.user_roles user_role
                  join core.roles role on role.id = user_role.role_id
                  where user_role.user_id = user_account.id
                    and role.code = 'collector'
              )
            """,
            (recipient_user_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise RemittanceRecipientInvalid(
                "The assigned collector is not active or cannot receive remittances."
            )
        return str(row["full_name"])

    @staticmethod
    def _verify_management(cursor, *, recipient_user_id: UUID) -> str:
        cursor.execute(
            """
            select user_account.full_name
            from core.users user_account
            where user_account.id = %s
              and user_account.status = 'active'
              and exists (
                  select 1
                  from core.user_roles user_role
                  join core.roles role on role.id = user_role.role_id
                  where user_role.user_id = user_account.id
                    and role.code = 'management'
              )
            """,
            (recipient_user_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise RemittanceRecipientInvalid(
                "The selected Management account is not active or cannot receive remittances."
            )
        return str(row["full_name"])

    @staticmethod
    def _eligible_items(
        cursor,
        *,
        collector_user_id: UUID,
        recipient_user_id: UUID,
        recipient_capacity: str,
        collection_date: date,
        for_update: bool,
    ) -> tuple[RemittanceItemRecord, ...]:
        lock_clause = "for update of transaction" if for_update else ""
        assigned_filter = ""
        params: tuple[object, ...]
        if recipient_capacity == ASSIGNED_COLLECTOR_CAPACITY:
            assigned_filter = "and transaction.assigned_collector_user_id = %s"
            params = (collector_user_id, recipient_user_id, collection_date)
        else:
            params = (collector_user_id, collection_date)
        cursor.execute(
            f"""
            select
                transaction.id as transaction_id,
                transaction.client_id,
                client.full_name as client_name,
                transaction.loan_id,
                loan_type.name as loan_type,
                transaction.collection_date,
                transaction.entry_type,
                transaction.amount,
                transaction.receipt_number,
                transaction.accepted_at,
                transaction.note,
                coalesce(covered.dates, ARRAY[]::date[]) as covered_dates
            from lending.collection_transactions transaction
            join lending.clients client on client.id = transaction.client_id
            join lending.loans loan on loan.id = transaction.loan_id
            join lending.loan_types loan_type on loan_type.id = loan.loan_type_id
            left join lateral (
                select array_agg(date_row.covered_date order by date_row.covered_date)
                    as dates
                from lending.collection_covered_dates date_row
                where date_row.transaction_id = transaction.id
            ) covered on true
            where transaction.collector_user_id = %s
              {assigned_filter}
              and transaction.collection_origin = 'cross_collector'
              and transaction.collection_date = %s
              and transaction.remittance_id is null
              and transaction.is_locked = false
              and transaction.is_voided = false
            order by transaction.accepted_at, transaction.id
            {lock_clause}
            """,
            params,
        )
        return tuple(
            PostgresRemittanceRepository._item_from_row(row)
            for row in cursor.fetchall()
        )
