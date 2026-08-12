from pathlib import Path


SQL_PATH = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0058_add_protected_remittance_transfer_journal_lifecycle.sql"
)


def test_remittance_transfer_journal_lifecycle_migration_is_protected_and_explicit() -> None:
    source = SQL_PATH.read_text(encoding="utf-8")
    assert source.strip().startswith("BEGIN;")
    assert source.strip().endswith("COMMIT;")

    assert "accounting.create_remittance_transfer_journal_draft" in source
    assert "accounting.post_remittance_transfer_journal" in source
    assert "accounting.reverse_posted_remittance_transfer" in source
    assert "accounting.remittance_transfer_journal_status" in source

    assert "'cash_office', 'cash_bank_gcash'" in source
    assert "'cash_collector_custody'" in source
    assert "'remittance_transfer'" in source
    assert "'remittance_transfer_reversal'" in source

    assert "'accounting.remittance_transfer.journal.prepare'" in source
    assert "'accounting.remittance_transfer.journal.post'" in source
    assert "'accounting.remittance_transfer.journal.reverse'" in source
    assert "explicit_management_posting" in source
    assert "automatic_source_posting" in source
    assert "income_recognition" in source

    # Installing this migration defines controls only. The only journal INSERTs
    # live inside protected callable functions; there is no top-level source-row
    # backfill or automatic posting invocation.
    top_level_prefix = source.split(
        "CREATE OR REPLACE FUNCTION accounting.create_remittance_transfer_journal_draft",
        1,
    )[0]
    assert "INSERT INTO accounting.journal_entries" not in top_level_prefix
    assert "INSERT INTO accounting.journal_lines" not in top_level_prefix
    assert "select accounting.post_remittance_transfer_journal" not in source.lower()
    assert "select accounting.reverse_posted_remittance_transfer" not in source.lower()
