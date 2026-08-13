BEGIN;

-- Pre-merge hardening from the disposable PostgreSQL proof:
-- revoking a newer evidence version must never reactivate an older superseded
-- forecast. A later replacement may explicitly supersede the revoked latest
-- version while preserving the immutable chain.

CREATE OR REPLACE FUNCTION accounting.record_ecl_forward_looking_evidence(
    p_evidence_key TEXT,
    p_source_name TEXT,
    p_source_reference TEXT,
    p_observation_period_start DATE,
    p_observation_period_end DATE,
    p_forecast_period_start DATE,
    p_forecast_period_end DATE,
    p_retrieved_at TIMESTAMPTZ,
    p_effective_date DATE,
    p_management_interpretation TEXT,
    p_actor_user_id UUID,
    p_supersedes_evidence_id UUID DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    prior accounting.ecl_forward_looking_evidence%ROWTYPE;
    next_version INTEGER;
    created_id UUID;
BEGIN
    IF p_actor_user_id IS NULL THEN
        RAISE EXCEPTION 'Management actor is required.';
    END IF;
    IF coalesce(btrim(p_evidence_key), '') = '' THEN
        RAISE EXCEPTION 'Evidence key is required.';
    END IF;
    IF coalesce(btrim(p_source_name), '') = ''
       OR coalesce(btrim(p_source_reference), '') = '' THEN
        RAISE EXCEPTION 'Authoritative source name and retained source reference are required.';
    END IF;
    IF length(btrim(coalesce(p_management_interpretation, ''))) < 20 THEN
        RAISE EXCEPTION 'Management interpretation must explain the evidence relevance.';
    END IF;
    IF p_forecast_period_start IS NULL OR p_forecast_period_end IS NULL
       OR p_forecast_period_end < p_forecast_period_start THEN
        RAISE EXCEPTION 'A valid forecast period is required.';
    END IF;
    IF p_retrieved_at IS NULL OR p_effective_date IS NULL THEN
        RAISE EXCEPTION 'Retrieval timestamp and effective date are required.';
    END IF;

    PERFORM 1 FROM core.users WHERE id = p_actor_user_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Management actor does not exist.';
    END IF;

    IF p_supersedes_evidence_id IS NULL THEN
        IF EXISTS (
            SELECT 1
            FROM accounting.ecl_forward_looking_evidence existing
            WHERE existing.evidence_key = p_evidence_key
        ) THEN
            RAISE EXCEPTION 'Existing evidence key requires an explicit supersedes_evidence_id for a new version.';
        END IF;
        next_version := 1;
    ELSE
        SELECT * INTO prior
        FROM accounting.ecl_forward_looking_evidence
        WHERE id = p_supersedes_evidence_id
        FOR SHARE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Superseded evidence version does not exist.';
        END IF;
        IF prior.evidence_key <> p_evidence_key THEN
            RAISE EXCEPTION 'A new evidence version must use the same evidence key as the version it supersedes.';
        END IF;
        IF EXISTS (
            SELECT 1
            FROM accounting.ecl_forward_looking_evidence later
            WHERE later.supersedes_evidence_id = prior.id
        ) THEN
            RAISE EXCEPTION 'The selected evidence version has already been superseded.';
        END IF;
        next_version := prior.version + 1;
    END IF;

    PERFORM set_config(
        'accounting.ecl_forward_looking_evidence_insert_allowed',
        'on',
        true
    );

    INSERT INTO accounting.ecl_forward_looking_evidence (
        evidence_key, version, source_name, source_reference,
        observation_period_start, observation_period_end,
        forecast_period_start, forecast_period_end, retrieved_at,
        effective_date, management_interpretation, approved_by_user_id,
        supersedes_evidence_id
    )
    VALUES (
        p_evidence_key, next_version, p_source_name, p_source_reference,
        p_observation_period_start, p_observation_period_end,
        p_forecast_period_start, p_forecast_period_end, p_retrieved_at,
        p_effective_date, p_management_interpretation, p_actor_user_id,
        p_supersedes_evidence_id
    )
    RETURNING id INTO created_id;

    PERFORM set_config(
        'accounting.ecl_forward_looking_evidence_insert_allowed',
        'off',
        true
    );

    RETURN created_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.revoke_ecl_forward_looking_evidence(
    p_evidence_id UUID,
    p_reason TEXT,
    p_actor_user_id UUID
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    created_id UUID;
BEGIN
    IF p_actor_user_id IS NULL THEN
        RAISE EXCEPTION 'Management actor is required.';
    END IF;
    IF length(btrim(coalesce(p_reason, ''))) < 3 THEN
        RAISE EXCEPTION 'Revocation reason is required.';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM accounting.ecl_forward_looking_evidence WHERE id = p_evidence_id
    ) THEN
        RAISE EXCEPTION 'Forward-looking evidence does not exist.';
    END IF;

    PERFORM set_config(
        'accounting.ecl_forward_looking_evidence_revocation_insert_allowed',
        'on',
        true
    );

    INSERT INTO accounting.ecl_forward_looking_evidence_revocations (
        evidence_id, reason, revoked_by_user_id
    ) VALUES (p_evidence_id, p_reason, p_actor_user_id)
    RETURNING id INTO created_id;

    PERFORM set_config(
        'accounting.ecl_forward_looking_evidence_revocation_insert_allowed',
        'off',
        true
    );

    RETURN created_id;
END;
$$;

CREATE OR REPLACE VIEW accounting.ecl_forward_looking_evidence_status AS
SELECT
    evidence.*,
    revocation.id AS revocation_id,
    revocation.reason AS revocation_reason,
    revocation.revoked_by_user_id,
    revocation.revoked_at,
    EXISTS (
        SELECT 1
        FROM accounting.ecl_forward_looking_evidence later
        WHERE later.supersedes_evidence_id = evidence.id
    ) AS is_superseded,
    CASE
        WHEN revocation.id IS NOT NULL THEN 'revoked'
        WHEN EXISTS (
            SELECT 1
            FROM accounting.ecl_forward_looking_evidence later
            WHERE later.supersedes_evidence_id = evidence.id
        ) THEN 'superseded'
        WHEN current_date < evidence.effective_date THEN 'not_yet_effective'
        WHEN current_date > evidence.forecast_period_end THEN 'stale'
        ELSE 'current'
    END AS evidence_status,
    (
        revocation.id IS NULL
        AND NOT EXISTS (
            SELECT 1
            FROM accounting.ecl_forward_looking_evidence later
            WHERE later.supersedes_evidence_id = evidence.id
        )
        AND current_date >= evidence.effective_date
        AND current_date <= evidence.forecast_period_end
    ) AS ready_for_new_measurement,
    false AS scenario_probability_defaulted,
    false AS multiplier_defaulted,
    false AS management_overlay_defaulted,
    false AS ecl_calculation_enabled,
    false AS account_1190_posting_enabled,
    false AS automatic_source_posting
FROM accounting.ecl_forward_looking_evidence evidence
LEFT JOIN accounting.ecl_forward_looking_evidence_revocations revocation
  ON revocation.evidence_id = evidence.id;

COMMENT ON VIEW accounting.ecl_forward_looking_evidence_status IS
'Revocation never reactivates an older superseded forecast. Only the newest unrevoked, effective, non-stale version without a later version can be ready for a new measurement.';

COMMIT;
