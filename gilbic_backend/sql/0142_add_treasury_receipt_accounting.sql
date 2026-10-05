BEGIN;

-- A deliberately bounded adapter: original, wholly unapplied verified receipts
-- only. Applications, fees, refunds and corrections require separate adapters.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM accounting.accounts WHERE (code='2200' OR system_key='unapplied_borrower_funds')
        AND NOT (code='2200' AND system_key='unapplied_borrower_funds' AND name='Unapplied Borrower Funds'
                 AND account_type='liability' AND normal_balance='credit' AND is_active AND is_posting)) THEN
        RAISE EXCEPTION 'Unapplied borrower control account definition conflicts with code 2200.';
    END IF;
    INSERT INTO accounting.accounts(code,system_key,name,account_type,normal_balance)
    VALUES('2200','unapplied_borrower_funds','Unapplied Borrower Funds','liability','credit')
    ON CONFLICT (system_key) DO NOTHING;
END $$;

CREATE TABLE IF NOT EXISTS accounting.treasury_cash_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL UNIQUE,
    book_id UUID NOT NULL REFERENCES accounting.book_identity(id),
    treasury_account_id UUID NOT NULL REFERENCES treasury.accounts(id),
    ledger_context_id UUID NOT NULL REFERENCES treasury.contexts(id),
    version BIGINT NOT NULL CHECK(version>0),
    cash_account_id UUID NOT NULL REFERENCES accounting.accounts(id),
    liability_account_id UUID NOT NULL REFERENCES accounting.accounts(id),
    wallet_snapshot JSONB NOT NULL,
    cash_snapshot JSONB NOT NULL,
    liability_snapshot JSONB NOT NULL,
    evidence_reference TEXT NOT NULL CHECK(length(evidence_reference)>=1 AND length(evidence_reference)<=1000 AND evidence_reference !~ '(^[[:space:]]|[[:space:]]$)'),
    evidence_digest TEXT NOT NULL CHECK(evidence_digest ~ '^[0-9a-f]{64}$'),
    actor_user_id UUID NOT NULL REFERENCES core.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(treasury_account_id,version)
);
CREATE TABLE IF NOT EXISTS accounting.treasury_receipt_preparations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL UNIQUE,
    receipt_id UUID NOT NULL REFERENCES treasury.receipts(id),
    event_id UUID NOT NULL REFERENCES treasury.events(id),
    treasury_account_id UUID NOT NULL REFERENCES treasury.accounts(id),
    mapping_id UUID NOT NULL REFERENCES accounting.treasury_cash_mappings(id),
    book_id UUID NOT NULL REFERENCES accounting.book_identity(id),
    source_digest TEXT NOT NULL CHECK(source_digest ~ '^[0-9a-f]{64}$'),
    confirmation_token TEXT NOT NULL CHECK(confirmation_token ~ '^[0-9a-f]{64}$'),
    snapshot JSONB NOT NULL,
    actor_user_id UUID NOT NULL REFERENCES core.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS accounting.treasury_receipt_postings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    preparation_id UUID NOT NULL UNIQUE REFERENCES accounting.treasury_receipt_preparations(id),
    receipt_id UUID NOT NULL UNIQUE REFERENCES treasury.receipts(id),
    event_id UUID NOT NULL UNIQUE REFERENCES treasury.events(id),
    treasury_account_id UUID NOT NULL REFERENCES treasury.accounts(id),
    book_id UUID NOT NULL REFERENCES accounting.book_identity(id),
    journal_entry_id UUID NOT NULL UNIQUE REFERENCES accounting.journal_entries(id),
    source_digest TEXT NOT NULL CHECK(source_digest ~ '^[0-9a-f]{64}$'),
    actor_user_id UUID NOT NULL REFERENCES core.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE OR REPLACE FUNCTION accounting.treasury_gl_wallet_snapshot(p_account_id UUID)
RETURNS JSONB LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog,treasury AS $$
 SELECT jsonb_build_object('id',id,'ledger_context_id',ledger_context_id,'kind',kind,'currency',currency,
        'ownership',ownership,'custodian_user_id',custodian_user_id,'active',active)
 FROM treasury.accounts WHERE id=p_account_id
