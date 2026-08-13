BEGIN;

-- Master #296 A2: authoritative, versioned forward-looking economic evidence.
-- This migration is governance/readiness only. It does not calculate ECL,
-- post account 1190, execute a write-off, or enable automatic source posting.

INSERT INTO core.permissions (code, description)
VALUES (
    'accounting.ecl.forward_looking_evidence.manage',
    'Record or revoke immutable Management-approved forward-looking economic evidence for ECL without calculating or posting ECL'
)
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code = 'accounting.ecl.forward_looking_evidence.manage'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.ecl_forward_looking_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_key TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version > 0),
    source_name TEXT NOT NULL CHECK (btrim(source_name) <> ''),
    source_reference TEXT NOT NULL CHECK (btrim(source_reference) <> ''),
    observation_period_start DATE,
    observation_period_end DATE,
    forecast_period_start DATE NOT NULL,
    forecast_period_end DATE NOT NULL,
    retrieved_at TIMESTAMPTZ NOT NULL,
    effective_date DATE NOT NULL,
    management_interpretation TEXT NOT NULL CHECK (
        length(btrim(management_interpretation)) >= 20
    ),
    approved_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    approved_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    supersedes_evidence_id UUID
        REFERENCES accounting.ecl_forward_looking_evidence(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT ecl_forward_looking_evidence_key_version_unique
        UNIQUE (evidence_key, version),
    CONSTRAINT ecl_forward_looking_evidence_key_present
        CHECK (btrim(evidence_key) <> ''),
    CONSTRAINT ecl_forward_looking_evidence_forecast_period_valid
        CHECK (forecast_period_end >= forecast_period_start),
    CONSTRAINT ecl_forward_looking_evidence_observation_period_valid
        CHECK (
            observation_period_start IS NULL
            OR observation_period_end IS NULL
            OR observation_period_end >= observation_period_start
        )
);

CREATE INDEX IF NOT EXISTS ecl_forward_looking_evidence_key_effective_idx
    ON accounting.ecl_forward_looking_evidence
       (evidence_key, effective_date, approved_at DESC);

CREATE TABLE IF NOT EXISTS accounting.ecl_forward_looking_evidence_revocations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_id UUID NOT NULL UNIQUE
        REFERENCES accounting.ecl_forward_looking_evidence(id) ON DELETE RESTRICT,
    reason TEXT NOT NULL CHECK (length(btrim(reason)) >= 3),
    revoked_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    revoked_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE OR REPLACE FUNCTION accounting.guard_ecl_forward_looking_evidence_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(
            current_setting('accounting.ecl_forward_looking_evidence_insert_allowed', true),
            ''
       ) = 'on' THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'ECL forward-looking evidence is immutable and must use the protected Management evidence function.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_ecl_forward_looking_evidence_guard
    ON accounting.ecl_forward_looking_evidence;
CREATE TRIGGER accounting_ecl_forward_looking_evidence_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.ecl_forward_looking_evidence
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_forward_looking_evidence_write();

CREATE OR REPLACE FUNCTION accounting.guard_ecl_forward_looking_evidence_revocation_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(
            current_setting('accounting.ecl_forward_looking_evidence_revocation_insert_allowed', true),
            ''
       ) = 'on' THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'ECL forward-looking evidence revocation is immutable and must use the protected Management revocation function.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_ecl_forward_looking_evidence_revocation_guard
    ON accounting.ecl_forward_looking_evidence_revocations;
CREATE TRIGGER accounting_ecl_forward_looking_evidence_revocation_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.ecl_forward_looking_evidence_revocations
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_forward_looking_evidence_revocation_write();

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
        IF EXISTS (
            SELECT 1
            FROM accounting.ecl_forward_looking_evidence_revocations revocation
            WHERE revocation.evidence_id = prior.id
        ) THEN
            RAISE EXCEPTION 'Revoked evidence cannot be used as the direct superseded version.';
        END IF;
        next_version := prior.version + 1;
    END IF;

    PERFORM set_config(
        'accounting.ecl_forward_looking_evidence_insert_allowed',
        'on',
        true
    );

    INSERT INTO accounting.ecl_forward_looking_evidence (
        evidence_key,
        version,
        source_name,
        source_reference,
        observation_period_start,
        observation_period_end,
        forecast_period_start,
        forecast_period_end,
        retrieved_at,
        effective_date,
        management_interpretation,
        approved_by_user_id,
        supersedes_evidence_id
    )
    VALUES (
        p_evidence_key,
        next_version,
        p_source_name,
        p_source_reference,
        p_observation_period_start,
        p_observation_period_end,
        p_forecast_period_start,
        p_forecast_period_end,
        p_retrieved_at,
        p_effective_date,
        p_management_interpretation,
        p_actor_user_id,
        p_supersedes_evidence_id
    )
    RETURNING id INTO created_id;

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
        evidence_id,
        reason,
        revoked_by_user_id
    )
    VALUES (
        p_evidence_id,
        p_reason,
        p_actor_user_id
    )
    RETURNING id INTO created_id;

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
        LEFT JOIN accounting.ecl_forward_looking_evidence_revocations later_revocation
          ON later_revocation.evidence_id = later.id
        WHERE later.supersedes_evidence_id = evidence.id
          AND later_revocation.id IS NULL
    ) AS is_superseded,
    CASE
        WHEN revocation.id IS NOT NULL THEN 'revoked'
        WHEN EXISTS (
            SELECT 1
            FROM accounting.ecl_forward_looking_evidence later
            LEFT JOIN accounting.ecl_forward_looking_evidence_revocations later_revocation
              ON later_revocation.evidence_id = later.id
            WHERE later.supersedes_evidence_id = evidence.id
              AND later_revocation.id IS NULL
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
            LEFT JOIN accounting.ecl_forward_looking_evidence_revocations later_revocation
              ON later_revocation.evidence_id = later.id
            WHERE later.supersedes_evidence_id = evidence.id
              AND later_revocation.id IS NULL
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

COMMENT ON TABLE accounting.ecl_forward_looking_evidence IS
'Immutable Management-approved forward-looking economic evidence versions for ECL. Later versions supersede only future measurements; prior measurements retain their exact evidence IDs/versions.';

COMMENT ON VIEW accounting.ecl_forward_looking_evidence_status IS
'Read-only current/stale/superseded/revoked status for forward-looking ECL evidence. No scenario probability, multiplier or overlay is invented or defaulted.';

COMMIT;
