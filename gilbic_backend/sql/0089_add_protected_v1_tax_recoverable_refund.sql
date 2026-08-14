BEGIN;

-- Master #296 A6.2 Tax Recoverable realization, cash-refund sub-slice.
-- A posted settled-tax decrease may create 1130 Tax Recoverable under 0086. This
-- migration allows that exact recoverable to be cleared only after separate immutable
-- Management evidence proves an actual cash/bank refund. The amount is derived from
-- the protected adjustment posting; callers cannot invent or partially realize it.
-- Tax-credit application, closed-period correction policy and automatic source posting
-- remain separate fail-closed controls.

INSERT INTO core.permissions (code, description)
VALUES
    ('accounting.tax.recoverable_refund_evidence.record', 'Record immutable Management-approved refund receipt evidence for one exact posted V1 Tax Recoverable'),
    ('accounting.tax.recoverable_refund.prepare', 'Prepare a protected V1 Tax Recoverable cash-refund General Journal draft from exact refund evidence'),
    ('accounting.tax.recoverable_refund.post', 'Post a protected V1 Tax Recoverable cash-refund General Journal after exact Management confirmation')
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code IN (
      'accounting.tax.recoverable_refund_evidence.record',
      'accounting.tax.recoverable_refund.prepare',
      'accounting.tax.recoverable_refund.post'
  )
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.v1_tax_recoverable_refund_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key UUID NOT NULL UNIQUE,
    adjustment_posting_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_adjustment_postings(id) ON DELETE RESTRICT,
    adjustment_evidence_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_adjustment_evidence(id) ON DELETE RESTRICT,
    tax_type TEXT NOT NULL CHECK (
        tax_type IN ('documentary_stamp_tax', 'percentage_tax_lending')
    ),
    refund_amount NUMERIC(18,2) NOT NULL CHECK (refund_amount > 0),
    refund_date DATE NOT NULL,
    cash_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    refund_reference TEXT NOT NULL CHECK (btrim(refund_reference) <> ''),
    authority_reference TEXT NOT NULL CHECK (btrim(authority_reference) <> ''),
    evidence_digest TEXT NOT NULL CHECK (evidence_digest ~ '^[0-9a-f]{64}$'),
    evidence_note TEXT NOT NULL CHECK (length(btrim(evidence_note)) >= 20),
    recorded_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS v1_tax_recoverable_refund_date_idx
    ON accounting.v1_tax_recoverable_refund_evidence(refund_date DESC, recorded_at DESC);

CREATE TABLE IF NOT EXISTS accounting.v1_tax_recoverable_refund_preparations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    refund_evidence_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_recoverable_refund_evidence(id) ON DELETE RESTRICT,
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    source_event_key TEXT NOT NULL UNIQUE CHECK (btrim(source_event_key) <> ''),
    posting_date DATE NOT NULL,
    refund_amount NUMERIC(18,2) NOT NULL CHECK (refund_amount > 0),
    cash_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    tax_recoverable_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    fiscal_period_id UUID NOT NULL REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    prepared_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    prepared_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS accounting.v1_tax_recoverable_refund_postings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    preparation_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_recoverable_refund_preparations(id) ON DELETE RESTRICT,
    refund_evidence_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_recoverable_refund_evidence(id) ON DELETE RESTRICT,
    adjustment_posting_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_adjustment_postings(id) ON DELETE RESTRICT,
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    entry_number TEXT NOT NULL UNIQUE CHECK (btrim(entry_number) <> ''),
    confirmation_token TEXT NOT NULL CHECK (confirmation_token ~ '^[0-9a-f]{64}$'),
    confirmation_digest TEXT NOT NULL CHECK (confirmation_digest ~ '^[0-9a-f]{64}$'),
    confirmed_evidence_digest TEXT NOT NULL CHECK (confirmed_evidence_digest ~ '^[0-9a-f]{64}$'),
    confirmed_refund_amount NUMERIC(18,2) NOT NULL CHECK (confirmed_refund_amount > 0),
    confirmed_cash_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    confirmed_tax_recoverable_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    confirmed_posting_date DATE NOT NULL,
    confirmed_fiscal_period_id UUID NOT NULL REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    policy_version TEXT NOT NULL CHECK (policy_version = 'v1_tax_recoverable_refund_posting_v1'),
    posted_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    posted_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE OR REPLACE FUNCTION accounting.guard_v1_tax_recoverable_refund_immutable_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    insert_allowed BOOLEAN := false;
BEGIN
    IF TG_TABLE_NAME = 'v1_tax_recoverable_refund_evidence' THEN
        insert_allowed := coalesce(current_setting('accounting.v1_tax_recoverable_refund_evidence_insert_allowed', true), '') = 'on';
    ELSIF TG_TABLE_NAME = 'v1_tax_recoverable_refund_preparations' THEN
        insert_allowed := coalesce(current_setting('accounting.v1_tax_recoverable_refund_preparation_insert_allowed', true), '') = 'on';
    ELSIF TG_TABLE_NAME = 'v1_tax_recoverable_refund_postings' THEN
        insert_allowed := coalesce(current_setting('accounting.v1_tax_recoverable_refund_posting_insert_allowed', true), '') = 'on';
    END IF;

    IF TG_OP = 'INSERT' AND insert_allowed THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'V1 Tax Recoverable refund evidence and audit rows are immutable and must use the protected Management workflow.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_v1_tax_recoverable_refund_evidence_guard
    ON accounting.v1_tax_recoverable_refund_evidence;
CREATE TRIGGER accounting_v1_tax_recoverable_refund_evidence_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.v1_tax_recoverable_refund_evidence
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_recoverable_refund_immutable_write();

