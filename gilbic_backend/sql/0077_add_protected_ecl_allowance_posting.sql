BEGIN;

-- Master #296 A4: protected initial allowance posting tied to one exact,
-- currently-authoritative A3 quantitative ECL measurement.
--
-- This slice permits ONLY the initial allowance recognition when the protected
-- prior allowance balance for the loan is exactly zero. Any later increase,
-- decrease, reversal, cure or write-off accounting remains A5 and fails closed.
-- Automatic source posting remains disabled.

INSERT INTO core.permissions (code, description)
VALUES
    (
        'accounting.ecl.allowance.prepare',
        'Prepare an immutable Management-confirmed draft for the exact current quantitative ECL allowance without posting it'
    ),
    (
        'accounting.ecl.allowance.post',
        'Explicitly post the exact prepared quantitative ECL allowance to account 1190 after Management reconfirmation'
    )
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code IN (
      'accounting.ecl.allowance.prepare',
      'accounting.ecl.allowance.post'
  )
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.ecl_allowance_draft_preparations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    measurement_id UUID NOT NULL UNIQUE
        REFERENCES accounting.ecl_quantitative_measurements(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    measurement_version INTEGER NOT NULL CHECK (measurement_version > 0),
    measurement_date DATE NOT NULL,
    calculation_digest TEXT NOT NULL CHECK (calculation_digest ~ '^[0-9a-f]{64}$'),
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    source_event_key TEXT NOT NULL UNIQUE,
    posting_date DATE NOT NULL,
    fiscal_period_id UUID NOT NULL
        REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    credit_loss_expense_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    allowance_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    allowance_amount NUMERIC(18,2) NOT NULL CHECK (allowance_amount > 0),
    prior_allowance_balance NUMERIC(18,2) NOT NULL CHECK (prior_allowance_balance >= 0),
    preparation_review_token TEXT NOT NULL
        CHECK (preparation_review_token ~ '^[0-9a-f]{64}$'),
    preparation_digest TEXT NOT NULL UNIQUE
        CHECK (preparation_digest ~ '^[0-9a-f]{64}$'),
    draft_policy_version TEXT NOT NULL CHECK (
        draft_policy_version = 'ecl_allowance_initial_journal_draft_v1'
    ),
    prepared_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    prepared_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (source_event_key = 'ecl_allowance:' || measurement_id::text),
    CHECK (prior_allowance_balance = 0.00)
);

CREATE INDEX IF NOT EXISTS ecl_allowance_draft_preparations_loan_idx
    ON accounting.ecl_allowance_draft_preparations (loan_id, prepared_at DESC);

CREATE TABLE IF NOT EXISTS accounting.ecl_allowance_postings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    preparation_id UUID NOT NULL UNIQUE
        REFERENCES accounting.ecl_allowance_draft_preparations(id) ON DELETE RESTRICT,
    measurement_id UUID NOT NULL UNIQUE
        REFERENCES accounting.ecl_quantitative_measurements(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    measurement_version INTEGER NOT NULL CHECK (measurement_version > 0),
    calculation_digest TEXT NOT NULL CHECK (calculation_digest ~ '^[0-9a-f]{64}$'),
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    source_event_key TEXT NOT NULL UNIQUE,
    posting_date DATE NOT NULL,
    fiscal_period_id UUID NOT NULL
        REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    credit_loss_expense_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    allowance_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    allowance_amount NUMERIC(18,2) NOT NULL CHECK (allowance_amount > 0),
    prior_allowance_balance NUMERIC(18,2) NOT NULL CHECK (prior_allowance_balance >= 0),
    resulting_allowance_balance NUMERIC(18,2) NOT NULL CHECK (resulting_allowance_balance > 0),
    preparation_review_token TEXT NOT NULL
        CHECK (preparation_review_token ~ '^[0-9a-f]{64}$'),
    preparation_digest TEXT NOT NULL CHECK (preparation_digest ~ '^[0-9a-f]{64}$'),
    posting_review_token TEXT NOT NULL
        CHECK (posting_review_token ~ '^[0-9a-f]{64}$'),
    draft_policy_version TEXT NOT NULL CHECK (
        draft_policy_version = 'ecl_allowance_initial_journal_draft_v1'
    ),
    posting_policy_version TEXT NOT NULL CHECK (
        posting_policy_version = 'ecl_allowance_initial_journal_posting_v1'
    ),
    entry_number TEXT NOT NULL UNIQUE CHECK (btrim(entry_number) <> ''),
    posted_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    posted_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (measurement_id IS NOT NULL),
    CHECK (source_event_key = 'ecl_allowance:' || measurement_id::text),
    CHECK (prior_allowance_balance = 0.00),
    CHECK (resulting_allowance_balance = allowance_amount)
);

CREATE INDEX IF NOT EXISTS ecl_allowance_postings_loan_idx
    ON accounting.ecl_allowance_postings (loan_id, posted_at DESC);

CREATE TABLE IF NOT EXISTS accounting.ecl_allowance_posting_lines (
    posting_id UUID NOT NULL
        REFERENCES accounting.ecl_allowance_postings(id) ON DELETE RESTRICT,
    line_number INTEGER NOT NULL CHECK (line_number > 0),
    account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    account_system_key TEXT NOT NULL CHECK (btrim(account_system_key) <> ''),
    debit NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (debit >= 0),
    credit NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (credit >= 0),
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    PRIMARY KEY (posting_id, line_number),
    CHECK (
        (debit > 0 AND credit = 0)
        OR (credit > 0 AND debit = 0)
    )
);

CREATE OR REPLACE FUNCTION accounting.require_ecl_allowance_management_actor(
    p_actor_user_id UUID,
    p_permission_code TEXT
)
RETURNS VOID
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    IF p_permission_code NOT IN (
        'accounting.ecl.allowance.prepare',
        'accounting.ecl.allowance.post'
    ) THEN
        RAISE EXCEPTION 'Unsupported ECL allowance Management permission.';
    END IF;

    IF p_actor_user_id IS NULL OR NOT EXISTS (
        SELECT 1
        FROM core.users actor
        JOIN core.user_roles user_role ON user_role.user_id = actor.id
        JOIN core.role_permissions role_permission
          ON role_permission.role_id = user_role.role_id
        WHERE actor.id = p_actor_user_id
          AND actor.status = 'active'
          AND role_permission.permission_code = p_permission_code
    ) THEN
        RAISE EXCEPTION 'An active Management actor with % permission is required.',
            p_permission_code;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.ecl_loan_allowance_balance(p_loan_id UUID)
