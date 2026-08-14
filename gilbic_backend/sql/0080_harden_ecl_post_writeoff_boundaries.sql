BEGIN;

-- Master #296 A5 hardening. Once a loan has been fully derecognized by the
-- protected A5 write-off path, no later A3 measurement, A4 allowance lifecycle,
-- A5 remeasurement, or normal Regular/7x7 collection accounting may recreate
-- a receivable or allowance. Later same-loan cash is handled only through the
-- dedicated protected post-write-off recovery evidence + accounting path.
-- Automatic source posting remains disabled.

INSERT INTO core.permissions (code, description)
VALUES (
    'accounting.ecl.recovery.review',
    'Review exact protected same-loan cash evidence after accounting write-off without requiring a derecognized loan to regain contractual DPD readiness'
)
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code = 'accounting.ecl.recovery.review'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.ecl_post_writeoff_recovery_review_provenance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    credit_risk_review_id BIGINT NOT NULL UNIQUE
        REFERENCES accounting.ecl_credit_risk_label_reviews(id) ON DELETE RESTRICT,
    writeoff_id UUID NOT NULL
        REFERENCES accounting.ecl_accounting_writeoffs(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    recovery_transaction_id UUID NOT NULL UNIQUE
        REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    recovery_amount NUMERIC(18,2) NOT NULL CHECK (recovery_amount > 0),
    evidence_reference TEXT NOT NULL CHECK (btrim(evidence_reference) <> ''),
    review_note TEXT NOT NULL CHECK (length(btrim(review_note)) >= 20),
    review_token TEXT NOT NULL CHECK (review_token ~ '^[0-9a-f]{64}$'),
    policy_version TEXT NOT NULL CHECK (
        policy_version = 'ecl_post_writeoff_recovery_evidence_review_v1'
    ),
    reviewed_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS ecl_post_writeoff_recovery_review_loan_idx
    ON accounting.ecl_post_writeoff_recovery_review_provenance(loan_id, reviewed_at DESC);

DROP TRIGGER IF EXISTS accounting_ecl_post_writeoff_recovery_review_audit_guard
    ON accounting.ecl_post_writeoff_recovery_review_provenance;
CREATE TRIGGER accounting_ecl_post_writeoff_recovery_review_audit_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.ecl_post_writeoff_recovery_review_provenance
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_a5_audit_write();

CREATE OR REPLACE FUNCTION accounting.guard_ecl_post_writeoff_loan_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM accounting.ecl_accounting_writeoffs writeoff
        WHERE writeoff.loan_id = NEW.loan_id
    ) THEN
        RAISE EXCEPTION 'Loan has been fully written off. New ECL measurement/allowance activity is blocked; later protected cash must use the A5 post-write-off recovery path.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_ecl_post_writeoff_measurement_guard
    ON accounting.ecl_quantitative_measurements;
CREATE TRIGGER accounting_ecl_post_writeoff_measurement_guard
BEFORE INSERT ON accounting.ecl_quantitative_measurements
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_post_writeoff_loan_insert();

DROP TRIGGER IF EXISTS accounting_ecl_post_writeoff_allowance_preparation_guard
    ON accounting.ecl_allowance_draft_preparations;
CREATE TRIGGER accounting_ecl_post_writeoff_allowance_preparation_guard
BEFORE INSERT ON accounting.ecl_allowance_draft_preparations
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_post_writeoff_loan_insert();

DROP TRIGGER IF EXISTS accounting_ecl_post_writeoff_allowance_posting_guard
    ON accounting.ecl_allowance_postings;
CREATE TRIGGER accounting_ecl_post_writeoff_allowance_posting_guard
BEFORE INSERT ON accounting.ecl_allowance_postings
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_post_writeoff_loan_insert();

DROP TRIGGER IF EXISTS accounting_ecl_post_writeoff_remeasurement_guard
    ON accounting.ecl_allowance_remeasurements;
