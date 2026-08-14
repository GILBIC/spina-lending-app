BEGIN;

-- Master #296 A6.2, slice 3: protected tax-liability General Journal lifecycle.
-- Exact approved tax evidence remains immutable. This migration adds only the
-- Management-confirmed liability recognition path; settlement and adjustment/
-- reversal evidence remain a later A6.2 slice. Automatic source posting stays off.

INSERT INTO core.permissions (code, description)
VALUES
    ('accounting.tax.liability.prepare', 'Prepare a protected tax-liability General Journal draft from exact current V1 tax evidence'),
    ('accounting.tax.liability.post', 'Post a protected tax-liability General Journal entry after exact Management confirmation')
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code IN (
      'accounting.tax.liability.prepare',
      'accounting.tax.liability.post'
  )
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

INSERT INTO accounting.accounts (
    code, system_key, name, account_type, normal_balance, is_posting
)
VALUES
    ('5300', 'percentage_tax_lending_expense', 'Percentage / Gross Receipts Tax Expense', 'expense', 'debit', true),
    ('5310', 'documentary_stamp_tax_expense', 'Documentary Stamp Tax Expense', 'expense', 'debit', true)
ON CONFLICT (system_key) DO UPDATE SET
    code = excluded.code,
    name = excluded.name,
    account_type = excluded.account_type,
    normal_balance = excluded.normal_balance,
    is_posting = excluded.is_posting,
    is_active = true,
    updated_at = now();

CREATE TABLE IF NOT EXISTS accounting.v1_tax_liability_preparations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tax_type TEXT NOT NULL CHECK (
        tax_type IN ('documentary_stamp_tax', 'percentage_tax_lending')
    ),
    evidence_id UUID NOT NULL,
    dst_evidence_id UUID
        REFERENCES accounting.v1_dst_evidence(id) ON DELETE RESTRICT,
    percentage_evidence_id UUID
        REFERENCES accounting.v1_percentage_tax_evidence(id) ON DELETE RESTRICT,
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    source_event_key TEXT NOT NULL UNIQUE CHECK (btrim(source_event_key) <> ''),
    recognition_date DATE NOT NULL,
    tax_due NUMERIC(18,2) NOT NULL CHECK (tax_due > 0),
    evidence_digest TEXT NOT NULL CHECK (evidence_digest ~ '^[0-9a-f]{64}$'),
    expense_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    tax_payable_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    fiscal_period_id UUID NOT NULL
        REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    prepared_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    prepared_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (
        (
            tax_type = 'documentary_stamp_tax'
            AND dst_evidence_id = evidence_id
            AND percentage_evidence_id IS NULL
        )
        OR
        (
            tax_type = 'percentage_tax_lending'
            AND percentage_evidence_id = evidence_id
            AND dst_evidence_id IS NULL
        )
    ),
    UNIQUE (tax_type, evidence_id)
);

CREATE INDEX IF NOT EXISTS v1_tax_liability_preparations_date_idx
    ON accounting.v1_tax_liability_preparations(recognition_date DESC, prepared_at DESC);

CREATE TABLE IF NOT EXISTS accounting.v1_tax_liability_postings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    preparation_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_liability_preparations(id) ON DELETE RESTRICT,
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    entry_number TEXT NOT NULL CHECK (btrim(entry_number) <> ''),
    confirmation_token TEXT NOT NULL CHECK (confirmation_token ~ '^[0-9a-f]{64}$'),
    confirmation_digest TEXT NOT NULL CHECK (confirmation_digest ~ '^[0-9a-f]{64}$'),
    confirmed_evidence_digest TEXT NOT NULL
        CHECK (confirmed_evidence_digest ~ '^[0-9a-f]{64}$'),
    confirmed_tax_due NUMERIC(18,2) NOT NULL CHECK (confirmed_tax_due > 0),
    confirmed_expense_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    confirmed_tax_payable_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    confirmed_posting_date DATE NOT NULL,
    confirmed_fiscal_period_id UUID NOT NULL
        REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    policy_version TEXT NOT NULL
        CHECK (policy_version = 'v1_tax_liability_posting_v1'),
    posted_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    posted_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE OR REPLACE FUNCTION accounting.guard_v1_tax_liability_preparation_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(
            current_setting('accounting.v1_tax_liability_preparation_insert_allowed', true),
            ''
       ) = 'on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'V1 tax-liability preparation audit is immutable and must use the protected Management preparation function.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_v1_tax_liability_preparation_guard
    ON accounting.v1_tax_liability_preparations;
CREATE TRIGGER accounting_v1_tax_liability_preparation_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.v1_tax_liability_preparations
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_liability_preparation_write();

CREATE OR REPLACE FUNCTION accounting.guard_v1_tax_liability_posting_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(
            current_setting('accounting.v1_tax_liability_posting_insert_allowed', true),
            ''
       ) = 'on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'V1 tax-liability posting audit is immutable and must use the protected Management posting function.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_v1_tax_liability_posting_guard
    ON accounting.v1_tax_liability_postings;
CREATE TRIGGER accounting_v1_tax_liability_posting_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.v1_tax_liability_postings
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_liability_posting_write();

CREATE OR REPLACE FUNCTION accounting.guard_v1_tax_liability_journal_entry_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    reversed_source TEXT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF (
            NEW.source_type = 'v1_tax_liability'
            OR coalesce(NEW.source_event_key, '') LIKE 'v1_tax_liability:%'
        )
        AND coalesce(
            current_setting('accounting.v1_tax_liability_journal_prepare_allowed', true),
            ''
        ) <> 'on' THEN
            RAISE EXCEPTION 'V1 tax-liability journals must use the protected Management preparation function.';
        END IF;

        IF NEW.reversal_of_entry_id IS NOT NULL THEN
            SELECT source_type INTO reversed_source
            FROM accounting.journal_entries
            WHERE id = NEW.reversal_of_entry_id;
            IF reversed_source = 'v1_tax_liability' THEN
                RAISE EXCEPTION 'Posted V1 tax liabilities cannot be reversed through the manual General Journal; use the protected tax adjustment/reversal workflow.';
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.source_type IS DISTINCT FROM 'v1_tax_liability' THEN
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'V1 tax-liability journals are immutable and cannot be deleted.';
    END IF;

    IF OLD.status = 'draft' AND NEW.status = 'posted' THEN
        IF coalesce(
            current_setting('accounting.v1_tax_liability_journal_post_allowed', true),
            ''
        ) <> 'on' THEN
            RAISE EXCEPTION 'V1 tax-liability journals require the protected Management posting function.';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'V1 tax-liability journals are system generated and immutable.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_v1_tax_liability_journal_entry_guard
    ON accounting.journal_entries;
CREATE TRIGGER accounting_v1_tax_liability_journal_entry_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_liability_journal_entry_change();

CREATE OR REPLACE FUNCTION accounting.guard_v1_tax_liability_journal_line_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_entry UUID;
    target_source TEXT;
