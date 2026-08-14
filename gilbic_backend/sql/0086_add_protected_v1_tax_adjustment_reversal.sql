BEGIN;

-- Master #296 A6.2 adjustment/reversal core.
-- This slice never rewrites a posted liability or settlement. It supports only two
-- fail-closed correction states from exact superseded tax evidence:
--   1) an unpaid stale liability may be fully reversed while its original period is
--      still open, after retained Management adjustment evidence; and
--   2) a stale liability that was already fully settled may recognize only the exact
--      supported decrease as Tax Recoverable, preserving the original cash settlement.
-- Additional-tax amendments and later refund/credit realization remain explicit later
-- evidence events; this migration does not infer them and automatic posting stays off.

INSERT INTO core.permissions (code, description)
VALUES
    ('accounting.tax.adjustment_evidence.record', 'Record immutable Management-approved V1 tax correction/adjustment evidence for one stale posted tax liability'),
    ('accounting.tax.adjustment.prepare', 'Prepare a protected V1 tax adjustment/reversal General Journal draft from exact correction evidence'),
    ('accounting.tax.adjustment.post', 'Post a protected V1 tax adjustment/reversal General Journal after exact Management confirmation')
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code IN (
      'accounting.tax.adjustment_evidence.record',
      'accounting.tax.adjustment.prepare',
      'accounting.tax.adjustment.post'
  )
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

INSERT INTO accounting.accounts (
    code, system_key, name, account_type, normal_balance, is_posting
)
VALUES
    ('1130', 'tax_recoverable', 'Tax Recoverable', 'asset', 'debit', true)
ON CONFLICT (system_key) DO UPDATE SET
    code = excluded.code,
    name = excluded.name,
    account_type = excluded.account_type,
    normal_balance = excluded.normal_balance,
    is_posting = excluded.is_posting,
    is_active = true,
    updated_at = now();

CREATE TABLE IF NOT EXISTS accounting.v1_tax_adjustment_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key UUID NOT NULL UNIQUE,
    adjustment_kind TEXT NOT NULL CHECK (
        adjustment_kind IN (
            'reverse_unsettled_liability',
            'recognize_settled_tax_recoverable'
        )
    ),
    tax_type TEXT NOT NULL CHECK (
        tax_type IN ('documentary_stamp_tax', 'percentage_tax_lending')
    ),
    tax_liability_posting_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_liability_postings(id) ON DELETE RESTRICT,
    original_evidence_id UUID NOT NULL,
    replacement_evidence_id UUID NOT NULL,
    original_tax_due NUMERIC(18,2) NOT NULL CHECK (original_tax_due > 0),
    replacement_tax_due NUMERIC(18,2) NOT NULL CHECK (replacement_tax_due >= 0),
    adjustment_amount NUMERIC(18,2) NOT NULL CHECK (adjustment_amount > 0),
    original_liability_journal_entry_id UUID NOT NULL
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    settlement_posting_id UUID
        REFERENCES accounting.v1_tax_settlement_postings(id) ON DELETE RESTRICT,
    original_settlement_journal_entry_id UUID
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    adjustment_date DATE NOT NULL,
    adjustment_reference TEXT NOT NULL CHECK (btrim(adjustment_reference) <> ''),
    evidence_reference TEXT NOT NULL CHECK (btrim(evidence_reference) <> ''),
    evidence_digest TEXT NOT NULL CHECK (evidence_digest ~ '^[0-9a-f]{64}$'),
    evidence_note TEXT NOT NULL CHECK (length(btrim(evidence_note)) >= 20),
    recorded_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (original_evidence_id <> replacement_evidence_id),
    CHECK (
        (
            adjustment_kind = 'reverse_unsettled_liability'
            AND settlement_posting_id IS NULL
            AND original_settlement_journal_entry_id IS NULL
            AND adjustment_amount = original_tax_due
        )
        OR
        (
            adjustment_kind = 'recognize_settled_tax_recoverable'
            AND settlement_posting_id IS NOT NULL
            AND original_settlement_journal_entry_id IS NOT NULL
            AND original_tax_due > replacement_tax_due
            AND adjustment_amount = original_tax_due - replacement_tax_due
        )
    )
);

CREATE INDEX IF NOT EXISTS v1_tax_adjustment_evidence_date_idx
    ON accounting.v1_tax_adjustment_evidence(adjustment_date DESC, recorded_at DESC);
CREATE INDEX IF NOT EXISTS v1_tax_adjustment_replacement_idx
    ON accounting.v1_tax_adjustment_evidence(tax_type, replacement_evidence_id);

CREATE TABLE IF NOT EXISTS accounting.v1_tax_adjustment_preparations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    adjustment_evidence_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_adjustment_evidence(id) ON DELETE RESTRICT,
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    source_event_key TEXT NOT NULL UNIQUE CHECK (btrim(source_event_key) <> ''),
    original_liability_journal_entry_id UUID NOT NULL
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    adjustment_kind TEXT NOT NULL CHECK (
        adjustment_kind IN (
            'reverse_unsettled_liability',
            'recognize_settled_tax_recoverable'
        )
    ),
    posting_date DATE NOT NULL,
    adjustment_amount NUMERIC(18,2) NOT NULL CHECK (adjustment_amount > 0),
    debit_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    credit_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    fiscal_period_id UUID NOT NULL REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    prepared_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    prepared_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS accounting.v1_tax_adjustment_postings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    preparation_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_adjustment_preparations(id) ON DELETE RESTRICT,
    adjustment_evidence_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_adjustment_evidence(id) ON DELETE RESTRICT,
    tax_liability_posting_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_liability_postings(id) ON DELETE RESTRICT,
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    entry_number TEXT NOT NULL UNIQUE CHECK (btrim(entry_number) <> ''),
    confirmation_token TEXT NOT NULL CHECK (confirmation_token ~ '^[0-9a-f]{64}$'),
    confirmation_digest TEXT NOT NULL CHECK (confirmation_digest ~ '^[0-9a-f]{64}$'),
    confirmed_evidence_digest TEXT NOT NULL CHECK (confirmed_evidence_digest ~ '^[0-9a-f]{64}$'),
    confirmed_original_tax_due NUMERIC(18,2) NOT NULL CHECK (confirmed_original_tax_due > 0),
    confirmed_replacement_tax_due NUMERIC(18,2) NOT NULL CHECK (confirmed_replacement_tax_due >= 0),
    confirmed_adjustment_amount NUMERIC(18,2) NOT NULL CHECK (confirmed_adjustment_amount > 0),
    confirmed_debit_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    confirmed_credit_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    confirmed_posting_date DATE NOT NULL,
    confirmed_fiscal_period_id UUID NOT NULL REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    policy_version TEXT NOT NULL CHECK (policy_version = 'v1_tax_adjustment_posting_v1'),
    posted_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    posted_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE OR REPLACE FUNCTION accounting.guard_v1_tax_adjustment_immutable_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    insert_allowed BOOLEAN := false;
BEGIN
    IF TG_TABLE_NAME = 'v1_tax_adjustment_evidence' THEN
        insert_allowed := coalesce(current_setting('accounting.v1_tax_adjustment_evidence_insert_allowed', true), '') = 'on';
    ELSIF TG_TABLE_NAME = 'v1_tax_adjustment_preparations' THEN
        insert_allowed := coalesce(current_setting('accounting.v1_tax_adjustment_preparation_insert_allowed', true), '') = 'on';
    ELSIF TG_TABLE_NAME = 'v1_tax_adjustment_postings' THEN
        insert_allowed := coalesce(current_setting('accounting.v1_tax_adjustment_posting_insert_allowed', true), '') = 'on';
    END IF;

    IF TG_OP = 'INSERT' AND insert_allowed THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'V1 tax adjustment evidence and audit rows are immutable and must use the protected Management workflow.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_v1_tax_adjustment_evidence_guard
    ON accounting.v1_tax_adjustment_evidence;
CREATE TRIGGER accounting_v1_tax_adjustment_evidence_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.v1_tax_adjustment_evidence
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_adjustment_immutable_write();

DROP TRIGGER IF EXISTS accounting_v1_tax_adjustment_preparation_guard
    ON accounting.v1_tax_adjustment_preparations;
CREATE TRIGGER accounting_v1_tax_adjustment_preparation_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.v1_tax_adjustment_preparations
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_adjustment_immutable_write();

DROP TRIGGER IF EXISTS accounting_v1_tax_adjustment_posting_guard
    ON accounting.v1_tax_adjustment_postings;
CREATE TRIGGER accounting_v1_tax_adjustment_posting_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.v1_tax_adjustment_postings
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_adjustment_immutable_write();

-- Harden the existing preparation insert gate so a replacement evidence item that is
-- already economically covered by a posted settled-tax-recoverable adjustment cannot
-- later create a second full tax liability.
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
        IF EXISTS (
            SELECT 1
            FROM accounting.v1_tax_adjustment_evidence adjustment
            JOIN accounting.v1_tax_adjustment_postings posted
              ON posted.adjustment_evidence_id = adjustment.id
            WHERE adjustment.tax_type = NEW.tax_type
              AND adjustment.replacement_evidence_id = NEW.evidence_id
              AND adjustment.adjustment_kind = 'recognize_settled_tax_recoverable'
        ) THEN
            RAISE EXCEPTION 'Replacement tax evidence is already covered by a posted settled-tax-recoverable adjustment and cannot create a duplicate full liability.';
        END IF;
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'V1 tax-liability preparation audit is immutable and must use the protected Management preparation function.';
END;
$$;

