from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from tools import run_stage5d17_disposable_postgres_validation as disposable


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="GILBIC_TEST_DATABASE_URL is not configured"
)
MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0119_add_client_cif_review_confirmation.sql"
)


@pytest.fixture(scope="module")
def runtime_url() -> str:
    # These tests include TRUNCATE rejection and a committed migration rerun.
    # Only the existing runner's explicitly disposable, loopback DB is allowed.
    if os.getenv("SPINA_ALLOW_DISPOSABLE_DATABASE") != "1":
        raise RuntimeError("CIF proof requires SPINA_ALLOW_DISPOSABLE_DATABASE=1")
    assert DATABASE_URL is not None
    params = disposable._safe_local_connection_params(DATABASE_URL)
    if not re.fullmatch(r"spina_onboarding_[0-9a-f]{12}", params["dbname"]):
        raise RuntimeError("CIF proof requires the onboarding disposable database")
    disposable._clear_endpoint_environment()
    return make_conninfo(**params)


@pytest.fixture
def connection(runtime_url: str) -> Iterator[psycopg.Connection]:
    connection = psycopg.connect(runtime_url, row_factory=dict_row)
    try:
        row = connection.execute(
            "select to_regclass('lending.client_cif_review_confirmations') as relation"
        ).fetchone()
        assert row["relation"] is not None, "Runner must apply CIF migrations 0114/0119"
        yield connection
    finally:
        # Roll back test data instead of disabling immutable-evidence triggers.
        connection.rollback()
        connection.close()


def _seed_case(connection: psycopg.Connection) -> dict[str, UUID]:
    case = {key: uuid4() for key in ("actor", "client", "other", "cif", "next_cif")}
    connection.execute(
        "insert into core.users (id, username, full_name) values (%s, %s, %s)",
        (case["actor"], f"cif-proof-{case['actor'].hex}", "Synthetic CIF Witness"),
    )
    for client_id in (case["client"], case["other"]):
        connection.execute(
            """
            insert into lending.clients (id, client_code, full_name, status)
            values (%s, %s, 'Synthetic CIF Borrower', 'inactive')
            """,
            (client_id, f"SYN-CIF-{client_id.hex}"),
        )
    for version, key in ((1, "cif"), (2, "next_cif")):
        connection.execute(
            """
            insert into lending.client_cif_versions (
                id, client_id, version_number, is_current,
                full_name, phone_number, present_address
            ) values (%s, %s, %s, %s, 'Synthetic CIF Borrower',
                      '00000000000', 'Synthetic office test address')
            """,
            (case[key], case["client"], version, version == 1),
        )
    return case


def _insert(
    connection: psycopg.Connection, case: dict[str, UUID], **overrides: Any
) -> dict[str, Any]:
    values = {
        "client_id": case["client"],
        "cif_version_id": case["cif"],
        "review_cycle_number": 1,
        "review_snapshot": Jsonb({"full_name": "Synthetic CIF Borrower"}),
        "applicant_confirmation_evidence_reference": "SYNTHETIC-CIF-CONFIRMATION",
        "witnessed_by_user_id": case["actor"],
    }
    values.update(overrides)
    return connection.execute(
        """
        insert into lending.client_cif_review_confirmations (
            client_id, cif_version_id, review_cycle_number, review_snapshot,
            applicant_confirmation_evidence_reference, witnessed_by_user_id
        ) values (%(client_id)s, %(cif_version_id)s, %(review_cycle_number)s,
                  %(review_snapshot)s, %(applicant_confirmation_evidence_reference)s,
                  %(witnessed_by_user_id)s)
        returning *
        """,
        values,
    ).fetchone()


def _read(connection: psycopg.Connection, record_id: UUID) -> dict[str, Any]:
    return connection.execute(
        "select * from lending.client_cif_review_confirmations where id = %s",
        (record_id,),
    ).fetchone()


def _unrelated_counts(connection: psycopg.Connection) -> dict[str, int]:
    tables = connection.execute(
        """
        select schemaname, tablename from pg_tables
        where schemaname in ('core', 'lending', 'accounting', 'mobile', 'auth')
          and not (schemaname = 'lending' and tablename = 'client_cif_review_confirmations')
        order by schemaname, tablename
        """
    ).fetchall()
    return {
        f"{table['schemaname']}.{table['tablename']}": connection.execute(
            sql.SQL("select count(*) as count from {}.{}").format(
                sql.Identifier(table["schemaname"]), sql.Identifier(table["tablename"])
            )
        ).fetchone()["count"]
        for table in tables
    }


