from pathlib import Path


SQL_DIR = Path(__file__).parents[1] / "sql"


def test_cross_collector_activity_migration_contains_required_boundaries() -> None:
    sql = (
        SQL_DIR / "0013_add_cross_collector_activity_notifications.sql"
    ).read_text(encoding="utf-8")

    required = (
        "assigned_collector_user_id UUID",
        "collection_origin TEXT NOT NULL",
        "lending.capture_collection_assignment",
        "core.activity_notifications",
        "client_payment_posted",
        "client_payment_remitted",
        "client_payment_accepted",
        "cross_collection_posted",
        "cross_collection_remitted",
        "cross_collection_accepted",
        "lending.collection_assignment_reviews",
    )
    assert "BEGIN;" in sql and "COMMIT;" in sql
    for value in required:
        assert value in sql


def test_cross_collector_trigger_functions_pin_search_path() -> None:
    sql = (
        SQL_DIR / "0013_add_cross_collector_activity_notifications.sql"
    ).read_text(encoding="utf-8")

    assert sql.count("SET search_path = pg_catalog, core, lending") >= 3
    assert "SET search_path = pg_catalog, lending, core" in sql
