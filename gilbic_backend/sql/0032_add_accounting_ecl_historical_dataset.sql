BEGIN;

-- Stage 5E.2 stores reconstructed legacy loan episodes in an accounting-only
-- historical evidence area. These records are never operational lending rows
-- and they do not change borrower balances, collections, workbook values, ECL,
-- or General Ledger journals.

CREATE TABLE IF NOT EXISTS accounting.ecl_history_import_batches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_filename text NOT NULL,
    source_sha256 text NOT NULL UNIQUE,
    source_size_bytes bigint NOT NULL CHECK (source_size_bytes >= 0),
    sqlite_integrity_check text NOT NULL,
    source_snapshot_date date,
    source_client_count integer NOT NULL DEFAULT 0 CHECK (source_client_count >= 0),
    source_renewal_count integer NOT NULL DEFAULT 0 CHECK (source_renewal_count >= 0),
    source_transaction_count integer NOT NULL DEFAULT 0 CHECK (source_transaction_count >= 0),
    reconstructed_episode_count integer NOT NULL DEFAULT 0 CHECK (reconstructed_episode_count >= 0),
    imported_at timestamptz NOT NULL DEFAULT now(),
    import_note text
);

CREATE TABLE IF NOT EXISTS accounting.ecl_historical_loan_episodes (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    import_batch_id uuid NOT NULL
        REFERENCES accounting.ecl_history_import_batches(id) ON DELETE RESTRICT,
    episode_key text NOT NULL,
    borrower_key text NOT NULL,
    episode_sequence integer NOT NULL CHECK (episode_sequence > 0),
    loan_type text NOT NULL,
    source_event text NOT NULL,
    release_date date,
    due_date date,
    principal numeric(18,2) NOT NULL DEFAULT 0,
    contractual_total numeric(18,2),
    interest_rate numeric(18,8),
    outcome_evidence text NOT NULL CHECK (
        outcome_evidence IN (
            'renewed',
            'archived',
            'archived_at_snapshot',
            'deleted',
            'open_at_snapshot'
        )
    ),
    outcome_date date,
    renewal_rollover_amount numeric(18,2),
    cash_collected numeric(18,2) NOT NULL DEFAULT 0,
    positive_payment_count integer NOT NULL DEFAULT 0 CHECK (positive_payment_count >= 0),
    zero_payment_observation_count integer NOT NULL DEFAULT 0 CHECK (zero_payment_observation_count >= 0),
    observed_collection_days integer NOT NULL DEFAULT 0 CHECK (observed_collection_days >= 0),
    source_quality_status text NOT NULL CHECK (
        source_quality_status IN ('ready_for_outcome_labeling', 'source_review_required')
    ),
    source_quality_note text,
    explicit_default_label boolean,
    explicit_loss_amount numeric(18,2),
    explicit_recovery_amount numeric(18,2),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (import_batch_id, episode_key)
);

CREATE INDEX IF NOT EXISTS ix_ecl_historical_episodes_batch
    ON accounting.ecl_historical_loan_episodes(import_batch_id);
CREATE INDEX IF NOT EXISTS ix_ecl_historical_episodes_borrower
    ON accounting.ecl_historical_loan_episodes(borrower_key, episode_sequence);
CREATE INDEX IF NOT EXISTS ix_ecl_historical_episodes_release
    ON accounting.ecl_historical_loan_episodes(release_date);

CREATE OR REPLACE VIEW accounting.ecl_historical_dataset_summary AS
SELECT
    count(DISTINCT batch.id)::bigint AS import_batch_count,
    count(episode.id)::bigint AS episode_count,
    count(episode.id) FILTER (
        WHERE episode.source_quality_status = 'ready_for_outcome_labeling'
    )::bigint AS usable_episode_count,
    count(episode.id) FILTER (
        WHERE episode.source_quality_status = 'source_review_required'
    )::bigint AS source_review_required_count,
    count(episode.id) FILTER (WHERE episode.outcome_evidence = 'renewed')::bigint
        AS renewed_episode_count,
    count(episode.id) FILTER (
        WHERE episode.outcome_evidence IN ('archived', 'archived_at_snapshot')
    )::bigint AS archived_episode_count,
    count(episode.id) FILTER (WHERE episode.outcome_evidence = 'deleted')::bigint
        AS deleted_episode_count,
    count(episode.id) FILTER (WHERE episode.outcome_evidence = 'open_at_snapshot')::bigint
        AS open_episode_count,
    count(episode.id) FILTER (WHERE episode.explicit_default_label IS NOT NULL)::bigint
        AS explicitly_labeled_outcome_count,
    count(episode.id) FILTER (WHERE episode.explicit_default_label IS TRUE)::bigint
        AS explicitly_defaulted_episode_count,
    coalesce(sum(episode.principal), 0)::numeric(18,2) AS reconstructed_principal,
    coalesce(sum(episode.cash_collected), 0)::numeric(18,2) AS observed_cash_collected,
    min(episode.release_date) AS earliest_episode_release,
    max(episode.release_date) AS latest_episode_release,
    max(batch.source_snapshot_date) AS latest_source_snapshot,
    CASE
        WHEN count(episode.id) = 0 THEN 'historical_dataset_required'
        WHEN count(episode.id) FILTER (
            WHERE episode.source_quality_status = 'ready_for_outcome_labeling'
        ) = 0 THEN 'historical_source_review_required'
        WHEN count(episode.id) FILTER (
            WHERE episode.explicit_default_label IS NOT NULL
        ) = 0 THEN 'outcome_labeling_required'
        WHEN count(episode.id) FILTER (
            WHERE episode.explicit_default_label IS TRUE
        ) = 0 THEN 'default_outcome_data_required'
        WHEN count(episode.id) FILTER (
            WHERE episode.explicit_loss_amount IS NOT NULL
               OR episode.explicit_recovery_amount IS NOT NULL
        ) = 0 THEN 'loss_recovery_labeling_required'
        ELSE 'calibration_methodology_required'
    END AS historical_dataset_status,
    false AS ecl_included,
    NULL::numeric(18,2) AS ecl_amount,
    false AS ready_to_post
