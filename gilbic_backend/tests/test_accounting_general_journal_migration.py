from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "sql"
RESET = (ROOT / "0023_reset_empty_august_2026_pre_cutover_period.sql").read_text(
    encoding="utf-8"
)
JOURNAL = (ROOT / "0024_add_manual_general_journal_and_trial_balance.sql").read_text(
    encoding="utf-8"
)


def test_pre_cutover_period_reset_is_narrow_and_audited() -> None:
    assert "pre_cutover_period_reset_audit" in RESET
    assert "August 2026" in RESET
    assert "2026-08-01" in RESET
    assert "2026-08-31" in RESET
    assert "journal_count_value <> 0" in RESET
    assert "period_events" in RESET
    assert "replacement_period_id" in RESET
    assert "create_fiscal_period" in RESET
    assert "immutable" in RESET.lower()


def test_general_journal_adds_permission_and_protected_functions() -> None:
    assert "accounting.journal.manage" in JOURNAL
    assert "create_manual_journal_draft" in JOURNAL
    assert "update_manual_journal_draft" in JOURNAL
    assert "cancel_manual_journal_draft" in JOURNAL
    assert "post_manual_journal_entry" in JOURNAL
    assert "create_manual_reversal_draft" in JOURNAL
    assert "validate_manual_journal_lines" in JOURNAL
    assert "must be balanced" in JOURNAL
    assert "No open accounting period" in JOURNAL


def test_cancelled_drafts_keep_immutable_audit_snapshot() -> None:
    assert "cancelled_journal_draft_audit" in JOURNAL
    assert "line_snapshot" in JOURNAL
    assert "event_snapshot" in JOURNAL
    assert "guard_cancelled_journal_draft_audit" in JOURNAL
    assert "DELETE FROM accounting.journal_entries" in JOURNAL
