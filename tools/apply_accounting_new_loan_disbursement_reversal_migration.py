from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
REVERSAL_MIGRATION = SQL_ROOT / "0049_add_controlled_new_loan_disbursement_reversals.sql"


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
            "Stage 5D.23 live migration safety gate failed: expected BEGIN/COMMIT wrapper"
        )
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _exists(connection: psycopg.Connection, relation: str) -> bool:
    return connection.execute(
        "select to_regclass(%s)", (relation,)
    ).fetchone()[0] is not None


def _count(connection: psycopg.Connection, relation: str) -> int:
    return int(connection.execute(f"select count(*) from {relation}").fetchone()[0])


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
        "lending.loan_disbursement_cancellations",
        "accounting.loan_disbursement_journal_reversals",
        "accounting.loan_disbursement_cancellation_status",
    ):
        if not _exists(connection, relation):
            raise SystemExit("Stage 5D.23 live verification failed: missing " + relation)

    for schema, function_name in (
        ("accounting", "guard_loan_disbursement_cancellation_record_write"),
        ("accounting", "guard_loan_disbursement_reversal_record_write"),
        ("accounting", "guard_protected_loan_disbursement_reversal_insert"),
        ("accounting", "reverse_posted_new_loan_disbursement"),
    ):
        if _function_count(connection, schema, function_name) != 1:
            raise SystemExit(
                "Stage 5D.23 live verification failed: protected function missing or ambiguous: "
                + schema
                + "."
                + function_name
            )

    trigger_checks = (
        (
            "lending.loan_disbursement_cancellations",
            "lending_loan_disbursement_cancellation_guard",
        ),
        (
            "accounting.loan_disbursement_journal_reversals",
            "accounting_loan_disbursement_journal_reversal_guard",
        ),
        (
            "accounting.journal_entries",
            "accounting_protected_loan_disbursement_reversal_insert_guard",
        ),
    )
    for relation, trigger_name in trigger_checks:
        if _trigger_count(connection, relation, trigger_name) != 1:
            raise SystemExit(
                "Stage 5D.23 live verification failed: protected trigger missing: "
                + trigger_name
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
        where permission.code = 'accounting.loan_disbursement.journal.reverse'
        """
    ).fetchone()
    if permission != (1, 1):
        raise SystemExit(
            "Stage 5D.23 live verification failed: Management reversal permission is missing"
        )

    cancellations = _count(connection, "lending.loan_disbursement_cancellations")
    reversals = _count(connection, "accounting.loan_disbursement_journal_reversals")
    status_rows = _count(connection, "accounting.loan_disbursement_cancellation_status")
    posting_rows = _count(connection, "accounting.loan_disbursement_journal_postings")
    if status_rows != posting_rows:
        raise SystemExit(
            "Stage 5D.23 live verification failed: cancellation status row count does not match protected Stage 5D.22 posting count"
        )
    if cancellations != reversals:
        raise SystemExit(
            "Stage 5D.23 live verification failed: cancellation and reversal audit counts differ"
        )

    automatic = int(
        connection.execute(
            """
            select count(*)
            from accounting.loan_disbursement_cancellation_status
            where automatic_source_posting = true
            """
        ).fetchone()[0]
    )
    if automatic:
        raise SystemExit(
            "Stage 5D.23 live verification failed: automatic source posting was unexpectedly enabled"
        )

    cancellation_ready = int(
        connection.execute(
            """
            select count(*)
            from accounting.loan_disbursement_cancellation_status
            where cancellation_ready = true
            """
        ).fetchone()[0]
    )
    cancelled_exact = int(
        connection.execute(
            """
            select count(*)
            from accounting.loan_disbursement_cancellation_status
            where cancelled_reversal_audit_exact = true
            """
        ).fetchone()[0]
    )
    return {
        "postings": posting_rows,
        "cancellations": cancellations,
        "reversals": reversals,
        "cancellation_ready": cancellation_ready,
        "cancelled_reversal_audit_exact": cancelled_exact,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install and verify Stage 5D.23 controlled new-Regular-loan disbursement "
            "cancellation/reversal controls without cancelling or reversing any live posting."
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
    if not REVERSAL_MIGRATION.is_file():
        raise SystemExit("Stage 5D.23 migration file was not found: " + str(REVERSAL_MIGRATION))
    body = _transaction_body(REVERSAL_MIGRATION.read_text(encoding="utf-8"))

    try:
        with psycopg.connect(database_url) as connection:
            prerequisites = (
                "lending.clients",
                "lending.loans",
                "lending.loan_disbursement_events",
                "accounting.loan_disbursement_journal_draft_preparations",
                "accounting.loan_disbursement_journal_postings",
                "accounting.accounts",
                "accounting.fiscal_periods",
                "accounting.journal_entries",
                "accounting.journal_lines",
                "accounting.journal_events",
                "core.audit_logs",
            )
            missing = [relation for relation in prerequisites if not _exists(connection, relation)]
            if missing:
                raise SystemExit(
                    "Stage 5D.23 live migration prerequisite is not installed: "
                    + ", ".join(missing)
                )

            cancellation_already_installed = _exists(
                connection, "lending.loan_disbursement_cancellations"
            )
            reversal_already_installed = _exists(
                connection, "accounting.loan_disbursement_journal_reversals"
            )
            before_cancellations = (
                _count(connection, "lending.loan_disbursement_cancellations")
                if cancellation_already_installed
                else 0
            )
            before_reversals = (
                _count(connection, "accounting.loan_disbursement_journal_reversals")
                if reversal_already_installed
                else 0
            )
            before = (
                _count(connection, "lending.clients"),
                _count(connection, "lending.loans"),
                _count(connection, "lending.collection_transactions"),
                _count(connection, "lending.loan_disbursement_events"),
                _count(connection, "accounting.loan_disbursement_journal_draft_preparations"),
                _count(connection, "accounting.loan_disbursement_journal_postings"),
                _count(connection, "accounting.journal_entries"),
                _count(connection, "accounting.journal_lines"),
                _count(connection, "accounting.journal_events"),
                _count(connection, "core.audit_logs"),
            )

            connection.execute(body)
            summary = _verify_installed(connection)

            after = (
                _count(connection, "lending.clients"),
                _count(connection, "lending.loans"),
                _count(connection, "lending.collection_transactions"),
                _count(connection, "lending.loan_disbursement_events"),
                _count(connection, "accounting.loan_disbursement_journal_draft_preparations"),
                _count(connection, "accounting.loan_disbursement_journal_postings"),
                _count(connection, "accounting.journal_entries"),
                _count(connection, "accounting.journal_lines"),
                _count(connection, "accounting.journal_events"),
                _count(connection, "core.audit_logs"),
            )
            if after != before:
                raise SystemExit(
                    "Stage 5D.23 live migration safety gate failed: installing reversal controls changed live operational or financial-history rows"
                )
            if summary["cancellations"] != before_cancellations:
                raise SystemExit(
                    "Stage 5D.23 live migration safety gate failed: installing controls created or removed cancellation evidence"
                )
            if summary["reversals"] != before_reversals:
                raise SystemExit(
                    "Stage 5D.23 live migration safety gate failed: installing controls created or removed reversal audit rows"
                )

            print(
                "Stage 5D.23 controlled reversal install summary: "
                f"postings={summary['postings']}, cancellations={summary['cancellations']}, "
                f"reversals={summary['reversals']}, cancellation_ready={summary['cancellation_ready']}, "
                f"cancelled_reversal_audit_exact={summary['cancelled_reversal_audit_exact']}, "
                "protected_reversal_enabled=True, automatic_source_posting=False; "
                "no operational or financial-history rows changed."
            )
            return 0
    except psycopg.Error as error:
        raise SystemExit(
            "Stage 5D.23 controlled reversal migration failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error


if __name__ == "__main__":
    raise SystemExit(main())