DROP TRIGGER IF EXISTS accounting_v1_tax_recoverable_refund_preparation_guard
    ON accounting.v1_tax_recoverable_refund_preparations;
CREATE TRIGGER accounting_v1_tax_recoverable_refund_preparation_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.v1_tax_recoverable_refund_preparations
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_recoverable_refund_immutable_write();

DROP TRIGGER IF EXISTS accounting_v1_tax_recoverable_refund_posting_guard
    ON accounting.v1_tax_recoverable_refund_postings;
CREATE TRIGGER accounting_v1_tax_recoverable_refund_posting_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.v1_tax_recoverable_refund_postings
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_recoverable_refund_immutable_write();

CREATE OR REPLACE FUNCTION accounting.guard_v1_tax_recoverable_refund_journal_entry_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    reversed_source TEXT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF (
            NEW.source_type = 'v1_tax_recoverable_refund'
            OR coalesce(NEW.source_event_key, '') LIKE 'v1_tax_recoverable_refund:%'
        )
        AND coalesce(current_setting('accounting.v1_tax_recoverable_refund_journal_prepare_allowed', true), '') <> 'on' THEN
            RAISE EXCEPTION 'V1 Tax Recoverable refund journals must use the protected Management refund preparation function.';
        END IF;

        IF NEW.reversal_of_entry_id IS NOT NULL THEN
            SELECT item.source_type INTO reversed_source
            FROM accounting.journal_entries item
            WHERE item.id = NEW.reversal_of_entry_id;
            IF reversed_source = 'v1_tax_recoverable_refund' THEN
                RAISE EXCEPTION 'Posted V1 Tax Recoverable refunds cannot be reversed through the manual General Journal; new retained correction evidence is required.';
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.source_type IS DISTINCT FROM 'v1_tax_recoverable_refund' THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'V1 Tax Recoverable refund journals are immutable and cannot be deleted.';
    END IF;

    IF OLD.status = 'draft' AND NEW.status = 'posted' THEN
        IF coalesce(current_setting('accounting.v1_tax_recoverable_refund_journal_post_allowed', true), '') <> 'on' THEN
            RAISE EXCEPTION 'V1 Tax Recoverable refund journals require the protected Management refund posting function.';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'V1 Tax Recoverable refund journals are system generated and immutable.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_v1_tax_recoverable_refund_journal_entry_guard
    ON accounting.journal_entries;
CREATE TRIGGER accounting_v1_tax_recoverable_refund_journal_entry_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_recoverable_refund_journal_entry_change();

CREATE OR REPLACE FUNCTION accounting.guard_v1_tax_recoverable_refund_journal_line_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_entry_id UUID;
    target_source_type TEXT;
BEGIN
    target_entry_id := CASE WHEN TG_OP = 'DELETE' THEN OLD.journal_entry_id ELSE NEW.journal_entry_id END;
    SELECT item.source_type INTO target_source_type
    FROM accounting.journal_entries item
    WHERE item.id = target_entry_id;

    IF target_source_type = 'v1_tax_recoverable_refund'
       AND coalesce(current_setting('accounting.v1_tax_recoverable_refund_journal_line_write_allowed', true), '') <> 'on' THEN
        RAISE EXCEPTION 'V1 Tax Recoverable refund journal lines are system generated and immutable.';
    END IF;

    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_v1_tax_recoverable_refund_journal_line_guard
    ON accounting.journal_lines;
CREATE TRIGGER accounting_v1_tax_recoverable_refund_journal_line_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_lines
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_recoverable_refund_journal_line_change();

