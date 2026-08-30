from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection

POLICY = "v1_tax_adjustment_posting_v1"


class V1TaxAdjustmentError(RuntimeError):
    code = "v1_tax_adjustment_error"


class V1TaxAdjustmentBlocked(V1TaxAdjustmentError):
    code = "v1_tax_adjustment_blocked"


@dataclass(frozen=True, slots=True)
class V1TaxAdjustmentCandidate:
    adjustment_kind: str
    tax_type: str
    tax_liability_posting_id: UUID
    original_evidence_id: UUID
    original_evidence_version: int
    replacement_evidence_id: UUID
    replacement_evidence_version: int
    source_id: UUID
    loan_id: UUID
    client_id: UUID
    original_tax_due: Decimal
    replacement_tax_due: Decimal
    adjustment_amount: Decimal
    original_evidence_digest: str
    replacement_evidence_digest: str
    fiscal_period_id: UUID
    fiscal_period_start: date
    fiscal_period_end: date
    settlement_posting_id: UUID | None


@dataclass(frozen=True, slots=True)
class V1TaxAdjustmentItem:
    adjustment_evidence_id: UUID
    adjustment_kind: str
    tax_type: str
    tax_liability_posting_id: UUID
    original_evidence_id: UUID
    replacement_evidence_id: UUID
    source_id: UUID
    loan_id: UUID
    client_id: UUID
    original_tax_due: Decimal
    replacement_tax_due: Decimal
    adjustment_amount: Decimal
    adjustment_date: date
    adjustment_reference: str
    evidence_reference: str
    evidence_digest: str
    recorded_by_user_id: UUID
    recorded_at: datetime
    settlement_posting_id: UUID | None
    original_settlement_journal_entry_id: UUID | None
    preparation_id: UUID | None
    journal_entry_id: UUID | None
    journal_status: str | None
    entry_number: str | None
    fiscal_period_id: UUID | None
    debit_account_id: UUID | None
    debit_account_code: str | None
    debit_account_name: str | None
    credit_account_id: UUID | None
    credit_account_code: str | None
    credit_account_name: str | None
    prepared_by_user_id: UUID | None
    prepared_at: datetime | None
    adjustment_posting_id: UUID | None
    confirmation_digest: str | None
    posted_by_user_id: UUID | None
    posted_at: datetime | None
    adjustment_status: str
    adjustment_blocker: str | None
    tax_settlement_enabled: bool
    tax_adjustment_reversal_enabled: bool
    automatic_source_posting: bool


