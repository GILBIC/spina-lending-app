from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "sql" / "0118_add_7x7_post_maturity_penalty_authority.sql"


def _migration_source() -> str:
    assert MIGRATION.is_file(), (
        "Priority #6 requires forward migration 0118 for the approved 7x7 "
        "post-maturity penalty authority/evidence layer."
    )
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_priority6_post_maturity_penalty_migration_exists() -> None:
    assert MIGRATION.is_file(), (
        "Priority #6 requires forward migration 0118 for the approved 7x7 "
        "post-maturity penalty authority/evidence layer."
    )


def test_priority6_penalty_authority_is_terms_bound_and_complete() -> None:
    source = _migration_source()

    assert "seven_by_seven_pricing_compliance_reviews" in source
    assert "penalty_policy_version" in source
    assert "penalty_monthly_rate" in source
    assert "penalty_proration_days" in source
    assert "penalty_rate_ceiling" in source
    assert "lifetime_nonprincipal_cost_ceiling" in source
    assert "counted_nonprincipal_cost_at_contract_lock" in source


def test_priority6_penalty_assessment_and_payment_evidence_is_append_only() -> None:
    source = _migration_source()

    assert "seven_by_seven_penalty_assessments" in source
    assert "seven_by_seven_penalty_payment_allocations" in source
    assert "terms_fingerprint" in source
    assert "assessed_through_date" in source
    assert "opening_penalty_base" in source
    assert "theoretical_penalty_exact" in source
    assert "opening_cost_headroom" in source
    assert "assessed_penalty_amount" in source
    assert "source_transaction_id" in source
    assert "before update or delete" in source
    assert "immutable" in source


def test_priority6_penalty_receipt_allocation_is_guarded_against_overapplication() -> None:
    source = _migration_source()

    assert "loan_installment_payment_allocations" in source
    assert "seven_by_seven_penalty_payment_allocations" in source
    assert "collection_transactions" in source
    assert "amount_applied" in source
    assert "for update" in source
    assert "cannot exceed" in source or "must not exceed" in source


def test_priority6_penalty_accounting_view_is_read_only_evidence() -> None:
    source = _migration_source()

    assert "accounting.seven_by_seven_penalty_evidence" in source
    assert "assessed_penalty" in source
    assert "penalty_paid" in source
    assert "penalty_outstanding" in source
    assert "ready_to_post" in source
    assert "false" in source
