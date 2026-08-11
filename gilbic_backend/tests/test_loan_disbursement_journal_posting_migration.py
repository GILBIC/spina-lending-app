from pathlib import Path


SQL = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0048_add_protected_new_loan_disbursement_journal_posting.sql"
).read_text(encoding="utf-8")
LOWER = SQL.lower()


def test_stage5d22_migration_defines_explicit_protected_posting_only() -> None:
    assert SQL.strip().startswith("BEGIN;")
    assert SQL.strip().endswith("COMMIT;")
    assert "accounting.loan_disbursement.journal.post" in SQL
    assert "accounting.loan_disbursement_journal_postings" in SQL
    assert "accounting.post_new_loan_disbursement_journal" in SQL
    assert "accounting.loan_disbursement_journal_posting_status" in SQL
    assert "new_loan_disbursement_journal_posting_v1" in SQL
    assert "new_loan_disbursement_journal_draft_v1" in SQL
    assert "new_loan_disbursement_coordinates_v1" in SQL
    assert "loans_receivable_regular" in SQL
    assert "cash_office" in SQL
    assert "cash_collector_custody" in SQL
    assert "cash_bank_gcash" in SQL
    assert "accounting.loan_disbursement_journal_post_allowed" in SQL
    assert "false AS automatic_source_posting" in SQL


def test_stage5d22_install_does_not_invoke_posting_function() -> None:
    assert LOWER.count("post_new_loan_disbursement_journal(") == 1
    assert "do $$" not in LOWER
    assert "select accounting.post_new_loan_disbursement_journal(" not in LOWER
    assert "insert into accounting.loan_disbursement_journal_postings\nselect" not in LOWER


def test_stage5d22_revalidates_source_draft_period_accounts_lines_and_audit() -> None:
    for marker in (
        "lending.loan_disbursement_events",
        "accounting.loan_disbursement_journal_draft_preparations",
        "accounting.fiscal_periods",
        "accounting.accounts",
        "accounting.journal_entries",
        "accounting.journal_lines",
        "event_row.is_voided",
        "event_row.event_kind <> 'new_loan_release'",
        "event_row.settlement_amount <> 0",
        "event_row.other_deduction_amount <> 0",
        "loan_row.calculation_mode <> 'fixed_daily'",
        "period_row.status <> 'open'",
        "journal_row.status <> 'draft'",
        "line_count <> 2",
        "debit_match_count <> 1",
        "credit_match_count <> 1",
        "existing protected new-loan disbursement posting audit",
    ):
        assert marker in LOWER


def test_stage5d22_posting_audit_is_immutable_and_auto_posting_stays_off() -> None:
    assert "guard_loan_disbursement_journal_posting_record_write" in SQL
    assert "loan_disbursement_journal_post_record_allowed" in SQL
    assert "automatic_source_posting', false" in SQL
    assert "false AS automatic_source_posting" in SQL
