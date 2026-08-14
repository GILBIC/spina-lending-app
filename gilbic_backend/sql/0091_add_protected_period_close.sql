BEGIN;

-- Master #296 A6.3, slice 1: formal period close and retained earnings.
-- A period must first move from open to review with no unresolved drafts. Review
-- freezes ordinary journal creation/posting. The protected close preparation then
-- snapshots every non-zero income/expense balance and, when needed, prepares one
-- General Journal closing entry that zeros those temporary accounts directly to
-- existing 3100 Retained Earnings. The protected post revalidates the snapshot,
-- posts only that close entry inside the review period, verifies temporary accounts
-- are zero, closes the period atomically, and leaves closed periods immutable.
-- Automatic source posting and period reopening remain disabled.

INSERT INTO core.permissions (code, description)
VALUES
    ('accounting.period.close.prepare', 'Prepare an immutable formal period-close snapshot and retained-earnings closing journal for a reviewed accounting period'),
    ('accounting.period.close.post', 'Post the exact protected retained-earnings close and atomically close the reviewed accounting period')
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code IN (
      'accounting.period.close.prepare',
      'accounting.period.close.post'
  )
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.period_close_preparations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fiscal_period_id UUID NOT NULL UNIQUE
        REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    period_label TEXT NOT NULL CHECK (btrim(period_label) <> ''),
    period_start_date DATE NOT NULL,
    period_end_date DATE NOT NULL,
    close_posting_date DATE NOT NULL,
    journal_entry_id UUID UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    source_event_key TEXT NOT NULL UNIQUE CHECK (btrim(source_event_key) <> ''),
    preclose_posted_journal_count INTEGER NOT NULL CHECK (preclose_posted_journal_count >= 0),
    temporary_account_count INTEGER NOT NULL CHECK (temporary_account_count >= 0),
    temporary_closing_debit_total NUMERIC(18,2) NOT NULL CHECK (temporary_closing_debit_total >= 0),
    temporary_closing_credit_total NUMERIC(18,2) NOT NULL CHECK (temporary_closing_credit_total >= 0),
    net_income NUMERIC(18,2) NOT NULL,
    retained_earnings_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    retained_earnings_balance_before NUMERIC(18,2) NOT NULL,
    close_digest TEXT NOT NULL CHECK (close_digest ~ '^[0-9a-f]{64}$'),
    policy_version TEXT NOT NULL CHECK (policy_version = 'period_close_retained_earnings_v1'),
    prepared_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    prepared_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (period_end_date >= period_start_date),
    CHECK (close_posting_date = period_end_date),
    CHECK (
        (temporary_account_count = 0 AND journal_entry_id IS NULL
         AND temporary_closing_debit_total = 0
         AND temporary_closing_credit_total = 0
         AND net_income = 0)
        OR temporary_account_count > 0
    )
);

CREATE TABLE IF NOT EXISTS accounting.period_close_account_snapshots (
    preparation_id UUID NOT NULL
        REFERENCES accounting.period_close_preparations(id) ON DELETE RESTRICT,
    account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    account_code TEXT NOT NULL CHECK (btrim(account_code) <> ''),
    account_name TEXT NOT NULL CHECK (btrim(account_name) <> ''),
    account_type TEXT NOT NULL CHECK (account_type IN ('income', 'expense')),
    period_debit_total NUMERIC(18,2) NOT NULL CHECK (period_debit_total >= 0),
    period_credit_total NUMERIC(18,2) NOT NULL CHECK (period_credit_total >= 0),
    debit_minus_credit_balance NUMERIC(18,2) NOT NULL CHECK (debit_minus_credit_balance <> 0),
    closing_debit NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (closing_debit >= 0),
    closing_credit NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (closing_credit >= 0),
    line_number INTEGER NOT NULL CHECK (line_number > 0),
    PRIMARY KEY (preparation_id, account_id),
    UNIQUE (preparation_id, account_code),
    UNIQUE (preparation_id, line_number),
    CHECK (
        (closing_debit > 0 AND closing_credit = 0)
        OR (closing_credit > 0 AND closing_debit = 0)
    ),
    CHECK (
        (debit_minus_credit_balance < 0 AND closing_debit = -debit_minus_credit_balance)
        OR
        (debit_minus_credit_balance > 0 AND closing_credit = debit_minus_credit_balance)
    )
);

CREATE TABLE IF NOT EXISTS accounting.period_close_postings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    preparation_id UUID NOT NULL UNIQUE
        REFERENCES accounting.period_close_preparations(id) ON DELETE RESTRICT,
    fiscal_period_id UUID NOT NULL UNIQUE
        REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    journal_entry_id UUID UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    entry_number TEXT,
    confirmation_token TEXT NOT NULL CHECK (confirmation_token ~ '^[0-9a-f]{64}$'),
    confirmation_digest TEXT NOT NULL CHECK (confirmation_digest ~ '^[0-9a-f]{64}$'),
    confirmed_close_digest TEXT NOT NULL CHECK (confirmed_close_digest ~ '^[0-9a-f]{64}$'),
    confirmed_net_income NUMERIC(18,2) NOT NULL,
    confirmed_retained_earnings_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    retained_earnings_balance_before NUMERIC(18,2) NOT NULL,
    retained_earnings_balance_after NUMERIC(18,2) NOT NULL,
    confirmed_period_start_date DATE NOT NULL,
    confirmed_period_end_date DATE NOT NULL,
    policy_version TEXT NOT NULL CHECK (policy_version = 'period_close_retained_earnings_v1'),
    posted_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    closed_at TIMESTAMPTZ NOT NULL,
    posted_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (
        (journal_entry_id IS NULL AND entry_number IS NULL AND confirmed_net_income = 0)
        OR journal_entry_id IS NOT NULL
    )
);

CREATE INDEX IF NOT EXISTS period_close_preparations_period_idx
    ON accounting.period_close_preparations(period_end_date DESC, prepared_at DESC);
CREATE INDEX IF NOT EXISTS period_close_postings_closed_idx
    ON accounting.period_close_postings(closed_at DESC);

CREATE OR REPLACE FUNCTION accounting.guard_period_close_audit_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    insert_allowed BOOLEAN := false;
BEGIN
    IF TG_TABLE_NAME = 'period_close_preparations' THEN
        insert_allowed := coalesce(current_setting('accounting.period_close_preparation_insert_allowed', true), '') = 'on';
    ELSIF TG_TABLE_NAME = 'period_close_account_snapshots' THEN
        insert_allowed := coalesce(current_setting('accounting.period_close_snapshot_insert_allowed', true), '') = 'on';
    ELSIF TG_TABLE_NAME = 'period_close_postings' THEN
        insert_allowed := coalesce(current_setting('accounting.period_close_posting_insert_allowed', true), '') = 'on';
    END IF;

    IF TG_OP = 'INSERT' AND insert_allowed THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Formal period-close preparation, snapshot and posting audit rows are immutable and must use the protected Management close workflow.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_period_close_preparation_guard
    ON accounting.period_close_preparations;
