BEGIN;

-- Priority #6 adds an explicit pre-contract readiness boundary for 7x7 pricing
-- and disclosure review. This migration records Management review evidence only;
-- it does not infer legal applicability, calculate EIR, set regulatory ceilings,
-- accrue penalties, change loan balances, or post accounting entries.

CREATE TABLE IF NOT EXISTS lending.seven_by_seven_pricing_compliance_reviews (
    id BIGSERIAL PRIMARY KEY,
    loan_id UUID NOT NULL
        REFERENCES lending.loans(id) ON DELETE RESTRICT,
    terms_fingerprint TEXT NOT NULL
        CHECK (terms_fingerprint ~ '^[0-9a-f]{64}$'),
    applicability_review_ready BOOLEAN NOT NULL,
    pricing_cap_review_ready BOOLEAN NOT NULL,
    disclosure_ready BOOLEAN NOT NULL,
    total_cost_cap_review_ready BOOLEAN NOT NULL,
    evidence_reference TEXT NOT NULL
        CHECK (btrim(evidence_reference) <> ''),
    review_note TEXT NOT NULL
        CHECK (btrim(review_note) <> ''),
    reviewed_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS lending_7x7_pricing_compliance_terms_idx
    ON lending.seven_by_seven_pricing_compliance_reviews (
        loan_id,
        terms_fingerprint,
        reviewed_at DESC,
        id DESC
    );

CREATE OR REPLACE FUNCTION lending.guard_7x7_pricing_compliance_review_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '7x7 pricing/compliance review evidence is immutable; record a new exact-term review instead.';
END;
$$;

DROP TRIGGER IF EXISTS lending_7x7_pricing_compliance_review_immutability_guard
    ON lending.seven_by_seven_pricing_compliance_reviews;
CREATE TRIGGER lending_7x7_pricing_compliance_review_immutability_guard
BEFORE UPDATE OR DELETE ON lending.seven_by_seven_pricing_compliance_reviews
FOR EACH ROW EXECUTE FUNCTION lending.guard_7x7_pricing_compliance_review_immutability();

COMMIT;
