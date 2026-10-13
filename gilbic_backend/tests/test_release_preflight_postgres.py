"""Real catalog checks in an explicitly disposable, minimal PostgreSQL database.

The trigger bodies are catalog fixtures, not financial behavior simulations.
The disclosure migration's behavior is covered by its existing PostgreSQL tests.
"""

import os
from uuid import uuid4

import psycopg
import pytest
from gilbic_backend.config import Settings
from psycopg import sql
from psycopg.conninfo import make_conninfo

from gilbic_backend import release_preflight
from tools import run_stage5d17_disposable_postgres_validation as disposable

DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="GILBIC_TEST_DATABASE_URL is not configured"
)

TABLES = (
    "core.users",
    "core.devices",
    "core.user_roles",
    "lending.clients",
    "lending.loans",
    "lending.client_payment_proofs",
    "core.employee_profiles",
    "core.employee_profile_versions",
    "core.employee_action_receipts",
    "core.employee_history",
    "lending.first_loan_disclosure_calculations",
    "lending.first_loan_approvals",
)
GUARDS = (
    (
        "lending.first_loan_disclosure_calculations",
        "first_loan_disclosure_source_guard",
        "lending.guard_first_loan_disclosure_insert",
        "INSERT",
        "ROW",
    ),
    (
        "lending.first_loan_disclosure_calculations",
        "first_loan_disclosure_immutable",
        "lending.reject_loan_application_history_mutation",
        "UPDATE OR DELETE",
        "ROW",
    ),
    (
        "lending.first_loan_disclosure_calculations",
        "first_loan_disclosure_no_truncate",
        "lending.reject_loan_application_history_mutation",
        "TRUNCATE",
        "STATEMENT",
    ),
    (
        "lending.first_loan_approvals",
        "first_loan_disclosure_approval_guard",
        "lending.guard_first_loan_disclosure_approval",
        "INSERT",
        "ROW",
    ),
)


@pytest.fixture(scope="module")
def catalog_url():
    if os.getenv("SPINA_ALLOW_DISPOSABLE_DATABASE") != "1":
        raise RuntimeError("Preflight proof requires explicit disposable opt-in")
    assert DATABASE_URL is not None
    params = disposable._safe_local_connection_params(DATABASE_URL)
    admin_url = make_conninfo(**{**params, "dbname": "postgres"})
    name = "spina_preflight_" + uuid4().hex[:12]
    target_url = make_conninfo(**{**params, "dbname": name})
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                sql.Identifier(name)
            )
        )
    try:
        yield target_url
    finally:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
            )


@pytest.fixture
def catalog(catalog_url):
    with psycopg.connect(catalog_url, autocommit=True) as connection:
        for schema in ("core", "lending"):
            connection.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                    sql.Identifier(schema)
                )
            )
            connection.execute(
                sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema))
            )
        for table in TABLES:
            connection.execute(
                sql.SQL("CREATE TABLE {} (id integer)").format(
                    sql.Identifier(*table.split("."))
                )
            )
        for function in {guard[2] for guard in GUARDS} | {"lending.wrong_guard"}:
            connection.execute(
                sql.SQL(
                    "CREATE FUNCTION {}() RETURNS trigger LANGUAGE plpgsql "
                    "AS 'BEGIN RETURN NEW; END'"
                ).format(sql.Identifier(*function.split(".")))
            )
        for table, name, function, event, level in GUARDS:
            _create_guard(connection, table, name, function, event, level)
        yield connection, Settings(_env_file=None, database_url=catalog_url)


def _create_guard(
    connection, table, name, function, event, level, *, timing="BEFORE", condition=""
):
    connection.execute(
        sql.SQL(
            "CREATE TRIGGER {} {} {} ON {} FOR EACH {} {} EXECUTE FUNCTION {}()"
        ).format(
            sql.Identifier(name),
            sql.SQL(timing),
            sql.SQL(event),
            sql.Identifier(*table.split(".")),
            sql.SQL(level),
            sql.SQL(condition),
            sql.Identifier(*function.split(".")),
        )
    )


def _drop_guard(connection, table, name):
    connection.execute(
        sql.SQL("DROP TRIGGER {} ON {}").format(
            sql.Identifier(name), sql.Identifier(*table.split("."))
        )
    )


def test_preflight_blocks_missing_disclosure_table(catalog):
    connection, settings = catalog
    connection.execute("DROP TABLE lending.first_loan_disclosure_calculations CASCADE")
    result = release_preflight.probe_database(settings)
    assert result["schema"] is False


