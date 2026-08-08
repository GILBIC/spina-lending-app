BEGIN;

-- Stage 5E.1 inventories historical outcome evidence before any ECL calibration.
-- It deliberately does not invent a minimum sample size, PD, LGD, cure rate,
-- recovery rate, scenario weight, macroeconomic overlay, or ECL amount.

CREATE OR REPLACE VIEW accounting.ecl_calibration_source_inventory AS
WITH loan_stats AS (
    SELECT
        count(*)::bigint AS total_loan_count,
        count(*) FILTER (WHERE status = 'active')::bigint AS active_loan_count,
        count(*) FILTER (WHERE status IN ('paid', 'closed'))::bigint
            AS resolved_loan_count,
        count(*) FILTER (WHERE status = 'defaulted')::bigint
            AS defaulted_loan_count,
        min(date_released) AS earliest_release_date,
        max(date_released) AS latest_release_date
    FROM lending.loans
), collection_stats AS (
    SELECT
        count(*) FILTER (
            WHERE is_voided = false
              AND entry_type <> 'pass'
        )::bigint AS valid_cash_collection_count,
        min(collection_date) FILTER (
            WHERE is_voided = false
              AND entry_type <> 'pass'
        ) AS earliest_collection_date,
        max(collection_date) FILTER (
            WHERE is_voided = false
              AND entry_type <> 'pass'
        ) AS latest_collection_date
    FROM lending.collection_transactions
)
SELECT
    loan_stats.total_loan_count,
    loan_stats.active_loan_count,
    loan_stats.resolved_loan_count,
    loan_stats.defaulted_loan_count,
    loan_stats.earliest_release_date,
    loan_stats.latest_release_date,
    collection_stats.valid_cash_collection_count,
    collection_stats.earliest_collection_date,
    collection_stats.latest_collection_date,
    (loan_stats.resolved_loan_count + loan_stats.defaulted_loan_count > 0)
        AS mature_outcome_history_present,
    (loan_stats.defaulted_loan_count > 0)
        AS default_loss_history_present,
    false AS dedicated_recovery_writeoff_source_present,
    false AS historical_loss_calibration_configured,
    false AS forward_looking_scenarios_configured,
    CASE
        WHEN loan_stats.resolved_loan_count + loan_stats.defaulted_loan_count = 0
            THEN 'historical_data_required'
        WHEN loan_stats.defaulted_loan_count = 0
            THEN 'default_outcome_data_required'
        ELSE 'recovery_writeoff_source_required'
    END AS calibration_readiness_status,
    array_remove(ARRAY[
        CASE
            WHEN loan_stats.resolved_loan_count + loan_stats.defaulted_loan_count = 0
                THEN 'No mature resolved/defaulted loan outcomes are available for historical loss calibration.'
        END,
        CASE
            WHEN loan_stats.defaulted_loan_count = 0
                THEN 'No defaulted loan outcomes are available to evidence default frequency or loss severity.'
        END,
        CASE
            WHEN collection_stats.valid_cash_collection_count = 0
                THEN 'No valid non-voided cash collection history is available.'
        END,
        'No dedicated recovery/write-off event source is available yet; recovery timing and realized loss severity cannot be calibrated from the current schema.'::text,
        'Forward-looking economic scenarios or another supportable forward-looking methodology have not been configured.'::text
    ], NULL) AS blockers,
    false AS calibration_source_ready,
    false AS ecl_included,
    NULL::numeric(18,2) AS ecl_amount,
    false AS ready_to_post,
    'ecl_calibration_sources_v1'::text AS inventory_version
FROM loan_stats
CROSS JOIN collection_stats;

CREATE OR REPLACE VIEW accounting.ecl_calibration_readiness_summary AS
SELECT
    ecl.active_loan_count,
    ecl.gross_exposure,
    ecl.contractual_arrears_amount,
    ecl.sicr_30dpd_backstop_count,
    ecl.default_90dpd_backstop_count,
    inventory.total_loan_count AS historical_total_loan_count,
    inventory.resolved_loan_count,
    inventory.defaulted_loan_count,
    inventory.valid_cash_collection_count,
    inventory.earliest_release_date,
    inventory.latest_release_date,
    inventory.earliest_collection_date,
    inventory.latest_collection_date,
    inventory.mature_outcome_history_present,
    inventory.default_loss_history_present,
    inventory.dedicated_recovery_writeoff_source_present,
    inventory.calibration_readiness_status,
    inventory.blockers,
    inventory.inventory_version,
    false AS historical_loss_calibration_configured,
    false AS forward_looking_scenarios_configured,
    NULL::numeric(18,2) AS ecl_amount,
    false AS ecl_included,
    false AS ready_to_post
FROM accounting.ecl_assessment_summary ecl
CROSS JOIN accounting.ecl_calibration_source_inventory inventory;

-- Keep account 1190 unquantified, but replace the generic Stage 5E status with
-- the more specific Stage 5E.1 historical-calibration source result.
CREATE OR REPLACE VIEW accounting.opening_balance_measurement_reference AS
WITH measurement AS (
    SELECT * FROM accounting.loan_measurement_summary
), ecl AS (
    SELECT * FROM accounting.ecl_assessment_summary
), calibration AS (
    SELECT * FROM accounting.ecl_calibration_source_inventory
)
SELECT
    '1100'::text AS account_code,
    CASE WHEN measurement.measurement_status = 'measured'
        THEN measurement.regular_loan_component ELSE NULL END
        AS measurement_reference_amount,
    measurement.measurement_status,
    'Regular accounting loan component after daily EIR accrual and actual cash allocation. This is a cutover measurement reference, not an automatic workbook entry.'::text
        AS measurement_note
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
    calibration.calibration_readiness_status,
    (
        'Stage 5E.1 ECL calibration readiness: current database has '
        || calibration.total_loan_count || ' total loans, '
        || calibration.active_loan_count || ' active, '
        || calibration.resolved_loan_count || ' resolved (paid/closed), and '
        || calibration.defaulted_loan_count || ' defaulted. Valid non-voided cash collection observations: '
        || calibration.valid_cash_collection_count || ', from '
        || coalesce(to_char(calibration.earliest_collection_date, 'YYYY-MM-DD'), 'none')
        || ' through '
        || coalesce(to_char(calibration.latest_collection_date, 'YYYY-MM-DD'), 'none')
        || '. Gross measured exposure remains PHP '
        || to_char(ecl.gross_exposure, 'FM999999999990.00')
        || '. No PD, LGD, recovery rate, forward-looking adjustment or ECL amount is inferred. Historical outcome/recovery data and an approved impairment methodology are required before account 1190 can be quantified.'
    )::text
FROM ecl
CROSS JOIN calibration;

COMMENT ON VIEW accounting.ecl_calibration_source_inventory IS
    'Stage 5E.1 inventory of historical outcome, collection, default and recovery/write-off evidence needed before ECL calibration. No loss rate or ECL amount is calculated.';

COMMENT ON VIEW accounting.ecl_calibration_readiness_summary IS
    'Stage 5E.1 combined ECL/calibration readiness. Posting and ECL quantification remain disabled.';

COMMIT;
