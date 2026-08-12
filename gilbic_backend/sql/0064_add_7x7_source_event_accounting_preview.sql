BEGIN;

-- Master Issue #296: first protected slice of the remaining 7x7 accounting
-- lifecycle. This migration is read-only accounting evidence/preview only.
-- It consumes the immutable 0063 original-EIR / initial-carrying anchor and
-- exact collection transaction UUIDs, proves deterministic event identity and
-- rolls accounting EIR/carrying components forward without creating journals.
--
-- Important policy boundary:
-- * the operational fixed PHP 7-per-PHP 1,000 allocation is comparison evidence
--   only; source interest_paid/principal_paid never drive accounting allocation;
-- * Desktop 7x7 has one effective payment cell per loan/calendar date. Multiple
--   active positive PAYMENT/ADV rows on one date therefore fail closed rather
--   than inventing intraday chronology;
-- * PASS/unable-to-pay creates no accounting cash event;
-- * operational REVERSAL rows are not normal posting events. A later protected
--   accounting reversal must reverse exact protected journal history;
-- * authoritative current carrying, journal drafts, posting and automatic
--   source posting all remain disabled in this slice.

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
    transaction.loan_id,
    loan.loan_number,
    loan.status AS loan_status,
    loan.principal AS contractual_principal,
    loan.date_released,
    loan.due_date,
    loan_type.code AS loan_type_code,
    loan_type.name AS loan_type_name,
    transaction.collection_date,
    transaction.collection_day,
    transaction.entry_type,
    transaction.amount,
    transaction.interest_paid AS operational_interest_paid,
    transaction.principal_paid AS operational_principal_paid,
    transaction.source,
    transaction.source_id,
    transaction.recorded_at,
    transaction.accepted_at,
    transaction.device_sequence,
    transaction.registered_device_id,
    transaction.is_voided,
    transaction.voided_at,
    transaction.reverses_transaction_id,
    transaction.reversal_transaction_id,
    (
        NOT transaction.is_voided
        AND transaction.entry_type IN ('PAYMENT', 'ADV')
        AND transaction.amount > 0
    ) AS is_active_positive_cash_event,
    (
        NOT transaction.is_voided
        AND transaction.entry_type IN ('PAYMENT', 'ADV')
        AND transaction.amount <= 0
    ) AS is_nonpositive_financial_source_event,
    (
        transaction.entry_type = 'REVERSAL'
        OR transaction.reverses_transaction_id IS NOT NULL
    ) AS is_operational_reversal,
    CASE
        WHEN NOT transaction.is_voided
         AND transaction.entry_type IN ('PAYMENT', 'ADV')
         AND transaction.amount > 0
            THEN accounting.seven_by_seven_collection_source_event_key(transaction.id)
        ELSE NULL
    END AS source_event_key,
    count(*) FILTER (
        WHERE NOT transaction.is_voided
          AND transaction.entry_type IN ('PAYMENT', 'ADV')
          AND transaction.amount > 0
    ) OVER (
        PARTITION BY transaction.loan_id, transaction.collection_date
    ) AS active_positive_cash_events_on_date
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
            WHERE NOT inventory.is_voided
              AND inventory.amount > 0
              AND inventory.entry_type NOT IN ('PAYMENT', 'ADV', 'REVERSAL')
        )::bigint AS unsupported_positive_source_event_count,
        count(inventory.transaction_id) FILTER (
            WHERE inventory.is_operational_reversal
        )::bigint AS operational_reversal_row_count,
        count(inventory.transaction_id) FILTER (
            WHERE inventory.is_voided
              AND inventory.entry_type IN ('PAYMENT', 'ADV')
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
    coalesce(summary.unsupported_positive_source_event_count, 0)::bigint
        AS unsupported_positive_source_event_count,
    coalesce(summary.operational_reversal_row_count, 0)::bigint
        AS operational_reversal_row_count,
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
        AND coalesce(summary.unsupported_positive_source_event_count, 0) = 0
    ) AS source_event_structure_ready,
    false AS current_carrying_amount_ready,
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
        WHEN coalesce(summary.unsupported_positive_source_event_count, 0) > 0
            THEN 'unsupported_positive_source_event_type'
        ELSE 'source_event_structure_ready_for_eir_preview'
    END AS source_event_readiness_status
FROM accounting.seven_by_seven_eir_initial_carrying_readiness anchor
LEFT JOIN inventory_summary summary ON summary.loan_id = anchor.loan_id;

