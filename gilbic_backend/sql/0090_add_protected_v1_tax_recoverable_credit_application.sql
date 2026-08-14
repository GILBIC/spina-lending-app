BEGIN;

-- Master #296 A6.2 Tax Recoverable realization, legally usable tax-credit application sub-slice.
-- One exact posted 1130 Tax Recoverable may be applied in full against one exact current
-- unpaid retained V1 tax return only after separate immutable Management evidence proves
-- legal usability and the actual application. The credit amount is derived from the
-- protected recoverable and must exactly equal the target return due. Partial recoverable
-- use, mixed cash-plus-credit settlement, closed-period correction and automatic source
-- posting remain fail-closed.

INSERT INTO core.permissions (code, description)
VALUES
    ('accounting.tax.recoverable_credit_evidence.record', 'Record immutable Management-approved legally usable tax-credit application evidence for one exact posted V1 Tax Recoverable and one exact unpaid V1 tax return'),
    ('accounting.tax.recoverable_credit.prepare', 'Prepare a protected V1 Tax Recoverable credit-application General Journal draft from exact retained authority/application evidence'),
    ('accounting.tax.recoverable_credit.post', 'Post a protected V1 Tax Recoverable credit-application General Journal after exact Management confirmation')
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code IN (
      'accounting.tax.recoverable_credit_evidence.record',
      'accounting.tax.recoverable_credit.prepare',
      'accounting.tax.recoverable_credit.post'
  )
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.v1_tax_recoverable_credit_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key UUID NOT NULL UNIQUE,
    adjustment_posting_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_adjustment_postings(id) ON DELETE RESTRICT,
    adjustment_evidence_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_adjustment_evidence(id) ON DELETE RESTRICT,
    tax_type TEXT NOT NULL CHECK (
        tax_type IN ('documentary_stamp_tax', 'percentage_tax_lending')
    ),
    target_tax_return_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_return_evidence(id) ON DELETE RESTRICT,
    credit_amount NUMERIC(18,2) NOT NULL CHECK (credit_amount > 0),
    application_date DATE NOT NULL,
    application_reference TEXT NOT NULL CHECK (btrim(application_reference) <> ''),
    authority_reference TEXT NOT NULL CHECK (btrim(authority_reference) <> ''),
    evidence_digest TEXT NOT NULL CHECK (evidence_digest ~ '^[0-9a-f]{64}$'),
    evidence_note TEXT NOT NULL CHECK (length(btrim(evidence_note)) >= 20),
    recorded_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS v1_tax_recoverable_credit_date_idx
    ON accounting.v1_tax_recoverable_credit_evidence(application_date DESC, recorded_at DESC);

CREATE TABLE IF NOT EXISTS accounting.v1_tax_recoverable_credit_preparations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    credit_evidence_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_recoverable_credit_evidence(id) ON DELETE RESTRICT,
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    source_event_key TEXT NOT NULL UNIQUE CHECK (btrim(source_event_key) <> ''),
    posting_date DATE NOT NULL,
    credit_amount NUMERIC(18,2) NOT NULL CHECK (credit_amount > 0),
    tax_payable_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    tax_recoverable_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    fiscal_period_id UUID NOT NULL REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    prepared_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    prepared_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS accounting.v1_tax_recoverable_credit_postings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    preparation_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_recoverable_credit_preparations(id) ON DELETE RESTRICT,
    credit_evidence_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_recoverable_credit_evidence(id) ON DELETE RESTRICT,
    adjustment_posting_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_adjustment_postings(id) ON DELETE RESTRICT,
    target_tax_return_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_return_evidence(id) ON DELETE RESTRICT,
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    entry_number TEXT NOT NULL UNIQUE CHECK (btrim(entry_number) <> ''),
    confirmation_token TEXT NOT NULL CHECK (confirmation_token ~ '^[0-9a-f]{64}$'),
    confirmation_digest TEXT NOT NULL CHECK (confirmation_digest ~ '^[0-9a-f]{64}$'),
    confirmed_evidence_digest TEXT NOT NULL CHECK (confirmed_evidence_digest ~ '^[0-9a-f]{64}$'),
    confirmed_credit_amount NUMERIC(18,2) NOT NULL CHECK (confirmed_credit_amount > 0),
    confirmed_tax_payable_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    confirmed_tax_recoverable_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    confirmed_posting_date DATE NOT NULL,
    confirmed_fiscal_period_id UUID NOT NULL REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    policy_version TEXT NOT NULL CHECK (policy_version = 'v1_tax_recoverable_credit_posting_v1'),
    posted_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    posted_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE OR REPLACE FUNCTION accounting.guard_v1_tax_recoverable_credit_immutable_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    insert_allowed BOOLEAN := false;
BEGIN
    IF TG_TABLE_NAME = 'v1_tax_recoverable_credit_evidence' THEN
        insert_allowed := coalesce(current_setting('accounting.v1_tax_recoverable_credit_evidence_insert_allowed', true), '') = 'on';
    ELSIF TG_TABLE_NAME = 'v1_tax_recoverable_credit_preparations' THEN
        insert_allowed := coalesce(current_setting('accounting.v1_tax_recoverable_credit_preparation_insert_allowed', true), '') = 'on';
    ELSIF TG_TABLE_NAME = 'v1_tax_recoverable_credit_postings' THEN
        insert_allowed := coalesce(current_setting('accounting.v1_tax_recoverable_credit_posting_insert_allowed', true), '') = 'on';
    END IF;

    IF TG_OP = 'INSERT' AND insert_allowed THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'V1 Tax Recoverable credit-application evidence and audit rows are immutable and must use the protected Management workflow.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_v1_tax_recoverable_credit_evidence_guard
    ON accounting.v1_tax_recoverable_credit_evidence;
CREATE TRIGGER accounting_v1_tax_recoverable_credit_evidence_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.v1_tax_recoverable_credit_evidence
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_recoverable_credit_immutable_write();

DROP TRIGGER IF EXISTS accounting_v1_tax_recoverable_credit_preparation_guard
    ON accounting.v1_tax_recoverable_credit_preparations;
CREATE TRIGGER accounting_v1_tax_recoverable_credit_preparation_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.v1_tax_recoverable_credit_preparations
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_recoverable_credit_immutable_write();

DROP TRIGGER IF EXISTS accounting_v1_tax_recoverable_credit_posting_guard
    ON accounting.v1_tax_recoverable_credit_postings;
CREATE TRIGGER accounting_v1_tax_recoverable_credit_posting_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.v1_tax_recoverable_credit_postings
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_recoverable_credit_immutable_write();

