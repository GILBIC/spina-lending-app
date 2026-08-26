BEGIN;

-- A borrower can voluntarily complete the installment that Management shifted
-- for a declared 7x7 No Collection day. This is not a Management reversal: the
-- original No Collection declaration remains immutable historical evidence,
-- while a separate operational adjustment records that the borrower completed
-- the affected installment on the original holiday date.
DO $migration$
DECLARE
    constraint_row record;
BEGIN
    FOR constraint_row IN
        SELECT constraint_def.conname
        FROM pg_constraint constraint_def
        JOIN pg_class relation_def
          ON relation_def.oid = constraint_def.conrelid
        JOIN pg_namespace namespace_def
          ON namespace_def.oid = relation_def.relnamespace
        WHERE namespace_def.nspname = 'lending'
          AND relation_def.relname = 'loan_schedule_adjustments'
          AND constraint_def.contype = 'c'
          AND pg_get_constraintdef(constraint_def.oid) ILIKE '%adjustment_type%'
    LOOP
        EXECUTE format(
            'ALTER TABLE lending.loan_schedule_adjustments DROP CONSTRAINT %I',
            constraint_row.conname
        );
    END LOOP;
END
$migration$;

ALTER TABLE lending.loan_schedule_adjustments
    ADD CONSTRAINT loan_schedule_adjustments_adjustment_type_check
    CHECK (
        adjustment_type IN (
            'no_collection',
            'reversal',
            'voluntary_completion'
        )
    );

ALTER TABLE lending.loan_schedule_adjustments
    ADD CONSTRAINT loan_schedule_adjustments_reference_semantics_check
    CHECK (
        (adjustment_type = 'no_collection' AND reverses_adjustment_id IS NULL)
        OR
        (adjustment_type = 'reversal' AND reverses_adjustment_id IS NOT NULL)
        OR
        (adjustment_type = 'voluntary_completion' AND reverses_adjustment_id IS NULL)
    );

