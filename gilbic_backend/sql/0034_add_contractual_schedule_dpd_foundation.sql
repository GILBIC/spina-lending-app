BEGIN;

-- Stage 5E.4.1 establishes the contractual payment-schedule and DPD foundation.
-- A loan is past due only against amounts that were contractually due under the
-- active signed contract schedule. This migration does not infer a schedule
-- from the old 120-day/daily convention, does not classify Default/Non-default,
-- does not calculate ECL, and does not post to the General Ledger.

CREATE TABLE IF NOT EXISTS lending.loan_contract_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    schedule_version INTEGER NOT NULL CHECK (schedule_version > 0),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'superseded')),
    payment_frequency TEXT NOT NULL CHECK (
        payment_frequency IN (
            'daily',
            'weekly',
            'semi_monthly',
            'monthly',
            'balloon',
            'custom'
        )
    ),
    contract_reference TEXT NOT NULL,
    contract_signed_date DATE,
    effective_from DATE NOT NULL,
    grace_days INTEGER NOT NULL DEFAULT 0 CHECK (grace_days >= 0),
    settings JSONB NOT NULL DEFAULT '{}'::jsonb,
    supersedes_schedule_id UUID
        REFERENCES lending.loan_contract_schedules(id) ON DELETE RESTRICT,
    created_by_user_id UUID REFERENCES core.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (btrim(contract_reference) <> ''),
    UNIQUE (loan_id, schedule_version),
    CHECK (
        (schedule_version = 1 AND supersedes_schedule_id IS NULL)
        OR schedule_version > 1
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS lending_loan_contract_one_active_uidx
    ON lending.loan_contract_schedules(loan_id)
    WHERE status = 'active';
CREATE INDEX IF NOT EXISTS lending_loan_contract_schedule_loan_version_idx
    ON lending.loan_contract_schedules(loan_id, schedule_version DESC);

CREATE TABLE IF NOT EXISTS lending.loan_contract_installments (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    schedule_id UUID NOT NULL
        REFERENCES lending.loan_contract_schedules(id) ON DELETE RESTRICT,
    installment_number INTEGER NOT NULL CHECK (installment_number > 0),
    due_date DATE NOT NULL,
    contractual_amount NUMERIC(18,2) NOT NULL CHECK (contractual_amount > 0),
    principal_component NUMERIC(18,2)
        CHECK (principal_component IS NULL OR principal_component >= 0),
    interest_component NUMERIC(18,2)
        CHECK (interest_component IS NULL OR interest_component >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (schedule_id, installment_number)
);

CREATE INDEX IF NOT EXISTS lending_loan_contract_installment_due_idx
    ON lending.loan_contract_installments(schedule_id, due_date, installment_number);

CREATE TABLE IF NOT EXISTS lending.loan_installment_payment_allocations (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    installment_id BIGINT NOT NULL
        REFERENCES lending.loan_contract_installments(id) ON DELETE RESTRICT,
    transaction_id UUID NOT NULL
        REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    amount_applied NUMERIC(18,2) NOT NULL CHECK (amount_applied > 0),
    allocation_basis TEXT NOT NULL CHECK (
        allocation_basis IN (
            'exact_covered_date',
            'oldest_due_first',
            'contract_reference',
            'manual_review'
        )
    ),
    allocation_reference TEXT,
    created_by_user_id UUID REFERENCES core.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (installment_id, transaction_id)
);

CREATE INDEX IF NOT EXISTS lending_loan_installment_allocation_tx_idx
    ON lending.loan_installment_payment_allocations(transaction_id);

CREATE OR REPLACE FUNCTION lending.guard_loan_installment_payment_allocation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    installment_loan_id UUID;
    transaction_loan_id UUID;
    transaction_amount NUMERIC(18,2);
    transaction_voided BOOLEAN;
    allocated_elsewhere NUMERIC(18,2);
BEGIN
    SELECT schedule.loan_id
    INTO installment_loan_id
    FROM lending.loan_contract_installments installment
    JOIN lending.loan_contract_schedules schedule
      ON schedule.id = installment.schedule_id
    WHERE installment.id = NEW.installment_id;

    SELECT transaction.loan_id, transaction.amount, transaction.is_voided
    INTO transaction_loan_id, transaction_amount, transaction_voided
    FROM lending.collection_transactions transaction
    WHERE transaction.id = NEW.transaction_id;

    IF installment_loan_id IS NULL OR transaction_loan_id IS NULL THEN
        RAISE EXCEPTION 'Installment and collection transaction must exist before payment allocation.';
    END IF;

    IF installment_loan_id <> transaction_loan_id THEN
        RAISE EXCEPTION 'Payment allocation must stay within the same loan.';
    END IF;

    IF transaction_voided THEN
        RAISE EXCEPTION 'A voided collection transaction cannot be allocated to a contractual installment.';
    END IF;

    SELECT coalesce(sum(allocation.amount_applied), 0)
    INTO allocated_elsewhere
    FROM lending.loan_installment_payment_allocations allocation
    WHERE allocation.transaction_id = NEW.transaction_id
      AND (TG_OP = 'INSERT' OR allocation.id <> NEW.id);

    IF allocated_elsewhere + NEW.amount_applied > transaction_amount THEN
        RAISE EXCEPTION 'Contractual installment allocations cannot exceed the collection transaction amount.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_loan_installment_payment_allocation_guard
    ON lending.loan_installment_payment_allocations;
CREATE TRIGGER lending_loan_installment_payment_allocation_guard
BEFORE INSERT OR UPDATE ON lending.loan_installment_payment_allocations
FOR EACH ROW EXECUTE FUNCTION lending.guard_loan_installment_payment_allocation();

CREATE OR REPLACE VIEW accounting.loan_contract_dpd_assessment AS
WITH active_schedule AS (
    SELECT
        loan.id AS loan_id,
        loan.loan_number,
        loan.status AS loan_status,
        schedule.id AS schedule_id,
        schedule.schedule_version,
        schedule.payment_frequency,
        schedule.contract_reference,
        schedule.contract_signed_date,
        schedule.effective_from,
        schedule.grace_days
    FROM lending.loans loan
    LEFT JOIN lending.loan_contract_schedules schedule
      ON schedule.loan_id = loan.id
     AND schedule.status = 'active'
), installment_balance AS (
    SELECT
        schedule.loan_id,
        installment.schedule_id,
        installment.id AS installment_id,
        installment.installment_number,
        installment.due_date,
        installment.contractual_amount,
        coalesce(sum(allocation.amount_applied) FILTER (
            WHERE transaction.is_voided = false
        ), 0)::numeric(18,2) AS allocated_amount
    FROM lending.loan_contract_schedules schedule
    JOIN lending.loan_contract_installments installment
      ON installment.schedule_id = schedule.id
    LEFT JOIN lending.loan_installment_payment_allocations allocation
      ON allocation.installment_id = installment.id
    LEFT JOIN lending.collection_transactions transaction
      ON transaction.id = allocation.transaction_id
    WHERE schedule.status = 'active'
    GROUP BY
        schedule.loan_id,
        installment.schedule_id,
        installment.id,
        installment.installment_number,
        installment.due_date,
        installment.contractual_amount
), installment_rollup AS (
    SELECT
        active.loan_id,
        count(balance.installment_id)::bigint AS installment_count,
        coalesce(sum(balance.contractual_amount), 0)::numeric(18,2)
            AS contractual_schedule_total,
        coalesce(sum(balance.allocated_amount), 0)::numeric(18,2)
            AS allocated_schedule_total,
        coalesce(sum(
            greatest(balance.contractual_amount - balance.allocated_amount, 0)
        ) FILTER (
            WHERE balance.due_date + active.grace_days <= current_date
        ), 0)::numeric(18,2) AS due_unpaid_amount,
        min(balance.due_date + active.grace_days) FILTER (
            WHERE balance.due_date + active.grace_days < current_date
              AND balance.allocated_amount < balance.contractual_amount
        ) AS earliest_unpaid_due_date
    FROM active_schedule active
    LEFT JOIN installment_balance balance
      ON balance.loan_id = active.loan_id
    GROUP BY active.loan_id
), transaction_rollup AS (
    SELECT
        active.loan_id,
        coalesce(sum(transaction.amount) FILTER (
            WHERE transaction.is_voided = false
              AND transaction.entry_type IN ('payment', 'advance')
              AND transaction.collection_date >= active.effective_from
        ), 0)::numeric(18,2) AS eligible_transaction_total
    FROM active_schedule active
    LEFT JOIN lending.collection_transactions transaction
      ON transaction.loan_id = active.loan_id
    GROUP BY active.loan_id
), allocation_rollup AS (
    SELECT
        active.loan_id,
        coalesce(sum(allocation.amount_applied) FILTER (
            WHERE transaction.is_voided = false
              AND transaction.entry_type IN ('payment', 'advance')
              AND transaction.collection_date >= active.effective_from
        ), 0)::numeric(18,2) AS eligible_allocated_total
    FROM active_schedule active
    LEFT JOIN lending.loan_contract_installments installment
      ON installment.schedule_id = active.schedule_id
    LEFT JOIN lending.loan_installment_payment_allocations allocation
      ON allocation.installment_id = installment.id
    LEFT JOIN lending.collection_transactions transaction
      ON transaction.id = allocation.transaction_id
    GROUP BY active.loan_id
)
SELECT
    active.loan_id,
    active.loan_number,
    active.loan_status,
    active.schedule_id,
    active.schedule_version,
    active.payment_frequency,
    active.contract_reference,
    active.contract_signed_date,
    active.effective_from,
    active.grace_days,
    coalesce(installments.installment_count, 0) AS installment_count,
    coalesce(installments.contractual_schedule_total, 0)::numeric(18,2)
        AS contractual_schedule_total,
    coalesce(installments.allocated_schedule_total, 0)::numeric(18,2)
        AS allocated_schedule_total,
    coalesce(transactions.eligible_transaction_total, 0)::numeric(18,2)
        AS eligible_transaction_total,
    coalesce(allocations.eligible_allocated_total, 0)::numeric(18,2)
        AS eligible_allocated_total,
    coalesce(installments.due_unpaid_amount, 0)::numeric(18,2)
        AS due_unpaid_amount,
    installments.earliest_unpaid_due_date,
    CASE
        WHEN active.schedule_id IS NULL THEN 'contract_schedule_required'
        WHEN coalesce(installments.installment_count, 0) = 0
            THEN 'contract_installments_required'
        WHEN coalesce(transactions.eligible_transaction_total, 0)
             <> coalesce(allocations.eligible_allocated_total, 0)
            THEN 'payment_allocation_required'
        ELSE 'ready'
    END AS dpd_data_status,
    CASE
        WHEN active.schedule_id IS NULL
          OR coalesce(installments.installment_count, 0) = 0
          OR coalesce(transactions.eligible_transaction_total, 0)
             <> coalesce(allocations.eligible_allocated_total, 0)
            THEN NULL::integer
        WHEN installments.earliest_unpaid_due_date IS NULL THEN 0
        ELSE greatest(
            current_date - installments.earliest_unpaid_due_date,
            0
        )::integer
    END AS days_past_due,
    CASE
        WHEN active.schedule_id IS NULL
          OR coalesce(installments.installment_count, 0) = 0
          OR coalesce(transactions.eligible_transaction_total, 0)
             <> coalesce(allocations.eligible_allocated_total, 0)
            THEN false
        WHEN installments.earliest_unpaid_due_date IS NULL THEN false
        ELSE current_date - installments.earliest_unpaid_due_date >= 30
    END AS thirty_day_sicr_backstop_reached,
    CASE
        WHEN active.schedule_id IS NULL
          OR coalesce(installments.installment_count, 0) = 0
          OR coalesce(transactions.eligible_transaction_total, 0)
             <> coalesce(allocations.eligible_allocated_total, 0)
            THEN false
        WHEN installments.earliest_unpaid_due_date IS NULL THEN false
        ELSE current_date - installments.earliest_unpaid_due_date >= 90
    END AS ninety_day_default_backstop_reached,
    false AS automatic_default_label_written,
    false AS ecl_included,
    NULL::numeric(18,2) AS ecl_amount,
    false AS ready_to_post
FROM active_schedule active
LEFT JOIN installment_rollup installments
  ON installments.loan_id = active.loan_id
LEFT JOIN transaction_rollup transactions
  ON transactions.loan_id = active.loan_id
LEFT JOIN allocation_rollup allocations
  ON allocations.loan_id = active.loan_id;

CREATE OR REPLACE VIEW accounting.loan_contract_dpd_summary AS
SELECT
    count(*)::bigint AS loan_count,
    count(*) FILTER (WHERE dpd_data_status = 'ready')::bigint AS ready_count,
    count(*) FILTER (
        WHERE dpd_data_status = 'contract_schedule_required'
    )::bigint AS contract_schedule_required_count,
    count(*) FILTER (
        WHERE dpd_data_status = 'contract_installments_required'
    )::bigint AS contract_installments_required_count,
    count(*) FILTER (
        WHERE dpd_data_status = 'payment_allocation_required'
    )::bigint AS payment_allocation_required_count,
    count(*) FILTER (
        WHERE dpd_data_status = 'ready' AND days_past_due > 0
    )::bigint AS past_due_count,
    count(*) FILTER (
        WHERE dpd_data_status = 'ready' AND thirty_day_sicr_backstop_reached
    )::bigint AS thirty_day_backstop_count,
    count(*) FILTER (
        WHERE dpd_data_status = 'ready' AND ninety_day_default_backstop_reached
    )::bigint AS ninety_day_backstop_count,
    false AS automatic_default_label_written,
    false AS ecl_included,
    NULL::numeric(18,2) AS ecl_amount,
    false AS ready_to_post
FROM accounting.loan_contract_dpd_assessment;

COMMENT ON TABLE lending.loan_contract_schedules IS
    'Versioned signed-contract payment schedule header. Payment frequency may be daily, weekly, semi-monthly, monthly, balloon, or custom. Existing loans are not auto-backfilled from generic product assumptions.';
COMMENT ON TABLE lending.loan_contract_installments IS
    'Exact contractual installment dates and amounts used as the primary source for DPD measurement.';
COMMENT ON TABLE lending.loan_installment_payment_allocations IS
    'Explicit application of non-voided collection cash to contractual installments. DPD remains unavailable while eligible payment amounts are not fully allocated.';
COMMENT ON VIEW accounting.loan_contract_dpd_assessment IS
    'Read-only contract-driven DPD assessment. 30-day SICR and 90-day default fields are rebuttable backstop flags only; they do not write a credit classification.';
COMMENT ON VIEW accounting.loan_contract_dpd_summary IS
    'Stage 5E.4.1 readiness summary for contract-driven DPD. No ECL amount or General Ledger posting is produced.';

COMMIT;
