BEGIN;

CREATE TABLE IF NOT EXISTS accounting.seven_by_seven_journal_reversals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_void_id UUID NOT NULL UNIQUE
        REFERENCES lending.collection_transaction_voids(id) ON DELETE RESTRICT,
    posting_id UUID NOT NULL UNIQUE
        REFERENCES accounting.seven_by_seven_journal_postings(id) ON DELETE RESTRICT,
    transaction_id UUID NOT NULL UNIQUE
        REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL
        REFERENCES lending.loans(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL
        REFERENCES lending.clients(id) ON DELETE RESTRICT,
    original_journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    reversal_journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    original_entry_number TEXT NOT NULL,
    reversal_entry_number TEXT NOT NULL UNIQUE,
    original_source_event_key TEXT NOT NULL,
    reversal_source_event_key TEXT NOT NULL UNIQUE,
    reversal_policy_version TEXT NOT NULL,
    reversal_posting_date DATE NOT NULL,
    fiscal_period_id UUID NOT NULL
        REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    reason TEXT NOT NULL CHECK (btrim(reason) <> ''),
    expected_line_count INTEGER NOT NULL CHECK (expected_line_count > 0),
    total_debit NUMERIC(18,2) NOT NULL CHECK (total_debit > 0),
    total_credit NUMERIC(18,2) NOT NULL CHECK (total_credit > 0),
    reversed_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    reversed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (original_source_event_key = 'collection:' || transaction_id::text),
    CHECK (
        reversal_source_event_key =
            'seven-by-seven-collection-void-reversal:' || posting_id::text
    ),
    CHECK (reversal_policy_version = 'seven_by_seven_collection_reversal_v1'),
    CHECK (btrim(original_entry_number) <> ''),
    CHECK (btrim(reversal_entry_number) <> ''),
    CHECK (total_debit = total_credit)
);

CREATE INDEX IF NOT EXISTS seven_by_seven_journal_reversals_loan_idx
    ON accounting.seven_by_seven_journal_reversals (loan_id, reversed_at DESC);

CREATE TABLE IF NOT EXISTS accounting.seven_by_seven_journal_reversal_lines (
    reversal_id UUID NOT NULL
        REFERENCES accounting.seven_by_seven_journal_reversals(id) ON DELETE RESTRICT,
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
    PRIMARY KEY (reversal_id, line_number),
    UNIQUE (reversal_id, journal_component),
    CHECK (btrim(journal_component) <> ''),
    CHECK (btrim(account_system_key) <> ''),
    CHECK (
        (debit > 0 AND credit = 0)
        OR (credit > 0 AND debit = 0)
    )
);

CREATE OR REPLACE FUNCTION accounting.guard_seven_by_seven_journal_reversal_record_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(
            current_setting('accounting.seven_by_seven_collection_void_reversal_allowed', true),
            ''
       ) = 'on' THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'Protected 7x7 reversal audit is immutable and must use the controlled collection-void workflow.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_seven_by_seven_journal_reversal_guard
    ON accounting.seven_by_seven_journal_reversals;
CREATE TRIGGER accounting_seven_by_seven_journal_reversal_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.seven_by_seven_journal_reversals
FOR EACH ROW EXECUTE FUNCTION accounting.guard_seven_by_seven_journal_reversal_record_write();

DROP TRIGGER IF EXISTS accounting_seven_by_seven_journal_reversal_line_guard
    ON accounting.seven_by_seven_journal_reversal_lines;
CREATE TRIGGER accounting_seven_by_seven_journal_reversal_line_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.seven_by_seven_journal_reversal_lines
FOR EACH ROW EXECUTE FUNCTION accounting.guard_seven_by_seven_journal_reversal_record_write();

-- Replace the 0066 fail-closed placeholder with a protected-session boundary.
-- Reversal journals may only be created by the controlled operational void flow.
CREATE OR REPLACE FUNCTION accounting.guard_protected_seven_by_seven_reversal_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    original_is_protected BOOLEAN := false;
    protected_session BOOLEAN := false;
