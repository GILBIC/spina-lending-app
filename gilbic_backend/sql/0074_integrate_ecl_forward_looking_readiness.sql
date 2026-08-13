BEGIN;

-- Master #296 A2: wire protected current forward-looking evidence into the
-- existing A1 quantitative-input gate without calculating ECL or enabling
-- allowance/source posting. Migration 0072 remains preserved as the A1 base.
--
-- Pre-merge disposable proof hardening:
-- * a later version permanently supersedes its predecessor for future readiness;
-- * revoking the later version must NOT reactivate the older forecast;
-- * a replacement may explicitly supersede the revoked latest version;
-- * protected-write GUCs are reset before the function returns.

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
        SELECT 1
        FROM accounting.ecl_forward_looking_evidence
        WHERE id = p_evidence_id
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
    )
    VALUES (p_evidence_id, p_reason, p_actor_user_id)
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

CREATE OR REPLACE VIEW accounting.ecl_forward_looking_evidence_readiness AS
SELECT
    count(*) FILTER (WHERE ready_for_new_measurement)::bigint AS current_evidence_count,
    coalesce(
        array_agg(id ORDER BY evidence_key, version)
            FILTER (WHERE ready_for_new_measurement),
        ARRAY[]::uuid[]
    ) AS current_evidence_ids,
    coalesce(
        jsonb_agg(
            jsonb_build_object(
                'id', id,
                'evidence_key', evidence_key,
                'version', version,
                'source_name', source_name,
                'source_reference', source_reference,
                'forecast_period_start', forecast_period_start,
                'forecast_period_end', forecast_period_end,
                'retrieved_at', retrieved_at,
                'effective_date', effective_date,
                'approved_by_user_id', approved_by_user_id,
                'approved_at', approved_at
            ) ORDER BY evidence_key, version
        ) FILTER (WHERE ready_for_new_measurement),
        '[]'::jsonb
    ) AS current_evidence,
    count(*) FILTER (WHERE evidence_status = 'stale')::bigint AS stale_count,
    count(*) FILTER (WHERE evidence_status = 'superseded')::bigint AS superseded_count,
    count(*) FILTER (WHERE evidence_status = 'revoked')::bigint AS revoked_count,
    count(*) FILTER (WHERE evidence_status = 'not_yet_effective')::bigint AS not_yet_effective_count,
    count(*) FILTER (WHERE evidence_status = 'current')::bigint AS current_status_count,
    count(*) FILTER (WHERE ready_for_new_measurement) > 0 AS approved_forward_looking_evidence_ready,
    false AS scenario_probability_defaulted,
    false AS multiplier_defaulted,
    false AS management_overlay_defaulted,
    false AS ecl_calculation_enabled,
    false AS account_1190_posting_enabled,
    false AS automatic_source_posting
FROM accounting.ecl_forward_looking_evidence_status;

DO $$
BEGIN
    IF to_regclass('accounting.ecl_quantitative_input_readiness_a1_base') IS NULL THEN
        IF to_regclass('accounting.ecl_quantitative_input_readiness') IS NULL THEN
            RAISE EXCEPTION 'A1 quantitative input-readiness view is required before A2 integration.';
        END IF;
        ALTER VIEW accounting.ecl_quantitative_input_readiness
            RENAME TO ecl_quantitative_input_readiness_a1_base;
    END IF;
END;
$$;

