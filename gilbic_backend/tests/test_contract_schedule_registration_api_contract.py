from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1] / "src" / "gilbic_backend"
API = (PACKAGE / "contract_schedule_registration_api.py").read_text(encoding="utf-8")
SERVICE = (PACKAGE / "contract_schedule_registration_service.py").read_text(
    encoding="utf-8"
)
MAIN = (PACKAGE / "main.py").read_text(encoding="utf-8")


def test_stage5e43_router_is_registered() -> None:
    assert "create_contract_schedule_registration_router" in MAIN
    assert "app.include_router(create_contract_schedule_registration_router())" in MAIN


def test_stage5e43_exposes_preview_then_explicit_registration() -> None:
    assert "/contract-schedules/preview" in API
    assert "/contract-schedules/register" in API
    assert "confirm_registration: bool = False" in API
    assert "contract_schedule_registration_confirmation_required" in API


def test_stage5e43_requires_management_permission_and_signed_contract_evidence() -> None:
    assert '"management" not in actor.roles' in API
    assert 'permission="lending.contract_schedule.manage"' in API
    assert "Verified contract schedule management permission is required." in API
    assert "evidence_reference: str" in API
    assert "verification_note: str" in API
    assert '"signed_contract"' in API
    assert '"signed_renewal_contract"' in API
    assert '"signed_restructure_contract"' in API


def test_stage5e43_does_not_infer_or_auto_classify() -> None:
    assert "generate_contract_installments" in API
    assert "legacy" not in API.lower()
    assert "update lending.loans" not in SERVICE.lower()
    assert "explicit_default_label" not in SERVICE
    assert "post_manual_journal_entry" not in SERVICE
    assert "ecl_amount" not in SERVICE
