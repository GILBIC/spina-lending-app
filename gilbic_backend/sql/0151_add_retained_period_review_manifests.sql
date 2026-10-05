BEGIN;

CREATE TABLE IF NOT EXISTS accounting.period_review_manifests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fiscal_period_id UUID NOT NULL REFERENCES accounting.fiscal_periods(id),
    review_version INTEGER NOT NULL CHECK(review_version>0),
    book_id UUID REFERENCES accounting.book_identity(id),
    policy_version TEXT NOT NULL CHECK(policy_version='dated_source_review_manifest_v1'),
    source_snapshot JSONB NOT NULL,
    source_digest TEXT NOT NULL CHECK(source_digest ~ '^[0-9a-f]{64}$'),
    reviewed_by_user_id UUID NOT NULL REFERENCES core.users(id),
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    capture_transaction_id BIGINT NOT NULL DEFAULT txid_current(),
    prior_review_count INTEGER NOT NULL CHECK(prior_review_count>=0),
    UNIQUE(fiscal_period_id,review_version)
);
CREATE TABLE IF NOT EXISTS accounting.period_close_manifest_bindings (
    preparation_id UUID PRIMARY KEY REFERENCES accounting.period_close_preparations(id),
    manifest_id UUID NOT NULL REFERENCES accounting.period_review_manifests(id),
    source_digest TEXT NOT NULL CHECK(source_digest ~ '^[0-9a-f]{64}$'),
    bound_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE OR REPLACE FUNCTION accounting.guard_period_review_manifest_write()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
    IF TG_OP='INSERT' AND current_setting('accounting.review_manifest_write',true)=TG_TABLE_NAME THEN RETURN NEW; END IF;
    RAISE EXCEPTION 'Retained period review manifests and close bindings are immutable protected evidence.' USING ERRCODE='55000';
END;
$$;
DO $$ DECLARE name TEXT; BEGIN
    FOREACH name IN ARRAY ARRAY['period_review_manifests','period_close_manifest_bindings'] LOOP
        EXECUTE format('ALTER TABLE accounting.%I ENABLE ROW LEVEL SECURITY',name);
        EXECUTE format('DROP TRIGGER IF EXISTS period_review_manifest_write_guard ON accounting.%I',name);
        EXECUTE format('CREATE TRIGGER period_review_manifest_write_guard BEFORE INSERT OR UPDATE OR DELETE ON accounting.%I FOR EACH ROW EXECUTE FUNCTION accounting.guard_period_review_manifest_write()',name);
        EXECUTE format('DROP TRIGGER IF EXISTS period_review_manifest_truncate_guard ON accounting.%I',name);
        EXECUTE format('CREATE TRIGGER period_review_manifest_truncate_guard BEFORE TRUNCATE ON accounting.%I FOR EACH STATEMENT EXECUTE FUNCTION accounting.guard_period_review_manifest_write()',name);
    END LOOP;
END; $$;

CREATE OR REPLACE FUNCTION accounting.period_review_additional_evidence(p_period UUID)
RETURNS JSONB LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$ SELECT '{}'::jsonb $$;
CREATE OR REPLACE FUNCTION accounting.lock_period_review_additional_sources()
RETURNS VOID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN RETURN; END $$;

-- The table/field specifications below are an explicit internal allowlist. No
-- caller supplies SQL, relation names, a digest, or a claimed accounting date.
CREATE OR REPLACE FUNCTION accounting.period_review_source_snapshot(p_period UUID)
RETURNS JSONB LANGUAGE plpgsql VOLATILE SECURITY INVOKER
SET search_path=pg_catalog SET timezone='UTC' AS $$
DECLARE period_row accounting.fiscal_periods%ROWTYPE; cutoff DATE; book JSONB; ledger JSONB;
    scope JSONB:='{}'::jsonb; families JSONB:='{}'::jsonb; rows JSONB; item RECORD;
    audit_table TEXT; audit_rows JSONB; selected JSONB:='[]'::jsonb; next_selected JSONB;
    payload JSONB; relation REGCLASS; changed BOOLEAN; pass INTEGER; source_count BIGINT:=0;
BEGIN
    SELECT * INTO period_row FROM accounting.fiscal_periods WHERE id=p_period;
    IF NOT FOUND THEN RAISE EXCEPTION 'Accounting period was not found.'; END IF;
    cutoff:=period_row.end_date;
    SELECT to_jsonb(b) INTO book FROM accounting.book_identity b;
    SELECT coalesce(jsonb_agg(to_jsonb(j)||jsonb_build_object('lines',(
        SELECT jsonb_agg(to_jsonb(l) ORDER BY l.line_number,l.id)
        FROM accounting.journal_lines l WHERE l.journal_entry_id=j.id),
        'period',jsonb_build_object('id',assigned.id,'start_date',assigned.start_date,'end_date',assigned.end_date))
        ORDER BY j.posting_date,j.id),'[]'::jsonb)
    INTO ledger FROM accounting.journal_entries j JOIN accounting.fiscal_periods assigned ON assigned.id=j.fiscal_period_id
    WHERE j.status='posted' AND j.posting_date<=cutoff
      AND NOT (j.fiscal_period_id=p_period AND j.source_type='period_close' AND j.source_event_key='period_close:'||p_period::text);
    scope:=jsonb_build_object('_journals',(SELECT coalesce(jsonb_agg(x->>'id'),'[]'::jsonb) FROM jsonb_array_elements(ledger) x),
        '_loans',(SELECT coalesce(jsonb_agg(l.id::text ORDER BY l.id),'[]'::jsonb) FROM lending.loans l WHERE l.date_released<=cutoff
          OR EXISTS(SELECT 1 FROM accounting.journal_lines line JOIN accounting.journal_entries j ON j.id=line.journal_entry_id
                    WHERE line.loan_id=l.id AND j.status='posted' AND j.posting_date<=cutoff)));

    FOR item IN SELECT * FROM (VALUES
      ('accounting.accounts',
       's.code=''3100'' OR EXISTS(SELECT 1 FROM accounting.journal_lines l WHERE l.account_id=s.id AND $3->''_journals'' ? l.journal_entry_id::text)',
       'to_jsonb(s)'),
      ('treasury.events','(s.effective_at AT TIME ZONE ''Asia/Manila'')::date<=$1','to_jsonb(s)'),
      ('treasury.movement_lines','(s.effective_at AT TIME ZONE ''Asia/Manila'')::date<=$1','to_jsonb(s)'),
      ('treasury.event_revisions','$3->''treasury.events'' ? s.event_id::text','to_jsonb(s)'),
      ('treasury.source_links','$3->''treasury.events'' ? s.event_id::text','to_jsonb(s)'),
      ('treasury.opening_positions','(s.cutoff AT TIME ZONE ''Asia/Manila'')::date<=$1',
       '(to_jsonb(s)-ARRAY[''status'',''version''])||jsonb_build_object(''recognized'',s.status IN (''active'',''superseded''))'),
      ('treasury.receipts','(s.effective_at AT TIME ZONE ''Asia/Manila'')::date<=$1',
       '(to_jsonb(s)-ARRAY[''applied_amount'',''refunded_amount'',''version''])||jsonb_build_object(''applied_at_cutoff'',(SELECT coalesce(sum(t.amount),0) FROM lending.collection_transactions t WHERE t.funding_receipt_id=s.id AND t.collection_date<=$1 AND (NOT t.is_voided OR (t.voided_at AT TIME ZONE ''Asia/Manila'')::date>$1)),''refunded_at_cutoff'',(SELECT coalesce(sum(link.linked_amount),0) FROM treasury.source_links link JOIN treasury.events e ON e.id=link.event_id WHERE link.source_kind=''receipt_refund'' AND link.source_id=s.id AND (e.effective_at AT TIME ZONE ''Asia/Manila'')::date<=$1))'),
      ('treasury.transfers','($3->''treasury.events'' ? s.source_event_id::text) OR ($3->''treasury.events'' ? s.destination_event_id::text)',
       '(to_jsonb(s)-ARRAY[''version'',''created_at'',''source_event_id'',''destination_event_id''])||jsonb_build_object(''source_event_id'',CASE WHEN $3->''treasury.events'' ? s.source_event_id::text THEN s.source_event_id END,''destination_event_id'',CASE WHEN $3->''treasury.events'' ? s.destination_event_id::text THEN s.destination_event_id END)'),
      ('lending.collection_transactions','s.collection_date<=$1',
       '(CASE WHEN s.is_voided AND (s.voided_at AT TIME ZONE ''Asia/Manila'')::date>$1 THEN coalesce((SELECT v.transaction_snapshot FROM lending.collection_transaction_voids v WHERE v.transaction_id=s.id),to_jsonb(s)) ELSE to_jsonb(s) END-ARRAY[''is_voided'',''voided_at'',''voided_by_user_id'',''void_reason'',''remittance_id'',''is_locked'',''locked_at'',''updated_at''])||jsonb_build_object(''is_voided'',s.is_voided AND (s.voided_at AT TIME ZONE ''Asia/Manila'')::date<=$1,''voided_at'',CASE WHEN (s.voided_at AT TIME ZONE ''Asia/Manila'')::date<=$1 THEN s.voided_at END)'),
      ('lending.collection_transaction_voids','(s.voided_at AT TIME ZONE ''Asia/Manila'')::date<=$1','to_jsonb(s)'),
      ('treasury.applications',
       'EXISTS(SELECT 1 FROM lending.collection_transactions t WHERE t.funding_receipt_id=s.receipt_id AND t.funding_account_id=s.account_id AND t.funding_source=''treasury_receipt'' AND (s.source_result->''transaction_ids'') ? t.id::text AND t.collection_date<=$1) OR ((s.created_at AT TIME ZONE ''Asia/Manila'')::date<=$1 AND NOT EXISTS(SELECT 1 FROM lending.collection_transactions t WHERE t.funding_receipt_id=s.receipt_id AND t.funding_account_id=s.account_id AND t.funding_source=''treasury_receipt'' AND (s.source_result->''transaction_ids'') ? t.id::text))',
       'to_jsonb(s)-''status'''),
      ('treasury.loan_payouts','$3->''treasury.events'' ? s.event_id::text',
       'jsonb_build_object(''id'',s.id,''account_id'',s.account_id,''ledger_context_id'',s.ledger_context_id,''source_kind'',s.source_kind,''source_id'',s.source_id,''loan_id'',s.loan_id,''renewal_request_id'',s.renewal_request_id,''client_id'',s.client_id,''destination'',s.destination,''recipient_reference'',s.recipient_reference,''amount'',s.amount,''source_digest'',s.source_digest,''source_snapshot'',s.source_snapshot,''event_id'',s.event_id)'),
      ('treasury.collector_openings','((s.payload->>''cutoff'')::timestamptz AT TIME ZONE ''Asia/Manila'')::date<=$1',
       '(to_jsonb(s)-ARRAY[''version'',''payload''])||jsonb_build_object(''payload'',s.payload-''status'')'),
      ('treasury.collector_settlements','((s.payload->>''accepted_at'')::timestamptz AT TIME ZONE ''Asia/Manila'')::date<=$1','to_jsonb(s)'),
      ('treasury.collector_counts','$3->''treasury.collector_settlements'' ? (SELECT st.id::text FROM treasury.collector_settlements st WHERE st.count_id=s.id)','to_jsonb(s)'),
      ('treasury.collector_cases','($3->''treasury.collector_openings'' ? s.opening_anchor_id::text) OR ($3->''treasury.collector_settlements'' ? s.settlement_id::text) OR (s.created_at AT TIME ZONE ''Asia/Manila'')::date<=$1',
       '(to_jsonb(s)-ARRAY[''version'',''payload''])||jsonb_build_object(''payload'',s.payload-ARRAY[''unidentified_amount'',''status'',''resolutions''])'),
      ('treasury.collector_credits','($3->''treasury.collector_openings'' ? s.opening_anchor_id::text) OR (s.created_at AT TIME ZONE ''Asia/Manila'')::date<=$1',
       '(to_jsonb(s)-ARRAY[''version'',''payload''])||jsonb_build_object(''payload'',s.payload-ARRAY[''reclassified_amount'',''returned_amount'',''applied_amount'',''reserved_amount'',''outstanding_amount'',''available_amount'',''frozen'',''status'',''entries''])'),
      ('treasury.collector_actions','($3->''treasury.events'' ? s.event_id::text) OR (s.event_id IS NULL AND (s.created_at AT TIME ZONE ''Asia/Manila'')::date<=$1)','to_jsonb(s)'),
      ('treasury.collector_entries','($3->''treasury.events'' ? (s.payload->>''incoming_event_id'')) OR ($3->''treasury.collector_actions'' ? (s.payload->>''action_id'')) OR (s.payload->>''kind''=''opening'' AND $3->''treasury.collector_credits'' ? s.credit_id::text) OR (s.created_at AT TIME ZONE ''Asia/Manila'')::date<=$1','to_jsonb(s)'),
      ('treasury.collector_resolutions','(s.created_at AT TIME ZONE ''Asia/Manila'')::date<=$1','to_jsonb(s)'),
      ('treasury.accounts','EXISTS(SELECT 1 FROM treasury.events e WHERE e.account_id=s.id AND $3->''treasury.events'' ? e.id::text) OR EXISTS(SELECT 1 FROM treasury.opening_positions o WHERE o.account_id=s.id AND $3->''treasury.opening_positions'' ? o.id::text)',
       'jsonb_build_object(''id'',s.id,''ledger_context_id'',s.ledger_context_id,''kind'',s.kind,''ownership'',s.ownership,''custodian_user_id'',s.custodian_user_id)'),
      ('treasury.evidence','EXISTS(SELECT 1 FROM treasury.events e WHERE e.evidence_id=s.id AND $3->''treasury.events'' ? e.id::text) OR EXISTS(SELECT 1 FROM treasury.movement_lines l WHERE l.evidence_id=s.id AND $3->''treasury.movement_lines'' ? l.id::text) OR EXISTS(SELECT 1 FROM treasury.opening_positions o WHERE o.evidence_id=s.id AND $3->''treasury.opening_positions'' ? o.id::text) OR EXISTS(SELECT 1 FROM treasury.event_revisions r WHERE r.evidence_id=s.id AND $3->''treasury.event_revisions'' ? r.id::text)','to_jsonb(s)'),
      ('lending.loan_disbursement_events','s.business_date<=$1',
       '(to_jsonb(s)-ARRAY[''is_voided'',''voided_at'',''voided_by_user_id'',''void_reason''])||jsonb_build_object(''is_voided'',s.is_voided AND (s.voided_at AT TIME ZONE ''Asia/Manila'')::date<=$1,''voided_at'',CASE WHEN (s.voided_at AT TIME ZONE ''Asia/Manila'')::date<=$1 THEN s.voided_at END)'),
      ('lending.loan_disbursement_cancellations','s.reversal_posting_date<=$1','to_jsonb(s)'),
      ('lending.loan_renewal_execution_events','s.business_date<=$1',
       '(to_jsonb(s)-ARRAY[''is_voided'',''voided_at'',''voided_by_user_id'',''void_reason''])||jsonb_build_object(''is_voided'',s.is_voided AND (s.voided_at AT TIME ZONE ''Asia/Manila'')::date<=$1,''voided_at'',CASE WHEN (s.voided_at AT TIME ZONE ''Asia/Manila'')::date<=$1 THEN s.voided_at END)'),
      ('lending.client_renewal_requests','EXISTS(SELECT 1 FROM (VALUES(s.cash_released_to_collector_at),(s.collector_cash_received_at),(s.cash_given_to_client_at),(s.client_cash_confirmed_at)) leg(at) WHERE (leg.at AT TIME ZONE ''Asia/Manila'')::date<=$1)',
       'jsonb_build_object(''id'',s.id,''loan_id'',s.loan_id,''client_id'',s.client_id,''net_release_amount'',s.net_release_amount,''cash_released_to_collector_at'',CASE WHEN (s.cash_released_to_collector_at AT TIME ZONE ''Asia/Manila'')::date<=$1 THEN s.cash_released_to_collector_at END,''collector_cash_received_at'',CASE WHEN (s.collector_cash_received_at AT TIME ZONE ''Asia/Manila'')::date<=$1 THEN s.collector_cash_received_at END,''cash_given_to_client_at'',CASE WHEN (s.cash_given_to_client_at AT TIME ZONE ''Asia/Manila'')::date<=$1 THEN s.cash_given_to_client_at END,''client_cash_confirmed_at'',CASE WHEN (s.client_cash_confirmed_at AT TIME ZONE ''Asia/Manila'')::date<=$1 THEN s.client_cash_confirmed_at END)'),
      ('lending.collection_remittances','s.status=''received'' AND (coalesce(s.custody_transferred_at,s.received_at) AT TIME ZONE ''Asia/Manila'')::date<=$1','to_jsonb(s)-''updated_at'''),
      ('lending.collection_remittance_items','$3->''lending.collection_remittances'' ? s.remittance_id::text','to_jsonb(s)'),
      ('accounting.remittance_transfer_evidence','s.business_date<=$1',
       '(to_jsonb(s)-ARRAY[''is_voided'',''voided_at'',''voided_by_user_id'',''void_reason''])||jsonb_build_object(''is_voided'',s.is_voided AND (s.voided_at AT TIME ZONE ''Asia/Manila'')::date<=$1,''voided_at'',CASE WHEN (s.voided_at AT TIME ZONE ''Asia/Manila'')::date<=$1 THEN s.voided_at END)'),
      -- A posted payout transit line selects its approved loan identity before
      -- borrower release. Later release dates and release-created schedules do
      -- not belong to that earlier cutoff; approved monetary terms still do.
      ('lending.loans','$3->''_loans'' ? s.id::text',
       'jsonb_build_object(''id'',s.id,''loan_number'',s.loan_number,''client_id'',s.client_id,''loan_type_id'',s.loan_type_id,''principal'',s.principal,''daily_amount'',s.daily_amount,''interest_rate'',s.interest_rate,''date_released'',CASE WHEN s.date_released<=$1 THEN s.date_released END,''due_date'',CASE WHEN s.date_released<=$1 THEN s.due_date END)'),
      ('lending.loan_types','EXISTS(SELECT 1 FROM lending.loans l WHERE l.loan_type_id=s.id AND $3->''_loans'' ? l.id::text)','to_jsonb(s)'),
      ('lending.loan_contract_schedules','($3->''_loans'' ? s.loan_id::text) AND EXISTS(SELECT 1 FROM lending.loans loan WHERE loan.id=s.loan_id AND loan.date_released<=$1)','to_jsonb(s)'),
      ('lending.loan_contract_schedule_registrations','$3->''lending.loan_contract_schedules'' ? s.schedule_id::text','to_jsonb(s)'),
      ('lending.loan_contract_installments','$3->''lending.loan_contract_schedules'' ? s.schedule_id::text','to_jsonb(s)'),
      ('lending.loan_installment_payment_allocations','$3->''lending.collection_transactions'' ? s.transaction_id::text','to_jsonb(s)'),
      ('lending.seven_by_seven_extra_principal_adjustments','$3->''lending.collection_transactions'' ? s.transaction_id::text','to_jsonb(s)'),
      ('accounting.seven_by_seven_policy_decisions','$3->''_loans'' ? s.loan_id::text','to_jsonb(s)'),
      ('accounting.seven_by_seven_policy_decision_voids','(s.voided_at AT TIME ZONE ''Asia/Manila'')::date<=$1','to_jsonb(s)'),
      ('accounting.seven_by_seven_eir_initial_carrying_anchors','$3->''_loans'' ? s.loan_id::text','to_jsonb(s)'),
      ('accounting.seven_by_seven_eir_initial_carrying_anchor_voids','(s.voided_at AT TIME ZONE ''Asia/Manila'')::date<=$1','to_jsonb(s)'),
      ('accounting.ecl_quantitative_measurements','s.measurement_date<=$1 AND $3->''_loans'' ? s.loan_id::text','to_jsonb(s)'),
      ('accounting.ecl_credit_risk_label_reviews','EXISTS(SELECT 1 FROM accounting.ecl_quantitative_measurements m WHERE $3->''accounting.ecl_quantitative_measurements'' ? m.id::text AND m.label_review_id=s.id)','to_jsonb(s)'),
      ('accounting.ecl_forward_looking_evidence','EXISTS(SELECT 1 FROM accounting.ecl_quantitative_measurements m WHERE $3->''accounting.ecl_quantitative_measurements'' ? m.id::text AND s.id=ANY(m.forward_evidence_ids))','to_jsonb(s)'),
      ('accounting.ecl_forward_looking_evidence_revocations','$3->''accounting.ecl_forward_looking_evidence'' ? s.evidence_id::text','to_jsonb(s)'),
      ('accounting.loan_period_assessment_preparations','s.cutoff_date<=$1 AND s.fiscal_period_id=$2','to_jsonb(s)'),
      ('accounting.loan_period_assessment_postings','$3->''accounting.loan_period_assessment_preparations'' ? s.preparation_id::text','to_jsonb(s)'),
      ('accounting.liability_obligations','s.recognition_date<=$1','to_jsonb(s)'),
      ('accounting.liability_line_claims','s.posting_date<=$1','to_jsonb(s)'),
      ('accounting.v1_dst_evidence','s.issue_date<=$1','to_jsonb(s)'),
      ('accounting.v1_percentage_tax_evidence','s.collection_date<=$1','to_jsonb(s)'),
      ('accounting.v1_tax_rule_evidence','EXISTS(SELECT 1 FROM accounting.v1_dst_evidence e JOIN accounting.v1_tax_rule_evidence original ON original.id=e.rule_evidence_id WHERE $3->''accounting.v1_dst_evidence'' ? e.id::text AND s.rule_key=original.rule_key AND s.tax_type=original.tax_type AND s.effective_from<=$1) OR EXISTS(SELECT 1 FROM accounting.v1_percentage_tax_evidence e JOIN accounting.v1_tax_rule_evidence original ON original.id=e.rule_evidence_id WHERE $3->''accounting.v1_percentage_tax_evidence'' ? e.id::text AND s.rule_key=original.rule_key AND s.tax_type=original.tax_type AND s.effective_from<=$1)','to_jsonb(s)'),
      ('accounting.v1_tax_return_evidence','s.filing_date<=$1','to_jsonb(s)'),
      ('accounting.v1_tax_return_liability_items','$3->''accounting.v1_tax_return_evidence'' ? s.tax_return_id::text','to_jsonb(s)'),
      ('accounting.v1_tax_payment_evidence','s.payment_date<=$1','to_jsonb(s)'),
      ('accounting.v1_tax_adjustment_evidence','s.adjustment_date<=$1','to_jsonb(s)'),
      ('accounting.v1_tax_additional_amendment_evidence','s.amendment_date<=$1','to_jsonb(s)'),
      ('accounting.v1_tax_additional_payment_evidence','s.payment_date<=$1','to_jsonb(s)'),
      ('accounting.v1_tax_recoverable_refund_evidence','s.refund_date<=$1','to_jsonb(s)'),
      ('accounting.v1_tax_recoverable_credit_evidence','s.application_date<=$1','to_jsonb(s)')
    ) AS spec(family,predicate,projection) LOOP
        relation:=item.family::regclass;
        EXECUTE format('SELECT coalesce(jsonb_agg(payload ORDER BY coalesce(payload->>''id'',payload::text)),''[]''::jsonb) FROM (SELECT %s AS payload FROM %s s WHERE %s) source',
            item.projection,relation,item.predicate) INTO rows USING cutoff,p_period,scope;
        families:=families||jsonb_build_object(item.family,rows);
        SELECT coalesce(jsonb_agg(x->>'id') FILTER (WHERE x ? 'id'),'[]'::jsonb) INTO payload FROM jsonb_array_elements(rows) x;
        scope:=scope||jsonb_build_object(item.family,payload);
    END LOOP;
    -- Select immutable audit parents and children by the exact retained source
    -- and journal identities. Own dated posting coordinates always limit scope;
    -- a future payment cannot enter via its reference to an old receipt/payable.
    SELECT coalesce(jsonb_agg(DISTINCT id ORDER BY id),'[]'::jsonb) INTO selected
    FROM jsonb_each(scope) family CROSS JOIN LATERAL jsonb_array_elements_text(family.value) identities(id);
    FOR pass IN 1..12 LOOP
        changed:=false;
        FOREACH audit_table IN ARRAY ARRAY[
            'treasury_cash_mappings','treasury_receipt_preparations','treasury_receipt_postings',
            'treasury_application_preparations','treasury_application_postings',
            'treasury_transfer_preparations','treasury_transfer_postings',
            'loan_disbursement_journal_draft_preparations','loan_disbursement_journal_postings','loan_disbursement_journal_reversals',
            'regular_journal_draft_preparations','regular_journal_draft_preparation_entries',
            'regular_journal_posting_sets','regular_journal_posting_entries','regular_journal_reversal_sets','regular_journal_reversal_entries',
            'seven_by_seven_journal_draft_preparations','seven_by_seven_journal_postings','seven_by_seven_journal_posting_lines',
            'seven_by_seven_journal_reversals','seven_by_seven_journal_reversal_lines',
            'remittance_transfer_journal_preparations','remittance_transfer_journal_postings','remittance_transfer_journal_reversals',
            'ecl_allowance_draft_preparations','ecl_allowance_postings','ecl_allowance_posting_lines',
            'ecl_allowance_remeasurements','ecl_accounting_writeoffs','ecl_post_writeoff_recoveries','ecl_post_writeoff_recovery_review_provenance',
            'v1_tax_liability_preparations','v1_tax_liability_postings',
            'v1_tax_settlement_preparations','v1_tax_settlement_postings',
            'v1_tax_adjustment_preparations','v1_tax_adjustment_postings',
            'v1_tax_additional_liability_preparations','v1_tax_additional_liability_postings',
            'v1_tax_additional_settlement_preparations','v1_tax_additional_settlement_postings',
            'v1_tax_recoverable_refund_preparations','v1_tax_recoverable_refund_postings',
            'v1_tax_recoverable_credit_preparations','v1_tax_recoverable_credit_postings'
        ] LOOP
            relation:=to_regclass('accounting.'||audit_table);
            IF relation IS NULL AND audit_table IN ('treasury_transfer_preparations','treasury_transfer_postings') THEN CONTINUE; END IF;
            IF relation IS NULL THEN RAISE EXCEPTION 'Manifest accounting authority is unavailable.'; END IF;
            EXECUTE format($query$
                SELECT coalesce(jsonb_agg(payload ORDER BY coalesce(payload->>'id',payload::text)),'[]'::jsonb)
                FROM (SELECT to_jsonb(s) AS payload FROM %s s) source
                WHERE coalesce((payload->>'posting_date')::date,(payload->>'confirmed_posting_date')::date,
                    (payload->>'reversal_posting_date')::date,(payload->>'recognition_date')::date,
                    (payload->>'writeoff_date')::date,(payload->>'recovery_date')::date,
                    (payload#>>'{snapshot,posting_date}')::date,$1)<=$1
                AND (payload->>'journal_entry_id' IS NULL OR $3 ? (payload->>'journal_entry_id'))
                AND (payload->>'reversal_journal_entry_id' IS NULL OR $3 ? (payload->>'reversal_journal_entry_id'))
                AND (($2 ? (payload->>'id')) OR EXISTS (SELECT 1 FROM jsonb_each_text(payload) reference
                    WHERE reference.key=ANY(ARRAY['journal_entry_id','reversal_journal_entry_id','original_journal_entry_id',
                        'preparation_id','posting_id','posting_set_id','preparation_set_id','reversal_set_id',
                        'measurement_id','transaction_id','disbursement_event_id','remittance_id','transfer_evidence_id',
                        'evidence_id','payment_evidence_id','tax_payment_evidence_id','tax_return_id','tax_liability_posting_id',
                        'adjustment_evidence_id','amendment_evidence_id','refund_evidence_id','credit_evidence_id',
                        'receipt_id','event_id','application_id','transfer_id']) AND $2 ? reference.value))
                $query$,relation) INTO audit_rows USING cutoff,selected,scope->'_journals';
            families:=families||jsonb_build_object('accounting.'||audit_table,audit_rows);
            SELECT coalesce(jsonb_agg(DISTINCT id ORDER BY id),'[]'::jsonb) INTO next_selected FROM (
                SELECT jsonb_array_elements_text(selected) AS id
                UNION ALL SELECT x->>'id' FROM jsonb_array_elements(audit_rows) x WHERE x ? 'id'
                UNION ALL SELECT reference.value FROM jsonb_array_elements(audit_rows) x
                    CROSS JOIN LATERAL jsonb_each_text(x) reference
                    WHERE reference.key=ANY(ARRAY['mapping_id','source_mapping_id','destination_mapping_id',
                        'preparation_id','posting_id','posting_set_id','preparation_set_id','reversal_set_id'])
                      AND reference.value IS NOT NULL
            ) identities;
            IF next_selected IS DISTINCT FROM selected THEN changed:=true; selected:=next_selected; END IF;
        END LOOP;
        EXIT WHEN NOT changed;
        IF pass=12 THEN RAISE EXCEPTION 'Manifest audit lineage did not converge; source review is required.'; END IF;
    END LOOP;
    SELECT coalesce(sum(jsonb_array_length(value)),0) INTO source_count FROM jsonb_each(families);
    payload:=accounting.period_review_additional_evidence(p_period);
    RETURN jsonb_build_object('policy_version','dated_source_review_manifest_v1','book',book,
        'period',jsonb_build_object('id',period_row.id,'label',period_row.label,'start_date',period_row.start_date,'end_date',cutoff),
        'ledger',ledger,'sources',families,'source_count',source_count,'journal_count',jsonb_array_length(ledger),
        'additional_evidence',payload,'comprehensive_source_coverage',false);
END;
$$;

CREATE OR REPLACE FUNCTION accounting.lock_period_review_manifest_sources(p_period UUID)
RETURNS VOID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE relation REGCLASS;
BEGIN
    IF current_setting('transaction_isolation')<>'read committed' THEN
        RAISE EXCEPTION 'Retained source review requires READ COMMITTED.' USING ERRCODE='55000';
    END IF;
    -- This keeps the established 0149 prefix and acquires its proof inputs.
    PERFORM accounting.assert_period_legacy_source_complete(p_period);
    LOCK TABLE lending.collection_remittance_items,treasury.evidence,treasury.transfers,
        treasury.collector_counts,accounting.ecl_post_writeoff_recoveries,
        accounting.ecl_post_writeoff_recovery_review_provenance IN SHARE MODE;
    FOREACH relation IN ARRAY ARRAY[to_regclass('accounting.treasury_transfer_preparations'),
        to_regclass('accounting.treasury_transfer_postings')] LOOP
        IF relation IS NOT NULL THEN EXECUTE format('LOCK TABLE %s IN SHARE MODE',relation); END IF;
    END LOOP;
    PERFORM accounting.lock_period_review_additional_sources();
    -- One writer order avoids SHARE-to-INSERT upgrades between independent
    -- review captures. These locks remain held through deferred validation.
    LOCK TABLE accounting.period_review_manifests,accounting.period_close_manifest_bindings IN SHARE ROW EXCLUSIVE MODE;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.period_review_manifest_state(p_period UUID)
RETURNS JSONB LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE retained accounting.period_review_manifests%ROWTYPE; current_snapshot JSONB;
    current_digest TEXT; period_status TEXT; exact BOOLEAN;
BEGIN
    SELECT status INTO period_status FROM accounting.fiscal_periods WHERE id=p_period;
    IF NOT FOUND THEN RETURN jsonb_build_object('state','period_missing','current',false,'comprehensive_source_coverage',false); END IF;
    SELECT * INTO retained FROM accounting.period_review_manifests WHERE fiscal_period_id=p_period ORDER BY review_version DESC LIMIT 1;
    IF NOT FOUND THEN RETURN jsonb_build_object('state',CASE WHEN period_status='open' THEN 'open_unreviewed' ELSE 'retained_review_missing' END,
        'current',false,'manifest_id',NULL,'version',NULL,'source_digest',NULL,'source_count',0,'journal_count',0,'comprehensive_source_coverage',false); END IF;
    current_snapshot:=accounting.period_review_source_snapshot(p_period);
    current_digest:=encode(sha256(convert_to(current_snapshot::text,'UTF8')),'hex');
    exact:=current_digest=retained.source_digest AND current_snapshot=retained.source_snapshot;
    RETURN jsonb_build_object('state',CASE WHEN period_status='open' THEN 'open_unreviewed' WHEN exact THEN 'retained_review_current' ELSE 'retained_review_stale' END,
        'current',period_status IN ('review','closed') AND exact,'manifest_id',retained.id,'version',retained.review_version,
        'source_digest',retained.source_digest,'current_digest',current_digest,
        'source_count',retained.source_snapshot->'source_count','journal_count',retained.source_snapshot->'journal_count',
        'comprehensive_source_coverage',false);
END;
$$;

CREATE OR REPLACE FUNCTION accounting.require_period_review_manifest_actor(p_actor UUID,p_permission TEXT)
RETURNS VOID LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
    IF p_permission IS NULL OR p_permission NOT IN ('accounting.period.manage','accounting.period.close.prepare','accounting.period.close.post') THEN
        RAISE EXCEPTION 'Unsupported retained review permission.' USING ERRCODE='42501';
    END IF;
    PERFORM 1 FROM core.users actor JOIN core.user_roles membership ON membership.user_id=actor.id
        JOIN core.roles role ON role.id=membership.role_id JOIN core.role_permissions permission ON permission.role_id=role.id
        WHERE actor.id=p_actor AND actor.status='active' AND role.code='management' AND permission.permission_code=p_permission
        FOR SHARE OF actor,membership,role,permission;
    IF NOT FOUND THEN RAISE EXCEPTION 'An active authorized Management reviewer is required.' USING ERRCODE='42501'; END IF;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.assert_period_review_manifest_current(p_period UUID,p_preparation UUID DEFAULT NULL)
RETURNS VOID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE retained accounting.period_review_manifests%ROWTYPE; snapshot JSONB;
BEGIN
    PERFORM accounting.lock_period_review_manifest_sources(p_period);
    SELECT * INTO retained FROM accounting.period_review_manifests WHERE fiscal_period_id=p_period ORDER BY review_version DESC LIMIT 1;
    IF NOT FOUND THEN RAISE EXCEPTION 'A retained period review manifest is required.' USING ERRCODE='23514'; END IF;
    snapshot:=accounting.period_review_source_snapshot(p_period);
    IF retained.source_snapshot IS DISTINCT FROM snapshot OR retained.source_digest IS DISTINCT FROM encode(sha256(convert_to(snapshot::text,'UTF8')),'hex') THEN
        RAISE EXCEPTION 'The retained period review manifest changed; review authorized source evidence.' USING ERRCODE='23514';
    END IF;
    IF p_preparation IS NOT NULL AND NOT EXISTS(SELECT 1 FROM accounting.period_close_manifest_bindings binding
        WHERE binding.preparation_id=p_preparation AND binding.manifest_id=retained.id AND binding.source_digest=retained.source_digest) THEN
        RAISE EXCEPTION 'Close preparation requires its exact retained review manifest binding.' USING ERRCODE='23514';
    END IF;
END;
$$;

DO $$ BEGIN
    IF to_regprocedure('accounting.set_fiscal_period_status_without_review_manifest(uuid,text,uuid)') IS NULL THEN
        ALTER FUNCTION accounting.set_fiscal_period_status(UUID,TEXT,UUID) RENAME TO set_fiscal_period_status_without_review_manifest;
    END IF;
    IF to_regprocedure('accounting.prepare_period_close_without_review_manifest(uuid,uuid)') IS NULL THEN
        ALTER FUNCTION accounting.prepare_period_close(UUID,UUID) RENAME TO prepare_period_close_without_review_manifest;
    END IF;
    IF to_regprocedure('accounting.post_period_close_without_review_manifest(uuid,uuid,text,text,numeric,text,date,text)') IS NULL THEN
        ALTER FUNCTION accounting.post_period_close(UUID,UUID,TEXT,TEXT,NUMERIC,TEXT,DATE,TEXT) RENAME TO post_period_close_without_review_manifest;
    END IF;
END; $$;

CREATE OR REPLACE FUNCTION accounting.set_fiscal_period_status(p_period_id UUID,p_new_status TEXT,p_actor_user_id UUID)
RETURNS TEXT LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE old_status TEXT; snapshot JSONB; prior_setting TEXT;
BEGIN
    PERFORM accounting.require_period_review_manifest_actor(p_actor_user_id,'accounting.period.manage');
    PERFORM pg_advisory_xact_lock(hashtextextended('period-close:'||p_period_id::text,0));
    SELECT status INTO old_status FROM accounting.fiscal_periods WHERE id=p_period_id FOR UPDATE;
    IF old_status='open' AND lower(btrim(p_new_status))='review' THEN
        PERFORM accounting.lock_period_review_manifest_sources(p_period_id);
        PERFORM accounting.assert_period_source_complete(p_period_id);
        snapshot:=accounting.period_review_source_snapshot(p_period_id);
        prior_setting:=current_setting('accounting.review_manifest_write',true);
        PERFORM set_config('accounting.review_manifest_write','period_review_manifests',true);
        INSERT INTO accounting.period_review_manifests(fiscal_period_id,review_version,book_id,policy_version,source_snapshot,source_digest,reviewed_by_user_id,prior_review_count)
        SELECT p_period_id,coalesce(max(review_version),0)+1,(snapshot#>>'{book,id}')::uuid,
            'dated_source_review_manifest_v1',snapshot,encode(sha256(convert_to(snapshot::text,'UTF8')),'hex'),p_actor_user_id,
            (SELECT count(*)::integer FROM accounting.fiscal_period_events WHERE fiscal_period_id=p_period_id AND to_status='review')
        FROM accounting.period_review_manifests WHERE fiscal_period_id=p_period_id;
        PERFORM set_config('accounting.review_manifest_write',coalesce(prior_setting,''),true);
    END IF;
    RETURN accounting.set_fiscal_period_status_without_review_manifest(p_period_id,p_new_status,p_actor_user_id);
END;
$$;

CREATE OR REPLACE FUNCTION accounting.prepare_period_close(p_period_id UUID,p_actor_user_id UUID)
RETURNS UUID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
    PERFORM accounting.require_period_review_manifest_actor(p_actor_user_id,'accounting.period.close.prepare');
    PERFORM pg_advisory_xact_lock(hashtextextended('period-close:'||p_period_id::text,0));
    PERFORM 1 FROM accounting.fiscal_periods WHERE id=p_period_id FOR UPDATE;
    PERFORM accounting.assert_period_review_manifest_current(p_period_id);
    RETURN accounting.prepare_period_close_without_review_manifest(p_period_id,p_actor_user_id);
END;
$$;

CREATE OR REPLACE FUNCTION accounting.post_period_close(p_period_id UUID,p_actor_user_id UUID,p_confirmation_token TEXT,
    p_expected_close_digest TEXT,p_expected_net_income NUMERIC,p_expected_retained_earnings_account_code TEXT,
    p_expected_close_posting_date DATE,p_policy_version TEXT)
RETURNS UUID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE prepared UUID;
BEGIN
    PERFORM accounting.require_period_review_manifest_actor(p_actor_user_id,'accounting.period.close.post');
    PERFORM pg_advisory_xact_lock(hashtextextended('period-close:'||p_period_id::text,0));
    PERFORM 1 FROM accounting.fiscal_periods WHERE id=p_period_id FOR UPDATE;
    SELECT id INTO prepared FROM accounting.period_close_preparations WHERE fiscal_period_id=p_period_id;
    IF prepared IS NULL THEN RAISE EXCEPTION 'Close preparation and retained review manifest are required.'; END IF;
    PERFORM accounting.assert_period_review_manifest_current(p_period_id,prepared);
    RETURN accounting.post_period_close_without_review_manifest(p_period_id,p_actor_user_id,p_confirmation_token,p_expected_close_digest,
        p_expected_net_income,p_expected_retained_earnings_account_code,p_expected_close_posting_date,p_policy_version);
END;
$$;

CREATE OR REPLACE FUNCTION accounting.guard_period_review_manifest_admission()
RETURNS trigger LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE prepared UUID;
BEGIN
    IF TG_TABLE_NAME='fiscal_periods' THEN
        IF NEW.status='review' AND NEW.status IS DISTINCT FROM OLD.status THEN
            IF NOT EXISTS(SELECT 1 FROM accounting.period_review_manifests m
                WHERE m.fiscal_period_id=NEW.id AND m.capture_transaction_id=txid_current()
                  AND m.prior_review_count=(SELECT count(*) FROM accounting.fiscal_period_events WHERE fiscal_period_id=NEW.id AND to_status='review')
                  AND m.review_version=(SELECT max(review_version) FROM accounting.period_review_manifests WHERE fiscal_period_id=NEW.id)) THEN
                RAISE EXCEPTION 'Review requires a new protected retained review manifest.' USING ERRCODE='23514';
            END IF;
            PERFORM accounting.assert_period_review_manifest_current(NEW.id);
        ELSIF NEW.status='closed' AND NEW.status IS DISTINCT FROM OLD.status THEN
            SELECT id INTO prepared FROM accounting.period_close_preparations WHERE fiscal_period_id=NEW.id;
            IF prepared IS NULL THEN RAISE EXCEPTION 'Close requires a bound retained review manifest.'; END IF;
            PERFORM accounting.assert_period_review_manifest_current(NEW.id,prepared);
        END IF;
    ELSE
        IF NOT EXISTS(SELECT 1 FROM accounting.fiscal_periods WHERE id=NEW.fiscal_period_id AND status='review') THEN
            RAISE EXCEPTION 'Close preparation requires a reviewed period and retained manifest.';
        END IF;
        PERFORM accounting.assert_period_review_manifest_current(NEW.fiscal_period_id);
    END IF;
    RETURN NEW;
END;
$$;
CREATE OR REPLACE FUNCTION accounting.bind_period_close_review_manifest()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE prior_setting TEXT;
BEGIN
    prior_setting:=current_setting('accounting.review_manifest_write',true);
    PERFORM set_config('accounting.review_manifest_write','period_close_manifest_bindings',true);
    INSERT INTO accounting.period_close_manifest_bindings(preparation_id,manifest_id,source_digest)
    SELECT NEW.id,id,source_digest FROM accounting.period_review_manifests
    WHERE fiscal_period_id=NEW.fiscal_period_id ORDER BY review_version DESC LIMIT 1;
    IF NOT FOUND THEN RAISE EXCEPTION 'Close preparation requires a retained review manifest.'; END IF;
    PERFORM set_config('accounting.review_manifest_write',coalesce(prior_setting,''),true);
    RETURN NEW;
END;
$$;
CREATE OR REPLACE FUNCTION accounting.recheck_period_review_manifest_commit()
RETURNS trigger LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE period UUID; status TEXT; prepared UUID;
BEGIN
    IF TG_TABLE_NAME='fiscal_periods' THEN period:=NEW.id; ELSE period:=NEW.fiscal_period_id; END IF;
    SELECT p.status INTO status FROM accounting.fiscal_periods p WHERE p.id=period;
    IF status IN ('review','closed') THEN
        SELECT id INTO prepared FROM accounting.period_close_preparations WHERE fiscal_period_id=period;
        PERFORM accounting.assert_period_review_manifest_current(period,prepared);
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS period_review_manifest_admission ON accounting.fiscal_periods;
CREATE TRIGGER period_review_manifest_admission BEFORE UPDATE ON accounting.fiscal_periods
FOR EACH ROW EXECUTE FUNCTION accounting.guard_period_review_manifest_admission();
DROP TRIGGER IF EXISTS period_review_manifest_preparation_admission ON accounting.period_close_preparations;
CREATE TRIGGER period_review_manifest_preparation_admission BEFORE INSERT ON accounting.period_close_preparations
FOR EACH ROW EXECUTE FUNCTION accounting.guard_period_review_manifest_admission();
DROP TRIGGER IF EXISTS period_close_review_manifest_binding ON accounting.period_close_preparations;
CREATE TRIGGER period_close_review_manifest_binding AFTER INSERT ON accounting.period_close_preparations
FOR EACH ROW EXECUTE FUNCTION accounting.bind_period_close_review_manifest();
DROP TRIGGER IF EXISTS period_review_manifest_commit ON accounting.fiscal_periods;
CREATE CONSTRAINT TRIGGER period_review_manifest_commit AFTER UPDATE ON accounting.fiscal_periods
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION accounting.recheck_period_review_manifest_commit();
DROP TRIGGER IF EXISTS period_review_manifest_preparation_commit ON accounting.period_close_preparations;
CREATE CONSTRAINT TRIGGER period_review_manifest_preparation_commit AFTER INSERT ON accounting.period_close_preparations
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION accounting.recheck_period_review_manifest_commit();

CREATE OR REPLACE FUNCTION accounting.period_review_manifest_blockers(p_period UUID)
RETURNS TABLE(source_type TEXT,source_id UUID,effective_date DATE,amount NUMERIC(18,2),reason TEXT,account_id UUID)
LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE state JSONB; cutoff DATE;
BEGIN
    SELECT p.end_date INTO cutoff FROM accounting.fiscal_periods p WHERE p.id=p_period AND p.status IN ('review','closed');
    IF NOT FOUND THEN RETURN; END IF;
    state:=accounting.period_review_manifest_state(p_period);
    IF coalesce((state->>'current')::boolean,false) THEN RETURN; END IF;
    RETURN QUERY SELECT 'period_review_manifest'::text,p_period,cutoff,NULL::numeric(18,2),
        CASE WHEN state->>'manifest_id' IS NULL THEN 'retained_review_manifest_required' ELSE 'retained_review_source_changed' END,NULL::uuid;
END;
$$;
DO $$ BEGIN
    IF to_regprocedure('accounting.period_sources_before_review_manifest(uuid)') IS NULL THEN
        ALTER FUNCTION accounting.period_source_blockers(UUID) RENAME TO period_sources_before_review_manifest;
    END IF;
END; $$;
CREATE OR REPLACE FUNCTION accounting.period_source_blockers(p_period_id UUID)
RETURNS TABLE(source_type TEXT,source_id UUID,effective_date DATE,amount NUMERIC(18,2),reason TEXT,account_id UUID)
LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
    SELECT * FROM accounting.period_sources_before_review_manifest(p_period_id)
    UNION ALL SELECT * FROM accounting.period_review_manifest_blockers(p_period_id);
$$;
CREATE OR REPLACE VIEW accounting.period_source_close_state AS
SELECT period.id AS fiscal_period_id,period.status AS fiscal_period_status,blockers.blocker_count,
    CASE WHEN blockers.blocker_count=0 THEN 'supported_source_gate_clear'
         WHEN period.status='closed' THEN 'closed_source_review_required'
         ELSE 'blocked_unreconciled_sources' END AS source_close_status,
    'dated_source_review_manifest_v1'::text AS coverage_policy,false AS comprehensive_source_coverage,
    ARRAY['treasury','collector','lending','tax','period_assessment','liabilities','review_manifest']::text[] AS source_families
FROM accounting.fiscal_periods period
CROSS JOIN LATERAL (SELECT count(*) AS blocker_count FROM accounting.period_source_blockers(period.id)) blockers;

DO $$ DECLARE signature REGPROCEDURE; role_name TEXT; table_name TEXT; BEGIN
    FOR signature IN SELECT p.oid::regprocedure FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
      WHERE n.nspname='accounting' AND p.proname=ANY(ARRAY[
        'guard_period_review_manifest_write','period_review_additional_evidence','lock_period_review_additional_sources',
        'period_review_source_snapshot','lock_period_review_manifest_sources','period_review_manifest_state',
        'require_period_review_manifest_actor','assert_period_review_manifest_current',
        'set_fiscal_period_status_without_review_manifest','prepare_period_close_without_review_manifest','post_period_close_without_review_manifest',
        'set_fiscal_period_status','prepare_period_close','post_period_close','guard_period_review_manifest_admission',
        'bind_period_close_review_manifest','recheck_period_review_manifest_commit',
        'period_review_manifest_blockers','period_sources_before_review_manifest','period_source_blockers']) LOOP
        EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC',signature);
        FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
            IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN EXECUTE format('REVOKE ALL ON FUNCTION %s FROM %I',signature,role_name); END IF;
        END LOOP;
    END LOOP;
    FOREACH table_name IN ARRAY ARRAY['period_review_manifests','period_close_manifest_bindings','period_source_close_state'] LOOP
        EXECUTE format('REVOKE ALL ON accounting.%I FROM PUBLIC',table_name);
        FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
            IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN EXECUTE format('REVOKE ALL ON accounting.%I FROM %I',table_name,role_name); END IF;
        END LOOP;
    END LOOP;
END; $$;
COMMENT ON TABLE accounting.period_review_manifests IS
'Immutable exact economic source and preclose ledger identity retained by authorized open-to-review transition. No historical backfill, acknowledgement override or comprehensive readiness claim.';
COMMENT ON FUNCTION accounting.period_review_manifest_state(UUID) IS
'Private scoped reader returns only retained identity, digests, counts and live equality; no Treasury/lending source snapshot payload. Late dated facts stay recorded and make retained history stale.';
COMMIT;
