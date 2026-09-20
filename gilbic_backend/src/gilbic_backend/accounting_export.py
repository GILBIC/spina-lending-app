"""Exact-money review books from existing posted ledger values; no posting logic."""

import csv
import hashlib
import html
import io
import json
import unicodedata
import zipfile
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from . import __version__

MAX_ROWS = 100_000
MAX_BYTES = 64 * 1024 * 1024
ZERO = Decimal("0.00")
WARNING = (
    "Internal review copy. Not a registered book, tax invoice, SAF, filing, or compliance certification. "
    "Actual taxpayer and registration identity are not configured in this export. "
    "Amounts come only from the existing posted General Journal; drafts do not affect books."
)
AUDIT_SCOPE = (
    "All accounting.journal_events for existing entries (posted or draft) whose posting_date "
    "falls within the selected range; all accounting.cancelled_journal_draft_audit rows whose "
    "original posting_date falls within the range, including their retained prior events. "
    "Event timestamps do not define the fiscal scope. This is not a system-wide audit log."
)
JOURNAL_COLUMNS = (
    "posting_date",
    "entry_id",
    "entry_number",
    "period_id",
    "entry_description",
    "source_type",
    "source_reference",
    "source_event_key",
    "reversal_of_entry_id",
    "created_by_user_id",
    "posted_by_user_id",
    "created_at",
    "posted_at",
    "line_number",
    "account_code",
    "account_name",
    "line_description",
    "debit",
    "credit",
    "client_id",
    "loan_id",
)
TRIAL_COLUMNS = (
    "account_code",
    "account_name",
    "account_type",
    "normal_balance",
    "is_active",
    "opening_debit_balance",
    "opening_credit_balance",
    "movement_debit",
    "movement_credit",
    "closing_debit_balance",
    "closing_credit_balance",
)
ACCOUNT_COLUMNS = (
    "account_id",
    "account_code",
    "system_key",
    "account_name",
    "account_type",
    "normal_balance",
    "is_active",
    "is_posting",
)
AUDIT_COLUMNS = (
    "event_id",
    "entry_id",
    "entry_number",
    "posting_date",
    "status",
    "event_type",
    "actor_user_id",
    "created_at",
    "details",
)
LEDGER_COLUMNS = (
    "account_code",
    "account_name",
    "posting_date",
    "entry_id",
    "entry_number",
    "line_number",
    "line_description",
    "debit",
    "credit",
    "running_debit_balance",
    "running_credit_balance",
    "reversal_of_entry_id",
)


class AccountingExportError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def validate_range(start_date: date, end_date: date) -> None:
    if end_date < start_date or (end_date - start_date).days >= 366:
        raise AccountingExportError(
            "range", "Select an inclusive date range of 1 to 366 days."
        )


def _json_default(value: Any) -> str:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    raise TypeError("Unsupported export value")


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            default=_json_default,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _money(value: Any) -> Decimal:
    if (
        not isinstance(value, Decimal)
        or not value.is_finite()
        or value != value.quantize(Decimal("0.01"))
    ):
        raise AccountingExportError(
            "integrity", "Ledger amounts are not exact cent values."
        )
    return value


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json_bytes(value).decode("utf-8").rstrip("\n")
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def csv_cell(value: Any) -> str:
    if isinstance(value, Decimal):
        return format(_money(value), ".2f")
    text = _text(value)
    # A visible escape preserves controls without allowing hidden formula prefixes.
    text = "".join(
        f"\\u{ord(character):04x}"
        if unicodedata.category(character).startswith("C")
        else character
        for character in text
    )
    if text.lstrip().startswith(("=", "+", "-", "@")):
        text = "'" + text
    return text


class _Files:
    def __init__(self):
        self.content: dict[str, bytes] = {}
        self.rows: dict[str, int | None] = {}
        self.size = 0

    def add(self, name: str, chunks, *, rows: int | None = None) -> None:
        if rows is not None and rows > MAX_ROWS:
            raise AccountingExportError(
                "oversized", "Export exceeds the row limit; select a shorter range."
            )
        buffer = io.BytesIO()
        for chunk in chunks:
            self.size += len(chunk)
            if self.size > MAX_BYTES:
                raise AccountingExportError(
                    "oversized",
                    "Export exceeds the content limit; select a shorter range.",
                )
            buffer.write(chunk)
        self.content[name] = buffer.getvalue()
        self.rows[name] = rows

    def csv(
        self, name: str, columns: tuple[str, ...], rows: list[dict[str, Any]]
    ) -> None:
        def chunks():
            for row in [columns]:
                stream = io.StringIO(newline="")
                csv.writer(stream, lineterminator="\r\n").writerow(row)
                yield stream.getvalue().encode("utf-8")
            for item in rows:
                stream = io.StringIO(newline="")
                csv.writer(stream, lineterminator="\r\n").writerow(
                    csv_cell(item.get(key)) for key in columns
                )
                yield stream.getvalue().encode("utf-8")

        self.add(name, chunks(), rows=len(rows))


