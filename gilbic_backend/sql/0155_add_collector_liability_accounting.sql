BEGIN;

-- Actual observed cash, then separate liability evidence. No operational writer
-- invokes this adapter and no installation creates money, mappings or balances.
DO $$ DECLARE item RECORD; BEGIN
 FOR item IN SELECT * FROM (VALUES
  ('1060','collector_return_in_transit','Collector Returns Awaiting Receipt','asset','debit'),
  ('2210','unidentified_collector_excess','Unidentified Collector Excess','liability','credit'),
  ('2220','collector_credit_payable','Collector Credit Payable','liability','credit')
 ) definitions(code,system_key,name,account_type,normal_balance) LOOP
  IF EXISTS(SELECT 1 FROM accounting.accounts WHERE code=item.code OR system_key=item.system_key) THEN
   IF 1<>(SELECT count(*) FROM accounting.accounts WHERE code=item.code AND system_key=item.system_key
     AND account_type=item.account_type AND normal_balance=item.normal_balance AND is_posting) THEN
    RAISE EXCEPTION 'Collector control chart definition conflicts at %.',item.code;
   END IF;
  ELSE
   INSERT INTO accounting.accounts(code,system_key,name,account_type,normal_balance)
   VALUES(item.code,item.system_key,item.name,item.account_type,item.normal_balance);
  END IF;
 END LOOP;
END $$;

