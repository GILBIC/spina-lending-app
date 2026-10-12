BEGIN;

-- Presentation evidence only: no installation or review changes a monetary line.
CREATE TABLE IF NOT EXISTS accounting.disclosure_policy_versions (
 id UUID PRIMARY KEY, book_id UUID NOT NULL REFERENCES accounting.book_identity(id),
 fiscal_period_id UUID NOT NULL REFERENCES accounting.fiscal_periods(id),
 reporting_policy_id UUID NOT NULL REFERENCES accounting.reporting_policy_versions(id),
 version INTEGER NOT NULL CHECK(version>0), payload JSONB NOT NULL, financing_accounts JSONB NOT NULL,
 actor_user_id UUID NOT NULL REFERENCES core.users(id), created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(fiscal_period_id,version)
);
CREATE TABLE IF NOT EXISTS accounting.journal_disclosure_reviews (
 id UUID PRIMARY KEY, book_id UUID NOT NULL REFERENCES accounting.book_identity(id),
 fiscal_period_id UUID NOT NULL REFERENCES accounting.fiscal_periods(id),
 disclosure_policy_id UUID NOT NULL REFERENCES accounting.disclosure_policy_versions(id),
 journal_entry_id UUID NOT NULL REFERENCES accounting.journal_entries(id),
 version INTEGER NOT NULL CHECK(version>0), payload JSONB NOT NULL,
 source_digest TEXT NOT NULL CHECK(source_digest ~ '^[0-9a-f]{64}$'), snapshot JSONB NOT NULL,
 actor_user_id UUID NOT NULL REFERENCES core.users(id), created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(journal_entry_id,version)
);
DO $$ DECLARE item TEXT; BEGIN
 FOREACH item IN ARRAY ARRAY['disclosure_policy_versions','journal_disclosure_reviews'] LOOP
  EXECUTE format('ALTER TABLE accounting.%I ENABLE ROW LEVEL SECURITY',item);
  EXECUTE format('DROP TRIGGER IF EXISTS disclosure_evidence_write ON accounting.%I',item);
  EXECUTE format('CREATE TRIGGER disclosure_evidence_write BEFORE INSERT OR UPDATE OR DELETE ON accounting.%I FOR EACH ROW EXECUTE FUNCTION accounting.guard_reporting_evidence()',item);
  EXECUTE format('DROP TRIGGER IF EXISTS disclosure_evidence_truncate ON accounting.%I',item);
  EXECUTE format('CREATE TRIGGER disclosure_evidence_truncate BEFORE TRUNCATE ON accounting.%I FOR EACH STATEMENT EXECUTE FUNCTION accounting.guard_reporting_evidence()',item);
 END LOOP;
END $$;

CREATE OR REPLACE FUNCTION accounting.disclosure_wallet_scope(p_period UUID)
RETURNS TABLE(account_id UUID,collector BOOLEAN) LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 WITH sources AS (
  SELECT treasury_account_id account_id,journal_entry_id,false collector FROM accounting.treasury_receipt_postings
  UNION ALL SELECT treasury_account_id,journal_entry_id,false FROM accounting.treasury_application_postings
  UNION ALL SELECT source_account_id,journal_entry_id,false FROM accounting.treasury_transfer_postings
  UNION ALL SELECT destination_account_id,journal_entry_id,false FROM accounting.treasury_transfer_postings
  UNION ALL SELECT treasury_account_id,journal_entry_id,false FROM accounting.loan_payout_accounting_postings
  UNION ALL SELECT account_id,journal_entry_id,true FROM accounting.collector_liability_postings
  UNION ALL SELECT wallet::uuid,posted.journal_entry_id,true FROM accounting.collector_liability_postings posted
    JOIN accounting.collector_liability_preparations prepared ON prepared.id=posted.preparation_id
    CROSS JOIN LATERAL jsonb_array_elements_text(prepared.snapshot->'account_ids') wallet
  UNION ALL SELECT unnest(accounting.collector_liability_accounts(source_kind,source_id)),journal_entry_id,true FROM accounting.collector_liability_postings
 ) SELECT s.account_id,bool_or(s.collector) FROM sources s JOIN accounting.journal_entries j ON j.id=s.journal_entry_id
 JOIN accounting.fiscal_periods period ON period.id=p_period WHERE j.status='posted' AND j.posting_date<=period.end_date GROUP BY s.account_id;
