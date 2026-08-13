from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection


DRAFT_POLICY = "ecl_allowance_initial_journal_draft_v1"
POSTING_POLICY = "ecl_allowance_initial_journal_posting_v1"


@dataclass(frozen=True, slots=True)
class EclAllowancePostingQueueItem:
    loan_id: UUID
    loan_number: str
    loan_status: str
    loan_type_code: str
    loan_type_name: str
    calculation_mode: str
    measurement_id: UUID | None
    measurement_version: int | None
    measurement_date: date | None
    loss_horizon: str | None
    calculation_digest: str | None
    measurement_status: str
    authoritative_ecl_amount: Decimal | None
    preparation_id: UUID | None
    journal_entry_id: UUID | None
    source_event_key: str | None
    posting_date: date | None
    fiscal_period_id: UUID | None
    credit_loss_expense_account_id: UUID | None
    allowance_account_id: UUID | None
    allowance_amount: Decimal | None
    prior_allowance_balance: Decimal | None
    preparation_review_token: str | None
    preparation_digest: str | None
    draft_policy_version: str | None
    journal_status: str | None
    entry_number: str | None
    posting_id: UUID | None
    posting_review_token: str | None
    posting_policy_version: str | None
    current_allowance_balance: Decimal
    allowance_posting_status: str
    protected_allowance_action_ready: bool
    account_1190_posting_enabled: bool
    automatic_source_posting: bool


@dataclass(frozen=True, slots=True)
class EclAllowancePreparation:
    id: UUID
    measurement_id: UUID
    loan_id: UUID
    client_id: UUID
    measurement_version: int
    measurement_date: date
    calculation_digest: str
    journal_entry_id: UUID
    source_event_key: str
    posting_date: date
    fiscal_period_id: UUID
    credit_loss_expense_account_id: UUID
    allowance_account_id: UUID
    allowance_amount: Decimal
    prior_allowance_balance: Decimal
    preparation_review_token: str
    preparation_digest: str
    draft_policy_version: str
    prepared_by_user_id: UUID
    prepared_at: datetime


@dataclass(frozen=True, slots=True)
class EclAllowancePosting:
    id: UUID
    preparation_id: UUID
    measurement_id: UUID
    loan_id: UUID
    client_id: UUID
    measurement_version: int
    calculation_digest: str
    journal_entry_id: UUID
    source_event_key: str
    posting_date: date
    fiscal_period_id: UUID
    credit_loss_expense_account_id: UUID
    allowance_account_id: UUID
    allowance_amount: Decimal
    prior_allowance_balance: Decimal
    resulting_allowance_balance: Decimal
    preparation_review_token: str
    preparation_digest: str
    posting_review_token: str
    draft_policy_version: str
    posting_policy_version: str
    entry_number: str
    posted_by_user_id: UUID
    posted_at: datetime


class EclAllowancePostingError(RuntimeError):
    code = "ecl_allowance_posting_error"


class EclAllowancePostingNotFound(EclAllowancePostingError):
    code = "ecl_allowance_posting_not_found"


class EclAllowancePostingBlocked(EclAllowancePostingError):
    code = "ecl_allowance_posting_blocked"


