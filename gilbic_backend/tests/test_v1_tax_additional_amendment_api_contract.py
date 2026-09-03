from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = (
    ROOT / "src" / "gilbic_backend" / "v1_tax_additional_amendment_api.py"
).read_text(encoding="utf-8")
REPOSITORY = (
    ROOT / "src" / "gilbic_backend" / "v1_tax_additional_amendment_repository.py"
).read_text(encoding="utf-8")
MAIN = (ROOT / "src" / "gilbic_backend" / "main.py").read_text(encoding="utf-8")


def test_additional_amendment_api_is_management_only_strict_and_wired() -> None:
    assert 'model_config = ConfigDict(extra="forbid")' in API
    assert '"management" not in actor.roles' in API
    assert "actor_user_id=actor.user_id" in API
    assert "actor.account_id" not in API
    assert "create_v1_tax_additional_amendment_router" in MAIN
    assert "app.include_router(create_v1_tax_additional_amendment_router())" in MAIN
    assert '"/api/mobile/v1/management/financial-accounting/tax/additional-amendments"' in API


def test_additional_amendment_api_has_action_specific_permissions_and_confirmation() -> None:
    for permission in (
        'AMENDMENT_EVIDENCE_PERMISSION = "accounting.tax.additional_amendment_evidence.record"',
        'AMENDMENT_PREPARE_PERMISSION = "accounting.tax.additional_amendment.prepare"',
        'AMENDMENT_POST_PERMISSION = "accounting.tax.additional_amendment.post"',
        'PAYMENT_EVIDENCE_PERMISSION = "accounting.tax.additional_payment_evidence.record"',
        'SETTLEMENT_PREPARE_PERMISSION = "accounting.tax.additional_settlement.prepare"',
        'SETTLEMENT_POST_PERMISSION = "accounting.tax.additional_settlement.post"',
    ):
        assert permission in API
    assert API.count("confirm: bool = False") == 4
    assert "_require_confirmation" in API


def test_additional_amendment_api_exposes_exact_retained_evidence_lifecycle() -> None:
    for route in (
        '"/api/v1/management/financial-accounting/tax/additional-amendments"',
        '"/api/v1/management/financial-accounting/tax/additional-amendments/evidence"',
        '"/api/v1/management/financial-accounting/tax/additional-amendments/{amendment_evidence_id}/prepare-liability"',
        '"/api/v1/management/financial-accounting/tax/additional-amendments/{amendment_evidence_id}/post-liability"',
        '"/api/v1/management/financial-accounting/tax/additional-amendments/{amendment_evidence_id}/payment-evidence"',
        '"/api/v1/management/financial-accounting/tax/additional-amendments/{amendment_evidence_id}/prepare-settlement"',
        '"/api/v1/management/financial-accounting/tax/additional-amendments/{amendment_evidence_id}/post-settlement"',
    ):
        assert route in API
        assert route.replace('/api/v1/', '/api/mobile/v1/') in API
    for field in (
        "tax_return_id",
        "tax_liability_posting_id",
        "replacement_evidence_id",
        "amendment_basis",
        "amendment_date",
        "recognition_date",
        "expected_original_declared_tax_due",
        "expected_revised_declared_tax_due",
        "expected_original_item_tax_due",
        "expected_replacement_item_tax_due",
        "expected_additional_tax_due",
        "cash_account_system_key",
        "expected_additional_liability_confirmation_digest",
        "expected_payment_evidence_digest",
    ):
        assert field in API
    assert "amended_return" in API
    assert "additional_assessment" in API


def test_additional_amendment_read_contract_exposes_server_derived_candidates() -> None:
    for field in (
        '"amendment_candidates"',
        '"amendment_status": amendment_status',
        '"limit": limit',
        '"offset": offset',
        '"tax_additional_amendment_enabled": True',
        '"tax_additional_settlement_enabled": True',
        '"tax_refund_credit_realization_enabled": False',
        '"automatic_source_posting": False',
    ):
        assert field in API
    assert "list_amendment_candidates" in API
    for field in (
        "tax_return_id",
        "tax_liability_posting_id",
        "original_evidence_id",
        "replacement_evidence_id",
        "original_declared_tax_due",
        "revised_declared_tax_due",
        "additional_tax_due",
        "payment_basis",
        "payment_required_amount",
        "filing_date",
        "recognition_date",
        "original_fiscal_period_id",
        "original_fiscal_period_start",
        "original_fiscal_period_end",
    ):
        assert field in API


def test_additional_amendment_candidates_are_exact_read_only_relationships() -> None:
    for fragment in (
        "class V1TaxAdditionalAmendmentCandidate",
        "accounting.v1_tax_return_liability_items",
        "accounting.v1_tax_return_evidence",
        "original.accounting_status = 'posted_adjustment_review_required'",
        "replacement.evidence_status = 'evidence_ready'",
        "replacement.accounting_status = 'evidence_ready'",
        "replacement.tax_due > original.tax_due",
        "period.status = 'open'",
        "accounting.v1_tax_adjustment_evidence",
        "accounting.v1_tax_additional_amendment_evidence",
        "payment.id IS NULL",
        "settlement_journal.status = 'posted'",
    ):
        assert fragment in REPOSITORY
    assert "cash_office" in API and "cash_bank_gcash" in API


def test_additional_amendment_repository_calls_only_protected_database_functions() -> None:
    for function in (
        "accounting.record_v1_tax_additional_amendment_evidence",
        "accounting.prepare_v1_tax_additional_liability_journal",
        "accounting.post_v1_tax_additional_liability_journal",
        "accounting.record_v1_tax_additional_payment_evidence",
        "accounting.prepare_v1_tax_additional_settlement_journal",
        "accounting.post_v1_tax_additional_settlement_journal",
    ):
        assert function in REPOSITORY
    assert "accounting.v1_tax_additional_amendment_queue" in REPOSITORY
    assert "accounting.v1_tax_additional_amendment_summary" in REPOSITORY
    assert "insert into accounting.journal_entries" not in REPOSITORY.lower()
    assert "accounting.post_journal_entry" not in REPOSITORY


def test_api_keeps_refund_credit_closed_period_and_partial_payment_outside_this_slice() -> None:
    lower = API.lower()
    assert "tax recoverable refund/credit realization" in lower
    assert "closed-period correction treatment" in lower
    assert "partial tax payments" in lower
    assert "automatic source posting remains disabled" in lower
