from pathlib import Path


SQL_PATH = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0111_add_client_credential_management.sql"
)


def test_client_credential_manage_permission_is_employee_and_management_only() -> None:
    sql = SQL_PATH.read_text(encoding="utf-8").lower()

    assert "client.credential.manage" in sql
    assert "('employee', 'client.credential.manage')" in sql
    assert "('management', 'client.credential.manage')" in sql
    assert "('collector', 'client.credential.manage')" not in sql
    assert "('client', 'client.credential.manage')" not in sql
    assert "on conflict" in sql
