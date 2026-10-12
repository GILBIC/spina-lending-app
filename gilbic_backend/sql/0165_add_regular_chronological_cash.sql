BEGIN;

-- Retain the previous version for exact first-cash and no-cash reviews.
DO $$ BEGIN
 IF to_regprocedure('accounting.treasury_regular_application_before_chronological_origin(uuid)') IS NULL THEN
  ALTER FUNCTION accounting.treasury_regular_application_origin(UUID) RENAME TO treasury_regular_application_before_chronological_origin;
 END IF;
 IF to_regprocedure('accounting.treasury_regular_application_before_chronological_coordinates(uuid)') IS NULL THEN
  ALTER FUNCTION accounting.treasury_regular_application_coordinates(UUID) RENAME TO treasury_regular_application_before_chronological_coordinates;
 END IF;
 IF to_regprocedure('accounting.loan_period_before_chronological_candidate(uuid,uuid)') IS NULL THEN
  ALTER FUNCTION accounting.loan_period_elapsed_assessment_candidate(UUID,UUID) RENAME TO loan_period_before_chronological_candidate;
 END IF;
END $$;

-- A prior claim is checked without invoking its chronological origin again.
-- Measurement is independently checked by the caller's one ordered loop.
CREATE OR REPLACE FUNCTION accounting.regular_application_structural_claim(p_transaction UUID)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE a accounting.treasury_application_postings%ROWTYPE; p accounting.treasury_application_preparations%ROWTYPE;
 j accounting.journal_entries%ROWTYPE; exact BOOLEAN; changed BOOLEAN; current_origin JSONB;
BEGIN
 SELECT * INTO a FROM accounting.treasury_application_postings WHERE transaction_id=p_transaction;
 IF NOT FOUND THEN RETURN NULL; END IF;
 SELECT * INTO p FROM accounting.treasury_application_preparations WHERE id=a.preparation_id;
 SELECT * INTO j FROM accounting.journal_entries WHERE id=a.journal_entry_id;
 exact:=a.application_id=p.application_id AND a.transaction_id=p.transaction_id AND a.receipt_id=p.receipt_id
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
    AND l.client_id IS NOT DISTINCT FROM x.client_id AND l.loan_id IS NOT DISTINCT FROM x.loan_id));
 current_origin:=accounting.regular_application_causal_origin(a.application_id,accounting.treasury_native_regular_application_origin(a.application_id));
 changed:=(current_origin-ARRAY['measurement','cash_rollforward']) IS DISTINCT FROM
   ((p.snapshot->'origin')-ARRAY['measurement','cash_rollforward'])
  OR EXISTS(SELECT 1 FROM jsonb_array_elements(p.snapshot->'lines') line
   WHERE (line->'account_snapshot')-ARRAY['name','is_active'] IS DISTINCT FROM accounting.treasury_gl_account_snapshot((line->>'account_id')::uuid)-ARRAY['name','is_active'])
  OR NOT EXISTS(SELECT 1 FROM accounting.treasury_receipt_posting_status s WHERE s.receipt_id=a.receipt_id AND s.exact_posted AND NOT s.correction_pending);
 RETURN jsonb_build_object('application_id',a.application_id,'transaction_id',a.transaction_id,'receipt_id',a.receipt_id,
  'treasury_account_id',a.treasury_account_id,'book_id',a.book_id,'loan_id',a.loan_id,'preparation_id',a.preparation_id,
  'journal_entry_id',a.journal_entry_id,'source_digest',a.source_digest,'amount',a.amount,
  'event_id',p.snapshot->'event_id','posting_date',p.snapshot->'posting_date','exact_posted',exact,'correction_pending',changed);
END $$;

CREATE OR REPLACE FUNCTION accounting.regular_original_cash_rollforward(p_loan UUID,p_cutoff DATE,p_through UUID DEFAULT NULL)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
DECLARE origin JSONB; anchor JSONB; target lending.collection_transactions%ROWTYPE; event RECORD; proof JSONB; retained JSONB;
 rate NUMERIC; loan_amount NUMERIC; accrued NUMERIC:=0; gross NUMERIC; raw_gross NUMERIC; raw_accrued NUMERIC;
 interest NUMERIC; total_interest NUMERIC:=0; prior_interest NUMERIC:=0; last_day DATE;
 before_loan NUMERIC; before_accrued NUMERIC; credit_interest NUMERIC; credit_loan NUMERIC; measurement JSONB;
 claims JSONB:='[]'::jsonb; entries UUID[]:=ARRAY[]::uuid[]; events_count INTEGER:=0; previous_loan NUMERIC; previous_accrued NUMERIC;
