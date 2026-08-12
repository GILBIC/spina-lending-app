from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0057_add_remittance_accounting_evidence.sql"
)


def migration_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_remittance_accounting_evidence_migration_is_transactional_and_install_only() -> None:
    sql = migration_sql()
    stripped = sql.strip()
    assert stripped.startswith("BEGIN;")
    assert stripped.endswith("COMMIT;")
    assert "accounting.remittance_transfer_evidence" in sql
    assert "accounting.remittance_transfer_readiness" in sql
    assert "accounting.remittance_transfer.evidence.manage" in sql
    assert "SELECT accounting.record_remittance_transfer_evidence" not in sql
    assert "INSERT INTO accounting.journal_entries" not in sql
    assert "INSERT INTO accounting.journal_lines" not in sql


def test_destination_is_explicit_and_never_inferred_from_recipient() -> None:
    sql = migration_sql()
    assert "destination_account_system_key" in sql
    assert "('cash_office', 'cash_bank_gcash')" in sql
    assert "recipient_user_id_snapshot" in sql
    assert "custody_user_id_snapshot" in sql
    assert "Recipient acceptance alone never selects the accounting destination" in sql
    assert "Remittance destination must be explicitly evidenced" in sql


def test_received_custody_state_is_required_before_destination_evidence() -> None:
    sql = migration_sql()
    assert "remittance_row.status <> 'received'" in sql
    assert "remittance_row.received_by_user_id IS DISTINCT FROM remittance_row.recipient_user_id" in sql
    assert "remittance_row.custody_user_id IS DISTINCT FROM remittance_row.recipient_user_id" in sql
    assert "remittance_row.custody_transferred_at IS DISTINCT FROM remittance_row.received_at" in sql
    assert "p_transferred_at < remittance_row.custody_transferred_at" in sql


def test_transfer_evidence_is_immutable_and_correction_is_controlled() -> None:
    sql = migration_sql()
    assert "guard_remittance_transfer_evidence_write" in sql
    assert "Remittance transfer evidence is immutable and cannot be deleted" in sql
    assert "accounting_one_active_remittance_transfer_evidence_uidx" in sql
    assert "void_remittance_transfer_evidence" in sql
    assert "different active destination evidence" in sql
    assert "accounting journal history" in sql


def test_ready_coordinate_is_asset_to_asset_and_not_income() -> None:
    sql = migration_sql()
    assert "'transfer_coordinate_ready'" in sql
    assert "THEN evidence.destination_account_system_key" in sql
    assert "THEN 'cash_collector_custody'" in sql
    assert "false AS income_recognition" in sql
    assert "Dr exact evidence-backed destination cash / Cr Cash - Collector Custody" in sql
    assert "asset-to-asset transfer is never income" in sql


def test_first_slice_keeps_journal_and_automatic_posting_disabled() -> None:
    sql = migration_sql()
    assert "false AS journal_lines_enabled" in sql
    assert "false AS automatic_source_posting" in sql
    assert "does not authorize journal lines or automatic posting" in sql