$$;
CREATE OR REPLACE FUNCTION accounting.treasury_gl_account_snapshot(p_account_id UUID)
RETURNS JSONB LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog,accounting AS $$
 SELECT jsonb_build_object('id',id,'code',code,'system_key',system_key,'name',name,'account_type',account_type,
        'normal_balance',normal_balance,'is_posting',is_posting,'is_active',is_active)
 FROM accounting.accounts WHERE id=p_account_id
$$;

CREATE OR REPLACE FUNCTION accounting.require_treasury_gl_actor(p_actor UUID,p_account UUID,p_permission TEXT)
RETURNS void LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,core,treasury AS $$
BEGIN
    IF current_setting('transaction_isolation') <> 'read committed' THEN
        RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Treasury accounting requires READ COMMITTED.';
    END IF;
    PERFORM u.id FROM core.users u JOIN core.user_roles ur ON ur.user_id=u.id
      JOIN core.roles r ON r.id=ur.role_id JOIN core.role_permissions rp ON rp.role_id=r.id
      WHERE u.id=p_actor AND u.status='active' AND r.code='management'
        AND rp.permission_code='accounting.journal.manage' FOR SHARE OF u,ur,r,rp;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE='42501', MESSAGE='Current Management accounting permission is required.';
    END IF;
    PERFORM id FROM treasury.accounts WHERE id=p_account AND active FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE='42501', MESSAGE='Active private Treasury account permission is required.';
    END IF;
    PERFORM g.account_id FROM treasury.account_access g
      WHERE g.account_id=p_account AND g.user_id=p_actor AND g.enabled AND g.private_history
        AND p_permission=ANY(g.permissions) FOR SHARE OF g;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE='42501', MESSAGE='Current private Treasury account permission is required.';
    END IF;
    PERFORM ur.user_id FROM core.user_roles ur JOIN core.role_permissions rp ON rp.role_id=ur.role_id
      WHERE ur.user_id=p_actor AND rp.permission_code=p_permission FOR SHARE OF ur,rp;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE='42501', MESSAGE='Current Treasury permission is required.';
    END IF;
END $$;

CREATE OR REPLACE FUNCTION accounting.guard_treasury_gl_evidence()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Treasury accounting evidence is immutable.';
    END IF;
    IF coalesce(current_setting('accounting.treasury_gl_write',true),'') <> TG_TABLE_NAME THEN
        RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Treasury accounting evidence requires its protected adapter.';
    END IF;
    RETURN NEW;
END $$;
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['treasury_cash_mappings','treasury_receipt_preparations','treasury_receipt_postings'] LOOP
        EXECUTE format('ALTER TABLE accounting.%I ENABLE ROW LEVEL SECURITY',t);
        EXECUTE format('REVOKE ALL ON accounting.%I FROM PUBLIC',t);
        EXECUTE format('DROP TRIGGER IF EXISTS treasury_gl_evidence_guard ON accounting.%I',t);
        EXECUTE format('CREATE TRIGGER treasury_gl_evidence_guard BEFORE INSERT OR UPDATE OR DELETE ON accounting.%I FOR EACH ROW EXECUTE FUNCTION accounting.guard_treasury_gl_evidence()',t);
        EXECUTE format('DROP TRIGGER IF EXISTS treasury_gl_truncate_guard ON accounting.%I',t);
        EXECUTE format('CREATE TRIGGER treasury_gl_truncate_guard BEFORE TRUNCATE ON accounting.%I FOR EACH STATEMENT EXECUTE FUNCTION accounting.guard_treasury_gl_evidence()',t);
    END LOOP;
END $$;

CREATE OR REPLACE FUNCTION accounting.configure_treasury_cash_mapping(
    p_account_id UUID,p_cash_code TEXT,p_expected_version BIGINT,p_request_id UUID,
    p_evidence_reference TEXT,p_evidence_digest TEXT,p_actor_user_id UUID)
