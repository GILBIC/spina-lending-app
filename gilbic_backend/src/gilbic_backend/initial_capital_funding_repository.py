from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection


POLICY = "initial_capital_funding_v1"


class InitialCapitalFundingError(RuntimeError):
    code = "initial_capital_funding_error"


class InitialCapitalFundingBlocked(InitialCapitalFundingError):
    code = "initial_capital_funding_blocked"


@dataclass(frozen=True, slots=True)
class InitialCapitalFundingItem:
    evidence_id: UUID
    funding_date: date
    amount: Decimal
    cash_account_code: str
    cash_account_name: str
    capital_account_code: str
    evidence_source: str
    evidence_reference: str
    evidence_digest: str
    evidence_note: str
    recorded_by_user_id: UUID
    recorded_at: datetime
    journal_entry_id: UUID | None
    journal_status: str | None
    entry_number: str | None
    fiscal_period_id: UUID | None
    prepared_by_user_id: UUID | None
    prepared_at: datetime | None
    confirmation_digest: str | None
    posted_by_user_id: UUID | None
    posted_at: datetime | None
    accounting_status: str
    accounting_blocker: str | None
    protected_initial_capital_funding_enabled: bool
    synthetic_opening_balance_required: bool
    automatic_source_posting: bool


@dataclass(frozen=True, slots=True)
class InitialCapitalFundingSummary:
    evidence_count: int
    evidence_ready_count: int
    prepared_not_posted_count: int
    posted_count: int
    blocked_no_open_period_count: int
    total_amount: Decimal
    posted_amount: Decimal


@dataclass(frozen=True, slots=True)
class EligibleInitialCapitalCashAccount:
    code: str
    name: str


class PostgresInitialCapitalFundingRepository:
    _COLUMNS = """
        evidence_id, funding_date, amount, cash_account_code, cash_account_name,
        capital_account_code, evidence_source, evidence_reference, evidence_digest,
        evidence_note, recorded_by_user_id, recorded_at, journal_entry_id,
        journal_status, entry_number, fiscal_period_id, prepared_by_user_id,
        prepared_at, confirmation_digest, posted_by_user_id, posted_at,
        accounting_status, accounting_blocker,
        protected_initial_capital_funding_enabled,
        synthetic_opening_balance_required, automatic_source_posting
    """

    def list_items(self, *, limit: int = 100, offset: int = 0) -> tuple[InitialCapitalFundingItem, ...]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {self._COLUMNS}
                    FROM accounting.initial_capital_funding_queue
                    ORDER BY funding_date DESC, recorded_at DESC, evidence_id
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                return tuple(
                    InitialCapitalFundingItem(**dict(row)) for row in cursor.fetchall()
                )

    def list_summary(self) -> InitialCapitalFundingSummary:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        count(*)::integer AS evidence_count,
                        count(*) FILTER (
                            WHERE accounting_status = 'evidence_ready'
                        )::integer AS evidence_ready_count,
                        count(*) FILTER (
                            WHERE accounting_status = 'prepared_not_posted'
                        )::integer AS prepared_not_posted_count,
                        count(*) FILTER (
                            WHERE accounting_status = 'posted'
                        )::integer AS posted_count,
                        count(*) FILTER (
                            WHERE accounting_status = 'blocked_no_open_period'
                        )::integer AS blocked_no_open_period_count,
                        coalesce(sum(amount), 0)::numeric(18,2) AS total_amount,
                        coalesce(sum(amount) FILTER (
                            WHERE accounting_status = 'posted'
                        ), 0)::numeric(18,2) AS posted_amount
                    FROM accounting.initial_capital_funding_queue
                    """
                )
                row = cursor.fetchone()
                if row is None:
                    raise InitialCapitalFundingBlocked(
                        "Protected initial-capital summary returned no result."
                    )
                return InitialCapitalFundingSummary(**dict(row))

    def list_eligible_cash_accounts(
        self,
    ) -> tuple[EligibleInitialCapitalCashAccount, ...]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT code, name
                    FROM accounting.accounts
                    WHERE system_key IN ('cash_office', 'cash_bank_gcash')
                      AND account_type = 'asset'
                      AND normal_balance = 'debit'
                      AND is_active
                      AND is_posting
                    ORDER BY code, id
                    """
                )
                return tuple(
                    EligibleInitialCapitalCashAccount(**dict(row))
                    for row in cursor.fetchall()
                )

    def get_item(self, evidence_id: UUID) -> InitialCapitalFundingItem:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"SELECT {self._COLUMNS} FROM accounting.initial_capital_funding_queue WHERE evidence_id=%s",
                    (evidence_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise InitialCapitalFundingBlocked(
                        "Initial-capital funding evidence was not found."
                    )
                return InitialCapitalFundingItem(**dict(row))

    def record_evidence(
        self,
        *,
        actor_user_id: UUID,
        idempotency_key: UUID,
        funding_date: date,
        amount: Decimal,
        cash_account_code: str,
        evidence_source: str,
        evidence_reference: str,
        evidence_digest: str,
        evidence_note: str,
    ) -> UUID:
        return self._call_id(
            """
            SELECT accounting.record_initial_capital_funding_evidence(
                %s,%s,%s,%s,%s,%s,%s,%s,%s
            ) AS id
            """,
            (
                actor_user_id,
                idempotency_key,
                funding_date,
                amount,
                cash_account_code,
                evidence_source,
                evidence_reference,
                evidence_digest,
                evidence_note,
            ),
        )

    def prepare(self, *, evidence_id: UUID, actor_user_id: UUID) -> UUID:
        return self._call_id(
            "SELECT accounting.prepare_initial_capital_funding_journal(%s,%s) AS id",
            (evidence_id, actor_user_id),
        )

    def post(
        self,
        *,
        evidence_id: UUID,
        actor_user_id: UUID,
        confirmation_token: str,
        expected_evidence_digest: str,
        expected_amount: Decimal,
        expected_cash_account_code: str,
        expected_posting_date: date,
        expected_fiscal_period_id: UUID,
        policy_version: str = POLICY,
    ) -> UUID:
        return self._call_id(
            """
            SELECT accounting.post_initial_capital_funding_journal(
                %s,%s,%s,%s,%s,%s,%s,%s,%s
            ) AS id
            """,
            (
                evidence_id,
                actor_user_id,
                confirmation_token,
                expected_evidence_digest,
                expected_amount,
                expected_cash_account_code,
                expected_posting_date,
                expected_fiscal_period_id,
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
                        raise InitialCapitalFundingBlocked(
                            "Protected initial-capital action returned no immutable identifier."
                        )
                    result = UUID(str(row["id"]))
                connection.commit()
                return result
        except InitialCapitalFundingError:
            raise
        except psycopg.Error as exc:
            message = str(exc).split("CONTEXT:", 1)[0].strip()
            raise InitialCapitalFundingBlocked(message) from exc
