from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "src" / "gilbic_backend" / "v1_tax_adjustment_api.py").read_text(
    encoding="utf-8"
)
REPOSITORY = (
    ROOT / "src" / "gilbic_backend" / "v1_tax_adjustment_repository.py"
).read_text(encoding="utf-8")
MAIN = (ROOT / "src" / "gilbic_backend" / "main.py").read_text(encoding="utf-8")


def test_v1_tax_adjustment_api_is_management_only_strict_and_wired() -> None:
    assert 'model_config = ConfigDict(extra="forbid")' in API
    assert '"management" not in actor.roles' in API
    assert "actor_user_id=actor.user_id" in API
    assert "actor.account_id" not in API
    assert "create_v1_tax_adjustment_router" in MAIN
    assert "app.include_router(create_v1_tax_adjustment_router())" in MAIN
    assert '"/api/mobile/v1/management/financial-accounting/tax/adjustments"' in API


def test_v1_tax_adjustment_api_has_action_specific_permissions_and_confirmation() -> (
    None
):
    for permission in (
        'EVIDENCE_PERMISSION = "accounting.tax.adjustment_evidence.record"',
        'ADJUSTMENT_PREPARE_PERMISSION = "accounting.tax.adjustment.prepare"',
        'ADJUSTMENT_POST_PERMISSION = "accounting.tax.adjustment.post"',
    ):
        assert permission in API
    assert API.count("confirm: bool = False") == 2
    assert "_require_confirmation" in API


def test_v1_tax_adjustment_api_exposes_only_exact_protected_core() -> None:
    for route in (
        '"/api/v1/management/financial-accounting/tax/adjustments"',
        '"/api/v1/management/financial-accounting/tax/adjustments/evidence"',
        '"/api/v1/management/financial-accounting/tax/adjustments/{adjustment_evidence_id}/prepare"',
        '"/api/v1/management/financial-accounting/tax/adjustments/{adjustment_evidence_id}/post"',
    ):
        assert route in API
    for field in (
        "tax_liability_posting_id",
        "replacement_evidence_id",
        "adjustment_kind",
        "adjustment_date",
        "confirmation_token",
        "expected_evidence_digest",
        "expected_original_tax_due",
        "expected_replacement_tax_due",
        "expected_adjustment_amount",
        "expected_debit_account_code",
        "expected_credit_account_code",
        "expected_posting_date",
        "expected_fiscal_period_id",
    ):
        assert field in API
    assert "reverse_unsettled_liability" in API
    assert "recognize_settled_tax_recoverable" in API


def test_v1_tax_adjustment_repository_calls_only_protected_database_functions() -> None:
    for function in (
        "accounting.record_v1_tax_adjustment_evidence",
        "accounting.prepare_v1_tax_adjustment_journal",
        "accounting.post_v1_tax_adjustment_journal",
    ):
        assert function in REPOSITORY
    assert "accounting.v1_tax_adjustment_queue" in REPOSITORY
    assert "accounting.v1_tax_adjustment_summary" in REPOSITORY
    assert "accounting.v1_tax_liability_queue" in REPOSITORY
    assert "accounting.v1_tax_payment_evidence" in REPOSITORY
    assert "accounting.v1_tax_settlement_postings" in REPOSITORY
    assert "accounting.v1_tax_adjustment_evidence" in REPOSITORY
    assert "posted_adjustment_review_required" in REPOSITORY
    assert "reverse_unsettled_liability" in REPOSITORY
    assert "recognize_settled_tax_recoverable" in REPOSITORY
    assert "insert into accounting.journal_entries" not in REPOSITORY.lower()
    assert "accounting.post_journal_entry" not in REPOSITORY


def test_api_keeps_later_amendment_refund_credit_actions_explicit_and_auto_posting_off() -> (
    None
):
    assert "additional-tax amendments" in API.lower()
    assert "refund/credit realization" in API.lower()
    assert "automatic source posting remains disabled" in API.lower()
    assert "tax_adjustment_reversal_enabled" in API
    assert "automatic_source_posting" in API


def test_v1_tax_adjustment_read_contract_exposes_only_server_derived_candidates() -> (
    None
):
    for field in (
        '"adjustment_candidates"',
        '"adjustment_kind"',
        '"tax_liability_posting_id"',
        '"original_evidence_id"',
        '"replacement_evidence_id"',
        '"original_tax_due"',
        '"replacement_tax_due"',
        '"adjustment_amount"',
        '"fiscal_period_id"',
        '"fiscal_period_start"',
        '"fiscal_period_end"',
        '"limit"',
        '"offset"',
    ):
        assert field in API
    assert "list_adjustment_candidates" in API
