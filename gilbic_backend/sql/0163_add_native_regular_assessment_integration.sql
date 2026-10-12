BEGIN;

CREATE OR REPLACE FUNCTION accounting.native_percentage_tax_source_exact(p_transaction UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT EXISTS(SELECT 1 FROM lending.collection_transactions t
  JOIN accounting.treasury_application_posting_status a ON a.transaction_id=t.id
  JOIN accounting.treasury_application_preparations prepared ON prepared.id=a.preparation_id
  JOIN accounting.treasury_receipt_posting_status r ON r.receipt_id=a.receipt_id
  WHERE t.id=p_transaction AND NOT t.is_voided AND t.entry_type IN('payment','advance') AND t.amount>0
   AND t.funding_source='treasury_receipt' AND a.loan_id=t.loan_id AND prepared.snapshot->>'client_id'=t.client_id::text
   AND a.amount=t.amount AND a.posting_date=t.collection_date AND a.exact_posted AND NOT a.correction_pending
   AND r.exact_posted AND NOT r.correction_pending);
$$;
REVOKE ALL ON FUNCTION accounting.native_percentage_tax_source_exact(UUID) FROM PUBLIC;
-- Preserve every existing tax allocation, rule, authority and retry check.
-- Only exact current Treasury source claims extend the original admission gate.
DO $$ DECLARE definition TEXT; old_clause TEXT; r TEXT; BEGIN
 definition:=pg_get_functiondef('accounting.record_v1_percentage_tax_evidence(uuid,uuid,uuid,uuid,numeric,numeric,numeric,numeric,text,text,text,uuid)'::regprocedure);
 old_clause:=$old$    ) THEN
        RAISE EXCEPTION 'Percentage-tax evidence requires the source cash transaction to have completed its protected lending accounting posting first.';$old$;
 IF position('accounting.native_percentage_tax_source_exact(' IN definition)=0 THEN
  IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Percentage tax source admission predecessor changed.'; END IF;
  definition:=replace(definition,old_clause,$new$    ) AND NOT accounting.native_percentage_tax_source_exact(transaction_row.id) THEN
        RAISE EXCEPTION 'Percentage-tax evidence requires the source cash transaction to have completed its protected lending accounting posting first.';$new$);
  EXECUTE definition;
 END IF;
 definition:=pg_get_viewdef('accounting.v1_tax_percentage_readiness'::regclass,true);
 old_clause:='SELECT seven_by_seven_journal_postings.transaction_id
            FROM accounting.seven_by_seven_journal_postings';
 IF position('accounting.native_percentage_tax_source_exact(' IN definition)=0 THEN
  -- pg_get_viewdef indentation varies across PostgreSQL major versions.
  IF definition !~ 'FROM accounting\.seven_by_seven_journal_postings' THEN RAISE EXCEPTION 'Percentage tax source projection predecessor changed.'; END IF;
  definition:=regexp_replace(definition,'FROM accounting\.seven_by_seven_journal_postings',
   'FROM accounting.seven_by_seven_journal_postings UNION SELECT native.transaction_id FROM accounting.treasury_application_postings native WHERE accounting.native_percentage_tax_source_exact(native.transaction_id)');
  EXECUTE 'CREATE OR REPLACE VIEW accounting.v1_tax_percentage_readiness AS '||definition;
 END IF;
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN EXECUTE format('REVOKE ALL ON FUNCTION accounting.native_percentage_tax_source_exact(UUID) FROM %I',r); END IF;
 END LOOP;
END $$;

DO $$ DECLARE definition TEXT; old_clause TEXT; item RECORD; BEGIN
 old_clause:=$old$                OR EXISTS (
                    SELECT 1
                    FROM accounting.seven_by_seven_journal_postings posted
                    WHERE posted.transaction_id = transaction_row.id
                )$old$;
 FOR item IN SELECT oid FROM pg_proc WHERE pronamespace='accounting'::regnamespace
  AND proname IN('prepare_v1_tax_liability_journal','post_v1_tax_liability_journal') LOOP
  definition:=pg_get_functiondef(item.oid);
  IF position('accounting.native_percentage_tax_source_exact(' IN definition)=0 THEN
   IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Tax liability protected source gate predecessor changed.'; END IF;
   definition:=replace(definition,old_clause,old_clause||E'\n                OR accounting.native_percentage_tax_source_exact(transaction_row.id)');
   EXECUTE definition;
  END IF;
 END LOOP;
