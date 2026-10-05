from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection
from .treasury_authorization import TreasuryDenied, require_account

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
    source_blocker_count: int = 0
    comprehensive_source_coverage: bool = False


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

    @classmethod
    def _queue(cls) -> str:
        # Apply live source evidence before filtering readiness, including late
        # evidence for an already closed period. Preserve the immutable close.
        fields = []
        for column in cls._COLUMNS.replace("\n", "").split(","):
            name = column.strip()
            if name == "close_status":
                fields.append(
                    "CASE WHEN s.blocker_count > 0 THEN s.source_close_status ELSE q.close_status END AS close_status"
                )
            elif name == "close_blocker":
                fields.append(
                    "CASE WHEN s.blocker_count > 0 THEN 'Unreconciled accounting sources require review.' ELSE q.close_blocker END AS close_blocker"
                )
            else:
                fields.append(f"q.{name}")
        fields.extend(
            [
                "s.blocker_count AS source_blocker_count",
                "s.comprehensive_source_coverage",
            ]
        )
        return (
            "(SELECT "
            + ", ".join(fields)
            + " FROM accounting.period_close_queue q JOIN accounting.period_source_close_state s USING (fiscal_period_id)) source_queue"
        )

    def list_items(
        self, *, status: str = "all", limit: int = 100, offset: int = 0
    ) -> tuple[PeriodCloseItem, ...]:
        where = self._status_where(status)
        with (
            open_connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            cursor.execute(
                f"""
                SELECT *
                FROM {self._queue()}
                WHERE {where}
                ORDER BY start_date DESC, fiscal_period_id
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            return tuple(PeriodCloseItem(**dict(row)) for row in cursor.fetchall())

    def get_item(self, fiscal_period_id: UUID) -> PeriodCloseItem:
        with (
            open_connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            cursor.execute(
                f"""
                SELECT *
                FROM {self._queue()}
                WHERE fiscal_period_id=%s
                """,
                (fiscal_period_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise PeriodCloseBlocked("Accounting period close item was not found.")
            return PeriodCloseItem(**dict(row))

    def source_coverage(
        self, fiscal_period_id: UUID, *, actor, limit: int = 100, offset: int = 0
    ) -> dict[str, object]:
        with (
            open_connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            # Authorization takes row-share locks; use one snapshot while
            # allowing those locks, and never return private wallet facts
            # solely because someone has accounting view permission.
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            cursor.execute(
                "SELECT * FROM accounting.period_source_close_state WHERE fiscal_period_id=%s",
                (fiscal_period_id,),
            )
            state = cursor.fetchone()
            if state is None:
                raise PeriodCloseBlocked("Accounting period was not found.")
            cursor.execute(
                """SELECT * FROM accounting.period_source_blockers(%s)
                ORDER BY effective_date,source_type,source_id LIMIT %s OFFSET %s""",
                (fiscal_period_id, limit, offset),
            )
            rows = cursor.fetchall()
            blockers = []
            # NULL scope denotes non-wallet accounting evidence already covered
            # by the route's current Management accounting-view authorization.
            visibility = {None: True}
            with connection.cursor(row_factory=dict_row) as authorization_cursor:
                for row in rows:
                    account_id = row["account_id"]
                    if account_id not in visibility:
                        try:
                            require_account(
                                authorization_cursor,
                                actor,
                                account_id,
                                "treasury.view",
                                lock=False,
                                private=True,
                            )
                            visibility[account_id] = True
                        except TreasuryDenied:
                            visibility[account_id] = False
                    if not visibility[account_id]:
                        blockers.append(
                            {
                                "source_type": "restricted_source",
                                "source_id": None,
                                "effective_date": None,
                                "amount": None,
                                "reason": "treasury_account_access_required",
                            }
                        )
                        continue
                    blockers.append(
                        {
                            "source_type": row["source_type"],
                            "source_id": str(row["source_id"]),
                            "effective_date": row["effective_date"].isoformat(),
                            "amount": format(row["amount"], ".2f")
                            if row["amount"] is not None
                            else None,
                            "reason": row["reason"],
                        }
                    )
            return {
                "fiscal_period_id": str(fiscal_period_id),
                "comprehensive_source_coverage": False,
                "source_families": state.get(
                    "source_families", ["treasury", "collector"]
                ),
                "coverage_policy": state["coverage_policy"],
                "source_close_status": state["source_close_status"],
                "blocker_count": state["blocker_count"],
                "limit": limit,
                "offset": offset,
                "blockers": blockers,
                "notice": "Evidence amounts may describe the same money and must not be added together. This inventory covers the listed source families; unsupported accounting and period-end assessments remain explicit blockers.",
            }

    def summary(self) -> dict[str, object]:
        with (
            open_connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            # Retain historical closed totals but make live readiness counts
            # agree with the queue when late source evidence arrives.
            cursor.execute(f"""
                SELECT historical.*,
                    live.ready_for_review_count AS live_ready_for_review_count,
                    live.ready_to_prepare_count AS live_ready_to_prepare_count,
                    live.prepared_count AS live_prepared_count,
                    live.blocked_count AS live_blocked_count,
                    live.source_review_required_count
                FROM accounting.period_close_summary historical
                CROSS JOIN (
                    SELECT count(*) FILTER (WHERE close_status='ready_for_review') AS ready_for_review_count,
                        count(*) FILTER (WHERE close_status='ready_to_prepare') AS ready_to_prepare_count,
                        count(*) FILTER (WHERE close_status='prepared_confirmation_required') AS prepared_count,
                        count(*) FILTER (WHERE close_status LIKE 'blocked_%' OR close_status='closed_source_review_required') AS blocked_count,
                        count(*) FILTER (WHERE source_blocker_count > 0) AS source_review_required_count
                    FROM {self._queue()}
                ) live
            """)
            row = cursor.fetchone()
            if row is None:
                raise PeriodCloseError("Formal period-close summary is unavailable.")
            result = dict(row)
            for field in (
                "ready_for_review_count",
                "ready_to_prepare_count",
                "prepared_count",
                "blocked_count",
            ):
                result[field] = result.pop("live_" + field)
            result["comprehensive_source_coverage"] = False
            return result

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
            "closed": "fiscal_period_status = 'closed'",
            "blocked": "close_status LIKE 'blocked_%%' OR close_status IN ('closed_legacy_without_protected_close_audit', 'closed_source_review_required')",
        }
        clause = clauses.get(status)
        if clause is None:
            raise ValueError("Unsupported formal period-close status filter.")
        return clause

    @staticmethod
    def _call_id(query: str, params: tuple[object, ...]) -> UUID:
        try:
            with (
                open_connection() as connection,
                connection.cursor(row_factory=dict_row) as cursor,
            ):
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