CREATE OR REPLACE VIEW accounting.seven_by_seven_source_event_accounting_preview AS
WITH RECURSIVE ordered_events AS (
    SELECT
        readiness.loan_id,
        readiness.loan_number,
        readiness.date_released,
        readiness.due_date,
        readiness.anchor_id,
        readiness.anchor_review_token,
        readiness.authoritative_daily_eir,
        readiness.authoritative_initial_gross_carrying_amount,
        inventory.transaction_id,
        inventory.collection_date,
        inventory.entry_type,
        inventory.amount,
        inventory.operational_interest_paid,
        inventory.operational_principal_paid,
        inventory.source,
        inventory.source_id,
        inventory.recorded_at,
        inventory.accepted_at,
        inventory.device_sequence,
        inventory.registered_device_id,
        inventory.source_event_key,
        row_number() OVER (
            PARTITION BY readiness.loan_id
            ORDER BY inventory.collection_date, inventory.transaction_id
        )::integer AS source_event_sequence
    FROM accounting.seven_by_seven_source_event_accounting_readiness readiness
    JOIN accounting.seven_by_seven_collection_source_inventory inventory
      ON inventory.loan_id = readiness.loan_id
     AND inventory.is_active_positive_cash_event
    WHERE readiness.source_event_structure_ready
),
rollforward AS (
    SELECT
        event.*,
        event.date_released AS previous_event_date,
        (event.collection_date - event.date_released)::integer AS days_since_previous_event,
        event.authoritative_initial_gross_carrying_amount::numeric(18,2)
            AS opening_gross_carrying_amount,
        0.00::numeric(18,2) AS opening_accrued_eir_interest,
        event.authoritative_initial_gross_carrying_amount::numeric(18,2)
            AS opening_7x7_loan_component,
        calc.eir_interest_accrual,
        calc.accrued_interest_available,
        calc.accounting_eir_interest_received,
        calc.accounting_7x7_principal_received,
        calc.closing_accrued_eir_interest,
        calc.closing_7x7_loan_component,
        calc.closing_gross_carrying_amount,
        calc.event_preview_ready,
        calc.preview_status
    FROM ordered_events event
    CROSS JOIN LATERAL (
        SELECT round(
            event.authoritative_initial_gross_carrying_amount
            * (
                power(
                    1::numeric + event.authoritative_daily_eir,
                    (event.collection_date - event.date_released)::numeric
                ) - 1::numeric
            ),
            2
        )::numeric(18,2) AS eir_interest_accrual
    ) interest_calc
    CROSS JOIN LATERAL (
        SELECT
            interest_calc.eir_interest_accrual AS accrued_interest_available,
            least(event.amount, interest_calc.eir_interest_accrual)::numeric(18,2)
                AS accounting_eir_interest_received
    ) allocation_base
    CROSS JOIN LATERAL (
        SELECT
            interest_calc.eir_interest_accrual,
            allocation_base.accrued_interest_available,
            allocation_base.accounting_eir_interest_received,
            (event.amount - allocation_base.accounting_eir_interest_received)::numeric(18,2)
                AS accounting_7x7_principal_received,
            (
                allocation_base.accrued_interest_available
                - allocation_base.accounting_eir_interest_received
            )::numeric(18,2) AS closing_accrued_eir_interest,
            (
                event.authoritative_initial_gross_carrying_amount
                - (event.amount - allocation_base.accounting_eir_interest_received)
            )::numeric(18,2) AS closing_7x7_loan_component,
            (
                event.authoritative_initial_gross_carrying_amount
                + interest_calc.eir_interest_accrual
                - event.amount
            )::numeric(18,2) AS closing_gross_carrying_amount,
            (
                event.amount <= event.authoritative_initial_gross_carrying_amount
                    + interest_calc.eir_interest_accrual
                AND (event.amount - allocation_base.accounting_eir_interest_received)
                    <= event.authoritative_initial_gross_carrying_amount
            ) AS event_preview_ready,
            CASE
                WHEN event.amount > event.authoritative_initial_gross_carrying_amount
                    + interest_calc.eir_interest_accrual
                    THEN 'cash_exceeds_opening_gross_plus_eir_accrual'
                WHEN (event.amount - allocation_base.accounting_eir_interest_received)
                    > event.authoritative_initial_gross_carrying_amount
                    THEN 'cash_exceeds_7x7_loan_component'
                ELSE 'event_eir_preview_ready'
            END AS preview_status
    ) calc
    WHERE event.source_event_sequence = 1

    UNION ALL

    SELECT
        event.*,
        prior.collection_date AS previous_event_date,
        (event.collection_date - prior.collection_date)::integer AS days_since_previous_event,
        CASE WHEN prior.event_preview_ready
            THEN prior.closing_gross_carrying_amount ELSE NULL END::numeric(18,2)
            AS opening_gross_carrying_amount,
        CASE WHEN prior.event_preview_ready
            THEN prior.closing_accrued_eir_interest ELSE NULL END::numeric(18,2)
            AS opening_accrued_eir_interest,
        CASE WHEN prior.event_preview_ready
            THEN prior.closing_7x7_loan_component ELSE NULL END::numeric(18,2)
            AS opening_7x7_loan_component,
        calc.eir_interest_accrual,
        calc.accrued_interest_available,
        calc.accounting_eir_interest_received,
        calc.accounting_7x7_principal_received,
        calc.closing_accrued_eir_interest,
        calc.closing_7x7_loan_component,
        calc.closing_gross_carrying_amount,
        calc.event_preview_ready,
        calc.preview_status
    FROM rollforward prior
    JOIN ordered_events event
      ON event.loan_id = prior.loan_id
     AND event.source_event_sequence = prior.source_event_sequence + 1
    CROSS JOIN LATERAL (
        SELECT CASE WHEN prior.event_preview_ready THEN round(
            prior.closing_gross_carrying_amount
            * (
                power(
                    1::numeric + event.authoritative_daily_eir,
                    (event.collection_date - prior.collection_date)::numeric
                ) - 1::numeric
            ),
            2
        )::numeric(18,2) ELSE NULL::numeric(18,2) END AS eir_interest_accrual
    ) interest_calc
    CROSS JOIN LATERAL (
        SELECT
            CASE WHEN prior.event_preview_ready
                THEN prior.closing_accrued_eir_interest + interest_calc.eir_interest_accrual
                ELSE NULL::numeric(18,2)
            END AS accrued_interest_available
    ) available_calc
    CROSS JOIN LATERAL (
        SELECT CASE WHEN prior.event_preview_ready
            THEN least(event.amount, available_calc.accrued_interest_available)
            ELSE NULL::numeric(18,2)
        END AS accounting_eir_interest_received
    ) interest_received_calc
    CROSS JOIN LATERAL (
        SELECT
            interest_calc.eir_interest_accrual,
            available_calc.accrued_interest_available::numeric(18,2),
            interest_received_calc.accounting_eir_interest_received::numeric(18,2),
            CASE WHEN prior.event_preview_ready THEN
                (event.amount - interest_received_calc.accounting_eir_interest_received)::numeric(18,2)
            ELSE NULL::numeric(18,2) END AS accounting_7x7_principal_received,
            CASE WHEN prior.event_preview_ready THEN
                (
                    available_calc.accrued_interest_available
                    - interest_received_calc.accounting_eir_interest_received
                )::numeric(18,2)
            ELSE NULL::numeric(18,2) END AS closing_accrued_eir_interest,
            CASE WHEN prior.event_preview_ready THEN
                (
                    prior.closing_7x7_loan_component
                    - (event.amount - interest_received_calc.accounting_eir_interest_received)
                )::numeric(18,2)
            ELSE NULL::numeric(18,2) END AS closing_7x7_loan_component,
            CASE WHEN prior.event_preview_ready THEN
                (
                    prior.closing_gross_carrying_amount
                    + interest_calc.eir_interest_accrual
                    - event.amount
                )::numeric(18,2)
            ELSE NULL::numeric(18,2) END AS closing_gross_carrying_amount,
            (
                prior.event_preview_ready
                AND event.amount <= prior.closing_gross_carrying_amount
                    + interest_calc.eir_interest_accrual
                AND (event.amount - interest_received_calc.accounting_eir_interest_received)
                    <= prior.closing_7x7_loan_component
            ) AS event_preview_ready,
            CASE
                WHEN NOT prior.event_preview_ready
                    THEN 'prior_source_event_preview_blocked'
                WHEN event.amount > prior.closing_gross_carrying_amount
                    + interest_calc.eir_interest_accrual
                    THEN 'cash_exceeds_opening_gross_plus_eir_accrual'
                WHEN (event.amount - interest_received_calc.accounting_eir_interest_received)
                    > prior.closing_7x7_loan_component
                    THEN 'cash_exceeds_7x7_loan_component'
                ELSE 'event_eir_preview_ready'
            END AS preview_status
    ) calc
)
SELECT
    rollforward.loan_id,
    rollforward.loan_number,
    rollforward.anchor_id,
    rollforward.anchor_review_token,
    rollforward.authoritative_daily_eir,
    rollforward.authoritative_initial_gross_carrying_amount,
    rollforward.transaction_id,
    rollforward.source_event_key,
    rollforward.source_event_sequence,
    rollforward.collection_date,
    rollforward.entry_type,
    rollforward.amount AS source_cash_amount,
    rollforward.source,
    rollforward.source_id,
    rollforward.recorded_at,
    rollforward.accepted_at,
    rollforward.device_sequence,
    rollforward.registered_device_id,
    rollforward.previous_event_date,
    rollforward.days_since_previous_event,
    rollforward.opening_gross_carrying_amount,
    rollforward.opening_accrued_eir_interest,
    rollforward.opening_7x7_loan_component,
    rollforward.eir_interest_accrual,
    rollforward.accrued_interest_available,
    rollforward.accounting_eir_interest_received,
    rollforward.accounting_7x7_principal_received,
    rollforward.closing_accrued_eir_interest,
    rollforward.closing_7x7_loan_component,
    rollforward.closing_gross_carrying_amount,
    rollforward.operational_interest_paid,
    rollforward.operational_principal_paid,
    (rollforward.operational_interest_paid - rollforward.accounting_eir_interest_received)::numeric(18,2)
        AS operational_minus_accounting_interest_difference,
    (rollforward.operational_principal_paid - rollforward.accounting_7x7_principal_received)::numeric(18,2)
        AS operational_minus_accounting_principal_difference,
    (
        rollforward.operational_interest_paid = rollforward.accounting_eir_interest_received
        AND rollforward.operational_principal_paid = rollforward.accounting_7x7_principal_received
    ) AS operational_allocation_matches_accounting_eir,
    (
        rollforward.closing_gross_carrying_amount
        = rollforward.closing_accrued_eir_interest + rollforward.closing_7x7_loan_component
    ) AS closing_components_reconcile,
    period.id AS open_fiscal_period_id,
    coalesce(periods.open_fiscal_period_count, 0)::bigint AS open_fiscal_period_count,
    rollforward.event_preview_ready,
    (
        rollforward.event_preview_ready
        AND rollforward.closing_gross_carrying_amount
            = rollforward.closing_accrued_eir_interest + rollforward.closing_7x7_loan_component
    ) AS accounting_measurement_preview_ready,
    (
        rollforward.event_preview_ready
        AND rollforward.closing_gross_carrying_amount
            = rollforward.closing_accrued_eir_interest + rollforward.closing_7x7_loan_component
        AND coalesce(periods.open_fiscal_period_count, 0) = 1
        AND period.id IS NOT NULL
    ) AS journal_coordinate_preview_ready,
    encode(
        sha256(
            convert_to(
                concat_ws(
                    '|',
                    'seven_by_seven_source_event_accounting_preview_v1',
                    rollforward.loan_id::text,
                    rollforward.anchor_id::text,
                    rollforward.anchor_review_token,
                    rollforward.authoritative_daily_eir::text,
                    rollforward.authoritative_initial_gross_carrying_amount::text,
                    rollforward.transaction_id::text,
                    rollforward.source_event_key,
                    rollforward.source_event_sequence::text,
                    rollforward.collection_date::text,
                    rollforward.entry_type,
                    rollforward.amount::text,
                    rollforward.operational_interest_paid::text,
                    rollforward.operational_principal_paid::text,
                    coalesce(rollforward.source, ''),
                    coalesce(rollforward.source_id, ''),
                    rollforward.previous_event_date::text,
                    rollforward.days_since_previous_event::text,
                    rollforward.opening_gross_carrying_amount::text,
                    rollforward.opening_accrued_eir_interest::text,
                    rollforward.opening_7x7_loan_component::text,
                    rollforward.eir_interest_accrual::text,
                    rollforward.accounting_eir_interest_received::text,
                    rollforward.accounting_7x7_principal_received::text,
                    rollforward.closing_accrued_eir_interest::text,
                    rollforward.closing_7x7_loan_component::text,
                    rollforward.closing_gross_carrying_amount::text,
                    coalesce(period.id::text, '')
                ),
                'UTF8'
            )
        ),
        'hex'
    ) AS source_event_review_token,
    false AS operational_allocation_substituted_for_accounting,
    false AS authoritative_current_carrying_amount_ready,
    false AS journal_lines_enabled,
    false AS automatic_source_posting,
    CASE
        WHEN NOT rollforward.event_preview_ready THEN rollforward.preview_status
        WHEN rollforward.closing_gross_carrying_amount < 0
          OR rollforward.closing_accrued_eir_interest < 0
          OR rollforward.closing_7x7_loan_component < 0
            THEN 'negative_carrying_component_blocked'
        WHEN rollforward.closing_gross_carrying_amount <>
             rollforward.closing_accrued_eir_interest + rollforward.closing_7x7_loan_component
            THEN 'closing_component_reconciliation_failed'
        WHEN coalesce(periods.open_fiscal_period_count, 0) = 0
            THEN 'measurement_preview_ready_open_fiscal_period_required_for_draft'
        WHEN coalesce(periods.open_fiscal_period_count, 0) > 1
            THEN 'overlapping_open_fiscal_periods_blocked'
        ELSE 'source_event_preview_and_journal_coordinates_ready'
    END AS source_event_preview_status
