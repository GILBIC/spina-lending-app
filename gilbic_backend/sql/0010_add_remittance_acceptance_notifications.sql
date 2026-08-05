BEGIN;

ALTER TABLE lending.collection_remittances
    ADD COLUMN IF NOT EXISTS custody_user_id UUID
        REFERENCES core.users(id) ON DELETE RESTRICT;
ALTER TABLE lending.collection_remittances
    ADD COLUMN IF NOT EXISTS custody_transferred_at TIMESTAMPTZ;

UPDATE lending.collection_remittances
SET custody_user_id = recipient_user_id,
    custody_transferred_at = received_at
WHERE status = 'received'
  AND (custody_user_id IS NULL OR custody_transferred_at IS NULL);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'collection_remittance_custody_state_check'
          AND conrelid = 'lending.collection_remittances'::regclass
    ) THEN
        ALTER TABLE lending.collection_remittances
            ADD CONSTRAINT collection_remittance_custody_state_check
            CHECK (
                (status = 'submitted'
                    AND custody_user_id IS NULL
                    AND custody_transferred_at IS NULL)
                OR
                (status = 'received'
                    AND custody_user_id = recipient_user_id
                    AND custody_transferred_at IS NOT NULL
                    AND custody_transferred_at = received_at)
            );
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS core.user_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    sender_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    remittance_id UUID NOT NULL UNIQUE
        REFERENCES lending.collection_remittances(id) ON DELETE RESTRICT,
    notification_type TEXT NOT NULL DEFAULT 'remittance_acceptance'
        CHECK (notification_type = 'remittance_acceptance'),
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    action_code TEXT NOT NULL DEFAULT 'accept_remittance'
        CHECK (action_code = 'accept_remittance'),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    read_at TIMESTAMPTZ,
    accepted_at TIMESTAMPTZ,
    CHECK (
        (status = 'pending' AND accepted_at IS NULL)
        OR
        (status = 'accepted' AND accepted_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS core_user_notifications_recipient_status_idx
    ON core.user_notifications (recipient_user_id, status, created_at DESC);

INSERT INTO core.user_notifications (
    recipient_user_id,
    sender_user_id,
    remittance_id,
    title,
    message,
    status,
    created_at,
    read_at,
    accepted_at
)
SELECT
    remittance.recipient_user_id,
    remittance.collector_user_id,
    remittance.id,
    'Remittance awaiting acceptance',
    format(
        '%s sent remittance %s for PHP %s. Accept only after the cash is physically received.',
        collector.full_name,
        remittance.remittance_number,
        to_char(remittance.total_amount, 'FM999999999999990.00')
    ),
    CASE WHEN remittance.status = 'received' THEN 'accepted' ELSE 'pending' END,
    remittance.submitted_at,
    CASE WHEN remittance.status = 'received' THEN remittance.received_at ELSE NULL END,
    CASE WHEN remittance.status = 'received' THEN remittance.received_at ELSE NULL END
FROM lending.collection_remittances remittance
JOIN core.users collector ON collector.id = remittance.collector_user_id
ON CONFLICT (remittance_id) DO NOTHING;

CREATE OR REPLACE FUNCTION lending.prepare_remittance_custody_transfer()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.status = 'received' AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'An accepted remittance is permanently closed.'
            USING ERRCODE = '55000';
    END IF;

    IF OLD.status = 'submitted' AND NEW.status = 'received' THEN
        IF NEW.received_by_user_id IS DISTINCT FROM OLD.recipient_user_id THEN
            RAISE EXCEPTION 'Only the selected remittance recipient may accept custody.'
                USING ERRCODE = '42501';
        END IF;
        IF NEW.received_at IS NULL THEN
            RAISE EXCEPTION 'Remittance acceptance requires a server timestamp.'
                USING ERRCODE = '23514';
        END IF;
        NEW.custody_user_id := OLD.recipient_user_id;
        NEW.custody_transferred_at := NEW.received_at;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_collection_remittance_custody_guard
    ON lending.collection_remittances;
CREATE TRIGGER lending_collection_remittance_custody_guard
BEFORE UPDATE ON lending.collection_remittances
FOR EACH ROW
EXECUTE FUNCTION lending.prepare_remittance_custody_transfer();

CREATE OR REPLACE FUNCTION core.create_remittance_acceptance_notification()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    collector_name TEXT;
BEGIN
    SELECT full_name
    INTO collector_name
    FROM core.users
    WHERE id = NEW.collector_user_id;

    INSERT INTO core.user_notifications (
        recipient_user_id,
        sender_user_id,
        remittance_id,
        title,
        message,
        created_at
    ) VALUES (
        NEW.recipient_user_id,
        NEW.collector_user_id,
        NEW.id,
        'Remittance awaiting acceptance',
        format(
            '%s sent remittance %s for PHP %s. Accept only after the cash is physically received.',
            coalesce(collector_name, 'A collector'),
            NEW.remittance_number,
            to_char(NEW.total_amount, 'FM999999999999990.00')
        ),
        NEW.submitted_at
    )
    ON CONFLICT (remittance_id) DO NOTHING;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_collection_remittance_notification_create
    ON lending.collection_remittances;
CREATE TRIGGER lending_collection_remittance_notification_create
AFTER INSERT ON lending.collection_remittances
FOR EACH ROW
EXECUTE FUNCTION core.create_remittance_acceptance_notification();

CREATE OR REPLACE FUNCTION core.complete_remittance_acceptance_notification()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.status = 'submitted' AND NEW.status = 'received' THEN
        UPDATE core.user_notifications
        SET status = 'accepted',
            read_at = coalesce(read_at, NEW.received_at),
            accepted_at = NEW.received_at
        WHERE remittance_id = NEW.id
          AND recipient_user_id = NEW.recipient_user_id;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_collection_remittance_notification_complete
    ON lending.collection_remittances;
CREATE TRIGGER lending_collection_remittance_notification_complete
AFTER UPDATE OF status ON lending.collection_remittances
FOR EACH ROW
EXECUTE FUNCTION core.complete_remittance_acceptance_notification();

COMMENT ON TABLE core.user_notifications IS
    'Actionable in-app notifications. Accepting a remittance transfers cash custody to the selected recipient.';
COMMENT ON COLUMN lending.collection_remittances.custody_user_id IS
    'The user currently accountable for the remitted cash after recipient acceptance.';
COMMENT ON COLUMN lending.collection_remittances.custody_transferred_at IS
    'Server timestamp when the selected recipient accepted the remittance and cash custody.';

COMMIT;