class PostgresEclAllowancePostingRepository:
    """Protected Management repository for Master #296 A4 allowance posting."""

    _QUEUE_COLUMNS = """
        loan_id, loan_number, loan_status, loan_type_code, loan_type_name,
        calculation_mode, measurement_id, measurement_version, measurement_date,
        loss_horizon, calculation_digest, measurement_status,
        authoritative_ecl_amount, preparation_id, journal_entry_id,
        source_event_key, posting_date, fiscal_period_id,
        credit_loss_expense_account_id, allowance_account_id, allowance_amount,
        prior_allowance_balance, preparation_review_token, preparation_digest,
        draft_policy_version, journal_status, entry_number, posting_id,
        posting_review_token, posting_policy_version, current_allowance_balance,
        allowance_posting_status, protected_allowance_action_ready,
        account_1190_posting_enabled, automatic_source_posting
    """

    _PREPARATION_COLUMNS = """
        id, measurement_id, loan_id, client_id, measurement_version,
        measurement_date, calculation_digest, journal_entry_id, source_event_key,
        posting_date, fiscal_period_id, credit_loss_expense_account_id,
        allowance_account_id, allowance_amount, prior_allowance_balance,
        preparation_review_token, preparation_digest, draft_policy_version,
        prepared_by_user_id, prepared_at
    """

    _POSTING_COLUMNS = """
        id, preparation_id, measurement_id, loan_id, client_id,
        measurement_version, calculation_digest, journal_entry_id,
        source_event_key, posting_date, fiscal_period_id,
        credit_loss_expense_account_id, allowance_account_id, allowance_amount,
        prior_allowance_balance, resulting_allowance_balance,
        preparation_review_token, preparation_digest, posting_review_token,
        draft_policy_version, posting_policy_version, entry_number,
        posted_by_user_id, posted_at
    """

    def list_queue(
        self,
        *,
        status: str = "all",
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[EclAllowancePostingQueueItem, ...]:
        where_clause = {
            "all": "true",
            "measurement_not_authoritative": "allowance_posting_status = 'measurement_not_authoritative'",
            "no_allowance_required": "allowance_posting_status = 'no_allowance_required'",
            "preparation_required": "allowance_posting_status = 'preparation_required'",
            "posting_ready": "allowance_posting_status = 'posting_ready'",
            "posted_current": "allowance_posting_status = 'posted_current'",
            "a5_remeasurement_required": "allowance_posting_status = 'a5_remeasurement_required'",
            "posting_audit_incomplete": "allowance_posting_status = 'posting_audit_incomplete'",
            "ready": "protected_allowance_action_ready = true",
        }.get(status)
        if where_clause is None:
            raise ValueError("Unsupported ECL allowance posting status filter.")

        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {self._QUEUE_COLUMNS}
                    FROM accounting.ecl_allowance_posting_queue
                    WHERE {where_clause}
                    ORDER BY loan_number, loan_id
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                return tuple(self._queue_from_row(row) for row in cursor.fetchall())

    def summary(self) -> dict[str, object]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        loan_count, measurement_not_authoritative_count,
                        no_allowance_required_count, preparation_required_count,
                        posting_ready_count, posted_current_count,
                        a5_remeasurement_required_count,
                        posting_audit_incomplete_count,
                        protected_allowance_balance_total,
                        account_1190_posting_enabled, automatic_source_posting
                    FROM accounting.ecl_allowance_posting_summary
                    """
                )
                row = cursor.fetchone()
                if row is None:
                    raise EclAllowancePostingError(
                        "ECL allowance posting summary is unavailable."
                    )
                return dict(row)

    def prepare(
        self,
        *,
        measurement_id: UUID,
        actor_user_id: UUID,
        preparation_review_token: str,
        expected_calculation_digest: str,
        expected_ecl_amount: Decimal,
        expected_posting_date: date,
        expected_fiscal_period_id: UUID,
        expected_credit_loss_expense_account_id: UUID,
        expected_allowance_account_id: UUID,
        expected_prior_allowance_balance: Decimal,
    ) -> EclAllowancePreparation:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT accounting.prepare_initial_ecl_allowance_journal(
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        ) AS preparation_id
                        """,
                        (
                            measurement_id,
                            actor_user_id,
                            preparation_review_token,
                            expected_calculation_digest,
                            expected_ecl_amount,
                            expected_posting_date,
                            expected_fiscal_period_id,
                            expected_credit_loss_expense_account_id,
                            expected_allowance_account_id,
                            expected_prior_allowance_balance,
                            DRAFT_POLICY,
                        ),
                    )
                    created = cursor.fetchone()
                    preparation_id = created["preparation_id"]
                    cursor.execute(
                        f"""
                        SELECT {self._PREPARATION_COLUMNS}
                        FROM accounting.ecl_allowance_draft_preparations
                        WHERE id = %s
                        """,
                        (preparation_id,),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise EclAllowancePostingNotFound(
                            "Protected ECL allowance preparation was not found after creation."
                        )
                    return self._preparation_from_row(row)
        except psycopg.Error as error:
            raise self._translate_error(error) from error

    def post(
        self,
        *,
        preparation_id: UUID,
        actor_user_id: UUID,
        posting_review_token: str,
        expected_measurement_id: UUID,
        expected_calculation_digest: str,
        expected_journal_entry_id: UUID,
        expected_source_event_key: str,
        expected_preparation_digest: str,
        expected_posting_date: date,
        expected_fiscal_period_id: UUID,
        expected_credit_loss_expense_account_id: UUID,
        expected_allowance_account_id: UUID,
        expected_allowance_amount: Decimal,
        expected_prior_allowance_balance: Decimal,
    ) -> EclAllowancePosting:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT accounting.post_initial_ecl_allowance_journal(
                            %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s
                        ) AS posting_id
                        """,
                        (
                            preparation_id,
                            actor_user_id,
                            posting_review_token,
                            expected_measurement_id,
                            expected_calculation_digest,
                            expected_journal_entry_id,
                            expected_source_event_key,
                            expected_preparation_digest,
                            expected_posting_date,
                            expected_fiscal_period_id,
                            expected_credit_loss_expense_account_id,
                            expected_allowance_account_id,
                            expected_allowance_amount,
                            expected_prior_allowance_balance,
                            POSTING_POLICY,
                        ),
                    )
                    created = cursor.fetchone()
                    posting_id = created["posting_id"]
                    cursor.execute(
                        f"""
                        SELECT {self._POSTING_COLUMNS}
                        FROM accounting.ecl_allowance_postings
                        WHERE id = %s
                        """,
                        (posting_id,),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise EclAllowancePostingNotFound(
                            "Protected ECL allowance posting was not found after posting."
                        )
                    return self._posting_from_row(row)
        except psycopg.Error as error:
            raise self._translate_error(error) from error

    @staticmethod
    def _queue_from_row(row) -> EclAllowancePostingQueueItem:
        return EclAllowancePostingQueueItem(
            loan_id=row["loan_id"],
            loan_number=str(row["loan_number"]),
            loan_status=str(row["loan_status"]),
            loan_type_code=str(row["loan_type_code"]),
            loan_type_name=str(row["loan_type_name"]),
            calculation_mode=str(row["calculation_mode"]),
            measurement_id=row["measurement_id"],
            measurement_version=(int(row["measurement_version"]) if row["measurement_version"] is not None else None),
            measurement_date=row["measurement_date"],
            loss_horizon=(str(row["loss_horizon"]) if row["loss_horizon"] else None),
            calculation_digest=(str(row["calculation_digest"]) if row["calculation_digest"] else None),
            measurement_status=str(row["measurement_status"]),
            authoritative_ecl_amount=row["authoritative_ecl_amount"],
            preparation_id=row["preparation_id"],
            journal_entry_id=row["journal_entry_id"],
            source_event_key=(str(row["source_event_key"]) if row["source_event_key"] else None),
            posting_date=row["posting_date"],
            fiscal_period_id=row["fiscal_period_id"],
            credit_loss_expense_account_id=row["credit_loss_expense_account_id"],
            allowance_account_id=row["allowance_account_id"],
            allowance_amount=row["allowance_amount"],
            prior_allowance_balance=row["prior_allowance_balance"],
            preparation_review_token=(str(row["preparation_review_token"]) if row["preparation_review_token"] else None),
            preparation_digest=(str(row["preparation_digest"]) if row["preparation_digest"] else None),
            draft_policy_version=(str(row["draft_policy_version"]) if row["draft_policy_version"] else None),
            journal_status=(str(row["journal_status"]) if row["journal_status"] else None),
            entry_number=(str(row["entry_number"]) if row["entry_number"] else None),
            posting_id=row["posting_id"],
            posting_review_token=(str(row["posting_review_token"]) if row["posting_review_token"] else None),
            posting_policy_version=(str(row["posting_policy_version"]) if row["posting_policy_version"] else None),
            current_allowance_balance=row["current_allowance_balance"],
            allowance_posting_status=str(row["allowance_posting_status"]),
            protected_allowance_action_ready=bool(row["protected_allowance_action_ready"]),
            account_1190_posting_enabled=bool(row["account_1190_posting_enabled"]),
            automatic_source_posting=bool(row["automatic_source_posting"]),
        )

    @staticmethod
    def _preparation_from_row(row) -> EclAllowancePreparation:
        return EclAllowancePreparation(
            id=row["id"], measurement_id=row["measurement_id"], loan_id=row["loan_id"],
            client_id=row["client_id"], measurement_version=int(row["measurement_version"]),
            measurement_date=row["measurement_date"], calculation_digest=str(row["calculation_digest"]),
            journal_entry_id=row["journal_entry_id"], source_event_key=str(row["source_event_key"]),
            posting_date=row["posting_date"], fiscal_period_id=row["fiscal_period_id"],
            credit_loss_expense_account_id=row["credit_loss_expense_account_id"],
            allowance_account_id=row["allowance_account_id"], allowance_amount=row["allowance_amount"],
            prior_allowance_balance=row["prior_allowance_balance"],
            preparation_review_token=str(row["preparation_review_token"]),
            preparation_digest=str(row["preparation_digest"]), draft_policy_version=str(row["draft_policy_version"]),
            prepared_by_user_id=row["prepared_by_user_id"], prepared_at=row["prepared_at"],
        )

    @staticmethod
    def _posting_from_row(row) -> EclAllowancePosting:
        return EclAllowancePosting(
            id=row["id"], preparation_id=row["preparation_id"], measurement_id=row["measurement_id"],
            loan_id=row["loan_id"], client_id=row["client_id"], measurement_version=int(row["measurement_version"]),
            calculation_digest=str(row["calculation_digest"]), journal_entry_id=row["journal_entry_id"],
            source_event_key=str(row["source_event_key"]), posting_date=row["posting_date"],
            fiscal_period_id=row["fiscal_period_id"], credit_loss_expense_account_id=row["credit_loss_expense_account_id"],
            allowance_account_id=row["allowance_account_id"], allowance_amount=row["allowance_amount"],
            prior_allowance_balance=row["prior_allowance_balance"], resulting_allowance_balance=row["resulting_allowance_balance"],
            preparation_review_token=str(row["preparation_review_token"]), preparation_digest=str(row["preparation_digest"]),
            posting_review_token=str(row["posting_review_token"]), draft_policy_version=str(row["draft_policy_version"]),
            posting_policy_version=str(row["posting_policy_version"]), entry_number=str(row["entry_number"]),
            posted_by_user_id=row["posted_by_user_id"], posted_at=row["posted_at"],
        )

    @staticmethod
    def _translate_error(error: psycopg.Error) -> EclAllowancePostingError:
        message = str(error).split("CONTEXT:", 1)[0].strip()
        lowered = message.lower()
        if "was not found" in lowered:
            return EclAllowancePostingNotFound(message)
        blocked_markers = (
            "required", "blocked", "changed", "invalid", "unsupported", "cannot",
            "a5", "reconcile", "reconciles", "immutable", "current authoritative",
            "no longer current", "prior allowance", "open fiscal period",
        )
        if any(marker in lowered for marker in blocked_markers):
            return EclAllowancePostingBlocked(message)
        return EclAllowancePostingError(message or "Protected ECL allowance posting failed.")
