from pathlib import Path


SQL_ROOT = Path(__file__).resolve().parents[1] / "sql"
MIGRATION = SQL_ROOT / "0116_enforce_one_active_7x7_per_client.sql"


def test_priority6_one_active_7x7_migration_exists() -> None:
    assert MIGRATION.is_file(), (
        "Priority #6 requires forward migration 0116 to enforce at most one active "
        "seven_by_seven loan per client without blocking a simultaneous Regular loan."
    )


def test_priority6_one_active_7x7_migration_is_fail_closed_and_concurrency_safe() -> None:
    source = MIGRATION.read_text(encoding="utf-8").lower()
    normalized = " ".join(source.split())

    assert "calculation_mode = 'seven_by_seven'" in source
    assert "status = 'active'" in source
    assert "having count(*) > 1" in normalized
    assert "pg_advisory_xact_lock" in source
    assert "create or replace function lending.guard_one_active_seven_by_seven_loan" in source
    assert "before insert or update of client_id, loan_type_id, status on lending.loans" in normalized
    assert "new.id" in source
    assert "raise exception" in source
