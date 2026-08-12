BEGIN;

-- Master Issue #296: first protected slice of the remaining 7x7 accounting
-- lifecycle. This migration is read-only accounting evidence/preview only.
-- It consumes the immutable 0063 original-EIR / initial-carrying anchor and
-- exact collection transaction UUIDs, proves deterministic source identity,
-- rolls accounting EIR/carrying components forward, and separately reproduces
-- the protected Desktop operational allocator for regression comparison.
--
-- Policy boundary:
-- * PostgreSQL collection entry_type values are lowercase payment/advance/pass.
-- * payment/advance source amounts are accounting cash evidence; operational
--   allocation is never substituted for accounting EIR allocation.
-- * pass creates no accounting cash event.
-- * voided payment/advance rows are excluded from the normal forward preview;
--   a later protected accounting reversal must reverse exact protected journal
--   history rather than inventing a source reversal transaction.
-- * Desktop has one effective payment per loan/calendar date. Multiple active
--   positive payment/advance rows on one date fail closed; no accepted_at/UUID
--   ordering is invented as an intraday accounting convention.
-- * authoritative current carrying, drafts, journals, posting and automatic
--   source posting remain disabled in this slice.

CREATE OR REPLACE FUNCTION accounting.seven_by_seven_collection_source_event_key(
    p_transaction_id UUID
)
RETURNS TEXT
LANGUAGE sql
IMMUTABLE
STRICT
AS $$
    SELECT 'collection:' || p_transaction_id::text;
$$;

CREATE OR REPLACE VIEW accounting.seven_by_seven_collection_source_inventory AS
SELECT
    transaction.id AS transaction_id,
    transaction.collector_user_id,
    transaction.loan_id,
    loan.loan_number,
    loan.status AS loan_status,
    loan.principal AS contractual_principal,
    loan.date_released,
    loan.due_date,
    loan_type.code AS loan_type_code,
    loan_type.name AS loan_type_name,
    loan_type.daily_interest_per_1000,
    transaction.collection_date,
    transaction.collection_day,
    transaction.entry_type,
    transaction.amount,
    transaction.accepted_at,
    transaction.device_sequence,
    transaction.registered_device_id,
    transaction.route_revision,
    transaction.remittance_id,
    transaction.is_locked,
    transaction.is_voided,
    transaction.voided_at,
    transaction.voided_by_user_id,
    transaction.void_reason,
    (
        NOT transaction.is_voided
        AND transaction.entry_type IN ('payment', 'advance')
        AND transaction.amount > 0
    ) AS is_active_positive_cash_event,
    (
        NOT transaction.is_voided
        AND transaction.entry_type IN ('payment', 'advance')
        AND transaction.amount <= 0
    ) AS is_nonpositive_financial_source_event,
    (
        NOT transaction.is_voided
        AND transaction.entry_type = 'pass'
        AND transaction.amount > 0
    ) AS is_unsupported_positive_pass,
    CASE
        WHEN NOT transaction.is_voided
         AND transaction.entry_type IN ('payment', 'advance')
         AND transaction.amount > 0
            THEN accounting.seven_by_seven_collection_source_event_key(transaction.id)
        ELSE NULL
    END AS source_event_key,
    count(*) FILTER (
        WHERE NOT transaction.is_voided
          AND transaction.entry_type IN ('payment', 'advance')
          AND transaction.amount > 0
    ) OVER (
        PARTITION BY transaction.loan_id, transaction.collection_date
    )::bigint AS active_positive_cash_events_on_date
FROM lending.collection_transactions transaction
JOIN lending.loans loan ON loan.id = transaction.loan_id
JOIN lending.loan_types loan_type ON loan_type.id = loan.loan_type_id
WHERE loan_type.calculation_mode = 'seven_by_seven';

