BEGIN;

-- Stage 5E.4.3 adds an explicit Management gate for registering verified
-- signed-contract schedules. It does not backfill or infer schedules for any
-- existing loan and it does not classify credit risk, calculate ECL, or post GL.

INSERT INTO core.permissions (code, description)
VALUES (
    'lending.contract_schedule.manage',
    'Preview and explicitly register verified signed-contract payment schedules without automatic credit-risk or accounting posting'
)
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code = 'lending.contract_schedule.manage'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS lending.loan_contract_schedule_registrations (
    id BIGSERIAL PRIMARY KEY,
    schedule_id UUID NOT NULL UNIQUE
        REFERENCES lending.loan_contract_schedules(id) ON DELETE RESTRICT,
    evidence_basis TEXT NOT NULL CHECK (
        evidence_basis IN (
            'signed_contract',
            'signed_renewal_contract',
            'signed_restructure_contract'
        )
    ),
    evidence_reference TEXT NOT NULL CHECK (btrim(evidence_reference) <> ''),
    verification_note TEXT NOT NULL CHECK (btrim(verification_note) <> ''),
    verified_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    verified_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS lending_contract_schedule_registration_verified_idx
    ON lending.loan_contract_schedule_registrations(verified_at DESC);

CREATE OR REPLACE FUNCTION lending.guard_contract_schedule_registration_audit()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Verified contract schedule registration records are immutable.';
END;
$$;

DROP TRIGGER IF EXISTS lending_contract_schedule_registration_audit_guard
    ON lending.loan_contract_schedule_registrations;
CREATE TRIGGER lending_contract_schedule_registration_audit_guard
BEFORE UPDATE OR DELETE ON lending.loan_contract_schedule_registrations
FOR EACH ROW EXECUTE FUNCTION lending.guard_contract_schedule_registration_audit();

-- Contractual installment rows are evidence of the exact signed schedule and
-- cannot be edited or deleted after registration. A corrected contract must be
-- represented by a new schedule version instead.
CREATE OR REPLACE FUNCTION lending.guard_contract_installment_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Contractual installment rows are immutable; create a superseding verified schedule instead.';
END;
$$;

DROP TRIGGER IF EXISTS lending_contract_installment_immutability_guard
    ON lending.loan_contract_installments;
CREATE TRIGGER lending_contract_installment_immutability_guard
BEFORE UPDATE OR DELETE ON lending.loan_contract_installments
FOR EACH ROW EXECUTE FUNCTION lending.guard_contract_installment_immutability();

-- Schedule terms are also immutable. The only permitted mutation is the
-- explicit active -> superseded status transition used by a later verified
-- contract version. All prior terms remain available as historical evidence.
CREATE OR REPLACE FUNCTION lending.guard_contract_schedule_terms()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Contract schedules cannot be deleted.';
    END IF;

    IF NEW.loan_id IS DISTINCT FROM OLD.loan_id
       OR NEW.schedule_version IS DISTINCT FROM OLD.schedule_version
       OR NEW.payment_frequency IS DISTINCT FROM OLD.payment_frequency
       OR NEW.contract_reference IS DISTINCT FROM OLD.contract_reference
       OR NEW.contract_signed_date IS DISTINCT FROM OLD.contract_signed_date
       OR NEW.effective_from IS DISTINCT FROM OLD.effective_from
       OR NEW.grace_days IS DISTINCT FROM OLD.grace_days
       OR NEW.settings IS DISTINCT FROM OLD.settings
       OR NEW.supersedes_schedule_id IS DISTINCT FROM OLD.supersedes_schedule_id
       OR NEW.created_by_user_id IS DISTINCT FROM OLD.created_by_user_id
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Verified contract schedule terms are immutable; create a superseding schedule instead.';
    END IF;

    IF NEW.status IS DISTINCT FROM OLD.status
       AND NOT (OLD.status = 'active' AND NEW.status = 'superseded') THEN
        RAISE EXCEPTION 'Contract schedule status may only transition from active to superseded.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_contract_schedule_terms_guard
    ON lending.loan_contract_schedules;
CREATE TRIGGER lending_contract_schedule_terms_guard
BEFORE UPDATE OR DELETE ON lending.loan_contract_schedules
FOR EACH ROW EXECUTE FUNCTION lending.guard_contract_schedule_terms();

COMMIT;
