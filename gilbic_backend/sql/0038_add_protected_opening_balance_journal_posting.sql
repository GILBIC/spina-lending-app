BEGIN;

INSERT INTO core.permissions (code, description)
VALUES (
    'accounting.opening_balance.post',
    'Explicitly post one fully revalidated protected opening-balance journal to the General Ledger'
)
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code = 'accounting.opening_balance.post'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.opening_balance_journal_postings (
    workbook_id UUID PRIMARY KEY
        REFERENCES accounting.opening_balance_workbooks(id) ON DELETE RESTRICT,
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    entry_number TEXT NOT NULL UNIQUE,
    posted_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    posted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION accounting.guard_opening_balance_journal_posting_record_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(
            current_setting('accounting.opening_balance_post_record_allowed', true),
            ''
       ) = 'on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Opening-balance posting records are immutable and must use the protected posting function.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_opening_balance_journal_posting_record_guard
    ON accounting.opening_balance_journal_postings;
CREATE TRIGGER accounting_opening_balance_journal_posting_record_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.opening_balance_journal_postings
FOR EACH ROW EXECUTE FUNCTION accounting.guard_opening_balance_journal_posting_record_write();

CREATE OR REPLACE FUNCTION accounting.post_opening_balance_journal(
    p_workbook_id UUID,
    p_actor_user_id UUID
)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    workbook accounting.opening_balance_workbooks%ROWTYPE;
    prep accounting.opening_balance_journal_preparations%ROWTYPE;
    journal accounting.journal_entries%ROWTYPE;
    existing_post accounting.opening_balance_journal_postings%ROWTYPE;
    period accounting.fiscal_periods%ROWTYPE;
    workbook_line_count BIGINT;
    verified_count BIGINT;
    nonzero_line_count BIGINT;
    invalid_account_count BIGINT;
    blocked_count BIGINT;
    journal_line_count BIGINT;
    journal_invalid_account_count BIGINT;
    journal_to_workbook_mismatch_count BIGINT;
    workbook_to_journal_mismatch_count BIGINT;
    workbook_debit NUMERIC(18,2);
    workbook_credit NUMERIC(18,2);
    journal_debit NUMERIC(18,2);
    journal_credit NUMERIC(18,2);
    generated_number TEXT;
BEGIN
    SELECT *
    INTO workbook
    FROM accounting.opening_balance_workbooks
    WHERE id = p_workbook_id
    FOR UPDATE;

    IF workbook.id IS NULL THEN
        RAISE EXCEPTION 'Opening-balance workbook was not found.';
    END IF;

    SELECT *
    INTO prep
    FROM accounting.opening_balance_journal_preparations
    WHERE workbook_id = p_workbook_id;

    IF prep.workbook_id IS NULL THEN
        RAISE EXCEPTION 'Prepare the protected opening-balance journal draft before posting.';
    END IF;

    SELECT *
    INTO journal
    FROM accounting.journal_entries
    WHERE id = prep.journal_entry_id
    FOR UPDATE;

    IF journal.id IS NULL THEN
        RAISE EXCEPTION 'Prepared opening-balance journal was not found.';
    END IF;

    SELECT *
    INTO existing_post
    FROM accounting.opening_balance_journal_postings
    WHERE workbook_id = p_workbook_id;

    IF journal.status = 'posted' THEN
        IF existing_post.workbook_id IS NOT NULL
           AND existing_post.journal_entry_id = journal.id
           AND existing_post.entry_number = journal.entry_number THEN
            RETURN journal.entry_number;
        END IF;
        RAISE EXCEPTION 'Opening-balance journal is posted without the protected posting audit record.';
    END IF;

    IF existing_post.workbook_id IS NOT NULL THEN
        RAISE EXCEPTION 'Opening-balance posting audit exists but the journal is not posted.';
    END IF;

    IF journal.status <> 'draft'
       OR journal.source_type IS DISTINCT FROM 'opening_balance'
       OR journal.source_reference IS DISTINCT FROM p_workbook_id::text
       OR journal.source_event_key IS DISTINCT FROM 'opening_balance:' || p_workbook_id::text THEN
        RAISE EXCEPTION 'Prepared opening-balance journal identity is invalid.';
    END IF;

    IF workbook.status <> 'review_ready' THEN
        RAISE EXCEPTION 'Opening-balance posting requires a review-ready workbook.';
    END IF;
    IF workbook.profit_loss_policy_confirmed = false THEN
        RAISE EXCEPTION 'Confirm the P&L migration policy before opening-balance posting.';
    END IF;
    IF journal.posting_date IS DISTINCT FROM workbook.cutover_date THEN
        RAISE EXCEPTION 'Opening-balance journal posting date no longer matches the approved cutover date.';
    END IF;

    SELECT
        count(*),
        count(*) FILTER (
            WHERE line.verification_status = 'verified'
              AND (line.proposed_debit IS NOT NULL OR line.proposed_credit IS NOT NULL)
              AND nullif(btrim(coalesce(line.evidence_note, '')), '') IS NOT NULL
        ),
        count(*) FILTER (
            WHERE coalesce(line.proposed_debit, 0) > 0
               OR coalesce(line.proposed_credit, 0) > 0
        ),
        coalesce(sum(coalesce(line.proposed_debit, 0)), 0),
        coalesce(sum(coalesce(line.proposed_credit, 0)), 0),
        count(*) FILTER (
            WHERE (coalesce(line.proposed_debit, 0) > 0 OR coalesce(line.proposed_credit, 0) > 0)
              AND (account.is_active = false OR account.is_posting = false)
        )
    INTO
        workbook_line_count,
        verified_count,
        nonzero_line_count,
        workbook_debit,
        workbook_credit,
        invalid_account_count
    FROM accounting.opening_balance_workbook_lines line
    JOIN accounting.accounts account ON account.id = line.account_id
    WHERE line.workbook_id = p_workbook_id;

    IF workbook_line_count = 0 OR verified_count <> workbook_line_count THEN
        RAISE EXCEPTION 'Every opening-balance workbook line must remain explicitly verified with evidence before posting.';
    END IF;
    IF nonzero_line_count < 2 THEN
        RAISE EXCEPTION 'Opening-balance posting requires at least two nonzero lines.';
    END IF;
    IF workbook_debit <= 0 OR workbook_debit <> workbook_credit THEN
        RAISE EXCEPTION 'Opening-balance workbook must remain exactly balanced before posting.';
    END IF;
    IF invalid_account_count > 0 THEN
        RAISE EXCEPTION 'Opening-balance workbook contains an inactive or non-posting account.';
    END IF;

    SELECT
        count(*),
        coalesce(sum(line.debit), 0),
        coalesce(sum(line.credit), 0),
        count(*) FILTER (
            WHERE account.is_active = false OR account.is_posting = false
        )
    INTO
        journal_line_count,
        journal_debit,
        journal_credit,
        journal_invalid_account_count
    FROM accounting.journal_lines line
    JOIN accounting.accounts account ON account.id = line.account_id
    WHERE line.journal_entry_id = journal.id;

    IF journal_line_count <> nonzero_line_count
       OR journal_line_count < 2
       OR journal_debit <= 0
       OR journal_debit <> journal_credit
       OR journal_debit <> workbook_debit
       OR journal_credit <> workbook_credit THEN
        RAISE EXCEPTION 'Protected opening-balance journal totals no longer match the reviewed workbook.';
    END IF;
    IF journal_invalid_account_count > 0 THEN
        RAISE EXCEPTION 'Protected opening-balance journal contains an inactive or non-posting account.';
    END IF;

    SELECT count(*)
    INTO journal_to_workbook_mismatch_count
    FROM accounting.journal_lines journal_line
    LEFT JOIN accounting.opening_balance_workbook_lines workbook_line
      ON workbook_line.workbook_id = p_workbook_id
     AND workbook_line.account_id = journal_line.account_id
    WHERE journal_line.journal_entry_id = journal.id
      AND (
          workbook_line.account_id IS NULL
          OR (coalesce(workbook_line.proposed_debit, 0) = 0 AND coalesce(workbook_line.proposed_credit, 0) = 0)
          OR journal_line.debit <> coalesce(workbook_line.proposed_debit, 0)
          OR journal_line.credit <> coalesce(workbook_line.proposed_credit, 0)
      );

    SELECT count(*)
    INTO workbook_to_journal_mismatch_count
    FROM accounting.opening_balance_workbook_lines workbook_line
    LEFT JOIN accounting.journal_lines journal_line
      ON journal_line.journal_entry_id = journal.id
     AND journal_line.account_id = workbook_line.account_id
    WHERE workbook_line.workbook_id = p_workbook_id
      AND (coalesce(workbook_line.proposed_debit, 0) > 0 OR coalesce(workbook_line.proposed_credit, 0) > 0)
      AND (
          journal_line.id IS NULL
          OR journal_line.debit <> coalesce(workbook_line.proposed_debit, 0)
          OR journal_line.credit <> coalesce(workbook_line.proposed_credit, 0)
      );

    IF journal_to_workbook_mismatch_count > 0 OR workbook_to_journal_mismatch_count > 0 THEN
        RAISE EXCEPTION 'Protected opening-balance journal lines no longer match the reviewed workbook.';
    END IF;

    SELECT *
    INTO period
    FROM accounting.fiscal_periods
    WHERE id = journal.fiscal_period_id
    FOR UPDATE;

    IF period.id IS NULL
       OR period.status <> 'open'
       OR workbook.cutover_date < period.start_date
       OR workbook.cutover_date > period.end_date THEN
        RAISE EXCEPTION 'Opening-balance journal can only be posted while its cutover accounting period is open.';
    END IF;

    -- Hold a stable source-readiness snapshot through the irreversible journal
    -- commit. These SHARE table locks conflict with the ROW EXCLUSIVE locks that
    -- INSERT/UPDATE/DELETE writers (including collection void/correction paths)
    -- must acquire. A writer that committed first is visible to the check below;
    -- a writer that arrives after these locks must wait until this post commits.
    LOCK TABLE
        lending.loans,
        lending.loan_types,
        lending.loan_collection_state
    IN SHARE MODE;

    SELECT count(*) FILTER (
        WHERE status = 'active' AND readiness_status = 'blocked'
    )
    INTO blocked_count
    FROM accounting.loan_cutover_readiness;

    IF blocked_count > 0 THEN
        RAISE EXCEPTION 'Blocked loan sources must be resolved before opening-balance posting.';
    END IF;

    PERFORM set_config('accounting.opening_balance_post_allowed', 'on', true);
    generated_number := accounting.post_journal_entry(journal.id, p_actor_user_id);

    INSERT INTO accounting.journal_events (
        journal_entry_id,
        event_type,
        actor_user_id,
        details
    )
    VALUES (
        journal.id,
        'posted',
        p_actor_user_id,
        jsonb_build_object(
            'entry_number', generated_number,
            'source_type', 'opening_balance',
            'workbook_id', p_workbook_id,
            'protected_posting', true,
            'automatic_source_posting', false
        )
    );

    PERFORM set_config('accounting.opening_balance_post_record_allowed', 'on', true);
    INSERT INTO accounting.opening_balance_journal_postings (
        workbook_id,
        journal_entry_id,
        entry_number,
        posted_by_user_id
    )
    VALUES (
        p_workbook_id,
        journal.id,
        generated_number,
        p_actor_user_id
    );

    RETURN generated_number;
END;
$$;

CREATE OR REPLACE VIEW accounting.opening_balance_journal_posting_status AS
SELECT
    workbook.id AS workbook_id,
    true AS opening_balance_posting_enabled,
    false AS automatic_source_posting_enabled,
    posting.posted_by_user_id,
    posting.posted_at,
    posting.entry_number AS posted_entry_number,
    (
        prep.journal_entry_id IS NOT NULL
        AND journal.status = 'draft'
        AND posting.workbook_id IS NULL
        AND workbook.status = 'review_ready'
        AND workbook.profit_loss_policy_confirmed = true
        AND journal.posting_date = workbook.cutover_date
        AND workbook_readiness.line_count > 0
        AND workbook_readiness.verified_count = workbook_readiness.line_count
        AND workbook_readiness.nonzero_line_count >= 2
        AND workbook_readiness.total_debit > 0
        AND workbook_readiness.total_debit = workbook_readiness.total_credit
        AND workbook_readiness.invalid_account_count = 0
        AND journal_readiness.line_count = workbook_readiness.nonzero_line_count
        AND journal_readiness.total_debit = workbook_readiness.total_debit
        AND journal_readiness.total_credit = workbook_readiness.total_credit
        AND journal_readiness.invalid_account_count = 0
        AND journal_readiness.journal_to_workbook_mismatch_count = 0
        AND workbook_match.workbook_to_journal_mismatch_count = 0
        AND period_gate.open_period_exists = true
        AND source_gate.blocked_count = 0
    ) AS posting_ready,
    CASE
        WHEN posting.workbook_id IS NOT NULL OR journal.status = 'posted'
            THEN 'Opening-balance journal is already posted.'
        WHEN prep.journal_entry_id IS NULL
            THEN 'Prepare the protected opening-balance journal draft before posting.'
        WHEN journal.status <> 'draft'
            THEN 'Only the protected draft can be posted.'
        WHEN workbook.status <> 'review_ready'
            THEN 'Opening Balance Workbook must remain Review Ready before posting.'
        WHEN workbook.profit_loss_policy_confirmed = false
            THEN 'Confirm the P&L migration policy before posting.'
        WHEN journal.posting_date IS DISTINCT FROM workbook.cutover_date
            THEN 'Journal posting date no longer matches the approved cutover date.'
        WHEN workbook_readiness.line_count = 0
             OR workbook_readiness.verified_count <> workbook_readiness.line_count
            THEN 'Every workbook line must remain explicitly verified with evidence and an amount.'
        WHEN workbook_readiness.nonzero_line_count < 2
            THEN 'Opening-balance posting requires at least two nonzero lines.'
        WHEN workbook_readiness.total_debit <= 0
             OR workbook_readiness.total_debit <> workbook_readiness.total_credit
            THEN 'Reviewed workbook must remain exactly balanced before posting.'
        WHEN workbook_readiness.invalid_account_count > 0
            THEN 'A nonzero workbook line uses an inactive or non-posting account.'
        WHEN journal_readiness.line_count <> workbook_readiness.nonzero_line_count
             OR journal_readiness.total_debit <> workbook_readiness.total_debit
             OR journal_readiness.total_credit <> workbook_readiness.total_credit
             OR journal_readiness.journal_to_workbook_mismatch_count > 0
             OR workbook_match.workbook_to_journal_mismatch_count > 0
            THEN 'Protected journal no longer exactly matches the reviewed workbook.'
        WHEN journal_readiness.invalid_account_count > 0
            THEN 'Protected journal contains an inactive or non-posting account.'
        WHEN period_gate.open_period_exists = false
            THEN 'Cutover accounting period must remain open before posting.'
        WHEN source_gate.blocked_count > 0
            THEN 'Blocked loan sources must be resolved before posting.'
        ELSE NULL
    END AS posting_blocker
FROM accounting.opening_balance_workbooks workbook
LEFT JOIN accounting.opening_balance_journal_preparations prep
  ON prep.workbook_id = workbook.id
LEFT JOIN accounting.journal_entries journal
  ON journal.id = prep.journal_entry_id
LEFT JOIN accounting.opening_balance_journal_postings posting
  ON posting.workbook_id = workbook.id
LEFT JOIN LATERAL (
    SELECT
        count(*) AS line_count,
        coalesce(sum(line.debit), 0)::numeric(18,2) AS total_debit,
        coalesce(sum(line.credit), 0)::numeric(18,2) AS total_credit,
        count(*) FILTER (
            WHERE account.is_active = false OR account.is_posting = false
        ) AS invalid_account_count,
        count(*) FILTER (
            WHERE workbook_line.account_id IS NULL
               OR (coalesce(workbook_line.proposed_debit, 0) = 0 AND coalesce(workbook_line.proposed_credit, 0) = 0)
               OR line.debit <> coalesce(workbook_line.proposed_debit, 0)
               OR line.credit <> coalesce(workbook_line.proposed_credit, 0)
        ) AS journal_to_workbook_mismatch_count
    FROM accounting.journal_lines line
    JOIN accounting.accounts account ON account.id = line.account_id
    LEFT JOIN accounting.opening_balance_workbook_lines workbook_line
      ON workbook_line.workbook_id = workbook.id
     AND workbook_line.account_id = line.account_id
    WHERE line.journal_entry_id = prep.journal_entry_id
) journal_readiness ON true
LEFT JOIN LATERAL (
    SELECT
        count(*) AS line_count,
        count(*) FILTER (
            WHERE line.verification_status = 'verified'
              AND (line.proposed_debit IS NOT NULL OR line.proposed_credit IS NOT NULL)
              AND nullif(btrim(coalesce(line.evidence_note, '')), '') IS NOT NULL
        ) AS verified_count,
        count(*) FILTER (
            WHERE coalesce(line.proposed_debit, 0) > 0
               OR coalesce(line.proposed_credit, 0) > 0
        ) AS nonzero_line_count,
        coalesce(sum(coalesce(line.proposed_debit, 0)), 0)::numeric(18,2) AS total_debit,
        coalesce(sum(coalesce(line.proposed_credit, 0)), 0)::numeric(18,2) AS total_credit,
        count(*) FILTER (
            WHERE (coalesce(line.proposed_debit, 0) > 0 OR coalesce(line.proposed_credit, 0) > 0)
              AND (account.is_active = false OR account.is_posting = false)
        ) AS invalid_account_count
    FROM accounting.opening_balance_workbook_lines line
    JOIN accounting.accounts account ON account.id = line.account_id
    WHERE line.workbook_id = workbook.id
) workbook_readiness ON true
LEFT JOIN LATERAL (
    SELECT count(*) AS workbook_to_journal_mismatch_count
    FROM accounting.opening_balance_workbook_lines workbook_line
    LEFT JOIN accounting.journal_lines journal_line
      ON journal_line.journal_entry_id = prep.journal_entry_id
     AND journal_line.account_id = workbook_line.account_id
    WHERE workbook_line.workbook_id = workbook.id
      AND (coalesce(workbook_line.proposed_debit, 0) > 0 OR coalesce(workbook_line.proposed_credit, 0) > 0)
      AND (
          journal_line.id IS NULL
          OR journal_line.debit <> coalesce(workbook_line.proposed_debit, 0)
          OR journal_line.credit <> coalesce(workbook_line.proposed_credit, 0)
      )
) workbook_match ON true
LEFT JOIN LATERAL (
    SELECT EXISTS (
        SELECT 1
        FROM accounting.fiscal_periods period
        WHERE period.id = journal.fiscal_period_id
          AND period.status = 'open'
          AND workbook.cutover_date BETWEEN period.start_date AND period.end_date
    ) AS open_period_exists
) period_gate ON true
LEFT JOIN LATERAL (
    SELECT count(*) FILTER (
        WHERE readiness.status = 'active'
          AND readiness.readiness_status = 'blocked'
    ) AS blocked_count
    FROM accounting.loan_cutover_readiness readiness
) source_gate ON true;

COMMIT;
