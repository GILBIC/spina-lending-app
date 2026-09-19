BEGIN;

INSERT INTO core.permissions(code, description)
VALUES ('client_payment_proof.review', 'Review Client payment evidence without posting a payment')
ON CONFLICT(code) DO NOTHING;
INSERT INTO core.role_permissions(role_id, permission_code)
SELECT id, 'client_payment_proof.review' FROM core.roles WHERE code='management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS lending.client_payment_proofs (
    id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    created_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_device_id UUID NOT NULL REFERENCES core.devices(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS client_payment_proofs_client_idx
    ON lending.client_payment_proofs(client_id, created_at DESC, id);

CREATE TABLE IF NOT EXISTS lending.client_payment_proof_versions (
    id UUID PRIMARY KEY,
    proof_id UUID NOT NULL REFERENCES lending.client_payment_proofs(id) ON DELETE RESTRICT,
    version_number INTEGER NOT NULL CHECK(version_number > 0),
    request_id UUID NOT NULL UNIQUE,
    note TEXT NOT NULL DEFAULT '' CHECK(length(note) <= 1000),
    media_type TEXT NOT NULL CHECK(media_type IN ('application/pdf','image/png','image/jpeg')),
    content_sha256 TEXT NOT NULL CHECK(content_sha256 ~ '^[0-9a-f]{64}$'),
    byte_count INTEGER NOT NULL CHECK(byte_count BETWEEN 1 AND 10485760),
    storage_key UUID NOT NULL UNIQUE,
    uploaded_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    uploaded_device_id UUID NOT NULL REFERENCES core.devices(id) ON DELETE RESTRICT,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(proof_id, version_number),
    UNIQUE(proof_id, id)
);

CREATE TABLE IF NOT EXISTS lending.client_payment_proof_reviews (
    id UUID PRIMARY KEY,
    proof_id UUID NOT NULL,
    version_id UUID NOT NULL,
    review_number INTEGER NOT NULL CHECK(review_number > 0),
    request_id UUID NOT NULL UNIQUE,
    previous_review_id UUID REFERENCES lending.client_payment_proof_reviews(id) ON DELETE RESTRICT,
    decision TEXT NOT NULL CHECK(decision IN ('reviewed','correction_required','rejected')),
    reason TEXT NOT NULL DEFAULT '' CHECK(length(reason) <= 1000),
    reviewed_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    reviewed_device_id UUID NOT NULL REFERENCES core.devices(id) ON DELETE RESTRICT,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY(proof_id, version_id)
        REFERENCES lending.client_payment_proof_versions(proof_id,id) ON DELETE RESTRICT,
    UNIQUE(version_id, review_number),
    CHECK(decision='reviewed' OR btrim(reason)<>'')
);

-- Append-only evidence and decisions. There is deliberately no collection,
-- receipt, allocation, balance, journal or provider-confirmation write here.
DO $$
DECLARE table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'client_payment_proofs','client_payment_proof_versions','client_payment_proof_reviews'
    ] LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS payment_proof_immutable ON lending.%I',table_name);
        EXECUTE format('CREATE TRIGGER payment_proof_immutable BEFORE UPDATE OR DELETE ON lending.%I FOR EACH ROW EXECUTE FUNCTION lending.reject_loan_application_history_mutation()',table_name);
        EXECUTE format('DROP TRIGGER IF EXISTS payment_proof_no_truncate ON lending.%I',table_name);
        EXECUTE format('CREATE TRIGGER payment_proof_no_truncate BEFORE TRUNCATE ON lending.%I FOR EACH STATEMENT EXECUTE FUNCTION lending.reject_loan_application_history_mutation()',table_name);
        EXECUTE format('REVOKE ALL ON lending.%I FROM PUBLIC',table_name);
    END LOOP;
END;
$$;

COMMIT;
