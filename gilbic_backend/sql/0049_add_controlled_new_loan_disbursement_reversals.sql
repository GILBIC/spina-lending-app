BEGIN;

INSERT INTO core.permissions (code, description)
VALUES (
    'accounting.loan_disbursement.journal.reverse',
    'Explicitly cancel and reverse one already-posted protected pure new Regular loan disbursement while preserving immutable original history'
)
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code = 'accounting.loan_disbursement.journal.reverse'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS lending.loan_disbursement_cancellations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    disbursement_event_id UUID NOT NULL UNIQUE
        REFERENCES lending.loan_disbursement_events(id) ON DELETE RESTRICT,
    posting_id UUID NOT NULL UNIQUE
        REFERENCES accounting.loan_disbursement_journal_postings(id) ON DELETE RESTRICT,
    original_journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    cancellation_source_key TEXT NOT NULL UNIQUE,
    reversal_posting_date DATE NOT NULL,
    reason TEXT NOT NULL CHECK (length(btrim(reason)) >= 3),
    cancelled_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    cancelled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        cancellation_source_key =
            'loan_disbursement_cancellation:' || disbursement_event_id::text
    )
);

CREATE INDEX IF NOT EXISTS loan_disbursement_cancellations_posting_idx
    ON lending.loan_disbursement_cancellations (posting_id, cancelled_at DESC);

CREATE TABLE IF NOT EXISTS accounting.loan_disbursement_journal_reversals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cancellation_id UUID NOT NULL UNIQUE
        REFERENCES lending.loan_disbursement_cancellations(id) ON DELETE RESTRICT,
    posting_id UUID NOT NULL UNIQUE
        REFERENCES accounting.loan_disbursement_journal_postings(id) ON DELETE RESTRICT,
    disbursement_event_id UUID NOT NULL UNIQUE
        REFERENCES lending.loan_disbursement_events(id) ON DELETE RESTRICT,
    original_journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    reversal_journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    original_entry_number TEXT NOT NULL,
    reversal_entry_number TEXT NOT NULL UNIQUE,
    original_source_event_key TEXT NOT NULL,
    reversal_source_event_key TEXT NOT NULL UNIQUE,
    original_debit_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    original_credit_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    amount NUMERIC(18,2) NOT NULL CHECK (amount > 0),
    reversed_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    reversed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (btrim(original_entry_number) <> ''),
    CHECK (btrim(reversal_entry_number) <> ''),
    CHECK (btrim(original_source_event_key) <> ''),
    CHECK (
        reversal_source_event_key =
            'loan_disbursement_cancellation_reversal:' || posting_id::text
    ),
    CHECK (original_debit_account_id <> original_credit_account_id)
);

CREATE INDEX IF NOT EXISTS loan_disbursement_journal_reversals_event_idx
    ON accounting.loan_disbursement_journal_reversals
       (disbursement_event_id, reversed_at DESC);

CREATE OR REPLACE FUNCTION accounting.guard_loan_disbursement_cancellation_record_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(
            current_setting('accounting.loan_disbursement_reversal_allowed', true),
            ''
       ) = 'on' THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'Protected new-loan disbursement cancellation evidence is immutable and must use the controlled reversal workflow.';
END;
$$;

DROP TRIGGER IF EXISTS lending_loan_disbursement_cancellation_guard
    ON lending.loan_disbursement_cancellations;
CREATE TRIGGER lending_loan_disbursement_cancellation_guard
BEFORE INSERT OR UPDATE OR DELETE
ON lending.loan_disbursement_cancellations
FOR EACH ROW EXECUTE FUNCTION accounting.guard_loan_disbursement_cancellation_record_write();

CREATE OR REPLACE FUNCTION accounting.guard_loan_disbursement_reversal_record_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(
            current_setting('accounting.loan_disbursement_reversal_allowed', true),
            ''
       ) = 'on' THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'Protected new-loan disbursement reversal audit is immutable and must use the controlled reversal workflow.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_loan_disbursement_journal_reversal_guard
    ON accounting.loan_disbursement_journal_reversals;
CREATE TRIGGER accounting_loan_disbursement_journal_reversal_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.loan_disbursement_journal_reversals
FOR EACH ROW EXECUTE FUNCTION accounting.guard_loan_disbursement_reversal_record_write();