CREATE OR REPLACE FUNCTION accounting.guard_v1_tax_recoverable_credit_journal_entry_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    reversed_source TEXT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF (
            NEW.source_type = 'v1_tax_recoverable_credit_application'
            OR coalesce(NEW.source_event_key, '') LIKE 'v1_tax_recoverable_credit:%'
        )
        AND coalesce(current_setting('accounting.v1_tax_recoverable_credit_journal_prepare_allowed', true), '') <> 'on' THEN
            RAISE EXCEPTION 'V1 Tax Recoverable credit-application journals must use the protected Management credit preparation function.';
        END IF;

        IF NEW.reversal_of_entry_id IS NOT NULL THEN
            SELECT item.source_type INTO reversed_source
            FROM accounting.journal_entries item
            WHERE item.id = NEW.reversal_of_entry_id;
            IF reversed_source = 'v1_tax_recoverable_credit_application' THEN
                RAISE EXCEPTION 'Posted V1 Tax Recoverable credit applications cannot be reversed through the manual General Journal; new retained correction evidence is required.';
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.source_type IS DISTINCT FROM 'v1_tax_recoverable_credit_application' THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'V1 Tax Recoverable credit-application journals are immutable and cannot be deleted.';
    END IF;

    IF OLD.status = 'draft' AND NEW.status = 'posted' THEN
        IF coalesce(current_setting('accounting.v1_tax_recoverable_credit_journal_post_allowed', true), '') <> 'on' THEN
            RAISE EXCEPTION 'V1 Tax Recoverable credit-application journals require the protected Management credit posting function.';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'V1 Tax Recoverable credit-application journals are system generated and immutable.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_v1_tax_recoverable_credit_journal_entry_guard
    ON accounting.journal_entries;
CREATE TRIGGER accounting_v1_tax_recoverable_credit_journal_entry_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_recoverable_credit_journal_entry_change();

CREATE OR REPLACE FUNCTION accounting.guard_v1_tax_recoverable_credit_journal_line_change()
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

    IF target_source_type = 'v1_tax_recoverable_credit_application'
       AND coalesce(current_setting('accounting.v1_tax_recoverable_credit_journal_line_write_allowed', true), '') <> 'on' THEN
        RAISE EXCEPTION 'V1 Tax Recoverable credit-application journal lines are system generated and immutable.';
    END IF;

    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_v1_tax_recoverable_credit_journal_line_guard
    ON accounting.journal_lines;
CREATE TRIGGER accounting_v1_tax_recoverable_credit_journal_line_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_lines
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_recoverable_credit_journal_line_change();

CREATE OR REPLACE FUNCTION accounting.guard_v1_tax_recoverable_credit_competing_payment()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM accounting.v1_tax_recoverable_credit_evidence credit
        WHERE credit.target_tax_return_id = NEW.tax_return_id
    ) THEN
        RAISE EXCEPTION 'This tax return is reserved for protected Tax Recoverable credit application; cash payment evidence would duplicate settlement.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_v1_tax_recoverable_credit_competing_payment_guard
    ON accounting.v1_tax_payment_evidence;
CREATE TRIGGER accounting_v1_tax_recoverable_credit_competing_payment_guard
BEFORE INSERT ON accounting.v1_tax_payment_evidence
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_recoverable_credit_competing_payment();

CREATE OR REPLACE FUNCTION accounting.guard_v1_tax_recoverable_credit_competing_refund()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM accounting.v1_tax_recoverable_credit_evidence credit
        WHERE credit.adjustment_posting_id = NEW.adjustment_posting_id
    ) THEN
        RAISE EXCEPTION 'This exact Tax Recoverable is reserved for protected tax-credit application; refund evidence would duplicate realization.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_v1_tax_recoverable_credit_competing_refund_guard
    ON accounting.v1_tax_recoverable_refund_evidence;
CREATE TRIGGER accounting_v1_tax_recoverable_credit_competing_refund_guard
BEFORE INSERT ON accounting.v1_tax_recoverable_refund_evidence
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_recoverable_credit_competing_refund();

