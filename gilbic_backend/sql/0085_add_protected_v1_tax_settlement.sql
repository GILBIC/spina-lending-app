BEGIN;

-- Master #296 A6.2 settlement sub-slice.
-- Tax returns aggregate exact already-posted V1 tax liabilities. Payment evidence
-- then supports one protected settlement journal: Dr 2100 Tax Payables / Cr the
-- exact approved real cash/bank account. No settlement is inferred from filing,
-- no filing is inferred from liability recognition, and automatic posting remains off.

INSERT INTO core.permissions (code, description)
VALUES
    ('accounting.tax.return_evidence.record', 'Record immutable Management-approved V1 tax return/filing evidence and its exact posted-liability composition'),
    ('accounting.tax.payment_evidence.record', 'Record immutable Management-approved V1 tax payment evidence for an exact retained tax return'),
    ('accounting.tax.settlement.prepare', 'Prepare a protected V1 tax settlement General Journal draft from exact return/payment evidence'),
    ('accounting.tax.settlement.post', 'Post a protected V1 tax settlement General Journal after exact Management confirmation')
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code IN (
      'accounting.tax.return_evidence.record',
      'accounting.tax.payment_evidence.record',
      'accounting.tax.settlement.prepare',
      'accounting.tax.settlement.post'
  )
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.v1_tax_return_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key UUID NOT NULL UNIQUE,
    tax_type TEXT NOT NULL CHECK (
        tax_type IN ('documentary_stamp_tax', 'percentage_tax_lending')
    ),
    return_period_start DATE NOT NULL,
    return_period_end DATE NOT NULL,
    filing_date DATE NOT NULL,
    declared_tax_due NUMERIC(18,2) NOT NULL CHECK (declared_tax_due > 0),
    return_reference TEXT NOT NULL CHECK (btrim(return_reference) <> ''),
    evidence_reference TEXT NOT NULL CHECK (btrim(evidence_reference) <> ''),
    evidence_digest TEXT NOT NULL CHECK (evidence_digest ~ '^[0-9a-f]{64}$'),
    evidence_note TEXT NOT NULL CHECK (length(btrim(evidence_note)) >= 20),
    recorded_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (return_period_end >= return_period_start),
    CHECK (filing_date >= return_period_end)
);

CREATE INDEX IF NOT EXISTS v1_tax_return_evidence_period_idx
    ON accounting.v1_tax_return_evidence(tax_type, return_period_start, return_period_end, filing_date DESC);

CREATE TABLE IF NOT EXISTS accounting.v1_tax_return_liability_items (
    tax_return_id UUID NOT NULL
        REFERENCES accounting.v1_tax_return_evidence(id) ON DELETE RESTRICT,
    tax_liability_posting_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_liability_postings(id) ON DELETE RESTRICT,
    tax_type TEXT NOT NULL CHECK (
        tax_type IN ('documentary_stamp_tax', 'percentage_tax_lending')
    ),
    evidence_id UUID NOT NULL,
    recognition_date DATE NOT NULL,
    tax_due NUMERIC(18,2) NOT NULL CHECK (tax_due > 0),
    liability_entry_number TEXT NOT NULL CHECK (btrim(liability_entry_number) <> ''),
    PRIMARY KEY (tax_return_id, tax_liability_posting_id)
);

CREATE TABLE IF NOT EXISTS accounting.v1_tax_payment_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key UUID NOT NULL UNIQUE,
    tax_return_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_return_evidence(id) ON DELETE RESTRICT,
    payment_date DATE NOT NULL,
    payment_amount NUMERIC(18,2) NOT NULL CHECK (payment_amount > 0),
    cash_account_system_key TEXT NOT NULL CHECK (btrim(cash_account_system_key) <> ''),
    payment_reference TEXT NOT NULL CHECK (btrim(payment_reference) <> ''),
    evidence_reference TEXT NOT NULL CHECK (btrim(evidence_reference) <> ''),
    evidence_digest TEXT NOT NULL CHECK (evidence_digest ~ '^[0-9a-f]{64}$'),
    evidence_note TEXT NOT NULL CHECK (length(btrim(evidence_note)) >= 20),
    recorded_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS v1_tax_payment_evidence_date_idx
    ON accounting.v1_tax_payment_evidence(payment_date DESC, recorded_at DESC);

CREATE TABLE IF NOT EXISTS accounting.v1_tax_settlement_preparations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_evidence_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_payment_evidence(id) ON DELETE RESTRICT,
    tax_return_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_return_evidence(id) ON DELETE RESTRICT,
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    source_event_key TEXT NOT NULL UNIQUE CHECK (btrim(source_event_key) <> ''),
    payment_date DATE NOT NULL,
    payment_amount NUMERIC(18,2) NOT NULL CHECK (payment_amount > 0),
    payment_evidence_digest TEXT NOT NULL CHECK (payment_evidence_digest ~ '^[0-9a-f]{64}$'),
    return_evidence_digest TEXT NOT NULL CHECK (return_evidence_digest ~ '^[0-9a-f]{64}$'),
    tax_payable_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    cash_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    fiscal_period_id UUID NOT NULL REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    prepared_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    prepared_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS accounting.v1_tax_settlement_postings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    preparation_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_settlement_preparations(id) ON DELETE RESTRICT,
    payment_evidence_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_payment_evidence(id) ON DELETE RESTRICT,
    tax_return_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_return_evidence(id) ON DELETE RESTRICT,
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    entry_number TEXT NOT NULL UNIQUE CHECK (btrim(entry_number) <> ''),
    confirmation_token TEXT NOT NULL CHECK (confirmation_token ~ '^[0-9a-f]{64}$'),
    confirmation_digest TEXT NOT NULL CHECK (confirmation_digest ~ '^[0-9a-f]{64}$'),
    confirmed_return_evidence_digest TEXT NOT NULL CHECK (confirmed_return_evidence_digest ~ '^[0-9a-f]{64}$'),
    confirmed_payment_evidence_digest TEXT NOT NULL CHECK (confirmed_payment_evidence_digest ~ '^[0-9a-f]{64}$'),
    confirmed_payment_amount NUMERIC(18,2) NOT NULL CHECK (confirmed_payment_amount > 0),
    confirmed_tax_payable_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    confirmed_cash_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    confirmed_posting_date DATE NOT NULL,
    confirmed_fiscal_period_id UUID NOT NULL REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    policy_version TEXT NOT NULL CHECK (policy_version = 'v1_tax_settlement_posting_v1'),
    posted_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    posted_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE OR REPLACE FUNCTION accounting.guard_v1_tax_settlement_immutable_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    insert_allowed BOOLEAN := false;
