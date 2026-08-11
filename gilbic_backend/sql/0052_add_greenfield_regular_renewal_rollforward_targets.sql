BEGIN;

-- Stage 5D.26 links authoritative renewal execution evidence to the Stage 5D.25
-- greenfield Regular EIR anchor. This is a read-only target/readiness layer.
-- It creates no carrying-amount journal, renewal journal, or source event.

CREATE OR REPLACE VIEW accounting.greenfield_regular_renewal_rollforward_targets AS
WITH execution_source AS (
    SELECT
        readiness.renewal_execution_event_id,
        readiness.disbursement_event_id AS renewal_disbursement_event_id,
        readiness.old_loan_id,
        readiness.old_loan_number,
        readiness.new_loan_id,
        readiness.new_loan_number,
        readiness.client_id,
        readiness.client_code,
        readiness.client_name,
        readiness.execution_business_date,
        readiness.executed_at,
        readiness.old_loan_settlement_amount,
        readiness.execution_external_reference,
        readiness.readiness_status AS renewal_source_readiness_status,
        readiness.source_event_key AS renewal_source_event_key
    FROM accounting.loan_renewal_execution_source_readiness readiness
    WHERE readiness.renewal_execution_event_id IS NOT NULL
), assembled AS (
    SELECT
        execution.*,
        anchor.posting_id AS anchor_posting_id,
        anchor.disbursement_event_id AS anchor_disbursement_event_id,
        anchor.journal_entry_id AS anchor_journal_entry_id,
        anchor.entry_number AS anchor_entry_number,
        anchor.anchor_date,
        anchor.initial_gross_carrying_amount,
        anchor.initial_loan_component,
        anchor.initial_accrued_interest_component,
        anchor.daily_eir,
        anchor.daily_eir_percent,
        anchor.contractual_due_date,
        anchor.schedule_id,
        anchor.contract_reference,
        anchor.evidence_reference AS contract_evidence_reference,
        anchor.readiness_status AS anchor_readiness_status,
        anchor.anchor_source_key,
        coalesce(source_counts.source_event_count_before_target, 0)::integer
            AS source_event_count_before_target,
        coalesce(source_counts.same_day_target_collection_count, 0)::integer
            AS same_day_target_collection_count
    FROM execution_source execution
    LEFT JOIN accounting.greenfield_regular_eir_anchor_readiness anchor
      ON anchor.loan_id = execution.old_loan_id
    LEFT JOIN LATERAL (
        SELECT
            count(transaction.id) FILTER (
                WHERE transaction.is_voided = false
                  AND transaction.entry_type IN ('payment', 'advance')
                  AND transaction.amount > 0
                  AND anchor.anchor_date IS NOT NULL
                  AND transaction.collection_date > anchor.anchor_date
                  AND transaction.collection_date < execution.execution_business_date
            )::integer AS source_event_count_before_target,
            count(transaction.id) FILTER (
                WHERE transaction.is_voided = false
                  AND transaction.entry_type IN ('payment', 'advance')
                  AND transaction.amount > 0
                  AND transaction.collection_date = execution.execution_business_date
            )::integer AS same_day_target_collection_count
        FROM lending.collection_transactions transaction
        WHERE transaction.loan_id = execution.old_loan_id
    ) source_counts ON true
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
    execution_business_date AS target_date,
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
    CASE
        WHEN renewal_source_readiness_status <> 'renewal_execution_evidence_ready'
            THEN 'renewal_execution_evidence_not_ready'
        WHEN anchor_posting_id IS NULL
            THEN 'greenfield_regular_eir_anchor_required'
        WHEN anchor_readiness_status <> 'greenfield_regular_eir_anchor_ready'
            THEN 'greenfield_regular_eir_anchor_not_ready'
        WHEN execution_business_date IS NULL OR executed_at IS NULL
            THEN 'renewal_execution_target_required'
        WHEN execution_business_date <= anchor_date
            THEN 'renewal_execution_after_anchor_required'
        WHEN contractual_due_date IS NULL
          OR execution_business_date > contractual_due_date
            THEN 'post_maturity_review_required'
        WHEN same_day_target_collection_count > 0
            THEN 'same_day_renewal_collection_ordering_review'
        WHEN source_event_count_before_target > 5000
            THEN 'source_history_too_large'
        ELSE 'greenfield_regular_renewal_rollforward_target_ready'
    END AS readiness_status,
    CASE
        WHEN renewal_execution_event_id IS NULL THEN NULL
        ELSE 'greenfield_regular_renewal_rollforward:'
            || renewal_execution_event_id::text
    END AS target_source_key,
    'greenfield_regular_renewal_rollforward_v1'::text AS rollforward_policy_version,
    CASE
        WHEN renewal_source_readiness_status = 'renewal_execution_evidence_ready'
         AND anchor_posting_id IS NOT NULL
         AND anchor_readiness_status = 'greenfield_regular_eir_anchor_ready'
         AND execution_business_date > anchor_date
         AND contractual_due_date IS NOT NULL
         AND execution_business_date <= contractual_due_date
         AND same_day_target_collection_count = 0
         AND source_event_count_before_target <= 5000
            THEN true
        ELSE false
    END AS measurement_preview_enabled,
    false AS accounting_carrying_amount_ready,
    false AS journal_lines_enabled,
    false AS automatic_source_posting
FROM assembled;

COMMENT ON VIEW accounting.greenfield_regular_renewal_rollforward_targets IS
    'Read-only Stage 5D.26 targets linking authoritative renewal execution evidence to a ready Stage 5D.25 greenfield Regular EIR anchor. Same-day renewal-date cash remains fail-closed. This view creates no journals and does not claim the measured preview is an authoritative ledger carrying amount.';

COMMIT;
