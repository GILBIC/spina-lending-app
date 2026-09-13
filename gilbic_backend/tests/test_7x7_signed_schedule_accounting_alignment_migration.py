from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0115_align_7x7_signed_schedule_accounting_authority.sql"
)


def test_priority6_migration_replaces_reconstructed_7x7_contract_cash_flows() -> None:
    assert MIGRATION.is_file(), (
        "Priority #6 requires a forward migration that makes the exact verified "
        "signed 7x7 installments authoritative for accounting readiness."
    )

    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "create or replace view accounting.seven_by_seven_contractual_cash_flow_lines" in sql
    assert "create or replace view accounting.seven_by_seven_contractual_cash_flow_readiness" in sql
    assert "lending.loan_contract_installments" in sql
    assert "principal_component" in sql
    assert "interest_component" in sql
    assert "contractual_amount" in sql

    # The old 0060 view rebuilt a different contract from product term_days,
    # required daily_amount to equal daily interest, and forced principal into
    # the maturity row. Priority #6 must not preserve those authorities.
    assert "installment.installment_number > source.term_days" not in sql
    assert "source.daily_amount <> source.expected_daily_contractual_interest" not in sql
    assert "rollup.installment_count, 0) <> source.term_days" not in sql
    assert "when installment.installment_number = source.term_days" not in sql

    # Loan-level maturity must reconcile to the last exact signed installment.
    assert "last_due_date" in sql
    assert "source.due_date" in sql
