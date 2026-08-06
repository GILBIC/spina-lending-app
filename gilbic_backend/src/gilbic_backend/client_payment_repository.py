from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection


class ClientPaymentError(RuntimeError):
    code = "client_payment_error"


class ClientPaymentBorrowerNotLinked(ClientPaymentError):
    code = "client_payment_borrower_not_linked"


@dataclass(frozen=True, slots=True)
class ClientPaymentRecord:
    transaction_id: UUID
    receipt_number: str
    loan_id: UUID
    loan_number: str
    loan_type_name: str
    collector_name: str
    collection_date: date
    recorded_at: datetime
    entry_type: str
    amount: Decimal
    covered_dates: tuple[date, ...]
    previous_balance: Decimal | None
    official_balance: Decimal | None
    note: str | None
    collection_origin: str | None
    is_voided: bool
    voided_at: datetime | None
    void_reason: str | None
    edit_version: int
    remittance_number: str | None
    remittance_status: str | None
    remittance_submitted_at: datetime | None
    remittance_received_at: datetime | None

    @property
    def status(self) -> str:
        if self.is_voided:
            return "voided"
        if self.remittance_received_at is not None or (
            self.remittance_status or ""
        ).lower() in {"received", "accepted"}:
            return "accepted"
        if self.remittance_number:
            return "remitted"
        return "posted"


@dataclass(frozen=True, slots=True)
class ClientPaymentTimeline:
    client_id: UUID
    client_code: str
    client_name: str
    payments: tuple[ClientPaymentRecord, ...]


class PostgresClientPaymentRepository:
    def list_for_user(self, *, user_id: UUID) -> ClientPaymentTimeline:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select id, client_code, full_name
                    from lending.clients
                    where user_id = %s
                    limit 1
                    """,
                    (user_id,),
                )
                client = cursor.fetchone()
                if not client:
                    raise ClientPaymentBorrowerNotLinked(
                        "This client account is not linked to a borrower record."
                    )

                cursor.execute(
                    """
                    select
                        payment.id as transaction_id,
                        payment.receipt_number,
                        payment.loan_id,
                        loan.loan_number,
                        coalesce(nullif(btrim(loan_type.name), ''), 'Loan')
                            as loan_type_name,
                        coalesce(
                            nullif(btrim(collector.full_name), ''),
                            nullif(btrim(collector.username), ''),
                            'SPINA'
                        ) as collector_name,
                        payment.collection_date,
                        payment.recorded_at,
                        payment.entry_type,
                        payment.amount,
                        case
                            when payment.is_voided then coalesce(
                                void_history.previous_covered_dates,
                                array[]::date[]
                            )
                            else coalesce(
                                covered_dates.covered_dates,
                                array[]::date[]
                            )
                        end as covered_dates,
                        payment.previous_balance,
                        payment.official_balance,
                        payment.note,
                        payment.collection_origin,
                        payment.is_voided,
                        payment.voided_at,
                        payment.void_reason,
                        payment.edit_version,
                        remittance.remittance_number,
                        remittance.status as remittance_status,
                        remittance.submitted_at as remittance_submitted_at,
                        remittance.received_at as remittance_received_at
                    from lending.collection_transactions payment
                    join lending.loans loan
                      on loan.id = payment.loan_id
                    left join lending.loan_types loan_type
                      on loan_type.id = loan.loan_type_id
                    left join core.users collector
                      on collector.id = payment.collector_user_id
                    left join lending.collection_remittances remittance
                      on remittance.id = payment.remittance_id
                    left join lateral (
                        select array_agg(
                            covered.covered_date
                            order by covered.covered_date
                        ) as covered_dates
                        from lending.collection_covered_dates covered
                        where covered.transaction_id = payment.id
                    ) covered_dates on true
                    left join lateral (
                        select history.previous_covered_dates
                        from lending.collection_transaction_voids history
                        where history.transaction_id = payment.id
                        order by history.voided_at desc, history.id desc
                        limit 1
                    ) void_history on true
                    where payment.client_id = %s
                      and payment.amount > 0
                    order by
                        payment.collection_date desc,
                        payment.recorded_at desc,
                        payment.id desc
                    """,
                    (client["id"],),
                )
                rows = cursor.fetchall()

        return ClientPaymentTimeline(
            client_id=client["id"],
            client_code=str(client["client_code"]),
            client_name=str(client["full_name"]),
            payments=tuple(self._payment_from_row(row) for row in rows),
        )

    @staticmethod
    def _payment_from_row(row) -> ClientPaymentRecord:
        raw_dates = row["covered_dates"] or []
        return ClientPaymentRecord(
            transaction_id=row["transaction_id"],
            receipt_number=str(row["receipt_number"]),
            loan_id=row["loan_id"],
            loan_number=str(row["loan_number"]),
            loan_type_name=str(row["loan_type_name"]),
            collector_name=str(row["collector_name"]),
            collection_date=row["collection_date"],
            recorded_at=row["recorded_at"],
            entry_type=str(row["entry_type"]),
            amount=Decimal(row["amount"]),
            covered_dates=tuple(raw_dates),
            previous_balance=(
                Decimal(row["previous_balance"])
                if row["previous_balance"] is not None
                else None
            ),
            official_balance=(
                Decimal(row["official_balance"])
                if row["official_balance"] is not None
                else None
            ),
            note=str(row["note"]) if row["note"] else None,
            collection_origin=(
                str(row["collection_origin"])
                if row["collection_origin"]
                else None
            ),
            is_voided=bool(row["is_voided"]),
            voided_at=row["voided_at"],
            void_reason=(
                str(row["void_reason"]) if row["void_reason"] else None
            ),
            edit_version=int(row["edit_version"]),
            remittance_number=(
                str(row["remittance_number"])
                if row["remittance_number"]
                else None
            ),
            remittance_status=(
                str(row["remittance_status"])
                if row["remittance_status"]
                else None
            ),
            remittance_submitted_at=row["remittance_submitted_at"],
            remittance_received_at=row["remittance_received_at"],
        )
