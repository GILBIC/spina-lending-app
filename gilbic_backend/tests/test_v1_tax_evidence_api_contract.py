from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "src" / "gilbic_backend" / "v1_tax_evidence_api.py").read_text(
    encoding="utf-8"
)
REPOSITORY = (
    ROOT / "src" / "gilbic_backend" / "v1_tax_evidence_repository.py"
).read_text(encoding="utf-8")
MAIN = (ROOT / "src" / "gilbic_backend" / "main.py").read_text(encoding="utf-8")


def test_v1_tax_api_is_management_only_strict_and_wired() -> None:
    assert 'model_config = ConfigDict(extra="forbid")' in API
    assert '"management" not in actor.roles' in API
    assert "actor_user_id=actor.user_id" in API
    assert "actor.account_id" not in API
    assert "create_v1_tax_evidence_router" in MAIN
    assert "app.include_router(create_v1_tax_evidence_router())" in MAIN


def test_v1_tax_evidence_mobile_aliases_reuse_the_same_handlers() -> None:
    for route in (
        '"/api/mobile/v1/management/financial-accounting/tax"',
        '"/api/mobile/v1/management/financial-accounting/tax/rules"',
        '"/api/mobile/v1/management/financial-accounting/tax/dst-evidence"',
        '"/api/mobile/v1/management/financial-accounting/tax/percentage-evidence"',
    ):
        assert route in API


def test_v1_tax_evidence_read_model_returns_exact_page_coordinates() -> None:
    for field in ('"readiness"', '"limit"', '"offset"'):
        assert field in API
    assert '"evidence_backed_tax_readiness_enabled"' in API
    assert '"tax_posting_enabled"' in API
    assert '"automatic_source_posting"' in API


def test_v1_tax_api_uses_action_specific_permissions_and_explicit_confirmation() -> None:
    for permission in (
        'RULE_PERMISSION = "accounting.tax.rule_evidence.record"',
        'DST_PERMISSION = "accounting.tax.dst_evidence.record"',
        'PERCENTAGE_PERMISSION = "accounting.tax.percentage_evidence.record"',
    ):
        assert permission in API
    assert API.count("confirm: bool = False") == 3
    assert "_require_confirmation" in API
    assert "v1_tax_evidence_confirmation_required" in API


def test_v1_tax_api_exposes_only_evidence_readiness_in_this_slice() -> None:
    for route in (
        '"/api/v1/management/financial-accounting/tax"',
        '"/api/v1/management/financial-accounting/tax/rules"',
        '"/api/v1/management/financial-accounting/tax/dst-evidence"',
        '"/api/v1/management/financial-accounting/tax/percentage-evidence"',
    ):
        assert route in API
    assert '"tax_posting_enabled": False' in API
    assert '"automatic_source_posting": False' in API
    assert "prepare" not in API.lower()
    assert "post_journal_entry" not in API


def test_v1_tax_requests_require_exact_evidence_coordinates() -> None:
    for field in (
        "idempotency_key",
        "tax_type",
        "rule_key",
        "effective_from",
        "treatment",
        "rate",
        "legal_source",
        "legal_reference",
        "retained_source_reference",
        "evidence_digest",
        "loan_id",
        "disbursement_event_id",
        "rule_evidence_id",
        "expected_issue_price",
        "expected_term_days",
        "expected_tax_due",
        "instrument_digest",
        "calculation_digest",
        "transaction_id",
        "expected_source_cash_amount",
        "taxable_lending_receipt_amount",
        "principal_receipt_amount",
        "allocation_digest",
        "management_rationale",
    ):
        assert field in API
    assert "Taxable lending receipt plus principal must exactly reconcile" in API
    assert "exact currency-cent precision" in API


def test_v1_tax_repository_calls_only_protected_evidence_functions() -> None:
    for function in (
        "accounting.record_v1_tax_rule_evidence",
        "accounting.record_v1_dst_evidence",
        "accounting.record_v1_percentage_tax_evidence",
    ):
        assert function in REPOSITORY
    assert "accounting.v1_tax_readiness_summary" in REPOSITORY
    assert "accounting.v1_tax_dst_readiness" in REPOSITORY
    assert "accounting.v1_tax_percentage_readiness" in REPOSITORY
    assert "insert into accounting.journal_entries" not in REPOSITORY.lower()
    assert "insert into accounting.journal_lines" not in REPOSITORY.lower()
    assert "post_journal_entry" not in REPOSITORY
