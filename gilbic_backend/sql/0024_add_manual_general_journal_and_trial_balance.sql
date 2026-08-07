BEGIN;

INSERT INTO core.permissions (code, description)
VALUES
    ('accounting.journal.manage', 'Create, post, reverse, and delete protected manual accounting journal drafts')
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission ON permission.code = 'accounting.journal.manage'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

ALTER TABLE accounting.journal_entries
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE TABLE IF NOT EXISTS accounting.journal_events (
    id BIGSERIAL PRIMARY KEY,
    journal_entry_id UUID NOT NULL
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    event_type TEXT NOT NULL
        CHECK (event_type IN ('draft_created', 'draft_updated', 'draft_deleted', 'posted', 'reversal_created')),
    actor_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS accounting_journal_events_entry_idx
    ON accounting.journal_events (journal_entry_id, created_at DESC);

CREATE OR REPLACE FUNCTION accounting.validate_manual_journal_lines(p_lines JSONB)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    line_count INTEGER;
    invalid_line_count INTEGER;
    invalid_account_count INTEGER;
    total_debit NUMERIC(18,2);
    total_credit NUMERIC(18,2);
BEGIN
    IF jsonb_typeof(p_lines) IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'Journal lines must be an array.';
    END IF;

    SELECT count(*)
    INTO line_count
    FROM jsonb_array_elements(p_lines);

    IF line_count < 2 THEN
        RAISE EXCEPTION 'A manual journal entry requires at least two lines.';
    END IF;

    WITH parsed AS (
        SELECT
            nullif(btrim(item ->> 'account_code'), '') as account_code,
            coalesce((item ->> 'debit')::numeric, 0) as debit,
            coalesce((item ->> 'credit')::numeric, 0) as credit
        FROM jsonb_array_elements(p_lines) item
    )
    SELECT
        count(*) FILTER (
            WHERE account_code IS NULL
               OR debit < 0
               OR credit < 0
               OR NOT ((debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0))
        ),
        coalesce(sum(debit), 0),
        coalesce(sum(credit), 0)
    INTO invalid_line_count, total_debit, total_credit
    FROM parsed;

    IF invalid_line_count > 0 THEN
        RAISE EXCEPTION 'Each journal line requires one active account and exactly one positive debit or credit amount.';
    END IF;

    WITH parsed AS (
        SELECT nullif(btrim(item ->> 'account_code'), '') as account_code
        FROM jsonb_array_elements(p_lines) item
    )
    SELECT count(*)
    INTO invalid_account_count
    FROM parsed
    LEFT JOIN accounting.accounts account
      ON account.code = parsed.account_code
     AND account.is_active = true
     AND account.is_posting = true
    WHERE account.id IS NULL;

    IF invalid_account_count > 0 THEN
        RAISE EXCEPTION 'Journal entry contains an unknown, inactive, or non-posting account.';
    END IF;

    IF total_debit <= 0 OR total_debit <> total_credit THEN
        RAISE EXCEPTION 'Manual journal entry must be balanced before it can be saved.';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.create_manual_journal_draft(
    p_posting_date DATE,
    p_description TEXT,
    p_actor_user_id UUID,
    p_lines JSONB
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    target_period_id UUID;
    created_id UUID;
    normalized_description TEXT;
BEGIN
    normalized_description := btrim(coalesce(p_description, ''));
    IF normalized_description = '' THEN
        RAISE EXCEPTION 'Journal description is required.';
    END IF;

    SELECT id INTO target_period_id
    FROM accounting.fiscal_periods
    WHERE status = 'open'
      AND p_posting_date BETWEEN start_date AND end_date
    ORDER BY start_date DESC
    LIMIT 1;

    IF target_period_id IS NULL THEN
        RAISE EXCEPTION 'No open accounting period contains the journal posting date.';
    END IF;

    PERFORM accounting.validate_manual_journal_lines(p_lines);

    INSERT INTO accounting.journal_entries (
        fiscal_period_id,
        posting_date,
        description,
        status,
        source_type,
        created_by_user_id,
        updated_at
    )
    VALUES (
        target_period_id,
        p_posting_date,
        normalized_description,
        'draft',
        'manual',
        p_actor_user_id,
        now()
    )
    RETURNING id INTO created_id;

    INSERT INTO accounting.journal_lines (
        journal_entry_id,
        line_number,
        account_id,
        description,
        debit,
        credit
    )
    SELECT
        created_id,
        ordinality::integer,
        account.id,
        coalesce(item ->> 'description', ''),
        coalesce((item ->> 'debit')::numeric, 0),
        coalesce((item ->> 'credit')::numeric, 0)
    FROM jsonb_array_elements(p_lines) WITH ORDINALITY parsed(item, ordinality)
    JOIN accounting.accounts account
      ON account.code = nullif(btrim(item ->> 'account_code'), '');

    INSERT INTO accounting.journal_events (
        journal_entry_id, event_type, actor_user_id, details
    )
    VALUES (
        created_id,
        'draft_created',
        p_actor_user_id,
        jsonb_build_object('posting_date', p_posting_date, 'line_count', jsonb_array_length(p_lines))
    );

    RETURN created_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.update_manual_journal_draft(
    p_entry_id UUID,
    p_posting_date DATE,
    p_description TEXT,
    p_actor_user_id UUID,
    p_lines JSONB
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    entry_row accounting.journal_entries%ROWTYPE;
    target_period_id UUID;
    normalized_description TEXT;
BEGIN
    SELECT * INTO entry_row
    FROM accounting.journal_entries
    WHERE id = p_entry_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Journal entry was not found.';
    END IF;
    IF entry_row.status <> 'draft' OR entry_row.source_type <> 'manual' THEN
        RAISE EXCEPTION 'Only a manual draft journal entry can be edited.';
    END IF;

    normalized_description := btrim(coalesce(p_description, ''));
    IF normalized_description = '' THEN
        RAISE EXCEPTION 'Journal description is required.';
    END IF;

    SELECT id INTO target_period_id
    FROM accounting.fiscal_periods
    WHERE status = 'open'
      AND p_posting_date BETWEEN start_date AND end_date
    ORDER BY start_date DESC
    LIMIT 1;

    IF target_period_id IS NULL THEN
        RAISE EXCEPTION 'No open accounting period contains the journal posting date.';
    END IF;

    PERFORM accounting.validate_manual_journal_lines(p_lines);

    UPDATE accounting.journal_entries
    SET fiscal_period_id = target_period_id,
        posting_date = p_posting_date,
        description = normalized_description,
        updated_at = now()
    WHERE id = p_entry_id;

    DELETE FROM accounting.journal_lines
    WHERE journal_entry_id = p_entry_id;

    INSERT INTO accounting.journal_lines (
        journal_entry_id,
        line_number,
        account_id,
        description,
        debit,
        credit
    )
    SELECT
        p_entry_id,
        ordinality::integer,
        account.id,
        coalesce(item ->> 'description', ''),
        coalesce((item ->> 'debit')::numeric, 0),
        coalesce((item ->> 'credit')::numeric, 0)
    FROM jsonb_array_elements(p_lines) WITH ORDINALITY parsed(item, ordinality)
    JOIN accounting.accounts account
      ON account.code = nullif(btrim(item ->> 'account_code'), '');

    INSERT INTO accounting.journal_events (
        journal_entry_id, event_type, actor_user_id, details
    )
    VALUES (
        p_entry_id,
        'draft_updated',
        p_actor_user_id,
        jsonb_build_object('posting_date', p_posting_date, 'line_count', jsonb_array_length(p_lines))
    );
END;
$$;

CREATE OR REPLACE FUNCTION accounting.delete_manual_journal_draft(
    p_entry_id UUID,
    p_actor_user_id UUID
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    entry_row accounting.journal_entries%ROWTYPE;
BEGIN
    SELECT * INTO entry_row
    FROM accounting.journal_entries
    WHERE id = p_entry_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Journal entry was not found.';
    END IF;
    IF entry_row.status <> 'draft' OR entry_row.source_type <> 'manual' THEN
        RAISE EXCEPTION 'Only a manual draft journal entry can be deleted.';
    END IF;

    INSERT INTO accounting.journal_events (
        journal_entry_id, event_type, actor_user_id, details
    )
    VALUES (
        p_entry_id,
        'draft_deleted',
        p_actor_user_id,
        jsonb_build_object('description', entry_row.description, 'posting_date', entry_row.posting_date)
    );

    -- Journal audit history is permanent, so a draft is soft-deleted by converting
    -- it to an immutable audit-only posted shell is intentionally NOT allowed.
    -- Instead the application does not expose draft deletion after this stage.
    RAISE EXCEPTION 'Manual draft deletion is disabled to preserve the permanent journal audit trail.';
END;
$$;

CREATE OR REPLACE FUNCTION accounting.post_manual_journal_entry(
    p_entry_id UUID,
    p_actor_user_id UUID
)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    generated_number TEXT;
BEGIN
    generated_number := accounting.post_journal_entry(p_entry_id, p_actor_user_id);
    INSERT INTO accounting.journal_events (
        journal_entry_id, event_type, actor_user_id, details
    )
    VALUES (
        p_entry_id,
        'posted',
        p_actor_user_id,
        jsonb_build_object('entry_number', generated_number)
    );
    RETURN generated_number;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.create_manual_reversal_draft(
    p_entry_id UUID,
    p_actor_user_id UUID,
    p_posting_date DATE,
    p_description TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    reversal_id UUID;
BEGIN
    reversal_id := accounting.create_reversal_draft(
        p_entry_id,
        p_actor_user_id,
        p_posting_date,
        p_description
    );
    INSERT INTO accounting.journal_events (
        journal_entry_id, event_type, actor_user_id, details
    )
    VALUES (
        reversal_id,
        'reversal_created',
        p_actor_user_id,
        jsonb_build_object('reversal_of_entry_id', p_entry_id)
    );
    RETURN reversal_id;
END;
$$;

COMMIT;
