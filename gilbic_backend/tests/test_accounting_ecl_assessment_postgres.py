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
    / "0030_add_accounting_ecl_assessment_readiness.sql"
).read_text(encoding="utf-8")


def _transaction_body(sql: str) -> str:
    body = sql.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    body = body[: -len("COMMIT;")].rstrip()
    return body


def test_stage5e_migration_executes_without_quantifying_ecl() -> None:
    assert DATABASE_URL is not None

    with psycopg.connect(DATABASE_URL) as connection:
        stage5d = connection.execute(
            "SELECT to_regclass('accounting.loan_measurement_at_cutover')"
        ).fetchone()[0]
        if stage5d is None:
            pytest.skip("Stage 5D loan measurement is not installed in the test database")

        try:
            connection.execute(_transaction_body(SQL))

            summary = connection.execute(
                """
                SELECT
                    active_loan_count,
                    backstop_assessed_count,
                    review_required_count,
                    gross_exposure,
                    sicr_30dpd_backstop_count,
                    default_90dpd_backstop_count,
                    ecl_measurement_status,
                    historical_loss_calibration_configured,
                    forward_looking_scenarios_configured,
                    ecl_amount,
                    ecl_included,
                    ready_to_post
                FROM accounting.ecl_assessment_summary
                """
            ).fetchone()

            assert summary is not None
            assert summary[0] >= 0
            assert summary[1] + summary[2] == summary[0]
            assert summary[3] >= 0
            assert summary[4] >= summary[5]
            assert summary[6] in {"calibration_required", "source_review_required"}
            assert summary[7] is False
            assert summary[8] is False
            assert summary[9] is None
            assert summary[10] is False
            assert summary[11] is False

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
            assert allowance[1] in {"calibration_required", "source_review_required"}
            assert "not quantified" in allowance[2]
        finally:
            connection.rollback()
