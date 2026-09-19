BEGIN;

-- Per-application draft history only; requires CIF identity from 0114/0119.
-- Do not replace profile confirmations or create loan/approval/release state.
CREATE TABLE IF NOT EXISTS lending.loan_applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_reference TEXT NOT NULL UNIQUE,
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    created_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (id, client_id),
    CHECK (btrim(application_reference) <> '')
);

CREATE TABLE IF NOT EXISTS lending.loan_application_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL,
    client_id UUID NOT NULL,
    cif_version_id UUID NOT NULL,
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    information JSONB NOT NULL,
    recorded_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (application_id, version_number),
    FOREIGN KEY (application_id, client_id)
        REFERENCES lending.loan_applications(id, client_id) ON DELETE RESTRICT,
    FOREIGN KEY (cif_version_id, client_id)
        REFERENCES lending.client_cif_versions(id, client_id) ON DELETE RESTRICT,
    -- Validate only the two section objects; incomplete drafts are allowed.
    -- CASE rejects scalars safely; IS TRUE prevents missing-key NULL bypass.
    CHECK (
        CASE WHEN jsonb_typeof(information) = 'object' THEN
            (
                jsonb_typeof(information -> 'request') = 'object'
                AND jsonb_typeof(information -> 'repayment') = 'object'
                AND information - 'request' - 'repayment' = '{}'::jsonb
            ) IS TRUE
        ELSE false END
    )
);

-- Corrections append a new version, never modify an existing header or version.
CREATE OR REPLACE FUNCTION lending.reject_loan_application_history_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'Loan application history is immutable'
        USING ERRCODE = '23514';
END;
$$;

DROP TRIGGER IF EXISTS trg_loan_applications_immutable
    ON lending.loan_applications;
CREATE TRIGGER trg_loan_applications_immutable
    BEFORE UPDATE OR DELETE ON lending.loan_applications
    FOR EACH ROW
    EXECUTE FUNCTION lending.reject_loan_application_history_mutation();

DROP TRIGGER IF EXISTS trg_loan_applications_no_truncate
    ON lending.loan_applications;
CREATE TRIGGER trg_loan_applications_no_truncate
    BEFORE TRUNCATE ON lending.loan_applications
    FOR EACH STATEMENT
    EXECUTE FUNCTION lending.reject_loan_application_history_mutation();

DROP TRIGGER IF EXISTS trg_loan_application_versions_immutable
    ON lending.loan_application_versions;
CREATE TRIGGER trg_loan_application_versions_immutable
    BEFORE UPDATE OR DELETE ON lending.loan_application_versions
    FOR EACH ROW
    EXECUTE FUNCTION lending.reject_loan_application_history_mutation();

DROP TRIGGER IF EXISTS trg_loan_application_versions_no_truncate
    ON lending.loan_application_versions;
CREATE TRIGGER trg_loan_application_versions_no_truncate
    BEFORE TRUNCATE ON lending.loan_application_versions
    FOR EACH STATEMENT
    EXECUTE FUNCTION lending.reject_loan_application_history_mutation();

-- Keep the existing 0109 private-schema/default-privilege boundary.
-- Actor authorization, atomic saves and retry handling belong to the backend.
REVOKE ALL ON lending.loan_applications, lending.loan_application_versions FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION lending.reject_loan_application_history_mutation()
    FROM PUBLIC;

COMMIT;