CREATE TRIGGER accounting_ecl_post_writeoff_remeasurement_guard
BEFORE INSERT ON accounting.ecl_allowance_remeasurements
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_post_writeoff_loan_insert();

CREATE OR REPLACE FUNCTION accounting.guard_ecl_post_writeoff_collection_accounting()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_loan_id UUID;
BEGIN
    SELECT transaction_row.loan_id
      INTO target_loan_id
    FROM lending.collection_transactions transaction_row
    WHERE transaction_row.id = NEW.transaction_id;

    IF target_loan_id IS NOT NULL AND EXISTS (
        SELECT 1
        FROM accounting.ecl_accounting_writeoffs writeoff
        WHERE writeoff.loan_id = target_loan_id
    ) THEN
        RAISE EXCEPTION 'Loan has been fully written off. Normal Regular/7x7 collection accounting is blocked; later protected cash must use the A5 post-write-off recovery path.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_ecl_post_writeoff_regular_collection_guard
    ON accounting.regular_journal_posting_entries;
CREATE TRIGGER accounting_ecl_post_writeoff_regular_collection_guard
BEFORE INSERT ON accounting.regular_journal_posting_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_post_writeoff_collection_accounting();

DROP TRIGGER IF EXISTS accounting_ecl_post_writeoff_7x7_collection_guard
    ON accounting.seven_by_seven_journal_postings;
CREATE TRIGGER accounting_ecl_post_writeoff_7x7_collection_guard
BEFORE INSERT ON accounting.seven_by_seven_journal_postings
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_post_writeoff_collection_accounting();

