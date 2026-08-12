BEGIN;

-- Master Issue #296: prove that 7x7 / EMER accounting EIR and carrying
-- measurement are separate from the operational PHP 7-per-PHP 1,000 rule.
--
-- Migration 0060 proves only the exact verified contractual base cash-flow
-- schedule. This migration adds a read-only mathematical EIR preview from that
-- immutable signed-contract schedule, while deliberately refusing to turn the
-- operational coupon rule into an authoritative accounting EIR or carrying
-- amount. IFRS 9 classification, business-model assessment, and expected cash-
-- flow / prepayment policy remain explicit review gates.
--
-- No lending history, journal entry, journal line, accounting decision, or
-- automatic posting is created by this migration.

CREATE OR REPLACE FUNCTION accounting.solve_verified_schedule_daily_eir_preview(
    p_schedule_id UUID,
    p_initial_carrying_amount NUMERIC
)
RETURNS NUMERIC
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    schedule_row RECORD;
    installment_row RECORD;
    low_rate NUMERIC := 0;
    high_rate NUMERIC := 1;
    mid_rate NUMERIC;
    present_value NUMERIC;
    total_cash NUMERIC := 0;
    installment_count INTEGER := 0;
    iteration INTEGER;
    day_offset INTEGER;
BEGIN
    IF p_schedule_id IS NULL
       OR p_initial_carrying_amount IS NULL
       OR p_initial_carrying_amount <= 0 THEN
        RETURN NULL;
    END IF;

    SELECT
        schedule.id,
        schedule.effective_from,
        schedule.status,
        schedule.payment_frequency,
        registration.evidence_basis,
        registration.verified_at
    INTO schedule_row
    FROM lending.loan_contract_schedules schedule
    JOIN lending.loan_contract_schedule_registrations registration
      ON registration.schedule_id = schedule.id
    WHERE schedule.id = p_schedule_id;

    IF NOT FOUND
       OR schedule_row.status IS DISTINCT FROM 'active'
       OR schedule_row.payment_frequency IS DISTINCT FROM 'daily'
       OR schedule_row.evidence_basis IS DISTINCT FROM 'signed_contract'
       OR schedule_row.verified_at IS NULL THEN
        RETURN NULL;
    END IF;

    SELECT
        count(*)::integer,
        coalesce(sum(contractual_amount), 0)::numeric
    INTO installment_count, total_cash
    FROM lending.loan_contract_installments
    WHERE schedule_id = p_schedule_id
      AND due_date > schedule_row.effective_from
      AND contractual_amount > 0;

    IF installment_count <= 0 OR total_cash <= p_initial_carrying_amount THEN
        RETURN NULL;
    END IF;

    FOR iteration IN 1..160 LOOP
        mid_rate := (low_rate + high_rate) / 2;
        present_value := 0;

        FOR installment_row IN
            SELECT due_date, contractual_amount
            FROM lending.loan_contract_installments
            WHERE schedule_id = p_schedule_id
              AND due_date > schedule_row.effective_from
              AND contractual_amount > 0
            ORDER BY due_date, installment_number
        LOOP
            day_offset := installment_row.due_date - schedule_row.effective_from;
            IF day_offset <= 0 THEN
                RETURN NULL;
            END IF;
            present_value := present_value
                + installment_row.contractual_amount
                  / power(1 + mid_rate, day_offset);
        END LOOP;

        IF present_value > p_initial_carrying_amount THEN
            low_rate := mid_rate;
        ELSE
            high_rate := mid_rate;
        END IF;
    END LOOP;

    RETURN round((low_rate + high_rate) / 2, 12);
END;
$$;

COMMENT ON FUNCTION accounting.solve_verified_schedule_daily_eir_preview(UUID, NUMERIC) IS
    'Read-only mathematical daily EIR preview from an active immutable verified signed-contract schedule. It is not an authoritative IFRS 9 EIR until classification and expected-cash-flow/prepayment policy gates are approved.';

