from __future__ import annotations

import ast
from pathlib import Path


RUNNER = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "apply_accounting_opening_journal_posting_migration.py"
)
MARKER = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "accounting-opening-journal-posting-live-migration.once"
)


def runner_source() -> str:
    return RUNNER.read_text(encoding="utf-8")


def test_live_runner_is_valid_python_and_marker_exists() -> None:
    source = runner_source()
    ast.parse(source)
    assert MARKER.is_file()
    assert "0038_add_protected_opening_balance_journal_posting.sql" in source


def test_live_runner_snapshots_journals_and_never_invokes_posting_function() -> None:
    source = runner_source()
    assert "_journal_snapshot" in source
    assert "source_type = 'opening_balance' AND status = 'posted'" in source
    assert "after_journals != before_journals" in source
    assert "journal entries, statuses, numbers, or lines changed" in source
    assert "require_zero_postings=True" in source

    # Deployment may install the function through the migration SQL but the
    # runner itself must never call the protected posting function.
    assert "post_opening_balance_journal(" not in source


def test_live_runner_preserves_loans_collections_workbook_and_ecl_safety() -> None:
    source = runner_source()
    assert "before_loan_statuses" in source and "after_loan_statuses" in source
    assert "before_transactions" in source and "after_transactions" in source
    assert "before_workbook" in source and "after_workbook" in source
    assert "before_reviewed" in source and "after_reviewed" in source
    assert "before_dpd" in source and "after_dpd" in source
    assert "automatic source posting disabled" in source