CREATE TRIGGER accounting_period_close_preparation_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.period_close_preparations
FOR EACH ROW EXECUTE FUNCTION accounting.guard_period_close_audit_write();

DROP TRIGGER IF EXISTS accounting_period_close_snapshot_guard
    ON accounting.period_close_account_snapshots;
CREATE TRIGGER accounting_period_close_snapshot_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.period_close_account_snapshots
FOR EACH ROW EXECUTE FUNCTION accounting.guard_period_close_audit_write();

DROP TRIGGER IF EXISTS accounting_period_close_posting_guard
    ON accounting.period_close_postings;
CREATE TRIGGER accounting_period_close_posting_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.period_close_postings
FOR EACH ROW EXECUTE FUNCTION accounting.guard_period_close_audit_write();

CREATE OR REPLACE FUNCTION accounting.require_period_close_management_actor(
    p_actor_user_id UUID,
    p_permission TEXT
)
RETURNS VOID
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    IF p_actor_user_id IS NULL OR NOT EXISTS (
        SELECT 1
        FROM core.users actor
        JOIN core.user_roles user_role ON user_role.user_id = actor.id
        JOIN core.roles role ON role.id = user_role.role_id
        JOIN core.role_permissions role_permission ON role_permission.role_id = role.id
        WHERE actor.id = p_actor_user_id
          AND actor.status = 'active'
          AND role.code = 'management'
          AND role_permission.permission_code = p_permission
    ) THEN
        RAISE EXCEPTION 'An active Management actor with % permission is required.', p_permission;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.guard_period_close_journal_entry_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    reversed_source TEXT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.source_type = 'period_close'
           AND coalesce(current_setting('accounting.period_close_journal_prepare_allowed', true), '') <> 'on' THEN
            RAISE EXCEPTION 'Formal period-close journals must use the protected Management close preparation function.';
        END IF;

        IF NEW.reversal_of_entry_id IS NOT NULL THEN
            SELECT source_type INTO reversed_source
            FROM accounting.journal_entries
            WHERE id = NEW.reversal_of_entry_id;
            IF reversed_source = 'period_close' THEN
                RAISE EXCEPTION 'A formal period-close journal cannot be reversed through the General Journal; closed periods are immutable in V1.';
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.source_type IS DISTINCT FROM 'period_close' THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Formal period-close journals are immutable and cannot be deleted.';
    END IF;

    IF OLD.status = 'draft' AND NEW.status = 'posted'
       AND coalesce(current_setting('accounting.period_close_journal_post_allowed', true), '') = 'on' THEN
        RETURN NEW;
    END IF;

    IF NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'Formal period-close journals are system generated and immutable.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_period_close_journal_entry_guard
    ON accounting.journal_entries;
CREATE TRIGGER accounting_period_close_journal_entry_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_period_close_journal_entry_change();

CREATE OR REPLACE FUNCTION accounting.guard_period_close_journal_line_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_entry UUID;
    target_source TEXT;
BEGIN
    target_entry := CASE WHEN TG_OP = 'DELETE' THEN OLD.journal_entry_id ELSE NEW.journal_entry_id END;
    SELECT source_type INTO target_source
    FROM accounting.journal_entries
    WHERE id = target_entry;

    IF target_source IS DISTINCT FROM 'period_close' THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'INSERT'
       AND coalesce(current_setting('accounting.period_close_journal_prepare_allowed', true), '') = 'on' THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'Formal period-close journal lines are system generated and immutable.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_period_close_journal_line_guard
    ON accounting.journal_lines;
CREATE TRIGGER accounting_period_close_journal_line_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_lines
FOR EACH ROW EXECUTE FUNCTION accounting.guard_period_close_journal_line_change();

-- Fail closed at the journal table itself. No new draft or coordinate change may target
-- a review/closed period. The only review-period exception is the exact protected
-- period-close draft/post lifecycle.
CREATE OR REPLACE FUNCTION accounting.guard_journal_fiscal_period_state()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    period_row accounting.fiscal_periods%ROWTYPE;
    close_prepare BOOLEAN := coalesce(current_setting('accounting.period_close_journal_prepare_allowed', true), '') = 'on';
    close_post BOOLEAN := coalesce(current_setting('accounting.period_close_journal_post_allowed', true), '') = 'on';
BEGIN
    SELECT * INTO period_row
    FROM accounting.fiscal_periods
    WHERE id = NEW.fiscal_period_id;

    IF period_row.id IS NULL THEN
        RAISE EXCEPTION 'Journal accounting period was not found.';
    END IF;
    IF NEW.posting_date NOT BETWEEN period_row.start_date AND period_row.end_date THEN
        RAISE EXCEPTION 'Journal posting date is outside its accounting period.';
    END IF;
    IF period_row.status = 'closed' THEN
        RAISE EXCEPTION 'Closed accounting periods reject all new journal drafts and posting-coordinate changes.';
    END IF;
    IF period_row.status = 'review'
       AND NOT (
            NEW.source_type = 'period_close'
            AND (close_prepare OR close_post)
       ) THEN
        RAISE EXCEPTION 'Accounting periods in review are frozen; only the protected formal close journal is allowed.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_journal_fiscal_period_state_guard
    ON accounting.journal_entries;
CREATE TRIGGER accounting_journal_fiscal_period_state_guard
BEFORE INSERT OR UPDATE ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_journal_fiscal_period_state();

CREATE OR REPLACE FUNCTION accounting.guard_fiscal_period()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.status = 'closed' THEN
        RAISE EXCEPTION 'Closed accounting periods are immutable.';
    END IF;

    IF TG_OP = 'UPDATE'
       AND NEW.status IS DISTINCT FROM OLD.status
       AND coalesce(current_setting('spina.accounting_period_transition', true), '') <> 'on' THEN
        RAISE EXCEPTION 'Accounting period status can only change through the controlled transition function.';
    END IF;

    IF TG_OP = 'UPDATE'
       AND NEW.status = 'closed'
       AND OLD.status IS DISTINCT FROM 'closed'
       AND coalesce(current_setting('accounting.period_close_transition_allowed', true), '') <> 'on' THEN
        RAISE EXCEPTION 'A reviewed accounting period can only close through the protected formal period-close posting function.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM accounting.fiscal_periods other
        WHERE other.id <> NEW.id
          AND daterange(other.start_date, other.end_date, '[]')
              && daterange(NEW.start_date, NEW.end_date, '[]')
    ) THEN
        RAISE EXCEPTION 'Accounting fiscal periods cannot overlap.';
    END IF;

    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.set_fiscal_period_status(
    p_period_id UUID,
    p_new_status TEXT,
    p_actor_user_id UUID
)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    period_row accounting.fiscal_periods%ROWTYPE;
    normalized_status TEXT;
