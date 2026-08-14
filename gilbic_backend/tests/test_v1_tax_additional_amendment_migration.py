from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SQL_0087 = (ROOT / "sql" / "0087_add_protected_v1_tax_additional_amendment.sql").read_text(
    encoding="utf-8"
)
SQL_0088 = (ROOT / "sql" / "0088_add_protected_v1_tax_additional_settlement.sql").read_text(
    encoding="utf-8"
)
LOWER_87 = SQL_0087.lower()
LOWER_88 = SQL_0088.lower()


def test_additional_amendment_migrations_are_transactional_management_only_and_explicit() -> None:
    for source in (SQL_0087, SQL_0088):
        assert source.strip().startswith("BEGIN;")
        assert source.strip().endswith("COMMIT;")
    for permission in (
        "accounting.tax.additional_amendment_evidence.record",
        "accounting.tax.additional_amendment.prepare",
        "accounting.tax.additional_amendment.post",
    ):
        assert permission in SQL_0087
    for permission in (
        "accounting.tax.additional_payment_evidence.record",
        "accounting.tax.additional_settlement.prepare",
        "accounting.tax.additional_settlement.post",
    ):
        assert permission in SQL_0088
    assert "where role.code = 'management'" in LOWER_87
    assert "where role.code = 'management'" in LOWER_88


def test_amendment_evidence_requires_exact_filed_return_and_strictly_higher_replacement() -> None:
    for fragment in (
        "v1_tax_additional_amendment_evidence",
        "tax_return_id uuid not null unique",
        "tax_liability_posting_id uuid not null unique",
        "replacement_item_tax_due > original_item_tax_due",
        "revised_declared_tax_due = original_declared_tax_due + additional_tax_due",
        "full_revised_return_unpaid",
        "additional_due_after_settlement",
        "additional-tax amendment supports exactly one stale upward liability per retained return",
        "strictly higher tax amount",
        "exact original liability fiscal period to remain open",
    ):
        assert fragment in LOWER_87


def test_additional_liability_reuses_general_journal_for_delta_only() -> None:
    assert "prepare_v1_tax_additional_liability_journal" in LOWER_87
    assert "post_v1_tax_additional_liability_journal" in LOWER_87
    assert "insert into accounting.journal_entries" in LOWER_87
    assert "insert into accounting.journal_lines" in LOWER_87
    assert "accounting.post_journal_entry" in LOWER_87
    assert "expense_account.id" in LOWER_87
    assert "payable_account.id" in LOWER_87
    assert "evidence.additional_tax_due" in LOWER_87
    assert "payable_account.code <> '2100'" in LOWER_87
    assert "v1_tax_additional_liability_force_audit_failure" in LOWER_87
    assert "duplicate full liability" in LOWER_87
    assert "create table if not exists accounting.journal_entries" not in LOWER_87
    assert "1130" not in LOWER_87


def test_additional_payment_and_settlement_are_separate_exact_evidence() -> None:
    for fragment in (
        "v1_tax_additional_payment_evidence",
        "record_v1_tax_additional_payment_evidence",
        "payment.payment_amount <> evidence.payment_required_amount",
        "partial payment is not inferred",
        "cash_account.code not in ('1010', '1030')",
        "prepare_v1_tax_additional_settlement_journal",
        "post_v1_tax_additional_settlement_journal",
        "v1_tax_additional_settlement_force_audit_failure",
        "v1_tax_additional_amendment_queue",
        "additional_tax_settled",
    ):
        assert fragment in LOWER_88
    assert "accounting.post_journal_entry" in LOWER_88
    assert "payable_account.code <> '2100'" in LOWER_88
    assert "1130" not in LOWER_88


def test_new_path_preserves_old_history_and_keeps_refund_auto_posting_disabled() -> None:
    assert "false as automatic_source_posting" in LOWER_87
    assert "false as automatic_source_posting" in LOWER_88
    assert "false as tax_refund_credit_realization_enabled" in LOWER_88
    assert "original return/liability/settlement history" in LOWER_87
    assert "tax recoverable realization remains disabled" in LOWER_88
    assert "posted v1 additional-tax liabilities cannot be reversed through the manual general journal" in LOWER_87
    assert "posted v1 additional-tax settlements cannot be reversed through the manual general journal" in LOWER_88
