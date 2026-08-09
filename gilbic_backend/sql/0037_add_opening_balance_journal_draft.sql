BEGIN;

INSERT INTO core.permissions (code, description)
VALUES (
    'accounting.opening_balance.prepare',
    'Create one protected opening-balance journal draft from a review-ready workbook without posting it'
)
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code = 'accounting.opening_balance.prepare'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.opening_balance_journal_preparations (
    workbook_id UUID PRIMARY KEY
        REFERENCES accounting.opening_balance_workbooks(id) ON DELETE RESTRICT,
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    prepared_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    prepared_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION accounting.guard_opening_balance_journal_preparation_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(
            current_setting('accounting.opening_balance_prepare_allowed', true),
            ''
       ) = 'on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Opening-balance journal preparation records are immutable and must use the protected preparation function.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_opening_balance_journal_preparation_guard
    ON accounting.opening_balance_journal_preparations;
CREATE TRIGGER accounting_opening_balance_journal_preparation_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.opening_balance_journal_preparations
FOR EACH ROW EXECUTE FUNCTION accounting.guard_opening_balance_journal_preparation_write();

CREATE OR REPLACE FUNCTION accounting.guard_opening_balance_prepared_workbook_reopen()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.status = 'review_ready'
       AND NEW.status = 'draft'
       AND EXISTS (
            SELECT 1
            FROM accounting.opening_balance_journal_preparations prep
            WHERE prep.workbook_id = OLD.id
       ) THEN
        RAISE EXCEPTION 'A workbook with a prepared opening-balance journal draft cannot be reopened. The protected draft must be resolved first.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_opening_balance_prepared_workbook_reopen_guard
    ON accounting.opening_balance_workbooks;
CREATE TRIGGER accounting_opening_balance_prepared_workbook_reopen_guard
BEFORE UPDATE ON accounting.opening_balance_workbooks
FOR EACH ROW EXECUTE FUNCTION accounting.guard_opening_balance_prepared_workbook_reopen();

CREATE OR REPLACE FUNCTION accounting.guard_opening_balance_journal_entry_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.source_type IS DISTINCT FROM 'opening_balance' THEN
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Opening-balance journal drafts cannot be deleted through the general journal.';
    END IF;

    IF OLD.status = 'draft' AND NEW.status = 'posted' THEN
        IF coalesce(
            current_setting('accounting.opening_balance_post_allowed', true),
            ''
        ) <> 'on' THEN
            RAISE EXCEPTION 'Opening-balance journal drafts require the protected opening-balance posting workflow.';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'Opening-balance journal drafts are system generated and cannot be edited.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_opening_balance_journal_entry_guard
    ON accounting.journal_entries;
CREATE TRIGGER accounting_opening_balance_journal_entry_guard
BEFORE UPDATE OR DELETE ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_opening_balance_journal_entry_change();

CREATE OR REPLACE FUNCTION accounting.guard_opening_balance_journal_line_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_entry_id UUID;
    target_source_type TEXT;
BEGIN
    target_entry_id := CASE
        WHEN TG_OP = 'DELETE' THEN OLD.journal_entry_id
        ELSE NEW.journal_entry_id
    END;

    SELECT source_type
    INTO target_source_type
    FROM accounting.journal_entries
    WHERE id = target_entry_id;

    IF target_source_type = 'opening_balance'
       AND coalesce(
            current_setting('accounting.opening_balance_prepare_allowed', true),
            ''
       ) <> 'on' THEN
        RAISE EXCEPTION 'Opening-balance journal lines are system generated and immutable.';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_opening_balance_journal_line_guard
    ON accounting.journal_lines;
CREATE TRIGGER accounting_opening_balance_journal_line_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_lines
FOR EACH ROW EXECUTE FUNCTION accounting.guard_opening_balance_journal_line_change();

CREATE OR REPLACE FUNCTION accounting.create_opening_balance_journal_draft(
    p_workbook_id UUID,
    p_actor_user_id UUID
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    workbook accounting.opening_balance_workbooks%ROWTYPE;
    existing_journal_id UUID;
    target_period_id UUID;
    created_journal_id UUID;
    line_count BIGINT;
    verified_count BIGINT;
    nonzero_line_count BIGINT;
    invalid_account_count BIGINT;
    blocked_count BIGINT;
    total_debit NUMERIC(18,2);
    total_credit NUMERIC(18,2);
BEGIN
    SELECT prep.journal_entry_id
    INTO existing_journal_id
    FROM accounting.opening_balance_journal_preparations prep
    WHERE prep.workbook_id = p_workbook_id;

    IF existing_journal_id IS NOT NULL THEN
        RETURN existing_journal_id;
    END IF;

    SELECT *
    INTO workbook
    FROM accounting.opening_balance_workbooks
    WHERE id = p_workbook_id
    FOR UPDATE;

    IF workbook.id IS NULL THEN
        RAISE EXCEPTION 'Opening-balance workbook was not found.';
    END IF;
    IF workbook.status <> 'review_ready' THEN
        RAISE EXCEPTION 'Opening-balance journal preparation requires a review-ready workbook.';
    END IF;
    IF workbook.profit_loss_policy_confirmed = false THEN
        RAISE EXCEPTION 'Confirm the P&L migration policy before preparing an opening-balance journal.';
    END IF;

    SELECT
        count(*),
        count(*) FILTER (
            WHERE verification_status = 'verified'
              AND (proposed_debit IS NOT NULL OR proposed_credit IS NOT NULL)
              AND nullif(btrim(coalesce(evidence_note, '')), '') IS NOT NULL
        ),
        count(*) FILTER (
            WHERE coalesce(proposed_debit, 0) > 0
               OR coalesce(proposed_credit, 0) > 0
        ),
        coalesce(sum(coalesce(proposed_debit, 0)), 0),
        coalesce(sum(coalesce(proposed_credit, 0)), 0)
    INTO
        line_count,
        verified_count,
        nonzero_line_count,
        total_debit,
        total_credit
    FROM accounting.opening_balance_workbook_lines
    WHERE workbook_id = p_workbook_id;

    IF line_count = 0 OR verified_count <> line_count THEN
        RAISE EXCEPTION 'Every opening-balance workbook line must remain explicitly verified with evidence before journal preparation.';
    END IF;
    IF nonzero_line_count < 2 THEN
        RAISE EXCEPTION 'The opening-balance journal requires at least two nonzero lines.';
    END IF;
    IF total_debit <= 0 OR total_debit <> total_credit THEN
        RAISE EXCEPTION 'The opening-balance workbook must remain exactly balanced before journal preparation.';
    END IF;

    SELECT count(*)
    INTO invalid_account_count
    FROM accounting.opening_balance_workbook_lines line
    JOIN accounting.accounts account ON account.id = line.account_id
    WHERE line.workbook_id = p_workbook_id
      AND (coalesce(line.proposed_debit, 0) > 0 OR coalesce(line.proposed_credit, 0) > 0)
      AND (account.is_active = false OR account.is_posting = false);

    IF invalid_account_count > 0 THEN
        RAISE EXCEPTION 'Opening-balance journal contains an inactive or non-posting account.';
    END IF;

    SELECT id
    INTO target_period_id
    FROM accounting.fiscal_periods
    WHERE status = 'open'
      AND workbook.cutover_date BETWEEN start_date AND end_date
    ORDER BY start_date DESC
    LIMIT 1;

    IF target_period_id IS NULL THEN
        RAISE EXCEPTION 'The opening-balance cutover date must remain inside an open accounting period.';
    END IF;

    SELECT count(*) FILTER (
        WHERE status = 'active' AND readiness_status = 'blocked'
    )
    INTO blocked_count
    FROM accounting.loan_cutover_readiness;

    IF blocked_count > 0 THEN
        RAISE EXCEPTION 'Blocked loan sources must be resolved before opening-balance journal preparation.';
    END IF;

    PERFORM set_config('accounting.opening_balance_prepare_allowed', 'on', true);

    INSERT INTO accounting.journal_entries (
        fiscal_period_id,
        posting_date,
        description,
        status,
        source_type,
        source_reference,
        source_event_key,
        created_by_user_id,
        updated_at
    )
    VALUES (
        target_period_id,
        workbook.cutover_date,
        'Opening balances at accounting cutover ' || workbook.cutover_date::text,
        'draft',
        'opening_balance',
        p_workbook_id::text,
        'opening_balance:' || p_workbook_id::text,
        p_actor_user_id,
        now()
    )
    RETURNING id INTO created_journal_id;

    INSERT INTO accounting.journal_lines (
        journal_entry_id,
        line_number,
        account_id,
        description,
        debit,
        credit
    )
    SELECT
        created_journal_id,
        row_number() OVER (ORDER BY account.code)::integer,
        line.account_id,
        'Verified opening balance: ' || account.code,
        coalesce(line.proposed_debit, 0),
        coalesce(line.proposed_credit, 0)
    FROM accounting.opening_balance_workbook_lines line
    JOIN accounting.accounts account ON account.id = line.account_id
    WHERE line.workbook_id = p_workbook_id
      AND (coalesce(line.proposed_debit, 0) > 0 OR coalesce(line.proposed_credit, 0) > 0)
    ORDER BY account.code;

    INSERT INTO accounting.journal_events (
        journal_entry_id,
        event_type,
        actor_user_id,
        details
    )
    VALUES (
        created_journal_id,
        'draft_created',
        p_actor_user_id,
        jsonb_build_object(
            'source_type', 'opening_balance',
            'workbook_id', p_workbook_id,
            'cutover_date', workbook.cutover_date,
            'line_count', nonzero_line_count,
            'total_debit', total_debit,
            'total_credit', total_credit,
            'posting_enabled', false
        )
    );

    INSERT INTO accounting.opening_balance_journal_preparations (
        workbook_id,
        journal_entry_id,
        prepared_by_user_id
    )
    VALUES (
        p_workbook_id,
        created_journal_id,
        p_actor_user_id
    );

    RETURN created_journal_id;
END;
$$;

CREATE OR REPLACE VIEW accounting.opening_balance_journal_preparation_status AS
SELECT
    workbook.id AS workbook_id,
    workbook.cutover_date,
    workbook.status AS workbook_status,
    prep.journal_entry_id,
    journal.status AS journal_status,
    journal.entry_number,
    journal.created_at AS journal_created_at,
    prep.prepared_by_user_id,
    prep.prepared_at,
    coalesce(lines.line_count, 0)::bigint AS journal_line_count,
    coalesce(lines.total_debit, 0)::numeric(18,2) AS total_debit,
    coalesce(lines.total_credit, 0)::numeric(18,2) AS total_credit,
    (prep.journal_entry_id IS NOT NULL) AS draft_prepared,
    false AS opening_balance_posting_enabled,
    false AS automatic_source_posting_enabled
FROM accounting.opening_balance_workbooks workbook
LEFT JOIN accounting.opening_balance_journal_preparations prep
  ON prep.workbook_id = workbook.id
LEFT JOIN accounting.journal_entries journal
  ON journal.id = prep.journal_entry_id
LEFT JOIN LATERAL (
    SELECT
        count(*) AS line_count,
        coalesce(sum(line.debit), 0) AS total_debit,
        coalesce(sum(line.credit), 0) AS total_credit
    FROM accounting.journal_lines line
    WHERE line.journal_entry_id = prep.journal_entry_id
) lines ON true;

COMMIT;
