BEGIN;

INSERT INTO core.permissions (code, description)
VALUES (
    'accounting.seven_by_seven.journal.post',
    'Explicitly post one integrity-ready protected 7x7 collection journal after exact Management confirmation'
)
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code = 'accounting.seven_by_seven.journal.post'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.seven_by_seven_journal_postings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    preparation_id UUID NOT NULL UNIQUE
        REFERENCES accounting.seven_by_seven_journal_draft_preparations(id)
        ON DELETE RESTRICT,
    transaction_id UUID NOT NULL UNIQUE
        REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL
        REFERENCES lending.loans(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL
        REFERENCES lending.clients(id) ON DELETE RESTRICT,
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    source_event_key TEXT NOT NULL UNIQUE,
    source_event_review_token TEXT NOT NULL,
    coordinate_digest TEXT NOT NULL,
    posting_review_token TEXT NOT NULL,
    draft_policy_version TEXT NOT NULL,
    posting_policy_version TEXT NOT NULL,
    posting_date DATE NOT NULL,
    fiscal_period_id UUID NOT NULL
        REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    source_cash_amount NUMERIC(18,2) NOT NULL CHECK (source_cash_amount > 0),
    eir_interest_accrual NUMERIC(18,2) NOT NULL CHECK (eir_interest_accrual >= 0),
    accounting_eir_interest_received NUMERIC(18,2) NOT NULL
        CHECK (accounting_eir_interest_received >= 0),
    accounting_7x7_principal_received NUMERIC(18,2) NOT NULL
        CHECK (accounting_7x7_principal_received >= 0),
    coordinate_line_count INTEGER NOT NULL CHECK (coordinate_line_count > 0),
    total_debit NUMERIC(18,2) NOT NULL CHECK (total_debit > 0),
    total_credit NUMERIC(18,2) NOT NULL CHECK (total_credit > 0),
    entry_number TEXT NOT NULL UNIQUE,
    posted_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    posted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (source_event_key = 'collection:' || transaction_id::text),
    CHECK (source_event_review_token ~ '^[0-9a-f]{64}$'),
    CHECK (coordinate_digest ~ '^[0-9a-f]{64}$'),
    CHECK (posting_review_token ~ '^[0-9a-f]{64}$'),
    CHECK (draft_policy_version = 'seven_by_seven_source_event_journal_draft_v1'),
    CHECK (posting_policy_version = 'seven_by_seven_source_event_journal_posting_v1'),
    CHECK (
        source_cash_amount =
            accounting_eir_interest_received + accounting_7x7_principal_received
    ),
    CHECK (total_debit = total_credit),
    CHECK (btrim(entry_number) <> '')
);

CREATE INDEX IF NOT EXISTS seven_by_seven_journal_postings_loan_idx
    ON accounting.seven_by_seven_journal_postings (loan_id, posted_at DESC);