BEGIN
    target_entry := CASE
        WHEN TG_OP = 'DELETE' THEN OLD.journal_entry_id
        ELSE NEW.journal_entry_id
    END;

    SELECT source_type INTO target_source
    FROM accounting.journal_entries
    WHERE id = target_entry;

    IF target_source = 'v1_tax_liability'
       AND coalesce(
            current_setting('accounting.v1_tax_liability_journal_line_write_allowed', true),
            ''
       ) <> 'on' THEN
        RAISE EXCEPTION 'V1 tax-liability journal lines are system generated and immutable.';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_v1_tax_liability_journal_line_guard
    ON accounting.journal_lines;
CREATE TRIGGER accounting_v1_tax_liability_journal_line_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_lines
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_liability_journal_line_change();

CREATE OR REPLACE FUNCTION accounting.prepare_v1_tax_liability_journal(
    p_tax_type TEXT,
    p_evidence_id UUID,
    p_actor_user_id UUID
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    normalized_tax_type TEXT := btrim(coalesce(p_tax_type, ''));
    existing accounting.v1_tax_liability_preparations%ROWTYPE;
    dst_evidence accounting.v1_dst_evidence%ROWTYPE;
    percentage_evidence accounting.v1_percentage_tax_evidence%ROWTYPE;
    loan_row lending.loans%ROWTYPE;
    event_row lending.loan_disbursement_events%ROWTYPE;
    transaction_row lending.collection_transactions%ROWTYPE;
    rule_row accounting.v1_tax_rule_evidence%ROWTYPE;
    expense_account accounting.accounts%ROWTYPE;
    payable_account accounting.accounts%ROWTYPE;
    period_row accounting.fiscal_periods%ROWTYPE;
    recognition_date DATE;
    tax_due NUMERIC(18,2);
    evidence_digest TEXT;
    source_loan_id UUID;
    source_client_id UUID;
    source_event_key TEXT;
    journal_id UUID;
    expected_due NUMERIC(18,2);
    actual_term_days INTEGER;
    proration_days INTEGER;
    expected_expense_key TEXT;
    expected_expense_code TEXT;
BEGIN
    PERFORM accounting.require_v1_tax_management_actor(
        p_actor_user_id,
        'accounting.tax.liability.prepare'
    );

    IF normalized_tax_type NOT IN ('documentary_stamp_tax', 'percentage_tax_lending')
       OR p_evidence_id IS NULL THEN
        RAISE EXCEPTION 'Tax-liability preparation requires an exact supported tax type and evidence identifier.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended(
            'v1-tax-liability:' || normalized_tax_type || ':' || p_evidence_id::text,
            0
        )
    );

    SELECT * INTO existing
    FROM accounting.v1_tax_liability_preparations item
    WHERE item.tax_type = normalized_tax_type
      AND item.evidence_id = p_evidence_id;
    IF existing.id IS NOT NULL THEN
        RETURN existing.journal_entry_id;
    END IF;

    IF normalized_tax_type = 'documentary_stamp_tax' THEN
        SELECT * INTO dst_evidence
        FROM accounting.v1_dst_evidence item
        WHERE item.id = p_evidence_id
        FOR SHARE;
        IF dst_evidence.id IS NULL THEN
            RAISE EXCEPTION 'Current DST evidence was not found.';
        END IF;
        IF EXISTS (
            SELECT 1 FROM accounting.v1_dst_evidence later
            WHERE later.loan_id = dst_evidence.loan_id
              AND later.evidence_version > dst_evidence.evidence_version
        ) THEN
            RAISE EXCEPTION 'Selected DST evidence is superseded and cannot create a tax liability.';
        END IF;

        SELECT * INTO loan_row
        FROM lending.loans loan
        WHERE loan.id = dst_evidence.loan_id
        FOR SHARE;
        SELECT * INTO event_row
        FROM lending.loan_disbursement_events event
        WHERE event.id = dst_evidence.disbursement_event_id
        FOR SHARE;
        SELECT * INTO rule_row
        FROM accounting.v1_tax_rule_evidence rule
        WHERE rule.id = dst_evidence.rule_evidence_id
        FOR SHARE;

        IF loan_row.id IS NULL OR event_row.id IS NULL OR rule_row.id IS NULL
           OR event_row.is_voided
           OR event_row.loan_id <> loan_row.id
           OR event_row.client_id <> loan_row.client_id
           OR dst_evidence.client_id <> loan_row.client_id
           OR dst_evidence.issue_date <> event_row.business_date
           OR dst_evidence.issue_price <> event_row.principal_snapshot
           OR event_row.principal_snapshot <> loan_row.principal THEN
            RAISE EXCEPTION 'DST source coordinates no longer match the current protected loan/disbursement evidence.';
        END IF;

        actual_term_days := loan_row.due_date - loan_row.date_released;
        IF actual_term_days <= 0 OR dst_evidence.term_days <> actual_term_days
           OR rule_row.tax_type <> 'documentary_stamp_tax'
           OR dst_evidence.issue_date < rule_row.effective_from
           OR (
                rule_row.effective_to IS NOT NULL
                AND dst_evidence.issue_date > rule_row.effective_to
           )
           OR (
                rule_row.maturity_max_days IS NOT NULL
                AND actual_term_days > rule_row.maturity_max_days
           )
           OR EXISTS (
                SELECT 1 FROM accounting.v1_tax_rule_evidence later
                WHERE later.tax_type = rule_row.tax_type
                  AND later.rule_key = rule_row.rule_key
                  AND later.rule_version > rule_row.rule_version
                  AND later.effective_from <= dst_evidence.issue_date
                  AND (
                      later.effective_to IS NULL
                      OR dst_evidence.issue_date <= later.effective_to
                  )
           ) THEN
            RAISE EXCEPTION 'DST rule/term evidence is no longer current for liability recognition.';
        END IF;

        proration_days := CASE WHEN actual_term_days < 365 THEN actual_term_days ELSE 365 END;
        expected_due := CASE
            WHEN rule_row.treatment = 'exempt' THEN 0::numeric(18,2)
            ELSE round(
                dst_evidence.issue_price * rule_row.rate
                * proration_days::numeric / 365::numeric,
                2
            )
        END;
        IF dst_evidence.applied_rate <> rule_row.rate
           OR dst_evidence.proration_numerator <> proration_days
           OR dst_evidence.proration_denominator <> 365
           OR dst_evidence.tax_due <> expected_due THEN
            RAISE EXCEPTION 'DST tax liability no longer reconciles to exact current evidence.';
        END IF;

        recognition_date := dst_evidence.issue_date;
        tax_due := dst_evidence.tax_due;
        evidence_digest := dst_evidence.calculation_digest;
        source_loan_id := dst_evidence.loan_id;
        source_client_id := dst_evidence.client_id;
        expected_expense_key := 'documentary_stamp_tax_expense';
        expected_expense_code := '5310';
    ELSE
        SELECT * INTO percentage_evidence
        FROM accounting.v1_percentage_tax_evidence item
        WHERE item.id = p_evidence_id
        FOR SHARE;
        IF percentage_evidence.id IS NULL THEN
            RAISE EXCEPTION 'Current percentage-tax evidence was not found.';
        END IF;
        IF EXISTS (
            SELECT 1 FROM accounting.v1_percentage_tax_evidence later
            WHERE later.transaction_id = percentage_evidence.transaction_id
              AND later.evidence_version > percentage_evidence.evidence_version
        ) THEN
            RAISE EXCEPTION 'Selected percentage-tax evidence is superseded and cannot create a tax liability.';
        END IF;

        SELECT * INTO transaction_row
        FROM lending.collection_transactions transaction
        WHERE transaction.id = percentage_evidence.transaction_id
        FOR SHARE;
        SELECT * INTO loan_row
        FROM lending.loans loan
        WHERE loan.id = percentage_evidence.loan_id
        FOR SHARE;
        SELECT * INTO rule_row
        FROM accounting.v1_tax_rule_evidence rule
        WHERE rule.id = percentage_evidence.rule_evidence_id
        FOR SHARE;

        IF transaction_row.id IS NULL OR loan_row.id IS NULL OR rule_row.id IS NULL
           OR transaction_row.is_voided
           OR transaction_row.entry_type NOT IN ('payment', 'advance')
           OR transaction_row.amount <= 0
           OR transaction_row.loan_id <> percentage_evidence.loan_id
           OR transaction_row.client_id <> percentage_evidence.client_id
           OR transaction_row.collection_date <> percentage_evidence.collection_date
           OR transaction_row.amount <> percentage_evidence.source_cash_amount
           OR percentage_evidence.source_cash_amount
                <> percentage_evidence.taxable_lending_receipt_amount
                 + percentage_evidence.principal_receipt_amount
           OR NOT (
                EXISTS (
                    SELECT 1
                    FROM accounting.regular_journal_posting_entries posted
                    WHERE posted.transaction_id = transaction_row.id
                )
                OR EXISTS (
                    SELECT 1
                    FROM accounting.seven_by_seven_journal_postings posted
                    WHERE posted.transaction_id = transaction_row.id
                )
           ) THEN
            RAISE EXCEPTION 'Percentage-tax liability requires the exact current protected non-voided posted cash source and allocation.';
        END IF;

        IF rule_row.tax_type <> 'percentage_tax_lending'
           OR transaction_row.collection_date < rule_row.effective_from
           OR (
                rule_row.effective_to IS NOT NULL
                AND transaction_row.collection_date > rule_row.effective_to
           )
           OR (
                rule_row.maturity_max_days IS NOT NULL
                AND (loan_row.due_date - loan_row.date_released) > rule_row.maturity_max_days
           )
           OR EXISTS (
                SELECT 1 FROM accounting.v1_tax_rule_evidence later
                WHERE later.tax_type = rule_row.tax_type
                  AND later.rule_key = rule_row.rule_key
                  AND later.rule_version > rule_row.rule_version
                  AND later.effective_from <= transaction_row.collection_date
                  AND (
                      later.effective_to IS NULL
                      OR transaction_row.collection_date <= later.effective_to
                  )
           ) THEN
            RAISE EXCEPTION 'Percentage-tax rule evidence is no longer current for liability recognition.';
        END IF;

        expected_due := CASE
            WHEN rule_row.treatment = 'exempt' THEN 0::numeric(18,2)
            ELSE round(
                percentage_evidence.taxable_lending_receipt_amount * rule_row.rate,
                2
            )
        END;
        IF percentage_evidence.applied_rate <> rule_row.rate
           OR percentage_evidence.tax_due <> expected_due THEN
            RAISE EXCEPTION 'Percentage-tax liability no longer reconciles to exact current evidence.';
        END IF;

        recognition_date := percentage_evidence.collection_date;
        tax_due := percentage_evidence.tax_due;
        evidence_digest := percentage_evidence.allocation_digest;
        source_loan_id := percentage_evidence.loan_id;
        source_client_id := percentage_evidence.client_id;
        expected_expense_key := 'percentage_tax_lending_expense';
        expected_expense_code := '5300';
    END IF;

    IF tax_due <= 0 THEN
        RAISE EXCEPTION 'No positive V1 tax liability is required for zero tax due evidence.';
    END IF;
    IF evidence_digest !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Tax-liability preparation requires the exact retained evidence digest.';
    END IF;

    SELECT * INTO expense_account
    FROM accounting.accounts account
    WHERE account.system_key = expected_expense_key
    FOR SHARE;
    SELECT * INTO payable_account
    FROM accounting.accounts account
    WHERE account.system_key = 'tax_payables'
    FOR SHARE;

    IF expense_account.id IS NULL
       OR expense_account.code <> expected_expense_code
       OR expense_account.account_type <> 'expense'
       OR expense_account.normal_balance <> 'debit'
       OR NOT expense_account.is_active
       OR NOT expense_account.is_posting THEN
        RAISE EXCEPTION 'The exact dedicated V1 tax expense account is unavailable or no longer posting-ready.';
    END IF;
    IF payable_account.id IS NULL
       OR payable_account.code <> '2100'
       OR payable_account.account_type <> 'liability'
       OR payable_account.normal_balance <> 'credit'
       OR NOT payable_account.is_active
       OR NOT payable_account.is_posting THEN
        RAISE EXCEPTION 'Exact active Tax Payables account 2100 is required for V1 tax liability recognition.';
    END IF;

    SELECT * INTO period_row
    FROM accounting.fiscal_periods period
    WHERE period.status = 'open'
      AND recognition_date BETWEEN period.start_date AND period.end_date
    ORDER BY period.start_date DESC
    LIMIT 1
    FOR SHARE;
    IF period_row.id IS NULL THEN
        RAISE EXCEPTION 'Tax liability recognition date must be inside an open accounting period.';
    END IF;

    source_event_key :=
        'v1_tax_liability:' || normalized_tax_type || ':' || p_evidence_id::text;

    IF EXISTS (
        SELECT 1 FROM accounting.journal_entries item
        WHERE item.source_event_key = source_event_key
    ) THEN
        RAISE EXCEPTION 'The protected V1 tax-liability source identity is already occupied outside the preparation audit.';
    END IF;

    PERFORM set_config('accounting.v1_tax_liability_journal_prepare_allowed', 'on', true);
    INSERT INTO accounting.journal_entries (
        fiscal_period_id, posting_date, description, status, source_type,
        source_reference, source_event_key, created_by_user_id, updated_at
    ) VALUES (
        period_row.id,
        recognition_date,
        CASE
            WHEN normalized_tax_type = 'documentary_stamp_tax'
                THEN 'Documentary stamp tax liability from approved evidence'
            ELSE 'Percentage / gross receipts tax liability from approved evidence'
        END,
        'draft',
        'v1_tax_liability',
        normalized_tax_type || ':' || p_evidence_id::text,
        source_event_key,
        p_actor_user_id,
        now()
    ) RETURNING id INTO journal_id;
    PERFORM set_config('accounting.v1_tax_liability_journal_prepare_allowed', 'off', true);

    PERFORM set_config('accounting.v1_tax_liability_journal_line_write_allowed', 'on', true);
    INSERT INTO accounting.journal_lines (
        journal_entry_id, line_number, account_id, description, debit, credit,
        client_id, loan_id
    ) VALUES
        (
            journal_id, 1, expense_account.id,
            CASE
                WHEN normalized_tax_type = 'documentary_stamp_tax'
                    THEN 'Documentary stamp tax expense'
                ELSE 'Percentage / gross receipts tax expense'
            END,
            tax_due, 0, source_client_id, source_loan_id
        ),
        (
            journal_id, 2, payable_account.id,
            'Tax payable recognized from exact approved V1 tax evidence',
            0, tax_due, source_client_id, source_loan_id
        );
    PERFORM set_config('accounting.v1_tax_liability_journal_line_write_allowed', 'off', true);

    INSERT INTO accounting.journal_events(
        journal_entry_id, event_type, actor_user_id, details
    ) VALUES (
        journal_id,
        'draft_created',
        p_actor_user_id,
        jsonb_build_object(
            'source_type', 'v1_tax_liability',
            'tax_type', normalized_tax_type,
            'evidence_id', p_evidence_id,
            'evidence_digest', evidence_digest,
            'recognition_date', recognition_date,
            'tax_due', tax_due,
            'expense_account_code', expense_account.code,
            'tax_payable_account_code', payable_account.code,
            'posting_enabled', false,
            'automatic_source_posting', false
        )
    );

    PERFORM set_config('accounting.v1_tax_liability_preparation_insert_allowed', 'on', true);
    INSERT INTO accounting.v1_tax_liability_preparations (
        tax_type, evidence_id, dst_evidence_id, percentage_evidence_id,
        journal_entry_id, source_event_key, recognition_date, tax_due,
        evidence_digest, expense_account_id, tax_payable_account_id,
        fiscal_period_id, prepared_by_user_id
    ) VALUES (
        normalized_tax_type,
        p_evidence_id,
        CASE WHEN normalized_tax_type = 'documentary_stamp_tax' THEN p_evidence_id ELSE NULL END,
        CASE WHEN normalized_tax_type = 'percentage_tax_lending' THEN p_evidence_id ELSE NULL END,
        journal_id,
        source_event_key,
        recognition_date,
        tax_due,
        evidence_digest,
        expense_account.id,
        payable_account.id,
        period_row.id,
        p_actor_user_id
    );
    PERFORM set_config('accounting.v1_tax_liability_preparation_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.tax.liability.prepared',
        'v1_tax_liability',
        p_evidence_id,
        jsonb_build_object(
            'tax_type', normalized_tax_type,
            'journal_entry_id', journal_id,
            'source_event_key', source_event_key,
            'recognition_date', recognition_date,
            'tax_due', tax_due,
            'evidence_digest', evidence_digest,
            'expense_account_code', expense_account.code,
            'tax_payable_account_code', payable_account.code,
            'automatic_source_posting', false
        )
    );

    RETURN journal_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.post_v1_tax_liability_journal(
    p_tax_type TEXT,
    p_evidence_id UUID,
    p_actor_user_id UUID,
    p_confirmation_token TEXT,
    p_expected_evidence_digest TEXT,
    p_expected_tax_due NUMERIC,
    p_expected_expense_account_code TEXT,
    p_expected_tax_payable_account_code TEXT,
    p_expected_posting_date DATE,
    p_expected_fiscal_period_id UUID,
    p_policy_version TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    normalized_tax_type TEXT := btrim(coalesce(p_tax_type, ''));
    normalized_token TEXT := lower(btrim(coalesce(p_confirmation_token, '')));
    normalized_digest TEXT := lower(btrim(coalesce(p_expected_evidence_digest, '')));
    normalized_expense_code TEXT := btrim(coalesce(p_expected_expense_account_code, ''));
    normalized_payable_code TEXT := btrim(coalesce(p_expected_tax_payable_account_code, ''));
    normalized_tax_due NUMERIC(18,2) := round(coalesce(p_expected_tax_due, -1), 2);
    preparation accounting.v1_tax_liability_preparations%ROWTYPE;
    existing accounting.v1_tax_liability_postings%ROWTYPE;
    dst_evidence accounting.v1_dst_evidence%ROWTYPE;
    percentage_evidence accounting.v1_percentage_tax_evidence%ROWTYPE;
    loan_row lending.loans%ROWTYPE;
    event_row lending.loan_disbursement_events%ROWTYPE;
    transaction_row lending.collection_transactions%ROWTYPE;
    rule_row accounting.v1_tax_rule_evidence%ROWTYPE;
    expense_account accounting.accounts%ROWTYPE;
    payable_account accounting.accounts%ROWTYPE;
    period_row accounting.fiscal_periods%ROWTYPE;
    journal accounting.journal_entries%ROWTYPE;
    current_recognition_date DATE;
    current_tax_due NUMERIC(18,2);
    current_digest TEXT;
    current_loan_id UUID;
    current_client_id UUID;
    expected_due NUMERIC(18,2);
    actual_term_days INTEGER;
    proration_days INTEGER;
    expected_expense_key TEXT;
    expected_expense_code TEXT;
    line_count BIGINT;
    total_debit NUMERIC(18,2);
    total_credit NUMERIC(18,2);
    expense_debit NUMERIC(18,2);
    payable_credit NUMERIC(18,2);
    foreign_line_count BIGINT;
    entry_number_value TEXT;
    confirmation_digest_value TEXT;
    result_id UUID;
BEGIN
    PERFORM accounting.require_v1_tax_management_actor(
        p_actor_user_id,
        'accounting.tax.liability.post'
    );

    IF normalized_tax_type NOT IN ('documentary_stamp_tax', 'percentage_tax_lending')
       OR p_evidence_id IS NULL THEN
        RAISE EXCEPTION 'Tax-liability posting requires an exact supported tax type and evidence identifier.';
    END IF;
    IF p_policy_version IS DISTINCT FROM 'v1_tax_liability_posting_v1' THEN
        RAISE EXCEPTION 'Unsupported V1 tax-liability posting policy version.';
    END IF;
    IF normalized_token !~ '^[0-9a-f]{64}$'
       OR normalized_digest !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Tax-liability posting requires the exact Management confirmation token and retained evidence digest.';
    END IF;
    IF p_expected_tax_due IS DISTINCT FROM normalized_tax_due
       OR normalized_tax_due <= 0 THEN
        RAISE EXCEPTION 'Tax-liability posting requires the exact positive currency-cent tax due.';
    END IF;
    IF normalized_expense_code = '' OR normalized_payable_code = ''
       OR p_expected_posting_date IS NULL OR p_expected_fiscal_period_id IS NULL THEN
        RAISE EXCEPTION 'Tax-liability posting requires exact account, date and fiscal-period confirmation.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended(
            'v1-tax-liability:' || normalized_tax_type || ':' || p_evidence_id::text,
            0
        )
    );

    SELECT * INTO preparation
    FROM accounting.v1_tax_liability_preparations item
    WHERE item.tax_type = normalized_tax_type
      AND item.evidence_id = p_evidence_id
    FOR SHARE;
    IF preparation.id IS NULL THEN
        RAISE EXCEPTION 'Tax-liability journal must be prepared from exact current evidence before posting.';
    END IF;

    SELECT * INTO existing
    FROM accounting.v1_tax_liability_postings item
    WHERE item.preparation_id = preparation.id
    FOR SHARE;
    IF existing.id IS NOT NULL THEN
        IF existing.confirmation_token <> normalized_token
           OR existing.confirmed_evidence_digest <> normalized_digest
           OR existing.confirmed_tax_due <> normalized_tax_due
           OR existing.confirmed_posting_date <> p_expected_posting_date
           OR existing.confirmed_fiscal_period_id <> p_expected_fiscal_period_id
           OR existing.policy_version <> p_policy_version
           OR existing.posted_by_user_id <> p_actor_user_id THEN
            RAISE EXCEPTION 'Existing V1 tax-liability posting does not match the immutable retry identity.';
        END IF;
        SELECT code INTO normalized_expense_code
        FROM accounting.accounts account
        WHERE account.id = existing.confirmed_expense_account_id
          AND account.code = btrim(coalesce(p_expected_expense_account_code, ''));
        IF normalized_expense_code IS NULL THEN
            RAISE EXCEPTION 'Existing V1 tax-liability posting does not match the immutable retry identity.';
        END IF;
        SELECT code INTO normalized_payable_code
        FROM accounting.accounts account
        WHERE account.id = existing.confirmed_tax_payable_account_id
          AND account.code = btrim(coalesce(p_expected_tax_payable_account_code, ''));
        IF normalized_payable_code IS NULL THEN
            RAISE EXCEPTION 'Existing V1 tax-liability posting does not match the immutable retry identity.';
        END IF;
        RETURN existing.id;
    END IF;

    IF normalized_tax_type = 'documentary_stamp_tax' THEN
        SELECT * INTO dst_evidence
        FROM accounting.v1_dst_evidence item
        WHERE item.id = p_evidence_id
        FOR SHARE;
        IF dst_evidence.id IS NULL OR EXISTS (
            SELECT 1 FROM accounting.v1_dst_evidence later
            WHERE later.loan_id = dst_evidence.loan_id
              AND later.evidence_version > dst_evidence.evidence_version
        ) THEN
            RAISE EXCEPTION 'Current DST evidence is missing or superseded before tax-liability posting.';
        END IF;

        SELECT * INTO loan_row
        FROM lending.loans loan
        WHERE loan.id = dst_evidence.loan_id
        FOR SHARE;
        SELECT * INTO event_row
        FROM lending.loan_disbursement_events event
        WHERE event.id = dst_evidence.disbursement_event_id
        FOR SHARE;
        SELECT * INTO rule_row
        FROM accounting.v1_tax_rule_evidence rule
        WHERE rule.id = dst_evidence.rule_evidence_id
        FOR SHARE;

        actual_term_days := loan_row.due_date - loan_row.date_released;
        proration_days := CASE WHEN actual_term_days < 365 THEN actual_term_days ELSE 365 END;
        expected_due := CASE
            WHEN rule_row.treatment = 'exempt' THEN 0::numeric(18,2)
            ELSE round(
                dst_evidence.issue_price * rule_row.rate
                * proration_days::numeric / 365::numeric,
                2
            )
        END;

        IF loan_row.id IS NULL OR event_row.id IS NULL OR rule_row.id IS NULL
           OR event_row.is_voided
           OR event_row.loan_id <> loan_row.id
           OR event_row.client_id <> loan_row.client_id
           OR dst_evidence.client_id <> loan_row.client_id
           OR dst_evidence.issue_date <> event_row.business_date
           OR dst_evidence.issue_price <> event_row.principal_snapshot
           OR event_row.principal_snapshot <> loan_row.principal
           OR actual_term_days <= 0
           OR dst_evidence.term_days <> actual_term_days
           OR rule_row.tax_type <> 'documentary_stamp_tax'
           OR dst_evidence.issue_date < rule_row.effective_from
           OR (
                rule_row.effective_to IS NOT NULL
                AND dst_evidence.issue_date > rule_row.effective_to
           )
           OR (
                rule_row.maturity_max_days IS NOT NULL
                AND actual_term_days > rule_row.maturity_max_days
           )
           OR EXISTS (
                SELECT 1 FROM accounting.v1_tax_rule_evidence later
                WHERE later.tax_type = rule_row.tax_type
                  AND later.rule_key = rule_row.rule_key
                  AND later.rule_version > rule_row.rule_version
                  AND later.effective_from <= dst_evidence.issue_date
                  AND (
                      later.effective_to IS NULL
                      OR dst_evidence.issue_date <= later.effective_to
                  )
           )
           OR dst_evidence.applied_rate <> rule_row.rate
           OR dst_evidence.proration_numerator <> proration_days
           OR dst_evidence.proration_denominator <> 365
           OR dst_evidence.tax_due <> expected_due THEN
            RAISE EXCEPTION 'DST source/rule/tax evidence changed after liability preparation.';
        END IF;

        current_recognition_date := dst_evidence.issue_date;
        current_tax_due := dst_evidence.tax_due;
        current_digest := dst_evidence.calculation_digest;
        current_loan_id := dst_evidence.loan_id;
        current_client_id := dst_evidence.client_id;
        expected_expense_key := 'documentary_stamp_tax_expense';
        expected_expense_code := '5310';
    ELSE
        SELECT * INTO percentage_evidence
        FROM accounting.v1_percentage_tax_evidence item
        WHERE item.id = p_evidence_id
        FOR SHARE;
        IF percentage_evidence.id IS NULL OR EXISTS (
            SELECT 1 FROM accounting.v1_percentage_tax_evidence later
            WHERE later.transaction_id = percentage_evidence.transaction_id
              AND later.evidence_version > percentage_evidence.evidence_version
        ) THEN
            RAISE EXCEPTION 'Current percentage-tax evidence is missing or superseded before tax-liability posting.';
        END IF;

        SELECT * INTO transaction_row
        FROM lending.collection_transactions transaction
        WHERE transaction.id = percentage_evidence.transaction_id
        FOR SHARE;
        SELECT * INTO loan_row
        FROM lending.loans loan
        WHERE loan.id = percentage_evidence.loan_id
        FOR SHARE;
        SELECT * INTO rule_row
        FROM accounting.v1_tax_rule_evidence rule
        WHERE rule.id = percentage_evidence.rule_evidence_id
        FOR SHARE;

        expected_due := CASE
            WHEN rule_row.treatment = 'exempt' THEN 0::numeric(18,2)
            ELSE round(
                percentage_evidence.taxable_lending_receipt_amount * rule_row.rate,
                2
            )
        END;

        IF transaction_row.id IS NULL OR loan_row.id IS NULL OR rule_row.id IS NULL
           OR transaction_row.is_voided
           OR transaction_row.entry_type NOT IN ('payment', 'advance')
           OR transaction_row.amount <= 0
           OR transaction_row.loan_id <> percentage_evidence.loan_id
           OR transaction_row.client_id <> percentage_evidence.client_id
           OR transaction_row.collection_date <> percentage_evidence.collection_date
           OR transaction_row.amount <> percentage_evidence.source_cash_amount
           OR percentage_evidence.source_cash_amount
                <> percentage_evidence.taxable_lending_receipt_amount
                 + percentage_evidence.principal_receipt_amount
           OR NOT (
                EXISTS (
                    SELECT 1
                    FROM accounting.regular_journal_posting_entries posted
                    WHERE posted.transaction_id = transaction_row.id
                )
                OR EXISTS (
                    SELECT 1
                    FROM accounting.seven_by_seven_journal_postings posted
                    WHERE posted.transaction_id = transaction_row.id
                )
           )
           OR rule_row.tax_type <> 'percentage_tax_lending'
           OR transaction_row.collection_date < rule_row.effective_from
           OR (
                rule_row.effective_to IS NOT NULL
                AND transaction_row.collection_date > rule_row.effective_to
           )
           OR (
                rule_row.maturity_max_days IS NOT NULL
                AND (loan_row.due_date - loan_row.date_released) > rule_row.maturity_max_days
           )
           OR EXISTS (
                SELECT 1 FROM accounting.v1_tax_rule_evidence later
                WHERE later.tax_type = rule_row.tax_type
                  AND later.rule_key = rule_row.rule_key
                  AND later.rule_version > rule_row.rule_version
                  AND later.effective_from <= transaction_row.collection_date
                  AND (
                      later.effective_to IS NULL
                      OR transaction_row.collection_date <= later.effective_to
                  )
           )
           OR percentage_evidence.applied_rate <> rule_row.rate
           OR percentage_evidence.tax_due <> expected_due THEN
            RAISE EXCEPTION 'Percentage-tax source/rule/allocation evidence changed after liability preparation.';
        END IF;

        current_recognition_date := percentage_evidence.collection_date;
        current_tax_due := percentage_evidence.tax_due;
        current_digest := percentage_evidence.allocation_digest;
        current_loan_id := percentage_evidence.loan_id;
        current_client_id := percentage_evidence.client_id;
        expected_expense_key := 'percentage_tax_lending_expense';
        expected_expense_code := '5300';
    END IF;

    IF current_tax_due <= 0
       OR current_tax_due <> normalized_tax_due
       OR current_digest <> normalized_digest
       OR current_recognition_date <> p_expected_posting_date
       OR preparation.recognition_date <> current_recognition_date
       OR preparation.tax_due <> current_tax_due
       OR preparation.evidence_digest <> current_digest THEN
        RAISE EXCEPTION 'Exact V1 tax evidence no longer matches the confirmed liability posting coordinates.';
    END IF;

    SELECT * INTO expense_account
    FROM accounting.accounts account
    WHERE account.id = preparation.expense_account_id
    FOR SHARE;
    SELECT * INTO payable_account
    FROM accounting.accounts account
    WHERE account.id = preparation.tax_payable_account_id
    FOR SHARE;

    IF expense_account.id IS NULL
       OR expense_account.system_key <> expected_expense_key
       OR expense_account.code <> expected_expense_code
       OR expense_account.code <> normalized_expense_code
       OR expense_account.account_type <> 'expense'
       OR expense_account.normal_balance <> 'debit'
       OR NOT expense_account.is_active
       OR NOT expense_account.is_posting THEN
        RAISE EXCEPTION 'Exact dedicated V1 tax expense account changed after liability preparation.';
    END IF;
    IF payable_account.id IS NULL
       OR payable_account.system_key <> 'tax_payables'
       OR payable_account.code <> '2100'
       OR payable_account.code <> normalized_payable_code
       OR payable_account.account_type <> 'liability'
       OR payable_account.normal_balance <> 'credit'
       OR NOT payable_account.is_active
       OR NOT payable_account.is_posting THEN
        RAISE EXCEPTION 'Exact Tax Payables account 2100 changed after liability preparation.';
    END IF;

    SELECT * INTO period_row
    FROM accounting.fiscal_periods period
    WHERE period.id = p_expected_fiscal_period_id
    FOR SHARE;
    IF period_row.id IS NULL
       OR period_row.status <> 'open'
       OR p_expected_posting_date NOT BETWEEN period_row.start_date AND period_row.end_date
       OR preparation.fiscal_period_id <> period_row.id THEN
        RAISE EXCEPTION 'Tax-liability posting requires the exact still-open fiscal period used at preparation.';
    END IF;

    SELECT * INTO journal
    FROM accounting.journal_entries item
    WHERE item.id = preparation.journal_entry_id
    FOR UPDATE;
    IF journal.id IS NULL
       OR journal.status <> 'draft'
       OR journal.source_type <> 'v1_tax_liability'
       OR journal.source_reference <> normalized_tax_type || ':' || p_evidence_id::text
       OR journal.source_event_key <> preparation.source_event_key
       OR journal.posting_date <> p_expected_posting_date
       OR journal.fiscal_period_id <> period_row.id THEN
        RAISE EXCEPTION 'Prepared V1 tax-liability General Journal draft no longer matches the protected source coordinates.';
    END IF;

    SELECT
        count(*),
        coalesce(sum(line.debit), 0),
        coalesce(sum(line.credit), 0),
        coalesce(sum(line.debit) FILTER (WHERE line.account_id = expense_account.id), 0),
        coalesce(sum(line.credit) FILTER (WHERE line.account_id = payable_account.id), 0),
        count(*) FILTER (
            WHERE line.account_id NOT IN (expense_account.id, payable_account.id)
               OR line.client_id IS DISTINCT FROM current_client_id
               OR line.loan_id IS DISTINCT FROM current_loan_id
        )
    INTO line_count, total_debit, total_credit,
         expense_debit, payable_credit, foreign_line_count
    FROM accounting.journal_lines line
    WHERE line.journal_entry_id = journal.id;

    IF line_count <> 2
       OR total_debit <> normalized_tax_due
       OR total_credit <> normalized_tax_due
       OR expense_debit <> normalized_tax_due
       OR payable_credit <> normalized_tax_due
       OR foreign_line_count <> 0 THEN
        RAISE EXCEPTION 'Prepared V1 tax-liability lines do not exactly reconcile Dr dedicated tax expense / Cr 2100 Tax Payables to retained evidence.';
    END IF;

    confirmation_digest_value := encode(sha256(convert_to(concat_ws('|',
        p_policy_version,
        normalized_tax_type,
        p_evidence_id::text,
        current_digest,
        current_recognition_date::text,
        to_char(current_tax_due, 'FM999999999999990.00'),
        expense_account.id::text,
        payable_account.id::text,
        period_row.id::text,
        journal.id::text,
        normalized_token
    ), 'UTF8')), 'hex');

    PERFORM set_config('accounting.v1_tax_liability_journal_post_allowed', 'on', true);
    entry_number_value := accounting.post_journal_entry(journal.id, p_actor_user_id);
    PERFORM set_config('accounting.v1_tax_liability_journal_post_allowed', 'off', true);

    IF coalesce(
        current_setting('accounting.v1_tax_liability_force_audit_failure', true),
        ''
    ) = 'on' THEN
        RAISE EXCEPTION 'Forced V1 tax-liability audit failure.';
    END IF;

    PERFORM set_config('accounting.v1_tax_liability_posting_insert_allowed', 'on', true);
    INSERT INTO accounting.v1_tax_liability_postings (
        preparation_id, journal_entry_id, entry_number, confirmation_token,
        confirmation_digest, confirmed_evidence_digest, confirmed_tax_due,
        confirmed_expense_account_id, confirmed_tax_payable_account_id,
        confirmed_posting_date, confirmed_fiscal_period_id, policy_version,
        posted_by_user_id
    ) VALUES (
        preparation.id, journal.id, entry_number_value, normalized_token,
        confirmation_digest_value, current_digest, current_tax_due,
        expense_account.id, payable_account.id, current_recognition_date,
        period_row.id, p_policy_version, p_actor_user_id
    ) RETURNING id INTO result_id;
    PERFORM set_config('accounting.v1_tax_liability_posting_insert_allowed', 'off', true);

    INSERT INTO accounting.journal_events(
        journal_entry_id, event_type, actor_user_id, details
    ) VALUES (
        journal.id,
        'posted',
        p_actor_user_id,
        jsonb_build_object(
            'entry_number', entry_number_value,
            'source_type', 'v1_tax_liability',
            'tax_type', normalized_tax_type,
            'evidence_id', p_evidence_id,
            'confirmation_digest', confirmation_digest_value,
            'automatic_source_posting', false
        )
    );

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.tax.liability.posted',
        'v1_tax_liability',
        p_evidence_id,
        jsonb_build_object(
            'tax_type', normalized_tax_type,
            'journal_entry_id', journal.id,
            'entry_number', entry_number_value,
            'recognition_date', current_recognition_date,
            'tax_due', current_tax_due,
            'evidence_digest', current_digest,
            'confirmation_digest', confirmation_digest_value,
            'expense_account_code', expense_account.code,
            'tax_payable_account_code', payable_account.code,
            'automatic_source_posting', false
        )
    );

    RETURN result_id;
