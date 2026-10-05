BEGIN;

-- Private original-contract normalization only. No ledger/source mutation and
-- no replacement of the existing153/155 dispatch or0139 funding admission.
-- Callers that later use this in a write must first hold their authoritative
-- source locks and retain/revalidate the returned source snapshot at commit.
CREATE OR REPLACE FUNCTION accounting.regular_original_origin(p_loan UUID,p_cutoff DATE)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER
SET search_path=pg_catalog SET timezone='UTC' AS $$
DECLARE book accounting.book_identity%ROWTYPE; loan lending.loans%ROWTYPE;
 payout treasury.loan_payouts%ROWTYPE; wallet treasury.accounts%ROWTYPE;
 completion accounting.loan_payout_accounting_posting_status%ROWTYPE;
 debit accounting.loan_payout_accounting_posting_status%ROWTYPE;
 completed accounting.loan_payout_accounting_postings%ROWTYPE;
 completion_preparation accounting.loan_payout_accounting_preparations%ROWTYPE;
 debit_preparation accounting.loan_payout_accounting_preparations%ROWTYPE;
 release lending.first_loan_releases%ROWTYPE; disbursement lending.loan_disbursement_events%ROWTYPE;
 schedule lending.loan_contract_schedules%ROWTYPE; registration lending.loan_contract_schedule_registrations%ROWTYPE;
 approval lending.first_loan_approvals%ROWTYPE; authorization_record lending.first_loan_authorizations%ROWTYPE;
 document lending.first_loan_packet_documents%ROWTYPE;
 blockers TEXT[]:=ARRAY[]::text[]; anchor JSONB; snapshot JSONB; installments JSONB;
 packet_rows JSONB; ledger JSONB; chart JSONB; rate NUMERIC; total NUMERIC;
 first_due DATE; last_due DATE; row_count INTEGER; distinct_dates INTEGER; nonfuture INTEGER;
 context_kind TEXT; product_mode TEXT; native_count INTEGER; legacy_count INTEGER;
