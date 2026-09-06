from pathlib import Path


SQL_PATH = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0112_add_guest_loan_applications.sql"
)


def test_guest_application_is_pre_account_and_management_reviewed() -> None:
    sql = SQL_PATH.read_text(encoding="utf-8").lower()

    assert "create table if not exists lending.guest_loan_applications" in sql
    assert "guest_loan_application_reference_seq" in sql
    assert "application_reference text not null unique" in sql
    assert "status in ('submitted', 'under_review', 'approved', 'rejected')" in sql
    assert "national_id_egov_evidence_reference text not null" in sql
    assert "tin_id_egov_evidence_reference text not null" in sql
    assert "meralco_bill_evidence_reference text not null" in sql
    assert "baseline_face_scan_evidence_reference text not null" in sql
    assert "promoted_client_id uuid unique" in sql
    assert "references lending.clients(id)" in sql
    assert "reviewed_by_user_id uuid" in sql
    assert "references core.users(id)" in sql
    assert "user_id uuid" not in sql.replace("reviewed_by_user_id uuid", "")
    assert "client.credential.manage" not in sql
    assert "loan_application.manage" in sql
    assert "('management', 'loan_application.manage')" in sql
    assert "('employee', 'loan_application.manage')" not in sql
    assert "('collector', 'loan_application.manage')" not in sql
    assert "('client', 'loan_application.manage')" not in sql
