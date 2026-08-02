from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .database import open_connection


class RemittanceError(RuntimeError):
    code = "remittance_error"


class RemittanceEmpty(RemittanceError):
    code = "remittance_empty"


class RemittanceNotFound(RemittanceError):
    code = "remittance_not_found"


class RemittanceRecipientInvalid(RemittanceError):
    code = "remittance_recipient_invalid"


class RemittanceAlreadyReceived(RemittanceError):
    code = "remittance_already_received"


@dataclass(frozen=True, slots=True)
class RemittanceRecipientRecord:
    user_id: UUID
    full_name: str
    role_name: str


@dataclass(frozen=True, slots=True)
class RemittanceItemRecord:
    transaction_id: UUID
    client_id: UUID
    client_name: str
    loan_id: UUID
    loan_type: str
    collection_date: date
    entry_type: str
    amount: Decimal
    receipt_number: str
    accepted_at: datetime
    note: str
    covered_dates: tuple[date, ...]


@dataclass(frozen=True, slots=True)
class RemittanceSummaryRecord:
    collection_date: date
    collector_user_id: UUID
    collector_name: str
    transaction_count: int
    payment_count: int
    unable_to_pay_count: int
    covered_payment_count: int
    client_count: int
    total_amount: Decimal
    items: tuple[RemittanceItemRecord, ...]


@dataclass(frozen=True, slots=True)
class RemittanceRecord:
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


