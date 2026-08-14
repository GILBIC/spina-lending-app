BEGIN;

-- Master #296 A6.2 additional-tax amendment sub-slice.
-- One exact filed V1 return may reserve one stale posted liability when one exact
-- newer current evidence item proves a strictly higher tax amount for the same
-- protected source, loan, client and tax type. Original return/liability/settlement
-- history remains immutable. The database derives only the supported additional-tax
-- delta; payment is separate evidence in 0088. Closed-period corrections fail closed
-- and automatic source posting stays disabled.

INSERT INTO core.permissions (code, description)
VALUES
    ('accounting.tax.additional_amendment_evidence.record', 'Record immutable Management-approved V1 amended-return/additional-assessment evidence for one exact upward tax correction'),
    ('accounting.tax.additional_amendment.prepare', 'Prepare a protected V1 additional-tax liability General Journal draft from exact amendment evidence'),
    ('accounting.tax.additional_amendment.post', 'Post a protected V1 additional-tax liability General Journal after exact Management confirmation')
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code IN (
      'accounting.tax.additional_amendment_evidence.record',
      'accounting.tax.additional_amendment.prepare',
      'accounting.tax.additional_amendment.post'
  )
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.v1_tax_additional_amendment_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key UUID NOT NULL UNIQUE,
    tax_return_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_return_evidence(id) ON DELETE RESTRICT,
    tax_type TEXT NOT NULL CHECK (
        tax_type IN ('documentary_stamp_tax', 'percentage_tax_lending')
    ),
    tax_liability_posting_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_liability_postings(id) ON DELETE RESTRICT,
    original_evidence_id UUID NOT NULL,
    replacement_evidence_id UUID NOT NULL,
    original_declared_tax_due NUMERIC(18,2) NOT NULL CHECK (original_declared_tax_due > 0),
    revised_declared_tax_due NUMERIC(18,2) NOT NULL CHECK (revised_declared_tax_due > 0),
    original_item_tax_due NUMERIC(18,2) NOT NULL CHECK (original_item_tax_due > 0),
    replacement_item_tax_due NUMERIC(18,2) NOT NULL CHECK (replacement_item_tax_due > 0),
    additional_tax_due NUMERIC(18,2) NOT NULL CHECK (additional_tax_due > 0),
    payment_basis TEXT NOT NULL CHECK (
        payment_basis IN ('full_revised_return_unpaid', 'additional_due_after_settlement')
    ),
    payment_required_amount NUMERIC(18,2) NOT NULL CHECK (payment_required_amount > 0),
    amendment_basis TEXT NOT NULL CHECK (
        amendment_basis IN ('amended_return', 'additional_assessment')
    ),
    amendment_date DATE NOT NULL,
    recognition_date DATE NOT NULL,
    amendment_reference TEXT NOT NULL CHECK (btrim(amendment_reference) <> ''),
    evidence_reference TEXT NOT NULL CHECK (btrim(evidence_reference) <> ''),
    evidence_digest TEXT NOT NULL CHECK (evidence_digest ~ '^[0-9a-f]{64}$'),
    evidence_note TEXT NOT NULL CHECK (length(btrim(evidence_note)) >= 20),
    original_payment_evidence_id UUID
        REFERENCES accounting.v1_tax_payment_evidence(id) ON DELETE RESTRICT,
    original_settlement_posting_id UUID
        REFERENCES accounting.v1_tax_settlement_postings(id) ON DELETE RESTRICT,
    original_settlement_journal_entry_id UUID
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    recorded_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (original_evidence_id <> replacement_evidence_id),
    CHECK (replacement_item_tax_due > original_item_tax_due),
    CHECK (additional_tax_due = replacement_item_tax_due - original_item_tax_due),
    CHECK (revised_declared_tax_due = original_declared_tax_due + additional_tax_due),
    CHECK (
        (
            payment_basis = 'full_revised_return_unpaid'
            AND original_payment_evidence_id IS NULL
            AND original_settlement_posting_id IS NULL
            AND original_settlement_journal_entry_id IS NULL
            AND payment_required_amount = revised_declared_tax_due
        )
        OR
        (
            payment_basis = 'additional_due_after_settlement'
            AND original_payment_evidence_id IS NOT NULL
            AND original_settlement_posting_id IS NOT NULL
            AND original_settlement_journal_entry_id IS NOT NULL
            AND payment_required_amount = additional_tax_due
        )
    )
);

CREATE INDEX IF NOT EXISTS v1_tax_additional_amendment_date_idx
    ON accounting.v1_tax_additional_amendment_evidence(amendment_date DESC, recorded_at DESC);
CREATE INDEX IF NOT EXISTS v1_tax_additional_amendment_replacement_idx
    ON accounting.v1_tax_additional_amendment_evidence(tax_type, replacement_evidence_id);

CREATE TABLE IF NOT EXISTS accounting.v1_tax_additional_liability_preparations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    amendment_evidence_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_additional_amendment_evidence(id) ON DELETE RESTRICT,
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    source_event_key TEXT NOT NULL UNIQUE CHECK (btrim(source_event_key) <> ''),
    recognition_date DATE NOT NULL,
    additional_tax_due NUMERIC(18,2) NOT NULL CHECK (additional_tax_due > 0),
    expense_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    tax_payable_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    fiscal_period_id UUID NOT NULL REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    prepared_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    prepared_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS accounting.v1_tax_additional_liability_postings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    preparation_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_additional_liability_preparations(id) ON DELETE RESTRICT,
    amendment_evidence_id UUID NOT NULL UNIQUE
        REFERENCES accounting.v1_tax_additional_amendment_evidence(id) ON DELETE RESTRICT,
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    entry_number TEXT NOT NULL UNIQUE CHECK (btrim(entry_number) <> ''),
    confirmation_token TEXT NOT NULL CHECK (confirmation_token ~ '^[0-9a-f]{64}$'),
    confirmation_digest TEXT NOT NULL CHECK (confirmation_digest ~ '^[0-9a-f]{64}$'),
    confirmed_evidence_digest TEXT NOT NULL CHECK (confirmed_evidence_digest ~ '^[0-9a-f]{64}$'),
    confirmed_original_declared_tax_due NUMERIC(18,2) NOT NULL CHECK (confirmed_original_declared_tax_due > 0),
    confirmed_revised_declared_tax_due NUMERIC(18,2) NOT NULL CHECK (confirmed_revised_declared_tax_due > 0),
    confirmed_original_item_tax_due NUMERIC(18,2) NOT NULL CHECK (confirmed_original_item_tax_due > 0),
    confirmed_replacement_item_tax_due NUMERIC(18,2) NOT NULL CHECK (confirmed_replacement_item_tax_due > 0),
    confirmed_additional_tax_due NUMERIC(18,2) NOT NULL CHECK (confirmed_additional_tax_due > 0),
    confirmed_expense_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    confirmed_tax_payable_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    confirmed_posting_date DATE NOT NULL,
    confirmed_fiscal_period_id UUID NOT NULL REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    policy_version TEXT NOT NULL CHECK (policy_version = 'v1_tax_additional_liability_posting_v1'),
    posted_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    posted_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE OR REPLACE FUNCTION accounting.guard_v1_tax_additional_amendment_immutable_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    insert_allowed BOOLEAN := false;
BEGIN
    IF TG_TABLE_NAME = 'v1_tax_additional_amendment_evidence' THEN
        insert_allowed := coalesce(current_setting('accounting.v1_tax_additional_amendment_evidence_insert_allowed', true), '') = 'on';
    ELSIF TG_TABLE_NAME = 'v1_tax_additional_liability_preparations' THEN
        insert_allowed := coalesce(current_setting('accounting.v1_tax_additional_liability_preparation_insert_allowed', true), '') = 'on';
    ELSIF TG_TABLE_NAME = 'v1_tax_additional_liability_postings' THEN
        insert_allowed := coalesce(current_setting('accounting.v1_tax_additional_liability_posting_insert_allowed', true), '') = 'on';
    END IF;

    IF TG_OP = 'INSERT' AND insert_allowed THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'V1 additional-tax amendment evidence and audit rows are immutable and must use the protected Management workflow.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_v1_tax_additional_amendment_evidence_guard
    ON accounting.v1_tax_additional_amendment_evidence;
