from __future__ import annotations

from pathlib import Path


SQL = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0061_add_7x7_eir_carrying_policy_readiness.sql"
).read_text(encoding="utf-8")


def test_7x7_eir_carrying_policy_migration_is_read_only_and_fail_closed() -> None:
    normalized = SQL.upper()
    assert SQL.strip().startswith("BEGIN;")
    assert SQL.strip().endswith("COMMIT;")

    assert "SOLVE_VERIFIED_SCHEDULE_DAILY_EIR_PREVIEW" in normalized
    assert "SEVEN_BY_SEVEN_EIR_CARRYING_POLICY_READINESS" in normalized
    assert "SEVEN_BY_SEVEN_EIR_CARRYING_POLICY_SUMMARY" in normalized

    assert "AUTHORITATIVE_DAILY_EIR" in normalized
    assert "NULL::NUMERIC(24,12) AS AUTHORITATIVE_DAILY_EIR" in normalized
    assert "NULL::NUMERIC(18,2) AS AUTHORITATIVE_INITIAL_GROSS_CARRYING_AMOUNT" in normalized
    assert "NULL::NUMERIC(18,2) AS AUTHORITATIVE_CURRENT_GROSS_CARRYING_AMOUNT" in normalized
    assert "FALSE AS EIR_POLICY_READY" in normalized
    assert "FALSE AS CARRYING_AMOUNT_READY" in normalized
    assert "FALSE AS JOURNAL_LINES_ENABLED" in normalized
    assert "FALSE AS AUTOMATIC_SOURCE_POSTING" in normalized

    assert "SPPI_AND_PREPAYMENT_POLICY_REVIEW_REQUIRED" in normalized
    assert "BUSINESS_MODEL_ASSESSMENT_REQUIRED" in normalized
    assert "PREPAYMENT_EXPECTED_CASH_FLOW_POLICY_REQUIRED" in normalized

    # Installing a readiness layer must not create operational or financial history.
    assert "INSERT INTO LENDING." not in normalized
    assert "UPDATE LENDING." not in normalized
    assert "DELETE FROM LENDING." not in normalized
    assert "INSERT INTO ACCOUNTING.JOURNAL_ENTRIES" not in normalized
    assert "INSERT INTO ACCOUNTING.JOURNAL_LINES" not in normalized
