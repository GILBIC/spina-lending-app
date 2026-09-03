from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "gilbic_backend" / "sql" / "0107_align_7x7_operational_readers.sql"


def test_0107_keeps_signed_totals_but_uses_operational_amount_for_dpd() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "CREATE OR REPLACE VIEW accounting.loan_contract_dpd_assessment" in sql
    assert "installment.contractual_amount" in sql
    assert "installment.operational_amount" in sql
    assert "balance.operational_amount - balance.active_allocated_amount" in sql
    assert "balance.removed_from_operational_schedule = false" in sql


def test_0107_uses_active_advance_and_reconciles_extra_principal_receipts() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "lending.loan_installment_active_advance" in sql
    assert "active_advance.active_advance_allocated" in sql
    assert "lending.seven_by_seven_extra_principal_adjustments" in sql
    assert "adjustment.principal_reduction" in sql
    assert "historical_installment_allocation_total" in sql
    assert "extra_principal_allocation_total" in sql


def test_0107_preserves_existing_dpd_public_columns() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    for column in (
        "contractual_schedule_total",
        "allocated_schedule_total",
        "eligible_transaction_total",
        "eligible_allocated_total",
        "due_unpaid_amount",
        "earliest_unpaid_due_date",
        "dpd_data_status",
        "days_past_due",
        "thirty_day_sicr_backstop_reached",
        "ninety_day_default_backstop_reached",
    ):
        assert column in sql
