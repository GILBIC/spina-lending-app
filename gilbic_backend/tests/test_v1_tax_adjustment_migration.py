from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "sql" / "0086_add_protected_v1_tax_adjustment_reversal.sql").read_text(
    encoding="utf-8"
)
LOWER = SQL.lower()


def test_v1_tax_adjustment_core_is_transactional_management_only_and_immutable() -> None:
    assert SQL.strip().startswith("BEGIN;")
    assert SQL.strip().endswith("COMMIT;")
    for permission in (
        "accounting.tax.adjustment_evidence.record",
        "accounting.tax.adjustment.prepare",
        "accounting.tax.adjustment.post",
    ):
        assert permission in SQL
    assert "where role.code = 'management'" in LOWER
    for name in (
        "v1_tax_adjustment_evidence",
        "v1_tax_adjustment_preparations",
        "v1_tax_adjustment_postings",
        "guard_v1_tax_adjustment_immutable_write",
    ):
        assert name in LOWER


def test_unsettled_stale_liability_requires_full_protected_reversal() -> None:
    assert "reverse_unsettled_liability" in LOWER
    assert "linked_payment_id is not null" in LOWER
    assert "adjustment_amount_value := original_posting.confirmed_tax_due" in LOWER
    assert "debit_account := payable_account" in LOWER
    assert "credit_account := expense_account" in LOWER
    assert "reversal_of_entry_id" in LOWER
    assert "exact still-open original liability fiscal period" in LOWER
    assert "dr 2100 tax payables / cr original dedicated tax expense" in LOWER


def test_settled_tax_decrease_recognizes_recoverable_without_rewriting_cash() -> None:
    assert "recognize_settled_tax_recoverable" in LOWER
    assert "('1130', 'tax_recoverable', 'tax recoverable'" in LOWER
    assert "replacement_queue.tax_due >= original_posting.confirmed_tax_due" in LOWER
    assert "debit_account := recoverable_account" in LOWER
    assert "credit_account := expense_account" in LOWER
    assert "dr 1130 tax recoverable / cr original dedicated tax expense" in LOWER
    assert "original settlement history is preserved" in LOWER


def test_adjustment_revalidates_exact_replacement_and_blocks_duplicate_full_liability() -> None:
    assert "replacement tax evidence must be the exact newer current unposted evidence" in LOWER
    assert "replacement evidence is already covered by a posted settled-tax-recoverable adjustment" in LOWER
    assert "covered_by_settled_adjustment" in LOWER
    assert "posted_adjusted_reversed" in LOWER
    assert "posted_adjusted_recoverable" in LOWER


def test_adjustment_is_idempotent_guarded_atomic_and_never_auto_posts() -> None:
    for fragment in (
        "immutable retry identity",
        "v1_tax_adjustment_force_audit_failure",
        "forced v1 tax adjustment audit failure",
        "v1_tax_adjustment_journal_prepare_allowed",
        "v1_tax_adjustment_journal_post_allowed",
        "manual general journal",
        "false as automatic_source_posting",
        "true as tax_adjustment_reversal_enabled",
    ):
        assert fragment in LOWER


def test_additional_tax_and_refund_credit_realization_stay_explicitly_outside_core() -> None:
    assert "additional-tax amendments" in LOWER
    assert "refund/credit realization" in LOWER
    assert "separate explicit" in LOWER