-- Permit reversal_of_entry_id against a protected V1 tax liability only inside the
-- protected adjustment preparation session. Manual General Journal reversal remains blocked.
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
            IF reversed_source = 'v1_tax_liability'
               AND NOT (
                    NEW.source_type = 'v1_tax_adjustment'
                    AND coalesce(
                        current_setting('accounting.v1_tax_liability_adjustment_reversal_allowed', true),
                        ''
                    ) = 'on'
               ) THEN
                RAISE EXCEPTION 'Posted V1 tax liabilities cannot be reversed through the manual General Journal; use the protected tax adjustment/reversal workflow.';
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.source_type IS DISTINCT FROM 'v1_tax_liability' THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
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

CREATE OR REPLACE FUNCTION accounting.guard_v1_tax_adjustment_journal_entry_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    reversed_source TEXT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF (
            NEW.source_type = 'v1_tax_adjustment'
            OR coalesce(NEW.source_event_key, '') LIKE 'v1_tax_adjustment:%'
        )
        AND coalesce(current_setting('accounting.v1_tax_adjustment_journal_prepare_allowed', true), '') <> 'on' THEN
            RAISE EXCEPTION 'V1 tax adjustment journals must use the protected Management adjustment preparation function.';
        END IF;

        IF NEW.reversal_of_entry_id IS NOT NULL THEN
            SELECT item.source_type INTO reversed_source
            FROM accounting.journal_entries item
            WHERE item.id = NEW.reversal_of_entry_id;
            IF NEW.source_type = 'v1_tax_adjustment'
               AND reversed_source <> 'v1_tax_liability' THEN
                RAISE EXCEPTION 'A protected V1 tax adjustment reversal may reference only the exact original V1 tax-liability journal.';
            END IF;
            IF reversed_source = 'v1_tax_adjustment' THEN
                RAISE EXCEPTION 'Posted V1 tax adjustments cannot be reversed through the manual General Journal; a new protected adjustment evidence event is required.';
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.source_type IS DISTINCT FROM 'v1_tax_adjustment' THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'V1 tax adjustment journals are immutable and cannot be deleted.';
    END IF;

    IF OLD.status = 'draft' AND NEW.status = 'posted' THEN
        IF coalesce(current_setting('accounting.v1_tax_adjustment_journal_post_allowed', true), '') <> 'on' THEN
            RAISE EXCEPTION 'V1 tax adjustment journals require the protected Management adjustment posting function.';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'V1 tax adjustment journals are system generated and immutable.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_v1_tax_adjustment_journal_entry_guard
    ON accounting.journal_entries;
CREATE TRIGGER accounting_v1_tax_adjustment_journal_entry_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_adjustment_journal_entry_change();

CREATE OR REPLACE FUNCTION accounting.guard_v1_tax_adjustment_journal_line_change()
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

    IF target_source_type = 'v1_tax_adjustment'
       AND coalesce(current_setting('accounting.v1_tax_adjustment_journal_line_write_allowed', true), '') <> 'on' THEN
        RAISE EXCEPTION 'V1 tax adjustment journal lines are system generated and immutable.';
    END IF;

    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_v1_tax_adjustment_journal_line_guard
    ON accounting.journal_lines;
CREATE TRIGGER accounting_v1_tax_adjustment_journal_line_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_lines
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_adjustment_journal_line_change();

