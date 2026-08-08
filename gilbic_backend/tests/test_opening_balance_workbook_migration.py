from pathlib import Path


SQL = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0027_add_protected_opening_balance_workbook.sql"
).read_text(encoding="utf-8")


def test_cutover_management_permission_is_scoped_to_management() -> None:
    assert "accounting.cutover.manage" in SQL
    assert "WHERE role.code = 'management'" in SQL


def test_workbook_and_lines_are_protected_and_audited() -> None:
    assert "CREATE TABLE IF NOT EXISTS accounting.opening_balance_workbooks" in SQL
    assert "CREATE TABLE IF NOT EXISTS accounting.opening_balance_workbook_lines" in SQL
    assert "CREATE TABLE IF NOT EXISTS accounting.opening_balance_workbook_audit" in SQL
    assert "Opening-balance workbook audit records are immutable." in SQL
    assert "accounting.cutover_write_allowed" in SQL
    assert "Opening-balance workbook changes must use the protected accounting functions." in SQL


def test_workbook_snapshots_source_references_without_posting() -> None:
    assert "accounting.opening_balance_cutover_source_reference" in SQL
    assert "accounting.create_opening_balance_workbook" in SQL
    assert "source_snapshot" in SQL
    assert "false AS ready_to_post" in SQL
    assert "false AS opening_balance_posting_enabled" in SQL
    assert "false AS automatic_source_posting_enabled" in SQL
    assert "post_journal_entry" not in SQL


def test_verified_lines_require_explicit_amount_and_evidence() -> None:
    assert "A verified opening-balance line requires an explicit amount" in SQL
    assert "including zero when appropriate" in SQL
    assert "requires a short evidence or reconciliation note" in SQL
    assert "An opening-balance line cannot contain both a debit and a credit amount" in SQL


def test_review_gate_requires_complete_balanced_approved_workbook() -> None:
    assert "Every opening-balance workbook line must be explicitly verified before review" in SQL
    assert "The opening-balance workbook must balance before review" in SQL
    assert "Confirm the P&L migration policy before review" in SQL
    assert "The cutover date must remain inside an open accounting period before review" in SQL
    assert "Blocked loan sources must be resolved before review" in SQL
    assert "review_ready" in SQL
