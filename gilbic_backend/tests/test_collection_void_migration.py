from pathlib import Path


SQL_DIR = Path(__file__).parents[1] / "sql"


def test_management_void_migration_is_audited_and_excluded_from_remittance() -> None:
    migration = (
        SQL_DIR / "0017_add_management_collection_voids.sql"
    ).read_text(encoding="utf-8")

    assert "BEGIN;" in migration and "COMMIT;" in migration
    assert "collection.void.unremitted" in migration
    assert "WHERE r.code = 'management'" in migration
    assert "is_voided BOOLEAN NOT NULL DEFAULT false" in migration
    assert "collection_transactions_void_state_check" in migration
    assert "lending.collection_transaction_voids" in migration
    assert "transaction_snapshot JSONB NOT NULL" in migration
    assert "state_before JSONB NOT NULL" in migration
    assert "state_after JSONB NOT NULL" in migration
    assert "Voided collection transactions are permanent" in migration
    assert "AND is_voided = false" in migration
