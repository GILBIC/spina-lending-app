BEGIN;

CREATE OR REPLACE VIEW accounting.remittance_transfer_journal_status AS
WITH line_summary AS (
    SELECT
        prepared.id AS preparation_id,
        count(line.id)::integer AS line_count,
        coalesce(sum(line.debit), 0)::numeric(18,2) AS total_debit,
        coalesce(sum(line.credit), 0)::numeric(18,2) AS total_credit,
        count(line.id) FILTER (
            WHERE line.account_id = prepared.debit_account_id
              AND line.debit = prepared.amount
              AND line.credit = 0
        )::integer AS debit_match_count,
        count(line.id) FILTER (
            WHERE line.account_id = prepared.credit_account_id
              AND line.credit = prepared.amount
              AND line.debit = 0
        )::integer AS credit_match_count
    FROM accounting.remittance_transfer_journal_preparations prepared
    LEFT JOIN accounting.journal_lines line
      ON line.journal_entry_id = prepared.journal_entry_id
    GROUP BY prepared.id
),
reversal_line_summary AS (
    SELECT
        reversal.id AS reversal_id,
        count(line.id)::integer AS line_count,
        coalesce(sum(line.debit), 0)::numeric(18,2) AS total_debit,
        coalesce(sum(line.credit), 0)::numeric(18,2) AS total_credit,
        count(line.id) FILTER (
            WHERE line.account_id = reversal.original_credit_account_id
              AND line.debit = reversal.amount
              AND line.credit = 0
        )::integer AS debit_match_count,
        count(line.id) FILTER (
            WHERE line.account_id = reversal.original_debit_account_id
              AND line.credit = reversal.amount
              AND line.debit = 0
        )::integer AS credit_match_count
    FROM accounting.remittance_transfer_journal_reversals reversal
    LEFT JOIN accounting.journal_lines line
      ON line.journal_entry_id = reversal.reversal_journal_entry_id
    GROUP BY reversal.id
)
SELECT
    prepared.id AS preparation_id,
    prepared.remittance_id,
    prepared.transfer_evidence_id,
    prepared.journal_entry_id,
    prepared.source_event_key,
    prepared.review_token AS draft_review_token,
    prepared.posting_date,
    prepared.fiscal_period_id,
    prepared.debit_account_id,
    debit_account.system_key AS debit_account_system_key,
    prepared.credit_account_id,
    credit_account.system_key AS credit_account_system_key,
    prepared.amount,
    journal.status AS journal_status,
    journal.entry_number,
    posting.id AS posting_id,
    posting.posting_review_token,
    posting.posted_by_user_id,
    posting.posted_at,
    reversal.id AS reversal_id,
    reversal.reversal_journal_entry_id,
    reversal.reversal_entry_number,
    reversal.reversal_posting_date,
    reversal.reason AS reversal_reason,
    CASE
        WHEN posting.id IS NULL
         AND journal.status = 'draft'
         AND journal.entry_number IS NULL
         AND journal.source_type = 'remittance_transfer'
         AND journal.source_reference = prepared.remittance_id::text
         AND journal.source_event_key = prepared.source_event_key
         AND journal.posting_date = prepared.posting_date
         AND journal.fiscal_period_id = prepared.fiscal_period_id
         AND line_summary.line_count = 2
         AND line_summary.total_debit = prepared.amount
         AND line_summary.total_credit = prepared.amount
         AND line_summary.debit_match_count = 1
         AND line_summary.credit_match_count = 1
         AND period.status = 'open'
         AND prepared.posting_date BETWEEN period.start_date AND period.end_date
         AND debit_account.system_key IN ('cash_office', 'cash_bank_gcash')
         AND debit_account.account_type = 'asset'
         AND debit_account.is_active = true
         AND debit_account.is_posting = true
         AND credit_account.system_key = 'cash_collector_custody'
         AND credit_account.account_type = 'asset'
         AND credit_account.is_active = true
         AND credit_account.is_posting = true
         AND readiness.readiness_status = 'transfer_coordinate_ready'
         AND readiness.transfer_evidence_id = prepared.transfer_evidence_id
         AND readiness.source_event_key = prepared.source_event_key
         AND readiness.business_date = prepared.posting_date
         AND readiness.debit_account_system_key = debit_account.system_key
         AND readiness.credit_account_system_key = credit_account.system_key
         AND readiness.debit_amount = prepared.amount
         AND readiness.credit_amount = prepared.amount
         AND readiness.income_recognition = false
         AND readiness.journal_lines_enabled = false
         AND readiness.automatic_source_posting = false
            THEN true
        ELSE false
    END AS posting_ready,
    CASE
        WHEN posting.id IS NOT NULL
         AND journal.status = 'posted'
         AND journal.entry_number = posting.entry_number
         AND journal.source_type = 'remittance_transfer'
         AND journal.source_reference = prepared.remittance_id::text
         AND journal.source_event_key = posting.source_event_key
         AND posting.preparation_id = prepared.id
         AND posting.remittance_id = prepared.remittance_id
         AND posting.transfer_evidence_id = prepared.transfer_evidence_id
         AND posting.journal_entry_id = prepared.journal_entry_id
         AND posting.source_event_key = prepared.source_event_key
         AND posting.draft_review_token = prepared.review_token
         AND posting.draft_policy_version = prepared.draft_policy_version
         AND posting.posting_policy_version = 'remittance_transfer_journal_posting_v1'
         AND posting.posting_date = prepared.posting_date
         AND posting.fiscal_period_id = prepared.fiscal_period_id
         AND posting.debit_account_id = prepared.debit_account_id
         AND posting.credit_account_id = prepared.credit_account_id
         AND posting.amount = prepared.amount
         AND line_summary.line_count = 2
         AND line_summary.total_debit = prepared.amount
         AND line_summary.total_credit = prepared.amount
         AND line_summary.debit_match_count = 1
         AND line_summary.credit_match_count = 1
            THEN true
        ELSE false
    END AS posted_audit_exact,
    CASE
        WHEN reversal.id IS NULL THEN false
        WHEN posting.id IS NOT NULL
         AND reversal.posting_id = posting.id
         AND reversal.remittance_id = posting.remittance_id
         AND reversal.original_journal_entry_id = posting.journal_entry_id
         AND reversal.original_entry_number = posting.entry_number
         AND reversal.original_source_event_key = posting.source_event_key
         AND reversal.original_debit_account_id = posting.debit_account_id
         AND reversal.original_credit_account_id = posting.credit_account_id
         AND reversal.amount = posting.amount
         AND reversal.reversal_source_event_key = 'remittance_transfer_reversal:' || posting.id::text
         AND reversal_journal.status = 'posted'
         AND reversal_journal.entry_number = reversal.reversal_entry_number
         AND reversal_journal.source_type = 'remittance_transfer_reversal'
         AND reversal_journal.source_reference = posting.id::text
         AND reversal_journal.source_event_key = reversal.reversal_source_event_key
         AND reversal_journal.reversal_of_entry_id = posting.journal_entry_id
         AND reversal_line_summary.line_count = 2
         AND reversal_line_summary.total_debit = reversal.amount
         AND reversal_line_summary.total_credit = reversal.amount
         AND reversal_line_summary.debit_match_count = 1
         AND reversal_line_summary.credit_match_count = 1
            THEN true
        ELSE false
    END AS reversal_audit_exact,
    CASE
        WHEN reversal.id IS NOT NULL THEN 'reversed'
        WHEN posting.id IS NOT NULL THEN 'posted'
        ELSE 'draft'
    END AS lifecycle_status,
    false AS income_recognition,
    true AS explicit_management_posting,
    false AS automatic_source_posting
