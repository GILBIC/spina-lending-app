BEGIN;

DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM accounting.accounts WHERE (code='1040' OR system_key='transfer_funds_in_transit')
   AND NOT(code='1040' AND system_key='transfer_funds_in_transit'
     AND account_type='asset' AND normal_balance='debit' AND is_posting)) THEN
  RAISE EXCEPTION 'Transfer transit control conflicts with an existing chart definition.';
 END IF;
 INSERT INTO accounting.accounts(code,system_key,name,account_type,normal_balance)
 VALUES('1040','transfer_funds_in_transit','Transfer Funds in Transit','asset','debit')
 ON CONFLICT(system_key) DO NOTHING;
END $$;

CREATE OR REPLACE FUNCTION accounting.guard_transfer_transit_definition()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF OLD.code='1040' OR OLD.system_key='transfer_funds_in_transit' THEN
  IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Transit control definitions are immutable; retire the account instead.'; END IF;
  IF ROW(NEW.id,NEW.code,NEW.system_key,NEW.account_type,NEW.normal_balance,NEW.is_posting)
   IS DISTINCT FROM ROW(OLD.id,OLD.code,OLD.system_key,OLD.account_type,OLD.normal_balance,OLD.is_posting) THEN
   RAISE EXCEPTION 'Transit control definitions are immutable; only display name and active status may change.';
  END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS transfer_transit_definition ON accounting.accounts;
CREATE TRIGGER transfer_transit_definition BEFORE UPDATE OR DELETE ON accounting.accounts
FOR EACH ROW EXECUTE FUNCTION accounting.guard_transfer_transit_definition();
REVOKE ALL ON FUNCTION accounting.guard_transfer_transit_definition() FROM PUBLIC;
DO $$ DECLARE r TEXT; BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN EXECUTE format('REVOKE ALL ON FUNCTION accounting.guard_transfer_transit_definition() FROM %I',r); END IF;
 END LOOP;
END $$;


