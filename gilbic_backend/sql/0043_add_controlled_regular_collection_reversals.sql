BEGIN;

CREATE TABLE IF NOT EXISTS accounting.regular_journal_reversal_sets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL UNIQUE
        REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    collection_void_id UUID NOT NULL UNIQUE
        REFERENCES lending.collection_transaction_voids(id) ON DELETE RESTRICT,
    posting_set_id UUID NOT NULL
        REFERENCES accounting.regular_journal_posting_sets(id) ON DELETE RESTRICT,
    posting_date DATE NOT NULL,
    reason TEXT NOT NULL CHECK (btrim(reason) <> ''),
    expected_entry_count INTEGER NOT NULL CHECK (expected_entry_count > 0),
    reversed_entry_count INTEGER NOT NULL CHECK (reversed_entry_count > 0),
    reversed_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    reversed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (expected_entry_count = reversed_entry_count)
);

CREATE TABLE IF NOT EXISTS accounting.regular_journal_reversal_entries (
    reversal_set_id UUID NOT NULL
        REFERENCES accounting.regular_journal_reversal_sets(id) ON DELETE RESTRICT,
    preparation_id UUID NOT NULL
        REFERENCES accounting.regular_journal_draft_preparations(id) ON DELETE RESTRICT,
    sequence_order INTEGER NOT NULL CHECK (sequence_order > 0),
    original_journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    reversal_journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    original_entry_number TEXT NOT NULL,
    reversal_entry_number TEXT NOT NULL UNIQUE,
    original_source_event_key TEXT NOT NULL,
    reversal_source_event_key TEXT NOT NULL UNIQUE,
    PRIMARY KEY (reversal_set_id, original_journal_entry_id),
    CHECK (btrim(original_entry_number) <> ''),
    CHECK (btrim(reversal_entry_number) <> ''),
    CHECK (btrim(original_source_event_key) <> ''),
    CHECK (btrim(reversal_source_event_key) <> '')
);

CREATE INDEX IF NOT EXISTS regular_journal_reversal_sets_posting_idx
    ON accounting.regular_journal_reversal_sets (posting_set_id, reversed_at DESC);
CREATE INDEX IF NOT EXISTS regular_journal_reversal_entries_set_idx
    ON accounting.regular_journal_reversal_entries (reversal_set_id, sequence_order);

CREATE OR REPLACE FUNCTION accounting.guard_regular_journal_reversal_record_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(
            current_setting('accounting.regular_collection_void_reversal_allowed', true),
            ''
       ) = 'on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Protected Regular reversal audit records are immutable and must use the controlled collection-void workflow.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_regular_journal_reversal_set_guard
    ON accounting.regular_journal_reversal_sets;
CREATE TRIGGER accounting_regular_journal_reversal_set_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.regular_journal_reversal_sets
FOR EACH ROW EXECUTE FUNCTION accounting.guard_regular_journal_reversal_record_write();

DROP TRIGGER IF EXISTS accounting_regular_journal_reversal_entry_guard
    ON accounting.regular_journal_reversal_entries;
CREATE TRIGGER accounting_regular_journal_reversal_entry_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.regular_journal_reversal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_regular_journal_reversal_record_write();

CREATE OR REPLACE FUNCTION accounting.guard_protected_regular_reversal_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    original_is_protected BOOLEAN := false;
    protected_session BOOLEAN := false;
BEGIN
    protected_session := coalesce(
        current_setting('accounting.regular_collection_void_reversal_allowed', true),
        ''
    ) = 'on';

    IF NEW.reversal_of_entry_id IS NOT NULL THEN
        SELECT EXISTS (
            SELECT 1
            FROM accounting.regular_journal_posting_entries posted
            WHERE posted.journal_entry_id = NEW.reversal_of_entry_id
        )
        INTO original_is_protected;
    END IF;

    IF NEW.source_type = 'regular_collection_void_reversal' THEN
        IF NOT protected_session OR NEW.reversal_of_entry_id IS NULL THEN
            RAISE EXCEPTION 'Protected Regular collection reversal journals must use the controlled collection-void workflow.';
        END IF;
    ELSIF original_is_protected THEN
        RAISE EXCEPTION 'Posted protected Regular journals can only be reversed through the controlled collection-void workflow.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_protected_regular_reversal_insert_guard
    ON accounting.journal_entries;
