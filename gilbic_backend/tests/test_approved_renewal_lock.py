from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_migration_blocks_pending_and_approved_duplicates() -> None:
    migration = (
        ROOT / "sql" / "0019_block_duplicate_approved_renewal_requests.sql"
    ).read_text(encoding="utf-8")

    assert "DROP INDEX IF EXISTS lending.lending_client_renewal_one_pending_uidx" in migration
    assert "status IN ('pending', 'approved')" in migration
    assert "lending_client_renewal_one_open_uidx" in migration


def test_repository_treats_approved_request_as_blocking() -> None:
    repository = (
        ROOT / "src" / "gilbic_backend" / "renewal_repository.py"
    ).read_text(encoding="utf-8")

    assert "request.status in ('pending', 'approved')" in repository
    assert "blocking.status as blocking_request_status" in repository
    assert "The approved renewal is still awaiting completion." in repository
    assert "Your approved renewal is awaiting completion." in repository


def test_api_exposes_blocking_request_status() -> None:
    api = (ROOT / "src" / "gilbic_backend" / "renewal_api.py").read_text(
        encoding="utf-8"
    )

    assert '"blocking_request_status": record.blocking_request_status' in api
