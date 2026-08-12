from __future__ import annotations

from pathlib import Path


SQL = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0066_add_protected_7x7_source_event_journal_posting.sql"
).read_text(encoding="utf-8")


def test_7x7_posting_is_explicit_management_only_reversal_off_and_auto_off() -> None:
    normalized = SQL.upper()
    assert SQL.strip().startswith("BEGIN;")
    assert SQL.strip().endswith("COMMIT;")

    assert "ACCOUNTING.SEVEN_BY_SEVEN.JOURNAL.POST" in normalized
    assert "WHERE ROLE.CODE = 'MANAGEMENT'" in normalized
    assert "SEVEN_BY_SEVEN_JOURNAL_POSTINGS" in normalized
    assert "SEVEN_BY_SEVEN_JOURNAL_POSTING_LINES" in normalized
    assert "POST_SEVEN_BY_SEVEN_JOURNAL" in normalized
    assert "SEVEN_BY_SEVEN_JOURNAL_POSTING_STATUS" in normalized
    assert "SEVEN_BY_SEVEN_SOURCE_EVENT_JOURNAL_POSTING_V1" in normalized

    assert "ACCOUNTING.SEVEN_BY_SEVEN_JOURNAL_POST_ALLOWED" in normalized
    assert "ACCOUNTING.POST_JOURNAL_ENTRY" in normalized
    assert "EXPLICIT_MANAGEMENT_POSTING" in normalized
    assert "TRUE AS PROTECTED_POSTING_ENABLED" in normalized
    assert "FALSE AS REVERSAL_ENABLED" in normalized
    assert "FALSE AS AUTOMATIC_SOURCE_POSTING" in normalized

    # Final posting must revalidate the exact 0064 source review and coordinate
    # digest plus the immutable 0065 draft instead of recomputing Desktop 7x7.
    assert "SEVEN_BY_SEVEN_JOURNAL_DRAFT_REVIEW" in normalized
    assert "SEVEN_BY_SEVEN_JOURNAL_DRAFT_STATUS" in normalized
    assert "SEVEN_BY_SEVEN_COORDINATE_DIGEST" in normalized
    assert "SEVEN_BY_SEVEN_SOURCE_EVENT_JOURNAL_COORDINATE_PREVIEW" in normalized
    assert "ACCRUED_INTEREST_RECEIVABLE" in normalized
    assert "INTEREST_INCOME_7X7" in normalized
    assert "CASH_COLLECTOR_CUSTODY" in normalized
    assert "LOANS_RECEIVABLE_7X7" in normalized

    # Posting enables no generic/manual reversal. Until the next controlled
    # reversal slice, both journal reversal and operational void fail closed.
    assert "GUARD_PROTECTED_SEVEN_BY_SEVEN_REVERSAL_INSERT" in normalized
    assert "GUARD_POSTED_SEVEN_BY_SEVEN_COLLECTION_VOID" in normalized
    assert "REVERSE_POSTED_SEVEN_BY_SEVEN" not in normalized
    assert "CREATE_SEVEN_BY_SEVEN_REVERSAL" not in normalized


def test_7x7_posting_audit_captures_immutable_exact_line_snapshots() -> None:
    normalized = SQL.upper()
    assert "COORDINATE_DIGEST" in normalized
    assert "SOURCE_EVENT_REVIEW_TOKEN" in normalized
    assert "POSTING_REVIEW_TOKEN" in normalized
    assert "JOURNAL_COMPONENT" in normalized
    assert "ACCOUNT_SYSTEM_KEY" in normalized
    assert "AUDIT_EXACT_LINE_MATCH_COUNT" in normalized
    assert "POSTED_AUDIT_EXACT" in normalized
    assert "EXACT RETRY" in normalized
