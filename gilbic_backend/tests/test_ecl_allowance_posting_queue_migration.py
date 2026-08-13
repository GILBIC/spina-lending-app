from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "sql" / "0078_harden_ecl_allowance_posting_queue.sql").read_text(
    encoding="utf-8"
)


def test_0078_exposes_exact_preparation_candidates_without_writing() -> None:
    lower = SQL.lower()
    assert SQL.strip().startswith("BEGIN;")
    assert SQL.strip().endswith("COMMIT;")
    assert "measurement_queue.measurement_id" in lower
    assert "measurement_queue.measurement_date" in lower
    assert "measurement_queue.authoritative_ecl_amount" in lower
    assert "credit_loss_expense_account_id" in lower
    assert "allowance_account_id" in lower
    assert "accounting.ecl_loan_allowance_balance" in lower
    assert "period.status = 'open'" in lower
    assert "insert into accounting.journal_entries" not in lower
    assert "insert into accounting.journal_lines" not in lower


def test_0078_fails_closed_when_exact_coordinates_are_missing() -> None:
    lower = SQL.lower()
    assert "credit_loss_expense_account_count <> 1" in lower
    assert "allowance_account_count <> 1" in lower
    assert "preparation_blocked" in lower
    assert "measurement_not_authoritative" in lower
    assert "a5_remeasurement_required" in lower
    assert "posting_audit_incomplete" in lower


def test_0078_enables_only_explicit_1190_path() -> None:
    assert "true AS account_1190_posting_enabled" in SQL
    assert "false AS automatic_source_posting" in SQL