CREATE OR REPLACE FUNCTION accounting.guard_protected_loan_disbursement_reversal_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    original_is_protected BOOLEAN := false;
    protected_session BOOLEAN := false;
BEGIN
    protected_session := coalesce(
        current_setting('accounting.loan_disbursement_reversal_allowed', true),
        ''
    ) = 'on';

    IF NEW.reversal_of_entry_id IS NOT NULL THEN
        SELECT EXISTS (
            SELECT 1
            FROM accounting.loan_disbursement_journal_postings posted
            WHERE posted.journal_entry_id = NEW.reversal_of_entry_id
        )
        INTO original_is_protected;
    END IF;

    IF NEW.source_type = 'loan_disbursement_cancellation_reversal' THEN
        IF NOT protected_session OR NEW.reversal_of_entry_id IS NULL THEN
            RAISE EXCEPTION 'Protected new-loan disbursement reversal journals must use the controlled cancellation workflow.';
        END IF;
    ELSIF original_is_protected THEN
        RAISE EXCEPTION 'Posted protected new-loan disbursement journals can only be reversed through the controlled cancellation workflow.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_protected_loan_disbursement_reversal_insert_guard
    ON accounting.journal_entries;
CREATE TRIGGER accounting_protected_loan_disbursement_reversal_insert_guard
BEFORE INSERT ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_protected_loan_disbursement_reversal_insert();

