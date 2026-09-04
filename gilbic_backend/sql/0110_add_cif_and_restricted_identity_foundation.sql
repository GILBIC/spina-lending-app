BEGIN;

CREATE SCHEMA IF NOT EXISTS restricted_identity;
REVOKE ALL ON SCHEMA restricted_identity FROM PUBLIC;

INSERT INTO core.permissions (code, description)
VALUES
    ('cif.view', 'View ordinary Client Information Form records and lifecycle status'),
    ('cif.prepare', 'Create and update draft Client Information Forms'),
    ('cif.verify', 'Verify a complete Client Information Form source digest'),
    ('cif.approve', 'Activate a verified Client Information Form'),
    ('cif.reverification.open', 'Open an early Client Information Form re-verification requirement'),
    ('identity_evidence.view', 'View restricted identity-verification metadata for an approved purpose'),
    ('identity_evidence.manage', 'Create, review, and supersede restricted identity-verification metadata')
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code IN ('cif.view', 'cif.prepare')
WHERE role.code IN ('employee', 'management')
ON CONFLICT DO NOTHING;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code IN (
      'cif.verify',
      'cif.approve',
      'cif.reverification.open',
      'identity_evidence.view',
      'identity_evidence.manage'
  )
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE SEQUENCE IF NOT EXISTS lending.client_cif_number_sequence
    AS BIGINT
    START WITH 1
    INCREMENT BY 1
    NO CYCLE;