def _balances(snapshot: dict[str, Any]):
    accounts = snapshot["accounts"]
    journals = snapshot["journals"]
    movement: dict[str, list[Decimal]] = {}
    entries: dict[str, list[Decimal]] = {}
    for line in journals:
        debit, credit = _money(line["debit"]), _money(line["credit"])
        if not ((debit > ZERO and credit == ZERO) or (credit > ZERO and debit == ZERO)):
            raise AccountingExportError(
                "integrity", "A posted journal line has invalid debit or credit values."
            )
        for key, values in (
            (str(line["account_code"]), movement),
            (str(line["entry_id"]), entries),
        ):
            pair = values.setdefault(key, [ZERO, ZERO])
            pair[0] += debit
            pair[1] += credit
    if any(pair[0] != pair[1] for pair in entries.values()):
        raise AccountingExportError(
            "integrity", "Posted journal entries do not balance."
        )
    trials = []
    openings: dict[str, Decimal] = {}
    total_opening = total_closing = ZERO
    known = set()
    for account in accounts:
        code = str(account["account_code"])
        if code in known:
            raise AccountingExportError(
                "integrity", "Duplicate account identity in the export."
            )
        known.add(code)
        opening = _money(account["opening_debit"]) - _money(account["opening_credit"])
        debit, credit = (
            _money(account["movement_debit"]),
            _money(account["movement_credit"]),
        )
        if [debit, credit] != movement.get(code, [ZERO, ZERO]):
            raise AccountingExportError(
                "integrity", "Journal and Trial Balance movements do not reconcile."
            )
        closing = opening + debit - credit
        openings[code] = opening
        total_opening += opening
        total_closing += closing
        trials.append(
            {
                **account,
                "opening_debit_balance": max(opening, ZERO),
                "opening_credit_balance": max(-opening, ZERO),
                "closing_debit_balance": max(closing, ZERO),
                "closing_credit_balance": max(-closing, ZERO),
            }
        )
    if not movement.keys() <= known or total_opening != ZERO or total_closing != ZERO:
        raise AccountingExportError(
            "integrity", "Opening or closing ledger balances do not reconcile."
        )
    ledger = []
    running = dict(openings)
    for line in sorted(
        journals,
        key=lambda row: (
            row["account_code"],
            row["posting_date"],
            str(row["entry_id"]),
            row["line_number"],
        ),
    ):
        code = str(line["account_code"])
        running[code] += line["debit"] - line["credit"]
        ledger.append(
            {
                **line,
                "running_debit_balance": max(running[code], ZERO),
                "running_credit_balance": max(-running[code], ZERO),
            }
        )
    return trials, ledger


def _print_chunks(start_date, end_date, trials, journals):
    yield (
        "<!doctype html><html lang=en><meta charset=utf-8>"
        "<meta http-equiv=Content-Security-Policy content=\"default-src 'none'; style-src 'unsafe-inline'\">"
        "<title>Spina accounting review</title><style>body{font:12px sans-serif}"
        "table{border-collapse:collapse;width:100%}td,th{border:1px solid #999;padding:4px;overflow-wrap:anywhere}"
        "thead{display:table-header-group}@page{size:A4 landscape;margin:12mm}"
        "@media print{h2{break-before:page}}</style><body>"
        f"<h1>Accounting review: {start_date} to {end_date}</h1><p>{html.escape(WARNING)}</p>"
        f"<p>{html.escape(AUDIT_SCOPE)}</p>"
    ).encode()
    for title, columns, rows in (
        ("Trial Balance", TRIAL_COLUMNS, trials),
        (
            "Posted General Journal",
            (
                "posting_date",
                "entry_number",
                "account_code",
                "account_name",
                "line_description",
                "debit",
                "credit",
                "reversal_of_entry_id",
            ),
            journals,
        ),
    ):
        yield (
            "<h2>"
            + title
            + "</h2><table><thead><tr>"
            + "".join("<th>" + html.escape(column) + "</th>" for column in columns)
            + "</tr></thead><tbody>"
        ).encode("utf-8")
        for row in rows:
            yield (
                "<tr>"
                + "".join(
                    "<td>" + html.escape(_text(row.get(column))) + "</td>"
                    for column in columns
                )
                + "</tr>"
            ).encode("utf-8")
        yield b"</tbody></table>"
    yield b"</body></html>"


