BEGIN;

-- Stage 5D is a read-only accounting measurement layer. It derives effective-
-- interest measurements for the protected cutover workbook but does not write
-- workbook amounts, verify workbook lines, or create General Ledger journals.

CREATE OR REPLACE FUNCTION accounting.solve_level_payment_daily_eir(
    p_principal NUMERIC,
    p_daily_payment NUMERIC,
    p_term_days INTEGER
)
RETURNS NUMERIC
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    low_rate NUMERIC := 0;
    high_rate NUMERIC := 1;
    mid_rate NUMERIC;
    present_value NUMERIC;
    iteration INTEGER;
    day_number INTEGER;
BEGIN
    IF p_principal IS NULL OR p_principal <= 0
       OR p_daily_payment IS NULL OR p_daily_payment <= 0
       OR p_term_days IS NULL OR p_term_days <= 0
       OR p_daily_payment * p_term_days <= p_principal THEN
        RETURN NULL;
    END IF;

    FOR iteration IN 1..120 LOOP
        mid_rate := (low_rate + high_rate) / 2;
        present_value := 0;
        FOR day_number IN 1..p_term_days LOOP
            present_value := present_value
                + p_daily_payment / power(1 + mid_rate, day_number);
        END LOOP;
        IF present_value > p_principal THEN
            low_rate := mid_rate;
        ELSE
            high_rate := mid_rate;
        END IF;
    END LOOP;
    RETURN round((low_rate + high_rate) / 2, 12);
END;
$$;

CREATE OR REPLACE FUNCTION accounting.solve_daily_coupon_balloon_eir(
    p_principal NUMERIC,
    p_daily_coupon NUMERIC,
    p_term_days INTEGER
)
RETURNS NUMERIC
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    low_rate NUMERIC := 0;
    high_rate NUMERIC := 1;
    mid_rate NUMERIC;
    present_value NUMERIC;
    iteration INTEGER;
    day_number INTEGER;
BEGIN
    IF p_principal IS NULL OR p_principal <= 0
       OR p_daily_coupon IS NULL OR p_daily_coupon <= 0
       OR p_term_days IS NULL OR p_term_days <= 0 THEN
        RETURN NULL;
    END IF;

    FOR iteration IN 1..120 LOOP
        mid_rate := (low_rate + high_rate) / 2;
        present_value := 0;
        FOR day_number IN 1..p_term_days LOOP
            present_value := present_value
                + p_daily_coupon / power(1 + mid_rate, day_number);
        END LOOP;
        present_value := present_value
            + p_principal / power(1 + mid_rate, p_term_days);
        IF present_value > p_principal THEN
            low_rate := mid_rate;
        ELSE
            high_rate := mid_rate;
        END IF;
    END LOOP;
    RETURN round((low_rate + high_rate) / 2, 12);
END;
$$;

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
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    loan_row RECORD;
    elapsed_days INTEGER;
    effective_rate NUMERIC;
    loan_balance NUMERIC;
    accrued_balance NUMERIC := 0;
    interest_income NUMERIC := 0;
    daily_interest NUMERIC;
    cash_amount NUMERIC;
    cash_count BIGINT;
    day_number INTEGER;
    day_date DATE;
    contractual_due NUMERIC;
    contractual_unpaid NUMERIC;
    status_text TEXT := 'measured';
    note_text TEXT;
