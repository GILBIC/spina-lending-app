from __future__ import annotations

import argparse
import os
from collections import Counter
from pathlib import Path

import psycopg


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
MIGRATIONS = (
    SQL_ROOT / "0053_add_greenfield_regular_ledger_reconciliation_targets.sql",
    SQL_ROOT / "0054_add_protected_renewal_boundary_eir_journal_posting.sql",
    SQL_ROOT / "0055_harden_renewal_boundary_eir_posting_audit_alias.sql",
)


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


def _transaction_body(source: str, *, label: str) -> str:
    body = source.strip()
    if not body.startswith("BEGIN;") or not body.endswith("COMMIT;"):
        raise SystemExit(
            f"Renewal-boundary EIR live migration safety gate failed: {label} must have an exact BEGIN/COMMIT wrapper"
        )
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _exists(connection: psycopg.Connection, relation: str) -> bool:
    return connection.execute(
        "select to_regclass(%s)", (relation,)
    ).fetchone()[0] is not None


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
        _count_if_exists(
            connection, "accounting.renewal_boundary_eir_journal_preparations"
        ),
        _count_if_exists(
            connection, "accounting.renewal_boundary_eir_journal_preparation_entries"
        ),
        _count_if_exists(
            connection, "accounting.renewal_boundary_eir_journal_posting_sets"
        ),
        _count_if_exists(
            connection, "accounting.renewal_boundary_eir_journal_posting_entries"
        ),
    )


def _verify_installed(connection: psycopg.Connection) -> dict[str, int]:
    relations = (
        "accounting.greenfield_regular_renewal_ledger_reconciliation_targets",
        "accounting.renewal_boundary_eir_journal_preparations",
        "accounting.renewal_boundary_eir_journal_preparation_entries",
        "accounting.renewal_boundary_eir_journal_posting_sets",
        "accounting.renewal_boundary_eir_journal_posting_entries",
        "accounting.renewal_boundary_eir_journal_status",
    )
    missing_relations = [name for name in relations if not _exists(connection, name)]
    if missing_relations:
        raise SystemExit(
            "Renewal-boundary EIR live verification failed: missing protected relations: "
            + ", ".join(missing_relations)
        )

    required_functions = (
        "accounting.create_renewal_boundary_eir_journal_draft_batch(uuid,uuid,text,text,text,numeric,jsonb)",
        "accounting.post_renewal_boundary_eir_journal_review_set(uuid,uuid,text,integer,numeric,numeric,text)",
    )
    missing_functions = [
        name
        for name in required_functions
        if connection.execute("select to_regprocedure(%s)", (name,)).fetchone()[0]
        is None
    ]
    if missing_functions:
        raise SystemExit(
            "Renewal-boundary EIR live verification failed: missing protected functions: "
            + ", ".join(missing_functions)
        )

    trigger_names = {
        "accounting_renewal_boundary_eir_preparation_guard",
        "accounting_renewal_boundary_eir_preparation_entry_guard",
        "accounting_renewal_boundary_eir_posting_set_guard",
        "accounting_renewal_boundary_eir_posting_entry_guard",
        "accounting_renewal_boundary_eir_system_journal_entry_guard",
        "accounting_renewal_boundary_eir_system_journal_line_guard",
        "accounting_renewal_boundary_eir_manual_reversal_guard",
        "lending_renewal_execution_boundary_eir_history_void_guard",
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
            "Renewal-boundary EIR live verification failed: protected trigger set is incomplete: "
            + ", ".join(sorted(trigger_names - installed_triggers))
        )

    permissions = {
        str(row[0])
        for row in connection.execute(
            """
            select permission.code
            from core.roles role
            join core.role_permissions role_permission on role_permission.role_id = role.id
            join core.permissions permission on permission.code = role_permission.permission_code
            where role.code = 'management'
              and permission.code in (
                  'accounting.renewal_boundary_eir_journal.prepare',
                  'accounting.renewal_boundary_eir_journal.post'
              )
            """
        ).fetchall()
    }
    expected_permissions = {
        "accounting.renewal_boundary_eir_journal.prepare",
        "accounting.renewal_boundary_eir_journal.post",
    }
    if permissions != expected_permissions:
        raise SystemExit(
            "Renewal-boundary EIR live verification failed: Management protected posting permissions are incomplete."
        )

    invalid_auto = int(
        connection.execute(
            """
            select count(*)
            from accounting.renewal_boundary_eir_journal_status
            where automatic_source_posting = true
            """
        ).fetchone()[0]
    )
    if invalid_auto:
        raise SystemExit(
            "Renewal-boundary EIR live verification failed: automatic source posting was unexpectedly enabled."
        )

    return {
        "preparations": _count(
            connection, "accounting.renewal_boundary_eir_journal_preparations"
        ),
        "preparation_entries": _count(
            connection, "accounting.renewal_boundary_eir_journal_preparation_entries"
        ),
        "posting_sets": _count(
            connection, "accounting.renewal_boundary_eir_journal_posting_sets"
        ),
        "posting_entries": _count(
            connection, "accounting.renewal_boundary_eir_journal_posting_entries"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install the missing read-only renewal-ledger reconciliation view, then "
            "install and verify protected Regular renewal-boundary EIR journal "
            "preparation/posting controls without creating any live drafts, "
            "postings, source events, or journal history."
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

    missing_files = [str(path) for path in MIGRATIONS if not path.is_file()]
    if missing_files:
        raise SystemExit(
            "Renewal-boundary EIR live migration file was not found: "
            + ", ".join(missing_files)
        )
    bodies = [
        _transaction_body(path.read_text(encoding="utf-8"), label=path.name)
        for path in MIGRATIONS
    ]

    try:
        with psycopg.connect(database_url) as connection:
            prerequisites = (
                "lending.loans",
                "lending.collection_transactions",
                "lending.loan_disbursement_events",
                "lending.loan_renewal_execution_events",
                "accounting.greenfield_regular_renewal_rollforward_targets",
                "accounting.greenfield_regular_eir_anchor_readiness",
                "accounting.journal_entries",
                "accounting.journal_lines",
                "accounting.journal_events",
                "accounting.regular_journal_draft_preparations",
                "accounting.regular_journal_posting_sets",
                "accounting.regular_journal_reversal_sets",
                "core.audit_logs",
            )
            missing = [relation for relation in prerequisites if not _exists(connection, relation)]
            if missing:
                raise SystemExit(
                    "Renewal-boundary EIR live migration prerequisite is not installed: "
                    + ", ".join(missing)
                )

            before = _history_snapshot(connection)
            for body in bodies:
                connection.execute(body)
            summary = _verify_installed(connection)
            after = _history_snapshot(connection)

            if after != before:
                raise SystemExit(
                    "Renewal-boundary EIR live migration safety gate failed: installing the read-only reconciliation view and protected boundary posting controls changed live operational/accounting history."
                )

            print(
                "Renewal-boundary EIR protected posting live summary: "
                "renewal_ledger_reconciliation_view=True, "
                f"preparations={summary['preparations']}, "
                f"preparation_entries={summary['preparation_entries']}, "
                f"posting_sets={summary['posting_sets']}, "
                f"posting_entries={summary['posting_entries']}, "
                "history_unchanged=True, protected_prepare=True, "
                "explicit_management_posting=True, automatic_source_posting=False."
            )
            return 0
    except psycopg.Error as error:
        raise SystemExit(
            "Renewal-boundary EIR protected posting migration failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error


if __name__ == "__main__":
    raise SystemExit(main())