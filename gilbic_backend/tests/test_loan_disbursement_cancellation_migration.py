from pathlib import Path


SQL = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0049_add_controlled_new_loan_disbursement_reversals.sql"
).read_text(encoding="utf-8")
LOWER = SQL.lower()


def test_stage5d23_defines_controlled_reversal_without_rewriting_original_history() -> None:
    assert SQL.strip().startswith("BEGIN;")
    assert SQL.strip().endswith("COMMIT;")
    assert "accounting.loan_disbursement.journal.reverse" in SQL
    assert "lending.loan_disbursement_cancellations" in SQL
    assert "accounting.loan_disbursement_journal_reversals" in SQL
    assert "accounting.reverse_posted_new_loan_disbursement" in SQL
    assert "accounting.loan_disbursement_cancellation_status" in SQL
    assert "loan_disbursement_cancellation_reversal" in SQL
    assert "reversal_of_entry_id" in SQL
    assert "original_line.credit" in SQL
    assert "original_line.debit" in SQL
    assert "false AS automatic_source_posting" in SQL


def test_stage5d23_install_does_not_invoke_reversal_or_mutate_evidence() -> None:
    assert LOWER.count("reverse_posted_new_loan_disbursement(") == 1
    assert "select accounting.reverse_posted_new_loan_disbursement(" not in LOWER
    assert "do $$" not in LOWER
    assert "update lending.loan_disbursement_events" not in LOWER
    assert "delete from lending.loan_disbursement_events" not in LOWER
    assert "delete from accounting.journal_entries" not in LOWER


def test_stage5d23_revalidates_original_posting_evidence_accounts_lines_and_period() -> None:
    for marker in (
        "accounting.loan_disbursement_journal_postings",
        "accounting.loan_disbursement_journal_draft_preparations",
        "lending.loan_disbursement_events",
        "accounting.fiscal_periods",
        "accounting.accounts",
        "accounting.journal_entries",
        "accounting.journal_lines",
        "event_row.is_voided",
        "event_row.event_kind <> 'new_loan_release'",
        "event_row.settlement_amount <> 0",
        "event_row.other_deduction_amount <> 0",
        "debit_account.system_key <> 'loans_receivable_regular'",
        "credit_account.system_key not in",
        "line_count <> 2",
        "debit_match_count <> 1",
        "credit_match_count <> 1",
        "period.status = 'open'",
    ):
        assert marker in LOWER


def test_stage5d23_blocks_generic_reversal_and_keeps_audits_immutable() -> None:
    assert "guard_protected_loan_disbursement_reversal_insert" in SQL
    assert "guard_loan_disbursement_cancellation_record_write" in SQL
    assert "guard_loan_disbursement_reversal_record_write" in SQL
    assert "posted protected new-loan disbursement journals can only be reversed" in LOWER
    assert "protected new-loan disbursement cancellation evidence is immutable" in LOWER
    assert "protected new-loan disbursement reversal audit is immutable" in LOWER
    assert "automatic_source_posting', false" in SQL
