BEGIN;

-- Keep the original authoritative Treasury/Collector inventory and compose all
-- supported adapters at the shared database boundary used by close and reports.
DO $$ BEGIN
    IF to_regprocedure('accounting.period_initial_source_blockers(uuid)') IS NULL THEN
        ALTER FUNCTION accounting.period_source_blockers(UUID) RENAME TO period_initial_source_blockers;
    END IF;
    IF to_regprocedure('accounting.assert_period_initial_source_complete(uuid)') IS NULL THEN
        ALTER FUNCTION accounting.assert_period_source_complete(UUID) RENAME TO assert_period_initial_source_complete;
    END IF;
END; $$;

CREATE OR REPLACE FUNCTION accounting.period_liability_source_blockers(p_period_id UUID)
RETURNS TABLE(source_type TEXT,source_id UUID,effective_date DATE,amount NUMERIC(18,2),reason TEXT,account_id UUID)
LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
    SELECT 'liability_control'::text,account.id,period.end_date,reconciliation.difference::numeric(18,2),
        CASE WHEN reconciliation.unregistered_line_count>0 THEN 'liability_lines_unregistered'
             ELSE 'liability_schedule_difference' END,NULL::uuid
    FROM accounting.fiscal_periods period
    CROSS JOIN LATERAL accounting.liability_control_reconciliation(period.end_date) reconciliation
    JOIN accounting.accounts account ON account.code=reconciliation.account_code
    WHERE period.id=p_period_id AND (reconciliation.difference<>0 OR reconciliation.unregistered_line_count>0);
$$;

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

CREATE OR REPLACE FUNCTION accounting.assert_period_source_complete(p_period_id UUID)
RETURNS VOID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
    -- Legacy acquires journal/source locks first in the established fixed order.
    -- These plus liability and Treasury locks protect the composed fresh query.
    PERFORM accounting.assert_period_legacy_source_complete(p_period_id);
    LOCK TABLE accounting.liability_obligations,accounting.liability_line_claims,
        accounting.treasury_cash_mappings,accounting.treasury_receipt_preparations,
        accounting.treasury_receipt_postings,treasury.event_revisions,
        treasury.receipts,treasury.applications IN SHARE MODE;
    PERFORM accounting.assert_period_initial_source_complete(p_period_id);
END;
$$;

CREATE OR REPLACE VIEW accounting.period_source_close_state AS
SELECT period.id AS fiscal_period_id,period.status AS fiscal_period_status,blockers.blocker_count,
    CASE WHEN blockers.blocker_count=0 THEN 'supported_source_gate_clear'
         WHEN period.status='closed' THEN 'closed_source_review_required'
         ELSE 'blocked_unreconciled_sources' END AS source_close_status,
    'lending_treasury_liability_v2'::text AS coverage_policy,
    false AS comprehensive_source_coverage,
    ARRAY['treasury','collector','lending','tax','period_assessment','liabilities']::text[] AS source_families
FROM accounting.fiscal_periods period
CROSS JOIN LATERAL (SELECT count(*) AS blocker_count FROM accounting.period_source_blockers(period.id)) blockers;

DO $$ DECLARE role_name text; function_name text; BEGIN
    FOREACH role_name IN ARRAY ARRAY['PUBLIC','anon','authenticated','service_role'] LOOP
        IF role_name='PUBLIC' OR EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
            FOREACH function_name IN ARRAY ARRAY['period_initial_source_blockers(uuid)',
                'period_liability_source_blockers(uuid)','period_source_blockers(uuid)',
                'assert_period_initial_source_complete(uuid)','assert_period_source_complete(uuid)'] LOOP
                EXECUTE format('REVOKE ALL ON FUNCTION accounting.%s FROM %s',function_name,
                    CASE WHEN role_name='PUBLIC' THEN 'PUBLIC' ELSE quote_ident(role_name) END);
            END LOOP;
            EXECUTE format('REVOKE ALL ON accounting.period_source_close_state FROM %s',
                CASE WHEN role_name='PUBLIC' THEN 'PUBLIC' ELSE quote_ident(role_name) END);
        END IF;
    END LOOP;
END; $$;

COMMENT ON FUNCTION accounting.period_source_blockers(UUID) IS
'Composed authoritative source blockers. Exact audited receipt cash clears only its original event; application/correction/Collector adapters remain independently required. Generic liability balances may remain unpaid when every posted control line is attributed and reconciled.';
COMMIT;