CREATE OR REPLACE FUNCTION accounting.record_v1_tax_recoverable_credit_evidence(
    p_actor_user_id UUID,
    p_idempotency_key UUID,
    p_adjustment_posting_id UUID,
    p_target_tax_return_id UUID,
    p_application_date DATE,
    p_application_reference TEXT,
    p_authority_reference TEXT,
    p_evidence_digest TEXT,
    p_evidence_note TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    normalized_application_reference TEXT := btrim(coalesce(p_application_reference, ''));
    normalized_authority_reference TEXT := btrim(coalesce(p_authority_reference, ''));
    normalized_digest TEXT := lower(btrim(coalesce(p_evidence_digest, '')));
    normalized_note TEXT := btrim(coalesce(p_evidence_note, ''));
    adjustment_posting accounting.v1_tax_adjustment_postings%ROWTYPE;
    adjustment_evidence accounting.v1_tax_adjustment_evidence%ROWTYPE;
    adjustment_queue accounting.v1_tax_adjustment_queue%ROWTYPE;
    adjustment_journal accounting.journal_entries%ROWTYPE;
    target_return accounting.v1_tax_return_evidence%ROWTYPE;
    recoverable_account accounting.accounts%ROWTYPE;
    existing accounting.v1_tax_recoverable_credit_evidence%ROWTYPE;
    item_count INTEGER;
    exact_count INTEGER;
    item_total NUMERIC(18,2);
    created_id UUID;
BEGIN
    PERFORM accounting.require_v1_tax_management_actor(
        p_actor_user_id,
        'accounting.tax.recoverable_credit_evidence.record'
    );

    IF p_idempotency_key IS NULL OR p_adjustment_posting_id IS NULL
       OR p_target_tax_return_id IS NULL OR p_application_date IS NULL
       OR normalized_application_reference = '' OR normalized_authority_reference = ''
       OR normalized_digest !~ '^[0-9a-f]{64}$' OR length(normalized_note) < 20 THEN
        RAISE EXCEPTION 'Tax Recoverable credit evidence requires exact recoverable posting, target return, application date, retained application/authority references, SHA-256 digest and substantive note.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended(
            'v1-tax-recoverable-credit:' || p_adjustment_posting_id::text || ':' || p_target_tax_return_id::text,
            0
        )
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
        RAISE EXCEPTION 'Tax-credit application requires an exact current posted settled-tax decrease carried in active 1130 Tax Recoverable.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM accounting.v1_tax_recoverable_refund_evidence refund
        WHERE refund.adjustment_posting_id = adjustment_posting.id
    ) THEN
        RAISE EXCEPTION 'This exact Tax Recoverable already has immutable cash-refund evidence and cannot also be applied as a tax credit.';
    END IF;

    SELECT * INTO target_return
    FROM accounting.v1_tax_return_evidence item
    WHERE item.id = p_target_tax_return_id
    FOR SHARE;
    IF target_return.id IS NULL THEN
        RAISE EXCEPTION 'Target V1 tax return evidence was not found for credit application.';
    END IF;
    IF target_return.tax_type <> adjustment_evidence.tax_type THEN
        RAISE EXCEPTION 'V1 Tax Recoverable credit application is restricted to the exact same retained tax type.';
    END IF;
    IF target_return.declared_tax_due <> adjustment_posting.confirmed_adjustment_amount THEN
        RAISE EXCEPTION 'V1 Tax Recoverable credit application is full-only: exact recoverable amount must equal the target return declared tax due.';
    END IF;
    IF p_application_date < adjustment_posting.confirmed_posting_date
       OR p_application_date < target_return.filing_date THEN
        RAISE EXCEPTION 'Tax-credit application date cannot predate either Tax Recoverable recognition or the retained target return filing date.';
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
    WHERE item.tax_return_id = target_return.id;

    IF item_count <= 0 OR exact_count <> item_count
       OR item_total <> target_return.declared_tax_due THEN
        RAISE EXCEPTION 'Target tax return liabilities are not exact current posted V1 liabilities for protected credit application.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM accounting.v1_tax_payment_evidence payment
        WHERE payment.tax_return_id = target_return.id
    ) OR EXISTS (
        SELECT 1 FROM accounting.v1_tax_settlement_preparations preparation
        WHERE preparation.tax_return_id = target_return.id
    ) OR EXISTS (
        SELECT 1 FROM accounting.v1_tax_settlement_postings posting
        WHERE posting.tax_return_id = target_return.id
    ) THEN
        RAISE EXCEPTION 'Target tax return already has cash-payment or settlement evidence; tax-credit application would duplicate settlement.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM accounting.v1_tax_additional_amendment_evidence amendment
        WHERE amendment.tax_return_id = target_return.id
    ) THEN
        RAISE EXCEPTION 'Target tax return is already reserved by an additional-tax amendment and cannot use the base V1 Tax Recoverable credit path.';
    END IF;

    SELECT * INTO existing
    FROM accounting.v1_tax_recoverable_credit_evidence item
    WHERE item.idempotency_key = p_idempotency_key
    FOR SHARE;
    IF existing.id IS NOT NULL THEN
        IF existing.adjustment_posting_id = adjustment_posting.id
           AND existing.adjustment_evidence_id = adjustment_evidence.id
           AND existing.tax_type = adjustment_evidence.tax_type
           AND existing.target_tax_return_id = target_return.id
           AND existing.credit_amount = adjustment_posting.confirmed_adjustment_amount
           AND existing.application_date = p_application_date
           AND existing.application_reference = normalized_application_reference
           AND existing.authority_reference = normalized_authority_reference
           AND existing.evidence_digest = normalized_digest
           AND existing.evidence_note = normalized_note
           AND existing.recorded_by_user_id = p_actor_user_id THEN
            RETURN existing.id;
        END IF;
        RAISE EXCEPTION 'Tax Recoverable credit idempotency key already belongs to different immutable evidence.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM accounting.v1_tax_recoverable_credit_evidence item
        WHERE item.adjustment_posting_id = adjustment_posting.id
    ) THEN
        RAISE EXCEPTION 'This exact Tax Recoverable already has immutable tax-credit application evidence.';
    END IF;
    IF EXISTS (
        SELECT 1 FROM accounting.v1_tax_recoverable_credit_evidence item
        WHERE item.target_tax_return_id = target_return.id
    ) THEN
        RAISE EXCEPTION 'This exact target tax return already has immutable Tax Recoverable credit evidence.';
    END IF;

    PERFORM set_config('accounting.v1_tax_recoverable_credit_evidence_insert_allowed', 'on', true);
    INSERT INTO accounting.v1_tax_recoverable_credit_evidence(
        idempotency_key, adjustment_posting_id, adjustment_evidence_id,
        tax_type, target_tax_return_id, credit_amount, application_date,
        application_reference, authority_reference, evidence_digest,
        evidence_note, recorded_by_user_id
    ) VALUES (
        p_idempotency_key, adjustment_posting.id, adjustment_evidence.id,
        adjustment_evidence.tax_type, target_return.id,
        adjustment_posting.confirmed_adjustment_amount, p_application_date,
        normalized_application_reference, normalized_authority_reference,
        normalized_digest, normalized_note, p_actor_user_id
    ) RETURNING id INTO created_id;
    PERFORM set_config('accounting.v1_tax_recoverable_credit_evidence_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.tax.recoverable_credit.evidence_recorded',
        'v1_tax_recoverable_credit',
        created_id,
        jsonb_build_object(
            'adjustment_posting_id', adjustment_posting.id,
            'target_tax_return_id', target_return.id,
            'tax_type', adjustment_evidence.tax_type,
            'credit_amount', adjustment_posting.confirmed_adjustment_amount,
            'application_date', p_application_date,
            'evidence_digest', normalized_digest,
            'full_only', true,
            'automatic_source_posting', false
        )
    );

    RETURN created_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.prepare_v1_tax_recoverable_credit_journal(
    p_credit_evidence_id UUID,
    p_actor_user_id UUID
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    evidence accounting.v1_tax_recoverable_credit_evidence%ROWTYPE;
    existing accounting.v1_tax_recoverable_credit_preparations%ROWTYPE;
    adjustment_posting accounting.v1_tax_adjustment_postings%ROWTYPE;
    adjustment_evidence accounting.v1_tax_adjustment_evidence%ROWTYPE;
    adjustment_queue accounting.v1_tax_adjustment_queue%ROWTYPE;
    target_return accounting.v1_tax_return_evidence%ROWTYPE;
    payable_account accounting.accounts%ROWTYPE;
    recoverable_account accounting.accounts%ROWTYPE;
    target_period accounting.fiscal_periods%ROWTYPE;
    item_count INTEGER;
    exact_count INTEGER;
    item_total NUMERIC(18,2);
    protected_source_event_key TEXT;
    created_journal_id UUID;
BEGIN
    PERFORM accounting.require_v1_tax_management_actor(
        p_actor_user_id,
        'accounting.tax.recoverable_credit.prepare'
    );
    IF p_credit_evidence_id IS NULL THEN
        RAISE EXCEPTION 'Tax Recoverable credit preparation requires exact immutable credit evidence.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended('v1-tax-recoverable-credit-evidence:' || p_credit_evidence_id::text, 0)
    );

    SELECT * INTO existing
    FROM accounting.v1_tax_recoverable_credit_preparations item
    WHERE item.credit_evidence_id = p_credit_evidence_id;
    IF existing.id IS NOT NULL THEN
        RETURN existing.journal_entry_id;
    END IF;

    SELECT * INTO evidence
    FROM accounting.v1_tax_recoverable_credit_evidence item
    WHERE item.id = p_credit_evidence_id
    FOR SHARE;
    IF evidence.id IS NULL THEN
        RAISE EXCEPTION 'Tax Recoverable credit evidence was not found.';
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
    SELECT * INTO target_return
    FROM accounting.v1_tax_return_evidence item
    WHERE item.id = evidence.target_tax_return_id
    FOR SHARE;
    SELECT * INTO recoverable_account
    FROM accounting.accounts account
    WHERE account.id = adjustment_posting.confirmed_debit_account_id
    FOR SHARE;
    SELECT * INTO payable_account
    FROM accounting.accounts account
    WHERE account.system_key = 'tax_payables'
    FOR SHARE;

    IF adjustment_posting.id IS NULL OR adjustment_evidence.id IS NULL
       OR adjustment_evidence.adjustment_kind <> 'recognize_settled_tax_recoverable'
       OR adjustment_queue.adjustment_status <> 'posted_settled_tax_recoverable'
       OR adjustment_posting.confirmed_adjustment_amount <> evidence.credit_amount
       OR target_return.id IS NULL OR target_return.tax_type <> evidence.tax_type
       OR target_return.declared_tax_due <> evidence.credit_amount
       OR recoverable_account.id IS NULL OR recoverable_account.system_key <> 'tax_recoverable'
       OR recoverable_account.code <> '1130' OR NOT recoverable_account.is_active
       OR NOT recoverable_account.is_posting
       OR payable_account.id IS NULL OR payable_account.system_key <> 'tax_payables'
       OR payable_account.code <> '2100' OR NOT payable_account.is_active
       OR NOT payable_account.is_posting THEN
        RAISE EXCEPTION 'Exact Tax Recoverable source, target return or 2100/1130 accounts changed after credit evidence was recorded.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM accounting.v1_tax_recoverable_refund_evidence refund
        WHERE refund.adjustment_posting_id = adjustment_posting.id
    ) THEN
        RAISE EXCEPTION 'Tax-credit preparation is blocked because cash-refund evidence now exists for this Tax Recoverable.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM accounting.v1_tax_payment_evidence payment
        WHERE payment.tax_return_id = target_return.id
    ) OR EXISTS (
        SELECT 1 FROM accounting.v1_tax_settlement_preparations preparation
        WHERE preparation.tax_return_id = target_return.id
    ) OR EXISTS (
        SELECT 1 FROM accounting.v1_tax_settlement_postings posting
        WHERE posting.tax_return_id = target_return.id
    ) OR EXISTS (
        SELECT 1 FROM accounting.v1_tax_additional_amendment_evidence amendment
        WHERE amendment.tax_return_id = target_return.id
    ) THEN
        RAISE EXCEPTION 'Target tax return is no longer exclusively available for protected Tax Recoverable credit application.';
    END IF;

    SELECT
        count(*)::integer,
        count(*) FILTER (
            WHERE posting.id IS NOT NULL
              AND source_preparation.tax_type = item.tax_type
              AND source_preparation.evidence_id = item.evidence_id
              AND source_preparation.recognition_date = item.recognition_date
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
    LEFT JOIN accounting.v1_tax_liability_preparations source_preparation
      ON source_preparation.id = posting.preparation_id
    LEFT JOIN accounting.journal_entries liability_journal
      ON liability_journal.id = posting.journal_entry_id
    LEFT JOIN accounting.v1_tax_liability_queue queue
      ON queue.tax_type = item.tax_type
     AND queue.evidence_id = item.evidence_id
     AND queue.posting_id = posting.id
    WHERE item.tax_return_id = target_return.id;

    IF item_count <= 0 OR exact_count <> item_count OR item_total <> evidence.credit_amount THEN
        RAISE EXCEPTION 'Target tax return liabilities changed before Tax Recoverable credit preparation.';
    END IF;

    SELECT * INTO target_period
    FROM accounting.fiscal_periods period
    WHERE period.status = 'open'
      AND evidence.application_date BETWEEN period.start_date AND period.end_date
    ORDER BY period.start_date DESC
    LIMIT 1
    FOR SHARE;
    IF target_period.id IS NULL THEN
        RAISE EXCEPTION 'Tax Recoverable credit application date must be inside an open fiscal period.';
    END IF;

    protected_source_event_key := 'v1_tax_recoverable_credit:' || evidence.id::text;
    IF EXISTS (
        SELECT 1 FROM accounting.journal_entries journal
        WHERE journal.source_event_key = protected_source_event_key
    ) THEN
        RAISE EXCEPTION 'Protected V1 Tax Recoverable credit source identity is already occupied outside the credit audit.';
    END IF;

    PERFORM set_config('accounting.v1_tax_recoverable_credit_journal_prepare_allowed', 'on', true);
    INSERT INTO accounting.journal_entries(
        fiscal_period_id, posting_date, description, status, source_type,
        source_reference, source_event_key, created_by_user_id, updated_at
    ) VALUES (
        target_period.id, evidence.application_date,
        'Protected V1 Tax Recoverable credit application to return ' || target_return.return_reference,
        'draft', 'v1_tax_recoverable_credit_application', evidence.id::text,
        protected_source_event_key, p_actor_user_id, now()
    ) RETURNING id INTO created_journal_id;
    PERFORM set_config('accounting.v1_tax_recoverable_credit_journal_prepare_allowed', 'off', true);

    PERFORM set_config('accounting.v1_tax_recoverable_credit_journal_line_write_allowed', 'on', true);
    INSERT INTO accounting.journal_lines(
        journal_entry_id, line_number, account_id, description, debit, credit
    ) VALUES
        (created_journal_id, 1, payable_account.id, 'Apply retained Tax Recoverable against target tax payable', evidence.credit_amount, 0),
        (created_journal_id, 2, recoverable_account.id, 'Consume legally usable 1130 Tax Recoverable credit', 0, evidence.credit_amount);
    PERFORM set_config('accounting.v1_tax_recoverable_credit_journal_line_write_allowed', 'off', true);

    INSERT INTO accounting.journal_events(journal_entry_id, event_type, actor_user_id, details)
    VALUES (
        created_journal_id, 'draft_created', p_actor_user_id,
        jsonb_build_object(
            'source_type', 'v1_tax_recoverable_credit_application',
            'credit_evidence_id', evidence.id,
            'adjustment_posting_id', evidence.adjustment_posting_id,
            'target_tax_return_id', evidence.target_tax_return_id,
            'credit_amount', evidence.credit_amount,
            'tax_payable_account_code', payable_account.code,
            'tax_recoverable_account_code', recoverable_account.code,
            'automatic_source_posting', false
        )
    );

    PERFORM set_config('accounting.v1_tax_recoverable_credit_preparation_insert_allowed', 'on', true);
    INSERT INTO accounting.v1_tax_recoverable_credit_preparations(
        credit_evidence_id, journal_entry_id, source_event_key, posting_date,
        credit_amount, tax_payable_account_id, tax_recoverable_account_id,
        fiscal_period_id, prepared_by_user_id
    ) VALUES (
        evidence.id, created_journal_id, protected_source_event_key,
        evidence.application_date, evidence.credit_amount, payable_account.id,
        recoverable_account.id, target_period.id, p_actor_user_id
    );
    PERFORM set_config('accounting.v1_tax_recoverable_credit_preparation_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id, 'accounting.tax.recoverable_credit.prepared',
        'v1_tax_recoverable_credit', evidence.id,
        jsonb_build_object(
            'target_tax_return_id', target_return.id,
            'journal_entry_id', created_journal_id,
            'credit_amount', evidence.credit_amount,
            'tax_payable_account_code', payable_account.code,
            'tax_recoverable_account_code', recoverable_account.code,
            'fiscal_period_id', target_period.id,
            'automatic_source_posting', false
        )
    );

    RETURN created_journal_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.post_v1_tax_recoverable_credit_journal(
    p_credit_evidence_id UUID,
    p_actor_user_id UUID,
    p_confirmation_token TEXT,
    p_expected_evidence_digest TEXT,
    p_expected_credit_amount NUMERIC,
    p_expected_tax_payable_account_code TEXT,
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
    normalized_amount NUMERIC(18,2) := round(coalesce(p_expected_credit_amount, -1), 2);
    normalized_payable_code TEXT := btrim(coalesce(p_expected_tax_payable_account_code, ''));
    normalized_recoverable_code TEXT := btrim(coalesce(p_expected_tax_recoverable_account_code, ''));
    evidence accounting.v1_tax_recoverable_credit_evidence%ROWTYPE;
    preparation accounting.v1_tax_recoverable_credit_preparations%ROWTYPE;
    existing accounting.v1_tax_recoverable_credit_postings%ROWTYPE;
    adjustment_posting accounting.v1_tax_adjustment_postings%ROWTYPE;
    adjustment_evidence accounting.v1_tax_adjustment_evidence%ROWTYPE;
    adjustment_queue accounting.v1_tax_adjustment_queue%ROWTYPE;
    target_return accounting.v1_tax_return_evidence%ROWTYPE;
    payable_account accounting.accounts%ROWTYPE;
    recoverable_account accounting.accounts%ROWTYPE;
    target_period accounting.fiscal_periods%ROWTYPE;
    journal accounting.journal_entries%ROWTYPE;
    item_count INTEGER;
    exact_count INTEGER;
    item_total NUMERIC(18,2);
    line_count INTEGER;
    total_debit NUMERIC(18,2);
    total_credit NUMERIC(18,2);
    payable_debit NUMERIC(18,2);
    recoverable_credit NUMERIC(18,2);
    foreign_line_count INTEGER;
    generated_entry_number TEXT;
    confirmation_digest_value TEXT;
    created_posting_id UUID;
BEGIN
    PERFORM accounting.require_v1_tax_management_actor(
        p_actor_user_id,
        'accounting.tax.recoverable_credit.post'
    );

    IF p_credit_evidence_id IS NULL
       OR p_policy_version IS DISTINCT FROM 'v1_tax_recoverable_credit_posting_v1'
       OR normalized_token !~ '^[0-9a-f]{64}$'
       OR normalized_digest !~ '^[0-9a-f]{64}$'
       OR p_expected_credit_amount IS DISTINCT FROM normalized_amount
       OR normalized_amount <= 0
       OR normalized_payable_code <> '2100'
       OR normalized_recoverable_code <> '1130'
       OR p_expected_posting_date IS NULL OR p_expected_fiscal_period_id IS NULL THEN
        RAISE EXCEPTION 'Protected Tax Recoverable credit posting requires exact Management confirmation, evidence digest, full credit amount, 2100/1130 accounts, date, period and policy.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended('v1-tax-recoverable-credit-evidence:' || p_credit_evidence_id::text, 0)
    );

    SELECT * INTO evidence
    FROM accounting.v1_tax_recoverable_credit_evidence item
    WHERE item.id = p_credit_evidence_id
    FOR SHARE;
    SELECT * INTO preparation
    FROM accounting.v1_tax_recoverable_credit_preparations item
    WHERE item.credit_evidence_id = p_credit_evidence_id
    FOR SHARE;
    IF evidence.id IS NULL OR preparation.id IS NULL THEN
        RAISE EXCEPTION 'Tax Recoverable credit must have exact immutable evidence and a protected preparation before posting.';
    END IF;

    SELECT * INTO existing
    FROM accounting.v1_tax_recoverable_credit_postings item
    WHERE item.preparation_id = preparation.id
    FOR SHARE;
    IF existing.id IS NOT NULL THEN
        IF existing.confirmation_token = normalized_token
           AND existing.confirmed_evidence_digest = normalized_digest
           AND existing.confirmed_credit_amount = normalized_amount
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
                WHERE account.id = existing.confirmed_tax_recoverable_account_id
                  AND account.code = normalized_recoverable_code
           ) THEN
            RETURN existing.id;
        END IF;
        RAISE EXCEPTION 'Existing V1 Tax Recoverable credit posting does not match the immutable retry identity.';
    END IF;

    IF evidence.evidence_digest <> normalized_digest
       OR evidence.credit_amount <> normalized_amount
       OR evidence.application_date <> p_expected_posting_date
       OR preparation.posting_date <> p_expected_posting_date
       OR preparation.credit_amount <> normalized_amount THEN
        RAISE EXCEPTION 'Exact immutable Tax Recoverable credit evidence no longer matches the confirmed posting coordinates.';
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
    SELECT * INTO target_return
    FROM accounting.v1_tax_return_evidence item
    WHERE item.id = evidence.target_tax_return_id
    FOR SHARE;

    IF adjustment_posting.id IS NULL OR adjustment_evidence.id IS NULL
       OR adjustment_evidence.adjustment_kind <> 'recognize_settled_tax_recoverable'
       OR adjustment_queue.adjustment_status <> 'posted_settled_tax_recoverable'
       OR adjustment_posting.confirmed_adjustment_amount <> normalized_amount
       OR target_return.id IS NULL OR target_return.tax_type <> evidence.tax_type
       OR target_return.declared_tax_due <> normalized_amount THEN
        RAISE EXCEPTION 'Exact posted Tax Recoverable source or target return changed before credit posting.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM accounting.v1_tax_recoverable_refund_evidence refund
        WHERE refund.adjustment_posting_id = adjustment_posting.id
    ) OR EXISTS (
        SELECT 1 FROM accounting.v1_tax_payment_evidence payment
        WHERE payment.tax_return_id = target_return.id
    ) OR EXISTS (
        SELECT 1 FROM accounting.v1_tax_settlement_preparations settlement
        WHERE settlement.tax_return_id = target_return.id
    ) OR EXISTS (
        SELECT 1 FROM accounting.v1_tax_settlement_postings settlement
        WHERE settlement.tax_return_id = target_return.id
    ) OR EXISTS (
        SELECT 1 FROM accounting.v1_tax_additional_amendment_evidence amendment
        WHERE amendment.tax_return_id = target_return.id
    ) THEN
        RAISE EXCEPTION 'Competing refund, cash settlement or amendment evidence appeared before Tax Recoverable credit posting.';
    END IF;

    SELECT
        count(*)::integer,
        count(*) FILTER (
            WHERE posting.id IS NOT NULL
              AND source_preparation.tax_type = item.tax_type
              AND source_preparation.evidence_id = item.evidence_id
              AND source_preparation.recognition_date = item.recognition_date
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
    LEFT JOIN accounting.v1_tax_liability_preparations source_preparation
      ON source_preparation.id = posting.preparation_id
    LEFT JOIN accounting.journal_entries liability_journal
      ON liability_journal.id = posting.journal_entry_id
    LEFT JOIN accounting.v1_tax_liability_queue queue
      ON queue.tax_type = item.tax_type
     AND queue.evidence_id = item.evidence_id
     AND queue.posting_id = posting.id
    WHERE item.tax_return_id = target_return.id;

    IF item_count <= 0 OR exact_count <> item_count OR item_total <> normalized_amount THEN
        RAISE EXCEPTION 'Target tax return liabilities changed before Tax Recoverable credit posting.';
    END IF;

    SELECT * INTO payable_account
    FROM accounting.accounts account
    WHERE account.id = preparation.tax_payable_account_id
    FOR SHARE;
    SELECT * INTO recoverable_account
    FROM accounting.accounts account
    WHERE account.id = preparation.tax_recoverable_account_id
    FOR SHARE;
    IF payable_account.id IS NULL OR payable_account.system_key <> 'tax_payables'
       OR payable_account.code <> normalized_payable_code
       OR payable_account.account_type <> 'liability' OR payable_account.normal_balance <> 'credit'
       OR NOT payable_account.is_active OR NOT payable_account.is_posting
       OR recoverable_account.id IS NULL
       OR recoverable_account.id <> adjustment_posting.confirmed_debit_account_id
       OR recoverable_account.system_key <> 'tax_recoverable'
       OR recoverable_account.code <> normalized_recoverable_code
       OR recoverable_account.account_type <> 'asset' OR recoverable_account.normal_balance <> 'debit'
       OR NOT recoverable_account.is_active OR NOT recoverable_account.is_posting THEN
        RAISE EXCEPTION 'Exact confirmed 2100 Tax Payables / 1130 Tax Recoverable accounts are no longer posting-ready.';
    END IF;

    SELECT * INTO target_period
    FROM accounting.fiscal_periods period
    WHERE period.id = p_expected_fiscal_period_id
    FOR SHARE;
    IF target_period.id IS NULL OR target_period.status <> 'open'
       OR p_expected_posting_date NOT BETWEEN target_period.start_date AND target_period.end_date
       OR preparation.fiscal_period_id <> target_period.id THEN
        RAISE EXCEPTION 'Tax Recoverable credit posting requires the exact still-open fiscal period used at preparation.';
    END IF;

    SELECT * INTO journal
    FROM accounting.journal_entries item
    WHERE item.id = preparation.journal_entry_id
    FOR UPDATE;
    IF journal.id IS NULL OR journal.status <> 'draft'
       OR journal.source_type <> 'v1_tax_recoverable_credit_application'
       OR journal.source_reference <> evidence.id::text
       OR journal.source_event_key <> preparation.source_event_key
       OR journal.posting_date <> p_expected_posting_date
       OR journal.fiscal_period_id <> target_period.id
       OR journal.reversal_of_entry_id IS NOT NULL THEN
        RAISE EXCEPTION 'Prepared V1 Tax Recoverable credit General Journal draft no longer matches the protected application coordinates.';
    END IF;

    SELECT
        count(*)::integer,
        coalesce(sum(line.debit), 0)::numeric(18,2),
        coalesce(sum(line.credit), 0)::numeric(18,2),
        coalesce(sum(line.debit) FILTER (WHERE line.account_id = payable_account.id), 0)::numeric(18,2),
        coalesce(sum(line.credit) FILTER (WHERE line.account_id = recoverable_account.id), 0)::numeric(18,2),
        count(*) FILTER (
            WHERE line.account_id NOT IN (payable_account.id, recoverable_account.id)
               OR line.client_id IS NOT NULL
               OR line.loan_id IS NOT NULL
        )::integer
    INTO line_count, total_debit, total_credit, payable_debit, recoverable_credit, foreign_line_count
    FROM accounting.journal_lines line
    WHERE line.journal_entry_id = journal.id;

    IF line_count <> 2 OR total_debit <> normalized_amount OR total_credit <> normalized_amount
       OR payable_debit <> normalized_amount OR recoverable_credit <> normalized_amount
       OR foreign_line_count <> 0 THEN
        RAISE EXCEPTION 'Prepared V1 Tax Recoverable credit lines do not exactly reconcile Dr 2100 Tax Payables / Cr 1130 Tax Recoverable to retained application evidence.';
    END IF;

    confirmation_digest_value := encode(sha256(convert_to(concat_ws('|',
        p_policy_version, evidence.id::text, evidence.adjustment_posting_id::text,
        evidence.target_tax_return_id::text, normalized_digest,
        to_char(normalized_amount, 'FM999999999999990.00'),
        payable_account.id::text, recoverable_account.id::text,
        p_expected_posting_date::text, target_period.id::text,
        journal.id::text, normalized_token
    ), 'UTF8')), 'hex');

    PERFORM set_config('accounting.v1_tax_recoverable_credit_journal_post_allowed', 'on', true);
    generated_entry_number := accounting.post_journal_entry(journal.id, p_actor_user_id);
    PERFORM set_config('accounting.v1_tax_recoverable_credit_journal_post_allowed', 'off', true);

    IF coalesce(current_setting('accounting.v1_tax_recoverable_credit_force_audit_failure', true), '') = 'on' THEN
        RAISE EXCEPTION 'Forced V1 Tax Recoverable credit audit failure.';
    END IF;

    PERFORM set_config('accounting.v1_tax_recoverable_credit_posting_insert_allowed', 'on', true);
    INSERT INTO accounting.v1_tax_recoverable_credit_postings(
        preparation_id, credit_evidence_id, adjustment_posting_id,
        target_tax_return_id, journal_entry_id, entry_number,
        confirmation_token, confirmation_digest, confirmed_evidence_digest,
        confirmed_credit_amount, confirmed_tax_payable_account_id,
        confirmed_tax_recoverable_account_id, confirmed_posting_date,
        confirmed_fiscal_period_id, policy_version, posted_by_user_id
    ) VALUES (
        preparation.id, evidence.id, evidence.adjustment_posting_id,
        evidence.target_tax_return_id, journal.id, generated_entry_number,
        normalized_token, confirmation_digest_value, normalized_digest,
        normalized_amount, payable_account.id, recoverable_account.id,
        p_expected_posting_date, target_period.id, p_policy_version,
        p_actor_user_id
    ) RETURNING id INTO created_posting_id;
    PERFORM set_config('accounting.v1_tax_recoverable_credit_posting_insert_allowed', 'off', true);

    INSERT INTO accounting.journal_events(journal_entry_id, event_type, actor_user_id, details)
    VALUES (
        journal.id, 'posted', p_actor_user_id,
        jsonb_build_object(
            'entry_number', generated_entry_number,
            'source_type', 'v1_tax_recoverable_credit_application',
            'credit_evidence_id', evidence.id,
            'adjustment_posting_id', evidence.adjustment_posting_id,
            'target_tax_return_id', evidence.target_tax_return_id,
            'confirmation_digest', confirmation_digest_value,
            'automatic_source_posting', false
        )
    );

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id, 'accounting.tax.recoverable_credit.posted',
        'v1_tax_recoverable_credit', evidence.id,
        jsonb_build_object(
            'journal_entry_id', journal.id,
            'entry_number', generated_entry_number,
            'target_tax_return_id', target_return.id,
            'credit_amount', normalized_amount,
            'tax_payable_account_code', payable_account.code,
            'tax_recoverable_account_code', recoverable_account.code,
            'confirmation_digest', confirmation_digest_value,
            'full_only', true,
            'automatic_source_posting', false
        )
    );

    RETURN created_posting_id;