BEGIN
 origin:=accounting.regular_original_origin(p_loan,p_cutoff);
 IF origin->>'ready' IS DISTINCT FROM 'true' THEN RETURN origin; END IF;
 anchor:=origin->'anchor'; rate:=(anchor->>'daily_eir')::numeric;
 loan_amount:=(anchor->>'initial_gross_carrying_amount')::numeric; last_day:=(anchor->>'anchor_date')::date;
 IF p_cutoff<=last_day OR p_cutoff>(anchor->>'contractual_due_date')::date THEN
  RETURN jsonb_build_object('ready',false,'blockers',jsonb_build_array('original_cash_boundary_required'));
 END IF;
 IF p_through IS NOT NULL THEN
  SELECT * INTO target FROM lending.collection_transactions WHERE id=p_through AND loan_id=p_loan AND collection_date=p_cutoff;
  IF NOT FOUND THEN RETURN jsonb_build_object('ready',false,'blockers',jsonb_build_array('exact_cash_boundary_required')); END IF;
 END IF;
 FOR event IN SELECT t.* FROM lending.collection_transactions t WHERE t.loan_id=p_loan AND t.collection_date<=p_cutoff
  AND (t.amount>0 OR t.entry_type IN('payment','advance'))
  AND (p_through IS NULL OR (t.collection_date,t.accepted_at,t.id)<=(target.collection_date,target.accepted_at,target.id))
  ORDER BY t.collection_date,t.accepted_at,t.id LOOP
  events_count:=events_count+1;
  IF events_count>5000 OR event.is_voided OR event.amount<=0 OR event.entry_type NOT IN('payment','advance')
   OR event.funding_source IS DISTINCT FROM 'treasury_receipt' OR event.collection_date<last_day
   OR event.collection_date<=(anchor->>'anchor_date')::date
   OR EXISTS(SELECT 1 FROM lending.collection_transaction_voids WHERE transaction_id=event.id) THEN
   RETURN jsonb_build_object('ready',false,'blockers',jsonb_build_array('unsupported_or_reversed_original_cash_source'));
  END IF;
  previous_loan:=loan_amount; previous_accrued:=accrued; prior_interest:=total_interest;
  raw_gross:=(loan_amount+accrued)*power(1::numeric+rate,(event.collection_date-last_day)::numeric);
  raw_accrued:=accrued+raw_gross-loan_amount-accrued;
  interest:=round(raw_gross-loan_amount-accrued,2);
  gross:=round(raw_gross,2); before_accrued:=round(raw_accrued,2); before_loan:=gross-before_accrued;
  IF event.amount>gross THEN RETURN jsonb_build_object('ready',false,'blockers',jsonb_build_array('cash_exceeds_original_carrying_review')); END IF;
  credit_interest:=least(event.amount,before_accrued); credit_loan:=event.amount-credit_interest;
  accrued:=before_accrued-credit_interest; loan_amount:=gross-event.amount-accrued;
  total_interest:=total_interest+interest; last_day:=event.collection_date;
  IF p_through IS NULL OR event.id<>p_through THEN
   proof:=accounting.regular_application_structural_claim(event.id);
   SELECT snapshot->'measurement' INTO retained FROM accounting.treasury_application_preparations WHERE id=(proof->>'preparation_id')::uuid;
   IF proof IS NULL OR proof->>'exact_posted' IS DISTINCT FROM 'true' OR proof->>'correction_pending' IS DISTINCT FROM 'false'
    OR proof->>'loan_id' IS DISTINCT FROM p_loan::text OR (proof->>'amount')::numeric IS DISTINCT FROM event.amount
    OR (retained->>'cumulative_interest')::numeric IS DISTINCT FROM total_interest
    OR (retained->>'initial_loan_component')::numeric IS DISTINCT FROM previous_loan
    OR (retained->>'gross_carrying_before')::numeric IS DISTINCT FROM gross
    OR (retained->>'cash_to_accrued_interest')::numeric IS DISTINCT FROM credit_interest
    OR (retained->>'cash_to_loan_component')::numeric IS DISTINCT FROM credit_loan
    OR (retained->>'loan_component_after')::numeric IS DISTINCT FROM loan_amount
    OR (retained->>'accrued_interest_after')::numeric IS DISTINCT FROM accrued
    OR (SELECT count(*) FROM accounting.treasury_application_postings WHERE transaction_id=event.id)<>1 THEN
    RETURN jsonb_build_object('ready',false,'blockers',jsonb_build_array('prior_original_cash_posting_not_exact'));
   END IF;
   claims:=claims||jsonb_build_array(jsonb_build_object('transaction',to_jsonb(event),'posting',proof));
   entries:=array_append(entries,(proof->>'journal_entry_id')::uuid);
  END IF;
  measurement:=jsonb_build_object('daily_eir',rate,'anchor_date',anchor->'anchor_date','gross_carrying_raw',raw_gross,
   'raw_cumulative_interest',prior_interest+raw_gross-previous_loan-previous_accrued,
   'cumulative_interest',total_interest::numeric(18,2)::text,'prior_cash_cumulative_interest',prior_interest::numeric(18,2)::text,
   'initial_loan_component',previous_loan::numeric(18,2)::text,'prior_cash_accrued_interest',previous_accrued::numeric(18,2)::text,
   'gross_carrying_before',gross::numeric(18,2)::text,'cash_to_accrued_interest',credit_interest::numeric(18,2)::text,
   'cash_to_loan_component',credit_loan::numeric(18,2)::text,'loan_component_after',loan_amount::numeric(18,2)::text,
   'accrued_interest_after',accrued::numeric(18,2)::text);
 END LOOP;
 IF p_through IS NOT NULL AND (events_count=0 OR event.id IS DISTINCT FROM p_through) THEN
  RETURN jsonb_build_object('ready',false,'blockers',jsonb_build_array('exact_cash_boundary_required'));
 END IF;
 raw_gross:=(loan_amount+accrued)*power(1::numeric+rate,(p_cutoff-last_day)::numeric);
 RETURN jsonb_build_object('ready',true,'blockers','[]'::jsonb,'anchor',anchor,'native_origin',origin,
  'measurement',measurement,'cash_claims',claims,'journal_ids',to_jsonb(entries),'last_cash_date',last_day,
  'cash_cumulative_interest',total_interest,'cash_loan_component',loan_amount,'cash_accrued_interest',accrued,
  'gross_carrying_raw',raw_gross,'tail_interest_raw',raw_gross-loan_amount-accrued,
  'cumulative_interest',total_interest+round(raw_gross-loan_amount-accrued,2));
