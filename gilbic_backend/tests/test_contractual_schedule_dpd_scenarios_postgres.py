from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

SQL = (
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


def _create_actor_and_device(connection, suffix: str):
    user_id = connection.execute(
        """
        INSERT INTO core.users (username, full_name, status)
        VALUES (%s, %s, 'active')
        RETURNING id
        """,
        (f"dpd-scenario-{suffix}", f"DPD Scenario Actor {suffix}"),
    ).fetchone()[0]
    device_id = connection.execute(
        """
        INSERT INTO core.devices (
            user_id,
            device_identifier_hash,
            platform,
            status
        )
        VALUES (%s, %s, 'desktop', 'active')
        RETURNING id
        """,
        (user_id, f"dpd-device-{suffix}"),
    ).fetchone()[0]
    return user_id, device_id


def _create_loan_type(connection, suffix: str):
    return connection.execute(
        """
        INSERT INTO lending.loan_types (
            code,
            name,
            term_days,
            calculation_mode,
            daily_interest_per_1000
        )
        VALUES (%s, %s, 365, 'custom', 0)
        RETURNING id
        """,
        (f"DPDS-{suffix}", f"DPD Scenario {suffix}"),
    ).fetchone()[0]


def _create_loan_with_schedule(
    connection,
    *,
    suffix: str,
    loan_type_id,
    frequency: str,
    grace_days: int,
    installments: list[tuple[int, int, str]],
):
    client_id = connection.execute(
        """
        INSERT INTO lending.clients (client_code, full_name, status)
        VALUES (%s, %s, 'active')
        RETURNING id
        """,
        (f"DPDS-C-{suffix}", f"DPD Scenario Client {suffix}"),
    ).fetchone()[0]
    loan_id = connection.execute(
        """
        INSERT INTO lending.loans (
            loan_number,
            client_id,
            loan_type_id,
            principal,
            daily_amount,
            date_released,
            due_date,
            status
        )
        VALUES (
            %s,
            %s,
            %s,
            10000.00,
            0.00,
            current_date - 180,
            current_date + 180,
            'active'
        )
        RETURNING id
        """,
        (f"DPDS-L-{suffix}", client_id, loan_type_id),
    ).fetchone()[0]
    schedule_id = connection.execute(
        """
        INSERT INTO lending.loan_contract_schedules (
            loan_id,
            schedule_version,
            payment_frequency,
            contract_reference,
            contract_signed_date,
            effective_from,
            grace_days
        )
        VALUES (
            %s,
            1,
            %s,
            %s,
            current_date - 180,
            current_date - 180,
            %s
        )
        RETURNING id
        """,
        (loan_id, frequency, f"CONTRACT-{suffix}", grace_days),
    ).fetchone()[0]

    installment_ids: list[int] = []
    for number, due_offset_days, amount in installments:
        installment_id = connection.execute(
            """
            INSERT INTO lending.loan_contract_installments (
                schedule_id,
                installment_number,
                due_date,
                contractual_amount
            )
            VALUES (%s, %s, current_date + %s, %s)
            RETURNING id
            """,
            (schedule_id, number, due_offset_days, amount),
        ).fetchone()[0]
        installment_ids.append(installment_id)

    return client_id, loan_id, schedule_id, installment_ids


def _create_collection(
    connection,
    *,
    suffix: str,
    loan_id,
    client_id,
    actor_id,
    device_id,
    device_sequence: int,
    entry_type: str,
    amount: str,
    collection_offset_days: int,
    advance_from_offset: int | None = None,
    advance_until_offset: int | None = None,
):
    if entry_type == "advance":
        advance_from_sql = "current_date + %s"
        advance_until_sql = "current_date + %s"
        advance_params = [advance_from_offset, advance_until_offset]
    else:
        advance_from_sql = "NULL"
        advance_until_sql = "NULL"
        advance_params = []

    sql = f"""
        INSERT INTO lending.collection_transactions (
            idempotency_key,
            loan_id,
            client_id,
            collector_user_id,
            registered_device_id,
            route_entry_id,
            collection_date,
            entry_type,
            amount,
            advance_from,
            advance_until,
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
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            current_date + %s,
            %s,
            %s,
            {advance_from_sql},
            {advance_until_sql},
            now(),
            %s,
            '',
            10000.00,
            10000.00,
            0,
            NULL,
            %s,
            '{{}}'::jsonb
        )
        RETURNING id
    """
    params = [
        uuid4(),
        loan_id,
        client_id,
        actor_id,
        device_id,
        loan_id,
        collection_offset_days,
        entry_type,
        amount,
        *advance_params,
        device_sequence,
        f"DPDS-R-{suffix}-{device_sequence}",
    ]
    return connection.execute(sql, params).fetchone()[0]


def _assessment(connection, loan_id):
    return connection.execute(
        """
        SELECT
            payment_frequency,
            due_unpaid_amount,
            dpd_data_status,
            days_past_due,
            thirty_day_sicr_backstop_reached,
            ninety_day_default_backstop_reached,
            automatic_default_label_written,
            ecl_amount,
            ecl_included,
            ready_to_post
        FROM accounting.loan_contract_dpd_assessment
        WHERE loan_id = %s
        """,
        (loan_id,),
    ).fetchone()


def test_stage5e41_synthetic_contract_and_payment_scenarios() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:8]

    with psycopg.connect(DATABASE_URL) as connection:
        foundation = connection.execute(
            "SELECT to_regclass('lending.collection_transactions')"
        ).fetchone()[0]
        if foundation is None:
            pytest.skip("Collection schema is not installed in the test database")

        void_column = connection.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'lending'
              AND table_name = 'collection_transactions'
              AND column_name = 'is_voided'
            """
        ).fetchone()
        if void_column is None:
            pytest.skip("Collection void support is not installed in the test database")

        try:
            connection.execute(_transaction_body(SQL))
            actor_id, device_id = _create_actor_and_device(connection, suffix)
            loan_type_id = _create_loan_type(connection, suffix)
            device_sequence = 1

            # Daily: one unpaid contractual installment five calendar days late.
            _, daily_loan, _, _ = _create_loan_with_schedule(
                connection,
                suffix=f"{suffix}-daily",
                loan_type_id=loan_type_id,
                frequency="daily",
                grace_days=0,
                installments=[(1, -5, "90.00")],
            )
            daily = _assessment(connection, daily_loan)
            assert daily[:6] == ("daily", 90, "ready", 5, False, False)

            # Weekly: 35 DPD reaches the 30-day SICR backstop but not 90 days.
            _, weekly_loan, _, _ = _create_loan_with_schedule(
                connection,
                suffix=f"{suffix}-weekly",
                loan_type_id=loan_type_id,
                frequency="weekly",
                grace_days=0,
                installments=[(1, -35, "500.00")],
            )
            weekly = _assessment(connection, weekly_loan)
            assert weekly[:6] == ("weekly", 500, "ready", 35, True, False)

            # Semi-monthly represents contracts such as 15th/30th schedules.
            _, semi_loan, _, _ = _create_loan_with_schedule(
                connection,
                suffix=f"{suffix}-semi",
                loan_type_id=loan_type_id,
                frequency="semi_monthly",
                grace_days=0,
                installments=[(1, -91, "800.00")],
            )
            semi = _assessment(connection, semi_loan)
            assert semi[:6] == ("semi_monthly", 800, "ready", 91, True, True)

            # Monthly: a future installment is not delinquent.
            _, monthly_loan, _, _ = _create_loan_with_schedule(
                connection,
                suffix=f"{suffix}-monthly",
                loan_type_id=loan_type_id,
                frequency="monthly",
                grace_days=0,
                installments=[(1, 10, "1000.00")],
            )
            monthly = _assessment(connection, monthly_loan)
            assert monthly[:6] == ("monthly", 0, "ready", 0, False, False)

            # Balloon: the single final contractual payment is still in the future.
            _, balloon_loan, _, _ = _create_loan_with_schedule(
                connection,
                suffix=f"{suffix}-balloon",
                loan_type_id=loan_type_id,
                frequency="balloon",
                grace_days=0,
                installments=[(1, 30, "10000.00")],
            )
            balloon = _assessment(connection, balloon_loan)
            assert balloon[:6] == ("balloon", 0, "ready", 0, False, False)

            # Custom contract: three grace days reduce a five-day-late due date to 2 DPD.
            _, custom_loan, _, _ = _create_loan_with_schedule(
                connection,
                suffix=f"{suffix}-custom",
                loan_type_id=loan_type_id,
                frequency="custom",
                grace_days=3,
                installments=[(1, -5, "700.00")],
            )
            custom = _assessment(connection, custom_loan)
            assert custom[:6] == ("custom", 700, "ready", 2, False, False)

            # Partial payment: remaining amount stays past due from the original due date.
            partial_client, partial_loan, _, partial_installments = _create_loan_with_schedule(
                connection,
                suffix=f"{suffix}-partial",
                loan_type_id=loan_type_id,
                frequency="weekly",
                grace_days=0,
                installments=[(1, -10, "100.00")],
            )
            partial_tx = _create_collection(
                connection,
                suffix=f"{suffix}-partial",
                loan_id=partial_loan,
                client_id=partial_client,
                actor_id=actor_id,
                device_id=device_id,
                device_sequence=device_sequence,
                entry_type="payment",
                amount="40.00",
                collection_offset_days=0,
            )
            device_sequence += 1
            connection.execute(
                """
                INSERT INTO lending.loan_installment_payment_allocations (
                    installment_id,
                    transaction_id,
                    amount_applied,
                    allocation_basis,
                    allocation_reference
                )
                VALUES (%s, %s, 40.00, 'oldest_due_first', %s)
                """,
                (partial_installments[0], partial_tx, f"TEST-{suffix}-partial"),
            )
            partial = _assessment(connection, partial_loan)
            assert partial[:6] == ("weekly", 60, "ready", 10, False, False)

            # Advance: cash already allocated to yesterday and tomorrow means no DPD today.
            advance_client, advance_loan, _, advance_installments = _create_loan_with_schedule(
                connection,
                suffix=f"{suffix}-advance",
                loan_type_id=loan_type_id,
                frequency="daily",
                grace_days=0,
                installments=[(1, -1, "90.00"), (2, 1, "90.00")],
            )
            advance_tx = _create_collection(
                connection,
                suffix=f"{suffix}-advance",
                loan_id=advance_loan,
                client_id=advance_client,
                actor_id=actor_id,
                device_id=device_id,
                device_sequence=device_sequence,
                entry_type="advance",
                amount="180.00",
                collection_offset_days=-2,
                advance_from_offset=-1,
                advance_until_offset=1,
            )
            device_sequence += 1
            for installment_id in advance_installments:
                connection.execute(
                    """
                    INSERT INTO lending.loan_installment_payment_allocations (
                        installment_id,
                        transaction_id,
                        amount_applied,
                        allocation_basis,
                        allocation_reference
                    )
                    VALUES (%s, %s, 90.00, 'exact_covered_date', %s)
                    """,
                    (installment_id, advance_tx, f"TEST-{suffix}-advance"),
                )
            advance = _assessment(connection, advance_loan)
            assert advance[:6] == ("daily", 0, "ready", 0, False, False)

            # Unallocated cash must block DPD instead of guessing how payment was applied.
            unallocated_client, unallocated_loan, _, _ = _create_loan_with_schedule(
                connection,
                suffix=f"{suffix}-unallocated",
                loan_type_id=loan_type_id,
                frequency="daily",
                grace_days=0,
                installments=[(1, -10, "100.00")],
            )
            _create_collection(
                connection,
                suffix=f"{suffix}-unallocated",
                loan_id=unallocated_loan,
                client_id=unallocated_client,
                actor_id=actor_id,
                device_id=device_id,
                device_sequence=device_sequence,
                entry_type="payment",
                amount="100.00",
                collection_offset_days=0,
            )
            device_sequence += 1
            unallocated = _assessment(connection, unallocated_loan)
            assert unallocated[0] == "daily"
            assert unallocated[2] == "payment_allocation_required"
            assert unallocated[3] is None
            assert unallocated[4] is False
            assert unallocated[5] is False

            # Every scenario remains read-only for classification, ECL, and posting.
            for row in (
                daily,
                weekly,
                semi,
                monthly,
                balloon,
                custom,
                partial,
                advance,
                unallocated,
            ):
                assert row[6] is False
                assert row[7] is None
                assert row[8] is False
                assert row[9] is False
        finally:
            connection.rollback()
