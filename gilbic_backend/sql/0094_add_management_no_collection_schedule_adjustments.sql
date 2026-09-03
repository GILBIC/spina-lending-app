BEGIN;

-- Management-only No Collection shifts operational collection dates without
-- rewriting the immutable signed-contract due_date evidence.
INSERT INTO core.permissions (code, description)
VALUES (
    'lending.no_collection.manage',
    'Declare or reverse audited per-loan No Collection schedule adjustments without rewriting signed-contract due dates'
)
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code = 'lending.no_collection.manage'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS lending.loan_schedule_operational_state (
    schedule_id UUID PRIMARY KEY
        REFERENCES lending.loan_contract_schedules(id) ON DELETE RESTRICT,
    operational_version INTEGER NOT NULL DEFAULT 0
        CHECK (operational_version >= 0),
    updated_by_user_id UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS lending.loan_schedule_adjustments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    schedule_id UUID NOT NULL
        REFERENCES lending.loan_contract_schedules(id) ON DELETE RESTRICT,
    adjustment_type TEXT NOT NULL
        CHECK (adjustment_type IN ('no_collection', 'reversal')),
    no_collection_date DATE NOT NULL,
    reason TEXT NOT NULL CHECK (btrim(reason) <> ''),
    expected_operational_version INTEGER NOT NULL
        CHECK (expected_operational_version >= 0),
    resulting_operational_version INTEGER NOT NULL
        CHECK (resulting_operational_version > 0),
    reverses_adjustment_id UUID
        REFERENCES lending.loan_schedule_adjustments(id) ON DELETE RESTRICT,
    actor_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (adjustment_type = 'no_collection' AND reverses_adjustment_id IS NULL)
        OR
        (adjustment_type = 'reversal' AND reverses_adjustment_id IS NOT NULL)
    ),
    UNIQUE (schedule_id, resulting_operational_version),
    UNIQUE (reverses_adjustment_id)
);

CREATE INDEX IF NOT EXISTS lending_loan_schedule_adjustments_loan_created_idx
    ON lending.loan_schedule_adjustments(loan_id, created_at DESC);
CREATE INDEX IF NOT EXISTS lending_loan_schedule_adjustments_date_idx
    ON lending.loan_schedule_adjustments(schedule_id, no_collection_date);

CREATE TABLE IF NOT EXISTS lending.loan_schedule_adjustment_items (
    adjustment_id UUID NOT NULL
        REFERENCES lending.loan_schedule_adjustments(id) ON DELETE RESTRICT,
    installment_id BIGINT NOT NULL
        REFERENCES lending.loan_contract_installments(id) ON DELETE RESTRICT,
    installment_number INTEGER NOT NULL CHECK (installment_number > 0),
    contractual_due_date DATE NOT NULL,
    prior_effective_due_date DATE NOT NULL,
    new_effective_due_date DATE NOT NULL,
    contractual_amount NUMERIC(18,2) NOT NULL CHECK (contractual_amount > 0),
    PRIMARY KEY (adjustment_id, installment_id),
    CHECK (prior_effective_due_date <> new_effective_due_date)
);

CREATE INDEX IF NOT EXISTS lending_loan_schedule_adjustment_items_installment_idx
    ON lending.loan_schedule_adjustment_items(installment_id, adjustment_id);

CREATE TABLE IF NOT EXISTS lending.loan_installment_operational_dates (
    installment_id BIGINT PRIMARY KEY
        REFERENCES lending.loan_contract_installments(id) ON DELETE RESTRICT,
    effective_due_date DATE NOT NULL,
    last_adjustment_id UUID NOT NULL
        REFERENCES lending.loan_schedule_adjustments(id) ON DELETE RESTRICT,
    updated_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE VIEW lending.loan_contract_installments_operational AS
SELECT
    installment.id,
    installment.schedule_id,
    installment.installment_number,
    installment.due_date AS contractual_due_date,
    coalesce(operational.effective_due_date, installment.due_date)
        AS effective_due_date,
    installment.contractual_amount,
    installment.principal_component,
    installment.interest_component,
    installment.created_at,
    operational.last_adjustment_id
FROM lending.loan_contract_installments installment
LEFT JOIN lending.loan_installment_operational_dates operational
  ON operational.installment_id = installment.id;

CREATE OR REPLACE FUNCTION lending.guard_loan_schedule_adjustment_audit()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Loan schedule adjustment audit records are immutable.';
END;
$$;

DROP TRIGGER IF EXISTS lending_loan_schedule_adjustment_audit_guard
    ON lending.loan_schedule_adjustments;
CREATE TRIGGER lending_loan_schedule_adjustment_audit_guard
BEFORE UPDATE OR DELETE ON lending.loan_schedule_adjustments
FOR EACH ROW EXECUTE FUNCTION lending.guard_loan_schedule_adjustment_audit();

DROP TRIGGER IF EXISTS lending_loan_schedule_adjustment_item_audit_guard
    ON lending.loan_schedule_adjustment_items;
CREATE TRIGGER lending_loan_schedule_adjustment_item_audit_guard
BEFORE UPDATE OR DELETE ON lending.loan_schedule_adjustment_items
FOR EACH ROW EXECUTE FUNCTION lending.guard_loan_schedule_adjustment_audit();

-- DPD uses the operational schedule overlay so a Management-declared No
-- Collection date does not become client delinquency. Original contractual
-- due_date remains untouched in lending.loan_contract_installments.
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
        installment.effective_due_date AS due_date,
        installment.contractual_amount,
        coalesce(sum(allocation.amount_applied) FILTER (
            WHERE transaction.is_voided = false
        ), 0)::numeric(18,2) AS allocated_amount
    FROM lending.loan_contract_schedules schedule
    JOIN lending.loan_contract_installments_operational installment
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
        installment.effective_due_date,
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
        ELSE greatest(current_date - installments.earliest_unpaid_due_date, 0)::integer
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

COMMENT ON TABLE lending.loan_schedule_adjustments IS
    'Immutable Management schedule-adjustment audit. No Collection and reversal actions are versioned per verified loan schedule.';
COMMENT ON TABLE lending.loan_schedule_adjustment_items IS
    'Immutable old/new operational due-date evidence for every installment moved by one schedule adjustment.';
COMMENT ON TABLE lending.loan_installment_operational_dates IS
    'Current operational due-date overlay. The signed-contract due_date in loan_contract_installments remains immutable.';
COMMENT ON VIEW lending.loan_contract_installments_operational IS
    'Signed-contract installments plus current Management-approved operational due-date overlay.';

COMMIT;
