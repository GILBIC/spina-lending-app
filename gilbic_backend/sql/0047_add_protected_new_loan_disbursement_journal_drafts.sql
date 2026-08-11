BEGIN;

INSERT INTO core.permissions (code, description)
VALUES (
    'accounting.loan_disbursement.journal.prepare',
    'Create a protected draft journal for an exact reviewed pure new Regular loan disbursement coordinate without posting it'
)
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code = 'accounting.loan_disbursement.journal.prepare'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.loan_disbursement_journal_draft_preparations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    disbursement_event_id UUID NOT NULL UNIQUE
        REFERENCES lending.loan_disbursement_events(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL
        REFERENCES lending.loans(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL
        REFERENCES lending.clients(id) ON DELETE RESTRICT,
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    source_event_key TEXT NOT NULL UNIQUE,
    review_token TEXT NOT NULL,
    coordinate_policy_version TEXT NOT NULL,
    draft_policy_version TEXT NOT NULL,
    posting_date DATE NOT NULL,
    fiscal_period_id UUID NOT NULL
        REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    debit_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    credit_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    amount NUMERIC(18,2) NOT NULL CHECK (amount > 0),
    prepared_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    prepared_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (source_event_key = 'loan_disbursement:' || disbursement_event_id::text),
    CHECK (review_token ~ '^[0-9a-f]{64}$'),
    CHECK (coordinate_policy_version = 'new_loan_disbursement_coordinates_v1'),
    CHECK (draft_policy_version = 'new_loan_disbursement_journal_draft_v1'),
    CHECK (debit_account_id <> credit_account_id)
);

CREATE INDEX IF NOT EXISTS loan_disbursement_journal_draft_preparations_loan_idx
    ON accounting.loan_disbursement_journal_draft_preparations
       (loan_id, prepared_at DESC);

CREATE OR REPLACE FUNCTION accounting.guard_loan_disbursement_journal_draft_preparation_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(
            current_setting('accounting.loan_disbursement_journal_prepare_allowed', true),
            ''
       ) = 'on' THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'Protected new-loan disbursement journal preparation records are immutable and must use the protected preparation function.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_loan_disbursement_journal_draft_preparation_guard
    ON accounting.loan_disbursement_journal_draft_preparations;
CREATE TRIGGER accounting_loan_disbursement_journal_draft_preparation_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.loan_disbursement_journal_draft_preparations
FOR EACH ROW EXECUTE FUNCTION accounting.guard_loan_disbursement_journal_draft_preparation_write();

CREATE OR REPLACE FUNCTION accounting.guard_loan_disbursement_system_journal_entry_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    protected_entry BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM accounting.loan_disbursement_journal_draft_preparations prepared
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
        RAISE EXCEPTION 'Protected new-loan disbursement journal drafts cannot be deleted through the General Journal.';
    END IF;

    IF OLD.status = 'draft' AND NEW.status = 'posted' THEN
        IF coalesce(
            current_setting('accounting.loan_disbursement_journal_post_allowed', true),
            ''
        ) <> 'on' THEN
            RAISE EXCEPTION 'Protected new-loan disbursement journal drafts require the future protected disbursement posting workflow.';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'Protected new-loan disbursement journal drafts are system generated and cannot be edited.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_loan_disbursement_system_journal_entry_guard
    ON accounting.journal_entries;
CREATE TRIGGER accounting_loan_disbursement_system_journal_entry_guard
BEFORE UPDATE OR DELETE ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_loan_disbursement_system_journal_entry_change();

CREATE OR REPLACE FUNCTION accounting.guard_loan_disbursement_system_journal_line_change()
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
        FROM accounting.loan_disbursement_journal_draft_preparations prepared
        WHERE prepared.journal_entry_id = target_entry_id
    )
    INTO protected_entry;

    IF protected_entry
       AND coalesce(
            current_setting('accounting.loan_disbursement_journal_prepare_allowed', true),
            ''
       ) <> 'on' THEN
        RAISE EXCEPTION 'Protected new-loan disbursement journal lines are system generated and immutable.';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_loan_disbursement_system_journal_line_guard
    ON accounting.journal_lines;
