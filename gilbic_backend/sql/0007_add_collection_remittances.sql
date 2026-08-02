BEGIN;

INSERT INTO core.permissions (code, description)
VALUES
    ('collection.correct.current_custody', 'Create an audited correction while the signed-in user is the current collection custodian'),
    ('collection.correct.finalized', 'Create an authorized management adjustment after final remittance acceptance'),
    ('remittance.create', 'Create and submit a collection custody transfer'),
    ('remittance.receive', 'Receive and confirm a collection custody transfer'),
    ('remittance.finalize', 'Finalize a collection remittance and permanently close collector editing'),
    ('remittance.view', 'View collection remittance summaries and custody history')
ON CONFLICT (code) DO NOTHING;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT r.id, p.code
FROM (VALUES
    ('collector', 'collection.correct.current_custody'),
    ('collector', 'remittance.create'),
    ('collector', 'remittance.receive'),
    ('collector', 'remittance.view'),
    ('employee', 'remittance.receive'),
    ('employee', 'remittance.finalize'),
    ('employee', 'remittance.view'),
    ('management', 'collection.correct.finalized'),
    ('management', 'remittance.receive'),
    ('management', 'remittance.finalize'),
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
    sender_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    recipient_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    collection_date DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'submitted'
        CHECK (status IN ('submitted', 'received', 'finalized')),
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
    finalized_at TIMESTAMPTZ,
    finalized_by_user_id UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (sender_user_id <> recipient_user_id),
    CHECK (
        (status = 'submitted'
            AND received_at IS NULL
            AND received_by_user_id IS NULL
            AND finalized_at IS NULL
            AND finalized_by_user_id IS NULL)
        OR
        (status = 'received'
            AND received_at IS NOT NULL
            AND received_by_user_id IS NOT NULL
            AND finalized_at IS NULL
            AND finalized_by_user_id IS NULL)
        OR
        (status = 'finalized'
            AND received_at IS NOT NULL
            AND received_by_user_id IS NOT NULL
            AND finalized_at IS NOT NULL
            AND finalized_by_user_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS lending_collection_remittance_sender_date_idx
    ON lending.collection_remittances (sender_user_id, collection_date DESC, submitted_at DESC);
CREATE INDEX IF NOT EXISTS lending_collection_remittance_recipient_status_idx
    ON lending.collection_remittances (recipient_user_id, status, submitted_at DESC);

ALTER TABLE lending.collection_transactions
    ADD COLUMN IF NOT EXISTS current_custodian_user_id UUID
        REFERENCES core.users(id) ON DELETE RESTRICT;
ALTER TABLE lending.collection_transactions
    ADD COLUMN IF NOT EXISTS custody_state TEXT NOT NULL DEFAULT 'held';
ALTER TABLE lending.collection_transactions
    ADD COLUMN IF NOT EXISTS active_remittance_id UUID
        REFERENCES lending.collection_remittances(id) ON DELETE RESTRICT;
ALTER TABLE lending.collection_transactions
    ADD COLUMN IF NOT EXISTS custody_version BIGINT NOT NULL DEFAULT 0;
ALTER TABLE lending.collection_transactions
    ADD COLUMN IF NOT EXISTS effective_edit_version BIGINT NOT NULL DEFAULT 0;
ALTER TABLE lending.collection_transactions
    ADD COLUMN IF NOT EXISTS custody_updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

UPDATE lending.collection_transactions
SET current_custodian_user_id = collector_user_id
WHERE current_custodian_user_id IS NULL;

CREATE OR REPLACE FUNCTION lending.initialize_collection_custodian()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.current_custodian_user_id IS NULL THEN
        NEW.current_custodian_user_id := NEW.collector_user_id;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_collection_initialize_custodian
    ON lending.collection_transactions;
CREATE TRIGGER lending_collection_initialize_custodian
BEFORE INSERT ON lending.collection_transactions
FOR EACH ROW
EXECUTE FUNCTION lending.initialize_collection_custodian();

ALTER TABLE lending.collection_transactions
    ALTER COLUMN current_custodian_user_id SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'collection_transactions_custody_state_check'
          AND conrelid = 'lending.collection_transactions'::regclass
    ) THEN
        ALTER TABLE lending.collection_transactions
            ADD CONSTRAINT collection_transactions_custody_state_check
            CHECK (custody_state IN ('held', 'finalized'));
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'collection_transactions_custody_version_check'
          AND conrelid = 'lending.collection_transactions'::regclass
    ) THEN
        ALTER TABLE lending.collection_transactions
            ADD CONSTRAINT collection_transactions_custody_version_check
            CHECK (custody_version >= 0 AND effective_edit_version >= 0);
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS lending_collection_transaction_custodian_idx
    ON lending.collection_transactions (
        current_custodian_user_id,
        custody_state,
        collection_date,
        accepted_at
    );
CREATE INDEX IF NOT EXISTS lending_collection_transaction_active_remittance_idx
    ON lending.collection_transactions (active_remittance_id)
    WHERE active_remittance_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS lending.collection_remittance_items (
    remittance_id UUID NOT NULL
        REFERENCES lending.collection_remittances(id) ON DELETE RESTRICT,
    transaction_id UUID NOT NULL
        REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    from_custodian_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    to_custodian_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    collection_date DATE NOT NULL,
    entry_type TEXT NOT NULL CHECK (entry_type IN ('payment', 'advance', 'pass')),
    amount NUMERIC(18,2) NOT NULL CHECK (amount >= 0),
    receipt_number TEXT NOT NULL,
    effective_edit_version BIGINT NOT NULL CHECK (effective_edit_version >= 0),
    transaction_snapshot JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (remittance_id, transaction_id),
    CHECK (from_custodian_user_id <> to_custodian_user_id)
);

CREATE INDEX IF NOT EXISTS lending_collection_remittance_items_transaction_idx
    ON lending.collection_remittance_items (transaction_id, created_at DESC);
CREATE INDEX IF NOT EXISTS lending_collection_remittance_items_client_idx
    ON lending.collection_remittance_items (client_id, collection_date DESC);

CREATE TABLE IF NOT EXISTS lending.collection_covered_dates (
    transaction_id UUID NOT NULL
        REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    covered_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (transaction_id, covered_date),
    UNIQUE (loan_id, covered_date)
);

CREATE INDEX IF NOT EXISTS lending_collection_covered_date_idx
    ON lending.collection_covered_dates (covered_date, transaction_id);

CREATE TABLE IF NOT EXISTS lending.collection_transaction_edits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL
        REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    edited_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    custodian_user_id_at_edit UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    edit_version BIGINT NOT NULL CHECK (edit_version > 0),
    reason TEXT NOT NULL CHECK (btrim(reason) <> ''),
    previous_snapshot JSONB NOT NULL,
    replacement_snapshot JSONB NOT NULL,
    previous_covered_dates DATE[] NOT NULL DEFAULT ARRAY[]::DATE[],
    replacement_covered_dates DATE[] NOT NULL DEFAULT ARRAY[]::DATE[],
    edited_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (transaction_id, edit_version)
);