BEGIN
    protected_session := coalesce(
        current_setting('accounting.seven_by_seven_collection_void_reversal_allowed', true),
        ''
    ) = 'on';

    IF NEW.reversal_of_entry_id IS NOT NULL THEN
        SELECT EXISTS (
            SELECT 1
            FROM accounting.seven_by_seven_journal_postings posted
            WHERE posted.journal_entry_id = NEW.reversal_of_entry_id
        )
        INTO original_is_protected;
    END IF;

    IF NEW.source_type = 'seven_by_seven_collection_reversal' THEN
        IF NOT protected_session
           OR NEW.reversal_of_entry_id IS NULL
           OR NOT original_is_protected THEN
            RAISE EXCEPTION 'Protected 7x7 collection reversal journals must use the controlled collection-void workflow.';
        END IF;
    ELSIF original_is_protected THEN
        RAISE EXCEPTION 'Posted protected 7x7 journals can only be reversed through the controlled collection-void workflow.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_protected_seven_by_seven_reversal_insert_guard
    ON accounting.journal_entries;
CREATE TRIGGER accounting_protected_seven_by_seven_reversal_insert_guard
BEFORE INSERT ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_protected_seven_by_seven_reversal_insert();

CREATE OR REPLACE FUNCTION accounting.reverse_posted_seven_by_seven_collection(
    p_transaction_id UUID,
    p_collection_void_id UUID,
    p_actor_user_id UUID,
    p_posting_date DATE,
    p_reason TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    source_transaction lending.collection_transactions%ROWTYPE;
    void_record lending.collection_transaction_voids%ROWTYPE;
    posted accounting.seven_by_seven_journal_postings%ROWTYPE;
    existing_reversal accounting.seven_by_seven_journal_reversals%ROWTYPE;
    original_journal accounting.journal_entries%ROWTYPE;
    reversal_journal accounting.journal_entries%ROWTYPE;
    target_period_id UUID;
    created_reversal_id UUID;
    created_reversal_entry_id UUID;
    generated_number TEXT;
    reversal_source_key TEXT;
    normalized_reason TEXT;
    original_line_count INTEGER;
    original_total_debit NUMERIC(18,2);
    original_total_credit NUMERIC(18,2);
    original_exact_snapshot_count INTEGER;
    existing_reversal_line_count INTEGER;
    existing_reversal_exact_count INTEGER;
    inserted_line_count INTEGER;
    reversed_line_count INTEGER;
    reversed_exact_count INTEGER;
BEGIN
    normalized_reason := btrim(coalesce(p_reason, ''));
    IF normalized_reason = '' THEN
        RAISE EXCEPTION 'A controlled 7x7 collection reversal requires the collection void reason.';
    END IF;
    IF p_posting_date IS NULL THEN
        RAISE EXCEPTION 'A controlled 7x7 collection reversal requires a posting date.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended('accounting-seven-by-seven-collection-reversal:' || p_transaction_id::text, 0)
    );

    SELECT *
    INTO source_transaction
    FROM lending.collection_transactions
    WHERE id = p_transaction_id
    FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'The collection transaction for the protected 7x7 reversal was not found.';
    END IF;

    SELECT *
    INTO void_record
    FROM lending.collection_transaction_voids
    WHERE id = p_collection_void_id
      AND transaction_id = p_transaction_id
    FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'The immutable collection void audit was not found for the protected 7x7 accounting reversal.';
    END IF;
    IF void_record.voided_by_user_id IS DISTINCT FROM p_actor_user_id
       OR btrim(void_record.reason) IS DISTINCT FROM normalized_reason
       OR (void_record.voided_at AT TIME ZONE 'Asia/Manila')::date IS DISTINCT FROM p_posting_date THEN
        RAISE EXCEPTION 'The collection void audit actor, reason, or business date is inconsistent with the protected 7x7 accounting reversal.';
    END IF;

    SELECT *
    INTO posted
    FROM accounting.seven_by_seven_journal_postings
    WHERE transaction_id = p_transaction_id
    FOR SHARE;

    -- A source that was never posted has no accounting history to reverse.
    -- Any immutable draft is intentionally left stale and cannot post after void.
    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    SELECT *
    INTO original_journal
    FROM accounting.journal_entries
    WHERE id = posted.journal_entry_id
    FOR SHARE;

    IF NOT FOUND
       OR original_journal.status <> 'posted'
       OR original_journal.entry_number IS DISTINCT FROM posted.entry_number
       OR original_journal.source_type <> 'seven_by_seven_collection'
       OR original_journal.source_reference IS DISTINCT FROM p_transaction_id::text
       OR original_journal.source_event_key IS DISTINCT FROM posted.source_event_key
       OR original_journal.reversal_of_entry_id IS NOT NULL THEN
        RAISE EXCEPTION 'Protected 7x7 reversal source no longer matches its immutable posting audit.';
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
                WHERE line.journal_entry_id = posted.journal_entry_id
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
        original_line_count,
        original_total_debit,
        original_total_credit,
        original_exact_snapshot_count
    FROM accounting.seven_by_seven_journal_posting_lines snapshot
    WHERE snapshot.posting_id = posted.id;

    IF original_line_count <> posted.coordinate_line_count
       OR original_exact_snapshot_count <> posted.coordinate_line_count
       OR original_total_debit <> posted.total_debit
       OR original_total_credit <> posted.total_credit
       OR original_total_debit <> original_total_credit THEN
        RAISE EXCEPTION 'Protected 7x7 reversal source journal no longer matches its immutable line snapshots.';
    END IF;

    SELECT *
    INTO existing_reversal
    FROM accounting.seven_by_seven_journal_reversals reversal
    WHERE reversal.transaction_id = p_transaction_id
    FOR SHARE;

    IF FOUND THEN
        SELECT *
        INTO reversal_journal
        FROM accounting.journal_entries
        WHERE id = existing_reversal.reversal_journal_entry_id
        FOR SHARE;

        SELECT
            count(snapshot.line_number)::integer,
            count(snapshot.line_number) FILTER (
                WHERE EXISTS (
                    SELECT 1
                    FROM accounting.journal_lines line
                    WHERE line.journal_entry_id = existing_reversal.reversal_journal_entry_id
                      AND line.line_number = snapshot.line_number
                      AND line.account_id = snapshot.account_id
                      AND line.debit = snapshot.debit
                      AND line.credit = snapshot.credit
                      AND line.client_id = snapshot.client_id
                      AND line.loan_id = snapshot.loan_id
                )
            )::integer
        INTO existing_reversal_line_count, existing_reversal_exact_count
        FROM accounting.seven_by_seven_journal_reversal_lines snapshot
        WHERE snapshot.reversal_id = existing_reversal.id;

        IF existing_reversal.collection_void_id IS DISTINCT FROM p_collection_void_id
           OR existing_reversal.posting_id IS DISTINCT FROM posted.id
           OR existing_reversal.loan_id IS DISTINCT FROM posted.loan_id
           OR existing_reversal.client_id IS DISTINCT FROM posted.client_id
           OR existing_reversal.original_journal_entry_id IS DISTINCT FROM posted.journal_entry_id
           OR existing_reversal.original_entry_number IS DISTINCT FROM posted.entry_number
           OR existing_reversal.original_source_event_key IS DISTINCT FROM posted.source_event_key
           OR existing_reversal.reversal_posting_date IS DISTINCT FROM p_posting_date
           OR existing_reversal.reason IS DISTINCT FROM normalized_reason
           OR existing_reversal.reversed_by_user_id IS DISTINCT FROM p_actor_user_id
           OR existing_reversal.expected_line_count <> posted.coordinate_line_count
           OR existing_reversal.total_debit <> posted.total_debit
           OR existing_reversal.total_credit <> posted.total_credit
           OR reversal_journal.id IS NULL
           OR reversal_journal.status <> 'posted'
           OR reversal_journal.entry_number IS DISTINCT FROM existing_reversal.reversal_entry_number
           OR reversal_journal.source_type <> 'seven_by_seven_collection_reversal'
           OR reversal_journal.source_reference IS DISTINCT FROM p_collection_void_id::text
           OR reversal_journal.source_event_key IS DISTINCT FROM existing_reversal.reversal_source_event_key
           OR reversal_journal.reversal_of_entry_id IS DISTINCT FROM posted.journal_entry_id
           OR existing_reversal_line_count <> posted.coordinate_line_count
           OR existing_reversal_exact_count <> posted.coordinate_line_count THEN
            RAISE EXCEPTION 'Existing protected 7x7 reversal audit is inconsistent.';
        END IF;

        RETURN existing_reversal.id;
    END IF;

    IF source_transaction.is_voided THEN
        RAISE EXCEPTION 'The collection transaction was already voided without an exact protected 7x7 reversal audit.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM accounting.journal_entries journal
        WHERE journal.reversal_of_entry_id = posted.journal_entry_id
    ) THEN
        RAISE EXCEPTION 'The protected 7x7 source journal already has a reversal outside this collection-void audit.';
    END IF;

    SELECT period.id
    INTO target_period_id
    FROM accounting.fiscal_periods period
    WHERE period.status = 'open'
      AND p_posting_date BETWEEN period.start_date AND period.end_date
    ORDER BY period.start_date DESC
    LIMIT 1
    FOR UPDATE;

    IF target_period_id IS NULL THEN
        RAISE EXCEPTION 'No open accounting period contains the controlled 7x7 reversal date.';
    END IF;

    PERFORM set_config(
        'accounting.seven_by_seven_collection_void_reversal_allowed',
        'on',
        true
    );

    created_reversal_entry_id := gen_random_uuid();
    reversal_source_key :=
        'seven-by-seven-collection-void-reversal:' || posted.id::text;

    INSERT INTO accounting.journal_entries (
        id,
        fiscal_period_id,
        posting_date,
        description,
        status,
        source_type,
        source_reference,
        source_event_key,
        reversal_of_entry_id,
        created_by_user_id
    ) VALUES (
        created_reversal_entry_id,
        target_period_id,
        p_posting_date,
        'Controlled 7x7 collection reversal of ' || posted.entry_number
            || ': ' || normalized_reason,
        'draft',
        'seven_by_seven_collection_reversal',
        p_collection_void_id::text,
        reversal_source_key,
        posted.journal_entry_id,
        p_actor_user_id
    );

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
        created_reversal_entry_id,
        snapshot.line_number,
        snapshot.account_id,
        'Controlled 7x7 reversal: ' || snapshot.journal_component,
        snapshot.credit,
        snapshot.debit,
        snapshot.client_id,
        snapshot.loan_id
    FROM accounting.seven_by_seven_journal_posting_lines snapshot
    WHERE snapshot.posting_id = posted.id
    ORDER BY snapshot.line_number;
    GET DIAGNOSTICS inserted_line_count = ROW_COUNT;

    IF inserted_line_count <> posted.coordinate_line_count THEN
        RAISE EXCEPTION 'Protected 7x7 reversal journal line creation is incomplete.';
    END IF;

    INSERT INTO accounting.journal_events (
        journal_entry_id,
        event_type,
        actor_user_id,
        details
    ) VALUES (
        created_reversal_entry_id,
        'reversal_created',
        p_actor_user_id,
        jsonb_build_object(
            'reversal_of_entry_id', posted.journal_entry_id,
            'posting_id', posted.id,
            'transaction_id', p_transaction_id,
            'collection_void_id', p_collection_void_id,
            'reason', normalized_reason,
            'exact_posting_snapshot_swap', true
        )
    );

    generated_number := accounting.post_journal_entry(
        created_reversal_entry_id,
        p_actor_user_id
    );

    INSERT INTO accounting.journal_events (
        journal_entry_id,
        event_type,
        actor_user_id,
        details
    ) VALUES (
        created_reversal_entry_id,
        'posted',
        p_actor_user_id,
        jsonb_build_object(
            'entry_number', generated_number,
            'protected_seven_by_seven_collection_void', true,
            'automatic_source_posting', false
        )
    );

    created_reversal_id := gen_random_uuid();
    INSERT INTO accounting.seven_by_seven_journal_reversals (
        id,
        collection_void_id,
        posting_id,
        transaction_id,
        loan_id,
        client_id,
        original_journal_entry_id,
        reversal_journal_entry_id,
        original_entry_number,
        reversal_entry_number,
        original_source_event_key,
        reversal_source_event_key,
        reversal_policy_version,
        reversal_posting_date,
        fiscal_period_id,
        reason,
        expected_line_count,
        total_debit,
        total_credit,
        reversed_by_user_id
    ) VALUES (
        created_reversal_id,
        p_collection_void_id,
        posted.id,
        p_transaction_id,
        posted.loan_id,
        posted.client_id,
        posted.journal_entry_id,
        created_reversal_entry_id,
        posted.entry_number,
        generated_number,
        posted.source_event_key,
        reversal_source_key,
        'seven_by_seven_collection_reversal_v1',
        p_posting_date,
        target_period_id,
        normalized_reason,
        posted.coordinate_line_count,
        posted.total_debit,
        posted.total_credit,
        p_actor_user_id
    );

    INSERT INTO accounting.seven_by_seven_journal_reversal_lines (
        reversal_id,
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
        created_reversal_id,
        snapshot.line_number,
        snapshot.journal_component,
        snapshot.account_id,
        snapshot.account_system_key,
        snapshot.credit,
        snapshot.debit,
        snapshot.client_id,
        snapshot.loan_id
    FROM accounting.seven_by_seven_journal_posting_lines snapshot
    WHERE snapshot.posting_id = posted.id
    ORDER BY snapshot.line_number;
    GET DIAGNOSTICS reversed_line_count = ROW_COUNT;

    SELECT count(snapshot.line_number)::integer
    INTO reversed_exact_count
    FROM accounting.seven_by_seven_journal_reversal_lines snapshot
    WHERE snapshot.reversal_id = created_reversal_id
      AND EXISTS (
        SELECT 1
        FROM accounting.journal_lines line
        WHERE line.journal_entry_id = created_reversal_entry_id
          AND line.line_number = snapshot.line_number
          AND line.account_id = snapshot.account_id
          AND line.debit = snapshot.debit
          AND line.credit = snapshot.credit
          AND line.client_id = snapshot.client_id
          AND line.loan_id = snapshot.loan_id
      );

    IF reversed_line_count <> posted.coordinate_line_count
       OR reversed_exact_count <> posted.coordinate_line_count THEN
        RAISE EXCEPTION 'Protected 7x7 collection reversal did not complete exact line-swap audit atomically.';
    END IF;

    INSERT INTO core.audit_logs (
        actor_user_id,
        action,
        target_type,
        target_id,
        details
    ) VALUES (
        p_actor_user_id,
        'accounting.seven_by_seven_journal.reversed',
        'seven_by_seven_journal_reversal',
        created_reversal_id,
        jsonb_build_object(
            'posting_id', posted.id::text,
            'transaction_id', p_transaction_id::text,
            'collection_void_id', p_collection_void_id::text,
            'original_journal_entry_id', posted.journal_entry_id::text,
            'reversal_journal_entry_id', created_reversal_entry_id::text,
            'original_entry_number', posted.entry_number,
            'reversal_entry_number', generated_number,
            'reason', normalized_reason,
            'reversal_posting_date', p_posting_date,
            'expected_line_count', posted.coordinate_line_count,
            'exact_debit_credit_swap', true,
            'explicit_management_posting', true,
            'automatic_source_posting', false
        )
    );

    PERFORM set_config(
        'accounting.seven_by_seven_collection_void_reversal_allowed',
        'off',
        true
    );

    RETURN created_reversal_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.perform_controlled_seven_by_seven_collection_void_reversal()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    business_posting_date DATE;
    void_id UUID;
BEGIN
    IF OLD.is_voided = false AND NEW.is_voided = true THEN
        SELECT void_record.id
        INTO void_id
        FROM lending.collection_transaction_voids void_record
        WHERE void_record.transaction_id = OLD.id;

        business_posting_date := (NEW.voided_at AT TIME ZONE 'Asia/Manila')::date;

        PERFORM accounting.reverse_posted_seven_by_seven_collection(
            OLD.id,
            void_id,
            NEW.voided_by_user_id,
            business_posting_date,
            NEW.void_reason
        );
    END IF;

    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.guard_posted_seven_by_seven_collection_void()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    posted accounting.seven_by_seven_journal_postings%ROWTYPE;
    void_id UUID;
    reversal_id UUID;
    reversal_entry_id UUID;
    reversal_line_count INTEGER;
    reversal_exact_count INTEGER;
BEGIN
    IF OLD.is_voided = false AND NEW.is_voided = true THEN
        SELECT *
        INTO posted
        FROM accounting.seven_by_seven_journal_postings
        WHERE transaction_id = OLD.id;

        IF NOT FOUND THEN
            RETURN NEW;
        END IF;

        SELECT void_record.id
        INTO void_id
        FROM lending.collection_transaction_voids void_record
        WHERE void_record.transaction_id = OLD.id;

        IF void_id IS NULL THEN
            RAISE EXCEPTION 'An accounted 7x7 collection requires immutable collection-void evidence before it can be voided.';
        END IF;

        SELECT reversal.id, reversal.reversal_journal_entry_id
        INTO reversal_id, reversal_entry_id
        FROM accounting.seven_by_seven_journal_reversals reversal
        JOIN accounting.journal_entries journal
          ON journal.id = reversal.reversal_journal_entry_id
        WHERE reversal.transaction_id = OLD.id
          AND reversal.collection_void_id = void_id
          AND reversal.posting_id = posted.id
          AND reversal.original_journal_entry_id = posted.journal_entry_id
          AND reversal.expected_line_count = posted.coordinate_line_count
          AND reversal.total_debit = posted.total_debit
          AND reversal.total_credit = posted.total_credit
          AND journal.status = 'posted'
          AND journal.entry_number = reversal.reversal_entry_number
          AND journal.source_type = 'seven_by_seven_collection_reversal'
          AND journal.source_reference = void_id::text
          AND journal.source_event_key = reversal.reversal_source_event_key
          AND journal.reversal_of_entry_id = posted.journal_entry_id;

        IF reversal_id IS NULL THEN
            RAISE EXCEPTION 'An accounted 7x7 collection cannot be voided until its protected reversing journal is posted and audited.';
        END IF;

        SELECT
            count(snapshot.line_number)::integer,
            count(snapshot.line_number) FILTER (
                WHERE EXISTS (
                    SELECT 1
                    FROM accounting.seven_by_seven_journal_posting_lines original
                    WHERE original.posting_id = posted.id
                      AND original.line_number = snapshot.line_number
                      AND original.journal_component = snapshot.journal_component
                      AND original.account_id = snapshot.account_id
                      AND original.account_system_key = snapshot.account_system_key
                      AND original.credit = snapshot.debit
                      AND original.debit = snapshot.credit
                      AND original.client_id = snapshot.client_id
                      AND original.loan_id = snapshot.loan_id
                )
                AND EXISTS (
                    SELECT 1
                    FROM accounting.journal_lines line
                    WHERE line.journal_entry_id = reversal_entry_id
                      AND line.line_number = snapshot.line_number
                      AND line.account_id = snapshot.account_id
                      AND line.debit = snapshot.debit
                      AND line.credit = snapshot.credit
                      AND line.client_id = snapshot.client_id
                      AND line.loan_id = snapshot.loan_id
                )
            )::integer
        INTO reversal_line_count, reversal_exact_count
        FROM accounting.seven_by_seven_journal_reversal_lines snapshot
        WHERE snapshot.reversal_id = reversal_id;

        IF reversal_line_count <> posted.coordinate_line_count
           OR reversal_exact_count <> posted.coordinate_line_count THEN
            RAISE EXCEPTION 'An accounted 7x7 collection cannot be voided because its protected reversal line audit is incomplete or not an exact debit/credit swap.';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

-- Trigger order: 00 immutable void evidence, 01 Regular reversal, 02 7x7
-- reversal, 03 final 7x7 audit guard, then the existing alphabetic Regular guard.
DROP TRIGGER IF EXISTS accounting_02_seven_by_seven_posted_collection_void_guard
    ON lending.collection_transactions;
DROP TRIGGER IF EXISTS accounting_02_seven_by_seven_collection_void_reversal
    ON lending.collection_transactions;
DROP TRIGGER IF EXISTS accounting_03_seven_by_seven_posted_collection_void_guard
    ON lending.collection_transactions;

CREATE TRIGGER accounting_02_seven_by_seven_collection_void_reversal
BEFORE UPDATE OF is_voided ON lending.collection_transactions
FOR EACH ROW EXECUTE FUNCTION accounting.perform_controlled_seven_by_seven_collection_void_reversal();

CREATE TRIGGER accounting_03_seven_by_seven_posted_collection_void_guard
BEFORE UPDATE OF is_voided ON lending.collection_transactions
FOR EACH ROW EXECUTE FUNCTION accounting.guard_posted_seven_by_seven_collection_void();

CREATE OR REPLACE VIEW accounting.seven_by_seven_journal_reversal_status AS
WITH reversal_line_summary AS (
    SELECT
        reversal.id AS reversal_id,
        count(snapshot.line_number)::integer AS line_count,
        coalesce(sum(snapshot.debit), 0)::numeric(18,2) AS total_debit,
        coalesce(sum(snapshot.credit), 0)::numeric(18,2) AS total_credit,
        count(snapshot.line_number) FILTER (
            WHERE EXISTS (
                SELECT 1
                FROM accounting.seven_by_seven_journal_posting_lines original
                WHERE original.posting_id = reversal.posting_id
                  AND original.line_number = snapshot.line_number
                  AND original.journal_component = snapshot.journal_component
                  AND original.account_id = snapshot.account_id
                  AND original.account_system_key = snapshot.account_system_key
                  AND original.credit = snapshot.debit
                  AND original.debit = snapshot.credit
                  AND original.client_id = snapshot.client_id
                  AND original.loan_id = snapshot.loan_id
            )
            AND EXISTS (
                SELECT 1
                FROM accounting.journal_lines line
                WHERE line.journal_entry_id = reversal.reversal_journal_entry_id
                  AND line.line_number = snapshot.line_number
                  AND line.account_id = snapshot.account_id
                  AND line.debit = snapshot.debit
                  AND line.credit = snapshot.credit
                  AND line.client_id = snapshot.client_id
                  AND line.loan_id = snapshot.loan_id
            )
        )::integer AS exact_swap_count
    FROM accounting.seven_by_seven_journal_reversals reversal
    LEFT JOIN accounting.seven_by_seven_journal_reversal_lines snapshot
      ON snapshot.reversal_id = reversal.id
    GROUP BY reversal.id
)
SELECT
    posted.id AS posting_id,
    posted.transaction_id,
    posted.loan_id,
    posted.client_id,
    posted.journal_entry_id AS original_journal_entry_id,
    posted.entry_number AS original_entry_number,
    posted.source_event_key AS original_source_event_key,
    posted.coordinate_line_count,
    posted.total_debit,
    posted.total_credit,
    source.is_voided,
    void_record.id AS collection_void_id,
    reversal.id AS reversal_id,
    reversal.reversal_journal_entry_id,
    reversal.reversal_entry_number,
    reversal.reversal_source_event_key,
    reversal.reversal_posting_date,
    reversal.reversed_by_user_id,
    reversal.reversed_at,
    reversal_journal.status AS reversal_journal_status,
    CASE
        WHEN source.is_voided
         AND reversal.id IS NOT NULL
         AND void_record.id = reversal.collection_void_id
         AND reversal.posting_id = posted.id
         AND reversal.transaction_id = posted.transaction_id
         AND reversal.loan_id = posted.loan_id
         AND reversal.client_id = posted.client_id
         AND reversal.original_journal_entry_id = posted.journal_entry_id
         AND reversal.original_entry_number = posted.entry_number
         AND reversal.original_source_event_key = posted.source_event_key
         AND reversal.reversal_policy_version = 'seven_by_seven_collection_reversal_v1'
         AND reversal.expected_line_count = posted.coordinate_line_count
         AND reversal.total_debit = posted.total_debit
         AND reversal.total_credit = posted.total_credit
         AND reversal_journal.status = 'posted'
         AND reversal_journal.entry_number = reversal.reversal_entry_number
         AND reversal_journal.source_type = 'seven_by_seven_collection_reversal'
         AND reversal_journal.source_reference = void_record.id::text
         AND reversal_journal.source_event_key = reversal.reversal_source_event_key
         AND reversal_journal.reversal_of_entry_id = posted.journal_entry_id
         AND reversal_line_summary.line_count = posted.coordinate_line_count
         AND reversal_line_summary.exact_swap_count = posted.coordinate_line_count
         AND reversal_line_summary.total_debit = posted.total_credit
         AND reversal_line_summary.total_credit = posted.total_debit
            THEN true
        ELSE false
    END AS reversal_audit_exact,
    true AS protected_reversal_enabled,
    false AS automatic_source_posting
FROM accounting.seven_by_seven_journal_postings posted
JOIN lending.collection_transactions source
  ON source.id = posted.transaction_id
LEFT JOIN lending.collection_transaction_voids void_record
  ON void_record.transaction_id = posted.transaction_id
LEFT JOIN accounting.seven_by_seven_journal_reversals reversal
  ON reversal.posting_id = posted.id
LEFT JOIN accounting.journal_entries reversal_journal
  ON reversal_journal.id = reversal.reversal_journal_entry_id
LEFT JOIN reversal_line_summary
  ON reversal_line_summary.reversal_id = reversal.id;

-- The 0066 posting-status view has the correct lifecycle shape but deliberately
-- exposed reversal_enabled=false. Preserve its exact definition and only flip
-- that installed capability flag now that 0067 provides the controlled path.
DO $$
DECLARE
    view_definition TEXT;
BEGIN
    SELECT pg_get_viewdef(
        'accounting.seven_by_seven_journal_posting_status'::regclass,
        true
    )
    INTO view_definition;

    IF position('false AS reversal_enabled' IN view_definition) = 0 THEN
        RAISE EXCEPTION '7x7 posting status view does not expose the expected disabled reversal capability flag.';
    END IF;

    EXECUTE
        'CREATE OR REPLACE VIEW accounting.seven_by_seven_journal_posting_status AS '
        || replace(
            view_definition,
            'false AS reversal_enabled',
            'true AS reversal_enabled'
        );
END;
$$;

COMMENT ON TABLE accounting.seven_by_seven_journal_reversals IS
    'Immutable controlled reversal audit for one posted protected 7x7 collection, bound to the operational collection-void evidence.';
COMMENT ON TABLE accounting.seven_by_seven_journal_reversal_lines IS
    'Immutable exact debit/credit-swapped line snapshots copied from the original protected 7x7 posting snapshots.';
COMMENT ON VIEW accounting.seven_by_seven_journal_reversal_status IS
    'Fail-closed posted-7x7 collection reversal reconciliation. A voided accounted source is exact only when its protected reversing journal is posted, audited, and an exact swap of the immutable original posting snapshots.';
COMMENT ON VIEW accounting.seven_by_seven_journal_posting_status IS
    'Fail-closed protected 7x7 posting readiness and immutable posted-audit status. Posting remains explicit Management action; controlled reversal is enabled by migration 0067 and automatic source posting remains off.';

COMMIT;