CREATE TRIGGER accounting_loan_disbursement_system_journal_line_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_lines
FOR EACH ROW EXECUTE FUNCTION accounting.guard_loan_disbursement_system_journal_line_change();

CREATE OR REPLACE FUNCTION accounting.create_new_loan_disbursement_journal_draft(
    p_disbursement_event_id UUID,
    p_actor_user_id UUID,
    p_review_token TEXT,
    p_expected_source_event_key TEXT,
    p_expected_posting_date DATE,
    p_expected_fiscal_period_id UUID,
    p_expected_debit_account_id UUID,
    p_expected_credit_account_id UUID,
    p_expected_amount NUMERIC,
    p_coordinate_policy_version TEXT,
    p_draft_policy_version TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    coordinate_row RECORD;
    existing_preparation accounting.loan_disbursement_journal_draft_preparations%ROWTYPE;
    journal_id UUID;
    preparation_id UUID;
    normalized_review_token TEXT := lower(btrim(coalesce(p_review_token, '')));
    normalized_source_key TEXT := btrim(coalesce(p_expected_source_event_key, ''));
    expected_amount NUMERIC(18,2) := round(coalesce(p_expected_amount, 0), 2);
    existing_line_count INTEGER;
    existing_debit NUMERIC(18,2);
    existing_credit NUMERIC(18,2);
    existing_debit_match INTEGER;
    existing_credit_match INTEGER;
BEGIN
    IF p_coordinate_policy_version IS DISTINCT FROM 'new_loan_disbursement_coordinates_v1' THEN
        RAISE EXCEPTION 'Unsupported new-loan disbursement coordinate policy version.';
    END IF;
    IF p_draft_policy_version IS DISTINCT FROM 'new_loan_disbursement_journal_draft_v1' THEN
        RAISE EXCEPTION 'Unsupported new-loan disbursement journal draft policy version.';
    END IF;
    IF normalized_review_token !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Protected new-loan disbursement review token is invalid.';
    END IF;
    IF normalized_source_key <> 'loan_disbursement:' || p_disbursement_event_id::text THEN
        RAISE EXCEPTION 'Protected new-loan disbursement source identity is invalid.';
    END IF;
    IF expected_amount <= 0 OR p_expected_amount IS DISTINCT FROM expected_amount THEN
        RAISE EXCEPTION 'Protected new-loan disbursement confirmed amount must be a positive two-decimal amount.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended(
            'new-loan-disbursement-journal-draft:' || p_disbursement_event_id::text,
            0
        )
    );

    -- Freeze every mutable source consumed by the Stage 5D.19 evidence and
    -- Stage 5D.20 coordinate views before the final exact replay.
    LOCK TABLE
        lending.loan_disbursement_events,
        lending.loans,
        lending.loan_types,
        accounting.fiscal_periods,
        accounting.accounts,
        accounting.journal_entries,
        accounting.journal_lines,
        accounting.loan_disbursement_journal_draft_preparations
    IN SHARE MODE;

    SELECT *
    INTO existing_preparation
    FROM accounting.loan_disbursement_journal_draft_preparations prepared
    WHERE prepared.disbursement_event_id = p_disbursement_event_id;

    IF existing_preparation.id IS NOT NULL THEN
        IF existing_preparation.source_event_key <> normalized_source_key
           OR existing_preparation.review_token <> normalized_review_token
           OR existing_preparation.coordinate_policy_version <> p_coordinate_policy_version
           OR existing_preparation.draft_policy_version <> p_draft_policy_version
           OR existing_preparation.posting_date <> p_expected_posting_date
           OR existing_preparation.fiscal_period_id <> p_expected_fiscal_period_id
           OR existing_preparation.debit_account_id <> p_expected_debit_account_id
           OR existing_preparation.credit_account_id <> p_expected_credit_account_id
           OR existing_preparation.amount <> expected_amount THEN
            RAISE EXCEPTION 'Existing protected new-loan disbursement draft does not match the reviewed confirmation.';
        END IF;

        SELECT
            count(*)::integer,
            coalesce(sum(line.debit), 0)::numeric(18,2),
            coalesce(sum(line.credit), 0)::numeric(18,2),
            count(*) FILTER (
                WHERE line.account_id = existing_preparation.debit_account_id
                  AND line.debit = existing_preparation.amount
                  AND line.credit = 0
            )::integer,
            count(*) FILTER (
                WHERE line.account_id = existing_preparation.credit_account_id
                  AND line.credit = existing_preparation.amount
                  AND line.debit = 0
            )::integer
        INTO
            existing_line_count,
            existing_debit,
            existing_credit,
            existing_debit_match,
            existing_credit_match
        FROM accounting.journal_lines line
        WHERE line.journal_entry_id = existing_preparation.journal_entry_id;

        IF NOT EXISTS (
            SELECT 1
            FROM accounting.journal_entries journal
            WHERE journal.id = existing_preparation.journal_entry_id
              AND journal.status = 'draft'
              AND journal.entry_number IS NULL
              AND journal.source_type = 'loan_disbursement'
              AND journal.source_reference = p_disbursement_event_id::text
              AND journal.source_event_key = normalized_source_key
              AND journal.posting_date = existing_preparation.posting_date
              AND journal.fiscal_period_id = existing_preparation.fiscal_period_id
        )
        OR existing_line_count <> 2
        OR existing_debit <> existing_preparation.amount
        OR existing_credit <> existing_preparation.amount
        OR existing_debit_match <> 1
        OR existing_credit_match <> 1 THEN
            RAISE EXCEPTION 'Existing protected new-loan disbursement journal draft failed immutable integrity review.';
        END IF;

        RETURN existing_preparation.id;
    END IF;

    SELECT *
    INTO coordinate_row
    FROM accounting.loan_disbursement_journal_coordinates coordinate
    WHERE coordinate.disbursement_event_id = p_disbursement_event_id;

    IF coordinate_row.disbursement_event_id IS NULL THEN
        RAISE EXCEPTION 'Authoritative loan-disbursement evidence was not found for protected draft preparation.';
    END IF;
    IF coordinate_row.coordinate_status <> 'coordinate_ready' THEN
        RAISE EXCEPTION 'New-loan disbursement coordinate is not ready: %', coordinate_row.coordinate_status;
    END IF;
    IF coordinate_row.event_kind <> 'new_loan_release'
       OR coordinate_row.calculation_mode <> 'fixed_daily'
       OR coordinate_row.evidence_readiness_status <> 'source_evidence_ready'
       OR coordinate_row.initial_measurement_basis <> 'transaction_price_plain_cash_v1' THEN
        RAISE EXCEPTION 'Protected draft preparation supports only the approved pure new Regular release coordinate.';
    END IF;
    IF coordinate_row.source_event_key <> normalized_source_key
       OR coordinate_row.posting_date <> p_expected_posting_date
       OR coordinate_row.fiscal_period_id <> p_expected_fiscal_period_id
       OR coordinate_row.debit_account_id <> p_expected_debit_account_id
       OR coordinate_row.credit_account_id <> p_expected_credit_account_id
       OR coordinate_row.debit_amount <> expected_amount
       OR coordinate_row.credit_amount <> expected_amount
       OR coordinate_row.debit_account_system_key <> 'loans_receivable_regular'
       OR coordinate_row.credit_account_system_key NOT IN (
            'cash_office',
            'cash_collector_custody',
            'cash_bank_gcash'
       ) THEN
        RAISE EXCEPTION 'New-loan disbursement coordinates changed after Management review. Refresh before preparing the draft.';
    END IF;
    IF coordinate_row.journal_draft_enabled IS DISTINCT FROM false
       OR coordinate_row.automatic_source_posting IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'Stage 5D.20 coordinate safety flags are inconsistent.';
    END IF;

    -- Defense in depth against a race or unaudited source-key reservation.
    IF EXISTS (
        SELECT 1
        FROM accounting.journal_entries journal
        WHERE journal.source_event_key = normalized_source_key
    ) THEN
        RAISE EXCEPTION 'Accounting journal history already exists for this loan-disbursement source event.';
    END IF;

    PERFORM set_config(
        'accounting.loan_disbursement_journal_prepare_allowed',
        'on',
        true
    );

    INSERT INTO accounting.journal_entries (
        fiscal_period_id,
        posting_date,
        description,
        status,
        source_type,
        source_reference,
        source_event_key,
        created_by_user_id
    )
    VALUES (
        coordinate_row.fiscal_period_id,
        coordinate_row.posting_date,
        'New Regular loan disbursement - ' || coordinate_row.loan_number,
        'draft',
        'loan_disbursement',
        p_disbursement_event_id::text,
        coordinate_row.source_event_key,
        p_actor_user_id
    )
    RETURNING id INTO journal_id;

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
    VALUES
        (
            journal_id,
            1,
            coordinate_row.debit_account_id,
            'Initial recognition - new Regular loan',
            expected_amount,
            0,
            coordinate_row.client_id,
            coordinate_row.loan_id
        ),
        (
            journal_id,
            2,
            coordinate_row.credit_account_id,
            'Cash funding - ' || coordinate_row.external_reference,
            0,
            expected_amount,
            coordinate_row.client_id,
            coordinate_row.loan_id
        );

    INSERT INTO accounting.loan_disbursement_journal_draft_preparations (
        disbursement_event_id,
        loan_id,
        client_id,
        journal_entry_id,
        source_event_key,
        review_token,
        coordinate_policy_version,
        draft_policy_version,
        posting_date,
        fiscal_period_id,
        debit_account_id,
        credit_account_id,
        amount,
        prepared_by_user_id
    )
    VALUES (
        p_disbursement_event_id,
        coordinate_row.loan_id,
        coordinate_row.client_id,
        journal_id,
        coordinate_row.source_event_key,
        normalized_review_token,
        p_coordinate_policy_version,
        p_draft_policy_version,
        coordinate_row.posting_date,
        coordinate_row.fiscal_period_id,
        coordinate_row.debit_account_id,
        coordinate_row.credit_account_id,
        expected_amount,
        p_actor_user_id
    )
    RETURNING id INTO preparation_id;

    PERFORM set_config(
        'accounting.loan_disbursement_journal_prepare_allowed',
        'off',
        true
    );

    INSERT INTO core.audit_logs (
        actor_user_id,
        action,
        target_type,
        target_id,
        details
    )
    VALUES (
        p_actor_user_id,
        'accounting.loan_disbursement_journal_draft.prepared',
        'loan_disbursement_journal_draft_preparation',
        preparation_id,
        jsonb_build_object(
            'disbursement_event_id', p_disbursement_event_id::text,
            'loan_id', coordinate_row.loan_id::text,
            'journal_entry_id', journal_id::text,
            'source_event_key', coordinate_row.source_event_key,
            'posting_date', coordinate_row.posting_date,
            'amount', expected_amount,
            'debit_account_system_key', coordinate_row.debit_account_system_key,
            'credit_account_system_key', coordinate_row.credit_account_system_key,
            'review_token', normalized_review_token,
            'posting_enabled', false,
            'automatic_source_posting', false
        )
    );

    RETURN preparation_id;
