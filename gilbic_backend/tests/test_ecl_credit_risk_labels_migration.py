from pathlib import Path


SQL_ROOT = Path(__file__).resolve().parents[1] / "sql"
SQL = (SQL_ROOT / "0070_add_ecl_credit_risk_labels.sql").read_text(encoding="utf-8")
HARDENING_SQL = (
    SQL_ROOT / "0071_harden_ecl_cash_recovery_chronology.sql"
).read_text(encoding="utf-8")
READINESS_SQL = (
    SQL_ROOT / "0072_add_ecl_quantitative_input_readiness.sql"
).read_text(encoding="utf-8")

DOC = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "accounting"
    / "ecl-credit-risk-label-policy.md"
).read_text(encoding="utf-8")


def test_ecl_label_migration_defines_supported_stage_default_writeoff_recovery_labels() -> None:
    for value in (
        "stage_1_12_month",
        "stage_2_lifetime",
        "stage_3_credit_impaired",
        "supported_no_reasonable_expectation_of_recovery",
        "cash_recovery_observed",
        "cured",
    ):
        assert value in SQL


def test_ecl_label_migration_keeps_30_and_90_dpd_as_rebuttable_backstops() -> None:
    assert "sicr_backstop_rebutted" in SQL
    assert "default_backstop_rebutted" in SQL
    assert "30-DPD SICR backstop" in SQL
    assert "90-DPD default backstop" in SQL
    assert "Contractual DPD alone cannot be the separate evidence" in SQL
    assert "rebuttable SICR backstop" in DOC
    assert "rebuttable default backstop" in DOC


def test_ecl_label_migration_requires_separate_evidence_for_early_deterioration_writeoff_and_cure() -> None:
    assert "before the 30-DPD backstop requires separately evidenced" in SQL
    assert "before the 90-DPD backstop requires separately evidenced" in SQL
    assert "Write-off support requires explicit no-reasonable-expectation-of-recovery evidence" in SQL
    assert "Contractual DPD alone cannot support a write-off conclusion" in SQL
    assert "Contractual DPD alone cannot prove a cure" in SQL
    assert "Recovery transaction must be a later non-voided positive protected collection" in SQL


def test_0071_requires_authoritative_strict_recovery_timestamp_ordering() -> None:
    normalized = HARDENING_SQL.upper()
    assert HARDENING_SQL.strip().startswith("BEGIN;")
    assert HARDENING_SQL.strip().endswith("COMMIT;")
    assert "GUARD_ECL_CASH_RECOVERY_CHRONOLOGY" in normalized
    assert "ECL_CASH_RECOVERY_CHRONOLOGY_GUARD" in normalized
    assert "BEFORE INSERT ON ACCOUNTING.ECL_CREDIT_RISK_LABEL_REVIEWS" in normalized
    assert "PRIOR_REVIEW.REVIEW_VERSION + 1 <> NEW.REVIEW_VERSION" in normalized
    assert "NEWER.REVIEW_VERSION > PRIOR_REVIEW.REVIEW_VERSION" in normalized
    assert "RECOVERY_TX.ACCEPTED_AT <= PRIOR_REVIEW.CREATED_AT" in normalized
    assert "IMMEDIATELY PRIOR DETERIORATED REVIEW FOR THE SAME LOAN" in normalized
    assert "SAME-CALENDAR-DAY ORDERING IS NEVER INFERRED" in normalized
    assert "RECOVERY_TX.COLLECTION_DATE < PRIOR_REVIEW.CREATED_AT::DATE" not in normalized
    assert "INSERT INTO ACCOUNTING.JOURNAL_ENTRIES" not in normalized
    assert "INSERT INTO ACCOUNTING.JOURNAL_LINES" not in normalized


def test_0072_defines_one_deterministic_fail_closed_input_gate_per_loan() -> None:
    normalized = READINESS_SQL.upper()
    assert READINESS_SQL.strip().startswith("BEGIN;")
    assert READINESS_SQL.strip().endswith("COMMIT;")
    assert "CREATE OR REPLACE VIEW ACCOUNTING.ECL_QUANTITATIVE_INPUT_READINESS AS" in normalized
    assert "CREATE OR REPLACE VIEW ACCOUNTING.ECL_QUANTITATIVE_INPUT_READINESS_SUMMARY AS" in normalized
    for blocker in (
        "verified_contractual_schedule_dpd_required",
        "current_credit_risk_label_required",
        "original_eir_initial_carrying_evidence_required",
        "protected_collection_posting_reversal_history_required",
        "authoritative_current_gross_carrying_evidence_required",
        "required_loss_recovery_writeoff_outcome_evidence_required",
        "approved_forward_looking_evidence_required",
    ):
        assert blocker in READINESS_SQL
    for ordinal in ("10,", "20,", "30,", "40,", "45,", "50,", "60,"):
        assert ordinal in READINESS_SQL
    assert "array_agg(blocker.code ORDER BY blocker.ordinal)" in READINESS_SQL
    assert "jsonb_agg(" in READINESS_SQL
    assert "ORDER BY blocker.ordinal" in READINESS_SQL
    assert "cardinality(diagnostic.blocker_codes) = 0 AS quantitative_input_ready" in READINESS_SQL


