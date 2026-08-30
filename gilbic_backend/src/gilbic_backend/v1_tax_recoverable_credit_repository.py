from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection

POLICY = "v1_tax_recoverable_credit_posting_v1"


class V1TaxRecoverableCreditError(RuntimeError):
    code = "v1_tax_recoverable_credit_error"


class V1TaxRecoverableCreditBlocked(V1TaxRecoverableCreditError):
    code = "v1_tax_recoverable_credit_blocked"


@dataclass(frozen=True, slots=True)
class V1TaxRecoverableCreditCandidate:
    adjustment_posting_id: UUID
    adjustment_evidence_id: UUID
    tax_type: str
    source_id: UUID
    loan_id: UUID
    client_id: UUID
    credit_amount: Decimal
    target_tax_return_id: UUID
    target_return_period_start: date
    target_return_period_end: date
    target_filing_date: date
    target_declared_tax_due: Decimal
    target_return_reference: str
    target_return_evidence_digest: str
    minimum_application_date: date
    adjustment_evidence_digest: str
    entry_number: str
    fiscal_period_id: UUID


@dataclass(frozen=True, slots=True)
class V1TaxRecoverableCreditItem:
    credit_evidence_id: UUID
    adjustment_posting_id: UUID
    adjustment_evidence_id: UUID
    tax_type: str
    source_id: UUID
    loan_id: UUID
    client_id: UUID
    target_tax_return_id: UUID
    target_return_period_start: date
    target_return_period_end: date
    target_filing_date: date
    target_declared_tax_due: Decimal
    target_return_reference: str
    target_return_evidence_digest: str
    credit_amount: Decimal
    application_date: date
    application_reference: str
    authority_reference: str
    evidence_digest: str
    recorded_by_user_id: UUID
    recorded_at: datetime
    preparation_id: UUID | None
    journal_entry_id: UUID | None
    journal_status: str | None
    entry_number: str | None
    fiscal_period_id: UUID | None
    tax_payable_account_id: UUID | None
    tax_payable_account_code: str | None
    tax_payable_account_name: str | None
    tax_recoverable_account_id: UUID | None
    tax_recoverable_account_code: str | None
    tax_recoverable_account_name: str | None
    prepared_by_user_id: UUID | None
    prepared_at: datetime | None
    credit_posting_id: UUID | None
    confirmation_digest: str | None
    posted_by_user_id: UUID | None
    posted_at: datetime | None
    credit_status: str
    credit_blocker: str | None
    tax_recoverable_refund_realization_enabled: bool
    tax_recoverable_credit_application_enabled: bool
    partial_tax_recoverable_realization_enabled: bool
    automatic_source_posting: bool