CREATE OR REPLACE FUNCTION accounting.record_v1_tax_recoverable_refund_evidence(
    p_actor_user_id UUID,
    p_idempotency_key UUID,
    p_adjustment_posting_id UUID,
    p_refund_date DATE,
    p_cash_account_code TEXT,
    p_refund_reference TEXT,
    p_authority_reference TEXT,
    p_evidence_digest TEXT,
    p_evidence_note TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    normalized_cash_code TEXT := btrim(coalesce(p_cash_account_code, ''));
    normalized_refund_reference TEXT := btrim(coalesce(p_refund_reference, ''));
    normalized_authority_reference TEXT := btrim(coalesce(p_authority_reference, ''));
    normalized_digest TEXT := lower(btrim(coalesce(p_evidence_digest, '')));
    normalized_note TEXT := btrim(coalesce(p_evidence_note, ''));
    adjustment_posting accounting.v1_tax_adjustment_postings%ROWTYPE;
    adjustment_evidence accounting.v1_tax_adjustment_evidence%ROWTYPE;
    adjustment_queue accounting.v1_tax_adjustment_queue%ROWTYPE;
    adjustment_journal accounting.journal_entries%ROWTYPE;
    recoverable_account accounting.accounts%ROWTYPE;
    cash_account accounting.accounts%ROWTYPE;
    existing accounting.v1_tax_recoverable_refund_evidence%ROWTYPE;
    created_id UUID;
BEGIN
    PERFORM accounting.require_v1_tax_management_actor(
        p_actor_user_id,
        'accounting.tax.recoverable_refund_evidence.record'
    );

    IF p_idempotency_key IS NULL OR p_adjustment_posting_id IS NULL
       OR p_refund_date IS NULL OR normalized_cash_code NOT IN ('1010', '1030')
       OR normalized_refund_reference = '' OR normalized_authority_reference = ''
       OR normalized_digest !~ '^[0-9a-f]{64}$' OR length(normalized_note) < 20 THEN
        RAISE EXCEPTION 'Tax Recoverable cash-refund evidence requires exact adjustment posting, refund date, approved cash/bank account, retained refund/authority references, SHA-256 digest and substantive note.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended('v1-tax-recoverable-refund:' || p_adjustment_posting_id::text, 0)
    );

    SELECT * INTO adjustment_posting
    FROM accounting.v1_tax_adjustment_postings item
    WHERE item.id = p_adjustment_posting_id
    FOR SHARE;
    IF adjustment_posting.id IS NULL THEN
        RAISE EXCEPTION 'Posted V1 Tax Recoverable adjustment was not found.';
    END IF;

    SELECT * INTO adjustment_evidence
    FROM accounting.v1_tax_adjustment_evidence item
    WHERE item.id = adjustment_posting.adjustment_evidence_id
    FOR SHARE;
    SELECT * INTO adjustment_queue
    FROM accounting.v1_tax_adjustment_queue item
    WHERE item.adjustment_posting_id = adjustment_posting.id;
    SELECT * INTO adjustment_journal
    FROM accounting.journal_entries item
    WHERE item.id = adjustment_posting.journal_entry_id
    FOR SHARE;
    SELECT * INTO recoverable_account
    FROM accounting.accounts account
    WHERE account.id = adjustment_posting.confirmed_debit_account_id
    FOR SHARE;

    IF adjustment_evidence.id IS NULL
       OR adjustment_evidence.adjustment_kind <> 'recognize_settled_tax_recoverable'
       OR adjustment_queue.adjustment_posting_id IS NULL
       OR adjustment_queue.adjustment_status <> 'posted_settled_tax_recoverable'
       OR adjustment_journal.id IS NULL OR adjustment_journal.status <> 'posted'
       OR adjustment_journal.entry_number <> adjustment_posting.entry_number
       OR adjustment_posting.confirmed_adjustment_amount <> adjustment_evidence.adjustment_amount
       OR recoverable_account.id IS NULL OR recoverable_account.system_key <> 'tax_recoverable'
       OR recoverable_account.code <> '1130' OR recoverable_account.account_type <> 'asset'
       OR recoverable_account.normal_balance <> 'debit' OR NOT recoverable_account.is_active
       OR NOT recoverable_account.is_posting THEN
        RAISE EXCEPTION 'Cash refund realization requires an exact current posted settled-tax decrease carried in active 1130 Tax Recoverable.';
    END IF;

    IF p_refund_date < adjustment_posting.confirmed_posting_date THEN
        RAISE EXCEPTION 'Retained cash refund evidence cannot predate recognition of the exact Tax Recoverable.';
    END IF;

    SELECT * INTO cash_account
    FROM accounting.accounts account
    WHERE account.code = normalized_cash_code
    FOR SHARE;
    IF cash_account.id IS NULL OR cash_account.system_key NOT IN ('cash_office', 'cash_bank_gcash')
       OR cash_account.code NOT IN ('1010', '1030') OR cash_account.account_type <> 'asset'
       OR cash_account.normal_balance <> 'debit' OR NOT cash_account.is_active
       OR NOT cash_account.is_posting THEN
        RAISE EXCEPTION 'Tax Recoverable cash refund must use active approved 1010 Cash - Office or 1030 Cash - Bank / GCash.';
    END IF;

    SELECT * INTO existing
    FROM accounting.v1_tax_recoverable_refund_evidence item
    WHERE item.idempotency_key = p_idempotency_key
    FOR SHARE;
    IF existing.id IS NOT NULL THEN
        IF existing.adjustment_posting_id = adjustment_posting.id
           AND existing.adjustment_evidence_id = adjustment_evidence.id
           AND existing.tax_type = adjustment_evidence.tax_type
           AND existing.refund_amount = adjustment_posting.confirmed_adjustment_amount
           AND existing.refund_date = p_refund_date
           AND existing.cash_account_id = cash_account.id
           AND existing.refund_reference = normalized_refund_reference
           AND existing.authority_reference = normalized_authority_reference
           AND existing.evidence_digest = normalized_digest
           AND existing.evidence_note = normalized_note
           AND existing.recorded_by_user_id = p_actor_user_id THEN
            RETURN existing.id;
        END IF;
        RAISE EXCEPTION 'Tax Recoverable refund idempotency key already belongs to different immutable evidence.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM accounting.v1_tax_recoverable_refund_evidence item
        WHERE item.adjustment_posting_id = adjustment_posting.id
    ) THEN
        RAISE EXCEPTION 'This exact Tax Recoverable already has immutable refund realization evidence.';
    END IF;

    PERFORM set_config('accounting.v1_tax_recoverable_refund_evidence_insert_allowed', 'on', true);
    INSERT INTO accounting.v1_tax_recoverable_refund_evidence(
        idempotency_key, adjustment_posting_id, adjustment_evidence_id,
        tax_type, refund_amount, refund_date, cash_account_id,
        refund_reference, authority_reference, evidence_digest,
        evidence_note, recorded_by_user_id
    ) VALUES (
        p_idempotency_key, adjustment_posting.id, adjustment_evidence.id,
        adjustment_evidence.tax_type, adjustment_posting.confirmed_adjustment_amount,
        p_refund_date, cash_account.id, normalized_refund_reference,
        normalized_authority_reference, normalized_digest, normalized_note,
        p_actor_user_id
    ) RETURNING id INTO created_id;
    PERFORM set_config('accounting.v1_tax_recoverable_refund_evidence_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.tax.recoverable_refund.evidence_recorded',
        'v1_tax_recoverable_refund',
        created_id,
        jsonb_build_object(
            'adjustment_posting_id', adjustment_posting.id,
            'adjustment_evidence_id', adjustment_evidence.id,
            'tax_type', adjustment_evidence.tax_type,
            'refund_amount', adjustment_posting.confirmed_adjustment_amount,
            'refund_date', p_refund_date,
            'cash_account_code', cash_account.code,
            'evidence_digest', normalized_digest,
            'tax_recoverable_credit_application_enabled', false,
            'automatic_source_posting', false
        )
    );

    RETURN created_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.prepare_v1_tax_recoverable_refund_journal(
    p_refund_evidence_id UUID,
    p_actor_user_id UUID
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    evidence accounting.v1_tax_recoverable_refund_evidence%ROWTYPE;
    existing accounting.v1_tax_recoverable_refund_preparations%ROWTYPE;
    adjustment_posting accounting.v1_tax_adjustment_postings%ROWTYPE;
    adjustment_evidence accounting.v1_tax_adjustment_evidence%ROWTYPE;
    adjustment_queue accounting.v1_tax_adjustment_queue%ROWTYPE;
    cash_account accounting.accounts%ROWTYPE;
    recoverable_account accounting.accounts%ROWTYPE;
    target_period accounting.fiscal_periods%ROWTYPE;
    protected_source_event_key TEXT;
    created_journal_id UUID;
BEGIN
    PERFORM accounting.require_v1_tax_management_actor(
        p_actor_user_id,
        'accounting.tax.recoverable_refund.prepare'
    );
    IF p_refund_evidence_id IS NULL THEN
        RAISE EXCEPTION 'Tax Recoverable refund preparation requires exact immutable refund evidence.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended('v1-tax-recoverable-refund-evidence:' || p_refund_evidence_id::text, 0)
    );

    SELECT * INTO existing
    FROM accounting.v1_tax_recoverable_refund_preparations item
    WHERE item.refund_evidence_id = p_refund_evidence_id;
    IF existing.id IS NOT NULL THEN
        RETURN existing.journal_entry_id;
    END IF;

    SELECT * INTO evidence
    FROM accounting.v1_tax_recoverable_refund_evidence item
    WHERE item.id = p_refund_evidence_id
    FOR SHARE;
    IF evidence.id IS NULL THEN
        RAISE EXCEPTION 'Tax Recoverable refund evidence was not found.';
    END IF;

    SELECT * INTO adjustment_posting
    FROM accounting.v1_tax_adjustment_postings item
    WHERE item.id = evidence.adjustment_posting_id
    FOR SHARE;
    SELECT * INTO adjustment_evidence
    FROM accounting.v1_tax_adjustment_evidence item
    WHERE item.id = evidence.adjustment_evidence_id
    FOR SHARE;
    SELECT * INTO adjustment_queue
    FROM accounting.v1_tax_adjustment_queue item
    WHERE item.adjustment_posting_id = adjustment_posting.id;
    SELECT * INTO cash_account
    FROM accounting.accounts account
    WHERE account.id = evidence.cash_account_id
    FOR SHARE;
    SELECT * INTO recoverable_account
    FROM accounting.accounts account
    WHERE account.id = adjustment_posting.confirmed_debit_account_id
    FOR SHARE;

    IF adjustment_posting.id IS NULL OR adjustment_evidence.id IS NULL
       OR adjustment_evidence.id <> adjustment_posting.adjustment_evidence_id
       OR adjustment_evidence.adjustment_kind <> 'recognize_settled_tax_recoverable'
       OR adjustment_queue.adjustment_status <> 'posted_settled_tax_recoverable'
       OR adjustment_posting.confirmed_adjustment_amount <> evidence.refund_amount
       OR evidence.tax_type <> adjustment_evidence.tax_type
       OR recoverable_account.id IS NULL OR recoverable_account.system_key <> 'tax_recoverable'
       OR recoverable_account.code <> '1130' OR NOT recoverable_account.is_active
       OR NOT recoverable_account.is_posting
       OR cash_account.id IS NULL OR cash_account.code NOT IN ('1010', '1030')
       OR cash_account.system_key NOT IN ('cash_office', 'cash_bank_gcash')
       OR NOT cash_account.is_active OR NOT cash_account.is_posting THEN
        RAISE EXCEPTION 'Exact Tax Recoverable adjustment or approved refund account changed after refund evidence was recorded.';
    END IF;

    SELECT * INTO target_period
    FROM accounting.fiscal_periods period
    WHERE period.status = 'open'
      AND evidence.refund_date BETWEEN period.start_date AND period.end_date
    ORDER BY period.start_date DESC
    LIMIT 1
    FOR SHARE;
    IF target_period.id IS NULL THEN
        RAISE EXCEPTION 'Tax Recoverable cash refund date must be inside an open fiscal period.';
    END IF;

    protected_source_event_key := 'v1_tax_recoverable_refund:' || evidence.id::text;
    IF EXISTS (
        SELECT 1 FROM accounting.journal_entries journal
        WHERE journal.source_event_key = protected_source_event_key
    ) THEN
        RAISE EXCEPTION 'Protected V1 Tax Recoverable refund source identity is already occupied outside the refund audit.';
    END IF;

    PERFORM set_config('accounting.v1_tax_recoverable_refund_journal_prepare_allowed', 'on', true);
    INSERT INTO accounting.journal_entries(
        fiscal_period_id, posting_date, description, status, source_type,
        source_reference, source_event_key, created_by_user_id, updated_at
    ) VALUES (
        target_period.id, evidence.refund_date,
        'Protected V1 Tax Recoverable cash refund: ' || evidence.refund_reference,
        'draft', 'v1_tax_recoverable_refund', evidence.id::text,
        protected_source_event_key, p_actor_user_id, now()
    ) RETURNING id INTO created_journal_id;
    PERFORM set_config('accounting.v1_tax_recoverable_refund_journal_prepare_allowed', 'off', true);

    PERFORM set_config('accounting.v1_tax_recoverable_refund_journal_line_write_allowed', 'on', true);
    INSERT INTO accounting.journal_lines(
        journal_entry_id, line_number, account_id, description, debit, credit,
        client_id, loan_id
    ) VALUES
        (
            created_journal_id, 1, cash_account.id,
            'Receive retained tax refund', evidence.refund_amount, 0,
            adjustment_queue.client_id, adjustment_queue.loan_id
        ),
        (
            created_journal_id, 2, recoverable_account.id,
            'Realize 1130 Tax Recoverable', 0, evidence.refund_amount,
            adjustment_queue.client_id, adjustment_queue.loan_id
        );
    PERFORM set_config('accounting.v1_tax_recoverable_refund_journal_line_write_allowed', 'off', true);

    INSERT INTO accounting.journal_events(journal_entry_id, event_type, actor_user_id, details)
    VALUES (
        created_journal_id, 'draft_created', p_actor_user_id,
        jsonb_build_object(
            'source_type', 'v1_tax_recoverable_refund',
            'refund_evidence_id', evidence.id,
            'adjustment_posting_id', evidence.adjustment_posting_id,
            'refund_amount', evidence.refund_amount,
            'cash_account_code', cash_account.code,
            'tax_recoverable_account_code', recoverable_account.code,
            'automatic_source_posting', false
        )
    );

    PERFORM set_config('accounting.v1_tax_recoverable_refund_preparation_insert_allowed', 'on', true);
    INSERT INTO accounting.v1_tax_recoverable_refund_preparations(
        refund_evidence_id, journal_entry_id, source_event_key, posting_date,
        refund_amount, cash_account_id, tax_recoverable_account_id,
        fiscal_period_id, prepared_by_user_id
    ) VALUES (
        evidence.id, created_journal_id, protected_source_event_key,
        evidence.refund_date, evidence.refund_amount, cash_account.id,
        recoverable_account.id, target_period.id, p_actor_user_id
    );
    PERFORM set_config('accounting.v1_tax_recoverable_refund_preparation_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id, 'accounting.tax.recoverable_refund.prepared',
        'v1_tax_recoverable_refund', evidence.id,
        jsonb_build_object(
            'journal_entry_id', created_journal_id,
            'refund_amount', evidence.refund_amount,
            'cash_account_code', cash_account.code,
            'tax_recoverable_account_code', recoverable_account.code,
            'fiscal_period_id', target_period.id,
            'automatic_source_posting', false
        )
    );

    RETURN created_journal_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.post_v1_tax_recoverable_refund_journal(
    p_refund_evidence_id UUID,
    p_actor_user_id UUID,
    p_confirmation_token TEXT,
    p_expected_evidence_digest TEXT,
    p_expected_refund_amount NUMERIC,
    p_expected_cash_account_code TEXT,
    p_expected_tax_recoverable_account_code TEXT,
    p_expected_posting_date DATE,
    p_expected_fiscal_period_id UUID,
    p_policy_version TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    normalized_token TEXT := lower(btrim(coalesce(p_confirmation_token, '')));
    normalized_digest TEXT := lower(btrim(coalesce(p_expected_evidence_digest, '')));
    normalized_amount NUMERIC(18,2) := round(coalesce(p_expected_refund_amount, -1), 2);
    normalized_cash_code TEXT := btrim(coalesce(p_expected_cash_account_code, ''));
    normalized_recoverable_code TEXT := btrim(coalesce(p_expected_tax_recoverable_account_code, ''));
    evidence accounting.v1_tax_recoverable_refund_evidence%ROWTYPE;
    preparation accounting.v1_tax_recoverable_refund_preparations%ROWTYPE;
    existing accounting.v1_tax_recoverable_refund_postings%ROWTYPE;
    adjustment_posting accounting.v1_tax_adjustment_postings%ROWTYPE;
    adjustment_evidence accounting.v1_tax_adjustment_evidence%ROWTYPE;
    adjustment_queue accounting.v1_tax_adjustment_queue%ROWTYPE;
    cash_account accounting.accounts%ROWTYPE;
    recoverable_account accounting.accounts%ROWTYPE;
    target_period accounting.fiscal_periods%ROWTYPE;
    journal accounting.journal_entries%ROWTYPE;
    line_count INTEGER;
    total_debit NUMERIC(18,2);
    total_credit NUMERIC(18,2);
    cash_debit NUMERIC(18,2);
    recoverable_credit NUMERIC(18,2);
    foreign_line_count INTEGER;
    generated_entry_number TEXT;
    confirmation_digest_value TEXT;
    created_posting_id UUID;
BEGIN
    PERFORM accounting.require_v1_tax_management_actor(
        p_actor_user_id,
        'accounting.tax.recoverable_refund.post'
    );

    IF p_refund_evidence_id IS NULL
       OR p_policy_version IS DISTINCT FROM 'v1_tax_recoverable_refund_posting_v1'
       OR normalized_token !~ '^[0-9a-f]{64}$'
       OR normalized_digest !~ '^[0-9a-f]{64}$'
       OR p_expected_refund_amount IS DISTINCT FROM normalized_amount
       OR normalized_amount <= 0
       OR normalized_cash_code NOT IN ('1010', '1030')
       OR normalized_recoverable_code <> '1130'
       OR p_expected_posting_date IS NULL OR p_expected_fiscal_period_id IS NULL THEN
        RAISE EXCEPTION 'Protected Tax Recoverable refund posting requires exact Management confirmation, evidence digest, full refund amount, approved cash/bank account, 1130 account, date, period and policy.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended('v1-tax-recoverable-refund-evidence:' || p_refund_evidence_id::text, 0)
    );

    SELECT * INTO evidence
    FROM accounting.v1_tax_recoverable_refund_evidence item
    WHERE item.id = p_refund_evidence_id
    FOR SHARE;
    SELECT * INTO preparation
    FROM accounting.v1_tax_recoverable_refund_preparations item
    WHERE item.refund_evidence_id = p_refund_evidence_id
    FOR SHARE;
    IF evidence.id IS NULL OR preparation.id IS NULL THEN
        RAISE EXCEPTION 'Tax Recoverable refund must have exact immutable evidence and a protected preparation before posting.';
    END IF;

    SELECT * INTO existing
    FROM accounting.v1_tax_recoverable_refund_postings item
    WHERE item.preparation_id = preparation.id
    FOR SHARE;
    IF existing.id IS NOT NULL THEN
        IF existing.confirmation_token = normalized_token
           AND existing.confirmed_evidence_digest = normalized_digest
           AND existing.confirmed_refund_amount = normalized_amount
           AND existing.confirmed_posting_date = p_expected_posting_date
           AND existing.confirmed_fiscal_period_id = p_expected_fiscal_period_id
           AND existing.policy_version = p_policy_version
           AND existing.posted_by_user_id = p_actor_user_id
           AND EXISTS (
                SELECT 1 FROM accounting.accounts account
                WHERE account.id = existing.confirmed_cash_account_id
                  AND account.code = normalized_cash_code
           )
           AND EXISTS (
                SELECT 1 FROM accounting.accounts account
                WHERE account.id = existing.confirmed_tax_recoverable_account_id
                  AND account.code = normalized_recoverable_code
           ) THEN
            RETURN existing.id;
        END IF;
        RAISE EXCEPTION 'Existing V1 Tax Recoverable refund posting does not match the immutable retry identity.';
    END IF;

    IF evidence.evidence_digest <> normalized_digest
       OR evidence.refund_amount <> normalized_amount
       OR evidence.refund_date <> p_expected_posting_date
       OR preparation.posting_date <> p_expected_posting_date
       OR preparation.refund_amount <> normalized_amount THEN
        RAISE EXCEPTION 'Exact immutable Tax Recoverable refund evidence no longer matches the confirmed posting coordinates.';
    END IF;

    SELECT * INTO adjustment_posting
    FROM accounting.v1_tax_adjustment_postings item
    WHERE item.id = evidence.adjustment_posting_id
    FOR SHARE;
    SELECT * INTO adjustment_evidence
    FROM accounting.v1_tax_adjustment_evidence item
    WHERE item.id = evidence.adjustment_evidence_id
    FOR SHARE;
    SELECT * INTO adjustment_queue
    FROM accounting.v1_tax_adjustment_queue item
    WHERE item.adjustment_posting_id = adjustment_posting.id;
    IF adjustment_posting.id IS NULL OR adjustment_evidence.id IS NULL
       OR adjustment_evidence.id <> adjustment_posting.adjustment_evidence_id
       OR adjustment_evidence.adjustment_kind <> 'recognize_settled_tax_recoverable'
       OR adjustment_queue.adjustment_status <> 'posted_settled_tax_recoverable'
       OR adjustment_posting.confirmed_adjustment_amount <> normalized_amount THEN
        RAISE EXCEPTION 'Exact posted Tax Recoverable source changed before cash-refund posting.';
    END IF;

    SELECT * INTO cash_account
    FROM accounting.accounts account
    WHERE account.id = preparation.cash_account_id
    FOR SHARE;
    SELECT * INTO recoverable_account
    FROM accounting.accounts account
    WHERE account.id = preparation.tax_recoverable_account_id
    FOR SHARE;
    IF cash_account.id IS NULL OR cash_account.id <> evidence.cash_account_id
       OR cash_account.code <> normalized_cash_code
       OR cash_account.system_key NOT IN ('cash_office', 'cash_bank_gcash')
       OR cash_account.account_type <> 'asset' OR cash_account.normal_balance <> 'debit'
       OR NOT cash_account.is_active OR NOT cash_account.is_posting
       OR recoverable_account.id IS NULL OR recoverable_account.id <> adjustment_posting.confirmed_debit_account_id
       OR recoverable_account.code <> normalized_recoverable_code
       OR recoverable_account.system_key <> 'tax_recoverable'
       OR recoverable_account.account_type <> 'asset' OR recoverable_account.normal_balance <> 'debit'
       OR NOT recoverable_account.is_active OR NOT recoverable_account.is_posting THEN
        RAISE EXCEPTION 'Exact confirmed cash/Tax Recoverable accounts are no longer posting-ready.';
    END IF;

    SELECT * INTO target_period
    FROM accounting.fiscal_periods period
    WHERE period.id = p_expected_fiscal_period_id
    FOR SHARE;
    IF target_period.id IS NULL OR target_period.status <> 'open'
       OR p_expected_posting_date NOT BETWEEN target_period.start_date AND target_period.end_date
       OR preparation.fiscal_period_id <> target_period.id THEN
        RAISE EXCEPTION 'Tax Recoverable refund posting requires the exact still-open fiscal period used at preparation.';
    END IF;

    SELECT * INTO journal
    FROM accounting.journal_entries item
    WHERE item.id = preparation.journal_entry_id
    FOR UPDATE;
    IF journal.id IS NULL OR journal.status <> 'draft'
       OR journal.source_type <> 'v1_tax_recoverable_refund'
       OR journal.source_reference <> evidence.id::text
       OR journal.source_event_key <> preparation.source_event_key
       OR journal.posting_date <> p_expected_posting_date
       OR journal.fiscal_period_id <> target_period.id
       OR journal.reversal_of_entry_id IS NOT NULL THEN
        RAISE EXCEPTION 'Prepared V1 Tax Recoverable refund General Journal draft no longer matches the protected refund coordinates.';
    END IF;

    SELECT
        count(*)::integer,
        coalesce(sum(line.debit), 0)::numeric(18,2),
        coalesce(sum(line.credit), 0)::numeric(18,2),
        coalesce(sum(line.debit) FILTER (WHERE line.account_id = cash_account.id), 0)::numeric(18,2),
        coalesce(sum(line.credit) FILTER (WHERE line.account_id = recoverable_account.id), 0)::numeric(18,2),
        count(*) FILTER (
            WHERE line.account_id NOT IN (cash_account.id, recoverable_account.id)
               OR line.client_id IS DISTINCT FROM adjustment_queue.client_id
               OR line.loan_id IS DISTINCT FROM adjustment_queue.loan_id
        )::integer
    INTO line_count, total_debit, total_credit, cash_debit, recoverable_credit, foreign_line_count
    FROM accounting.journal_lines line
    WHERE line.journal_entry_id = journal.id;

    IF line_count <> 2 OR total_debit <> normalized_amount OR total_credit <> normalized_amount
       OR cash_debit <> normalized_amount OR recoverable_credit <> normalized_amount
       OR foreign_line_count <> 0 THEN
        RAISE EXCEPTION 'Prepared V1 Tax Recoverable refund lines do not exactly reconcile Dr approved cash-bank / Cr 1130 Tax Recoverable to retained refund evidence.';
    END IF;

    confirmation_digest_value := encode(sha256(convert_to(concat_ws('|',
        p_policy_version, evidence.id::text, evidence.adjustment_posting_id::text,
        normalized_digest, to_char(normalized_amount, 'FM999999999999990.00'),
        cash_account.id::text, recoverable_account.id::text,
        p_expected_posting_date::text, target_period.id::text,
        journal.id::text, normalized_token
    ), 'UTF8')), 'hex');

    PERFORM set_config('accounting.v1_tax_recoverable_refund_journal_post_allowed', 'on', true);
    generated_entry_number := accounting.post_journal_entry(journal.id, p_actor_user_id);
    PERFORM set_config('accounting.v1_tax_recoverable_refund_journal_post_allowed', 'off', true);

    IF coalesce(current_setting('accounting.v1_tax_recoverable_refund_force_audit_failure', true), '') = 'on' THEN
        RAISE EXCEPTION 'Forced V1 Tax Recoverable refund audit failure.';
    END IF;

    PERFORM set_config('accounting.v1_tax_recoverable_refund_posting_insert_allowed', 'on', true);
    INSERT INTO accounting.v1_tax_recoverable_refund_postings(
        preparation_id, refund_evidence_id, adjustment_posting_id,
        journal_entry_id, entry_number, confirmation_token,
        confirmation_digest, confirmed_evidence_digest, confirmed_refund_amount,
        confirmed_cash_account_id, confirmed_tax_recoverable_account_id,
        confirmed_posting_date, confirmed_fiscal_period_id,
        policy_version, posted_by_user_id
    ) VALUES (
        preparation.id, evidence.id, evidence.adjustment_posting_id,
        journal.id, generated_entry_number, normalized_token,
        confirmation_digest_value, normalized_digest, normalized_amount,
        cash_account.id, recoverable_account.id, p_expected_posting_date,
        target_period.id, p_policy_version, p_actor_user_id
    ) RETURNING id INTO created_posting_id;
    PERFORM set_config('accounting.v1_tax_recoverable_refund_posting_insert_allowed', 'off', true);

    INSERT INTO accounting.journal_events(journal_entry_id, event_type, actor_user_id, details)
    VALUES (
        journal.id, 'posted', p_actor_user_id,
        jsonb_build_object(
            'entry_number', generated_entry_number,
            'source_type', 'v1_tax_recoverable_refund',
            'refund_evidence_id', evidence.id,
            'adjustment_posting_id', evidence.adjustment_posting_id,
            'confirmation_digest', confirmation_digest_value,
            'automatic_source_posting', false
        )
    );

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id, 'accounting.tax.recoverable_refund.posted',
        'v1_tax_recoverable_refund', evidence.id,
        jsonb_build_object(
            'journal_entry_id', journal.id,
            'entry_number', generated_entry_number,
            'refund_amount', normalized_amount,
            'cash_account_code', cash_account.code,
            'tax_recoverable_account_code', recoverable_account.code,
            'confirmation_digest', confirmation_digest_value,
            'tax_recoverable_credit_application_enabled', false,
            'automatic_source_posting', false
        )
    );

    RETURN created_posting_id;
