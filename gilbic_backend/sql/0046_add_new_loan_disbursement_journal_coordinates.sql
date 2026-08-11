BEGIN;

INSERT INTO core.permissions (code, description)
VALUES (
    'accounting.loan_disbursement.coordinates.view',
    'View protected candidate accounting coordinates for authoritative pure new Regular loan releases'
)
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code = 'accounting.loan_disbursement.coordinates.view'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

-- Stage 5D.20 is deliberately read-only. It does not create journal entries,
-- journal lines, posting sets, or automatic posting behavior. It translates
-- immutable Stage 5D.19 source evidence into the exact two-line candidate for
-- the first supported greenfield case only:
--   pure new Regular loan release, no settlement, no deduction,
--   Dr Loans Receivable - Regular / Cr exact evidence-backed cash account.
--
-- IFRS 9 initial recognition is at fair value plus directly attributable
-- transaction costs for assets not at FVTPL; transaction price is normally the
-- initial fair value. This V1 coordinate supports only ordinary plain-cash
-- origination where the evidence amount equals principal and no other release
-- component exists. Concessionary/off-market, fee, deduction, settlement,
-- renewal/restructure and 7x7 cases remain outside this stage.

CREATE OR REPLACE VIEW accounting.loan_disbursement_journal_coordinates AS
WITH source AS (
    SELECT
        readiness.loan_id,
        readiness.loan_number,
        readiness.client_id,
        readiness.client_code,
        readiness.client_name,
        readiness.loan_type_code,
        readiness.loan_type_name,
        readiness.calculation_mode,
        readiness.principal,
        readiness.date_released,
        readiness.loan_status,
        readiness.disbursement_event_id,
        readiness.event_kind,
        readiness.business_date,
        readiness.disbursed_at,
        readiness.cash_disbursed_amount,
        readiness.settlement_amount,
        readiness.other_deduction_amount,
        readiness.funding_account_system_key,
        readiness.external_reference,
        readiness.principal_snapshot,
        readiness.source_event_key,
        readiness.readiness_status AS evidence_readiness_status,
        period.id AS fiscal_period_id,
        receivable.id AS receivable_account_id,
        receivable.is_active AS receivable_is_active,
        receivable.is_posting AS receivable_is_posting,
        funding.id AS funding_account_id,
        funding.account_type AS funding_account_type,
        funding.is_active AS funding_is_active,
        funding.is_posting AS funding_is_posting,
        journal.id AS existing_journal_entry_id
    FROM accounting.loan_disbursement_source_readiness readiness
    LEFT JOIN accounting.fiscal_periods period
      ON period.status = 'open'
     AND readiness.business_date BETWEEN period.start_date AND period.end_date
    LEFT JOIN accounting.accounts receivable
      ON receivable.system_key = 'loans_receivable_regular'
    LEFT JOIN accounting.accounts funding
      ON funding.system_key = readiness.funding_account_system_key
    LEFT JOIN accounting.journal_entries journal
      ON journal.source_event_key = readiness.source_event_key
), evaluated AS (
    SELECT
        source.*,
        CASE
            WHEN source.evidence_readiness_status <> 'source_evidence_ready'
                THEN source.evidence_readiness_status
            WHEN source.event_kind <> 'new_loan_release'
                THEN 'release_context_policy_review'
            WHEN source.calculation_mode <> 'fixed_daily'
                THEN 'loan_type_policy_review'
            WHEN source.settlement_amount <> 0
              OR source.other_deduction_amount <> 0
                THEN 'release_component_policy_review'
            WHEN round(source.cash_disbursed_amount, 2)
                 IS DISTINCT FROM round(source.principal_snapshot, 2)
                THEN 'principal_cash_mismatch'
            WHEN source.fiscal_period_id IS NULL
                THEN 'fiscal_period_not_open'
            WHEN source.receivable_account_id IS NULL
              OR source.receivable_is_active IS DISTINCT FROM true
              OR source.receivable_is_posting IS DISTINCT FROM true
                THEN 'receivable_account_unavailable'
            WHEN source.funding_account_id IS NULL
              OR source.funding_account_type IS DISTINCT FROM 'asset'
              OR source.funding_is_active IS DISTINCT FROM true
              OR source.funding_is_posting IS DISTINCT FROM true
              OR source.funding_account_system_key NOT IN (
                    'cash_office',
                    'cash_collector_custody',
                    'cash_bank_gcash'
                 )
                THEN 'funding_account_unavailable'
            WHEN source.existing_journal_entry_id IS NOT NULL
                THEN 'journal_history_exists'
            ELSE 'coordinate_ready'
        END AS coordinate_status
    FROM source
)
SELECT
    evaluated.loan_id,
    evaluated.loan_number,
    evaluated.client_id,
    evaluated.client_code,
    evaluated.client_name,
    evaluated.loan_type_code,
    evaluated.loan_type_name,
    evaluated.calculation_mode,
    evaluated.disbursement_event_id,
    evaluated.event_kind,
    evaluated.business_date AS posting_date,
    evaluated.disbursed_at,
    evaluated.external_reference,
    evaluated.source_event_key,
    evaluated.evidence_readiness_status,
    evaluated.coordinate_status,
    evaluated.fiscal_period_id,
    CASE WHEN evaluated.coordinate_status = 'coordinate_ready'
        THEN 'loans_receivable_regular' END AS debit_account_system_key,
    CASE WHEN evaluated.coordinate_status = 'coordinate_ready'
        THEN evaluated.principal_snapshot END AS debit_amount,
    CASE WHEN evaluated.coordinate_status = 'coordinate_ready'
        THEN evaluated.funding_account_system_key END AS credit_account_system_key,
    CASE WHEN evaluated.coordinate_status = 'coordinate_ready'
        THEN evaluated.cash_disbursed_amount END AS credit_amount,
    CASE WHEN evaluated.coordinate_status = 'coordinate_ready'
        THEN evaluated.receivable_account_id END AS debit_account_id,
    CASE WHEN evaluated.coordinate_status = 'coordinate_ready'
        THEN evaluated.funding_account_id END AS credit_account_id,
    evaluated.existing_journal_entry_id,
    'transaction_price_plain_cash_v1'::text AS initial_measurement_basis,
    false AS journal_draft_enabled,
    false AS automatic_source_posting
FROM evaluated;

COMMENT ON VIEW accounting.loan_disbursement_journal_coordinates IS
    'Read-only Stage 5D.20 candidate coordinates from immutable Stage 5D.19 evidence. Supports only pure new fixed-daily Regular release; creates no journal history and leaves automatic source posting disabled.';

COMMIT;
