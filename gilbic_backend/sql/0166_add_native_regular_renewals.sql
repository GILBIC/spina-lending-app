BEGIN;

-- New reviews need causal creation time; retained rows keep their original dates.
ALTER TABLE accounting.ecl_credit_risk_label_reviews ALTER COLUMN created_at SET DEFAULT clock_timestamp();

DO $$ DECLARE expected RECORD; BEGIN
 FOR expected IN SELECT * FROM (VALUES
  ('4020','regular_renewal_gain','Regular Renewal Gain','income','credit'),
  ('5010','regular_renewal_loss','Regular Renewal Loss','expense','debit')) x(code,system_key,name,account_type,normal_balance) LOOP
  IF EXISTS(SELECT 1 FROM accounting.accounts a WHERE (a.code=expected.code OR a.system_key=expected.system_key)
   AND (a.code,a.system_key,a.account_type,a.normal_balance,a.is_posting)
    IS DISTINCT FROM(expected.code,expected.system_key,expected.account_type,expected.normal_balance,true)) THEN
   RAISE EXCEPTION 'Renewal gain/loss role conflicts with the retained chart.' USING ERRCODE='23514';
  END IF;
  INSERT INTO accounting.accounts(code,system_key,name,account_type,normal_balance)
  VALUES(expected.code,expected.system_key,expected.name,expected.account_type,expected.normal_balance) ON CONFLICT(system_key) DO NOTHING;
 END LOOP;
END $$;

-- All inputs are retained server-derived source amounts except the separately
-- reviewed derecognition fair value and settlement consideration. This pure
-- decomposition never chooses the treatment or substitutes principal for value.
CREATE OR REPLACE FUNCTION accounting.native_renewal_measurement(p_basis JSONB)
RETURNS JSONB LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE treatment TEXT:=p_basis->>'decision'; loan NUMERIC:=(p_basis->>'old_loan_component')::numeric;
 accrued NUMERIC:=(p_basis->>'old_accrued_interest')::numeric; allowance NUMERIC:=(p_basis->>'old_allowance')::numeric;
 cash NUMERIC:=(p_basis->>'fresh_cash')::numeric; revised NUMERIC:=(p_basis->>'revised_pv')::numeric;
 settlement NUMERIC:=(p_basis->>'settlement_consideration')::numeric; fair NUMERIC:=(p_basis->>'new_initial_fair_value')::numeric;
 old_difference NUMERIC; new_difference NUMERIC:=0; measured NUMERIC; new_allowance NUMERIC; lines JSONB;
 impairment JSONB:=p_basis->'credit_impaired_boundary'; before_allowance NUMERIC; unwind NUMERIC:=0; adjustment NUMERIC:=0;
BEGIN
 IF treatment IS NULL OR treatment NOT IN('modification_no_derecognition','derecognition')
  OR loan IS NULL OR accrued IS NULL OR allowance IS NULL OR cash IS NULL OR revised IS NULL
  OR loan<0 OR accrued<0 OR loan+accrued<=0 OR allowance<0 OR allowance>loan+accrued OR cash<=0 OR revised<=0
  OR EXISTS(SELECT 1 FROM unnest(ARRAY[loan,accrued,allowance,cash,revised]) v WHERE v<>round(v,2)) THEN
  RAISE EXCEPTION 'Exact positive renewed asset, fresh cash and old carrying components are required.' USING ERRCODE='23514';
 END IF;
 IF impairment IS NOT NULL THEN
  before_allowance:=(impairment->>'allowance_before')::numeric;
  unwind:=(impairment->>'allowance_unwind')::numeric;
  adjustment:=(impairment->>'impairment_adjustment')::numeric;
  IF before_allowance IS NULL OR unwind IS NULL OR adjustment IS NULL OR before_allowance<0
   OR (impairment->>'allowance_after')::numeric IS DISTINCT FROM allowance
   OR before_allowance+unwind+adjustment<>allowance
   OR EXISTS(SELECT 1 FROM unnest(ARRAY[before_allowance,unwind,adjustment]) v WHERE v<>round(v,2) OR v::text IN('NaN','Infinity','-Infinity')) THEN
   RAISE EXCEPTION 'Exact reconciled impairment boundary is required.' USING ERRCODE='23514'; END IF;
 END IF;
 IF treatment='modification_no_derecognition' THEN
  measured:=revised; new_allowance:=allowance;
  old_difference:=measured-loan-accrued-cash;
 ELSE
  IF settlement IS NULL OR settlement<0 OR fair IS NULL OR fair<=0 OR settlement<>round(settlement,2) OR fair<>round(fair,2) THEN
   RAISE EXCEPTION 'Derecognition requires explicit reviewed settlement consideration and new initial fair value.' USING ERRCODE='23514';
  END IF;
  measured:=fair; new_allowance:=0;
  old_difference:=settlement-(loan+accrued-allowance);
  new_difference:=fair-settlement-cash;
 END IF;
 SELECT coalesce(jsonb_agg(jsonb_build_object('line_number',x.n,'component',x.component,'account_code',x.code,
  'loan_role',x.loan_role,'debit',x.dr::numeric(18,2)::text,'credit',x.cr::numeric(18,2)::text) ORDER BY x.n),'[]'::jsonb)
 INTO lines FROM (VALUES
  (10,'renewed_asset','1100','new',measured,0::numeric),
  (20,'old_loan_component','1100','old',0::numeric,loan),
  (30,'old_accrued_interest','1120','old',0::numeric,accrued),
  (40,'fresh_cash_transit','1050','new',0::numeric,cash),
  (50,'old_allowance','1190','old',allowance,0::numeric),
  (60,'continued_allowance','1190','new',0::numeric,new_allowance),
  (70,'old_asset_difference',CASE WHEN old_difference>=0 THEN '4020' ELSE '5010' END,'old',greatest(-old_difference,0),greatest(old_difference,0)),
  (80,'new_asset_difference',CASE WHEN new_difference>=0 THEN '4020' ELSE '5010' END,'new',greatest(-new_difference,0),greatest(new_difference,0)),
  (90,'old_asset_allowance_unwind','4000','old',greatest(unwind,0),greatest(-unwind,0)),
  (100,'old_asset_allowance_unwind','1190','old',greatest(-unwind,0),greatest(unwind,0)),
  (110,'old_asset_impaired_adjustment','5000','old',greatest(adjustment,0),greatest(-adjustment,0)),
  (120,'old_asset_impaired_adjustment','1190','old',greatest(-adjustment,0),greatest(adjustment,0))) x(n,component,code,loan_role,dr,cr)
 WHERE x.dr+x.cr>0;
 IF (SELECT sum((x->>'debit')::numeric-(x->>'credit')::numeric) FROM jsonb_array_elements(lines) x)<>0 THEN
  RAISE EXCEPTION 'Renewal decomposition is not balanced.' USING ERRCODE='23514';
 END IF;
 RETURN jsonb_build_object('policy_version','native_regular_renewal_measurement_v1','decision',treatment,
  'accounting_asset_continues',treatment='modification_no_derecognition','old_gross_carrying',(loan+accrued)::numeric(18,2)::text,
  'old_allowance',allowance::numeric(18,2)::text,'fresh_cash',cash::numeric(18,2)::text,
  'new_initial_carrying',measured::numeric(18,2)::text,'new_initial_allowance',new_allowance::numeric(18,2)::text,
  'old_asset_difference',old_difference::numeric(18,2)::text,'new_asset_difference',new_difference::numeric(18,2)::text,'lines',lines)
  ||CASE WHEN impairment IS NULL THEN '{}'::jsonb ELSE jsonb_build_object('credit_impaired_boundary',impairment) END;
END $$;

CREATE TABLE IF NOT EXISTS accounting.native_renewal_measurement_reviews(
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),request_id UUID NOT NULL UNIQUE,
 payout_id UUID NOT NULL REFERENCES treasury.loan_payouts(id),
 execution_id UUID NOT NULL REFERENCES lending.loan_renewal_execution_events(id),
 decision_id UUID NOT NULL REFERENCES accounting.renewal_treatment_decisions(id),
 book_id UUID NOT NULL REFERENCES accounting.book_identity(id),
 actor_user_id UUID NOT NULL REFERENCES core.users(id),
 evidence_id UUID NOT NULL REFERENCES treasury.evidence(id),
 source_digest TEXT NOT NULL CHECK(source_digest ~ '^[0-9a-f]{64}$'),
 measurement_digest TEXT NOT NULL CHECK(measurement_digest ~ '^[0-9a-f]{64}$'),
 source_snapshot JSONB NOT NULL,reviewed_measurement JSONB NOT NULL,review_note TEXT NOT NULL CHECK(length(btrim(review_note))>=20),
 reviewed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS accounting.native_regular_asset_lineage(
 operational_loan_id UUID PRIMARY KEY REFERENCES lending.loans(id),
 accounting_asset_id UUID NOT NULL REFERENCES lending.loans(id),
 previous_operational_loan_id UUID NOT NULL UNIQUE REFERENCES lending.loans(id),
 payout_id UUID NOT NULL UNIQUE REFERENCES treasury.loan_payouts(id),
 execution_id UUID NOT NULL UNIQUE REFERENCES lending.loan_renewal_execution_events(id),
 review_id UUID NOT NULL UNIQUE REFERENCES accounting.native_renewal_measurement_reviews(id),
 preparation_id UUID NOT NULL UNIQUE REFERENCES accounting.loan_payout_accounting_preparations(id),
 journal_entry_id UUID NOT NULL UNIQUE REFERENCES accounting.journal_entries(id),
 effective_date DATE NOT NULL,anchor JSONB NOT NULL,actor_user_id UUID NOT NULL REFERENCES core.users(id),
 created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
 CHECK(operational_loan_id<>previous_operational_loan_id)
);
DO $$ DECLARE table_name TEXT; r TEXT; BEGIN
 FOREACH table_name IN ARRAY ARRAY['native_renewal_measurement_reviews','native_regular_asset_lineage'] LOOP
  EXECUTE format('ALTER TABLE accounting.%I ENABLE ROW LEVEL SECURITY',table_name);
  EXECUTE format('DROP TRIGGER IF EXISTS native_renewal_immutable ON accounting.%I',table_name);
  EXECUTE format('CREATE TRIGGER native_renewal_immutable BEFORE INSERT OR UPDATE OR DELETE ON accounting.%I FOR EACH ROW EXECUTE FUNCTION accounting.guard_treasury_gl_evidence()',table_name);
  EXECUTE format('DROP TRIGGER IF EXISTS native_renewal_truncate ON accounting.%I',table_name);
  EXECUTE format('CREATE TRIGGER native_renewal_truncate BEFORE TRUNCATE ON accounting.%I FOR EACH STATEMENT EXECUTE FUNCTION accounting.guard_treasury_gl_evidence()',table_name);
  EXECUTE format('REVOKE ALL ON accounting.%I FROM PUBLIC',table_name);
  FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
   IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN EXECUTE format('REVOKE ALL ON accounting.%I FROM %I',table_name,r); END IF;
  END LOOP;
 END LOOP;
END $$;

-- A request submitted after a cash event does not change that earlier event.
-- Retain all contemporaneous request rows; only truly later rows are omitted.
DO $$ BEGIN
 IF to_regprocedure('accounting.native_application_before_renewal_origin(uuid)') IS NULL THEN
  ALTER FUNCTION accounting.treasury_native_regular_application_origin(UUID) RENAME TO native_application_before_renewal_origin;
 END IF;
