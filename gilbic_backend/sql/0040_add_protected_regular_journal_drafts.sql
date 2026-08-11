BEGIN;

INSERT INTO core.permissions (code, description)
VALUES (
    'accounting.regular_journal.prepare',
    'Create protected system-generated Regular source-event journal drafts from exact posting-ready evidence without posting them'
)
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code = 'accounting.regular_journal.prepare'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.regular_journal_draft_preparations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id UUID NOT NULL
        REFERENCES lending.loans(id) ON DELETE RESTRICT,
    transaction_id UUID NOT NULL UNIQUE
        REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    review_set_fingerprint TEXT NOT NULL,
    bundle_fingerprint TEXT NOT NULL,
    evidence_policy_version TEXT NOT NULL,
    draft_policy_version TEXT NOT NULL,
    expected_set_transaction_count INTEGER NOT NULL
        CHECK (expected_set_transaction_count > 0),
    expected_entry_count INTEGER NOT NULL CHECK (expected_entry_count > 0),
    prepared_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    prepared_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (review_set_fingerprint ~ '^[0-9a-f]{64}$'),
    CHECK (bundle_fingerprint ~ '^[0-9a-f]{64}$'),
    CHECK (btrim(evidence_policy_version) <> ''),
    CHECK (btrim(draft_policy_version) <> ''),
    UNIQUE (loan_id, transaction_id)
);

CREATE INDEX IF NOT EXISTS regular_journal_draft_preparations_review_set_idx
    ON accounting.regular_journal_draft_preparations
       (loan_id, review_set_fingerprint, prepared_at DESC);

CREATE TABLE IF NOT EXISTS accounting.regular_journal_draft_preparation_entries (
    preparation_id UUID NOT NULL
        REFERENCES accounting.regular_journal_draft_preparations(id)
        ON DELETE RESTRICT,
    sequence_order INTEGER NOT NULL CHECK (sequence_order > 0),
    entry_type TEXT NOT NULL
        CHECK (entry_type IN ('eir_accrual_period', 'collection')),
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    bundle_entry_key TEXT NOT NULL UNIQUE,
    source_event_key TEXT NOT NULL UNIQUE,
    PRIMARY KEY (preparation_id, sequence_order),
    CHECK (btrim(bundle_entry_key) <> ''),
    CHECK (btrim(source_event_key) <> '')
);

CREATE INDEX IF NOT EXISTS regular_journal_draft_preparations_loan_idx
    ON accounting.regular_journal_draft_preparations (loan_id, prepared_at DESC);

CREATE OR REPLACE FUNCTION accounting.guard_regular_journal_draft_preparation_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(
            current_setting('accounting.regular_journal_prepare_allowed', true),
            ''
       ) = 'on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Protected Regular journal preparation records are immutable and must use the protected preparation function.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_regular_journal_draft_preparation_guard
    ON accounting.regular_journal_draft_preparations;
CREATE TRIGGER accounting_regular_journal_draft_preparation_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.regular_journal_draft_preparations
FOR EACH ROW EXECUTE FUNCTION accounting.guard_regular_journal_draft_preparation_write();

DROP TRIGGER IF EXISTS accounting_regular_journal_draft_preparation_entry_guard
    ON accounting.regular_journal_draft_preparation_entries;
CREATE TRIGGER accounting_regular_journal_draft_preparation_entry_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.regular_journal_draft_preparation_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_regular_journal_draft_preparation_write();

CREATE OR REPLACE FUNCTION accounting.guard_regular_system_journal_entry_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    protected_entry BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM accounting.regular_journal_draft_preparation_entries prepared
        WHERE prepared.journal_entry_id = OLD.id
    )
    INTO protected_entry;

    IF NOT protected_entry THEN
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Protected Regular source-event journal drafts cannot be deleted through the General Journal.';
    END IF;

    IF OLD.status = 'draft' AND NEW.status = 'posted' THEN
        IF coalesce(
            current_setting('accounting.regular_journal_post_allowed', true),
            ''
        ) <> 'on' THEN
            RAISE EXCEPTION 'Protected Regular source-event journal drafts require the protected Regular posting workflow.';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'Protected Regular source-event journal drafts are system generated and cannot be edited.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_regular_system_journal_entry_guard
    ON accounting.journal_entries;
