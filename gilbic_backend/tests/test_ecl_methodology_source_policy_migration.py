from pathlib import Path


SQL = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0069_add_ecl_methodology_source_policy.sql"
).read_text(encoding="utf-8")


DOC = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "accounting"
    / "ecl-methodology-source-policy.md"
).read_text(encoding="utf-8")


def test_policy_approves_cash_shortfall_method_without_numeric_model_defaults() -> None:
    assert "ecl_methodology_v1" in SQL
    assert "probability_weighted_discounted_expected_cash_shortfall" in SQL
    assert "original_effective_interest_rate" in SQL
    assert "true AS probability_weighted_outcomes_required" in SQL
    assert "true AS time_value_of_money_required" in SQL
    assert "true AS forward_looking_information_required" in SQL
    assert "false AS pd_lgd_parameter_model_required" in SQL
    assert "false AS numeric_pd_enabled" in SQL
    assert "false AS numeric_lgd_enabled" in SQL
    assert "false AS numeric_cure_rate_enabled" in SQL
    assert "false AS numeric_recovery_rate_enabled" in SQL
    assert "false AS scenario_weights_enabled" in SQL


def test_policy_keeps_30_and_90_dpd_as_rebuttable_backstops() -> None:
    assert "true AS sicr_30_dpd_backstop_is_rebuttable" in SQL
    assert "true AS default_90_dpd_backstop_is_rebuttable" in SQL
    assert "not an automatic Stage 2 label" in DOC
    assert "not an irreversible automatic default label" in DOC


def test_policy_approves_only_named_evidence_source_classes() -> None:
    for source_class in (
        "verified_contractual_cash_flows",
        "original_eir_and_carrying_evidence",
        "protected_collection_history",
        "contractual_dpd_and_qualitative_credit_risk_evidence",
        "historical_loan_episode_dataset",
        "management_reviewed_default_outcomes",
        "protected_loss_recovery_writeoff_evidence",
        "authoritative_forward_looking_economic_evidence",
    ):
        assert source_class in SQL


def test_policy_fails_closed_before_loss_recovery_and_forward_looking_evidence() -> None:
    assert "false AS protected_loss_recovery_evidence_ready" in SQL
    assert "false AS forward_looking_evidence_ready" in SQL
    assert "protected_loss_recovery_evidence_required" in SQL
    assert "false AS staging_automation_enabled" in SQL
    assert "false AS quantitative_ecl_ready" in SQL
    assert "false AS ecl_calculation_enabled" in SQL
    assert "false AS account_1190_posting_enabled" in SQL
    assert "false AS automatic_source_posting" in SQL


def test_policy_migration_is_view_only_and_does_not_create_financial_history() -> None:
    upper = SQL.upper()
    assert "CREATE TABLE" not in upper
    assert "INSERT INTO ACCOUNTING.JOURNAL_ENTRIES" not in upper
    assert "INSERT INTO ACCOUNTING.JOURNAL_LINES" not in upper
    assert "UPDATE LENDING." not in upper
    assert "DELETE FROM LENDING." not in upper
    assert "SET EXPLICIT_DEFAULT_LABEL" not in upper
    assert "SET EXPLICIT_LOSS_AMOUNT" not in upper
    assert "SET EXPLICIT_RECOVERY_AMOUNT" not in upper
    assert "1190" in SQL


def test_policy_document_uses_primary_ifrs_foundation_references() -> None:
    assert "https://www.ifrs.org/issued-standards/list-of-standards/ifrs-9-financial-instruments/" in DOC
    assert "https://www.ifrs.org/news-and-events/updates/ifric/2022/ifric-update-september-2022/" in DOC
    assert "https://www.ifrs.org/news-and-events/updates/ifric/2019/ifric-update-march-2019/" in DOC
    assert "https://media.ifrs.org/2013/IASB/October/IASB-Update-October-2013.html" in DOC
    assert "https://media.ifrs.org/2013/IASB/September/IASB-Update-September-2013.html" in DOC
