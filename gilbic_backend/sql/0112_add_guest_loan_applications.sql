BEGIN;

CREATE SEQUENCE IF NOT EXISTS lending.guest_loan_application_reference_seq;

CREATE TABLE IF NOT EXISTS lending.guest_loan_applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_reference TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'submitted'
        CHECK (status IN ('submitted', 'under_review', 'approved', 'rejected')),
    full_name TEXT NOT NULL,
    phone_number TEXT NOT NULL,
    email TEXT,
    present_address TEXT NOT NULL,
    permanent_address TEXT NOT NULL,
    livelihood_type TEXT NOT NULL,
    livelihood_details TEXT,
    declared_monthly_income NUMERIC(18,2) NOT NULL
        CHECK (declared_monthly_income >= 0),
    declared_monthly_expenses NUMERIC(18,2) NOT NULL
        CHECK (declared_monthly_expenses >= 0),
    declared_monthly_debt_payments NUMERIC(18,2) NOT NULL
        CHECK (declared_monthly_debt_payments >= 0),
    requested_loan_type TEXT NOT NULL
        CHECK (requested_loan_type IN ('regular', '7x7')),
    requested_amount NUMERIC(18,2) NOT NULL CHECK (requested_amount > 0),
    requested_term_days INTEGER NOT NULL CHECK (requested_term_days > 0),
    loan_purpose TEXT NOT NULL,
    national_id_evidence_reference TEXT NOT NULL,
    tin_id_evidence_reference TEXT NOT NULL,
    selfie_evidence_reference TEXT NOT NULL,
    privacy_consent BOOLEAN NOT NULL CHECK (privacy_consent),
    accuracy_declaration BOOLEAN NOT NULL CHECK (accuracy_declaration),
    applicant_status_note TEXT,
    internal_review_note TEXT,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    review_started_at TIMESTAMPTZ,
    reviewed_at TIMESTAMPTZ,
    reviewed_by_user_id UUID REFERENCES core.users(id) ON DELETE SET NULL,
    promoted_client_id UUID UNIQUE REFERENCES lending.clients(id) ON DELETE RESTRICT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (btrim(application_reference) <> ''),
    CHECK (btrim(full_name) <> ''),
    CHECK (btrim(phone_number) <> '')
);

CREATE INDEX IF NOT EXISTS lending_guest_loan_applications_status_submitted_idx
    ON lending.guest_loan_applications(status, submitted_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS lending_guest_loan_applications_reference_lower_uidx
    ON lending.guest_loan_applications(lower(application_reference));

INSERT INTO core.permissions (code, description)
VALUES (
    'loan_application.manage',
    'Review and decide guest loan applications'
)
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT r.id, p.code
FROM (VALUES
    ('management', 'loan_application.manage')
) AS mapping(role_code, permission_code)
JOIN core.roles r ON r.code = mapping.role_code
JOIN core.permissions p ON p.code = mapping.permission_code
ON CONFLICT DO NOTHING;

COMMIT;
