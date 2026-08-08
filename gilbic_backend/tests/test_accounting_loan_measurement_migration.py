from pathlib import Path


SQL = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0028_add_accounting_loan_measurement_engine.sql"
).read_text(encoding="utf-8")


def test_regular_and_7x7_eir_solvers_are_defined() -> None:
    assert "accounting.solve_level_payment_daily_eir" in SQL
    assert "accounting.solve_daily_coupon_balloon_eir" in SQL
    assert "accounting.measure_loan_at_cutover" in SQL


def test_measurement_uses_actual_non_voided_cash_timing() -> None:
    assert "t.collection_date = day_date" in SQL
    assert "t.is_voided = false" in SQL
    assert "t.entry_type <> 'pass'" in SQL
    assert "covered advance dates do not move the accounting cash date" in SQL


def test_7x7_cash_activity_requires_review_before_using_measurement() -> None:
    assert "7x7_cash_flow_review_required" in SQL
    assert "Principal-versus-interest allocation" in SQL
    assert "principal-prepayment modification" in SQL


def test_measurement_is_reference_only_and_excludes_ecl() -> None:
    assert "accounting.opening_balance_measurement_reference" in SQL
    assert "measurement_reference_amount" in SQL
    assert "false AS ecl_included" in SQL
    assert "false AS ready_to_post" in SQL
    assert "post_journal_entry" not in SQL
    assert "update_opening_balance_workbook_line" not in SQL