$$;
CREATE OR REPLACE FUNCTION accounting.require_disclosure_actor(p_actor UUID,p_period UUID,p_permission TEXT,p_lock BOOLEAN DEFAULT false)
RETURNS VOID LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE wallet RECORD; permission TEXT;
BEGIN
 IF p_permission IS NULL OR p_permission NOT IN('accounting.view','accounting.journal.manage') THEN
  RAISE EXCEPTION 'Current accounting permission required.' USING ERRCODE='42501'; END IF;
 IF p_lock THEN
  LOCK TABLE core.users,core.user_roles,core.roles,core.role_permissions,treasury.account_access IN SHARE MODE;
 END IF;
 IF NOT EXISTS(SELECT 1 FROM core.users u JOIN core.user_roles ur ON ur.user_id=u.id JOIN core.roles r ON r.id=ur.role_id JOIN core.role_permissions rp ON rp.role_id=r.id
  WHERE u.id=p_actor AND u.status='active' AND r.code='management' AND rp.permission_code=p_permission) THEN
  RAISE EXCEPTION 'Current Management accounting permission required.' USING ERRCODE='42501'; END IF;
 -- Authorize all contributing wallets, including opening balances, before any
 -- totals or page filtering. No configured-owner exception grants private history.
 FOR wallet IN SELECT * FROM accounting.disclosure_wallet_scope(p_period) ORDER BY account_id LOOP
  FOREACH permission IN ARRAY CASE WHEN wallet.collector THEN ARRAY['treasury.view','treasury.collector_surplus.view'] ELSE ARRAY['treasury.view'] END LOOP
   IF NOT EXISTS(SELECT 1 FROM treasury.account_access access JOIN treasury.accounts a ON a.id=access.account_id
    WHERE access.user_id=p_actor AND access.account_id=wallet.account_id AND access.enabled AND access.private_history AND a.active AND permission=ANY(access.permissions))
    OR NOT EXISTS(SELECT 1 FROM core.user_roles ur JOIN core.role_permissions rp ON rp.role_id=ur.role_id WHERE ur.user_id=p_actor AND rp.permission_code=permission) THEN
    RAISE EXCEPTION 'Current private Treasury permission required for disclosure reporting.' USING ERRCODE='42501'; END IF;
  END LOOP;
 END LOOP;
END $$;

CREATE OR REPLACE FUNCTION accounting.journal_disclosure_protected_kind(p_journal UUID)
RETURNS TEXT LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT CASE
  WHEN j.source_type='opening_balance' AND EXISTS(SELECT 1 FROM accounting.opening_balance_journal_postings p WHERE p.journal_entry_id=j.id AND p.entry_number=j.entry_number) THEN 'opening'
  WHEN j.source_type='reversal' AND EXISTS(SELECT 1 FROM accounting.opening_balance_journal_postings p WHERE p.journal_entry_id=j.reversal_of_entry_id AND accounting.legacy_journal_reversal_exact(p.journal_entry_id,j.id)) THEN 'opening_reversal'
  WHEN j.source_type='period_close' AND EXISTS(SELECT 1 FROM accounting.period_close_postings p WHERE p.journal_entry_id=j.id AND p.fiscal_period_id=j.fiscal_period_id AND p.entry_number=j.entry_number) THEN 'period_close'
  END FROM accounting.journal_entries j WHERE j.id=p_journal AND j.status='posted';