CREATE OR REPLACE FUNCTION accounting.record_v1_tax_adjustment_evidence(
    p_actor_user_id UUID,
    p_idempotency_key UUID,
    p_tax_liability_posting_id UUID,
    p_replacement_evidence_id UUID,
    p_adjustment_kind TEXT,
    p_adjustment_date DATE,
    p_adjustment_reference TEXT,
    p_evidence_reference TEXT,
    p_evidence_digest TEXT,
    p_evidence_note TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    normalized_kind TEXT := btrim(coalesce(p_adjustment_kind, ''));
    normalized_adjustment_reference TEXT := btrim(coalesce(p_adjustment_reference, ''));
    normalized_evidence_reference TEXT := btrim(coalesce(p_evidence_reference, ''));
    normalized_digest TEXT := lower(btrim(coalesce(p_evidence_digest, '')));
    normalized_note TEXT := btrim(coalesce(p_evidence_note, ''));
    original_posting accounting.v1_tax_liability_postings%ROWTYPE;
    original_preparation accounting.v1_tax_liability_preparations%ROWTYPE;
    original_queue accounting.v1_tax_liability_queue%ROWTYPE;
    replacement_queue accounting.v1_tax_liability_queue%ROWTYPE;
    original_journal accounting.journal_entries%ROWTYPE;
    original_period accounting.fiscal_periods%ROWTYPE;
    linked_return_id UUID;
    linked_payment_id UUID;
    linked_settlement accounting.v1_tax_settlement_postings%ROWTYPE;
    linked_settlement_journal accounting.journal_entries%ROWTYPE;
    existing accounting.v1_tax_adjustment_evidence%ROWTYPE;
    adjustment_amount_value NUMERIC(18,2);
    created_id UUID;
BEGIN
    PERFORM accounting.require_v1_tax_management_actor(
        p_actor_user_id,
        'accounting.tax.adjustment_evidence.record'
    );

    IF p_idempotency_key IS NULL
       OR p_tax_liability_posting_id IS NULL
       OR p_replacement_evidence_id IS NULL
       OR normalized_kind NOT IN (
            'reverse_unsettled_liability',
            'recognize_settled_tax_recoverable'
       )
       OR p_adjustment_date IS NULL
       OR normalized_adjustment_reference = ''
       OR normalized_evidence_reference = ''
       OR normalized_digest !~ '^[0-9a-f]{64}$'
       OR length(normalized_note) < 20 THEN
        RAISE EXCEPTION 'Tax adjustment evidence requires exact stale liability, current replacement evidence, supported adjustment kind/date, retained references/digest and substantive note.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended('v1-tax-adjustment-liability:' || p_tax_liability_posting_id::text, 0)
    );

    SELECT * INTO original_posting
    FROM accounting.v1_tax_liability_postings item
    WHERE item.id = p_tax_liability_posting_id
    FOR SHARE;
    IF original_posting.id IS NULL THEN
        RAISE EXCEPTION 'Original posted V1 tax liability was not found for adjustment evidence.';
    END IF;

    SELECT * INTO original_preparation
    FROM accounting.v1_tax_liability_preparations item
    WHERE item.id = original_posting.preparation_id
    FOR SHARE;
    SELECT * INTO original_journal
    FROM accounting.journal_entries item
    WHERE item.id = original_posting.journal_entry_id
    FOR SHARE;
    SELECT * INTO original_queue
    FROM accounting.v1_tax_liability_queue queue
    WHERE queue.posting_id = original_posting.id
      AND queue.tax_type = original_preparation.tax_type
      AND queue.evidence_id = original_preparation.evidence_id;

    IF original_preparation.id IS NULL OR original_journal.id IS NULL
       OR original_journal.status <> 'posted'
       OR original_journal.entry_number <> original_posting.entry_number
       OR original_queue.posting_id IS NULL
       OR original_queue.accounting_status <> 'posted_adjustment_review_required' THEN
        RAISE EXCEPTION 'Tax adjustment requires an exact posted liability whose protected evidence is now stale or superseded.';
    END IF;

    SELECT * INTO replacement_queue
    FROM accounting.v1_tax_liability_queue queue
    WHERE queue.tax_type = original_preparation.tax_type
      AND queue.evidence_id = p_replacement_evidence_id;
    IF replacement_queue.evidence_id IS NULL
       OR replacement_queue.evidence_status <> 'evidence_ready'
       OR replacement_queue.source_id <> original_queue.source_id
       OR replacement_queue.loan_id <> original_queue.loan_id
       OR replacement_queue.client_id <> original_queue.client_id
       OR replacement_queue.evidence_version <= original_queue.evidence_version
       OR replacement_queue.accounting_status NOT IN ('evidence_ready', 'no_liability_required')
       OR replacement_queue.preparation_id IS NOT NULL
       OR replacement_queue.posting_id IS NOT NULL THEN
        RAISE EXCEPTION 'Replacement tax evidence must be the exact newer current unposted evidence for the same protected source, loan and client.';
    END IF;

    SELECT * INTO original_period
    FROM accounting.fiscal_periods period
    WHERE period.id = original_posting.confirmed_fiscal_period_id
    FOR SHARE;
    IF original_period.id IS NULL OR original_period.status <> 'open'
       OR p_adjustment_date NOT BETWEEN original_period.start_date AND original_period.end_date THEN
        RAISE EXCEPTION 'V1 tax correction execution is allowed only while the original liability fiscal period remains open and contains the adjustment date.';
    END IF;

    SELECT item.tax_return_id INTO linked_return_id
    FROM accounting.v1_tax_return_liability_items item
    WHERE item.tax_liability_posting_id = original_posting.id;
    IF linked_return_id IS NOT NULL THEN
        SELECT payment.id INTO linked_payment_id
        FROM accounting.v1_tax_payment_evidence payment
        WHERE payment.tax_return_id = linked_return_id;
        SELECT settlement.* INTO linked_settlement
        FROM accounting.v1_tax_settlement_postings settlement
        WHERE settlement.tax_return_id = linked_return_id;
        IF linked_settlement.id IS NOT NULL THEN
            SELECT * INTO linked_settlement_journal
            FROM accounting.journal_entries item
            WHERE item.id = linked_settlement.journal_entry_id
            FOR SHARE;
        END IF;
    END IF;

    IF normalized_kind = 'reverse_unsettled_liability' THEN
        IF linked_payment_id IS NOT NULL OR linked_settlement.id IS NOT NULL THEN
            RAISE EXCEPTION 'An unpaid-liability reversal cannot be used after tax payment evidence exists; paid or in-flight payment states require the protected settlement-adjustment path.';
        END IF;
        adjustment_amount_value := original_posting.confirmed_tax_due;
    ELSE
        IF linked_settlement.id IS NULL
           OR linked_settlement_journal.id IS NULL
           OR linked_settlement_journal.status <> 'posted'
           OR linked_settlement_journal.entry_number <> linked_settlement.entry_number THEN
            RAISE EXCEPTION 'Settled-tax recoverable recognition requires the exact immutable posted settlement history.';
        END IF;
        IF replacement_queue.tax_due >= original_posting.confirmed_tax_due THEN
            RAISE EXCEPTION 'Settled-tax recoverable recognition is limited to an exact supported decrease; equal or additional tax requires separate explicit amendment/payment evidence.';
        END IF;
        adjustment_amount_value := original_posting.confirmed_tax_due - replacement_queue.tax_due;
    END IF;

    SELECT * INTO existing
    FROM accounting.v1_tax_adjustment_evidence item
    WHERE item.idempotency_key = p_idempotency_key
    FOR SHARE;
    IF existing.id IS NOT NULL THEN
        IF existing.adjustment_kind = normalized_kind
           AND existing.tax_type = original_preparation.tax_type
           AND existing.tax_liability_posting_id = original_posting.id
           AND existing.original_evidence_id = original_preparation.evidence_id
           AND existing.replacement_evidence_id = p_replacement_evidence_id
           AND existing.original_tax_due = original_posting.confirmed_tax_due
           AND existing.replacement_tax_due = replacement_queue.tax_due
           AND existing.adjustment_amount = adjustment_amount_value
           AND existing.original_liability_journal_entry_id = original_journal.id
           AND existing.settlement_posting_id IS NOT DISTINCT FROM linked_settlement.id
           AND existing.original_settlement_journal_entry_id IS NOT DISTINCT FROM linked_settlement_journal.id
           AND existing.adjustment_date = p_adjustment_date
           AND existing.adjustment_reference = normalized_adjustment_reference
           AND existing.evidence_reference = normalized_evidence_reference
           AND existing.evidence_digest = normalized_digest
           AND existing.evidence_note = normalized_note
           AND existing.recorded_by_user_id = p_actor_user_id THEN
            RETURN existing.id;
        END IF;
        RAISE EXCEPTION 'Tax adjustment evidence idempotency key already belongs to different immutable evidence.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM accounting.v1_tax_adjustment_evidence item
        WHERE item.tax_liability_posting_id = original_posting.id
    ) THEN
        RAISE EXCEPTION 'This original V1 tax-liability posting already has an immutable protected adjustment evidence record.';
    END IF;

    PERFORM set_config('accounting.v1_tax_adjustment_evidence_insert_allowed', 'on', true);
    INSERT INTO accounting.v1_tax_adjustment_evidence(
        idempotency_key, adjustment_kind, tax_type, tax_liability_posting_id,
        original_evidence_id, replacement_evidence_id, original_tax_due,
        replacement_tax_due, adjustment_amount, original_liability_journal_entry_id,
        settlement_posting_id, original_settlement_journal_entry_id,
        adjustment_date, adjustment_reference, evidence_reference,
        evidence_digest, evidence_note, recorded_by_user_id
    ) VALUES (
        p_idempotency_key, normalized_kind, original_preparation.tax_type,
        original_posting.id, original_preparation.evidence_id,
        p_replacement_evidence_id, original_posting.confirmed_tax_due,
        replacement_queue.tax_due, adjustment_amount_value, original_journal.id,
        linked_settlement.id, linked_settlement_journal.id, p_adjustment_date,
        normalized_adjustment_reference, normalized_evidence_reference,
        normalized_digest, normalized_note, p_actor_user_id
    ) RETURNING id INTO created_id;
    PERFORM set_config('accounting.v1_tax_adjustment_evidence_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.tax.adjustment_evidence.recorded',
        'v1_tax_adjustment',
        created_id,
        jsonb_build_object(
            'adjustment_kind', normalized_kind,
            'tax_type', original_preparation.tax_type,
            'tax_liability_posting_id', original_posting.id,
            'original_evidence_id', original_preparation.evidence_id,
            'replacement_evidence_id', p_replacement_evidence_id,
            'original_tax_due', original_posting.confirmed_tax_due,
            'replacement_tax_due', replacement_queue.tax_due,
            'adjustment_amount', adjustment_amount_value,
            'settlement_posting_id', linked_settlement.id,
            'adjustment_date', p_adjustment_date,
            'evidence_digest', normalized_digest,
            'automatic_source_posting', false
        )
    );

    RETURN created_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.prepare_v1_tax_adjustment_journal(
    p_adjustment_evidence_id UUID,
    p_actor_user_id UUID
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    evidence accounting.v1_tax_adjustment_evidence%ROWTYPE;
    existing accounting.v1_tax_adjustment_preparations%ROWTYPE;
    original_posting accounting.v1_tax_liability_postings%ROWTYPE;
    original_preparation accounting.v1_tax_liability_preparations%ROWTYPE;
    original_journal accounting.journal_entries%ROWTYPE;
    original_queue accounting.v1_tax_liability_queue%ROWTYPE;
    replacement_queue accounting.v1_tax_liability_queue%ROWTYPE;
    settlement accounting.v1_tax_settlement_postings%ROWTYPE;
    settlement_journal accounting.journal_entries%ROWTYPE;
    target_period accounting.fiscal_periods%ROWTYPE;
    expense_account accounting.accounts%ROWTYPE;
    payable_account accounting.accounts%ROWTYPE;
    recoverable_account accounting.accounts%ROWTYPE;
    debit_account accounting.accounts%ROWTYPE;
    credit_account accounting.accounts%ROWTYPE;
    linked_payment_id UUID;
    created_journal_id UUID;
    protected_source_event_key TEXT;
BEGIN
    PERFORM accounting.require_v1_tax_management_actor(
        p_actor_user_id,
        'accounting.tax.adjustment.prepare'
    );
    IF p_adjustment_evidence_id IS NULL THEN
        RAISE EXCEPTION 'Tax adjustment preparation requires exact immutable adjustment evidence.';
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended('v1-tax-adjustment:' || p_adjustment_evidence_id::text, 0));

    SELECT * INTO existing
    FROM accounting.v1_tax_adjustment_preparations item
    WHERE item.adjustment_evidence_id = p_adjustment_evidence_id;
    IF existing.id IS NOT NULL THEN
        RETURN existing.journal_entry_id;
    END IF;

    SELECT * INTO evidence
    FROM accounting.v1_tax_adjustment_evidence item
    WHERE item.id = p_adjustment_evidence_id
    FOR SHARE;
    IF evidence.id IS NULL THEN
        RAISE EXCEPTION 'Tax adjustment evidence was not found.';
    END IF;

    SELECT * INTO original_posting
    FROM accounting.v1_tax_liability_postings item
    WHERE item.id = evidence.tax_liability_posting_id
    FOR SHARE;
    SELECT * INTO original_preparation
    FROM accounting.v1_tax_liability_preparations item
    WHERE item.id = original_posting.preparation_id
    FOR SHARE;
    SELECT * INTO original_journal
    FROM accounting.journal_entries item
    WHERE item.id = original_posting.journal_entry_id
    FOR SHARE;
    SELECT * INTO original_queue
    FROM accounting.v1_tax_liability_queue queue
    WHERE queue.posting_id = original_posting.id
      AND queue.tax_type = evidence.tax_type
      AND queue.evidence_id = evidence.original_evidence_id;
    SELECT * INTO replacement_queue
    FROM accounting.v1_tax_liability_queue queue
    WHERE queue.tax_type = evidence.tax_type
      AND queue.evidence_id = evidence.replacement_evidence_id;

    IF original_posting.id IS NULL OR original_preparation.id IS NULL
       OR original_journal.id IS NULL OR original_journal.status <> 'posted'
       OR original_journal.entry_number <> original_posting.entry_number
       OR original_queue.accounting_status <> 'posted_adjustment_review_required'
       OR replacement_queue.evidence_id IS NULL
       OR replacement_queue.evidence_status <> 'evidence_ready'
       OR replacement_queue.source_id <> original_queue.source_id
       OR replacement_queue.loan_id <> original_queue.loan_id
       OR replacement_queue.client_id <> original_queue.client_id
       OR replacement_queue.evidence_version <= original_queue.evidence_version
       OR replacement_queue.tax_due <> evidence.replacement_tax_due
       OR replacement_queue.accounting_status NOT IN ('evidence_ready', 'no_liability_required')
       OR replacement_queue.preparation_id IS NOT NULL
       OR replacement_queue.posting_id IS NOT NULL
       OR original_posting.confirmed_tax_due <> evidence.original_tax_due
       OR original_preparation.evidence_id <> evidence.original_evidence_id
       OR original_journal.id <> evidence.original_liability_journal_entry_id THEN
        RAISE EXCEPTION 'Exact original/replacement tax evidence coordinates changed after adjustment evidence was recorded.';
    END IF;

    SELECT * INTO target_period
    FROM accounting.fiscal_periods period
    WHERE period.id = original_posting.confirmed_fiscal_period_id
    FOR SHARE;
    IF target_period.id IS NULL OR target_period.status <> 'open'
       OR evidence.adjustment_date NOT BETWEEN target_period.start_date AND target_period.end_date THEN
        RAISE EXCEPTION 'Tax adjustment requires the exact original liability fiscal period to remain open.';
    END IF;

    SELECT * INTO expense_account
    FROM accounting.accounts account
    WHERE account.id = original_posting.confirmed_expense_account_id
    FOR SHARE;
    SELECT * INTO payable_account
    FROM accounting.accounts account
    WHERE account.id = original_posting.confirmed_tax_payable_account_id
    FOR SHARE;
    SELECT * INTO recoverable_account
    FROM accounting.accounts account
    WHERE account.system_key = 'tax_recoverable'
    FOR SHARE;

    IF expense_account.id IS NULL OR expense_account.account_type <> 'expense'
       OR expense_account.normal_balance <> 'debit' OR NOT expense_account.is_active
       OR NOT expense_account.is_posting
       OR expense_account.code <> CASE WHEN evidence.tax_type = 'documentary_stamp_tax' THEN '5310' ELSE '5300' END THEN
        RAISE EXCEPTION 'Exact original dedicated tax expense account is no longer posting-ready.';
    END IF;
    IF payable_account.id IS NULL OR payable_account.system_key <> 'tax_payables'
       OR payable_account.code <> '2100' OR payable_account.account_type <> 'liability'
       OR payable_account.normal_balance <> 'credit' OR NOT payable_account.is_active
       OR NOT payable_account.is_posting THEN
        RAISE EXCEPTION 'Exact 2100 Tax Payables is no longer posting-ready.';
    END IF;
    IF recoverable_account.id IS NULL OR recoverable_account.code <> '1130'
       OR recoverable_account.account_type <> 'asset'
       OR recoverable_account.normal_balance <> 'debit'
       OR NOT recoverable_account.is_active OR NOT recoverable_account.is_posting THEN
        RAISE EXCEPTION 'Exact active 1130 Tax Recoverable is required for settled-tax correction accounting.';
    END IF;

    IF evidence.adjustment_kind = 'reverse_unsettled_liability' THEN
        SELECT payment.id INTO linked_payment_id
        FROM accounting.v1_tax_return_liability_items item
        JOIN accounting.v1_tax_payment_evidence payment
          ON payment.tax_return_id = item.tax_return_id
        WHERE item.tax_liability_posting_id = original_posting.id;
        IF linked_payment_id IS NOT NULL OR evidence.settlement_posting_id IS NOT NULL THEN
            RAISE EXCEPTION 'Unsettled tax-liability reversal is blocked because payment/settlement evidence now exists.';
        END IF;
        IF evidence.adjustment_amount <> evidence.original_tax_due THEN
            RAISE EXCEPTION 'Unsettled tax-liability reversal must fully reverse the exact original posted liability.';
        END IF;
        debit_account := payable_account;
        credit_account := expense_account;
    ELSE
        SELECT * INTO settlement
        FROM accounting.v1_tax_settlement_postings item
        WHERE item.id = evidence.settlement_posting_id
        FOR SHARE;
        SELECT * INTO settlement_journal
        FROM accounting.journal_entries item
        WHERE item.id = settlement.journal_entry_id
        FOR SHARE;
        IF settlement.id IS NULL OR settlement_journal.id IS NULL
           OR settlement_journal.status <> 'posted'
           OR settlement_journal.entry_number <> settlement.entry_number
           OR evidence.original_settlement_journal_entry_id <> settlement_journal.id
           OR evidence.original_tax_due <= evidence.replacement_tax_due
           OR evidence.adjustment_amount <> evidence.original_tax_due - evidence.replacement_tax_due THEN
            RAISE EXCEPTION 'Settled-tax recoverable coordinates no longer exactly match the retained settlement and replacement evidence.';
        END IF;
        debit_account := recoverable_account;
        credit_account := expense_account;
    END IF;

    protected_source_event_key := 'v1_tax_adjustment:' || evidence.id::text;
    IF EXISTS (
        SELECT 1 FROM accounting.journal_entries journal
        WHERE journal.source_event_key = protected_source_event_key
    ) THEN
        RAISE EXCEPTION 'Protected V1 tax adjustment source identity is already occupied outside the adjustment audit.';
    END IF;

    PERFORM set_config('accounting.v1_tax_adjustment_journal_prepare_allowed', 'on', true);
    PERFORM set_config('accounting.v1_tax_liability_adjustment_reversal_allowed', 'on', true);
    INSERT INTO accounting.journal_entries(
        fiscal_period_id, posting_date, description, status, source_type,
        source_reference, source_event_key, reversal_of_entry_id,
        created_by_user_id, updated_at
    ) VALUES (
        target_period.id, evidence.adjustment_date,
        CASE
            WHEN evidence.adjustment_kind = 'reverse_unsettled_liability'
                THEN 'Protected V1 tax liability reversal: ' || evidence.adjustment_reference
            ELSE 'Protected V1 settled tax recoverable: ' || evidence.adjustment_reference
        END,
        'draft', 'v1_tax_adjustment', evidence.id::text,
        protected_source_event_key,
        CASE WHEN evidence.adjustment_kind = 'reverse_unsettled_liability' THEN original_journal.id ELSE NULL END,
        p_actor_user_id, now()
    ) RETURNING id INTO created_journal_id;
    PERFORM set_config('accounting.v1_tax_liability_adjustment_reversal_allowed', 'off', true);
    PERFORM set_config('accounting.v1_tax_adjustment_journal_prepare_allowed', 'off', true);

    PERFORM set_config('accounting.v1_tax_adjustment_journal_line_write_allowed', 'on', true);
    INSERT INTO accounting.journal_lines(
        journal_entry_id, line_number, account_id, description, debit, credit,
        client_id, loan_id
    ) VALUES
        (
            created_journal_id, 1, debit_account.id,
            CASE
                WHEN evidence.adjustment_kind = 'reverse_unsettled_liability'
                    THEN 'Reverse stale tax payable'
                ELSE 'Recognize settled tax recoverable'
            END,
            evidence.adjustment_amount, 0,
            original_queue.client_id, original_queue.loan_id
        ),
        (
            created_journal_id, 2, credit_account.id,
            'Correct original ' || credit_account.name,
            0, evidence.adjustment_amount,
            original_queue.client_id, original_queue.loan_id
        );
    PERFORM set_config('accounting.v1_tax_adjustment_journal_line_write_allowed', 'off', true);

    INSERT INTO accounting.journal_events(journal_entry_id, event_type, actor_user_id, details)
    VALUES (
        created_journal_id, 'draft_created', p_actor_user_id,
        jsonb_build_object(
            'source_type', 'v1_tax_adjustment',
            'adjustment_evidence_id', evidence.id,
            'adjustment_kind', evidence.adjustment_kind,
            'tax_liability_posting_id', original_posting.id,
            'original_evidence_id', evidence.original_evidence_id,
            'replacement_evidence_id', evidence.replacement_evidence_id,
            'adjustment_amount', evidence.adjustment_amount,
            'debit_account_code', debit_account.code,
            'credit_account_code', credit_account.code,
            'automatic_source_posting', false
        )
    );

    PERFORM set_config('accounting.v1_tax_adjustment_preparation_insert_allowed', 'on', true);
    INSERT INTO accounting.v1_tax_adjustment_preparations(
        adjustment_evidence_id, journal_entry_id, source_event_key,
        original_liability_journal_entry_id, adjustment_kind, posting_date,
        adjustment_amount, debit_account_id, credit_account_id,
        fiscal_period_id, prepared_by_user_id
    ) VALUES (
        evidence.id, created_journal_id, protected_source_event_key,
        original_journal.id, evidence.adjustment_kind, evidence.adjustment_date,
        evidence.adjustment_amount, debit_account.id, credit_account.id,
        target_period.id, p_actor_user_id
    );
    PERFORM set_config('accounting.v1_tax_adjustment_preparation_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id, 'accounting.tax.adjustment.prepared',
        'v1_tax_adjustment', evidence.id,
        jsonb_build_object(
            'journal_entry_id', created_journal_id,
            'adjustment_kind', evidence.adjustment_kind,
            'adjustment_amount', evidence.adjustment_amount,
            'debit_account_code', debit_account.code,
            'credit_account_code', credit_account.code,
            'fiscal_period_id', target_period.id,
            'automatic_source_posting', false
        )
    );

    RETURN created_journal_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.post_v1_tax_adjustment_journal(
    p_adjustment_evidence_id UUID,
    p_actor_user_id UUID,
    p_confirmation_token TEXT,
    p_expected_evidence_digest TEXT,
    p_expected_original_tax_due NUMERIC,
    p_expected_replacement_tax_due NUMERIC,
    p_expected_adjustment_amount NUMERIC,
    p_expected_debit_account_code TEXT,
    p_expected_credit_account_code TEXT,
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
    normalized_original_due NUMERIC(18,2) := round(coalesce(p_expected_original_tax_due, -1), 2);
    normalized_replacement_due NUMERIC(18,2) := round(coalesce(p_expected_replacement_tax_due, -1), 2);
    normalized_adjustment_amount NUMERIC(18,2) := round(coalesce(p_expected_adjustment_amount, -1), 2);
    normalized_debit_code TEXT := btrim(coalesce(p_expected_debit_account_code, ''));
    normalized_credit_code TEXT := btrim(coalesce(p_expected_credit_account_code, ''));
    evidence accounting.v1_tax_adjustment_evidence%ROWTYPE;
    preparation accounting.v1_tax_adjustment_preparations%ROWTYPE;
    existing accounting.v1_tax_adjustment_postings%ROWTYPE;
    original_posting accounting.v1_tax_liability_postings%ROWTYPE;
    original_preparation accounting.v1_tax_liability_preparations%ROWTYPE;
    original_queue accounting.v1_tax_liability_queue%ROWTYPE;
    replacement_queue accounting.v1_tax_liability_queue%ROWTYPE;
    settlement accounting.v1_tax_settlement_postings%ROWTYPE;
    settlement_journal accounting.journal_entries%ROWTYPE;
    period_row accounting.fiscal_periods%ROWTYPE;
    debit_account accounting.accounts%ROWTYPE;
    credit_account accounting.accounts%ROWTYPE;
    journal accounting.journal_entries%ROWTYPE;
    linked_payment_id UUID;
    line_count INTEGER;
    total_debit NUMERIC(18,2);
    total_credit NUMERIC(18,2);
    expected_debit NUMERIC(18,2);
    expected_credit NUMERIC(18,2);
    foreign_line_count INTEGER;
    generated_entry_number TEXT;
    confirmation_digest_value TEXT;
    created_posting_id UUID;
BEGIN
    PERFORM accounting.require_v1_tax_management_actor(
        p_actor_user_id,
        'accounting.tax.adjustment.post'
    );

    IF p_adjustment_evidence_id IS NULL
       OR p_policy_version IS DISTINCT FROM 'v1_tax_adjustment_posting_v1'
       OR normalized_token !~ '^[0-9a-f]{64}$'
       OR normalized_digest !~ '^[0-9a-f]{64}$'
       OR p_expected_original_tax_due IS DISTINCT FROM normalized_original_due
       OR p_expected_replacement_tax_due IS DISTINCT FROM normalized_replacement_due
       OR p_expected_adjustment_amount IS DISTINCT FROM normalized_adjustment_amount
       OR normalized_original_due <= 0 OR normalized_replacement_due < 0
       OR normalized_adjustment_amount <= 0
       OR normalized_debit_code = '' OR normalized_credit_code = ''
       OR p_expected_posting_date IS NULL OR p_expected_fiscal_period_id IS NULL THEN
        RAISE EXCEPTION 'Protected tax adjustment posting requires exact Management confirmation, evidence digest, original/replacement tax, adjustment amount, accounts, date, period and policy.';
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended('v1-tax-adjustment:' || p_adjustment_evidence_id::text, 0));

    SELECT * INTO evidence
    FROM accounting.v1_tax_adjustment_evidence item
    WHERE item.id = p_adjustment_evidence_id
    FOR SHARE;
    SELECT * INTO preparation
    FROM accounting.v1_tax_adjustment_preparations item
    WHERE item.adjustment_evidence_id = p_adjustment_evidence_id
    FOR SHARE;
    IF evidence.id IS NULL OR preparation.id IS NULL THEN
        RAISE EXCEPTION 'Tax adjustment must have exact immutable evidence and a protected preparation before posting.';
    END IF;

    SELECT * INTO existing
    FROM accounting.v1_tax_adjustment_postings item
    WHERE item.preparation_id = preparation.id
    FOR SHARE;
    IF existing.id IS NOT NULL THEN
        IF existing.confirmation_token = normalized_token
           AND existing.confirmed_evidence_digest = normalized_digest
           AND existing.confirmed_original_tax_due = normalized_original_due
           AND existing.confirmed_replacement_tax_due = normalized_replacement_due
           AND existing.confirmed_adjustment_amount = normalized_adjustment_amount
           AND existing.confirmed_posting_date = p_expected_posting_date
           AND existing.confirmed_fiscal_period_id = p_expected_fiscal_period_id
           AND existing.policy_version = p_policy_version
           AND existing.posted_by_user_id = p_actor_user_id
           AND EXISTS (
                SELECT 1 FROM accounting.accounts account
                WHERE account.id = existing.confirmed_debit_account_id
                  AND account.code = normalized_debit_code
           )
           AND EXISTS (
                SELECT 1 FROM accounting.accounts account
                WHERE account.id = existing.confirmed_credit_account_id
                  AND account.code = normalized_credit_code
           ) THEN
            RETURN existing.id;
        END IF;
        RAISE EXCEPTION 'Existing V1 tax adjustment posting does not match the immutable retry identity.';
    END IF;

    IF evidence.evidence_digest <> normalized_digest
       OR evidence.original_tax_due <> normalized_original_due
       OR evidence.replacement_tax_due <> normalized_replacement_due
       OR evidence.adjustment_amount <> normalized_adjustment_amount
       OR evidence.adjustment_date <> p_expected_posting_date
       OR preparation.posting_date <> p_expected_posting_date
       OR preparation.adjustment_amount <> normalized_adjustment_amount
       OR preparation.adjustment_kind <> evidence.adjustment_kind THEN
        RAISE EXCEPTION 'Exact immutable V1 tax adjustment evidence no longer matches the confirmed posting coordinates.';
    END IF;

    SELECT * INTO original_posting
    FROM accounting.v1_tax_liability_postings item
    WHERE item.id = evidence.tax_liability_posting_id
    FOR SHARE;
    SELECT * INTO original_preparation
    FROM accounting.v1_tax_liability_preparations item
    WHERE item.id = original_posting.preparation_id
    FOR SHARE;
    SELECT * INTO original_queue
    FROM accounting.v1_tax_liability_queue queue
    WHERE queue.posting_id = original_posting.id
      AND queue.tax_type = evidence.tax_type
      AND queue.evidence_id = evidence.original_evidence_id;
    SELECT * INTO replacement_queue
    FROM accounting.v1_tax_liability_queue queue
    WHERE queue.tax_type = evidence.tax_type
      AND queue.evidence_id = evidence.replacement_evidence_id;

    IF original_posting.id IS NULL OR original_preparation.id IS NULL
       OR original_queue.accounting_status <> 'posted_adjustment_review_required'
       OR replacement_queue.evidence_id IS NULL
       OR replacement_queue.evidence_status <> 'evidence_ready'
       OR replacement_queue.source_id <> original_queue.source_id
       OR replacement_queue.loan_id <> original_queue.loan_id
       OR replacement_queue.client_id <> original_queue.client_id
       OR replacement_queue.evidence_version <= original_queue.evidence_version
       OR replacement_queue.tax_due <> normalized_replacement_due
       OR replacement_queue.accounting_status NOT IN ('evidence_ready', 'no_liability_required')
       OR replacement_queue.preparation_id IS NOT NULL
       OR replacement_queue.posting_id IS NOT NULL
       OR original_posting.confirmed_tax_due <> normalized_original_due THEN
        RAISE EXCEPTION 'Original stale liability or exact current replacement evidence changed before tax adjustment posting.';
    END IF;

    SELECT * INTO period_row
    FROM accounting.fiscal_periods period
    WHERE period.id = p_expected_fiscal_period_id
    FOR SHARE;
    IF period_row.id IS NULL OR period_row.status <> 'open'
       OR p_expected_fiscal_period_id <> original_posting.confirmed_fiscal_period_id
       OR preparation.fiscal_period_id <> period_row.id
       OR p_expected_posting_date NOT BETWEEN period_row.start_date AND period_row.end_date THEN
        RAISE EXCEPTION 'Tax adjustment posting requires the exact still-open original liability fiscal period.';
    END IF;

    SELECT * INTO debit_account
    FROM accounting.accounts account
    WHERE account.id = preparation.debit_account_id
    FOR SHARE;
    SELECT * INTO credit_account
    FROM accounting.accounts account
    WHERE account.id = preparation.credit_account_id
    FOR SHARE;
    IF debit_account.id IS NULL OR debit_account.code <> normalized_debit_code
       OR credit_account.id IS NULL OR credit_account.code <> normalized_credit_code
       OR NOT debit_account.is_active OR NOT debit_account.is_posting
       OR NOT credit_account.is_active OR NOT credit_account.is_posting THEN
        RAISE EXCEPTION 'Exact confirmed tax adjustment debit/credit accounts are no longer posting-ready.';
    END IF;

    IF evidence.adjustment_kind = 'reverse_unsettled_liability' THEN
        IF debit_account.system_key <> 'tax_payables' OR debit_account.code <> '2100'
           OR credit_account.id <> original_posting.confirmed_expense_account_id
           OR normalized_adjustment_amount <> normalized_original_due THEN
            RAISE EXCEPTION 'Unsettled tax reversal must remain exact Dr 2100 Tax Payables / Cr original dedicated tax expense for the full original liability.';
        END IF;
        SELECT payment.id INTO linked_payment_id
        FROM accounting.v1_tax_return_liability_items item
        JOIN accounting.v1_tax_payment_evidence payment
          ON payment.tax_return_id = item.tax_return_id
        WHERE item.tax_liability_posting_id = original_posting.id;
        IF linked_payment_id IS NOT NULL OR evidence.settlement_posting_id IS NOT NULL THEN
            RAISE EXCEPTION 'Unsettled tax reversal is blocked because payment/settlement evidence now exists.';
        END IF;
    ELSE
        IF debit_account.system_key <> 'tax_recoverable' OR debit_account.code <> '1130'
           OR credit_account.id <> original_posting.confirmed_expense_account_id
           OR normalized_original_due <= normalized_replacement_due
           OR normalized_adjustment_amount <> normalized_original_due - normalized_replacement_due THEN
            RAISE EXCEPTION 'Settled tax decrease must remain exact Dr 1130 Tax Recoverable / Cr original dedicated tax expense for the supported decrease only.';
        END IF;
        SELECT * INTO settlement
        FROM accounting.v1_tax_settlement_postings item
        WHERE item.id = evidence.settlement_posting_id
        FOR SHARE;
        SELECT * INTO settlement_journal
        FROM accounting.journal_entries item
        WHERE item.id = settlement.journal_entry_id
        FOR SHARE;
        IF settlement.id IS NULL OR settlement_journal.id IS NULL
           OR settlement_journal.status <> 'posted'
           OR settlement_journal.entry_number <> settlement.entry_number
           OR settlement_journal.id <> evidence.original_settlement_journal_entry_id THEN
            RAISE EXCEPTION 'Exact original posted settlement history changed before settled-tax recoverable posting.';
        END IF;
    END IF;

    SELECT * INTO journal
    FROM accounting.journal_entries item
    WHERE item.id = preparation.journal_entry_id
    FOR UPDATE;
    IF journal.id IS NULL OR journal.status <> 'draft'
       OR journal.source_type <> 'v1_tax_adjustment'
       OR journal.source_reference <> evidence.id::text
       OR journal.source_event_key <> preparation.source_event_key
       OR journal.posting_date <> p_expected_posting_date
       OR journal.fiscal_period_id <> period_row.id
       OR journal.reversal_of_entry_id IS DISTINCT FROM CASE
            WHEN evidence.adjustment_kind = 'reverse_unsettled_liability'
                THEN evidence.original_liability_journal_entry_id
            ELSE NULL
          END THEN
        RAISE EXCEPTION 'Prepared V1 tax adjustment General Journal draft no longer matches the protected adjustment coordinates.';
    END IF;

    SELECT
        count(*)::integer,
        coalesce(sum(line.debit), 0)::numeric(18,2),
        coalesce(sum(line.credit), 0)::numeric(18,2),
        coalesce(sum(line.debit) FILTER (WHERE line.account_id = debit_account.id), 0)::numeric(18,2),
        coalesce(sum(line.credit) FILTER (WHERE line.account_id = credit_account.id), 0)::numeric(18,2),
        count(*) FILTER (
            WHERE line.account_id NOT IN (debit_account.id, credit_account.id)
               OR line.client_id IS DISTINCT FROM original_queue.client_id
               OR line.loan_id IS DISTINCT FROM original_queue.loan_id
        )::integer
    INTO line_count, total_debit, total_credit, expected_debit, expected_credit, foreign_line_count
    FROM accounting.journal_lines line
    WHERE line.journal_entry_id = journal.id;

    IF line_count <> 2
       OR total_debit <> normalized_adjustment_amount
       OR total_credit <> normalized_adjustment_amount
       OR expected_debit <> normalized_adjustment_amount
       OR expected_credit <> normalized_adjustment_amount
       OR foreign_line_count <> 0 THEN
        RAISE EXCEPTION 'Prepared V1 tax adjustment lines no longer exactly reconcile to retained correction evidence.';
    END IF;

    confirmation_digest_value := encode(sha256(convert_to(concat_ws('|',
        p_policy_version, evidence.id::text, evidence.adjustment_kind,
        evidence.tax_liability_posting_id::text, evidence.original_evidence_id::text,
        evidence.replacement_evidence_id::text, normalized_digest,
        to_char(normalized_original_due, 'FM999999999999990.00'),
        to_char(normalized_replacement_due, 'FM999999999999990.00'),
        to_char(normalized_adjustment_amount, 'FM999999999999990.00'),
        debit_account.id::text, credit_account.id::text,
        p_expected_posting_date::text, period_row.id::text,
        journal.id::text, normalized_token
    ), 'UTF8')), 'hex');

    PERFORM set_config('accounting.v1_tax_adjustment_journal_post_allowed', 'on', true);
    generated_entry_number := accounting.post_journal_entry(journal.id, p_actor_user_id);
    PERFORM set_config('accounting.v1_tax_adjustment_journal_post_allowed', 'off', true);

    IF coalesce(current_setting('accounting.v1_tax_adjustment_force_audit_failure', true), '') = 'on' THEN
        RAISE EXCEPTION 'Forced V1 tax adjustment audit failure.';
    END IF;

    PERFORM set_config('accounting.v1_tax_adjustment_posting_insert_allowed', 'on', true);
    INSERT INTO accounting.v1_tax_adjustment_postings(
        preparation_id, adjustment_evidence_id, tax_liability_posting_id,
        journal_entry_id, entry_number, confirmation_token, confirmation_digest,
        confirmed_evidence_digest, confirmed_original_tax_due,
        confirmed_replacement_tax_due, confirmed_adjustment_amount,
        confirmed_debit_account_id, confirmed_credit_account_id,
        confirmed_posting_date, confirmed_fiscal_period_id,
        policy_version, posted_by_user_id
    ) VALUES (
        preparation.id, evidence.id, evidence.tax_liability_posting_id,
        journal.id, generated_entry_number, normalized_token,
        confirmation_digest_value, normalized_digest, normalized_original_due,
        normalized_replacement_due, normalized_adjustment_amount,
        debit_account.id, credit_account.id, p_expected_posting_date,
        period_row.id, p_policy_version, p_actor_user_id
    ) RETURNING id INTO created_posting_id;
    PERFORM set_config('accounting.v1_tax_adjustment_posting_insert_allowed', 'off', true);

    INSERT INTO accounting.journal_events(journal_entry_id, event_type, actor_user_id, details)
    VALUES (
        journal.id, 'posted', p_actor_user_id,
        jsonb_build_object(
            'entry_number', generated_entry_number,
            'source_type', 'v1_tax_adjustment',
            'adjustment_evidence_id', evidence.id,
            'adjustment_kind', evidence.adjustment_kind,
            'confirmation_digest', confirmation_digest_value,
            'automatic_source_posting', false
        )
    );

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id, 'accounting.tax.adjustment.posted',
        'v1_tax_adjustment', evidence.id,
        jsonb_build_object(
            'journal_entry_id', journal.id,
            'entry_number', generated_entry_number,
            'adjustment_kind', evidence.adjustment_kind,
            'original_tax_due', normalized_original_due,
            'replacement_tax_due', normalized_replacement_due,
            'adjustment_amount', normalized_adjustment_amount,
            'debit_account_code', debit_account.code,
            'credit_account_code', credit_account.code,
            'confirmation_digest', confirmation_digest_value,
            'automatic_source_posting', false
        )
    );

    RETURN created_posting_id;