END;
$$;

CREATE OR REPLACE VIEW accounting.loan_disbursement_journal_draft_status AS
WITH line_summary AS (
    SELECT
        prepared.id AS preparation_id,
        count(line.id)::integer AS line_count,
        coalesce(sum(line.debit), 0)::numeric(18,2) AS total_debit,
        coalesce(sum(line.credit), 0)::numeric(18,2) AS total_credit,
        count(line.id) FILTER (
            WHERE line.account_id = prepared.debit_account_id
              AND line.debit = prepared.amount
              AND line.credit = 0
        )::integer AS debit_line_match_count,
        count(line.id) FILTER (
            WHERE line.account_id = prepared.credit_account_id
              AND line.credit = prepared.amount
              AND line.debit = 0
        )::integer AS credit_line_match_count
    FROM accounting.loan_disbursement_journal_draft_preparations prepared
    LEFT JOIN accounting.journal_lines line
      ON line.journal_entry_id = prepared.journal_entry_id
    GROUP BY prepared.id
)
SELECT
    prepared.id AS preparation_id,
    prepared.disbursement_event_id,
    prepared.loan_id,
    prepared.client_id,
    prepared.journal_entry_id,
    prepared.source_event_key,
    prepared.review_token,
    prepared.coordinate_policy_version,
    prepared.draft_policy_version,
    prepared.posting_date,
    prepared.fiscal_period_id,
    period.label AS fiscal_period_label,
    period.status AS fiscal_period_status,
    prepared.amount,
    prepared.debit_account_id,
    debit_account.system_key AS debit_account_system_key,
    prepared.credit_account_id,
    credit_account.system_key AS credit_account_system_key,
    journal.status AS journal_status,
    journal.entry_number,
    prepared.prepared_by_user_id,
    prepared.prepared_at,
    line_summary.line_count,
    line_summary.total_debit,
    line_summary.total_credit,
    CASE
        WHEN journal.status <> 'draft' THEN false
        WHEN journal.entry_number IS NOT NULL THEN false
        WHEN journal.source_type <> 'loan_disbursement' THEN false
        WHEN journal.source_reference <> prepared.disbursement_event_id::text THEN false
        WHEN journal.source_event_key <> prepared.source_event_key THEN false
        WHEN journal.posting_date <> prepared.posting_date THEN false
        WHEN journal.fiscal_period_id <> prepared.fiscal_period_id THEN false
        WHEN period.status <> 'open' THEN false
        WHEN debit_account.system_key <> 'loans_receivable_regular'
          OR debit_account.is_active IS DISTINCT FROM true
          OR debit_account.is_posting IS DISTINCT FROM true THEN false
        WHEN credit_account.system_key NOT IN (
            'cash_office', 'cash_collector_custody', 'cash_bank_gcash'
        )
          OR credit_account.account_type <> 'asset'
          OR credit_account.is_active IS DISTINCT FROM true
          OR credit_account.is_posting IS DISTINCT FROM true THEN false
        WHEN line_summary.line_count <> 2 THEN false
        WHEN line_summary.total_debit <> prepared.amount
          OR line_summary.total_credit <> prepared.amount THEN false
        WHEN line_summary.debit_line_match_count <> 1
          OR line_summary.credit_line_match_count <> 1 THEN false
        ELSE true
    END AS draft_integrity_ready,
    false AS posting_enabled,
    false AS automatic_source_posting
FROM accounting.loan_disbursement_journal_draft_preparations prepared
JOIN accounting.journal_entries journal
  ON journal.id = prepared.journal_entry_id
JOIN accounting.fiscal_periods period
  ON period.id = prepared.fiscal_period_id
JOIN accounting.accounts debit_account
  ON debit_account.id = prepared.debit_account_id
JOIN accounting.accounts credit_account
  ON credit_account.id = prepared.credit_account_id
JOIN line_summary
  ON line_summary.preparation_id = prepared.id;

COMMENT ON TABLE accounting.loan_disbursement_journal_draft_preparations IS
    'Immutable Stage 5D.21 preparation audit for a protected Management-confirmed pure new Regular loan-disbursement draft. One authoritative source event may create at most one protected draft.';
COMMENT ON VIEW accounting.loan_disbursement_journal_draft_status IS
    'Read-only Stage 5D.21 draft integrity status. Stage 5D.21 does not enable posting or automatic source posting.';

COMMIT;
