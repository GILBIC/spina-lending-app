from __future__ import annotations

import importlib.util
import os
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from gilbic_backend.borrower_schedule_adjustment_repository import (
    PostgresBorrowerScheduleAdjustmentRepository,
)
from gilbic_backend.client_loan_repository import PostgresClientLoanRepository


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

TEST_DIR = Path(__file__).resolve().parent
SOURCE_PATH = TEST_DIR / "test_combined_collection_renewal_workflow_postgres.py"
_spec = importlib.util.spec_from_file_location("client_schedule_cases", SOURCE_PATH)
assert _spec is not None and _spec.loader is not None
cases = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cases)

X7_SOURCE_PATH = TEST_DIR / "test_seven_by_seven_mobile_collection_postgres.py"
_x7_spec = importlib.util.spec_from_file_location("client_x7_schedule_cases", X7_SOURCE_PATH)
assert _x7_spec is not None and _x7_spec.loader is not None
x7_cases = importlib.util.module_from_spec(_x7_spec)
_x7_spec.loader.exec_module(x7_cases)

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
              and table_name = 'loan_schedule_operational_state'
              and column_name = 'active_borrower_extension_slots'
            """
        ).fetchone()[0]
        if installed == 0:
            connection.execute(_migration_body(SQL_0110))


def _link_client_user(*, client_id, label: str):
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    with psycopg.connect(DATABASE_URL) as connection:
        client_user_id = connection.execute(
            """
            insert into core.users (username, full_name, status)
            values (%s, %s, 'active')
            returning id
            """,
            (f"client-schedule-{label}-{suffix}", f"Client Schedule {label} {suffix}"),
        ).fetchone()[0]
        connection.execute(
            """
            update lending.clients
            set user_id = %s
            where id = %s
            """,
            (client_user_id, client_id),
        )
    return client_user_id


def test_linked_client_reads_persisted_shifted_regular_schedule() -> None:
    assert DATABASE_URL is not None
    _ensure_0110_installed()
    case = cases._setup_combined_case(
        verified_regular_schedule=True,
        regular_first_due=date(2097, 8, 2),
    )
    client_user_id = _link_client_user(client_id=case.client_id, label="regular")

    shortfall = PostgresBorrowerScheduleAdjustmentRepository().record_shortfall(
        actor_user_id=case.collector_id,
        loan_id=case.regular_loan_id,
        event_date=date(2097, 8, 2),
        expected_operational_version=0,
    )
    assert shortfall.active_borrower_extension_slots_after == 1

    schedule = PostgresClientLoanRepository().get_schedule_for_user(
        user_id=client_user_id,
        loan_id=case.regular_loan_id,
        as_of_date=date(2097, 8, 3),
    )

    installment_rows = [row for row in schedule.rows if row.kind == "installment"]
    assert schedule.client_id == case.client_id
    assert schedule.loan_id == case.regular_loan_id
    assert schedule.loan_type == "Regular"
    assert schedule.calculation_mode != "seven_by_seven"
    assert schedule.schedule_extension_slots == 1
    assert schedule.past_due_count == 0
    assert schedule.base_maturity == date(2097, 11, 9)
    assert schedule.updated_maturity == date(2097, 11, 10)
    assert schedule.maturity_projection_status == "extended"
    assert [
        (row.schedule_date, row.status, row.amount)
        for row in installment_rows[:3]
    ] == [
        (date(2097, 8, 3), "Due Today", cases.Decimal("50.00")),
        (date(2097, 8, 4), "Scheduled", cases.Decimal("50.00")),
        (date(2097, 8, 5), "Scheduled", cases.Decimal("50.00")),
    ]


def test_linked_client_reads_persisted_shifted_7x7_schedule_separately() -> None:
    assert DATABASE_URL is not None
    _ensure_0110_installed()
    case = x7_cases._setup_case(principal="5000.00")
    x7_cases._register_verified_schedule(case)
    client_user_id = _link_client_user(client_id=case.client_id, label="x7")

    shortfall = PostgresBorrowerScheduleAdjustmentRepository().record_shortfall(
        actor_user_id=case.collector_id,
        loan_id=case.loan_id,
        event_date=case.payment_start,
        expected_operational_version=0,
    )
    assert shortfall.active_borrower_extension_slots_after == 1

    schedule = PostgresClientLoanRepository().get_schedule_for_user(
        user_id=client_user_id,
        loan_id=case.loan_id,
        as_of_date=case.payment_start + timedelta(days=1),
    )

    installment_rows = [row for row in schedule.rows if row.kind == "installment"]
    assert schedule.client_id == case.client_id
    assert schedule.loan_id == case.loan_id
    assert schedule.calculation_mode == "seven_by_seven"
    assert "7x7" in schedule.loan_type
    assert schedule.schedule_extension_slots == 1
    assert schedule.past_due_count == 0
    assert schedule.base_maturity is not None
    assert schedule.updated_maturity == schedule.base_maturity + timedelta(days=1)
    assert schedule.maturity_projection_status == "extended"
    assert [
        (row.schedule_date, row.status, row.amount)
        for row in installment_rows[:3]
    ] == [
        (case.payment_start + timedelta(days=1), "Due Today", x7_cases.Decimal("50.00")),
        (case.payment_start + timedelta(days=2), "Scheduled", x7_cases.Decimal("50.00")),
        (case.payment_start + timedelta(days=3), "Scheduled", x7_cases.Decimal("50.00")),
    ]
