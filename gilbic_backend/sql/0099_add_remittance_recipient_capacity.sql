BEGIN;

-- Install the compatibility default as part of the DDL itself. Do not backfill
-- existing rows with UPDATE: accepted remittances are intentionally closed to
-- every row mutation by the custody guard introduced in 0010.
ALTER TABLE lending.collection_remittances
    ADD COLUMN IF NOT EXISTS recipient_capacity TEXT DEFAULT 'legacy';

ALTER TABLE lending.collection_remittances
    ALTER COLUMN recipient_capacity SET DEFAULT 'legacy';

ALTER TABLE lending.collection_remittances
    ALTER COLUMN recipient_capacity SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'collection_remittance_recipient_capacity_check'
          AND conrelid = 'lending.collection_remittances'::regclass
    ) THEN
        ALTER TABLE lending.collection_remittances
            ADD CONSTRAINT collection_remittance_recipient_capacity_check
            CHECK (
                recipient_capacity IN (
                    'legacy',
                    'assigned_collector',
                    'management',
                    'employee'
                )
            );
    END IF;
END
$$;

CREATE OR REPLACE FUNCTION lending.prevent_remittance_recipient_capacity_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.recipient_capacity IS DISTINCT FROM OLD.recipient_capacity THEN
        RAISE EXCEPTION 'Remittance recipient capacity is immutable after submission.'
            USING ERRCODE = '55000';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_collection_remittance_recipient_capacity_guard
    ON lending.collection_remittances;
CREATE TRIGGER lending_collection_remittance_recipient_capacity_guard
BEFORE UPDATE OF recipient_capacity ON lending.collection_remittances
FOR EACH ROW
EXECUTE FUNCTION lending.prevent_remittance_recipient_capacity_mutation();

COMMENT ON COLUMN lending.collection_remittances.recipient_capacity IS
    'Immutable capacity selected when the remittance is submitted. Existing rows are legacy because historical role intent cannot be inferred safely.';

COMMIT;