BEGIN
    SELECT
        l.id,
        l.loan_number,
        c.full_name,
        lt.calculation_mode,
        lt.term_days,
        lt.daily_interest_per_1000,
        lt.settings,
        l.principal,
        l.daily_amount,
        l.date_released,
        l.due_date,
        l.status,
        coalesce(s.remaining_balance, l.principal) AS operational_balance
    INTO loan_row
    FROM lending.loans l
    JOIN lending.clients c ON c.id = l.client_id
    JOIN lending.loan_types lt ON lt.id = l.loan_type_id
    LEFT JOIN lending.loan_collection_state s ON s.loan_id = l.id
    WHERE l.id = p_loan_id;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    loan_id := loan_row.id;
    loan_number := loan_row.loan_number;
    client_name := loan_row.full_name;
    calculation_mode := loan_row.calculation_mode;
    policy_version := coalesce(
        loan_row.settings ->> 'accounting_policy_version',
        'unversioned'
    );
    date_released := loan_row.date_released;
    due_date := loan_row.due_date;
    cutover_date := p_cutover_date;
    principal := loan_row.principal;
    operational_balance := loan_row.operational_balance;

    IF p_cutover_date IS NULL THEN
        measurement_status := 'cutover_date_required';
        measurement_note := 'Initialize the protected cutover workbook before accounting measurement.';
        RETURN NEXT;
        RETURN;
    END IF;
    IF p_cutover_date < loan_row.date_released THEN
        measurement_status := 'not_yet_released';
        measurement_note := 'Loan was not yet released at the selected cutover date.';
        RETURN NEXT;
        RETURN;
    END IF;
    IF p_cutover_date > loan_row.due_date THEN
        measurement_status := 'post_maturity_review_required';
        measurement_note := 'Active post-maturity loans require a separate delinquency and ECL review before cutover measurement.';
        RETURN NEXT;
        RETURN;
    END IF;

    elapsed_days := p_cutover_date - loan_row.date_released;
    days_elapsed := elapsed_days;

    IF loan_row.calculation_mode = 'fixed_daily' THEN
        effective_rate := accounting.solve_level_payment_daily_eir(
            loan_row.principal,
            loan_row.daily_amount,
            loan_row.term_days
        );
        contractual_due := round(
            loan_row.daily_amount * least(elapsed_days, loan_row.term_days),
            2
        );
        contractual_unpaid := NULL;
        note_text := 'Regular measurement uses the fixed contractual installment cash flows to solve the daily EIR. Actual non-voided cash is applied on its collection date; covered advance dates do not move the accounting cash date.';
    ELSIF loan_row.calculation_mode = 'seven_by_seven' THEN
        effective_rate := accounting.solve_daily_coupon_balloon_eir(
            loan_row.principal,
            round(ceil(loan_row.principal / 1000.0)
                * loan_row.daily_interest_per_1000, 2),
            loan_row.term_days
        );
        contractual_due := round(
            ceil(loan_row.principal / 1000.0)
                * loan_row.daily_interest_per_1000
                * least(elapsed_days, loan_row.term_days),
            2
        );

        SELECT count(*)
        INTO cash_count
        FROM lending.collection_transactions t
        WHERE t.loan_id = p_loan_id
          AND t.collection_date <= p_cutover_date
          AND t.is_voided = false
          AND t.entry_type <> 'pass'
          AND t.amount > 0;

        IF cash_count > 0 THEN
            measurement_status := '7x7_cash_flow_review_required';
            measurement_note := '7x7 has cash activity before cutover. Principal-versus-interest allocation and any prepayment modification must be reviewed before EIR carrying amounts are used.';
            daily_eir := effective_rate;
            daily_eir_percent := round(effective_rate * 100, 8);
            contractual_cash_due := contractual_due;
            SELECT coalesce(sum(t.amount), 0)
            INTO actual_cash_received
            FROM lending.collection_transactions t
            WHERE t.loan_id = p_loan_id
              AND t.collection_date <= p_cutover_date
              AND t.is_voided = false
              AND t.entry_type <> 'pass';
            RETURN NEXT;
            RETURN;
        END IF;
        contractual_unpaid := contractual_due;
        note_text := '7x7 base measurement solves EIR from daily contractual interest plus principal at maturity. The current loan has no pre-cutover 7x7 cash activity, so no principal-prepayment modification is assumed.';
    ELSE
        measurement_status := 'unsupported_calculation_mode';
        measurement_note := 'This loan calculation mode is not supported by the Stage 5D accounting measurement engine.';
        RETURN NEXT;
        RETURN;
    END IF;

    IF effective_rate IS NULL OR effective_rate <= 0 THEN
        measurement_status := 'eir_not_solved';
        measurement_note := 'The contractual cash-flow schedule does not produce a valid positive daily effective interest rate.';
        RETURN NEXT;
        RETURN;
    END IF;

    daily_eir := effective_rate;
    daily_eir_percent := round(effective_rate * 100, 8);
    contractual_cash_due := contractual_due;

    SELECT coalesce(sum(t.amount), 0)
    INTO actual_cash_received
    FROM lending.collection_transactions t
    WHERE t.loan_id = p_loan_id
      AND t.collection_date <= p_cutover_date
      AND t.is_voided = false
      AND t.entry_type <> 'pass';

    loan_balance := loan_row.principal;

    -- Same-day release cash has no elapsed interest period. Apply it first.
    SELECT coalesce(sum(t.amount), 0)
    INTO cash_amount
    FROM lending.collection_transactions t
    WHERE t.loan_id = p_loan_id
      AND t.collection_date = loan_row.date_released
      AND t.collection_date <= p_cutover_date
      AND t.is_voided = false
      AND t.entry_type <> 'pass';

    IF cash_amount > 0 THEN
        loan_balance := loan_balance - cash_amount;
    END IF;

    IF loan_balance < -0.01 THEN
        measurement_status := 'cash_exceeds_carrying_review_required';
        measurement_note := 'Cash recorded at release exceeds the initial accounting carrying amount and requires source review.';
        RETURN NEXT;
        RETURN;
    END IF;

    IF elapsed_days > 0 THEN
        FOR day_number IN 1..elapsed_days LOOP
            day_date := loan_row.date_released + day_number;
            daily_interest := (loan_balance + accrued_balance) * effective_rate;
            accrued_balance := accrued_balance + daily_interest;
            interest_income := interest_income + daily_interest;

            SELECT coalesce(sum(t.amount), 0)
            INTO cash_amount
            FROM lending.collection_transactions t
            WHERE t.loan_id = p_loan_id
              AND t.collection_date = day_date
              AND t.is_voided = false
              AND t.entry_type <> 'pass';

            IF cash_amount > 0 THEN
                IF cash_amount <= accrued_balance THEN
                    accrued_balance := accrued_balance - cash_amount;
                ELSE
                    cash_amount := cash_amount - accrued_balance;
                    accrued_balance := 0;
                    loan_balance := loan_balance - cash_amount;
                END IF;
            END IF;

            IF loan_balance < -0.01 THEN
                status_text := 'cash_exceeds_carrying_review_required';
                note_text := 'Recorded cash exceeds the measured accounting carrying amount and requires source review.';
                EXIT;
            END IF;
        END LOOP;
    END IF;

    loan_component := round(greatest(loan_balance, 0), 2);
    accrued_interest_component := round(greatest(accrued_balance, 0), 2);
    gross_carrying_amount := round(
        greatest(loan_balance, 0) + greatest(accrued_balance, 0),
        2
    );
    effective_interest_income := round(interest_income, 2);
    contractual_unpaid_interest := contractual_unpaid;
    measurement_status := status_text;
    measurement_note := note_text;
    RETURN NEXT;
