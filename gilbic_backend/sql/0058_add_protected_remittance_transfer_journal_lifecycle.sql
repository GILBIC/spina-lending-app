BEGIN;

INSERT INTO core.permissions (code, description)
VALUES
    (
        'accounting.remittance_transfer.journal.prepare',
        'Create a protected draft journal for an exact reviewed remittance custody-transfer coordinate without posting it'
    ),
    (
        'accounting.remittance_transfer.journal.post',
        'Explicitly post one integrity-ready protected remittance custody-transfer draft after exact Management confirmation'
    ),
    (
        'accounting.remittance_transfer.journal.reverse',
        'Explicitly reverse one already-posted protected remittance custody-transfer journal while preserving immutable original history'
    )
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code IN (
      'accounting.remittance_transfer.journal.prepare',
      'accounting.remittance_transfer.journal.post',
      'accounting.remittance_transfer.journal.reverse'
  )
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.remittance_transfer_journal_preparations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    remittance_id UUID NOT NULL UNIQUE
        REFERENCES lending.collection_remittances(id) ON DELETE RESTRICT,
    transfer_evidence_id UUID NOT NULL UNIQUE
        REFERENCES accounting.remittance_transfer_evidence(id) ON DELETE RESTRICT,
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
    CHECK (source_event_key = 'remittance_transfer:' || remittance_id::text),
    CHECK (review_token ~ '^[0-9a-f]{64}$'),
    CHECK (coordinate_policy_version = 'remittance_transfer_coordinates_v1'),
    CHECK (draft_policy_version = 'remittance_transfer_journal_draft_v1'),
    CHECK (debit_account_id <> credit_account_id)
);

CREATE TABLE IF NOT EXISTS accounting.remittance_transfer_journal_postings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    preparation_id UUID NOT NULL UNIQUE
        REFERENCES accounting.remittance_transfer_journal_preparations(id) ON DELETE RESTRICT,
    remittance_id UUID NOT NULL UNIQUE
        REFERENCES lending.collection_remittances(id) ON DELETE RESTRICT,
    transfer_evidence_id UUID NOT NULL UNIQUE
        REFERENCES accounting.remittance_transfer_evidence(id) ON DELETE RESTRICT,
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    source_event_key TEXT NOT NULL UNIQUE,
    draft_review_token TEXT NOT NULL,
    posting_review_token TEXT NOT NULL,
    draft_policy_version TEXT NOT NULL,
    posting_policy_version TEXT NOT NULL,
    posting_date DATE NOT NULL,
    fiscal_period_id UUID NOT NULL
        REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    debit_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    credit_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    amount NUMERIC(18,2) NOT NULL CHECK (amount > 0),
    entry_number TEXT NOT NULL UNIQUE,
    posted_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    posted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (source_event_key = 'remittance_transfer:' || remittance_id::text),
    CHECK (draft_review_token ~ '^[0-9a-f]{64}$'),
    CHECK (posting_review_token ~ '^[0-9a-f]{64}$'),
    CHECK (draft_policy_version = 'remittance_transfer_journal_draft_v1'),
    CHECK (posting_policy_version = 'remittance_transfer_journal_posting_v1'),
    CHECK (debit_account_id <> credit_account_id),
    CHECK (btrim(entry_number) <> '')
);

CREATE TABLE IF NOT EXISTS accounting.remittance_transfer_journal_reversals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    posting_id UUID NOT NULL UNIQUE
        REFERENCES accounting.remittance_transfer_journal_postings(id) ON DELETE RESTRICT,
    remittance_id UUID NOT NULL UNIQUE
        REFERENCES lending.collection_remittances(id) ON DELETE RESTRICT,
    original_journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    reversal_journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    original_entry_number TEXT NOT NULL,
    reversal_entry_number TEXT NOT NULL UNIQUE,
    original_source_event_key TEXT NOT NULL,
    reversal_source_event_key TEXT NOT NULL UNIQUE,
    original_debit_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    original_credit_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    amount NUMERIC(18,2) NOT NULL CHECK (amount > 0),
    reversal_posting_date DATE NOT NULL,
    reason TEXT NOT NULL CHECK (length(btrim(reason)) >= 3),
    reversed_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    reversed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (btrim(original_entry_number) <> ''),
    CHECK (btrim(reversal_entry_number) <> ''),
    CHECK (original_source_event_key = 'remittance_transfer:' || remittance_id::text),
    CHECK (reversal_source_event_key = 'remittance_transfer_reversal:' || posting_id::text),
    CHECK (original_debit_account_id <> original_credit_account_id)
);

CREATE OR REPLACE FUNCTION accounting.guard_remittance_transfer_journal_preparation_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(current_setting('accounting.remittance_transfer_prepare_allowed', true), '') = 'on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Protected remittance-transfer journal preparations are immutable and must use the protected preparation workflow.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_remittance_transfer_preparation_guard
    ON accounting.remittance_transfer_journal_preparations;
CREATE TRIGGER accounting_remittance_transfer_preparation_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.remittance_transfer_journal_preparations
FOR EACH ROW EXECUTE FUNCTION accounting.guard_remittance_transfer_journal_preparation_write();