END $$;

-- Ignore only retained later accounting claims when reconstructing an earlier
-- application. Unknown journals, earlier cash and changed sources remain visible.
CREATE OR REPLACE FUNCTION accounting.regular_application_causal_origin(p_application UUID,p_origin JSONB)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE t lending.collection_transactions%ROWTYPE; ledger JSONB;
BEGIN
 SELECT * INTO t FROM lending.collection_transactions WHERE id=(p_origin#>>'{transaction,id}')::uuid;
 SELECT coalesce(jsonb_agg(item.value ORDER BY item.ordinality),'[]'::jsonb) INTO ledger
 FROM jsonb_array_elements(p_origin->'loan_ledger') WITH ORDINALITY item(value,ordinality)
 WHERE NOT EXISTS(SELECT 1 FROM accounting.treasury_application_postings a
  JOIN lending.collection_transactions later ON later.id=a.transaction_id
  WHERE a.journal_entry_id=(item.value#>>'{journal,id}')::uuid AND later.loan_id=t.loan_id
   AND (later.collection_date,later.accepted_at,later.id)>(t.collection_date,t.accepted_at,t.id))
 AND NOT EXISTS(SELECT 1 FROM accounting.loan_elapsed_assessment_postings a
  WHERE a.loan_id=t.loan_id AND a.as_of_date>=t.collection_date
   AND (item.value#>>'{journal,id}')::uuid IN(a.eir_journal_entry_id,a.allowance_journal_entry_id));
 RETURN jsonb_set(p_origin,'{loan_ledger}',ledger);
END $$;

-- Preserve first-cash bytes; only later actual cash selects the new policy.
CREATE OR REPLACE FUNCTION accounting.regular_application_has_prior_cash(p_application UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT EXISTS(SELECT 1 FROM treasury.applications a JOIN lending.collection_transactions t ON t.id::text=a.source_result->'transaction_ids'->>0
  JOIN lending.collection_transactions prior ON prior.loan_id=t.loan_id
   AND (prior.collection_date,prior.accepted_at,prior.id)<(t.collection_date,t.accepted_at,t.id)
  WHERE a.id=p_application AND (prior.amount>0 OR prior.entry_type IN('payment','advance'))
   AND EXISTS(SELECT 1 FROM treasury.loan_payouts p WHERE p.loan_id=t.loan_id AND p.source_kind='first_loan' AND p.status<>'cancelled'));
$$;

CREATE OR REPLACE FUNCTION accounting.treasury_chronological_regular_application_origin(p_application UUID)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE result JSONB; roll JSONB; measured JSONB; recognized NUMERIC; cash_interest NUMERIC;
BEGIN
 result:=accounting.treasury_native_regular_application_origin(p_application);
 roll:=accounting.regular_original_cash_rollforward((result#>>'{transaction,loan_id}')::uuid,(result#>>'{transaction,collection_date}')::date,(result#>>'{transaction,id}')::uuid);
 IF roll->>'ready' IS DISTINCT FROM 'true' THEN RETURN result||jsonb_build_object('cash_rollforward',roll,'measurement',NULL); END IF;
 measured:=roll->'measurement'; cash_interest:=(measured->>'prior_cash_cumulative_interest')::numeric;
 recognized:=greatest(cash_interest,coalesce((result#>>'{measurement,prior_recognized_interest}')::numeric,0));
 measured:=measured||jsonb_build_object('prior_recognized_interest',recognized::numeric(18,2)::text,
  'incremental_interest',((measured->>'cumulative_interest')::numeric-recognized)::numeric(18,2)::text,
  'prior_cutoff',result#>'{measurement,prior_cutoff}','prior_allowance',result#>'{measurement,prior_allowance}',
  'prior_accrued_interest',((measured->>'prior_cash_accrued_interest')::numeric+recognized-cash_interest)::numeric(18,2)::text);
 RETURN accounting.regular_application_causal_origin(p_application,result||jsonb_build_object('cash_rollforward',roll,'measurement',measured));
END $$;

CREATE OR REPLACE FUNCTION accounting.treasury_regular_application_origin(p_application UUID)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF accounting.regular_application_has_prior_cash(p_application) THEN RETURN accounting.treasury_chronological_regular_application_origin(p_application); END IF;
 RETURN accounting.regular_application_causal_origin(p_application,accounting.treasury_regular_application_before_chronological_origin(p_application));
END $$;

-- The ordered cash proof has already validated each earlier application on this
-- asset. Do not rebuild that entire chain once more for every liability debit.
-- Uncovered claims (including other products/assets) retain their own proof.
CREATE OR REPLACE FUNCTION accounting.regular_client_application_claims_exact(
 p_client UUID,p_cutoff DATE,p_loan UUID,p_claims JSONB)
RETURNS BOOLEAN LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE claim RECORD; proof JSONB;
BEGIN
 FOR claim IN SELECT a.* FROM accounting.treasury_application_postings a
  JOIN accounting.treasury_application_preparations p ON p.id=a.preparation_id
  WHERE (p.snapshot->>'client_id')::uuid=p_client AND (p.snapshot->>'posting_date')::date<=p_cutoff LOOP
  SELECT item->'posting' INTO proof FROM jsonb_array_elements(coalesce(p_claims,'[]'::jsonb)) item
   WHERE item#>>'{posting,journal_entry_id}'=claim.journal_entry_id::text
    AND item#>>'{posting,application_id}'=claim.application_id::text
    AND item#>>'{posting,loan_id}'=p_loan::text;
  IF proof IS NOT NULL THEN
   IF proof->>'exact_posted' IS DISTINCT FROM 'true' OR proof->>'correction_pending' IS DISTINCT FROM 'false' THEN RETURN false; END IF;
  ELSE
   IF NOT EXISTS(SELECT 1 FROM accounting.treasury_application_posting_status s
    WHERE s.application_id=claim.application_id AND s.exact_posted AND NOT s.correction_pending) THEN RETURN false; END IF;
  END IF;
 END LOOP;
 RETURN true;
END $$;

DO $$ DECLARE definition TEXT; old_clause TEXT; BEGIN
 definition:=pg_get_functiondef('accounting.treasury_native_regular_application_coordinates(uuid)'::regprocedure);
 definition:=replace(definition,'accounting.treasury_native_regular_application_coordinates(', 'accounting.treasury_chronological_regular_application_coordinates(');
 old_clause:=$old$ IF EXISTS(SELECT 1 FROM jsonb_array_elements(origin->'collection_history') x WHERE x->>'id'<>t.id::text
    AND ((x->>'amount')::numeric>0 OR x->>'entry_type' IN('payment','advance')))
  OR EXISTS(SELECT 1 FROM lending.collection_transaction_voids v JOIN lending.collection_transactions x ON x.id=v.transaction_id WHERE x.loan_id=t.loan_id) THEN
  RAISE EXCEPTION 'Original first cash adapter requires no prior cash or reversed source history.' USING ERRCODE='55000'; END IF;$old$;
 IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Chronological cash predecessor changed.'; END IF;
 definition:=replace(definition,old_clause,$new$ IF origin#>>'{cash_rollforward,ready}' IS DISTINCT FROM 'true' THEN
  RAISE EXCEPTION 'Exact chronological original cash claims are required.' USING ERRCODE='55000'; END IF;$new$);
 definition:=replace(definition,'previous_end:=NULL;',
  'allowed:=allowed||ARRAY(SELECT value::uuid FROM jsonb_array_elements_text(origin#>''{cash_rollforward,journal_ids}'')); previous_end:=NULL;');
 definition:=replace(definition,'b1120<>prior_interest','b1120<>(measured->>''prior_accrued_interest'')::numeric');
 old_clause:=$old$OR EXISTS(SELECT 1 FROM accounting.treasury_application_posting_status s JOIN treasury.receipts rr ON rr.id=s.receipt_id
   WHERE rr.client_id=r.client_id AND s.posting_date<=t.collection_date AND (NOT s.exact_posted OR s.correction_pending))$old$;
 IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Chronological liability proof predecessor changed.'; END IF;
 definition:=replace(definition,old_clause,
  'OR NOT accounting.regular_client_application_claims_exact(r.client_id,t.collection_date,t.loan_id,origin#>''{cash_rollforward,cash_claims}'')');
 definition:=replace(definition,'''treasury_regular_original_first_cash_v1''','''treasury_regular_original_chronological_cash_v1''');
 EXECUTE definition;
END $$;

CREATE OR REPLACE FUNCTION accounting.treasury_regular_application_coordinates(p_application UUID)
RETURNS JSONB LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF accounting.regular_application_has_prior_cash(p_application) THEN RETURN accounting.treasury_chronological_regular_application_coordinates(p_application); END IF;
 RETURN accounting.treasury_regular_application_before_chronological_coordinates(p_application);
END $$;

-- Extend the existing exact preparation-bound guard and deferred source proof.
DO $$ DECLARE definition TEXT; signature TEXT; old_clause TEXT; BEGIN
 FOREACH signature IN ARRAY ARRAY['accounting.regular_application_prefix_admitted(uuid)','accounting.assert_regular_application_committed()'] LOOP
  definition:=pg_get_functiondef(signature::regprocedure);
  old_clause:='p.snapshot->>''accounting_policy_version'' IS DISTINCT FROM ''treasury_regular_original_first_cash_v1''';
  IF position(old_clause IN definition)>0 THEN
   definition:=replace(definition,old_clause,'coalesce(p.snapshot->>''accounting_policy_version'','''') NOT IN(''treasury_regular_original_first_cash_v1'',''treasury_regular_original_chronological_cash_v1'')');
   EXECUTE definition;
  ELSIF position('treasury_regular_original_chronological_cash_v1' IN definition)=0 THEN RAISE EXCEPTION 'Chronological cash protection predecessor changed.'; END IF;
 END LOOP;
END $$;

DO $$ DECLARE definition TEXT; old_clause TEXT; replacement TEXT; BEGIN
 definition:=pg_get_functiondef('accounting.loan_period_native_elapsed_assessment_candidate(uuid,uuid)'::regprocedure);
 definition:=replace(definition,'accounting.loan_period_native_elapsed_assessment_candidate(', 'accounting.loan_period_native_cash_assessment_candidate(');
 definition:=replace(definition,'native_origin JSONB;','native_origin JSONB; roll JSONB; cash_interest NUMERIC;');
 old_clause:=$old$ IF EXISTS(SELECT 1 FROM lending.collection_transactions t WHERE t.loan_id=p_loan AND t.collection_date<=period_row.end_date
  AND (t.amount>0 OR t.entry_type IN('payment','advance'))) THEN blockers:=array_append(blockers,'collection_prefix_adapter_required'); END IF;$old$;
 IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Cash assessment predecessor changed.'; END IF;
 definition:=replace(definition,old_clause,$new$ roll:=accounting.regular_original_cash_rollforward(p_loan,period_row.end_date,NULL);
 IF roll->>'ready' IS DISTINCT FROM 'true' THEN RETURN jsonb_build_object('ready',false,'blockers',to_jsonb(blockers)||(roll->'blockers')); END IF;
 cash_interest:=(roll->>'cash_cumulative_interest')::numeric;$new$);
 old_clause:='gross_raw:=initial*power(1::numeric+rate,days::numeric); interest:=round(gross_raw-initial,2);';
 IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Cash assessment original measurement predecessor changed.'; END IF;
 definition:=replace(definition,old_clause,'gross_raw:=(roll->>''gross_carrying_raw'')::numeric; interest:=(roll->>''cumulative_interest'')::numeric;');
 old_clause:=$old$ SELECT coalesce(jsonb_agg(jsonb_build_object('id',i.id,'installment_number',i.installment_number,'due_date',i.due_date,
   'contractual_amount',i.contractual_amount,'allocated_amount',0,'remaining_amount',i.contractual_amount) ORDER BY i.installment_number),'[]'::jsonb),
  coalesce(sum(i.contractual_amount/power(1::numeric+rate,(i.due_date-period_row.end_date)::numeric)),0),
  coalesce(sum(i.contractual_amount) FILTER(WHERE i.due_date<=period_row.end_date),0),
  min(i.due_date) FILTER(WHERE i.due_date<=period_row.end_date)
 INTO flows,contractual_pv,due_unpaid,oldest_due FROM lending.loan_contract_installments i WHERE i.schedule_id=anchor.schedule_id;$old$;
 replacement:=$new$ SELECT coalesce(jsonb_agg(jsonb_build_object('id',i.id,'installment_number',i.installment_number,'due_date',i.due_date,
   'contractual_amount',i.contractual_amount,'allocated_amount',paid.amount,'remaining_amount',i.contractual_amount-paid.amount) ORDER BY i.installment_number),'[]'::jsonb),
  coalesce(sum((i.contractual_amount-paid.amount)/power(1::numeric+rate,(i.due_date-period_row.end_date)::numeric)),0),
  coalesce(sum(i.contractual_amount-paid.amount) FILTER(WHERE i.due_date<=period_row.end_date),0),
  min(i.due_date) FILTER(WHERE i.due_date<=period_row.end_date AND i.contractual_amount>paid.amount)
 INTO flows,contractual_pv,due_unpaid,oldest_due FROM lending.loan_contract_installments i
 CROSS JOIN LATERAL(SELECT coalesce(sum(a.amount_applied),0) AS amount FROM lending.loan_installment_payment_allocations a
  JOIN lending.collection_transactions t ON t.id=a.transaction_id WHERE a.installment_id=i.id AND t.collection_date<=period_row.end_date AND NOT t.is_voided) paid
 WHERE i.schedule_id=anchor.schedule_id;
 IF EXISTS(SELECT 1 FROM jsonb_array_elements(flows) x WHERE (x->>'remaining_amount')::numeric<0) THEN blockers:=array_append(blockers,'contractual_allocations_exceed_signed_amount'); END IF;$new$;
 IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Cash assessment contractual source predecessor changed.'; END IF;
 definition:=replace(definition,old_clause,replacement);
 old_clause:='IF round(contractual_pv,2)<>round(gross_raw,2) THEN blockers:=array_append(blockers,''contractual_pv_carrying_reconciliation_required''); END IF;';
 IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Cash assessment PV predecessor changed.'; END IF;
 definition:=replace(definition,old_clause,'IF contractual_pv<=0 OR gross_raw<=0 THEN blockers:=array_append(blockers,''settled_original_cash_assessment_required''); END IF;');
 old_clause:='||own_entries;';
 definition:=replace(definition,old_clause,'||own_entries||ARRAY(SELECT value::uuid FROM jsonb_array_elements_text(roll->''journal_ids''));');
 old_clause:='IF previous_interest>interest THEN';
 definition:=replace(definition,old_clause,'previous_interest:=greatest(previous_interest,cash_interest); IF previous_interest>interest THEN');
 old_clause:='IF b1100<>initial OR b1110<>0 OR b1120<>previous_interest OR b1190<>previous_allowance THEN';
 IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Cash assessment carrying predecessor changed.'; END IF;
 definition:=replace(definition,old_clause,
  'IF b1100<>(roll->>''cash_loan_component'')::numeric OR b1110<>0 OR b1120<>(roll->>''cash_accrued_interest'')::numeric+previous_interest-cash_interest OR b1190<>previous_allowance THEN');
 definition:=replace(definition,'''regular_original_segment_prefix_v1''','''regular_original_cash_prefix_v1''');
 definition:=replace(definition,'''raw_cumulative_interest'',gross_raw-initial',
  '''raw_cumulative_interest'',cash_interest+(roll->>''tail_interest_raw'')::numeric');
 old_clause:='snapshot:=snapshot||jsonb_build_object(''native_origin'',native_origin);';
 IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Cash assessment retained native predecessor changed.'; END IF;
 definition:=replace(definition,old_clause,'snapshot:=snapshot||jsonb_build_object(''native_origin'',native_origin,''cash_rollforward'',roll,''contractual_pv_carrying_difference'',contractual_pv-gross_raw);');
 EXECUTE definition;
END $$;

CREATE OR REPLACE FUNCTION accounting.loan_period_elapsed_assessment_candidate(p_period UUID,p_loan UUID)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM treasury.loan_payouts WHERE loan_id=p_loan AND source_kind='first_loan' AND status<>'cancelled')
  AND EXISTS(SELECT 1 FROM lending.collection_transactions t JOIN accounting.fiscal_periods p ON p.id=p_period
   WHERE t.loan_id=p_loan AND t.collection_date<=p.end_date AND (t.amount>0 OR t.entry_type IN('payment','advance'))) THEN
  RETURN accounting.loan_period_native_cash_assessment_candidate(p_period,p_loan);
 END IF;
 RETURN accounting.loan_period_before_chronological_candidate(p_period,p_loan);
END $$;

DO $$ DECLARE item RECORD; role_name TEXT; BEGIN
 FOR item IN SELECT p.oid::regprocedure signature FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
 WHERE n.nspname='accounting' AND p.proname IN('regular_original_cash_rollforward','regular_application_causal_origin','regular_application_structural_claim','regular_client_application_claims_exact',
  'regular_application_has_prior_cash','treasury_chronological_regular_application_origin','treasury_chronological_regular_application_coordinates',
  'treasury_regular_application_origin','treasury_regular_application_coordinates','treasury_regular_application_before_chronological_origin',
  'treasury_regular_application_before_chronological_coordinates','loan_period_before_chronological_candidate',
  'loan_period_native_cash_assessment_candidate','loan_period_elapsed_assessment_candidate') LOOP
  EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC',item.signature);
  FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
   IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN EXECUTE format('REVOKE ALL ON FUNCTION %s FROM %I',item.signature,role_name); END IF;
  END LOOP;
 END LOOP;
END $$;

COMMIT;
