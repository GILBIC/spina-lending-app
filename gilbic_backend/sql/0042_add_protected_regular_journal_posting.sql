BEGIN;

INSERT INTO core.permissions (code, description)
VALUES (
    'accounting.regular_journal.post',
    'Explicitly post one complete protected Regular review set to the General Ledger after final fail-closed revalidation'
)
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code = 'accounting.regular_journal.post'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.regular_journal_posting_sets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id UUID NOT NULL
        REFERENCES lending.loans(id) ON DELETE RESTRICT,
    review_set_fingerprint TEXT NOT NULL,
    expected_transaction_count INTEGER NOT NULL
        CHECK (expected_transaction_count > 0),
    expected_entry_count INTEGER NOT NULL
        CHECK (expected_entry_count > 0),
    posted_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    posted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (review_set_fingerprint ~ '^[0-9a-f]{64}$'),
    UNIQUE (loan_id, review_set_fingerprint)
);

CREATE TABLE IF NOT EXISTS accounting.regular_journal_posting_entries (
    posting_set_id UUID NOT NULL
        REFERENCES accounting.regular_journal_posting_sets(id) ON DELETE RESTRICT,
    preparation_id UUID NOT NULL
        REFERENCES accounting.regular_journal_draft_preparations(id) ON DELETE RESTRICT,
    transaction_id UUID NOT NULL
        REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    sequence_order INTEGER NOT NULL CHECK (sequence_order > 0),
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    entry_number TEXT NOT NULL UNIQUE,
    source_event_key TEXT NOT NULL UNIQUE,
    PRIMARY KEY (posting_set_id, transaction_id, sequence_order),
    CHECK (btrim(entry_number) <> ''),
    CHECK (btrim(source_event_key) <> '')
);

CREATE INDEX IF NOT EXISTS regular_journal_posting_sets_loan_idx
    ON accounting.regular_journal_posting_sets (loan_id, posted_at DESC);

CREATE OR REPLACE FUNCTION accounting.guard_regular_journal_posting_record_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(
            current_setting('accounting.regular_journal_post_record_allowed', true),
            ''
       ) = 'on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Protected Regular journal posting audit records are immutable and must use the protected posting function.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_regular_journal_posting_set_guard
    ON accounting.regular_journal_posting_sets;
CREATE TRIGGER accounting_regular_journal_posting_set_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.regular_journal_posting_sets
FOR EACH ROW EXECUTE FUNCTION accounting.guard_regular_journal_posting_record_write();

DROP TRIGGER IF EXISTS accounting_regular_journal_posting_entry_guard
    ON accounting.regular_journal_posting_entries;
CREATE TRIGGER accounting_regular_journal_posting_entry_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.regular_journal_posting_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_regular_journal_posting_record_write();