END;
$$;

CREATE OR REPLACE VIEW accounting.v1_tax_recoverable_refund_queue AS
SELECT
    evidence.id AS refund_evidence_id,
    evidence.adjustment_posting_id,
    evidence.adjustment_evidence_id,
    evidence.tax_type,
    adjustment.source_id,
    adjustment.loan_id,
    adjustment.client_id,
    evidence.refund_amount,
    evidence.refund_date,
    evidence.cash_account_id,
    cash.code AS cash_account_code,
    cash.name AS cash_account_name,
    evidence.refund_reference,
    evidence.authority_reference,
    evidence.evidence_digest,
    evidence.recorded_by_user_id,
    evidence.recorded_at,
    preparation.id AS preparation_id,
    preparation.journal_entry_id,
    journal.status AS journal_status,
    journal.entry_number,
    preparation.fiscal_period_id,
    preparation.tax_recoverable_account_id,
    recoverable.code AS tax_recoverable_account_code,
    recoverable.name AS tax_recoverable_account_name,
    preparation.prepared_by_user_id,
    preparation.prepared_at,
    posting.id AS refund_posting_id,
    posting.confirmation_digest,
    posting.posted_by_user_id,
    posting.posted_at,
    CASE
        WHEN posting.id IS NOT NULL THEN 'refund_realized'
        WHEN adjustment.adjustment_status <> 'posted_settled_tax_recoverable'
            THEN 'blocked_recoverable_not_current'
        WHEN cash.id IS NULL OR cash.code NOT IN ('1010', '1030')
          OR cash.system_key NOT IN ('cash_office', 'cash_bank_gcash')
          OR NOT cash.is_active OR NOT cash.is_posting
            THEN 'blocked_cash_account'
        WHEN preparation.id IS NOT NULL AND journal.status IS DISTINCT FROM 'draft'
            THEN 'blocked_untracked_refund_journal_state'
        WHEN open_period.id IS NULL THEN 'blocked_no_open_refund_period'
        WHEN preparation.id IS NOT NULL THEN 'refund_prepared'
        ELSE 'refund_evidence_ready'
    END AS refund_status,
    CASE
        WHEN posting.id IS NOT NULL THEN NULL
        WHEN adjustment.adjustment_status <> 'posted_settled_tax_recoverable'
            THEN 'Underlying 1130 Tax Recoverable adjustment is no longer in the exact current posted state retained by this refund evidence.'
        WHEN cash.id IS NULL OR cash.code NOT IN ('1010', '1030')
          OR cash.system_key NOT IN ('cash_office', 'cash_bank_gcash')
          OR NOT cash.is_active OR NOT cash.is_posting
            THEN 'Exact retained refund cash/bank account is no longer posting-ready.'
        WHEN preparation.id IS NOT NULL AND journal.status IS DISTINCT FROM 'draft'
            THEN 'Prepared refund journal is not a draft but has no immutable protected refund posting audit.'
        WHEN open_period.id IS NULL
            THEN 'Retained refund date is not inside an open accounting period.'
        WHEN preparation.id IS NOT NULL
            THEN 'Exact Management confirmation is required before protected Tax Recoverable refund posting.'
        ELSE NULL
    END AS refund_blocker,
    true AS tax_recoverable_refund_realization_enabled,
    false AS tax_recoverable_credit_application_enabled,
    false AS automatic_source_posting
