BEGIN;

-- First application family: one reviewed 7x7 payment/advance in one open EIR
-- interval. The existing signed-schedule EIR engine remains the measurement
-- authority. Receipt cash has already been recognized by migration 0142.
CREATE TABLE IF NOT EXISTS accounting.treasury_application_preparations (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), request_id UUID NOT NULL UNIQUE,
 application_id UUID NOT NULL REFERENCES treasury.applications(id),
 transaction_id UUID NOT NULL REFERENCES lending.collection_transactions(id),
 receipt_id UUID NOT NULL REFERENCES treasury.receipts(id),
 treasury_account_id UUID NOT NULL REFERENCES treasury.accounts(id),
 book_id UUID NOT NULL REFERENCES accounting.book_identity(id),
 loan_id UUID NOT NULL REFERENCES lending.loans(id),
 source_digest TEXT NOT NULL CHECK(source_digest ~ '^[0-9a-f]{64}$'),
 confirmation_token TEXT NOT NULL CHECK(confirmation_token ~ '^[0-9a-f]{64}$'),
 snapshot JSONB NOT NULL,
 actor_user_id UUID NOT NULL REFERENCES core.users(id),
 created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS accounting.treasury_application_postings (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 preparation_id UUID NOT NULL UNIQUE REFERENCES accounting.treasury_application_preparations(id),
 application_id UUID NOT NULL UNIQUE REFERENCES treasury.applications(id),
 transaction_id UUID NOT NULL UNIQUE REFERENCES lending.collection_transactions(id),
 receipt_id UUID NOT NULL REFERENCES treasury.receipts(id),
 treasury_account_id UUID NOT NULL REFERENCES treasury.accounts(id),
 book_id UUID NOT NULL REFERENCES accounting.book_identity(id),
 loan_id UUID NOT NULL REFERENCES lending.loans(id),
 journal_entry_id UUID NOT NULL UNIQUE REFERENCES accounting.journal_entries(id),
 amount NUMERIC(18,2) NOT NULL CHECK(amount>0),
 source_digest TEXT NOT NULL CHECK(source_digest ~ '^[0-9a-f]{64}$'),
 actor_user_id UUID NOT NULL REFERENCES core.users(id),
 created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS treasury_application_postings_receipt_idx ON accounting.treasury_application_postings(receipt_id);
CREATE INDEX IF NOT EXISTS treasury_application_postings_loan_idx ON accounting.treasury_application_postings(loan_id);
DO $$ DECLARE t TEXT; BEGIN
 FOREACH t IN ARRAY ARRAY['treasury_application_preparations','treasury_application_postings'] LOOP
  EXECUTE format('ALTER TABLE accounting.%I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('REVOKE ALL ON accounting.%I FROM PUBLIC',t);
  EXECUTE format('DROP TRIGGER IF EXISTS treasury_application_evidence_guard ON accounting.%I',t);
  EXECUTE format('CREATE TRIGGER treasury_application_evidence_guard BEFORE INSERT OR UPDATE OR DELETE ON accounting.%I FOR EACH ROW EXECUTE FUNCTION accounting.guard_treasury_gl_evidence()',t);
  EXECUTE format('DROP TRIGGER IF EXISTS treasury_application_truncate_guard ON accounting.%I',t);
  EXECUTE format('CREATE TRIGGER treasury_application_truncate_guard BEFORE TRUNCATE ON accounting.%I FOR EACH STATEMENT EXECUTE FUNCTION accounting.guard_treasury_gl_evidence()',t);
 END LOOP;
END $$;

-- Historical source comparison excludes mutable receipt capacity and open-period
-- readiness. Later applications and a valid period close do not invalidate an
-- earlier recognition; changed EIR history and reversals remain visible.
CREATE OR REPLACE FUNCTION accounting.treasury_application_origin(p_application_id UUID)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER
SET search_path=pg_catalog,accounting,treasury,lending SET timezone='UTC' AS $$
DECLARE a treasury.applications%ROWTYPE; r treasury.receipts%ROWTYPE;
 t lending.collection_transactions%ROWTYPE; measurement JSONB; transaction_text TEXT;
BEGIN
 SELECT * INTO a FROM treasury.applications WHERE id=p_application_id;
 IF a.id IS NULL OR jsonb_typeof(a.source_result->'transaction_ids') IS DISTINCT FROM 'array' THEN RETURN NULL; END IF;
 IF jsonb_array_length(a.source_result->'transaction_ids')<>1 THEN RETURN NULL; END IF;
 transaction_text:=a.source_result->'transaction_ids'->>0;
 IF transaction_text IS NULL OR transaction_text !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN RETURN NULL; END IF;
 SELECT * INTO t FROM lending.collection_transactions WHERE id=transaction_text::uuid;
 SELECT * INTO r FROM treasury.receipts WHERE id=a.receipt_id;
 IF t.id IS NULL OR r.id IS NULL THEN RETURN NULL; END IF;
 SELECT to_jsonb(x) INTO measurement FROM accounting.preview_seven_by_seven_source_event_accounting(t.loan_id) x WHERE x.transaction_id=t.id;
 RETURN jsonb_build_object('application',to_jsonb(a),
  'transaction',jsonb_build_object('id',t.id,'loan_id',t.loan_id,'client_id',t.client_id,
    'funding_source',t.funding_source,'funding_receipt_id',t.funding_receipt_id,'funding_account_id',t.funding_account_id,
    'amount',t.amount::text,'applied_amount',t.applied_amount::text,'unallocated_amount',t.unallocated_amount::text,
    'collection_date',t.collection_date,'entry_type',t.entry_type,'is_voided',t.is_voided,
    'recorded_at',t.recorded_at,'accepted_at',t.accepted_at,'details',t.details),
  'receipt',jsonb_build_object('id',r.id,'event_id',r.event_id,'account_id',r.account_id,
    'ledger_context_id',r.ledger_context_id,'client_id',r.client_id,'amount',r.amount::text,
    'effective_at',r.effective_at,'refunded_amount',r.refunded_amount::text),
  'revisions',(SELECT coalesce(jsonb_agg(to_jsonb(er) ORDER BY er.version),'[]'::jsonb) FROM treasury.event_revisions er WHERE er.event_id=r.event_id),
  'measurement',measurement);
END $$;

CREATE OR REPLACE VIEW accounting.treasury_application_posting_status AS
SELECT a.application_id,a.transaction_id,a.receipt_id,a.treasury_account_id,a.book_id,a.loan_id,
 a.preparation_id,a.journal_entry_id,a.source_digest,a.amount,
 (p.snapshot->>'event_id')::uuid AS event_id,
 (p.snapshot->>'posting_date')::date AS posting_date,
 (a.application_id=p.application_id AND a.transaction_id=p.transaction_id AND a.receipt_id=p.receipt_id
  AND a.treasury_account_id=p.treasury_account_id AND a.book_id=p.book_id AND a.loan_id=p.loan_id
  AND a.source_digest=p.source_digest AND a.actor_user_id=p.actor_user_id AND a.amount=(p.snapshot->>'amount')::numeric
  AND j.status='posted' AND j.source_type='treasury_receipt_application'
  AND j.source_event_key=p.snapshot->>'source_event_key' AND j.source_reference=p.application_id::text
  AND j.posting_date=(p.snapshot->>'posting_date')::date AND j.fiscal_period_id=(p.snapshot->>'fiscal_period_id')::uuid
  AND j.created_by_user_id=p.actor_user_id AND j.posted_by_user_id=p.actor_user_id AND j.reversal_of_entry_id IS NULL
  AND (SELECT count(*) FROM accounting.journal_lines WHERE journal_entry_id=j.id)=jsonb_array_length(p.snapshot->'lines')
  AND NOT EXISTS(SELECT 1 FROM jsonb_to_recordset(p.snapshot->'lines') x(line_number INT,account_id UUID,debit NUMERIC,credit NUMERIC,client_id UUID,loan_id UUID)
   WHERE NOT EXISTS(SELECT 1 FROM accounting.journal_lines l WHERE l.journal_entry_id=j.id AND l.line_number=x.line_number
    AND l.account_id=x.account_id AND l.debit=x.debit AND l.credit=x.credit
    AND l.client_id IS NOT DISTINCT FROM x.client_id AND l.loan_id IS NOT DISTINCT FROM x.loan_id))) AS exact_posted,
 (accounting.treasury_application_origin(a.application_id) IS DISTINCT FROM p.snapshot->'origin'
  OR EXISTS(SELECT 1 FROM jsonb_array_elements(p.snapshot->'lines') line
    WHERE (line->'account_snapshot')-ARRAY['name','is_active'] IS DISTINCT FROM
      accounting.treasury_gl_account_snapshot((line->>'account_id')::uuid)-ARRAY['name','is_active'])) AS correction_pending
FROM accounting.treasury_application_postings a
JOIN accounting.treasury_application_preparations p ON p.id=a.preparation_id
JOIN accounting.journal_entries j ON j.id=a.journal_entry_id;

CREATE OR REPLACE FUNCTION accounting.treasury_application_coordinates(p_application_id UUID)
RETURNS JSONB LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,accounting,treasury,lending SET timezone='UTC' AS $$
DECLARE a treasury.applications%ROWTYPE; r treasury.receipts%ROWTYPE; t lending.collection_transactions%ROWTYPE;
 p accounting.fiscal_periods%ROWTYPE; cash accounting.treasury_receipt_postings%ROWTYPE;
 cash_p accounting.treasury_receipt_preparations%ROWTYPE; origin JSONB; measurement JSONB; lines JSONB;
 result JSONB; wallet UUID; book UUID; liability UUID; principal_balance NUMERIC; interest_balance NUMERIC;
 consumed NUMERIC; previous_date DATE; line_count INT; loan_mode TEXT; ledger_evidence JSONB; prior_source RECORD;
 liability_balance NUMERIC; expected_liability NUMERIC; liability_ledger_evidence JSONB;
BEGIN
 IF current_setting('transaction_isolation')<>'read committed' THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Application accounting requires READ COMMITTED.';
 END IF;
 SELECT account_id INTO wallet FROM treasury.applications WHERE id=p_application_id;
 PERFORM id FROM treasury.accounts WHERE id=wallet FOR UPDATE;
 book:=accounting.require_book_treasury_account(wallet);
 SELECT * INTO a FROM treasury.applications WHERE id=p_application_id FOR UPDATE;
 SELECT * INTO r FROM treasury.receipts WHERE id=a.receipt_id FOR UPDATE;
 PERFORM id FROM treasury.events WHERE id=r.event_id FOR UPDATE;
 -- Freeze authoritative source and measurement inputs, including later source
 -- insertion. Contention can reject/retry; no stale financial replay is admitted.
 LOCK TABLE lending.collection_transactions,lending.loans,lending.loan_types,lending.clients,
  lending.loan_contract_schedules,lending.loan_contract_installments,lending.loan_contract_schedule_registrations,
  accounting.seven_by_seven_policy_decisions,accounting.seven_by_seven_policy_decision_voids,
  accounting.seven_by_seven_eir_initial_carrying_anchors,accounting.seven_by_seven_eir_initial_carrying_anchor_voids,
  lending.seven_by_seven_extra_principal_adjustments IN SHARE MODE;
 origin:=accounting.treasury_application_origin(p_application_id);
 IF origin IS NULL OR a.status<>'active' OR a.source_result->>'status' IS DISTINCT FROM 'recorded'
   OR a.source_result->>'amount' IS DISTINCT FROM a.amount::text THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='One exact active Treasury application transaction is required.';
 END IF;
 SELECT * INTO t FROM lending.collection_transactions WHERE id=(origin->'transaction'->>'id')::uuid FOR UPDATE;
 SELECT lt.calculation_mode INTO loan_mode FROM lending.loans l JOIN lending.loan_types lt ON lt.id=l.loan_type_id
  WHERE l.id=t.loan_id AND l.client_id=r.client_id;
 IF loan_mode IS DISTINCT FROM 'seven_by_seven' OR a.account_id<>r.account_id OR a.ledger_context_id<>r.ledger_context_id
  OR t.funding_source<>'treasury_receipt' OR t.funding_receipt_id IS DISTINCT FROM r.id OR t.funding_account_id IS DISTINCT FROM wallet
  OR t.client_id<>r.client_id OR t.amount<>a.amount OR t.applied_amount<>a.amount OR t.unallocated_amount<>0
  OR t.entry_type NOT IN ('payment','advance') OR t.is_voided OR r.refunded_amount<>0
  OR t.collection_date<(r.effective_at AT TIME ZONE 'Asia/Manila')::date
  OR jsonb_array_length(origin->'revisions')<>0
  OR EXISTS(SELECT 1 FROM treasury.source_links WHERE event_id=r.event_id)
  OR EXISTS(SELECT 1 FROM lending.seven_by_seven_extra_principal_adjustments WHERE loan_id=t.loan_id)
  OR EXISTS(SELECT 1 FROM lending.collection_transactions WHERE loan_id=t.loan_id AND is_voided AND amount>0)
  OR EXISTS(SELECT 1 FROM treasury.applications other WHERE other.id<>a.id AND other.source_result->'transaction_ids' ? t.id::text)
  OR (SELECT coalesce(sum(amount),0) FROM treasury.applications WHERE receipt_id=r.id AND status='active')<>r.applied_amount THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Application source is unsupported, corrected, reused or does not reconcile to its receipt.';
 END IF;
 SELECT * INTO cash FROM accounting.treasury_receipt_postings WHERE receipt_id=r.id;
 SELECT * INTO cash_p FROM accounting.treasury_receipt_preparations WHERE id=cash.preparation_id;
 IF cash.id IS NULL OR cash.book_id<>book OR NOT EXISTS(SELECT 1 FROM accounting.treasury_receipt_posting_status
   WHERE receipt_id=r.id AND exact_posted AND NOT correction_pending) THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Exact posted receipt cash and unapplied borrower liability are required first.';
 END IF;
 measurement:=origin->'measurement';
 IF measurement IS NULL OR measurement='null'::jsonb OR (measurement->>'event_preview_ready')::boolean IS DISTINCT FROM true THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Current protected signed-schedule 7x7 EIR measurement is required.';
 END IF;
 previous_date:=(measurement->>'previous_event_date')::date;
 SELECT * INTO p FROM accounting.fiscal_periods WHERE t.collection_date BETWEEN start_date AND end_date FOR UPDATE;
 IF p.id IS NULL OR p.status<>'open' OR previous_date<p.start_date OR t.collection_date>p.end_date THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Application EIR interval requires one open fiscal period; cross-period recognition is deferred.';
 END IF;
 LOCK TABLE accounting.accounts IN SHARE MODE;
 LOCK TABLE accounting.journal_entries,accounting.journal_lines IN SHARE ROW EXCLUSIVE MODE;
 liability:=(cash_p.snapshot->>'liability_account_id')::uuid;
 IF NOT EXISTS(SELECT 1 FROM accounting.accounts WHERE id=liability AND code='2200' AND system_key='unapplied_borrower_funds'
   AND account_type='liability' AND normal_balance='credit' AND is_active AND is_posting) THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='The original receipt liability chart mapping is unavailable.';
 END IF;
 IF (SELECT count(*) FROM accounting.accounts WHERE is_active AND is_posting
   AND (code,system_key,account_type,normal_balance) IN (
     ('1110','loans_receivable_7x7','asset','debit'),
     ('1120','accrued_interest_receivable','asset','debit'),
     ('4010','interest_income_7x7','income','credit')))<>3 THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Protected EIR chart account roles are unavailable or incompatible.';
 END IF;
 IF EXISTS(SELECT 1 FROM accounting.treasury_application_posting_status WHERE (receipt_id=r.id OR loan_id=t.loan_id)
   AND (NOT exact_posted OR correction_pending)) THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Prior application accounting requires protected correction review.';
 END IF;
 -- Compile the large legacy proof view only for an actual legacy prior source.
 -- The first application and Treasury-only histories must not expand unrelated
 -- legacy coordinate/readiness trees just to prove an empty set.
 FOR prior_source IN SELECT prior.id,prior.funding_source FROM lending.collection_transactions prior
   WHERE prior.loan_id=t.loan_id AND prior.collection_date<t.collection_date
     AND NOT prior.is_voided AND prior.amount>0 AND prior.entry_type IN ('payment','advance')
   ORDER BY prior.collection_date,prior.id LOOP
  IF prior_source.funding_source='collector_cash' THEN
   IF NOT EXISTS(SELECT 1 FROM accounting.seven_by_seven_journal_postings WHERE transaction_id=prior_source.id) THEN
    RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Every prior loan source requires exact posted accounting proof.';
   END IF;
   IF NOT EXISTS(SELECT 1 FROM accounting.seven_by_seven_journal_posting_status legacy
     WHERE legacy.transaction_id=prior_source.id AND legacy.posted_audit_exact) THEN
    RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Every prior loan source requires exact posted accounting proof.';
   END IF;
  ELSIF NOT EXISTS(SELECT 1 FROM accounting.treasury_application_posting_status previous
    WHERE previous.transaction_id=prior_source.id AND previous.exact_posted AND NOT previous.correction_pending) THEN
   RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Every prior loan source requires exact posted accounting proof.';
  END IF;
 END LOOP;
 IF EXISTS(SELECT 1 FROM accounting.journal_entries j JOIN accounting.journal_lines l ON l.journal_entry_id=j.id
   WHERE j.status='posted' AND l.loan_id=t.loan_id AND j.posting_date>t.collection_date) THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Later loan GL activity requires a backdated accounting correction review.';
 END IF;
 SELECT coalesce(sum(l.debit-l.credit) FILTER(WHERE ac.system_key='loans_receivable_7x7'),0),
   coalesce(sum(l.debit-l.credit) FILTER(WHERE ac.system_key='accrued_interest_receivable'),0),
   coalesce(jsonb_agg(jsonb_build_object('journal_id',j.id,'date',j.posting_date,'line',to_jsonb(l)) ORDER BY j.id,l.line_number),'[]'::jsonb)
 INTO principal_balance,interest_balance,ledger_evidence
 FROM accounting.journal_entries j JOIN accounting.journal_lines l ON l.journal_entry_id=j.id
 JOIN accounting.accounts ac ON ac.id=l.account_id
 WHERE j.status='posted' AND l.loan_id=t.loan_id AND j.posting_date<=t.collection_date
   AND ac.system_key IN ('loans_receivable_7x7','accrued_interest_receivable');
 IF principal_balance IS DISTINCT FROM (measurement->>'opening_7x7_loan_component')::numeric
  OR interest_balance IS DISTINCT FROM (measurement->>'opening_accrued_eir_interest')::numeric THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Authoritative prior GL carrying components do not match protected EIR measurement.';
 END IF;
 SELECT coalesce(sum(l.credit-l.debit),0),
   coalesce(jsonb_agg(jsonb_build_object('journal_id',j.id,'date',j.posting_date,'line',to_jsonb(l)) ORDER BY j.id,l.line_number),'[]'::jsonb)
 INTO liability_balance,liability_ledger_evidence
 FROM accounting.journal_entries j JOIN accounting.journal_lines l ON l.journal_entry_id=j.id
 WHERE j.status='posted' AND j.posting_date<=t.collection_date AND l.account_id=liability AND l.client_id=r.client_id;
 SELECT coalesce(sum((rp.snapshot->>'amount')::numeric),0) INTO expected_liability
 FROM accounting.treasury_receipt_postings posted JOIN accounting.treasury_receipt_preparations rp ON rp.id=posted.preparation_id
 WHERE (rp.snapshot->>'client_id')::uuid=r.client_id AND (rp.snapshot->>'posting_date')::date<=t.collection_date;
 SELECT expected_liability-coalesce(sum(posted.amount),0) INTO expected_liability
 FROM accounting.treasury_application_postings posted JOIN accounting.treasury_application_preparations ap ON ap.id=posted.preparation_id
 WHERE (ap.snapshot->>'client_id')::uuid=r.client_id AND (ap.snapshot->>'posting_date')::date<=t.collection_date;
 IF liability_balance IS DISTINCT FROM expected_liability OR liability_balance<a.amount
  OR EXISTS(SELECT 1 FROM accounting.journal_entries j JOIN accounting.journal_lines l ON l.journal_entry_id=j.id
    WHERE j.status='posted' AND j.posting_date<=t.collection_date AND l.account_id=liability AND l.client_id=r.client_id
      AND NOT EXISTS(SELECT 1 FROM accounting.treasury_receipt_postings rp WHERE rp.journal_entry_id=j.id)
      AND NOT EXISTS(SELECT 1 FROM accounting.treasury_application_postings ap WHERE ap.journal_entry_id=j.id)) THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Borrower liability GL requires exact retained receipt and application reconciliation.';
 END IF;
 SELECT coalesce(sum(amount),0) INTO consumed FROM accounting.treasury_application_postings WHERE receipt_id=r.id;
 IF consumed+a.amount>r.amount THEN RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Application exceeds the receipt liability remaining in accounting.'; END IF;
 SELECT jsonb_agg(jsonb_build_object('line_number',c.line_number,'journal_component',c.journal_component,
   'account_id',CASE WHEN c.journal_component='collection_cash_debit' THEN liability ELSE c.account_id END,
   'account_code',CASE WHEN c.journal_component='collection_cash_debit' THEN '2200' ELSE c.account_code END,
   'account_snapshot',accounting.treasury_gl_account_snapshot(CASE WHEN c.journal_component='collection_cash_debit' THEN liability ELSE c.account_id END),
   'debit',c.debit::text,'credit',c.credit::text,'client_id',r.client_id,
   'loan_id',CASE WHEN c.journal_component='collection_cash_debit' THEN NULL ELSE t.loan_id END) ORDER BY c.line_number),count(*)
 INTO lines,line_count FROM accounting.seven_by_seven_source_event_journal_coordinate_preview c
 WHERE c.transaction_id=t.id AND c.coordinate_preview_ready AND NOT c.journal_lines_enabled AND NOT c.automatic_source_posting;
 IF lines IS NULL OR line_count NOT BETWEEN 2 AND 5
  OR (SELECT count(*) FROM jsonb_array_elements(lines) x WHERE x->>'journal_component'='collection_cash_debit'
    AND (x->>'debit')::numeric=a.amount AND (x->>'credit')::numeric=0)<>1
  OR EXISTS(SELECT 1 FROM jsonb_array_elements(lines) x WHERE x->>'account_code' NOT IN ('2200','1120','1110','4010'))
  OR (SELECT sum((x->>'debit')::numeric)-sum((x->>'credit')::numeric) FROM jsonb_array_elements(lines) x)<>0 THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Exact protected EIR application coordinates are unavailable.';
 END IF;
 result:=jsonb_build_object('book_id',book,'application_id',a.id,'transaction_id',t.id,'receipt_id',r.id,'event_id',r.event_id,
  'treasury_account_id',wallet,'ledger_context_id',r.ledger_context_id,'loan_id',t.loan_id,'client_id',r.client_id,
  'posting_date',t.collection_date,'fiscal_period_id',p.id,'amount',a.amount::text,
  'source_event_key','treasury_application:'||a.id::text,'receipt_posting_id',cash.id,'receipt_source_digest',cash.source_digest,
  'receipt_version',r.version,'liability_remaining',(r.amount-consumed)::text,'evidence',cash_p.snapshot->'evidence',
  'origin',origin,'measurement',measurement,'lines',lines,'ledger_evidence',ledger_evidence,
  'borrower_liability_balance',liability_balance::text,'liability_ledger_evidence',liability_ledger_evidence);
 RETURN result||jsonb_build_object('source_digest',encode(sha256(convert_to(result::text,'UTF8')),'hex'));
END $$;

CREATE OR REPLACE FUNCTION accounting.prepare_treasury_application(p_application_id UUID,p_expected_source_digest TEXT,p_request_id UUID,p_actor_user_id UUID)
RETURNS UUID LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting,treasury AS $$
DECLARE wallet UUID; prior accounting.treasury_application_preparations%ROWTYPE; source JSONB; result UUID; previous TEXT;
BEGIN
 SELECT account_id INTO wallet FROM treasury.applications WHERE id=p_application_id;
 PERFORM accounting.require_treasury_gl_actor(p_actor_user_id,wallet,'treasury.view');
 SELECT * INTO prior FROM accounting.treasury_application_preparations WHERE request_id=p_request_id;
 IF FOUND THEN
  IF prior.application_id=p_application_id AND prior.source_digest=p_expected_source_digest AND prior.actor_user_id=p_actor_user_id THEN RETURN prior.id; END IF;
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Application preparation request retry conflicts with retained review.';
 END IF;
 IF p_request_id IS NULL THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='Application preparation request is required.'; END IF;
 IF EXISTS(SELECT 1 FROM accounting.treasury_application_postings WHERE application_id=p_application_id) THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Application is already accounted.';
 END IF;
 source:=accounting.treasury_application_coordinates(p_application_id);
 IF source->>'source_digest' IS DISTINCT FROM p_expected_source_digest THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Application source or EIR evidence is stale; review again.';
 END IF;
 previous:=current_setting('accounting.treasury_gl_write',true);
 PERFORM set_config('accounting.treasury_gl_write','treasury_application_preparations',true);
 INSERT INTO accounting.treasury_application_preparations(request_id,application_id,transaction_id,receipt_id,treasury_account_id,book_id,loan_id,source_digest,confirmation_token,snapshot,actor_user_id)
 VALUES(p_request_id,p_application_id,(source->>'transaction_id')::uuid,(source->>'receipt_id')::uuid,wallet,(source->>'book_id')::uuid,
  (source->>'loan_id')::uuid,p_expected_source_digest,encode(sha256(convert_to(gen_random_uuid()::text||p_expected_source_digest,'UTF8')),'hex'),source-'source_digest',p_actor_user_id)
 RETURNING id INTO result;
 PERFORM set_config('accounting.treasury_gl_write',coalesce(previous,''),true);
 RETURN result;
END $$;

CREATE OR REPLACE FUNCTION accounting.guard_treasury_application_journal()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting AS $$
DECLARE p accounting.treasury_application_preparations%ROWTYPE;
BEGIN
 IF TG_OP<>'DELETE' AND NEW.reversal_of_entry_id IS NOT NULL AND EXISTS(SELECT 1 FROM accounting.journal_entries
   WHERE id=NEW.reversal_of_entry_id AND source_type='treasury_receipt_application') THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Application reversal requires its protected accounting correction adapter.';
 END IF;
 IF (TG_OP<>'INSERT' AND (OLD.source_type='treasury_receipt_application' OR OLD.source_event_key LIKE 'treasury_application:%'))
  OR (TG_OP<>'DELETE' AND (NEW.source_type='treasury_receipt_application' OR NEW.source_event_key LIKE 'treasury_application:%')) THEN
  IF TG_OP='DELETE' THEN RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Protected application journals cannot be cancelled.'; END IF;
  SELECT * INTO p FROM accounting.treasury_application_preparations WHERE id::text=current_setting('accounting.treasury_application_post',true);
  IF p.id IS NULL OR NEW.source_type IS DISTINCT FROM 'treasury_receipt_application'
   OR NEW.source_event_key IS DISTINCT FROM p.snapshot->>'source_event_key' OR NEW.source_reference IS DISTINCT FROM p.application_id::text
   OR NEW.posting_date IS DISTINCT FROM (p.snapshot->>'posting_date')::date OR NEW.fiscal_period_id IS DISTINCT FROM (p.snapshot->>'fiscal_period_id')::uuid
   OR NEW.created_by_user_id IS DISTINCT FROM p.actor_user_id OR NEW.reversal_of_entry_id IS NOT NULL
   OR (NEW.status='posted' AND NEW.posted_by_user_id IS DISTINCT FROM p.actor_user_id) THEN
   RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Protected application journal requires its exact reviewed adapter.';
  END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS treasury_application_journal_guard ON accounting.journal_entries;
CREATE TRIGGER treasury_application_journal_guard BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_treasury_application_journal();

CREATE OR REPLACE FUNCTION accounting.assert_treasury_application_audit()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting AS $$
DECLARE entry UUID;
BEGIN
 IF TG_TABLE_NAME='journal_entries' THEN
  IF NEW.source_type IS DISTINCT FROM 'treasury_receipt_application' AND coalesce(NEW.source_event_key,'') NOT LIKE 'treasury_application:%' THEN RETURN NEW; END IF;
  entry:=NEW.id;
 ELSE entry:=NEW.journal_entry_id; END IF;
 IF NOT EXISTS(SELECT 1 FROM accounting.treasury_application_posting_status WHERE journal_entry_id=entry AND exact_posted) THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Application journal requires its exact immutable audit and EIR coordinates.';
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS treasury_application_journal_audit ON accounting.journal_entries;
CREATE CONSTRAINT TRIGGER treasury_application_journal_audit AFTER INSERT OR UPDATE ON accounting.journal_entries
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION accounting.assert_treasury_application_audit();
DROP TRIGGER IF EXISTS treasury_application_posting_audit ON accounting.treasury_application_postings;
CREATE CONSTRAINT TRIGGER treasury_application_posting_audit AFTER INSERT ON accounting.treasury_application_postings
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION accounting.assert_treasury_application_audit();

CREATE OR REPLACE FUNCTION accounting.post_treasury_application(p_preparation_id UUID,p_expected_source_digest TEXT,p_confirmation_token TEXT,p_actor_user_id UUID)
RETURNS UUID LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting,treasury AS $$
DECLARE p accounting.treasury_application_preparations%ROWTYPE; prior accounting.treasury_application_postings%ROWTYPE;
 source JSONB; result UUID; previous TEXT; previous_write TEXT;
BEGIN
 SELECT * INTO p FROM accounting.treasury_application_preparations WHERE id=p_preparation_id;
 PERFORM accounting.require_treasury_gl_actor(p_actor_user_id,p.treasury_account_id,'treasury.view');
 IF p.id IS NULL OR p.source_digest IS DISTINCT FROM p_expected_source_digest OR p.confirmation_token IS DISTINCT FROM p_confirmation_token
  OR p.actor_user_id IS DISTINCT FROM p_actor_user_id THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Application confirmation must exactly match retained evidence and actor.';
 END IF;
 SELECT * INTO prior FROM accounting.treasury_application_postings WHERE application_id=p.application_id;
 IF FOUND THEN
  IF prior.preparation_id=p.id AND prior.source_digest=p_expected_source_digest AND prior.actor_user_id=p_actor_user_id
    AND EXISTS(SELECT 1 FROM accounting.treasury_application_posting_status WHERE journal_entry_id=prior.journal_entry_id AND exact_posted) THEN RETURN prior.journal_entry_id; END IF;
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Application already accounted under a different exact review.';
 END IF;
 source:=accounting.treasury_application_coordinates(p.application_id);
 IF source->>'source_digest' IS DISTINCT FROM p.source_digest OR source-'source_digest' IS DISTINCT FROM p.snapshot THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Application source, prior ledger or EIR evidence is stale; prepare again.';
 END IF;
 previous:=current_setting('accounting.treasury_application_post',true);
 previous_write:=current_setting('accounting.treasury_gl_write',true);
 PERFORM set_config('accounting.treasury_application_post',p.id::text,true);
 INSERT INTO accounting.journal_entries(fiscal_period_id,posting_date,description,source_type,source_reference,source_event_key,created_by_user_id)
 VALUES((p.snapshot->>'fiscal_period_id')::uuid,(p.snapshot->>'posting_date')::date,'Apply retained borrower funds using protected 7x7 EIR',
  'treasury_receipt_application',p.application_id::text,p.snapshot->>'source_event_key',p_actor_user_id) RETURNING id INTO result;
 INSERT INTO accounting.journal_lines(journal_entry_id,line_number,account_id,description,debit,credit,client_id,loan_id)
 SELECT result,x.line_number,x.account_id,x.journal_component,x.debit,x.credit,x.client_id,x.loan_id
 FROM jsonb_to_recordset(p.snapshot->'lines') x(line_number INT,account_id UUID,journal_component TEXT,debit NUMERIC,credit NUMERIC,client_id UUID,loan_id UUID);
 PERFORM accounting.post_journal_entry(result,p_actor_user_id);
 PERFORM set_config('accounting.treasury_gl_write','treasury_application_postings',true);
 INSERT INTO accounting.treasury_application_postings(preparation_id,application_id,transaction_id,receipt_id,treasury_account_id,book_id,loan_id,journal_entry_id,amount,source_digest,actor_user_id)
 VALUES(p.id,p.application_id,p.transaction_id,p.receipt_id,p.treasury_account_id,p.book_id,p.loan_id,result,(p.snapshot->>'amount')::numeric,p.source_digest,p_actor_user_id);
 IF NOT EXISTS(SELECT 1 FROM accounting.treasury_application_posting_status WHERE journal_entry_id=result AND exact_posted) THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Application posted audit does not match reviewed EIR lines.';
 END IF;
 PERFORM set_config('accounting.treasury_application_post',coalesce(previous,''),true);
 PERFORM set_config('accounting.treasury_gl_write',coalesce(previous_write,''),true);
 RETURN result;
END $$;

-- Retain new/late operational cash evidence. Destructive reversal of an already
-- recognized application requires the future protected accounting reversal.
CREATE OR REPLACE FUNCTION accounting.guard_accounted_treasury_application_reversal()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,accounting AS $$
BEGIN
 IF TG_TABLE_SCHEMA='treasury' THEN
  IF NEW.status IS DISTINCT FROM OLD.status AND EXISTS(SELECT 1 FROM accounting.treasury_application_postings WHERE application_id=OLD.id) THEN
   RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Accounted application reversal requires protected accounting correction review.';
  END IF;
 ELSE
  IF (NEW.amount,NEW.applied_amount,NEW.unallocated_amount,NEW.collection_date,NEW.loan_id,NEW.client_id,NEW.entry_type,NEW.is_voided)
    IS DISTINCT FROM (OLD.amount,OLD.applied_amount,OLD.unallocated_amount,OLD.collection_date,OLD.loan_id,OLD.client_id,OLD.entry_type,OLD.is_voided)
    AND EXISTS(SELECT 1 FROM accounting.treasury_application_postings WHERE transaction_id=OLD.id) THEN
   RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Accounted application source requires protected accounting correction review.';
  END IF;
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS treasury_application_accounting_reversal_guard ON treasury.applications;
CREATE TRIGGER treasury_application_accounting_reversal_guard BEFORE UPDATE ON treasury.applications FOR EACH ROW
EXECUTE FUNCTION accounting.guard_accounted_treasury_application_reversal();
DROP TRIGGER IF EXISTS treasury_application_accounting_collection_guard ON lending.collection_transactions;
CREATE TRIGGER treasury_application_accounting_collection_guard BEFORE UPDATE ON lending.collection_transactions FOR EACH ROW
EXECUTE FUNCTION accounting.guard_accounted_treasury_application_reversal();

REVOKE ALL ON accounting.treasury_application_posting_status FROM PUBLIC;
DO $$ DECLARE f RECORD; r TEXT; t TEXT; BEGIN
 FOR f IN SELECT p.oid::regprocedure signature FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
  WHERE n.nspname='accounting' AND p.proname IN ('treasury_application_origin','treasury_application_coordinates',
  'prepare_treasury_application','guard_treasury_application_journal','assert_treasury_application_audit',
  'post_treasury_application','guard_accounted_treasury_application_reversal') LOOP
  EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC',f.signature);
  FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
   IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN EXECUTE format('REVOKE ALL ON FUNCTION %s FROM %I',f.signature,r); END IF;
  END LOOP;
 END LOOP;
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   FOREACH t IN ARRAY ARRAY['treasury_application_preparations','treasury_application_postings','treasury_application_posting_status'] LOOP
    EXECUTE format('REVOKE ALL ON accounting.%I FROM %I',t,r);
   END LOOP;
  END IF;
 END LOOP;
END $$;
COMMIT;