CREATE OR REPLACE FUNCTION accounting.reverse_posted_new_loan_disbursement(
    p_posting_id UUID,
    p_actor_user_id UUID,
    p_reversal_posting_date DATE,
    p_reason TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    posting accounting.loan_disbursement_journal_postings%ROWTYPE;
    prepared accounting.loan_disbursement_journal_draft_preparations%ROWTYPE;
    event_row lending.loan_disbursement_events%ROWTYPE;
    original_journal accounting.journal_entries%ROWTYPE;
    debit_account accounting.accounts%ROWTYPE;
    credit_account accounting.accounts%ROWTYPE;
    existing_cancellation lending.loan_disbursement_cancellations%ROWTYPE;
    existing_reversal accounting.loan_disbursement_journal_reversals%ROWTYPE;
    target_period_id UUID;
    cancellation_id UUID;
    reversal_journal_id UUID;
    generated_number TEXT;
    reversal_source_key TEXT;
    normalized_reason TEXT := btrim(coalesce(p_reason, ''));
    line_count INTEGER;
    total_debit NUMERIC(18,2);
    total_credit NUMERIC(18,2);
    debit_match_count INTEGER;
    credit_match_count INTEGER;
    invalid_line_count INTEGER;
    reversal_line_count INTEGER;
    reversal_debit NUMERIC(18,2);
    reversal_credit NUMERIC(18,2);
    reversal_cash_match INTEGER;
    reversal_loan_match INTEGER;
BEGIN
    IF p_reversal_posting_date IS NULL THEN
        RAISE EXCEPTION 'A controlled new-loan disbursement reversal posting date is required.';
    END IF;
    IF length(normalized_reason) < 3 THEN
        RAISE EXCEPTION 'A controlled new-loan disbursement reversal requires a clear reason.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended(
            'new-loan-disbursement-reversal:' || p_posting_id::text,
            0
        )
    );

    LOCK TABLE
        lending.loan_disbursement_events,
        lending.loan_disbursement_cancellations,
        lending.loans,
        lending.loan_types,
        accounting.fiscal_periods,
        accounting.accounts,
        accounting.journal_entries,
        accounting.journal_lines,
        accounting.loan_disbursement_journal_draft_preparations,
        accounting.loan_disbursement_journal_postings,
        accounting.loan_disbursement_journal_reversals
    IN SHARE MODE;

    SELECT *
    INTO posting
    FROM accounting.loan_disbursement_journal_postings item
    WHERE item.id = p_posting_id;

    IF posting.id IS NULL THEN
        RAISE EXCEPTION 'Protected new-loan disbursement posting audit was not found.';
    END IF;

    SELECT *
    INTO existing_cancellation
    FROM lending.loan_disbursement_cancellations item
    WHERE item.posting_id = p_posting_id;

    IF existing_cancellation.id IS NOT NULL THEN
        SELECT *
        INTO existing_reversal
        FROM accounting.loan_disbursement_journal_reversals item
        WHERE item.cancellation_id = existing_cancellation.id;

        IF existing_cancellation.disbursement_event_id <> posting.disbursement_event_id
           OR existing_cancellation.original_journal_entry_id <> posting.journal_entry_id
           OR existing_cancellation.reversal_posting_date <> p_reversal_posting_date
           OR existing_cancellation.reason <> normalized_reason
           OR existing_cancellation.cancelled_by_user_id <> p_actor_user_id
           OR existing_reversal.id IS NULL
           OR existing_reversal.posting_id <> posting.id
           OR existing_reversal.disbursement_event_id <> posting.disbursement_event_id
           OR existing_reversal.original_journal_entry_id <> posting.journal_entry_id
           OR existing_reversal.original_entry_number <> posting.entry_number
           OR existing_reversal.original_source_event_key <> posting.source_event_key
           OR existing_reversal.original_debit_account_id <> posting.debit_account_id
           OR existing_reversal.original_credit_account_id <> posting.credit_account_id
           OR existing_reversal.amount <> posting.amount THEN
            RAISE EXCEPTION 'Existing protected new-loan disbursement cancellation/reversal audit is inconsistent with this exact retry.';
        END IF;

        SELECT
            count(*)::integer,
            coalesce(sum(line.debit), 0)::numeric(18,2),
            coalesce(sum(line.credit), 0)::numeric(18,2),
            count(*) FILTER (
                WHERE line.account_id = posting.credit_account_id
                  AND line.debit = posting.amount
                  AND line.credit = 0
                  AND line.client_id = posting.client_id
                  AND line.loan_id = posting.loan_id
            )::integer,
            count(*) FILTER (
                WHERE line.account_id = posting.debit_account_id
                  AND line.credit = posting.amount
                  AND line.debit = 0
                  AND line.client_id = posting.client_id
                  AND line.loan_id = posting.loan_id
            )::integer
        INTO
            reversal_line_count,
            reversal_debit,
            reversal_credit,
            reversal_cash_match,
            reversal_loan_match
        FROM accounting.journal_lines line
        JOIN accounting.journal_entries journal
          ON journal.id = line.journal_entry_id
        WHERE line.journal_entry_id = existing_reversal.reversal_journal_entry_id
          AND journal.status = 'posted'
          AND journal.entry_number = existing_reversal.reversal_entry_number
          AND journal.source_event_key = existing_reversal.reversal_source_event_key
          AND journal.reversal_of_entry_id = posting.journal_entry_id;

        IF reversal_line_count <> 2
           OR reversal_debit <> posting.amount
           OR reversal_credit <> posting.amount
           OR reversal_cash_match <> 1
           OR reversal_loan_match <> 1 THEN
            RAISE EXCEPTION 'Existing protected new-loan disbursement reversal failed immutable journal integrity review.';
        END IF;

        RETURN existing_cancellation.id;
    END IF;

    SELECT *
    INTO prepared
    FROM accounting.loan_disbursement_journal_draft_preparations item
    WHERE item.id = posting.preparation_id;

    SELECT *
    INTO event_row
    FROM lending.loan_disbursement_events item
    WHERE item.id = posting.disbursement_event_id;

    SELECT *
    INTO original_journal
    FROM accounting.journal_entries item
    WHERE item.id = posting.journal_entry_id;

    SELECT *
    INTO debit_account
    FROM accounting.accounts item
    WHERE item.id = posting.debit_account_id;

    SELECT *
    INTO credit_account
    FROM accounting.accounts item
    WHERE item.id = posting.credit_account_id;

    IF prepared.id IS NULL
       OR prepared.disbursement_event_id <> posting.disbursement_event_id
       OR prepared.loan_id <> posting.loan_id
       OR prepared.client_id <> posting.client_id
       OR prepared.journal_entry_id <> posting.journal_entry_id
       OR prepared.source_event_key <> posting.source_event_key
       OR prepared.review_token <> posting.draft_review_token
       OR prepared.amount <> posting.amount
       OR prepared.debit_account_id <> posting.debit_account_id
       OR prepared.credit_account_id <> posting.credit_account_id THEN
        RAISE EXCEPTION 'Protected new-loan disbursement draft preparation no longer matches its immutable Stage 5D.22 posting audit.';
    END IF;

    IF event_row.id IS NULL
       OR event_row.is_voided
       OR event_row.event_kind <> 'new_loan_release'
       OR event_row.loan_id <> posting.loan_id
       OR event_row.client_id <> posting.client_id
       OR event_row.cash_disbursed_amount <> posting.amount
       OR event_row.settlement_amount <> 0
       OR event_row.other_deduction_amount <> 0
       OR event_row.principal_snapshot <> posting.amount
       OR event_row.funding_account_system_key <> credit_account.system_key THEN
        RAISE EXCEPTION 'Authoritative new-loan disbursement evidence no longer matches its posted accounting history.';
    END IF;

    IF original_journal.id IS NULL
       OR original_journal.status <> 'posted'
       OR original_journal.entry_number <> posting.entry_number
       OR original_journal.source_type <> 'loan_disbursement'
       OR original_journal.source_reference <> posting.disbursement_event_id::text
       OR original_journal.source_event_key <> posting.source_event_key
       OR original_journal.reversal_of_entry_id IS NOT NULL THEN
        RAISE EXCEPTION 'Original protected new-loan disbursement journal no longer matches its immutable Stage 5D.22 posting audit.';
    END IF;

    IF debit_account.id IS NULL
       OR debit_account.system_key <> 'loans_receivable_regular'
       OR debit_account.account_type <> 'asset'
       OR debit_account.is_active IS DISTINCT FROM true
       OR debit_account.is_posting IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'Original protected Loans Receivable - Regular account is unavailable for controlled reversal.';
    END IF;

    IF credit_account.id IS NULL
       OR credit_account.system_key NOT IN (
            'cash_office', 'cash_collector_custody', 'cash_bank_gcash'
       )
       OR credit_account.account_type <> 'asset'
       OR credit_account.is_active IS DISTINCT FROM true
       OR credit_account.is_posting IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'Original evidence-backed cash funding account is unavailable for controlled reversal.';
    END IF;

    SELECT
        count(*)::integer,
        coalesce(sum(line.debit), 0)::numeric(18,2),
        coalesce(sum(line.credit), 0)::numeric(18,2),
        count(*) FILTER (
            WHERE line.account_id = posting.debit_account_id
              AND line.debit = posting.amount
              AND line.credit = 0
              AND line.client_id = posting.client_id
              AND line.loan_id = posting.loan_id
        )::integer,
        count(*) FILTER (
            WHERE line.account_id = posting.credit_account_id
              AND line.credit = posting.amount
              AND line.debit = 0
              AND line.client_id = posting.client_id
              AND line.loan_id = posting.loan_id
        )::integer,
        count(*) FILTER (
            WHERE NOT (
                (line.account_id = posting.debit_account_id
                 AND line.debit = posting.amount
                 AND line.credit = 0
                 AND line.client_id = posting.client_id
                 AND line.loan_id = posting.loan_id)
                OR
                (line.account_id = posting.credit_account_id
                 AND line.credit = posting.amount
                 AND line.debit = 0
                 AND line.client_id = posting.client_id
                 AND line.loan_id = posting.loan_id)
            )
        )::integer
    INTO
        line_count,
        total_debit,
        total_credit,
        debit_match_count,
        credit_match_count,
        invalid_line_count
    FROM accounting.journal_lines line
    WHERE line.journal_entry_id = posting.journal_entry_id;

    IF line_count <> 2
       OR total_debit <> posting.amount
       OR total_credit <> posting.amount
       OR debit_match_count <> 1
       OR credit_match_count <> 1
       OR invalid_line_count <> 0 THEN
        RAISE EXCEPTION 'Original protected new-loan disbursement journal lines no longer match the immutable Stage 5D.22 audit.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM accounting.journal_entries journal
        WHERE journal.reversal_of_entry_id = posting.journal_entry_id
    ) THEN
        RAISE EXCEPTION 'The protected new-loan disbursement journal already has a reversal outside this cancellation audit.';
    END IF;

    SELECT period.id
    INTO target_period_id
    FROM accounting.fiscal_periods period
    WHERE period.status = 'open'
      AND p_reversal_posting_date BETWEEN period.start_date AND period.end_date
    ORDER BY period.start_date DESC
    LIMIT 1;

    IF target_period_id IS NULL THEN
        RAISE EXCEPTION 'No open accounting period contains the controlled new-loan disbursement reversal date.';
    END IF;

    PERFORM set_config('accounting.loan_disbursement_reversal_allowed', 'on', true);

    cancellation_id := gen_random_uuid();
    INSERT INTO lending.loan_disbursement_cancellations (
        id,
        disbursement_event_id,
        posting_id,
        original_journal_entry_id,
        cancellation_source_key,
        reversal_posting_date,
        reason,
        cancelled_by_user_id
    ) VALUES (
        cancellation_id,
        posting.disbursement_event_id,
        posting.id,
        posting.journal_entry_id,
        'loan_disbursement_cancellation:' || posting.disbursement_event_id::text,
        p_reversal_posting_date,
        normalized_reason,
        p_actor_user_id
    );

    reversal_journal_id := gen_random_uuid();
    reversal_source_key :=
        'loan_disbursement_cancellation_reversal:' || posting.id::text;

    INSERT INTO accounting.journal_entries (
        id,
        fiscal_period_id,
        posting_date,
        description,
        status,
        source_type,
        source_reference,
        source_event_key,
        reversal_of_entry_id,
        created_by_user_id
    ) VALUES (
        reversal_journal_id,
        target_period_id,
        p_reversal_posting_date,
        'Controlled cancellation reversal of ' || posting.entry_number
            || ': ' || normalized_reason,
        'draft',
        'loan_disbursement_cancellation_reversal',
        cancellation_id::text,
        reversal_source_key,
        posting.journal_entry_id,
        p_actor_user_id
    );

    INSERT INTO accounting.journal_lines (
        journal_entry_id,
        line_number,
        account_id,
        description,
        debit,
        credit,
        client_id,
        loan_id
    )
    SELECT
        reversal_journal_id,
        original_line.line_number,
        original_line.account_id,
        'Cancellation reversal - ' || original_line.description,
        original_line.credit,
        original_line.debit,
        original_line.client_id,
        original_line.loan_id
    FROM accounting.journal_lines original_line
    WHERE original_line.journal_entry_id = posting.journal_entry_id
    ORDER BY original_line.line_number;

    INSERT INTO accounting.journal_events (
        journal_entry_id,
        event_type,
        actor_user_id,
        details
    ) VALUES (
        reversal_journal_id,
        'reversal_created',
        p_actor_user_id,
        jsonb_build_object(
            'reversal_of_entry_id', posting.journal_entry_id,
            'posting_id', posting.id,
            'disbursement_event_id', posting.disbursement_event_id,
            'cancellation_id', cancellation_id,
            'reason', normalized_reason,
            'automatic_source_posting', false
        )
    );

    generated_number := accounting.post_journal_entry(
        reversal_journal_id,
        p_actor_user_id
    );

    INSERT INTO accounting.journal_events (
        journal_entry_id,
        event_type,
        actor_user_id,
        details
    ) VALUES (
        reversal_journal_id,
        'posted',
        p_actor_user_id,
        jsonb_build_object(
            'entry_number', generated_number,
            'protected_loan_disbursement_cancellation', true,
            'automatic_source_posting', false
        )
    );

    INSERT INTO accounting.loan_disbursement_journal_reversals (
        cancellation_id,
        posting_id,
        disbursement_event_id,
        original_journal_entry_id,
        reversal_journal_entry_id,
        original_entry_number,
        reversal_entry_number,
        original_source_event_key,
        reversal_source_event_key,
        original_debit_account_id,
        original_credit_account_id,
        amount,
        reversed_by_user_id
    ) VALUES (
        cancellation_id,
        posting.id,
        posting.disbursement_event_id,
        posting.journal_entry_id,
        reversal_journal_id,
        posting.entry_number,
        generated_number,
        posting.source_event_key,
        reversal_source_key,
        posting.debit_account_id,
        posting.credit_account_id,
        posting.amount,
        p_actor_user_id
    );

    PERFORM set_config('accounting.loan_disbursement_reversal_allowed', 'off', true);

    INSERT INTO core.audit_logs (
        actor_user_id,
        action,
        target_type,
        target_id,
        details
    ) VALUES (
        p_actor_user_id,
        'accounting.loan_disbursement_journal.cancelled_reversed',
        'loan_disbursement_cancellation',
        cancellation_id,
        jsonb_build_object(
            'posting_id', posting.id::text,
            'disbursement_event_id', posting.disbursement_event_id::text,
            'original_journal_entry_id', posting.journal_entry_id::text,
            'original_entry_number', posting.entry_number,
            'reversal_journal_entry_id', reversal_journal_id::text,
            'reversal_entry_number', generated_number,
            'reversal_posting_date', p_reversal_posting_date,
            'amount', posting.amount,
            'reason', normalized_reason,
            'automatic_source_posting', false
        )
    );

    RETURN cancellation_id;
