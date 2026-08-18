from __future__ import annotations

import sys
from pathlib import Path

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "gilbic_backend" / "src"
for import_root in (ROOT, BACKEND_SRC):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from gilbic_backend.config import get_settings


MIGRATIONS = (
    ROOT / "gilbic_backend" / "sql" / "0097_add_delegated_collector_area_access.sql",
    ROOT / "gilbic_backend" / "sql" / "0098_harden_hierarchical_collector_area_ownership.sql",
)

DELEGATED_TABLES = (
    "collector_area_access_requests",
    "collector_area_access_request_scopes",
    "collector_area_access_grants",
    "collector_area_access_grant_scopes",
    "collector_area_access_events",
)
EXPECTED_PERMISSIONS = {
    "delegated_area.view",
    "delegated_area.request",
    "delegated_area.grant",
}
EXPECTED_TRIGGERS = {
    "lending_guard_collector_area_access_request_scope_immutable",
    "lending_guard_collector_area_access_grant_scope_immutable",
    "lending_guard_collector_area_access_event_immutable",
    "lending_guard_collector_area_access_request_update",
    "lending_guard_collector_area_access_grant_update",
}


def _transaction_body(path: Path) -> str:
    source = path.read_text(encoding="utf-8").strip()
    if not source.startswith("BEGIN;") or not source.endswith("COMMIT;"):
        raise SystemExit(
            f"{path.name} safety gate failed: expected immutable BEGIN/COMMIT wrapper"
        )
    return source[len("BEGIN;") : -len("COMMIT;")].strip()


def _table_exists(connection: psycopg.Connection, name: str) -> bool:
    return connection.execute(
        "SELECT to_regclass(%s) IS NOT NULL",
        (f"lending.{name}",),
    ).fetchone()[0]