CREATE TRIGGER accounting_v1_tax_additional_amendment_evidence_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.v1_tax_additional_amendment_evidence
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_additional_amendment_immutable_write();

DROP TRIGGER IF EXISTS accounting_v1_tax_additional_liability_preparation_guard
    ON accounting.v1_tax_additional_liability_preparations;
CREATE TRIGGER accounting_v1_tax_additional_liability_preparation_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.v1_tax_additional_liability_preparations
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_additional_amendment_immutable_write();

DROP TRIGGER IF EXISTS accounting_v1_tax_additional_liability_posting_guard
    ON accounting.v1_tax_additional_liability_postings;
CREATE TRIGGER accounting_v1_tax_additional_liability_posting_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.v1_tax_additional_liability_postings
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_additional_amendment_immutable_write();

-- Reserve an amended return before the obsolete base payment path can insert payment
-- evidence. Existing 0085 insert gates remain intact for all other settlement rows.
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
        IF TG_TABLE_NAME = 'v1_tax_payment_evidence' THEN
            PERFORM pg_advisory_xact_lock(
                hashtextextended('v1-tax-return-correction:' || NEW.tax_return_id::text, 0)
            );
            IF EXISTS (
                SELECT 1
                FROM accounting.v1_tax_additional_amendment_evidence amendment
                WHERE amendment.tax_return_id = NEW.tax_return_id
            ) THEN
                RAISE EXCEPTION 'This tax return is reserved by immutable additional-tax amendment evidence; use the protected additional-amendment payment workflow.';
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'V1 tax return/payment/settlement evidence and audit rows are immutable and must use the protected Management workflow.';
END;
$$;

-- Upward amendment and the 0086 decrease/reversal path are mutually exclusive for the
-- same original liability. The shared advisory lock makes the reservation race-safe.
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
        IF TG_TABLE_NAME = 'v1_tax_adjustment_evidence' THEN
            PERFORM pg_advisory_xact_lock(
                hashtextextended('v1-tax-adjustment-liability:' || NEW.tax_liability_posting_id::text, 0)
            );
            IF EXISTS (
                SELECT 1
                FROM accounting.v1_tax_additional_amendment_evidence amendment
                WHERE amendment.tax_liability_posting_id = NEW.tax_liability_posting_id
            ) THEN
                RAISE EXCEPTION 'This posted tax liability already belongs to immutable additional-tax amendment evidence and cannot enter a competing correction workflow.';
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'V1 tax adjustment evidence and audit rows are immutable and must use the protected Management workflow.';
END;
$$;

-- A replacement evidence item reserved by either a settled-tax-recoverable adjustment
-- or this upward amendment cannot create a duplicate full liability.
CREATE OR REPLACE FUNCTION accounting.guard_v1_tax_liability_preparation_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(current_setting('accounting.v1_tax_liability_preparation_insert_allowed', true), '') = 'on' THEN
        PERFORM pg_advisory_xact_lock(
            hashtextextended('v1-tax-amendment-replacement:' || NEW.evidence_id::text, 0)
        );
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
        IF EXISTS (
            SELECT 1
            FROM accounting.v1_tax_additional_amendment_evidence amendment
            WHERE amendment.tax_type = NEW.tax_type
              AND amendment.replacement_evidence_id = NEW.evidence_id
        ) THEN
            RAISE EXCEPTION 'Replacement tax evidence is reserved by immutable additional-tax amendment evidence and cannot create a duplicate full liability.';
        END IF;
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'V1 tax-liability preparation audit is immutable and must use the protected Management preparation function.';
END;
$$;

CREATE OR REPLACE FUNCTION accounting.guard_v1_tax_additional_liability_journal_entry_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    reversed_source TEXT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF (
            NEW.source_type = 'v1_tax_additional_liability'
            OR coalesce(NEW.source_event_key, '') LIKE 'v1_tax_additional_liability:%'
        )
        AND coalesce(current_setting('accounting.v1_tax_additional_liability_journal_prepare_allowed', true), '') <> 'on' THEN
            RAISE EXCEPTION 'V1 additional-tax liability journals must use the protected Management amendment preparation function.';
        END IF;

        IF NEW.reversal_of_entry_id IS NOT NULL THEN
            SELECT item.source_type INTO reversed_source
            FROM accounting.journal_entries item
            WHERE item.id = NEW.reversal_of_entry_id;
            IF reversed_source = 'v1_tax_additional_liability' THEN
                RAISE EXCEPTION 'Posted V1 additional-tax liabilities cannot be reversed through the manual General Journal; new protected amendment evidence is required.';
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.source_type IS DISTINCT FROM 'v1_tax_additional_liability' THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'V1 additional-tax liability journals are immutable and cannot be deleted.';
    END IF;

    IF OLD.status = 'draft' AND NEW.status = 'posted' THEN
        IF coalesce(current_setting('accounting.v1_tax_additional_liability_journal_post_allowed', true), '') <> 'on' THEN
            RAISE EXCEPTION 'V1 additional-tax liability journals require the protected Management amendment posting function.';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'V1 additional-tax liability journals are system generated and immutable.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_v1_tax_additional_liability_journal_entry_guard
    ON accounting.journal_entries;
CREATE TRIGGER accounting_v1_tax_additional_liability_journal_entry_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_additional_liability_journal_entry_change();

CREATE OR REPLACE FUNCTION accounting.guard_v1_tax_additional_liability_journal_line_change()
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

    IF target_source_type = 'v1_tax_additional_liability'
       AND coalesce(current_setting('accounting.v1_tax_additional_liability_journal_line_write_allowed', true), '') <> 'on' THEN
        RAISE EXCEPTION 'V1 additional-tax liability journal lines are system generated and immutable.';
    END IF;

    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_v1_tax_additional_liability_journal_line_guard
    ON accounting.journal_lines;
CREATE TRIGGER accounting_v1_tax_additional_liability_journal_line_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_lines
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_additional_liability_journal_line_change();

