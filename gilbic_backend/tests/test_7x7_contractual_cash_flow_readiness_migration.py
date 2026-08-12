from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0060_add_7x7_contractual_cash_flow_readiness.sql"
)


def migration_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_migration_is_transactional_and_read_only() -> None:
    sql = migration_sql()
    stripped = sql.strip()
    assert stripped.startswith("BEGIN;")
    assert stripped.endswith("COMMIT;")
    assert "accounting.seven_by_seven_contractual_cash_flow_lines" in sql
    assert "accounting.seven_by_seven_contractual_cash_flow_readiness" in sql
    assert "accounting.seven_by_seven_contractual_cash_flow_summary" in sql
    assert "INSERT INTO accounting.journal_entries" not in sql
    assert "INSERT INTO accounting.journal_lines" not in sql
    assert "UPDATE lending." not in sql
    assert "DELETE FROM lending." not in sql


def test_signed_contract_is_the_authoritative_schedule_source() -> None:
    sql = migration_sql()
    assert "lending.loan_contract_schedule_registrations" in sql
    assert "source.evidence_basis <> 'signed_contract'" in sql
    assert "verified_signed_contract_schedule_required" in sql
    assert "renewal_or_restructure_policy_required" in sql
    assert "SPINA does not infer a production schedule" in sql


def test_base_7x7_contractual_shape_is_explicit() -> None:
    sql = migration_sql()
    assert "ceil(loan.principal / 1000.0)" in sql
    assert "loan_type.daily_interest_per_1000" in sql
    assert "source.date_released + installment.installment_number" in sql
    assert "source.expected_daily_contractual_interest + source.principal" in sql
    assert "expected_contractual_total_no_prepayment" in sql
    assert "principal_prepayment_allowed" in sql
    assert "principal_prepayment_changes_daily_interest" in sql
    assert "no_prepayment_through_maturity_base_schedule" in sql


def test_pfrs9_follow_on_decisions_remain_fail_closed() -> None:
    sql = migration_sql()
    assert "true AS prepayment_option_requires_eir_estimate" in sql
    assert "false AS sppi_classification_concluded" in sql
    assert "false AS eir_policy_ready" in sql
    assert "false AS carrying_amount_ready" in sql
    assert "false AS journal_lines_enabled" in sql
    assert "false AS automatic_source_posting" in sql
    assert "no borrower prepayment expectation" in sql
    assert "no borrower prepayment expectation, SPPI conclusion, EIR allocation" in sql