BEGIN
    IF TG_TABLE_NAME = 'v1_tax_return_evidence' THEN
        insert_allowed := coalesce(current_setting('accounting.v1_tax_return_evidence_insert_allowed', true), '') = 'on';
    ELSIF TG_TABLE_NAME = 'v1_tax_return_liability_items' THEN
        insert_allowed := coalesce(current_setting('accounting.v1_tax_return_evidence_insert_allowed', true), '') = 'on';
    ELSIF TG_TABLE_NAME = 'v1_tax_payment_evidence' THEN
        insert_allowed := coalesce(current_setting('accounting.v1_tax_payment_evidence_insert_allowed', true), '') = 'on';
    ELSIF TG_TABLE_NAME = 'v1_tax_settlement_preparations' THEN
        insert_allowed := coalesce(current_setting('accounting.v1_tax_settlement_preparation_insert_allowed', true), '') = 'on';
    ELSIF TG_TABLE_NAME = 'v1_tax_settlement_postings' THEN
        insert_allowed := coalesce(current_setting('accounting.v1_tax_settlement_posting_insert_allowed', true), '') = 'on';
    END IF;

    IF TG_OP = 'INSERT' AND insert_allowed THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'V1 tax return/payment/settlement evidence and audit rows are immutable and must use the protected Management workflow.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_v1_tax_return_evidence_guard ON accounting.v1_tax_return_evidence;
CREATE TRIGGER accounting_v1_tax_return_evidence_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.v1_tax_return_evidence
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_settlement_immutable_write();

DROP TRIGGER IF EXISTS accounting_v1_tax_return_liability_items_guard ON accounting.v1_tax_return_liability_items;
CREATE TRIGGER accounting_v1_tax_return_liability_items_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.v1_tax_return_liability_items
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_settlement_immutable_write();

DROP TRIGGER IF EXISTS accounting_v1_tax_payment_evidence_guard ON accounting.v1_tax_payment_evidence;
CREATE TRIGGER accounting_v1_tax_payment_evidence_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.v1_tax_payment_evidence
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_settlement_immutable_write();

DROP TRIGGER IF EXISTS accounting_v1_tax_settlement_preparation_guard ON accounting.v1_tax_settlement_preparations;
CREATE TRIGGER accounting_v1_tax_settlement_preparation_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.v1_tax_settlement_preparations
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_settlement_immutable_write();

DROP TRIGGER IF EXISTS accounting_v1_tax_settlement_posting_guard ON accounting.v1_tax_settlement_postings;
CREATE TRIGGER accounting_v1_tax_settlement_posting_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.v1_tax_settlement_postings
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_settlement_immutable_write();

CREATE OR REPLACE FUNCTION accounting.guard_v1_tax_settlement_journal_entry_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    reversed_source TEXT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF (
            NEW.source_type = 'v1_tax_settlement'
            OR coalesce(NEW.source_event_key, '') LIKE 'v1_tax_settlement:%'
        )
        AND coalesce(current_setting('accounting.v1_tax_settlement_journal_prepare_allowed', true), '') <> 'on' THEN
            RAISE EXCEPTION 'V1 tax settlement journals must use the protected Management settlement preparation function.';
        END IF;

        IF NEW.reversal_of_entry_id IS NOT NULL THEN
            SELECT item.source_type INTO reversed_source
            FROM accounting.journal_entries item
            WHERE item.id = NEW.reversal_of_entry_id;
            IF reversed_source = 'v1_tax_settlement' THEN
                RAISE EXCEPTION 'Posted V1 tax settlements cannot be reversed through the manual General Journal; use the protected tax adjustment/reversal workflow.';
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.source_type IS DISTINCT FROM 'v1_tax_settlement' THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'V1 tax settlement journals are immutable and cannot be deleted.';
    END IF;

    IF OLD.status = 'draft' AND NEW.status = 'posted' THEN
        IF coalesce(current_setting('accounting.v1_tax_settlement_journal_post_allowed', true), '') <> 'on' THEN
            RAISE EXCEPTION 'V1 tax settlement journals require the protected Management settlement posting function.';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'V1 tax settlement journals are system generated and immutable.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_v1_tax_settlement_journal_entry_guard ON accounting.journal_entries;
CREATE TRIGGER accounting_v1_tax_settlement_journal_entry_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_settlement_journal_entry_change();

CREATE OR REPLACE FUNCTION accounting.guard_v1_tax_settlement_journal_line_change()
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

    IF target_source_type = 'v1_tax_settlement'
       AND coalesce(current_setting('accounting.v1_tax_settlement_journal_line_write_allowed', true), '') <> 'on' THEN
        RAISE EXCEPTION 'V1 tax settlement journal lines are system generated and immutable.';
    END IF;

    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_v1_tax_settlement_journal_line_guard ON accounting.journal_lines;
CREATE TRIGGER accounting_v1_tax_settlement_journal_line_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_lines
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_settlement_journal_line_change();

