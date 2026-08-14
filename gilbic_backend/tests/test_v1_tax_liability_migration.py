from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "sql" / "0083_add_protected_v1_tax_liability_posting.sql").read_text(
    encoding="utf-8"
)
LOWER = SQL.lower()


def test_v1_tax_liability_migration_is_transactional_management_only_and_reuses_general_journal() -> None:
    assert SQL.strip().startswith("BEGIN;")
    assert SQL.strip().endswith("COMMIT;")
    for permission in (
        "accounting.tax.liability.prepare",
        "accounting.tax.liability.post",
    ):
        assert permission in SQL
    assert "where role.code = 'management'" in LOWER
    assert "accounting.prepare_v1_tax_liability_journal" in LOWER
    assert "accounting.post_v1_tax_liability_journal" in LOWER
    assert "insert into accounting.journal_entries" in LOWER
    assert "insert into accounting.journal_lines" in LOWER
    assert "accounting.post_journal_entry" in LOWER
    assert "automatic_source_posting" in LOWER


def test_v1_tax_liability_uses_frozen_accounts_and_no_parallel_journal() -> None:
    assert "'5300', 'percentage_tax_lending_expense'" in LOWER
    assert "'5310', 'documentary_stamp_tax_expense'" in LOWER
    assert "account.system_key = 'tax_payables'" in LOWER
    assert "payable_account.code <> '2100'" in LOWER
    assert "dr dedicated tax expense / cr 2100 tax payables" in LOWER
    assert "create table if not exists accounting.v1_tax_liability_preparations" in LOWER
    assert "create table if not exists accounting.v1_tax_liability_postings" in LOWER
    assert "create table if not exists accounting.journal_entries" not in LOWER
    assert "create table if not exists accounting.journal_lines" not in LOWER


def test_v1_tax_liability_revalidates_source_rule_period_accounts_and_exact_lines() -> None:
    for fragment in (
        "event_row.is_voided",
        "transaction_row.is_voided",
        "regular_journal_posting_entries",
        "seven_by_seven_journal_postings",
        "later.rule_version > rule_row.rule_version",
        "period_row.status <> 'open'",
        "expense_account.is_active",
        "payable_account.is_active",
        "line_count <> 2",
        "expense_debit <> normalized_tax_due",
        "payable_credit <> normalized_tax_due",
        "foreign_line_count <> 0",
    ):
        assert fragment in LOWER
    assert "percentage_evidence.taxable_lending_receipt_amount * rule_row.rate" in LOWER
    assert "dst_evidence.issue_price * rule_row.rate" in LOWER


def test_v1_tax_liability_is_guarded_idempotent_and_atomic() -> None:
    for fragment in (
        "guard_v1_tax_liability_preparation_write",
        "guard_v1_tax_liability_posting_write",
        "guard_v1_tax_liability_journal_entry_change",
        "guard_v1_tax_liability_journal_line_change",
        "v1-tax-liability:",
        "existing v1 tax-liability posting does not match the immutable retry identity",
        "v1_tax_liability_force_audit_failure",
        "forced v1 tax-liability audit failure",
    ):
        assert fragment in LOWER
    assert "cannot be reversed through the manual general journal" in LOWER
    assert "v1_tax_liability_journal_post_allowed" in LOWER


def test_v1_tax_liability_zero_due_and_later_controls_fail_closed() -> None:
    assert "no positive v1 tax liability is required for zero tax due evidence" in LOWER
    assert "'no_liability_required'" in LOWER
    assert "'posted_adjustment_review_required'" in LOWER
    assert "false as tax_settlement_enabled" in LOWER
    assert "false as tax_adjustment_reversal_enabled" in LOWER
    assert "false as automatic_source_posting" in LOWER
    # This slice recognizes liabilities only. Cash settlement is deliberately deferred.
    assert "tax_settlement_enabled" in LOWER
    assert "cash_bank_gcash" not in LOWER
    assert "cash_office" not in LOWER
