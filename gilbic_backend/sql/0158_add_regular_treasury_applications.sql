BEGIN;

-- Preserve the exact0146 implementations for existing7x7 reviews and audits.
DO $$ BEGIN
 IF to_regprocedure('accounting.treasury_application_7x7_origin(uuid)') IS NULL THEN
  ALTER FUNCTION accounting.treasury_application_origin(UUID) RENAME TO treasury_application_7x7_origin;
 END IF;
 IF to_regprocedure('accounting.treasury_application_7x7_coordinates(uuid)') IS NULL THEN
  ALTER FUNCTION accounting.treasury_application_coordinates(UUID) RENAME TO treasury_application_7x7_coordinates;
 END IF;
END $$;

CREATE OR REPLACE FUNCTION accounting.treasury_regular_application_origin(p_application UUID)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
DECLARE a treasury.applications%ROWTYPE; r treasury.receipts%ROWTYPE; t lending.collection_transactions%ROWTYPE;
 loan lending.loans%ROWTYPE; anchor JSONB; prefixes JSONB; ledger JSONB; history JSONB; measured JSONB;
 rate NUMERIC; initial NUMERIC; cumulative NUMERIC; prior_interest NUMERIC:=0; prior_allowance NUMERIC:=0;
 gross_raw NUMERIC; cash_interest NUMERIC; cash_principal NUMERIC; previous_cutoff DATE; text_id TEXT;
