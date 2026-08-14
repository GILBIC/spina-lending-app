BEGIN;

-- A6.3 hardening for 0091. The first disposable PostgreSQL proof exposed a
-- fail-closed defect in balance scoping: a LEFT JOIN could still sum lines whose
-- journal did not satisfy the target-period/posted predicate, including the newly
-- prepared close draft itself. Centralize the exact ledger-balance query so every
-- preparation/posting revalidation uses only the intended posted journal population.

CREATE OR REPLACE FUNCTION accounting.period_close_temporary_balances(
    p_period_id UUID,
    p_include_period_close BOOLEAN DEFAULT false
)
RETURNS TABLE (
    account_id UUID,
    account_code TEXT,
    account_name TEXT,
    account_type TEXT,
    period_debit_total NUMERIC(18,2),
    period_credit_total NUMERIC(18,2),
    debit_minus_credit_balance NUMERIC(18,2)
)
LANGUAGE sql
STABLE
AS $$
    WITH posted_lines AS (
        SELECT
            line.account_id,
            sum(line.debit)::numeric(18,2) AS debit_total,
            sum(line.credit)::numeric(18,2) AS credit_total
        FROM accounting.journal_entries journal
        JOIN accounting.journal_lines line
          ON line.journal_entry_id = journal.id
        WHERE journal.fiscal_period_id = p_period_id
          AND journal.status = 'posted'
          AND (p_include_period_close OR journal.source_type IS DISTINCT FROM 'period_close')
        GROUP BY line.account_id
    )
    SELECT
        account.id,
        account.code,
        account.name,
        account.account_type,
        coalesce(posted.debit_total, 0)::numeric(18,2),
        coalesce(posted.credit_total, 0)::numeric(18,2),
        (coalesce(posted.debit_total, 0) - coalesce(posted.credit_total, 0))::numeric(18,2)
    FROM accounting.accounts account
    LEFT JOIN posted_lines posted ON posted.account_id = account.id
    WHERE account.account_type IN ('income', 'expense')
      AND account.is_active
      AND account.is_posting
      AND coalesce(posted.debit_total, 0) - coalesce(posted.credit_total, 0) <> 0
    ORDER BY account.code;
$$;

