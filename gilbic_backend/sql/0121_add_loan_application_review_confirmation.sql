BEGIN;

-- Information-review evidence only; no loan approval or financial transition.
-- Requires immutable application history 0120 and existing CIF review 0119.
CREATE UNIQUE INDEX IF NOT EXISTS lending_loan_application_versions_source_uidx
    ON lending.loan_application_versions(id, application_id, client_id, cif_version_id);

CREATE TABLE IF NOT EXISTS lending.loan_application_review_confirmations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_version_id UUID NOT NULL UNIQUE,
    application_id UUID NOT NULL,
    client_id UUID NOT NULL,
    cif_version_id UUID NOT NULL,
    applicant_confirmation_evidence_reference TEXT NOT NULL,
    witnessed_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    confirmed_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    FOREIGN KEY (application_version_id, application_id, client_id, cif_version_id)
        REFERENCES lending.loan_application_versions(id, application_id, client_id, cif_version_id)
        ON DELETE RESTRICT,
    CHECK (btrim(applicant_confirmation_evidence_reference) <> '')
);

-- Reuse 0120's history guard. Corrections append a version and confirmation.
DROP TRIGGER IF EXISTS trg_loan_application_review_confirmation_immutable
    ON lending.loan_application_review_confirmations;
CREATE TRIGGER trg_loan_application_review_confirmation_immutable
    BEFORE UPDATE OR DELETE ON lending.loan_application_review_confirmations
    FOR EACH ROW
    EXECUTE FUNCTION lending.reject_loan_application_history_mutation();

DROP TRIGGER IF EXISTS trg_loan_application_review_confirmation_no_truncate
    ON lending.loan_application_review_confirmations;
CREATE TRIGGER trg_loan_application_review_confirmation_no_truncate
    BEFORE TRUNCATE ON lending.loan_application_review_confirmations
    FOR EACH STATEMENT
    EXECUTE FUNCTION lending.reject_loan_application_history_mutation();

-- Preserve 0109's private-schema/default-privilege boundary.
REVOKE ALL ON lending.loan_application_review_confirmations FROM PUBLIC;

COMMIT;
