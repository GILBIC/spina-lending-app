BEGIN;

INSERT INTO core.permissions (code, description)
VALUES
    (
        'accounting.renewal_boundary_eir_journal.prepare',
        'Create immutable protected renewal-boundary EIR journal drafts from an exact Management-reviewed greenfield Regular reconciliation without posting them'
    ),
    (
        'accounting.renewal_boundary_eir_journal.post',
        'Explicitly post an exact protected renewal-boundary EIR journal review set after Management confirmation'
    )
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code IN (
      'accounting.renewal_boundary_eir_journal.prepare',
      'accounting.renewal_boundary_eir_journal.post'
  )
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.renewal_boundary_eir_journal_preparations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    renewal_execution_event_id UUID NOT NULL UNIQUE
        REFERENCES lending.loan_renewal_execution_events(id) ON DELETE RESTRICT,
    old_loan_id UUID NOT NULL
        REFERENCES lending.loans(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL
        REFERENCES lending.clients(id) ON DELETE RESTRICT,
    target_date DATE NOT NULL,
    review_token TEXT NOT NULL,
    boundary_policy_version TEXT NOT NULL,
    draft_policy_version TEXT NOT NULL,
    expected_entry_count INTEGER NOT NULL CHECK (expected_entry_count > 0),
    total_amount NUMERIC(18,2) NOT NULL CHECK (total_amount > 0),
    prepared_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    prepared_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (review_token ~ '^[0-9a-f]{64}$'),
    CHECK (boundary_policy_version = 'greenfield_regular_renewal_boundary_eir_v1'),
    CHECK (draft_policy_version = 'renewal_boundary_eir_journal_draft_v1')
);

CREATE INDEX IF NOT EXISTS renewal_boundary_eir_journal_preparations_loan_idx
    ON accounting.renewal_boundary_eir_journal_preparations
       (old_loan_id, target_date DESC, prepared_at DESC);

CREATE TABLE IF NOT EXISTS accounting.renewal_boundary_eir_journal_preparation_entries (
    preparation_id UUID NOT NULL
        REFERENCES accounting.renewal_boundary_eir_journal_preparations(id)
        ON DELETE RESTRICT,
    sequence_order INTEGER NOT NULL CHECK (sequence_order > 0),
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    fiscal_period_id UUID NOT NULL
        REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    posting_date DATE NOT NULL,
    amount NUMERIC(18,2) NOT NULL CHECK (amount > 0),
    source_reference TEXT NOT NULL,
    source_event_key TEXT NOT NULL UNIQUE,
    debit_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    credit_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    PRIMARY KEY (preparation_id, sequence_order),
    CHECK (btrim(source_reference) <> ''),
    CHECK (btrim(source_event_key) <> ''),
    CHECK (debit_account_id <> credit_account_id)
);

CREATE TABLE IF NOT EXISTS accounting.renewal_boundary_eir_journal_posting_sets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    preparation_id UUID NOT NULL UNIQUE
        REFERENCES accounting.renewal_boundary_eir_journal_preparations(id)
        ON DELETE RESTRICT,
    renewal_execution_event_id UUID NOT NULL UNIQUE
        REFERENCES lending.loan_renewal_execution_events(id) ON DELETE RESTRICT,
    old_loan_id UUID NOT NULL
        REFERENCES lending.loans(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL
        REFERENCES lending.clients(id) ON DELETE RESTRICT,
    review_token TEXT NOT NULL,
    posting_policy_version TEXT NOT NULL,
    expected_entry_count INTEGER NOT NULL CHECK (expected_entry_count > 0),
    posted_entry_count INTEGER NOT NULL CHECK (posted_entry_count > 0),
    total_debit NUMERIC(18,2) NOT NULL CHECK (total_debit > 0),
    total_credit NUMERIC(18,2) NOT NULL CHECK (total_credit > 0),
    posted_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    posted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (review_token ~ '^[0-9a-f]{64}$'),
    CHECK (posting_policy_version = 'renewal_boundary_eir_journal_posting_v1'),
    CHECK (posted_entry_count = expected_entry_count),
    CHECK (total_debit = total_credit)
);

CREATE TABLE IF NOT EXISTS accounting.renewal_boundary_eir_journal_posting_entries (
    posting_set_id UUID NOT NULL
        REFERENCES accounting.renewal_boundary_eir_journal_posting_sets(id)
        ON DELETE RESTRICT,
    preparation_id UUID NOT NULL
        REFERENCES accounting.renewal_boundary_eir_journal_preparations(id)
        ON DELETE RESTRICT,
    sequence_order INTEGER NOT NULL CHECK (sequence_order > 0),
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    entry_number TEXT NOT NULL UNIQUE,
    source_event_key TEXT NOT NULL UNIQUE,
    PRIMARY KEY (posting_set_id, sequence_order),
    UNIQUE (preparation_id, sequence_order)
);

CREATE OR REPLACE FUNCTION accounting.guard_renewal_boundary_eir_preparation_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(
            current_setting('accounting.renewal_boundary_eir_prepare_allowed', true),
            ''
       ) = 'on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Protected renewal-boundary EIR journal preparation records are immutable and must use the protected preparation function.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_renewal_boundary_eir_preparation_guard
    ON accounting.renewal_boundary_eir_journal_preparations;