RETURNS UUID LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting,treasury AS $$
DECLARE w treasury.accounts%ROWTYPE; c accounting.accounts%ROWTYPE; l accounting.accounts%ROWTYPE;
    prior accounting.treasury_cash_mappings%ROWTYPE; b UUID; v BIGINT; result UUID; previous TEXT;
BEGIN
    PERFORM accounting.require_treasury_gl_actor(p_actor_user_id,p_account_id,'treasury.account.manage');
    b := accounting.require_book_treasury_account(p_account_id);
    SELECT * INTO w FROM treasury.accounts WHERE id=p_account_id;
    SELECT * INTO prior FROM accounting.treasury_cash_mappings WHERE request_id=p_request_id;
    IF FOUND THEN
        IF prior.treasury_account_id=p_account_id AND prior.version=p_expected_version+1
          AND prior.cash_snapshot->>'code'=p_cash_code AND prior.evidence_reference=p_evidence_reference
          AND prior.evidence_digest=p_evidence_digest AND prior.actor_user_id=p_actor_user_id THEN RETURN prior.id; END IF;
        RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Mapping request retry does not match retained evidence.';
    END IF;
    IF p_request_id IS NULL OR p_expected_version IS NULL OR p_expected_version<0
      OR p_evidence_reference IS NULL OR length(p_evidence_reference) NOT BETWEEN 1 AND 1000
      OR p_evidence_reference ~ '(^[[:space:]]|[[:space:]]$)'
      OR p_evidence_digest IS NULL OR p_evidence_digest !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='Exact mapping request and retained evidence are required.';
    END IF;
    SELECT coalesce(max(version),0) INTO v FROM accounting.treasury_cash_mappings WHERE treasury_account_id=p_account_id;
    IF v<>p_expected_version THEN RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Mapping version is stale.'; END IF;
    SELECT * INTO c FROM accounting.accounts WHERE code=p_cash_code FOR SHARE;
    SELECT * INTO l FROM accounting.accounts WHERE system_key='unapplied_borrower_funds' FOR SHARE;
    IF w.currency<>'PHP' OR w.kind NOT IN ('physical_cash','gcash','bank')
      OR c.id IS NULL OR NOT c.is_active OR NOT c.is_posting OR c.account_type<>'asset' OR c.normal_balance<>'debit'
      OR (w.kind='physical_cash' AND (c.code<>'1010' OR c.system_key<>'cash_office'))
      OR (w.kind IN ('gcash','bank') AND (c.code<>'1030' OR c.system_key<>'cash_bank_gcash'))
      OR l.id IS NULL OR l.code<>'2200' OR l.account_type<>'liability' OR l.normal_balance<>'credit' OR NOT l.is_active OR NOT l.is_posting THEN
        RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Reviewed receipt cash and liability account mapping is unsupported.';
    END IF;
    previous := current_setting('accounting.treasury_gl_write',true);
    PERFORM set_config('accounting.treasury_gl_write','treasury_cash_mappings',true);
    INSERT INTO accounting.treasury_cash_mappings(request_id,book_id,treasury_account_id,ledger_context_id,version,
      cash_account_id,liability_account_id,wallet_snapshot,cash_snapshot,liability_snapshot,evidence_reference,evidence_digest,actor_user_id)
    VALUES(p_request_id,b,w.id,w.ledger_context_id,v+1,c.id,l.id,accounting.treasury_gl_wallet_snapshot(w.id),
      accounting.treasury_gl_account_snapshot(c.id),accounting.treasury_gl_account_snapshot(l.id),p_evidence_reference,p_evidence_digest,p_actor_user_id)
    RETURNING id INTO result;
    PERFORM set_config('accounting.treasury_gl_write',coalesce(previous,''),true);
    RETURN result;
END $$;

CREATE OR REPLACE FUNCTION accounting.treasury_receipt_coordinates(p_receipt_id UUID,p_mapping_id UUID)
RETURNS JSONB LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting,treasury
SET timezone='UTC' AS $$
DECLARE r treasury.receipts%ROWTYPE; e treasury.events%ROWTYPE; m accounting.treasury_cash_mappings%ROWTYPE;
    proof treasury.evidence%ROWTYPE; line treasury.movement_lines%ROWTYPE; period accounting.fiscal_periods%ROWTYPE;
    b UUID; result JSONB; day DATE; wallet UUID;
