from __future__ import annotations

from pathlib import Path


SQL_ROOT = Path(__file__).resolve().parents[1] / "sql"
SQL = (SQL_ROOT / "0067_add_controlled_7x7_collection_reversals.sql").read_text(
    encoding="utf-8"
)
HARDENING_SQL = (
    SQL_ROOT / "0068_harden_controlled_7x7_collection_reversal_guard.sql"
).read_text(encoding="utf-8")


def test_7x7_reversal_is_controlled_exact_and_auto_posting_stays_off() -> None:
    normalized = SQL.upper()
    assert SQL.strip().startswith("BEGIN;")
    assert SQL.strip().endswith("COMMIT;")

    assert "SEVEN_BY_SEVEN_JOURNAL_REVERSALS" in normalized
    assert "SEVEN_BY_SEVEN_JOURNAL_REVERSAL_LINES" in normalized
    assert "REVERSE_POSTED_SEVEN_BY_SEVEN_COLLECTION" in normalized
    assert "PERFORM_CONTROLLED_SEVEN_BY_SEVEN_COLLECTION_VOID_REVERSAL" in normalized
    assert "GUARD_POSTED_SEVEN_BY_SEVEN_COLLECTION_VOID" in normalized
    assert "SEVEN_BY_SEVEN_JOURNAL_REVERSAL_STATUS" in normalized
    assert "SEVEN_BY_SEVEN_COLLECTION_REVERSAL_V1" in normalized

    # The protected reversal must be coupled to immutable operational void
    # evidence and copy the 0066 posting snapshots with debit/credit swapped.
    assert "LENDING.COLLECTION_TRANSACTION_VOIDS" in normalized
    assert "SEVEN_BY_SEVEN_JOURNAL_POSTING_LINES" in normalized
    assert "SNAPSHOT.CREDIT" in normalized
    assert "SNAPSHOT.DEBIT" in normalized
    assert "EXACT_DEBIT_CREDIT_SWAP" in normalized
    assert "REVERSAL_OF_ENTRY_ID" in normalized

    # Manual/general-journal reversal remains fail-closed; the private flag is
    # transaction-local and only the controlled void path may create the journal.
    assert "ACCOUNTING.SEVEN_BY_SEVEN_COLLECTION_VOID_REVERSAL_ALLOWED" in normalized
    assert "PROTECTED 7X7 COLLECTION REVERSAL JOURNALS MUST USE THE CONTROLLED COLLECTION-VOID WORKFLOW" in normalized
    assert "ACCOUNTING_02_SEVEN_BY_SEVEN_COLLECTION_VOID_REVERSAL" in normalized
    assert "ACCOUNTING_03_SEVEN_BY_SEVEN_POSTED_COLLECTION_VOID_GUARD" in normalized
    assert "TRUE AS PROTECTED_REVERSAL_ENABLED" in normalized
    assert "FALSE AS AUTOMATIC_SOURCE_POSTING" in normalized


def test_7x7_reversal_audit_is_immutable_and_install_is_history_free() -> None:
    normalized = SQL.upper()
    assert "GUARD_SEVEN_BY_SEVEN_JOURNAL_REVERSAL_RECORD_WRITE" in normalized
    assert "REVERSAL AUDIT IS IMMUTABLE" in normalized
    assert "BEFORE INSERT OR UPDATE OR DELETE" in normalized
    assert "REVERSAL_AUDIT_EXACT" in normalized
    assert "POST_JOURNAL_ENTRY" in normalized

    # Installation changes only schema/functions/triggers/views. It never
    # inserts operational collection voids, protected postings, or reversals.
    assert "INSERT INTO LENDING.COLLECTION_TRANSACTION_VOIDS" not in normalized
    assert "INSERT INTO ACCOUNTING.SEVEN_BY_SEVEN_JOURNAL_POSTINGS" not in normalized


def test_0068_hardens_final_void_guard_without_ambiguous_local_names() -> None:
    normalized = HARDENING_SQL.upper()
    assert HARDENING_SQL.strip().startswith("BEGIN;")
    assert HARDENING_SQL.strip().endswith("COMMIT;")
    assert "GUARD_POSTED_SEVEN_BY_SEVEN_COLLECTION_VOID" in normalized
    assert "MATCHED_REVERSAL_ID UUID" in normalized
    assert "MATCHED_REVERSAL_ENTRY_ID UUID" in normalized
    assert "SNAPSHOT.REVERSAL_ID = MATCHED_REVERSAL_ID" in normalized
    assert "LINE.JOURNAL_ENTRY_ID = MATCHED_REVERSAL_ENTRY_ID" in normalized
    assert "WHERE SNAPSHOT.REVERSAL_ID = REVERSAL_ID" not in normalized
    assert "WHERE LINE.JOURNAL_ENTRY_ID = REVERSAL_ENTRY_ID" not in normalized
    assert "INSERT INTO" not in normalized