def build_accounting_export(
    snapshot: dict[str, Any],
    *,
    start_date: date,
    end_date: date,
    generated_by_user_id: UUID,
) -> bytes:
    validate_range(start_date, end_date)
    for name in ("accounts", "journals", "periods", "audit", "cancelled"):
        if len(snapshot[name]) > MAX_ROWS:
            raise AccountingExportError(
                "oversized", "Export exceeds the row limit; select a shorter range."
            )
    trials, ledger = _balances(snapshot)
    files = _Files()
    files.csv("general-journal.csv", JOURNAL_COLUMNS, snapshot["journals"])
    files.csv("general-ledger.csv", LEDGER_COLUMNS, ledger)
    files.csv("trial-balance.csv", TRIAL_COLUMNS, trials)
    files.csv("chart-of-accounts.csv", ACCOUNT_COLUMNS, snapshot["accounts"])
    files.csv("accounting-audit.csv", AUDIT_COLUMNS, snapshot["audit"])
    files.add(
        "cancelled-drafts.json",
        [json_bytes(snapshot["cancelled"])],
        rows=len(snapshot["cancelled"]),
    )
    files.add(
        "print-view.html",
        _print_chunks(start_date, end_date, trials, snapshot["journals"]),
    )
    readme = f"# Spina accounting review\n\n{WARNING}\n\n{AUDIT_SCOPE}\n\nInclusive posting dates: {start_date} to {end_date}. Time zone: Asia/Manila.\nOpening balances aggregate all posted entries before the start date. Movement includes posted entries in range, including reversals and formal closing entries. Closing = opening + debits - credits. Accounts include inactive/retired accounts and zero activity. The Trial Balance contains opening and closing balances; General Ledger rows start from those openings.\n\nCSV is UTF-8 with CRLF records. Text beginning with formula characters (after spaces) is prefixed with an apostrophe; control characters are visible Unicode escapes. Exact monetary columns are unprefixed decimal cents. JSON audit snapshots preserve source values; fractional JSON numbers are decimal strings to avoid binary float loss, and integers remain integers.\n\nFiles are one repeatable-read, read-only accounting snapshot. Routine authentication can update device last-seen separately. Neither this download nor its printable copy issues an invoice, posts money, approves taxpayer facts or proves registration. Hashes identify bytes, not independent government authentication.\n"
    files.add("README.md", [readme.encode("utf-8")])
    manifest = {
        "schema_version": 1,
        "kind": "spina_accounting_export",
        "status": "internal_review_only",
        "backend_version": __version__,
        "start_date": start_date,
        "end_date": end_date,
        "timezone": "Asia/Manila",
        "generated_at": snapshot["generated_at"],
        "generated_by_user_id": generated_by_user_id,
        "snapshot": "PostgreSQL REPEATABLE READ READ ONLY",
        "posted_only_books": True,
        "audit_scope": AUDIT_SCOPE,
        "audit_decimal_encoding": "JSON fractional numbers are exact decimal strings; integer numbers remain integers.",
        "fiscal_periods": snapshot["periods"],
        "missing_taxpayer_registration_facts": [
            "registered_name",
            "registered_address",
            "tin",
            "branch_code",
            "rdo",
            "taxpayer_classification",
            "book_registration",
            "invoice_applicability",
            "saf_applicability",
        ],
        "registered": False,
        "saf_compliant": False,
        "tax_invoice": False,
        "review_only": True,
        "official_books_registered": False,
        "saf_compliance_verified": False,
        "taxpayer_identity_verified": False,
        "totals": {
            key: format(sum((row[column] for row in trials), ZERO), ".2f")
            for key, column in (
                ("opening_debit", "opening_debit_balance"),
                ("opening_credit", "opening_credit_balance"),
                ("movement_debit", "movement_debit"),
                ("movement_credit", "movement_credit"),
                ("closing_debit", "closing_debit_balance"),
                ("closing_credit", "closing_credit_balance"),
            )
        },
        "files": {
            name: {
                "sha256": hashlib.sha256(value).hexdigest(),
                "bytes": len(value),
                "rows": files.rows[name],
            }
            for name, value in files.content.items()
        },
        "reconciliation": {
            "per_entry_balanced": True,
            "journal_trial_movement_equal": True,
            "opening_balanced": True,
            "closing_balanced": True,
        },
        "warning": WARNING,
    }
    files.add("manifest.json", [json_bytes(manifest)])
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.content.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100600 << 16
            archive.writestr(info, content)
    return output.getvalue()
