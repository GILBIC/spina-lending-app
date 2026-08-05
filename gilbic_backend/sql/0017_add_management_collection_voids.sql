BEGIN;

INSERT INTO core.permissions (code, description)
VALUES (
    'collection.void.unremitted',
    'Void an incorrect unlocked collection entry with a permanent audit trail'
)
ON CONFLICT (code) DO NOTHING;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT r.id, p.code
FROM core.roles r
JOIN core.permissions p ON p.code = 'collection.void.unremitted'
WHERE r.code = 'management'
ON CONFLICT DO NOTHING;

ALTER TABLE lending.collection_transactions
    ADD COLUMN IF NOT EXISTS is_voided BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE lending.collection_transactions
    ADD COLUMN IF NOT EXISTS voided_at TIMESTAMPTZ;
ALTER TABLE lending.collection_transactions
    ADD COLUMN IF NOT EXISTS voided_by_user_id UUID
        REFERENCES core.users(id) ON DELETE RESTRICT;
ALTER TABLE lending.collection_transactions
    ADD COLUMN IF NOT EXISTS void_reason TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'collection_transactions_void_state_check'
          AND conrelid = 'lending.collection_transactions'::regclass
    ) THEN
        ALTER TABLE lending.collection_transactions
            ADD CONSTRAINT collection_transactions_void_state_check
            CHECK (
                (
                    is_voided = false
                    AND voided_at IS NULL
                    AND voided_by_user_id IS NULL
                    AND void_reason IS NULL
                )
                OR
                (
                    is_voided = true
                    AND voided_at IS NOT NULL
                    AND voided_by_user_id IS NOT NULL
                    AND btrim(coalesce(void_reason, '')) <> ''
                    AND remittance_id IS NULL
                    AND is_locked = false
                )
            );
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS lending.collection_transaction_voids (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL UNIQUE
        REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    voided_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    reason TEXT NOT NULL CHECK (btrim(reason) <> ''),
    transaction_snapshot JSONB NOT NULL,
    previous_covered_dates DATE[] NOT NULL DEFAULT ARRAY[]::DATE[],
    state_before JSONB NOT NULL,
    state_after JSONB NOT NULL,
    voided_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS lending_collection_voids_actor_idx
    ON lending.collection_transaction_voids (voided_by_user_id, voided_at DESC);
CREATE INDEX IF NOT EXISTS lending_collection_transaction_active_unremitted_idx
    ON lending.collection_transactions (
        collector_user_id,
        collection_date,
        accepted_at
    )
    WHERE remittance_id IS NULL
      AND is_locked = false
      AND is_voided = false;

CREATE OR REPLACE FUNCTION lending.prevent_locked_collection_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.is_voided THEN
        RAISE EXCEPTION 'Voided collection transactions are permanent and cannot be edited.'
            USING ERRCODE = '55000';
    END IF;

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
           OR NEW.locked_by_user_id IS DISTINCT FROM OLD.locked_by_user_id
           OR NEW.is_voided IS DISTINCT FROM OLD.is_voided
           OR NEW.voided_at IS DISTINCT FROM OLD.voided_at
           OR NEW.voided_by_user_id IS DISTINCT FROM OLD.voided_by_user_id
           OR NEW.void_reason IS DISTINCT FROM OLD.void_reason THEN
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

CREATE OR REPLACE FUNCTION lending.guard_collection_covered_date()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_transaction_id UUID;
    transaction_locked BOOLEAN;
    transaction_voided BOOLEAN;
    stored_loan_id UUID;
BEGIN
    target_transaction_id := COALESCE(NEW.transaction_id, OLD.transaction_id);

    SELECT is_locked, is_voided, loan_id
    INTO transaction_locked, transaction_voided, stored_loan_id
    FROM lending.collection_transactions
    WHERE id = target_transaction_id;

    IF stored_loan_id IS NULL THEN
        RAISE EXCEPTION 'The collection transaction for this covered date does not exist.'
            USING ERRCODE = '23503';
    END IF;

    IF transaction_locked THEN
        RAISE EXCEPTION 'Covered dates for a remitted collection are locked.'
            USING ERRCODE = '55000';
    END IF;

    IF transaction_voided THEN
        RAISE EXCEPTION 'Covered dates for a voided collection cannot be changed.'
            USING ERRCODE = '55000';
    END IF;

    IF TG_OP <> 'DELETE' AND stored_loan_id <> NEW.loan_id THEN
        RAISE EXCEPTION 'The covered date loan does not match the collection transaction.'
            USING ERRCODE = '23514';
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$;

COMMENT ON COLUMN lending.collection_transactions.is_voided IS
    'True only after Management performs an audited void before remittance.';
COMMENT ON TABLE lending.collection_transaction_voids IS
    'Append-only snapshots and balance restoration evidence for Management voids.';

COMMIT;
