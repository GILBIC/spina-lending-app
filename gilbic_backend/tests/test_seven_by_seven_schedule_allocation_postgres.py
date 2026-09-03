from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import psycopg
import pytest

from gilbic_backend.contract_schedule_registration_service import (
    register_verified_contract_schedule,
)
from gilbic_backend.seven_by_seven_schedule_allocation import (
    SevenBySevenExtraAllocationChoiceRequired,
    plan_verified_seven_by_seven_scheduled_payment,
    store_verified_seven_by_seven_scheduled_payment_allocations,
)
from gilbic_backend.seven_by_seven_signed_schedule import (
    generate_signed_seven_by_seven_schedule,
)


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)


def _insert_receipt(
    connection: psycopg.Connection,
    *,
    loan_id,
    client_id,
    actor_id,
    device_id,
    collection_date: date,
    amount: Decimal,
    device_sequence: int,
    previous_balance: Decimal,
    official_balance: Decimal,
):
    transaction_id = uuid4()
    accepted_at = datetime.now(timezone.utc)
    connection.execute(
        """
        insert into lending.collection_transactions (
            id,
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
            accepted_at,
            device_sequence,
            note,
            route_revision,
            previous_balance,
            official_balance,
            pass_count_after,
            receipt_number,
            details
        ) values (
            %s, %s, %s, %s, %s, %s, %s, %s,
            'payment', %s, %s, %s, %s, '', %s, %s, %s, 0, %s, '{}'::jsonb
        )
        """,
        (
            transaction_id,
            uuid4(),
            loan_id,
            client_id,
            actor_id,
            device_id,
            loan_id,
            collection_date,
            amount,
            accepted_at,
            accepted_at,
            device_sequence,
            f"loan:{loan_id}:test:{device_sequence}",
            previous_balance,
            official_balance,
            f"X7-SA-{uuid4().hex[:12]}",
        ),
    )
    return transaction_id