CREATE TRIGGER accounting_protected_regular_reversal_insert_guard
BEFORE INSERT ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_protected_regular_reversal_insert();

CREATE OR REPLACE FUNCTION accounting.reverse_posted_regular_collection(
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
    prepared accounting.regular_journal_draft_preparations%ROWTYPE;
    void_record lending.collection_transaction_voids%ROWTYPE;
    source_transaction lending.collection_transactions%ROWTYPE;
    existing_reversal accounting.regular_journal_reversal_sets%ROWTYPE;
    posting_set accounting.regular_journal_posting_sets%ROWTYPE;
    target_period_id UUID;
    posting_set_id UUID;
    created_reversal_set_id UUID;
    created_reversal_entry_id UUID;
    generated_number TEXT;
    reversal_source_key TEXT;
    normalized_reason TEXT;
    actual_entry_count INTEGER;
    draft_entry_count INTEGER;
    posted_entry_count INTEGER;
    posting_audit_count INTEGER;
    distinct_posting_set_count INTEGER;
    invalid_mapping_count INTEGER;
    reversal_count INTEGER;
    original_entry RECORD;
BEGIN
    normalized_reason := btrim(coalesce(p_reason, ''));
    IF normalized_reason = '' THEN
        RAISE EXCEPTION 'A controlled Regular collection reversal requires the collection void reason.';
    END IF;

    SELECT *
    INTO source_transaction
    FROM lending.collection_transactions
    WHERE id = p_transaction_id
    FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'The collection transaction for the protected reversal was not found.';
    END IF;
    IF source_transaction.is_voided THEN
        RAISE EXCEPTION 'The collection transaction was already voided before its protected accounting reversal.';
    END IF;

    SELECT *
    INTO void_record
    FROM lending.collection_transaction_voids
    WHERE id = p_collection_void_id
      AND transaction_id = p_transaction_id
    FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'The immutable collection void audit was not found for the protected accounting reversal.';
    END IF;
    IF void_record.voided_by_user_id IS DISTINCT FROM p_actor_user_id
       OR btrim(void_record.reason) IS DISTINCT FROM normalized_reason THEN
        RAISE EXCEPTION 'The collection void audit actor or reason is inconsistent with the protected accounting reversal.';
    END IF;

    SELECT *
    INTO prepared
    FROM accounting.regular_journal_draft_preparations
    WHERE transaction_id = p_transaction_id
    FOR SHARE;

    -- No protected preparation means the operational collection has never entered
    -- the Stage 5D.16/5D.17 accounting path and therefore needs no ledger reversal.
    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    SELECT
        count(*)::integer,
        count(*) FILTER (WHERE journal.status = 'draft')::integer,
        count(*) FILTER (WHERE journal.status = 'posted')::integer,
        count(posted.journal_entry_id)::integer,
        count(DISTINCT posted.posting_set_id)::integer
    INTO
        actual_entry_count,
        draft_entry_count,
        posted_entry_count,
        posting_audit_count,
        distinct_posting_set_count
    FROM accounting.regular_journal_draft_preparation_entries prepared_entry
    JOIN accounting.journal_entries journal
      ON journal.id = prepared_entry.journal_entry_id
    LEFT JOIN accounting.regular_journal_posting_entries posted
      ON posted.preparation_id = prepared_entry.preparation_id
     AND posted.sequence_order = prepared_entry.sequence_order
     AND posted.journal_entry_id = prepared_entry.journal_entry_id
    WHERE prepared_entry.preparation_id = prepared.id;

    IF actual_entry_count <> prepared.expected_entry_count OR actual_entry_count <= 0 THEN
        RAISE EXCEPTION 'Protected Regular reversal source preparation is incomplete.';
    END IF;

    -- A prepared-but-unposted source may still be voided. The immutable draft is
    -- intentionally left stale; Stage 5D.17 will refuse to post it after the void.
    IF posting_audit_count = 0 AND posted_entry_count = 0
       AND draft_entry_count = actual_entry_count THEN
        RETURN NULL;
    END IF;

    IF posting_audit_count <> actual_entry_count
       OR posted_entry_count <> actual_entry_count
       OR draft_entry_count <> 0
       OR distinct_posting_set_count <> 1 THEN
        RAISE EXCEPTION 'Protected Regular reversal source posting is partial, unaudited, or inconsistent.';
    END IF;

    SELECT count(*)::integer
    INTO invalid_mapping_count
    FROM accounting.regular_journal_draft_preparation_entries prepared_entry
    JOIN accounting.journal_entries journal
      ON journal.id = prepared_entry.journal_entry_id
    JOIN accounting.regular_journal_posting_entries posted
      ON posted.preparation_id = prepared_entry.preparation_id
     AND posted.sequence_order = prepared_entry.sequence_order
     AND posted.journal_entry_id = prepared_entry.journal_entry_id
    WHERE prepared_entry.preparation_id = prepared.id
      AND (
          journal.status <> 'posted'
          OR journal.entry_number IS DISTINCT FROM posted.entry_number
          OR journal.source_event_key IS DISTINCT FROM posted.source_event_key
      );

    IF invalid_mapping_count <> 0 THEN
        RAISE EXCEPTION 'Protected Regular reversal source no longer matches its immutable Stage 5D.17 posting audit.';
    END IF;

    SELECT posted.posting_set_id
    INTO posting_set_id
    FROM accounting.regular_journal_posting_entries posted
    WHERE posted.preparation_id = prepared.id
    ORDER BY posted.sequence_order
    LIMIT 1;

    SELECT *
    INTO posting_set
    FROM accounting.regular_journal_posting_sets posting
    WHERE posting.id = posting_set_id
    FOR SHARE;

    IF NOT FOUND
       OR posting_set.loan_id IS DISTINCT FROM prepared.loan_id
       OR posting_set.review_set_fingerprint IS DISTINCT FROM prepared.review_set_fingerprint THEN
        RAISE EXCEPTION 'Protected Regular reversal posting-set linkage is inconsistent.';
    END IF;

    SELECT *
    INTO existing_reversal
    FROM accounting.regular_journal_reversal_sets reversal
    WHERE reversal.transaction_id = p_transaction_id
    FOR SHARE;

    IF FOUND THEN
        SELECT count(*)::integer
        INTO reversal_count
        FROM accounting.regular_journal_reversal_entries reversal_entry
        JOIN accounting.journal_entries journal
          ON journal.id = reversal_entry.reversal_journal_entry_id
        WHERE reversal_entry.reversal_set_id = existing_reversal.id
          AND journal.status = 'posted'
          AND journal.entry_number = reversal_entry.reversal_entry_number
          AND journal.source_event_key = reversal_entry.reversal_source_event_key;

        IF existing_reversal.collection_void_id IS DISTINCT FROM p_collection_void_id
           OR existing_reversal.posting_set_id IS DISTINCT FROM posting_set_id
           OR existing_reversal.expected_entry_count <> actual_entry_count
           OR existing_reversal.reversed_entry_count <> actual_entry_count
           OR reversal_count <> actual_entry_count THEN
            RAISE EXCEPTION 'Existing protected Regular reversal audit is inconsistent.';
        END IF;
        RETURN existing_reversal.id;
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
        RAISE EXCEPTION 'No open accounting period contains the controlled Regular reversal date.';
    END IF;

    PERFORM set_config(
        'accounting.regular_collection_void_reversal_allowed',
        'on',
        true
    );

    created_reversal_set_id := gen_random_uuid();
    INSERT INTO accounting.regular_journal_reversal_sets (
        id,
        transaction_id,
        collection_void_id,
        posting_set_id,
        posting_date,
        reason,
        expected_entry_count,
        reversed_entry_count,
        reversed_by_user_id
    ) VALUES (
        created_reversal_set_id,
        p_transaction_id,
        p_collection_void_id,
        posting_set_id,
        p_posting_date,
        normalized_reason,
        actual_entry_count,
        actual_entry_count,
        p_actor_user_id
    );

    FOR original_entry IN
        SELECT
            posted.preparation_id,
            posted.sequence_order,
            posted.journal_entry_id,
            posted.entry_number,
            posted.source_event_key,
            journal.description
        FROM accounting.regular_journal_posting_entries posted
        JOIN accounting.journal_entries journal
          ON journal.id = posted.journal_entry_id
        WHERE posted.preparation_id = prepared.id
        ORDER BY posted.sequence_order
    LOOP
        IF EXISTS (
            SELECT 1
            FROM accounting.journal_entries reversal
            WHERE reversal.reversal_of_entry_id = original_entry.journal_entry_id
        ) THEN
            RAISE EXCEPTION 'A protected Regular source journal already has a reversal outside this collection-void audit.';
        END IF;

        created_reversal_entry_id := gen_random_uuid();
        reversal_source_key :=
            'regular-collection-void-reversal:'
            || p_collection_void_id::text
            || ':'
            || original_entry.journal_entry_id::text;

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
            'Controlled reversal of ' || original_entry.entry_number || ': '
                || original_entry.description,
            'draft',
            'regular_collection_void_reversal',
            p_collection_void_id::text,
            reversal_source_key,
            original_entry.journal_entry_id,
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
            original_line.line_number,
            original_line.account_id,
            original_line.description,
            original_line.credit,
            original_line.debit,
            original_line.client_id,
            original_line.loan_id
        FROM accounting.journal_lines original_line
        WHERE original_line.journal_entry_id = original_entry.journal_entry_id
        ORDER BY original_line.line_number;

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
                'reversal_of_entry_id', original_entry.journal_entry_id,
                'transaction_id', p_transaction_id,
                'collection_void_id', p_collection_void_id,
                'reason', normalized_reason
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
                'protected_regular_collection_void', true
            )
        );

        INSERT INTO accounting.regular_journal_reversal_entries (
            reversal_set_id,
            preparation_id,
            sequence_order,
            original_journal_entry_id,
            reversal_journal_entry_id,
            original_entry_number,
            reversal_entry_number,
            original_source_event_key,
            reversal_source_event_key
        ) VALUES (
            created_reversal_set_id,
            original_entry.preparation_id,
            original_entry.sequence_order,
            original_entry.journal_entry_id,
            created_reversal_entry_id,
            original_entry.entry_number,
            generated_number,
            original_entry.source_event_key,
            reversal_source_key
        );
    END LOOP;

    SELECT count(*)::integer
    INTO reversal_count
    FROM accounting.regular_journal_reversal_entries reversal_entry
    JOIN accounting.journal_entries reversal
      ON reversal.id = reversal_entry.reversal_journal_entry_id
    WHERE reversal_entry.reversal_set_id = created_reversal_set_id
      AND reversal.status = 'posted'
      AND reversal.entry_number = reversal_entry.reversal_entry_number
      AND reversal.source_event_key = reversal_entry.reversal_source_event_key;

    IF reversal_count <> actual_entry_count THEN
        RAISE EXCEPTION 'Protected Regular collection reversal did not complete atomically.';
    END IF;

    PERFORM set_config(
        'accounting.regular_collection_void_reversal_allowed',
        'off',
        true
    );

    RETURN created_reversal_set_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.guard_accounted_regular_collection_void()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    prepared_id UUID;
    actual_entry_count INTEGER;
    posted_journal_count INTEGER;
    posting_audit_count INTEGER;
    void_id UUID;
    reversal_set_count INTEGER;