CREATE OR REPLACE FUNCTION accounting.record_v1_tax_additional_amendment_evidence(
    p_actor_user_id UUID,
    p_idempotency_key UUID,
    p_tax_return_id UUID,
    p_tax_liability_posting_id UUID,
    p_replacement_evidence_id UUID,
    p_amendment_basis TEXT,
    p_amendment_date DATE,
    p_recognition_date DATE,
    p_amendment_reference TEXT,
    p_evidence_reference TEXT,
    p_evidence_digest TEXT,
    p_evidence_note TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    normalized_basis TEXT := btrim(coalesce(p_amendment_basis, ''));
    normalized_amendment_reference TEXT := btrim(coalesce(p_amendment_reference, ''));
    normalized_evidence_reference TEXT := btrim(coalesce(p_evidence_reference, ''));
    normalized_digest TEXT := lower(btrim(coalesce(p_evidence_digest, '')));
    normalized_note TEXT := btrim(coalesce(p_evidence_note, ''));
    tax_return accounting.v1_tax_return_evidence%ROWTYPE;
    return_item accounting.v1_tax_return_liability_items%ROWTYPE;
    original_posting accounting.v1_tax_liability_postings%ROWTYPE;
    original_preparation accounting.v1_tax_liability_preparations%ROWTYPE;
    original_journal accounting.journal_entries%ROWTYPE;
    original_queue accounting.v1_tax_liability_queue%ROWTYPE;
    replacement_queue accounting.v1_tax_liability_queue%ROWTYPE;
    original_period accounting.fiscal_periods%ROWTYPE;
    original_payment accounting.v1_tax_payment_evidence%ROWTYPE;
    original_settlement accounting.v1_tax_settlement_postings%ROWTYPE;
    original_settlement_journal accounting.journal_entries%ROWTYPE;
    existing accounting.v1_tax_additional_amendment_evidence%ROWTYPE;
    item_count INTEGER;
    supported_count INTEGER;
    item_total NUMERIC(18,2);
    additional_due NUMERIC(18,2);
    revised_due NUMERIC(18,2);
    payment_basis_value TEXT;
    payment_required_value NUMERIC(18,2);
    created_id UUID;
BEGIN
    PERFORM accounting.require_v1_tax_management_actor(
        p_actor_user_id,
        'accounting.tax.additional_amendment_evidence.record'
    );

    IF p_idempotency_key IS NULL OR p_tax_return_id IS NULL
       OR p_tax_liability_posting_id IS NULL OR p_replacement_evidence_id IS NULL
       OR normalized_basis NOT IN ('amended_return', 'additional_assessment')
       OR p_amendment_date IS NULL OR p_recognition_date IS NULL
       OR normalized_amendment_reference = '' OR normalized_evidence_reference = ''
       OR normalized_digest !~ '^[0-9a-f]{64}$' OR length(normalized_note) < 20 THEN
        RAISE EXCEPTION 'Additional-tax amendment evidence requires exact filed return, stale liability, newer evidence, supported basis/dates and retained references/digest/note.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended('v1-tax-adjustment-liability:' || p_tax_liability_posting_id::text, 0)
    );
    PERFORM pg_advisory_xact_lock(
        hashtextextended('v1-tax-return-correction:' || p_tax_return_id::text, 0)
    );
    PERFORM pg_advisory_xact_lock(
        hashtextextended('v1-tax-amendment-replacement:' || p_replacement_evidence_id::text, 0)
    );

    SELECT * INTO existing
    FROM accounting.v1_tax_additional_amendment_evidence item
    WHERE item.idempotency_key = p_idempotency_key
    FOR SHARE;
    IF existing.id IS NOT NULL THEN
        IF existing.tax_return_id = p_tax_return_id
           AND existing.tax_liability_posting_id = p_tax_liability_posting_id
           AND existing.replacement_evidence_id = p_replacement_evidence_id
           AND existing.amendment_basis = normalized_basis
           AND existing.amendment_date = p_amendment_date
           AND existing.recognition_date = p_recognition_date
           AND existing.amendment_reference = normalized_amendment_reference
           AND existing.evidence_reference = normalized_evidence_reference
           AND existing.evidence_digest = normalized_digest
           AND existing.evidence_note = normalized_note
           AND existing.recorded_by_user_id = p_actor_user_id THEN
            RETURN existing.id;
        END IF;
        RAISE EXCEPTION 'Additional-tax amendment idempotency key already belongs to different immutable evidence.';
    END IF;

    SELECT * INTO tax_return
    FROM accounting.v1_tax_return_evidence item
    WHERE item.id = p_tax_return_id
    FOR SHARE;
    IF tax_return.id IS NULL THEN
        RAISE EXCEPTION 'Retained filed tax return evidence was not found for the additional-tax amendment.';
    END IF;
    IF p_amendment_date < tax_return.filing_date THEN
        RAISE EXCEPTION 'Additional-tax amendment/assessment evidence cannot predate the retained original filing date.';
    END IF;

    SELECT * INTO original_posting
    FROM accounting.v1_tax_liability_postings item
    WHERE item.id = p_tax_liability_posting_id
    FOR SHARE;
    IF original_posting.id IS NULL THEN
        RAISE EXCEPTION 'Original posted V1 tax liability was not found for the additional-tax amendment.';
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
        RAISE EXCEPTION 'Additional-tax amendment requires an exact posted liability whose protected evidence is currently stale/superseded.';
    END IF;

    SELECT * INTO return_item
    FROM accounting.v1_tax_return_liability_items item
    WHERE item.tax_return_id = tax_return.id
      AND item.tax_liability_posting_id = original_posting.id;
    IF return_item.tax_return_id IS NULL
       OR return_item.tax_type <> original_preparation.tax_type
       OR return_item.evidence_id <> original_preparation.evidence_id
       OR return_item.recognition_date <> original_preparation.recognition_date
       OR return_item.tax_due <> original_posting.confirmed_tax_due
       OR return_item.liability_entry_number <> original_posting.entry_number
       OR tax_return.tax_type <> original_preparation.tax_type THEN
        RAISE EXCEPTION 'Original filed return does not contain the exact immutable stale liability coordinates required for amendment.';
    END IF;

    SELECT * INTO replacement_queue
    FROM accounting.v1_tax_liability_queue queue
    WHERE queue.tax_type = original_preparation.tax_type
      AND queue.evidence_id = p_replacement_evidence_id;
    IF replacement_queue.evidence_id IS NULL
       OR replacement_queue.evidence_status <> 'evidence_ready'
       OR replacement_queue.accounting_status <> 'evidence_ready'
       OR replacement_queue.source_id <> original_queue.source_id
       OR replacement_queue.loan_id <> original_queue.loan_id
       OR replacement_queue.client_id <> original_queue.client_id
       OR replacement_queue.evidence_version <= original_queue.evidence_version
       OR replacement_queue.preparation_id IS NOT NULL
       OR replacement_queue.posting_id IS NOT NULL
       OR replacement_queue.tax_due <= original_posting.confirmed_tax_due THEN
        RAISE EXCEPTION 'Additional-tax amendment requires the exact newer current unposted evidence for the same protected source, loan, client and tax type with a strictly higher tax amount.';
    END IF;

    SELECT
        count(*)::integer,
        count(*) FILTER (
            WHERE (
                item.tax_liability_posting_id = original_posting.id
                AND queue.accounting_status = 'posted_adjustment_review_required'
            ) OR (
                item.tax_liability_posting_id <> original_posting.id
                AND queue.accounting_status = 'posted'
            )
        )::integer,
        coalesce(sum(item.tax_due), 0)::numeric(18,2)
    INTO item_count, supported_count, item_total
    FROM accounting.v1_tax_return_liability_items item
    LEFT JOIN accounting.v1_tax_liability_queue queue
      ON queue.posting_id = item.tax_liability_posting_id
     AND queue.tax_type = item.tax_type
     AND queue.evidence_id = item.evidence_id
    WHERE item.tax_return_id = tax_return.id;

    IF item_count <= 0 OR supported_count <> item_count
       OR item_total <> tax_return.declared_tax_due THEN
        RAISE EXCEPTION 'Additional-tax amendment supports exactly one stale upward liability per retained return; every other filed liability must remain exact and current.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM accounting.v1_tax_adjustment_evidence adjustment
        WHERE adjustment.tax_liability_posting_id = original_posting.id
    ) THEN
        RAISE EXCEPTION 'Original liability already has immutable protected correction evidence; competing additional-tax amendment evidence is not allowed.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM accounting.v1_tax_additional_amendment_evidence item
        WHERE item.tax_return_id = tax_return.id
           OR item.tax_liability_posting_id = original_posting.id
           OR (item.tax_type = original_preparation.tax_type
               AND item.replacement_evidence_id = replacement_queue.evidence_id)
    ) THEN
        RAISE EXCEPTION 'This return, stale liability, or replacement evidence is already reserved by immutable additional-tax amendment evidence.';
    END IF;

    SELECT * INTO original_period
    FROM accounting.fiscal_periods period
    WHERE period.id = original_posting.confirmed_fiscal_period_id
    FOR SHARE;
    IF original_period.id IS NULL OR original_period.status <> 'open'
       OR p_recognition_date NOT BETWEEN original_period.start_date AND original_period.end_date THEN
        RAISE EXCEPTION 'Additional-tax liability recognition requires the exact original liability fiscal period to remain open and contain the recognition date.';
    END IF;

    additional_due := replacement_queue.tax_due - original_posting.confirmed_tax_due;
    revised_due := tax_return.declared_tax_due + additional_due;

    SELECT * INTO original_payment
    FROM accounting.v1_tax_payment_evidence payment
    WHERE payment.tax_return_id = tax_return.id
    FOR SHARE;
    IF original_payment.id IS NULL THEN
        payment_basis_value := 'full_revised_return_unpaid';
        payment_required_value := revised_due;
    ELSE
        SELECT * INTO original_settlement
        FROM accounting.v1_tax_settlement_postings settlement
        WHERE settlement.tax_return_id = tax_return.id
        FOR SHARE;
        IF original_settlement.id IS NULL THEN
            RAISE EXCEPTION 'Original return has payment evidence without an exact posted settlement; additional-tax amendment is blocked until that in-flight state is explicitly resolved.';
        END IF;
        SELECT * INTO original_settlement_journal
        FROM accounting.journal_entries journal
        WHERE journal.id = original_settlement.journal_entry_id
        FOR SHARE;
        IF original_payment.payment_amount <> tax_return.declared_tax_due
           OR original_settlement.payment_evidence_id <> original_payment.id
           OR original_settlement_journal.id IS NULL
           OR original_settlement_journal.status <> 'posted'
           OR original_settlement_journal.entry_number <> original_settlement.entry_number THEN
            RAISE EXCEPTION 'Original tax settlement history no longer exactly matches the retained filed return and payment evidence.';
        END IF;
        payment_basis_value := 'additional_due_after_settlement';
        payment_required_value := additional_due;
    END IF;

    PERFORM set_config('accounting.v1_tax_additional_amendment_evidence_insert_allowed', 'on', true);
    INSERT INTO accounting.v1_tax_additional_amendment_evidence(
        idempotency_key, tax_return_id, tax_type, tax_liability_posting_id,
        original_evidence_id, replacement_evidence_id,
        original_declared_tax_due, revised_declared_tax_due,
        original_item_tax_due, replacement_item_tax_due, additional_tax_due,
        payment_basis, payment_required_amount, amendment_basis,
        amendment_date, recognition_date, amendment_reference,
        evidence_reference, evidence_digest, evidence_note,
        original_payment_evidence_id, original_settlement_posting_id,
        original_settlement_journal_entry_id, recorded_by_user_id
    ) VALUES (
        p_idempotency_key, tax_return.id, original_preparation.tax_type,
        original_posting.id, original_preparation.evidence_id,
        replacement_queue.evidence_id, tax_return.declared_tax_due, revised_due,
        original_posting.confirmed_tax_due, replacement_queue.tax_due,
        additional_due, payment_basis_value, payment_required_value,
        normalized_basis, p_amendment_date, p_recognition_date,
        normalized_amendment_reference, normalized_evidence_reference,
        normalized_digest, normalized_note, original_payment.id,
        original_settlement.id, original_settlement_journal.id,
        p_actor_user_id
    ) RETURNING id INTO created_id;
    PERFORM set_config('accounting.v1_tax_additional_amendment_evidence_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.tax.additional_amendment_evidence.recorded',
        'v1_tax_additional_amendment',
        created_id,
        jsonb_build_object(
            'tax_return_id', tax_return.id,
            'tax_type', original_preparation.tax_type,
            'tax_liability_posting_id', original_posting.id,
            'original_evidence_id', original_preparation.evidence_id,
            'replacement_evidence_id', replacement_queue.evidence_id,
            'original_declared_tax_due', tax_return.declared_tax_due,
            'revised_declared_tax_due', revised_due,
            'additional_tax_due', additional_due,
            'payment_basis', payment_basis_value,
            'payment_required_amount', payment_required_value,
            'amendment_basis', normalized_basis,
            'amendment_date', p_amendment_date,
            'recognition_date', p_recognition_date,
            'evidence_digest', normalized_digest,
            'automatic_source_posting', false
        )
    );

    RETURN created_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.prepare_v1_tax_additional_liability_journal(
    p_amendment_evidence_id UUID,
    p_actor_user_id UUID
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    evidence accounting.v1_tax_additional_amendment_evidence%ROWTYPE;
    existing accounting.v1_tax_additional_liability_preparations%ROWTYPE;
    tax_return accounting.v1_tax_return_evidence%ROWTYPE;
    original_posting accounting.v1_tax_liability_postings%ROWTYPE;
    original_preparation accounting.v1_tax_liability_preparations%ROWTYPE;
    original_queue accounting.v1_tax_liability_queue%ROWTYPE;
    replacement_queue accounting.v1_tax_liability_queue%ROWTYPE;
    original_payment accounting.v1_tax_payment_evidence%ROWTYPE;
    original_settlement accounting.v1_tax_settlement_postings%ROWTYPE;
    original_settlement_journal accounting.journal_entries%ROWTYPE;
    target_period accounting.fiscal_periods%ROWTYPE;
    expense_account accounting.accounts%ROWTYPE;
    payable_account accounting.accounts%ROWTYPE;
    item_count INTEGER;
    supported_count INTEGER;
    item_total NUMERIC(18,2);
    protected_source_event_key TEXT;
    created_journal_id UUID;
BEGIN
    PERFORM accounting.require_v1_tax_management_actor(
        p_actor_user_id,
        'accounting.tax.additional_amendment.prepare'
    );
    IF p_amendment_evidence_id IS NULL THEN
        RAISE EXCEPTION 'Additional-tax liability preparation requires exact immutable amendment evidence.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended('v1-tax-additional-amendment:' || p_amendment_evidence_id::text, 0)
    );

    SELECT * INTO existing
    FROM accounting.v1_tax_additional_liability_preparations item
    WHERE item.amendment_evidence_id = p_amendment_evidence_id;
    IF existing.id IS NOT NULL THEN
        RETURN existing.journal_entry_id;
    END IF;

    SELECT * INTO evidence
    FROM accounting.v1_tax_additional_amendment_evidence item
    WHERE item.id = p_amendment_evidence_id
    FOR SHARE;
    IF evidence.id IS NULL THEN
        RAISE EXCEPTION 'Additional-tax amendment evidence was not found.';
    END IF;

    SELECT * INTO tax_return
    FROM accounting.v1_tax_return_evidence item
    WHERE item.id = evidence.tax_return_id
    FOR SHARE;
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

    IF tax_return.id IS NULL OR original_posting.id IS NULL OR original_preparation.id IS NULL
       OR original_queue.accounting_status <> 'posted_adjustment_review_required'
       OR replacement_queue.evidence_id IS NULL
       OR replacement_queue.evidence_status <> 'evidence_ready'
       OR replacement_queue.accounting_status <> 'evidence_ready'
       OR replacement_queue.source_id <> original_queue.source_id
       OR replacement_queue.loan_id <> original_queue.loan_id
       OR replacement_queue.client_id <> original_queue.client_id
       OR replacement_queue.evidence_version <= original_queue.evidence_version
       OR replacement_queue.preparation_id IS NOT NULL
       OR replacement_queue.posting_id IS NOT NULL
       OR original_preparation.evidence_id <> evidence.original_evidence_id
       OR original_posting.confirmed_tax_due <> evidence.original_item_tax_due
       OR replacement_queue.tax_due <> evidence.replacement_item_tax_due
       OR evidence.additional_tax_due <> evidence.replacement_item_tax_due - evidence.original_item_tax_due
       OR tax_return.declared_tax_due <> evidence.original_declared_tax_due
       OR evidence.revised_declared_tax_due <> evidence.original_declared_tax_due + evidence.additional_tax_due THEN
        RAISE EXCEPTION 'Exact original return/liability or current replacement evidence changed after additional-tax amendment evidence was recorded.';
    END IF;

    SELECT
        count(*)::integer,
        count(*) FILTER (
            WHERE (
                item.tax_liability_posting_id = original_posting.id
                AND queue.accounting_status = 'posted_adjustment_review_required'
            ) OR (
                item.tax_liability_posting_id <> original_posting.id
                AND queue.accounting_status = 'posted'
            )
        )::integer,
        coalesce(sum(item.tax_due), 0)::numeric(18,2)
    INTO item_count, supported_count, item_total
    FROM accounting.v1_tax_return_liability_items item
    LEFT JOIN accounting.v1_tax_liability_queue queue
      ON queue.posting_id = item.tax_liability_posting_id
     AND queue.tax_type = item.tax_type
     AND queue.evidence_id = item.evidence_id
    WHERE item.tax_return_id = tax_return.id;
    IF item_count <= 0 OR supported_count <> item_count
       OR item_total <> evidence.original_declared_tax_due THEN
        RAISE EXCEPTION 'Retained return composition is no longer exact enough for protected additional-tax liability recognition.';
    END IF;

    SELECT * INTO target_period
    FROM accounting.fiscal_periods period
    WHERE period.id = original_posting.confirmed_fiscal_period_id
    FOR SHARE;
    IF target_period.id IS NULL OR target_period.status <> 'open'
       OR evidence.recognition_date NOT BETWEEN target_period.start_date AND target_period.end_date THEN
        RAISE EXCEPTION 'Additional-tax liability requires the exact original liability fiscal period to remain open.';
    END IF;

    IF evidence.payment_basis = 'full_revised_return_unpaid' THEN
        SELECT * INTO original_payment
        FROM accounting.v1_tax_payment_evidence payment
        WHERE payment.tax_return_id = evidence.tax_return_id
        FOR SHARE;
        IF original_payment.id IS NOT NULL
           OR evidence.original_payment_evidence_id IS NOT NULL
           OR evidence.original_settlement_posting_id IS NOT NULL THEN
            RAISE EXCEPTION 'Original return payment state changed after unpaid amendment evidence was recorded.';
        END IF;
        IF evidence.payment_required_amount <> evidence.revised_declared_tax_due THEN
            RAISE EXCEPTION 'Unpaid amended return must retain the full revised declared tax due as the later payment requirement.';
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
           OR original_settlement_journal.entry_number <> original_settlement.entry_number
           OR evidence.payment_required_amount <> evidence.additional_tax_due THEN
            RAISE EXCEPTION 'Exact original settled-return history changed after additional-tax amendment evidence was recorded.';
        END IF;
    END IF;

    SELECT * INTO expense_account
    FROM accounting.accounts account
    WHERE account.id = original_posting.confirmed_expense_account_id
    FOR SHARE;
    SELECT * INTO payable_account
    FROM accounting.accounts account
    WHERE account.id = original_posting.confirmed_tax_payable_account_id
    FOR SHARE;
    IF expense_account.id IS NULL OR expense_account.account_type <> 'expense'
       OR expense_account.normal_balance <> 'debit' OR NOT expense_account.is_active
       OR NOT expense_account.is_posting
       OR expense_account.code <> (
            CASE WHEN evidence.tax_type = 'documentary_stamp_tax' THEN '5310' ELSE '5300' END
       ) THEN
        RAISE EXCEPTION 'Exact original dedicated tax expense account is no longer posting-ready for the additional liability.';
    END IF;
    IF payable_account.id IS NULL OR payable_account.system_key <> 'tax_payables'
       OR payable_account.code <> '2100' OR payable_account.account_type <> 'liability'
       OR payable_account.normal_balance <> 'credit' OR NOT payable_account.is_active
       OR NOT payable_account.is_posting THEN
        RAISE EXCEPTION 'Exact active 2100 Tax Payables is required for the protected additional-tax liability.';
    END IF;

    protected_source_event_key := 'v1_tax_additional_liability:' || evidence.id::text;
    IF EXISTS (
        SELECT 1 FROM accounting.journal_entries journal
        WHERE journal.source_event_key = protected_source_event_key
    ) THEN
        RAISE EXCEPTION 'Protected V1 additional-tax liability source identity is already occupied outside the amendment audit.';
    END IF;

    PERFORM set_config('accounting.v1_tax_additional_liability_journal_prepare_allowed', 'on', true);
    INSERT INTO accounting.journal_entries(
        fiscal_period_id, posting_date, description, status, source_type,
        source_reference, source_event_key, created_by_user_id, updated_at
    ) VALUES (
        target_period.id, evidence.recognition_date,
        'Protected V1 additional tax from ' || evidence.amendment_basis || ': ' || evidence.amendment_reference,
        'draft', 'v1_tax_additional_liability', evidence.id::text,
        protected_source_event_key, p_actor_user_id, now()
    ) RETURNING id INTO created_journal_id;
    PERFORM set_config('accounting.v1_tax_additional_liability_journal_prepare_allowed', 'off', true);

    PERFORM set_config('accounting.v1_tax_additional_liability_journal_line_write_allowed', 'on', true);
    INSERT INTO accounting.journal_lines(
        journal_entry_id, line_number, account_id, description, debit, credit,
        client_id, loan_id
    ) VALUES
        (
            created_journal_id, 1, expense_account.id,
            'Recognize retained additional tax due', evidence.additional_tax_due, 0,
            original_queue.client_id, original_queue.loan_id
        ),
        (
            created_journal_id, 2, payable_account.id,
            'Recognize additional Tax Payables', 0, evidence.additional_tax_due,
            original_queue.client_id, original_queue.loan_id
        );
    PERFORM set_config('accounting.v1_tax_additional_liability_journal_line_write_allowed', 'off', true);

    INSERT INTO accounting.journal_events(journal_entry_id, event_type, actor_user_id, details)
    VALUES (
        created_journal_id, 'draft_created', p_actor_user_id,
        jsonb_build_object(
            'source_type', 'v1_tax_additional_liability',
            'amendment_evidence_id', evidence.id,
            'tax_return_id', evidence.tax_return_id,
            'tax_liability_posting_id', evidence.tax_liability_posting_id,
            'original_evidence_id', evidence.original_evidence_id,
            'replacement_evidence_id', evidence.replacement_evidence_id,
            'additional_tax_due', evidence.additional_tax_due,
            'expense_account_code', expense_account.code,
            'tax_payable_account_code', payable_account.code,
            'automatic_source_posting', false
        )
    );

    PERFORM set_config('accounting.v1_tax_additional_liability_preparation_insert_allowed', 'on', true);
    INSERT INTO accounting.v1_tax_additional_liability_preparations(
        amendment_evidence_id, journal_entry_id, source_event_key,
        recognition_date, additional_tax_due, expense_account_id,
        tax_payable_account_id, fiscal_period_id, prepared_by_user_id
    ) VALUES (
        evidence.id, created_journal_id, protected_source_event_key,
        evidence.recognition_date, evidence.additional_tax_due,
        expense_account.id, payable_account.id, target_period.id, p_actor_user_id
    );
    PERFORM set_config('accounting.v1_tax_additional_liability_preparation_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id, 'accounting.tax.additional_amendment.liability_prepared',
        'v1_tax_additional_amendment', evidence.id,
        jsonb_build_object(
            'journal_entry_id', created_journal_id,
            'additional_tax_due', evidence.additional_tax_due,
            'expense_account_code', expense_account.code,
            'tax_payable_account_code', payable_account.code,
            'fiscal_period_id', target_period.id,
            'automatic_source_posting', false
        )
    );

    RETURN created_journal_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.post_v1_tax_additional_liability_journal(
    p_amendment_evidence_id UUID,
    p_actor_user_id UUID,
    p_confirmation_token TEXT,
    p_expected_evidence_digest TEXT,
    p_expected_original_declared_tax_due NUMERIC,
    p_expected_revised_declared_tax_due NUMERIC,
    p_expected_original_item_tax_due NUMERIC,
    p_expected_replacement_item_tax_due NUMERIC,
    p_expected_additional_tax_due NUMERIC,
    p_expected_expense_account_code TEXT,
    p_expected_tax_payable_account_code TEXT,
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
    normalized_original_declared NUMERIC(18,2) := round(coalesce(p_expected_original_declared_tax_due, -1), 2);
    normalized_revised_declared NUMERIC(18,2) := round(coalesce(p_expected_revised_declared_tax_due, -1), 2);
    normalized_original_item NUMERIC(18,2) := round(coalesce(p_expected_original_item_tax_due, -1), 2);
    normalized_replacement_item NUMERIC(18,2) := round(coalesce(p_expected_replacement_item_tax_due, -1), 2);
    normalized_additional NUMERIC(18,2) := round(coalesce(p_expected_additional_tax_due, -1), 2);
    normalized_expense_code TEXT := btrim(coalesce(p_expected_expense_account_code, ''));
    normalized_payable_code TEXT := btrim(coalesce(p_expected_tax_payable_account_code, ''));
    evidence accounting.v1_tax_additional_amendment_evidence%ROWTYPE;
    preparation accounting.v1_tax_additional_liability_preparations%ROWTYPE;
    existing accounting.v1_tax_additional_liability_postings%ROWTYPE;
    original_posting accounting.v1_tax_liability_postings%ROWTYPE;
    original_queue accounting.v1_tax_liability_queue%ROWTYPE;
    replacement_queue accounting.v1_tax_liability_queue%ROWTYPE;
    original_payment accounting.v1_tax_payment_evidence%ROWTYPE;
    original_settlement accounting.v1_tax_settlement_postings%ROWTYPE;
    original_settlement_journal accounting.journal_entries%ROWTYPE;
    period_row accounting.fiscal_periods%ROWTYPE;
    expense_account accounting.accounts%ROWTYPE;
    payable_account accounting.accounts%ROWTYPE;
    journal accounting.journal_entries%ROWTYPE;
    line_count INTEGER;
    total_debit NUMERIC(18,2);
    total_credit NUMERIC(18,2);
    expected_expense_debit NUMERIC(18,2);
    expected_payable_credit NUMERIC(18,2);
    foreign_line_count INTEGER;
    generated_entry_number TEXT;
    confirmation_digest_value TEXT;
    created_posting_id UUID;
BEGIN
    PERFORM accounting.require_v1_tax_management_actor(
        p_actor_user_id,
        'accounting.tax.additional_amendment.post'
    );

    IF p_amendment_evidence_id IS NULL
       OR p_policy_version IS DISTINCT FROM 'v1_tax_additional_liability_posting_v1'
       OR normalized_token !~ '^[0-9a-f]{64}$'
       OR normalized_digest !~ '^[0-9a-f]{64}$'
       OR p_expected_original_declared_tax_due IS DISTINCT FROM normalized_original_declared
       OR p_expected_revised_declared_tax_due IS DISTINCT FROM normalized_revised_declared
       OR p_expected_original_item_tax_due IS DISTINCT FROM normalized_original_item
       OR p_expected_replacement_item_tax_due IS DISTINCT FROM normalized_replacement_item
       OR p_expected_additional_tax_due IS DISTINCT FROM normalized_additional
       OR normalized_original_declared <= 0 OR normalized_revised_declared <= normalized_original_declared
       OR normalized_original_item <= 0 OR normalized_replacement_item <= normalized_original_item
       OR normalized_additional <= 0
       OR normalized_expense_code = '' OR normalized_payable_code = ''
       OR p_expected_posting_date IS NULL OR p_expected_fiscal_period_id IS NULL THEN
        RAISE EXCEPTION 'Protected additional-tax liability posting requires exact Management confirmation, evidence digest, original/revised totals, original/replacement item tax, delta, accounts, date, period and policy.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended('v1-tax-additional-amendment:' || p_amendment_evidence_id::text, 0)
    );

    SELECT * INTO evidence
    FROM accounting.v1_tax_additional_amendment_evidence item
    WHERE item.id = p_amendment_evidence_id
    FOR SHARE;
    SELECT * INTO preparation
    FROM accounting.v1_tax_additional_liability_preparations item
    WHERE item.amendment_evidence_id = p_amendment_evidence_id
    FOR SHARE;
    IF evidence.id IS NULL OR preparation.id IS NULL THEN
        RAISE EXCEPTION 'Additional-tax liability must have exact immutable amendment evidence and a protected preparation before posting.';
    END IF;

    SELECT * INTO existing
    FROM accounting.v1_tax_additional_liability_postings item
    WHERE item.preparation_id = preparation.id
    FOR SHARE;
    IF existing.id IS NOT NULL THEN
        IF existing.confirmation_token = normalized_token
           AND existing.confirmed_evidence_digest = normalized_digest
           AND existing.confirmed_original_declared_tax_due = normalized_original_declared
           AND existing.confirmed_revised_declared_tax_due = normalized_revised_declared
           AND existing.confirmed_original_item_tax_due = normalized_original_item
           AND existing.confirmed_replacement_item_tax_due = normalized_replacement_item
           AND existing.confirmed_additional_tax_due = normalized_additional
           AND existing.confirmed_posting_date = p_expected_posting_date
           AND existing.confirmed_fiscal_period_id = p_expected_fiscal_period_id
           AND existing.policy_version = p_policy_version
           AND existing.posted_by_user_id = p_actor_user_id
           AND EXISTS (
                SELECT 1 FROM accounting.accounts account
                WHERE account.id = existing.confirmed_expense_account_id
                  AND account.code = normalized_expense_code
           )
           AND EXISTS (
                SELECT 1 FROM accounting.accounts account
                WHERE account.id = existing.confirmed_tax_payable_account_id
                  AND account.code = normalized_payable_code
           ) THEN
            RETURN existing.id;
        END IF;
        RAISE EXCEPTION 'Existing V1 additional-tax liability posting does not match the immutable retry identity.';
    END IF;

    IF evidence.evidence_digest <> normalized_digest
       OR evidence.original_declared_tax_due <> normalized_original_declared
       OR evidence.revised_declared_tax_due <> normalized_revised_declared
       OR evidence.original_item_tax_due <> normalized_original_item
       OR evidence.replacement_item_tax_due <> normalized_replacement_item
       OR evidence.additional_tax_due <> normalized_additional
       OR evidence.recognition_date <> p_expected_posting_date
       OR normalized_revised_declared <> normalized_original_declared + normalized_additional
       OR normalized_additional <> normalized_replacement_item - normalized_original_item
       OR preparation.recognition_date <> p_expected_posting_date
       OR preparation.additional_tax_due <> normalized_additional THEN
        RAISE EXCEPTION 'Exact immutable additional-tax amendment evidence no longer matches the confirmed liability coordinates.';
    END IF;

    SELECT * INTO original_posting
    FROM accounting.v1_tax_liability_postings item
    WHERE item.id = evidence.tax_liability_posting_id
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
    IF original_posting.id IS NULL
       OR original_queue.accounting_status <> 'posted_adjustment_review_required'
       OR replacement_queue.evidence_id IS NULL
       OR replacement_queue.evidence_status <> 'evidence_ready'
       OR replacement_queue.accounting_status <> 'evidence_ready'
       OR replacement_queue.source_id <> original_queue.source_id
       OR replacement_queue.loan_id <> original_queue.loan_id
       OR replacement_queue.client_id <> original_queue.client_id
       OR replacement_queue.tax_due <> normalized_replacement_item
       OR replacement_queue.preparation_id IS NOT NULL
       OR replacement_queue.posting_id IS NOT NULL
       OR original_posting.confirmed_tax_due <> normalized_original_item THEN
        RAISE EXCEPTION 'Original stale liability or exact current replacement evidence changed before additional-tax liability posting.';
    END IF;

    IF evidence.payment_basis = 'full_revised_return_unpaid' THEN
        SELECT * INTO original_payment
        FROM accounting.v1_tax_payment_evidence payment
        WHERE payment.tax_return_id = evidence.tax_return_id
        FOR SHARE;
        IF original_payment.id IS NOT NULL THEN
            RAISE EXCEPTION 'Base return payment evidence appeared after unpaid additional-tax amendment evidence was recorded.';
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
        FROM accounting.journal_entries item
        WHERE item.id = evidence.original_settlement_journal_entry_id
        FOR SHARE;
        IF original_payment.id IS NULL OR original_settlement.id IS NULL
           OR original_settlement.payment_evidence_id <> original_payment.id
           OR original_settlement.tax_return_id <> evidence.tax_return_id
           OR original_settlement_journal.id IS NULL
           OR original_settlement_journal.status <> 'posted'
           OR original_settlement_journal.entry_number <> original_settlement.entry_number THEN
            RAISE EXCEPTION 'Original settled return history changed before additional-tax liability posting.';
        END IF;
    END IF;

    SELECT * INTO period_row
    FROM accounting.fiscal_periods period
    WHERE period.id = p_expected_fiscal_period_id
    FOR SHARE;
    IF period_row.id IS NULL OR period_row.status <> 'open'
       OR period_row.id <> original_posting.confirmed_fiscal_period_id
       OR preparation.fiscal_period_id <> period_row.id
       OR p_expected_posting_date NOT BETWEEN period_row.start_date AND period_row.end_date THEN
        RAISE EXCEPTION 'Additional-tax liability posting requires the exact still-open original liability fiscal period.';
    END IF;

    SELECT * INTO expense_account
    FROM accounting.accounts account
    WHERE account.id = preparation.expense_account_id
    FOR SHARE;
    SELECT * INTO payable_account
    FROM accounting.accounts account
    WHERE account.id = preparation.tax_payable_account_id
    FOR SHARE;
    IF expense_account.id IS NULL OR expense_account.code <> normalized_expense_code
       OR expense_account.id <> original_posting.confirmed_expense_account_id
       OR expense_account.account_type <> 'expense'
       OR expense_account.normal_balance <> 'debit'
       OR NOT expense_account.is_active OR NOT expense_account.is_posting
       OR payable_account.id IS NULL OR payable_account.code <> normalized_payable_code
       OR payable_account.system_key <> 'tax_payables' OR payable_account.code <> '2100'
       OR payable_account.account_type <> 'liability'
       OR payable_account.normal_balance <> 'credit'
       OR NOT payable_account.is_active OR NOT payable_account.is_posting THEN
        RAISE EXCEPTION 'Exact confirmed additional-tax expense/payable accounts are no longer posting-ready.';
    END IF;

    SELECT * INTO journal
    FROM accounting.journal_entries item
    WHERE item.id = preparation.journal_entry_id
    FOR UPDATE;
    IF journal.id IS NULL OR journal.status <> 'draft'
       OR journal.source_type <> 'v1_tax_additional_liability'
       OR journal.source_reference <> evidence.id::text
       OR journal.source_event_key <> preparation.source_event_key
       OR journal.posting_date <> p_expected_posting_date
       OR journal.fiscal_period_id <> period_row.id
       OR journal.reversal_of_entry_id IS NOT NULL THEN
        RAISE EXCEPTION 'Prepared V1 additional-tax liability General Journal draft no longer matches the protected amendment coordinates.';
    END IF;

    SELECT
        count(*)::integer,
        coalesce(sum(line.debit), 0)::numeric(18,2),
        coalesce(sum(line.credit), 0)::numeric(18,2),
        coalesce(sum(line.debit) FILTER (WHERE line.account_id = expense_account.id), 0)::numeric(18,2),
        coalesce(sum(line.credit) FILTER (WHERE line.account_id = payable_account.id), 0)::numeric(18,2),
        count(*) FILTER (
            WHERE line.account_id NOT IN (expense_account.id, payable_account.id)
               OR line.client_id IS DISTINCT FROM original_queue.client_id
               OR line.loan_id IS DISTINCT FROM original_queue.loan_id
        )::integer
    INTO line_count, total_debit, total_credit,
         expected_expense_debit, expected_payable_credit, foreign_line_count
    FROM accounting.journal_lines line
    WHERE line.journal_entry_id = journal.id;

    IF line_count <> 2
       OR total_debit <> normalized_additional
       OR total_credit <> normalized_additional
       OR expected_expense_debit <> normalized_additional
       OR expected_payable_credit <> normalized_additional
       OR foreign_line_count <> 0 THEN
        RAISE EXCEPTION 'Prepared V1 additional-tax liability lines no longer exactly reconcile to retained amendment evidence.';
    END IF;

    confirmation_digest_value := encode(sha256(convert_to(concat_ws('|',
        p_policy_version, evidence.id::text, evidence.tax_return_id::text,
        evidence.tax_liability_posting_id::text, evidence.original_evidence_id::text,
        evidence.replacement_evidence_id::text, normalized_digest,
        to_char(normalized_original_declared, 'FM999999999999990.00'),
        to_char(normalized_revised_declared, 'FM999999999999990.00'),
        to_char(normalized_original_item, 'FM999999999999990.00'),
        to_char(normalized_replacement_item, 'FM999999999999990.00'),
        to_char(normalized_additional, 'FM999999999999990.00'),
        expense_account.id::text, payable_account.id::text,
        p_expected_posting_date::text, period_row.id::text,
        journal.id::text, normalized_token
    ), 'UTF8')), 'hex');

    PERFORM set_config('accounting.v1_tax_additional_liability_journal_post_allowed', 'on', true);
    generated_entry_number := accounting.post_journal_entry(journal.id, p_actor_user_id);
    PERFORM set_config('accounting.v1_tax_additional_liability_journal_post_allowed', 'off', true);

    IF coalesce(current_setting('accounting.v1_tax_additional_liability_force_audit_failure', true), '') = 'on' THEN
        RAISE EXCEPTION 'Forced V1 additional-tax liability audit failure.';
    END IF;

    PERFORM set_config('accounting.v1_tax_additional_liability_posting_insert_allowed', 'on', true);
    INSERT INTO accounting.v1_tax_additional_liability_postings(
        preparation_id, amendment_evidence_id, journal_entry_id, entry_number,
        confirmation_token, confirmation_digest, confirmed_evidence_digest,
        confirmed_original_declared_tax_due, confirmed_revised_declared_tax_due,
        confirmed_original_item_tax_due, confirmed_replacement_item_tax_due,
        confirmed_additional_tax_due, confirmed_expense_account_id,
        confirmed_tax_payable_account_id, confirmed_posting_date,
        confirmed_fiscal_period_id, policy_version, posted_by_user_id
    ) VALUES (
        preparation.id, evidence.id, journal.id, generated_entry_number,
        normalized_token, confirmation_digest_value, normalized_digest,
        normalized_original_declared, normalized_revised_declared,
        normalized_original_item, normalized_replacement_item,
        normalized_additional, expense_account.id, payable_account.id,
        p_expected_posting_date, period_row.id, p_policy_version,
        p_actor_user_id
    ) RETURNING id INTO created_posting_id;
    PERFORM set_config('accounting.v1_tax_additional_liability_posting_insert_allowed', 'off', true);

    INSERT INTO accounting.journal_events(journal_entry_id, event_type, actor_user_id, details)
    VALUES (
        journal.id, 'posted', p_actor_user_id,
        jsonb_build_object(
            'entry_number', generated_entry_number,
            'source_type', 'v1_tax_additional_liability',
            'amendment_evidence_id', evidence.id,
            'confirmation_digest', confirmation_digest_value,
            'automatic_source_posting', false
        )
    );

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id, 'accounting.tax.additional_amendment.liability_posted',
        'v1_tax_additional_amendment', evidence.id,
        jsonb_build_object(
            'journal_entry_id', journal.id,
            'entry_number', generated_entry_number,
            'original_declared_tax_due', normalized_original_declared,
            'revised_declared_tax_due', normalized_revised_declared,
            'additional_tax_due', normalized_additional,
            'expense_account_code', expense_account.code,
            'tax_payable_account_code', payable_account.code,
            'confirmation_digest', confirmation_digest_value,
            'automatic_source_posting', false
        )
    );

    RETURN created_posting_id;
