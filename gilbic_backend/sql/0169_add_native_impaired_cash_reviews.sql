BEGIN;

-- These are dated measurement evidence. Gross cash journals remain the source
-- of money; the fiscal assessment recognizes the net-interest adjustment once.
CREATE TABLE IF NOT EXISTS accounting.native_impaired_cash_reviews (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 book_id UUID NOT NULL REFERENCES accounting.book_identity(id),
 fiscal_period_id UUID NOT NULL REFERENCES accounting.fiscal_periods(id),
 loan_id UUID NOT NULL REFERENCES lending.loans(id),
 application_id UUID NOT NULL REFERENCES treasury.applications(id),
 transaction_id UUID NOT NULL REFERENCES lending.collection_transactions(id),
 as_of_date DATE NOT NULL,
 source_digest TEXT NOT NULL CHECK(source_digest ~ '^[0-9a-f]{64}$'),
 confirmation_digest TEXT NOT NULL CHECK(confirmation_digest ~ '^[0-9a-f]{64}$'),
 source_snapshot JSONB NOT NULL CHECK(jsonb_typeof(source_snapshot)='object'),
 scenarios JSONB NOT NULL CHECK(jsonb_typeof(scenarios)='array'),
 measurement_snapshot JSONB NOT NULL CHECK(jsonb_typeof(measurement_snapshot)='object'),
 review_rationale TEXT NOT NULL CHECK(length(btrim(review_rationale)) BETWEEN 20 AND 2000),
 prepared_by UUID NOT NULL REFERENCES core.users(id),
 calculated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(application_id,confirmation_digest)
);
ALTER TABLE accounting.native_impaired_cash_reviews ENABLE ROW LEVEL SECURITY;
CREATE INDEX IF NOT EXISTS native_impaired_cash_review_lookup
 ON accounting.native_impaired_cash_reviews(fiscal_period_id,loan_id,application_id,calculated_at DESC,id);

CREATE OR REPLACE FUNCTION accounting.native_credit_impaired_chain(p_opening DATE,p_gross NUMERIC,p_allowance NUMERIC,
 p_rate NUMERIC,p_cutoff DATE,p_maturity DATE,p_events JSONB)
RETURNS JSONB LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE item JSONB; day DATE; last_day DATE:=p_opening; gross NUMERIC:=p_gross; allowance NUMERIC:=p_allowance;
 cash NUMERIC; target NUMERIC; gi NUMERIC; ni NUMERIC; unwind NUMERIC; factor NUMERIC; after_gross NUMERIC; full_payoff BOOLEAN;
 interval_gi NUMERIC; total_interval_gi NUMERIC:=0;
 stopped BOOLEAN:=false; deferred BOOLEAN:=false; total_gi NUMERIC:=0; total_unwind NUMERIC:=0;
 total_delta NUMERIC:=0; settlement NUMERIC:=0; count_events INTEGER:=0;