END;
$$;

CREATE OR REPLACE VIEW accounting.v1_tax_recoverable_credit_queue AS
SELECT
    evidence.id AS credit_evidence_id,
    evidence.adjustment_posting_id,
    evidence.adjustment_evidence_id,
    evidence.tax_type,
    adjustment.source_id,
    adjustment.loan_id,
    adjustment.client_id,
    evidence.target_tax_return_id,
    target_return.return_period_start AS target_return_period_start,
    target_return.return_period_end AS target_return_period_end,
    target_return.filing_date AS target_filing_date,
    target_return.declared_tax_due AS target_declared_tax_due,
    target_return.return_reference AS target_return_reference,
    target_return.evidence_digest AS target_return_evidence_digest,
    evidence.credit_amount,
    evidence.application_date,
    evidence.application_reference,
    evidence.authority_reference,
    evidence.evidence_digest,
    evidence.recorded_by_user_id,
    evidence.recorded_at,
    preparation.id AS preparation_id,
    preparation.journal_entry_id,
    journal.status AS journal_status,
    journal.entry_number,
    preparation.fiscal_period_id,
    preparation.tax_payable_account_id,
    payable.code AS tax_payable_account_code,
    payable.name AS tax_payable_account_name,
    preparation.tax_recoverable_account_id,
    recoverable.code AS tax_recoverable_account_code,
    recoverable.name AS tax_recoverable_account_name,
    preparation.prepared_by_user_id,
    preparation.prepared_at,
    posting.id AS credit_posting_id,
    posting.confirmation_digest,
    posting.posted_by_user_id,
    posting.posted_at,
    CASE
        WHEN posting.id IS NOT NULL THEN 'credit_applied'
        WHEN adjustment.adjustment_status <> 'posted_settled_tax_recoverable'
            THEN 'blocked_recoverable_not_current'
        WHEN refund.id IS NOT NULL THEN 'blocked_competing_refund_evidence'
        WHEN payment.id IS NOT NULL OR cash_settlement.id IS NOT NULL
            THEN 'blocked_target_cash_settlement'
        WHEN amendment.id IS NOT NULL THEN 'blocked_target_amendment'
        WHEN composition.liability_count <= 0
          OR composition.current_exact_count <> composition.liability_count
          OR composition.liability_total <> evidence.credit_amount
            THEN 'blocked_target_return_changed'
        WHEN payable.id IS NULL OR payable.system_key <> 'tax_payables'
          OR payable.code <> '2100' OR NOT payable.is_active OR NOT payable.is_posting
            THEN 'blocked_tax_payable_account'
        WHEN recoverable.id IS NULL OR recoverable.system_key <> 'tax_recoverable'
          OR recoverable.code <> '1130' OR NOT recoverable.is_active OR NOT recoverable.is_posting
            THEN 'blocked_tax_recoverable_account'
        WHEN preparation.id IS NOT NULL AND journal.status IS DISTINCT FROM 'draft'
            THEN 'blocked_untracked_credit_journal_state'
        WHEN open_period.id IS NULL THEN 'blocked_no_open_application_period'
        WHEN preparation.id IS NOT NULL THEN 'credit_prepared'
        ELSE 'credit_evidence_ready'
    END AS credit_status,
    CASE
        WHEN posting.id IS NOT NULL THEN NULL
        WHEN adjustment.adjustment_status <> 'posted_settled_tax_recoverable'
            THEN 'Underlying 1130 Tax Recoverable adjustment is no longer in the exact current posted state retained by this credit evidence.'
        WHEN refund.id IS NOT NULL
            THEN 'Competing immutable cash-refund evidence exists for the same Tax Recoverable.'
        WHEN payment.id IS NOT NULL OR cash_settlement.id IS NOT NULL
            THEN 'Target tax return has cash-payment/settlement evidence and cannot also consume this Tax Recoverable.'
        WHEN amendment.id IS NOT NULL
            THEN 'Target tax return is reserved by an additional-tax amendment.'
        WHEN composition.liability_count <= 0
          OR composition.current_exact_count <> composition.liability_count
          OR composition.liability_total <> evidence.credit_amount
            THEN 'Target return liabilities are no longer exact current posted liabilities equal to the retained full credit amount.'
        WHEN payable.id IS NULL OR payable.system_key <> 'tax_payables'
          OR payable.code <> '2100' OR NOT payable.is_active OR NOT payable.is_posting
            THEN 'Exact 2100 Tax Payables is no longer posting-ready.'
        WHEN recoverable.id IS NULL OR recoverable.system_key <> 'tax_recoverable'
          OR recoverable.code <> '1130' OR NOT recoverable.is_active OR NOT recoverable.is_posting
            THEN 'Exact 1130 Tax Recoverable is no longer posting-ready.'
        WHEN preparation.id IS NOT NULL AND journal.status IS DISTINCT FROM 'draft'
            THEN 'Prepared credit journal is not a draft but has no immutable protected credit posting audit.'
        WHEN open_period.id IS NULL
            THEN 'Retained credit-application date is not inside an open accounting period.'
        WHEN preparation.id IS NOT NULL
            THEN 'Exact Management confirmation is required before protected Tax Recoverable credit posting.'
        ELSE NULL
    END AS credit_blocker,
    true AS tax_recoverable_refund_realization_enabled,
    true AS tax_recoverable_credit_application_enabled,
    false AS partial_tax_recoverable_realization_enabled,
    false AS automatic_source_posting
