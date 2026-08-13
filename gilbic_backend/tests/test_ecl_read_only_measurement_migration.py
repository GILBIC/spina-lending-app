from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SQL = (
    ROOT / "sql" / "0075_add_read_only_quantitative_ecl_measurement.sql"
).read_text(encoding="utf-8")
DOC = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "accounting"
    / "ecl-read-only-measurement-policy.md"
).read_text(encoding="utf-8")


def test_0075_is_read_only_accounting_and_preserves_posting_boundary() -> None:
    lower = SQL.lower()
    assert SQL.strip().startswith("BEGIN;")
    assert SQL.strip().endswith("COMMIT;")
    assert "create table if not exists accounting.ecl_quantitative_measurements" in lower
    assert "record_read_only_quantitative_ecl_measurement" in lower
    assert "accounting.ecl.measurement.review" in lower
    assert "insert into accounting.journal_entries" not in lower
    assert "insert into accounting.journal_lines" not in lower
    assert "account_1190_posting_enabled" in lower
    assert "false as account_1190_posting_enabled" in lower
    assert "false as automatic_source_posting" in lower


def test_0075_uses_probability_weighted_discounted_cash_shortfall_not_pd_lgd() -> None:
    lower = SQL.lower()
    assert "loan_level_probability_weighted_discounted_cash_shortfall_v1" in SQL
    assert "original_daily_eir_calendar_days_to_measurement_date" in SQL
    assert "remaining_amount / power(" in SQL
    assert "expected_amount / power(" in SQL
    assert "scenario_shortfall := greatest(contractual_pv - expected_pv, 0)" in SQL
    assert "weighted_shortfall := weighted_shortfall + probability * scenario_shortfall" in SQL
    assert "scenario probabilities must sum exactly to 1.000000000000" in lower
    assert "pd x lgd" in lower
    assert "does not substitute an invented pd × lgd model" in DOC.lower()


def test_0075_stage_1_is_event_horizon_not_cash_flow_truncation() -> None:
    assert "WHEN 'stage_1_12_month' THEN '12_month'" in SQL
    assert "WHEN 'stage_2_lifetime' THEN 'lifetime'" in SQL
    assert "WHEN 'stage_3_credit_impaired' THEN 'lifetime'" in SQL
    assert "cash flows are not" in SQL
    assert "mechanically truncated at 12 months" in DOC


def test_0075_pins_exact_protected_inputs_and_digest() -> None:
    lower = SQL.lower()
    for token in (
        "schedule_id",
        "schedule_version",
        "contract_reference",
        "label_review_id",
        "label_review_version",
        "original_eir_source_key",
        "original_eir_policy_version",
        "original_daily_eir",
        "forward_evidence_ids",
        "input_snapshot",
        "contractual_cash_flow_snapshot",
        "scenario_snapshot",
        "measurement_date",
        "calculation_digest",
        "sha256",
    ):
        assert token in lower
    assert "unique (loan_id, measurement_date, calculation_digest)" in lower
    assert "measurements are immutable and versioned" in DOC.lower()


def test_0075_blocks_direct_writes_and_incomplete_loans() -> None:
    lower = SQL.lower()
    assert "before insert or update or delete" in lower
    assert "must use the protected management measurement function" in lower
    assert "if not coalesce(readiness.quantitative_input_ready, false)" in lower
    assert "quantitative ecl input gate is blocked" in lower
    assert "when readiness.quantitative_input_ready = false then 'input_blocked'" in lower
    assert "else null::numeric(18,2)" in lower
    assert "blocked or incomplete loans" in DOC.lower()


def test_0075_requires_explicit_evidence_supported_scenarios_without_defaults() -> None:
    lower = SQL.lower()
    assert "between 2 and 20 explicit evidence-supported scenarios" in lower
    assert "forward_evidence_ids" in lower
    assert "ready_for_new_measurement" in lower
    assert "scenario_probability_defaulted" in SQL
    assert "false AS scenario_probability_defaulted" in SQL
    assert "free-text notes cannot clear" in DOC.lower()
    assert "scenario probabilities are exact to at most 12 decimal places" in DOC.lower()


def test_0075_hardens_forward_evidence_forecast_start() -> None:
    assert "current_date >= evidence.forecast_period_start" in SQL
    assert "current_date < evidence.forecast_period_start" in SQL
    assert "cannot satisfy readiness before both" in DOC