BEGIN
    SELECT account_id INTO wallet FROM treasury.receipts WHERE id=p_receipt_id;
    IF wallet IS NULL THEN RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Verified receipt source is unavailable.'; END IF;
    PERFORM id FROM treasury.accounts WHERE id=wallet FOR UPDATE;
    b := accounting.require_book_treasury_account(wallet);
    SELECT * INTO r FROM treasury.receipts WHERE id=p_receipt_id FOR UPDATE;
    SELECT * INTO e FROM treasury.events WHERE id=r.event_id FOR UPDATE;
    SELECT * INTO m FROM accounting.treasury_cash_mappings WHERE id=p_mapping_id;
    IF m.id IS NULL OR m.treasury_account_id<>wallet OR m.book_id<>b
      OR m.version<>(SELECT max(version) FROM accounting.treasury_cash_mappings WHERE treasury_account_id=wallet)
      OR m.wallet_snapshot IS DISTINCT FROM accounting.treasury_gl_wallet_snapshot(wallet) THEN
        RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Receipt mapping is missing or stale.';
    END IF;
    PERFORM id FROM accounting.accounts WHERE id IN (m.cash_account_id,m.liability_account_id) ORDER BY id FOR SHARE;
    IF m.cash_snapshot IS DISTINCT FROM accounting.treasury_gl_account_snapshot(m.cash_account_id)
      OR m.liability_snapshot IS DISTINCT FROM accounting.treasury_gl_account_snapshot(m.liability_account_id) THEN
        RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Receipt chart mapping is stale.';
    END IF;
    IF e.id IS NULL OR e.account_id<>wallet OR e.ledger_context_id<>r.ledger_context_id OR r.ledger_context_id<>m.ledger_context_id
      OR e.direction<>'credit' OR e.fee<>0 OR e.classification<>'borrower_receipt' OR e.version<>1
      OR e.provider<>m.wallet_snapshot->>'kind' OR e.amount<>r.amount OR e.effective_at<>r.effective_at
      OR r.applied_amount<>0 OR r.refunded_amount<>0 OR r.version<>1
      OR e.effective_at>clock_timestamp() OR e.verified_by_user_id IS NULL
      OR e.recipient_attestation IS NULL OR btrim(e.recipient_attestation)=''
      OR EXISTS(SELECT 1 FROM treasury.event_revisions WHERE event_id=e.id)
      OR EXISTS(SELECT 1 FROM treasury.applications WHERE receipt_id=r.id)
      OR EXISTS(SELECT 1 FROM treasury.source_links WHERE event_id=e.id)
      OR EXISTS(SELECT 1 FROM treasury.transfers WHERE source_event_id=e.id OR destination_event_id=e.id) THEN
        RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Receipt source must be original, verified, unapplied and uncorrected.';
    END IF;
    SELECT * INTO proof FROM treasury.evidence WHERE id=e.evidence_id AND account_id=wallet AND purpose='recipient';
    SELECT * INTO line FROM treasury.movement_lines WHERE event_id=e.id AND component='principal';
    IF proof.id IS NULL OR proof.byte_count<=0 OR proof.sha256 !~ '^[0-9a-f]{64}$'
      OR line.id IS NULL OR line.account_id<>wallet OR line.ledger_context_id<>r.ledger_context_id
      OR line.signed_amount<>r.amount OR line.effective_at<>r.effective_at OR line.evidence_id IS DISTINCT FROM proof.id
      OR (SELECT count(*) FROM treasury.movement_lines WHERE event_id=e.id)<>1 THEN
        RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Receipt source lacks exact retained recipient and cash movement evidence.';
    END IF;
    day := (r.effective_at AT TIME ZONE 'Asia/Manila')::date;
    SELECT * INTO period FROM accounting.fiscal_periods WHERE day BETWEEN start_date AND end_date FOR UPDATE;
    IF period.id IS NULL OR period.status<>'open' THEN
        RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Receipt posting date requires an open fiscal period.';
    END IF;
    result := jsonb_build_object('book_id',b,'mapping_id',m.id,'mapping_version',m.version,
      'receipt_id',r.id,'event_id',e.id,'treasury_account_id',wallet,'ledger_context_id',r.ledger_context_id,
      'posting_date',day,'fiscal_period_id',period.id,'amount',r.amount::text,'client_id',r.client_id,
      'source_event_key','treasury_receipt:'||e.id::text,'cash_account_id',m.cash_account_id,'liability_account_id',m.liability_account_id,
      'receipt',to_jsonb(r),'event',to_jsonb(e),'evidence',to_jsonb(proof),'movement',to_jsonb(line),
      'mapping',to_jsonb(m));
    RETURN result || jsonb_build_object('source_digest',encode(sha256(convert_to(result::text,'UTF8')),'hex'));
