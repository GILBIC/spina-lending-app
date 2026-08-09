from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0037_add_opening_balance_journal_draft.sql"
)


def migration_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_migration_is_transactional_and_does_not_prepare_live_data() -> None:
    sql = migration_sql()
    stripped = sql.strip()
    assert stripped.startswith("BEGIN;")
    assert stripped.endswith("COMMIT;")
    assert "accounting.opening_balance_journal_preparations" in sql
    assert "accounting.create_opening_balance_journal_draft" in sql
    assert "opening_balance_posting_enabled" in sql
    assert "false AS opening_balance_posting_enabled" in sql
    assert "false AS automatic_source_posting_enabled" in sql

    # The migration installs controls only. It must never invoke the preparation
    # function or seed a journal/preparation row during deployment.
    assert "SELECT accounting.create_opening_balance_journal_draft" not in sql
    assert "select accounting.create_opening_balance_journal_draft" not in sql


def test_preparation_requires_review_evidence_balance_and_open_period() -> None:
    sql = migration_sql()
    assert "workbook.status <> 'review_ready'" in sql
    assert "verification_status = 'verified'" in sql
    assert "evidence_note" in sql
    assert "total_debit <> total_credit" in sql
    assert "status = 'open'" in sql
    assert "readiness_status = 'blocked'" in sql
    assert "account.is_active = false OR account.is_posting = false" in sql


def test_generated_draft_is_idempotent_and_system_owned() -> None:
    sql = migration_sql()
    assert "source_event_key" in sql
    assert "'opening_balance:' || p_workbook_id::text" in sql
    assert "FOR UPDATE" in sql
    assert "existing_journal_id" in sql
    assert "source_type" in sql and "'opening_balance'" in sql
    assert "posting_enabled', false" in sql


def test_general_journal_cannot_edit_delete_or_post_opening_balance_draft() -> None:
    sql = migration_sql()
    assert "guard_opening_balance_journal_entry_change" in sql
    assert "guard_opening_balance_journal_line_change" in sql
    assert "opening_balance_post_allowed" in sql
    assert "require the protected opening-balance posting workflow" in sql
    assert "system generated and cannot be edited" in sql
    assert "system generated and immutable" in sql


def test_prepared_workbook_cannot_drift_back_to_draft() -> None:
    sql = migration_sql()
    assert "guard_opening_balance_prepared_workbook_reopen" in sql
    assert "OLD.status = 'review_ready'" in sql
    assert "NEW.status = 'draft'" in sql
    assert "cannot be reopened" in sql