CREATE TABLE IF NOT EXISTS accounting.treasury_transfer_preparations (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),request_id UUID NOT NULL UNIQUE,
 transfer_id UUID NOT NULL REFERENCES treasury.transfers(id),leg TEXT NOT NULL CHECK(leg IN ('source','destination')),
 event_id UUID NOT NULL REFERENCES treasury.events(id),book_id UUID NOT NULL REFERENCES accounting.book_identity(id),
 source_account_id UUID NOT NULL REFERENCES treasury.accounts(id),destination_account_id UUID NOT NULL REFERENCES treasury.accounts(id),
 source_mapping_id UUID NOT NULL REFERENCES accounting.treasury_cash_mappings(id),destination_mapping_id UUID NOT NULL REFERENCES accounting.treasury_cash_mappings(id),
 source_digest TEXT NOT NULL CHECK(source_digest ~ '^[0-9a-f]{64}$'),confirmation_token TEXT NOT NULL CHECK(confirmation_token ~ '^[0-9a-f]{64}$'),
 snapshot JSONB NOT NULL,actor_user_id UUID NOT NULL REFERENCES core.users(id),created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS accounting.treasury_transfer_postings (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),preparation_id UUID NOT NULL UNIQUE REFERENCES accounting.treasury_transfer_preparations(id),
 transfer_id UUID NOT NULL REFERENCES treasury.transfers(id),leg TEXT NOT NULL CHECK(leg IN ('source','destination')),
 event_id UUID NOT NULL UNIQUE REFERENCES treasury.events(id),book_id UUID NOT NULL REFERENCES accounting.book_identity(id),
 source_account_id UUID NOT NULL REFERENCES treasury.accounts(id),destination_account_id UUID NOT NULL REFERENCES treasury.accounts(id),
 journal_entry_id UUID NOT NULL UNIQUE REFERENCES accounting.journal_entries(id),amount NUMERIC(18,2) NOT NULL CHECK(amount>0),
 fee NUMERIC(18,2) NOT NULL CHECK(fee>=0 AND (leg='source' OR fee=0)),
 source_digest TEXT NOT NULL CHECK(source_digest ~ '^[0-9a-f]{64}$'),actor_user_id UUID NOT NULL REFERENCES core.users(id),
 created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),UNIQUE(transfer_id,leg)
);
DO $$ DECLARE t TEXT; BEGIN
 FOREACH t IN ARRAY ARRAY['treasury_transfer_preparations','treasury_transfer_postings'] LOOP
  EXECUTE format('ALTER TABLE accounting.%I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('REVOKE ALL ON accounting.%I FROM PUBLIC',t);
  EXECUTE format('DROP TRIGGER IF EXISTS treasury_transfer_evidence_guard ON accounting.%I',t);
  EXECUTE format('CREATE TRIGGER treasury_transfer_evidence_guard BEFORE INSERT OR UPDATE OR DELETE ON accounting.%I FOR EACH ROW EXECUTE FUNCTION accounting.guard_treasury_gl_evidence()',t);
  EXECUTE format('DROP TRIGGER IF EXISTS treasury_transfer_truncate_guard ON accounting.%I',t);
  EXECUTE format('CREATE TRIGGER treasury_transfer_truncate_guard BEFORE TRUNCATE ON accounting.%I FOR EACH STATEMENT EXECUTE FUNCTION accounting.guard_treasury_gl_evidence()',t);
 END LOOP;
END $$;

CREATE OR REPLACE FUNCTION accounting.require_treasury_transfer_actor(p_actor UUID,p_transfer UUID)
RETURNS VOID LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting,treasury AS $$
DECLARE original treasury.transfers%ROWTYPE; current_transfer treasury.transfers%ROWTYPE; account UUID;
BEGIN
 SELECT * INTO original FROM treasury.transfers WHERE id=p_transfer;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='Private transfer is unavailable.'; END IF;
 FOR account IN SELECT id FROM treasury.accounts WHERE id IN(original.source_account_id,original.destination_account_id) ORDER BY id LOOP
  PERFORM accounting.require_treasury_gl_actor(p_actor,account,'treasury.view');
 END LOOP;
 SELECT * INTO current_transfer FROM treasury.transfers WHERE id=p_transfer FOR UPDATE;
 IF (current_transfer.source_account_id,current_transfer.destination_account_id) IS DISTINCT FROM
   (original.source_account_id,original.destination_account_id) THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Transfer account identity changed while authorizing; review again.';
 END IF;
END $$;

CREATE OR REPLACE FUNCTION accounting.treasury_transfer_mapping_snapshot(p_mapping UUID,p_account UUID)
RETURNS JSONB LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting,treasury AS $$
DECLARE m accounting.treasury_cash_mappings%ROWTYPE; book UUID;
BEGIN
 book:=accounting.require_book_treasury_account(p_account);
 SELECT * INTO m FROM accounting.treasury_cash_mappings WHERE id=p_mapping;
 IF m.id IS NULL OR m.treasury_account_id<>p_account OR m.book_id<>book
  OR m.id IS DISTINCT FROM (SELECT id FROM accounting.treasury_cash_mappings WHERE treasury_account_id=p_account ORDER BY version DESC LIMIT 1)
  OR m.wallet_snapshot IS DISTINCT FROM accounting.treasury_gl_wallet_snapshot(p_account)
  OR m.cash_snapshot IS DISTINCT FROM accounting.treasury_gl_account_snapshot(m.cash_account_id)
  OR NOT EXISTS(SELECT 1 FROM treasury.accounts a JOIN accounting.accounts c ON c.id=m.cash_account_id
    WHERE a.id=p_account AND a.active AND c.is_active AND c.is_posting AND c.account_type='asset' AND c.normal_balance='debit'
      AND ((a.kind='physical_cash' AND c.code='1010' AND c.system_key='cash_office')
        OR (a.kind IN('bank','gcash') AND c.code='1030' AND c.system_key='cash_bank_gcash'))) THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Latest explicit owned-wallet cash mapping is required; review stale mapping evidence.';
 END IF;
 RETURN jsonb_build_object('id',m.id,'version',m.version,'book_id',m.book_id,'account_id',p_account,
  'cash_account_id',m.cash_account_id,'wallet_snapshot',m.wallet_snapshot,'cash_snapshot',m.cash_snapshot);
END $$;

CREATE OR REPLACE FUNCTION accounting.treasury_transfer_origin(p_transfer UUID,p_leg TEXT)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog,accounting,treasury SET timezone='UTC' AS $$
DECLARE t treasury.transfers%ROWTYPE; e treasury.events%ROWTYPE; event UUID; result JSONB;
BEGIN
 SELECT * INTO t FROM treasury.transfers WHERE id=p_transfer;
 IF t.id IS NULL OR p_leg IS NULL OR p_leg NOT IN('source','destination') THEN RETURN NULL; END IF;
 event:=CASE p_leg WHEN 'source' THEN t.source_event_id ELSE t.destination_event_id END;
 SELECT * INTO e FROM treasury.events WHERE id=event;
 IF e.id IS NULL THEN RETURN NULL; END IF;
 result:=jsonb_build_object('transfer_id',t.id,'ledger_context_id',t.ledger_context_id,'source_account_id',t.source_account_id,
  'destination_account_id',t.destination_account_id,'amount',t.amount::text,'leg',p_leg,'event',to_jsonb(e),
  'movements',(SELECT coalesce(jsonb_agg(to_jsonb(m) ORDER BY m.component,m.id),'[]'::jsonb) FROM treasury.movement_lines m WHERE m.event_id=e.id),
  'revisions',(SELECT coalesce(jsonb_agg(to_jsonb(r) ORDER BY r.version),'[]'::jsonb) FROM treasury.event_revisions r WHERE r.event_id=e.id),
  'source_links',(SELECT coalesce(jsonb_agg(to_jsonb(s) ORDER BY s.id),'[]'::jsonb) FROM treasury.source_links s WHERE s.event_id=e.id),
  'receipts',(SELECT coalesce(jsonb_agg(r.id ORDER BY r.id),'[]'::jsonb) FROM treasury.receipts r WHERE r.event_id=e.id),
  'transfer_uses',(SELECT coalesce(jsonb_agg(other.id ORDER BY other.id),'[]'::jsonb) FROM treasury.transfers other WHERE e.id IN(other.source_event_id,other.destination_event_id)));
 -- Appending the missing destination is an actual later fact, not a correction
 -- of the retained source debit. Destination proof does depend on its source.
 IF p_leg='destination' THEN result:=result||jsonb_build_object('source_origin',accounting.treasury_transfer_origin(p_transfer,'source')); END IF;
 RETURN result;
END $$;

CREATE OR REPLACE VIEW accounting.treasury_transfer_posting_proof AS
SELECT a.transfer_id,a.leg,a.event_id,a.book_id,a.source_account_id,a.destination_account_id,
 CASE a.leg WHEN 'source' THEN a.source_account_id ELSE a.destination_account_id END AS treasury_account_id,
 a.preparation_id,a.journal_entry_id,a.source_digest,a.amount,a.fee,(p.snapshot->>'posting_date')::date AS posting_date,
 (a.transfer_id=p.transfer_id AND a.leg=p.leg AND a.event_id=p.event_id AND a.book_id=p.book_id
  AND a.source_account_id=p.source_account_id AND a.destination_account_id=p.destination_account_id
  AND a.source_digest=p.source_digest AND a.actor_user_id=p.actor_user_id
  AND a.amount=(p.snapshot->>'amount')::numeric AND a.fee=(p.snapshot->>'fee')::numeric
  AND j.status='posted' AND j.source_type='treasury_owned_transfer' AND j.source_event_key=p.snapshot->>'source_event_key'
  AND j.source_reference=p.transfer_id::text AND j.posting_date=(p.snapshot->>'posting_date')::date
  AND j.fiscal_period_id=(p.snapshot->>'fiscal_period_id')::uuid AND j.created_by_user_id=p.actor_user_id
  AND j.posted_by_user_id=p.actor_user_id AND j.reversal_of_entry_id IS NULL
  AND (SELECT count(*) FROM accounting.journal_lines WHERE journal_entry_id=j.id)=jsonb_array_length(p.snapshot->'lines')
  AND NOT EXISTS(SELECT 1 FROM jsonb_to_recordset(p.snapshot->'lines') x(line_number INT,account_id UUID,debit NUMERIC,credit NUMERIC)
   WHERE NOT EXISTS(SELECT 1 FROM accounting.journal_lines l WHERE l.journal_entry_id=j.id AND l.line_number=x.line_number
    AND l.account_id=x.account_id AND l.debit=x.debit AND l.credit=x.credit AND l.client_id IS NULL AND l.loan_id IS NULL))) AS exact_posted,
 (accounting.treasury_transfer_origin(a.transfer_id,a.leg) IS DISTINCT FROM p.snapshot->'origin'
  OR EXISTS(SELECT 1 FROM jsonb_array_elements(p.snapshot->'lines') line
    WHERE (line->'account_snapshot')-ARRAY['name','is_active'] IS DISTINCT FROM
      accounting.treasury_gl_account_snapshot((line->>'account_id')::uuid)-ARRAY['name','is_active'])) AS correction_pending
FROM accounting.treasury_transfer_postings a JOIN accounting.treasury_transfer_preparations p ON p.id=a.preparation_id
JOIN accounting.journal_entries j ON j.id=a.journal_entry_id;

CREATE OR REPLACE VIEW accounting.treasury_transfer_posting_status AS
SELECT p.transfer_id,p.leg,p.event_id,p.book_id,p.source_account_id,p.destination_account_id,p.treasury_account_id,
 p.preparation_id,p.journal_entry_id,p.source_digest,p.amount,p.fee,p.posting_date,p.exact_posted,
 (p.correction_pending OR (p.leg='destination' AND
   (source.exact_posted IS DISTINCT FROM true OR source.correction_pending IS DISTINCT FROM false))) AS correction_pending
FROM accounting.treasury_transfer_posting_proof p
LEFT JOIN accounting.treasury_transfer_posting_proof source ON source.transfer_id=p.transfer_id AND source.leg='source';

CREATE OR REPLACE FUNCTION accounting.treasury_transfer_coordinates(p_transfer UUID,p_leg TEXT,p_source_mapping UUID,p_destination_mapping UUID)
RETURNS JSONB LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting,treasury SET timezone='UTC' AS $$
DECLARE t treasury.transfers%ROWTYPE; e treasury.events%ROWTYPE; period accounting.fiscal_periods%ROWTYPE;
 origin JSONB; source_map JSONB; destination_map JSONB; result JSONB; lines JSONB; evidence JSONB;
 book UUID; other_book UUID; own_account UUID; own_cash UUID; transit UUID; fee_account UUID; event UUID;
 day DATE; source_proof accounting.treasury_transfer_posting_status%ROWTYPE;
BEGIN
 IF current_setting('transaction_isolation')<>'read committed' THEN RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Transfer accounting requires READ COMMITTED.'; END IF;
 IF p_leg IS NULL OR p_leg NOT IN('source','destination') THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='An exact actual transfer leg is required.'; END IF;
 SELECT * INTO t FROM treasury.transfers WHERE id=p_transfer;
 IF t.id IS NULL THEN RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Actual transfer source is unavailable.'; END IF;
 PERFORM id FROM treasury.accounts WHERE id IN(t.source_account_id,t.destination_account_id) ORDER BY id FOR UPDATE;
 SELECT * INTO t FROM treasury.transfers WHERE id=p_transfer FOR UPDATE;
 book:=accounting.require_book_treasury_account(t.source_account_id);
 other_book:=accounting.require_book_treasury_account(t.destination_account_id);
 IF book<>other_book OR t.source_account_id=t.destination_account_id
  OR NOT EXISTS(SELECT 1 FROM treasury.accounts WHERE id=t.source_account_id AND ledger_context_id=t.ledger_context_id)
  OR NOT EXISTS(SELECT 1 FROM treasury.accounts WHERE id=t.destination_account_id AND ledger_context_id=t.ledger_context_id) THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Transfer must remain between distinct owned accounts in the same book and context.';
 END IF;
 LOCK TABLE accounting.accounts IN SHARE MODE;
 source_map:=accounting.treasury_transfer_mapping_snapshot(p_source_mapping,t.source_account_id);
 destination_map:=accounting.treasury_transfer_mapping_snapshot(p_destination_mapping,t.destination_account_id);
 event:=CASE p_leg WHEN 'source' THEN t.source_event_id ELSE t.destination_event_id END;
 own_account:=CASE p_leg WHEN 'source' THEN t.source_account_id ELSE t.destination_account_id END;
 own_cash:=CASE p_leg WHEN 'source' THEN (source_map->>'cash_account_id')::uuid ELSE (destination_map->>'cash_account_id')::uuid END;
 SELECT * INTO e FROM treasury.events WHERE id=event FOR UPDATE;
 IF e.id IS NULL THEN RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Actual verified transfer leg is required; metadata does not move money.'; END IF;
 LOCK TABLE treasury.event_revisions,treasury.movement_lines,treasury.source_links,treasury.receipts IN SHARE MODE;
 origin:=accounting.treasury_transfer_origin(p_transfer,p_leg);
 IF e.account_id<>own_account OR e.ledger_context_id<>t.ledger_context_id OR e.amount<>t.amount
  OR e.direction<>(CASE p_leg WHEN 'source' THEN 'debit' ELSE 'credit' END)
  OR e.classification<>'account_transfer' OR e.version<>1
  OR e.provider IS DISTINCT FROM (SELECT kind FROM treasury.accounts WHERE id=own_account)
  OR e.effective_at>clock_timestamp() OR btrim(e.recipient_attestation)='' OR e.verified_by_user_id IS NULL
  OR jsonb_array_length(origin->'revisions')<>0 OR jsonb_array_length(origin->'source_links')<>0
  OR jsonb_array_length(origin->'receipts')<>0 OR jsonb_array_length(origin->'transfer_uses')<>1
  OR (SELECT count(*) FROM treasury.movement_lines WHERE event_id=e.id)<>(CASE WHEN e.fee>0 THEN 2 ELSE 1 END)
  OR NOT EXISTS(SELECT 1 FROM treasury.movement_lines WHERE event_id=e.id AND component='principal'
    AND signed_amount=CASE p_leg WHEN 'source' THEN -e.amount ELSE e.amount END
    AND account_id=e.account_id AND ledger_context_id=e.ledger_context_id AND effective_at=e.effective_at AND evidence_id=e.evidence_id)
  OR (e.fee>0 AND (p_leg<>'source' OR NOT EXISTS(SELECT 1 FROM treasury.movement_lines WHERE event_id=e.id AND component='fee'
    AND signed_amount=-e.fee AND account_id=e.account_id AND ledger_context_id=e.ledger_context_id AND effective_at=e.effective_at AND evidence_id=e.evidence_id))) THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Transfer event is corrected, reused or does not exactly prove its actual leg and fee.';
 END IF;
 SELECT to_jsonb(ev) INTO evidence FROM treasury.evidence ev WHERE id=e.evidence_id AND account_id=own_account AND purpose='recipient';
 IF evidence IS NULL THEN RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Retained recipient evidence for the actual transfer leg is required.'; END IF;
 day:=(e.effective_at AT TIME ZONE 'Asia/Manila')::date;
 SELECT * INTO period FROM accounting.fiscal_periods WHERE day BETWEEN start_date AND end_date FOR UPDATE;
 IF period.id IS NULL OR period.status<>'open' OR (SELECT count(*) FROM accounting.fiscal_periods WHERE day BETWEEN start_date AND end_date)<>1 THEN RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='The actual transfer leg date requires one open fiscal period.'; END IF;
 LOCK TABLE accounting.journal_entries,accounting.journal_lines IN SHARE ROW EXCLUSIVE MODE;
 SELECT id INTO transit FROM accounting.accounts WHERE code='1040' AND system_key='transfer_funds_in_transit' AND account_type='asset' AND normal_balance='debit' AND is_active AND is_posting;
 SELECT id INTO fee_account FROM accounting.accounts WHERE code='5240' AND system_key='bank_charges_expense' AND account_type='expense' AND normal_balance='debit' AND is_active AND is_posting;
 IF transit IS NULL OR (e.fee>0 AND fee_account IS NULL) THEN RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Exact active transit and actual fee expense chart roles are required.'; END IF;
 IF p_leg='destination' THEN
  SELECT * INTO source_proof FROM accounting.treasury_transfer_posting_status WHERE transfer_id=t.id AND leg='source';
  IF source_proof.journal_entry_id IS NULL OR NOT source_proof.exact_posted OR source_proof.correction_pending
    OR source_proof.book_id<>book OR source_proof.amount<>e.amount OR source_proof.posting_date>day THEN
   RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Destination requires exact earlier source debit accounting proof; unconfirmed or reversed chronology needs investigation.';
  END IF;
 END IF;
 SELECT jsonb_agg(jsonb_build_object('line_number',x.n,'account_id',x.account,'account_code',a.code,
   'account_snapshot',accounting.treasury_gl_account_snapshot(x.account),'debit',x.debit::numeric(18,2)::text,'credit',x.credit::numeric(18,2)::text,
   'description',x.description) ORDER BY x.n) INTO lines
 FROM (VALUES
   (10,CASE p_leg WHEN 'source' THEN transit ELSE own_cash END,e.amount,0::numeric,'Actual owned transfer principal'),
   (20,fee_account,e.fee,0::numeric,'Separately evidenced source transaction fee'),
   (30,CASE p_leg WHEN 'source' THEN own_cash ELSE transit END,0::numeric,e.amount+e.fee,'Actual owned transfer counter-entry')
 ) x(n,account,debit,credit,description) JOIN accounting.accounts a ON a.id=x.account WHERE x.debit>0 OR x.credit>0;
 result:=jsonb_build_object('transfer_id',t.id,'leg',p_leg,'event_id',e.id,'book_id',book,
  'source_account_id',t.source_account_id,'destination_account_id',t.destination_account_id,'treasury_account_id',own_account,
  'ledger_context_id',t.ledger_context_id,'amount',e.amount::text,'fee',e.fee::text,'posting_date',day,'fiscal_period_id',period.id,
  'source_event_key','treasury_transfer:'||e.id::text,'source_mapping',source_map,'destination_mapping',destination_map,
  'transit_account_id',transit,'source_posted_journal_id',source_proof.journal_entry_id,'source_posted_digest',source_proof.source_digest,
  'origin',origin,'evidence',evidence,'lines',lines);
 RETURN result||jsonb_build_object('source_digest',encode(sha256(convert_to(result::text,'UTF8')),'hex'));
END $$;

CREATE OR REPLACE FUNCTION accounting.prepare_treasury_transfer(p_transfer UUID,p_leg TEXT,p_source_mapping UUID,p_destination_mapping UUID,p_digest TEXT,p_request UUID,p_actor UUID)
RETURNS UUID LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting AS $$
DECLARE prior accounting.treasury_transfer_preparations%ROWTYPE; source JSONB; result UUID; previous TEXT;
BEGIN
 PERFORM accounting.require_treasury_transfer_actor(p_actor,p_transfer);
 SELECT * INTO prior FROM accounting.treasury_transfer_preparations WHERE request_id=p_request;
 IF FOUND THEN
  IF prior.transfer_id=p_transfer AND prior.leg=p_leg AND prior.source_mapping_id=p_source_mapping
   AND prior.destination_mapping_id=p_destination_mapping AND prior.source_digest=p_digest AND prior.actor_user_id=p_actor THEN RETURN prior.id; END IF;
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Transfer preparation retry conflicts with the retained exact review.';
 END IF;
 IF p_request IS NULL THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='Transfer preparation request identity is required.'; END IF;
 IF EXISTS(SELECT 1 FROM accounting.treasury_transfer_postings WHERE transfer_id=p_transfer AND leg=p_leg) THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Actual transfer leg is already accounted.';
 END IF;
 source:=accounting.treasury_transfer_coordinates(p_transfer,p_leg,p_source_mapping,p_destination_mapping);
 IF source->>'source_digest' IS DISTINCT FROM p_digest THEN RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Transfer source or mappings are stale; review again.'; END IF;
 previous:=current_setting('accounting.treasury_gl_write',true);
 PERFORM set_config('accounting.treasury_gl_write','treasury_transfer_preparations',true);
 INSERT INTO accounting.treasury_transfer_preparations(request_id,transfer_id,leg,event_id,book_id,source_account_id,destination_account_id,
  source_mapping_id,destination_mapping_id,source_digest,confirmation_token,snapshot,actor_user_id)
 VALUES(p_request,p_transfer,p_leg,(source->>'event_id')::uuid,(source->>'book_id')::uuid,
  (source->>'source_account_id')::uuid,(source->>'destination_account_id')::uuid,p_source_mapping,p_destination_mapping,p_digest,
  encode(sha256(convert_to(gen_random_uuid()::text||p_digest,'UTF8')),'hex'),source-'source_digest',p_actor) RETURNING id INTO result;
 PERFORM set_config('accounting.treasury_gl_write',coalesce(previous,''),true);
 RETURN result;
END $$;

CREATE OR REPLACE FUNCTION accounting.guard_treasury_transfer_journal()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting AS $$
DECLARE p accounting.treasury_transfer_preparations%ROWTYPE;
BEGIN
 IF TG_OP<>'DELETE' AND NEW.reversal_of_entry_id IS NOT NULL AND EXISTS(SELECT 1 FROM accounting.journal_entries
   WHERE id=NEW.reversal_of_entry_id AND source_type='treasury_owned_transfer') THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Transfer reversal requires its protected accounting correction adapter.';
 END IF;
 IF (TG_OP<>'INSERT' AND (OLD.source_type='treasury_owned_transfer' OR OLD.source_event_key LIKE 'treasury_transfer:%'))
  OR (TG_OP<>'DELETE' AND (NEW.source_type='treasury_owned_transfer' OR NEW.source_event_key LIKE 'treasury_transfer:%')) THEN
  IF TG_OP='DELETE' THEN RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Protected transfer journals cannot be cancelled.'; END IF;
  SELECT * INTO p FROM accounting.treasury_transfer_preparations WHERE id::text=current_setting('accounting.treasury_transfer_post',true);
  IF p.id IS NULL OR NEW.source_type IS DISTINCT FROM 'treasury_owned_transfer' OR NEW.source_event_key IS DISTINCT FROM p.snapshot->>'source_event_key'
   OR NEW.source_reference IS DISTINCT FROM p.transfer_id::text OR NEW.posting_date IS DISTINCT FROM (p.snapshot->>'posting_date')::date
   OR NEW.fiscal_period_id IS DISTINCT FROM (p.snapshot->>'fiscal_period_id')::uuid OR NEW.created_by_user_id IS DISTINCT FROM p.actor_user_id
   OR NEW.reversal_of_entry_id IS NOT NULL OR (NEW.status='posted' AND NEW.posted_by_user_id IS DISTINCT FROM p.actor_user_id) THEN
   RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Protected transfer journal requires its exact reviewed actual-leg adapter.';
  END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS treasury_transfer_journal_guard ON accounting.journal_entries;
CREATE TRIGGER treasury_transfer_journal_guard BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_treasury_transfer_journal();

CREATE OR REPLACE FUNCTION accounting.assert_treasury_transfer_audit()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting AS $$
DECLARE entry UUID;
BEGIN
 IF TG_TABLE_NAME='journal_entries' THEN
  IF NEW.source_type IS DISTINCT FROM 'treasury_owned_transfer' AND coalesce(NEW.source_event_key,'') NOT LIKE 'treasury_transfer:%' THEN RETURN NEW; END IF;
  entry:=NEW.id;
 ELSE entry:=NEW.journal_entry_id; END IF;
 IF NOT EXISTS(SELECT 1 FROM accounting.treasury_transfer_posting_status WHERE journal_entry_id=entry AND exact_posted) THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Transfer journal requires its exact immutable actual-leg audit.';
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS treasury_transfer_journal_audit ON accounting.journal_entries;
CREATE CONSTRAINT TRIGGER treasury_transfer_journal_audit AFTER INSERT OR UPDATE ON accounting.journal_entries
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION accounting.assert_treasury_transfer_audit();
DROP TRIGGER IF EXISTS treasury_transfer_posting_audit ON accounting.treasury_transfer_postings;
CREATE CONSTRAINT TRIGGER treasury_transfer_posting_audit AFTER INSERT ON accounting.treasury_transfer_postings
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION accounting.assert_treasury_transfer_audit();

CREATE OR REPLACE FUNCTION accounting.guard_treasury_transfer_line_truncate()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM accounting.journal_entries WHERE source_type='treasury_owned_transfer') THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Protected transfer cash and transit proof cannot be truncated.';
 END IF;
 RETURN NULL;
