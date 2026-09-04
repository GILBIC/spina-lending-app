from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import psycopg
import pytest


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

TEST_DIR = Path(__file__).resolve().parent
SOURCE_PATH = TEST_DIR / "test_seven_by_seven_no_collection_voluntary_postgres.py"
_spec = importlib.util.spec_from_file_location("borrower_schedule_upgrade_cases", SOURCE_PATH)
assert _spec is not None and _spec.loader is not None
cases = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cases)

SQL_0110 = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0110_add_borrower_schedule_adjustments.sql"
).read_text(encoding="utf-8")


def _migration_body(source: str) -> str:
    stripped = source.strip()
    assert stripped.startswith("BEGIN;")
    assert stripped.endswith("COMMIT;")
    return stripped[len("BEGIN;") : -len("COMMIT;")].strip()


def _ensure_0110_installed() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        installed = connection.execute(
            """
            select count(*)
            from information_schema.columns
            where table_schema = 'lending'
              and table_name = 'loan_schedule_adjustments'
              and column_name = 'event_date'
            """
        ).fetchone()[0]
        if installed == 0:
            connection.execute(_migration_body(SQL_0110))


def test_0110_backfills_existing_no_collection_event_date_without_losing_audit() -> None:
    assert DATABASE_URL is not None
    case = cases._setup_case()
    adjustment_id = cases._declare_no_collection(case)

    with psycopg.connect(DATABASE_URL) as connection:
        before = connection.execute(
            """
            select no_collection_date, adjustment_type
            from lending.loan_schedule_adjustments
            where id = %s
            """,
            (adjustment_id,),
        ).fetchone()
        assert before is not None
        assert before[1] == "no_collection"
        assert connection.execute(
            """
            select count(*)
            from information_schema.columns
            where table_schema = 'lending'
              and table_name = 'loan_schedule_adjustments'
              and column_name = 'event_date'
            """
        ).fetchone()[0] == 0

        connection.execute(_migration_body(SQL_0110))

        after = connection.execute(
            """
            select no_collection_date, event_date, adjustment_type
            from lending.loan_schedule_adjustments
            where id = %s
            """,
            (adjustment_id,),
        ).fetchone()
        assert after is not None
        assert after[0] == before[0]
        assert after[1] == before[0]
        assert after[2] == "no_collection"
        assert connection.execute(
            "select count(*) from lending.loan_schedule_adjustments where id = %s",
            (adjustment_id,),
        ).fetchone()[0] == 1


def test_management_no_collection_declaration_writes_event_date_after_0110() -> None:
    assert DATABASE_URL is not None
    case = cases._setup_case()
    _ensure_0110_installed()

    adjustment_id = cases._declare_no_collection(case)

    with psycopg.connect(DATABASE_URL) as connection:
        row = connection.execute(
            """
            select adjustment_type, no_collection_date, event_date
            from lending.loan_schedule_adjustments
            where id = %s
            """,
            (adjustment_id,),
        ).fetchone()
    assert row == ("no_collection", case.payment_start, case.payment_start)
