BEGIN;

-- Master Issue #296: approve the V1 expected-credit-loss methodology and the
-- source classes that may support it without inventing PD, LGD, cure,
-- recovery, scenario-weight, staging, write-off or ECL values.
--
-- IFRS 9 measurement is implemented here only as a policy boundary. A later
-- protected measurement stage must estimate probability-weighted expected cash
-- shortfalls, reflect time value of money, and use reasonable and supportable
-- past, current and forward-looking information. Credit-loss cash shortfalls
-- are discounted using the original effective interest rate.
--
-- This migration deliberately creates views only. It does not label a loan,
-- populate historical loss/recovery fields, calculate ECL, populate account
-- 1190, create a journal, or enable automatic source posting.

CREATE OR REPLACE VIEW accounting.ecl_methodology_policy_v1 AS
SELECT
    'ecl_methodology_v1'::text AS policy_version,
    true AS methodology_approved,
    'probability_weighted_discounted_expected_cash_shortfall'::text
        AS measurement_method,
    'original_effective_interest_rate'::text AS discount_rate_basis,
    true AS probability_weighted_outcomes_required,
    true AS time_value_of_money_required,
    true AS past_events_information_required,
    true AS current_conditions_information_required,
    true AS forward_looking_information_required,
    '12_month_ecl_when_lifetime_ecl_criteria_not_met'::text
        AS twelve_month_ecl_policy,
    'lifetime_ecl_when_significant_increase_in_credit_risk'::text
        AS lifetime_ecl_policy,
    true AS sicr_30_dpd_backstop_is_rebuttable,
    true AS default_90_dpd_backstop_is_rebuttable,
    false AS pd_lgd_parameter_model_required,
    false AS numeric_pd_enabled,
    false AS numeric_lgd_enabled,
    false AS numeric_cure_rate_enabled,
    false AS numeric_recovery_rate_enabled,
    false AS scenario_weights_enabled,
    false AS automatic_staging_enabled,
    false AS automatic_default_enabled,
    false AS automatic_write_off_enabled,
    false AS ecl_calculation_enabled,
    false AS account_1190_posting_enabled,
    false AS automatic_source_posting;

CREATE OR REPLACE VIEW accounting.ecl_approved_source_classes_v1 AS
SELECT *
FROM (
    VALUES
        (
            1,
            'verified_contractual_cash_flows'::text,
            'Active immutable verified signed-contract schedules and exact contractual installments.'::text,
            true,
            'contractual_cash_flow_baseline'::text
        ),
        (
            2,
            'original_eir_and_carrying_evidence'::text,
            'Protected original-EIR, initial-measurement and reconciled carrying evidence for the applicable loan accounting path.'::text,
            true,
            'discount_and_exposure_basis'::text
        ),
        (
            3,
            'protected_collection_history'::text,
            'Authoritative non-voided collection events plus protected posting/reversal history; mutable operational summaries are not substitutes.'::text,
            true,
            'observed_cash_and_performance'::text
        ),
        (
            4,
            'contractual_dpd_and_qualitative_credit_risk_evidence'::text,
            'Contract-driven DPD backstops and separately evidenced qualitative credit-risk facts. DPD alone does not create an automatic stage or default label.'::text,
            true,
            'credit_risk_change_evidence'::text
        ),
        (
            5,
            'historical_loan_episode_dataset'::text,
            'Immutable accounting-only reconstructed historical loan episodes with source-quality status.'::text,
            true,
            'historical_experience'::text
        ),
        (
            6,
            'management_reviewed_default_outcomes'::text,
            'Immutable Management-reviewed historical default/non-default outcomes recorded through the protected review workflow.'::text,
            true,
            'historical_default_outcomes'::text
        ),
        (
            7,
            'protected_loss_recovery_writeoff_evidence'::text,
            'Future protected evidence for actual loss, recovery, cure and write-off outcomes. Existing nullable historical fields are not authoritative until that protected workflow exists.'::text,
            true,
            'loss_and_recovery_experience'::text
        ),
        (
            8,
            'authoritative_forward_looking_economic_evidence'::text,
            'Versioned reasonable-and-supportable external economic evidence and Management-approved scenario interpretation. No variable, forecast or scenario weight is assumed by this policy.'::text,
            true,
            'forward_looking_adjustment'::text
        )
) AS approved_source(
    source_order,
    source_class,
    source_definition,
    approved_for_v1_methodology,
    methodology_role
);

CREATE OR REPLACE VIEW accounting.ecl_methodology_source_readiness AS
WITH historical AS (
    SELECT
        episode_count,
        structurally_usable_count,
        source_review_required_count,
        pending_outcome_review_count,
        reviewed_outcome_count,
        reviewed_default_count,
        reviewed_non_default_count
    FROM accounting.ecl_outcome_label_review_summary
)
SELECT
    historical.episode_count AS historical_episode_count,
    historical.structurally_usable_count AS historical_structurally_usable_count,
    historical.source_review_required_count AS historical_source_review_required_count,
    historical.pending_outcome_review_count AS historical_pending_outcome_review_count,
    historical.reviewed_outcome_count AS historical_reviewed_outcome_count,
    historical.reviewed_default_count AS historical_reviewed_default_count,
    historical.reviewed_non_default_count AS historical_reviewed_non_default_count,
    true AS contractual_cash_flow_source_approved,
    true AS original_eir_and_carrying_source_approved,
    true AS protected_collection_history_source_approved,
    true AS contractual_dpd_and_qualitative_source_approved,
    true AS historical_episode_source_approved,
    true AS reviewed_default_outcome_source_approved,
    true AS protected_loss_recovery_source_class_approved,
    true AS forward_looking_source_class_approved,
    false AS protected_loss_recovery_evidence_ready,
    false AS forward_looking_evidence_ready,
    CASE
        WHEN historical.episode_count = 0
            THEN 'historical_dataset_required'
        WHEN historical.structurally_usable_count = 0
            THEN 'historical_source_review_required'
        WHEN historical.pending_outcome_review_count > 0
            THEN 'historical_outcome_review_required'
        WHEN historical.reviewed_default_count = 0
            THEN 'default_outcome_evidence_required'
        ELSE 'protected_loss_recovery_evidence_required'
    END AS methodology_source_status,
    true AS methodology_policy_approved,
    false AS staging_automation_enabled,
    false AS quantitative_ecl_ready,
    false AS ecl_calculation_enabled,
    false AS account_1190_posting_enabled,
    false AS automatic_source_posting
FROM historical;

COMMENT ON VIEW accounting.ecl_methodology_policy_v1 IS
    'Master #296 approved V1 ECL methodology boundary: probability-weighted discounted expected cash shortfalls using reasonable/supportable past, current and forward-looking information. No numeric PD/LGD/cure/recovery/scenario assumptions are enabled.';

COMMENT ON VIEW accounting.ecl_approved_source_classes_v1 IS
    'Approved evidence classes for the SPINA V1 ECL methodology. Approval of a source class does not mean the required evidence is currently complete or quantitative ECL is enabled.';

COMMENT ON VIEW accounting.ecl_methodology_source_readiness IS
    'Fail-closed ECL source readiness. Protected loss/recovery evidence and forward-looking evidence remain required before quantitative ECL; staging, 1190 posting and automatic source posting remain disabled.';

COMMIT;
