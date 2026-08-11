from __future__ import annotations

import argparse
import os
from collections import Counter
from pathlib import Path

import psycopg


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
MIGRATION = SQL_ROOT / "0052_add_greenfield_regular_renewal_rollforward_targets.sql"


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
            "Stage 5D.26 live migration safety gate failed: expected BEGIN/COMMIT wrapper"
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
    view_name = "accounting.greenfield_regular_renewal_rollforward_targets"
    if not _exists(connection, view_name):
        raise SystemExit(
            "Stage 5D.26 live verification failed: greenfield Regular renewal roll-forward target view is missing"
        )

    invalid_flags = int(
        connection.execute(
            """
            select count(*)
            from accounting.greenfield_regular_renewal_rollforward_targets
            where accounting_carrying_amount_ready = true
               or journal_lines_enabled = true
               or automatic_source_posting = true
            """
        ).fetchone()[0]
    )
    if invalid_flags:
        raise SystemExit(
            "Stage 5D.26 live verification failed: target view unexpectedly enabled accounting carrying, journal lines, or automatic posting"
        )

    active_execution_count = int(
        connection.execute(
            """
            select count(*)
            from lending.loan_renewal_execution_events execution
            join lending.loan_disbursement_events release
              on release.id = execution.disbursement_event_id
            where execution.is_voided = false
              and release.is_voided = false
              and release.event_kind = 'renewal_release'
            """
        ).fetchone()[0]
    )
    rows = _count(connection, view_name)
    if rows != active_execution_count:
        raise SystemExit(
            "Stage 5D.26 live verification failed: roll-forward target count does not match active authoritative renewal executions"
        )

    ready = int(
        connection.execute(
            """
            select count(*)
            from accounting.greenfield_regular_renewal_rollforward_targets
            where readiness_status = 'greenfield_regular_renewal_rollforward_target_ready'
            """
        ).fetchone()[0]
    )
    same_day_review = int(
        connection.execute(
            """
            select count(*)
            from accounting.greenfield_regular_renewal_rollforward_targets
            where readiness_status = 'same_day_renewal_collection_ordering_review'
            """
        ).fetchone()[0]
    )
    preview_enabled = int(
        connection.execute(
            """
            select count(*)
            from accounting.greenfield_regular_renewal_rollforward_targets
            where measurement_preview_enabled = true
            """
        ).fetchone()[0]
    )
    if preview_enabled != ready:
        raise SystemExit(
            "Stage 5D.26 live verification failed: measurement preview enablement does not match target readiness"
        )
    return {
        "active_renewal_executions": active_execution_count,
        "rows": rows,
        "ready": ready,
        "blocked": rows - ready,
        "same_day_review": same_day_review,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install and verify Stage 5D.26 read-only greenfield Regular renewal "
            "roll-forward targets without creating source events or journals."
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
        raise SystemExit("Stage 5D.26 migration file was not found: " + str(MIGRATION))
    body = _transaction_body(MIGRATION.read_text(encoding="utf-8"))

    try:
        with psycopg.connect(database_url) as connection:
            prerequisites = (
                "lending.loans",
                "lending.collection_transactions",
                "lending.loan_disbursement_events",
                "lending.loan_renewal_execution_events",
                "accounting.loan_renewal_execution_source_readiness",
                "accounting.greenfield_regular_eir_anchor_readiness",
                "accounting.journal_entries",
                "accounting.journal_lines",
                "accounting.opening_balance_workbooks",
                "core.audit_logs",
            )
            missing = [relation for relation in prerequisites if not _exists(connection, relation)]
            if missing:
                raise SystemExit(
                    "Stage 5D.26 live migration prerequisite is not installed: "
                    + ", ".join(missing)
                )

            before = (
                _count(connection, "lending.loans"),
                _loan_status_counts(connection),
                _count(connection, "lending.collection_transactions"),
                _count(connection, "lending.loan_disbursement_events"),
                _count(connection, "lending.loan_renewal_execution_events"),
                _count(connection, "accounting.journal_entries"),
                _count(connection, "accounting.journal_lines"),
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
                _count(connection, "lending.loan_renewal_execution_events"),
                _count(connection, "accounting.journal_entries"),
                _count(connection, "accounting.journal_lines"),
                _count(connection, "accounting.opening_balance_workbooks"),
                _count(connection, "core.audit_logs"),
            )
            if after != before:
                raise SystemExit(
                    "Stage 5D.26 live migration safety gate failed: installing the read-only roll-forward target layer changed live operational/accounting history"
                )

            print(
                "Stage 5D.26 greenfield Regular renewal roll-forward summary: "
                f"active_renewal_executions={summary['active_renewal_executions']}, "
                f"rows={summary['rows']}, target_ready={summary['ready']}, "
                f"blocked={summary['blocked']}, same_day_review={summary['same_day_review']}, "
                "accounting_carrying_amount_ready=False, journal_lines_enabled=False, "
                "automatic_source_posting=False."
            )
            return 0
    except psycopg.Error as error:
        raise SystemExit(
            "Stage 5D.26 greenfield Regular renewal roll-forward migration failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error


if __name__ == "__main__":
    raise SystemExit(main())