RETURNS NUMERIC(18,2)
LANGUAGE sql
STABLE
AS $$
    SELECT coalesce(
        sum(line.credit - line.debit),
        0
    )::numeric(18,2)
    FROM accounting.journal_lines line
    JOIN accounting.journal_entries journal
      ON journal.id = line.journal_entry_id
    JOIN accounting.accounts account
      ON account.id = line.account_id
    WHERE journal.status = 'posted'
      AND account.system_key = 'allowance_expected_credit_loss'
      AND line.loan_id = p_loan_id;
$$;

CREATE OR REPLACE FUNCTION accounting.guard_ecl_allowance_preparation_record_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(
            current_setting('accounting.ecl_allowance_preparation_record_allowed', true),
            ''
       ) = 'on' THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'Protected ECL allowance preparation audit is immutable and must use the protected preparation function.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_ecl_allowance_preparation_guard
    ON accounting.ecl_allowance_draft_preparations;
CREATE TRIGGER accounting_ecl_allowance_preparation_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.ecl_allowance_draft_preparations
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_allowance_preparation_record_write();

CREATE OR REPLACE FUNCTION accounting.guard_ecl_allowance_posting_audit_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(
            current_setting('accounting.ecl_allowance_posting_audit_allowed', true),
            ''
       ) = 'on' THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'Protected ECL allowance posting audit is immutable and must use the protected posting function.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_ecl_allowance_posting_guard
    ON accounting.ecl_allowance_postings;
CREATE TRIGGER accounting_ecl_allowance_posting_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.ecl_allowance_postings
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_allowance_posting_audit_write();

DROP TRIGGER IF EXISTS accounting_ecl_allowance_posting_line_guard
    ON accounting.ecl_allowance_posting_lines;
CREATE TRIGGER accounting_ecl_allowance_posting_line_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.ecl_allowance_posting_lines
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_allowance_posting_audit_write();

-- Reserve the ECL allowance journal namespace for the protected path only.
CREATE OR REPLACE FUNCTION accounting.guard_ecl_allowance_journal_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.source_type = 'ecl_allowance'
       AND coalesce(
            current_setting('accounting.ecl_allowance_journal_prepare_allowed', true),
            ''
       ) <> 'on' THEN
        RAISE EXCEPTION 'ECL allowance journals must be created through the protected allowance preparation workflow.';
    END IF;

    IF NEW.reversal_of_entry_id IS NOT NULL
       AND EXISTS (
            SELECT 1
            FROM accounting.ecl_allowance_postings posting
            WHERE posting.journal_entry_id = NEW.reversal_of_entry_id
       )
       AND coalesce(
            current_setting('accounting.ecl_allowance_reversal_allowed', true),
            ''
       ) <> 'on' THEN
        RAISE EXCEPTION 'Posted protected ECL allowance journals cannot be reversed through the manual General Journal; A5 controlled remeasurement/reversal is required.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_ecl_allowance_journal_insert_guard
    ON accounting.journal_entries;
CREATE TRIGGER accounting_ecl_allowance_journal_insert_guard
BEFORE INSERT ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_allowance_journal_insert();

CREATE OR REPLACE FUNCTION accounting.guard_ecl_allowance_journal_entry_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    protected_entry BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM accounting.ecl_allowance_draft_preparations prepared
        WHERE prepared.journal_entry_id = OLD.id
    ) INTO protected_entry;

    IF NOT protected_entry THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Protected ECL allowance journal drafts cannot be deleted through the General Journal.';
    END IF;

    IF OLD.status = 'draft' AND NEW.status = 'posted' THEN
        IF coalesce(
            current_setting('accounting.ecl_allowance_journal_post_allowed', true),
            ''
        ) <> 'on' THEN
            RAISE EXCEPTION 'Protected ECL allowance journal drafts require the protected allowance posting workflow.';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'Protected ECL allowance journal drafts are system generated and cannot be edited.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_ecl_allowance_journal_entry_guard
    ON accounting.journal_entries;
CREATE TRIGGER accounting_ecl_allowance_journal_entry_guard
BEFORE UPDATE OR DELETE ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_allowance_journal_entry_change();

-- Account 1190 is a protected source-controlled account. Generic/manual journal
-- lines cannot write or mutate it. A5 may reuse this explicit GUC only from its
-- future protected accounting path.
CREATE OR REPLACE FUNCTION accounting.guard_ecl_allowance_journal_line_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_entry_id UUID;
    new_is_allowance BOOLEAN := false;
    old_is_allowance BOOLEAN := false;
    protected_entry BOOLEAN := false;
BEGIN
    target_entry_id := CASE
        WHEN TG_OP = 'DELETE' THEN OLD.journal_entry_id
        ELSE NEW.journal_entry_id
    END;

    IF TG_OP <> 'DELETE' THEN
        SELECT account.system_key = 'allowance_expected_credit_loss'
        INTO new_is_allowance
        FROM accounting.accounts account
        WHERE account.id = NEW.account_id;
    END IF;

    IF TG_OP <> 'INSERT' THEN
        SELECT account.system_key = 'allowance_expected_credit_loss'
        INTO old_is_allowance
        FROM accounting.accounts account
        WHERE account.id = OLD.account_id;
    END IF;

    IF (coalesce(new_is_allowance, false) OR coalesce(old_is_allowance, false))
       AND coalesce(
            current_setting('accounting.ecl_allowance_journal_line_write_allowed', true),
            ''
       ) <> 'on' THEN
        RAISE EXCEPTION 'Account 1190 Allowance for Expected Credit Loss can only be changed through a protected ECL allowance accounting workflow.';
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM accounting.ecl_allowance_draft_preparations prepared
        WHERE prepared.journal_entry_id = target_entry_id
    ) INTO protected_entry;

    IF protected_entry
       AND coalesce(
            current_setting('accounting.ecl_allowance_journal_line_write_allowed', true),
            ''
       ) <> 'on' THEN
        RAISE EXCEPTION 'Protected ECL allowance journal lines are system generated and immutable.';
    END IF;

    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_ecl_allowance_journal_line_guard
    ON accounting.journal_lines;
