BEGIN;

INSERT INTO core.permissions (code, description)
VALUES
    ('renewal.manage', 'Review client loan-renewal requests')
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission ON permission.code = 'renewal.manage'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS lending.client_renewal_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL
        REFERENCES lending.clients(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL
        REFERENCES lending.loans(id) ON DELETE RESTRICT,
    requested_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    requested_amount NUMERIC(18,2) NOT NULL
        CHECK (requested_amount > 0),
    client_message TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')),
    reviewed_by_user_id UUID
        REFERENCES core.users(id) ON DELETE RESTRICT,
    review_note TEXT NOT NULL DEFAULT '',
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (length(client_message) <= 1000),
    CHECK (length(review_note) <= 1000),
    CHECK (
        (status = 'pending'
            AND reviewed_by_user_id IS NULL
            AND reviewed_at IS NULL
            AND cancelled_at IS NULL)
        OR
        (status IN ('approved', 'rejected')
            AND reviewed_by_user_id IS NOT NULL
            AND reviewed_at IS NOT NULL
            AND cancelled_at IS NULL)
        OR
        (status = 'cancelled'
            AND reviewed_by_user_id IS NULL
            AND reviewed_at IS NULL
            AND cancelled_at IS NOT NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS lending_client_renewal_one_pending_uidx
    ON lending.client_renewal_requests (client_id, loan_id)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS lending_client_renewal_client_idx
    ON lending.client_renewal_requests (client_id, submitted_at DESC);
CREATE INDEX IF NOT EXISTS lending_client_renewal_status_idx
    ON lending.client_renewal_requests (status, submitted_at DESC);
CREATE INDEX IF NOT EXISTS lending_client_renewal_loan_idx
    ON lending.client_renewal_requests (loan_id, submitted_at DESC);

COMMIT;