CREATE OR REPLACE VIEW accounting.seven_by_seven_eir_carrying_policy_readiness AS
SELECT
    readiness.loan_id,
    readiness.loan_number,
    readiness.loan_status,
    readiness.loan_type_code,
    readiness.loan_type_name,
    readiness.principal,
    readiness.date_released,
    readiness.due_date,
    readiness.term_days,
    readiness.schedule_id,
    readiness.schedule_version,
    readiness.contract_reference,
    readiness.evidence_reference,
    readiness.expected_daily_contractual_interest
        AS operational_daily_contractual_interest,
    round(
        readiness.expected_daily_contractual_interest / nullif(readiness.principal, 0),
        12
    ) AS operational_daily_rate_on_original_principal,
    CASE
        WHEN readiness.contractual_cash_flow_validation_ready THEN
            accounting.solve_verified_schedule_daily_eir_preview(
                readiness.schedule_id,
                readiness.principal
            )
        ELSE NULL
    END AS base_no_prepayment_daily_eir_preview,
    CASE
        WHEN readiness.contractual_cash_flow_validation_ready THEN
            round(
                accounting.solve_verified_schedule_daily_eir_preview(
                    readiness.schedule_id,
                    readiness.principal
                ) * 100,
                8
            )
        ELSE NULL
    END AS base_no_prepayment_daily_eir_percent,
    CASE
        WHEN readiness.contractual_cash_flow_validation_ready
         AND accounting.solve_verified_schedule_daily_eir_preview(
                readiness.schedule_id,
                readiness.principal
             ) IS NOT NULL THEN
            abs(
                accounting.solve_verified_schedule_daily_eir_preview(
                    readiness.schedule_id,
                    readiness.principal
                )
                - readiness.expected_daily_contractual_interest
                  / nullif(readiness.principal, 0)
            ) <= 0.000000000001
        ELSE NULL
    END AS operational_rate_matches_base_math_preview,
    readiness.principal_prepayment_allowed,
    readiness.principal_prepayment_changes_daily_interest,
    readiness.validated_base_schedule_basis,
    true AS business_model_assessment_required,
    true AS sppi_assessment_required,
    true AS prepayment_expected_cash_flow_policy_required,
    true AS expected_life_assessment_required,
    NULL::numeric(24,12) AS authoritative_daily_eir,
    NULL::numeric(18,2) AS authoritative_initial_gross_carrying_amount,
    NULL::numeric(18,2) AS authoritative_current_gross_carrying_amount,
    CASE
        WHEN readiness.contractual_cash_flow_validation_ready = false
            THEN 'contractual_cash_flow_readiness_required'
        WHEN accounting.solve_verified_schedule_daily_eir_preview(
                readiness.schedule_id,
                readiness.principal
             ) IS NULL
            THEN 'base_eir_preview_not_solved'
        WHEN readiness.principal_prepayment_allowed
         AND readiness.principal_prepayment_changes_daily_interest = false
            THEN 'sppi_and_prepayment_policy_review_required'
        ELSE 'accounting_classification_and_expected_cash_flow_policy_required'
    END AS policy_readiness_status,
    false AS sppi_classification_concluded,
    false AS business_model_classification_concluded,
    false AS expected_cash_flow_policy_approved,
    false AS eir_policy_ready,
    false AS carrying_amount_ready,
    false AS journal_lines_enabled,
    false AS automatic_source_posting,
    CASE
        WHEN readiness.contractual_cash_flow_validation_ready = false THEN
            'The verified 7x7 signed-contract cash-flow gate must pass before any EIR preview is considered.'
        WHEN readiness.principal_prepayment_allowed
         AND readiness.principal_prepayment_changes_daily_interest = false THEN
            'The no-prepayment base schedule can be solved mathematically, but that preview is not the operational PHP 7-per-PHP 1,000 rule promoted into accounting. The contract permits principal prepayment while contractual daily interest remains based on original principal after partial principal reduction, so SPPI classification and the expected prepayment/expected-life cash-flow policy require explicit supported review before an authoritative EIR or amortised-cost carrying amount may exist.'
        ELSE
            'The verified base schedule can be solved mathematically, but authoritative IFRS 9 EIR and carrying measurement remain blocked until business-model, SPPI, expected-life, and expected-cash-flow policy evidence is approved.'
    END AS policy_note
FROM accounting.seven_by_seven_contractual_cash_flow_readiness readiness;

COMMENT ON VIEW accounting.seven_by_seven_eir_carrying_policy_readiness IS
    'Read-only Master Issue #296 separation gate. A verified 7x7 contractual base schedule may produce a mathematical no-prepayment EIR preview, but authoritative EIR/carrying amounts remain NULL pending supported IFRS 9 business-model, SPPI and expected-cash-flow/prepayment policy conclusions.';

CREATE OR REPLACE VIEW accounting.seven_by_seven_eir_carrying_policy_summary AS
SELECT
    count(*)::bigint AS seven_by_seven_loan_count,
    count(*) FILTER (
        WHERE policy_readiness_status = 'contractual_cash_flow_readiness_required'
    )::bigint AS contractual_cash_flow_readiness_required_count,
    count(*) FILTER (
        WHERE base_no_prepayment_daily_eir_preview IS NOT NULL
    )::bigint AS base_eir_preview_solved_count,
    count(*) FILTER (
        WHERE policy_readiness_status = 'sppi_and_prepayment_policy_review_required'
    )::bigint AS sppi_and_prepayment_review_required_count,
    count(*) FILTER (
        WHERE policy_readiness_status = 'accounting_classification_and_expected_cash_flow_policy_required'
    )::bigint AS other_policy_review_required_count,
    false AS sppi_classification_concluded,
    false AS business_model_classification_concluded,
    false AS expected_cash_flow_policy_approved,
    false AS eir_policy_ready,
    false AS carrying_amount_ready,
    false AS journal_lines_enabled,
    false AS automatic_source_posting
FROM accounting.seven_by_seven_eir_carrying_policy_readiness;

COMMENT ON VIEW accounting.seven_by_seven_eir_carrying_policy_summary IS
    'Counts only 7x7 EIR/carrying policy-readiness states. No authoritative EIR, amortised-cost carrying amount, journal line, or automatic posting is enabled.';

COMMIT;