BEGIN
    PERFORM accounting.require_period_close_management_actor(
        p_actor_user_id,
        'accounting.period.manage'
    );

    normalized_status := lower(btrim(coalesce(p_new_status, '')));
    IF normalized_status NOT IN ('open', 'review', 'closed') THEN
        RAISE EXCEPTION 'Unsupported accounting period status.';
    END IF;

    SELECT * INTO period_row
    FROM accounting.fiscal_periods
    WHERE id = p_period_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Accounting period was not found.';
    END IF;
    IF period_row.status = 'closed' THEN
        RAISE EXCEPTION 'Closed accounting periods are immutable and cannot be reopened in V1.';
    END IF;
    IF period_row.status = normalized_status THEN
        RETURN normalized_status;
    END IF;

    IF period_row.status = 'open' AND normalized_status <> 'review' THEN
        RAISE EXCEPTION 'An open accounting period must move to review before it can be closed.';
    END IF;
    IF period_row.status = 'review' AND normalized_status NOT IN ('open', 'closed') THEN
        RAISE EXCEPTION 'A review accounting period can only be reopened before close preparation or closed through the protected close workflow.';
    END IF;

    IF period_row.status = 'open' AND normalized_status = 'review'
       AND EXISTS (
            SELECT 1
            FROM accounting.journal_entries journal
            WHERE journal.fiscal_period_id = p_period_id
              AND journal.status = 'draft'
       ) THEN
        RAISE EXCEPTION 'Accounting period cannot enter review while draft journal entries remain.';
    END IF;

    IF period_row.status = 'review' AND normalized_status = 'open'
       AND EXISTS (
            SELECT 1
            FROM accounting.period_close_preparations preparation
            WHERE preparation.fiscal_period_id = p_period_id
       ) THEN
        RAISE EXCEPTION 'A reviewed period with an immutable close preparation cannot be reopened.';
    END IF;

    IF normalized_status = 'closed'
       AND coalesce(current_setting('accounting.period_close_transition_allowed', true), '') <> 'on' THEN
        RAISE EXCEPTION 'Use the protected formal period-close posting workflow to close a reviewed accounting period.';
    END IF;

    IF normalized_status = 'closed' AND EXISTS (
        SELECT 1
        FROM accounting.journal_entries journal
        WHERE journal.fiscal_period_id = p_period_id
          AND journal.status = 'draft'
    ) THEN
        RAISE EXCEPTION 'Accounting period cannot close while draft journal entries remain.';
    END IF;

    PERFORM set_config('spina.accounting_period_transition', 'on', true);
    UPDATE accounting.fiscal_periods
    SET
        status = normalized_status,
        closed_by_user_id = CASE
            WHEN normalized_status = 'closed' THEN p_actor_user_id
            ELSE NULL
        END,
        closed_at = CASE
            WHEN normalized_status = 'closed' THEN clock_timestamp()
            ELSE NULL
        END
    WHERE id = p_period_id;

    INSERT INTO accounting.fiscal_period_events (
        fiscal_period_id,
        event_type,
        from_status,
        to_status,
        actor_user_id
    )
    VALUES (
        p_period_id,
        'status_changed',
        period_row.status,
        normalized_status,
        p_actor_user_id
    );

    RETURN normalized_status;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.post_journal_entry(
    p_entry_id UUID,
    p_actor_user_id UUID
)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    entry_row accounting.journal_entries%ROWTYPE;
    period_row accounting.fiscal_periods%ROWTYPE;
    line_count INTEGER;
    invalid_account_count INTEGER;
    total_debit NUMERIC(18,2);
    total_credit NUMERIC(18,2);
    generated_number TEXT;
    protected_review_close BOOLEAN;