END;
$$;

CREATE OR REPLACE VIEW accounting.v1_tax_liability_queue AS
WITH current_tax AS (
    SELECT
        'documentary_stamp_tax'::text AS tax_type,
        evidence.id AS evidence_id,
        evidence.evidence_version,
        evidence.loan_id,
        evidence.client_id,
        evidence.disbursement_event_id AS source_id,
        evidence.issue_date AS recognition_date,
        evidence.tax_due,
        evidence.calculation_digest AS evidence_digest,
        CASE
            WHEN EXISTS (
                SELECT 1 FROM accounting.v1_dst_evidence later
                WHERE later.loan_id = evidence.loan_id
                  AND later.evidence_version > evidence.evidence_version
            ) THEN 'blocked_evidence_superseded'
            ELSE coalesce(ready.tax_status, 'blocked_evidence_unresolved')
        END AS tax_status,
        CASE
            WHEN EXISTS (
                SELECT 1 FROM accounting.v1_dst_evidence later
                WHERE later.loan_id = evidence.loan_id
                  AND later.evidence_version > evidence.evidence_version
            ) THEN 'A later immutable DST evidence version supersedes this evidence.'
            ELSE coalesce(
                ready.tax_blocker,
                CASE
                    WHEN ready.evidence_id IS NULL
                        THEN 'Current DST readiness no longer resolves this evidence.'
                    ELSE NULL
                END
            )
        END AS tax_blocker
    FROM accounting.v1_dst_evidence evidence
    LEFT JOIN accounting.v1_tax_dst_readiness ready
      ON ready.evidence_id = evidence.id

    UNION ALL

    SELECT
        'percentage_tax_lending'::text AS tax_type,
        evidence.id AS evidence_id,
        evidence.evidence_version,
        evidence.loan_id,
        evidence.client_id,
        evidence.transaction_id AS source_id,
        evidence.collection_date AS recognition_date,
        evidence.tax_due,
        evidence.allocation_digest AS evidence_digest,
        CASE
            WHEN EXISTS (
                SELECT 1 FROM accounting.v1_percentage_tax_evidence later
                WHERE later.transaction_id = evidence.transaction_id
                  AND later.evidence_version > evidence.evidence_version
            ) THEN 'blocked_evidence_superseded'
            ELSE coalesce(ready.tax_status, 'blocked_evidence_unresolved')
        END AS tax_status,
        CASE
            WHEN EXISTS (
                SELECT 1 FROM accounting.v1_percentage_tax_evidence later
                WHERE later.transaction_id = evidence.transaction_id
                  AND later.evidence_version > evidence.evidence_version
            ) THEN 'A later immutable percentage-tax evidence version supersedes this evidence.'
            ELSE coalesce(
                ready.tax_blocker,
                CASE
                    WHEN ready.evidence_id IS NULL
                        THEN 'Current percentage-tax readiness no longer resolves this evidence.'
                    ELSE NULL
                END
            )
        END AS tax_blocker
    FROM accounting.v1_percentage_tax_evidence evidence
    LEFT JOIN accounting.v1_tax_percentage_readiness ready
      ON ready.evidence_id = evidence.id
)
SELECT
    current_tax.tax_type,
    current_tax.evidence_id,
    current_tax.evidence_version,
    current_tax.source_id,
    current_tax.loan_id,
    current_tax.client_id,
    current_tax.recognition_date,
    current_tax.tax_due,
    current_tax.evidence_digest,
    current_tax.tax_status AS evidence_status,
    current_tax.tax_blocker AS evidence_blocker,
    expense.code AS expense_account_code,
    expense.name AS expense_account_name,
    payable.code AS tax_payable_account_code,
    payable.name AS tax_payable_account_name,
    preparation.id AS preparation_id,
    preparation.journal_entry_id,
    journal.status AS journal_status,
    journal.entry_number,
    preparation.fiscal_period_id,
    preparation.prepared_by_user_id,
    preparation.prepared_at,
    posting.id AS posting_id,
    posting.confirmation_digest,
    posting.posted_by_user_id,
    posting.posted_at,
    CASE
        WHEN posting.id IS NOT NULL
             AND current_tax.tax_status <> 'evidence_ready'
            THEN 'posted_adjustment_review_required'
        WHEN posting.id IS NOT NULL THEN 'posted'
        WHEN current_tax.tax_status <> 'evidence_ready' THEN 'blocked_evidence'
        WHEN coalesce(current_tax.tax_due, 0) = 0 THEN 'no_liability_required'
        WHEN preparation.id IS NOT NULL
             AND journal.status IS DISTINCT FROM 'draft'
            THEN 'blocked_untracked_journal_state'
        WHEN preparation.id IS NOT NULL
             AND (
                period_gate.open_period_id IS NULL
                OR NOT accounts_gate.accounts_ready
             )
            THEN 'prepared_blocked_revalidation'
        WHEN preparation.id IS NOT NULL THEN 'prepared_not_posted'
        WHEN NOT accounts_gate.accounts_ready THEN 'blocked_accounts'
        WHEN period_gate.open_period_id IS NULL THEN 'blocked_no_open_period'
        ELSE 'evidence_ready'
    END AS accounting_status,
    CASE
        WHEN posting.id IS NOT NULL
             AND current_tax.tax_status <> 'evidence_ready'
            THEN 'Posted tax liability evidence is no longer current; a protected adjustment/reversal review is required.'
        WHEN posting.id IS NOT NULL THEN NULL
        WHEN current_tax.tax_status <> 'evidence_ready'
            THEN current_tax.tax_blocker
        WHEN coalesce(current_tax.tax_due, 0) = 0
            THEN NULL
        WHEN preparation.id IS NOT NULL
             AND journal.status IS DISTINCT FROM 'draft'
            THEN 'Prepared tax-liability journal is not a draft but has no immutable protected posting audit.'
        WHEN preparation.id IS NOT NULL
             AND period_gate.open_period_id IS NULL
            THEN 'Prepared recognition date is no longer inside the exact still-open fiscal period.'
        WHEN preparation.id IS NOT NULL
             AND NOT accounts_gate.accounts_ready
            THEN 'Prepared dedicated tax expense or 2100 Tax Payables account is no longer posting-ready.'
        WHEN preparation.id IS NOT NULL
            THEN 'Exact Management confirmation is required before protected tax-liability posting.'
        WHEN NOT accounts_gate.accounts_ready
            THEN 'Dedicated tax expense and 2100 Tax Payables accounts must be active posting accounts.'
        WHEN period_gate.open_period_id IS NULL
            THEN 'Tax liability recognition date is not inside an open accounting period.'
        ELSE NULL
    END AS accounting_blocker,
    true AS protected_tax_liability_posting_enabled,
    false AS tax_settlement_enabled,
    false AS tax_adjustment_reversal_enabled,
    false AS automatic_source_posting
