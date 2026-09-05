from __future__ import annotations

import importlib.util
import os
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from gilbic_backend.borrower_schedule_adjustment_repository import (
    PostgresBorrowerScheduleAdjustmentRepository,
)


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

TEST_DIR = Path(__file__).resolve().parent
SOURCE_PATH = TEST_DIR / "test_seven_by_seven_no_collection_voluntary_postgres.py"
_spec = importlib.util.spec_from_file_location("borrower_schedule_repository_cases", SOURCE_PATH)
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


def test_shortfall_persists_all_shifted_rows_version_and_slot_atomically() -> None:
    assert DATABASE_URL is not None
    case = cases._setup_case()
    _ensure_0110_installed()

    with psycopg.connect(DATABASE_URL) as connection:
        schedule = connection.execute(
            """
            select id, payment_frequency
            from lending.loan_contract_schedules
            where loan_id = %s
              and status = 'active'
            """,
            (case.loan_id,),
        ).fetchone()
        assert schedule is not None
        schedule_id = schedule[0]
        contractual_before = connection.execute(
            """
            select id, installment_number, due_date, contractual_amount
            from lending.loan_contract_installments
            where schedule_id = %s
            order by installment_number, id
            """,
            (schedule_id,),
        ).fetchall()
        collection_state_before = connection.execute(
            "select state_version from lending.loan_collection_state where loan_id = %s",
            (case.loan_id,),
        ).fetchone()[0]

    record = PostgresBorrowerScheduleAdjustmentRepository().record_shortfall(
        actor_user_id=case.collector_id,
        loan_id=case.loan_id,
        event_date=case.payment_start,
        expected_operational_version=0,
    )

    assert record.adjustment_type == "borrower_shortfall"
    assert record.event_date == case.payment_start
    assert record.expected_operational_version == 0
    assert record.resulting_operational_version == 1
    assert record.active_borrower_extension_slots_before == 0
    assert record.active_borrower_extension_slots_after == 1
    assert len(record.shifts) == len(contractual_before)

    with psycopg.connect(DATABASE_URL) as connection:
        adjustment = connection.execute(
            """
            select
                adjustment_type,
                no_collection_date,
                event_date,
                expected_operational_version,
                resulting_operational_version
            from lending.loan_schedule_adjustments
            where id = %s
            """,
            (record.adjustment_id,),
        ).fetchone()
        assert adjustment == (
            "borrower_shortfall",
            None,
            case.payment_start,
            0,
            1,
        )

        state = connection.execute(
            """
            select operational_version, active_borrower_extension_slots
            from lending.loan_schedule_operational_state
            where schedule_id = %s
            """,
            (schedule_id,),
        ).fetchone()
        assert state == (1, 1)

        items = connection.execute(
            """
            select
                installment_id,
                installment_number,
                contractual_due_date,
                prior_effective_due_date,
                new_effective_due_date
            from lending.loan_schedule_adjustment_items
            where adjustment_id = %s
            order by installment_number, installment_id
            """,
            (record.adjustment_id,),
        ).fetchall()
        assert len(items) == len(contractual_before)
        assert items[0][3] == case.payment_start
        assert items[0][4] == contractual_before[1][2]
        assert all(item[4] > item[3] for item in items)

        operational = connection.execute(
            """
            select installment_id, effective_due_date, last_adjustment_id
            from lending.loan_installment_operational_dates
            where installment_id = any(%s)
            order by installment_id
            """,
            ([row[0] for row in contractual_before],),
        ).fetchall()
        assert len(operational) == len(contractual_before)
        assert all(row[2] == record.adjustment_id for row in operational)

        contractual_after = connection.execute(
            """
            select id, installment_number, due_date, contractual_amount
            from lending.loan_contract_installments
            where schedule_id = %s
            order by installment_number, id
            """,
            (schedule_id,),
        ).fetchall()
        assert contractual_after == contractual_before

        collection_state_after = connection.execute(
            "select state_version from lending.loan_collection_state where loan_id = %s",
            (case.loan_id,),
        ).fetchone()[0]
        assert collection_state_after == collection_state_before + 1


