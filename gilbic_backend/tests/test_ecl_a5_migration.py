from __future__ import annotations

from pathlib import Path


SQL = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0079_add_ecl_remeasurement_writeoff_recovery.sql"
).read_text(encoding="utf-8")
LOWER = SQL.lower()
UPPER = SQL.upper()


def test_a5_migration_is_transactional_and_management_protected() -> None:
    assert SQL.strip().startswith("BEGIN;")
    assert SQL.strip().endswith("COMMIT;")
    for permission in (
        "accounting.ecl.remeasurement.post",
        "accounting.ecl.writeoff.post",
        "accounting.ecl.recovery.post",
    ):
        assert permission in SQL
    assert "require_ecl_a5_management_actor" in LOWER
    assert "where role.code = 'management'" in LOWER


def test_a5_preserves_immutable_history_and_has_explicit_audit_tables() -> None:
    for relation in (
        "accounting.ecl_allowance_remeasurements",
        "accounting.ecl_accounting_writeoffs",
        "accounting.ecl_post_writeoff_recoveries",
    ):
        assert relation in LOWER
    assert "guard_ecl_a5_audit_write" in LOWER
    assert "immutable" in LOWER
    assert "update accounting.ecl_quantitative_measurements" not in LOWER
    assert "delete from accounting.ecl_quantitative_measurements" not in LOWER
    assert "update accounting.ecl_allowance_postings" not in LOWER
    assert "delete from accounting.ecl_allowance_postings" not in LOWER
    assert "update accounting.ecl_credit_risk_label_reviews" not in LOWER
    assert "delete from accounting.ecl_credit_risk_label_reviews" not in LOWER


def test_a5_remeasurement_uses_only_exact_new_measurement_and_5000_1190_delta() -> None:
    assert "post_ecl_allowance_remeasurement" in LOWER
    assert "ecl_allowance_remeasurement_posting_v1" in SQL
    assert "measurement_status <> 'measured_read_only'" in LOWER
    assert "authoritative_ecl_amount is distinct from target_amount" in LOWER
    assert "ecl_loan_allowance_balance(measurement.loan_id)" in LOWER
    assert "'credit_loss_expense'" in LOWER
    assert "'allowance_expected_credit_loss'" in LOWER
    assert "when delta > 0 then 'increase'" in LOWER
    assert "when target_amount = 0 then 'full_reversal'" in LOWER
    assert "'ecl allowance decrease/reversal'" in LOWER
    assert "'credit-loss impairment gain/reversal'" in LOWER


def test_a5_full_writeoff_requires_stage3_default_support_and_exact_full_cover() -> None:
    assert "post_ecl_full_writeoff" in LOWER
    assert "ecl_full_writeoff_posting_v1" in SQL
    assert "stage_3_credit_impaired" in SQL
    assert "supported_no_reasonable_expectation_of_recovery" in SQL
    assert "authoritative_ecl_amount is distinct from gross_amount" in LOWER
    assert "allowance_amount <> gross_amount" in LOWER
    assert "gross_carrying_amount = loan_component + accrued_interest_component" in LOWER
    assert "loans_receivable_regular" in LOWER
    assert "loans_receivable_7x7" in LOWER
    assert "accrued_interest_receivable" in LOWER
    assert "use protected ecl allowance on full write-off" in LOWER
    assert "derecognize loan receivable on full write-off" in LOWER
    # V1 intentionally does not invent a partial write-off amount.
    assert "partial_writeoff" not in LOWER
    assert "partial write-off" not in LOWER


def test_a5_post_writeoff_recovery_uses_exact_protected_cash_and_no_receivable_recreation() -> None:
    assert "post_ecl_post_writeoff_recovery" in LOWER
    assert "ecl_post_writeoff_recovery_posting_v1" in SQL
    assert "cash_recovery_observed" in SQL
    assert "tx.accepted_at <= writeoff.posted_at" in LOWER
    assert "regular_journal_posting_entries" in LOWER
    assert "seven_by_seven_journal_postings" in LOWER
    assert "cash_collector_custody" in LOWER
    assert "credit_loss_expense" in LOWER
    recovery_body = LOWER.split("create or replace function accounting.post_ecl_post_writeoff_recovery", 1)[1]
    assert "loans_receivable_regular" not in recovery_body
    assert "loans_receivable_7x7" not in recovery_body
    assert "accrued_interest_receivable" not in recovery_body


def test_a5_blocks_generic_bypass_and_keeps_automatic_posting_off() -> None:
    assert "guard_ecl_a5_journal_entry_change" in LOWER
    assert "cannot be reversed through the manual general journal" in LOWER
    assert "guard_ecl_a5_journal_line_change" in LOWER
    assert "ecl_a5_force_audit_failure" in LOWER
    assert "forced a5 audit failure" in LOWER
    assert "false as automatic_source_posting" in LOWER
    assert "automatic_source_posting', false" in LOWER
    assert "automatic_source_posting', true" not in LOWER
    assert "automatic_source_posting = true" not in LOWER
    assert "automatic_source_posting=true" not in LOWER
