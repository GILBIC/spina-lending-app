BEGIN;

CREATE TABLE IF NOT EXISTS accounting.loan_contract_metadata_audit (
    id BIGSERIAL PRIMARY KEY,
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    loan_number TEXT NOT NULL,
    field_name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    reason TEXT NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (btrim(loan_number) <> ''),
    CHECK (btrim(field_name) <> ''),
    CHECK (btrim(reason) <> '')
);

CREATE OR REPLACE FUNCTION accounting.guard_loan_contract_metadata_audit()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Accounting loan-contract metadata audit records are immutable.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_loan_contract_metadata_audit_guard
    ON accounting.loan_contract_metadata_audit;
CREATE TRIGGER accounting_loan_contract_metadata_audit_guard
BEFORE UPDATE OR DELETE ON accounting.loan_contract_metadata_audit
FOR EACH ROW EXECUTE FUNCTION accounting.guard_loan_contract_metadata_audit();

-- Regular is contractually a fixed 20% interest product over the configured term.
-- Store the rule on the loan type so accounting does not depend on a nullable
-- per-loan field for future schedule derivation.
UPDATE lending.loan_types
SET settings = coalesce(settings, '{}'::jsonb) || jsonb_build_object(
        'contract_interest_rate_percent', 20.0,
        'accounting_interest_model', 'effective_interest',
        'accounting_policy_version', 'regular_fixed_20_v1'
    ),
    updated_at = now()
WHERE calculation_mode = 'fixed_daily'
  AND lower(name) = 'regular';

-- Preserve a permanent audit before normalizing legacy/test Regular rows whose
-- contract rate was left null even though the product rule is fixed at 20%.
INSERT INTO accounting.loan_contract_metadata_audit (
    loan_id,
    loan_number,
    field_name,
    old_value,
    new_value,
    reason
)
SELECT
    loan.id,
    loan.loan_number,
    'interest_rate',
    null,
    '20.0000',
    'Normalized missing Regular contract interest rate to the fixed 20% product rule before accounting cutover.'
FROM lending.loans loan
JOIN lending.loan_types loan_type ON loan_type.id = loan.loan_type_id
WHERE loan_type.calculation_mode = 'fixed_daily'
  AND lower(loan_type.name) = 'regular'
  AND loan.interest_rate IS NULL
  AND NOT EXISTS (
      SELECT 1
      FROM accounting.loan_contract_metadata_audit audit
      WHERE audit.loan_id = loan.id
        AND audit.field_name = 'interest_rate'
        AND audit.new_value = '20.0000'
  );

UPDATE lending.loans loan
SET interest_rate = 20.0000,
    updated_at = now()
FROM lending.loan_types loan_type
WHERE loan_type.id = loan.loan_type_id
  AND loan_type.calculation_mode = 'fixed_daily'
  AND lower(loan_type.name) = 'regular'
  AND loan.interest_rate IS NULL;

-- Persist the agreed 7x7 operational contract metadata without enabling mobile
-- 7x7 collection or claiming that the PFRS EIR schedule has already been proven.
UPDATE lending.loan_types
SET settings = coalesce(settings, '{}'::jsonb) || jsonb_build_object(
        'principal_payment_structure', 'separate_from_daily_interest',
        'interest_basis', 'original_principal_until_principal_zero',
        'accounting_interest_model', 'effective_interest_pending_contract_schedule_validation',
        'accounting_policy_version', '7x7_original_principal_v1'
    ),
    updated_at = now()
WHERE calculation_mode = 'seven_by_seven';

CREATE OR REPLACE VIEW accounting.loan_cutover_readiness AS
SELECT
    loan.id AS loan_id,
    loan.loan_number,
    client.client_code,
    client.full_name AS client_name,
    loan_type.code AS loan_type_code,
    loan_type.name AS loan_type_name,
    loan_type.calculation_mode,
    loan_type.term_days,
    loan.principal,
    loan.daily_amount,
    loan.interest_rate,
    loan.date_released,
    loan.due_date,
    loan.status,
    coalesce(state.remaining_balance, loan.principal) AS operational_balance,
    CASE
        WHEN loan_type.calculation_mode = 'fixed_daily' THEN
            round(loan.principal * (1 + coalesce(loan.interest_rate, 0) / 100.0), 2)
        ELSE NULL
    END AS regular_contract_total,
    CASE
        WHEN loan_type.calculation_mode = 'fixed_daily' THEN
            round(loan.daily_amount * loan_type.term_days, 2)
        ELSE NULL
    END AS regular_scheduled_total,
    CASE
        WHEN loan_type.calculation_mode = 'seven_by_seven' THEN
            round(ceil(loan.principal / 1000.0) * loan_type.daily_interest_per_1000, 2)
        ELSE NULL
    END AS seven_by_seven_expected_daily_interest,
    CASE
        WHEN loan_type.calculation_mode = 'fixed_daily'
         AND loan.interest_rate IS NOT NULL
         AND loan.interest_rate > 0
         AND loan.daily_amount > 0
         AND abs(
             round(loan.principal * (1 + loan.interest_rate / 100.0), 2)
             - round(loan.daily_amount * loan_type.term_days, 2)
         ) <= 0.01
         AND loan.due_date = loan.date_released + loan_type.term_days
            THEN 'source_ready'
        WHEN loan_type.calculation_mode = 'seven_by_seven'
         AND loan_type.daily_interest_per_1000 > 0
         AND loan.daily_amount = round(
             ceil(loan.principal / 1000.0) * loan_type.daily_interest_per_1000,
             2
         )
         AND coalesce(
             (loan_type.settings ->> 'mobile_collections_enabled')::boolean,
             false
         ) = false
            THEN 'contract_schedule_validation_required'
        ELSE 'blocked'
    END AS readiness_status,
    array_remove(ARRAY[
        CASE
            WHEN loan_type.calculation_mode = 'fixed_daily'
             AND (loan.interest_rate IS NULL OR loan.interest_rate <= 0)
                THEN 'Regular contract interest rate is missing or invalid.'
        END,
        CASE
            WHEN loan_type.calculation_mode = 'fixed_daily'
             AND abs(
                 round(loan.principal * (1 + coalesce(loan.interest_rate, 0) / 100.0), 2)
                 - round(loan.daily_amount * loan_type.term_days, 2)
             ) > 0.01
                THEN 'Regular scheduled cash total does not equal principal plus fixed contract interest.'
        END,
        CASE
            WHEN loan.due_date <> loan.date_released + loan_type.term_days
                THEN 'Loan due date does not match the configured contractual term.'
        END,
        CASE
            WHEN loan_type.calculation_mode = 'seven_by_seven'
             AND loan.daily_amount <> round(
                 ceil(loan.principal / 1000.0) * loan_type.daily_interest_per_1000,
                 2
             )
                THEN '7x7 daily amount does not match the fixed daily interest based on original principal.'
        END,
        CASE
            WHEN loan_type.calculation_mode = 'seven_by_seven'
                THEN 'Validate the contractual principal repayment/maturity cash-flow schedule before deriving the PFRS effective-interest rate.'
        END,
        CASE
            WHEN loan_type.calculation_mode = 'seven_by_seven'
             AND coalesce(
                 (loan_type.settings ->> 'mobile_collections_enabled')::boolean,
                 false
             ) = true
                THEN '7x7 mobile collections must remain disabled during accounting cutover validation.'
        END
    ], NULL) AS blockers
