BEGIN;

-- Stage 5D.27 connects the immutable Stage 5D.17/5D.18 protected Regular
-- posting/reversal audit chain to the Stage 5D.25 greenfield anchor and the
-- Stage 5D.26 renewal-date measurement target. This view is deliberately only
-- a coarse read-only gate. Exact EIR period cents, source identities, journal
-- lines and ledger components are replayed in Python before any carrying amount
-- can be called authoritative.

CREATE OR REPLACE VIEW accounting.greenfield_regular_renewal_ledger_reconciliation_targets AS
WITH target AS (
    SELECT *
    FROM accounting.greenfield_regular_renewal_rollforward_targets
), protected_transaction_state AS (
    SELECT
        preparation.loan_id,
        preparation.transaction_id,
        max(preparation.expected_entry_count)::integer AS expected_entry_count,
        count(prepared_entry.journal_entry_id)::integer AS prepared_entry_count,
        count(posted_entry.journal_entry_id)::integer AS posting_audit_entry_count,
        count(*) FILTER (
            WHERE journal.status = 'posted'
              AND journal.entry_number = posted_entry.entry_number
              AND journal.source_event_key = posted_entry.source_event_key
        )::integer AS exact_posted_entry_count
    FROM accounting.regular_journal_draft_preparations preparation
    JOIN accounting.regular_journal_draft_preparation_entries prepared_entry
      ON prepared_entry.preparation_id = preparation.id
    LEFT JOIN accounting.regular_journal_posting_entries posted_entry
      ON posted_entry.preparation_id = preparation.id
     AND posted_entry.sequence_order = prepared_entry.sequence_order
     AND posted_entry.journal_entry_id = prepared_entry.journal_entry_id
    JOIN accounting.journal_entries journal
      ON journal.id = prepared_entry.journal_entry_id
    GROUP BY preparation.loan_id, preparation.transaction_id
), assembled AS (
    SELECT
        target.*,
        coalesce(source.active_source_count, 0)::integer AS active_source_count,
        coalesce(protected.complete_active_source_count, 0)::integer
            AS protected_complete_active_source_count,
        coalesce(protected.voided_posted_source_count, 0)::integer
            AS voided_posted_source_count,
        coalesce(protected.voided_unreversed_source_count, 0)::integer
            AS voided_unreversed_source_count,
        coalesce(unprotected.unprotected_posted_journal_count, 0)::integer
            AS unprotected_posted_journal_count
    FROM target
    LEFT JOIN LATERAL (
        SELECT count(transaction.id)::integer AS active_source_count
        FROM lending.collection_transactions transaction
        WHERE transaction.loan_id = target.old_loan_id
          AND target.anchor_date IS NOT NULL
          AND transaction.collection_date > target.anchor_date
          AND transaction.collection_date < target.target_date
          AND transaction.is_voided = false
          AND transaction.entry_type IN ('payment', 'advance')
          AND transaction.amount > 0
    ) source ON true
    LEFT JOIN LATERAL (
        SELECT
            count(*) FILTER (
                WHERE transaction.is_voided = false
                  AND transaction.entry_type IN ('payment', 'advance')
                  AND transaction.amount > 0
                  AND state.expected_entry_count > 0
                  AND state.prepared_entry_count = state.expected_entry_count
                  AND state.posting_audit_entry_count = state.expected_entry_count
                  AND state.exact_posted_entry_count = state.expected_entry_count
            )::integer AS complete_active_source_count,
            count(*) FILTER (
                WHERE transaction.is_voided = true
                  AND state.posting_audit_entry_count > 0
            )::integer AS voided_posted_source_count,
            count(*) FILTER (
                WHERE transaction.is_voided = true
                  AND state.posting_audit_entry_count > 0
                  AND NOT EXISTS (
                      SELECT 1
                      FROM accounting.regular_journal_reversal_sets reversal_set
                      WHERE reversal_set.transaction_id = transaction.id
                        AND reversal_set.expected_entry_count = state.expected_entry_count
                        AND reversal_set.reversed_entry_count = state.expected_entry_count
                  )
            )::integer AS voided_unreversed_source_count
        FROM protected_transaction_state state
        JOIN lending.collection_transactions transaction
          ON transaction.id = state.transaction_id
        WHERE state.loan_id = target.old_loan_id
          AND target.anchor_date IS NOT NULL
          AND transaction.collection_date > target.anchor_date
          AND transaction.collection_date < target.target_date
    ) protected ON true
    LEFT JOIN LATERAL (
        SELECT count(DISTINCT journal.id)::integer AS unprotected_posted_journal_count
        FROM accounting.journal_entries journal
        WHERE journal.status = 'posted'
          AND journal.source_type IN ('collection', 'regular_eir_accrual')
          AND target.anchor_date IS NOT NULL
          AND journal.posting_date > target.anchor_date
          AND journal.posting_date < target.target_date
          AND EXISTS (
              SELECT 1
              FROM accounting.journal_lines line
              WHERE line.journal_entry_id = journal.id
                AND line.loan_id = target.old_loan_id
          )
          AND NOT EXISTS (
              SELECT 1
              FROM accounting.regular_journal_posting_entries posted
              WHERE posted.journal_entry_id = journal.id
          )
    ) unprotected ON true
)
SELECT
    renewal_execution_event_id,
    renewal_disbursement_event_id,
    old_loan_id,
    old_loan_number,
    new_loan_id,
    new_loan_number,
    client_id,
    client_code,
    client_name,
    target_date,
    executed_at,
    old_loan_settlement_amount,
    execution_external_reference,
    renewal_source_readiness_status,
    renewal_source_event_key,
    anchor_posting_id,
    anchor_disbursement_event_id,
    anchor_journal_entry_id,
    anchor_entry_number,
    anchor_date,
    initial_gross_carrying_amount,
    initial_loan_component,
    initial_accrued_interest_component,
    daily_eir,
    daily_eir_percent,
    contractual_due_date,
    schedule_id,
    contract_reference,
    contract_evidence_reference,
    anchor_readiness_status,
    anchor_source_key,
    source_event_count_before_target,
    same_day_target_collection_count,
    readiness_status AS rollforward_readiness_status,
    target_source_key,
    rollforward_policy_version,
    measurement_preview_enabled,
    active_source_count,
    protected_complete_active_source_count,
    voided_posted_source_count,
    voided_unreversed_source_count,
    unprotected_posted_journal_count,
    CASE
        WHEN readiness_status <> 'greenfield_regular_renewal_rollforward_target_ready'
            THEN readiness_status
        WHEN active_source_count <> protected_complete_active_source_count
            THEN 'protected_regular_source_posting_gap'
        WHEN voided_unreversed_source_count > 0
            THEN 'voided_protected_regular_source_not_reversed'
        WHEN unprotected_posted_journal_count > 0
            THEN 'unprotected_regular_journal_history_review'
        ELSE 'greenfield_regular_ledger_reconciliation_candidate'
    END AS reconciliation_readiness_status,
    CASE
        WHEN readiness_status = 'greenfield_regular_renewal_rollforward_target_ready'
         AND active_source_count = protected_complete_active_source_count
         AND voided_unreversed_source_count = 0
         AND unprotected_posted_journal_count = 0
            THEN true
        ELSE false
    END AS exact_reconciliation_preview_enabled,
    'greenfield_regular_ledger_reconciliation_v1'::text
        AS reconciliation_policy_version,
    false AS accounting_carrying_amount_ready,
    false AS journal_lines_enabled,
    false AS automatic_source_posting
FROM assembled;

COMMENT ON VIEW accounting.greenfield_regular_renewal_ledger_reconciliation_targets IS
    'Read-only Stage 5D.27 coarse gate connecting Stage 5D.17/5D.18 protected Regular journal audit history to Stage 5D.25/5D.26 greenfield renewal targets. Exact source identities, period cents, lines and carrying components are replayed separately; this view never creates journals or enables automatic posting.';

COMMIT;