END $$;
DROP TRIGGER IF EXISTS treasury_transfer_line_truncate ON accounting.journal_lines;
CREATE TRIGGER treasury_transfer_line_truncate BEFORE TRUNCATE ON accounting.journal_lines FOR EACH STATEMENT
EXECUTE FUNCTION accounting.guard_treasury_transfer_line_truncate();

CREATE OR REPLACE FUNCTION accounting.post_treasury_transfer(p_preparation UUID,p_digest TEXT,p_token TEXT,p_actor UUID)
RETURNS UUID LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting,treasury AS $$
DECLARE p accounting.treasury_transfer_preparations%ROWTYPE; prior accounting.treasury_transfer_postings%ROWTYPE;
 source JSONB; result UUID; account UUID; previous TEXT; previous_write TEXT;
BEGIN
 SELECT * INTO p FROM accounting.treasury_transfer_preparations WHERE id=p_preparation;
 IF p.id IS NULL THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='Private transfer preparation is unavailable.'; END IF;
 FOR account IN SELECT id FROM treasury.accounts WHERE id IN(p.source_account_id,p.destination_account_id) ORDER BY id LOOP
  PERFORM accounting.require_treasury_gl_actor(p_actor,account,'treasury.view');
 END LOOP;
 IF p.source_digest IS DISTINCT FROM p_digest OR p.confirmation_token IS DISTINCT FROM p_token OR p.actor_user_id IS DISTINCT FROM p_actor THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Transfer confirmation must match the exact retained review and actor.';
 END IF;
 SELECT * INTO prior FROM accounting.treasury_transfer_postings WHERE transfer_id=p.transfer_id AND leg=p.leg;
 IF FOUND THEN
  IF prior.preparation_id=p.id AND prior.source_digest=p_digest AND prior.actor_user_id=p_actor
   AND EXISTS(SELECT 1 FROM accounting.treasury_transfer_posting_status WHERE journal_entry_id=prior.journal_entry_id AND exact_posted) THEN RETURN prior.journal_entry_id; END IF;
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Transfer leg is already accounted under a different exact review.';
 END IF;
 source:=accounting.treasury_transfer_coordinates(p.transfer_id,p.leg,p.source_mapping_id,p.destination_mapping_id);
 IF source->>'source_digest' IS DISTINCT FROM p.source_digest OR source-'source_digest' IS DISTINCT FROM p.snapshot THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Actual transfer leg, authority or mapping evidence is stale; prepare again.';
 END IF;
 previous:=current_setting('accounting.treasury_transfer_post',true);
 previous_write:=current_setting('accounting.treasury_gl_write',true);
 PERFORM set_config('accounting.treasury_transfer_post',p.id::text,true);
 INSERT INTO accounting.journal_entries(fiscal_period_id,posting_date,description,source_type,source_reference,source_event_key,created_by_user_id)
 VALUES((p.snapshot->>'fiscal_period_id')::uuid,(p.snapshot->>'posting_date')::date,'Actual owned-wallet transfer '||p.leg,
  'treasury_owned_transfer',p.transfer_id::text,p.snapshot->>'source_event_key',p_actor) RETURNING id INTO result;
 INSERT INTO accounting.journal_lines(journal_entry_id,line_number,account_id,description,debit,credit)
 SELECT result,x.line_number,x.account_id,x.description,x.debit,x.credit
 FROM jsonb_to_recordset(p.snapshot->'lines') x(line_number INT,account_id UUID,description TEXT,debit NUMERIC,credit NUMERIC);
 PERFORM accounting.post_journal_entry(result,p_actor);
 PERFORM set_config('accounting.treasury_gl_write','treasury_transfer_postings',true);
 INSERT INTO accounting.treasury_transfer_postings(preparation_id,transfer_id,leg,event_id,book_id,source_account_id,destination_account_id,
  journal_entry_id,amount,fee,source_digest,actor_user_id)
 VALUES(p.id,p.transfer_id,p.leg,p.event_id,p.book_id,p.source_account_id,p.destination_account_id,result,
  (p.snapshot->>'amount')::numeric,(p.snapshot->>'fee')::numeric,p.source_digest,p_actor);
 IF NOT EXISTS(SELECT 1 FROM accounting.treasury_transfer_posting_status WHERE journal_entry_id=result AND exact_posted) THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Posted transfer audit does not match exact reviewed money coordinates.';
 END IF;
 PERFORM set_config('accounting.treasury_transfer_post',coalesce(previous,''),true);
 PERFORM set_config('accounting.treasury_gl_write',coalesce(previous_write,''),true);
 RETURN result;
