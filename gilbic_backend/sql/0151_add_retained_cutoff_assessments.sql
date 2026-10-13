BEGIN;

-- Actual dated no-change proof. This deliberately neither backdates the ECL
-- engine nor manufactures a journal. Composition is a separate migration.
CREATE TABLE IF NOT EXISTS accounting.loan_period_assessment_preparations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    book_id UUID NOT NULL REFERENCES accounting.book_identity(id) ON DELETE RESTRICT,
    fiscal_period_id UUID NOT NULL REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    cutoff_date DATE NOT NULL,
    measurement_id UUID NOT NULL REFERENCES accounting.ecl_quantitative_measurements(id) ON DELETE RESTRICT,
    source_digest TEXT NOT NULL CHECK (source_digest ~ '^[0-9a-f]{64}$'),
    source_snapshot JSONB NOT NULL CHECK (jsonb_typeof(source_snapshot) = 'object'),
    policy_version TEXT NOT NULL CHECK (policy_version = 'regular_release_day_cutoff_assessment_v1'),
    review_rationale TEXT NOT NULL CHECK (length(btrim(review_rationale)) >= 20),
    prepared_by UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    prepared_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (book_id,fiscal_period_id,loan_id,source_digest)
);
CREATE TABLE IF NOT EXISTS accounting.loan_period_assessment_postings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    preparation_id UUID NOT NULL UNIQUE REFERENCES accounting.loan_period_assessment_preparations(id) ON DELETE RESTRICT,
    book_id UUID NOT NULL REFERENCES accounting.book_identity(id) ON DELETE RESTRICT,
    fiscal_period_id UUID NOT NULL REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    source_digest TEXT NOT NULL CHECK (source_digest ~ '^[0-9a-f]{64}$'),
    confirmed_by UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    confirmed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE accounting.loan_period_assessment_preparations ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounting.loan_period_assessment_postings ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION accounting.guard_loan_period_assessment_audit()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
    IF TG_OP = 'INSERT' AND coalesce(current_setting('accounting.cutoff_assessment_insert_allowed',true),'')='on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Retained cutoff assessment audits are immutable and require the protected workflow.' USING ERRCODE='55000';
END;
$$;
DROP TRIGGER IF EXISTS cutoff_assessment_preparation_guard ON accounting.loan_period_assessment_preparations;
CREATE TRIGGER cutoff_assessment_preparation_guard BEFORE INSERT OR UPDATE OR DELETE ON accounting.loan_period_assessment_preparations
FOR EACH ROW EXECUTE FUNCTION accounting.guard_loan_period_assessment_audit();
DROP TRIGGER IF EXISTS cutoff_assessment_posting_guard ON accounting.loan_period_assessment_postings;
CREATE TRIGGER cutoff_assessment_posting_guard BEFORE INSERT OR UPDATE OR DELETE ON accounting.loan_period_assessment_postings
FOR EACH ROW EXECUTE FUNCTION accounting.guard_loan_period_assessment_audit();
DROP TRIGGER IF EXISTS cutoff_assessment_preparation_truncate_guard ON accounting.loan_period_assessment_preparations;
CREATE TRIGGER cutoff_assessment_preparation_truncate_guard BEFORE TRUNCATE ON accounting.loan_period_assessment_preparations
FOR EACH STATEMENT EXECUTE FUNCTION accounting.guard_loan_period_assessment_audit();
DROP TRIGGER IF EXISTS cutoff_assessment_posting_truncate_guard ON accounting.loan_period_assessment_postings;
CREATE TRIGGER cutoff_assessment_posting_truncate_guard BEFORE TRUNCATE ON accounting.loan_period_assessment_postings
FOR EACH STATEMENT EXECUTE FUNCTION accounting.guard_loan_period_assessment_audit();

