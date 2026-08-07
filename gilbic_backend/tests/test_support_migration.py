from pathlib import Path


def test_support_migration_adds_permission_and_audited_statuses() -> None:
    migration = (
        Path(__file__).parents[1]
        / "sql"
        / "0020_add_client_support_requests.sql"
    ).read_text(encoding="utf-8")

    assert "support.manage" in migration
    assert "client_support_requests" in migration
    assert "status IN ('open', 'answered', 'resolved', 'cancelled')" in migration
    assert "length(btrim(subject)) BETWEEN 3 AND 120" in migration
    assert "length(btrim(message)) BETWEEN 3 AND 2000" in migration
    assert "managed_by_user_id" in migration
    assert "management_response" in migration