FROM lending.loans loan
JOIN lending.clients client ON client.id = loan.client_id
JOIN lending.loan_types loan_type ON loan_type.id = loan.loan_type_id
LEFT JOIN lending.loan_collection_state state ON state.loan_id = loan.id;

CREATE OR REPLACE VIEW accounting.cutover_readiness_summary AS
SELECT
    count(*) FILTER (WHERE status = 'active') AS active_loan_count,
    count(*) FILTER (
        WHERE status = 'active' AND readiness_status = 'source_ready'
    ) AS source_ready_count,
    count(*) FILTER (
        WHERE status = 'active'
          AND readiness_status = 'contract_schedule_validation_required'
    ) AS contract_validation_count,
    count(*) FILTER (
        WHERE status = 'active' AND readiness_status = 'blocked'
    ) AS blocked_count,
    false AS opening_balances_configured,
    false AS automatic_source_posting_enabled,
    CASE
        WHEN count(*) FILTER (
            WHERE status = 'active' AND readiness_status = 'blocked'
        ) > 0 THEN 'blocked'
        WHEN count(*) FILTER (
            WHERE status = 'active'
              AND readiness_status = 'contract_schedule_validation_required'
        ) > 0 THEN 'contract_validation_required'
        ELSE 'opening_balances_required'
    END AS overall_status
FROM accounting.loan_cutover_readiness;

-- A reversal is the correction record for the original posted journal. Do not
-- create reversal-of-reversal chains. A later correction must be a new properly
-- documented manual journal, leaving the original and its reversal intact.
CREATE OR REPLACE FUNCTION accounting.create_reversal_draft(
    p_entry_id UUID,
    p_actor_user_id UUID,
    p_posting_date DATE,
    p_description TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    original accounting.journal_entries%ROWTYPE;
    target_period_id UUID;
    reversal_id UUID;
BEGIN
    SELECT * INTO original
    FROM accounting.journal_entries
    WHERE id = p_entry_id
    FOR SHARE;

    IF NOT FOUND OR original.status <> 'posted' THEN
        RAISE EXCEPTION 'Only a posted journal entry can be reversed.';
    END IF;
    IF original.reversal_of_entry_id IS NOT NULL
       OR original.source_type = 'reversal' THEN
        RAISE EXCEPTION 'A reversal journal cannot be reversed again. Record any further correction as a new documented journal entry.';
    END IF;
    IF EXISTS (
        SELECT 1 FROM accounting.journal_entries
        WHERE reversal_of_entry_id = p_entry_id
    ) THEN
        RAISE EXCEPTION 'This journal entry already has a reversal.';
    END IF;
    IF btrim(coalesce(p_description, '')) = '' THEN
        RAISE EXCEPTION 'Reversal description is required.';
    END IF;

    SELECT id INTO target_period_id
    FROM accounting.fiscal_periods
    WHERE status = 'open'
      AND p_posting_date BETWEEN start_date AND end_date
    ORDER BY start_date DESC
    LIMIT 1;

    IF target_period_id IS NULL THEN
        RAISE EXCEPTION 'No open accounting period contains the reversal date.';
    END IF;

    INSERT INTO accounting.journal_entries (
        fiscal_period_id,
        posting_date,
        description,
        source_type,
        source_reference,
        source_event_key,
        reversal_of_entry_id,
        created_by_user_id
    )
    VALUES (
        target_period_id,
        p_posting_date,
        btrim(p_description),
        'reversal',
        original.entry_number,
        'reversal:' || original.id::text,
        original.id,
        p_actor_user_id
    )
    RETURNING id INTO reversal_id;

    INSERT INTO accounting.journal_lines (
        journal_entry_id,
        line_number,
        account_id,
        description,
        debit,
        credit,
        client_id,
        loan_id
    )
    SELECT
        reversal_id,
        line_number,
        account_id,
        description,
        credit,
        debit,
        client_id,
        loan_id
    FROM accounting.journal_lines
    WHERE journal_entry_id = original.id
    ORDER BY line_number;

    RETURN reversal_id;
END;
$$;

COMMIT;
