from __future__ import annotations

import importlib.util
import os
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest

from gilbic_backend.borrower_schedule_adjustment_repository import (
    BorrowerScheduleAdjustmentConflict,
    PostgresBorrowerScheduleAdjustmentRepository,
)
from gilbic_backend.concurrent_receipt_collection_posting import (
    ConcurrentReceiptSafeCollectionPostingBridge,
)
from spina_mobile_collections.contracts import (
    CollectionCommand,
    CollectionEntryType,
)


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

TEST_DIR = Path(__file__).resolve().parent
SOURCE_PATH = TEST_DIR / "test_combined_collection_renewal_workflow_postgres.py"
_spec = importlib.util.spec_from_file_location("regular_catchup_cases", SOURCE_PATH)
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


def _setup_regular_with_one_extension():
    assert DATABASE_URL is not None
    _ensure_0110_installed()
    case = cases._setup_combined_case(
        verified_regular_schedule=True,
        regular_first_due=date(2097, 8, 1),
    )
    shortfall = PostgresBorrowerScheduleAdjustmentRepository().record_shortfall(
        actor_user_id=case.collector_id,
        loan_id=case.regular_loan_id,
        event_date=date(2097, 8, 1),
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
                (case.regular_loan_id,),
            ).fetchone()[0]
        )
    return case, shortfall, route_state_version


def _payment_command(
    case,
    *,
    amount: str,
    route_state_version: int,
    key: UUID | None = None,
) -> CollectionCommand:
    return CollectionCommand(
        idempotency_key=key or uuid4(),
        route_entry_id=str(case.regular_loan_id),
        client_id=str(case.client_id),
        loan_id=str(case.regular_loan_id),
        collection_date=date(2097, 8, 2),
        entry_type=CollectionEntryType.PAYMENT,
        amount=Decimal(amount),
        recorded_at=datetime(2097, 8, 2, 1, 0, tzinfo=UTC),
        device_id=case.installation_id,
        device_sequence=1,
        route_revision=f"loan:{case.regular_loan_id}:v{route_state_version}",
    )


def test_regular_normal_payment_catches_up_and_contracts_in_same_transaction() -> None:
    assert DATABASE_URL is not None
    case, shortfall, route_state_version = _setup_regular_with_one_extension()

    with psycopg.connect(DATABASE_URL) as connection:
        posted = ConcurrentReceiptSafeCollectionPostingBridge().post_collection(
            connection,
            case.actor,
            _payment_command(
                case,
                amount="100.00",
                route_state_version=route_state_version,
            ),
        )

    transaction_id = posted.server_transaction_id
    with psycopg.connect(DATABASE_URL) as connection:
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
            (transaction_id,),
        ).fetchall()
        state = connection.execute(
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
            (case.regular_loan_id, date(2097, 8, 2)),
        ).fetchone()[0]
        effective_dates = connection.execute(
            """
            select installment_number, effective_due_date
            from lending.loan_contract_installments_operational
            where schedule_id = %s
            order by installment_number
            limit 3
            """,
            (shortfall.schedule_id,),
        ).fetchall()
        collection_state_version = int(
            connection.execute(
                """
                select state_version
                from lending.loan_collection_state
                where loan_id = %s
                """,
                (case.regular_loan_id,),
            ).fetchone()[0]
        )

    assert allocations == [
        (1, Decimal("50.00"), "oldest_due_first"),
        (2, Decimal("50.00"), "borrower_catch_up_oldest_first"),
    ]
    assert state == (2, 0)
    assert catchup_adjustments == 1
    # Settled rows retain their reached/paid operational history. The remaining
    # unpaid schedule is what contracts: installment 3 moves Aug 4 -> Aug 3.
    assert effective_dates == [
        (1, date(2097, 8, 2)),
        (2, date(2097, 8, 3)),
        (3, date(2097, 8, 3)),
    ]
    assert collection_state_version == route_state_version + 1
    assert posted.route_revision == (
        f"loan:{case.regular_loan_id}:v{collection_state_version}"
    )


def test_regular_partial_catchup_keeps_extension_until_future_row_is_fully_paid() -> None:
    assert DATABASE_URL is not None
    case, shortfall, route_state_version = _setup_regular_with_one_extension()

    with psycopg.connect(DATABASE_URL) as connection:
        posted = ConcurrentReceiptSafeCollectionPostingBridge().post_collection(
            connection,
            case.actor,
            _payment_command(
                case,
                amount="75.00",
                route_state_version=route_state_version,
            ),
        )

    with psycopg.connect(DATABASE_URL) as connection:
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
        state = connection.execute(
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
            """,
            (case.regular_loan_id,),
        ).fetchone()[0]
        effective_dates = connection.execute(
            """
            select installment_number, effective_due_date
            from lending.loan_contract_installments_operational
            where schedule_id = %s
            order by installment_number
            limit 3
            """,
            (shortfall.schedule_id,),
        ).fetchall()

    assert allocations == [
        (1, Decimal("50.00"), "oldest_due_first"),
        (2, Decimal("25.00"), "borrower_catch_up_oldest_first"),
    ]
    assert state == (1, 1)
    assert catchup_adjustments == 0
    assert effective_dates == [
        (1, date(2097, 8, 2)),
        (2, date(2097, 8, 3)),
        (3, date(2097, 8, 4)),
    ]


def test_forced_catchup_contraction_failure_rolls_back_receipt_and_allocations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert DATABASE_URL is not None
    case, shortfall, route_state_version = _setup_regular_with_one_extension()
    payment_key = uuid4()

    def fail_catchup(*args, **kwargs):
        raise BorrowerScheduleAdjustmentConflict(
            "Forced catch-up contraction failure for atomic rollback proof."
        )

    monkeypatch.setattr(
        PostgresBorrowerScheduleAdjustmentRepository,
        "record_catchup_in_transaction",
        fail_catchup,
    )

    with pytest.raises(BorrowerScheduleAdjustmentConflict):
        with psycopg.connect(DATABASE_URL) as connection:
            ConcurrentReceiptSafeCollectionPostingBridge().post_collection(
                connection,
                case.actor,
                _payment_command(
                    case,
                    amount="100.00",
                    route_state_version=route_state_version,
                    key=payment_key,
                ),
            )

    with psycopg.connect(DATABASE_URL) as connection:
        receipt_count = connection.execute(
            """
            select count(*)
            from lending.collection_transactions
            where idempotency_key = %s
            """,
            (payment_key,),
        ).fetchone()[0]
        allocation_count = connection.execute(
            """
            select count(*)
            from lending.loan_installment_payment_allocations allocation
            join lending.collection_transactions transaction
              on transaction.id = allocation.transaction_id
            where transaction.idempotency_key = %s
            """,
            (payment_key,),
        ).fetchone()[0]
        state = connection.execute(
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
            """,
            (case.regular_loan_id,),
        ).fetchone()[0]
        collection_state_version = int(
            connection.execute(
                """
                select state_version
                from lending.loan_collection_state
                where loan_id = %s
                """,
                (case.regular_loan_id,),
            ).fetchone()[0]
        )

    assert receipt_count == 0
    assert allocation_count == 0
    assert state == (1, 1)
    assert catchup_adjustments == 0
    assert collection_state_version == route_state_version
