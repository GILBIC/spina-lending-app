from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0043_add_controlled_regular_collection_reversals.sql"
)


def migration_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_regular_collection_reversal_migration_is_install_only() -> None:
    sql = migration_sql()
    stripped = sql.strip()
    assert stripped.startswith("BEGIN;")
    assert stripped.endswith("COMMIT;")
    assert "accounting.regular_journal_reversal_sets" in sql
    assert "accounting.regular_journal_reversal_entries" in sql
    assert "accounting.reverse_posted_regular_collection" in sql

    # Installing Stage 5D.18 must not itself void a collection or create a reversal.
    assert "SELECT accounting.reverse_posted_regular_collection" not in sql
    assert "UPDATE lending.collection_transactions\nSET is_voided = true" not in sql


def test_regular_collection_reversal_preserves_original_posted_history() -> None:
    sql = migration_sql()
    assert "reversal_of_entry_id" in sql
    assert "original_line.credit" in sql
    assert "original_line.debit" in sql
    assert "original_journal_entry_id UUID NOT NULL UNIQUE" in sql
    assert "reversal_journal_entry_id UUID NOT NULL UNIQUE" in sql
    assert "Posted protected Regular journals can only be reversed" in sql


def test_regular_collection_reversal_requires_complete_stage5d17_audit() -> None:
    sql = migration_sql()
    assert "posting_audit_count <> actual_entry_count" in sql
    assert "posted_entry_count <> actual_entry_count" in sql
    assert "distinct_posting_set_count <> 1" in sql
    assert "journal.entry_number IS DISTINCT FROM posted.entry_number" in sql
    assert "journal.source_event_key IS DISTINCT FROM posted.source_event_key" in sql
    assert "partial, unaudited, or inconsistent" in sql


def test_regular_collection_reversal_is_atomic_and_duplicate_safe() -> None:
    sql = migration_sql()
    assert "transaction_id UUID NOT NULL UNIQUE" in sql
    assert "collection_void_id UUID NOT NULL UNIQUE" in sql
    assert "reversal_of_entry_id = original_entry.journal_entry_id" in sql
    assert "already has a reversal outside this collection-void audit" in sql
    assert "did not complete atomically" in sql
    assert "accounting.post_journal_entry(" in sql


def test_unposted_protected_draft_can_be_invalidated_by_operational_void() -> None:
    sql = migration_sql()
    assert "posting_audit_count = 0 AND posted_entry_count = 0" in sql
    assert "draft_entry_count = actual_entry_count" in sql
    assert "RETURN NULL" in sql
    assert "Stage 5D.17 will refuse to post it after the void" in sql


def test_accounted_void_has_database_enforced_reversal_gate() -> None:
    sql = migration_sql()
    assert "accounting.perform_controlled_regular_collection_void_reversal" in sql
    assert "accounting.guard_accounted_regular_collection_void" in sql
    assert "BEFORE UPDATE OF is_voided ON lending.collection_transactions" in sql
    assert "cannot be voided until its protected reversing journals are posted and audited" in sql
    assert "accounting_00_regular_collection_void_reversal" in sql


def test_reversal_uses_business_date_and_open_period() -> None:
    sql = migration_sql()
    assert "AT TIME ZONE 'Asia/Manila'" in sql
    assert "period.status = 'open'" in sql
    assert "No open accounting period contains the controlled Regular reversal date" in sql


def test_reversal_audit_is_immutable_and_fully_linked() -> None:
    sql = migration_sql()
    assert "guard_regular_journal_reversal_record_write" in sql
    assert "collection_void_id" in sql
    assert "posting_set_id" in sql
    assert "original_source_event_key" in sql
    assert "reversal_source_event_key" in sql
    assert "regular_collection_void_reversal_allowed" in sql