END $$;

-- A protected tax expense does not remeasure the loan asset. Certify the exact
-- separate tax claim before excluding it from loan measurement provenance;
-- labels alone, unknown journals and altered chart semantics never qualify.
CREATE OR REPLACE FUNCTION accounting.native_loan_ancillary_tax_exact(p_journal UUID,p_loan UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT EXISTS(SELECT 1 FROM accounting.v1_tax_liability_preparations p
  JOIN accounting.v1_tax_liability_postings a ON a.preparation_id=p.id AND a.journal_entry_id=p_journal
  JOIN accounting.legacy_tax_evidence_sources e ON e.tax_type=p.tax_type AND e.evidence_id=p.evidence_id
  JOIN accounting.accounts expense ON expense.id=p.expense_account_id
  JOIN accounting.accounts payable ON payable.id=p.tax_payable_account_id
  WHERE p.journal_entry_id=p_journal AND e.loan_id=p_loan
   AND accounting.legacy_tax_liability_posted_exact(e.tax_type,e.evidence_id)
   AND (expense.code,expense.system_key,expense.account_type,expense.normal_balance)=
    (CASE e.tax_type WHEN 'documentary_stamp_tax' THEN '5310' ELSE '5300' END,
     CASE e.tax_type WHEN 'documentary_stamp_tax' THEN 'documentary_stamp_tax_expense' ELSE 'percentage_tax_lending_expense' END,
     'expense','debit') AND expense.is_posting
   AND (payable.code,payable.system_key,payable.account_type,payable.normal_balance)=('2100','tax_payables','liability','credit')
   AND payable.is_posting);
$$;
REVOKE ALL ON FUNCTION accounting.native_loan_ancillary_tax_exact(UUID,UUID) FROM PUBLIC;
DO $$ DECLARE definition TEXT; old_clause TEXT; r TEXT; BEGIN
 definition:=pg_get_functiondef('accounting.regular_original_origin(uuid,date)'::regprocedure);
 old_clause:='AND j.id NOT IN(debit.journal_entry_id,completion.journal_entry_id)) THEN';
 IF position('accounting.native_loan_ancillary_tax_exact(' IN definition)=0 THEN
  IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Native original unknown-journal predecessor changed.'; END IF;
  definition:=replace(definition,old_clause,
   'AND j.id NOT IN(debit.journal_entry_id,completion.journal_entry_id) AND NOT accounting.native_loan_ancillary_tax_exact(j.id,p_loan)) THEN');
  EXECUTE definition;
 END IF;
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE format('REVOKE ALL ON FUNCTION accounting.native_loan_ancillary_tax_exact(UUID,UUID) FROM %I',r);
  END IF;
 END LOOP;
END $$;

-- 0140 added an explicit paper-scan default to evidence already retained by
-- older payout reviews. Interpret only that absent historical member as its
-- migration-defined default; never rewrite the immutable reviewed snapshot.
CREATE OR REPLACE FUNCTION accounting.loan_payout_origin_matches(p_current JSONB,p_retained JSONB)
RETURNS BOOLEAN LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF jsonb_typeof(p_retained->'office_evidence')='object'
  AND NOT (p_retained->'office_evidence' ? 'capture_method')
  AND p_current#>>'{office_evidence,capture_method}'='paper_scan' THEN
  p_current:=p_current#-'{office_evidence,capture_method}';
 END IF;
 RETURN p_current IS NOT DISTINCT FROM p_retained;
END $$;

DO $$ DECLARE definition TEXT; old_clause TEXT; BEGIN
 definition:=pg_get_viewdef('accounting.loan_payout_accounting_posting_proof'::regclass,true);
 old_clause:='accounting.loan_payout_accounting_origin(a.payout_id, a.stage) IS DISTINCT FROM (p.snapshot -> ''origin''::text)';
 IF position('accounting.loan_payout_origin_matches(' IN definition)=0 THEN
  IF position(old_clause IN definition)=0 THEN
   RAISE EXCEPTION 'Native payout retained-origin comparison predecessor changed.';
  END IF;
  definition:=replace(definition,old_clause,
   'NOT accounting.loan_payout_origin_matches(accounting.loan_payout_accounting_origin(a.payout_id, a.stage), p.snapshot -> ''origin''::text)');
  EXECUTE 'CREATE OR REPLACE VIEW accounting.loan_payout_accounting_posting_proof AS '||definition;
 END IF;
END $$;

-- Native first-loan provenance feeds the existing original-contract measurement.
-- Keep the legacy implementations and their returned JSON exactly unchanged:
-- historical preparations and confirmed source digests remain authoritative.
ALTER TABLE lending.loan_contract_collection_activation_events
 ADD COLUMN IF NOT EXISTS reconciliation_metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

-- Read-only eligibility exposes the explicit activation action for a captured
-- original release. It never repairs a flag, materializes a schedule or posts.
CREATE OR REPLACE FUNCTION lending.native_original_activation_ready(p_loan UUID)
RETURNS BOOLEAN LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE state lending.loan_collection_state%ROWTYPE; origin JSONB; schedule UUID;
 total NUMERIC; settings JSONB; assessment RECORD;
BEGIN
 SELECT * INTO state FROM lending.loan_collection_state WHERE loan_id=p_loan;
 IF state.loan_id IS NULL OR state.is_reconciled OR state.state_version<>0
  OR EXISTS(SELECT 1 FROM lending.collection_transactions WHERE loan_id=p_loan)
  OR EXISTS(SELECT 1 FROM lending.loan_contract_collection_activation_events WHERE loan_id=p_loan)
  OR NOT EXISTS(SELECT 1 FROM treasury.loan_payouts WHERE loan_id=p_loan AND source_kind='first_loan' AND status='completed') THEN RETURN false; END IF;
 origin:=accounting.regular_original_origin(p_loan,(statement_timestamp() AT TIME ZONE 'Asia/Manila')::date);
 IF origin->>'ready' IS DISTINCT FROM 'true' THEN RETURN false; END IF;
 schedule:=(origin#>>'{anchor,schedule_id}')::uuid;
 SELECT sum(contractual_amount) INTO total FROM lending.loan_contract_installments WHERE schedule_id=schedule;
 SELECT lt.settings INTO settings FROM lending.loans l JOIN lending.loan_types lt ON lt.id=l.loan_type_id WHERE l.id=p_loan AND l.status='active';
 SELECT * INTO assessment FROM accounting.loan_contract_dpd_assessment WHERE loan_id=p_loan;
 IF total IS NULL OR state.remaining_balance<>total OR assessment.schedule_id IS DISTINCT FROM schedule
  OR assessment.dpd_data_status IS DISTINCT FROM 'ready' OR assessment.contractual_schedule_total<>total OR assessment.allocated_schedule_total<>0
  OR assessment.automatic_default_label_written OR assessment.ecl_included OR assessment.ecl_amount IS NOT NULL OR assessment.ready_to_post
  OR lower(coalesce(settings->>'mobile_collections_enabled','')) NOT IN('true','1','yes','on')
  OR settings->>'mobile_balance_mode' IS DISTINCT FROM 'direct_remaining_balance'
  OR NOT EXISTS(SELECT 1 FROM lending.loan_schedule_operational_state WHERE schedule_id=schedule AND operational_version=0)
  OR EXISTS(SELECT 1 FROM lending.loan_installment_payment_allocations a JOIN lending.loan_contract_installments i ON i.id=a.installment_id WHERE i.schedule_id=schedule) THEN RETURN false; END IF;
 RETURN true;
END $$;

CREATE OR REPLACE FUNCTION lending.activate_reconciled_native_original(p_loan UUID,p_actor UUID,p_note TEXT)
RETURNS BOOLEAN LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE state lending.loan_collection_state%ROWTYPE; origin JSONB; schedule UUID; total NUMERIC;
 settings JSONB; assessment RECORD; metadata JSONB;
BEGIN
 -- Ordinary legacy/unreviewed balances retain the existing explicit blocker.
 IF NOT EXISTS(SELECT 1 FROM treasury.loan_payouts WHERE loan_id=p_loan AND source_kind='first_loan' AND status='completed') THEN RETURN false; END IF;
 PERFORM 1 FROM core.users u JOIN core.user_roles ur ON ur.user_id=u.id
 JOIN core.roles r ON r.id=ur.role_id JOIN core.role_permissions rp ON rp.role_id=r.id
 WHERE u.id=p_actor AND u.status='active' AND r.code='management' AND rp.permission_code='lending.contract_collection.activate'
 FOR SHARE OF u,ur,r,rp;
 IF NOT FOUND THEN RAISE EXCEPTION 'Active Management activation authority is required.' USING ERRCODE='42501'; END IF;
 PERFORM id FROM lending.loans WHERE id=p_loan FOR UPDATE;
 SELECT * INTO state FROM lending.loan_collection_state WHERE loan_id=p_loan FOR UPDATE;
 IF state.loan_id IS NULL OR state.is_reconciled OR state.state_version<>0
  OR EXISTS(SELECT 1 FROM lending.collection_transactions WHERE loan_id=p_loan)
  OR EXISTS(SELECT 1 FROM lending.loan_contract_collection_activation_events WHERE loan_id=p_loan)
  OR length(btrim(coalesce(p_note,'')))<10 THEN
  RAISE EXCEPTION 'Only an untouched original native collection state may be reconciled on activation.' USING ERRCODE='55000';
 END IF;
 PERFORM accounting.lock_elapsed_assessment_sources();
 origin:=accounting.regular_original_origin(p_loan,(clock_timestamp() AT TIME ZONE 'Asia/Manila')::date);
 IF origin->>'ready' IS DISTINCT FROM 'true' THEN
  RAISE EXCEPTION 'Exact protected original native release is required for collection-state reconciliation.' USING ERRCODE='55000';
 END IF;
 schedule:=(origin#>>'{anchor,schedule_id}')::uuid;
 PERFORM schedule_id FROM lending.loan_schedule_operational_state WHERE schedule_id=schedule FOR UPDATE;
 IF NOT lending.native_original_activation_ready(p_loan) THEN
  RAISE EXCEPTION 'Exact untouched original state is no longer available for reconciliation.' USING ERRCODE='55000';
 END IF;
 SELECT sum(contractual_amount) INTO total FROM lending.loan_contract_installments WHERE schedule_id=schedule;
 SELECT lt.settings INTO settings FROM lending.loans l JOIN lending.loan_types lt ON lt.id=l.loan_type_id WHERE l.id=p_loan AND l.status='active';
 SELECT * INTO assessment FROM accounting.loan_contract_dpd_assessment WHERE loan_id=p_loan;
 IF total IS NULL OR state.remaining_balance<>total OR assessment.schedule_id IS DISTINCT FROM schedule
  OR assessment.dpd_data_status IS DISTINCT FROM 'ready' OR assessment.contractual_schedule_total<>total OR assessment.allocated_schedule_total<>0
  OR assessment.automatic_default_label_written OR assessment.ecl_included OR assessment.ecl_amount IS NOT NULL OR assessment.ready_to_post
  OR lower(coalesce(settings->>'mobile_collections_enabled','')) NOT IN('true','1','yes','on')
  OR settings->>'mobile_balance_mode' IS DISTINCT FROM 'direct_remaining_balance'
  OR EXISTS(SELECT 1 FROM lending.loan_installment_payment_allocations a JOIN lending.loan_contract_installments i ON i.id=a.installment_id WHERE i.schedule_id=schedule) THEN
  RAISE EXCEPTION 'Original remaining balance, signed schedule and operational readiness must reconcile exactly.' USING ERRCODE='55000';
 END IF;
 metadata:=jsonb_build_object('policy_version','native_original_collection_reconciliation_v1','before',to_jsonb(state),
  'after_is_reconciled',true,'unchanged_remaining_balance',total,'origin_source_digest',origin->>'source_digest',
  'schedule_id',schedule,'actor_user_id',p_actor,'reconciled_at',clock_timestamp(),
  'schedule_operational_state',(SELECT to_jsonb(s) FROM lending.loan_schedule_operational_state s WHERE s.schedule_id=schedule));
 UPDATE lending.loan_collection_state SET is_reconciled=true WHERE loan_id=p_loan;
 INSERT INTO lending.loan_contract_collection_activation_events(loan_id,schedule_id,event_action,activation_note,acted_by_user_id,reconciliation_metadata)
 VALUES(p_loan,schedule,'activate',p_note,p_actor,metadata);
 RETURN true;
END $$;
REVOKE ALL ON FUNCTION lending.activate_reconciled_native_original(UUID,UUID,TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION lending.native_original_activation_ready(UUID) FROM PUBLIC;
DO $$ DECLARE r TEXT; BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE format('REVOKE ALL ON FUNCTION lending.activate_reconciled_native_original(UUID,UUID,TEXT) FROM %I',r);
   EXECUTE format('REVOKE ALL ON FUNCTION lending.native_original_activation_ready(UUID) FROM %I',r);
  END IF;
 END LOOP;
END $$;

DO $$ BEGIN
 IF to_regprocedure('accounting.loan_period_legacy_elapsed_assessment_candidate(uuid,uuid)') IS NULL THEN
  ALTER FUNCTION accounting.loan_period_elapsed_assessment_candidate(UUID,UUID)
   RENAME TO loan_period_legacy_elapsed_assessment_candidate;
 END IF;
 IF to_regprocedure('accounting.treasury_legacy_regular_application_origin(uuid)') IS NULL THEN
  ALTER FUNCTION accounting.treasury_regular_application_origin(UUID)
   RENAME TO treasury_legacy_regular_application_origin;
 END IF;
 IF to_regprocedure('accounting.treasury_legacy_regular_application_coordinates(uuid)') IS NULL THEN
  ALTER FUNCTION accounting.treasury_regular_application_coordinates(UUID)
   RENAME TO treasury_legacy_regular_application_coordinates;
 END IF;
 IF to_regprocedure('accounting.lock_elapsed_assessment_before_native_sources()') IS NULL THEN
  ALTER FUNCTION accounting.lock_elapsed_assessment_sources()
   RENAME TO lock_elapsed_assessment_before_native_sources;
 END IF;
END $$;

-- Derive the native specialization from the preserved calculation, changing
-- only origin admission and its journal lineage. Refuse an unknown predecessor
-- instead of silently replacing measurement, prefix, or allocation semantics.
DO $$ DECLARE definition TEXT; old_clause TEXT; replacement TEXT; BEGIN
 definition:=pg_get_functiondef('accounting.loan_period_legacy_elapsed_assessment_candidate(uuid,uuid)'::regprocedure);
 definition:=replace(definition,'accounting.loan_period_legacy_elapsed_assessment_candidate(',
  'accounting.loan_period_native_elapsed_assessment_candidate(');
 old_clause:='loan lending.loans%ROWTYPE; anchor RECORD; prior RECORD;';
 IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Native assessment requires the known original-contract measurement.'; END IF;
 definition:=replace(definition,old_clause,old_clause||' native_origin JSONB;');
 old_clause:=$old$ IF 1<>(SELECT count(*) FROM accounting.greenfield_regular_eir_anchor_readiness WHERE loan_id=p_loan) THEN
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
 END IF;$old$;
 replacement:=$new$ native_origin:=accounting.regular_original_origin(p_loan,period_row.end_date);
 IF native_origin->>'ready' IS DISTINCT FROM 'true' THEN
  RETURN jsonb_build_object('ready',false,'blockers',to_jsonb(blockers)||coalesce(native_origin->'blockers','[]'::jsonb));
 END IF;
 SELECT * INTO anchor FROM jsonb_to_record(native_origin->'anchor') AS x(
  loan_id UUID,client_id UUID,posting_id UUID,disbursement_event_id UUID,journal_entry_id UUID,
  anchor_date DATE,initial_gross_carrying_amount NUMERIC,schedule_id UUID,schedule_version INTEGER,
  contractual_due_date DATE,daily_eir NUMERIC,anchor_policy_version TEXT,anchor_source_key TEXT);
 IF loan.due_date IS DISTINCT FROM anchor.contractual_due_date THEN
  blockers:=array_append(blockers,'protected_regular_anchor_not_exact');
 END IF;$new$;
 IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Native assessment origin admission predecessor changed.'; END IF;
 definition:=replace(definition,old_clause,replacement);
 old_clause:='allowed_entries:=ARRAY[anchor.journal_entry_id]||own_entries;';
 IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Native assessment journal lineage predecessor changed.'; END IF;
 definition:=replace(definition,old_clause,
  'allowed_entries:=ARRAY[anchor.journal_entry_id,(native_origin#>>''{snapshot,debit_proof,journal_entry_id}'')::uuid]||own_entries;');
 -- The native helper certifies origin-day journals. The elapsed caller must
 -- also reject unknown later loan-dimensional activity, including offsetting
 -- transit lines or an account whose code has subsequently changed.
 old_clause:='AND l.loan_id=p_loan AND a.code IN(''1100'',''1110'',''1120'',''1190'')';
 IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Native assessment unknown-control predecessor changed.'; END IF;
 definition:=replace(definition,old_clause,'AND l.loan_id=p_loan AND NOT accounting.native_loan_ancillary_tax_exact(j.id,p_loan)');
 old_clause:='AND EXISTS(SELECT 1 FROM accounting.journal_lines l WHERE l.journal_entry_id=j.id AND l.loan_id=p_loan);';
 IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Native assessment ledger predecessor changed.'; END IF;
 definition:=replace(definition,old_clause,
  'AND EXISTS(SELECT 1 FROM accounting.journal_lines l WHERE l.journal_entry_id=j.id AND l.loan_id=p_loan) AND NOT accounting.native_loan_ancillary_tax_exact(j.id,p_loan);');
 old_clause:=$old$'incremental_interest',interest-previous_interest,'prior_cutoff',previous_cutoff));$old$;
 IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Native assessment retained-source predecessor changed.'; END IF;
 definition:=replace(definition,old_clause,old_clause||E'\n snapshot:=snapshot||jsonb_build_object(''native_origin'',native_origin);');
 EXECUTE definition;
END $$;

CREATE OR REPLACE FUNCTION accounting.loan_period_elapsed_assessment_candidate(p_period UUID,p_loan UUID)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 -- The native branch must handle ambiguous dual origins itself. A successful
 -- legacy preview must never hide a retained noncancelled Treasury payout.
 IF EXISTS(SELECT 1 FROM treasury.loan_payouts WHERE loan_id=p_loan AND source_kind='first_loan' AND status<>'cancelled') THEN
  RETURN accounting.loan_period_native_elapsed_assessment_candidate(p_period,p_loan);
 END IF;
 RETURN accounting.loan_period_legacy_elapsed_assessment_candidate(p_period,p_loan);
END $$;

DO $$ DECLARE definition TEXT; old_clause TEXT; BEGIN
 definition:=pg_get_functiondef('accounting.treasury_legacy_regular_application_origin(uuid)'::regprocedure);
 definition:=replace(definition,'accounting.treasury_legacy_regular_application_origin(',
  'accounting.treasury_native_regular_application_origin(');
 old_clause:='loan lending.loans%ROWTYPE; anchor JSONB; prefixes JSONB; ledger JSONB; history JSONB; measured JSONB;';
 IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Native application measurement predecessor changed.'; END IF;
 definition:=replace(definition,old_clause,old_clause||' native_origin JSONB;');
 old_clause:=$old$ SELECT to_jsonb(x)-ARRAY['client_name','client_code','loan_number'] INTO anchor
 FROM accounting.greenfield_regular_eir_anchor_readiness x WHERE x.loan_id=t.loan_id;
 IF (SELECT count(*) FROM accounting.greenfield_regular_eir_anchor_readiness WHERE loan_id=t.loan_id)<>1 THEN anchor:=NULL; END IF;$old$;
 IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Native application origin predecessor changed.'; END IF;
 definition:=replace(definition,old_clause,
  ' native_origin:=accounting.regular_original_origin(t.loan_id,t.collection_date); anchor:=native_origin->''anchor'';');
 old_clause:=$old$'contract_schedule_count',(SELECT count(*) FROM lending.loan_contract_schedules WHERE loan_id=t.loan_id));$old$;
 IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Native application retained-source predecessor changed.'; END IF;
 definition:=replace(definition,old_clause,
  $new$'contract_schedule_count',(SELECT count(*) FROM lending.loan_contract_schedules WHERE loan_id=t.loan_id),'native_origin',native_origin);$new$);
 old_clause:='WHERE j.status=''posted'' AND j.posting_date<=t.collection_date AND l.loan_id=t.loan_id';
 IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Native application ledger predecessor changed.'; END IF;
 definition:=replace(definition,old_clause,old_clause||' AND NOT accounting.native_loan_ancillary_tax_exact(j.id,t.loan_id)');
 EXECUTE definition;
