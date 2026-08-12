BEGIN;

-- Master Issue #296: validate the contractual principal-repayment/maturity
-- cash-flow shape for greenfield 7x7 / EMER loans before any PFRS 9 EIR,
-- carrying-amount, journal, or mobile-write path is enabled.
--
-- This migration is deliberately read-only. The signed borrower contract and
-- its immutable verified schedule remain the source of contractual cash flows.
-- SPINA does not infer a production schedule from the generic 120-day product
-- convention, does not conclude SPPI/amortised-cost classification, does not
-- select a prepayment expectation for EIR, and does not post accounting.

CREATE OR REPLACE VIEW accounting.seven_by_seven_contractual_cash_flow_lines AS
WITH contract_source AS (
    SELECT
        loan.id AS loan_id,
        loan.loan_number,
        loan.principal,
        loan.daily_amount,
        loan.date_released,
        loan.due_date,
        loan_type.term_days,
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
)
SELECT
    source.loan_id,
    source.loan_number,
    source.schedule_id,
    source.schedule_version,
    installment.id AS installment_id,
    installment.installment_number,
    installment.due_date,
    installment.contractual_amount,
    installment.principal_component,
    installment.interest_component,
    source.date_released + installment.installment_number AS expected_due_date,
    CASE
        WHEN installment.installment_number = source.term_days
            THEN round(
                source.expected_daily_contractual_interest + source.principal,
                2
            )::numeric(18,2)
        ELSE source.expected_daily_contractual_interest
    END AS expected_contractual_amount,
    CASE
        WHEN installment.installment_number = source.term_days
            THEN source.principal
        ELSE 0::numeric
    END::numeric(18,2) AS expected_principal_component,
    source.expected_daily_contractual_interest AS expected_interest_component,
    CASE
        WHEN installment.installment_number < 1
          OR installment.installment_number > source.term_days
            THEN 'installment_number_out_of_contract_term'
        WHEN installment.due_date
             <> source.date_released + installment.installment_number
            THEN 'contractual_due_date_mismatch'
        WHEN installment.contractual_amount <> CASE
            WHEN installment.installment_number = source.term_days
                THEN round(
                    source.expected_daily_contractual_interest + source.principal,
                    2
                )::numeric(18,2)
            ELSE source.expected_daily_contractual_interest
        END
            THEN 'contractual_amount_mismatch'
        WHEN installment.principal_component IS NOT NULL
         AND installment.principal_component <> CASE
            WHEN installment.installment_number = source.term_days
                THEN source.principal
            ELSE 0::numeric
         END
            THEN 'principal_component_mismatch'
        WHEN installment.interest_component IS NOT NULL
         AND installment.interest_component
             <> source.expected_daily_contractual_interest
            THEN 'interest_component_mismatch'
        ELSE 'line_ready'
    END AS line_status
FROM contract_source source
JOIN lending.loan_contract_installments installment
  ON installment.schedule_id = source.schedule_id;

COMMENT ON VIEW accounting.seven_by_seven_contractual_cash_flow_lines IS
    'Read-only line-by-line validation of the verified greenfield 7x7 base contractual schedule: daily fixed contractual interest from original principal and full principal due at maturity. Optional prepayment remains a separate EIR-estimation policy question.';

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
        loan_type.term_days,
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
        coalesce(sum(line.expected_interest_component), 0)::numeric(18,2)
            AS expected_interest_total_from_lines,
        coalesce(sum(line.expected_principal_component), 0)::numeric(18,2)
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
    source.term_days,
    source.daily_interest_per_1000,
    source.expected_daily_contractual_interest,
    round(
        source.expected_daily_contractual_interest * source.term_days,
        2
    )::numeric(18,2) AS expected_contractual_interest_total,
    round(
        source.principal
        + source.expected_daily_contractual_interest * source.term_days,
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
        WHEN source.due_date <> source.date_released + source.term_days
            THEN 'loan_term_review_required'
        WHEN source.daily_interest_per_1000 <= 0
          OR source.daily_amount <> source.expected_daily_contractual_interest
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
        WHEN coalesce(rollup.installment_count, 0) <> source.term_days
          OR rollup.first_installment_number <> 1
          OR rollup.last_installment_number <> source.term_days
          OR rollup.first_due_date <> source.date_released + 1
          OR rollup.last_due_date <> source.due_date
          OR coalesce(rollup.line_mismatch_count, 0) <> 0
          OR coalesce(rollup.contractual_schedule_total, 0)
             <> round(
                    source.principal
                    + source.expected_daily_contractual_interest * source.term_days,
                    2
                )::numeric(18,2)
          OR coalesce(rollup.expected_principal_total_from_lines, 0)
             <> source.principal
          OR coalesce(rollup.expected_interest_total_from_lines, 0)
             <> round(
                    source.expected_daily_contractual_interest * source.term_days,
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
         AND source.due_date = source.date_released + source.term_days
         AND source.daily_interest_per_1000 > 0
         AND source.daily_amount = source.expected_daily_contractual_interest
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
         AND coalesce(rollup.installment_count, 0) = source.term_days
         AND rollup.first_installment_number = 1
         AND rollup.last_installment_number = source.term_days
         AND rollup.first_due_date = source.date_released + 1
         AND rollup.last_due_date = source.due_date
         AND coalesce(rollup.line_mismatch_count, 0) = 0
         AND coalesce(rollup.contractual_schedule_total, 0)
             = round(
                    source.principal
                    + source.expected_daily_contractual_interest * source.term_days,
                    2
               )::numeric(18,2)
         AND coalesce(rollup.expected_principal_total_from_lines, 0)
             = source.principal
         AND coalesce(rollup.expected_interest_total_from_lines, 0)
             = round(
                    source.expected_daily_contractual_interest * source.term_days,
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
    'This validates only the exact verified greenfield 7x7 contractual base cash-flow shape: fixed daily contractual interest from original principal and full principal due at maturity. The contractual prepayment option is preserved but no borrower prepayment expectation, SPPI conclusion, EIR allocation, carrying amount, journal line, or automatic posting is inferred here.'::text AS validation_note
FROM source
LEFT JOIN schedule_rollup rollup
  ON rollup.loan_id = source.loan_id
 AND rollup.schedule_id = source.schedule_id;

COMMENT ON VIEW accounting.seven_by_seven_contractual_cash_flow_readiness IS
    'Read-only evidence gate for Master Issue #296 7x7 contractual cash-flow validation. Ready means an immutable verified signed-contract schedule exactly supports the greenfield daily-interest / principal-at-maturity base cash-flow shape; it is not an SPPI, EIR, carrying-amount, or posting conclusion.';

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
    '7x7 contractual cash-flow readiness counts only. No SPPI conclusion, EIR policy, carrying amount, journal, or automatic posting is enabled.';

COMMIT;
