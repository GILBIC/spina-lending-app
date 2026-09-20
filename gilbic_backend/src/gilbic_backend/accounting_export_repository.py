"""Complete, bounded accounting reads in a single repeatable read snapshot."""

import json
from datetime import date
from decimal import Decimal
from functools import partial
from typing import Any, LiteralString

from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import set_json_loads

from .accounting_export import (
    MAX_BYTES,
    MAX_ROWS,
    AccountingExportError,
    json_bytes,
    validate_range,
)
from .database import open_connection


class PostgresAccountingExportRepository:
    def load_snapshot(self, *, start_date: date, end_date: date) -> dict[str, Any]:
        validate_range(start_date, end_date)
        with (
            open_connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            set_json_loads(partial(json.loads, parse_float=Decimal), connection)
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '15000ms'")
            cursor.execute("SET LOCAL TIME ZONE 'Asia/Manila'")
            cursor.execute("SELECT transaction_timestamp() AS generated_at")
            timestamp = cursor.fetchone()
            if timestamp is None:
                raise AccountingExportError(
                    "integrity", "Accounting snapshot time is unavailable."
                )
            result: dict[str, Any] = dict(timestamp)
            # Opening balances must not hide malformed historical entries.
            cursor.execute(
                """SELECT journal.id
                   FROM accounting.journal_entries journal
                   LEFT JOIN accounting.journal_lines line
                     ON line.journal_entry_id = journal.id
                   WHERE journal.status = 'posted' AND journal.posting_date <= %s
                   GROUP BY journal.id
                   HAVING count(line.id) < 2 OR sum(line.debit) <> sum(line.credit)
                       OR coalesce(sum(line.debit), 0) <= 0
                   LIMIT 1""",
                (end_date,),
            )
            if cursor.fetchone() is not None:
                raise AccountingExportError(
                    "integrity", "Posted ledger integrity review is required."
                )
            consumed = 0

            def read(name: str, query: LiteralString, parameters: tuple) -> None:
                nonlocal consumed
                # Check source byte volume on the server before even one wide
                # JSONB record is materialized in Python. Named cursors then
                # avoid libpq buffering an entire dataset before row checks.
                cursor.execute(
                    sql.SQL(
                        "SELECT count(*) AS row_count, coalesce(sum(octet_length(to_jsonb(export_row)::text)),0) AS estimated_bytes FROM ({}) AS export_row"
                    ).format(sql.SQL(query)),
                    parameters,
                )
                size = cursor.fetchone()
                if (
                    size is None
                    or size["row_count"] > MAX_ROWS
                    or size["estimated_bytes"] + consumed > MAX_BYTES
                ):
                    raise AccountingExportError(
                        "oversized",
                        "Export exceeds resource limits; select a shorter range.",
                    )
                rows = []
                with connection.cursor(
                    name=f"accounting_export_{name}", row_factory=dict_row
                ) as streamed:
                    streamed.execute(query, parameters)
                    for row in streamed:
                        if len(rows) >= MAX_ROWS:
                            raise AccountingExportError(
                                "oversized",
                                "Export exceeds the row limit; select a shorter range.",
                            )
                        consumed += len(json_bytes(row))
                        if consumed > MAX_BYTES:
                            raise AccountingExportError(
                                "oversized",
                                "Export exceeds the content limit; select a shorter range.",
                            )
                        rows.append(dict(row))
                result[name] = rows

            read(
                "accounts",
                """SELECT account.id AS account_id, account.code AS account_code,
                          account.system_key, account.name AS account_name,
                          account.account_type, account.normal_balance,
                          account.is_active, account.is_posting,
                          coalesce(sum(line.debit) FILTER (WHERE journal.posting_date < %s),0) AS opening_debit,
                          coalesce(sum(line.credit) FILTER (WHERE journal.posting_date < %s),0) AS opening_credit,
                          coalesce(sum(line.debit) FILTER (WHERE journal.posting_date >= %s),0) AS movement_debit,
                          coalesce(sum(line.credit) FILTER (WHERE journal.posting_date >= %s),0) AS movement_credit
                   FROM accounting.accounts account
                   LEFT JOIN (accounting.journal_lines line
                     JOIN accounting.journal_entries journal
                       ON journal.id = line.journal_entry_id
                      AND journal.status = 'posted' AND journal.posting_date <= %s)
                     ON line.account_id = account.id
                   GROUP BY account.id ORDER BY account.code, account.id LIMIT 100001""",
                (start_date, start_date, start_date, start_date, end_date),
            )
            read(
                "journals",
                """SELECT journal.id AS entry_id, journal.entry_number,
                          journal.fiscal_period_id AS period_id, journal.posting_date,
                          journal.description AS entry_description, journal.source_type,
                          journal.source_reference, journal.source_event_key,
                          journal.reversal_of_entry_id, journal.created_by_user_id,
                          journal.posted_by_user_id, journal.created_at, journal.posted_at,
                          line.line_number, account.code AS account_code,
                          account.name AS account_name, line.description AS line_description,
                          line.debit, line.credit, line.client_id, line.loan_id
                   FROM accounting.journal_entries journal
                   JOIN accounting.journal_lines line ON line.journal_entry_id = journal.id
                   JOIN accounting.accounts account ON account.id = line.account_id
                   WHERE journal.status = 'posted' AND journal.posting_date BETWEEN %s AND %s
                   ORDER BY journal.posting_date, journal.id, line.line_number LIMIT 100001""",
                (start_date, end_date),
            )
            read(
                "periods",
                """SELECT id, label, start_date, end_date, status
                   FROM accounting.fiscal_periods
                   WHERE start_date <= %s AND end_date >= %s
                   ORDER BY start_date, id LIMIT 100001""",
                (end_date, start_date),
            )
            read(
                "audit",
                """SELECT event.id AS event_id, event.journal_entry_id AS entry_id,
                          journal.entry_number, journal.posting_date, journal.status,
                          event.event_type, event.actor_user_id, event.created_at,
                          event.details
                   FROM accounting.journal_events event
                   JOIN accounting.journal_entries journal ON journal.id = event.journal_entry_id
                   WHERE journal.posting_date BETWEEN %s AND %s
                   ORDER BY event.created_at, event.id LIMIT 100001""",
                (start_date, end_date),
            )
            read(
                "cancelled",
                """SELECT id, original_journal_entry_id, fiscal_period_id,
                          posting_date, description, source_type, created_by_user_id,
                          cancelled_by_user_id, lines, prior_events, cancelled_at
                   FROM accounting.cancelled_journal_draft_audit
                   WHERE posting_date BETWEEN %s AND %s
                   ORDER BY posting_date, id LIMIT 100001""",
                (start_date, end_date),
            )
            return result
