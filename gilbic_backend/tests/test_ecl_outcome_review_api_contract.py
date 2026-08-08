from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1] / "src" / "gilbic_backend"
API = (PACKAGE / "ecl_outcome_review_api.py").read_text(encoding="utf-8")
MAIN = (PACKAGE / "main.py").read_text(encoding="utf-8")


def test_stage5e3_router_is_registered() -> None:
    assert "from .ecl_outcome_review_api import create_ecl_outcome_review_router" in MAIN
    assert "app.include_router(create_ecl_outcome_review_router())" in MAIN


def test_stage5e3_api_requires_management_and_review_permission() -> None:
    assert '"management" not in actor.roles' in API
    assert 'permission="accounting.ecl.review"' in API
    assert "Historical ECL outcome review permission is required." in API


def test_stage5e3_api_requires_explicit_review_evidence() -> None:
    assert "default_label: bool" in API
    assert "evidence_basis: Literal[" in API
    assert "evidence_reference: str" in API
    assert "review_note: str" in API


def test_stage5e3_api_does_not_expose_loss_or_ecl_posting_actions() -> None:
    assert "explicit_loss_amount" not in API
    assert "explicit_recovery_amount" not in API
    assert "post_manual_journal_entry" not in API
    assert "ecl_amount was calculated" not in API