CREATE TRIGGER accounting_regular_system_journal_entry_guard
BEFORE UPDATE OR DELETE ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_regular_system_journal_entry_change();

CREATE OR REPLACE FUNCTION accounting.guard_regular_system_journal_line_change()
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
        FROM accounting.regular_journal_draft_preparation_entries prepared
        WHERE prepared.journal_entry_id = target_entry_id
    )
    INTO protected_entry;

    IF protected_entry
       AND coalesce(
            current_setting('accounting.regular_journal_prepare_allowed', true),
            ''
       ) <> 'on' THEN
        RAISE EXCEPTION 'Protected Regular source-event journal lines are system generated and immutable.';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_regular_system_journal_line_guard
    ON accounting.journal_lines;
CREATE TRIGGER accounting_regular_system_journal_line_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_lines
FOR EACH ROW EXECUTE FUNCTION accounting.guard_regular_system_journal_line_change();

-- Defense in depth: the General Journal POST endpoint is a manual-journal workflow.
-- It must not be able to post any system-generated draft by guessing its UUID.
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
    IF entry_row.status <> 'draft' OR entry_row.source_type <> 'manual' THEN
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

CREATE OR REPLACE FUNCTION accounting.create_regular_journal_draft_batch(
    p_loan_id UUID,
    p_transaction_id UUID,
    p_actor_user_id UUID,
    p_review_set_fingerprint TEXT,
    p_bundle_fingerprint TEXT,
    p_evidence_policy_version TEXT,
    p_draft_policy_version TEXT,
    p_expected_set_transaction_count INTEGER,
    p_entries JSONB
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    loan_row lending.loans%ROWTYPE;
    transaction_row lending.collection_transactions%ROWTYPE;
    existing_preparation accounting.regular_journal_draft_preparations%ROWTYPE;
    preparation_id UUID;
    entry_item JSONB;
    created_journal_id UUID;
    expected_count INTEGER;
    invalid_entry_count INTEGER;
    duplicate_count INTEGER;
    invalid_period_count INTEGER;
    invalid_line_count INTEGER;
    invalid_account_count INTEGER;
    invalid_eir_line_count INTEGER;
    invalid_collection_line_count INTEGER;
    entry_sequence INTEGER;
    entry_type_value TEXT;
    entry_source_type TEXT;
    entry_source_reference TEXT;
    entry_source_event_key TEXT;
    entry_bundle_key TEXT;
    entry_posting_date DATE;
    entry_period_id UUID;
    entry_period_label TEXT;
BEGIN
    IF p_draft_policy_version IS DISTINCT FROM 'regular_journal_draft_v1' THEN
        RAISE EXCEPTION 'Unsupported protected Regular journal draft policy version.';
    END IF;
    IF p_evidence_policy_version IS DISTINCT FROM
        'regular_cross_period_posting_ready_evidence_v1' THEN
        RAISE EXCEPTION 'Protected Regular journal draft requires the approved posting-ready evidence policy.';
    END IF;
    IF coalesce(p_review_set_fingerprint, '') !~ '^[0-9a-f]{64}$'
       OR coalesce(p_bundle_fingerprint, '') !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Protected Regular journal draft evidence fingerprint is invalid.';
    END IF;
    IF p_expected_set_transaction_count IS NULL
       OR p_expected_set_transaction_count < 1 THEN
        RAISE EXCEPTION 'Protected Regular journal draft review set count is invalid.';
    END IF;
    IF jsonb_typeof(p_entries) IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'Protected Regular journal draft entries must be an array.';
    END IF;

    expected_count := jsonb_array_length(p_entries);
    IF expected_count < 1 THEN
        RAISE EXCEPTION 'Protected Regular journal draft requires at least one posting-ready entry.';
    END IF;

    -- Serialize all protected preparation attempts for one loan. The application
    -- also takes this lock before its final read-only replay.
    PERFORM pg_advisory_xact_lock(
        hashtextextended('regular-journal-draft-loan:' || p_loan_id::text, 0)
    );

    -- Freeze the operational source tables before validating the supplied
    -- server-replayed evidence. Collection writers require ROW EXCLUSIVE locks,
    -- which conflict with SHARE, so they either commit before this point or wait.
    LOCK TABLE
        lending.loan_collection_state,
        lending.loans,
        lending.loan_types,
        lending.collection_transactions
    IN SHARE MODE;

    -- Fiscal-period/account configuration must not drift while the draft rows
    -- are validated and inserted.
    LOCK TABLE accounting.fiscal_periods, accounting.accounts IN SHARE MODE;

    SELECT *
    INTO loan_row
    FROM lending.loans
    WHERE id = p_loan_id;

    IF loan_row.id IS NULL THEN
        RAISE EXCEPTION 'Loan was not found for protected Regular journal preparation.';
    END IF;

    SELECT *
    INTO transaction_row
    FROM lending.collection_transactions
    WHERE id = p_transaction_id;

    IF transaction_row.id IS NULL
       OR transaction_row.loan_id <> p_loan_id THEN
        RAISE EXCEPTION 'Collection transaction does not belong to the protected Regular loan.';
    END IF;
    IF transaction_row.is_voided
       OR transaction_row.entry_type NOT IN ('payment', 'advance')
       OR transaction_row.amount <= 0 THEN
        RAISE EXCEPTION 'Only a non-voided positive payment or advance can create protected Regular journal drafts.';
    END IF;

    SELECT *
    INTO existing_preparation
    FROM accounting.regular_journal_draft_preparations prepared
    WHERE prepared.transaction_id = p_transaction_id;

    IF existing_preparation.id IS NOT NULL THEN
        IF existing_preparation.loan_id <> p_loan_id
           OR existing_preparation.review_set_fingerprint <> p_review_set_fingerprint
           OR existing_preparation.bundle_fingerprint <> p_bundle_fingerprint
           OR existing_preparation.evidence_policy_version <> p_evidence_policy_version
           OR existing_preparation.draft_policy_version <> p_draft_policy_version
           OR existing_preparation.expected_set_transaction_count
                <> p_expected_set_transaction_count
           OR existing_preparation.expected_entry_count <> expected_count THEN
            RAISE EXCEPTION 'Existing protected Regular journal preparation does not match the reviewed evidence.';
        END IF;

        SELECT count(*)
        INTO duplicate_count
        FROM accounting.regular_journal_draft_preparation_entries prepared_entry
        JOIN accounting.journal_entries journal
          ON journal.id = prepared_entry.journal_entry_id
        WHERE prepared_entry.preparation_id = existing_preparation.id
          AND journal.status = 'draft';

        IF duplicate_count <> expected_count THEN
            RAISE EXCEPTION 'Existing protected Regular journal preparation is incomplete or no longer draft.';
        END IF;
        RETURN existing_preparation.id;
    END IF;

    WITH parsed AS (
        SELECT
            item,
            ordinality::integer AS array_order,
            (item ->> 'sequence_order')::integer AS sequence_order,
            item ->> 'entry_type' AS entry_type,
            nullif(btrim(item ->> 'bundle_entry_key'), '') AS bundle_entry_key,
            nullif(btrim(item ->> 'source_type'), '') AS source_type,
            nullif(btrim(item ->> 'source_reference'), '') AS source_reference,
            nullif(btrim(item ->> 'source_event_key'), '') AS source_event_key,
            nullif(btrim(item ->> 'related_collection_source_event_key'), '')
                AS related_collection_source_event_key,
            (item ->> 'posting_date')::date AS posting_date,
            (item ->> 'amount')::numeric AS amount,
            (item ->> 'fiscal_period_id')::uuid AS fiscal_period_id,
            nullif(btrim(item ->> 'fiscal_period_label'), '') AS fiscal_period_label,
            (item ->> 'fiscal_period_start_date')::date AS fiscal_period_start_date,
            (item ->> 'fiscal_period_end_date')::date AS fiscal_period_end_date,
            item ->> 'fiscal_period_status' AS fiscal_period_status,
            jsonb_typeof(item -> 'journal_lines') AS journal_lines_type,
            CASE
                WHEN jsonb_typeof(item -> 'journal_lines') = 'array'
                THEN jsonb_array_length(item -> 'journal_lines')
                ELSE 0
            END AS journal_line_count,
            (item ->> 'total_debit')::numeric AS total_debit,
            (item ->> 'total_credit')::numeric AS total_credit,
            coalesce((item ->> 'balanced')::boolean, false) AS balanced
        FROM jsonb_array_elements(p_entries) WITH ORDINALITY source(item, ordinality)
    )
    SELECT count(*)
    INTO invalid_entry_count
    FROM parsed
    WHERE sequence_order <> array_order
       OR sequence_order < 1
       OR entry_type NOT IN ('eir_accrual_period', 'collection')
       OR bundle_entry_key IS NULL
       OR source_type IS NULL
       OR source_reference IS NULL
       OR source_event_key IS NULL
       OR related_collection_source_event_key IS DISTINCT FROM
            'collection:' || p_transaction_id::text
       OR amount <= 0
       OR amount <> round(amount, 2)
       OR total_debit <> amount
       OR total_credit <> amount
       OR balanced = false
       OR fiscal_period_label IS NULL
       OR fiscal_period_status <> 'open'
       OR journal_lines_type <> 'array'
       OR journal_line_count < 2;

    IF invalid_entry_count > 0 THEN
        RAISE EXCEPTION 'Protected Regular journal entry evidence is malformed or not exactly balanced.';
    END IF;

    WITH parsed AS (
        SELECT
            item ->> 'entry_type' AS entry_type,
            item ->> 'source_type' AS source_type,
            item ->> 'source_reference' AS source_reference,
            item ->> 'source_event_key' AS source_event_key,
            (item ->> 'fiscal_period_id')::uuid AS fiscal_period_id,
            (item ->> 'posting_date')::date AS posting_date,
            (item ->> 'amount')::numeric AS amount,
            (item ->> 'sequence_order')::integer AS sequence_order
        FROM jsonb_array_elements(p_entries) item
    )
    SELECT count(*)
    INTO invalid_entry_count
    FROM parsed
    WHERE (
        entry_type = 'collection'
        AND (
            source_type <> 'collection'
            OR source_reference <> p_transaction_id::text
            OR source_event_key <> 'collection:' || p_transaction_id::text
            OR posting_date <> transaction_row.collection_date
            OR amount <> transaction_row.amount
            OR sequence_order <> expected_count
        )
    ) OR (
        entry_type = 'eir_accrual_period'
        AND (
            source_type <> 'regular_eir_accrual'
            OR source_reference <>
                p_transaction_id::text || ':fiscal_period:' || fiscal_period_id::text
            OR source_event_key <>
                'eir_accrual:collection:' || p_transaction_id::text
                || ':fiscal_period:' || fiscal_period_id::text
            OR source_event_key =
                'eir_accrual:collection:' || p_transaction_id::text
        )
    );

    IF invalid_entry_count > 0 THEN
        RAISE EXCEPTION 'Protected Regular journal source identity or collection boundary is not exact.';
    END IF;

    SELECT count(*)
    INTO invalid_entry_count
    FROM jsonb_array_elements(p_entries) item
    WHERE item ->> 'entry_type' = 'collection';

    IF invalid_entry_count <> 1
       OR (p_entries -> (expected_count - 1) ->> 'entry_type') <> 'collection' THEN
        RAISE EXCEPTION 'Protected Regular journal sequence requires exactly one final collection entry.';
    END IF;

    WITH parsed AS (
        SELECT
            item ->> 'source_event_key' AS source_event_key,
            item ->> 'bundle_entry_key' AS bundle_entry_key
        FROM jsonb_array_elements(p_entries) item
    )
    SELECT
        count(*) - count(DISTINCT source_event_key),
        count(*) - count(DISTINCT bundle_entry_key)
    INTO duplicate_count, invalid_entry_count
    FROM parsed;

    IF duplicate_count > 0 OR invalid_entry_count > 0 THEN
        RAISE EXCEPTION 'Protected Regular journal source and bundle identities must be unique.';
    END IF;

    SELECT count(*)
    INTO duplicate_count
    FROM accounting.journal_entries journal
    WHERE journal.source_event_key IN (
        SELECT item ->> 'source_event_key'
        FROM jsonb_array_elements(p_entries) item
    );

    IF duplicate_count > 0 THEN
        RAISE EXCEPTION 'One or more protected Regular source events already have a journal entry.';
    END IF;

    WITH parsed AS (
        SELECT
            (item ->> 'fiscal_period_id')::uuid AS fiscal_period_id,
            item ->> 'fiscal_period_label' AS fiscal_period_label,
            (item ->> 'fiscal_period_start_date')::date AS fiscal_period_start_date,
            (item ->> 'fiscal_period_end_date')::date AS fiscal_period_end_date,
            (item ->> 'posting_date')::date AS posting_date
        FROM jsonb_array_elements(p_entries) item
    )
    SELECT count(*)
    INTO invalid_period_count
    FROM parsed
    LEFT JOIN accounting.fiscal_periods period
      ON period.id = parsed.fiscal_period_id
    WHERE period.id IS NULL
       OR period.label <> parsed.fiscal_period_label
       OR period.start_date <> parsed.fiscal_period_start_date
       OR period.end_date <> parsed.fiscal_period_end_date
       OR period.status <> 'open'
       OR parsed.posting_date NOT BETWEEN period.start_date AND period.end_date;

    IF invalid_period_count > 0 THEN
        RAISE EXCEPTION 'Protected Regular journal fiscal-period evidence changed or is no longer open.';
    END IF;

    WITH lines AS (
        SELECT
            entry_item ->> 'entry_type' AS entry_type,
            (entry_item ->> 'amount')::numeric AS entry_amount,
            line_item,
            line_ordinality::integer AS array_order,
            (line_item ->> 'line_order')::integer AS line_order,
            nullif(btrim(line_item ->> 'account_system_key'), '') AS account_system_key,
            line_item ->> 'side' AS side,
            (line_item ->> 'amount')::numeric AS line_amount,
            nullif(btrim(line_item ->> 'label'), '') AS label
        FROM jsonb_array_elements(p_entries) entry_item
        CROSS JOIN LATERAL jsonb_array_elements(entry_item -> 'journal_lines')
            WITH ORDINALITY lines(line_item, line_ordinality)
    )
    SELECT count(*)
    INTO invalid_line_count
    FROM lines
    WHERE line_order <> array_order
       OR line_order < 1
       OR account_system_key IS NULL
       OR side NOT IN ('debit', 'credit')
       OR line_amount <= 0
       OR line_amount <> round(line_amount, 2)
       OR label IS NULL;

    IF invalid_line_count > 0 THEN
        RAISE EXCEPTION 'Protected Regular journal line evidence is malformed.';
    END IF;

    WITH parsed_lines AS (
        SELECT
            entry_item ->> 'bundle_entry_key' AS bundle_entry_key,
            (entry_item ->> 'amount')::numeric AS entry_amount,
            line_item ->> 'side' AS side,
            (line_item ->> 'amount')::numeric AS line_amount
        FROM jsonb_array_elements(p_entries) entry_item
        CROSS JOIN LATERAL jsonb_array_elements(entry_item -> 'journal_lines') line_item
    ),
    totals AS (
        SELECT
            bundle_entry_key,
            max(entry_amount) AS entry_amount,
            count(*) AS line_count,
            coalesce(sum(line_amount) FILTER (WHERE side = 'debit'), 0) AS total_debit,
            coalesce(sum(line_amount) FILTER (WHERE side = 'credit'), 0) AS total_credit
        FROM parsed_lines
        GROUP BY bundle_entry_key
    )
    SELECT count(*)
    INTO invalid_line_count
    FROM totals
    WHERE line_count < 2
       OR total_debit <> entry_amount
       OR total_credit <> entry_amount;

    IF invalid_line_count > 0 THEN
        RAISE EXCEPTION 'Protected Regular journal lines do not balance exactly to each entry amount.';
    END IF;

    WITH keys AS (
        SELECT DISTINCT line_item ->> 'account_system_key' AS account_system_key
        FROM jsonb_array_elements(p_entries) entry_item
        CROSS JOIN LATERAL jsonb_array_elements(entry_item -> 'journal_lines') line_item
    )
    SELECT count(*)
    INTO invalid_account_count
    FROM keys
    LEFT JOIN accounting.accounts account
      ON account.system_key = keys.account_system_key
     AND account.is_active = true
     AND account.is_posting = true
    WHERE account.id IS NULL;

    IF invalid_account_count > 0 THEN
        RAISE EXCEPTION 'Protected Regular journal uses an unknown, inactive, or non-posting account.';
    END IF;

    WITH eir AS (
        SELECT
            entry_item ->> 'bundle_entry_key' AS bundle_entry_key,
            (entry_item ->> 'amount')::numeric AS entry_amount,
            line_item ->> 'account_system_key' AS account_system_key,
            line_item ->> 'side' AS side,
            (line_item ->> 'amount')::numeric AS line_amount
        FROM jsonb_array_elements(p_entries) entry_item
        CROSS JOIN LATERAL jsonb_array_elements(entry_item -> 'journal_lines') line_item
        WHERE entry_item ->> 'entry_type' = 'eir_accrual_period'
    ),
    checks AS (
        SELECT
            bundle_entry_key,
            max(entry_amount) AS entry_amount,
            count(*) AS line_count,
            count(*) FILTER (
                WHERE account_system_key = 'accrued_interest_receivable'
                  AND side = 'debit'
                  AND line_amount = entry_amount
            ) AS debit_count,
            count(*) FILTER (
                WHERE account_system_key = 'interest_income_regular'
                  AND side = 'credit'
                  AND line_amount = entry_amount
            ) AS credit_count
        FROM eir
        GROUP BY bundle_entry_key
    )
    SELECT count(*)
    INTO invalid_eir_line_count
    FROM checks
    WHERE line_count <> 2 OR debit_count <> 1 OR credit_count <> 1;

    IF invalid_eir_line_count > 0 THEN
        RAISE EXCEPTION 'Protected Regular EIR draft lines do not match the approved 1120/4000 accounting pattern.';
    END IF;

    WITH collection_lines AS (
        SELECT
            (entry_item ->> 'amount')::numeric AS entry_amount,
            line_item ->> 'account_system_key' AS account_system_key,
            line_item ->> 'side' AS side,
            (line_item ->> 'amount')::numeric AS line_amount
        FROM jsonb_array_elements(p_entries) entry_item
        CROSS JOIN LATERAL jsonb_array_elements(entry_item -> 'journal_lines') line_item
        WHERE entry_item ->> 'entry_type' = 'collection'
    )
    SELECT count(*)
    INTO invalid_collection_line_count
    FROM (
        SELECT
            max(entry_amount) AS entry_amount,
            count(*) FILTER (
                WHERE account_system_key = 'cash_collector_custody'
                  AND side = 'debit'
                  AND line_amount = entry_amount
            ) AS cash_debit_count,
            count(*) FILTER (
                WHERE side = 'credit'
                  AND account_system_key IN (
                      'accrued_interest_receivable',
                      'loans_receivable_regular'
                  )
            ) AS valid_credit_count,
            count(*) FILTER (
                WHERE NOT (
                    (account_system_key = 'cash_collector_custody' AND side = 'debit')
                    OR (
                        side = 'credit'
                        AND account_system_key IN (
                            'accrued_interest_receivable',
                            'loans_receivable_regular'
                        )
                    )
                )
            ) AS invalid_pattern_count,
            count(*) AS total_line_count
        FROM collection_lines
    ) checked
    WHERE cash_debit_count <> 1
       OR valid_credit_count <> total_line_count - 1
       OR invalid_pattern_count <> 0;

    IF invalid_collection_line_count > 0 THEN
        RAISE EXCEPTION 'Protected Regular collection draft lines do not match the approved 1020/1120/1100 accounting pattern.';
    END IF;

    PERFORM set_config('accounting.regular_journal_prepare_allowed', 'on', true);

    INSERT INTO accounting.regular_journal_draft_preparations (
        loan_id,
        transaction_id,
        review_set_fingerprint,
        bundle_fingerprint,
        evidence_policy_version,
        draft_policy_version,
        expected_set_transaction_count,
        expected_entry_count,
        prepared_by_user_id
    )
    VALUES (
        p_loan_id,
        p_transaction_id,
        p_review_set_fingerprint,
        p_bundle_fingerprint,
        p_evidence_policy_version,
        p_draft_policy_version,
        p_expected_set_transaction_count,
        expected_count,
        p_actor_user_id
    )
    RETURNING id INTO preparation_id;

    FOR entry_item IN
        SELECT item
        FROM jsonb_array_elements(p_entries) item
        ORDER BY (item ->> 'sequence_order')::integer
    LOOP
        entry_sequence := (entry_item ->> 'sequence_order')::integer;
        entry_type_value := entry_item ->> 'entry_type';
        entry_source_type := entry_item ->> 'source_type';
        entry_source_reference := entry_item ->> 'source_reference';
        entry_source_event_key := entry_item ->> 'source_event_key';
        entry_bundle_key := entry_item ->> 'bundle_entry_key';
        entry_posting_date := (entry_item ->> 'posting_date')::date;
        entry_period_id := (entry_item ->> 'fiscal_period_id')::uuid;
        entry_period_label := entry_item ->> 'fiscal_period_label';

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
            entry_period_id,
            entry_posting_date,
            CASE
                WHEN entry_type_value = 'collection'
                    THEN 'Protected Regular collection ' || p_transaction_id::text
                ELSE 'Protected Regular EIR accrual for collection '
                    || p_transaction_id::text || ' - ' || entry_period_label
            END,
            'draft',
            entry_source_type,
            entry_source_reference,
            entry_source_event_key,
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
            credit,
            client_id,
            loan_id
        )
        SELECT
            created_journal_id,
            (line_item ->> 'line_order')::integer,
            account.id,
            line_item ->> 'label',
            CASE WHEN line_item ->> 'side' = 'debit'
                THEN (line_item ->> 'amount')::numeric ELSE 0 END,
            CASE WHEN line_item ->> 'side' = 'credit'
                THEN (line_item ->> 'amount')::numeric ELSE 0 END,
            loan_row.client_id,
            p_loan_id
        FROM jsonb_array_elements(entry_item -> 'journal_lines') line_item
        JOIN accounting.accounts account
          ON account.system_key = line_item ->> 'account_system_key'
        ORDER BY (line_item ->> 'line_order')::integer;

        INSERT INTO accounting.journal_events (
            journal_entry_id, event_type, actor_user_id, details
        )
        VALUES (
            created_journal_id,
            'draft_created',
            p_actor_user_id,
            jsonb_build_object(
                'source_type', entry_source_type,
                'transaction_id', p_transaction_id,
                'sequence_order', entry_sequence,
                'bundle_entry_key', entry_bundle_key,
                'review_set_fingerprint', p_review_set_fingerprint,
                'bundle_fingerprint', p_bundle_fingerprint,
                'draft_policy_version', p_draft_policy_version,
                'posting_enabled', false,
                'automatic_source_posting_enabled', false
            )
        );

        INSERT INTO accounting.regular_journal_draft_preparation_entries (
            preparation_id,
            sequence_order,
            entry_type,
            journal_entry_id,
            bundle_entry_key,
            source_event_key
        )
        VALUES (
            preparation_id,
            entry_sequence,
            entry_type_value,
            created_journal_id,
            entry_bundle_key,
            entry_source_event_key
        );
    END LOOP;

    RETURN preparation_id;