def test_0072_keeps_forward_looking_evidence_explicitly_blocked_until_a2() -> None:
    assert "false AS approved_forward_looking_evidence_ready" in READINESS_SQL
    assert "forward_looking_governance_not_installed" in READINESS_SQL
    assert "A2 governance is not installed yet" in READINESS_SQL
    assert "Approved versioned forward-looking economic evidence is required" in READINESS_SQL


def test_0072_never_substitutes_notes_or_enables_quantitative_accounting() -> None:
    lower = READINESS_SQL.lower()
    assert "Typed/free-text notes never substitute" in READINESS_SQL
    assert "NULL::numeric(18,2) AS ecl_amount" in READINESS_SQL
    assert "false AS ecl_calculation_enabled" in READINESS_SQL
    assert "false AS account_1190_posting_enabled" in READINESS_SQL
    assert "false AS automatic_source_posting" in READINESS_SQL
    assert "insert into accounting.journal_entries" not in lower
    assert "insert into accounting.journal_lines" not in lower
    assert "update accounting.journal_entries" not in lower
    assert "insert into accounting.ecl_credit_risk_label_reviews" not in lower


def test_0072_rechecks_exact_protected_collection_posting_and_reversal_history() -> None:
    assert "accounting.regular_journal_posting_entries" in READINESS_SQL
    assert "accounting.regular_journal_reversal_sets" in READINESS_SQL
    assert "accounting.regular_journal_reversal_entries" in READINESS_SQL
    assert "accounting.seven_by_seven_journal_postings" in READINESS_SQL
    assert "accounting.seven_by_seven_journal_reversals" in READINESS_SQL
    assert "journal.status = 'posted'" in READINESS_SQL
    assert "reversal_journal.status = 'posted'" in READINESS_SQL


def test_ecl_label_reviews_are_immutable_and_versioned() -> None:
    assert "CREATE TABLE IF NOT EXISTS accounting.ecl_credit_risk_label_reviews" in SQL
    assert "UNIQUE (loan_id, review_version)" in SQL
    assert "supersedes_review_id" in SQL
    assert "Historical" not in SQL.split("guard_ecl_credit_risk_label_audit", 1)[1].split("END;", 1)[0]
    assert "ECL credit-risk label review records are immutable." in SQL


def test_ecl_label_queue_stales_only_on_schedule_or_evidence_band_boundary() -> None:
    assert "past_due_1_29" in SQL
    assert "past_due_30_89" in SQL
    assert "past_due_90_plus" in SQL
    assert "review.snapshot_schedule_id <> dpd.schedule_id" in SQL
    assert "review.snapshot_schedule_version <> dpd.schedule_version" in SQL
    assert "review.snapshot_dpd_risk_band <> dpd.current_dpd_risk_band" in SQL
    assert "label_refresh_required" in SQL


def test_ecl_label_stage_remains_non_quantitative_and_non_posting() -> None:
    lower = SQL.lower()
    upper = SQL.upper()
    hardening_lower = HARDENING_SQL.lower()
    readiness_lower = READINESS_SQL.lower()
    assert "false AS automatic_staging_enabled" in SQL
    assert "false AS automatic_default_enabled" in SQL
    assert "false AS automatic_write_off_enabled" in SQL
    assert "false AS automatic_recovery_enabled" in SQL
    assert "false AS quantitative_ecl_ready" in SQL
    assert "false AS ecl_calculation_enabled" in SQL
    assert "false AS account_1190_posting_enabled" in SQL
    assert "false AS automatic_source_posting" in SQL
    assert "insert into accounting.journal_entries" not in lower
    assert "insert into accounting.journal_lines" not in lower
    assert "update accounting.journal_entries" not in lower
    assert "insert into accounting.journal_entries" not in hardening_lower
    assert "insert into accounting.journal_lines" not in hardening_lower
    assert "insert into accounting.journal_entries" not in readiness_lower
    assert "insert into accounting.journal_lines" not in readiness_lower
    assert "CREATE OR REPLACE FUNCTION ACCOUNTING.REVIEW_ECL_CREDIT_RISK_LABELS" in upper


def test_policy_document_uses_primary_accounting_sources() -> None:
    assert "https://www.ifrs.org/issued-standards/list-of-standards/ifrs-9-financial-instruments/" in DOC
    assert "https://media.ifrs.org/2013/IASB/October/IASB-Update-October-2013.html" in DOC
    assert "https://media.ifrs.org/2013/IASB/September/IASB-Update-September-2013.html" in DOC
    assert "https://www.ifrs.org/news-and-events/updates/ifric/2018/ifric-update-november-2018/" in DOC
    assert "https://www.ifrs.org/projects/completed-projects/2019/curing-of-a-credit-impaired-financial-asset-ifrs-9/" in DOC
    assert "https://standards.aasb.gov.au/aasb-9-sep-2020" in DOC