$$;
CREATE OR REPLACE FUNCTION accounting.journal_disclosure_source_status(p_journal UUID)
RETURNS TEXT LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE j accounting.journal_entries%ROWTYPE; exact BOOLEAN;
BEGIN
 SELECT * INTO j FROM accounting.journal_entries WHERE id=p_journal AND status='posted';
 IF NOT FOUND THEN RETURN 'posted_journal_required'; END IF;
 IF accounting.journal_disclosure_protected_kind(j.id) IS NOT NULL OR j.source_type='manual' THEN RETURN 'current'; END IF;
 CASE j.source_type
 WHEN 'collection','regular_eir_accrual' THEN SELECT accounting.legacy_regular_collection_posted_exact(transaction_id) INTO exact FROM accounting.regular_journal_posting_entries WHERE journal_entry_id=j.id;
 WHEN 'reversal' THEN SELECT accounting.legacy_journal_reversal_exact(original.id,j.id) INTO exact FROM accounting.journal_entries original WHERE original.id=j.reversal_of_entry_id AND original.source_type='manual';
 WHEN 'treasury_verified_receipt' THEN SELECT exact_posted AND NOT correction_pending INTO exact FROM accounting.treasury_receipt_posting_status WHERE journal_entry_id=j.id AND book_id=(SELECT id FROM accounting.book_identity WHERE singleton);
 WHEN 'treasury_receipt_application' THEN SELECT accounting.proven_treasury_application_exact(application_id,transaction_id) INTO exact FROM accounting.treasury_application_posting_status WHERE journal_entry_id=j.id AND book_id=(SELECT id FROM accounting.book_identity WHERE singleton);
 WHEN 'treasury_owned_transfer' THEN SELECT exact_posted AND NOT correction_pending INTO exact FROM accounting.treasury_transfer_posting_status WHERE journal_entry_id=j.id AND book_id=(SELECT id FROM accounting.book_identity WHERE singleton);
 WHEN 'collector_liability' THEN SELECT exact_posted AND NOT correction_pending INTO exact FROM accounting.collector_liability_posting_status WHERE journal_entry_id=j.id AND book_id=(SELECT id FROM accounting.book_identity WHERE singleton);
 WHEN 'treasury_loan_payout' THEN SELECT exact_posted AND NOT correction_pending INTO exact FROM accounting.loan_payout_accounting_posting_status WHERE journal_entry_id=j.id AND book_id=(SELECT id FROM accounting.book_identity WHERE singleton);
 WHEN 'period_elapsed_eir','period_elapsed_ecl' THEN SELECT accounting.period_elapsed_loan_assessment_exact(fiscal_period_id,loan_id) INTO exact FROM accounting.loan_elapsed_assessment_postings WHERE j.id IN(eir_journal_entry_id,allowance_journal_entry_id);
 ELSE RETURN 'source_proof_required';
 END CASE;
 RETURN CASE WHEN exact IS TRUE THEN 'current' ELSE 'source_correction_required' END;
END $$;

CREATE OR REPLACE FUNCTION accounting.lock_journal_disclosure_sources(p_journal UUID)
RETURNS VOID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE source_type TEXT; wallet UUID;
BEGIN
 IF current_setting('transaction_isolation')<>'read committed' THEN RAISE EXCEPTION 'Disclosure retention requires READ COMMITTED.' USING ERRCODE='55000'; END IF;
 SELECT j.source_type INTO source_type FROM accounting.journal_entries j WHERE j.id=p_journal;
 IF source_type IN('manual','reversal','opening_balance','period_close') THEN RETURN; END IF;
 -- Acquire operational wallet locks before chart/period locks, as the monetary
 -- adapters do. Source table locks also serialize direct protected corrections.
 FOR wallet IN SELECT account_id FROM accounting.disclosure_wallet_scope((SELECT fiscal_period_id FROM accounting.journal_entries WHERE id=p_journal)) ORDER BY account_id LOOP
  PERFORM 1 FROM treasury.accounts WHERE id=wallet FOR SHARE;
 END LOOP;
 IF source_type='collector_liability' THEN
  PERFORM accounting.lock_collector_liability_sources();
 ELSE
  LOCK TABLE lending.collection_transactions,lending.loans,lending.loan_types,
    accounting.treasury_cash_mappings,treasury.loan_payouts,treasury.receipts,treasury.applications,treasury.transfers,
    treasury.events,treasury.event_revisions,treasury.movement_lines,treasury.source_links,treasury.evidence IN SHARE MODE;
  PERFORM accounting.lock_loan_period_assessment_sources();
 END IF;
END $$;