class PostgresV1TaxAdjustmentRepository:
    _COLUMNS = """
        adjustment_evidence_id, adjustment_kind, tax_type,
        tax_liability_posting_id, original_evidence_id, replacement_evidence_id,
        source_id, loan_id, client_id, original_tax_due, replacement_tax_due,
        adjustment_amount, adjustment_date, adjustment_reference,
        evidence_reference, evidence_digest, recorded_by_user_id, recorded_at,
        settlement_posting_id, original_settlement_journal_entry_id,
        preparation_id, journal_entry_id, journal_status, entry_number,
        fiscal_period_id, debit_account_id, debit_account_code,
        debit_account_name, credit_account_id, credit_account_code,
        credit_account_name, prepared_by_user_id, prepared_at,
        adjustment_posting_id, confirmation_digest, posted_by_user_id,
        posted_at, adjustment_status, adjustment_blocker,
        tax_settlement_enabled, tax_adjustment_reversal_enabled,
        automatic_source_posting
    """

    _CANDIDATE_COLUMNS = """
        CASE
            WHEN payment.id IS NULL AND settlement.id IS NULL
                THEN 'reverse_unsettled_liability'
            ELSE 'recognize_settled_tax_recoverable'
        END AS adjustment_kind,
        original.tax_type,
        original.posting_id AS tax_liability_posting_id,
        original.evidence_id AS original_evidence_id,
        original.evidence_version AS original_evidence_version,
        replacement.evidence_id AS replacement_evidence_id,
        replacement.evidence_version AS replacement_evidence_version,
        original.source_id,
        original.loan_id,
        original.client_id,
        original.tax_due AS original_tax_due,
        replacement.tax_due AS replacement_tax_due,
        CASE
            WHEN payment.id IS NULL AND settlement.id IS NULL
                THEN original.tax_due
            ELSE original.tax_due - replacement.tax_due
        END::numeric(18,2) AS adjustment_amount,
        original.evidence_digest AS original_evidence_digest,
        replacement.evidence_digest AS replacement_evidence_digest,
        original.fiscal_period_id,
        period.start_date AS fiscal_period_start,
        period.end_date AS fiscal_period_end,
        settlement.id AS settlement_posting_id
    """

    def list_adjustment_candidates(
        self, *, limit: int = 100, offset: int = 0
    ) -> tuple[V1TaxAdjustmentCandidate, ...]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {self._CANDIDATE_COLUMNS}
                    FROM accounting.v1_tax_liability_queue original
                    JOIN accounting.v1_tax_liability_queue replacement
                      ON replacement.tax_type = original.tax_type
                     AND replacement.source_id = original.source_id
                     AND replacement.loan_id = original.loan_id
                     AND replacement.client_id = original.client_id
                     AND replacement.evidence_version > original.evidence_version
                     AND replacement.evidence_status = 'evidence_ready'
                     AND replacement.accounting_status IN (
                         'evidence_ready', 'no_liability_required'
                     )
                     AND replacement.preparation_id IS NULL
                     AND replacement.posting_id IS NULL
                    JOIN accounting.fiscal_periods period
                      ON period.id = original.fiscal_period_id
                     AND period.status = 'open'
                    LEFT JOIN accounting.v1_tax_return_liability_items return_item
                      ON return_item.tax_liability_posting_id = original.posting_id
                    LEFT JOIN accounting.v1_tax_payment_evidence payment
                      ON payment.tax_return_id = return_item.tax_return_id
                    LEFT JOIN accounting.v1_tax_settlement_postings settlement
                      ON settlement.tax_return_id = return_item.tax_return_id
                    LEFT JOIN accounting.journal_entries settlement_journal
                      ON settlement_journal.id = settlement.journal_entry_id
                    WHERE original.accounting_status =
                          'posted_adjustment_review_required'
                      AND original.posting_id IS NOT NULL
                      AND original.journal_status = 'posted'
                      AND NOT EXISTS (
                          SELECT 1
                          FROM accounting.v1_tax_adjustment_evidence evidence
                          WHERE evidence.tax_liability_posting_id =
                                original.posting_id
                      )
                      AND (
                          (payment.id IS NULL AND settlement.id IS NULL)
                          OR (
                              settlement.id IS NOT NULL
                              AND settlement_journal.status = 'posted'
                              AND settlement_journal.entry_number =
                                  settlement.entry_number
                              AND replacement.tax_due < original.tax_due
                          )
                      )
                    ORDER BY period.end_date, original.tax_type,
                             original.posting_id
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                return tuple(
                    V1TaxAdjustmentCandidate(**dict(row)) for row in cursor.fetchall()
                )

    def list_items(
        self, *, status: str = "all", limit: int = 100, offset: int = 0
    ) -> tuple[V1TaxAdjustmentItem, ...]:
        where = self._status_where(status)
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {self._COLUMNS}
                    FROM accounting.v1_tax_adjustment_queue
                    WHERE {where}
                    ORDER BY adjustment_date DESC, recorded_at DESC,
                             adjustment_evidence_id
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                return tuple(
                    V1TaxAdjustmentItem(**dict(row)) for row in cursor.fetchall()
                )

    def get_item(self, adjustment_evidence_id: UUID) -> V1TaxAdjustmentItem:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {self._COLUMNS}
                    FROM accounting.v1_tax_adjustment_queue
                    WHERE adjustment_evidence_id=%s
                    """,
                    (adjustment_evidence_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise V1TaxAdjustmentBlocked(
                        "V1 tax adjustment evidence item was not found."
                    )
                return V1TaxAdjustmentItem(**dict(row))

    def summary(self) -> dict[str, object]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute("SELECT * FROM accounting.v1_tax_adjustment_summary")
                row = cursor.fetchone()
                if row is None:
                    raise V1TaxAdjustmentError(
                        "V1 tax adjustment summary is unavailable."
                    )
                return dict(row)

    def record_evidence(
        self,
        *,
        actor_user_id: UUID,
        idempotency_key: UUID,
        tax_liability_posting_id: UUID,
        replacement_evidence_id: UUID,
        adjustment_kind: str,
        adjustment_date: date,
        adjustment_reference: str,
        evidence_reference: str,
        evidence_digest: str,
        evidence_note: str,
    ) -> UUID:
        return self._call_id(
            """
            SELECT accounting.record_v1_tax_adjustment_evidence(
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            ) AS id
            """,
            (
                actor_user_id,
                idempotency_key,
                tax_liability_posting_id,
                replacement_evidence_id,
                adjustment_kind,
                adjustment_date,
                adjustment_reference,
                evidence_reference,
                evidence_digest,
                evidence_note,
            ),
        )

    def prepare(self, *, adjustment_evidence_id: UUID, actor_user_id: UUID) -> UUID:
        return self._call_id(
            "SELECT accounting.prepare_v1_tax_adjustment_journal(%s,%s) AS id",
            (adjustment_evidence_id, actor_user_id),
        )

    def post(
        self,
        *,
        adjustment_evidence_id: UUID,
        actor_user_id: UUID,
        confirmation_token: str,
        expected_evidence_digest: str,
        expected_original_tax_due: Decimal,
        expected_replacement_tax_due: Decimal,
        expected_adjustment_amount: Decimal,
        expected_debit_account_code: str,
        expected_credit_account_code: str,
        expected_posting_date: date,
        expected_fiscal_period_id: UUID,
        policy_version: str = POLICY,
    ) -> UUID:
        return self._call_id(
            """
            SELECT accounting.post_v1_tax_adjustment_journal(
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            ) AS id
            """,
            (
                adjustment_evidence_id,
                actor_user_id,
                confirmation_token,
                expected_evidence_digest,
                expected_original_tax_due,
                expected_replacement_tax_due,
                expected_adjustment_amount,
                expected_debit_account_code,
                expected_credit_account_code,
                expected_posting_date,
                expected_fiscal_period_id,
                policy_version,
            ),
        )

    @staticmethod
    def _status_where(status: str) -> str:
        clauses = {
            "all": "true",
            "ready": "adjustment_status = 'evidence_ready'",
            "prepared": "adjustment_status = 'prepared_not_posted'",
            "posted": (
                "adjustment_status IN "
                "('posted_unsettled_liability_reversal',"
                "'posted_settled_tax_recoverable')"
            ),
            "review": "adjustment_status = 'posted_further_adjustment_review_required'",
            "blocked": "adjustment_status LIKE 'blocked_%'",
        }
        clause = clauses.get(status)
        if clause is None:
            raise ValueError("Unsupported V1 tax adjustment status filter.")
        return clause

    @staticmethod
    def _call_id(query: str, params: tuple[object, ...]) -> UUID:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(query, params)
                    row = cursor.fetchone()
                    if row is None or row["id"] is None:
                        raise V1TaxAdjustmentBlocked(
                            "Protected V1 tax adjustment action returned no immutable identifier."
                        )
                    result = UUID(str(row["id"]))
                connection.commit()
                return result
        except V1TaxAdjustmentError:
            raise
        except psycopg.Error as exc:
            message = str(exc).split("CONTEXT:", 1)[0].strip()
            raise V1TaxAdjustmentBlocked(message) from exc