CREATE OR REPLACE FUNCTION accounting.guard_remittance_transfer_journal_posting_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(current_setting('accounting.remittance_transfer_post_record_allowed', true), '') = 'on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Protected remittance-transfer posting audit is immutable and must use the protected posting workflow.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_remittance_transfer_posting_guard
    ON accounting.remittance_transfer_journal_postings;
CREATE TRIGGER accounting_remittance_transfer_posting_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.remittance_transfer_journal_postings
FOR EACH ROW EXECUTE FUNCTION accounting.guard_remittance_transfer_journal_posting_write();

CREATE OR REPLACE FUNCTION accounting.guard_remittance_transfer_journal_reversal_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(current_setting('accounting.remittance_transfer_reversal_allowed', true), '') = 'on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Protected remittance-transfer reversal audit is immutable and must use the controlled reversal workflow.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_remittance_transfer_reversal_guard
    ON accounting.remittance_transfer_journal_reversals;
CREATE TRIGGER accounting_remittance_transfer_reversal_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.remittance_transfer_journal_reversals
FOR EACH ROW EXECUTE FUNCTION accounting.guard_remittance_transfer_journal_reversal_write();

CREATE OR REPLACE FUNCTION accounting.guard_remittance_transfer_system_journal_entry_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    protected_entry BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM accounting.remittance_transfer_journal_preparations prepared
        WHERE prepared.journal_entry_id = OLD.id
    ) INTO protected_entry;

    IF NOT protected_entry THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Protected remittance-transfer journal drafts cannot be deleted through the General Journal.';
    END IF;

    IF OLD.status = 'draft' AND NEW.status = 'posted' THEN
        IF coalesce(current_setting('accounting.remittance_transfer_post_allowed', true), '') <> 'on' THEN
            RAISE EXCEPTION 'Protected remittance-transfer journal drafts require the explicit protected posting workflow.';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'Protected remittance-transfer journal drafts are system generated and cannot be edited.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_remittance_transfer_system_journal_entry_guard
    ON accounting.journal_entries;
CREATE TRIGGER accounting_remittance_transfer_system_journal_entry_guard
BEFORE UPDATE OR DELETE ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_remittance_transfer_system_journal_entry_change();

CREATE OR REPLACE FUNCTION accounting.guard_remittance_transfer_system_journal_line_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_entry_id UUID;
    protected_entry BOOLEAN;
BEGIN
    target_entry_id := CASE WHEN TG_OP = 'DELETE' THEN OLD.journal_entry_id ELSE NEW.journal_entry_id END;
    SELECT EXISTS (
        SELECT 1
        FROM accounting.remittance_transfer_journal_preparations prepared
        WHERE prepared.journal_entry_id = target_entry_id
    ) INTO protected_entry;

    IF protected_entry
       AND coalesce(current_setting('accounting.remittance_transfer_prepare_allowed', true), '') <> 'on' THEN
        RAISE EXCEPTION 'Protected remittance-transfer journal lines are system generated and immutable.';
    END IF;

    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_remittance_transfer_system_journal_line_guard
    ON accounting.journal_lines;
CREATE TRIGGER accounting_remittance_transfer_system_journal_line_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_lines
FOR EACH ROW EXECUTE FUNCTION accounting.guard_remittance_transfer_system_journal_line_change();

CREATE OR REPLACE FUNCTION accounting.guard_protected_remittance_transfer_reversal_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    original_is_protected BOOLEAN := false;
    protected_session BOOLEAN := false;
BEGIN
    protected_session := coalesce(
        current_setting('accounting.remittance_transfer_reversal_allowed', true),
        ''
    ) = 'on';

    IF NEW.reversal_of_entry_id IS NOT NULL THEN
        SELECT EXISTS (
            SELECT 1
            FROM accounting.remittance_transfer_journal_postings posted
            WHERE posted.journal_entry_id = NEW.reversal_of_entry_id
        ) INTO original_is_protected;
    END IF;

    IF NEW.source_type = 'remittance_transfer_reversal' THEN
        IF NOT protected_session OR NEW.reversal_of_entry_id IS NULL THEN
            RAISE EXCEPTION 'Protected remittance-transfer reversal journals must use the controlled reversal workflow.';
        END IF;
    ELSIF original_is_protected THEN
        RAISE EXCEPTION 'Posted protected remittance-transfer journals can only be reversed through the controlled reversal workflow.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_protected_remittance_transfer_reversal_insert_guard
    ON accounting.journal_entries;
CREATE TRIGGER accounting_protected_remittance_transfer_reversal_insert_guard
BEFORE INSERT ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_protected_remittance_transfer_reversal_insert();

