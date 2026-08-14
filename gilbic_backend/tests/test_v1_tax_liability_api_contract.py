from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "src" / "gilbic_backend" / "v1_tax_liability_api.py").read_text(
    encoding="utf-8"
)
REPOSITORY = (
    ROOT / "src" / "gilbic_backend" / "v1_tax_liability_repository.py"
).read_text(encoding="utf-8")
MAIN = (ROOT / "src" / "gilbic_backend" / "main.py").read_text(encoding="utf-8")


def test_v1_tax_liability_api_is_management_only_strict_and_wired() -> None:
    assert 'model_config = ConfigDict(extra="forbid")' in API
    assert '"management" not in actor.roles' in API
    assert "actor_user_id=actor.user_id" in API
    assert "actor.account_id" not in API
    assert "create_v1_tax_liability_router" in MAIN
    assert "app.include_router(create_v1_tax_liability_router())" in MAIN
    assert "/api/mobile/" not in API


def test_v1_tax_liability_api_uses_action_specific_permissions_and_confirmation() -> None:
    assert (
        'LIABILITY_PREPARE_PERMISSION = "accounting.tax.liability.prepare"'
        in API
    )
    assert 'LIABILITY_POST_PERMISSION = "accounting.tax.liability.post"' in API
    assert API.count("confirm: bool = False") == 2
    assert "_require_confirmation" in API
    assert "v1_tax_liability_confirmation_required" in API


def test_v1_tax_liability_api_exposes_exact_protected_lifecycle_only() -> None:
    for route in (
        '"/api/v1/management/financial-accounting/tax/liabilities"',
        '"/api/v1/management/financial-accounting/tax/liabilities/{tax_type}/{evidence_id}/prepare"',
        '"/api/v1/management/financial-accounting/tax/liabilities/{tax_type}/{evidence_id}/post"',
    ):
        assert route in API
    for field in (
        "confirmation_token",
        "expected_evidence_digest",
        "expected_tax_due",
        "expected_expense_account_code",
        "expected_tax_payable_account_code",
        "expected_posting_date",
        "expected_fiscal_period_id",
    ):
        assert field in API
    assert "Tax liability amount must use exact currency-cent precision." in API
    assert "Tax settlement" in API
    assert "adjustment/reversal" in API


def test_v1_tax_liability_repository_calls_only_protected_database_functions() -> None:
    for function in (
        "accounting.prepare_v1_tax_liability_journal",
        "accounting.post_v1_tax_liability_journal",
    ):
        assert function in REPOSITORY
    assert "accounting.v1_tax_liability_queue" in REPOSITORY
    assert "accounting.v1_tax_liability_summary" in REPOSITORY
    assert "insert into accounting.journal_entries" not in REPOSITORY.lower()
    assert "insert into accounting.journal_lines" not in REPOSITORY.lower()
    assert "accounting.post_journal_entry" not in REPOSITORY


def test_v1_tax_liability_status_surface_keeps_later_controls_explicitly_separate() -> None:
    for status in (
        '"ready"',
        '"prepared"',
        '"posted"',
        '"adjustment_review"',
        '"blocked"',
    ):
        assert status in API
    assert "protected_tax_liability_posting_enabled" in API
    assert "tax_settlement_enabled" in API
    assert "tax_adjustment_reversal_enabled" in API
    assert "automatic_source_posting" in API
