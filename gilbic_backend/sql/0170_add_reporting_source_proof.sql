BEGIN;

-- Retained presentation evidence may cover these existing protected postings.
-- This adds no monetary posting and does not certify unrecorded source activity.
CREATE OR REPLACE FUNCTION accounting.reporting_initial_capital_exact(p_journal UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT EXISTS (
  SELECT 1 FROM accounting.initial_capital_funding_evidence e
  JOIN accounting.initial_capital_funding_preparations p ON p.evidence_id=e.id
  JOIN accounting.initial_capital_funding_postings a ON a.evidence_id=e.id AND a.journal_entry_id=p.journal_entry_id
  JOIN accounting.journal_entries j ON j.id=a.journal_entry_id
  JOIN accounting.accounts cash ON cash.id=e.cash_account_id
  JOIN accounting.accounts capital ON capital.id=e.capital_account_id
  WHERE j.id=p_journal AND a.entry_number=j.entry_number
   AND (a.confirmed_amount,a.confirmed_cash_account_id,a.confirmed_posting_date,a.confirmed_fiscal_period_id)
       IS NOT DISTINCT FROM (e.amount,e.cash_account_id,e.funding_date,p.fiscal_period_id)
   AND a.confirmation_digest=encode(sha256(convert_to(concat_ws('|',a.policy_version,e.id::text,e.evidence_digest,
       e.funding_date::text,to_char(e.amount,'FM999999999999990.00'),cash.id::text,capital.id::text,p.fiscal_period_id::text,j.id::text,a.confirmation_token),'UTF8')),'hex')
   AND p.source_event_key='initial_capital_funding:'||e.id::text
   AND cash.system_key IN('cash_office','cash_bank_gcash') AND cash.account_type='asset' AND cash.normal_balance='debit' AND cash.is_posting
   AND cash.code=CASE cash.system_key WHEN 'cash_office' THEN '1010' ELSE '1030' END
   AND capital.code='3000' AND capital.system_key='capital' AND capital.account_type='equity' AND capital.normal_balance='credit' AND capital.is_posting
   AND accounting.legacy_two_line_posted_exact(j.id,p.source_event_key,'initial_capital_funding',e.id::text,
       e.funding_date,p.fiscal_period_id,e.cash_account_id,e.capital_account_id,e.amount,NULL,NULL)
 );
$$;

CREATE OR REPLACE FUNCTION accounting.reporting_initial_ecl_exact(p_journal UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT EXISTS (
  SELECT 1 FROM accounting.ecl_allowance_postings a
  JOIN accounting.ecl_allowance_draft_preparations p ON p.id=a.preparation_id
  JOIN accounting.ecl_quantitative_measurements m ON m.id=p.measurement_id
  JOIN accounting.journal_entries j ON j.id=a.journal_entry_id
  JOIN accounting.accounts expense ON expense.id=p.credit_loss_expense_account_id
  JOIN accounting.accounts contra ON contra.id=p.allowance_account_id
  WHERE j.id=p_journal AND j.entry_number=a.entry_number
   AND (p.measurement_version,p.calculation_digest,p.allowance_amount,p.measurement_date,p.loan_id)
       IS NOT DISTINCT FROM (m.measurement_version,m.calculation_digest,m.ecl_amount,m.measurement_date,m.loan_id)
   AND (a.measurement_id,a.loan_id,a.client_id,a.measurement_version,a.calculation_digest,a.journal_entry_id,a.source_event_key,
        a.posting_date,a.fiscal_period_id,a.credit_loss_expense_account_id,a.allowance_account_id,a.allowance_amount,a.prior_allowance_balance,
        a.preparation_review_token,a.preparation_digest,a.draft_policy_version)
       IS NOT DISTINCT FROM (p.measurement_id,p.loan_id,p.client_id,p.measurement_version,p.calculation_digest,p.journal_entry_id,p.source_event_key,
        p.posting_date,p.fiscal_period_id,p.credit_loss_expense_account_id,p.allowance_account_id,p.allowance_amount,p.prior_allowance_balance,
        p.preparation_review_token,p.preparation_digest,p.draft_policy_version)
   AND a.resulting_allowance_balance=m.ecl_amount AND a.prior_allowance_balance=0
   AND expense.code='5000' AND expense.system_key='credit_loss_expense' AND expense.account_type='expense' AND expense.normal_balance='debit' AND expense.is_posting
   AND contra.code='1190' AND contra.system_key='allowance_expected_credit_loss' AND contra.account_type='asset' AND contra.normal_balance='credit' AND contra.is_posting
   AND accounting.legacy_two_line_posted_exact(j.id,'ecl_allowance:'||m.id::text,'ecl_allowance',m.id::text,
       p.posting_date,p.fiscal_period_id,expense.id,contra.id,m.ecl_amount,p.client_id,p.loan_id)
   AND 2=(SELECT count(*) FROM accounting.ecl_allowance_posting_lines WHERE posting_id=a.id)
   AND NOT EXISTS(SELECT 1 FROM accounting.ecl_allowance_posting_lines retained
     LEFT JOIN accounting.journal_lines actual ON actual.journal_entry_id=j.id AND actual.line_number=retained.line_number
     LEFT JOIN accounting.accounts account ON account.id=actual.account_id
     WHERE retained.posting_id=a.id AND (actual.id IS NULL OR
       (retained.account_id,retained.account_system_key,retained.debit,retained.credit,retained.client_id,retained.loan_id)
       IS DISTINCT FROM (actual.account_id,account.system_key,actual.debit,actual.credit,actual.client_id,actual.loan_id)))
 );
$$;

CREATE OR REPLACE FUNCTION accounting.reporting_renewal_eir_exact(p_journal UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT EXISTS(
  SELECT 1 FROM accounting.renewal_boundary_eir_journal_preparation_entries e
  JOIN accounting.renewal_boundary_eir_journal_preparations p ON p.id=e.preparation_id
  JOIN accounting.renewal_boundary_eir_journal_posting_sets a ON a.preparation_id=p.id
  WHERE e.journal_entry_id=p_journal
   AND (a.renewal_execution_event_id,a.old_loan_id,a.client_id,a.review_token,a.expected_entry_count,a.posted_entry_count,a.total_debit,a.total_credit)
       IS NOT DISTINCT FROM (p.renewal_execution_event_id,p.old_loan_id,p.client_id,p.review_token,p.expected_entry_count,p.expected_entry_count,p.total_amount,p.total_amount)
   AND p.expected_entry_count=(SELECT count(*) FROM accounting.renewal_boundary_eir_journal_preparation_entries WHERE preparation_id=p.id)
   AND p.expected_entry_count=(SELECT count(*) FROM accounting.renewal_boundary_eir_journal_posting_entries WHERE posting_set_id=a.id)
   AND NOT EXISTS(
    SELECT 1 FROM accounting.renewal_boundary_eir_journal_preparation_entries item
    LEFT JOIN accounting.renewal_boundary_eir_journal_posting_entries audit ON audit.posting_set_id=a.id AND audit.sequence_order=item.sequence_order
    LEFT JOIN accounting.journal_entries j ON j.id=item.journal_entry_id
    LEFT JOIN accounting.accounts debit ON debit.id=item.debit_account_id
    LEFT JOIN accounting.accounts credit ON credit.id=item.credit_account_id
    WHERE item.preparation_id=p.id AND (audit.journal_entry_id IS DISTINCT FROM j.id OR audit.preparation_id IS DISTINCT FROM p.id
      OR audit.entry_number IS DISTINCT FROM j.entry_number OR audit.source_event_key IS DISTINCT FROM item.source_event_key
      OR debit.system_key IS DISTINCT FROM 'accrued_interest_receivable' OR debit.code IS DISTINCT FROM '1120'
      OR debit.account_type IS DISTINCT FROM 'asset' OR debit.normal_balance IS DISTINCT FROM 'debit' OR NOT debit.is_posting
      OR credit.system_key IS DISTINCT FROM 'interest_income_regular' OR credit.code IS DISTINCT FROM '4000'
      OR credit.account_type IS DISTINCT FROM 'income' OR credit.normal_balance IS DISTINCT FROM 'credit' OR NOT credit.is_posting
      OR NOT accounting.legacy_two_line_posted_exact(j.id,item.source_event_key,'regular_renewal_eir_accrual',item.source_reference,
         item.posting_date,item.fiscal_period_id,item.debit_account_id,item.credit_account_id,item.amount,p.client_id,p.old_loan_id)))
 );
$$;

CREATE OR REPLACE FUNCTION accounting.reporting_ecl_remeasurement_exact(p_journal UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT EXISTS(SELECT 1 FROM accounting.ecl_allowance_remeasurements a
 JOIN accounting.ecl_quantitative_measurements m ON m.id=a.measurement_id
 JOIN accounting.journal_entries j ON j.id=a.journal_entry_id
 JOIN accounting.accounts expense ON expense.id=a.credit_loss_expense_account_id
 JOIN accounting.accounts contra ON contra.id=a.allowance_account_id
 WHERE j.id=p_journal AND j.entry_number=a.entry_number
  AND (a.loan_id,a.measurement_version,a.calculation_digest,a.target_allowance_balance,a.posting_date)
      IS NOT DISTINCT FROM (m.loan_id,m.measurement_version,m.calculation_digest,m.ecl_amount,m.measurement_date)
  AND a.adjustment_amount=abs(a.target_allowance_balance-a.prior_allowance_balance)
  AND a.adjustment_direction=CASE WHEN a.target_allowance_balance>a.prior_allowance_balance THEN 'increase' WHEN a.target_allowance_balance=0 THEN 'full_reversal' ELSE 'decrease' END
  AND a.source_event_key='ecl_remeasurement:'||m.id::text
  AND expense.code='5000' AND expense.system_key='credit_loss_expense' AND expense.account_type='expense' AND expense.normal_balance='debit' AND expense.is_posting
  AND contra.code='1190' AND contra.system_key='allowance_expected_credit_loss' AND contra.account_type='asset' AND contra.normal_balance='credit' AND contra.is_posting
  AND accounting.legacy_two_line_posted_exact(j.id,a.source_event_key,'ecl_allowance_remeasurement',m.id::text,a.posting_date,a.fiscal_period_id,
    CASE WHEN a.adjustment_direction='increase' THEN expense.id ELSE contra.id END,
    CASE WHEN a.adjustment_direction='increase' THEN contra.id ELSE expense.id END,a.adjustment_amount,a.client_id,a.loan_id));
$$;

CREATE OR REPLACE FUNCTION accounting.reporting_ecl_writeoff_exact(p_journal UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT EXISTS(SELECT 1 FROM accounting.ecl_accounting_writeoffs a
 JOIN accounting.ecl_quantitative_measurements m ON m.id=a.measurement_id
 JOIN accounting.ecl_credit_risk_label_reviews review ON review.id=a.credit_risk_review_id
 JOIN accounting.journal_entries j ON j.id=a.journal_entry_id
 JOIN accounting.accounts principal ON principal.id=a.loan_receivable_account_id
 JOIN accounting.accounts interest ON interest.id=a.accrued_interest_account_id
 JOIN accounting.accounts contra ON contra.id=a.allowance_account_id
 WHERE j.id=p_journal AND j.status='posted' AND j.entry_number=a.entry_number
  AND j.source_type='ecl_writeoff' AND j.source_reference=a.credit_risk_review_id::text
  AND j.source_event_key='ecl_writeoff:'||a.loan_id::text AND j.source_event_key=a.source_event_key
  AND j.posting_date=a.posting_date AND j.fiscal_period_id=a.fiscal_period_id
  AND (a.loan_id,a.measurement_version,a.calculation_digest,a.gross_carrying_amount)
      IS NOT DISTINCT FROM (m.loan_id,m.measurement_version,m.calculation_digest,m.ecl_amount)
  AND review.loan_id=a.loan_id AND review.stage_label='stage_3_credit_impaired' AND review.default_label
  AND review.write_off_label='supported_no_reasonable_expectation_of_recovery'
  AND principal.system_key IN('loans_receivable_regular','loans_receivable_7x7') AND principal.account_type='asset' AND principal.normal_balance='debit' AND principal.is_posting
  AND interest.code='1120' AND interest.system_key='accrued_interest_receivable' AND interest.account_type='asset' AND interest.normal_balance='debit' AND interest.is_posting
  AND contra.code='1190' AND contra.system_key='allowance_expected_credit_loss' AND contra.account_type='asset' AND contra.normal_balance='credit' AND contra.is_posting
  AND a.gross_carrying_amount=a.allowance_balance AND a.gross_carrying_amount=a.loan_component+a.accrued_interest_component
  AND NOT EXISTS(
   (SELECT account_id,debit,credit,client_id,loan_id FROM accounting.journal_lines WHERE journal_entry_id=j.id
    EXCEPT ALL SELECT * FROM (VALUES (contra.id,a.gross_carrying_amount,0::numeric,a.client_id,a.loan_id),
       (principal.id,0::numeric,a.loan_component,a.client_id,a.loan_id),(interest.id,0::numeric,a.accrued_interest_component,a.client_id,a.loan_id)) expected(account_id,debit,credit,client_id,loan_id) WHERE debit+credit>0)
   UNION ALL
   (SELECT * FROM (VALUES (contra.id,a.gross_carrying_amount,0::numeric,a.client_id,a.loan_id),
       (principal.id,0::numeric,a.loan_component,a.client_id,a.loan_id),(interest.id,0::numeric,a.accrued_interest_component,a.client_id,a.loan_id)) expected(account_id,debit,credit,client_id,loan_id) WHERE debit+credit>0
    EXCEPT ALL SELECT account_id,debit,credit,client_id,loan_id FROM accounting.journal_lines WHERE journal_entry_id=j.id)));
$$;

CREATE OR REPLACE FUNCTION accounting.reporting_ecl_recovery_exact(p_journal UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT EXISTS(SELECT 1 FROM accounting.ecl_post_writeoff_recoveries a
 JOIN accounting.ecl_accounting_writeoffs writeoff ON writeoff.id=a.writeoff_id
 JOIN accounting.ecl_post_writeoff_recovery_review_provenance evidence ON evidence.credit_risk_review_id=a.credit_risk_review_id
 JOIN accounting.ecl_credit_risk_label_reviews review ON review.id=a.credit_risk_review_id
 JOIN lending.collection_transactions source ON source.id=a.recovery_transaction_id
 JOIN accounting.journal_entries j ON j.id=a.journal_entry_id
 JOIN accounting.accounts cash ON cash.id=a.cash_account_id
 JOIN accounting.accounts expense ON expense.id=a.credit_loss_expense_account_id
 WHERE j.id=p_journal AND j.entry_number=a.entry_number
  AND (evidence.writeoff_id,evidence.loan_id,evidence.client_id,evidence.recovery_transaction_id,evidence.recovery_amount)
      IS NOT DISTINCT FROM (a.writeoff_id,a.loan_id,a.client_id,a.recovery_transaction_id,a.recovery_amount)
  AND writeoff.loan_id=a.loan_id AND writeoff.client_id=a.client_id AND accounting.reporting_ecl_writeoff_exact(writeoff.journal_entry_id)
  AND review.loan_id=a.loan_id AND review.recovery_label='cash_recovery_observed' AND review.recovery_transaction_id=source.id
  AND source.loan_id=a.loan_id AND source.client_id=a.client_id AND source.amount=a.recovery_amount AND NOT source.is_voided
  AND source.entry_type IN('payment','advance') AND source.accepted_at>writeoff.posted_at AND source.collection_date=a.posting_date
  AND NOT EXISTS(SELECT 1 FROM accounting.regular_journal_posting_entries normal WHERE normal.transaction_id=source.id)
  AND NOT EXISTS(SELECT 1 FROM accounting.seven_by_seven_journal_postings normal WHERE normal.transaction_id=source.id)
  AND a.source_event_key='ecl_recovery:'||source.id::text
  AND cash.code='1020' AND cash.system_key='cash_collector_custody' AND cash.account_type='asset' AND cash.normal_balance='debit' AND cash.is_posting
  AND expense.code='5000' AND expense.system_key='credit_loss_expense' AND expense.account_type='expense' AND expense.normal_balance='debit' AND expense.is_posting
  AND accounting.legacy_two_line_posted_exact(j.id,a.source_event_key,'ecl_post_writeoff_recovery',source.id::text,
    a.posting_date,a.fiscal_period_id,cash.id,expense.id,a.recovery_amount,a.client_id,a.loan_id));
$$;

DO $$ BEGIN
 IF to_regprocedure('accounting.journal_disclosure_source_status_before_0170(uuid)') IS NULL THEN
  ALTER FUNCTION accounting.journal_disclosure_source_status(UUID) RENAME TO journal_disclosure_source_status_before_0170;
 END IF;
 IF to_regprocedure('accounting.lock_journal_disclosure_sources_before_0170(uuid)') IS NULL THEN
  ALTER FUNCTION accounting.lock_journal_disclosure_sources(UUID) RENAME TO lock_journal_disclosure_sources_before_0170;
 END IF;
END $$;

CREATE OR REPLACE FUNCTION accounting.journal_disclosure_source_status(p_journal UUID)
RETURNS TEXT LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE j accounting.journal_entries%ROWTYPE; exact BOOLEAN;
BEGIN
 SELECT * INTO j FROM accounting.journal_entries WHERE id=p_journal AND status='posted';
 IF NOT FOUND THEN RETURN 'posted_journal_required'; END IF;
 CASE j.source_type
 WHEN 'initial_capital_funding' THEN exact:=accounting.reporting_initial_capital_exact(j.id);
 WHEN 'ecl_allowance' THEN exact:=accounting.reporting_initial_ecl_exact(j.id);
 WHEN 'ecl_allowance_remeasurement' THEN exact:=accounting.reporting_ecl_remeasurement_exact(j.id);
 WHEN 'ecl_writeoff' THEN exact:=accounting.reporting_ecl_writeoff_exact(j.id);
 WHEN 'ecl_post_writeoff_recovery' THEN exact:=accounting.reporting_ecl_recovery_exact(j.id);
 WHEN 'regular_renewal_eir_accrual' THEN exact:=accounting.reporting_renewal_eir_exact(j.id);
 WHEN 'loan_disbursement' THEN
  SELECT EXISTS(SELECT 1 FROM accounting.loan_disbursement_journal_posting_status a
   JOIN lending.loan_disbursement_events source ON source.id=a.disbursement_event_id
   WHERE a.journal_entry_id=j.id AND a.posted_audit_exact AND a.loan_id=source.loan_id AND a.client_id=source.client_id
    AND a.amount=source.cash_disbursed_amount AND a.posting_date=source.business_date
    AND j.source_reference=source.id::text AND j.source_event_key='loan_disbursement:'||source.id::text
    AND j.posting_date=a.posting_date AND j.fiscal_period_id=a.fiscal_period_id) INTO exact;
 WHEN 'loan_disbursement_cancellation_reversal' THEN
  SELECT EXISTS(SELECT 1 FROM accounting.loan_disbursement_cancellation_status a WHERE a.reversal_journal_entry_id=j.id
   AND a.cancelled_reversal_audit_exact AND j.posting_date=a.reversal_posting_date
   AND accounting.legacy_journal_reversal_exact(a.original_journal_entry_id,j.id)) INTO exact;
 WHEN 'seven_by_seven_collection' THEN
  SELECT EXISTS(SELECT 1 FROM accounting.seven_by_seven_journal_posting_status a JOIN lending.collection_transactions t ON t.id=a.transaction_id
   WHERE a.journal_entry_id=j.id AND a.posted_audit_exact AND a.loan_id=t.loan_id AND a.client_id=t.client_id
    AND a.source_cash_amount=t.applied_amount AND a.posting_date=t.collection_date
    AND j.posting_date=a.posting_date AND j.fiscal_period_id=a.fiscal_period_id) INTO exact;
 WHEN 'seven_by_seven_collection_reversal' THEN
  SELECT EXISTS(SELECT 1 FROM accounting.seven_by_seven_journal_reversal_status a WHERE a.reversal_journal_entry_id=j.id
   AND a.reversal_audit_exact AND j.posting_date=a.reversal_posting_date
   AND accounting.legacy_journal_reversal_exact(a.original_journal_entry_id,j.id)) INTO exact;
 WHEN 'regular_collection_void_reversal' THEN
  SELECT EXISTS(SELECT 1 FROM accounting.regular_journal_reversal_entries a JOIN accounting.regular_journal_reversal_sets s ON s.id=a.reversal_set_id
   WHERE a.reversal_journal_entry_id=j.id AND accounting.legacy_regular_collection_reversed_exact(s.transaction_id,j.posting_date)) INTO exact;
 WHEN 'remittance_transfer' THEN
  SELECT EXISTS(SELECT 1 FROM accounting.remittance_transfer_journal_status a
   JOIN accounting.remittance_transfer_evidence evidence ON evidence.id=a.transfer_evidence_id
   JOIN lending.collection_remittances source ON source.id=a.remittance_id
   WHERE a.journal_entry_id=j.id AND a.posted_audit_exact
    AND a.amount=evidence.total_amount_snapshot AND a.posting_date=evidence.business_date
    AND a.debit_account_system_key=evidence.destination_account_system_key AND a.credit_account_system_key='cash_collector_custody'
    AND accounting.legacy_two_line_posted_exact(j.id,a.source_event_key,'remittance_transfer',a.remittance_id::text,
        a.posting_date,a.fiscal_period_id,a.debit_account_id,a.credit_account_id,a.amount,NULL,NULL)
    -- This protected reversal reorders the cash accounts to keep the debit
    -- first. Prove those exact coordinates instead of original line numbers.
    AND ((a.reversal_audit_exact AND accounting.legacy_two_line_posted_exact(
        a.reversal_journal_entry_id,'remittance_transfer_reversal:'||a.posting_id::text,
        'remittance_transfer_reversal',a.posting_id::text,a.reversal_posting_date,
        (SELECT fiscal_period_id FROM accounting.journal_entries WHERE id=a.reversal_journal_entry_id),
        a.credit_account_id,a.debit_account_id,a.amount,NULL,NULL)) OR
       (NOT evidence.is_voided AND source.status='received' AND
        (evidence.total_amount_snapshot,evidence.collector_user_id_snapshot,evidence.recipient_user_id_snapshot,
         evidence.custody_user_id_snapshot,evidence.custody_transferred_at_snapshot,evidence.collection_date_snapshot,evidence.remittance_number_snapshot)
        IS NOT DISTINCT FROM (source.total_amount,source.collector_user_id,source.recipient_user_id,source.custody_user_id,
         source.custody_transferred_at,source.collection_date,source.remittance_number)))) INTO exact;
 WHEN 'remittance_transfer_reversal' THEN
  SELECT EXISTS(SELECT 1 FROM accounting.remittance_transfer_journal_status a
   WHERE a.reversal_journal_entry_id=j.id AND a.posted_audit_exact AND a.reversal_audit_exact
    AND accounting.legacy_two_line_posted_exact(j.id,'remittance_transfer_reversal:'||a.posting_id::text,
        'remittance_transfer_reversal',a.posting_id::text,a.reversal_posting_date,j.fiscal_period_id,
        a.credit_account_id,a.debit_account_id,a.amount,NULL,NULL)) INTO exact;
 WHEN 'v1_tax_liability' THEN
  SELECT EXISTS(SELECT 1 FROM accounting.v1_tax_liability_postings a
   JOIN accounting.v1_tax_liability_preparations p ON p.id=a.preparation_id WHERE a.journal_entry_id=j.id
   AND accounting.legacy_tax_liability_posted_exact(p.tax_type,p.evidence_id)) INTO exact;
 WHEN 'v1_tax_settlement','v1_tax_adjustment','v1_tax_additional_liability','v1_tax_additional_settlement','v1_tax_recoverable_refund','v1_tax_recoverable_credit_application' THEN
  SELECT EXISTS(SELECT 1 FROM (
    SELECT 'v1_tax_settlement' source_type,'tax_payment' proof_type,journal_entry_id,payment_evidence_id source_id FROM accounting.v1_tax_settlement_postings
    UNION ALL SELECT 'v1_tax_adjustment','tax_adjustment',journal_entry_id,adjustment_evidence_id FROM accounting.v1_tax_adjustment_postings
    UNION ALL SELECT 'v1_tax_additional_liability','tax_additional_liability',journal_entry_id,amendment_evidence_id FROM accounting.v1_tax_additional_liability_postings
    UNION ALL SELECT 'v1_tax_additional_settlement','tax_additional_payment',journal_entry_id,payment_evidence_id FROM accounting.v1_tax_additional_settlement_postings
    UNION ALL SELECT 'v1_tax_recoverable_refund','tax_refund',journal_entry_id,refund_evidence_id FROM accounting.v1_tax_recoverable_refund_postings
    UNION ALL SELECT 'v1_tax_recoverable_credit_application','tax_credit_application',journal_entry_id,credit_evidence_id FROM accounting.v1_tax_recoverable_credit_postings
   ) a JOIN accounting.legacy_tax_movement_proof p ON p.source_type=a.proof_type AND p.source_id=a.source_id
   WHERE a.journal_entry_id=j.id AND a.source_type=j.source_type AND p.posted_exact) INTO exact;
 ELSE RETURN accounting.journal_disclosure_source_status_before_0170(p_journal);
 END CASE;
 RETURN CASE WHEN exact IS TRUE THEN 'current' ELSE 'source_correction_required' END;
END $$;

CREATE OR REPLACE FUNCTION accounting.lock_journal_disclosure_sources(p_journal UUID)
RETURNS VOID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 PERFORM accounting.lock_journal_disclosure_sources_before_0170(p_journal);
 LOCK TABLE accounting.initial_capital_funding_evidence,accounting.initial_capital_funding_preparations,accounting.initial_capital_funding_postings,
  accounting.renewal_boundary_eir_journal_preparations,accounting.renewal_boundary_eir_journal_preparation_entries,
  accounting.renewal_boundary_eir_journal_posting_sets,accounting.renewal_boundary_eir_journal_posting_entries,
  accounting.native_renewal_measurement_reviews,accounting.native_regular_asset_lineage,
  accounting.renewal_treatment_decisions,accounting.renewal_treatment_decision_voids,
  accounting.ecl_quantitative_measurements,accounting.ecl_allowance_draft_preparations,accounting.ecl_allowance_postings,accounting.ecl_allowance_posting_lines,
  accounting.ecl_allowance_remeasurements,accounting.ecl_accounting_writeoffs,accounting.ecl_post_writeoff_recoveries,
  accounting.ecl_credit_risk_label_reviews,accounting.ecl_post_writeoff_recovery_review_provenance,
  lending.collection_remittances,accounting.remittance_transfer_evidence,accounting.remittance_transfer_journal_preparations,
  accounting.remittance_transfer_journal_postings,accounting.remittance_transfer_journal_reversals
 IN SHARE MODE;
 IF to_regclass('accounting.native_impaired_cash_reviews') IS NOT NULL THEN
  LOCK TABLE accounting.native_impaired_cash_reviews IN SHARE MODE;
 END IF;
END $$;

DO $$ DECLARE role_name TEXT; signature TEXT; BEGIN
 FOREACH role_name IN ARRAY ARRAY['PUBLIC','anon','authenticated'] LOOP
  IF role_name='PUBLIC' OR EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
   FOREACH signature IN ARRAY ARRAY['reporting_initial_capital_exact(uuid)','reporting_initial_ecl_exact(uuid)','reporting_renewal_eir_exact(uuid)',
    'reporting_ecl_remeasurement_exact(uuid)','reporting_ecl_writeoff_exact(uuid)','reporting_ecl_recovery_exact(uuid)',
    'journal_disclosure_source_status(uuid)','journal_disclosure_source_status_before_0170(uuid)',
    'lock_journal_disclosure_sources(uuid)','lock_journal_disclosure_sources_before_0170(uuid)'] LOOP
    EXECUTE format('REVOKE ALL ON FUNCTION accounting.%s FROM %s',signature,CASE WHEN role_name='PUBLIC' THEN 'PUBLIC' ELSE quote_ident(role_name) END);
   END LOOP;
  END IF;
 END LOOP;
END $$;

COMMIT;
