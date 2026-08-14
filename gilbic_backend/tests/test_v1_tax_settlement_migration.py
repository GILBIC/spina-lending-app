from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "sql" / "0085_add_protected_v1_tax_settlement.sql").read_text(
    encoding="utf-8"
)
LOWER = SQL.lower()


def test_v1_tax_settlement_is_transactional_management_only_and_evidence_backed() -> None:
    assert SQL.strip().startswith("BEGIN;")
    assert SQL.strip().endswith("COMMIT;")
    for permission in (
        "accounting.tax.return_evidence.record",
        "accounting.tax.payment_evidence.record",
        "accounting.tax.settlement.prepare",
        "accounting.tax.settlement.post",
    ):
        assert permission in SQL
    assert "where role.code = 'management'" in LOWER
    assert "record_v1_tax_return_evidence" in LOWER
    assert "record_v1_tax_payment_evidence" in LOWER
    assert "prepare_v1_tax_settlement_journal" in LOWER
    assert "post_v1_tax_settlement_journal" in LOWER


def test_return_evidence_aggregates_exact_current_posted_liabilities() -> None:
    for fragment in (
        "v1_tax_return_evidence",
        "v1_tax_return_liability_items",
        "tax_liability_posting_id uuid not null unique",
        "queue.accounting_status = 'posted'",
        "liability_total <> normalized_due",
        "already assigned to another immutable tax return",
    ):
        assert fragment in LOWER
    assert "partial payments require a later explicit policy" in LOWER


def test_payment_evidence_uses_only_exact_approved_real_cash_bank_accounts() -> None:
    assert "normalized_cash_key not in ('cash_office', 'cash_bank_gcash')" in LOWER
    assert "cash_account.code not in ('1010', '1030')" in LOWER
    assert "payment_amount <> tax_return.declared_tax_due" in LOWER
    assert "v1_tax_payment_evidence" in LOWER
    assert "corrections require the protected tax adjustment/reversal workflow" in LOWER


def test_settlement_reuses_general_journal_and_never_reexpenses_tax() -> None:
    assert "insert into accounting.journal_entries" in LOWER
    assert "insert into accounting.journal_lines" in LOWER
    assert "accounting.post_journal_entry" in LOWER
    assert "settle retained tax payable" in LOWER
    assert "tax payment from " in LOWER
    assert "dr 2100 tax payables / cr approved cash-bank account" in LOWER
    assert "5300" not in LOWER
    assert "5310" not in LOWER
    assert "create table if not exists accounting.journal_entries" not in LOWER
    assert "create table if not exists accounting.journal_lines" not in LOWER


def test_settlement_is_immutable_idempotent_guarded_and_atomic() -> None:
    for fragment in (
        "guard_v1_tax_settlement_immutable_write",
        "guard_v1_tax_settlement_journal_entry_change",
        "guard_v1_tax_settlement_journal_line_change",
        "v1-tax-settlement:",
        "immutable retry identity",
        "v1_tax_settlement_force_audit_failure",
        "forced v1 tax settlement audit failure",
        "cannot be reversed through the manual general journal",
    ):
        assert fragment in LOWER


def test_settlement_keeps_adjustment_and_automatic_posting_disabled() -> None:
    assert "true as tax_settlement_enabled" in LOWER
    assert "false as tax_adjustment_reversal_enabled" in LOWER
    assert "false as automatic_source_posting" in LOWER
    assert "settled_adjustment_review_required" in LOWER
