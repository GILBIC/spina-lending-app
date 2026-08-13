BEGIN;

-- Master #296 A2: wire protected current forward-looking evidence into the
-- existing A1 quantitative-input gate without calculating ECL or enabling
-- allowance/source posting. Migration 0072 remains preserved as the A1 base.
--
-- A later version permanently supersedes its predecessor for future readiness.
-- Revoking the later version must NOT reactivate the older forecast.

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
'Revocation never reactivates an older superseded forecast. Only a latest, unrevoked, effective and non-stale version can be ready for a new measurement.';

COMMENT ON VIEW accounting.ecl_forward_looking_evidence_readiness IS
'Master #296 A2 read-only readiness for current Management-approved forward-looking economic evidence. Exact evidence IDs/versions are exposed for later measurement snapshotting; no scenario probability, multiplier or overlay is defaulted.';

COMMENT ON VIEW accounting.ecl_quantitative_input_readiness IS
'Master #296 A1+A2 read-only per-loan quantitative-ECL input gate. Forward-looking readiness is satisfied only by current immutable Management-approved evidence. No ECL amount, account 1190 posting, write-off execution or automatic source posting is enabled.';

COMMIT;
