BEGIN;

-- Master #296 A6.1: prove a protected Management path can record actual initial
-- capital/funding from retained source evidence into the chosen real cash/bank
-- account. This reuses accounting.journal_entries / journal_lines and the existing
-- protected posting function. It never creates or depends on an opening-balance
-- workbook and automatic source posting remains disabled.

INSERT INTO core.permissions (code, description)
VALUES
    ('accounting.initial_capital.evidence.record', 'Record immutable initial-capital funding evidence for later protected accounting'),
    ('accounting.initial_capital.prepare', 'Prepare the protected initial-capital General Journal draft from exact retained funding evidence'),
    ('accounting.initial_capital.post', 'Post the protected initial-capital General Journal entry after exact Management confirmation')
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code IN (
      'accounting.initial_capital.evidence.record',
      'accounting.initial_capital.prepare',
      'accounting.initial_capital.post'
  )
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.initial_capital_funding_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key UUID NOT NULL UNIQUE,
    funding_date DATE NOT NULL,
    amount NUMERIC(18,2) NOT NULL CHECK (amount > 0),
    cash_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    capital_account_id UUID NOT NULL REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    evidence_source TEXT NOT NULL CHECK (btrim(evidence_source) <> ''),
    evidence_reference TEXT NOT NULL CHECK (btrim(evidence_reference) <> ''),
    evidence_digest TEXT NOT NULL CHECK (evidence_digest ~ '^[0-9a-f]{64}$'),
    evidence_note TEXT NOT NULL CHECK (btrim(evidence_note) <> ''),
    recorded_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (evidence_source, evidence_reference)
);

CREATE INDEX IF NOT EXISTS initial_capital_funding_evidence_date_idx
    ON accounting.initial_capital_funding_evidence(funding_date, recorded_at DESC);