CREATE TABLE IF NOT EXISTS lending.loan_no_collection_voluntary_completions (
    adjustment_id UUID PRIMARY KEY
        REFERENCES lending.loan_schedule_adjustments(id) ON DELETE RESTRICT,
    no_collection_adjustment_id UUID NOT NULL UNIQUE
        REFERENCES lending.loan_schedule_adjustments(id) ON DELETE RESTRICT,
    transaction_id UUID NOT NULL UNIQUE
        REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    affected_installment_id BIGINT NOT NULL
        REFERENCES lending.loan_contract_installments(id) ON DELETE RESTRICT,
    current_receipt_completion_amount NUMERIC(18,2) NOT NULL
        CHECK (current_receipt_completion_amount > 0),
    prior_advance_activation_amount NUMERIC(18,2) NOT NULL DEFAULT 0
        CHECK (prior_advance_activation_amount >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (adjustment_id <> no_collection_adjustment_id)
);

CREATE INDEX IF NOT EXISTS lending_nc_voluntary_completion_installment_idx
    ON lending.loan_no_collection_voluntary_completions(affected_installment_id);

CREATE OR REPLACE FUNCTION lending.validate_no_collection_voluntary_completion()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    completion_loan_id UUID;
    completion_schedule_id UUID;
    completion_date DATE;
    completion_type TEXT;
    source_loan_id UUID;
    source_schedule_id UUID;
    source_date DATE;
    source_type TEXT;
    receipt_loan_id UUID;
    receipt_date DATE;
    receipt_type TEXT;
    receipt_amount NUMERIC(18,2);
    receipt_is_voided BOOLEAN;
    installment_schedule_id UUID;
    installment_amount NUMERIC(18,2);
BEGIN
    SELECT
        adjustment.loan_id,
        adjustment.schedule_id,
        adjustment.no_collection_date,
        adjustment.adjustment_type
    INTO
        completion_loan_id,
        completion_schedule_id,
        completion_date,
        completion_type
    FROM lending.loan_schedule_adjustments adjustment
    WHERE adjustment.id = NEW.adjustment_id;

    IF NOT FOUND OR completion_type <> 'voluntary_completion' THEN
        RAISE EXCEPTION
            'No Collection voluntary completion requires a voluntary_completion schedule adjustment.';
    END IF;

    SELECT
        adjustment.loan_id,
        adjustment.schedule_id,
        adjustment.no_collection_date,
        adjustment.adjustment_type
    INTO
        source_loan_id,
        source_schedule_id,
        source_date,
        source_type
    FROM lending.loan_schedule_adjustments adjustment
    WHERE adjustment.id = NEW.no_collection_adjustment_id;

    IF NOT FOUND OR source_type <> 'no_collection' THEN
        RAISE EXCEPTION
            'No Collection voluntary completion must reference an original no_collection adjustment.';
    END IF;

    IF completion_loan_id <> source_loan_id
       OR completion_schedule_id <> source_schedule_id
       OR completion_date <> source_date THEN
        RAISE EXCEPTION
            'Voluntary completion and source No Collection must belong to the same loan, schedule, and date.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM lending.loan_schedule_adjustments reversal
        WHERE reversal.reverses_adjustment_id = NEW.no_collection_adjustment_id
    ) THEN
        RAISE EXCEPTION
            'A Management-reversed No Collection cannot receive voluntary completion evidence.';
    END IF;

    SELECT
        transaction.loan_id,
        transaction.collection_date,
        transaction.entry_type,
        transaction.amount,
        transaction.is_voided
    INTO
        receipt_loan_id,
        receipt_date,
        receipt_type,
        receipt_amount,
        receipt_is_voided
    FROM lending.collection_transactions transaction
    WHERE transaction.id = NEW.transaction_id;

    IF NOT FOUND
       OR receipt_loan_id <> source_loan_id
       OR receipt_date <> source_date
       OR receipt_type <> 'payment'
       OR receipt_is_voided THEN
        RAISE EXCEPTION
            'Voluntary completion evidence requires a non-voided Payment receipt for the same loan and No Collection date.';
    END IF;

    IF NEW.current_receipt_completion_amount > receipt_amount THEN
        RAISE EXCEPTION
            'The No Collection completion component cannot exceed the source receipt amount.';
    END IF;

    SELECT
        installment.schedule_id,
        installment.contractual_amount
    INTO
        installment_schedule_id,
        installment_amount
    FROM lending.loan_contract_installments installment
    WHERE installment.id = NEW.affected_installment_id;

    IF NOT FOUND OR installment_schedule_id <> source_schedule_id THEN
        RAISE EXCEPTION
            'The completed installment must belong to the same verified schedule as the No Collection adjustment.';
    END IF;

    IF NEW.current_receipt_completion_amount
       + NEW.prior_advance_activation_amount <> installment_amount THEN
        RAISE EXCEPTION
            'Voluntary completion evidence must reconcile exactly to the signed installment amount.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_nc_voluntary_completion_validate
    ON lending.loan_no_collection_voluntary_completions;
CREATE TRIGGER lending_nc_voluntary_completion_validate
BEFORE INSERT ON lending.loan_no_collection_voluntary_completions
FOR EACH ROW EXECUTE FUNCTION lending.validate_no_collection_voluntary_completion();

DROP TRIGGER IF EXISTS lending_nc_voluntary_completion_audit_guard
    ON lending.loan_no_collection_voluntary_completions;
CREATE TRIGGER lending_nc_voluntary_completion_audit_guard
BEFORE UPDATE OR DELETE ON lending.loan_no_collection_voluntary_completions
FOR EACH ROW EXECUTE FUNCTION lending.guard_loan_schedule_adjustment_audit();

COMMENT ON TABLE lending.loan_no_collection_voluntary_completions IS
    'Immutable evidence that a borrower fully completed a Management-declared No Collection installment on the original holiday date. The source No Collection remains historical fact; this evidence is not a Management reversal.';

COMMENT ON COLUMN lending.loan_no_collection_voluntary_completions.current_receipt_completion_amount IS
    'Cash from the referenced same-day Payment receipt that completed the affected signed installment after older Past Due priority.';

COMMENT ON COLUMN lending.loan_no_collection_voluntary_completions.prior_advance_activation_amount IS
    'Previously prepaid amount already attached to the affected installment that must financially activate with full voluntary completion on the original No Collection date.';

COMMIT;