FROM accounting.v1_tax_recoverable_credit_evidence evidence
JOIN accounting.v1_tax_adjustment_postings adjustment_posting
  ON adjustment_posting.id = evidence.adjustment_posting_id
LEFT JOIN accounting.v1_tax_adjustment_queue adjustment
  ON adjustment.adjustment_posting_id = adjustment_posting.id
JOIN accounting.v1_tax_return_evidence target_return
  ON target_return.id = evidence.target_tax_return_id
LEFT JOIN accounting.v1_tax_recoverable_refund_evidence refund
  ON refund.adjustment_posting_id = evidence.adjustment_posting_id
LEFT JOIN accounting.v1_tax_payment_evidence payment
  ON payment.tax_return_id = evidence.target_tax_return_id
LEFT JOIN accounting.v1_tax_settlement_postings cash_settlement
  ON cash_settlement.tax_return_id = evidence.target_tax_return_id
LEFT JOIN accounting.v1_tax_additional_amendment_evidence amendment
  ON amendment.tax_return_id = evidence.target_tax_return_id
LEFT JOIN accounting.v1_tax_recoverable_credit_preparations preparation
  ON preparation.credit_evidence_id = evidence.id
LEFT JOIN accounting.journal_entries journal
  ON journal.id = preparation.journal_entry_id