BEGIN
 SELECT * INTO a FROM treasury.applications WHERE id=p_application;
 IF a.id IS NULL OR jsonb_typeof(a.source_result->'transaction_ids') IS DISTINCT FROM 'array' THEN RETURN NULL; END IF;
 IF jsonb_array_length(a.source_result->'transaction_ids')<>1 THEN RETURN NULL; END IF;
 text_id:=a.source_result->'transaction_ids'->>0;
 IF text_id IS NULL OR text_id !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN RETURN NULL; END IF;
 SELECT * INTO t FROM lending.collection_transactions WHERE id=text_id::uuid;
 SELECT * INTO r FROM treasury.receipts WHERE id=a.receipt_id;
 SELECT * INTO loan FROM lending.loans WHERE id=t.loan_id;
 IF t.id IS NULL OR r.id IS NULL OR loan.id IS NULL THEN RETURN NULL; END IF;
 SELECT to_jsonb(x)-ARRAY['client_name','client_code','loan_number'] INTO anchor
 FROM accounting.greenfield_regular_eir_anchor_readiness x WHERE x.loan_id=t.loan_id;
 IF (SELECT count(*) FROM accounting.greenfield_regular_eir_anchor_readiness WHERE loan_id=t.loan_id)<>1 THEN anchor:=NULL; END IF;
 SELECT coalesce(jsonb_agg(jsonb_build_object('posting_id',p.id,'preparation',to_jsonb(s),'posting',to_jsonb(p),
  'period_start',f.start_date,'period_end',f.end_date,
  'exact',accounting.period_elapsed_loan_assessment_exact(p.fiscal_period_id,p.loan_id)) ORDER BY p.as_of_date,p.id),'[]'::jsonb)
 INTO prefixes FROM accounting.loan_elapsed_assessment_postings p
 JOIN accounting.loan_elapsed_assessment_preparations s ON s.id=p.preparation_id
 JOIN accounting.fiscal_periods f ON f.id=p.fiscal_period_id
 WHERE p.loan_id=t.loan_id AND p.as_of_date<t.collection_date;
 SELECT (s.source_snapshot#>>'{eir,cumulative_interest}')::numeric,(s.measurement_snapshot->>'ecl_amount')::numeric,p.as_of_date
 INTO prior_interest,prior_allowance,previous_cutoff FROM accounting.loan_elapsed_assessment_postings p
 JOIN accounting.loan_elapsed_assessment_preparations s ON s.id=p.preparation_id
 WHERE p.loan_id=t.loan_id AND p.as_of_date<t.collection_date ORDER BY p.as_of_date DESC,p.id DESC LIMIT 1;
 prior_interest:=coalesce(prior_interest,0); prior_allowance:=coalesce(prior_allowance,0);
 IF anchor IS NOT NULL THEN
  rate:=(anchor->>'daily_eir')::numeric; initial:=(anchor->>'initial_gross_carrying_amount')::numeric;
  IF rate>0 AND initial>0 AND t.collection_date>(anchor->>'anchor_date')::date
   AND t.collection_date-(anchor->>'anchor_date')::date<=3660 THEN
   -- Fiscal cutoffs never reset this original raw compounding basis. This is
   -- the first-cash specialization of allocate_event_date_eir_cash.
   gross_raw:=initial*power(1::numeric+rate,(t.collection_date-(anchor->>'anchor_date')::date)::numeric);
   cumulative:=round(gross_raw-initial,2); cash_interest:=least(t.amount,cumulative); cash_principal:=t.amount-cash_interest;
   measured:=jsonb_build_object('daily_eir',rate,'anchor_date',anchor->'anchor_date','gross_carrying_raw',gross_raw,
    'raw_cumulative_interest',gross_raw-initial,'cumulative_interest',cumulative::numeric(18,2)::text,
    'prior_recognized_interest',prior_interest::numeric(18,2)::text,
    'incremental_interest',(cumulative-prior_interest)::numeric(18,2)::text,'prior_cutoff',previous_cutoff,
    'initial_loan_component',initial::numeric(18,2)::text,'prior_allowance',prior_allowance::numeric(18,2)::text,
    'cash_to_accrued_interest',cash_interest::numeric(18,2)::text,'cash_to_loan_component',cash_principal::numeric(18,2)::text,
    'gross_carrying_before',round(gross_raw,2)::numeric(18,2)::text,
    'loan_component_after',(round(gross_raw,2)-cumulative-cash_principal)::numeric(18,2)::text,
    'accrued_interest_after',(cumulative-cash_interest)::numeric(18,2)::text);
  END IF;
 END IF;
 SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY x.collection_date,x.accepted_at,x.id),'[]'::jsonb) INTO history
 FROM lending.collection_transactions x WHERE x.loan_id=t.loan_id
  AND (x.collection_date,x.accepted_at,x.id)<=(t.collection_date,t.accepted_at,t.id);
 SELECT coalesce(jsonb_agg(jsonb_build_object('journal',to_jsonb(j),'line',to_jsonb(l),
  'account',accounting.treasury_gl_account_snapshot(l.account_id)-ARRAY['name','is_active']) ORDER BY j.posting_date,j.id,l.line_number),'[]'::jsonb)
 INTO ledger FROM accounting.journal_entries j JOIN accounting.journal_lines l ON l.journal_entry_id=j.id
 WHERE j.status='posted' AND j.posting_date<=t.collection_date AND l.loan_id=t.loan_id
  AND NOT EXISTS(SELECT 1 FROM accounting.treasury_application_postings own WHERE own.application_id=a.id AND own.journal_entry_id=j.id);
 RETURN jsonb_build_object('application',to_jsonb(a),'transaction',to_jsonb(t),
  'receipt',jsonb_build_object('id',r.id,'event_id',r.event_id,'account_id',r.account_id,'ledger_context_id',r.ledger_context_id,
   'client_id',r.client_id,'amount',r.amount::text,'effective_at',r.effective_at,'refunded_amount',r.refunded_amount::text),
  'revisions',(SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY x.version),'[]'::jsonb) FROM treasury.event_revisions x WHERE x.event_id=r.event_id),
  'loan',jsonb_build_object('id',loan.id,'client_id',loan.client_id,'loan_type_id',loan.loan_type_id,'principal',loan.principal,
   'daily_amount',loan.daily_amount,'interest_rate',loan.interest_rate,'date_released',loan.date_released,'due_date',loan.due_date),
  'anchor',anchor,'schedule',(SELECT to_jsonb(x) FROM lending.loan_contract_schedules x WHERE x.id=(anchor->>'schedule_id')::uuid),
  'registration',(SELECT to_jsonb(x) FROM lending.loan_contract_schedule_registrations x WHERE x.schedule_id=(anchor->>'schedule_id')::uuid),
  'installments',(SELECT jsonb_agg(to_jsonb(x) ORDER BY x.installment_number) FROM lending.loan_contract_installments x WHERE x.schedule_id=(anchor->>'schedule_id')::uuid),
  'allocations',(SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY x.installment_id),'[]'::jsonb) FROM lending.loan_installment_payment_allocations x WHERE x.transaction_id=t.id),
  'collection_history',history,'prefix_claims',prefixes,'measurement',measured,'loan_ledger',ledger,
  'renewals',(SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY x.id),'[]'::jsonb) FROM lending.client_renewal_requests x WHERE x.loan_id=t.loan_id),
  'contract_schedule_count',(SELECT count(*) FROM lending.loan_contract_schedules WHERE loan_id=t.loan_id));
END $$;

