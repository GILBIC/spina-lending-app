from pathlib import Path


SQL_PATH = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0114_add_client_cif_first_loan_foundation.sql"
)


def test_client_cif_foundation_is_versioned_lean_and_privacy_minimal() -> None:
    sql = SQL_PATH.read_text(encoding="utf-8").lower()

    assert "create table if not exists lending.client_cif_versions" in sql
    assert "client_id uuid not null references lending.clients(id)" in sql
    assert "version_number integer not null" in sql
    assert "unique (client_id, version_number)" in sql
    assert "is_current boolean not null default true" in sql
    assert "where is_current" in sql

    assert "status text not null default 'draft'" in sql
    assert "'draft'" in sql
    assert "'active'" in sql
    assert "'superseded'" in sql

    assert "full_name text not null" in sql
    assert "phone_number text not null" in sql
    assert "email text" in sql
    assert "present_address text not null" in sql
    assert "national_id_egov_evidence_reference text" in sql
    assert "tin_id_egov_evidence_reference text" in sql
    assert "meralco_bill_evidence_reference text" in sql

    assert "baseline_face_scan_evidence_reference text" in sql
    assert "baseline_liveness_status text not null default 'pending'" in sql
    assert "'pending'" in sql
    assert "'passed'" in sql
    assert "'failed'" in sql

    assert "activated_at timestamptz" in sql
    assert "expires_at timestamptz" in sql
    assert "review_due_at timestamptz" in sql
    assert "reverification_required_at timestamptz" in sql
    assert "reverification_reason text" in sql

    for forbidden in (
        "password",
        "biometric_template",
        "face_embedding",
        "raw_face",
        "raw_national_id",
        "raw_tin",
        "national_id_number",
        "tin_number",
    ):
        assert forbidden not in sql
