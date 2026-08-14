from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection


POLICY = "period_close_retained_earnings_v1"


class PeriodCloseError(RuntimeError):
    code = "period_close_error"


class PeriodCloseBlocked(PeriodCloseError):
    code = "period_close_blocked"


@dataclass(frozen=True, slots=True)
class PeriodCloseItem:
    fiscal_period_id: UUID
    label: str
    start_date: date
    end_date: date
    fiscal_period_status: str
    closed_by_user_id: UUID | None
    closed_at: datetime | None
    preparation_id: UUID | None
    journal_entry_id: UUID | None
    temporary_account_count: int | None
    net_income: Decimal | None
    retained_earnings_balance_before: Decimal | None
    close_digest: str | None
    close_posting_id: UUID | None
    closing_entry_number: str | None
    retained_earnings_balance_after: Decimal | None
    close_status: str
    close_blocker: str | None
    protected_period_close_enabled: bool
    retained_earnings_close_enabled: bool
    closed_period_posting_protection_enabled: bool
    period_reopen_enabled: bool
    automatic_source_posting: bool


class PostgresPeriodCloseRepository:
    _COLUMNS = """
        fiscal_period_id, label, start_date, end_date, fiscal_period_status,
        closed_by_user_id, closed_at, preparation_id, journal_entry_id,
        temporary_account_count, net_income, retained_earnings_balance_before,
        close_digest, close_posting_id, closing_entry_number,
        retained_earnings_balance_after, close_status, close_blocker,
        protected_period_close_enabled, retained_earnings_close_enabled,
        closed_period_posting_protection_enabled, period_reopen_enabled,
        automatic_source_posting
    """

    def list_items(
        self, *, status: str = "all", limit: int = 100, offset: int = 0
    ) -> tuple[PeriodCloseItem, ...]:
        where = self._status_where(status)
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {self._COLUMNS}
                    FROM accounting.period_close_queue
                    WHERE {where}
                    ORDER BY start_date DESC, fiscal_period_id
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                return tuple(PeriodCloseItem(**dict(row)) for row in cursor.fetchall())

    def get_item(self, fiscal_period_id: UUID) -> PeriodCloseItem:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {self._COLUMNS}
                    FROM accounting.period_close_queue
                    WHERE fiscal_period_id=%s
                    """,
                    (fiscal_period_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise PeriodCloseBlocked("Accounting period close item was not found.")
                return PeriodCloseItem(**dict(row))

    def summary(self) -> dict[str, object]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute("SELECT * FROM accounting.period_close_summary")
                row = cursor.fetchone()
                if row is None:
                    raise PeriodCloseError("Formal period-close summary is unavailable.")
                return dict(row)

    def prepare(self, *, fiscal_period_id: UUID, actor_user_id: UUID) -> UUID:
        return self._call_id(
            "SELECT accounting.prepare_period_close(%s,%s) AS id",
            (fiscal_period_id, actor_user_id),
        )

    def post(
        self,
        *,
        fiscal_period_id: UUID,
        actor_user_id: UUID,
        confirmation_token: str,
        expected_close_digest: str,
        expected_net_income: Decimal,
        expected_retained_earnings_account_code: str,
        expected_period_end_date: date,
        policy_version: str = POLICY,
    ) -> UUID:
        return self._call_id(
            """
            SELECT accounting.post_period_close(
                %s,%s,%s,%s,%s,%s,%s,%s
            ) AS id
            """,
            (
                fiscal_period_id,
                actor_user_id,
                confirmation_token,
                expected_close_digest,
                expected_net_income,
                expected_retained_earnings_account_code,
                expected_period_end_date,
                policy_version,
            ),
        )

    @staticmethod
    def _status_where(status: str) -> str:
        clauses = {
            "all": "true",
            "ready_for_review": "close_status = 'ready_for_review'",
            "ready_to_prepare": "close_status = 'ready_to_prepare'",
            "prepared": "close_status = 'prepared_confirmation_required'",
            "closed": "close_status = 'closed_protected'",
            "blocked": "close_status LIKE 'blocked_%' OR close_status = 'closed_legacy_without_protected_close_audit'",
        }
        clause = clauses.get(status)
        if clause is None:
            raise ValueError("Unsupported formal period-close status filter.")
        return clause

    @staticmethod
    def _call_id(query: str, params: tuple[object, ...]) -> UUID:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(query, params)
                    row = cursor.fetchone()
                    if row is None or row["id"] is None:
                        raise PeriodCloseBlocked(
                            "Protected formal period-close action returned no immutable identifier."
                        )
                    result = UUID(str(row["id"]))
                connection.commit()
                return result
        except PeriodCloseError:
            raise
        except psycopg.Error as exc:
            message = str(exc).split("CONTEXT:", 1)[0].strip()
            raise PeriodCloseBlocked(message) from exc
