BEGIN;

-- Stage 5B records the 7x7 contractual base schedule that was confirmed for
-- accounting preparation. This still does not enable automatic accounting
-- posting or mobile 7x7 collection.
UPDATE lending.loan_types
SET settings = coalesce(settings, '{}'::jsonb) || jsonb_build_object(
        'contractual_interest_payment_frequency', 'daily',
        'contractual_principal_due', 'on_or_before_maturity',
        'principal_prepayment_allowed', true,
        'principal_prepayment_changes_daily_interest', false,
        'renewal_settlement_rule', 'new_principal_minus_old_principal_outstanding_minus_accrued_unpaid_interest',
        'accounting_interest_model', 'effective_interest_base_schedule_validated',
        'accounting_policy_version', '7x7_interest_daily_balloon_v2'
    ),
    updated_at = now()
WHERE calculation_mode = 'seven_by_seven';

DROP VIEW IF EXISTS accounting.opening_balance_cutover_summary;
DROP VIEW IF EXISTS accounting.opening_balance_cutover_worksheet;
DROP VIEW IF EXISTS accounting.cutover_readiness_summary;
DROP VIEW IF EXISTS accounting.loan_cutover_readiness;

CREATE VIEW accounting.loan_cutover_readiness AS
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
        WHEN loan_type.calculation_mode = 'seven_by_seven' THEN
            round(
                ceil(loan.principal / 1000.0)
                * loan_type.daily_interest_per_1000
                * loan_type.term_days,
                2
            )
        ELSE NULL
    END AS seven_by_seven_contract_interest_total,
    CASE
        WHEN loan_type.calculation_mode = 'seven_by_seven' THEN
            round(
                loan.principal
                + ceil(loan.principal / 1000.0)
                  * loan_type.daily_interest_per_1000
                  * loan_type.term_days,
                2
            )
        ELSE NULL
    END AS seven_by_seven_contract_total_if_principal_at_maturity,
    CASE
        WHEN loan_type.calculation_mode = 'seven_by_seven' AND loan.principal > 0 THEN
            round(
                (ceil(loan.principal / 1000.0) * loan_type.daily_interest_per_1000)
                / loan.principal * 100.0,
                6
            )
        ELSE NULL
    END AS seven_by_seven_base_daily_rate_percent,
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
         AND loan.due_date = loan.date_released + loan_type.term_days
         AND loan_type.settings ->> 'contractual_interest_payment_frequency' = 'daily'
         AND loan_type.settings ->> 'contractual_principal_due' = 'on_or_before_maturity'
         AND coalesce(
             (loan_type.settings ->> 'principal_prepayment_allowed')::boolean,
             false
         ) = true
         AND coalesce(
             (loan_type.settings ->> 'principal_prepayment_changes_daily_interest')::boolean,
             true
         ) = false
         AND coalesce(
             (loan_type.settings ->> 'mobile_collections_enabled')::boolean,
             false
         ) = false
            THEN 'source_ready'
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
             AND (
                 loan_type.settings ->> 'contractual_interest_payment_frequency' IS DISTINCT FROM 'daily'
                 OR loan_type.settings ->> 'contractual_principal_due' IS DISTINCT FROM 'on_or_before_maturity'
                 OR coalesce((loan_type.settings ->> 'principal_prepayment_allowed')::boolean, false) = false
                 OR coalesce((loan_type.settings ->> 'principal_prepayment_changes_daily_interest')::boolean, true) = true
             )
                THEN '7x7 contractual cash-flow schedule metadata is incomplete.'
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

CREATE VIEW accounting.cutover_readiness_summary AS
SELECT
    count(*) FILTER (WHERE status = 'active') AS active_loan_count,
    count(*) FILTER (
        WHERE status = 'active' AND readiness_status = 'source_ready'
    ) AS source_ready_count,
    0::bigint AS contract_validation_count,
    count(*) FILTER (
        WHERE status = 'active' AND readiness_status = 'blocked'
    ) AS blocked_count,
    false AS opening_balances_configured,
    false AS automatic_source_posting_enabled,
    CASE
        WHEN count(*) FILTER (
            WHERE status = 'active' AND readiness_status = 'blocked'
        ) > 0 THEN 'blocked'
        ELSE 'opening_balances_required'
    END AS overall_status
