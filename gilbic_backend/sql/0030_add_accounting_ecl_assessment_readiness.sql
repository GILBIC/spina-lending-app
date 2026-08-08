BEGIN;

-- Stage 5E adds a read-only expected-credit-loss assessment layer for the
-- protected 2026 cutover workflow. It deliberately does not invent PD, LGD,
-- scenario weights, management overlays, or an ECL amount. Those inputs require
-- an approved, supportable impairment policy and calibration before 1190 may be
-- populated or any credit-loss journal may be created.
--
-- The DPD values below are mechanical contractual-arrears backstops only. They
-- are not automatic IFRS/PFRS 9 staging decisions. The 30-day SICR and 90-day
-- default thresholds are exposed as rebuttable backstop indicators so that a
-- later approved policy can combine them with qualitative and forward-looking
-- information.

CREATE OR REPLACE VIEW accounting.ecl_assessment_at_cutover AS
WITH base AS (
    SELECT
        measurement.*,
        CASE
            WHEN measurement.measurement_status = 'measured'
             AND coalesce(measurement.days_elapsed, 0) > 0
             AND coalesce(measurement.contractual_cash_due, 0) > 0
            THEN measurement.contractual_cash_due
                / measurement.days_elapsed
            ELSE NULL
        END AS contractual_daily_due
    FROM accounting.loan_measurement_at_cutover measurement
), arrears AS (
    SELECT
        base.*,
        greatest(
            coalesce(base.contractual_cash_due, 0)
                - coalesce(base.actual_cash_received, 0),
            0
        )::numeric(18,2) AS contractual_arrears_amount,
        CASE
            WHEN base.measurement_status <> 'measured' THEN NULL
            WHEN coalesce(base.contractual_cash_due, 0)
                 <= coalesce(base.actual_cash_received, 0) THEN 0
            WHEN base.contractual_daily_due IS NULL
              OR base.contractual_daily_due <= 0 THEN NULL
            ELSE greatest(
                (
                    base.cutover_date
                    - (
                        base.date_released
                        + least(
                            base.days_elapsed,
                            floor(
                                coalesce(base.actual_cash_received, 0)
                                / base.contractual_daily_due
                            )::integer + 1
                        )
                    )
                )::integer,
                0
            )
        END AS days_past_due_backstop
    FROM base
)
SELECT
    arrears.loan_id,
    arrears.loan_number,
    arrears.client_name,
    arrears.calculation_mode,
    arrears.cutover_date,
    arrears.date_released,
    arrears.due_date,
    arrears.gross_carrying_amount AS gross_exposure,
    arrears.contractual_cash_due,
    arrears.actual_cash_received,
    arrears.contractual_arrears_amount,
    arrears.days_past_due_backstop,
    CASE
        WHEN arrears.measurement_status <> 'measured'
            THEN 'measurement_review_required'
        WHEN arrears.days_past_due_backstop IS NULL
            THEN 'arrears_schedule_review_required'
        WHEN arrears.days_past_due_backstop >= 90
            THEN 'default_90dpd_backstop'
        WHEN arrears.days_past_due_backstop >= 30
            THEN 'sicr_30dpd_backstop'
        ELSE 'no_dpd_backstop_trigger'
    END AS credit_risk_backstop,
    CASE
        WHEN arrears.measurement_status <> 'measured'
            THEN 'measurement_review_required'
        WHEN arrears.days_past_due_backstop IS NULL
            THEN 'arrears_schedule_review_required'
        ELSE 'calibration_required'
    END AS ecl_assessment_status,
    NULL::integer AS ecl_stage,
    NULL::numeric(18,8) AS probability_of_default,
    NULL::numeric(18,8) AS loss_given_default,
    NULL::numeric(18,8) AS forward_looking_multiplier,
    NULL::numeric(18,2) AS ecl_amount,
    false AS ecl_included,
    'Stage 5E exposes contractual-arrears backstops only. Final SICR/default staging and ECL measurement require an approved policy using reasonable and supportable historical, current and forward-looking information; no PD, LGD, scenario weight or management overlay is assumed.'::text AS assessment_note
FROM arrears
ORDER BY arrears.calculation_mode, arrears.loan_number;

