from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection


REMEASUREMENT_POLICY = "ecl_allowance_remeasurement_posting_v1"
WRITEOFF_POLICY = "ecl_full_writeoff_posting_v1"
RECOVERY_REVIEW_POLICY = "ecl_post_writeoff_recovery_evidence_review_v1"
RECOVERY_POLICY = "ecl_post_writeoff_recovery_posting_v1"


class EclA5AccountingError(RuntimeError):
    code = "ecl_a5_accounting_error"


class EclA5AccountingBlocked(EclA5AccountingError):
    code = "ecl_a5_accounting_blocked"


@dataclass(frozen=True, slots=True)
class EclA5Action:
    loan_id: UUID
    loan_number: str
    loan_status: str
    calculation_mode: str
    credit_risk_review_id: int | None
    stage_label: str | None
    default_label: bool | None
    write_off_label: str | None
    recovery_label: str | None
    measurement_id: UUID | None
    measurement_version: int | None
    measurement_date: date | None
    calculation_digest: str | None
    measurement_status: str | None
    authoritative_ecl_amount: Decimal | None
    current_allowance_balance: Decimal
    loan_receivable_account_id: UUID | None
    loan_receivable_system_key: str | None
    accrued_interest_account_id: UUID | None
    loan_component: Decimal | None
    accrued_interest_component: Decimal | None
    gross_carrying_amount: Decimal | None
    writeoff_id: UUID | None
    recovery_transaction_id: UUID | None
    recovery_amount: Decimal | None
    recovery_candidate_transaction_id: UUID | None
    recovery_candidate_amount: Decimal | None
    recovery_candidate_collection_date: date | None
    posting_date: date | None
    fiscal_period_id: UUID | None
    credit_loss_expense_account_id: UUID | None
    allowance_account_id: UUID | None
    cash_account_id: UUID | None
    a5_status: str
    protected_a5_accounting_enabled: bool
    automatic_source_posting: bool