CREATE OR REPLACE FUNCTION accounting.journal_disclosure_snapshot(p_journal UUID,p_policy UUID)
RETURNS JSONB LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
 SELECT jsonb_build_object('book_id',(SELECT id FROM accounting.book_identity WHERE singleton),
  'reporting_policy_id',p_policy,'journal',to_jsonb(j),'source_status',accounting.journal_disclosure_source_status(j.id),
  'lines',coalesce((SELECT jsonb_agg(jsonb_build_object('line',to_jsonb(l),
   'account',to_jsonb(a)-ARRAY['name','is_active','created_at','updated_at'],
   'cash_classification',CASE WHEN p.payload->'cash_account_codes' ? a.code THEN
     (SELECT to_jsonb(c) FROM accounting.cash_flow_classifications c WHERE c.policy_id=p_policy AND c.journal_line_id=l.id ORDER BY version DESC LIMIT 1)
     ELSE NULL END) ORDER BY l.line_number)
   FROM accounting.journal_lines l JOIN accounting.accounts a ON a.id=l.account_id WHERE l.journal_entry_id=j.id),'[]'::jsonb))
 FROM accounting.journal_entries j JOIN accounting.reporting_policy_versions p ON p.id=p_policy
 WHERE j.id=p_journal AND j.status='posted' AND j.fiscal_period_id=p.fiscal_period_id;
$$;
CREATE OR REPLACE FUNCTION accounting.journal_disclosure_digest(p_journal UUID,p_policy UUID)
RETURNS TEXT LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT encode(sha256(convert_to(accounting.journal_disclosure_snapshot(p_journal,p_policy)::text,'UTF8')),'hex');
$$;

CREATE OR REPLACE FUNCTION accounting.retain_disclosure_policy(p_request UUID,p_book UUID,p_policy UUID,p_version INTEGER,p_payload JSONB,p_actor UUID)
RETURNS UUID LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE existing accounting.disclosure_policy_versions%ROWTYPE; policy accounting.reporting_policy_versions%ROWTYPE;
 codes TEXT[]; current_version INT; old_setting TEXT;
BEGIN
 PERFORM accounting.require_liability_actor(p_actor,'accounting.journal.manage');
 IF p_book IS NULL OR p_book IS DISTINCT FROM (SELECT id FROM accounting.book_identity WHERE singleton) THEN
  RAISE EXCEPTION 'Reviewed accounting book does not match.' USING ERRCODE='55000'; END IF;
 IF p_request IS NULL OR p_version IS NULL OR p_version<0 THEN RAISE EXCEPTION 'Exact request and version required.' USING ERRCODE='22023'; END IF;
 PERFORM accounting.require_reporting_evidence(p_payload,ARRAY['financing_account_codes','evidence_reference','evidence_digest','reviewed']);
 PERFORM pg_advisory_xact_lock(hashtextextended('disclosure-policy:'||p_request::text,0));
 PERFORM accounting.require_disclosure_actor(p_actor,(SELECT fiscal_period_id FROM accounting.reporting_policy_versions WHERE id=p_policy),'accounting.journal.manage',true);
 SELECT * INTO existing FROM accounting.disclosure_policy_versions WHERE id=p_request;
 IF FOUND THEN
  IF existing.book_id=p_book AND existing.reporting_policy_id=p_policy AND existing.version=p_version+1 AND existing.payload=p_payload AND existing.actor_user_id=p_actor THEN RETURN p_request; END IF;
  RAISE EXCEPTION 'Disclosure policy request conflict.' USING ERRCODE='55000'; END IF;
 SELECT * INTO policy FROM accounting.reporting_policy_versions WHERE id=p_policy AND book_id=p_book;
 IF NOT FOUND THEN RAISE EXCEPTION 'Reporting policy unavailable.' USING ERRCODE='55000'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('period-close:'||policy.fiscal_period_id::text,0));
 PERFORM 1 FROM accounting.fiscal_periods WHERE id=policy.fiscal_period_id AND status='open' FOR UPDATE;
 IF NOT FOUND OR EXISTS(SELECT 1 FROM accounting.reporting_policy_versions WHERE fiscal_period_id=policy.fiscal_period_id AND version>policy.version) THEN
  RAISE EXCEPTION 'Current reporting policy and open period required.' USING ERRCODE='55000'; END IF;
 SELECT coalesce(max(version),0) INTO current_version FROM accounting.disclosure_policy_versions WHERE fiscal_period_id=policy.fiscal_period_id;
 IF current_version<>p_version THEN RAISE EXCEPTION 'Disclosure policy version changed.' USING ERRCODE='55000'; END IF;
 IF jsonb_typeof(p_payload->'financing_account_codes') IS DISTINCT FROM 'array'
  OR jsonb_array_length(p_payload->'financing_account_codes')>100 THEN RAISE EXCEPTION 'Explicit financing accounts required.' USING ERRCODE='22023'; END IF;
 IF EXISTS(SELECT 1 FROM jsonb_array_elements(p_payload->'financing_account_codes') WHERE jsonb_typeof(value)<>'string') THEN
  RAISE EXCEPTION 'Exact financing code strings required.' USING ERRCODE='22023'; END IF;
 codes:=ARRAY(SELECT jsonb_array_elements_text(p_payload->'financing_account_codes'));
 LOCK TABLE accounting.accounts IN SHARE MODE;
 IF cardinality(codes)<>(SELECT count(DISTINCT value) FROM unnest(codes) value)
  OR cardinality(codes)<>(SELECT count(*) FROM accounting.accounts WHERE code=ANY(codes) AND account_type='liability' AND normal_balance='credit' AND is_posting) THEN
  RAISE EXCEPTION 'Unique compatible financing liability accounts required.' USING ERRCODE='22023'; END IF;
 IF policy.cash_accounts IS DISTINCT FROM accounting.reporting_cash_definition(ARRAY(SELECT jsonb_array_elements_text(policy.payload->'cash_account_codes'))) THEN
  RAISE EXCEPTION 'Cash policy definition changed.' USING ERRCODE='55000'; END IF;
 old_setting:=current_setting('accounting.reporting_evidence_insert_allowed',true);
 PERFORM set_config('accounting.reporting_evidence_insert_allowed','on',true);
 INSERT INTO accounting.disclosure_policy_versions(id,book_id,fiscal_period_id,reporting_policy_id,version,payload,financing_accounts,actor_user_id)
 VALUES(p_request,p_book,policy.fiscal_period_id,p_policy,p_version+1,p_payload,accounting.reporting_cash_definition(codes),p_actor);
 PERFORM set_config('accounting.reporting_evidence_insert_allowed',coalesce(old_setting,''),true);
 INSERT INTO core.audit_logs(actor_user_id,action,target_type,target_id,details) VALUES(p_actor,'accounting.disclosure_policy.retained','disclosure_policy',p_request,jsonb_build_object('book_id',p_book,'period_id',policy.fiscal_period_id));
 RETURN p_request;
