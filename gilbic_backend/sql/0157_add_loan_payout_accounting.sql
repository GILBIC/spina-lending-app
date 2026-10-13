BEGIN;

-- Cash leaves on the actual debit. A loan receivable arises only at the
-- separately protected borrower completion; neither preparation nor Collector
-- acknowledgment substitutes for that completion. The 0139 guard is unchanged.
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM accounting.accounts WHERE (code='1050' OR system_key='loan_disbursement_transit')
  AND NOT(code='1050' AND system_key='loan_disbursement_transit'
   AND account_type='asset' AND normal_balance='debit' AND is_posting)) THEN
  RAISE EXCEPTION 'Loan disbursement transit conflicts with an existing chart definition.';
 END IF;
 INSERT INTO accounting.accounts(code,system_key,name,account_type,normal_balance)
 VALUES('1050','loan_disbursement_transit','Loan Disbursement Transit','asset','debit') ON CONFLICT(system_key) DO NOTHING;
END $$;

CREATE OR REPLACE FUNCTION accounting.guard_loan_payout_transit_definition()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF OLD.code='1050' OR OLD.system_key='loan_disbursement_transit' THEN
  IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Transit control definitions are immutable; retire the account instead.'; END IF;
  IF ROW(NEW.id,NEW.code,NEW.system_key,NEW.account_type,NEW.normal_balance,NEW.is_posting)
   IS DISTINCT FROM ROW(OLD.id,OLD.code,OLD.system_key,OLD.account_type,OLD.normal_balance,OLD.is_posting) THEN
   RAISE EXCEPTION 'Transit control definitions are immutable; only display name and active status may change.';
  END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS loan_payout_transit_definition ON accounting.accounts;
CREATE TRIGGER loan_payout_transit_definition BEFORE UPDATE OR DELETE ON accounting.accounts
FOR EACH ROW EXECUTE FUNCTION accounting.guard_loan_payout_transit_definition();
REVOKE ALL ON FUNCTION accounting.guard_loan_payout_transit_definition() FROM PUBLIC;
DO $$ DECLARE r TEXT; BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN EXECUTE format('REVOKE ALL ON FUNCTION accounting.guard_loan_payout_transit_definition() FROM %I',r); END IF;
 END LOOP;
END $$;


