from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API = (
    ROOT / "src" / "gilbic_backend" / "ecl_allowance_posting_api.py"
).read_text(encoding="utf-8")
REPOSITORY = (
    ROOT / "src" / "gilbic_backend" / "ecl_allowance_posting_repository.py"
).read_text(encoding="utf-8")
MAIN = (ROOT / "src" / "gilbic_backend" / "main.py").read_text(encoding="utf-8")


def test_a4_management_api_is_wired_and_permission_scoped() -> None:
    assert "create_ecl_allowance_posting_router" in MAIN
    assert "app.include_router(create_ecl_allowance_posting_router())" in MAIN
    assert 'PREPARE_PERMISSION = "accounting.ecl.allowance.prepare"' in API
    assert 'POST_PERMISSION = "accounting.ecl.allowance.post"' in API
    assert "/ecl-allowance-posting/{measurement_id}/prepare" in API
    assert "/ecl-allowance-posting/preparations/{preparation_id}/post" in API


def test_a4_requests_require_exact_confirmation_fields() -> None:
    for token in (
        "preparation_review_token",
        "posting_review_token",
        "expected_calculation_digest",
        "expected_ecl_amount",
        "expected_posting_date",
        "expected_fiscal_period_id",
        "expected_credit_loss_expense_account_id",
        "expected_allowance_account_id",
        "expected_prior_allowance_balance",
        "expected_measurement_id",
        "expected_journal_entry_id",
        "expected_source_event_key",
        "expected_preparation_digest",
        "expected_allowance_amount",
    ):
        assert token in API
    assert "exact currency-cent precision" in API
    assert "prior balance 0.00" in API


def test_a4_repository_uses_only_protected_database_functions() -> None:
    assert "accounting.prepare_initial_ecl_allowance_journal" in REPOSITORY
    assert "accounting.post_initial_ecl_allowance_journal" in REPOSITORY
    assert 'DRAFT_POLICY = "ecl_allowance_initial_journal_draft_v1"' in REPOSITORY
    assert 'POSTING_POLICY = "ecl_allowance_initial_journal_posting_v1"' in REPOSITORY
    assert "insert into accounting.journal_entries" not in REPOSITORY.lower()
    assert "insert into accounting.journal_lines" not in REPOSITORY.lower()


def test_a4_api_keeps_automatic_posting_off() -> None:
    assert '"account_1190_posting_enabled": True' in API
    assert '"automatic_source_posting": False' in API
    assert "Automatic source posting remains disabled" in API
