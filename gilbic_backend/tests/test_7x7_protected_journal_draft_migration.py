from __future__ import annotations

from pathlib import Path


SQL = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0065_add_protected_7x7_source_event_journal_drafts.sql"
).read_text(encoding="utf-8")


def test_7x7_journal_draft_is_explicit_management_only_and_posting_disabled() -> None:
    normalized = SQL.upper()
    assert SQL.strip().startswith("BEGIN;")
    assert SQL.strip().endswith("COMMIT;")

    assert "ACCOUNTING.SEVEN_BY_SEVEN.JOURNAL.PREPARE" in normalized
    assert "WHERE ROLE.CODE = 'MANAGEMENT'" in normalized
    assert "SEVEN_BY_SEVEN_JOURNAL_DRAFT_PREPARATIONS" in normalized
    assert "CREATE_SEVEN_BY_SEVEN_JOURNAL_DRAFT" in normalized
    assert "SOURCE_EVENT_REVIEW_TOKEN" in normalized
    assert "COORDINATE_DIGEST" in normalized
    assert "SEVEN_BY_SEVEN_COORDINATE_DIGEST" in normalized
    assert "SOURCE_EVENT_KEY = 'COLLECTION:' || TRANSACTION_ID::TEXT" in normalized

    assert "'ACCRUED_INTEREST_RECEIVABLE'" in normalized
    assert "'INTEREST_INCOME_7X7'" in normalized
    assert "'CASH_COLLECTOR_CUSTODY'" in normalized
    assert "'LOANS_RECEIVABLE_7X7'" in normalized
    assert "'SEVEN_BY_SEVEN_COLLECTION'" in normalized

    # This migration may create a draft only through the protected function,
    # but it must not define or enable posting/reversal/automatic source posting.
    assert "INSERT INTO ACCOUNTING.JOURNAL_ENTRIES" in normalized
    assert "INSERT INTO ACCOUNTING.JOURNAL_LINES" in normalized
    assert "CREATE_SEVEN_BY_SEVEN_JOURNAL_POST" not in normalized
    assert "REVERSE_SEVEN_BY_SEVEN" not in normalized
    assert "FALSE AS POSTING_ENABLED" in normalized
    assert "FALSE AS AUTOMATIC_SOURCE_POSTING" in normalized
    assert "FUTURE PROTECTED 7X7 POSTING WORKFLOW" in normalized

    # Draft lines are copied from the already-proven 0064 coordinate preview,
    # not recomputed from the Desktop operational allocator.
    assert "SEVEN_BY_SEVEN_SOURCE_EVENT_JOURNAL_COORDINATE_PREVIEW" in normalized
    assert "OPERATIONAL_ALLOCATION_SUBSTITUTED_FOR_ACCOUNTING IS DISTINCT FROM FALSE" in normalized
    assert "AUTHORITATIVE_CURRENT_CARRYING_AMOUNT_READY IS DISTINCT FROM FALSE" in normalized