END;
$$;

CREATE OR REPLACE VIEW accounting.v1_tax_adjustment_queue AS
SELECT
    evidence.id AS adjustment_evidence_id,
    evidence.adjustment_kind,
    evidence.tax_type,
    evidence.tax_liability_posting_id,
    evidence.original_evidence_id,
    evidence.replacement_evidence_id,
    original_queue.source_id,
    original_queue.loan_id,
    original_queue.client_id,
    evidence.original_tax_due,
    evidence.replacement_tax_due,
    evidence.adjustment_amount,
    evidence.adjustment_date,
    evidence.adjustment_reference,
    evidence.evidence_reference,
    evidence.evidence_digest,
    evidence.recorded_by_user_id,
    evidence.recorded_at,
    evidence.settlement_posting_id,
    evidence.original_settlement_journal_entry_id,
    preparation.id AS preparation_id,
    preparation.journal_entry_id,
    journal.status AS journal_status,
    journal.entry_number,
    preparation.fiscal_period_id,
    preparation.debit_account_id,
    debit_account.code AS debit_account_code,
    debit_account.name AS debit_account_name,
    preparation.credit_account_id,
    credit_account.code AS credit_account_code,
    credit_account.name AS credit_account_name,
    preparation.prepared_by_user_id,
    preparation.prepared_at,
    posting.id AS adjustment_posting_id,
    posting.confirmation_digest,
    posting.posted_by_user_id,
    posting.posted_at,
    CASE
        WHEN posting.id IS NOT NULL
             AND (
                original_queue.accounting_status <> 'posted_adjustment_review_required'
                OR replacement_queue.evidence_status <> 'evidence_ready'
                OR replacement_queue.source_id <> original_queue.source_id
                OR replacement_queue.tax_due <> evidence.replacement_tax_due
             )
            THEN 'posted_further_adjustment_review_required'
        WHEN posting.id IS NOT NULL
             AND evidence.adjustment_kind = 'reverse_unsettled_liability'
            THEN 'posted_unsettled_liability_reversal'
        WHEN posting.id IS NOT NULL
            THEN 'posted_settled_tax_recoverable'
        WHEN original_queue.accounting_status <> 'posted_adjustment_review_required'
            THEN 'blocked_original_liability_not_stale'
        WHEN replacement_queue.evidence_id IS NULL
          OR replacement_queue.evidence_status <> 'evidence_ready'
          OR replacement_queue.source_id <> original_queue.source_id
          OR replacement_queue.loan_id <> original_queue.loan_id
          OR replacement_queue.client_id <> original_queue.client_id
          OR replacement_queue.tax_due <> evidence.replacement_tax_due
            THEN 'blocked_replacement_evidence_changed'
        WHEN preparation.id IS NOT NULL AND journal.status IS DISTINCT FROM 'draft'
            THEN 'blocked_untracked_adjustment_journal_state'
        WHEN open_period.id IS NULL
            THEN 'blocked_original_period_not_open'
        WHEN preparation.id IS NOT NULL THEN 'prepared_not_posted'
        ELSE 'evidence_ready'
    END AS adjustment_status,
    CASE
        WHEN posting.id IS NOT NULL
             AND (
                original_queue.accounting_status <> 'posted_adjustment_review_required'
                OR replacement_queue.evidence_status <> 'evidence_ready'
                OR replacement_queue.source_id <> original_queue.source_id
                OR replacement_queue.tax_due <> evidence.replacement_tax_due
             )
            THEN 'A later tax-evidence change occurred after this protected adjustment; a new explicit review is required.'
        WHEN posting.id IS NOT NULL THEN NULL
        WHEN original_queue.accounting_status <> 'posted_adjustment_review_required'
            THEN 'Original liability is no longer in the exact stale-posting review state used by this adjustment evidence.'
        WHEN replacement_queue.evidence_id IS NULL
          OR replacement_queue.evidence_status <> 'evidence_ready'
          OR replacement_queue.source_id <> original_queue.source_id
          OR replacement_queue.loan_id <> original_queue.loan_id
          OR replacement_queue.client_id <> original_queue.client_id
          OR replacement_queue.tax_due <> evidence.replacement_tax_due
            THEN 'Exact replacement tax evidence no longer matches the retained correction evidence.'
        WHEN preparation.id IS NOT NULL AND journal.status IS DISTINCT FROM 'draft'
            THEN 'Prepared adjustment journal is not a draft but has no immutable protected adjustment posting audit.'
        WHEN open_period.id IS NULL
            THEN 'Original liability fiscal period is no longer open for the V1 pre-close adjustment path.'
        WHEN preparation.id IS NOT NULL
            THEN 'Exact Management confirmation is required before protected tax adjustment posting.'
        ELSE NULL
    END AS adjustment_blocker,
    true AS tax_settlement_enabled,
    true AS tax_adjustment_reversal_enabled,
    false AS automatic_source_posting