CREATE OR REPLACE FUNCTION accounting.post_regular_journal_review_set(
    p_loan_id UUID,
    p_review_set_fingerprint TEXT,
    p_actor_user_id UUID
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    existing_post accounting.regular_journal_posting_sets%ROWTYPE;
    created_posting_set_id UUID;
    expected_transaction_count INTEGER;
    preparation_count INTEGER;
    expected_entry_count INTEGER;
    actual_entry_count INTEGER;
    draft_entry_count INTEGER;
    posted_entry_count INTEGER;
    audit_entry_count INTEGER;
    invalid_count INTEGER;
    generated_number TEXT;
    posting_entry RECORD;
BEGIN
    IF coalesce(p_review_set_fingerprint, '') !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Protected Regular journal review token is invalid.';
    END IF;

    -- Serialize preparation and posting on the Stage 5D.16 per-loan lock.
    PERFORM pg_advisory_xact_lock(
        hashtextextended('regular-journal-draft-loan:' || p_loan_id::text, 0)
    );

    -- Freeze every mutable source used by the protected evidence while the
    -- final checks and irreversible journal transitions run.
    LOCK TABLE
        lending.loan_collection_state,
        lending.loans,
        lending.loan_types,
        lending.collection_transactions
    IN SHARE MODE;

    LOCK TABLE
        accounting.opening_balance_workbooks,
        accounting.opening_balance_journal_preparations,
        accounting.opening_balance_journal_postings,
        accounting.opening_balance_loan_snapshot_batches,
        accounting.opening_balance_loan_measurement_snapshots,
        accounting.fiscal_periods,
        accounting.accounts,
        accounting.regular_journal_draft_preparations,
        accounting.regular_journal_draft_preparation_entries
    IN SHARE MODE;

    SELECT
        count(*)::integer,
        min(prepared.expected_set_transaction_count)::integer,
        coalesce(sum(prepared.expected_entry_count), 0)::integer
    INTO preparation_count, expected_transaction_count, expected_entry_count
    FROM accounting.regular_journal_draft_preparations prepared
    WHERE prepared.loan_id = p_loan_id
      AND prepared.review_set_fingerprint = p_review_set_fingerprint;

    IF preparation_count = 0 THEN
        RAISE EXCEPTION 'Protected Regular journal review set was not found.';
    END IF;

    SELECT count(*)::integer
    INTO invalid_count
    FROM accounting.regular_journal_draft_preparations prepared
    WHERE prepared.loan_id = p_loan_id
      AND prepared.review_set_fingerprint = p_review_set_fingerprint
      AND (
          prepared.expected_set_transaction_count <> expected_transaction_count
          OR prepared.expected_set_transaction_count <> preparation_count
          OR prepared.evidence_policy_version IS DISTINCT FROM
                'regular_cross_period_posting_ready_evidence_v1'
          OR prepared.draft_policy_version IS DISTINCT FROM
                'regular_journal_draft_v1'
      );

    IF invalid_count > 0 OR expected_transaction_count <> preparation_count THEN
        RAISE EXCEPTION 'Protected Regular journal review set preparation metadata is inconsistent.';
    END IF;

    SELECT *
    INTO existing_post
    FROM accounting.regular_journal_posting_sets posting
    WHERE posting.loan_id = p_loan_id
      AND posting.review_set_fingerprint = p_review_set_fingerprint
    FOR UPDATE;

    SELECT
        count(*)::integer,
        count(*) FILTER (WHERE journal.status = 'draft')::integer,
        count(*) FILTER (WHERE journal.status = 'posted')::integer
    INTO actual_entry_count, draft_entry_count, posted_entry_count
    FROM accounting.regular_journal_draft_preparations prepared
    JOIN accounting.regular_journal_draft_preparation_entries prepared_entry
      ON prepared_entry.preparation_id = prepared.id
    JOIN accounting.journal_entries journal
      ON journal.id = prepared_entry.journal_entry_id
    WHERE prepared.loan_id = p_loan_id
      AND prepared.review_set_fingerprint = p_review_set_fingerprint;

    IF actual_entry_count <> expected_entry_count THEN
        RAISE EXCEPTION 'Protected Regular journal review set is incomplete.';
    END IF;

    -- Exact retry succeeds only when the immutable audit and every posted
    -- journal still agree. Partial or unaudited posted states fail closed.
    IF existing_post.id IS NOT NULL THEN
        SELECT count(*)::integer
        INTO audit_entry_count
        FROM accounting.regular_journal_posting_entries posted_entry
        JOIN accounting.journal_entries journal
          ON journal.id = posted_entry.journal_entry_id
        JOIN accounting.regular_journal_draft_preparation_entries prepared_entry
          ON prepared_entry.journal_entry_id = journal.id
        JOIN accounting.regular_journal_draft_preparations prepared
          ON prepared.id = prepared_entry.preparation_id
        WHERE posted_entry.posting_set_id = existing_post.id
          AND prepared.loan_id = p_loan_id
          AND prepared.review_set_fingerprint = p_review_set_fingerprint
          AND journal.status = 'posted'
          AND journal.entry_number = posted_entry.entry_number
          AND journal.source_event_key = posted_entry.source_event_key;

        IF existing_post.expected_transaction_count <> expected_transaction_count
           OR existing_post.expected_entry_count <> expected_entry_count
           OR posted_entry_count <> expected_entry_count
           OR draft_entry_count <> 0
           OR audit_entry_count <> expected_entry_count THEN
            RAISE EXCEPTION 'Protected Regular journal posting audit does not match the posted review set.';
        END IF;
        RETURN existing_post.id;
    END IF;

    IF posted_entry_count > 0 OR draft_entry_count <> expected_entry_count THEN
        RAISE EXCEPTION 'Protected Regular review set contains a posted or non-draft journal without the complete protected posting audit.';
    END IF;

    -- Revalidate each operational collection boundary. A void/correction that
    -- changes a prepared source blocks posting.
    SELECT count(*)::integer
    INTO invalid_count
    FROM accounting.regular_journal_draft_preparations prepared
    LEFT JOIN lending.collection_transactions transaction
      ON transaction.id = prepared.transaction_id
    WHERE prepared.loan_id = p_loan_id
      AND prepared.review_set_fingerprint = p_review_set_fingerprint
      AND (
          transaction.id IS NULL
          OR transaction.loan_id <> p_loan_id
          OR transaction.is_voided
          OR transaction.entry_type NOT IN ('payment', 'advance')
          OR transaction.amount <= 0
      );

    IF invalid_count > 0 THEN
        RAISE EXCEPTION 'A protected Regular collection source changed or is no longer valid.';
    END IF;

    -- Revalidate journal identity, coordinates, active posting accounts and
    -- exact balance before any entry can be posted.
    SELECT count(*)::integer
    INTO invalid_count
    FROM accounting.regular_journal_draft_preparations prepared
    JOIN accounting.regular_journal_draft_preparation_entries prepared_entry
      ON prepared_entry.preparation_id = prepared.id
    JOIN accounting.journal_entries journal
      ON journal.id = prepared_entry.journal_entry_id
    JOIN accounting.fiscal_periods period
      ON period.id = journal.fiscal_period_id
    JOIN LATERAL (
        SELECT
            count(*)::integer AS line_count,
            coalesce(sum(line.debit), 0)::numeric(18,2) AS total_debit,
            coalesce(sum(line.credit), 0)::numeric(18,2) AS total_credit,
            count(*) FILTER (
                WHERE account.is_active = false OR account.is_posting = false
            )::integer AS invalid_account_count
        FROM accounting.journal_lines line
        JOIN accounting.accounts account ON account.id = line.account_id
        WHERE line.journal_entry_id = journal.id
    ) totals ON true
    WHERE prepared.loan_id = p_loan_id
      AND prepared.review_set_fingerprint = p_review_set_fingerprint
      AND (
          journal.status <> 'draft'
          OR journal.entry_number IS NOT NULL
          OR journal.source_event_key IS DISTINCT FROM prepared_entry.source_event_key
          OR period.status <> 'open'
          OR journal.posting_date NOT BETWEEN period.start_date AND period.end_date
          OR totals.line_count < 2
          OR totals.invalid_account_count > 0
          OR totals.total_debit <= 0
          OR totals.total_debit <> totals.total_credit
          OR (
              prepared_entry.entry_type = 'collection'
              AND (
                  journal.source_type IS DISTINCT FROM 'collection'
                  OR journal.source_reference IS DISTINCT FROM prepared.transaction_id::text
                  OR journal.source_event_key IS DISTINCT FROM
                        'collection:' || prepared.transaction_id::text
              )
          )
          OR (
              prepared_entry.entry_type = 'eir_accrual_period'
              AND (
                  journal.source_type IS DISTINCT FROM 'regular_eir_accrual'
                  OR journal.source_reference IS DISTINCT FROM
                        prepared.transaction_id::text || ':fiscal_period:' ||
                        journal.fiscal_period_id::text
                  OR journal.source_event_key IS DISTINCT FROM
                        'eir_accrual:collection:' || prepared.transaction_id::text ||
                        ':fiscal_period:' || journal.fiscal_period_id::text
              )
          )
      );

    IF invalid_count > 0 THEN
        RAISE EXCEPTION 'Protected Regular journal draft integrity, identity, period, account, or balance changed before posting.';
    END IF;

    -- Collection journal must still equal the source transaction date/amount.
    SELECT count(*)::integer
    INTO invalid_count
    FROM accounting.regular_journal_draft_preparations prepared
    JOIN lending.collection_transactions transaction
      ON transaction.id = prepared.transaction_id
    JOIN accounting.regular_journal_draft_preparation_entries prepared_entry
      ON prepared_entry.preparation_id = prepared.id
     AND prepared_entry.entry_type = 'collection'
    JOIN accounting.journal_entries journal
      ON journal.id = prepared_entry.journal_entry_id
    JOIN LATERAL (
        SELECT
            coalesce(sum(line.debit), 0)::numeric(18,2) AS total_debit,
            coalesce(sum(line.credit), 0)::numeric(18,2) AS total_credit
        FROM accounting.journal_lines line
        WHERE line.journal_entry_id = journal.id
    ) totals ON true
    WHERE prepared.loan_id = p_loan_id
      AND prepared.review_set_fingerprint = p_review_set_fingerprint
      AND (
          journal.posting_date <> transaction.collection_date
          OR totals.total_debit <> transaction.amount
          OR totals.total_credit <> transaction.amount
      );

    IF invalid_count > 0 THEN
        RAISE EXCEPTION 'Protected Regular collection journal no longer matches its source transaction date or amount.';
    END IF;

    -- EIR line pattern remains Dr 1120 / Cr 4000.
    SELECT count(*)::integer
    INTO invalid_count
    FROM accounting.regular_journal_draft_preparations prepared
    JOIN accounting.regular_journal_draft_preparation_entries prepared_entry
      ON prepared_entry.preparation_id = prepared.id
     AND prepared_entry.entry_type = 'eir_accrual_period'
    JOIN accounting.journal_entries journal
      ON journal.id = prepared_entry.journal_entry_id
    JOIN LATERAL (
        SELECT
            count(*)::integer AS line_count,
            count(*) FILTER (
                WHERE account.system_key = 'accrued_interest_receivable'
                  AND line.debit > 0 AND line.credit = 0
            )::integer AS debit_count,
            count(*) FILTER (
                WHERE account.system_key = 'interest_income_regular'
                  AND line.credit > 0 AND line.debit = 0
            )::integer AS credit_count
        FROM accounting.journal_lines line
        JOIN accounting.accounts account ON account.id = line.account_id
        WHERE line.journal_entry_id = journal.id
    ) pattern ON true
    WHERE prepared.loan_id = p_loan_id
      AND prepared.review_set_fingerprint = p_review_set_fingerprint
      AND (
          pattern.line_count <> 2
          OR pattern.debit_count <> 1
          OR pattern.credit_count <> 1
      );

    IF invalid_count > 0 THEN
        RAISE EXCEPTION 'Protected Regular EIR journal lines no longer match the approved 1120/4000 pattern.';
    END IF;

    -- Collection pattern remains Dr 1020; credits only to 1120/1100.
    SELECT count(*)::integer
    INTO invalid_count
    FROM accounting.regular_journal_draft_preparations prepared
    JOIN accounting.regular_journal_draft_preparation_entries prepared_entry
      ON prepared_entry.preparation_id = prepared.id
     AND prepared_entry.entry_type = 'collection'
    JOIN accounting.journal_entries journal
      ON journal.id = prepared_entry.journal_entry_id
    JOIN LATERAL (
        SELECT
            count(*) FILTER (
                WHERE account.system_key = 'cash_collector_custody'
                  AND line.debit > 0 AND line.credit = 0
            )::integer AS cash_debit_count,
            count(*) FILTER (
                WHERE line.credit > 0 AND line.debit = 0
                  AND account.system_key IN (
                      'accrued_interest_receivable',
                      'loans_receivable_regular'
                  )
            )::integer AS valid_credit_count,
            count(*) FILTER (
                WHERE NOT (
                    (account.system_key = 'cash_collector_custody'
                     AND line.debit > 0 AND line.credit = 0)
                    OR
                    (account.system_key IN (
                        'accrued_interest_receivable',
                        'loans_receivable_regular'
                     ) AND line.credit > 0 AND line.debit = 0)
                )
            )::integer AS invalid_pattern_count,
            count(*)::integer AS line_count
        FROM accounting.journal_lines line
        JOIN accounting.accounts account ON account.id = line.account_id
        WHERE line.journal_entry_id = journal.id
    ) pattern ON true
    WHERE prepared.loan_id = p_loan_id
      AND prepared.review_set_fingerprint = p_review_set_fingerprint
      AND (
          pattern.cash_debit_count <> 1
          OR pattern.valid_credit_count <> pattern.line_count - 1
          OR pattern.invalid_pattern_count <> 0
      );

    IF invalid_count > 0 THEN
        RAISE EXCEPTION 'Protected Regular collection journal lines no longer match the approved 1020/1120/1100 pattern.';
    END IF;

    PERFORM set_config('accounting.regular_journal_post_record_allowed', 'on', true);
    INSERT INTO accounting.regular_journal_posting_sets (
        loan_id,
        review_set_fingerprint,
        expected_transaction_count,
        expected_entry_count,
        posted_by_user_id
    )
    VALUES (
        p_loan_id,
        p_review_set_fingerprint,
        expected_transaction_count,
        expected_entry_count,
        p_actor_user_id
    )
    RETURNING id INTO created_posting_set_id;

    -- Stage 5D.16 permits protected draft->posted only while this local gate is on.
    PERFORM set_config('accounting.regular_journal_post_allowed', 'on', true);

    FOR posting_entry IN
        SELECT
            prepared.id AS preparation_id,
            prepared.transaction_id,
            prepared_entry.sequence_order,
            prepared_entry.journal_entry_id,
            prepared_entry.source_event_key,
            journal.posting_date
        FROM accounting.regular_journal_draft_preparations prepared
        JOIN accounting.regular_journal_draft_preparation_entries prepared_entry
          ON prepared_entry.preparation_id = prepared.id
        JOIN accounting.journal_entries journal
          ON journal.id = prepared_entry.journal_entry_id
        WHERE prepared.loan_id = p_loan_id
          AND prepared.review_set_fingerprint = p_review_set_fingerprint
        ORDER BY journal.posting_date, prepared.transaction_id, prepared_entry.sequence_order
        FOR UPDATE OF journal
    LOOP
        generated_number := accounting.post_journal_entry(
            posting_entry.journal_entry_id,
            p_actor_user_id
        );

        INSERT INTO accounting.journal_events (
            journal_entry_id,
            event_type,
            actor_user_id,
            details
        )
        VALUES (
            posting_entry.journal_entry_id,
            'posted',
            p_actor_user_id,
            jsonb_build_object(
                'entry_number', generated_number,
                'protected_posting', true,
                'review_set_fingerprint', p_review_set_fingerprint,
                'loan_id', p_loan_id,
                'automatic_source_posting', false
            )
        );

        INSERT INTO accounting.regular_journal_posting_entries (
            posting_set_id,
            preparation_id,
            transaction_id,
            sequence_order,
            journal_entry_id,
            entry_number,
            source_event_key
        )
        VALUES (
            created_posting_set_id,
            posting_entry.preparation_id,
            posting_entry.transaction_id,
            posting_entry.sequence_order,
            posting_entry.journal_entry_id,
            generated_number,
            posting_entry.source_event_key
        );
    END LOOP;

    SELECT count(*)::integer
    INTO audit_entry_count
    FROM accounting.regular_journal_posting_entries
    WHERE posting_set_id = created_posting_set_id;

    SELECT count(*)::integer
    INTO posted_entry_count
    FROM accounting.regular_journal_draft_preparations prepared
    JOIN accounting.regular_journal_draft_preparation_entries prepared_entry
      ON prepared_entry.preparation_id = prepared.id
    JOIN accounting.journal_entries journal
      ON journal.id = prepared_entry.journal_entry_id
    WHERE prepared.loan_id = p_loan_id
      AND prepared.review_set_fingerprint = p_review_set_fingerprint
      AND journal.status = 'posted'
      AND journal.entry_number IS NOT NULL;

    IF audit_entry_count <> expected_entry_count
       OR posted_entry_count <> expected_entry_count THEN
        RAISE EXCEPTION 'Protected Regular journal posting did not complete atomically.';
    END IF;

    RETURN created_posting_set_id;
END;
$$;

COMMIT;
