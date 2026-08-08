from pathlib import Path


SQL = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0030_add_accounting_ecl_assessment_readiness.sql"
).read_text(encoding="utf-8")


def test_stage5e_defines_read_only_ecl_assessment_views() -> None:
    assert "CREATE VIEW accounting.ecl_assessment_at_cutover" in SQL
    assert "CREATE VIEW accounting.ecl_assessment_summary" in SQL
    assert "days_past_due_backstop" in SQL
    assert "sicr_30dpd_backstop" in SQL
    assert "default_90dpd_backstop" in SQL


def test_stage5e_does_not_invent_ecl_rates_or_amounts() -> None:
    assert "NULL::numeric(18,8) AS probability_of_default" in SQL
    assert "NULL::numeric(18,8) AS loss_given_default" in SQL
    assert "NULL::numeric(18,8) AS forward_looking_multiplier" in SQL
    assert "NULL::numeric(18,2) AS ecl_amount" in SQL
    assert "historical_loss_calibration_configured" in SQL
    assert "forward_looking_scenarios_configured" in SQL


def test_stage5e_exposes_1190_as_policy_blocked_reference() -> None:
    assert "'1190'" in SQL
    assert "ECL is intentionally not quantified" in SQL
    assert "NULL::numeric" in SQL
    assert "calibration_required" in SQL


def test_stage5e_keeps_posting_disabled() -> None:
    assert "false AS ecl_included" in SQL
    assert "false AS ready_to_post" in SQL
    assert "post_journal_entry" not in SQL
    assert "post_manual_journal_entry" not in SQL
    assert "update_opening_balance_workbook_line" not in SQL
    assert "INSERT INTO accounting.journal_entries" not in SQL


def test_stage5e_labels_30_and_90_day_values_as_backstops_not_stages() -> None:
    assert "rebuttable backstop indicators" in SQL
    assert "NULL::integer AS ecl_stage" in SQL
    assert "days_past_due_backstop >= 30" in SQL
    assert "days_past_due_backstop >= 90" in SQL