END $$;

CREATE OR REPLACE FUNCTION accounting.treasury_transfer_transit_reconciliation(p_as_of DATE)
RETURNS TABLE(transfer_id UUID,book_id UUID,source_account_id UUID,destination_account_id UUID,
 source_amount NUMERIC,destination_amount NUMERIC,expected_transit NUMERIC,ledger_transit NUMERIC,difference NUMERIC,requires_review BOOLEAN)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 WITH retained AS (
  SELECT p.transfer_id,p.book_id,p.source_account_id,p.destination_account_id,
   coalesce(sum(p.amount) FILTER(WHERE p.leg='source'),0) AS source_amount,
   coalesce(sum(p.amount) FILTER(WHERE p.leg='destination'),0) AS destination_amount,
   bool_or(NOT p.exact_posted OR p.correction_pending) AS requires_review
  FROM accounting.treasury_transfer_posting_status p WHERE p.posting_date<=p_as_of
  GROUP BY p.transfer_id,p.book_id,p.source_account_id,p.destination_account_id
 ), ledger AS (
  SELECT a.transfer_id,sum(l.debit-l.credit) AS amount
  FROM accounting.treasury_transfer_postings a JOIN accounting.treasury_transfer_preparations p ON p.id=a.preparation_id
  JOIN accounting.journal_entries j ON j.id=a.journal_entry_id AND j.status='posted' AND j.posting_date<=p_as_of
  JOIN accounting.journal_lines l ON l.journal_entry_id=j.id AND l.account_id=(p.snapshot->>'transit_account_id')::uuid
  GROUP BY a.transfer_id
 ) SELECT r.transfer_id,r.book_id,r.source_account_id,r.destination_account_id,r.source_amount,r.destination_amount,
   r.source_amount-r.destination_amount,coalesce(l.amount,0),coalesce(l.amount,0)-(r.source_amount-r.destination_amount),
   r.requires_review OR coalesce(l.amount,0)<>(r.source_amount-r.destination_amount)
 FROM retained r LEFT JOIN ledger l ON l.transfer_id=r.transfer_id;