END $$;
CREATE OR REPLACE FUNCTION accounting.treasury_native_regular_application_origin(p_application UUID)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE result JSONB; prior_requests JSONB;
BEGIN
 result:=accounting.native_application_before_renewal_origin(p_application);
 SELECT coalesce(jsonb_agg(x ORDER BY x->>'id'),'[]'::jsonb) INTO prior_requests
 FROM jsonb_array_elements(result->'renewals') x
 WHERE (x->>'submitted_at')::timestamptz<=(result#>>'{transaction,accepted_at}')::timestamptz;
 RETURN jsonb_set(result,'{renewals}',prior_requests);
END $$;

-- Reconstruct an earlier cutoff from its dated source after a later operational
-- renewal. Neither current status nor a later request is an earlier cash flow.
DO $$ DECLARE definition TEXT; old_clause TEXT; signature TEXT; BEGIN
 FOREACH signature IN ARRAY ARRAY['accounting.loan_period_native_elapsed_assessment_candidate(uuid,uuid)',
  'accounting.loan_period_native_cash_assessment_candidate(uuid,uuid)'] LOOP
  definition:=pg_get_functiondef(signature::regprocedure);
  old_clause:='IF loan.status<>''active'' OR EXISTS';
  IF position(old_clause IN definition)>0 THEN
   definition:=replace(definition,old_clause,
    'IF (loan.status<>''active'' AND NOT EXISTS(SELECT 1 FROM lending.loan_renewal_execution_events later WHERE later.old_loan_id=p_loan AND NOT later.is_voided AND later.business_date>period_row.end_date)) OR EXISTS');
  END IF;
  old_clause:='OR EXISTS(SELECT 1 FROM lending.client_renewal_requests r WHERE r.loan_id=p_loan)';
  IF position(old_clause IN definition)>0 THEN
   definition:=replace(definition,old_clause,
    'OR EXISTS(SELECT 1 FROM lending.client_renewal_requests r WHERE r.loan_id=p_loan AND (r.submitted_at AT TIME ZONE ''Asia/Manila'')::date<=period_row.end_date)');
  END IF;
  EXECUTE definition;
 END LOOP;
END $$;

-- Reconstruct the impairment interval at the renewal date using the same exact
-- fiscal opening and dated cash reviews as the native assessment. A completed
-- renewal pins review identities; future append-only reviews are not its source.
CREATE OR REPLACE FUNCTION accounting.native_renewal_impairment(p_loan UUID,p_cutoff DATE,p_boundary JSONB)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
DECLARE retained JSONB; risk JSONB; impairment_risk JSONB; source JSONB; opening JSONB; interest JSONB; impaired BOOLEAN; net_established BOOLEAN;
 before_allowance NUMERIC:=(p_boundary->>'old_allowance')::numeric; unwind NUMERIC:=0; adjustment NUMERIC:=0; after_allowance NUMERIC;
BEGIN
 SELECT r.source_snapshot->'boundary' INTO retained FROM accounting.native_regular_asset_lineage n
 JOIN accounting.native_renewal_measurement_reviews r ON r.id=n.review_id WHERE n.previous_operational_loan_id=p_loan;
 IF FOUND THEN
  risk:=retained->'predecessor_risk_review';
  IF risk IS NOT NULL AND risk<>'null'::jsonb AND risk IS DISTINCT FROM
   (SELECT to_jsonb(r) FROM accounting.ecl_credit_risk_label_reviews r WHERE r.id=(risk->>'id')::bigint) THEN
   RAISE EXCEPTION 'Retained predecessor risk review changed.' USING ERRCODE='55000'; END IF;
 ELSE
  SELECT to_jsonb(r) INTO risk FROM accounting.ecl_credit_risk_label_reviews r
   WHERE r.loan_id=p_loan AND (r.created_at AT TIME ZONE 'Asia/Manila')::date<=p_cutoff ORDER BY r.review_version DESC LIMIT 1;
   IF risk IS NULL AND to_regprocedure('accounting.native_renewal_inherited_credit_review(uuid)') IS NOT NULL THEN
    risk:=accounting.native_renewal_inherited_credit_review(p_loan)->'risk_review';
   END IF;
 END IF;
 source:=jsonb_build_object('loan',jsonb_build_object('id',p_loan),'cutoff_date',p_cutoff,
  'anchor',p_boundary#>'{rollforward,anchor}','cash_rollforward',p_boundary->'rollforward',
  'prior_prefixes',(SELECT coalesce(jsonb_agg(jsonb_build_object('preparation',p)),'[]'::jsonb) FROM jsonb_array_elements(p_boundary->'prefixes') p),
  'eir',jsonb_build_object('daily_eir',p_boundary->'original_daily_eir','cumulative_interest',p_boundary#>'{rollforward,cumulative_interest}'),
  'renewal_boundary',true);
 -- Helpers are installed by0168/0169 before this workflow is used. Normal
 -- renewals remain usable on the0166-only schema.
 IF to_regprocedure('accounting.native_credit_impaired_opening(jsonb)') IS NOT NULL THEN
  opening:=accounting.native_credit_impaired_opening(source);
 ELSE
  SELECT p INTO opening FROM jsonb_array_elements(p_boundary->'prefixes') p ORDER BY (p->>'as_of_date')::date DESC LIMIT 1;
 END IF;
 impaired:=coalesce(risk->>'stage_label'='stage_3_credit_impaired',false)
  OR coalesce(opening#>>'{measurement_snapshot,risk_review,stage_label}'='stage_3_credit_impaired',false);
 IF NOT impaired THEN RETURN jsonb_build_object('predecessor_credit_impaired',false,'predecessor_risk_review',risk); END IF;
 IF risk IS NULL OR risk='null'::jsonb THEN
  SELECT to_jsonb(r) INTO risk FROM accounting.ecl_credit_risk_label_reviews r
   WHERE r.id=(opening#>>'{measurement_snapshot,risk_review,id}')::bigint;
 END IF;
 -- Fiscal measurements add annotations; lineage retains only the original
 -- immutable review row identified by that already verified measurement.
 SELECT to_jsonb(r) INTO impairment_risk FROM accounting.ecl_credit_risk_label_reviews r
  WHERE r.id=CASE WHEN risk->>'stage_label'='stage_3_credit_impaired' THEN (risk->>'id')::bigint
   ELSE (opening#>>'{measurement_snapshot,risk_review,id}')::bigint END
  AND r.stage_label='stage_3_credit_impaired';
 IF impairment_risk IS NULL THEN
  RAISE EXCEPTION 'Exact retained predecessor impairment review is required.' USING ERRCODE='55000'; END IF;
 net_established:=coalesce(opening#>>'{measurement_snapshot,risk_review,stage_label}'='stage_3_credit_impaired',false)
  AND opening#>>'{renewal_impairment_opening,net_interest_established}' IS DISTINCT FROM 'false';
 IF net_established THEN
  IF retained IS NOT NULL THEN source:=source||jsonb_build_object('retained_impaired_cash_reviews',
   coalesce(retained#>'{impairment_interest,cash_measurements}','[]'::jsonb)); END IF;
  interest:=accounting.native_credit_impaired_interest(source);
  unwind:=(interest->>'allowance_unwind')::numeric;
  adjustment:=coalesce((interest#>>'{cash_chain_measurement,virtual_impairment_adjustment}')::numeric,0);
 ELSE
  -- IFRS9 5.4.1(b): the initial impaired review day does not invent an earlier
  -- net-interest period. The actual review still follows the continuing asset.
  interest:=jsonb_build_object('basis','gross_before_initial_impaired_cutoff','allowance_unwind','0.00',
   'impairment_boundary_date',p_cutoff,'cash_measurements','[]'::jsonb);
 END IF;
 after_allowance:=before_allowance+unwind+adjustment;
 IF after_allowance<0 OR after_allowance>(p_boundary->>'old_gross_carrying')::numeric THEN
  RAISE EXCEPTION 'Renewal impaired allowance must remain within exact gross exposure.' USING ERRCODE='23514'; END IF;
 RETURN jsonb_build_object('predecessor_credit_impaired',true,'predecessor_risk_review',risk,
  'predecessor_impairment_review',impairment_risk,
  'net_interest_established',net_established,
  'derecognition_blocker','successor_credit_adjusted_eir_policy_required','impairment_interest',interest,
  'old_allowance',after_allowance::numeric(18,2)::text,'credit_impaired_boundary',jsonb_build_object(
   'allowance_before',before_allowance::numeric(18,2)::text,'allowance_unwind',unwind::numeric(18,2)::text,
   'impairment_adjustment',adjustment::numeric(18,2)::text,'allowance_after',after_allowance::numeric(18,2)::text));
END $$;

CREATE OR REPLACE FUNCTION accounting.native_renewal_boundary(p_loan UUID,p_cutoff DATE)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
DECLARE roll JSONB; prefix RECORD; recognized NUMERIC; cash_interest NUMERIC; incremental NUMERIC;
 allowance NUMERIC:=0; loan_amount NUMERIC; accrued NUMERIC; b1100 NUMERIC; b1120 NUMERIC; b1190 NUMERIC; b1110 NUMERIC;
 entries UUID[]; prefixes JSONB:='[]'::jsonb; ledger JSONB; result JSONB; own_completion UUID;
BEGIN
 roll:=accounting.regular_original_cash_rollforward(p_loan,p_cutoff,NULL);
 IF roll->>'ready' IS DISTINCT FROM 'true' THEN
  RAISE EXCEPTION 'Exact chronological old asset is required for renewal: %',roll->'blockers' USING ERRCODE='55000';
 END IF;
 cash_interest:=(roll->>'cash_cumulative_interest')::numeric; recognized:=cash_interest;
 entries:=ARRAY[(roll#>>'{anchor,journal_entry_id}')::uuid,(roll#>>'{native_origin,snapshot,debit_proof,journal_entry_id}')::uuid]
  ||ARRAY(SELECT value::uuid FROM jsonb_array_elements_text(roll->'journal_ids'));
 FOR prefix IN SELECT p.*,a.id AS posting_id,a.eir_journal_entry_id,a.allowance_journal_entry_id
  FROM accounting.loan_elapsed_assessment_preparations p JOIN accounting.loan_elapsed_assessment_postings a ON a.preparation_id=p.id
  WHERE p.loan_id=p_loan AND p.as_of_date<=p_cutoff
   -- A later zero-exposure assessment of this exact completed renewal creates
   -- no journal and is not a pre-renewal carrying claim. Its full current
   -- assessment proof remains mandatory for close, outside this origin graph.
   AND NOT (p.source_snapshot->>'settled_by_exact_renewal' IS NOT DISTINCT FROM 'true'
    AND a.eir_journal_entry_id IS NULL AND a.allowance_journal_entry_id IS NULL
    AND (p.measurement_snapshot->>'ecl_amount')::numeric=0
    AND (p.measurement_snapshot->>'allowance_delta')::numeric=0
    AND EXISTS(SELECT 1 FROM accounting.native_regular_asset_lineage n WHERE n.previous_operational_loan_id=p_loan
     AND n.effective_date<=p.as_of_date AND p.source_snapshot->'renewal_lineage'=to_jsonb(n)))
  ORDER BY p.as_of_date,p.id LOOP
  IF NOT accounting.period_elapsed_loan_assessment_exact(prefix.fiscal_period_id,p_loan) THEN
   RAISE EXCEPTION 'Renewal old-asset fiscal prefix is not exact.' USING ERRCODE='55000';
  END IF;
  recognized:=greatest(recognized,(prefix.source_snapshot#>>'{eir,cumulative_interest}')::numeric);
  allowance:=(prefix.measurement_snapshot->>'ecl_amount')::numeric;
  entries:=entries||ARRAY[prefix.eir_journal_entry_id,prefix.allowance_journal_entry_id];
  prefixes:=prefixes||jsonb_build_array(to_jsonb(prefix));
 END LOOP;
 loan_amount:=(roll->>'cash_loan_component')::numeric;
 accrued:=(roll->>'cash_accrued_interest')::numeric+recognized-cash_interest;
 incremental:=(roll->>'cumulative_interest')::numeric-recognized;
 SELECT journal_entry_id INTO own_completion FROM accounting.native_regular_asset_lineage WHERE previous_operational_loan_id=p_loan;
 SELECT coalesce(sum(l.debit-l.credit) FILTER(WHERE a.code='1100'),0),
  coalesce(sum(l.debit-l.credit) FILTER(WHERE a.code='1120'),0),
  coalesce(sum(l.credit-l.debit) FILTER(WHERE a.code='1190'),0),
  coalesce(sum(l.debit-l.credit) FILTER(WHERE a.code='1110'),0)
 INTO b1100,b1120,b1190,b1110 FROM accounting.journal_entries j JOIN accounting.journal_lines l ON l.journal_entry_id=j.id
 JOIN accounting.accounts a ON a.id=l.account_id WHERE j.status='posted' AND j.posting_date<=p_cutoff AND l.loan_id=p_loan
  AND j.id IS DISTINCT FROM own_completion;
 IF incremental<0 OR (b1100,b1120,b1190,b1110) IS DISTINCT FROM(loan_amount,accrued,allowance,0::numeric)
  OR EXISTS(SELECT 1 FROM accounting.journal_entries j JOIN accounting.journal_lines l ON l.journal_entry_id=j.id
   WHERE j.status='posted' AND j.posting_date<=p_cutoff AND l.loan_id=p_loan AND j.id IS DISTINCT FROM own_completion
    AND NOT j.id=ANY(array_remove(entries,NULL)) AND NOT accounting.native_loan_ancillary_tax_exact(j.id,p_loan)) THEN
  RAISE EXCEPTION 'Renewal old carrying must reconcile to exact known component journals.' USING ERRCODE='55000';
 END IF;
 SELECT coalesce(jsonb_agg(jsonb_build_object('journal',to_jsonb(j),'line',to_jsonb(l),
  'account',accounting.treasury_gl_account_snapshot(l.account_id)-ARRAY['name','is_active']) ORDER BY j.posting_date,j.id,l.line_number),'[]'::jsonb)
 INTO ledger FROM accounting.journal_entries j JOIN accounting.journal_lines l ON l.journal_entry_id=j.id
 WHERE j.id=ANY(array_remove(entries,NULL));
 result:=jsonb_build_object('rollforward',roll,'prefixes',prefixes,'ledger',ledger,
  'old_loan_component',loan_amount::numeric(18,2)::text,'old_accrued_interest',(accrued+incremental)::numeric(18,2)::text,
  'old_allowance',allowance::numeric(18,2)::text,'incremental_interest',incremental::numeric(18,2)::text,
  'old_gross_carrying',(loan_amount+accrued+incremental)::numeric(18,2)::text,
  'original_daily_eir',roll#>'{anchor,daily_eir}','accounting_asset_id',coalesce(
   (SELECT accounting_asset_id::text FROM accounting.native_regular_asset_lineage WHERE operational_loan_id=p_loan),p_loan::text));
 RETURN result||accounting.native_renewal_impairment(p_loan,p_cutoff,result);
END $$;

CREATE OR REPLACE FUNCTION accounting.native_renewal_source(p_payout UUID)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
DECLARE payout treasury.loan_payouts%ROWTYPE; execution lending.loan_renewal_execution_events%ROWTYPE;
 release lending.loan_disbursement_events%ROWTYPE; schedule lending.loan_contract_schedules%ROWTYPE;
 registration lending.loan_contract_schedule_registrations%ROWTYPE; debit accounting.loan_payout_accounting_posting_status%ROWTYPE;
 boundary JSONB; installments JSONB; evidence JSONB; source JSONB; new_loan JSONB;
 pv NUMERIC; total NUMERIC; n INTEGER; book UUID; cutoff DATE;
BEGIN
 SELECT * INTO payout FROM treasury.loan_payouts WHERE id=p_payout;
 SELECT * INTO execution FROM lending.loan_renewal_execution_events WHERE id::text=payout.source_snapshot#>>'{source,execution_id}';
 SELECT * INTO release FROM lending.loan_disbursement_events WHERE id=execution.disbursement_event_id;
 SELECT * INTO debit FROM accounting.loan_payout_accounting_posting_status WHERE payout_id=p_payout AND stage='debit';
 SELECT id INTO book FROM accounting.book_identity WHERE singleton;
 cutoff:=execution.business_date;
 IF payout.id IS NULL OR payout.source_kind<>'renewal' OR payout.status<>'completed' OR execution.id IS NULL OR execution.is_voided
  OR release.id IS NULL OR release.is_voided OR release.event_kind<>'renewal_release'
  OR payout.loan_id<>execution.new_loan_id OR payout.client_id<>execution.client_id
  OR payout.renewal_request_id IS DISTINCT FROM execution.renewal_request_id OR payout.source_id<>execution.renewal_request_id
  OR payout.amount<>release.cash_disbursed_amount OR payout.amount<=0 OR release.other_deduction_amount<>0
  OR release.settlement_amount<>execution.old_loan_settlement_amount OR release.loan_id<>execution.new_loan_id
  OR release.business_date<>cutoff OR cutoff>(statement_timestamp() AT TIME ZONE 'Asia/Manila')::date
  OR payout.payload->>'borrower_handover_status' IS DISTINCT FROM 'confirmed'
  OR payout.payload#>>'{acknowledgments,borrower,received}' IS DISTINCT FROM 'true'
  OR payout.payload#>>'{acknowledgments,borrower,actor_user_id}' IS DISTINCT FROM payout.source_snapshot#>>'{source,borrower_user_id}'
  OR (payout.payload#>>'{acknowledgments,borrower,reviewed_amount}')::numeric IS DISTINCT FROM payout.amount
  OR debit.exact_posted IS DISTINCT FROM true OR debit.correction_pending IS DISTINCT FROM false
  OR debit.book_id IS DISTINCT FROM book OR debit.amount IS DISTINCT FROM payout.amount OR debit.posting_date>cutoff THEN
  RAISE EXCEPTION 'Completed exact native renewal, independent borrower receipt and protected debit are required.' USING ERRCODE='55000';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM lending.client_renewal_requests r JOIN lending.loans l ON l.id=r.loan_id
   JOIN lending.loan_collection_state c ON c.loan_id=l.id WHERE r.id=payout.renewal_request_id
    AND r.loan_id=execution.old_loan_id AND r.new_loan_id=execution.new_loan_id AND r.status='approved'
    AND r.client_decision='accepted' AND r.activation_status='active' AND r.handover_proof_status='approved'
    AND l.status='paid' AND c.remaining_balance=0)
  OR EXISTS(SELECT 1 FROM accounting.loan_disbursement_journal_postings WHERE loan_id=execution.new_loan_id)
  OR EXISTS(SELECT 1 FROM accounting.journal_entries WHERE source_event_key IN('loan_disbursement:'||release.id::text,'loan_renewal_execution:'||execution.id::text)) THEN
  RAISE EXCEPTION 'Renewal completion requires controlled operational settlement and no competing legacy completion.' USING ERRCODE='55000';
 END IF;
 SELECT s.* INTO schedule FROM lending.loan_contract_schedules s JOIN lending.loan_contract_schedule_registrations r ON r.schedule_id=s.id
 WHERE s.loan_id=execution.new_loan_id AND s.effective_from=cutoff AND r.evidence_basis='signed_renewal_contract';
 SELECT * INTO registration FROM lending.loan_contract_schedule_registrations WHERE schedule_id=schedule.id;
 IF schedule.id IS NULL OR schedule.contract_signed_date>cutoff OR
  (SELECT count(*) FROM lending.loan_contract_schedules WHERE loan_id=execution.new_loan_id)<>1 THEN
  RAISE EXCEPTION 'One exact signed renewal contract schedule is required.' USING ERRCODE='55000';
 END IF;
 boundary:=accounting.native_renewal_boundary(execution.old_loan_id,cutoff);
 SELECT jsonb_agg(to_jsonb(i) ORDER BY i.installment_number),sum(i.contractual_amount),count(*)::integer,
  round(sum(i.contractual_amount/power(1::numeric+(boundary->>'original_daily_eir')::numeric,(i.due_date-cutoff)::numeric)),2)
 INTO installments,total,n,pv FROM lending.loan_contract_installments i WHERE i.schedule_id=schedule.id;
 IF n=0 OR pv<=0 OR EXISTS(SELECT 1 FROM lending.loan_contract_installments WHERE schedule_id=schedule.id AND due_date<=cutoff) THEN
  RAISE EXCEPTION 'Renewal measurement requires positive signed future contractual flows.' USING ERRCODE='55000';
 END IF;
 SELECT jsonb_build_object('id',l.id,'client_id',l.client_id,'loan_type_id',l.loan_type_id,
  'calculation_mode',t.calculation_mode,'principal',l.principal::text,'date_released',l.date_released,'due_date',l.due_date)
 INTO new_loan FROM lending.loans l JOIN lending.loan_types t ON t.id=l.loan_type_id WHERE l.id=execution.new_loan_id;
 IF new_loan IS NULL OR new_loan->>'client_id' IS DISTINCT FROM execution.client_id::text
  OR new_loan->>'calculation_mode' IS DISTINCT FROM 'fixed_daily'
  OR (new_loan->>'principal')::numeric IS DISTINCT FROM release.cash_disbursed_amount+release.settlement_amount
  OR (new_loan->>'date_released')::date IS DISTINCT FROM cutoff
  OR (new_loan->>'due_date')::date IS DISTINCT FROM (SELECT max(i.due_date) FROM lending.loan_contract_installments i WHERE i.schedule_id=schedule.id) THEN
  RAISE EXCEPTION 'Renewed regular loan terms must match the protected funding and exact signed schedule.' USING ERRCODE='55000';
 END IF;
 SELECT to_jsonb(e) INTO evidence FROM treasury.evidence e WHERE e.id::text=payout.payload#>>'{proof_review,evidence_id}'
  AND e.account_id=payout.account_id AND e.purpose='recipient';
 IF evidence IS NULL THEN RAISE EXCEPTION 'Private protected renewal receipt proof is required.' USING ERRCODE='55000'; END IF;
 source:=jsonb_build_object('policy_version','native_regular_renewal_source_v1','book_id',book,'payout',to_jsonb(payout),
  'execution',to_jsonb(execution),'disbursement',to_jsonb(release),'debit_proof',to_jsonb(debit),
  'boundary',boundary,'new_loan',new_loan,'schedule',to_jsonb(schedule)-'status','registration',to_jsonb(registration),'installments',installments,
  'contractual_total',total::numeric(18,2)::text,'installment_count',n,'revised_pv',pv::numeric(18,2)::text,
  'borrower_evidence',evidence,'payout_debit_origin',accounting.loan_payout_accounting_origin(p_payout,'debit'));
 RETURN source||jsonb_build_object('source_digest',encode(sha256(convert_to(source::text,'UTF8')),'hex'));
END $$;

-- Preserve the original-only solver and reuse its verified cash-flow arithmetic
-- for the separately attested signed renewal contract registration.
DO $$ DECLARE definition TEXT; old_clause TEXT; BEGIN
 definition:=pg_get_functiondef('accounting.solve_verified_contract_schedule_daily_eir(uuid,date,numeric)'::regprocedure);
 old_clause:='registration.evidence_basis = ''signed_contract''';
 IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Verified contract EIR solver registration gate changed.'; END IF;
 definition:=replace(definition,'accounting.solve_verified_contract_schedule_daily_eir(',
  'accounting.native_renewal_schedule_daily_eir(');
 definition:=replace(definition,old_clause,'registration.evidence_basis = ''signed_renewal_contract''');
 EXECUTE definition;
END $$;
ALTER FUNCTION accounting.native_renewal_schedule_daily_eir(UUID,DATE,NUMERIC) SET search_path=pg_catalog;

CREATE OR REPLACE FUNCTION accounting.record_native_renewal_measurement(
 p_payout UUID,p_digest TEXT,p_request UUID,p_actor UUID,p_evidence UUID,p_review JSONB)
RETURNS UUID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE source JSONB; retained JSONB; prior accounting.native_renewal_measurement_reviews%ROWTYPE;
 evidence treasury.evidence%ROWTYPE; cutoff DATE; settlement NUMERIC; fair NUMERIC; decision UUID;
 digest TEXT; created UUID; old_write TEXT; change NUMERIC; original NUMERIC; rate NUMERIC; revised NUMERIC;
BEGIN
 PERFORM accounting.require_native_renewal_actor(p_actor,p_payout);
 IF NOT EXISTS(SELECT 1 FROM core.users u JOIN core.user_roles ur ON ur.user_id=u.id JOIN core.roles r ON r.id=ur.role_id
  JOIN core.role_permissions rp ON rp.role_id=r.id WHERE u.id=p_actor AND u.status='active' AND r.code='management'
   AND rp.permission_code='accounting.renewal_treatment_decision.manage') THEN
  RAISE EXCEPTION 'Current Management renewal treatment authority is required.' USING ERRCODE='42501';
 END IF;
 IF p_request IS NULL OR p_review IS NULL OR jsonb_typeof(p_review)<>'object' OR
  coalesce(p_review->>'decision','') NOT IN('modification_no_derecognition','derecognition')
  OR length(btrim(coalesce(p_review->>'decision_rationale','')))<20
  OR btrim(coalesce(p_review->>'accounting_policy_reference',''))=''
  OR jsonb_typeof(p_review->'qualitative_assessment') IS DISTINCT FROM 'object'
  OR p_review#>'{qualitative_assessment,cash_flow_terms_reviewed}' IS DISTINCT FROM 'true'::jsonb
  OR p_review#>'{qualitative_assessment,substantial_change_assessed}' IS DISTINCT FROM 'true'::jsonb
  OR p_review#>'{qualitative_assessment,signed_contract_reviewed}' IS DISTINCT FROM 'true'::jsonb
  OR length(btrim(coalesce(p_review#>>'{qualitative_assessment,decision_basis}','')))<20
  OR length(btrim(coalesce(p_review->>'settlement_basis','')))<20 THEN
  RAISE EXCEPTION 'Explicit treatment, qualitative policy assessment and substantive settlement evidence are required.' USING ERRCODE='23514';
 END IF;
 SELECT * INTO prior FROM accounting.native_renewal_measurement_reviews WHERE request_id=p_request;
 IF FOUND THEN
  IF prior.payout_id=p_payout AND prior.actor_user_id=p_actor AND prior.source_digest=p_digest AND prior.evidence_id=p_evidence
   AND prior.reviewed_measurement->'review'=p_review THEN RETURN prior.id; END IF;
  RAISE EXCEPTION 'Renewal measurement retry differs from the immutable reviewed request.' USING ERRCODE='55000';
 END IF;
 PERFORM accounting.lock_elapsed_assessment_sources();
 LOCK TABLE accounting.native_renewal_measurement_reviews,accounting.native_regular_asset_lineage,
  accounting.renewal_treatment_decisions,accounting.renewal_treatment_decision_voids,treasury.evidence IN SHARE ROW EXCLUSIVE MODE;
 LOCK TABLE lending.loan_collection_state IN SHARE MODE;
 source:=accounting.native_renewal_source(p_payout);
 IF source->>'source_digest' IS DISTINCT FROM p_digest THEN RAISE EXCEPTION 'Renewal source changed; reload the current review.' USING ERRCODE='55000'; END IF;
 SELECT * INTO evidence FROM treasury.evidence WHERE id=p_evidence AND account_id=(source#>>'{payout,account_id}')::uuid;
 IF evidence.id IS NULL OR coalesce(evidence.sha256,'') !~ '^[0-9a-f]{64}$' OR evidence.byte_count<=0 THEN
  RAISE EXCEPTION 'Retained private measurement and settlement evidence is required.' USING ERRCODE='55000';
 END IF;
 cutoff:=(source#>>'{execution,business_date}')::date;
 settlement:=(p_review->>'settlement_consideration')::numeric;
 IF settlement IS NULL OR settlement<0 OR settlement<>round(settlement,2)
  OR (p_review->>'settlement_rebate')::numeric IS NULL OR (p_review->>'settlement_rebate')::numeric<0
  OR (p_review->>'settlement_rebate')::numeric<>round((p_review->>'settlement_rebate')::numeric,2)
  OR settlement+(p_review->>'settlement_rebate')::numeric<>(source#>>'{execution,old_loan_settlement_amount}')::numeric THEN
  RAISE EXCEPTION 'Explicit consideration and rebate must equal the signed operational settlement.' USING ERRCODE='23514';
 END IF;
 original:=(source#>>'{boundary,old_gross_carrying}')::numeric; rate:=(source#>>'{boundary,original_daily_eir}')::numeric;
 revised:=(source->>'revised_pv')::numeric; change:=revised-original;
 IF p_review->>'decision'='derecognition' THEN
  IF source#>>'{boundary,predecessor_credit_impaired}'='true' THEN
   RAISE EXCEPTION 'Impaired predecessor derecognition requires supported successor initial credit status and credit-adjusted EIR policy.' USING ERRCODE='23514'; END IF;
  fair:=(p_review->>'new_initial_fair_value')::numeric;
  IF fair IS NULL OR fair<=0 OR fair<>round(fair,2) OR (p_review->>'fair_value_effective_date')::date IS DISTINCT FROM cutoff
   OR length(btrim(coalesce(p_review->>'fair_value_basis','')))<20
   OR length(btrim(coalesce(p_review->>'day_one_difference_rationale','')))<20 THEN
   RAISE EXCEPTION 'Derecognition requires explicit effective-date fair value, measurement basis and day-one difference review.' USING ERRCODE='23514';
  END IF;
 ELSE
  IF p_review->>'new_initial_fair_value' IS NOT NULL THEN RAISE EXCEPTION 'Modification uses original-EIR present value, not a new fair value.' USING ERRCODE='23514'; END IF;
 END IF;
 retained:=jsonb_build_object('review',p_review,'evidence',to_jsonb(evidence),
  'measurement',accounting.native_renewal_measurement(source->'boundary'||jsonb_build_object(
   'decision',p_review->>'decision','fresh_cash',source#>'{payout,amount}','revised_pv',source->'revised_pv',
   'settlement_consideration',settlement,'new_initial_fair_value',fair)));
 rate:=CASE WHEN p_review->>'decision'='derecognition' THEN accounting.native_renewal_schedule_daily_eir(
  (source#>>'{schedule,id}')::uuid,cutoff,fair) ELSE rate END;
 IF rate IS NULL OR rate<=0 THEN RAISE EXCEPTION 'A positive independently solved renewal EIR is required.' USING ERRCODE='23514'; END IF;
 retained:=retained||jsonb_build_object('daily_eir',rate);
 digest:=encode(sha256(convert_to(jsonb_build_object('source_digest',p_digest,'measurement',retained)::text,'UTF8')),'hex');
 decision:=accounting.record_renewal_treatment_decision(
  (source#>>'{execution,id}')::uuid,(source#>>'{execution,old_loan_id}')::uuid,(source#>>'{execution,new_loan_id}')::uuid,
  (source#>>'{execution,client_id}')::uuid,cutoff,digest,'renewal_accounting_treatment_readiness_v1',p_review->>'decision',
  'renewal_treatment_decision_evidence_v1',p_review->>'accounting_policy_reference',p_review->'qualitative_assessment',
  p_review->>'decision_rationale','treasury-evidence:'||evidence.id::text,original,
  (source#>>'{boundary,original_daily_eir}')::numeric,(source#>>'{payout,amount}')::numeric,
  (source#>>'{execution,old_loan_settlement_amount}')::numeric,0,(source#>>'{schedule,id}')::uuid,
  (source#>>'{schedule,schedule_version}')::integer,source#>>'{schedule,contract_reference}',source#>>'{registration,evidence_reference}',
  (source->>'installment_count')::integer,(source->>'contractual_total')::numeric,revised,change,
  round(abs(change)/original*100,6),p_actor);
 old_write:=current_setting('accounting.treasury_gl_write',true);
 PERFORM set_config('accounting.treasury_gl_write','native_renewal_measurement_reviews',true);
 INSERT INTO accounting.native_renewal_measurement_reviews(request_id,payout_id,execution_id,decision_id,book_id,actor_user_id,
  evidence_id,source_digest,measurement_digest,source_snapshot,reviewed_measurement,review_note)
 VALUES(p_request,p_payout,(source#>>'{execution,id}')::uuid,decision,(source->>'book_id')::uuid,p_actor,
  evidence.id,p_digest,digest,source-'source_digest',retained,p_review->>'decision_rationale') RETURNING id INTO created;
 PERFORM set_config('accounting.treasury_gl_write',coalesce(old_write,''),true);
 RETURN created;
END $$;

CREATE OR REPLACE FUNCTION accounting.require_native_renewal_actor(p_actor UUID,p_payout UUID)
RETURNS VOID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 PERFORM accounting.require_loan_payout_accounting_actor(p_actor,p_payout);
 PERFORM 1 FROM core.users u JOIN core.user_roles ur ON ur.user_id=u.id JOIN core.roles r ON r.id=ur.role_id
  JOIN core.role_permissions rp ON rp.role_id=r.id WHERE u.id=p_actor AND u.status='active' AND r.code='management'
   AND rp.permission_code='accounting.renewal_treatment_decision.manage' FOR SHARE OF u,ur,r,rp;
 IF NOT FOUND THEN RAISE EXCEPTION 'Current Management renewal treatment authority is required.' USING ERRCODE='42501'; END IF;
END $$;

-- This exact structural claim deliberately does not rebuild the current origin:
-- earlier applications use it to omit a later renewal without a dependency cycle.
CREATE OR REPLACE FUNCTION accounting.native_renewal_structural_exact(p_journal UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT EXISTS(SELECT 1 FROM accounting.native_regular_asset_lineage n
  JOIN accounting.native_renewal_measurement_reviews r ON r.id=n.review_id
  JOIN accounting.loan_payout_accounting_preparations p ON p.id=n.preparation_id
  JOIN accounting.loan_payout_accounting_postings a ON a.preparation_id=p.id
  JOIN accounting.journal_entries j ON j.id=n.journal_entry_id
  WHERE j.id=p_journal AND a.journal_entry_id=j.id AND a.payout_id=n.payout_id AND a.stage='completion'
   AND a.book_id=r.book_id AND a.loan_id=n.operational_loan_id AND a.source_digest=p.source_digest
   AND a.actor_user_id=p.actor_user_id AND n.actor_user_id=p.actor_user_id
   AND p.snapshot->>'accounting_policy_version'='native_regular_renewal_completion_v1'
   AND p.snapshot->>'renewal_review_id'=r.id::text AND p.snapshot->>'old_loan_id'=n.previous_operational_loan_id::text
   AND p.snapshot->>'accounting_asset_id'=n.accounting_asset_id::text
   AND j.status='posted' AND j.source_type='treasury_loan_payout'
   AND j.source_reference=n.payout_id::text AND j.source_event_key=p.snapshot->>'source_event_key'
   AND j.posting_date=n.effective_date AND j.posting_date=(p.snapshot->>'posting_date')::date
   AND j.fiscal_period_id=(p.snapshot->>'fiscal_period_id')::uuid AND j.reversal_of_entry_id IS NULL
   AND j.created_by_user_id=p.actor_user_id AND j.posted_by_user_id=p.actor_user_id
   AND n.anchor=p.snapshot->'renewal_anchor'
   AND (SELECT count(*) FROM accounting.journal_lines WHERE journal_entry_id=j.id)=jsonb_array_length(p.snapshot->'lines')
   AND NOT EXISTS(SELECT 1 FROM jsonb_to_recordset(p.snapshot->'lines') x(line_number INT,account_id UUID,debit NUMERIC,credit NUMERIC,client_id UUID,loan_id UUID)
    WHERE NOT EXISTS(SELECT 1 FROM accounting.journal_lines l WHERE l.journal_entry_id=j.id AND l.line_number=x.line_number
     AND (l.account_id,l.debit,l.credit,l.client_id,l.loan_id) IS NOT DISTINCT FROM(x.account_id,x.debit,x.credit,x.client_id,x.loan_id)))
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p.snapshot->'lines') line WHERE
    (line->'account_snapshot')-ARRAY['name','is_active'] IS DISTINCT FROM accounting.treasury_gl_account_snapshot((line->>'account_id')::uuid)-ARRAY['name','is_active'])
   AND NOT EXISTS(SELECT 1 FROM accounting.renewal_treatment_decision_voids v WHERE v.decision_id=r.decision_id));
$$;

-- A continuing asset's prior reviewed credit risk belongs to that asset even
-- when operations changed its loan id. Expose the real predecessor identity
-- separately; never manufacture a successor review or a cure.
CREATE OR REPLACE FUNCTION accounting.native_renewal_inherited_credit_review(p_loan UUID)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
DECLARE n accounting.native_regular_asset_lineage%ROWTYPE; risk JSONB;
BEGIN
 SELECT * INTO n FROM accounting.native_regular_asset_lineage WHERE operational_loan_id=p_loan;
 IF NOT FOUND THEN RETURN NULL; END IF;
 risk:=coalesce(n.anchor#>'{credit_risk_opening,credit_risk_review}',
  n.anchor#>'{impairment_opening,impairment_risk_review}',n.anchor#>'{impairment_opening,credit_risk_review}');
 IF risk IS NULL OR risk='null'::jsonb THEN RETURN NULL; END IF;
 IF NOT accounting.native_renewal_structural_exact(n.journal_entry_id)
  OR NOT EXISTS(SELECT 1 FROM accounting.loan_payout_accounting_posting_status s
   WHERE s.journal_entry_id=n.journal_entry_id AND s.exact_posted AND NOT s.correction_pending)
  OR NOT EXISTS(SELECT 1 FROM accounting.native_renewal_measurement_reviews r WHERE r.id=n.review_id
   AND r.reviewed_measurement#>>'{measurement,decision}'='modification_no_derecognition')
   OR coalesce(risk->>'stage_label','') NOT IN('stage_1_12_month','stage_2_lifetime','stage_3_credit_impaired')
  OR risk IS DISTINCT FROM (SELECT to_jsonb(r) FROM accounting.ecl_credit_risk_label_reviews r WHERE r.id=(risk->>'id')::bigint) THEN
   RAISE EXCEPTION 'Exact continuing asset credit risk lineage is required.' USING ERRCODE='55000'; END IF;
 RETURN jsonb_build_object('risk_review',risk,'lineage',to_jsonb(n));
END $$;

DO $$ DECLARE definition TEXT; needle TEXT; BEGIN
 definition:=pg_get_functiondef('accounting.review_ecl_credit_risk_labels(uuid,text,boolean,text,text,text,text,text,boolean,boolean,text,text,text,text,uuid,uuid)'::regprocedure);
 needle:='next_version := coalesce(prior_review.review_version, 0) + 1;';
 IF position('accounting.native_renewal_inherited_credit_review' IN definition)=0 THEN
  IF position(needle IN definition)=0 THEN RAISE EXCEPTION 'Protected risk review version boundary changed.'; END IF;
  definition:=replace(definition,needle,needle||$new$
    IF prior_review_id IS NULL THEN
        SELECT * INTO prior_review FROM jsonb_populate_record(NULL::accounting.ecl_credit_risk_label_reviews,
            accounting.native_renewal_inherited_credit_review(p_loan_id)->'risk_review');
        prior_review_id := prior_review.id;
    END IF;
$new$);
  EXECUTE definition;
 END IF;
END $$;

DO $$ DECLARE definition TEXT; old_clause TEXT; BEGIN
 definition:=pg_get_functiondef('accounting.regular_application_causal_origin(uuid,jsonb)'::regprocedure);
 old_clause:='RETURN jsonb_set(p_origin,''{loan_ledger}'',ledger);';
 IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Renewal causal predecessor changed.'; END IF;
 definition:=replace(definition,old_clause,$new$
 SELECT coalesce(jsonb_agg(item.value ORDER BY item.ordinality),'[]'::jsonb) INTO ledger
 FROM jsonb_array_elements(ledger) WITH ORDINALITY item(value,ordinality)
 WHERE NOT EXISTS(SELECT 1 FROM accounting.native_regular_asset_lineage n
  JOIN lending.loan_renewal_execution_events e ON e.id=n.execution_id
  WHERE n.previous_operational_loan_id=t.loan_id AND n.journal_entry_id=(item.value#>>'{journal,id}')::uuid
   AND (e.business_date>t.collection_date OR (e.business_date=t.collection_date AND e.executed_at>t.accepted_at))
   AND accounting.native_renewal_structural_exact(n.journal_entry_id));
 RETURN jsonb_set(p_origin,'{loan_ledger}',ledger);$new$);
 EXECUTE definition;
END $$;

DO $$ BEGIN
 IF to_regprocedure('accounting.loan_payout_before_renewal_origin(uuid,text)') IS NULL THEN
  ALTER FUNCTION accounting.loan_payout_accounting_origin(UUID,TEXT) RENAME TO loan_payout_before_renewal_origin;
 END IF;
 IF to_regprocedure('accounting.loan_payout_before_renewal_coordinates(uuid,text)') IS NULL THEN
  ALTER FUNCTION accounting.loan_payout_coordinates(UUID,TEXT) RENAME TO loan_payout_before_renewal_coordinates;
 END IF;
 IF to_regprocedure('accounting.post_loan_payout_before_renewal(uuid,text,text,uuid)') IS NULL THEN
  ALTER FUNCTION accounting.post_loan_payout_accounting(UUID,TEXT,TEXT,UUID) RENAME TO post_loan_payout_before_renewal;
 END IF;
 IF to_regprocedure('accounting.prepare_loan_payout_before_renewal(uuid,text,text,uuid,uuid)') IS NULL THEN
  ALTER FUNCTION accounting.prepare_loan_payout_accounting(UUID,TEXT,TEXT,UUID,UUID) RENAME TO prepare_loan_payout_before_renewal;
 END IF;
END $$;

CREATE OR REPLACE FUNCTION accounting.prepare_loan_payout_accounting(p_payout UUID,p_stage TEXT,p_digest TEXT,p_request UUID,p_actor UUID)
RETURNS UUID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF p_stage='completion' AND EXISTS(SELECT 1 FROM treasury.loan_payouts WHERE id=p_payout AND source_kind='renewal') THEN
  PERFORM accounting.require_native_renewal_actor(p_actor,p_payout);
 END IF;
 RETURN accounting.prepare_loan_payout_before_renewal(p_payout,p_stage,p_digest,p_request,p_actor);
END $$;

CREATE OR REPLACE FUNCTION accounting.loan_payout_accounting_origin(p_payout UUID,p_stage TEXT)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
DECLARE source JSONB; reviewed JSONB;
BEGIN
 IF p_stage<>'completion' OR NOT EXISTS(SELECT 1 FROM treasury.loan_payouts WHERE id=p_payout AND source_kind='renewal') THEN
  RETURN accounting.loan_payout_before_renewal_origin(p_payout,p_stage);
 END IF;
 BEGIN source:=accounting.native_renewal_source(p_payout);
 EXCEPTION WHEN SQLSTATE '55000' OR SQLSTATE '23514' THEN
  RETURN jsonb_build_object('policy_version','native_regular_renewal_completion_v1','source_no_longer_exact',true);
 END;
 SELECT to_jsonb(r) INTO reviewed FROM accounting.native_renewal_measurement_reviews r WHERE r.payout_id=p_payout
  AND NOT EXISTS(SELECT 1 FROM accounting.renewal_treatment_decision_voids v WHERE v.decision_id=r.decision_id)
  ORDER BY r.reviewed_at DESC,r.id DESC LIMIT 1;
 RETURN jsonb_build_object('policy_version','native_regular_renewal_completion_v1','source',source-'source_digest','review',reviewed);
END $$;

CREATE OR REPLACE FUNCTION accounting.loan_payout_coordinates(p_payout UUID,p_stage TEXT)
RETURNS JSONB LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
DECLARE source JSONB; review accounting.native_renewal_measurement_reviews%ROWTYPE; payout treasury.loan_payouts%ROWTYPE;
 fiscal accounting.fiscal_periods%ROWTYPE; measured JSONB; anchor JSONB; lines JSONB; result JSONB; mapping JSONB; mapping_id UUID;
 old_loan UUID; new_loan UUID; asset UUID; incremental NUMERIC; raw_lines JSONB; origin JSONB; item RECORD;
BEGIN
 IF p_stage<>'completion' OR NOT EXISTS(SELECT 1 FROM treasury.loan_payouts WHERE id=p_payout AND source_kind='renewal') THEN
  RETURN accounting.loan_payout_before_renewal_coordinates(p_payout,p_stage);
 END IF;
 IF current_setting('transaction_isolation')<>'read committed' THEN RAISE EXCEPTION 'Renewal accounting requires READ COMMITTED.' USING ERRCODE='55000'; END IF;
 SELECT * INTO payout FROM treasury.loan_payouts WHERE id=p_payout;
 PERFORM id FROM treasury.accounts WHERE id=payout.account_id FOR UPDATE;
 SELECT * INTO payout FROM treasury.loan_payouts WHERE id=p_payout FOR UPDATE;
 PERFORM accounting.require_book_treasury_account(payout.account_id);
 PERFORM accounting.lock_elapsed_assessment_sources();
 LOCK TABLE accounting.native_renewal_measurement_reviews,accounting.native_regular_asset_lineage,
  accounting.renewal_treatment_decisions,accounting.renewal_treatment_decision_voids,
  lending.loan_renewal_execution_events,lending.client_renewal_requests IN SHARE ROW EXCLUSIVE MODE;
 LOCK TABLE lending.loan_collection_state IN SHARE MODE;
 source:=accounting.native_renewal_source(p_payout);
 SELECT * INTO review FROM accounting.native_renewal_measurement_reviews r WHERE r.payout_id=p_payout
  AND NOT EXISTS(SELECT 1 FROM accounting.renewal_treatment_decision_voids v WHERE v.decision_id=r.decision_id)
  ORDER BY r.reviewed_at DESC,r.id DESC LIMIT 1;
 IF review.id IS NULL OR review.source_digest IS DISTINCT FROM source->>'source_digest'
  OR review.source_snapshot IS DISTINCT FROM source-'source_digest'
  OR review.measurement_digest IS DISTINCT FROM encode(sha256(convert_to(jsonb_build_object('source_digest',review.source_digest,'measurement',review.reviewed_measurement)::text,'UTF8')),'hex') THEN
  RAISE EXCEPTION 'An exact active retained renewal treatment and measurement review is required.' USING ERRCODE='55000';
 END IF;
 SELECT * INTO fiscal FROM accounting.fiscal_periods WHERE (source#>>'{execution,business_date}')::date BETWEEN start_date AND end_date FOR UPDATE;
 IF fiscal.id IS NULL OR fiscal.status<>'open' OR 1<>(SELECT count(*) FROM accounting.fiscal_periods WHERE (source#>>'{execution,business_date}')::date BETWEEN start_date AND end_date) THEN
  RAISE EXCEPTION 'Renewal requires its one actual-date open accounting period.' USING ERRCODE='55000';
 END IF;
 LOCK TABLE accounting.accounts,accounting.journal_entries,accounting.journal_lines IN SHARE ROW EXCLUSIVE MODE;
 old_loan:=(source#>>'{execution,old_loan_id}')::uuid; new_loan:=payout.loan_id;
 IF EXISTS(SELECT 1 FROM accounting.journal_entries j JOIN accounting.journal_lines l ON l.journal_entry_id=j.id
  WHERE j.status='posted' AND l.loan_id IN(old_loan,new_loan) AND j.posting_date>(source#>>'{execution,business_date}')::date) THEN
  RAISE EXCEPTION 'Later asset accounting requires an explicit backdated correction adapter.' USING ERRCODE='55000';
 END IF;
 measured:=review.reviewed_measurement->'measurement'; incremental:=(source#>>'{boundary,incremental_interest}')::numeric;
 asset:=CASE WHEN measured->>'decision'='modification_no_derecognition' THEN (source#>>'{boundary,accounting_asset_id}')::uuid ELSE new_loan END;
 raw_lines:=measured->'lines';
 IF incremental>0 THEN raw_lines:=raw_lines||jsonb_build_array(
  jsonb_build_object('line_number',1,'component','old_asset_elapsed_interest','account_code','1120','loan_role','old','debit',incremental::numeric(18,2)::text,'credit','0.00'),
  jsonb_build_object('line_number',2,'component','old_asset_elapsed_interest','account_code','4000','loan_role','old','debit','0.00','credit',incremental::numeric(18,2)::text)); END IF;
 FOR item IN SELECT * FROM (VALUES
  ('1100','loans_receivable_regular','asset','debit'),('1120','accrued_interest_receivable','asset','debit'),
  ('1190','allowance_expected_credit_loss','asset','credit'),('1050','loan_disbursement_transit','asset','debit'),
   ('4000','interest_income_regular','income','credit'),('4020','regular_renewal_gain','income','credit'),
   ('5000','credit_loss_expense','expense','debit'),('5010','regular_renewal_loss','expense','debit')) e(code,system_key,kind,side) LOOP
  IF NOT EXISTS(SELECT 1 FROM accounting.accounts a WHERE (a.code,a.system_key,a.account_type,a.normal_balance)=(item.code,item.system_key,item.kind,item.side) AND a.is_posting AND a.is_active) THEN
   RAISE EXCEPTION 'Exact active renewal chart roles are required.' USING ERRCODE='55000'; END IF;
 END LOOP;
 SELECT jsonb_agg(x||jsonb_build_object('line_number',ordinal,'account_id',a.id,'account_snapshot',accounting.treasury_gl_account_snapshot(a.id),
  'client_id',payout.client_id,'loan_id',CASE WHEN x->>'loan_role'='old' THEN old_loan ELSE new_loan END,
  'description','Protected reviewed renewal '||(x->>'component')) ORDER BY ordinal) INTO lines
 FROM jsonb_array_elements(raw_lines) WITH ORDINALITY raw(x,ordinal) JOIN accounting.accounts a ON a.code=x->>'account_code';
 SELECT id INTO mapping_id FROM accounting.treasury_cash_mappings WHERE treasury_account_id=payout.account_id ORDER BY version DESC LIMIT 1;
 mapping:=accounting.treasury_transfer_mapping_snapshot(mapping_id,payout.account_id);
 anchor:=jsonb_build_object('loan_id',new_loan,'client_id',payout.client_id,'disbursement_event_id',source#>'{disbursement,id}',
  'anchor_date',source#>'{execution,business_date}','initial_gross_carrying_amount',measured->'new_initial_carrying',
  'initial_loan_component',measured->'new_initial_carrying','initial_accrued_interest_component',0,
  'initial_allowance',measured->'new_initial_allowance','schedule_id',source#>'{schedule,id}',
  'schedule_version',source#>'{schedule,schedule_version}','contractual_due_date',(SELECT max((i->>'due_date')::date) FROM jsonb_array_elements(source->'installments') i),
  'daily_eir',review.reviewed_measurement->'daily_eir','accounting_asset_id',asset,
  'anchor_policy_version','native_regular_renewal_anchor_v1','anchor_source_key','native_regular_renewal_anchor:'||review.id::text);
  IF measured->>'decision'='modification_no_derecognition'
   AND source#>'{boundary,predecessor_risk_review}' IS NOT NULL
   AND source#>'{boundary,predecessor_risk_review}'<>'null'::jsonb THEN
   anchor:=anchor||jsonb_build_object('credit_risk_opening',jsonb_build_object('renewal_review_id',review.id,
    'credit_risk_review',source#>'{boundary,predecessor_risk_review}','anchor_date',source#>'{execution,business_date}'));
  END IF;
 IF source#>>'{boundary,predecessor_credit_impaired}'='true' THEN
   anchor:=anchor||jsonb_build_object('impairment_opening',jsonb_build_object('renewal_review_id',review.id,
   'credit_risk_review',source#>'{boundary,predecessor_risk_review}','anchor_date',source#>'{execution,business_date}',
   'impairment_risk_review',source#>'{boundary,predecessor_impairment_review}',
   'initial_allowance',measured->'new_initial_allowance','boundary',source#>'{boundary,credit_impaired_boundary}',
   'net_interest_established',source#>'{boundary,net_interest_established}',
   'predecessor_interest',source#>'{boundary,impairment_interest}'));
 END IF;
 origin:=accounting.loan_payout_accounting_origin(p_payout,p_stage);
 result:=jsonb_build_object('accounting_policy_version','native_regular_renewal_completion_v1','book_id',review.book_id,
  'payout_id',payout.id,'stage','completion','event_id',payout.event_id,'disbursement_event_id',source#>'{disbursement,id}',
  'treasury_account_id',payout.account_id,'ledger_context_id',payout.ledger_context_id,'loan_id',new_loan,'client_id',payout.client_id,
  'old_loan_id',old_loan,'accounting_asset_id',asset,'amount',payout.amount::text,'fee','0.00',
  'posting_date',source#>'{execution,business_date}','fiscal_period_id',fiscal.id,'mapping_id',mapping_id,'mapping',mapping,
  'transit_account_id',(SELECT id FROM accounting.accounts WHERE code='1050'),
  'debit_journal_entry_id',source#>'{debit_proof,journal_entry_id}','debit_source_digest',source#>'{debit_proof,source_digest}',
  'renewal_review_id',review.id,'renewal_decision',measured->'decision','measurement',measured,
   'predecessor_credit_impaired',source#>'{boundary,predecessor_credit_impaired}',
   'credit_impaired_boundary',source#>'{boundary,credit_impaired_boundary}',
  'renewal_anchor',anchor,'origin',origin,'lines',lines,
  'evidence',(SELECT to_jsonb(e) FROM treasury.evidence e JOIN treasury.events ev ON ev.evidence_id=e.id WHERE ev.id=payout.event_id),
  'borrower_evidence',source->'borrower_evidence','measurement_evidence',review.reviewed_measurement->'evidence',
  'source_event_key','treasury_loan_payout:'||payout.id::text||':completion');
 RETURN result||jsonb_build_object('source_digest',encode(sha256(convert_to(result::text,'UTF8')),'hex'));
END $$;

CREATE OR REPLACE FUNCTION accounting.native_renewal_prefix_admitted(p_journal UUID)
RETURNS BOOLEAN LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE p accounting.loan_payout_accounting_preparations%ROWTYPE; j accounting.journal_entries%ROWTYPE; current_source JSONB;
BEGIN
 SELECT * INTO p FROM accounting.loan_payout_accounting_preparations WHERE id::text=current_setting('accounting.loan_payout_accounting_post',true);
 SELECT * INTO j FROM accounting.journal_entries WHERE id=p_journal;
 IF p.id IS NULL OR p.stage<>'completion' OR p.snapshot->>'accounting_policy_version' IS DISTINCT FROM 'native_regular_renewal_completion_v1'
  OR j.status IS DISTINCT FROM 'draft' OR j.source_type IS DISTINCT FROM 'treasury_loan_payout'
  OR j.source_reference IS DISTINCT FROM p.payout_id::text OR j.source_event_key IS DISTINCT FROM p.snapshot->>'source_event_key'
  OR j.created_by_user_id IS DISTINCT FROM p.actor_user_id OR j.reversal_of_entry_id IS NOT NULL
  OR j.fiscal_period_id IS DISTINCT FROM (p.snapshot->>'fiscal_period_id')::uuid OR j.posting_date IS DISTINCT FROM (p.snapshot->>'posting_date')::date
  OR EXISTS(SELECT 1 FROM accounting.loan_payout_accounting_postings WHERE payout_id=p.payout_id AND stage='completion') THEN RETURN false; END IF;
 current_source:=accounting.loan_payout_coordinates(p.payout_id,p.stage);
 RETURN current_source->>'source_digest'=p.source_digest AND current_source-'source_digest'=p.snapshot
  AND (SELECT count(*) FROM accounting.journal_lines WHERE journal_entry_id=j.id)=jsonb_array_length(p.snapshot->'lines')
  AND NOT EXISTS(SELECT 1 FROM jsonb_to_recordset(p.snapshot->'lines') x(line_number INT,account_id UUID,debit NUMERIC,credit NUMERIC,client_id UUID,loan_id UUID)
   LEFT JOIN accounting.journal_lines l ON l.journal_entry_id=j.id AND l.line_number=x.line_number
   WHERE l.id IS NULL OR (l.account_id,l.debit,l.credit,l.client_id,l.loan_id) IS DISTINCT FROM(x.account_id,x.debit,x.credit,x.client_id,x.loan_id));
END $$;

-- Preserve the elapsed-source guard and add only a writer-scoped, freshly
-- recomputed renewal preparation with every actual line exactly matched.
DO $$ DECLARE definition TEXT; old_clause TEXT; BEGIN
 definition:=pg_get_functiondef('accounting.guard_elapsed_assessment_journal()'::regprocedure);
 old_clause:='AND NOT accounting.regular_application_prefix_admitted(NEW.id) THEN';
 IF position('accounting.native_renewal_prefix_admitted(NEW.id)' IN definition)=0 THEN
  IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Exact elapsed source guard predecessor is required for renewal.'; END IF;
  definition:=replace(definition,old_clause,'AND NOT accounting.regular_application_prefix_admitted(NEW.id) AND NOT accounting.native_renewal_prefix_admitted(NEW.id) THEN');
  EXECUTE definition;
 END IF;
END $$;

-- Views retain function OIDs through a rename. Rebind the existing exact proof
-- to the dispatch function so renewal source drift uses its reviewed lineage.
DO $$ DECLARE definition TEXT; BEGIN
 definition:=pg_get_viewdef('accounting.loan_payout_accounting_posting_proof'::regclass,true);
 definition:=replace(definition,'accounting.loan_payout_before_renewal_origin(',
  'accounting.loan_payout_accounting_origin(');
 EXECUTE 'CREATE OR REPLACE VIEW accounting.loan_payout_accounting_posting_proof AS '||definition;
END $$;

CREATE OR REPLACE FUNCTION accounting.post_loan_payout_accounting(p_preparation UUID,p_digest TEXT,p_token TEXT,p_actor UUID)
RETURNS UUID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE p accounting.loan_payout_accounting_preparations%ROWTYPE; result UUID; previous TEXT; previous_allowance TEXT;
 review accounting.native_renewal_measurement_reviews%ROWTYPE;
BEGIN
 SELECT * INTO p FROM accounting.loan_payout_accounting_preparations WHERE id=p_preparation;
 IF p.snapshot->>'accounting_policy_version' IS DISTINCT FROM 'native_regular_renewal_completion_v1' THEN
  RETURN accounting.post_loan_payout_before_renewal(p_preparation,p_digest,p_token,p_actor); END IF;
 PERFORM accounting.require_native_renewal_actor(p_actor,p.payout_id);
 SELECT * INTO review FROM accounting.native_renewal_measurement_reviews WHERE id=(p.snapshot->>'renewal_review_id')::uuid;
 previous_allowance:=current_setting('accounting.ecl_allowance_journal_line_write_allowed',true);
 -- The existing payout guard independently requires every line to match this
 -- exact retained renewal preparation. Restore the caller's allowance gate.
 PERFORM set_config('accounting.ecl_allowance_journal_line_write_allowed','on',true);
 result:=accounting.post_loan_payout_before_renewal(p_preparation,p_digest,p_token,p_actor);
 PERFORM set_config('accounting.ecl_allowance_journal_line_write_allowed',coalesce(previous_allowance,''),true);
 IF EXISTS(SELECT 1 FROM accounting.native_regular_asset_lineage WHERE preparation_id=p.id) THEN
  IF NOT accounting.native_renewal_structural_exact(result) THEN RAISE EXCEPTION 'Retained renewal lineage no longer matches its journal.' USING ERRCODE='55000'; END IF;
  RETURN result;
 END IF;
 previous:=current_setting('accounting.treasury_gl_write',true);
 PERFORM set_config('accounting.treasury_gl_write','native_regular_asset_lineage',true);
 INSERT INTO accounting.native_regular_asset_lineage(operational_loan_id,accounting_asset_id,previous_operational_loan_id,
  payout_id,execution_id,review_id,preparation_id,journal_entry_id,effective_date,anchor,actor_user_id)
 VALUES(p.loan_id,(p.snapshot->>'accounting_asset_id')::uuid,(p.snapshot->>'old_loan_id')::uuid,p.payout_id,review.execution_id,
  review.id,p.id,result,(p.snapshot->>'posting_date')::date,p.snapshot->'renewal_anchor',p_actor);
 PERFORM set_config('accounting.treasury_gl_write',coalesce(previous,''),true);
 IF NOT accounting.native_renewal_structural_exact(result) OR NOT EXISTS(SELECT 1 FROM accounting.loan_payout_accounting_posting_status
  WHERE journal_entry_id=result AND exact_posted AND NOT correction_pending) THEN
  RAISE EXCEPTION 'Renewal journal, asset lineage and retained source must reconcile together.' USING ERRCODE='55000';
 END IF;
 RETURN result;
END $$;

CREATE OR REPLACE FUNCTION accounting.assert_native_renewal_committed()
RETURNS TRIGGER LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE n accounting.native_regular_asset_lineage%ROWTYPE;
BEGIN
 SELECT * INTO n FROM accounting.native_regular_asset_lineage WHERE journal_entry_id=NEW.journal_entry_id;
 IF n.operational_loan_id IS NULL AND TG_TABLE_NAME='loan_payout_accounting_postings' THEN
  IF EXISTS(SELECT 1 FROM accounting.loan_payout_accounting_preparations WHERE id=NEW.preparation_id
   AND snapshot->>'accounting_policy_version'='native_regular_renewal_completion_v1') THEN
   RAISE EXCEPTION 'Renewal completion requires protected asset lineage in the same transaction.' USING ERRCODE='55000'; END IF;
  RETURN NEW;
 END IF;
 IF NOT accounting.native_renewal_structural_exact(n.journal_entry_id)
  OR NOT EXISTS(SELECT 1 FROM accounting.loan_payout_accounting_posting_status WHERE journal_entry_id=n.journal_entry_id AND exact_posted AND NOT correction_pending) THEN
  RAISE EXCEPTION 'Renewal completion sources changed before commit.' USING ERRCODE='55000'; END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS native_renewal_commit_audit ON accounting.native_regular_asset_lineage;
CREATE CONSTRAINT TRIGGER native_renewal_commit_audit AFTER INSERT ON accounting.native_regular_asset_lineage
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION accounting.assert_native_renewal_committed();
DROP TRIGGER IF EXISTS native_renewal_post_commit_audit ON accounting.loan_payout_accounting_postings;
CREATE CONSTRAINT TRIGGER native_renewal_post_commit_audit AFTER INSERT ON accounting.loan_payout_accounting_postings
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION accounting.assert_native_renewal_committed();

CREATE OR REPLACE FUNCTION accounting.native_regular_segment_origin(p_loan UUID,p_cutoff DATE)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
DECLARE n accounting.native_regular_asset_lineage%ROWTYPE; r accounting.native_renewal_measurement_reviews%ROWTYPE;
 a accounting.loan_payout_accounting_postings%ROWTYPE; status accounting.loan_payout_accounting_posting_status%ROWTYPE;
 anchor JSONB; snapshot JSONB; installments JSONB;
BEGIN
 SELECT * INTO n FROM accounting.native_regular_asset_lineage WHERE operational_loan_id=p_loan;
 IF NOT FOUND THEN RETURN accounting.regular_original_origin(p_loan,p_cutoff); END IF;
 IF p_cutoff IS NULL OR p_cutoff<n.effective_date OR NOT accounting.native_renewal_structural_exact(n.journal_entry_id) THEN
  RETURN jsonb_build_object('ready',false,'blockers',jsonb_build_array('exact_renewal_lineage_required')); END IF;
 SELECT * INTO status FROM accounting.loan_payout_accounting_posting_status WHERE journal_entry_id=n.journal_entry_id;
 SELECT * INTO r FROM accounting.native_renewal_measurement_reviews WHERE id=n.review_id;
 SELECT * INTO a FROM accounting.loan_payout_accounting_postings WHERE preparation_id=n.preparation_id;
 SELECT jsonb_agg(to_jsonb(i) ORDER BY i.installment_number) INTO installments
  FROM lending.loan_contract_installments i WHERE i.schedule_id=(n.anchor->>'schedule_id')::uuid;
 IF status.exact_posted IS DISTINCT FROM true OR status.correction_pending IS DISTINCT FROM false
  OR (SELECT to_jsonb(s)-'status' FROM lending.loan_contract_schedules s WHERE s.id=(n.anchor->>'schedule_id')::uuid) IS DISTINCT FROM r.source_snapshot->'schedule'
  OR (SELECT to_jsonb(s) FROM lending.loan_contract_schedule_registrations s WHERE s.schedule_id=(n.anchor->>'schedule_id')::uuid) IS DISTINCT FROM r.source_snapshot->'registration'
  OR installments IS DISTINCT FROM r.source_snapshot->'installments'
  OR (SELECT count(*) FROM lending.loan_contract_schedules WHERE loan_id=p_loan)<>1 THEN
  RETURN jsonb_build_object('ready',false,'blockers',jsonb_build_array('renewal_lineage_source_changed')); END IF;
 anchor:=n.anchor||jsonb_build_object('journal_entry_id',n.journal_entry_id,'posting_id',a.id);
 snapshot:=jsonb_build_object('policy_version','native_regular_renewal_anchor_v1','book',(SELECT to_jsonb(b) FROM accounting.book_identity b WHERE singleton),
  'cutoff_date',p_cutoff,'anchor',anchor,'lineage',to_jsonb(n),'review',to_jsonb(r),
  'completion_proof',to_jsonb(status),'debit_proof',r.source_snapshot->'debit_proof',
  'schedule',r.source_snapshot->'schedule','registration',r.source_snapshot->'registration','installments',installments);
 RETURN jsonb_build_object('ready',true,'blockers','[]'::jsonb,'origin_kind','native_renewal','anchor',anchor,'snapshot',snapshot,
  'source_digest',encode(sha256(convert_to(snapshot::text,'UTF8')),'hex'));
END $$;

DO $$ DECLARE definition TEXT; BEGIN
 definition:=pg_get_functiondef('accounting.regular_original_cash_rollforward(uuid,date,uuid)'::regprocedure);
 definition:=replace(definition,'accounting.regular_original_cash_rollforward(', 'accounting.native_regular_segment_cash_rollforward(');
 definition:=replace(definition,'accounting.regular_original_origin(', 'accounting.native_regular_segment_origin(');
 definition:=replace(definition,'p_cutoff<=last_day','p_cutoff<last_day');
 definition:=replace(definition,'event.collection_date<=(anchor->>''anchor_date'')::date','event.collection_date<(anchor->>''anchor_date'')::date');
 EXECUTE definition;
 -- An earlier paid operational loan and its successor use separate immutable
 -- schedules. Only the retained originating renewal may cross this gate.
 definition:=pg_get_functiondef('accounting.native_application_before_renewal_origin(uuid)'::regprocedure);
 definition:=replace(definition,'accounting.native_application_before_renewal_origin(', 'accounting.native_renewal_application_base_origin(');
 definition:=replace(definition,'accounting.regular_original_origin(', 'accounting.native_regular_segment_origin(');
 definition:=replace(definition,'prior_allowance:=coalesce(prior_allowance,0);',
  'prior_allowance:=coalesce(prior_allowance,(anchor->>''initial_allowance'')::numeric,0);');
 EXECUTE definition;
 definition:=pg_get_functiondef('accounting.treasury_chronological_regular_application_origin(uuid)'::regprocedure);
 definition:=replace(definition,'accounting.treasury_chronological_regular_application_origin(', 'accounting.native_renewal_application_origin(');
 definition:=replace(definition,'accounting.regular_original_cash_rollforward(', 'accounting.native_regular_segment_cash_rollforward(');
 definition:=replace(definition,'''prior_allowance'',result#>''{measurement,prior_allowance}''',
  '''prior_allowance'',coalesce(result#>''{measurement,prior_allowance}'',result#>''{anchor,initial_allowance}'',''0''::jsonb)');
 EXECUTE definition;
 definition:=pg_get_functiondef('accounting.treasury_chronological_regular_application_coordinates(uuid)'::regprocedure);
 definition:=replace(definition,'accounting.treasury_chronological_regular_application_coordinates(', 'accounting.native_renewal_application_coordinates(');
 definition:=replace(definition,
  'OR EXISTS(SELECT 1 FROM lending.loan_renewal_execution_events x WHERE x.old_loan_id=t.loan_id OR x.new_loan_id=t.loan_id)',
  'OR EXISTS(SELECT 1 FROM lending.loan_renewal_execution_events x WHERE (x.old_loan_id=t.loan_id OR x.new_loan_id=t.loan_id) AND NOT EXISTS(SELECT 1 FROM accounting.native_regular_asset_lineage n WHERE n.operational_loan_id=t.loan_id AND n.execution_id=x.id))');
 definition:=replace(definition,'''treasury_regular_original_chronological_cash_v1''','''treasury_regular_renewal_chronological_cash_v1''');
 EXECUTE definition;
 definition:=pg_get_functiondef('accounting.loan_period_native_cash_assessment_candidate(uuid,uuid)'::regprocedure);
 definition:=replace(definition,'accounting.loan_period_native_cash_assessment_candidate(', 'accounting.loan_period_native_renewal_assessment_candidate(');
 definition:=replace(definition,'accounting.regular_original_origin(', 'accounting.native_regular_segment_origin(');
 definition:=replace(definition,'accounting.regular_original_cash_rollforward(', 'accounting.native_regular_segment_cash_rollforward(');
 definition:=replace(definition,
  'OR EXISTS(SELECT 1 FROM lending.loan_renewal_execution_events e WHERE (e.old_loan_id=p_loan OR e.new_loan_id=p_loan) AND e.business_date<=period_row.end_date)',
  'OR EXISTS(SELECT 1 FROM lending.loan_renewal_execution_events e WHERE (e.old_loan_id=p_loan OR e.new_loan_id=p_loan) AND e.business_date<=period_row.end_date AND NOT EXISTS(SELECT 1 FROM accounting.native_regular_asset_lineage n WHERE n.operational_loan_id=p_loan AND n.execution_id=e.id))');
 definition:=replace(definition,'anchor.anchor_date>=period_row.end_date','anchor.anchor_date>period_row.end_date');
 definition:=replace(definition,'days<=0','days<0');
 definition:=replace(definition,'rate:=anchor.daily_eir;',
  'previous_allowance:=coalesce((native_origin#>>''{anchor,initial_allowance}'')::numeric,0); rate:=anchor.daily_eir;');
 definition:=replace(definition,'''regular_original_cash_prefix_v1''','''regular_renewal_cash_prefix_v1''');
 EXECUTE definition;
END $$;

CREATE OR REPLACE FUNCTION accounting.treasury_native_regular_application_origin(p_application UUID)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE result JSONB; prior_requests JSONB;
BEGIN
 IF EXISTS(SELECT 1 FROM treasury.applications a JOIN lending.collection_transactions t ON t.id::text=a.source_result->'transaction_ids'->>0
  JOIN accounting.native_regular_asset_lineage n ON n.operational_loan_id=t.loan_id WHERE a.id=p_application) THEN
  result:=accounting.native_renewal_application_base_origin(p_application);
 ELSE result:=accounting.native_application_before_renewal_origin(p_application); END IF;
 SELECT coalesce(jsonb_agg(x ORDER BY x->>'id'),'[]'::jsonb) INTO prior_requests FROM jsonb_array_elements(result->'renewals') x
  WHERE (x->>'submitted_at')::timestamptz<=(result#>>'{transaction,accepted_at}')::timestamptz;
 RETURN jsonb_set(result,'{renewals}',prior_requests);
END $$;

DO $$ BEGIN
 IF to_regprocedure('accounting.treasury_application_before_renewal_origin(uuid)') IS NULL THEN
  ALTER FUNCTION accounting.treasury_regular_application_origin(UUID) RENAME TO treasury_application_before_renewal_origin; END IF;
 IF to_regprocedure('accounting.treasury_application_before_renewal_coordinates(uuid)') IS NULL THEN
  ALTER FUNCTION accounting.treasury_regular_application_coordinates(UUID) RENAME TO treasury_application_before_renewal_coordinates; END IF;
 IF to_regprocedure('accounting.loan_period_before_renewal_candidate(uuid,uuid)') IS NULL THEN
  ALTER FUNCTION accounting.loan_period_elapsed_assessment_candidate(UUID,UUID) RENAME TO loan_period_before_renewal_candidate; END IF;
END $$;
CREATE OR REPLACE FUNCTION accounting.treasury_regular_application_origin(p_application UUID)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM treasury.applications a JOIN lending.collection_transactions t ON t.id::text=a.source_result->'transaction_ids'->>0
  JOIN accounting.native_regular_asset_lineage n ON n.operational_loan_id=t.loan_id WHERE a.id=p_application) THEN
  RETURN accounting.native_renewal_application_origin(p_application); END IF;
 RETURN accounting.treasury_application_before_renewal_origin(p_application);
END $$;
CREATE OR REPLACE FUNCTION accounting.treasury_regular_application_coordinates(p_application UUID)
RETURNS JSONB LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM treasury.applications a JOIN lending.collection_transactions t ON t.id::text=a.source_result->'transaction_ids'->>0
  JOIN accounting.native_regular_asset_lineage n ON n.operational_loan_id=t.loan_id WHERE a.id=p_application) THEN
  RETURN accounting.native_renewal_application_coordinates(p_application); END IF;
 RETURN accounting.treasury_application_before_renewal_coordinates(p_application);
END $$;
CREATE OR REPLACE FUNCTION accounting.loan_period_elapsed_assessment_candidate(p_period UUID,p_loan UUID)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM accounting.native_regular_asset_lineage n JOIN accounting.fiscal_periods p ON p.id=p_period
  WHERE n.previous_operational_loan_id=p_loan AND n.effective_date<=p.end_date) THEN
  RETURN accounting.loan_period_renewal_settled_candidate(p_period,p_loan); END IF;
 IF EXISTS(SELECT 1 FROM accounting.native_regular_asset_lineage WHERE operational_loan_id=p_loan) THEN
  RETURN accounting.loan_period_native_renewal_assessment_candidate(p_period,p_loan); END IF;
 RETURN accounting.loan_period_before_renewal_candidate(p_period,p_loan);
END $$;

CREATE OR REPLACE FUNCTION accounting.loan_period_renewal_settled_candidate(p_period UUID,p_loan UUID)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
DECLARE n accounting.native_regular_asset_lineage%ROWTYPE; r accounting.native_renewal_measurement_reviews%ROWTYPE;
 p accounting.fiscal_periods%ROWTYPE; loan lending.loans%ROWTYPE; snapshot JSONB; ledger JSONB; own UUID[];
 blockers TEXT[]:=ARRAY[]::text[]; gross NUMERIC; accrued NUMERIC; allowance NUMERIC; boundary JSONB;
BEGIN
 SELECT * INTO p FROM accounting.fiscal_periods WHERE id=p_period;
 SELECT * INTO n FROM accounting.native_regular_asset_lineage WHERE previous_operational_loan_id=p_loan AND effective_date<=p.end_date;
 SELECT * INTO r FROM accounting.native_renewal_measurement_reviews WHERE id=n.review_id;
 SELECT * INTO loan FROM lending.loans WHERE id=p_loan;
 IF n.operational_loan_id IS NULL OR NOT accounting.native_renewal_structural_exact(n.journal_entry_id)
  OR NOT EXISTS(SELECT 1 FROM accounting.loan_payout_accounting_posting_status s WHERE s.journal_entry_id=n.journal_entry_id AND s.exact_posted AND NOT s.correction_pending)
  OR loan.status<>'paid' OR NOT EXISTS(SELECT 1 FROM lending.loan_collection_state WHERE loan_id=p_loan AND remaining_balance=0) THEN
  RETURN jsonb_build_object('ready',false,'blockers',jsonb_build_array('exact_renewal_settlement_required')); END IF;
 boundary:=r.source_snapshot->'boundary';
 SELECT coalesce(array_agg(x) FILTER(WHERE x IS NOT NULL),ARRAY[]::uuid[]) INTO own
  FROM accounting.loan_elapsed_assessment_postings a CROSS JOIN LATERAL unnest(ARRAY[a.eir_journal_entry_id,a.allowance_journal_entry_id]) x
  WHERE a.loan_id=p_loan AND a.fiscal_period_id=p_period;
 SELECT coalesce(sum(l.debit-l.credit) FILTER(WHERE a.code IN('1100','1110')),0),
  coalesce(sum(l.debit-l.credit) FILTER(WHERE a.code='1120'),0),coalesce(sum(l.credit-l.debit) FILTER(WHERE a.code='1190'),0)
 INTO gross,accrued,allowance FROM accounting.journal_entries j JOIN accounting.journal_lines l ON l.journal_entry_id=j.id
 JOIN accounting.accounts a ON a.id=l.account_id WHERE j.status='posted' AND j.posting_date<=p.end_date AND l.loan_id=p_loan AND NOT j.id=ANY(own);
 IF (gross,accrued,allowance) IS DISTINCT FROM(0::numeric,0::numeric,0::numeric) THEN blockers:=array_append(blockers,'renewed_old_asset_controls_not_zero'); END IF;
 IF EXISTS(SELECT 1 FROM accounting.journal_entries j JOIN accounting.journal_lines l ON l.journal_entry_id=j.id
  WHERE j.status='posted' AND j.posting_date<=p.end_date AND l.loan_id=p_loan AND j.id<>n.journal_entry_id AND NOT j.id=ANY(own)
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(boundary->'ledger') x WHERE x#>>'{journal,id}'=j.id::text)
   AND NOT accounting.native_loan_ancillary_tax_exact(j.id,p_loan)) THEN blockers:=array_append(blockers,'unrecognized_settled_asset_journal'); END IF;
 SELECT coalesce(jsonb_agg(jsonb_build_object('journal',to_jsonb(j),'line',to_jsonb(l),'account',accounting.treasury_gl_account_snapshot(l.account_id)-ARRAY['name','is_active'])
  ORDER BY j.posting_date,j.id,l.line_number),'[]'::jsonb) INTO ledger
 FROM accounting.journal_entries j JOIN accounting.journal_lines l ON l.journal_entry_id=j.id
 WHERE j.status='posted' AND j.posting_date<=p.end_date AND l.loan_id=p_loan AND NOT j.id=ANY(own)
  AND NOT accounting.native_loan_ancillary_tax_exact(j.id,p_loan);
 snapshot:=jsonb_build_object('policy_version','regular_renewal_settled_prefix_v1','book',(SELECT to_jsonb(b) FROM accounting.book_identity b WHERE singleton),
  'period_id',p_period,'period_start',p.start_date,'cutoff_date',p.end_date,
  'loan',jsonb_build_object('id',loan.id,'client_id',loan.client_id,'loan_type_id',loan.loan_type_id,'principal',loan.principal,
   'daily_amount',loan.daily_amount,'interest_rate',loan.interest_rate,'date_released',loan.date_released,'due_date',loan.due_date),
  'anchor',boundary#>'{rollforward,anchor}','native_origin',boundary#>'{rollforward,native_origin}',
  'chart',accounting.elapsed_assessment_chart(),'ledger',ledger,'renewal_lineage',to_jsonb(n),'renewal_review',to_jsonb(r),
  'settled_by_exact_renewal',true,'contractual_cash_flows','[]'::jsonb,'contractual_pv_raw',0,'gross_carrying_raw',0,'gross_carrying_amount',0,
  'dpd',0,'due_unpaid_amount',0,'prior_allowance',0,
  'eir',jsonb_build_object('segment_source_key',boundary#>'{rollforward,anchor,anchor_source_key}',
   'anchor_date',boundary#>'{rollforward,anchor,anchor_date}','daily_eir',boundary->'original_daily_eir',
   'raw_cumulative_interest',boundary#>'{rollforward,cumulative_interest}',
   'cumulative_interest',boundary#>'{rollforward,cumulative_interest}',
   'prior_recognized_interest',boundary#>'{rollforward,cumulative_interest}','incremental_interest',0,'prior_cutoff',n.effective_date));
 RETURN jsonb_build_object('ready',cardinality(blockers)=0,'blockers',to_jsonb(blockers),'as_of_date',p.end_date,
  'eir',snapshot->'eir','snapshot',snapshot,'source_digest',encode(sha256(convert_to(snapshot::text,'UTF8')),'hex'));
END $$;

DO $$ BEGIN
 IF to_regprocedure('accounting.calculate_elapsed_before_renewal_ecl(jsonb,jsonb,jsonb)') IS NULL THEN
  ALTER FUNCTION accounting.calculate_elapsed_assessment_ecl(JSONB,JSONB,JSONB) RENAME TO calculate_elapsed_before_renewal_ecl; END IF;
 IF to_regprocedure('accounting.period_legacy_before_renewal_blockers(uuid)') IS NULL THEN
  ALTER FUNCTION accounting.period_legacy_source_blockers(UUID) RENAME TO period_legacy_before_renewal_blockers; END IF;
 IF to_regprocedure('accounting.period_review_before_renewal_evidence(uuid)') IS NULL THEN
  ALTER FUNCTION accounting.period_review_additional_evidence(UUID) RENAME TO period_review_before_renewal_evidence; END IF;
 IF to_regprocedure('accounting.lock_period_review_before_renewal_sources()') IS NULL THEN
  ALTER FUNCTION accounting.lock_period_review_additional_sources() RENAME TO lock_period_review_before_renewal_sources; END IF;
END $$;
CREATE OR REPLACE FUNCTION accounting.calculate_elapsed_assessment_ecl(p_source JSONB,p_risk JSONB,p_scenarios JSONB)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF p_source->>'settled_by_exact_renewal' IS DISTINCT FROM 'true' THEN
  RETURN accounting.calculate_elapsed_before_renewal_ecl(p_source,p_risk,p_scenarios); END IF;
 IF (p_source->>'gross_carrying_amount')::numeric<>0 OR (p_source->>'prior_allowance')::numeric<>0
  OR p_scenarios IS DISTINCT FROM '[]'::jsonb OR p_risk->>'as_of_date' IS DISTINCT FROM p_source->>'cutoff_date'
  OR p_risk->>'primary_evidence_basis' IS DISTINCT FROM 'exact_renewal'
  OR p_risk->>'evidence_reference' IS DISTINCT FROM p_source#>>'{renewal_review,id}'
  OR length(btrim(coalesce(p_risk->>'review_note','')))<20
  OR EXISTS(SELECT 1 FROM jsonb_object_keys(p_risk) key WHERE key NOT IN('as_of_date','primary_evidence_basis','evidence_reference','review_note')) THEN
  RAISE EXCEPTION 'Exact reviewed renewal settlement and an explicit old-asset cutoff review are required.' USING ERRCODE='23514'; END IF;
 RETURN jsonb_build_object('policy_version','regular_exact_renewal_zero_ecl_v1','as_of_date',p_source->'cutoff_date',
  'loss_horizon','settled','risk_review',p_risk,'forward_evidence','[]'::jsonb,'scenarios','[]'::jsonb,
  'original_daily_eir',p_source#>'{eir,daily_eir}','contractual_cash_flows','[]'::jsonb,
  'contractual_pv_raw',0,'gross_carrying_amount',0,'weighted_shortfall_raw',0,'ecl_amount',0,'prior_allowance',0,'allowance_delta',0);
END $$;
CREATE OR REPLACE FUNCTION accounting.period_legacy_source_blockers(p_period UUID)
RETURNS TABLE(source_type TEXT,source_id UUID,effective_date DATE,amount NUMERIC(18,2),reason TEXT,account_id UUID)
LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT b.* FROM accounting.period_legacy_before_renewal_blockers(p_period) b
 WHERE NOT(b.source_type='loan_renewal_execution' AND EXISTS(SELECT 1 FROM accounting.native_regular_asset_lineage n
  JOIN accounting.loan_payout_accounting_posting_status s ON s.journal_entry_id=n.journal_entry_id
  JOIN accounting.fiscal_periods p ON p.id=p_period WHERE n.execution_id=b.source_id AND n.effective_date<=p.end_date
   AND accounting.native_renewal_structural_exact(n.journal_entry_id) AND s.exact_posted AND NOT s.correction_pending));
$$;
CREATE OR REPLACE FUNCTION accounting.period_review_additional_evidence(p_period UUID)
RETURNS JSONB LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT accounting.period_review_before_renewal_evidence(p_period)||CASE WHEN count(n.operational_loan_id)=0 THEN '{}'::jsonb ELSE
  jsonb_build_object('native_regular_renewals',jsonb_agg(jsonb_build_object('lineage',to_jsonb(n),'review',to_jsonb(r)) ORDER BY n.operational_loan_id)) END
 FROM accounting.native_regular_asset_lineage n JOIN accounting.native_renewal_measurement_reviews r ON r.id=n.review_id
 JOIN accounting.fiscal_periods p ON p.id=p_period WHERE n.effective_date<=p.end_date;
$$;
CREATE OR REPLACE FUNCTION accounting.lock_period_review_additional_sources()
RETURNS VOID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 PERFORM accounting.lock_period_review_before_renewal_sources();
 LOCK TABLE accounting.native_regular_asset_lineage,accounting.native_renewal_measurement_reviews,
  accounting.renewal_treatment_decisions,accounting.renewal_treatment_decision_voids IN SHARE MODE;
END $$;

-- The same preparation-bound journal/deferred checks apply to successor cash.
DO $$ DECLARE definition TEXT; signature TEXT; BEGIN
 FOREACH signature IN ARRAY ARRAY['accounting.regular_application_prefix_admitted(uuid)','accounting.assert_regular_application_committed()'] LOOP
  definition:=pg_get_functiondef(signature::regprocedure);
  definition:=replace(definition,'''treasury_regular_original_chronological_cash_v1'')',
   '''treasury_regular_original_chronological_cash_v1'',''treasury_regular_renewal_chronological_cash_v1'')');
  EXECUTE definition;
 END LOOP;
 -- A second renewal derives its source boundary from the retained segment,
 -- while the original segment follows the original normalizer unchanged.
 definition:=pg_get_functiondef('accounting.native_renewal_boundary(uuid,date)'::regprocedure);
 definition:=replace(definition,'accounting.regular_original_cash_rollforward(', 'accounting.native_regular_segment_cash_rollforward(');
 definition:=replace(definition,'cash_interest:=(roll->>''cash_cumulative_interest'')::numeric;',
  'allowance:=coalesce((roll#>>''{anchor,initial_allowance}'')::numeric,0); cash_interest:=(roll->>''cash_cumulative_interest'')::numeric;');
 EXECUTE definition;
END $$;

DO $$ DECLARE r TEXT; item RECORD; BEGIN
 FOR item IN SELECT p.oid::regprocedure AS signature FROM pg_proc p WHERE p.pronamespace='accounting'::regnamespace
  AND (p.proname LIKE '%renewal%' OR p.proname LIKE 'native_regular_segment_%'
   OR p.proname IN('treasury_native_regular_application_origin','loan_payout_accounting_origin','loan_payout_coordinates',
    'prepare_loan_payout_accounting','post_loan_payout_accounting','regular_application_causal_origin','treasury_regular_application_origin',
    'treasury_regular_application_coordinates','loan_period_elapsed_assessment_candidate',
    'calculate_elapsed_assessment_ecl','period_legacy_source_blockers','period_review_additional_evidence',
    'lock_period_review_additional_sources')) LOOP
  EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC',item.signature);
  FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
   IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN EXECUTE format('REVOKE ALL ON FUNCTION %s FROM %I',item.signature,r); END IF;
  END LOOP;
 END LOOP;
END $$;

REVOKE ALL ON FUNCTION accounting.native_renewal_measurement(JSONB) FROM PUBLIC;
DO $$ DECLARE r TEXT; BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN EXECUTE format('REVOKE ALL ON FUNCTION accounting.native_renewal_measurement(JSONB) FROM %I',r); END IF;
 END LOOP;
END $$;
COMMIT;
