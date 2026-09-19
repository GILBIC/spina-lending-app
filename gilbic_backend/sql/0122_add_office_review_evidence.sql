BEGIN;

ALTER TABLE lending.client_cif_versions ADD COLUMN IF NOT EXISTS identity_information JSONB;
ALTER TABLE lending.client_cif_versions DROP CONSTRAINT IF EXISTS client_cif_identity_information_shape;
ALTER TABLE lending.client_cif_versions ADD CONSTRAINT client_cif_identity_information_shape CHECK (
    identity_information IS NULL OR (
        jsonb_typeof(identity_information) = 'object'
        AND identity_information - 'birth_date' - 'birth_place' - 'civil_status' - 'citizenship' = '{}'::jsonb
    )
);

-- Private files are retained outside the served application root. No raw identity
-- or reusable biometric media is introduced by this signed-document boundary.
CREATE TABLE IF NOT EXISTS lending.office_review_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL UNIQUE,
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    cif_version_id UUID NOT NULL,
    application_id UUID,
    application_version_id UUID,
    purpose TEXT NOT NULL CHECK (purpose IN (
        'cif_review', 'application_review', 'borrower_contract_signed',
        'borrower_cash_received', 'privacy_acknowledgment'
    )),
    subject_id UUID NOT NULL,
    review_snapshot JSONB NOT NULL CHECK (
        jsonb_typeof(review_snapshot) = 'object' AND review_snapshot <> '{}'::jsonb
    ),
    snapshot_sha256 TEXT NOT NULL CHECK (snapshot_sha256 ~ '^[0-9a-f]{64}$'),
    content_sha256 TEXT NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    media_type TEXT NOT NULL CHECK (media_type IN ('application/pdf', 'image/png', 'image/jpeg')),
    byte_count INTEGER NOT NULL CHECK (byte_count BETWEEN 1 AND 10485760),
    captured_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (cif_version_id, client_id)
        REFERENCES lending.client_cif_versions(id, client_id) ON DELETE RESTRICT,
    FOREIGN KEY (application_version_id, application_id, client_id, cif_version_id)
        REFERENCES lending.loan_application_versions(id, application_id, client_id, cif_version_id)
        ON DELETE RESTRICT,
    CHECK ((application_id IS NULL) = (application_version_id IS NULL)),
    CHECK (purpose <> 'cif_review' OR (subject_id = cif_version_id AND application_id IS NULL)),
    CHECK (purpose <> 'application_review' OR (
        application_version_id IS NOT NULL AND subject_id = application_version_id
    ))
);

CREATE TABLE IF NOT EXISTS lending.client_cif_review_cycles (
    cif_version_id UUID PRIMARY KEY,
    client_id UUID NOT NULL,
    predecessor_cif_version_id UUID NOT NULL UNIQUE,
    reason TEXT NOT NULL CHECK (length(btrim(reason)) BETWEEN 3 AND 500),
    created_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (cif_version_id, client_id)
        REFERENCES lending.client_cif_versions(id, client_id) ON DELETE RESTRICT,
    FOREIGN KEY (predecessor_cif_version_id, client_id)
        REFERENCES lending.client_cif_versions(id, client_id) ON DELETE RESTRICT,
    CHECK (cif_version_id <> predecessor_cif_version_id)
);

DROP TRIGGER IF EXISTS trg_office_review_evidence_immutable ON lending.office_review_evidence;
CREATE TRIGGER trg_office_review_evidence_immutable
    BEFORE UPDATE OR DELETE ON lending.office_review_evidence
    FOR EACH ROW EXECUTE FUNCTION lending.reject_loan_application_history_mutation();
DROP TRIGGER IF EXISTS trg_office_review_evidence_no_truncate ON lending.office_review_evidence;
CREATE TRIGGER trg_office_review_evidence_no_truncate
    BEFORE TRUNCATE ON lending.office_review_evidence
    FOR EACH STATEMENT EXECUTE FUNCTION lending.reject_loan_application_history_mutation();
DROP TRIGGER IF EXISTS trg_client_cif_review_cycles_immutable ON lending.client_cif_review_cycles;
CREATE TRIGGER trg_client_cif_review_cycles_immutable
    BEFORE UPDATE OR DELETE ON lending.client_cif_review_cycles
    FOR EACH ROW EXECUTE FUNCTION lending.reject_loan_application_history_mutation();
DROP TRIGGER IF EXISTS trg_client_cif_review_cycles_no_truncate ON lending.client_cif_review_cycles;
CREATE TRIGGER trg_client_cif_review_cycles_no_truncate
    BEFORE TRUNCATE ON lending.client_cif_review_cycles
    FOR EACH STATEMENT EXECUTE FUNCTION lending.reject_loan_application_history_mutation();
REVOKE ALL ON lending.office_review_evidence, lending.client_cif_review_cycles FROM PUBLIC;

COMMIT;