FROM current_tax
LEFT JOIN accounting.v1_tax_liability_preparations preparation
  ON preparation.tax_type = current_tax.tax_type
 AND preparation.evidence_id = current_tax.evidence_id
LEFT JOIN accounting.journal_entries journal
  ON journal.id = preparation.journal_entry_id
LEFT JOIN accounting.v1_tax_liability_postings posting
  ON posting.preparation_id = preparation.id
LEFT JOIN accounting.accounts expense
  ON expense.system_key = CASE
      WHEN current_tax.tax_type = 'documentary_stamp_tax'
          THEN 'documentary_stamp_tax_expense'
      ELSE 'percentage_tax_lending_expense'
  END
LEFT JOIN accounting.accounts payable
  ON payable.system_key = 'tax_payables'
LEFT JOIN LATERAL (
    SELECT (
        expense.id IS NOT NULL
        AND expense.code = CASE
            WHEN current_tax.tax_type = 'documentary_stamp_tax' THEN '5310'
            ELSE '5300'
        END
        AND expense.account_type = 'expense'
        AND expense.normal_balance = 'debit'
        AND expense.is_active
        AND expense.is_posting
        AND payable.id IS NOT NULL
        AND payable.code = '2100'
        AND payable.account_type = 'liability'
        AND payable.normal_balance = 'credit'
        AND payable.is_active
        AND payable.is_posting
    ) AS accounts_ready
) accounts_gate ON true
LEFT JOIN LATERAL (
    SELECT period.id AS open_period_id
    FROM accounting.fiscal_periods period
    WHERE period.status = 'open'
      AND current_tax.recognition_date BETWEEN period.start_date AND period.end_date
      AND (
          preparation.fiscal_period_id IS NULL
          OR period.id = preparation.fiscal_period_id
      )
    ORDER BY period.start_date DESC
    LIMIT 1
) period_gate ON true;