FROM accounting.v1_tax_adjustment_evidence evidence
JOIN accounting.v1_tax_liability_postings original_posting
  ON original_posting.id = evidence.tax_liability_posting_id
JOIN accounting.v1_tax_liability_preparations original_preparation
  ON original_preparation.id = original_posting.preparation_id
LEFT JOIN accounting.v1_tax_liability_queue original_queue
  ON original_queue.posting_id = original_posting.id
 AND original_queue.tax_type = evidence.tax_type
 AND original_queue.evidence_id = evidence.original_evidence_id
LEFT JOIN accounting.v1_tax_liability_queue replacement_queue
  ON replacement_queue.tax_type = evidence.tax_type
 AND replacement_queue.evidence_id = evidence.replacement_evidence_id
LEFT JOIN accounting.v1_tax_adjustment_preparations preparation
  ON preparation.adjustment_evidence_id = evidence.id
LEFT JOIN accounting.journal_entries journal
  ON journal.id = preparation.journal_entry_id
LEFT JOIN accounting.accounts debit_account
  ON debit_account.id = preparation.debit_account_id
LEFT JOIN accounting.accounts credit_account
  ON credit_account.id = preparation.credit_account_id
LEFT JOIN accounting.v1_tax_adjustment_postings posting
  ON posting.preparation_id = preparation.id