CREATE INDEX IF NOT EXISTS lending_collection_transaction_edits_actor_idx
    ON lending.collection_transaction_edits (edited_by_user_id, edited_at DESC);
CREATE INDEX IF NOT EXISTS lending_collection_transaction_edits_transaction_idx
    ON lending.collection_transaction_edits (transaction_id, edit_version DESC);

CREATE OR REPLACE FUNCTION lending.guard_collection_evidence()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key
       OR NEW.loan_id IS DISTINCT FROM OLD.loan_id
       OR NEW.client_id IS DISTINCT FROM OLD.client_id
       OR NEW.collector_user_id IS DISTINCT FROM OLD.collector_user_id
       OR NEW.registered_device_id IS DISTINCT FROM OLD.registered_device_id
       OR NEW.route_entry_id IS DISTINCT FROM OLD.route_entry_id
       OR NEW.collection_date IS DISTINCT FROM OLD.collection_date
       OR NEW.entry_type IS DISTINCT FROM OLD.entry_type
       OR NEW.amount IS DISTINCT FROM OLD.amount
       OR NEW.advance_from IS DISTINCT FROM OLD.advance_from
       OR NEW.advance_until IS DISTINCT FROM OLD.advance_until
       OR NEW.recorded_at IS DISTINCT FROM OLD.recorded_at
       OR NEW.accepted_at IS DISTINCT FROM OLD.accepted_at
       OR NEW.device_sequence IS DISTINCT FROM OLD.device_sequence
       OR NEW.note IS DISTINCT FROM OLD.note
       OR NEW.route_revision IS DISTINCT FROM OLD.route_revision
       OR NEW.previous_balance IS DISTINCT FROM OLD.previous_balance
       OR NEW.official_balance IS DISTINCT FROM OLD.official_balance
       OR NEW.pass_count_after IS DISTINCT FROM OLD.pass_count_after
       OR NEW.advance_until_after IS DISTINCT FROM OLD.advance_until_after
       OR NEW.receipt_number IS DISTINCT FROM OLD.receipt_number
       OR NEW.details IS DISTINCT FROM OLD.details THEN
        RAISE EXCEPTION 'Original collection evidence is immutable. Create an audited correction instead.'
            USING ERRCODE = '55000';
    END IF;

    IF OLD.custody_state = 'finalized'
       AND (
           NEW.current_custodian_user_id IS DISTINCT FROM OLD.current_custodian_user_id
           OR NEW.active_remittance_id IS DISTINCT FROM OLD.active_remittance_id
           OR NEW.custody_state IS DISTINCT FROM OLD.custody_state
           OR NEW.custody_version IS DISTINCT FROM OLD.custody_version
           OR NEW.effective_edit_version IS DISTINCT FROM OLD.effective_edit_version
       ) THEN
        RAISE EXCEPTION 'Finalized remittance custody cannot be changed.'
            USING ERRCODE = '55000';
    END IF;

    IF (
        NEW.current_custodian_user_id IS DISTINCT FROM OLD.current_custodian_user_id
        OR NEW.active_remittance_id IS DISTINCT FROM OLD.active_remittance_id
        OR NEW.custody_state IS DISTINCT FROM OLD.custody_state
    ) AND NEW.custody_version <= OLD.custody_version THEN
        RAISE EXCEPTION 'Custody changes must increase the custody version.'
            USING ERRCODE = '40001';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_collection_evidence_guard
    ON lending.collection_transactions;
