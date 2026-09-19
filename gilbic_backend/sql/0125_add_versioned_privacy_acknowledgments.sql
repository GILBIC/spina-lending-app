BEGIN;
CREATE TABLE IF NOT EXISTS lending.client_privacy_acknowledgments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    cif_version_id UUID NOT NULL,
    notice_version TEXT NOT NULL CHECK (btrim(notice_version) <> ''),
    notice_sha256 TEXT NOT NULL CHECK (notice_sha256 ~ '^[0-9a-f]{64}$'),
    consent_version TEXT NOT NULL CHECK (btrim(consent_version) <> ''),
    consent_sha256 TEXT NOT NULL CHECK (consent_sha256 ~ '^[0-9a-f]{64}$'),
    optional_service_communications BOOLEAN NOT NULL DEFAULT FALSE,
    evidence_id UUID NOT NULL UNIQUE REFERENCES lending.office_review_evidence(id) ON DELETE RESTRICT,
    review_snapshot JSONB NOT NULL CHECK (jsonb_typeof(review_snapshot) = 'object'),
    acknowledged_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    acknowledged_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (cif_version_id, client_id) REFERENCES lending.client_cif_versions(id, client_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS client_privacy_acknowledgments_current_idx
    ON lending.client_privacy_acknowledgments(client_id, cif_version_id, acknowledged_at DESC);
DROP TRIGGER IF EXISTS client_privacy_acknowledgments_immutable ON lending.client_privacy_acknowledgments;
CREATE TRIGGER client_privacy_acknowledgments_immutable
    BEFORE UPDATE OR DELETE ON lending.client_privacy_acknowledgments
    FOR EACH ROW EXECUTE FUNCTION lending.reject_loan_application_history_mutation();
DROP TRIGGER IF EXISTS client_privacy_acknowledgments_no_truncate ON lending.client_privacy_acknowledgments;
CREATE TRIGGER client_privacy_acknowledgments_no_truncate
    BEFORE TRUNCATE ON lending.client_privacy_acknowledgments
    FOR EACH STATEMENT EXECUTE FUNCTION lending.reject_loan_application_history_mutation();
REVOKE ALL ON lending.client_privacy_acknowledgments FROM PUBLIC;
COMMIT;