def test_preflight_requires_screen_signature_capture_method(catalog):
    connection, settings = catalog
    for table in release_preflight.REQUIRED_TABLES:
        schema, name = table.split(".")
        connection.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema))
        )
        connection.execute(
            sql.SQL("CREATE TABLE IF NOT EXISTS {} (id integer)").format(
                sql.Identifier(schema, name)
            )
        )
    assert release_preflight.probe_database(settings)["schema"] is False
    connection.execute(
        "ALTER TABLE lending.office_review_evidence ADD COLUMN capture_method TEXT NOT NULL DEFAULT 'paper_scan'"
    )
    assert release_preflight.probe_database(settings)["schema"] is True
    connection.execute(
        "ALTER TABLE lending.office_review_evidence ALTER COLUMN capture_method DROP NOT NULL"
    )
    assert release_preflight.probe_database(settings)["schema"] is False


@pytest.mark.parametrize("table,name,function,event,level", GUARDS)
def test_preflight_blocks_missing_disclosure_guard(
    catalog, table, name, function, event, level
):
    connection, settings = catalog
    _drop_guard(connection, table, name)
    result = release_preflight.probe_database(settings)
    assert not all(result.values()), result
    assert result["disclosure_guards"] is False


def test_preflight_blocks_column_limited_immutability(catalog):
    connection, settings = catalog
    _drop_guard(
        connection,
        "lending.first_loan_disclosure_calculations",
        "first_loan_disclosure_immutable",
    )
    connection.execute(
        """CREATE TRIGGER first_loan_disclosure_immutable
        BEFORE UPDATE OF id OR DELETE ON lending.first_loan_disclosure_calculations
        FOR EACH ROW EXECUTE FUNCTION lending.reject_loan_application_history_mutation()"""
    )
    result = release_preflight.probe_database(settings)
    assert result["disclosure_guards"] is False


@pytest.mark.parametrize("mode", ("ENABLE", "ENABLE ALWAYS"))
def test_preflight_accepts_complete_origin_or_always_enabled_guards(catalog, mode):
    connection, settings = catalog
    for table, name, *_ in GUARDS:
        connection.execute(
            sql.SQL("ALTER TABLE {} {} TRIGGER {}").format(
                sql.Identifier(*table.split(".")), sql.SQL(mode), sql.Identifier(name)
            )
        )
    assert release_preflight.probe_database(settings) == {
        # This historical disclosure-only fixture cannot run the treasury runtime.
        "schema": False,
        "private_grants": True,
        "disclosure_guards": True,
        "treasury_guards": False,
        "accounting_source_guards": False,
    }


@pytest.mark.parametrize("table,name,function,event,level", GUARDS)
@pytest.mark.parametrize("mode", ("DISABLE", "ENABLE REPLICA"))
def test_preflight_blocks_guards_that_do_not_fire_for_origin_writes(
    catalog, table, name, function, event, level, mode
):
    connection, settings = catalog
    connection.execute(
        sql.SQL("ALTER TABLE {} {} TRIGGER {}").format(
            sql.Identifier(*table.split(".")), sql.SQL(mode), sql.Identifier(name)
        )
    )
    assert release_preflight.probe_database(settings)["disclosure_guards"] is False


@pytest.mark.parametrize("table,name,function,event,level", GUARDS)
@pytest.mark.parametrize("wrong_binding", ("function", "table"))
def test_preflight_blocks_wrong_guard_binding(
    catalog, table, name, function, event, level, wrong_binding
):
    connection, settings = catalog
    _drop_guard(connection, table, name)
    _create_guard(
        connection,
        "core.users" if wrong_binding == "table" else table,
        name,
        "lending.wrong_guard" if wrong_binding == "function" else function,
        event,
        level,
    )
    assert release_preflight.probe_database(settings)["disclosure_guards"] is False


@pytest.mark.parametrize("guard", (GUARDS[0], GUARDS[3]))
@pytest.mark.parametrize("replacement", ("after", "conditional"))
def test_preflight_blocks_late_or_conditional_insert_guards(
    catalog, guard, replacement
):
    connection, settings = catalog
    table, name, function, event, level = guard
    _drop_guard(connection, table, name)
    _create_guard(
        connection,
        table,
        name,
        function,
        event,
        level,
        timing="AFTER" if replacement == "after" else "BEFORE",
        condition="WHEN (false)" if replacement == "conditional" else "",
    )
    assert release_preflight.probe_database(settings)["disclosure_guards"] is False