CREATE TRIGGER accounting_renewal_boundary_eir_preparation_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.renewal_boundary_eir_journal_preparations
FOR EACH ROW EXECUTE FUNCTION accounting.guard_renewal_boundary_eir_preparation_write();

DROP TRIGGER IF EXISTS accounting_renewal_boundary_eir_preparation_entry_guard
    ON accounting.renewal_boundary_eir_journal_preparation_entries;
CREATE TRIGGER accounting_renewal_boundary_eir_preparation_entry_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.renewal_boundary_eir_journal_preparation_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_renewal_boundary_eir_preparation_write();

CREATE OR REPLACE FUNCTION accounting.guard_renewal_boundary_eir_posting_audit_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(
            current_setting('accounting.renewal_boundary_eir_post_record_allowed', true),
            ''
       ) = 'on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Protected renewal-boundary EIR posting audit records are immutable and must use the protected posting function.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_renewal_boundary_eir_posting_set_guard
    ON accounting.renewal_boundary_eir_journal_posting_sets;
CREATE TRIGGER accounting_renewal_boundary_eir_posting_set_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.renewal_boundary_eir_journal_posting_sets
FOR EACH ROW EXECUTE FUNCTION accounting.guard_renewal_boundary_eir_posting_audit_write();

DROP TRIGGER IF EXISTS accounting_renewal_boundary_eir_posting_entry_guard
    ON accounting.renewal_boundary_eir_journal_posting_entries;
CREATE TRIGGER accounting_renewal_boundary_eir_posting_entry_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.renewal_boundary_eir_journal_posting_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_renewal_boundary_eir_posting_audit_write();

CREATE OR REPLACE FUNCTION accounting.guard_renewal_boundary_eir_system_journal_entry_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    protected_entry BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM accounting.renewal_boundary_eir_journal_preparation_entries prepared
        WHERE prepared.journal_entry_id = OLD.id
    ) INTO protected_entry;

    IF NOT protected_entry THEN
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR journal entries cannot be deleted.';
    END IF;

    IF OLD.status = 'draft' AND NEW.status = 'posted' THEN
        IF coalesce(
            current_setting('accounting.renewal_boundary_eir_journal_post_allowed', true),
            ''
        ) <> 'on' THEN
            RAISE EXCEPTION 'Protected renewal-boundary EIR drafts require the protected Management-confirmed posting workflow.';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR journal entries are system generated and immutable.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_renewal_boundary_eir_system_journal_entry_guard
    ON accounting.journal_entries;
CREATE TRIGGER accounting_renewal_boundary_eir_system_journal_entry_guard
BEFORE UPDATE OR DELETE ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_renewal_boundary_eir_system_journal_entry_change();

CREATE OR REPLACE FUNCTION accounting.guard_renewal_boundary_eir_system_journal_line_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_entry_id UUID;
    protected_entry BOOLEAN;
BEGIN
    target_entry_id := CASE
        WHEN TG_OP = 'DELETE' THEN OLD.journal_entry_id
        ELSE NEW.journal_entry_id
    END;
    SELECT EXISTS (
        SELECT 1
        FROM accounting.renewal_boundary_eir_journal_preparation_entries prepared
        WHERE prepared.journal_entry_id = target_entry_id
    ) INTO protected_entry;

    IF protected_entry THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR journal lines are system generated and immutable.';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_renewal_boundary_eir_system_journal_line_guard
    ON accounting.journal_lines;
CREATE TRIGGER accounting_renewal_boundary_eir_system_journal_line_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_lines
FOR EACH ROW EXECUTE FUNCTION accounting.guard_renewal_boundary_eir_system_journal_line_change();

CREATE OR REPLACE FUNCTION accounting.guard_renewal_boundary_eir_manual_reversal_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.reversal_of_entry_id IS NOT NULL
       AND EXISTS (
           SELECT 1
           FROM accounting.renewal_boundary_eir_journal_preparation_entries prepared
           WHERE prepared.journal_entry_id = NEW.reversal_of_entry_id
       )
       AND coalesce(
            current_setting('accounting.renewal_boundary_eir_reversal_allowed', true),
            ''
       ) <> 'on' THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR journals cannot use the generic/manual reversal workflow; a controlled protected reversal is required.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_renewal_boundary_eir_manual_reversal_guard
    ON accounting.journal_entries;
CREATE TRIGGER accounting_renewal_boundary_eir_manual_reversal_guard
BEFORE INSERT ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_renewal_boundary_eir_manual_reversal_insert();

CREATE OR REPLACE FUNCTION lending.guard_renewal_execution_boundary_eir_history_void()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.is_voided = false
       AND NEW.is_voided = true
       AND (
           EXISTS (
               SELECT 1
               FROM accounting.renewal_boundary_eir_journal_preparations prepared
               WHERE prepared.renewal_execution_event_id = OLD.id
           )
           OR EXISTS (
               SELECT 1
               FROM accounting.journal_entries journal
               WHERE journal.source_event_key LIKE
                   'renewal_eir_accrual:' || OLD.id::text || ':fiscal_period:%'
           )
       ) THEN
        RAISE EXCEPTION 'Renewal execution evidence has protected renewal-boundary EIR journal history; use a controlled accounting reversal/cancellation before voiding the execution evidence.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_renewal_execution_boundary_eir_history_void_guard
    ON lending.loan_renewal_execution_events;
