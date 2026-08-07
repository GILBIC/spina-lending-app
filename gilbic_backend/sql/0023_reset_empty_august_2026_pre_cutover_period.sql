BEGIN;

CREATE TABLE IF NOT EXISTS accounting.pre_cutover_period_reset_audit (
    id BIGSERIAL PRIMARY KEY,
    original_period_id UUID NOT NULL,
    replacement_period_id UUID,
    label TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    previous_status TEXT NOT NULL,
    closed_by_user_id UUID,
    closed_at TIMESTAMPTZ,
    journal_count INTEGER NOT NULL,
    period_events JSONB NOT NULL,
    reset_reason TEXT NOT NULL,
    reset_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION accounting.guard_pre_cutover_reset_audit()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Pre-cutover accounting reset audit records are immutable.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_pre_cutover_reset_audit_guard
    ON accounting.pre_cutover_period_reset_audit;
CREATE TRIGGER accounting_pre_cutover_reset_audit_guard
BEFORE UPDATE OR DELETE ON accounting.pre_cutover_period_reset_audit
FOR EACH ROW EXECUTE FUNCTION accounting.guard_pre_cutover_reset_audit();

DO $$
DECLARE
    period_row accounting.fiscal_periods%ROWTYPE;
    replacement_id UUID;
    event_snapshot JSONB;
    audit_id BIGINT;
    journal_count_value INTEGER;
BEGIN
    SELECT * INTO period_row
    FROM accounting.fiscal_periods
    WHERE label = 'August 2026'
      AND start_date = DATE '2026-08-01'
      AND end_date = DATE '2026-08-31'
      AND status = 'closed'
    LIMIT 1;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    SELECT count(*) INTO journal_count_value
    FROM accounting.journal_entries
    WHERE fiscal_period_id = period_row.id;

    IF journal_count_value <> 0 THEN
        RAISE EXCEPTION 'The August 2026 test period cannot be reset because journal entries exist.';
    END IF;

    SELECT coalesce(
        jsonb_agg(
            jsonb_build_object(
                'event_type', event_type,
                'from_status', from_status,
                'to_status', to_status,
                'actor_user_id', actor_user_id,
                'created_at', created_at
            ) ORDER BY created_at, id
        ),
        '[]'::jsonb
    )
    INTO event_snapshot
    FROM accounting.fiscal_period_events
    WHERE fiscal_period_id = period_row.id;

    INSERT INTO accounting.pre_cutover_period_reset_audit (
        original_period_id,
        label,
        start_date,
        end_date,
        previous_status,
        closed_by_user_id,
        closed_at,
        journal_count,
        period_events,
        reset_reason
    )
    VALUES (
        period_row.id,
        period_row.label,
        period_row.start_date,
        period_row.end_date,
        period_row.status,
        period_row.closed_by_user_id,
        period_row.closed_at,
        journal_count_value,
        event_snapshot,
        'Stage 3 pre-cutover close-flow test reset before General Journal enablement.'
    )
    RETURNING id INTO audit_id;

    DELETE FROM accounting.fiscal_period_events
    WHERE fiscal_period_id = period_row.id;

    DELETE FROM accounting.fiscal_periods
    WHERE id = period_row.id;

    replacement_id := accounting.create_fiscal_period(
        period_row.label,
        period_row.start_date,
        period_row.end_date,
        period_row.closed_by_user_id
    );

    -- The archive row is deliberately updated once inside this migration before
    -- the immutable guard is relied upon by normal application operations.
    ALTER TABLE accounting.pre_cutover_period_reset_audit DISABLE TRIGGER accounting_pre_cutover_reset_audit_guard;
    UPDATE accounting.pre_cutover_period_reset_audit
    SET replacement_period_id = replacement_id
    WHERE id = audit_id;
    ALTER TABLE accounting.pre_cutover_period_reset_audit ENABLE TRIGGER accounting_pre_cutover_reset_audit_guard;
END;
$$;

COMMIT;
