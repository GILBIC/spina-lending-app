BEGIN;

-- Preserve the conservative lineage inventory. Filter at the legacy boundary,
-- not only its public UNION, because its own close triggers are authoritative.
DO $$ BEGIN
    IF to_regprocedure('accounting.period_legacy_uncomposed_source_blockers(uuid)') IS NULL THEN
        ALTER FUNCTION accounting.period_legacy_source_blockers(UUID) RENAME TO period_legacy_uncomposed_source_blockers;
    END IF;
END; $$;

CREATE OR REPLACE FUNCTION accounting.proven_treasury_application_exact(p_application UUID,p_transaction UUID DEFAULT NULL)
RETURNS BOOLEAN LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE result BOOLEAN;
BEGIN
    -- Avoid compiling the source measurement tree for a nonexistent audit.
    IF NOT EXISTS (SELECT 1 FROM accounting.treasury_application_postings p
        WHERE p.application_id=p_application AND (p_transaction IS NULL OR p.transaction_id=p_transaction)) THEN
        RETURN false;
    END IF;
    SELECT posting.exact_posted AND NOT posting.correction_pending
        AND EXISTS (SELECT 1 FROM accounting.book_identity book WHERE book.id=posting.book_id)
        AND EXISTS (SELECT 1 FROM accounting.treasury_receipt_posting_status receipt
            WHERE receipt.receipt_id=posting.receipt_id AND receipt.event_id=posting.event_id
              AND receipt.book_id=posting.book_id AND receipt.treasury_account_id=posting.treasury_account_id
              AND receipt.exact_posted AND NOT receipt.correction_pending)
    INTO result FROM accounting.treasury_application_posting_status posting
    WHERE posting.application_id=p_application AND (p_transaction IS NULL OR posting.transaction_id=p_transaction);
    RETURN coalesce(result,false);
END;
$$;

CREATE OR REPLACE FUNCTION accounting.period_treasury_application_blockers(p_period_id UUID)
RETURNS TABLE(source_type TEXT,source_id UUID,effective_date DATE,amount NUMERIC(18,2),reason TEXT,account_id UUID)
LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
    WITH population AS (
        SELECT application.id,application.account_id,application.amount,
            (application.created_at AT TIME ZONE 'Asia/Manila')::date AS recording_date,
            CASE WHEN jsonb_typeof(application.source_result->'transaction_ids')='array'
                 THEN jsonb_array_length(application.source_result->'transaction_ids') ELSE -1 END AS expected_links,
            count(source.id) AS actual_links,
            min(source.collection_date) FILTER (WHERE source.collection_date BETWEEN period.start_date AND period.end_date) AS collection_date,
            min((source.voided_at AT TIME ZONE 'Asia/Manila')::date) FILTER (
                WHERE source.is_voided AND (source.voided_at AT TIME ZONE 'Asia/Manila')::date BETWEEN period.start_date AND period.end_date) AS void_date,
            period.start_date,period.end_date
        FROM accounting.fiscal_periods period CROSS JOIN treasury.applications application
        LEFT JOIN lending.collection_transactions source ON
            (CASE WHEN jsonb_typeof(application.source_result->'transaction_ids')='array'
                  THEN application.source_result->'transaction_ids' ELSE '[]'::jsonb END) ? source.id::text
            AND source.funding_source='treasury_receipt'
            AND source.funding_receipt_id=application.receipt_id AND source.funding_account_id=application.account_id
        WHERE period.id=p_period_id
        GROUP BY application.id,period.start_date,period.end_date
    ), scoped AS (
        SELECT population.*,coalesce(collection_date,void_date,
            CASE WHEN (expected_links<=0 OR expected_links<>actual_links)
                      AND recording_date BETWEEN start_date AND end_date THEN recording_date END) AS source_date
        FROM population
    )
    SELECT 'treasury_application'::text,source.id,source.source_date,source.amount,
        'treasury_application_protected_posting_incomplete'::text,source.account_id
    FROM scoped source
    WHERE source.source_date IS NOT NULL AND NOT accounting.proven_treasury_application_exact(source.id,NULL);
$$;

