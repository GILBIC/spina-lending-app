from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0036_add_per_loan_contract_collection_activation.sql"
).read_text(encoding="utf-8")


def test_activation_migration_is_transaction_wrapped() -> None:
    stripped = MIGRATION.strip()
    assert stripped.startswith("BEGIN;")
    assert stripped.endswith("COMMIT;")


def test_activation_migration_adds_management_permission_and_immutable_event_log() -> None:
    assert "lending.contract_collection.activate" in MIGRATION
    assert "loan_contract_collection_activation_events" in MIGRATION
    assert "event_action IN ('activate', 'deactivate')" in MIGRATION
    assert "lending_contract_collection_activation_audit_guard" in MIGRATION
    assert "BEFORE UPDATE OR DELETE" in MIGRATION


def test_activation_migration_validates_same_loan_verified_active_schedule() -> None:
    assert "schedule_loan_id IS DISTINCT FROM NEW.loan_id" in MIGRATION
    assert "Only the current active contractual schedule" in MIGRATION
    assert "loan_contract_schedule_registrations" in MIGRATION
    assert "requires a verified signed-contract schedule registration" in MIGRATION


def test_activation_migration_exposes_latest_per_loan_state() -> None:
    assert "loan_contract_collection_activation_state" in MIGRATION
    assert "SELECT DISTINCT ON (event.loan_id)" in MIGRATION
    assert "(event.event_action = 'activate') AS is_active" in MIGRATION


def test_activation_migration_does_not_activate_or_modify_live_loans() -> None:
    assert "INSERT INTO lending.loan_contract_collection_activation_events" not in MIGRATION
    assert "UPDATE lending.loans" not in MIGRATION
    assert "UPDATE lending.loan_contract_schedules" not in MIGRATION
    assert "INSERT INTO lending.loan_contract_installments" not in MIGRATION
    assert "INSERT INTO lending.loan_installment_payment_allocations" not in MIGRATION