LEFT JOIN accounting.accounts payable
  ON payable.id = coalesce(
      preparation.tax_payable_account_id,
      (SELECT account.id FROM accounting.accounts account WHERE account.system_key = 'tax_payables' LIMIT 1)
  )
LEFT JOIN accounting.accounts recoverable
  ON recoverable.id = coalesce(preparation.tax_recoverable_account_id, adjustment_posting.confirmed_debit_account_id)
LEFT JOIN accounting.v1_tax_recoverable_credit_postings posting
  ON posting.preparation_id = preparation.id
LEFT JOIN LATERAL (
    SELECT
        count(*)::integer AS liability_count,
        count(*) FILTER (
            WHERE liability_posting.id IS NOT NULL
              AND liability_preparation.tax_type = item.tax_type
              AND liability_preparation.evidence_id = item.evidence_id
              AND liability_preparation.recognition_date = item.recognition_date
              AND liability_posting.confirmed_tax_due = item.tax_due
              AND liability_posting.entry_number = item.liability_entry_number
              AND liability_journal.status = 'posted'
              AND liability_journal.entry_number = liability_posting.entry_number
              AND liability_queue.accounting_status = 'posted'
        )::integer AS current_exact_count,
        coalesce(sum(item.tax_due), 0)::numeric(18,2) AS liability_total
    FROM accounting.v1_tax_return_liability_items item
    LEFT JOIN accounting.v1_tax_liability_postings liability_posting
      ON liability_posting.id = item.tax_liability_posting_id
    LEFT JOIN accounting.v1_tax_liability_preparations liability_preparation
      ON liability_preparation.id = liability_posting.preparation_id
    LEFT JOIN accounting.journal_entries liability_journal
      ON liability_journal.id = liability_posting.journal_entry_id
    LEFT JOIN accounting.v1_tax_liability_queue liability_queue
      ON liability_queue.tax_type = item.tax_type
     AND liability_queue.evidence_id = item.evidence_id
     AND liability_queue.posting_id = liability_posting.id
    WHERE item.tax_return_id = target_return.id
) composition ON true
LEFT JOIN LATERAL (
    SELECT period.id
    FROM accounting.fiscal_periods period
    WHERE period.status = 'open'
      AND evidence.application_date BETWEEN period.start_date AND period.end_date
      AND (preparation.fiscal_period_id IS NULL OR preparation.fiscal_period_id = period.id)
    ORDER BY period.start_date DESC
    LIMIT 1
) open_period ON true;

