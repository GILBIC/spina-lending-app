from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0106_add_7x7_extra_principal_operational_evidence.sql"
)


def test_extra_principal_persistence_keeps_signed_schedule_immutable() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "seven_by_seven_extra_principal_adjustments" in sql
    assert "seven_by_seven_extra_principal_adjustment_items" in sql
    assert "loan_installment_operational_amounts" in sql
    assert "loan_contract_installments_operational" in sql
    assert "installment.contractual_amount" in sql
    assert "amount_state.operational_amount" in sql
    assert "never rewrite" in sql


def test_extra_principal_persistence_requires_explicit_receipt_intent_and_stale_guard() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "extra_as_principal_reduction" in sql
    assert "transaction.entry_type" in sql
    assert "transaction.is_voided" in sql
    assert "expected_operational_version" in sql
    assert "resulting_operational_version = expected_operational_version + 1" in sql
    assert "operational schedule version is stale" in sql


def test_unused_advance_refund_due_is_separate_immutable_evidence() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "loan_unused_advance_refund_dues" in sql
    assert "advance_retained_after + advance_refund_due" in sql
    assert "= advance_allocated_before" in sql
    assert "requires a separate management-approved refund release workflow" in sql
    assert "never silently netted to another loan" in sql
    assert "lending_unused_advance_refund_due_audit_guard" in sql


def test_active_advance_subtracts_prior_refund_due_without_rewriting_allocations() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "loan_installment_active_advance" in sql
    assert "future_advance_oldest_first" in sql
    assert "gross_advance_allocated" in sql
    assert "refund_due_total" in sql
    assert "active_advance_allocated" in sql
    assert "gross.gross_advance_allocated - coalesce(refunds.refund_due_total, 0)" in sql