CREATE OR REPLACE FUNCTION accounting.create_remittance_transfer_journal_draft(
    p_remittance_id UUID,
    p_actor_user_id UUID,
    p_review_token TEXT,
    p_expected_transfer_evidence_id UUID,
    p_expected_source_event_key TEXT,
    p_expected_posting_date DATE,
    p_expected_debit_account_system_key TEXT,
    p_expected_credit_account_system_key TEXT,
    p_expected_amount NUMERIC,
    p_coordinate_policy_version TEXT,
    p_draft_policy_version TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    readiness RECORD;
    existing accounting.remittance_transfer_journal_preparations%ROWTYPE;
    period_id UUID;
    debit_account accounting.accounts%ROWTYPE;
    credit_account accounting.accounts%ROWTYPE;
    journal_id UUID;
    preparation_id UUID;
    token TEXT := lower(btrim(coalesce(p_review_token, '')));
    source_key TEXT := btrim(coalesce(p_expected_source_event_key, ''));
    amount NUMERIC(18,2) := round(coalesce(p_expected_amount, 0), 2);
    line_count INTEGER;
    total_debit NUMERIC(18,2);
    total_credit NUMERIC(18,2);
BEGIN
    IF p_coordinate_policy_version IS DISTINCT FROM 'remittance_transfer_coordinates_v1' THEN
        RAISE EXCEPTION 'Unsupported remittance-transfer coordinate policy version.';
    END IF;
    IF p_draft_policy_version IS DISTINCT FROM 'remittance_transfer_journal_draft_v1' THEN
        RAISE EXCEPTION 'Unsupported remittance-transfer draft policy version.';
    END IF;
    IF token !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Protected remittance-transfer review token is invalid.';
    END IF;
    IF source_key <> 'remittance_transfer:' || p_remittance_id::text THEN
        RAISE EXCEPTION 'Protected remittance-transfer source identity is invalid.';
    END IF;
    IF amount <= 0 OR p_expected_amount IS DISTINCT FROM amount THEN
        RAISE EXCEPTION 'Protected remittance-transfer confirmed amount must be a positive two-decimal amount.';
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended('remittance-transfer-draft:' || p_remittance_id::text, 0));

    LOCK TABLE
        lending.collection_remittances,
        accounting.remittance_transfer_evidence,
        accounting.fiscal_periods,
        accounting.accounts,
        accounting.journal_entries,
        accounting.journal_lines,
        accounting.remittance_transfer_journal_preparations,
        accounting.remittance_transfer_journal_postings
    IN SHARE MODE;

    SELECT * INTO existing
    FROM accounting.remittance_transfer_journal_preparations prepared
    WHERE prepared.remittance_id = p_remittance_id;

    IF existing.id IS NOT NULL THEN
        IF existing.transfer_evidence_id <> p_expected_transfer_evidence_id
           OR existing.source_event_key <> source_key
           OR existing.review_token <> token
           OR existing.coordinate_policy_version <> p_coordinate_policy_version
           OR existing.draft_policy_version <> p_draft_policy_version
           OR existing.posting_date <> p_expected_posting_date
           OR existing.amount <> amount THEN
            RAISE EXCEPTION 'Existing protected remittance-transfer draft does not match the reviewed confirmation.';
        END IF;

        SELECT count(*)::integer,
               coalesce(sum(debit), 0)::numeric(18,2),
               coalesce(sum(credit), 0)::numeric(18,2)
        INTO line_count, total_debit, total_credit
        FROM accounting.journal_lines
        WHERE journal_entry_id = existing.journal_entry_id;

        IF line_count <> 2 OR total_debit <> existing.amount OR total_credit <> existing.amount THEN
            RAISE EXCEPTION 'Existing protected remittance-transfer draft failed immutable line integrity review.';
        END IF;
        RETURN existing.id;
    END IF;

    SELECT * INTO readiness
    FROM accounting.remittance_transfer_readiness item
    WHERE item.remittance_id = p_remittance_id;

    IF readiness.remittance_id IS NULL THEN
        RAISE EXCEPTION 'Remittance transfer was not found.';
    END IF;
    IF readiness.readiness_status <> 'transfer_coordinate_ready' THEN
        RAISE EXCEPTION 'Remittance-transfer coordinate is not ready: %', readiness.readiness_status;
    END IF;
    IF readiness.transfer_evidence_id <> p_expected_transfer_evidence_id
       OR readiness.source_event_key <> source_key
       OR readiness.business_date <> p_expected_posting_date
       OR readiness.debit_account_system_key <> p_expected_debit_account_system_key
       OR readiness.credit_account_system_key <> p_expected_credit_account_system_key
       OR readiness.debit_amount <> amount
       OR readiness.credit_amount <> amount
       OR readiness.income_recognition IS DISTINCT FROM false
       OR readiness.journal_lines_enabled IS DISTINCT FROM false
       OR readiness.automatic_source_posting IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'Remittance-transfer coordinates changed after Management review. Refresh before preparing the draft.';
    END IF;
    IF p_expected_debit_account_system_key NOT IN ('cash_office', 'cash_bank_gcash')
       OR p_expected_credit_account_system_key <> 'cash_collector_custody' THEN
        RAISE EXCEPTION 'Protected remittance-transfer coordinates must be Dr Office/Bank-GCash and Cr Collector Custody.';
    END IF;

    SELECT id INTO period_id
    FROM accounting.fiscal_periods
    WHERE status = 'open'
      AND p_expected_posting_date BETWEEN start_date AND end_date
    ORDER BY start_date DESC
    LIMIT 1;
    IF period_id IS NULL THEN
        RAISE EXCEPTION 'No open accounting period contains the remittance-transfer posting date.';
    END IF;

    SELECT * INTO debit_account
    FROM accounting.accounts
    WHERE system_key = p_expected_debit_account_system_key;
    SELECT * INTO credit_account
    FROM accounting.accounts
    WHERE system_key = p_expected_credit_account_system_key;

    IF debit_account.id IS NULL
       OR debit_account.account_type <> 'asset'
       OR debit_account.is_active IS DISTINCT FROM true
       OR debit_account.is_posting IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'Protected remittance-transfer debit account is unavailable.';
    END IF;
    IF credit_account.id IS NULL
       OR credit_account.system_key <> 'cash_collector_custody'
       OR credit_account.account_type <> 'asset'
       OR credit_account.is_active IS DISTINCT FROM true
       OR credit_account.is_posting IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'Protected remittance-transfer credit account is unavailable.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM accounting.journal_entries journal
        WHERE journal.source_event_key = source_key
    ) THEN
        RAISE EXCEPTION 'Accounting journal history already exists for this remittance-transfer source event.';
    END IF;

    PERFORM set_config('accounting.remittance_transfer_prepare_allowed', 'on', true);
    INSERT INTO accounting.journal_entries (
        fiscal_period_id,
        posting_date,
        description,
        status,
        source_type,
        source_reference,
        source_event_key,
        created_by_user_id
    ) VALUES (
        period_id,
        p_expected_posting_date,
        'Remittance custody transfer - ' || readiness.remittance_number,
        'draft',
        'remittance_transfer',
        p_remittance_id::text,
        source_key,
        p_actor_user_id
    ) RETURNING id INTO journal_id;

    INSERT INTO accounting.journal_lines (
        journal_entry_id, line_number, account_id, description, debit, credit
    ) VALUES
        (
            journal_id, 1, debit_account.id,
            'Remittance destination - ' || coalesce(readiness.external_reference, readiness.remittance_number),
            amount, 0
        ),
        (
            journal_id, 2, credit_account.id,
            'Release collector cash custody - ' || readiness.remittance_number,
            0, amount
        );

    INSERT INTO accounting.remittance_transfer_journal_preparations (
        remittance_id,
        transfer_evidence_id,
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
    ) VALUES (
        p_remittance_id,
        p_expected_transfer_evidence_id,
        journal_id,
        source_key,
        token,
        p_coordinate_policy_version,
        p_draft_policy_version,
        p_expected_posting_date,
        period_id,
        debit_account.id,
        credit_account.id,
        amount,
        p_actor_user_id
    ) RETURNING id INTO preparation_id;
    PERFORM set_config('accounting.remittance_transfer_prepare_allowed', 'off', true);

    INSERT INTO core.audit_logs (actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.remittance_transfer_journal_draft.prepared',
        'remittance_transfer_journal_preparation',
        preparation_id,
        jsonb_build_object(
            'remittance_id', p_remittance_id::text,
            'transfer_evidence_id', p_expected_transfer_evidence_id::text,
            'journal_entry_id', journal_id::text,
            'source_event_key', source_key,
            'amount', amount,
            'debit_account_system_key', debit_account.system_key,
            'credit_account_system_key', credit_account.system_key,
            'income_recognition', false,
            'automatic_source_posting', false
        )
    );

    RETURN preparation_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.post_remittance_transfer_journal(
    p_preparation_id UUID,
    p_actor_user_id UUID,
    p_posting_review_token TEXT,
    p_expected_journal_entry_id UUID,
    p_expected_source_event_key TEXT,
    p_expected_draft_review_token TEXT,
    p_expected_amount NUMERIC,
    p_posting_policy_version TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    prepared accounting.remittance_transfer_journal_preparations%ROWTYPE;
    existing accounting.remittance_transfer_journal_postings%ROWTYPE;
    evidence accounting.remittance_transfer_evidence%ROWTYPE;
    readiness RECORD;
    journal accounting.journal_entries%ROWTYPE;
    period accounting.fiscal_periods%ROWTYPE;
    debit_account accounting.accounts%ROWTYPE;
    credit_account accounting.accounts%ROWTYPE;
    posting_token TEXT := lower(btrim(coalesce(p_posting_review_token, '')));
    draft_token TEXT := lower(btrim(coalesce(p_expected_draft_review_token, '')));
    source_key TEXT := btrim(coalesce(p_expected_source_event_key, ''));
    amount NUMERIC(18,2) := round(coalesce(p_expected_amount, 0), 2);
    line_count INTEGER;
    total_debit NUMERIC(18,2);
    total_credit NUMERIC(18,2);
    debit_match INTEGER;
    credit_match INTEGER;
    entry_number TEXT;
    posting_id UUID;
BEGIN
    IF p_posting_policy_version IS DISTINCT FROM 'remittance_transfer_journal_posting_v1' THEN
        RAISE EXCEPTION 'Unsupported remittance-transfer posting policy version.';
    END IF;
    IF posting_token !~ '^[0-9a-f]{64}$' OR draft_token !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Protected remittance-transfer posting review identity is invalid.';
    END IF;
    IF amount <= 0 OR p_expected_amount IS DISTINCT FROM amount THEN
        RAISE EXCEPTION 'Protected remittance-transfer posting amount must be a positive two-decimal amount.';
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended('remittance-transfer-post:' || p_preparation_id::text, 0));

    LOCK TABLE
        lending.collection_remittances,
        accounting.remittance_transfer_evidence,
        accounting.fiscal_periods,
        accounting.accounts,
        accounting.journal_entries,
        accounting.journal_lines,
        accounting.remittance_transfer_journal_preparations,
        accounting.remittance_transfer_journal_postings
    IN SHARE MODE;

    SELECT * INTO prepared
    FROM accounting.remittance_transfer_journal_preparations item
    WHERE item.id = p_preparation_id;
    IF prepared.id IS NULL THEN
        RAISE EXCEPTION 'Protected remittance-transfer journal preparation was not found.';
    END IF;

    IF prepared.journal_entry_id <> p_expected_journal_entry_id
       OR prepared.source_event_key <> source_key
       OR prepared.review_token <> draft_token
       OR prepared.amount <> amount THEN
        RAISE EXCEPTION 'Protected remittance-transfer posting confirmation changed from the immutable draft preparation.';
    END IF;

    SELECT * INTO existing
    FROM accounting.remittance_transfer_journal_postings item
    WHERE item.preparation_id = prepared.id;
    IF existing.id IS NOT NULL THEN
        IF existing.journal_entry_id <> prepared.journal_entry_id
           OR existing.source_event_key <> prepared.source_event_key
           OR existing.draft_review_token <> prepared.review_token
           OR existing.posting_review_token <> posting_token
           OR existing.amount <> prepared.amount
           OR existing.posting_policy_version <> p_posting_policy_version THEN
            RAISE EXCEPTION 'Existing protected remittance-transfer posting audit does not match this exact retry.';
        END IF;
        RETURN existing.id;
    END IF;

    SELECT * INTO evidence
    FROM accounting.remittance_transfer_evidence item
    WHERE item.id = prepared.transfer_evidence_id;
    SELECT * INTO readiness
    FROM accounting.remittance_transfer_readiness item
    WHERE item.remittance_id = prepared.remittance_id;
    SELECT * INTO journal
    FROM accounting.journal_entries item
    WHERE item.id = prepared.journal_entry_id;
    SELECT * INTO period
    FROM accounting.fiscal_periods item
    WHERE item.id = prepared.fiscal_period_id;
    SELECT * INTO debit_account
    FROM accounting.accounts item
    WHERE item.id = prepared.debit_account_id;
    SELECT * INTO credit_account
    FROM accounting.accounts item
    WHERE item.id = prepared.credit_account_id;

    IF evidence.id IS NULL OR evidence.is_voided
       OR readiness.readiness_status <> 'transfer_coordinate_ready'
       OR readiness.transfer_evidence_id <> prepared.transfer_evidence_id
       OR readiness.source_event_key <> prepared.source_event_key
       OR readiness.business_date <> prepared.posting_date
       OR readiness.debit_account_system_key <> debit_account.system_key
       OR readiness.credit_account_system_key <> credit_account.system_key
       OR readiness.debit_amount <> prepared.amount
       OR readiness.credit_amount <> prepared.amount THEN
        RAISE EXCEPTION 'Authoritative remittance-transfer evidence or coordinates changed before protected posting.';
    END IF;

    IF period.id IS NULL OR period.status <> 'open'
       OR prepared.posting_date NOT BETWEEN period.start_date AND period.end_date THEN
        RAISE EXCEPTION 'Protected remittance-transfer journal can only post into its still-open containing fiscal period.';
    END IF;
    IF debit_account.system_key NOT IN ('cash_office', 'cash_bank_gcash')
       OR debit_account.account_type <> 'asset'
       OR debit_account.is_active IS DISTINCT FROM true
       OR debit_account.is_posting IS DISTINCT FROM true
       OR credit_account.system_key <> 'cash_collector_custody'
       OR credit_account.account_type <> 'asset'
       OR credit_account.is_active IS DISTINCT FROM true
       OR credit_account.is_posting IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'Protected remittance-transfer accounts are no longer valid active cash posting accounts.';
    END IF;

    IF journal.id IS NULL OR journal.status <> 'draft'
       OR journal.entry_number IS NOT NULL
       OR journal.source_type <> 'remittance_transfer'
       OR journal.source_reference <> prepared.remittance_id::text
       OR journal.source_event_key <> prepared.source_event_key
       OR journal.posting_date <> prepared.posting_date
       OR journal.fiscal_period_id <> prepared.fiscal_period_id THEN
        RAISE EXCEPTION 'Protected remittance-transfer journal draft identity changed or was posted without the protected workflow.';
    END IF;

    SELECT count(*)::integer,
           coalesce(sum(line.debit), 0)::numeric(18,2),
           coalesce(sum(line.credit), 0)::numeric(18,2),
           count(*) FILTER (
               WHERE line.account_id = prepared.debit_account_id
                 AND line.debit = prepared.amount AND line.credit = 0
           )::integer,
           count(*) FILTER (
               WHERE line.account_id = prepared.credit_account_id
                 AND line.credit = prepared.amount AND line.debit = 0
           )::integer
    INTO line_count, total_debit, total_credit, debit_match, credit_match
    FROM accounting.journal_lines line
    WHERE line.journal_entry_id = prepared.journal_entry_id;

    IF line_count <> 2 OR total_debit <> prepared.amount OR total_credit <> prepared.amount
       OR total_debit <> total_credit OR debit_match <> 1 OR credit_match <> 1 THEN
        RAISE EXCEPTION 'Protected remittance-transfer journal lines no longer match the exact Dr destination cash / Cr Collector Custody pattern.';
    END IF;

    PERFORM set_config('accounting.remittance_transfer_post_allowed', 'on', true);
    SELECT accounting.post_journal_entry(prepared.journal_entry_id, p_actor_user_id)
    INTO entry_number;
    PERFORM set_config('accounting.remittance_transfer_post_allowed', 'off', true);

    PERFORM set_config('accounting.remittance_transfer_post_record_allowed', 'on', true);
    INSERT INTO accounting.remittance_transfer_journal_postings (
        preparation_id, remittance_id, transfer_evidence_id, journal_entry_id,
        source_event_key, draft_review_token, posting_review_token,
        draft_policy_version, posting_policy_version, posting_date,
        fiscal_period_id, debit_account_id, credit_account_id, amount,
        entry_number, posted_by_user_id
    ) VALUES (
        prepared.id, prepared.remittance_id, prepared.transfer_evidence_id,
        prepared.journal_entry_id, prepared.source_event_key, prepared.review_token,
        posting_token, prepared.draft_policy_version, p_posting_policy_version,
        prepared.posting_date, prepared.fiscal_period_id, prepared.debit_account_id,
        prepared.credit_account_id, prepared.amount, entry_number, p_actor_user_id
    ) RETURNING id INTO posting_id;
    PERFORM set_config('accounting.remittance_transfer_post_record_allowed', 'off', true);

    INSERT INTO core.audit_logs (actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.remittance_transfer_journal.posted',
        'remittance_transfer_journal_posting',
        posting_id,
        jsonb_build_object(
            'preparation_id', prepared.id::text,
            'remittance_id', prepared.remittance_id::text,
            'journal_entry_id', prepared.journal_entry_id::text,
            'entry_number', entry_number,
            'source_event_key', prepared.source_event_key,
            'amount', prepared.amount,
            'income_recognition', false,
            'automatic_source_posting', false
        )
    );

    RETURN posting_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.reverse_posted_remittance_transfer(
    p_posting_id UUID,
    p_actor_user_id UUID,
    p_reversal_posting_date DATE,
    p_reason TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    posting accounting.remittance_transfer_journal_postings%ROWTYPE;
    prepared accounting.remittance_transfer_journal_preparations%ROWTYPE;
    existing accounting.remittance_transfer_journal_reversals%ROWTYPE;
    original_journal accounting.journal_entries%ROWTYPE;
    target_period_id UUID;
    reversal_id UUID;
    reversal_journal_id UUID;
    reversal_number TEXT;
    reversal_source_key TEXT;
    reason TEXT := btrim(coalesce(p_reason, ''));
BEGIN
    IF p_reversal_posting_date IS NULL THEN
        RAISE EXCEPTION 'A remittance-transfer reversal posting date is required.';
    END IF;
    IF length(reason) < 3 THEN
        RAISE EXCEPTION 'A remittance-transfer reversal requires a clear reason.';
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended('remittance-transfer-reverse:' || p_posting_id::text, 0));

    LOCK TABLE
        accounting.fiscal_periods,
        accounting.accounts,
        accounting.journal_entries,
        accounting.journal_lines,
        accounting.remittance_transfer_journal_preparations,
        accounting.remittance_transfer_journal_postings,
        accounting.remittance_transfer_journal_reversals
    IN SHARE MODE;

    SELECT * INTO posting
    FROM accounting.remittance_transfer_journal_postings item
    WHERE item.id = p_posting_id;
    IF posting.id IS NULL THEN
        RAISE EXCEPTION 'Protected remittance-transfer posting audit was not found.';
    END IF;

    SELECT * INTO existing
    FROM accounting.remittance_transfer_journal_reversals item
    WHERE item.posting_id = p_posting_id;
    IF existing.id IS NOT NULL THEN
        IF existing.reversal_posting_date <> p_reversal_posting_date
           OR existing.reason <> reason
           OR existing.reversed_by_user_id <> p_actor_user_id
           OR existing.amount <> posting.amount
           OR existing.original_journal_entry_id <> posting.journal_entry_id THEN
            RAISE EXCEPTION 'Existing protected remittance-transfer reversal does not match this exact retry.';
        END IF;
        RETURN existing.id;
    END IF;

    SELECT * INTO prepared
    FROM accounting.remittance_transfer_journal_preparations item
    WHERE item.id = posting.preparation_id;
    SELECT * INTO original_journal
    FROM accounting.journal_entries item
    WHERE item.id = posting.journal_entry_id;

    IF prepared.id IS NULL
       OR prepared.remittance_id <> posting.remittance_id
       OR prepared.journal_entry_id <> posting.journal_entry_id
       OR prepared.source_event_key <> posting.source_event_key
       OR prepared.amount <> posting.amount
       OR original_journal.id IS NULL
       OR original_journal.status <> 'posted'
       OR original_journal.entry_number <> posting.entry_number
       OR original_journal.source_type <> 'remittance_transfer'
       OR original_journal.source_event_key <> posting.source_event_key
       OR original_journal.reversal_of_entry_id IS NOT NULL THEN
        RAISE EXCEPTION 'Original protected remittance-transfer posting history failed immutable integrity review.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM accounting.journal_entries journal
        WHERE journal.reversal_of_entry_id = posting.journal_entry_id
    ) THEN
        RAISE EXCEPTION 'This protected remittance-transfer journal already has reversal history.';
    END IF;

    SELECT id INTO target_period_id
    FROM accounting.fiscal_periods
    WHERE status = 'open'
      AND p_reversal_posting_date BETWEEN start_date AND end_date
    ORDER BY start_date DESC
    LIMIT 1;
    IF target_period_id IS NULL THEN
        RAISE EXCEPTION 'No open accounting period contains the remittance-transfer reversal date.';
    END IF;

    reversal_source_key := 'remittance_transfer_reversal:' || posting.id::text;
    PERFORM set_config('accounting.remittance_transfer_reversal_allowed', 'on', true);

    INSERT INTO accounting.journal_entries (
        fiscal_period_id, posting_date, description, status,
        source_type, source_reference, source_event_key,
        reversal_of_entry_id, created_by_user_id
    ) VALUES (
        target_period_id,
        p_reversal_posting_date,
        'Reverse remittance custody transfer - ' || posting.entry_number || ' - ' || reason,
        'draft',
        'remittance_transfer_reversal',
        posting.id::text,
        reversal_source_key,
        posting.journal_entry_id,
        p_actor_user_id
    ) RETURNING id INTO reversal_journal_id;

    INSERT INTO accounting.journal_lines (
        journal_entry_id, line_number, account_id, description, debit, credit
    ) VALUES
        (
            reversal_journal_id, 1, posting.credit_account_id,
            'Reverse collector custody release', posting.amount, 0
        ),
        (
            reversal_journal_id, 2, posting.debit_account_id,
            'Reverse remittance destination transfer', 0, posting.amount
        );

    SELECT accounting.post_journal_entry(reversal_journal_id, p_actor_user_id)
    INTO reversal_number;

    INSERT INTO accounting.remittance_transfer_journal_reversals (
        posting_id, remittance_id, original_journal_entry_id,
        reversal_journal_entry_id, original_entry_number, reversal_entry_number,
        original_source_event_key, reversal_source_event_key,
        original_debit_account_id, original_credit_account_id,
        amount, reversal_posting_date, reason, reversed_by_user_id
    ) VALUES (
        posting.id, posting.remittance_id, posting.journal_entry_id,
        reversal_journal_id, posting.entry_number, reversal_number,
        posting.source_event_key, reversal_source_key,
        posting.debit_account_id, posting.credit_account_id,
        posting.amount, p_reversal_posting_date, reason, p_actor_user_id
    ) RETURNING id INTO reversal_id;

    PERFORM set_config('accounting.remittance_transfer_reversal_allowed', 'off', true);

    INSERT INTO core.audit_logs (actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.remittance_transfer_journal.reversed',
        'remittance_transfer_journal_reversal',
        reversal_id,
        jsonb_build_object(
            'posting_id', posting.id::text,
            'remittance_id', posting.remittance_id::text,
            'original_journal_entry_id', posting.journal_entry_id::text,
            'reversal_journal_entry_id', reversal_journal_id::text,
            'original_entry_number', posting.entry_number,
            'reversal_entry_number', reversal_number,
            'amount', posting.amount,
            'reason', reason,
            'income_recognition', false,
            'automatic_source_posting', false
        )
    );

    RETURN reversal_id;
