from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API = (
    ROOT / "src" / "gilbic_backend" / "v1_tax_recoverable_refund_api.py"
).read_text(encoding="utf-8")
REPOSITORY = (
    ROOT / "src" / "gilbic_backend" / "v1_tax_recoverable_refund_repository.py"
).read_text(encoding="utf-8")
MAIN = (ROOT / "src" / "gilbic_backend" / "main.py").read_text(encoding="utf-8")


def test_recoverable_refund_api_is_management_only_strict_and_wired() -> None:
    assert 'model_config = ConfigDict(extra="forbid")' in API
    assert '"management" not in actor.roles' in API
    assert "actor_user_id=actor.user_id" in API
    assert "actor.account_id" not in API
    assert "create_v1_tax_recoverable_refund_router" in MAIN
    assert "app.include_router(create_v1_tax_recoverable_refund_router())" in MAIN
    assert "/api/mobile/" not in API


def test_recoverable_refund_api_uses_action_specific_permissions_and_confirmation() -> None:
    for permission in (
        'EVIDENCE_PERMISSION = "accounting.tax.recoverable_refund_evidence.record"',
        'REFUND_PREPARE_PERMISSION = "accounting.tax.recoverable_refund.prepare"',
        'REFUND_POST_PERMISSION = "accounting.tax.recoverable_refund.post"',
    ):
        assert permission in API
    assert API.count("confirm: bool = False") == 2
    assert "_require_confirmation" in API


def test_recoverable_refund_api_exposes_exact_evidence_and_confirmed_coordinates_only() -> None:
    for route in (
        '"/api/v1/management/financial-accounting/tax/recoverable-refunds"',
        '"/api/v1/management/financial-accounting/tax/recoverable-refunds/evidence"',
        '"/api/v1/management/financial-accounting/tax/recoverable-refunds/{refund_evidence_id}/prepare"',
        '"/api/v1/management/financial-accounting/tax/recoverable-refunds/{refund_evidence_id}/post"',
    ):
        assert route in API
    for field in (
        "adjustment_posting_id",
        "refund_date",
        "cash_account_code",
        "refund_reference",
        "authority_reference",
        "evidence_digest",
        "confirmation_token",
        "expected_refund_amount",
        "expected_cash_account_code",
        "expected_tax_recoverable_account_code",
        "expected_posting_date",
        "expected_fiscal_period_id",
    ):
        assert field in API
    assert 'Literal["1010", "1030"]' in API
    assert 'Literal["1130"]' in API
    assert "refund_amount:" not in API.split("class RecordV1TaxRecoverableRefundEvidenceRequest", 1)[1].split("class PrepareV1TaxRecoverableRefundRequest", 1)[0]


def test_recoverable_refund_repository_calls_only_protected_database_functions() -> None:
    for function in (
        "accounting.record_v1_tax_recoverable_refund_evidence",
        "accounting.prepare_v1_tax_recoverable_refund_journal",
        "accounting.post_v1_tax_recoverable_refund_journal",
    ):
        assert function in REPOSITORY
    assert "accounting.v1_tax_recoverable_refund_queue" in REPOSITORY
    assert "accounting.v1_tax_recoverable_refund_summary" in REPOSITORY
    assert "insert into accounting.journal_entries" not in REPOSITORY.lower()
    assert "accounting.post_journal_entry" not in REPOSITORY


def test_api_keeps_credit_application_partial_realization_and_auto_posting_disabled() -> None:
    assert "tax-credit application" in API.lower()
    assert "partial recoverable realization remain disabled" in API.lower()
    assert "automatic source posting remains disabled" in API.lower()
    assert "tax_recoverable_credit_application_enabled" in API
    assert "automatic_source_posting" in API
