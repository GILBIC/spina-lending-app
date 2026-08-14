from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VERIFIER = (ROOT / "tools" / "apply_v1_tax_accounting_migrations.py").read_text(
    encoding="utf-8"
)
WORKFLOW = (
    ROOT / ".github" / "workflows" / "v1-tax-accounting-live-verifier.yml"
).read_text(encoding="utf-8")
LOWER = VERIFIER.lower()


def test_live_verifier_applies_only_exact_a62_migrations_in_order() -> None:
    names = [
        "0082_add_v1_tax_evidence_readiness.sql",
        "0083_add_protected_v1_tax_liability_posting.sql",
        "0084_harden_v1_tax_liability_preparation.sql",
        "0085_add_protected_v1_tax_settlement.sql",
        "0086_add_protected_v1_tax_adjustment_reversal.sql",
        "0087_add_protected_v1_tax_additional_amendment.sql",
        "0088_add_protected_v1_tax_additional_settlement.sql",
        "0089_add_protected_v1_tax_recoverable_refund.sql",
        "0090_add_protected_v1_tax_recoverable_credit_application.sql",
    ]
    positions = [VERIFIER.index(name) for name in names]
    assert positions == sorted(positions)
    assert "expected begin/commit wrapper" in LOWER
    assert "accounting.initial_capital_funding_evidence" in LOWER


def test_live_verifier_preserves_operational_and_tax_business_history() -> None:
    for relation in (
        "lending.loans",
        "lending.loan_disbursement_events",
        "lending.collection_transactions",
        "accounting.journal_entries",
        "accounting.journal_lines",
        "accounting.journal_events",
        "core.audit_logs",
        "accounting.v1_tax_rule_evidence",
        "accounting.v1_dst_evidence",
        "accounting.v1_percentage_tax_evidence",
        "accounting.v1_tax_liability_postings",
        "accounting.v1_tax_return_evidence",
        "accounting.v1_tax_payment_evidence",
        "accounting.v1_tax_settlement_postings",
        "accounting.v1_tax_adjustment_postings",
        "accounting.v1_tax_additional_amendment_evidence",
        "accounting.v1_tax_additional_settlement_postings",
        "accounting.v1_tax_recoverable_refund_postings",
        "accounting.v1_tax_recoverable_credit_postings",
    ):
        assert relation in LOWER
    assert "protected_history_unchanged=true" in LOWER
    assert "protected_tax_rows_unchanged=true" in LOWER
    assert "created or removed protected tax business rows" in LOWER


def test_live_verifier_checks_exact_accounts_permissions_and_nonautomatic_controls() -> None:
    for coordinate in (
        '("1010", "cash_office", "asset", "debit", true, true)',
        '("1030", "cash_bank_gcash", "asset", "debit", true, true)',
        '("1130", "tax_recoverable", "asset", "debit", true, true)',
        '("2100", "tax_payables", "liability", "credit", true, true)',
        '("5300", "percentage_tax_lending_expense", "expense", "debit", true, true)',
        '("5310", "documentary_stamp_tax_expense", "expense", "debit", true, true)',
    ):
        assert coordinate in LOWER
    for permission in (
        "accounting.tax.rule_evidence.record",
        "accounting.tax.liability.post",
        "accounting.tax.settlement.post",
        "accounting.tax.adjustment.post",
        "accounting.tax.additional_amendment.post",
        "accounting.tax.additional_settlement.post",
        "accounting.tax.recoverable_refund.post",
        "accounting.tax.recoverable_credit.post",
    ):
        assert permission in LOWER
    assert "evidence_backed_tax_readiness_enabled" in LOWER
    assert "tax_recoverable_refund_realization_enabled" in LOWER
    assert "tax_recoverable_credit_application_enabled" in LOWER
    assert "partial_tax_recoverable_realization_enabled" in LOWER
    assert "automatic_source_posting" in LOWER
    assert "recoverable_flags != (true, true, false, false)" in LOWER


def test_live_verifier_never_calls_business_record_prepare_or_post_functions() -> None:
    # Function names are retained as installation assertions, but the verifier itself
    # must never invoke business workflows or synthesize legal-book evidence.
    for forbidden in (
        "select accounting.record_v1_tax_",
        "select accounting.prepare_v1_tax_",
        "select accounting.post_v1_tax_",
        "insert into accounting.journal_entries",
        "insert into accounting.journal_lines",
        "insert into accounting.v1_tax_",
    ):
        assert forbidden not in LOWER


def test_live_workflow_is_pr_static_and_push_live_on_approved_runner_only() -> None:
    workflow_lower = WORKFLOW.lower()
    assert "pull_request:" in WORKFLOW
    assert "push:" in WORKFLOW
    assert "branches: [main]" in WORKFLOW
    assert "test_v1_tax_live_verifier_contract.py" in WORKFLOW
    assert "apply_v1_tax_accounting_migrations.py" in WORKFLOW
    assert "if: github.event_name == 'push'" in WORKFLOW
    assert "$env:runner_name -ne 'spina-windows'" in workflow_lower
    assert "c:\\github\\spina-lending-app-clean\\.env" in workflow_lower
    assert "c:\\spina_online\\spina_backend\\.env" in workflow_lower
    assert "--database-url-env gilbic_database_url" in workflow_lower
