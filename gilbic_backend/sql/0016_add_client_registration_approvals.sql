BEGIN;

CREATE TABLE IF NOT EXISTS core.client_registration_requests (
    user_id UUID PRIMARY KEY
        REFERENCES core.users(id) ON DELETE RESTRICT,
    claimed_client_code TEXT NOT NULL,
    claimed_phone_number TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),
    linked_client_id UUID UNIQUE
        REFERENCES lending.clients(id) ON DELETE RESTRICT,
    reviewed_by_user_id UUID
        REFERENCES core.users(id) ON DELETE RESTRICT,
    review_note TEXT NOT NULL DEFAULT '',
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (btrim(claimed_client_code) <> ''),
    CHECK (
        (status = 'pending'
            AND linked_client_id IS NULL
            AND reviewed_by_user_id IS NULL
            AND reviewed_at IS NULL)
        OR
        (status = 'approved'
            AND linked_client_id IS NOT NULL
            AND reviewed_by_user_id IS NOT NULL
            AND reviewed_at IS NOT NULL)
        OR
        (status = 'rejected'
            AND linked_client_id IS NULL
            AND reviewed_by_user_id IS NOT NULL
            AND reviewed_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS core_client_registration_status_idx
    ON core.client_registration_requests (status, submitted_at DESC);
CREATE INDEX IF NOT EXISTS core_client_registration_claim_code_idx
    ON core.client_registration_requests (lower(claimed_client_code));

COMMIT;
