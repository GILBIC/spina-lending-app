BEGIN;

CREATE SCHEMA IF NOT EXISTS accounting;
REVOKE ALL ON SCHEMA accounting FROM PUBLIC;

INSERT INTO core.permissions (code, description)
VALUES
    ('accounting.view', 'View the SPINA accounting foundation and financial control center')
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission ON permission.code = 'accounting.view'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT NOT NULL UNIQUE,
    system_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    account_type TEXT NOT NULL
        CHECK (account_type IN ('asset', 'liability', 'equity', 'income', 'expense')),
    normal_balance TEXT NOT NULL
        CHECK (normal_balance IN ('debit', 'credit')),
    is_posting BOOLEAN NOT NULL DEFAULT true,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (btrim(code) <> ''),
    CHECK (btrim(system_key) <> ''),
    CHECK (btrim(name) <> '')
);

CREATE INDEX IF NOT EXISTS accounting_accounts_type_code_idx
    ON accounting.accounts (account_type, code);

INSERT INTO accounting.accounts (
    code, system_key, name, account_type, normal_balance, is_posting
)
VALUES
    ('1010', 'cash_office', 'Cash - Office', 'asset', 'debit', true),
    ('1020', 'cash_collector_custody', 'Cash - Collector Custody', 'asset', 'debit', true),
    ('1030', 'cash_bank_gcash', 'Cash - Bank / GCash', 'asset', 'debit', true),
    ('1100', 'loans_receivable_regular', 'Loans Receivable - Regular', 'asset', 'debit', true),
    ('1110', 'loans_receivable_7x7', 'Loans Receivable - 7x7', 'asset', 'debit', true),
    ('1120', 'accrued_interest_receivable', 'Accrued Interest Receivable', 'asset', 'debit', true),
    ('1190', 'allowance_expected_credit_loss', 'Allowance for Expected Credit Loss', 'asset', 'credit', true),
    ('2000', 'accounts_payable', 'Accounts Payable', 'liability', 'credit', true),
    ('2100', 'tax_payables', 'Tax Payables', 'liability', 'credit', true),
    ('3000', 'capital', 'Capital', 'equity', 'credit', true),
    ('3100', 'retained_earnings', 'Retained Earnings', 'equity', 'credit', true),
    ('4000', 'interest_income_regular', 'Interest Income - Regular', 'income', 'credit', true),
    ('4010', 'interest_income_7x7', 'Interest Income - 7x7', 'income', 'credit', true),
    ('4090', 'other_lending_income', 'Other Lending Income', 'income', 'credit', true),
    ('5000', 'credit_loss_expense', 'Credit Loss Expense', 'expense', 'debit', true),
    ('5100', 'salaries_wages_expense', 'Salaries and Wages Expense', 'expense', 'debit', true),
    ('5110', 'employer_contributions_expense', 'Employer Contributions Expense', 'expense', 'debit', true),
    ('5200', 'rent_expense', 'Rent Expense', 'expense', 'debit', true),
    ('5210', 'utilities_expense', 'Utilities Expense', 'expense', 'debit', true),
    ('5220', 'transportation_expense', 'Transportation Expense', 'expense', 'debit', true),
    ('5230', 'professional_fees_expense', 'Professional Fees Expense', 'expense', 'debit', true),
    ('5240', 'bank_charges_expense', 'Bank Charges Expense', 'expense', 'debit', true),
    ('5290', 'other_operating_expense', 'Other Operating Expense', 'expense', 'debit', true)
ON CONFLICT (system_key) DO UPDATE SET
    code = excluded.code,
    name = excluded.name,
    account_type = excluded.account_type,
    normal_balance = excluded.normal_balance,
    is_posting = excluded.is_posting,
    is_active = true,
    updated_at = now();

CREATE TABLE IF NOT EXISTS accounting.fiscal_periods (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    label TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'review', 'closed')),
    closed_by_user_id UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (end_date >= start_date),
    CHECK (btrim(label) <> ''),
    CHECK (
        (status = 'closed' AND closed_by_user_id IS NOT NULL AND closed_at IS NOT NULL)
        OR
        (status <> 'closed' AND closed_by_user_id IS NULL AND closed_at IS NULL)
    ),
    UNIQUE (start_date, end_date)
);

CREATE INDEX IF NOT EXISTS accounting_fiscal_period_status_idx
    ON accounting.fiscal_periods (status, start_date, end_date);

CREATE OR REPLACE FUNCTION accounting.guard_fiscal_period()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.status = 'closed' THEN
        RAISE EXCEPTION 'Closed accounting periods are immutable.';
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

DROP TRIGGER IF EXISTS accounting_fiscal_period_guard
    ON accounting.fiscal_periods;
