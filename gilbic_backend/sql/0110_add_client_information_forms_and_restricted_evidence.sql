BEGIN;

INSERT INTO core.permissions (code, description)
VALUES
    ('cif.view', 'View ordinary Client Information Form versions and status'),
    ('cif.prepare', 'Create and edit draft Client Information Forms'),
    ('cif.verify', 'Verify frozen Client Information Form source data'),
    ('cif.approve', 'Activate a verified Client Information Form'),
    ('cif.reverification.manage', 'Open and resolve Client Information Form re-verification requirements'),
    ('identity_evidence.view', 'View restricted identity and residence verification metadata for an approved purpose'),
    ('identity_evidence.record', 'Record restricted identity and residence verification metadata'),
    ('identity_evidence.review', 'Review restricted identity and residence verification metadata')
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM (VALUES
    ('employee', 'cif.view'),
    ('employee', 'cif.prepare'),
    ('management', 'cif.view'),
    ('management', 'cif.prepare'),
    ('management', 'cif.verify'),
    ('management', 'cif.approve'),
    ('management', 'cif.reverification.manage'),
    ('management', 'identity_evidence.view'),
    ('management', 'identity_evidence.record'),
    ('management', 'identity_evidence.review')
) AS mapping(role_code, permission_code)
JOIN core.roles role ON role.code = mapping.role_code
JOIN core.permissions permission ON permission.code = mapping.permission_code
ON CONFLICT DO NOTHING;

CREATE SEQUENCE IF NOT EXISTS lending.client_information_form_number_seq
    AS BIGINT
    START WITH 1
    INCREMENT BY 1
    NO CYCLE;

