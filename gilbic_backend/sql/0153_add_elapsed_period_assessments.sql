BEGIN;

-- Historical economic dates are distinct from actual calculation/retention time.
-- This first policy supports protected original Regular no-cash segments only.
CREATE TABLE IF NOT EXISTS accounting.loan_elapsed_assessment_preparations (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 book_id UUID NOT NULL REFERENCES accounting.book_identity(id) ON DELETE RESTRICT,
 fiscal_period_id UUID NOT NULL REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
 loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
 client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
 as_of_date DATE NOT NULL,
 source_digest TEXT NOT NULL CHECK(source_digest ~ '^[0-9a-f]{64}$'),
 confirmation_digest TEXT NOT NULL CHECK(confirmation_digest ~ '^[0-9a-f]{64}$'),
 source_snapshot JSONB NOT NULL CHECK(jsonb_typeof(source_snapshot)='object'),
 risk_review JSONB NOT NULL CHECK(jsonb_typeof(risk_review)='object'),
 scenarios JSONB NOT NULL CHECK(jsonb_typeof(scenarios)='array'),
 measurement_snapshot JSONB NOT NULL CHECK(jsonb_typeof(measurement_snapshot)='object'),
 review_rationale TEXT NOT NULL CHECK(length(btrim(review_rationale))>=20),
 prepared_by UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
 calculated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(book_id,fiscal_period_id,loan_id,confirmation_digest)
);
CREATE TABLE IF NOT EXISTS accounting.loan_elapsed_assessment_postings (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 preparation_id UUID NOT NULL UNIQUE REFERENCES accounting.loan_elapsed_assessment_preparations(id) ON DELETE RESTRICT,
 book_id UUID NOT NULL REFERENCES accounting.book_identity(id) ON DELETE RESTRICT,
 fiscal_period_id UUID NOT NULL REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
 loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
 as_of_date DATE NOT NULL,
 eir_journal_entry_id UUID UNIQUE REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
 allowance_journal_entry_id UUID UNIQUE REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
 confirmation_digest TEXT NOT NULL CHECK(confirmation_digest ~ '^[0-9a-f]{64}$'),
 posted_by UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
 posted_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(book_id,loan_id,as_of_date)
);
ALTER TABLE accounting.loan_elapsed_assessment_preparations ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounting.loan_elapsed_assessment_postings ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION accounting.guard_elapsed_assessment_audit()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF TG_OP='INSERT' AND current_setting('accounting.elapsed_assessment_write',true)=TG_TABLE_NAME THEN RETURN NEW; END IF;
 RAISE EXCEPTION 'Historical assessment audits are immutable and require their protected workflow.' USING ERRCODE='55000';
END $$;