CREATE TABLE IF NOT EXISTS accounting.seven_by_seven_journal_posting_lines (
    posting_id UUID NOT NULL
        REFERENCES accounting.seven_by_seven_journal_postings(id) ON DELETE RESTRICT,
    line_number INTEGER NOT NULL CHECK (line_number > 0),
    journal_component TEXT NOT NULL,
    account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    account_system_key TEXT NOT NULL,
    debit NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (debit >= 0),
    credit NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (credit >= 0),
    client_id UUID NOT NULL
        REFERENCES lending.clients(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL
        REFERENCES lending.loans(id) ON DELETE RESTRICT,
    PRIMARY KEY (posting_id, line_number),
    UNIQUE (posting_id, journal_component),
    CHECK (btrim(journal_component) <> ''),
    CHECK (btrim(account_system_key) <> ''),
    CHECK (
        (debit > 0 AND credit = 0)
        OR (credit > 0 AND debit = 0)
    )
);

CREATE OR REPLACE FUNCTION accounting.guard_seven_by_seven_journal_posting_record_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(
            current_setting('accounting.seven_by_seven_journal_post_record_allowed', true),
            ''
       ) = 'on' THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'Protected 7x7 journal posting audit is immutable and must use the protected posting function.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_seven_by_seven_journal_posting_guard
    ON accounting.seven_by_seven_journal_postings;
CREATE TRIGGER accounting_seven_by_seven_journal_posting_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.seven_by_seven_journal_postings
FOR EACH ROW EXECUTE FUNCTION accounting.guard_seven_by_seven_journal_posting_record_write();

DROP TRIGGER IF EXISTS accounting_seven_by_seven_journal_posting_line_guard
    ON accounting.seven_by_seven_journal_posting_lines;
CREATE TRIGGER accounting_seven_by_seven_journal_posting_line_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.seven_by_seven_journal_posting_lines
FOR EACH ROW EXECUTE FUNCTION accounting.guard_seven_by_seven_journal_posting_record_write();

-- Until the next Master #296 sub-slice installs a controlled 7x7 reversal,
-- generic/manual reversal of a protected posted 7x7 journal is fail-closed.
CREATE OR REPLACE FUNCTION accounting.guard_protected_seven_by_seven_reversal_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    original_is_protected BOOLEAN := false;
BEGIN
    IF NEW.reversal_of_entry_id IS NOT NULL THEN
        SELECT EXISTS (
            SELECT 1
            FROM accounting.seven_by_seven_journal_postings posted
            WHERE posted.journal_entry_id = NEW.reversal_of_entry_id
        )
        INTO original_is_protected;
    END IF;

    IF NEW.source_type = 'seven_by_seven_collection_reversal' THEN
        RAISE EXCEPTION 'Protected 7x7 reversal remains disabled until the controlled reversal workflow is installed.';
    ELSIF original_is_protected THEN
        RAISE EXCEPTION 'Posted protected 7x7 journals cannot be reversed through the manual General Journal.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_protected_seven_by_seven_reversal_insert_guard
    ON accounting.journal_entries;
CREATE TRIGGER accounting_protected_seven_by_seven_reversal_insert_guard
BEFORE INSERT ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_protected_seven_by_seven_reversal_insert();

-- Posting is now enabled, but reversal is deliberately not. A posted 7x7
-- collection therefore cannot be operationally voided until the next protected
-- sub-slice can reverse the accounting in the same transaction.
CREATE OR REPLACE FUNCTION accounting.guard_posted_seven_by_seven_collection_void()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.is_voided = false
       AND NEW.is_voided = true
       AND EXISTS (
            SELECT 1
            FROM accounting.seven_by_seven_journal_postings posted
            WHERE posted.transaction_id = OLD.id
       ) THEN
        RAISE EXCEPTION 'An accounted 7x7 collection cannot be voided until the protected 7x7 reversal workflow is installed and completes.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_02_seven_by_seven_posted_collection_void_guard
    ON lending.collection_transactions;
CREATE TRIGGER accounting_02_seven_by_seven_posted_collection_void_guard
BEFORE UPDATE OF is_voided ON lending.collection_transactions
FOR EACH ROW EXECUTE FUNCTION accounting.guard_posted_seven_by_seven_collection_void();

CREATE OR REPLACE FUNCTION accounting.post_seven_by_seven_journal(
    p_preparation_id UUID,
    p_actor_user_id UUID,
    p_posting_review_token TEXT,
    p_expected_journal_entry_id UUID,
    p_expected_source_event_key TEXT,
    p_expected_source_event_review_token TEXT,
    p_expected_coordinate_digest TEXT,
    p_expected_posting_date DATE,
    p_expected_fiscal_period_id UUID,
    p_expected_source_cash_amount NUMERIC,
    p_expected_eir_interest_accrual NUMERIC,
    p_expected_accounting_eir_interest_received NUMERIC,
    p_expected_accounting_7x7_principal_received NUMERIC,
    p_expected_coordinate_line_count INTEGER,
    p_expected_total_debit NUMERIC,
    p_expected_total_credit NUMERIC,
    p_posting_policy_version TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    prepared accounting.seven_by_seven_journal_draft_preparations%ROWTYPE;
    existing_post accounting.seven_by_seven_journal_postings%ROWTYPE;
    current_review RECORD;
    current_draft RECORD;
    journal_row accounting.journal_entries%ROWTYPE;
    period_row accounting.fiscal_periods%ROWTYPE;
    normalized_posting_token TEXT := lower(btrim(coalesce(p_posting_review_token, '')));
    normalized_source_key TEXT := btrim(coalesce(p_expected_source_event_key, ''));
    normalized_source_review_token TEXT := lower(btrim(coalesce(p_expected_source_event_review_token, '')));
    normalized_coordinate_digest TEXT := lower(btrim(coalesce(p_expected_coordinate_digest, '')));
    expected_cash NUMERIC(18,2) := round(coalesce(p_expected_source_cash_amount, 0), 2);
    expected_eir_accrual NUMERIC(18,2) := round(coalesce(p_expected_eir_interest_accrual, 0), 2);
    expected_interest_received NUMERIC(18,2) := round(coalesce(p_expected_accounting_eir_interest_received, 0), 2);
    expected_principal_received NUMERIC(18,2) := round(coalesce(p_expected_accounting_7x7_principal_received, 0), 2);
    expected_total_debit NUMERIC(18,2) := round(coalesce(p_expected_total_debit, 0), 2);
    expected_total_credit NUMERIC(18,2) := round(coalesce(p_expected_total_credit, 0), 2);
    current_coordinate_digest TEXT;
    actual_line_count INTEGER;
    actual_total_debit NUMERIC(18,2);
    actual_total_credit NUMERIC(18,2);
    exact_current_line_match_count INTEGER;
    invalid_current_coordinate_count INTEGER;
    source_journal_count INTEGER;
    audit_line_count INTEGER;
    audit_total_debit NUMERIC(18,2);
    audit_total_credit NUMERIC(18,2);
    audit_exact_line_match_count INTEGER;
    entry_number TEXT;
    posting_id UUID;
    inserted_line_count INTEGER;
BEGIN
    IF p_posting_policy_version IS DISTINCT FROM 'seven_by_seven_source_event_journal_posting_v1' THEN
        RAISE EXCEPTION 'Unsupported protected 7x7 journal posting policy version.';
    END IF;
    IF normalized_posting_token !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Protected 7x7 posting review token is invalid.';
    END IF;
    IF normalized_source_review_token !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Protected 7x7 source-event review token is invalid.';
    END IF;
    IF normalized_coordinate_digest !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Protected 7x7 coordinate digest is invalid.';
    END IF;
    IF p_expected_coordinate_line_count IS NULL OR p_expected_coordinate_line_count <= 0 THEN
        RAISE EXCEPTION 'Protected 7x7 posting confirmation requires a positive coordinate line count.';
    END IF;
    IF expected_cash <= 0
       OR expected_eir_accrual < 0
       OR expected_interest_received < 0
       OR expected_principal_received < 0
       OR p_expected_source_cash_amount IS DISTINCT FROM expected_cash
       OR p_expected_eir_interest_accrual IS DISTINCT FROM expected_eir_accrual
       OR p_expected_accounting_eir_interest_received IS DISTINCT FROM expected_interest_received
       OR p_expected_accounting_7x7_principal_received IS DISTINCT FROM expected_principal_received
       OR expected_cash <> expected_interest_received + expected_principal_received
       OR p_expected_total_debit IS DISTINCT FROM expected_total_debit
       OR p_expected_total_credit IS DISTINCT FROM expected_total_credit
       OR expected_total_debit <= 0
       OR expected_total_debit <> expected_total_credit THEN
        RAISE EXCEPTION 'Protected 7x7 posting confirmation contains invalid or unreconciled two-decimal amounts.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended(
            'seven-by-seven-journal-post:' || p_preparation_id::text,
            0
        )
    );

    LOCK TABLE
        lending.collection_transactions,
        lending.loans,
        lending.clients,
        accounting.fiscal_periods,
        accounting.accounts,
        accounting.journal_entries,
        accounting.journal_lines,
        accounting.seven_by_seven_journal_draft_preparations,
        accounting.seven_by_seven_journal_postings,
        accounting.seven_by_seven_journal_posting_lines
    IN SHARE MODE;

    SELECT *
    INTO prepared
    FROM accounting.seven_by_seven_journal_draft_preparations item
    WHERE item.id = p_preparation_id;

    IF prepared.id IS NULL THEN
        RAISE EXCEPTION 'Protected 7x7 journal preparation was not found.';
    END IF;

    IF p_expected_journal_entry_id <> prepared.journal_entry_id
       OR normalized_source_key <> prepared.source_event_key
       OR normalized_source_key <> 'collection:' || prepared.transaction_id::text
       OR normalized_source_review_token <> prepared.source_event_review_token
       OR normalized_coordinate_digest <> prepared.coordinate_digest
       OR prepared.draft_policy_version <> 'seven_by_seven_source_event_journal_draft_v1'
       OR p_expected_posting_date <> prepared.posting_date
       OR p_expected_fiscal_period_id <> prepared.fiscal_period_id
       OR expected_cash <> prepared.source_cash_amount
       OR expected_eir_accrual <> prepared.eir_interest_accrual
       OR expected_interest_received <> prepared.accounting_eir_interest_received
       OR expected_principal_received <> prepared.accounting_7x7_principal_received
       OR p_expected_coordinate_line_count <> prepared.coordinate_line_count
       OR expected_total_debit <> prepared.total_debit
       OR expected_total_credit <> prepared.total_credit THEN
        RAISE EXCEPTION 'Protected 7x7 posting confirmation changed from the immutable draft preparation.';
    END IF;

    SELECT *
    INTO existing_post
    FROM accounting.seven_by_seven_journal_postings posted
    WHERE posted.preparation_id = prepared.id;

    -- Exact retry is permitted only while immutable posting audit, journal and
    -- posting-line snapshots still agree with the original confirmed facts.
    IF existing_post.id IS NOT NULL THEN
        IF existing_post.transaction_id <> prepared.transaction_id
           OR existing_post.loan_id <> prepared.loan_id
           OR existing_post.client_id <> prepared.client_id
           OR existing_post.journal_entry_id <> prepared.journal_entry_id
           OR existing_post.source_event_key <> prepared.source_event_key
           OR existing_post.source_event_review_token <> prepared.source_event_review_token
           OR existing_post.coordinate_digest <> prepared.coordinate_digest
           OR existing_post.posting_review_token <> normalized_posting_token
           OR existing_post.draft_policy_version <> prepared.draft_policy_version
           OR existing_post.posting_policy_version <> p_posting_policy_version
           OR existing_post.posting_date <> prepared.posting_date
           OR existing_post.fiscal_period_id <> prepared.fiscal_period_id
           OR existing_post.source_cash_amount <> prepared.source_cash_amount
           OR existing_post.eir_interest_accrual <> prepared.eir_interest_accrual
           OR existing_post.accounting_eir_interest_received <> prepared.accounting_eir_interest_received
           OR existing_post.accounting_7x7_principal_received <> prepared.accounting_7x7_principal_received
           OR existing_post.coordinate_line_count <> prepared.coordinate_line_count
           OR existing_post.total_debit <> prepared.total_debit
           OR existing_post.total_credit <> prepared.total_credit THEN
            RAISE EXCEPTION 'Existing protected 7x7 posting audit does not match the confirmed posting identity.';
        END IF;

        SELECT *
        INTO journal_row
        FROM accounting.journal_entries journal
        WHERE journal.id = prepared.journal_entry_id;

        IF journal_row.id IS NULL
           OR journal_row.status <> 'posted'
           OR journal_row.entry_number <> existing_post.entry_number
           OR journal_row.source_type <> 'seven_by_seven_collection'
           OR journal_row.source_reference <> prepared.transaction_id::text
           OR journal_row.source_event_key <> prepared.source_event_key
           OR journal_row.posting_date <> prepared.posting_date
           OR journal_row.fiscal_period_id <> prepared.fiscal_period_id THEN
            RAISE EXCEPTION 'Existing protected 7x7 posting audit does not match the posted journal.';
        END IF;

        SELECT
            count(snapshot.line_number)::integer,
            coalesce(sum(snapshot.debit), 0)::numeric(18,2),
            coalesce(sum(snapshot.credit), 0)::numeric(18,2),
            count(snapshot.line_number) FILTER (
                WHERE EXISTS (
                    SELECT 1
                    FROM accounting.journal_lines line
                    JOIN accounting.accounts account ON account.id = line.account_id
                    WHERE line.journal_entry_id = prepared.journal_entry_id
                      AND line.line_number = snapshot.line_number
                      AND line.account_id = snapshot.account_id
                      AND account.system_key = snapshot.account_system_key
                      AND line.debit = snapshot.debit
                      AND line.credit = snapshot.credit
                      AND line.client_id = snapshot.client_id
                      AND line.loan_id = snapshot.loan_id
                )
            )::integer
        INTO
            audit_line_count,
            audit_total_debit,
            audit_total_credit,
            audit_exact_line_match_count
        FROM accounting.seven_by_seven_journal_posting_lines snapshot
        WHERE snapshot.posting_id = existing_post.id;

        IF audit_line_count <> prepared.coordinate_line_count
           OR audit_exact_line_match_count <> prepared.coordinate_line_count
           OR audit_total_debit <> prepared.total_debit
           OR audit_total_credit <> prepared.total_credit THEN
            RAISE EXCEPTION 'Existing protected 7x7 posting audit failed immutable line integrity review.';
        END IF;

        RETURN existing_post.id;
    END IF;

    SELECT *
    INTO current_review
    FROM accounting.seven_by_seven_journal_draft_review review
    WHERE review.transaction_id = prepared.transaction_id;

    IF current_review.transaction_id IS NULL
       OR current_review.draft_review_ready IS DISTINCT FROM true
       OR current_review.loan_id <> prepared.loan_id
       OR current_review.client_id <> prepared.client_id
       OR current_review.source_event_key <> prepared.source_event_key
       OR current_review.source_event_review_token <> prepared.source_event_review_token
       OR current_review.coordinate_digest <> prepared.coordinate_digest
       OR current_review.posting_date <> prepared.posting_date
       OR current_review.fiscal_period_id <> prepared.fiscal_period_id
       OR current_review.source_cash_amount <> prepared.source_cash_amount
       OR current_review.eir_interest_accrual <> prepared.eir_interest_accrual
       OR current_review.accounting_eir_interest_received <> prepared.accounting_eir_interest_received
       OR current_review.accounting_7x7_principal_received <> prepared.accounting_7x7_principal_received
       OR current_review.coordinate_line_count <> prepared.coordinate_line_count
       OR current_review.total_debit <> prepared.total_debit
       OR current_review.total_credit <> prepared.total_credit
       OR current_review.posting_enabled IS DISTINCT FROM false
       OR current_review.automatic_source_posting IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'Current protected 7x7 source evidence or coordinates changed after draft preparation. Refresh Management review.';
    END IF;

    SELECT *
    INTO current_draft
    FROM accounting.seven_by_seven_journal_draft_status status
    WHERE status.preparation_id = prepared.id;

    IF current_draft.preparation_id IS NULL
       OR current_draft.draft_integrity_ready IS DISTINCT FROM true
       OR current_draft.journal_entry_id <> prepared.journal_entry_id
       OR current_draft.source_event_review_token <> prepared.source_event_review_token
       OR current_draft.coordinate_digest <> prepared.coordinate_digest
       OR current_draft.posting_enabled IS DISTINCT FROM false
       OR current_draft.automatic_source_posting IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'Protected 7x7 journal draft is stale or failed final integrity review.';
    END IF;

    SELECT *
    INTO period_row
    FROM accounting.fiscal_periods period
    WHERE period.id = prepared.fiscal_period_id;

    IF period_row.id IS NULL
       OR period_row.status <> 'open'
       OR prepared.posting_date NOT BETWEEN period_row.start_date AND period_row.end_date THEN
        RAISE EXCEPTION 'Protected 7x7 journal can only post into its still-open containing fiscal period.';
    END IF;

    SELECT *
    INTO journal_row
    FROM accounting.journal_entries journal
    WHERE journal.id = prepared.journal_entry_id;

    IF journal_row.id IS NULL
       OR journal_row.status <> 'draft'
       OR journal_row.entry_number IS NOT NULL
       OR journal_row.posted_by_user_id IS NOT NULL
       OR journal_row.posted_at IS NOT NULL
       OR journal_row.source_type <> 'seven_by_seven_collection'
       OR journal_row.source_reference <> prepared.transaction_id::text
       OR journal_row.source_event_key <> prepared.source_event_key
       OR journal_row.posting_date <> prepared.posting_date
       OR journal_row.fiscal_period_id <> prepared.fiscal_period_id THEN
        RAISE EXCEPTION 'Protected 7x7 journal draft identity changed or was posted without the protected posting audit.';
    END IF;

    SELECT count(*)::integer
    INTO source_journal_count
    FROM accounting.journal_entries journal
    WHERE journal.source_event_key = prepared.source_event_key;

    IF source_journal_count <> 1 THEN
        RAISE EXCEPTION 'Protected 7x7 source-event journal identity is no longer unique.';
    END IF;

    SELECT accounting.seven_by_seven_coordinate_digest(prepared.transaction_id)
    INTO current_coordinate_digest;

    IF current_coordinate_digest IS NULL
       OR current_coordinate_digest <> prepared.coordinate_digest THEN
        RAISE EXCEPTION 'Protected 7x7 journal coordinates changed before posting.';
    END IF;

    SELECT
        count(line.id)::integer,
        coalesce(sum(line.debit), 0)::numeric(18,2),
        coalesce(sum(line.credit), 0)::numeric(18,2),
        count(line.id) FILTER (
            WHERE EXISTS (
                SELECT 1
                FROM accounting.seven_by_seven_source_event_journal_coordinate_preview coordinate
                WHERE coordinate.transaction_id = prepared.transaction_id
                  AND coordinate.line_number = line.line_number
                  AND coordinate.account_id = line.account_id
                  AND coordinate.debit = line.debit
                  AND coordinate.credit = line.credit
            )
        )::integer
    INTO
        actual_line_count,
        actual_total_debit,
        actual_total_credit,
        exact_current_line_match_count
    FROM accounting.journal_lines line
    WHERE line.journal_entry_id = prepared.journal_entry_id;

    SELECT count(*)::integer
    INTO invalid_current_coordinate_count
    FROM accounting.seven_by_seven_source_event_journal_coordinate_preview coordinate
    JOIN accounting.accounts account ON account.id = coordinate.account_id
    WHERE coordinate.transaction_id = prepared.transaction_id
      AND (
          coordinate.coordinate_preview_ready IS DISTINCT FROM true
          OR coordinate.journal_lines_enabled IS DISTINCT FROM false
          OR coordinate.automatic_source_posting IS DISTINCT FROM false
          OR account.is_active IS DISTINCT FROM true
          OR account.is_posting IS DISTINCT FROM true
          OR CASE coordinate.journal_component
                WHEN 'eir_accrual_debit' THEN
                    account.system_key <> 'accrued_interest_receivable'
                    OR account.account_type <> 'asset'
                    OR coordinate.debit <= 0 OR coordinate.credit <> 0
                WHEN 'eir_accrual_credit' THEN
                    account.system_key <> 'interest_income_7x7'
                    OR account.account_type <> 'income'
                    OR coordinate.credit <= 0 OR coordinate.debit <> 0
                WHEN 'collection_cash_debit' THEN
                    account.system_key <> 'cash_collector_custody'
                    OR account.account_type <> 'asset'
                    OR coordinate.debit <= 0 OR coordinate.credit <> 0
                WHEN 'collection_eir_interest_credit' THEN
                    account.system_key <> 'accrued_interest_receivable'
                    OR account.account_type <> 'asset'
                    OR coordinate.credit <= 0 OR coordinate.debit <> 0
                WHEN 'collection_7x7_principal_credit' THEN
                    account.system_key <> 'loans_receivable_7x7'
                    OR account.account_type <> 'asset'
                    OR coordinate.credit <= 0 OR coordinate.debit <> 0
                ELSE true
             END
      );

    IF actual_line_count <> prepared.coordinate_line_count
       OR exact_current_line_match_count <> prepared.coordinate_line_count
       OR actual_total_debit <> prepared.total_debit
       OR actual_total_credit <> prepared.total_credit
       OR actual_total_debit <> actual_total_credit
       OR invalid_current_coordinate_count <> 0 THEN
        RAISE EXCEPTION 'Protected 7x7 journal lines no longer match the exact current approved EIR coordinate pattern.';
    END IF;

    -- Migration 0065 permits the protected transition only while this private
    -- transaction-local flag is enabled. The base posting function independently
    -- revalidates the open period, active accounts and journal balance.
    PERFORM set_config('accounting.seven_by_seven_journal_post_allowed', 'on', true);
    SELECT accounting.post_journal_entry(prepared.journal_entry_id, p_actor_user_id)
    INTO entry_number;
    PERFORM set_config('accounting.seven_by_seven_journal_post_allowed', 'off', true);

    PERFORM set_config('accounting.seven_by_seven_journal_post_record_allowed', 'on', true);
    INSERT INTO accounting.seven_by_seven_journal_postings (
        preparation_id,
        transaction_id,
        loan_id,
        client_id,
        journal_entry_id,
        source_event_key,
        source_event_review_token,
        coordinate_digest,
        posting_review_token,
        draft_policy_version,
        posting_policy_version,
        posting_date,
        fiscal_period_id,
        source_cash_amount,
        eir_interest_accrual,
        accounting_eir_interest_received,
        accounting_7x7_principal_received,
        coordinate_line_count,
        total_debit,
        total_credit,
        entry_number,
        posted_by_user_id
    ) VALUES (
        prepared.id,
        prepared.transaction_id,
        prepared.loan_id,
        prepared.client_id,
        prepared.journal_entry_id,
        prepared.source_event_key,
        prepared.source_event_review_token,
        prepared.coordinate_digest,
        normalized_posting_token,
        prepared.draft_policy_version,
        p_posting_policy_version,
        prepared.posting_date,
        prepared.fiscal_period_id,
        prepared.source_cash_amount,
        prepared.eir_interest_accrual,
        prepared.accounting_eir_interest_received,
        prepared.accounting_7x7_principal_received,
        prepared.coordinate_line_count,
        prepared.total_debit,
        prepared.total_credit,
        entry_number,
        p_actor_user_id
    ) RETURNING id INTO posting_id;

    INSERT INTO accounting.seven_by_seven_journal_posting_lines (
        posting_id,
        line_number,
        journal_component,
        account_id,
        account_system_key,
        debit,
        credit,
        client_id,
        loan_id
    )
    SELECT
        posting_id,
        coordinate.line_number,
        coordinate.journal_component,
        coordinate.account_id,
        account.system_key,
        coordinate.debit,
        coordinate.credit,
        prepared.client_id,
        prepared.loan_id
    FROM accounting.seven_by_seven_source_event_journal_coordinate_preview coordinate
    JOIN accounting.accounts account ON account.id = coordinate.account_id
    WHERE coordinate.transaction_id = prepared.transaction_id
      AND coordinate.coordinate_preview_ready
    ORDER BY coordinate.line_number;
    GET DIAGNOSTICS inserted_line_count = ROW_COUNT;

    IF inserted_line_count <> prepared.coordinate_line_count THEN
        RAISE EXCEPTION 'Protected 7x7 posting audit line snapshot is incomplete.';
    END IF;

    PERFORM set_config('accounting.seven_by_seven_journal_post_record_allowed', 'off', true);

    INSERT INTO core.audit_logs (
        actor_user_id,
        action,
        target_type,
        target_id,
        details
    ) VALUES (
        p_actor_user_id,
        'accounting.seven_by_seven_journal.posted',
        'seven_by_seven_journal_posting',
        posting_id,
        jsonb_build_object(
            'preparation_id', prepared.id::text,
            'transaction_id', prepared.transaction_id::text,
            'loan_id', prepared.loan_id::text,
            'journal_entry_id', prepared.journal_entry_id::text,
            'entry_number', entry_number,
            'source_event_key', prepared.source_event_key,
            'source_event_review_token', prepared.source_event_review_token,
            'coordinate_digest', prepared.coordinate_digest,
            'posting_review_token', normalized_posting_token,
            'posting_date', prepared.posting_date,
            'source_cash_amount', prepared.source_cash_amount,
            'eir_interest_accrual', prepared.eir_interest_accrual,
            'accounting_eir_interest_received', prepared.accounting_eir_interest_received,
            'accounting_7x7_principal_received', prepared.accounting_7x7_principal_received,
            'coordinate_line_count', prepared.coordinate_line_count,
            'total_debit', prepared.total_debit,
            'total_credit', prepared.total_credit,
            'explicit_management_posting', true,
            'reversal_enabled', false,
            'automatic_source_posting', false
        )
    );

    RETURN posting_id;
