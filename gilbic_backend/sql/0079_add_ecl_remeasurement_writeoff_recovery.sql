BEGIN;

-- Master #296 A5: controlled ECL remeasurement, full write-off and post-write-off
-- cash recovery. Every action is explicit Management accounting. Prior A3/A4/A5
-- evidence stays immutable and automatic source posting remains disabled.

INSERT INTO core.permissions (code, description)
VALUES
    ('accounting.ecl.remeasurement.post', 'Post a protected ECL allowance increase/decrease/reversal from an exact new authoritative measurement'),
    ('accounting.ecl.writeoff.post', 'Post a protected full accounting write-off from current write-off support and exact gross carrying/allowance evidence'),
    ('accounting.ecl.recovery.post', 'Post an exact protected post-write-off cash recovery without recreating a receivable')
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code IN (
      'accounting.ecl.remeasurement.post',
      'accounting.ecl.writeoff.post',
      'accounting.ecl.recovery.post'
  )
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.ecl_allowance_remeasurements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    measurement_id UUID NOT NULL UNIQUE
        REFERENCES accounting.ecl_quantitative_measurements(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    measurement_version INTEGER NOT NULL CHECK (measurement_version > 0),
    calculation_digest TEXT NOT NULL CHECK (calculation_digest ~ '^[0-9a-f]{64}$'),
    prior_allowance_balance NUMERIC(18,2) NOT NULL CHECK (prior_allowance_balance > 0),
    target_allowance_balance NUMERIC(18,2) NOT NULL CHECK (target_allowance_balance >= 0),
    adjustment_amount NUMERIC(18,2) NOT NULL CHECK (adjustment_amount > 0),
    adjustment_direction TEXT NOT NULL CHECK (
        adjustment_direction IN ('increase', 'decrease', 'full_reversal')
    ),
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    source_event_key TEXT NOT NULL UNIQUE CHECK (btrim(source_event_key) <> ''),
    posting_date DATE NOT NULL,
    fiscal_period_id UUID NOT NULL
        REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    credit_loss_expense_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    allowance_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    review_token TEXT NOT NULL CHECK (review_token ~ '^[0-9a-f]{64}$'),
    posting_digest TEXT NOT NULL CHECK (posting_digest ~ '^[0-9a-f]{64}$'),
    policy_version TEXT NOT NULL CHECK (
        policy_version = 'ecl_allowance_remeasurement_posting_v1'
    ),
    entry_number TEXT NOT NULL CHECK (btrim(entry_number) <> ''),
    posted_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    posted_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS ecl_allowance_remeasurements_loan_posted_idx
    ON accounting.ecl_allowance_remeasurements(loan_id, posted_at DESC);

CREATE TABLE IF NOT EXISTS accounting.ecl_accounting_writeoffs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id UUID NOT NULL UNIQUE REFERENCES lending.loans(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    credit_risk_review_id BIGINT NOT NULL
        REFERENCES accounting.ecl_credit_risk_label_reviews(id) ON DELETE RESTRICT,
    measurement_id UUID NOT NULL
        REFERENCES accounting.ecl_quantitative_measurements(id) ON DELETE RESTRICT,
    measurement_version INTEGER NOT NULL CHECK (measurement_version > 0),
    calculation_digest TEXT NOT NULL CHECK (calculation_digest ~ '^[0-9a-f]{64}$'),
    loan_receivable_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    accrued_interest_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    allowance_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    loan_component NUMERIC(18,2) NOT NULL CHECK (loan_component >= 0),
    accrued_interest_component NUMERIC(18,2) NOT NULL CHECK (accrued_interest_component >= 0),
    gross_carrying_amount NUMERIC(18,2) NOT NULL CHECK (gross_carrying_amount > 0),
    allowance_balance NUMERIC(18,2) NOT NULL CHECK (allowance_balance > 0),
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    source_event_key TEXT NOT NULL UNIQUE CHECK (btrim(source_event_key) <> ''),
    posting_date DATE NOT NULL,
    fiscal_period_id UUID NOT NULL
        REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    review_token TEXT NOT NULL CHECK (review_token ~ '^[0-9a-f]{64}$'),
    posting_digest TEXT NOT NULL CHECK (posting_digest ~ '^[0-9a-f]{64}$'),
    policy_version TEXT NOT NULL CHECK (policy_version = 'ecl_full_writeoff_posting_v1'),
    entry_number TEXT NOT NULL CHECK (btrim(entry_number) <> ''),
    posted_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    posted_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (gross_carrying_amount = loan_component + accrued_interest_component),
    CHECK (allowance_balance = gross_carrying_amount)
);

CREATE TABLE IF NOT EXISTS accounting.ecl_post_writeoff_recoveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    writeoff_id UUID NOT NULL
        REFERENCES accounting.ecl_accounting_writeoffs(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    credit_risk_review_id BIGINT NOT NULL
        REFERENCES accounting.ecl_credit_risk_label_reviews(id) ON DELETE RESTRICT,
    recovery_transaction_id UUID NOT NULL UNIQUE
        REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    recovery_amount NUMERIC(18,2) NOT NULL CHECK (recovery_amount > 0),
    cash_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    credit_loss_expense_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    source_event_key TEXT NOT NULL UNIQUE CHECK (btrim(source_event_key) <> ''),
    posting_date DATE NOT NULL,
    fiscal_period_id UUID NOT NULL
        REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    review_token TEXT NOT NULL CHECK (review_token ~ '^[0-9a-f]{64}$'),
    posting_digest TEXT NOT NULL CHECK (posting_digest ~ '^[0-9a-f]{64}$'),
    policy_version TEXT NOT NULL CHECK (
        policy_version = 'ecl_post_writeoff_recovery_posting_v1'
    ),
    entry_number TEXT NOT NULL CHECK (btrim(entry_number) <> ''),
    posted_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    posted_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS ecl_post_writeoff_recoveries_loan_posted_idx
    ON accounting.ecl_post_writeoff_recoveries(loan_id, posted_at DESC);

CREATE OR REPLACE FUNCTION accounting.guard_ecl_a5_audit_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(current_setting('accounting.ecl_a5_audit_insert_allowed', true), '') = 'on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'A5 ECL accounting audit records are immutable and must use the protected Management accounting functions.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_ecl_allowance_remeasurement_audit_guard
    ON accounting.ecl_allowance_remeasurements;
CREATE TRIGGER accounting_ecl_allowance_remeasurement_audit_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.ecl_allowance_remeasurements
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_a5_audit_write();

DROP TRIGGER IF EXISTS accounting_ecl_writeoff_audit_guard
    ON accounting.ecl_accounting_writeoffs;
CREATE TRIGGER accounting_ecl_writeoff_audit_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.ecl_accounting_writeoffs
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_a5_audit_write();

DROP TRIGGER IF EXISTS accounting_ecl_post_writeoff_recovery_audit_guard
    ON accounting.ecl_post_writeoff_recoveries;
CREATE TRIGGER accounting_ecl_post_writeoff_recovery_audit_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.ecl_post_writeoff_recoveries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_a5_audit_write();

CREATE OR REPLACE FUNCTION accounting.require_ecl_a5_management_actor(
    p_actor_user_id UUID,
    p_permission TEXT
)
RETURNS VOID
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    IF p_actor_user_id IS NULL OR NOT EXISTS (
        SELECT 1
        FROM core.users actor
        JOIN core.user_roles user_role ON user_role.user_id = actor.id
        JOIN core.role_permissions role_permission ON role_permission.role_id = user_role.role_id
        WHERE actor.id = p_actor_user_id
          AND actor.status = 'active'
          AND role_permission.permission_code = p_permission
    ) THEN
        RAISE EXCEPTION 'An active Management actor with % permission is required.', p_permission;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.ecl_loan_gross_carrying_components(
    p_loan_id UUID
)
RETURNS TABLE (
    calculation_mode TEXT,
    loan_receivable_account_id UUID,
    loan_receivable_system_key TEXT,
    accrued_interest_account_id UUID,
    loan_component NUMERIC(18,2),
    accrued_interest_component NUMERIC(18,2),
    gross_carrying_amount NUMERIC(18,2)
)
LANGUAGE sql
STABLE
AS $$
    WITH coordinates AS (
        SELECT
            loan.id AS loan_id,
            loan_type.calculation_mode,
            loan_account.id AS loan_account_id,
            loan_account.system_key AS loan_system_key,
            accrued_account.id AS accrued_account_id
        FROM lending.loans loan
        JOIN lending.loan_types loan_type ON loan_type.id = loan.loan_type_id
        JOIN accounting.accounts loan_account
          ON loan_account.system_key = CASE loan_type.calculation_mode
              WHEN 'fixed_daily' THEN 'loans_receivable_regular'
              WHEN 'seven_by_seven' THEN 'loans_receivable_7x7'
              ELSE '__unsupported__'
          END
         AND loan_account.is_active AND loan_account.is_posting
        JOIN accounting.accounts accrued_account
          ON accrued_account.system_key = 'accrued_interest_receivable'
         AND accrued_account.is_active AND accrued_account.is_posting
        WHERE loan.id = p_loan_id
    ), balances AS (
        SELECT
            coordinates.*,
            coalesce(sum(line.debit - line.credit) FILTER (
                WHERE line.account_id = coordinates.loan_account_id
            ), 0)::numeric(18,2) AS loan_balance,
            coalesce(sum(line.debit - line.credit) FILTER (
                WHERE line.account_id = coordinates.accrued_account_id
            ), 0)::numeric(18,2) AS accrued_balance
        FROM coordinates
        LEFT JOIN accounting.journal_lines line
          ON line.loan_id = coordinates.loan_id
        LEFT JOIN accounting.journal_entries journal
          ON journal.id = line.journal_entry_id
         AND journal.status = 'posted'
        WHERE line.id IS NULL OR journal.id IS NOT NULL
        GROUP BY coordinates.loan_id, coordinates.calculation_mode,
                 coordinates.loan_account_id, coordinates.loan_system_key,
                 coordinates.accrued_account_id
    )
    SELECT
        calculation_mode,
        loan_account_id,
        loan_system_key,
        accrued_account_id,
        loan_balance,
        accrued_balance,
        (loan_balance + accrued_balance)::numeric(18,2)
    FROM balances;
$$;

CREATE OR REPLACE FUNCTION accounting.guard_ecl_a5_journal_entry_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    protected_source BOOLEAN;
    reversed_source TEXT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        protected_source := NEW.source_type IN (
            'ecl_allowance_remeasurement',
            'ecl_writeoff',
            'ecl_post_writeoff_recovery'
        );
        IF protected_source
           AND coalesce(current_setting('accounting.ecl_a5_journal_prepare_allowed', true), '') <> 'on' THEN
            RAISE EXCEPTION 'A5 ECL accounting journals must use the protected Management accounting functions.';
        END IF;

        IF NEW.reversal_of_entry_id IS NOT NULL THEN
            SELECT source_type INTO reversed_source
            FROM accounting.journal_entries
            WHERE id = NEW.reversal_of_entry_id;
            IF reversed_source IN (
                'ecl_allowance_remeasurement',
                'ecl_writeoff',
                'ecl_post_writeoff_recovery'
            ) THEN
                RAISE EXCEPTION 'A5 ECL accounting journals cannot be reversed through the manual General Journal.';
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    protected_source := OLD.source_type IN (
        'ecl_allowance_remeasurement',
        'ecl_writeoff',
        'ecl_post_writeoff_recovery'
    );
    IF NOT protected_source THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'A5 ECL accounting journals are immutable and cannot be deleted.';
    END IF;

    IF OLD.status = 'draft' AND NEW.status = 'posted' THEN
        IF coalesce(current_setting('accounting.ecl_a5_journal_post_allowed', true), '') <> 'on' THEN
            RAISE EXCEPTION 'A5 ECL accounting journals require the protected A5 posting workflow.';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'A5 ECL accounting journals are system generated and immutable.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_ecl_a5_journal_entry_guard
    ON accounting.journal_entries;
CREATE TRIGGER accounting_ecl_a5_journal_entry_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_a5_journal_entry_change();

CREATE OR REPLACE FUNCTION accounting.guard_ecl_a5_journal_line_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_entry UUID;
    source_type_value TEXT;
BEGIN
    target_entry := CASE WHEN TG_OP = 'DELETE' THEN OLD.journal_entry_id ELSE NEW.journal_entry_id END;
    SELECT source_type INTO source_type_value
    FROM accounting.journal_entries
    WHERE id = target_entry;

    IF source_type_value IN (
        'ecl_allowance_remeasurement',
        'ecl_writeoff',
        'ecl_post_writeoff_recovery'
    ) AND coalesce(current_setting('accounting.ecl_a5_journal_line_write_allowed', true), '') <> 'on' THEN
        RAISE EXCEPTION 'A5 ECL accounting journal lines are system generated and immutable.';
    END IF;

    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_ecl_a5_journal_line_guard
    ON accounting.journal_lines;
CREATE TRIGGER accounting_ecl_a5_journal_line_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_lines
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_a5_journal_line_change();

CREATE OR REPLACE FUNCTION accounting.guard_ecl_a5_recovery_double_post()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM accounting.ecl_post_writeoff_recoveries recovery
        WHERE recovery.recovery_transaction_id = NEW.transaction_id
    ) THEN
        RAISE EXCEPTION 'Post-write-off recovery transaction is already accounted through the protected A5 recovery path.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_ecl_a5_regular_recovery_double_post_guard
    ON accounting.regular_journal_posting_entries;
CREATE TRIGGER accounting_ecl_a5_regular_recovery_double_post_guard
BEFORE INSERT ON accounting.regular_journal_posting_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_a5_recovery_double_post();

DROP TRIGGER IF EXISTS accounting_ecl_a5_7x7_recovery_double_post_guard
    ON accounting.seven_by_seven_journal_postings;
CREATE TRIGGER accounting_ecl_a5_7x7_recovery_double_post_guard
BEFORE INSERT ON accounting.seven_by_seven_journal_postings
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_a5_recovery_double_post();

CREATE OR REPLACE FUNCTION accounting.post_ecl_allowance_remeasurement(
    p_measurement_id UUID,
    p_actor_user_id UUID,
    p_review_token TEXT,
    p_expected_calculation_digest TEXT,
    p_expected_prior_allowance NUMERIC,
    p_expected_target_allowance NUMERIC,
    p_expected_posting_date DATE,
    p_expected_fiscal_period_id UUID,
    p_expected_credit_loss_expense_account_id UUID,
    p_expected_allowance_account_id UUID,
    p_policy_version TEXT
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
    existing accounting.ecl_allowance_remeasurements%ROWTYPE;
    normalized_token TEXT := lower(btrim(coalesce(p_review_token, '')));
    normalized_digest TEXT := lower(btrim(coalesce(p_expected_calculation_digest, '')));
    prior_amount NUMERIC(18,2) := round(coalesce(p_expected_prior_allowance, -1), 2);
    target_amount NUMERIC(18,2) := round(coalesce(p_expected_target_allowance, -1), 2);
    current_allowance NUMERIC(18,2);
    delta NUMERIC(18,2);
    direction TEXT;
    journal_id UUID;
    entry_number_value TEXT;
    digest_value TEXT;
    result_id UUID;
BEGIN
    PERFORM accounting.require_ecl_a5_management_actor(p_actor_user_id, 'accounting.ecl.remeasurement.post');
    IF p_policy_version IS DISTINCT FROM 'ecl_allowance_remeasurement_posting_v1' THEN
        RAISE EXCEPTION 'Unsupported ECL allowance remeasurement policy version.';
    END IF;
    IF normalized_token !~ '^[0-9a-f]{64}$' OR normalized_digest !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Exact ECL remeasurement review token and calculation digest are required.';
    END IF;
    IF p_expected_prior_allowance IS DISTINCT FROM prior_amount OR prior_amount <= 0
       OR p_expected_target_allowance IS DISTINCT FROM target_amount OR target_amount < 0 THEN
        RAISE EXCEPTION 'ECL remeasurement requires exact currency-cent prior and target allowance amounts.';
    END IF;

    SELECT * INTO existing
    FROM accounting.ecl_allowance_remeasurements item
    WHERE item.measurement_id = p_measurement_id;
    IF existing.id IS NOT NULL THEN
        IF existing.review_token <> normalized_token
           OR existing.calculation_digest <> normalized_digest
           OR existing.prior_allowance_balance <> prior_amount
           OR existing.target_allowance_balance <> target_amount
           OR existing.posting_date <> p_expected_posting_date
           OR existing.fiscal_period_id <> p_expected_fiscal_period_id
           OR existing.credit_loss_expense_account_id <> p_expected_credit_loss_expense_account_id
           OR existing.allowance_account_id <> p_expected_allowance_account_id
           OR existing.policy_version <> p_policy_version THEN
            RAISE EXCEPTION 'Existing ECL remeasurement does not match the confirmed immutable retry identity.';
        END IF;
        IF accounting.ecl_loan_allowance_balance(existing.loan_id) <> existing.target_allowance_balance THEN
            RAISE EXCEPTION 'Existing ECL remeasurement no longer reconciles to the protected allowance balance.';
        END IF;
        RETURN existing.id;
    END IF;

    SELECT * INTO measurement
    FROM accounting.ecl_quantitative_measurements item
    WHERE item.id = p_measurement_id
    FOR SHARE;
    IF measurement.id IS NULL THEN RAISE EXCEPTION 'Quantitative ECL measurement was not found.'; END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended('ecl-a5:' || measurement.loan_id::text, 0));

    SELECT * INTO loan_row FROM lending.loans loan WHERE loan.id = measurement.loan_id FOR UPDATE;
    IF loan_row.id IS NULL THEN RAISE EXCEPTION 'Measured loan was not found.'; END IF;

    SELECT * INTO queue
    FROM accounting.ecl_quantitative_measurement_queue current_queue
    WHERE current_queue.loan_id = measurement.loan_id;
    IF queue.loan_id IS NULL
       OR queue.measurement_status <> 'measured_read_only'
       OR queue.quantitative_input_ready IS DISTINCT FROM true
       OR queue.measurement_forward_evidence_current IS DISTINCT FROM true
       OR queue.measurement_id IS DISTINCT FROM measurement.id
       OR queue.measurement_version IS DISTINCT FROM measurement.measurement_version
       OR queue.calculation_digest IS DISTINCT FROM normalized_digest
       OR queue.authoritative_ecl_amount IS DISTINCT FROM target_amount THEN
        RAISE EXCEPTION 'Remeasurement requires the exact new current authoritative A3 measurement.';
    END IF;
    IF EXISTS (SELECT 1 FROM accounting.ecl_allowance_postings posting WHERE posting.measurement_id = measurement.id) THEN
        RAISE EXCEPTION 'This measurement already created the initial A4 allowance and cannot be consumed again as an A5 remeasurement.';
    END IF;

    current_allowance := accounting.ecl_loan_allowance_balance(measurement.loan_id);
    IF current_allowance <> prior_amount THEN
        RAISE EXCEPTION 'Protected prior allowance changed from the confirmed A5 remeasurement amount.';
    END IF;
    IF measurement.ecl_amount <> target_amount OR measurement.calculation_digest <> normalized_digest
       OR p_expected_posting_date IS DISTINCT FROM measurement.measurement_date THEN
        RAISE EXCEPTION 'ECL remeasurement confirmation changed from the exact measurement snapshot.';
    END IF;

    delta := round(target_amount - prior_amount, 2);
    IF delta = 0 THEN RAISE EXCEPTION 'No ECL allowance adjustment is required for an unchanged target allowance.'; END IF;
    direction := CASE
        WHEN delta > 0 THEN 'increase'
        WHEN target_amount = 0 THEN 'full_reversal'
        ELSE 'decrease'
    END;

    SELECT * INTO period_row FROM accounting.fiscal_periods period
    WHERE period.id = p_expected_fiscal_period_id FOR SHARE;
    IF period_row.id IS NULL OR period_row.status <> 'open'
       OR p_expected_posting_date NOT BETWEEN period_row.start_date AND period_row.end_date THEN
        RAISE EXCEPTION 'ECL remeasurement requires the exact open fiscal period containing the measurement date.';
    END IF;

    SELECT * INTO expense_account FROM accounting.accounts account
    WHERE account.id = p_expected_credit_loss_expense_account_id FOR SHARE;
    IF expense_account.id IS NULL OR expense_account.system_key <> 'credit_loss_expense'
       OR expense_account.code <> '5000' OR expense_account.account_type <> 'expense'
       OR expense_account.normal_balance <> 'debit' OR NOT expense_account.is_active OR NOT expense_account.is_posting THEN
        RAISE EXCEPTION 'Exact active posting account 5000 Credit Loss Expense is required.';
    END IF;
    SELECT * INTO allowance_account FROM accounting.accounts account
    WHERE account.id = p_expected_allowance_account_id FOR SHARE;
    IF allowance_account.id IS NULL OR allowance_account.system_key <> 'allowance_expected_credit_loss'
       OR allowance_account.code <> '1190' OR allowance_account.account_type <> 'asset'
       OR allowance_account.normal_balance <> 'credit' OR NOT allowance_account.is_active OR NOT allowance_account.is_posting THEN
        RAISE EXCEPTION 'Exact active posting account 1190 Allowance for Expected Credit Loss is required.';
    END IF;

    digest_value := encode(sha256(convert_to(concat_ws('|', p_policy_version, measurement.id::text,
        measurement.loan_id::text, loan_row.client_id::text, normalized_digest,
        to_char(prior_amount, 'FM999999999999990.00'), to_char(target_amount, 'FM999999999999990.00'),
        direction, p_expected_posting_date::text, period_row.id::text, expense_account.id::text,
        allowance_account.id::text, normalized_token), 'UTF8')), 'hex');

    PERFORM set_config('accounting.ecl_a5_journal_prepare_allowed', 'on', true);
    INSERT INTO accounting.journal_entries (
        fiscal_period_id, posting_date, description, source_type, source_reference,
        source_event_key, created_by_user_id
    ) VALUES (
        period_row.id, p_expected_posting_date,
        'ECL allowance ' || direction || ' - loan ' || loan_row.loan_number || ' - measurement v' || measurement.measurement_version::text,
        'ecl_allowance_remeasurement', measurement.id::text,
        'ecl_remeasurement:' || measurement.id::text, p_actor_user_id
    ) RETURNING id INTO journal_id;
    PERFORM set_config('accounting.ecl_a5_journal_prepare_allowed', 'off', true);

    PERFORM set_config('accounting.ecl_a5_journal_line_write_allowed', 'on', true);
    PERFORM set_config('accounting.ecl_allowance_journal_line_write_allowed', 'on', true);
    IF delta > 0 THEN
        INSERT INTO accounting.journal_lines (journal_entry_id, line_number, account_id, description, debit, credit, client_id, loan_id)
        VALUES
            (journal_id, 1, expense_account.id, 'ECL remeasurement increase', delta, 0, loan_row.client_id, measurement.loan_id),
            (journal_id, 2, allowance_account.id, 'ECL allowance increase', 0, delta, loan_row.client_id, measurement.loan_id);
    ELSE
        INSERT INTO accounting.journal_lines (journal_entry_id, line_number, account_id, description, debit, credit, client_id, loan_id)
        VALUES
            (journal_id, 1, allowance_account.id, 'ECL allowance decrease/reversal', abs(delta), 0, loan_row.client_id, measurement.loan_id),
            (journal_id, 2, expense_account.id, 'Credit-loss impairment gain/reversal', 0, abs(delta), loan_row.client_id, measurement.loan_id);
    END IF;
    PERFORM set_config('accounting.ecl_allowance_journal_line_write_allowed', 'off', true);
    PERFORM set_config('accounting.ecl_a5_journal_line_write_allowed', 'off', true);

    PERFORM set_config('accounting.ecl_a5_journal_post_allowed', 'on', true);
    entry_number_value := accounting.post_journal_entry(journal_id, p_actor_user_id);
    PERFORM set_config('accounting.ecl_a5_journal_post_allowed', 'off', true);

    IF accounting.ecl_loan_allowance_balance(measurement.loan_id) <> target_amount THEN
        RAISE EXCEPTION 'A5 remeasurement posting did not produce the exact target protected allowance balance.';
    END IF;
    IF coalesce(current_setting('accounting.ecl_a5_force_audit_failure', true), '') = 'on' THEN
        RAISE EXCEPTION 'Forced A5 audit failure.';
    END IF;

    PERFORM set_config('accounting.ecl_a5_audit_insert_allowed', 'on', true);
    INSERT INTO accounting.ecl_allowance_remeasurements (
        measurement_id, loan_id, client_id, measurement_version, calculation_digest,
        prior_allowance_balance, target_allowance_balance, adjustment_amount,
        adjustment_direction, journal_entry_id, source_event_key, posting_date,
        fiscal_period_id, credit_loss_expense_account_id, allowance_account_id,
        review_token, posting_digest, policy_version, entry_number, posted_by_user_id
    ) VALUES (
        measurement.id, measurement.loan_id, loan_row.client_id, measurement.measurement_version,
        normalized_digest, prior_amount, target_amount, abs(delta), direction, journal_id,
        'ecl_remeasurement:' || measurement.id::text, p_expected_posting_date,
        period_row.id, expense_account.id, allowance_account.id, normalized_token,
        digest_value, p_policy_version, entry_number_value, p_actor_user_id
    ) RETURNING id INTO result_id;
    PERFORM set_config('accounting.ecl_a5_audit_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (p_actor_user_id, 'accounting.ecl.remeasurement.posted', 'ecl_allowance_remeasurement', result_id,
        jsonb_build_object('measurement_id', measurement.id, 'loan_id', measurement.loan_id,
            'prior_allowance', prior_amount, 'target_allowance', target_amount,
            'adjustment_amount', abs(delta), 'direction', direction, 'journal_entry_id', journal_id,
            'entry_number', entry_number_value, 'automatic_source_posting', false));
    RETURN result_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.post_ecl_full_writeoff(
    p_loan_id UUID,
    p_actor_user_id UUID,
    p_review_token TEXT,
    p_expected_credit_risk_review_id BIGINT,
    p_expected_measurement_id UUID,
    p_expected_calculation_digest TEXT,
    p_expected_loan_component NUMERIC,
    p_expected_accrued_interest_component NUMERIC,
    p_expected_gross_carrying_amount NUMERIC,
    p_expected_allowance_balance NUMERIC,
    p_expected_loan_receivable_account_id UUID,
    p_expected_accrued_interest_account_id UUID,
    p_expected_allowance_account_id UUID,
    p_expected_posting_date DATE,
    p_expected_fiscal_period_id UUID,
    p_policy_version TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    existing accounting.ecl_accounting_writeoffs%ROWTYPE;
    label RECORD;
    measurement accounting.ecl_quantitative_measurements%ROWTYPE;
    measurement_queue RECORD;
    gross RECORD;
    loan_row lending.loans%ROWTYPE;
    period_row accounting.fiscal_periods%ROWTYPE;
    loan_account accounting.accounts%ROWTYPE;
    accrued_account accounting.accounts%ROWTYPE;
    allowance_account accounting.accounts%ROWTYPE;
    normalized_token TEXT := lower(btrim(coalesce(p_review_token, '')));
    normalized_digest TEXT := lower(btrim(coalesce(p_expected_calculation_digest, '')));
    loan_component NUMERIC(18,2) := round(coalesce(p_expected_loan_component, -1), 2);
    accrued_component NUMERIC(18,2) := round(coalesce(p_expected_accrued_interest_component, -1), 2);
    gross_amount NUMERIC(18,2) := round(coalesce(p_expected_gross_carrying_amount, -1), 2);
    allowance_amount NUMERIC(18,2) := round(coalesce(p_expected_allowance_balance, -1), 2);
    journal_id UUID;
    entry_number_value TEXT;
    digest_value TEXT;
    result_id UUID;
    line_no INTEGER := 1;
BEGIN
    PERFORM accounting.require_ecl_a5_management_actor(p_actor_user_id, 'accounting.ecl.writeoff.post');
    IF p_policy_version IS DISTINCT FROM 'ecl_full_writeoff_posting_v1' THEN RAISE EXCEPTION 'Unsupported ECL full write-off policy version.'; END IF;
    IF normalized_token !~ '^[0-9a-f]{64}$' OR normalized_digest !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'Exact write-off review token and calculation digest are required.'; END IF;
    IF p_expected_loan_component IS DISTINCT FROM loan_component OR loan_component < 0
       OR p_expected_accrued_interest_component IS DISTINCT FROM accrued_component OR accrued_component < 0
       OR p_expected_gross_carrying_amount IS DISTINCT FROM gross_amount OR gross_amount <= 0
       OR p_expected_allowance_balance IS DISTINCT FROM allowance_amount OR allowance_amount <= 0
       OR gross_amount <> loan_component + accrued_component OR allowance_amount <> gross_amount THEN
        RAISE EXCEPTION 'Full write-off requires exact reconciled gross carrying components and an equal protected allowance.';
    END IF;

    SELECT * INTO existing FROM accounting.ecl_accounting_writeoffs item WHERE item.loan_id = p_loan_id;
    IF existing.id IS NOT NULL THEN
        IF existing.review_token <> normalized_token
           OR existing.credit_risk_review_id <> p_expected_credit_risk_review_id
           OR existing.measurement_id <> p_expected_measurement_id
           OR existing.calculation_digest <> normalized_digest
           OR existing.loan_component <> loan_component OR existing.accrued_interest_component <> accrued_component
           OR existing.gross_carrying_amount <> gross_amount OR existing.allowance_balance <> allowance_amount
           OR existing.loan_receivable_account_id <> p_expected_loan_receivable_account_id
           OR existing.accrued_interest_account_id <> p_expected_accrued_interest_account_id
           OR existing.allowance_account_id <> p_expected_allowance_account_id
           OR existing.posting_date <> p_expected_posting_date OR existing.fiscal_period_id <> p_expected_fiscal_period_id
           OR existing.policy_version <> p_policy_version THEN
            RAISE EXCEPTION 'Existing full write-off does not match the confirmed immutable retry identity.';
        END IF;
        SELECT * INTO gross FROM accounting.ecl_loan_gross_carrying_components(existing.loan_id);
        IF coalesce(gross.gross_carrying_amount, -1) <> 0 OR accounting.ecl_loan_allowance_balance(existing.loan_id) <> 0 THEN
            RAISE EXCEPTION 'Existing write-off no longer reconciles to zero gross carrying and zero allowance.';
        END IF;
        RETURN existing.id;
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended('ecl-a5:' || p_loan_id::text, 0));
    SELECT * INTO loan_row FROM lending.loans loan WHERE loan.id = p_loan_id FOR UPDATE;
    IF loan_row.id IS NULL THEN RAISE EXCEPTION 'Loan was not found.'; END IF;

    SELECT * INTO label FROM accounting.ecl_credit_risk_label_queue queue WHERE queue.loan_id = p_loan_id;
    IF label.loan_id IS NULL OR label.current_label_ready IS DISTINCT FROM true
       OR label.review_id IS DISTINCT FROM p_expected_credit_risk_review_id
       OR label.stage_label <> 'stage_3_credit_impaired' OR label.default_label IS DISTINCT FROM true
       OR label.write_off_label <> 'supported_no_reasonable_expectation_of_recovery'
       OR coalesce(btrim(label.write_off_evidence_reference), '') = ''
       OR coalesce(btrim(label.write_off_note), '') = '' THEN
        RAISE EXCEPTION 'Full write-off requires the exact current protected Stage 3/default no-reasonable-expectation-of-recovery review.';
    END IF;

    SELECT * INTO measurement FROM accounting.ecl_quantitative_measurements item
    WHERE item.id = p_expected_measurement_id FOR SHARE;
    IF measurement.id IS NULL OR measurement.loan_id <> p_loan_id OR measurement.calculation_digest <> normalized_digest THEN
        RAISE EXCEPTION 'Exact current quantitative ECL measurement is required for write-off.';
    END IF;
    SELECT * INTO measurement_queue FROM accounting.ecl_quantitative_measurement_queue queue WHERE queue.loan_id = p_loan_id;
    IF measurement_queue.measurement_status <> 'measured_read_only'
       OR measurement_queue.measurement_id IS DISTINCT FROM measurement.id
       OR measurement_queue.calculation_digest IS DISTINCT FROM normalized_digest
       OR measurement_queue.authoritative_ecl_amount IS DISTINCT FROM gross_amount
       OR measurement.ecl_amount <> gross_amount THEN
        RAISE EXCEPTION 'Write-off requires a current authoritative A3 measurement equal to the exact gross carrying amount.';
    END IF;

    SELECT * INTO gross FROM accounting.ecl_loan_gross_carrying_components(p_loan_id);
    IF gross.gross_carrying_amount IS NULL OR gross.loan_component <> loan_component
       OR gross.accrued_interest_component <> accrued_component OR gross.gross_carrying_amount <> gross_amount
       OR gross.loan_receivable_account_id <> p_expected_loan_receivable_account_id
       OR gross.accrued_interest_account_id <> p_expected_accrued_interest_account_id THEN
        RAISE EXCEPTION 'Protected General Ledger gross carrying evidence changed from the confirmed write-off coordinates.';
    END IF;
    IF accounting.ecl_loan_allowance_balance(p_loan_id) <> allowance_amount THEN
        RAISE EXCEPTION 'Protected allowance balance changed from the confirmed full write-off amount.';
    END IF;

    SELECT * INTO loan_account FROM accounting.accounts account WHERE account.id = p_expected_loan_receivable_account_id FOR SHARE;
    IF loan_account.id IS NULL OR loan_account.system_key <> gross.loan_receivable_system_key
       OR loan_account.account_type <> 'asset' OR loan_account.normal_balance <> 'debit'
       OR NOT loan_account.is_active OR NOT loan_account.is_posting THEN RAISE EXCEPTION 'Exact protected loan-receivable account is required.'; END IF;
    SELECT * INTO accrued_account FROM accounting.accounts account WHERE account.id = p_expected_accrued_interest_account_id FOR SHARE;
    IF accrued_account.id IS NULL OR accrued_account.system_key <> 'accrued_interest_receivable'
       OR accrued_account.code <> '1120' OR accrued_account.account_type <> 'asset' OR accrued_account.normal_balance <> 'debit'
       OR NOT accrued_account.is_active OR NOT accrued_account.is_posting THEN RAISE EXCEPTION 'Exact active posting account 1120 is required.'; END IF;
    SELECT * INTO allowance_account FROM accounting.accounts account WHERE account.id = p_expected_allowance_account_id FOR SHARE;
    IF allowance_account.id IS NULL OR allowance_account.system_key <> 'allowance_expected_credit_loss'
       OR allowance_account.code <> '1190' OR allowance_account.account_type <> 'asset' OR allowance_account.normal_balance <> 'credit'
       OR NOT allowance_account.is_active OR NOT allowance_account.is_posting THEN RAISE EXCEPTION 'Exact active posting account 1190 is required.'; END IF;

    IF p_expected_posting_date IS DISTINCT FROM current_date THEN RAISE EXCEPTION 'V1 write-off must use the current authoritative accounting date.'; END IF;
    SELECT * INTO period_row FROM accounting.fiscal_periods period WHERE period.id = p_expected_fiscal_period_id FOR SHARE;
    IF period_row.id IS NULL OR period_row.status <> 'open' OR p_expected_posting_date NOT BETWEEN period_row.start_date AND period_row.end_date THEN RAISE EXCEPTION 'Write-off requires the exact open fiscal period.'; END IF;

    digest_value := encode(sha256(convert_to(concat_ws('|', p_policy_version, p_loan_id::text,
        p_expected_credit_risk_review_id::text, measurement.id::text, normalized_digest,
        to_char(loan_component, 'FM999999999999990.00'), to_char(accrued_component, 'FM999999999999990.00'),
        to_char(gross_amount, 'FM999999999999990.00'), allowance_account.id::text,
        loan_account.id::text, accrued_account.id::text, p_expected_posting_date::text,
        period_row.id::text, normalized_token), 'UTF8')), 'hex');

    PERFORM set_config('accounting.ecl_a5_journal_prepare_allowed', 'on', true);
    INSERT INTO accounting.journal_entries(fiscal_period_id, posting_date, description, source_type, source_reference, source_event_key, created_by_user_id)
    VALUES(period_row.id, p_expected_posting_date, 'Full ECL accounting write-off - loan ' || loan_row.loan_number,
        'ecl_writeoff', p_expected_credit_risk_review_id::text,
        'ecl_writeoff:' || p_loan_id::text, p_actor_user_id) RETURNING id INTO journal_id;
    PERFORM set_config('accounting.ecl_a5_journal_prepare_allowed', 'off', true);

    PERFORM set_config('accounting.ecl_a5_journal_line_write_allowed', 'on', true);
    PERFORM set_config('accounting.ecl_allowance_journal_line_write_allowed', 'on', true);
    INSERT INTO accounting.journal_lines(journal_entry_id, line_number, account_id, description, debit, credit, client_id, loan_id)
    VALUES(journal_id, line_no, allowance_account.id, 'Use protected ECL allowance on full write-off', gross_amount, 0, loan_row.client_id, p_loan_id);
    line_no := line_no + 1;
    IF loan_component > 0 THEN
        INSERT INTO accounting.journal_lines(journal_entry_id, line_number, account_id, description, debit, credit, client_id, loan_id)
        VALUES(journal_id, line_no, loan_account.id, 'Derecognize loan receivable on full write-off', 0, loan_component, loan_row.client_id, p_loan_id);
        line_no := line_no + 1;
    END IF;
    IF accrued_component > 0 THEN
        INSERT INTO accounting.journal_lines(journal_entry_id, line_number, account_id, description, debit, credit, client_id, loan_id)
        VALUES(journal_id, line_no, accrued_account.id, 'Derecognize accrued interest receivable on full write-off', 0, accrued_component, loan_row.client_id, p_loan_id);
    END IF;
    PERFORM set_config('accounting.ecl_allowance_journal_line_write_allowed', 'off', true);
    PERFORM set_config('accounting.ecl_a5_journal_line_write_allowed', 'off', true);

    PERFORM set_config('accounting.ecl_a5_journal_post_allowed', 'on', true);
    entry_number_value := accounting.post_journal_entry(journal_id, p_actor_user_id);
    PERFORM set_config('accounting.ecl_a5_journal_post_allowed', 'off', true);

    SELECT * INTO gross FROM accounting.ecl_loan_gross_carrying_components(p_loan_id);
    IF gross.gross_carrying_amount <> 0 OR accounting.ecl_loan_allowance_balance(p_loan_id) <> 0 THEN
        RAISE EXCEPTION 'Full write-off did not reduce both gross carrying and allowance to zero.';
    END IF;
    IF coalesce(current_setting('accounting.ecl_a5_force_audit_failure', true), '') = 'on' THEN RAISE EXCEPTION 'Forced A5 audit failure.'; END IF;

    PERFORM set_config('accounting.ecl_a5_audit_insert_allowed', 'on', true);
    INSERT INTO accounting.ecl_accounting_writeoffs(
        loan_id, client_id, credit_risk_review_id, measurement_id, measurement_version,
        calculation_digest, loan_receivable_account_id, accrued_interest_account_id,
        allowance_account_id, loan_component, accrued_interest_component, gross_carrying_amount,
        allowance_balance, journal_entry_id, source_event_key, posting_date, fiscal_period_id,
        review_token, posting_digest, policy_version, entry_number, posted_by_user_id
    ) VALUES(p_loan_id, loan_row.client_id, p_expected_credit_risk_review_id, measurement.id,
        measurement.measurement_version, normalized_digest, loan_account.id, accrued_account.id,
        allowance_account.id, loan_component, accrued_component, gross_amount, allowance_amount,
        journal_id, 'ecl_writeoff:' || p_loan_id::text, p_expected_posting_date, period_row.id,
        normalized_token, digest_value, p_policy_version, entry_number_value, p_actor_user_id)
    RETURNING id INTO result_id;
    PERFORM set_config('accounting.ecl_a5_audit_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES(p_actor_user_id, 'accounting.ecl.writeoff.posted', 'ecl_accounting_writeoff', result_id,
        jsonb_build_object('loan_id', p_loan_id, 'credit_risk_review_id', p_expected_credit_risk_review_id,
            'measurement_id', measurement.id, 'gross_carrying_amount', gross_amount,
            'allowance_balance', allowance_amount, 'journal_entry_id', journal_id,
            'entry_number', entry_number_value, 'automatic_source_posting', false));
    RETURN result_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.post_ecl_post_writeoff_recovery(
    p_credit_risk_review_id BIGINT,
    p_actor_user_id UUID,
    p_review_token TEXT,
    p_expected_recovery_transaction_id UUID,
    p_expected_recovery_amount NUMERIC,
    p_expected_posting_date DATE,
    p_expected_fiscal_period_id UUID,
    p_expected_cash_account_id UUID,
    p_expected_credit_loss_expense_account_id UUID,
    p_policy_version TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    existing accounting.ecl_post_writeoff_recoveries%ROWTYPE;
    review accounting.ecl_credit_risk_label_reviews%ROWTYPE;
    queue RECORD;
    tx lending.collection_transactions%ROWTYPE;
    writeoff accounting.ecl_accounting_writeoffs%ROWTYPE;
    period_row accounting.fiscal_periods%ROWTYPE;
    cash_account accounting.accounts%ROWTYPE;
    expense_account accounting.accounts%ROWTYPE;
    gross RECORD;
    normalized_token TEXT := lower(btrim(coalesce(p_review_token, '')));
    recovery_amount NUMERIC(18,2) := round(coalesce(p_expected_recovery_amount, -1), 2);
    journal_id UUID;
    entry_number_value TEXT;
    digest_value TEXT;
    result_id UUID;
BEGIN
    PERFORM accounting.require_ecl_a5_management_actor(p_actor_user_id, 'accounting.ecl.recovery.post');
    IF p_policy_version IS DISTINCT FROM 'ecl_post_writeoff_recovery_posting_v1' THEN RAISE EXCEPTION 'Unsupported post-write-off recovery policy version.'; END IF;
    IF normalized_token !~ '^[0-9a-f]{64}$' OR p_expected_recovery_amount IS DISTINCT FROM recovery_amount OR recovery_amount <= 0 THEN
        RAISE EXCEPTION 'Exact recovery review token and positive currency-cent amount are required.';
    END IF;

    SELECT * INTO existing FROM accounting.ecl_post_writeoff_recoveries item
    WHERE item.recovery_transaction_id = p_expected_recovery_transaction_id;
    IF existing.id IS NOT NULL THEN
        IF existing.credit_risk_review_id <> p_credit_risk_review_id OR existing.review_token <> normalized_token
           OR existing.recovery_amount <> recovery_amount OR existing.posting_date <> p_expected_posting_date
           OR existing.fiscal_period_id <> p_expected_fiscal_period_id OR existing.cash_account_id <> p_expected_cash_account_id
           OR existing.credit_loss_expense_account_id <> p_expected_credit_loss_expense_account_id
           OR existing.policy_version <> p_policy_version THEN
            RAISE EXCEPTION 'Existing post-write-off recovery does not match the confirmed immutable retry identity.';
        END IF;
        RETURN existing.id;
    END IF;

    SELECT * INTO review FROM accounting.ecl_credit_risk_label_reviews item WHERE item.id = p_credit_risk_review_id FOR SHARE;
    IF review.id IS NULL OR review.recovery_label <> 'cash_recovery_observed'
       OR review.recovery_transaction_id IS DISTINCT FROM p_expected_recovery_transaction_id THEN
        RAISE EXCEPTION 'Post-write-off recovery requires the exact protected cash_recovery_observed review and transaction.';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('ecl-a5:' || review.loan_id::text, 0));

    SELECT * INTO queue FROM accounting.ecl_credit_risk_label_queue current_queue WHERE current_queue.loan_id = review.loan_id;
    IF queue.current_label_ready IS DISTINCT FROM true OR queue.review_id IS DISTINCT FROM review.id
       OR queue.recovery_label <> 'cash_recovery_observed' THEN
        RAISE EXCEPTION 'Post-write-off recovery review is no longer the exact current protected credit-risk review.';
    END IF;

    SELECT * INTO writeoff FROM accounting.ecl_accounting_writeoffs item WHERE item.loan_id = review.loan_id;
    IF writeoff.id IS NULL THEN RAISE EXCEPTION 'A completed protected accounting write-off is required before post-write-off recovery.'; END IF;

    SELECT * INTO tx FROM lending.collection_transactions transaction
    WHERE transaction.id = p_expected_recovery_transaction_id FOR SHARE;
    IF tx.id IS NULL OR tx.loan_id <> review.loan_id OR tx.is_voided OR tx.amount <> recovery_amount
       OR tx.amount <= 0 OR tx.entry_type NOT IN ('payment', 'advance') OR tx.accepted_at IS NULL
       OR tx.accepted_at <= writeoff.posted_at OR p_expected_posting_date IS DISTINCT FROM tx.collection_date THEN
        RAISE EXCEPTION 'Recovery must be the exact later same-loan non-voided protected positive cash transaction after accounting write-off.';
    END IF;
    IF EXISTS (SELECT 1 FROM accounting.regular_journal_posting_entries posted WHERE posted.transaction_id = tx.id)
       OR EXISTS (SELECT 1 FROM accounting.seven_by_seven_journal_postings posted WHERE posted.transaction_id = tx.id) THEN
        RAISE EXCEPTION 'Recovery transaction already has normal source-event accounting and cannot also use the A5 post-write-off recovery path.';
    END IF;

    SELECT * INTO gross FROM accounting.ecl_loan_gross_carrying_components(review.loan_id);
    IF coalesce(gross.gross_carrying_amount, -1) <> 0 OR accounting.ecl_loan_allowance_balance(review.loan_id) <> 0 THEN
        RAISE EXCEPTION 'Post-write-off recovery requires zero protected gross carrying and zero protected allowance.';
    END IF;

    SELECT * INTO period_row FROM accounting.fiscal_periods period WHERE period.id = p_expected_fiscal_period_id FOR SHARE;
    IF period_row.id IS NULL OR period_row.status <> 'open' OR p_expected_posting_date NOT BETWEEN period_row.start_date AND period_row.end_date THEN
        RAISE EXCEPTION 'Recovery requires the exact open fiscal period containing the protected collection date.';
    END IF;
    SELECT * INTO cash_account FROM accounting.accounts account WHERE account.id = p_expected_cash_account_id FOR SHARE;
    IF cash_account.id IS NULL OR cash_account.system_key <> 'cash_collector_custody' OR cash_account.code <> '1020'
       OR cash_account.account_type <> 'asset' OR cash_account.normal_balance <> 'debit' OR NOT cash_account.is_active OR NOT cash_account.is_posting THEN
        RAISE EXCEPTION 'Exact active posting account 1020 Cash - Collector Custody is required.';
    END IF;
    SELECT * INTO expense_account FROM accounting.accounts account WHERE account.id = p_expected_credit_loss_expense_account_id FOR SHARE;
    IF expense_account.id IS NULL OR expense_account.system_key <> 'credit_loss_expense' OR expense_account.code <> '5000'
       OR expense_account.account_type <> 'expense' OR expense_account.normal_balance <> 'debit' OR NOT expense_account.is_active OR NOT expense_account.is_posting THEN
        RAISE EXCEPTION 'Exact active posting account 5000 Credit Loss Expense is required.';
    END IF;

    digest_value := encode(sha256(convert_to(concat_ws('|', p_policy_version, writeoff.id::text,
        review.id::text, tx.id::text, review.loan_id::text,
        to_char(recovery_amount, 'FM999999999999990.00'), p_expected_posting_date::text,
        period_row.id::text, cash_account.id::text, expense_account.id::text, normalized_token), 'UTF8')), 'hex');

    PERFORM set_config('accounting.ecl_a5_journal_prepare_allowed', 'on', true);
    INSERT INTO accounting.journal_entries(fiscal_period_id, posting_date, description, source_type, source_reference, source_event_key, created_by_user_id)
    VALUES(period_row.id, p_expected_posting_date, 'Post-write-off cash recovery - loan ' || review.loan_id::text,
        'ecl_post_writeoff_recovery', tx.id::text, 'ecl_recovery:' || tx.id::text, p_actor_user_id)
    RETURNING id INTO journal_id;
    PERFORM set_config('accounting.ecl_a5_journal_prepare_allowed', 'off', true);

    PERFORM set_config('accounting.ecl_a5_journal_line_write_allowed', 'on', true);
    INSERT INTO accounting.journal_lines(journal_entry_id, line_number, account_id, description, debit, credit, client_id, loan_id)
    VALUES
        (journal_id, 1, cash_account.id, 'Exact protected post-write-off cash recovery', recovery_amount, 0, writeoff.client_id, review.loan_id),
        (journal_id, 2, expense_account.id, 'Post-write-off recovery recognized in credit-loss profit or loss', 0, recovery_amount, writeoff.client_id, review.loan_id);
    PERFORM set_config('accounting.ecl_a5_journal_line_write_allowed', 'off', true);

    PERFORM set_config('accounting.ecl_a5_journal_post_allowed', 'on', true);
    entry_number_value := accounting.post_journal_entry(journal_id, p_actor_user_id);
    PERFORM set_config('accounting.ecl_a5_journal_post_allowed', 'off', true);
    IF coalesce(current_setting('accounting.ecl_a5_force_audit_failure', true), '') = 'on' THEN RAISE EXCEPTION 'Forced A5 audit failure.'; END IF;

    PERFORM set_config('accounting.ecl_a5_audit_insert_allowed', 'on', true);
    INSERT INTO accounting.ecl_post_writeoff_recoveries(
        writeoff_id, loan_id, client_id, credit_risk_review_id, recovery_transaction_id,
        recovery_amount, cash_account_id, credit_loss_expense_account_id, journal_entry_id,
        source_event_key, posting_date, fiscal_period_id, review_token, posting_digest,
        policy_version, entry_number, posted_by_user_id
    ) VALUES(writeoff.id, review.loan_id, writeoff.client_id, review.id, tx.id, recovery_amount,
        cash_account.id, expense_account.id, journal_id, 'ecl_recovery:' || tx.id::text,
        p_expected_posting_date, period_row.id, normalized_token, digest_value,
        p_policy_version, entry_number_value, p_actor_user_id) RETURNING id INTO result_id;
    PERFORM set_config('accounting.ecl_a5_audit_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES(p_actor_user_id, 'accounting.ecl.post_writeoff_recovery.posted', 'ecl_post_writeoff_recovery', result_id,
        jsonb_build_object('writeoff_id', writeoff.id, 'loan_id', review.loan_id,
            'credit_risk_review_id', review.id, 'recovery_transaction_id', tx.id,
            'recovery_amount', recovery_amount, 'journal_entry_id', journal_id,
            'entry_number', entry_number_value, 'automatic_source_posting', false));
    RETURN result_id;
END;
$$;

CREATE OR REPLACE VIEW accounting.ecl_a5_action_queue AS
SELECT
    loan.id AS loan_id,
    loan.loan_number,
    loan.status AS loan_status,
    loan_type.calculation_mode,
    label.review_id AS credit_risk_review_id,
    label.stage_label,
    label.default_label,
    label.write_off_label,
    label.recovery_label,
    measurement.measurement_id,
    measurement.measurement_version,
    measurement.measurement_date,
    measurement.calculation_digest,
    measurement.measurement_status,
    measurement.authoritative_ecl_amount,
    accounting.ecl_loan_allowance_balance(loan.id)::numeric(18,2) AS current_allowance_balance,
    gross.loan_receivable_account_id,
    gross.loan_receivable_system_key,
    gross.accrued_interest_account_id,
    gross.loan_component,
    gross.accrued_interest_component,
    gross.gross_carrying_amount,
    writeoff.id AS writeoff_id,
    recovery_tx.id AS recovery_transaction_id,
    recovery_tx.amount::numeric(18,2) AS recovery_amount,
    CASE
        WHEN writeoff.id IS NOT NULL AND gross.gross_carrying_amount = 0
             AND accounting.ecl_loan_allowance_balance(loan.id) = 0
             AND label.recovery_label = 'cash_recovery_observed'
             AND recovery_tx.id IS NOT NULL
             AND NOT EXISTS (SELECT 1 FROM accounting.ecl_post_writeoff_recoveries r WHERE r.recovery_transaction_id = recovery_tx.id)
            THEN 'post_writeoff_recovery_ready'
        WHEN writeoff.id IS NOT NULL AND gross.gross_carrying_amount = 0
             AND accounting.ecl_loan_allowance_balance(loan.id) = 0
            THEN 'written_off'
        WHEN label.current_label_ready AND label.write_off_label = 'supported_no_reasonable_expectation_of_recovery'
             AND measurement.measurement_status = 'measured_read_only'
             AND measurement.authoritative_ecl_amount = gross.gross_carrying_amount
             AND accounting.ecl_loan_allowance_balance(loan.id) = gross.gross_carrying_amount
             AND gross.gross_carrying_amount > 0
            THEN 'writeoff_ready'
        WHEN measurement.measurement_status = 'measured_read_only'
             AND accounting.ecl_loan_allowance_balance(loan.id) > 0
             AND measurement.authoritative_ecl_amount IS DISTINCT FROM accounting.ecl_loan_allowance_balance(loan.id)
            THEN 'remeasurement_required'
        WHEN measurement.measurement_status = 'measured_read_only'
             AND accounting.ecl_loan_allowance_balance(loan.id) = measurement.authoritative_ecl_amount
             AND accounting.ecl_loan_allowance_balance(loan.id) > 0
            THEN 'allowance_current'
        ELSE 'blocked'
    END AS a5_status,
    true AS protected_a5_accounting_enabled,
    false AS automatic_source_posting
FROM lending.loans loan
JOIN lending.loan_types loan_type ON loan_type.id = loan.loan_type_id
LEFT JOIN accounting.ecl_credit_risk_label_queue label ON label.loan_id = loan.id
LEFT JOIN accounting.ecl_quantitative_measurement_queue measurement ON measurement.loan_id = loan.id
LEFT JOIN LATERAL accounting.ecl_loan_gross_carrying_components(loan.id) gross ON true
LEFT JOIN accounting.ecl_accounting_writeoffs writeoff ON writeoff.loan_id = loan.id
LEFT JOIN accounting.ecl_credit_risk_label_reviews current_review ON current_review.id = label.review_id
LEFT JOIN lending.collection_transactions recovery_tx ON recovery_tx.id = current_review.recovery_transaction_id
WHERE loan.status = 'active';

CREATE OR REPLACE VIEW accounting.ecl_a5_summary AS
SELECT
    count(*)::bigint AS loan_count,
    count(*) FILTER (WHERE a5_status = 'remeasurement_required')::bigint AS remeasurement_required_count,
    count(*) FILTER (WHERE a5_status = 'allowance_current')::bigint AS allowance_current_count,
    count(*) FILTER (WHERE a5_status = 'writeoff_ready')::bigint AS writeoff_ready_count,
    count(*) FILTER (WHERE a5_status = 'written_off')::bigint AS written_off_count,
    count(*) FILTER (WHERE a5_status = 'post_writeoff_recovery_ready')::bigint AS recovery_ready_count,
    count(*) FILTER (WHERE a5_status = 'blocked')::bigint AS blocked_count,
    (SELECT count(*)::bigint FROM accounting.ecl_allowance_remeasurements) AS remeasurement_posting_count,
    (SELECT count(*)::bigint FROM accounting.ecl_accounting_writeoffs) AS writeoff_posting_count,
    (SELECT count(*)::bigint FROM accounting.ecl_post_writeoff_recoveries) AS post_writeoff_recovery_count,
    true AS protected_a5_accounting_enabled,
    false AS automatic_source_posting
FROM accounting.ecl_a5_action_queue;

COMMENT ON FUNCTION accounting.post_ecl_allowance_remeasurement(UUID,UUID,TEXT,TEXT,NUMERIC,NUMERIC,DATE,UUID,UUID,UUID,TEXT) IS
'A5 explicit Management remeasurement posting from an exact new authoritative A3 measurement. Adjusts 1190 to the exact target through 5000, preserves prior measurements/postings, enforces exact retry identity and automatic_source_posting=false.';
COMMENT ON FUNCTION accounting.post_ecl_full_writeoff(UUID,UUID,TEXT,BIGINT,UUID,TEXT,NUMERIC,NUMERIC,NUMERIC,NUMERIC,UUID,UUID,UUID,DATE,UUID,TEXT) IS
'A5 full accounting write-off only. Requires current Stage 3/default write-off support, authoritative ECL equal to exact protected gross carrying, equal protected 1190 allowance, direct gross carrying derecognition and immutable audit.';
COMMENT ON FUNCTION accounting.post_ecl_post_writeoff_recovery(BIGINT,UUID,TEXT,UUID,NUMERIC,DATE,UUID,UUID,UUID,TEXT) IS
'A5 post-write-off recovery posting. Requires exact later same-loan protected cash_recovery_observed transaction after completed accounting write-off; Dr 1020 / Cr 5000, no receivable recreation, immutable audit and automatic_source_posting=false.';

COMMIT;