CREATE OR REPLACE VIEW accounting.seven_by_seven_source_event_accounting_readiness AS
WITH inventory_summary AS (
    SELECT
        anchor.loan_id,
        count(inventory.transaction_id) FILTER (
            WHERE inventory.is_active_positive_cash_event
        )::bigint AS active_positive_cash_event_count,
        count(DISTINCT inventory.collection_date) FILTER (
            WHERE inventory.is_active_positive_cash_event
              AND inventory.active_positive_cash_events_on_date > 1
        )::bigint AS duplicate_active_cash_date_count,
        count(inventory.transaction_id) FILTER (
            WHERE inventory.is_active_positive_cash_event
              AND inventory.collection_date <= anchor.date_released
        )::bigint AS same_day_or_pre_anchor_cash_event_count,
        count(inventory.transaction_id) FILTER (
            WHERE inventory.is_active_positive_cash_event
              AND inventory.collection_date > anchor.due_date
        )::bigint AS post_maturity_cash_event_count,
        count(inventory.transaction_id) FILTER (
            WHERE inventory.is_nonpositive_financial_source_event
        )::bigint AS nonpositive_financial_source_event_count,
        count(inventory.transaction_id) FILTER (
            WHERE inventory.is_unsupported_positive_pass
        )::bigint AS unsupported_positive_pass_count,
        count(inventory.transaction_id) FILTER (
            WHERE inventory.is_voided
              AND inventory.entry_type IN ('payment', 'advance')
        )::bigint AS voided_original_cash_event_count
    FROM accounting.seven_by_seven_eir_initial_carrying_readiness anchor
    LEFT JOIN accounting.seven_by_seven_collection_source_inventory inventory
      ON inventory.loan_id = anchor.loan_id
    GROUP BY anchor.loan_id
)
SELECT
    anchor.*,
    coalesce(summary.active_positive_cash_event_count, 0)::bigint
        AS active_positive_cash_event_count,
    coalesce(summary.duplicate_active_cash_date_count, 0)::bigint
        AS duplicate_active_cash_date_count,
    coalesce(summary.same_day_or_pre_anchor_cash_event_count, 0)::bigint
        AS same_day_or_pre_anchor_cash_event_count,
    coalesce(summary.post_maturity_cash_event_count, 0)::bigint
        AS post_maturity_cash_event_count,
    coalesce(summary.nonpositive_financial_source_event_count, 0)::bigint
        AS nonpositive_financial_source_event_count,
    coalesce(summary.unsupported_positive_pass_count, 0)::bigint
        AS unsupported_positive_pass_count,
    coalesce(summary.voided_original_cash_event_count, 0)::bigint
        AS voided_original_cash_event_count,
    (
        anchor.eir_initial_carrying_readiness_status =
            'eir_initial_carrying_anchor_ready_for_7x7_accounting_lifecycle'
        AND anchor.active_anchor_exists
        AND anchor.active_anchor_is_current
        AND anchor.anchor_eir_reconciles
        AND anchor.eir_policy_ready
        AND anchor.initial_carrying_amount_ready
        AND coalesce(summary.duplicate_active_cash_date_count, 0) = 0
        AND coalesce(summary.same_day_or_pre_anchor_cash_event_count, 0) = 0
        AND coalesce(summary.post_maturity_cash_event_count, 0) = 0
        AND coalesce(summary.nonpositive_financial_source_event_count, 0) = 0
        AND coalesce(summary.unsupported_positive_pass_count, 0) = 0
    ) AS source_event_structure_ready,
    false AS authoritative_current_carrying_amount_ready,
    false AS journal_draft_enabled,
    false AS journal_lines_enabled,
    false AS automatic_source_posting,
    CASE
        WHEN anchor.eir_initial_carrying_readiness_status <>
            'eir_initial_carrying_anchor_ready_for_7x7_accounting_lifecycle'
            THEN anchor.eir_initial_carrying_readiness_status
        WHEN coalesce(summary.duplicate_active_cash_date_count, 0) > 0
            THEN 'same_day_multiple_financial_source_events'
        WHEN coalesce(summary.same_day_or_pre_anchor_cash_event_count, 0) > 0
            THEN 'same_day_or_pre_anchor_cash_ordering_review'
        WHEN coalesce(summary.post_maturity_cash_event_count, 0) > 0
            THEN 'post_maturity_cash_event_policy_review'
        WHEN coalesce(summary.nonpositive_financial_source_event_count, 0) > 0
            THEN 'nonpositive_payment_or_advance_source_review'
        WHEN coalesce(summary.unsupported_positive_pass_count, 0) > 0
            THEN 'positive_pass_source_review'
        ELSE 'source_event_structure_ready_for_eir_preview'
    END AS source_event_readiness_status
FROM accounting.seven_by_seven_eir_initial_carrying_readiness anchor
LEFT JOIN inventory_summary summary ON summary.loan_id = anchor.loan_id;

