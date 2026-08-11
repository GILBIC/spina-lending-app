from pathlib import Path


SQL = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0047_add_protected_new_loan_disbursement_journal_drafts.sql"
).read_text(encoding="utf-8")
LOWER = SQL.lower()


def test_stage5d21_migration_is_protected_draft_only() -> None:
    assert SQL.strip().startswith("BEGIN;")
    assert SQL.strip().endswith("COMMIT;")
    assert "accounting.loan_disbursement.journal.prepare" in SQL
    assert "accounting.loan_disbursement_journal_draft_preparations" in SQL
    assert "accounting.loan_disbursement_journal_draft_status" in SQL
    assert "accounting.create_new_loan_disbursement_journal_draft" in SQL
    assert "new_loan_disbursement_coordinates_v1" in SQL
    assert "new_loan_disbursement_journal_draft_v1" in SQL
    assert "'loan_disbursement:' || p_disbursement_event_id::text" in SQL
    assert "'loans_receivable_regular'" in SQL
    assert "'cash_office'" in SQL
    assert "'cash_collector_custody'" in SQL
    assert "'cash_bank_gcash'" in SQL
    assert "'draft'" in SQL
    assert "false AS posting_enabled" in SQL
    assert "false AS automatic_source_posting" in SQL


def test_stage5d21_install_does_not_invoke_draft_or_posting_function() -> None:
    # The protected draft function contains INSERT statements by design, but the
    # migration must only define the capability. There is exactly one occurrence
    # of the function signature and no anonymous block or top-level function call.
    assert LOWER.count("create_new_loan_disbursement_journal_draft(") == 1
    assert "do $$" not in LOWER
    assert "select accounting.create_new_loan_disbursement_journal_draft(" not in LOWER
    assert "select accounting.post_journal_entry(" not in LOWER
    assert "select accounting.post_manual_journal_entry(" not in LOWER


def test_stage5d21_protects_draft_and_lines_from_general_journal_bypass() -> None:
    assert "accounting_loan_disbursement_system_journal_entry_guard" in SQL
    assert "accounting_loan_disbursement_system_journal_line_guard" in SQL
    assert "accounting.loan_disbursement_journal_post_allowed" in SQL
    assert "cannot be edited" in SQL
    assert "cannot be deleted through the General Journal" in SQL
    assert "system generated and immutable" in SQL