CREATE OR REPLACE FUNCTION accounting.loan_period_assessment_candidate(p_period UUID,p_loan UUID)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE
    period_row accounting.fiscal_periods%ROWTYPE;
    book_row accounting.book_identity%ROWTYPE;
    anchor RECORD;
    measured accounting.ecl_quantitative_measurements%ROWTYPE;
    allowance_row accounting.ecl_allowance_postings%ROWTYPE;
    label_row accounting.ecl_credit_risk_label_reviews%ROWTYPE;
    blockers TEXT[] := ARRAY[]::text[];
    snapshot JSONB;
    flows JSONB;
    ledger JSONB;
    forward_rows JSONB;
    balance_1100 NUMERIC;
    balance_1110 NUMERIC;
    balance_1120 NUMERIC;
    balance_1190 NUMERIC;
    exact_allowance BOOLEAN := false;
BEGIN
    SELECT * INTO period_row FROM accounting.fiscal_periods WHERE id=p_period;
    IF NOT FOUND THEN
        RETURN jsonb_build_object('ready',false,'blockers',jsonb_build_array('fiscal_period_required'));
    END IF;
    SELECT * INTO book_row FROM accounting.book_identity;
    IF NOT FOUND THEN blockers:=array_append(blockers,'accounting_book_identity_required'); END IF;
    -- A fresh review must not bless changed chart meaning merely because the
    -- numeric component sums still match. Retirement/name changes do not alter
    -- the accounting meaning of an already posted historical balance.
    IF EXISTS (SELECT 1 FROM (VALUES
        ('1100','loans_receivable_regular','asset','debit'),
        ('1110','loans_receivable_7x7','asset','debit'),
        ('1120','accrued_interest_receivable','asset','debit'),
        ('1190','allowance_expected_credit_loss','asset','credit'),
        ('5000','credit_loss_expense','expense','debit')
    ) expected(code,system_key,account_type,normal_balance)
    WHERE NOT EXISTS (SELECT 1 FROM accounting.accounts account
        WHERE (account.code,account.system_key,account.account_type,account.normal_balance)
          =(expected.code,expected.system_key,expected.account_type,expected.normal_balance))) THEN
        blockers:=array_append(blockers,'loan_control_chart_meaning_mismatch');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM lending.loans WHERE id=p_loan) THEN
        RETURN jsonb_build_object('ready',false,'blockers',jsonb_build_array('loan_required'));
    END IF;
    -- No volatile queue or fiscal status is an economic digest input.
    snapshot:=jsonb_build_object('policy_version','regular_release_day_cutoff_assessment_v1',
        'book',to_jsonb(book_row),'period_id',p_period,'start_date',period_row.start_date,
        'cutoff_date',period_row.end_date,'loan',(SELECT to_jsonb(l) FROM lending.loans l WHERE id=p_loan));
    IF 1 <> (SELECT count(*) FROM accounting.greenfield_regular_eir_anchor_readiness WHERE loan_id=p_loan) THEN
        RETURN jsonb_build_object('ready',false,'blockers',to_jsonb(array_append(blockers,'single_protected_regular_anchor_required')),'snapshot',snapshot);
    END IF;
    SELECT * INTO anchor FROM accounting.greenfield_regular_eir_anchor_readiness WHERE loan_id=p_loan;
    IF EXISTS (SELECT 1 FROM accounting.journal_lines line JOIN accounting.accounts account ON account.id=line.account_id
        WHERE line.journal_entry_id=anchor.journal_entry_id AND line.credit>0
          AND (account.account_type<>'asset' OR account.normal_balance<>'debit'
               OR NOT ((account.code='1010' AND account.system_key='cash_office')
                    OR (account.code='1030' AND account.system_key='cash_bank_gcash')))) THEN
        blockers:=array_append(blockers,'release_cash_chart_meaning_mismatch');
    END IF;
    IF anchor.readiness_status IS DISTINCT FROM 'greenfield_regular_eir_anchor_ready'
       OR NOT EXISTS (SELECT 1 FROM accounting.journal_entries WHERE id=anchor.journal_entry_id AND fiscal_period_id=p_period)
       OR (SELECT due_date FROM lending.loans WHERE id=p_loan) IS DISTINCT FROM anchor.contractual_due_date THEN
        blockers:=array_append(blockers,'protected_regular_anchor_not_exact');
    END IF;
    IF anchor.anchor_date IS DISTINCT FROM period_row.end_date THEN
        blockers:=array_append(blockers,'elapsed_eir_boundary_adapter_required');
    END IF;
    IF (SELECT status FROM lending.loans WHERE id=p_loan) IS DISTINCT FROM 'active'
       OR EXISTS (SELECT 1 FROM lending.loan_contract_schedules WHERE loan_id=p_loan AND id<>anchor.schedule_id)
       OR EXISTS (SELECT 1 FROM lending.collection_transactions WHERE loan_id=p_loan AND collection_date<=period_row.end_date
                  AND (amount>0 OR entry_type IN ('payment','advance')))
       OR EXISTS (SELECT 1 FROM lending.loan_renewal_execution_events WHERE (old_loan_id=p_loan OR new_loan_id=p_loan) AND business_date<=period_row.end_date)
       OR EXISTS (SELECT 1 FROM lending.client_renewal_requests WHERE loan_id=p_loan)
       OR EXISTS (SELECT 1 FROM treasury.loan_payouts WHERE loan_id=p_loan AND status<>'cancelled')
       OR EXISTS (SELECT 1 FROM accounting.ecl_accounting_writeoffs WHERE loan_id=p_loan)
       OR EXISTS (SELECT 1 FROM accounting.ecl_allowance_remeasurements WHERE loan_id=p_loan) THEN
        blockers:=array_append(blockers,'source_state_requires_extended_assessment_adapter');
    END IF;
    SELECT * INTO measured FROM accounting.ecl_quantitative_measurements
    WHERE loan_id=p_loan AND measurement_date=period_row.end_date ORDER BY measurement_version DESC LIMIT 1;
    IF NOT FOUND THEN blockers:=array_append(blockers,'dated_quantitative_measurement_required'); END IF;
    SELECT * INTO label_row FROM accounting.ecl_credit_risk_label_reviews
    WHERE loan_id=p_loan ORDER BY review_version DESC LIMIT 1;
    IF measured.id IS NOT NULL AND (
        measured.schedule_id IS DISTINCT FROM anchor.schedule_id
        OR measured.schedule_version IS DISTINCT FROM anchor.schedule_version
        OR measured.contract_reference IS DISTINCT FROM anchor.contract_reference
        OR measured.original_eir_source_key IS DISTINCT FROM anchor.anchor_source_key
        OR measured.original_eir_policy_version IS DISTINCT FROM anchor.anchor_policy_version
        OR measured.original_daily_eir IS DISTINCT FROM anchor.daily_eir
        OR measured.original_initial_gross_carrying_amount IS DISTINCT FROM anchor.initial_gross_carrying_amount
        OR measured.label_review_id IS DISTINCT FROM label_row.id
        OR measured.label_review_version IS DISTINCT FROM label_row.review_version
        OR measured.stage_label IS DISTINCT FROM 'stage_1_12_month'
        OR label_row.stage_label IS DISTINCT FROM 'stage_1_12_month'
        OR label_row.default_label IS DISTINCT FROM false
        OR label_row.write_off_label IS DISTINCT FROM 'none'
        OR label_row.recovery_label IS DISTINCT FROM 'none'
        OR label_row.snapshot_schedule_id IS DISTINCT FROM anchor.schedule_id
        OR label_row.snapshot_days_past_due IS DISTINCT FROM 0
        OR label_row.snapshot_due_unpaid_amount IS DISTINCT FROM 0
        OR measured.input_snapshot->>'quantitative_input_ready' IS DISTINCT FROM 'true'
    ) THEN blockers:=array_append(blockers,'dated_measurement_source_snapshot_mismatch'); END IF;
    SELECT coalesce(jsonb_agg(jsonb_build_object('installment_number',i.installment_number,
        'due_date',i.due_date,'contractual_amount',i.contractual_amount,
        'allocated_amount',0.00::numeric(18,2),'remaining_amount',i.contractual_amount) ORDER BY i.installment_number),'[]'::jsonb)
    INTO flows FROM lending.loan_contract_installments i WHERE i.schedule_id=anchor.schedule_id;
    IF measured.id IS NOT NULL AND measured.contractual_cash_flow_snapshot IS DISTINCT FROM flows THEN
        blockers:=array_append(blockers,'dated_contractual_cashflow_snapshot_mismatch');
    END IF;
    -- A newer version or revocation is a reason to revisit retained evidence.
    -- Calendar aging alone does not change evidence valid at the actual cutoff.
    SELECT coalesce(jsonb_agg(to_jsonb(e) ORDER BY e.id),'[]'::jsonb) INTO forward_rows
    FROM accounting.ecl_forward_looking_evidence e WHERE e.id=ANY(measured.forward_evidence_ids);
    IF measured.id IS NOT NULL AND (cardinality(measured.forward_evidence_ids)<>jsonb_array_length(forward_rows)
        OR EXISTS (SELECT 1 FROM accounting.ecl_forward_looking_evidence e WHERE e.id=ANY(measured.forward_evidence_ids)
            AND (e.effective_date>period_row.end_date OR period_row.end_date NOT BETWEEN e.forecast_period_start AND e.forecast_period_end
                 OR EXISTS (SELECT 1 FROM accounting.ecl_forward_looking_evidence_revocations r WHERE r.evidence_id=e.id)
                 OR EXISTS (SELECT 1 FROM accounting.ecl_forward_looking_evidence newer WHERE newer.evidence_key=e.evidence_key AND newer.version>e.version)))) THEN
        blockers:=array_append(blockers,'dated_forward_evidence_required');
    END IF;
    SELECT coalesce(sum(l.debit-l.credit) FILTER (WHERE a.code='1100'),0),
           coalesce(sum(l.debit-l.credit) FILTER (WHERE a.code='1110'),0),
           coalesce(sum(l.debit-l.credit) FILTER (WHERE a.code='1120'),0),
           coalesce(sum(l.credit-l.debit) FILTER (WHERE a.code='1190'),0)
    INTO balance_1100,balance_1110,balance_1120,balance_1190
    FROM accounting.journal_entries j JOIN accounting.journal_lines l ON l.journal_entry_id=j.id
    JOIN accounting.accounts a ON a.id=l.account_id
    WHERE j.status='posted' AND j.posting_date<=period_row.end_date AND l.loan_id=p_loan;
    IF balance_1100 IS DISTINCT FROM anchor.initial_gross_carrying_amount OR balance_1110<>0 OR balance_1120<>0 THEN
        blockers:=array_append(blockers,'dated_receivable_components_not_reconciled');
    END IF;
    SELECT * INTO allowance_row FROM accounting.ecl_allowance_postings WHERE measurement_id=measured.id;
    IF measured.ecl_amount=0 THEN
        exact_allowance:=balance_1190=0 AND allowance_row.id IS NULL
            AND NOT EXISTS (SELECT 1 FROM accounting.ecl_allowance_postings WHERE loan_id=p_loan);
    ELSIF measured.ecl_amount>0 THEN
        SELECT EXISTS (
            SELECT 1 FROM accounting.ecl_allowance_draft_preparations p
            JOIN accounting.journal_entries j ON j.id=p.journal_entry_id
            JOIN accounting.accounts expense ON expense.id=p.credit_loss_expense_account_id
            JOIN accounting.accounts contra ON contra.id=p.allowance_account_id
            WHERE p.id=allowance_row.preparation_id AND p.measurement_id=measured.id
              AND p.measurement_date=period_row.end_date AND p.posting_date=period_row.end_date
              AND p.fiscal_period_id=p_period AND p.loan_id=p_loan AND p.client_id=anchor.client_id
              AND p.measurement_version=measured.measurement_version AND p.calculation_digest=measured.calculation_digest
              AND p.allowance_amount=measured.ecl_amount AND p.prior_allowance_balance=0
              AND expense.system_key='credit_loss_expense' AND contra.system_key='allowance_expected_credit_loss' AND contra.code='1190'
              AND (allowance_row.measurement_id,allowance_row.loan_id,allowance_row.client_id,allowance_row.measurement_version,
                   allowance_row.calculation_digest,allowance_row.journal_entry_id,allowance_row.source_event_key,
                   allowance_row.posting_date,allowance_row.fiscal_period_id,allowance_row.credit_loss_expense_account_id,
                   allowance_row.allowance_account_id,allowance_row.allowance_amount,allowance_row.prior_allowance_balance,
                   allowance_row.preparation_review_token,allowance_row.preparation_digest,allowance_row.draft_policy_version)
                  IS NOT DISTINCT FROM
                  (p.measurement_id,p.loan_id,p.client_id,p.measurement_version,p.calculation_digest,p.journal_entry_id,p.source_event_key,
                   p.posting_date,p.fiscal_period_id,p.credit_loss_expense_account_id,p.allowance_account_id,p.allowance_amount,
                   p.prior_allowance_balance,p.preparation_review_token,p.preparation_digest,p.draft_policy_version)
              AND allowance_row.resulting_allowance_balance=measured.ecl_amount AND j.entry_number=allowance_row.entry_number
              AND accounting.legacy_two_line_posted_exact(j.id,'ecl_allowance:'||measured.id::text,'ecl_allowance',measured.id::text,
                    period_row.end_date,p_period,expense.id,contra.id,measured.ecl_amount,anchor.client_id,p_loan)
              AND 2=(SELECT count(*) FROM accounting.ecl_allowance_posting_lines WHERE posting_id=allowance_row.id)
              AND NOT EXISTS (
                  SELECT 1 FROM accounting.ecl_allowance_posting_lines retained
                  LEFT JOIN accounting.journal_lines actual ON actual.journal_entry_id=j.id AND actual.line_number=retained.line_number
                  LEFT JOIN accounting.accounts a ON a.id=actual.account_id
                  WHERE retained.posting_id=allowance_row.id AND (actual.id IS NULL
                    OR (retained.account_id,retained.account_system_key,retained.debit,retained.credit,retained.client_id,retained.loan_id)
                       IS DISTINCT FROM (actual.account_id,a.system_key,actual.debit,actual.credit,actual.client_id,actual.loan_id)))
        ) AND balance_1190=measured.ecl_amount INTO exact_allowance;
    END IF;
    IF measured.id IS NOT NULL AND NOT coalesce(exact_allowance,false) THEN
        blockers:=array_append(blockers,'dated_allowance_posting_not_reconciled');
    END IF;
    IF EXISTS (SELECT 1 FROM accounting.journal_entries j JOIN accounting.journal_lines l ON l.journal_entry_id=j.id
               JOIN accounting.accounts a ON a.id=l.account_id
               WHERE j.status='posted' AND j.posting_date<=period_row.end_date AND l.loan_id=p_loan
                 AND a.code IN ('1100','1110','1120','1190')
                 AND j.id<>anchor.journal_entry_id AND j.id IS DISTINCT FROM allowance_row.journal_entry_id) THEN
        blockers:=array_append(blockers,'unrecognized_loan_control_journal');
    END IF;
    -- Include actual line identities, not just net balances. Full loan journals
    -- retain the counterparts as well, without relying on the open-period queue.
    SELECT coalesce(jsonb_agg(to_jsonb(j) || jsonb_build_object('lines',(
        SELECT jsonb_agg(to_jsonb(l) || jsonb_build_object('account',to_jsonb(a)) ORDER BY l.line_number)
        FROM accounting.journal_lines l JOIN accounting.accounts a ON a.id=l.account_id WHERE l.journal_entry_id=j.id)) ORDER BY j.posting_date,j.id),'[]'::jsonb)
    INTO ledger FROM accounting.journal_entries j
    WHERE j.status='posted' AND j.posting_date<=period_row.end_date
      AND EXISTS (SELECT 1 FROM accounting.journal_lines WHERE journal_entry_id=j.id AND loan_id=p_loan);
    snapshot:=snapshot || jsonb_build_object('anchor',to_jsonb(anchor),'measurement',to_jsonb(measured),
        'label',to_jsonb(label_row),'contractual_cash_flows',flows,'forward_evidence',forward_rows,
        'allowance_posting',to_jsonb(allowance_row),
        'allowance_preparation',(SELECT to_jsonb(p) FROM accounting.ecl_allowance_draft_preparations p WHERE id=allowance_row.preparation_id),
        'allowance_retained_lines',(SELECT jsonb_agg(to_jsonb(l) ORDER BY line_number) FROM accounting.ecl_allowance_posting_lines l WHERE posting_id=allowance_row.id),
        'ledger',ledger,
        'schedule',(SELECT to_jsonb(s) FROM lending.loan_contract_schedules s WHERE id=anchor.schedule_id),
        'registration',(SELECT to_jsonb(r) FROM lending.loan_contract_schedule_registrations r WHERE schedule_id=anchor.schedule_id),
        'disbursement',(SELECT to_jsonb(e) FROM lending.loan_disbursement_events e WHERE id=anchor.disbursement_event_id),
        'receivable_1100',balance_1100,'receivable_1110',balance_1110,'receivable_1120',balance_1120,'allowance_1190',balance_1190);
    RETURN jsonb_build_object('ready',cardinality(blockers)=0,'blockers',to_jsonb(blockers),'snapshot',snapshot,
        'source_digest',encode(sha256(convert_to(snapshot::text,'UTF8')),'hex'));