CREATE TABLE IF NOT EXISTS lending.client_information_forms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cif_number TEXT NOT NULL DEFAULT (
        'CIF-' || lpad(
            nextval('lending.client_information_form_number_seq')::TEXT,
            10,
            '0'
        )
    ),
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    form_version INTEGER NOT NULL CHECK (form_version > 0),
    lifecycle_state TEXT NOT NULL DEFAULT 'draft'
        CHECK (lifecycle_state IN ('draft', 'active', 'superseded')),
    effective_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    supersedes_cif_id UUID
        REFERENCES lending.client_information_forms(id) ON DELETE RESTRICT,

    legal_full_name TEXT NOT NULL CHECK (btrim(legal_full_name) <> ''),
    birth_date DATE,
    place_of_birth TEXT NOT NULL DEFAULT '',
    nationality TEXT NOT NULL DEFAULT '',
    civil_status TEXT NOT NULL DEFAULT '',
    phone_number TEXT NOT NULL DEFAULT '',
    email TEXT,
    present_address JSONB NOT NULL DEFAULT '{}'::JSONB
        CHECK (jsonb_typeof(present_address) = 'object'),
    permanent_address JSONB NOT NULL DEFAULT '{}'::JSONB
        CHECK (jsonb_typeof(permanent_address) = 'object'),
    same_as_present_address BOOLEAN NOT NULL DEFAULT false,
    livelihood_profile JSONB NOT NULL DEFAULT '{}'::JSONB
        CHECK (jsonb_typeof(livelihood_profile) = 'object'),

    privacy_notice_version TEXT NOT NULL DEFAULT '',
    privacy_acknowledged_at TIMESTAMPTZ,
    client_signature_reference TEXT NOT NULL DEFAULT '',
    client_signature_digest CHAR(64),

    prepared_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    verified_by_user_id UUID
        REFERENCES core.users(id) ON DELETE RESTRICT,
    verified_at TIMESTAMPTZ,
    verification_note TEXT NOT NULL DEFAULT '',
    approved_by_user_id UUID
        REFERENCES core.users(id) ON DELETE RESTRICT,
    approved_at TIMESTAMPTZ,
    approval_note TEXT NOT NULL DEFAULT '',

    form_schema_version TEXT NOT NULL DEFAULT '1'
        CHECK (btrim(form_schema_version) <> ''),
    source_digest CHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (cif_number),
    UNIQUE (client_id, form_version),
    CHECK (supersedes_cif_id IS NULL OR supersedes_cif_id <> id),
    CHECK (
        client_signature_digest IS NULL
        OR client_signature_digest ~ '^[0-9a-f]{64}$'
    ),
    CHECK (source_digest IS NULL OR source_digest ~ '^[0-9a-f]{64}$'),
    CHECK (
        (
            verified_by_user_id IS NULL
            AND verified_at IS NULL
            AND source_digest IS NULL
            AND verification_note = ''
        )
        OR
        (
            verified_by_user_id IS NOT NULL
            AND verified_at IS NOT NULL
            AND source_digest IS NOT NULL
            AND btrim(verification_note) <> ''
        )
    ),
    CHECK (
        approved_by_user_id IS NULL
        OR verified_by_user_id IS NULL
        OR approved_by_user_id <> verified_by_user_id
    ),
    CHECK (
        (
            lifecycle_state = 'draft'
            AND effective_at IS NULL
            AND expires_at IS NULL
            AND approved_by_user_id IS NULL
            AND approved_at IS NULL
            AND approval_note = ''
        )
        OR
        (
            lifecycle_state IN ('active', 'superseded')
            AND effective_at IS NOT NULL
            AND expires_at = effective_at + INTERVAL '5 years'
            AND verified_by_user_id IS NOT NULL
            AND verified_at IS NOT NULL
            AND approved_by_user_id IS NOT NULL
            AND approved_at IS NOT NULL
            AND btrim(approval_note) <> ''
            AND source_digest IS NOT NULL
            AND birth_date IS NOT NULL
            AND btrim(nationality) <> ''
            AND btrim(phone_number) <> ''
            AND present_address <> '{}'::JSONB
            AND permanent_address <> '{}'::JSONB
            AND livelihood_profile <> '{}'::JSONB
            AND btrim(privacy_notice_version) <> ''
            AND privacy_acknowledged_at IS NOT NULL
            AND btrim(client_signature_reference) <> ''
            AND client_signature_digest IS NOT NULL
        )
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS lending_client_information_forms_one_active_uidx
    ON lending.client_information_forms(client_id)
    WHERE lifecycle_state = 'active';

CREATE UNIQUE INDEX IF NOT EXISTS lending_client_information_forms_one_draft_uidx
    ON lending.client_information_forms(client_id)
    WHERE lifecycle_state = 'draft';

CREATE INDEX IF NOT EXISTS lending_client_information_forms_client_version_idx
    ON lending.client_information_forms(client_id, form_version DESC);

CREATE INDEX IF NOT EXISTS lending_client_information_forms_expiry_idx
    ON lending.client_information_forms(expires_at)
    WHERE lifecycle_state = 'active';

CREATE OR REPLACE FUNCTION lending.guard_client_information_form()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, lending, core
AS $$
DECLARE
    related_client_id UUID;
    old_source JSONB;
    new_source JSONB;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'CIF records cannot be deleted.';
    END IF;

    IF NEW.supersedes_cif_id IS NOT NULL THEN
        SELECT prior.client_id
        INTO related_client_id
        FROM lending.client_information_forms prior
        WHERE prior.id = NEW.supersedes_cif_id;

        IF NOT FOUND OR related_client_id <> NEW.client_id THEN
            RAISE EXCEPTION 'Superseded CIF must belong to the same client.';
        END IF;
    END IF;

    IF TG_OP = 'INSERT' THEN
        RETURN NEW;
    END IF;

    NEW.updated_at := now();

    IF NEW.id <> OLD.id
       OR NEW.cif_number <> OLD.cif_number
       OR NEW.client_id <> OLD.client_id
       OR NEW.form_version <> OLD.form_version
       OR NEW.prepared_by_user_id <> OLD.prepared_by_user_id
       OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION 'CIF identity coordinates are immutable.';
    END IF;

    IF OLD.lifecycle_state IN ('active', 'superseded') THEN
        IF OLD.lifecycle_state = 'active'
           AND NEW.lifecycle_state = 'superseded'
           AND (
               to_jsonb(NEW) - ARRAY['lifecycle_state', 'updated_at']
           ) = (
               to_jsonb(OLD) - ARRAY['lifecycle_state', 'updated_at']
           ) THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'Activated CIF content is immutable.';
    END IF;

    IF OLD.lifecycle_state <> 'draft' THEN
        RAISE EXCEPTION 'Unsupported CIF lifecycle transition.';
    END IF;

    old_source := to_jsonb(OLD) - ARRAY[
        'lifecycle_state',
        'effective_at',
        'expires_at',
        'verified_by_user_id',
        'verified_at',
        'verification_note',
        'approved_by_user_id',
        'approved_at',
        'approval_note',
        'source_digest',
        'updated_at'
    ];
    new_source := to_jsonb(NEW) - ARRAY[
        'lifecycle_state',
        'effective_at',
        'expires_at',
        'verified_by_user_id',
        'verified_at',
        'verification_note',
        'approved_by_user_id',
        'approved_at',
        'approval_note',
        'source_digest',
        'updated_at'
    ];

    IF NEW.lifecycle_state = 'draft' THEN
        IF old_source IS DISTINCT FROM new_source
           AND (
               NEW.verified_by_user_id IS NOT NULL
               OR NEW.verified_at IS NOT NULL
               OR NEW.source_digest IS NOT NULL
               OR NEW.verification_note <> ''
           ) THEN
            RAISE EXCEPTION 'Editing CIF source data requires verification to be cleared.';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.lifecycle_state = 'active' THEN
        IF old_source IS DISTINCT FROM new_source THEN
            RAISE EXCEPTION 'A verified CIF cannot change while it is being activated.';
        END IF;
        IF NEW.verified_by_user_id IS NULL
           OR NEW.approved_by_user_id IS NULL
           OR NEW.verified_by_user_id = NEW.approved_by_user_id THEN
            RAISE EXCEPTION 'CIF activation requires different verifier and approver users.';
        END IF;
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'Unsupported CIF lifecycle transition.';
END;
$$;

DROP TRIGGER IF EXISTS lending_client_information_form_guard
    ON lending.client_information_forms;
CREATE TRIGGER lending_client_information_form_guard
BEFORE INSERT OR UPDATE OR DELETE ON lending.client_information_forms
FOR EACH ROW EXECUTE FUNCTION lending.guard_client_information_form();

CREATE TABLE IF NOT EXISTS lending.client_cif_reverification_requirements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    source_cif_id UUID
        REFERENCES lending.client_information_forms(id) ON DELETE RESTRICT,
    reason TEXT NOT NULL CHECK (
        reason IN (
            'material_identity_change',
            'address_change',
            'contact_change',
            'document_expiry',
            'discrepancy',
            'suspicious_activity',
            'approved_risk_event'
        )
    ),
    severity TEXT NOT NULL DEFAULT 'standard'
        CHECK (severity IN ('standard', 'high')),
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'resolved')),
    note TEXT NOT NULL CHECK (btrim(note) <> ''),
    opened_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_by_user_id UUID
        REFERENCES core.users(id) ON DELETE RESTRICT,
    resolved_at TIMESTAMPTZ,
    resolution_cif_id UUID
        REFERENCES lending.client_information_forms(id) ON DELETE RESTRICT,
    resolution_note TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (
            status = 'open'
            AND resolved_by_user_id IS NULL
            AND resolved_at IS NULL
            AND resolution_cif_id IS NULL
            AND resolution_note = ''
        )
        OR
        (
            status = 'resolved'
            AND resolved_by_user_id IS NOT NULL
            AND resolved_at IS NOT NULL
            AND resolution_cif_id IS NOT NULL
            AND btrim(resolution_note) <> ''
        )
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS lending_cif_reverification_one_open_reason_uidx
    ON lending.client_cif_reverification_requirements(client_id, reason)
    WHERE status = 'open';

