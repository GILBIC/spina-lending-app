BEGIN;

-- R1 Task 2: private pre-release evidence, never a loan, tax event or journal.
-- Source freshness, retained bytes and exact financial approval stay in the
-- protected repository. A database owner can still impersonate row inputs.
CREATE TABLE IF NOT EXISTS lending.first_loan_disclosure_calculations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schema_version INTEGER NOT NULL DEFAULT 1 CHECK (schema_version = 1),
    request_id UUID NOT NULL UNIQUE,
    application_id UUID NOT NULL
        REFERENCES lending.loan_applications(id) ON DELETE RESTRICT,
    application_version_id UUID NOT NULL
        REFERENCES lending.loan_application_versions(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    cif_version_id UUID NOT NULL
        REFERENCES lending.client_cif_versions(id) ON DELETE RESTRICT,
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    supersedes_calculation_id UUID UNIQUE
        REFERENCES lending.first_loan_disclosure_calculations(id) ON DELETE RESTRICT,
    dst_rule_id UUID NOT NULL
        REFERENCES accounting.v1_tax_rule_evidence(id) ON DELETE RESTRICT,
    grt_rule_id UUID NOT NULL
        REFERENCES accounting.v1_tax_rule_evidence(id) ON DELETE RESTRICT,
    request_digest TEXT NOT NULL
        CHECK (length(request_digest) = 64 AND request_digest ~ '^[0-9a-f]{64}$'),
    review_digest TEXT NOT NULL
        CHECK (length(review_digest) = 64 AND review_digest ~ '^[0-9a-f]{64}$'),
    input_snapshot JSONB NOT NULL
        CHECK (jsonb_typeof(input_snapshot) = 'object' AND input_snapshot <> '{}'),
    source_snapshot JSONB NOT NULL
        CHECK (jsonb_typeof(source_snapshot) = 'object' AND source_snapshot <> '{}'),
    rule_snapshot JSONB NOT NULL
        CHECK (jsonb_typeof(rule_snapshot) = 'object' AND rule_snapshot <> '{}'),
    review_snapshot JSONB NOT NULL
        CHECK (jsonb_typeof(review_snapshot) = 'object' AND review_snapshot <> '{}'),
    support_storage_key UUID NOT NULL UNIQUE,
    support_sha256 TEXT NOT NULL
        CHECK (length(support_sha256) = 64 AND support_sha256 ~ '^[0-9a-f]{64}$'),
    support_media_type TEXT NOT NULL
        CHECK (support_media_type IN ('application/pdf', 'image/png', 'image/jpeg')),
    support_byte_count INTEGER NOT NULL
        CHECK (support_byte_count BETWEEN 1 AND 10485760),
    reviewed_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    reviewed_device_id UUID NOT NULL REFERENCES core.devices(id) ON DELETE RESTRICT,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (application_id, version_number),
    UNIQUE (application_version_id, version_number),
    CHECK (supersedes_calculation_id IS NULL OR supersedes_calculation_id <> id)
);

CREATE OR REPLACE FUNCTION lending.guard_first_loan_disclosure_insert()
RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE
    prior lending.first_loan_disclosure_calculations%ROWTYPE;
BEGIN
    -- Same application -> Client order as the existing first-loan _source.
    -- Lock the stable parent, not only an optional prior calculation row.
    PERFORM 1 FROM lending.loan_applications
    WHERE id = NEW.application_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Disclosure application source is invalid'
            USING ERRCODE = '23514';
    END IF;
    PERFORM 1 FROM lending.clients WHERE id = NEW.client_id FOR UPDATE;
    IF NOT EXISTS (
        SELECT 1 FROM lending.loan_application_versions v
        JOIN lending.client_cif_versions c ON c.id = v.cif_version_id
        WHERE v.id = NEW.application_version_id
          AND v.application_id = NEW.application_id
          AND v.client_id = NEW.client_id
          AND v.cif_version_id = NEW.cif_version_id
          AND c.client_id = NEW.client_id
    ) THEN
        RAISE EXCEPTION 'Disclosure application, Client and CIF must match'
            USING ERRCODE = '23514';
    END IF;

    IF NEW.source_snapshot->>'application_id' IS DISTINCT FROM NEW.application_id::text
       OR NEW.source_snapshot->>'application_version_id' IS DISTINCT FROM NEW.application_version_id::text
       OR NEW.source_snapshot->>'client_id' IS DISTINCT FROM NEW.client_id::text
       OR NEW.source_snapshot->>'cif_version_id' IS DISTINCT FROM NEW.cif_version_id::text THEN
        RAISE EXCEPTION 'Disclosure source snapshot must match its recorded identities'
            USING ERRCODE = '23514';
    END IF;

    PERFORM u.id FROM core.users u JOIN core.devices d ON d.user_id = u.id
    WHERE u.id = NEW.reviewed_by_user_id AND u.status = 'active'
      AND d.id = NEW.reviewed_device_id AND d.status = 'active'
      AND EXISTS (
          SELECT 1 FROM core.user_roles ur
          JOIN core.roles r ON r.id = ur.role_id
          JOIN core.role_permissions p ON p.role_id = r.id
          WHERE ur.user_id = u.id AND r.code = 'management'
            AND p.permission_code = 'lending.first_loan.approve'
      ) FOR SHARE OF u, d;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Disclosure review requires authorized Management and device'
            USING ERRCODE = '23514';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM accounting.v1_tax_rule_evidence
        WHERE id = NEW.dst_rule_id AND tax_type = 'documentary_stamp_tax'
    ) OR NOT EXISTS (
        SELECT 1 FROM accounting.v1_tax_rule_evidence
        WHERE id = NEW.grt_rule_id AND tax_type = 'percentage_tax_lending'
    ) THEN
        RAISE EXCEPTION 'Disclosure rule identities must have the correct tax types'
            USING ERRCODE = '23514';
    END IF;

    SELECT * INTO prior FROM lending.first_loan_disclosure_calculations
    WHERE application_id = NEW.application_id
    ORDER BY version_number DESC LIMIT 1;
    IF prior.id IS NULL THEN
        IF NEW.version_number <> 1 OR NEW.supersedes_calculation_id IS NOT NULL THEN
            RAISE EXCEPTION 'The first disclosure review starts at version one'
                USING ERRCODE = '23514';
        END IF;
    ELSIF NEW.supersedes_calculation_id IS DISTINCT FROM prior.id
       OR NEW.version_number::bigint <> prior.version_number::bigint + 1 THEN
        RAISE EXCEPTION 'Disclosure review must supersede the current application review'
            USING ERRCODE = '23514';
    END IF;

    -- The authenticated repository supplies the actor; time is database-owned.
    NEW.reviewed_at := clock_timestamp();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS first_loan_disclosure_source_guard
    ON lending.first_loan_disclosure_calculations;