class PostgresEclA5AccountingRepository:
    """Protected Management repository for Master #296 A5 accounting actions."""

    _ACTION_SOURCE = """
        WITH action_source AS (
            SELECT
                queue.*,
                candidate.id AS recovery_candidate_transaction_id,
                candidate.amount AS recovery_candidate_amount,
                candidate.collection_date AS recovery_candidate_collection_date,
                CASE
                    WHEN queue.a5_status = 'written_off' AND candidate.id IS NOT NULL
                        THEN 'recovery_review_required'
                    ELSE queue.a5_status
                END AS action_status
            FROM accounting.ecl_a5_action_queue queue
            LEFT JOIN accounting.ecl_accounting_writeoffs writeoff
              ON writeoff.id = queue.writeoff_id
            LEFT JOIN LATERAL (
                SELECT
                    transaction_row.id,
                    transaction_row.amount,
                    transaction_row.collection_date
                FROM lending.collection_transactions transaction_row
                WHERE transaction_row.loan_id = queue.loan_id
                  AND writeoff.id IS NOT NULL
                  AND NOT transaction_row.is_voided
                  AND transaction_row.amount > 0
                  AND transaction_row.entry_type IN ('payment', 'advance')
                  AND transaction_row.accepted_at IS NOT NULL
                  AND transaction_row.accepted_at > writeoff.posted_at
                  AND NOT EXISTS (
                      SELECT 1
                      FROM accounting.regular_journal_posting_entries posted
                      WHERE posted.transaction_id = transaction_row.id
                  )
                  AND NOT EXISTS (
                      SELECT 1
                      FROM accounting.seven_by_seven_journal_postings posted
                      WHERE posted.transaction_id = transaction_row.id
                  )
                  AND NOT EXISTS (
                      SELECT 1
                      FROM accounting.ecl_post_writeoff_recovery_review_provenance reviewed
                      WHERE reviewed.recovery_transaction_id = transaction_row.id
                  )
                  AND NOT EXISTS (
                      SELECT 1
                      FROM accounting.ecl_post_writeoff_recoveries posted_recovery
                      WHERE posted_recovery.recovery_transaction_id = transaction_row.id
                  )
                ORDER BY transaction_row.accepted_at, transaction_row.id
                LIMIT 1
            ) candidate ON true
        ), action_coordinates AS (
            SELECT
                action_source.*,
                CASE action_status
                    WHEN 'remeasurement_required' THEN measurement_date
                    WHEN 'writeoff_ready' THEN current_date
                    WHEN 'post_writeoff_recovery_ready' THEN reviewed_recovery.collection_date
                    ELSE NULL
                END AS posting_date
            FROM action_source
            LEFT JOIN lending.collection_transactions reviewed_recovery
              ON reviewed_recovery.id = action_source.recovery_transaction_id
        )
    """

    _QUEUE_COLUMNS = """
        action.loan_id, action.loan_number, action.loan_status,
        action.calculation_mode, action.credit_risk_review_id,
        action.stage_label, action.default_label, action.write_off_label,
        action.recovery_label, action.measurement_id,
        action.measurement_version, action.measurement_date,
        action.calculation_digest, action.measurement_status,
        action.authoritative_ecl_amount, action.current_allowance_balance,
        action.loan_receivable_account_id,
        action.loan_receivable_system_key,
        action.accrued_interest_account_id, action.loan_component,
        action.accrued_interest_component, action.gross_carrying_amount,
        action.writeoff_id, action.recovery_transaction_id,
        action.recovery_amount, action.recovery_candidate_transaction_id,
        action.recovery_candidate_amount,
        action.recovery_candidate_collection_date, action.posting_date,
        period.id AS fiscal_period_id,
        expense_account.id AS credit_loss_expense_account_id,
        allowance_account.id AS allowance_account_id,
        cash_account.id AS cash_account_id, action.action_status AS a5_status,
        action.protected_a5_accounting_enabled,
        action.automatic_source_posting
    """

    def list_actions(
        self,
        *,
        status: str = "all",
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[EclA5Action, ...]:
        where_clause = {
            "all": "true",
            "remeasurement_required": "action.action_status = 'remeasurement_required'",
            "allowance_current": "action.action_status = 'allowance_current'",
            "writeoff_ready": "action.action_status = 'writeoff_ready'",
            "written_off": "action.action_status = 'written_off'",
            "recovery_review_required": "action.action_status = 'recovery_review_required'",
            "post_writeoff_recovery_ready": "action.action_status = 'post_writeoff_recovery_ready'",
            "blocked": "action.action_status = 'blocked'",
        }.get(status)
        if where_clause is None:
            raise ValueError("Unsupported A5 accounting status filter.")
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    {self._ACTION_SOURCE}
                    SELECT {self._QUEUE_COLUMNS}
                    FROM action_coordinates action
                    LEFT JOIN accounting.fiscal_periods period
                      ON period.status = 'open'
                     AND action.posting_date BETWEEN period.start_date AND period.end_date
                    LEFT JOIN accounting.accounts expense_account
                      ON expense_account.system_key = 'credit_loss_expense'
                     AND expense_account.code = '5000'
                     AND expense_account.account_type = 'expense'
                     AND expense_account.normal_balance = 'debit'
                     AND expense_account.is_active AND expense_account.is_posting
                    LEFT JOIN accounting.accounts allowance_account
                      ON allowance_account.system_key = 'allowance_expected_credit_loss'
                     AND allowance_account.code = '1190'
                     AND allowance_account.account_type = 'asset'
                     AND allowance_account.normal_balance = 'credit'
                     AND allowance_account.is_active AND allowance_account.is_posting
                    LEFT JOIN accounting.accounts cash_account
                      ON cash_account.system_key = 'cash_collector_custody'
                     AND cash_account.code = '1020'
                     AND cash_account.account_type = 'asset'
                     AND cash_account.normal_balance = 'debit'
                     AND cash_account.is_active AND cash_account.is_posting
                    WHERE {where_clause}
                    ORDER BY action.loan_number, action.loan_id
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                return tuple(EclA5Action(**dict(row)) for row in cursor.fetchall())

    def summary(self) -> dict[str, object]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute("SELECT * FROM accounting.ecl_a5_summary")
                row = cursor.fetchone()
                if row is None:
                    raise EclA5AccountingError("A5 accounting summary is unavailable.")
                result = dict(row)
                cursor.execute(
                    f"""
                    {self._ACTION_SOURCE}
                    SELECT count(*)::bigint AS recovery_review_required_count
                    FROM action_source action
                    WHERE action.action_status = 'recovery_review_required'
                    """
                )
                recovery_row = cursor.fetchone()
                if recovery_row is None:
                    raise EclA5AccountingError(
                        "A5 recovery-review summary is unavailable."
                    )
                result["recovery_review_required_count"] = recovery_row[
                    "recovery_review_required_count"
                ]
                return result

    def post_remeasurement(
        self,
        *,
        measurement_id: UUID,
        actor_user_id: UUID,
        review_token: str,
        expected_calculation_digest: str,
        expected_prior_allowance: Decimal,
        expected_target_allowance: Decimal,
        expected_posting_date: date,
        expected_fiscal_period_id: UUID,
        expected_credit_loss_expense_account_id: UUID,
        expected_allowance_account_id: UUID,
        policy_version: str = REMEASUREMENT_POLICY,
    ) -> UUID:
        return self._call_id(
            """
            SELECT accounting.post_ecl_allowance_remeasurement(
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            ) AS id
            """,
            (
                measurement_id,
                actor_user_id,
                review_token,
                expected_calculation_digest,
                expected_prior_allowance,
                expected_target_allowance,
                expected_posting_date,
                expected_fiscal_period_id,
                expected_credit_loss_expense_account_id,
                expected_allowance_account_id,
                policy_version,
            ),
        )

    def post_full_writeoff(
        self,
        *,
        loan_id: UUID,
        actor_user_id: UUID,
        review_token: str,
        expected_credit_risk_review_id: int,
        expected_measurement_id: UUID,
        expected_calculation_digest: str,
        expected_loan_component: Decimal,
        expected_accrued_interest_component: Decimal,
        expected_gross_carrying_amount: Decimal,
        expected_allowance_balance: Decimal,
        expected_loan_receivable_account_id: UUID,
        expected_accrued_interest_account_id: UUID,
        expected_allowance_account_id: UUID,
        expected_posting_date: date,
        expected_fiscal_period_id: UUID,
        policy_version: str = WRITEOFF_POLICY,
    ) -> UUID:
        return self._call_id(
            """
            SELECT accounting.post_ecl_full_writeoff(
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            ) AS id
            """,
            (
                loan_id,
                actor_user_id,
                review_token,
                expected_credit_risk_review_id,
                expected_measurement_id,
                expected_calculation_digest,
                expected_loan_component,
                expected_accrued_interest_component,
                expected_gross_carrying_amount,
                expected_allowance_balance,
                expected_loan_receivable_account_id,
                expected_accrued_interest_account_id,
                expected_allowance_account_id,
                expected_posting_date,
                expected_fiscal_period_id,
                policy_version,
            ),
        )

    def review_post_writeoff_recovery(
        self,
        *,
        loan_id: UUID,
        actor_user_id: UUID,
        review_token: str,
        expected_recovery_transaction_id: UUID,
        expected_recovery_amount: Decimal,
        evidence_reference: str,
        review_note: str,
        policy_version: str = RECOVERY_REVIEW_POLICY,
    ) -> int:
        return self._call_int(
            """
            SELECT accounting.review_ecl_post_writeoff_recovery(
                %s,%s,%s,%s,%s,%s,%s,%s
            ) AS id
            """,
            (
                loan_id,
                actor_user_id,
                review_token,
                expected_recovery_transaction_id,
                expected_recovery_amount,
                evidence_reference,
                review_note,
                policy_version,
            ),
        )

    def post_recovery(
        self,
        *,
        credit_risk_review_id: int,
        actor_user_id: UUID,
        review_token: str,
        expected_recovery_transaction_id: UUID,
        expected_recovery_amount: Decimal,
        expected_posting_date: date,
        expected_fiscal_period_id: UUID,
        expected_cash_account_id: UUID,
        expected_credit_loss_expense_account_id: UUID,
        policy_version: str = RECOVERY_POLICY,
    ) -> UUID:
        return self._call_id(
            """
            SELECT accounting.post_ecl_post_writeoff_recovery(
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            ) AS id
            """,
            (
                credit_risk_review_id,
                actor_user_id,
                review_token,
                expected_recovery_transaction_id,
                expected_recovery_amount,
                expected_posting_date,
                expected_fiscal_period_id,
                expected_cash_account_id,
                expected_credit_loss_expense_account_id,
                policy_version,
            ),
        )

    @staticmethod
    def _call_id(query: str, params: tuple[object, ...]) -> UUID:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(query, params)
                    row = cursor.fetchone()
                    if row is None or row["id"] is None:
                        raise EclA5AccountingBlocked(
                            "Protected A5 accounting action returned no immutable audit id."
                        )
                    result = UUID(str(row["id"]))
                connection.commit()
                return result
        except EclA5AccountingError:
            raise
        except psycopg.Error as exc:
            message = str(exc).split("CONTEXT:", 1)[0].strip()
            raise EclA5AccountingBlocked(message) from exc

    @staticmethod
    def _call_int(query: str, params: tuple[object, ...]) -> int:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(query, params)
                    row = cursor.fetchone()
                    if row is None or row["id"] is None:
                        raise EclA5AccountingBlocked(
                            "Protected A5 recovery evidence review returned no immutable review id."
                        )
                    result = int(row["id"])
                connection.commit()
                return result
        except EclA5AccountingError:
            raise
        except psycopg.Error as exc:
            message = str(exc).split("CONTEXT:", 1)[0].strip()
            raise EclA5AccountingBlocked(message) from exc
