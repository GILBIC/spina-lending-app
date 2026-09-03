BEGIN;

CREATE TABLE IF NOT EXISTS lending.collection_remittance_reviews (
    remittance_id UUID PRIMARY KEY
        REFERENCES lending.collection_remittances(id) ON DELETE RESTRICT,
    reviewed_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS lending_collection_remittance_reviews_actor_idx
    ON lending.collection_remittance_reviews (
        reviewed_by_user_id,
        reviewed_at DESC
    );

CREATE TABLE IF NOT EXISTS lending.collection_remittance_rejections (
    remittance_id UUID PRIMARY KEY
        REFERENCES lending.collection_remittances(id) ON DELETE RESTRICT,
    rejected_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    rejected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reason TEXT NOT NULL CHECK (btrim(reason) <> '')
);

CREATE INDEX IF NOT EXISTS lending_collection_remittance_rejections_actor_idx
    ON lending.collection_remittance_rejections (
        rejected_by_user_id,
        rejected_at DESC
    );

-- A rejected handover stays permanently itemized in its original remittance.
-- The same official payment may then be included in a corrected/resubmitted
-- remittance, so transaction_id can no longer be globally unique here.
ALTER TABLE lending.collection_remittance_items
    DROP CONSTRAINT IF EXISTS collection_remittance_items_transaction_id_key;

CREATE INDEX IF NOT EXISTS lending_collection_remittance_items_transaction_idx
    ON lending.collection_remittance_items (transaction_id, remittance_id);

-- Remitted transactions normally remain immutable. The only exception is the
-- server-controlled unlock after the selected recipient rejects the remittance.
-- No financial/payment field may change during that unlock.
CREATE OR REPLACE FUNCTION lending.prevent_locked_collection_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, lending, core
AS $$
DECLARE
    rejected_remittance BOOLEAN := false;
    old_financial JSONB;
    new_financial JSONB;
BEGIN
    IF OLD.is_locked AND NEW IS DISTINCT FROM OLD THEN
        IF OLD.remittance_id IS NOT NULL THEN
            SELECT EXISTS (
                SELECT 1
                FROM lending.collection_remittance_rejections rejection
                WHERE rejection.remittance_id = OLD.remittance_id
            )
            INTO rejected_remittance;
        END IF;

        old_financial := to_jsonb(OLD) - ARRAY[
            'remittance_id',
            'is_locked',
            'locked_at',
            'locked_by_user_id',
            'updated_at',
            'updated_by_user_id'
        ]::text[];
        new_financial := to_jsonb(NEW) - ARRAY[
            'remittance_id',
            'is_locked',
            'locked_at',
            'locked_by_user_id',
            'updated_at',
            'updated_by_user_id'
        ]::text[];

        IF rejected_remittance
           AND NEW.remittance_id IS NULL
           AND NEW.is_locked = false
           AND NEW.locked_at IS NULL
           AND NEW.locked_by_user_id IS NULL
           AND new_financial = old_financial THEN
            RETURN NEW;
        END IF;

        RAISE EXCEPTION 'Remitted collection transactions are permanently locked. Create an authorized supervisor adjustment instead.'
            USING ERRCODE = '55000';
    END IF;

    IF OLD.remittance_id IS NOT NULL
       AND NEW.remittance_id IS DISTINCT FROM OLD.remittance_id THEN
        RAISE EXCEPTION 'A collection transaction cannot be moved to another remittance.'
            USING ERRCODE = '55000';
    END IF;

    RETURN NEW;
END;
$$;

COMMENT ON TABLE lending.collection_remittance_reviews IS
    'Permanent evidence that the selected recipient reviewed the complete itemized remittance before accepting or rejecting it.';
COMMENT ON TABLE lending.collection_remittance_rejections IS
    'Permanent recipient rejection history. Rejection returns cash responsibility to the original collecting user without deleting the remittance snapshot.';

COMMIT;