CREATE OR REPLACE FUNCTION accounting.treasury_application_origin(p_application_id UUID)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
DECLARE mode TEXT;
BEGIN
 SELECT lt.calculation_mode INTO mode FROM treasury.applications a
 JOIN lending.collection_transactions t ON t.funding_receipt_id=a.receipt_id AND a.source_result->'transaction_ids' ? t.id::text
 JOIN lending.loans l ON l.id=t.loan_id JOIN lending.loan_types lt ON lt.id=l.loan_type_id WHERE a.id=p_application_id LIMIT 1;
 IF mode='fixed_daily' THEN RETURN accounting.treasury_regular_application_origin(p_application_id); END IF;
 RETURN accounting.treasury_application_7x7_origin(p_application_id);
END $$;

CREATE OR REPLACE FUNCTION accounting.treasury_regular_application_coordinates(p_application UUID)
RETURNS JSONB LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
DECLARE a treasury.applications%ROWTYPE; r treasury.receipts%ROWTYPE; t lending.collection_transactions%ROWTYPE;
 period accounting.fiscal_periods%ROWTYPE; cash accounting.treasury_receipt_postings%ROWTYPE;
 cash_p accounting.treasury_receipt_preparations%ROWTYPE; wallet UUID; book UUID; liability UUID; origin JSONB;
 measured JSONB; anchor JSONB; prefixes JSONB; prefix JSONB; allowed UUID[]; anchor_day DATE; previous_end DATE;
 prior_interest NUMERIC; prior_allowance NUMERIC; cumulative NUMERIC; incremental NUMERIC; initial NUMERIC;
 b1100 NUMERIC; b1110 NUMERIC; b1120 NUMERIC; b1190 NUMERIC; consumed NUMERIC; balance NUMERIC; expected NUMERIC;
 liability_ledger JSONB; lines JSONB; result JSONB; credit_interest NUMERIC; credit_principal NUMERIC;
