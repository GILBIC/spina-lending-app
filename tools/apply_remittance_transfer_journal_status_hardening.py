from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
MIGRATION = SQL_ROOT / "0059_harden_remittance_transfer_journal_status.sql"


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _transaction_body(source: str) -> str:
    body = source.strip()
    if not body.startswith("BEGIN;") or not body.endswith("COMMIT;"):
        raise SystemExit(
            "Remittance journal status hardening safety gate failed: expected BEGIN/COMMIT wrapper"
        )
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _exists(connection: psycopg.Connection, relation: str) -> bool:
    return connection.execute(
        "select to_regclass(%s)", (relation,)
    ).fetchone()[0] is not None


def _count(connection: psycopg.Connection, relation: str) -> int:
    return int(connection.execute(f"select count(*) from {relation}").fetchone()[0])


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install the fail-closed remittance-transfer journal status view hardening "
            "without creating or changing operational/accounting history."
        )
    )
    parser.add_argument("--env-file", action="append", type=Path, default=[])
    parser.add_argument("--database-url-env", default="GILBIC_DATABASE_URL")
    args = parser.parse_args()

    for env_path in args.env_file:
        _load_env_file(env_path)

    database_url = os.getenv(args.database_url_env)
    if not database_url:
        raise SystemExit(f"{args.database_url_env} is not configured")
    if not MIGRATION.is_file():
        raise SystemExit(
            "Remittance journal status hardening migration file was not found: "
            + str(MIGRATION)
        )
    body = _transaction_body(MIGRATION.read_text(encoding="utf-8"))

    try:
        with psycopg.connect(database_url) as connection:
            prerequisites = (
                "lending.collection_remittances",
                "accounting.accounts",
                "accounting.fiscal_periods",
                "accounting.journal_entries",
                "accounting.journal_lines",
                "accounting.remittance_transfer_evidence",
                "accounting.remittance_transfer_readiness",
                "accounting.remittance_transfer_journal_preparations",
                "accounting.remittance_transfer_journal_postings",
                "accounting.remittance_transfer_journal_reversals",
                "accounting.remittance_transfer_journal_status",
            )
            missing = [item for item in prerequisites if not _exists(connection, item)]
            if missing:
                raise SystemExit(
                    "Remittance journal status hardening prerequisite is not installed: "
                    + ", ".join(missing)
                )

            before = (
                _count(connection, "lending.collection_remittances"),
                _count(connection, "accounting.remittance_transfer_evidence"),
                _count(connection, "accounting.remittance_transfer_journal_preparations"),
                _count(connection, "accounting.remittance_transfer_journal_postings"),
                _count(connection, "accounting.remittance_transfer_journal_reversals"),
                _count(connection, "accounting.journal_entries"),
                _count(connection, "accounting.journal_lines"),
                _count(connection, "core.audit_logs"),
            )

            connection.execute(body)

            after = (
                _count(connection, "lending.collection_remittances"),
                _count(connection, "accounting.remittance_transfer_evidence"),
                _count(connection, "accounting.remittance_transfer_journal_preparations"),
                _count(connection, "accounting.remittance_transfer_journal_postings"),
                _count(connection, "accounting.remittance_transfer_journal_reversals"),
                _count(connection, "accounting.journal_entries"),
                _count(connection, "accounting.journal_lines"),
                _count(connection, "core.audit_logs"),
            )
            if after != before:
                raise SystemExit(
                    "Remittance journal status hardening safety gate failed: installing the view changed live history"
                )

            invalid_flags = int(
                connection.execute(
                    """
                    select count(*)
                    from accounting.remittance_transfer_journal_status
                    where income_recognition = true
                       or explicit_management_posting = false
                       or automatic_source_posting = true
                    """
                ).fetchone()[0]
            )
            if invalid_flags:
                raise SystemExit(
                    "Remittance journal status hardening failed: lifecycle safety flags are inconsistent"
                )

            stale_ready = int(
                connection.execute(
                    """
                    select count(*)
                    from accounting.remittance_transfer_journal_status status
                    join accounting.remittance_transfer_readiness readiness
                      on readiness.remittance_id = status.remittance_id
                    join accounting.fiscal_periods period
                      on period.id = status.fiscal_period_id
                    join accounting.accounts debit_account
                      on debit_account.id = status.debit_account_id
                    join accounting.accounts credit_account
                      on credit_account.id = status.credit_account_id
                    where status.posting_ready = true
                      and (
                          readiness.readiness_status <> 'transfer_coordinate_ready'
                          or readiness.transfer_evidence_id <> status.transfer_evidence_id
                          or readiness.source_event_key <> status.source_event_key
                          or readiness.business_date <> status.posting_date
                          or readiness.debit_account_system_key <> status.debit_account_system_key
                          or readiness.credit_account_system_key <> status.credit_account_system_key
                          or readiness.debit_amount <> status.amount
                          or readiness.credit_amount <> status.amount
                          or period.status <> 'open'
                          or status.posting_date not between period.start_date and period.end_date
                          or debit_account.is_active = false
                          or debit_account.is_posting = false
                          or credit_account.is_active = false
                          or credit_account.is_posting = false
                      )
                    """
                ).fetchone()[0]
            )
            if stale_ready:
                raise SystemExit(
                    "Remittance journal status hardening failed: posting_ready did not fail closed for current source/account/period controls"
                )

            print(
                "Remittance journal status hardening live summary: "
                f"status_rows={_count(connection, 'accounting.remittance_transfer_journal_status')}, "
                "history_unchanged=True, posting_ready_fail_closed=True, "
                "income_recognition=False, explicit_management_posting=True, "
                "automatic_source_posting=False."
            )
            return 0
    except psycopg.Error as error:
        raise SystemExit(
            "Remittance journal status hardening migration failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error


if __name__ == "__main__":
    raise SystemExit(main())
