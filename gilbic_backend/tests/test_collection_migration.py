from pathlib import Path


SQL_DIR = Path(__file__).parents[1] / "sql"


def test_collection_migration_preserves_atomic_and_unique_boundaries() -> None:
    migration = (SQL_DIR / "0005_add_idempotent_collections.sql").read_text(
        encoding="utf-8"
    )

    assert "BEGIN;" in migration and "COMMIT;" in migration
    assert "lending.collection_transactions" in migration
    assert "mobile.gilbic_collection_idempotency" in migration
    assert "registered_device_id UUID" in migration
    assert "idempotency_key UUID NOT NULL UNIQUE" in migration
    assert "idempotency_key UUID PRIMARY KEY" in migration
    assert "lending_collection_device_sequence_uidx" in migration
    assert "lending_collection_one_pass_per_day_uidx" in migration
    assert "is_reconciled BOOLEAN NOT NULL DEFAULT false" in migration
    assert "state_version BIGINT NOT NULL DEFAULT 0" in migration
    assert "REVOKE ALL ON SCHEMA mobile FROM PUBLIC" in migration


def test_registered_device_foreign_key_has_covering_index() -> None:
    migration = (
        SQL_DIR / "0006_index_collection_registered_devices.sql"
    ).read_text(encoding="utf-8")

    assert "BEGIN;" in migration and "COMMIT;" in migration
    assert "mobile_collection_registered_device_idx" in migration
    assert "mobile.gilbic_collection_idempotency (registered_device_id)" in migration


def test_remittance_migration_adds_exact_dates_audited_edits_and_locking() -> None:
    migration = (SQL_DIR / "0007_add_collection_remittances.sql").read_text(
        encoding="utf-8"
    )

    assert "BEGIN;" in migration and "COMMIT;" in migration
    assert "collection.correct.own_unremitted" in migration
    assert "collection.correct.locked" in migration
    assert "lending.collection_remittances" in migration
    assert "collector_user_id UUID NOT NULL" in migration
    assert "recipient_user_id UUID NOT NULL" in migration
    assert "transaction_count = payment_count + unable_to_pay_count" in migration
    assert "lending.collection_remittance_items" in migration
    assert "transaction_id UUID NOT NULL UNIQUE" in migration
    assert "lending.collection_covered_dates" in migration
    assert "UNIQUE (loan_id, covered_date)" in migration
    assert "lending.collection_transaction_edits" in migration
    assert "previous_snapshot JSONB NOT NULL" in migration
    assert "replacement_snapshot JSONB NOT NULL" in migration
    assert "lending.collection_supervisor_adjustments" in migration
    assert "is_locked BOOLEAN NOT NULL DEFAULT false" in migration
    assert "prevent_locked_collection_mutation" in migration
    assert "Covered dates for a remitted collection are locked" in migration
    assert "Server-calculated collector cash handovers" in migration


def test_legacy_ranges_are_backfilled_as_individual_covered_dates() -> None:
    migration = (
        SQL_DIR / "0008_backfill_collection_covered_dates.sql"
    ).read_text(encoding="utf-8")

    assert "BEGIN;" in migration and "COMMIT;" in migration
    assert "generate_series" in migration
    assert "lending.collection_covered_dates" in migration
    assert "transaction.entry_type IN ('payment', 'advance')" in migration
    assert "ON CONFLICT DO NOTHING" in migration


def test_remitted_collection_rows_become_fully_immutable() -> None:
    migration = (
        SQL_DIR / "0009_harden_remitted_collection_immutability.sql"
    ).read_text(encoding="utf-8")

    assert "BEGIN;" in migration and "COMMIT;" in migration
    assert "IF OLD.is_locked AND NEW IS DISTINCT FROM OLD" in migration
    assert "permanently locked" in migration
    assert "authorized supervisor adjustment" in migration
    assert "lending_collection_transaction_lock_guard" in migration


def test_remittance_notification_acceptance_transfers_cash_custody() -> None:
    migration = (
        SQL_DIR / "0010_add_remittance_acceptance_notifications.sql"
    ).read_text(encoding="utf-8")

    assert "BEGIN;" in migration and "COMMIT;" in migration
    assert "core.user_notifications" in migration
    assert "action_code TEXT NOT NULL DEFAULT 'accept_remittance'" in migration
    assert "custody_user_id UUID" in migration
    assert "custody_transferred_at TIMESTAMPTZ" in migration
    assert "Only the selected remittance recipient may accept custody" in migration
    assert "NEW.custody_user_id := OLD.recipient_user_id" in migration
    assert "NEW.custody_transferred_at := NEW.received_at" in migration
    assert "Remittance awaiting acceptance" in migration
    assert "Accept only after the cash is physically received" in migration
    assert "status = 'accepted'" in migration
    assert "Accepting a remittance transfers cash custody" in migration