END;
$$;

CREATE OR REPLACE VIEW accounting.v1_tax_additional_amendment_liability_queue AS
SELECT
    evidence.id AS amendment_evidence_id,
    evidence.amendment_basis,
    evidence.tax_type,
    evidence.tax_return_id,
    evidence.tax_liability_posting_id,
    evidence.original_evidence_id,
    evidence.replacement_evidence_id,
    original_queue.source_id,
    original_queue.loan_id,
    original_queue.client_id,
    evidence.original_declared_tax_due,
    evidence.revised_declared_tax_due,
    evidence.original_item_tax_due,
    evidence.replacement_item_tax_due,
    evidence.additional_tax_due,
    evidence.payment_basis,
    evidence.payment_required_amount,
    evidence.amendment_date,
    evidence.recognition_date,
    evidence.amendment_reference,
    evidence.evidence_reference,
    evidence.evidence_digest,
    evidence.original_payment_evidence_id,
    evidence.original_settlement_posting_id,
    evidence.original_settlement_journal_entry_id,
    evidence.recorded_by_user_id,
    evidence.recorded_at,
    preparation.id AS liability_preparation_id,
    preparation.journal_entry_id AS liability_journal_entry_id,
    journal.status AS liability_journal_status,
    journal.entry_number AS liability_entry_number,
    preparation.fiscal_period_id AS liability_fiscal_period_id,
    expense_account.code AS expense_account_code,
    payable_account.code AS tax_payable_account_code,
    preparation.prepared_by_user_id AS liability_prepared_by_user_id,
    preparation.prepared_at AS liability_prepared_at,
    posting.id AS additional_liability_posting_id,
    posting.confirmation_digest AS liability_confirmation_digest,
    posting.posted_by_user_id AS liability_posted_by_user_id,
    posting.posted_at AS liability_posted_at,
    CASE
        WHEN posting.id IS NOT NULL
             AND (
                original_queue.accounting_status <> 'posted_adjustment_review_required'
                OR replacement_queue.evidence_status <> 'evidence_ready'
                OR replacement_queue.accounting_status <> 'evidence_ready'
                OR replacement_queue.source_id <> original_queue.source_id
                OR replacement_queue.tax_due <> evidence.replacement_item_tax_due
             )
            THEN 'additional_liability_posted_review_required'
        WHEN posting.id IS NOT NULL THEN 'additional_liability_posted_awaiting_payment'
        WHEN preparation.id IS NOT NULL AND journal.status IS DISTINCT FROM 'draft'
            THEN 'blocked_untracked_additional_liability_journal_state'
        WHEN original_queue.accounting_status <> 'posted_adjustment_review_required'
            THEN 'blocked_original_liability_not_stale'
        WHEN replacement_queue.evidence_id IS NULL
          OR replacement_queue.evidence_status <> 'evidence_ready'
          OR replacement_queue.accounting_status <> 'evidence_ready'
          OR replacement_queue.source_id <> original_queue.source_id
          OR replacement_queue.loan_id <> original_queue.loan_id
          OR replacement_queue.client_id <> original_queue.client_id
          OR replacement_queue.tax_due <> evidence.replacement_item_tax_due
            THEN 'blocked_replacement_evidence_changed'
        WHEN preparation.id IS NOT NULL THEN 'additional_liability_prepared'
        WHEN open_original_period.id IS NULL THEN 'blocked_original_period_not_open'
        ELSE 'amendment_evidence_ready'
    END AS amendment_status,
    CASE
        WHEN posting.id IS NOT NULL
             AND (
                original_queue.accounting_status <> 'posted_adjustment_review_required'
                OR replacement_queue.evidence_status <> 'evidence_ready'
                OR replacement_queue.accounting_status <> 'evidence_ready'
                OR replacement_queue.source_id <> original_queue.source_id
                OR replacement_queue.tax_due <> evidence.replacement_item_tax_due
             )
            THEN 'A later tax-evidence change occurred after the additional liability was posted; a new explicit review is required.'
        WHEN posting.id IS NOT NULL THEN NULL
        WHEN preparation.id IS NOT NULL AND journal.status IS DISTINCT FROM 'draft'
            THEN 'Prepared additional-tax liability journal is not a draft but has no immutable protected posting audit.'
        WHEN original_queue.accounting_status <> 'posted_adjustment_review_required'
            THEN 'Original liability is no longer in the exact stale-posting state retained by this amendment evidence.'
        WHEN replacement_queue.evidence_id IS NULL
          OR replacement_queue.evidence_status <> 'evidence_ready'
          OR replacement_queue.accounting_status <> 'evidence_ready'
          OR replacement_queue.source_id <> original_queue.source_id
          OR replacement_queue.loan_id <> original_queue.loan_id
          OR replacement_queue.client_id <> original_queue.client_id
          OR replacement_queue.tax_due <> evidence.replacement_item_tax_due
            THEN 'Exact replacement tax evidence no longer matches the retained upward amendment evidence.'
        WHEN preparation.id IS NOT NULL THEN 'Exact Management confirmation is required before posting the protected additional-tax liability.'
        WHEN open_original_period.id IS NULL THEN 'Original liability fiscal period is no longer open for this pre-close upward amendment path.'
        ELSE NULL
    END AS amendment_blocker,
    true AS tax_additional_amendment_enabled,
    false AS automatic_source_posting
