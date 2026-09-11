BEGIN;

CREATE SEQUENCE IF NOT EXISTS lending.client_onboarding_reference_seq;

CREATE TABLE IF NOT EXISTS lending.client_onboarding_applicants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_reference TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'requirements_incomplete'
        CHECK (status IN (
            'requirements_incomplete',
            'under_verification',
            'eligible_for_cif',
            'requirements_rejected'
        )),
    full_name TEXT NOT NULL,
    phone_number TEXT NOT NULL,
    email TEXT,
    present_address TEXT NOT NULL,
    national_id_egov_evidence_reference TEXT NOT NULL,
    national_id_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (national_id_status IN ('pending', 'passed', 'failed')),
    tin_id_egov_evidence_reference TEXT NOT NULL,
    tin_id_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (tin_id_status IN ('pending', 'passed', 'failed')),
    meralco_bill_evidence_reference TEXT NOT NULL,
    meralco_bill_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (meralco_bill_status IN ('pending', 'passed', 'failed')),
    collector_visit_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (collector_visit_status IN ('pending', 'passed', 'failed')),
    collector_visit_evidence_reference TEXT,
    collector_visit_note TEXT NOT NULL DEFAULT '',
    collector_visit_by_user_id UUID REFERENCES core.users(id) ON DELETE SET NULL,
    collector_visit_completed_at TIMESTAMPTZ,
    eligibility_reviewed_by_user_id UUID REFERENCES core.users(id) ON DELETE SET NULL,
    eligibility_reviewed_at TIMESTAMPTZ,
    bypassed_requirements TEXT[] NOT NULL DEFAULT '{}'::text[],
    bypass_reason TEXT,
    bypassed_by_user_id UUID REFERENCES core.users(id) ON DELETE SET NULL,
    bypassed_at TIMESTAMPTZ,
    promoted_client_id UUID UNIQUE REFERENCES lending.clients(id) ON DELETE RESTRICT,
    privacy_consent BOOLEAN NOT NULL CHECK (privacy_consent),
    accuracy_declaration BOOLEAN NOT NULL CHECK (accuracy_declaration),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (btrim(application_reference) <> ''),
    CHECK (btrim(full_name) <> ''),
    CHECK (btrim(phone_number) <> ''),
    CHECK (btrim(present_address) <> ''),
    CHECK (
        cardinality(bypassed_requirements) = 0
        OR (
            btrim(coalesce(bypass_reason, '')) <> ''
            AND bypassed_by_user_id IS NOT NULL
            AND bypassed_at IS NOT NULL
        )
    ),
    CHECK (status <> 'eligible_for_cif' OR promoted_client_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS lending_client_onboarding_status_created_idx
    ON lending.client_onboarding_applicants(status, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS lending_client_onboarding_reference_lower_uidx
    ON lending.client_onboarding_applicants(lower(application_reference));

INSERT INTO core.permissions (code, description)
VALUES
    (
        'client_onboarding.requirement.review',
        'Review normal pre-CIF onboarding requirements'
    ),
    (
        'client_onboarding.visit.record',
        'Record the Collector residence visit'
    ),
    (
        'client_onboarding.bypass',
        'Bypass pre-CIF requirements as Management'
    )
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT r.id, p.code
FROM (VALUES
    ('employee', 'client_onboarding.requirement.review'),
    ('management', 'client_onboarding.requirement.review'),
    ('collector', 'client_onboarding.visit.record'),
    ('management', 'client_onboarding.bypass')
) AS mapping(role_code, permission_code)
JOIN core.roles r ON r.code = mapping.role_code
JOIN core.permissions p ON p.code = mapping.permission_code
ON CONFLICT DO NOTHING;

COMMIT;
