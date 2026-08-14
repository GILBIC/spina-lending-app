from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SQL = (
    ROOT / "sql" / "0090_add_protected_v1_tax_recoverable_credit_application.sql"
).read_text(encoding="utf-8")
LOWER = SQL.lower()


def test_recoverable_credit_migration_is_transactional_management_only_and_immutable() -> None:
    assert SQL.strip().startswith("BEGIN;")
    assert SQL.strip().endswith("COMMIT;")
    for permission in (
        "accounting.tax.recoverable_credit_evidence.record",
        "accounting.tax.recoverable_credit.prepare",
        "accounting.tax.recoverable_credit.post",
    ):
        assert permission in SQL
    assert "where role.code = 'management'" in LOWER
    assert "guard_v1_tax_recoverable_credit_immutable_write" in LOWER
    assert "immutable" in LOWER


def test_credit_amount_is_derived_full_only_and_targets_exact_unpaid_same_tax_return() -> None:
    for fragment in (
        "adjustment_kind <> 'recognize_settled_tax_recoverable'",
        "adjustment_queue.adjustment_status <> 'posted_settled_tax_recoverable'",
        "recoverable_account.system_key <> 'tax_recoverable'",
        "recoverable_account.code <> '1130'",
        "target_return.tax_type <> adjustment_evidence.tax_type",
        "target_return.declared_tax_due <> adjustment_posting.confirmed_adjustment_amount",
        "credit application is full-only",
        "v1_tax_payment_evidence",
        "v1_tax_settlement_postings",
        "v1_tax_additional_amendment_evidence",
    ):
        assert fragment in LOWER
    assert "p_credit_amount" not in LOWER
    assert "mixed cash-plus-credit" in LOWER
    assert "false as partial_tax_recoverable_realization_enabled" in LOWER


def test_credit_and_refund_cash_settlement_are_mutually_exclusive() -> None:
    assert "guard_v1_tax_recoverable_credit_competing_payment" in LOWER
    assert "cash payment evidence would duplicate settlement" in LOWER
    assert "guard_v1_tax_recoverable_credit_competing_refund" in LOWER
    assert "refund evidence would duplicate realization" in LOWER
    assert "already has immutable cash-refund evidence" in LOWER


def test_credit_journal_is_exact_payable_debit_recoverable_credit_and_manual_bypass_is_blocked() -> None:
    assert "v1_tax_recoverable_credit_application" in LOWER
    assert "insert into accounting.journal_entries" in LOWER
    assert "insert into accounting.journal_lines" in LOWER
    assert "accounting.post_journal_entry" in LOWER
    assert "normalized_payable_code <> '2100'" in LOWER
    assert "normalized_recoverable_code <> '1130'" in LOWER
    assert "payable_debit <> normalized_amount" in LOWER
    assert "recoverable_credit <> normalized_amount" in LOWER
    assert "protected management credit posting function" in LOWER
    assert "posted v1 tax recoverable credit applications cannot be reversed through the manual general journal" in LOWER
    assert "v1_tax_recoverable_credit_force_audit_failure" in LOWER


def test_recoverable_controls_enable_full_refund_and_credit_but_keep_partial_and_auto_off() -> None:
    assert "true as tax_recoverable_refund_realization_enabled" in LOWER
    assert "true as tax_recoverable_credit_application_enabled" in LOWER
    assert "false as partial_tax_recoverable_realization_enabled" in LOWER
    assert "false as automatic_source_posting" in LOWER
    assert "v1_tax_recoverable_controls" in LOWER