END $$;

CREATE OR REPLACE FUNCTION accounting.validate_disclosure_components(p_journal UUID,p_policy UUID,p_components JSONB)
RETURNS VOID LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE part JSONB; debit RECORD; credit RECORD; item RECORD; codes JSONB; amount NUMERIC; actual JSONB; expected JSONB;
BEGIN
 SELECT payload->'cash_account_codes' INTO codes FROM accounting.reporting_policy_versions WHERE id=p_policy;
 IF codes IS NULL OR jsonb_typeof(p_components) IS DISTINCT FROM 'array' THEN RAISE EXCEPTION 'Explicit components and cash policy required.' USING ERRCODE='22023'; END IF;
 IF jsonb_array_length(p_components) NOT BETWEEN 1 AND 1000 THEN RAISE EXCEPTION 'Explicit components required.' USING ERRCODE='22023'; END IF;
 FOR part IN SELECT value FROM jsonb_array_elements(p_components) LOOP
  IF jsonb_typeof(part)<>'object' OR NOT part ?& ARRAY['debit_line_id','credit_line_id','amount','classification','evidence_reference','evidence_digest']
   OR EXISTS(SELECT 1 FROM jsonb_object_keys(part) k WHERE k NOT IN('debit_line_id','credit_line_id','amount','classification','evidence_reference','evidence_digest'))
   OR jsonb_typeof(part->'debit_line_id') IS DISTINCT FROM 'string' OR jsonb_typeof(part->'credit_line_id') IS DISTINCT FROM 'string'
   OR jsonb_typeof(part->'amount') IS DISTINCT FROM 'string' OR part->>'amount' !~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$'
   OR part->>'classification' IS NULL OR part->>'classification' NOT IN('cash_operating','cash_investing','cash_financing','cash_internal','noncash_investing','noncash_financing','noncash_investing_financing','noncash_operating','noncash_reclassification')
   OR jsonb_typeof(part->'evidence_reference') IS DISTINCT FROM 'string' OR length(part->>'evidence_reference') NOT BETWEEN 1 AND 1000
   OR part->>'evidence_reference' ~ '(^[[:space:]]|[[:space:]]$)'
   OR jsonb_typeof(part->'evidence_digest') IS DISTINCT FROM 'string' OR part->>'evidence_digest' !~ '^[0-9a-f]{64}$' THEN
   RAISE EXCEPTION 'Exact component fields, classification and evidence required.' USING ERRCODE='22023'; END IF;
  amount:=(part->>'amount')::numeric;
  SELECT l.*,a.code INTO debit FROM accounting.journal_lines l JOIN accounting.accounts a ON a.id=l.account_id WHERE l.id=(part->>'debit_line_id')::uuid AND l.journal_entry_id=p_journal AND l.debit>0 AND l.credit=0;
  IF NOT FOUND THEN RAISE EXCEPTION 'Original debit line required.' USING ERRCODE='22023'; END IF;
  SELECT l.*,a.code INTO credit FROM accounting.journal_lines l JOIN accounting.accounts a ON a.id=l.account_id WHERE l.id=(part->>'credit_line_id')::uuid AND l.journal_entry_id=p_journal AND l.credit>0 AND l.debit=0;
  IF NOT FOUND OR amount<=0 THEN RAISE EXCEPTION 'Original credit line and positive amount required.' USING ERRCODE='22023'; END IF;
  IF (codes ? debit.code OR codes ? credit.code) IS DISTINCT FROM (left(part->>'classification',5)='cash_') THEN
   RAISE EXCEPTION 'Cash-connected components cannot be noncash.' USING ERRCODE='22023'; END IF;
 END LOOP;
 IF EXISTS(SELECT 1 FROM jsonb_array_elements(p_components) p GROUP BY p->>'debit_line_id',p->>'credit_line_id',p->>'classification' HAVING count(*)>1) THEN
  RAISE EXCEPTION 'Duplicate pair and classification must be combined.' USING ERRCODE='22023'; END IF;
 FOR item IN SELECT l.*,a.code FROM accounting.journal_lines l JOIN accounting.accounts a ON a.id=l.account_id WHERE l.journal_entry_id=p_journal LOOP
  IF item.debit+item.credit IS DISTINCT FROM (SELECT sum((p->>'amount')::numeric) FROM jsonb_array_elements(p_components) p WHERE item.id::text IN(p->>'debit_line_id',p->>'credit_line_id')) THEN
   RAISE EXCEPTION 'Every original line must be allocated exactly.' USING ERRCODE='22023'; END IF;
  IF codes ? item.code THEN
   SELECT jsonb_object_agg(category,total) INTO actual FROM (SELECT substring(p->>'classification' FROM 6) category,sum((p->>'amount')::numeric*CASE WHEN item.debit>0 THEN 1 ELSE -1 END) total
    FROM jsonb_array_elements(p_components) p WHERE item.id::text IN(p->>'debit_line_id',p->>'credit_line_id') GROUP BY 1) amounts;
   SELECT jsonb_object_agg(category,total) INTO expected FROM (SELECT p->>'category' category,sum((p->>'amount')::numeric) total
    FROM jsonb_array_elements((SELECT payload->'allocations' FROM accounting.cash_flow_classifications WHERE policy_id=p_policy AND journal_line_id=item.id ORDER BY version DESC LIMIT 1)) p GROUP BY 1) amounts;
   IF actual IS DISTINCT FROM expected THEN RAISE EXCEPTION 'Components must reconcile to retained cash classifications.' USING ERRCODE='22023'; END IF;
  END IF;
 END LOOP;
