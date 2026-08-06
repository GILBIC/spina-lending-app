from pathlib import Path


def test_client_renewal_migration_adds_safe_request_workflow() -> None:
    migration = (
        Path(__file__).parents[1]
        / "sql"
        / "0018_add_client_renewal_requests.sql"
    ).read_text(encoding="utf-8").lower()

    assert "create table if not exists lending.client_renewal_requests" in migration
    assert "requested_amount numeric(18,2)" in migration
    assert "status in ('pending', 'approved', 'rejected', 'cancelled')" in migration
    assert "where status = 'pending'" in migration
    assert "renewal.manage" in migration
    assert "management" in migration