END;
$$;

CREATE OR REPLACE FUNCTION accounting.lock_loan_period_assessment_sources()
RETURNS VOID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
    IF current_setting('transaction_isolation')<>'read committed' THEN
        RAISE EXCEPTION 'Retained cutoff assessment requires READ COMMITTED.' USING ERRCODE='55000';
    END IF;
    -- Subsequence of 0143's established source order, followed by new sources.
    LOCK TABLE lending.client_renewal_requests,lending.collection_transaction_voids,lending.collection_transactions,
        lending.loan_disbursement_cancellations,lending.loan_disbursement_events,lending.loan_renewal_execution_events,lending.loans,
        accounting.accounts,accounting.fiscal_periods,accounting.journal_entries,accounting.journal_lines,
        accounting.loan_disbursement_journal_draft_preparations,accounting.loan_disbursement_journal_postings,
        accounting.loan_disbursement_journal_reversals,accounting.ecl_quantitative_measurements,treasury.loan_payouts,
        accounting.book_identity,lending.loan_types,lending.loan_contract_schedules,lending.loan_contract_schedule_registrations,
        lending.loan_contract_installments,lending.loan_installment_payment_allocations,
        accounting.ecl_credit_risk_label_reviews,accounting.ecl_forward_looking_evidence,accounting.ecl_forward_looking_evidence_revocations,
        accounting.ecl_allowance_draft_preparations,accounting.ecl_allowance_postings,accounting.ecl_allowance_posting_lines,
        accounting.ecl_allowance_remeasurements,accounting.ecl_accounting_writeoffs
    IN SHARE MODE;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.require_loan_period_assessment_actor(p_actor UUID,p_permission TEXT)