END;
$$;

CREATE OR REPLACE VIEW accounting.seven_by_seven_journal_posting_status AS
WITH actual_line_summary AS (
    SELECT
        prepared.id AS preparation_id,
        count(line.id)::integer AS line_count,
        coalesce(sum(line.debit), 0)::numeric(18,2) AS total_debit,
        coalesce(sum(line.credit), 0)::numeric(18,2) AS total_credit,
        count(line.id) FILTER (
            WHERE EXISTS (
                SELECT 1
                FROM accounting.seven_by_seven_source_event_journal_coordinate_preview coordinate
                WHERE coordinate.transaction_id = prepared.transaction_id
                  AND coordinate.line_number = line.line_number
                  AND coordinate.account_id = line.account_id
                  AND coordinate.debit = line.debit
                  AND coordinate.credit = line.credit
            )
        )::integer AS exact_current_line_match_count
    FROM accounting.seven_by_seven_journal_draft_preparations prepared
    LEFT JOIN accounting.journal_lines line
      ON line.journal_entry_id = prepared.journal_entry_id
    GROUP BY prepared.id
),
current_coordinate_safety AS (
    SELECT
        coordinate.transaction_id,
        count(*)::integer AS coordinate_line_count,
        count(*) FILTER (
            WHERE coordinate.coordinate_preview_ready IS DISTINCT FROM true
               OR coordinate.journal_lines_enabled IS DISTINCT FROM false
               OR coordinate.automatic_source_posting IS DISTINCT FROM false
               OR account.is_active IS DISTINCT FROM true
               OR account.is_posting IS DISTINCT FROM true
               OR CASE coordinate.journal_component
                    WHEN 'eir_accrual_debit' THEN
                        account.system_key <> 'accrued_interest_receivable'
                        OR account.account_type <> 'asset'
                    WHEN 'eir_accrual_credit' THEN
                        account.system_key <> 'interest_income_7x7'
                        OR account.account_type <> 'income'
                    WHEN 'collection_cash_debit' THEN
                        account.system_key <> 'cash_collector_custody'
                        OR account.account_type <> 'asset'
                    WHEN 'collection_eir_interest_credit' THEN
                        account.system_key <> 'accrued_interest_receivable'
                        OR account.account_type <> 'asset'
                    WHEN 'collection_7x7_principal_credit' THEN
                        account.system_key <> 'loans_receivable_7x7'
                        OR account.account_type <> 'asset'
                    ELSE true
                  END
        )::integer AS invalid_coordinate_count
    FROM accounting.seven_by_seven_source_event_journal_coordinate_preview coordinate
    JOIN accounting.accounts account ON account.id = coordinate.account_id
    GROUP BY coordinate.transaction_id
),
audit_line_summary AS (
    SELECT
        posted.id AS posting_id,
        count(snapshot.line_number)::integer AS audit_line_count,
        coalesce(sum(snapshot.debit), 0)::numeric(18,2) AS audit_total_debit,
        coalesce(sum(snapshot.credit), 0)::numeric(18,2) AS audit_total_credit,
        count(snapshot.line_number) FILTER (
            WHERE EXISTS (
                SELECT 1
                FROM accounting.journal_lines line
                JOIN accounting.accounts account ON account.id = line.account_id
                WHERE line.journal_entry_id = posted.journal_entry_id
                  AND line.line_number = snapshot.line_number
                  AND line.account_id = snapshot.account_id
                  AND account.system_key = snapshot.account_system_key
                  AND line.debit = snapshot.debit
                  AND line.credit = snapshot.credit
                  AND line.client_id = snapshot.client_id
                  AND line.loan_id = snapshot.loan_id
            )
        )::integer AS audit_exact_line_match_count
    FROM accounting.seven_by_seven_journal_postings posted
    LEFT JOIN accounting.seven_by_seven_journal_posting_lines snapshot
      ON snapshot.posting_id = posted.id
    GROUP BY posted.id
)
SELECT
    prepared.id AS preparation_id,
    prepared.transaction_id,
    prepared.loan_id,
    prepared.client_id,
    prepared.journal_entry_id,
    prepared.source_event_key,
    prepared.source_event_review_token,
    prepared.coordinate_digest,
    prepared.draft_policy_version,
    prepared.posting_date,
    prepared.fiscal_period_id,
    period.label AS fiscal_period_label,
    period.status AS fiscal_period_status,
    prepared.source_cash_amount,
    prepared.eir_interest_accrual,
    prepared.accounting_eir_interest_received,
    prepared.accounting_7x7_principal_received,
    prepared.coordinate_line_count,
    prepared.total_debit AS prepared_total_debit,
    prepared.total_credit AS prepared_total_credit,
    prepared.prepared_by_user_id,
    prepared.prepared_at,
    journal.status AS journal_status,
    journal.entry_number,
    journal.posted_by_user_id AS journal_posted_by_user_id,
    journal.posted_at AS journal_posted_at,
    actual_line_summary.line_count,
    actual_line_summary.total_debit,
    actual_line_summary.total_credit,
    posted.id AS posting_id,
    posted.posting_review_token,
    posted.posting_policy_version,
    posted.entry_number AS audited_entry_number,
    posted.posted_by_user_id,
    posted.posted_at,
    CASE
        WHEN posted.id IS NULL
         AND current_review.transaction_id IS NOT NULL
         AND current_review.draft_review_ready
         AND current_review.source_event_key = prepared.source_event_key
         AND current_review.source_event_review_token = prepared.source_event_review_token
         AND current_review.coordinate_digest = prepared.coordinate_digest
         AND current_review.posting_date = prepared.posting_date
         AND current_review.fiscal_period_id = prepared.fiscal_period_id
         AND current_review.source_cash_amount = prepared.source_cash_amount
         AND current_review.eir_interest_accrual = prepared.eir_interest_accrual
         AND current_review.accounting_eir_interest_received = prepared.accounting_eir_interest_received
         AND current_review.accounting_7x7_principal_received = prepared.accounting_7x7_principal_received
         AND current_review.coordinate_line_count = prepared.coordinate_line_count
         AND current_review.total_debit = prepared.total_debit
         AND current_review.total_credit = prepared.total_credit
         AND current_draft.draft_integrity_ready
         AND journal.status = 'draft'
         AND journal.entry_number IS NULL
         AND journal.source_type = 'seven_by_seven_collection'
         AND journal.source_reference = prepared.transaction_id::text
         AND journal.source_event_key = prepared.source_event_key
         AND period.status = 'open'
         AND prepared.posting_date BETWEEN period.start_date AND period.end_date
         AND current_coordinate_safety.coordinate_line_count = prepared.coordinate_line_count
         AND current_coordinate_safety.invalid_coordinate_count = 0
         AND actual_line_summary.line_count = prepared.coordinate_line_count
         AND actual_line_summary.exact_current_line_match_count = prepared.coordinate_line_count
         AND actual_line_summary.total_debit = prepared.total_debit
         AND actual_line_summary.total_credit = prepared.total_credit
         AND NOT current_review.posting_enabled
         AND NOT current_review.automatic_source_posting
            THEN true
        ELSE false
    END AS posting_ready,
    CASE
        WHEN posted.id IS NOT NULL
         AND journal.status = 'posted'
         AND journal.entry_number = posted.entry_number
         AND journal.source_type = 'seven_by_seven_collection'
         AND journal.source_reference = prepared.transaction_id::text
         AND journal.source_event_key = posted.source_event_key
         AND posted.preparation_id = prepared.id
         AND posted.transaction_id = prepared.transaction_id
         AND posted.loan_id = prepared.loan_id
         AND posted.client_id = prepared.client_id
         AND posted.journal_entry_id = prepared.journal_entry_id
         AND posted.source_event_key = prepared.source_event_key
         AND posted.source_event_review_token = prepared.source_event_review_token
         AND posted.coordinate_digest = prepared.coordinate_digest
         AND posted.draft_policy_version = prepared.draft_policy_version
         AND posted.posting_policy_version = 'seven_by_seven_source_event_journal_posting_v1'
         AND posted.posting_date = prepared.posting_date
         AND posted.fiscal_period_id = prepared.fiscal_period_id
         AND posted.source_cash_amount = prepared.source_cash_amount
         AND posted.eir_interest_accrual = prepared.eir_interest_accrual
         AND posted.accounting_eir_interest_received = prepared.accounting_eir_interest_received
         AND posted.accounting_7x7_principal_received = prepared.accounting_7x7_principal_received
         AND posted.coordinate_line_count = prepared.coordinate_line_count
         AND posted.total_debit = prepared.total_debit
         AND posted.total_credit = prepared.total_credit
         AND actual_line_summary.line_count = prepared.coordinate_line_count
         AND actual_line_summary.total_debit = prepared.total_debit
         AND actual_line_summary.total_credit = prepared.total_credit
         AND audit_line_summary.audit_line_count = prepared.coordinate_line_count
         AND audit_line_summary.audit_exact_line_match_count = prepared.coordinate_line_count
         AND audit_line_summary.audit_total_debit = prepared.total_debit
         AND audit_line_summary.audit_total_credit = prepared.total_credit
            THEN true
        ELSE false
    END AS posted_audit_exact,
    true AS protected_posting_enabled,
    false AS reversal_enabled,
    false AS automatic_source_posting