CREATE TRIGGER first_loan_disclosure_source_guard
BEFORE INSERT ON lending.first_loan_disclosure_calculations
FOR EACH ROW EXECUTE FUNCTION lending.guard_first_loan_disclosure_insert();

DROP TRIGGER IF EXISTS first_loan_disclosure_immutable
    ON lending.first_loan_disclosure_calculations;
CREATE TRIGGER first_loan_disclosure_immutable
BEFORE UPDATE OR DELETE ON lending.first_loan_disclosure_calculations
FOR EACH ROW EXECUTE FUNCTION lending.reject_loan_application_history_mutation();

DROP TRIGGER IF EXISTS first_loan_disclosure_no_truncate
    ON lending.first_loan_disclosure_calculations;
CREATE TRIGGER first_loan_disclosure_no_truncate
BEFORE TRUNCATE ON lending.first_loan_disclosure_calculations
FOR EACH STATEMENT EXECUTE FUNCTION lending.reject_loan_application_history_mutation();

CREATE OR REPLACE FUNCTION lending.guard_first_loan_disclosure_approval()
RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE
    calculation lending.first_loan_disclosure_calculations%ROWTYPE;
    binding JSONB;
    calculation_id_text TEXT;
BEGIN
    -- No activation/backfill: existing schema-1 insertion/readback is unchanged.
    -- Full source-required activation is the later protected lifecycle slice.
    IF coalesce(NEW.packet->>'schema_version', '1') = '1'
       AND NOT (NEW.packet ? 'tax_disclosure') THEN
        RETURN NEW;
    END IF;
    binding := NEW.packet->'tax_disclosure';
    IF NEW.packet->'schema_version' IS DISTINCT FROM '2'::jsonb
       OR jsonb_typeof(binding) IS DISTINCT FROM 'object' THEN
        RAISE EXCEPTION 'A schema-two approval requires its disclosure binding'
            USING ERRCODE = '23514';
    END IF;

    calculation_id_text := binding->>'calculation_id';
    IF calculation_id_text IS NULL OR length(calculation_id_text) <> 36
       OR calculation_id_text !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN
        RAISE EXCEPTION 'A canonical saved disclosure identity is required'
            USING ERRCODE = '23514';
    END IF;
    -- Stabilize the same application chain before selecting its saved review.
    PERFORM 1 FROM lending.loan_applications a
    JOIN lending.loan_application_versions v ON v.application_id = a.id
    WHERE v.id = NEW.application_version_id FOR UPDATE OF a;
    SELECT * INTO calculation FROM lending.first_loan_disclosure_calculations
    WHERE id = calculation_id_text::uuid;
    IF calculation.id IS NULL
       OR calculation.review_digest IS DISTINCT FROM binding->>'review_digest'
       OR calculation.client_id IS DISTINCT FROM NEW.client_id
       OR calculation.application_version_id IS DISTINCT FROM NEW.application_version_id
       OR calculation.cif_version_id IS DISTINCT FROM NEW.cif_version_id
       OR jsonb_typeof(calculation.input_snapshot->'terms') IS DISTINCT FROM 'object'
       OR calculation.input_snapshot->'terms' IS DISTINCT FROM NEW.packet->'terms'
       OR EXISTS (
           SELECT 1 FROM lending.first_loan_disclosure_calculations newer
           WHERE newer.application_id = calculation.application_id
             AND newer.version_number > calculation.version_number
       ) THEN
        RAISE EXCEPTION 'Approval disclosure identity, digest or source differs'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS first_loan_disclosure_approval_guard
    ON lending.first_loan_approvals;
CREATE TRIGGER first_loan_disclosure_approval_guard
BEFORE INSERT ON lending.first_loan_approvals
FOR EACH ROW EXECUTE FUNCTION lending.guard_first_loan_disclosure_approval();

REVOKE ALL ON lending.first_loan_disclosure_calculations FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION lending.guard_first_loan_disclosure_insert() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION lending.guard_first_loan_disclosure_approval() FROM PUBLIC;
DO $$
DECLARE
    browser_role TEXT;
BEGIN
    FOREACH browser_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = browser_role) THEN
            EXECUTE format(
                'REVOKE ALL ON lending.first_loan_disclosure_calculations FROM %I',
                browser_role
            );
            EXECUTE format(
                'REVOKE EXECUTE ON FUNCTION lending.guard_first_loan_disclosure_insert() FROM %I',
                browser_role
            );
            EXECUTE format(
                'REVOKE EXECUTE ON FUNCTION lending.guard_first_loan_disclosure_approval() FROM %I',
                browser_role
            );
        END IF;
    END LOOP;
END;
$$;

COMMIT;