class PostgresV1TaxRecoverableCreditRepository:
    _CANDIDATE_COLUMNS = """
        adjustment_posting.id AS adjustment_posting_id,
        adjustment.adjustment_evidence_id,
        adjustment.tax_type,
        adjustment.source_id,
        adjustment.loan_id,
        adjustment.client_id,
        adjustment_posting.confirmed_adjustment_amount AS credit_amount,
        target_return.id AS target_tax_return_id,
        target_return.return_period_start AS target_return_period_start,
        target_return.return_period_end AS target_return_period_end,
        target_return.filing_date AS target_filing_date,
        target_return.declared_tax_due AS target_declared_tax_due,
        target_return.return_reference AS target_return_reference,
        target_return.evidence_digest AS target_return_evidence_digest,
        greatest(
            adjustment_posting.confirmed_posting_date,
            target_return.filing_date
        ) AS minimum_application_date,
        adjustment.evidence_digest AS adjustment_evidence_digest,
        adjustment_posting.entry_number,
        adjustment_posting.confirmed_fiscal_period_id AS fiscal_period_id
    """

    _COLUMNS = """
        credit_evidence_id, adjustment_posting_id, adjustment_evidence_id,
        tax_type, source_id, loan_id, client_id, target_tax_return_id,
        target_return_period_start, target_return_period_end, target_filing_date,
        target_declared_tax_due, target_return_reference,
        target_return_evidence_digest, credit_amount, application_date,
        application_reference, authority_reference, evidence_digest,
        recorded_by_user_id, recorded_at, preparation_id, journal_entry_id,
        journal_status, entry_number, fiscal_period_id, tax_payable_account_id,
        tax_payable_account_code, tax_payable_account_name,
        tax_recoverable_account_id, tax_recoverable_account_code,
        tax_recoverable_account_name, prepared_by_user_id, prepared_at,
        credit_posting_id, confirmation_digest, posted_by_user_id, posted_at,
        credit_status, credit_blocker, tax_recoverable_refund_realization_enabled,
        tax_recoverable_credit_application_enabled,
        partial_tax_recoverable_realization_enabled, automatic_source_posting
    """

    def list_credit_candidates(
        self, *, limit: int = 100, offset: int = 0
    ) -> tuple[V1TaxRecoverableCreditCandidate, ...]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {self._CANDIDATE_COLUMNS}
                    FROM accounting.v1_tax_adjustment_queue adjustment
                    JOIN accounting.v1_tax_adjustment_postings adjustment_posting
                      ON adjustment_posting.id = adjustment.adjustment_posting_id
                     AND adjustment_posting.adjustment_evidence_id =
                         adjustment.adjustment_evidence_id
                    JOIN accounting.journal_entries adjustment_journal
                      ON adjustment_journal.id = adjustment_posting.journal_entry_id
                    JOIN accounting.accounts recoverable_account
                      ON recoverable_account.id =
                         adjustment_posting.confirmed_debit_account_id
                    JOIN accounting.v1_tax_return_evidence target_return
                      ON target_return.tax_type = adjustment.tax_type
                     AND target_return.declared_tax_due =
                         adjustment_posting.confirmed_adjustment_amount
                    JOIN LATERAL (
                        SELECT
                            count(*)::integer AS item_count,
                            count(*) FILTER (
                                WHERE liability_posting.id IS NOT NULL
                                  AND liability_preparation.tax_type = item.tax_type
                                  AND liability_preparation.evidence_id = item.evidence_id
                                  AND liability_preparation.recognition_date =
                                      item.recognition_date
                                  AND liability_posting.confirmed_tax_due = item.tax_due
                                  AND liability_posting.entry_number =
                                      item.liability_entry_number
                                  AND liability_journal.status = 'posted'
                                  AND liability_journal.entry_number =
                                      liability_posting.entry_number
                                  AND liability_queue.accounting_status = 'posted'
                            )::integer AS exact_count,
                            coalesce(sum(item.tax_due), 0)::numeric(18,2)
                                AS item_total
                        FROM accounting.v1_tax_return_liability_items item
                        LEFT JOIN accounting.v1_tax_liability_postings liability_posting
                          ON liability_posting.id = item.tax_liability_posting_id
                        LEFT JOIN accounting.v1_tax_liability_preparations liability_preparation
                          ON liability_preparation.id = liability_posting.preparation_id
                        LEFT JOIN accounting.journal_entries liability_journal
                          ON liability_journal.id = liability_posting.journal_entry_id
                        LEFT JOIN accounting.v1_tax_liability_queue liability_queue
                          ON liability_queue.tax_type = item.tax_type
                         AND liability_queue.evidence_id = item.evidence_id
                         AND liability_queue.posting_id = liability_posting.id
                        WHERE item.tax_return_id = target_return.id
                    ) liability
                      ON liability.item_count > 0
                     AND liability.exact_count = liability.item_count
                     AND liability.item_total = target_return.declared_tax_due
                    WHERE adjustment.adjustment_status =
                          'posted_settled_tax_recoverable'
                      AND adjustment.adjustment_kind =
                          'recognize_settled_tax_recoverable'
                      AND adjustment_posting.confirmed_adjustment_amount =
                          adjustment.adjustment_amount
                      AND adjustment_posting.confirmed_evidence_digest =
                          adjustment.evidence_digest
                      AND adjustment_posting.entry_number = adjustment.entry_number
                      AND adjustment_journal.status = 'posted'
                      AND adjustment_journal.entry_number =
                          adjustment_posting.entry_number
                      AND recoverable_account.system_key = 'tax_recoverable'
                      AND recoverable_account.code = '1130'
                      AND recoverable_account.account_type = 'asset'
                      AND recoverable_account.normal_balance = 'debit'
                      AND recoverable_account.is_active
                      AND recoverable_account.is_posting
                      AND NOT EXISTS (
                          SELECT 1
                          FROM accounting.v1_tax_recoverable_refund_evidence refund
                          WHERE refund.adjustment_posting_id = adjustment_posting.id
                      )
                      AND NOT EXISTS (
                          SELECT 1
                          FROM accounting.v1_tax_recoverable_credit_evidence credit
                          WHERE credit.adjustment_posting_id = adjustment_posting.id
                             OR credit.target_tax_return_id = target_return.id
                      )
                      AND NOT EXISTS (
                          SELECT 1
                          FROM accounting.v1_tax_payment_evidence payment
                          WHERE payment.tax_return_id = target_return.id
                      )
                      AND NOT EXISTS (
                          SELECT 1
                          FROM accounting.v1_tax_settlement_preparations settlement
                          WHERE settlement.tax_return_id = target_return.id
                      )
                      AND NOT EXISTS (
                          SELECT 1
                          FROM accounting.v1_tax_settlement_postings settlement
                          WHERE settlement.tax_return_id = target_return.id
                      )
                      AND NOT EXISTS (
                          SELECT 1
                          FROM accounting.v1_tax_additional_amendment_evidence amendment
                          WHERE amendment.tax_return_id = target_return.id
                      )
                    ORDER BY minimum_application_date, adjustment.tax_type,
                             adjustment_posting.id, target_return.id
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                return tuple(
                    V1TaxRecoverableCreditCandidate(**dict(row))
                    for row in cursor.fetchall()
                )

    def list_items(
        self, *, status: str = "all", limit: int = 100, offset: int = 0
    ) -> tuple[V1TaxRecoverableCreditItem, ...]:
        where = self._status_where(status)
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {self._COLUMNS}
                    FROM accounting.v1_tax_recoverable_credit_queue
                    WHERE {where}
                    ORDER BY application_date DESC, recorded_at DESC, credit_evidence_id
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                return tuple(
                    V1TaxRecoverableCreditItem(**dict(row)) for row in cursor.fetchall()
                )

    def get_item(self, credit_evidence_id: UUID) -> V1TaxRecoverableCreditItem:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {self._COLUMNS}
                    FROM accounting.v1_tax_recoverable_credit_queue
                    WHERE credit_evidence_id=%s
                    """,
                    (credit_evidence_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise V1TaxRecoverableCreditBlocked(
                        "V1 Tax Recoverable credit evidence item was not found."
                    )
                return V1TaxRecoverableCreditItem(**dict(row))

    def summary(self) -> dict[str, object]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    "SELECT * FROM accounting.v1_tax_recoverable_credit_summary"
                )
                row = cursor.fetchone()
                if row is None:
                    raise V1TaxRecoverableCreditError(
                        "V1 Tax Recoverable credit summary is unavailable."
                    )
                return dict(row)

    def record_evidence(
        self,
        *,
        actor_user_id: UUID,
        idempotency_key: UUID,
        adjustment_posting_id: UUID,
        target_tax_return_id: UUID,
        application_date: date,
        application_reference: str,
        authority_reference: str,
        evidence_digest: str,
        evidence_note: str,
    ) -> UUID:
        return self._call_id(
            """
            SELECT accounting.record_v1_tax_recoverable_credit_evidence(
                %s,%s,%s,%s,%s,%s,%s,%s,%s
            ) AS id
            """,
            (
                actor_user_id,
                idempotency_key,
                adjustment_posting_id,
                target_tax_return_id,
                application_date,
                application_reference,
                authority_reference,
                evidence_digest,
                evidence_note,
            ),
        )

    def prepare(self, *, credit_evidence_id: UUID, actor_user_id: UUID) -> UUID:
        return self._call_id(
            "SELECT accounting.prepare_v1_tax_recoverable_credit_journal(%s,%s) AS id",
            (credit_evidence_id, actor_user_id),
        )

    def post(
        self,
        *,
        credit_evidence_id: UUID,
        actor_user_id: UUID,
        confirmation_token: str,
        expected_evidence_digest: str,
        expected_credit_amount: Decimal,
        expected_tax_payable_account_code: str,
        expected_tax_recoverable_account_code: str,
        expected_posting_date: date,
        expected_fiscal_period_id: UUID,
        policy_version: str = POLICY,
    ) -> UUID:
        return self._call_id(
            """
            SELECT accounting.post_v1_tax_recoverable_credit_journal(
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            ) AS id
            """,
            (
                credit_evidence_id,
                actor_user_id,
                confirmation_token,
                expected_evidence_digest,
                expected_credit_amount,
                expected_tax_payable_account_code,
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
            "ready": "credit_status = 'credit_evidence_ready'",
            "prepared": "credit_status = 'credit_prepared'",
            "applied": "credit_status = 'credit_applied'",
            "blocked": "credit_status LIKE 'blocked_%'",
        }
        clause = clauses.get(status)
        if clause is None:
            raise ValueError("Unsupported V1 Tax Recoverable credit status filter.")
        return clause

    @staticmethod
    def _call_id(query: str, params: tuple[object, ...]) -> UUID:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(query, params)
                    row = cursor.fetchone()
                    if row is None or row["id"] is None:
                        raise V1TaxRecoverableCreditBlocked(
                            "Protected V1 Tax Recoverable credit action returned no immutable identifier."
                        )
                    result = UUID(str(row["id"]))
                connection.commit()
                return result
        except V1TaxRecoverableCreditError:
            raise
        except psycopg.Error as exc:
            message = str(exc).split("CONTEXT:", 1)[0].strip()
            raise V1TaxRecoverableCreditBlocked(message) from exc
