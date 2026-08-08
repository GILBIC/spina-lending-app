BEGIN;

-- Stage 5E.3 adds a controlled, audited review workflow for historical
-- credit-loss outcome labels. It does not infer labels from renewal, archive,
-- deletion, cash totals, arrears, or any other reconstructed operational event.

INSERT INTO core.permissions (code, description)
VALUES (
    'accounting.ecl.review',
    'Review and record evidence-backed historical ECL outcome labels without calculating or posting ECL'
)
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code = 'accounting.ecl.review'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.ecl_outcome_label_reviews (
    id BIGSERIAL PRIMARY KEY,
    historical_episode_id BIGINT NOT NULL
        REFERENCES accounting.ecl_historical_loan_episodes(id) ON DELETE RESTRICT,
    review_version INTEGER NOT NULL CHECK (review_version > 0),
    default_label BOOLEAN NOT NULL,
    evidence_basis TEXT NOT NULL CHECK (
        evidence_basis IN (
            'source_document',
            'collection_history',
            'renewal_settlement',
            'management_review'
        )
    ),
    evidence_reference TEXT NOT NULL,
    review_note TEXT NOT NULL,
    reviewer_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    supersedes_review_id BIGINT
        REFERENCES accounting.ecl_outcome_label_reviews(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (historical_episode_id, review_version)
);

CREATE INDEX IF NOT EXISTS ix_ecl_outcome_reviews_episode_created
    ON accounting.ecl_outcome_label_reviews(historical_episode_id, created_at DESC);

CREATE OR REPLACE FUNCTION accounting.guard_ecl_outcome_review_audit()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Historical ECL outcome review records are immutable.';
END;
$$;

DROP TRIGGER IF EXISTS ecl_outcome_review_audit_guard
    ON accounting.ecl_outcome_label_reviews;
CREATE TRIGGER ecl_outcome_review_audit_guard
BEFORE UPDATE OR DELETE ON accounting.ecl_outcome_label_reviews
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_outcome_review_audit();

CREATE OR REPLACE FUNCTION accounting.guard_ecl_explicit_default_label_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF coalesce(
        current_setting('accounting.ecl_review_write_allowed', true),
        ''
    ) <> 'on' THEN
        RAISE EXCEPTION 'Historical ECL outcome labels must use the protected review function.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS ecl_explicit_default_label_write_guard
    ON accounting.ecl_historical_loan_episodes;
CREATE TRIGGER ecl_explicit_default_label_write_guard
BEFORE UPDATE OF explicit_default_label ON accounting.ecl_historical_loan_episodes
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_explicit_default_label_write();

CREATE OR REPLACE FUNCTION accounting.review_ecl_historical_outcome(
    p_historical_episode_id BIGINT,
    p_default_label BOOLEAN,
    p_evidence_basis TEXT,
    p_evidence_reference TEXT,
    p_review_note TEXT,
    p_actor_user_id UUID
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    episode accounting.ecl_historical_loan_episodes%ROWTYPE;
    prior_review_id BIGINT;
    next_version INTEGER;
    new_review_id BIGINT;
    normalized_basis TEXT;
    normalized_reference TEXT;
    normalized_note TEXT;
BEGIN
    normalized_basis := lower(trim(coalesce(p_evidence_basis, '')));
    normalized_reference := trim(coalesce(p_evidence_reference, ''));
    normalized_note := trim(coalesce(p_review_note, ''));

    IF p_historical_episode_id IS NULL THEN
        RAISE EXCEPTION 'Historical episode id is required.';
    END IF;
    IF p_default_label IS NULL THEN
        RAISE EXCEPTION 'A reviewed default/non-default label is required.';
    END IF;
    IF normalized_basis NOT IN (
        'source_document',
        'collection_history',
        'renewal_settlement',
        'management_review'
    ) THEN
        RAISE EXCEPTION 'A supported evidence basis is required.';
    END IF;
    IF normalized_reference = '' THEN
        RAISE EXCEPTION 'Evidence reference is required.';
    END IF;
    IF normalized_note = '' THEN
        RAISE EXCEPTION 'Review note is required.';
    END IF;
    IF p_actor_user_id IS NULL THEN
        RAISE EXCEPTION 'Reviewer user id is required.';
    END IF;

    SELECT *
    INTO episode
    FROM accounting.ecl_historical_loan_episodes
    WHERE id = p_historical_episode_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Historical ECL episode was not found.';
    END IF;

    IF episode.source_quality_status <> 'ready_for_outcome_labeling' THEN
        RAISE EXCEPTION 'Source review must be completed before an ECL outcome label can be recorded.';
    END IF;

    SELECT review.id, review.review_version
    INTO prior_review_id, next_version
    FROM accounting.ecl_outcome_label_reviews review
    WHERE review.historical_episode_id = p_historical_episode_id
    ORDER BY review.review_version DESC
    LIMIT 1;

    next_version := coalesce(next_version, 0) + 1;

    INSERT INTO accounting.ecl_outcome_label_reviews (
        historical_episode_id,
        review_version,
        default_label,
        evidence_basis,
        evidence_reference,
        review_note,
        reviewer_user_id,
        supersedes_review_id
    )
    VALUES (
        p_historical_episode_id,
        next_version,
        p_default_label,
        normalized_basis,
        normalized_reference,
        normalized_note,
        p_actor_user_id,
        prior_review_id
    )
    RETURNING id INTO new_review_id;

    PERFORM set_config('accounting.ecl_review_write_allowed', 'on', true);

    UPDATE accounting.ecl_historical_loan_episodes
    SET explicit_default_label = p_default_label
    WHERE id = p_historical_episode_id;

    RETURN new_review_id;
END;
$$;

CREATE OR REPLACE VIEW accounting.ecl_outcome_label_review_queue AS
WITH latest_review AS (
    SELECT DISTINCT ON (review.historical_episode_id)
        review.historical_episode_id,
        review.id AS review_id,
        review.review_version,
        review.default_label,
        review.evidence_basis,
        review.evidence_reference,
        review.review_note,
        review.reviewer_user_id,
        reviewer.full_name AS reviewer_name,
        review.created_at AS reviewed_at
    FROM accounting.ecl_outcome_label_reviews review
    LEFT JOIN core.users reviewer ON reviewer.id = review.reviewer_user_id
    ORDER BY review.historical_episode_id, review.review_version DESC
)
SELECT
    episode.id AS historical_episode_id,
    episode.import_batch_id,
    episode.episode_key,
    episode.borrower_key,
    episode.episode_sequence,
    episode.loan_type,
    episode.source_event,
    episode.release_date,
    episode.due_date,
    episode.principal,
    episode.contractual_total,
    episode.interest_rate,
    episode.outcome_evidence,
    episode.outcome_date,
    episode.renewal_rollover_amount,
    episode.cash_collected,
    episode.positive_payment_count,
    episode.zero_payment_observation_count,
    episode.observed_collection_days,
    episode.source_quality_status,
    episode.source_quality_note,
    episode.explicit_default_label,
    latest_review.review_id,
    latest_review.review_version,
    latest_review.evidence_basis,
    latest_review.evidence_reference,
    latest_review.review_note,
    latest_review.reviewer_user_id,
    latest_review.reviewer_name,
    latest_review.reviewed_at,
    CASE
        WHEN episode.source_quality_status = 'source_review_required'
            THEN 'source_review_required'
        WHEN episode.explicit_default_label IS NULL
            THEN 'outcome_review_required'
        ELSE 'outcome_reviewed'
    END AS review_status
FROM accounting.ecl_historical_loan_episodes episode
LEFT JOIN latest_review
  ON latest_review.historical_episode_id = episode.id;

CREATE OR REPLACE VIEW accounting.ecl_outcome_label_review_summary AS
SELECT
    count(*)::bigint AS episode_count,
    count(*) FILTER (
        WHERE source_quality_status = 'ready_for_outcome_labeling'
    )::bigint AS structurally_usable_count,
    count(*) FILTER (
        WHERE source_quality_status = 'source_review_required'
    )::bigint AS source_review_required_count,
    count(*) FILTER (
        WHERE source_quality_status = 'ready_for_outcome_labeling'
          AND explicit_default_label IS NULL
    )::bigint AS pending_outcome_review_count,
    count(*) FILTER (
        WHERE explicit_default_label IS NOT NULL
    )::bigint AS reviewed_outcome_count,
    count(*) FILTER (
        WHERE explicit_default_label IS TRUE
    )::bigint AS reviewed_default_count,
    count(*) FILTER (
        WHERE explicit_default_label IS FALSE
    )::bigint AS reviewed_non_default_count,
    CASE
        WHEN count(*) = 0 THEN 'historical_dataset_required'
        WHEN count(*) FILTER (
            WHERE source_quality_status = 'ready_for_outcome_labeling'
        ) = 0 THEN 'historical_source_review_required'
        WHEN count(*) FILTER (
            WHERE source_quality_status = 'ready_for_outcome_labeling'
              AND explicit_default_label IS NULL
        ) > 0
        AND count(*) FILTER (
            WHERE explicit_default_label IS NOT NULL
        ) = 0 THEN 'outcome_labeling_required'
        WHEN count(*) FILTER (
            WHERE source_quality_status = 'ready_for_outcome_labeling'
              AND explicit_default_label IS NULL
        ) > 0 THEN 'outcome_labeling_in_progress'
        WHEN count(*) FILTER (
            WHERE explicit_default_label IS TRUE
        ) = 0 THEN 'default_outcome_data_required'
        WHEN count(*) FILTER (
            WHERE explicit_loss_amount IS NOT NULL
               OR explicit_recovery_amount IS NOT NULL
        ) = 0 THEN 'loss_recovery_labeling_required'
        ELSE 'calibration_methodology_required'
    END AS review_status,
    false AS ecl_included,
    NULL::numeric(18,2) AS ecl_amount,
    false AS ready_to_post
FROM accounting.ecl_historical_loan_episodes;

-- Rebind the Stage 5E.2 dataset status so partial labeling cannot advance the
-- portfolio to calibration readiness. Every structurally usable episode must
-- receive an explicit reviewed outcome before the next ECL stage can proceed.
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
            WHERE episode.source_quality_status = 'ready_for_outcome_labeling'
              AND episode.explicit_default_label IS NULL
        ) > 0
        AND count(episode.id) FILTER (
            WHERE episode.explicit_default_label IS NOT NULL
        ) = 0 THEN 'outcome_labeling_required'
        WHEN count(episode.id) FILTER (
            WHERE episode.source_quality_status = 'ready_for_outcome_labeling'
              AND episode.explicit_default_label IS NULL
        ) > 0 THEN 'outcome_labeling_in_progress'
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

COMMENT ON TABLE accounting.ecl_outcome_label_reviews IS
    'Immutable Stage 5E.3 evidence-backed review history for explicit historical default/non-default labels.';
COMMENT ON VIEW accounting.ecl_outcome_label_review_queue IS
    'Management review queue for Stage 5E.3 historical outcome labeling. No outcome is inferred automatically.';
COMMENT ON VIEW accounting.ecl_outcome_label_review_summary IS
    'Stage 5E.3 review progress. ECL remains unquantified and posting remains disabled.';
COMMENT ON FUNCTION accounting.review_ecl_historical_outcome(BIGINT, BOOLEAN, TEXT, TEXT, TEXT, UUID) IS
    'Protected Stage 5E.3 function for recording an evidence-backed historical default/non-default label with immutable review history.';

COMMIT;
