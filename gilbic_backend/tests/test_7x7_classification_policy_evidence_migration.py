from __future__ import annotations

from pathlib import Path


SQL = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0062_add_7x7_classification_policy_evidence.sql"
).read_text(encoding="utf-8")


def test_7x7_classification_policy_evidence_is_protected_and_fail_closed() -> None:
    normalized = SQL.upper()
    assert SQL.strip().startswith("BEGIN;")
    assert SQL.strip().endswith("COMMIT;")

    assert "ACCOUNTING.7X7_CLASSIFICATION_POLICY.MANAGE" in normalized
    assert "SEVEN_BY_SEVEN_POLICY_REVIEW_TOKEN" in normalized
    assert "SEVEN_BY_SEVEN_POLICY_DECISIONS" in normalized
    assert "SEVEN_BY_SEVEN_POLICY_DECISION_VOIDS" in normalized
    assert "RECORD_SEVEN_BY_SEVEN_POLICY_DECISION" in normalized
    assert "VOID_SEVEN_BY_SEVEN_POLICY_DECISION" in normalized
    assert "SEVEN_BY_SEVEN_CLASSIFICATION_POLICY_READINESS" in normalized
    assert "SEVEN_BY_SEVEN_CLASSIFICATION_POLICY_SUMMARY" in normalized

    assert "HELD_TO_COLLECT" in normalized
    assert "HELD_TO_COLLECT_AND_SELL" in normalized
    assert "AMORTISED_COST" in normalized
    assert "FVOCI" in normalized
    assert "FVPL" in normalized
    assert "SPPI_CONCLUSION" in normalized
    assert "SEPARATE_EXPECTED_PREPAYMENT_CASH_FLOW_EVIDENCE_REQUIRED" in normalized

    assert "NULL::NUMERIC(24,12) AS AUTHORITATIVE_DAILY_EIR" in normalized
    assert "NULL::NUMERIC(18,2) AS AUTHORITATIVE_INITIAL_GROSS_CARRYING_AMOUNT" in normalized
    assert "NULL::NUMERIC(18,2) AS AUTHORITATIVE_CURRENT_GROSS_CARRYING_AMOUNT" in normalized
    assert "FALSE AS EIR_POLICY_READY" in normalized
    assert "FALSE AS CARRYING_AMOUNT_READY" in normalized
    assert "FALSE AS JOURNAL_LINES_ENABLED" in normalized
    assert "FALSE AS AUTOMATIC_SOURCE_POSTING" in normalized

    # This evidence layer may write only protected accounting decision/audit
    # evidence. It must never create or mutate lending or journal history.
    assert "INSERT INTO LENDING." not in normalized
    assert "UPDATE LENDING." not in normalized
    assert "DELETE FROM LENDING." not in normalized
    assert "INSERT INTO ACCOUNTING.JOURNAL_ENTRIES" not in normalized
    assert "INSERT INTO ACCOUNTING.JOURNAL_LINES" not in normalized
    assert "UPDATE ACCOUNTING.JOURNAL_ENTRIES" not in normalized
    assert "DELETE FROM ACCOUNTING.JOURNAL_ENTRIES" not in normalized
