BEGIN;

-- 7x7 Extra Principal keeps the immutable signed schedule as evidence while
-- shortening only the operational future tail. DPD therefore must measure
-- delinquency against the current operational amount/effective date, and only
-- current active Advance may satisfy that amount. Historical gross Advance and
-- signed contractual totals remain visible for audit/reconciliation.

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
        installment.operational_amount,
        installment.removed_from_operational_schedule,
        coalesce(sum(allocation.amount_applied) FILTER (
            WHERE transaction.is_voided = false
        ), 0)::numeric(18,2) AS historical_allocated_amount,
        (
            coalesce(sum(allocation.amount_applied) FILTER (
                WHERE transaction.is_voided = false
                  AND allocation.allocation_basis <> 'future_advance_oldest_first'
            ), 0)
            + coalesce(active_advance.active_advance_allocated, 0)
        )::numeric(18,2) AS active_allocated_amount
    FROM lending.loan_contract_schedules schedule
    JOIN lending.loan_contract_installments_operational installment
      ON installment.schedule_id = schedule.id
    LEFT JOIN lending.loan_installment_payment_allocations allocation
      ON allocation.installment_id = installment.id
    LEFT JOIN lending.collection_transactions transaction
      ON transaction.id = allocation.transaction_id
    LEFT JOIN lending.loan_installment_active_advance active_advance
      ON active_advance.installment_id = installment.id
    WHERE schedule.status = 'active'
    GROUP BY
        schedule.loan_id,
        installment.schedule_id,
        installment.id,
        installment.installment_number,
        installment.effective_due_date,
        installment.contractual_amount,
        installment.operational_amount,
        installment.removed_from_operational_schedule,
        active_advance.active_advance_allocated
), installment_rollup AS (
    SELECT
        active.loan_id,
        count(balance.installment_id)::bigint AS installment_count,
        coalesce(sum(balance.contractual_amount), 0)::numeric(18,2)
            AS contractual_schedule_total,
        coalesce(sum(balance.historical_allocated_amount), 0)::numeric(18,2)
            AS allocated_schedule_total,
        coalesce(sum(
            greatest(balance.operational_amount - balance.active_allocated_amount, 0)
        ) FILTER (
            WHERE balance.due_date + active.grace_days <= current_date
              AND balance.removed_from_operational_schedule = false
        ), 0)::numeric(18,2) AS due_unpaid_amount,
        min(balance.due_date + active.grace_days) FILTER (
            WHERE balance.due_date + active.grace_days < current_date
              AND balance.removed_from_operational_schedule = false
              AND balance.active_allocated_amount < balance.operational_amount
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
        ), 0)::numeric(18,2) AS historical_installment_allocation_total
    FROM active_schedule active
    LEFT JOIN lending.loan_contract_installments installment
      ON installment.schedule_id = active.schedule_id
    LEFT JOIN lending.loan_installment_payment_allocations allocation
      ON allocation.installment_id = installment.id
    LEFT JOIN lending.collection_transactions transaction
      ON transaction.id = allocation.transaction_id
    GROUP BY active.loan_id
), extra_principal_rollup AS (
    SELECT
        active.loan_id,
        coalesce(sum(adjustment.principal_reduction) FILTER (
            WHERE source_transaction.is_voided = false
              AND source_transaction.collection_date >= active.effective_from
        ), 0)::numeric(18,2) AS extra_principal_allocation_total
    FROM active_schedule active
    LEFT JOIN lending.seven_by_seven_extra_principal_adjustments adjustment
      ON adjustment.schedule_id = active.schedule_id
    LEFT JOIN lending.collection_transactions source_transaction
      ON source_transaction.id = adjustment.transaction_id
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
    (
        coalesce(allocations.historical_installment_allocation_total, 0)
        + coalesce(extra_principal.extra_principal_allocation_total, 0)
    )::numeric(18,2) AS eligible_allocated_total,
    coalesce(installments.due_unpaid_amount, 0)::numeric(18,2)
        AS due_unpaid_amount,
    installments.earliest_unpaid_due_date,
    CASE
        WHEN active.schedule_id IS NULL THEN 'contract_schedule_required'
        WHEN coalesce(installments.installment_count, 0) = 0
            THEN 'contract_installments_required'
        WHEN coalesce(transactions.eligible_transaction_total, 0)
             <> (
                 coalesce(allocations.historical_installment_allocation_total, 0)
                 + coalesce(extra_principal.extra_principal_allocation_total, 0)
             )
            THEN 'payment_allocation_required'
        ELSE 'ready'
    END AS dpd_data_status,
    CASE
        WHEN active.schedule_id IS NULL
          OR coalesce(installments.installment_count, 0) = 0
          OR coalesce(transactions.eligible_transaction_total, 0)
             <> (
                 coalesce(allocations.historical_installment_allocation_total, 0)
                 + coalesce(extra_principal.extra_principal_allocation_total, 0)
             )
            THEN NULL::integer
        WHEN installments.earliest_unpaid_due_date IS NULL THEN 0
        ELSE greatest(current_date - installments.earliest_unpaid_due_date, 0)::integer
    END AS days_past_due,
    CASE
        WHEN active.schedule_id IS NULL
          OR coalesce(installments.installment_count, 0) = 0
          OR coalesce(transactions.eligible_transaction_total, 0)
             <> (
                 coalesce(allocations.historical_installment_allocation_total, 0)
                 + coalesce(extra_principal.extra_principal_allocation_total, 0)
             )
            THEN false
        WHEN installments.earliest_unpaid_due_date IS NULL THEN false
        ELSE current_date - installments.earliest_unpaid_due_date >= 30
    END AS thirty_day_sicr_backstop_reached,
    CASE
        WHEN active.schedule_id IS NULL
          OR coalesce(installments.installment_count, 0) = 0
          OR coalesce(transactions.eligible_transaction_total, 0)
             <> (
                 coalesce(allocations.historical_installment_allocation_total, 0)
                 + coalesce(extra_principal.extra_principal_allocation_total, 0)
             )
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
  ON allocations.loan_id = active.loan_id
LEFT JOIN extra_principal_rollup extra_principal
  ON extra_principal.loan_id = active.loan_id;

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

COMMENT ON VIEW accounting.loan_contract_dpd_assessment IS
    'Contract-driven DPD using immutable signed totals for audit and the current operational amount/effective-date overlay for delinquency. Active Advance is gross verified Advance less Refund Due; explicit 7x7 Extra Principal adjustment amounts reconcile their source receipt without rewriting installment allocations.';

COMMIT;
