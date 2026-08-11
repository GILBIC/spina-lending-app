from __future__ import annotations

import argparse
import os
from collections import Counter
from pathlib import Path

import psycopg


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
MIGRATION = SQL_ROOT / "0053_add_greenfield_regular_ledger_reconciliation_targets.sql"


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
            "Stage 5D.27 live migration safety gate failed: expected BEGIN/COMMIT wrapper"
        )
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _exists(connection: psycopg.Connection, relation: str) -> bool:
    return connection.execute(
        "select to_regclass(%s)", (relation,)
    ).fetchone()[0] is not None


def _count(connection: psycopg.Connection, relation: str) -> int:
    return int(connection.execute(f"select count(*) from {relation}").fetchone()[0])


def _loan_status_counts(connection: psycopg.Connection) -> Counter[str]:
    rows = connection.execute(
        "select status, count(*)::bigint from lending.loans group by status"
    ).fetchall()
    return Counter({str(status): int(count) for status, count in rows})


def _verify_installed(connection: psycopg.Connection) -> dict[str, int]:
    view_name = "accounting.greenfield_regular_renewal_ledger_reconciliation_targets"
    if not _exists(connection, view_name):
        raise SystemExit(
            "Stage 5D.27 live verification failed: greenfield Regular ledger reconciliation target view is missing"
        )

    invalid_flags = int(
        connection.execute(
            """
            select count(*)
            from accounting.greenfield_regular_renewal_ledger_reconciliation_targets
            where accounting_carrying_amount_ready = true
               or journal_lines_enabled = true
               or automatic_source_posting = true
            """
        ).fetchone()[0]
    )
    if invalid_flags:
        raise SystemExit(
            "Stage 5D.27 live verification failed: coarse target view unexpectedly enabled carrying amount, journal lines, or automatic posting"
        )

    upstream_rows = _count(
        connection,
        "accounting.greenfield_regular_renewal_rollforward_targets",
    )
    rows = _count(connection, view_name)
    if rows != upstream_rows:
        raise SystemExit(
            "Stage 5D.27 live verification failed: reconciliation target count does not match Stage 5D.26 target count"
        )

    candidates = int(
        connection.execute(
            """
            select count(*)
            from accounting.greenfield_regular_renewal_ledger_reconciliation_targets
            where reconciliation_readiness_status =
                  'greenfield_regular_ledger_reconciliation_candidate'
              and exact_reconciliation_preview_enabled = true
            """
        ).fetchone()[0]
    )
    invalid_candidate_flags = int(
        connection.execute(
            """
            select count(*)
            from accounting.greenfield_regular_renewal_ledger_reconciliation_targets
            where exact_reconciliation_preview_enabled = true
              and reconciliation_readiness_status <>
                  'greenfield_regular_ledger_reconciliation_candidate'
            """
        ).fetchone()[0]
    )
    if invalid_candidate_flags:
        raise SystemExit(
            "Stage 5D.27 live verification failed: exact reconciliation preview flag disagrees with coarse readiness"
        )

    posting_gaps = int(
        connection.execute(
            """
            select count(*)
            from accounting.greenfield_regular_renewal_ledger_reconciliation_targets
            where reconciliation_readiness_status = 'protected_regular_source_posting_gap'
            """
        ).fetchone()[0]
    )
    unprotected = int(
        connection.execute(
            """
            select count(*)
            from accounting.greenfield_regular_renewal_ledger_reconciliation_targets
            where reconciliation_readiness_status = 'unprotected_regular_journal_history_review'
            """
        ).fetchone()[0]
    )
    return {
        "rows": rows,
        "candidates": candidates,
        "blocked": rows - candidates,
        "posting_gaps": posting_gaps,
        "unprotected": unprotected,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install and verify Stage 5D.27 read-only greenfield Regular protected "
            "ledger reconciliation targets without creating source events or journals."
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
        raise SystemExit("Stage 5D.27 migration file was not found: " + str(MIGRATION))
    body = _transaction_body(MIGRATION.read_text(encoding="utf-8"))

    try:
        with psycopg.connect(database_url) as connection:
            prerequisites = (
                "lending.loans",
                "lending.collection_transactions",
                "lending.loan_renewal_execution_events",
                "accounting.greenfield_regular_renewal_rollforward_targets",
                "accounting.regular_journal_draft_preparations",
                "accounting.regular_journal_draft_preparation_entries",
                "accounting.regular_journal_posting_sets",
                "accounting.regular_journal_posting_entries",
                "accounting.regular_journal_reversal_sets",
                "accounting.regular_journal_reversal_entries",
                "accounting.journal_entries",
                "accounting.journal_lines",
                "core.audit_logs",
            )
            missing = [
                relation for relation in prerequisites if not _exists(connection, relation)
            ]
            if missing:
                raise SystemExit(
                    "Stage 5D.27 live migration prerequisite is not installed: "
                    + ", ".join(missing)
                )

            before = (
                _count(connection, "lending.loans"),
                _loan_status_counts(connection),
                _count(connection, "lending.collection_transactions"),
                _count(connection, "lending.loan_renewal_execution_events"),
                _count(connection, "accounting.journal_entries"),
                _count(connection, "accounting.journal_lines"),
                _count(connection, "accounting.regular_journal_draft_preparations"),
                _count(connection, "accounting.regular_journal_posting_sets"),
                _count(connection, "accounting.regular_journal_reversal_sets"),
                _count(connection, "core.audit_logs"),
            )

            connection.execute(body)
            summary = _verify_installed(connection)

            after = (
                _count(connection, "lending.loans"),
                _loan_status_counts(connection),
                _count(connection, "lending.collection_transactions"),
                _count(connection, "lending.loan_renewal_execution_events"),
                _count(connection, "accounting.journal_entries"),
                _count(connection, "accounting.journal_lines"),
                _count(connection, "accounting.regular_journal_draft_preparations"),
                _count(connection, "accounting.regular_journal_posting_sets"),
                _count(connection, "accounting.regular_journal_reversal_sets"),
                _count(connection, "core.audit_logs"),
            )
            if after != before:
                raise SystemExit(
                    "Stage 5D.27 live migration safety gate failed: installing the read-only reconciliation target layer changed live operational/accounting history"
                )

            print(
                "Stage 5D.27 greenfield Regular ledger reconciliation summary: "
                f"rows={summary['rows']}, candidates={summary['candidates']}, "
                f"blocked={summary['blocked']}, posting_gaps={summary['posting_gaps']}, "
                f"unprotected_history={summary['unprotected']}, "
                "accounting_carrying_amount_ready=False at coarse SQL gate, "
                "journal_lines_enabled=False, automatic_source_posting=False."
            )
            return 0
    except psycopg.Error as error:
        raise SystemExit(
            "Stage 5D.27 greenfield Regular ledger reconciliation migration failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error


if __name__ == "__main__":
    raise SystemExit(main())
