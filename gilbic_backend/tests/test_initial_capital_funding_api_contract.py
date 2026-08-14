from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "src" / "gilbic_backend" / "initial_capital_funding_api.py").read_text(
    encoding="utf-8"
)
REPOSITORY = (
    ROOT / "src" / "gilbic_backend" / "initial_capital_funding_repository.py"
).read_text(encoding="utf-8")
MAIN = (ROOT / "src" / "gilbic_backend" / "main.py").read_text(encoding="utf-8")


def test_initial_capital_api_is_management_only_strict_and_explicit() -> None:
    assert 'model_config = ConfigDict(extra="forbid")' in API
    assert '"management" not in actor.roles' in API
    assert "accounting.initial_capital.evidence.record" in API
    assert "accounting.initial_capital.prepare" in API
    assert "accounting.initial_capital.post" in API
    assert "actor.user_id" in API
    assert "confirm: bool = False" in API
    assert "confirmation_token" in API
    assert "expected_evidence_digest" in API
    assert "expected_amount" in API
    assert "expected_cash_account_code" in API
    assert "expected_posting_date" in API
    assert "expected_fiscal_period_id" in API


def test_initial_capital_api_exposes_no_automatic_or_synthetic_opening_balance_path() -> None:
    assert "/api/v1/management/financial-accounting/initial-capital-funding" in API
    assert "synthetic opening balance" in API
    assert "never posts automatically" in API
    assert "/api/mobile/" not in API
    assert "create_initial_capital_funding_router" in MAIN
    assert "app.include_router(create_initial_capital_funding_router())" in MAIN


def test_initial_capital_repository_calls_only_protected_database_functions() -> None:
    assert "record_initial_capital_funding_evidence" in REPOSITORY
    assert "prepare_initial_capital_funding_journal" in REPOSITORY
    assert "post_initial_capital_funding_journal" in REPOSITORY
    assert "create_manual_journal_draft" not in REPOSITORY
    assert "post_manual_journal_entry" not in REPOSITORY
    assert 'POLICY = "initial_capital_funding_v1"' in REPOSITORY
