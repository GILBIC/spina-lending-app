from pathlib import Path


SQL = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0026_validate_7x7_schedule_and_add_cutover_worksheet.sql"
).read_text(encoding="utf-8")


def test_7x7_contract_schedule_is_explicitly_validated() -> None:
    assert "contractual_interest_payment_frequency" in SQL
    assert "'daily'" in SQL
    assert "contractual_principal_due" in SQL
    assert "on_or_before_maturity" in SQL
    assert "principal_prepayment_allowed" in SQL
    assert "principal_prepayment_changes_daily_interest" in SQL
    assert "effective_interest_base_schedule_validated" in SQL
    assert "7x7_interest_daily_balloon_v2" in SQL


def test_7x7_reference_schedule_keeps_original_principal_interest_rule() -> None:
    assert "ceil(loan.principal / 1000.0) * loan_type.daily_interest_per_1000" in SQL
    assert "seven_by_seven_contract_interest_total" in SQL
    assert "seven_by_seven_contract_total_if_principal_at_maturity" in SQL
    assert "seven_by_seven_base_daily_rate_percent" in SQL
    assert "mobile_collections_enabled" in SQL


def test_cutover_readiness_moves_to_opening_balance_stage() -> None:
    assert "CREATE VIEW accounting.cutover_readiness_summary" in SQL
    assert "opening_balances_required" in SQL
    assert "false AS opening_balances_configured" in SQL
    assert "false AS automatic_source_posting_enabled" in SQL


def test_opening_balance_worksheet_is_reference_only_and_not_postable() -> None:
    assert "opening_balance_cutover_worksheet" in SQL
    assert "opening_balance_cutover_summary" in SQL
    assert "regular_operational_reference" in SQL
    assert "7x7_principal_reference" in SQL
    assert "ecl_assessment_required" in SQL
    assert "source_review_required" in SQL
    assert "false AS worksheet_balanced" in SQL
    assert "false AS ready_to_post" in SQL
    assert "false AS opening_balance_posting_enabled" in SQL


def test_cutover_worksheet_requires_cash_and_balance_sheet_reconciliation() -> None:
    assert "actual office cash count" in SQL
    assert "unremitted collection cash" in SQL
    assert "Received remittances are a custody reference only" in SQL
    assert "effective-interest schedule" in SQL
    assert "verified accounts payable" in SQL
    assert "verified tax liabilities" in SQL
    assert "verified contributed capital" in SQL
    assert "retained earnings" in SQL