LEFT JOIN LATERAL (
    SELECT period.id
    FROM accounting.fiscal_periods period
    WHERE period.id = original_posting.confirmed_fiscal_period_id
      AND period.status = 'open'
      AND evidence.adjustment_date BETWEEN period.start_date AND period.end_date
    LIMIT 1
) open_period ON true;

CREATE OR REPLACE VIEW accounting.v1_tax_adjustment_summary AS
SELECT
    count(*)::bigint AS adjustment_evidence_count,
    count(*) FILTER (WHERE adjustment_status = 'evidence_ready')::bigint AS ready_to_prepare_count,
    count(*) FILTER (WHERE adjustment_status = 'prepared_not_posted')::bigint AS prepared_count,
    count(*) FILTER (WHERE adjustment_status = 'posted_unsettled_liability_reversal')::bigint AS posted_reversal_count,
    count(*) FILTER (WHERE adjustment_status = 'posted_settled_tax_recoverable')::bigint AS posted_recoverable_count,
    count(*) FILTER (WHERE adjustment_status = 'posted_further_adjustment_review_required')::bigint AS further_review_count,
    count(*) FILTER (WHERE adjustment_status LIKE 'blocked_%')::bigint AS blocked_count,
    coalesce(sum(adjustment_amount) FILTER (
        WHERE adjustment_status IN (
            'posted_unsettled_liability_reversal',
            'posted_settled_tax_recoverable'
        )
    ), 0)::numeric(18,2) AS posted_adjustment_total,
    true AS tax_settlement_enabled,
    true AS tax_adjustment_reversal_enabled,
    false AS automatic_source_posting
