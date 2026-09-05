BEGIN;

-- Borrower-caused schedule movement uses the same versioned operational-date
-- authority as Management No Collection, while keeping signed-contract dates
-- and existing No Collection evidence immutable.
ALTER TABLE lending.loan_schedule_operational_state
    ADD COLUMN IF NOT EXISTS active_borrower_extension_slots INTEGER NOT NULL DEFAULT 0
        CHECK (active_borrower_extension_slots >= 0);

ALTER TABLE lending.loan_schedule_adjustments
    ADD COLUMN IF NOT EXISTS event_date DATE;

-- Existing No Collection, reversal, and voluntary-completion rows are immutable
-- audit evidence. Migration 0110 is the one controlled upgrade that must copy
-- their already-audited no_collection_date into the new generic event_date.
-- Disable only the table's user audit trigger inside this transaction; PostgreSQL
-- rolls the trigger state back too if any later statement fails.
ALTER TABLE lending.loan_schedule_adjustments
    DISABLE TRIGGER lending_loan_schedule_adjustment_audit_guard;

UPDATE lending.loan_schedule_adjustments
SET event_date = no_collection_date
WHERE event_date IS NULL;

ALTER TABLE lending.loan_schedule_adjustments
    ENABLE TRIGGER lending_loan_schedule_adjustment_audit_guard;

ALTER TABLE lending.loan_schedule_adjustments
    ALTER COLUMN event_date SET NOT NULL;

-- Borrower adjustments do not represent a Management No Collection day, so the
-- legacy field becomes nullable while remaining mandatory for existing
-- No Collection-derived adjustment forms below.
ALTER TABLE lending.loan_schedule_adjustments
    ALTER COLUMN no_collection_date DROP NOT NULL;

ALTER TABLE lending.loan_schedule_adjustments
    DROP CONSTRAINT IF EXISTS loan_schedule_adjustments_adjustment_type_check;
ALTER TABLE lending.loan_schedule_adjustments
    DROP CONSTRAINT IF EXISTS loan_schedule_adjustments_check;
ALTER TABLE lending.loan_schedule_adjustments
    DROP CONSTRAINT IF EXISTS loan_schedule_adjustments_reference_semantics_check;
ALTER TABLE lending.loan_schedule_adjustments
    DROP CONSTRAINT IF EXISTS loan_schedule_adjustments_type_evidence_check;

ALTER TABLE lending.loan_schedule_adjustments
    ADD CONSTRAINT loan_schedule_adjustments_adjustment_type_check
    CHECK (
        adjustment_type IN (
            'no_collection',
            'reversal',
            'voluntary_completion',
            'borrower_shortfall',
            'borrower_catch_up'
        )
    );

ALTER TABLE lending.loan_schedule_adjustments
    ADD CONSTRAINT loan_schedule_adjustments_type_evidence_check
    CHECK (
        (
            adjustment_type = 'no_collection'
            AND no_collection_date IS NOT NULL
            AND event_date = no_collection_date
            AND reverses_adjustment_id IS NULL
        )
        OR
        (
            adjustment_type = 'reversal'
            AND no_collection_date IS NOT NULL
            AND event_date = no_collection_date
            AND reverses_adjustment_id IS NOT NULL
        )
        OR
        (
            adjustment_type = 'voluntary_completion'
            AND no_collection_date IS NOT NULL
            AND event_date = no_collection_date
            AND reverses_adjustment_id IS NULL
        )
        OR
        (
            adjustment_type IN ('borrower_shortfall', 'borrower_catch_up')
            AND no_collection_date IS NULL
            AND reverses_adjustment_id IS NULL
        )
    );

CREATE INDEX IF NOT EXISTS lending_loan_schedule_adjustments_event_date_idx
    ON lending.loan_schedule_adjustments(schedule_id, event_date);

-- Catch-up is protected chronological payment allocation, not Advance. Keep all
-- historical bases valid and add one explicit audited basis for this new case.
ALTER TABLE lending.loan_installment_payment_allocations
    DROP CONSTRAINT IF EXISTS loan_installment_payment_allocations_allocation_basis_check;

ALTER TABLE lending.loan_installment_payment_allocations
    ADD CONSTRAINT loan_installment_payment_allocations_allocation_basis_check
    CHECK (
        allocation_basis IN (
            'exact_covered_date',
            'oldest_due_first',
            'voluntary_extra_tail',
            'future_advance_oldest_first',
            'borrower_catch_up_oldest_first',
            'contract_reference',
            'manual_review'
        )
    );

COMMENT ON COLUMN lending.loan_schedule_operational_state.active_borrower_extension_slots IS
    'Count of active borrower-caused schedule extension slots. Management No Collection does not increment this count.';
COMMENT ON COLUMN lending.loan_schedule_adjustments.event_date IS
    'Generic audited date that caused an operational schedule adjustment. For No Collection-derived adjustments, event_date equals no_collection_date.';
COMMENT ON TABLE lending.loan_schedule_adjustments IS
    'Immutable versioned operational schedule-adjustment audit for Management No Collection/reversal/voluntary completion and borrower shortfall/catch-up events.';
COMMENT ON COLUMN lending.loan_installment_payment_allocations.allocation_basis IS
    'Protected allocation purpose. borrower_catch_up_oldest_first is normal-payment catch-up against shifted chronological obligations before any true Advance or Principal Reduction.';

COMMIT;