$$;

-- Preserve the 0149 composition and bind the same public function OID, so all
-- existing close views and commit checks continue through the latest inventory.
CREATE OR REPLACE FUNCTION accounting.period_transfer_control_blockers(p_period UUID)
RETURNS TABLE(source_type TEXT,source_id UUID,effective_date DATE,amount NUMERIC(18,2),reason TEXT,account_id UUID)
LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT 'transfer_transit_control'::text,r.transfer_id,p.end_date,r.difference::numeric(18,2),
  'transfer_transit_reconciliation_required'::text,r.source_account_id
 FROM accounting.fiscal_periods p CROSS JOIN LATERAL accounting.treasury_transfer_transit_reconciliation(p.end_date) r
 WHERE p.id=p_period AND r.requires_review
 UNION ALL
 SELECT 'transfer_transit_unregistered'::text,j.id,p.end_date,sum(l.debit-l.credit)::numeric(18,2),
  'transfer_transit_line_without_native_audit'::text,NULL::uuid
 FROM accounting.fiscal_periods p JOIN accounting.journal_entries j ON j.status='posted' AND j.posting_date<=p.end_date
 JOIN accounting.journal_lines l ON l.journal_entry_id=j.id JOIN accounting.accounts a ON a.id=l.account_id
 WHERE p.id=p_period AND a.system_key='transfer_funds_in_transit'
  AND NOT EXISTS(SELECT 1 FROM accounting.treasury_transfer_postings audit WHERE audit.journal_entry_id=j.id)
 GROUP BY j.id,p.end_date;
