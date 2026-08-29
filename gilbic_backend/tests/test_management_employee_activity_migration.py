from __future__ import annotations

from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0109_add_management_employee_activity_permission.sql"
)


def test_employee_activity_migration_is_additive_and_management_only() -> None:
    assert MIGRATION.exists(), "Employee Activity permission migration is missing."
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert sql.lstrip().startswith("begin;")
    assert sql.rstrip().endswith("commit;")
    assert "employee.activity.review" in sql
    assert "on conflict" in sql
    assert "create table" not in sql
    assert "('management', 'employee.activity.review')" in sql
    assert "('employee', 'employee.activity.review')" not in sql
    assert "('collector', 'employee.activity.review')" not in sql
    assert "('client', 'employee.activity.review')" not in sql