CREATE TABLE IF NOT EXISTS lending.client_information_forms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cif_number TEXT NOT NULL UNIQUE CHECK (btrim(cif_number) <> ''),
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
    nationality TEXT,
    civil_status TEXT,
    phone_number TEXT,
    email TEXT,
    present_address JSONB NOT NULL DEFAULT '{}'::jsonb,
    permanent_address JSONB NOT NULL DEFAULT '{}'::jsonb,
    livelihood_profile JSONB NOT NULL DEFAULT '{}'::jsonb,

    privacy_notice_version TEXT NOT NULL CHECK (btrim(privacy_notice_version) <> ''),
    privacy_acknowledged_at TIMESTAMPTZ,
    client_signature_reference TEXT,
    client_signature_sha256 CHAR(64)
        CHECK (
            client_signature_sha256 IS NULL
            OR client_signature_sha256 ~ '^[0-9a-f]{64}$'
        ),

    prepared_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    verified_by_user_id UUID
        REFERENCES core.users(id) ON DELETE RESTRICT,
    verified_at TIMESTAMPTZ,
    approved_by_user_id UUID
        REFERENCES core.users(id) ON DELETE RESTRICT,
    approved_at TIMESTAMPTZ,
    content_digest_sha256 CHAR(64)
        CHECK (
            content_digest_sha256 IS NULL
            OR content_digest_sha256 ~ '^[0-9a-f]{64}$'
        ),
    form_schema_version TEXT NOT NULL DEFAULT 'cif-v1'
        CHECK (btrim(form_schema_version) <> ''),
    draft_revision BIGINT NOT NULL DEFAULT 1 CHECK (draft_revision > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (client_id, form_version),
    CHECK (supersedes_cif_id IS NULL OR supersedes_cif_id <> id),
    CHECK (
        (verified_at IS NULL
            AND verified_by_user_id IS NULL
            AND content_digest_sha256 IS NULL)
        OR
        (verified_at IS NOT NULL
            AND verified_by_user_id IS NOT NULL
            AND content_digest_sha256 IS NOT NULL)
    ),
    CHECK (
        lifecycle_state = 'draft'
        OR (
            effective_at IS NOT NULL
            AND expires_at IS NOT NULL
            AND expires_at = effective_at + INTERVAL '5 years'
            AND verified_by_user_id IS NOT NULL
            AND verified_at IS NOT NULL
            AND approved_by_user_id IS NOT NULL
            AND approved_at IS NOT NULL
            AND verified_by_user_id <> approved_by_user_id
            AND content_digest_sha256 IS NOT NULL
            AND privacy_acknowledged_at IS NOT NULL
            AND client_signature_reference IS NOT NULL
            AND btrim(client_signature_reference) <> ''
            AND client_signature_sha256 IS NOT NULL
        )
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS lending_client_information_forms_active_uidx
    ON lending.client_information_forms(client_id)
    WHERE lifecycle_state = 'active';
CREATE INDEX IF NOT EXISTS lending_client_information_forms_client_version_idx
    ON lending.client_information_forms(client_id, form_version DESC);
CREATE INDEX IF NOT EXISTS lending_client_information_forms_expiry_idx
    ON lending.client_information_forms(expires_at)
    WHERE lifecycle_state = 'active';

CREATE OR REPLACE FUNCTION lending.guard_cif_supersession_client()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    superseded_client_id UUID;
BEGIN
    IF NEW.supersedes_cif_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT form.client_id
    INTO superseded_client_id
    FROM lending.client_information_forms form
    WHERE form.id = NEW.supersedes_cif_id;

    IF superseded_client_id IS NULL THEN
        RAISE EXCEPTION 'Superseded CIF does not exist.';
    END IF;
    IF superseded_client_id <> NEW.client_id THEN
        RAISE EXCEPTION 'A CIF may supersede only a CIF for the same client.';
    END IF;
    IF NEW.id = NEW.supersedes_cif_id THEN
        RAISE EXCEPTION 'A CIF cannot supersede itself.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_cif_supersession_client_guard
    ON lending.client_information_forms;
CREATE TRIGGER lending_cif_supersession_client_guard
BEFORE INSERT OR UPDATE ON lending.client_information_forms
FOR EACH ROW EXECUTE FUNCTION lending.guard_cif_supersession_client();

CREATE OR REPLACE FUNCTION lending.guard_client_information_form_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    new_without_state JSONB;
    old_without_state JSONB;
    content_changed BOOLEAN;
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.lifecycle_state <> 'draft' THEN
            RAISE EXCEPTION 'Activated or superseded CIF records are immutable.';
        END IF;
        RETURN OLD;
    END IF;

    IF OLD.lifecycle_state IN ('active', 'superseded') THEN
        new_without_state := to_jsonb(NEW) - ARRAY['lifecycle_state', 'updated_at'];
        old_without_state := to_jsonb(OLD) - ARRAY['lifecycle_state', 'updated_at'];
        IF OLD.lifecycle_state = 'active'
           AND NEW.lifecycle_state = 'superseded'
           AND new_without_state = old_without_state THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'Activated or superseded CIF records are immutable.';
    END IF;

    IF NEW.lifecycle_state NOT IN ('draft', 'active') THEN
        RAISE EXCEPTION 'A draft CIF may only remain draft or become active.';
    END IF;

    IF OLD.verified_at IS NOT NULL THEN
        content_changed := (
            NEW.legal_full_name IS DISTINCT FROM OLD.legal_full_name
            OR NEW.birth_date IS DISTINCT FROM OLD.birth_date
            OR NEW.nationality IS DISTINCT FROM OLD.nationality
            OR NEW.civil_status IS DISTINCT FROM OLD.civil_status
            OR NEW.phone_number IS DISTINCT FROM OLD.phone_number
            OR NEW.email IS DISTINCT FROM OLD.email
            OR NEW.present_address IS DISTINCT FROM OLD.present_address
            OR NEW.permanent_address IS DISTINCT FROM OLD.permanent_address
            OR NEW.livelihood_profile IS DISTINCT FROM OLD.livelihood_profile
            OR NEW.privacy_notice_version IS DISTINCT FROM OLD.privacy_notice_version
            OR NEW.privacy_acknowledged_at IS DISTINCT FROM OLD.privacy_acknowledged_at
            OR NEW.client_signature_reference IS DISTINCT FROM OLD.client_signature_reference
            OR NEW.client_signature_sha256 IS DISTINCT FROM OLD.client_signature_sha256
            OR NEW.form_schema_version IS DISTINCT FROM OLD.form_schema_version
        );
        IF content_changed AND NOT (
            NEW.verified_by_user_id IS NULL
            AND NEW.verified_at IS NULL
            AND NEW.approved_by_user_id IS NULL
            AND NEW.approved_at IS NULL
            AND NEW.content_digest_sha256 IS NULL
            AND NEW.effective_at IS NULL
            AND NEW.expires_at IS NULL
        ) THEN
            RAISE EXCEPTION 'Changing a verified draft must clear verification before re-verification.';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_client_information_form_mutation_guard
    ON lending.client_information_forms;
CREATE TRIGGER lending_client_information_form_mutation_guard
BEFORE UPDATE OR DELETE ON lending.client_information_forms
FOR EACH ROW EXECUTE FUNCTION lending.guard_client_information_form_mutation();

CREATE TABLE IF NOT EXISTS lending.client_cif_reverification_requirements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    source_cif_id UUID NOT NULL
        REFERENCES lending.client_information_forms(id) ON DELETE RESTRICT,
    reason TEXT NOT NULL CHECK (
        reason IN (
            'material_identity_change',
            'address_change',
            'contact_change',
            'document_expiry',
            'discrepancy',
            'suspicious_activity',
            'other_risk_event'
        )
    ),
    severity TEXT NOT NULL DEFAULT 'standard'
        CHECK (severity IN ('standard', 'elevated', 'critical')),
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'resolved', 'cancelled')),
    note TEXT NOT NULL DEFAULT '',
    opened_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolution_cif_id UUID
        REFERENCES lending.client_information_forms(id) ON DELETE RESTRICT,
    resolved_by_user_id UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (status = 'open'
            AND resolution_cif_id IS NULL
            AND resolved_by_user_id IS NULL
            AND resolved_at IS NULL)
        OR
        (status IN ('resolved', 'cancelled')
            AND resolved_by_user_id IS NOT NULL
            AND resolved_at IS NOT NULL)
    ),
    CHECK (status <> 'resolved' OR resolution_cif_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS lending_cif_reverification_open_client_idx
    ON lending.client_cif_reverification_requirements(client_id, opened_at DESC)
    WHERE status = 'open';

CREATE OR REPLACE FUNCTION lending.guard_cif_reverification_client()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    source_client_id UUID;
    resolution_client_id UUID;
BEGIN
    SELECT form.client_id
    INTO source_client_id
    FROM lending.client_information_forms form
    WHERE form.id = NEW.source_cif_id;

    IF source_client_id IS NULL OR source_client_id <> NEW.client_id THEN
        RAISE EXCEPTION 'Re-verification source CIF must belong to the same client.';
    END IF;

    IF NEW.resolution_cif_id IS NOT NULL THEN
        SELECT form.client_id
        INTO resolution_client_id
        FROM lending.client_information_forms form
        WHERE form.id = NEW.resolution_cif_id;
        IF resolution_client_id IS NULL OR resolution_client_id <> NEW.client_id THEN
            RAISE EXCEPTION 'Re-verification resolution CIF must belong to the same client.';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_cif_reverification_client_guard
    ON lending.client_cif_reverification_requirements;
CREATE TRIGGER lending_cif_reverification_client_guard
BEFORE INSERT OR UPDATE ON lending.client_cif_reverification_requirements
FOR EACH ROW EXECUTE FUNCTION lending.guard_cif_reverification_client();

CREATE OR REPLACE FUNCTION lending.guard_cif_reverification_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'CIF re-verification requirements cannot be deleted.';
    END IF;

    IF OLD.client_id IS DISTINCT FROM NEW.client_id
       OR OLD.source_cif_id IS DISTINCT FROM NEW.source_cif_id
       OR OLD.reason IS DISTINCT FROM NEW.reason
       OR OLD.severity IS DISTINCT FROM NEW.severity
       OR OLD.note IS DISTINCT FROM NEW.note
       OR OLD.opened_by_user_id IS DISTINCT FROM NEW.opened_by_user_id
       OR OLD.opened_at IS DISTINCT FROM NEW.opened_at
       OR OLD.created_at IS DISTINCT FROM NEW.created_at THEN
        RAISE EXCEPTION 'CIF re-verification source evidence is immutable.';
    END IF;

    IF OLD.status <> 'open' THEN
        RAISE EXCEPTION 'Closed CIF re-verification requirements are immutable.';
    END IF;
    IF NEW.status NOT IN ('open', 'resolved', 'cancelled') THEN
        RAISE EXCEPTION 'Invalid CIF re-verification transition.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_cif_reverification_mutation_guard
    ON lending.client_cif_reverification_requirements;
CREATE TRIGGER lending_cif_reverification_mutation_guard
BEFORE UPDATE OR DELETE ON lending.client_cif_reverification_requirements
FOR EACH ROW EXECUTE FUNCTION lending.guard_cif_reverification_mutation();

CREATE TABLE IF NOT EXISTS lending.client_cif_events (
    id BIGSERIAL PRIMARY KEY,
    cif_id UUID NOT NULL
        REFERENCES lending.client_information_forms(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    event_type TEXT NOT NULL CHECK (
        event_type IN (
            'created',
            'draft_updated',
            'verified',
            'activated',
            'superseded',
            'reverification_opened',
            'reverification_resolved',
            'reverification_cancelled'
        )
    ),
    actor_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS lending_client_cif_events_client_idx
    ON lending.client_cif_events(client_id, occurred_at DESC);

CREATE OR REPLACE FUNCTION lending.guard_client_cif_event_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'CIF lifecycle events are immutable.';
END;
$$;

DROP TRIGGER IF EXISTS lending_client_cif_event_immutability_guard
    ON lending.client_cif_events;
CREATE TRIGGER lending_client_cif_event_immutability_guard
BEFORE UPDATE OR DELETE ON lending.client_cif_events
FOR EACH ROW EXECUTE FUNCTION lending.guard_client_cif_event_immutability();

DROP VIEW IF EXISTS lending.client_information_form_status;
CREATE VIEW lending.client_information_form_status AS
SELECT
    form.id,
    form.cif_number,
    form.client_id,
    form.form_version,
    form.lifecycle_state,
    form.effective_at,
    form.expires_at,
    form.supersedes_cif_id,
    CASE
        WHEN form.lifecycle_state = 'draft' THEN 'Draft'
        WHEN form.lifecycle_state = 'superseded' THEN 'Superseded'
        WHEN now() >= form.expires_at THEN 'Expired'
        WHEN now() >= form.expires_at - INTERVAL '90 days' THEN 'Expiring'
        ELSE 'Active'
    END AS public_status,
    EXISTS (
        SELECT 1
        FROM lending.client_cif_reverification_requirements requirement
        WHERE requirement.client_id = form.client_id
          AND requirement.status = 'open'
    ) AS reverification_required,
    (
        form.lifecycle_state = 'active'
        AND now() < form.expires_at
        AND NOT EXISTS (
            SELECT 1
            FROM lending.client_cif_reverification_requirements requirement
            WHERE requirement.client_id = form.client_id
              AND requirement.status = 'open'
        )
    ) AS is_eligible_for_new_credit,
    TRUE AS allows_existing_obligation_servicing
FROM lending.client_information_forms form;

CREATE TABLE IF NOT EXISTS restricted_identity.cif_verification_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cif_id UUID NOT NULL
        REFERENCES lending.client_information_forms(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    evidence_type TEXT NOT NULL CHECK (
        evidence_type IN (
            'national_id_check',
            'everify_outcome',
            'government_id_metadata',
            'utility_proof',
            'residence_visit',
            'approved_exception'
        )
    ),
    verification_method TEXT NOT NULL CHECK (btrim(verification_method) <> ''),
    verification_result TEXT NOT NULL CHECK (
        verification_result IN (
            'verified',
            'not_verified',
            'inconclusive',
            'exception_approved'
        )
    ),
    checked_at TIMESTAMPTZ NOT NULL,
    document_date DATE,
    document_expires_at TIMESTAMPTZ,
    masked_reference TEXT CHECK (
        masked_reference IS NULL OR btrim(masked_reference) <> ''
    ),
    external_evidence_reference TEXT CHECK (
        external_evidence_reference IS NULL
        OR btrim(external_evidence_reference) <> ''
    ),
    evidence_sha256 CHAR(64) NOT NULL
        CHECK (evidence_sha256 ~ '^[0-9a-f]{64}$'),
    retention_class TEXT NOT NULL CHECK (
        retention_class IN (
            'identity_verification',
            'residence_verification',
            'exception_evidence'
        )
    ),
    retain_until DATE NOT NULL,
    legal_hold BOOLEAN NOT NULL DEFAULT false,
    review_state TEXT NOT NULL DEFAULT 'draft' CHECK (
        review_state IN ('draft', 'verified', 'rejected', 'superseded')
    ),
    verified_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    final_reviewed_by_user_id UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    reviewed_at TIMESTAMPTZ,
    supersedes_evidence_id UUID
        REFERENCES restricted_identity.cif_verification_evidence(id)
        ON DELETE RESTRICT,
    created_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (supersedes_evidence_id IS NULL OR supersedes_evidence_id <> id),
    CHECK (
        (review_state = 'draft'
            AND final_reviewed_by_user_id IS NULL
            AND reviewed_at IS NULL)
        OR
        (review_state IN ('verified', 'rejected', 'superseded')
            AND final_reviewed_by_user_id IS NOT NULL
            AND reviewed_at IS NOT NULL)
    ),
    CHECK (
        evidence_type <> 'approved_exception'
        OR review_state = 'draft'
        OR final_reviewed_by_user_id <> verified_by_user_id
    )
);

CREATE INDEX IF NOT EXISTS restricted_identity_cif_evidence_idx
    ON restricted_identity.cif_verification_evidence(cif_id, created_at DESC);
CREATE INDEX IF NOT EXISTS restricted_identity_client_evidence_idx
    ON restricted_identity.cif_verification_evidence(client_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS restricted_identity_evidence_digest_uidx
    ON restricted_identity.cif_verification_evidence(
        cif_id,
        evidence_type,
        evidence_sha256
    );

CREATE OR REPLACE FUNCTION restricted_identity.guard_restricted_evidence_client()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    form_client_id UUID;
    superseded_client_id UUID;
BEGIN
    SELECT form.client_id
    INTO form_client_id
    FROM lending.client_information_forms form
    WHERE form.id = NEW.cif_id;

    IF form_client_id IS NULL OR form_client_id <> NEW.client_id THEN
        RAISE EXCEPTION 'Restricted evidence CIF and client must match.';
    END IF;

    IF NEW.supersedes_evidence_id IS NOT NULL THEN
        SELECT evidence.client_id
        INTO superseded_client_id
        FROM restricted_identity.cif_verification_evidence evidence
        WHERE evidence.id = NEW.supersedes_evidence_id;
        IF superseded_client_id IS NULL OR superseded_client_id <> NEW.client_id THEN
            RAISE EXCEPTION 'Restricted evidence may supersede only evidence for the same client.';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS restricted_identity_evidence_client_guard
    ON restricted_identity.cif_verification_evidence;
CREATE TRIGGER restricted_identity_evidence_client_guard
BEFORE INSERT OR UPDATE ON restricted_identity.cif_verification_evidence
FOR EACH ROW EXECUTE FUNCTION restricted_identity.guard_restricted_evidence_client();

CREATE OR REPLACE FUNCTION restricted_identity.guard_restricted_evidence_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    new_without_state JSONB;
    old_without_state JSONB;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Restricted verification evidence cannot be deleted.';
    END IF;

    IF OLD.review_state IN ('verified', 'rejected', 'superseded') THEN
        new_without_state := to_jsonb(NEW) - ARRAY['review_state'];
        old_without_state := to_jsonb(OLD) - ARRAY['review_state'];
        IF OLD.review_state = 'verified'
           AND NEW.review_state = 'superseded'
           AND new_without_state = old_without_state THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'Reviewed restricted verification evidence is immutable.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS restricted_identity_evidence_mutation_guard
    ON restricted_identity.cif_verification_evidence;
CREATE TRIGGER restricted_identity_evidence_mutation_guard
BEFORE UPDATE OR DELETE ON restricted_identity.cif_verification_evidence
FOR EACH ROW EXECUTE FUNCTION restricted_identity.guard_restricted_evidence_mutation();

CREATE TABLE IF NOT EXISTS restricted_identity.evidence_access_events (
    id BIGSERIAL PRIMARY KEY,
    evidence_id UUID
        REFERENCES restricted_identity.cif_verification_evidence(id)
        ON DELETE RESTRICT,
    cif_id UUID NOT NULL
        REFERENCES lending.client_information_forms(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    actor_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    registered_device_id UUID NOT NULL REFERENCES core.devices(id) ON DELETE RESTRICT,
    action TEXT NOT NULL CHECK (
        action IN ('list', 'view', 'create', 'review', 'supersede')
    ),
    purpose_code TEXT NOT NULL CHECK (
        purpose_code IN (
            'initial_cif_verification',
            'reverification',
            'discrepancy_review',
            'compliance_review',
            'legal_hold',
            'retention_disposal'
        )
    ),
    request_id UUID NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS restricted_identity_access_actor_idx
    ON restricted_identity.evidence_access_events(actor_user_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS restricted_identity_access_evidence_idx
    ON restricted_identity.evidence_access_events(evidence_id, occurred_at DESC)
    WHERE evidence_id IS NOT NULL;

CREATE OR REPLACE FUNCTION restricted_identity.guard_evidence_access_event_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Restricted evidence access events are immutable.';
END;
$$;

DROP TRIGGER IF EXISTS restricted_identity_access_event_immutability_guard
    ON restricted_identity.evidence_access_events;
CREATE TRIGGER restricted_identity_access_event_immutability_guard
BEFORE UPDATE OR DELETE ON restricted_identity.evidence_access_events
FOR EACH ROW EXECUTE FUNCTION restricted_identity.guard_evidence_access_event_immutability();

REVOKE ALL ON ALL TABLES IN SCHEMA restricted_identity FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA restricted_identity FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA restricted_identity FROM PUBLIC;

COMMENT ON SCHEMA restricted_identity IS
    'Private metadata-only identity and residence verification boundary. Ordinary client, collector, application, and contract APIs must not query this schema.';
COMMENT ON TABLE restricted_identity.cif_verification_evidence IS
    'Necessary verification metadata only. External evidence objects require separately approved encrypted custody and are represented only by references and digests.';
COMMENT ON TABLE restricted_identity.evidence_access_events IS
    'Immutable purpose-bound access evidence without copied document content.';
COMMENT ON VIEW lending.client_information_form_status IS
    'Deterministic public CIF status and new-credit eligibility. Existing-obligation servicing is never blocked by CIF state.';

COMMIT;
