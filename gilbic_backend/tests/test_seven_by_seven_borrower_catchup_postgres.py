from __future__ import annotations

import importlib.util
import os
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest

from gilbic_backend.borrower_schedule_adjustment_repository import (
    PostgresBorrowerScheduleAdjustmentRepository,
)
from gilbic_backend.concurrent_receipt_collection_posting import (
    ConcurrentReceiptSafeCollectionPostingBridge,
)


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

TEST_DIR = Path(__file__).resolve().parent
SOURCE_PATH = TEST_DIR / "test_seven_by_seven_mobile_collection_postgres.py"
_spec = importlib.util.spec_from_file_location("seven_by_seven_catchup_cases", SOURCE_PATH)
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


def test_7x7_normal_catchup_keeps_interest_first_and_contracts_schedule_atomically() -> None:
    assert DATABASE_URL is not None
    _ensure_0110_installed()
    case = cases._setup_case(principal="5000.00")
    cases._register_verified_schedule(case)

    shortfall = PostgresBorrowerScheduleAdjustmentRepository().record_shortfall(
        actor_user_id=case.collector_id,
        loan_id=case.loan_id,
        event_date=case.payment_start,
        expected_operational_version=0,
    )
    assert shortfall.active_borrower_extension_slots_after == 1

    with psycopg.connect(DATABASE_URL) as connection:
        route_state_version = int(
            connection.execute(
                """
                select state_version
                from lending.loan_collection_state
                where loan_id = %s
                """,
                (case.loan_id,),
            ).fetchone()[0]
        )

    command = cases._command(
        case,
        collection_date=case.payment_start + timedelta(days=1),
        amount="100.00",
        route_version=route_state_version,
    )
    with psycopg.connect(DATABASE_URL) as connection:
        posted = ConcurrentReceiptSafeCollectionPostingBridge().post_collection(
            connection,
            case.actor,
            command,
        )

    with psycopg.connect(DATABASE_URL) as connection:
        receipt = connection.execute(
            """
            select
                amount,
                official_balance,
                details->>'seven_by_seven_fixed_daily_interest',
                details->>'seven_by_seven_gap_days',
                details->>'seven_by_seven_interest_due',
                details->>'seven_by_seven_interest_paid',
                details->>'seven_by_seven_principal_paid',
                details->>'seven_by_seven_closing_interest_arrears'
            from lending.collection_transactions
            where id = %s
            """,
            (posted.server_transaction_id,),
        ).fetchone()
        allocations = connection.execute(
            """
            select
                installment.installment_number,
                allocation.amount_applied,
                allocation.allocation_basis
            from lending.loan_installment_payment_allocations allocation
            join lending.loan_contract_installments installment
              on installment.id = allocation.installment_id
            where allocation.transaction_id = %s
            order by installment.installment_number
            """,
            (posted.server_transaction_id,),
        ).fetchall()
        schedule_state = connection.execute(
            """
            select operational_version, active_borrower_extension_slots
            from lending.loan_schedule_operational_state
            where schedule_id = %s
            """,
            (shortfall.schedule_id,),
        ).fetchone()
        catchup_adjustments = connection.execute(
            """
            select count(*)
            from lending.loan_schedule_adjustments
            where loan_id = %s
              and adjustment_type = 'borrower_catch_up'
              and event_date = %s
            """,
            (case.loan_id, case.payment_start + timedelta(days=1)),
        ).fetchone()[0]
        collection_state = connection.execute(
            """
            select remaining_balance, state_version
            from lending.loan_collection_state
            where loan_id = %s
            """,
            (case.loan_id,),
        ).fetchone()

    assert receipt == (
        Decimal("100.00"),
        Decimal("4970.00"),
        "35.00",
        "2",
        "70.00",
        "70.00",
        "30.00",
        "0.00",
    )
    assert allocations == [
        (1, Decimal("50.00"), "oldest_due_first"),
        (2, Decimal("50.00"), "borrower_catch_up_oldest_first"),
    ]
    assert schedule_state == (2, 0)
    assert catchup_adjustments == 1
    assert collection_state == (Decimal("4970.00"), route_state_version + 1)
    assert posted.route_revision == f"loan:{case.loan_id}:v{route_state_version + 1}"
