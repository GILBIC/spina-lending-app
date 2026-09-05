from pathlib import Path


SQL_PATH = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0110_add_borrower_schedule_adjustments.sql"
)


def test_borrower_schedule_adjustment_migration_generalizes_operational_evidence() -> None:
    source = SQL_PATH.read_text(encoding="utf-8")

    assert source.strip().startswith("BEGIN;")
    assert "event_date DATE" in source
    assert "borrower_shortfall" in source
    assert "borrower_catch_up" in source
    assert "active_borrower_extension_slots" in source
    assert "borrower_catch_up_oldest_first" in source
    assert "no_collection_date" in source
    assert source.strip().endswith("COMMIT;")


def test_borrower_schedule_migration_preserves_no_collection_compatibility() -> None:
    source = SQL_PATH.read_text(encoding="utf-8")

    assert "adjustment_type IN" in source
    assert "'no_collection'" in source
    assert "'reversal'" in source
    assert "event_date = no_collection_date" in source


def test_borrower_schedule_migration_preserves_7x7_voluntary_completion_semantics() -> None:
    source = SQL_PATH.read_text(encoding="utf-8")

    assert "'voluntary_completion'" in source
    assert (
        "DROP CONSTRAINT IF EXISTS loan_schedule_adjustments_reference_semantics_check"
        in source
    )
    assert "adjustment_type = 'voluntary_completion'" in source
