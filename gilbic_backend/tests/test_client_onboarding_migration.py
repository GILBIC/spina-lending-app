from pathlib import Path


SQL_PATH = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0112_add_guest_loan_applications.sql"
)


def test_pre_cif_onboarding_schema_and_permissions() -> None:
    sql = SQL_PATH.read_text(encoding="utf-8").lower()

    assert "create sequence if not exists lending.client_onboarding_reference_seq" in sql
    assert "create table if not exists lending.client_onboarding_applicants" in sql
    assert "requirements_incomplete" in sql
    assert "under_verification" in sql
    assert "eligible_for_cif" in sql
    assert "requirements_rejected" in sql

    assert "national_id_egov_evidence_reference text not null" in sql
    assert "national_id_status" in sql
    assert "tin_id_egov_evidence_reference text not null" in sql
    assert "tin_id_status" in sql
    assert "meralco_bill_evidence_reference text not null" in sql
    assert "meralco_bill_status" in sql
    assert "collector_visit_status" in sql
    assert "collector_visit_evidence_reference" in sql

    assert "bypassed_requirements text[]" in sql
    assert "bypass_reason text" in sql
    assert "bypassed_by_user_id uuid" in sql
    assert "bypassed_at timestamptz" in sql
    assert "promoted_client_id uuid unique" in sql
    assert "references lending.clients(id)" in sql

    assert "client_onboarding.requirement.review" in sql
    assert "client_onboarding.visit.record" in sql
    assert "client_onboarding.bypass" in sql
    assert "('employee', 'client_onboarding.requirement.review')" in sql
    assert "('management', 'client_onboarding.requirement.review')" in sql
    assert "('collector', 'client_onboarding.visit.record')" in sql
    assert "('management', 'client_onboarding.bypass')" in sql

    assert "loan_application.manage" not in sql
    assert "baseline_face_scan" not in sql
    assert "requested_amount" not in sql
    assert "requested_loan_type" not in sql
    assert "loan_purpose" not in sql