-- A normal credit-risk label refresh correctly requires current contractual-DPD
-- evidence. After accounting write-off, however, derecognition intentionally makes
-- that DPD/gross-carrying evidence unavailable. Recovery observation therefore has
-- a separate protected Management review that copies the last immutable risk
-- snapshot only as chronology and binds the new review to the completed write-off
-- plus one exact later protected cash transaction. It does not record a cure.
CREATE OR REPLACE FUNCTION accounting.review_ecl_post_writeoff_recovery(
    p_loan_id UUID,
    p_actor_user_id UUID,
    p_review_token TEXT,
    p_expected_recovery_transaction_id UUID,
    p_expected_recovery_amount NUMERIC,
    p_evidence_reference TEXT,
    p_review_note TEXT,
    p_policy_version TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    existing accounting.ecl_post_writeoff_recovery_review_provenance%ROWTYPE;
    writeoff accounting.ecl_accounting_writeoffs%ROWTYPE;
    prior_review accounting.ecl_credit_risk_label_reviews%ROWTYPE;
    tx lending.collection_transactions%ROWTYPE;
    gross RECORD;
    normalized_token TEXT := lower(btrim(coalesce(p_review_token, '')));
    normalized_reference TEXT := btrim(coalesce(p_evidence_reference, ''));
    normalized_note TEXT := btrim(coalesce(p_review_note, ''));
    recovery_amount NUMERIC(18,2) := round(coalesce(p_expected_recovery_amount, -1), 2);
    next_version INTEGER;
    new_review_id BIGINT;
    provenance_id UUID;
BEGIN
    PERFORM accounting.require_ecl_a5_management_actor(
        p_actor_user_id,
        'accounting.ecl.recovery.review'
    );

    IF p_policy_version IS DISTINCT FROM 'ecl_post_writeoff_recovery_evidence_review_v1' THEN
        RAISE EXCEPTION 'Unsupported post-write-off recovery evidence review policy version.';
    END IF;
    IF p_loan_id IS NULL OR p_expected_recovery_transaction_id IS NULL THEN
        RAISE EXCEPTION 'Exact loan and protected recovery transaction are required.';
    END IF;
    IF normalized_token !~ '^[0-9a-f]{64}$'
       OR p_expected_recovery_amount IS DISTINCT FROM recovery_amount
       OR recovery_amount <= 0 THEN
        RAISE EXCEPTION 'Exact recovery evidence review token and positive currency-cent amount are required.';
    END IF;
    IF normalized_reference = '' OR length(normalized_note) < 20 THEN
        RAISE EXCEPTION 'Post-write-off recovery review requires retained evidence reference and substantive Management rationale.';
    END IF;

    SELECT * INTO existing
    FROM accounting.ecl_post_writeoff_recovery_review_provenance item
    WHERE item.recovery_transaction_id = p_expected_recovery_transaction_id;
    IF existing.id IS NOT NULL THEN
        IF existing.loan_id <> p_loan_id
           OR existing.recovery_amount <> recovery_amount
           OR existing.evidence_reference <> normalized_reference
           OR existing.review_note <> normalized_note
           OR existing.review_token <> normalized_token
           OR existing.policy_version <> p_policy_version
           OR existing.reviewed_by_user_id <> p_actor_user_id THEN
            RAISE EXCEPTION 'Existing post-write-off recovery evidence review does not match the confirmed immutable retry identity.';
        END IF;
        RETURN existing.credit_risk_review_id;
    END IF;

    PERFORM 1 FROM lending.loans loan WHERE loan.id = p_loan_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Loan was not found.'; END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('ecl-a5:' || p_loan_id::text, 0));

    SELECT * INTO writeoff
    FROM accounting.ecl_accounting_writeoffs item
    WHERE item.loan_id = p_loan_id
    FOR SHARE;
    IF writeoff.id IS NULL THEN
        RAISE EXCEPTION 'A completed protected accounting write-off is required before recovery evidence can be reviewed.';
    END IF;

    SELECT * INTO prior_review
    FROM accounting.ecl_credit_risk_label_reviews review
    WHERE review.loan_id = p_loan_id
    ORDER BY review.review_version DESC
    LIMIT 1
    FOR SHARE;
    IF prior_review.id IS NULL THEN
        RAISE EXCEPTION 'Prior protected credit-risk chronology is required for post-write-off recovery review.';
    END IF;
    IF prior_review.id <> writeoff.credit_risk_review_id
       AND NOT EXISTS (
            SELECT 1
            FROM accounting.ecl_post_writeoff_recovery_review_provenance provenance
            WHERE provenance.credit_risk_review_id = prior_review.id
              AND provenance.writeoff_id = writeoff.id
       ) THEN
        RAISE EXCEPTION 'Latest protected credit-risk review is not part of the exact write-off/recovery chronology.';
    END IF;
    IF prior_review.stage_label <> 'stage_3_credit_impaired'
       OR NOT prior_review.default_label
       OR prior_review.write_off_label <> 'supported_no_reasonable_expectation_of_recovery' THEN
        RAISE EXCEPTION 'Post-write-off recovery chronology must retain the protected Stage 3/default write-off-support baseline.';
    END IF;

    SELECT * INTO tx
    FROM lending.collection_transactions transaction_row
    WHERE transaction_row.id = p_expected_recovery_transaction_id
    FOR SHARE;
    IF tx.id IS NULL
       OR tx.loan_id <> p_loan_id
       OR tx.is_voided
       OR tx.amount <> recovery_amount
       OR tx.amount <= 0
       OR tx.entry_type NOT IN ('payment', 'advance')
       OR tx.accepted_at IS NULL
       OR tx.accepted_at <= writeoff.posted_at THEN
        RAISE EXCEPTION 'Recovery evidence must be the exact later same-loan non-voided positive protected cash transaction after accounting write-off.';
    END IF;
    IF EXISTS (
        SELECT 1 FROM accounting.regular_journal_posting_entries posted
        WHERE posted.transaction_id = tx.id
    ) OR EXISTS (
        SELECT 1 FROM accounting.seven_by_seven_journal_postings posted
        WHERE posted.transaction_id = tx.id
    ) THEN
        RAISE EXCEPTION 'Recovery transaction already has normal source-event accounting and cannot enter the A5 post-write-off recovery path.';
    END IF;

    SELECT * INTO gross FROM accounting.ecl_loan_gross_carrying_components(p_loan_id);
    IF coalesce(gross.gross_carrying_amount, -1) <> 0
       OR accounting.ecl_loan_allowance_balance(p_loan_id) <> 0 THEN
        RAISE EXCEPTION 'Post-write-off recovery evidence requires zero protected gross carrying and zero protected allowance.';
    END IF;

    next_version := prior_review.review_version + 1;
    INSERT INTO accounting.ecl_credit_risk_label_reviews (
        loan_id, review_version, stage_label, default_label, write_off_label,
        recovery_label, primary_evidence_basis, evidence_reference, review_note,
        snapshot_schedule_id, snapshot_schedule_version, snapshot_days_past_due,
        snapshot_due_unpaid_amount, snapshot_thirty_day_backstop,
        snapshot_ninety_day_backstop, snapshot_dpd_risk_band,
        sicr_backstop_rebutted, default_backstop_rebutted,
        rebuttal_evidence_reference, rebuttal_note,
        write_off_evidence_reference, write_off_note,
        recovery_transaction_id, reviewer_user_id, supersedes_review_id
    ) VALUES (
        p_loan_id, next_version, prior_review.stage_label, prior_review.default_label,
        prior_review.write_off_label, 'cash_recovery_observed',
        'protected_collection_history', normalized_reference, normalized_note,
        prior_review.snapshot_schedule_id, prior_review.snapshot_schedule_version,
        prior_review.snapshot_days_past_due, prior_review.snapshot_due_unpaid_amount,
        prior_review.snapshot_thirty_day_backstop, prior_review.snapshot_ninety_day_backstop,
        prior_review.snapshot_dpd_risk_band, prior_review.sicr_backstop_rebutted,
        prior_review.default_backstop_rebutted, prior_review.rebuttal_evidence_reference,
        prior_review.rebuttal_note, prior_review.write_off_evidence_reference,
        prior_review.write_off_note, tx.id, p_actor_user_id, prior_review.id
    ) RETURNING id INTO new_review_id;

    PERFORM set_config('accounting.ecl_a5_audit_insert_allowed', 'on', true);
    INSERT INTO accounting.ecl_post_writeoff_recovery_review_provenance (
        credit_risk_review_id, writeoff_id, loan_id, client_id,
        recovery_transaction_id, recovery_amount, evidence_reference, review_note,
        review_token, policy_version, reviewed_by_user_id
    ) VALUES (
        new_review_id, writeoff.id, p_loan_id, writeoff.client_id,
        tx.id, recovery_amount, normalized_reference, normalized_note,
        normalized_token, p_policy_version, p_actor_user_id
    ) RETURNING id INTO provenance_id;
    PERFORM set_config('accounting.ecl_a5_audit_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES(
        p_actor_user_id,
        'accounting.ecl.postwriteoff_recovery.reviewed',
        'ecl_post_writeoff_recovery_review_provenance',
        provenance_id,
        jsonb_build_object(
            'credit_risk_review_id', new_review_id,
            'loan_id', p_loan_id,
            'writeoff_id', writeoff.id,
            'recovery_transaction_id', tx.id,
            'recovery_amount', recovery_amount,
            'automatic_source_posting', false
        )
    );

    RETURN new_review_id;
END;
$$;

-- Replace the 0079 posting function so it consumes only a review carrying the
-- dedicated immutable post-write-off provenance above. The ordinary ECL label
-- queue is intentionally not required after derecognition because its DPD gate
-- correctly becomes unavailable at zero gross carrying amount.
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
    provenance accounting.ecl_post_writeoff_recovery_review_provenance%ROWTYPE;
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
    IF p_policy_version IS DISTINCT FROM 'ecl_post_writeoff_recovery_posting_v1' THEN
        RAISE EXCEPTION 'Unsupported post-write-off recovery policy version.';
    END IF;
    IF normalized_token !~ '^[0-9a-f]{64}$'
       OR p_expected_recovery_amount IS DISTINCT FROM recovery_amount
       OR recovery_amount <= 0 THEN
        RAISE EXCEPTION 'Exact recovery review token and positive currency-cent amount are required.';
    END IF;

    SELECT * INTO existing
    FROM accounting.ecl_post_writeoff_recoveries item
    WHERE item.recovery_transaction_id = p_expected_recovery_transaction_id;
    IF existing.id IS NOT NULL THEN
        IF existing.credit_risk_review_id <> p_credit_risk_review_id
           OR existing.review_token <> normalized_token
           OR existing.recovery_amount <> recovery_amount
           OR existing.posting_date <> p_expected_posting_date
           OR existing.fiscal_period_id <> p_expected_fiscal_period_id
           OR existing.cash_account_id <> p_expected_cash_account_id
           OR existing.credit_loss_expense_account_id <> p_expected_credit_loss_expense_account_id
           OR existing.policy_version <> p_policy_version THEN
            RAISE EXCEPTION 'Existing post-write-off recovery does not match the confirmed immutable retry identity.';
        END IF;
        RETURN existing.id;
    END IF;

    SELECT * INTO review
    FROM accounting.ecl_credit_risk_label_reviews item
    WHERE item.id = p_credit_risk_review_id
    FOR SHARE;
    IF review.id IS NULL
       OR review.recovery_label <> 'cash_recovery_observed'
       OR review.recovery_transaction_id IS DISTINCT FROM p_expected_recovery_transaction_id THEN
        RAISE EXCEPTION 'Post-write-off recovery requires the exact protected cash-recovery-observed review and transaction.';
    END IF;

    SELECT * INTO provenance
    FROM accounting.ecl_post_writeoff_recovery_review_provenance item
    WHERE item.credit_risk_review_id = review.id
      AND item.recovery_transaction_id = p_expected_recovery_transaction_id
    FOR SHARE;
    IF provenance.id IS NULL
       OR provenance.loan_id <> review.loan_id
       OR provenance.recovery_amount <> recovery_amount
       OR provenance.policy_version <> 'ecl_post_writeoff_recovery_evidence_review_v1' THEN
        RAISE EXCEPTION 'Recovery review lacks exact immutable post-write-off evidence provenance.';
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended('ecl-a5:' || review.loan_id::text, 0));
    IF EXISTS (
        SELECT 1
        FROM accounting.ecl_credit_risk_label_reviews later
        WHERE later.loan_id = review.loan_id
          AND later.review_version > review.review_version
    ) THEN
        RAISE EXCEPTION 'Post-write-off recovery review is no longer the latest protected recovery evidence.';
    END IF;

    SELECT * INTO writeoff
    FROM accounting.ecl_accounting_writeoffs item
    WHERE item.id = provenance.writeoff_id
      AND item.loan_id = review.loan_id
    FOR SHARE;
    IF writeoff.id IS NULL THEN
        RAISE EXCEPTION 'A completed protected accounting write-off is required before post-write-off recovery.';
    END IF;

    SELECT * INTO tx
    FROM lending.collection_transactions transaction_row
    WHERE transaction_row.id = p_expected_recovery_transaction_id
    FOR SHARE;
    IF tx.id IS NULL
       OR tx.loan_id <> review.loan_id
       OR tx.is_voided
       OR tx.amount <> recovery_amount
       OR tx.amount <= 0
       OR tx.entry_type NOT IN ('payment', 'advance')
       OR tx.accepted_at IS NULL
       OR tx.accepted_at <= writeoff.posted_at
       OR p_expected_posting_date IS DISTINCT FROM tx.collection_date THEN
        RAISE EXCEPTION 'Recovery must be the exact later same-loan non-voided protected positive cash transaction after accounting write-off.';
    END IF;
    IF EXISTS (
        SELECT 1 FROM accounting.regular_journal_posting_entries posted
        WHERE posted.transaction_id = tx.id
    ) OR EXISTS (
        SELECT 1 FROM accounting.seven_by_seven_journal_postings posted
        WHERE posted.transaction_id = tx.id
    ) THEN
        RAISE EXCEPTION 'Recovery transaction already has normal source-event accounting and cannot also use the A5 post-write-off recovery path.';
    END IF;

    SELECT * INTO gross FROM accounting.ecl_loan_gross_carrying_components(review.loan_id);
    IF coalesce(gross.gross_carrying_amount, -1) <> 0
       OR accounting.ecl_loan_allowance_balance(review.loan_id) <> 0 THEN
        RAISE EXCEPTION 'Post-write-off recovery requires zero protected gross carrying and zero protected allowance.';
    END IF;

    SELECT * INTO period_row
    FROM accounting.fiscal_periods period
    WHERE period.id = p_expected_fiscal_period_id
    FOR SHARE;
    IF period_row.id IS NULL
       OR period_row.status <> 'open'
       OR p_expected_posting_date NOT BETWEEN period_row.start_date AND period_row.end_date THEN
        RAISE EXCEPTION 'Recovery requires the exact open fiscal period containing the protected collection date.';
    END IF;

    SELECT * INTO cash_account
    FROM accounting.accounts account
    WHERE account.id = p_expected_cash_account_id
    FOR SHARE;
    IF cash_account.id IS NULL
       OR cash_account.system_key <> 'cash_collector_custody'
       OR cash_account.code <> '1020'
       OR cash_account.account_type <> 'asset'
       OR cash_account.normal_balance <> 'debit'
       OR NOT cash_account.is_active
       OR NOT cash_account.is_posting THEN
        RAISE EXCEPTION 'Exact active posting account 1020 Cash - Collector Custody is required.';
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
       OR NOT expense_account.is_active
       OR NOT expense_account.is_posting THEN
        RAISE EXCEPTION 'Exact active posting account 5000 Credit Loss Expense is required.';
    END IF;

    digest_value := encode(sha256(convert_to(concat_ws('|',
        p_policy_version, provenance.id::text, writeoff.id::text, review.id::text,
        tx.id::text, review.loan_id::text,
        to_char(recovery_amount, 'FM999999999999990.00'),
        p_expected_posting_date::text, period_row.id::text,
        cash_account.id::text, expense_account.id::text, normalized_token
    ), 'UTF8')), 'hex');

    PERFORM set_config('accounting.ecl_a5_journal_prepare_allowed', 'on', true);
    INSERT INTO accounting.journal_entries(
        fiscal_period_id, posting_date, description, source_type,
        source_reference, source_event_key, created_by_user_id
    ) VALUES(
        period_row.id, p_expected_posting_date,
        'Post-write-off cash recovery - loan ' || review.loan_id::text,
        'ecl_post_writeoff_recovery', tx.id::text,
        'ecl_recovery:' || tx.id::text, p_actor_user_id
    ) RETURNING id INTO journal_id;
    PERFORM set_config('accounting.ecl_a5_journal_prepare_allowed', 'off', true);

    PERFORM set_config('accounting.ecl_a5_journal_line_write_allowed', 'on', true);
    INSERT INTO accounting.journal_lines(
        journal_entry_id, line_number, account_id, description,
        debit, credit, client_id, loan_id
    ) VALUES
        (journal_id, 1, cash_account.id,
         'Exact protected post-write-off cash recovery',
         recovery_amount, 0, writeoff.client_id, review.loan_id),
        (journal_id, 2, expense_account.id,
         'Post-write-off recovery recognized in credit-loss profit or loss',
         0, recovery_amount, writeoff.client_id, review.loan_id);
    PERFORM set_config('accounting.ecl_a5_journal_line_write_allowed', 'off', true);

    PERFORM set_config('accounting.ecl_a5_journal_post_allowed', 'on', true);
    entry_number_value := accounting.post_journal_entry(journal_id, p_actor_user_id);
    PERFORM set_config('accounting.ecl_a5_journal_post_allowed', 'off', true);
    IF coalesce(current_setting('accounting.ecl_a5_force_audit_failure', true), '') = 'on' THEN
        RAISE EXCEPTION 'Forced A5 audit failure.';
    END IF;

    PERFORM set_config('accounting.ecl_a5_audit_insert_allowed', 'on', true);
    INSERT INTO accounting.ecl_post_writeoff_recoveries(
        writeoff_id, loan_id, client_id, credit_risk_review_id,
        recovery_transaction_id, recovery_amount, cash_account_id,
        credit_loss_expense_account_id, journal_entry_id, source_event_key,
        posting_date, fiscal_period_id, review_token, posting_digest,
        policy_version, entry_number, posted_by_user_id
    ) VALUES(
        writeoff.id, review.loan_id, writeoff.client_id, review.id, tx.id,
        recovery_amount, cash_account.id, expense_account.id, journal_id,
        'ecl_recovery:' || tx.id::text, p_expected_posting_date, period_row.id,
        normalized_token, digest_value, p_policy_version,
        entry_number_value, p_actor_user_id
    ) RETURNING id INTO result_id;
    PERFORM set_config('accounting.ecl_a5_audit_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES(
        p_actor_user_id,
        'accounting.ecl.post_writeoff_recovery.posted',
        'ecl_post_writeoff_recovery',
        result_id,
        jsonb_build_object(
            'writeoff_id', writeoff.id,
            'loan_id', review.loan_id,
            'credit_risk_review_id', review.id,
            'recovery_review_provenance_id', provenance.id,
            'recovery_transaction_id', tx.id,
            'recovery_amount', recovery_amount,
            'journal_entry_id', journal_id,
            'entry_number', entry_number_value,
            'automatic_source_posting', false
        )
    );
    RETURN result_id;
