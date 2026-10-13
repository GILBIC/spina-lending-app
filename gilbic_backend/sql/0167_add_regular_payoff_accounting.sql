BEGIN;

DO $$ DECLARE item RECORD; BEGIN
 FOR item IN SELECT * FROM (VALUES
  ('4030','regular_settlement_gain','Regular Loan Settlement Gain','income','credit'),
  ('5020','regular_settlement_loss','Regular Loan Settlement Loss','expense','debit')) x(code,key,name,kind,normal) LOOP
  IF EXISTS(SELECT 1 FROM accounting.accounts WHERE (code=item.code OR system_key=item.key)
   AND (code,system_key,account_type,normal_balance,is_posting) IS DISTINCT FROM(item.code,item.key,item.kind,item.normal,true)) THEN
   RAISE EXCEPTION 'Regular settlement chart definition conflicts with an existing account.';
  END IF;
  INSERT INTO accounting.accounts(code,system_key,name,account_type,normal_balance)
  VALUES(item.code,item.key,item.name,item.kind,item.normal) ON CONFLICT(system_key) DO NOTHING;
 END LOOP;
END $$;

CREATE TABLE IF NOT EXISTS accounting.regular_payoff_reviews(
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),request_id UUID NOT NULL UNIQUE,
 application_id UUID NOT NULL UNIQUE REFERENCES treasury.applications(id),
 source_digest TEXT NOT NULL CHECK(source_digest ~ '^[0-9a-f]{64}$'),source_snapshot JSONB NOT NULL,
 treatment TEXT NOT NULL CHECK(treatment='full_contractual_payoff_no_rebate'),
 contract_evidence_reference TEXT NOT NULL,review_rationale TEXT NOT NULL CHECK(length(btrim(review_rationale))>=20),
 actor_user_id UUID NOT NULL REFERENCES core.users(id),created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS accounting.regular_closed_term_reviews(
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),request_id UUID NOT NULL UNIQUE,
 loan_id UUID NOT NULL UNIQUE REFERENCES lending.loans(id),
 source_digest TEXT NOT NULL CHECK(source_digest ~ '^[0-9a-f]{64}$'),source_snapshot JSONB NOT NULL,
 treatment TEXT NOT NULL CHECK(treatment='original_eir_through_maturity_no_extension'),
 contract_evidence_reference TEXT NOT NULL,review_rationale TEXT NOT NULL CHECK(length(btrim(review_rationale))>=20),
 actor_user_id UUID NOT NULL REFERENCES core.users(id),created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

ALTER TABLE accounting.regular_payoff_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounting.regular_closed_term_reviews ENABLE ROW LEVEL SECURITY;

-- These private dispatchers preserve original-only source bytes while allowing
-- the same cash treatment on an independently proven renewed asset segment.
CREATE OR REPLACE FUNCTION accounting.regular_cash_has_renewal_lineage(p_loan UUID)
RETURNS BOOLEAN LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF to_regclass('accounting.native_regular_asset_lineage') IS NULL THEN RETURN false; END IF;
 RETURN EXISTS(SELECT 1 FROM accounting.native_regular_asset_lineage WHERE operational_loan_id=p_loan);
END $$;

CREATE OR REPLACE FUNCTION accounting.regular_cash_segment_origin(p_loan UUID,p_cutoff DATE)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF accounting.regular_cash_has_renewal_lineage(p_loan) THEN
  RETURN accounting.native_regular_segment_origin(p_loan,p_cutoff); END IF;
 RETURN accounting.regular_original_origin(p_loan,p_cutoff);
END $$;

CREATE OR REPLACE FUNCTION accounting.regular_cash_application_origin(p_application UUID)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE loan UUID;
BEGIN
 SELECT t.loan_id INTO loan FROM treasury.applications a JOIN lending.collection_transactions t
  ON t.id::text=a.source_result->'transaction_ids'->>0 WHERE a.id=p_application;
 IF accounting.regular_cash_has_renewal_lineage(loan) THEN
  RETURN accounting.native_renewal_application_origin(p_application); END IF;
 RETURN accounting.treasury_chronological_regular_application_origin(p_application);
END $$;

CREATE OR REPLACE FUNCTION accounting.regular_cash_contract_schedule(p_loan UUID)
RETURNS TABLE(schedule_id UUID,evidence_reference TEXT,evidence_basis TEXT)
LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF accounting.regular_cash_has_renewal_lineage(p_loan) THEN
  RETURN QUERY SELECT (n.anchor->>'schedule_id')::uuid,r.source_snapshot#>>'{registration,evidence_reference}',
   'signed_renewal_contract'::text FROM accounting.native_regular_asset_lineage n
   JOIN accounting.native_renewal_measurement_reviews r ON r.id=n.review_id WHERE n.operational_loan_id=p_loan;
 ELSE
  RETURN QUERY SELECT release.schedule_id,release.contract_evidence_reference,'signed_contract'::text
   FROM lending.first_loan_releases release WHERE release.loan_id=p_loan;
 END IF;
END $$;

CREATE OR REPLACE FUNCTION accounting.regular_closed_term_source(p_loan UUID)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE source JSONB; maturity DATE;
BEGIN
 SELECT due_date INTO maturity FROM lending.loans WHERE id=p_loan;
 IF maturity IS NULL OR maturity>=(statement_timestamp() AT TIME ZONE 'Asia/Manila')::date THEN
  RETURN jsonb_build_object('ready',false,'blockers',jsonb_build_array('closed_original_contract_required'));
 END IF;
 source:=accounting.regular_cash_segment_origin(p_loan,maturity);
 IF source->>'ready' IS DISTINCT FROM 'true' THEN RETURN source; END IF;
 RETURN source;
