BEGIN;

-- Priority #6: the exact active verified signed 7x7 installment schedule is the
-- contractual cash-flow authority. The product-level term_days value is only a
-- default/prefill and must not reconstruct a different accounting schedule.
--
-- This migration intentionally preserves the public columns/types of the 0060
-- accounting views so the existing EIR/classification/carrying evidence chain
-- continues to consume one source. It changes no journal, posting, payment,
-- production data, or pricing/compliance decision.

CREATE OR REPLACE VIEW accounting.seven_by_seven_contractual_cash_flow_lines AS
WITH contract_source AS (
    SELECT
        loan.id AS loan_id,
        loan.loan_number,
        loan.principal,
        loan.daily_amount,
        loan.date_released,
        loan.due_date,
        loan_type.daily_interest_per_1000,
        schedule.id AS schedule_id,
        schedule.schedule_version,
        round(
            ceil(loan.principal / 1000.0)
            * loan_type.daily_interest_per_1000,
            2
        )::numeric(18,2) AS expected_daily_contractual_interest
    FROM lending.loans loan
    JOIN lending.loan_types loan_type
      ON loan_type.id = loan.loan_type_id
    LEFT JOIN lending.loan_contract_schedules schedule
      ON schedule.loan_id = loan.id
     AND schedule.status = 'active'
    WHERE loan_type.calculation_mode = 'seven_by_seven'
), schedule_rows AS (
    SELECT
        source.*,
        installment.id AS installment_id,
        installment.installment_number,
        installment.due_date AS installment_due_date,
        installment.contractual_amount,
        installment.principal_component,
        installment.interest_component,
        max(installment.installment_number) OVER (
            PARTITION BY installment.schedule_id
        ) AS last_installment_number,
        coalesce(
            sum(coalesce(installment.principal_component, 0)) OVER (
                PARTITION BY installment.schedule_id
                ORDER BY installment.installment_number
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
            ),
            0
        )::numeric(18,2) AS prior_principal
    FROM contract_source source
    JOIN lending.loan_contract_installments installment
      ON installment.schedule_id = source.schedule_id
), validated_rows AS (
    SELECT
        row_source.*,
        (row_source.date_released + row_source.installment_number)
            AS expected_due_date,
        CASE
            WHEN row_source.installment_number = row_source.last_installment_number
                THEN round(
                    row_source.principal - row_source.prior_principal,
                    2
                )::numeric(18,2)
            ELSE round(
                row_source.daily_amount
                - row_source.expected_daily_contractual_interest,
                2
            )::numeric(18,2)
        END AS expected_principal_component
    FROM schedule_rows row_source
)
SELECT
    row_source.loan_id,
    row_source.loan_number,
    row_source.schedule_id,
    row_source.schedule_version,
    row_source.installment_id,
    row_source.installment_number,
    row_source.installment_due_date AS due_date,
    row_source.contractual_amount,
    row_source.principal_component,
    row_source.interest_component,
    row_source.expected_due_date,
    round(
        row_source.expected_daily_contractual_interest
        + row_source.expected_principal_component,
        2
    )::numeric(18,2) AS expected_contractual_amount,
    row_source.expected_principal_component,
    row_source.expected_daily_contractual_interest
        AS expected_interest_component,
    CASE
        WHEN row_source.installment_number < 1
            THEN 'installment_number_out_of_contract_term'
        WHEN row_source.installment_due_date <> row_source.expected_due_date
            THEN 'contractual_due_date_mismatch'
        WHEN row_source.daily_amount <= row_source.expected_daily_contractual_interest
            THEN 'agreed_daily_payment_not_above_interest'
        WHEN row_source.principal_component IS NULL
          OR row_source.interest_component IS NULL
            THEN 'contractual_component_missing'
        WHEN row_source.interest_component
             <> row_source.expected_daily_contractual_interest
            THEN 'interest_component_mismatch'
        WHEN row_source.principal_component <= 0
            THEN 'principal_component_mismatch'
        WHEN row_source.contractual_amount
             <> round(
                    row_source.principal_component
                    + row_source.interest_component,
                    2
                )::numeric(18,2)
            THEN 'contractual_amount_component_mismatch'
        WHEN row_source.installment_number < row_source.last_installment_number
         AND row_source.contractual_amount <> row_source.daily_amount
            THEN 'contractual_amount_mismatch'
        WHEN row_source.installment_number = row_source.last_installment_number
         AND row_source.contractual_amount > row_source.daily_amount
            THEN 'contractual_amount_mismatch'
        WHEN row_source.principal_component
             <> row_source.expected_principal_component
            THEN 'principal_component_mismatch'
        ELSE 'line_ready'
    END AS line_status
