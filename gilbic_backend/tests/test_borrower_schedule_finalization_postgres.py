from __future__ import annotations

import importlib.util
import os
from datetime import timedelta
from pathlib import Path

import psycopg
import pytest

from gilbic_backend.borrower_schedule_finalization import (
    PostgresBorrowerScheduleFinalizer,
)


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

TEST_DIR = Path(__file__).resolve().parent
SOURCE_PATH = TEST_DIR / "test_seven_by_seven_no_collection_voluntary_postgres.py"
_spec = importlib.util.spec_from_file_location("borrower_schedule_finalization_cases", SOURCE_PATH)
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


def test_elapsed_unresolved_installment_is_finalized_before_today() -> None:
    assert DATABASE_URL is not None
    case = cases._setup_case()
    _ensure_0110_installed()
    business_date = case.payment_start + timedelta(days=1)

    records = PostgresBorrowerScheduleFinalizer().finalize_elapsed_for_loans(
        actor_user_id=case.collector_id,
        loan_ids=(case.loan_id,),
        business_date=business_date,
    )

    assert len(records) == 1
    record = records[0]
    assert record.adjustment_type == "borrower_shortfall"
    assert record.event_date == case.payment_start
    assert record.active_borrower_extension_slots_before == 0
    assert record.active_borrower_extension_slots_after == 1

    with psycopg.connect(DATABASE_URL) as connection:
        adjustment_count = connection.execute(
            """
            select count(*)
            from lending.loan_schedule_adjustments
            where loan_id = %s
              and adjustment_type = 'borrower_shortfall'
              and event_date = %s
            """,
            (case.loan_id, case.payment_start),
        ).fetchone()[0]
        assert adjustment_count == 1

        operational_state = connection.execute(
            """
            select operational_version, active_borrower_extension_slots
            from lending.loan_schedule_operational_state
            where schedule_id = %s
            """,
            (record.schedule_id,),
        ).fetchone()
        assert operational_state == (1, 1)

        first_effective_due_date = connection.execute(
            """
            select effective_due_date
            from lending.loan_contract_installments_operational
            where schedule_id = %s
            order by installment_number, id
            limit 1
            """,
            (record.schedule_id,),
        ).fetchone()[0]
        assert first_effective_due_date == business_date