CREATE TABLE IF NOT EXISTS accounting.initial_capital_funding_preparations (
    evidence_id UUID PRIMARY KEY
        REFERENCES accounting.initial_capital_funding_evidence(id) ON DELETE RESTRICT,
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    source_event_key TEXT NOT NULL UNIQUE CHECK (btrim(source_event_key) <> ''),
    fiscal_period_id UUID NOT NULL
        REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    prepared_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    prepared_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS accounting.initial_capital_funding_postings (
    evidence_id UUID PRIMARY KEY
        REFERENCES accounting.initial_capital_funding_evidence(id) ON DELETE RESTRICT,
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    entry_number TEXT NOT NULL CHECK (btrim(entry_number) <> ''),
    confirmation_token TEXT NOT NULL CHECK (confirmation_token ~ '^[0-9a-f]{64}$'),
    confirmation_digest TEXT NOT NULL CHECK (confirmation_digest ~ '^[0-9a-f]{64}$'),
    confirmed_amount NUMERIC(18,2) NOT NULL CHECK (confirmed_amount > 0),
    confirmed_cash_account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    confirmed_posting_date DATE NOT NULL,
    confirmed_fiscal_period_id UUID NOT NULL
        REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    policy_version TEXT NOT NULL CHECK (policy_version = 'initial_capital_funding_v1'),
    posted_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    posted_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE OR REPLACE FUNCTION accounting.guard_initial_capital_evidence_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(current_setting('accounting.initial_capital_evidence_insert_allowed', true), '') = 'on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Initial-capital funding evidence is immutable and must use the protected Management evidence function.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_initial_capital_evidence_guard
    ON accounting.initial_capital_funding_evidence;
CREATE TRIGGER accounting_initial_capital_evidence_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.initial_capital_funding_evidence
FOR EACH ROW EXECUTE FUNCTION accounting.guard_initial_capital_evidence_write();

CREATE OR REPLACE FUNCTION accounting.guard_initial_capital_preparation_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(current_setting('accounting.initial_capital_preparation_insert_allowed', true), '') = 'on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Initial-capital journal preparation audit is immutable and must use the protected preparation function.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_initial_capital_preparation_guard
    ON accounting.initial_capital_funding_preparations;
CREATE TRIGGER accounting_initial_capital_preparation_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.initial_capital_funding_preparations
FOR EACH ROW EXECUTE FUNCTION accounting.guard_initial_capital_preparation_write();

CREATE OR REPLACE FUNCTION accounting.guard_initial_capital_posting_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(current_setting('accounting.initial_capital_posting_insert_allowed', true), '') = 'on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Initial-capital posting audit is immutable and must use the protected posting function.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_initial_capital_posting_guard
    ON accounting.initial_capital_funding_postings;
CREATE TRIGGER accounting_initial_capital_posting_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.initial_capital_funding_postings
FOR EACH ROW EXECUTE FUNCTION accounting.guard_initial_capital_posting_write();

CREATE OR REPLACE FUNCTION accounting.require_initial_capital_management_actor(
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

CREATE OR REPLACE FUNCTION accounting.guard_initial_capital_journal_entry_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    reversed_source TEXT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.source_type = 'initial_capital_funding'
           AND coalesce(current_setting('accounting.initial_capital_journal_prepare_allowed', true), '') <> 'on' THEN
            RAISE EXCEPTION 'Initial-capital journals must use the protected Management preparation function.';
        END IF;

        IF NEW.reversal_of_entry_id IS NOT NULL THEN
            SELECT source_type INTO reversed_source
            FROM accounting.journal_entries
            WHERE id = NEW.reversal_of_entry_id;
            IF reversed_source = 'initial_capital_funding' THEN
                RAISE EXCEPTION 'Initial-capital funding cannot be reversed through the manual General Journal; a separately supported protected evidence event is required.';
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.source_type IS DISTINCT FROM 'initial_capital_funding' THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Initial-capital journals are immutable and cannot be deleted.';
    END IF;

    IF OLD.status = 'draft' AND NEW.status = 'posted' THEN
        IF coalesce(current_setting('accounting.initial_capital_journal_post_allowed', true), '') <> 'on' THEN
            RAISE EXCEPTION 'Initial-capital journals require the protected Management posting function.';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'Initial-capital journals are system generated and immutable.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_initial_capital_journal_entry_guard
    ON accounting.journal_entries;
CREATE TRIGGER accounting_initial_capital_journal_entry_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_initial_capital_journal_entry_change();

CREATE OR REPLACE FUNCTION accounting.guard_initial_capital_journal_line_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_entry UUID;
    target_source TEXT;
BEGIN
    target_entry := CASE WHEN TG_OP = 'DELETE' THEN OLD.journal_entry_id ELSE NEW.journal_entry_id END;
    SELECT source_type INTO target_source
    FROM accounting.journal_entries
    WHERE id = target_entry;

    IF target_source = 'initial_capital_funding'
       AND coalesce(current_setting('accounting.initial_capital_journal_line_write_allowed', true), '') <> 'on' THEN
        RAISE EXCEPTION 'Initial-capital journal lines are system generated and immutable.';
    END IF;

    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_initial_capital_journal_line_guard
    ON accounting.journal_lines;
CREATE TRIGGER accounting_initial_capital_journal_line_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_lines
FOR EACH ROW EXECUTE FUNCTION accounting.guard_initial_capital_journal_line_change();

CREATE OR REPLACE FUNCTION accounting.record_initial_capital_funding_evidence(
    p_actor_user_id UUID,
    p_idempotency_key UUID,
    p_funding_date DATE,
    p_amount NUMERIC,
    p_cash_account_code TEXT,
    p_evidence_source TEXT,
    p_evidence_reference TEXT,
    p_evidence_digest TEXT,
    p_evidence_note TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    existing accounting.initial_capital_funding_evidence%ROWTYPE;
    cash_account accounting.accounts%ROWTYPE;
    capital_account accounting.accounts%ROWTYPE;
    normalized_amount NUMERIC(18,2) := round(coalesce(p_amount, -1), 2);
    normalized_cash_code TEXT := btrim(coalesce(p_cash_account_code, ''));
    normalized_source TEXT := btrim(coalesce(p_evidence_source, ''));
    normalized_reference TEXT := btrim(coalesce(p_evidence_reference, ''));
    normalized_digest TEXT := lower(btrim(coalesce(p_evidence_digest, '')));
    normalized_note TEXT := btrim(coalesce(p_evidence_note, ''));
    result_id UUID;
BEGIN
    PERFORM accounting.require_initial_capital_management_actor(
        p_actor_user_id,
        'accounting.initial_capital.evidence.record'
    );

    IF p_idempotency_key IS NULL THEN
        RAISE EXCEPTION 'Initial-capital evidence requires an exact idempotency key.';
    END IF;
    IF p_funding_date IS NULL THEN
        RAISE EXCEPTION 'Initial-capital funding date is required.';
    END IF;
    IF p_amount IS DISTINCT FROM normalized_amount OR normalized_amount <= 0 THEN
        RAISE EXCEPTION 'Initial-capital funding requires an exact positive currency-cent amount.';
    END IF;
    IF normalized_source = '' OR normalized_reference = '' OR normalized_note = '' THEN
        RAISE EXCEPTION 'Initial-capital funding requires retained evidence source, reference and note.';
    END IF;
    IF normalized_digest !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Initial-capital funding requires the exact retained evidence SHA-256 digest.';
    END IF;

    SELECT * INTO cash_account
    FROM accounting.accounts account
    WHERE account.code = normalized_cash_code
    FOR SHARE;
    IF cash_account.id IS NULL
       OR cash_account.system_key NOT IN ('cash_office', 'cash_bank_gcash')
       OR cash_account.account_type <> 'asset'
       OR cash_account.normal_balance <> 'debit'
       OR NOT cash_account.is_active OR NOT cash_account.is_posting THEN
        RAISE EXCEPTION 'Initial capital may only debit the exact active posting Cash - Office or Cash - Bank / GCash account selected from evidence.';
    END IF;

    SELECT * INTO capital_account
    FROM accounting.accounts account
    WHERE account.system_key = 'capital'
    FOR SHARE;
    IF capital_account.id IS NULL
       OR capital_account.code <> '3000'
       OR capital_account.account_type <> 'equity'
       OR capital_account.normal_balance <> 'credit'
       OR NOT capital_account.is_active OR NOT capital_account.is_posting THEN
        RAISE EXCEPTION 'Initial capital requires the exact active posting Capital account 3000.';
    END IF;

    SELECT * INTO existing
    FROM accounting.initial_capital_funding_evidence item
    WHERE item.idempotency_key = p_idempotency_key;
    IF existing.id IS NOT NULL THEN
        IF existing.funding_date <> p_funding_date
           OR existing.amount <> normalized_amount
           OR existing.cash_account_id <> cash_account.id
           OR existing.capital_account_id <> capital_account.id
           OR existing.evidence_source <> normalized_source
           OR existing.evidence_reference <> normalized_reference
           OR existing.evidence_digest <> normalized_digest
           OR existing.evidence_note <> normalized_note
           OR existing.recorded_by_user_id <> p_actor_user_id THEN
            RAISE EXCEPTION 'Existing initial-capital evidence does not match the immutable retry identity.';
        END IF;
        RETURN existing.id;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM accounting.initial_capital_funding_evidence item
        WHERE item.evidence_source = normalized_source
          AND item.evidence_reference = normalized_reference
    ) THEN
        RAISE EXCEPTION 'This initial-capital evidence source/reference is already registered under another retry identity.';
    END IF;

    PERFORM set_config('accounting.initial_capital_evidence_insert_allowed', 'on', true);
    INSERT INTO accounting.initial_capital_funding_evidence (
        idempotency_key, funding_date, amount, cash_account_id, capital_account_id,
        evidence_source, evidence_reference, evidence_digest, evidence_note,
        recorded_by_user_id
    ) VALUES (
        p_idempotency_key, p_funding_date, normalized_amount, cash_account.id,
        capital_account.id, normalized_source, normalized_reference,
        normalized_digest, normalized_note, p_actor_user_id
    ) RETURNING id INTO result_id;
    PERFORM set_config('accounting.initial_capital_evidence_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.initial_capital.evidence.recorded',
        'initial_capital_funding_evidence',
        result_id,
        jsonb_build_object(
            'funding_date', p_funding_date,
            'amount', normalized_amount,
            'cash_account_code', cash_account.code,
            'capital_account_code', capital_account.code,
            'evidence_source', normalized_source,
            'evidence_reference', normalized_reference,
            'evidence_digest', normalized_digest,
            'automatic_source_posting', false
        )
    );
    RETURN result_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.prepare_initial_capital_funding_journal(
    p_evidence_id UUID,
    p_actor_user_id UUID
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    evidence accounting.initial_capital_funding_evidence%ROWTYPE;
    existing accounting.initial_capital_funding_preparations%ROWTYPE;
    period_row accounting.fiscal_periods%ROWTYPE;
    cash_account accounting.accounts%ROWTYPE;
    capital_account accounting.accounts%ROWTYPE;
    journal_id UUID;
    event_key TEXT;
BEGIN
    PERFORM accounting.require_initial_capital_management_actor(
        p_actor_user_id,
        'accounting.initial_capital.prepare'
    );
    IF p_evidence_id IS NULL THEN
        RAISE EXCEPTION 'Initial-capital preparation requires retained funding evidence.';
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended('initial-capital:' || p_evidence_id::text, 0));

    SELECT * INTO existing
    FROM accounting.initial_capital_funding_preparations item
    WHERE item.evidence_id = p_evidence_id;
    IF existing.evidence_id IS NOT NULL THEN
        RETURN existing.journal_entry_id;
    END IF;

    SELECT * INTO evidence
    FROM accounting.initial_capital_funding_evidence item
    WHERE item.id = p_evidence_id
    FOR SHARE;
    IF evidence.id IS NULL THEN
        RAISE EXCEPTION 'Initial-capital funding evidence was not found.';
    END IF;

    SELECT * INTO cash_account
    FROM accounting.accounts account
    WHERE account.id = evidence.cash_account_id
    FOR SHARE;
    SELECT * INTO capital_account
    FROM accounting.accounts account
    WHERE account.id = evidence.capital_account_id
    FOR SHARE;

    IF cash_account.id IS NULL
       OR cash_account.system_key NOT IN ('cash_office', 'cash_bank_gcash')
       OR cash_account.account_type <> 'asset' OR cash_account.normal_balance <> 'debit'
       OR NOT cash_account.is_active OR NOT cash_account.is_posting THEN
        RAISE EXCEPTION 'Retained initial-capital evidence no longer resolves to an eligible active cash/bank account.';
    END IF;
    IF capital_account.id IS NULL OR capital_account.system_key <> 'capital'
       OR capital_account.code <> '3000' OR capital_account.account_type <> 'equity'
       OR capital_account.normal_balance <> 'credit'
       OR NOT capital_account.is_active OR NOT capital_account.is_posting THEN
        RAISE EXCEPTION 'Retained initial-capital evidence no longer resolves to active Capital account 3000.';
    END IF;

    SELECT * INTO period_row
    FROM accounting.fiscal_periods period
    WHERE period.status = 'open'
      AND evidence.funding_date BETWEEN period.start_date AND period.end_date
    ORDER BY period.start_date DESC
    LIMIT 1
    FOR SHARE;
    IF period_row.id IS NULL THEN
        RAISE EXCEPTION 'Initial-capital funding date must be inside an open accounting period before journal preparation.';
    END IF;

    event_key := 'initial_capital_funding:' || evidence.id::text;

    PERFORM set_config('accounting.initial_capital_journal_prepare_allowed', 'on', true);
    INSERT INTO accounting.journal_entries (
        fiscal_period_id, posting_date, description, status, source_type,
        source_reference, source_event_key, created_by_user_id, updated_at
    ) VALUES (
        period_row.id,
        evidence.funding_date,
        'Initial capital funding - ' || evidence.evidence_reference,
        'draft',
        'initial_capital_funding',
        evidence.id::text,
        event_key,
        p_actor_user_id,
        now()
    ) RETURNING id INTO journal_id;
    PERFORM set_config('accounting.initial_capital_journal_prepare_allowed', 'off', true);

    PERFORM set_config('accounting.initial_capital_journal_line_write_allowed', 'on', true);
    INSERT INTO accounting.journal_lines (
        journal_entry_id, line_number, account_id, description, debit, credit
    ) VALUES
        (journal_id, 1, cash_account.id,
            'Initial capital funding received - ' || evidence.evidence_reference,
            evidence.amount, 0),
        (journal_id, 2, capital_account.id,
            'Initial capital recognized from retained funding evidence',
            0, evidence.amount);
    PERFORM set_config('accounting.initial_capital_journal_line_write_allowed', 'off', true);

    INSERT INTO accounting.journal_events(journal_entry_id, event_type, actor_user_id, details)
    VALUES (
        journal_id,
        'draft_created',
        p_actor_user_id,
        jsonb_build_object(
            'source_type', 'initial_capital_funding',
            'evidence_id', evidence.id,
            'evidence_digest', evidence.evidence_digest,
            'funding_date', evidence.funding_date,
            'amount', evidence.amount,
            'cash_account_code', cash_account.code,
            'capital_account_code', capital_account.code,
            'posting_enabled', false,
            'automatic_source_posting', false
        )
    );

    PERFORM set_config('accounting.initial_capital_preparation_insert_allowed', 'on', true);
    INSERT INTO accounting.initial_capital_funding_preparations (
        evidence_id, journal_entry_id, source_event_key, fiscal_period_id,
        prepared_by_user_id
    ) VALUES (
        evidence.id, journal_id, event_key, period_row.id, p_actor_user_id
    );
    PERFORM set_config('accounting.initial_capital_preparation_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.initial_capital.journal.prepared',
        'initial_capital_funding_evidence',
        evidence.id,
        jsonb_build_object(
            'journal_entry_id', journal_id,
            'source_event_key', event_key,
            'amount', evidence.amount,
            'cash_account_code', cash_account.code,
            'capital_account_code', capital_account.code,
            'automatic_source_posting', false
        )
    );
    RETURN journal_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.post_initial_capital_funding_journal(
    p_evidence_id UUID,
    p_actor_user_id UUID,
    p_confirmation_token TEXT,
    p_expected_evidence_digest TEXT,
    p_expected_amount NUMERIC,
    p_expected_cash_account_code TEXT,
    p_expected_posting_date DATE,
    p_expected_fiscal_period_id UUID,
    p_policy_version TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    evidence accounting.initial_capital_funding_evidence%ROWTYPE;
    preparation accounting.initial_capital_funding_preparations%ROWTYPE;
    existing accounting.initial_capital_funding_postings%ROWTYPE;
    journal accounting.journal_entries%ROWTYPE;
    period_row accounting.fiscal_periods%ROWTYPE;
    cash_account accounting.accounts%ROWTYPE;
    capital_account accounting.accounts%ROWTYPE;
    normalized_token TEXT := lower(btrim(coalesce(p_confirmation_token, '')));
    normalized_digest TEXT := lower(btrim(coalesce(p_expected_evidence_digest, '')));
    normalized_cash_code TEXT := btrim(coalesce(p_expected_cash_account_code, ''));
    normalized_amount NUMERIC(18,2) := round(coalesce(p_expected_amount, -1), 2);
    line_count BIGINT;
    total_debit NUMERIC(18,2);
    total_credit NUMERIC(18,2);
    exact_cash_debit NUMERIC(18,2);
    exact_capital_credit NUMERIC(18,2);
    foreign_line_count BIGINT;
    entry_number_value TEXT;
    confirmation_digest_value TEXT;
    result_id UUID;
BEGIN
    PERFORM accounting.require_initial_capital_management_actor(
        p_actor_user_id,
        'accounting.initial_capital.post'
    );

    IF p_policy_version IS DISTINCT FROM 'initial_capital_funding_v1' THEN
        RAISE EXCEPTION 'Unsupported initial-capital funding policy version.';
    END IF;
    IF normalized_token !~ '^[0-9a-f]{64}$'
       OR normalized_digest !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Initial-capital posting requires the exact Management confirmation token and retained evidence digest.';
    END IF;
    IF p_expected_amount IS DISTINCT FROM normalized_amount OR normalized_amount <= 0 THEN
        RAISE EXCEPTION 'Initial-capital posting requires the exact positive currency-cent funding amount.';
    END IF;
    IF p_expected_posting_date IS NULL OR p_expected_fiscal_period_id IS NULL THEN
        RAISE EXCEPTION 'Initial-capital posting requires the exact posting date and fiscal period.';
    END IF;

    SELECT * INTO existing
    FROM accounting.initial_capital_funding_postings item
    WHERE item.evidence_id = p_evidence_id;
    IF existing.evidence_id IS NOT NULL THEN
        SELECT code INTO normalized_cash_code
        FROM accounting.accounts account
        WHERE account.id = existing.confirmed_cash_account_id
          AND account.code = btrim(coalesce(p_expected_cash_account_code, ''));
        IF existing.confirmation_token <> normalized_token
           OR existing.confirmed_amount <> normalized_amount
           OR existing.confirmed_posting_date <> p_expected_posting_date
           OR existing.confirmed_fiscal_period_id <> p_expected_fiscal_period_id
           OR existing.policy_version <> p_policy_version
           OR normalized_cash_code IS NULL THEN
            RAISE EXCEPTION 'Existing initial-capital posting does not match the immutable retry identity.';
        END IF;
        SELECT evidence_digest INTO normalized_digest
        FROM accounting.initial_capital_funding_evidence item
        WHERE item.id = existing.evidence_id
          AND item.evidence_digest = lower(btrim(coalesce(p_expected_evidence_digest, '')));
        IF normalized_digest IS NULL THEN
            RAISE EXCEPTION 'Existing initial-capital posting does not match the immutable retry identity.';
        END IF;
        RETURN existing.evidence_id;
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended('initial-capital:' || p_evidence_id::text, 0));

    SELECT * INTO evidence
    FROM accounting.initial_capital_funding_evidence item
    WHERE item.id = p_evidence_id
    FOR SHARE;
    IF evidence.id IS NULL THEN
        RAISE EXCEPTION 'Initial-capital funding evidence was not found.';
    END IF;

    IF evidence.evidence_digest <> normalized_digest
       OR evidence.amount <> normalized_amount
       OR evidence.funding_date <> p_expected_posting_date THEN
        RAISE EXCEPTION 'Initial-capital evidence changed from the exact confirmed posting coordinates.';
    END IF;

    SELECT * INTO cash_account
    FROM accounting.accounts account
    WHERE account.id = evidence.cash_account_id
    FOR SHARE;
    SELECT * INTO capital_account
    FROM accounting.accounts account
    WHERE account.id = evidence.capital_account_id
    FOR SHARE;
    IF cash_account.id IS NULL OR cash_account.code <> normalized_cash_code
       OR cash_account.system_key NOT IN ('cash_office', 'cash_bank_gcash')
       OR cash_account.account_type <> 'asset' OR cash_account.normal_balance <> 'debit'
       OR NOT cash_account.is_active OR NOT cash_account.is_posting THEN
        RAISE EXCEPTION 'Exact retained cash/bank account confirmation is required for initial-capital posting.';
    END IF;
    IF capital_account.id IS NULL OR capital_account.system_key <> 'capital'
       OR capital_account.code <> '3000' OR capital_account.account_type <> 'equity'
       OR capital_account.normal_balance <> 'credit'
       OR NOT capital_account.is_active OR NOT capital_account.is_posting THEN
        RAISE EXCEPTION 'Exact active Capital account 3000 is required for initial-capital posting.';
    END IF;

    SELECT * INTO preparation
    FROM accounting.initial_capital_funding_preparations item
    WHERE item.evidence_id = evidence.id;
    IF preparation.evidence_id IS NULL THEN
        RAISE EXCEPTION 'Initial-capital journal must be prepared from retained evidence before posting.';
    END IF;

    SELECT * INTO period_row
    FROM accounting.fiscal_periods period
    WHERE period.id = p_expected_fiscal_period_id
    FOR SHARE;
    IF period_row.id IS NULL OR period_row.status <> 'open'
       OR p_expected_posting_date NOT BETWEEN period_row.start_date AND period_row.end_date
       OR preparation.fiscal_period_id <> period_row.id THEN
        RAISE EXCEPTION 'Initial-capital posting requires the exact still-open fiscal period used at preparation.';
    END IF;

    SELECT * INTO journal
    FROM accounting.journal_entries item
    WHERE item.id = preparation.journal_entry_id
    FOR UPDATE;
    IF journal.id IS NULL OR journal.status <> 'draft'
       OR journal.source_type <> 'initial_capital_funding'
       OR journal.source_reference <> evidence.id::text
       OR journal.source_event_key <> preparation.source_event_key
       OR journal.posting_date <> p_expected_posting_date
       OR journal.fiscal_period_id <> period_row.id THEN
        RAISE EXCEPTION 'Prepared initial-capital General Journal draft no longer matches the protected evidence coordinates.';
    END IF;

    SELECT
        count(*),
        coalesce(sum(line.debit), 0),
        coalesce(sum(line.credit), 0),
        coalesce(sum(line.debit) FILTER (WHERE line.account_id = cash_account.id), 0),
        coalesce(sum(line.credit) FILTER (WHERE line.account_id = capital_account.id), 0),
        count(*) FILTER (
            WHERE line.account_id NOT IN (cash_account.id, capital_account.id)
               OR line.client_id IS NOT NULL OR line.loan_id IS NOT NULL
        )
    INTO line_count, total_debit, total_credit,
         exact_cash_debit, exact_capital_credit, foreign_line_count
    FROM accounting.journal_lines line
    WHERE line.journal_entry_id = journal.id;

    IF line_count <> 2 OR total_debit <> normalized_amount OR total_credit <> normalized_amount
       OR exact_cash_debit <> normalized_amount OR exact_capital_credit <> normalized_amount
       OR foreign_line_count <> 0 THEN
        RAISE EXCEPTION 'Prepared initial-capital General Journal lines do not exactly reconcile Dr selected cash/bank / Cr Capital to retained evidence.';
    END IF;

    confirmation_digest_value := encode(sha256(convert_to(concat_ws('|',
        p_policy_version,
        evidence.id::text,
        evidence.evidence_digest,
        evidence.funding_date::text,
        to_char(evidence.amount, 'FM999999999999990.00'),
        cash_account.id::text,
        capital_account.id::text,
        period_row.id::text,
        journal.id::text,
        normalized_token
    ), 'UTF8')), 'hex');

    PERFORM set_config('accounting.initial_capital_journal_post_allowed', 'on', true);
    entry_number_value := accounting.post_journal_entry(journal.id, p_actor_user_id);
    PERFORM set_config('accounting.initial_capital_journal_post_allowed', 'off', true);

    IF coalesce(current_setting('accounting.initial_capital_force_audit_failure', true), '') = 'on' THEN
        RAISE EXCEPTION 'Forced initial-capital audit failure.';
    END IF;

    PERFORM set_config('accounting.initial_capital_posting_insert_allowed', 'on', true);
    INSERT INTO accounting.initial_capital_funding_postings (
        evidence_id, journal_entry_id, entry_number, confirmation_token,
        confirmation_digest, confirmed_amount, confirmed_cash_account_id,
        confirmed_posting_date, confirmed_fiscal_period_id, policy_version,
        posted_by_user_id
    ) VALUES (
        evidence.id, journal.id, entry_number_value, normalized_token,
        confirmation_digest_value, normalized_amount, cash_account.id,
        p_expected_posting_date, period_row.id, p_policy_version,
        p_actor_user_id
    ) RETURNING evidence_id INTO result_id;
    PERFORM set_config('accounting.initial_capital_posting_insert_allowed', 'off', true);

    INSERT INTO accounting.journal_events(journal_entry_id, event_type, actor_user_id, details)
    VALUES (
        journal.id,
        'posted',
        p_actor_user_id,
        jsonb_build_object(
            'entry_number', entry_number_value,
            'source_type', 'initial_capital_funding',
            'evidence_id', evidence.id,
            'confirmation_digest', confirmation_digest_value,
            'automatic_source_posting', false
        )
    );

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.initial_capital.posted',
        'initial_capital_funding_evidence',
        evidence.id,
        jsonb_build_object(
            'journal_entry_id', journal.id,
            'entry_number', entry_number_value,
            'funding_date', evidence.funding_date,
            'amount', evidence.amount,
            'cash_account_code', cash_account.code,
            'capital_account_code', capital_account.code,
            'evidence_digest', evidence.evidence_digest,
            'confirmation_digest', confirmation_digest_value,
            'automatic_source_posting', false
        )
    );

    RETURN result_id;
END;
$$;

CREATE OR REPLACE VIEW accounting.initial_capital_funding_queue AS
SELECT
    evidence.id AS evidence_id,
    evidence.funding_date,
    evidence.amount,
    cash_account.code AS cash_account_code,
    cash_account.name AS cash_account_name,
    capital_account.code AS capital_account_code,
    evidence.evidence_source,
    evidence.evidence_reference,
    evidence.evidence_digest,
    evidence.evidence_note,
    evidence.recorded_by_user_id,
    evidence.recorded_at,
    preparation.journal_entry_id,
    journal.status AS journal_status,
    journal.entry_number,
    preparation.fiscal_period_id,
    preparation.prepared_by_user_id,
    preparation.prepared_at,
    posting.confirmation_digest,
    posting.posted_by_user_id,
    posting.posted_at,
    CASE
        WHEN posting.evidence_id IS NOT NULL THEN 'posted'
        WHEN preparation.evidence_id IS NOT NULL THEN 'prepared_not_posted'
        WHEN period_gate.open_period_id IS NULL THEN 'blocked_no_open_period'
        ELSE 'evidence_ready'
    END AS accounting_status,
    CASE
        WHEN posting.evidence_id IS NOT NULL THEN NULL
        WHEN preparation.evidence_id IS NOT NULL THEN 'Exact Management confirmation is required before posting.'
        WHEN period_gate.open_period_id IS NULL THEN 'Funding date is not inside an open accounting period.'
        ELSE NULL
    END AS accounting_blocker,
    true AS protected_initial_capital_funding_enabled,
    false AS synthetic_opening_balance_required,
    false AS automatic_source_posting
FROM accounting.initial_capital_funding_evidence evidence
JOIN accounting.accounts cash_account ON cash_account.id = evidence.cash_account_id
JOIN accounting.accounts capital_account ON capital_account.id = evidence.capital_account_id
LEFT JOIN accounting.initial_capital_funding_preparations preparation
  ON preparation.evidence_id = evidence.id
LEFT JOIN accounting.journal_entries journal
  ON journal.id = preparation.journal_entry_id
LEFT JOIN accounting.initial_capital_funding_postings posting
  ON posting.evidence_id = evidence.id
LEFT JOIN LATERAL (
    SELECT period.id AS open_period_id
    FROM accounting.fiscal_periods period
    WHERE period.status = 'open'
      AND evidence.funding_date BETWEEN period.start_date AND period.end_date
    ORDER BY period.start_date DESC
    LIMIT 1
) period_gate ON true;

COMMIT;