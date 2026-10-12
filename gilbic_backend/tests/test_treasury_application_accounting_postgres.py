"""Application accounting consumes retained borrower funds without new cash."""

import os
from decimal import Decimal
from pathlib import Path

import pytest
from test_treasury_receipt_accounting_postgres import install, seed
from treasury_application_accounting_test_support import create_application_source
from treasury_test_support import connect

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0149_add_treasury_application_accounting.sql"
)


def keep_current_application_schema(conn):
    """A latest-schema verifier must exercise158, not silently reinstall149."""
    current = int(os.getenv("SPINA_CURRENT_SCHEMA_THROUGH", "0")) >= 158
    if current:
        row = conn.execute(
            "SELECT to_regprocedure('accounting.treasury_regular_application_coordinates(uuid)') IS NOT NULL "
            "AND position('treasury_regular_application_coordinates' IN pg_get_functiondef("
            "'accounting.treasury_application_coordinates(uuid)'::regprocedure))>0 AS dispatched"
        ).fetchone()
        assert row["dispatched"], "Latest-schema tests require the intact158 dispatcher"
    return current


@pytest.fixture
def application_db():
    if not os.getenv("GILBIC_TEST_DATABASE_URL"):
        pytest.skip("Explicit disposable PostgreSQL URL required")
    assert os.getenv("SPINA_ALLOW_DISPOSABLE_DATABASE") == "1"
    with connect() as conn:
        try:
            current = keep_current_application_schema(conn)
            fixture = seed(conn, install_migrations=not current)
            if not current and MIGRATION.exists():
                install(conn, MIGRATION)
            yield fixture
        finally:
            conn.rollback()


def test_application_adapter_requires_explicit_review_without_seeded_postings(
    application_db,
):
    connection = application_db["conn"]
    assert (
        connection.execute(
            "SELECT to_regclass('accounting.treasury_application_preparations') AS relation"
        ).fetchone()["relation"]
        is not None
    ), "Application accounting migration is missing"
    assert (
        connection.execute(
            "SELECT count(*) AS n FROM accounting.treasury_application_postings"
        ).fetchone()["n"]
        == 0
    )


def test_application_consumes_exact_existing_eir_allocation_without_cash(
    application_db, monkeypatch
):
    f = create_application_source(application_db, monkeypatch)
    conn = f["conn"]
    source = conn.execute(
        "SELECT accounting.treasury_application_coordinates(%s) AS source",
        (f["application"],),
    ).fetchone()["source"]
    lines = source["lines"]
    assert not {line["account_code"] for line in lines}.intersection(
        {"1010", "1020", "1030"}
    )
    assert next(
        Decimal(line["debit"]) for line in lines if line["account_code"] == "2200"
    ) == Decimal("50.00")
    assert sum(Decimal(line["debit"]) for line in lines) == sum(
        Decimal(line["credit"]) for line in lines
    )
    assert (
        next(
            Decimal(line["credit"]) for line in lines if line["account_code"] == "4010"
        )
        == f["measurement"]["eir_interest_accrual"]
    )
