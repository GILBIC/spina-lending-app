BEGIN;

-- Master #296 A3 hardening. Keep 0075's calculation implementation intact,
-- but normalize semantically unordered forward-evidence UUID arrays before the
-- calculation digest is built and make the read-only queue fail closed when a
-- measurement's exact forward evidence later becomes stale/superseded/revoked.

DROP FUNCTION IF EXISTS accounting.record_read_only_quantitative_ecl_measurement_v1_impl(
    UUID, DATE, JSONB, TEXT, UUID
);

ALTER FUNCTION accounting.record_read_only_quantitative_ecl_measurement(
    UUID, DATE, JSONB, TEXT, UUID
) RENAME TO record_read_only_quantitative_ecl_measurement_v1_impl;

CREATE OR REPLACE FUNCTION accounting.record_read_only_quantitative_ecl_measurement(
    p_loan_id UUID,
    p_measurement_date DATE,
    p_scenarios JSONB,
    p_review_rationale TEXT,
    p_actor_user_id UUID
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    normalized_scenarios JSONB;
BEGIN
    IF p_scenarios IS NULL OR jsonb_typeof(p_scenarios) <> 'array' THEN
        -- Preserve the protected implementation's authoritative validation
        -- message rather than guessing a replacement input.
        RETURN accounting.record_read_only_quantitative_ecl_measurement_v1_impl(
            p_loan_id,
            p_measurement_date,
            p_scenarios,
            p_review_rationale,
            p_actor_user_id
        );
    END IF;

    SELECT coalesce(
        jsonb_agg(
            CASE
                WHEN jsonb_typeof(scenario.value) = 'object'
                 AND jsonb_typeof(scenario.value -> 'forward_evidence_ids') = 'array'
                THEN
                    (scenario.value - 'forward_evidence_ids')
                    || jsonb_build_object(
                        'forward_evidence_ids',
                        coalesce(
                            (
                                SELECT jsonb_agg(to_jsonb(evidence_id) ORDER BY evidence_id)
                                FROM (
                                    SELECT DISTINCT raw_id::uuid AS evidence_id
                                    FROM jsonb_array_elements_text(
                                        scenario.value -> 'forward_evidence_ids'
                                    ) AS raw(raw_id)
                                ) normalized_ids
                            ),
                            '[]'::jsonb
                        )
                    )
                ELSE scenario.value
            END
            ORDER BY coalesce(scenario.value ->> 'scenario_key', ''), scenario.ordinality
        ),
        '[]'::jsonb
    )
    INTO normalized_scenarios
    FROM jsonb_array_elements(p_scenarios) WITH ORDINALITY AS scenario(value, ordinality);

    RETURN accounting.record_read_only_quantitative_ecl_measurement_v1_impl(
        p_loan_id,
        p_measurement_date,
        normalized_scenarios,
        p_review_rationale,
        p_actor_user_id
    );
END;
$$;

CREATE OR REPLACE VIEW accounting.ecl_quantitative_measurement_queue AS
WITH latest_today AS (
    SELECT DISTINCT ON (measurement.loan_id)
        measurement.*
    FROM accounting.ecl_quantitative_measurements measurement
    WHERE measurement.measurement_date = current_date
    ORDER BY measurement.loan_id, measurement.measurement_version DESC
), assembled AS (
    SELECT
        readiness.*,
        measurement.id AS measurement_id,
        measurement.measurement_version,
        measurement.measurement_date,
        measurement.loss_horizon,
        measurement.schedule_id AS measured_schedule_id,
        measurement.schedule_version AS measured_schedule_version,
        measurement.label_review_id AS measured_label_review_id,
        measurement.label_review_version AS measured_label_review_version,
        measurement.forward_evidence_ids AS measured_forward_evidence_ids,
        measurement.calculation_digest,
        measurement.ecl_amount AS measured_ecl_amount,
        CASE
            WHEN measurement.id IS NULL THEN false
            ELSE NOT EXISTS (
                SELECT 1
                FROM unnest(measurement.forward_evidence_ids) AS used(evidence_id)
                LEFT JOIN accounting.ecl_forward_looking_evidence_status evidence
                  ON evidence.id = used.evidence_id
                WHERE evidence.id IS NULL
                   OR NOT evidence.ready_for_new_measurement
            )
        END AS measurement_forward_evidence_current
    FROM accounting.ecl_quantitative_input_readiness readiness
    LEFT JOIN latest_today measurement
      ON measurement.loan_id = readiness.loan_id
)
SELECT
    assembled.loan_id,
    assembled.loan_number,
    assembled.loan_status,
    assembled.loan_type_code,
    assembled.loan_type_name,
    assembled.calculation_mode,
    assembled.schedule_id,
    assembled.schedule_version,
    assembled.contract_reference,
    assembled.stage_label,
    assembled.review_id,
    assembled.review_version,
    assembled.blocker_codes,
    assembled.blockers,
    assembled.quantitative_input_ready,
    assembled.measurement_id,
    assembled.measurement_version,
    assembled.measurement_date,
    assembled.loss_horizon,
    assembled.calculation_digest,
    assembled.measurement_forward_evidence_current,
    CASE
        WHEN assembled.quantitative_input_ready = false THEN 'input_blocked'
        WHEN assembled.measurement_id IS NULL THEN 'measurement_required'
        WHEN assembled.measured_schedule_id IS DISTINCT FROM assembled.schedule_id
          OR assembled.measured_schedule_version IS DISTINCT FROM assembled.schedule_version
          OR assembled.measured_label_review_id IS DISTINCT FROM assembled.review_id
          OR assembled.measured_label_review_version IS DISTINCT FROM assembled.review_version
          OR NOT assembled.measurement_forward_evidence_current
            THEN 'new_measurement_required'
        ELSE 'measured_read_only'
    END AS measurement_status,
    CASE
        WHEN assembled.quantitative_input_ready
         AND assembled.measurement_id IS NOT NULL
         AND assembled.measured_schedule_id = assembled.schedule_id
         AND assembled.measured_schedule_version = assembled.schedule_version
         AND assembled.measured_label_review_id = assembled.review_id
         AND assembled.measured_label_review_version = assembled.review_version
         AND assembled.measurement_forward_evidence_current
            THEN assembled.measured_ecl_amount
        ELSE NULL::numeric(18,2)
    END AS authoritative_ecl_amount,
    true AS read_only_ecl_calculation_enabled,
    false AS account_1190_posting_enabled,
    false AS automatic_source_posting
FROM assembled;

CREATE OR REPLACE VIEW accounting.ecl_quantitative_measurement_summary AS
SELECT
    count(*)::bigint AS loan_count,
    count(*) FILTER (WHERE quantitative_input_ready)::bigint AS input_ready_count,
    count(*) FILTER (WHERE measurement_status = 'input_blocked')::bigint AS input_blocked_count,
    count(*) FILTER (WHERE measurement_status = 'measurement_required')::bigint AS measurement_required_count,
    count(*) FILTER (WHERE measurement_status = 'new_measurement_required')::bigint AS new_measurement_required_count,
    count(*) FILTER (WHERE measurement_status = 'measured_read_only')::bigint AS measured_count,
    coalesce(sum(authoritative_ecl_amount), 0)::numeric(18,2) AS authoritative_ecl_total,
    true AS read_only_ecl_calculation_enabled,
    false AS account_1190_posting_enabled,
    false AS automatic_source_posting
FROM accounting.ecl_quantitative_measurement_queue;

COMMENT ON FUNCTION accounting.record_read_only_quantitative_ecl_measurement(
    UUID, DATE, JSONB, TEXT, UUID
) IS
'Protected A3 wrapper that canonicalizes semantically unordered forward-evidence UUID arrays before the immutable calculation digest is produced. No probability or cash-flow input is invented.';

COMMENT ON VIEW accounting.ecl_quantitative_measurement_queue IS
'A3 read-only queue. A used forward-evidence version becoming stale, superseded or revoked makes a current-date measurement non-authoritative and requires a new measurement; blocked loans always expose NULL ECL. Account 1190 and automatic posting remain disabled.';

COMMIT;