END;
$$;

DROP VIEW IF EXISTS accounting.opening_balance_measurement_reference;
DROP VIEW IF EXISTS accounting.loan_measurement_summary;
DROP VIEW IF EXISTS accounting.loan_measurement_at_cutover;

CREATE VIEW accounting.loan_measurement_at_cutover AS
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

CREATE VIEW accounting.loan_measurement_summary AS
SELECT
    count(*) AS active_loan_count,
    count(*) FILTER (WHERE measurement_status = 'measured') AS measured_loan_count,
    count(*) FILTER (WHERE measurement_status <> 'measured') AS review_required_count,
    coalesce(sum(actual_cash_received) FILTER (
        WHERE measurement_status = 'measured'
    ), 0)::numeric(18,2) AS actual_cash_received,
    coalesce(sum(effective_interest_income) FILTER (
        WHERE measurement_status = 'measured'
    ), 0)::numeric(18,2) AS effective_interest_income,
    coalesce(sum(loan_component) FILTER (
        WHERE measurement_status = 'measured'
          AND calculation_mode = 'fixed_daily'
    ), 0)::numeric(18,2) AS regular_loan_component,
    coalesce(sum(loan_component) FILTER (
        WHERE measurement_status = 'measured'
          AND calculation_mode = 'seven_by_seven'
    ), 0)::numeric(18,2) AS seven_by_seven_loan_component,
    coalesce(sum(accrued_interest_component) FILTER (
        WHERE measurement_status = 'measured'
    ), 0)::numeric(18,2) AS accrued_interest_component,
    coalesce(sum(gross_carrying_amount) FILTER (
        WHERE measurement_status = 'measured'
    ), 0)::numeric(18,2) AS gross_carrying_amount,
    CASE
        WHEN count(*) = 0 THEN 'cutover_workbook_required'
        WHEN count(*) FILTER (WHERE measurement_status <> 'measured') > 0
            THEN 'review_required'
        ELSE 'measured'
    END AS measurement_status,
    'eir_cutover_v1'::text AS measurement_policy_version,
    false AS ecl_included,
    false AS ready_to_post