CREATE OR REPLACE VIEW accounting.ecl_quantitative_input_readiness AS
WITH forward_readiness AS (
    SELECT *
    FROM accounting.ecl_forward_looking_evidence_readiness
), normalized AS (
    SELECT
        base.*,
        forward_readiness.approved_forward_looking_evidence_ready AS a2_forward_ready,
        forward_readiness.current_evidence_count AS forward_current_evidence_count,
        forward_readiness.current_evidence_ids AS forward_current_evidence_ids,
        coalesce(
            ARRAY(
                SELECT code
                FROM unnest(base.blocker_codes) WITH ORDINALITY AS existing(code, ordinal)
                WHERE code <> 'approved_forward_looking_evidence_required'
                ORDER BY ordinal
            ),
            ARRAY[]::text[]
        ) AS non_forward_blocker_codes,
        coalesce(
            (
                SELECT jsonb_agg(item.value ORDER BY item.ordinality)
                FROM jsonb_array_elements(base.blockers) WITH ORDINALITY AS item(value, ordinality)
                WHERE item.value ->> 'code' <> 'approved_forward_looking_evidence_required'
            ),
            '[]'::jsonb
        ) AS non_forward_blockers
    FROM accounting.ecl_quantitative_input_readiness_a1_base base
    CROSS JOIN forward_readiness
)
SELECT
    normalized.loan_id,
    normalized.loan_number,
    normalized.loan_status,
    normalized.loan_type_code,
    normalized.loan_type_name,
    normalized.calculation_mode,
    normalized.schedule_id,
    normalized.schedule_version,
    normalized.contract_reference,
    normalized.dpd_data_status,
    normalized.days_past_due,
    normalized.current_dpd_risk_band,
    normalized.review_id,
    normalized.review_version,
    normalized.stage_label,
    normalized.default_label,
    normalized.write_off_label,
    normalized.recovery_label,
    normalized.label_review_status,
    normalized.contractual_schedule_dpd_ready,
    normalized.current_credit_risk_label_ready,
    normalized.original_eir_initial_carrying_ready,
    normalized.protected_collection_posting_reversal_history_ready,
    normalized.authoritative_current_carrying_ready,
    normalized.required_loss_recovery_writeoff_outcome_evidence_ready,
    normalized.a2_forward_ready AS approved_forward_looking_evidence_ready,
    CASE
        WHEN normalized.a2_forward_ready THEN normalized.non_forward_blocker_codes
        ELSE normalized.non_forward_blocker_codes
             || ARRAY['approved_forward_looking_evidence_required']::text[]
    END AS blocker_codes,
    CASE
        WHEN normalized.a2_forward_ready THEN normalized.non_forward_blockers
        ELSE normalized.non_forward_blockers || jsonb_build_array(
            jsonb_build_object(
                'code', 'approved_forward_looking_evidence_required',
                'evidence_class', 'forward_looking_evidence',
                'message', 'At least one current immutable Management-approved forward-looking economic evidence version is required for a new quantitative ECL measurement.',
                'source_status', CASE
                    WHEN normalized.forward_current_evidence_count = 0
                        THEN 'no_current_approved_forward_looking_evidence'
                    ELSE 'current_forward_looking_evidence_available'
                END
            )
        )
    END AS blockers,
    cardinality(normalized.non_forward_blocker_codes) = 0
        AND normalized.a2_forward_ready AS quantitative_input_ready,
    NULL::numeric(18,2) AS ecl_amount,
    false AS ecl_calculation_enabled,
    false AS account_1190_posting_enabled,
    false AS automatic_source_posting
FROM normalized;

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

COMMENT ON VIEW accounting.ecl_forward_looking_evidence_status IS
'Revocation never reactivates an older superseded forecast. A replacement may explicitly supersede the revoked latest version while preserving the immutable chain.';

COMMENT ON VIEW accounting.ecl_forward_looking_evidence_readiness IS
'Master #296 A2 read-only readiness for current Management-approved forward-looking economic evidence. Exact evidence IDs/versions are exposed for later measurement snapshotting; no scenario probability, multiplier or overlay is defaulted.';

COMMENT ON VIEW accounting.ecl_quantitative_input_readiness IS
'Master #296 A1+A2 read-only per-loan quantitative-ECL input gate. Forward-looking readiness is satisfied only by current immutable Management-approved evidence. No ECL amount, account 1190 posting, write-off execution or automatic source posting is enabled.';

COMMIT;