END;
$$;

-- Keep the same public A5 queue columns while sourcing post-write-off recovery
-- readiness from the dedicated evidence provenance instead of a DPD-ready queue.
CREATE OR REPLACE VIEW accounting.ecl_a5_action_queue AS
SELECT
    loan.id AS loan_id,
    loan.loan_number,
    loan.status AS loan_status,
    loan_type.calculation_mode,
    CASE
        WHEN writeoff.id IS NOT NULL AND recovery_review.credit_risk_review_id IS NOT NULL
            THEN recovery_review.credit_risk_review_id
        ELSE label.review_id
    END AS credit_risk_review_id,
    CASE
        WHEN writeoff.id IS NOT NULL AND recovery_label_review.id IS NOT NULL
            THEN recovery_label_review.stage_label
        ELSE label.stage_label
    END AS stage_label,
    CASE
        WHEN writeoff.id IS NOT NULL AND recovery_label_review.id IS NOT NULL
            THEN recovery_label_review.default_label
        ELSE label.default_label
    END AS default_label,
    CASE
        WHEN writeoff.id IS NOT NULL AND recovery_label_review.id IS NOT NULL
            THEN recovery_label_review.write_off_label
        ELSE label.write_off_label
    END AS write_off_label,
    CASE
        WHEN writeoff.id IS NOT NULL AND recovery_label_review.id IS NOT NULL
            THEN recovery_label_review.recovery_label
        ELSE label.recovery_label
    END AS recovery_label,
    coalesce(writeoff.measurement_id, measurement.measurement_id) AS measurement_id,
    coalesce(writeoff.measurement_version, measurement.measurement_version) AS measurement_version,
    coalesce(writeoff_measurement.measurement_date, measurement.measurement_date) AS measurement_date,
    coalesce(writeoff.calculation_digest, measurement.calculation_digest) AS calculation_digest,
    CASE
        WHEN writeoff_measurement.id IS NOT NULL THEN 'measured_read_only'::text
        ELSE measurement.measurement_status
    END AS measurement_status,
    coalesce(writeoff_measurement.ecl_amount, measurement.authoritative_ecl_amount)::numeric(18,2)
        AS authoritative_ecl_amount,
    accounting.ecl_loan_allowance_balance(loan.id)::numeric(18,2)
        AS current_allowance_balance,
    gross.loan_receivable_account_id,
    gross.loan_receivable_system_key,
    gross.accrued_interest_account_id,
    gross.loan_component,
    gross.accrued_interest_component,
    gross.gross_carrying_amount,
    writeoff.id AS writeoff_id,
    recovery_review.recovery_transaction_id,
    recovery_review.recovery_amount,
    CASE
        WHEN writeoff.id IS NOT NULL
             AND gross.gross_carrying_amount = 0
             AND accounting.ecl_loan_allowance_balance(loan.id) = 0
             AND recovery_review.credit_risk_review_id IS NOT NULL
             AND recovery_label_review.recovery_label = 'cash_recovery_observed'
             AND NOT EXISTS (
                 SELECT 1
                 FROM accounting.ecl_post_writeoff_recoveries posted_recovery
                 WHERE posted_recovery.recovery_transaction_id = recovery_review.recovery_transaction_id
             )
            THEN 'post_writeoff_recovery_ready'
        WHEN writeoff.id IS NOT NULL
             AND gross.gross_carrying_amount = 0
             AND accounting.ecl_loan_allowance_balance(loan.id) = 0
            THEN 'written_off'
        WHEN label.current_label_ready
             AND label.write_off_label = 'supported_no_reasonable_expectation_of_recovery'
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
LEFT JOIN accounting.ecl_quantitative_measurements writeoff_measurement
  ON writeoff_measurement.id = writeoff.measurement_id
