from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import psycopg
import pytest

from gilbic_backend.management_no_collection_repository import (
    PostgresManagementNoCollectionRepository,
)


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


def _seed_pre_0110_no_collection_adjustment(case) -> object:
    """Insert one valid legacy adjustment row using the pre-0110 column shape."""
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        schedule_id = connection.execute(
            """
            select id
            from lending.loan_contract_schedules
            where loan_id = %s
              and status = 'active'
            """,
            (case.loan_id,),
        ).fetchone()[0]
        return connection.execute(
            """
            insert into lending.loan_schedule_adjustments (
                loan_id,
                schedule_id,
                adjustment_type,
                no_collection_date,
                reason,
                expected_operational_version,
                resulting_operational_version,
                actor_user_id
            )
            values (%s, %s, 'no_collection', %s, %s, 0, 1, %s)
            returning id
            """,
            (
                case.loan_id,
                schedule_id,
                case.payment_start,
                "Pre-0110 disposable No Collection audit row.",
                case.collector_id,
            ),
        ).fetchone()[0]


def test_0110_backfills_existing_no_collection_event_date_without_losing_audit() -> None:
    assert DATABASE_URL is not None
    case = cases._setup_case()
    adjustment_id = _seed_pre_0110_no_collection_adjustment(case)

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


def test_management_no_collection_reversal_writes_event_date_after_0110() -> None:
    assert DATABASE_URL is not None
    case = cases._setup_case()
    _ensure_0110_installed()
    adjustment_id = cases._declare_no_collection(case)

    reversed_record = PostgresManagementNoCollectionRepository().reverse(
        actor_user_id=case.collector_id,
        adjustment_id=adjustment_id,
        expected_operational_version=1,
        reason="Disposable reversal after 0110.",
    )

    with psycopg.connect(DATABASE_URL) as connection:
        row = connection.execute(
            """
            select adjustment_type, no_collection_date, event_date, reverses_adjustment_id
            from lending.loan_schedule_adjustments
            where id = %s
            """,
            (reversed_record.adjustment_id,),
        ).fetchone()
    assert row == (
        "reversal",
        case.payment_start,
        case.payment_start,
        adjustment_id,
    )


def test_7x7_voluntary_completion_writes_event_date_after_0110() -> None:
    assert DATABASE_URL is not None
    _ensure_0110_installed()

    cases.test_partial_then_same_day_full_nc_voluntary_completion_is_atomic_and_idempotent()

    with psycopg.connect(DATABASE_URL) as connection:
        rows = connection.execute(
            """
            select no_collection_date, event_date
            from lending.loan_schedule_adjustments
            where adjustment_type = 'voluntary_completion'
            order by created_at
            """
        ).fetchall()
    assert rows
    assert all(event_date == no_collection_date for no_collection_date, event_date in rows)