CREATE OR REPLACE FUNCTION accounting.period_legacy_source_blockers(p_period_id UUID)
RETURNS TABLE(source_type TEXT,source_id UUID,effective_date DATE,amount NUMERIC(18,2),reason TEXT,account_id UUID)
LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE blocker RECORD; application UUID;
BEGIN
    FOR blocker IN SELECT * FROM accounting.period_legacy_uncomposed_source_blockers(p_period_id) LOOP
        IF blocker.source_type IN ('eir_period_end','ecl_period_end') THEN
            IF accounting.period_loan_assessment_exact(p_period_id,blocker.source_id) THEN CONTINUE; END IF;
        ELSIF blocker.source_type='collection' AND blocker.reason='treasury_collection_application_mapping_required' THEN
            SELECT p.application_id INTO application FROM accounting.treasury_application_postings p
            WHERE p.transaction_id=blocker.source_id;
            IF application IS NOT NULL AND accounting.proven_treasury_application_exact(application,blocker.source_id) THEN CONTINUE; END IF;
        END IF;
        RETURN QUERY SELECT blocker.source_type,blocker.source_id,blocker.effective_date,
            blocker.amount,blocker.reason,blocker.account_id;
    END LOOP;
    RETURN QUERY SELECT * FROM accounting.period_treasury_application_blockers(p_period_id);
END;
$$;

CREATE OR REPLACE FUNCTION accounting.assert_period_legacy_source_complete(p_period_id UUID)
RETURNS VOID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM accounting.fiscal_periods WHERE id=p_period_id) THEN
        RAISE EXCEPTION 'Accounting period was not found.';
    END IF;
    IF current_setting('transaction_isolation')<>'read committed' THEN
        RAISE EXCEPTION 'Source-complete period close requires a READ COMMITTED transaction.';
    END IF;
    -- Preserve 0143's full relation order before taking additional proof locks.
    LOCK TABLE
        lending.client_renewal_requests,lending.collection_remittances,
        lending.collection_transaction_voids,lending.collection_transactions,
        lending.loan_disbursement_cancellations,lending.loan_disbursement_events,
        lending.loan_renewal_execution_events,lending.loans,
        accounting.accounts,accounting.fiscal_periods,accounting.journal_entries,accounting.journal_lines,
        accounting.loan_disbursement_journal_draft_preparations,
        accounting.loan_disbursement_journal_postings,accounting.loan_disbursement_journal_reversals,
        accounting.regular_journal_draft_preparations,accounting.regular_journal_draft_preparation_entries,
        accounting.regular_journal_posting_sets,accounting.regular_journal_posting_entries,
        accounting.regular_journal_reversal_sets,accounting.regular_journal_reversal_entries,
        accounting.remittance_transfer_evidence,accounting.remittance_transfer_journal_preparations,
        accounting.remittance_transfer_journal_postings,accounting.remittance_transfer_journal_reversals,
        accounting.seven_by_seven_journal_draft_preparations,
        accounting.seven_by_seven_journal_postings,accounting.seven_by_seven_journal_posting_lines,
        accounting.seven_by_seven_journal_reversals,accounting.seven_by_seven_journal_reversal_lines,
        accounting.ecl_quantitative_measurements,
        accounting.v1_tax_rule_evidence,accounting.v1_dst_evidence,accounting.v1_percentage_tax_evidence,
        accounting.v1_tax_liability_preparations,accounting.v1_tax_liability_postings,
        accounting.v1_tax_return_evidence,accounting.v1_tax_return_liability_items,
        accounting.v1_tax_payment_evidence,accounting.v1_tax_settlement_preparations,accounting.v1_tax_settlement_postings,
        accounting.v1_tax_adjustment_evidence,accounting.v1_tax_adjustment_preparations,accounting.v1_tax_adjustment_postings,
        accounting.v1_tax_additional_amendment_evidence,accounting.v1_tax_additional_liability_preparations,accounting.v1_tax_additional_liability_postings,
        accounting.v1_tax_additional_payment_evidence,accounting.v1_tax_additional_settlement_preparations,accounting.v1_tax_additional_settlement_postings,
        accounting.v1_tax_recoverable_refund_evidence,accounting.v1_tax_recoverable_refund_preparations,accounting.v1_tax_recoverable_refund_postings,
        accounting.v1_tax_recoverable_credit_evidence,accounting.v1_tax_recoverable_credit_preparations,accounting.v1_tax_recoverable_credit_postings,
        treasury.loan_payouts
    IN SHARE MODE;
    PERFORM accounting.lock_loan_period_assessment_sources();
    LOCK TABLE accounting.loan_period_assessment_preparations,accounting.loan_period_assessment_postings,
        lending.clients,accounting.seven_by_seven_policy_decisions,accounting.seven_by_seven_policy_decision_voids,
        accounting.seven_by_seven_eir_initial_carrying_anchors,accounting.seven_by_seven_eir_initial_carrying_anchor_voids,
        lending.seven_by_seven_extra_principal_adjustments,
        accounting.liability_obligations,accounting.liability_line_claims,
        accounting.treasury_cash_mappings,accounting.treasury_receipt_preparations,accounting.treasury_receipt_postings,
        treasury.event_revisions,treasury.receipts,treasury.applications,
        accounting.treasury_application_preparations,accounting.treasury_application_postings,
        treasury.collector_actions,treasury.collector_cases,treasury.collector_credits,treasury.collector_entries,
        treasury.collector_openings,treasury.collector_resolutions,treasury.collector_settlements,
        treasury.events,treasury.movement_lines,treasury.opening_positions,treasury.accounts,treasury.source_links
    IN SHARE MODE;
    -- A fresh volatile inventory after every wait; retained until deferred commit
    -- checks. Late sources remain recordable after commit and restore blockers.
    IF EXISTS (SELECT 1 FROM accounting.period_legacy_source_blockers(p_period_id)) THEN
        RAISE EXCEPTION 'Accounting period has an unreconciled legacy source; review authorized lending and accounting evidence.' USING ERRCODE='23514';
    END IF;
