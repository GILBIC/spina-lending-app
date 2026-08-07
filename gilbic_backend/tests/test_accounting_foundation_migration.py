from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0021_add_accounting_foundation.sql"
).read_text(encoding="utf-8")


def test_accounting_foundation_creates_separate_schema_and_chart() -> None:
    assert "CREATE SCHEMA IF NOT EXISTS accounting" in MIGRATION
    assert "CREATE TABLE IF NOT EXISTS accounting.accounts" in MIGRATION
    assert "CREATE TABLE IF NOT EXISTS accounting.fiscal_periods" in MIGRATION
    assert "CREATE TABLE IF NOT EXISTS accounting.journal_entries" in MIGRATION
    assert "CREATE TABLE IF NOT EXISTS accounting.journal_lines" in MIGRATION
    assert "'loans_receivable_regular'" in MIGRATION
    assert "'loans_receivable_7x7'" in MIGRATION
    assert "'interest_income_regular'" in MIGRATION
    assert "'interest_income_7x7'" in MIGRATION
    assert "'allowance_expected_credit_loss'" in MIGRATION


def test_accounting_foundation_requires_balanced_immutable_posting() -> None:
    assert "total_debit <> total_credit" in MIGRATION
    assert "A journal entry requires at least two lines" in MIGRATION
    assert "Posted journal entries are immutable" in MIGRATION
    assert "Lines of a posted journal entry are immutable" in MIGRATION
    assert "Journal entries can only be posted to an open accounting period" in MIGRATION
    assert "Accounting fiscal periods cannot overlap" in MIGRATION
    assert "source_event_key TEXT UNIQUE" in MIGRATION


def test_accounting_foundation_uses_reversal_instead_of_editing_posted_entry() -> None:
    assert "CREATE OR REPLACE FUNCTION accounting.create_reversal_draft" in MIGRATION
    assert "reversal_of_entry_id UUID UNIQUE" in MIGRATION
    assert "debit,\n        credit" in MIGRATION
    assert "credit,\n        debit" in MIGRATION


def test_accounting_foundation_does_not_backfill_live_financial_records() -> None:
    lowered = MIGRATION.lower()
    assert "insert into accounting.journal_entries" in lowered
    assert "from lending.collection_transactions" not in lowered
    assert "from lending.loans" not in lowered
    assert "opening_balance" not in lowered