FROM accounting.v1_tax_adjustment_queue;

-- User-facing wrappers expose the current capability state without changing the base
-- readiness views that the protected settlement and adjustment functions use for exact
-- historical revalidation.
CREATE OR REPLACE VIEW accounting.v1_tax_liability_effective_queue AS
SELECT
    queue.tax_type,
    queue.evidence_id,
    queue.evidence_version,
    queue.source_id,
    queue.loan_id,
    queue.client_id,
    queue.recognition_date,
    queue.tax_due,
    queue.evidence_digest,
    queue.evidence_status,
    queue.evidence_blocker,
    queue.expense_account_code,
    queue.expense_account_name,
    queue.tax_payable_account_code,
    queue.tax_payable_account_name,
    queue.preparation_id,
    queue.journal_entry_id,
    queue.journal_status,
    queue.entry_number,
    queue.fiscal_period_id,
    queue.prepared_by_user_id,
    queue.prepared_at,
    queue.posting_id,
    queue.confirmation_digest,
    queue.posted_by_user_id,
    queue.posted_at,
    CASE
        WHEN adjusted.adjustment_posting_id IS NOT NULL
             AND adjusted.adjustment_kind = 'reverse_unsettled_liability'
            THEN 'posted_adjusted_reversed'
        WHEN adjusted.adjustment_posting_id IS NOT NULL
            THEN 'posted_adjusted_recoverable'
        WHEN covered.adjustment_posting_id IS NOT NULL
            THEN 'covered_by_settled_adjustment'
        ELSE queue.accounting_status
    END AS accounting_status,
    CASE
        WHEN adjusted.adjustment_posting_id IS NOT NULL
             AND adjusted.adjustment_kind = 'reverse_unsettled_liability'
            THEN 'Original stale tax liability was fully reversed by an immutable protected V1 tax adjustment.'
        WHEN adjusted.adjustment_posting_id IS NOT NULL
            THEN 'Original settled stale tax liability has an immutable protected Tax Recoverable correction; original settlement history is preserved.'
        WHEN covered.adjustment_posting_id IS NOT NULL
            THEN 'Current replacement evidence is economically covered by a posted settled-tax-recoverable adjustment and must not create a duplicate full liability.'
        ELSE queue.accounting_blocker
    END AS accounting_blocker,
    true AS protected_tax_liability_posting_enabled,
    true AS tax_settlement_enabled,
    true AS tax_adjustment_reversal_enabled,
    false AS automatic_source_posting