BEGIN
    IF OLD.is_voided = false AND NEW.is_voided = true THEN
        SELECT prepared.id
        INTO prepared_id
        FROM accounting.regular_journal_draft_preparations prepared
        WHERE prepared.transaction_id = OLD.id;

        IF prepared_id IS NULL THEN
            RETURN NEW;
        END IF;

        SELECT
            count(*)::integer,
            count(*) FILTER (WHERE journal.status = 'posted')::integer,
            count(posted.journal_entry_id)::integer
        INTO actual_entry_count, posted_journal_count, posting_audit_count
        FROM accounting.regular_journal_draft_preparation_entries prepared_entry
        JOIN accounting.journal_entries journal
          ON journal.id = prepared_entry.journal_entry_id
        LEFT JOIN accounting.regular_journal_posting_entries posted
          ON posted.preparation_id = prepared_entry.preparation_id
         AND posted.sequence_order = prepared_entry.sequence_order
         AND posted.journal_entry_id = prepared_entry.journal_entry_id
        WHERE prepared_entry.preparation_id = prepared_id;

        IF posted_journal_count = 0 AND posting_audit_count = 0 THEN
            RETURN NEW;
        END IF;

        IF actual_entry_count <= 0
           OR posted_journal_count <> actual_entry_count
           OR posting_audit_count <> actual_entry_count THEN
            RAISE EXCEPTION 'An accounted Regular collection cannot be voided while its protected posting state is partial or inconsistent.';
        END IF;

        SELECT void_record.id
        INTO void_id
        FROM lending.collection_transaction_voids void_record
        WHERE void_record.transaction_id = OLD.id;

        IF void_id IS NULL THEN
            RAISE EXCEPTION 'An accounted Regular collection requires immutable collection-void evidence before it can be voided.';
        END IF;

        SELECT count(*)::integer
        INTO reversal_set_count
        FROM accounting.regular_journal_reversal_sets reversal
        WHERE reversal.transaction_id = OLD.id
          AND reversal.collection_void_id = void_id
          AND reversal.expected_entry_count = actual_entry_count
          AND reversal.reversed_entry_count = actual_entry_count;

        IF reversal_set_count <> 1 THEN
            RAISE EXCEPTION 'An accounted Regular collection cannot be voided until its protected reversing journals are posted and audited.';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_accounted_regular_collection_void_guard
    ON lending.collection_transactions;