END $$;

CREATE OR REPLACE FUNCTION accounting.prepare_treasury_receipt(p_receipt_id UUID,p_mapping_id UUID,
    p_expected_source_digest TEXT,p_request_id UUID,p_actor_user_id UUID)
RETURNS UUID LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting,treasury AS $$
DECLARE wallet UUID; prior accounting.treasury_receipt_preparations%ROWTYPE; source JSONB; result UUID; previous TEXT;
BEGIN
    SELECT account_id INTO wallet FROM treasury.receipts WHERE id=p_receipt_id;
    PERFORM accounting.require_treasury_gl_actor(p_actor_user_id,wallet,'treasury.view');
    SELECT * INTO prior FROM accounting.treasury_receipt_preparations WHERE request_id=p_request_id;
    IF FOUND THEN
        IF prior.receipt_id=p_receipt_id AND prior.mapping_id=p_mapping_id
          AND prior.source_digest=p_expected_source_digest AND prior.actor_user_id=p_actor_user_id THEN RETURN prior.id; END IF;
        RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Preparation request retry conflicts with retained receipt review.';
    END IF;
    IF p_request_id IS NULL THEN RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='Receipt preparation request is required.'; END IF;
    source := accounting.treasury_receipt_coordinates(p_receipt_id,p_mapping_id);
    IF source->>'source_digest' IS DISTINCT FROM p_expected_source_digest THEN
        RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Receipt source evidence is stale; review it again.';
    END IF;
    IF EXISTS(SELECT 1 FROM accounting.treasury_receipt_postings WHERE receipt_id=p_receipt_id) THEN
        RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Receipt cash is already posted.';
    END IF;
    previous := current_setting('accounting.treasury_gl_write',true);
    PERFORM set_config('accounting.treasury_gl_write','treasury_receipt_preparations',true);
    INSERT INTO accounting.treasury_receipt_preparations(request_id,receipt_id,event_id,treasury_account_id,mapping_id,
      book_id,source_digest,confirmation_token,snapshot,actor_user_id)
    VALUES(p_request_id,p_receipt_id,(source->>'event_id')::uuid,wallet,p_mapping_id,(source->>'book_id')::uuid,
      p_expected_source_digest,encode(sha256(convert_to(gen_random_uuid()::text||p_expected_source_digest,'UTF8')),'hex'),
      source-'source_digest',p_actor_user_id) RETURNING id INTO result;
    PERFORM set_config('accounting.treasury_gl_write',coalesce(previous,''),true);
    RETURN result;
END $$;