END;
$$;

CREATE OR REPLACE VIEW accounting.regular_journal_draft_preparation_status AS
SELECT
    preparation.id AS preparation_id,
    preparation.loan_id,
    preparation.transaction_id,
    preparation.review_set_fingerprint,
    preparation.bundle_fingerprint,
    preparation.evidence_policy_version,
    preparation.draft_policy_version,
    preparation.expected_set_transaction_count,
    preparation.expected_entry_count,
    preparation.prepared_by_user_id,
    preparation.prepared_at,
    coalesce(entries.actual_entry_count, 0)::bigint AS actual_entry_count,
    coalesce(entries.draft_entry_count, 0)::bigint AS draft_entry_count,
    coalesce(entries.posted_entry_count, 0)::bigint AS posted_entry_count,
    coalesce(entries.total_debit, 0)::numeric(18,2) AS total_debit,
    coalesce(entries.total_credit, 0)::numeric(18,2) AS total_credit,
    (
        coalesce(entries.actual_entry_count, 0) = preparation.expected_entry_count
        AND coalesce(entries.draft_entry_count, 0) = preparation.expected_entry_count
        AND coalesce(entries.posted_entry_count, 0) = 0
        AND coalesce(entries.invalid_identity_count, 0) = 0
        AND coalesce(entries.invalid_period_count, 0) = 0
        AND coalesce(entries.unbalanced_entry_count, 0) = 0
    ) AS draft_integrity_ready,
    false AS regular_journal_posting_enabled,
    false AS automatic_source_posting_enabled,
    CASE
        WHEN coalesce(entries.actual_entry_count, 0) <> preparation.expected_entry_count
            THEN 'Prepared Regular journal entry count no longer matches the protected evidence.'
        WHEN coalesce(entries.posted_entry_count, 0) > 0
            THEN 'A protected Regular journal was posted outside the disabled Stage 5D.16 boundary.'
        WHEN coalesce(entries.draft_entry_count, 0) <> preparation.expected_entry_count
            THEN 'One or more protected Regular journals are no longer in draft status.'
        WHEN coalesce(entries.invalid_identity_count, 0) > 0
            THEN 'A protected Regular journal source identity no longer matches its immutable preparation mapping.'
        WHEN coalesce(entries.invalid_period_count, 0) > 0
            THEN 'A protected Regular journal fiscal period is no longer open or does not contain its posting date.'
        WHEN coalesce(entries.unbalanced_entry_count, 0) > 0
            THEN 'A protected Regular journal is no longer exactly balanced.'
        ELSE NULL
    END AS draft_integrity_blocker
