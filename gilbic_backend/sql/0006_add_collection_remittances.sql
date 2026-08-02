BEGIN;

INSERT INTO core.permissions (code, description)
VALUES
    ('collection.correct.own_unremitted', 'Correct the signed-in collector''s own unlocked collection entries'),
    ('collection.correct.locked', 'Create an audited supervisor adjustment for a locked collection entry'),
    ('remittance.create', 'Create and submit a collector remittance'),
    ('remittance.receive', 'Receive and confirm collector remittances'),
    ('remittance.view', 'View collector remittance summaries')
ON CONFLICT (code) DO NOTHING;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT r.id, p.code
FROM (VALUES
    ('collector', 'collection.correct.own_unremitted'),
    ('collector', 'remittance.create'),
    ('collector', 'remittance.view'),
    ('employee', 'remittance.receive'),
    ('employee', 'remittance.view'),
    ('management', 'collection.correct.locked'),
    ('management', 'remittance.receive'),
    ('management', 'remittance.view')
) AS mapping(role_code, permission_code)
JOIN core.roles r ON r.code = mapping.role_code
JOIN core.permissions p ON p.code = mapping.permission_code
ON CONFLICT DO NOTHING;

CREATE SEQUENCE IF NOT EXISTS lending.collection_remittance_sequence
    AS BIGINT
    START WITH 1
    INCREMENT BY 1
    NO CYCLE;

CREATE TABLE IF NOT EXISTS lending.collection_remittances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    remittance_number TEXT NOT NULL UNIQUE,
    collector_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    recipient_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    collection_date DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'submitted'
        CHECK (status IN ('submitted', 'received')),
    transaction_count INTEGER NOT NULL CHECK (transaction_count >= 0),
    payment_count INTEGER NOT NULL CHECK (payment_count >= 0),
    unable_to_pay_count INTEGER NOT NULL CHECK (unable_to_pay_count >= 0),
    covered_payment_count INTEGER NOT NULL CHECK (covered_payment_count >= 0),
    client_count INTEGER NOT NULL CHECK (client_count >= 0),
    total_amount NUMERIC(18,2) NOT NULL CHECK (total_amount >= 0),
    note TEXT NOT NULL DEFAULT '',
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    received_at TIMESTAMPTZ,
    received_by_user_id UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (collector_user_id <> recipient_user_id),
    CHECK (
        (status = 'submitted' AND received_at IS NULL AND received_by_user_id IS NULL)
        OR
        (status = 'received' AND received_at IS NOT NULL AND received_by_user_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS lending_collection_remittance_collector_date_idx
    ON lending.collection_remittances (collector_user_id, collection_date DESC, submitted_at DESC);
CREATE INDEX IF NOT EXISTS lending_collection_remittance_recipient_status_idx
    ON lending.collection_remittances (recipient_user_id, status, submitted_at DESC);

ALTER TABLE lending.collection_transactions
    ADD COLUMN IF NOT EXISTS remittance_id UUID
        REFERENCES lending.collection_remittances(id) ON DELETE RESTRICT;
ALTER TABLE lending.collection_transactions
    ADD COLUMN IF NOT EXISTS is_locked BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE lending.collection_transactions
    ADD COLUMN IF NOT EXISTS locked_at TIMESTAMPTZ;
ALTER TABLE lending.collection_transactions
    ADD COLUMN IF NOT EXISTS locked_by_user_id UUID
        REFERENCES core.users(id) ON DELETE RESTRICT;
ALTER TABLE lending.collection_transactions
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE lending.collection_transactions
    ADD COLUMN IF NOT EXISTS updated_by_user_id UUID
        REFERENCES core.users(id) ON DELETE RESTRICT;
ALTER TABLE lending.collection_transactions
    ADD COLUMN IF NOT EXISTS edit_version BIGINT NOT NULL DEFAULT 0
        CHECK (edit_version >= 0);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'collection_transactions_lock_state_check'
          AND conrelid = 'lending.collection_transactions'::regclass
    ) THEN
        ALTER TABLE lending.collection_transactions
            ADD CONSTRAINT collection_transactions_lock_state_check
            CHECK (
                (is_locked = false
                    AND remittance_id IS NULL
                    AND locked_at IS NULL
                    AND locked_by_user_id IS NULL)
                OR
                (is_locked = true
                    AND remittance_id IS NOT NULL
                    AND locked_at IS NOT NULL
                    AND locked_by_user_id IS NOT NULL)
            );
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS lending_collection_transaction_unremitted_idx
    ON lending.collection_transactions (collector_user_id, collection_date, accepted_at)
    WHERE remittance_id IS NULL AND is_locked = false;
CREATE INDEX IF NOT EXISTS lending_collection_transaction_remittance_idx
    ON lending.collection_transactions (remittance_id)
    WHERE remittance_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS lending.collection_remittance_items (
    remittance_id UUID NOT NULL
        REFERENCES lending.collection_remittances(id) ON DELETE RESTRICT,
    transaction_id UUID NOT NULL UNIQUE
        REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    collection_date DATE NOT NULL,
    entry_type TEXT NOT NULL CHECK (entry_type IN ('payment', 'advance', 'pass')),
    amount NUMERIC(18,2) NOT NULL CHECK (amount >= 0),
    receipt_number TEXT NOT NULL,
    transaction_snapshot JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (remittance_id, transaction_id)
);

CREATE INDEX IF NOT EXISTS lending_collection_remittance_items_client_idx
    ON lending.collection_remittance_items (client_id, collection_date DESC);

CREATE TABLE IF NOT EXISTS lending.collection_covered_dates (
    transaction_id UUID NOT NULL
        REFERENCES lending.collection_transactions(id) ON DELETE CASCADE,
    covered_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (transaction_id, covered_date)
);

CREATE INDEX IF NOT EXISTS lending_collection_covered_date_idx
    ON lending.collection_covered_dates (covered_date, transaction_id);

CREATE TABLE IF NOT EXISTS lending.collection_transaction_edits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL
        REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    edited_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    edit_version BIGINT NOT NULL CHECK (edit_version > 0),
    reason TEXT NOT NULL CHECK (btrim(reason) <> ''),
    previous_snapshot JSONB NOT NULL,
    replacement_snapshot JSONB NOT NULL,
    edited_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (transaction_id, edit_version)
);

