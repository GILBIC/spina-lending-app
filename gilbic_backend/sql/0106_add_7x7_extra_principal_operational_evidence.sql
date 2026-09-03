BEGIN;

-- 7x7 Extra Principal is an operational shortening of the current future tail.
-- It must never rewrite immutable signed installment rows. The source cash
-- receipt remains lending.collection_transactions evidence; this migration adds
-- only the schedule-effect and unused-Advance Refund Due evidence needed after
-- the operational allocator has already determined the receipt's money split.

CREATE TABLE IF NOT EXISTS lending.seven_by_seven_extra_principal_adjustments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    schedule_id UUID NOT NULL
        REFERENCES lending.loan_contract_schedules(id) ON DELETE RESTRICT,
    transaction_id UUID NOT NULL UNIQUE
        REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    principal_reduction NUMERIC(18,2) NOT NULL CHECK (principal_reduction > 0),
    prior_future_principal NUMERIC(18,2) NOT NULL CHECK (prior_future_principal > 0),
    resulting_future_principal NUMERIC(18,2) NOT NULL
        CHECK (resulting_future_principal >= 0),
    removed_future_interest NUMERIC(18,2) NOT NULL DEFAULT 0
        CHECK (removed_future_interest >= 0),
    advance_refund_due NUMERIC(18,2) NOT NULL DEFAULT 0
        CHECK (advance_refund_due >= 0),
    expected_operational_version INTEGER NOT NULL
        CHECK (expected_operational_version >= 0),
    resulting_operational_version INTEGER NOT NULL
        CHECK (resulting_operational_version > 0),
    actor_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        resulting_future_principal
        = prior_future_principal - principal_reduction
    ),
    CHECK (
        resulting_operational_version = expected_operational_version + 1
    ),
    UNIQUE (schedule_id, resulting_operational_version)
);

CREATE INDEX IF NOT EXISTS lending_7x7_extra_principal_loan_created_idx
    ON lending.seven_by_seven_extra_principal_adjustments(loan_id, created_at DESC);
CREATE INDEX IF NOT EXISTS lending_7x7_extra_principal_schedule_version_idx
    ON lending.seven_by_seven_extra_principal_adjustments(
        schedule_id,
        resulting_operational_version DESC
    );

CREATE TABLE IF NOT EXISTS lending.seven_by_seven_extra_principal_adjustment_items (
    adjustment_id UUID NOT NULL
        REFERENCES lending.seven_by_seven_extra_principal_adjustments(id)
        ON DELETE RESTRICT,
    installment_id BIGINT NOT NULL
        REFERENCES lending.loan_contract_installments(id) ON DELETE RESTRICT,
    installment_number INTEGER NOT NULL CHECK (installment_number > 0),
    effective_due_date DATE NOT NULL,
    signed_contractual_amount NUMERIC(18,2) NOT NULL
        CHECK (signed_contractual_amount > 0),
    signed_principal_component NUMERIC(18,2) NOT NULL
        CHECK (signed_principal_component > 0),
    signed_interest_component NUMERIC(18,2) NOT NULL
        CHECK (signed_interest_component >= 0),
    prior_operational_amount NUMERIC(18,2) NOT NULL
        CHECK (prior_operational_amount > 0),
    prior_operational_principal_component NUMERIC(18,2) NOT NULL
        CHECK (prior_operational_principal_component > 0),
    prior_operational_interest_component NUMERIC(18,2) NOT NULL
        CHECK (prior_operational_interest_component >= 0),
    new_operational_amount NUMERIC(18,2) NOT NULL
        CHECK (new_operational_amount >= 0),
    new_operational_principal_component NUMERIC(18,2) NOT NULL
        CHECK (new_operational_principal_component >= 0),
    new_operational_interest_component NUMERIC(18,2) NOT NULL
        CHECK (new_operational_interest_component >= 0),
    advance_allocated_before NUMERIC(18,2) NOT NULL DEFAULT 0
        CHECK (advance_allocated_before >= 0),
    advance_retained_after NUMERIC(18,2) NOT NULL DEFAULT 0
        CHECK (advance_retained_after >= 0),
    advance_refund_due NUMERIC(18,2) NOT NULL DEFAULT 0
        CHECK (advance_refund_due >= 0),
    removed_from_operational_schedule BOOLEAN NOT NULL DEFAULT false,
    PRIMARY KEY (adjustment_id, installment_id),
    CHECK (
        signed_contractual_amount
        = signed_principal_component + signed_interest_component
    ),
    CHECK (
        prior_operational_amount
        = prior_operational_principal_component
          + prior_operational_interest_component
    ),
    CHECK (
        new_operational_amount
        = new_operational_principal_component
          + new_operational_interest_component
    ),
    CHECK (new_operational_amount <= prior_operational_amount),
    CHECK (
        new_operational_principal_component
        <= prior_operational_principal_component
    ),
    CHECK (
        advance_retained_after + advance_refund_due
        = advance_allocated_before
    ),
    CHECK (advance_retained_after <= new_operational_amount),
    CHECK (
        (
            removed_from_operational_schedule
            AND new_operational_amount = 0
            AND new_operational_principal_component = 0
            AND new_operational_interest_component = 0
            AND advance_retained_after = 0
        )
        OR
        (
            NOT removed_from_operational_schedule
            AND new_operational_amount > 0
            AND new_operational_principal_component > 0
            AND new_operational_interest_component
                = prior_operational_interest_component
        )
    )
);

