from decimal import Decimal
from pathlib import Path


SQL = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0029_reconcile_accounting_loan_measurement_rounding.sql"
).read_text(encoding="utf-8")


def test_stage5d1_preserves_original_measurement_as_internal_raw_function() -> None:
    assert "measure_loan_at_cutover_unreconciled" in SQL
    assert "ALTER FUNCTION accounting.measure_loan_at_cutover(uuid,date)" in SQL
    assert "RENAME TO measure_loan_at_cutover_unreconciled" in SQL


def test_stage5d1_allocates_cent_residual_to_loan_component() -> None:
    assert "raw.gross_carrying_amount" in SQL
    assert "raw.accrued_interest_component" in SQL
    assert "AS loan_component" in SQL
    assert "raw.gross_carrying_amount\n                    - raw.accrued_interest_component" in SQL


def test_stage5d1_rebinds_public_cutover_view_to_reconciled_function() -> None:
    assert "CREATE OR REPLACE VIEW accounting.loan_measurement_at_cutover" in SQL
    assert "CROSS JOIN LATERAL accounting.measure_loan_at_cutover(" in SQL
    assert "accounting.loan_measurement_reconciliation" in SQL
    assert "all_measured_loans_reconciled" in SQL
    assert "summary_reconciled" in SQL


def test_stage5d1_keeps_posting_and_ecl_disabled() -> None:
    assert "false AS ready_to_post" in SQL
    assert "false AS ecl_included" in SQL
    assert "post_journal_entry" not in SQL
    assert "opening_balance_posting_enabled = true" not in SQL
    assert "automatic_source_posting_enabled = true" not in SQL


def test_observed_2026_08_08_cutover_has_two_cent_pre_fix_variance() -> None:
    regular = Decimal("19723.77")
    seven_by_seven = Decimal("9000.00")
    accrued = Decimal("619.36")
    gross = Decimal("29343.11")

    assert regular + seven_by_seven + accrued - gross == Decimal("0.02")


def test_stage5d1_reconciliation_target_preserves_accrued_and_gross() -> None:
    seven_by_seven = Decimal("9000.00")
    accrued = Decimal("619.36")
    gross = Decimal("29343.11")

    reconciled_regular = gross - seven_by_seven - accrued

    assert reconciled_regular == Decimal("19723.75")
    assert reconciled_regular + seven_by_seven + accrued == gross


def test_individual_observed_regular_measurement_reconciles_to_cent() -> None:
    gross = Decimal("4891.49")
    accrued = Decimal("45.42")

    reconciled_loan_component = gross - accrued

    assert reconciled_loan_component == Decimal("4846.07")
    assert reconciled_loan_component + accrued == gross
