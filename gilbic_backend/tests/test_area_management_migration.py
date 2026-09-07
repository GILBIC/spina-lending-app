from pathlib import Path


SQL_PATH = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0113_add_authoritative_area_management.sql"
)


def _sql() -> str:
    assert SQL_PATH.exists(), "Area Management migration 0113 is not implemented yet."
    return SQL_PATH.read_text(encoding="utf-8").lower()


def test_area_management_schema_contract() -> None:
    sql = _sql()

    assert "create table if not exists lending.area_nodes" in sql
    assert "parent_area_uid uuid" in sql
    assert "full_path text not null" in sql
    assert "sort_order integer not null" in sql
    assert "is_active boolean not null" in sql
    assert "is_legacy_unmapped boolean not null" in sql
    assert "add column if not exists area_uid uuid" in sql
    assert "client_area_pending_transfers" in sql
    assert "client_area_transfer_history" in sql


def test_area_management_permissions_are_scoped_to_employee_and_management() -> None:
    sql = _sql()

    for permission in (
        "area.manage",
        "area.collector.assign",
        "area.client.assign",
        "area.retire",
    ):
        assert permission in sql

    for permission in (
        "area.manage",
        "area.collector.assign",
        "area.client.assign",
    ):
        assert f"('employee', '{permission}')" in sql
        assert f"('management', '{permission}')" in sql

    assert "('employee', 'area.retire')" not in sql
    assert "('management', 'area.retire')" in sql
    assert "('collector', 'area.manage')" not in sql
    assert "('collector', 'area.collector.assign')" not in sql
    assert "('collector', 'area.client.assign')" not in sql
    assert "('collector', 'area.retire')" not in sql


def test_area_management_migration_has_no_fixed_subarea_depth() -> None:
    sql = _sql()

    assert "depth <= 4" not in sql
    assert "depth<=4" not in sql
    assert "subarea_1" not in sql
    assert "subarea_2" not in sql
    assert "subarea_3" not in sql
    assert "subarea_4" not in sql


def test_area_management_migration_does_not_rewrite_collection_history() -> None:
    sql = _sql()

    assert "update lending.collection_transactions" not in sql
    assert "delete from lending.collection_transactions" not in sql
    assert "truncate lending.collection_transactions" not in sql


def test_area_management_migration_preserves_legacy_paths_as_whole_roots() -> None:
    sql = _sql()

    assert "is_legacy_unmapped" in sql
    assert "lending.clients" in sql
    assert "lending.collector_area_assignments" in sql
    assert "lending.normalize_area_path" in sql
    assert "parent_area_uid" in sql
    assert "null" in sql
    # Legacy values must be inserted as complete path strings. Migration code
    # must not parse known display/address separators into guessed hierarchy.
    for forbidden_split in (
        "split_part(",
        "string_to_array(",
        "regexp_split_to_array(",
    ):
        assert forbidden_split not in sql


def test_area_management_migration_enforces_one_active_permanent_owner_per_node() -> None:
    sql = _sql()

    assert "lending_collector_active_area_uid_uidx" in sql
    assert "where is_active = true and area_uid is not null" in sql
    assert "count(distinct" in sql
    assert "raise exception" in sql