LEFT JOIN LATERAL (
    SELECT provenance.*
    FROM accounting.ecl_post_writeoff_recovery_review_provenance provenance
    WHERE provenance.loan_id = loan.id
    ORDER BY provenance.reviewed_at DESC, provenance.id DESC
    LIMIT 1
) recovery_review ON true
LEFT JOIN accounting.ecl_credit_risk_label_reviews recovery_label_review
  ON recovery_label_review.id = recovery_review.credit_risk_review_id
WHERE loan.status = 'active';

COMMENT ON TABLE accounting.ecl_post_writeoff_recovery_review_provenance IS
'Immutable A5 Management evidence provenance for exact same-loan protected cash observed after completed accounting write-off. It bypasses no accounting control and does not represent cure.';
COMMENT ON FUNCTION accounting.review_ecl_post_writeoff_recovery(UUID,UUID,TEXT,UUID,NUMERIC,TEXT,TEXT,TEXT) IS
'Explicit Management review of exact protected post-write-off cash. Uses the immutable write-off/risk chronology because derecognized loans correctly no longer satisfy ordinary contractual-DPD readiness; automatic_source_posting remains false.';
COMMENT ON FUNCTION accounting.post_ecl_post_writeoff_recovery(BIGINT,UUID,TEXT,UUID,NUMERIC,DATE,UUID,UUID,UUID,TEXT) IS
'A5 explicit Management post-write-off cash recovery from exact dedicated protected recovery provenance. Posts Dr 1020 / Cr 5000, recreates no receivable or allowance, requires exact retry identity and automatic_source_posting=false.';
COMMENT ON VIEW accounting.ecl_a5_action_queue IS
'A5 protected action queue. Post-write-off recovery readiness comes only from dedicated immutable same-loan cash evidence after derecognition; automatic_source_posting=false.';

COMMIT;