CREATE INDEX IF NOT EXISTS lending_cif_reverification_client_status_idx
    ON lending.client_cif_reverification_requirements(client_id, status, opened_at DESC);

CREATE OR REPLACE FUNCTION lending.guard_cif_reverification_requirement()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, lending, core
AS $$
DECLARE
    related_client_id UUID;
    related_state TEXT;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'CIF re-verification requirements cannot be deleted.';
    END IF;

    IF NEW.source_cif_id IS NOT NULL THEN
        SELECT cif.client_id
        INTO related_client_id
        FROM lending.client_information_forms cif
        WHERE cif.id = NEW.source_cif_id;
        IF NOT FOUND OR related_client_id <> NEW.client_id THEN
            RAISE EXCEPTION 'Source CIF must belong to the same client.';
        END IF;
    END IF;

    IF NEW.resolution_cif_id IS NOT NULL THEN
        SELECT cif.client_id, cif.lifecycle_state
        INTO related_client_id, related_state
        FROM lending.client_information_forms cif
        WHERE cif.id = NEW.resolution_cif_id;
        IF NOT FOUND OR related_client_id <> NEW.client_id THEN
            RAISE EXCEPTION 'Resolution CIF must belong to the same client.';
        END IF;
        IF related_state <> 'active' THEN
            RAISE EXCEPTION 'Resolution CIF must be active.';
        END IF;
    END IF;

    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'open' THEN
            RAISE EXCEPTION 'A CIF re-verification requirement must start open.';
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.status = 'open'
       AND NEW.status = 'resolved'
       AND (
           to_jsonb(NEW) - ARRAY[
               'status',
               'resolved_by_user_id',
               'resolved_at',
               'resolution_cif_id',
               'resolution_note'
           ]
       ) = (
           to_jsonb(OLD) - ARRAY[
               'status',
               'resolved_by_user_id',
               'resolved_at',
               'resolution_cif_id',
               'resolution_note'
           ]
       ) THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'CIF re-verification requirements are append-only except open-to-resolved transition.';
