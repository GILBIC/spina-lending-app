BEGIN;

-- Master #296 A4 usability/fail-closed hardening. Before a preparation exists,
-- expose the exact current posting date, open period, 5000/1190 accounts,
-- authoritative amount and prior protected allowance balance that Management
-- must confirm. No journal or allowance is created by this view.

CREATE OR REPLACE VIEW accounting.ecl_allowance_posting_queue AS
WITH account_coordinates AS (
    SELECT
        (min(account.id::text) FILTER (
            WHERE account.system_key = 'credit_loss_expense'
              AND account.code = '5000'
              AND account.account_type = 'expense'
              AND account.normal_balance = 'debit'
              AND account.is_active
              AND account.is_posting
        ))::uuid AS credit_loss_expense_account_id,
        count(*) FILTER (
            WHERE account.system_key = 'credit_loss_expense'
              AND account.code = '5000'
              AND account.account_type = 'expense'
              AND account.normal_balance = 'debit'
              AND account.is_active
              AND account.is_posting
        )::integer AS credit_loss_expense_account_count,
        (min(account.id::text) FILTER (
            WHERE account.system_key = 'allowance_expected_credit_loss'
              AND account.code = '1190'
              AND account.account_type = 'asset'
              AND account.normal_balance = 'credit'
              AND account.is_active
              AND account.is_posting
        ))::uuid AS allowance_account_id,
        count(*) FILTER (
            WHERE account.system_key = 'allowance_expected_credit_loss'
              AND account.code = '1190'
              AND account.account_type = 'asset'
              AND account.normal_balance = 'credit'
              AND account.is_active
              AND account.is_posting
        )::integer AS allowance_account_count
    FROM accounting.accounts account
)
SELECT
    measurement_queue.loan_id,
    measurement_queue.loan_number,
    measurement_queue.loan_status,
    measurement_queue.loan_type_code,
    measurement_queue.loan_type_name,
    measurement_queue.calculation_mode,
    measurement_queue.measurement_id,
    measurement_queue.measurement_version,
    measurement_queue.measurement_date,
    measurement_queue.loss_horizon,
    measurement_queue.calculation_digest,
    measurement_queue.measurement_status,
    measurement_queue.authoritative_ecl_amount,
    prepared.id AS preparation_id,
    prepared.journal_entry_id,
    coalesce(
        prepared.source_event_key,
        CASE WHEN measurement_queue.measurement_id IS NOT NULL
             THEN 'ecl_allowance:' || measurement_queue.measurement_id::text
        END
    ) AS source_event_key,
    coalesce(prepared.posting_date, measurement_queue.measurement_date)
        AS posting_date,
    coalesce(prepared.fiscal_period_id, period_coordinates.id) AS fiscal_period_id,
    coalesce(
        prepared.credit_loss_expense_account_id,
        account_coordinates.credit_loss_expense_account_id
    ) AS credit_loss_expense_account_id,
    coalesce(
        prepared.allowance_account_id,
        account_coordinates.allowance_account_id
    ) AS allowance_account_id,
    coalesce(prepared.allowance_amount, measurement_queue.authoritative_ecl_amount)
        AS allowance_amount,
    coalesce(
        prepared.prior_allowance_balance,
        accounting.ecl_loan_allowance_balance(measurement_queue.loan_id)
    ) AS prior_allowance_balance,
    prepared.preparation_review_token,
    prepared.preparation_digest,
    coalesce(prepared.draft_policy_version, 'ecl_allowance_initial_journal_draft_v1')
        AS draft_policy_version,
    journal.status AS journal_status,
    journal.entry_number,
    posting.id AS posting_id,
    posting.posting_review_token,
    posting.posting_policy_version,
    accounting.ecl_loan_allowance_balance(measurement_queue.loan_id)
        AS current_allowance_balance,
    CASE
        WHEN measurement_queue.measurement_status <> 'measured_read_only'
          OR measurement_queue.authoritative_ecl_amount IS NULL
            THEN 'measurement_not_authoritative'
        WHEN measurement_queue.authoritative_ecl_amount = 0
          AND accounting.ecl_loan_allowance_balance(measurement_queue.loan_id) = 0
            THEN 'no_allowance_required'
        WHEN posting.id IS NOT NULL
          AND posting.measurement_id = measurement_queue.measurement_id
          AND accounting.ecl_loan_allowance_balance(measurement_queue.loan_id)
              = posting.resulting_allowance_balance
            THEN 'posted_current'
        WHEN accounting.ecl_loan_allowance_balance(measurement_queue.loan_id) <> 0
            THEN 'a5_remeasurement_required'
        WHEN prepared.id IS NOT NULL AND journal.status = 'draft'
            THEN 'posting_ready'
        WHEN prepared.id IS NOT NULL AND journal.status = 'posted' AND posting.id IS NULL
            THEN 'posting_audit_incomplete'
        WHEN period_coordinates.open_period_count <> 1
          OR account_coordinates.credit_loss_expense_account_count <> 1
          OR account_coordinates.allowance_account_count <> 1
            THEN 'preparation_blocked'
        ELSE 'preparation_required'
    END AS allowance_posting_status,
    (
        measurement_queue.measurement_status = 'measured_read_only'
        AND measurement_queue.authoritative_ecl_amount > 0
        AND accounting.ecl_loan_allowance_balance(measurement_queue.loan_id) = 0
        AND posting.id IS NULL
        AND period_coordinates.open_period_count = 1
        AND account_coordinates.credit_loss_expense_account_count = 1
        AND account_coordinates.allowance_account_count = 1
    ) AS protected_allowance_action_ready,
    true AS account_1190_posting_enabled,
    false AS automatic_source_posting