CREATE OR REPLACE VIEW accounting.v1_tax_liability_summary AS
SELECT
    count(*)::bigint AS evidence_item_count,
    count(*) FILTER (WHERE accounting_status = 'evidence_ready')::bigint AS ready_to_prepare_count,
    count(*) FILTER (WHERE accounting_status = 'prepared_not_posted')::bigint AS prepared_count,
    count(*) FILTER (WHERE accounting_status = 'posted')::bigint AS posted_count,
    count(*) FILTER (WHERE accounting_status = 'no_liability_required')::bigint AS no_liability_required_count,
    count(*) FILTER (
        WHERE accounting_status NOT IN (
            'evidence_ready', 'prepared_not_posted', 'posted', 'no_liability_required'
        )
    )::bigint AS blocked_or_adjustment_review_count,
    coalesce(sum(tax_due) FILTER (WHERE accounting_status = 'posted'), 0)::numeric(18,2)
        AS posted_tax_liability_total,
    true AS protected_tax_liability_posting_enabled,
    false AS tax_settlement_enabled,
    false AS tax_adjustment_reversal_enabled,
    false AS automatic_source_posting
FROM accounting.v1_tax_liability_queue;

COMMENT ON TABLE accounting.v1_tax_liability_preparations IS
'Immutable A6.2 protected preparation audit tying one current DST or percentage-tax evidence record to one exact General Journal draft.';
COMMENT ON TABLE accounting.v1_tax_liability_postings IS
'Immutable A6.2 protected tax-liability posting audit. Exact evidence/account/date/period confirmation is required and automatic source posting remains disabled.';
COMMENT ON VIEW accounting.v1_tax_liability_queue IS
'Current and historical evidence-backed V1 tax liabilities. Positive current evidence may be prepared/posted only through the protected Management path; zero tax creates no journal and stale posted evidence requires later adjustment/reversal review.';

COMMIT;