END;
$$;

DROP TRIGGER IF EXISTS lending_cif_reverification_requirement_guard
    ON lending.client_cif_reverification_requirements;
CREATE TRIGGER lending_cif_reverification_requirement_guard
BEFORE INSERT OR UPDATE OR DELETE ON lending.client_cif_reverification_requirements
FOR EACH ROW EXECUTE FUNCTION lending.guard_cif_reverification_requirement();

CREATE OR REPLACE VIEW lending.client_information_form_status AS
SELECT
    cif.id,
    cif.cif_number,
    cif.client_id,
    cif.form_version,
    cif.lifecycle_state,
    cif.effective_at,
    cif.expires_at,
    cif.supersedes_cif_id,
    cif.legal_full_name,
    cif.birth_date,
    cif.place_of_birth,
    cif.nationality,
    cif.civil_status,
    cif.phone_number,
    cif.email,
    cif.present_address,
    cif.permanent_address,
    cif.same_as_present_address,
    cif.livelihood_profile,
    cif.privacy_notice_version,
    cif.privacy_acknowledged_at,
    cif.client_signature_reference,
    cif.client_signature_digest,
    cif.prepared_by_user_id,
    cif.verified_by_user_id,
    cif.verified_at,
    cif.approved_by_user_id,
    cif.approved_at,
    cif.form_schema_version,
    cif.source_digest,
    cif.created_at,
    cif.updated_at,
    CASE
        WHEN cif.lifecycle_state = 'draft' THEN 'Draft'
        WHEN cif.lifecycle_state = 'superseded' THEN 'Superseded'
        WHEN current_timestamp < cif.effective_at THEN 'Draft'
        WHEN current_timestamp >= cif.expires_at THEN 'Expired'
        WHEN current_timestamp >= cif.expires_at - INTERVAL '90 days' THEN 'Expiring'
        ELSE 'Active'
    END AS public_status,
    EXISTS (
        SELECT 1
        FROM lending.client_cif_reverification_requirements requirement
        WHERE requirement.client_id = cif.client_id
          AND requirement.status = 'open'
    ) AS has_open_reverification,
    (
        cif.lifecycle_state = 'active'
        AND current_timestamp >= cif.effective_at
        AND current_timestamp < cif.expires_at
        AND NOT EXISTS (
            SELECT 1
            FROM lending.client_cif_reverification_requirements requirement
            WHERE requirement.client_id = cif.client_id
              AND requirement.status = 'open'
        )
    ) AS is_eligible_for_new_credit
FROM lending.client_information_forms cif;

CREATE SCHEMA IF NOT EXISTS restricted_identity;
REVOKE ALL ON SCHEMA restricted_identity FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA restricted_identity FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA restricted_identity FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA restricted_identity FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA restricted_identity REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA restricted_identity REVOKE ALL ON SEQUENCES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA restricted_identity REVOKE ALL ON FUNCTIONS FROM PUBLIC;

