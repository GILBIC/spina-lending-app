from __future__ import annotations

from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0039_add_protected_cutover_eir_snapshots.sql"
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_migration_is_schema_only_and_does_not_backfill_or_prepare_live_accounting() -> None:
    sql = _sql()
    lowered = sql.lower()

    assert sql.startswith("BEGIN;")
    assert sql.rstrip().endswith("COMMIT;")
    assert "backfills no historical" in lowered
    assert "inserts zero snapshot rows by itself" in lowered
    assert lowered.count(
        "insert into accounting.opening_balance_loan_measurement_snapshots"
    ) == 1
    assert lowered.count(
        "insert into accounting.opening_balance_loan_snapshot_batches"
    ) == 1
    assert "insert into accounting.opening_balance_journal_preparations" not in lowered
    assert "insert into accounting.journal_entries" not in lowered
    assert "accounting.post_journal_entry" not in lowered
    assert "automatic_default" not in lowered
    assert "allowance_expected_credit_loss" not in lowered


def test_snapshot_rows_and_batches_are_immutable_and_only_insert_during_preparation() -> None:
    sql = _sql()

    assert "accounting.opening_balance_loan_snapshot_batches" in sql
    assert "accounting.opening_balance_loan_measurement_snapshots" in sql
    assert "accounting.opening_balance_snapshot_write_allowed" in sql
    assert "accounting.opening_balance_prepare_allowed" in sql
    assert "BEFORE INSERT OR UPDATE OR DELETE" in sql
    assert "Protected opening-balance loan EIR snapshots are immutable" in sql
    assert "PRIMARY KEY (workbook_id, loan_id)" in sql
    assert "UNIQUE (journal_entry_id, loan_id)" in sql


def test_preparation_trigger_serializes_source_and_captures_exact_active_loan_count() -> None:
    sql = _sql()

    assert "CREATE OR REPLACE FUNCTION accounting.capture_opening_balance_loan_eir_snapshots()" in sql
    assert "BEFORE INSERT ON accounting.opening_balance_journal_preparations" in sql
    assert "lending.loans," in sql
    assert "lending.loan_types," in sql
    assert "lending.loan_collection_state" in sql
    assert "IN SHARE MODE" in sql
    assert "Blocked loan sources must be resolved" in sql
    assert "CROSS JOIN LATERAL accounting.measure_loan_at_cutover" in sql
    assert "WHERE readiness.status = 'active'" in sql
    assert "GET DIAGNOSTICS captured_count = ROW_COUNT" in sql
    assert "captured_count <> expected_count" in sql
    assert "captured_loan_count = expected_active_loan_count" in sql


def test_measured_snapshot_requires_exact_component_reconciliation() -> None:
    sql = _sql()

    assert "measurement_status <> 'measured'" in sql
    assert "daily_eir IS NOT NULL AND daily_eir > 0" in sql
    assert "loan_component + accrued_interest_component = gross_carrying_amount" in sql
    assert "'eir_cutover_v1'" in sql


def test_snapshot_reconciliation_fail_closes_to_prepared_journal_accounts() -> None:
    sql = _sql()

    assert "CREATE OR REPLACE VIEW accounting.opening_balance_loan_snapshot_reconciliation" in sql
    assert "account.system_key = 'loans_receivable_regular'" in sql
    assert "account.system_key = 'loans_receivable_7x7'" in sql
    assert "account.system_key = 'accrued_interest_receivable'" in sql
    assert "snapshot.review_required_count = 0" in sql
    assert "snapshot.regular_loan_component = journal.journal_regular_loan_component" in sql
    assert "snapshot.seven_by_seven_loan_component = journal.journal_seven_by_seven_loan_component" in sql
    assert "snapshot.accrued_interest_component = journal.journal_accrued_interest_component" in sql
    assert ") AS ledger_anchor_ready" in sql
