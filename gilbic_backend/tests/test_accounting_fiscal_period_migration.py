from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0022_add_accounting_fiscal_period_management.sql"
).read_text(encoding="utf-8")


def test_fiscal_period_management_adds_permission_and_audit_events() -> None:
    assert "'accounting.period.manage'" in MIGRATION
    assert "CREATE TABLE IF NOT EXISTS accounting.fiscal_period_events" in MIGRATION
    assert "'created'" in MIGRATION
    assert "'status_changed'" in MIGRATION


def test_fiscal_periods_have_database_level_non_overlap_control() -> None:
    assert "accounting_fiscal_periods_no_overlap" in MIGRATION
    assert "EXCLUDE USING gist" in MIGRATION
    assert "daterange(start_date, end_date, '[]') WITH &&" in MIGRATION


def test_fiscal_period_status_changes_use_controlled_transition_function() -> None:
    assert "CREATE OR REPLACE FUNCTION accounting.set_fiscal_period_status" in MIGRATION
    assert "must move to review before it can be closed" in MIGRATION
    assert "can only be reopened or closed" in MIGRATION
    assert "Closed accounting periods are immutable" in MIGRATION
    assert "spina.accounting_period_transition" in MIGRATION


def test_fiscal_period_cannot_close_with_draft_journals() -> None:
    assert "journal.status = 'draft'" in MIGRATION
    assert "cannot close while draft journal entries remain" in MIGRATION


def test_fiscal_period_management_does_not_post_or_backfill_financial_data() -> None:
    lowered = MIGRATION.lower()
    assert "accounting.post_journal_entry(" not in lowered
    assert "from lending.collection_transactions" not in lowered
    assert "from lending.loans" not in lowered
    assert "opening_balance" not in lowered
