from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0042_add_protected_regular_journal_posting.sql"
)


def migration_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_regular_posting_migration_is_transactional_and_does_not_post_on_install() -> None:
    sql = migration_sql()
    stripped = sql.strip()
    assert stripped.startswith("BEGIN;")
    assert stripped.endswith("COMMIT;")
    assert "accounting.regular_journal_posting_sets" in sql
    assert "accounting.regular_journal_posting_entries" in sql
    assert "accounting.post_regular_journal_review_set" in sql
    assert "accounting.regular_journal.post" in sql

    # Deployment installs the explicit posting controls only. It must never invoke
    # the protected posting function by itself.
    assert "SELECT accounting.post_regular_journal_review_set" not in sql
    assert "select accounting.post_regular_journal_review_set" not in sql


def test_regular_posting_is_full_review_set_atomic_and_idempotent() -> None:
    sql = migration_sql()
    assert "expected_set_transaction_count <> preparation_count" in sql
    assert "actual_entry_count <> expected_entry_count" in sql
    assert "posting audit does not match the posted review set" in sql
    assert "RETURN existing_post.id" in sql
    assert "posted_entry_count > 0 OR draft_entry_count <> expected_entry_count" in sql
    assert "posting did not complete atomically" in sql


def test_regular_posting_revalidates_source_identity_period_accounts_and_balance() -> None:
    sql = migration_sql()
    assert "transaction.is_voided" in sql
    assert "transaction.entry_type NOT IN ('payment', 'advance')" in sql
    assert "journal.posting_date <> transaction.collection_date" in sql
    assert "totals.total_debit <> transaction.amount" in sql
    assert "journal.source_event_key IS DISTINCT FROM prepared_entry.source_event_key" in sql
    assert "period.status <> 'open'" in sql
    assert "account.is_active = false OR account.is_posting = false" in sql
    assert "totals.total_debit <> totals.total_credit" in sql


def test_regular_posting_preserves_approved_account_patterns() -> None:
    sql = migration_sql()
    assert "accrued_interest_receivable" in sql
    assert "interest_income_regular" in sql
    assert "cash_collector_custody" in sql
    assert "loans_receivable_regular" in sql
    assert "approved 1120/4000 pattern" in sql
    assert "approved 1020/1120/1100 pattern" in sql


def test_regular_posting_uses_existing_ledger_gate_and_immutable_audit() -> None:
    sql = migration_sql()
    assert "accounting.regular_journal_post_allowed" in sql
    assert "accounting.post_journal_entry(" in sql
    assert "accounting.regular_journal_post_record_allowed" in sql
    assert "guard_regular_journal_posting_record_write" in sql
    assert "'protected_posting', true" in sql
    assert "'automatic_source_posting', false" in sql


def test_regular_posting_freezes_all_protected_source_tables_through_commit() -> None:
    sql = migration_sql()
    assert "LOCK TABLE" in sql
    assert "lending.loan_collection_state" in sql
    assert "lending.collection_transactions" in sql
    assert "accounting.opening_balance_loan_measurement_snapshots" in sql
    assert "accounting.regular_journal_draft_preparations" in sql
    assert "IN SHARE MODE" in sql