BEGIN
    SELECT * INTO entry_row
    FROM accounting.journal_entries
    WHERE id = p_entry_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Journal entry was not found.';
    END IF;
    IF entry_row.status <> 'draft' THEN
        RAISE EXCEPTION 'Only a draft journal entry can be posted.';
    END IF;

    SELECT * INTO period_row
    FROM accounting.fiscal_periods
    WHERE id = entry_row.fiscal_period_id
    FOR UPDATE;

    protected_review_close :=
        period_row.status = 'review'
        AND entry_row.source_type = 'period_close'
        AND coalesce(current_setting('accounting.period_close_journal_post_allowed', true), '') = 'on';

    IF period_row.status <> 'open' AND NOT protected_review_close THEN
        RAISE EXCEPTION 'Journal entries can only be posted to an open accounting period, except the protected formal close journal in review.';
    END IF;
    IF entry_row.posting_date < period_row.start_date
       OR entry_row.posting_date > period_row.end_date THEN
        RAISE EXCEPTION 'Journal posting date is outside its accounting period.';
    END IF;

    SELECT
        count(*),
        coalesce(sum(line.debit), 0),
        coalesce(sum(line.credit), 0),
        count(*) FILTER (
            WHERE account.is_active = false OR account.is_posting = false
        )
    INTO line_count, total_debit, total_credit, invalid_account_count
    FROM accounting.journal_lines line
    JOIN accounting.accounts account ON account.id = line.account_id
    WHERE line.journal_entry_id = p_entry_id;

    IF line_count < 2 THEN
        RAISE EXCEPTION 'A journal entry requires at least two lines.';
    END IF;
    IF invalid_account_count > 0 THEN
        RAISE EXCEPTION 'Journal entry contains an inactive or non-posting account.';
    END IF;
    IF total_debit <= 0 OR total_debit <> total_credit THEN
        RAISE EXCEPTION 'Journal entry is not balanced.';
    END IF;

    generated_number := 'JE-'
        || to_char(entry_row.posting_date, 'YYYYMM')
        || '-'
        || lpad(nextval('accounting.journal_number_seq')::text, 8, '0');

    PERFORM set_config('spina.accounting_post', 'on', true);
    UPDATE accounting.journal_entries
    SET
        entry_number = generated_number,
        status = 'posted',
        posted_by_user_id = p_actor_user_id,
        posted_at = clock_timestamp(),
        updated_at = clock_timestamp()
    WHERE id = p_entry_id;

    RETURN generated_number;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.create_reversal_draft(
    p_entry_id UUID,
    p_actor_user_id UUID,
    p_posting_date DATE,
    p_description TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    original accounting.journal_entries%ROWTYPE;
    target_period_id UUID;
    reversal_id UUID;
BEGIN
    SELECT * INTO original
    FROM accounting.journal_entries
    WHERE id = p_entry_id
    FOR SHARE;

    IF NOT FOUND OR original.status <> 'posted' THEN
        RAISE EXCEPTION 'Only a posted journal entry can be reversed.';
    END IF;
    IF original.source_type = 'period_close' THEN
        RAISE EXCEPTION 'A formal period-close journal cannot be reversed; closed periods are immutable in V1.';
    END IF;
    IF EXISTS (
        SELECT 1 FROM accounting.journal_entries
        WHERE reversal_of_entry_id = p_entry_id
    ) THEN
        RAISE EXCEPTION 'This journal entry already has a reversal.';
    END IF;

    SELECT id INTO target_period_id
    FROM accounting.fiscal_periods
    WHERE status = 'open'
      AND p_posting_date BETWEEN start_date AND end_date
    ORDER BY start_date DESC
    LIMIT 1;

    IF target_period_id IS NULL THEN
        RAISE EXCEPTION 'No open accounting period contains the reversal date.';
    END IF;

    INSERT INTO accounting.journal_entries (
        fiscal_period_id,
        posting_date,
        description,
        source_type,
        source_reference,
        source_event_key,
        reversal_of_entry_id,
        created_by_user_id
    )
    VALUES (
        target_period_id,
        p_posting_date,
        btrim(p_description),
        'reversal',
        original.entry_number,
        'reversal:' || original.id::text,
        original.id,
        p_actor_user_id
    )
    RETURNING id INTO reversal_id;

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
        reversal_id,
        line_number,
        account_id,
        description,
        credit,
        debit,
        client_id,
        loan_id
    FROM accounting.journal_lines
    WHERE journal_entry_id = original.id
    ORDER BY line_number;

    RETURN reversal_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.prepare_period_close(
    p_period_id UUID,
    p_actor_user_id UUID
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    period_row accounting.fiscal_periods%ROWTYPE;
    retained_account accounting.accounts%ROWTYPE;
    existing accounting.period_close_preparations%ROWTYPE;
    preparation_id UUID := gen_random_uuid();
    journal_id UUID;
    posted_journal_count INTEGER;
    temp_count INTEGER;
    close_debit_total NUMERIC(18,2);
    close_credit_total NUMERIC(18,2);
    net_income_value NUMERIC(18,2);
    retained_before NUMERIC(18,2);
    digest_source TEXT;
    close_digest_value TEXT;
BEGIN
    PERFORM accounting.require_period_close_management_actor(
        p_actor_user_id,
        'accounting.period.close.prepare'
    );
    PERFORM pg_advisory_xact_lock(hashtextextended('period-close:' || p_period_id::text, 0));

    SELECT * INTO period_row
    FROM accounting.fiscal_periods
    WHERE id = p_period_id
    FOR UPDATE;
    IF period_row.id IS NULL THEN
        RAISE EXCEPTION 'Accounting period was not found.';
    END IF;

    SELECT * INTO existing
    FROM accounting.period_close_preparations preparation
    WHERE preparation.fiscal_period_id = p_period_id;
    IF existing.id IS NOT NULL THEN
        RETURN existing.id;
    END IF;

    IF period_row.status <> 'review' THEN
        RAISE EXCEPTION 'Formal period-close preparation requires the accounting period to be in review.';
    END IF;
    IF EXISTS (
        SELECT 1 FROM accounting.journal_entries journal
        WHERE journal.fiscal_period_id = p_period_id
          AND journal.status = 'draft'
    ) THEN
        RAISE EXCEPTION 'Formal period-close preparation requires all journal drafts to be resolved first.';
    END IF;

    SELECT * INTO retained_account
    FROM accounting.accounts account
    WHERE account.system_key = 'retained_earnings';
    IF retained_account.id IS NULL
       OR retained_account.code <> '3100'
       OR retained_account.account_type <> 'equity'
       OR retained_account.normal_balance <> 'credit'
       OR NOT retained_account.is_active
       OR NOT retained_account.is_posting THEN
        RAISE EXCEPTION 'Exact active posting account 3100 Retained Earnings is required for formal period close.';
    END IF;

    SELECT count(*)::integer INTO posted_journal_count
    FROM accounting.journal_entries journal
    WHERE journal.fiscal_period_id = p_period_id
      AND journal.status = 'posted';

    WITH balances AS (
        SELECT
            account.id,
            account.code,
            account.name,
            account.account_type,
            coalesce(sum(line.debit), 0)::numeric(18,2) AS debit_total,
            coalesce(sum(line.credit), 0)::numeric(18,2) AS credit_total,
            (coalesce(sum(line.debit), 0) - coalesce(sum(line.credit), 0))::numeric(18,2) AS balance
        FROM accounting.accounts account
        LEFT JOIN accounting.journal_lines line ON line.account_id = account.id
        LEFT JOIN accounting.journal_entries journal
          ON journal.id = line.journal_entry_id
         AND journal.status = 'posted'
         AND journal.fiscal_period_id = p_period_id
         AND journal.source_type IS DISTINCT FROM 'period_close'
        WHERE account.account_type IN ('income', 'expense')
          AND account.is_active
          AND account.is_posting
        GROUP BY account.id
    ), nonzero AS (
        SELECT * FROM balances WHERE balance <> 0
    )
    SELECT
        count(*)::integer,
        coalesce(sum(CASE WHEN balance < 0 THEN -balance ELSE 0 END), 0)::numeric(18,2),
        coalesce(sum(CASE WHEN balance > 0 THEN balance ELSE 0 END), 0)::numeric(18,2),
        coalesce(sum(CASE WHEN balance < 0 THEN -balance ELSE 0 END), 0)::numeric(18,2)
          - coalesce(sum(CASE WHEN balance > 0 THEN balance ELSE 0 END), 0)::numeric(18,2),
        coalesce(string_agg(
            code || ':' || account_type || ':'
            || to_char(debit_total, 'FM999999999999990.00') || ':'
            || to_char(credit_total, 'FM999999999999990.00') || ':'
            || to_char(balance, 'FM999999999999990.00'),
            '|' ORDER BY code
        ), '')
    INTO temp_count, close_debit_total, close_credit_total, net_income_value, digest_source
    FROM nonzero;

    SELECT coalesce(sum(line.credit - line.debit), 0)::numeric(18,2)
    INTO retained_before
    FROM accounting.journal_lines line
    JOIN accounting.journal_entries journal ON journal.id = line.journal_entry_id
    WHERE line.account_id = retained_account.id
      AND journal.status = 'posted'
      AND journal.posting_date <= period_row.end_date;

    close_digest_value := encode(sha256(convert_to(concat_ws('|',
        'period_close_retained_earnings_v1',
        period_row.id::text,
        period_row.label,
        period_row.start_date::text,
        period_row.end_date::text,
        posted_journal_count::text,
        temp_count::text,
        to_char(close_debit_total, 'FM999999999999990.00'),
        to_char(close_credit_total, 'FM999999999999990.00'),
        to_char(net_income_value, 'FM999999999999990.00'),
        retained_account.id::text,
        to_char(retained_before, 'FM999999999999990.00'),
        digest_source
    ), 'UTF8')), 'hex');

    IF temp_count > 0 THEN
        PERFORM set_config('accounting.period_close_journal_prepare_allowed', 'on', true);
        INSERT INTO accounting.journal_entries(
            fiscal_period_id, posting_date, description, status,
            source_type, source_reference, source_event_key,
            created_by_user_id, updated_at
        ) VALUES (
            period_row.id,
            period_row.end_date,
            'Formal period close - ' || period_row.label,
            'draft',
            'period_close',
            period_row.id::text,
            'period_close:' || period_row.id::text,
            p_actor_user_id,
            clock_timestamp()
        ) RETURNING id INTO journal_id;

        WITH balances AS (
            SELECT
                account.id,
                account.code,
                (coalesce(sum(line.debit), 0) - coalesce(sum(line.credit), 0))::numeric(18,2) AS balance
            FROM accounting.accounts account
            LEFT JOIN accounting.journal_lines line ON line.account_id = account.id
            LEFT JOIN accounting.journal_entries journal
              ON journal.id = line.journal_entry_id
             AND journal.status = 'posted'
             AND journal.fiscal_period_id = p_period_id
             AND journal.source_type IS DISTINCT FROM 'period_close'
            WHERE account.account_type IN ('income', 'expense')
              AND account.is_active
              AND account.is_posting
            GROUP BY account.id
        ), numbered AS (
            SELECT *, row_number() OVER (ORDER BY code)::integer AS line_number
            FROM balances
            WHERE balance <> 0
        )
        INSERT INTO accounting.journal_lines(
            journal_entry_id, line_number, account_id, description,
            debit, credit
        )
        SELECT
            journal_id,
            line_number,
            id,
            'Close temporary account to Retained Earnings',
            CASE WHEN balance < 0 THEN -balance ELSE 0 END,
            CASE WHEN balance > 0 THEN balance ELSE 0 END
        FROM numbered
        ORDER BY line_number;

        IF net_income_value <> 0 THEN
            INSERT INTO accounting.journal_lines(
                journal_entry_id, line_number, account_id, description,
                debit, credit
            ) VALUES (
                journal_id,
                temp_count + 1,
                retained_account.id,
                'Transfer period profit or loss to Retained Earnings',
                CASE WHEN net_income_value < 0 THEN -net_income_value ELSE 0 END,
                CASE WHEN net_income_value > 0 THEN net_income_value ELSE 0 END
            );
        END IF;
        PERFORM set_config('accounting.period_close_journal_prepare_allowed', 'off', true);
    END IF;

    PERFORM set_config('accounting.period_close_preparation_insert_allowed', 'on', true);
    INSERT INTO accounting.period_close_preparations(
        id, fiscal_period_id, period_label, period_start_date, period_end_date,
        close_posting_date, journal_entry_id, source_event_key,
        preclose_posted_journal_count, temporary_account_count,
        temporary_closing_debit_total, temporary_closing_credit_total,
        net_income, retained_earnings_account_id, retained_earnings_balance_before,
        close_digest, policy_version, prepared_by_user_id
    ) VALUES (
        preparation_id, period_row.id, period_row.label, period_row.start_date,
        period_row.end_date, period_row.end_date, journal_id,
        'period_close:' || period_row.id::text,
        posted_journal_count, temp_count, close_debit_total, close_credit_total,
        net_income_value, retained_account.id, retained_before,
        close_digest_value, 'period_close_retained_earnings_v1', p_actor_user_id
    );
    PERFORM set_config('accounting.period_close_preparation_insert_allowed', 'off', true);

    PERFORM set_config('accounting.period_close_snapshot_insert_allowed', 'on', true);
    WITH balances AS (
        SELECT
            account.id,
            account.code,
            account.name,
            account.account_type,
            coalesce(sum(line.debit), 0)::numeric(18,2) AS debit_total,
            coalesce(sum(line.credit), 0)::numeric(18,2) AS credit_total,
            (coalesce(sum(line.debit), 0) - coalesce(sum(line.credit), 0))::numeric(18,2) AS balance
        FROM accounting.accounts account
        LEFT JOIN accounting.journal_lines line ON line.account_id = account.id
        LEFT JOIN accounting.journal_entries journal
          ON journal.id = line.journal_entry_id
         AND journal.status = 'posted'
         AND journal.fiscal_period_id = p_period_id
         AND journal.source_type IS DISTINCT FROM 'period_close'
        WHERE account.account_type IN ('income', 'expense')
          AND account.is_active
          AND account.is_posting
        GROUP BY account.id
    ), numbered AS (
        SELECT *, row_number() OVER (ORDER BY code)::integer AS line_number
        FROM balances WHERE balance <> 0
    )
    INSERT INTO accounting.period_close_account_snapshots(
        preparation_id, account_id, account_code, account_name, account_type,
        period_debit_total, period_credit_total, debit_minus_credit_balance,
        closing_debit, closing_credit, line_number
    )
    SELECT
        preparation_id, id, code, name, account_type,
        debit_total, credit_total, balance,
        CASE WHEN balance < 0 THEN -balance ELSE 0 END,
        CASE WHEN balance > 0 THEN balance ELSE 0 END,
        line_number
    FROM numbered
    ORDER BY line_number;
    PERFORM set_config('accounting.period_close_snapshot_insert_allowed', 'off', true);

    IF journal_id IS NOT NULL THEN
        INSERT INTO accounting.journal_events(journal_entry_id, event_type, actor_user_id, details)
        VALUES (
            journal_id,
            'draft_created',
            p_actor_user_id,
            jsonb_build_object(
                'source_type', 'period_close',
                'fiscal_period_id', period_row.id,
                'net_income', net_income_value,
                'close_digest', close_digest_value,
                'automatic_source_posting', false
            )
        );
    END IF;

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.period_close.prepared',
        'fiscal_period',
        period_row.id,
        jsonb_build_object(
            'preparation_id', preparation_id,
            'journal_entry_id', journal_id,
            'temporary_account_count', temp_count,
            'net_income', net_income_value,
            'retained_earnings_balance_before', retained_before,
            'close_digest', close_digest_value,
            'automatic_source_posting', false
        )
    );

    RETURN preparation_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.post_period_close(
    p_period_id UUID,
    p_actor_user_id UUID,
    p_confirmation_token TEXT,
    p_expected_close_digest TEXT,
    p_expected_net_income NUMERIC,
    p_expected_retained_earnings_account_code TEXT,
    p_expected_period_end_date DATE,
    p_policy_version TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    period_row accounting.fiscal_periods%ROWTYPE;
    preparation accounting.period_close_preparations%ROWTYPE;
    existing accounting.period_close_postings%ROWTYPE;
    retained_account accounting.accounts%ROWTYPE;
    normalized_token TEXT := lower(btrim(coalesce(p_confirmation_token, '')));
    normalized_digest TEXT := lower(btrim(coalesce(p_expected_close_digest, '')));
    normalized_re_code TEXT := btrim(coalesce(p_expected_retained_earnings_account_code, ''));
    current_posted_count INTEGER;
    current_temp_count INTEGER;
    current_close_debit NUMERIC(18,2);
    current_close_credit NUMERIC(18,2);
    current_net_income NUMERIC(18,2);
    current_retained_before NUMERIC(18,2);
    mismatch_count INTEGER;
    expected_line_count INTEGER;
    actual_line_count INTEGER;
    line_debit NUMERIC(18,2);
    line_credit NUMERIC(18,2);
    entry_number_value TEXT;
    remaining_temp_count INTEGER;
    retained_after NUMERIC(18,2);
    confirmation_digest_value TEXT;
    closed_timestamp TIMESTAMPTZ;
    posting_id UUID;
BEGIN
    PERFORM accounting.require_period_close_management_actor(
        p_actor_user_id,
        'accounting.period.close.post'
    );
    IF normalized_token !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Formal period-close confirmation token is invalid.';
    END IF;
    IF normalized_digest !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Formal period-close evidence digest is invalid.';
    END IF;
    IF p_policy_version IS DISTINCT FROM 'period_close_retained_earnings_v1' THEN
        RAISE EXCEPTION 'Unsupported formal period-close policy version.';
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended('period-close:' || p_period_id::text, 0));

    SELECT * INTO preparation
    FROM accounting.period_close_preparations item
    WHERE item.fiscal_period_id = p_period_id;
    IF preparation.id IS NULL THEN
        RAISE EXCEPTION 'Formal period-close preparation was not found.';
    END IF;

    SELECT * INTO existing
    FROM accounting.period_close_postings posting
    WHERE posting.fiscal_period_id = p_period_id;
    IF existing.id IS NOT NULL THEN
        IF existing.confirmation_token = normalized_token
           AND existing.confirmed_close_digest = normalized_digest
           AND existing.confirmed_net_income = round(p_expected_net_income, 2)
           AND existing.confirmed_period_end_date = p_expected_period_end_date
           AND existing.policy_version = p_policy_version THEN
            RETURN existing.id;
        END IF;
        RAISE EXCEPTION 'Formal period close is already posted with different confirmation coordinates.';
    END IF;

    SELECT * INTO period_row
    FROM accounting.fiscal_periods
    WHERE id = p_period_id
    FOR UPDATE;
    IF period_row.id IS NULL OR period_row.status <> 'review' THEN
        RAISE EXCEPTION 'Formal period-close posting requires the exact accounting period to remain in review.';
    END IF;
    IF period_row.start_date <> preparation.period_start_date
       OR period_row.end_date <> preparation.period_end_date
       OR period_row.label <> preparation.period_label
       OR period_row.end_date <> p_expected_period_end_date THEN
        RAISE EXCEPTION 'Accounting period coordinates changed after formal close preparation.';
    END IF;

    SELECT * INTO retained_account
    FROM accounting.accounts account
    WHERE account.id = preparation.retained_earnings_account_id
    FOR SHARE;
    IF retained_account.id IS NULL
       OR retained_account.code <> '3100'
       OR retained_account.code <> normalized_re_code
       OR retained_account.system_key <> 'retained_earnings'
       OR retained_account.account_type <> 'equity'
       OR retained_account.normal_balance <> 'credit'
       OR NOT retained_account.is_active
       OR NOT retained_account.is_posting THEN
        RAISE EXCEPTION 'Exact 3100 Retained Earnings account is no longer posting-ready.';
    END IF;
    IF preparation.close_digest <> normalized_digest
       OR preparation.net_income <> round(p_expected_net_income, 2) THEN
        RAISE EXCEPTION 'Formal period-close confirmation does not match the immutable preparation snapshot.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM accounting.journal_entries journal
        WHERE journal.fiscal_period_id = p_period_id
          AND journal.status = 'draft'
          AND journal.id IS DISTINCT FROM preparation.journal_entry_id
    ) THEN
        RAISE EXCEPTION 'Unexpected journal draft exists after formal close preparation.';
    END IF;

    SELECT count(*)::integer INTO current_posted_count
    FROM accounting.journal_entries journal
    WHERE journal.fiscal_period_id = p_period_id
      AND journal.status = 'posted'
      AND journal.source_type IS DISTINCT FROM 'period_close';

    WITH balances AS (
        SELECT
            account.id,
            coalesce(sum(line.debit), 0)::numeric(18,2) AS debit_total,
            coalesce(sum(line.credit), 0)::numeric(18,2) AS credit_total,
            (coalesce(sum(line.debit), 0) - coalesce(sum(line.credit), 0))::numeric(18,2) AS balance
        FROM accounting.accounts account
        LEFT JOIN accounting.journal_lines line ON line.account_id = account.id
        LEFT JOIN accounting.journal_entries journal
          ON journal.id = line.journal_entry_id
         AND journal.status = 'posted'
         AND journal.fiscal_period_id = p_period_id
         AND journal.source_type IS DISTINCT FROM 'period_close'
        WHERE account.account_type IN ('income', 'expense')
          AND account.is_active
          AND account.is_posting
        GROUP BY account.id
    ), nonzero AS (SELECT * FROM balances WHERE balance <> 0)
    SELECT
        count(*)::integer,
        coalesce(sum(CASE WHEN balance < 0 THEN -balance ELSE 0 END), 0)::numeric(18,2),
        coalesce(sum(CASE WHEN balance > 0 THEN balance ELSE 0 END), 0)::numeric(18,2),
        coalesce(sum(CASE WHEN balance < 0 THEN -balance ELSE 0 END), 0)::numeric(18,2)
          - coalesce(sum(CASE WHEN balance > 0 THEN balance ELSE 0 END), 0)::numeric(18,2)
    INTO current_temp_count, current_close_debit, current_close_credit, current_net_income
    FROM nonzero;

    SELECT coalesce(sum(line.credit - line.debit), 0)::numeric(18,2)
    INTO current_retained_before
    FROM accounting.journal_lines line
    JOIN accounting.journal_entries journal ON journal.id = line.journal_entry_id
    WHERE line.account_id = retained_account.id
      AND journal.status = 'posted'
      AND journal.posting_date <= period_row.end_date;

    IF current_posted_count <> preparation.preclose_posted_journal_count
       OR current_temp_count <> preparation.temporary_account_count
       OR current_close_debit <> preparation.temporary_closing_debit_total
       OR current_close_credit <> preparation.temporary_closing_credit_total
       OR current_net_income <> preparation.net_income
       OR current_retained_before <> preparation.retained_earnings_balance_before THEN
        RAISE EXCEPTION 'Posted ledger balances changed after formal period-close preparation.';
    END IF;

    WITH balances AS (
        SELECT
            account.id,
            coalesce(sum(line.debit), 0)::numeric(18,2) AS debit_total,
            coalesce(sum(line.credit), 0)::numeric(18,2) AS credit_total,
            (coalesce(sum(line.debit), 0) - coalesce(sum(line.credit), 0))::numeric(18,2) AS balance
        FROM accounting.accounts account
        LEFT JOIN accounting.journal_lines line ON line.account_id = account.id
        LEFT JOIN accounting.journal_entries journal
          ON journal.id = line.journal_entry_id
         AND journal.status = 'posted'
         AND journal.fiscal_period_id = p_period_id
         AND journal.source_type IS DISTINCT FROM 'period_close'
        WHERE account.account_type IN ('income', 'expense')
          AND account.is_active
          AND account.is_posting
        GROUP BY account.id
    )
    SELECT count(*)::integer INTO mismatch_count
    FROM accounting.period_close_account_snapshots snapshot
    FULL JOIN balances balance ON balance.id = snapshot.account_id
    WHERE snapshot.preparation_id = preparation.id
      AND (
          balance.id IS NULL
          OR balance.balance = 0
          OR snapshot.period_debit_total <> balance.debit_total
          OR snapshot.period_credit_total <> balance.credit_total
          OR snapshot.debit_minus_credit_balance <> balance.balance
      );
    IF mismatch_count <> 0 THEN
        RAISE EXCEPTION 'Temporary-account close snapshot no longer matches the posted ledger.';
    END IF;

    IF preparation.journal_entry_id IS NOT NULL THEN
        SELECT count(*)::integer,
               coalesce(sum(line.debit), 0)::numeric(18,2),
               coalesce(sum(line.credit), 0)::numeric(18,2)
        INTO actual_line_count, line_debit, line_credit
        FROM accounting.journal_lines line
        WHERE line.journal_entry_id = preparation.journal_entry_id;

        expected_line_count := preparation.temporary_account_count
            + CASE WHEN preparation.net_income <> 0 THEN 1 ELSE 0 END;
        IF actual_line_count <> expected_line_count
           OR line_debit <> line_credit
           OR line_debit <= 0 THEN
            RAISE EXCEPTION 'Prepared formal period-close journal is no longer exactly balanced.';
        END IF;

        SELECT count(*)::integer INTO mismatch_count
        FROM accounting.period_close_account_snapshots snapshot
        LEFT JOIN accounting.journal_lines line
          ON line.journal_entry_id = preparation.journal_entry_id
         AND line.account_id = snapshot.account_id
         AND line.line_number = snapshot.line_number
        WHERE snapshot.preparation_id = preparation.id
          AND (
              line.id IS NULL
              OR line.debit <> snapshot.closing_debit
              OR line.credit <> snapshot.closing_credit
              OR line.client_id IS NOT NULL
              OR line.loan_id IS NOT NULL
          );
        IF mismatch_count <> 0 THEN
            RAISE EXCEPTION 'Prepared temporary-account closing lines changed after formal close preparation.';
        END IF;

        IF preparation.net_income <> 0 AND NOT EXISTS (
            SELECT 1
            FROM accounting.journal_lines line
            WHERE line.journal_entry_id = preparation.journal_entry_id
              AND line.account_id = retained_account.id
              AND line.line_number = preparation.temporary_account_count + 1
              AND line.debit = CASE WHEN preparation.net_income < 0 THEN -preparation.net_income ELSE 0 END
              AND line.credit = CASE WHEN preparation.net_income > 0 THEN preparation.net_income ELSE 0 END
              AND line.client_id IS NULL
              AND line.loan_id IS NULL
        ) THEN
            RAISE EXCEPTION 'Prepared Retained Earnings close line changed after formal close preparation.';
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM accounting.journal_entries journal
            WHERE journal.id = preparation.journal_entry_id
              AND journal.status = 'draft'
              AND journal.source_type = 'period_close'
              AND journal.source_reference = p_period_id::text
              AND journal.source_event_key = preparation.source_event_key
              AND journal.fiscal_period_id = p_period_id
              AND journal.posting_date = preparation.close_posting_date
              AND journal.reversal_of_entry_id IS NULL
        ) THEN
            RAISE EXCEPTION 'Prepared formal period-close General Journal draft changed after preparation.';
        END IF;

        PERFORM set_config('accounting.period_close_journal_post_allowed', 'on', true);
        entry_number_value := accounting.post_journal_entry(
            preparation.journal_entry_id,
            p_actor_user_id
        );
        PERFORM set_config('accounting.period_close_journal_post_allowed', 'off', true);

        INSERT INTO accounting.journal_events(journal_entry_id, event_type, actor_user_id, details)
        VALUES (
            preparation.journal_entry_id,
            'posted',
            p_actor_user_id,
            jsonb_build_object(
                'entry_number', entry_number_value,
                'source_type', 'period_close',
                'fiscal_period_id', p_period_id,
                'net_income', preparation.net_income,
                'close_digest', preparation.close_digest,
                'automatic_source_posting', false
            )
        );
    ELSE
        IF preparation.temporary_account_count <> 0 OR preparation.net_income <> 0 THEN
            RAISE EXCEPTION 'Formal zero-activity close preparation is inconsistent.';
        END IF;
    END IF;

    IF coalesce(current_setting('accounting.period_close_force_audit_failure', true), '') = 'on' THEN
        RAISE EXCEPTION 'Forced formal period-close audit failure.';
    END IF;

    SELECT count(*)::integer INTO remaining_temp_count
    FROM accounting.accounts account
    WHERE account.account_type IN ('income', 'expense')
      AND account.is_active
      AND account.is_posting
      AND (
          SELECT coalesce(sum(line.debit - line.credit), 0)
          FROM accounting.journal_lines line
          JOIN accounting.journal_entries journal ON journal.id = line.journal_entry_id
          WHERE line.account_id = account.id
            AND journal.status = 'posted'
            AND journal.fiscal_period_id = p_period_id
      ) <> 0;
    IF remaining_temp_count <> 0 THEN
        RAISE EXCEPTION 'Formal period close failed: one or more temporary income/expense accounts remain non-zero.';
    END IF;

    SELECT coalesce(sum(line.credit - line.debit), 0)::numeric(18,2)
    INTO retained_after
    FROM accounting.journal_lines line
    JOIN accounting.journal_entries journal ON journal.id = line.journal_entry_id
    WHERE line.account_id = retained_account.id
      AND journal.status = 'posted'
      AND journal.posting_date <= period_row.end_date;
    IF retained_after <> preparation.retained_earnings_balance_before + preparation.net_income THEN
        RAISE EXCEPTION 'Retained Earnings after close does not reconcile to the immutable pre-close balance plus period profit or loss.';
    END IF;

    confirmation_digest_value := encode(sha256(convert_to(concat_ws('|',
        p_policy_version,
        preparation.id::text,
        p_period_id::text,
        preparation.close_digest,
        to_char(preparation.net_income, 'FM999999999999990.00'),
        retained_account.id::text,
        to_char(preparation.retained_earnings_balance_before, 'FM999999999999990.00'),
        to_char(retained_after, 'FM999999999999990.00'),
        preparation.period_start_date::text,
        preparation.period_end_date::text,
        coalesce(preparation.journal_entry_id::text, 'no-journal'),
        coalesce(entry_number_value, 'no-entry-number'),
        normalized_token
    ), 'UTF8')), 'hex');

    PERFORM set_config('accounting.period_close_transition_allowed', 'on', true);
    PERFORM accounting.set_fiscal_period_status(p_period_id, 'closed', p_actor_user_id);
    PERFORM set_config('accounting.period_close_transition_allowed', 'off', true);

    SELECT closed_at INTO closed_timestamp
    FROM accounting.fiscal_periods
    WHERE id = p_period_id;

    PERFORM set_config('accounting.period_close_posting_insert_allowed', 'on', true);
    INSERT INTO accounting.period_close_postings(
        preparation_id, fiscal_period_id, journal_entry_id, entry_number,
        confirmation_token, confirmation_digest, confirmed_close_digest,
        confirmed_net_income, confirmed_retained_earnings_account_id,
        retained_earnings_balance_before, retained_earnings_balance_after,
        confirmed_period_start_date, confirmed_period_end_date,
        policy_version, posted_by_user_id, closed_at
    ) VALUES (
        preparation.id, p_period_id, preparation.journal_entry_id, entry_number_value,
        normalized_token, confirmation_digest_value, preparation.close_digest,
        preparation.net_income, retained_account.id,
        preparation.retained_earnings_balance_before, retained_after,
        preparation.period_start_date, preparation.period_end_date,
        p_policy_version, p_actor_user_id, closed_timestamp
    ) RETURNING id INTO posting_id;
    PERFORM set_config('accounting.period_close_posting_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.period_close.posted',
        'fiscal_period',
        p_period_id,
        jsonb_build_object(
            'preparation_id', preparation.id,
            'posting_id', posting_id,
            'journal_entry_id', preparation.journal_entry_id,
            'entry_number', entry_number_value,
            'net_income', preparation.net_income,
            'retained_earnings_balance_before', preparation.retained_earnings_balance_before,
            'retained_earnings_balance_after', retained_after,
            'confirmation_digest', confirmation_digest_value,
            'closed_at', closed_timestamp,
            'period_reopen_enabled', false,
            'automatic_source_posting', false
        )
    );

    RETURN posting_id;
