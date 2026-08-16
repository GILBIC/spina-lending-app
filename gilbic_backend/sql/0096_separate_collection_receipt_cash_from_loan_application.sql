BEGIN;

-- A collection transaction is first a real cash/GCash receipt and custody event.
-- The full amount physically received must remain auditable even when some of it
-- cannot yet be applied to a contractual obligation. Loan application is kept
-- separately so a second legitimate same-day receipt is never discarded merely
-- because the current scheduled installment was already satisfied.
ALTER TABLE lending.collection_transactions
    ADD COLUMN IF NOT EXISTS applied_amount NUMERIC(18,2);
ALTER TABLE lending.collection_transactions
    ADD COLUMN IF NOT EXISTS unallocated_amount NUMERIC(18,2);
ALTER TABLE lending.collection_transactions
    ADD COLUMN IF NOT EXISTS allocation_state TEXT;

UPDATE lending.collection_transactions
SET
    applied_amount = CASE
        WHEN entry_type = 'pass' THEN 0::numeric(18,2)
        ELSE amount
    END,
    unallocated_amount = 0::numeric(18,2),
    allocation_state = CASE
        WHEN entry_type = 'pass' THEN 'not_applicable'
        ELSE 'fully_allocated'
    END
WHERE applied_amount IS NULL
   OR unallocated_amount IS NULL
   OR allocation_state IS NULL;

ALTER TABLE lending.collection_transactions
    ALTER COLUMN applied_amount SET DEFAULT 0,
    ALTER COLUMN applied_amount SET NOT NULL,
    ALTER COLUMN unallocated_amount SET DEFAULT 0,
    ALTER COLUMN unallocated_amount SET NOT NULL,
    ALTER COLUMN allocation_state SET DEFAULT 'fully_allocated',
    ALTER COLUMN allocation_state SET NOT NULL;

-- Compatibility bridge while every existing writer is moved to explicit receipt
-- application fields. PostgreSQL applies column defaults before BEFORE INSERT
-- triggers, so an old writer that supplies only amount arrives here as 0/0 with
-- the default fully_allocated state. Preserve its historical behaviour by treating
-- the whole receipt as applied. A future receipt-first writer can explicitly send
-- a partial/unallocated split and this trigger leaves that split untouched.
CREATE OR REPLACE FUNCTION lending.normalize_collection_receipt_application_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.entry_type = 'pass' THEN
        NEW.applied_amount := 0;
        NEW.unallocated_amount := 0;
        NEW.allocation_state := 'not_applicable';
        RETURN NEW;
    END IF;

    IF NEW.entry_type IN ('payment', 'advance')
       AND NEW.amount > 0
       AND NEW.applied_amount = 0
       AND NEW.unallocated_amount = 0
       AND NEW.allocation_state = 'fully_allocated' THEN
        NEW.applied_amount := NEW.amount;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS normalize_collection_receipt_application_insert
    ON lending.collection_transactions;
CREATE TRIGGER normalize_collection_receipt_application_insert
BEFORE INSERT ON lending.collection_transactions
FOR EACH ROW
EXECUTE FUNCTION lending.normalize_collection_receipt_application_insert();

ALTER TABLE lending.collection_transactions
    DROP CONSTRAINT IF EXISTS lending_collection_applied_amount_check;
ALTER TABLE lending.collection_transactions
    ADD CONSTRAINT lending_collection_applied_amount_check
    CHECK (applied_amount >= 0 AND applied_amount <= amount);

ALTER TABLE lending.collection_transactions
    DROP CONSTRAINT IF EXISTS lending_collection_unallocated_amount_check;
ALTER TABLE lending.collection_transactions
    ADD CONSTRAINT lending_collection_unallocated_amount_check
    CHECK (unallocated_amount >= 0 AND unallocated_amount <= amount);

ALTER TABLE lending.collection_transactions
    DROP CONSTRAINT IF EXISTS lending_collection_receipt_application_sum_check;
ALTER TABLE lending.collection_transactions
    ADD CONSTRAINT lending_collection_receipt_application_sum_check
    CHECK (
        (entry_type = 'pass' AND amount = 0 AND applied_amount = 0 AND unallocated_amount = 0)
        OR
        (entry_type IN ('payment', 'advance')
         AND applied_amount + unallocated_amount = amount)
    );

ALTER TABLE lending.collection_transactions
    DROP CONSTRAINT IF EXISTS lending_collection_allocation_state_check;
ALTER TABLE lending.collection_transactions
    ADD CONSTRAINT lending_collection_allocation_state_check
    CHECK (
        allocation_state IN (
            'not_applicable',
            'fully_allocated',
            'partially_allocated',
            'unallocated'
        )
        AND (
            (entry_type = 'pass' AND allocation_state = 'not_applicable')
            OR
            (entry_type IN ('payment', 'advance') AND (
                (allocation_state = 'fully_allocated' AND applied_amount = amount AND unallocated_amount = 0)
                OR
                (allocation_state = 'partially_allocated' AND applied_amount > 0 AND unallocated_amount > 0)
                OR
                (allocation_state = 'unallocated' AND applied_amount = 0 AND unallocated_amount = amount)
            ))
        )
    );

CREATE INDEX IF NOT EXISTS lending_collection_unresolved_allocation_idx
    ON lending.collection_transactions (collection_date, accepted_at, id)
    WHERE is_voided = false
      AND entry_type IN ('payment', 'advance')
      AND unallocated_amount > 0;

CREATE OR REPLACE VIEW lending.collection_receipt_application_state AS
SELECT
    transaction.id AS transaction_id,
    transaction.idempotency_key,
    transaction.loan_id,
    transaction.client_id,
    transaction.collector_user_id,
    transaction.registered_device_id,
    transaction.collection_date,
    transaction.entry_type,
    transaction.amount AS cash_received_amount,
    transaction.applied_amount,
    transaction.unallocated_amount,
    transaction.allocation_state,
    coalesce(
        nullif(transaction.details->>'payment_allocation_intent', ''),
        CASE WHEN transaction.entry_type = 'advance' THEN 'advance' ELSE 'scheduled' END
    ) AS payment_allocation_intent,
    transaction.receipt_number,
    transaction.accepted_at,
    transaction.remittance_id,
    transaction.is_locked,
    transaction.is_voided
FROM lending.collection_transactions transaction;

COMMENT ON COLUMN lending.collection_transactions.amount IS
    'Actual cash/GCash amount physically received for this immutable receipt/custody event. Do not infer loan application from this field.';
COMMENT ON COLUMN lending.collection_transactions.applied_amount IS
    'Portion of the receipt currently applied to the loan obligation. Financial/DPD allocation must use this amount, not raw cash received.';
COMMENT ON COLUMN lending.collection_transactions.unallocated_amount IS
    'Portion of real cash received that is still awaiting an authorized obligation allocation. It remains part of custody/remittance even while unapplied.';
COMMENT ON COLUMN lending.collection_transactions.allocation_state IS
    'Operational receipt-allocation status. Unallocated cash is never silently converted to ADV.';
COMMENT ON VIEW lending.collection_receipt_application_state IS
    'Receipt/custody amount versus loan-applied/unallocated amount. Remittance follows cash_received_amount; loan obligation/accounting automation must fail closed on unresolved unallocated cash.';

COMMIT;