BEGIN
 -- Reuse the bounded primitive's finite/currency/rate checks without accruing.
 PERFORM accounting.native_credit_impaired_interval(p_gross,p_allowance,p_rate,0,0,p_allowance,false);
 IF p_opening IS NULL OR p_cutoff IS NULL OR p_maturity IS NULL OR p_cutoff<p_opening
  OR p_cutoff-p_opening>36600 OR jsonb_typeof(p_events) IS DISTINCT FROM 'array'
  OR jsonb_array_length(p_events)>5000 THEN
  RAISE EXCEPTION 'Exact bounded impaired cash dates and ordered events are required.' USING ERRCODE='23514'; END IF;
 FOR item IN SELECT value FROM jsonb_array_elements(p_events) LOOP
  day:=(item->>'cash_date')::date; cash:=(item->>'cash')::numeric;
  full_payoff:=(item->>'full_payoff')::boolean; count_events:=count_events+1;
   IF day IS NULL OR day<last_day OR day<p_opening
    OR (day=p_opening AND item->>'opening_day_cash' IS DISTINCT FROM 'true') OR day>p_cutoff OR stopped OR deferred
   OR cash IS NULL OR cash<=0 OR cash<>round(cash,2) OR cash::text IN('NaN','Infinity','-Infinity')
   OR full_payoff IS NULL THEN RAISE EXCEPTION 'Exact chronological impaired cash is required.' USING ERRCODE='23514'; END IF;
  factor:=power(1+p_rate,greatest(least(day,p_maturity)-least(last_day,p_maturity),0))-1;
  interval_gi:=round(gross*factor,2); ni:=round((gross-allowance)*factor,2); gi:=interval_gi;
  -- Protected callers may supply the independently proved gross recurrence.
  -- This primitive grants no posting or source authority to its arguments.
  IF item ? 'verified_gross_interest' THEN gi:=(item->>'verified_gross_interest')::numeric; END IF;
  unwind:=gi-ni;
  IF gi IS NULL OR gi<0 OR gi<>round(gi,2) OR gi::text IN('NaN','Infinity','-Infinity') OR ni<0 THEN
   RAISE EXCEPTION 'Verified gross and net impaired interval do not reconcile.' USING ERRCODE='23514'; END IF;
  after_gross:=gross+gi-cash;
  IF full_payoff THEN after_gross:=0; settlement:=settlement+cash-gross-gi; END IF;
  IF item ? 'verified_gross_after' AND (item->>'verified_gross_after')::numeric IS DISTINCT FROM after_gross THEN
   RAISE EXCEPTION 'Verified gross cash boundary does not reconcile.' USING ERRCODE='23514'; END IF;
  IF after_gross<0 THEN RAISE EXCEPTION 'Partial cash exceeds gross carrying; protected settlement is required.' USING ERRCODE='23514'; END IF;
  target:=(item->>'target_allowance')::numeric;
  deferred:=coalesce((item->>'defer_final_measurement')::boolean,false);
  IF deferred THEN
   IF day<>p_cutoff OR count_events<>jsonb_array_length(p_events) OR target IS NOT NULL OR full_payoff THEN
    RAISE EXCEPTION 'Only the final cutoff-day cash may use the final fiscal measurement.' USING ERRCODE='23514'; END IF;
   allowance:=allowance+unwind;
  ELSE
   IF target IS NULL OR target<0 OR target>after_gross OR target<>round(target,2)
    OR target::text IN('NaN','Infinity','-Infinity') OR (full_payoff AND target<>0) THEN
    RAISE EXCEPTION 'Dated reviewed allowance within remaining gross exposure is required.' USING ERRCODE='23514'; END IF;
   total_delta:=total_delta+target-allowance-unwind; allowance:=target;
  END IF;
  total_gi:=total_gi+gi; total_interval_gi:=total_interval_gi+interval_gi;
  total_unwind:=total_unwind+unwind; gross:=after_gross; last_day:=day; stopped:=full_payoff;
 END LOOP;
 IF NOT stopped AND NOT deferred THEN
  factor:=power(1+p_rate,greatest(least(p_cutoff,p_maturity)-least(last_day,p_maturity),0))-1;
  gi:=round(gross*factor,2); ni:=round((gross-allowance)*factor,2); unwind:=gi-ni;
  total_gi:=total_gi+gi; total_interval_gi:=total_interval_gi+gi;
  total_unwind:=total_unwind+unwind; gross:=gross+gi; allowance:=allowance+unwind;
 END IF;
 RETURN jsonb_build_object('gross_interest',total_gi,'net_interest',total_gi-total_unwind,'allowance_unwind',total_unwind,
  'gross_after',gross,'virtual_allowance_before_final_review',allowance,'virtual_impairment_adjustment',total_delta,
  'gross_settlement_difference',settlement,'final_measurement_deferred',deferred,
  'currency_rounding_adjustment',total_gi-total_interval_gi);
END $$;

CREATE OR REPLACE FUNCTION accounting.native_impaired_cash_candidate(p_period UUID,p_loan UUID,p_application UUID)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
DECLARE period accounting.fiscal_periods%ROWTYPE; posting accounting.treasury_application_postings%ROWTYPE;
 preparation accounting.treasury_application_preparations%ROWTYPE; transaction lending.collection_transactions%ROWTYPE;
  origin JSONB; opening JSONB; source JSONB; flows JSONB; inherited JSONB; contractual NUMERIC; gross NUMERIC; rate NUMERIC;
