"""Immutable evidence attribution and reconciliation of existing liability GL lines."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, LiteralString
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .accounting_book_repository import book_identity_payload, read_book_identity
from .accounting_query import require_row
from .database import open_connection


class LiabilityControlError(RuntimeError):
    code = "liability_control_unavailable"


class LiabilityControlDenied(LiabilityControlError):
    code = "liability_control_permission_required"


class LiabilityControlConflict(LiabilityControlError):
    code = "liability_control_conflict"


def _error(error: psycopg.Error) -> LiabilityControlError:
    if error.sqlstate == "42501":
        return LiabilityControlDenied(
            "Current Management accounting permission is required."
        )
    if error.sqlstate in {
        "22023",
        "22P02",
        "22007",
        "22008",
        "55000",
        "23514",
        "23505",
    }:
        return LiabilityControlConflict(
            error.diag.message_primary or "Liability source evidence was rejected."
        )
    return LiabilityControlError("Liability control evidence is unavailable.")


def _payload(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, ".2f")
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _payload(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_payload(item) for item in value]
    return value


class PostgresLiabilityControlRepository:
    def load_schedule(
        self, *, actor_user_id: UUID, as_of: date | None = None
    ) -> dict[str, object]:
        try:
            with (
                open_connection() as connection,
                connection.cursor(row_factory=dict_row) as cursor,
            ):
                # Authorization retains share locks, so this snapshot is not READ ONLY.
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                cursor.execute(
                    "SELECT accounting.require_liability_actor(%s,'accounting.view')",
                    (actor_user_id,),
                )
                book = book_identity_payload(read_book_identity(cursor))
                if as_of is None:
                    cursor.execute(
                        "SELECT (clock_timestamp() AT TIME ZONE 'Asia/Manila')::date AS as_of"
                    )
                    as_of = require_row(cursor.fetchone())["as_of"]
                cursor.execute(
                    "SELECT * FROM accounting.liability_control_schedule(%s)", (as_of,)
                )
                obligations = cursor.fetchall()
                cursor.execute(
                    "SELECT * FROM accounting.liability_control_reconciliation(%s)",
                    (as_of,),
                )
                reconciliation = cursor.fetchall()
                cursor.execute(
                    """SELECT claim.id AS claim_id,claim.obligation_id,claim.journal_line_id,
                              claim.kind,claim.reverses_claim_id,claim.posting_date,claim.signed_amount,
                              claim.payload,claim.created_by_user_id,claim.created_at
                       FROM accounting.liability_line_claims claim
                       WHERE claim.posting_date<=%s ORDER BY claim.posting_date,claim.id""",
                    (as_of,),
                )
                movements = cursor.fetchall()
                cursor.execute(
                    """SELECT line.id AS journal_line_id,journal.id AS journal_entry_id,journal.entry_number,
                              account.code AS account_code,journal.posting_date,line.debit,line.credit,
                              journal.source_type,journal.source_reference,journal.reversal_of_entry_id
                       FROM accounting.journal_lines line
                       JOIN accounting.journal_entries journal ON journal.id=line.journal_entry_id
                       JOIN accounting.accounts account ON account.id=line.account_id
                       LEFT JOIN accounting.liability_line_claims claim ON claim.journal_line_id=line.id
                       WHERE account.code IN ('2000','2300','2310','2320','2330','2340')
                         AND journal.status='posted' AND journal.posting_date<=%s AND claim.id IS NULL
                       ORDER BY journal.posting_date,journal.id,line.line_number""",
                    (as_of,),
                )
                unregistered = cursor.fetchall()
                reconciled = all(
                    row["difference"] == 0 and row["unregistered_line_count"] == 0
                    for row in reconciliation
                )
                return _payload(
                    {
                        "book": book,
                        "as_of": as_of,
                        "obligations": obligations,
                        "movements": movements,
                        "reconciliation": reconciliation,
                        "unregistered_lines": unregistered,
                        "registered_controls_reconciled": book["status"] == "configured"
                        and reconciled,
                        "comprehensive_source_coverage": False,
                        "notice": "This schedule attributes existing posted generic liability lines; it creates no cash or journal entry. Unpaid reconciled obligations are valid. Treasury, Collector and tax require their dedicated schedules.",
                    }
                )
        except psycopg.Error as error:
            raise _error(error) from error

    def register_obligation(
        self,
        *,
        request_id: UUID,
        expected_book_id: UUID,
        payload: dict[str, object],
        actor_user_id: UUID,
    ) -> UUID:
        return self._write(
            "SELECT accounting.register_liability_obligation(%s,%s,%s,%s) AS id",
            request_id,
            expected_book_id,
            payload,
            actor_user_id,
        )

    def record_movement(
        self,
        *,
        request_id: UUID,
        expected_book_id: UUID,
        payload: dict[str, object],
        actor_user_id: UUID,
    ) -> UUID:
        return self._write(
            "SELECT accounting.record_liability_movement(%s,%s,%s,%s) AS id",
            request_id,
            expected_book_id,
            payload,
            actor_user_id,
        )

    @staticmethod
    def _write(
        query: LiteralString,
        request_id: UUID,
        expected_book_id: UUID,
        payload: dict[str, object],
        actor_user_id: UUID,
    ) -> UUID:
        try:
            with (
                open_connection() as connection,
                connection.cursor(row_factory=dict_row) as cursor,
            ):
                cursor.execute(
                    query, (request_id, expected_book_id, Jsonb(payload), actor_user_id)
                )
                return require_row(cursor.fetchone())["id"]
        except psycopg.Error as error:
            raise _error(error) from error
