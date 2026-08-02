BEGIN;

CREATE OR REPLACE FUNCTION lending.prevent_locked_collection_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.is_locked AND NEW IS DISTINCT FROM OLD THEN
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

DROP TRIGGER IF EXISTS lending_collection_transaction_lock_guard
    ON lending.collection_transactions;
CREATE TRIGGER lending_collection_transaction_lock_guard
BEFORE UPDATE ON lending.collection_transactions
FOR EACH ROW
EXECUTE FUNCTION lending.prevent_locked_collection_mutation();

COMMIT;
