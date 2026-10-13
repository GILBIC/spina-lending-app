BEGIN;

-- One immutable accounting identity per isolated database. No actual identity,
-- opening balance, company approval, or Treasury-to-GL mapping is seeded here.
CREATE TABLE IF NOT EXISTS accounting.book_identity (
    singleton BOOLEAN PRIMARY KEY DEFAULT true CHECK (singleton),
    id UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    kind TEXT NOT NULL CHECK (kind IN ('owner_operations', 'corporate_legal', 'synthetic')),
    entity_label TEXT NOT NULL CHECK (entity_label !~ '(^[[:space:]]|[[:space:]]$)' AND length(entity_label) BETWEEN 1 AND 200),
    evidence_reference TEXT NOT NULL CHECK (evidence_reference !~ '(^[[:space:]]|[[:space:]]$)' AND length(evidence_reference) BETWEEN 1 AND 1000),
    evidence_digest TEXT NOT NULL CHECK (evidence_digest ~ '^[0-9a-f]{64}$'),
    configured_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    configured_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE accounting.book_identity ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE accounting.book_identity FROM PUBLIC;

CREATE OR REPLACE FUNCTION accounting.guard_book_identity_write()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog, accounting, core
AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'Accounting book identity and its setup evidence are immutable.';
    END IF;
    IF coalesce(current_setting('accounting.book_identity_setup_allowed', true), '') <> 'on' THEN
        RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'Accounting book identity requires protected setup.';
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS accounting_book_identity_write_guard ON accounting.book_identity;
CREATE TRIGGER accounting_book_identity_write_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.book_identity
FOR EACH ROW EXECUTE FUNCTION accounting.guard_book_identity_write();
DROP TRIGGER IF EXISTS accounting_book_identity_truncate_guard ON accounting.book_identity;
CREATE TRIGGER accounting_book_identity_truncate_guard
BEFORE TRUNCATE ON accounting.book_identity
FOR EACH STATEMENT EXECUTE FUNCTION accounting.guard_book_identity_write();

CREATE OR REPLACE FUNCTION accounting.configure_book_identity(
    p_kind TEXT, p_entity_label TEXT, p_evidence_reference TEXT,
    p_evidence_digest TEXT, p_actor_user_id UUID
)
RETURNS UUID LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog, accounting, core, lending, treasury
AS $$
DECLARE
    existing accounting.book_identity%ROWTYPE;
    actor_id UUID;
    created_id UUID;
    previous_setup_setting TEXT;
BEGIN
    -- Do not trust a stale token or client-supplied actor. The backend supplies
    -- its authenticated actor, whose database authority is rechecked and locked.
    SELECT actor.id INTO actor_id
    FROM core.users actor
    JOIN core.user_roles membership ON membership.user_id = actor.id
    JOIN core.roles role ON role.id = membership.role_id
    JOIN core.role_permissions permission ON permission.role_id = role.id
    WHERE actor.id = p_actor_user_id AND actor.status = 'active'
      AND role.code = 'management'
      AND permission.permission_code = 'accounting.journal.manage'
    FOR SHARE OF actor, membership, role, permission;
    IF actor_id IS NULL THEN
        RAISE EXCEPTION USING ERRCODE = '42501', MESSAGE = 'An active Management actor with accounting.journal.manage permission is required.';
    END IF;
    IF p_kind IS NULL OR p_kind NOT IN ('owner_operations', 'corporate_legal', 'synthetic')
       OR p_entity_label IS NULL OR p_entity_label ~ '(^[[:space:]]|[[:space:]]$)'
       OR length(p_entity_label) NOT BETWEEN 1 AND 200
       OR p_evidence_reference IS NULL OR p_evidence_reference ~ '(^[[:space:]]|[[:space:]]$)'
       OR length(p_evidence_reference) NOT BETWEEN 1 AND 1000
       OR p_evidence_digest IS NULL OR p_evidence_digest !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'Book kind, exact entity label and retained evidence reference with lowercase SHA-256 digest are required.';
    END IF;

    -- The empty-source proof must see commits preceding the table locks. A
    -- previously established repeatable-read snapshot cannot provide that.
    IF current_setting('transaction_isolation') <> 'read committed' THEN
        RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'Accounting book setup requires a READ COMMITTED transaction.';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('accounting:book-identity', 0));
    SELECT * INTO existing FROM accounting.book_identity WHERE singleton;
    IF existing.id IS NOT NULL THEN
        IF existing.kind = p_kind AND existing.entity_label = p_entity_label
           AND existing.evidence_reference = p_evidence_reference
           AND existing.evidence_digest = p_evidence_digest
           AND existing.configured_by_user_id = p_actor_user_id THEN
            RETURN existing.id;
        END IF;
        RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'Accounting book identity is already configured; changed identity, evidence or actor cannot replace it.';
    END IF;

    IF p_kind <> 'owner_operations' THEN
        -- Block concurrent insertion while proving this is a fresh company/test
        -- database. Chart-of-accounts seeds, users and periods are permitted.
        LOCK TABLE lending.loans, accounting.journal_entries, treasury.accounts,
            accounting.opening_balance_workbooks, accounting.initial_capital_funding_evidence,
            accounting.v1_tax_rule_evidence, accounting.ecl_history_import_batches,
            accounting.cancelled_journal_draft_audit, accounting.fiscal_periods,
            accounting.period_close_preparations IN SHARE MODE;
        IF EXISTS (SELECT 1 FROM lending.loans)
           OR EXISTS (SELECT 1 FROM accounting.journal_entries)
           OR EXISTS (SELECT 1 FROM treasury.accounts)
           OR EXISTS (SELECT 1 FROM accounting.opening_balance_workbooks)
           OR EXISTS (SELECT 1 FROM accounting.initial_capital_funding_evidence)
           OR EXISTS (SELECT 1 FROM accounting.v1_tax_rule_evidence)
           OR EXISTS (SELECT 1 FROM accounting.ecl_history_import_batches)
           OR EXISTS (SELECT 1 FROM accounting.cancelled_journal_draft_audit)
           OR EXISTS (SELECT 1 FROM accounting.period_close_preparations)
           OR EXISTS (SELECT 1 FROM accounting.fiscal_periods WHERE status <> 'open') THEN
            RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'Corporate and synthetic book setup requires an empty business database; existing owner history cannot be relabelled.';
        END IF;
    END IF;

    previous_setup_setting := current_setting('accounting.book_identity_setup_allowed', true);
    PERFORM set_config('accounting.book_identity_setup_allowed', 'on', true);
    INSERT INTO accounting.book_identity(kind, entity_label, evidence_reference, evidence_digest, configured_by_user_id)
    VALUES(p_kind, p_entity_label, p_evidence_reference, p_evidence_digest, p_actor_user_id)
    RETURNING id INTO created_id;
    PERFORM set_config('accounting.book_identity_setup_allowed', coalesce(previous_setup_setting, ''), true);
    RETURN created_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.require_book_treasury_context(p_context_id UUID)