CREATE TRIGGER accounting_ecl_allowance_journal_line_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_lines
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_allowance_journal_line_change();

CREATE OR REPLACE FUNCTION accounting.prepare_initial_ecl_allowance_journal(
    p_measurement_id UUID,
    p_actor_user_id UUID,
    p_preparation_review_token TEXT,
    p_expected_calculation_digest TEXT,
    p_expected_ecl_amount NUMERIC,
    p_expected_posting_date DATE,
    p_expected_fiscal_period_id UUID,
    p_expected_credit_loss_expense_account_id UUID,
    p_expected_allowance_account_id UUID,
    p_expected_prior_allowance_balance NUMERIC,
    p_draft_policy_version TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    measurement accounting.ecl_quantitative_measurements%ROWTYPE;
    queue RECORD;
    loan_row lending.loans%ROWTYPE;
    period_row accounting.fiscal_periods%ROWTYPE;
    expense_account accounting.accounts%ROWTYPE;
    allowance_account accounting.accounts%ROWTYPE;
    existing accounting.ecl_allowance_draft_preparations%ROWTYPE;
    journal_row accounting.journal_entries%ROWTYPE;
    normalized_review_token TEXT := lower(btrim(coalesce(p_preparation_review_token, '')));
    normalized_digest TEXT := lower(btrim(coalesce(p_expected_calculation_digest, '')));
    expected_amount NUMERIC(18,2) := round(coalesce(p_expected_ecl_amount, 0), 2);
    expected_prior NUMERIC(18,2) := round(coalesce(p_expected_prior_allowance_balance, 0), 2);
    current_allowance NUMERIC(18,2);
    unallocated_allowance NUMERIC(18,2);
    preparation_digest_value TEXT;
    journal_id UUID;
    preparation_id UUID;
    line_count INTEGER;
    total_debit NUMERIC(18,2);
    total_credit NUMERIC(18,2);
BEGIN
    PERFORM accounting.require_ecl_allowance_management_actor(
        p_actor_user_id,
        'accounting.ecl.allowance.prepare'
    );

    IF p_draft_policy_version IS DISTINCT FROM 'ecl_allowance_initial_journal_draft_v1' THEN
        RAISE EXCEPTION 'Unsupported protected ECL allowance draft policy version.';
    END IF;
    IF normalized_review_token !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Protected ECL allowance preparation review token is invalid.';
    END IF;
    IF normalized_digest !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Expected quantitative ECL calculation digest is invalid.';
    END IF;
    IF p_expected_ecl_amount IS DISTINCT FROM expected_amount
       OR expected_amount <= 0 THEN
        RAISE EXCEPTION 'Initial ECL allowance preparation requires a positive exact currency-cent amount.';
    END IF;
    IF p_expected_prior_allowance_balance IS DISTINCT FROM expected_prior
       OR expected_prior <> 0.00 THEN
        RAISE EXCEPTION 'A4 initial allowance posting requires exact prior allowance balance 0.00; non-zero allowance state requires A5 remeasurement accounting.';
    END IF;

    SELECT * INTO measurement
    FROM accounting.ecl_quantitative_measurements item
    WHERE item.id = p_measurement_id
    FOR SHARE;
    IF measurement.id IS NULL THEN
        RAISE EXCEPTION 'Quantitative ECL measurement was not found.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended('ecl-allowance:' || measurement.loan_id::text, 0)
    );

    SELECT * INTO loan_row
    FROM lending.loans loan
    WHERE loan.id = measurement.loan_id
    FOR UPDATE;
    IF loan_row.id IS NULL THEN
        RAISE EXCEPTION 'Measured loan was not found.';
    END IF;

    SELECT * INTO queue
    FROM accounting.ecl_quantitative_measurement_queue current_queue
    WHERE current_queue.loan_id = measurement.loan_id;
    IF queue.loan_id IS NULL
       OR queue.measurement_status <> 'measured_read_only'
       OR queue.quantitative_input_ready IS DISTINCT FROM true
       OR queue.measurement_forward_evidence_current IS DISTINCT FROM true
       OR queue.measurement_id IS DISTINCT FROM measurement.id
       OR queue.measurement_version IS DISTINCT FROM measurement.measurement_version
       OR queue.calculation_digest IS DISTINCT FROM measurement.calculation_digest
       OR queue.authoritative_ecl_amount IS DISTINCT FROM measurement.ecl_amount THEN
        RAISE EXCEPTION 'Quantitative ECL measurement is no longer the exact current authoritative measurement. Refresh Management review.';
    END IF;

    IF measurement.calculation_digest <> normalized_digest
       OR measurement.ecl_amount <> expected_amount
       OR p_expected_posting_date IS DISTINCT FROM measurement.measurement_date THEN
        RAISE EXCEPTION 'ECL allowance confirmation changed from the exact quantitative measurement snapshot.';
    END IF;

    SELECT * INTO period_row
    FROM accounting.fiscal_periods period
    WHERE period.id = p_expected_fiscal_period_id
    FOR SHARE;
    IF period_row.id IS NULL
       OR period_row.status <> 'open'
       OR p_expected_posting_date < period_row.start_date
       OR p_expected_posting_date > period_row.end_date THEN
        RAISE EXCEPTION 'ECL allowance posting requires the exact open fiscal period containing the measurement date.';
    END IF;

    SELECT * INTO expense_account
    FROM accounting.accounts account
    WHERE account.id = p_expected_credit_loss_expense_account_id
    FOR SHARE;
    IF expense_account.id IS NULL
       OR expense_account.system_key <> 'credit_loss_expense'
       OR expense_account.code <> '5000'
       OR expense_account.account_type <> 'expense'
       OR expense_account.normal_balance <> 'debit'
       OR expense_account.is_active IS DISTINCT FROM true
       OR expense_account.is_posting IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'Exact active posting account 5000 Credit Loss Expense is required.';
    END IF;

    SELECT * INTO allowance_account
    FROM accounting.accounts account
    WHERE account.id = p_expected_allowance_account_id
    FOR SHARE;
    IF allowance_account.id IS NULL
       OR allowance_account.system_key <> 'allowance_expected_credit_loss'
       OR allowance_account.code <> '1190'
       OR allowance_account.account_type <> 'asset'
       OR allowance_account.normal_balance <> 'credit'
       OR allowance_account.is_active IS DISTINCT FROM true
       OR allowance_account.is_posting IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'Exact active posting account 1190 Allowance for Expected Credit Loss is required.';
    END IF;

    SELECT * INTO existing
    FROM accounting.ecl_allowance_draft_preparations prepared
    WHERE prepared.measurement_id = measurement.id;

    IF existing.id IS NOT NULL THEN
        IF existing.loan_id <> measurement.loan_id
           OR existing.client_id <> loan_row.client_id
           OR existing.measurement_version <> measurement.measurement_version
           OR existing.measurement_date <> measurement.measurement_date
           OR existing.calculation_digest <> normalized_digest
           OR existing.source_event_key <> 'ecl_allowance:' || measurement.id::text
           OR existing.posting_date <> p_expected_posting_date
           OR existing.fiscal_period_id <> p_expected_fiscal_period_id
           OR existing.credit_loss_expense_account_id <> expense_account.id
           OR existing.allowance_account_id <> allowance_account.id
           OR existing.allowance_amount <> expected_amount
           OR existing.prior_allowance_balance <> expected_prior
           OR existing.preparation_review_token <> normalized_review_token
           OR existing.draft_policy_version <> p_draft_policy_version THEN
            RAISE EXCEPTION 'Existing protected ECL allowance preparation does not match the confirmed measurement identity.';
        END IF;

        SELECT * INTO journal_row
        FROM accounting.journal_entries journal
        WHERE journal.id = existing.journal_entry_id;
        IF journal_row.id IS NULL
           OR journal_row.source_type <> 'ecl_allowance'
           OR journal_row.source_reference <> measurement.id::text
           OR journal_row.source_event_key <> existing.source_event_key
           OR journal_row.posting_date <> existing.posting_date
           OR journal_row.fiscal_period_id <> existing.fiscal_period_id
           OR journal_row.status NOT IN ('draft', 'posted') THEN
            RAISE EXCEPTION 'Existing protected ECL allowance journal no longer matches its immutable preparation.';
        END IF;

        SELECT
            count(*)::integer,
            coalesce(sum(line.debit), 0)::numeric(18,2),
            coalesce(sum(line.credit), 0)::numeric(18,2)
        INTO line_count, total_debit, total_credit
        FROM accounting.journal_lines line
        WHERE line.journal_entry_id = existing.journal_entry_id;
        IF line_count <> 2
           OR total_debit <> expected_amount
           OR total_credit <> expected_amount THEN
            RAISE EXCEPTION 'Existing protected ECL allowance journal lines no longer match the immutable preparation.';
        END IF;

        current_allowance := accounting.ecl_loan_allowance_balance(measurement.loan_id);
        IF journal_row.status = 'draft' AND current_allowance <> existing.prior_allowance_balance THEN
            RAISE EXCEPTION 'Prior allowance state changed after ECL allowance preparation; A5 remeasurement/reversal review is required.';
        ELSIF journal_row.status = 'posted'
          AND current_allowance <> existing.prior_allowance_balance + existing.allowance_amount THEN
            RAISE EXCEPTION 'Posted ECL allowance state no longer reconciles to its immutable preparation.';
        END IF;

        RETURN existing.id;
    END IF;

    current_allowance := accounting.ecl_loan_allowance_balance(measurement.loan_id);
    IF current_allowance <> expected_prior THEN
        RAISE EXCEPTION 'Prior allowance state changed from the confirmed 0.00; A5 remeasurement accounting is required.';
    END IF;

    SELECT coalesce(sum(line.credit - line.debit), 0)::numeric(18,2)
    INTO unallocated_allowance
    FROM accounting.journal_lines line
    JOIN accounting.journal_entries journal ON journal.id = line.journal_entry_id
    JOIN accounting.accounts account ON account.id = line.account_id
    WHERE journal.status = 'posted'
      AND account.system_key = 'allowance_expected_credit_loss'
      AND line.loan_id IS NULL;
    IF unallocated_allowance <> 0.00 THEN
        RAISE EXCEPTION 'Unallocated account 1190 balance exists; protected per-loan allowance posting is blocked until reconciled.';
    END IF;

    preparation_digest_value := encode(
        sha256(
            convert_to(
                concat_ws(
                    '|',
                    'ecl_allowance_initial_journal_draft_v1',
                    measurement.id::text,
                    measurement.loan_id::text,
                    loan_row.client_id::text,
                    measurement.measurement_version::text,
                    measurement.measurement_date::text,
                    normalized_digest,
                    p_expected_posting_date::text,
                    p_expected_fiscal_period_id::text,
                    expense_account.id::text,
                    allowance_account.id::text,
                    to_char(expected_amount, 'FM999999999999990.00'),
                    to_char(expected_prior, 'FM999999999999990.00'),
                    normalized_review_token
                ),
                'UTF8'
            )
        ),
        'hex'
    );

    PERFORM set_config('accounting.ecl_allowance_journal_prepare_allowed', 'on', true);
    INSERT INTO accounting.journal_entries (
        fiscal_period_id,
        posting_date,
        description,
        source_type,
        source_reference,
        source_event_key,
        created_by_user_id
    ) VALUES (
        period_row.id,
        p_expected_posting_date,
        'Expected credit loss allowance - loan ' || loan_row.loan_number
            || ' - measurement v' || measurement.measurement_version::text,
        'ecl_allowance',
        measurement.id::text,
        'ecl_allowance:' || measurement.id::text,
        p_actor_user_id
    ) RETURNING id INTO journal_id;
    PERFORM set_config('accounting.ecl_allowance_journal_prepare_allowed', 'off', true);

    PERFORM set_config('accounting.ecl_allowance_journal_line_write_allowed', 'on', true);
    INSERT INTO accounting.journal_lines (
        journal_entry_id, line_number, account_id, description,
        debit, credit, client_id, loan_id
    ) VALUES
        (
            journal_id, 1, expense_account.id,
            'Credit loss expense from quantitative ECL measurement ' || measurement.id::text,
            expected_amount, 0, loan_row.client_id, measurement.loan_id
        ),
        (
            journal_id, 2, allowance_account.id,
            'Allowance for Expected Credit Loss from measurement ' || measurement.id::text,
            0, expected_amount, loan_row.client_id, measurement.loan_id
        );
    PERFORM set_config('accounting.ecl_allowance_journal_line_write_allowed', 'off', true);

    PERFORM set_config('accounting.ecl_allowance_preparation_record_allowed', 'on', true);
    INSERT INTO accounting.ecl_allowance_draft_preparations (
        measurement_id, loan_id, client_id, measurement_version,
        measurement_date, calculation_digest, journal_entry_id,
        source_event_key, posting_date, fiscal_period_id,
        credit_loss_expense_account_id, allowance_account_id,
        allowance_amount, prior_allowance_balance,
        preparation_review_token, preparation_digest, draft_policy_version,
        prepared_by_user_id
    ) VALUES (
        measurement.id, measurement.loan_id, loan_row.client_id,
        measurement.measurement_version, measurement.measurement_date,
        normalized_digest, journal_id,
        'ecl_allowance:' || measurement.id::text,
        p_expected_posting_date, period_row.id,
        expense_account.id, allowance_account.id,
        expected_amount, expected_prior,
        normalized_review_token, preparation_digest_value,
        p_draft_policy_version, p_actor_user_id
    ) RETURNING id INTO preparation_id;
    PERFORM set_config('accounting.ecl_allowance_preparation_record_allowed', 'off', true);

    INSERT INTO core.audit_logs (actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.ecl.allowance.prepared',
        'ecl_allowance_draft_preparation',
        preparation_id,
        jsonb_build_object(
            'measurement_id', measurement.id,
            'loan_id', measurement.loan_id,
            'measurement_version', measurement.measurement_version,
            'calculation_digest', normalized_digest,
            'journal_entry_id', journal_id,
            'posting_date', p_expected_posting_date,
            'fiscal_period_id', period_row.id,
            'credit_loss_expense_account_id', expense_account.id,
            'allowance_account_id', allowance_account.id,
            'allowance_amount', expected_amount,
            'prior_allowance_balance', expected_prior,
            'preparation_digest', preparation_digest_value,
            'account_1190_posting_enabled', true,
            'automatic_source_posting', false
        )
    );

    RETURN preparation_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.post_initial_ecl_allowance_journal(
    p_preparation_id UUID,
    p_actor_user_id UUID,
    p_posting_review_token TEXT,
    p_expected_measurement_id UUID,
    p_expected_calculation_digest TEXT,
    p_expected_journal_entry_id UUID,
    p_expected_source_event_key TEXT,
    p_expected_preparation_digest TEXT,
    p_expected_posting_date DATE,
    p_expected_fiscal_period_id UUID,
    p_expected_credit_loss_expense_account_id UUID,
    p_expected_allowance_account_id UUID,
    p_expected_allowance_amount NUMERIC,
    p_expected_prior_allowance_balance NUMERIC,
    p_posting_policy_version TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    prepared accounting.ecl_allowance_draft_preparations%ROWTYPE;
    existing accounting.ecl_allowance_postings%ROWTYPE;
    measurement accounting.ecl_quantitative_measurements%ROWTYPE;
    queue RECORD;
    journal_row accounting.journal_entries%ROWTYPE;
    period_row accounting.fiscal_periods%ROWTYPE;
    expense_account accounting.accounts%ROWTYPE;
    allowance_account accounting.accounts%ROWTYPE;
    normalized_posting_token TEXT := lower(btrim(coalesce(p_posting_review_token, '')));
    normalized_measurement_digest TEXT := lower(btrim(coalesce(p_expected_calculation_digest, '')));
    normalized_source_event_key TEXT := btrim(coalesce(p_expected_source_event_key, ''));
    normalized_preparation_digest TEXT := lower(btrim(coalesce(p_expected_preparation_digest, '')));
    expected_amount NUMERIC(18,2) := round(coalesce(p_expected_allowance_amount, 0), 2);
    expected_prior NUMERIC(18,2) := round(coalesce(p_expected_prior_allowance_balance, 0), 2);
    current_allowance NUMERIC(18,2);
    resulting_allowance NUMERIC(18,2);
    line_count INTEGER;
    exact_line_count INTEGER;
    total_debit NUMERIC(18,2);
    total_credit NUMERIC(18,2);
    entry_number_value TEXT;
    posting_id UUID;
BEGIN
    PERFORM accounting.require_ecl_allowance_management_actor(
        p_actor_user_id,
        'accounting.ecl.allowance.post'
    );

    IF p_posting_policy_version IS DISTINCT FROM 'ecl_allowance_initial_journal_posting_v1' THEN
        RAISE EXCEPTION 'Unsupported protected ECL allowance posting policy version.';
    END IF;
    IF normalized_posting_token !~ '^[0-9a-f]{64}$'
       OR normalized_measurement_digest !~ '^[0-9a-f]{64}$'
       OR normalized_preparation_digest !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Protected ECL allowance posting confirmation contains an invalid token or digest.';
    END IF;
    IF p_expected_allowance_amount IS DISTINCT FROM expected_amount
       OR expected_amount <= 0
       OR p_expected_prior_allowance_balance IS DISTINCT FROM expected_prior
       OR expected_prior <> 0.00 THEN
        RAISE EXCEPTION 'A4 allowance posting requires exact positive currency-cent amount and prior allowance balance 0.00.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended('ecl-allowance-post:' || p_preparation_id::text, 0)
    );

    SELECT * INTO prepared
    FROM accounting.ecl_allowance_draft_preparations item
    WHERE item.id = p_preparation_id;
    IF prepared.id IS NULL THEN
        RAISE EXCEPTION 'Protected ECL allowance preparation was not found.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended('ecl-allowance:' || prepared.loan_id::text, 0)
    );
    PERFORM 1 FROM lending.loans WHERE id = prepared.loan_id FOR UPDATE;

    IF p_expected_measurement_id IS DISTINCT FROM prepared.measurement_id
       OR normalized_measurement_digest <> prepared.calculation_digest
       OR p_expected_journal_entry_id IS DISTINCT FROM prepared.journal_entry_id
       OR normalized_source_event_key <> prepared.source_event_key
       OR normalized_preparation_digest <> prepared.preparation_digest
       OR p_expected_posting_date IS DISTINCT FROM prepared.posting_date
       OR p_expected_fiscal_period_id IS DISTINCT FROM prepared.fiscal_period_id
       OR p_expected_credit_loss_expense_account_id IS DISTINCT FROM prepared.credit_loss_expense_account_id
       OR p_expected_allowance_account_id IS DISTINCT FROM prepared.allowance_account_id
       OR expected_amount <> prepared.allowance_amount
       OR expected_prior <> prepared.prior_allowance_balance THEN
        RAISE EXCEPTION 'Protected ECL allowance posting confirmation changed from the immutable preparation.';
    END IF;

    SELECT * INTO measurement
    FROM accounting.ecl_quantitative_measurements item
    WHERE item.id = prepared.measurement_id
    FOR SHARE;
    IF measurement.id IS NULL
       OR measurement.loan_id <> prepared.loan_id
       OR measurement.measurement_version <> prepared.measurement_version
       OR measurement.measurement_date <> prepared.measurement_date
       OR measurement.calculation_digest <> prepared.calculation_digest
       OR measurement.ecl_amount <> prepared.allowance_amount THEN
        RAISE EXCEPTION 'Exact quantitative ECL source measurement no longer matches the protected allowance preparation.';
    END IF;

    SELECT * INTO queue
    FROM accounting.ecl_quantitative_measurement_queue current_queue
    WHERE current_queue.loan_id = prepared.loan_id;
    IF queue.loan_id IS NULL
       OR queue.measurement_status <> 'measured_read_only'
       OR queue.measurement_id IS DISTINCT FROM prepared.measurement_id
       OR queue.calculation_digest IS DISTINCT FROM prepared.calculation_digest
       OR queue.authoritative_ecl_amount IS DISTINCT FROM prepared.allowance_amount
       OR queue.quantitative_input_ready IS DISTINCT FROM true
       OR queue.measurement_forward_evidence_current IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'Exact quantitative ECL measurement is no longer current and authoritative; allowance posting is blocked.';
    END IF;

    SELECT * INTO period_row
    FROM accounting.fiscal_periods period
    WHERE period.id = prepared.fiscal_period_id
    FOR SHARE;
    IF period_row.id IS NULL
       OR period_row.status <> 'open'
       OR prepared.posting_date < period_row.start_date
       OR prepared.posting_date > period_row.end_date THEN
        RAISE EXCEPTION 'Protected ECL allowance posting requires the same open fiscal period confirmed at preparation.';
    END IF;

    SELECT * INTO expense_account
    FROM accounting.accounts account
    WHERE account.id = prepared.credit_loss_expense_account_id
    FOR SHARE;
    SELECT * INTO allowance_account
    FROM accounting.accounts account
    WHERE account.id = prepared.allowance_account_id
    FOR SHARE;
    IF expense_account.id IS NULL
       OR expense_account.system_key <> 'credit_loss_expense'
       OR expense_account.code <> '5000'
       OR expense_account.is_active IS DISTINCT FROM true
       OR expense_account.is_posting IS DISTINCT FROM true
       OR allowance_account.id IS NULL
       OR allowance_account.system_key <> 'allowance_expected_credit_loss'
       OR allowance_account.code <> '1190'
       OR allowance_account.is_active IS DISTINCT FROM true
       OR allowance_account.is_posting IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'Protected ECL allowance posting accounts changed or are no longer active posting accounts.';
    END IF;

    SELECT * INTO journal_row
    FROM accounting.journal_entries journal
    WHERE journal.id = prepared.journal_entry_id;
    IF journal_row.id IS NULL
       OR journal_row.source_type <> 'ecl_allowance'
       OR journal_row.source_reference <> prepared.measurement_id::text
       OR journal_row.source_event_key <> prepared.source_event_key
       OR journal_row.posting_date <> prepared.posting_date
       OR journal_row.fiscal_period_id <> prepared.fiscal_period_id THEN
        RAISE EXCEPTION 'Protected ECL allowance journal identity changed after preparation.';
    END IF;

    SELECT
        count(*)::integer,
        count(*) FILTER (
            WHERE (line.line_number = 1
                   AND line.account_id = prepared.credit_loss_expense_account_id
                   AND line.debit = prepared.allowance_amount
                   AND line.credit = 0
                   AND line.loan_id = prepared.loan_id
                   AND line.client_id = prepared.client_id)
               OR (line.line_number = 2
                   AND line.account_id = prepared.allowance_account_id
                   AND line.debit = 0
                   AND line.credit = prepared.allowance_amount
                   AND line.loan_id = prepared.loan_id
                   AND line.client_id = prepared.client_id)
        )::integer,
        coalesce(sum(line.debit), 0)::numeric(18,2),
        coalesce(sum(line.credit), 0)::numeric(18,2)
    INTO line_count, exact_line_count, total_debit, total_credit
    FROM accounting.journal_lines line
    WHERE line.journal_entry_id = prepared.journal_entry_id;
    IF line_count <> 2
       OR exact_line_count <> 2
       OR total_debit <> prepared.allowance_amount
       OR total_credit <> prepared.allowance_amount THEN
        RAISE EXCEPTION 'Protected ECL allowance journal lines changed after preparation.';
    END IF;

    SELECT * INTO existing
    FROM accounting.ecl_allowance_postings posted
    WHERE posted.preparation_id = prepared.id;

    IF existing.id IS NOT NULL THEN
        IF existing.measurement_id <> prepared.measurement_id
           OR existing.loan_id <> prepared.loan_id
           OR existing.client_id <> prepared.client_id
           OR existing.measurement_version <> prepared.measurement_version
           OR existing.calculation_digest <> prepared.calculation_digest
           OR existing.journal_entry_id <> prepared.journal_entry_id
           OR existing.source_event_key <> prepared.source_event_key
           OR existing.posting_date <> prepared.posting_date
           OR existing.fiscal_period_id <> prepared.fiscal_period_id
           OR existing.credit_loss_expense_account_id <> prepared.credit_loss_expense_account_id
           OR existing.allowance_account_id <> prepared.allowance_account_id
           OR existing.allowance_amount <> prepared.allowance_amount
           OR existing.prior_allowance_balance <> prepared.prior_allowance_balance
           OR existing.preparation_review_token <> prepared.preparation_review_token
           OR existing.preparation_digest <> prepared.preparation_digest
           OR existing.posting_review_token <> normalized_posting_token
           OR existing.draft_policy_version <> prepared.draft_policy_version
           OR existing.posting_policy_version <> p_posting_policy_version THEN
            RAISE EXCEPTION 'Existing protected ECL allowance posting audit does not match the confirmed posting identity.';
        END IF;
        IF journal_row.status <> 'posted'
           OR journal_row.entry_number <> existing.entry_number THEN
            RAISE EXCEPTION 'Existing protected ECL allowance journal no longer matches its immutable posting audit.';
        END IF;
        current_allowance := accounting.ecl_loan_allowance_balance(prepared.loan_id);
        IF current_allowance <> existing.resulting_allowance_balance THEN
            RAISE EXCEPTION 'Existing protected ECL allowance balance no longer reconciles to its posting audit.';
        END IF;
        RETURN existing.id;
    END IF;

    IF journal_row.status <> 'draft'
       OR journal_row.entry_number IS NOT NULL
       OR journal_row.posted_by_user_id IS NOT NULL
       OR journal_row.posted_at IS NOT NULL THEN
        RAISE EXCEPTION 'Only the exact protected draft ECL allowance journal can be posted.';
    END IF;

    current_allowance := accounting.ecl_loan_allowance_balance(prepared.loan_id);
    IF current_allowance <> prepared.prior_allowance_balance
       OR current_allowance <> expected_prior THEN
        RAISE EXCEPTION 'Prior allowance state changed after preparation; A5 remeasurement accounting is required.';
    END IF;

    PERFORM set_config('accounting.ecl_allowance_journal_post_allowed', 'on', true);
    entry_number_value := accounting.post_journal_entry(
        prepared.journal_entry_id,
        p_actor_user_id
    );
    PERFORM set_config('accounting.ecl_allowance_journal_post_allowed', 'off', true);

    resulting_allowance := accounting.ecl_loan_allowance_balance(prepared.loan_id);
    IF resulting_allowance <> prepared.prior_allowance_balance + prepared.allowance_amount THEN
        RAISE EXCEPTION 'Posted account 1190 balance does not reconcile to the confirmed ECL allowance amount.';
    END IF;

    PERFORM set_config('accounting.ecl_allowance_posting_audit_allowed', 'on', true);
    INSERT INTO accounting.ecl_allowance_postings (
        preparation_id, measurement_id, loan_id, client_id,
        measurement_version, calculation_digest, journal_entry_id,
        source_event_key, posting_date, fiscal_period_id,
        credit_loss_expense_account_id, allowance_account_id,
        allowance_amount, prior_allowance_balance, resulting_allowance_balance,
        preparation_review_token, preparation_digest, posting_review_token,
        draft_policy_version, posting_policy_version, entry_number,
        posted_by_user_id
    ) VALUES (
        prepared.id, prepared.measurement_id, prepared.loan_id, prepared.client_id,
        prepared.measurement_version, prepared.calculation_digest,
        prepared.journal_entry_id, prepared.source_event_key,
        prepared.posting_date, prepared.fiscal_period_id,
        prepared.credit_loss_expense_account_id, prepared.allowance_account_id,
        prepared.allowance_amount, prepared.prior_allowance_balance,
        resulting_allowance, prepared.preparation_review_token,
        prepared.preparation_digest, normalized_posting_token,
        prepared.draft_policy_version, p_posting_policy_version,
        entry_number_value, p_actor_user_id
    ) RETURNING id INTO posting_id;

    INSERT INTO accounting.ecl_allowance_posting_lines (
        posting_id, line_number, account_id, account_system_key,
        debit, credit, client_id, loan_id
    )
    SELECT
        posting_id,
        line.line_number,
        line.account_id,
        account.system_key,
        line.debit,
        line.credit,
        line.client_id,
        line.loan_id
    FROM accounting.journal_lines line
    JOIN accounting.accounts account ON account.id = line.account_id
    WHERE line.journal_entry_id = prepared.journal_entry_id
    ORDER BY line.line_number;
    PERFORM set_config('accounting.ecl_allowance_posting_audit_allowed', 'off', true);

    INSERT INTO core.audit_logs (actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.ecl.allowance.posted',
        'ecl_allowance_posting',
        posting_id,
        jsonb_build_object(
            'preparation_id', prepared.id,
            'measurement_id', prepared.measurement_id,
            'loan_id', prepared.loan_id,
            'measurement_version', prepared.measurement_version,
            'calculation_digest', prepared.calculation_digest,
            'journal_entry_id', prepared.journal_entry_id,
            'entry_number', entry_number_value,
            'posting_date', prepared.posting_date,
            'fiscal_period_id', prepared.fiscal_period_id,
            'credit_loss_expense_account_id', prepared.credit_loss_expense_account_id,
            'allowance_account_id', prepared.allowance_account_id,
            'allowance_amount', prepared.allowance_amount,
            'prior_allowance_balance', prepared.prior_allowance_balance,
            'resulting_allowance_balance', resulting_allowance,
            'preparation_digest', prepared.preparation_digest,
            'account_1190_posting_enabled', true,
            'automatic_source_posting', false
        )
    );

    RETURN posting_id;
