BEGIN;

-- Stage 5E.4.6A creates the audit foundation for activating contractual mobile
-- allocation one loan at a time. This migration creates no activation events,
-- does not change any loan schedule, and does not enable collection behavior.

INSERT INTO core.permissions (code, description)
VALUES (
    'lending.contract_collection.activate',
    'Explicitly activate or deactivate verified contractual mobile allocation for one loan at a time'
)
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code = 'lending.contract_collection.activate'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS lending.loan_contract_collection_activation_events (
    id BIGSERIAL PRIMARY KEY,
    loan_id UUID NOT NULL
        REFERENCES lending.loans(id) ON DELETE RESTRICT,
    schedule_id UUID NOT NULL
        REFERENCES lending.loan_contract_schedules(id) ON DELETE RESTRICT,
    event_action TEXT NOT NULL CHECK (event_action IN ('activate', 'deactivate')),
    activation_note TEXT NOT NULL CHECK (btrim(activation_note) <> ''),
    acted_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    acted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS lending_contract_collection_activation_loan_idx
    ON lending.loan_contract_collection_activation_events(
        loan_id, acted_at DESC, id DESC
    );

CREATE INDEX IF NOT EXISTS lending_contract_collection_activation_schedule_idx
    ON lending.loan_contract_collection_activation_events(schedule_id);

CREATE OR REPLACE FUNCTION lending.validate_contract_collection_activation_event()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    schedule_loan_id UUID;
    schedule_status TEXT;
BEGIN
    SELECT schedule.loan_id, schedule.status
      INTO schedule_loan_id, schedule_status
    FROM lending.loan_contract_schedules schedule
    WHERE schedule.id = NEW.schedule_id;

    IF schedule_loan_id IS NULL THEN
        RAISE EXCEPTION 'Contract collection activation requires an existing contractual schedule.';
    END IF;

    IF schedule_loan_id IS DISTINCT FROM NEW.loan_id THEN
        RAISE EXCEPTION 'Contract collection activation schedule must belong to the same loan.';
    END IF;

    IF NEW.event_action = 'activate' THEN
        IF schedule_status <> 'active' THEN
            RAISE EXCEPTION 'Only the current active contractual schedule may be activated for collection.';
        END IF;

        IF NOT EXISTS (
            SELECT 1
            FROM lending.loan_contract_schedule_registrations registration
            WHERE registration.schedule_id = NEW.schedule_id
        ) THEN
            RAISE EXCEPTION 'Contract collection activation requires a verified signed-contract schedule registration.';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_contract_collection_activation_validate
    ON lending.loan_contract_collection_activation_events;
CREATE TRIGGER lending_contract_collection_activation_validate
BEFORE INSERT ON lending.loan_contract_collection_activation_events
FOR EACH ROW EXECUTE FUNCTION lending.validate_contract_collection_activation_event();

CREATE OR REPLACE FUNCTION lending.guard_contract_collection_activation_audit()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Contract collection activation events are immutable; append a new activation or deactivation event instead.';
END;
$$;

DROP TRIGGER IF EXISTS lending_contract_collection_activation_audit_guard
    ON lending.loan_contract_collection_activation_events;
CREATE TRIGGER lending_contract_collection_activation_audit_guard
BEFORE UPDATE OR DELETE ON lending.loan_contract_collection_activation_events
FOR EACH ROW EXECUTE FUNCTION lending.guard_contract_collection_activation_audit();

CREATE OR REPLACE VIEW lending.loan_contract_collection_activation_state AS
SELECT DISTINCT ON (event.loan_id)
    event.id AS event_id,
    event.loan_id,
    event.schedule_id,
    event.event_action,
    (event.event_action = 'activate') AS is_active,
    event.activation_note,
    event.acted_by_user_id,
    event.acted_at
FROM lending.loan_contract_collection_activation_events event
ORDER BY event.loan_id, event.acted_at DESC, event.id DESC;

COMMENT ON TABLE lending.loan_contract_collection_activation_events IS
    'Immutable per-loan contractual collection activation/deactivation audit. Migration 0036 creates no activation rows; activation requires a later explicit Management action.';
COMMENT ON VIEW lending.loan_contract_collection_activation_state IS
    'Latest immutable contractual collection activation state per loan. This view alone does not change collection behavior until the application is explicitly wired to it.';

COMMIT;