RETURNS UUID LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog, accounting, treasury
AS $$
DECLARE
    book accounting.book_identity%ROWTYPE;
    context_kind TEXT;
BEGIN
    SELECT * INTO book FROM accounting.book_identity WHERE singleton;
    IF book.id IS NULL THEN
        RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'Accounting book identity is unconfigured.';
    END IF;
    SELECT kind INTO context_kind FROM treasury.contexts WHERE id = p_context_id FOR SHARE;
    IF context_kind IS NULL THEN
        RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'Treasury context is unavailable.';
    END IF;
    IF context_kind <> book.kind THEN
        RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'Treasury context does not match the accounting book kind.';
    END IF;
    RETURN book.id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.require_book_treasury_account(p_account_id UUID)
RETURNS UUID LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog, accounting, treasury
AS $$
DECLARE
    wallet treasury.accounts%ROWTYPE;
    book_id UUID;
    book_kind TEXT;
BEGIN
    SELECT * INTO wallet FROM treasury.accounts WHERE id = p_account_id FOR SHARE;
    IF wallet.id IS NULL OR NOT wallet.active THEN
        RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'Treasury account is unavailable or inactive.';
    END IF;
    book_id := accounting.require_book_treasury_context(wallet.ledger_context_id);
    SELECT kind INTO book_kind FROM accounting.book_identity WHERE id = book_id;
    IF NOT ((book_kind = 'corporate_legal' AND wallet.ownership = 'corporate')
         OR (book_kind = 'owner_operations' AND wallet.ownership IN ('owner_personal', 'owner_business'))
         OR (book_kind = 'synthetic' AND wallet.ownership = 'synthetic')) THEN
        RAISE EXCEPTION USING ERRCODE = '55000', MESSAGE = 'Treasury account ownership is incompatible with the accounting book.';
    END IF;
    RETURN book_id;
END;
$$;

REVOKE ALL ON FUNCTION accounting.guard_book_identity_write(),
    accounting.configure_book_identity(TEXT, TEXT, TEXT, TEXT, UUID),
    accounting.require_book_treasury_context(UUID),
    accounting.require_book_treasury_account(UUID) FROM PUBLIC;

-- Preserve the repository's backend-only private-schema model. No client policy
-- or role is created. A non-owner backend role needs explicit deployment grants.
DO $private_book_identity$
DECLARE client_role TEXT;
BEGIN
    FOR client_role IN SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated', 'service_role') LOOP
        EXECUTE format('REVOKE ALL ON TABLE accounting.book_identity FROM %I', client_role);
        EXECUTE format('REVOKE ALL ON FUNCTION accounting.guard_book_identity_write(), accounting.configure_book_identity(TEXT,TEXT,TEXT,TEXT,UUID), accounting.require_book_treasury_context(UUID), accounting.require_book_treasury_account(UUID) FROM %I', client_role);
    END LOOP;
END;
$private_book_identity$;

COMMENT ON TABLE accounting.book_identity IS
'Immutable identity of this isolated General Ledger database. Evidence is an attestation reference and SHA-256 digest, not automatic validation of legal status or opening balances.';

COMMIT;
