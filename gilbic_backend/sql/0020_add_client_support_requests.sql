BEGIN;

INSERT INTO core.permissions (code, description)
VALUES
    ('support.manage', 'Review and answer client support requests')
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission ON permission.code = 'support.manage'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS lending.client_support_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL
        REFERENCES lending.clients(id) ON DELETE RESTRICT,
    created_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    category TEXT NOT NULL
        CHECK (category IN ('payment', 'loan', 'renewal', 'account', 'other')),
    subject TEXT NOT NULL,
    message TEXT NOT NULL,
    reference_text TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'answered', 'resolved', 'cancelled')),
    managed_by_user_id UUID
        REFERENCES core.users(id) ON DELETE RESTRICT,
    management_response TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    responded_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (length(btrim(subject)) BETWEEN 3 AND 120),
    CHECK (length(btrim(message)) BETWEEN 3 AND 2000),
    CHECK (length(reference_text) <= 120),
    CHECK (length(management_response) <= 2000),
    CHECK (
        (status = 'open'
            AND managed_by_user_id IS NULL
            AND management_response = ''
            AND responded_at IS NULL
            AND resolved_at IS NULL
            AND cancelled_at IS NULL)
        OR
        (status = 'answered'
            AND managed_by_user_id IS NOT NULL
            AND length(btrim(management_response)) >= 3
            AND responded_at IS NOT NULL
            AND resolved_at IS NULL
            AND cancelled_at IS NULL)
        OR
        (status = 'resolved'
            AND managed_by_user_id IS NOT NULL
            AND length(btrim(management_response)) >= 3
            AND responded_at IS NOT NULL
            AND resolved_at IS NOT NULL
            AND cancelled_at IS NULL)
        OR
        (status = 'cancelled'
            AND managed_by_user_id IS NULL
            AND management_response = ''
            AND responded_at IS NULL
            AND resolved_at IS NULL
            AND cancelled_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS lending_client_support_client_idx
    ON lending.client_support_requests (client_id, created_at DESC);
CREATE INDEX IF NOT EXISTS lending_client_support_status_idx
    ON lending.client_support_requests (status, created_at DESC);

COMMIT;
