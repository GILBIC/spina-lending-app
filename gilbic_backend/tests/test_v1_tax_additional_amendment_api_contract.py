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
    assert "/api/mobile/" not in API


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