FROM accounting.v1_tax_additional_amendment_evidence evidence
JOIN accounting.v1_tax_liability_postings original_posting
  ON original_posting.id = evidence.tax_liability_posting_id
LEFT JOIN accounting.v1_tax_liability_queue original_queue
  ON original_queue.posting_id = original_posting.id
 AND original_queue.tax_type = evidence.tax_type
 AND original_queue.evidence_id = evidence.original_evidence_id
LEFT JOIN accounting.v1_tax_liability_queue replacement_queue
  ON replacement_queue.tax_type = evidence.tax_type
 AND replacement_queue.evidence_id = evidence.replacement_evidence_id
LEFT JOIN accounting.v1_tax_additional_liability_preparations preparation
  ON preparation.amendment_evidence_id = evidence.id
LEFT JOIN accounting.journal_entries journal
  ON journal.id = preparation.journal_entry_id
LEFT JOIN accounting.accounts expense_account
  ON expense_account.id = preparation.expense_account_id
LEFT JOIN accounting.accounts payable_account
  ON payable_account.id = preparation.tax_payable_account_id
LEFT JOIN accounting.v1_tax_additional_liability_postings posting
  ON posting.preparation_id = preparation.id
LEFT JOIN LATERAL (
    SELECT period.id
    FROM accounting.fiscal_periods period
    WHERE period.id = original_posting.confirmed_fiscal_period_id
      AND period.status = 'open'
      AND evidence.recognition_date BETWEEN period.start_date AND period.end_date
    LIMIT 1
) open_original_period ON true;

