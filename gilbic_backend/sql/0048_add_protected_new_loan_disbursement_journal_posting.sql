BEGIN;

INSERT INTO core.permissions (code, description)
VALUES (
    'accounting.loan_disbursement.journal.post',
    'Explicitly post one integrity-ready protected pure new Regular loan-disbursement draft after exact Management confirmation'
)
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code = 'accounting.loan_disbursement.journal.post'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.loan_disbursement_journal_postings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    preparation_id UUID NOT NULL UNIQUE
        REFERENCES accounting.loan_disbursement_journal_draft_preparations(id)
        ON DELETE RESTRICT,
    disbursement_event_id UUID NOT NULL UNIQUE
        REFERENCES lending.loan_disbursement_events(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL
        REFERENCES lending.loans(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL
        REFERENCES lending.clients(id) ON DELETE RESTRICT,
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    source_event_key TEXT NOT NULL UNIQUE,
    draft_review_token TEXT NOT NULL,
    posting_review_token TEXT NOT NULL,
    draft_policy_version TEXT NOT NULL,
    posting_policy_version TEXT NOT NULL,
    posting_date DATE NOT NULL,
    fiscal_period_id UUID NOT NULL
        REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    debit_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    credit_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    amount NUMERIC(18,2) NOT NULL CHECK (amount > 0),
    entry_number TEXT NOT NULL UNIQUE,
    posted_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    posted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (source_event_key = 'loan_disbursement:' || disbursement_event_id::text),
    CHECK (draft_review_token ~ '^[0-9a-f]{64}$'),
    CHECK (posting_review_token ~ '^[0-9a-f]{64}$'),
    CHECK (draft_policy_version = 'new_loan_disbursement_journal_draft_v1'),
    CHECK (posting_policy_version = 'new_loan_disbursement_journal_posting_v1'),
    CHECK (debit_account_id <> credit_account_id),
    CHECK (btrim(entry_number) <> '')
);

CREATE INDEX IF NOT EXISTS loan_disbursement_journal_postings_loan_idx
    ON accounting.loan_disbursement_journal_postings (loan_id, posted_at DESC);

CREATE OR REPLACE FUNCTION accounting.guard_loan_disbursement_journal_posting_record_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(
            current_setting('accounting.loan_disbursement_journal_post_record_allowed', true),
            ''
       ) = 'on' THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'Protected new-loan disbursement journal posting audit is immutable and must use the protected posting function.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_loan_disbursement_journal_posting_guard
    ON accounting.loan_disbursement_journal_postings;
CREATE TRIGGER accounting_loan_disbursement_journal_posting_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.loan_disbursement_journal_postings
FOR EACH ROW EXECUTE FUNCTION accounting.guard_loan_disbursement_journal_posting_record_write();

CREATE OR REPLACE FUNCTION accounting.post_new_loan_disbursement_journal(
    p_preparation_id UUID,
    p_actor_user_id UUID,
    p_posting_review_token TEXT,
    p_expected_journal_entry_id UUID,
    p_expected_source_event_key TEXT,
    p_expected_draft_review_token TEXT,
    p_expected_posting_date DATE,
    p_expected_fiscal_period_id UUID,
    p_expected_debit_account_id UUID,
    p_expected_credit_account_id UUID,
    p_expected_amount NUMERIC,
    p_expected_total_debit NUMERIC,
    p_expected_total_credit NUMERIC,
    p_posting_policy_version TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    prepared accounting.loan_disbursement_journal_draft_preparations%ROWTYPE;
    existing_post accounting.loan_disbursement_journal_postings%ROWTYPE;
    event_row lending.loan_disbursement_events%ROWTYPE;
    loan_row RECORD;
    journal_row accounting.journal_entries%ROWTYPE;
    period_row accounting.fiscal_periods%ROWTYPE;
    debit_account_row accounting.accounts%ROWTYPE;
    credit_account_row accounting.accounts%ROWTYPE;
    normalized_posting_token TEXT := lower(btrim(coalesce(p_posting_review_token, '')));
    normalized_source_key TEXT := btrim(coalesce(p_expected_source_event_key, ''));
    normalized_draft_token TEXT := lower(btrim(coalesce(p_expected_draft_review_token, '')));
    expected_amount NUMERIC(18,2) := round(coalesce(p_expected_amount, 0), 2);
    expected_total_debit NUMERIC(18,2) := round(coalesce(p_expected_total_debit, 0), 2);
    expected_total_credit NUMERIC(18,2) := round(coalesce(p_expected_total_credit, 0), 2);
    line_count INTEGER;
    total_debit NUMERIC(18,2);
    total_credit NUMERIC(18,2);
    debit_match_count INTEGER;
    credit_match_count INTEGER;
    invalid_line_count INTEGER;
    entry_number TEXT;
    posting_id UUID;
BEGIN
    IF p_posting_policy_version IS DISTINCT FROM 'new_loan_disbursement_journal_posting_v1' THEN
        RAISE EXCEPTION 'Unsupported new-loan disbursement journal posting policy version.';
    END IF;
    IF normalized_posting_token !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Protected new-loan disbursement posting review token is invalid.';
    END IF;
    IF normalized_draft_token !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Protected new-loan disbursement draft review token is invalid.';
    END IF;
    IF expected_amount <= 0
       OR p_expected_amount IS DISTINCT FROM expected_amount
       OR p_expected_total_debit IS DISTINCT FROM expected_total_debit
       OR p_expected_total_credit IS DISTINCT FROM expected_total_credit
       OR expected_total_debit <> expected_amount
       OR expected_total_credit <> expected_amount THEN
        RAISE EXCEPTION 'Protected new-loan disbursement posting confirmation must contain one exact positive balanced two-decimal amount.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended(
            'new-loan-disbursement-journal-post:' || p_preparation_id::text,
            0
        )
    );

    -- Freeze every source used by the evidence, coordinate, draft and posting
    -- decisions. The protected posting transition and immutable audit then occur
    -- inside this same database transaction.
    LOCK TABLE
        lending.loan_disbursement_events,
        lending.loans,
        lending.loan_types,
        accounting.fiscal_periods,
        accounting.accounts,
        accounting.journal_entries,
        accounting.journal_lines,
        accounting.loan_disbursement_journal_draft_preparations,
        accounting.loan_disbursement_journal_postings
    IN SHARE MODE;

    SELECT *
    INTO prepared
    FROM accounting.loan_disbursement_journal_draft_preparations item
    WHERE item.id = p_preparation_id;

    IF prepared.id IS NULL THEN
        RAISE EXCEPTION 'Protected new-loan disbursement journal preparation was not found.';
    END IF;

    IF normalized_source_key <> prepared.source_event_key
       OR normalized_source_key <> 'loan_disbursement:' || prepared.disbursement_event_id::text
       OR p_expected_journal_entry_id <> prepared.journal_entry_id
       OR normalized_draft_token <> prepared.review_token
       OR prepared.draft_policy_version <> 'new_loan_disbursement_journal_draft_v1'
       OR prepared.coordinate_policy_version <> 'new_loan_disbursement_coordinates_v1'
       OR p_expected_posting_date <> prepared.posting_date
       OR p_expected_fiscal_period_id <> prepared.fiscal_period_id
       OR p_expected_debit_account_id <> prepared.debit_account_id
       OR p_expected_credit_account_id <> prepared.credit_account_id
       OR expected_amount <> prepared.amount THEN
        RAISE EXCEPTION 'Protected new-loan disbursement posting confirmation changed from the immutable draft preparation.';
    END IF;

    SELECT *
    INTO existing_post
    FROM accounting.loan_disbursement_journal_postings posting
    WHERE posting.preparation_id = p_preparation_id;

    -- Exact retry succeeds only if the immutable posting audit and the posted
    -- journal still agree with every confirmed identity and amount.
    IF existing_post.id IS NOT NULL THEN
        IF existing_post.disbursement_event_id <> prepared.disbursement_event_id
           OR existing_post.loan_id <> prepared.loan_id
           OR existing_post.client_id <> prepared.client_id
           OR existing_post.journal_entry_id <> prepared.journal_entry_id
           OR existing_post.source_event_key <> normalized_source_key
           OR existing_post.draft_review_token <> normalized_draft_token
           OR existing_post.posting_review_token <> normalized_posting_token
           OR existing_post.draft_policy_version <> prepared.draft_policy_version
           OR existing_post.posting_policy_version <> p_posting_policy_version
           OR existing_post.posting_date <> prepared.posting_date
           OR existing_post.fiscal_period_id <> prepared.fiscal_period_id
           OR existing_post.debit_account_id <> prepared.debit_account_id
           OR existing_post.credit_account_id <> prepared.credit_account_id
           OR existing_post.amount <> prepared.amount THEN
            RAISE EXCEPTION 'Existing protected new-loan disbursement posting audit does not match the confirmed posting identity.';
        END IF;

        SELECT *
        INTO journal_row
        FROM accounting.journal_entries journal
        WHERE journal.id = prepared.journal_entry_id;

        IF journal_row.id IS NULL
           OR journal_row.status <> 'posted'
           OR journal_row.entry_number <> existing_post.entry_number
           OR journal_row.source_type <> 'loan_disbursement'
           OR journal_row.source_reference <> prepared.disbursement_event_id::text
           OR journal_row.source_event_key <> normalized_source_key
           OR journal_row.posting_date <> prepared.posting_date
           OR journal_row.fiscal_period_id <> prepared.fiscal_period_id THEN
            RAISE EXCEPTION 'Existing protected new-loan disbursement posting audit does not match the posted journal.';
        END IF;

        SELECT
            count(*)::integer,
            coalesce(sum(line.debit), 0)::numeric(18,2),
            coalesce(sum(line.credit), 0)::numeric(18,2),
            count(*) FILTER (
                WHERE line.account_id = prepared.debit_account_id
                  AND line.debit = prepared.amount
                  AND line.credit = 0
                  AND line.client_id = prepared.client_id
                  AND line.loan_id = prepared.loan_id
            )::integer,
            count(*) FILTER (
                WHERE line.account_id = prepared.credit_account_id
                  AND line.credit = prepared.amount
                  AND line.debit = 0
                  AND line.client_id = prepared.client_id
                  AND line.loan_id = prepared.loan_id
            )::integer
        INTO line_count, total_debit, total_credit, debit_match_count, credit_match_count
        FROM accounting.journal_lines line
        WHERE line.journal_entry_id = prepared.journal_entry_id;

        IF line_count <> 2
           OR total_debit <> prepared.amount
           OR total_credit <> prepared.amount
           OR debit_match_count <> 1
           OR credit_match_count <> 1 THEN
            RAISE EXCEPTION 'Existing protected new-loan disbursement posting audit failed immutable line integrity review.';
        END IF;

        RETURN existing_post.id;
    END IF;

    SELECT *
    INTO event_row
    FROM lending.loan_disbursement_events event
    WHERE event.id = prepared.disbursement_event_id;

    SELECT
        loan.id,
        loan.client_id,
        loan.loan_type_id,
        loan.principal,
        loan.date_released,
        loan.status,
        loan_type.calculation_mode
    INTO loan_row
    FROM lending.loans loan
    JOIN lending.loan_types loan_type ON loan_type.id = loan.loan_type_id
    WHERE loan.id = prepared.loan_id;

    SELECT *
    INTO journal_row
    FROM accounting.journal_entries journal
    WHERE journal.id = prepared.journal_entry_id;

    SELECT *
    INTO period_row
    FROM accounting.fiscal_periods period
    WHERE period.id = prepared.fiscal_period_id;

    SELECT *
    INTO debit_account_row
    FROM accounting.accounts account
    WHERE account.id = prepared.debit_account_id;

    SELECT *
    INTO credit_account_row
    FROM accounting.accounts account
    WHERE account.id = prepared.credit_account_id;

    IF event_row.id IS NULL
       OR event_row.is_voided
       OR event_row.event_kind <> 'new_loan_release'
       OR event_row.loan_id <> prepared.loan_id
       OR event_row.client_id <> prepared.client_id
       OR event_row.business_date <> prepared.posting_date
       OR event_row.settlement_amount <> 0
       OR event_row.other_deduction_amount <> 0
       OR event_row.cash_disbursed_amount <> prepared.amount
       OR event_row.principal_snapshot <> prepared.amount
       OR event_row.funding_account_system_key NOT IN (
            'cash_office', 'cash_collector_custody', 'cash_bank_gcash'
       ) THEN
        RAISE EXCEPTION 'Authoritative new-loan disbursement evidence changed or is no longer eligible for protected posting.';
    END IF;

    IF loan_row.id IS NULL
       OR loan_row.client_id <> prepared.client_id
       OR loan_row.principal <> event_row.principal_snapshot
       OR loan_row.date_released <> event_row.date_released_snapshot
       OR loan_row.date_released <> event_row.business_date
       OR loan_row.calculation_mode <> 'fixed_daily' THEN
        RAISE EXCEPTION 'New Regular loan state no longer matches the authoritative disbursement evidence.';
    END IF;

    IF period_row.id IS NULL
       OR period_row.status <> 'open'
       OR prepared.posting_date NOT BETWEEN period_row.start_date AND period_row.end_date THEN
        RAISE EXCEPTION 'Protected new-loan disbursement journal can only post into its still-open containing fiscal period.';
    END IF;

    IF debit_account_row.id IS NULL
       OR debit_account_row.system_key <> 'loans_receivable_regular'
       OR debit_account_row.account_type <> 'asset'
       OR debit_account_row.is_active IS DISTINCT FROM true
       OR debit_account_row.is_posting IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'Protected new-loan disbursement debit account is no longer the active posting Loans Receivable - Regular account.';
    END IF;

    IF credit_account_row.id IS NULL
       OR credit_account_row.system_key <> event_row.funding_account_system_key
       OR credit_account_row.system_key NOT IN (
            'cash_office', 'cash_collector_custody', 'cash_bank_gcash'
       )
       OR credit_account_row.account_type <> 'asset'
       OR credit_account_row.is_active IS DISTINCT FROM true
       OR credit_account_row.is_posting IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'Protected new-loan disbursement credit account no longer matches the active evidence-backed cash funding account.';
    END IF;

    IF journal_row.id IS NULL
       OR journal_row.status <> 'draft'
       OR journal_row.entry_number IS NOT NULL
       OR journal_row.posted_by_user_id IS NOT NULL
       OR journal_row.posted_at IS NOT NULL
       OR journal_row.source_type <> 'loan_disbursement'
       OR journal_row.source_reference <> prepared.disbursement_event_id::text
       OR journal_row.source_event_key <> prepared.source_event_key
       OR journal_row.posting_date <> prepared.posting_date
       OR journal_row.fiscal_period_id <> prepared.fiscal_period_id THEN
        RAISE EXCEPTION 'Protected new-loan disbursement journal draft identity changed or was posted without the protected posting audit.';
    END IF;

    SELECT
        count(*)::integer,
        coalesce(sum(line.debit), 0)::numeric(18,2),
        coalesce(sum(line.credit), 0)::numeric(18,2),
        count(*) FILTER (
            WHERE line.account_id = prepared.debit_account_id
              AND line.debit = prepared.amount
              AND line.credit = 0
              AND line.client_id = prepared.client_id
              AND line.loan_id = prepared.loan_id
        )::integer,
        count(*) FILTER (
            WHERE line.account_id = prepared.credit_account_id
              AND line.credit = prepared.amount
              AND line.debit = 0
              AND line.client_id = prepared.client_id
              AND line.loan_id = prepared.loan_id
        )::integer,
        count(*) FILTER (
            WHERE NOT (
                (line.account_id = prepared.debit_account_id
                 AND line.debit = prepared.amount
                 AND line.credit = 0
                 AND line.client_id = prepared.client_id
                 AND line.loan_id = prepared.loan_id)
                OR
                (line.account_id = prepared.credit_account_id
                 AND line.credit = prepared.amount
                 AND line.debit = 0
                 AND line.client_id = prepared.client_id
                 AND line.loan_id = prepared.loan_id)
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
    WHERE line.journal_entry_id = prepared.journal_entry_id;

    IF line_count <> 2
       OR total_debit <> prepared.amount
       OR total_credit <> prepared.amount
       OR total_debit <> total_credit
       OR debit_match_count <> 1
       OR credit_match_count <> 1
       OR invalid_line_count <> 0 THEN
        RAISE EXCEPTION 'Protected new-loan disbursement journal lines no longer match the exact approved Dr 1100 / Cr evidence-backed cash pattern.';
    END IF;

    -- The base posting function still performs its own open-period, active-account
    -- and balance checks. Stage 5D.21's guard additionally requires this private
    -- protected-post GUC, preventing direct generic/manual posting bypass.
    PERFORM set_config('accounting.loan_disbursement_journal_post_allowed', 'on', true);
    SELECT accounting.post_journal_entry(prepared.journal_entry_id, p_actor_user_id)
    INTO entry_number;
    PERFORM set_config('accounting.loan_disbursement_journal_post_allowed', 'off', true);

    PERFORM set_config('accounting.loan_disbursement_journal_post_record_allowed', 'on', true);
    INSERT INTO accounting.loan_disbursement_journal_postings (
        preparation_id,
        disbursement_event_id,
        loan_id,
        client_id,
        journal_entry_id,
        source_event_key,
        draft_review_token,
        posting_review_token,
        draft_policy_version,
        posting_policy_version,
        posting_date,
        fiscal_period_id,
        debit_account_id,
        credit_account_id,
        amount,
        entry_number,
        posted_by_user_id
    )
    VALUES (
        prepared.id,
        prepared.disbursement_event_id,
        prepared.loan_id,
        prepared.client_id,
        prepared.journal_entry_id,
        prepared.source_event_key,
        prepared.review_token,
        normalized_posting_token,
        prepared.draft_policy_version,
        p_posting_policy_version,
        prepared.posting_date,
        prepared.fiscal_period_id,
        prepared.debit_account_id,
        prepared.credit_account_id,
        prepared.amount,
        entry_number,
        p_actor_user_id
    )
    RETURNING id INTO posting_id;
    PERFORM set_config('accounting.loan_disbursement_journal_post_record_allowed', 'off', true);

    INSERT INTO core.audit_logs (
        actor_user_id,
        action,
        target_type,
        target_id,
        details
    )
    VALUES (
        p_actor_user_id,
        'accounting.loan_disbursement_journal.posted',
        'loan_disbursement_journal_posting',
        posting_id,
        jsonb_build_object(
            'preparation_id', prepared.id::text,
            'disbursement_event_id', prepared.disbursement_event_id::text,
            'loan_id', prepared.loan_id::text,
            'journal_entry_id', prepared.journal_entry_id::text,
            'entry_number', entry_number,
            'source_event_key', prepared.source_event_key,
            'posting_date', prepared.posting_date,
            'amount', prepared.amount,
            'debit_account_system_key', debit_account_row.system_key,
            'credit_account_system_key', credit_account_row.system_key,
            'draft_review_token', prepared.review_token,
            'posting_review_token', normalized_posting_token,
            'automatic_source_posting', false
        )
    );

    RETURN posting_id;
END;
$$;

CREATE OR REPLACE VIEW accounting.loan_disbursement_journal_posting_status AS
WITH line_summary AS (
    SELECT
        prepared.id AS preparation_id,
        count(line.id)::integer AS line_count,
        coalesce(sum(line.debit), 0)::numeric(18,2) AS total_debit,
        coalesce(sum(line.credit), 0)::numeric(18,2) AS total_credit,
        count(line.id) FILTER (
            WHERE line.account_id = prepared.debit_account_id
              AND line.debit = prepared.amount
              AND line.credit = 0
              AND line.client_id = prepared.client_id
              AND line.loan_id = prepared.loan_id
        )::integer AS debit_match_count,
        count(line.id) FILTER (
            WHERE line.account_id = prepared.credit_account_id
              AND line.credit = prepared.amount
              AND line.debit = 0
              AND line.client_id = prepared.client_id
              AND line.loan_id = prepared.loan_id
        )::integer AS credit_match_count
    FROM accounting.loan_disbursement_journal_draft_preparations prepared
    LEFT JOIN accounting.journal_lines line
      ON line.journal_entry_id = prepared.journal_entry_id
    GROUP BY prepared.id
)
SELECT
    prepared.id AS preparation_id,
    prepared.disbursement_event_id,
    prepared.loan_id,
    prepared.client_id,
    prepared.journal_entry_id,
    prepared.source_event_key,
    prepared.review_token AS draft_review_token,
    prepared.draft_policy_version,
    prepared.posting_date,
    prepared.fiscal_period_id,
    period.label AS fiscal_period_label,
    period.status AS fiscal_period_status,
    prepared.amount,
    prepared.debit_account_id,
    debit_account.system_key AS debit_account_system_key,
    prepared.credit_account_id,
    credit_account.system_key AS credit_account_system_key,
    journal.status AS journal_status,
    journal.entry_number,
    journal.posted_by_user_id AS journal_posted_by_user_id,
    journal.posted_at AS journal_posted_at,
    line_summary.line_count,
    line_summary.total_debit,
    line_summary.total_credit,
    posting.id AS posting_id,
    posting.posting_review_token,
    posting.posting_policy_version,
    posting.entry_number AS audited_entry_number,
    posting.posted_by_user_id,
    posting.posted_at,
    CASE
        WHEN posting.id IS NULL
         AND journal.status = 'draft'
         AND journal.entry_number IS NULL
         AND period.status = 'open'
         AND journal.posting_date BETWEEN period.start_date AND period.end_date
         AND debit_account.system_key = 'loans_receivable_regular'
         AND debit_account.is_active = true
         AND debit_account.is_posting = true
         AND credit_account.system_key IN (
             'cash_office', 'cash_collector_custody', 'cash_bank_gcash'
         )
         AND credit_account.is_active = true
         AND credit_account.is_posting = true
         AND line_summary.line_count = 2
         AND line_summary.total_debit = prepared.amount
         AND line_summary.total_credit = prepared.amount
         AND line_summary.debit_match_count = 1
         AND line_summary.credit_match_count = 1
            THEN true
        ELSE false
    END AS posting_ready,
    CASE
        WHEN posting.id IS NOT NULL
         AND journal.status = 'posted'
         AND journal.entry_number = posting.entry_number
         AND journal.source_event_key = posting.source_event_key
         AND posting.preparation_id = prepared.id
         AND posting.journal_entry_id = prepared.journal_entry_id
         AND posting.disbursement_event_id = prepared.disbursement_event_id
         AND posting.loan_id = prepared.loan_id
         AND posting.client_id = prepared.client_id
         AND posting.draft_review_token = prepared.review_token
         AND posting.posting_date = prepared.posting_date
         AND posting.fiscal_period_id = prepared.fiscal_period_id
         AND posting.debit_account_id = prepared.debit_account_id
         AND posting.credit_account_id = prepared.credit_account_id
         AND posting.amount = prepared.amount
         AND line_summary.line_count = 2
         AND line_summary.total_debit = prepared.amount
         AND line_summary.total_credit = prepared.amount
         AND line_summary.debit_match_count = 1
         AND line_summary.credit_match_count = 1
            THEN true
        ELSE false
    END AS posted_audit_exact,
    true AS protected_posting_enabled,
    false AS automatic_source_posting
FROM accounting.loan_disbursement_journal_draft_preparations prepared
JOIN accounting.journal_entries journal
  ON journal.id = prepared.journal_entry_id
JOIN accounting.fiscal_periods period
  ON period.id = prepared.fiscal_period_id
JOIN accounting.accounts debit_account
  ON debit_account.id = prepared.debit_account_id
JOIN accounting.accounts credit_account
  ON credit_account.id = prepared.credit_account_id
JOIN line_summary
  ON line_summary.preparation_id = prepared.id
LEFT JOIN accounting.loan_disbursement_journal_postings posting
  ON posting.preparation_id = prepared.id;

COMMENT ON TABLE accounting.loan_disbursement_journal_postings IS
    'Immutable Stage 5D.22 protected posting audit for one Management-confirmed pure new Regular loan-disbursement draft. Exact retry must resolve to the same posted journal and audit.';
COMMENT ON VIEW accounting.loan_disbursement_journal_posting_status IS
    'Read-only Stage 5D.22 posting readiness/audit status. Posting remains explicit Management action and automatic source posting remains disabled.';

COMMIT;
