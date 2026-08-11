BEGIN;

-- Stage 5D.25 bridges the protected pure new-loan release lifecycle to the
-- event-date Regular EIR engine for a greenfield company. It is read-only:
-- no opening-balance workbook, accounting journal, or source event is created.

CREATE OR REPLACE FUNCTION accounting.solve_verified_contract_schedule_daily_eir(
    p_schedule_id UUID,
    p_anchor_date DATE,
    p_initial_carrying NUMERIC
)
RETURNS NUMERIC
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    initial_amount NUMERIC := round(coalesce(p_initial_carrying, 0), 2);
    low_rate NUMERIC := 0;
    high_rate NUMERIC := 0.01;
    mid_rate NUMERIC;
    present_value NUMERIC;
    installment_row RECORD;
    installment_count INTEGER;
    contractual_total NUMERIC;
    invalid_due_count INTEGER;
    registration_count INTEGER;
    expansion INTEGER;
    iteration INTEGER;
BEGIN
    IF p_schedule_id IS NULL OR p_anchor_date IS NULL OR initial_amount <= 0 THEN
        RETURN NULL;
    END IF;

    SELECT count(*)::integer
    INTO registration_count
    FROM lending.loan_contract_schedule_registrations registration
    WHERE registration.schedule_id = p_schedule_id
      AND registration.evidence_basis = 'signed_contract';

    IF registration_count <> 1 THEN
        RETURN NULL;
    END IF;

    SELECT
        count(*)::integer,
        coalesce(sum(installment.contractual_amount), 0),
        count(*) FILTER (WHERE installment.due_date <= p_anchor_date)::integer
    INTO installment_count, contractual_total, invalid_due_count
    FROM lending.loan_contract_installments installment
    WHERE installment.schedule_id = p_schedule_id;

    IF installment_count <= 0
       OR invalid_due_count > 0
       OR contractual_total <= initial_amount THEN
        RETURN NULL;
    END IF;

    -- Find a positive upper bound. Exact verified contract cash flows are
    -- discounted by elapsed calendar days from the protected release anchor.
    FOR expansion IN 1..24 LOOP
        present_value := 0;
        FOR installment_row IN
            SELECT due_date, contractual_amount
            FROM lending.loan_contract_installments
            WHERE schedule_id = p_schedule_id
            ORDER BY due_date, installment_number
        LOOP
            present_value := present_value
                + installment_row.contractual_amount
                  / power(
                        1 + high_rate,
                        installment_row.due_date - p_anchor_date
                    );
        END LOOP;
        EXIT WHEN present_value < initial_amount;
        high_rate := high_rate * 2;
    END LOOP;

    IF present_value >= initial_amount THEN
        RETURN NULL;
    END IF;

    FOR iteration IN 1..160 LOOP
        mid_rate := (low_rate + high_rate) / 2;
        present_value := 0;
        FOR installment_row IN
            SELECT due_date, contractual_amount
            FROM lending.loan_contract_installments
            WHERE schedule_id = p_schedule_id
            ORDER BY due_date, installment_number
        LOOP
            present_value := present_value
                + installment_row.contractual_amount
                  / power(
                        1 + mid_rate,
                        installment_row.due_date - p_anchor_date
                    );
        END LOOP;

        IF present_value > initial_amount THEN
            low_rate := mid_rate;
        ELSE
            high_rate := mid_rate;
        END IF;
    END LOOP;

    RETURN round((low_rate + high_rate) / 2, 12);
END;
$$;