CREATE OR REPLACE FUNCTION accounting.calculate_elapsed_assessment_ecl(p_source JSONB,p_risk JSONB,p_scenarios JSONB)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
DECLARE cutoff DATE:=(p_source->>'cutoff_date')::date; rate NUMERIC:=(p_source#>>'{eir,daily_eir}')::numeric;
 contractual NUMERIC:=(p_source->>'contractual_pv_raw')::numeric; scenario JSONB; flow JSONB; evidence RECORD;
 probability NUMERIC; probability_total NUMERIC:=0; expected_pv NUMERIC; weighted NUMERIC:=0; amount NUMERIC;
 cash_date DATE; key TEXT; seen_keys TEXT[]:=ARRAY[]::text[]; seen_dates DATE[]; seen_evidence UUID[];
 selected_evidence_id UUID; all_evidence UUID[]:=ARRAY[]::uuid[]; normalized JSONB:='[]'::jsonb;
 expected JSONB; evidence_rows JSONB; loss NUMERIC; normalized_risk JSONB;
BEGIN
 IF cutoff IS NULL OR rate IS NULL OR rate<=0 OR contractual IS NULL OR contractual<=0 THEN RAISE EXCEPTION 'Exact historical source measurement is required.'; END IF;
 IF p_risk IS NULL OR jsonb_typeof(p_risk)<>'object' OR EXISTS(SELECT 1 FROM jsonb_object_keys(p_risk) k
  WHERE k NOT IN('as_of_date','stage_label','default_label','write_off_label','recovery_label','primary_evidence_basis','evidence_reference','review_note'))
  OR p_risk->>'as_of_date' IS DISTINCT FROM cutoff::text OR p_risk->>'stage_label' IS DISTINCT FROM 'stage_1_12_month'
  OR p_risk->'default_label' IS DISTINCT FROM 'false'::jsonb OR p_risk->>'write_off_label' IS DISTINCT FROM 'none'
  OR p_risk->>'recovery_label' IS DISTINCT FROM 'none' OR p_risk->>'primary_evidence_basis' IS DISTINCT FROM 'contractual_dpd'
  OR length(btrim(coalesce(p_risk->>'evidence_reference','')))<3 OR length(btrim(coalesce(p_risk->>'review_note','')))<20
  OR (p_source->>'dpd')::integer>=30 THEN
  RAISE EXCEPTION 'Supported explicit as-of credit-risk review and contractual risk backstops are required.' USING ERRCODE='23514';
 END IF;
 normalized_risk:=p_risk||jsonb_build_object('schedule_id',p_source#>'{anchor,schedule_id}',
  'schedule_version',p_source#>'{anchor,schedule_version}','days_past_due',p_source->'dpd','due_unpaid_amount',p_source->'due_unpaid_amount');
 IF p_scenarios IS NULL OR jsonb_typeof(p_scenarios)<>'array' OR jsonb_array_length(p_scenarios) NOT BETWEEN 2 AND 20 THEN
  RAISE EXCEPTION 'Between2 and20 explicit evidence-supported scenarios are required.' USING ERRCODE='22023';
 END IF;
 FOR scenario IN SELECT value FROM jsonb_array_elements(p_scenarios) LOOP
  IF jsonb_typeof(scenario)<>'object' THEN RAISE EXCEPTION 'Every ECL scenario must be an object.' USING ERRCODE='22023'; END IF;
  IF EXISTS(SELECT 1 FROM jsonb_object_keys(scenario) k WHERE k NOT IN('scenario_key','probability','evidence_reference','management_rationale','forward_evidence_ids','expected_cash_flows')) THEN
   RAISE EXCEPTION 'Unsupported scenario input fields.' USING ERRCODE='22023'; END IF;
  key:=btrim(coalesce(scenario->>'scenario_key',''));
  IF key='' OR key=ANY(seen_keys) OR length(btrim(coalesce(scenario->>'evidence_reference','')))<3
   OR length(btrim(coalesce(scenario->>'management_rationale','')))<20 THEN RAISE EXCEPTION 'Unique scenario and substantive source evidence are required.' USING ERRCODE='22023'; END IF;
  seen_keys:=array_append(seen_keys,key);
  IF coalesce(jsonb_typeof(scenario->'probability'),'null') NOT IN('number','string')
   OR coalesce(scenario->>'probability','') !~ '^(0|1)(\.[0-9]{1,12})?$' THEN RAISE EXCEPTION 'Exact probability precision is required.' USING ERRCODE='22023'; END IF;
  probability:=(scenario->>'probability')::numeric;
  IF probability<=0 OR probability>1 OR probability<>round(probability,12) THEN RAISE EXCEPTION 'Scenario probability must be greater than zero and no more than one.' USING ERRCODE='22023'; END IF;
  probability_total:=probability_total+probability;
  IF jsonb_typeof(scenario->'forward_evidence_ids') IS DISTINCT FROM 'array' OR jsonb_array_length(scenario->'forward_evidence_ids')=0 THEN
   RAISE EXCEPTION 'Every historical scenario requires exact cutoff-eligible forward evidence.' USING ERRCODE='23514'; END IF;
  seen_evidence:=ARRAY[]::uuid[];
  FOR selected_evidence_id IN SELECT value::uuid FROM jsonb_array_elements_text(scenario->'forward_evidence_ids') LOOP
   IF selected_evidence_id=ANY(seen_evidence) THEN RAISE EXCEPTION 'Duplicate forward evidence identity.' USING ERRCODE='22023'; END IF;
   seen_evidence:=array_append(seen_evidence,selected_evidence_id);
   SELECT * INTO evidence FROM accounting.ecl_forward_looking_evidence e WHERE e.id=selected_evidence_id;
   IF NOT FOUND OR evidence.effective_date>cutoff OR evidence.observation_period_end IS NULL OR evidence.observation_period_end>cutoff
    OR (evidence.retrieved_at AT TIME ZONE 'Asia/Manila')::date>cutoff OR cutoff NOT BETWEEN evidence.forecast_period_start AND evidence.forecast_period_end
    OR EXISTS(SELECT 1 FROM accounting.ecl_forward_looking_evidence_revocations r WHERE r.evidence_id=selected_evidence_id)
    OR EXISTS(SELECT 1 FROM accounting.ecl_forward_looking_evidence newer WHERE newer.evidence_key=evidence.evidence_key
      AND newer.version>evidence.version AND newer.effective_date<=cutoff) THEN
    RAISE EXCEPTION 'Historical cutoff evidence is missing, corrected, revoked or available only after the as-of date.' USING ERRCODE='23514';
   END IF;
   all_evidence:=array_append(all_evidence,selected_evidence_id);
  END LOOP;
  IF jsonb_typeof(scenario->'expected_cash_flows') IS DISTINCT FROM 'array' OR jsonb_array_length(scenario->'expected_cash_flows')>3660 THEN
   RAISE EXCEPTION 'Explicit bounded expected cash-flow arrays are required.' USING ERRCODE='22023'; END IF;
  expected_pv:=0; expected:='[]'::jsonb; seen_dates:=ARRAY[]::date[];
  FOR flow IN SELECT value FROM jsonb_array_elements(scenario->'expected_cash_flows') LOOP
   IF jsonb_typeof(flow)<>'object' OR EXISTS(SELECT 1 FROM jsonb_object_keys(flow) k WHERE k NOT IN('cash_date','amount'))
    OR jsonb_typeof(flow->'cash_date') IS DISTINCT FROM 'string' OR coalesce(flow->>'cash_date','') !~ '^\d{4}-\d{2}-\d{2}$'
    OR coalesce(jsonb_typeof(flow->'amount'),'null') NOT IN('number','string') OR coalesce(flow->>'amount','') !~ '^[0-9]+(\.[0-9]{1,2})?$' THEN
    RAISE EXCEPTION 'Expected receipts require exact dates and currency-cent amounts.' USING ERRCODE='22023'; END IF;
   cash_date:=(flow->>'cash_date')::date; amount:=(flow->>'amount')::numeric(18,2);
   IF cash_date<cutoff OR cash_date>cutoff+3660 OR cash_date=ANY(seen_dates) OR amount<=0 THEN
    RAISE EXCEPTION 'Expected receipt dates must be unique and at or after cutoff, with positive exact amounts.' USING ERRCODE='22023'; END IF;
   seen_dates:=array_append(seen_dates,cash_date);
   expected_pv:=expected_pv+amount/power(1::numeric+rate,(cash_date-cutoff)::numeric);
   expected:=expected||jsonb_build_array(jsonb_build_object('cash_date',cash_date,'amount',amount));
  END LOOP;
  SELECT coalesce(jsonb_agg(value ORDER BY value->>'cash_date'),'[]'::jsonb) INTO expected FROM jsonb_array_elements(expected);
  loss:=greatest(contractual-expected_pv,0); weighted:=weighted+probability*loss;
  normalized:=normalized||jsonb_build_array(jsonb_build_object('scenario_key',key,'probability',probability,
   'evidence_reference',scenario->>'evidence_reference','management_rationale',scenario->>'management_rationale',
   'forward_evidence_ids',(SELECT jsonb_agg(x ORDER BY x) FROM unnest(seen_evidence) x),
   'expected_cash_flows',expected,'expected_cash_flow_pv_raw',expected_pv,'cash_shortfall_pv_raw',loss));
 END LOOP;
 IF probability_total<>1 THEN RAISE EXCEPTION 'Scenario probabilities must sum exactly to one.' USING ERRCODE='22023'; END IF;
 SELECT jsonb_agg(value ORDER BY value->>'scenario_key') INTO normalized FROM jsonb_array_elements(normalized);
 SELECT jsonb_agg(to_jsonb(e) ORDER BY e.id) INTO evidence_rows FROM accounting.ecl_forward_looking_evidence e WHERE e.id=ANY(all_evidence);
 RETURN jsonb_build_object('policy_version','historical_original_timing_cash_shortfall_v1','as_of_date',cutoff,
  'loss_horizon','12_month','risk_review',normalized_risk,'forward_evidence',evidence_rows,'scenarios',normalized,
  'original_daily_eir',rate,'contractual_cash_flows',p_source->'contractual_cash_flows',
  'contractual_pv_raw',contractual,'gross_carrying_amount',p_source->'gross_carrying_amount',
  'weighted_shortfall_raw',weighted,'ecl_amount',round(weighted,2),'prior_allowance',p_source->'prior_allowance',
  'allowance_delta',round(weighted,2)-(p_source->>'prior_allowance')::numeric);
END $$;

CREATE OR REPLACE FUNCTION accounting.lock_elapsed_assessment_sources()
RETURNS VOID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF current_setting('transaction_isolation')<>'read committed' THEN RAISE EXCEPTION 'Historical assessment writes require READ COMMITTED.' USING ERRCODE='55000'; END IF;
 -- Same source order as148/149, but acquire journal writer locks directly;
 -- two posters must not hold SHARE and then compete to upgrade it.
 LOCK TABLE lending.client_renewal_requests,lending.collection_transaction_voids,lending.collection_transactions,
  lending.loan_disbursement_cancellations,lending.loan_disbursement_events,lending.loan_renewal_execution_events,lending.loans,
  accounting.accounts,accounting.fiscal_periods IN SHARE MODE;
 LOCK TABLE accounting.journal_entries,accounting.journal_lines IN SHARE ROW EXCLUSIVE MODE;
 LOCK TABLE accounting.loan_disbursement_journal_draft_preparations,accounting.loan_disbursement_journal_postings,
  accounting.loan_disbursement_journal_reversals,accounting.ecl_quantitative_measurements,treasury.loan_payouts,
  accounting.book_identity,lending.loan_types,lending.loan_contract_schedules,lending.loan_contract_schedule_registrations,
  lending.loan_contract_installments,lending.loan_installment_payment_allocations,
  accounting.ecl_credit_risk_label_reviews,accounting.ecl_forward_looking_evidence,accounting.ecl_forward_looking_evidence_revocations,
  accounting.ecl_allowance_draft_preparations,accounting.ecl_allowance_postings,accounting.ecl_allowance_posting_lines,
  accounting.ecl_allowance_remeasurements,accounting.ecl_accounting_writeoffs IN SHARE MODE;
 LOCK TABLE accounting.loan_elapsed_assessment_preparations,accounting.loan_elapsed_assessment_postings IN SHARE ROW EXCLUSIVE MODE;
END $$;

CREATE OR REPLACE FUNCTION accounting.prepare_elapsed_loan_period_assessment(p_period UUID,p_loan UUID,p_actor UUID,
 p_digest TEXT,p_risk JSONB,p_scenarios JSONB,p_rationale TEXT)
RETURNS UUID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE candidate JSONB; measured JSONB; digest TEXT; existing UUID; created UUID; old_setting TEXT; status TEXT;
BEGIN
 PERFORM accounting.require_loan_period_assessment_actor(p_actor,'accounting.period.close.prepare');
 IF p_digest IS NULL OR p_digest !~ '^[0-9a-f]{64}$' OR length(btrim(coalesce(p_rationale,'')))<20 THEN RAISE EXCEPTION 'Exact source digest and substantive historical rationale are required.'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('period-close:'||p_period::text,0));
 PERFORM pg_advisory_xact_lock(hashtextextended('loan-elapsed-assessment:'||p_loan::text,0));
 SELECT p.status INTO status FROM accounting.fiscal_periods p WHERE p.id=p_period FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Fiscal period was not found.'; END IF;
 PERFORM accounting.lock_elapsed_assessment_sources();
 candidate:=accounting.loan_period_elapsed_assessment_candidate(p_period,p_loan);
 IF coalesce((candidate->>'ready')::boolean,false) IS NOT true THEN RAISE EXCEPTION 'Historical assessment source is blocked; inspect authorized candidate.' USING ERRCODE='23514'; END IF;
 IF candidate->>'source_digest' IS DISTINCT FROM p_digest THEN RAISE EXCEPTION 'Historical source digest changed.' USING ERRCODE='40001'; END IF;
 measured:=accounting.calculate_elapsed_assessment_ecl(candidate->'snapshot',p_risk,p_scenarios);
 digest:=encode(sha256(convert_to(jsonb_build_object('source_digest',p_digest,'measurement',measured,'rationale',btrim(p_rationale))::text,'UTF8')),'hex');
 SELECT id INTO existing FROM accounting.loan_elapsed_assessment_preparations WHERE fiscal_period_id=p_period AND loan_id=p_loan AND confirmation_digest=digest;
 IF FOUND THEN RETURN existing; END IF;
 IF status<>'open' OR EXISTS(SELECT 1 FROM accounting.loan_elapsed_assessment_postings WHERE fiscal_period_id=p_period AND loan_id=p_loan) THEN
  RAISE EXCEPTION 'New historical preparation requires an open unposted assessment; protected correction adapter is required otherwise.' USING ERRCODE='55000'; END IF;
 old_setting:=current_setting('accounting.elapsed_assessment_write',true);
 PERFORM set_config('accounting.elapsed_assessment_write','loan_elapsed_assessment_preparations',true);
 INSERT INTO accounting.loan_elapsed_assessment_preparations(book_id,fiscal_period_id,loan_id,client_id,as_of_date,
  source_digest,confirmation_digest,source_snapshot,risk_review,scenarios,measurement_snapshot,review_rationale,prepared_by)
 VALUES((candidate#>>'{snapshot,book,id}')::uuid,p_period,p_loan,(candidate#>>'{snapshot,loan,client_id}')::uuid,
  (candidate->>'as_of_date')::date,p_digest,digest,candidate->'snapshot',p_risk,p_scenarios,measured,btrim(p_rationale),p_actor) RETURNING id INTO created;
 PERFORM set_config('accounting.elapsed_assessment_write',coalesce(old_setting,''),true);
 RETURN created;
END $$;
DO $$ DECLARE t TEXT; BEGIN
 FOREACH t IN ARRAY ARRAY['loan_elapsed_assessment_preparations','loan_elapsed_assessment_postings'] LOOP
  EXECUTE format('DROP TRIGGER IF EXISTS elapsed_audit_guard ON accounting.%I',t);
  EXECUTE format('CREATE TRIGGER elapsed_audit_guard BEFORE INSERT OR UPDATE OR DELETE ON accounting.%I FOR EACH ROW EXECUTE FUNCTION accounting.guard_elapsed_assessment_audit()',t);
  EXECUTE format('DROP TRIGGER IF EXISTS elapsed_audit_truncate_guard ON accounting.%I',t);
  EXECUTE format('CREATE TRIGGER elapsed_audit_truncate_guard BEFORE TRUNCATE ON accounting.%I FOR EACH STATEMENT EXECUTE FUNCTION accounting.guard_elapsed_assessment_audit()',t);
 END LOOP;
END $$;

CREATE OR REPLACE FUNCTION accounting.elapsed_assessment_chart()
RETURNS JSONB LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT coalesce(jsonb_agg(jsonb_build_object('id',a.id,'code',a.code,'system_key',a.system_key,
  'account_type',a.account_type,'normal_balance',a.normal_balance,'is_posting',a.is_posting) ORDER BY a.code),'[]'::jsonb)
 FROM accounting.accounts a WHERE a.code IN('1100','1110','1120','1190','4000','5000');
$$;

-- Declared before the recursive source candidate. Live recursion only visits
-- strictly earlier cutoffs, never the current or a future prefix.
CREATE OR REPLACE FUNCTION accounting.period_elapsed_loan_assessment_exact(p_period UUID,p_loan UUID)
RETURNS BOOLEAN LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN RETURN false; END $$;

CREATE OR REPLACE FUNCTION accounting.loan_period_elapsed_assessment_candidate(p_period UUID,p_loan UUID)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
DECLARE period_row accounting.fiscal_periods%ROWTYPE; book accounting.book_identity%ROWTYPE;
 loan lending.loans%ROWTYPE; anchor RECORD; prior RECORD;
 blockers TEXT[]:=ARRAY[]::text[]; snapshot JSONB; ledger JSONB; flows JSONB; prior_rows JSONB;
 own_entries UUID[]; allowed_entries UUID[]; rate NUMERIC; gross_raw NUMERIC; interest NUMERIC;
 previous_interest NUMERIC:=0; previous_allowance NUMERIC:=0; previous_cutoff DATE;
 b1100 NUMERIC; b1110 NUMERIC; b1120 NUMERIC; b1190 NUMERIC; due_unpaid NUMERIC; oldest_due DATE; dpd INTEGER;
 contractual_pv NUMERIC; initial NUMERIC; days INTEGER; chart JSONB;
BEGIN
 SELECT * INTO period_row FROM accounting.fiscal_periods WHERE id=p_period;
 IF NOT FOUND THEN RETURN jsonb_build_object('ready',false,'blockers',jsonb_build_array('fiscal_period_required')); END IF;
 SELECT * INTO book FROM accounting.book_identity WHERE singleton;
 IF NOT FOUND THEN blockers:=array_append(blockers,'accounting_book_identity_required'); END IF;
 SELECT * INTO loan FROM lending.loans WHERE id=p_loan;
 IF NOT FOUND THEN RETURN jsonb_build_object('ready',false,'blockers',jsonb_build_array('loan_required')); END IF;
 IF period_row.end_date>(clock_timestamp() AT TIME ZONE 'Asia/Manila')::date THEN blockers:=array_append(blockers,'future_economic_cutoff_not_supported'); END IF;
 IF EXISTS(SELECT 1 FROM (VALUES
  ('1100','loans_receivable_regular','asset','debit'),('1110','loans_receivable_7x7','asset','debit'),
  ('1120','accrued_interest_receivable','asset','debit'),('1190','allowance_expected_credit_loss','asset','credit'),
  ('4000','interest_income_regular','income','credit'),('5000','credit_loss_expense','expense','debit')
 ) e(code,system_key,account_type,normal_balance) WHERE NOT EXISTS(SELECT 1 FROM accounting.accounts a
  WHERE (a.code,a.system_key,a.account_type,a.normal_balance)=(e.code,e.system_key,e.account_type,e.normal_balance) AND a.is_posting)) THEN
  blockers:=array_append(blockers,'loan_control_chart_meaning_mismatch');
 END IF;
 IF 1<>(SELECT count(*) FROM accounting.greenfield_regular_eir_anchor_readiness WHERE loan_id=p_loan) THEN
  RETURN jsonb_build_object('ready',false,'blockers',to_jsonb(array_append(blockers,'single_protected_regular_anchor_required')));
 END IF;
 SELECT * INTO anchor FROM accounting.greenfield_regular_eir_anchor_readiness WHERE loan_id=p_loan;
 IF anchor.readiness_status IS DISTINCT FROM 'greenfield_regular_eir_anchor_ready' OR loan.due_date IS DISTINCT FROM anchor.contractual_due_date THEN
  blockers:=array_append(blockers,'protected_regular_anchor_not_exact');
 END IF;
 IF EXISTS(SELECT 1 FROM accounting.journal_lines l JOIN accounting.accounts a ON a.id=l.account_id
  WHERE l.journal_entry_id=anchor.journal_entry_id AND l.credit>0 AND
  (a.account_type<>'asset' OR a.normal_balance<>'debit' OR NOT((a.code='1010' AND a.system_key='cash_office') OR (a.code='1030' AND a.system_key='cash_bank_gcash')))) THEN
  blockers:=array_append(blockers,'release_cash_chart_meaning_mismatch');
 END IF;
 IF anchor.anchor_date>=period_row.end_date OR period_row.end_date>anchor.contractual_due_date THEN
  blockers:=array_append(blockers,'elapsed_original_contract_boundary_required');
 END IF;
 IF anchor.contractual_due_date>period_row.end_date+365 THEN blockers:=array_append(blockers,'twelve_month_default_horizon_adapter_required'); END IF;
 IF loan.status<>'active' OR EXISTS(SELECT 1 FROM lending.loan_contract_schedules s WHERE s.loan_id=p_loan AND s.id<>anchor.schedule_id)
  OR EXISTS(SELECT 1 FROM lending.loan_renewal_execution_events e WHERE (e.old_loan_id=p_loan OR e.new_loan_id=p_loan) AND e.business_date<=period_row.end_date)
  OR EXISTS(SELECT 1 FROM lending.client_renewal_requests r WHERE r.loan_id=p_loan)
  OR EXISTS(SELECT 1 FROM accounting.ecl_accounting_writeoffs w WHERE w.loan_id=p_loan)
  OR EXISTS(SELECT 1 FROM accounting.ecl_allowance_remeasurements w WHERE w.loan_id=p_loan)
  OR EXISTS(SELECT 1 FROM accounting.ecl_allowance_postings w WHERE w.loan_id=p_loan AND w.posting_date<=period_row.end_date) THEN
  blockers:=array_append(blockers,'source_state_requires_extended_assessment_adapter');
 END IF;
 IF EXISTS(SELECT 1 FROM lending.collection_transactions t WHERE t.loan_id=p_loan AND t.collection_date<=period_row.end_date
  AND (t.amount>0 OR t.entry_type IN('payment','advance'))) THEN blockers:=array_append(blockers,'collection_prefix_adapter_required'); END IF;
 rate:=anchor.daily_eir; initial:=anchor.initial_gross_carrying_amount; days:=period_row.end_date-anchor.anchor_date;
 IF rate IS NULL OR rate<=0 OR initial IS NULL OR initial<=0 OR days<=0 OR days>3660 THEN
  RETURN jsonb_build_object('ready',false,'blockers',to_jsonb(array_append(blockers,'original_eir_measurement_required')));
 END IF;
 gross_raw:=initial*power(1::numeric+rate,days::numeric); interest:=round(gross_raw-initial,2);
 SELECT coalesce(jsonb_agg(jsonb_build_object('id',i.id,'installment_number',i.installment_number,'due_date',i.due_date,
   'contractual_amount',i.contractual_amount,'allocated_amount',0,'remaining_amount',i.contractual_amount) ORDER BY i.installment_number),'[]'::jsonb),
  coalesce(sum(i.contractual_amount/power(1::numeric+rate,(i.due_date-period_row.end_date)::numeric)),0),
  coalesce(sum(i.contractual_amount) FILTER(WHERE i.due_date<=period_row.end_date),0),
  min(i.due_date) FILTER(WHERE i.due_date<=period_row.end_date)
 INTO flows,contractual_pv,due_unpaid,oldest_due FROM lending.loan_contract_installments i WHERE i.schedule_id=anchor.schedule_id;
 dpd:=greatest(coalesce(period_row.end_date-oldest_due,0),0);
 IF dpd>=30 THEN blockers:=array_append(blockers,'historical_risk_stage_extension_required'); END IF;
 IF round(contractual_pv,2)<>round(gross_raw,2) THEN blockers:=array_append(blockers,'contractual_pv_carrying_reconciliation_required'); END IF;
 SELECT coalesce(array_agg(x) FILTER(WHERE x IS NOT NULL),ARRAY[]::uuid[]) INTO own_entries
 FROM accounting.loan_elapsed_assessment_postings a CROSS JOIN LATERAL unnest(ARRAY[a.eir_journal_entry_id,a.allowance_journal_entry_id]) x
 WHERE a.fiscal_period_id=p_period AND a.loan_id=p_loan;
 allowed_entries:=ARRAY[anchor.journal_entry_id]||own_entries;
 FOR prior IN SELECT p.*,a.id AS audit_id,a.eir_journal_entry_id,a.allowance_journal_entry_id
  FROM accounting.loan_elapsed_assessment_preparations p JOIN accounting.loan_elapsed_assessment_postings a ON a.preparation_id=p.id
  WHERE p.loan_id=p_loan AND p.book_id=book.id AND p.as_of_date<period_row.end_date ORDER BY p.as_of_date,p.id LOOP
  IF prior.as_of_date>=period_row.start_date OR NOT accounting.period_elapsed_loan_assessment_exact(prior.fiscal_period_id,p_loan) THEN
   blockers:=array_append(blockers,'prior_recognized_prefix_not_exact');
  END IF;
  previous_interest:=(prior.source_snapshot#>>'{eir,cumulative_interest}')::numeric;
  previous_allowance:=(prior.measurement_snapshot->>'ecl_amount')::numeric;
  previous_cutoff:=prior.as_of_date;
  allowed_entries:=allowed_entries||ARRAY[prior.eir_journal_entry_id,prior.allowance_journal_entry_id];
 END LOOP;
 IF (previous_cutoff IS NULL AND period_row.start_date>anchor.anchor_date+1)
  OR (previous_cutoff IS NOT NULL AND previous_cutoff<>period_row.start_date-1) THEN blockers:=array_append(blockers,'earlier_elapsed_period_prefix_required'); END IF;
 IF previous_interest>interest THEN blockers:=array_append(blockers,'recognized_interest_exceeds_current_prefix'); END IF;
 SELECT coalesce(sum(l.debit-l.credit) FILTER(WHERE a.code='1100'),0),coalesce(sum(l.debit-l.credit) FILTER(WHERE a.code='1110'),0),
  coalesce(sum(l.debit-l.credit) FILTER(WHERE a.code='1120'),0),coalesce(sum(l.credit-l.debit) FILTER(WHERE a.code='1190'),0)
 INTO b1100,b1110,b1120,b1190 FROM accounting.journal_entries j JOIN accounting.journal_lines l ON l.journal_entry_id=j.id
 JOIN accounting.accounts a ON a.id=l.account_id WHERE j.status='posted' AND j.posting_date<=period_row.end_date AND l.loan_id=p_loan AND NOT j.id=ANY(own_entries);
 IF b1100<>initial OR b1110<>0 OR b1120<>previous_interest OR b1190<>previous_allowance THEN blockers:=array_append(blockers,'dated_loan_control_components_not_reconciled'); END IF;
 IF EXISTS(SELECT 1 FROM accounting.journal_entries j JOIN accounting.journal_lines l ON l.journal_entry_id=j.id JOIN accounting.accounts a ON a.id=l.account_id
  WHERE j.status='posted' AND j.posting_date<=period_row.end_date AND l.loan_id=p_loan AND a.code IN('1100','1110','1120','1190')
  AND NOT j.id=ANY(array_remove(allowed_entries,NULL))) THEN blockers:=array_append(blockers,'unrecognized_loan_control_journal'); END IF;
 SELECT coalesce(jsonb_agg(to_jsonb(j)||jsonb_build_object('lines',(SELECT jsonb_agg(to_jsonb(l)||jsonb_build_object('account',
  jsonb_build_object('id',a.id,'code',a.code,'system_key',a.system_key,'account_type',a.account_type,'normal_balance',a.normal_balance,'is_posting',a.is_posting)) ORDER BY l.line_number)
  FROM accounting.journal_lines l JOIN accounting.accounts a ON a.id=l.account_id WHERE l.journal_entry_id=j.id)) ORDER BY j.posting_date,j.id),'[]'::jsonb)
 INTO ledger FROM accounting.journal_entries j WHERE j.status='posted' AND j.posting_date<=period_row.end_date AND NOT j.id=ANY(own_entries)
 AND EXISTS(SELECT 1 FROM accounting.journal_lines l WHERE l.journal_entry_id=j.id AND l.loan_id=p_loan);
 SELECT coalesce(jsonb_agg(jsonb_build_object('preparation',to_jsonb(p),'posting',to_jsonb(a)) ORDER BY p.as_of_date,p.id),'[]'::jsonb)
 INTO prior_rows FROM accounting.loan_elapsed_assessment_preparations p JOIN accounting.loan_elapsed_assessment_postings a ON a.preparation_id=p.id
 WHERE p.loan_id=p_loan AND p.book_id=book.id AND p.as_of_date<period_row.end_date;
 chart:=accounting.elapsed_assessment_chart();
 snapshot:=jsonb_build_object('policy_version','regular_original_segment_prefix_v1','book',to_jsonb(book),'period_id',p_period,
  'period_start',period_row.start_date,'cutoff_date',period_row.end_date,
  'loan',jsonb_build_object('id',loan.id,'client_id',loan.client_id,'loan_type_id',loan.loan_type_id,'principal',loan.principal,
    'daily_amount',loan.daily_amount,'interest_rate',loan.interest_rate,'date_released',loan.date_released,'due_date',loan.due_date),
  'anchor',to_jsonb(anchor),'chart',chart,'ledger',ledger,'prior_prefixes',prior_rows,
  'schedule',(SELECT to_jsonb(s) FROM lending.loan_contract_schedules s WHERE s.id=anchor.schedule_id),
  'registration',(SELECT to_jsonb(r) FROM lending.loan_contract_schedule_registrations r WHERE r.schedule_id=anchor.schedule_id),
  'disbursement',(SELECT to_jsonb(e) FROM lending.loan_disbursement_events e WHERE e.id=anchor.disbursement_event_id),
  'contractual_cash_flows',flows,'contractual_pv_raw',contractual_pv,'gross_carrying_raw',gross_raw,'gross_carrying_amount',round(gross_raw,2),
  'dpd',dpd,'due_unpaid_amount',due_unpaid,'prior_allowance',previous_allowance,
  'eir',jsonb_build_object('segment_source_key',anchor.anchor_source_key,'anchor_date',anchor.anchor_date,'daily_eir',rate,
   'raw_cumulative_interest',gross_raw-initial,'cumulative_interest',interest,'prior_recognized_interest',previous_interest,
   'incremental_interest',interest-previous_interest,'prior_cutoff',previous_cutoff));
 RETURN jsonb_build_object('ready',cardinality(blockers)=0,'blockers',to_jsonb(blockers),'as_of_date',period_row.end_date,
  'eir',snapshot->'eir','snapshot',snapshot,'source_digest',encode(sha256(convert_to(snapshot::text,'UTF8')),'hex'));
END $$;

CREATE OR REPLACE FUNCTION accounting.elapsed_assessment_lines(p_preparation UUID,p_kind TEXT)
RETURNS TABLE(line_number INTEGER,account_id UUID,debit NUMERIC,credit NUMERIC,client_id UUID,loan_id UUID)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 WITH basis AS(SELECT p.*,
  CASE p_kind WHEN 'eir' THEN (p.source_snapshot#>>'{eir,incremental_interest}')::numeric
   WHEN 'ecl' THEN (p.measurement_snapshot->>'allowance_delta')::numeric END AS amount
  FROM accounting.loan_elapsed_assessment_preparations p WHERE p.id=p_preparation),
 sides AS(SELECT b.*,CASE WHEN p_kind='eir' THEN '1120' WHEN amount>0 THEN '5000' ELSE '1190' END AS dr,
  CASE WHEN p_kind='eir' THEN '4000' WHEN amount>0 THEN '1190' ELSE '5000' END AS cr FROM basis b)
 SELECT 1,(a.value->>'id')::uuid,abs(s.amount),0::numeric,s.client_id,s.loan_id FROM sides s
 CROSS JOIN LATERAL jsonb_array_elements(s.source_snapshot->'chart') a WHERE a.value->>'code'=s.dr AND s.amount<>0
 UNION ALL SELECT 2,(a.value->>'id')::uuid,0::numeric,abs(s.amount),s.client_id,s.loan_id FROM sides s
 CROSS JOIN LATERAL jsonb_array_elements(s.source_snapshot->'chart') a WHERE a.value->>'code'=s.cr AND s.amount<>0;
$$;

CREATE OR REPLACE FUNCTION accounting.elapsed_assessment_journal_exact(p_preparation UUID,p_journal UUID,p_kind TEXT)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT EXISTS(SELECT 1 FROM accounting.loan_elapsed_assessment_preparations p JOIN accounting.journal_entries j ON j.id=p_journal
  WHERE p.id=p_preparation AND j.status='posted' AND j.fiscal_period_id=p.fiscal_period_id AND j.posting_date=p.as_of_date
   AND j.source_type='period_elapsed_'||p_kind AND j.source_reference=p.id::text
   AND j.source_event_key='period_'||p_kind||':'||p.fiscal_period_id::text||':'||p.loan_id::text
   AND j.created_by_user_id=p.prepared_by AND j.reversal_of_entry_id IS NULL AND j.entry_number IS NOT NULL
   AND 2=(SELECT count(*) FROM accounting.journal_lines WHERE journal_entry_id=j.id)
   AND 2=(SELECT count(*) FROM accounting.elapsed_assessment_lines(p.id,p_kind))
   AND NOT EXISTS(SELECT 1 FROM accounting.elapsed_assessment_lines(p.id,p_kind) expected
    LEFT JOIN accounting.journal_lines actual ON actual.journal_entry_id=j.id AND actual.line_number=expected.line_number
    WHERE actual.id IS NULL OR (actual.account_id,actual.debit,actual.credit,actual.client_id,actual.loan_id)
     IS DISTINCT FROM(expected.account_id,expected.debit,expected.credit,expected.client_id,expected.loan_id)));
$$;

CREATE OR REPLACE FUNCTION accounting.period_elapsed_loan_assessment_exact(p_period UUID,p_loan UUID)
RETURNS BOOLEAN LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE p accounting.loan_elapsed_assessment_preparations%ROWTYPE; a accounting.loan_elapsed_assessment_postings%ROWTYPE;
 candidate JSONB; measured JSONB; eir NUMERIC; delta NUMERIC;
BEGIN
 SELECT posting.* INTO a FROM accounting.loan_elapsed_assessment_postings posting WHERE fiscal_period_id=p_period AND loan_id=p_loan;
 IF NOT FOUND THEN RETURN false; END IF;
 SELECT * INTO p FROM accounting.loan_elapsed_assessment_preparations WHERE id=a.preparation_id;
 IF (a.book_id,a.fiscal_period_id,a.loan_id,a.as_of_date,a.confirmation_digest)
  IS DISTINCT FROM(p.book_id,p.fiscal_period_id,p.loan_id,p.as_of_date,p.confirmation_digest)
  OR NOT EXISTS(SELECT 1 FROM accounting.book_identity b WHERE b.id=p.book_id) THEN RETURN false; END IF;
 candidate:=accounting.loan_period_elapsed_assessment_candidate(p_period,p_loan);
 IF coalesce((candidate->>'ready')::boolean,false) IS NOT true OR candidate->>'source_digest' IS DISTINCT FROM p.source_digest
  OR candidate->'snapshot' IS DISTINCT FROM p.source_snapshot THEN RETURN false; END IF;
 measured:=accounting.calculate_elapsed_assessment_ecl(p.source_snapshot,p.risk_review,p.scenarios);
 IF measured IS DISTINCT FROM p.measurement_snapshot OR p.confirmation_digest IS DISTINCT FROM encode(sha256(convert_to(
  jsonb_build_object('source_digest',p.source_digest,'measurement',measured,'rationale',p.review_rationale)::text,'UTF8')),'hex') THEN RETURN false; END IF;
 eir:=(p.source_snapshot#>>'{eir,incremental_interest}')::numeric; delta:=(measured->>'allowance_delta')::numeric;
 RETURN (CASE WHEN eir=0 THEN a.eir_journal_entry_id IS NULL ELSE accounting.elapsed_assessment_journal_exact(p.id,a.eir_journal_entry_id,'eir') END)
  AND (CASE WHEN delta=0 THEN a.allowance_journal_entry_id IS NULL ELSE accounting.elapsed_assessment_journal_exact(p.id,a.allowance_journal_entry_id,'ecl') END)
  AND NOT EXISTS(SELECT 1 FROM accounting.journal_entries j WHERE j.id IN(a.eir_journal_entry_id,a.allowance_journal_entry_id) AND j.posted_by_user_id IS DISTINCT FROM a.posted_by);
EXCEPTION WHEN check_violation OR invalid_parameter_value OR invalid_text_representation OR datetime_field_overflow THEN RETURN false;
END $$;

CREATE OR REPLACE FUNCTION accounting.guard_elapsed_assessment_journal()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE p accounting.loan_elapsed_assessment_preparations%ROWTYPE; kind TEXT;
BEGIN
 IF TG_OP<>'DELETE' AND NEW.reversal_of_entry_id IS NOT NULL AND EXISTS(SELECT 1 FROM accounting.journal_entries j
  WHERE j.id=NEW.reversal_of_entry_id AND j.source_type IN('period_elapsed_eir','period_elapsed_ecl')) THEN
  RAISE EXCEPTION 'Historical assessment reversal requires its protected correction adapter.' USING ERRCODE='55000'; END IF;
 IF (TG_OP<>'INSERT' AND (OLD.source_type IN('period_elapsed_eir','period_elapsed_ecl') OR OLD.source_event_key LIKE 'period_eir:%' OR OLD.source_event_key LIKE 'period_ecl:%'))
  OR (TG_OP<>'DELETE' AND (NEW.source_type IN('period_elapsed_eir','period_elapsed_ecl') OR NEW.source_event_key LIKE 'period_eir:%' OR NEW.source_event_key LIKE 'period_ecl:%')) THEN
  IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Protected historical assessment journals are immutable.' USING ERRCODE='55000'; END IF;
  SELECT * INTO p FROM accounting.loan_elapsed_assessment_preparations WHERE id::text=current_setting('accounting.elapsed_assessment_post',true);
  kind:=CASE NEW.source_type WHEN 'period_elapsed_eir' THEN 'eir' WHEN 'period_elapsed_ecl' THEN 'ecl' END;
  IF p.id IS NULL OR kind IS NULL OR NEW.source_reference IS DISTINCT FROM p.id::text
   OR NEW.source_event_key IS DISTINCT FROM 'period_'||kind||':'||p.fiscal_period_id::text||':'||p.loan_id::text
   OR NEW.fiscal_period_id IS DISTINCT FROM p.fiscal_period_id OR NEW.posting_date IS DISTINCT FROM p.as_of_date
   OR NEW.created_by_user_id IS DISTINCT FROM p.prepared_by OR NEW.reversal_of_entry_id IS NOT NULL
   OR EXISTS(SELECT 1 FROM accounting.loan_elapsed_assessment_postings a WHERE a.preparation_id=p.id) THEN
   RAISE EXCEPTION 'Protected historical journal requires the exact retained assessment.' USING ERRCODE='55000'; END IF;
 ELSE
  -- Existing collection/renewal/manual paths cannot recognize a cash span
  -- again after a fiscal prefix. This never rejects recording actual money.
  IF TG_OP='UPDATE' AND NEW.status='posted' AND OLD.status<>'posted' AND EXISTS(
   SELECT 1 FROM accounting.journal_lines l JOIN accounting.accounts account ON account.id=l.account_id
   JOIN accounting.loan_elapsed_assessment_postings a ON a.loan_id=l.loan_id
   WHERE l.journal_entry_id=NEW.id AND account.code IN('1100','1110','1120','1190')) THEN
   RAISE EXCEPTION 'This loan requires the protected prefix-aware collection or correction accounting adapter.' USING ERRCODE='55000'; END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS elapsed_assessment_journal_guard ON accounting.journal_entries;
CREATE TRIGGER elapsed_assessment_journal_guard BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_elapsed_assessment_journal();

CREATE OR REPLACE FUNCTION accounting.guard_elapsed_assessment_line()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE journal accounting.journal_entries%ROWTYPE; p accounting.loan_elapsed_assessment_preparations%ROWTYPE; target UUID; kind TEXT;
BEGIN
 IF TG_OP='TRUNCATE' THEN
  IF EXISTS(SELECT 1 FROM accounting.loan_elapsed_assessment_postings) THEN RAISE EXCEPTION 'Protected historical assessment journals cannot be truncated.' USING ERRCODE='55000'; END IF;
  RETURN NULL;
 END IF;
 IF TG_OP='DELETE' THEN target:=OLD.journal_entry_id; ELSE target:=NEW.journal_entry_id; END IF;
 IF TG_OP='UPDATE' AND EXISTS(SELECT 1 FROM accounting.journal_entries j WHERE j.id=OLD.journal_entry_id AND j.source_type IN('period_elapsed_eir','period_elapsed_ecl')) THEN
  RAISE EXCEPTION 'Protected historical journal lines are immutable.' USING ERRCODE='55000'; END IF;
 SELECT * INTO journal FROM accounting.journal_entries WHERE id=target;
 IF journal.source_type IN('period_elapsed_eir','period_elapsed_ecl') THEN
  IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Protected historical journal lines are immutable.' USING ERRCODE='55000'; END IF;
  SELECT * INTO p FROM accounting.loan_elapsed_assessment_preparations WHERE id::text=current_setting('accounting.elapsed_assessment_post',true);
  kind:=CASE journal.source_type WHEN 'period_elapsed_eir' THEN 'eir' ELSE 'ecl' END;
  IF p.id IS NULL OR journal.source_reference IS DISTINCT FROM p.id::text OR journal.status<>'draft'
   OR NOT EXISTS(SELECT 1 FROM accounting.elapsed_assessment_lines(p.id,kind) expected
    WHERE (NEW.line_number,NEW.account_id,NEW.debit,NEW.credit,NEW.client_id,NEW.loan_id)
     IS NOT DISTINCT FROM(expected.line_number,expected.account_id,expected.debit,expected.credit,expected.client_id,expected.loan_id)) THEN
   RAISE EXCEPTION 'Historical journal line must match exact prepared measurement coordinates.' USING ERRCODE='55000'; END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS elapsed_assessment_line_guard ON accounting.journal_lines;
CREATE TRIGGER elapsed_assessment_line_guard BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_lines
FOR EACH ROW EXECUTE FUNCTION accounting.guard_elapsed_assessment_line();
DROP TRIGGER IF EXISTS elapsed_assessment_line_truncate_guard ON accounting.journal_lines;
CREATE TRIGGER elapsed_assessment_line_truncate_guard BEFORE TRUNCATE ON accounting.journal_lines
FOR EACH STATEMENT EXECUTE FUNCTION accounting.guard_elapsed_assessment_line();

CREATE OR REPLACE FUNCTION accounting.post_elapsed_loan_period_assessment(p_preparation UUID,p_actor UUID,p_digest TEXT)
RETURNS UUID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE p accounting.loan_elapsed_assessment_preparations%ROWTYPE; candidate JSONB; measured JSONB; status TEXT;
 existing UUID; created UUID; journal UUID; eir_journal UUID; allowance_journal UUID; kind TEXT; old_post TEXT; old_write TEXT; old_allowance TEXT;
BEGIN
 PERFORM accounting.require_loan_period_assessment_actor(p_actor,'accounting.period.close.post');
 SELECT * INTO p FROM accounting.loan_elapsed_assessment_preparations WHERE id=p_preparation;
 IF NOT FOUND THEN RAISE EXCEPTION 'Historical assessment preparation was not found.'; END IF;
 IF p_digest IS DISTINCT FROM p.confirmation_digest THEN RAISE EXCEPTION 'Exact confirmation digest is required.' USING ERRCODE='55000'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('period-close:'||p.fiscal_period_id::text,0));
 PERFORM pg_advisory_xact_lock(hashtextextended('loan-elapsed-assessment:'||p.loan_id::text,0));
 SELECT period.status INTO status FROM accounting.fiscal_periods period WHERE id=p.fiscal_period_id FOR UPDATE;
 PERFORM accounting.lock_elapsed_assessment_sources();
 SELECT id INTO existing FROM accounting.loan_elapsed_assessment_postings WHERE preparation_id=p.id;
 IF FOUND THEN RETURN existing; END IF;
 IF status<>'open' THEN RAISE EXCEPTION 'Historical assessment posting requires an open period.' USING ERRCODE='55000'; END IF;
 candidate:=accounting.loan_period_elapsed_assessment_candidate(p.fiscal_period_id,p.loan_id);
 IF coalesce((candidate->>'ready')::boolean,false) IS NOT true OR candidate->>'source_digest' IS DISTINCT FROM p.source_digest OR candidate->'snapshot' IS DISTINCT FROM p.source_snapshot THEN
  RAISE EXCEPTION 'Historical source changed or is blocked after preparation.' USING ERRCODE='40001'; END IF;
 measured:=accounting.calculate_elapsed_assessment_ecl(p.source_snapshot,p.risk_review,p.scenarios);
 IF measured IS DISTINCT FROM p.measurement_snapshot THEN RAISE EXCEPTION 'Historical measurement evidence changed after preparation.' USING ERRCODE='40001'; END IF;
 old_post:=current_setting('accounting.elapsed_assessment_post',true); old_write:=current_setting('accounting.elapsed_assessment_write',true);
 old_allowance:=current_setting('accounting.ecl_allowance_journal_line_write_allowed',true);
 PERFORM set_config('accounting.elapsed_assessment_post',p.id::text,true);
 FOREACH kind IN ARRAY ARRAY['eir','ecl'] LOOP
  IF NOT EXISTS(SELECT 1 FROM accounting.elapsed_assessment_lines(p.id,kind)) THEN CONTINUE; END IF;
  INSERT INTO accounting.journal_entries(fiscal_period_id,posting_date,description,source_type,source_reference,source_event_key,created_by_user_id)
  VALUES(p.fiscal_period_id,p.as_of_date,'Retained historical cutoff '||kind,'period_elapsed_'||kind,p.id::text,
   'period_'||kind||':'||p.fiscal_period_id::text||':'||p.loan_id::text,p.prepared_by) RETURNING id INTO journal;
  -- Reuse1190's existing protected-workflow capability only for these exact
  -- preparation-bound lines;153's line guard independently checks every field.
  IF kind='ecl' THEN PERFORM set_config('accounting.ecl_allowance_journal_line_write_allowed','on',true); END IF;
  INSERT INTO accounting.journal_lines(journal_entry_id,line_number,account_id,description,debit,credit,client_id,loan_id)
  SELECT journal,x.line_number,x.account_id,'Protected historical '||kind,x.debit,x.credit,x.client_id,x.loan_id
  FROM accounting.elapsed_assessment_lines(p.id,kind) x;
  IF kind='ecl' THEN PERFORM set_config('accounting.ecl_allowance_journal_line_write_allowed',coalesce(old_allowance,''),true); END IF;
  PERFORM accounting.post_journal_entry(journal,p_actor);
  IF kind='eir' THEN eir_journal:=journal; ELSE allowance_journal:=journal; END IF;
 END LOOP;
 PERFORM set_config('accounting.elapsed_assessment_write','loan_elapsed_assessment_postings',true);
 INSERT INTO accounting.loan_elapsed_assessment_postings(preparation_id,book_id,fiscal_period_id,loan_id,as_of_date,
  eir_journal_entry_id,allowance_journal_entry_id,confirmation_digest,posted_by)
 VALUES(p.id,p.book_id,p.fiscal_period_id,p.loan_id,p.as_of_date,eir_journal,allowance_journal,p.confirmation_digest,p_actor) RETURNING id INTO created;
 IF NOT accounting.period_elapsed_loan_assessment_exact(p.fiscal_period_id,p.loan_id) THEN RAISE EXCEPTION 'Posted historical assessment is not exact.' USING ERRCODE='23514'; END IF;
 PERFORM set_config('accounting.elapsed_assessment_post',coalesce(old_post,''),true);
 PERFORM set_config('accounting.elapsed_assessment_write',coalesce(old_write,''),true);
 RETURN created;
END $$;

CREATE OR REPLACE FUNCTION accounting.assert_elapsed_assessment_committed()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE period UUID; loan UUID;
BEGIN
 IF TG_TABLE_NAME='journal_entries' THEN
  IF NEW.source_type NOT IN('period_elapsed_eir','period_elapsed_ecl') THEN RETURN NEW; END IF;
  SELECT a.fiscal_period_id,a.loan_id INTO period,loan FROM accounting.loan_elapsed_assessment_postings a
   WHERE NEW.id IN(a.eir_journal_entry_id,a.allowance_journal_entry_id);
 ELSE period:=NEW.fiscal_period_id; loan:=NEW.loan_id; END IF;
 IF period IS NULL OR NOT accounting.period_elapsed_loan_assessment_exact(period,loan) THEN
  RAISE EXCEPTION 'Historical assessment source changed or lacks exact protected posting at commit.' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS elapsed_assessment_journal_commit ON accounting.journal_entries;
CREATE CONSTRAINT TRIGGER elapsed_assessment_journal_commit AFTER INSERT OR UPDATE ON accounting.journal_entries
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION accounting.assert_elapsed_assessment_committed();
DROP TRIGGER IF EXISTS elapsed_assessment_posting_commit ON accounting.loan_elapsed_assessment_postings;
CREATE CONSTRAINT TRIGGER elapsed_assessment_posting_commit AFTER INSERT ON accounting.loan_elapsed_assessment_postings
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION accounting.assert_elapsed_assessment_committed();

DO $$ BEGIN
 IF to_regprocedure('accounting.period_loan_assessment_without_elapsed_exact(uuid,uuid)') IS NULL THEN
  ALTER FUNCTION accounting.period_loan_assessment_exact(UUID,UUID) RENAME TO period_loan_assessment_without_elapsed_exact;
 END IF;
END $$;
CREATE OR REPLACE FUNCTION accounting.period_loan_assessment_exact(p_period UUID,p_loan UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT accounting.period_elapsed_loan_assessment_exact(p_period,p_loan)
  OR accounting.period_loan_assessment_without_elapsed_exact(p_period,p_loan);
$$;

DO $$ BEGIN
 IF to_regprocedure('accounting.period_review_before_elapsed_evidence(uuid)') IS NULL
  AND to_regprocedure('accounting.period_review_additional_evidence(uuid)') IS NOT NULL THEN
  ALTER FUNCTION accounting.period_review_additional_evidence(UUID) RENAME TO period_review_before_elapsed_evidence;
 END IF;
 IF to_regprocedure('accounting.lock_period_review_before_elapsed_sources()') IS NULL
  AND to_regprocedure('accounting.lock_period_review_additional_sources()') IS NOT NULL THEN
  ALTER FUNCTION accounting.lock_period_review_additional_sources() RENAME TO lock_period_review_before_elapsed_sources;
 END IF;
END $$;
CREATE OR REPLACE FUNCTION accounting.period_review_additional_evidence(p_period UUID)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE prior JSONB:='{}'::jsonb; retained JSONB;
BEGIN
 IF to_regprocedure('accounting.period_review_before_elapsed_evidence(uuid)') IS NOT NULL THEN prior:=accounting.period_review_before_elapsed_evidence(p_period); END IF;
 SELECT coalesce(jsonb_agg(jsonb_build_object('preparation',to_jsonb(p),'posting',to_jsonb(a)) ORDER BY p.as_of_date,p.id),'[]'::jsonb)
 INTO retained FROM accounting.loan_elapsed_assessment_preparations p LEFT JOIN accounting.loan_elapsed_assessment_postings a ON a.preparation_id=p.id
 WHERE p.as_of_date<=(SELECT end_date FROM accounting.fiscal_periods WHERE id=p_period);
 RETURN prior||jsonb_build_object('historical_loan_assessments',retained);
END $$;
CREATE OR REPLACE FUNCTION accounting.lock_period_review_additional_sources()
RETURNS VOID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF to_regprocedure('accounting.lock_period_review_before_elapsed_sources()') IS NOT NULL THEN PERFORM accounting.lock_period_review_before_elapsed_sources(); END IF;
 LOCK TABLE accounting.loan_elapsed_assessment_preparations,accounting.loan_elapsed_assessment_postings IN SHARE MODE;
END $$;

DO $$ DECLARE f RECORD; r TEXT; t TEXT; BEGIN
 FOR f IN SELECT p.oid::regprocedure signature FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
  WHERE n.nspname='accounting' AND (p.proname LIKE '%elapsed%assessment%' OR p.proname IN(
   'period_loan_assessment_exact','period_loan_assessment_without_elapsed_exact','elapsed_assessment_chart',
   'period_review_before_elapsed_evidence','lock_period_review_before_elapsed_sources',
   'period_review_additional_evidence','lock_period_review_additional_sources')) LOOP
  EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC',f.signature);
  FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
   IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN EXECUTE format('REVOKE ALL ON FUNCTION %s FROM %I',f.signature,r); END IF;
  END LOOP;
 END LOOP;
 FOREACH t IN ARRAY ARRAY['loan_elapsed_assessment_preparations','loan_elapsed_assessment_postings'] LOOP
  EXECUTE format('REVOKE ALL ON accounting.%I FROM PUBLIC',t);
  FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
   IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN EXECUTE format('REVOKE ALL ON accounting.%I FROM %I',t,r); END IF;
  END LOOP;
 END LOOP;
END $$;
COMMIT;