END $$;

CREATE OR REPLACE FUNCTION accounting.regular_closed_term_review_exact(p_loan UUID)
RETURNS BOOLEAN LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE review accounting.regular_closed_term_reviews%ROWTYPE; source JSONB;
BEGIN
 SELECT * INTO review FROM accounting.regular_closed_term_reviews WHERE loan_id=p_loan;
 IF NOT FOUND THEN RETURN false; END IF;
 source:=accounting.regular_closed_term_source(p_loan);
 RETURN source->>'ready'='true' AND source->>'source_digest'=review.source_digest AND source->'snapshot'=review.source_snapshot;
END $$;

CREATE OR REPLACE FUNCTION accounting.regular_closed_term_candidate(p_application UUID)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE source JSONB; app treasury.applications%ROWTYPE; transaction lending.collection_transactions%ROWTYPE; review UUID;
BEGIN
 SELECT * INTO app FROM treasury.applications WHERE id=p_application;
 SELECT * INTO transaction FROM lending.collection_transactions WHERE id::text=app.source_result->'transaction_ids'->>0;
 source:=accounting.regular_closed_term_source(transaction.loan_id);
 IF source->>'ready' IS DISTINCT FROM 'true' THEN RETURN source; END IF;
 SELECT id INTO review FROM accounting.regular_closed_term_reviews WHERE loan_id=transaction.loan_id;
 RETURN jsonb_build_object('ready',true,'blockers','[]'::jsonb,'application_id',app.id,'treasury_account_id',app.account_id,
  'book_id',source#>'{snapshot,book,id}','loan_id',transaction.loan_id,'contractual_due_date',source#>'{anchor,contractual_due_date}',
  'source_digest',source->>'source_digest','contract_evidence_reference',coalesce(source#>'{anchor,evidence_reference}',source#>'{snapshot,registration,evidence_reference}'),
  'review_id',review,'treatment','original_eir_through_maturity_no_extension');
END $$;

-- Full contractual repayment is a source fact. Its accounting treatment remains
-- an explicit retained Management decision, never inferred from a paid flag.
CREATE OR REPLACE FUNCTION accounting.regular_transaction_full_payoff(p_transaction UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT EXISTS(SELECT 1 FROM lending.collection_transactions t
  CROSS JOIN LATERAL accounting.regular_cash_contract_schedule(t.loan_id) release
  JOIN lending.loan_contract_schedule_registrations registration ON registration.schedule_id=release.schedule_id
  WHERE t.id=p_transaction AND t.amount>0 AND NOT t.is_voided AND t.funding_source='treasury_receipt'
   AND t.amount=t.previous_balance AND t.official_balance=0 AND t.applied_amount=t.amount AND t.unallocated_amount=0
   AND registration.evidence_basis=release.evidence_basis AND registration.evidence_reference=release.evidence_reference
   AND NOT EXISTS(SELECT 1 FROM lending.collection_transaction_voids WHERE transaction_id=t.id)
   AND t.amount=(SELECT coalesce(sum(amount_applied),0) FROM lending.loan_installment_payment_allocations WHERE transaction_id=t.id)
   AND NOT EXISTS(SELECT 1 FROM lending.loan_contract_installments i WHERE i.schedule_id=release.schedule_id
    AND i.contractual_amount<>(SELECT coalesce(sum(pa.amount_applied),0) FROM lending.loan_installment_payment_allocations pa
     JOIN lending.collection_transactions paid ON paid.id=pa.transaction_id WHERE pa.installment_id=i.id AND NOT paid.is_voided
      AND (paid.collection_date,paid.accepted_at,paid.id)<=(t.collection_date,t.accepted_at,t.id)))
   AND NOT EXISTS(SELECT 1 FROM lending.loan_installment_payment_allocations pa
    JOIN lending.loan_contract_installments i ON i.id=pa.installment_id WHERE pa.transaction_id=t.id AND i.schedule_id<>release.schedule_id));
$$;

CREATE OR REPLACE FUNCTION accounting.regular_application_full_payoff(p_application UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT coalesce(bool_or(accounting.regular_transaction_full_payoff(t.id)),false)
 FROM treasury.applications a JOIN lending.collection_transactions t ON t.id::text=a.source_result->'transaction_ids'->>0
 WHERE a.id=p_application AND jsonb_array_length(a.source_result->'transaction_ids')=1;
$$;

-- Same-day protected applications are later events than the release even when
-- their business dates coincide. This proof reads only immutable audit/journal
-- structure, so admitting them never recursively rebuilds the original anchor.
CREATE OR REPLACE FUNCTION accounting.regular_application_journal_structurally_exact(p_journal UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT EXISTS(SELECT 1 FROM accounting.treasury_application_postings a
  JOIN accounting.treasury_application_preparations p ON p.id=a.preparation_id
  JOIN accounting.journal_entries j ON j.id=a.journal_entry_id
  WHERE j.id=p_journal AND a.application_id=p.application_id AND a.transaction_id=p.transaction_id
   AND a.receipt_id=p.receipt_id AND a.loan_id=p.loan_id AND a.book_id=p.book_id AND a.source_digest=p.source_digest
   AND a.actor_user_id=p.actor_user_id AND a.amount=(p.snapshot->>'amount')::numeric
   AND j.status='posted' AND j.source_type='treasury_receipt_application' AND j.reversal_of_entry_id IS NULL
   AND j.source_reference=p.application_id::text AND j.source_event_key=p.snapshot->>'source_event_key'
   AND j.fiscal_period_id=(p.snapshot->>'fiscal_period_id')::uuid AND j.posting_date=(p.snapshot->>'posting_date')::date
   AND j.created_by_user_id=p.actor_user_id AND j.posted_by_user_id=p.actor_user_id
   AND p.snapshot->>'product_model'='fixed_daily'
   AND p.snapshot->>'accounting_policy_version' IN('treasury_regular_original_first_cash_v1','treasury_regular_original_chronological_cash_v1','treasury_regular_renewal_chronological_cash_v1','treasury_regular_original_full_payoff_v1')
   AND (SELECT count(*) FROM accounting.journal_lines WHERE journal_entry_id=j.id)=jsonb_array_length(p.snapshot->'lines')
   AND NOT EXISTS(SELECT 1 FROM jsonb_to_recordset(p.snapshot->'lines') x(line_number INT,account_id UUID,debit NUMERIC,credit NUMERIC,client_id UUID,loan_id UUID)
    WHERE NOT EXISTS(SELECT 1 FROM accounting.journal_lines l WHERE l.journal_entry_id=j.id AND l.line_number=x.line_number
     AND (l.account_id,l.debit,l.credit,l.client_id,l.loan_id) IS NOT DISTINCT FROM(x.account_id,x.debit,x.credit,x.client_id,x.loan_id))));
$$;

CREATE OR REPLACE FUNCTION accounting.regular_elapsed_journal_structurally_exact(p_journal UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT EXISTS(SELECT 1 FROM accounting.loan_elapsed_assessment_postings a
  JOIN accounting.loan_elapsed_assessment_preparations p ON p.id=a.preparation_id
  JOIN accounting.journal_entries j ON j.id=p_journal
  WHERE (a.book_id,a.fiscal_period_id,a.loan_id,a.as_of_date,a.confirmation_digest)
    IS NOT DISTINCT FROM(p.book_id,p.fiscal_period_id,p.loan_id,p.as_of_date,p.confirmation_digest)
   AND j.posted_by_user_id=a.posted_by
   AND ((a.eir_journal_entry_id=j.id AND accounting.elapsed_assessment_journal_exact(p.id,j.id,'eir'))
    OR (a.allowance_journal_entry_id=j.id AND accounting.elapsed_assessment_journal_exact(p.id,j.id,'ecl'))));
$$;

DO $$ DECLARE definition TEXT; signature TEXT; BEGIN
 definition:=pg_get_functiondef('accounting.regular_original_origin(uuid,date)'::regprocedure);
 definition:=replace(definition,'AND j.id NOT IN(debit.journal_entry_id,completion.journal_entry_id)',
  'AND j.id NOT IN(debit.journal_entry_id,completion.journal_entry_id) AND NOT accounting.regular_application_journal_structurally_exact(j.id) AND NOT accounting.regular_elapsed_journal_structurally_exact(j.id)');
 EXECUTE definition;
 FOREACH signature IN ARRAY ARRAY['accounting.treasury_native_regular_application_origin(uuid)',
  'accounting.native_application_before_renewal_origin(uuid)','accounting.native_renewal_application_base_origin(uuid)'] LOOP
  IF to_regprocedure(signature) IS NOT NULL THEN
   definition:=pg_get_functiondef(signature::regprocedure);
   definition:=replace(definition,'t.collection_date>(anchor->>''anchor_date'')::date','t.collection_date>=(anchor->>''anchor_date'')::date');
   EXECUTE definition;
  END IF;
 END LOOP;
END $$;

-- Extend the single chronological recurrence. Settlement clears both carrying
-- components; the cash difference is separate from earned original EIR.
CREATE OR REPLACE FUNCTION accounting.regular_original_interval_gross(p_loan NUMERIC,p_accrued NUMERIC,p_rate NUMERIC,
 p_previous DATE,p_event DATE,p_maturity DATE)
RETURNS NUMERIC LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF p_loan<0 OR p_accrued<0 OR p_rate<=0 OR p_event<p_previous OR p_maturity IS NULL
  OR p_loan IS NULL OR p_accrued IS NULL OR p_rate IS NULL OR p_previous IS NULL OR p_event IS NULL THEN
  RAISE EXCEPTION 'Exact nonnegative original carrying components and chronological dates are required.' USING ERRCODE='22023';
 END IF;
 RETURN (p_loan+p_accrued)*power(1::numeric+p_rate,(least(p_event,p_maturity)-least(p_previous,p_maturity))::numeric);
END $$;

DO $$ DECLARE definition TEXT; old_clause TEXT; signature TEXT; BEGIN
 FOREACH signature IN ARRAY ARRAY['accounting.regular_original_cash_rollforward(uuid,date,uuid)',
  'accounting.native_regular_segment_cash_rollforward(uuid,date,uuid)'] LOOP
 IF to_regprocedure(signature) IS NULL THEN CONTINUE; END IF;
 definition:=pg_get_functiondef(signature::regprocedure);
 definition:=replace(definition,'previous_accrued NUMERIC;','previous_accrued NUMERIC; full_payoff BOOLEAN:=false;');
 definition:=replace(definition,'p_cutoff<=last_day OR p_cutoff>(anchor->>''contractual_due_date'')::date','p_cutoff<last_day');
 definition:=replace(definition,'p_cutoff<last_day OR p_cutoff>(anchor->>''contractual_due_date'')::date','p_cutoff<last_day');
 definition:=replace(definition,'event.collection_date<=(anchor->>''anchor_date'')::date','event.collection_date<(anchor->>''anchor_date'')::date');
 old_clause:='previous_loan:=loan_amount; previous_accrued:=accrued; prior_interest:=total_interest;';
 definition:=replace(definition,old_clause,
  'IF full_payoff THEN RETURN jsonb_build_object(''ready'',false,''blockers'',jsonb_build_array(''cash_after_full_payoff'')); END IF; full_payoff:=accounting.regular_transaction_full_payoff(event.id); '
  ||'IF event.collection_date>(anchor->>''contractual_due_date'')::date AND NOT full_payoff AND NOT accounting.regular_closed_term_review_exact(p_loan) THEN RETURN jsonb_build_object(''ready'',false,''blockers'',jsonb_build_array(''post_maturity_cash_treatment_required'')); END IF; '||old_clause);
 definition:=replace(definition,'(event.collection_date-last_day)::numeric',
  '(least(event.collection_date,(anchor->>''contractual_due_date'')::date)-least(last_day,(anchor->>''contractual_due_date'')::date))::numeric');
 definition:=replace(definition,'IF event.amount>gross THEN','IF event.amount>gross AND NOT full_payoff THEN');
 old_clause:='accrued:=before_accrued-credit_interest; loan_amount:=gross-event.amount-accrued;';
 IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Payoff recurrence predecessor changed.'; END IF;
 definition:=replace(definition,old_clause,old_clause||' IF full_payoff THEN credit_interest:=before_accrued; credit_loan:=before_loan; accrued:=0; loan_amount:=0; END IF;');
 old_clause:=$old$'accrued_interest_after',accrued::numeric(18,2)::text);$old$;
 definition:=replace(definition,old_clause,old_clause||
  ' IF full_payoff THEN measurement:=measurement||jsonb_build_object(''full_contractual_payoff'',true,''settlement_difference'',(event.amount-gross)::numeric(18,2)::text,''eir_end_date'',least(event.collection_date,(anchor->>''contractual_due_date'')::date)); END IF;');
 definition:=replace(definition,'RETURN jsonb_build_object(''ready'',true,''blockers'',''[]''::jsonb,''anchor'',anchor',
  'RETURN CASE WHEN full_payoff THEN jsonb_build_object(''settled_by_exact_payoff'',true) ELSE ''{}''::jsonb END||jsonb_build_object(''ready'',true,''blockers'',''[]''::jsonb,''anchor'',anchor');
 definition:=replace(definition,'(p_cutoff-last_day)::numeric',
  '(least(p_cutoff,(anchor->>''contractual_due_date'')::date)-least(last_day,(anchor->>''contractual_due_date'')::date))::numeric');
 definition:=replace(definition,
  'raw_gross:=(loan_amount+accrued)*power(1::numeric+rate,(least(event.collection_date,(anchor->>''contractual_due_date'')::date)-least(last_day,(anchor->>''contractual_due_date'')::date))::numeric);',
  'raw_gross:=accounting.regular_original_interval_gross(loan_amount,accrued,rate,last_day,event.collection_date,(anchor->>''contractual_due_date'')::date);');
 definition:=replace(definition,
  'raw_gross:=(loan_amount+accrued)*power(1::numeric+rate,(least(p_cutoff,(anchor->>''contractual_due_date'')::date)-least(last_day,(anchor->>''contractual_due_date'')::date))::numeric);',
  'raw_gross:=accounting.regular_original_interval_gross(loan_amount,accrued,rate,last_day,p_cutoff,(anchor->>''contractual_due_date'')::date);');
 EXECUTE definition;
 END LOOP;
END $$;

-- Paid status after an actual contractual completion must not change an older
-- as-of assessment. The existing source and dated cash guards still apply.
DO $$ DECLARE definition TEXT; signature TEXT; BEGIN
 FOREACH signature IN ARRAY ARRAY['accounting.loan_period_native_elapsed_assessment_candidate(uuid,uuid)',
  'accounting.loan_period_native_cash_assessment_candidate(uuid,uuid)',
  'accounting.loan_period_native_renewal_assessment_candidate(uuid,uuid)'] LOOP
  IF to_regprocedure(signature) IS NULL THEN CONTINUE; END IF;
  definition:=pg_get_functiondef(signature::regprocedure);
  definition:=replace(definition,'loan.status<>''active''',
   '(loan.status<>''active'' AND NOT(loan.status=''paid'' AND EXISTS(SELECT 1 FROM lending.collection_transactions paid WHERE paid.loan_id=p_loan AND accounting.regular_transaction_full_payoff(paid.id))))');
  IF signature LIKE '%native_cash%' OR signature LIKE '%native_renewal%' THEN
   definition:=replace(definition,'anchor.anchor_date>=period_row.end_date OR period_row.end_date>anchor.contractual_due_date',
    'anchor.anchor_date>period_row.end_date OR (period_row.end_date>anchor.contractual_due_date AND NOT accounting.regular_closed_term_review_exact(p_loan) AND NOT EXISTS(SELECT 1 FROM lending.collection_transactions paid WHERE paid.loan_id=p_loan AND paid.collection_date<=period_row.end_date AND accounting.regular_transaction_full_payoff(paid.id)))');
   definition:=replace(definition,'anchor.anchor_date>period_row.end_date OR period_row.end_date>anchor.contractual_due_date',
    'anchor.anchor_date>period_row.end_date OR (period_row.end_date>anchor.contractual_due_date AND NOT accounting.regular_closed_term_review_exact(p_loan) AND NOT EXISTS(SELECT 1 FROM lending.collection_transactions paid WHERE paid.loan_id=p_loan AND paid.collection_date<=period_row.end_date AND accounting.regular_transaction_full_payoff(paid.id)))');
   definition:=replace(definition,'days<=0','days<0');
   definition:=replace(definition,'IF contractual_pv<=0 OR gross_raw<=0 THEN',
    'IF (contractual_pv<=0 OR gross_raw<=0) AND NOT(contractual_pv=0 AND gross_raw=0 AND roll->>''settled_by_exact_payoff''=''true'') THEN');
   definition:=replace(definition,'RETURN jsonb_build_object(''ready'',cardinality(blockers)=0',
    'IF roll->>''settled_by_exact_payoff''=''true'' THEN snapshot:=snapshot||jsonb_build_object(''settled_by_exact_payoff'',true); END IF; RETURN jsonb_build_object(''ready'',cardinality(blockers)=0');
  END IF;
  EXECUTE definition;
 END LOOP;
END $$;

DO $$ BEGIN
 IF to_regprocedure('accounting.calculate_elapsed_assessment_before_settled_ecl(jsonb,jsonb,jsonb)') IS NULL THEN
  ALTER FUNCTION accounting.calculate_elapsed_assessment_ecl(JSONB,JSONB,JSONB) RENAME TO calculate_elapsed_assessment_before_settled_ecl;
 END IF;
END $$;
CREATE OR REPLACE FUNCTION accounting.calculate_elapsed_assessment_ecl(p_source JSONB,p_risk JSONB,p_scenarios JSONB)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE review_id TEXT;
BEGIN
 IF p_source->>'settled_by_exact_payoff' IS DISTINCT FROM 'true' THEN
  RETURN accounting.calculate_elapsed_assessment_before_settled_ecl(p_source,p_risk,p_scenarios);
 END IF;
 SELECT preparation.snapshot#>>'{measurement,payoff_review_id}' INTO review_id
 FROM accounting.treasury_application_postings posting
 JOIN accounting.treasury_application_preparations preparation ON preparation.id=posting.preparation_id
 WHERE posting.loan_id=(p_source#>>'{loan,id}')::uuid AND preparation.snapshot->>'accounting_policy_version'='treasury_regular_original_full_payoff_v1'
  AND (preparation.snapshot->>'posting_date')::date<=(p_source->>'cutoff_date')::date;
 IF review_id IS NULL OR (p_source->>'gross_carrying_amount')::numeric<>0 OR (p_source->>'contractual_pv_raw')::numeric<>0
  OR p_scenarios IS DISTINCT FROM '[]'::jsonb OR p_risk->>'as_of_date' IS DISTINCT FROM p_source->>'cutoff_date'
  OR p_risk->>'primary_evidence_basis' IS DISTINCT FROM 'exact_payoff' OR p_risk->>'evidence_reference' IS DISTINCT FROM review_id
  OR length(btrim(coalesce(p_risk->>'review_note','')))<20
  OR EXISTS(SELECT 1 FROM jsonb_object_keys(p_risk) key WHERE key NOT IN('as_of_date','primary_evidence_basis','evidence_reference','review_note')) THEN
  RAISE EXCEPTION 'Exact posted payoff and explicit settled-asset review are required for zero ECL.' USING ERRCODE='23514';
 END IF;
 RETURN jsonb_build_object('policy_version','regular_exact_payoff_zero_ecl_v1','as_of_date',p_source->'cutoff_date',
  'loss_horizon','settled','risk_review',p_risk,'forward_evidence','[]'::jsonb,'scenarios','[]'::jsonb,
  'original_daily_eir',p_source#>'{eir,daily_eir}','contractual_cash_flows',p_source->'contractual_cash_flows',
  'contractual_pv_raw',0,'gross_carrying_amount',0,'weighted_shortfall_raw',0,'ecl_amount',0,
  'prior_allowance',p_source->'prior_allowance','allowance_delta',-(p_source->>'prior_allowance')::numeric);
END $$;

CREATE OR REPLACE FUNCTION accounting.regular_payoff_candidate(p_application UUID)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE origin JSONB; snapshot JSONB; contract_reference TEXT;
BEGIN
 IF NOT accounting.regular_application_full_payoff(p_application) THEN
  RETURN jsonb_build_object('ready',false,'blockers',jsonb_build_array('exact_complete_contractual_payment_required'));
 END IF;
 origin:=accounting.regular_cash_application_origin(p_application);
 IF origin#>>'{native_origin,ready}' IS DISTINCT FROM 'true' OR origin#>>'{cash_rollforward,ready}' IS DISTINCT FROM 'true'
  OR origin#>>'{measurement,full_contractual_payoff}' IS DISTINCT FROM 'true' THEN
  RETURN jsonb_build_object('ready',false,'blockers',coalesce(origin#>'{cash_rollforward,blockers}',jsonb_build_array('exact_original_payoff_source_required')));
 END IF;
 contract_reference:=origin#>>'{registration,evidence_reference}';
 snapshot:=jsonb_build_object('policy_version','regular_contractual_payoff_review_v1','application_id',p_application,
  'contract_evidence_reference',contract_reference,'origin',origin);
 RETURN jsonb_build_object('ready',true,'blockers','[]'::jsonb,'source_digest',encode(sha256(convert_to(snapshot::text,'UTF8')),'hex'),
  'application_id',p_application,'treasury_account_id',origin#>'{application,account_id}',
  'book_id',origin#>'{native_origin,snapshot,book,id}',
  'contract_evidence_reference',contract_reference,'snapshot',snapshot,
  'amount',origin#>'{application,amount}','gross_carrying_before',origin#>'{measurement,gross_carrying_before}',
  'settlement_difference',origin#>'{measurement,settlement_difference}');
END $$;

CREATE OR REPLACE FUNCTION accounting.guard_regular_payoff_review()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF TG_OP<>'INSERT' OR current_setting('accounting.regular_payoff_review_write',true) IS DISTINCT FROM NEW.request_id::text THEN
  RAISE EXCEPTION 'Payoff treatment evidence is immutable and requires its protected review command.' USING ERRCODE='55000';
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS regular_payoff_review_guard ON accounting.regular_payoff_reviews;
CREATE TRIGGER regular_payoff_review_guard BEFORE INSERT OR UPDATE OR DELETE ON accounting.regular_payoff_reviews
FOR EACH ROW EXECUTE FUNCTION accounting.guard_regular_payoff_review();
DROP TRIGGER IF EXISTS regular_payoff_review_truncate_guard ON accounting.regular_payoff_reviews;
CREATE TRIGGER regular_payoff_review_truncate_guard BEFORE TRUNCATE ON accounting.regular_payoff_reviews
FOR EACH STATEMENT EXECUTE FUNCTION accounting.guard_regular_payoff_review();
DROP TRIGGER IF EXISTS regular_closed_term_review_guard ON accounting.regular_closed_term_reviews;
CREATE TRIGGER regular_closed_term_review_guard BEFORE INSERT OR UPDATE OR DELETE ON accounting.regular_closed_term_reviews
FOR EACH ROW EXECUTE FUNCTION accounting.guard_regular_payoff_review();
DROP TRIGGER IF EXISTS regular_closed_term_review_truncate_guard ON accounting.regular_closed_term_reviews;
CREATE TRIGGER regular_closed_term_review_truncate_guard BEFORE TRUNCATE ON accounting.regular_closed_term_reviews
FOR EACH STATEMENT EXECUTE FUNCTION accounting.guard_regular_payoff_review();

CREATE OR REPLACE FUNCTION accounting.record_regular_closed_term_review(p_application UUID,p_digest TEXT,p_request UUID,
 p_treatment TEXT,p_contract_reference TEXT,p_rationale TEXT,p_actor UUID)
RETURNS UUID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE wallet UUID; candidate JSONB; source JSONB; existing accounting.regular_closed_term_reviews%ROWTYPE;
 created UUID; old_setting TEXT; loan UUID;
BEGIN
 SELECT account_id INTO wallet FROM treasury.applications WHERE id=p_application;
 PERFORM accounting.require_treasury_gl_actor(p_actor,wallet,'treasury.view');
 PERFORM id FROM treasury.accounts WHERE id=wallet FOR UPDATE;
 PERFORM accounting.lock_elapsed_assessment_sources();
 LOCK TABLE accounting.regular_closed_term_reviews IN SHARE ROW EXCLUSIVE MODE;
 candidate:=accounting.regular_closed_term_candidate(p_application); loan:=(candidate->>'loan_id')::uuid;
 SELECT * INTO existing FROM accounting.regular_closed_term_reviews WHERE request_id=p_request OR loan_id=loan;
 IF FOUND THEN
  IF (existing.loan_id,existing.request_id,existing.source_digest,existing.treatment,existing.contract_evidence_reference,existing.review_rationale,existing.actor_user_id)
   IS DISTINCT FROM(loan,p_request,p_digest,p_treatment,p_contract_reference,btrim(p_rationale),p_actor) THEN
   RAISE EXCEPTION 'Closed-term review retry must match its retained evidence.' USING ERRCODE='55000'; END IF;
  RETURN existing.id;
 END IF;
 source:=accounting.regular_closed_term_source(loan);
 IF candidate->>'ready' IS DISTINCT FROM 'true' OR candidate->>'source_digest' IS DISTINCT FROM p_digest
  OR p_treatment IS DISTINCT FROM 'original_eir_through_maturity_no_extension'
  OR candidate->>'contract_evidence_reference' IS DISTINCT FROM p_contract_reference OR length(btrim(coalesce(p_rationale,'')))<20 THEN
  RAISE EXCEPTION 'Exact signed maturity and explicit original-term treatment evidence are required.' USING ERRCODE='55000'; END IF;
 old_setting:=current_setting('accounting.regular_payoff_review_write',true);
 PERFORM set_config('accounting.regular_payoff_review_write',p_request::text,true);
 INSERT INTO accounting.regular_closed_term_reviews(request_id,loan_id,source_digest,source_snapshot,treatment,
  contract_evidence_reference,review_rationale,actor_user_id)
 VALUES(p_request,loan,p_digest,source->'snapshot',p_treatment,p_contract_reference,btrim(p_rationale),p_actor) RETURNING id INTO created;
 PERFORM set_config('accounting.regular_payoff_review_write',coalesce(old_setting,''),true);
 RETURN created;
END $$;

CREATE OR REPLACE FUNCTION accounting.record_regular_payoff_review(p_application UUID,p_digest TEXT,p_request UUID,
 p_treatment TEXT,p_contract_reference TEXT,p_rationale TEXT,p_actor UUID)
RETURNS UUID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE wallet UUID; candidate JSONB; existing accounting.regular_payoff_reviews%ROWTYPE; created UUID; old_setting TEXT;
BEGIN
 SELECT account_id INTO wallet FROM treasury.applications WHERE id=p_application;
 PERFORM accounting.require_treasury_gl_actor(p_actor,wallet,'treasury.view');
 PERFORM id FROM treasury.accounts WHERE id=wallet FOR UPDATE;
 PERFORM accounting.lock_elapsed_assessment_sources();
 LOCK TABLE accounting.regular_payoff_reviews IN SHARE ROW EXCLUSIVE MODE;
 SELECT * INTO existing FROM accounting.regular_payoff_reviews WHERE request_id=p_request OR application_id=p_application;
 IF FOUND THEN
  IF (existing.application_id,existing.request_id,existing.source_digest,existing.treatment,existing.contract_evidence_reference,existing.review_rationale,existing.actor_user_id)
   IS DISTINCT FROM(p_application,p_request,p_digest,p_treatment,p_contract_reference,btrim(p_rationale),p_actor) THEN
   RAISE EXCEPTION 'Payoff review retry must match its retained evidence.' USING ERRCODE='55000'; END IF;
  RETURN existing.id;
 END IF;
 candidate:=accounting.regular_payoff_candidate(p_application);
 IF candidate->>'ready' IS DISTINCT FROM 'true' OR candidate->>'source_digest' IS DISTINCT FROM p_digest
  OR p_treatment IS DISTINCT FROM 'full_contractual_payoff_no_rebate'
  OR candidate->>'contract_evidence_reference' IS DISTINCT FROM p_contract_reference
  OR length(btrim(coalesce(p_rationale,'')))<20 THEN
  RAISE EXCEPTION 'Exact current contractual payoff, explicit no-rebate treatment and substantive evidence are required.' USING ERRCODE='55000';
 END IF;
 old_setting:=current_setting('accounting.regular_payoff_review_write',true);
 PERFORM set_config('accounting.regular_payoff_review_write',p_request::text,true);
 INSERT INTO accounting.regular_payoff_reviews(request_id,application_id,source_digest,source_snapshot,treatment,
  contract_evidence_reference,review_rationale,actor_user_id)
 VALUES(p_request,p_application,p_digest,candidate->'snapshot',p_treatment,p_contract_reference,btrim(p_rationale),p_actor) RETURNING id INTO created;
 PERFORM set_config('accounting.regular_payoff_review_write',coalesce(old_setting,''),true);
 RETURN created;
END $$;

DO $$ BEGIN
 IF to_regprocedure('accounting.treasury_regular_application_before_payoff_origin(uuid)') IS NULL THEN
  ALTER FUNCTION accounting.treasury_regular_application_origin(UUID) RENAME TO treasury_regular_application_before_payoff_origin;
 END IF;
 IF to_regprocedure('accounting.treasury_regular_application_before_payoff_coordinates(uuid)') IS NULL THEN
  ALTER FUNCTION accounting.treasury_regular_application_coordinates(UUID) RENAME TO treasury_regular_application_before_payoff_coordinates;
 END IF;
END $$;

CREATE OR REPLACE FUNCTION accounting.treasury_regular_application_origin(p_application UUID)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE origin JSONB; candidate JSONB; review accounting.regular_payoff_reviews%ROWTYPE; closed_review accounting.regular_closed_term_reviews%ROWTYPE;
BEGIN
 IF NOT accounting.regular_application_full_payoff(p_application) THEN
  IF EXISTS(SELECT 1 FROM treasury.applications a JOIN lending.collection_transactions t ON t.id::text=a.source_result->'transaction_ids'->>0
   JOIN lending.loans loan ON loan.id=t.loan_id JOIN treasury.loan_payouts payout ON payout.loan_id=loan.id AND payout.status='completed'
    AND (payout.source_kind='first_loan' OR (payout.source_kind='renewal' AND accounting.regular_cash_has_renewal_lineage(loan.id)))
   WHERE a.id=p_application AND t.collection_date>loan.due_date) THEN
   origin:=accounting.regular_cash_application_origin(p_application);
   SELECT * INTO closed_review FROM accounting.regular_closed_term_reviews WHERE loan_id=(origin#>>'{transaction,loan_id}')::uuid;
   IF closed_review.id IS NOT NULL AND accounting.regular_closed_term_review_exact(closed_review.loan_id) AND origin->'measurement'<>'null'::jsonb THEN
    origin:=jsonb_set(origin,'{measurement}',(origin->'measurement')||jsonb_build_object('closed_term_review_id',closed_review.id,
     'closed_term_treatment',closed_review.treatment,'closed_term_rationale',closed_review.review_rationale));
   END IF;
   RETURN origin;
  END IF;
  RETURN accounting.treasury_regular_application_before_payoff_origin(p_application);
 END IF;
 candidate:=accounting.regular_payoff_candidate(p_application); origin:=candidate#>'{snapshot,origin}';
 SELECT * INTO review FROM accounting.regular_payoff_reviews WHERE application_id=p_application;
 IF review.id IS NOT NULL AND candidate->>'source_digest'=review.source_digest AND candidate->'snapshot'=review.source_snapshot THEN
  origin:=jsonb_set(origin,'{measurement}',(origin->'measurement')||jsonb_build_object('payoff_review_id',review.id,
   'payoff_treatment',review.treatment,'contract_evidence_reference',review.contract_evidence_reference,'payoff_review_rationale',review.review_rationale));
 END IF;
 RETURN origin;
END $$;

DO $$ DECLARE definition TEXT; signature TEXT; BEGIN
 FOREACH signature IN ARRAY ARRAY['accounting.treasury_chronological_regular_application_coordinates(uuid)',
  'accounting.native_renewal_application_coordinates(uuid)'] LOOP
 IF to_regprocedure(signature) IS NULL THEN CONTINUE; END IF;
 definition:=pg_get_functiondef(signature::regprocedure);
 definition:=replace(definition,'OR t.collection_date>(anchor->>''contractual_due_date'')::date',
  'OR (t.collection_date>(anchor->>''contractual_due_date'')::date AND measured->>''closed_term_review_id'' IS NULL)');
 EXECUTE definition;
 END LOOP;
END $$;

DO $$ DECLARE definition TEXT; old_clause TEXT; signature TEXT; BEGIN
 FOREACH signature IN ARRAY ARRAY['accounting.treasury_chronological_regular_application_coordinates(uuid)',
  'accounting.native_renewal_application_coordinates(uuid)'] LOOP
 IF to_regprocedure(signature) IS NULL THEN CONTINUE; END IF;
 definition:=pg_get_functiondef(signature::regprocedure);
 IF signature LIKE '%native_renewal%' THEN
  definition:=replace(definition,'accounting.native_renewal_application_coordinates(', 'accounting.treasury_payoff_renewal_application_coordinates(');
 ELSE
  definition:=replace(definition,'accounting.treasury_chronological_regular_application_coordinates(', 'accounting.treasury_payoff_regular_application_coordinates(');
 END IF;
 definition:=replace(definition,'t.collection_date>(anchor->>''contractual_due_date'')::date','false');
 definition:=replace(definition,'OR a.amount>(measured->>''gross_carrying_before'')::numeric',
  'OR measured->>''payoff_review_id'' IS NULL OR measured->>''full_contractual_payoff'' IS DISTINCT FROM ''true''');
 old_clause:=$old$(50,'collection_loan_component_credit','1100',0::numeric,credit_principal))$old$;
 IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Payoff journal coordinate predecessor changed.'; END IF;
 definition:=replace(definition,old_clause,$new$(50,'collection_loan_component_credit','1100',0::numeric,credit_principal),
  (60,'settlement_gain','4030',0::numeric,greatest((measured->>'settlement_difference')::numeric,0)),
  (70,'settlement_loss','5020',greatest(-(measured->>'settlement_difference')::numeric,0),0::numeric))$new$);
 definition:=replace(definition,'NOT BETWEEN 2 AND 5','NOT BETWEEN 2 AND 6');
 definition:=replace(definition,'''treasury_regular_original_chronological_cash_v1''','''treasury_regular_original_full_payoff_v1''');
 definition:=replace(definition,'''treasury_regular_renewal_chronological_cash_v1''','''treasury_regular_original_full_payoff_v1''');
 definition:=replace(definition,'anchor:=origin->''anchor'';',
  'IF EXISTS(SELECT 1 FROM (VALUES(''4030'',''regular_settlement_gain'',''income'',''credit''),(''5020'',''regular_settlement_loss'',''expense'',''debit'')) x(code,key,kind,normal) WHERE NOT EXISTS(SELECT 1 FROM accounting.accounts ac WHERE (ac.code,ac.system_key,ac.account_type,ac.normal_balance)=(x.code,x.key,x.kind,x.normal) AND ac.is_posting AND ac.is_active)) THEN RAISE EXCEPTION ''Exact settlement account definitions are required.'' USING ERRCODE=''55000''; END IF; anchor:=origin->''anchor'';');
 EXECUTE definition;
 END LOOP;
END $$;

CREATE OR REPLACE FUNCTION accounting.treasury_regular_application_coordinates(p_application UUID)
RETURNS JSONB LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE loan UUID; renewed BOOLEAN;
BEGIN
 SELECT t.loan_id INTO loan FROM treasury.applications a JOIN lending.collection_transactions t
  ON t.id::text=a.source_result->'transaction_ids'->>0 WHERE a.id=p_application;
 renewed:=accounting.regular_cash_has_renewal_lineage(loan);
 IF accounting.regular_application_full_payoff(p_application) THEN
  IF renewed THEN RETURN accounting.treasury_payoff_renewal_application_coordinates(p_application); END IF;
  RETURN accounting.treasury_payoff_regular_application_coordinates(p_application);
 END IF;
 IF EXISTS(SELECT 1 FROM treasury.applications a JOIN lending.collection_transactions t ON t.id::text=a.source_result->'transaction_ids'->>0
  JOIN lending.loans l ON l.id=t.loan_id JOIN treasury.loan_payouts payout ON payout.loan_id=l.id AND payout.status='completed'
   AND (payout.source_kind='first_loan' OR (payout.source_kind='renewal' AND renewed))
  WHERE a.id=p_application AND t.collection_date>l.due_date) THEN
  IF renewed THEN RETURN accounting.native_renewal_application_coordinates(p_application); END IF;
  RETURN accounting.treasury_chronological_regular_application_coordinates(p_application);
 END IF;
 RETURN accounting.treasury_regular_application_before_payoff_coordinates(p_application);
END $$;

DO $$ DECLARE definition TEXT; signature TEXT; BEGIN
 FOREACH signature IN ARRAY ARRAY['accounting.regular_application_prefix_admitted(uuid)','accounting.assert_regular_application_committed()'] LOOP
  definition:=pg_get_functiondef(signature::regprocedure);
  definition:=replace(definition,'''treasury_regular_original_chronological_cash_v1''',
   '''treasury_regular_original_chronological_cash_v1'',''treasury_regular_original_full_payoff_v1''');
  EXECUTE definition;
 END LOOP;
END $$;

DO $$ DECLARE item RECORD; role_name TEXT; BEGIN
 FOR item IN SELECT p.oid::regprocedure signature FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
 WHERE n.nspname='accounting' AND (p.proname LIKE '%payoff%' OR p.proname LIKE '%closed_term%' OR p.proname LIKE 'regular_cash_%' OR p.proname IN('treasury_regular_application_origin','treasury_regular_application_coordinates',
  'regular_original_interval_gross','regular_application_journal_structurally_exact','regular_elapsed_journal_structurally_exact',
  'calculate_elapsed_assessment_ecl','calculate_elapsed_assessment_before_settled_ecl')) LOOP
  EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC',item.signature);
  FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
   IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN EXECUTE format('REVOKE ALL ON FUNCTION %s FROM %I',item.signature,role_name); END IF;
  END LOOP;
 END LOOP;
 REVOKE ALL ON accounting.regular_payoff_reviews FROM PUBLIC;
 REVOKE ALL ON accounting.regular_closed_term_reviews FROM PUBLIC;
 FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
   EXECUTE format('REVOKE ALL ON accounting.regular_payoff_reviews FROM %I',role_name);
   EXECUTE format('REVOKE ALL ON accounting.regular_closed_term_reviews FROM %I',role_name);
  END IF;
 END LOOP;
END $$;

COMMIT;