CREATE OR REPLACE FUNCTION accounting.record_v1_tax_return_evidence(
    p_actor_user_id UUID,
    p_idempotency_key UUID,
    p_tax_type TEXT,
    p_return_period_start DATE,
    p_return_period_end DATE,
    p_filing_date DATE,
    p_declared_tax_due NUMERIC,
    p_return_reference TEXT,
    p_evidence_reference TEXT,
    p_evidence_digest TEXT,
    p_evidence_note TEXT,
    p_liability_posting_ids UUID[]
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    normalized_tax_type TEXT := btrim(coalesce(p_tax_type, ''));
    normalized_return_reference TEXT := btrim(coalesce(p_return_reference, ''));
    normalized_evidence_reference TEXT := btrim(coalesce(p_evidence_reference, ''));
    normalized_digest TEXT := lower(btrim(coalesce(p_evidence_digest, '')));
    normalized_note TEXT := btrim(coalesce(p_evidence_note, ''));
    normalized_due NUMERIC(18,2) := round(coalesce(p_declared_tax_due, -1), 2);
    normalized_posting_ids UUID[];
    existing accounting.v1_tax_return_evidence%ROWTYPE;
    existing_ids UUID[];
    valid_count INTEGER;
    expected_count INTEGER;
    liability_total NUMERIC(18,2);
    created_id UUID;
BEGIN
    PERFORM accounting.require_v1_tax_management_actor(
        p_actor_user_id,
        'accounting.tax.return_evidence.record'
    );

    SELECT array_agg(DISTINCT value ORDER BY value)
    INTO normalized_posting_ids
    FROM unnest(coalesce(p_liability_posting_ids, ARRAY[]::uuid[])) value;

    expected_count := coalesce(cardinality(normalized_posting_ids), 0);
    IF p_idempotency_key IS NULL
       OR normalized_tax_type NOT IN ('documentary_stamp_tax', 'percentage_tax_lending')
       OR p_return_period_start IS NULL
       OR p_return_period_end IS NULL
       OR p_return_period_end < p_return_period_start
       OR p_filing_date IS NULL
       OR p_filing_date < p_return_period_end
       OR p_declared_tax_due IS DISTINCT FROM normalized_due
       OR normalized_due <= 0
       OR normalized_return_reference = ''
       OR normalized_evidence_reference = ''
       OR normalized_digest !~ '^[0-9a-f]{64}$'
       OR length(normalized_note) < 20
       OR expected_count = 0 THEN
        RAISE EXCEPTION 'Tax return evidence requires exact period, filing, positive declared tax, retained references/digest/note, and at least one exact posted liability.';
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended('v1-tax-return:' || p_idempotency_key::text, 0));

    SELECT * INTO existing
    FROM accounting.v1_tax_return_evidence item
    WHERE item.idempotency_key = p_idempotency_key
    FOR SHARE;
    IF existing.id IS NOT NULL THEN
        SELECT array_agg(item.tax_liability_posting_id ORDER BY item.tax_liability_posting_id)
        INTO existing_ids
        FROM accounting.v1_tax_return_liability_items item
        WHERE item.tax_return_id = existing.id;

        IF existing.tax_type = normalized_tax_type
           AND existing.return_period_start = p_return_period_start
           AND existing.return_period_end = p_return_period_end
           AND existing.filing_date = p_filing_date
           AND existing.declared_tax_due = normalized_due
           AND existing.return_reference = normalized_return_reference
           AND existing.evidence_reference = normalized_evidence_reference
           AND existing.evidence_digest = normalized_digest
           AND existing.evidence_note = normalized_note
           AND existing.recorded_by_user_id = p_actor_user_id
           AND existing_ids IS NOT DISTINCT FROM normalized_posting_ids THEN
            RETURN existing.id;
        END IF;
        RAISE EXCEPTION 'Tax return evidence idempotency key already belongs to different immutable evidence.';
    END IF;

    SELECT
        count(*)::integer,
        coalesce(sum(posting.confirmed_tax_due), 0)::numeric(18,2)
    INTO valid_count, liability_total
    FROM accounting.v1_tax_liability_postings posting
    JOIN accounting.v1_tax_liability_preparations preparation
      ON preparation.id = posting.preparation_id
    JOIN accounting.journal_entries journal
      ON journal.id = posting.journal_entry_id
    JOIN accounting.v1_tax_liability_queue queue
      ON queue.tax_type = preparation.tax_type
     AND queue.evidence_id = preparation.evidence_id
     AND queue.posting_id = posting.id
    WHERE posting.id = ANY(normalized_posting_ids)
      AND preparation.tax_type = normalized_tax_type
      AND preparation.recognition_date BETWEEN p_return_period_start AND p_return_period_end
      AND journal.status = 'posted'
      AND journal.entry_number = posting.entry_number
      AND queue.accounting_status = 'posted';

    IF valid_count <> expected_count THEN
        RAISE EXCEPTION 'Tax return composition requires every selected liability to be exact, posted, current, same-tax-type evidence inside the declared return period.';
    END IF;
    IF liability_total <> normalized_due THEN
        RAISE EXCEPTION 'Declared tax due does not exactly reconcile to the selected immutable posted tax liabilities.';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM accounting.v1_tax_return_liability_items item
        WHERE item.tax_liability_posting_id = ANY(normalized_posting_ids)
    ) THEN
        RAISE EXCEPTION 'A selected tax liability is already assigned to another immutable tax return evidence record.';
    END IF;

    PERFORM set_config('accounting.v1_tax_return_evidence_insert_allowed', 'on', true);
    INSERT INTO accounting.v1_tax_return_evidence(
        idempotency_key, tax_type, return_period_start, return_period_end,
        filing_date, declared_tax_due, return_reference, evidence_reference,
        evidence_digest, evidence_note, recorded_by_user_id
    ) VALUES (
        p_idempotency_key, normalized_tax_type, p_return_period_start,
        p_return_period_end, p_filing_date, normalized_due,
        normalized_return_reference, normalized_evidence_reference,
        normalized_digest, normalized_note, p_actor_user_id
    ) RETURNING id INTO created_id;

    INSERT INTO accounting.v1_tax_return_liability_items(
        tax_return_id, tax_liability_posting_id, tax_type, evidence_id,
        recognition_date, tax_due, liability_entry_number
    )
    SELECT
        created_id, posting.id, preparation.tax_type, preparation.evidence_id,
        preparation.recognition_date, posting.confirmed_tax_due, posting.entry_number
    FROM accounting.v1_tax_liability_postings posting
    JOIN accounting.v1_tax_liability_preparations preparation
      ON preparation.id = posting.preparation_id
    WHERE posting.id = ANY(normalized_posting_ids)
    ORDER BY posting.id;
    PERFORM set_config('accounting.v1_tax_return_evidence_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.tax.return_evidence.recorded',
        'v1_tax_return',
        created_id,
        jsonb_build_object(
            'tax_type', normalized_tax_type,
            'return_period_start', p_return_period_start,
            'return_period_end', p_return_period_end,
            'filing_date', p_filing_date,
            'declared_tax_due', normalized_due,
            'liability_count', expected_count,
            'return_reference', normalized_return_reference,
            'evidence_digest', normalized_digest,
            'automatic_source_posting', false
        )
    );

    RETURN created_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.record_v1_tax_payment_evidence(
    p_actor_user_id UUID,
    p_idempotency_key UUID,
    p_tax_return_id UUID,
    p_payment_date DATE,
    p_payment_amount NUMERIC,
    p_cash_account_system_key TEXT,
    p_payment_reference TEXT,
    p_evidence_reference TEXT,
    p_evidence_digest TEXT,
    p_evidence_note TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    tax_return accounting.v1_tax_return_evidence%ROWTYPE;
    cash_account accounting.accounts%ROWTYPE;
    existing accounting.v1_tax_payment_evidence%ROWTYPE;
    normalized_amount NUMERIC(18,2) := round(coalesce(p_payment_amount, -1), 2);
    normalized_cash_key TEXT := btrim(coalesce(p_cash_account_system_key, ''));
    normalized_payment_reference TEXT := btrim(coalesce(p_payment_reference, ''));
    normalized_evidence_reference TEXT := btrim(coalesce(p_evidence_reference, ''));
    normalized_digest TEXT := lower(btrim(coalesce(p_evidence_digest, '')));
    normalized_note TEXT := btrim(coalesce(p_evidence_note, ''));
    created_id UUID;
BEGIN
    PERFORM accounting.require_v1_tax_management_actor(
        p_actor_user_id,
        'accounting.tax.payment_evidence.record'
    );

    IF p_idempotency_key IS NULL OR p_tax_return_id IS NULL OR p_payment_date IS NULL
       OR p_payment_amount IS DISTINCT FROM normalized_amount OR normalized_amount <= 0
       OR normalized_cash_key NOT IN ('cash_office', 'cash_bank_gcash')
       OR normalized_payment_reference = '' OR normalized_evidence_reference = ''
       OR normalized_digest !~ '^[0-9a-f]{64}$' OR length(normalized_note) < 20 THEN
        RAISE EXCEPTION 'Tax payment evidence requires exact return, date, amount, approved cash/bank account, retained references/digest and substantive note.';
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended('v1-tax-payment:' || p_idempotency_key::text, 0));

    SELECT * INTO tax_return
    FROM accounting.v1_tax_return_evidence item
    WHERE item.id = p_tax_return_id
    FOR SHARE;
    IF tax_return.id IS NULL THEN
        RAISE EXCEPTION 'Tax return evidence was not found for payment evidence.';
    END IF;
    IF p_payment_date < tax_return.filing_date THEN
        RAISE EXCEPTION 'Tax payment date cannot precede the retained filing date in the V1 full-settlement workflow.';
    END IF;
    IF normalized_amount <> tax_return.declared_tax_due THEN
        RAISE EXCEPTION 'V1 tax payment must exactly equal the retained declared tax due; partial payments require a later explicit policy.';
    END IF;

    SELECT * INTO cash_account
    FROM accounting.accounts account
    WHERE account.system_key = normalized_cash_key
    FOR SHARE;
    IF cash_account.id IS NULL OR cash_account.account_type <> 'asset'
       OR cash_account.normal_balance <> 'debit' OR NOT cash_account.is_active
       OR NOT cash_account.is_posting
       OR cash_account.code NOT IN ('1010', '1030') THEN
        RAISE EXCEPTION 'Tax payment requires exact active approved Cash - Office or Cash - Bank / GCash posting evidence.';
    END IF;

    SELECT * INTO existing
    FROM accounting.v1_tax_payment_evidence item
    WHERE item.idempotency_key = p_idempotency_key
    FOR SHARE;
    IF existing.id IS NOT NULL THEN
        IF existing.tax_return_id = p_tax_return_id
           AND existing.payment_date = p_payment_date
           AND existing.payment_amount = normalized_amount
           AND existing.cash_account_system_key = normalized_cash_key
           AND existing.payment_reference = normalized_payment_reference
           AND existing.evidence_reference = normalized_evidence_reference
           AND existing.evidence_digest = normalized_digest
           AND existing.evidence_note = normalized_note
           AND existing.recorded_by_user_id = p_actor_user_id THEN
            RETURN existing.id;
        END IF;
        RAISE EXCEPTION 'Tax payment evidence idempotency key already belongs to different immutable evidence.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM accounting.v1_tax_payment_evidence item
        WHERE item.tax_return_id = p_tax_return_id
    ) THEN
        RAISE EXCEPTION 'This tax return already has immutable V1 payment evidence; corrections require the protected tax adjustment/reversal workflow.';
    END IF;

    PERFORM set_config('accounting.v1_tax_payment_evidence_insert_allowed', 'on', true);
    INSERT INTO accounting.v1_tax_payment_evidence(
        idempotency_key, tax_return_id, payment_date, payment_amount,
        cash_account_system_key, payment_reference, evidence_reference,
        evidence_digest, evidence_note, recorded_by_user_id
    ) VALUES (
        p_idempotency_key, p_tax_return_id, p_payment_date, normalized_amount,
        normalized_cash_key, normalized_payment_reference,
        normalized_evidence_reference, normalized_digest, normalized_note,
        p_actor_user_id
    ) RETURNING id INTO created_id;
    PERFORM set_config('accounting.v1_tax_payment_evidence_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.tax.payment_evidence.recorded',
        'v1_tax_payment',
        created_id,
        jsonb_build_object(
            'tax_return_id', p_tax_return_id,
            'payment_date', p_payment_date,
            'payment_amount', normalized_amount,
            'cash_account_system_key', normalized_cash_key,
            'payment_reference', normalized_payment_reference,
            'evidence_digest', normalized_digest,
            'automatic_source_posting', false
        )
    );

    RETURN created_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.prepare_v1_tax_settlement_journal(
    p_payment_evidence_id UUID,
    p_actor_user_id UUID
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    payment accounting.v1_tax_payment_evidence%ROWTYPE;
    tax_return accounting.v1_tax_return_evidence%ROWTYPE;
    existing accounting.v1_tax_settlement_preparations%ROWTYPE;
    payable_account accounting.accounts%ROWTYPE;
    cash_account accounting.accounts%ROWTYPE;
    target_period accounting.fiscal_periods%ROWTYPE;
    item_count INTEGER;
    exact_count INTEGER;
    item_total NUMERIC(18,2);
    protected_source_event_key TEXT;
    created_journal_id UUID;
BEGIN
    PERFORM accounting.require_v1_tax_management_actor(
        p_actor_user_id,
        'accounting.tax.settlement.prepare'
    );
    IF p_payment_evidence_id IS NULL THEN
        RAISE EXCEPTION 'Tax settlement preparation requires exact payment evidence.';
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended('v1-tax-settlement:' || p_payment_evidence_id::text, 0));

    SELECT * INTO existing
    FROM accounting.v1_tax_settlement_preparations item
    WHERE item.payment_evidence_id = p_payment_evidence_id;
    IF existing.id IS NOT NULL THEN
        RETURN existing.journal_entry_id;
    END IF;

    SELECT * INTO payment
    FROM accounting.v1_tax_payment_evidence item
    WHERE item.id = p_payment_evidence_id
    FOR SHARE;
    IF payment.id IS NULL THEN
        RAISE EXCEPTION 'Tax payment evidence was not found.';
    END IF;
    SELECT * INTO tax_return
    FROM accounting.v1_tax_return_evidence item
    WHERE item.id = payment.tax_return_id
    FOR SHARE;
    IF tax_return.id IS NULL OR payment.payment_amount <> tax_return.declared_tax_due
       OR payment.payment_date < tax_return.filing_date THEN
        RAISE EXCEPTION 'Tax return/payment evidence no longer reconciles for protected settlement.';
    END IF;

    SELECT
        count(*)::integer,
        count(*) FILTER (
            WHERE posting.id IS NOT NULL
              AND preparation.tax_type = item.tax_type
              AND preparation.evidence_id = item.evidence_id
              AND preparation.recognition_date = item.recognition_date
              AND posting.confirmed_tax_due = item.tax_due
              AND posting.entry_number = item.liability_entry_number
              AND journal.status = 'posted'
              AND journal.entry_number = posting.entry_number
              AND queue.accounting_status = 'posted'
        )::integer,
        coalesce(sum(item.tax_due), 0)::numeric(18,2)
    INTO item_count, exact_count, item_total
    FROM accounting.v1_tax_return_liability_items item
    LEFT JOIN accounting.v1_tax_liability_postings posting
      ON posting.id = item.tax_liability_posting_id
    LEFT JOIN accounting.v1_tax_liability_preparations preparation
      ON preparation.id = posting.preparation_id
    LEFT JOIN accounting.journal_entries journal
      ON journal.id = posting.journal_entry_id
    LEFT JOIN accounting.v1_tax_liability_queue queue
      ON queue.tax_type = item.tax_type
     AND queue.evidence_id = item.evidence_id
     AND queue.posting_id = posting.id
    WHERE item.tax_return_id = tax_return.id;

    IF item_count <= 0 OR exact_count <> item_count OR item_total <> tax_return.declared_tax_due THEN
        RAISE EXCEPTION 'Tax settlement is blocked because retained return liabilities are missing, stale, reversed, superseded, or no longer exactly reconciled.';
    END IF;

    SELECT * INTO payable_account
    FROM accounting.accounts account
    WHERE account.system_key = 'tax_payables'
    FOR SHARE;
    SELECT * INTO cash_account
    FROM accounting.accounts account
    WHERE account.system_key = payment.cash_account_system_key
    FOR SHARE;
    IF payable_account.id IS NULL OR payable_account.code <> '2100'
       OR payable_account.account_type <> 'liability' OR payable_account.normal_balance <> 'credit'
       OR NOT payable_account.is_active OR NOT payable_account.is_posting THEN
        RAISE EXCEPTION 'Exact active 2100 Tax Payables is required for protected tax settlement.';
    END IF;
    IF cash_account.id IS NULL OR cash_account.system_key NOT IN ('cash_office', 'cash_bank_gcash')
       OR cash_account.code NOT IN ('1010', '1030') OR cash_account.account_type <> 'asset'
       OR cash_account.normal_balance <> 'debit' OR NOT cash_account.is_active OR NOT cash_account.is_posting THEN
        RAISE EXCEPTION 'Exact active approved Cash - Office or Cash - Bank / GCash account is required for protected tax settlement.';
    END IF;

    SELECT * INTO target_period
    FROM accounting.fiscal_periods period
    WHERE period.status = 'open'
      AND payment.payment_date BETWEEN period.start_date AND period.end_date
    ORDER BY period.start_date DESC
    LIMIT 1
    FOR SHARE;
    IF target_period.id IS NULL THEN
        RAISE EXCEPTION 'Tax settlement payment date must be inside an open accounting period.';
    END IF;

    protected_source_event_key := 'v1_tax_settlement:' || payment.id::text;
    IF EXISTS (
        SELECT 1 FROM accounting.journal_entries journal
        WHERE journal.source_event_key = protected_source_event_key
    ) THEN
        RAISE EXCEPTION 'Protected V1 tax settlement source identity is already occupied outside the settlement audit.';
    END IF;

    PERFORM set_config('accounting.v1_tax_settlement_journal_prepare_allowed', 'on', true);
    INSERT INTO accounting.journal_entries(
        fiscal_period_id, posting_date, description, status, source_type,
        source_reference, source_event_key, created_by_user_id, updated_at
    ) VALUES (
        target_period.id, payment.payment_date,
        'Tax settlement for retained return ' || tax_return.return_reference,
        'draft', 'v1_tax_settlement', payment.id::text,
        protected_source_event_key, p_actor_user_id, now()
    ) RETURNING id INTO created_journal_id;
    PERFORM set_config('accounting.v1_tax_settlement_journal_prepare_allowed', 'off', true);

    PERFORM set_config('accounting.v1_tax_settlement_journal_line_write_allowed', 'on', true);
    INSERT INTO accounting.journal_lines(
        journal_entry_id, line_number, account_id, description, debit, credit
    ) VALUES
        (created_journal_id, 1, payable_account.id, 'Settle retained tax payable', payment.payment_amount, 0),
        (created_journal_id, 2, cash_account.id, 'Tax payment from ' || cash_account.name, 0, payment.payment_amount);
    PERFORM set_config('accounting.v1_tax_settlement_journal_line_write_allowed', 'off', true);

    INSERT INTO accounting.journal_events(journal_entry_id, event_type, actor_user_id, details)
    VALUES (
        created_journal_id, 'draft_created', p_actor_user_id,
        jsonb_build_object(
            'source_type', 'v1_tax_settlement',
            'tax_return_id', tax_return.id,
            'payment_evidence_id', payment.id,
            'payment_amount', payment.payment_amount,
            'tax_payable_account_code', payable_account.code,
            'cash_account_code', cash_account.code,
            'return_evidence_digest', tax_return.evidence_digest,
            'payment_evidence_digest', payment.evidence_digest,
            'automatic_source_posting', false
        )
    );

    PERFORM set_config('accounting.v1_tax_settlement_preparation_insert_allowed', 'on', true);
    INSERT INTO accounting.v1_tax_settlement_preparations(
        payment_evidence_id, tax_return_id, journal_entry_id, source_event_key,
        payment_date, payment_amount, payment_evidence_digest,
        return_evidence_digest, tax_payable_account_id, cash_account_id,
        fiscal_period_id, prepared_by_user_id
    ) VALUES (
        payment.id, tax_return.id, created_journal_id, protected_source_event_key,
        payment.payment_date, payment.payment_amount, payment.evidence_digest,
        tax_return.evidence_digest, payable_account.id, cash_account.id,
        target_period.id, p_actor_user_id
    );
    PERFORM set_config('accounting.v1_tax_settlement_preparation_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id, 'accounting.tax.settlement.prepared',
        'v1_tax_payment', payment.id,
        jsonb_build_object(
            'tax_return_id', tax_return.id,
            'journal_entry_id', created_journal_id,
            'payment_date', payment.payment_date,
            'payment_amount', payment.payment_amount,
            'tax_payable_account_code', payable_account.code,
            'cash_account_code', cash_account.code,
            'automatic_source_posting', false
        )
    );

    RETURN created_journal_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.post_v1_tax_settlement_journal(
    p_payment_evidence_id UUID,
    p_actor_user_id UUID,
    p_confirmation_token TEXT,
    p_expected_return_evidence_digest TEXT,
    p_expected_payment_evidence_digest TEXT,
    p_expected_payment_amount NUMERIC,
    p_expected_tax_payable_account_code TEXT,
    p_expected_cash_account_code TEXT,
    p_expected_posting_date DATE,
    p_expected_fiscal_period_id UUID,
    p_policy_version TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    normalized_token TEXT := lower(btrim(coalesce(p_confirmation_token, '')));
    normalized_return_digest TEXT := lower(btrim(coalesce(p_expected_return_evidence_digest, '')));
    normalized_payment_digest TEXT := lower(btrim(coalesce(p_expected_payment_evidence_digest, '')));
    normalized_amount NUMERIC(18,2) := round(coalesce(p_expected_payment_amount, -1), 2);
    normalized_payable_code TEXT := btrim(coalesce(p_expected_tax_payable_account_code, ''));
    normalized_cash_code TEXT := btrim(coalesce(p_expected_cash_account_code, ''));
    preparation accounting.v1_tax_settlement_preparations%ROWTYPE;
    existing accounting.v1_tax_settlement_postings%ROWTYPE;
    payment accounting.v1_tax_payment_evidence%ROWTYPE;
    tax_return accounting.v1_tax_return_evidence%ROWTYPE;
    payable_account accounting.accounts%ROWTYPE;
    cash_account accounting.accounts%ROWTYPE;
    target_period accounting.fiscal_periods%ROWTYPE;
    journal accounting.journal_entries%ROWTYPE;
    item_count INTEGER;
    exact_count INTEGER;
    item_total NUMERIC(18,2);
    line_count INTEGER;
    total_debit NUMERIC(18,2);
    total_credit NUMERIC(18,2);
    payable_debit NUMERIC(18,2);
    cash_credit NUMERIC(18,2);
    foreign_line_count INTEGER;
    generated_entry_number TEXT;
    confirmation_digest_value TEXT;
    created_posting_id UUID;
BEGIN
    PERFORM accounting.require_v1_tax_management_actor(
        p_actor_user_id,
        'accounting.tax.settlement.post'
    );
    IF p_payment_evidence_id IS NULL
       OR p_policy_version IS DISTINCT FROM 'v1_tax_settlement_posting_v1'
       OR normalized_token !~ '^[0-9a-f]{64}$'
       OR normalized_return_digest !~ '^[0-9a-f]{64}$'
       OR normalized_payment_digest !~ '^[0-9a-f]{64}$'
       OR p_expected_payment_amount IS DISTINCT FROM normalized_amount
       OR normalized_amount <= 0
       OR normalized_payable_code = '' OR normalized_cash_code = ''
       OR p_expected_posting_date IS NULL OR p_expected_fiscal_period_id IS NULL THEN
        RAISE EXCEPTION 'Protected tax settlement posting requires exact Management confirmation, evidence digests, amount, accounts, date, period and policy.';
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended('v1-tax-settlement:' || p_payment_evidence_id::text, 0));

    SELECT * INTO preparation
    FROM accounting.v1_tax_settlement_preparations item
    WHERE item.payment_evidence_id = p_payment_evidence_id
    FOR SHARE;
    IF preparation.id IS NULL THEN
        RAISE EXCEPTION 'Tax settlement must be prepared from exact payment evidence before posting.';
    END IF;

    SELECT * INTO existing
    FROM accounting.v1_tax_settlement_postings item
    WHERE item.preparation_id = preparation.id
    FOR SHARE;
    IF existing.id IS NOT NULL THEN
        IF existing.confirmation_token = normalized_token
           AND existing.confirmed_return_evidence_digest = normalized_return_digest
           AND existing.confirmed_payment_evidence_digest = normalized_payment_digest
           AND existing.confirmed_payment_amount = normalized_amount
           AND existing.confirmed_posting_date = p_expected_posting_date
           AND existing.confirmed_fiscal_period_id = p_expected_fiscal_period_id
           AND existing.policy_version = p_policy_version
           AND existing.posted_by_user_id = p_actor_user_id
           AND EXISTS (
                SELECT 1 FROM accounting.accounts account
                WHERE account.id = existing.confirmed_tax_payable_account_id
                  AND account.code = normalized_payable_code
           )
           AND EXISTS (
                SELECT 1 FROM accounting.accounts account
                WHERE account.id = existing.confirmed_cash_account_id
                  AND account.code = normalized_cash_code
           ) THEN
            RETURN existing.id;
        END IF;
        RAISE EXCEPTION 'Existing V1 tax settlement posting does not match the immutable retry identity.';
    END IF;

    SELECT * INTO payment
    FROM accounting.v1_tax_payment_evidence item
    WHERE item.id = p_payment_evidence_id
    FOR SHARE;
    SELECT * INTO tax_return
    FROM accounting.v1_tax_return_evidence item
    WHERE item.id = payment.tax_return_id
    FOR SHARE;
    IF payment.id IS NULL OR tax_return.id IS NULL
       OR payment.tax_return_id <> preparation.tax_return_id
       OR payment.payment_amount <> tax_return.declared_tax_due
       OR payment.payment_amount <> normalized_amount
       OR payment.payment_date <> p_expected_posting_date
       OR payment.evidence_digest <> normalized_payment_digest
       OR tax_return.evidence_digest <> normalized_return_digest
       OR preparation.payment_evidence_digest <> normalized_payment_digest
       OR preparation.return_evidence_digest <> normalized_return_digest
       OR preparation.payment_amount <> normalized_amount
       OR preparation.payment_date <> p_expected_posting_date THEN
        RAISE EXCEPTION 'Exact V1 tax return/payment evidence no longer matches the confirmed settlement coordinates.';
    END IF;

    SELECT
        count(*)::integer,
        count(*) FILTER (
            WHERE posting.id IS NOT NULL
              AND preparation_row.tax_type = item.tax_type
              AND preparation_row.evidence_id = item.evidence_id
              AND preparation_row.recognition_date = item.recognition_date
              AND posting.confirmed_tax_due = item.tax_due
              AND posting.entry_number = item.liability_entry_number
              AND liability_journal.status = 'posted'
              AND liability_journal.entry_number = posting.entry_number
              AND queue.accounting_status = 'posted'
        )::integer,
        coalesce(sum(item.tax_due), 0)::numeric(18,2)
    INTO item_count, exact_count, item_total
    FROM accounting.v1_tax_return_liability_items item
    LEFT JOIN accounting.v1_tax_liability_postings posting
      ON posting.id = item.tax_liability_posting_id
    LEFT JOIN accounting.v1_tax_liability_preparations preparation_row
      ON preparation_row.id = posting.preparation_id
    LEFT JOIN accounting.journal_entries liability_journal
      ON liability_journal.id = posting.journal_entry_id
    LEFT JOIN accounting.v1_tax_liability_queue queue
      ON queue.tax_type = item.tax_type
     AND queue.evidence_id = item.evidence_id
     AND queue.posting_id = posting.id
    WHERE item.tax_return_id = tax_return.id;
    IF item_count <= 0 OR exact_count <> item_count OR item_total <> normalized_amount THEN
        RAISE EXCEPTION 'Tax settlement posting is blocked because retained return liabilities are no longer exact current posted liabilities.';
    END IF;

    SELECT * INTO payable_account
    FROM accounting.accounts account
    WHERE account.id = preparation.tax_payable_account_id
    FOR SHARE;
    SELECT * INTO cash_account
    FROM accounting.accounts account
    WHERE account.id = preparation.cash_account_id
    FOR SHARE;
    IF payable_account.id IS NULL OR payable_account.system_key <> 'tax_payables'
       OR payable_account.code <> '2100' OR payable_account.code <> normalized_payable_code
       OR payable_account.account_type <> 'liability' OR payable_account.normal_balance <> 'credit'
       OR NOT payable_account.is_active OR NOT payable_account.is_posting THEN
        RAISE EXCEPTION 'Exact 2100 Tax Payables changed after settlement preparation.';
    END IF;
    IF cash_account.id IS NULL OR cash_account.system_key <> payment.cash_account_system_key
       OR cash_account.system_key NOT IN ('cash_office', 'cash_bank_gcash')
       OR cash_account.code NOT IN ('1010', '1030') OR cash_account.code <> normalized_cash_code
       OR cash_account.account_type <> 'asset' OR cash_account.normal_balance <> 'debit'
       OR NOT cash_account.is_active OR NOT cash_account.is_posting THEN
        RAISE EXCEPTION 'Exact approved tax-payment cash/bank account changed after settlement preparation.';
    END IF;

    SELECT * INTO target_period
    FROM accounting.fiscal_periods period
    WHERE period.id = p_expected_fiscal_period_id
    FOR SHARE;
    IF target_period.id IS NULL OR target_period.status <> 'open'
       OR p_expected_posting_date NOT BETWEEN target_period.start_date AND target_period.end_date
       OR preparation.fiscal_period_id <> target_period.id THEN
        RAISE EXCEPTION 'Tax settlement posting requires the exact still-open fiscal period used at preparation.';
    END IF;

    SELECT * INTO journal
    FROM accounting.journal_entries item
    WHERE item.id = preparation.journal_entry_id
    FOR UPDATE;
    IF journal.id IS NULL OR journal.status <> 'draft'
       OR journal.source_type <> 'v1_tax_settlement'
       OR journal.source_reference <> payment.id::text
       OR journal.source_event_key <> preparation.source_event_key
       OR journal.posting_date <> p_expected_posting_date
       OR journal.fiscal_period_id <> target_period.id THEN
        RAISE EXCEPTION 'Prepared V1 tax settlement General Journal draft no longer matches the protected payment coordinates.';
    END IF;

    SELECT
        count(*)::integer,
        coalesce(sum(line.debit), 0)::numeric(18,2),
        coalesce(sum(line.credit), 0)::numeric(18,2),
        coalesce(sum(line.debit) FILTER (WHERE line.account_id = payable_account.id), 0)::numeric(18,2),
        coalesce(sum(line.credit) FILTER (WHERE line.account_id = cash_account.id), 0)::numeric(18,2),
        count(*) FILTER (WHERE line.account_id NOT IN (payable_account.id, cash_account.id))::integer
    INTO line_count, total_debit, total_credit, payable_debit, cash_credit, foreign_line_count
    FROM accounting.journal_lines line
    WHERE line.journal_entry_id = journal.id;
    IF line_count <> 2 OR total_debit <> normalized_amount OR total_credit <> normalized_amount
       OR payable_debit <> normalized_amount OR cash_credit <> normalized_amount
       OR foreign_line_count <> 0 THEN
        RAISE EXCEPTION 'Prepared V1 tax settlement lines do not exactly reconcile Dr 2100 Tax Payables / Cr approved cash-bank account to retained payment evidence.';
    END IF;

    confirmation_digest_value := encode(sha256(convert_to(concat_ws('|',
        p_policy_version, payment.id::text, tax_return.id::text,
        normalized_return_digest, normalized_payment_digest,
        to_char(normalized_amount, 'FM999999999999990.00'),
        payable_account.id::text, cash_account.id::text,
        p_expected_posting_date::text, target_period.id::text,
        journal.id::text, normalized_token
    ), 'UTF8')), 'hex');

    PERFORM set_config('accounting.v1_tax_settlement_journal_post_allowed', 'on', true);
    generated_entry_number := accounting.post_journal_entry(journal.id, p_actor_user_id);
    PERFORM set_config('accounting.v1_tax_settlement_journal_post_allowed', 'off', true);

    IF coalesce(current_setting('accounting.v1_tax_settlement_force_audit_failure', true), '') = 'on' THEN
        RAISE EXCEPTION 'Forced V1 tax settlement audit failure.';
    END IF;

    PERFORM set_config('accounting.v1_tax_settlement_posting_insert_allowed', 'on', true);
    INSERT INTO accounting.v1_tax_settlement_postings(
        preparation_id, payment_evidence_id, tax_return_id, journal_entry_id,
        entry_number, confirmation_token, confirmation_digest,
        confirmed_return_evidence_digest, confirmed_payment_evidence_digest,
        confirmed_payment_amount, confirmed_tax_payable_account_id,
        confirmed_cash_account_id, confirmed_posting_date,
        confirmed_fiscal_period_id, policy_version, posted_by_user_id
    ) VALUES (
        preparation.id, payment.id, tax_return.id, journal.id,
        generated_entry_number, normalized_token, confirmation_digest_value,
        normalized_return_digest, normalized_payment_digest, normalized_amount,
        payable_account.id, cash_account.id, p_expected_posting_date,
        target_period.id, p_policy_version, p_actor_user_id
    ) RETURNING id INTO created_posting_id;
    PERFORM set_config('accounting.v1_tax_settlement_posting_insert_allowed', 'off', true);

    INSERT INTO accounting.journal_events(journal_entry_id, event_type, actor_user_id, details)
    VALUES (
        journal.id, 'posted', p_actor_user_id,
        jsonb_build_object(
            'entry_number', generated_entry_number,
            'source_type', 'v1_tax_settlement',
            'tax_return_id', tax_return.id,
            'payment_evidence_id', payment.id,
            'confirmation_digest', confirmation_digest_value,
            'automatic_source_posting', false
        )
    );

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id, 'accounting.tax.settlement.posted',
        'v1_tax_payment', payment.id,
        jsonb_build_object(
            'tax_return_id', tax_return.id,
            'journal_entry_id', journal.id,
            'entry_number', generated_entry_number,
            'payment_amount', normalized_amount,
            'tax_payable_account_code', payable_account.code,
            'cash_account_code', cash_account.code,
            'confirmation_digest', confirmation_digest_value,
            'automatic_source_posting', false
        )
    );

    RETURN created_posting_id;
