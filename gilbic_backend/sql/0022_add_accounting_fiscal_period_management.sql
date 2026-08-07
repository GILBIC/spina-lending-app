BEGIN;

INSERT INTO core.permissions (code, description)
VALUES
    ('accounting.period.manage', 'Create, review, reopen, and close accounting fiscal periods')
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission ON permission.code = 'accounting.period.manage'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'accounting_fiscal_periods_no_overlap'
          AND conrelid = 'accounting.fiscal_periods'::regclass
    ) THEN
        ALTER TABLE accounting.fiscal_periods
            ADD CONSTRAINT accounting_fiscal_periods_no_overlap
            EXCLUDE USING gist (
                daterange(start_date, end_date, '[]') WITH &&
            );
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS accounting.fiscal_period_events (
    id BIGSERIAL PRIMARY KEY,
    fiscal_period_id UUID NOT NULL
        REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    event_type TEXT NOT NULL
        CHECK (event_type IN ('created', 'status_changed')),
    from_status TEXT
        CHECK (from_status IS NULL OR from_status IN ('open', 'review', 'closed')),
    to_status TEXT NOT NULL
        CHECK (to_status IN ('open', 'review', 'closed')),
    actor_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (event_type = 'created' AND from_status IS NULL)
        OR
        (event_type = 'status_changed' AND from_status IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS accounting_fiscal_period_events_period_idx
    ON accounting.fiscal_period_events (fiscal_period_id, created_at DESC);

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

CREATE OR REPLACE FUNCTION accounting.create_fiscal_period(
    p_label TEXT,
    p_start_date DATE,
    p_end_date DATE,
    p_actor_user_id UUID
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    created_id UUID;
    normalized_label TEXT;
BEGIN
    normalized_label := btrim(coalesce(p_label, ''));
    IF normalized_label = '' THEN
        RAISE EXCEPTION 'Accounting period label is required.';
    END IF;
    IF p_start_date IS NULL OR p_end_date IS NULL THEN
        RAISE EXCEPTION 'Accounting period start and end dates are required.';
    END IF;
    IF p_end_date < p_start_date THEN
        RAISE EXCEPTION 'Accounting period end date cannot be before the start date.';
    END IF;

    INSERT INTO accounting.fiscal_periods (
        label,
        start_date,
        end_date,
        status
    )
    VALUES (
        normalized_label,
        p_start_date,
        p_end_date,
        'open'
    )
    RETURNING id INTO created_id;

    INSERT INTO accounting.fiscal_period_events (
        fiscal_period_id,
        event_type,
        from_status,
        to_status,
        actor_user_id
    )
    VALUES (
        created_id,
        'created',
        NULL,
        'open',
        p_actor_user_id
    );

    RETURN created_id;
EXCEPTION
    WHEN exclusion_violation THEN
        RAISE EXCEPTION 'Accounting fiscal periods cannot overlap.';
    WHEN unique_violation THEN
        RAISE EXCEPTION 'An accounting period already exists for this date range.';
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
        RAISE EXCEPTION 'Closed accounting periods are immutable.';
    END IF;
    IF period_row.status = normalized_status THEN
        RETURN normalized_status;
    END IF;

    IF period_row.status = 'open' AND normalized_status <> 'review' THEN
        RAISE EXCEPTION 'An open accounting period must move to review before it can be closed.';
    END IF;
    IF period_row.status = 'review' AND normalized_status NOT IN ('open', 'closed') THEN
        RAISE EXCEPTION 'A review accounting period can only be reopened or closed.';
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
            WHEN normalized_status = 'closed' THEN now()
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

COMMIT;