def test_catchup_persists_contraction_and_removes_one_active_extension_slot() -> None:
    assert DATABASE_URL is not None
    case = cases._setup_case()
    _ensure_0110_installed()
    repository = PostgresBorrowerScheduleAdjustmentRepository()

    shortfall = repository.record_shortfall(
        actor_user_id=case.collector_id,
        loan_id=case.loan_id,
        event_date=case.payment_start,
        expected_operational_version=0,
    )
    catchup_date = case.payment_start + timedelta(days=1)

    with psycopg.connect(DATABASE_URL) as connection:
        schedule_id = shortfall.schedule_id
        contractual_before = connection.execute(
            """
            select id, installment_number, due_date, contractual_amount
            from lending.loan_contract_installments
            where schedule_id = %s
            order by installment_number, id
            """,
            (schedule_id,),
        ).fetchall()
        assert len(contractual_before) >= 3
        first_installment_id = int(contractual_before[0][0])
        catchup_installment_id = int(contractual_before[1][0])

        effective_after_shortfall = connection.execute(
            """
            select installment_id, effective_due_date, last_adjustment_id
            from lending.loan_installment_operational_dates
            where installment_id = any(%s)
            order by installment_id
            """,
            ([row[0] for row in contractual_before],),
        ).fetchall()
        collection_state_before_catchup = connection.execute(
            "select state_version from lending.loan_collection_state where loan_id = %s",
            (case.loan_id,),
        ).fetchone()[0]

        transaction_id = connection.execute(
            """
            insert into lending.collection_transactions (
                idempotency_key,
                loan_id,
                client_id,
                collector_user_id,
                registered_device_id,
                route_entry_id,
                collection_date,
                entry_type,
                amount,
                recorded_at,
                device_sequence,
                route_revision,
                previous_balance,
                official_balance,
                pass_count_after,
                receipt_number
            ) values (
                %s, %s, %s, %s, %s, %s, %s, 'payment', 100.00,
                now(), 1, %s, 3000.00, 3000.00, 0, %s
            )
            returning id
            """,
            (
                uuid4(),
                case.loan_id,
                case.client_id,
                case.collector_id,
                case.device_record_id,
                case.loan_id,
                catchup_date,
                f"loan:{case.loan_id}:catchup-fixture",
                f"BOR-CATCH-{uuid4()}",
            ),
        ).fetchone()[0]
        connection.execute(
            """
            insert into lending.loan_installment_payment_allocations (
                installment_id,
                transaction_id,
                amount_applied,
                allocation_basis,
                allocation_reference,
                created_by_user_id
            ) values
                (%s, %s, 50.00, 'oldest_due_first', 'catchup-test-current', %s),
                (%s, %s, 50.00, 'borrower_catch_up_oldest_first', 'catchup-test-extra', %s)
            """,
            (
                first_installment_id,
                transaction_id,
                case.collector_id,
                catchup_installment_id,
                transaction_id,
                case.collector_id,
            ),
        )

    catchup = repository.record_catchup(
        actor_user_id=case.collector_id,
        loan_id=case.loan_id,
        event_date=catchup_date,
        expected_operational_version=1,
        completed_catchup_installment_ids=(catchup_installment_id,),
    )

    assert catchup.adjustment_type == "borrower_catch_up"
    assert catchup.event_date == catchup_date
    assert catchup.expected_operational_version == 1
    assert catchup.resulting_operational_version == 2
    assert catchup.active_borrower_extension_slots_before == 1
    assert catchup.active_borrower_extension_slots_after == 0
    assert len(catchup.shifts) == len(contractual_before) - 2

    with psycopg.connect(DATABASE_URL) as connection:
        adjustment = connection.execute(
            """
            select
                adjustment_type,
                no_collection_date,
                event_date,
                expected_operational_version,
                resulting_operational_version
            from lending.loan_schedule_adjustments
            where id = %s
            """,
            (catchup.adjustment_id,),
        ).fetchone()
        assert adjustment == (
            "borrower_catch_up",
            None,
            catchup_date,
            1,
            2,
        )

        state = connection.execute(
            """
            select operational_version, active_borrower_extension_slots
            from lending.loan_schedule_operational_state
            where schedule_id = %s
            """,
            (schedule_id,),
        ).fetchone()
        assert state == (2, 0)

        effective_after_catchup = connection.execute(
            """
            select installment_id, effective_due_date, last_adjustment_id
            from lending.loan_installment_operational_dates
            where installment_id = any(%s)
            order by installment_id
            """,
            ([row[0] for row in contractual_before],),
        ).fetchall()
        assert effective_after_catchup[0] == effective_after_shortfall[0]
        assert effective_after_catchup[1] == effective_after_shortfall[1]
        assert all(
            row[2] == catchup.adjustment_id
            for row in effective_after_catchup[2:]
        )
        assert effective_after_catchup[-1][1] == contractual_before[-1][2]

        contractual_after = connection.execute(
            """
            select id, installment_number, due_date, contractual_amount
            from lending.loan_contract_installments
            where schedule_id = %s
            order by installment_number, id
            """,
            (schedule_id,),
        ).fetchall()
        assert contractual_after == contractual_before

        collection_state_after_catchup = connection.execute(
            "select state_version from lending.loan_collection_state where loan_id = %s",
            (case.loan_id,),
        ).fetchone()[0]
        assert collection_state_after_catchup == collection_state_before_catchup + 1