END;
$$;

CREATE OR REPLACE VIEW accounting.v1_tax_settlement_queue AS
SELECT
    tax_return.id AS tax_return_id,
    tax_return.tax_type,
    tax_return.return_period_start,
    tax_return.return_period_end,
    tax_return.filing_date,
    tax_return.declared_tax_due,
    tax_return.return_reference,
    tax_return.evidence_reference AS return_evidence_reference,
    tax_return.evidence_digest AS return_evidence_digest,
    tax_return.recorded_by_user_id AS return_recorded_by_user_id,
    tax_return.recorded_at AS return_recorded_at,
    composition.liability_count,
    composition.current_exact_count,
    composition.liability_total,
    payment.id AS payment_evidence_id,
    payment.payment_date,
    payment.payment_amount,
    payment.cash_account_system_key,
    cash.code AS cash_account_code,
    cash.name AS cash_account_name,
    payment.payment_reference,
    payment.evidence_reference AS payment_evidence_reference,
    payment.evidence_digest AS payment_evidence_digest,
    payment.recorded_by_user_id AS payment_recorded_by_user_id,
    payment.recorded_at AS payment_recorded_at,
    preparation.id AS preparation_id,
    preparation.journal_entry_id,
    journal.status AS journal_status,
    journal.entry_number,
    preparation.fiscal_period_id,
    preparation.prepared_by_user_id,
    preparation.prepared_at,
    posting.id AS settlement_posting_id,
    posting.confirmation_digest,
    posting.posted_by_user_id,
    posting.posted_at,
    CASE
        WHEN posting.id IS NOT NULL
             AND composition.current_exact_count <> composition.liability_count
            THEN 'settled_adjustment_review_required'
        WHEN posting.id IS NOT NULL THEN 'settled'
        WHEN composition.liability_count <= 0
          OR composition.current_exact_count <> composition.liability_count
          OR composition.liability_total <> tax_return.declared_tax_due
            THEN 'blocked_return_composition_changed'
        WHEN payment.id IS NULL THEN 'return_recorded_awaiting_payment'
        WHEN payment.payment_amount <> tax_return.declared_tax_due
            THEN 'blocked_payment_amount_mismatch'
        WHEN payment.payment_date < tax_return.filing_date
            THEN 'blocked_payment_date'
        WHEN cash.id IS NULL OR NOT cash.is_active OR NOT cash.is_posting
          OR cash.system_key NOT IN ('cash_office', 'cash_bank_gcash')
          OR cash.code NOT IN ('1010', '1030')
            THEN 'blocked_cash_account'
        WHEN preparation.id IS NOT NULL AND journal.status IS DISTINCT FROM 'draft'
            THEN 'blocked_untracked_settlement_journal_state'
        WHEN preparation.id IS NOT NULL AND open_period.id IS NULL
            THEN 'prepared_blocked_period_revalidation'
        WHEN preparation.id IS NOT NULL THEN 'settlement_prepared'
        WHEN open_period.id IS NULL THEN 'blocked_no_open_payment_period'
        ELSE 'payment_evidence_ready'
    END AS settlement_status,
    CASE
        WHEN posting.id IS NOT NULL
             AND composition.current_exact_count <> composition.liability_count
            THEN 'Settled return contains a liability that is no longer current; protected tax adjustment/reversal review is required.'
        WHEN posting.id IS NOT NULL THEN NULL
        WHEN composition.liability_count <= 0
          OR composition.current_exact_count <> composition.liability_count
          OR composition.liability_total <> tax_return.declared_tax_due
            THEN 'Retained return composition no longer exactly matches current protected posted tax liabilities.'
        WHEN payment.id IS NULL
            THEN 'Retained payment evidence is required before settlement preparation.'
        WHEN payment.payment_amount <> tax_return.declared_tax_due
            THEN 'Payment evidence no longer exactly equals declared tax due.'
        WHEN payment.payment_date < tax_return.filing_date
            THEN 'Payment evidence predates retained filing evidence.'
        WHEN cash.id IS NULL OR NOT cash.is_active OR NOT cash.is_posting
          OR cash.system_key NOT IN ('cash_office', 'cash_bank_gcash')
          OR cash.code NOT IN ('1010', '1030')
            THEN 'Exact payment cash/bank account is no longer posting-ready.'
        WHEN preparation.id IS NOT NULL AND journal.status IS DISTINCT FROM 'draft'
            THEN 'Prepared settlement journal is not a draft but has no immutable protected posting audit.'
        WHEN preparation.id IS NOT NULL AND open_period.id IS NULL
            THEN 'Prepared payment date is no longer inside the exact still-open fiscal period.'
        WHEN preparation.id IS NOT NULL
            THEN 'Exact Management confirmation is required before protected settlement posting.'
        WHEN open_period.id IS NULL
            THEN 'Payment date is not inside an open accounting period.'
        ELSE NULL
    END AS settlement_blocker,
    true AS tax_settlement_enabled,
    false AS tax_adjustment_reversal_enabled,
    false AS automatic_source_posting
