from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SQL = (
    ROOT / "sql" / "0089_add_protected_v1_tax_recoverable_refund.sql"
).read_text(encoding="utf-8")
LOWER = SQL.lower()


def test_recoverable_refund_migration_is_transactional_management_only_and_immutable() -> None:
    assert SQL.strip().startswith("BEGIN;")
    assert SQL.strip().endswith("COMMIT;")
    for permission in (
        "accounting.tax.recoverable_refund_evidence.record",
        "accounting.tax.recoverable_refund.prepare",
        "accounting.tax.recoverable_refund.post",
    ):
        assert permission in SQL
    assert "where role.code = 'management'" in LOWER
    assert "guard_v1_tax_recoverable_refund_immutable_write" in LOWER
    assert "immutable" in LOWER


def test_refund_amount_is_derived_from_exact_posted_1130_recoverable() -> None:
    for fragment in (
        "adjustment_kind <> 'recognize_settled_tax_recoverable'",
        "adjustment_queue.adjustment_status <> 'posted_settled_tax_recoverable'",
        "recoverable_account.system_key <> 'tax_recoverable'",
        "recoverable_account.code <> '1130'",
        "adjustment_posting.confirmed_adjustment_amount",
        "this exact tax recoverable already has immutable refund realization evidence",
    ):
        assert fragment in LOWER
    assert "p_refund_amount" not in LOWER
    assert "partial_tax_recoverable_realization_enabled" in LOWER
    assert "false as partial_tax_recoverable_realization_enabled" in LOWER


def test_refund_journal_is_exact_cash_debit_recoverable_credit_and_manual_bypass_is_blocked() -> None:
    assert "v1_tax_recoverable_refund" in LOWER
    assert "insert into accounting.journal_entries" in LOWER
    assert "insert into accounting.journal_lines" in LOWER
    assert "accounting.post_journal_entry" in LOWER
    assert "cash_account.code not in ('1010', '1030')" in LOWER
    assert "recoverable_account.code <> normalized_recoverable_code" in LOWER
    assert "cash_debit <> normalized_amount" in LOWER
    assert "recoverable_credit <> normalized_amount" in LOWER
    assert "protected management refund posting function" in LOWER
    assert "posted v1 tax recoverable refunds cannot be reversed through the manual general journal" in LOWER
    assert "v1_tax_recoverable_refund_force_audit_failure" in LOWER


def test_refund_controls_keep_credit_application_and_auto_posting_disabled() -> None:
    assert "true as tax_recoverable_refund_realization_enabled" in LOWER
    assert "false as tax_recoverable_credit_application_enabled" in LOWER
    assert "false as automatic_source_posting" in LOWER
    assert "v1_tax_recoverable_controls" in LOWER