CREATE OR REPLACE VIEW accounting.v1_tax_recoverable_credit_summary AS
SELECT
    count(*)::bigint AS credit_evidence_count,
    count(*) FILTER (WHERE credit_status = 'credit_evidence_ready')::bigint AS ready_to_prepare_count,
    count(*) FILTER (WHERE credit_status = 'credit_prepared')::bigint AS prepared_count,
    count(*) FILTER (WHERE credit_status = 'credit_applied')::bigint AS applied_count,
    count(*) FILTER (WHERE credit_status LIKE 'blocked_%')::bigint AS blocked_count,
    coalesce(sum(credit_amount) FILTER (WHERE credit_status = 'credit_applied'), 0)::numeric(18,2) AS applied_credit_total,
    true AS tax_recoverable_refund_realization_enabled,
    true AS tax_recoverable_credit_application_enabled,
    false AS partial_tax_recoverable_realization_enabled,
    false AS automatic_source_posting
FROM accounting.v1_tax_recoverable_credit_queue;

CREATE OR REPLACE VIEW accounting.v1_tax_recoverable_controls AS
SELECT
    true AS tax_recoverable_refund_realization_enabled,
    true AS tax_recoverable_credit_application_enabled,
    false AS partial_tax_recoverable_realization_enabled,
    false AS automatic_source_posting;

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
        WHEN credit.id IS NOT NULL THEN 'blocked_competing_credit_evidence'
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
        WHEN credit.id IS NOT NULL
            THEN 'Competing immutable Tax Recoverable credit evidence exists for the same recoverable.'
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
    true AS tax_recoverable_credit_application_enabled,
    false AS automatic_source_posting