FROM accounting.v1_tax_return_evidence tax_return
LEFT JOIN LATERAL (
    SELECT
        count(*)::integer AS liability_count,
        count(*) FILTER (
            WHERE posting.id IS NOT NULL
              AND preparation_row.tax_type = item.tax_type
              AND preparation_row.evidence_id = item.evidence_id
              AND preparation_row.recognition_date = item.recognition_date
              AND posting.confirmed_tax_due = item.tax_due
              AND posting.entry_number = item.liability_entry_number
              AND liability_journal.status = 'posted'
              AND liability_journal.entry_number = posting.entry_number
              AND queue.accounting_status = 'posted'
        )::integer AS current_exact_count,
        coalesce(sum(item.tax_due), 0)::numeric(18,2) AS liability_total
    FROM accounting.v1_tax_return_liability_items item
    LEFT JOIN accounting.v1_tax_liability_postings posting
      ON posting.id = item.tax_liability_posting_id
    LEFT JOIN accounting.v1_tax_liability_preparations preparation_row
      ON preparation_row.id = posting.preparation_id
    LEFT JOIN accounting.journal_entries liability_journal
      ON liability_journal.id = posting.journal_entry_id
    LEFT JOIN accounting.v1_tax_liability_queue queue
      ON queue.tax_type = item.tax_type
     AND queue.evidence_id = item.evidence_id
     AND queue.posting_id = posting.id
    WHERE item.tax_return_id = tax_return.id
) composition ON true
LEFT JOIN accounting.v1_tax_payment_evidence payment
  ON payment.tax_return_id = tax_return.id
