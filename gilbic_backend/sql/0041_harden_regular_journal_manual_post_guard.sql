BEGIN;

-- Stage 5D.16 follow-up hardening: SQL three-valued logic means
-- `source_type <> 'manual'` does not reject NULL. Use IS DISTINCT FROM so the
-- manual General Journal can post only entries explicitly identified as manual.
CREATE OR REPLACE FUNCTION accounting.post_manual_journal_entry(
    p_entry_id UUID,
    p_actor_user_id UUID
)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    entry_row accounting.journal_entries%ROWTYPE;
    generated_number TEXT;
BEGIN
    SELECT *
    INTO entry_row
    FROM accounting.journal_entries
    WHERE id = p_entry_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Journal entry was not found.';
    END IF;
    IF entry_row.status <> 'draft'
       OR entry_row.source_type IS DISTINCT FROM 'manual' THEN
        RAISE EXCEPTION 'Only a manual draft journal entry can be posted through the manual General Journal workflow.';
    END IF;

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

COMMIT;
