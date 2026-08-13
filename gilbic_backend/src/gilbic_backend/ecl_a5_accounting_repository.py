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
    a5_status: str
    protected_a5_accounting_enabled: bool
    automatic_source_posting: bool


class PostgresEclA5AccountingRepository:
    """Protected Management repository for Master #296 A5 accounting actions."""

    _QUEUE_COLUMNS = """
        loan_id, loan_number, loan_status, calculation_mode,
        credit_risk_review_id, stage_label, default_label,
        write_off_label, recovery_label, measurement_id,
        measurement_version, measurement_date, calculation_digest,
        measurement_status, authoritative_ecl_amount,
        current_allowance_balance, loan_receivable_account_id,
        loan_receivable_system_key, accrued_interest_account_id,
        loan_component, accrued_interest_component, gross_carrying_amount,
        writeoff_id, recovery_transaction_id, recovery_amount,
        a5_status, protected_a5_accounting_enabled, automatic_source_posting
    """

    def list_actions(self, *, status: str = "all", limit: int = 100, offset: int = 0) -> tuple[EclA5Action, ...]:
        where_clause = {
            "all": "true",
            "remeasurement_required": "a5_status = 'remeasurement_required'",
            "allowance_current": "a5_status = 'allowance_current'",
            "writeoff_ready": "a5_status = 'writeoff_ready'",
            "written_off": "a5_status = 'written_off'",
            "post_writeoff_recovery_ready": "a5_status = 'post_writeoff_recovery_ready'",
            "blocked": "a5_status = 'blocked'",
        }.get(status)
        if where_clause is None:
            raise ValueError("Unsupported A5 accounting status filter.")
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"SELECT {self._QUEUE_COLUMNS} FROM accounting.ecl_a5_action_queue WHERE {where_clause} ORDER BY loan_number, loan_id LIMIT %s OFFSET %s",
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
                return dict(row)

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
                measurement_id, actor_user_id, review_token,
                expected_calculation_digest, expected_prior_allowance,
                expected_target_allowance, expected_posting_date,
                expected_fiscal_period_id, expected_credit_loss_expense_account_id,
                expected_allowance_account_id, policy_version,
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
                loan_id, actor_user_id, review_token,
                expected_credit_risk_review_id, expected_measurement_id,
                expected_calculation_digest, expected_loan_component,
                expected_accrued_interest_component,
                expected_gross_carrying_amount, expected_allowance_balance,
                expected_loan_receivable_account_id,
                expected_accrued_interest_account_id,
                expected_allowance_account_id, expected_posting_date,
                expected_fiscal_period_id, policy_version,
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
                credit_risk_review_id, actor_user_id, review_token,
                expected_recovery_transaction_id, expected_recovery_amount,
                expected_posting_date, expected_fiscal_period_id,
                expected_cash_account_id,
                expected_credit_loss_expense_account_id, policy_version,
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
