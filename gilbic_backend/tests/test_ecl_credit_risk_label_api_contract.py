from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1] / "src" / "gilbic_backend"
API = (PACKAGE / "ecl_credit_risk_label_api.py").read_text(encoding="utf-8")
REPOSITORY = (PACKAGE / "ecl_credit_risk_label_repository.py").read_text(encoding="utf-8")
MAIN = (PACKAGE / "main.py").read_text(encoding="utf-8")


def test_ecl_credit_risk_label_router_is_registered() -> None:
    assert "from .ecl_credit_risk_label_api import create_ecl_credit_risk_label_router" in MAIN
    assert "app.include_router(create_ecl_credit_risk_label_router())" in MAIN


def test_ecl_credit_risk_label_api_requires_management_and_dedicated_permission() -> None:
    assert '"management" not in actor.roles' in API
    assert 'permission="accounting.ecl.credit_risk_label.review"' in API
    assert "ECL credit-risk label review permission is required." in API
    assert "Management access is required for quantitative ECL input-readiness review." in API


def test_ecl_credit_risk_label_api_requires_explicit_evidence_and_rebuttal_controls() -> None:
    assert "stage_label: StageLabel" in API
    assert "default_label: bool" in API
    assert "write_off_label: WriteOffLabel" in API
    assert "recovery_label: RecoveryLabel" in API
    assert "primary_evidence_basis: EvidenceBasis" in API
    assert "sicr_backstop_rebutted: bool" in API
    assert "default_backstop_rebutted: bool" in API
    assert "rebuttal_evidence_reference" in API
    assert "write_off_evidence_reference" in API
    assert "recovery_transaction_id: UUID | None" in API


def test_ecl_credit_risk_label_repository_uses_protected_function_and_read_only_views() -> None:
    assert "accounting.review_ecl_credit_risk_labels" in REPOSITORY
    assert "accounting.ecl_credit_risk_label_queue" in REPOSITORY
    assert "accounting.ecl_credit_risk_label_summary" in REPOSITORY
    assert "accounting.ecl_quantitative_input_readiness" in REPOSITORY
    assert "accounting.ecl_quantitative_input_readiness_summary" in REPOSITORY
    assert "accounting.journal_entries" not in REPOSITORY
    assert "accounting.journal_lines" not in REPOSITORY


def test_ecl_quantitative_input_readiness_api_exposes_exact_blockers_only() -> None:
    assert '"/api/v1/management/financial-accounting/ecl-quantitative-input-readiness"' in API
    assert "load_quantitative_input_readiness" in API
    assert '"blocker_codes": list(loan.blocker_codes)' in API
    assert '"blockers": list(loan.blockers)' in API
    assert '"quantitative_input_ready": loan.quantitative_input_ready' in API
    assert "Free-text notes do not satisfy blockers." in API
    assert "Forward-looking evidence remains blocked until A2 governance is installed" in API


def test_ecl_credit_risk_label_api_does_not_expose_quantitative_ecl_or_posting_action() -> None:
    assert "ecl_amount:" not in API
    assert "post_manual_journal_entry" not in API
    assert "account_1190_posting_enabled" in API
    assert "No quantitative ECL" in API
    assert "write-off journal" in API
    assert "no ECL amount or account 1190 posting is enabled here" in API