CREATE INDEX IF NOT EXISTS lending_7x7_extra_principal_item_installment_idx
    ON lending.seven_by_seven_extra_principal_adjustment_items(
        installment_id,
        adjustment_id
    );

CREATE TABLE IF NOT EXISTS lending.loan_installment_operational_amounts (
    installment_id BIGINT PRIMARY KEY
        REFERENCES lending.loan_contract_installments(id) ON DELETE RESTRICT,
    operational_amount NUMERIC(18,2) NOT NULL CHECK (operational_amount >= 0),
    operational_principal_component NUMERIC(18,2) NOT NULL
        CHECK (operational_principal_component >= 0),
    operational_interest_component NUMERIC(18,2) NOT NULL
        CHECK (operational_interest_component >= 0),
    removed_from_operational_schedule BOOLEAN NOT NULL DEFAULT false,
    last_extra_principal_adjustment_id UUID NOT NULL
        REFERENCES lending.seven_by_seven_extra_principal_adjustments(id)
        ON DELETE RESTRICT,
    updated_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        operational_amount
        = operational_principal_component + operational_interest_component
    ),
    CHECK (
        (
            removed_from_operational_schedule
            AND operational_amount = 0
            AND operational_principal_component = 0
            AND operational_interest_component = 0
        )
        OR
        (
            NOT removed_from_operational_schedule
            AND operational_amount > 0
            AND operational_principal_component > 0
        )
    )
);