CREATE TABLE IF NOT EXISTS accounting.loan_payout_accounting_preparations (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),request_id UUID NOT NULL UNIQUE,
 payout_id UUID NOT NULL REFERENCES treasury.loan_payouts(id),stage TEXT NOT NULL CHECK(stage IN('debit','completion')),
 event_id UUID NOT NULL REFERENCES treasury.events(id),disbursement_event_id UUID REFERENCES lending.loan_disbursement_events(id),
 treasury_account_id UUID NOT NULL REFERENCES treasury.accounts(id),book_id UUID NOT NULL REFERENCES accounting.book_identity(id),
 loan_id UUID NOT NULL REFERENCES lending.loans(id),client_id UUID NOT NULL REFERENCES lending.clients(id),
 mapping_id UUID NOT NULL REFERENCES accounting.treasury_cash_mappings(id),
 source_digest TEXT NOT NULL CHECK(source_digest ~ '^[0-9a-f]{64}$'),confirmation_token TEXT NOT NULL CHECK(confirmation_token ~ '^[0-9a-f]{64}$'),
 snapshot JSONB NOT NULL,actor_user_id UUID NOT NULL REFERENCES core.users(id),created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
 CHECK((stage='debit' AND disbursement_event_id IS NULL) OR (stage='completion' AND disbursement_event_id IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS accounting.loan_payout_accounting_postings (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),preparation_id UUID NOT NULL UNIQUE REFERENCES accounting.loan_payout_accounting_preparations(id),
 payout_id UUID NOT NULL REFERENCES treasury.loan_payouts(id),stage TEXT NOT NULL CHECK(stage IN('debit','completion')),
 event_id UUID NOT NULL REFERENCES treasury.events(id),disbursement_event_id UUID UNIQUE REFERENCES lending.loan_disbursement_events(id),
 treasury_account_id UUID NOT NULL REFERENCES treasury.accounts(id),book_id UUID NOT NULL REFERENCES accounting.book_identity(id),
 loan_id UUID NOT NULL REFERENCES lending.loans(id),client_id UUID NOT NULL REFERENCES lending.clients(id),
 journal_entry_id UUID NOT NULL UNIQUE REFERENCES accounting.journal_entries(id),amount NUMERIC(18,2) NOT NULL CHECK(amount>0),
 fee NUMERIC(18,2) NOT NULL CHECK(fee>=0 AND (stage='debit' OR fee=0)),source_digest TEXT NOT NULL CHECK(source_digest ~ '^[0-9a-f]{64}$'),
 actor_user_id UUID NOT NULL REFERENCES core.users(id),created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),UNIQUE(payout_id,stage),
 CHECK((stage='debit' AND disbursement_event_id IS NULL) OR (stage='completion' AND disbursement_event_id IS NOT NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS loan_payout_debit_event_once ON accounting.loan_payout_accounting_postings(event_id) WHERE stage='debit';
DO $$ DECLARE t TEXT; BEGIN
 FOREACH t IN ARRAY ARRAY['loan_payout_accounting_preparations','loan_payout_accounting_postings'] LOOP
  EXECUTE format('ALTER TABLE accounting.%I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('REVOKE ALL ON accounting.%I FROM PUBLIC',t);
  EXECUTE format('DROP TRIGGER IF EXISTS loan_payout_accounting_evidence_guard ON accounting.%I',t);
  EXECUTE format('CREATE TRIGGER loan_payout_accounting_evidence_guard BEFORE INSERT OR UPDATE OR DELETE ON accounting.%I FOR EACH ROW EXECUTE FUNCTION accounting.guard_treasury_gl_evidence()',t);
  EXECUTE format('DROP TRIGGER IF EXISTS loan_payout_accounting_truncate_guard ON accounting.%I',t);
  EXECUTE format('CREATE TRIGGER loan_payout_accounting_truncate_guard BEFORE TRUNCATE ON accounting.%I FOR EACH STATEMENT EXECUTE FUNCTION accounting.guard_treasury_gl_evidence()',t);
 END LOOP;
END $$;

CREATE OR REPLACE FUNCTION accounting.loan_payout_accounting_origin(p_payout UUID,p_stage TEXT)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog,accounting,treasury,lending SET timezone='UTC' AS $$
DECLARE p treasury.loan_payouts%ROWTYPE; e treasury.events%ROWTYPE; result JSONB;
BEGIN
 SELECT * INTO p FROM treasury.loan_payouts WHERE id=p_payout;
 SELECT * INTO e FROM treasury.events WHERE id=p.event_id;
 IF e.id IS NULL OR p_stage IS NULL OR p_stage NOT IN('debit','completion') THEN RETURN NULL; END IF;
 result:=jsonb_build_object('payout',to_jsonb(p)-ARRAY['version','status','payload'],
  'event',to_jsonb(e),'evidence',(SELECT to_jsonb(ev) FROM treasury.evidence ev WHERE ev.id=e.evidence_id),
  'movements',(SELECT coalesce(jsonb_agg(to_jsonb(m) ORDER BY m.component,m.id),'[]'::jsonb) FROM treasury.movement_lines m WHERE m.event_id=e.id),
  'revisions',(SELECT coalesce(jsonb_agg(to_jsonb(r) ORDER BY r.version),'[]'::jsonb) FROM treasury.event_revisions r WHERE r.event_id=e.id),
  'links',(SELECT coalesce(jsonb_agg(to_jsonb(s) ORDER BY s.id),'[]'::jsonb) FROM treasury.source_links s WHERE s.event_id=e.id),
  'receipts',(SELECT coalesce(jsonb_agg(r.id ORDER BY r.id),'[]'::jsonb) FROM treasury.receipts r WHERE r.event_id=e.id),
  'transfers',(SELECT coalesce(jsonb_agg(t.id ORDER BY t.id),'[]'::jsonb) FROM treasury.transfers t WHERE e.id IN(t.source_event_id,t.destination_event_id)));
 IF p_stage='completion' THEN
  result:=result||jsonb_build_object('completion_status',p.status,'completion_payload',p.payload,
   'release',(SELECT to_jsonb(r) FROM lending.first_loan_releases r WHERE r.funding_payout_id=p.id),
   'disbursement',(SELECT to_jsonb(d) FROM lending.loan_disbursement_events d JOIN lending.first_loan_releases r ON r.disbursement_event_id=d.id WHERE r.funding_payout_id=p.id),
   'loan',(SELECT jsonb_build_object('id',l.id,'client_id',l.client_id,'loan_type_id',l.loan_type_id,'calculation_mode',lt.calculation_mode,
     'principal',l.principal::text,'date_released',l.date_released,'due_date',l.due_date) FROM lending.loans l JOIN lending.loan_types lt ON lt.id=l.loan_type_id WHERE l.id=p.loan_id),
   'borrower_evidence',(SELECT to_jsonb(ev) FROM treasury.evidence ev WHERE ev.id::text=p.payload->'borrower_receipt'->>'evidence_id'),
   'office_evidence',(SELECT to_jsonb(ev) FROM lending.office_review_evidence ev WHERE 'office-evidence:'||ev.id::text=p.payload->'borrower_receipt'->>'office_evidence_reference'));
 END IF;
 RETURN result;
END $$;

CREATE OR REPLACE VIEW accounting.loan_payout_accounting_posting_proof AS
SELECT a.payout_id,a.stage,a.event_id,a.disbursement_event_id,a.treasury_account_id,a.book_id,a.loan_id,a.client_id,
 a.preparation_id,a.journal_entry_id,a.source_digest,a.amount,a.fee,(p.snapshot->>'posting_date')::date AS posting_date,
 (a.payout_id=p.payout_id AND a.stage=p.stage AND a.event_id=p.event_id
  AND a.disbursement_event_id IS NOT DISTINCT FROM p.disbursement_event_id AND a.treasury_account_id=p.treasury_account_id
  AND a.book_id=p.book_id AND a.loan_id=p.loan_id AND a.client_id=p.client_id AND a.source_digest=p.source_digest
  AND a.actor_user_id=p.actor_user_id AND a.amount=(p.snapshot->>'amount')::numeric AND a.fee=(p.snapshot->>'fee')::numeric
  AND j.status='posted' AND j.source_type='treasury_loan_payout' AND j.source_event_key=p.snapshot->>'source_event_key'
  AND j.source_reference=p.payout_id::text AND j.posting_date=(p.snapshot->>'posting_date')::date
  AND j.fiscal_period_id=(p.snapshot->>'fiscal_period_id')::uuid AND j.created_by_user_id=p.actor_user_id
  AND j.posted_by_user_id=p.actor_user_id AND j.reversal_of_entry_id IS NULL
  AND (SELECT count(*) FROM accounting.journal_lines WHERE journal_entry_id=j.id)=jsonb_array_length(p.snapshot->'lines')
  AND NOT EXISTS(SELECT 1 FROM jsonb_to_recordset(p.snapshot->'lines') x(line_number INT,account_id UUID,debit NUMERIC,credit NUMERIC,client_id UUID,loan_id UUID)
   WHERE NOT EXISTS(SELECT 1 FROM accounting.journal_lines l WHERE l.journal_entry_id=j.id AND l.line_number=x.line_number
    AND l.account_id=x.account_id AND l.debit=x.debit AND l.credit=x.credit
    AND l.client_id IS NOT DISTINCT FROM x.client_id AND l.loan_id IS NOT DISTINCT FROM x.loan_id))) AS exact_posted,
 (accounting.loan_payout_accounting_origin(a.payout_id,a.stage) IS DISTINCT FROM p.snapshot->'origin'
  OR EXISTS(SELECT 1 FROM jsonb_array_elements(p.snapshot->'lines') line WHERE
   (line->'account_snapshot')-ARRAY['name','is_active'] IS DISTINCT FROM accounting.treasury_gl_account_snapshot((line->>'account_id')::uuid)-ARRAY['name','is_active'])) AS correction_pending
FROM accounting.loan_payout_accounting_postings a JOIN accounting.loan_payout_accounting_preparations p ON p.id=a.preparation_id
JOIN accounting.journal_entries j ON j.id=a.journal_entry_id;

CREATE OR REPLACE VIEW accounting.loan_payout_accounting_posting_status AS
SELECT p.payout_id,p.stage,p.event_id,p.disbursement_event_id,p.treasury_account_id,p.book_id,p.loan_id,p.client_id,
 p.preparation_id,p.journal_entry_id,p.source_digest,p.amount,p.fee,p.posting_date,p.exact_posted,
 (p.correction_pending OR (p.stage='completion' AND
  (debit.exact_posted IS DISTINCT FROM true OR debit.correction_pending IS DISTINCT FROM false))) AS correction_pending
FROM accounting.loan_payout_accounting_posting_proof p
LEFT JOIN accounting.loan_payout_accounting_posting_proof debit ON debit.payout_id=p.payout_id AND debit.stage='debit';

CREATE OR REPLACE FUNCTION accounting.loan_payout_coordinates(p_payout UUID,p_stage TEXT)
RETURNS JSONB LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting,treasury,lending SET timezone='UTC' AS $$
DECLARE p treasury.loan_payouts%ROWTYPE; e treasury.events%ROWTYPE; r lending.first_loan_releases%ROWTYPE;
 d lending.loan_disbursement_events%ROWTYPE; fiscal accounting.fiscal_periods%ROWTYPE; coordinate RECORD;
 debit accounting.loan_payout_accounting_posting_status%ROWTYPE; office lending.office_review_evidence%ROWTYPE;
 book UUID; mapping_id UUID; cash UUID; transit UUID; fee_account UUID; receivable UUID; day DATE; stage_fee NUMERIC(18,2);
 mapping JSONB; origin JSONB; lines JSONB; result JSONB; evidence JSONB; borrower_evidence JSONB;
BEGIN
 IF current_setting('transaction_isolation')<>'read committed' THEN RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Payout accounting requires READ COMMITTED.'; END IF;
 IF p_stage IS NULL OR p_stage NOT IN('debit','completion') THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='An exact payout accounting stage is required.'; END IF;
 SELECT * INTO p FROM treasury.loan_payouts WHERE id=p_payout;
 PERFORM id FROM treasury.accounts WHERE id=p.account_id FOR UPDATE;
 SELECT * INTO p FROM treasury.loan_payouts WHERE id=p_payout FOR UPDATE;
 IF p.id IS NULL OR p.event_id IS NULL OR p.status NOT IN('debited','recipient_confirmed','completed') THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='An actual verified payout debit is required before accounting.';
 END IF;
 book:=accounting.require_book_treasury_account(p.account_id);
 LOCK TABLE accounting.accounts IN SHARE MODE;
 SELECT id INTO mapping_id FROM accounting.treasury_cash_mappings WHERE treasury_account_id=p.account_id ORDER BY version DESC LIMIT 1;
 mapping:=accounting.treasury_transfer_mapping_snapshot(mapping_id,p.account_id);
 cash:=(mapping->>'cash_account_id')::uuid;
 IF NOT EXISTS(SELECT 1 FROM treasury.accounts WHERE id=p.account_id AND ledger_context_id=p.ledger_context_id AND kind IN('gcash','bank')) THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Payout requires its exact owned bank or wallet context.';
 END IF;
 SELECT * INTO e FROM treasury.events WHERE id=p.event_id FOR UPDATE;
 LOCK TABLE treasury.event_revisions,treasury.movement_lines,treasury.source_links,treasury.receipts,treasury.transfers,treasury.evidence IN SHARE MODE;
 origin:=accounting.loan_payout_accounting_origin(p.id,p_stage);
 IF e.id IS NULL OR e.account_id<>p.account_id OR e.ledger_context_id<>p.ledger_context_id OR e.direction<>'debit'
  OR e.amount<>p.amount OR e.version<>1 OR e.classification<>'verified_unclassified' OR btrim(coalesce(e.reference,''))=''
  OR btrim(coalesce(e.recipient_attestation,''))='' OR e.verified_by_user_id IS NULL OR e.effective_at>clock_timestamp()
  OR e.provider IS DISTINCT FROM (SELECT kind FROM treasury.accounts WHERE id=p.account_id)
  OR jsonb_array_length(origin->'revisions')<>0 OR jsonb_array_length(origin->'receipts')<>0 OR jsonb_array_length(origin->'transfers')<>0
  OR jsonb_array_length(origin->'links')<>1
  OR NOT EXISTS(SELECT 1 FROM treasury.source_links WHERE event_id=e.id AND ledger_context_id=p.ledger_context_id
    AND source_kind='loan_payout_funding' AND source_id=p.id AND source_version=1 AND linked_amount=p.amount)
  OR (SELECT count(*) FROM treasury.movement_lines WHERE event_id=e.id)<>(CASE WHEN e.fee>0 THEN 2 ELSE 1 END)
  OR NOT EXISTS(SELECT 1 FROM treasury.movement_lines WHERE event_id=e.id AND component='principal' AND signed_amount=-e.amount
    AND account_id=e.account_id AND ledger_context_id=e.ledger_context_id AND effective_at=e.effective_at AND evidence_id=e.evidence_id)
  OR (e.fee>0 AND NOT EXISTS(SELECT 1 FROM treasury.movement_lines WHERE event_id=e.id AND component='fee' AND signed_amount=-e.fee
    AND account_id=e.account_id AND ledger_context_id=e.ledger_context_id AND effective_at=e.effective_at AND evidence_id=e.evidence_id)) THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Payout funding is corrected, reused or does not exactly prove the original debit and fee.';
 END IF;
 SELECT to_jsonb(ev) INTO evidence FROM treasury.evidence ev WHERE id=e.evidence_id AND account_id=p.account_id AND purpose='recipient';
 IF evidence IS NULL THEN RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Retained private actual debit evidence is required.'; END IF;
 day:=(e.effective_at AT TIME ZONE 'Asia/Manila')::date;
 stage_fee:=CASE WHEN p_stage='debit' THEN e.fee ELSE 0 END;
 SELECT id INTO transit FROM accounting.accounts WHERE code='1050' AND system_key='loan_disbursement_transit'
  AND account_type='asset' AND normal_balance='debit' AND is_active AND is_posting;
 SELECT id INTO fee_account FROM accounting.accounts WHERE code='5240' AND system_key='bank_charges_expense'
  AND account_type='expense' AND normal_balance='debit' AND is_active AND is_posting;
 IF transit IS NULL OR (stage_fee>0 AND fee_account IS NULL) THEN RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Exact active payout transit and fee chart roles are required.'; END IF;
 IF p_stage='completion' THEN
  LOCK TABLE lending.first_loan_releases,lending.loan_disbursement_events,lending.loans,lending.loan_types,
   lending.office_review_evidence,lending.first_loan_approvals,lending.first_loan_authorizations,lending.first_loan_authorization_revocations IN SHARE MODE;
  IF p.source_kind<>'first_loan' OR p.status<>'completed' OR p.payload->>'borrower_handover_status' IS DISTINCT FROM 'confirmed' THEN
   RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Protected first-loan borrower completion is required; intermediary receipt is insufficient.';
  END IF;
  SELECT * INTO r FROM lending.first_loan_releases WHERE funding_payout_id=p.id;
  SELECT * INTO d FROM lending.loan_disbursement_events WHERE id=r.disbursement_event_id;
  SELECT * INTO office FROM lending.office_review_evidence WHERE 'office-evidence:'||id::text=r.borrower_receipt_reference;
  SELECT to_jsonb(ev) INTO borrower_evidence FROM treasury.evidence ev WHERE ev.id::text=p.payload->'borrower_receipt'->>'evidence_id'
   AND ev.account_id=p.account_id AND ev.purpose='recipient';
  IF r.id IS NULL OR d.id IS NULL OR r.loan_id<>p.loan_id OR d.loan_id<>p.loan_id OR d.client_id<>p.client_id
   OR r.received_amount IS DISTINCT FROM p.amount OR r.cash_amount IS NOT NULL OR r.cash_evidence_reference IS NOT NULL
   OR r.authorization_id::text IS DISTINCT FROM p.source_snapshot->>'authorization_id'
   OR r.packet_hash IS DISTINCT FROM p.source_snapshot->>'packet_hash' OR r.receipt_method NOT IN('cash','gcash','bank')
   OR r.contract_evidence_reference IS DISTINCT FROM p.source_snapshot->>'contract_evidence_reference'
   OR d.is_voided OR d.event_kind<>'new_loan_release' OR d.funding_account_system_key<>'cash_bank_gcash'
   OR d.settlement_amount<>0 OR d.other_deduction_amount<>0 OR d.principal_snapshot<>p.amount OR d.cash_disbursed_amount<>p.amount
   OR office.id IS NULL OR office.purpose<>'borrower_payout_received' OR office.subject_id<>p.id OR office.client_id<>p.client_id
   OR office.review_snapshot IS DISTINCT FROM p.payload->'borrower_receipt'->'snapshot'
   OR borrower_evidence IS NULL OR office.content_sha256 IS DISTINCT FROM borrower_evidence->>'sha256'
   OR office.byte_count IS DISTINCT FROM (borrower_evidence->>'byte_count')::int
   OR r.borrower_receipt_reference IS DISTINCT FROM p.payload->'borrower_receipt'->>'office_evidence_reference'
   OR d.business_date IS DISTINCT FROM (((p.payload->'borrower_receipt'->'snapshot'->>'acknowledged_at')::timestamptz AT TIME ZONE 'Asia/Manila')::date)
   OR (p.payload->'borrower_receipt'->'snapshot'->>'acknowledged_at')::timestamptz<e.effective_at
   OR d.disbursed_at<e.effective_at THEN
   RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Exact pure new loan release, independent borrower evidence and actual dates must reconcile.';
  END IF;
  SELECT * INTO debit FROM accounting.loan_payout_accounting_posting_status WHERE payout_id=p.id AND stage='debit';
  IF debit.journal_entry_id IS NULL OR NOT debit.exact_posted OR debit.correction_pending OR debit.amount<>p.amount
   OR debit.book_id<>book OR debit.treasury_account_id<>p.account_id OR debit.posting_date>d.business_date THEN
   RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Exact prior debit accounting is required before borrower completion accounting.';
  END IF;
  day:=d.business_date;
 END IF;
 SELECT * INTO fiscal FROM accounting.fiscal_periods WHERE day BETWEEN start_date AND end_date FOR UPDATE;
 IF fiscal.id IS NULL OR fiscal.status<>'open' OR (SELECT count(*) FROM accounting.fiscal_periods WHERE day BETWEEN start_date AND end_date)<>1 THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='The actual payout stage date requires one open accounting period.';
 END IF;
 LOCK TABLE accounting.journal_entries,accounting.journal_lines IN SHARE ROW EXCLUSIVE MODE;
 IF p_stage='completion' THEN
  SELECT * INTO coordinate FROM accounting.loan_disbursement_journal_coordinates WHERE disbursement_event_id=d.id;
  IF NOT FOUND OR coordinate.coordinate_status<>'coordinate_ready' OR coordinate.initial_measurement_basis<>'transaction_price_plain_cash_v1'
   OR coordinate.journal_draft_enabled OR coordinate.automatic_source_posting OR coordinate.calculation_mode<>'fixed_daily'
   OR coordinate.debit_amount<>p.amount OR coordinate.credit_amount<>p.amount OR coordinate.credit_account_id<>cash
   OR coordinate.posting_date<>day OR coordinate.fiscal_period_id<>fiscal.id THEN
   RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Unchanged protected pure new Regular loan coordinates are required.';
  END IF;
  receivable:=coordinate.debit_account_id;
  IF NOT EXISTS(SELECT 1 FROM accounting.accounts WHERE id=receivable AND code='1100' AND system_key='loans_receivable_regular'
   AND account_type='asset' AND normal_balance='debit' AND is_active AND is_posting) THEN
   RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='The authoritative Regular loan receivable role is unavailable.';
  END IF;
 END IF;
 SELECT jsonb_agg(jsonb_build_object('line_number',x.n,'account_id',x.account,'account_code',a.code,
  'account_snapshot',accounting.treasury_gl_account_snapshot(x.account),'debit',x.debit::numeric(18,2)::text,'credit',x.credit::numeric(18,2)::text,
  'client_id',p.client_id,'loan_id',CASE WHEN x.account IN(transit,receivable) THEN p.loan_id ELSE NULL END,'description',x.description) ORDER BY x.n)
 INTO lines FROM (VALUES
  (10,CASE WHEN p_stage='debit' THEN transit ELSE receivable END,p.amount,0::numeric,'Protected actual payout principal'),
  (20,fee_account,stage_fee,0::numeric,'Actual separately evidenced payout fee'),
  (30,CASE WHEN p_stage='debit' THEN cash ELSE transit END,0::numeric,p.amount+stage_fee,'Protected payout counter-entry')
 ) x(n,account,debit,credit,description) JOIN accounting.accounts a ON a.id=x.account WHERE x.debit>0 OR x.credit>0;
 origin:=accounting.loan_payout_accounting_origin(p.id,p_stage);
 result:=jsonb_build_object('book_id',book,'payout_id',p.id,'stage',p_stage,'event_id',e.id,'disbursement_event_id',d.id,
  'treasury_account_id',p.account_id,'ledger_context_id',p.ledger_context_id,'loan_id',p.loan_id,'client_id',p.client_id,
  'amount',p.amount::text,'fee',stage_fee::text,'posting_date',day,'fiscal_period_id',fiscal.id,'mapping_id',mapping_id,'mapping',mapping,
  'transit_account_id',transit,'source_event_key','treasury_loan_payout:'||p.id::text||':'||p_stage,
  'debit_journal_entry_id',debit.journal_entry_id,'debit_source_digest',debit.source_digest,
  'origin',origin,'evidence',evidence,'borrower_evidence',borrower_evidence,'office_evidence',CASE WHEN office.id IS NOT NULL THEN to_jsonb(office) ELSE NULL END,'lines',lines);
 RETURN result||jsonb_build_object('source_digest',encode(sha256(convert_to(result::text,'UTF8')),'hex'));
END $$;

CREATE OR REPLACE FUNCTION accounting.require_loan_payout_accounting_actor(p_actor UUID,p_payout UUID)
RETURNS VOID LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting,treasury AS $$
DECLARE account UUID; locked_account UUID;
BEGIN
 SELECT account_id INTO account FROM treasury.loan_payouts WHERE id=p_payout;
 IF account IS NULL THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='Private payout is unavailable.'; END IF;
 PERFORM accounting.require_treasury_gl_actor(p_actor,account,'treasury.view');
 SELECT account_id INTO locked_account FROM treasury.loan_payouts WHERE id=p_payout FOR UPDATE;
 IF locked_account IS DISTINCT FROM account THEN RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Payout wallet changed during review.'; END IF;
END $$;

CREATE OR REPLACE FUNCTION accounting.prepare_loan_payout_accounting(p_payout UUID,p_stage TEXT,p_digest TEXT,p_request UUID,p_actor UUID)
RETURNS UUID LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting AS $$
DECLARE prior accounting.loan_payout_accounting_preparations%ROWTYPE; source JSONB; result UUID; previous TEXT;
BEGIN
 PERFORM accounting.require_loan_payout_accounting_actor(p_actor,p_payout);
 SELECT * INTO prior FROM accounting.loan_payout_accounting_preparations WHERE request_id=p_request;
 IF FOUND THEN
  IF prior.payout_id=p_payout AND prior.stage=p_stage AND prior.source_digest=p_digest AND prior.actor_user_id=p_actor THEN RETURN prior.id; END IF;
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Payout preparation retry conflicts with the retained exact review.';
 END IF;
 IF p_request IS NULL THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='Payout preparation request identity is required.'; END IF;
 IF EXISTS(SELECT 1 FROM accounting.loan_payout_accounting_postings WHERE payout_id=p_payout AND stage=p_stage) THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Actual payout stage is already accounted.';
 END IF;
 source:=accounting.loan_payout_coordinates(p_payout,p_stage);
 IF source->>'source_digest' IS DISTINCT FROM p_digest THEN RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Payout source or mapping is stale; review again.'; END IF;
 previous:=current_setting('accounting.treasury_gl_write',true);
 PERFORM set_config('accounting.treasury_gl_write','loan_payout_accounting_preparations',true);
 INSERT INTO accounting.loan_payout_accounting_preparations(request_id,payout_id,stage,event_id,disbursement_event_id,
  treasury_account_id,book_id,loan_id,client_id,mapping_id,source_digest,confirmation_token,snapshot,actor_user_id)
 VALUES(p_request,p_payout,p_stage,(source->>'event_id')::uuid,(source->>'disbursement_event_id')::uuid,
  (source->>'treasury_account_id')::uuid,(source->>'book_id')::uuid,(source->>'loan_id')::uuid,(source->>'client_id')::uuid,
  (source->>'mapping_id')::uuid,p_digest,encode(sha256(convert_to(gen_random_uuid()::text||p_digest,'UTF8')),'hex'),source-'source_digest',p_actor)
 RETURNING id INTO result;
 PERFORM set_config('accounting.treasury_gl_write',coalesce(previous,''),true);
 RETURN result;
END $$;

CREATE OR REPLACE FUNCTION accounting.guard_loan_payout_accounting_journal()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting AS $$
DECLARE p accounting.loan_payout_accounting_preparations%ROWTYPE;
BEGIN
 IF TG_OP<>'DELETE' AND NEW.reversal_of_entry_id IS NOT NULL AND EXISTS(SELECT 1 FROM accounting.journal_entries
   WHERE id=NEW.reversal_of_entry_id AND source_type='treasury_loan_payout') THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Payout reversal requires its protected accounting correction adapter.';
 END IF;
 IF (TG_OP<>'INSERT' AND (OLD.source_type='treasury_loan_payout' OR OLD.source_event_key LIKE 'treasury_loan_payout:%'))
  OR (TG_OP<>'DELETE' AND (NEW.source_type='treasury_loan_payout' OR NEW.source_event_key LIKE 'treasury_loan_payout:%')) THEN
  IF TG_OP='DELETE' THEN RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Protected payout journals cannot be cancelled.'; END IF;
  SELECT * INTO p FROM accounting.loan_payout_accounting_preparations WHERE id::text=current_setting('accounting.loan_payout_accounting_post',true);
  IF p.id IS NULL OR NEW.source_type IS DISTINCT FROM 'treasury_loan_payout' OR NEW.source_event_key IS DISTINCT FROM p.snapshot->>'source_event_key'
   OR NEW.source_reference IS DISTINCT FROM p.payout_id::text OR NEW.posting_date IS DISTINCT FROM (p.snapshot->>'posting_date')::date
   OR NEW.fiscal_period_id IS DISTINCT FROM (p.snapshot->>'fiscal_period_id')::uuid OR NEW.created_by_user_id IS DISTINCT FROM p.actor_user_id
   OR NEW.reversal_of_entry_id IS NOT NULL OR (NEW.status='posted' AND NEW.posted_by_user_id IS DISTINCT FROM p.actor_user_id) THEN
   RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Protected payout journal requires its exact reviewed actual-stage adapter.';
  END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS loan_payout_accounting_journal_guard ON accounting.journal_entries;
CREATE TRIGGER loan_payout_accounting_journal_guard BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_loan_payout_accounting_journal();

CREATE OR REPLACE FUNCTION accounting.assert_loan_payout_accounting_audit()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting AS $$
DECLARE entry UUID;
BEGIN
 IF TG_TABLE_NAME='journal_entries' THEN
  IF NEW.source_type IS DISTINCT FROM 'treasury_loan_payout' AND coalesce(NEW.source_event_key,'') NOT LIKE 'treasury_loan_payout:%' THEN RETURN NEW; END IF;
  entry:=NEW.id;
 ELSE entry:=NEW.journal_entry_id; END IF;
 IF NOT EXISTS(SELECT 1 FROM accounting.loan_payout_accounting_posting_status WHERE journal_entry_id=entry AND exact_posted) THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Payout journal requires its exact immutable actual-stage audit.';
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS loan_payout_accounting_journal_audit ON accounting.journal_entries;
CREATE CONSTRAINT TRIGGER loan_payout_accounting_journal_audit AFTER INSERT OR UPDATE ON accounting.journal_entries
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION accounting.assert_loan_payout_accounting_audit();
DROP TRIGGER IF EXISTS loan_payout_accounting_posting_audit ON accounting.loan_payout_accounting_postings;
CREATE CONSTRAINT TRIGGER loan_payout_accounting_posting_audit AFTER INSERT ON accounting.loan_payout_accounting_postings
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION accounting.assert_loan_payout_accounting_audit();

CREATE OR REPLACE FUNCTION accounting.guard_loan_payout_accounting_line_truncate()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM accounting.journal_entries WHERE source_type='treasury_loan_payout') THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Protected payout cash and transit proof cannot be truncated.';
 END IF;
 RETURN NULL;
END $$;
DROP TRIGGER IF EXISTS loan_payout_accounting_line_truncate ON accounting.journal_lines;
CREATE TRIGGER loan_payout_accounting_line_truncate BEFORE TRUNCATE ON accounting.journal_lines FOR EACH STATEMENT
EXECUTE FUNCTION accounting.guard_loan_payout_accounting_line_truncate();

CREATE OR REPLACE FUNCTION accounting.post_loan_payout_accounting(p_preparation UUID,p_digest TEXT,p_token TEXT,p_actor UUID)
RETURNS UUID LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting AS $$
DECLARE p accounting.loan_payout_accounting_preparations%ROWTYPE; prior accounting.loan_payout_accounting_postings%ROWTYPE;
 source JSONB; result UUID; previous TEXT; previous_write TEXT;
BEGIN
 SELECT * INTO p FROM accounting.loan_payout_accounting_preparations WHERE id=p_preparation;
 IF p.id IS NULL THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='Private payout preparation is unavailable.'; END IF;
 PERFORM accounting.require_treasury_gl_actor(p_actor,p.treasury_account_id,'treasury.view');
 IF p.source_digest IS DISTINCT FROM p_digest OR p.confirmation_token IS DISTINCT FROM p_token OR p.actor_user_id IS DISTINCT FROM p_actor THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Payout confirmation must match the exact retained review and actor.';
 END IF;
 SELECT * INTO prior FROM accounting.loan_payout_accounting_postings WHERE payout_id=p.payout_id AND stage=p.stage;
 IF FOUND THEN
  IF prior.preparation_id=p.id AND prior.source_digest=p_digest AND prior.actor_user_id=p_actor
   AND EXISTS(SELECT 1 FROM accounting.loan_payout_accounting_posting_status WHERE journal_entry_id=prior.journal_entry_id AND exact_posted) THEN RETURN prior.journal_entry_id; END IF;
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Payout stage is already accounted under a different exact review.';
 END IF;
 source:=accounting.loan_payout_coordinates(p.payout_id,p.stage);
 IF source->>'source_digest' IS DISTINCT FROM p.source_digest OR source-'source_digest' IS DISTINCT FROM p.snapshot THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Actual payout stage, authority or mapping evidence is stale; prepare again.';
 END IF;
 previous:=current_setting('accounting.loan_payout_accounting_post',true);
 previous_write:=current_setting('accounting.treasury_gl_write',true);
 PERFORM set_config('accounting.loan_payout_accounting_post',p.id::text,true);
 INSERT INTO accounting.journal_entries(fiscal_period_id,posting_date,description,source_type,source_reference,source_event_key,created_by_user_id)
 VALUES((p.snapshot->>'fiscal_period_id')::uuid,(p.snapshot->>'posting_date')::date,'Actual protected loan payout '||p.stage,
  'treasury_loan_payout',p.payout_id::text,p.snapshot->>'source_event_key',p_actor) RETURNING id INTO result;
 INSERT INTO accounting.journal_lines(journal_entry_id,line_number,account_id,description,debit,credit,client_id,loan_id)
 SELECT result,x.line_number,x.account_id,x.description,x.debit,x.credit,x.client_id,x.loan_id
 FROM jsonb_to_recordset(p.snapshot->'lines') x(line_number INT,account_id UUID,description TEXT,debit NUMERIC,credit NUMERIC,client_id UUID,loan_id UUID);
 PERFORM accounting.post_journal_entry(result,p_actor);
 PERFORM set_config('accounting.treasury_gl_write','loan_payout_accounting_postings',true);
 INSERT INTO accounting.loan_payout_accounting_postings(preparation_id,payout_id,stage,event_id,disbursement_event_id,
  treasury_account_id,book_id,loan_id,client_id,journal_entry_id,amount,fee,source_digest,actor_user_id)
 VALUES(p.id,p.payout_id,p.stage,p.event_id,p.disbursement_event_id,p.treasury_account_id,p.book_id,p.loan_id,p.client_id,result,
  (p.snapshot->>'amount')::numeric,(p.snapshot->>'fee')::numeric,p.source_digest,p_actor);
 IF NOT EXISTS(SELECT 1 FROM accounting.loan_payout_accounting_posting_status WHERE journal_entry_id=result AND exact_posted) THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Posted payout audit does not match exact reviewed money coordinates.';
 END IF;
 PERFORM set_config('accounting.loan_payout_accounting_post',coalesce(previous,''),true);
 PERFORM set_config('accounting.treasury_gl_write',coalesce(previous_write,''),true);
 RETURN result;
END $$;

CREATE OR REPLACE FUNCTION accounting.loan_payout_transit_reconciliation(p_as_of DATE)
RETURNS TABLE(payout_id UUID,book_id UUID,treasury_account_id UUID,loan_id UUID,client_id UUID,
 debit_amount NUMERIC,completion_amount NUMERIC,expected_transit NUMERIC,ledger_transit NUMERIC,difference NUMERIC,requires_review BOOLEAN)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 WITH retained AS (
  SELECT p.payout_id,p.book_id,p.treasury_account_id,p.loan_id,p.client_id,
   coalesce(sum(p.amount) FILTER(WHERE p.stage='debit'),0) AS debit_amount,
   coalesce(sum(p.amount) FILTER(WHERE p.stage='completion'),0) AS completion_amount,
   bool_or(NOT p.exact_posted OR p.correction_pending) AS requires_review
  FROM accounting.loan_payout_accounting_posting_status p WHERE p.posting_date<=p_as_of
  GROUP BY p.payout_id,p.book_id,p.treasury_account_id,p.loan_id,p.client_id
 ), ledger AS (
  SELECT a.payout_id,sum(l.debit-l.credit) AS amount
  FROM accounting.loan_payout_accounting_postings a JOIN accounting.loan_payout_accounting_preparations p ON p.id=a.preparation_id
  JOIN accounting.journal_entries j ON j.id=a.journal_entry_id AND j.status='posted' AND j.posting_date<=p_as_of
  JOIN accounting.journal_lines l ON l.journal_entry_id=j.id AND l.account_id=(p.snapshot->>'transit_account_id')::uuid
  GROUP BY a.payout_id
 ) SELECT r.payout_id,r.book_id,r.treasury_account_id,r.loan_id,r.client_id,r.debit_amount,r.completion_amount,
   r.debit_amount-r.completion_amount,coalesce(l.amount,0),coalesce(l.amount,0)-(r.debit_amount-r.completion_amount),
   r.requires_review OR coalesce(l.amount,0)<>(r.debit_amount-r.completion_amount)
 FROM retained r LEFT JOIN ledger l ON l.payout_id=r.payout_id;
$$;

CREATE OR REPLACE FUNCTION accounting.period_loan_payout_control_blockers(p_period UUID)
RETURNS TABLE(source_type TEXT,source_id UUID,effective_date DATE,amount NUMERIC(18,2),reason TEXT,account_id UUID)
LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT 'loan_payout_transit_control'::text,r.payout_id,p.end_date,r.difference::numeric(18,2),
  'loan_payout_transit_reconciliation_required'::text,r.treasury_account_id
 FROM accounting.fiscal_periods p CROSS JOIN LATERAL accounting.loan_payout_transit_reconciliation(p.end_date) r
 WHERE p.id=p_period AND r.requires_review
 UNION ALL
 SELECT 'loan_payout_transit_unregistered'::text,j.id,p.end_date,sum(l.debit-l.credit)::numeric(18,2),
  'loan_payout_transit_line_without_native_audit'::text,NULL::uuid
 FROM accounting.fiscal_periods p JOIN accounting.journal_entries j ON j.status='posted' AND j.posting_date<=p.end_date
 JOIN accounting.journal_lines l ON l.journal_entry_id=j.id JOIN accounting.accounts a ON a.id=l.account_id
 WHERE p.id=p_period AND a.system_key='loan_disbursement_transit'
  AND NOT EXISTS(SELECT 1 FROM accounting.loan_payout_accounting_postings audit WHERE audit.journal_entry_id=j.id)
 GROUP BY j.id,p.end_date;
$$;

-- Preserve the source-plus-review-manifest composition from 0151 and later
-- adapters. Only the exact debit event and borrower release obligation clear.
DO $$ BEGIN
 IF to_regprocedure('accounting.period_initial_before_payout_blockers(uuid)') IS NULL THEN
  ALTER FUNCTION accounting.period_initial_source_blockers(UUID) RENAME TO period_initial_before_payout_blockers;
 END IF;
 IF to_regprocedure('accounting.period_legacy_before_payout_blockers(uuid)') IS NULL THEN
  ALTER FUNCTION accounting.period_legacy_source_blockers(UUID) RENAME TO period_legacy_before_payout_blockers;
 END IF;
END $$;
CREATE OR REPLACE FUNCTION accounting.period_initial_source_blockers(p_period UUID)
RETURNS TABLE(source_type TEXT,source_id UUID,effective_date DATE,amount NUMERIC(18,2),reason TEXT,account_id UUID)
LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT b.* FROM accounting.period_initial_before_payout_blockers(p_period) b
 CROSS JOIN accounting.fiscal_periods period WHERE period.id=p_period AND NOT(b.source_type='treasury_event' AND EXISTS(
  SELECT 1 FROM accounting.loan_payout_accounting_posting_status p WHERE p.stage='debit' AND p.event_id=b.source_id
   AND p.posting_date<=period.end_date AND p.exact_posted AND NOT p.correction_pending))
 UNION ALL SELECT * FROM accounting.period_loan_payout_control_blockers(p_period);
$$;
CREATE OR REPLACE FUNCTION accounting.period_legacy_source_blockers(p_period UUID)
RETURNS TABLE(source_type TEXT,source_id UUID,effective_date DATE,amount NUMERIC(18,2),reason TEXT,account_id UUID)
LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT b.* FROM accounting.period_legacy_before_payout_blockers(p_period) b CROSS JOIN accounting.fiscal_periods period
 WHERE period.id=p_period AND NOT(b.source_type='loan_disbursement' AND EXISTS(
  SELECT 1 FROM accounting.loan_payout_accounting_posting_status p WHERE p.stage='completion' AND p.disbursement_event_id=b.source_id
   AND p.posting_date<=period.end_date AND p.exact_posted AND NOT p.correction_pending));
$$;

DO $$ BEGIN
 IF to_regprocedure('accounting.period_review_additional_evidence(uuid)') IS NOT NULL THEN
  IF to_regprocedure('accounting.period_review_before_payout_evidence(uuid)') IS NULL THEN
   ALTER FUNCTION accounting.period_review_additional_evidence(UUID) RENAME TO period_review_before_payout_evidence;
  END IF;
  EXECUTE $fn$CREATE OR REPLACE FUNCTION accounting.period_review_additional_evidence(p_period UUID)
   RETURNS JSONB LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $body$
   SELECT accounting.period_review_before_payout_evidence(p_period)||CASE WHEN count(p.id)=0 THEN '{}'::jsonb ELSE
    jsonb_build_object('loan_payout_accounting',jsonb_agg(jsonb_build_object('posting',to_jsonb(p),'preparation',to_jsonb(prepared)) ORDER BY p.id)) END
   FROM accounting.loan_payout_accounting_postings p JOIN accounting.loan_payout_accounting_preparations prepared ON prepared.id=p.preparation_id
   JOIN accounting.fiscal_periods period ON period.id=p_period WHERE (prepared.snapshot->>'posting_date')::date<=period.end_date
   $body$ $fn$;
  IF to_regprocedure('accounting.lock_period_review_before_payout_sources()') IS NULL THEN
   ALTER FUNCTION accounting.lock_period_review_additional_sources() RENAME TO lock_period_review_before_payout_sources;
  END IF;
  EXECUTE $fn$CREATE OR REPLACE FUNCTION accounting.lock_period_review_additional_sources()
   RETURNS VOID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $body$
   BEGIN
    PERFORM accounting.lock_period_review_before_payout_sources();
    LOCK TABLE accounting.loan_payout_accounting_preparations,accounting.loan_payout_accounting_postings,
     treasury.loan_payouts,lending.first_loan_releases,lending.office_review_evidence IN SHARE MODE;
   END $body$ $fn$;
 END IF;
END $$;

DO $$ DECLARE role_name TEXT; item RECORD; BEGIN
 FOREACH role_name IN ARRAY ARRAY['PUBLIC','anon','authenticated','service_role'] LOOP
  IF role_name='PUBLIC' OR EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
   FOR item IN SELECT oid::regprocedure::text signature FROM pg_proc WHERE pronamespace='accounting'::regnamespace
    AND (proname LIKE '%loan_payout_accounting%' OR proname IN ('loan_payout_coordinates','loan_payout_transit_reconciliation',
     'period_loan_payout_control_blockers','period_initial_before_payout_blockers','period_legacy_before_payout_blockers',
     'period_initial_source_blockers','period_legacy_source_blockers','period_review_additional_evidence',
     'period_review_before_payout_evidence','lock_period_review_before_payout_sources','lock_period_review_additional_sources')) LOOP
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM %s',item.signature,CASE WHEN role_name='PUBLIC' THEN 'PUBLIC' ELSE quote_ident(role_name) END);
   END LOOP;
   EXECUTE format('REVOKE ALL ON accounting.loan_payout_accounting_preparations,accounting.loan_payout_accounting_postings,
    accounting.loan_payout_accounting_posting_proof,accounting.loan_payout_accounting_posting_status FROM %s',
    CASE WHEN role_name='PUBLIC' THEN 'PUBLIC' ELSE quote_ident(role_name) END);
  END IF;
 END LOOP;
END $$;
COMMIT;
