BEGIN;

-- Shared by close preparation, posting revalidation and the final zero-balance
-- invariant. Retired/nonposting accounts must never disappear from the ledger.
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
LANGUAGE plpgsql
VOLATILE
AS $$
BEGIN
    -- Keep chart flags stable through the enclosing preparation/post transaction.
    PERFORM account.id
    FROM accounting.accounts account
    WHERE account.account_type IN ('income', 'expense')
    ORDER BY account.id
    FOR SHARE;

    IF EXISTS (
        SELECT 1
        FROM accounting.accounts account
        JOIN accounting.journal_lines line ON line.account_id = account.id
        JOIN accounting.journal_entries journal ON journal.id = line.journal_entry_id
        WHERE account.account_type IN ('income', 'expense')
          AND (NOT account.is_active OR NOT account.is_posting)
          AND journal.fiscal_period_id = p_period_id
          AND journal.status = 'posted'
          AND (p_include_period_close OR journal.source_type IS DISTINCT FROM 'period_close')
        GROUP BY account.id
        HAVING sum(line.debit - line.credit) <> 0
    ) THEN
        RAISE EXCEPTION 'Formal period close requires accounting resolution of nonzero inactive or nonposting income/expense account balances.';
    END IF;

    RETURN QUERY
    WITH posted_lines AS (
        SELECT
            line.account_id,
            sum(line.debit)::numeric(18,2) AS debit_total,
            sum(line.credit)::numeric(18,2) AS credit_total
        FROM accounting.journal_entries journal
        JOIN accounting.journal_lines line ON line.journal_entry_id = journal.id
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
        posted.debit_total,
        posted.credit_total,
        (posted.debit_total - posted.credit_total)::numeric(18,2)
    FROM accounting.accounts account
    JOIN posted_lines posted ON posted.account_id = account.id
    WHERE account.account_type IN ('income', 'expense')
      AND posted.debit_total - posted.credit_total <> 0
    ORDER BY account.code;
END;
$$;

REVOKE ALL ON FUNCTION accounting.period_close_temporary_balances(UUID, BOOLEAN) FROM PUBLIC;

COMMIT;