CREATE TRIGGER accounting_accounted_regular_collection_void_guard
BEFORE UPDATE OF is_voided ON lending.collection_transactions
FOR EACH ROW EXECUTE FUNCTION accounting.guard_accounted_regular_collection_void();

CREATE OR REPLACE FUNCTION accounting.perform_controlled_regular_collection_void_reversal()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    business_posting_date DATE;
BEGIN
    IF OLD.is_voided = false AND NEW.is_voided = true THEN
        business_posting_date := (NEW.voided_at AT TIME ZONE 'Asia/Manila')::date;
        PERFORM set_config(
            'accounting.regular_collection_void_reversal_allowed',
            'on',
            true
        );
        PERFORM accounting.reverse_posted_regular_collection(
            OLD.id,
            (
                SELECT void_record.id
                FROM lending.collection_transaction_voids void_record
                WHERE void_record.transaction_id = OLD.id
            ),
            NEW.voided_by_user_id,
            business_posting_date,
            NEW.void_reason
        );
        PERFORM set_config(
            'accounting.regular_collection_void_reversal_allowed',
            'off',
            true
        );
    END IF;

    RETURN NEW;
END;
$$;

-- PostgreSQL runs triggers with the same timing/event alphabetically by name.
-- Prefix 00 guarantees the reversal is created before the fail-closed audit guard.
DROP TRIGGER IF EXISTS accounting_00_regular_collection_void_reversal
    ON lending.collection_transactions;
CREATE TRIGGER accounting_00_regular_collection_void_reversal
BEFORE UPDATE OF is_voided ON lending.collection_transactions
FOR EACH ROW EXECUTE FUNCTION accounting.perform_controlled_regular_collection_void_reversal();

COMMIT;