CREATE TABLE IF NOT EXISTS accounting.collector_liability_preparations (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), request_id UUID NOT NULL UNIQUE,
 source_kind TEXT NOT NULL CHECK(source_kind IN ('settlement','recognition','return_debit','return_confirmation','return_reversal')),
 source_id UUID NOT NULL, book_id UUID NOT NULL REFERENCES accounting.book_identity(id),
 account_id UUID NOT NULL REFERENCES treasury.accounts(id),
 collector_user_id UUID NOT NULL REFERENCES core.users(id),
 source_digest TEXT NOT NULL CHECK(source_digest ~ '^[0-9a-f]{64}$'),
 confirmation_token TEXT NOT NULL CHECK(confirmation_token ~ '^[0-9a-f]{64}$'),
 snapshot JSONB NOT NULL, actor_user_id UUID NOT NULL REFERENCES core.users(id),
 created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS accounting.collector_liability_postings (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 preparation_id UUID NOT NULL UNIQUE REFERENCES accounting.collector_liability_preparations(id),
 source_kind TEXT NOT NULL, source_id UUID NOT NULL, UNIQUE(source_kind,source_id),
 event_id UUID UNIQUE REFERENCES treasury.events(id),
 book_id UUID NOT NULL REFERENCES accounting.book_identity(id),
 account_id UUID NOT NULL REFERENCES treasury.accounts(id),
 collector_user_id UUID NOT NULL REFERENCES core.users(id),
 journal_entry_id UUID NOT NULL UNIQUE REFERENCES accounting.journal_entries(id),
 source_digest TEXT NOT NULL, actor_user_id UUID NOT NULL REFERENCES core.users(id),
 created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
DO $$ DECLARE item TEXT; BEGIN
 FOREACH item IN ARRAY ARRAY['collector_liability_preparations','collector_liability_postings'] LOOP
  EXECUTE format('ALTER TABLE accounting.%I ENABLE ROW LEVEL SECURITY',item);
  EXECUTE format('REVOKE ALL ON accounting.%I FROM PUBLIC',item);
  EXECUTE format('DROP TRIGGER IF EXISTS collector_liability_evidence_guard ON accounting.%I',item);
  EXECUTE format('CREATE TRIGGER collector_liability_evidence_guard BEFORE INSERT OR UPDATE OR DELETE ON accounting.%I FOR EACH ROW EXECUTE FUNCTION accounting.guard_treasury_gl_evidence()',item);
  EXECUTE format('DROP TRIGGER IF EXISTS collector_liability_truncate_guard ON accounting.%I',item);
  EXECUTE format('CREATE TRIGGER collector_liability_truncate_guard BEFORE TRUNCATE ON accounting.%I FOR EACH STATEMENT EXECUTE FUNCTION accounting.guard_treasury_gl_evidence()',item);
 END LOOP;
END $$;

CREATE OR REPLACE FUNCTION accounting.guard_collector_control_definition()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF OLD.code IN ('1060','2210','2220') AND (TG_OP='DELETE' OR
    ROW(NEW.id,NEW.code,NEW.system_key,NEW.account_type,NEW.normal_balance,NEW.is_posting)
    IS DISTINCT FROM ROW(OLD.id,OLD.code,OLD.system_key,OLD.account_type,OLD.normal_balance,OLD.is_posting)) THEN
  RAISE EXCEPTION 'Collector control definitions are immutable; display name and retirement may change.' USING ERRCODE='55000';
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS collector_control_definition ON accounting.accounts;
CREATE TRIGGER collector_control_definition BEFORE UPDATE OR DELETE ON accounting.accounts
FOR EACH ROW EXECUTE FUNCTION accounting.guard_collector_control_definition();

CREATE OR REPLACE FUNCTION accounting.collector_liability_accounts(p_kind TEXT,p_source UUID)
RETURNS UUID[] LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE result UUID[];
BEGIN
 IF p_kind='settlement' THEN
  SELECT ARRAY[account_id] INTO result FROM treasury.collector_settlements WHERE id=p_source;
 ELSIF p_kind='return_debit' THEN
  SELECT ARRAY[account_id,(payload->>'origin_account_id')::uuid] INTO result FROM treasury.collector_actions WHERE id=p_source;
 ELSIF p_kind IN ('recognition','return_confirmation','return_reversal') THEN
  SELECT ARRAY[entry.account_id,credit.account_id] INTO result
  FROM treasury.collector_entries entry JOIN treasury.collector_credits credit ON credit.id=entry.credit_id WHERE entry.id=p_source;
 ELSE RAISE EXCEPTION 'Unsupported Collector accounting source family.' USING ERRCODE='22023'; END IF;
 IF result IS NULL THEN RAISE EXCEPTION 'Private Collector accounting source is unavailable.' USING ERRCODE='42501'; END IF;
 RETURN ARRAY(SELECT DISTINCT item FROM unnest(result) item ORDER BY item);
END $$;

CREATE OR REPLACE FUNCTION accounting.require_collector_liability_actor(p_actor UUID,p_kind TEXT,p_source UUID)
RETURNS VOID LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE wallet UUID;
BEGIN
 FOREACH wallet IN ARRAY accounting.collector_liability_accounts(p_kind,p_source) LOOP
  PERFORM accounting.require_treasury_gl_actor(p_actor,wallet,'treasury.view');
  PERFORM accounting.require_treasury_gl_actor(p_actor,wallet,'treasury.collector_surplus.view');
  PERFORM accounting.require_book_treasury_account(wallet);
 END LOOP;
END $$;

CREATE OR REPLACE FUNCTION accounting.collector_gl_account(p_code TEXT,p_key TEXT,p_type TEXT,p_normal TEXT)
RETURNS UUID LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE result UUID;
BEGIN
 SELECT id INTO result FROM accounting.accounts WHERE code=p_code AND system_key=p_key
  AND account_type=p_type AND normal_balance=p_normal AND is_posting;
 IF result IS NULL THEN RAISE EXCEPTION 'Exact Collector chart role required for %.',p_code USING ERRCODE='55000'; END IF;
 RETURN result;
END $$;

CREATE OR REPLACE FUNCTION accounting.collector_liability_prerequisite(p_kind TEXT,p_source UUID,p_day DATE)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE result JSONB;
BEGIN
 IF NOT EXISTS(SELECT 1 FROM accounting.collector_liability_postings WHERE source_kind=p_kind AND source_id=p_source) THEN
  RAISE EXCEPTION 'Exact posted Collector % proof is required first.',p_kind USING ERRCODE='55000';
 END IF;
 SELECT jsonb_build_object('id',posted.id,'journal_entry_id',posted.journal_entry_id,'source_digest',posted.source_digest,
   'evidence',prepared.snapshot->'evidence') INTO result
 FROM accounting.collector_liability_postings posted JOIN accounting.collector_liability_preparations prepared ON prepared.id=posted.preparation_id
 JOIN accounting.collector_liability_posting_status status ON status.preparation_id=prepared.id
 WHERE posted.source_kind=p_kind AND posted.source_id=p_source AND status.exact_posted AND NOT status.correction_pending
  AND (prepared.snapshot->>'posting_date')::date<=p_day;
 IF result IS NULL THEN RAISE EXCEPTION 'Current exact posted Collector % proof is required first.',p_kind USING ERRCODE='55000'; END IF;
 RETURN result;
END $$;

-- The origin excludes operational capacity/version/status values that legitimately
-- change when subsequent immutable entries are appended. Corrections, frozen
-- credit and inconsistent capacities still fail validation, never disappear.
CREATE OR REPLACE FUNCTION accounting.collector_liability_origin(p_kind TEXT,p_source UUID,p_mapping_ids JSONB DEFAULT NULL)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
DECLARE
 s treasury.collector_settlements%ROWTYPE; counted treasury.collector_counts%ROWTYPE;
 excess treasury.collector_cases%ROWTYPE; credit treasury.collector_credits%ROWTYPE;
 entry treasury.collector_entries%ROWTYPE; action treasury.collector_actions%ROWTYPE;
 acknowledgment treasury.collector_acknowledgments%ROWTYPE; resolution treasury.collector_resolutions%ROWTYPE;
 event treasury.events%ROWTYPE; remittance lending.collection_remittances%ROWTYPE;
 mapping accounting.treasury_cash_mappings%ROWTYPE; wallet treasury.accounts%ROWTYPE;
 period accounting.fiscal_periods%ROWTYPE; book accounting.book_identity%ROWTYPE;
 selected_wallet UUID; account_ids UUID[]; collector UUID; cash UUID; custody UUID; unidentified UUID; payable UUID; transit UUID; fees UUID;
 day DATE; amount NUMERIC; fee NUMERIC:=0; gross NUMERIC:=0; excess_amount NUMERIC:=0;
 source_facts JSONB:='{}'; prerequisites JSONB:='[]'; evidence JSONB:='[]'; mappings JSONB:='{}';
 lines JSONB; line_values JSONB:='[]'; dependency JSONB; item RECORD; current_source RECORD; proof BOOLEAN; count_entries BIGINT;
BEGIN
 account_ids:=accounting.collector_liability_accounts(p_kind,p_source);
 SELECT * INTO book FROM accounting.book_identity WHERE singleton;
 IF book.id IS NULL THEN RAISE EXCEPTION 'Accounting book identity is required.' USING ERRCODE='55000'; END IF;
 IF p_kind='settlement' THEN
  SELECT * INTO s FROM treasury.collector_settlements WHERE id=p_source;
  SELECT * INTO counted FROM treasury.collector_counts WHERE id=s.count_id;
  SELECT * INTO remittance FROM lending.collection_remittances WHERE id=s.remittance_id;
  SELECT * INTO excess FROM treasury.collector_cases WHERE settlement_id=s.id;
  selected_wallet:=s.account_id; collector:=s.collector_user_id; amount:=(s.payload->>'physical_amount')::numeric;
  gross:=(s.payload->>'gross_obligation')::numeric; excess_amount:=amount-gross;
  SELECT * INTO event FROM treasury.events WHERE id=s.event_id;
  day:=(event.effective_at AT TIME ZONE 'Asia/Manila')::date;
  IF event.id IS NULL OR remittance.status<>'received' OR counted.payload->>'disposition' IS DISTINCT FROM 'counted_ready'
   OR NOT s.payload ?& ARRAY['physical_amount','gross_obligation','authorized_credit_amount']
   OR NOT counted.payload ?& ARRAY['refund_due_total','physical_cash_required','gross_obligation','counted_amount','difference','counted_at']
   OR amount<=0 OR gross<=0 OR excess_amount<0 OR remittance.total_amount<>gross
   OR s.payload->>'authorized_credit_amount'<>'0.00' OR counted.payload->>'refund_due_total'<>'0.00'
   OR (counted.payload->>'physical_cash_required')::numeric<>gross OR (counted.payload->>'gross_obligation')::numeric<>gross
   OR (counted.payload->>'counted_amount')::numeric<>amount OR (counted.payload->>'difference')::numeric<>excess_amount
   OR (counted.payload->>'counted_at')::timestamptz<>event.effective_at
   OR event.direction<>'credit' OR event.classification<>'collector_counted_receipt' OR event.fee<>0 OR event.amount<>amount
   OR counted.account_id<>s.account_id OR counted.collector_user_id<>collector OR counted.evidence_id<>event.evidence_id
   OR EXISTS(SELECT 1 FROM lending.collection_remittance_refund_due_release_items WHERE remittance_id=remittance.id)
   OR EXISTS(SELECT 1 FROM treasury.collector_exceptions WHERE payload->>'remittance_id'=remittance.id::text)
   OR EXISTS(SELECT 1 FROM accounting.remittance_transfer_journal_preparations WHERE remittance_id=remittance.id)
   OR EXISTS(SELECT 1 FROM accounting.journal_entries WHERE source_type='remittance_transfer' AND source_reference=remittance.id::text)
   OR (excess_amount>0 AND (excess.id IS NULL OR (excess.payload->>'received_excess_amount')::numeric<>excess_amount))
   OR (excess_amount=0 AND excess.id IS NOT NULL) THEN
   RAISE EXCEPTION 'Collector count requires exact original cash, unnetted collections and no competing remittance accounting.' USING ERRCODE='55000';
  END IF;
  IF gross<>(SELECT coalesce(sum(i.amount),0) FROM lending.collection_remittance_items i WHERE i.remittance_id=remittance.id)
   OR jsonb_typeof(counted.payload#>'{source_snapshot,items}') IS DISTINCT FROM 'array'
   OR jsonb_array_length(counted.payload#>'{source_snapshot,items}')<>(SELECT count(*) FROM lending.collection_remittance_items WHERE remittance_id=remittance.id) THEN
   RAISE EXCEPTION 'Collector count source constituents changed.' USING ERRCODE='55000';
  END IF;
  FOR item IN SELECT i.*,to_jsonb(t) AS current_collection FROM lending.collection_remittance_items i
   JOIN lending.collection_transactions t ON t.id=i.transaction_id WHERE i.remittance_id=remittance.id ORDER BY i.transaction_id LOOP
   SELECT * INTO current_source FROM lending.collection_transactions WHERE id=item.transaction_id;
   IF current_source.is_voided OR NOT current_source.is_locked OR current_source.funding_source<>'collector_cash'
    OR current_source.remittance_id IS DISTINCT FROM remittance.id OR current_source.amount<>item.amount
    OR current_source.amount<>current_source.applied_amount OR current_source.unallocated_amount<>0
    OR current_source.collection_date<>item.collection_date OR current_source.collection_date>day
    OR current_source.collector_user_id<>collector
    OR NOT ((current_source.entry_type='pass' AND current_source.amount=0)
      OR (current_source.entry_type IN ('payment','advance') AND current_source.amount>0)) OR NOT EXISTS(
      SELECT 1 FROM jsonb_array_elements(counted.payload#>'{source_snapshot,items}') retained
      WHERE retained->>'transaction_id'=item.transaction_id::text AND (retained->>'amount')::numeric=item.amount
       AND (retained->>'collection_date')::date=item.collection_date AND (retained->>'edit_version')::integer=current_source.edit_version) THEN
    RAISE EXCEPTION 'Collector count source collection changed or is unsupported.' USING ERRCODE='55000';
   END IF;
   IF current_source.entry_type='pass' THEN
    IF EXISTS(SELECT 1 FROM accounting.journal_entries WHERE source_type='collection' AND source_reference=item.transaction_id::text) THEN
     RAISE EXCEPTION 'A zero-effect Collector PASS must not have a collection cash journal.' USING ERRCODE='55000'; END IF;
    CONTINUE;
   END IF;
   proof:=false;
   IF EXISTS(SELECT 1 FROM accounting.regular_journal_draft_preparations WHERE transaction_id=item.transaction_id) THEN
    proof:=accounting.legacy_regular_collection_posted_exact(item.transaction_id);
   ELSIF EXISTS(SELECT 1 FROM accounting.seven_by_seven_journal_postings WHERE transaction_id=item.transaction_id) THEN
    SELECT EXISTS(SELECT 1 FROM accounting.seven_by_seven_journal_posting_status p WHERE p.transaction_id=item.transaction_id
      AND p.posted_audit_exact AND p.source_cash_amount=item.amount AND p.posting_date=item.collection_date) INTO proof;
   END IF;
   IF NOT proof THEN RAISE EXCEPTION 'Exact posted Collector custody collection proof is required before count accounting.' USING ERRCODE='55000'; END IF;
  END LOOP;
  IF (SELECT count(*) FROM treasury.source_links WHERE event_id=event.id)<>(CASE WHEN excess_amount>0 THEN 2 ELSE 1 END)
   OR NOT EXISTS(SELECT 1 FROM treasury.source_links WHERE event_id=event.id AND source_kind='collector_remittance_physical'
    AND source_id=remittance.id AND linked_amount=gross AND ledger_context_id=s.ledger_context_id)
   OR (excess_amount>0 AND NOT EXISTS(SELECT 1 FROM treasury.source_links WHERE event_id=event.id AND source_kind='collector_excess_pending'
    AND source_id=excess.id AND linked_amount=excess_amount AND ledger_context_id=s.ledger_context_id)) THEN
   RAISE EXCEPTION 'Collector accepted cash source links do not match.' USING ERRCODE='55000';
  END IF;
  source_facts:=jsonb_build_object('settlement',to_jsonb(s),'count',to_jsonb(counted),
    'remittance_id',remittance.id,'case_id',excess.id,'gross',gross::text,'excess',excess_amount::text,
    'constituents',(SELECT jsonb_agg(jsonb_build_object('item',to_jsonb(i),'transaction',to_jsonb(t)) ORDER BY i.transaction_id)
      FROM lending.collection_remittance_items i JOIN lending.collection_transactions t ON t.id=i.transaction_id WHERE i.remittance_id=remittance.id));
  custody:=accounting.collector_gl_account('1020','cash_collector_custody','asset','debit');
  unidentified:=accounting.collector_gl_account('2210','unidentified_collector_excess','liability','credit');
  line_values:=jsonb_build_array(jsonb_build_object('account_id',custody,'debit','0.00','credit',gross::text));
  IF excess_amount>0 THEN line_values:=line_values||jsonb_build_array(jsonb_build_object('account_id',unidentified,'debit','0.00','credit',excess_amount::text)); END IF;
 ELSE
  IF p_kind='return_debit' THEN
   SELECT * INTO action FROM treasury.collector_actions WHERE id=p_source;
   SELECT * INTO credit FROM treasury.collector_credits WHERE id=action.credit_id;
  ELSE
   SELECT * INTO entry FROM treasury.collector_entries WHERE id=p_source;
   SELECT * INTO credit FROM treasury.collector_credits WHERE id=entry.credit_id;
   IF entry.payload->>'kind' IS DISTINCT FROM (CASE p_kind WHEN 'recognition' THEN 'recognition' WHEN 'return_confirmation' THEN 'return' ELSE 'return_reversal' END) THEN
    RAISE EXCEPTION 'Collector entry does not match the reviewed accounting family.' USING ERRCODE='55000';
   END IF;
   IF p_kind<>'recognition' THEN SELECT * INTO action FROM treasury.collector_actions WHERE id=(entry.payload->>'action_id')::uuid; END IF;
  END IF;
  SELECT * INTO excess FROM treasury.collector_cases WHERE id=credit.case_id;
  IF credit.id IS NULL OR credit.opening_anchor_id IS NOT NULL OR excess.settlement_id IS NULL
   OR (credit.payload->>'frozen')::boolean OR (credit.payload->>'reclassified_amount')::numeric<>0 OR (credit.payload->>'applied_amount')::numeric<>0 THEN
   RAISE EXCEPTION 'Collector credit requires original accepted excess; historical opening or source correction is unsupported.' USING ERRCODE='55000';
  END IF;
  IF (excess.payload->>'unidentified_amount')::numeric IS DISTINCT FROM
    (excess.payload->>'received_excess_amount')::numeric-(SELECT coalesce(sum((payload->>'amount')::numeric),0) FROM treasury.collector_resolutions WHERE case_id=excess.id)
   OR (credit.payload->>'outstanding_amount')::numeric IS DISTINCT FROM
    (SELECT coalesce(sum(CASE payload->>'kind' WHEN 'recognition' THEN (payload->>'amount')::numeric WHEN 'return' THEN -(payload->>'amount')::numeric WHEN 'return_reversal' THEN (payload->>'amount')::numeric ELSE 0 END),0) FROM treasury.collector_entries WHERE credit_id=credit.id) THEN
   RAISE EXCEPTION 'Collector liability capacity does not reconcile to immutable entries.' USING ERRCODE='55000';
  END IF;
  collector:=credit.collector_user_id; selected_wallet:=coalesce(action.account_id,credit.account_id);
  payable:=accounting.collector_gl_account('2220','collector_credit_payable','liability','credit');
  source_facts:=jsonb_build_object('credit_id',credit.id,'case_id',credit.case_id,'recognized_amount',credit.payload->>'recognized_amount');
  IF p_kind='recognition' THEN
   amount:=(entry.payload->>'amount')::numeric; day:=(entry.created_at AT TIME ZONE 'Asia/Manila')::date;
   SELECT * INTO resolution FROM treasury.collector_resolutions WHERE case_id=excess.id AND payload->>'credit_id'=credit.id::text;
   IF resolution.id IS NULL OR resolution.payload->>'kind'<>'collector_credit' OR (resolution.payload->>'amount')::numeric<>amount
    OR (credit.payload->>'recognized_amount')::numeric<>amount OR resolution.evidence_id IS DISTINCT FROM (entry.payload->>'evidence_id')::uuid
    OR (SELECT count(*) FROM treasury.collector_entries WHERE credit_id=credit.id AND payload->>'kind'='recognition')<>1
    OR (SELECT count(*) FROM treasury.collector_resolutions WHERE payload->>'credit_id'=credit.id::text)<>1 THEN
    RAISE EXCEPTION 'Collector recognition requires one exact immutable resolution.' USING ERRCODE='55000';
   END IF;
   dependency:=accounting.collector_liability_prerequisite('settlement',excess.settlement_id,day);
   unidentified:=accounting.collector_gl_account('2210','unidentified_collector_excess','liability','credit');
   line_values:=jsonb_build_array(jsonb_build_object('account_id',unidentified,'debit',amount::text,'credit','0.00'),jsonb_build_object('account_id',payable,'debit','0.00','credit',amount::text));
   source_facts:=source_facts||jsonb_build_object('entry',to_jsonb(entry),'resolution',to_jsonb(resolution));
   evidence:=evidence||jsonb_build_array((SELECT to_jsonb(e) FROM treasury.evidence e WHERE id=resolution.evidence_id AND account_id=credit.account_id AND purpose='recipient'));
  ELSE
   IF action.id IS NULL OR action.credit_id<>credit.id OR action.payload->>'kind'<>'return'
    OR action.payload->>'origin_account_id'<>credit.account_id::text OR action.collector_user_id<>collector
    OR action.ledger_context_id<>credit.ledger_context_id OR action.event_id IS NULL
    OR action.payload->>'status' NOT IN ('debited_confirmation_pending','paid','partly_reversed','reversed') THEN
    RAISE EXCEPTION 'An exact approved actual Collector return debit is required.' USING ERRCODE='55000';
   END IF;
   SELECT * INTO event FROM treasury.events WHERE id=CASE WHEN p_kind='return_reversal' THEN (entry.payload->>'incoming_event_id')::uuid ELSE action.event_id END;
   amount:=CASE WHEN p_kind='return_reversal' THEN (entry.payload->>'amount')::numeric ELSE (action.payload->>'amount')::numeric END;
   day:=(event.effective_at AT TIME ZONE 'Asia/Manila')::date; fee:=event.fee;
   transit:=accounting.collector_gl_account('1060','collector_return_in_transit','asset','debit');
   source_facts:=source_facts||jsonb_build_object('action_id',action.id,'approved_action',action.payload-ARRAY['status','event_id','event_version','acknowledgment_id','reversed_amount'],
     'event_id',action.event_id,'event_version',action.payload->>'event_version');
   evidence:=evidence||jsonb_build_array((SELECT to_jsonb(e) FROM treasury.evidence e WHERE id=action.evidence_id AND account_id=action.account_id AND purpose='recipient'));
   IF p_kind='return_debit' THEN
    IF event.direction<>'debit' OR event.amount<>amount OR event.classification<>'verified_unclassified'
     OR NOT EXISTS(SELECT 1 FROM treasury.source_links WHERE event_id=event.id AND source_id=action.id AND source_kind='collector_surplus_return'
      AND linked_amount=amount AND ledger_context_id=action.ledger_context_id)
     OR (SELECT count(*) FROM treasury.source_links WHERE event_id=event.id)<>1 THEN
     RAISE EXCEPTION 'Exact actual Collector return principal, fee and source link are required.' USING ERRCODE='55000';
    END IF;
    SELECT id INTO item FROM treasury.collector_entries WHERE credit_id=credit.id AND payload->>'kind'='recognition';
    dependency:=accounting.collector_liability_prerequisite('recognition',item.id,day);
    line_values:=jsonb_build_array(jsonb_build_object('account_id',transit,'debit',amount::text,'credit','0.00'));
    IF fee>0 THEN fees:=accounting.collector_gl_account('5240','bank_charges_expense','expense','debit');
     line_values:=line_values||jsonb_build_array(jsonb_build_object('account_id',fees,'debit',fee::text,'credit','0.00')); END IF;
   ELSIF p_kind='return_confirmation' THEN
    SELECT * INTO acknowledgment FROM treasury.collector_acknowledgments WHERE id=(action.payload->>'acknowledgment_id')::uuid;
    IF action.payload->>'status' NOT IN ('paid','partly_reversed','reversed') OR acknowledgment.id IS NULL
     OR acknowledgment.action_id<>action.id OR acknowledgment.collector_user_id<>collector
     OR acknowledgment.payload->>'confirmation'<>'received' OR acknowledgment.payload->>'event_id'<>event.id::text
     OR (acknowledgment.payload->>'reviewed_amount')::numeric<>amount OR (entry.payload->>'amount')::numeric<>amount
     OR (acknowledgment.payload->>'acknowledged_at')::timestamptz<event.effective_at
     OR (acknowledgment.payload->>'acknowledged_at')::timestamptz>entry.created_at
     OR (SELECT count(*) FROM treasury.collector_entries WHERE payload->>'action_id'=action.id::text AND payload->>'kind'='return')<>1 THEN
     RAISE EXCEPTION 'An exact immutable received Collector acknowledgment is required.' USING ERRCODE='55000';
    END IF;
    day:=((acknowledgment.payload->>'acknowledged_at')::timestamptz AT TIME ZONE 'Asia/Manila')::date; fee:=0;
    dependency:=accounting.collector_liability_prerequisite('return_debit',action.id,day);
    line_values:=jsonb_build_array(jsonb_build_object('account_id',payable,'debit',amount::text,'credit','0.00'),jsonb_build_object('account_id',transit,'debit','0.00','credit',amount::text));
    source_facts:=source_facts||jsonb_build_object('entry',to_jsonb(entry),'acknowledgment',to_jsonb(acknowledgment));
   ELSE
    IF event.direction<>'credit' OR event.amount<>amount OR fee<>0 OR event.classification<>'collector_return_reversal'
     OR NOT EXISTS(SELECT 1 FROM treasury.source_links WHERE event_id=event.id AND source_id=action.id AND source_kind='collector_surplus_return_reversal'
       AND linked_amount=amount AND ledger_context_id=action.ledger_context_id)
     OR (SELECT count(*) FROM treasury.source_links WHERE event_id=event.id)<>1
     OR (SELECT coalesce(sum((payload->>'amount')::numeric),0) FROM treasury.collector_entries WHERE payload->>'action_id'=action.id::text AND payload->>'kind'='return_reversal')>(action.payload->>'amount')::numeric THEN
     RAISE EXCEPTION 'Exact actual incoming Collector reversal is required.' USING ERRCODE='55000';
    END IF;
    SELECT id INTO item FROM treasury.collector_entries WHERE payload->>'action_id'=action.id::text AND payload->>'kind'='return';
    dependency:=accounting.collector_liability_prerequisite('return_confirmation',item.id,day);
    line_values:=jsonb_build_array(jsonb_build_object('account_id',payable,'debit','0.00','credit',amount::text));
    source_facts:=source_facts||jsonb_build_object('entry',to_jsonb(entry));
   END IF;
  END IF;
  prerequisites:=prerequisites||jsonb_build_array(dependency-'evidence'); evidence:=evidence||coalesce(dependency->'evidence','[]');
 END IF;
 -- Common event proof. A confirmation retains the same event as evidence but
 -- has no cash-event claim and cannot recognize that cash a second time.
 IF event.id IS NOT NULL THEN
  IF event.version<>1 OR event.account_id<>selected_wallet OR event.amount<>amount OR event.verified_by_user_id IS NULL
   OR event.effective_at>clock_timestamp()
   OR btrim(coalesce(event.recipient_attestation,''))='' OR EXISTS(SELECT 1 FROM treasury.event_revisions WHERE event_id=event.id)
   OR (SELECT count(*) FROM treasury.movement_lines WHERE event_id=event.id)<>(CASE WHEN event.fee>0 THEN 2 ELSE 1 END)
   OR NOT EXISTS(SELECT 1 FROM treasury.movement_lines WHERE event_id=event.id AND component='principal'
     AND signed_amount=CASE event.direction WHEN 'credit' THEN event.amount ELSE -event.amount END
     AND account_id=event.account_id AND ledger_context_id=event.ledger_context_id AND effective_at=event.effective_at AND evidence_id=event.evidence_id)
   OR (event.fee>0 AND NOT EXISTS(SELECT 1 FROM treasury.movement_lines WHERE event_id=event.id AND component='fee' AND signed_amount=-event.fee
     AND account_id=event.account_id AND ledger_context_id=event.ledger_context_id AND effective_at=event.effective_at AND evidence_id=event.evidence_id)) THEN
   RAISE EXCEPTION 'Collector source event or exact cash movement evidence changed.' USING ERRCODE='55000';
  END IF;
  source_facts:=source_facts||jsonb_build_object('event',to_jsonb(event),'source_links',(SELECT jsonb_agg(to_jsonb(l) ORDER BY l.id) FROM treasury.source_links l WHERE event_id=event.id),
    'movement_lines',(SELECT jsonb_agg(to_jsonb(l) ORDER BY l.id) FROM treasury.movement_lines l WHERE event_id=event.id));
  evidence:=evidence||jsonb_build_array((SELECT to_jsonb(e) FROM treasury.evidence e WHERE id=event.evidence_id AND account_id=event.account_id AND purpose='recipient'));
 END IF;
 FOREACH selected_wallet IN ARRAY account_ids LOOP
  SELECT * INTO wallet FROM treasury.accounts WHERE id=selected_wallet;
  SELECT * INTO mapping FROM accounting.treasury_cash_mappings WHERE treasury_account_id=selected_wallet
   AND (p_mapping_ids IS NULL OR id=(p_mapping_ids->>selected_wallet::text)::uuid) ORDER BY version DESC LIMIT 1;
  IF mapping.id IS NULL OR mapping.book_id<>book.id OR mapping.ledger_context_id<>wallet.ledger_context_id
   OR (mapping.wallet_snapshot-'active') IS DISTINCT FROM (accounting.treasury_gl_wallet_snapshot(selected_wallet)-'active')
   OR (mapping.cash_snapshot-ARRAY['name','is_active']) IS DISTINCT FROM (accounting.treasury_gl_account_snapshot(mapping.cash_account_id)-ARRAY['name','is_active']) THEN
   RAISE EXCEPTION 'Current reviewed Collector cash mapping is required.' USING ERRCODE='55000';
  END IF;
  mappings:=mappings||jsonb_build_object(selected_wallet::text,mapping.id);
  IF selected_wallet=(CASE WHEN p_kind='settlement' THEN s.account_id WHEN p_kind='recognition' THEN credit.account_id ELSE action.account_id END) THEN cash:=mapping.cash_account_id; END IF;
 END LOOP;
 selected_wallet:=CASE WHEN p_kind='settlement' THEN s.account_id WHEN p_kind='recognition' THEN credit.account_id ELSE action.account_id END;
 IF p_kind IN ('settlement','return_reversal') THEN line_values:=jsonb_build_array(jsonb_build_object('account_id',cash,'debit',amount::text,'credit','0.00'))||line_values;
 ELSIF p_kind='return_debit' THEN line_values:=line_values||jsonb_build_array(jsonb_build_object('account_id',cash,'debit','0.00','credit',(amount+fee)::text)); END IF;
 SELECT jsonb_agg(value||jsonb_build_object('line_number',ordinality,'account_code',a.code,
   'account_snapshot',accounting.treasury_gl_account_snapshot(a.id)-ARRAY['name','is_active']) ORDER BY ordinality)
 INTO lines FROM jsonb_array_elements(line_values) WITH ORDINALITY JOIN accounting.accounts a ON a.id=(value->>'account_id')::uuid;
 IF lines IS NULL OR jsonb_array_length(lines)<2 OR (SELECT sum((value->>'debit')::numeric-(value->>'credit')::numeric) FROM jsonb_array_elements(lines))<>0 THEN
  RAISE EXCEPTION 'Exact balanced Collector journal coordinates are required.' USING ERRCODE='55000'; END IF;
 SELECT jsonb_agg(value ORDER BY value->>'id') INTO evidence FROM (SELECT DISTINCT value FROM jsonb_array_elements(evidence)) retained;
 IF evidence IS NULL OR EXISTS(SELECT 1 FROM jsonb_array_elements(evidence) e WHERE e='null'::jsonb
  OR NOT e ?& ARRAY['id','sha256','byte_count'] OR e->>'byte_count' IS NULL OR (e->>'byte_count')::bigint<=0
  OR e->>'sha256' IS NULL OR e->>'sha256' !~ '^[0-9a-f]{64}$') THEN
  RAISE EXCEPTION 'Retained private Collector evidence is required.' USING ERRCODE='55000'; END IF;
 SELECT * INTO period FROM accounting.fiscal_periods WHERE day BETWEEN start_date AND end_date;
 IF period.id IS NULL OR day IS NULL OR day>(clock_timestamp() AT TIME ZONE 'Asia/Manila')::date
  OR amount IS NULL OR amount<=0 OR fee IS NULL OR fee<0 THEN
  RAISE EXCEPTION 'Collector evidence requires an actual positive amount and dated fiscal period.' USING ERRCODE='55000'; END IF;
 RETURN jsonb_build_object('book_id',book.id,'source_kind',p_kind,'source_id',p_source,'treasury_account_id',selected_wallet,
  'account_ids',to_jsonb(account_ids),'collector_user_id',collector,'fiscal_period_id',period.id,'posting_date',day,
  'amount',amount::numeric(18,2)::text,'fee',fee::numeric(18,2)::text,'cash_event_id',CASE WHEN p_kind IN ('settlement','return_debit','return_reversal') THEN event.id END,
  'mapping_ids',mappings,'source_facts',source_facts,'prerequisites',prerequisites,'evidence',evidence,'lines',lines);
END $$;

CREATE OR REPLACE FUNCTION accounting.collector_liability_is_current(p_preparation UUID)
RETURNS BOOLEAN LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE prepared accounting.collector_liability_preparations%ROWTYPE;
BEGIN
 SELECT * INTO prepared FROM accounting.collector_liability_preparations WHERE id=p_preparation;
 IF NOT FOUND THEN RETURN false; END IF;
 RETURN accounting.collector_liability_origin(prepared.source_kind,prepared.source_id,prepared.snapshot->'mapping_ids')=prepared.snapshot;
EXCEPTION WHEN OTHERS THEN
 -- Invalid current source evidence is a blocker. Historical audit remains
 -- visible, and no operational money writer is rejected by this read function.
 RETURN false;
END $$;

CREATE OR REPLACE VIEW accounting.collector_liability_posting_status AS
SELECT posted.id,posted.preparation_id,posted.source_kind,posted.source_id,posted.event_id,
 posted.book_id,posted.account_id,posted.collector_user_id,posted.journal_entry_id,posted.source_digest,
 (prepared.snapshot->>'posting_date')::date AS posting_date,(prepared.snapshot->>'amount')::numeric AS amount,
 (posted.source_kind=prepared.source_kind AND posted.source_id=prepared.source_id AND posted.book_id=prepared.book_id
  AND posted.account_id=prepared.account_id AND posted.collector_user_id=prepared.collector_user_id
  AND posted.source_digest=prepared.source_digest AND posted.actor_user_id=prepared.actor_user_id
  AND posted.event_id IS NOT DISTINCT FROM (prepared.snapshot->>'cash_event_id')::uuid
  AND journal.status='posted' AND journal.source_type='collector_liability'
  AND journal.source_event_key='collector_liability:'||prepared.source_kind||':'||prepared.source_id::text
  AND journal.source_reference=prepared.source_id::text AND journal.reversal_of_entry_id IS NULL
  AND journal.posting_date=(prepared.snapshot->>'posting_date')::date
  AND journal.fiscal_period_id=(prepared.snapshot->>'fiscal_period_id')::uuid
  AND journal.created_by_user_id=prepared.actor_user_id AND journal.posted_by_user_id=prepared.actor_user_id
  AND (SELECT count(*) FROM accounting.journal_lines WHERE journal_entry_id=journal.id)=jsonb_array_length(prepared.snapshot->'lines')
  AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(prepared.snapshot->'lines') retained
   LEFT JOIN accounting.journal_lines actual ON actual.journal_entry_id=journal.id AND actual.line_number=(retained->>'line_number')::integer
   WHERE actual.id IS NULL OR actual.account_id IS DISTINCT FROM (retained->>'account_id')::uuid
    OR actual.debit IS DISTINCT FROM (retained->>'debit')::numeric OR actual.credit IS DISTINCT FROM (retained->>'credit')::numeric
    OR actual.client_id IS NOT NULL OR actual.loan_id IS NOT NULL)) AS exact_posted,
 NOT accounting.collector_liability_is_current(prepared.id) AS correction_pending
FROM accounting.collector_liability_postings posted
JOIN accounting.collector_liability_preparations prepared ON prepared.id=posted.preparation_id
JOIN accounting.journal_entries journal ON journal.id=posted.journal_entry_id;

CREATE OR REPLACE FUNCTION accounting.lock_collector_liability_sources()
RETURNS VOID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF current_setting('transaction_isolation')<>'read committed' THEN
  RAISE EXCEPTION 'Collector accounting requires READ COMMITTED.' USING ERRCODE='55000'; END IF;
 LOCK TABLE lending.collection_remittances,lending.collection_remittance_items,lending.collection_transactions,
  lending.collection_remittance_refund_due_release_items,accounting.accounts,accounting.fiscal_periods,
  accounting.regular_journal_draft_preparations,accounting.regular_journal_draft_preparation_entries,
  accounting.regular_journal_posting_sets,accounting.regular_journal_posting_entries,
  accounting.seven_by_seven_journal_postings,accounting.seven_by_seven_journal_posting_lines,
  accounting.remittance_transfer_journal_preparations,accounting.remittance_transfer_journal_postings,
  treasury.collector_counts,treasury.collector_settlements,treasury.collector_cases,treasury.collector_credits,
  treasury.collector_entries,treasury.collector_resolutions,treasury.collector_actions,treasury.collector_acknowledgments,
  treasury.collector_exceptions,treasury.evidence,treasury.events,treasury.event_revisions,treasury.movement_lines,treasury.source_links,
  accounting.treasury_cash_mappings
 IN SHARE MODE;
 LOCK TABLE accounting.journal_entries,accounting.journal_lines,
  accounting.collector_liability_preparations,accounting.collector_liability_postings IN SHARE ROW EXCLUSIVE MODE;
END $$;

CREATE OR REPLACE FUNCTION accounting.collector_liability_coordinates(p_kind TEXT,p_source UUID)
RETURNS JSONB LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE result JSONB; wallet UUID; item RECORD;
BEGIN
 FOREACH wallet IN ARRAY accounting.collector_liability_accounts(p_kind,p_source) LOOP
  PERFORM 1 FROM treasury.accounts WHERE id=wallet FOR UPDATE;
  PERFORM accounting.require_book_treasury_account(wallet);
 END LOOP;
 PERFORM accounting.lock_collector_liability_sources();
 result:=accounting.collector_liability_origin(p_kind,p_source);
 IF NOT EXISTS(SELECT 1 FROM accounting.fiscal_periods WHERE id=(result->>'fiscal_period_id')::uuid AND status='open') THEN
  RAISE EXCEPTION 'New Collector accounting requires an open source period.' USING ERRCODE='55000'; END IF;
 IF EXISTS(SELECT 1 FROM jsonb_array_elements(result->'lines') line JOIN accounting.accounts account ON account.id=(line->>'account_id')::uuid WHERE NOT account.is_active) THEN
  RAISE EXCEPTION 'New Collector accounting requires active chart accounts.' USING ERRCODE='55000'; END IF;
 RETURN result||jsonb_build_object('source_digest',encode(sha256(convert_to(result::text,'UTF8')),'hex'));
END $$;

CREATE OR REPLACE FUNCTION accounting.prepare_collector_liability(p_kind TEXT,p_source UUID,p_digest TEXT,p_request UUID,p_actor UUID)
RETURNS UUID LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE existing accounting.collector_liability_preparations%ROWTYPE; source JSONB; created UUID; old_setting TEXT;
BEGIN
 PERFORM accounting.require_collector_liability_actor(p_actor,p_kind,p_source);
 IF p_request IS NULL OR p_digest IS NULL OR p_digest !~ '^[0-9a-f]{64}$' THEN
  RAISE EXCEPTION 'Exact Collector accounting request and reviewed digest are required.' USING ERRCODE='22023'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('collector-accounting-request:'||p_request::text,0));
 SELECT * INTO existing FROM accounting.collector_liability_preparations WHERE request_id=p_request;
 IF FOUND THEN
  IF (existing.source_kind,existing.source_id,existing.source_digest,existing.actor_user_id) IS NOT DISTINCT FROM (p_kind,p_source,p_digest,p_actor) THEN RETURN existing.id; END IF;
  RAISE EXCEPTION 'Collector preparation retry conflicts with its retained review.' USING ERRCODE='55000';
 END IF;
 source:=accounting.collector_liability_coordinates(p_kind,p_source);
 IF source->>'source_digest' IS DISTINCT FROM p_digest THEN RAISE EXCEPTION 'Collector source review changed.' USING ERRCODE='55000'; END IF;
 IF EXISTS(SELECT 1 FROM accounting.collector_liability_postings WHERE source_kind=p_kind AND source_id=p_source) THEN
  RAISE EXCEPTION 'Collector source accounting is already posted.' USING ERRCODE='55000'; END IF;
 old_setting:=current_setting('accounting.treasury_gl_write',true);
 PERFORM set_config('accounting.treasury_gl_write','collector_liability_preparations',true);
 INSERT INTO accounting.collector_liability_preparations(request_id,source_kind,source_id,book_id,account_id,collector_user_id,source_digest,confirmation_token,snapshot,actor_user_id)
 VALUES(p_request,p_kind,p_source,(source->>'book_id')::uuid,(source->>'treasury_account_id')::uuid,(source->>'collector_user_id')::uuid,
  p_digest,encode(sha256(convert_to(gen_random_uuid()::text||p_digest,'UTF8')),'hex'),source-'source_digest',p_actor) RETURNING id INTO created;
 PERFORM set_config('accounting.treasury_gl_write',coalesce(old_setting,''),true);
 RETURN created;
END $$;

CREATE OR REPLACE FUNCTION accounting.guard_collector_liability_journal()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE prepared accounting.collector_liability_preparations%ROWTYPE; related UUID;
BEGIN
 IF TG_OP<>'DELETE' AND NEW.reversal_of_entry_id IS NOT NULL AND EXISTS(SELECT 1 FROM accounting.journal_entries WHERE id=NEW.reversal_of_entry_id AND source_type='collector_liability') THEN
  RAISE EXCEPTION 'Collector cash correction requires actual protected source evidence.' USING ERRCODE='55000'; END IF;
 IF TG_OP<>'DELETE' AND (NEW.source_type='remittance_transfer' OR NEW.source_event_key LIKE 'remittance_transfer:%')
   AND EXISTS(SELECT 1 FROM accounting.collector_liability_postings posted JOIN accounting.collector_liability_preparations p ON p.id=posted.preparation_id
    WHERE posted.source_kind='settlement' AND p.snapshot#>>'{source_facts,remittance_id}'=NEW.source_reference) THEN
  RAISE EXCEPTION 'Collector counted cash already has its protected transfer journal.' USING ERRCODE='55000'; END IF;
 IF (TG_OP<>'INSERT' AND (OLD.source_type='collector_liability' OR OLD.source_event_key LIKE 'collector_liability:%'))
  OR (TG_OP<>'DELETE' AND (NEW.source_type='collector_liability' OR NEW.source_event_key LIKE 'collector_liability:%')) THEN
  IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Collector journals cannot be deleted.' USING ERRCODE='55000'; END IF;
  SELECT * INTO prepared FROM accounting.collector_liability_preparations WHERE id=nullif(current_setting('accounting.collector_liability_post',true),'')::uuid;
  IF prepared.id IS NULL OR NEW.source_type<>'collector_liability'
   OR NEW.source_event_key<>'collector_liability:'||prepared.source_kind||':'||prepared.source_id::text
   OR NEW.source_reference<>prepared.source_id::text OR NEW.reversal_of_entry_id IS NOT NULL
   OR NEW.fiscal_period_id<>(prepared.snapshot->>'fiscal_period_id')::uuid
   OR NEW.posting_date<>(prepared.snapshot->>'posting_date')::date OR NEW.created_by_user_id<>prepared.actor_user_id THEN
   RAISE EXCEPTION 'Collector journals require their exact protected preparation.' USING ERRCODE='55000'; END IF;
 END IF;
 RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
END $$;
DROP TRIGGER IF EXISTS accounting_00_collector_liability_journal_guard ON accounting.journal_entries;
CREATE TRIGGER accounting_00_collector_liability_journal_guard BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_collector_liability_journal();

CREATE OR REPLACE FUNCTION accounting.assert_collector_liability_audit()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE journal UUID;
BEGIN
 IF TG_TABLE_NAME='journal_entries' THEN
  IF NEW.source_type IS DISTINCT FROM 'collector_liability' AND coalesce(NEW.source_event_key,'') NOT LIKE 'collector_liability:%' THEN RETURN NEW; END IF;
  journal:=NEW.id;
 ELSE journal:=NEW.journal_entry_id; END IF;
 IF NOT EXISTS(SELECT 1 FROM accounting.collector_liability_posting_status WHERE journal_entry_id=journal AND exact_posted) THEN
  RAISE EXCEPTION 'Collector journal requires exact posted immutable audit and lines.' USING ERRCODE='55000'; END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS collector_liability_journal_audit ON accounting.journal_entries;
CREATE CONSTRAINT TRIGGER collector_liability_journal_audit AFTER INSERT OR UPDATE ON accounting.journal_entries
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION accounting.assert_collector_liability_audit();
DROP TRIGGER IF EXISTS collector_liability_posting_audit ON accounting.collector_liability_postings;
CREATE CONSTRAINT TRIGGER collector_liability_posting_audit AFTER INSERT ON accounting.collector_liability_postings
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION accounting.assert_collector_liability_audit();

CREATE OR REPLACE FUNCTION accounting.post_collector_liability(p_preparation UUID,p_digest TEXT,p_token TEXT,p_actor UUID)
RETURNS UUID LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE prepared accounting.collector_liability_preparations%ROWTYPE; existing accounting.collector_liability_postings%ROWTYPE;
 source JSONB; created UUID; old_setting TEXT; old_write TEXT; retained_wallet TEXT;
BEGIN
 SELECT * INTO prepared FROM accounting.collector_liability_preparations WHERE id=p_preparation;
 IF NOT FOUND THEN RAISE EXCEPTION 'Private Collector preparation is unavailable.' USING ERRCODE='42501'; END IF;
 PERFORM accounting.require_collector_liability_actor(p_actor,prepared.source_kind,prepared.source_id);
 FOR retained_wallet IN SELECT jsonb_array_elements_text(prepared.snapshot->'account_ids') LOOP
  PERFORM accounting.require_treasury_gl_actor(p_actor,retained_wallet::uuid,'treasury.view');
  PERFORM accounting.require_treasury_gl_actor(p_actor,retained_wallet::uuid,'treasury.collector_surplus.view');
 END LOOP;
 IF prepared.actor_user_id IS DISTINCT FROM p_actor OR prepared.source_digest IS DISTINCT FROM p_digest OR prepared.confirmation_token IS DISTINCT FROM p_token THEN
  RAISE EXCEPTION 'Collector confirmation must match the exact prepared actor, digest and token.' USING ERRCODE='55000'; END IF;
 SELECT * INTO existing FROM accounting.collector_liability_postings WHERE source_kind=prepared.source_kind AND source_id=prepared.source_id;
 IF FOUND THEN
  IF existing.preparation_id=prepared.id AND EXISTS(SELECT 1 FROM accounting.collector_liability_posting_status WHERE id=existing.id AND exact_posted) THEN RETURN existing.journal_entry_id; END IF;
  RAISE EXCEPTION 'Collector source was posted by a different retained review.' USING ERRCODE='55000'; END IF;
 source:=accounting.collector_liability_coordinates(prepared.source_kind,prepared.source_id);
 IF source->>'source_digest' IS DISTINCT FROM prepared.source_digest OR source-'source_digest' IS DISTINCT FROM prepared.snapshot THEN
  RAISE EXCEPTION 'Collector source changed after review; prepare current evidence.' USING ERRCODE='55000'; END IF;
 old_setting:=current_setting('accounting.collector_liability_post',true); old_write:=current_setting('accounting.treasury_gl_write',true);
 PERFORM set_config('accounting.collector_liability_post',prepared.id::text,true);
 INSERT INTO accounting.journal_entries(fiscal_period_id,posting_date,description,source_type,source_reference,source_event_key,created_by_user_id)
 VALUES((source->>'fiscal_period_id')::uuid,(source->>'posting_date')::date,'Reviewed Collector cash and liability evidence','collector_liability',prepared.source_id::text,
  'collector_liability:'||prepared.source_kind||':'||prepared.source_id::text,p_actor) RETURNING id INTO created;
 INSERT INTO accounting.journal_lines(journal_entry_id,line_number,account_id,description,debit,credit)
 SELECT created,(line->>'line_number')::integer,(line->>'account_id')::uuid,'Retained Collector source effect',(line->>'debit')::numeric,(line->>'credit')::numeric
 FROM jsonb_array_elements(source->'lines') line;
 PERFORM accounting.post_journal_entry(created,p_actor);
 PERFORM set_config('accounting.treasury_gl_write','collector_liability_postings',true);
 INSERT INTO accounting.collector_liability_postings(preparation_id,source_kind,source_id,event_id,book_id,account_id,collector_user_id,journal_entry_id,source_digest,actor_user_id)
 VALUES(prepared.id,prepared.source_kind,prepared.source_id,(source->>'cash_event_id')::uuid,prepared.book_id,prepared.account_id,prepared.collector_user_id,created,p_digest,p_actor);
 IF NOT EXISTS(SELECT 1 FROM accounting.collector_liability_posting_status WHERE journal_entry_id=created AND exact_posted) THEN
  RAISE EXCEPTION 'Collector posted lines do not match retained audit.' USING ERRCODE='55000'; END IF;
 PERFORM set_config('accounting.collector_liability_post',coalesce(old_setting,''),true);
 PERFORM set_config('accounting.treasury_gl_write',coalesce(old_write,''),true);
 RETURN created;
END $$;

-- A retained draft and its completed journal are both protected. In particular,
-- a zero-net pair of unregistered control lines is never considered reconciled.
CREATE OR REPLACE FUNCTION accounting.guard_collector_liability_lines()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE journal UUID;
BEGIN
 IF TG_OP='TRUNCATE' THEN
  IF EXISTS(SELECT 1 FROM accounting.collector_liability_postings) THEN
   RAISE EXCEPTION 'Collector accounting journals and lines cannot be truncated.' USING ERRCODE='55000'; END IF;
  RETURN NULL;
 END IF;
 journal:=CASE WHEN TG_OP='DELETE' THEN OLD.journal_entry_id ELSE NEW.journal_entry_id END;
 IF EXISTS(SELECT 1 FROM accounting.journal_entries WHERE id=journal AND source_type='collector_liability')
  OR (TG_OP='UPDATE' AND EXISTS(SELECT 1 FROM accounting.journal_entries WHERE id=OLD.journal_entry_id AND source_type='collector_liability')) THEN
  IF TG_OP<>'INSERT' OR NOT EXISTS(SELECT 1 FROM accounting.journal_entries j
    JOIN accounting.collector_liability_preparations p ON p.id=nullif(current_setting('accounting.collector_liability_post',true),'')::uuid
    CROSS JOIN LATERAL jsonb_array_elements(p.snapshot->'lines') line
    WHERE j.id=journal AND j.status='draft' AND j.source_event_key='collector_liability:'||p.source_kind||':'||p.source_id::text
     AND NEW.line_number=(line->>'line_number')::integer AND NEW.account_id=(line->>'account_id')::uuid
     AND NEW.debit=(line->>'debit')::numeric AND NEW.credit=(line->>'credit')::numeric
     AND NEW.client_id IS NULL AND NEW.loan_id IS NULL) THEN
   RAISE EXCEPTION 'Collector journal lines require their exact protected source.' USING ERRCODE='55000'; END IF;
 END IF;
 RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
END $$;
DROP TRIGGER IF EXISTS collector_liability_lines_guard ON accounting.journal_lines;
CREATE TRIGGER collector_liability_lines_guard BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_lines
FOR EACH ROW EXECUTE FUNCTION accounting.guard_collector_liability_lines();
DROP TRIGGER IF EXISTS collector_liability_lines_truncate ON accounting.journal_lines;
CREATE TRIGGER collector_liability_lines_truncate BEFORE TRUNCATE ON accounting.journal_lines
FOR EACH STATEMENT EXECUTE FUNCTION accounting.guard_collector_liability_lines();
DROP TRIGGER IF EXISTS collector_liability_journals_truncate ON accounting.journal_entries;
CREATE TRIGGER collector_liability_journals_truncate BEFORE TRUNCATE ON accounting.journal_entries
FOR EACH STATEMENT EXECUTE FUNCTION accounting.guard_collector_liability_lines();

CREATE OR REPLACE FUNCTION accounting.collector_source_exact(p_type TEXT,p_source UUID,p_cutoff DATE)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT EXISTS(SELECT 1 FROM accounting.collector_liability_posting_status status
 JOIN accounting.collector_liability_preparations prepared ON prepared.id=status.preparation_id
 WHERE status.exact_posted AND NOT status.correction_pending AND status.posting_date<=p_cutoff AND CASE p_type
  WHEN 'treasury_event' THEN status.event_id=p_source
  WHEN 'collector_settlement' THEN status.source_kind='settlement' AND status.source_id=p_source
  WHEN 'collector_case' THEN status.source_kind='settlement' AND prepared.snapshot#>>'{source_facts,case_id}'=p_source::text
  WHEN 'collector_credit' THEN status.source_kind='recognition' AND prepared.snapshot#>>'{source_facts,credit_id}'=p_source::text
  WHEN 'collector_resolution' THEN status.source_kind='recognition' AND prepared.snapshot#>>'{source_facts,resolution,id}'=p_source::text
  WHEN 'collector_entry' THEN status.source_kind IN ('recognition','return_confirmation','return_reversal') AND status.source_id=p_source
  WHEN 'collector_return_debit' THEN status.source_kind='return_debit' AND status.source_id=p_source
  WHEN 'remittance_transfer' THEN status.source_kind='settlement' AND prepared.snapshot#>>'{source_facts,remittance_id}'=p_source::text
  ELSE false END);
$$;

-- Raw control movements use actual source dates, never today's mutable
-- outstanding balance. Missing or unsupported source proof remains a blocker.
CREATE OR REPLACE FUNCTION accounting.collector_control_movements()
RETURNS TABLE(account_code TEXT,effective_date DATE,signed_amount NUMERIC,source_type TEXT,source_id UUID,account_id UUID)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT '2210'::text,(coalesce(event.effective_at,(opening.payload->>'cutoff')::timestamptz,item.created_at) AT TIME ZONE 'Asia/Manila')::date,
  -(item.payload->>'received_excess_amount')::numeric,'collector_case'::text,item.id,item.account_id
 FROM treasury.collector_cases item LEFT JOIN treasury.collector_settlements settlement ON settlement.id=item.settlement_id
 LEFT JOIN treasury.events event ON event.id=settlement.event_id LEFT JOIN treasury.collector_openings opening ON opening.id=item.opening_anchor_id
 UNION ALL
 SELECT '2210',(created_at AT TIME ZONE 'Asia/Manila')::date,(payload->>'amount')::numeric,'collector_resolution',id,account_id
 FROM treasury.collector_resolutions
 UNION ALL
 SELECT '2220',(coalesce((opening.payload->>'cutoff')::timestamptz,credit.created_at) AT TIME ZONE 'Asia/Manila')::date,
  -(credit.payload->>'recognized_amount')::numeric,'collector_credit',credit.id,credit.account_id
 FROM treasury.collector_credits credit LEFT JOIN treasury.collector_openings opening ON opening.id=credit.opening_anchor_id
 UNION ALL
 SELECT '1060',(event.effective_at AT TIME ZONE 'Asia/Manila')::date,event.amount,'collector_return_debit',action.id,action.account_id
 FROM treasury.collector_actions action JOIN treasury.events event ON event.id=action.event_id WHERE action.payload->>'kind'='return'
 UNION ALL
 SELECT role.code,(coalesce((ack.payload->>'acknowledged_at')::timestamptz,entry.created_at) AT TIME ZONE 'Asia/Manila')::date,
  role.sign*(entry.payload->>'amount')::numeric,'collector_entry',entry.id,entry.account_id
 FROM treasury.collector_entries entry JOIN treasury.collector_actions action ON action.id=(entry.payload->>'action_id')::uuid
 LEFT JOIN treasury.collector_acknowledgments ack ON ack.id=(action.payload->>'acknowledgment_id')::uuid
 CROSS JOIN (VALUES('2220',1),('1060',-1)) role(code,sign) WHERE entry.payload->>'kind'='return'
 UNION ALL
 SELECT '2220',(coalesce(event.effective_at,entry.created_at) AT TIME ZONE 'Asia/Manila')::date,
  -(entry.payload->>'amount')::numeric,'collector_entry',entry.id,entry.account_id
 FROM treasury.collector_entries entry LEFT JOIN treasury.events event ON event.id=(entry.payload->>'incoming_event_id')::uuid
 WHERE entry.payload->>'kind'='return_reversal';
$$;

CREATE OR REPLACE FUNCTION accounting.collector_control_reconciliation(p_cutoff DATE)
RETURNS TABLE(account_code TEXT,source_balance NUMERIC,ledger_balance NUMERIC,difference NUMERIC,unregistered_line_count BIGINT)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 WITH raw AS (SELECT m.account_code,sum(m.signed_amount) amount FROM accounting.collector_control_movements() m WHERE m.effective_date<=p_cutoff GROUP BY m.account_code),
 ledger AS (SELECT a.code,sum(l.debit-l.credit) amount,count(*) FILTER(WHERE NOT EXISTS(
   SELECT 1 FROM accounting.collector_liability_posting_status p WHERE p.journal_entry_id=j.id AND p.exact_posted)) unregistered
  FROM accounting.accounts a JOIN accounting.journal_lines l ON l.account_id=a.id JOIN accounting.journal_entries j ON j.id=l.journal_entry_id
  WHERE a.code IN ('1060','2210','2220') AND j.status='posted' AND j.posting_date<=p_cutoff GROUP BY a.code)
 SELECT role.code,coalesce(raw.amount,0),coalesce(ledger.amount,0),coalesce(ledger.amount,0)-coalesce(raw.amount,0),coalesce(ledger.unregistered,0)
 FROM (VALUES('1060'),('2210'),('2220')) role(code) LEFT JOIN raw ON raw.account_code=role.code LEFT JOIN ledger ON ledger.code=role.code;
$$;

CREATE OR REPLACE FUNCTION accounting.period_collector_control_blockers(p_period UUID)
RETURNS TABLE(source_type TEXT,source_id UUID,effective_date DATE,amount NUMERIC(18,2),reason TEXT,account_id UUID)
LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT DISTINCT m.source_type,m.source_id,m.effective_date,abs(m.signed_amount)::numeric(18,2),
  'collector_exact_source_proof_required'::text,m.account_id
 FROM accounting.fiscal_periods period CROSS JOIN LATERAL accounting.collector_control_movements() m
 WHERE period.id=p_period AND m.effective_date<=period.end_date AND NOT accounting.collector_source_exact(m.source_type,m.source_id,period.end_date)
 UNION ALL
 SELECT 'collector_control',a.id,period.end_date,r.difference::numeric(18,2),
  CASE WHEN r.unregistered_line_count>0 THEN 'collector_control_lines_unregistered' ELSE 'collector_control_balance_difference' END,NULL::uuid
 FROM accounting.fiscal_periods period CROSS JOIN LATERAL accounting.collector_control_reconciliation(period.end_date) r
 JOIN accounting.accounts a ON a.code=r.account_code WHERE period.id=p_period AND (r.difference<>0 OR r.unregistered_line_count>0)
 UNION ALL
 SELECT 'collector_accounting_correction',p.source_id,p.posting_date,p.amount::numeric(18,2),'collector_posted_source_changed',p.account_id
 FROM accounting.fiscal_periods period JOIN accounting.collector_liability_posting_status p ON p.posting_date<=period.end_date
 WHERE period.id=p_period AND (NOT p.exact_posted OR p.correction_pending);
$$;

DO $$ BEGIN
 IF to_regprocedure('accounting.period_initial_before_collector_blockers(uuid)') IS NULL THEN
  ALTER FUNCTION accounting.period_initial_source_blockers(UUID) RENAME TO period_initial_before_collector_blockers;
 END IF;
 IF to_regprocedure('accounting.period_legacy_before_collector_blockers(uuid)') IS NULL THEN
  ALTER FUNCTION accounting.period_legacy_source_blockers(UUID) RENAME TO period_legacy_before_collector_blockers;
 END IF;
END $$;
CREATE OR REPLACE FUNCTION accounting.period_initial_source_blockers(p_period UUID)
RETURNS TABLE(source_type TEXT,source_id UUID,effective_date DATE,amount NUMERIC(18,2),reason TEXT,account_id UUID)
LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT b.* FROM accounting.period_initial_before_collector_blockers(p_period) b
 CROSS JOIN accounting.fiscal_periods period WHERE period.id=p_period
  AND NOT accounting.collector_source_exact(b.source_type,b.source_id,period.end_date)
  -- A return's immutable acknowledgment determines liability discharge; the
  -- original initial inventory conservatively used its earlier debit date.
  AND NOT (b.source_type='collector_entry' AND EXISTS(SELECT 1 FROM treasury.collector_entries e
    JOIN treasury.collector_actions a ON a.id=(e.payload->>'action_id')::uuid
    JOIN treasury.collector_acknowledgments ack ON ack.id=(a.payload->>'acknowledgment_id')::uuid
    WHERE e.id=b.source_id AND e.payload->>'kind'='return' AND
     ((ack.payload->>'acknowledged_at')::timestamptz AT TIME ZONE 'Asia/Manila')::date>period.end_date))
 UNION ALL SELECT * FROM accounting.period_collector_control_blockers(p_period);
$$;
CREATE OR REPLACE FUNCTION accounting.period_legacy_source_blockers(p_period UUID)
RETURNS TABLE(source_type TEXT,source_id UUID,effective_date DATE,amount NUMERIC(18,2),reason TEXT,account_id UUID)
LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT b.* FROM accounting.period_legacy_before_collector_blockers(p_period) b CROSS JOIN accounting.fiscal_periods period
 WHERE period.id=p_period AND NOT (b.source_type='remittance_transfer' AND accounting.collector_source_exact(b.source_type,b.source_id,period.end_date));
$$;

-- Extend 0151 without changing its public source-plus-manifest union. The
-- optional branch also permits isolated adapter tests against the 0149 base.
DO $$ BEGIN
 IF to_regprocedure('accounting.period_review_additional_evidence(uuid)') IS NOT NULL THEN
  IF to_regprocedure('accounting.period_review_before_collector_evidence(uuid)') IS NULL THEN
   ALTER FUNCTION accounting.period_review_additional_evidence(UUID) RENAME TO period_review_before_collector_evidence;
  END IF;
  EXECUTE $fn$CREATE OR REPLACE FUNCTION accounting.period_review_additional_evidence(p_period UUID)
   RETURNS JSONB LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $body$
   SELECT accounting.period_review_before_collector_evidence(p_period)||CASE WHEN count(p.id)=0 THEN '{}'::jsonb ELSE
    jsonb_build_object('collector_liability',jsonb_agg(jsonb_build_object('posting',to_jsonb(p),'preparation',to_jsonb(prepared)) ORDER BY p.id)) END
   FROM accounting.collector_liability_postings p JOIN accounting.collector_liability_preparations prepared ON prepared.id=p.preparation_id
   JOIN accounting.fiscal_periods period ON period.id=p_period WHERE (prepared.snapshot->>'posting_date')::date<=period.end_date
   $body$ $fn$;
  IF to_regprocedure('accounting.lock_period_review_before_collector_sources()') IS NULL THEN
   ALTER FUNCTION accounting.lock_period_review_additional_sources() RENAME TO lock_period_review_before_collector_sources;
  END IF;
  EXECUTE $fn$CREATE OR REPLACE FUNCTION accounting.lock_period_review_additional_sources()
   RETURNS VOID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $body$
   BEGIN
    PERFORM accounting.lock_period_review_before_collector_sources();
    LOCK TABLE accounting.collector_liability_preparations,accounting.collector_liability_postings,
     treasury.collector_acknowledgments,treasury.collector_exceptions IN SHARE MODE;
   END $body$ $fn$;
 END IF;
END $$;

DO $$ DECLARE role_name TEXT; item RECORD; BEGIN
 FOREACH role_name IN ARRAY ARRAY['PUBLIC','anon','authenticated','service_role'] LOOP
  IF role_name='PUBLIC' OR EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
   FOR item IN SELECT oid::regprocedure::text signature FROM pg_proc WHERE pronamespace='accounting'::regnamespace
    AND (proname LIKE '%collector%' OR proname IN ('period_initial_source_blockers','period_legacy_source_blockers',
     'period_review_additional_evidence','lock_period_review_additional_sources')) LOOP
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM %s',item.signature,CASE WHEN role_name='PUBLIC' THEN 'PUBLIC' ELSE quote_ident(role_name) END);
   END LOOP;
   EXECUTE format('REVOKE ALL ON accounting.collector_liability_preparations,accounting.collector_liability_postings,accounting.collector_liability_posting_status FROM %s',
    CASE WHEN role_name='PUBLIC' THEN 'PUBLIC' ELSE quote_ident(role_name) END);
  END IF;
 END LOOP;
END $$;
COMMIT;