FROM accounting.v1_tax_recoverable_refund_evidence evidence
JOIN accounting.v1_tax_adjustment_postings adjustment_posting
  ON adjustment_posting.id = evidence.adjustment_posting_id
LEFT JOIN accounting.v1_tax_adjustment_queue adjustment
  ON adjustment.adjustment_posting_id = adjustment_posting.id
LEFT JOIN accounting.accounts cash
  ON cash.id = evidence.cash_account_id
LEFT JOIN accounting.v1_tax_recoverable_refund_preparations preparation
  ON preparation.refund_evidence_id = evidence.id
LEFT JOIN accounting.journal_entries journal
  ON journal.id = preparation.journal_entry_id
LEFT JOIN accounting.accounts recoverable
  ON recoverable.id = preparation.tax_recoverable_account_id
LEFT JOIN accounting.v1_tax_recoverable_refund_postings posting
  ON posting.preparation_id = preparation.id
LEFT JOIN LATERAL (
    SELECT period.id
    FROM accounting.fiscal_periods period
    WHERE period.status = 'open'
      AND evidence.refund_date BETWEEN period.start_date AND period.end_date
      AND (preparation.fiscal_period_id IS NULL OR preparation.fiscal_period_id = period.id)
    ORDER BY period.start_date DESC
    LIMIT 1
) open_period ON true;