-- Existing generic posting and reversal functions remain untouched. Admission
-- to this source family requires an exact retained preparation, and deferred
-- proof prevents a committed draft or posted entry without its immutable audit.
CREATE OR REPLACE FUNCTION accounting.guard_treasury_receipt_journal()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting AS $$
DECLARE p accounting.treasury_receipt_preparations%ROWTYPE;
BEGIN
    IF TG_OP<>'DELETE' AND NEW.reversal_of_entry_id IS NOT NULL AND EXISTS(
       SELECT 1 FROM accounting.journal_entries WHERE id=NEW.reversal_of_entry_id AND source_type='treasury_verified_receipt') THEN
        RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Receipt cash reversal requires a protected receipt correction adapter.';
    END IF;
    IF (TG_OP<>'INSERT' AND (OLD.source_type='treasury_verified_receipt' OR OLD.source_event_key LIKE 'treasury_receipt:%'))
      OR (TG_OP<>'DELETE' AND (NEW.source_type='treasury_verified_receipt' OR NEW.source_event_key LIKE 'treasury_receipt:%')) THEN
        IF TG_OP='DELETE' THEN RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Protected receipt journals cannot be cancelled.'; END IF;
        SELECT * INTO p FROM accounting.treasury_receipt_preparations
          WHERE id::text=current_setting('accounting.treasury_receipt_post',true);
        IF p.id IS NULL OR NEW.source_type IS DISTINCT FROM 'treasury_verified_receipt'
          OR NEW.source_event_key IS DISTINCT FROM p.snapshot->>'source_event_key'
          OR NEW.source_reference IS DISTINCT FROM p.receipt_id::text
          OR NEW.fiscal_period_id IS DISTINCT FROM (p.snapshot->>'fiscal_period_id')::uuid
          OR NEW.posting_date IS DISTINCT FROM (p.snapshot->>'posting_date')::date
          OR NEW.created_by_user_id IS DISTINCT FROM p.actor_user_id OR NEW.reversal_of_entry_id IS NOT NULL
          OR (NEW.status='posted' AND NEW.posted_by_user_id IS DISTINCT FROM p.actor_user_id) THEN
            RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Protected receipt journal requires its exact reviewed adapter.';
        END IF;
    END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS treasury_receipt_journal_guard ON accounting.journal_entries;
CREATE TRIGGER treasury_receipt_journal_guard BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_treasury_receipt_journal();

-- TRUNCATE does not run the inherited posted-line row guard. Preserve this
-- adapter's retained cash proof even through a trusted backend bulk operation.
CREATE OR REPLACE FUNCTION accounting.guard_treasury_receipt_line_truncate()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting AS $$
BEGIN
    IF EXISTS(SELECT 1 FROM accounting.journal_entries WHERE source_type='treasury_verified_receipt'
        OR source_event_key LIKE 'treasury_receipt:%') THEN
        RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Protected receipt journal lines are immutable; truncation would erase retained cash proof.';
    END IF;
    RETURN NULL;
END $$;
DROP TRIGGER IF EXISTS treasury_receipt_line_truncate_guard ON accounting.journal_lines;
CREATE TRIGGER treasury_receipt_line_truncate_guard BEFORE TRUNCATE ON accounting.journal_lines
FOR EACH STATEMENT EXECUTE FUNCTION accounting.guard_treasury_receipt_line_truncate();

CREATE OR REPLACE VIEW accounting.treasury_receipt_posting_status AS
SELECT a.event_id,a.receipt_id,a.treasury_account_id,a.book_id,a.journal_entry_id,a.preparation_id,a.source_digest,
 (p.snapshot->>'posting_date')::date AS posting_date,(p.snapshot->>'amount')::numeric(18,2) AS amount,
 (a.event_id=p.event_id AND a.receipt_id=p.receipt_id AND a.treasury_account_id=p.treasury_account_id
  AND a.book_id=p.book_id AND a.source_digest=p.source_digest AND a.actor_user_id=p.actor_user_id
  AND j.status='posted' AND j.source_type='treasury_verified_receipt'
  AND j.source_event_key=p.snapshot->>'source_event_key' AND j.source_reference=p.receipt_id::text
  AND j.posting_date=(p.snapshot->>'posting_date')::date AND j.fiscal_period_id=(p.snapshot->>'fiscal_period_id')::uuid
  AND j.created_by_user_id=p.actor_user_id AND j.posted_by_user_id=p.actor_user_id AND j.reversal_of_entry_id IS NULL
  AND (SELECT count(*) FROM accounting.journal_lines l WHERE l.journal_entry_id=j.id)=2
  AND (SELECT count(*) FROM accounting.journal_lines l WHERE l.journal_entry_id=j.id
    AND l.client_id=(p.snapshot->>'client_id')::uuid AND l.loan_id IS NULL
    AND ((l.line_number=1 AND l.account_id=(p.snapshot->>'cash_account_id')::uuid AND l.debit=(p.snapshot->>'amount')::numeric AND l.credit=0)
      OR (l.line_number=2 AND l.account_id=(p.snapshot->>'liability_account_id')::uuid AND l.credit=(p.snapshot->>'amount')::numeric AND l.debit=0)))=2) AS exact_posted,
 (EXISTS(SELECT 1 FROM treasury.event_revisions er WHERE er.event_id=a.event_id)
  OR ((p.snapshot->'mapping'->'cash_snapshot')-'is_active'-'name') IS DISTINCT FROM
      (accounting.treasury_gl_account_snapshot((p.snapshot->>'cash_account_id')::uuid)-'is_active'-'name')
  OR ((p.snapshot->'mapping'->'liability_snapshot')-'is_active'-'name') IS DISTINCT FROM
      (accounting.treasury_gl_account_snapshot((p.snapshot->>'liability_account_id')::uuid)-'is_active'-'name')) AS correction_pending
