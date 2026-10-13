"""All-journal disclosure coverage in one authorized database snapshot."""

from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .database import open_connection
from .financial_reporting import (
    cash_flow_statement,
    journal_disclosure_report,
    money,
    validate_disclosure_components,
)
from .reporting_evidence_repository import (
    PostgresReportingEvidenceRepository,
    ReportingEvidenceError,
    read_internal_collector_cash,
    read_internal_transfer_principals,
    read_reporting_policy,
)


def read_journal_disclosures(cursor, period_id, actor_user_id):
    # This authorization precedes opening balances, aggregates, and candidates.
    cursor.execute(
        "SELECT accounting.require_disclosure_actor(%s,%s,'accounting.view')",
        (actor_user_id, period_id),
    )
    reporting = read_reporting_policy(cursor, period_id)
    cursor.execute(
        "SELECT * FROM accounting.disclosure_policy_versions WHERE fiscal_period_id=%s ORDER BY version DESC LIMIT 1",
        (period_id,),
    )
    retained = cursor.fetchone()
    policy = None
    valid = False
    if retained:
        cursor.execute(
            "SELECT accounting.reporting_cash_definition(%s) AS definition",
            (retained["payload"]["financing_account_codes"],),
        )
        valid = bool(
            reporting
            and reporting["cash_definition_valid"]
            and str(retained["reporting_policy_id"]) == reporting["id"]
            and retained["financing_accounts"] == cursor.fetchone()["definition"]
        )
        policy = retained["payload"] | {
            "id": str(retained["id"]),
            "book_id": str(retained["book_id"]),
            "reporting_policy_id": str(retained["reporting_policy_id"]),
            "fiscal_period_id": str(period_id),
            "version": retained["version"],
            "definition_valid": valid,
            "reviewed_at": retained["created_at"].isoformat(),
        }
    cursor.execute(
        """SELECT a.code,a.name,
        coalesce(sum(l.credit-l.debit) FILTER(WHERE j.status='posted' AND j.posting_date<p.start_date),0) AS opening,
        coalesce(sum(l.credit-l.debit) FILTER(WHERE j.status='posted' AND j.posting_date<=p.end_date),0) AS closing
        FROM accounting.accounts a CROSS JOIN accounting.fiscal_periods p
        LEFT JOIN accounting.journal_lines l ON l.account_id=a.id LEFT JOIN accounting.journal_entries j ON j.id=l.journal_entry_id
        WHERE p.id=%s AND a.code=ANY(%s) GROUP BY a.id ORDER BY a.code""",
        (period_id, policy["financing_account_codes"] if policy else []),
    )
    financing = list(cursor.fetchall())
    cursor.execute(
        """SELECT j.id,j.entry_number,j.posting_date,j.source_type,j.reversal_of_entry_id,
        accounting.journal_disclosure_protected_kind(j.id) AS protected_kind,
        accounting.journal_disclosure_source_status(j.id) AS source_status,
        accounting.journal_disclosure_digest(j.id,%s) AS source_digest,
        r.id AS review_id,r.version AS review_version,r.disclosure_policy_id,
        r.source_digest AS retained_digest,r.payload,r.created_at AS reviewed_at
        FROM accounting.journal_entries j LEFT JOIN LATERAL
          (SELECT * FROM accounting.journal_disclosure_reviews WHERE journal_entry_id=j.id ORDER BY version DESC LIMIT 1) r ON true
        WHERE j.fiscal_period_id=%s AND j.status='posted' ORDER BY j.posting_date,j.id""",
        (UUID(reporting["id"]) if reporting else None, period_id),
    )
    rows = list(cursor.fetchall())
    cursor.execute(
        """SELECT l.id,l.journal_entry_id,a.code AS account_code,a.name AS account_name,l.debit,l.credit,
        c.payload->'allocations' AS cash_allocations FROM accounting.journal_lines l
        JOIN accounting.journal_entries j ON j.id=l.journal_entry_id JOIN accounting.accounts a ON a.id=l.account_id
        LEFT JOIN LATERAL(SELECT payload FROM accounting.cash_flow_classifications WHERE journal_line_id=l.id AND policy_id=%s ORDER BY version DESC LIMIT 1) c ON true
        WHERE j.fiscal_period_id=%s AND j.status='posted' ORDER BY j.id,l.line_number""",
        (UUID(reporting["id"]) if reporting else None, period_id),
    )
    line_rows = list(cursor.fetchall())
    by_journal, cash_lines = {}, []
    transfers = read_internal_transfer_principals(cursor, period_id)
    collector = read_internal_collector_cash(cursor, period_id)
    journal_map = {row["id"]: row for row in rows}
    cash_codes = reporting["cash_account_codes"] if reporting else []
    for line in line_rows:
        journal = journal_map[line["journal_entry_id"]]
        public = {
            "id": str(line["id"]),
            "account_code": line["account_code"],
            "account_name": line["account_name"],
            "debit": money(line["debit"]),
            "credit": money(line["credit"]),
            "cash_allocations": line["cash_allocations"]
            if line["account_code"] in cash_codes
            else None,
        }
        by_journal.setdefault(line["journal_entry_id"], []).append(public)
        if line["account_code"] in cash_codes:
            cash_lines.append(
                {
                    "journal_line_id": line["id"],
                    "journal_entry_id": line["journal_entry_id"],
                    "account_code": line["account_code"],
                    "entry_number": journal["entry_number"],
                    "source_type": journal["source_type"],
                    "amount": line["debit"] - line["credit"],
                    "allocations": line["cash_allocations"],
                    "is_opening_adjustment": journal["protected_kind"]
                    in {"opening", "opening_reversal"},
                    "internal_transfer": transfers.get(line["id"]),
                    "collector_cash": collector.get(line["id"]),
                }
            )
    cash_check = cash_flow_statement(
        policy=reporting,
        opening_cash=Decimal(0),
        closing_cash=sum((line["amount"] for line in cash_lines), Decimal(0)),
        lines=cash_lines,
    )
    invalid_cash = {
        line["journal_entry_id"] for line in cash_check["unclassified_lines"]
    }
    cash_allocations = {
        str(line["journal_line_id"]): line["allocations"] for line in cash_lines
    }
    journals = []
    for row in rows:
        components = row["payload"]["components"] if row["payload"] else None
        status = (
            "review_required"
            if not row["review_id"]
            else "policy_changed"
            if not policy or str(row["disclosure_policy_id"]) != policy["id"]
            else "source_changed"
            if row["retained_digest"] != row["source_digest"]
            else "current"
        )
        if status == "current":
            try:
                validate_disclosure_components(
                    lines=by_journal[row["id"]],
                    components=components,
                    cash_account_codes=cash_codes,
                    cash_allocations=cash_allocations,
                )
            except (ValueError, KeyError, TypeError):
                status = "component_review_required"
        source_status = row["source_status"]
        if source_status == "current" and str(row["id"]) in invalid_cash:
            source_status = "cash_review_required"
        journals.append(
            {
                "journal_entry_id": str(row["id"]),
                "entry_number": row["entry_number"],
                "posting_date": row["posting_date"].isoformat(),
                "source_type": row["source_type"],
                "reversal_of_entry_id": str(row["reversal_of_entry_id"])
                if row["reversal_of_entry_id"]
                else None,
                "protected_kind": row["protected_kind"],
                "source_status": source_status,
                "review_status": status,
                "review_version": row["review_version"] or 0,
                "review_id": str(row["review_id"]) if row["review_id"] else None,
                "reviewed_at": row["reviewed_at"].isoformat()
                if row["reviewed_at"]
                else None,
                "source_digest": row["source_digest"],
                "lines": by_journal.get(row["id"], []),
                "components": components,
                "reason": row["payload"]["reason"] if row["payload"] else None,
            }
        )
    result = journal_disclosure_report(
        policy_valid=valid, financing_accounts=financing, journals=journals
    )
    cursor.execute(
        "SELECT code,name FROM accounting.accounts WHERE account_type='liability' AND normal_balance='credit' AND is_posting ORDER BY code"
    )
    options = list(cursor.fetchall())
    cursor.execute(
        "SELECT id,label,start_date,end_date,status FROM accounting.fiscal_periods WHERE id=%s",
        (period_id,),
    )
    period = cursor.fetchone()
    cursor.execute("SELECT id FROM accounting.book_identity WHERE singleton")
    book = cursor.fetchone()
    return result | {
        "book_id": str(book["id"]) if book else None,
        "period": {key: str(value) for key, value in period.items()}
        if period
        else None,
        "cash_account_codes": cash_codes,
        "policy": policy,
        "reporting_policy_id": reporting["id"] if reporting else None,
        "journals": journals,
        "financing_account_options": options,
    }