FROM rollforward
LEFT JOIN LATERAL (
    SELECT count(*)::bigint AS open_fiscal_period_count
    FROM accounting.fiscal_periods fiscal_period
    WHERE rollforward.collection_date BETWEEN fiscal_period.start_date AND fiscal_period.end_date
      AND fiscal_period.status = 'open'
) periods ON true
LEFT JOIN LATERAL (
    SELECT fiscal_period.id
    FROM accounting.fiscal_periods fiscal_period
    WHERE rollforward.collection_date BETWEEN fiscal_period.start_date AND fiscal_period.end_date
      AND fiscal_period.status = 'open'
    ORDER BY fiscal_period.start_date, fiscal_period.id
    LIMIT 1
) period ON true;

CREATE OR REPLACE VIEW accounting.seven_by_seven_source_event_journal_coordinate_preview AS
WITH account_map AS (
    SELECT
        max(id) FILTER (
            WHERE system_key = 'accrued_interest_receivable' AND is_active AND is_posting
        ) AS accrued_interest_receivable_account_id,
        max(id) FILTER (
            WHERE system_key = 'interest_income_7x7' AND is_active AND is_posting
        ) AS interest_income_7x7_account_id,
        max(id) FILTER (
            WHERE system_key = 'cash_collector_custody' AND is_active AND is_posting
        ) AS cash_collector_custody_account_id,
        max(id) FILTER (
            WHERE system_key = 'loans_receivable_7x7' AND is_active AND is_posting
        ) AS loans_receivable_7x7_account_id
    FROM accounting.accounts
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
        AND line_source.accrued_interest_receivable_account_id IS NOT NULL
        AND line_source.interest_income_7x7_account_id IS NOT NULL
        AND line_source.cash_collector_custody_account_id IS NOT NULL
        AND line_source.loans_receivable_7x7_account_id IS NOT NULL
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
            WHERE preview.accounting_measurement_preview_ready
              AND NOT preview.operational_allocation_matches_accounting_eir
        )::bigint AS operational_accounting_allocation_difference_event_count,
        count(preview.transaction_id) FILTER (
            WHERE NOT preview.accounting_measurement_preview_ready
        )::bigint AS blocked_preview_event_count
    FROM accounting.seven_by_seven_source_event_accounting_readiness readiness
    LEFT JOIN accounting.seven_by_seven_source_event_accounting_preview preview
      ON preview.loan_id = readiness.loan_id
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
    readiness.unsupported_positive_source_event_count,
    readiness.operational_reversal_row_count,
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
    false AS current_carrying_amount_ready,
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
    'Read-only 7x7 source-event accounting EIR/carrying preview. Exact transaction UUIDs define source identity; accounting allocation uses the immutable 0063 original EIR, never operational interest_paid/principal_paid. Multiple positive events on one date fail closed. No journal draft/posting or authoritative current carrying is enabled.';

COMMENT ON VIEW accounting.seven_by_seven_source_event_journal_coordinate_preview IS
    'Read-only 7x7 journal coordinate preview: EIR accrual Dr Accrued Interest Receivable / Cr Interest Income - 7x7; cash collection Dr Cash - Collector Custody / Cr Accrued Interest Receivable and Loans Receivable - 7x7 using accounting EIR allocation. journal_lines_enabled and automatic_source_posting remain false.';

COMMIT;