def test_verified_7x7_same_day_receipts_accumulate_on_one_signed_row() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    release_date = date(2098, 2, 1)
    first_due_date = release_date + timedelta(days=1)

    with psycopg.connect(DATABASE_URL) as connection:
        if connection.execute(
            "select to_regclass('lending.loan_contract_installments_operational')"
        ).fetchone()[0] is None:
            pytest.skip("Operational contract schedule schema is not installed")

        try:
            actor_id = connection.execute(
                """
                insert into core.users (username, full_name, status)
                values (%s, %s, 'active') returning id
                """,
                (f"x7-sa-{suffix}", f"7x7 Schedule Allocation {suffix}"),
            ).fetchone()[0]
            device_id = connection.execute(
                """
                insert into core.devices (
                    user_id, device_identifier_hash, platform, app_version, status
                ) values (%s, %s, 'android', 'x7-schedule-allocation-test', 'active')
                returning id
                """,
                (actor_id, f"hash-{suffix}"),
            ).fetchone()[0]
            loan_type_id = connection.execute(
                """
                insert into lending.loan_types (
                    code, name, term_days, calculation_mode, daily_interest_per_1000
                ) values (%s, %s, 120, 'seven_by_seven', 7.00)
                returning id
                """,
                (f"X7SA-{suffix}", f"7x7 Schedule Allocation {suffix}"),
            ).fetchone()[0]
            client_id = connection.execute(
                """
                insert into lending.clients (client_code, full_name, area, status)
                values (%s, %s, 'Cardona', 'active') returning id
                """,
                (f"X7SAC-{suffix}", f"7x7 Allocation Client {suffix}"),
            ).fetchone()[0]
            loan_id = connection.execute(
                """
                insert into lending.loans (
                    loan_number, client_id, loan_type_id, principal, daily_amount,
                    date_released, due_date, status, created_by_user_id
                ) values (%s, %s, %s, 3000.00, 21.00, %s, %s, 'active', %s)
                returning id
                """,
                (
                    f"X7SAL-{suffix}",
                    client_id,
                    loan_type_id,
                    release_date,
                    release_date + timedelta(days=120),
                    actor_id,
                ),
            ).fetchone()[0]

            rows = generate_signed_seven_by_seven_schedule(
                original_principal=Decimal("3000.00"),
                agreed_daily_payment=Decimal("50.00"),
                daily_interest_per_1000=Decimal("7.00"),
                first_due_date=first_due_date,
            )
            with connection.cursor() as cursor:
                schedule_id = register_verified_contract_schedule(
                    cursor,
                    loan_id=loan_id,
                    payment_frequency="daily",
                    contract_reference=f"SIGNED-X7-SA-{suffix}",
                    contract_signed_date=release_date,
                    effective_from=release_date,
                    grace_days=0,
                    installments=rows,
                    evidence_basis="signed_contract",
                    evidence_reference=f"SIGNED-X7-SA-DOC-{suffix}",
                    verification_note="Borrower accepted the agreed 50 peso daily payment.",
                    verified_by_user_id=actor_id,
                    confirmed=True,
                )

            with connection.cursor() as cursor:
                first_plan = plan_verified_seven_by_seven_scheduled_payment(
                    cursor,
                    loan_id=loan_id,
                    collection_date=first_due_date,
                    transaction_amount=Decimal("20.00"),
                )
            assert len(first_plan) == 1
            assert first_plan[0].amount_applied == Decimal("20.00")

            first_tx = _insert_receipt(
                connection,
                loan_id=loan_id,
                client_id=client_id,
                actor_id=actor_id,
                device_id=device_id,
                collection_date=first_due_date,
                amount=Decimal("20.00"),
                device_sequence=1,
                previous_balance=Decimal("3000.00"),
                official_balance=Decimal("3000.00"),
            )
            with connection.cursor() as cursor:
                store_verified_seven_by_seven_scheduled_payment_allocations(
                    cursor,
                    transaction_id=first_tx,
                    actor_user_id=actor_id,
                    instructions=first_plan,
                )

            with connection.cursor() as cursor:
                second_plan = plan_verified_seven_by_seven_scheduled_payment(
                    cursor,
                    loan_id=loan_id,
                    collection_date=first_due_date,
                    transaction_amount=Decimal("30.00"),
                )
            assert len(second_plan) == 1
            assert second_plan[0].installment_id == first_plan[0].installment_id
            assert second_plan[0].amount_applied == Decimal("30.00")

            second_tx = _insert_receipt(
                connection,
                loan_id=loan_id,
                client_id=client_id,
                actor_id=actor_id,
                device_id=device_id,
                collection_date=first_due_date,
                amount=Decimal("30.00"),
                device_sequence=2,
                previous_balance=Decimal("3000.00"),
                official_balance=Decimal("2992.00"),
            )
            with connection.cursor() as cursor:
                store_verified_seven_by_seven_scheduled_payment_allocations(
                    cursor,
                    transaction_id=second_tx,
                    actor_user_id=actor_id,
                    instructions=second_plan,
                )

            allocated = connection.execute(
                """
                select
                    installment.installment_number,
                    installment.contractual_amount,
                    sum(allocation.amount_applied)::numeric(18,2)
                from lending.loan_contract_installments installment
                join lending.loan_installment_payment_allocations allocation
                  on allocation.installment_id = installment.id
                where installment.schedule_id = %s
                  and installment.installment_number = 1
                group by installment.installment_number, installment.contractual_amount
                """,
                (schedule_id,),
            ).fetchone()
            assert allocated == (1, Decimal("50.00"), Decimal("50.00"))

            with connection.cursor() as cursor:
                with pytest.raises(SevenBySevenExtraAllocationChoiceRequired):
                    plan_verified_seven_by_seven_scheduled_payment(
                        cursor,
                        loan_id=loan_id,
                        collection_date=first_due_date,
                        transaction_amount=Decimal("1.00"),
                    )
        finally:
            connection.rollback()
