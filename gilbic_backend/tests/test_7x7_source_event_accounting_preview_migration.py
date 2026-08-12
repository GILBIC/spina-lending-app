from __future__ import annotations

from pathlib import Path


SQL = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0064_add_7x7_source_event_accounting_preview.sql"
).read_text(encoding="utf-8")


def test_7x7_source_event_preview_is_read_only_and_uses_authoritative_schema() -> None:
    normalized = SQL.upper()
    assert SQL.strip().startswith("BEGIN;")
    assert SQL.strip().endswith("COMMIT;")

    assert "SEVEN_BY_SEVEN_COLLECTION_SOURCE_EVENT_KEY" in normalized
    assert "SEVEN_BY_SEVEN_COLLECTION_SOURCE_INVENTORY" in normalized
    assert "SEVEN_BY_SEVEN_SOURCE_EVENT_ACCOUNTING_READINESS" in normalized
    assert "PREVIEW_SEVEN_BY_SEVEN_SOURCE_EVENT_ACCOUNTING" in normalized
    assert "PREVIEW_SEVEN_BY_SEVEN_OPERATIONAL_ALLOCATION" in normalized
    assert "SEVEN_BY_SEVEN_OPERATIONAL_ALLOCATION_PARITY_PREVIEW" in normalized
    assert "SEVEN_BY_SEVEN_SOURCE_EVENT_JOURNAL_COORDINATE_PREVIEW" in normalized
    assert "SEVEN_BY_SEVEN_SOURCE_EVENT_ACCOUNTING_SUMMARY" in normalized

    # Current PostgreSQL source schema uses lowercase payment/advance/pass.
    assert "ENTRY_TYPE IN ('PAYMENT', 'ADVANCE')" in normalized
    assert "ENTRY_TYPE = 'PASS'" in normalized
    assert "INTEREST_PAID" not in normalized
    assert "PRINCIPAL_PAID" not in normalized
    assert "REVERSAL_TRANSACTION_ID" not in normalized
    assert "REVERSES_TRANSACTION_ID" not in normalized

    # Accounting EIR allocation is separate from the Desktop operational rule.
    assert "AUTHORITATIVE_DAILY_EIR" in normalized
    assert "FIXED_OPERATIONAL_DAILY_INTEREST" in normalized
    assert "OPERATIONAL_ALLOCATION_SUBSTITUTED_FOR_ACCOUNTING" in normalized
    assert "FALSE AS OPERATIONAL_ALLOCATION_SUBSTITUTED_FOR_ACCOUNTING" in normalized
    assert "SAME_DAY_MULTIPLE_FINANCIAL_SOURCE_EVENTS" in normalized
    assert "SAME_DAY_OR_PRE_ANCHOR_CASH_ORDERING_REVIEW" in normalized

    # Read-only journal coordinates use the established account system keys.
    assert "'ACCRUED_INTEREST_RECEIVABLE'" in normalized
    assert "'INTEREST_INCOME_7X7'" in normalized
    assert "'CASH_COLLECTOR_CUSTODY'" in normalized
    assert "'LOANS_RECEIVABLE_7X7'" in normalized

    # This slice must not create or mutate source/history or journals.
    assert "INSERT INTO LENDING." not in normalized
    assert "UPDATE LENDING." not in normalized
    assert "DELETE FROM LENDING." not in normalized
    assert "INSERT INTO ACCOUNTING.JOURNAL_ENTRIES" not in normalized
    assert "INSERT INTO ACCOUNTING.JOURNAL_LINES" not in normalized
    assert "UPDATE ACCOUNTING.JOURNAL_ENTRIES" not in normalized
    assert "DELETE FROM ACCOUNTING.JOURNAL_ENTRIES" not in normalized
    assert "NULL::NUMERIC(18,2) AS AUTHORITATIVE_CURRENT_GROSS_CARRYING_AMOUNT" in normalized
    assert "FALSE AS AUTHORITATIVE_CURRENT_CARRYING_AMOUNT_READY" in normalized
    assert "FALSE AS JOURNAL_DRAFT_ENABLED" in normalized
    assert "FALSE AS JOURNAL_LINES_ENABLED" in normalized
    assert "FALSE AS AUTOMATIC_SOURCE_POSTING" in normalized
