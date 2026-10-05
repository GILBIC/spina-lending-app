"""Retain reviewed presentation evidence independently from monetary posting."""

from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .database import open_connection


class ReportingEvidenceError(RuntimeError):
    def __init__(self, message, *, status=409):
        super().__init__(message)
        self.status = status


def read_reporting_policy(cursor, period_id):
    # Preserve posted-ledger reports during an incremental migration rollout.
    cursor.execute(
        "SELECT to_regclass('accounting.reporting_policy_versions') AS relation"
    )
    if cursor.fetchone()["relation"] is None:
        return None
    cursor.execute(
        "SELECT * FROM accounting.reporting_policy_versions WHERE fiscal_period_id=%s ORDER BY version DESC LIMIT 1",
        (period_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    cursor.execute(
        "SELECT accounting.reporting_cash_definition(%s) AS cash_accounts",
        (row["payload"]["cash_account_codes"],),
    )
    valid = (
        row["cash_accounts"] is not None
        and row["cash_accounts"] == cursor.fetchone()["cash_accounts"]
    )
    return row["payload"] | {
        "cash_definition_valid": valid,
        "cash_definition_status": "retained_definition_current"
        if valid
        else "cash_definition_changed",
        "id": str(row["id"]),
        "book_id": str(row["book_id"]),
        "fiscal_period_id": str(row["fiscal_period_id"]),
        "version": row["version"],
        "reviewed_by_user_id": str(row["actor_user_id"]),
        "reviewed_at": row["created_at"].isoformat(),
    }


def read_internal_transfer_principals(cursor, period_id):
    """Private grouping authority for the same statement snapshot, never client input."""
    cursor.execute(
        "SELECT to_regclass('accounting.treasury_transfer_posting_status') AS relation"
    )
    if cursor.fetchone()["relation"] is None:
        return {}
    cursor.execute(
        """SELECT line.id AS journal_line_id,proof.transfer_id,proof.leg,
            CASE proof.leg WHEN 'source' THEN -proof.amount ELSE proof.amount END AS principal
        FROM accounting.treasury_transfer_posting_status proof
        JOIN accounting.treasury_transfer_preparations preparation ON preparation.id=proof.preparation_id
        JOIN accounting.journal_entries journal ON journal.id=proof.journal_entry_id
        JOIN accounting.journal_lines line ON line.journal_entry_id=journal.id
        WHERE proof.exact_posted AND NOT proof.correction_pending
          AND proof.book_id=(SELECT id FROM accounting.book_identity WHERE singleton)
          AND journal.fiscal_period_id=%s AND journal.status='posted'
          AND journal.source_type='treasury_owned_transfer'
          AND line.account_id=(CASE proof.leg WHEN 'source'
            THEN preparation.snapshot#>>'{source_mapping,cash_account_id}'
            ELSE preparation.snapshot#>>'{destination_mapping,cash_account_id}' END)::uuid
          AND line.debit-line.credit=CASE proof.leg WHEN 'source'
            THEN -proof.amount-proof.fee ELSE proof.amount END""",
        (period_id,),
    )
    return {
        row["journal_line_id"]: {
            "transfer_id": str(row["transfer_id"]),
            "leg": row["leg"],
            "principal": row["principal"],
        }
        for row in cursor.fetchall()
    }


def read_internal_collector_cash(cursor, period_id):
    """Exact custody cash use and handover proof; an application has no internal leg."""
    cursor.execute(
        "SELECT to_regclass('accounting.collector_liability_posting_status') AS relation"
    )
    if cursor.fetchone()["relation"] is None:
        return {}
    cursor.execute(
        """SELECT line.id AS journal_line_id,proof.source_kind,proof.source_id,
            journal.id AS journal_entry_id,CASE WHEN proof.source_kind='settlement'
            THEN coalesce(prepared.snapshot#>>'{source_facts,physical_principal}',
                prepared.snapshot#>>'{source_facts,gross}')::numeric *
                CASE WHEN account.code='1020' THEN -1 ELSE 1 END
            ELSE 0 END AS internal_principal
        FROM accounting.collector_liability_posting_status proof
        JOIN accounting.collector_liability_preparations prepared ON prepared.id=proof.preparation_id
        JOIN accounting.journal_entries journal ON journal.id=proof.journal_entry_id
        JOIN accounting.journal_lines line ON line.journal_entry_id=journal.id
        JOIN accounting.accounts account ON account.id=line.account_id
        WHERE proof.exact_posted AND NOT proof.correction_pending
          AND proof.book_id=(SELECT id FROM accounting.book_identity WHERE singleton)
          AND journal.fiscal_period_id=%s AND journal.status='posted'
          AND journal.source_type='collector_liability'
          AND proof.source_kind IN('settlement','return_debit','return_reversal','credit_application')
          AND (proof.source_kind<>'credit_application' OR (account.code='1020' AND line.credit>0 AND line.debit=0))
          AND account.code IN('1010','1020','1030')""",
        (period_id,),
    )
    return {
        row["journal_line_id"]: {
            "source_kind": row["source_kind"],
            "source_id": str(row["source_id"]),
            "journal_entry_id": str(row["journal_entry_id"]),
            "internal_principal": row["internal_principal"],
        }
        for row in cursor.fetchall()
    }


class PostgresReportingEvidenceRepository:
    def load_policy(self, *, period_id, actor_user_id):
        try:
            with (
                open_connection() as connection,
                connection.cursor(row_factory=dict_row) as cursor,
            ):
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                cursor.execute(
                    "SELECT accounting.require_liability_actor(%s,'accounting.view')",
                    (actor_user_id,),
                )
                return read_reporting_policy(cursor, period_id)
        except psycopg.Error as error:
            raise ReportingEvidenceError(
                "Reporting evidence is unavailable.",
                status=403 if error.sqlstate == "42501" else 503,
            ) from error

    def retain_policy(
        self,
        *,
        request_id,
        book_id,
        period_id,
        expected_version,
        payload,
        actor_user_id,
    ):
        return self._write(
            "SELECT accounting.retain_reporting_policy(%s,%s,%s,%s,%s,%s) AS id",
            (
                request_id,
                book_id,
                period_id,
                expected_version,
                Jsonb(payload),
                actor_user_id,
            ),
        )

    def retain_classification(
        self, *, request_id, book_id, policy_id, payload, actor_user_id
    ):
        return self._write(
            "SELECT accounting.retain_cash_flow_classification(%s,%s,%s,%s,%s) AS id",
            (request_id, book_id, policy_id, Jsonb(payload), actor_user_id),
        )

    @staticmethod
    def _write(query, params):
        try:
            with (
                open_connection() as connection,
                connection.cursor(row_factory=dict_row) as cursor,
            ):
                cursor.execute(query, params)
                return UUID(str(cursor.fetchone()["id"]))
        except psycopg.Error as error:
            status = (
                403
                if error.sqlstate == "42501"
                else 409
                if error.sqlstate in {"22023", "22P02", "55000", "23514", "23505"}
                else 503
            )
            raise ReportingEvidenceError(
                error.diag.message_primary
                if status == 409
                else "Reporting evidence could not be retained.",
                status=status,
            ) from error