END;
$$;

CREATE OR REPLACE VIEW accounting.loan_disbursement_cancellation_status AS
SELECT
    posting.id AS posting_id,
    posting.preparation_id,
    posting.disbursement_event_id,
    posting.loan_id,
    posting.client_id,
    posting.journal_entry_id AS original_journal_entry_id,
    posting.entry_number AS original_entry_number,
    posting.source_event_key AS original_source_event_key,
    posting.posting_review_token,
    posting.amount,
    posting.debit_account_id AS original_debit_account_id,
    debit_account.system_key AS original_debit_account_system_key,
    posting.credit_account_id AS original_credit_account_id,
    credit_account.system_key AS original_credit_account_system_key,
    original_journal.status AS original_journal_status,
    cancellation.id AS cancellation_id,
    cancellation.cancellation_source_key,
    cancellation.reversal_posting_date,
    cancellation.reason AS cancellation_reason,
    cancellation.cancelled_by_user_id,
    cancellation.cancelled_at,
    reversal.id AS reversal_id,
    reversal.reversal_journal_entry_id,
    reversal.reversal_entry_number,
    reversal.reversal_source_event_key,
    reversal_journal.status AS reversal_journal_status,
    CASE
        WHEN cancellation.id IS NULL
         AND reversal.id IS NULL
         AND original_journal.status = 'posted'
         AND original_journal.entry_number = posting.entry_number
         AND original_journal.source_event_key = posting.source_event_key
         AND debit_account.system_key = 'loans_receivable_regular'
         AND debit_account.is_active = true
         AND debit_account.is_posting = true
         AND credit_account.system_key IN (
             'cash_office', 'cash_collector_custody', 'cash_bank_gcash'
         )
         AND credit_account.is_active = true
         AND credit_account.is_posting = true
            THEN true
        ELSE false
    END AS cancellation_ready,
    CASE
        WHEN cancellation.id IS NOT NULL
         AND reversal.id IS NOT NULL
         AND reversal.cancellation_id = cancellation.id
         AND reversal.posting_id = posting.id
         AND reversal.disbursement_event_id = posting.disbursement_event_id
         AND reversal.original_journal_entry_id = posting.journal_entry_id
         AND reversal.original_entry_number = posting.entry_number
         AND reversal.original_source_event_key = posting.source_event_key
         AND reversal.amount = posting.amount
         AND reversal_journal.status = 'posted'
         AND reversal_journal.entry_number = reversal.reversal_entry_number
         AND reversal_journal.source_event_key = reversal.reversal_source_event_key
         AND reversal_journal.reversal_of_entry_id = posting.journal_entry_id
            THEN true
        ELSE false
    END AS cancelled_reversal_audit_exact,
    true AS protected_reversal_enabled,
    false AS automatic_source_posting
