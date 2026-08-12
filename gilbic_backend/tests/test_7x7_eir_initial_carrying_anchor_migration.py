from __future__ import annotations

from pathlib import Path


SQL = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0063_add_7x7_eir_initial_carrying_anchor.sql"
).read_text(encoding="utf-8")


def test_7x7_eir_initial_carrying_anchor_is_protected_and_posting_disabled() -> None:
    normalized = SQL.upper()
    assert SQL.strip().startswith("BEGIN;")
    assert SQL.strip().endswith("COMMIT;")

    assert "ACCOUNTING.7X7_EIR_ANCHOR.MANAGE" in normalized
    assert "SEVEN_BY_SEVEN_EIR_ANCHOR_REVIEW_TOKEN" in normalized
    assert "SEVEN_BY_SEVEN_EIR_INITIAL_CARRYING_ANCHORS" in normalized
    assert "SEVEN_BY_SEVEN_EIR_INITIAL_CARRYING_ANCHOR_VOIDS" in normalized
    assert "RECORD_SEVEN_BY_SEVEN_EIR_INITIAL_CARRYING_ANCHOR" in normalized
    assert "VOID_SEVEN_BY_SEVEN_EIR_INITIAL_CARRYING_ANCHOR" in normalized
    assert "SEVEN_BY_SEVEN_EIR_INITIAL_CARRYING_READINESS" in normalized
    assert "SEVEN_BY_SEVEN_EIR_INITIAL_CARRYING_SUMMARY" in normalized

    assert "MANAGEMENT_EVIDENCE_BACKED_IFRS9_INITIAL_MEASUREMENT" in normalized
    assert "SOLVE_VERIFIED_SCHEDULE_DAILY_EIR_PREVIEW" in normalized
    assert "AUTHORITATIVE_DAILY_EIR" in normalized
    assert "AUTHORITATIVE_INITIAL_GROSS_CARRYING_AMOUNT" in normalized
    assert "NULL::NUMERIC(18,2) AS AUTHORITATIVE_CURRENT_GROSS_CARRYING_AMOUNT" in normalized
    assert "FALSE AS CURRENT_CARRYING_AMOUNT_READY" in normalized
    assert "FALSE AS CARRYING_AMOUNT_READY" in normalized
    assert "FALSE AS JOURNAL_LINES_ENABLED" in normalized
    assert "FALSE AS AUTOMATIC_SOURCE_POSTING" in normalized

    # The anchor may write only immutable accounting evidence/audit rows. It
    # must not create lending history, journal entries/lines, or source posting.
    assert "INSERT INTO LENDING." not in normalized
    assert "UPDATE LENDING." not in normalized
    assert "DELETE FROM LENDING." not in normalized
    assert "INSERT INTO ACCOUNTING.JOURNAL_ENTRIES" not in normalized
    assert "INSERT INTO ACCOUNTING.JOURNAL_LINES" not in normalized
    assert "UPDATE ACCOUNTING.JOURNAL_ENTRIES" not in normalized
    assert "DELETE FROM ACCOUNTING.JOURNAL_ENTRIES" not in normalized