END;
$$;

CREATE OR REPLACE VIEW accounting.period_close_queue AS
SELECT
    period.id AS fiscal_period_id,
    period.label,
    period.start_date,
    period.end_date,
    period.status AS fiscal_period_status,
    period.closed_by_user_id,
    period.closed_at,
    preparation.id AS preparation_id,
    preparation.journal_entry_id,
    preparation.temporary_account_count,
    preparation.net_income,
    preparation.retained_earnings_balance_before,
    preparation.close_digest,
    posting.id AS close_posting_id,
    posting.entry_number AS closing_entry_number,
    posting.retained_earnings_balance_after,
    CASE
        WHEN period.status = 'closed' AND posting.id IS NOT NULL THEN 'closed_protected'
        WHEN period.status = 'closed' THEN 'closed_legacy_without_protected_close_audit'
        WHEN period.status = 'open' AND draft_state.draft_count > 0 THEN 'blocked_open_drafts'
        WHEN period.status = 'open' THEN 'ready_for_review'
        WHEN period.status = 'review' AND preparation.id IS NULL AND draft_state.draft_count > 0 THEN 'blocked_review_drafts'
        WHEN period.status = 'review' AND preparation.id IS NULL THEN 'ready_to_prepare'
        WHEN period.status = 'review' AND preparation.id IS NOT NULL THEN 'prepared_confirmation_required'
        ELSE 'blocked_unknown_state'
    END AS close_status,
    CASE
        WHEN period.status = 'closed' AND posting.id IS NOT NULL THEN NULL
        WHEN period.status = 'closed' THEN 'This period predates protected A6.3 close audit; it remains immutable and is not retroactively rewritten.'
        WHEN period.status = 'open' AND draft_state.draft_count > 0 THEN 'Resolve every journal draft before moving the period to review.'
        WHEN period.status = 'open' THEN 'Move the period to review to freeze ordinary posting before formal close preparation.'
        WHEN period.status = 'review' AND preparation.id IS NULL AND draft_state.draft_count > 0 THEN 'Unexpected review-period drafts must be resolved before close preparation.'
        WHEN period.status = 'review' AND preparation.id IS NOT NULL THEN 'Exact Management confirmation is required to post retained earnings and atomically close the period.'
        ELSE NULL
    END AS close_blocker,
    true AS protected_period_close_enabled,
    true AS retained_earnings_close_enabled,
    true AS closed_period_posting_protection_enabled,
    false AS period_reopen_enabled,
    false AS automatic_source_posting