END;
$$;

CREATE OR REPLACE VIEW accounting.ecl_allowance_posting_queue AS
SELECT
    measurement_queue.loan_id,
    measurement_queue.loan_number,
    measurement_queue.loan_status,
    measurement_queue.loan_type_code,
    measurement_queue.loan_type_name,
    measurement_queue.calculation_mode,
    measurement_queue.measurement_id,
    measurement_queue.measurement_version,
    measurement_queue.measurement_date,
    measurement_queue.loss_horizon,
    measurement_queue.calculation_digest,
    measurement_queue.measurement_status,
    measurement_queue.authoritative_ecl_amount,
    prepared.id AS preparation_id,
    prepared.journal_entry_id,
    prepared.source_event_key,
    prepared.posting_date,
    prepared.fiscal_period_id,
    prepared.credit_loss_expense_account_id,
    prepared.allowance_account_id,
    prepared.allowance_amount,
    prepared.prior_allowance_balance,
    prepared.preparation_review_token,
    prepared.preparation_digest,
    prepared.draft_policy_version,
    journal.status AS journal_status,
    journal.entry_number,
    posting.id AS posting_id,
    posting.posting_review_token,
    posting.posting_policy_version,
    accounting.ecl_loan_allowance_balance(measurement_queue.loan_id)
        AS current_allowance_balance,
    CASE
        WHEN measurement_queue.measurement_status <> 'measured_read_only'
          OR measurement_queue.authoritative_ecl_amount IS NULL
            THEN 'measurement_not_authoritative'
        WHEN measurement_queue.authoritative_ecl_amount = 0
          AND accounting.ecl_loan_allowance_balance(measurement_queue.loan_id) = 0
            THEN 'no_allowance_required'
        WHEN posting.id IS NOT NULL
          AND posting.measurement_id = measurement_queue.measurement_id
          AND accounting.ecl_loan_allowance_balance(measurement_queue.loan_id)
              = posting.resulting_allowance_balance
            THEN 'posted_current'
        WHEN accounting.ecl_loan_allowance_balance(measurement_queue.loan_id) <> 0
            THEN 'a5_remeasurement_required'
        WHEN prepared.id IS NOT NULL AND journal.status = 'draft'
            THEN 'posting_ready'
        WHEN prepared.id IS NOT NULL AND journal.status = 'posted' AND posting.id IS NULL
            THEN 'posting_audit_incomplete'
        ELSE 'preparation_required'
    END AS allowance_posting_status,
    (
        measurement_queue.measurement_status = 'measured_read_only'
        AND measurement_queue.authoritative_ecl_amount > 0
        AND accounting.ecl_loan_allowance_balance(measurement_queue.loan_id) = 0
        AND posting.id IS NULL
    ) AS protected_allowance_action_ready,
    true AS account_1190_posting_enabled,
    false AS automatic_source_posting