CREATE OR REPLACE VIEW accounting.v1_tax_additional_amendment_liability_summary AS
SELECT
    count(*)::bigint AS amendment_evidence_count,
    count(*) FILTER (WHERE amendment_status = 'amendment_evidence_ready')::bigint AS ready_to_prepare_count,
    count(*) FILTER (WHERE amendment_status = 'additional_liability_prepared')::bigint AS prepared_count,
    count(*) FILTER (WHERE amendment_status = 'additional_liability_posted_awaiting_payment')::bigint AS posted_awaiting_payment_count,
    count(*) FILTER (WHERE amendment_status = 'additional_liability_posted_review_required')::bigint AS posted_review_count,
    count(*) FILTER (WHERE amendment_status LIKE 'blocked_%')::bigint AS blocked_count,
    coalesce(sum(additional_tax_due) FILTER (
        WHERE amendment_status IN (
            'additional_liability_posted_awaiting_payment',
            'additional_liability_posted_review_required'
        )
    ), 0)::numeric(18,2) AS posted_additional_tax_total,
    true AS tax_additional_amendment_enabled,
    false AS automatic_source_posting
FROM accounting.v1_tax_additional_amendment_liability_queue;

COMMENT ON TABLE accounting.v1_tax_additional_amendment_evidence IS
'Immutable Management-approved upward amendment/assessment evidence for one exact filed V1 return and one stale posted liability. It preserves original return/liability/settlement history and derives only the supported additional tax delta.';
COMMENT ON TABLE accounting.v1_tax_additional_liability_postings IS
'Immutable protected posting audit for the additional-tax liability delta: Dr original dedicated tax expense / Cr 2100 Tax Payables while the original liability period remains open.';
COMMENT ON VIEW accounting.v1_tax_additional_amendment_liability_queue IS
'Protected V1 upward tax-amendment liability queue. Payment/settlement is intentionally a separate retained-evidence step.';

COMMIT;