FROM accounting.v1_tax_liability_queue queue
LEFT JOIN LATERAL (
    SELECT evidence.adjustment_kind, posting.id AS adjustment_posting_id
    FROM accounting.v1_tax_adjustment_evidence evidence
    JOIN accounting.v1_tax_adjustment_postings posting
      ON posting.adjustment_evidence_id = evidence.id
    WHERE evidence.tax_liability_posting_id = queue.posting_id
    LIMIT 1
) adjusted ON true
LEFT JOIN LATERAL (
    SELECT posting.id AS adjustment_posting_id
    FROM accounting.v1_tax_adjustment_evidence evidence
    JOIN accounting.v1_tax_adjustment_postings posting
      ON posting.adjustment_evidence_id = evidence.id
    WHERE evidence.tax_type = queue.tax_type
      AND evidence.replacement_evidence_id = queue.evidence_id
      AND evidence.adjustment_kind = 'recognize_settled_tax_recoverable'
    LIMIT 1
) covered ON true;

CREATE OR REPLACE VIEW accounting.v1_tax_liability_effective_summary AS
SELECT
    count(*)::bigint AS evidence_item_count,
    count(*) FILTER (WHERE accounting_status = 'evidence_ready')::bigint AS ready_to_prepare_count,
    count(*) FILTER (WHERE accounting_status = 'prepared_not_posted')::bigint AS prepared_count,
    count(*) FILTER (WHERE accounting_status = 'posted')::bigint AS posted_count,
    count(*) FILTER (WHERE accounting_status = 'no_liability_required')::bigint AS no_liability_required_count,
    count(*) FILTER (WHERE accounting_status LIKE 'posted_adjusted_%')::bigint AS adjusted_posting_count,
    count(*) FILTER (WHERE accounting_status = 'covered_by_settled_adjustment')::bigint AS covered_replacement_count,
    count(*) FILTER (
        WHERE accounting_status NOT IN (
            'evidence_ready', 'prepared_not_posted', 'posted', 'no_liability_required',
            'posted_adjusted_reversed', 'posted_adjusted_recoverable',
            'covered_by_settled_adjustment'
        )
    )::bigint AS blocked_or_adjustment_review_count,
    coalesce(sum(tax_due) FILTER (WHERE accounting_status = 'posted'), 0)::numeric(18,2)
        AS posted_tax_liability_total,
    true AS protected_tax_liability_posting_enabled,
    true AS tax_settlement_enabled,
    true AS tax_adjustment_reversal_enabled,
    false AS automatic_source_posting
FROM accounting.v1_tax_liability_effective_queue;

CREATE OR REPLACE VIEW accounting.v1_tax_settlement_effective_queue AS
SELECT
    queue.tax_return_id,
    queue.tax_type,
    queue.return_period_start,
    queue.return_period_end,
    queue.filing_date,
    queue.declared_tax_due,
    queue.return_reference,
    queue.return_evidence_reference,
    queue.return_evidence_digest,
    queue.return_recorded_by_user_id,
    queue.return_recorded_at,
    queue.liability_count,
    queue.current_exact_count,
    queue.liability_total,
    queue.payment_evidence_id,
    queue.payment_date,
    queue.payment_amount,
    queue.cash_account_system_key,
    queue.cash_account_code,
    queue.cash_account_name,
    queue.payment_reference,
    queue.payment_evidence_reference,
    queue.payment_evidence_digest,
    queue.payment_recorded_by_user_id,
    queue.payment_recorded_at,
    queue.preparation_id,
    queue.journal_entry_id,
    queue.journal_status,
    queue.entry_number,
    queue.fiscal_period_id,
    queue.prepared_by_user_id,
    queue.prepared_at,
    queue.settlement_posting_id,
    queue.confirmation_digest,
    queue.posted_by_user_id,
    queue.posted_at,
    CASE
        WHEN queue.settlement_status = 'settled_adjustment_review_required'
             AND adjustment_state.stale_count > 0
             AND adjustment_state.adjusted_stale_count = adjustment_state.stale_count
            THEN 'settled_adjustment_recorded'
        WHEN queue.settlement_status = 'settled_adjustment_review_required'
             AND adjustment_state.adjustment_evidence_count > 0
            THEN 'settled_adjustment_in_progress'
        ELSE queue.settlement_status
    END AS settlement_status,
    CASE
        WHEN queue.settlement_status = 'settled_adjustment_review_required'
             AND adjustment_state.stale_count > 0
             AND adjustment_state.adjusted_stale_count = adjustment_state.stale_count
            THEN 'Every stale liability in this settled return has a posted protected adjustment; original return/payment/settlement history remains immutable.'
        WHEN queue.settlement_status = 'settled_adjustment_review_required'
             AND adjustment_state.adjustment_evidence_count > 0
            THEN 'Protected adjustment evidence exists but not every stale settled liability has a posted adjustment yet.'
        ELSE queue.settlement_blocker
    END AS settlement_blocker,
    true AS tax_settlement_enabled,
    true AS tax_adjustment_reversal_enabled,
    false AS automatic_source_posting
FROM accounting.v1_tax_settlement_queue queue
LEFT JOIN LATERAL (
    SELECT
        count(*) FILTER (
            WHERE liability_queue.accounting_status = 'posted_adjustment_review_required'
        )::integer AS stale_count,
        count(*) FILTER (
            WHERE liability_queue.accounting_status = 'posted_adjustment_review_required'
              AND adjustment_posting.id IS NOT NULL
        )::integer AS adjusted_stale_count,
        count(adjustment_evidence.id)::integer AS adjustment_evidence_count
    FROM accounting.v1_tax_return_liability_items item
    LEFT JOIN accounting.v1_tax_liability_queue liability_queue
      ON liability_queue.posting_id = item.tax_liability_posting_id
    LEFT JOIN accounting.v1_tax_adjustment_evidence adjustment_evidence
      ON adjustment_evidence.tax_liability_posting_id = item.tax_liability_posting_id
    LEFT JOIN accounting.v1_tax_adjustment_postings adjustment_posting
      ON adjustment_posting.adjustment_evidence_id = adjustment_evidence.id
    WHERE item.tax_return_id = queue.tax_return_id
) adjustment_state ON true;

CREATE OR REPLACE VIEW accounting.v1_tax_settlement_effective_summary AS
SELECT
    count(*)::bigint AS return_count,
    count(*) FILTER (WHERE settlement_status = 'return_recorded_awaiting_payment')::bigint AS awaiting_payment_evidence_count,
    count(*) FILTER (WHERE settlement_status = 'payment_evidence_ready')::bigint AS ready_to_prepare_count,
    count(*) FILTER (WHERE settlement_status = 'settlement_prepared')::bigint AS prepared_count,
    count(*) FILTER (WHERE settlement_status = 'settled')::bigint AS settled_count,
    count(*) FILTER (WHERE settlement_status = 'settled_adjustment_review_required')::bigint AS settled_adjustment_review_count,
    count(*) FILTER (WHERE settlement_status = 'settled_adjustment_in_progress')::bigint AS settled_adjustment_in_progress_count,
    count(*) FILTER (WHERE settlement_status = 'settled_adjustment_recorded')::bigint AS settled_adjustment_recorded_count,
    count(*) FILTER (WHERE settlement_status LIKE 'blocked_%' OR settlement_status LIKE 'prepared_blocked_%')::bigint AS blocked_count,
    coalesce(sum(payment_amount) FILTER (
        WHERE settlement_status IN ('settled', 'settled_adjustment_recorded')
    ), 0)::numeric(18,2) AS settled_tax_total,
    true AS tax_settlement_enabled,
    true AS tax_adjustment_reversal_enabled,
    false AS automatic_source_posting
FROM accounting.v1_tax_settlement_effective_queue;

COMMENT ON TABLE accounting.v1_tax_adjustment_evidence IS
'Immutable Management-approved V1 pre-close correction evidence for one stale posted tax liability and one exact newer current evidence item. It never rewrites original liability or settlement history.';
COMMENT ON TABLE accounting.v1_tax_adjustment_postings IS
'Immutable protected V1 tax adjustment posting audit. Unpaid stale liabilities reverse Dr 2100 / Cr original tax expense; already-settled decreases recognize Dr 1130 Tax Recoverable / Cr original tax expense.';
COMMENT ON VIEW accounting.v1_tax_adjustment_queue IS
'Protected V1 tax correction/reversal queue. This core executes unpaid full reversals and settled tax-decrease recoverable recognition only while the original fiscal period remains open.';

COMMIT;
