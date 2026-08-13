BEGIN;

-- Master #296 A2: authoritative, versioned forward-looking economic evidence.
-- This migration is governance/readiness only. It does not calculate ECL,
-- post account 1190, execute a write-off, or enable automatic source posting.

CREATE TABLE IF NOT EXISTS accounting.ecl_forward_looking_evidence (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_key text NOT NULL,
    version integer NOT NULL,
    source_name text NOT NULL,
    source_reference text NOT NULL,
    observation_period_start date,
    observation_period_end date,
    forecast_period_start date NOT NULL,
    forecast_period_end date NOT NULL,
    retrieved_at timestamptz NOT NULL,
    effective_date date NOT NULL,
    management_interpretation text NOT NULL,
    approved_by_user_id uuid NOT NULL,
    approved_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    supersedes_evidence_id uuid REFERENCES accounting.ecl_forward_looking_evidence(id),
    revoked_at timestamptz,
    revoked_by_user_id uuid,
    revocation_reason text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT ecl_forward_looking_evidence_key_version_unique
        UNIQUE (evidence_key, version),
    CONSTRAINT ecl_forward_looking_evidence_version_positive
        CHECK (version > 0),
    CONSTRAINT ecl_forward_looking_evidence_source_name_present
        CHECK (btrim(source_name) <> ''),
    CONSTRAINT ecl_forward_looking_evidence_source_reference_present
        CHECK (btrim(source_reference) <> ''),
    CONSTRAINT ecl_forward_looking_evidence_interpretation_present
        CHECK (btrim(management_interpretation) <> ''),
    CONSTRAINT ecl_forward_looking_evidence_forecast_period_valid
        CHECK (forecast_period_end >= forecast_period_start),
    CONSTRAINT ecl_forward_looking_evidence_observation_period_valid
        CHECK (
            observation_period_start IS NULL
            OR observation_period_end IS NULL
            OR observation_period_end >= observation_period_start
        ),
    CONSTRAINT ecl_forward_looking_evidence_revocation_complete
        CHECK (
            (revoked_at IS NULL AND revoked_by_user_id IS NULL AND revocation_reason IS NULL)
            OR (
                revoked_at IS NOT NULL
                AND revoked_by_user_id IS NOT NULL
                AND btrim(coalesce(revocation_reason, '')) <> ''
            )
        )
);

CREATE INDEX IF NOT EXISTS ecl_forward_looking_evidence_key_effective_idx
    ON accounting.ecl_forward_looking_evidence (evidence_key, effective_date, approved_at);

CREATE OR REPLACE FUNCTION accounting.guard_ecl_forward_looking_evidence_immutable()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'ECL forward-looking evidence is immutable; create a new version instead.';
END;
$$;

DROP TRIGGER IF EXISTS trg_ecl_forward_looking_evidence_immutable
    ON accounting.ecl_forward_looking_evidence;
CREATE TRIGGER trg_ecl_forward_looking_evidence_immutable
BEFORE UPDATE OR DELETE ON accounting.ecl_forward_looking_evidence
FOR EACH ROW
EXECUTE FUNCTION accounting.guard_ecl_forward_looking_evidence_immutable();

CREATE OR REPLACE VIEW accounting.ecl_forward_looking_evidence_status AS
WITH ranked AS (
    SELECT
        evidence.*,
        EXISTS (
            SELECT 1
            FROM accounting.ecl_forward_looking_evidence later
            WHERE later.supersedes_evidence_id = evidence.id
              AND later.revoked_at IS NULL
        ) AS is_superseded
    FROM accounting.ecl_forward_looking_evidence evidence
)
SELECT
    ranked.*,
    CASE
        WHEN ranked.revoked_at IS NOT NULL THEN 'revoked'
        WHEN ranked.is_superseded THEN 'superseded'
        WHEN current_date < ranked.effective_date THEN 'not_yet_effective'
        WHEN current_date > ranked.forecast_period_end THEN 'stale'
        ELSE 'current'
    END AS evidence_status,
    (
        ranked.revoked_at IS NULL
        AND NOT ranked.is_superseded
        AND current_date >= ranked.effective_date
        AND current_date <= ranked.forecast_period_end
    ) AS ready_for_new_measurement
FROM ranked;

COMMENT ON TABLE accounting.ecl_forward_looking_evidence IS
'Immutable Management-approved forward-looking economic evidence versions for ECL. Later versions supersede only future measurements; prior measurements must retain exact evidence IDs/versions.';

COMMENT ON VIEW accounting.ecl_forward_looking_evidence_status IS
'Read-only current/stale/superseded/revoked status for forward-looking ECL evidence. No scenario probability, multiplier or overlay is implied or defaulted by this view.';

COMMIT;
