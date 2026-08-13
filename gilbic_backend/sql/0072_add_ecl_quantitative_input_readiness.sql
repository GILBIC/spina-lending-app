BEGIN;

-- Master #296 A1: expose one fail-closed, read-only quantitative-ECL input
-- readiness gate per active loan. This migration deliberately does not create
-- forward-looking evidence, calculate ECL, post account 1190, execute a
-- write-off, or enable automatic source posting.

CREATE OR REPLACE VIEW accounting.ecl_quantitative_input_readiness AS
WITH base AS (
    SELECT
        queue.*,
        loan.client_id,
        loan.loan_type_id,
        loan.principal,
        loan.date_released,
        loan.due_date,
        loan_type.code AS loan_type_code,
        loan_type.name AS loan_type_name,
        loan_type.calculation_mode
    FROM accounting.ecl_credit_risk_label_queue queue
    JOIN lending.loans loan ON loan.id = queue.loan_id
    JOIN lending.loan_types loan_type ON loan_type.id = loan.loan_type_id
), evidence AS (
    SELECT
        base.*,
        regular_anchor.readiness_status AS regular_eir_anchor_status,
        regular_anchor.daily_eir AS regular_original_daily_eir,
        regular_anchor.initial_gross_carrying_amount AS regular_initial_gross_carrying_amount,
        seven_anchor.eir_initial_carrying_readiness_status AS seven_by_seven_eir_anchor_status,
        seven_anchor.authoritative_daily_eir AS seven_by_seven_original_daily_eir,
        seven_anchor.authoritative_initial_gross_carrying_amount AS seven_by_seven_initial_gross_carrying_amount,
        coalesce(regular_history.active_source_count, 0)::integer AS regular_active_source_count,
        coalesce(regular_history.exact_posted_active_source_count, 0)::integer AS regular_exact_posted_active_source_count,
        coalesce(regular_history.voided_posted_source_count, 0)::integer AS regular_voided_posted_source_count,
        coalesce(regular_history.exact_reversed_voided_source_count, 0)::integer AS regular_exact_reversed_voided_source_count,
        coalesce(seven_history.active_source_count, 0)::integer AS seven_by_seven_active_source_count,
        coalesce(seven_history.exact_posted_active_source_count, 0)::integer AS seven_by_seven_exact_posted_active_source_count,
        coalesce(seven_history.voided_posted_source_count, 0)::integer AS seven_by_seven_voided_posted_source_count,
        coalesce(seven_history.exact_reversed_voided_source_count, 0)::integer AS seven_by_seven_exact_reversed_voided_source_count,
        prior_review.created_at AS prior_reviewed_at,
        recovery_tx.accepted_at AS recovery_accepted_at,
        recovery_tx.loan_id AS recovery_loan_id,
        recovery_tx.is_voided AS recovery_is_voided,
        recovery_tx.amount AS recovery_amount,
        recovery_tx.entry_type AS recovery_entry_type
    FROM base
    LEFT JOIN accounting.greenfield_regular_eir_anchor_readiness regular_anchor
      ON regular_anchor.loan_id = base.loan_id
     AND base.calculation_mode = 'fixed_daily'
    LEFT JOIN accounting.seven_by_seven_eir_initial_carrying_readiness seven_anchor
      ON seven_anchor.loan_id = base.loan_id
     AND base.calculation_mode = 'seven_by_seven'
    LEFT JOIN accounting.ecl_credit_risk_label_reviews current_review
      ON current_review.id = base.review_id
    LEFT JOIN accounting.ecl_credit_risk_label_reviews prior_review
      ON prior_review.id = current_review.supersedes_review_id
    LEFT JOIN lending.collection_transactions recovery_tx
      ON recovery_tx.id = base.recovery_transaction_id
    LEFT JOIN LATERAL (
        SELECT
            count(*) FILTER (
                WHERE transaction.is_voided = false
            )::integer AS active_source_count,
            count(*) FILTER (
                WHERE transaction.is_voided = false
                  AND EXISTS (
                      SELECT 1
                      FROM accounting.regular_journal_draft_preparations preparation
                      WHERE preparation.loan_id = base.loan_id
                        AND preparation.transaction_id = transaction.id
                        AND preparation.expected_entry_count > 0
                        AND (
                            SELECT count(*)::integer
                            FROM accounting.regular_journal_draft_preparation_entries prepared_entry
                            JOIN accounting.regular_journal_posting_entries posted_entry
                              ON posted_entry.preparation_id = prepared_entry.preparation_id
                             AND posted_entry.sequence_order = prepared_entry.sequence_order
                             AND posted_entry.journal_entry_id = prepared_entry.journal_entry_id
                             AND posted_entry.transaction_id = transaction.id
                            JOIN accounting.journal_entries journal
                              ON journal.id = posted_entry.journal_entry_id
                            WHERE prepared_entry.preparation_id = preparation.id
                              AND journal.status = 'posted'
                              AND journal.entry_number = posted_entry.entry_number
                              AND journal.source_event_key = posted_entry.source_event_key
                        ) = preparation.expected_entry_count
                  )
            )::integer AS exact_posted_active_source_count,
            count(*) FILTER (
                WHERE transaction.is_voided = true
                  AND EXISTS (
                      SELECT 1
                      FROM accounting.regular_journal_posting_entries posted_entry
                      WHERE posted_entry.transaction_id = transaction.id
                  )
            )::integer AS voided_posted_source_count,
            count(*) FILTER (
                WHERE transaction.is_voided = true
                  AND EXISTS (
                      SELECT 1
                      FROM accounting.regular_journal_reversal_sets reversal_set
                      WHERE reversal_set.transaction_id = transaction.id
                        AND reversal_set.expected_entry_count > 0
                        AND reversal_set.reversed_entry_count = reversal_set.expected_entry_count
                        AND (
                            SELECT count(*)::integer
                            FROM accounting.regular_journal_reversal_entries reversal_entry
                            JOIN accounting.journal_entries reversal_journal
                              ON reversal_journal.id = reversal_entry.reversal_journal_entry_id
                            WHERE reversal_entry.reversal_set_id = reversal_set.id
                              AND reversal_journal.status = 'posted'
                              AND reversal_journal.entry_number = reversal_entry.reversal_entry_number
                              AND reversal_journal.source_event_key = reversal_entry.reversal_source_event_key
                        ) = reversal_set.expected_entry_count
                  )
            )::integer AS exact_reversed_voided_source_count
        FROM lending.collection_transactions transaction
        WHERE transaction.loan_id = base.loan_id
          AND transaction.entry_type IN ('payment', 'advance')
          AND transaction.amount > 0
          AND base.calculation_mode = 'fixed_daily'
    ) regular_history ON true
    LEFT JOIN LATERAL (
        SELECT
            count(*) FILTER (
                WHERE transaction.is_voided = false
            )::integer AS active_source_count,
            count(*) FILTER (
                WHERE transaction.is_voided = false
                  AND EXISTS (
                      SELECT 1
                      FROM accounting.seven_by_seven_journal_postings posting
                      JOIN accounting.journal_entries journal
                        ON journal.id = posting.journal_entry_id
                      WHERE posting.transaction_id = transaction.id
                        AND posting.loan_id = base.loan_id
                        AND journal.status = 'posted'
                        AND journal.entry_number = posting.entry_number
                        AND journal.source_event_key = posting.source_event_key
                  )
            )::integer AS exact_posted_active_source_count,
            count(*) FILTER (
                WHERE transaction.is_voided = true
                  AND EXISTS (
                      SELECT 1
                      FROM accounting.seven_by_seven_journal_postings posting
                      WHERE posting.transaction_id = transaction.id
                        AND posting.loan_id = base.loan_id
                  )
            )::integer AS voided_posted_source_count,
            count(*) FILTER (
                WHERE transaction.is_voided = true
                  AND EXISTS (
                      SELECT 1
                      FROM accounting.seven_by_seven_journal_reversals reversal
                      JOIN accounting.journal_entries reversal_journal
                        ON reversal_journal.id = reversal.reversal_journal_entry_id
                      WHERE reversal.transaction_id = transaction.id
                        AND reversal.loan_id = base.loan_id
                        AND reversal_journal.status = 'posted'
                        AND reversal_journal.entry_number = reversal.reversal_entry_number
                        AND reversal_journal.source_event_key = reversal.reversal_source_event_key
                  )
            )::integer AS exact_reversed_voided_source_count
        FROM lending.collection_transactions transaction
        WHERE transaction.loan_id = base.loan_id
          AND transaction.entry_type IN ('payment', 'advance')
          AND transaction.amount > 0
          AND base.calculation_mode = 'seven_by_seven'
    ) seven_history ON true
), evaluated AS (
    SELECT
        evidence.*,
        (
            evidence.dpd_data_status = 'ready'
            AND evidence.schedule_id IS NOT NULL
            AND evidence.schedule_version IS NOT NULL
            AND coalesce(btrim(evidence.contract_reference), '') <> ''
        ) AS contractual_schedule_dpd_ready,
        coalesce(evidence.current_label_ready, false) AS current_credit_risk_label_ready,
        CASE evidence.calculation_mode
            WHEN 'fixed_daily' THEN
                evidence.regular_eir_anchor_status = 'greenfield_regular_eir_anchor_ready'
                AND evidence.regular_original_daily_eir IS NOT NULL
                AND evidence.regular_original_daily_eir > 0
                AND evidence.regular_initial_gross_carrying_amount IS NOT NULL
                AND evidence.regular_initial_gross_carrying_amount > 0
            WHEN 'seven_by_seven' THEN
                evidence.seven_by_seven_eir_anchor_status = 'eir_initial_carrying_anchor_ready_for_7x7_accounting_lifecycle'
                AND evidence.seven_by_seven_original_daily_eir IS NOT NULL
                AND evidence.seven_by_seven_original_daily_eir > 0
                AND evidence.seven_by_seven_initial_gross_carrying_amount IS NOT NULL
                AND evidence.seven_by_seven_initial_gross_carrying_amount > 0
            ELSE false
        END AS original_eir_initial_carrying_ready,
        CASE evidence.calculation_mode
            WHEN 'fixed_daily' THEN
                evidence.regular_active_source_count = evidence.regular_exact_posted_active_source_count
                AND evidence.regular_voided_posted_source_count = evidence.regular_exact_reversed_voided_source_count
            WHEN 'seven_by_seven' THEN
                evidence.seven_by_seven_active_source_count = evidence.seven_by_seven_exact_posted_active_source_count
                AND evidence.seven_by_seven_voided_posted_source_count = evidence.seven_by_seven_exact_reversed_voided_source_count
            ELSE false
        END AS protected_collection_posting_reversal_history_ready,
        CASE evidence.calculation_mode
            WHEN 'fixed_daily' THEN
                evidence.regular_eir_anchor_status = 'greenfield_regular_eir_anchor_ready'
                AND evidence.regular_active_source_count = 0
                AND evidence.regular_voided_posted_source_count = 0
            WHEN 'seven_by_seven' THEN
                evidence.seven_by_seven_eir_anchor_status = 'eir_initial_carrying_anchor_ready_for_7x7_accounting_lifecycle'
                AND evidence.seven_by_seven_active_source_count = 0
                AND evidence.seven_by_seven_voided_posted_source_count = 0
            ELSE false
        END AS authoritative_current_carrying_ready,
        CASE
            WHEN NOT coalesce(evidence.current_label_ready, false) THEN true
            WHEN evidence.write_off_label = 'supported_no_reasonable_expectation_of_recovery'
              AND (
                    coalesce(btrim(evidence.write_off_evidence_reference), '') = ''
                 OR coalesce(btrim(evidence.write_off_note), '') = ''
              ) THEN false
            WHEN evidence.recovery_label = 'cash_recovery_observed'
              AND (
                    evidence.recovery_transaction_id IS NULL
                 OR evidence.prior_reviewed_at IS NULL
                 OR evidence.recovery_loan_id IS DISTINCT FROM evidence.loan_id
                 OR coalesce(evidence.recovery_is_voided, true)
                 OR coalesce(evidence.recovery_amount, 0) <= 0
                 OR evidence.recovery_entry_type NOT IN ('payment', 'advance')
                 OR evidence.recovery_accepted_at IS NULL
                 OR evidence.recovery_accepted_at <= evidence.prior_reviewed_at
              ) THEN false
            WHEN evidence.recovery_label = 'cured'
              AND (
                    coalesce(btrim(evidence.evidence_reference), '') = ''
                 OR coalesce(btrim(evidence.review_note), '') = ''
                 OR evidence.primary_evidence_basis = 'contractual_dpd'
              ) THEN false
            ELSE true
        END AS required_loss_recovery_writeoff_outcome_evidence_ready,
        false AS approved_forward_looking_evidence_ready
    FROM evidence
), blocker_rows AS (
    SELECT
        evaluated.loan_id,
        blocker.ordinal,
        blocker.code,
        blocker.evidence_class,
        blocker.message,
        blocker.source_status
    FROM evaluated
    CROSS JOIN LATERAL (
        VALUES
            (
                10,
                'verified_contractual_schedule_dpd_required'::text,
                'contractual_schedule_dpd'::text,
                evaluated.contractual_schedule_dpd_ready,
                'Verified current contractual schedule and contractual DPD evidence are required.'::text,
                coalesce(evaluated.dpd_data_status, 'missing')::text
            ),
            (
                20,
                'current_credit_risk_label_required'::text,
                'credit_risk_label'::text,
                evaluated.current_credit_risk_label_ready,
                'A current non-stale evidence-backed Management credit-risk label is required.'::text,
                coalesce(evaluated.label_review_status, 'missing')::text
            ),
            (
                30,
                'original_eir_initial_carrying_evidence_required'::text,
                'original_eir_initial_carrying'::text,
                evaluated.original_eir_initial_carrying_ready,
                'Applicable protected original EIR and initial gross carrying evidence are required.'::text,
                CASE evaluated.calculation_mode
                    WHEN 'fixed_daily' THEN coalesce(evaluated.regular_eir_anchor_status, 'missing_regular_eir_anchor')
                    WHEN 'seven_by_seven' THEN coalesce(evaluated.seven_by_seven_eir_anchor_status, 'missing_7x7_eir_anchor')
                    ELSE 'unsupported_calculation_mode'
                END::text
            ),
            (
                40,
                'protected_collection_posting_reversal_history_required'::text,
                'protected_collection_posting_reversal_history'::text,
                evaluated.protected_collection_posting_reversal_history_ready,
                'Every applicable protected collection must have exact protected posting coverage and every posted void must have its controlled reversal.'::text,
                CASE evaluated.calculation_mode
                    WHEN 'fixed_daily' THEN format(
                        'active=%s,posted=%s,voided_posted=%s,reversed=%s',
                        evaluated.regular_active_source_count,
                        evaluated.regular_exact_posted_active_source_count,
                        evaluated.regular_voided_posted_source_count,
                        evaluated.regular_exact_reversed_voided_source_count
                    )
                    WHEN 'seven_by_seven' THEN format(
                        'active=%s,posted=%s,voided_posted=%s,reversed=%s',
                        evaluated.seven_by_seven_active_source_count,
                        evaluated.seven_by_seven_exact_posted_active_source_count,
                        evaluated.seven_by_seven_voided_posted_source_count,
                        evaluated.seven_by_seven_exact_reversed_voided_source_count
                    )
                    ELSE 'unsupported_calculation_mode'
                END::text
            ),
            (
                45,
                'authoritative_current_gross_carrying_evidence_required'::text,
                'current_gross_carrying'::text,
                evaluated.authoritative_current_carrying_ready,
                'An authoritative current gross carrying amount reconciled from the original anchor and protected accounting history is required.'::text,
                CASE evaluated.calculation_mode
                    WHEN 'fixed_daily' THEN CASE
                        WHEN evaluated.regular_active_source_count = 0
                         AND evaluated.regular_voided_posted_source_count = 0
                            THEN coalesce(evaluated.regular_eir_anchor_status, 'missing_regular_eir_anchor')
                        ELSE 'current_regular_carrying_rollforward_not_authoritative'
                    END
                    WHEN 'seven_by_seven' THEN CASE
                        WHEN evaluated.seven_by_seven_active_source_count = 0
                         AND evaluated.seven_by_seven_voided_posted_source_count = 0
                            THEN coalesce(evaluated.seven_by_seven_eir_anchor_status, 'missing_7x7_eir_anchor')
                        ELSE 'current_7x7_carrying_rollforward_not_authoritative'
                    END
                    ELSE 'unsupported_calculation_mode'
                END::text
            ),
            (
                50,
                'required_loss_recovery_writeoff_outcome_evidence_required'::text,
                'loss_recovery_writeoff_outcome'::text,
                evaluated.required_loss_recovery_writeoff_outcome_evidence_ready,
                'Any applicable write-off-support, recovery, or cure conclusion must retain its exact protected outcome evidence.'::text,
                CASE
                    WHEN NOT evaluated.current_credit_risk_label_ready THEN 'not_applicable_until_current_label'
                    WHEN evaluated.write_off_label = 'supported_no_reasonable_expectation_of_recovery' THEN 'writeoff_support_evidence'
                    WHEN evaluated.recovery_label = 'cash_recovery_observed' THEN 'cash_recovery_transaction_evidence'
                    WHEN evaluated.recovery_label = 'cured' THEN 'cure_evidence'
                    ELSE 'not_currently_applicable'
                END::text
            ),
            (
                60,
                'approved_forward_looking_evidence_required'::text,
                'forward_looking_evidence'::text,
                evaluated.approved_forward_looking_evidence_ready,
                'Approved versioned forward-looking economic evidence is required; A2 governance is not installed yet.'::text,
                'forward_looking_governance_not_installed'::text
            )
    ) AS blocker(ordinal, code, evidence_class, is_ready, message, source_status)
    WHERE NOT blocker.is_ready
), aggregated AS (
    SELECT
        evaluated.*,
        coalesce(
            array_agg(blocker.code ORDER BY blocker.ordinal)
                FILTER (WHERE blocker.code IS NOT NULL),
            ARRAY[]::text[]
        ) AS blocker_codes,
        coalesce(
            jsonb_agg(
                jsonb_build_object(
                    'code', blocker.code,
                    'evidence_class', blocker.evidence_class,
                    'message', blocker.message,
                    'source_status', blocker.source_status
                ) ORDER BY blocker.ordinal
            ) FILTER (WHERE blocker.code IS NOT NULL),
            '[]'::jsonb
        ) AS blockers
    FROM evaluated
    LEFT JOIN blocker_rows blocker ON blocker.loan_id = evaluated.loan_id
    GROUP BY
        evaluated.loan_id,
        evaluated.loan_number,
        evaluated.loan_status,
        evaluated.schedule_id,
        evaluated.schedule_version,
        evaluated.contract_reference,
        evaluated.dpd_data_status,
        evaluated.days_past_due,
        evaluated.due_unpaid_amount,
        evaluated.thirty_day_sicr_backstop_reached,
        evaluated.ninety_day_default_backstop_reached,
        evaluated.current_dpd_risk_band,
        evaluated.review_id,
        evaluated.review_version,
        evaluated.stage_label,
        evaluated.default_label,
        evaluated.write_off_label,
        evaluated.recovery_label,
        evaluated.primary_evidence_basis,
        evaluated.evidence_reference,
        evaluated.review_note,
        evaluated.sicr_backstop_rebutted,
        evaluated.default_backstop_rebutted,
        evaluated.rebuttal_evidence_reference,
        evaluated.rebuttal_note,
        evaluated.write_off_evidence_reference,
        evaluated.write_off_note,
        evaluated.recovery_transaction_id,
        evaluated.reviewer_name,
        evaluated.reviewed_at,
        evaluated.current_label_ready,
        evaluated.label_review_status,
        evaluated.quantitative_ecl_ready,
        evaluated.ecl_calculation_enabled,
        evaluated.account_1190_posting_enabled,
        evaluated.automatic_source_posting,
        evaluated.client_id,
        evaluated.loan_type_id,
        evaluated.principal,
        evaluated.date_released,
        evaluated.due_date,
        evaluated.loan_type_code,
        evaluated.loan_type_name,
        evaluated.calculation_mode,
        evaluated.regular_eir_anchor_status,
        evaluated.regular_original_daily_eir,
        evaluated.regular_initial_gross_carrying_amount,
        evaluated.seven_by_seven_eir_anchor_status,
        evaluated.seven_by_seven_original_daily_eir,
        evaluated.seven_by_seven_initial_gross_carrying_amount,
        evaluated.regular_active_source_count,
        evaluated.regular_exact_posted_active_source_count,
        evaluated.regular_voided_posted_source_count,
        evaluated.regular_exact_reversed_voided_source_count,
        evaluated.seven_by_seven_active_source_count,
        evaluated.seven_by_seven_exact_posted_active_source_count,
        evaluated.seven_by_seven_voided_posted_source_count,
        evaluated.seven_by_seven_exact_reversed_voided_source_count,
        evaluated.prior_reviewed_at,
        evaluated.recovery_accepted_at,
        evaluated.recovery_loan_id,
        evaluated.recovery_is_voided,
        evaluated.recovery_amount,
        evaluated.recovery_entry_type,
        evaluated.contractual_schedule_dpd_ready,
        evaluated.current_credit_risk_label_ready,
        evaluated.original_eir_initial_carrying_ready,
        evaluated.protected_collection_posting_reversal_history_ready,
        evaluated.authoritative_current_carrying_ready,
        evaluated.required_loss_recovery_writeoff_outcome_evidence_ready,
        evaluated.approved_forward_looking_evidence_ready
)
SELECT
    loan_id,
    loan_number,
    loan_status,
    loan_type_code,
    loan_type_name,
    calculation_mode,
    schedule_id,
    schedule_version,
    contract_reference,
    dpd_data_status,
    days_past_due,
    current_dpd_risk_band,
    review_id,
    review_version,
    stage_label,
    default_label,
    write_off_label,
    recovery_label,
    label_review_status,
    contractual_schedule_dpd_ready,
    current_credit_risk_label_ready,
    original_eir_initial_carrying_ready,
    protected_collection_posting_reversal_history_ready,
    authoritative_current_carrying_ready,
    required_loss_recovery_writeoff_outcome_evidence_ready,
    approved_forward_looking_evidence_ready,
    blocker_codes,
    blockers,
    cardinality(blocker_codes) = 0 AS quantitative_input_ready,
    NULL::numeric(18,2) AS ecl_amount,
    false AS ecl_calculation_enabled,
    false AS account_1190_posting_enabled,
    false AS automatic_source_posting