BEGIN
 IF current_setting('transaction_isolation')<>'read committed' THEN RAISE EXCEPTION 'Regular application requires READ COMMITTED.' USING ERRCODE='55000'; END IF;
 SELECT account_id INTO wallet FROM treasury.applications WHERE id=p_application;
 PERFORM id FROM treasury.accounts WHERE id=wallet FOR UPDATE;
 book:=accounting.require_book_treasury_account(wallet);
 SELECT * INTO a FROM treasury.applications WHERE id=p_application FOR UPDATE;
 SELECT * INTO r FROM treasury.receipts WHERE id=a.receipt_id FOR UPDATE;
 PERFORM id FROM treasury.events WHERE id=r.event_id FOR UPDATE;
 PERFORM accounting.lock_elapsed_assessment_sources();
 LOCK TABLE treasury.applications,treasury.receipts,treasury.events,treasury.event_revisions,treasury.movement_lines,
  treasury.source_links,accounting.treasury_cash_mappings,accounting.treasury_receipt_preparations,
  accounting.treasury_receipt_postings,accounting.treasury_application_preparations,accounting.treasury_application_postings IN SHARE MODE;
 origin:=accounting.treasury_regular_application_origin(a.id);
 IF origin IS NULL OR a.status<>'active' OR a.source_result->>'status' IS DISTINCT FROM 'recorded'
  OR a.source_result->>'amount' IS DISTINCT FROM a.amount::text THEN RAISE EXCEPTION 'One exact active Regular Treasury application is required.' USING ERRCODE='55000'; END IF;
 SELECT * INTO t FROM lending.collection_transactions WHERE id=(origin#>>'{transaction,id}')::uuid FOR UPDATE;
 IF NOT EXISTS(SELECT 1 FROM lending.loans l JOIN lending.loan_types lt ON lt.id=l.loan_type_id
    WHERE l.id=t.loan_id AND l.client_id=r.client_id AND lt.calculation_mode='fixed_daily')
  OR a.account_id<>r.account_id OR a.ledger_context_id<>r.ledger_context_id OR t.funding_source<>'treasury_receipt'
  OR t.funding_receipt_id IS DISTINCT FROM r.id OR t.funding_account_id IS DISTINCT FROM wallet OR t.client_id<>r.client_id
  OR t.amount<>a.amount OR t.applied_amount<>a.amount OR t.unallocated_amount<>0 OR t.entry_type NOT IN('payment','advance')
  OR t.is_voided OR r.refunded_amount<>0 OR t.collection_date<(r.effective_at AT TIME ZONE 'Asia/Manila')::date
  OR jsonb_array_length(origin->'revisions')<>0 OR EXISTS(SELECT 1 FROM treasury.source_links WHERE event_id=r.event_id)
  OR EXISTS(SELECT 1 FROM treasury.applications other WHERE other.id<>a.id AND other.source_result->'transaction_ids' ? t.id::text)
  OR (SELECT coalesce(sum(amount),0) FROM treasury.applications WHERE receipt_id=r.id AND status='active')<>r.applied_amount THEN
  RAISE EXCEPTION 'Regular application source is unsupported, corrected or does not reconcile.' USING ERRCODE='55000'; END IF;
 IF EXISTS(SELECT 1 FROM jsonb_array_elements(origin->'collection_history') x WHERE x->>'id'<>t.id::text
    AND ((x->>'amount')::numeric>0 OR x->>'entry_type' IN('payment','advance')))
  OR EXISTS(SELECT 1 FROM lending.collection_transaction_voids v JOIN lending.collection_transactions x ON x.id=v.transaction_id WHERE x.loan_id=t.loan_id) THEN
  RAISE EXCEPTION 'Original first cash adapter requires no prior cash or reversed source history.' USING ERRCODE='55000'; END IF;
 anchor:=origin->'anchor'; measured:=origin->'measurement'; prefixes:=origin->'prefix_claims';
 IF anchor IS NULL OR anchor='null'::jsonb OR anchor->>'readiness_status' IS DISTINCT FROM 'greenfield_regular_eir_anchor_ready'
  OR measured IS NULL OR measured='null'::jsonb OR (origin->>'contract_schedule_count')::integer<>1
  OR jsonb_array_length(origin->'renewals')<>0 OR (origin#>>'{loan,due_date}')::date<>(anchor->>'contractual_due_date')::date
  OR t.collection_date>(anchor->>'contractual_due_date')::date
  OR EXISTS(SELECT 1 FROM lending.loan_renewal_execution_events x WHERE x.old_loan_id=t.loan_id OR x.new_loan_id=t.loan_id)
  OR EXISTS(SELECT 1 FROM accounting.ecl_accounting_writeoffs WHERE loan_id=t.loan_id)
  OR EXISTS(SELECT 1 FROM accounting.ecl_allowance_remeasurements WHERE loan_id=t.loan_id)
  OR EXISTS(SELECT 1 FROM accounting.ecl_allowance_postings WHERE loan_id=t.loan_id) THEN
  RAISE EXCEPTION 'Exact original protected Regular release and unchanged signed schedule are required; other origins or corrections need another adapter.' USING ERRCODE='55000'; END IF;
 IF NOT EXISTS(SELECT 1 FROM accounting.journal_entries j JOIN accounting.journal_lines l ON l.journal_entry_id=j.id
   JOIN accounting.accounts ac ON ac.id=l.account_id WHERE j.id=(anchor->>'journal_entry_id')::uuid
    AND l.credit=(anchor->>'initial_gross_carrying_amount')::numeric AND ac.account_type='asset' AND ac.normal_balance='debit' AND ac.is_posting
    AND (ac.code,ac.system_key) IN(('1010','cash_office'),('1030','cash_bank_gcash'))) THEN
  RAISE EXCEPTION 'Original protected release cash chart meaning is incompatible.' USING ERRCODE='55000'; END IF;
 IF (SELECT coalesce(sum(amount_applied),0) FROM lending.loan_installment_payment_allocations WHERE transaction_id=t.id)<>a.amount
  OR EXISTS(SELECT 1 FROM lending.loan_installment_payment_allocations pa JOIN lending.loan_contract_installments i ON i.id=pa.installment_id
    WHERE pa.transaction_id=t.id AND i.schedule_id IS DISTINCT FROM (anchor->>'schedule_id')::uuid) THEN
  RAISE EXCEPTION 'Exact original signed-installment application evidence is required.' USING ERRCODE='55000'; END IF;
 SELECT * INTO period FROM accounting.fiscal_periods WHERE t.collection_date BETWEEN start_date AND end_date FOR UPDATE;
 IF period.id IS NULL OR period.status<>'open' THEN RAISE EXCEPTION 'Regular application requires its open fiscal period.' USING ERRCODE='55000'; END IF;
 anchor_day:=(anchor->>'anchor_date')::date; initial:=(measured->>'initial_loan_component')::numeric;
 prior_interest:=(measured->>'prior_recognized_interest')::numeric; prior_allowance:=(measured->>'prior_allowance')::numeric;
 cumulative:=(measured->>'cumulative_interest')::numeric; incremental:=(measured->>'incremental_interest')::numeric;
 credit_interest:=(measured->>'cash_to_accrued_interest')::numeric; credit_principal:=(measured->>'cash_to_loan_component')::numeric;
 allowed:=ARRAY[(anchor->>'journal_entry_id')::uuid]; previous_end:=NULL;
 FOR prefix IN SELECT value FROM jsonb_array_elements(prefixes) LOOP
  IF prefix->>'exact' IS DISTINCT FROM 'true' OR prefix#>>'{posting,book_id}'<>book::text
   OR (prefix->>'period_end')::date<>(prefix#>>'{posting,as_of_date}')::date
   OR (prefix->>'period_end')::date>=period.start_date
   OR (previous_end IS NULL AND (prefix->>'period_start')::date>anchor_day+1)
   OR (previous_end IS NOT NULL AND (prefix->>'period_start')::date<>previous_end+1)
   OR prefix#>>'{preparation,source_snapshot,anchor,anchor_source_key}' IS DISTINCT FROM anchor->>'anchor_source_key' THEN
   RAISE EXCEPTION 'Prior fiscal prefix is not exact or contiguous with the original Regular source.' USING ERRCODE='55000'; END IF;
  previous_end:=(prefix->>'period_end')::date;
  allowed:=allowed||ARRAY[(prefix#>>'{posting,eir_journal_entry_id}')::uuid,(prefix#>>'{posting,allowance_journal_entry_id}')::uuid];
 END LOOP;
 IF (previous_end IS NULL AND anchor_day<period.start_date)
  OR (previous_end IS NOT NULL AND previous_end<>period.start_date-1) OR incremental<0
  OR a.amount>(measured->>'gross_carrying_before')::numeric THEN
  RAISE EXCEPTION 'Missing exact fiscal prefix or cash exceeds original carrying amount.' USING ERRCODE='55000'; END IF;
 IF EXISTS(SELECT 1 FROM accounting.journal_entries j JOIN accounting.journal_lines l ON l.journal_entry_id=j.id
  WHERE j.status='posted' AND l.loan_id=t.loan_id AND j.posting_date>t.collection_date) THEN
  RAISE EXCEPTION 'Later loan accounting requires a backdated correction adapter.' USING ERRCODE='55000'; END IF;
 SELECT coalesce(sum(l.debit-l.credit) FILTER(WHERE ac.code='1100'),0),coalesce(sum(l.debit-l.credit) FILTER(WHERE ac.code='1110'),0),
  coalesce(sum(l.debit-l.credit) FILTER(WHERE ac.code='1120'),0),coalesce(sum(l.credit-l.debit) FILTER(WHERE ac.code='1190'),0)
 INTO b1100,b1110,b1120,b1190 FROM accounting.journal_entries j JOIN accounting.journal_lines l ON l.journal_entry_id=j.id
 JOIN accounting.accounts ac ON ac.id=l.account_id WHERE j.status='posted' AND l.loan_id=t.loan_id AND j.posting_date<=t.collection_date;
 IF b1100<>initial OR b1110<>0 OR b1120<>prior_interest OR b1190<>prior_allowance
  OR EXISTS(SELECT 1 FROM accounting.journal_entries j JOIN accounting.journal_lines l ON l.journal_entry_id=j.id
   WHERE j.status='posted' AND l.loan_id=t.loan_id AND j.posting_date<=t.collection_date AND NOT j.id=ANY(array_remove(allowed,NULL))) THEN
  RAISE EXCEPTION 'Regular loan GL controls do not match exact origin and fiscal prefix claims.' USING ERRCODE='55000'; END IF;
 SELECT * INTO cash FROM accounting.treasury_receipt_postings WHERE receipt_id=r.id;
 SELECT * INTO cash_p FROM accounting.treasury_receipt_preparations WHERE id=cash.preparation_id;
 IF cash.id IS NULL OR cash.book_id<>book OR NOT EXISTS(SELECT 1 FROM accounting.treasury_receipt_posting_status
  WHERE receipt_id=r.id AND exact_posted AND NOT correction_pending) THEN
  RAISE EXCEPTION 'Exact posted receipt cash and unapplied borrower liability are required first.' USING ERRCODE='55000'; END IF;
 liability:=(cash_p.snapshot->>'liability_account_id')::uuid;
 IF NOT EXISTS(SELECT 1 FROM accounting.accounts WHERE id=liability AND code='2200' AND system_key='unapplied_borrower_funds'
  AND account_type='liability' AND normal_balance='credit' AND is_active AND is_posting)
  OR (SELECT count(*) FROM accounting.accounts WHERE is_active AND is_posting AND (code,system_key,account_type,normal_balance) IN(
   ('1100','loans_receivable_regular','asset','debit'),('1120','accrued_interest_receivable','asset','debit'),('4000','interest_income_regular','income','credit')))<>3 THEN
  RAISE EXCEPTION 'Regular application chart definition or original liability mapping is unavailable.' USING ERRCODE='55000'; END IF;
 SELECT coalesce(sum(l.credit-l.debit),0),coalesce(jsonb_agg(jsonb_build_object('journal_id',j.id,'date',j.posting_date,'line',to_jsonb(l)) ORDER BY j.id,l.line_number),'[]'::jsonb)
 INTO balance,liability_ledger FROM accounting.journal_entries j JOIN accounting.journal_lines l ON l.journal_entry_id=j.id
 WHERE j.status='posted' AND j.posting_date<=t.collection_date AND l.account_id=liability AND l.client_id=r.client_id;
 SELECT coalesce(sum((rp.snapshot->>'amount')::numeric),0) INTO expected FROM accounting.treasury_receipt_postings p
 JOIN accounting.treasury_receipt_preparations rp ON rp.id=p.preparation_id
 WHERE (rp.snapshot->>'client_id')::uuid=r.client_id AND (rp.snapshot->>'posting_date')::date<=t.collection_date;
 SELECT expected-coalesce(sum(p.amount),0) INTO expected FROM accounting.treasury_application_postings p
 JOIN accounting.treasury_application_preparations ap ON ap.id=p.preparation_id
 WHERE (ap.snapshot->>'client_id')::uuid=r.client_id AND (ap.snapshot->>'posting_date')::date<=t.collection_date;
 IF balance<>expected OR balance<a.amount
  OR EXISTS(SELECT 1 FROM accounting.journal_entries j JOIN accounting.journal_lines l ON l.journal_entry_id=j.id
   WHERE j.status='posted' AND j.posting_date<=t.collection_date AND l.account_id=liability AND l.client_id=r.client_id
    AND NOT EXISTS(SELECT 1 FROM accounting.treasury_receipt_postings p WHERE p.journal_entry_id=j.id)
    AND NOT EXISTS(SELECT 1 FROM accounting.treasury_application_postings p WHERE p.journal_entry_id=j.id))
  OR EXISTS(SELECT 1 FROM accounting.treasury_receipt_posting_status s JOIN treasury.receipts rr ON rr.id=s.receipt_id
   WHERE rr.client_id=r.client_id AND s.posting_date<=t.collection_date AND (NOT s.exact_posted OR s.correction_pending))
  OR EXISTS(SELECT 1 FROM accounting.treasury_application_posting_status s JOIN treasury.receipts rr ON rr.id=s.receipt_id
   WHERE rr.client_id=r.client_id AND s.posting_date<=t.collection_date AND (NOT s.exact_posted OR s.correction_pending)) THEN
  RAISE EXCEPTION 'Borrower liability GL requires exact retained receipt and application reconciliation.' USING ERRCODE='55000'; END IF;
 SELECT coalesce(sum(amount),0) INTO consumed FROM accounting.treasury_application_postings WHERE receipt_id=r.id;
 IF consumed+a.amount>r.amount THEN RAISE EXCEPTION 'Application exceeds remaining posted receipt liability.' USING ERRCODE='55000'; END IF;
 SELECT jsonb_agg(jsonb_build_object('line_number',x.n,'journal_component',x.component,'account_id',ac.id,'account_code',x.code,
  'account_snapshot',accounting.treasury_gl_account_snapshot(ac.id),'debit',x.dr::numeric(18,2)::text,'credit',x.cr::numeric(18,2)::text,
  'client_id',r.client_id,'loan_id',CASE WHEN x.code='2200' THEN NULL ELSE t.loan_id END) ORDER BY x.n)
 INTO lines FROM (VALUES(10,'unapplied_funds_debit','2200',a.amount,0::numeric),
  (20,'incremental_eir_debit','1120',incremental,0::numeric),(30,'incremental_eir_income','4000',0::numeric,incremental),
  (40,'collection_accrued_interest_credit','1120',0::numeric,credit_interest),
  (50,'collection_loan_component_credit','1100',0::numeric,credit_principal)) x(n,component,code,dr,cr)
 JOIN accounting.accounts ac ON ac.code=x.code WHERE x.dr+x.cr>0;
 IF lines IS NULL OR jsonb_array_length(lines) NOT BETWEEN 2 AND 5
  OR (SELECT sum((x->>'debit')::numeric)-sum((x->>'credit')::numeric) FROM jsonb_array_elements(lines) x)<>0 THEN
  RAISE EXCEPTION 'Original Regular application coordinates are not balanced.' USING ERRCODE='23514'; END IF;
 result:=jsonb_build_object('product_model','fixed_daily','accounting_policy_version','treasury_regular_original_first_cash_v1',
  'book_id',book,'application_id',a.id,'transaction_id',t.id,'receipt_id',r.id,'event_id',r.event_id,'treasury_account_id',wallet,
  'ledger_context_id',r.ledger_context_id,'loan_id',t.loan_id,'client_id',r.client_id,'posting_date',t.collection_date,
  'fiscal_period_id',period.id,'amount',a.amount::numeric(18,2)::text,'source_event_key','treasury_application:'||a.id::text,
  'receipt_posting_id',cash.id,'receipt_source_digest',cash.source_digest,'receipt_version',r.version,
  'liability_remaining',(r.amount-consumed)::numeric(18,2)::text,'evidence',cash_p.snapshot->'evidence','origin',origin,
  'measurement',measured,'prefix_claims',prefixes,'lines',lines,'ledger_evidence',origin->'loan_ledger',
  'borrower_liability_balance',balance::numeric(18,2)::text,'liability_ledger_evidence',liability_ledger);
 RETURN result||jsonb_build_object('source_digest',encode(sha256(convert_to(result::text,'UTF8')),'hex'));
END $$;

CREATE OR REPLACE FUNCTION accounting.treasury_application_coordinates(p_application_id UUID)
RETURNS JSONB LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE mode TEXT;
BEGIN
 SELECT lt.calculation_mode INTO mode FROM treasury.applications a
 JOIN lending.collection_transactions t ON t.funding_receipt_id=a.receipt_id AND a.source_result->'transaction_ids' ? t.id::text
 JOIN lending.loans l ON l.id=t.loan_id JOIN lending.loan_types lt ON lt.id=l.loan_type_id WHERE a.id=p_application_id LIMIT 1;
 IF mode='fixed_daily' THEN RETURN accounting.treasury_regular_application_coordinates(p_application_id); END IF;
 RETURN accounting.treasury_application_7x7_coordinates(p_application_id);
END $$;

-- Rebind the existing view's origin call to the dispatch function after rename.
-- Preserve its shape/OID and all immutable original audit comparisons.
DO $$ DECLARE definition TEXT; BEGIN
 definition:=pg_get_viewdef('accounting.treasury_application_posting_status'::regclass,true);
 definition:=replace(definition,'accounting.treasury_application_7x7_origin(', 'accounting.treasury_application_origin(');
 EXECUTE 'CREATE OR REPLACE VIEW accounting.treasury_application_posting_status AS '||definition;
END $$;

CREATE OR REPLACE FUNCTION accounting.regular_application_prefix_admitted(p_journal UUID)
RETURNS BOOLEAN LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE p accounting.treasury_application_preparations%ROWTYPE; j accounting.journal_entries%ROWTYPE; current_source JSONB;
BEGIN
 SELECT * INTO p FROM accounting.treasury_application_preparations WHERE id::text=current_setting('accounting.treasury_application_post',true);
 SELECT * INTO j FROM accounting.journal_entries WHERE id=p_journal;
 IF p.id IS NULL OR p.snapshot->>'product_model' IS DISTINCT FROM 'fixed_daily'
  OR p.snapshot->>'accounting_policy_version' IS DISTINCT FROM 'treasury_regular_original_first_cash_v1'
  OR j.source_type IS DISTINCT FROM 'treasury_receipt_application' OR j.source_reference IS DISTINCT FROM p.application_id::text
  OR j.source_event_key IS DISTINCT FROM p.snapshot->>'source_event_key' OR j.created_by_user_id IS DISTINCT FROM p.actor_user_id
  OR j.fiscal_period_id IS DISTINCT FROM (p.snapshot->>'fiscal_period_id')::uuid OR j.posting_date IS DISTINCT FROM (p.snapshot->>'posting_date')::date
  OR j.reversal_of_entry_id IS NOT NULL THEN RETURN false; END IF;
 current_source:=accounting.treasury_regular_application_coordinates(p.application_id);
 RETURN current_source->>'source_digest'=p.source_digest AND current_source-'source_digest'=p.snapshot
  AND (SELECT count(*) FROM accounting.journal_lines WHERE journal_entry_id=j.id)=jsonb_array_length(p.snapshot->'lines')
  AND NOT EXISTS(SELECT 1 FROM jsonb_to_recordset(p.snapshot->'lines') x(line_number INT,account_id UUID,debit NUMERIC,credit NUMERIC,client_id UUID,loan_id UUID)
   LEFT JOIN accounting.journal_lines l ON l.journal_entry_id=j.id AND l.line_number=x.line_number
   WHERE l.id IS NULL OR (l.account_id,l.debit,l.credit,l.client_id,l.loan_id) IS DISTINCT FROM(x.account_id,x.debit,x.credit,x.client_id,x.loan_id));
END $$;

-- Preserve153's exact historical source guard; only this preparation-bound
-- native path can recognize a remaining cash interval after an exact prefix.
DO $$ DECLARE definition TEXT; old_clause TEXT; BEGIN
 definition:=pg_get_functiondef('accounting.guard_elapsed_assessment_journal()'::regprocedure);
 old_clause:='WHERE l.journal_entry_id=NEW.id AND account.code IN(''1100'',''1110'',''1120'',''1190'')) THEN';
 IF position('accounting.regular_application_prefix_admitted(NEW.id)' IN definition)=0 THEN
  IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Expected protected153 source guard is unavailable; Regular extension cannot replace unknown semantics.'; END IF;
  definition:=replace(definition,old_clause,
   'WHERE l.journal_entry_id=NEW.id AND account.code IN(''1100'',''1110'',''1120'',''1190'')) AND NOT accounting.regular_application_prefix_admitted(NEW.id) THEN');
  EXECUTE definition;
 END IF;
END $$;

CREATE OR REPLACE FUNCTION accounting.assert_regular_application_committed()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE p accounting.treasury_application_preparations%ROWTYPE; journal UUID;
BEGIN
 IF TG_TABLE_NAME='journal_entries' THEN
  IF NEW.source_type IS DISTINCT FROM 'treasury_receipt_application' THEN RETURN NEW; END IF;
  journal:=NEW.id;
 ELSE journal:=NEW.journal_entry_id; END IF;
 SELECT preparation.* INTO p FROM accounting.treasury_application_preparations preparation
 JOIN accounting.treasury_application_postings posted ON posted.preparation_id=preparation.id WHERE posted.journal_entry_id=journal;
 IF p.snapshot->>'accounting_policy_version' IS DISTINCT FROM 'treasury_regular_original_first_cash_v1' THEN RETURN NEW; END IF;
 IF NOT EXISTS(SELECT 1 FROM accounting.treasury_application_posting_status s WHERE s.journal_entry_id=journal AND s.exact_posted AND NOT s.correction_pending)
  OR NOT EXISTS(SELECT 1 FROM accounting.treasury_receipt_posting_status s WHERE s.receipt_id=p.receipt_id AND s.exact_posted AND NOT s.correction_pending) THEN
  RAISE EXCEPTION 'Regular application source or fiscal prefix changed before commit.' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS regular_application_journal_commit ON accounting.journal_entries;
CREATE CONSTRAINT TRIGGER regular_application_journal_commit AFTER INSERT OR UPDATE ON accounting.journal_entries
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION accounting.assert_regular_application_committed();
DROP TRIGGER IF EXISTS regular_application_posting_commit ON accounting.treasury_application_postings;
CREATE CONSTRAINT TRIGGER regular_application_posting_commit AFTER INSERT ON accounting.treasury_application_postings
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION accounting.assert_regular_application_committed();

-- A product-neutral description is the only change to the shared0146 writer.
DO $$ DECLARE definition TEXT; BEGIN
 definition:=pg_get_functiondef('accounting.post_treasury_application(uuid,text,text,uuid)'::regprocedure);
 definition:=replace(definition,'Apply retained borrower funds using protected 7x7 EIR','Apply retained borrower funds using protected product EIR');
 EXECUTE definition;
END $$;

DO $$ DECLARE item RECORD; role_name TEXT; BEGIN
 FOR item IN SELECT p.oid::regprocedure signature FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
 WHERE n.nspname='accounting' AND p.proname IN('treasury_regular_application_origin','treasury_regular_application_coordinates',
  'treasury_application_7x7_origin','treasury_application_7x7_coordinates','treasury_application_origin','treasury_application_coordinates',
  'regular_application_prefix_admitted','guard_elapsed_assessment_journal','assert_regular_application_committed','post_treasury_application') LOOP
  EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC',item.signature);
  FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
   IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN EXECUTE format('REVOKE ALL ON FUNCTION %s FROM %I',item.signature,role_name); END IF;
  END LOOP;
 END LOOP;
END $$;
COMMIT;