class PostgresRemittanceRepository:
    def list_recipients(
        self,
        *,
        actor_user_id: UUID,
    ) -> tuple[RemittanceRecipientRecord, ...]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select distinct
                        u.id,
                        u.full_name,
                        case
                            when bool_or(r.code = 'management') then 'Management'
                            else 'Employee'
                        end as role_name
                    from core.users u
                    join core.user_roles ur on ur.user_id = u.id
                    join core.roles r on r.id = ur.role_id
                    where u.status = 'active'
                      and u.id <> %s
                      and r.code in ('employee', 'management')
                    group by u.id, u.full_name
                    order by lower(u.full_name), u.id
                    """,
                    (actor_user_id,),
                )
                rows = cursor.fetchall()
        return tuple(
            RemittanceRecipientRecord(
                user_id=row["id"],
                full_name=str(row["full_name"]),
                role_name=str(row["role_name"]),
            )
            for row in rows
        )

    def preview(
        self,
        *,
        collector_user_id: UUID,
        collection_date: date,
    ) -> RemittanceSummaryRecord:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                items = self._eligible_items(
                    cursor,
                    collector_user_id=collector_user_id,
                    collection_date=collection_date,
                    for_update=False,
                )
                collector_name = self._user_name(cursor, collector_user_id)
        return self._summary(
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
    ) -> RemittanceRecord:
        if collector_user_id == recipient_user_id:
            raise RemittanceRecipientInvalid(
                "Choose another person to receive the remittance."
            )

        with open_connection() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                        (f"gilbic-remittance:{collector_user_id}:{collection_date}",),
                    )
                    collector_name = self._user_name(cursor, collector_user_id)
                    recipient_name = self._verify_recipient(
                        cursor,
                        recipient_user_id=recipient_user_id,
                    )
                    items = self._eligible_items(
                        cursor,
                        collector_user_id=collector_user_id,
                        collection_date=collection_date,
                        for_update=True,
                    )
                    summary = self._summary(
                        collector_user_id=collector_user_id,
                        collector_name=collector_name,
                        collection_date=collection_date,
                        items=items,
                    )
                    if not summary.items:
                        raise RemittanceEmpty(
                            "There are no unlocked collections available to remit."
                        )

                    submitted_at = datetime.now(timezone.utc)
                    remittance_id = uuid4()
                    remittance_number = self._next_number(
                        cursor,
                        collection_date=collection_date,
                    )
                    cursor.execute(
                        """
                        insert into lending.collection_remittances (
                            id,
                            remittance_number,
                            collector_user_id,
                            recipient_user_id,
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
                            %s, %s, %s, %s, %s, 'submitted',
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        """,
                        (
                            remittance_id,
                            remittance_number,
                            collector_user_id,
                            recipient_user_id,
                            collection_date,
                            summary.transaction_count,
                            summary.payment_count,
                            summary.unable_to_pay_count,
                            summary.covered_payment_count,
                            summary.client_count,
                            summary.total_amount,
                            note.strip(),
                            submitted_at,
                            submitted_at,
                            submitted_at,
                        ),
                    )

                    for item in summary.items:
                        snapshot = self._item_payload(item)
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
                                Jsonb(snapshot),
                            ),
                        )

                    transaction_ids = [item.transaction_id for item in summary.items]
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
                          and remittance_id is null
                          and is_locked = false
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
                            "A collection changed while the remittance was being submitted. Refresh and review the summary."
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
                        ) values (%s, 'remittance.submitted', 'collection_remittance', %s, %s, %s)
                        """,
                        (
                            collector_user_id,
                            remittance_id,
                            Jsonb(
                                {
                                    "remittance_number": remittance_number,
                                    "recipient_user_id": str(recipient_user_id),
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
            note=note.strip(),
            submitted_at=submitted_at,
            received_at=None,
            items=summary.items,
        )

    def list_for_user(
        self,
        *,
        actor_user_id: UUID,
    ) -> tuple[RemittanceRecord, ...]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        r.*,
                        collector.full_name as collector_name,
                        recipient.full_name as recipient_name
                    from lending.collection_remittances r
                    join core.users collector on collector.id = r.collector_user_id
                    join core.users recipient on recipient.id = r.recipient_user_id
                    where r.collector_user_id = %s or r.recipient_user_id = %s
                    order by r.submitted_at desc, r.id desc
                    """,
                    (actor_user_id, actor_user_id),
                )
                rows = cursor.fetchall()
                records = []
                for row in rows:
                    items = self._remittance_items(cursor, row["id"])
                    records.append(self._record_from_row(row, items))
        return tuple(records)

    def confirm_received(
        self,
        *,
        remittance_id: UUID,
        recipient_user_id: UUID,
    ) -> RemittanceRecord:
        with open_connection() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        select
                            r.*,
                            collector.full_name as collector_name,
                            recipient.full_name as recipient_name
                        from lending.collection_remittances r
                        join core.users collector on collector.id = r.collector_user_id
                        join core.users recipient on recipient.id = r.recipient_user_id
                        where r.id = %s
                        for update of r
                        """,
                        (remittance_id,),
                    )
                    row = cursor.fetchone()
                    if not row:
                        raise RemittanceNotFound("Remittance was not found.")
                    if row["recipient_user_id"] != recipient_user_id:
                        raise RemittanceRecipientInvalid(
                            "Only the selected recipient can confirm this remittance."
                        )
                    if row["status"] == "received":
                        raise RemittanceAlreadyReceived(
                            "This remittance was already confirmed as received."
                        )

                    received_at = datetime.now(timezone.utc)
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
                            Jsonb({"remittance_number": row["remittance_number"]}),
                            received_at,
                        ),
                    )
                    items = self._remittance_items(cursor, remittance_id)
                    updated = dict(row)
                    updated["status"] = "received"
                    updated["received_at"] = received_at
        return self._record_from_row(updated, items)

    @staticmethod
    def _user_name(cursor, user_id: UUID) -> str:
        cursor.execute(
            "select full_name from core.users where id = %s and status = 'active'",
            (user_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise RemittanceError("The signed-in account is not active.")
        return str(row["full_name"])

    @staticmethod
    def _verify_recipient(cursor, *, recipient_user_id: UUID) -> str:
        cursor.execute(
            """
            select u.full_name
            from core.users u
            where u.id = %s
              and u.status = 'active'
              and exists (
                  select 1
                  from core.user_roles ur
                  join core.roles r on r.id = ur.role_id
                  where ur.user_id = u.id
                    and r.code in ('employee', 'management')
              )
            """,
            (recipient_user_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise RemittanceRecipientInvalid(
                "The selected remittance recipient is not authorized."
            )
        return str(row["full_name"])

    @staticmethod
    def _eligible_items(
        cursor,
        *,
        collector_user_id: UUID,
        collection_date: date,
        for_update: bool,
    ) -> tuple[RemittanceItemRecord, ...]:
        lock_clause = "for update of transaction" if for_update else ""
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
            from lending.collection_transactions as transaction
            join lending.clients client on client.id = transaction.client_id
            join lending.loans loan on loan.id = transaction.loan_id
            join lending.loan_types loan_type on loan_type.id = loan.loan_type_id
            left join lateral (
                select array_agg(cd.covered_date order by cd.covered_date) as dates
                from lending.collection_covered_dates cd
                where cd.transaction_id = transaction.id
            ) covered on true
            where transaction.collector_user_id = %s
              and transaction.collection_date = %s
              and transaction.remittance_id is null
              and transaction.is_locked = false
            order by transaction.accepted_at, transaction.id
            {lock_clause}
            """,
            (collector_user_id, collection_date),
        )
        return tuple(PostgresRemittanceRepository._item_from_row(row) for row in cursor.fetchall())

    @staticmethod
    def _summary(
        *,
        collector_user_id: UUID,
        collector_name: str,
        collection_date: date,
        items: tuple[RemittanceItemRecord, ...],
    ) -> RemittanceSummaryRecord:
        payment_items = tuple(item for item in items if item.entry_type != "pass")
        unable_items = tuple(item for item in items if item.entry_type == "pass")
        covered_items = tuple(
            item
            for item in payment_items
            if item.entry_type == "advance" or len(item.covered_dates) > 1
        )
        return RemittanceSummaryRecord(
            collection_date=collection_date,
            collector_user_id=collector_user_id,
            collector_name=collector_name,
            transaction_count=len(items),
            payment_count=len(payment_items),
            unable_to_pay_count=len(unable_items),
            covered_payment_count=len(covered_items),
            client_count=len({item.client_id for item in items}),
            total_amount=sum(
                (item.amount for item in payment_items),
                start=Decimal("0.00"),
            ),
            items=items,
        )

    @staticmethod
    def _item_from_row(row) -> RemittanceItemRecord:
        return RemittanceItemRecord(
            transaction_id=row["transaction_id"],
            client_id=row["client_id"],
            client_name=str(row["client_name"]),
            loan_id=row["loan_id"],
            loan_type=str(row["loan_type"]),
            collection_date=row["collection_date"],
            entry_type=str(row["entry_type"]),
            amount=Decimal(row["amount"]),
            receipt_number=str(row["receipt_number"]),
            accepted_at=row["accepted_at"],
            note=str(row["note"] or ""),
            covered_dates=tuple(row["covered_dates"] or ()),
        )

    @staticmethod
    def _item_payload(item: RemittanceItemRecord) -> dict[str, object]:
        return {
            "transaction_id": str(item.transaction_id),
            "client_id": str(item.client_id),
            "client_name": item.client_name,
            "loan_id": str(item.loan_id),
            "loan_type": item.loan_type,
            "collection_date": item.collection_date.isoformat(),
            "entry_type": item.entry_type,
            "amount": str(item.amount),
            "receipt_number": item.receipt_number,
            "accepted_at": item.accepted_at.isoformat(),
            "note": item.note,
            "covered_dates": [value.isoformat() for value in item.covered_dates],
        }

    @staticmethod
    def _remittance_items(cursor, remittance_id: UUID) -> tuple[RemittanceItemRecord, ...]:
        cursor.execute(
            """
            select
                item.transaction_id,
                item.client_id,
                coalesce(item.transaction_snapshot->>'client_name', client.full_name) as client_name,
                item.loan_id,
                coalesce(item.transaction_snapshot->>'loan_type', loan_type.name) as loan_type,
                item.collection_date,
                item.entry_type,
                item.amount,
                item.receipt_number,
                coalesce(
                    (item.transaction_snapshot->>'accepted_at')::timestamptz,
                    transaction.accepted_at
                ) as accepted_at,
                coalesce(item.transaction_snapshot->>'note', '') as note,
                coalesce(
                    array(
                        select jsonb_array_elements_text(
                            coalesce(item.transaction_snapshot->'covered_dates', '[]'::jsonb)
                        )::date
                    ),
                    ARRAY[]::date[]
                ) as covered_dates
            from lending.collection_remittance_items item
            join lending.collection_transactions transaction
              on transaction.id = item.transaction_id
            join lending.clients client on client.id = item.client_id
            join lending.loans loan on loan.id = item.loan_id
            join lending.loan_types loan_type on loan_type.id = loan.loan_type_id
            where item.remittance_id = %s
            order by transaction.accepted_at, item.transaction_id
            """,
            (remittance_id,),
        )
        return tuple(PostgresRemittanceRepository._item_from_row(row) for row in cursor.fetchall())

    @staticmethod
    def _record_from_row(row, items: tuple[RemittanceItemRecord, ...]) -> RemittanceRecord:
        return RemittanceRecord(
            remittance_id=row["id"],
            remittance_number=str(row["remittance_number"]),
            collector_user_id=row["collector_user_id"],
            collector_name=str(row["collector_name"]),
            recipient_user_id=row["recipient_user_id"],
            recipient_name=str(row["recipient_name"]),
            collection_date=row["collection_date"],
            status=str(row["status"]),
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
        )

    @staticmethod
    def _next_number(cursor, *, collection_date: date) -> str:
        cursor.execute("select nextval('lending.collection_remittance_sequence')")
        sequence = int(cursor.fetchone()["nextval"])
        return f"REM-{collection_date:%Y%m%d}-{sequence:08d}"
