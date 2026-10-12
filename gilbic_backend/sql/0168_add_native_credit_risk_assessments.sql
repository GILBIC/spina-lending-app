BEGIN;

CREATE OR REPLACE FUNCTION accounting.native_reviewed_stage_one_admitted(p_review JSONB)
RETURNS BOOLEAN LANGUAGE sql IMMUTABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT coalesce(p_review->>'stage_label'='stage_1_12_month' AND p_review->'default_label'='false'::jsonb
  AND p_review->>'write_off_label'='none' AND p_review->>'recovery_label' IN('none','cured','cash_recovery_observed')
  AND (p_review->>'snapshot_days_past_due')::integer>=0
  AND ((p_review->>'snapshot_days_past_due')::integer<30 OR p_review->'sicr_backstop_rebutted'='true'::jsonb)
  AND ((p_review->>'snapshot_days_past_due')::integer<90 OR p_review->'default_backstop_rebutted'='true'::jsonb)
  AND (NOT(coalesce((p_review->>'sicr_backstop_rebutted')::boolean,false) OR coalesce((p_review->>'default_backstop_rebutted')::boolean,false))
   OR (p_review->>'primary_evidence_basis'<>'contractual_dpd'
    AND length(btrim(coalesce(p_review->>'rebuttal_evidence_reference','')))>0
    AND length(btrim(coalesce(p_review->>'rebuttal_note','')))>0)),false);
$$;