CREATE TRIGGER lending_renewal_execution_boundary_eir_history_void_guard
BEFORE UPDATE OF is_voided ON lending.loan_renewal_execution_events
FOR EACH ROW EXECUTE FUNCTION lending.guard_renewal_execution_boundary_eir_history_void();

CREATE OR REPLACE FUNCTION accounting.create_renewal_boundary_eir_journal_draft_batch(
    p_renewal_execution_event_id UUID,
    p_actor_user_id UUID,
    p_review_token TEXT,
    p_boundary_policy_version TEXT,
    p_draft_policy_version TEXT,
    p_expected_total_amount NUMERIC,
    p_entries JSONB
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    execution_row lending.loan_renewal_execution_events%ROWTYPE;
    existing_preparation accounting.renewal_boundary_eir_journal_preparations%ROWTYPE;
    preparation_id UUID;
    created_journal_id UUID;
    entry_item JSONB;
    expected_count INTEGER;
    normalized_review_token TEXT := lower(btrim(coalesce(p_review_token, '')));
    expected_total NUMERIC(18,2) := round(coalesce(p_expected_total_amount, 0), 2);
    actual_total NUMERIC(18,2);
    invalid_count INTEGER;
    duplicate_count INTEGER;
    debit_account_id UUID;
    credit_account_id UUID;
    entry_sequence INTEGER;
    entry_period_id UUID;
    entry_posting_date DATE;
    entry_amount NUMERIC(18,2);
    entry_source_reference TEXT;
    entry_source_event_key TEXT;
BEGIN
    IF p_boundary_policy_version IS DISTINCT FROM 'greenfield_regular_renewal_boundary_eir_v1' THEN
        RAISE EXCEPTION 'Unsupported renewal-boundary EIR evidence policy version.';
    END IF;
    IF p_draft_policy_version IS DISTINCT FROM 'renewal_boundary_eir_journal_draft_v1' THEN
        RAISE EXCEPTION 'Unsupported renewal-boundary EIR journal draft policy version.';
    END IF;
    IF normalized_review_token !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR review token is invalid.';
    END IF;
    IF p_expected_total_amount IS DISTINCT FROM expected_total OR expected_total <= 0 THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR total must be a positive two-decimal amount.';
    END IF;
    IF jsonb_typeof(p_entries) IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR entries must be an array.';
    END IF;
    expected_count := jsonb_array_length(p_entries);
    IF expected_count < 1 THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR preparation requires at least one fiscal-period entry.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended(
            'renewal-boundary-eir-journal:' || p_renewal_execution_event_id::text,
            0
        )
    );

    LOCK TABLE
        lending.loan_renewal_execution_events,
        lending.loan_disbursement_events,
        lending.loans,
        lending.loan_types,
        lending.clients,
        lending.collection_transactions,
        lending.loan_contract_schedules,
        lending.loan_contract_schedule_registrations,
        lending.loan_contract_installments,
        accounting.loan_disbursement_journal_postings,
        accounting.loan_disbursement_journal_reversals,
        lending.loan_disbursement_cancellations,
        accounting.regular_journal_draft_preparations,
        accounting.regular_journal_draft_preparation_entries,
        accounting.regular_journal_posting_sets,
        accounting.regular_journal_posting_entries,
        accounting.regular_journal_reversal_sets,
        accounting.regular_journal_reversal_entries,
        accounting.journal_entries,
        accounting.journal_lines,
        accounting.fiscal_periods,
        accounting.accounts,
        accounting.renewal_boundary_eir_journal_preparations,
        accounting.renewal_boundary_eir_journal_preparation_entries,
        accounting.renewal_boundary_eir_journal_posting_sets,
        accounting.renewal_boundary_eir_journal_posting_entries
    IN SHARE MODE;

    SELECT * INTO execution_row
    FROM lending.loan_renewal_execution_events execution
    WHERE execution.id = p_renewal_execution_event_id;

    IF execution_row.id IS NULL OR execution_row.is_voided THEN
        RAISE EXCEPTION 'Active authoritative renewal execution evidence was not found.';
    END IF;

    SELECT * INTO existing_preparation
    FROM accounting.renewal_boundary_eir_journal_preparations prepared
    WHERE prepared.renewal_execution_event_id = p_renewal_execution_event_id;

    IF existing_preparation.id IS NOT NULL THEN
        IF existing_preparation.old_loan_id <> execution_row.old_loan_id
           OR existing_preparation.client_id <> execution_row.client_id
           OR existing_preparation.target_date <> execution_row.business_date
           OR existing_preparation.review_token <> normalized_review_token
           OR existing_preparation.boundary_policy_version <> p_boundary_policy_version
           OR existing_preparation.draft_policy_version <> p_draft_policy_version
           OR existing_preparation.expected_entry_count <> expected_count
           OR existing_preparation.total_amount <> expected_total THEN
            RAISE EXCEPTION 'Existing protected renewal-boundary EIR preparation does not match the reviewed confirmation.';
        END IF;

        SELECT count(*)::integer
        INTO invalid_count
        FROM accounting.renewal_boundary_eir_journal_preparation_entries prepared_entry
        JOIN accounting.journal_entries journal
          ON journal.id = prepared_entry.journal_entry_id
        WHERE prepared_entry.preparation_id = existing_preparation.id
          AND journal.status IN ('draft', 'posted');
        IF invalid_count <> expected_count THEN
            RAISE EXCEPTION 'Existing protected renewal-boundary EIR preparation is incomplete or has unexpected journal state.';
        END IF;
        RETURN existing_preparation.id;
    END IF;

    WITH parsed AS (
        SELECT
            item,
            ordinality::integer AS array_order,
            (item ->> 'sequence_order')::integer AS sequence_order,
            (item ->> 'fiscal_period_id')::uuid AS fiscal_period_id,
            (item ->> 'posting_date')::date AS posting_date,
            (item ->> 'amount')::numeric AS amount,
            nullif(btrim(item ->> 'source_type'), '') AS source_type,
            nullif(btrim(item ->> 'source_reference'), '') AS source_reference,
            nullif(btrim(item ->> 'source_event_key'), '') AS source_event_key,
            nullif(btrim(item ->> 'debit_account_system_key'), '') AS debit_account_system_key,
            nullif(btrim(item ->> 'credit_account_system_key'), '') AS credit_account_system_key
        FROM jsonb_array_elements(p_entries) WITH ORDINALITY source(item, ordinality)
    )
    SELECT count(*)::integer, coalesce(sum(round(amount, 2)), 0)::numeric(18,2)
    INTO invalid_count, actual_total
    FROM parsed
    WHERE sequence_order <> array_order
       OR sequence_order < 1
       OR amount <= 0
       OR amount <> round(amount, 2)
       OR source_type <> 'regular_renewal_eir_accrual'
       OR source_reference <>
          p_renewal_execution_event_id::text || ':fiscal_period:' || fiscal_period_id::text
       OR source_event_key <>
          'renewal_eir_accrual:' || p_renewal_execution_event_id::text ||
          ':fiscal_period:' || fiscal_period_id::text
       OR debit_account_system_key <> 'accrued_interest_receivable'
       OR credit_account_system_key <> 'interest_income_regular';

    IF invalid_count > 0 THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR journal entry evidence is malformed or has an invalid source/account identity.';
    END IF;

    SELECT coalesce(sum((item ->> 'amount')::numeric), 0)::numeric(18,2)
    INTO actual_total
    FROM jsonb_array_elements(p_entries) item;
    IF actual_total <> expected_total THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR entries do not reconcile to the reviewed total amount.';
    END IF;

    WITH parsed AS (
        SELECT
            item ->> 'source_event_key' AS source_event_key,
            (item ->> 'fiscal_period_id')::uuid AS fiscal_period_id
        FROM jsonb_array_elements(p_entries) item
    )
    SELECT
        (count(*) - count(DISTINCT source_event_key))
        + (count(*) - count(DISTINCT fiscal_period_id))
    INTO duplicate_count
    FROM parsed;
    IF duplicate_count > 0 THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR source and fiscal-period identities must be unique.';
    END IF;

    SELECT count(*)::integer
    INTO duplicate_count
    FROM accounting.journal_entries journal
    WHERE journal.source_event_key IN (
        SELECT item ->> 'source_event_key'
        FROM jsonb_array_elements(p_entries) item
    );
    IF duplicate_count > 0 THEN
        RAISE EXCEPTION 'One or more protected renewal-boundary EIR source events already have journal history.';
    END IF;

    WITH parsed AS (
        SELECT
            (item ->> 'fiscal_period_id')::uuid AS fiscal_period_id,
            (item ->> 'posting_date')::date AS posting_date
        FROM jsonb_array_elements(p_entries) item
    )
    SELECT count(*)::integer
    INTO invalid_count
    FROM parsed
    LEFT JOIN accounting.fiscal_periods period
      ON period.id = parsed.fiscal_period_id
    WHERE period.id IS NULL
       OR period.status <> 'open'
       OR parsed.posting_date NOT BETWEEN period.start_date AND period.end_date
       OR parsed.posting_date > execution_row.business_date;
    IF invalid_count > 0 THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR fiscal-period evidence changed, is not open, or exceeds the authoritative renewal date.';
    END IF;

    SELECT id INTO debit_account_id
    FROM accounting.accounts
    WHERE system_key = 'accrued_interest_receivable'
      AND is_active = true
      AND is_posting = true;
    SELECT id INTO credit_account_id
    FROM accounting.accounts
    WHERE system_key = 'interest_income_regular'
      AND is_active = true
      AND is_posting = true;
    IF debit_account_id IS NULL OR credit_account_id IS NULL
       OR debit_account_id = credit_account_id THEN
        RAISE EXCEPTION 'Required renewal-boundary EIR posting accounts are missing, inactive, non-posting, or invalid.';
    END IF;

    PERFORM set_config('accounting.renewal_boundary_eir_prepare_allowed', 'on', true);

    INSERT INTO accounting.renewal_boundary_eir_journal_preparations (
        renewal_execution_event_id,
        old_loan_id,
        client_id,
        target_date,
        review_token,
        boundary_policy_version,
        draft_policy_version,
        expected_entry_count,
        total_amount,
        prepared_by_user_id
    ) VALUES (
        p_renewal_execution_event_id,
        execution_row.old_loan_id,
        execution_row.client_id,
        execution_row.business_date,
        normalized_review_token,
        p_boundary_policy_version,
        p_draft_policy_version,
        expected_count,
        expected_total,
        p_actor_user_id
    ) RETURNING id INTO preparation_id;

    FOR entry_item IN
        SELECT item
        FROM jsonb_array_elements(p_entries) item
        ORDER BY (item ->> 'sequence_order')::integer
    LOOP
        entry_sequence := (entry_item ->> 'sequence_order')::integer;
        entry_period_id := (entry_item ->> 'fiscal_period_id')::uuid;
        entry_posting_date := (entry_item ->> 'posting_date')::date;
        entry_amount := round((entry_item ->> 'amount')::numeric, 2);
        entry_source_reference := entry_item ->> 'source_reference';
        entry_source_event_key := entry_item ->> 'source_event_key';

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
        ) VALUES (
            entry_period_id,
            entry_posting_date,
            'Protected Regular renewal-boundary EIR accrual ' ||
                p_renewal_execution_event_id::text || ' - fiscal period ' ||
                entry_period_id::text,
            'draft',
            'regular_renewal_eir_accrual',
            entry_source_reference,
            entry_source_event_key,
            p_actor_user_id,
            now()
        ) RETURNING id INTO created_journal_id;

        INSERT INTO accounting.journal_lines (
            journal_entry_id,
            line_number,
            account_id,
            description,
            debit,
            credit,
            client_id,
            loan_id
        ) VALUES
            (
                created_journal_id,
                1,
                debit_account_id,
                'Regular renewal-boundary effective interest accrued',
                entry_amount,
                0,
                execution_row.client_id,
                execution_row.old_loan_id
            ),
            (
                created_journal_id,
                2,
                credit_account_id,
                'Regular renewal-boundary effective interest income',
                0,
                entry_amount,
                execution_row.client_id,
                execution_row.old_loan_id
            );

        INSERT INTO accounting.journal_events (
            journal_entry_id, event_type, actor_user_id, details
        ) VALUES (
            created_journal_id,
            'draft_created',
            p_actor_user_id,
            jsonb_build_object(
                'protected_renewal_boundary_eir', true,
                'renewal_execution_event_id', p_renewal_execution_event_id,
                'sequence_order', entry_sequence,
                'review_token', normalized_review_token,
                'boundary_policy_version', p_boundary_policy_version,
                'draft_policy_version', p_draft_policy_version,
                'posting_enabled', false,
                'automatic_source_posting', false
            )
        );

        INSERT INTO accounting.renewal_boundary_eir_journal_preparation_entries (
            preparation_id,
            sequence_order,
            journal_entry_id,
            fiscal_period_id,
            posting_date,
            amount,
            source_reference,
            source_event_key,
            debit_account_id,
            credit_account_id
        ) VALUES (
            preparation_id,
            entry_sequence,
            created_journal_id,
            entry_period_id,
            entry_posting_date,
            entry_amount,
            entry_source_reference,
            entry_source_event_key,
            debit_account_id,
            credit_account_id
        );
    END LOOP;

    RETURN preparation_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.post_renewal_boundary_eir_journal_review_set(
    p_renewal_execution_event_id UUID,
    p_actor_user_id UUID,
    p_review_token TEXT,
    p_expected_entry_count INTEGER,
    p_expected_total_debit NUMERIC,
    p_expected_total_credit NUMERIC,
    p_posting_policy_version TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    execution_row lending.loan_renewal_execution_events%ROWTYPE;
    prepared accounting.renewal_boundary_eir_journal_preparations%ROWTYPE;
    existing_post accounting.renewal_boundary_eir_journal_posting_sets%ROWTYPE;
    created_posting_set_id UUID;
    normalized_review_token TEXT := lower(btrim(coalesce(p_review_token, '')));
    expected_debit NUMERIC(18,2) := round(coalesce(p_expected_total_debit, 0), 2);
    expected_credit NUMERIC(18,2) := round(coalesce(p_expected_total_credit, 0), 2);
    actual_entry_count INTEGER;
    draft_entry_count INTEGER;
    posted_entry_count INTEGER;
    audit_entry_count INTEGER;
    invalid_count INTEGER;
    actual_debit NUMERIC(18,2);
    actual_credit NUMERIC(18,2);
    posting_entry RECORD;
    generated_number TEXT;
BEGIN
    IF p_posting_policy_version IS DISTINCT FROM 'renewal_boundary_eir_journal_posting_v1' THEN
        RAISE EXCEPTION 'Unsupported renewal-boundary EIR journal posting policy version.';
    END IF;
    IF normalized_review_token !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR review token is invalid.';
    END IF;
    IF p_expected_entry_count IS NULL OR p_expected_entry_count < 1
       OR p_expected_total_debit IS DISTINCT FROM expected_debit
       OR p_expected_total_credit IS DISTINCT FROM expected_credit
       OR expected_debit <= 0
       OR expected_debit <> expected_credit THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR posting confirmation totals are invalid.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended(
            'renewal-boundary-eir-journal:' || p_renewal_execution_event_id::text,
            0
        )
    );

    LOCK TABLE
        lending.loan_renewal_execution_events,
        accounting.journal_entries,
        accounting.journal_lines,
        accounting.fiscal_periods,
        accounting.accounts,
        accounting.renewal_boundary_eir_journal_preparations,
        accounting.renewal_boundary_eir_journal_preparation_entries,
        accounting.renewal_boundary_eir_journal_posting_sets,
        accounting.renewal_boundary_eir_journal_posting_entries
    IN SHARE MODE;

    SELECT * INTO execution_row
    FROM lending.loan_renewal_execution_events execution
    WHERE execution.id = p_renewal_execution_event_id;
    IF execution_row.id IS NULL OR execution_row.is_voided THEN
        RAISE EXCEPTION 'Active authoritative renewal execution evidence was not found for protected boundary posting.';
    END IF;

    SELECT * INTO prepared
    FROM accounting.renewal_boundary_eir_journal_preparations preparation
    WHERE preparation.renewal_execution_event_id = p_renewal_execution_event_id;
    IF prepared.id IS NULL THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR draft preparation was not found.';
    END IF;
    IF prepared.review_token <> normalized_review_token
       OR prepared.expected_entry_count <> p_expected_entry_count
       OR prepared.total_amount <> expected_debit
       OR prepared.old_loan_id <> execution_row.old_loan_id
       OR prepared.client_id <> execution_row.client_id
       OR prepared.target_date <> execution_row.business_date THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR posting confirmation no longer matches the immutable preparation.';
    END IF;

    SELECT * INTO existing_post
    FROM accounting.renewal_boundary_eir_journal_posting_sets posting
    WHERE posting.preparation_id = prepared.id;

    SELECT
        count(*)::integer,
        count(*) FILTER (WHERE journal.status = 'draft')::integer,
        count(*) FILTER (WHERE journal.status = 'posted')::integer,
        coalesce(sum(totals.total_debit), 0)::numeric(18,2),
        coalesce(sum(totals.total_credit), 0)::numeric(18,2)
    INTO actual_entry_count, draft_entry_count, posted_entry_count, actual_debit, actual_credit
    FROM accounting.renewal_boundary_eir_journal_preparation_entries prepared_entry
    JOIN accounting.journal_entries journal
      ON journal.id = prepared_entry.journal_entry_id
    JOIN LATERAL (
        SELECT
            coalesce(sum(line.debit), 0)::numeric(18,2) AS total_debit,
            coalesce(sum(line.credit), 0)::numeric(18,2) AS total_credit
        FROM accounting.journal_lines line
        WHERE line.journal_entry_id = journal.id
    ) totals ON true
    WHERE prepared_entry.preparation_id = prepared.id;

    IF actual_entry_count <> p_expected_entry_count
       OR actual_debit <> expected_debit
       OR actual_credit <> expected_credit THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR draft count or totals changed before posting.';
    END IF;

    IF existing_post.id IS NOT NULL THEN
        SELECT count(*)::integer INTO audit_entry_count
        FROM accounting.renewal_boundary_eir_journal_posting_entries posting_entry
        JOIN accounting.journal_entries journal
          ON journal.id = posting_entry.journal_entry_id
        WHERE posting_entry.posting_set_id = existing_post.id
          AND journal.status = 'posted'
          AND journal.entry_number = posting_entry.entry_number
          AND journal.source_event_key = posting_entry.source_event_key;
        IF existing_post.renewal_execution_event_id <> p_renewal_execution_event_id
           OR existing_post.review_token <> normalized_review_token
           OR existing_post.expected_entry_count <> p_expected_entry_count
           OR existing_post.posted_entry_count <> p_expected_entry_count
           OR existing_post.total_debit <> expected_debit
           OR existing_post.total_credit <> expected_credit
           OR posted_entry_count <> p_expected_entry_count
           OR draft_entry_count <> 0
           OR audit_entry_count <> p_expected_entry_count THEN
            RAISE EXCEPTION 'Protected renewal-boundary EIR posting audit does not match the posted review set.';
        END IF;
        RETURN existing_post.id;
    END IF;

    IF posted_entry_count > 0 OR draft_entry_count <> p_expected_entry_count THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR review set contains posted or non-draft history without the complete protected posting audit.';
    END IF;

    SELECT count(*)::integer
    INTO invalid_count
    FROM accounting.renewal_boundary_eir_journal_preparation_entries prepared_entry
    JOIN accounting.journal_entries journal
      ON journal.id = prepared_entry.journal_entry_id
    JOIN accounting.fiscal_periods period
      ON period.id = prepared_entry.fiscal_period_id
    JOIN accounting.accounts debit_account
      ON debit_account.id = prepared_entry.debit_account_id
    JOIN accounting.accounts credit_account
      ON credit_account.id = prepared_entry.credit_account_id
    JOIN LATERAL (
        SELECT
            count(*)::integer AS line_count,
            coalesce(sum(line.debit), 0)::numeric(18,2) AS total_debit,
            coalesce(sum(line.credit), 0)::numeric(18,2) AS total_credit,
            count(*) FILTER (
                WHERE line.account_id = prepared_entry.debit_account_id
                  AND line.debit = prepared_entry.amount
                  AND line.credit = 0
                  AND line.loan_id = prepared.old_loan_id
                  AND line.client_id = prepared.client_id
            )::integer AS exact_debit_count,
            count(*) FILTER (
                WHERE line.account_id = prepared_entry.credit_account_id
                  AND line.credit = prepared_entry.amount
                  AND line.debit = 0
                  AND line.loan_id = prepared.old_loan_id
                  AND line.client_id = prepared.client_id
            )::integer AS exact_credit_count,
            count(*) FILTER (
                WHERE line.loan_id IS DISTINCT FROM prepared.old_loan_id
                   OR line.client_id IS DISTINCT FROM prepared.client_id
            )::integer AS wrong_dimension_count
        FROM accounting.journal_lines line
        WHERE line.journal_entry_id = journal.id
    ) totals ON true
    WHERE prepared_entry.preparation_id = prepared.id
      AND (
          journal.status <> 'draft'
          OR journal.entry_number IS NOT NULL
          OR journal.fiscal_period_id <> prepared_entry.fiscal_period_id
          OR journal.posting_date <> prepared_entry.posting_date
          OR journal.source_type <> 'regular_renewal_eir_accrual'
          OR journal.source_reference <> prepared_entry.source_reference
          OR journal.source_event_key <> prepared_entry.source_event_key
          OR journal.source_reference <>
               p_renewal_execution_event_id::text || ':fiscal_period:' ||
               prepared_entry.fiscal_period_id::text
          OR journal.source_event_key <>
               'renewal_eir_accrual:' || p_renewal_execution_event_id::text ||
               ':fiscal_period:' || prepared_entry.fiscal_period_id::text
          OR period.status <> 'open'
          OR journal.posting_date NOT BETWEEN period.start_date AND period.end_date
          OR journal.posting_date > execution_row.business_date
          OR debit_account.system_key <> 'accrued_interest_receivable'
          OR credit_account.system_key <> 'interest_income_regular'
          OR debit_account.is_active = false
          OR debit_account.is_posting = false
          OR credit_account.is_active = false
          OR credit_account.is_posting = false
          OR totals.line_count <> 2
          OR totals.total_debit <> prepared_entry.amount
          OR totals.total_credit <> prepared_entry.amount
          OR totals.exact_debit_count <> 1
          OR totals.exact_credit_count <> 1
          OR totals.wrong_dimension_count <> 0
      );
    IF invalid_count > 0 THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR draft integrity, identity, period, account, balance, or dimensions changed before posting.';
    END IF;

    PERFORM set_config('accounting.renewal_boundary_eir_post_record_allowed', 'on', true);
    INSERT INTO accounting.renewal_boundary_eir_journal_posting_sets (
        preparation_id,
        renewal_execution_event_id,
        old_loan_id,
        client_id,
        review_token,
        posting_policy_version,
        expected_entry_count,
        posted_entry_count,
        total_debit,
        total_credit,
        posted_by_user_id
    ) VALUES (
        prepared.id,
        p_renewal_execution_event_id,
        prepared.old_loan_id,
        prepared.client_id,
        normalized_review_token,
        p_posting_policy_version,
        p_expected_entry_count,
        p_expected_entry_count,
        expected_debit,
        expected_credit,
        p_actor_user_id
    ) RETURNING id INTO created_posting_set_id;

    PERFORM set_config('accounting.renewal_boundary_eir_journal_post_allowed', 'on', true);

    FOR posting_entry IN
        SELECT
            prepared_entry.sequence_order,
            prepared_entry.journal_entry_id,
            prepared_entry.source_event_key
        FROM accounting.renewal_boundary_eir_journal_preparation_entries prepared_entry
        JOIN accounting.journal_entries journal
          ON journal.id = prepared_entry.journal_entry_id
        WHERE prepared_entry.preparation_id = prepared.id
        ORDER BY prepared_entry.sequence_order
        FOR UPDATE OF journal
    LOOP
        generated_number := accounting.post_journal_entry(
            posting_entry.journal_entry_id,
            p_actor_user_id
        );

        INSERT INTO accounting.journal_events (
            journal_entry_id, event_type, actor_user_id, details
        ) VALUES (
            posting_entry.journal_entry_id,
            'posted',
            p_actor_user_id,
            jsonb_build_object(
                'entry_number', generated_number,
                'protected_renewal_boundary_eir', true,
                'renewal_execution_event_id', p_renewal_execution_event_id,
                'review_token', normalized_review_token,
                'automatic_source_posting', false
            )
        );

        INSERT INTO accounting.renewal_boundary_eir_journal_posting_entries (
            posting_set_id,
            preparation_id,
            sequence_order,
            journal_entry_id,
            entry_number,
            source_event_key
        ) VALUES (
            created_posting_set_id,
            prepared.id,
            posting_entry.sequence_order,
            posting_entry.journal_entry_id,
            generated_number,
            posting_entry.source_event_key
        );
    END LOOP;

    SELECT count(*)::integer INTO audit_entry_count
    FROM accounting.renewal_boundary_eir_journal_posting_entries posting_entry
    JOIN accounting.journal_entries journal
      ON journal.id = posting_entry.journal_entry_id
    WHERE posting_entry.posting_set_id = created_posting_set_id
      AND journal.status = 'posted'
      AND journal.entry_number = posting_entry.entry_number
      AND journal.source_event_key = posting_entry.source_event_key;

    IF audit_entry_count <> p_expected_entry_count THEN
        RAISE EXCEPTION 'Protected renewal-boundary EIR posting audit is incomplete; posting transaction was rolled back.';
    END IF;

    RETURN created_posting_set_id;