FROM accounting.regular_journal_draft_preparations preparation
LEFT JOIN LATERAL (
    SELECT
        count(*) AS actual_entry_count,
        count(*) FILTER (WHERE journal.status = 'draft') AS draft_entry_count,
        count(*) FILTER (WHERE journal.status = 'posted') AS posted_entry_count,
        coalesce(sum(line_totals.total_debit), 0) AS total_debit,
        coalesce(sum(line_totals.total_credit), 0) AS total_credit,
        count(*) FILTER (
            WHERE journal.source_event_key <> prepared_entry.source_event_key
               OR (
                   prepared_entry.entry_type = 'collection'
                   AND (
                       journal.source_type <> 'collection'
                       OR journal.source_reference <> preparation.transaction_id::text
                       OR journal.source_event_key <>
                           'collection:' || preparation.transaction_id::text
                   )
               )
               OR (
                   prepared_entry.entry_type = 'eir_accrual_period'
                   AND (
                       journal.source_type <> 'regular_eir_accrual'
                       OR journal.source_event_key NOT LIKE
                           'eir_accrual:collection:' || preparation.transaction_id::text
                           || ':fiscal_period:%'
                   )
               )
        ) AS invalid_identity_count,
        count(*) FILTER (
            WHERE period.status <> 'open'
               OR journal.posting_date NOT BETWEEN period.start_date AND period.end_date
        ) AS invalid_period_count,
        count(*) FILTER (
            WHERE line_totals.line_count < 2
               OR line_totals.total_debit <= 0
               OR line_totals.total_debit <> line_totals.total_credit
        ) AS unbalanced_entry_count
    FROM accounting.regular_journal_draft_preparation_entries prepared_entry
    JOIN accounting.journal_entries journal
      ON journal.id = prepared_entry.journal_entry_id
    JOIN accounting.fiscal_periods period
      ON period.id = journal.fiscal_period_id
    LEFT JOIN LATERAL (
        SELECT
            count(*) AS line_count,
            coalesce(sum(line.debit), 0) AS total_debit,
            coalesce(sum(line.credit), 0) AS total_credit
        FROM accounting.journal_lines line
        WHERE line.journal_entry_id = journal.id
    ) line_totals ON true
    WHERE prepared_entry.preparation_id = preparation.id
) entries ON true;

COMMIT;
