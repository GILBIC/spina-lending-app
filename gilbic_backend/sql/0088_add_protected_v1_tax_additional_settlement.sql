BEGIN;

-- Master #296 A6.2 additional-tax payment/settlement sub-slice.
-- This migration consumes an already-posted protected additional-tax liability from
-- 0087, then requires separate immutable Management payment evidence before creating
-- one protected settlement journal: Dr 2100 Tax Payables / Cr approved 1010 or 1030.
-- It never treats an amended return/assessment as proof of payment, never clears Tax
-- Recoverable, never infers partial payment, and never enables automatic source posting.

INSERT INTO core.permissions (code, description)
VALUES
    ('accounting.tax.additional_payment_evidence.record', 'Record immutable Management-approved payment evidence for one posted V1 additional-tax amendment liability'),
    ('accounting.tax.additional_settlement.prepare', 'Prepare a protected V1 additional-tax settlement General Journal draft from exact amendment/payment evidence'),
    ('accounting.tax.additional_settlement.post', 'Post a protected V1 additional-tax settlement General Journal after exact Management confirmation')
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code IN (
      'accounting.tax.additional_payment_evidence.record',
      'accounting.tax.additional_settlement.prepare',
      'accounting.tax.additional_settlement.post'
  )
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.v1_tax_additional_payment_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key UUID NOT NULL UNIQUE,
    amendment_evidence_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_additional_amendment_evidence(id) ON DELETE RESTRICT,
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

CREATE INDEX IF NOT EXISTS v1_tax_additional_payment_date_idx
    ON accounting.v1_tax_additional_payment_evidence(payment_date DESC, recorded_at DESC);

CREATE TABLE IF NOT EXISTS accounting.v1_tax_additional_settlement_preparations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_evidence_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_additional_payment_evidence(id) ON DELETE RESTRICT,
    amendment_evidence_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_additional_amendment_evidence(id) ON DELETE RESTRICT,
    additional_liability_posting_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_additional_liability_postings(id) ON DELETE RESTRICT,
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    source_event_key TEXT NOT NULL UNIQUE CHECK (btrim(source_event_key) <> ''),
    payment_date DATE NOT NULL,
    payment_amount NUMERIC(18,2) NOT NULL CHECK (payment_amount > 0),
    amendment_evidence_digest TEXT NOT NULL CHECK (amendment_evidence_digest ~ '^[0-9a-f]{64}$'),
    additional_liability_confirmation_digest TEXT NOT NULL CHECK (additional_liability_confirmation_digest ~ '^[0-9a-f]{64}$'),
    payment_evidence_digest TEXT NOT NULL CHECK (payment_evidence_digest ~ '^[0-9a-f]{64}$'),
    tax_payable_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    cash_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    fiscal_period_id UUID NOT NULL REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    prepared_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    prepared_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS accounting.v1_tax_additional_settlement_postings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    preparation_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_additional_settlement_preparations(id) ON DELETE RESTRICT,
    payment_evidence_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_additional_payment_evidence(id) ON DELETE RESTRICT,
    amendment_evidence_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_additional_amendment_evidence(id) ON DELETE RESTRICT,
    additional_liability_posting_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_additional_liability_postings(id) ON DELETE RESTRICT,
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    entry_number TEXT NOT NULL UNIQUE CHECK (btrim(entry_number) <> ''),
    confirmation_token TEXT NOT NULL CHECK (confirmation_token ~ '^[0-9a-f]{64}$'),
    confirmation_digest TEXT NOT NULL CHECK (confirmation_digest ~ '^[0-9a-f]{64}$'),
    confirmed_amendment_evidence_digest TEXT NOT NULL CHECK (confirmed_amendment_evidence_digest ~ '^[0-9a-f]{64}$'),
    confirmed_additional_liability_confirmation_digest TEXT NOT NULL CHECK (confirmed_additional_liability_confirmation_digest ~ '^[0-9a-f]{64}$'),
    confirmed_payment_evidence_digest TEXT NOT NULL CHECK (confirmed_payment_evidence_digest ~ '^[0-9a-f]{64}$'),
    confirmed_payment_amount NUMERIC(18,2) NOT NULL CHECK (confirmed_payment_amount > 0),
    confirmed_tax_payable_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    confirmed_cash_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    confirmed_posting_date DATE NOT NULL,
    confirmed_fiscal_period_id UUID NOT NULL REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    policy_version TEXT NOT NULL CHECK (policy_version = 'v1_tax_additional_settlement_posting_v1'),
    posted_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    posted_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE OR REPLACE FUNCTION accounting.guard_v1_tax_additional_settlement_immutable_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    insert_allowed BOOLEAN := false;
BEGIN
    IF TG_TABLE_NAME = 'v1_tax_additional_payment_evidence' THEN
        insert_allowed := coalesce(current_setting('accounting.v1_tax_additional_payment_evidence_insert_allowed', true), '') = 'on';
    ELSIF TG_TABLE_NAME = 'v1_tax_additional_settlement_preparations' THEN
        insert_allowed := coalesce(current_setting('accounting.v1_tax_additional_settlement_preparation_insert_allowed', true), '') = 'on';
    ELSIF TG_TABLE_NAME = 'v1_tax_additional_settlement_postings' THEN
        insert_allowed := coalesce(current_setting('accounting.v1_tax_additional_settlement_posting_insert_allowed', true), '') = 'on';
    END IF;

    IF TG_OP = 'INSERT' AND insert_allowed THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'V1 additional-tax payment/settlement evidence and audit rows are immutable and must use the protected Management workflow.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_v1_tax_additional_payment_evidence_guard
    ON accounting.v1_tax_additional_payment_evidence;
CREATE TRIGGER accounting_v1_tax_additional_payment_evidence_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.v1_tax_additional_payment_evidence
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_additional_settlement_immutable_write();

DROP TRIGGER IF EXISTS accounting_v1_tax_additional_settlement_preparation_guard
    ON accounting.v1_tax_additional_settlement_preparations;
CREATE TRIGGER accounting_v1_tax_additional_settlement_preparation_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.v1_tax_additional_settlement_preparations
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_additional_settlement_immutable_write();

DROP TRIGGER IF EXISTS accounting_v1_tax_additional_settlement_posting_guard
    ON accounting.v1_tax_additional_settlement_postings;