END;
$$;

CREATE OR REPLACE VIEW accounting.remittance_transfer_journal_status AS
WITH line_summary AS (
    SELECT
        prepared.id AS preparation_id,
        count(line.id)::integer AS line_count,
        coalesce(sum(line.debit), 0)::numeric(18,2) AS total_debit,
        coalesce(sum(line.credit), 0)::numeric(18,2) AS total_credit,
        count(line.id) FILTER (
            WHERE line.account_id = prepared.debit_account_id
              AND line.debit = prepared.amount AND line.credit = 0
        )::integer AS debit_match_count,
        count(line.id) FILTER (
            WHERE line.account_id = prepared.credit_account_id
              AND line.credit = prepared.amount AND line.debit = 0
        )::integer AS credit_match_count
    FROM accounting.remittance_transfer_journal_preparations prepared
    LEFT JOIN accounting.journal_lines line
      ON line.journal_entry_id = prepared.journal_entry_id
    GROUP BY prepared.id
),
reversal_line_summary AS (
    SELECT
        reversal.id AS reversal_id,
        count(line.id)::integer AS line_count,
        coalesce(sum(line.debit), 0)::numeric(18,2) AS total_debit,
        coalesce(sum(line.credit), 0)::numeric(18,2) AS total_credit,
        count(line.id) FILTER (
            WHERE line.account_id = reversal.original_credit_account_id
              AND line.debit = reversal.amount AND line.credit = 0
        )::integer AS debit_match_count,
        count(line.id) FILTER (
            WHERE line.account_id = reversal.original_debit_account_id
              AND line.credit = reversal.amount AND line.debit = 0
        )::integer AS credit_match_count
    FROM accounting.remittance_transfer_journal_reversals reversal
    LEFT JOIN accounting.journal_lines line
      ON line.journal_entry_id = reversal.reversal_journal_entry_id
    GROUP BY reversal.id
)
SELECT
    prepared.id AS preparation_id,
    prepared.remittance_id,
    prepared.transfer_evidence_id,
    prepared.journal_entry_id,
    prepared.source_event_key,
    prepared.review_token AS draft_review_token,
    prepared.posting_date,
    prepared.fiscal_period_id,
    prepared.debit_account_id,
    debit_account.system_key AS debit_account_system_key,
    prepared.credit_account_id,
    credit_account.system_key AS credit_account_system_key,
    prepared.amount,
    journal.status AS journal_status,
    journal.entry_number,
    posting.id AS posting_id,
    posting.posting_review_token,
    posting.posted_by_user_id,
    posting.posted_at,
    reversal.id AS reversal_id,
    reversal.reversal_journal_entry_id,
    reversal.reversal_entry_number,
    reversal.reversal_posting_date,
    reversal.reason AS reversal_reason,
    CASE
        WHEN posting.id IS NULL
         AND journal.status = 'draft'
         AND line_summary.line_count = 2
         AND line_summary.total_debit = prepared.amount
         AND line_summary.total_credit = prepared.amount
         AND line_summary.debit_match_count = 1
         AND line_summary.credit_match_count = 1
         AND period.status = 'open'
            THEN true
        ELSE false
    END AS posting_ready,
    CASE
        WHEN posting.id IS NOT NULL
         AND journal.status = 'posted'
         AND journal.entry_number = posting.entry_number
         AND posting.journal_entry_id = prepared.journal_entry_id
         AND posting.source_event_key = prepared.source_event_key
         AND posting.amount = prepared.amount
         AND line_summary.line_count = 2
         AND line_summary.total_debit = prepared.amount
         AND line_summary.total_credit = prepared.amount
         AND line_summary.debit_match_count = 1
         AND line_summary.credit_match_count = 1
            THEN true
        ELSE false
    END AS posted_audit_exact,
    CASE
        WHEN reversal.id IS NULL THEN false
        WHEN reversal_journal.status = 'posted'
         AND reversal_journal.entry_number = reversal.reversal_entry_number
         AND reversal_journal.reversal_of_entry_id = posting.journal_entry_id
         AND reversal_line_summary.line_count = 2
         AND reversal_line_summary.total_debit = reversal.amount
         AND reversal_line_summary.total_credit = reversal.amount
         AND reversal_line_summary.debit_match_count = 1
         AND reversal_line_summary.credit_match_count = 1
            THEN true
        ELSE false
    END AS reversal_audit_exact,
    CASE
        WHEN reversal.id IS NOT NULL THEN 'reversed'
        WHEN posting.id IS NOT NULL THEN 'posted'
        ELSE 'draft'
    END AS lifecycle_status,
    false AS income_recognition,
    true AS explicit_management_posting,
    false AS automatic_source_posting
