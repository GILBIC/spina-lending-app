from pathlib import Path


SQL = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0031_add_accounting_ecl_calibration_readiness.sql"
).read_text(encoding="utf-8")


def test_stage5e1_defines_historical_calibration_inventory() -> None:
    assert "CREATE OR REPLACE VIEW accounting.ecl_calibration_source_inventory" in SQL
    assert "CREATE OR REPLACE VIEW accounting.ecl_calibration_readiness_summary" in SQL
    assert "resolved_loan_count" in SQL
    assert "defaulted_loan_count" in SQL
    assert "valid_cash_collection_count" in SQL
    assert "dedicated_recovery_writeoff_source_present" in SQL


def test_stage5e1_does_not_invent_model_parameters() -> None:
    lowered = SQL.lower()
    assert "probability_of_default" not in lowered
    assert "loss_given_default" not in lowered
    assert "scenario_weight" not in lowered
    assert "management_overlay" not in lowered
    assert "null::numeric(18,2) as ecl_amount" in lowered


def test_stage5e1_keeps_ecl_and_posting_disabled() -> None:
    assert "false AS historical_loss_calibration_configured" in SQL
    assert "false AS forward_looking_scenarios_configured" in SQL
    assert "false AS ecl_included" in SQL
    assert "false AS ready_to_post" in SQL
    assert "INSERT INTO accounting.journal_entries" not in SQL
    assert "post_journal_entry" not in SQL
    assert "update_opening_balance_workbook_line" not in SQL


def test_stage5e1_keeps_1190_unquantified_and_surfaces_source_gap() -> None:
    assert "'1190'" in SQL
    assert "NULL::numeric" in SQL
    assert "historical_data_required" in SQL
    assert "No PD, LGD, recovery rate" in SQL
    assert "Historical outcome/recovery data" in SQL
