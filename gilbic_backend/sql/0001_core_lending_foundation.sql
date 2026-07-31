BEGIN;

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS lending;

REVOKE ALL ON SCHEMA core FROM PUBLIC;
REVOKE ALL ON SCHEMA lending FROM PUBLIC;

CREATE TABLE IF NOT EXISTS core.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT NOT NULL,
    email TEXT,
    full_name TEXT NOT NULL,
    external_auth_id UUID UNIQUE,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'locked', 'pending')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (btrim(username) <> ''),
    CHECK (btrim(full_name) <> '')
);

CREATE UNIQUE INDEX IF NOT EXISTS core_users_username_lower_uidx
    ON core.users (lower(username));
CREATE UNIQUE INDEX IF NOT EXISTS core_users_email_lower_uidx
    ON core.users (lower(email))
    WHERE email IS NOT NULL;

CREATE TABLE IF NOT EXISTS core.roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    is_system BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (btrim(code) <> ''),
    CHECK (btrim(name) <> '')
);

CREATE TABLE IF NOT EXISTS core.permissions (
    code TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (btrim(code) <> '')
);

CREATE TABLE IF NOT EXISTS core.role_permissions (
    role_id UUID NOT NULL REFERENCES core.roles(id) ON DELETE CASCADE,
    permission_code TEXT NOT NULL REFERENCES core.permissions(code) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (role_id, permission_code)
);

CREATE INDEX IF NOT EXISTS core_role_permissions_permission_idx
    ON core.role_permissions(permission_code);

CREATE TABLE IF NOT EXISTS core.user_roles (
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES core.roles(id) ON DELETE RESTRICT,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, role_id)
);

CREATE INDEX IF NOT EXISTS core_user_roles_role_idx
    ON core.user_roles(role_id);

CREATE TABLE IF NOT EXISTS core.devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    device_identifier_hash TEXT NOT NULL,
    platform TEXT NOT NULL
        CHECK (platform IN ('android', 'ios', 'web', 'desktop')),
    app_version TEXT,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'revoked', 'pending')),
    registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ,
    UNIQUE (user_id, device_identifier_hash),
    CHECK (btrim(device_identifier_hash) <> '')
);

CREATE INDEX IF NOT EXISTS core_devices_user_idx ON core.devices(user_id);
CREATE INDEX IF NOT EXISTS core_devices_status_idx ON core.devices(status);

CREATE TABLE IF NOT EXISTS lending.clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE REFERENCES core.users(id) ON DELETE SET NULL,
    client_code TEXT NOT NULL UNIQUE,
    legacy_client_id TEXT,
    full_name TEXT NOT NULL,
    phone_number TEXT,
    gcash_number TEXT,
    area TEXT,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'blocked', 'closed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (btrim(client_code) <> ''),
    CHECK (btrim(full_name) <> '')
);

CREATE INDEX IF NOT EXISTS lending_clients_area_idx ON lending.clients(area);
CREATE INDEX IF NOT EXISTS lending_clients_status_idx ON lending.clients(status);
CREATE INDEX IF NOT EXISTS lending_clients_legacy_idx ON lending.clients(legacy_client_id)
    WHERE legacy_client_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS lending.loan_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    term_days INTEGER NOT NULL CHECK (term_days > 0),
    calculation_mode TEXT NOT NULL
        CHECK (calculation_mode IN ('fixed_daily', 'seven_by_seven', 'custom')),
    daily_interest_per_1000 NUMERIC(12,2) NOT NULL DEFAULT 0
        CHECK (daily_interest_per_1000 >= 0),
    settings JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (btrim(code) <> ''),
    CHECK (btrim(name) <> '')
);

CREATE TABLE IF NOT EXISTS lending.loans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_number TEXT NOT NULL UNIQUE,
    legacy_loan_id TEXT,
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    loan_type_id UUID NOT NULL REFERENCES lending.loan_types(id) ON DELETE RESTRICT,
    principal NUMERIC(18,2) NOT NULL CHECK (principal > 0),
    daily_amount NUMERIC(18,2) NOT NULL CHECK (daily_amount >= 0),
    interest_rate NUMERIC(9,4),
    date_released DATE NOT NULL,
    due_date DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('draft', 'approved', 'active', 'paid', 'closed', 'cancelled', 'defaulted')),
    created_by_user_id UUID REFERENCES core.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (due_date >= date_released)
);

CREATE INDEX IF NOT EXISTS lending_loans_client_idx ON lending.loans(client_id);
CREATE INDEX IF NOT EXISTS lending_loans_type_idx ON lending.loans(loan_type_id);
CREATE INDEX IF NOT EXISTS lending_loans_status_idx ON lending.loans(status);
CREATE INDEX IF NOT EXISTS lending_loans_legacy_idx ON lending.loans(legacy_loan_id)
    WHERE legacy_loan_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS lending_loans_created_by_user_idx
    ON lending.loans(created_by_user_id)
    WHERE created_by_user_id IS NOT NULL;

INSERT INTO core.roles (code, name, description)
VALUES
    ('client', 'Client', 'Borrower-facing Gilbic access'),
    ('collector', 'Collector', 'Assigned route and collection operations'),
    ('employee', 'Employee', 'Internal employee tools'),
    ('management', 'Management', 'Management dashboards and administrative functions')
ON CONFLICT (code) DO NOTHING;

INSERT INTO core.permissions (code, description)
VALUES
    ('loan.self.view', 'View the signed-in client loan information'),
    ('route.view', 'View assigned collector routes'),
    ('collection.create', 'Submit collector payment, ADV, and PASS entries'),
    ('employee.portal.view', 'Access employee tools'),
    ('management.dashboard.view', 'Access management dashboards')
ON CONFLICT (code) DO NOTHING;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT r.id, p.code
FROM (VALUES
    ('client', 'loan.self.view'),
    ('collector', 'route.view'),
    ('collector', 'collection.create'),
    ('employee', 'employee.portal.view'),
    ('management', 'management.dashboard.view')
) AS mapping(role_code, permission_code)
JOIN core.roles r ON r.code = mapping.role_code
JOIN core.permissions p ON p.code = mapping.permission_code
ON CONFLICT DO NOTHING;

COMMIT;