END $$;

CREATE OR REPLACE FUNCTION accounting.treasury_regular_application_origin(p_application UUID)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM treasury.applications a JOIN lending.collection_transactions t
  ON t.id::text=a.source_result->'transaction_ids'->>0
  JOIN treasury.loan_payouts p ON p.loan_id=t.loan_id AND p.source_kind='first_loan' AND p.status<>'cancelled'
  WHERE a.id=p_application) THEN
  RETURN accounting.treasury_native_regular_application_origin(p_application);
 END IF;
 RETURN accounting.treasury_legacy_regular_application_origin(p_application);
END $$;

DO $$ DECLARE definition TEXT; old_clause TEXT; BEGIN
 definition:=pg_get_functiondef('accounting.treasury_legacy_regular_application_coordinates(uuid)'::regprocedure);
 definition:=replace(definition,'accounting.treasury_legacy_regular_application_coordinates(',
  'accounting.treasury_native_regular_application_coordinates(');
 old_clause:=$old$OR anchor->>'readiness_status' IS DISTINCT FROM 'greenfield_regular_eir_anchor_ready'$old$;
 IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Native application admission predecessor changed.'; END IF;
 definition:=replace(definition,old_clause,$new$OR origin#>>'{native_origin,ready}' IS DISTINCT FROM 'true'$new$);
 old_clause:=$old$ IF NOT EXISTS(SELECT 1 FROM accounting.journal_entries j JOIN accounting.journal_lines l ON l.journal_entry_id=j.id
   JOIN accounting.accounts ac ON ac.id=l.account_id WHERE j.id=(anchor->>'journal_entry_id')::uuid
    AND l.credit=(anchor->>'initial_gross_carrying_amount')::numeric AND ac.account_type='asset' AND ac.normal_balance='debit' AND ac.is_posting
    AND (ac.code,ac.system_key) IN(('1010','cash_office'),('1030','cash_bank_gcash'))) THEN
  RAISE EXCEPTION 'Original protected release cash chart meaning is incompatible.' USING ERRCODE='55000'; END IF;$old$;
 IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Native application cash-origin predecessor changed.'; END IF;
 definition:=replace(definition,old_clause,$new$ IF origin#>>'{native_origin,snapshot,book,id}' IS DISTINCT FROM book::text THEN
  RAISE EXCEPTION 'Native original loan belongs to another accounting book.' USING ERRCODE='55000'; END IF;$new$);
 old_clause:=$old$allowed:=ARRAY[(anchor->>'journal_entry_id')::uuid]; previous_end:=NULL;$old$;
 IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Native application journal lineage predecessor changed.'; END IF;
 definition:=replace(definition,old_clause,
  $new$allowed:=ARRAY[(anchor->>'journal_entry_id')::uuid,(origin#>>'{native_origin,snapshot,debit_proof,journal_entry_id}')::uuid]; previous_end:=NULL;$new$);
 old_clause:='AND NOT j.id=ANY(array_remove(allowed,NULL))) THEN';
 IF position(old_clause IN definition)=0 THEN RAISE EXCEPTION 'Native application unknown-journal predecessor changed.'; END IF;
 definition:=replace(definition,old_clause,
  'AND NOT j.id=ANY(array_remove(allowed,NULL)) AND NOT accounting.native_loan_ancillary_tax_exact(j.id,t.loan_id)) THEN');
 EXECUTE definition;
END $$;

CREATE OR REPLACE FUNCTION accounting.treasury_regular_application_coordinates(p_application UUID)
RETURNS JSONB LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM treasury.applications a JOIN lending.collection_transactions t
  ON t.id::text=a.source_result->'transaction_ids'->>0
  JOIN treasury.loan_payouts p ON p.loan_id=t.loan_id AND p.source_kind='first_loan' AND p.status<>'cancelled'
  WHERE a.id=p_application) THEN
  RETURN accounting.treasury_native_regular_application_coordinates(p_application);
 END IF;
 RETURN accounting.treasury_legacy_regular_application_coordinates(p_application);
END $$;

CREATE OR REPLACE FUNCTION accounting.lock_elapsed_assessment_sources()
RETURNS VOID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 PERFORM accounting.lock_elapsed_assessment_before_native_sources();
 -- Only relation locks follow the common source locks; the private normalizer
 -- never acquires an originating wallet row after the caller's wallet locks.
 LOCK TABLE accounting.loan_payout_accounting_preparations,accounting.loan_payout_accounting_postings,
  treasury.accounts,treasury.contexts,accounting.treasury_cash_mappings,
  treasury.events,treasury.event_revisions,treasury.movement_lines,treasury.source_links,treasury.evidence,
  lending.first_loan_releases,lending.first_loan_approvals,lending.first_loan_authorizations,
  lending.first_loan_authorization_revocations,lending.first_loan_packet_documents,lending.office_review_evidence
 IN SHARE MODE;
END $$;

DO $$ DECLARE item RECORD; role_name TEXT; BEGIN
 FOR item IN SELECT p.oid::regprocedure signature FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
 WHERE n.nspname='accounting' AND p.proname IN(
  'loan_payout_origin_matches',
  'loan_period_elapsed_assessment_candidate','loan_period_legacy_elapsed_assessment_candidate',
  'loan_period_native_elapsed_assessment_candidate','treasury_regular_application_origin',
  'treasury_legacy_regular_application_origin','treasury_native_regular_application_origin',
  'treasury_regular_application_coordinates','treasury_legacy_regular_application_coordinates',
  'treasury_native_regular_application_coordinates','lock_elapsed_assessment_sources',
  'lock_elapsed_assessment_before_native_sources') LOOP
  EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC',item.signature);
  FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
   IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM %I',item.signature,role_name);
   END IF;
  END LOOP;
 END LOOP;
END $$;

COMMENT ON FUNCTION accounting.loan_period_native_elapsed_assessment_candidate(UUID,UUID) IS
'Original native Regular no-cash fiscal prefix, using exact dated payout debit/completion and original signed EIR. Includes both origin journals; legacy review JSON is unchanged.';
COMMENT ON FUNCTION accounting.treasury_native_regular_application_coordinates(UUID) IS
'First Regular Treasury application from exact native completion and contiguous fiscal prefixes. Consumes already posted borrower funds; creates no second cash posting.';

COMMIT;