LEFT JOIN accounting.accounts cash
  ON cash.system_key = payment.cash_account_system_key
LEFT JOIN accounting.v1_tax_settlement_preparations preparation
  ON preparation.tax_return_id = tax_return.id
LEFT JOIN accounting.journal_entries journal
  ON journal.id = preparation.journal_entry_id
LEFT JOIN accounting.v1_tax_settlement_postings posting
  ON posting.preparation_id = preparation.id
LEFT JOIN LATERAL (
    SELECT period.id
    FROM accounting.fiscal_periods period
    WHERE period.status = 'open'
      AND payment.payment_date BETWEEN period.start_date AND period.end_date
      AND (preparation.fiscal_period_id IS NULL OR preparation.fiscal_period_id = period.id)
    ORDER BY period.start_date DESC
    LIMIT 1
) open_period ON true;

CREATE OR REPLACE VIEW accounting.v1_tax_settlement_summary AS
SELECT
    count(*)::bigint AS return_count,
    count(*) FILTER (WHERE settlement_status = 'return_recorded_awaiting_payment')::bigint AS awaiting_payment_evidence_count,
    count(*) FILTER (WHERE settlement_status = 'payment_evidence_ready')::bigint AS ready_to_prepare_count,
    count(*) FILTER (WHERE settlement_status = 'settlement_prepared')::bigint AS prepared_count,
    count(*) FILTER (WHERE settlement_status = 'settled')::bigint AS settled_count,
    count(*) FILTER (WHERE settlement_status = 'settled_adjustment_review_required')::bigint AS settled_adjustment_review_count,
    count(*) FILTER (WHERE settlement_status LIKE 'blocked_%' OR settlement_status LIKE 'prepared_blocked_%')::bigint AS blocked_count,
    coalesce(sum(payment_amount) FILTER (WHERE settlement_status = 'settled'), 0)::numeric(18,2) AS settled_tax_total,
    true AS tax_settlement_enabled,
    false AS tax_adjustment_reversal_enabled,
    false AS automatic_source_posting
FROM accounting.v1_tax_settlement_queue;

COMMENT ON TABLE accounting.v1_tax_return_evidence IS
'Immutable Management-approved tax return/filing evidence. Each return is composed only of exact current protected posted V1 tax liabilities and never posts automatically.';
COMMENT ON TABLE accounting.v1_tax_payment_evidence IS
'Immutable retained V1 tax payment evidence for one exact tax return. V1 requires full payment and an approved real Cash - Office or Cash - Bank / GCash account.';
COMMENT ON TABLE accounting.v1_tax_settlement_postings IS
'Immutable protected settlement audit for Dr 2100 Tax Payables / Cr exact approved cash-bank account; settlement remains separate from tax expense recognition.';

COMMIT;