END $$;

CREATE OR REPLACE FUNCTION accounting.retain_journal_disclosure_review(p_request UUID,p_book UUID,p_disclosure_policy UUID,p_payload JSONB,p_actor UUID)
RETURNS UUID LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE existing accounting.journal_disclosure_reviews%ROWTYPE; policy accounting.disclosure_policy_versions%ROWTYPE;
 reporting accounting.reporting_policy_versions%ROWTYPE; journal UUID; source JSONB; digest TEXT; current_version INT; old_setting TEXT;
BEGIN
 PERFORM accounting.require_liability_actor(p_actor,'accounting.journal.manage');
 IF p_book IS NULL OR p_book IS DISTINCT FROM (SELECT id FROM accounting.book_identity WHERE singleton) THEN RAISE EXCEPTION 'Reviewed accounting book does not match.' USING ERRCODE='55000'; END IF;
 IF p_request IS NULL THEN RAISE EXCEPTION 'Exact request required.' USING ERRCODE='22023'; END IF;
 PERFORM accounting.require_reporting_evidence(p_payload,ARRAY['journal_entry_id','expected_version','source_digest','components','reason','evidence_reference','evidence_digest','reviewed']);
 IF jsonb_typeof(p_payload->'expected_version') IS DISTINCT FROM 'number' OR p_payload->>'expected_version' !~ '^(0|[1-9][0-9]{0,8})$'
  OR jsonb_typeof(p_payload->'source_digest') IS DISTINCT FROM 'string' OR p_payload->>'source_digest' !~ '^[0-9a-f]{64}$'
  OR jsonb_typeof(p_payload->'reason') IS DISTINCT FROM 'string' OR length(p_payload->>'reason') NOT BETWEEN 1 AND 4000 OR p_payload->>'reason' !~ '[^[:space:]]' THEN
  RAISE EXCEPTION 'Exact version, source digest and reason required.' USING ERRCODE='22023'; END IF;
 journal:=(p_payload->>'journal_entry_id')::uuid;
 PERFORM pg_advisory_xact_lock(hashtextextended('journal-disclosure:'||p_request::text,0));
 PERFORM accounting.require_disclosure_actor(p_actor,(SELECT fiscal_period_id FROM accounting.disclosure_policy_versions WHERE id=p_disclosure_policy),'accounting.journal.manage',true);
 SELECT * INTO existing FROM accounting.journal_disclosure_reviews WHERE id=p_request;
 IF FOUND THEN
  IF existing.book_id=p_book AND existing.disclosure_policy_id=p_disclosure_policy AND existing.payload=p_payload AND existing.actor_user_id=p_actor THEN RETURN p_request; END IF;
  RAISE EXCEPTION 'Journal disclosure request conflict.' USING ERRCODE='55000'; END IF;
 SELECT * INTO policy FROM accounting.disclosure_policy_versions WHERE id=p_disclosure_policy AND book_id=p_book;
 IF NOT FOUND THEN RAISE EXCEPTION 'Disclosure policy unavailable.' USING ERRCODE='55000'; END IF;
 -- Serialize with the established close boundary before holding source locks.
 -- In particular, Collector proof locks must not wait behind a closing period.
 PERFORM pg_advisory_xact_lock(hashtextextended('period-close:'||policy.fiscal_period_id::text,0));
 PERFORM accounting.lock_journal_disclosure_sources(journal);
 PERFORM 1 FROM accounting.fiscal_periods WHERE id=policy.fiscal_period_id AND status='open' FOR UPDATE;
 IF NOT FOUND OR EXISTS(SELECT 1 FROM accounting.disclosure_policy_versions WHERE fiscal_period_id=policy.fiscal_period_id AND version>policy.version) THEN
  RAISE EXCEPTION 'Current disclosure policy and open period required.' USING ERRCODE='55000'; END IF;
 SELECT * INTO reporting FROM accounting.reporting_policy_versions WHERE id=policy.reporting_policy_id;
 IF EXISTS(SELECT 1 FROM accounting.reporting_policy_versions WHERE fiscal_period_id=policy.fiscal_period_id AND version>reporting.version) THEN
  RAISE EXCEPTION 'Reporting policy changed.' USING ERRCODE='55000'; END IF;
 LOCK TABLE accounting.accounts IN SHARE MODE;
 IF policy.financing_accounts IS DISTINCT FROM accounting.reporting_cash_definition(ARRAY(SELECT jsonb_array_elements_text(policy.payload->'financing_account_codes')))
  OR reporting.cash_accounts IS DISTINCT FROM accounting.reporting_cash_definition(ARRAY(SELECT jsonb_array_elements_text(reporting.payload->'cash_account_codes'))) THEN
  RAISE EXCEPTION 'Retained policy chart definition changed.' USING ERRCODE='55000'; END IF;
 PERFORM 1 FROM accounting.journal_entries WHERE id=journal FOR SHARE;
 PERFORM 1 FROM accounting.journal_lines WHERE journal_entry_id=journal ORDER BY line_number FOR SHARE;
 SELECT coalesce(max(version),0) INTO current_version FROM accounting.journal_disclosure_reviews WHERE journal_entry_id=journal;
 IF current_version<>(p_payload->>'expected_version')::integer THEN RAISE EXCEPTION 'Journal disclosure version changed.' USING ERRCODE='55000'; END IF;
 source:=accounting.journal_disclosure_snapshot(journal,policy.reporting_policy_id);
 digest:=encode(sha256(convert_to(source::text,'UTF8')),'hex');
 IF digest IS NULL OR digest IS DISTINCT FROM p_payload->>'source_digest' THEN RAISE EXCEPTION 'Journal disclosure source changed.' USING ERRCODE='55000'; END IF;
 IF source->>'source_status' IS DISTINCT FROM 'current' OR accounting.journal_disclosure_protected_kind(journal) IS NOT NULL THEN
  RAISE EXCEPTION 'Current source proof and a non-excluded journal required.' USING ERRCODE='55000'; END IF;
 PERFORM accounting.validate_disclosure_components(journal,policy.reporting_policy_id,p_payload->'components');
 old_setting:=current_setting('accounting.reporting_evidence_insert_allowed',true);
 PERFORM set_config('accounting.reporting_evidence_insert_allowed','on',true);
 INSERT INTO accounting.journal_disclosure_reviews(id,book_id,fiscal_period_id,disclosure_policy_id,journal_entry_id,version,payload,source_digest,snapshot,actor_user_id)
 VALUES(p_request,p_book,policy.fiscal_period_id,p_disclosure_policy,journal,current_version+1,p_payload,digest,source,p_actor);
 PERFORM set_config('accounting.reporting_evidence_insert_allowed',coalesce(old_setting,''),true);
 INSERT INTO core.audit_logs(actor_user_id,action,target_type,target_id,details) VALUES(p_actor,'accounting.journal_disclosure.retained','journal_disclosure',p_request,jsonb_build_object('book_id',p_book,'journal_entry_id',journal,'version',current_version+1));
 RETURN p_request;