FROM accounting.ecl_quantitative_measurement_queue measurement_queue
CROSS JOIN account_coordinates
LEFT JOIN LATERAL (
    SELECT
        min(period.id::text)::uuid AS id,
        count(*)::integer AS open_period_count
    FROM accounting.fiscal_periods period
    WHERE period.status = 'open'
      AND measurement_queue.measurement_date BETWEEN period.start_date AND period.end_date
) period_coordinates ON true
LEFT JOIN accounting.ecl_allowance_draft_preparations prepared
  ON prepared.measurement_id = measurement_queue.measurement_id
LEFT JOIN accounting.journal_entries journal
  ON journal.id = prepared.journal_entry_id
LEFT JOIN accounting.ecl_allowance_postings posting
  ON posting.preparation_id = prepared.id;

CREATE OR REPLACE VIEW accounting.ecl_allowance_posting_summary AS
SELECT
    count(*)::bigint AS loan_count,
    count(*) FILTER (WHERE allowance_posting_status = 'measurement_not_authoritative')::bigint
        AS measurement_not_authoritative_count,
    count(*) FILTER (WHERE allowance_posting_status = 'no_allowance_required')::bigint
        AS no_allowance_required_count,
    count(*) FILTER (WHERE allowance_posting_status = 'preparation_required')::bigint
        AS preparation_required_count,
    count(*) FILTER (WHERE allowance_posting_status = 'posting_ready')::bigint
        AS posting_ready_count,
    count(*) FILTER (WHERE allowance_posting_status = 'posted_current')::bigint
        AS posted_current_count,
    count(*) FILTER (WHERE allowance_posting_status = 'a5_remeasurement_required')::bigint
        AS a5_remeasurement_required_count,
    count(*) FILTER (WHERE allowance_posting_status = 'posting_audit_incomplete')::bigint
        AS posting_audit_incomplete_count,
    count(*) FILTER (WHERE allowance_posting_status = 'preparation_blocked')::bigint
        AS preparation_blocked_count,
    coalesce(sum(current_allowance_balance), 0)::numeric(18,2)
        AS protected_allowance_balance_total,
    true AS account_1190_posting_enabled,
    false AS automatic_source_posting
FROM accounting.ecl_allowance_posting_queue;

COMMENT ON VIEW accounting.ecl_allowance_posting_queue IS
'A4 Management queue exposes exact candidate measurement/date/open-period/5000/1190/amount/prior-balance coordinates before preparation. Missing or ambiguous exact coordinates fail closed; no journal is auto-created and automatic source posting remains disabled.';

COMMIT;