FROM accounting.treasury_receipt_postings a JOIN accounting.treasury_receipt_preparations p ON p.id=a.preparation_id
JOIN accounting.journal_entries j ON j.id=a.journal_entry_id;

CREATE OR REPLACE FUNCTION accounting.assert_treasury_receipt_audit()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting AS $$
DECLARE entry_id UUID;
BEGIN
    IF TG_TABLE_NAME='journal_entries' THEN
        IF NEW.source_type IS DISTINCT FROM 'treasury_verified_receipt' AND coalesce(NEW.source_event_key,'') NOT LIKE 'treasury_receipt:%' THEN RETURN NEW; END IF;
        entry_id:=NEW.id;
    ELSE entry_id:=NEW.journal_entry_id; END IF;
    IF NOT EXISTS(SELECT 1 FROM accounting.treasury_receipt_posting_status WHERE journal_entry_id=entry_id AND exact_posted) THEN
        RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Receipt journal requires exact immutable posted audit and two reviewed lines.';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS treasury_receipt_journal_audit ON accounting.journal_entries;
CREATE CONSTRAINT TRIGGER treasury_receipt_journal_audit AFTER INSERT OR UPDATE ON accounting.journal_entries
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION accounting.assert_treasury_receipt_audit();
DROP TRIGGER IF EXISTS treasury_receipt_posting_audit ON accounting.treasury_receipt_postings;
CREATE CONSTRAINT TRIGGER treasury_receipt_posting_audit AFTER INSERT ON accounting.treasury_receipt_postings
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION accounting.assert_treasury_receipt_audit();

CREATE OR REPLACE FUNCTION accounting.post_treasury_receipt(p_preparation_id UUID,p_expected_source_digest TEXT,
    p_confirmation_token TEXT,p_actor_user_id UUID)
RETURNS UUID LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting,treasury AS $$
DECLARE p accounting.treasury_receipt_preparations%ROWTYPE; a accounting.treasury_receipt_postings%ROWTYPE;
    source JSONB; result UUID; previous TEXT; previous_write TEXT;