def _table_columns(connection: psycopg.Connection, schema: str, table: str) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema=%s AND table_name=%s
            ORDER BY ordinal_position
            """,
            (schema, table),
        ).fetchall()
    ]


def _snapshot_table(
    connection: psycopg.Connection,
    schema: str,
    table: str,
) -> list[tuple[object, ...]]:
    columns = _table_columns(connection, schema, table)
    if not columns:
        raise SystemExit(f"safety gate failed: expected table {schema}.{table} is missing")
    query = sql.SQL("SELECT {} FROM {}.{} ORDER BY id").format(
        sql.SQL(", ").join(sql.Identifier(column) for column in columns),
        sql.Identifier(schema),
        sql.Identifier(table),
    )
    return list(connection.execute(query).fetchall())


def _function_exists(connection: psycopg.Connection, signature: str) -> bool:
    return connection.execute(
        "SELECT to_regprocedure(%s) IS NOT NULL",
        (signature,),
    ).fetchone()[0]


def _trigger_state(connection: psycopg.Connection, trigger_name: str) -> str | None:
    row = connection.execute(
        """
        SELECT trigger.tgenabled
        FROM pg_trigger trigger
        WHERE trigger.tgname=%s AND NOT trigger.tgisinternal
        """,
        (trigger_name,),
    ).fetchone()
    return None if row is None else str(row[0])


def _verify_installed(connection: psycopg.Connection) -> None:
    missing_tables = [name for name in DELEGATED_TABLES if not _table_exists(connection, name)]
    if missing_tables:
        raise SystemExit(
            "0097/0098 verification failed: delegated-area tables are incomplete: "
            + ", ".join(missing_tables)
        )

    permissions = {
        str(row[0])
        for row in connection.execute(
            "SELECT code FROM core.permissions WHERE code = ANY(%s)",
            (list(EXPECTED_PERMISSIONS),),
        ).fetchall()
    }
    if permissions != EXPECTED_PERMISSIONS:
        raise SystemExit("0097/0098 verification failed: delegated permissions are incomplete")

    collector_permissions = {
        str(row[0])
        for row in connection.execute(
            """
            SELECT permission.code
            FROM core.roles role
            JOIN core.role_permissions mapping ON mapping.role_id=role.id
            JOIN core.permissions permission ON permission.code=mapping.permission_code
            WHERE role.code='collector' AND permission.code = ANY(%s)
            """,
            (list(EXPECTED_PERMISSIONS),),
        ).fetchall()
    }
    if collector_permissions != EXPECTED_PERMISSIONS:
        raise SystemExit(
            "0097/0098 verification failed: Collector delegated permissions are incomplete"
        )

    required_functions = (
        "lending.normalize_area_path(text)",
        "lending.area_path_contains(text,text,boolean)",
        "lending.collector_area_owner(text)",
        "lending.collector_owns_area_path(uuid,text)",
        "lending.collector_has_active_delegated_area_access(uuid,text,timestamp with time zone)",
        "lending.capture_collection_assignment()",
    )
    missing_functions = [
        signature for signature in required_functions if not _function_exists(connection, signature)
    ]
    if missing_functions:
        raise SystemExit(
            "0097/0098 verification failed: required functions are incomplete: "
            + ", ".join(missing_functions)
        )

    for trigger_name in EXPECTED_TRIGGERS:
        if _trigger_state(connection, trigger_name) != "O":
            raise SystemExit(
                f"0097/0098 verification failed: trigger {trigger_name} is missing or disabled"
            )

    capture_trigger = connection.execute(
        """
        SELECT trigger.tgenabled, procedure.proname
        FROM pg_trigger trigger
        JOIN pg_proc procedure ON procedure.oid=trigger.tgfoid
        WHERE trigger.tgrelid='lending.collection_transactions'::regclass
          AND trigger.tgname='lending_collection_assignment_capture'
          AND NOT trigger.tgisinternal
        """
    ).fetchone()
    if capture_trigger != ("O", "capture_collection_assignment"):
        raise SystemExit(
            "0097/0098 verification failed: collection assignment capture trigger is not authoritative"
        )

    normalized = connection.execute(
        "SELECT lending.normalize_area_path(%s)",
        ("  CARDONA  ›   Looc  ",),
    ).fetchone()[0]
    if normalized != "CARDONA › Looc":
        raise SystemExit("0097/0098 verification failed: area normalization is incorrect")

    boundary = connection.execute(
        """
        SELECT
            lending.area_path_contains('CARDONA', 'CARDONA › Looc', true),
            lending.area_path_contains('CARDONA', 'CARDONAL', true),
            lending.area_path_contains('CARDONA › Looc', 'CARDONA › Looc', false)
        """
    ).fetchone()
    if boundary != (True, False, True):
        raise SystemExit("0097/0098 verification failed: hierarchical path boundaries are incorrect")

    owner_definition = connection.execute(
        "SELECT pg_get_functiondef(to_regprocedure('lending.collector_owns_area_path(uuid,text)'))"
    ).fetchone()[0]
    if "coalesce" not in str(owner_definition).lower():
        raise SystemExit(
            "0097/0098 verification failed: ambiguous ownership is not explicitly fail-closed"
        )


def main() -> int:
    for path in MIGRATIONS:
        if not path.is_file():
            raise SystemExit(f"0097/0098 migration file was not found: {path}")

    migration_bodies = [_transaction_body(path) for path in MIGRATIONS]
    database_url = get_settings().database_url

    try:
        with psycopg.connect(database_url) as connection:
            prerequisites = (
                "lending.collection_transactions",
                "lending.collector_area_assignments",
                "lending.collection_receipt_application_state",
            )
            missing_prerequisites = [
                name
                for name in prerequisites
                if connection.execute("SELECT to_regclass(%s) IS NULL", (name,)).fetchone()[0]
            ]
            if missing_prerequisites:
                raise SystemExit(
                    "0097/0098 safety gate failed: prerequisite schema is missing: "
                    + ", ".join(missing_prerequisites)
                )

            existing = {name: _table_exists(connection, name) for name in DELEGATED_TABLES}
            if all(existing.values()):
                _verify_installed(connection)
                print("0097/0098 are already installed and verified; no changes were made.")
                return 0
            if any(existing.values()):
                present = ", ".join(name for name, value in existing.items() if value)
                raise SystemExit(
                    "0097/0098 safety gate failed: partial delegated-area schema already exists: "
                    + present
                )

            before_transactions = _snapshot_table(
                connection, "lending", "collection_transactions"
            )
            before_assignments = _snapshot_table(
                connection, "lending", "collector_area_assignments"
            )

            # Serialize the schema transition against new collection writes and area
            # ownership edits. The migration is schema/authorization-only and must not
            # rewrite either existing financial history or permanent assignments.
            connection.execute(
                "LOCK TABLE lending.collection_transactions IN ACCESS EXCLUSIVE MODE"
            )
            connection.execute(
                "LOCK TABLE lending.collector_area_assignments IN ACCESS EXCLUSIVE MODE"
            )

            for body in migration_bodies:
                connection.execute(body)

            _verify_installed(connection)

            after_transactions = _snapshot_table(
                connection, "lending", "collection_transactions"
            )
            after_assignments = _snapshot_table(
                connection, "lending", "collector_area_assignments"
            )
            if after_transactions != before_transactions:
                raise SystemExit(
                    "0097/0098 safety gate failed: pre-existing collection history changed"
                )
            if after_assignments != before_assignments:
                raise SystemExit(
                    "0097/0098 safety gate failed: permanent Collector assignments changed"
                )

            created_authorization_rows = sum(
                int(
                    connection.execute(
                        sql.SQL("SELECT count(*)::bigint FROM lending.{}").format(
                            sql.Identifier(name)
                        )
                    ).fetchone()[0]
                )
                for name in DELEGATED_TABLES
            )
            if created_authorization_rows != 0:
                raise SystemExit(
                    "0097/0098 safety gate failed: migration unexpectedly created delegated authorization evidence"
                )

            # psycopg commits only after every verification above passes. Any exception
            # rolls 0097 and 0098 back together.

    except psycopg.Error as error:
        raise SystemExit(f"0097/0098 migration failed and was rolled back: {error}") from error

    print(
        "0097/0098 live migration complete. Delegated Collector authorization and "
        "hierarchical ownership are installed; existing collection history and permanent "
        "Collector assignments are unchanged."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