def test_valid_confirmation_has_server_time_and_no_new_financial_rows(connection) -> None:
    case = _seed_case(connection)
    before = _unrelated_counts(connection)
    assert {"auth.users", "core.users", "lending.clients", "lending.loans"} <= before.keys()
    row = _insert(connection, case)
    assert row["client_id"] == case["client"]
    assert row["cif_version_id"] == case["cif"]
    assert row["witnessed_by_user_id"] == case["actor"]
    assert row["review_cycle_number"] == 1
    assert row["review_snapshot"] == {"full_name": "Synthetic CIF Borrower"}
    assert row["applicant_confirmation_evidence_reference"] == "SYNTHETIC-CIF-CONFIRMATION"
    assert row["confirmed_at"] == connection.execute("select now() as now").fetchone()["now"]
    assert _unrelated_counts(connection) == before
    client = connection.execute(
        "select status, user_id from lending.clients where id = %s", (case["client"],)
    ).fetchone()
    assert client == {"status": "inactive", "user_id": None}
    cif = connection.execute(
        "select status, activated_at from lending.client_cif_versions where id = %s",
        (case["cif"],),
    ).fetchone()
    assert cif == {"status": "draft", "activated_at": None}


@pytest.mark.parametrize("duplicate", ["cif_version", "client_cycle"])
def test_duplicate_confirmation_is_rejected_without_overwriting(connection, duplicate) -> None:
    case = _seed_case(connection)
    first = _insert(connection, case)
    override = (
        {"review_cycle_number": 2}
        if duplicate == "cif_version"
        else {"cif_version_id": case["next_cif"]}
    )
    with pytest.raises(psycopg.errors.UniqueViolation):
        with connection.transaction():
            _insert(connection, case, **override)
    assert _read(connection, first["id"]) == first


def test_new_version_and_review_cycle_preserve_previous_confirmation(connection) -> None:
    case = _seed_case(connection)
    first = _insert(connection, case)
    second = _insert(connection, case, cif_version_id=case["next_cif"], review_cycle_number=2)
    assert first["id"] != second["id"]
    assert _read(connection, first["id"]) == first


@pytest.mark.parametrize("field", ["client_id", "cif_version_id", "witnessed_by_user_id"])
def test_missing_reference_is_rejected(connection, field) -> None:
    case = _seed_case(connection)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with connection.transaction():
            _insert(connection, case, **{field: uuid4()})


def test_existing_but_mismatched_client_and_cif_are_rejected(connection) -> None:
    case = _seed_case(connection)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with connection.transaction():
            _insert(connection, case, client_id=case["other"])


@pytest.mark.parametrize(
    "field,value,sqlstate",
    [
        ("review_cycle_number", 0, "23514"),
        ("review_cycle_number", -1, "23514"),
        ("review_cycle_number", None, "23502"),
        ("applicant_confirmation_evidence_reference", "", "23514"),
        ("applicant_confirmation_evidence_reference", "   ", "23514"),
        ("applicant_confirmation_evidence_reference", None, "23502"),
        ("review_snapshot", None, "23502"),
        ("review_snapshot", Jsonb({}), "23514"),
        ("review_snapshot", Jsonb([]), "23514"),
        ("review_snapshot", Jsonb("not an object"), "23514"),
        ("review_snapshot", Jsonb(None), "23514"),
        ("witnessed_by_user_id", None, "23502"),
        ("client_id", None, "23502"),
        ("cif_version_id", None, "23502"),
    ],
)
def test_invalid_confirmation_is_rejected(connection, field, value, sqlstate) -> None:
    case = _seed_case(connection)
    with pytest.raises(psycopg.IntegrityError) as rejected:
        with connection.transaction():
            _insert(connection, case, **{field: value})
    assert rejected.value.sqlstate == sqlstate
    count = connection.execute(
        "select count(*) as count from lending.client_cif_review_confirmations where client_id = %s",
        (case["client"],),
    ).fetchone()["count"]
    assert count == 0


@pytest.mark.parametrize("operation", ["update", "delete", "truncate"])
def test_confirmation_mutations_are_rejected(connection, operation) -> None:
    case = _seed_case(connection)
    first = _insert(connection, case)
    statements = {
        "update": (
            "update lending.client_cif_review_confirmations "
            "set review_snapshot = '{\"tampered\":true}'::jsonb where id = %s",
            (first["id"],),
        ),
        "delete": ("delete from lending.client_cif_review_confirmations where id = %s", (first["id"],)),
        "truncate": ("truncate lending.client_cif_review_confirmations", None),
    }
    statement, params = statements[operation]
    with pytest.raises(psycopg.errors.CheckViolation, match="CIF review confirmations are immutable"):
        with connection.transaction():
            connection.execute(statement, params)
    assert _read(connection, first["id"]) == first


def test_migration_rerun_preserves_confirmation_and_guards(runtime_url) -> None:
    # Deliberately committed synthetic data remains only until the runner drops
    # this entire disposable DB. Never disable triggers to clean up evidence.
    with psycopg.connect(runtime_url, autocommit=True, row_factory=dict_row) as connection:
        case = _seed_case(connection)
        first = _insert(connection, case)
        migration_sql = MIGRATION.read_text(encoding="utf-8")
        for _ in range(2):
            connection.execute(migration_sql)
            assert _read(connection, first["id"]) == first
        with pytest.raises(psycopg.errors.CheckViolation, match="CIF review confirmations are immutable"):
            connection.execute(
                "delete from lending.client_cif_review_confirmations where id = %s",
                (first["id"],),
            )
        assert _read(connection, first["id"]) == first