CREATE TRIGGER lending_collection_evidence_guard
BEFORE UPDATE ON lending.collection_transactions
FOR EACH ROW
EXECUTE FUNCTION lending.guard_collection_evidence();

CREATE OR REPLACE FUNCTION lending.guard_original_covered_date()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    stored_loan_id UUID;
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        RAISE EXCEPTION 'Original covered dates are immutable. Create an audited correction instead.'
            USING ERRCODE = '55000';
    END IF;

    SELECT loan_id
    INTO stored_loan_id
    FROM lending.collection_transactions
    WHERE id = NEW.transaction_id;

    IF stored_loan_id IS NULL THEN
        RAISE EXCEPTION 'The collection transaction for this covered date does not exist.'
            USING ERRCODE = '23503';
    END IF;

    IF stored_loan_id <> NEW.loan_id THEN
        RAISE EXCEPTION 'The covered date loan does not match the collection transaction.'
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_collection_covered_date_guard
    ON lending.collection_covered_dates;
CREATE TRIGGER lending_collection_covered_date_guard
BEFORE INSERT OR UPDATE OR DELETE ON lending.collection_covered_dates
FOR EACH ROW
EXECUTE FUNCTION lending.guard_original_covered_date();

COMMENT ON TABLE lending.collection_remittances IS
    'Server-calculated custody transfers. Submission removes edit control from the sender and gives it to the recipient.';
COMMENT ON COLUMN lending.collection_transactions.current_custodian_user_id IS
    'Only this user may create ordinary audited corrections while custody_state is held.';
COMMENT ON COLUMN lending.collection_transactions.custody_state IS
    'Held permits the current custodian to correct; finalized permanently closes collector editing.';
COMMENT ON TABLE lending.collection_transaction_edits IS
    'Append-only effective corrections. The original collection transaction remains unchanged.';
COMMENT ON TABLE lending.collection_covered_dates IS
    'Exact individually selected dates from the original payment. Corrections store replacement dates in the edit audit row.';

COMMIT;
