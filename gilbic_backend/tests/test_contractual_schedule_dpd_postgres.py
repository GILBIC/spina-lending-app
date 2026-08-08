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


def test_stage5e41_migration_executes_and_measures_contractual_dpd() -> None:
    assert DATABASE_URL is not None

    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        foundation = connection.execute(
            "SELECT to_regclass('lending.loans')"
        ).fetchone()[0]
        if foundation is None:
            pytest.skip("Core lending schema is not installed in the test database")

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

            loan_type_id = connection.execute(
                """
                INSERT INTO lending.loan_types (
                    code,
                    name,
                    term_days,
                    calculation_mode,
                    daily_interest_per_1000
                )
                VALUES (%s, %s, 120, 'custom', 0)
                RETURNING id
                """,
                (f"DPD-{suffix}", f"DPD Test {suffix}"),
            ).fetchone()[0]

            client_id = connection.execute(
                """
                INSERT INTO lending.clients (client_code, full_name, status)
                VALUES (%s, %s, 'active')
                RETURNING id
                """,
                (f"DPD-C-{suffix}", f"DPD Client {suffix}"),
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
                    1000.00,
                    0.00,
                    current_date - 120,
                    current_date + 30,
                    'active'
                )
                RETURNING id
                """,
                (f"DPD-L-{suffix}", client_id, loan_type_id),
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
                    'weekly',
                    %s,
                    current_date - 120,
                    current_date - 120,
                    0
                )
                RETURNING id
                """,
                (loan_id, f"CONTRACT-{suffix}"),
            ).fetchone()[0]

            connection.execute(
                """
                INSERT INTO lending.loan_contract_installments (
                    schedule_id,
                    installment_number,
                    due_date,
                    contractual_amount
                )
                VALUES
                    (%s, 1, current_date - 95, 500.00),
                    (%s, 2, current_date + 7, 500.00)
                """,
                (schedule_id, schedule_id),
            )

            assessment = connection.execute(
                """
                SELECT
                    payment_frequency,
                    contract_reference,
                    installment_count,
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

            assert assessment is not None
            assert assessment[0] == "weekly"
            assert assessment[1] == f"CONTRACT-{suffix}"
            assert assessment[2] == 2
            assert assessment[3] == 500
            assert assessment[4] == "ready"
            assert assessment[5] == 95
            assert assessment[6] is True
            assert assessment[7] is True
            assert assessment[8] is False
            assert assessment[9] is None
            assert assessment[10] is False
            assert assessment[11] is False
        finally:
            connection.rollback()
