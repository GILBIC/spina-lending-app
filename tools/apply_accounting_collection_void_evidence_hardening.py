from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
HARDENING_MIGRATION = SQL_ROOT / "0044_harden_collection_void_reversal_evidence.sql"


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
            "Stage 5D.18 void-evidence hardening safety gate failed: expected BEGIN/COMMIT wrapper"
        )
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _exists(connection: psycopg.Connection, relation: str) -> bool:
    return connection.execute(
        "SELECT to_regclass(%s)",
        (relation,),
    ).fetchone()[0] is not None


def _count(connection: psycopg.Connection, relation: str) -> int:
    return int(connection.execute(f"SELECT count(*) FROM {relation}").fetchone()[0])


def _function_count(connection: psycopg.Connection, schema: str, name: str) -> int:
    return int(
        connection.execute(
            """
            SELECT count(*)
            FROM pg_proc proc
            JOIN pg_namespace ns ON ns.oid = proc.pronamespace
            WHERE ns.nspname = %s
              AND proc.proname = %s
            """,
            (schema, name),
        ).fetchone()[0]
    )


def _trigger_names(connection: psycopg.Connection) -> set[str]:
    rows = connection.execute(
        """
        SELECT tgname
        FROM pg_trigger
        WHERE NOT tgisinternal
          AND tgname IN (
              'lending_collection_transaction_void_audit_guard',
              'accounting_00_collection_void_evidence_guard',
              'accounting_01_regular_collection_void_reversal',
              'accounting_00_regular_collection_void_reversal',
              'accounting_accounted_regular_collection_void_guard'
          )
        """
    ).fetchall()
    return {str(row[0]) for row in rows}


def _verify_installed(connection: psycopg.Connection) -> None:
    if _function_count(
        connection,
        "lending",
        "guard_collection_transaction_void_audit_immutability",
    ) != 1:
        raise SystemExit(
            "Stage 5D.18 live verification failed: immutable collection-void audit guard function is missing"
        )
    if _function_count(
        connection,
        "accounting",
        "guard_collection_void_transition_evidence",
    ) != 1:
        raise SystemExit(
            "Stage 5D.18 live verification failed: exact collection-void transition evidence guard is missing"
        )

    expected_triggers = {
        "lending_collection_transaction_void_audit_guard",
        "accounting_00_collection_void_evidence_guard",
        "accounting_01_regular_collection_void_reversal",
        "accounting_accounted_regular_collection_void_guard",
    }
    observed = _trigger_names(connection)
    if observed != expected_triggers:
        raise SystemExit(
            "Stage 5D.18 live verification failed: hardened void/reversal trigger set is incorrect: "
            + ", ".join(sorted(observed))
        )

    ordered = [
        str(row[0])
        for row in connection.execute(
            """
            SELECT tgname
            FROM pg_trigger
            WHERE tgrelid = 'lending.collection_transactions'::regclass
              AND NOT tgisinternal
              AND tgname IN (
                  'accounting_00_collection_void_evidence_guard',
                  'accounting_01_regular_collection_void_reversal',
                  'accounting_accounted_regular_collection_void_guard'
              )
            ORDER BY tgname
            """
        ).fetchall()
    ]
    if ordered != [
        "accounting_00_collection_void_evidence_guard",
        "accounting_01_regular_collection_void_reversal",
        "accounting_accounted_regular_collection_void_guard",
    ]:
        raise SystemExit(
            "Stage 5D.18 live verification failed: void evidence/reversal/fail-closed trigger ordering is not deterministic"
        )

    guard_definition = connection.execute(
        """
        SELECT pg_get_functiondef(proc.oid)
        FROM pg_proc proc
        JOIN pg_namespace ns ON ns.oid = proc.pronamespace
        WHERE ns.nspname = 'accounting'
          AND proc.proname = 'guard_collection_void_transition_evidence'
        """
    ).fetchone()[0]
    guard_definition = str(guard_definition)
    for required_text in (
        "voided_by_user_id IS DISTINCT FROM NEW.voided_by_user_id",
        "void_record.voided_at IS DISTINCT FROM NEW.voided_at",
        "immutable void evidence",
    ):
        if required_text not in guard_definition:
            raise SystemExit(
                "Stage 5D.18 live verification failed: exact operational void evidence check is incomplete: "
                + required_text
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install and verify Stage 5D.18 immutable collection-void evidence and "
            "trigger ordering without changing any live operational/accounting rows."
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
    if not HARDENING_MIGRATION.is_file():
        raise SystemExit(
            "Stage 5D.18 hardening migration file was not found: "
            + str(HARDENING_MIGRATION)
        )
    migration_body = _transaction_body(HARDENING_MIGRATION.read_text(encoding="utf-8"))

    try:
        with psycopg.connect(database_url) as connection:
            prerequisites = (
                "lending.collection_transactions",
                "lending.collection_transaction_voids",
                "accounting.journal_entries",
                "accounting.regular_journal_reversal_sets",
                "accounting.regular_journal_reversal_entries",
            )
            missing = [relation for relation in prerequisites if not _exists(connection, relation)]
            if missing:
                raise SystemExit(
                    "Stage 5D.18 hardening prerequisite is not installed: "
                    + ", ".join(missing)
                )

            before = (
                _count(connection, "lending.collection_transactions"),
                _count(connection, "lending.collection_transaction_voids"),
                _count(connection, "accounting.journal_entries"),
                _count(connection, "accounting.journal_lines"),
                _count(connection, "accounting.journal_events"),
                _count(connection, "accounting.regular_journal_reversal_sets"),
                _count(connection, "accounting.regular_journal_reversal_entries"),
            )

            connection.execute(migration_body)
            _verify_installed(connection)

            after = (
                _count(connection, "lending.collection_transactions"),
                _count(connection, "lending.collection_transaction_voids"),
                _count(connection, "accounting.journal_entries"),
                _count(connection, "accounting.journal_lines"),
                _count(connection, "accounting.journal_events"),
                _count(connection, "accounting.regular_journal_reversal_sets"),
                _count(connection, "accounting.regular_journal_reversal_entries"),
            )
            if after != before:
                raise SystemExit(
                    "Stage 5D.18 hardening safety gate failed: installing immutable evidence controls changed live rows"
                )

            print(
                "Stage 5D.18 void-evidence hardening summary: "
                f"transactions={after[0]}, void_audits={after[1]}, journals={after[2]}, "
                f"reversal_sets={after[5]}, reversal_entries={after[6]}, "
                "void_audit_immutable=True, evidence_match_required=True, "
                "controlled_reversal_enabled=True, automatic_source_posting=False."
            )
            return 0
    except psycopg.Error as error:
        raise SystemExit(
            "Stage 5D.18 void-evidence hardening failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error


if __name__ == "__main__":
    raise SystemExit(main())
