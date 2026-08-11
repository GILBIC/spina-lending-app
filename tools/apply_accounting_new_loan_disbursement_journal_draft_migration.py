from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
DRAFT_MIGRATION = SQL_ROOT / "0047_add_protected_new_loan_disbursement_journal_drafts.sql"


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
            "Stage 5D.21 live migration safety gate failed: expected BEGIN/COMMIT wrapper"
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
        "accounting.loan_disbursement_journal_draft_preparations",
        "accounting.loan_disbursement_journal_draft_status",
    ):
        if not _exists(connection, relation):
            raise SystemExit("Stage 5D.21 live verification failed: missing " + relation)

    for function_name in (
        "guard_loan_disbursement_journal_draft_preparation_write",
        "guard_loan_disbursement_system_journal_entry_change",
        "guard_loan_disbursement_system_journal_line_change",
        "create_new_loan_disbursement_journal_draft",
    ):
        if _function_count(connection, "accounting", function_name) != 1:
            raise SystemExit(
                "Stage 5D.21 live verification failed: protected function missing or ambiguous: accounting."
                + function_name
            )

    trigger_checks = (
        (
            "accounting.loan_disbursement_journal_draft_preparations",
            "accounting_loan_disbursement_journal_draft_preparation_guard",
        ),
        (
            "accounting.journal_entries",
            "accounting_loan_disbursement_system_journal_entry_guard",
        ),
        (
            "accounting.journal_lines",
            "accounting_loan_disbursement_system_journal_line_guard",
        ),
    )
    for relation, trigger_name in trigger_checks:
        count = int(
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
        if count != 1:
            raise SystemExit(
                "Stage 5D.21 live verification failed: protected trigger missing: "
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
        where permission.code = 'accounting.loan_disbursement.journal.prepare'
        """
    ).fetchone()
    if permission != (1, 1):
        raise SystemExit(
            "Stage 5D.21 live verification failed: Management draft preparation permission is missing"
        )

    preparations = _count(
        connection, "accounting.loan_disbursement_journal_draft_preparations"
    )
    statuses = _count(connection, "accounting.loan_disbursement_journal_draft_status")
    if statuses != preparations:
        raise SystemExit(
            "Stage 5D.21 live verification failed: draft status row count does not match immutable preparation count"
        )

    unsafe_flags = int(
        connection.execute(
            """
            select count(*)
            from accounting.loan_disbursement_journal_draft_status
            where posting_enabled = true
               or automatic_source_posting = true
            """
        ).fetchone()[0]
    )
    if unsafe_flags:
        raise SystemExit(
            "Stage 5D.21 live verification failed: draft stage unexpectedly enabled posting or automatic source posting"
        )

    draft_journals = int(
        connection.execute(
            """
            select count(*)
            from accounting.loan_disbursement_journal_draft_status
            where journal_status = 'draft'
            """
        ).fetchone()[0]
    )
    integrity_ready = int(
        connection.execute(
            """
            select count(*)
            from accounting.loan_disbursement_journal_draft_status
            where draft_integrity_ready = true
            """
        ).fetchone()[0]
    )
    return {
        "preparations": preparations,
        "draft_journals": draft_journals,
        "integrity_ready": integrity_ready,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install and verify Stage 5D.21 protected new-Regular-loan disbursement "
            "draft controls without creating any live draft or posting history."
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
    if not DRAFT_MIGRATION.is_file():
        raise SystemExit("Stage 5D.21 migration file was not found: " + str(DRAFT_MIGRATION))
    body = _transaction_body(DRAFT_MIGRATION.read_text(encoding="utf-8"))

    try:
        with psycopg.connect(database_url) as connection:
            prerequisites = (
                "lending.loans",
                "lending.clients",
                "lending.loan_disbursement_events",
                "accounting.loan_disbursement_journal_coordinates",
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
                    "Stage 5D.21 live migration prerequisite is not installed: "
                    + ", ".join(missing)
                )

            preparation_already_installed = _exists(
                connection,
                "accounting.loan_disbursement_journal_draft_preparations",
            )
            before_preparations = (
                _count(connection, "accounting.loan_disbursement_journal_draft_preparations")
                if preparation_already_installed
                else 0
            )

            before = (
                _count(connection, "lending.clients"),
                _count(connection, "lending.loans"),
                _count(connection, "lending.collection_transactions"),
                _count(connection, "lending.loan_disbursement_events"),
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
                _count(connection, "accounting.journal_entries"),
                _count(connection, "accounting.journal_lines"),
                _count(connection, "accounting.journal_events"),
                _count(connection, "core.audit_logs"),
            )
            if after != before:
                raise SystemExit(
                    "Stage 5D.21 live migration safety gate failed: installing draft controls changed live operational or financial-history rows"
                )
            if summary["preparations"] != before_preparations:
                raise SystemExit(
                    "Stage 5D.21 live migration safety gate failed: installing controls created or removed protected draft preparations"
                )

            print(
                "Stage 5D.21 protected draft install summary: "
                f"preparations={summary['preparations']}, "
                f"draft_journals={summary['draft_journals']}, "
                f"integrity_ready={summary['integrity_ready']}, "
                "posting_enabled=False, automatic_source_posting=False; "
                "no operational or financial-history rows changed."
            )
            return 0
    except psycopg.Error as error:
        raise SystemExit(
            "Stage 5D.21 protected draft migration failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error


if __name__ == "__main__":
    raise SystemExit(main())