FROM validated_rows row_source;

COMMENT ON VIEW accounting.seven_by_seven_contractual_cash_flow_lines IS
    'Priority #6 read-only validation of the exact active signed 7x7 daily-payment schedule. Fixed contractual daily interest remains based on original principal; principal is amortized inside the signed installment amounts, with only the final row reduced when required for exact principal reconciliation.';

CREATE OR REPLACE VIEW accounting.seven_by_seven_contractual_cash_flow_readiness AS
WITH source AS (
    SELECT
        loan.id AS loan_id,
        loan.loan_number,
        loan.status AS loan_status,
        loan.principal,
        loan.daily_amount,
        loan.date_released,
        loan.due_date,
        loan_type.code AS loan_type_code,
        loan_type.name AS loan_type_name,
        loan_type.daily_interest_per_1000,
        loan_type.settings AS loan_type_settings,
        schedule.id AS schedule_id,
        schedule.schedule_version,
        schedule.payment_frequency,
        schedule.contract_reference,
        schedule.contract_signed_date,
        schedule.effective_from,
        schedule.grace_days,
        registration.evidence_basis,
        registration.evidence_reference,
        registration.verified_by_user_id,
        registration.verified_at,
        round(
            ceil(loan.principal / 1000.0)
            * loan_type.daily_interest_per_1000,
            2
        )::numeric(18,2) AS expected_daily_contractual_interest
    FROM lending.loans loan
    JOIN lending.loan_types loan_type
      ON loan_type.id = loan.loan_type_id
    LEFT JOIN lending.loan_contract_schedules schedule
      ON schedule.loan_id = loan.id
     AND schedule.status = 'active'
    LEFT JOIN lending.loan_contract_schedule_registrations registration
      ON registration.schedule_id = schedule.id
    WHERE loan_type.calculation_mode = 'seven_by_seven'
), schedule_rollup AS (
    SELECT
        line.loan_id,
        line.schedule_id,
        count(*)::bigint AS installment_count,
        min(line.installment_number) AS first_installment_number,
        max(line.installment_number) AS last_installment_number,
        min(line.due_date) AS first_due_date,
        max(line.due_date) AS last_due_date,
        coalesce(sum(line.contractual_amount), 0)::numeric(18,2)
            AS contractual_schedule_total,
        count(*) FILTER (WHERE line.line_status <> 'line_ready')::bigint
            AS line_mismatch_count,
        coalesce(sum(line.interest_component), 0)::numeric(18,2)
            AS expected_interest_total_from_lines,
        coalesce(sum(line.principal_component), 0)::numeric(18,2)
            AS expected_principal_total_from_lines
    FROM accounting.seven_by_seven_contractual_cash_flow_lines line
    GROUP BY line.loan_id, line.schedule_id
)
SELECT
    source.loan_id,
    source.loan_number,
    source.loan_status,
    source.loan_type_code,
    source.loan_type_name,
    source.principal,
    source.daily_amount,
    source.date_released,
    source.due_date,
    coalesce(rollup.installment_count, 0)::integer AS term_days,
    source.daily_interest_per_1000,
    source.expected_daily_contractual_interest,
    round(
        source.expected_daily_contractual_interest
        * coalesce(rollup.installment_count, 0),
        2
    )::numeric(18,2) AS expected_contractual_interest_total,
    round(
        source.principal
        + source.expected_daily_contractual_interest
          * coalesce(rollup.installment_count, 0),
        2
    )::numeric(18,2) AS expected_contractual_total_no_prepayment,
    source.schedule_id,
    source.schedule_version,
    source.payment_frequency,
    source.contract_reference,
    source.contract_signed_date,
    source.effective_from,
    source.grace_days,
    source.evidence_basis,
    source.evidence_reference,
    source.verified_by_user_id,
    source.verified_at,
    coalesce(rollup.installment_count, 0)::bigint AS installment_count,
    rollup.first_due_date,
    rollup.last_due_date,
    coalesce(rollup.contractual_schedule_total, 0)::numeric(18,2)
        AS contractual_schedule_total,
    coalesce(rollup.line_mismatch_count, 0)::bigint AS line_mismatch_count,
    coalesce(rollup.expected_interest_total_from_lines, 0)::numeric(18,2)
        AS expected_interest_total_from_lines,
    coalesce(rollup.expected_principal_total_from_lines, 0)::numeric(18,2)
        AS expected_principal_total_from_lines,
    coalesce(
        (source.loan_type_settings ->> 'principal_prepayment_allowed')::boolean,
        false
    ) AS principal_prepayment_allowed,
    coalesce(
        (source.loan_type_settings ->> 'principal_prepayment_changes_daily_interest')::boolean,
        true
    ) AS principal_prepayment_changes_daily_interest,
    CASE
        WHEN source.schedule_id IS NULL
            THEN 'verified_signed_contract_schedule_required'
        WHEN source.verified_at IS NULL
            THEN 'verified_signed_contract_schedule_required'
        WHEN source.evidence_basis <> 'signed_contract'
            THEN 'renewal_or_restructure_policy_required'
        WHEN source.contract_signed_date IS NULL
          OR source.contract_signed_date > source.date_released
            THEN 'signed_contract_date_review_required'
        WHEN source.payment_frequency <> 'daily'
          OR source.effective_from <> source.date_released
          OR source.grace_days <> 0
            THEN 'base_contract_timing_review_required'
        WHEN source.daily_interest_per_1000 <= 0
          OR source.daily_amount <= source.expected_daily_contractual_interest
            THEN 'operational_daily_interest_review_required'
        WHEN source.loan_type_settings ->> 'contractual_interest_payment_frequency'
             IS DISTINCT FROM 'daily'
          OR source.loan_type_settings ->> 'contractual_principal_due'
             IS DISTINCT FROM 'on_or_before_maturity'
          OR coalesce(
                (source.loan_type_settings ->> 'principal_prepayment_allowed')::boolean,
                false
             ) = false
          OR coalesce(
                (source.loan_type_settings ->> 'principal_prepayment_changes_daily_interest')::boolean,
                true
             ) = true
            THEN '7x7_contract_policy_review_required'
        WHEN coalesce(rollup.installment_count, 0) <= 0
          OR rollup.first_installment_number <> 1
          OR rollup.last_installment_number <> rollup.installment_count
          OR rollup.first_due_date <> source.date_released + 1
          OR rollup.last_due_date <> source.due_date
          OR rollup.last_due_date - source.date_released
             <> rollup.installment_count::integer
          OR coalesce(rollup.line_mismatch_count, 0) <> 0
          OR coalesce(rollup.contractual_schedule_total, 0)
             <> round(
                    source.principal
                    + source.expected_daily_contractual_interest
                      * coalesce(rollup.installment_count, 0),
                    2
                )::numeric(18,2)
          OR coalesce(rollup.expected_principal_total_from_lines, 0)
             <> source.principal
          OR coalesce(rollup.expected_interest_total_from_lines, 0)
             <> round(
                    source.expected_daily_contractual_interest
                    * coalesce(rollup.installment_count, 0),
                    2
                )::numeric(18,2)
            THEN 'contract_cash_flow_mismatch'
        ELSE 'pfrs9_contract_cash_flow_ready'
    END AS readiness_status,
    CASE
        WHEN source.schedule_id IS NOT NULL
         AND source.verified_at IS NOT NULL
         AND source.evidence_basis = 'signed_contract'
         AND source.contract_signed_date IS NOT NULL
         AND source.contract_signed_date <= source.date_released
         AND source.payment_frequency = 'daily'
         AND source.effective_from = source.date_released
         AND source.grace_days = 0
         AND source.daily_interest_per_1000 > 0
         AND source.daily_amount > source.expected_daily_contractual_interest
         AND source.loan_type_settings ->> 'contractual_interest_payment_frequency' = 'daily'
         AND source.loan_type_settings ->> 'contractual_principal_due' = 'on_or_before_maturity'
         AND coalesce(
                (source.loan_type_settings ->> 'principal_prepayment_allowed')::boolean,
                false
             ) = true
         AND coalesce(
                (source.loan_type_settings ->> 'principal_prepayment_changes_daily_interest')::boolean,
                true
             ) = false
         AND coalesce(rollup.installment_count, 0) > 0
         AND rollup.first_installment_number = 1
         AND rollup.last_installment_number = rollup.installment_count
         AND rollup.first_due_date = source.date_released + 1
         AND rollup.last_due_date = source.due_date
         AND rollup.last_due_date - source.date_released
             = rollup.installment_count::integer
         AND coalesce(rollup.line_mismatch_count, 0) = 0
         AND coalesce(rollup.contractual_schedule_total, 0)
             = round(
                    source.principal
                    + source.expected_daily_contractual_interest
                      * coalesce(rollup.installment_count, 0),
                    2
               )::numeric(18,2)
         AND coalesce(rollup.expected_principal_total_from_lines, 0)
             = source.principal
         AND coalesce(rollup.expected_interest_total_from_lines, 0)
             = round(
                    source.expected_daily_contractual_interest
                    * coalesce(rollup.installment_count, 0),
                    2
               )::numeric(18,2)
            THEN true
        ELSE false
    END AS contractual_cash_flow_validation_ready,
    true AS prepayment_option_requires_eir_estimate,
    'no_prepayment_through_maturity_base_schedule'::text AS validated_base_schedule_basis,
    false AS sppi_classification_concluded,
    false AS eir_policy_ready,
    false AS carrying_amount_ready,
    false AS journal_lines_enabled,
    false AS automatic_source_posting,
    'Priority #6 validates the exact verified signed 7x7 daily-payment schedule. Fixed contractual daily interest remains based on original principal; principal amortizes through the signed rows, contractual maturity is the signed last due date, and no pricing eligibility, borrower prepayment expectation, SPPI conclusion, EIR allocation, carrying amount, journal line, penalty, or automatic posting is inferred here.'::text AS validation_note
