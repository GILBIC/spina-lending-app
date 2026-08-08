from __future__ import annotations

import os
from pathlib import Path

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
    / "0031_add_accounting_ecl_calibration_readiness.sql"
).read_text(encoding="utf-8")


def _transaction_body(sql: str) -> str:
    body = sql.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def test_stage5e1_migration_executes_without_calculating_ecl() -> None:
    assert DATABASE_URL is not None

    with psycopg.connect(DATABASE_URL) as connection:
        stage5e = connection.execute(
            "SELECT to_regclass('accounting.ecl_assessment_summary')"
        ).fetchone()[0]
        if stage5e is None:
            pytest.skip("Stage 5E ECL readiness is not installed in the test database")

        try:
            connection.execute(_transaction_body(SQL))

            inventory = connection.execute(
                """
                SELECT
                    total_loan_count,
                    active_loan_count,
                    resolved_loan_count,
                    defaulted_loan_count,
                    valid_cash_collection_count,
                    calibration_readiness_status,
                    calibration_source_ready,
                    historical_loss_calibration_configured,
                    forward_looking_scenarios_configured,
                    ecl_amount,
                    ecl_included,
                    ready_to_post
                FROM accounting.ecl_calibration_source_inventory
                """
            ).fetchone()

            assert inventory is not None
            assert inventory[0] >= inventory[1]
            assert inventory[2] >= 0
            assert inventory[3] >= 0
            assert inventory[4] >= 0
            assert inventory[5] in {
                "historical_data_required",
                "default_outcome_data_required",
                "recovery_writeoff_source_required",
            }
            assert inventory[6] is False
            assert inventory[7] is False
            assert inventory[8] is False
            assert inventory[9] is None
            assert inventory[10] is False
            assert inventory[11] is False

            allowance = connection.execute(
                """
                SELECT
                    measurement_reference_amount,
                    measurement_status,
                    measurement_note
                FROM accounting.opening_balance_measurement_reference
                WHERE account_code = '1190'
                """
            ).fetchone()

            assert allowance is not None
            assert allowance[0] is None
            assert allowance[1] in {
                "historical_data_required",
                "default_outcome_data_required",
                "recovery_writeoff_source_required",
            }
            assert "Stage 5E.1 ECL calibration readiness" in allowance[2]
            assert "No PD, LGD" in allowance[2]
        finally:
            connection.rollback()