CREATE OR REPLACE VIEW accounting.ecl_assessment_summary AS
SELECT
    count(*)::bigint AS active_loan_count,
    count(*) FILTER (
        WHERE ecl_assessment_status = 'calibration_required'
    )::bigint AS backstop_assessed_count,
    count(*) FILTER (
        WHERE ecl_assessment_status <> 'calibration_required'
    )::bigint AS review_required_count,
    coalesce(sum(gross_exposure) FILTER (
        WHERE ecl_assessment_status = 'calibration_required'
    ), 0)::numeric(18,2) AS gross_exposure,
    coalesce(sum(contractual_arrears_amount) FILTER (
        WHERE ecl_assessment_status = 'calibration_required'
    ), 0)::numeric(18,2) AS contractual_arrears_amount,
    count(*) FILTER (
        WHERE days_past_due_backstop >= 30
    )::bigint AS sicr_30dpd_backstop_count,
    count(*) FILTER (
        WHERE days_past_due_backstop >= 90
    )::bigint AS default_90dpd_backstop_count,
    count(*) FILTER (
        WHERE coalesce(days_past_due_backstop, 0) < 30
          AND ecl_assessment_status = 'calibration_required'
    )::bigint AS below_30dpd_backstop_count,
    CASE
        WHEN count(*) FILTER (
            WHERE ecl_assessment_status <> 'calibration_required'
        ) > 0 THEN 'source_review_required'
        ELSE 'calibration_required'
    END AS ecl_measurement_status,
    'ecl_readiness_v1'::text AS assessment_policy_version,
    false AS historical_loss_calibration_configured,
    false AS forward_looking_scenarios_configured,
    NULL::numeric(18,2) AS ecl_amount,
    false AS ecl_included,
    false AS ready_to_post
FROM accounting.ecl_assessment_at_cutover;

-- Extend the Stage 5D workbook reference surface with account 1190. The amount
-- intentionally remains NULL until an approved ECL policy is calibrated and a
-- later stage computes a supportable loss allowance.
CREATE OR REPLACE VIEW accounting.opening_balance_measurement_reference AS
WITH measurement AS (
    SELECT * FROM accounting.loan_measurement_summary
), ecl AS (
    SELECT * FROM accounting.ecl_assessment_summary
)
SELECT
    '1100'::text AS account_code,
    CASE WHEN measurement.measurement_status = 'measured'
        THEN measurement.regular_loan_component ELSE NULL END AS measurement_reference_amount,
    measurement.measurement_status,
    'Regular accounting loan component after daily EIR accrual and actual cash allocation. This is a cutover measurement reference, not an automatic workbook entry.'::text AS measurement_note
FROM measurement
UNION ALL
SELECT
    '1110',
    CASE WHEN measurement.measurement_status = 'measured'
        THEN measurement.seven_by_seven_loan_component ELSE NULL END,
    measurement.measurement_status,
    '7x7 accounting loan component. Current base measurement is allowed only when no pre-cutover 7x7 cash flow requires principal/prepayment modification review.'
FROM measurement
UNION ALL
SELECT
    '1120',
    CASE WHEN measurement.measurement_status = 'measured'
        THEN measurement.accrued_interest_component ELSE NULL END,
    measurement.measurement_status,
    'Accrued effective-interest component across measured Regular and 7x7 loans. ECL remains separate and is not included.'
FROM measurement
UNION ALL
SELECT
    '1190',
    NULL::numeric,
    ecl.ecl_measurement_status,
    (
        'Stage 5E ECL readiness: '
        || ecl.backstop_assessed_count || '/' || ecl.active_loan_count
        || ' loans have mechanical arrears backstops; '
        || ecl.sicr_30dpd_backstop_count || ' are 30+ DPD and '
        || ecl.default_90dpd_backstop_count || ' are 90+ DPD. '
        || 'Gross measured exposure is PHP '
        || to_char(ecl.gross_exposure, 'FM999999999990.00')
        || '. ECL is intentionally not quantified until historical loss calibration, qualitative SICR/default policy and forward-looking scenarios are approved.'
    )::text
FROM ecl;

COMMENT ON VIEW accounting.ecl_assessment_at_cutover IS
    'Stage 5E read-only ECL readiness by measured loan. DPD fields are rebuttable contractual-arrears backstop indicators, not automatic staging decisions.';

COMMENT ON VIEW accounting.ecl_assessment_summary IS
    'Stage 5E portfolio ECL readiness. No PD, LGD, scenario weights, ECL amount or posting is enabled.';

COMMIT;