END;
$$;

CREATE OR REPLACE VIEW accounting.renewal_boundary_eir_journal_status AS
SELECT
    prepared.id AS preparation_id,
    prepared.renewal_execution_event_id,
    prepared.old_loan_id,
    prepared.client_id,
    prepared.target_date,
    prepared.review_token,
    prepared.boundary_policy_version,
    prepared.draft_policy_version,
    prepared.expected_entry_count,
    prepared.total_amount,
    prepared.prepared_by_user_id,
    prepared.prepared_at,
    posting.id AS posting_set_id,
    posting.posting_policy_version,
    posting.posted_by_user_id,
    posting.posted_at,
    coalesce(entries.actual_entry_count, 0)::integer AS actual_entry_count,
    coalesce(entries.draft_entry_count, 0)::integer AS draft_entry_count,
    coalesce(entries.posted_entry_count, 0)::integer AS posted_entry_count,
    coalesce(entries.total_debit, 0)::numeric(18,2) AS total_debit,
    coalesce(entries.total_credit, 0)::numeric(18,2) AS total_credit,
    coalesce(posting_audit.audit_entry_count, 0)::integer AS posting_audit_entry_count,
    (
        coalesce(entries.actual_entry_count, 0) = prepared.expected_entry_count
        AND coalesce(entries.total_debit, 0) = prepared.total_amount
        AND coalesce(entries.total_credit, 0) = prepared.total_amount
        AND coalesce(entries.invalid_identity_count, 0) = 0
        AND coalesce(entries.invalid_period_count, 0) = 0
        AND coalesce(entries.invalid_line_count, 0) = 0
    ) AS integrity_ready,
    (
        posting.id IS NOT NULL
        AND coalesce(entries.posted_entry_count, 0) = prepared.expected_entry_count
        AND coalesce(entries.draft_entry_count, 0) = 0
        AND coalesce(posting_audit.audit_entry_count, 0) = prepared.expected_entry_count
        AND posting.expected_entry_count = prepared.expected_entry_count
        AND posting.posted_entry_count = prepared.expected_entry_count
        AND posting.total_debit = prepared.total_amount
        AND posting.total_credit = prepared.total_amount
        AND posting.review_token = prepared.review_token
    ) AS protected_posting_complete,
    false AS automatic_source_posting