BEGIN
 SELECT * INTO period FROM accounting.fiscal_periods WHERE id=p_period;
 SELECT * INTO posting FROM accounting.treasury_application_postings WHERE application_id=p_application AND loan_id=p_loan;
 SELECT * INTO preparation FROM accounting.treasury_application_preparations WHERE id=posting.preparation_id;
 SELECT * INTO transaction FROM lending.collection_transactions WHERE id=posting.transaction_id;
 IF period.id IS NULL OR posting.id IS NULL OR transaction.loan_id IS DISTINCT FROM p_loan
  OR transaction.collection_date NOT BETWEEN period.start_date AND period.end_date
  OR preparation.snapshot->>'fiscal_period_id' IS DISTINCT FROM p_period::text THEN
  RETURN jsonb_build_object('ready',false,'blockers',jsonb_build_array('exact_posted_period_cash_required')); END IF;
 origin:=preparation.snapshot->'origin';
 SELECT x->'preparation' INTO opening FROM jsonb_array_elements(coalesce(origin->'prefix_claims','[]'::jsonb)) x
 WHERE x->>'exact'='true' ORDER BY (x#>>'{preparation,as_of_date}')::date DESC LIMIT 1;
  IF opening IS NULL THEN
   opening:=accounting.native_credit_impaired_opening(origin);
   IF opening#>>'{renewal_impairment_opening,net_interest_established}'='true'
    AND opening->>'renewal_review_id' IS NOT NULL
    AND (opening->>'as_of_date')::date BETWEEN period.start_date AND transaction.collection_date THEN
    inherited:=accounting.native_renewal_inherited_credit_review(p_loan);
    IF inherited#>>'{lineage,review_id}' IS DISTINCT FROM opening->>'renewal_review_id' THEN inherited:=NULL; END IF;
   END IF;
  END IF;
  IF opening IS NULL OR (inherited IS NULL AND (opening->>'as_of_date')::date IS DISTINCT FROM period.start_date-1)
   OR (opening->>'id' IS NULL AND inherited IS NULL)
  OR opening#>>'{measurement_snapshot,risk_review,stage_label}' IS DISTINCT FROM 'stage_3_credit_impaired' THEN
  RETURN jsonb_build_object('ready',false,'blockers',jsonb_build_array('posted_opening_impaired_assessment_required')); END IF;
 IF NOT EXISTS(SELECT 1 FROM accounting.treasury_application_posting_status s WHERE s.application_id=p_application
   AND s.exact_posted AND NOT s.correction_pending)
   OR (inherited IS NULL AND NOT accounting.period_elapsed_loan_assessment_exact((opening->>'fiscal_period_id')::uuid,p_loan)) THEN
  RETURN jsonb_build_object('ready',false,'blockers',jsonb_build_array('impaired_cash_source_not_exact')); END IF;
 IF EXISTS(SELECT 1 FROM lending.collection_transactions later WHERE later.loan_id=p_loan
  AND later.collection_date=transaction.collection_date AND (later.amount>0 OR later.entry_type IN('payment','advance'))
  AND (later.accepted_at,later.id)>(transaction.accepted_at,transaction.id)) THEN
  RETURN jsonb_build_object('ready',false,'blockers',jsonb_build_array('last_actual_cash_of_day_required')); END IF;
 IF accounting.regular_application_full_payoff(p_application) THEN
  RETURN jsonb_build_object('ready',false,'blockers',jsonb_build_array('exact_payoff_supplies_zero_cash_target')); END IF;
 rate:=(origin#>>'{measurement,daily_eir}')::numeric;
 gross:=(origin#>>'{measurement,loan_component_after}')::numeric+(origin#>>'{measurement,accrued_interest_after}')::numeric;
 IF gross IS NULL OR gross<=0 OR rate IS NULL OR origin#>>'{native_origin,ready}' IS DISTINCT FROM 'true' THEN
  RETURN jsonb_build_object('ready',false,'blockers',jsonb_build_array('verified_positive_native_cash_exposure_required')); END IF;
 SELECT coalesce(jsonb_agg(jsonb_build_object('id',i.id,'installment_number',i.installment_number,'due_date',i.due_date,
   'contractual_amount',i.contractual_amount,'allocated_amount',paid.amount,'remaining_amount',i.contractual_amount-paid.amount)
   ORDER BY i.installment_number),'[]'::jsonb),
  coalesce(sum((i.contractual_amount-paid.amount)/power(1+rate,greatest(i.due_date-transaction.collection_date,0))),0)
 INTO flows,contractual FROM lending.loan_contract_installments i
 CROSS JOIN LATERAL(SELECT coalesce(sum(a.amount_applied),0) amount FROM lending.loan_installment_payment_allocations a
  JOIN lending.collection_transactions t ON t.id=a.transaction_id WHERE a.installment_id=i.id AND NOT t.is_voided
   AND (t.collection_date,t.accepted_at,t.id)<=(transaction.collection_date,transaction.accepted_at,transaction.id)) paid
 WHERE i.schedule_id=(origin#>>'{anchor,schedule_id}')::uuid;
 IF contractual<=0 OR EXISTS(SELECT 1 FROM jsonb_array_elements(flows) x WHERE (x->>'remaining_amount')::numeric<0) THEN
  RETURN jsonb_build_object('ready',false,'blockers',jsonb_build_array('exact_remaining_signed_cash_flows_required')); END IF;
 source:=jsonb_build_object('policy_version','native_impaired_cash_source_v1','book',origin#>'{native_origin,snapshot,book}',
  'loan',origin->'loan','anchor',origin->'anchor','native_origin',origin->'native_origin','opening_assessment',opening,
  'fiscal_period_id',p_period,'cutoff_date',transaction.collection_date,'application_id',p_application,
  'application_preparation',to_jsonb(preparation),'application_posting',to_jsonb(posting),
  'gross_carrying_amount',gross,'prior_allowance',opening#>'{measurement_snapshot,ecl_amount}',
  'eir',jsonb_build_object('daily_eir',rate),'contractual_cash_flows',flows,'contractual_pv_raw',contractual);
 RETURN jsonb_build_object('ready',true,'blockers','[]'::jsonb,'snapshot',source,
  'source_digest',encode(sha256(convert_to(source::text,'UTF8')),'hex'),'book_id',posting.book_id,
  'application_id',p_application,'loan_id',p_loan,'as_of_date',transaction.collection_date,
  'gross_carrying_amount',gross::numeric(18,2)::text,'opening_assessment_id',opening->'id',
   'opening_cutoff_date',opening->'as_of_date')
   ||CASE WHEN inherited IS NOT NULL THEN jsonb_build_object('opening_renewal_review_id',opening->'renewal_review_id') ELSE '{}'::jsonb END;
END $$;

-- Preserve every original-EIR forecast eligibility/version/revocation check.
-- The posted opening Stage 3 label governs these intervals; no new label is
-- invented on the later cash day, and no caller supplies an allowance amount.
DO $$ DECLARE definition TEXT; first_pos INTEGER; last_pos INTEGER; BEGIN
 definition:=pg_get_functiondef('accounting.calculate_native_lifetime_assessment_ecl(jsonb,jsonb,jsonb)'::regprocedure);
 definition:=replace(definition,'accounting.calculate_native_lifetime_assessment_ecl(', 'accounting.calculate_native_impaired_cash_ecl(');
 first_pos:=strpos(definition,' IF p_risk IS NULL'); last_pos:=strpos(definition,' IF p_scenarios IS NULL');
 IF first_pos=0 OR last_pos<=first_pos THEN RAISE EXCEPTION 'Lifetime cash measurement predecessor changed.'; END IF;
 definition:=substr(definition,1,first_pos-1)||$risk$
 normalized_risk:=p_source#>'{opening_assessment,measurement_snapshot,risk_review}';
 IF normalized_risk->>'stage_label' IS DISTINCT FROM 'stage_3_credit_impaired'
   OR (p_source#>>'{opening_assessment,as_of_date}')::date>cutoff
   OR ((p_source#>>'{opening_assessment,as_of_date}')::date=cutoff AND NOT coalesce(
    p_source#>>'{opening_assessment,renewal_impairment_opening,net_interest_established}'='true'
    AND p_source#>>'{opening_assessment,renewal_review_id}' IS NOT NULL,false)) THEN
  RAISE EXCEPTION 'Exact posted opening impaired measurement is required.' USING ERRCODE='23514'; END IF;
 contractual:=(p_source->>'gross_carrying_amount')::numeric;
 normalized_risk:=normalized_risk||jsonb_build_object('as_of_date',cutoff);
$risk$||substr(definition,last_pos);
 definition:=replace(definition,'''historical_native_lifetime_cash_shortfall_v1''','''native_impaired_cash_expected_receipts_v1''');
 definition:=replace(definition,'''credit_risk_review_id'',(p_risk->>''credit_risk_review_id'')::bigint',
  '''opening_assessment_id'',p_source#>''{opening_assessment,id}''');
 EXECUTE definition;
END $$;

CREATE OR REPLACE FUNCTION accounting.guard_native_impaired_cash_review()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF TG_OP='INSERT' AND current_setting('accounting.impaired_cash_review_write',true)=NEW.id::text THEN RETURN NEW; END IF;
 RAISE EXCEPTION 'Dated impaired cash reviews are immutable and require the protected review command.' USING ERRCODE='55000';
END $$;
DROP TRIGGER IF EXISTS native_impaired_cash_review_guard ON accounting.native_impaired_cash_reviews;
CREATE TRIGGER native_impaired_cash_review_guard BEFORE INSERT OR UPDATE OR DELETE ON accounting.native_impaired_cash_reviews
 FOR EACH ROW EXECUTE FUNCTION accounting.guard_native_impaired_cash_review();
DROP TRIGGER IF EXISTS native_impaired_cash_review_truncate_guard ON accounting.native_impaired_cash_reviews;
CREATE TRIGGER native_impaired_cash_review_truncate_guard BEFORE TRUNCATE ON accounting.native_impaired_cash_reviews
 FOR EACH STATEMENT EXECUTE FUNCTION accounting.guard_native_impaired_cash_review();

CREATE OR REPLACE FUNCTION accounting.record_native_impaired_cash_review(p_period UUID,p_loan UUID,p_application UUID,
 p_actor UUID,p_digest TEXT,p_scenarios JSONB,p_rationale TEXT)
RETURNS UUID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
DECLARE candidate JSONB; measured JSONB; digest TEXT; retained UUID; created UUID:=gen_random_uuid(); old_setting TEXT; status TEXT;
BEGIN
 PERFORM accounting.require_loan_period_assessment_actor(p_actor,'accounting.period.close.prepare');
 IF p_digest IS NULL OR p_digest !~ '^[0-9a-f]{64}$' OR length(btrim(coalesce(p_rationale,''))) NOT BETWEEN 20 AND 2000 THEN
  RAISE EXCEPTION 'Exact source digest and substantive cash review rationale are required.' USING ERRCODE='22023'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('period-close:'||p_period::text,0));
 PERFORM pg_advisory_xact_lock(hashtextextended('loan-elapsed-assessment:'||p_loan::text,0));
 SELECT p.status INTO status FROM accounting.fiscal_periods p WHERE p.id=p_period FOR UPDATE;
 PERFORM accounting.lock_elapsed_assessment_sources();
 LOCK TABLE accounting.native_impaired_cash_reviews IN SHARE ROW EXCLUSIVE MODE;
 candidate:=accounting.native_impaired_cash_candidate(p_period,p_loan,p_application);
 IF candidate->>'ready' IS DISTINCT FROM 'true' THEN RAISE EXCEPTION 'Dated impaired cash source is blocked.' USING ERRCODE='23514'; END IF;
 IF candidate->>'source_digest' IS DISTINCT FROM p_digest THEN RAISE EXCEPTION 'Dated impaired cash source changed.' USING ERRCODE='40001'; END IF;
 measured:=accounting.calculate_native_impaired_cash_ecl(candidate->'snapshot','{}'::jsonb,p_scenarios);
 digest:=encode(sha256(convert_to(jsonb_build_object('source_digest',p_digest,'measurement',measured,'rationale',btrim(p_rationale))::text,'UTF8')),'hex');
 SELECT id INTO retained FROM accounting.native_impaired_cash_reviews WHERE application_id=p_application AND confirmation_digest=digest;
 IF FOUND THEN RETURN retained; END IF;
 IF status IS DISTINCT FROM 'open' OR EXISTS(SELECT 1 FROM accounting.loan_elapsed_assessment_postings WHERE fiscal_period_id=p_period AND loan_id=p_loan) THEN
  RAISE EXCEPTION 'New cash review requires an open, unposted fiscal assessment.' USING ERRCODE='55000'; END IF;
 old_setting:=current_setting('accounting.impaired_cash_review_write',true);
 PERFORM set_config('accounting.impaired_cash_review_write',created::text,true);
 INSERT INTO accounting.native_impaired_cash_reviews(id,book_id,fiscal_period_id,loan_id,application_id,transaction_id,
  as_of_date,source_digest,confirmation_digest,source_snapshot,scenarios,measurement_snapshot,review_rationale,prepared_by)
 VALUES(created,(candidate->>'book_id')::uuid,p_period,p_loan,p_application,
  (candidate#>>'{snapshot,application_posting,transaction_id}')::uuid,(candidate->>'as_of_date')::date,
  p_digest,digest,candidate->'snapshot',p_scenarios,measured,btrim(p_rationale),p_actor);
 PERFORM set_config('accounting.impaired_cash_review_write',coalesce(old_setting,''),true);
 RETURN created;
END $$;

CREATE OR REPLACE FUNCTION accounting.native_impaired_cash_review_exact(p_review UUID)
RETURNS BOOLEAN LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
DECLARE review accounting.native_impaired_cash_reviews%ROWTYPE; candidate JSONB; measured JSONB;
BEGIN
 SELECT * INTO review FROM accounting.native_impaired_cash_reviews WHERE id=p_review;
 IF NOT FOUND THEN RETURN false; END IF;
 candidate:=accounting.native_impaired_cash_candidate(review.fiscal_period_id,review.loan_id,review.application_id);
 IF candidate->>'ready' IS DISTINCT FROM 'true' OR candidate->>'source_digest' IS DISTINCT FROM review.source_digest
  OR candidate->'snapshot' IS DISTINCT FROM review.source_snapshot THEN RETURN false; END IF;
 measured:=accounting.calculate_native_impaired_cash_ecl(review.source_snapshot,'{}'::jsonb,review.scenarios);
 RETURN measured=review.measurement_snapshot AND review.confirmation_digest=encode(sha256(convert_to(
  jsonb_build_object('source_digest',review.source_digest,'measurement',measured,'rationale',review.review_rationale)::text,'UTF8')),'hex');
EXCEPTION WHEN check_violation OR invalid_parameter_value OR invalid_text_representation OR datetime_field_overflow THEN RETURN false;
END $$;

CREATE OR REPLACE FUNCTION accounting.assert_native_impaired_cash_review()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF NOT accounting.native_impaired_cash_review_exact(NEW.id) THEN
  RAISE EXCEPTION 'Dated impaired cash review source changed before commit.' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS native_impaired_cash_review_commit ON accounting.native_impaired_cash_reviews;
CREATE CONSTRAINT TRIGGER native_impaired_cash_review_commit AFTER INSERT ON accounting.native_impaired_cash_reviews
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION accounting.assert_native_impaired_cash_review();

DO $$ BEGIN
 IF to_regprocedure('accounting.native_credit_impaired_interest_before_cash(jsonb)') IS NULL THEN
  ALTER FUNCTION accounting.native_credit_impaired_interest(JSONB) RENAME TO native_credit_impaired_interest_before_cash; END IF;
 IF to_regprocedure('accounting.loan_period_before_impaired_cash_candidate(uuid,uuid)') IS NULL THEN
  ALTER FUNCTION accounting.loan_period_elapsed_assessment_candidate(UUID,UUID) RENAME TO loan_period_before_impaired_cash_candidate; END IF;
 IF to_regprocedure('accounting.lock_elapsed_before_impaired_cash_sources()') IS NULL THEN
  ALTER FUNCTION accounting.lock_elapsed_assessment_sources() RENAME TO lock_elapsed_before_impaired_cash_sources; END IF;
 IF to_regprocedure('accounting.period_review_before_impaired_cash_evidence(uuid)') IS NULL THEN
  ALTER FUNCTION accounting.period_review_additional_evidence(UUID) RENAME TO period_review_before_impaired_cash_evidence; END IF;
 IF to_regprocedure('accounting.lock_period_review_before_impaired_cash_sources()') IS NULL THEN
  ALTER FUNCTION accounting.lock_period_review_additional_sources() RENAME TO lock_period_review_before_impaired_cash_sources; END IF;
END $$;

CREATE OR REPLACE FUNCTION accounting.native_credit_impaired_interest(p_source JSONB)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
DECLARE opening JSONB; day_cash RECORD; prep accounting.treasury_application_preparations%ROWTYPE;
 review accounting.native_impaired_cash_reviews%ROWTYPE; measured JSONB; event JSONB;
 events JSONB:='[]'::jsonb; proofs JSONB:='[]'::jsonb; cutoff DATE:=(p_source->>'cutoff_date')::date;
 opening_day DATE; cumulative NUMERIC; gi NUMERIC; current_cumulative NUMERIC; after_gross NUMERIC;
  full_payoff BOOLEAN; target NUMERIC; retained_review JSONB; inherited BOOLEAN;
  rounding_delta NUMERIC; final_reviewed BOOLEAN;
BEGIN
 IF p_source->>'settled_by_exact_renewal'='true' THEN RETURN NULL; END IF;
 opening:=accounting.native_credit_impaired_opening(p_source);
 opening_day:=(opening->>'as_of_date')::date;
  inherited:=opening->>'renewal_review_id' IS NOT NULL AND opening#>>'{renewal_impairment_opening,net_interest_established}'='true';
 IF opening#>>'{measurement_snapshot,risk_review,stage_label}' IS DISTINCT FROM 'stage_3_credit_impaired'
  OR opening#>>'{renewal_impairment_opening,net_interest_established}'='false'
  OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(coalesce(p_source#>'{cash_rollforward,cash_claims}','[]'::jsonb)) x
     WHERE (x#>>'{transaction,collection_date}')::date>opening_day
      OR (inherited AND (x#>>'{transaction,collection_date}')::date=opening_day)) THEN
  RETURN accounting.native_credit_impaired_interest_before_cash(p_source); END IF;
 cumulative:=(opening#>>'{source_snapshot,eir,cumulative_interest}')::numeric;
 FOR day_cash IN
  SELECT DISTINCT ON(cash_day) cash_day,claim,day_amount FROM (
   SELECT (x#>>'{transaction,collection_date}')::date cash_day,x claim,
    sum((x#>>'{transaction,amount}')::numeric) OVER(PARTITION BY x#>>'{transaction,collection_date}') day_amount
   FROM jsonb_array_elements(p_source#>'{cash_rollforward,cash_claims}') x
    WHERE (x#>>'{transaction,collection_date}')::date>opening_day
     OR (inherited AND (x#>>'{transaction,collection_date}')::date=opening_day)) grouped
  ORDER BY cash_day,(claim#>>'{transaction,accepted_at}')::timestamptz DESC,claim#>>'{transaction,id}' DESC LOOP
  SELECT * INTO prep FROM accounting.treasury_application_preparations WHERE id=(day_cash.claim#>>'{posting,preparation_id}')::uuid;
  IF day_cash.claim#>>'{posting,exact_posted}' IS DISTINCT FROM 'true'
   OR day_cash.claim#>>'{posting,correction_pending}' IS DISTINCT FROM 'false' OR prep.id IS NULL THEN
   RAISE EXCEPTION 'Exact posted impaired cash chain is required.' USING ERRCODE='23514'; END IF;
  current_cumulative:=(prep.snapshot#>>'{measurement,cumulative_interest}')::numeric;
  after_gross:=(prep.snapshot#>>'{measurement,loan_component_after}')::numeric+(prep.snapshot#>>'{measurement,accrued_interest_after}')::numeric;
  full_payoff:=prep.snapshot#>>'{measurement,full_contractual_payoff}'='true'; full_payoff:=coalesce(full_payoff,false);
  IF full_payoff AND (prep.snapshot->>'accounting_policy_version' IS DISTINCT FROM 'treasury_regular_original_full_payoff_v1'
   OR NOT accounting.regular_application_full_payoff(prep.application_id)) THEN
   RAISE EXCEPTION 'Full impairment settlement requires exact protected payoff.' USING ERRCODE='23514'; END IF;
  event:=jsonb_build_object('cash_date',day_cash.cash_day,'cash',day_cash.day_amount,'full_payoff',full_payoff,
    'verified_gross_interest',current_cumulative-cumulative,'verified_gross_after',after_gross,
    'opening_day_cash',inherited AND day_cash.cash_day=opening_day);
  IF full_payoff THEN
   event:=event||jsonb_build_object('target_allowance',0);
  ELSIF day_cash.cash_day=cutoff AND p_source->>'renewal_boundary' IS DISTINCT FROM 'true' THEN
   -- No subsequent interest interval exists: the final cutoff scenarios are
   -- the dated measurement, without fabricating an interim target.
   event:=event||jsonb_build_object('defer_final_measurement',true,'target_allowance',NULL);
  ELSE
   IF p_source ? 'retained_impaired_cash_reviews' THEN
    SELECT x INTO retained_review FROM jsonb_array_elements(p_source->'retained_impaired_cash_reviews') x
     WHERE x->>'application_id'=prep.application_id::text;
    SELECT * INTO review FROM accounting.native_impaired_cash_reviews WHERE id=(retained_review->>'id')::uuid;
    IF retained_review IS DISTINCT FROM to_jsonb(review) THEN
     RAISE EXCEPTION 'Exact retained renewal cash review changed.' USING ERRCODE='23514'; END IF;
   ELSE
    SELECT * INTO review FROM accounting.native_impaired_cash_reviews WHERE application_id=prep.application_id
     ORDER BY calculated_at DESC,id DESC LIMIT 1;
   END IF;
   IF NOT FOUND OR NOT accounting.native_impaired_cash_review_exact(review.id) THEN
    RAISE EXCEPTION 'Dated impaired cash measurement is required before net-interest assessment.' USING ERRCODE='23514'; END IF;
   target:=(review.measurement_snapshot->>'ecl_amount')::numeric;
   event:=event||jsonb_build_object('target_allowance',target);
   proofs:=proofs||jsonb_build_array(to_jsonb(review));
  END IF;
  proofs:=proofs||jsonb_build_array(jsonb_build_object('cash_day',day_cash.cash_day,'application_posting',day_cash.claim->'posting',
   'application_measurement',prep.snapshot->'measurement','event',event));
  events:=events||jsonb_build_array(event); cumulative:=current_cumulative;
 END LOOP;
 measured:=accounting.native_credit_impaired_chain(opening_day,(opening#>>'{source_snapshot,gross_carrying_amount}')::numeric,
  (opening#>>'{measurement_snapshot,ecl_amount}')::numeric,(p_source#>>'{eir,daily_eir}')::numeric,
  cutoff,(p_source#>>'{anchor,contractual_due_date}')::date,events);
 gi:=(p_source#>>'{eir,cumulative_interest}')::numeric-(opening#>>'{source_snapshot,eir,cumulative_interest}')::numeric;
 IF gi IS NULL OR gi<0 OR gi<>round(gi,2) OR gi::text IN('NaN','Infinity','-Infinity') THEN
  RAISE EXCEPTION 'Verified gross interest must be nonnegative exact currency.' USING ERRCODE='23514'; END IF;
 -- Keep direct rounded net EIR. The protected cumulative gross source may carry
 -- a signed cent residual, which is disclosed separately from economic unwind.
 rounding_delta:=gi-(measured->>'gross_interest')::numeric;
 final_reviewed:=full_payoff OR ((event->>'cash_date')::date=cutoff AND event ? 'target_allowance'
  AND event->>'target_allowance' IS NOT NULL);
 after_gross:=(measured->>'gross_after')::numeric+CASE WHEN full_payoff THEN 0 ELSE rounding_delta END;
 IF after_gross<0 OR (final_reviewed AND (measured->>'virtual_allowance_before_final_review')::numeric>after_gross) THEN
  RAISE EXCEPTION 'Final reviewed allowance must remain within verified gross exposure.' USING ERRCODE='23514'; END IF;
 measured:=measured||jsonb_build_object('gross_interest',gi,
  'allowance_unwind',gi-(measured->>'net_interest')::numeric,
  'currency_rounding_adjustment',(measured->>'currency_rounding_adjustment')::numeric+rounding_delta,
  'gross_after',after_gross,
  'virtual_allowance_before_final_review',(measured->>'virtual_allowance_before_final_review')::numeric
    +CASE WHEN final_reviewed THEN 0 ELSE rounding_delta END,
  'virtual_impairment_adjustment',(measured->>'virtual_impairment_adjustment')::numeric
    -CASE WHEN final_reviewed THEN rounding_delta ELSE 0 END,
  'gross_settlement_difference',(measured->>'gross_settlement_difference')::numeric
    -CASE WHEN full_payoff THEN rounding_delta ELSE 0 END);
 RETURN jsonb_build_object('basis','original_eir_on_reviewed_net_carrying','opening_assessment_id',opening->'id',
  'opening_cutoff_date',opening_day,'impairment_boundary_date',opening_day,'gross_interest',gi::numeric(18,2)::text,
  'net_interest',(measured->>'net_interest')::numeric(18,2)::text,
  'allowance_unwind',(measured->>'allowance_unwind')::numeric(18,2)::text,'cash_measurements',proofs,
  'currency_rounding_adjustment',(measured->>'currency_rounding_adjustment')::numeric(18,2)::text,
   'cash_chain_measurement',measured)
   ||CASE WHEN inherited THEN jsonb_build_object('opening_renewal_review_id',opening->'renewal_review_id') ELSE '{}'::jsonb END;
END $$;

CREATE OR REPLACE FUNCTION accounting.loan_period_elapsed_assessment_candidate(p_period UUID,p_loan UUID)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
DECLARE candidate JSONB; source JSONB; opening JSONB; reviews JSONB;
BEGIN
 candidate:=accounting.loan_period_before_impaired_cash_candidate(p_period,p_loan);
 source:=candidate->'snapshot';
 IF candidate->>'ready' IS DISTINCT FROM 'true' OR NOT source ? 'native_origin' THEN RETURN candidate; END IF;
 opening:=accounting.native_credit_impaired_opening(source);
 IF opening#>>'{measurement_snapshot,risk_review,stage_label}' IS DISTINCT FROM 'stage_3_credit_impaired'
   OR opening#>>'{renewal_impairment_opening,net_interest_established}'='false'
  OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(coalesce(source#>'{cash_rollforward,cash_claims}','[]'::jsonb)) x
    WHERE (x#>>'{transaction,collection_date}')::date>(opening->>'as_of_date')::date
     OR (opening->>'renewal_review_id' IS NOT NULL AND (x#>>'{transaction,collection_date}')::date=(opening->>'as_of_date')::date)) THEN RETURN candidate; END IF;
 SELECT coalesce(jsonb_agg(to_jsonb(r) ORDER BY r.as_of_date,r.application_id),'[]'::jsonb) INTO reviews FROM (
  SELECT DISTINCT ON(application_id) * FROM accounting.native_impaired_cash_reviews
  WHERE fiscal_period_id=p_period AND loan_id=p_loan AND as_of_date<=(source->>'cutoff_date')::date
  ORDER BY application_id,calculated_at DESC,id DESC) r;
 source:=source||jsonb_build_object('impaired_cash_reviews',reviews);
 RETURN candidate||jsonb_build_object('snapshot',source,'source_digest',encode(sha256(convert_to(source::text,'UTF8')),'hex'));
END $$;

CREATE OR REPLACE FUNCTION accounting.lock_elapsed_assessment_sources()
RETURNS VOID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 PERFORM accounting.lock_elapsed_before_impaired_cash_sources();
 LOCK TABLE accounting.native_renewal_measurement_reviews,accounting.native_regular_asset_lineage,
  accounting.renewal_treatment_decisions,accounting.renewal_treatment_decision_voids IN SHARE MODE;
 LOCK TABLE accounting.native_impaired_cash_reviews IN SHARE ROW EXCLUSIVE MODE;
END $$;
CREATE OR REPLACE FUNCTION accounting.period_review_additional_evidence(p_period UUID)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
BEGIN
 RETURN accounting.period_review_before_impaired_cash_evidence(p_period)||jsonb_build_object('native_impaired_cash_reviews',
  (SELECT coalesce(jsonb_agg(to_jsonb(r) ORDER BY r.as_of_date,r.id),'[]'::jsonb) FROM accounting.native_impaired_cash_reviews r
   WHERE r.as_of_date<=(SELECT end_date FROM accounting.fiscal_periods WHERE id=p_period)));
END $$;
CREATE OR REPLACE FUNCTION accounting.lock_period_review_additional_sources()
RETURNS VOID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 PERFORM accounting.lock_period_review_before_impaired_cash_sources();
 LOCK TABLE accounting.native_impaired_cash_reviews IN SHARE MODE;
END $$;

DO $$ DECLARE f RECORD; r TEXT; BEGIN
 REVOKE ALL ON accounting.native_impaired_cash_reviews FROM PUBLIC;
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN EXECUTE format('REVOKE ALL ON accounting.native_impaired_cash_reviews FROM %I',r); END IF;
 END LOOP;
 FOR f IN SELECT p.oid::regprocedure signature FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
  WHERE n.nspname='accounting' AND (p.proname LIKE '%impaired_cash%' OR p.proname IN('native_credit_impaired_chain',
   'native_credit_impaired_interest','native_credit_impaired_interest_before_cash','loan_period_elapsed_assessment_candidate',
   'lock_elapsed_assessment_sources','period_review_additional_evidence','lock_period_review_additional_sources')) LOOP
  EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC',f.signature);
  FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
   IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN EXECUTE format('REVOKE ALL ON FUNCTION %s FROM %I',f.signature,r); END IF;
  END LOOP;
 END LOOP;
END $$;
COMMIT;