FROM aggregated;

CREATE OR REPLACE VIEW accounting.ecl_quantitative_input_readiness_summary AS
SELECT
    count(*)::bigint AS loan_count,
    count(*) FILTER (WHERE quantitative_input_ready)::bigint AS quantitative_input_ready_count,
    count(*) FILTER (
        WHERE blocker_codes @> ARRAY['verified_contractual_schedule_dpd_required']::text[]
    )::bigint AS contractual_schedule_dpd_blocked_count,
    count(*) FILTER (
        WHERE blocker_codes @> ARRAY['current_credit_risk_label_required']::text[]
    )::bigint AS credit_risk_label_blocked_count,
    count(*) FILTER (
        WHERE blocker_codes @> ARRAY['original_eir_initial_carrying_evidence_required']::text[]
    )::bigint AS original_eir_initial_carrying_blocked_count,
    count(*) FILTER (
        WHERE blocker_codes @> ARRAY['protected_collection_posting_reversal_history_required']::text[]
    )::bigint AS protected_history_blocked_count,
    count(*) FILTER (
        WHERE blocker_codes @> ARRAY['authoritative_current_gross_carrying_evidence_required']::text[]
    )::bigint AS current_carrying_blocked_count,
    count(*) FILTER (
        WHERE blocker_codes @> ARRAY['required_loss_recovery_writeoff_outcome_evidence_required']::text[]
    )::bigint AS outcome_evidence_blocked_count,
    count(*) FILTER (
        WHERE blocker_codes @> ARRAY['approved_forward_looking_evidence_required']::text[]
    )::bigint AS forward_looking_evidence_blocked_count,
    false AS quantitative_ecl_ready,
    NULL::numeric(18,2) AS ecl_amount,
    false AS ecl_calculation_enabled,
    false AS account_1190_posting_enabled,
    false AS automatic_source_posting
FROM accounting.ecl_quantitative_input_readiness;

COMMENT ON VIEW accounting.ecl_quantitative_input_readiness IS
    'Master #296 A1 read-only per-loan quantitative-ECL input gate. Blockers are deterministic protected evidence diagnostics only. Typed/free-text notes never substitute for missing accounting evidence. Forward-looking evidence remains blocked until A2 governance is installed. No ECL amount, account 1190 posting, write-off execution, or automatic source posting is enabled.';

COMMENT ON VIEW accounting.ecl_quantitative_input_readiness_summary IS
    'Read-only blocker summary for the Master #296 A1 quantitative-ECL input gate. It never calculates ECL or posts accounting.';

COMMIT;