CREATE OR REPLACE FUNCTION accounting.prepare_period_close(
    p_period_id UUID,
    p_actor_user_id UUID
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    period_row accounting.fiscal_periods%ROWTYPE;
    retained_account accounting.accounts%ROWTYPE;
    existing accounting.period_close_preparations%ROWTYPE;
    preparation_id UUID := gen_random_uuid();
    journal_id UUID;
    posted_journal_count INTEGER;
    temp_count INTEGER;
    close_debit_total NUMERIC(18,2);
    close_credit_total NUMERIC(18,2);
    net_income_value NUMERIC(18,2);
    retained_before NUMERIC(18,2);
    digest_source TEXT;
    close_digest_value TEXT;
BEGIN
    PERFORM accounting.require_period_close_management_actor(
        p_actor_user_id,
        'accounting.period.close.prepare'
    );
    PERFORM pg_advisory_xact_lock(hashtextextended('period-close:' || p_period_id::text, 0));

    SELECT * INTO period_row
    FROM accounting.fiscal_periods
    WHERE id = p_period_id
    FOR UPDATE;
    IF period_row.id IS NULL THEN
        RAISE EXCEPTION 'Accounting period was not found.';
    END IF;

    SELECT * INTO existing
    FROM accounting.period_close_preparations preparation
    WHERE preparation.fiscal_period_id = p_period_id;
    IF existing.id IS NOT NULL THEN
        RETURN existing.id;
    END IF;

    IF period_row.status <> 'review' THEN
        RAISE EXCEPTION 'Formal period-close preparation requires the accounting period to be in review.';
    END IF;
    IF EXISTS (
        SELECT 1 FROM accounting.journal_entries journal
        WHERE journal.fiscal_period_id = p_period_id
          AND journal.status = 'draft'
    ) THEN
        RAISE EXCEPTION 'Formal period-close preparation requires all journal drafts to be resolved first.';
    END IF;

    SELECT * INTO retained_account
    FROM accounting.accounts account
    WHERE account.system_key = 'retained_earnings';
    IF retained_account.id IS NULL
       OR retained_account.code <> '3100'
       OR retained_account.account_type <> 'equity'
       OR retained_account.normal_balance <> 'credit'
       OR NOT retained_account.is_active
       OR NOT retained_account.is_posting THEN
        RAISE EXCEPTION 'Exact active posting account 3100 Retained Earnings is required for formal period close.';
    END IF;

    SELECT count(*)::integer INTO posted_journal_count
    FROM accounting.journal_entries journal
    WHERE journal.fiscal_period_id = p_period_id
      AND journal.status = 'posted'
      AND journal.source_type IS DISTINCT FROM 'period_close';

    SELECT
        count(*)::integer,
        coalesce(sum(CASE WHEN balance.debit_minus_credit_balance < 0
                          THEN -balance.debit_minus_credit_balance ELSE 0 END), 0)::numeric(18,2),
        coalesce(sum(CASE WHEN balance.debit_minus_credit_balance > 0
                          THEN balance.debit_minus_credit_balance ELSE 0 END), 0)::numeric(18,2),
        coalesce(sum(CASE WHEN balance.debit_minus_credit_balance < 0
                          THEN -balance.debit_minus_credit_balance ELSE 0 END), 0)::numeric(18,2)
          - coalesce(sum(CASE WHEN balance.debit_minus_credit_balance > 0
                              THEN balance.debit_minus_credit_balance ELSE 0 END), 0)::numeric(18,2),
        coalesce(string_agg(
            balance.account_code || ':' || balance.account_type || ':'
            || to_char(balance.period_debit_total, 'FM999999999999990.00') || ':'
            || to_char(balance.period_credit_total, 'FM999999999999990.00') || ':'
            || to_char(balance.debit_minus_credit_balance, 'FM999999999999990.00'),
            '|' ORDER BY balance.account_code
        ), '')
    INTO temp_count, close_debit_total, close_credit_total, net_income_value, digest_source
    FROM accounting.period_close_temporary_balances(p_period_id, false) balance;

    SELECT coalesce(sum(line.credit - line.debit), 0)::numeric(18,2)
    INTO retained_before
    FROM accounting.journal_lines line
    JOIN accounting.journal_entries journal ON journal.id = line.journal_entry_id
    WHERE line.account_id = retained_account.id
      AND journal.status = 'posted'
      AND journal.posting_date <= period_row.end_date;

    close_digest_value := encode(sha256(convert_to(concat_ws('|',
        'period_close_retained_earnings_v1',
        period_row.id::text,
        period_row.label,
        period_row.start_date::text,
        period_row.end_date::text,
        posted_journal_count::text,
        temp_count::text,
        to_char(close_debit_total, 'FM999999999999990.00'),
        to_char(close_credit_total, 'FM999999999999990.00'),
        to_char(net_income_value, 'FM999999999999990.00'),
        retained_account.id::text,
        to_char(retained_before, 'FM999999999999990.00'),
        digest_source
    ), 'UTF8')), 'hex');

    IF temp_count > 0 THEN
        PERFORM set_config('accounting.period_close_journal_prepare_allowed', 'on', true);
        INSERT INTO accounting.journal_entries(
            fiscal_period_id, posting_date, description, status,
            source_type, source_reference, source_event_key,
            created_by_user_id, updated_at
        ) VALUES (
            period_row.id,
            period_row.end_date,
            'Formal period close - ' || period_row.label,
            'draft',
            'period_close',
            period_row.id::text,
            'period_close:' || period_row.id::text,
            p_actor_user_id,
            clock_timestamp()
        ) RETURNING id INTO journal_id;

        INSERT INTO accounting.journal_lines(
            journal_entry_id, line_number, account_id, description,
            debit, credit
        )
        SELECT
            journal_id,
            row_number() OVER (ORDER BY balance.account_code)::integer,
            balance.account_id,
            'Close temporary account to Retained Earnings',
            CASE WHEN balance.debit_minus_credit_balance < 0
                 THEN -balance.debit_minus_credit_balance ELSE 0 END,
            CASE WHEN balance.debit_minus_credit_balance > 0
                 THEN balance.debit_minus_credit_balance ELSE 0 END
        FROM accounting.period_close_temporary_balances(p_period_id, false) balance
        ORDER BY balance.account_code;

        IF net_income_value <> 0 THEN
            INSERT INTO accounting.journal_lines(
                journal_entry_id, line_number, account_id, description,
                debit, credit
            ) VALUES (
                journal_id,
                temp_count + 1,
                retained_account.id,
                'Transfer period profit or loss to Retained Earnings',
                CASE WHEN net_income_value < 0 THEN -net_income_value ELSE 0 END,
                CASE WHEN net_income_value > 0 THEN net_income_value ELSE 0 END
            );
        END IF;
        PERFORM set_config('accounting.period_close_journal_prepare_allowed', 'off', true);
    END IF;

    PERFORM set_config('accounting.period_close_preparation_insert_allowed', 'on', true);
    INSERT INTO accounting.period_close_preparations(
        id, fiscal_period_id, period_label, period_start_date, period_end_date,
        close_posting_date, journal_entry_id, source_event_key,
        preclose_posted_journal_count, temporary_account_count,
        temporary_closing_debit_total, temporary_closing_credit_total,
        net_income, retained_earnings_account_id, retained_earnings_balance_before,
        close_digest, policy_version, prepared_by_user_id
    ) VALUES (
        preparation_id, period_row.id, period_row.label, period_row.start_date,
        period_row.end_date, period_row.end_date, journal_id,
        'period_close:' || period_row.id::text,
        posted_journal_count, temp_count, close_debit_total, close_credit_total,
        net_income_value, retained_account.id, retained_before,
        close_digest_value, 'period_close_retained_earnings_v1', p_actor_user_id
    );
    PERFORM set_config('accounting.period_close_preparation_insert_allowed', 'off', true);

    PERFORM set_config('accounting.period_close_snapshot_insert_allowed', 'on', true);
    INSERT INTO accounting.period_close_account_snapshots(
        preparation_id, account_id, account_code, account_name, account_type,
        period_debit_total, period_credit_total, debit_minus_credit_balance,
        closing_debit, closing_credit, line_number
    )
    SELECT
        preparation_id,
        balance.account_id,
        balance.account_code,
        balance.account_name,
        balance.account_type,
        balance.period_debit_total,
        balance.period_credit_total,
        balance.debit_minus_credit_balance,
        CASE WHEN balance.debit_minus_credit_balance < 0
             THEN -balance.debit_minus_credit_balance ELSE 0 END,
        CASE WHEN balance.debit_minus_credit_balance > 0
             THEN balance.debit_minus_credit_balance ELSE 0 END,
        row_number() OVER (ORDER BY balance.account_code)::integer
    FROM accounting.period_close_temporary_balances(p_period_id, false) balance
    ORDER BY balance.account_code;
    PERFORM set_config('accounting.period_close_snapshot_insert_allowed', 'off', true);

    IF journal_id IS NOT NULL THEN
        INSERT INTO accounting.journal_events(journal_entry_id, event_type, actor_user_id, details)
        VALUES (
            journal_id,
            'draft_created',
            p_actor_user_id,
            jsonb_build_object(
                'source_type', 'period_close',
                'fiscal_period_id', period_row.id,
                'net_income', net_income_value,
                'close_digest', close_digest_value,
                'automatic_source_posting', false
            )
        );
    END IF;

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.period_close.prepared',
        'fiscal_period',
        period_row.id,
        jsonb_build_object(
            'preparation_id', preparation_id,
            'journal_entry_id', journal_id,
            'temporary_account_count', temp_count,
            'net_income', net_income_value,
            'retained_earnings_balance_before', retained_before,
            'close_digest', close_digest_value,
            'automatic_source_posting', false
        )
    );

    RETURN preparation_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.post_period_close(
    p_period_id UUID,
    p_actor_user_id UUID,
    p_confirmation_token TEXT,
    p_expected_close_digest TEXT,
    p_expected_net_income NUMERIC,
    p_expected_retained_earnings_account_code TEXT,
    p_expected_period_end_date DATE,
    p_policy_version TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    period_row accounting.fiscal_periods%ROWTYPE;
    preparation accounting.period_close_preparations%ROWTYPE;
    existing accounting.period_close_postings%ROWTYPE;
    retained_account accounting.accounts%ROWTYPE;
    close_journal accounting.journal_entries%ROWTYPE;
    normalized_token TEXT := lower(btrim(coalesce(p_confirmation_token, '')));
    normalized_digest TEXT := lower(btrim(coalesce(p_expected_close_digest, '')));
    normalized_re_code TEXT := btrim(coalesce(p_expected_retained_earnings_account_code, ''));
    current_posted_count INTEGER;
    current_temp_count INTEGER;
    current_close_debit NUMERIC(18,2);
    current_close_credit NUMERIC(18,2);
    current_net_income NUMERIC(18,2);
    current_retained_before NUMERIC(18,2);
    snapshot_count INTEGER;
    mismatch_count INTEGER;
    expected_line_count INTEGER;
    actual_line_count INTEGER;
    line_debit NUMERIC(18,2);
    line_credit NUMERIC(18,2);
    foreign_line_count INTEGER;
    entry_number_value TEXT;
    remaining_temp_count INTEGER;
    retained_after NUMERIC(18,2);
    confirmation_digest_value TEXT;
    closed_timestamp TIMESTAMPTZ;
    posting_id UUID;
BEGIN
    PERFORM accounting.require_period_close_management_actor(
        p_actor_user_id,
        'accounting.period.close.post'
    );
    IF normalized_token !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Formal period-close confirmation token is invalid.';
    END IF;
    IF normalized_digest !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Formal period-close evidence digest is invalid.';
    END IF;
    IF p_policy_version IS DISTINCT FROM 'period_close_retained_earnings_v1' THEN
        RAISE EXCEPTION 'Unsupported formal period-close policy version.';
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended('period-close:' || p_period_id::text, 0));

    SELECT * INTO preparation
    FROM accounting.period_close_preparations item
    WHERE item.fiscal_period_id = p_period_id;
    IF preparation.id IS NULL THEN
        RAISE EXCEPTION 'Formal period-close preparation was not found.';
    END IF;

    SELECT * INTO existing
    FROM accounting.period_close_postings posting
    WHERE posting.fiscal_period_id = p_period_id;
    IF existing.id IS NOT NULL THEN
        IF existing.confirmation_token = normalized_token
           AND existing.confirmed_close_digest = normalized_digest
           AND existing.confirmed_net_income = round(p_expected_net_income, 2)
           AND existing.confirmed_period_end_date = p_expected_period_end_date
           AND existing.policy_version = p_policy_version THEN
            RETURN existing.id;
        END IF;
        RAISE EXCEPTION 'Formal period close is already posted with different confirmation coordinates.';
    END IF;

    SELECT * INTO period_row
    FROM accounting.fiscal_periods
    WHERE id = p_period_id
    FOR UPDATE;
    IF period_row.id IS NULL OR period_row.status <> 'review' THEN
        RAISE EXCEPTION 'Formal period-close posting requires the exact accounting period to remain in review.';
    END IF;
    IF period_row.start_date <> preparation.period_start_date
       OR period_row.end_date <> preparation.period_end_date
       OR period_row.label <> preparation.period_label
       OR period_row.end_date <> p_expected_period_end_date THEN
        RAISE EXCEPTION 'Accounting period coordinates changed after formal close preparation.';
    END IF;

    SELECT * INTO retained_account
    FROM accounting.accounts account
    WHERE account.id = preparation.retained_earnings_account_id
    FOR SHARE;
    IF retained_account.id IS NULL
       OR retained_account.code <> '3100'
       OR retained_account.code <> normalized_re_code
       OR retained_account.system_key <> 'retained_earnings'
       OR retained_account.account_type <> 'equity'
       OR retained_account.normal_balance <> 'credit'
       OR NOT retained_account.is_active
       OR NOT retained_account.is_posting THEN
        RAISE EXCEPTION 'Exact 3100 Retained Earnings account is no longer posting-ready.';
    END IF;
    IF preparation.close_digest <> normalized_digest
       OR preparation.net_income <> round(p_expected_net_income, 2) THEN
        RAISE EXCEPTION 'Formal period-close confirmation does not match the immutable preparation snapshot.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM accounting.journal_entries journal
        WHERE journal.fiscal_period_id = p_period_id
          AND journal.status = 'draft'
          AND journal.id IS DISTINCT FROM preparation.journal_entry_id
    ) THEN
        RAISE EXCEPTION 'Unexpected journal draft exists after formal close preparation.';
    END IF;

    SELECT count(*)::integer INTO current_posted_count
    FROM accounting.journal_entries journal
    WHERE journal.fiscal_period_id = p_period_id
      AND journal.status = 'posted'
      AND journal.source_type IS DISTINCT FROM 'period_close';

    SELECT
        count(*)::integer,
        coalesce(sum(CASE WHEN balance.debit_minus_credit_balance < 0
                          THEN -balance.debit_minus_credit_balance ELSE 0 END), 0)::numeric(18,2),
        coalesce(sum(CASE WHEN balance.debit_minus_credit_balance > 0
                          THEN balance.debit_minus_credit_balance ELSE 0 END), 0)::numeric(18,2),
        coalesce(sum(CASE WHEN balance.debit_minus_credit_balance < 0
                          THEN -balance.debit_minus_credit_balance ELSE 0 END), 0)::numeric(18,2)
          - coalesce(sum(CASE WHEN balance.debit_minus_credit_balance > 0
                              THEN balance.debit_minus_credit_balance ELSE 0 END), 0)::numeric(18,2)
    INTO current_temp_count, current_close_debit, current_close_credit, current_net_income
    FROM accounting.period_close_temporary_balances(p_period_id, false) balance;

    SELECT coalesce(sum(line.credit - line.debit), 0)::numeric(18,2)
    INTO current_retained_before
    FROM accounting.journal_lines line
    JOIN accounting.journal_entries journal ON journal.id = line.journal_entry_id
    WHERE line.account_id = retained_account.id
      AND journal.status = 'posted'
      AND journal.posting_date <= period_row.end_date;

    IF current_posted_count <> preparation.preclose_posted_journal_count
       OR current_temp_count <> preparation.temporary_account_count
       OR current_close_debit <> preparation.temporary_closing_debit_total
       OR current_close_credit <> preparation.temporary_closing_credit_total
       OR current_net_income <> preparation.net_income
       OR current_retained_before <> preparation.retained_earnings_balance_before THEN
        RAISE EXCEPTION 'Posted ledger balances changed after formal period-close preparation.';
    END IF;

    SELECT count(*)::integer INTO snapshot_count
    FROM accounting.period_close_account_snapshots snapshot
    WHERE snapshot.preparation_id = preparation.id;
    IF snapshot_count <> preparation.temporary_account_count THEN
        RAISE EXCEPTION 'Formal period-close account snapshot count changed after preparation.';
    END IF;

    SELECT count(*)::integer INTO mismatch_count
    FROM accounting.period_close_temporary_balances(p_period_id, false) balance
    FULL JOIN (
        SELECT *
        FROM accounting.period_close_account_snapshots snapshot
        WHERE snapshot.preparation_id = preparation.id
    ) snapshot ON snapshot.account_id = balance.account_id
    WHERE balance.account_id IS NULL
       OR snapshot.account_id IS NULL
       OR snapshot.account_code <> balance.account_code
       OR snapshot.account_name <> balance.account_name
       OR snapshot.account_type <> balance.account_type
       OR snapshot.period_debit_total <> balance.period_debit_total
       OR snapshot.period_credit_total <> balance.period_credit_total
       OR snapshot.debit_minus_credit_balance <> balance.debit_minus_credit_balance;
    IF mismatch_count <> 0 THEN
        RAISE EXCEPTION 'Temporary-account close snapshot no longer matches the posted ledger.';
    END IF;

    IF preparation.journal_entry_id IS NOT NULL THEN
        SELECT * INTO close_journal
        FROM accounting.journal_entries journal
        WHERE journal.id = preparation.journal_entry_id
        FOR UPDATE;
        IF close_journal.id IS NULL
           OR close_journal.status <> 'draft'
           OR close_journal.source_type <> 'period_close'
           OR close_journal.source_reference <> p_period_id::text
           OR close_journal.source_event_key <> preparation.source_event_key
           OR close_journal.fiscal_period_id <> p_period_id
           OR close_journal.posting_date <> preparation.close_posting_date
           OR close_journal.reversal_of_entry_id IS NOT NULL THEN
            RAISE EXCEPTION 'Prepared formal period-close General Journal draft changed after preparation.';
        END IF;

        SELECT
            count(*)::integer,
            coalesce(sum(line.debit), 0)::numeric(18,2),
            coalesce(sum(line.credit), 0)::numeric(18,2),
            count(*) FILTER (
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM accounting.period_close_account_snapshots snapshot
                    WHERE snapshot.preparation_id = preparation.id
                      AND snapshot.account_id = line.account_id
                      AND snapshot.line_number = line.line_number
                )
                AND NOT (
                    preparation.net_income <> 0
                    AND line.account_id = retained_account.id
                    AND line.line_number = preparation.temporary_account_count + 1
                )
            )::integer
        INTO actual_line_count, line_debit, line_credit, foreign_line_count
        FROM accounting.journal_lines line
        WHERE line.journal_entry_id = preparation.journal_entry_id;

        expected_line_count := preparation.temporary_account_count
            + CASE WHEN preparation.net_income <> 0 THEN 1 ELSE 0 END;
        IF actual_line_count <> expected_line_count
           OR line_debit <> line_credit
           OR line_debit <= 0
           OR foreign_line_count <> 0 THEN
            RAISE EXCEPTION 'Prepared formal period-close journal is no longer exactly balanced or contains foreign lines.';
        END IF;

        SELECT count(*)::integer INTO mismatch_count
        FROM accounting.period_close_account_snapshots snapshot
        LEFT JOIN accounting.journal_lines line
          ON line.journal_entry_id = preparation.journal_entry_id
         AND line.account_id = snapshot.account_id
         AND line.line_number = snapshot.line_number
        WHERE snapshot.preparation_id = preparation.id
          AND (
              line.id IS NULL
              OR line.debit <> snapshot.closing_debit
              OR line.credit <> snapshot.closing_credit
              OR line.client_id IS NOT NULL
              OR line.loan_id IS NOT NULL
          );
        IF mismatch_count <> 0 THEN
            RAISE EXCEPTION 'Prepared temporary-account closing lines changed after formal close preparation.';
        END IF;

        IF preparation.net_income <> 0 AND NOT EXISTS (
            SELECT 1
            FROM accounting.journal_lines line
            WHERE line.journal_entry_id = preparation.journal_entry_id
              AND line.account_id = retained_account.id
              AND line.line_number = preparation.temporary_account_count + 1
              AND line.debit = CASE WHEN preparation.net_income < 0 THEN -preparation.net_income ELSE 0 END
              AND line.credit = CASE WHEN preparation.net_income > 0 THEN preparation.net_income ELSE 0 END
              AND line.client_id IS NULL
              AND line.loan_id IS NULL
        ) THEN
            RAISE EXCEPTION 'Prepared Retained Earnings close line changed after formal close preparation.';
        END IF;

        PERFORM set_config('accounting.period_close_journal_post_allowed', 'on', true);
        entry_number_value := accounting.post_journal_entry(
            preparation.journal_entry_id,
            p_actor_user_id
        );
        PERFORM set_config('accounting.period_close_journal_post_allowed', 'off', true);

        INSERT INTO accounting.journal_events(journal_entry_id, event_type, actor_user_id, details)
        VALUES (
            preparation.journal_entry_id,
            'posted',
            p_actor_user_id,
            jsonb_build_object(
                'entry_number', entry_number_value,
                'source_type', 'period_close',
                'fiscal_period_id', p_period_id,
                'net_income', preparation.net_income,
                'close_digest', preparation.close_digest,
                'automatic_source_posting', false
            )
        );
    ELSE
        IF preparation.temporary_account_count <> 0 OR preparation.net_income <> 0 THEN
            RAISE EXCEPTION 'Formal zero-activity close preparation is inconsistent.';
        END IF;
    END IF;

    IF coalesce(current_setting('accounting.period_close_force_audit_failure', true), '') = 'on' THEN
        RAISE EXCEPTION 'Forced formal period-close audit failure.';
    END IF;

    SELECT count(*)::integer INTO remaining_temp_count
    FROM accounting.period_close_temporary_balances(p_period_id, true);
    IF remaining_temp_count <> 0 THEN
        RAISE EXCEPTION 'Formal period close failed: one or more temporary income/expense accounts remain non-zero.';
    END IF;

    SELECT coalesce(sum(line.credit - line.debit), 0)::numeric(18,2)
    INTO retained_after
    FROM accounting.journal_lines line
    JOIN accounting.journal_entries journal ON journal.id = line.journal_entry_id
    WHERE line.account_id = retained_account.id
      AND journal.status = 'posted'
      AND journal.posting_date <= period_row.end_date;
    IF retained_after <> preparation.retained_earnings_balance_before + preparation.net_income THEN
        RAISE EXCEPTION 'Retained Earnings after close does not reconcile to the immutable pre-close balance plus period profit or loss.';
    END IF;

    confirmation_digest_value := encode(sha256(convert_to(concat_ws('|',
        p_policy_version,
        preparation.id::text,
        p_period_id::text,
        preparation.close_digest,
        to_char(preparation.net_income, 'FM999999999999990.00'),
        retained_account.id::text,
        to_char(preparation.retained_earnings_balance_before, 'FM999999999999990.00'),
        to_char(retained_after, 'FM999999999999990.00'),
        preparation.period_start_date::text,
        preparation.period_end_date::text,
        coalesce(preparation.journal_entry_id::text, 'no-journal'),
        coalesce(entry_number_value, 'no-entry-number'),
        normalized_token
    ), 'UTF8')), 'hex');

    PERFORM set_config('accounting.period_close_transition_allowed', 'on', true);
    PERFORM accounting.set_fiscal_period_status(p_period_id, 'closed', p_actor_user_id);
    PERFORM set_config('accounting.period_close_transition_allowed', 'off', true);

    SELECT closed_at INTO closed_timestamp
    FROM accounting.fiscal_periods
    WHERE id = p_period_id;

    PERFORM set_config('accounting.period_close_posting_insert_allowed', 'on', true);
    INSERT INTO accounting.period_close_postings(
        preparation_id, fiscal_period_id, journal_entry_id, entry_number,
        confirmation_token, confirmation_digest, confirmed_close_digest,
        confirmed_net_income, confirmed_retained_earnings_account_id,
        retained_earnings_balance_before, retained_earnings_balance_after,
        confirmed_period_start_date, confirmed_period_end_date,
        policy_version, posted_by_user_id, closed_at
    ) VALUES (
        preparation.id, p_period_id, preparation.journal_entry_id, entry_number_value,
        normalized_token, confirmation_digest_value, preparation.close_digest,
        preparation.net_income, retained_account.id,
        preparation.retained_earnings_balance_before, retained_after,
        preparation.period_start_date, preparation.period_end_date,
        p_policy_version, p_actor_user_id, closed_timestamp
    ) RETURNING id INTO posting_id;
    PERFORM set_config('accounting.period_close_posting_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.period_close.posted',
        'fiscal_period',
        p_period_id,
        jsonb_build_object(
            'preparation_id', preparation.id,
            'posting_id', posting_id,
            'journal_entry_id', preparation.journal_entry_id,
            'entry_number', entry_number_value,
            'net_income', preparation.net_income,
            'retained_earnings_balance_before', preparation.retained_earnings_balance_before,
            'retained_earnings_balance_after', retained_after,
            'confirmation_digest', confirmation_digest_value,
            'closed_at', closed_timestamp,
            'period_reopen_enabled', false,
            'automatic_source_posting', false
        )
    );

    RETURN posting_id;
END;
$$;

COMMENT ON FUNCTION accounting.period_close_temporary_balances(UUID, BOOLEAN) IS
'Exact A6.3 temporary-account balance source. It sums only posted journal lines from the requested fiscal period and excludes the period-close journal for pre-close snapshots unless explicitly requested for post-closing zero-balance proof.';

COMMIT;