CREATE TRIGGER accounting_v1_tax_additional_settlement_posting_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.v1_tax_additional_settlement_postings
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_additional_settlement_immutable_write();

CREATE OR REPLACE FUNCTION accounting.guard_v1_tax_additional_settlement_journal_entry_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    reversed_source TEXT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF (
            NEW.source_type = 'v1_tax_additional_settlement'
            OR coalesce(NEW.source_event_key, '') LIKE 'v1_tax_additional_settlement:%'
        )
        AND coalesce(current_setting('accounting.v1_tax_additional_settlement_journal_prepare_allowed', true), '') <> 'on' THEN
            RAISE EXCEPTION 'V1 additional-tax settlement journals must use the protected Management settlement preparation function.';
        END IF;

        IF NEW.reversal_of_entry_id IS NOT NULL THEN
            SELECT item.source_type INTO reversed_source
            FROM accounting.journal_entries item
            WHERE item.id = NEW.reversal_of_entry_id;
            IF reversed_source = 'v1_tax_additional_settlement' THEN
                RAISE EXCEPTION 'Posted V1 additional-tax settlements cannot be reversed through the manual General Journal; new protected evidence is required.';
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.source_type IS DISTINCT FROM 'v1_tax_additional_settlement' THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'V1 additional-tax settlement journals are immutable and cannot be deleted.';
    END IF;

    IF OLD.status = 'draft' AND NEW.status = 'posted' THEN
        IF coalesce(current_setting('accounting.v1_tax_additional_settlement_journal_post_allowed', true), '') <> 'on' THEN
            RAISE EXCEPTION 'V1 additional-tax settlement journals require the protected Management settlement posting function.';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'V1 additional-tax settlement journals are system generated and immutable.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_v1_tax_additional_settlement_journal_entry_guard
    ON accounting.journal_entries;
CREATE TRIGGER accounting_v1_tax_additional_settlement_journal_entry_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_additional_settlement_journal_entry_change();

CREATE OR REPLACE FUNCTION accounting.guard_v1_tax_additional_settlement_journal_line_change()
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

    IF target_source_type = 'v1_tax_additional_settlement'
       AND coalesce(current_setting('accounting.v1_tax_additional_settlement_journal_line_write_allowed', true), '') <> 'on' THEN
        RAISE EXCEPTION 'V1 additional-tax settlement journal lines are system generated and immutable.';
    END IF;

    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_v1_tax_additional_settlement_journal_line_guard
    ON accounting.journal_lines;
CREATE TRIGGER accounting_v1_tax_additional_settlement_journal_line_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_lines
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_additional_settlement_journal_line_change();