BEGIN
    SELECT * INTO p FROM accounting.treasury_receipt_preparations WHERE id=p_preparation_id;
    PERFORM accounting.require_treasury_gl_actor(p_actor_user_id,p.treasury_account_id,'treasury.view');
    IF p.id IS NULL OR p.source_digest IS DISTINCT FROM p_expected_source_digest
      OR p.confirmation_token IS DISTINCT FROM p_confirmation_token OR p.actor_user_id IS DISTINCT FROM p_actor_user_id THEN
        RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Receipt confirmation must exactly match the prepared evidence and actor.';
    END IF;
    SELECT * INTO a FROM accounting.treasury_receipt_postings WHERE event_id=p.event_id;
    IF FOUND THEN
        IF a.preparation_id=p.id AND a.source_digest=p_expected_source_digest AND a.actor_user_id=p_actor_user_id
          AND EXISTS(SELECT 1 FROM accounting.treasury_receipt_posting_status WHERE journal_entry_id=a.journal_entry_id AND exact_posted) THEN RETURN a.journal_entry_id; END IF;
        RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Receipt already posted by a different exact review; retry conflicts.';
    END IF;
    source:=accounting.treasury_receipt_coordinates(p.receipt_id,p.mapping_id);
    IF source->>'source_digest' IS DISTINCT FROM p.source_digest OR source-'source_digest' IS DISTINCT FROM p.snapshot THEN
        RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Receipt source evidence is stale; prepare a fresh review.';
    END IF;
    previous:=current_setting('accounting.treasury_receipt_post',true);
    previous_write:=current_setting('accounting.treasury_gl_write',true);
    PERFORM set_config('accounting.treasury_receipt_post',p.id::text,true);
    INSERT INTO accounting.journal_entries(fiscal_period_id,posting_date,description,source_type,source_reference,source_event_key,created_by_user_id)
    VALUES((p.snapshot->>'fiscal_period_id')::uuid,(p.snapshot->>'posting_date')::date,'Verified borrower receipt; funds unapplied',
      'treasury_verified_receipt',p.receipt_id::text,p.snapshot->>'source_event_key',p_actor_user_id) RETURNING id INTO result;
    INSERT INTO accounting.journal_lines(journal_entry_id,line_number,account_id,description,debit,credit,client_id)
    VALUES(result,1,(p.snapshot->>'cash_account_id')::uuid,'Verified wallet cash',(p.snapshot->>'amount')::numeric,0,(p.snapshot->>'client_id')::uuid),
      (result,2,(p.snapshot->>'liability_account_id')::uuid,'Unapplied borrower funds',0,(p.snapshot->>'amount')::numeric,(p.snapshot->>'client_id')::uuid);
    PERFORM accounting.post_journal_entry(result,p_actor_user_id);
    PERFORM set_config('accounting.treasury_gl_write','treasury_receipt_postings',true);
    INSERT INTO accounting.treasury_receipt_postings(preparation_id,receipt_id,event_id,treasury_account_id,book_id,journal_entry_id,source_digest,actor_user_id)
    VALUES(p.id,p.receipt_id,p.event_id,p.treasury_account_id,p.book_id,result,p.source_digest,p_actor_user_id);
    IF NOT EXISTS(SELECT 1 FROM accounting.treasury_receipt_posting_status WHERE journal_entry_id=result AND exact_posted) THEN
        RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Receipt posted audit does not match exact reviewed lines.';
    END IF;
    PERFORM set_config('accounting.treasury_receipt_post',coalesce(previous,''),true);
    PERFORM set_config('accounting.treasury_gl_write',coalesce(previous_write,''),true);
    RETURN result;
END $$;

REVOKE ALL ON accounting.treasury_receipt_posting_status FROM PUBLIC;
DO $$
DECLARE f RECORD; r TEXT; t TEXT;
BEGIN
    FOR f IN SELECT p.oid::regprocedure AS signature FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
      WHERE n.nspname='accounting' AND p.proname IN ('treasury_gl_wallet_snapshot','treasury_gl_account_snapshot',
        'require_treasury_gl_actor','guard_treasury_gl_evidence','configure_treasury_cash_mapping','treasury_receipt_coordinates',
        'prepare_treasury_receipt','guard_treasury_receipt_journal','guard_treasury_receipt_line_truncate',
        'assert_treasury_receipt_audit','post_treasury_receipt') LOOP
        EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC',f.signature);
        FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
            IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN EXECUTE format('REVOKE ALL ON FUNCTION %s FROM %I',f.signature,r); END IF;
        END LOOP;
    END LOOP;
    FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
        IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN
            FOREACH t IN ARRAY ARRAY['treasury_cash_mappings','treasury_receipt_preparations','treasury_receipt_postings','treasury_receipt_posting_status'] LOOP
                EXECUTE format('REVOKE ALL ON accounting.%I FROM %I',t,r);
            END LOOP;
        END IF;
    END LOOP;
END $$;

COMMIT;