CREATE TABLE IF NOT EXISTS restricted_identity.cif_verification_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    cif_id UUID NOT NULL
        REFERENCES lending.client_information_forms(id) ON DELETE RESTRICT,
    evidence_type TEXT NOT NULL CHECK (
        evidence_type IN (
            'national_id_check',
            'government_id_metadata',
            'utility_proof',
            'residence_visit',
            'approved_exception'
        )
    ),
    verification_method TEXT NOT NULL CHECK (btrim(verification_method) <> ''),
    verification_outcome TEXT NOT NULL CHECK (
        verification_outcome IN (
            'verified',
            'not_verified',
            'inconclusive',
            'exception_approved'
        )
    ),
    checked_at TIMESTAMPTZ NOT NULL,
    document_date DATE,
    document_expires_at DATE,
    masked_reference TEXT NOT NULL CHECK (
        btrim(masked_reference) <> ''
        AND length(masked_reference) <= 120
        AND masked_reference !~ '[0-9]{6,}'
        AND masked_reference !~ '[[:cntrl:]]'
    ),
    external_evidence_reference TEXT NOT NULL CHECK (
        btrim(external_evidence_reference) <> ''
        AND length(external_evidence_reference) <= 500
    ),
    evidence_digest CHAR(64) NOT NULL
        CHECK (evidence_digest ~ '^[0-9a-f]{64}$'),
    retention_class TEXT NOT NULL CHECK (
        retention_class IN (
            'identity_verification',
            'residence_verification',
            'approved_exception'
        )
    ),
    retain_until DATE NOT NULL,
    legal_hold BOOLEAN NOT NULL DEFAULT false,
    recorded_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    supersedes_evidence_id UUID
        REFERENCES restricted_identity.cif_verification_evidence(id)
        ON DELETE RESTRICT,
    CHECK (supersedes_evidence_id IS NULL OR supersedes_evidence_id <> id),
    CHECK (
        document_expires_at IS NULL
        OR document_date IS NULL
        OR document_expires_at >= document_date
    ),
    CHECK (retain_until >= checked_at::DATE)
);

CREATE INDEX IF NOT EXISTS restricted_identity_evidence_cif_recorded_idx
    ON restricted_identity.cif_verification_evidence(cif_id, recorded_at DESC);

CREATE INDEX IF NOT EXISTS restricted_identity_evidence_client_type_idx
    ON restricted_identity.cif_verification_evidence(client_id, evidence_type, recorded_at DESC);

CREATE OR REPLACE FUNCTION restricted_identity.guard_restricted_evidence()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, restricted_identity, lending, core
AS $$
DECLARE
    cif_client_id UUID;
    prior_client_id UUID;
    prior_cif_id UUID;
BEGIN
    IF TG_OP = 'UPDATE' OR TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Restricted evidence records are append-only.';
    END IF;

    SELECT cif.client_id
    INTO cif_client_id
    FROM lending.client_information_forms cif
    WHERE cif.id = NEW.cif_id;

    IF NOT FOUND OR cif_client_id <> NEW.client_id THEN
        RAISE EXCEPTION 'Restricted evidence client and CIF must match.';
    END IF;

    IF NEW.supersedes_evidence_id IS NOT NULL THEN
        SELECT prior.client_id, prior.cif_id
        INTO prior_client_id, prior_cif_id
        FROM restricted_identity.cif_verification_evidence prior
        WHERE prior.id = NEW.supersedes_evidence_id;

        IF NOT FOUND
           OR prior_client_id <> NEW.client_id
           OR prior_cif_id <> NEW.cif_id THEN
            RAISE EXCEPTION 'Superseded evidence must belong to the same client and CIF.';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS restricted_identity_evidence_guard
    ON restricted_identity.cif_verification_evidence;
CREATE TRIGGER restricted_identity_evidence_guard
BEFORE INSERT OR UPDATE OR DELETE ON restricted_identity.cif_verification_evidence
FOR EACH ROW EXECUTE FUNCTION restricted_identity.guard_restricted_evidence();

CREATE TABLE IF NOT EXISTS restricted_identity.cif_verification_evidence_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_id UUID NOT NULL UNIQUE
        REFERENCES restricted_identity.cif_verification_evidence(id)
        ON DELETE RESTRICT,
    review_decision TEXT NOT NULL
        CHECK (review_decision IN ('approved', 'rejected')),
    review_note TEXT NOT NULL CHECK (btrim(review_note) <> ''),
    reviewed_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION restricted_identity.guard_restricted_evidence_review()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, restricted_identity, lending, core