FROM accounting.renewal_boundary_eir_journal_preparations prepared
LEFT JOIN accounting.renewal_boundary_eir_journal_posting_sets posting
  ON posting.preparation_id = prepared.id
LEFT JOIN LATERAL (
    SELECT
        count(*)::integer AS actual_entry_count,
        count(*) FILTER (WHERE journal.status = 'draft')::integer AS draft_entry_count,
        count(*) FILTER (WHERE journal.status = 'posted')::integer AS posted_entry_count,
        coalesce(sum(totals.total_debit), 0)::numeric(18,2) AS total_debit,
        coalesce(sum(totals.total_credit), 0)::numeric(18,2) AS total_credit,
        count(*) FILTER (
            WHERE journal.fiscal_period_id <> entry.fiscal_period_id
               OR journal.posting_date <> entry.posting_date
               OR journal.source_type <> 'regular_renewal_eir_accrual'
               OR journal.source_reference <> entry.source_reference
               OR journal.source_event_key <> entry.source_event_key
        )::integer AS invalid_identity_count,
        count(*) FILTER (
            WHERE period.status <> 'open'
               OR journal.posting_date NOT BETWEEN period.start_date AND period.end_date
        )::integer AS invalid_period_count,
        count(*) FILTER (
            WHERE totals.line_count <> 2
               OR totals.total_debit <> entry.amount
               OR totals.total_credit <> entry.amount
               OR totals.exact_debit_count <> 1
               OR totals.exact_credit_count <> 1
               OR totals.wrong_dimension_count <> 0
        )::integer AS invalid_line_count
    FROM accounting.renewal_boundary_eir_journal_preparation_entries entry
    JOIN accounting.journal_entries journal
      ON journal.id = entry.journal_entry_id
    JOIN accounting.fiscal_periods period
      ON period.id = entry.fiscal_period_id
    LEFT JOIN LATERAL (
        SELECT
            count(*)::integer AS line_count,
            coalesce(sum(line.debit), 0)::numeric(18,2) AS total_debit,
            coalesce(sum(line.credit), 0)::numeric(18,2) AS total_credit,
            count(*) FILTER (
                WHERE line.account_id = entry.debit_account_id
                  AND line.debit = entry.amount
                  AND line.credit = 0
                  AND line.loan_id = prepared.old_loan_id
                  AND line.client_id = prepared.client_id
            )::integer AS exact_debit_count,
            count(*) FILTER (
                WHERE line.account_id = entry.credit_account_id
                  AND line.credit = entry.amount
                  AND line.debit = 0
                  AND line.loan_id = prepared.old_loan_id
                  AND line.client_id = prepared.client_id
            )::integer AS exact_credit_count,
            count(*) FILTER (
                WHERE line.loan_id IS DISTINCT FROM prepared.old_loan_id
                   OR line.client_id IS DISTINCT FROM prepared.client_id
            )::integer AS wrong_dimension_count
        FROM accounting.journal_lines line
        WHERE line.journal_entry_id = journal.id
    ) totals ON true
    WHERE entry.preparation_id = prepared.id
) entries ON true
LEFT JOIN LATERAL (
    SELECT count(*)::integer AS audit_entry_count
    FROM accounting.renewal_boundary_eir_journal_posting_entries posting_entry
    JOIN accounting.journal_entries journal
      ON journal.id = posting_entry.journal_entry_id
    WHERE posting_entry.posting_set_id = posting.id
      AND journal.status = 'posted'
      AND journal.entry_number = posting_entry.entry_number
      AND journal.source_event_key = posting_entry.source_event_key
) posting_audit ON true;

COMMIT;