FROM accounting.seven_by_seven_journal_draft_preparations prepared
JOIN accounting.journal_entries journal
  ON journal.id = prepared.journal_entry_id
JOIN accounting.fiscal_periods period
  ON period.id = prepared.fiscal_period_id
JOIN actual_line_summary
  ON actual_line_summary.preparation_id = prepared.id
LEFT JOIN accounting.seven_by_seven_journal_draft_review current_review
  ON current_review.transaction_id = prepared.transaction_id
LEFT JOIN accounting.seven_by_seven_journal_draft_status current_draft
  ON current_draft.preparation_id = prepared.id
LEFT JOIN current_coordinate_safety
  ON current_coordinate_safety.transaction_id = prepared.transaction_id
LEFT JOIN accounting.seven_by_seven_journal_postings posted
  ON posted.preparation_id = prepared.id
LEFT JOIN audit_line_summary
  ON audit_line_summary.posting_id = posted.id;

COMMENT ON TABLE accounting.seven_by_seven_journal_postings IS
    'Immutable Management-confirmed protected posting audit for one 7x7 collection source event. Installation creates no posting history; automatic source posting is disabled.';
COMMENT ON TABLE accounting.seven_by_seven_journal_posting_lines IS
    'Immutable exact line snapshots bound to one protected 7x7 posting so later reversal/audit does not depend on mutable current source-preview availability.';
COMMENT ON VIEW accounting.seven_by_seven_journal_posting_status IS
    'Fail-closed protected 7x7 posting readiness and immutable posted-audit status. Posting is explicit Management action; reversal remains disabled and automatic source posting remains off.';

COMMIT;