FROM accounting.ecl_history_import_batches batch
LEFT JOIN accounting.ecl_historical_loan_episodes episode
    ON episode.import_batch_id = batch.id;

-- Stage 5E.2 replaces the generic 1190 calibration-source status only when a
-- historical import exists. It still refuses to quantify ECL until explicit
-- outcomes, losses/recoveries, and an approved methodology exist.
CREATE OR REPLACE VIEW accounting.opening_balance_measurement_reference AS
WITH measurement AS (
    SELECT * FROM accounting.loan_measurement_summary
), ecl AS (
    SELECT * FROM accounting.ecl_assessment_summary
), calibration AS (
    SELECT * FROM accounting.ecl_calibration_source_inventory
), historical AS (
    SELECT * FROM accounting.ecl_historical_dataset_summary
)
SELECT
    '1100'::text AS account_code,
    CASE WHEN measurement.measurement_status = 'measured'
        THEN measurement.regular_loan_component ELSE NULL END,
    measurement.measurement_status,
    'Regular accounting loan component after daily EIR accrual and actual cash allocation. This is a cutover measurement reference, not an automatic workbook entry.'::text
FROM measurement
UNION ALL
SELECT
    '1110',
    CASE WHEN measurement.measurement_status = 'measured'
        THEN measurement.seven_by_seven_loan_component ELSE NULL END,
    measurement.measurement_status,
    '7x7 accounting loan component. Current base measurement is allowed only when no pre-cutover 7x7 cash flow requires principal/prepayment modification review.'
FROM measurement
UNION ALL
SELECT
    '1120',
    CASE WHEN measurement.measurement_status = 'measured'
        THEN measurement.accrued_interest_component ELSE NULL END,
    measurement.measurement_status,
    'Accrued effective-interest component across measured Regular and 7x7 loans. ECL remains separate and is not included.'
FROM measurement
UNION ALL
SELECT
    '1190',
    NULL::numeric,
    CASE
        WHEN historical.import_batch_count > 0 THEN historical.historical_dataset_status
        ELSE calibration.calibration_readiness_status
    END,
    CASE
        WHEN historical.import_batch_count > 0 THEN
            (
                'Stage 5E.2 historical reconstruction: '
                || historical.episode_count || ' loan episodes reconstructed; '
                || historical.usable_episode_count || ' are structurally usable and '
                || historical.source_review_required_count || ' require source review. '
                || historical.renewed_episode_count || ' ended with renewal evidence, '
                || historical.archived_episode_count || ' have archive evidence, and '
                || historical.deleted_episode_count || ' were deleted. '
                || 'These operational events are not treated as paid/default/loss labels. '
                || historical.explicitly_labeled_outcome_count || ' episodes currently have explicit credit-loss outcome labels. '
                || 'No PD, LGD, cure rate, recovery rate, forward-looking adjustment or ECL amount is inferred.'
            )::text
        ELSE
            (
                'Stage 5E.1 ECL calibration readiness: current database has '
                || calibration.total_loan_count || ' total loans, '
                || calibration.active_loan_count || ' active, '
                || calibration.resolved_loan_count || ' resolved (paid/closed), and '
                || calibration.defaulted_loan_count || ' defaulted. '
                || 'Historical outcome/recovery data and an approved impairment methodology are required before account 1190 can be quantified.'
            )::text
    END
FROM ecl
CROSS JOIN calibration
CROSS JOIN historical;

COMMENT ON TABLE accounting.ecl_history_import_batches IS
    'Immutable source inventory for Stage 5E.2 legacy ECL-history reconstruction. Does not change operational lending data.';
COMMENT ON TABLE accounting.ecl_historical_loan_episodes IS
    'Reconstructed legacy loan episodes for later reviewed ECL calibration. Renewal/archive/delete are evidence events, not inferred default or loss labels.';
COMMENT ON VIEW accounting.ecl_historical_dataset_summary IS
    'Stage 5E.2 readiness summary. ECL remains unquantified and posting remains disabled.';

COMMIT;
