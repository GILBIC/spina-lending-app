from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
POSTING_MIGRATION = SQL_ROOT / "0048_add_protected_new_loan_disbursement_journal_posting.sql"


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
            "Stage 5D.22 live migration safety gate failed: expected BEGIN/COMMIT wrapper"
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


def _verify_installed(connection: psycopg.Connection) -> dict[str, int]:
    for relation in (
        "accounting.loan_disbursement_journal_postings",
        "accounting.loan_disbursement_journal_posting_status",
    ):
        if not _exists(connection, relation):
            raise SystemExit("Stage 5D.22 live verification failed: missing " + relation)

    for function_name in (
        "guard_loan_disbursement_journal_posting_record_write",
        "post_new_loan_disbursement_journal",
    ):
        if _function_count(connection, "accounting", function_name) != 1:
            raise SystemExit(
                "Stage 5D.22 live verification failed: protected function missing or ambiguous: accounting."
                + function_name
            )

    trigger_count = int(
        connection.execute(
            """
            select count(*)
            from pg_trigger
            where tgrelid = 'accounting.loan_disbursement_journal_postings'::regclass
              and not tgisinternal
              and tgname = 'accounting_loan_disbursement_journal_posting_guard'
            """
        ).fetchone()[0]
    )
    if trigger_count != 1:
        raise SystemExit(
            "Stage 5D.22 live verification failed: immutable posting-audit trigger is missing"
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
        where permission.code = 'accounting.loan_disbursement.journal.post'
        """
    ).fetchone()
    if permission != (1, 1):
        raise SystemExit(
            "Stage 5D.22 live verification failed: Management posting permission is missing"
        )

    postings = _count(connection, "accounting.loan_disbursement_journal_postings")
    status_rows = _count(connection, "accounting.loan_disbursement_journal_posting_status")
    preparation_rows = _count(
        connection, "accounting.loan_disbursement_journal_draft_preparations"
    )
    if status_rows != preparation_rows:
        raise SystemExit(
            "Stage 5D.22 live verification failed: posting status row count does not match protected draft preparation count"
        )

    automatic = int(
        connection.execute(
            """
            select count(*)
            from accounting.loan_disbursement_journal_posting_status
            where automatic_source_posting = true
            """
        ).fetchone()[0]
    )
    if automatic:
        raise SystemExit(
            "Stage 5D.22 live verification failed: automatic source posting was unexpectedly enabled"
        )

    posted_exact = int(
        connection.execute(
            """
            select count(*)
            from accounting.loan_disbursement_journal_posting_status
            where posted_audit_exact = true
            """
        ).fetchone()[0]
    )
    posting_ready = int(
        connection.execute(
            """
            select count(*)
            from accounting.loan_disbursement_journal_posting_status
            where posting_ready = true
            """
        ).fetchone()[0]
    )
    return {
        "preparations": preparation_rows,
        "status_rows": status_rows,
        "postings": postings,
        "posting_ready": posting_ready,
        "posted_audit_exact": posted_exact,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install and verify Stage 5D.22 explicit protected new-Regular-loan "
            "disbursement posting controls without posting any live draft or changing financial history."
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
    if not POSTING_MIGRATION.is_file():
        raise SystemExit("Stage 5D.22 migration file was not found: " + str(POSTING_MIGRATION))
    body = _transaction_body(POSTING_MIGRATION.read_text(encoding="utf-8"))

    try:
        with psycopg.connect(database_url) as connection:
            prerequisites = (
                "lending.clients",
                "lending.loans",
                "lending.loan_disbursement_events",
                "accounting.loan_disbursement_journal_draft_preparations",
                "accounting.loan_disbursement_journal_draft_status",
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
                    "Stage 5D.22 live migration prerequisite is not installed: "
                    + ", ".join(missing)
                )

            posting_already_installed = _exists(
                connection, "accounting.loan_disbursement_journal_postings"
            )
            before_postings = (
                _count(connection, "accounting.loan_disbursement_journal_postings")
                if posting_already_installed
                else 0
            )
            before = (
                _count(connection, "lending.clients"),
                _count(connection, "lending.loans"),
                _count(connection, "lending.collection_transactions"),
                _count(connection, "lending.loan_disbursement_events"),
                _count(connection, "accounting.loan_disbursement_journal_draft_preparations"),
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
                _count(connection, "accounting.journal_entries"),
                _count(connection, "accounting.journal_lines"),
                _count(connection, "accounting.journal_events"),
                _count(connection, "core.audit_logs"),
            )
            if after != before:
                raise SystemExit(
                    "Stage 5D.22 live migration safety gate failed: installing posting controls changed live operational or financial-history rows"
                )
            if summary["postings"] != before_postings:
                raise SystemExit(
                    "Stage 5D.22 live migration safety gate failed: installing controls created or removed protected posting audits"
                )

            print(
                "Stage 5D.22 protected posting install summary: "
                f"preparations={summary['preparations']}, status_rows={summary['status_rows']}, "
                f"postings={summary['postings']}, posting_ready={summary['posting_ready']}, "
                f"posted_audit_exact={summary['posted_audit_exact']}, "
                "protected_posting_enabled=True, automatic_source_posting=False; "
                "no operational or financial-history rows changed."
            )
            return 0
    except psycopg.Error as error:
        raise SystemExit(
            "Stage 5D.22 protected posting migration failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error


if __name__ == "__main__":
    raise SystemExit(main())