FROM source
LEFT JOIN schedule_rollup rollup
  ON rollup.loan_id = source.loan_id
 AND rollup.schedule_id = source.schedule_id;

COMMENT ON VIEW accounting.seven_by_seven_contractual_cash_flow_readiness IS
    'Priority #6 read-only evidence gate. Ready means the active verified signed 7x7 schedule itself reconciles principal, fixed-original-principal daily interest, agreed daily payment, exact signed maturity, and loan-level maturity. Product term_days remains only a default/prefill and is not an accounting schedule authority.';

CREATE OR REPLACE VIEW accounting.seven_by_seven_contractual_cash_flow_summary AS
SELECT
    count(*)::bigint AS seven_by_seven_loan_count,
    count(*) FILTER (
        WHERE readiness_status = 'pfrs9_contract_cash_flow_ready'
    )::bigint AS ready_count,
    count(*) FILTER (
        WHERE readiness_status <> 'pfrs9_contract_cash_flow_ready'
    )::bigint AS review_required_count,
    count(*) FILTER (
        WHERE readiness_status = 'verified_signed_contract_schedule_required'
    )::bigint AS verified_schedule_required_count,
    count(*) FILTER (
        WHERE readiness_status = 'contract_cash_flow_mismatch'
    )::bigint AS contract_cash_flow_mismatch_count,
    false AS sppi_classification_concluded,
    false AS eir_policy_ready,
    false AS carrying_amount_ready,
    false AS journal_lines_enabled,
    false AS automatic_source_posting
FROM accounting.seven_by_seven_contractual_cash_flow_readiness;

COMMENT ON VIEW accounting.seven_by_seven_contractual_cash_flow_summary IS
    'Priority #6 7x7 signed-schedule contractual cash-flow readiness counts only. No pricing approval, SPPI conclusion, EIR policy, carrying amount, journal, penalty, or automatic posting is enabled.';

COMMIT;
