BEGIN;

-- General Journal reversals are immutable copied drafts, not manual edits.
-- Keep generated drafts in their owning posting workflows while allowing the
-- existing separately reviewed reversal workflow to reach the ledger.
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
    original accounting.journal_entries%ROWTYPE;
    reversal_id UUID;
BEGIN
    SELECT * INTO original
    FROM accounting.journal_entries
    WHERE id = p_entry_id
    FOR UPDATE;
    IF NOT FOUND OR original.status <> 'posted' THEN
        RAISE EXCEPTION 'Only a posted journal entry can be reversed.';
    END IF;
    IF original.source_type = 'period_close' THEN
        RAISE EXCEPTION 'A formal period-close journal cannot be reversed; closed periods are immutable in V1.';
    END IF;
    IF original.reversal_of_entry_id IS NOT NULL OR original.source_type = 'reversal' THEN
        RAISE EXCEPTION 'A reversal journal cannot be reversed again. Record any further correction as a new documented journal entry.';
    END IF;
    IF EXISTS (
        SELECT 1 FROM accounting.journal_entries
        WHERE reversal_of_entry_id = p_entry_id
    ) THEN
        RAISE EXCEPTION 'This journal entry already has a reversal.';
    END IF;

    reversal_id := accounting.create_reversal_draft(
        p_entry_id, p_actor_user_id, p_posting_date, p_description
    );
    INSERT INTO accounting.journal_events (
        journal_entry_id, event_type, actor_user_id, details
    ) VALUES (
        reversal_id, 'reversal_created', p_actor_user_id,
        jsonb_build_object('reversal_of_entry_id', p_entry_id)
    );
    RETURN reversal_id;
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
    entry_row accounting.journal_entries%ROWTYPE;
    original accounting.journal_entries%ROWTYPE;
    generated_number TEXT;
    lines_differ BOOLEAN;
BEGIN
    SELECT * INTO entry_row
    FROM accounting.journal_entries
    WHERE id = p_entry_id
    FOR UPDATE;
    IF NOT FOUND OR entry_row.status <> 'draft' THEN
        RAISE EXCEPTION 'Only a draft journal entry can be posted.';
    END IF;

    IF entry_row.source_type = 'reversal' THEN
        SELECT * INTO original
        FROM accounting.journal_entries
        WHERE id = entry_row.reversal_of_entry_id
        FOR UPDATE;
        IF NOT FOUND OR original.status <> 'posted'
           OR original.source_type IN ('period_close', 'reversal')
           OR original.reversal_of_entry_id IS NOT NULL
           OR entry_row.source_event_key IS DISTINCT FROM 'reversal:' || original.id::text
           OR entry_row.source_reference IS DISTINCT FROM original.entry_number
           OR (SELECT count(*) FROM accounting.journal_entries
               WHERE reversal_of_entry_id = original.id) <> 1 THEN
            RAISE EXCEPTION 'Only a linked reversal of an eligible posted original can use this workflow.';
        END IF;

        WITH original_lines AS (
            SELECT line_number, account_id, description, credit AS debit,
                   debit AS credit, client_id, loan_id
            FROM accounting.journal_lines WHERE journal_entry_id = original.id
        ), reversal_lines AS (
            SELECT line_number, account_id, description, debit, credit, client_id, loan_id
            FROM accounting.journal_lines WHERE journal_entry_id = entry_row.id
        )
        SELECT EXISTS (
            (SELECT * FROM original_lines EXCEPT SELECT * FROM reversal_lines)
            UNION ALL
            (SELECT * FROM reversal_lines EXCEPT SELECT * FROM original_lines)
        ) INTO lines_differ;
        IF lines_differ THEN
            RAISE EXCEPTION 'The reversal must retain the exact reversed lines of its posted original.';
        END IF;
    ELSIF entry_row.source_type IS DISTINCT FROM 'manual' THEN
        RAISE EXCEPTION 'Only a manual or reviewed reversal draft can be posted through General Journal; generated drafts remain protected.';
    END IF;

    -- Retain the existing period, balancing, source and immutability checks.
    generated_number := accounting.post_journal_entry(p_entry_id, p_actor_user_id);
    INSERT INTO accounting.journal_events (
        journal_entry_id, event_type, actor_user_id, details
    ) VALUES (
        p_entry_id, 'posted', p_actor_user_id,
        jsonb_build_object('entry_number', generated_number)
    );
    RETURN generated_number;
END;
$$;

COMMIT;