CREATE OR REPLACE VIEW accounting.v1_tax_recoverable_refund_summary AS
SELECT
    count(*)::bigint AS refund_evidence_count,
    count(*) FILTER (WHERE refund_status = 'refund_evidence_ready')::bigint AS ready_to_prepare_count,
    count(*) FILTER (WHERE refund_status = 'refund_prepared')::bigint AS prepared_count,
    count(*) FILTER (WHERE refund_status = 'refund_realized')::bigint AS realized_count,
    count(*) FILTER (WHERE refund_status LIKE 'blocked_%')::bigint AS blocked_count,
    coalesce(sum(refund_amount) FILTER (WHERE refund_status = 'refund_realized'), 0)::numeric(18,2) AS realized_refund_total,
    true AS tax_recoverable_refund_realization_enabled,
    false AS tax_recoverable_credit_application_enabled,
    false AS automatic_source_posting
FROM accounting.v1_tax_recoverable_refund_queue;

CREATE OR REPLACE VIEW accounting.v1_tax_recoverable_controls AS
SELECT
    true AS tax_recoverable_refund_realization_enabled,
    false AS tax_recoverable_credit_application_enabled,
    false AS partial_tax_recoverable_realization_enabled,
    false AS automatic_source_posting;

COMMENT ON TABLE accounting.v1_tax_recoverable_refund_evidence IS
'Immutable Management-approved evidence that an exact posted 1130 Tax Recoverable was actually refunded in full to approved 1010/1030 cash-bank custody. The refund amount is derived from the protected adjustment posting.';
COMMENT ON TABLE accounting.v1_tax_recoverable_refund_postings IS
'Immutable protected posting audit for cash realization of 1130 Tax Recoverable: Dr approved 1010/1030 cash-bank / Cr 1130 Tax Recoverable for the exact retained refund amount.';
COMMENT ON VIEW accounting.v1_tax_recoverable_controls IS
'V1 A6.2 Tax Recoverable controls. Cash-refund realization is protected; tax-credit application, partial realization and automatic source posting remain disabled.';

COMMIT;