FROM accounting.remittance_transfer_journal_preparations prepared
JOIN accounting.journal_entries journal
  ON journal.id = prepared.journal_entry_id
JOIN accounting.fiscal_periods period
  ON period.id = prepared.fiscal_period_id
JOIN accounting.accounts debit_account
  ON debit_account.id = prepared.debit_account_id
JOIN accounting.accounts credit_account
  ON credit_account.id = prepared.credit_account_id
JOIN line_summary
  ON line_summary.preparation_id = prepared.id
LEFT JOIN accounting.remittance_transfer_journal_postings posting
  ON posting.preparation_id = prepared.id
LEFT JOIN accounting.remittance_transfer_journal_reversals reversal
  ON reversal.posting_id = posting.id
LEFT JOIN accounting.journal_entries reversal_journal
  ON reversal_journal.id = reversal.reversal_journal_entry_id
LEFT JOIN reversal_line_summary
  ON reversal_line_summary.reversal_id = reversal.id;

COMMENT ON TABLE accounting.remittance_transfer_journal_preparations IS
    'Immutable Management-reviewed protected remittance custody-transfer draft preparations.';
COMMENT ON TABLE accounting.remittance_transfer_journal_postings IS
    'Immutable explicit Management posting audit for protected remittance custody transfers.';
COMMENT ON TABLE accounting.remittance_transfer_journal_reversals IS
    'Immutable controlled reversal audit for a posted protected remittance custody transfer.';
COMMENT ON VIEW accounting.remittance_transfer_journal_status IS
    'Protected remittance journal lifecycle reconciliation. Transfers remain asset-to-asset, explicit Management posting only, with automatic source posting disabled.';

COMMIT;