-- A retained operational review proves its actual review day only. It cannot
-- silently supply historical risk labels for an earlier economic cutoff.
CREATE OR REPLACE FUNCTION accounting.native_cutoff_credit_risk_review(p_source JSONB,p_review BIGINT DEFAULT NULL)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE r accounting.ecl_credit_risk_label_reviews%ROWTYPE; cutoff DATE:=(p_source->>'cutoff_date')::date;
BEGIN
 SELECT * INTO r FROM accounting.ecl_credit_risk_label_reviews
 WHERE loan_id=(p_source#>>'{loan,id}')::uuid AND (created_at AT TIME ZONE 'Asia/Manila')::date<=cutoff
 ORDER BY review_version DESC LIMIT 1;
 IF NOT FOUND OR (p_review IS NOT NULL AND r.id<>p_review)
  OR (r.created_at AT TIME ZONE 'Asia/Manila')::date<>cutoff
  OR r.snapshot_schedule_id IS DISTINCT FROM (p_source#>>'{anchor,schedule_id}')::uuid
  OR r.snapshot_schedule_version IS DISTINCT FROM (p_source#>>'{anchor,schedule_version}')::integer
  OR r.snapshot_days_past_due IS DISTINCT FROM (p_source->>'dpd')::integer
  OR r.snapshot_due_unpaid_amount IS DISTINCT FROM (p_source->>'due_unpaid_amount')::numeric THEN RETURN NULL; END IF;
 IF r.stage_label='stage_1_12_month' AND NOT accounting.native_reviewed_stage_one_admitted(to_jsonb(r)) THEN RETURN NULL; END IF;
 RETURN to_jsonb(r);
END $$;

-- Reuse the dated, original-EIR cash-shortfall engine. Its financial arithmetic
-- and all forecast availability/version/revocation checks remain unchanged.
DO $$ DECLARE definition TEXT; original_name TEXT; first_pos INTEGER; last_pos INTEGER; BEGIN
  SELECT p.proname,pg_get_functiondef(p.oid) INTO original_name,definition FROM pg_proc p
  JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='accounting'
   AND p.proname LIKE 'calculate_elapsed%' AND p.prosrc LIKE '%normalized_risk:=p_risk||%'
   AND p.prosrc LIKE '%historical_original_timing_cash_shortfall_v1%' LIMIT 1;
  IF definition IS NULL THEN RAISE EXCEPTION 'Exact dated cash-shortfall engine is required.'; END IF;
  definition:=replace(definition,'accounting.'||original_name||'(','accounting.calculate_native_lifetime_assessment_ecl(');
  first_pos:=strpos(definition,' IF p_risk IS NULL'); last_pos:=strpos(definition,' IF p_scenarios IS NULL');
  IF first_pos=0 OR last_pos<=first_pos THEN RAISE EXCEPTION 'Dated risk admission changed; review required.'; END IF;
  definition:=substr(definition,1,first_pos-1)||$risk$
 IF p_risk IS NULL OR jsonb_typeof(p_risk)<>'object' OR (SELECT count(*) FROM jsonb_object_keys(p_risk))<>1
  OR coalesce(p_risk->>'credit_risk_review_id','') !~ '^[1-9][0-9]*$' THEN
  RAISE EXCEPTION 'Exact retained credit-risk review identity is required.' USING ERRCODE='23514'; END IF;
 normalized_risk:=accounting.native_cutoff_credit_risk_review(p_source,(p_risk->>'credit_risk_review_id')::bigint);
 IF normalized_risk IS NULL OR NOT (
  normalized_risk->>'stage_label' IN('stage_2_lifetime','stage_3_credit_impaired')) THEN
  RAISE EXCEPTION 'Exact dated lifetime review and risk backstops are required.' USING ERRCODE='23514'; END IF;
 normalized_risk:=normalized_risk||jsonb_build_object('as_of_date',cutoff);
 -- IFRS9 B5.5.33: impaired asset loss uses gross carrying, not contractual PV.
 IF normalized_risk->>'stage_label'='stage_3_credit_impaired' THEN contractual:=(p_source->>'gross_carrying_amount')::numeric; END IF;
$risk$||substr(definition,last_pos);
  definition:=replace(definition,'''historical_original_timing_cash_shortfall_v1''','''historical_native_lifetime_cash_shortfall_v1''');
  definition:=replace(definition,'''loss_horizon'',''12_month''','''loss_horizon'',''lifetime'',''credit_risk_review_id'',(p_risk->>''credit_risk_review_id'')::bigint');
  definition:=replace(definition,'''original_daily_eir'',rate',
   '''loss_basis'',CASE WHEN normalized_risk->>''stage_label''=''stage_3_credit_impaired'' THEN ''gross_carrying_less_expected_pv'' ELSE ''contractual_cash_shortfall'' END,''expected_cash_present_value'',(SELECT round(sum((x->>''probability'')::numeric*(x->>''expected_cash_flow_pv_raw'')::numeric),2) FROM jsonb_array_elements(normalized) x),''original_daily_eir'',rate');
  definition:=replace(definition,'loss:=greatest(contractual-expected_pv,0);',
   'loss:=CASE WHEN normalized_risk->>''stage_label''=''stage_3_credit_impaired'' THEN contractual-expected_pv ELSE greatest(contractual-expected_pv,0) END;');
  definition:=replace(definition,'round(weighted,2)','round(greatest(weighted,0),2)');
  EXECUTE definition;
 IF to_regprocedure('accounting.calculate_elapsed_assessment_before_risk_ecl(jsonb,jsonb,jsonb)') IS NULL THEN
  ALTER FUNCTION accounting.calculate_elapsed_assessment_ecl(JSONB,JSONB,JSONB) RENAME TO calculate_elapsed_assessment_before_risk_ecl;
 END IF;
END $$;

-- Retain full-precision weighted PV. Rounding the final loss once can differ
-- by a cent from subtracting two independently rounded display amounts.
DO $$ DECLARE definition TEXT; needle TEXT; BEGIN
 definition:=pg_get_functiondef('accounting.calculate_native_lifetime_assessment_ecl(jsonb,jsonb,jsonb)'::regprocedure);
 IF strpos(definition,'weighted_expected_cash_present_value_raw')=0 THEN
  needle:='''allowance_delta'',round(greatest(weighted,0),2)-(p_source->>''prior_allowance'')::numeric);';
  IF strpos(definition,needle)=0 THEN RAISE EXCEPTION 'Full-precision lifetime loss return changed.'; END IF;
  definition:=replace(definition,needle,$metadata$
  'allowance_delta',round(greatest(weighted,0),2)-(p_source->>'prior_allowance')::numeric)
  ||CASE WHEN normalized_risk->>'stage_label'='stage_3_credit_impaired' THEN jsonb_build_object(
   'weighted_expected_cash_present_value_raw',(contractual-weighted)::text,
   'currency_rounding_adjustment',round(greatest(weighted,0),2)-greatest(contractual-round(contractual-weighted,2),0))
   ELSE '{}'::jsonb END;
$metadata$);
  EXECUTE definition;
 END IF;
END $$;

-- Stage 1 retains its existing 12-month measurement basis. A retained review
-- can admit a separately evidenced rebuttal; it never turns that loan into a
-- lifetime-loss population or relaxes the 0070 backstop governance.
DO $$ DECLARE definition TEXT; first_pos INTEGER; last_pos INTEGER; BEGIN
 definition:=pg_get_functiondef('accounting.calculate_native_lifetime_assessment_ecl(jsonb,jsonb,jsonb)'::regprocedure);
 definition:=replace(definition,'accounting.calculate_native_lifetime_assessment_ecl(', 'accounting.calculate_native_reviewed_stage_one_ecl(');
 first_pos:=strpos(definition,' IF p_risk IS NULL'); last_pos:=strpos(definition,' IF p_scenarios IS NULL');
 IF first_pos=0 OR last_pos<=first_pos THEN RAISE EXCEPTION 'Retained 12-month risk admission predecessor changed.'; END IF;
 definition:=substr(definition,1,first_pos-1)||$risk$
 IF p_risk IS NULL OR jsonb_typeof(p_risk)<>'object' OR (SELECT count(*) FROM jsonb_object_keys(p_risk))<>1
  OR coalesce(p_risk->>'credit_risk_review_id','') !~ '^[1-9][0-9]*$' THEN
  RAISE EXCEPTION 'Exact retained credit-risk review identity is required.' USING ERRCODE='23514'; END IF;
 normalized_risk:=accounting.native_cutoff_credit_risk_review(p_source,(p_risk->>'credit_risk_review_id')::bigint);
 IF NOT accounting.native_reviewed_stage_one_admitted(normalized_risk) THEN
  RAISE EXCEPTION 'Exact dated Stage 1 review and separately evidenced backstop rebuttals are required.' USING ERRCODE='23514'; END IF;
 normalized_risk:=normalized_risk||jsonb_build_object('as_of_date',cutoff);
$risk$||substr(definition,last_pos);
 definition:=replace(definition,'''historical_native_lifetime_cash_shortfall_v1''','''historical_native_reviewed_12_month_cash_shortfall_v1''');
 definition:=replace(definition,'''loss_horizon'', ''lifetime''','''loss_horizon'', ''12_month''');
 definition:=replace(definition,'''loss_horizon'',''lifetime''','''loss_horizon'',''12_month''');
 EXECUTE definition;
END $$;
CREATE OR REPLACE FUNCTION accounting.calculate_elapsed_assessment_ecl(p_source JSONB,p_risk JSONB,p_scenarios JSONB)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE r JSONB;
BEGIN
 IF p_risk ? 'credit_risk_review_id' THEN
  r:=accounting.native_cutoff_credit_risk_review(p_source,(p_risk->>'credit_risk_review_id')::bigint);
  IF r->>'stage_label'='stage_1_12_month' THEN RETURN accounting.calculate_native_reviewed_stage_one_ecl(p_source,p_risk,p_scenarios); END IF;
  RETURN accounting.calculate_native_lifetime_assessment_ecl(p_source,p_risk,p_scenarios); END IF;
 IF p_source ? 'native_origin' AND coalesce(p_source->>'settled_by_exact_payoff','false')<>'true'
  AND coalesce(p_source->>'settled_by_exact_renewal','false')<>'true' THEN
  SELECT to_jsonb(review) INTO r FROM accounting.ecl_credit_risk_label_reviews review
  WHERE review.loan_id=(p_source#>>'{loan,id}')::uuid
   AND (review.created_at AT TIME ZONE 'Asia/Manila')::date<=(p_source->>'cutoff_date')::date
  ORDER BY review.review_version DESC LIMIT 1;
   IF r IS NULL THEN
    r:=accounting.native_renewal_inherited_credit_review((p_source#>>'{loan,id}')::uuid)->'risk_review';
   END IF;
  IF r IS NOT NULL THEN
   RAISE EXCEPTION 'Retained credit risk requires its exact dated review identity; legacy Stage 1 inputs cannot replace it.' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN accounting.calculate_elapsed_assessment_before_risk_ecl(p_source,p_risk,p_scenarios);
END $$;

-- Admit delinquent native sources only when the actual dated review proves the
-- schedule, unpaid amount and DPD used by that candidate. Keep legacy bytes.
DO $$ DECLARE name TEXT; definition TEXT; old_clause TEXT; BEGIN
 FOREACH name IN ARRAY ARRAY['loan_period_native_elapsed_assessment_candidate','loan_period_native_cash_assessment_candidate','loan_period_native_renewal_assessment_candidate'] LOOP
  IF to_regprocedure('accounting.'||name||'(uuid,uuid)') IS NULL THEN CONTINUE; END IF;
  definition:=pg_get_functiondef(to_regprocedure('accounting.'||name||'(uuid,uuid)'));
  IF strpos(definition,'dated_native_lifetime_risk_review_required')>0 THEN
   definition:=replace(definition,'NOT IN(''stage_2_lifetime'',''stage_3_credit_impaired'')',
    'NOT IN(''stage_1_12_month'',''stage_2_lifetime'',''stage_3_credit_impaired'')');
   EXECUTE definition; CONTINUE; END IF;
  old_clause:='IF dpd>=30 THEN blockers:=array_append(blockers,''historical_risk_stage_extension_required''); END IF;';
  IF strpos(definition,old_clause)=0 THEN RAISE EXCEPTION 'Native risk source boundary changed in %.',name; END IF;
  definition:=replace(definition,old_clause,$admit$
 IF dpd>=30 AND coalesce(accounting.native_cutoff_credit_risk_review(jsonb_build_object(
  'loan',jsonb_build_object('id',p_loan),'anchor',jsonb_build_object('schedule_id',anchor.schedule_id,'schedule_version',anchor.schedule_version),
  'cutoff_date',period_row.end_date,'dpd',dpd,'due_unpaid_amount',due_unpaid))->>'stage_label','') NOT IN('stage_1_12_month','stage_2_lifetime','stage_3_credit_impaired') THEN
  blockers:=array_append(blockers,'dated_native_lifetime_risk_review_required'); END IF;
$admit$);
  EXECUTE definition;
 END LOOP;
END $$;

-- No labels, dates, forecasts or payoff authority are inferred by this arithmetic
-- primitive. Its protected callers supply exact source-derived inputs.
CREATE OR REPLACE FUNCTION accounting.native_credit_impaired_interval(p_gross NUMERIC,p_allowance NUMERIC,p_rate NUMERIC,
 p_days INTEGER,p_cash NUMERIC,p_target NUMERIC,p_full_payoff BOOLEAN)
RETURNS JSONB LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE factor NUMERIC; gi NUMERIC; ni NUMERIC; unwind NUMERIC; remaining NUMERIC;
BEGIN
 IF p_gross IS NULL OR p_allowance IS NULL OR p_rate IS NULL OR p_days IS NULL OR p_cash IS NULL OR p_target IS NULL OR p_full_payoff IS NULL
  OR p_gross::text IN('NaN','Infinity','-Infinity') OR p_allowance::text IN('NaN','Infinity','-Infinity')
  OR p_rate::text IN('NaN','Infinity','-Infinity') OR p_cash::text IN('NaN','Infinity','-Infinity') OR p_target::text IN('NaN','Infinity','-Infinity')
  OR p_gross<0 OR p_allowance<0 OR p_allowance>p_gross OR p_rate<0 OR p_rate>1 OR p_days<0 OR p_days>36600
  OR p_cash<0 OR p_target<0 OR p_gross<>round(p_gross,2) OR p_allowance<>round(p_allowance,2)
  OR p_cash<>round(p_cash,2) OR p_target<>round(p_target,2) THEN
  RAISE EXCEPTION 'Exact bounded impaired interval inputs and reviewed allowance are required.' USING ERRCODE='23514'; END IF;
 factor:=power(1+p_rate,p_days)-1; gi:=round(p_gross*factor,2); ni:=round((p_gross-p_allowance)*factor,2); unwind:=gi-ni;
 remaining:=p_gross+gi-p_cash;
 IF p_full_payoff THEN
  IF p_cash<=0 OR p_target<>0 THEN RAISE EXCEPTION 'Exact full payoff requires actual cash and zero remaining allowance.' USING ERRCODE='23514'; END IF;
  remaining:=0;
 ELSIF remaining<0 THEN RAISE EXCEPTION 'Partial cash exceeds gross carrying; a reviewed settlement treatment is required.' USING ERRCODE='23514'; END IF;
 IF p_target>remaining THEN RAISE EXCEPTION 'Reviewed loss allowance exceeds remaining gross exposure.' USING ERRCODE='23514'; END IF;
 RETURN jsonb_build_object('gross_interest',gi,'net_interest',ni,'allowance_unwind',unwind,
  'gross_after',remaining,'allowance_before_review',p_allowance+unwind,'allowance_after',p_target,
  'allowance_delta',p_target-p_allowance-unwind,'net_after',remaining-p_target,
  'gross_settlement_difference',CASE WHEN p_full_payoff THEN p_cash-p_gross-gi ELSE 0 END);
END $$;

CREATE OR REPLACE FUNCTION accounting.native_credit_impaired_opening(p_source JSONB)
RETURNS JSONB LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE opening JSONB; inherited JSONB:=coalesce(p_source#>'{anchor,impairment_opening}',p_source#>'{native_origin,anchor,impairment_opening}');
BEGIN
 SELECT x->'preparation' INTO opening FROM jsonb_array_elements(coalesce(p_source->'prior_prefixes','[]'::jsonb)) x
 ORDER BY (x#>>'{preparation,as_of_date}')::date DESC LIMIT 1;
 IF opening IS NOT NULL THEN RETURN opening; END IF;
 IF inherited IS NULL THEN RETURN NULL; END IF;
  RETURN jsonb_build_object('id',NULL,'renewal_review_id',inherited->'renewal_review_id','as_of_date',inherited->'anchor_date',
   'source_snapshot',jsonb_build_object('gross_carrying_amount',coalesce(p_source#>'{anchor,initial_gross_carrying_amount}',p_source#>'{native_origin,anchor,initial_gross_carrying_amount}'),
   'eir',jsonb_build_object('cumulative_interest',0)),
  'measurement_snapshot',jsonb_build_object('ecl_amount',inherited->'initial_allowance',
   'risk_review',coalesce(inherited->'impairment_risk_review',inherited->'credit_risk_review')),'renewal_impairment_opening',inherited);
END $$;

CREATE OR REPLACE FUNCTION accounting.native_credit_impaired_interest(p_source JSONB)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE opening JSONB; risk JSONB; gross_interest NUMERIC; unwind NUMERIC; last_day DATE;
 factor NUMERIC; interval_gross NUMERIC; net_interest NUMERIC;
 cutoff DATE:=(p_source->>'cutoff_date')::date; rate NUMERIC:=(p_source#>>'{eir,daily_eir}')::numeric;
BEGIN
 IF p_source->>'settled_by_exact_renewal'='true' THEN RETURN NULL; END IF;
 opening:=accounting.native_credit_impaired_opening(p_source);
 gross_interest:=(p_source#>>'{eir,cumulative_interest}')::numeric-coalesce((opening#>>'{source_snapshot,eir,cumulative_interest}')::numeric,0);
 IF opening#>>'{renewal_impairment_opening,net_interest_established}'='false' THEN
  RETURN jsonb_build_object('basis','gross_before_initial_impaired_cutoff','opening_assessment_id',NULL,
   'opening_cutoff_date',NULL,'impairment_boundary_date',cutoff,'gross_interest',gross_interest::numeric(18,2)::text,
   'net_interest',gross_interest::numeric(18,2)::text,'allowance_unwind','0.00','cash_measurements','[]'::jsonb);
 END IF;
 IF opening#>>'{measurement_snapshot,risk_review,stage_label}' IS DISTINCT FROM 'stage_3_credit_impaired' THEN
  risk:=accounting.native_cutoff_credit_risk_review(p_source);
  IF risk->>'stage_label' IS DISTINCT FROM 'stage_3_credit_impaired' THEN RETURN NULL; END IF;
  RETURN jsonb_build_object('basis','gross_before_initial_impaired_cutoff','opening_assessment_id',NULL,
   'opening_cutoff_date',NULL,'impairment_boundary_date',cutoff,'gross_interest',gross_interest::numeric(18,2)::text,
   'net_interest',gross_interest::numeric(18,2)::text,'allowance_unwind','0.00','cash_measurements','[]'::jsonb);
 END IF;
 last_day:=(opening->>'as_of_date')::date;
 IF EXISTS(SELECT 1 FROM jsonb_array_elements(coalesce(p_source#>'{cash_rollforward,cash_claims}','[]'::jsonb)) x
   WHERE (x#>>'{transaction,collection_date}')::date>last_day) THEN
  RAISE EXCEPTION 'Dated impaired cash measurement is required before net-interest assessment.' USING ERRCODE='23514'; END IF;
 factor:=power(1+rate,greatest(least(cutoff,(p_source#>>'{anchor,contractual_due_date}')::date)-least(last_day,(p_source#>>'{anchor,contractual_due_date}')::date),0))-1;
 interval_gross:=round((opening#>>'{source_snapshot,gross_carrying_amount}')::numeric*factor,2);
 net_interest:=round(((opening#>>'{source_snapshot,gross_carrying_amount}')::numeric
  -(opening#>>'{measurement_snapshot,ecl_amount}')::numeric)*factor,2);
 -- Cumulative protected gross accrual can differ from rounded interval accrual.
 -- Preserve that source and direct net EIR; disclose the signed currency residual.
 unwind:=gross_interest-net_interest;
 IF gross_interest IS NULL OR net_interest IS NULL OR gross_interest<0 OR net_interest<0
  OR gross_interest<>round(gross_interest,2)
  OR EXISTS(SELECT 1 FROM unnest(ARRAY[gross_interest,net_interest,interval_gross]) v WHERE v::text IN('NaN','Infinity','-Infinity')) THEN
  RAISE EXCEPTION 'Verified net carrying interval is required.' USING ERRCODE='23514'; END IF;
 RETURN jsonb_build_object('basis','original_eir_on_reviewed_net_carrying','opening_assessment_id',opening->'id',
  'opening_cutoff_date',last_day,'impairment_boundary_date',last_day,'gross_interest',gross_interest::numeric(18,2)::text,
   'net_interest',net_interest::numeric(18,2)::text,'allowance_unwind',unwind::numeric(18,2)::text,
   'currency_rounding_adjustment',(gross_interest-interval_gross)::numeric(18,2)::text,'cash_measurements','[]'::jsonb)
   ||CASE WHEN opening->>'renewal_review_id' IS NOT NULL THEN jsonb_build_object('opening_renewal_review_id',opening->'renewal_review_id') ELSE '{}'::jsonb END;
END $$;

-- Replaying 168 then 169 must refresh the saved pre-cash implementation too.
DO $$ DECLARE definition TEXT; BEGIN
 IF to_regprocedure('accounting.native_credit_impaired_interest_before_cash(jsonb)') IS NOT NULL THEN
  definition:=pg_get_functiondef('accounting.native_credit_impaired_interest(jsonb)'::regprocedure);
  EXECUTE replace(definition,'accounting.native_credit_impaired_interest(', 'accounting.native_credit_impaired_interest_before_cash(');
 END IF;
END $$;

DO $$ DECLARE definition TEXT; BEGIN
 IF to_regprocedure('accounting.calculate_elapsed_before_impaired_ecl(jsonb,jsonb,jsonb)') IS NULL THEN
  ALTER FUNCTION accounting.calculate_elapsed_assessment_ecl(JSONB,JSONB,JSONB) RENAME TO calculate_elapsed_before_impaired_ecl;
 ELSE
  definition:=pg_get_functiondef('accounting.calculate_elapsed_assessment_ecl(jsonb,jsonb,jsonb)'::regprocedure);
  EXECUTE replace(definition,'accounting.calculate_elapsed_assessment_ecl(', 'accounting.calculate_elapsed_before_impaired_ecl(');
 END IF;
 IF to_regprocedure('accounting.elapsed_assessment_before_impaired_lines(uuid,text)') IS NULL THEN
  ALTER FUNCTION accounting.elapsed_assessment_lines(UUID,TEXT) RENAME TO elapsed_assessment_before_impaired_lines; END IF;
END $$;
CREATE OR REPLACE FUNCTION accounting.calculate_elapsed_assessment_ecl(p_source JSONB,p_risk JSONB,p_scenarios JSONB)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE measured JSONB; interest JSONB;
BEGIN
 measured:=accounting.calculate_elapsed_before_impaired_ecl(p_source,p_risk,p_scenarios);
 IF NOT p_source ? 'native_origin' THEN RETURN measured; END IF;
 interest:=accounting.native_credit_impaired_interest(p_source);
 IF interest IS NULL THEN RETURN measured; END IF;
 IF measured#>>'{risk_review,stage_label}' IN('stage_1_12_month','stage_2_lifetime')
  AND measured#>>'{risk_review,recovery_label}' IS DISTINCT FROM 'cured' THEN
  RAISE EXCEPTION 'Objective retained cure review is required to leave impaired status.' USING ERRCODE='23514'; END IF;
 RETURN measured||jsonb_build_object('credit_impaired_interest',interest,
  'allowance_delta',(measured->>'allowance_delta')::numeric-(interest->>'allowance_unwind')::numeric);
END $$;

-- Gross accrual is already exact, including cash journals. Reclassify its
-- fiscal-period gross/net difference once; never recognize it again on cure.
CREATE OR REPLACE FUNCTION accounting.native_credit_impaired_unwind_lines(p_unwind NUMERIC)
RETURNS TABLE(line_number INTEGER,account_code TEXT,debit NUMERIC,credit NUMERIC)
LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF p_unwind IS NULL OR p_unwind<>round(p_unwind,2) OR p_unwind::text IN('NaN','Infinity','-Infinity') THEN
  RAISE EXCEPTION 'Exact signed currency reconciliation is required.' USING ERRCODE='23514'; END IF;
 RETURN QUERY SELECT * FROM (VALUES
  (1,'4000'::text,greatest(p_unwind,0),greatest(-p_unwind,0)),
  (2,'1190'::text,greatest(-p_unwind,0),greatest(p_unwind,0))) x(n,code,dr,cr) WHERE p_unwind<>0;
END $$;

CREATE OR REPLACE FUNCTION accounting.elapsed_assessment_lines(p_preparation UUID,p_kind TEXT)
RETURNS TABLE(line_number INTEGER,account_id UUID,debit NUMERIC,credit NUMERIC,client_id UUID,loan_id UUID)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 WITH basis AS(SELECT p.*,coalesce((p.measurement_snapshot#>>'{credit_impaired_interest,allowance_unwind}')::numeric,0) AS unwind
  FROM accounting.loan_elapsed_assessment_preparations p WHERE p.id=p_preparation)
 SELECT x.line_number+CASE WHEN p_kind='ecl' AND b.unwind<>0 THEN 2 ELSE 0 END,x.account_id,x.debit,x.credit,x.client_id,x.loan_id
 FROM accounting.elapsed_assessment_before_impaired_lines(p_preparation,p_kind) x CROSS JOIN basis b
 UNION ALL SELECT x.line_number,(a->>'id')::uuid,x.debit,x.credit,b.client_id,b.loan_id
 FROM basis b CROSS JOIN LATERAL accounting.native_credit_impaired_unwind_lines(b.unwind) x
 CROSS JOIN LATERAL jsonb_array_elements(b.source_snapshot->'chart') a
 WHERE p_kind='ecl' AND a->>'code'=x.account_code;
$$;
DO $$ DECLARE definition TEXT; BEGIN
 definition:=pg_get_functiondef('accounting.elapsed_assessment_journal_exact(uuid,uuid,text)'::regprocedure);
 definition:=replace(definition,'AND 2=(SELECT count(*) FROM accounting.journal_lines WHERE journal_entry_id=j.id)',
  'AND (SELECT count(*) FROM accounting.elapsed_assessment_lines(p.id,p_kind))=(SELECT count(*) FROM accounting.journal_lines WHERE journal_entry_id=j.id)');
 definition:=replace(definition,'AND 2=(SELECT count(*) FROM accounting.elapsed_assessment_lines(p.id,p_kind))',
  'AND (SELECT count(*) FROM accounting.elapsed_assessment_lines(p.id,p_kind))>0');
 EXECUTE definition;
 definition:=pg_get_functiondef('accounting.period_elapsed_loan_assessment_exact(uuid,uuid)'::regprocedure);
 definition:=replace(definition,'CASE WHEN delta=0 THEN',
  'CASE WHEN delta=0 AND coalesce((measured#>>''{credit_impaired_interest,allowance_unwind}'')::numeric,0)=0 THEN');
 EXECUTE definition;
END $$;

CREATE OR REPLACE FUNCTION accounting.prepare_elapsed_loan_risk_assessment(p_period UUID,p_loan UUID,p_actor UUID,
 p_digest TEXT,p_review BIGINT,p_scenarios JSONB,p_rationale TEXT)
RETURNS UUID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 -- The existing writer rechecks actor, source locks/digest and full retained
 -- risk/evidence measurement, then retains the immutable confirmation bytes.
 IF p_review IS NULL OR p_review<=0 THEN RAISE EXCEPTION 'Retained risk review identity is required.' USING ERRCODE='22023'; END IF;
 RETURN accounting.prepare_elapsed_loan_period_assessment(p_period,p_loan,p_actor,p_digest,
  jsonb_build_object('credit_risk_review_id',p_review),p_scenarios,p_rationale);
END $$;

DO $$ DECLARE f RECORD; r TEXT; BEGIN
 FOR f IN SELECT p.oid::regprocedure signature FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
  WHERE n.nspname='accounting' AND p.proname IN('native_cutoff_credit_risk_review','calculate_native_lifetime_assessment_ecl',
   'calculate_elapsed_assessment_before_risk_ecl','calculate_elapsed_assessment_ecl','prepare_elapsed_loan_risk_assessment',
   'native_credit_impaired_interval','native_credit_impaired_opening','native_credit_impaired_interest','native_credit_impaired_unwind_lines','calculate_elapsed_before_impaired_ecl',
   'native_reviewed_stage_one_admitted','calculate_native_reviewed_stage_one_ecl',
   'elapsed_assessment_before_impaired_lines','elapsed_assessment_lines') LOOP
  EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC',f.signature);
  FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
   IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN EXECUTE format('REVOKE ALL ON FUNCTION %s FROM %I',f.signature,r); END IF;
  END LOOP;
 END LOOP;
END $$;
COMMIT;
