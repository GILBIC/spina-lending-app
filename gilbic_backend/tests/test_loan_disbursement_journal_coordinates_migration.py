from __future__ import annotations

from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0046_add_new_loan_disbursement_journal_coordinates.sql"
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_stage5d20_is_read_only_and_does_not_create_or_post_journals() -> None:
    sql = _sql()
    lowered = sql.lower()

    assert sql.startswith("BEGIN;")
    assert sql.rstrip().endswith("COMMIT;")
    assert "create or replace view accounting.loan_disbursement_journal_coordinates" in lowered
    assert "insert into accounting.journal_entries" not in lowered
    assert "insert into accounting.journal_lines" not in lowered
    assert "accounting.post_journal_entry" not in lowered
    assert "automatic_source_posting" in lowered
    assert "false as journal_draft_enabled" in lowered
    assert "false as automatic_source_posting" in lowered


def test_stage5d20_supports_only_plain_new_regular_cash_coordinates() -> None:
    sql = _sql()

    assert "source_evidence_ready" in sql
    assert "event_kind <> 'new_loan_release'" in sql
    assert "calculation_mode <> 'fixed_daily'" in sql
    assert "settlement_amount <> 0" in sql
    assert "other_deduction_amount <> 0" in sql
    assert "cash_disbursed_amount" in sql
    assert "principal_snapshot" in sql
    assert "loans_receivable_regular" in sql
    assert "cash_office" in sql
    assert "cash_collector_custody" in sql
    assert "cash_bank_gcash" in sql
    assert "fiscal_period_not_open" in sql
    assert "journal_history_exists" in sql
    assert "coordinate_ready" in sql


def test_stage5d20_does_not_enable_7x7_renewal_fee_or_deduction_accounting() -> None:
    lowered = _sql().lower()

    assert "loan_type_policy_review" in lowered
    assert "release_context_policy_review" in lowered
    assert "release_component_policy_review" in lowered
    assert "loans_receivable_7x7" not in lowered
    assert "other_lending_income" not in lowered
    assert "interest_income_7x7" not in lowered
