from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import psycopg
from psycopg import sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "gilbic_backend" / "sql" / "0109_mvp_private_schema_barrier.sql"
PRIVATE_SCHEMAS = ("core", "lending", "accounting", "mobile")
SUPABASE_CLIENT_ROLES = ("anon", "authenticated", "service_role")
PUBLIC_PROBE_ROLE = "spina_mvp_public_probe"


def _database_url(value: str | None) -> str:
    url = (value or os.getenv("GILBIC_TEST_DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("GILBIC_TEST_DATABASE_URL or --database-url is required.")
    if os.getenv("SPINA_ALLOW_DISPOSABLE_DATABASE") != "1":
        raise RuntimeError(
            "Refusing to run: SPINA_ALLOW_DISPOSABLE_DATABASE=1 is required."
        )

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    database_name = parsed.path.lstrip("/").lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("The barrier validator accepts only a loopback database host.")
    if not any(marker in database_name for marker in ("test", "mvp", "disposable")):
        raise RuntimeError(
            "The database name must contain test, mvp, or disposable."
        )
    return url


def _role_exists(cursor: psycopg.Cursor[object], role_name: str) -> bool:
    cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = %s)", (role_name,))
    return bool(cursor.fetchone()[0])


def _create_probe_objects(cursor: psycopg.Cursor[object], suffix: str) -> None:
    for schema_name in PRIVATE_SCHEMAS:
        cursor.execute(
            sql.SQL("CREATE TABLE {}.{} (id integer primary key, note text)").format(
                sql.Identifier(schema_name),
                sql.Identifier(f"mvp_barrier_{suffix}_table"),
            )
        )
        cursor.execute(
            sql.SQL("CREATE SEQUENCE {}.{}").format(
                sql.Identifier(schema_name),
                sql.Identifier(f"mvp_barrier_{suffix}_sequence"),
            )
        )
        cursor.execute(
            sql.SQL(
                "CREATE FUNCTION {}.{}() RETURNS integer "
                "LANGUAGE sql IMMUTABLE AS 'SELECT 1'"
            ).format(
                sql.Identifier(schema_name),
                sql.Identifier(f"mvp_barrier_{suffix}_function"),
            )
        )


def _grant_unsafe_baseline(cursor: psycopg.Cursor[object]) -> None:
    targets = ("PUBLIC", *SUPABASE_CLIENT_ROLES)
    for schema_name in PRIVATE_SCHEMAS:
        for target in targets:
            target_sql = sql.SQL("PUBLIC") if target == "PUBLIC" else sql.Identifier(target)
            cursor.execute(
                sql.SQL("GRANT USAGE, CREATE ON SCHEMA {} TO {}").format(
                    sql.Identifier(schema_name), target_sql
                )
            )
            cursor.execute(
                sql.SQL("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA {} TO {}").format(
                    sql.Identifier(schema_name), target_sql
                )
            )
            cursor.execute(
                sql.SQL("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA {} TO {}").format(
                    sql.Identifier(schema_name), target_sql
                )
            )
            cursor.execute(
                sql.SQL("GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA {} TO {}").format(
                    sql.Identifier(schema_name), target_sql
                )
            )
            cursor.execute(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA {} "
                    "GRANT ALL PRIVILEGES ON TABLES TO {}"
                ).format(sql.Identifier(schema_name), target_sql)
            )
            cursor.execute(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA {} "
                    "GRANT ALL PRIVILEGES ON SEQUENCES TO {}"
                ).format(sql.Identifier(schema_name), target_sql)
            )
            cursor.execute(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA {} "
                    "GRANT ALL PRIVILEGES ON FUNCTIONS TO {}"
                ).format(sql.Identifier(schema_name), target_sql)
            )


def _privilege(
    cursor: psycopg.Cursor[object],
    function_name: str,
    role_name: str,
    object_name: str,
    privilege_name: str,
) -> bool:
    cursor.execute(
        sql.SQL("SELECT {}(%s, %s, %s)").format(sql.Identifier(function_name)),
        (role_name, object_name, privilege_name),
    )
    return bool(cursor.fetchone()[0])


