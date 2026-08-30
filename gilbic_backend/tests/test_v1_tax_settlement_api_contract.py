from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "src" / "gilbic_backend" / "v1_tax_settlement_api.py").read_text(
    encoding="utf-8"
)
REPOSITORY = (
    ROOT / "src" / "gilbic_backend" / "v1_tax_settlement_repository.py"
).read_text(encoding="utf-8")
MAIN = (ROOT / "src" / "gilbic_backend" / "main.py").read_text(encoding="utf-8")


def test_v1_tax_settlement_api_is_management_only_strict_and_wired() -> None:
    assert 'model_config = ConfigDict(extra="forbid")' in API
    assert '"management" not in actor.roles' in API
    assert "actor_user_id=actor.user_id" in API
    assert "actor.account_id" not in API
    assert "create_v1_tax_settlement_router" in MAIN
    assert "app.include_router(create_v1_tax_settlement_router())" in MAIN
    assert '"/api/mobile/v1/management/financial-accounting/tax/settlements"' in API


def test_v1_tax_settlement_api_has_action_specific_permissions() -> None:
    for permission in (
        'RETURN_PERMISSION = "accounting.tax.return_evidence.record"',
        'PAYMENT_PERMISSION = "accounting.tax.payment_evidence.record"',
        'SETTLEMENT_PREPARE_PERMISSION = "accounting.tax.settlement.prepare"',
        'SETTLEMENT_POST_PERMISSION = "accounting.tax.settlement.post"',
    ):
        assert permission in API
    assert API.count("confirm: bool = False") == 2
    assert "_require_confirmation" in API


def test_v1_tax_settlement_api_requires_return_composition_and_exact_full_payment() -> (
    None
):
    for field in (
        "return_period_start",
        "return_period_end",
        "filing_date",
        "declared_tax_due",
        "liability_posting_ids",
        "payment_date",
        "payment_amount",
        "cash_account_system_key",
        "payment_reference",
    ):
        assert field in API
    assert 'Literal["cash_office", "cash_bank_gcash"]' in API
    assert "must be unique" in API
    assert "exact currency-cent precision" in API


def test_v1_tax_settlement_api_exposes_only_protected_workflow() -> None:
    for route in (
        '"/api/v1/management/financial-accounting/tax/settlements"',
        '"/api/v1/management/financial-accounting/tax/settlements/returns"',
        '"/api/v1/management/financial-accounting/tax/settlements/returns/{tax_return_id}/payments"',
        '"/api/v1/management/financial-accounting/tax/settlements/payments/{payment_evidence_id}/prepare"',
        '"/api/v1/management/financial-accounting/tax/settlements/payments/{payment_evidence_id}/post"',
    ):
        assert route in API
    for field in (
        "confirmation_token",
        "expected_return_evidence_digest",
        "expected_payment_evidence_digest",
        "expected_payment_amount",
        "expected_tax_payable_account_code",
        "expected_cash_account_code",
        "expected_posting_date",
        "expected_fiscal_period_id",
    ):
        assert field in API


def test_v1_tax_settlement_repository_calls_only_protected_database_functions() -> None:
    for function in (
        "accounting.record_v1_tax_return_evidence",
        "accounting.record_v1_tax_payment_evidence",
        "accounting.prepare_v1_tax_settlement_journal",
        "accounting.post_v1_tax_settlement_journal",
    ):
        assert function in REPOSITORY
    assert "accounting.v1_tax_settlement_effective_queue" in REPOSITORY
    assert "accounting.v1_tax_settlement_effective_summary" in REPOSITORY
    assert "accounting.v1_tax_liability_queue" in REPOSITORY
    assert "accounting.v1_tax_return_liability_items" in REPOSITORY
    assert "accounting_status = 'posted'" in REPOSITORY
    assert "journal_status = 'posted'" in REPOSITORY
    assert "NOT EXISTS" in REPOSITORY
    assert "account.system_key = 'tax_payables'" in REPOSITORY
    assert "account.system_key = 'tax_payable'" not in REPOSITORY
    assert "insert into accounting.journal_entries" not in REPOSITORY.lower()
    assert "accounting.post_journal_entry" not in REPOSITORY


def test_api_surfaces_adjustment_progress_and_keeps_auto_posting_off() -> None:
    for status in (
        '"adjustment_review"',
        '"adjustment_in_progress"',
        '"adjusted"',
    ):
        assert status in API
    assert "tax_settlement_enabled" in API
    assert "tax_adjustment_reversal_enabled" in API
    assert "automatic_source_posting" in API
    assert "tax recoverable" in API.lower()
    assert "additional-tax amendments" in API.lower()
    assert "refund/credit realization" in API.lower()
    assert "automatic source posting remains disabled" in API.lower()


def test_v1_tax_settlement_read_contract_exposes_server_derived_candidates_and_page_coordinates() -> (
    None
):
    for field in (
        '"return_liability_candidates"',
        '"tax_type"',
        '"posting_id"',
        '"evidence_id"',
        '"evidence_version"',
        '"recognition_date"',
        '"tax_due"',
        '"evidence_digest"',
        '"entry_number"',
        '"fiscal_period_id"',
        '"limit"',
        '"offset"',
    ):
        assert field in API
    assert "list_return_liability_candidates" in API
    assert '"return_evidence_record"' in API
    assert '"payment_evidence_record"' in API
