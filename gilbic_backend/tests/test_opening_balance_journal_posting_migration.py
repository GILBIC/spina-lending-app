from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0038_add_protected_opening_balance_journal_posting.sql"
)


def migration_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_posting_migration_is_transactional_and_never_posts_during_install() -> None:
    sql = migration_sql()
    stripped = sql.strip()
    assert stripped.startswith("BEGIN;")
    assert stripped.endswith("COMMIT;")
    assert "accounting.opening_balance_journal_postings" in sql
    assert "accounting.post_opening_balance_journal" in sql
    assert "accounting.opening_balance_journal_posting_status" in sql
    assert "accounting.opening_balance.post" in sql
    assert "false AS automatic_source_posting_enabled" in sql

    # Deployment installs controls only. The protected function may be defined,
    # but the migration itself must never invoke it or call the generic posting
    # function outside that protected function body.
    assert "SELECT accounting.post_opening_balance_journal" not in sql
    assert "select accounting.post_opening_balance_journal" not in sql


def test_protected_post_revalidates_workbook_journal_period_and_sources() -> None:
    sql = migration_sql()
    assert "workbook.status <> 'review_ready'" in sql
    assert "verification_status = 'verified'" in sql
    assert "evidence_note" in sql
    assert "workbook_debit <> workbook_credit" in sql
    assert "journal_debit <> workbook_debit" in sql
    assert "journal_to_workbook_mismatch_count" in sql
    assert "workbook_to_journal_mismatch_count" in sql
    assert "period.status <> 'open'" in sql
    assert "readiness_status = 'blocked'" in sql
    assert "account.is_active = false OR account.is_posting = false" in sql


def test_protected_post_uses_existing_ledger_guard_and_immutable_audit() -> None:
    sql = migration_sql()
    assert "accounting.opening_balance_post_allowed" in sql
    assert "accounting.post_journal_entry(journal.id, p_actor_user_id)" in sql
    assert "accounting.opening_balance_post_record_allowed" in sql
    assert "guard_opening_balance_journal_posting_record_write" in sql
    assert "protected_posting', true" in sql
    assert "automatic_source_posting', false" in sql


def test_repeated_protected_post_is_idempotent() -> None:
    sql = migration_sql()
    assert "IF journal.status = 'posted' THEN" in sql
    assert "existing_post.journal_entry_id = journal.id" in sql
    assert "RETURN journal.entry_number" in sql