FROM accounting.loan_measurement_at_cutover;

CREATE VIEW accounting.opening_balance_measurement_reference AS
WITH summary AS (
    SELECT * FROM accounting.loan_measurement_summary
)
SELECT
    '1100'::text AS account_code,
    CASE WHEN measurement_status = 'measured'
        THEN regular_loan_component ELSE NULL END AS measurement_reference_amount,
    measurement_status,
    'Regular accounting loan component after daily EIR accrual and actual cash allocation. This is a cutover measurement reference, not an automatic workbook entry.'::text AS measurement_note
FROM summary
UNION ALL
SELECT
    '1110',
    CASE WHEN measurement_status = 'measured'
        THEN seven_by_seven_loan_component ELSE NULL END,
    measurement_status,
    '7x7 accounting loan component. Current base measurement is allowed only when no pre-cutover 7x7 cash flow requires principal/prepayment modification review.'
FROM summary
UNION ALL
SELECT
    '1120',
    CASE WHEN measurement_status = 'measured'
        THEN accrued_interest_component ELSE NULL END,
    measurement_status,
    'Accrued effective-interest component across measured Regular and 7x7 loans. ECL remains separate and is not included.'
FROM summary;

-- Add dynamic Stage 5D measurement references beside the immutable Stage 5C
-- source snapshot. No proposed debit/credit is populated automatically.
CREATE OR REPLACE VIEW accounting.opening_balance_cutover_worksheet AS
WITH latest_workbook AS (
    SELECT *
    FROM accounting.opening_balance_workbooks
    ORDER BY created_at DESC
    LIMIT 1
), workbook_rows AS (
    SELECT
        workbook.id AS workbook_id,
        account.code AS account_code,
        account.system_key,
        account.name AS account_name,
        account.account_type,
        account.normal_balance,
        line.source_reference_amount,
        line.source_basis,
        line.requirement_type AS readiness_status,
        line.guidance,
        line.proposed_debit,
        line.proposed_credit,
        line.verification_status,
        line.evidence_note
    FROM latest_workbook workbook
    JOIN accounting.opening_balance_workbook_lines line
      ON line.workbook_id = workbook.id
    JOIN accounting.accounts account ON account.id = line.account_id
), source_rows AS (
    SELECT
        NULL::uuid AS workbook_id,
        source.account_code,
        source.system_key,
        source.account_name,
        source.account_type,
        source.normal_balance,
        source.source_reference_amount,
        source.source_basis,
        source.requirement_type AS readiness_status,
        source.guidance,
        NULL::numeric AS proposed_debit,
        NULL::numeric AS proposed_credit,
        'pending'::text AS verification_status,
        NULL::text AS evidence_note
    FROM accounting.opening_balance_cutover_source_reference source
    WHERE NOT EXISTS (SELECT 1 FROM latest_workbook)
), rows AS (
    SELECT * FROM workbook_rows
    UNION ALL
    SELECT * FROM source_rows
)
SELECT
    rows.*,
    measurement.measurement_reference_amount,
    measurement.measurement_status,
    measurement.measurement_note