CREATE TRIGGER accounting_fiscal_period_guard
BEFORE INSERT OR UPDATE ON accounting.fiscal_periods
FOR EACH ROW EXECUTE FUNCTION accounting.guard_fiscal_period();

CREATE SEQUENCE IF NOT EXISTS accounting.journal_number_seq START WITH 1;

CREATE TABLE IF NOT EXISTS accounting.journal_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entry_number TEXT UNIQUE,
    fiscal_period_id UUID NOT NULL
        REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    posting_date DATE NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'posted')),
    source_type TEXT,
    source_reference TEXT,
    source_event_key TEXT UNIQUE,
    reversal_of_entry_id UUID UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    created_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    posted_by_user_id UUID
        REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    posted_at TIMESTAMPTZ,
    CHECK (btrim(description) <> ''),
    CHECK (source_type IS NULL OR btrim(source_type) <> ''),
    CHECK (source_reference IS NULL OR btrim(source_reference) <> ''),
    CHECK (source_event_key IS NULL OR btrim(source_event_key) <> ''),
    CHECK (
        (status = 'draft'
            AND entry_number IS NULL
            AND posted_by_user_id IS NULL
            AND posted_at IS NULL)
        OR
        (status = 'posted'
            AND entry_number IS NOT NULL
            AND posted_by_user_id IS NOT NULL
            AND posted_at IS NOT NULL)
    ),
    CHECK (reversal_of_entry_id IS NULL OR reversal_of_entry_id <> id)
);

CREATE INDEX IF NOT EXISTS accounting_journal_entries_period_date_idx
    ON accounting.journal_entries (fiscal_period_id, posting_date);
CREATE INDEX IF NOT EXISTS accounting_journal_entries_status_date_idx
    ON accounting.journal_entries (status, posting_date);
CREATE INDEX IF NOT EXISTS accounting_journal_entries_source_idx
    ON accounting.journal_entries (source_type, source_reference)
    WHERE source_type IS NOT NULL;

CREATE TABLE IF NOT EXISTS accounting.journal_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    journal_entry_id UUID NOT NULL
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    line_number INTEGER NOT NULL CHECK (line_number > 0),
    account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    description TEXT NOT NULL DEFAULT '',
    debit NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (debit >= 0),
    credit NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (credit >= 0),
    client_id UUID REFERENCES lending.clients(id) ON DELETE RESTRICT,
    loan_id UUID REFERENCES lending.loans(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (debit > 0 AND credit = 0)
        OR
        (credit > 0 AND debit = 0)
    ),
    UNIQUE (journal_entry_id, line_number)
);

CREATE INDEX IF NOT EXISTS accounting_journal_lines_account_idx
    ON accounting.journal_lines (account_id, journal_entry_id);
CREATE INDEX IF NOT EXISTS accounting_journal_lines_loan_idx
    ON accounting.journal_lines (loan_id)
    WHERE loan_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS accounting_journal_lines_client_idx
    ON accounting.journal_lines (client_id)
    WHERE client_id IS NOT NULL;

CREATE OR REPLACE FUNCTION accounting.guard_journal_entry_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.status = 'posted' THEN
            RAISE EXCEPTION 'Posted journal entries cannot be deleted.';
        END IF;
        RETURN OLD;
    END IF;

    IF OLD.status = 'posted' THEN
        RAISE EXCEPTION 'Posted journal entries are immutable; create a reversal instead.';
    END IF;

    IF NEW.status = 'posted'
       AND coalesce(current_setting('spina.accounting_post', true), '') <> 'on' THEN
        RAISE EXCEPTION 'Journal entries can only be posted through the accounting posting function.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_journal_entry_guard
    ON accounting.journal_entries;
CREATE TRIGGER accounting_journal_entry_guard
BEFORE UPDATE OR DELETE ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_journal_entry_change();

CREATE OR REPLACE FUNCTION accounting.guard_journal_line_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    parent_status TEXT;
    target_entry UUID;
BEGIN
    IF TG_OP = 'UPDATE' AND NEW.journal_entry_id <> OLD.journal_entry_id THEN
        RAISE EXCEPTION 'Journal lines cannot be moved between journal entries.';
    END IF;

    target_entry := CASE WHEN TG_OP = 'DELETE'
        THEN OLD.journal_entry_id ELSE NEW.journal_entry_id END;

    SELECT status
    INTO parent_status
    FROM accounting.journal_entries
    WHERE id = target_entry;

    IF parent_status IS DISTINCT FROM 'draft' THEN
        RAISE EXCEPTION 'Lines of a posted journal entry are immutable.';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_journal_line_guard
    ON accounting.journal_lines;
