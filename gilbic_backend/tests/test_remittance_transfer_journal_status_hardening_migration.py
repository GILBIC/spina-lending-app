from pathlib import Path


SQL_PATH = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0059_harden_remittance_transfer_journal_status.sql"
)


def test_status_hardening_is_read_only_and_fail_closed() -> None:
    source = SQL_PATH.read_text(encoding="utf-8")
    assert source.strip().startswith("BEGIN;")
    assert source.strip().endswith("COMMIT;")
    assert "CREATE OR REPLACE VIEW accounting.remittance_transfer_journal_status" in source
    assert "transfer_coordinate_ready" in source
    assert "period.status = 'open'" in source
    assert "debit_account.is_active = true" in source
    assert "credit_account.is_active = true" in source
    assert "income_recognition" in source
    assert "explicit_management_posting" in source
    assert "automatic_source_posting" in source
    assert "INSERT INTO accounting.journal_entries" not in source
    assert "INSERT INTO accounting.journal_lines" not in source
    assert "UPDATE lending.collection_remittances" not in source