RETURNS VOID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
    IF p_permission IS NULL OR p_permission NOT IN ('accounting.period.close.prepare','accounting.period.close.post') THEN
        RAISE EXCEPTION 'Unsupported cutoff assessment permission.' USING ERRCODE='42501';
    END IF;
    PERFORM 1 FROM core.users actor JOIN core.user_roles membership ON membership.user_id=actor.id
    JOIN core.roles role ON role.id=membership.role_id JOIN core.role_permissions permission ON permission.role_id=role.id
    WHERE actor.id=p_actor AND actor.status='active' AND role.code='management' AND permission.permission_code=p_permission
    FOR SHARE OF actor,membership,role,permission;
    IF NOT FOUND THEN RAISE EXCEPTION 'An active Management actor with cutoff assessment permission is required.' USING ERRCODE='42501'; END IF;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.prepare_loan_period_assessment(p_period UUID,p_loan UUID,p_actor UUID,p_digest TEXT,p_rationale TEXT)
RETURNS UUID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE candidate JSONB; existing UUID; created UUID; old_setting TEXT; period_status TEXT;
BEGIN
    PERFORM accounting.require_loan_period_assessment_actor(p_actor,'accounting.period.close.prepare');
    IF p_digest IS NULL OR p_digest !~ '^[0-9a-f]{64}$' OR length(btrim(coalesce(p_rationale,'')))<20 THEN
        RAISE EXCEPTION 'Exact source digest and substantive cutoff review rationale are required.';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('period-close:'||p_period::text,0));
    SELECT status INTO period_status FROM accounting.fiscal_periods WHERE id=p_period FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Accounting period was not found.'; END IF;
    PERFORM accounting.lock_loan_period_assessment_sources();
    -- Serialize audit writes across periods; SHARE then INSERT would deadlock
    -- when independent preparers simultaneously upgraded their table locks.
    LOCK TABLE accounting.loan_period_assessment_preparations,accounting.loan_period_assessment_postings IN SHARE ROW EXCLUSIVE MODE;
    candidate:=accounting.loan_period_assessment_candidate(p_period,p_loan);
    IF coalesce((candidate->>'ready')::boolean,false) IS NOT true THEN
        RAISE EXCEPTION 'Dated loan assessment is blocked; inspect authorized source evidence.' USING ERRCODE='23514';
    END IF;
    IF candidate->>'source_digest' IS DISTINCT FROM p_digest THEN RAISE EXCEPTION 'Cutoff source digest changed; review current evidence.' USING ERRCODE='40001'; END IF;
    SELECT id INTO existing FROM accounting.loan_period_assessment_preparations
    WHERE fiscal_period_id=p_period AND loan_id=p_loan AND source_digest=p_digest;
    IF FOUND THEN RETURN existing; END IF;
    IF period_status<>'open' THEN RAISE EXCEPTION 'New cutoff assessment preparation requires an open period.'; END IF;
    old_setting:=current_setting('accounting.cutoff_assessment_insert_allowed',true);
    PERFORM set_config('accounting.cutoff_assessment_insert_allowed','on',true);
    INSERT INTO accounting.loan_period_assessment_preparations(book_id,fiscal_period_id,loan_id,cutoff_date,measurement_id,
        source_digest,source_snapshot,policy_version,review_rationale,prepared_by)
    VALUES ((candidate#>>'{snapshot,book,id}')::uuid,p_period,p_loan,(candidate#>>'{snapshot,cutoff_date}')::date,
        (candidate#>>'{snapshot,measurement,id}')::uuid,p_digest,candidate->'snapshot','regular_release_day_cutoff_assessment_v1',btrim(p_rationale),p_actor)
    RETURNING id INTO created;
    PERFORM set_config('accounting.cutoff_assessment_insert_allowed',coalesce(old_setting,''),true);
    RETURN created;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.post_loan_period_assessment(p_preparation UUID,p_actor UUID,p_digest TEXT)
RETURNS UUID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE prepared accounting.loan_period_assessment_preparations%ROWTYPE; candidate JSONB;
    existing UUID; created UUID; old_setting TEXT; period_status TEXT;
BEGIN
    PERFORM accounting.require_loan_period_assessment_actor(p_actor,'accounting.period.close.post');
    SELECT * INTO prepared FROM accounting.loan_period_assessment_preparations WHERE id=p_preparation;
    IF NOT FOUND THEN RAISE EXCEPTION 'Retained cutoff assessment preparation was not found.'; END IF;
    IF p_digest IS DISTINCT FROM prepared.source_digest THEN RAISE EXCEPTION 'Confirmed cutoff digest does not match preparation.'; END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('period-close:'||prepared.fiscal_period_id::text,0));
    SELECT status INTO period_status FROM accounting.fiscal_periods WHERE id=prepared.fiscal_period_id FOR UPDATE;
    PERFORM accounting.lock_loan_period_assessment_sources();
    LOCK TABLE accounting.loan_period_assessment_preparations,accounting.loan_period_assessment_postings IN SHARE ROW EXCLUSIVE MODE;
    SELECT id INTO existing FROM accounting.loan_period_assessment_postings WHERE preparation_id=p_preparation;
    -- Exact historical retry preserves audit identity; live currency is separate.
    IF FOUND THEN RETURN existing; END IF;
    IF period_status<>'open' THEN RAISE EXCEPTION 'New cutoff assessment confirmation requires an open period.'; END IF;
    candidate:=accounting.loan_period_assessment_candidate(prepared.fiscal_period_id,prepared.loan_id);
    IF coalesce((candidate->>'ready')::boolean,false) IS NOT true
       OR candidate->>'source_digest' IS DISTINCT FROM p_digest OR candidate->'snapshot' IS DISTINCT FROM prepared.source_snapshot THEN
        RAISE EXCEPTION 'Cutoff source evidence changed or is blocked after preparation.' USING ERRCODE='40001';
    END IF;
    old_setting:=current_setting('accounting.cutoff_assessment_insert_allowed',true);
    PERFORM set_config('accounting.cutoff_assessment_insert_allowed','on',true);
    INSERT INTO accounting.loan_period_assessment_postings(preparation_id,book_id,fiscal_period_id,loan_id,source_digest,confirmed_by)
    VALUES (prepared.id,prepared.book_id,prepared.fiscal_period_id,prepared.loan_id,p_digest,p_actor) RETURNING id INTO created;
    PERFORM set_config('accounting.cutoff_assessment_insert_allowed',coalesce(old_setting,''),true);
    RETURN created;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.period_loan_assessment_exact(p_period UUID,p_loan UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
    SELECT EXISTS (SELECT 1 FROM accounting.loan_period_assessment_preparations p
        JOIN accounting.loan_period_assessment_postings confirmation ON confirmation.preparation_id=p.id
        JOIN accounting.book_identity book ON book.id=p.book_id
        CROSS JOIN LATERAL accounting.loan_period_assessment_candidate(p_period,p_loan) candidate
        WHERE p.fiscal_period_id=p_period AND p.loan_id=p_loan
          AND confirmation.book_id=p.book_id AND confirmation.fiscal_period_id=p.fiscal_period_id
          AND confirmation.loan_id=p.loan_id AND confirmation.source_digest=p.source_digest
          AND coalesce((candidate->>'ready')::boolean,false)
          AND candidate->>'source_digest'=p.source_digest AND candidate->'snapshot'=p.source_snapshot);
$$;

DO $$ DECLARE role_name TEXT; function_name TEXT; BEGIN
    FOREACH role_name IN ARRAY ARRAY['PUBLIC','anon','authenticated','service_role'] LOOP
        IF role_name='PUBLIC' OR EXISTS (SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
            EXECUTE format('REVOKE ALL ON accounting.loan_period_assessment_preparations,accounting.loan_period_assessment_postings FROM %s',
                CASE WHEN role_name='PUBLIC' THEN 'PUBLIC' ELSE quote_ident(role_name) END);
            FOREACH function_name IN ARRAY ARRAY['guard_loan_period_assessment_audit()',
                'loan_period_assessment_candidate(uuid,uuid)','lock_loan_period_assessment_sources()',
                'require_loan_period_assessment_actor(uuid,text)','prepare_loan_period_assessment(uuid,uuid,uuid,text,text)',
                'post_loan_period_assessment(uuid,uuid,text)','period_loan_assessment_exact(uuid,uuid)'] LOOP
                EXECUTE format('REVOKE ALL ON FUNCTION accounting.%s FROM %s',function_name,
                    CASE WHEN role_name='PUBLIC' THEN 'PUBLIC' ELSE quote_ident(role_name) END);
            END LOOP;
        END IF;
    END LOOP;
END; $$;
COMMENT ON FUNCTION accounting.period_loan_assessment_exact(UUID,UUID) IS
'Live exactness of retained actual-cutoff EIR/ECL proof. Supports protected original Regular release on cutoff plus genuinely dated measurement and exact initial allowance. Does not clear raw source, tax, liability, elapsed-EIR, modification or Treasury blockers.';
COMMIT;