CREATE TRIGGER accounting_journal_line_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_lines
FOR EACH ROW EXECUTE FUNCTION accounting.guard_journal_line_change();

CREATE OR REPLACE FUNCTION accounting.post_journal_entry(
    p_entry_id UUID,
    p_actor_user_id UUID
)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    entry_row accounting.journal_entries%ROWTYPE;
    period_row accounting.fiscal_periods%ROWTYPE;
    line_count INTEGER;
    invalid_account_count INTEGER;
    total_debit NUMERIC(18,2);
    total_credit NUMERIC(18,2);
    generated_number TEXT;
BEGIN
    SELECT * INTO entry_row
    FROM accounting.journal_entries
    WHERE id = p_entry_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Journal entry was not found.';
    END IF;
    IF entry_row.status <> 'draft' THEN
        RAISE EXCEPTION 'Only a draft journal entry can be posted.';
    END IF;

    SELECT * INTO period_row
    FROM accounting.fiscal_periods
    WHERE id = entry_row.fiscal_period_id
    FOR UPDATE;

    IF period_row.status <> 'open' THEN
        RAISE EXCEPTION 'Journal entries can only be posted to an open accounting period.';
    END IF;
    IF entry_row.posting_date < period_row.start_date
       OR entry_row.posting_date > period_row.end_date THEN
        RAISE EXCEPTION 'Journal posting date is outside its accounting period.';
    END IF;

    SELECT
        count(*),
        coalesce(sum(line.debit), 0),
        coalesce(sum(line.credit), 0),
        count(*) FILTER (
            WHERE account.is_active = false OR account.is_posting = false
        )
    INTO line_count, total_debit, total_credit, invalid_account_count
    FROM accounting.journal_lines line
    JOIN accounting.accounts account ON account.id = line.account_id
    WHERE line.journal_entry_id = p_entry_id;

    IF line_count < 2 THEN
        RAISE EXCEPTION 'A journal entry requires at least two lines.';
    END IF;
    IF invalid_account_count > 0 THEN
        RAISE EXCEPTION 'Journal entry contains an inactive or non-posting account.';
    END IF;
    IF total_debit <= 0 OR total_debit <> total_credit THEN
        RAISE EXCEPTION 'Journal entry is not balanced.';
    END IF;

    generated_number := 'JE-'
        || to_char(entry_row.posting_date, 'YYYYMM')
        || '-'
        || lpad(nextval('accounting.journal_number_seq')::text, 8, '0');

    PERFORM set_config('spina.accounting_post', 'on', true);
    UPDATE accounting.journal_entries
    SET
        entry_number = generated_number,
        status = 'posted',
        posted_by_user_id = p_actor_user_id,
        posted_at = now()
    WHERE id = p_entry_id;

    RETURN generated_number;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.create_reversal_draft(
    p_entry_id UUID,
    p_actor_user_id UUID,
    p_posting_date DATE,
    p_description TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    original accounting.journal_entries%ROWTYPE;
    target_period_id UUID;
    reversal_id UUID;
BEGIN
    SELECT * INTO original
    FROM accounting.journal_entries
    WHERE id = p_entry_id
    FOR SHARE;

    IF NOT FOUND OR original.status <> 'posted' THEN
        RAISE EXCEPTION 'Only a posted journal entry can be reversed.';
    END IF;
    IF EXISTS (
        SELECT 1 FROM accounting.journal_entries
        WHERE reversal_of_entry_id = p_entry_id
    ) THEN
        RAISE EXCEPTION 'This journal entry already has a reversal.';
    END IF;

    SELECT id INTO target_period_id
    FROM accounting.fiscal_periods
    WHERE status = 'open'
      AND p_posting_date BETWEEN start_date AND end_date
    ORDER BY start_date DESC
    LIMIT 1;

    IF target_period_id IS NULL THEN
        RAISE EXCEPTION 'No open accounting period contains the reversal date.';
    END IF;

    INSERT INTO accounting.journal_entries (
        fiscal_period_id,
        posting_date,
        description,
        source_type,
        source_reference,
        source_event_key,
        reversal_of_entry_id,
        created_by_user_id
    )
    VALUES (
        target_period_id,
        p_posting_date,
        btrim(p_description),
        'reversal',
        original.entry_number,
        'reversal:' || original.id::text,
        original.id,
        p_actor_user_id
    )
    RETURNING id INTO reversal_id;

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
        reversal_id,
        line_number,
        account_id,
        description,
        credit,
        debit,
        client_id,
        loan_id
    FROM accounting.journal_lines
    WHERE journal_entry_id = original.id
    ORDER BY line_number;

    RETURN reversal_id;
END;
$$;

COMMIT;
