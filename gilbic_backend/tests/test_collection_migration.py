from pathlib import Path


def test_collection_migration_preserves_atomic_and_unique_boundaries() -> None:
    migration = (
        Path(__file__).parents[1]
        / "sql"
        / "0005_add_idempotent_collections.sql"
    ).read_text(encoding="utf-8")

    assert "BEGIN;" in migration and "COMMIT;" in migration
    assert "lending.collection_transactions" in migration
    assert "mobile.gilbic_collection_idempotency" in migration
    assert "registered_device_id UUID" in migration
    assert "UNIQUE (idempotency_key)" in migration
    assert "lending_collection_device_sequence_uidx" in migration
    assert "lending_collection_one_pass_per_day_uidx" in migration
    assert "is_reconciled BOOLEAN NOT NULL DEFAULT false" in migration
    assert "state_version BIGINT NOT NULL DEFAULT 0" in migration
    assert "REVOKE ALL ON SCHEMA mobile FROM PUBLIC" in migration