END $$;

DO $$ BEGIN
 IF to_regprocedure('accounting.period_review_before_disclosure_evidence(uuid)') IS NULL THEN
  ALTER FUNCTION accounting.period_review_additional_evidence(UUID) RENAME TO period_review_before_disclosure_evidence;
  ALTER FUNCTION accounting.lock_period_review_additional_sources() RENAME TO lock_period_review_before_disclosure_sources;
 END IF;
END $$;
CREATE OR REPLACE FUNCTION accounting.period_review_additional_evidence(p_period UUID)
RETURNS JSONB LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
 SELECT accounting.period_review_before_disclosure_evidence(p_period) ||
  CASE WHEN EXISTS(SELECT 1 FROM accounting.disclosure_policy_versions WHERE fiscal_period_id=p_period) THEN
   jsonb_build_object('disclosure_policies',(SELECT jsonb_agg(to_jsonb(p) ORDER BY version) FROM accounting.disclosure_policy_versions p WHERE fiscal_period_id=p_period),
    'journal_disclosure_reviews',coalesce((SELECT jsonb_agg(to_jsonb(r) ORDER BY journal_entry_id,version) FROM accounting.journal_disclosure_reviews r WHERE fiscal_period_id=p_period),'[]'::jsonb))
   ELSE '{}'::jsonb END;
