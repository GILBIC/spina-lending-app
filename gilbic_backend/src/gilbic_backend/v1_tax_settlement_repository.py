from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection


POLICY = "v1_tax_settlement_posting_v1"


class V1TaxSettlementError(RuntimeError):
    code = "v1_tax_settlement_error"


class V1TaxSettlementBlocked(V1TaxSettlementError):
    code = "v1_tax_settlement_blocked"


@dataclass(frozen=True, slots=True)
class V1TaxSettlementItem:
    tax_return_id: UUID
    tax_type: str
    return_period_start: date
    return_period_end: date
    filing_date: date
    declared_tax_due: Decimal
    return_reference: str
    return_evidence_reference: str
    return_evidence_digest: str
    return_recorded_by_user_id: UUID
    return_recorded_at: datetime
    liability_count: int
    current_exact_count: int
    liability_total: Decimal
    payment_evidence_id: UUID | None
    payment_date: date | None
    payment_amount: Decimal | None
    cash_account_system_key: str | None
    cash_account_code: str | None
    cash_account_name: str | None
    payment_reference: str | None
    payment_evidence_reference: str | None
    payment_evidence_digest: str | None
    payment_recorded_by_user_id: UUID | None
    payment_recorded_at: datetime | None
    preparation_id: UUID | None
    journal_entry_id: UUID | None
    journal_status: str | None
    entry_number: str | None
    fiscal_period_id: UUID | None
    prepared_by_user_id: UUID | None
    prepared_at: datetime | None
    settlement_posting_id: UUID | None
    confirmation_digest: str | None
    posted_by_user_id: UUID | None
    posted_at: datetime | None
    settlement_status: str
    settlement_blocker: str | None
    tax_settlement_enabled: bool
    tax_adjustment_reversal_enabled: bool
    automatic_source_posting: bool