class PostgresJournalDisclosureRepository(PostgresReportingEvidenceRepository):
    def load_disclosures(self, *, period_id, actor_user_id):
        try:
            with (
                open_connection() as connection,
                connection.cursor(row_factory=dict_row) as cursor,
            ):
                cursor.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
                )
                return read_journal_disclosures(cursor, period_id, actor_user_id)
        except psycopg.Error as error:
            raise ReportingEvidenceError(
                "Disclosure evidence is unavailable.",
                status=403 if error.sqlstate == "42501" else 503,
            ) from error

    def retain_disclosure_policy(
        self,
        *,
        request_id,
        book_id,
        reporting_policy_id,
        expected_version,
        payload,
        actor_user_id,
    ):
        return self._write(
            "SELECT accounting.retain_disclosure_policy(%s,%s,%s,%s,%s,%s) AS id",
            (
                request_id,
                book_id,
                reporting_policy_id,
                expected_version,
                Jsonb(payload),
                actor_user_id,
            ),
        )

    def retain_disclosure(
        self, *, request_id, book_id, disclosure_policy_id, payload, actor_user_id
    ):
        return self._write(
            "SELECT accounting.retain_journal_disclosure_review(%s,%s,%s,%s,%s) AS id",
            (request_id, book_id, disclosure_policy_id, Jsonb(payload), actor_user_id),
        )
