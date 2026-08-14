from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection


POLICY = "v1_tax_liability_posting_v1"


class V1TaxLiabilityError(RuntimeError):
    code = "v1_tax_liability_error"


class V1TaxLiabilityBlocked(V1TaxLiabilityError):
    code = "v1_tax_liability_blocked"


@dataclass(frozen=True, slots=True)
class V1TaxLiabilityItem:
    tax_type: str
    evidence_id: UUID
    evidence_version: int
    source_id: UUID
    loan_id: UUID
    client_id: UUID
    recognition_date: date
    tax_due: Decimal
    evidence_digest: str
    evidence_status: str
    evidence_blocker: str | None
    expense_account_code: str | None
    expense_account_name: str | None
    tax_payable_account_code: str | None
    tax_payable_account_name: str | None
    preparation_id: UUID | None
    journal_entry_id: UUID | None
    journal_status: str | None
    entry_number: str | None
    fiscal_period_id: UUID | None
    prepared_by_user_id: UUID | None
    prepared_at: datetime | None
    posting_id: UUID | None
    confirmation_digest: str | None
    posted_by_user_id: UUID | None
    posted_at: datetime | None
    accounting_status: str
    accounting_blocker: str | None
    protected_tax_liability_posting_enabled: bool
    tax_settlement_enabled: bool
    tax_adjustment_reversal_enabled: bool
    automatic_source_posting: bool


class PostgresV1TaxLiabilityRepository:
    """Protected Management repository for A6.2 tax-liability recognition."""

    _COLUMNS = """
        tax_type, evidence_id, evidence_version, source_id, loan_id, client_id,
        recognition_date, tax_due, evidence_digest, evidence_status,
        evidence_blocker, expense_account_code, expense_account_name,
        tax_payable_account_code, tax_payable_account_name, preparation_id,
        journal_entry_id, journal_status, entry_number, fiscal_period_id,
        prepared_by_user_id, prepared_at, posting_id, confirmation_digest,
        posted_by_user_id, posted_at, accounting_status, accounting_blocker,
        protected_tax_liability_posting_enabled, tax_settlement_enabled,
        tax_adjustment_reversal_enabled, automatic_source_posting
    """

    def list_items(
        self, *, status: str = "all", limit: int = 100, offset: int = 0
    ) -> tuple[V1TaxLiabilityItem, ...]:
        where = self._status_where(status)
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {self._COLUMNS}
                    FROM accounting.v1_tax_liability_effective_queue
                    WHERE {where}
                    ORDER BY recognition_date DESC, tax_type, evidence_version DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                return tuple(
                    V1TaxLiabilityItem(**dict(row)) for row in cursor.fetchall()
                )

    def get_item(self, *, tax_type: str, evidence_id: UUID) -> V1TaxLiabilityItem:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {self._COLUMNS}
                    FROM accounting.v1_tax_liability_effective_queue
                    WHERE tax_type=%s AND evidence_id=%s
                    """,
                    (tax_type, evidence_id),
                )
                row = cursor.fetchone()
                if row is None:
                    raise V1TaxLiabilityBlocked(
                        "V1 tax-liability evidence item was not found."
                    )
                return V1TaxLiabilityItem(**dict(row))

    def summary(self) -> dict[str, object]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    "SELECT * FROM accounting.v1_tax_liability_effective_summary"
                )
                row = cursor.fetchone()
                if row is None:
                    raise V1TaxLiabilityError(
                        "V1 tax-liability summary is unavailable."
                    )
                return dict(row)

    def prepare(
        self,
        *,
        tax_type: str,
        evidence_id: UUID,
        actor_user_id: UUID,
    ) -> UUID:
        return self._call_id(
            """
            SELECT accounting.prepare_v1_tax_liability_journal(%s,%s,%s) AS id
            """,
            (tax_type, evidence_id, actor_user_id),
        )

    def post(
        self,
        *,
        tax_type: str,
        evidence_id: UUID,
        actor_user_id: UUID,
        confirmation_token: str,
        expected_evidence_digest: str,
        expected_tax_due: Decimal,
        expected_expense_account_code: str,
        expected_tax_payable_account_code: str,
        expected_posting_date: date,
        expected_fiscal_period_id: UUID,
        policy_version: str = POLICY,
    ) -> UUID:
        return self._call_id(
            """
            SELECT accounting.post_v1_tax_liability_journal(
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            ) AS id
            """,
            (
                tax_type,
                evidence_id,
                actor_user_id,
                confirmation_token,
                expected_evidence_digest,
                expected_tax_due,
                expected_expense_account_code,
                expected_tax_payable_account_code,
                expected_posting_date,
                expected_fiscal_period_id,
                policy_version,
            ),
        )

    @staticmethod
    def _status_where(status: str) -> str:
        clauses = {
            "all": "true",
            "ready": "accounting_status = 'evidence_ready'",
            "prepared": "accounting_status = 'prepared_not_posted'",
            "posted": "accounting_status = 'posted'",
            "adjustment_review": "accounting_status = 'posted_adjustment_review_required'",
            "adjusted": "accounting_status LIKE 'posted_adjusted_%'",
            "covered": "accounting_status = 'covered_by_settled_adjustment'",
            "blocked": (
                "accounting_status NOT IN "
                "('evidence_ready','prepared_not_posted','posted',"
                "'no_liability_required','posted_adjusted_reversed',"
                "'posted_adjusted_recoverable','covered_by_settled_adjustment')"
            ),
        }
        clause = clauses.get(status)
        if clause is None:
            raise ValueError("Unsupported V1 tax-liability status filter.")
        return clause

    @staticmethod
    def _call_id(query: str, params: tuple[object, ...]) -> UUID:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(query, params)
                    row = cursor.fetchone()
                    if row is None or row["id"] is None:
                        raise V1TaxLiabilityBlocked(
                            "Protected V1 tax-liability action returned no immutable identifier."
                        )
                    result = UUID(str(row["id"]))
                connection.commit()
                return result
        except V1TaxLiabilityError:
            raise
        except psycopg.Error as exc:
            message = str(exc).split("CONTEXT:", 1)[0].strip()
            raise V1TaxLiabilityBlocked(message) from exc