CREATE INDEX IF NOT EXISTS lending_collection_transaction_edits_actor_idx
    ON lending.collection_transaction_edits (edited_by_user_id, edited_at DESC);

CREATE OR REPLACE FUNCTION lending.prevent_locked_collection_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.is_locked THEN
        IF NEW.amount IS DISTINCT FROM OLD.amount
           OR NEW.entry_type IS DISTINCT FROM OLD.entry_type
           OR NEW.collection_date IS DISTINCT FROM OLD.collection_date
           OR NEW.advance_from IS DISTINCT FROM OLD.advance_from
           OR NEW.advance_until IS DISTINCT FROM OLD.advance_until
           OR NEW.note IS DISTINCT FROM OLD.note
           OR NEW.previous_balance IS DISTINCT FROM OLD.previous_balance
           OR NEW.official_balance IS DISTINCT FROM OLD.official_balance
           OR NEW.pass_count_after IS DISTINCT FROM OLD.pass_count_after
           OR NEW.advance_until_after IS DISTINCT FROM OLD.advance_until_after
           OR NEW.collector_user_id IS DISTINCT FROM OLD.collector_user_id
           OR NEW.remittance_id IS DISTINCT FROM OLD.remittance_id
           OR NEW.is_locked IS DISTINCT FROM OLD.is_locked
           OR NEW.locked_at IS DISTINCT FROM OLD.locked_at
           OR NEW.locked_by_user_id IS DISTINCT FROM OLD.locked_by_user_id THEN
            RAISE EXCEPTION 'Remitted collection transactions are locked and cannot be edited.'
                USING ERRCODE = '55000';
        END IF;
    END IF;

    IF OLD.remittance_id IS NOT NULL
       AND NEW.remittance_id IS DISTINCT FROM OLD.remittance_id THEN
        RAISE EXCEPTION 'A collection transaction cannot be moved to another remittance.'
            USING ERRCODE = '55000';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_collection_transaction_lock_guard
    ON lending.collection_transactions;
CREATE TRIGGER lending_collection_transaction_lock_guard
BEFORE UPDATE ON lending.collection_transactions
FOR EACH ROW
EXECUTE FUNCTION lending.prevent_locked_collection_mutation();

CREATE OR REPLACE FUNCTION lending.prevent_locked_covered_date_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_transaction_id UUID;
    transaction_locked BOOLEAN;
BEGIN
    target_transaction_id := COALESCE(NEW.transaction_id, OLD.transaction_id);

    SELECT is_locked
    INTO transaction_locked
    FROM lending.collection_transactions
    WHERE id = target_transaction_id;

    IF transaction_locked THEN
        RAISE EXCEPTION 'Covered dates for a remitted collection are locked.'
            USING ERRCODE = '55000';
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$;

DROP TRIGGER IF EXISTS lending_collection_covered_date_lock_guard
    ON lending.collection_covered_dates;
CREATE TRIGGER lending_collection_covered_date_lock_guard
BEFORE INSERT OR UPDATE OR DELETE ON lending.collection_covered_dates
FOR EACH ROW
EXECUTE FUNCTION lending.prevent_locked_covered_date_mutation();

COMMENT ON TABLE lending.collection_remittances IS
    'Server-calculated collector cash handovers. Submitting locks every included collection transaction.';
COMMENT ON TABLE lending.collection_transaction_edits IS
    'Append-only audit snapshots for corrections made before remittance or by authorized management afterward.';
COMMENT ON TABLE lending.collection_covered_dates IS
    'Exact individually selected dates covered by one payment; advance_from and advance_until remain compatibility bounds.';

COMMIT;
