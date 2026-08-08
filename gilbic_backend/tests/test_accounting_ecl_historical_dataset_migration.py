from pathlib import Path


SQL = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0032_add_accounting_ecl_historical_dataset.sql"
).read_text(encoding="utf-8")


def test_stage5e2_creates_accounting_only_history_tables() -> None:
    assert "CREATE TABLE IF NOT EXISTS accounting.ecl_history_import_batches" in SQL
    assert "CREATE TABLE IF NOT EXISTS accounting.ecl_historical_loan_episodes" in SQL
    assert "CREATE OR REPLACE VIEW accounting.ecl_historical_dataset_summary" in SQL


def test_stage5e2_does_not_infer_default_or_loss_from_renewal_archive_delete() -> None:
    assert "explicit_default_label boolean" in SQL
    assert "explicit_loss_amount numeric" in SQL
    assert "explicit_recovery_amount numeric" in SQL
    assert "outcome_labeling_required" in SQL
    assert "operational events are not treated as paid/default/loss labels" in SQL


def test_stage5e2_keeps_ecl_and_posting_disabled() -> None:
    assert "NULL::numeric(18,2) AS ecl_amount" in SQL
    assert "false AS ecl_included" in SQL
    assert "false AS ready_to_post" in SQL
    assert "INSERT INTO accounting.journal_entries" not in SQL
    assert "post_manual_journal_entry" not in SQL
    assert "update_opening_balance_workbook_line" not in SQL
    assert "UPDATE lending." not in SQL
    assert "DELETE FROM lending." not in SQL


def test_stage5e2_never_stores_contact_fields() -> None:
    lowered = SQL.lower()
    assert "contact_number" not in lowered
    assert "phone_number" not in lowered