FROM accounting.remittance_transfer_journal_preparations prepared
JOIN accounting.journal_entries journal
  ON journal.id = prepared.journal_entry_id
JOIN accounting.fiscal_periods period
  ON period.id = prepared.fiscal_period_id
JOIN accounting.accounts debit_account
  ON debit_account.id = prepared.debit_account_id
JOIN accounting.accounts credit_account
  ON credit_account.id = prepared.credit_account_id
JOIN line_summary
  ON line_summary.preparation_id = prepared.id
LEFT JOIN accounting.remittance_transfer_readiness readiness
  ON readiness.remittance_id = prepared.remittance_id
LEFT JOIN accounting.remittance_transfer_journal_postings posting
  ON posting.preparation_id = prepared.id
LEFT JOIN accounting.remittance_transfer_journal_reversals reversal
  ON reversal.posting_id = posting.id
LEFT JOIN accounting.journal_entries reversal_journal
  ON reversal_journal.id = reversal.reversal_journal_entry_id
LEFT JOIN reversal_line_summary
  ON reversal_line_summary.reversal_id = reversal.id;

COMMENT ON VIEW accounting.remittance_transfer_journal_status IS
    'Protected remittance journal lifecycle reconciliation. Draft posting_ready requires current authoritative 0057 transfer-coordinate readiness, an open containing period, active asset posting accounts, exact protected lines, explicit Management posting, no income recognition, and automatic source posting disabled.';

COMMIT;