FROM accounting.fiscal_periods period
LEFT JOIN accounting.period_close_preparations preparation
  ON preparation.fiscal_period_id = period.id
LEFT JOIN accounting.period_close_postings posting
  ON posting.fiscal_period_id = period.id
LEFT JOIN LATERAL (
    SELECT count(*)::integer AS draft_count
    FROM accounting.journal_entries journal
    WHERE journal.fiscal_period_id = period.id
      AND journal.status = 'draft'
) draft_state ON true;

CREATE OR REPLACE VIEW accounting.period_close_summary AS
SELECT
    count(*)::bigint AS period_count,
    count(*) FILTER (WHERE close_status = 'ready_for_review')::bigint AS ready_for_review_count,
    count(*) FILTER (WHERE close_status = 'ready_to_prepare')::bigint AS ready_to_prepare_count,
    count(*) FILTER (WHERE close_status = 'prepared_confirmation_required')::bigint AS prepared_count,
    count(*) FILTER (WHERE close_status = 'closed_protected')::bigint AS protected_closed_count,
    count(*) FILTER (WHERE close_status LIKE 'blocked_%')::bigint AS blocked_count,
    coalesce(sum(net_income) FILTER (WHERE close_status = 'closed_protected'), 0)::numeric(18,2) AS closed_net_income_total,
    true AS protected_period_close_enabled,
    true AS retained_earnings_close_enabled,
    true AS closed_period_posting_protection_enabled,
    false AS period_reopen_enabled,
    false AS automatic_source_posting
FROM accounting.period_close_queue;

COMMENT ON TABLE accounting.period_close_preparations IS
'Immutable A6.3 formal period-close snapshot prepared only after an accounting period is frozen in review. It records exact temporary-account balances, net profit/loss and pre-close 3100 Retained Earnings.';
COMMENT ON TABLE accounting.period_close_account_snapshots IS
'Immutable per-income/expense-account balances and exact deterministic closing coordinates retained by one formal period-close preparation.';
COMMENT ON TABLE accounting.period_close_postings IS
'Immutable protected close audit proving the exact closing journal, Retained Earnings movement and atomic reviewed-to-closed period transition.';
COMMENT ON VIEW accounting.period_close_queue IS
'A6.3 formal close readiness/control queue. Review freezes ordinary posting; closed periods reject drafts/postings and cannot reopen in V1. automatic_source_posting=false.';

COMMIT;
