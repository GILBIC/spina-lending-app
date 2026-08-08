BEGIN;

-- Stage 5D.1 fixes a presentation-level cent reconciliation issue discovered
-- during the 2026-08-08 cutover validation. The Stage 5D engine rounded the
-- loan component and accrued-interest component independently while gross
-- carrying amount was rounded from their unrounded sum. That can make the
-- displayed components differ from gross carrying amount by one or more cents
-- across a portfolio even though the underlying EIR calculation is correct.
--
-- Preserve the original Stage 5D calculation as an internal raw function, then
-- expose the same public function name with a deterministic cent allocation:
--   gross carrying amount = loan component + accrued-interest component
-- Accrued interest keeps the directly rounded accrual amount. The loan component
-- receives the rounding residual. EIR, cash timing, ECL, workbook values, and
-- journal-posting controls are unchanged.

DO $migration$
BEGIN
    IF to_regprocedure(
        'accounting.measure_loan_at_cutover_unreconciled(uuid,date)'
    ) IS NULL THEN
        EXECUTE 'ALTER FUNCTION accounting.measure_loan_at_cutover(uuid,date) '
             || 'RENAME TO measure_loan_at_cutover_unreconciled';
    END IF;
END
$migration$;

CREATE OR REPLACE FUNCTION accounting.measure_loan_at_cutover(
    p_loan_id UUID,
    p_cutover_date DATE
)
RETURNS TABLE (
    loan_id UUID,
    loan_number TEXT,
    client_name TEXT,
    calculation_mode TEXT,
    policy_version TEXT,
    date_released DATE,
    due_date DATE,
    cutover_date DATE,
    days_elapsed INTEGER,
    principal NUMERIC,
    operational_balance NUMERIC,
    daily_eir NUMERIC,
    daily_eir_percent NUMERIC,
    contractual_cash_due NUMERIC,
    actual_cash_received NUMERIC,
    effective_interest_income NUMERIC,
    loan_component NUMERIC,
    accrued_interest_component NUMERIC,
    gross_carrying_amount NUMERIC,
    contractual_unpaid_interest NUMERIC,
    measurement_status TEXT,
    measurement_note TEXT
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        raw.loan_id,
        raw.loan_number,
        raw.client_name,
        raw.calculation_mode,
        raw.policy_version,
        raw.date_released,
        raw.due_date,
        raw.cutover_date,
        raw.days_elapsed,
        raw.principal,
        raw.operational_balance,
        raw.daily_eir,
        raw.daily_eir_percent,
        raw.contractual_cash_due,
        raw.actual_cash_received,
        raw.effective_interest_income,
        CASE
            WHEN raw.measurement_status = 'measured'
             AND raw.gross_carrying_amount IS NOT NULL
             AND raw.accrued_interest_component IS NOT NULL
            THEN round(
                raw.gross_carrying_amount
                    - raw.accrued_interest_component,
                2
            )
            ELSE raw.loan_component
        END AS loan_component,
        raw.accrued_interest_component,
        raw.gross_carrying_amount,
        raw.contractual_unpaid_interest,
        raw.measurement_status,
        raw.measurement_note
    FROM accounting.measure_loan_at_cutover_unreconciled(
        p_loan_id,
        p_cutover_date
    ) AS raw;
$$;

-- Rebind the public cutover view to the reconciled public function. Existing
-- summary/reference views keep the same schema and therefore continue to work.
CREATE OR REPLACE VIEW accounting.loan_measurement_at_cutover AS
WITH latest_workbook AS (
    SELECT id, cutover_date
    FROM accounting.opening_balance_workbooks
    ORDER BY created_at DESC
    LIMIT 1
)
SELECT measurement.*
FROM latest_workbook workbook
JOIN accounting.loan_cutover_readiness readiness
  ON readiness.status = 'active'
CROSS JOIN LATERAL accounting.measure_loan_at_cutover(
    readiness.loan_id,
    workbook.cutover_date
) measurement
ORDER BY measurement.calculation_mode, measurement.loan_number;

-- Read-only audit surface for Stage 5D.1 validation. It does not change workbook
-- lines and does not create or post journals.
CREATE OR REPLACE VIEW accounting.loan_measurement_reconciliation AS
WITH measured AS (
    SELECT *
    FROM accounting.loan_measurement_at_cutover
    WHERE measurement_status = 'measured'
), summary AS (
    SELECT *
    FROM accounting.loan_measurement_summary
)
SELECT
    count(*)::bigint AS measured_loan_count,
    coalesce(
        sum(
            round(
                loan_component
                    + accrued_interest_component
                    - gross_carrying_amount,
                2
            )
        ),
        0
    )::numeric(18,2) AS loan_row_component_variance,
    coalesce(
        bool_and(
            abs(
                loan_component
                    + accrued_interest_component
                    - gross_carrying_amount
            ) < 0.005
        ),
        true
    ) AS all_measured_loans_reconciled,
    round(
        summary.regular_loan_component
            + summary.seven_by_seven_loan_component
            + summary.accrued_interest_component
            - summary.gross_carrying_amount,
        2
    )::numeric(18,2) AS summary_component_variance,
    abs(
        summary.regular_loan_component
            + summary.seven_by_seven_loan_component
            + summary.accrued_interest_component
            - summary.gross_carrying_amount
    ) < 0.005 AS summary_reconciled,
    false AS ready_to_post,
    false AS ecl_included
FROM measured
CROSS JOIN summary
GROUP BY
    summary.regular_loan_component,
    summary.seven_by_seven_loan_component,
    summary.accrued_interest_component,
    summary.gross_carrying_amount;

COMMENT ON FUNCTION accounting.measure_loan_at_cutover(UUID, DATE) IS
    'Stage 5D.1 reconciled cutover measurement. Gross carrying amount and directly rounded accrued interest are preserved; the loan component receives any cent rounding residual.';

COMMENT ON VIEW accounting.loan_measurement_reconciliation IS
    'Read-only Stage 5D.1 reconciliation audit. Zero variances are required before later opening-journal work; ECL and posting remain disabled.';

COMMIT;