CREATE OR REPLACE FUNCTION accounting.preview_seven_by_seven_source_event_accounting(
    p_loan_id UUID
)
RETURNS TABLE (
    loan_id UUID,
    loan_number TEXT,
    anchor_id UUID,
    anchor_review_token TEXT,
    authoritative_daily_eir NUMERIC(24,12),
    authoritative_initial_gross_carrying_amount NUMERIC(18,2),
    transaction_id UUID,
    source_event_key TEXT,
    source_event_sequence INTEGER,
    collector_user_id UUID,
    collection_date DATE,
    collection_day INTEGER,
    entry_type TEXT,
    source_cash_amount NUMERIC(18,2),
    accepted_at TIMESTAMPTZ,
    device_sequence BIGINT,
    registered_device_id UUID,
    previous_event_date DATE,
    days_since_previous_event INTEGER,
    opening_gross_carrying_amount NUMERIC(18,2),
    opening_accrued_eir_interest NUMERIC(18,2),
    opening_7x7_loan_component NUMERIC(18,2),
    eir_interest_accrual NUMERIC(18,2),
    accrued_interest_available NUMERIC(18,2),
    accounting_eir_interest_received NUMERIC(18,2),
    accounting_7x7_principal_received NUMERIC(18,2),
    closing_accrued_eir_interest NUMERIC(18,2),
    closing_7x7_loan_component NUMERIC(18,2),
    closing_gross_carrying_amount NUMERIC(18,2),
    event_preview_ready BOOLEAN,
    preview_status TEXT
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    readiness RECORD;
    source_row RECORD;
    previous_date_value DATE;
    opening_gross NUMERIC(18,2);
    opening_accrued NUMERIC(18,2);
    opening_loan NUMERIC(18,2);
    accrual NUMERIC(18,2);
    available NUMERIC(18,2);
    interest_received NUMERIC(18,2);
    principal_received NUMERIC(18,2);
    closing_accrued NUMERIC(18,2);
    closing_loan NUMERIC(18,2);
    closing_gross NUMERIC(18,2);
    sequence_value INTEGER := 0;
    ready_value BOOLEAN;
    status_value TEXT;
BEGIN
    SELECT source_readiness.*
    INTO readiness
    FROM accounting.seven_by_seven_source_event_accounting_readiness source_readiness
    WHERE source_readiness.loan_id = p_loan_id;

    IF NOT FOUND OR NOT readiness.source_event_structure_ready THEN
        RETURN;
    END IF;

    previous_date_value := readiness.date_released;
    opening_gross := readiness.authoritative_initial_gross_carrying_amount;
    opening_accrued := 0.00;
    opening_loan := readiness.authoritative_initial_gross_carrying_amount;

    FOR source_row IN
        SELECT inventory.*
        FROM accounting.seven_by_seven_collection_source_inventory inventory
        WHERE inventory.loan_id = p_loan_id
          AND inventory.is_active_positive_cash_event
        -- Duplicate same-day events are rejected above, so transaction_id never
        -- acts as a financial intraday-order convention on a ready loan.
        ORDER BY inventory.collection_date, inventory.transaction_id
    LOOP
        sequence_value := sequence_value + 1;
        accrual := round(
            opening_gross
            * (
                power(
                    1::numeric + readiness.authoritative_daily_eir,
                    (source_row.collection_date - previous_date_value)::numeric
                ) - 1::numeric
            ),
            2
        )::numeric(18,2);
        available := (opening_accrued + accrual)::numeric(18,2);
        interest_received := least(source_row.amount, available)::numeric(18,2);
        principal_received := (source_row.amount - interest_received)::numeric(18,2);
        closing_accrued := (available - interest_received)::numeric(18,2);
        closing_loan := (opening_loan - principal_received)::numeric(18,2);
        closing_gross := (closing_loan + closing_accrued)::numeric(18,2);

        ready_value := (
            principal_received <= opening_loan
            AND source_row.amount <= opening_gross + accrual
            AND closing_loan >= 0
            AND closing_accrued >= 0
            AND closing_gross >= 0
            AND closing_gross = closing_loan + closing_accrued
        );
        status_value := CASE
            WHEN principal_received > opening_loan
                THEN 'cash_exceeds_7x7_loan_component'
            WHEN source_row.amount > opening_gross + accrual
                THEN 'cash_exceeds_opening_gross_plus_eir_accrual'
            WHEN closing_loan < 0 OR closing_accrued < 0 OR closing_gross < 0
                THEN 'negative_carrying_component_blocked'
            WHEN closing_gross <> closing_loan + closing_accrued
                THEN 'closing_component_reconciliation_failed'
            ELSE 'event_eir_preview_ready'
        END;

        loan_id := readiness.loan_id;
        loan_number := readiness.loan_number;
        anchor_id := readiness.anchor_id;
        anchor_review_token := readiness.anchor_review_token;
        authoritative_daily_eir := readiness.authoritative_daily_eir;
        authoritative_initial_gross_carrying_amount :=
            readiness.authoritative_initial_gross_carrying_amount;
        transaction_id := source_row.transaction_id;
        source_event_key := source_row.source_event_key;
        source_event_sequence := sequence_value;
        collector_user_id := source_row.collector_user_id;
        collection_date := source_row.collection_date;
        collection_day := source_row.collection_day;
        entry_type := source_row.entry_type;
        source_cash_amount := source_row.amount;
        accepted_at := source_row.accepted_at;
        device_sequence := source_row.device_sequence;
        registered_device_id := source_row.registered_device_id;
        previous_event_date := previous_date_value;
        days_since_previous_event := source_row.collection_date - previous_date_value;
        opening_gross_carrying_amount := opening_gross;
        opening_accrued_eir_interest := opening_accrued;
        opening_7x7_loan_component := opening_loan;
        eir_interest_accrual := accrual;
        accrued_interest_available := available;
        accounting_eir_interest_received := interest_received;
        accounting_7x7_principal_received := principal_received;
        closing_accrued_eir_interest := closing_accrued;
        closing_7x7_loan_component := closing_loan;
        closing_gross_carrying_amount := closing_gross;
        event_preview_ready := ready_value;
        preview_status := status_value;
        RETURN NEXT;

        IF NOT ready_value THEN
            RETURN;
        END IF;

        previous_date_value := source_row.collection_date;
        opening_gross := closing_gross;
        opening_accrued := closing_accrued;
        opening_loan := closing_loan;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.preview_seven_by_seven_operational_allocation(
    p_loan_id UUID
)
RETURNS TABLE (
    loan_id UUID,
    transaction_id UUID,
    source_event_sequence INTEGER,
    collection_date DATE,
    source_cash_amount NUMERIC(18,2),
    fixed_operational_daily_interest NUMERIC(18,2),
    operational_gap_days INTEGER,
    opening_operational_remaining_principal NUMERIC(18,2),
    opening_operational_interest_arrears NUMERIC(18,2),
    operational_interest_due NUMERIC(18,2),
    operational_interest_paid NUMERIC(18,2),
    operational_principal_paid NUMERIC(18,2),
    operational_unallocated_cash NUMERIC(18,2),
    closing_operational_remaining_principal NUMERIC(18,2),
    closing_operational_interest_arrears NUMERIC(18,2),
    operational_event_applied BOOLEAN,
    operational_preview_status TEXT
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    readiness RECORD;
    source_row RECORD;
    previous_date_value DATE;
    fixed_interest NUMERIC(18,2);
    remaining_principal NUMERIC(18,2);
    interest_arrears NUMERIC(18,2) := 0.00;
    gap_days INTEGER;
    interest_due NUMERIC(18,2);
    interest_paid NUMERIC(18,2);
    principal_paid NUMERIC(18,2);
    unallocated NUMERIC(18,2);
    sequence_value INTEGER := 0;
    allocator_complete BOOLEAN := false;
BEGIN
    SELECT source_readiness.*
    INTO readiness
    FROM accounting.seven_by_seven_source_event_accounting_readiness source_readiness
    WHERE source_readiness.loan_id = p_loan_id;

    IF NOT FOUND OR NOT readiness.source_event_structure_ready THEN
        RETURN;
    END IF;

    SELECT round(
        ceil(inventory.contractual_principal / 1000.0)
        * inventory.daily_interest_per_1000,
        2
    )::numeric(18,2)
    INTO fixed_interest
    FROM accounting.seven_by_seven_collection_source_inventory inventory
    WHERE inventory.loan_id = p_loan_id
    LIMIT 1;

    IF fixed_interest IS NULL THEN
        SELECT round(
            ceil(loan.principal / 1000.0) * loan_type.daily_interest_per_1000,
            2
        )::numeric(18,2)
        INTO fixed_interest
        FROM lending.loans loan
        JOIN lending.loan_types loan_type ON loan_type.id = loan.loan_type_id
        WHERE loan.id = p_loan_id
          AND loan_type.calculation_mode = 'seven_by_seven';
    END IF;

    IF fixed_interest IS NULL OR fixed_interest <= 0 THEN
        RETURN;
    END IF;

    remaining_principal := readiness.principal;
    -- Desktop allocate_x7_payments starts previous_date at payment_start - 1.
    -- For the anchored greenfield loan the protected payment_start comparison
    -- is the loan release date. Same-day release cash is blocked above.
    previous_date_value := readiness.date_released - 1;

    FOR source_row IN
        SELECT inventory.*
        FROM accounting.seven_by_seven_collection_source_inventory inventory
        WHERE inventory.loan_id = p_loan_id
          AND inventory.is_active_positive_cash_event
        ORDER BY inventory.collection_date, inventory.transaction_id
    LOOP
        sequence_value := sequence_value + 1;

        loan_id := readiness.loan_id;
        transaction_id := source_row.transaction_id;
        source_event_sequence := sequence_value;
        collection_date := source_row.collection_date;
        source_cash_amount := source_row.amount;
        fixed_operational_daily_interest := fixed_interest;
        opening_operational_remaining_principal := remaining_principal;
        opening_operational_interest_arrears := interest_arrears;

        IF allocator_complete THEN
            operational_gap_days := 0;
            operational_interest_due := interest_arrears;
            operational_interest_paid := 0.00;
            operational_principal_paid := 0.00;
            operational_unallocated_cash := source_row.amount;
            closing_operational_remaining_principal := remaining_principal;
            closing_operational_interest_arrears := interest_arrears;
            operational_event_applied := false;
            operational_preview_status := 'desktop_allocator_would_stop_before_event';
            RETURN NEXT;
            CONTINUE;
        END IF;

        gap_days := greatest(1, source_row.collection_date - previous_date_value);
        interest_due := (fixed_interest * gap_days + interest_arrears)::numeric(18,2);
        interest_paid := least(source_row.amount, interest_due)::numeric(18,2);
        principal_paid := least(
            remaining_principal,
            greatest(0::numeric, source_row.amount - interest_paid)
        )::numeric(18,2);
        unallocated := greatest(
            0::numeric,
            source_row.amount - interest_paid - principal_paid
        )::numeric(18,2);

        remaining_principal := greatest(0::numeric, remaining_principal - principal_paid)::numeric(18,2);
        interest_arrears := greatest(0::numeric, interest_due - interest_paid)::numeric(18,2);

        operational_gap_days := gap_days;
        operational_interest_due := interest_due;
        operational_interest_paid := interest_paid;
        operational_principal_paid := principal_paid;
        operational_unallocated_cash := unallocated;
        closing_operational_remaining_principal := remaining_principal;
        closing_operational_interest_arrears := interest_arrears;
        operational_event_applied := true;
        operational_preview_status := CASE
            WHEN unallocated > 0 THEN 'desktop_allocator_unallocated_overpayment'
            ELSE 'desktop_operational_allocation_reproduced'
        END;
        RETURN NEXT;

        previous_date_value := source_row.collection_date;
        IF remaining_principal <= 0.004 AND interest_arrears <= 0.004 THEN
            remaining_principal := 0.00;
            interest_arrears := 0.00;
            allocator_complete := true;
        END IF;
    END LOOP;
END;
$$;

CREATE OR REPLACE VIEW accounting.seven_by_seven_source_event_accounting_preview AS
SELECT
    preview.*,
    period.id AS open_fiscal_period_id,
    coalesce(period_count.open_fiscal_period_count, 0)::bigint AS open_fiscal_period_count,
    (
        preview.event_preview_ready
        AND preview.closing_gross_carrying_amount
            = preview.closing_accrued_eir_interest + preview.closing_7x7_loan_component
    ) AS accounting_measurement_preview_ready,
    (
        preview.event_preview_ready
        AND preview.closing_gross_carrying_amount
            = preview.closing_accrued_eir_interest + preview.closing_7x7_loan_component
        AND coalesce(period_count.open_fiscal_period_count, 0) = 1
        AND period.id IS NOT NULL
    ) AS journal_coordinate_preview_ready,
    encode(
        sha256(
            convert_to(
                concat_ws(
                    '|',
                    'seven_by_seven_source_event_accounting_preview_v1',
                    preview.loan_id::text,
                    preview.anchor_id::text,
                    preview.anchor_review_token,
                    preview.authoritative_daily_eir::text,
                    preview.authoritative_initial_gross_carrying_amount::text,
                    preview.transaction_id::text,
                    preview.source_event_key,
                    preview.source_event_sequence::text,
                    preview.collector_user_id::text,
                    preview.collection_date::text,
                    preview.collection_day::text,
                    preview.entry_type,
                    preview.source_cash_amount::text,
                    preview.accepted_at::text,
                    preview.device_sequence::text,
                    coalesce(preview.registered_device_id::text, ''),
                    preview.previous_event_date::text,
                    preview.days_since_previous_event::text,
                    preview.opening_gross_carrying_amount::text,
                    preview.opening_accrued_eir_interest::text,
                    preview.opening_7x7_loan_component::text,
                    preview.eir_interest_accrual::text,
                    preview.accounting_eir_interest_received::text,
                    preview.accounting_7x7_principal_received::text,
                    preview.closing_accrued_eir_interest::text,
                    preview.closing_7x7_loan_component::text,
                    preview.closing_gross_carrying_amount::text,
                    coalesce(period.id::text, '')
                ),
                'UTF8'
            )
        ),
        'hex'
    ) AS source_event_review_token,
    false AS operational_allocation_substituted_for_accounting,
    false AS authoritative_current_carrying_amount_ready,
    false AS journal_draft_enabled,
    false AS journal_lines_enabled,
    false AS automatic_source_posting,
    CASE
        WHEN NOT preview.event_preview_ready THEN preview.preview_status
        WHEN preview.closing_gross_carrying_amount <>
             preview.closing_accrued_eir_interest + preview.closing_7x7_loan_component
            THEN 'closing_component_reconciliation_failed'
        WHEN coalesce(period_count.open_fiscal_period_count, 0) = 0
            THEN 'measurement_preview_ready_open_fiscal_period_required_for_draft'
        WHEN coalesce(period_count.open_fiscal_period_count, 0) > 1
            THEN 'overlapping_open_fiscal_periods_blocked'
        ELSE 'source_event_preview_and_journal_coordinates_ready'
    END AS source_event_preview_status
FROM accounting.seven_by_seven_source_event_accounting_readiness readiness
CROSS JOIN LATERAL accounting.preview_seven_by_seven_source_event_accounting(
    readiness.loan_id
) preview
LEFT JOIN LATERAL (
    SELECT count(*)::bigint AS open_fiscal_period_count
    FROM accounting.fiscal_periods fiscal_period
    WHERE preview.collection_date BETWEEN fiscal_period.start_date AND fiscal_period.end_date
      AND fiscal_period.status = 'open'
) period_count ON true
LEFT JOIN LATERAL (
    SELECT fiscal_period.id
    FROM accounting.fiscal_periods fiscal_period
    WHERE preview.collection_date BETWEEN fiscal_period.start_date AND fiscal_period.end_date
      AND fiscal_period.status = 'open'
    ORDER BY fiscal_period.start_date, fiscal_period.id
    LIMIT 1
) period ON true;

CREATE OR REPLACE VIEW accounting.seven_by_seven_operational_allocation_parity_preview AS
SELECT
    accounting_preview.loan_id,
    accounting_preview.transaction_id,
    accounting_preview.source_event_key,
    accounting_preview.source_event_sequence,
    accounting_preview.collection_date,
    accounting_preview.source_cash_amount,
    accounting_preview.authoritative_daily_eir,
    accounting_preview.accounting_eir_interest_received,
    accounting_preview.accounting_7x7_principal_received,
    operational.fixed_operational_daily_interest,
    operational.operational_gap_days,
    operational.opening_operational_remaining_principal,
    operational.opening_operational_interest_arrears,
    operational.operational_interest_due,
    operational.operational_interest_paid,
    operational.operational_principal_paid,
    operational.operational_unallocated_cash,
    operational.closing_operational_remaining_principal,
    operational.closing_operational_interest_arrears,
    operational.operational_event_applied,
    operational.operational_preview_status,
    (
        operational.operational_interest_paid
        - accounting_preview.accounting_eir_interest_received
    )::numeric(18,2) AS operational_minus_accounting_interest_difference,
    (
        operational.operational_principal_paid
        - accounting_preview.accounting_7x7_principal_received
    )::numeric(18,2) AS operational_minus_accounting_principal_difference,
    (
        operational.operational_event_applied
        AND operational.operational_interest_paid
            = accounting_preview.accounting_eir_interest_received
        AND operational.operational_principal_paid
            = accounting_preview.accounting_7x7_principal_received
        AND operational.operational_unallocated_cash = 0
    ) AS operational_allocation_matches_accounting_eir,
    false AS operational_allocation_substituted_for_accounting,
    false AS journal_lines_enabled,
    false AS automatic_source_posting
FROM accounting.seven_by_seven_source_event_accounting_preview accounting_preview
JOIN LATERAL accounting.preview_seven_by_seven_operational_allocation(
    accounting_preview.loan_id
) operational
  ON operational.transaction_id = accounting_preview.transaction_id;

CREATE OR REPLACE VIEW accounting.seven_by_seven_source_event_journal_coordinate_preview AS
WITH account_map AS (
    SELECT
        (
            SELECT account.id
            FROM accounting.accounts account
            WHERE account.system_key = 'accrued_interest_receivable'
              AND account.is_active AND account.is_posting
            ORDER BY account.id
            LIMIT 1
        ) AS accrued_interest_receivable_account_id,
        (
            SELECT count(*)
            FROM accounting.accounts account
            WHERE account.system_key = 'accrued_interest_receivable'
              AND account.is_active AND account.is_posting
        )::bigint AS accrued_interest_receivable_account_count,
        (
            SELECT account.id
            FROM accounting.accounts account
            WHERE account.system_key = 'interest_income_7x7'
              AND account.is_active AND account.is_posting
            ORDER BY account.id
            LIMIT 1
        ) AS interest_income_7x7_account_id,
        (
            SELECT count(*)
            FROM accounting.accounts account
            WHERE account.system_key = 'interest_income_7x7'
              AND account.is_active AND account.is_posting
        )::bigint AS interest_income_7x7_account_count,
        (
            SELECT account.id
            FROM accounting.accounts account
            WHERE account.system_key = 'cash_collector_custody'
              AND account.is_active AND account.is_posting
            ORDER BY account.id
            LIMIT 1
        ) AS cash_collector_custody_account_id,
        (
            SELECT count(*)
            FROM accounting.accounts account
            WHERE account.system_key = 'cash_collector_custody'
              AND account.is_active AND account.is_posting
        )::bigint AS cash_collector_custody_account_count,
        (
            SELECT account.id
            FROM accounting.accounts account
            WHERE account.system_key = 'loans_receivable_7x7'
              AND account.is_active AND account.is_posting
            ORDER BY account.id
            LIMIT 1
        ) AS loans_receivable_7x7_account_id,
        (
            SELECT count(*)
            FROM accounting.accounts account
            WHERE account.system_key = 'loans_receivable_7x7'
              AND account.is_active AND account.is_posting
        )::bigint AS loans_receivable_7x7_account_count
),
line_source AS (
    SELECT preview.*, account_map.*
    FROM accounting.seven_by_seven_source_event_accounting_preview preview
    CROSS JOIN account_map
    WHERE preview.accounting_measurement_preview_ready
)
SELECT
    line_source.loan_id,
    line_source.transaction_id,
    line_source.source_event_key,
    line_source.source_event_review_token,
    line_source.collection_date AS posting_date,
    line_source.open_fiscal_period_id,
    line.line_number,
    line.journal_component,
    line.account_id,
    account.code AS account_code,
    account.system_key AS account_system_key,
    account.name AS account_name,
    line.debit,
    line.credit,
    (
        line_source.journal_coordinate_preview_ready
        AND line_source.accrued_interest_receivable_account_count = 1
        AND line_source.interest_income_7x7_account_count = 1
        AND line_source.cash_collector_custody_account_count = 1
        AND line_source.loans_receivable_7x7_account_count = 1
        AND line.account_id IS NOT NULL
    ) AS coordinate_preview_ready,
    false AS journal_lines_enabled,
    false AS automatic_source_posting
FROM line_source
CROSS JOIN LATERAL (
    SELECT *
    FROM (
        VALUES
            (
                10,
                'eir_accrual_debit',
                line_source.accrued_interest_receivable_account_id,
                line_source.eir_interest_accrual,
                0.00::numeric(18,2)
            ),
            (
                20,
                'eir_accrual_credit',
                line_source.interest_income_7x7_account_id,
                0.00::numeric(18,2),
                line_source.eir_interest_accrual
            ),
            (
                30,
                'collection_cash_debit',
                line_source.cash_collector_custody_account_id,
                line_source.source_cash_amount,
                0.00::numeric(18,2)
            ),
            (
                40,
                'collection_eir_interest_credit',
                line_source.accrued_interest_receivable_account_id,
                0.00::numeric(18,2),
                line_source.accounting_eir_interest_received
            ),
            (
                50,
                'collection_7x7_principal_credit',
                line_source.loans_receivable_7x7_account_id,
                0.00::numeric(18,2),
                line_source.accounting_7x7_principal_received
            )
    ) AS candidate(line_number, journal_component, account_id, debit, credit)
    WHERE candidate.debit > 0 OR candidate.credit > 0
) line
LEFT JOIN accounting.accounts account ON account.id = line.account_id;

CREATE OR REPLACE VIEW accounting.seven_by_seven_source_event_accounting_summary AS
WITH preview_summary AS (
    SELECT
        readiness.loan_id,
        count(preview.transaction_id)::bigint AS preview_event_count,
        count(preview.transaction_id) FILTER (
            WHERE preview.accounting_measurement_preview_ready
        )::bigint AS measurement_ready_event_count,
        count(preview.transaction_id) FILTER (
            WHERE preview.journal_coordinate_preview_ready
        )::bigint AS coordinate_ready_event_count,
        count(preview.transaction_id) FILTER (
            WHERE NOT preview.accounting_measurement_preview_ready
        )::bigint AS blocked_preview_event_count,
        count(parity.transaction_id) FILTER (
            WHERE parity.operational_event_applied
              AND NOT parity.operational_allocation_matches_accounting_eir
        )::bigint AS operational_accounting_allocation_difference_event_count
    FROM accounting.seven_by_seven_source_event_accounting_readiness readiness
    LEFT JOIN accounting.seven_by_seven_source_event_accounting_preview preview
      ON preview.loan_id = readiness.loan_id
    LEFT JOIN accounting.seven_by_seven_operational_allocation_parity_preview parity
      ON parity.transaction_id = preview.transaction_id
    GROUP BY readiness.loan_id
),
last_preview AS (
    SELECT DISTINCT ON (preview.loan_id)
        preview.loan_id,
        preview.transaction_id AS last_transaction_id,
        preview.collection_date AS last_collection_date,
        preview.closing_gross_carrying_amount AS preview_current_gross_carrying_amount,
        preview.closing_accrued_eir_interest AS preview_current_accrued_eir_interest,
        preview.closing_7x7_loan_component AS preview_current_7x7_loan_component,
        preview.accounting_measurement_preview_ready AS last_event_measurement_preview_ready,
        preview.source_event_review_token AS last_source_event_review_token
    FROM accounting.seven_by_seven_source_event_accounting_preview preview
    ORDER BY preview.loan_id, preview.source_event_sequence DESC
)
SELECT
    readiness.loan_id,
    readiness.loan_number,
    readiness.anchor_id,
    readiness.authoritative_daily_eir,
    readiness.authoritative_initial_gross_carrying_amount,
    readiness.source_event_structure_ready,
    readiness.source_event_readiness_status,
    readiness.active_positive_cash_event_count,
    readiness.duplicate_active_cash_date_count,
    readiness.same_day_or_pre_anchor_cash_event_count,
    readiness.post_maturity_cash_event_count,
    readiness.nonpositive_financial_source_event_count,
    readiness.unsupported_positive_pass_count,
    readiness.voided_original_cash_event_count,
    coalesce(summary.preview_event_count, 0)::bigint AS preview_event_count,
    coalesce(summary.measurement_ready_event_count, 0)::bigint AS measurement_ready_event_count,
    coalesce(summary.coordinate_ready_event_count, 0)::bigint AS coordinate_ready_event_count,
    coalesce(summary.operational_accounting_allocation_difference_event_count, 0)::bigint
        AS operational_accounting_allocation_difference_event_count,
    coalesce(summary.blocked_preview_event_count, 0)::bigint AS blocked_preview_event_count,
    last_preview.last_transaction_id,
    last_preview.last_collection_date,
    CASE
        WHEN readiness.source_event_structure_ready
         AND coalesce(summary.preview_event_count, 0) = 0
            THEN readiness.authoritative_initial_gross_carrying_amount
        WHEN readiness.source_event_structure_ready
         AND coalesce(summary.blocked_preview_event_count, 0) = 0
            THEN last_preview.preview_current_gross_carrying_amount
        ELSE NULL::numeric(18,2)
    END AS preview_current_gross_carrying_amount,
    CASE
        WHEN readiness.source_event_structure_ready
         AND coalesce(summary.preview_event_count, 0) = 0
            THEN 0.00::numeric(18,2)
        WHEN readiness.source_event_structure_ready
         AND coalesce(summary.blocked_preview_event_count, 0) = 0
            THEN last_preview.preview_current_accrued_eir_interest
        ELSE NULL::numeric(18,2)
    END AS preview_current_accrued_eir_interest,
    CASE
        WHEN readiness.source_event_structure_ready
         AND coalesce(summary.preview_event_count, 0) = 0
            THEN readiness.authoritative_initial_gross_carrying_amount
        WHEN readiness.source_event_structure_ready
         AND coalesce(summary.blocked_preview_event_count, 0) = 0
            THEN last_preview.preview_current_7x7_loan_component
        ELSE NULL::numeric(18,2)
    END AS preview_current_7x7_loan_component,
    last_preview.last_source_event_review_token,
    NULL::numeric(18,2) AS authoritative_current_gross_carrying_amount,
    false AS authoritative_current_carrying_amount_ready,
    false AS journal_draft_enabled,
    false AS journal_lines_enabled,
    false AS automatic_source_posting,
    CASE
        WHEN NOT readiness.source_event_structure_ready
            THEN readiness.source_event_readiness_status
        WHEN coalesce(summary.blocked_preview_event_count, 0) > 0
            THEN 'source_event_eir_rollforward_blocked'
        WHEN coalesce(summary.preview_event_count, 0) < readiness.active_positive_cash_event_count
            THEN 'source_event_preview_count_mismatch'
        WHEN coalesce(summary.preview_event_count, 0) = 0
            THEN 'anchor_ready_no_cash_events'
        ELSE 'source_event_eir_preview_ready_for_protected_draft_design'
    END AS accounting_preview_summary_status
FROM accounting.seven_by_seven_source_event_accounting_readiness readiness
LEFT JOIN preview_summary summary ON summary.loan_id = readiness.loan_id
LEFT JOIN last_preview ON last_preview.loan_id = readiness.loan_id;

COMMENT ON VIEW accounting.seven_by_seven_source_event_accounting_preview IS
    'Read-only 7x7 source-event EIR/carrying preview. Exact collection transaction UUIDs define source identity; accounting allocation uses the immutable 0063 original EIR and never substitutes the Desktop operational allocator. Multiple active positive events on one date fail closed. No authoritative current carrying, journal draft/posting or automatic source posting is enabled.';

COMMENT ON VIEW accounting.seven_by_seven_operational_allocation_parity_preview IS
    'Read-only regression parity against the protected Desktop 7x7 allocator: fixed original-principal daily interest, payment_start minus one day initial gap, interest-arrears first, then principal. Differences from accounting EIR allocation are exposed, not substituted.';

COMMENT ON VIEW accounting.seven_by_seven_source_event_journal_coordinate_preview IS
    'Read-only 7x7 journal-coordinate preview: EIR accrual Dr Accrued Interest Receivable / Cr Interest Income - 7x7; cash collection Dr Cash - Collector Custody / Cr Accrued Interest Receivable and Loans Receivable - 7x7 using accounting EIR allocation. journal_lines_enabled and automatic_source_posting remain false.';

COMMIT;