FROM rows
LEFT JOIN accounting.opening_balance_measurement_reference measurement
  ON measurement.account_code = rows.account_code
ORDER BY rows.account_code;

-- Recreate summary because its dependency is the worksheet view above.
CREATE OR REPLACE VIEW accounting.opening_balance_cutover_summary AS
WITH latest_workbook AS (
    SELECT *
    FROM accounting.opening_balance_workbooks
    ORDER BY created_at DESC
    LIMIT 1
), line_summary AS (
    SELECT
        count(*) AS line_count,
        count(*) FILTER (WHERE source_reference_amount IS NOT NULL)
            AS source_reference_count,
        count(*) FILTER (WHERE readiness_status = 'manual_required')
            AS manual_required_count,
        count(*) FILTER (WHERE readiness_status = 'reconciliation_required')
            AS reconciliation_required_count,
        count(*) FILTER (WHERE readiness_status = 'calculation_required')
            AS calculation_required_count,
        count(*) FILTER (WHERE readiness_status = 'assessment_required')
            AS assessment_required_count,
        count(*) FILTER (
            WHERE verification_status = 'verified'
              AND (proposed_debit IS NOT NULL OR proposed_credit IS NOT NULL)
        ) AS verified_line_count,
        count(*) FILTER (
            WHERE verification_status <> 'verified'
               OR (proposed_debit IS NULL AND proposed_credit IS NULL)
        ) AS pending_line_count,
        coalesce(sum(coalesce(proposed_debit, 0)), 0)::numeric(18,2)
            AS total_debit,
        coalesce(sum(coalesce(proposed_credit, 0)), 0)::numeric(18,2)
            AS total_credit
    FROM accounting.opening_balance_cutover_worksheet
), blocker_summary AS (
    SELECT count(*) FILTER (
        WHERE status = 'active' AND readiness_status = 'blocked'
    ) AS blocked_count
    FROM accounting.loan_cutover_readiness
)
SELECT
    workbook.id AS workbook_id,
    workbook.cutover_date,
    coalesce(workbook.status, 'source_review_required')::text AS worksheet_status,
    line.line_count AS worksheet_line_count,
    line.source_reference_count,
    line.manual_required_count,
    line.reconciliation_required_count,
    line.calculation_required_count,
    line.assessment_required_count,
    coalesce(NOT workbook.profit_loss_policy_confirmed, true)
        AS profit_loss_migration_policy_required,
    coalesce(workbook.profit_loss_policy_confirmed, false)
        AS profit_loss_policy_confirmed,
    workbook.profit_loss_policy_note,
    line.verified_line_count,
    line.pending_line_count,
    line.total_debit,
    line.total_credit,
    abs(line.total_debit - line.total_credit)::numeric(18,2) AS balance_variance,
    (
        line.total_debit > 0
        AND abs(line.total_debit - line.total_credit) <= 0.01
    ) AS worksheet_balanced,
    (
        workbook.id IS NOT NULL
        AND workbook.status = 'draft'
        AND line.pending_line_count = 0
        AND line.total_debit > 0
        AND abs(line.total_debit - line.total_credit) <= 0.01
        AND workbook.profit_loss_policy_confirmed = true
        AND blocker.blocked_count = 0
    ) AS ready_for_review,
    false AS ready_to_post,
    false AS opening_balance_posting_enabled,
    false AS automatic_source_posting_enabled
FROM line_summary line
CROSS JOIN blocker_summary blocker
LEFT JOIN latest_workbook workbook ON true;

COMMIT;