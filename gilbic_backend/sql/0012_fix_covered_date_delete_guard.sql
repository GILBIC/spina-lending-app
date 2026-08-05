BEGIN;

CREATE OR REPLACE FUNCTION lending.guard_collection_covered_date()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_transaction_id UUID;
    transaction_locked BOOLEAN;
    stored_loan_id UUID;
BEGIN
    IF TG_OP = 'DELETE' THEN
        target_transaction_id := OLD.transaction_id;
    ELSE
        target_transaction_id := NEW.transaction_id;
    END IF;

    SELECT is_locked, loan_id
    INTO transaction_locked, stored_loan_id
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

    IF TG_OP <> 'DELETE' AND stored_loan_id <> NEW.loan_id THEN
        RAISE EXCEPTION 'The covered date loan does not match the collection transaction.'
            USING ERRCODE = '23514';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

COMMIT;