FROM accounting.v1_tax_recoverable_refund_evidence evidence
JOIN accounting.v1_tax_adjustment_postings adjustment_posting
  ON adjustment_posting.id = evidence.adjustment_posting_id
LEFT JOIN accounting.v1_tax_adjustment_queue adjustment
  ON adjustment.adjustment_posting_id = adjustment_posting.id
LEFT JOIN accounting.v1_tax_recoverable_credit_evidence credit
  ON credit.adjustment_posting_id = evidence.adjustment_posting_id
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
    true AS tax_recoverable_credit_application_enabled,
    false AS automatic_source_posting
FROM accounting.v1_tax_recoverable_refund_queue;

COMMENT ON TABLE accounting.v1_tax_recoverable_credit_evidence IS
'Immutable Management-approved evidence that one exact posted 1130 Tax Recoverable is legally usable and actually applied in full against one exact same-tax-type unpaid retained V1 tax return. Amount is derived from the protected adjustment posting.';
COMMENT ON TABLE accounting.v1_tax_recoverable_credit_postings IS
'Immutable protected posting audit for full tax-credit application of 1130 Tax Recoverable: Dr 2100 Tax Payables / Cr 1130 Tax Recoverable for the exact retained amount.';
COMMENT ON VIEW accounting.v1_tax_recoverable_controls IS
'V1 A6.2 Tax Recoverable controls. Full cash-refund realization and full same-tax-type base-return credit application are protected; partial/mixed realization and automatic source posting remain disabled.';

COMMIT;