CREATE OR REPLACE VIEW accounting.greenfield_regular_eir_anchor_readiness AS
WITH protected_release AS (
    SELECT
        posting.id AS posting_id,
        posting.preparation_id,
        posting.disbursement_event_id,
        posting.loan_id,
        posting.client_id,
        posting.journal_entry_id,
        posting.source_event_key,
        posting.posting_date,
        posting.debit_account_id,
        posting.credit_account_id,
        posting.amount AS posted_amount,
        posting.entry_number,
        posting.posting_policy_version,
        event.event_kind,
        event.business_date AS release_business_date,
        event.disbursed_at,
        event.cash_disbursed_amount,
        event.settlement_amount,
        event.other_deduction_amount,
        event.funding_account_system_key,
        event.external_reference AS release_external_reference,
        event.principal_snapshot,
        event.date_released_snapshot,
        event.is_voided AS release_is_voided,
        loan.loan_number,
        loan.client_id AS current_loan_client_id,
        client.client_code,
        client.full_name AS client_name,
        journal.status AS journal_status,
        journal.posting_date AS journal_posting_date,
        journal.entry_number AS journal_entry_number,
        journal.source_type AS journal_source_type,
        journal.source_reference AS journal_source_reference,
        journal.source_event_key AS journal_source_event_key,
        debit_account.system_key AS debit_account_system_key,
        credit_account.system_key AS credit_account_system_key,
        cancellation.id AS cancellation_id,
        reversal.id AS reversal_id
    FROM accounting.loan_disbursement_journal_postings posting
    JOIN lending.loan_disbursement_events event
      ON event.id = posting.disbursement_event_id
    JOIN lending.loans loan
      ON loan.id = posting.loan_id
    JOIN lending.clients client
      ON client.id = posting.client_id
    JOIN accounting.journal_entries journal
      ON journal.id = posting.journal_entry_id
    JOIN accounting.accounts debit_account
      ON debit_account.id = posting.debit_account_id
    JOIN accounting.accounts credit_account
      ON credit_account.id = posting.credit_account_id
    LEFT JOIN lending.loan_disbursement_cancellations cancellation
      ON cancellation.posting_id = posting.id
    LEFT JOIN accounting.loan_disbursement_journal_reversals reversal
      ON reversal.posting_id = posting.id
), original_verified_schedule AS (
    SELECT
        schedule.loan_id,
        schedule.id AS schedule_id,
        schedule.schedule_version,
        schedule.status AS schedule_status,
        schedule.payment_frequency,
        schedule.contract_reference,
        schedule.contract_signed_date,
        schedule.effective_from,
        registration.id AS registration_id,
        registration.evidence_basis,
        registration.evidence_reference,
        registration.verified_by_user_id,
        registration.verified_at
    FROM lending.loan_contract_schedules schedule
    JOIN lending.loan_contract_schedule_registrations registration
      ON registration.schedule_id = schedule.id
    WHERE schedule.schedule_version = 1
      AND schedule.supersedes_schedule_id IS NULL
), schedule_rollup AS (
    SELECT
        schedule.id AS schedule_id,
        count(installment.id)::integer AS installment_count,
        min(installment.due_date) AS first_due_date,
        max(installment.due_date) AS last_due_date,
        coalesce(sum(installment.contractual_amount), 0)::numeric(18,2)
            AS contractual_cash_total,
        count(*) FILTER (
            WHERE installment.due_date <= schedule.effective_from
        )::integer AS nonfuture_due_count
    FROM lending.loan_contract_schedules schedule
    LEFT JOIN lending.loan_contract_installments installment
      ON installment.schedule_id = schedule.id
    GROUP BY schedule.id
), journal_line_rollup AS (
    SELECT
        posting.id AS posting_id,
        count(line.id)::integer AS line_count,
        coalesce(sum(line.debit), 0)::numeric(18,2) AS total_debit,
        coalesce(sum(line.credit), 0)::numeric(18,2) AS total_credit,
        count(*) FILTER (
            WHERE line.account_id = posting.debit_account_id
              AND line.debit = posting.amount
              AND line.credit = 0
              AND line.loan_id = posting.loan_id
              AND line.client_id = posting.client_id
        )::integer AS exact_debit_line_count,
        count(*) FILTER (
            WHERE line.account_id = posting.credit_account_id
              AND line.credit = posting.amount
              AND line.debit = 0
              AND line.loan_id = posting.loan_id
              AND line.client_id = posting.client_id
        )::integer AS exact_credit_line_count,
        count(*) FILTER (
            WHERE line.loan_id IS DISTINCT FROM posting.loan_id
               OR line.client_id IS DISTINCT FROM posting.client_id
        )::integer AS wrong_dimension_line_count
    FROM accounting.loan_disbursement_journal_postings posting
    LEFT JOIN accounting.journal_lines line
      ON line.journal_entry_id = posting.journal_entry_id
    GROUP BY posting.id
), collection_boundary AS (
    SELECT
        posting.id AS posting_id,
        count(transaction.id) FILTER (
            WHERE transaction.is_voided = false
              AND transaction.entry_type IN ('payment', 'advance')
              AND transaction.amount > 0
              AND transaction.collection_date < posting.posting_date
        )::integer AS pre_anchor_collection_count,
        count(transaction.id) FILTER (
            WHERE transaction.is_voided = false
              AND transaction.entry_type IN ('payment', 'advance')
              AND transaction.amount > 0
              AND transaction.collection_date = posting.posting_date
        )::integer AS same_day_collection_count
    FROM accounting.loan_disbursement_journal_postings posting
    LEFT JOIN lending.collection_transactions transaction
      ON transaction.loan_id = posting.loan_id
    GROUP BY posting.id
), assembled AS (
    SELECT
        release.*,
        schedule.schedule_id,
        schedule.schedule_version,
        schedule.schedule_status,
        schedule.payment_frequency,
        schedule.contract_reference,
        schedule.contract_signed_date,
        schedule.effective_from AS schedule_effective_from,
        schedule.registration_id,
        schedule.evidence_basis,
        schedule.evidence_reference,
        schedule.verified_by_user_id,
        schedule.verified_at,
        rollup.installment_count,
        rollup.first_due_date,
        rollup.last_due_date,
        rollup.contractual_cash_total,
        rollup.nonfuture_due_count,
        lines.line_count,
        lines.total_debit,
        lines.total_credit,
        lines.exact_debit_line_count,
        lines.exact_credit_line_count,
        lines.wrong_dimension_line_count,
        boundary.pre_anchor_collection_count,
        boundary.same_day_collection_count,
        accounting.solve_verified_contract_schedule_daily_eir(
            schedule.schedule_id,
            release.posting_date,
            release.posted_amount
        ) AS daily_eir
    FROM protected_release release
    LEFT JOIN original_verified_schedule schedule
      ON schedule.loan_id = release.loan_id
    LEFT JOIN schedule_rollup rollup
      ON rollup.schedule_id = schedule.schedule_id
    JOIN journal_line_rollup lines
      ON lines.posting_id = release.posting_id
    JOIN collection_boundary boundary
      ON boundary.posting_id = release.posting_id
)
SELECT
    posting_id,
    disbursement_event_id,
    loan_id,
    loan_number,
    client_id,
    client_code,
    client_name,
    journal_entry_id,
    entry_number,
    source_event_key AS release_source_event_key,
    release_business_date AS anchor_date,
    disbursed_at,
    posted_amount::numeric(18,2) AS initial_gross_carrying_amount,
    posted_amount::numeric(18,2) AS initial_loan_component,
    0::numeric(18,2) AS initial_accrued_interest_component,
    schedule_id,
    schedule_version,
    schedule_status,
    payment_frequency,
    contract_reference,
    contract_signed_date,
    schedule_effective_from,
    registration_id,
    evidence_basis,
    evidence_reference,
    installment_count,
    first_due_date,
    last_due_date AS contractual_due_date,
    contractual_cash_total,
    daily_eir,
    CASE WHEN daily_eir IS NOT NULL
        THEN round(daily_eir * 100, 8)
        ELSE NULL
    END AS daily_eir_percent,
    pre_anchor_collection_count,
    same_day_collection_count,
    CASE
        WHEN cancellation_id IS NOT NULL OR reversal_id IS NOT NULL
            THEN 'protected_release_cancelled'
        WHEN release_is_voided
            THEN 'release_evidence_voided'
        WHEN event_kind <> 'new_loan_release'
            THEN 'unsupported_release_kind'
        WHEN current_loan_client_id IS DISTINCT FROM client_id
            THEN 'loan_client_mismatch'
        WHEN posting_policy_version <> 'new_loan_disbursement_journal_posting_v1'
            THEN 'unsupported_release_posting_policy'
        WHEN journal_status <> 'posted'
            THEN 'protected_release_not_posted'
        WHEN journal_posting_date IS DISTINCT FROM posting_date
          OR journal_entry_number IS DISTINCT FROM entry_number
          OR journal_source_type IS DISTINCT FROM 'loan_disbursement'
          OR journal_source_reference IS DISTINCT FROM disbursement_event_id::text
          OR journal_source_event_key IS DISTINCT FROM source_event_key
            THEN 'protected_release_journal_identity_mismatch'
        WHEN posting_date IS DISTINCT FROM release_business_date
          OR release_business_date IS DISTINCT FROM date_released_snapshot
            THEN 'release_date_mismatch'
        WHEN settlement_amount <> 0 OR other_deduction_amount <> 0
            THEN 'non_pure_release_policy_review'
        WHEN cash_disbursed_amount IS DISTINCT FROM principal_snapshot
          OR posted_amount IS DISTINCT FROM principal_snapshot
            THEN 'initial_carrying_amount_mismatch'
        WHEN debit_account_system_key IS DISTINCT FROM 'loans_receivable_regular'
          OR credit_account_system_key IS DISTINCT FROM funding_account_system_key
            THEN 'protected_release_account_identity_mismatch'
        WHEN line_count <> 2
          OR total_debit IS DISTINCT FROM posted_amount
          OR total_credit IS DISTINCT FROM posted_amount
          OR exact_debit_line_count <> 1
          OR exact_credit_line_count <> 1
          OR wrong_dimension_line_count <> 0
            THEN 'protected_release_journal_lines_mismatch'
        WHEN schedule_id IS NULL OR registration_id IS NULL
            THEN 'verified_signed_contract_schedule_required'
        WHEN evidence_basis IS DISTINCT FROM 'signed_contract'
            THEN 'original_signed_contract_evidence_required'
        WHEN schedule_effective_from IS DISTINCT FROM posting_date
            THEN 'contract_schedule_anchor_date_mismatch'
        WHEN installment_count IS NULL OR installment_count <= 0
            THEN 'contract_installments_required'
        WHEN nonfuture_due_count > 0
            THEN 'contract_schedule_boundary_review'
        WHEN contractual_cash_total IS NULL
          OR contractual_cash_total <= posted_amount
            THEN 'positive_eir_not_supported_by_contract_cash_flows'
        WHEN daily_eir IS NULL OR daily_eir <= 0
            THEN 'verified_contract_eir_not_solved'
        WHEN pre_anchor_collection_count > 0
            THEN 'pre_anchor_collection_review'
        WHEN same_day_collection_count > 0
            THEN 'same_day_collection_ordering_review'
        ELSE 'greenfield_regular_eir_anchor_ready'
    END AS readiness_status,
    CASE
        WHEN posting_id IS NULL THEN NULL
        ELSE 'greenfield_regular_eir_anchor:' || posting_id::text
    END AS anchor_source_key,
    'greenfield_regular_eir_anchor_v1'::text AS anchor_policy_version,
    false AS collection_journal_integration_enabled,
    false AS journal_lines_enabled,
    false AS automatic_source_posting
FROM assembled;

COMMENT ON FUNCTION accounting.solve_verified_contract_schedule_daily_eir(
    UUID, DATE, NUMERIC
) IS
    'Read-only daily EIR solver using immutable verified signed-contract installment cash flows and a protected initial carrying amount. It creates no journal or source row.';
COMMENT ON VIEW accounting.greenfield_regular_eir_anchor_readiness IS
    'Read-only greenfield Regular EIR anchor evidence. Only an uncancelled protected Stage 5D.22 new-loan posting plus the immutable verified original signed-contract schedule can become ready. Same-day release cash remains fail-closed until event ordering is explicitly supported.';

COMMIT;
