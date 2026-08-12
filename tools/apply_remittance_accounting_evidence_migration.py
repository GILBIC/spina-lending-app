from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
MIGRATION = SQL_ROOT / "0057_add_remittance_accounting_evidence.sql"


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
            "Remittance accounting live migration safety gate failed: expected BEGIN/COMMIT wrapper"
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
        "accounting.remittance_transfer_evidence",
        "accounting.remittance_transfer_readiness",
    ):
        if not _exists(connection, relation):
            raise SystemExit(
                "Remittance accounting live verification failed: missing " + relation
            )

    for schema, function_name in (
        ("accounting", "guard_remittance_transfer_evidence_write"),
        ("accounting", "record_remittance_transfer_evidence"),
        ("accounting", "void_remittance_transfer_evidence"),
    ):
        if _function_count(connection, schema, function_name) != 1:
            raise SystemExit(
                "Remittance accounting live verification failed: protected function missing or ambiguous: "
                + schema
                + "."
                + function_name
            )

    trigger_count = int(
        connection.execute(
            """
            select count(*)
            from pg_trigger
            where tgrelid = 'accounting.remittance_transfer_evidence'::regclass
              and not tgisinternal
              and tgname = 'accounting_remittance_transfer_evidence_guard'
            """
        ).fetchone()[0]
    )
    if trigger_count != 1:
        raise SystemExit(
            "Remittance accounting live verification failed: immutable evidence trigger is missing"
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
        where permission.code = 'accounting.remittance_transfer.evidence.manage'
        """
    ).fetchone()
    if permission != (1, 1):
        raise SystemExit(
            "Remittance accounting live verification failed: Management evidence permission is missing"
        )

    invalid_flags = int(
        connection.execute(
            """
            select count(*)
            from accounting.remittance_transfer_readiness
            where income_recognition = true
               or journal_lines_enabled = true
               or automatic_source_posting = true
            """
        ).fetchone()[0]
    )
    if invalid_flags:
        raise SystemExit(
            "Remittance accounting live verification failed: custody transfer unexpectedly enabled income, journal lines, or automatic posting"
        )

    evidence_rows = _count(connection, "accounting.remittance_transfer_evidence")
    readiness_rows = _count(connection, "accounting.remittance_transfer_readiness")
    ready_rows = int(
        connection.execute(
            """
            select count(*)
            from accounting.remittance_transfer_readiness
            where readiness_status = 'transfer_coordinate_ready'
            """
        ).fetchone()[0]
    )
    return {
        "evidence_rows": evidence_rows,
        "readiness_rows": readiness_rows,
        "ready_rows": ready_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install and verify remittance destination-evidence controls on the live "
            "database without creating evidence, journals, or changing operational history."
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
        raise SystemExit("Remittance accounting migration file was not found: " + str(MIGRATION))
    body = _transaction_body(MIGRATION.read_text(encoding="utf-8"))

    try:
        with psycopg.connect(database_url) as connection:
            prerequisites = (
                "core.users",
                "core.roles",
                "core.permissions",
                "core.audit_logs",
                "lending.collection_remittances",
                "lending.collection_transactions",
                "accounting.accounts",
                "accounting.journal_entries",
                "accounting.journal_lines",
            )
            missing_prerequisites = [
                relation for relation in prerequisites if not _exists(connection, relation)
            ]
            if missing_prerequisites:
                raise SystemExit(
                    "Remittance accounting live migration prerequisite is not installed: "
                    + ", ".join(missing_prerequisites)
                )

            before_remittances = _count(connection, "lending.collection_remittances")
            before_transactions = _count(connection, "lending.collection_transactions")
            before_journals = _count(connection, "accounting.journal_entries")
            before_lines = _count(connection, "accounting.journal_lines")
            before_audit = _count(connection, "core.audit_logs")
            evidence_already_installed = _exists(
                connection, "accounting.remittance_transfer_evidence"
            )
            before_evidence = (
                _count(connection, "accounting.remittance_transfer_evidence")
                if evidence_already_installed
                else 0
            )

            connection.execute(body)
            summary = _verify_installed(connection)

            after = (
                _count(connection, "lending.collection_remittances"),
                _count(connection, "lending.collection_transactions"),
                _count(connection, "accounting.journal_entries"),
                _count(connection, "accounting.journal_lines"),
                _count(connection, "core.audit_logs"),
            )
            before = (
                before_remittances,
                before_transactions,
                before_journals,
                before_lines,
                before_audit,
            )
            if after != before:
                raise SystemExit(
                    "Remittance accounting live migration safety gate failed: installing controls changed live operational/accounting rows"
                )
            if summary["evidence_rows"] != before_evidence:
                raise SystemExit(
                    "Remittance accounting live migration safety gate failed: installing controls created or removed remittance evidence rows"
                )
            if summary["readiness_rows"] != before_remittances:
                raise SystemExit(
                    "Remittance accounting live verification failed: readiness row count does not equal remittance count"
                )

            print(
                "Remittance accounting live summary: "
                f"remittances={before_remittances}, evidence_rows={summary['evidence_rows']}, "
                f"coordinate_ready={summary['ready_rows']}, history_unchanged=True, "
                "income_recognition=False, journal_lines_enabled=False, "
                "automatic_source_posting=False."
            )
            return 0
    except psycopg.Error as error:
        raise SystemExit(
            "Remittance accounting live migration failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error


if __name__ == "__main__":
    raise SystemExit(main())