FROM accounting.ecl_quantitative_measurement_queue measurement_queue
LEFT JOIN accounting.ecl_allowance_draft_preparations prepared
  ON prepared.measurement_id = measurement_queue.measurement_id
LEFT JOIN accounting.journal_entries journal
  ON journal.id = prepared.journal_entry_id
LEFT JOIN accounting.ecl_allowance_postings posting
  ON posting.preparation_id = prepared.id;

CREATE OR REPLACE VIEW accounting.ecl_allowance_posting_summary AS
SELECT
    count(*)::bigint AS loan_count,
    count(*) FILTER (WHERE allowance_posting_status = 'measurement_not_authoritative')::bigint
        AS measurement_not_authoritative_count,
    count(*) FILTER (WHERE allowance_posting_status = 'no_allowance_required')::bigint
        AS no_allowance_required_count,
    count(*) FILTER (WHERE allowance_posting_status = 'preparation_required')::bigint
        AS preparation_required_count,
    count(*) FILTER (WHERE allowance_posting_status = 'posting_ready')::bigint
        AS posting_ready_count,
    count(*) FILTER (WHERE allowance_posting_status = 'posted_current')::bigint
        AS posted_current_count,
    count(*) FILTER (WHERE allowance_posting_status = 'a5_remeasurement_required')::bigint
        AS a5_remeasurement_required_count,
    count(*) FILTER (WHERE allowance_posting_status = 'posting_audit_incomplete')::bigint
        AS posting_audit_incomplete_count,
    coalesce(sum(current_allowance_balance), 0)::numeric(18,2)
        AS protected_allowance_balance_total,
    true AS account_1190_posting_enabled,
    false AS automatic_source_posting
FROM accounting.ecl_allowance_posting_queue;

COMMENT ON FUNCTION accounting.prepare_initial_ecl_allowance_journal(
    UUID, UUID, TEXT, TEXT, NUMERIC, DATE, UUID, UUID, UUID, NUMERIC, TEXT
) IS
'A4 protected initial allowance preparation. Requires exact current authoritative A3 measurement, exact open period/accounts/amount and prior per-loan allowance 0.00; creates an immutable draft only.';

COMMENT ON FUNCTION accounting.post_initial_ecl_allowance_journal(
    UUID, UUID, TEXT, UUID, TEXT, UUID, TEXT, TEXT, DATE, UUID, UUID, UUID,
    NUMERIC, NUMERIC, TEXT
) IS
'A4 explicit Management posting. Revalidates exact measurement, period, 5000/1190 accounts, amount, journal identity and prior allowance state inside the posting transaction; exact retry is idempotent and automatic source posting stays disabled.';

COMMENT ON VIEW accounting.ecl_allowance_posting_queue IS
'A4 protected allowance queue. Non-zero prior allowance or a changed measurement fails closed into A5 remeasurement-required state; account 1190 is writable only through protected ECL accounting.';

COMMIT;