$$;
CREATE OR REPLACE FUNCTION accounting.period_source_blockers(p_period_id UUID)
RETURNS TABLE(source_type TEXT,source_id UUID,effective_date DATE,amount NUMERIC(18,2),reason TEXT,account_id UUID)
LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT initial.* FROM accounting.period_initial_source_blockers(p_period_id) initial
 WHERE NOT(initial.source_type='treasury_event' AND (
  EXISTS(SELECT 1 FROM accounting.treasury_receipt_posting_status p WHERE p.event_id=initial.source_id AND p.exact_posted AND NOT p.correction_pending)
  OR EXISTS(SELECT 1 FROM accounting.treasury_transfer_posting_status p WHERE p.event_id=initial.source_id AND p.exact_posted AND NOT p.correction_pending)))
 UNION ALL SELECT * FROM accounting.period_legacy_source_blockers(p_period_id)
 UNION ALL SELECT * FROM accounting.period_liability_source_blockers(p_period_id)
 UNION ALL SELECT * FROM accounting.period_transfer_control_blockers(p_period_id);
$$;
CREATE OR REPLACE FUNCTION accounting.assert_period_source_complete(p_period_id UUID)
RETURNS VOID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 PERFORM accounting.assert_period_legacy_source_complete(p_period_id);
 LOCK TABLE accounting.liability_obligations,accounting.liability_line_claims,
  accounting.treasury_cash_mappings,accounting.treasury_receipt_preparations,accounting.treasury_receipt_postings,
  treasury.event_revisions,treasury.receipts,treasury.applications,
  treasury.transfers,accounting.treasury_transfer_preparations,accounting.treasury_transfer_postings IN SHARE MODE;
 PERFORM accounting.assert_period_initial_source_complete(p_period_id);
