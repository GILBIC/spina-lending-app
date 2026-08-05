from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0018_allow_collection_void_activity_notifications.sql"
)


def test_collection_void_notification_types_are_allowed() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "activity_notifications_notification_type_check" in sql
    assert "collector_payment_voided" in sql
    assert "client_payment_voided" in sql
    assert "cross_collection_posted" in sql
    assert "client_payment_accepted" in sql