CREATE OR REPLACE FUNCTION accounting.record_v1_tax_additional_payment_evidence(
    p_actor_user_id UUID,
    p_idempotency_key UUID,
    p_amendment_evidence_id UUID,
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
    evidence accounting.v1_tax_additional_amendment_evidence%ROWTYPE;
    liability_preparation accounting.v1_tax_additional_liability_preparations%ROWTYPE;
    liability_posting accounting.v1_tax_additional_liability_postings%ROWTYPE;
    liability_journal accounting.journal_entries%ROWTYPE;
    original_queue accounting.v1_tax_liability_queue%ROWTYPE;
    replacement_queue accounting.v1_tax_liability_queue%ROWTYPE;
    original_payment accounting.v1_tax_payment_evidence%ROWTYPE;
    original_settlement accounting.v1_tax_settlement_postings%ROWTYPE;
    original_settlement_journal accounting.journal_entries%ROWTYPE;
    cash_account accounting.accounts%ROWTYPE;
    existing accounting.v1_tax_additional_payment_evidence%ROWTYPE;
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
        'accounting.tax.additional_payment_evidence.record'
    );

    IF p_idempotency_key IS NULL OR p_amendment_evidence_id IS NULL
       OR p_payment_date IS NULL
       OR p_payment_amount IS DISTINCT FROM normalized_amount OR normalized_amount <= 0
       OR normalized_cash_key NOT IN ('cash_office', 'cash_bank_gcash')
       OR normalized_payment_reference = '' OR normalized_evidence_reference = ''
       OR normalized_digest !~ '^[0-9a-f]{64}$' OR length(normalized_note) < 20 THEN
        RAISE EXCEPTION 'Additional-tax payment evidence requires exact amendment, date, amount, approved cash/bank account and retained references/digest/note.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended('v1-tax-additional-amendment:' || p_amendment_evidence_id::text, 0)
    );

    SELECT * INTO evidence
    FROM accounting.v1_tax_additional_amendment_evidence item
    WHERE item.id = p_amendment_evidence_id
    FOR SHARE;
    IF evidence.id IS NULL THEN
        RAISE EXCEPTION 'Additional-tax amendment evidence was not found for payment evidence.';
    END IF;
    IF p_payment_date < evidence.amendment_date THEN
        RAISE EXCEPTION 'Additional-tax payment date cannot precede the retained amended-return/additional-assessment date.';
    END IF;
    IF normalized_amount <> evidence.payment_required_amount THEN
        RAISE EXCEPTION 'Additional-tax payment must exactly equal the retained amendment payment requirement; partial payment is not inferred.';
    END IF;

    SELECT * INTO liability_preparation
    FROM accounting.v1_tax_additional_liability_preparations item
    WHERE item.amendment_evidence_id = evidence.id
    FOR SHARE;
    SELECT * INTO liability_posting
    FROM accounting.v1_tax_additional_liability_postings item
    WHERE item.amendment_evidence_id = evidence.id
    FOR SHARE;
    IF liability_preparation.id IS NULL OR liability_posting.id IS NULL
       OR liability_posting.preparation_id <> liability_preparation.id
       OR liability_posting.confirmed_additional_tax_due <> evidence.additional_tax_due
       OR liability_posting.confirmed_evidence_digest <> evidence.evidence_digest THEN
        RAISE EXCEPTION 'Additional-tax payment evidence requires the exact protected additional liability to be posted first.';
    END IF;
    SELECT * INTO liability_journal
    FROM accounting.journal_entries item
    WHERE item.id = liability_posting.journal_entry_id
    FOR SHARE;
    IF liability_journal.id IS NULL OR liability_journal.status <> 'posted'
       OR liability_journal.entry_number <> liability_posting.entry_number THEN
        RAISE EXCEPTION 'Posted additional-tax liability journal history is missing or no longer exact.';
    END IF;

    SELECT * INTO original_queue
    FROM accounting.v1_tax_liability_queue queue
    WHERE queue.posting_id = evidence.tax_liability_posting_id
      AND queue.tax_type = evidence.tax_type
      AND queue.evidence_id = evidence.original_evidence_id;
    SELECT * INTO replacement_queue
    FROM accounting.v1_tax_liability_queue queue
    WHERE queue.tax_type = evidence.tax_type
      AND queue.evidence_id = evidence.replacement_evidence_id;
    IF original_queue.accounting_status <> 'posted_adjustment_review_required'
       OR replacement_queue.evidence_id IS NULL
       OR replacement_queue.evidence_status <> 'evidence_ready'
       OR replacement_queue.accounting_status <> 'evidence_ready'
       OR replacement_queue.source_id <> original_queue.source_id
       OR replacement_queue.loan_id <> original_queue.loan_id
       OR replacement_queue.client_id <> original_queue.client_id
       OR replacement_queue.tax_due <> evidence.replacement_item_tax_due THEN
        RAISE EXCEPTION 'Additional-tax payment is blocked because the exact original/replacement evidence coordinates changed after liability posting.';
    END IF;

    IF evidence.payment_basis = 'full_revised_return_unpaid' THEN
        SELECT * INTO original_payment
        FROM accounting.v1_tax_payment_evidence payment
        WHERE payment.tax_return_id = evidence.tax_return_id
        FOR SHARE;
        IF original_payment.id IS NOT NULL THEN
            RAISE EXCEPTION 'Base return payment evidence appeared after the unpaid amended-return workflow was reserved.';
        END IF;
    ELSE
        SELECT * INTO original_payment
        FROM accounting.v1_tax_payment_evidence payment
        WHERE payment.id = evidence.original_payment_evidence_id
        FOR SHARE;
        SELECT * INTO original_settlement
        FROM accounting.v1_tax_settlement_postings settlement
        WHERE settlement.id = evidence.original_settlement_posting_id
        FOR SHARE;
        SELECT * INTO original_settlement_journal
        FROM accounting.journal_entries journal
        WHERE journal.id = evidence.original_settlement_journal_entry_id
        FOR SHARE;
        IF original_payment.id IS NULL OR original_settlement.id IS NULL
           OR original_settlement.payment_evidence_id <> original_payment.id
           OR original_settlement.tax_return_id <> evidence.tax_return_id
           OR original_settlement_journal.id IS NULL
           OR original_settlement_journal.status <> 'posted'
           OR original_settlement_journal.entry_number <> original_settlement.entry_number THEN
            RAISE EXCEPTION 'Original settled-return history changed before additional-tax payment evidence was recorded.';
        END IF;
    END IF;

    SELECT * INTO cash_account
    FROM accounting.accounts account
    WHERE account.system_key = normalized_cash_key
    FOR SHARE;
    IF cash_account.id IS NULL OR cash_account.account_type <> 'asset'
       OR cash_account.normal_balance <> 'debit' OR NOT cash_account.is_active
       OR NOT cash_account.is_posting OR cash_account.code NOT IN ('1010', '1030') THEN
        RAISE EXCEPTION 'Additional-tax payment requires exact active approved Cash - Office or Cash - Bank / GCash evidence.';
    END IF;

    SELECT * INTO existing
    FROM accounting.v1_tax_additional_payment_evidence item
    WHERE item.idempotency_key = p_idempotency_key
    FOR SHARE;
    IF existing.id IS NOT NULL THEN
        IF existing.amendment_evidence_id = evidence.id
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
        RAISE EXCEPTION 'Additional-tax payment evidence idempotency key already belongs to different immutable evidence.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM accounting.v1_tax_additional_payment_evidence item
        WHERE item.amendment_evidence_id = evidence.id
    ) THEN
        RAISE EXCEPTION 'This additional-tax amendment already has immutable payment evidence.';
    END IF;

    PERFORM set_config('accounting.v1_tax_additional_payment_evidence_insert_allowed', 'on', true);
    INSERT INTO accounting.v1_tax_additional_payment_evidence(
        idempotency_key, amendment_evidence_id, payment_date, payment_amount,
        cash_account_system_key, payment_reference, evidence_reference,
        evidence_digest, evidence_note, recorded_by_user_id
    ) VALUES (
        p_idempotency_key, evidence.id, p_payment_date, normalized_amount,
        normalized_cash_key, normalized_payment_reference,
        normalized_evidence_reference, normalized_digest, normalized_note,
        p_actor_user_id
    ) RETURNING id INTO created_id;
    PERFORM set_config('accounting.v1_tax_additional_payment_evidence_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.tax.additional_payment_evidence.recorded',
        'v1_tax_additional_payment',
        created_id,
        jsonb_build_object(
            'amendment_evidence_id', evidence.id,
            'tax_return_id', evidence.tax_return_id,
            'payment_basis', evidence.payment_basis,
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

CREATE OR REPLACE FUNCTION accounting.prepare_v1_tax_additional_settlement_journal(
    p_payment_evidence_id UUID,
    p_actor_user_id UUID
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    payment accounting.v1_tax_additional_payment_evidence%ROWTYPE;
    evidence accounting.v1_tax_additional_amendment_evidence%ROWTYPE;
    liability_preparation accounting.v1_tax_additional_liability_preparations%ROWTYPE;
    liability_posting accounting.v1_tax_additional_liability_postings%ROWTYPE;
    liability_journal accounting.journal_entries%ROWTYPE;
    existing accounting.v1_tax_additional_settlement_preparations%ROWTYPE;
    original_queue accounting.v1_tax_liability_queue%ROWTYPE;
    replacement_queue accounting.v1_tax_liability_queue%ROWTYPE;
    payable_account accounting.accounts%ROWTYPE;
    cash_account accounting.accounts%ROWTYPE;
    target_period accounting.fiscal_periods%ROWTYPE;
    protected_source_event_key TEXT;
    created_journal_id UUID;
BEGIN
    PERFORM accounting.require_v1_tax_management_actor(
        p_actor_user_id,
        'accounting.tax.additional_settlement.prepare'
    );
    IF p_payment_evidence_id IS NULL THEN
        RAISE EXCEPTION 'Additional-tax settlement preparation requires exact payment evidence.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended('v1-tax-additional-settlement:' || p_payment_evidence_id::text, 0)
    );

    SELECT * INTO existing
    FROM accounting.v1_tax_additional_settlement_preparations item
    WHERE item.payment_evidence_id = p_payment_evidence_id;
    IF existing.id IS NOT NULL THEN
        RETURN existing.journal_entry_id;
    END IF;

    SELECT * INTO payment
    FROM accounting.v1_tax_additional_payment_evidence item
    WHERE item.id = p_payment_evidence_id
    FOR SHARE;
    IF payment.id IS NULL THEN
        RAISE EXCEPTION 'Additional-tax payment evidence was not found.';
    END IF;
    SELECT * INTO evidence
    FROM accounting.v1_tax_additional_amendment_evidence item
    WHERE item.id = payment.amendment_evidence_id
    FOR SHARE;
    IF evidence.id IS NULL OR payment.payment_amount <> evidence.payment_required_amount
       OR payment.payment_date < evidence.amendment_date THEN
        RAISE EXCEPTION 'Additional-tax amendment/payment evidence no longer reconciles for protected settlement.';
    END IF;

    SELECT * INTO liability_preparation
    FROM accounting.v1_tax_additional_liability_preparations item
    WHERE item.amendment_evidence_id = evidence.id
    FOR SHARE;
    SELECT * INTO liability_posting
    FROM accounting.v1_tax_additional_liability_postings item
    WHERE item.amendment_evidence_id = evidence.id
    FOR SHARE;
    SELECT * INTO liability_journal
    FROM accounting.journal_entries item
    WHERE item.id = liability_posting.journal_entry_id
    FOR SHARE;
    IF liability_preparation.id IS NULL OR liability_posting.id IS NULL
       OR liability_journal.id IS NULL OR liability_journal.status <> 'posted'
       OR liability_journal.entry_number <> liability_posting.entry_number
       OR liability_posting.confirmed_evidence_digest <> evidence.evidence_digest
       OR liability_posting.confirmed_additional_tax_due <> evidence.additional_tax_due THEN
        RAISE EXCEPTION 'Protected additional-tax liability history is missing or no longer exact for settlement.';
    END IF;

    SELECT * INTO original_queue
    FROM accounting.v1_tax_liability_queue queue
    WHERE queue.posting_id = evidence.tax_liability_posting_id
      AND queue.tax_type = evidence.tax_type
      AND queue.evidence_id = evidence.original_evidence_id;
    SELECT * INTO replacement_queue
    FROM accounting.v1_tax_liability_queue queue
    WHERE queue.tax_type = evidence.tax_type
      AND queue.evidence_id = evidence.replacement_evidence_id;
    IF original_queue.accounting_status <> 'posted_adjustment_review_required'
       OR replacement_queue.evidence_id IS NULL
       OR replacement_queue.evidence_status <> 'evidence_ready'
       OR replacement_queue.accounting_status <> 'evidence_ready'
       OR replacement_queue.source_id <> original_queue.source_id
       OR replacement_queue.loan_id <> original_queue.loan_id
       OR replacement_queue.client_id <> original_queue.client_id
       OR replacement_queue.tax_due <> evidence.replacement_item_tax_due THEN
        RAISE EXCEPTION 'Additional-tax settlement is blocked because exact original/replacement evidence changed after amendment liability posting.';
    END IF;

    SELECT * INTO payable_account
    FROM accounting.accounts account
    WHERE account.id = liability_posting.confirmed_tax_payable_account_id
    FOR SHARE;
    SELECT * INTO cash_account
    FROM accounting.accounts account
    WHERE account.system_key = payment.cash_account_system_key
    FOR SHARE;
    IF payable_account.id IS NULL OR payable_account.system_key <> 'tax_payables'
       OR payable_account.code <> '2100' OR payable_account.account_type <> 'liability'
       OR payable_account.normal_balance <> 'credit'
       OR NOT payable_account.is_active OR NOT payable_account.is_posting THEN
        RAISE EXCEPTION 'Exact active 2100 Tax Payables is required for additional-tax settlement.';
    END IF;
    IF cash_account.id IS NULL OR cash_account.system_key NOT IN ('cash_office', 'cash_bank_gcash')
       OR cash_account.code NOT IN ('1010', '1030') OR cash_account.account_type <> 'asset'
       OR cash_account.normal_balance <> 'debit'
       OR NOT cash_account.is_active OR NOT cash_account.is_posting THEN
        RAISE EXCEPTION 'Exact active approved Cash - Office or Cash - Bank / GCash is required for additional-tax settlement.';
    END IF;

    SELECT * INTO target_period
    FROM accounting.fiscal_periods period
    WHERE period.status = 'open'
      AND payment.payment_date BETWEEN period.start_date AND period.end_date
    ORDER BY period.start_date DESC
    LIMIT 1
    FOR SHARE;
    IF target_period.id IS NULL THEN
        RAISE EXCEPTION 'Additional-tax payment date must be inside an open accounting period.';
    END IF;

    protected_source_event_key := 'v1_tax_additional_settlement:' || payment.id::text;
    IF EXISTS (
        SELECT 1 FROM accounting.journal_entries journal
        WHERE journal.source_event_key = protected_source_event_key
    ) THEN
        RAISE EXCEPTION 'Protected V1 additional-tax settlement source identity is already occupied outside the settlement audit.';
    END IF;

    PERFORM set_config('accounting.v1_tax_additional_settlement_journal_prepare_allowed', 'on', true);
    INSERT INTO accounting.journal_entries(
        fiscal_period_id, posting_date, description, status, source_type,
        source_reference, source_event_key, created_by_user_id, updated_at
    ) VALUES (
        target_period.id, payment.payment_date,
        'Protected V1 additional-tax settlement for ' || evidence.amendment_reference,
        'draft', 'v1_tax_additional_settlement', payment.id::text,
        protected_source_event_key, p_actor_user_id, now()
    ) RETURNING id INTO created_journal_id;
    PERFORM set_config('accounting.v1_tax_additional_settlement_journal_prepare_allowed', 'off', true);

    PERFORM set_config('accounting.v1_tax_additional_settlement_journal_line_write_allowed', 'on', true);
    INSERT INTO accounting.journal_lines(
        journal_entry_id, line_number, account_id, description, debit, credit
    ) VALUES
        (created_journal_id, 1, payable_account.id, 'Settle retained amended tax payable', payment.payment_amount, 0),
        (created_journal_id, 2, cash_account.id, 'Additional tax payment from ' || cash_account.name, 0, payment.payment_amount);
    PERFORM set_config('accounting.v1_tax_additional_settlement_journal_line_write_allowed', 'off', true);

    INSERT INTO accounting.journal_events(journal_entry_id, event_type, actor_user_id, details)
    VALUES (
        created_journal_id, 'draft_created', p_actor_user_id,
        jsonb_build_object(
            'source_type', 'v1_tax_additional_settlement',
            'amendment_evidence_id', evidence.id,
            'additional_liability_posting_id', liability_posting.id,
            'payment_evidence_id', payment.id,
            'payment_basis', evidence.payment_basis,
            'payment_amount', payment.payment_amount,
            'tax_payable_account_code', payable_account.code,
            'cash_account_code', cash_account.code,
            'automatic_source_posting', false
        )
    );

    PERFORM set_config('accounting.v1_tax_additional_settlement_preparation_insert_allowed', 'on', true);
    INSERT INTO accounting.v1_tax_additional_settlement_preparations(
        payment_evidence_id, amendment_evidence_id, additional_liability_posting_id,
        journal_entry_id, source_event_key, payment_date, payment_amount,
        amendment_evidence_digest, additional_liability_confirmation_digest,
        payment_evidence_digest, tax_payable_account_id, cash_account_id,
        fiscal_period_id, prepared_by_user_id
    ) VALUES (
        payment.id, evidence.id, liability_posting.id, created_journal_id,
        protected_source_event_key, payment.payment_date, payment.payment_amount,
        evidence.evidence_digest, liability_posting.confirmation_digest,
        payment.evidence_digest, payable_account.id, cash_account.id,
        target_period.id, p_actor_user_id
    );
    PERFORM set_config('accounting.v1_tax_additional_settlement_preparation_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id, 'accounting.tax.additional_settlement.prepared',
        'v1_tax_additional_payment', payment.id,
        jsonb_build_object(
            'amendment_evidence_id', evidence.id,
            'additional_liability_posting_id', liability_posting.id,
            'journal_entry_id', created_journal_id,
            'payment_amount', payment.payment_amount,
            'tax_payable_account_code', payable_account.code,
            'cash_account_code', cash_account.code,
            'automatic_source_posting', false
        )
    );

    RETURN created_journal_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.post_v1_tax_additional_settlement_journal(
    p_payment_evidence_id UUID,
    p_actor_user_id UUID,
    p_confirmation_token TEXT,
    p_expected_amendment_evidence_digest TEXT,
    p_expected_additional_liability_confirmation_digest TEXT,
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
    normalized_amendment_digest TEXT := lower(btrim(coalesce(p_expected_amendment_evidence_digest, '')));
    normalized_liability_digest TEXT := lower(btrim(coalesce(p_expected_additional_liability_confirmation_digest, '')));
    normalized_payment_digest TEXT := lower(btrim(coalesce(p_expected_payment_evidence_digest, '')));
    normalized_amount NUMERIC(18,2) := round(coalesce(p_expected_payment_amount, -1), 2);
    normalized_payable_code TEXT := btrim(coalesce(p_expected_tax_payable_account_code, ''));
    normalized_cash_code TEXT := btrim(coalesce(p_expected_cash_account_code, ''));
    payment accounting.v1_tax_additional_payment_evidence%ROWTYPE;
    evidence accounting.v1_tax_additional_amendment_evidence%ROWTYPE;
    liability_posting accounting.v1_tax_additional_liability_postings%ROWTYPE;
    liability_journal accounting.journal_entries%ROWTYPE;
    preparation accounting.v1_tax_additional_settlement_preparations%ROWTYPE;
    existing accounting.v1_tax_additional_settlement_postings%ROWTYPE;
    original_queue accounting.v1_tax_liability_queue%ROWTYPE;
    replacement_queue accounting.v1_tax_liability_queue%ROWTYPE;
    period_row accounting.fiscal_periods%ROWTYPE;
    payable_account accounting.accounts%ROWTYPE;
    cash_account accounting.accounts%ROWTYPE;
    journal accounting.journal_entries%ROWTYPE;
    line_count INTEGER;
    total_debit NUMERIC(18,2);
    total_credit NUMERIC(18,2);
    expected_payable_debit NUMERIC(18,2);
    expected_cash_credit NUMERIC(18,2);
    foreign_line_count INTEGER;
    generated_entry_number TEXT;
    confirmation_digest_value TEXT;
    created_posting_id UUID;
BEGIN
    PERFORM accounting.require_v1_tax_management_actor(
        p_actor_user_id,
        'accounting.tax.additional_settlement.post'
    );

    IF p_payment_evidence_id IS NULL
       OR p_policy_version IS DISTINCT FROM 'v1_tax_additional_settlement_posting_v1'
       OR normalized_token !~ '^[0-9a-f]{64}$'
       OR normalized_amendment_digest !~ '^[0-9a-f]{64}$'
       OR normalized_liability_digest !~ '^[0-9a-f]{64}$'
       OR normalized_payment_digest !~ '^[0-9a-f]{64}$'
       OR p_expected_payment_amount IS DISTINCT FROM normalized_amount
       OR normalized_amount <= 0
       OR normalized_payable_code = '' OR normalized_cash_code = ''
       OR p_expected_posting_date IS NULL OR p_expected_fiscal_period_id IS NULL THEN
        RAISE EXCEPTION 'Protected additional-tax settlement posting requires exact Management confirmation, amendment/liability/payment digests, amount, accounts, date, period and policy.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended('v1-tax-additional-settlement:' || p_payment_evidence_id::text, 0)
    );

    SELECT * INTO payment
    FROM accounting.v1_tax_additional_payment_evidence item
    WHERE item.id = p_payment_evidence_id
    FOR SHARE;
    SELECT * INTO evidence
    FROM accounting.v1_tax_additional_amendment_evidence item
    WHERE item.id = payment.amendment_evidence_id
    FOR SHARE;
    SELECT * INTO liability_posting
    FROM accounting.v1_tax_additional_liability_postings item
    WHERE item.amendment_evidence_id = evidence.id
    FOR SHARE;
    SELECT * INTO preparation
    FROM accounting.v1_tax_additional_settlement_preparations item
    WHERE item.payment_evidence_id = payment.id
    FOR SHARE;
    IF payment.id IS NULL OR evidence.id IS NULL OR liability_posting.id IS NULL
       OR preparation.id IS NULL THEN
        RAISE EXCEPTION 'Additional-tax settlement requires exact immutable payment, amendment, liability and preparation evidence.';
    END IF;

    SELECT * INTO existing
    FROM accounting.v1_tax_additional_settlement_postings item
    WHERE item.preparation_id = preparation.id
    FOR SHARE;
    IF existing.id IS NOT NULL THEN
        IF existing.confirmation_token = normalized_token
           AND existing.confirmed_amendment_evidence_digest = normalized_amendment_digest
           AND existing.confirmed_additional_liability_confirmation_digest = normalized_liability_digest
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
        RAISE EXCEPTION 'Existing V1 additional-tax settlement posting does not match the immutable retry identity.';
    END IF;

    IF evidence.evidence_digest <> normalized_amendment_digest
       OR liability_posting.confirmation_digest <> normalized_liability_digest
       OR payment.evidence_digest <> normalized_payment_digest
       OR payment.payment_amount <> normalized_amount
       OR payment.payment_amount <> evidence.payment_required_amount
       OR payment.payment_date <> p_expected_posting_date
       OR preparation.payment_date <> p_expected_posting_date
       OR preparation.payment_amount <> normalized_amount
       OR preparation.amendment_evidence_digest <> normalized_amendment_digest
       OR preparation.additional_liability_confirmation_digest <> normalized_liability_digest
       OR preparation.payment_evidence_digest <> normalized_payment_digest THEN
        RAISE EXCEPTION 'Exact immutable additional-tax amendment/payment evidence no longer matches the confirmed settlement coordinates.';
    END IF;

    SELECT * INTO liability_journal
    FROM accounting.journal_entries item
    WHERE item.id = liability_posting.journal_entry_id
    FOR SHARE;
    IF liability_journal.id IS NULL OR liability_journal.status <> 'posted'
       OR liability_journal.entry_number <> liability_posting.entry_number
       OR liability_posting.confirmed_additional_tax_due <> evidence.additional_tax_due THEN
        RAISE EXCEPTION 'Protected additional-tax liability posting history changed before settlement.';
    END IF;

    SELECT * INTO original_queue
    FROM accounting.v1_tax_liability_queue queue
    WHERE queue.posting_id = evidence.tax_liability_posting_id
      AND queue.tax_type = evidence.tax_type
      AND queue.evidence_id = evidence.original_evidence_id;
    SELECT * INTO replacement_queue
    FROM accounting.v1_tax_liability_queue queue
    WHERE queue.tax_type = evidence.tax_type
      AND queue.evidence_id = evidence.replacement_evidence_id;
    IF original_queue.accounting_status <> 'posted_adjustment_review_required'
       OR replacement_queue.evidence_id IS NULL
       OR replacement_queue.evidence_status <> 'evidence_ready'
       OR replacement_queue.accounting_status <> 'evidence_ready'
       OR replacement_queue.source_id <> original_queue.source_id
       OR replacement_queue.loan_id <> original_queue.loan_id
       OR replacement_queue.client_id <> original_queue.client_id
       OR replacement_queue.tax_due <> evidence.replacement_item_tax_due THEN
        RAISE EXCEPTION 'Additional-tax settlement is blocked because exact original/replacement tax evidence changed before payment posting.';
    END IF;

    SELECT * INTO period_row
    FROM accounting.fiscal_periods period
    WHERE period.id = p_expected_fiscal_period_id
    FOR SHARE;
    IF period_row.id IS NULL OR period_row.status <> 'open'
       OR preparation.fiscal_period_id <> period_row.id
       OR p_expected_posting_date NOT BETWEEN period_row.start_date AND period_row.end_date THEN
        RAISE EXCEPTION 'Additional-tax settlement posting requires the exact still-open payment fiscal period.';
    END IF;

    SELECT * INTO payable_account
    FROM accounting.accounts account
    WHERE account.id = preparation.tax_payable_account_id
    FOR SHARE;
    SELECT * INTO cash_account
    FROM accounting.accounts account
    WHERE account.id = preparation.cash_account_id
    FOR SHARE;
    IF payable_account.id IS NULL OR payable_account.code <> normalized_payable_code
       OR payable_account.system_key <> 'tax_payables' OR payable_account.code <> '2100'
       OR payable_account.account_type <> 'liability'
       OR payable_account.normal_balance <> 'credit'
       OR NOT payable_account.is_active OR NOT payable_account.is_posting
       OR cash_account.id IS NULL OR cash_account.code <> normalized_cash_code
       OR cash_account.system_key NOT IN ('cash_office', 'cash_bank_gcash')
       OR cash_account.code NOT IN ('1010', '1030')
       OR cash_account.account_type <> 'asset' OR cash_account.normal_balance <> 'debit'
       OR NOT cash_account.is_active OR NOT cash_account.is_posting THEN
        RAISE EXCEPTION 'Exact confirmed additional-tax payable/cash accounts are no longer posting-ready.';
    END IF;

    SELECT * INTO journal
    FROM accounting.journal_entries item
    WHERE item.id = preparation.journal_entry_id
    FOR UPDATE;
    IF journal.id IS NULL OR journal.status <> 'draft'
       OR journal.source_type <> 'v1_tax_additional_settlement'
       OR journal.source_reference <> payment.id::text
       OR journal.source_event_key <> preparation.source_event_key
       OR journal.posting_date <> p_expected_posting_date
       OR journal.fiscal_period_id <> period_row.id
       OR journal.reversal_of_entry_id IS NOT NULL THEN
        RAISE EXCEPTION 'Prepared V1 additional-tax settlement General Journal draft no longer matches the protected payment coordinates.';
    END IF;

    SELECT
        count(*)::integer,
        coalesce(sum(line.debit), 0)::numeric(18,2),
        coalesce(sum(line.credit), 0)::numeric(18,2),
        coalesce(sum(line.debit) FILTER (WHERE line.account_id = payable_account.id), 0)::numeric(18,2),
        coalesce(sum(line.credit) FILTER (WHERE line.account_id = cash_account.id), 0)::numeric(18,2),
        count(*) FILTER (
            WHERE line.account_id NOT IN (payable_account.id, cash_account.id)
               OR line.client_id IS NOT NULL
               OR line.loan_id IS NOT NULL
        )::integer
    INTO line_count, total_debit, total_credit,
         expected_payable_debit, expected_cash_credit, foreign_line_count
    FROM accounting.journal_lines line
    WHERE line.journal_entry_id = journal.id;

    IF line_count <> 2
       OR total_debit <> normalized_amount
       OR total_credit <> normalized_amount
       OR expected_payable_debit <> normalized_amount
       OR expected_cash_credit <> normalized_amount
       OR foreign_line_count <> 0 THEN
        RAISE EXCEPTION 'Prepared V1 additional-tax settlement lines no longer exactly reconcile to retained payment evidence.';
    END IF;

    confirmation_digest_value := encode(sha256(convert_to(concat_ws('|',
        p_policy_version, payment.id::text, evidence.id::text,
        liability_posting.id::text, normalized_amendment_digest,
        normalized_liability_digest, normalized_payment_digest,
        to_char(normalized_amount, 'FM999999999999990.00'),
        payable_account.id::text, cash_account.id::text,
        p_expected_posting_date::text, period_row.id::text,
        journal.id::text, normalized_token
    ), 'UTF8')), 'hex');

    PERFORM set_config('accounting.v1_tax_additional_settlement_journal_post_allowed', 'on', true);
    generated_entry_number := accounting.post_journal_entry(journal.id, p_actor_user_id);
    PERFORM set_config('accounting.v1_tax_additional_settlement_journal_post_allowed', 'off', true);

    IF coalesce(current_setting('accounting.v1_tax_additional_settlement_force_audit_failure', true), '') = 'on' THEN
        RAISE EXCEPTION 'Forced V1 additional-tax settlement audit failure.';
    END IF;

    PERFORM set_config('accounting.v1_tax_additional_settlement_posting_insert_allowed', 'on', true);
    INSERT INTO accounting.v1_tax_additional_settlement_postings(
        preparation_id, payment_evidence_id, amendment_evidence_id,
        additional_liability_posting_id, journal_entry_id, entry_number,
        confirmation_token, confirmation_digest,
        confirmed_amendment_evidence_digest,
        confirmed_additional_liability_confirmation_digest,
        confirmed_payment_evidence_digest, confirmed_payment_amount,
        confirmed_tax_payable_account_id, confirmed_cash_account_id,
        confirmed_posting_date, confirmed_fiscal_period_id,
        policy_version, posted_by_user_id
    ) VALUES (
        preparation.id, payment.id, evidence.id, liability_posting.id,
        journal.id, generated_entry_number, normalized_token,
        confirmation_digest_value, normalized_amendment_digest,
        normalized_liability_digest, normalized_payment_digest,
        normalized_amount, payable_account.id, cash_account.id,
        p_expected_posting_date, period_row.id, p_policy_version,
        p_actor_user_id
    ) RETURNING id INTO created_posting_id;
    PERFORM set_config('accounting.v1_tax_additional_settlement_posting_insert_allowed', 'off', true);

    INSERT INTO accounting.journal_events(journal_entry_id, event_type, actor_user_id, details)
    VALUES (
        journal.id, 'posted', p_actor_user_id,
        jsonb_build_object(
            'entry_number', generated_entry_number,
            'source_type', 'v1_tax_additional_settlement',
            'amendment_evidence_id', evidence.id,
            'additional_liability_posting_id', liability_posting.id,
            'payment_evidence_id', payment.id,
            'confirmation_digest', confirmation_digest_value,
            'automatic_source_posting', false
        )
    );

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id, 'accounting.tax.additional_settlement.posted',
        'v1_tax_additional_payment', payment.id,
        jsonb_build_object(
            'amendment_evidence_id', evidence.id,
            'additional_liability_posting_id', liability_posting.id,
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

CREATE OR REPLACE VIEW accounting.v1_tax_additional_amendment_queue AS
SELECT
    liability.amendment_evidence_id,
    liability.amendment_basis,
    liability.tax_type,
    liability.tax_return_id,
    liability.tax_liability_posting_id,
    liability.original_evidence_id,
    liability.replacement_evidence_id,
    liability.source_id,
    liability.loan_id,
    liability.client_id,
    liability.original_declared_tax_due,
    liability.revised_declared_tax_due,
    liability.original_item_tax_due,
    liability.replacement_item_tax_due,
    liability.additional_tax_due,
    liability.payment_basis,
    liability.payment_required_amount,
    liability.amendment_date,
    liability.recognition_date,
    liability.amendment_reference,
    liability.evidence_reference,
    liability.evidence_digest,
    liability.original_payment_evidence_id,
    liability.original_settlement_posting_id,
    liability.original_settlement_journal_entry_id,
    liability.recorded_by_user_id,
    liability.recorded_at,
    liability.liability_preparation_id,
    liability.liability_journal_entry_id,
    liability.liability_journal_status,
    liability.liability_entry_number,
    liability.liability_fiscal_period_id,
    liability.expense_account_code,
    liability.tax_payable_account_code,
    liability.liability_prepared_by_user_id,
    liability.liability_prepared_at,
    liability.additional_liability_posting_id,
    liability.liability_confirmation_digest,
    liability.liability_posted_by_user_id,
    liability.liability_posted_at,
    payment.id AS additional_payment_evidence_id,
    payment.payment_date,
    payment.payment_amount,
    payment.cash_account_system_key,
    payment_cash.code AS payment_cash_account_code,
    payment_cash.name AS payment_cash_account_name,
    payment.payment_reference,
    payment.evidence_reference AS payment_evidence_reference,
    payment.evidence_digest AS payment_evidence_digest,
    payment.recorded_by_user_id AS payment_recorded_by_user_id,
    payment.recorded_at AS payment_recorded_at,
    settlement_preparation.id AS settlement_preparation_id,
    settlement_preparation.journal_entry_id AS settlement_journal_entry_id,
    settlement_journal.status AS settlement_journal_status,
    settlement_journal.entry_number AS settlement_entry_number,
    settlement_preparation.fiscal_period_id AS settlement_fiscal_period_id,
    settlement_preparation.prepared_by_user_id AS settlement_prepared_by_user_id,
    settlement_preparation.prepared_at AS settlement_prepared_at,
    settlement_posting.id AS additional_settlement_posting_id,
    settlement_posting.confirmation_digest AS settlement_confirmation_digest,
    settlement_posting.posted_by_user_id AS settlement_posted_by_user_id,
    settlement_posting.posted_at AS settlement_posted_at,
    CASE
        WHEN settlement_posting.id IS NOT NULL
             AND liability.amendment_status = 'additional_liability_posted_review_required'
            THEN 'additional_tax_settled_review_required'
        WHEN settlement_posting.id IS NOT NULL THEN 'additional_tax_settled'
        WHEN settlement_preparation.id IS NOT NULL
             AND settlement_journal.status IS DISTINCT FROM 'draft'
            THEN 'blocked_untracked_additional_settlement_journal_state'
        WHEN payment.id IS NOT NULL
             AND liability.amendment_status <> 'additional_liability_posted_awaiting_payment'
            THEN 'blocked_additional_liability_not_current'
        WHEN settlement_preparation.id IS NOT NULL THEN 'additional_settlement_prepared'
        WHEN payment.id IS NOT NULL THEN 'additional_payment_evidence_ready'
        ELSE liability.amendment_status
    END AS amendment_status,
    CASE
        WHEN settlement_posting.id IS NOT NULL
             AND liability.amendment_status = 'additional_liability_posted_review_required'
            THEN 'A later tax-evidence change occurred after the amended liability/payment settlement; a new explicit review is required.'
        WHEN settlement_posting.id IS NOT NULL THEN NULL
        WHEN settlement_preparation.id IS NOT NULL
             AND settlement_journal.status IS DISTINCT FROM 'draft'
            THEN 'Prepared additional-tax settlement journal is not a draft but has no immutable protected settlement posting audit.'
        WHEN payment.id IS NOT NULL
             AND liability.amendment_status <> 'additional_liability_posted_awaiting_payment'
            THEN 'The protected additional-tax liability is no longer current enough to accept or post payment.'
        WHEN settlement_preparation.id IS NOT NULL
            THEN 'Exact Management confirmation is required before posting the protected additional-tax settlement.'
        WHEN payment.id IS NOT NULL THEN NULL
        ELSE liability.amendment_blocker
    END AS amendment_blocker,
    true AS tax_additional_amendment_enabled,
    true AS tax_additional_settlement_enabled,
    false AS tax_refund_credit_realization_enabled,
    false AS automatic_source_posting
FROM accounting.v1_tax_additional_amendment_liability_queue liability
LEFT JOIN accounting.v1_tax_additional_payment_evidence payment
  ON payment.amendment_evidence_id = liability.amendment_evidence_id
LEFT JOIN accounting.accounts payment_cash
  ON payment_cash.system_key = payment.cash_account_system_key
LEFT JOIN accounting.v1_tax_additional_settlement_preparations settlement_preparation
  ON settlement_preparation.payment_evidence_id = payment.id
LEFT JOIN accounting.journal_entries settlement_journal
  ON settlement_journal.id = settlement_preparation.journal_entry_id
LEFT JOIN accounting.v1_tax_additional_settlement_postings settlement_posting
  ON settlement_posting.preparation_id = settlement_preparation.id;

CREATE OR REPLACE VIEW accounting.v1_tax_additional_amendment_summary AS
SELECT
    count(*)::bigint AS amendment_evidence_count,
    count(*) FILTER (WHERE amendment_status = 'amendment_evidence_ready')::bigint AS amendment_ready_count,
    count(*) FILTER (WHERE amendment_status = 'additional_liability_prepared')::bigint AS liability_prepared_count,
    count(*) FILTER (WHERE amendment_status = 'additional_liability_posted_awaiting_payment')::bigint AS awaiting_payment_count,
    count(*) FILTER (WHERE amendment_status = 'additional_payment_evidence_ready')::bigint AS payment_ready_count,
    count(*) FILTER (WHERE amendment_status = 'additional_settlement_prepared')::bigint AS settlement_prepared_count,
    count(*) FILTER (WHERE amendment_status = 'additional_tax_settled')::bigint AS settled_count,
    count(*) FILTER (WHERE amendment_status LIKE '%review_required')::bigint AS review_count,
    count(*) FILTER (WHERE amendment_status LIKE 'blocked_%')::bigint AS blocked_count,
    coalesce(sum(additional_tax_due) FILTER (
        WHERE amendment_status IN (
            'additional_liability_posted_awaiting_payment',
            'additional_payment_evidence_ready',
            'additional_settlement_prepared',
            'additional_tax_settled',
            'additional_tax_settled_review_required'
        )
    ), 0)::numeric(18,2) AS recognized_additional_tax_total,
    coalesce(sum(payment_amount) FILTER (
        WHERE amendment_status IN ('additional_tax_settled', 'additional_tax_settled_review_required')
    ), 0)::numeric(18,2) AS settled_payment_total,
    true AS tax_additional_amendment_enabled,
    true AS tax_additional_settlement_enabled,
    false AS tax_refund_credit_realization_enabled,
    false AS automatic_source_posting
FROM accounting.v1_tax_additional_amendment_queue;

COMMENT ON TABLE accounting.v1_tax_additional_payment_evidence IS
'Immutable Management-approved payment evidence for the exact payment requirement derived by one protected V1 additional-tax amendment. Partial payment is not inferred.';
COMMENT ON TABLE accounting.v1_tax_additional_settlement_postings IS
'Immutable protected V1 additional-tax settlement audit: Dr 2100 Tax Payables / Cr exact approved 1010 or 1030 cash-bank account. Original filed/settled history remains unchanged.';
COMMENT ON VIEW accounting.v1_tax_additional_amendment_queue IS
'End-to-end protected upward tax-amendment queue from retained amendment/assessment evidence through delta liability, exact payment evidence and settlement. Tax Recoverable realization remains disabled.';

COMMIT;