def _assert_barrier(cursor: psycopg.Cursor[object], suffix: str) -> None:
    checked_roles = (*SUPABASE_CLIENT_ROLES, PUBLIC_PROBE_ROLE)
    for schema_name in PRIVATE_SCHEMAS:
        table_name = f'{schema_name}.mvp_barrier_{suffix}_table'
        sequence_name = f'{schema_name}.mvp_barrier_{suffix}_sequence'
        function_name = f'{schema_name}.mvp_barrier_{suffix}_function()'
        for role_name in checked_roles:
            checks = {
                "schema usage": _privilege(
                    cursor,
                    "has_schema_privilege",
                    role_name,
                    schema_name,
                    "USAGE",
                ),
                "schema create": _privilege(
                    cursor,
                    "has_schema_privilege",
                    role_name,
                    schema_name,
                    "CREATE",
                ),
                "table select": _privilege(
                    cursor,
                    "has_table_privilege",
                    role_name,
                    table_name,
                    "SELECT",
                ),
                "table write": _privilege(
                    cursor,
                    "has_table_privilege",
                    role_name,
                    table_name,
                    "INSERT,UPDATE,DELETE",
                ),
                "sequence usage": _privilege(
                    cursor,
                    "has_sequence_privilege",
                    role_name,
                    sequence_name,
                    "USAGE",
                ),
                "function execute": _privilege(
                    cursor,
                    "has_function_privilege",
                    role_name,
                    function_name,
                    "EXECUTE",
                ),
            }
            unexpected = [label for label, allowed in checks.items() if allowed]
            if unexpected:
                raise AssertionError(
                    f"{role_name} retained {', '.join(unexpected)} on "
                    f"{schema_name} {suffix} objects"
                )

        cursor.execute(
            sql.SQL("SELECT count(*) FROM {}.{}").format(
                sql.Identifier(schema_name),
                sql.Identifier(f"mvp_barrier_{suffix}_table"),
            )
        )
        cursor.fetchone()


def _cleanup(
    connection: psycopg.Connection[object],
    created_roles: set[str],
) -> None:
    connection.rollback()
    connection.autocommit = True
    with connection.cursor() as cursor:
        for schema_name in PRIVATE_SCHEMAS:
            cursor.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                    sql.Identifier(schema_name)
                )
            )
        for role_name in (*SUPABASE_CLIENT_ROLES, PUBLIC_PROBE_ROLE):
            if role_name in created_roles and _role_exists(cursor, role_name):
                cursor.execute(
                    sql.SQL("DROP OWNED BY {} CASCADE").format(sql.Identifier(role_name))
                )
                cursor.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role_name)))


def validate(database_url: str) -> None:
    migration_sql = MIGRATION.read_text(encoding="utf-8")
    created_roles: set[str] = set()
    connection = psycopg.connect(database_url, autocommit=True)
    try:
        with connection.cursor() as cursor:
            for role_name in (*SUPABASE_CLIENT_ROLES, PUBLIC_PROBE_ROLE):
                if not _role_exists(cursor, role_name):
                    cursor.execute(
                        sql.SQL("CREATE ROLE {} NOLOGIN").format(
                            sql.Identifier(role_name)
                        )
                    )
                    created_roles.add(role_name)

            for schema_name in PRIVATE_SCHEMAS:
                cursor.execute(
                    sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema_name))
                )

            _create_probe_objects(cursor, "existing")
            _grant_unsafe_baseline(cursor)

            # Prove the test begins unsafe before the migration is applied.
            if not _privilege(
                cursor,
                "has_table_privilege",
                "anon",
                "lending.mvp_barrier_existing_table",
                "SELECT",
            ):
                raise AssertionError("Unsafe baseline was not established.")

            cursor.execute(migration_sql)
            _assert_barrier(cursor, "existing")

            # New objects created after 0109 must remain private by default.
            _create_probe_objects(cursor, "future")
            _assert_barrier(cursor, "future")

            cursor.execute("SELECT current_user")
            database_owner = cursor.fetchone()[0]
            print(
                "SPINA MVP private-schema barrier PASS: "
                f"database owner {database_owner} retained access; "
                "PUBLIC, anon, authenticated, service_role denied on existing "
                "and future schema/table/sequence/function probes."
            )
    except Exception:
        connection.rollback()
        raise
    finally:
        _cleanup(connection, created_roles)
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate migration 0109 on a loopback disposable PostgreSQL database."
    )
    parser.add_argument("--database-url")
    args = parser.parse_args(argv)
    validate(_database_url(args.database_url))
    return 0


if __name__ == "__main__":
    sys.exit(main())
