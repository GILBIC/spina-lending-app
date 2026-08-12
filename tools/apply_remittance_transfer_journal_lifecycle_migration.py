from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
MIGRATION = SQL_ROOT / "0058_add_protected_remittance_transfer_journal_lifecycle.sql"


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
            "Remittance transfer journal live migration safety gate failed: expected BEGIN/COMMIT wrapper"
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


def _permission_count(connection: psycopg.Connection, permission_code: str) -> tuple[int, int]:
    row = connection.execute(
        """
        select
            count(*) filter (where permission.code is not null),
            count(*) filter (where role.code = 'management')
        from core.permissions permission
        left join core.role_permissions rp
          on rp.permission_code = permission.code
        left join core.roles role on role.id = rp.role_id
        where permission.code = %s
        """,
        (permission_code,),
    ).fetchone()
    return int(row[0]), int(row[1])


def _verify_installed(connection: psycopg.Connection) -> dict[str, int]:
    relations = (
        "accounting.remittance_transfer_journal_preparations",
        "accounting.remittance_transfer_journal_postings",
        "accounting.remittance_transfer_journal_reversals",
        "accounting.remittance_transfer_journal_status",
    )
    for relation in relations:
        if not _exists(connection, relation):
            raise SystemExit(
                "Remittance transfer journal live verification failed: missing " + relation
            )

    functions = (
        "guard_remittance_transfer_journal_preparation_write",
        "guard_remittance_transfer_journal_posting_write",
        "guard_remittance_transfer_journal_reversal_write",
        "guard_remittance_transfer_system_journal_entry_change",
        "guard_remittance_transfer_system_journal_line_change",
        "guard_protected_remittance_transfer_reversal_insert",
        "create_remittance_transfer_journal_draft",
        "post_remittance_transfer_journal",
        "reverse_posted_remittance_transfer",
    )
    for function_name in functions:
        if _function_count(connection, "accounting", function_name) != 1:
            raise SystemExit(
                "Remittance transfer journal live verification failed: protected function missing or ambiguous: accounting."
                + function_name
            )

    for permission_code in (
        "accounting.remittance_transfer.journal.prepare",
        "accounting.remittance_transfer.journal.post",
        "accounting.remittance_transfer.journal.reverse",
    ):
        if _permission_count(connection, permission_code) != (1, 1):
            raise SystemExit(
                "Remittance transfer journal live verification failed: Management permission missing: "
                + permission_code
            )

    expected_triggers = (
        ("accounting.remittance_transfer_journal_preparations", "accounting_remittance_transfer_preparation_guard"),
        ("accounting.remittance_transfer_journal_postings", "accounting_remittance_transfer_posting_guard"),
        ("accounting.remittance_transfer_journal_reversals", "accounting_remittance_transfer_reversal_guard"),
        ("accounting.journal_entries", "accounting_remittance_transfer_system_journal_entry_guard"),
        ("accounting.journal_entries", "accounting_protected_remittance_transfer_reversal_insert_guard"),
        ("accounting.journal_lines", "accounting_remittance_transfer_system_journal_line_guard"),
    )
    for relation, trigger_name in expected_triggers:
        trigger_count = int(
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
        if trigger_count != 1:
            raise SystemExit(
                "Remittance transfer journal live verification failed: protected trigger missing: "
                + trigger_name
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
            "Remittance transfer journal live verification failed: lifecycle safety flags are inconsistent"
        )

    return {
        "preparations": _count(
            connection, "accounting.remittance_transfer_journal_preparations"
        ),
        "postings": _count(
            connection, "accounting.remittance_transfer_journal_postings"
        ),
        "reversals": _count(
            connection, "accounting.remittance_transfer_journal_reversals"
        ),
        "status_rows": _count(
            connection, "accounting.remittance_transfer_journal_status"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install and verify protected remittance-transfer draft/post/reversal controls "
            "on the live database without creating financial history or mutating source events."
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
            "Remittance transfer journal migration file was not found: " + str(MIGRATION)
        )
    body = _transaction_body(MIGRATION.read_text(encoding="utf-8"))

    try:
        with psycopg.connect(database_url) as connection:
            prerequisites = (
                "core.users",
                "core.roles",
                "core.permissions",
                "core.audit_logs",
                "lending.collection_remittances",
                "accounting.accounts",
                "accounting.fiscal_periods",
                "accounting.journal_entries",
                "accounting.journal_lines",
                "accounting.remittance_transfer_evidence",
                "accounting.remittance_transfer_readiness",
            )
            missing_prerequisites = [
                relation for relation in prerequisites if not _exists(connection, relation)
            ]
            if missing_prerequisites:
                raise SystemExit(
                    "Remittance transfer journal live migration prerequisite is not installed: "
                    + ", ".join(missing_prerequisites)
                )

            before_remittances = _count(connection, "lending.collection_remittances")
            before_evidence = _count(connection, "accounting.remittance_transfer_evidence")
            before_journals = _count(connection, "accounting.journal_entries")
            before_lines = _count(connection, "accounting.journal_lines")
            before_audit = _count(connection, "core.audit_logs")

            already_installed = _exists(
                connection, "accounting.remittance_transfer_journal_preparations"
            )
            before_preparations = (
                _count(connection, "accounting.remittance_transfer_journal_preparations")
                if already_installed
                else 0
            )
            before_postings = (
                _count(connection, "accounting.remittance_transfer_journal_postings")
                if already_installed
                else 0
            )
            before_reversals = (
                _count(connection, "accounting.remittance_transfer_journal_reversals")
                if already_installed
                else 0
            )

            connection.execute(body)
            summary = _verify_installed(connection)

            after_history = (
                _count(connection, "lending.collection_remittances"),
                _count(connection, "accounting.remittance_transfer_evidence"),
                _count(connection, "accounting.journal_entries"),
                _count(connection, "accounting.journal_lines"),
                _count(connection, "core.audit_logs"),
            )
            before_history = (
                before_remittances,
                before_evidence,
                before_journals,
                before_lines,
                before_audit,
            )
            if after_history != before_history:
                raise SystemExit(
                    "Remittance transfer journal live migration safety gate failed: installing controls changed live operational/accounting history"
                )

            if (
                summary["preparations"] != before_preparations
                or summary["postings"] != before_postings
                or summary["reversals"] != before_reversals
            ):
                raise SystemExit(
                    "Remittance transfer journal live migration safety gate failed: installation created or removed lifecycle rows"
                )
            if summary["status_rows"] != summary["preparations"]:
                raise SystemExit(
                    "Remittance transfer journal live verification failed: status row count does not reconcile to preparation count"
                )

            print(
                "Remittance transfer journal live summary: "
                f"remittances={before_remittances}, evidence_rows={before_evidence}, "
                f"preparations={summary['preparations']}, postings={summary['postings']}, "
                f"reversals={summary['reversals']}, history_unchanged=True, "
                "income_recognition=False, explicit_management_posting=True, "
                "automatic_source_posting=False."
            )
            return 0
    except psycopg.Error as error:
        raise SystemExit(
            "Remittance transfer journal live migration failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error


if __name__ == "__main__":
    raise SystemExit(main())