BEGIN
 IF p_cutoff IS NULL THEN RETURN jsonb_build_object('ready',false,'blockers',jsonb_build_array('economic_cutoff_required')); END IF;
 SELECT * INTO book FROM accounting.book_identity WHERE singleton;
 SELECT * INTO loan FROM lending.loans WHERE id=p_loan;
 IF book.id IS NULL THEN blockers:=array_append(blockers,'accounting_book_identity_required'); END IF;
 IF loan.id IS NULL THEN RETURN jsonb_build_object('ready',false,'blockers',to_jsonb(array_append(blockers,'loan_required'))); END IF;
 SELECT count(*) INTO native_count FROM treasury.loan_payouts
 WHERE loan_id=p_loan AND source_kind='first_loan' AND status<>'cancelled';
 SELECT count(*) INTO legacy_count FROM accounting.loan_disbursement_journal_postings
 WHERE loan_id=p_loan AND posting_date<=p_cutoff;
 IF native_count<>1 THEN
  RETURN jsonb_build_object('ready',false,'blockers',to_jsonb(array_append(blockers,
   CASE WHEN native_count>1 OR (native_count>0 AND legacy_count>0) THEN 'ambiguous_original_loan_origin'
        ELSE 'native_original_payout_required' END)));
 END IF;
 IF legacy_count>0 THEN blockers:=array_append(blockers,'ambiguous_original_loan_origin'); END IF;
 SELECT * INTO payout FROM treasury.loan_payouts
 WHERE loan_id=p_loan AND source_kind='first_loan' AND status<>'cancelled';
 SELECT * INTO wallet FROM treasury.accounts WHERE id=payout.account_id;
 SELECT kind INTO context_kind FROM treasury.contexts WHERE id=payout.ledger_context_id;
 IF book.id IS NULL OR wallet.id IS NULL OR context_kind IS DISTINCT FROM book.kind
  OR wallet.ledger_context_id IS DISTINCT FROM payout.ledger_context_id
  OR NOT coalesce((book.kind='synthetic' AND wallet.ownership='synthetic')
   OR (book.kind='corporate_legal' AND wallet.ownership='corporate')
   OR (book.kind='owner_operations' AND wallet.ownership IN('owner_personal','owner_business')),false) THEN
  blockers:=array_append(blockers,'native_origin_book_scope_mismatch');
 END IF;
 SELECT * INTO release FROM lending.first_loan_releases WHERE funding_payout_id=payout.id AND loan_id=p_loan;
 IF payout.status IS DISTINCT FROM 'completed' OR release.id IS NULL THEN
  RETURN jsonb_build_object('ready',false,'blockers',to_jsonb(array_append(blockers,'native_payout_completion_required')));
 END IF;
 SELECT * INTO disbursement FROM lending.loan_disbursement_events WHERE id=release.disbursement_event_id;
 IF disbursement.business_date>p_cutoff THEN
  RETURN jsonb_build_object('ready',false,'blockers',to_jsonb(array_append(blockers,'native_payout_completion_after_cutoff')));
 END IF;
 SELECT * INTO completion FROM accounting.loan_payout_accounting_posting_status WHERE payout_id=payout.id AND stage='completion';
 SELECT * INTO debit FROM accounting.loan_payout_accounting_posting_status WHERE payout_id=payout.id AND stage='debit';
 IF completion.journal_entry_id IS NULL OR debit.journal_entry_id IS NULL
  OR completion.exact_posted IS DISTINCT FROM true OR completion.correction_pending IS DISTINCT FROM false
  OR debit.exact_posted IS DISTINCT FROM true OR debit.correction_pending IS DISTINCT FROM false THEN
  RETURN jsonb_build_object('ready',false,'blockers',to_jsonb(array_append(blockers,'native_payout_posting_not_exact')));
 END IF;
 SELECT * INTO completed FROM accounting.loan_payout_accounting_postings WHERE preparation_id=completion.preparation_id;
 SELECT * INTO completion_preparation FROM accounting.loan_payout_accounting_preparations WHERE id=completion.preparation_id;
 SELECT * INTO debit_preparation FROM accounting.loan_payout_accounting_preparations WHERE id=debit.preparation_id;
 IF completion.book_id IS DISTINCT FROM book.id OR debit.book_id IS DISTINCT FROM book.id
  OR completion.loan_id IS DISTINCT FROM loan.id OR debit.loan_id IS DISTINCT FROM loan.id
  OR completion.client_id IS DISTINCT FROM loan.client_id OR debit.client_id IS DISTINCT FROM loan.client_id
  OR payout.client_id IS DISTINCT FROM loan.client_id OR payout.source_id IS DISTINCT FROM loan.id
  OR completion.treasury_account_id IS DISTINCT FROM payout.account_id OR debit.treasury_account_id IS DISTINCT FROM payout.account_id
  OR completion.event_id IS DISTINCT FROM debit.event_id OR completion.event_id IS DISTINCT FROM payout.event_id
  OR completion.disbursement_event_id IS DISTINCT FROM disbursement.id
  OR completion_preparation.snapshot->>'debit_journal_entry_id' IS DISTINCT FROM debit.journal_entry_id::text
  OR completion_preparation.snapshot->>'debit_source_digest' IS DISTINCT FROM debit.source_digest
  OR completion.amount IS DISTINCT FROM debit.amount OR completion.amount IS DISTINCT FROM payout.amount
  OR completion.amount IS DISTINCT FROM loan.principal OR completion.amount<=0 OR completion.fee<>0
  OR debit.posting_date>completion.posting_date OR completion.posting_date>p_cutoff
  OR completion.posting_date IS DISTINCT FROM disbursement.business_date THEN
  blockers:=array_append(blockers,'native_payout_origin_identity_mismatch');
 END IF;
 SELECT calculation_mode INTO product_mode FROM lending.loan_types WHERE id=loan.loan_type_id;
 IF product_mode IS DISTINCT FROM 'fixed_daily' OR disbursement.id IS NULL
  OR disbursement.loan_id IS DISTINCT FROM loan.id OR disbursement.client_id IS DISTINCT FROM loan.client_id
  OR disbursement.event_kind IS DISTINCT FROM 'new_loan_release' OR disbursement.is_voided IS DISTINCT FROM false
  OR disbursement.funding_account_system_key IS DISTINCT FROM 'cash_bank_gcash'
  OR disbursement.settlement_amount IS DISTINCT FROM 0 OR disbursement.other_deduction_amount IS DISTINCT FROM 0
  OR disbursement.cash_disbursed_amount IS DISTINCT FROM completion.amount OR disbursement.principal_snapshot IS DISTINCT FROM completion.amount
  OR disbursement.date_released_snapshot IS DISTINCT FROM completion.posting_date
  OR loan.date_released IS DISTINCT FROM completion.posting_date OR release.received_amount IS DISTINCT FROM completion.amount
  OR release.cash_amount IS NOT NULL OR release.cash_evidence_reference IS NOT NULL THEN
  blockers:=array_append(blockers,'native_original_release_not_exact');
 END IF;
 IF EXISTS(SELECT 1 FROM lending.loan_disbursement_events e WHERE e.loan_id=p_loan AND e.id<>disbursement.id
   AND e.business_date<=completion.posting_date AND NOT e.is_voided)
  OR EXISTS(SELECT 1 FROM lending.loan_renewal_execution_events e WHERE (e.old_loan_id=p_loan OR e.new_loan_id=p_loan)
   AND e.business_date<=completion.posting_date) THEN
  blockers:=array_append(blockers,'ambiguous_original_loan_origin');
 END IF;
 SELECT * INTO schedule FROM lending.loan_contract_schedules WHERE id=release.schedule_id;
 SELECT * INTO registration FROM lending.loan_contract_schedule_registrations WHERE schedule_id=schedule.id;
 SELECT * INTO approval FROM lending.first_loan_approvals WHERE loan_id=loan.id;
 SELECT * INTO authorization_record FROM lending.first_loan_authorizations WHERE id=release.authorization_id;
 SELECT * INTO document FROM lending.first_loan_packet_documents WHERE loan_id=loan.id;
 IF schedule.id IS NULL OR registration.id IS NULL OR approval.id IS NULL OR authorization_record.id IS NULL OR document.id IS NULL
  OR schedule.loan_id IS DISTINCT FROM loan.id OR schedule.schedule_version IS DISTINCT FROM 1 OR schedule.supersedes_schedule_id IS NOT NULL
  OR schedule.contract_reference IS DISTINCT FROM approval.id::text OR release.receipt->>'packet_id' IS DISTINCT FROM approval.id::text
  OR approval.client_id IS DISTINCT FROM loan.client_id OR authorization_record.loan_id IS DISTINCT FROM loan.id
  OR registration.evidence_basis IS DISTINCT FROM 'signed_contract' OR registration.evidence_reference IS DISTINCT FROM release.contract_evidence_reference
  OR registration.verified_by_user_id IS DISTINCT FROM authorization_record.authorized_by_user_id
  OR schedule.contract_signed_date IS DISTINCT FROM completion.posting_date OR schedule.effective_from IS DISTINCT FROM completion.posting_date
  OR schedule.settings->>'first_loan_packet_hash' IS DISTINCT FROM approval.packet_hash
  OR release.packet_hash IS DISTINCT FROM approval.packet_hash OR authorization_record.packet_hash IS DISTINCT FROM approval.packet_hash
  OR document.packet_hash IS DISTINCT FROM approval.packet_hash OR payout.source_snapshot->>'packet_hash' IS DISTINCT FROM approval.packet_hash
  OR payout.source_snapshot->>'authorization_id' IS DISTINCT FROM authorization_record.id::text
  OR payout.source_snapshot->>'contract_evidence_reference' IS DISTINCT FROM release.contract_evidence_reference
  OR approval.packet#>>'{terms,product_code}' IS DISTINCT FROM 'regular'
  OR approval.packet#>>'{terms,principal}' IS DISTINCT FROM completion.amount::text
  OR approval.packet#>>'{terms,schedule_basis_date}' IS DISTINCT FROM completion.posting_date::text
  OR approval.packet#>>'{terms,payment_frequency}' IS DISTINCT FROM schedule.payment_frequency
  OR approval.packet#>'{terms,deductions}' IS DISTINCT FROM '[]'::jsonb
  OR EXISTS(SELECT 1 FROM lending.first_loan_authorization_revocations r WHERE r.authorization_id=authorization_record.id) THEN
  blockers:=array_append(blockers,'native_signed_contract_lineage_not_exact');
 END IF;
 SELECT coalesce(jsonb_agg(to_jsonb(i) ORDER BY i.installment_number),'[]'::jsonb),
  coalesce(jsonb_agg(jsonb_build_object('installment_number',i.installment_number,'due_date',i.due_date::text,
   'contractual_amount',i.contractual_amount::text,'principal_component',i.principal_component::text,
   'interest_component',i.interest_component::text) ORDER BY i.installment_number),'[]'::jsonb),
  count(*)::integer,count(DISTINCT i.due_date)::integer,min(i.due_date),max(i.due_date),sum(i.contractual_amount),
  count(*) FILTER(WHERE i.due_date<=completion.posting_date)::integer
 INTO installments,packet_rows,row_count,distinct_dates,first_due,last_due,total,nonfuture
 FROM lending.loan_contract_installments i WHERE i.schedule_id=schedule.id;
 IF row_count=0 OR distinct_dates<>row_count OR nonfuture<>0 OR total IS NULL OR total<=completion.amount
  OR last_due IS DISTINCT FROM loan.due_date OR packet_rows IS DISTINCT FROM approval.packet->'schedule'
  OR EXISTS(SELECT 1 FROM lending.loan_contract_schedules s WHERE s.loan_id=p_loan AND s.id<>schedule.id AND s.effective_from<=p_cutoff) THEN
  blockers:=array_append(blockers,'native_signed_installments_not_exact');
 END IF;
 -- This is an original anchor, not a later loan rollforward. Unknown original
 -- loan/control entries cannot net away. Later activity is the153/155 caller's
 -- separate dated prefix/allocation responsibility and is not certified here.
 IF EXISTS(SELECT 1 FROM accounting.journal_entries j JOIN accounting.journal_lines l ON l.journal_entry_id=j.id
  WHERE j.status='posted' AND l.loan_id=p_loan
  AND j.posting_date<=completion.posting_date
  AND j.id NOT IN(debit.journal_entry_id,completion.journal_entry_id)) THEN
  blockers:=array_append(blockers,'unrecognized_original_loan_control_journal');
 END IF;
 IF EXISTS(SELECT 1 FROM (VALUES('1100','loans_receivable_regular'),('1050','loan_disbursement_transit')) x(code,system_key)
  WHERE NOT EXISTS(SELECT 1 FROM accounting.accounts a WHERE a.code=x.code AND a.system_key=x.system_key
   AND a.account_type='asset' AND a.normal_balance='debit' AND a.is_posting)) THEN
  blockers:=array_append(blockers,'native_origin_chart_meaning_mismatch');
 END IF;
 IF cardinality(blockers)>0 THEN RETURN jsonb_build_object('ready',false,'blockers',to_jsonb(blockers)); END IF;
 rate:=accounting.solve_verified_contract_schedule_daily_eir(schedule.id,completion.posting_date,completion.amount);
 IF rate IS NULL OR rate<=0 THEN RETURN jsonb_build_object('ready',false,'blockers',jsonb_build_array('native_original_eir_not_solved')); END IF;
 anchor:=jsonb_build_object('loan_id',loan.id,'client_id',loan.client_id,'posting_id',completed.id,
  'disbursement_event_id',disbursement.id,'journal_entry_id',completion.journal_entry_id,
  'anchor_date',completion.posting_date,'initial_gross_carrying_amount',completion.amount,
  'initial_loan_component',completion.amount,'initial_accrued_interest_component',0,
  'schedule_id',schedule.id,'schedule_version',schedule.schedule_version,'payment_frequency',schedule.payment_frequency,
  'contract_reference',schedule.contract_reference,'contract_signed_date',schedule.contract_signed_date,
  'schedule_effective_from',schedule.effective_from,'registration_id',registration.id,
  'evidence_basis',registration.evidence_basis,'evidence_reference',registration.evidence_reference,
  'installment_count',row_count,'first_due_date',first_due,'contractual_due_date',last_due,'contractual_cash_total',total,
  'daily_eir',rate,'anchor_policy_version','native_regular_payout_anchor_v1',
  'anchor_source_key','native_regular_payout_anchor:'||completed.id::text);
 SELECT jsonb_agg(jsonb_build_object('journal',to_jsonb(j),'line',to_jsonb(l),
  'account',accounting.treasury_gl_account_snapshot(l.account_id)-ARRAY['name','is_active']) ORDER BY j.posting_date,j.id,l.line_number)
 INTO ledger FROM accounting.journal_entries j JOIN accounting.journal_lines l ON l.journal_entry_id=j.id
 WHERE j.id IN(debit.journal_entry_id,completion.journal_entry_id);
 SELECT jsonb_agg(accounting.treasury_gl_account_snapshot(a.id)-ARRAY['name','is_active'] ORDER BY a.code)
 INTO chart FROM accounting.accounts a WHERE a.id IN(SELECT l.account_id FROM accounting.journal_lines l
  WHERE l.journal_entry_id IN(debit.journal_entry_id,completion.journal_entry_id));
 snapshot:=jsonb_build_object('policy_version','native_regular_payout_anchor_v1','book',to_jsonb(book),
  'cutoff_date',p_cutoff,'anchor',anchor,'debit_preparation',to_jsonb(debit_preparation),
  'completion_preparation',to_jsonb(completion_preparation),'debit_proof',to_jsonb(debit),
  'completion_proof',to_jsonb(completion),'completion_posting',to_jsonb(completed),
  'release',to_jsonb(release),'disbursement',to_jsonb(disbursement),'approval',to_jsonb(approval),
  'authorization',to_jsonb(authorization_record),'packet_document',to_jsonb(document),
  'schedule',to_jsonb(schedule)-'status','registration',to_jsonb(registration),
  'installments',installments,'ledger',ledger,'chart',chart,
  'wallet_scope',jsonb_build_object('account_id',wallet.id,'ledger_context_id',wallet.ledger_context_id,
    'kind',wallet.kind,'ownership',wallet.ownership,'context_kind',context_kind));
 RETURN jsonb_build_object('ready',true,'blockers','[]'::jsonb,'origin_kind','native_payout',
  'anchor',anchor,'snapshot',snapshot,'source_digest',encode(sha256(convert_to(snapshot::text,'UTF8')),'hex'));
END $$;

REVOKE ALL ON FUNCTION accounting.regular_original_origin(UUID,DATE) FROM PUBLIC;
DO $$ DECLARE r TEXT; BEGIN
 FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN
   EXECUTE format('REVOKE ALL ON FUNCTION accounting.regular_original_origin(UUID,DATE) FROM %I',r);
  END IF;
 END LOOP;
END $$;

COMMENT ON FUNCTION accounting.regular_original_origin(UUID,DATE) IS
'Private read-only native original Regular loan provenance. Requires exact154 debit/completion and approved signed installments; does not certify later carrying, risk, assessment, or application and does not alter legacy anchors.';

COMMIT;