CREATE TABLE IF NOT EXISTS lending.loan_unused_advance_refund_dues (
    adjustment_id UUID NOT NULL
        REFERENCES lending.seven_by_seven_extra_principal_adjustments(id)
        ON DELETE RESTRICT,
    installment_id BIGINT NOT NULL
        REFERENCES lending.loan_contract_installments(id) ON DELETE RESTRICT,
    amount_due NUMERIC(18,2) NOT NULL CHECK (amount_due > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (adjustment_id, installment_id)
);

CREATE INDEX IF NOT EXISTS lending_unused_advance_refund_due_installment_idx
    ON lending.loan_unused_advance_refund_dues(installment_id, created_at);

CREATE OR REPLACE FUNCTION lending.validate_7x7_extra_principal_adjustment()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    transaction_loan_id UUID;
    transaction_entry_type TEXT;
    transaction_amount NUMERIC(18,2);
    transaction_voided BOOLEAN;
    transaction_intent TEXT;
    schedule_loan_id UUID;
    schedule_status TEXT;
    schedule_registered BOOLEAN;
    current_operational_version INTEGER;
BEGIN
    SELECT
        transaction.loan_id,
        transaction.entry_type,
        transaction.amount,
        transaction.is_voided,
        coalesce(transaction.details ->> 'payment_allocation_intent', '')
    INTO
        transaction_loan_id,
        transaction_entry_type,
        transaction_amount,
        transaction_voided,
        transaction_intent
    FROM lending.collection_transactions transaction
    WHERE transaction.id = NEW.transaction_id;

    IF NOT FOUND
       OR transaction_loan_id <> NEW.loan_id
       OR transaction_entry_type <> 'payment'
       OR transaction_voided
       OR transaction_intent <> 'extra_as_principal_reduction' THEN
        RAISE EXCEPTION
            '7x7 Extra Principal requires a non-voided Payment receipt for the same loan with explicit extra_as_principal_reduction intent.';
    END IF;

    IF NEW.principal_reduction > transaction_amount THEN
        RAISE EXCEPTION
            '7x7 Extra Principal reduction cannot exceed the source physical cash receipt.';
    END IF;

    SELECT
        schedule.loan_id,
        schedule.status,
        EXISTS (
            SELECT 1
            FROM lending.loan_contract_schedule_registrations registration
            WHERE registration.schedule_id = schedule.id
        )
    INTO
        schedule_loan_id,
        schedule_status,
        schedule_registered
    FROM lending.loan_contract_schedules schedule
    WHERE schedule.id = NEW.schedule_id;

    IF NOT FOUND
       OR schedule_loan_id <> NEW.loan_id
       OR schedule_status <> 'active'
       OR NOT schedule_registered THEN
        RAISE EXCEPTION
            '7x7 Extra Principal requires the current verified active signed schedule for the same loan.';
    END IF;

    SELECT operational.operational_version
    INTO current_operational_version
    FROM lending.loan_schedule_operational_state operational
    WHERE operational.schedule_id = NEW.schedule_id;

    current_operational_version := coalesce(current_operational_version, 0);
    IF current_operational_version <> NEW.expected_operational_version THEN
        RAISE EXCEPTION
            '7x7 Extra Principal operational schedule version is stale.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_7x7_extra_principal_adjustment_validate
    ON lending.seven_by_seven_extra_principal_adjustments;
CREATE TRIGGER lending_7x7_extra_principal_adjustment_validate
BEFORE INSERT ON lending.seven_by_seven_extra_principal_adjustments
FOR EACH ROW EXECUTE FUNCTION lending.validate_7x7_extra_principal_adjustment();

CREATE OR REPLACE FUNCTION lending.validate_7x7_extra_principal_adjustment_item()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    adjustment_schedule_id UUID;
    installment_schedule_id UUID;
    installment_number_value INTEGER;
    signed_amount NUMERIC(18,2);
    signed_principal NUMERIC(18,2);
    signed_interest NUMERIC(18,2);
    current_amount NUMERIC(18,2);
    current_principal NUMERIC(18,2);
    current_interest NUMERIC(18,2);
    gross_active_advance NUMERIC(18,2);
    prior_refund_due NUMERIC(18,2);
BEGIN
    SELECT adjustment.schedule_id
    INTO adjustment_schedule_id
    FROM lending.seven_by_seven_extra_principal_adjustments adjustment
    WHERE adjustment.id = NEW.adjustment_id;

    SELECT
        installment.schedule_id,
        installment.installment_number,
        installment.contractual_amount,
        installment.principal_component,
        installment.interest_component
    INTO
        installment_schedule_id,
        installment_number_value,
        signed_amount,
        signed_principal,
        signed_interest
    FROM lending.loan_contract_installments installment
    WHERE installment.id = NEW.installment_id;

    IF adjustment_schedule_id IS NULL
       OR installment_schedule_id IS NULL
       OR installment_schedule_id <> adjustment_schedule_id
       OR signed_principal IS NULL
       OR signed_interest IS NULL
       OR installment_number_value <> NEW.installment_number
       OR signed_amount <> NEW.signed_contractual_amount
       OR signed_principal <> NEW.signed_principal_component
       OR signed_interest <> NEW.signed_interest_component THEN
        RAISE EXCEPTION
            '7x7 Extra Principal item must preserve the exact immutable signed installment evidence.';
    END IF;

    SELECT
        operational.operational_amount,
        operational.operational_principal_component,
        operational.operational_interest_component
    INTO
        current_amount,
        current_principal,
        current_interest
    FROM lending.loan_installment_operational_amounts operational
    WHERE operational.installment_id = NEW.installment_id;

    current_amount := coalesce(current_amount, signed_amount);
    current_principal := coalesce(current_principal, signed_principal);
    current_interest := coalesce(current_interest, signed_interest);

    IF current_amount <> NEW.prior_operational_amount
       OR current_principal <> NEW.prior_operational_principal_component
       OR current_interest <> NEW.prior_operational_interest_component THEN
        RAISE EXCEPTION
            '7x7 Extra Principal item does not match the current operational installment amount.';
    END IF;

    SELECT coalesce(sum(allocation.amount_applied), 0)::numeric(18,2)
    INTO gross_active_advance
    FROM lending.loan_installment_payment_allocations allocation
    JOIN lending.collection_transactions transaction
      ON transaction.id = allocation.transaction_id
    WHERE allocation.installment_id = NEW.installment_id
      AND allocation.allocation_basis = 'future_advance_oldest_first'
      AND transaction.is_voided = false;

    SELECT coalesce(sum(refund.amount_due), 0)::numeric(18,2)
    INTO prior_refund_due
    FROM lending.loan_unused_advance_refund_dues refund
    WHERE refund.installment_id = NEW.installment_id;

    IF greatest(gross_active_advance - prior_refund_due, 0)
       <> NEW.advance_allocated_before THEN
        RAISE EXCEPTION
            '7x7 Extra Principal active Advance does not reconcile after prior Refund Due classifications.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_7x7_extra_principal_item_validate
    ON lending.seven_by_seven_extra_principal_adjustment_items;
CREATE TRIGGER lending_7x7_extra_principal_item_validate
BEFORE INSERT ON lending.seven_by_seven_extra_principal_adjustment_items
FOR EACH ROW EXECUTE FUNCTION lending.validate_7x7_extra_principal_adjustment_item();

CREATE OR REPLACE FUNCTION lending.validate_loan_installment_operational_amount()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    item_record record;
BEGIN
    SELECT
        item.new_operational_amount,
        item.new_operational_principal_component,
        item.new_operational_interest_component,
        item.removed_from_operational_schedule
    INTO item_record
    FROM lending.seven_by_seven_extra_principal_adjustment_items item
    WHERE item.adjustment_id = NEW.last_extra_principal_adjustment_id
      AND item.installment_id = NEW.installment_id;

    IF NOT FOUND
       OR item_record.new_operational_amount <> NEW.operational_amount
       OR item_record.new_operational_principal_component
          <> NEW.operational_principal_component
       OR item_record.new_operational_interest_component
          <> NEW.operational_interest_component
       OR item_record.removed_from_operational_schedule
          <> NEW.removed_from_operational_schedule THEN
        RAISE EXCEPTION
            'Operational installment amount must match its immutable 7x7 Extra Principal adjustment item.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_installment_operational_amount_validate
    ON lending.loan_installment_operational_amounts;
CREATE TRIGGER lending_installment_operational_amount_validate
BEFORE INSERT OR UPDATE ON lending.loan_installment_operational_amounts
FOR EACH ROW EXECUTE FUNCTION lending.validate_loan_installment_operational_amount();

CREATE OR REPLACE FUNCTION lending.validate_unused_advance_refund_due()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    item_refund_due NUMERIC(18,2);
BEGIN
    SELECT item.advance_refund_due
    INTO item_refund_due
    FROM lending.seven_by_seven_extra_principal_adjustment_items item
    WHERE item.adjustment_id = NEW.adjustment_id
      AND item.installment_id = NEW.installment_id;

    IF NOT FOUND OR item_refund_due <> NEW.amount_due OR item_refund_due <= 0 THEN
        RAISE EXCEPTION
            'Unused Advance Refund Due must exactly match its immutable 7x7 Extra Principal adjustment item.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_unused_advance_refund_due_validate
    ON lending.loan_unused_advance_refund_dues;
CREATE TRIGGER lending_unused_advance_refund_due_validate
BEFORE INSERT ON lending.loan_unused_advance_refund_dues
FOR EACH ROW EXECUTE FUNCTION lending.validate_unused_advance_refund_due();

DROP TRIGGER IF EXISTS lending_7x7_extra_principal_adjustment_audit_guard
    ON lending.seven_by_seven_extra_principal_adjustments;
CREATE TRIGGER lending_7x7_extra_principal_adjustment_audit_guard
BEFORE UPDATE OR DELETE ON lending.seven_by_seven_extra_principal_adjustments
FOR EACH ROW EXECUTE FUNCTION lending.guard_loan_schedule_adjustment_audit();

DROP TRIGGER IF EXISTS lending_7x7_extra_principal_item_audit_guard
    ON lending.seven_by_seven_extra_principal_adjustment_items;
CREATE TRIGGER lending_7x7_extra_principal_item_audit_guard
BEFORE UPDATE OR DELETE ON lending.seven_by_seven_extra_principal_adjustment_items
FOR EACH ROW EXECUTE FUNCTION lending.guard_loan_schedule_adjustment_audit();

DROP TRIGGER IF EXISTS lending_unused_advance_refund_due_audit_guard
    ON lending.loan_unused_advance_refund_dues;
CREATE TRIGGER lending_unused_advance_refund_due_audit_guard
BEFORE UPDATE OR DELETE ON lending.loan_unused_advance_refund_dues
FOR EACH ROW EXECUTE FUNCTION lending.guard_loan_schedule_adjustment_audit();

-- Preserve the existing signed columns for compatibility and add explicit
-- operational amount columns beside the existing operational date overlay.
CREATE OR REPLACE VIEW lending.loan_contract_installments_operational AS
SELECT
    installment.id,
    installment.schedule_id,
    installment.installment_number,
    installment.due_date AS contractual_due_date,
    coalesce(date_state.effective_due_date, installment.due_date)
        AS effective_due_date,
    installment.contractual_amount,
    installment.principal_component,
    installment.interest_component,
    installment.created_at,
    date_state.last_adjustment_id,
    coalesce(amount_state.operational_amount, installment.contractual_amount)
        AS operational_amount,
    coalesce(
        amount_state.operational_principal_component,
        installment.principal_component
    ) AS operational_principal_component,
    coalesce(
        amount_state.operational_interest_component,
        installment.interest_component
    ) AS operational_interest_component,
    coalesce(amount_state.removed_from_operational_schedule, false)
        AS removed_from_operational_schedule,
    amount_state.last_extra_principal_adjustment_id
FROM lending.loan_contract_installments installment
LEFT JOIN lending.loan_installment_operational_dates date_state
  ON date_state.installment_id = installment.id
LEFT JOIN lending.loan_installment_operational_amounts amount_state
  ON amount_state.installment_id = installment.id;

-- Gross historical Advance remains immutable. Current active Advance is gross
-- verified future-row Advance less amounts already classified as Refund Due.
CREATE OR REPLACE VIEW lending.loan_installment_active_advance AS
WITH gross AS (
    SELECT
        installment.id AS installment_id,
        coalesce(sum(allocation.amount_applied) FILTER (
            WHERE transaction.is_voided = false
              AND allocation.allocation_basis = 'future_advance_oldest_first'
        ), 0)::numeric(18,2) AS gross_advance_allocated
    FROM lending.loan_contract_installments installment
    LEFT JOIN lending.loan_installment_payment_allocations allocation
      ON allocation.installment_id = installment.id
    LEFT JOIN lending.collection_transactions transaction
      ON transaction.id = allocation.transaction_id
    GROUP BY installment.id
), refunds AS (
    SELECT
        refund.installment_id,
        coalesce(sum(refund.amount_due), 0)::numeric(18,2) AS refund_due_total
    FROM lending.loan_unused_advance_refund_dues refund
    GROUP BY refund.installment_id
)
SELECT
    gross.installment_id,
    gross.gross_advance_allocated,
    coalesce(refunds.refund_due_total, 0)::numeric(18,2) AS refund_due_total,
    greatest(
        gross.gross_advance_allocated - coalesce(refunds.refund_due_total, 0),
        0
    )::numeric(18,2) AS active_advance_allocated
FROM gross
LEFT JOIN refunds
  ON refunds.installment_id = gross.installment_id;

COMMENT ON TABLE lending.seven_by_seven_extra_principal_adjustments IS
    'Immutable 7x7 Extra Principal schedule-effect header tied to the physical Payment receipt. It shortens only the operational future tail and never rewrites the signed schedule.';

COMMENT ON TABLE lending.seven_by_seven_extra_principal_adjustment_items IS
    'Immutable per-installment before/after projection for 7x7 Extra Principal, preserving signed terms, prior operational state, resulting operational state, and Advance conservation.';

COMMENT ON TABLE lending.loan_installment_operational_amounts IS
    'Current operational amount/principal/interest overlay created by audited 7x7 Extra Principal adjustments. Signed lending.loan_contract_installments rows remain unchanged.';

COMMENT ON TABLE lending.loan_unused_advance_refund_dues IS
    'Immutable classification that Advance is no longer needed after 7x7 Extra Principal. It is not cash release, is never silently netted to another loan, and requires a separate Management-approved refund release workflow.';

COMMENT ON VIEW lending.loan_installment_active_advance IS
    'Current installment-specific Advance available to satisfy the installment: immutable gross verified Advance less immutable Refund Due classifications. It is not a floating wallet.';

COMMIT;