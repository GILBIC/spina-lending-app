BEGIN;

-- Harden the protected posting function after disposable PostgreSQL validation
-- proved that PL/pgSQL resolves the local posting_entry RECORD name against a
-- same-named SQL alias ambiguously. Keep the accounting behavior unchanged and
-- make audit-table aliases unambiguous.
CREATE OR REPLACE FUNCTION accounting.post_renewal_boundary_eir_journal_review_set(
    p_renewal_execution_event_id UUID,
    p_actor_user_id UUID,
    p_review_token TEXT,
    p_expected_entry_count INTEGER,
    p_expected_total_debit NUMERIC,
    p_expected_total_credit NUMERIC,
    p_posting_policy_version TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    execution_row lending.loan_renewal_execution_events%ROWTYPE;
    prepared accounting.renewal_boundary_eir_journal_preparations%ROWTYPE;
    existing_post accounting.renewal_boundary_eir_journal_posting_sets%ROWTYPE;
    created_posting_set_id UUID;
    normalized_review_token TEXT := lower(btrim(coalesce(p_review_token, '')));
    expected_debit NUMERIC(18,2) := round(coalesce(p_expected_total_debit, 0), 2);
    expected_credit NUMERIC(18,2) := round(coalesce(p_expected_total_credit, 0), 2);
    actual_entry_count INTEGER;
    draft_entry_count INTEGER;
    posted_entry_count INTEGER;
    audit_entry_count INTEGER;
    invalid_count INTEGER;
    actual_debit NUMERIC(18,2);
    actual_credit NUMERIC(18,2);
    posting_entry RECORD;
    generated_number TEXT;
BEGIN
    IF p_posting_policy_version IS DISTINCT FROM 'renewal_boundary_eir_journal_posting_v1' THEN
        RAISE EXCEPTION 'Unsupported renewal-boundary EIR journal posting policy version.';
    END IF;
    IF normalized_review_token !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR review token is invalid.';
    END IF;
    IF p_expected_entry_count IS NULL OR p_expected_entry_count < 1
       OR p_expected_total_debit IS DISTINCT FROM expected_debit
       OR p_expected_total_credit IS DISTINCT FROM expected_credit
       OR expected_debit <= 0
       OR expected_debit <> expected_credit THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR posting confirmation totals are invalid.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended(
            'renewal-boundary-eir-journal:' || p_renewal_execution_event_id::text,
            0
        )
    );

    LOCK TABLE
        lending.loan_renewal_execution_events,
        accounting.journal_entries,
        accounting.journal_lines,
        accounting.fiscal_periods,
        accounting.accounts,
        accounting.renewal_boundary_eir_journal_preparations,
        accounting.renewal_boundary_eir_journal_preparation_entries,
        accounting.renewal_boundary_eir_journal_posting_sets,
        accounting.renewal_boundary_eir_journal_posting_entries
    IN SHARE MODE;

    SELECT * INTO execution_row
    FROM lending.loan_renewal_execution_events execution
    WHERE execution.id = p_renewal_execution_event_id;
    IF execution_row.id IS NULL OR execution_row.is_voided THEN
        RAISE EXCEPTION 'Active authoritative renewal execution evidence was not found for protected boundary posting.';
    END IF;

    SELECT * INTO prepared
    FROM accounting.renewal_boundary_eir_journal_preparations preparation
    WHERE preparation.renewal_execution_event_id = p_renewal_execution_event_id;
    IF prepared.id IS NULL THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR draft preparation was not found.';
    END IF;
    IF prepared.review_token <> normalized_review_token
       OR prepared.expected_entry_count <> p_expected_entry_count
       OR prepared.total_amount <> expected_debit
       OR prepared.old_loan_id <> execution_row.old_loan_id
       OR prepared.client_id <> execution_row.client_id
       OR prepared.target_date <> execution_row.business_date THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR posting confirmation no longer matches the immutable preparation.';
    END IF;

    SELECT * INTO existing_post
    FROM accounting.renewal_boundary_eir_journal_posting_sets posting
    WHERE posting.preparation_id = prepared.id;

    SELECT
        count(*)::integer,
        count(*) FILTER (WHERE journal.status = 'draft')::integer,
        count(*) FILTER (WHERE journal.status = 'posted')::integer,
        coalesce(sum(totals.total_debit), 0)::numeric(18,2),
        coalesce(sum(totals.total_credit), 0)::numeric(18,2)
    INTO actual_entry_count, draft_entry_count, posted_entry_count, actual_debit, actual_credit
    FROM accounting.renewal_boundary_eir_journal_preparation_entries prepared_entry
    JOIN accounting.journal_entries journal
      ON journal.id = prepared_entry.journal_entry_id
    JOIN LATERAL (
        SELECT
            coalesce(sum(line.debit), 0)::numeric(18,2) AS total_debit,
            coalesce(sum(line.credit), 0)::numeric(18,2) AS total_credit
        FROM accounting.journal_lines line
        WHERE line.journal_entry_id = journal.id
    ) totals ON true
    WHERE prepared_entry.preparation_id = prepared.id;

    IF actual_entry_count <> p_expected_entry_count
       OR actual_debit <> expected_debit
       OR actual_credit <> expected_credit THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR draft count or totals changed before posting.';
    END IF;

    IF existing_post.id IS NOT NULL THEN
        SELECT count(*)::integer INTO audit_entry_count
        FROM accounting.renewal_boundary_eir_journal_posting_entries audit_row
        JOIN accounting.journal_entries journal
          ON journal.id = audit_row.journal_entry_id
        WHERE audit_row.posting_set_id = existing_post.id
          AND journal.status = 'posted'
          AND journal.entry_number = audit_row.entry_number
          AND journal.source_event_key = audit_row.source_event_key;
        IF existing_post.renewal_execution_event_id <> p_renewal_execution_event_id
           OR existing_post.review_token <> normalized_review_token
           OR existing_post.expected_entry_count <> p_expected_entry_count
           OR existing_post.posted_entry_count <> p_expected_entry_count
           OR existing_post.total_debit <> expected_debit
           OR existing_post.total_credit <> expected_credit
           OR posted_entry_count <> p_expected_entry_count
           OR draft_entry_count <> 0
           OR audit_entry_count <> p_expected_entry_count THEN
            RAISE EXCEPTION 'Protected renewal-boundary EIR posting audit does not match the posted review set.';
        END IF;
        RETURN existing_post.id;
    END IF;

    IF posted_entry_count > 0 OR draft_entry_count <> p_expected_entry_count THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR review set contains posted or non-draft history without the complete protected posting audit.';
    END IF;

    SELECT count(*)::integer
    INTO invalid_count
    FROM accounting.renewal_boundary_eir_journal_preparation_entries prepared_entry
    JOIN accounting.journal_entries journal
      ON journal.id = prepared_entry.journal_entry_id
    JOIN accounting.fiscal_periods period
      ON period.id = prepared_entry.fiscal_period_id
    JOIN accounting.accounts debit_account
      ON debit_account.id = prepared_entry.debit_account_id
    JOIN accounting.accounts credit_account
      ON credit_account.id = prepared_entry.credit_account_id
    JOIN LATERAL (
        SELECT
            count(*)::integer AS line_count,
            coalesce(sum(line.debit), 0)::numeric(18,2) AS total_debit,
            coalesce(sum(line.credit), 0)::numeric(18,2) AS total_credit,
            count(*) FILTER (
                WHERE line.account_id = prepared_entry.debit_account_id
                  AND line.debit = prepared_entry.amount
                  AND line.credit = 0
                  AND line.loan_id = prepared.old_loan_id
                  AND line.client_id = prepared.client_id
            )::integer AS exact_debit_count,
            count(*) FILTER (
                WHERE line.account_id = prepared_entry.credit_account_id
                  AND line.credit = prepared_entry.amount
                  AND line.debit = 0
                  AND line.loan_id = prepared.old_loan_id
                  AND line.client_id = prepared.client_id
            )::integer AS exact_credit_count,
            count(*) FILTER (
                WHERE line.loan_id IS DISTINCT FROM prepared.old_loan_id
                   OR line.client_id IS DISTINCT FROM prepared.client_id
            )::integer AS wrong_dimension_count
        FROM accounting.journal_lines line
        WHERE line.journal_entry_id = journal.id
    ) totals ON true
    WHERE prepared_entry.preparation_id = prepared.id
      AND (
          journal.status <> 'draft'
          OR journal.entry_number IS NOT NULL
          OR journal.fiscal_period_id <> prepared_entry.fiscal_period_id
          OR journal.posting_date <> prepared_entry.posting_date
          OR journal.source_type <> 'regular_renewal_eir_accrual'
          OR journal.source_reference <> prepared_entry.source_reference
          OR journal.source_event_key <> prepared_entry.source_event_key
          OR journal.source_reference <>
               p_renewal_execution_event_id::text || ':fiscal_period:' ||
               prepared_entry.fiscal_period_id::text
          OR journal.source_event_key <>
               'renewal_eir_accrual:' || p_renewal_execution_event_id::text ||
               ':fiscal_period:' || prepared_entry.fiscal_period_id::text
          OR period.status <> 'open'
          OR journal.posting_date NOT BETWEEN period.start_date AND period.end_date
          OR journal.posting_date > execution_row.business_date
          OR debit_account.system_key <> 'accrued_interest_receivable'
          OR credit_account.system_key <> 'interest_income_regular'
          OR debit_account.is_active = false
          OR debit_account.is_posting = false
          OR credit_account.is_active = false
          OR credit_account.is_posting = false
          OR totals.line_count <> 2
          OR totals.total_debit <> prepared_entry.amount
          OR totals.total_credit <> prepared_entry.amount
          OR totals.exact_debit_count <> 1
          OR totals.exact_credit_count <> 1
          OR totals.wrong_dimension_count <> 0
      );
    IF invalid_count > 0 THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR draft integrity, identity, period, account, balance, or dimensions changed before posting.';
    END IF;

    PERFORM set_config('accounting.renewal_boundary_eir_post_record_allowed', 'on', true);
    INSERT INTO accounting.renewal_boundary_eir_journal_posting_sets (
        preparation_id,
        renewal_execution_event_id,
        old_loan_id,
        client_id,
        review_token,
        posting_policy_version,
        expected_entry_count,
        posted_entry_count,
        total_debit,
        total_credit,
        posted_by_user_id
    ) VALUES (
        prepared.id,
        p_renewal_execution_event_id,
        prepared.old_loan_id,
        prepared.client_id,
        normalized_review_token,
        p_posting_policy_version,
        p_expected_entry_count,
        p_expected_entry_count,
        expected_debit,
        expected_credit,
        p_actor_user_id
    ) RETURNING id INTO created_posting_set_id;

    PERFORM set_config('accounting.renewal_boundary_eir_journal_post_allowed', 'on', true);

    FOR posting_entry IN
        SELECT
            prepared_entry.sequence_order,
            prepared_entry.journal_entry_id,
            prepared_entry.source_event_key
        FROM accounting.renewal_boundary_eir_journal_preparation_entries prepared_entry
        JOIN accounting.journal_entries journal
          ON journal.id = prepared_entry.journal_entry_id
        WHERE prepared_entry.preparation_id = prepared.id
        ORDER BY prepared_entry.sequence_order
        FOR UPDATE OF journal
    LOOP
        generated_number := accounting.post_journal_entry(
            posting_entry.journal_entry_id,
            p_actor_user_id
        );

        INSERT INTO accounting.journal_events (
            journal_entry_id, event_type, actor_user_id, details
        ) VALUES (
            posting_entry.journal_entry_id,
            'posted',
            p_actor_user_id,
            jsonb_build_object(
                'entry_number', generated_number,
                'protected_renewal_boundary_eir', true,
                'renewal_execution_event_id', p_renewal_execution_event_id,
                'review_token', normalized_review_token,
                'automatic_source_posting', false
            )
        );

        INSERT INTO accounting.renewal_boundary_eir_journal_posting_entries (
            posting_set_id,
            preparation_id,
            sequence_order,
            journal_entry_id,
            entry_number,
            source_event_key
        ) VALUES (
            created_posting_set_id,
            prepared.id,
            posting_entry.sequence_order,
            posting_entry.journal_entry_id,
            generated_number,
            posting_entry.source_event_key
        );
    END LOOP;

    SELECT count(*)::integer INTO audit_entry_count
    FROM accounting.renewal_boundary_eir_journal_posting_entries audit_row
    JOIN accounting.journal_entries journal
      ON journal.id = audit_row.journal_entry_id
    WHERE audit_row.posting_set_id = created_posting_set_id
      AND journal.status = 'posted'
      AND journal.entry_number = audit_row.entry_number
      AND journal.source_event_key = audit_row.source_event_key;

    IF audit_entry_count <> p_expected_entry_count THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR posting audit is incomplete; posting transaction was rolled back.';
    END IF;

    RETURN created_posting_set_id;
END;
$$;

COMMIT;