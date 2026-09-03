from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "gilbic_backend" / "sql" / "0109_mvp_private_schema_barrier.sql"
VALIDATOR = ROOT / "tools" / "run_mvp_private_schema_barrier_validation.py"
PRIVATE_SCHEMAS = ("core", "lending", "accounting", "mobile")
PUBLIC_CLIENT_ROLES = ("public", "anon", "authenticated", "service_role")


def _normalized_sql() -> str:
    return " ".join(MIGRATION.read_text(encoding="utf-8").lower().split())


def test_migration_is_atomic_and_declares_every_private_schema() -> None:
    sql = _normalized_sql()

    assert sql.startswith("begin;")
    assert sql.endswith("commit;")
    for schema in PRIVATE_SCHEMAS:
        assert re.search(rf"\b{schema}\b", sql)

    assert "revoke usage on schema" in sql
    assert "revoke create on schema" in sql
    assert "revoke all privileges on all tables in schema" in sql
    assert "revoke all privileges on all sequences in schema" in sql
    assert "revoke all privileges on all functions in schema" in sql
    assert "alter default privileges in schema" in sql


def test_migration_handles_optional_supabase_roles_without_owner_changes() -> None:
    sql = _normalized_sql()

    assert "pg_roles" in sql
    for role in PUBLIC_CLIENT_ROLES:
        assert re.search(rf"\b{re.escape(role)}\b", sql)

    assert not re.search(
        r"\bgrant\b[^;]*\bto\s+(public|anon|authenticated|service_role)\b",
        sql,
    )
    assert " disable row level security" not in f" {sql}"
    assert " enable row level security" not in f" {sql}"
    assert " owner to " not in f" {sql}"
    assert " drop schema " not in f" {sql}"
    assert " create role " not in f" {sql}"


def test_default_privileges_prevent_future_public_table_sequence_and_function_access() -> None:
    sql = _normalized_sql()

    for object_type in ("tables", "sequences", "functions"):
        assert (
            f"alter default privileges in schema %i revoke all privileges on {object_type}"
            in sql
        )
    assert "from public" in sql
    assert "from %i" in sql


def test_validation_script_checks_schema_and_relation_privileges_for_all_roles() -> None:
    source = VALIDATOR.read_text(encoding="utf-8").lower()

    for schema in PRIVATE_SCHEMAS:
        assert schema in source
    for role in PUBLIC_CLIENT_ROLES[1:]:
        assert role in source
    assert "has_schema_privilege" in source
    assert "has_table_privilege" in source
    assert "has_sequence_privilege" in source
    assert "has_function_privilege" in source
    assert "database owner" in source
    assert "rollback" in source
    assert "spina_allow_disposable_database" in source
    assert "0109_mvp_private_schema_barrier.sql" in source