AS $$
DECLARE
    recorder_id UUID;
BEGIN
    IF TG_OP = 'UPDATE' OR TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Restricted evidence reviews are append-only.';
    END IF;

    SELECT evidence.recorded_by_user_id
    INTO recorder_id
    FROM restricted_identity.cif_verification_evidence evidence
    WHERE evidence.id = NEW.evidence_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Restricted evidence was not found.';
    END IF;

    IF recorder_id = NEW.reviewed_by_user_id THEN
        RAISE EXCEPTION 'Restricted evidence reviewer must differ from the recorder.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS restricted_identity_evidence_review_guard
    ON restricted_identity.cif_verification_evidence_reviews;
CREATE TRIGGER restricted_identity_evidence_review_guard
BEFORE INSERT OR UPDATE OR DELETE
ON restricted_identity.cif_verification_evidence_reviews
FOR EACH ROW EXECUTE FUNCTION restricted_identity.guard_restricted_evidence_review();

CREATE TABLE IF NOT EXISTS restricted_identity.evidence_access_events (
    id BIGSERIAL PRIMARY KEY,
    actor_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    evidence_id UUID NOT NULL
        REFERENCES restricted_identity.cif_verification_evidence(id)
        ON DELETE RESTRICT,
    action TEXT NOT NULL CHECK (action IN ('view', 'record', 'review')),
    purpose_code TEXT NOT NULL CHECK (
        purpose_code IN (
            'cif_verification',
            'cif_reverification',
            'compliance_review',
            'dpo_audit'
        )
    ),
    registered_device_id UUID NOT NULL
        REFERENCES core.devices(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (request_id, evidence_id, action)
);

CREATE INDEX IF NOT EXISTS restricted_identity_access_actor_time_idx
    ON restricted_identity.evidence_access_events(actor_user_id, occurred_at DESC);

CREATE INDEX IF NOT EXISTS restricted_identity_access_evidence_time_idx
    ON restricted_identity.evidence_access_events(evidence_id, occurred_at DESC);

CREATE OR REPLACE FUNCTION restricted_identity.guard_restricted_evidence_access_event()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, restricted_identity, lending, core
AS $$
BEGIN
    IF TG_OP = 'UPDATE' OR TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Restricted evidence access events are append-only.';
    END IF;

    PERFORM 1
    FROM core.devices device
    WHERE device.id = NEW.registered_device_id
      AND device.user_id = NEW.actor_user_id
      AND device.status = 'active';

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Restricted evidence access requires the actor active registered device.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS restricted_identity_evidence_access_event_guard
    ON restricted_identity.evidence_access_events;
CREATE TRIGGER restricted_identity_evidence_access_event_guard
BEFORE INSERT OR UPDATE OR DELETE ON restricted_identity.evidence_access_events
FOR EACH ROW EXECUTE FUNCTION restricted_identity.guard_restricted_evidence_access_event();

CREATE OR REPLACE VIEW restricted_identity.cif_verification_evidence_status AS
SELECT
    evidence.id,
    evidence.client_id,
    evidence.cif_id,
    evidence.evidence_type,
    evidence.verification_method,
    evidence.verification_outcome,
    evidence.checked_at,
    evidence.document_date,
    evidence.document_expires_at,
    evidence.masked_reference,
    evidence.external_evidence_reference,
    evidence.evidence_digest,
    evidence.retention_class,
    evidence.retain_until,
    evidence.legal_hold,
    evidence.recorded_by_user_id,
    evidence.recorded_at,
    evidence.supersedes_evidence_id,
    review.review_decision,
    review.review_note,
    review.reviewed_by_user_id,
    review.reviewed_at,
    EXISTS (
        SELECT 1
        FROM restricted_identity.cif_verification_evidence newer
        WHERE newer.supersedes_evidence_id = evidence.id
    ) AS is_superseded
FROM restricted_identity.cif_verification_evidence evidence
LEFT JOIN restricted_identity.cif_verification_evidence_reviews review
  ON review.evidence_id = evidence.id;

REVOKE ALL ON ALL TABLES IN SCHEMA restricted_identity FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA restricted_identity FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA restricted_identity FROM PUBLIC;

COMMIT;
