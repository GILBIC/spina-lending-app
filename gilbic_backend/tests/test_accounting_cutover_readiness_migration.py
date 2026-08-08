from pathlib import Path


SQL = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0025_add_accounting_cutover_readiness.sql"
).read_text(encoding="utf-8")


def test_regular_contract_metadata_is_normalized_with_audit() -> None:
    assert "loan_contract_metadata_audit" in SQL
    assert "contract_interest_rate_percent" in SQL
    assert "20.0000" in SQL
    assert "calculation_mode = 'fixed_daily'" in SQL
    assert "lower(loan_type.name) = 'regular'" in SQL
    assert "guard_loan_contract_metadata_audit" in SQL
    assert "immutable" in SQL.lower()


def test_cutover_readiness_keeps_automatic_posting_disabled() -> None:
    assert "loan_cutover_readiness" in SQL
    assert "cutover_readiness_summary" in SQL
    assert "source_ready" in SQL
    assert "contract_schedule_validation_required" in SQL
    assert "opening_balances_configured" in SQL
    assert "automatic_source_posting_enabled" in SQL
    assert "false AS opening_balances_configured" in SQL
    assert "false AS automatic_source_posting_enabled" in SQL


def test_regular_readiness_validates_contractual_cash_total() -> None:
    assert "loan.daily_amount * loan_type.term_days" in SQL
    assert "loan.principal * (1 + loan.interest_rate / 100.0)" in SQL
    assert "Regular scheduled cash total does not equal principal plus fixed contract interest" in SQL


def test_7x7_readiness_preserves_agreed_original_principal_rule() -> None:
    assert "principal_payment_structure" in SQL
    assert "separate_from_daily_interest" in SQL
    assert "original_principal_until_principal_zero" in SQL
    assert "effective_interest_pending_contract_schedule_validation" in SQL
    assert "7x7 mobile collections must remain disabled" in SQL


def test_reversal_of_reversal_is_blocked_at_database_layer() -> None:
    assert "original.reversal_of_entry_id IS NOT NULL" in SQL
    assert "original.source_type = 'reversal'" in SQL
    assert "A reversal journal cannot be reversed again" in SQL
    assert "create_reversal_draft" in SQL
