from pathlib import Path


SQL = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0034_add_contractual_schedule_dpd_foundation.sql"
).read_text(encoding="utf-8")


def test_stage5e41_supports_contract_specific_payment_frequencies() -> None:
    for frequency in (
        "daily",
        "weekly",
        "semi_monthly",
        "monthly",
        "balloon",
        "custom",
    ):
        assert f"'{frequency}'" in SQL

    assert "CREATE TABLE IF NOT EXISTS lending.loan_contract_schedules" in SQL
    assert "CREATE TABLE IF NOT EXISTS lending.loan_contract_installments" in SQL
    assert "contract_reference TEXT NOT NULL" in SQL
    assert "grace_days INTEGER NOT NULL DEFAULT 0" in SQL


def test_stage5e41_requires_explicit_installments_and_payment_allocations() -> None:
    assert "CREATE TABLE IF NOT EXISTS lending.loan_installment_payment_allocations" in SQL
    assert "payment_allocation_required" in SQL
    assert "contract_installments_required" in SQL
    assert "Contractual installment allocations cannot exceed the collection transaction amount." in SQL
    assert "Payment allocation must stay within the same loan." in SQL
    assert "A voided collection transaction cannot be allocated" in SQL


def test_stage5e41_uses_contractual_due_dates_for_dpd() -> None:
    assert "CREATE OR REPLACE VIEW accounting.loan_contract_dpd_assessment" in SQL
    assert "earliest_unpaid_due_date" in SQL
    assert "current_date - installments.earliest_unpaid_due_date" in SQL
    assert "thirty_day_sicr_backstop_reached" in SQL
    assert "ninety_day_default_backstop_reached" in SQL


def test_stage5e41_does_not_backfill_or_auto_classify_existing_loans() -> None:
    lowered = SQL.lower()
    assert "automatic_default_label_written" in lowered
    assert "insert into lending.loan_contract_schedules" not in lowered
    assert "update lending.loans" not in lowered
    assert "set explicit_default_label" not in lowered
    assert "insert into accounting.ecl_outcome_label_reviews" not in lowered


def test_stage5e41_still_does_not_calculate_ecl_or_post_to_gl() -> None:
    assert "false AS ecl_included" in SQL
    assert "NULL::numeric(18,2) AS ecl_amount" in SQL
    assert "false AS ready_to_post" in SQL
    assert "INSERT INTO accounting.journal_entries" not in SQL
    assert "post_manual_journal_entry" not in SQL
