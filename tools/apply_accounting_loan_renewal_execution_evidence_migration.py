from __future__ import annotations

import argparse
import os
from collections import Counter
from pathlib import Path

import psycopg


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
EVIDENCE_MIGRATION = SQL_ROOT / "0050_add_authoritative_renewal_execution_evidence.sql"


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
            "Stage 5D.24 live migration safety gate failed: expected BEGIN/COMMIT wrapper"
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


def _trigger_count(
    connection: psycopg.Connection,
    *,
    relation: str,
    trigger_name: str,
) -> int:
    return int(
        connection.execute(
            """
            select count(*)
            from pg_trigger
            where tgrelid = %s::regclass
              and not tgisinternal
              and tgname = %s
            """,
            (relation, trigger_name),
        ).fetchone()[0]
    )


def _verify_installed(connection: psycopg.Connection) -> dict[str, int]:
    for relation in (
        "lending.loan_renewal_execution_events",
        "accounting.loan_renewal_execution_source_readiness",
    ):
        if not _exists(connection, relation):
            raise SystemExit(
                "Stage 5D.24 live verification failed: missing " + relation
            )

    for schema, function_name in (
        ("lending", "guard_loan_renewal_execution_event_write"),
        ("lending", "guard_linked_renewal_release_void"),
        ("accounting", "record_loan_renewal_execution_evidence"),
        ("accounting", "void_loan_renewal_execution_evidence"),
    ):
        if _function_count(connection, schema, function_name) != 1:
            raise SystemExit(
                "Stage 5D.24 live verification failed: protected function missing or ambiguous: "
                + schema
                + "."
                + function_name
            )

    if _trigger_count(
        connection,
        relation="lending.loan_renewal_execution_events",
        trigger_name="lending_loan_renewal_execution_event_guard",
    ) != 1:
        raise SystemExit(
            "Stage 5D.24 live verification failed: immutable renewal execution evidence trigger is missing"
        )
    if _trigger_count(
        connection,
        relation="lending.loan_disbursement_events",
        trigger_name="lending_loan_renewal_execution_release_void_guard",
    ) != 1:
        raise SystemExit(
            "Stage 5D.24 live verification failed: linked renewal-release void dependency guard is missing"
        )

    permission = connection.execute(
        """
        select
            count(*) filter (where permission.code is not null),
            count(*) filter (where role.code = 'management')
        from core.permissions permission
        left join core.role_permissions rp
          on rp.permission_code = permission.code
        left join core.roles role on role.id = rp.role_id
        where permission.code = 'accounting.loan_renewal_execution.evidence.manage'
        """
    ).fetchone()
    if permission != (1, 1):
        raise SystemExit(
            "Stage 5D.24 live verification failed: Management renewal execution evidence permission is missing"
        )

    invalid_journal_flag = int(
        connection.execute(
            """
            select count(*)
            from accounting.loan_renewal_execution_source_readiness
            where journal_lines_enabled = true
               or automatic_source_posting = true
            """
        ).fetchone()[0]
    )
    if invalid_journal_flag:
        raise SystemExit(
            "Stage 5D.24 live verification failed: renewal readiness unexpectedly enabled journal lines or automatic posting"
        )

    total_events = _count(connection, "lending.loan_renewal_execution_events")
    active_events = int(
        connection.execute(
            "select count(*) from lending.loan_renewal_execution_events where is_voided = false"
        ).fetchone()[0]
    )
    readiness_rows = _count(connection, "accounting.loan_renewal_execution_source_readiness")
    ready = int(
        connection.execute(
            """
            select count(*)
            from accounting.loan_renewal_execution_source_readiness
            where readiness_status = 'renewal_execution_evidence_ready'
            """
        ).fetchone()[0]
    )
    missing = int(
        connection.execute(
            """
            select count(*)
            from accounting.loan_renewal_execution_source_readiness
            where readiness_status = 'missing_renewal_execution_evidence'
            """
        ).fetchone()[0]
    )
    policy_review = readiness_rows - ready - missing
    return {
        "events": total_events,
        "active_events": active_events,
        "readiness_rows": readiness_rows,
        "ready": ready,
        "missing": missing,
        "policy_review": policy_review,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install and verify Stage 5D.24 authoritative renewal execution evidence "
            "controls without inferring old/new loan relationships or creating evidence/journal rows."
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
    if not EVIDENCE_MIGRATION.is_file():
        raise SystemExit("Stage 5D.24 migration file was not found: " + str(EVIDENCE_MIGRATION))
    body = _transaction_body(EVIDENCE_MIGRATION.read_text(encoding="utf-8"))

    try:
        with psycopg.connect(database_url) as connection:
            prerequisites = (
                "lending.loans",
                "lending.clients",
                "lending.loan_types",
                "lending.client_renewal_requests",
                "lending.loan_disbursement_events",
                "accounting.journal_entries",
                "accounting.journal_lines",
                "accounting.journal_events",
                "core.audit_logs",
            )
            missing_prerequisites = [
                relation for relation in prerequisites if not _exists(connection, relation)
            ]
            if missing_prerequisites:
                raise SystemExit(
                    "Stage 5D.24 live migration prerequisite is not installed: "
                    + ", ".join(missing_prerequisites)
                )

            before_loans = _count(connection, "lending.loans")
            before_statuses = _loan_status_counts(connection)
            before_clients = _count(connection, "lending.clients")
            before_transactions = _count(connection, "lending.collection_transactions")
            before_journals = _count(connection, "accounting.journal_entries")
            before_lines = _count(connection, "accounting.journal_lines")
            before_journal_events = _count(connection, "accounting.journal_events")
            before_audit = _count(connection, "core.audit_logs")
            before_disbursement_events = _count(connection, "lending.loan_disbursement_events")
            active_renewal_releases = int(
                connection.execute(
                    """
                    select count(*)
                    from lending.loan_disbursement_events
                    where event_kind = 'renewal_release' and is_voided = false
                    """
                ).fetchone()[0]
            )
            execution_already_installed = _exists(
                connection, "lending.loan_renewal_execution_events"
            )
            before_execution_events = (
                _count(connection, "lending.loan_renewal_execution_events")
                if execution_already_installed
                else 0
            )

            connection.execute(body)
            summary = _verify_installed(connection)

            after = (
                _count(connection, "lending.loans"),
                _loan_status_counts(connection),
                _count(connection, "lending.clients"),
                _count(connection, "lending.collection_transactions"),
                _count(connection, "accounting.journal_entries"),
                _count(connection, "accounting.journal_lines"),
                _count(connection, "accounting.journal_events"),
                _count(connection, "core.audit_logs"),
                _count(connection, "lending.loan_disbursement_events"),
            )
            before = (
                before_loans,
                before_statuses,
                before_clients,
                before_transactions,
                before_journals,
                before_lines,
                before_journal_events,
                before_audit,
                before_disbursement_events,
            )
            if after != before:
                raise SystemExit(
                    "Stage 5D.24 live migration safety gate failed: installing renewal execution controls changed live operational/accounting rows"
                )
            if summary["events"] != before_execution_events:
                raise SystemExit(
                    "Stage 5D.24 live migration safety gate failed: installing controls created or removed renewal execution evidence rows"
                )
            if summary["readiness_rows"] != active_renewal_releases:
                raise SystemExit(
                    "Stage 5D.24 live verification failed: readiness row count does not equal active authoritative renewal_release evidence count"
                )

            print(
                "Stage 5D.24 renewal execution evidence summary: "
                f"active_renewal_releases={active_renewal_releases}, "
                f"execution_events={summary['events']}, active_execution_events={summary['active_events']}, "
                f"evidence_ready={summary['ready']}, missing_execution_evidence={summary['missing']}, "
                f"policy_review={summary['policy_review']}, dependency_guard=True, "
                "journal_lines_enabled=False, automatic_source_posting=False."
            )
            return 0
    except psycopg.Error as error:
        raise SystemExit(
            "Stage 5D.24 authoritative renewal execution evidence migration failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error


if __name__ == "__main__":
    raise SystemExit(main())
