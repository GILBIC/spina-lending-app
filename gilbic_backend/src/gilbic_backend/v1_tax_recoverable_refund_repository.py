from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection


POLICY = "v1_tax_recoverable_refund_posting_v1"


class V1TaxRecoverableRefundError(RuntimeError):
    code = "v1_tax_recoverable_refund_error"


class V1TaxRecoverableRefundBlocked(V1TaxRecoverableRefundError):
    code = "v1_tax_recoverable_refund_blocked"


@dataclass(frozen=True, slots=True)
class V1TaxRecoverableRefundItem:
    refund_evidence_id: UUID
    adjustment_posting_id: UUID
    adjustment_evidence_id: UUID
    tax_type: str
    source_id: UUID
    loan_id: UUID
    client_id: UUID
    refund_amount: Decimal
    refund_date: date
    cash_account_id: UUID
    cash_account_code: str
    cash_account_name: str
    refund_reference: str
    authority_reference: str
    evidence_digest: str
    recorded_by_user_id: UUID
    recorded_at: datetime
    preparation_id: UUID | None
    journal_entry_id: UUID | None
    journal_status: str | None
    entry_number: str | None
    fiscal_period_id: UUID | None
    tax_recoverable_account_id: UUID | None
    tax_recoverable_account_code: str | None
    tax_recoverable_account_name: str | None
    prepared_by_user_id: UUID | None
    prepared_at: datetime | None
    refund_posting_id: UUID | None
    confirmation_digest: str | None
    posted_by_user_id: UUID | None
    posted_at: datetime | None
    refund_status: str
    refund_blocker: str | None
    tax_recoverable_refund_realization_enabled: bool
    tax_recoverable_credit_application_enabled: bool
    automatic_source_posting: bool


class PostgresV1TaxRecoverableRefundRepository:
    _COLUMNS = """
        refund_evidence_id, adjustment_posting_id, adjustment_evidence_id,
        tax_type, source_id, loan_id, client_id, refund_amount, refund_date,
        cash_account_id, cash_account_code, cash_account_name, refund_reference,
        authority_reference, evidence_digest, recorded_by_user_id, recorded_at,
        preparation_id, journal_entry_id, journal_status, entry_number,
        fiscal_period_id, tax_recoverable_account_id,
        tax_recoverable_account_code, tax_recoverable_account_name,
        prepared_by_user_id, prepared_at, refund_posting_id,
        confirmation_digest, posted_by_user_id, posted_at, refund_status,
        refund_blocker, tax_recoverable_refund_realization_enabled,
        tax_recoverable_credit_application_enabled, automatic_source_posting
    """

    def list_items(
        self, *, status: str = "all", limit: int = 100, offset: int = 0
    ) -> tuple[V1TaxRecoverableRefundItem, ...]:
        where = self._status_where(status)
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {self._COLUMNS}
                    FROM accounting.v1_tax_recoverable_refund_queue
                    WHERE {where}
                    ORDER BY refund_date DESC, recorded_at DESC, refund_evidence_id
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                return tuple(
                    V1TaxRecoverableRefundItem(**dict(row)) for row in cursor.fetchall()
                )

    def get_item(self, refund_evidence_id: UUID) -> V1TaxRecoverableRefundItem:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {self._COLUMNS}
                    FROM accounting.v1_tax_recoverable_refund_queue
                    WHERE refund_evidence_id=%s
                    """,
                    (refund_evidence_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise V1TaxRecoverableRefundBlocked(
                        "V1 Tax Recoverable refund evidence item was not found."
                    )
                return V1TaxRecoverableRefundItem(**dict(row))

    def summary(self) -> dict[str, object]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    "SELECT * FROM accounting.v1_tax_recoverable_refund_summary"
                )
                row = cursor.fetchone()
                if row is None:
                    raise V1TaxRecoverableRefundError(
                        "V1 Tax Recoverable refund summary is unavailable."
                    )
                return dict(row)

    def record_evidence(
        self,
        *,
        actor_user_id: UUID,
        idempotency_key: UUID,
        adjustment_posting_id: UUID,
        refund_date: date,
        cash_account_code: str,
        refund_reference: str,
        authority_reference: str,
        evidence_digest: str,
        evidence_note: str,
    ) -> UUID:
        return self._call_id(
            """
            SELECT accounting.record_v1_tax_recoverable_refund_evidence(
                %s,%s,%s,%s,%s,%s,%s,%s,%s
            ) AS id
            """,
            (
                actor_user_id,
                idempotency_key,
                adjustment_posting_id,
                refund_date,
                cash_account_code,
                refund_reference,
                authority_reference,
                evidence_digest,
                evidence_note,
            ),
        )

    def prepare(self, *, refund_evidence_id: UUID, actor_user_id: UUID) -> UUID:
        return self._call_id(
            "SELECT accounting.prepare_v1_tax_recoverable_refund_journal(%s,%s) AS id",
            (refund_evidence_id, actor_user_id),
        )

    def post(
        self,
        *,
        refund_evidence_id: UUID,
        actor_user_id: UUID,
        confirmation_token: str,
        expected_evidence_digest: str,
        expected_refund_amount: Decimal,
        expected_cash_account_code: str,
        expected_tax_recoverable_account_code: str,
        expected_posting_date: date,
        expected_fiscal_period_id: UUID,
        policy_version: str = POLICY,
    ) -> UUID:
        return self._call_id(
            """
            SELECT accounting.post_v1_tax_recoverable_refund_journal(
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            ) AS id
            """,
            (
                refund_evidence_id,
                actor_user_id,
                confirmation_token,
                expected_evidence_digest,
                expected_refund_amount,
                expected_cash_account_code,
                expected_tax_recoverable_account_code,
                expected_posting_date,
                expected_fiscal_period_id,
                policy_version,
            ),
        )

    @staticmethod
    def _status_where(status: str) -> str:
        clauses = {
            "all": "true",
            "ready": "refund_status = 'refund_evidence_ready'",
            "prepared": "refund_status = 'refund_prepared'",
            "realized": "refund_status = 'refund_realized'",
            "blocked": "refund_status LIKE 'blocked_%'",
        }
        clause = clauses.get(status)
        if clause is None:
            raise ValueError("Unsupported V1 Tax Recoverable refund status filter.")
        return clause

    @staticmethod
    def _call_id(query: str, params: tuple[object, ...]) -> UUID:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(query, params)
                    row = cursor.fetchone()
                    if row is None or row["id"] is None:
                        raise V1TaxRecoverableRefundBlocked(
                            "Protected V1 Tax Recoverable refund action returned no immutable identifier."
                        )
                    result = UUID(str(row["id"]))
                connection.commit()
                return result
        except V1TaxRecoverableRefundError:
            raise
        except psycopg.Error as exc:
            message = str(exc).split("CONTEXT:", 1)[0].strip()
            raise V1TaxRecoverableRefundBlocked(message) from exc
