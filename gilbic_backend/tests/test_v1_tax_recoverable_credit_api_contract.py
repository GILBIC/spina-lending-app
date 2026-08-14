from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "src" / "gilbic_backend" / "v1_tax_recoverable_credit_api.py").read_text(
    encoding="utf-8"
)
REPOSITORY = (
    ROOT / "src" / "gilbic_backend" / "v1_tax_recoverable_credit_repository.py"
).read_text(encoding="utf-8")
MAIN = (ROOT / "src" / "gilbic_backend" / "main.py").read_text(encoding="utf-8")


def test_recoverable_credit_api_is_management_only_strict_and_wired() -> None:
    assert 'model_config = ConfigDict(extra="forbid")' in API
    assert '"management" not in actor.roles' in API
    assert "actor_user_id=actor.user_id" in API
    assert "actor.account_id" not in API
    assert "create_v1_tax_recoverable_credit_router" in MAIN
    assert "app.include_router(create_v1_tax_recoverable_credit_router())" in MAIN
    assert "/api/mobile/" not in API


def test_recoverable_credit_api_has_action_specific_permissions_and_confirmation() -> None:
    for permission in (
        'EVIDENCE_PERMISSION = "accounting.tax.recoverable_credit_evidence.record"',
        'CREDIT_PREPARE_PERMISSION = "accounting.tax.recoverable_credit.prepare"',
        'CREDIT_POST_PERMISSION = "accounting.tax.recoverable_credit.post"',
    ):
        assert permission in API
    assert API.count("confirm: bool = False") == 2
    assert "_require_confirmation" in API


def test_recoverable_credit_api_exposes_exact_full_only_target_return_coordinates() -> None:
    for route in (
        '"/api/v1/management/financial-accounting/tax/recoverable-credits"',
        '"/api/v1/management/financial-accounting/tax/recoverable-credits/evidence"',
        '"/api/v1/management/financial-accounting/tax/recoverable-credits/{credit_evidence_id}/prepare"',
        '"/api/v1/management/financial-accounting/tax/recoverable-credits/{credit_evidence_id}/post"',
    ):
        assert route in API
    for field in (
        "adjustment_posting_id",
        "target_tax_return_id",
        "application_date",
        "application_reference",
        "authority_reference",
        "confirmation_token",
        "expected_evidence_digest",
        "expected_credit_amount",
        "expected_tax_payable_account_code",
        "expected_tax_recoverable_account_code",
        "expected_posting_date",
        "expected_fiscal_period_id",
    ):
        assert field in API
    assert "credit_amount:" not in API.split("class RecordV1TaxRecoverableCreditEvidenceRequest", 1)[1].split("class Prepare", 1)[0]
    assert "mixed cash-plus-credit" in API.lower()
    assert "partial recoverable realization remain disabled" in API.lower()


def test_recoverable_credit_repository_calls_only_protected_database_functions() -> None:
    for function in (
        "accounting.record_v1_tax_recoverable_credit_evidence",
        "accounting.prepare_v1_tax_recoverable_credit_journal",
        "accounting.post_v1_tax_recoverable_credit_journal",
    ):
        assert function in REPOSITORY
    assert "accounting.v1_tax_recoverable_credit_queue" in REPOSITORY
    assert "accounting.v1_tax_recoverable_credit_summary" in REPOSITORY
    assert "insert into accounting.journal_entries" not in REPOSITORY.lower()
    assert "accounting.post_journal_entry" not in REPOSITORY
