from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from gilbic_backend.contract_schedule_engine import generate_contract_installments
from gilbic_backend.contract_schedule_service import (
    ContractPaymentAllocationConflict,
    ContractScheduleConflict,
    allocate_collection_transaction,
    store_contract_schedule,
)


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

SQL_0034 = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0034_add_contractual_schedule_dpd_foundation.sql"
).read_text(encoding="utf-8")


def _transaction_body(sql: str) -> str:
    body = sql.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _create_fixture(connection, suffix: str):
    actor_id = connection.execute(
        """
        insert into core.users (username, full_name, status)
        values (%s, %s, 'active')
        returning id
        """,
        (f"contract-auto-{suffix}", f"Contract Auto {suffix}"),
    ).fetchone()[0]
    device_id = connection.execute(
        """
        insert into core.devices (
            user_id,
            device_identifier_hash,
            platform,
            status
        )
        values (%s, %s, 'desktop', 'active')
        returning id
        """,
        (actor_id, f"contract-auto-device-{suffix}"),
    ).fetchone()[0]
    loan_type_id = connection.execute(
        """
        insert into lending.loan_types (
            code,
            name,
            term_days,
            calculation_mode,
            daily_interest_per_1000
        )
        values (%s, %s, 120, 'custom', 0)
        returning id
        """,
        (f"CA-{suffix}", f"Contract Automation {suffix}"),
    ).fetchone()[0]
    client_id = connection.execute(
        """
        insert into lending.clients (client_code, full_name, status)
        values (%s, %s, 'active')
        returning id
        """,
        (f"CA-C-{suffix}", f"Contract Client {suffix}"),
    ).fetchone()[0]
    loan_id = connection.execute(
        """
        insert into lending.loans (
            loan_number,
            client_id,
            loan_type_id,
            principal,
            daily_amount,
            date_released,
            due_date,
            status
        )
        values (%s, %s, %s, 270.00, 90.00, current_date, current_date + 2, 'active')
        returning id
        """,
        (f"CA-L-{suffix}", client_id, loan_type_id),
    ).fetchone()[0]
    return actor_id, device_id, client_id, loan_id


def _create_payment(
    connection,
    *,
    suffix: str,
    loan_id,
    client_id,
    actor_id,
    device_id,
    sequence: int,
    amount: str,
):
    return connection.execute(
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
            note,
            previous_balance,
            official_balance,
            pass_count_after,
            advance_until_after,
            receipt_number,
            details
        )
        values (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            current_date,
            'payment',
            %s,
            now(),
            %s,
            '',
            270.00,
            270.00,
            0,
            null,
            %s,
            '{}'::jsonb
        )
        returning id
        """,
        (
            uuid4(),
            loan_id,
            client_id,
            actor_id,
            device_id,
            loan_id,
            amount,
            sequence,
            f"CA-R-{suffix}-{sequence}",
        ),
    ).fetchone()[0]


def test_stage5e42_generates_stores_and_auto_allocates_without_touching_live_data() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:8]

    with psycopg.connect(DATABASE_URL) as connection:
        if connection.execute(
            "select to_regclass('lending.collection_transactions')"
        ).fetchone()[0] is None:
            pytest.skip("Collection schema is not installed in the test database")

        if connection.execute(
            """
            select 1
            from information_schema.columns
            where table_schema = 'lending'
              and table_name = 'collection_transactions'
              and column_name = 'is_voided'
            """
        ).fetchone() is None:
            pytest.skip("Collection void support is not installed in the test database")

        try:
            connection.execute(_transaction_body(SQL_0034))
            actor_id, device_id, client_id, loan_id = _create_fixture(connection, suffix)

            installments = generate_contract_installments(
                payment_frequency="daily",
                contractual_total=Decimal("270.00"),
                first_due_date=date.today(),
                installment_count=3,
                regular_installment_amount=Decimal("90.00"),
            )

            with connection.cursor() as cursor:
                schedule_id = store_contract_schedule(
                    cursor,
                    loan_id=loan_id,
                    payment_frequency="daily",
                    contract_reference=f"TEST-CONTRACT-{suffix}",
                    contract_signed_date=date.today(),
                    effective_from=date.today(),
                    grace_days=0,
                    installments=installments,
                    created_by_user_id=actor_id,
                )

                with pytest.raises(ContractScheduleConflict):
                    store_contract_schedule(
                        cursor,
                        loan_id=loan_id,
                        payment_frequency="daily",
                        contract_reference=f"DUPLICATE-{suffix}",
                        contract_signed_date=date.today(),
                        effective_from=date.today(),
                        grace_days=0,
                        installments=installments,
                        created_by_user_id=actor_id,
                    )

            stored = connection.execute(
                """
                select payment_frequency, contract_reference, schedule_version, status
                from lending.loan_contract_schedules
                where id = %s
                """,
                (schedule_id,),
            ).fetchone()
            assert stored == ("daily", f"TEST-CONTRACT-{suffix}", 1, "active")

            first_tx = _create_payment(
                connection,
                suffix=suffix,
                loan_id=loan_id,
                client_id=client_id,
                actor_id=actor_id,
                device_id=device_id,
                sequence=1,
                amount="180.00",
            )
            with connection.cursor() as cursor:
                first_plan = allocate_collection_transaction(
                    cursor,
                    transaction_id=first_tx,
                )
            assert [row.installment_number for row in first_plan] == [1, 2]
            assert [row.amount_applied for row in first_plan] == [
                Decimal("90.00"),
                Decimal("90.00"),
            ]

            # The next payment is made today even though today's contractual
            # installment is already covered. It must move to installment 3.
            second_tx = _create_payment(
                connection,
                suffix=suffix,
                loan_id=loan_id,
                client_id=client_id,
                actor_id=actor_id,
                device_id=device_id,
                sequence=2,
                amount="90.00",
            )
            with connection.cursor() as cursor:
                second_plan = allocate_collection_transaction(
                    cursor,
                    transaction_id=second_tx,
                )
                repeated_plan = allocate_collection_transaction(
                    cursor,
                    transaction_id=second_tx,
                )
            assert [row.installment_number for row in second_plan] == [3]
            assert repeated_plan == second_plan

            allocation_count = connection.execute(
                """
                select count(*), sum(amount_applied)
                from lending.loan_installment_payment_allocations
                where transaction_id in (%s, %s)
                """,
                (first_tx, second_tx),
            ).fetchone()
            assert allocation_count == (3, Decimal("270.00"))

            assessment = connection.execute(
                """
                select
                    dpd_data_status,
                    due_unpaid_amount,
                    days_past_due,
                    thirty_day_sicr_backstop_reached,
                    ninety_day_default_backstop_reached,
                    automatic_default_label_written,
                    ecl_included,
                    ecl_amount,
                    ready_to_post
                from accounting.loan_contract_dpd_assessment
                where loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert assessment == (
                "ready",
                Decimal("0.00"),
                0,
                False,
                False,
                False,
                False,
                None,
                False,
            )

            # An extra payment beyond the signed contractual schedule is not
            # silently accepted by the allocator.
            extra_tx = _create_payment(
                connection,
                suffix=suffix,
                loan_id=loan_id,
                client_id=client_id,
                actor_id=actor_id,
                device_id=device_id,
                sequence=3,
                amount="10.00",
            )
            with connection.cursor() as cursor:
                with pytest.raises(ContractPaymentAllocationConflict):
                    allocate_collection_transaction(
                        cursor,
                        transaction_id=extra_tx,
                    )
        finally:
            # All rows, schedules, and allocations in this test are synthetic.
            connection.rollback()
