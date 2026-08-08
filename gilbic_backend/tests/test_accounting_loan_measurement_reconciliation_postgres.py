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
    / "0029_reconcile_accounting_loan_measurement_rounding.sql"
).read_text(encoding="utf-8")


def _transaction_body(sql: str) -> str:
    body = sql.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    body = body[: -len("COMMIT;")].rstrip()
    return body


def test_stage5d1_migration_executes_and_reconciles_in_postgres() -> None:
    assert DATABASE_URL is not None

    with psycopg.connect(DATABASE_URL) as connection:
        original_function = connection.execute(
            "SELECT to_regprocedure(" 
            "'accounting.measure_loan_at_cutover(uuid,date)')"
        ).fetchone()[0]
        if original_function is None:
            pytest.skip("Stage 5D migration 0028 is not installed in the test database")

        try:
            connection.execute(_transaction_body(SQL))

            row_violation_count = connection.execute(
                """
                SELECT count(*)
                FROM accounting.loan_measurement_at_cutover
                WHERE measurement_status = 'measured'
                  AND abs(
                        loan_component
                        + accrued_interest_component
                        - gross_carrying_amount
                      ) >= 0.005
                """
            ).fetchone()[0]
            assert row_violation_count == 0

            reconciliation = connection.execute(
                """
                SELECT
                    measured_loan_count,
                    loan_row_component_variance,
                    all_measured_loans_reconciled,
                    summary_component_variance,
                    summary_reconciled,
                    ready_to_post,
                    ecl_included
                FROM accounting.loan_measurement_reconciliation
                """
            ).fetchone()

            assert reconciliation is not None
            assert reconciliation[1] == 0
            assert reconciliation[2] is True
            assert reconciliation[3] == 0
            assert reconciliation[4] is True
            assert reconciliation[5] is False
            assert reconciliation[6] is False
        finally:
            # PostgreSQL DDL is transactional. Leave the shared CI test database
            # exactly as it was before this migration validation.
            connection.rollback()
