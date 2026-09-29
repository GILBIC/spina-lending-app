"""A caller's schema must not replace builtins used by private app routines."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest

DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="Disposable database required")
MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0132_fix_private_function_search_paths.sql"
)


def _apply(connection):
    source = MIGRATION.read_text(encoding="utf-8")
    connection.execute(source.strip().removeprefix("BEGIN;").removesuffix("COMMIT;"))


def test_caller_schema_cannot_shadow_private_function_builtins():
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            connection.execute("CREATE SCHEMA IF NOT EXISTS core")
            connection.execute("CREATE SCHEMA readiness_untrusted")
            connection.execute("""CREATE FUNCTION readiness_untrusted.lower(text)
                RETURNS text LANGUAGE sql AS $$ SELECT 'shadowed'::text $$""")
            connection.execute("""CREATE FUNCTION core.readiness_path_probe()
                RETURNS text LANGUAGE plpgsql AS $$ BEGIN RETURN lower('TeST'::text); END $$""")
            before = connection.execute("""SELECT proowner, proacl, prosecdef, prosrc FROM pg_proc
                WHERE oid='core.readiness_path_probe()'::regprocedure""").fetchone()
            _apply(connection)
            connection.execute(
                "SET LOCAL search_path = readiness_untrusted, pg_catalog"
            )
            assert (
                connection.execute("SELECT core.readiness_path_probe()").fetchone()[0]
                == "test"
            )
            after = connection.execute("""SELECT proowner, proacl, prosecdef, prosrc FROM pg_proc
                WHERE oid='core.readiness_path_probe()'::regprocedure""").fetchone()
            assert after == before
            _apply(connection)
            assert (
                connection.execute("SELECT core.readiness_path_probe()").fetchone()[0]
                == "test"
            )
        finally:
            connection.rollback()


def test_existing_fixed_path_is_preserved_and_unsafe_shared_schema_rejected():
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            connection.execute("CREATE SCHEMA IF NOT EXISTS core")
            connection.execute("""CREATE FUNCTION core.readiness_fixed_path_probe()
                RETURNS int LANGUAGE sql SET search_path = pg_catalog AS $$ SELECT 1 $$""")
            _apply(connection)
            assert (
                connection.execute("""SELECT proconfig FROM pg_proc
                WHERE oid='core.readiness_fixed_path_probe()'::regprocedure""").fetchone()[
                    0
                ]
                == ["search_path=pg_catalog"]
            )
            connection.execute("GRANT CREATE ON SCHEMA public TO PUBLIC")
            with pytest.raises(psycopg.errors.RaiseException, match="Untrusted CREATE"):
                _apply(connection)
        finally:
            connection.rollback()