FROM accounting.loan_cutover_readiness;

CREATE VIEW accounting.opening_balance_cutover_worksheet AS
WITH source_values(
    account_code,
    source_reference_amount,
    source_basis,
    readiness_status,
    guidance
) AS (
    VALUES
        (
            '1010',
            NULL::numeric,
            'manual_required',
            'manual_required',
            'Enter the actual office cash count at the approved cutover date.'
        ),
        (
            '1020',
            (
                SELECT coalesce(sum(t.amount), 0)::numeric
                FROM lending.collection_transactions t
                WHERE t.is_voided = false
                  AND t.is_locked = false
                  AND t.remittance_id IS NULL
                  AND t.entry_type <> 'pass'
            ),
            'collection_custody_reference',
            'reconciliation_required',
            'Source reference is unlocked unremitted collection cash. Reconcile it to the physical collector-custody count before cutover.'
        ),
        (
            '1030',
            (
                SELECT coalesce(sum(r.total_amount), 0)::numeric
                FROM lending.collection_remittances r
                WHERE r.status = 'received'
            ),
            'received_remittance_reference',
            'reconciliation_required',
            'Received remittances are a custody reference only. Confirm whether each amount is in office cash, bank, or GCash before assigning an opening balance.'
        ),
        (
            '1100',
            (
                SELECT coalesce(sum(r.operational_balance), 0)::numeric
                FROM accounting.loan_cutover_readiness r
                WHERE r.status = 'active'
                  AND r.calculation_mode = 'fixed_daily'
            ),
            'regular_operational_reference',
            'calculation_required',
            'Operational Regular balance is reference-only. Derive the PFRS amortized-cost carrying amount using the effective-interest schedule before opening-balance posting.'
        ),
        (
            '1110',
            (
                SELECT coalesce(sum(r.operational_balance), 0)::numeric
                FROM accounting.loan_cutover_readiness r
                WHERE r.status = 'active'
                  AND r.calculation_mode = 'seven_by_seven'
            ),
            '7x7_principal_reference',
            'calculation_required',
            '7x7 principal outstanding is a source reference. Derive the accounting carrying amount from the validated contractual cash-flow schedule before posting.'
        ),
        (
            '1120',
            NULL::numeric,
            'accounting_schedule_required',
            'calculation_required',
            'Derive accrued interest receivable at the cutover date from the approved Regular and 7x7 accounting schedules. Do not reuse cash collected as income.'
        ),
        (
            '1190',
            NULL::numeric,
            'ecl_assessment_required',
            'assessment_required',
            'Complete the opening expected-credit-loss assessment separately from contractual interest and principal balances.'
        ),
        (
            '2000',
            NULL::numeric,
            'manual_required',
            'manual_required',
            'Enter verified accounts payable outstanding at the cutover date.'
        ),
        (
            '2100',
            NULL::numeric,
            'manual_required',
            'manual_required',
            'Enter verified tax liabilities at the cutover date. Tax accounting remains separate from PFRS loan measurement.'
        ),
        (
            '3000',
            NULL::numeric,
            'manual_required',
            'manual_required',
            'Enter verified contributed capital at the cutover date.'
        ),
        (
            '3100',
            NULL::numeric,
            'manual_required',
            'manual_required',
            'Enter verified retained earnings or the approved conversion balance after the cutover policy is finalized.'
        )
)
SELECT
    account.code AS account_code,
    account.system_key,
    account.name AS account_name,
    account.account_type,
    account.normal_balance,
    source.source_reference_amount,
    source.source_basis,
    source.readiness_status,
    source.guidance
FROM source_values source
JOIN accounting.accounts account ON account.code = source.account_code
ORDER BY account.code;

CREATE VIEW accounting.opening_balance_cutover_summary AS
SELECT
    NULL::date AS cutover_date,
    'source_review_required'::text AS worksheet_status,
    count(*) AS worksheet_line_count,
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
    true AS profit_loss_migration_policy_required,
    false AS worksheet_balanced,
    false AS ready_to_post,
    false AS opening_balance_posting_enabled,
    false AS automatic_source_posting_enabled
FROM accounting.opening_balance_cutover_worksheet;

COMMIT;