class PostgresV1TaxSettlementRepository:
    _COLUMNS = """
        tax_return_id, tax_type, return_period_start, return_period_end,
        filing_date, declared_tax_due, return_reference,
        return_evidence_reference, return_evidence_digest,
        return_recorded_by_user_id, return_recorded_at, liability_count,
        current_exact_count, liability_total, payment_evidence_id, payment_date,
        payment_amount, cash_account_system_key, cash_account_code,
        cash_account_name, payment_reference, payment_evidence_reference,
        payment_evidence_digest, payment_recorded_by_user_id,
        payment_recorded_at, preparation_id, journal_entry_id, journal_status,
        entry_number, fiscal_period_id, prepared_by_user_id, prepared_at,
        settlement_posting_id, confirmation_digest, posted_by_user_id, posted_at,
        settlement_status, settlement_blocker, tax_settlement_enabled,
        tax_adjustment_reversal_enabled, automatic_source_posting
    """

    def list_items(
        self, *, status: str = "all", limit: int = 100, offset: int = 0
    ) -> tuple[V1TaxSettlementItem, ...]:
        where = self._status_where(status)
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {self._COLUMNS}
                    FROM accounting.v1_tax_settlement_queue
                    WHERE {where}
                    ORDER BY return_period_end DESC, filing_date DESC, tax_return_id
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                return tuple(
                    V1TaxSettlementItem(**dict(row)) for row in cursor.fetchall()
                )

    def get_item(self, tax_return_id: UUID) -> V1TaxSettlementItem:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {self._COLUMNS}
                    FROM accounting.v1_tax_settlement_queue
                    WHERE tax_return_id=%s
                    """,
                    (tax_return_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise V1TaxSettlementBlocked("V1 tax return/settlement item was not found.")
                return V1TaxSettlementItem(**dict(row))

    def get_item_by_payment(self, payment_evidence_id: UUID) -> V1TaxSettlementItem:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {self._COLUMNS}
                    FROM accounting.v1_tax_settlement_queue
                    WHERE payment_evidence_id=%s
                    """,
                    (payment_evidence_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise V1TaxSettlementBlocked("V1 tax payment/settlement item was not found.")
                return V1TaxSettlementItem(**dict(row))

    def summary(self) -> dict[str, object]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute("SELECT * FROM accounting.v1_tax_settlement_summary")
                row = cursor.fetchone()
                if row is None:
                    raise V1TaxSettlementError("V1 tax settlement summary is unavailable.")
                return dict(row)

    def record_return_evidence(
        self,
        *,
        actor_user_id: UUID,
        idempotency_key: UUID,
        tax_type: str,
        return_period_start: date,
        return_period_end: date,
        filing_date: date,
        declared_tax_due: Decimal,
        return_reference: str,
        evidence_reference: str,
        evidence_digest: str,
        evidence_note: str,
        liability_posting_ids: tuple[UUID, ...],
    ) -> UUID:
        return self._call_id(
            """
            SELECT accounting.record_v1_tax_return_evidence(
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            ) AS id
            """,
            (
                actor_user_id,
                idempotency_key,
                tax_type,
                return_period_start,
                return_period_end,
                filing_date,
                declared_tax_due,
                return_reference,
                evidence_reference,
                evidence_digest,
                evidence_note,
                list(liability_posting_ids),
            ),
        )

    def record_payment_evidence(
        self,
        *,
        actor_user_id: UUID,
        idempotency_key: UUID,
        tax_return_id: UUID,
        payment_date: date,
        payment_amount: Decimal,
        cash_account_system_key: str,
        payment_reference: str,
        evidence_reference: str,
        evidence_digest: str,
        evidence_note: str,
    ) -> UUID:
        return self._call_id(
            """
            SELECT accounting.record_v1_tax_payment_evidence(
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            ) AS id
            """,
            (
                actor_user_id,
                idempotency_key,
                tax_return_id,
                payment_date,
                payment_amount,
                cash_account_system_key,
                payment_reference,
                evidence_reference,
                evidence_digest,
                evidence_note,
            ),
        )

    def prepare(
        self, *, payment_evidence_id: UUID, actor_user_id: UUID
    ) -> UUID:
        return self._call_id(
            "SELECT accounting.prepare_v1_tax_settlement_journal(%s,%s) AS id",
            (payment_evidence_id, actor_user_id),
        )

    def post(
        self,
        *,
        payment_evidence_id: UUID,
        actor_user_id: UUID,
        confirmation_token: str,
        expected_return_evidence_digest: str,
        expected_payment_evidence_digest: str,
        expected_payment_amount: Decimal,
        expected_tax_payable_account_code: str,
        expected_cash_account_code: str,
        expected_posting_date: date,
        expected_fiscal_period_id: UUID,
        policy_version: str = POLICY,
    ) -> UUID:
        return self._call_id(
            """
            SELECT accounting.post_v1_tax_settlement_journal(
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            ) AS id
            """,
            (
                payment_evidence_id,
                actor_user_id,
                confirmation_token,
                expected_return_evidence_digest,
                expected_payment_evidence_digest,
                expected_payment_amount,
                expected_tax_payable_account_code,
                expected_cash_account_code,
                expected_posting_date,
                expected_fiscal_period_id,
                policy_version,
            ),
        )

    @staticmethod
    def _status_where(status: str) -> str:
        clauses = {
            "all": "true",
            "awaiting_payment": "settlement_status = 'return_recorded_awaiting_payment'",
            "ready": "settlement_status = 'payment_evidence_ready'",
            "prepared": "settlement_status = 'settlement_prepared'",
            "settled": "settlement_status = 'settled'",
            "adjustment_review": "settlement_status = 'settled_adjustment_review_required'",
            "blocked": "settlement_status LIKE 'blocked_%' OR settlement_status LIKE 'prepared_blocked_%'",
        }
        clause = clauses.get(status)
        if clause is None:
            raise ValueError("Unsupported V1 tax settlement status filter.")
        return clause

    @staticmethod
    def _call_id(query: str, params: tuple[object, ...]) -> UUID:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(query, params)
                    row = cursor.fetchone()
                    if row is None or row["id"] is None:
                        raise V1TaxSettlementBlocked(
                            "Protected V1 tax settlement action returned no immutable identifier."
                        )
                    result = UUID(str(row["id"]))
                connection.commit()
                return result
        except V1TaxSettlementError:
            raise
        except psycopg.Error as exc:
            message = str(exc).split("CONTEXT:", 1)[0].strip()
            raise V1TaxSettlementBlocked(message) from exc