FROM accounting.loan_disbursement_journal_postings posting
JOIN accounting.journal_entries original_journal
  ON original_journal.id = posting.journal_entry_id
JOIN accounting.accounts debit_account
  ON debit_account.id = posting.debit_account_id
JOIN accounting.accounts credit_account
  ON credit_account.id = posting.credit_account_id
LEFT JOIN lending.loan_disbursement_cancellations cancellation
  ON cancellation.posting_id = posting.id
LEFT JOIN accounting.loan_disbursement_journal_reversals reversal
  ON reversal.cancellation_id = cancellation.id
LEFT JOIN accounting.journal_entries reversal_journal
  ON reversal_journal.id = reversal.reversal_journal_entry_id;

COMMENT ON TABLE lending.loan_disbursement_cancellations IS
    'Immutable Stage 5D.23 cancellation evidence for an already-posted protected pure new Regular loan disbursement. Original disbursement evidence and journal history remain unchanged.';
COMMENT ON TABLE accounting.loan_disbursement_journal_reversals IS
    'Immutable Stage 5D.23 audit linking a protected disbursement cancellation to its exact separate posted reversing journal.';
COMMENT ON VIEW accounting.loan_disbursement_cancellation_status IS
    'Read-only Stage 5D.23 cancellation/reversal status. Original history remains immutable and automatic source posting remains disabled.';

COMMIT;