$$;
CREATE OR REPLACE FUNCTION accounting.lock_period_review_additional_sources()
RETURNS VOID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 PERFORM accounting.lock_period_review_before_disclosure_sources();
 LOCK TABLE accounting.disclosure_policy_versions,accounting.journal_disclosure_reviews IN SHARE MODE;
END $$;

DO $$ DECLARE role_name TEXT; item RECORD; BEGIN
 FOREACH role_name IN ARRAY ARRAY['PUBLIC','anon','authenticated','service_role'] LOOP
  IF role_name='PUBLIC' OR EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
   EXECUTE format('REVOKE ALL ON accounting.disclosure_policy_versions,accounting.journal_disclosure_reviews FROM %s',CASE WHEN role_name='PUBLIC' THEN 'PUBLIC' ELSE quote_ident(role_name) END);
   FOR item IN SELECT oid::regprocedure::text signature FROM pg_proc WHERE pronamespace='accounting'::regnamespace AND (proname LIKE '%disclosure%' OR proname IN('period_review_additional_evidence','lock_period_review_additional_sources')) LOOP
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM %s',item.signature,CASE WHEN role_name='PUBLIC' THEN 'PUBLIC' ELSE quote_ident(role_name) END);
   END LOOP;
  END IF;
 END LOOP;
END $$;
COMMIT;
