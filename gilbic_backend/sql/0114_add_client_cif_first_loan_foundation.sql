BEGIN;

CREATE TABLE IF NOT EXISTS lending.client_cif_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'active', 'superseded')),

    full_name TEXT NOT NULL,
    phone_number TEXT NOT NULL,
    email TEXT,
    present_address TEXT NOT NULL,

    national_id_egov_evidence_reference TEXT,
    tin_id_egov_evidence_reference TEXT,
    meralco_bill_evidence_reference TEXT,

    baseline_face_scan_evidence_reference TEXT,
    baseline_liveness_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (baseline_liveness_status IN ('pending', 'passed', 'failed')),

    activated_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    review_due_at TIMESTAMPTZ,
    reverification_required_at TIMESTAMPTZ,
    reverification_reason TEXT,

    created_by_user_id UUID REFERENCES core.users(id) ON DELETE SET NULL,
    activated_by_user_id UUID REFERENCES core.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (client_id, version_number),
    CHECK (btrim(full_name) <> ''),
    CHECK (btrim(phone_number) <> ''),
    CHECK (btrim(present_address) <> ''),
    CHECK (
        status <> 'active'
        OR (
            baseline_liveness_status = 'passed'
            AND baseline_face_scan_evidence_reference IS NOT NULL
            AND activated_at IS NOT NULL
            AND expires_at IS NOT NULL
            AND review_due_at IS NOT NULL
        )
    ),
    CHECK (expires_at IS NULL OR activated_at IS NULL OR expires_at > activated_at),
    CHECK (review_due_at IS NULL OR expires_at IS NULL OR review_due_at <= expires_at),
    CHECK (
        reverification_required_at IS NULL
        OR btrim(coalesce(reverification_reason, '')) <> ''
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS lending_client_cif_versions_one_current_uidx
    ON lending.client_cif_versions(client_id)
    WHERE is_current;

CREATE INDEX IF NOT EXISTS lending_client_cif_versions_status_review_idx
    ON lending.client_cif_versions(status, review_due_at)
    WHERE is_current;

COMMIT;
