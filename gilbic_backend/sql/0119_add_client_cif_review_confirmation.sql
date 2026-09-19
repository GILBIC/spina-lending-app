BEGIN;

-- Applicant information-review evidence only; no financial transition.
-- 0115-0118 already belong to the merged 7x7 work. Requires CIF foundation 0114.
-- The composite key prevents attaching one Client's confirmation to another CIF.
CREATE UNIQUE INDEX IF NOT EXISTS lending_client_cif_versions_identity_uidx
    ON lending.client_cif_versions(id, client_id);

CREATE TABLE IF NOT EXISTS lending.client_cif_review_confirmations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    cif_version_id UUID NOT NULL REFERENCES lending.client_cif_versions(id) ON DELETE RESTRICT,
    review_cycle_number INTEGER NOT NULL CHECK (review_cycle_number > 0),
    review_snapshot JSONB NOT NULL,
    applicant_confirmation_evidence_reference TEXT NOT NULL,
    witnessed_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    confirmed_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (client_id, review_cycle_number),
    UNIQUE (cif_version_id),
    FOREIGN KEY (cif_version_id, client_id)
        REFERENCES lending.client_cif_versions(id, client_id) ON DELETE RESTRICT,
    CHECK (jsonb_typeof(review_snapshot) = 'object'),
    CHECK (review_snapshot <> '{}'::jsonb),
    CHECK (btrim(applicant_confirmation_evidence_reference) <> '')
);

-- Corrections require a new CIF version/review cycle, never an in-place rewrite.
CREATE OR REPLACE FUNCTION lending.reject_client_cif_review_confirmation_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'CIF review confirmations are immutable'
        USING ERRCODE = '23514';
END;
$$;

DROP TRIGGER IF EXISTS trg_client_cif_review_confirmation_immutable
    ON lending.client_cif_review_confirmations;
CREATE TRIGGER trg_client_cif_review_confirmation_immutable
    BEFORE UPDATE OR DELETE ON lending.client_cif_review_confirmations
    FOR EACH ROW
    EXECUTE FUNCTION lending.reject_client_cif_review_confirmation_mutation();

DROP TRIGGER IF EXISTS trg_client_cif_review_confirmation_no_truncate
    ON lending.client_cif_review_confirmations;
CREATE TRIGGER trg_client_cif_review_confirmation_no_truncate
    BEFORE TRUNCATE ON lending.client_cif_review_confirmations
    FOR EACH STATEMENT
    EXECUTE FUNCTION lending.reject_client_cif_review_confirmation_mutation();

-- Retain the existing private-schema/default-privilege boundary from 0109.
-- Only the protected backend may expose the future review/confirmation actions.
REVOKE ALL ON lending.client_cif_review_confirmations FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION lending.reject_client_cif_review_confirmation_mutation()
    FROM PUBLIC;

COMMIT;