END;
$$;

-- Rebind the small public composition to the filtered legacy function. Keep the
-- original receipt recognition filter and every unsupported liability/source.
CREATE OR REPLACE FUNCTION accounting.period_source_blockers(p_period_id UUID)
RETURNS TABLE(source_type TEXT,source_id UUID,effective_date DATE,amount NUMERIC(18,2),reason TEXT,account_id UUID)
LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
    SELECT initial.* FROM accounting.period_initial_source_blockers(p_period_id) initial
    WHERE NOT (initial.source_type='treasury_event' AND EXISTS (
        SELECT 1 FROM accounting.treasury_receipt_posting_status posting
        WHERE posting.event_id=initial.source_id AND posting.exact_posted AND NOT posting.correction_pending
    ))
    UNION ALL SELECT * FROM accounting.period_legacy_source_blockers(p_period_id)
    UNION ALL SELECT * FROM accounting.period_liability_source_blockers(p_period_id);
$$;

CREATE OR REPLACE VIEW accounting.period_source_close_state AS
SELECT period.id AS fiscal_period_id,period.status AS fiscal_period_status,blockers.blocker_count,
    CASE WHEN blockers.blocker_count=0 THEN 'supported_source_gate_clear'
         WHEN period.status='closed' THEN 'closed_source_review_required'
         ELSE 'blocked_unreconciled_sources' END AS source_close_status,
    'lending_treasury_proven_assessment_v3'::text AS coverage_policy,
    false AS comprehensive_source_coverage,
    ARRAY['treasury','collector','lending','tax','period_assessment','liabilities']::text[] AS source_families
FROM accounting.fiscal_periods period
CROSS JOIN LATERAL (SELECT count(*) AS blocker_count FROM accounting.period_source_blockers(period.id)) blockers;

DO $$ DECLARE role_name TEXT; function_name TEXT; BEGIN
    FOREACH role_name IN ARRAY ARRAY['PUBLIC','anon','authenticated','service_role'] LOOP
        IF role_name='PUBLIC' OR EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
            FOREACH function_name IN ARRAY ARRAY['period_legacy_uncomposed_source_blockers(uuid)',
                'proven_treasury_application_exact(uuid,uuid)','period_treasury_application_blockers(uuid)',
                'period_legacy_source_blockers(uuid)','assert_period_legacy_source_complete(uuid)','period_source_blockers(uuid)'] LOOP
                EXECUTE format('REVOKE ALL ON FUNCTION accounting.%s FROM %s',function_name,
                    CASE WHEN role_name='PUBLIC' THEN 'PUBLIC' ELSE quote_ident(role_name) END);
            END LOOP;
            EXECUTE format('REVOKE ALL ON accounting.period_source_close_state FROM %s',
                CASE WHEN role_name='PUBLIC' THEN 'PUBLIC' ELSE quote_ident(role_name) END);
        END IF;
    END LOOP;
END; $$;

COMMENT ON FUNCTION accounting.period_legacy_source_blockers(UUID) IS
'Conservative raw legacy inventory plus raw Treasury applications, discharging only current exact retained application and actual-cutoff assessment proofs. Other controls, source families and tax obligations remain authoritative. Internal account scope requires authorized projection.';
COMMENT ON FUNCTION accounting.period_treasury_application_blockers(UUID) IS
'Raw application inventory independent of preparation queues, scoped to actual collection/void dates with Manila recording-date fallback for incomplete source links. Original source amounts are evidence, not additive financial totals.';
COMMIT;
