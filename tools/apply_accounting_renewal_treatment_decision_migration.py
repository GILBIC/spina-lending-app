from __future__ import annotations

import argparse
import os
from collections import Counter
from pathlib import Path

import psycopg


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
MIGRATION = SQL_ROOT / "0056_add_renewal_treatment_decision_evidence.sql"


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
            "Renewal treatment decision live migration safety gate failed: migration 0056 must have an exact BEGIN/COMMIT wrapper."
        )
    return body[len("BEGIN;") :].lstrip()[: -len("COMMIT;")].rstrip()


def _exists(connection: psycopg.Connection, relation: str) -> bool:
    return connection.execute("select to_regclass(%s)", (relation,)).fetchone()[0] is not None


def _count(connection: psycopg.Connection, relation: str) -> int:
    return int(connection.execute(f"select count(*) from {relation}").fetchone()[0])


def _count_if_exists(connection: psycopg.Connection, relation: str) -> int:
    return _count(connection, relation) if _exists(connection, relation) else 0


def _loan_status_counts(connection: psycopg.Connection) -> Counter[str]:
    rows = connection.execute(
        "select status, count(*)::bigint from lending.loans group by status"
    ).fetchall()
    return Counter({str(status): int(count) for status, count in rows})


def _history_snapshot(connection: psycopg.Connection) -> tuple[object, ...]:
    return (
        _count(connection, "lending.loans"),
        _loan_status_counts(connection),
        _count(connection, "lending.collection_transactions"),
        _count(connection, "lending.loan_disbursement_events"),
        _count(connection, "lending.loan_renewal_execution_events"),
        _count(connection, "accounting.journal_entries"),
        _count(connection, "accounting.journal_lines"),
        _count(connection, "accounting.journal_events"),
        _count(connection, "accounting.regular_journal_draft_preparations"),
        _count(connection, "accounting.regular_journal_posting_sets"),
        _count(connection, "accounting.regular_journal_reversal_sets"),
        _count(connection, "accounting.renewal_boundary_eir_journal_preparations"),
        _count(connection, "accounting.renewal_boundary_eir_journal_posting_sets"),
        _count_if_exists(connection, "accounting.renewal_treatment_decisions"),
        _count_if_exists(connection, "accounting.renewal_treatment_decision_voids"),
    )


def _verify_installed(connection: psycopg.Connection) -> dict[str, int]:
    relations = (
        "accounting.renewal_treatment_decisions",
        "accounting.renewal_treatment_decision_voids",
        "accounting.renewal_treatment_decision_status",
    )
    missing_relations = [name for name in relations if not _exists(connection, name)]
    if missing_relations:
        raise SystemExit(
            "Renewal treatment decision live verification failed: missing protected relations: "
            + ", ".join(missing_relations)
        )

    required_functions = (
        "accounting.record_renewal_treatment_decision(uuid,uuid,uuid,uuid,date,text,text,text,text,text,jsonb,text,text,numeric,numeric,numeric,numeric,numeric,uuid,integer,text,text,integer,numeric,numeric,numeric,numeric,uuid)",
        "accounting.void_renewal_treatment_decision(uuid,uuid,text)",
    )
    missing_functions = [
        name
        for name in required_functions
        if connection.execute("select to_regprocedure(%s)", (name,)).fetchone()[0]
        is None
    ]
    if missing_functions:
        raise SystemExit(
            "Renewal treatment decision live verification failed: missing protected functions: "
            + ", ".join(missing_functions)
        )

    trigger_names = {
        "accounting_renewal_treatment_decision_guard",
        "accounting_renewal_treatment_decision_void_guard",
        "lending_renewal_execution_treatment_decision_history_guard",
    }
    installed_triggers = {
        str(row[0])
        for row in connection.execute(
            "select tgname from pg_trigger where not tgisinternal and tgname = any(%s)",
            (list(trigger_names),),
        ).fetchall()
    }
    if installed_triggers != trigger_names:
        raise SystemExit(
            "Renewal treatment decision live verification failed: protected trigger set is incomplete: "
            + ", ".join(sorted(trigger_names - installed_triggers))
        )

    permission = connection.execute(
        """
        select count(*)::integer
        from core.roles role
        join core.role_permissions role_permission on role_permission.role_id = role.id
        where role.code = 'management'
          and role_permission.permission_code = 'accounting.renewal_treatment_decision.manage'
        """
    ).fetchone()[0]
    if int(permission) != 1:
        raise SystemExit(
            "Renewal treatment decision live verification failed: Management decision permission is incomplete."
        )

    invalid_flags = int(
        connection.execute(
            """
            select count(*)
            from accounting.renewal_treatment_decision_status
            where automatic_classification_enabled = true
               or quantitative_threshold_decisive = true
               or journal_lines_enabled = true
               or automatic_source_posting = true
            """
        ).fetchone()[0]
    )
    if invalid_flags:
        raise SystemExit(
            "Renewal treatment decision live verification failed: a protected decision row unexpectedly enabled automatic classification, journal lines or source posting."
        )

    return {
        "decisions": _count(connection, "accounting.renewal_treatment_decisions"),
        "voids": _count(connection, "accounting.renewal_treatment_decision_voids"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install and verify immutable Management-reviewed renewal accounting treatment "
            "decision evidence without creating any live decision, void, journal, source "
            "event or accounting history."
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
        raise SystemExit("Renewal treatment decision migration 0056 was not found.")
    body = _transaction_body(MIGRATION.read_text(encoding="utf-8"))

    try:
        with psycopg.connect(database_url) as connection:
            prerequisites = (
                "core.users",
                "core.roles",
                "core.permissions",
                "core.role_permissions",
                "core.audit_logs",
                "lending.loans",
                "lending.collection_transactions",
                "lending.loan_disbursement_events",
                "lending.loan_renewal_execution_events",
                "lending.loan_contract_schedules",
                "lending.loan_contract_schedule_registrations",
                "lending.loan_contract_installments",
                "accounting.journal_entries",
                "accounting.journal_lines",
                "accounting.journal_events",
                "accounting.regular_journal_draft_preparations",
                "accounting.regular_journal_posting_sets",
                "accounting.regular_journal_reversal_sets",
                "accounting.renewal_boundary_eir_journal_preparations",
                "accounting.renewal_boundary_eir_journal_posting_sets",
            )
            missing = [name for name in prerequisites if not _exists(connection, name)]
            if missing:
                raise SystemExit(
                    "Renewal treatment decision live migration prerequisite is not installed: "
                    + ", ".join(missing)
                )

            before = _history_snapshot(connection)
            connection.execute(body)
            summary = _verify_installed(connection)
            after = _history_snapshot(connection)
            if after != before:
                raise SystemExit(
                    "Renewal treatment decision live migration safety gate failed: installing decision evidence controls changed live operational/accounting history."
                )

            print(
                "Renewal treatment decision evidence live summary: "
                f"decisions={summary['decisions']}, voids={summary['voids']}, "
                "history_unchanged=True, immutable_decision_evidence=True, "
                "explicit_management_review=True, automatic_classification=False, "
                "quantitative_threshold_decisive=False, journal_lines_enabled=False, "
                "automatic_source_posting=False."
            )
            return 0
    except psycopg.Error as error:
        raise SystemExit(
            "Renewal treatment decision protected migration failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error


if __name__ == "__main__":
    raise SystemExit(main())