END $$;
CREATE OR REPLACE VIEW accounting.period_source_close_state AS
SELECT period.id AS fiscal_period_id,period.status AS fiscal_period_status,blockers.blocker_count,
 CASE WHEN blockers.blocker_count=0 THEN 'supported_source_gate_clear' WHEN period.status='closed' THEN 'closed_source_review_required'
  ELSE 'blocked_unreconciled_sources' END AS source_close_status,
 'lending_treasury_owned_transfer_v4'::text AS coverage_policy,false AS comprehensive_source_coverage,
 ARRAY['treasury','collector','lending','tax','period_assessment','liabilities']::text[] AS source_families
FROM accounting.fiscal_periods period
CROSS JOIN LATERAL (SELECT count(*) AS blocker_count FROM accounting.period_source_blockers(period.id)) blockers;

DO $$ DECLARE f RECORD; r TEXT; t TEXT; BEGIN
 FOR f IN SELECT p.oid::regprocedure signature FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
  WHERE n.nspname='accounting' AND p.proname IN('require_treasury_transfer_actor','treasury_transfer_mapping_snapshot',
   'treasury_transfer_origin','treasury_transfer_coordinates','prepare_treasury_transfer','guard_treasury_transfer_journal',
   'assert_treasury_transfer_audit','guard_treasury_transfer_line_truncate','post_treasury_transfer',
   'treasury_transfer_transit_reconciliation','period_transfer_control_blockers','period_source_blockers','assert_period_source_complete') LOOP
  EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC',f.signature);
  FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
   IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN EXECUTE format('REVOKE ALL ON FUNCTION %s FROM %I',f.signature,r); END IF;
  END LOOP;
 END LOOP;
 FOREACH t IN ARRAY ARRAY['treasury_transfer_preparations','treasury_transfer_postings','treasury_transfer_posting_proof',
   'treasury_transfer_posting_status','period_source_close_state'] LOOP
  EXECUTE format('REVOKE ALL ON accounting.%I FROM PUBLIC',t);
  FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
   IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN EXECUTE format('REVOKE ALL ON accounting.%I FROM %I',t,r); END IF;
  END LOOP;
 END LOOP;
END $$;
COMMIT;
