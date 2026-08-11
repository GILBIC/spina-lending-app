from __future__ import annotations

import argparse
import os
from collections import Counter
from pathlib import Path

import psycopg


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
MIGRATION = SQL_ROOT / "0051_add_greenfield_regular_eir_anchor_readiness.sql"


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
            "Stage 5D.25 live migration safety gate failed: expected BEGIN/COMMIT wrapper"
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


def _function_count(connection: psycopg.Connection, schema: str, name: str) -> int:
    return int(
        connection.execute(
            """
            select count(*)
            from pg_proc proc
            join pg_namespace ns on ns.oid = proc.pronamespace
            where ns.nspname = %s and proc.proname = %s
            """,
            (schema, name),
        ).fetchone()[0]
    )


def _verify_installed(connection: psycopg.Connection) -> dict[str, int]:
    if not _exists(connection, "accounting.greenfield_regular_eir_anchor_readiness"):
        raise SystemExit(
            "Stage 5D.25 live verification failed: greenfield Regular EIR anchor readiness view is missing"
        )
    if _function_count(
        connection,
        "accounting",
        "solve_verified_contract_schedule_daily_eir",
    ) != 1:
        raise SystemExit(
            "Stage 5D.25 live verification failed: verified-contract daily EIR solver is missing or ambiguous"
        )

    invalid_flags = int(
        connection.execute(
            """
            select count(*)
            from accounting.greenfield_regular_eir_anchor_readiness
            where collection_journal_integration_enabled = true
               or journal_lines_enabled = true
               or automatic_source_posting = true
            """
        ).fetchone()[0]
    )
    if invalid_flags:
        raise SystemExit(
            "Stage 5D.25 live verification failed: readiness unexpectedly enabled collection integration, journal lines, or automatic posting"
        )

    posting_count = _count(connection, "accounting.loan_disbursement_journal_postings")
    rows = _count(connection, "accounting.greenfield_regular_eir_anchor_readiness")
    if rows != posting_count:
        raise SystemExit(
            "Stage 5D.25 live verification failed: readiness row count does not equal protected new-loan posting count"
        )
    ready = int(
        connection.execute(
            """
            select count(*)
            from accounting.greenfield_regular_eir_anchor_readiness
            where readiness_status = 'greenfield_regular_eir_anchor_ready'
            """
        ).fetchone()[0]
    )
    same_day_review = int(
        connection.execute(
            """
            select count(*)
            from accounting.greenfield_regular_eir_anchor_readiness
            where readiness_status = 'same_day_collection_ordering_review'
            """
        ).fetchone()[0]
    )
    return {
        "protected_postings": posting_count,
        "rows": rows,
        "ready": ready,
        "blocked": rows - ready,
        "same_day_review": same_day_review,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install and verify Stage 5D.25 read-only greenfield Regular EIR anchor "
            "readiness without creating opening balances, source events, or journals."
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
        raise SystemExit("Stage 5D.25 migration file was not found: " + str(MIGRATION))
    body = _transaction_body(MIGRATION.read_text(encoding="utf-8"))

    try:
        with psycopg.connect(database_url) as connection:
            prerequisites = (
                "lending.loans",
                "lending.collection_transactions",
                "lending.loan_disbursement_events",
                "lending.loan_disbursement_cancellations",
                "lending.loan_contract_schedules",
                "lending.loan_contract_installments",
                "lending.loan_contract_schedule_registrations",
                "accounting.loan_disbursement_journal_postings",
                "accounting.loan_disbursement_journal_reversals",
                "accounting.journal_entries",
                "accounting.journal_lines",
                "accounting.opening_balance_workbooks",
                "core.audit_logs",
            )
            missing = [relation for relation in prerequisites if not _exists(connection, relation)]
            if missing:
                raise SystemExit(
                    "Stage 5D.25 live migration prerequisite is not installed: "
                    + ", ".join(missing)
                )

            before = (
                _count(connection, "lending.loans"),
                _loan_status_counts(connection),
                _count(connection, "lending.collection_transactions"),
                _count(connection, "lending.loan_disbursement_events"),
                _count(connection, "lending.loan_disbursement_cancellations"),
                _count(connection, "lending.loan_contract_schedules"),
                _count(connection, "lending.loan_contract_installments"),
                _count(connection, "lending.loan_contract_schedule_registrations"),
                _count(connection, "accounting.journal_entries"),
                _count(connection, "accounting.journal_lines"),
                _count(connection, "accounting.loan_disbursement_journal_postings"),
                _count(connection, "accounting.loan_disbursement_journal_reversals"),
                _count(connection, "accounting.opening_balance_workbooks"),
                _count(connection, "core.audit_logs"),
            )

            connection.execute(body)
            summary = _verify_installed(connection)

            after = (
                _count(connection, "lending.loans"),
                _loan_status_counts(connection),
                _count(connection, "lending.collection_transactions"),
                _count(connection, "lending.loan_disbursement_events"),
                _count(connection, "lending.loan_disbursement_cancellations"),
                _count(connection, "lending.loan_contract_schedules"),
                _count(connection, "lending.loan_contract_installments"),
                _count(connection, "lending.loan_contract_schedule_registrations"),
                _count(connection, "accounting.journal_entries"),
                _count(connection, "accounting.journal_lines"),
                _count(connection, "accounting.loan_disbursement_journal_postings"),
                _count(connection, "accounting.loan_disbursement_journal_reversals"),
                _count(connection, "accounting.opening_balance_workbooks"),
                _count(connection, "core.audit_logs"),
            )
            if after != before:
                raise SystemExit(
                    "Stage 5D.25 live migration safety gate failed: installing read-only anchor readiness changed live operational/accounting history"
                )

            print(
                "Stage 5D.25 greenfield Regular EIR anchor summary: "
                f"protected_postings={summary['protected_postings']}, rows={summary['rows']}, "
                f"anchor_ready={summary['ready']}, blocked={summary['blocked']}, "
                f"same_day_review={summary['same_day_review']}, "
                "collection_journal_integration_enabled=False, journal_lines_enabled=False, "
                "automatic_source_posting=False."
            )
            return 0
    except psycopg.Error as error:
        raise SystemExit(
            "Stage 5D.25 greenfield Regular EIR anchor migration failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error


if __name__ == "__main__":
    raise SystemExit(main())
