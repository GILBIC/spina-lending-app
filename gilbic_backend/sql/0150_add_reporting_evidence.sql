BEGIN;

CREATE TABLE IF NOT EXISTS accounting.reporting_policy_versions (
    id UUID PRIMARY KEY,book_id UUID NOT NULL REFERENCES accounting.book_identity(id),
    fiscal_period_id UUID NOT NULL REFERENCES accounting.fiscal_periods(id),
    version INTEGER NOT NULL CHECK(version>0),payload JSONB NOT NULL,cash_accounts JSONB NOT NULL,
    actor_user_id UUID NOT NULL REFERENCES core.users(id),created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(fiscal_period_id,version)
);
-- Old retained rows cannot acquire an invented historical account definition.
ALTER TABLE accounting.reporting_policy_versions ADD COLUMN IF NOT EXISTS cash_accounts JSONB;

CREATE OR REPLACE FUNCTION accounting.reporting_cash_definition(p_codes TEXT[])
RETURNS JSONB LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
    SELECT coalesce(jsonb_agg(jsonb_build_object('id',id,'code',code,'system_key',system_key,
        'account_type',account_type,'normal_balance',normal_balance,'is_posting',is_posting) ORDER BY code),'[]'::jsonb)
    FROM accounting.accounts WHERE code=ANY(p_codes)
$$;
CREATE TABLE IF NOT EXISTS accounting.cash_flow_classifications (
    id UUID PRIMARY KEY,book_id UUID NOT NULL REFERENCES accounting.book_identity(id),
    policy_id UUID NOT NULL REFERENCES accounting.reporting_policy_versions(id),
    journal_line_id UUID NOT NULL REFERENCES accounting.journal_lines(id),
    version INTEGER NOT NULL CHECK(version>0),signed_amount NUMERIC(18,2) NOT NULL CHECK(signed_amount<>0),
    payload JSONB NOT NULL,actor_user_id UUID NOT NULL REFERENCES core.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),UNIQUE(policy_id,journal_line_id,version)
);
ALTER TABLE accounting.reporting_policy_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounting.cash_flow_classifications ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION accounting.guard_reporting_evidence()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
    IF TG_OP='INSERT' AND current_setting('accounting.reporting_evidence_insert_allowed',true)='on' THEN RETURN NEW; END IF;
    RAISE EXCEPTION 'Reporting evidence is immutable; retain a new reviewed version.';
END; $$;
DO $$ DECLARE table_name text; BEGIN
    FOREACH table_name IN ARRAY ARRAY['reporting_policy_versions','cash_flow_classifications'] LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS reporting_evidence_write ON accounting.%I',table_name);
        EXECUTE format('CREATE TRIGGER reporting_evidence_write BEFORE INSERT OR UPDATE OR DELETE ON accounting.%I FOR EACH ROW EXECUTE FUNCTION accounting.guard_reporting_evidence()',table_name);
        EXECUTE format('DROP TRIGGER IF EXISTS reporting_evidence_truncate ON accounting.%I',table_name);
        EXECUTE format('CREATE TRIGGER reporting_evidence_truncate BEFORE TRUNCATE ON accounting.%I FOR EACH STATEMENT EXECUTE FUNCTION accounting.guard_reporting_evidence()',table_name);
    END LOOP;
END; $$;

CREATE OR REPLACE FUNCTION accounting.require_reporting_evidence(p_payload JSONB,p_keys TEXT[])
RETURNS VOID LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
    IF p_payload IS NULL OR jsonb_typeof(p_payload)<>'object' OR NOT p_payload ?& p_keys
       OR EXISTS(SELECT 1 FROM jsonb_object_keys(p_payload) key WHERE NOT key=ANY(p_keys))
       OR p_payload->'reviewed' IS DISTINCT FROM 'true'::jsonb
       OR jsonb_typeof(p_payload->'evidence_reference') IS DISTINCT FROM 'string'
       OR length(p_payload->>'evidence_reference') NOT BETWEEN 1 AND 1000
       OR p_payload->>'evidence_reference' ~ '(^[[:space:]]|[[:space:]]$)'
       OR jsonb_typeof(p_payload->'evidence_digest') IS DISTINCT FROM 'string'
       OR p_payload->>'evidence_digest' !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Exact reviewed reporting evidence is required.' USING ERRCODE='22023';
    END IF;
END; $$;

CREATE OR REPLACE FUNCTION accounting.retain_reporting_policy(p_request UUID,p_book UUID,p_period UUID,p_expected_version INTEGER,p_payload JSONB,p_actor UUID)
RETURNS UUID LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE existing accounting.reporting_policy_versions%ROWTYPE; period_status text; current_version integer;
    codes text[]; note jsonb; old_setting text; cash_definition jsonb;
BEGIN
    PERFORM accounting.require_liability_actor(p_actor,'accounting.journal.manage');
    IF p_book IS NULL OR p_book IS DISTINCT FROM (SELECT id FROM accounting.book_identity WHERE singleton) THEN
        RAISE EXCEPTION 'Reviewed accounting book does not match.' USING ERRCODE='55000'; END IF;
    IF p_request IS NULL OR p_expected_version IS NULL OR p_expected_version<0 THEN
        RAISE EXCEPTION 'Reporting request and expected version are required.' USING ERRCODE='22023'; END IF;
    PERFORM accounting.require_reporting_evidence(p_payload,ARRAY['cash_account_codes','framework_label','notes','evidence_reference','evidence_digest','reviewed']);
    PERFORM pg_advisory_xact_lock(hashtextextended('reporting-policy:'||p_request::text,0));
    SELECT * INTO existing FROM accounting.reporting_policy_versions WHERE id=p_request;
    IF FOUND THEN
        IF existing.book_id=p_book AND existing.fiscal_period_id=p_period AND existing.version=p_expected_version+1
           AND existing.payload=p_payload AND existing.actor_user_id=p_actor THEN RETURN existing.id; END IF;
        RAISE EXCEPTION 'Reporting request conflict: retained values changed.' USING ERRCODE='55000';
    END IF;
    SELECT status INTO period_status FROM accounting.fiscal_periods WHERE id=p_period FOR UPDATE;
    IF NOT FOUND OR period_status<>'open' THEN RAISE EXCEPTION 'Reporting policy changes require an open period.' USING ERRCODE='55000'; END IF;
    SELECT coalesce(max(version),0) INTO current_version FROM accounting.reporting_policy_versions WHERE fiscal_period_id=p_period;
    IF current_version<>p_expected_version THEN RAISE EXCEPTION 'Reporting policy version changed; refresh review.' USING ERRCODE='55000'; END IF;
    IF jsonb_typeof(p_payload->'cash_account_codes') IS DISTINCT FROM 'array' THEN RAISE EXCEPTION 'Explicit cash controls are required.' USING ERRCODE='22023'; END IF;
    IF EXISTS(SELECT 1 FROM jsonb_array_elements(p_payload->'cash_account_codes') WHERE jsonb_typeof(value)<>'string') THEN
        RAISE EXCEPTION 'Exact cash account code strings are required.' USING ERRCODE='22023'; END IF;
    SELECT array_agg(value) INTO codes FROM jsonb_array_elements_text(p_payload->'cash_account_codes');
    PERFORM 1 FROM accounting.accounts WHERE code=ANY(codes) ORDER BY code FOR SHARE;
    IF coalesce(cardinality(codes),0)=0 OR cardinality(codes)<>(SELECT count(DISTINCT code) FROM unnest(codes) code)
       OR EXISTS(SELECT 1 FROM unnest(codes) code WHERE code NOT IN ('1010','1020','1030'))
       OR (SELECT count(*) FROM accounting.accounts WHERE code=ANY(codes) AND account_type='asset' AND normal_balance='debit' AND is_posting AND system_key IN ('cash_office','cash_collector_custody','cash_bank_gcash'))<>cardinality(codes) THEN
        RAISE EXCEPTION 'Unique compatible cash control accounts are required.' USING ERRCODE='22023'; END IF;
    cash_definition:=accounting.reporting_cash_definition(codes);
    IF jsonb_typeof(p_payload->'framework_label') IS DISTINCT FROM 'string' OR length(p_payload->>'framework_label') NOT BETWEEN 1 AND 200
       OR p_payload->>'framework_label' ~ '(^[[:space:]]|[[:space:]]$)'
       OR jsonb_typeof(p_payload->'notes') IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'Reporting basis and retained notes are required.' USING ERRCODE='22023'; END IF;
    IF jsonb_array_length(p_payload->'notes') NOT BETWEEN 1 AND 50 THEN RAISE EXCEPTION 'Retain between one and fifty reporting notes.' USING ERRCODE='22023'; END IF;
    FOR note IN SELECT value FROM jsonb_array_elements(p_payload->'notes') LOOP
        IF jsonb_typeof(note)<>'object' OR NOT note ?& ARRAY['title','text','evidence_reference','evidence_digest']
           OR EXISTS(SELECT 1 FROM jsonb_object_keys(note) key WHERE key NOT IN ('title','text','evidence_reference','evidence_digest'))
           OR jsonb_typeof(note->'title') IS DISTINCT FROM 'string' OR length(btrim(note->>'title')) NOT BETWEEN 1 AND 200
           OR jsonb_typeof(note->'text') IS DISTINCT FROM 'string' OR length(btrim(note->>'text')) NOT BETWEEN 1 AND 20000
           OR jsonb_typeof(note->'evidence_reference') IS DISTINCT FROM 'string' OR length(btrim(note->>'evidence_reference')) NOT BETWEEN 1 AND 1000
           OR note->>'title' !~ '[^[:space:]]' OR note->>'text' !~ '[^[:space:]]' OR note->>'evidence_reference' !~ '[^[:space:]]'
           OR jsonb_typeof(note->'evidence_digest') IS DISTINCT FROM 'string' OR note->>'evidence_digest' !~ '^[0-9a-f]{64}$' THEN
            RAISE EXCEPTION 'Each reporting note needs exact retained text and evidence.' USING ERRCODE='22023'; END IF;
    END LOOP;
    old_setting:=current_setting('accounting.reporting_evidence_insert_allowed',true);
    PERFORM set_config('accounting.reporting_evidence_insert_allowed','on',true);
    INSERT INTO accounting.reporting_policy_versions(id,book_id,fiscal_period_id,version,payload,cash_accounts,actor_user_id)
    VALUES(p_request,p_book,p_period,p_expected_version+1,p_payload,cash_definition,p_actor);
    PERFORM set_config('accounting.reporting_evidence_insert_allowed',coalesce(old_setting,''),true);
    INSERT INTO core.audit_logs(actor_user_id,action,target_type,target_id,details)
    VALUES(p_actor,'accounting.reporting_policy.retained','reporting_policy',p_request,jsonb_build_object('book_id',p_book,'period_id',p_period,'version',p_expected_version+1));
    RETURN p_request;
END; $$;

CREATE OR REPLACE FUNCTION accounting.retain_cash_flow_classification(p_request UUID,p_book UUID,p_policy UUID,p_payload JSONB,p_actor UUID)
RETURNS UUID LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE existing accounting.cash_flow_classifications%ROWTYPE; policy accounting.reporting_policy_versions%ROWTYPE;
    source record; part jsonb; amount numeric; total numeric:=0; current_version integer; old_setting text;
BEGIN
    PERFORM accounting.require_liability_actor(p_actor,'accounting.journal.manage');
    IF p_book IS NULL OR p_book IS DISTINCT FROM (SELECT id FROM accounting.book_identity WHERE singleton) THEN
        RAISE EXCEPTION 'Reviewed accounting book does not match.' USING ERRCODE='55000'; END IF;
    IF p_request IS NULL THEN RAISE EXCEPTION 'Reporting request identity is required.' USING ERRCODE='22023'; END IF;
    PERFORM accounting.require_reporting_evidence(p_payload,ARRAY['journal_line_id','expected_amount','expected_version','allocations','evidence_reference','evidence_digest','reviewed']);
    PERFORM pg_advisory_xact_lock(hashtextextended('cash-classification:'||p_request::text,0));
    SELECT * INTO existing FROM accounting.cash_flow_classifications WHERE id=p_request;
    IF FOUND THEN
        IF existing.book_id=p_book AND existing.policy_id=p_policy AND existing.payload=p_payload AND existing.actor_user_id=p_actor THEN RETURN existing.id; END IF;
        RAISE EXCEPTION 'Cash classification request conflict: retained values changed.' USING ERRCODE='55000';
    END IF;
    SELECT * INTO policy FROM accounting.reporting_policy_versions WHERE id=p_policy;
    IF NOT FOUND OR policy.book_id<>p_book THEN RAISE EXCEPTION 'Reviewed reporting policy is unavailable.' USING ERRCODE='55000'; END IF;
    PERFORM 1 FROM accounting.fiscal_periods WHERE id=policy.fiscal_period_id AND status='open' FOR UPDATE;
    IF NOT FOUND OR EXISTS(SELECT 1 FROM accounting.reporting_policy_versions WHERE fiscal_period_id=policy.fiscal_period_id AND version>policy.version) THEN
        RAISE EXCEPTION 'Cash classification requires the current policy and an open period.' USING ERRCODE='55000'; END IF;
    PERFORM 1 FROM accounting.accounts WHERE code IN (SELECT jsonb_array_elements_text(policy.payload->'cash_account_codes')) ORDER BY code FOR SHARE;
    IF policy.cash_accounts IS NULL OR policy.cash_accounts IS DISTINCT FROM accounting.reporting_cash_definition(ARRAY(SELECT jsonb_array_elements_text(policy.payload->'cash_account_codes'))) THEN
        RAISE EXCEPTION 'Cash definition changed; retain a new reviewed reporting policy.' USING ERRCODE='55000'; END IF;
    SELECT line.id,line.debit-line.credit AS signed_amount,account.code,journal.source_type,journal.fiscal_period_id,journal.status,
        EXISTS(SELECT 1 FROM accounting.journal_entries original WHERE original.id=journal.reversal_of_entry_id AND original.source_type='opening_balance') AS opening_reversal
    INTO source FROM accounting.journal_lines line JOIN accounting.journal_entries journal ON journal.id=line.journal_entry_id
    JOIN accounting.accounts account ON account.id=line.account_id WHERE line.id=(p_payload->>'journal_line_id')::uuid FOR SHARE OF line,journal,account;
    IF NOT FOUND OR source.status<>'posted' OR source.fiscal_period_id<>policy.fiscal_period_id
       OR NOT policy.payload->'cash_account_codes' ? source.code OR source.signed_amount=0
       OR source.source_type IN ('opening_balance','period_close')
       OR source.opening_reversal
       OR jsonb_typeof(p_payload->'expected_amount') IS DISTINCT FROM 'string'
       OR p_payload->>'expected_amount' !~ '^-?(0|[1-9][0-9]{0,15})\.[0-9]{2}$'
       OR (p_payload->>'expected_amount')::numeric IS DISTINCT FROM source.signed_amount THEN
        RAISE EXCEPTION 'Exact original posted cash amount and selected period are required.' USING ERRCODE='55000'; END IF;
    IF jsonb_typeof(p_payload->'expected_version') IS DISTINCT FROM 'number' OR p_payload->>'expected_version' !~ '^(0|[1-9][0-9]{0,8})$'
       OR jsonb_typeof(p_payload->'allocations') IS DISTINCT FROM 'array' THEN RAISE EXCEPTION 'Exact cash classification version and allocations are required.' USING ERRCODE='22023'; END IF;
    SELECT coalesce(max(version),0) INTO current_version FROM accounting.cash_flow_classifications WHERE policy_id=p_policy AND journal_line_id=source.id;
    IF current_version<>(p_payload->>'expected_version')::integer THEN RAISE EXCEPTION 'Cash classification version changed; refresh review.' USING ERRCODE='55000'; END IF;
    IF jsonb_array_length(p_payload->'allocations') NOT BETWEEN 1 AND 20 THEN RAISE EXCEPTION 'Cash allocation amounts are required.' USING ERRCODE='22023'; END IF;
    FOR part IN SELECT value FROM jsonb_array_elements(p_payload->'allocations') LOOP
        IF jsonb_typeof(part)<>'object' OR NOT part ?& ARRAY['category','amount']
           OR EXISTS(SELECT 1 FROM jsonb_object_keys(part) key WHERE key NOT IN ('category','amount'))
           OR part->>'category' NOT IN ('operating','investing','financing','internal') OR part->>'category' IS NULL
           OR jsonb_typeof(part->'amount') IS DISTINCT FROM 'string' OR part->>'amount' !~ '^-?(0|[1-9][0-9]{0,15})\.[0-9]{2}$' THEN
            RAISE EXCEPTION 'Supported category and exact cash allocation amount are required.' USING ERRCODE='22023'; END IF;
        amount:=(part->>'amount')::numeric;
        IF amount*source.signed_amount<=0 THEN RAISE EXCEPTION 'Cash allocation amount must preserve the line direction.' USING ERRCODE='22023'; END IF;
        total:=total+amount;
    END LOOP;
    IF total<>source.signed_amount THEN RAISE EXCEPTION 'Cash allocations must equal the exact posted amount.' USING ERRCODE='22023'; END IF;
    old_setting:=current_setting('accounting.reporting_evidence_insert_allowed',true);
    PERFORM set_config('accounting.reporting_evidence_insert_allowed','on',true);
    INSERT INTO accounting.cash_flow_classifications(id,book_id,policy_id,journal_line_id,version,signed_amount,payload,actor_user_id)
    VALUES(p_request,p_book,p_policy,source.id,current_version+1,source.signed_amount,p_payload,p_actor);
    PERFORM set_config('accounting.reporting_evidence_insert_allowed',coalesce(old_setting,''),true);
    INSERT INTO core.audit_logs(actor_user_id,action,target_type,target_id,details)
    VALUES(p_actor,'accounting.cash_flow_classification.retained','cash_flow_classification',p_request,jsonb_build_object('book_id',p_book,'policy_id',p_policy,'journal_line_id',source.id));
    RETURN p_request;
END; $$;

DO $$ DECLARE role_name text; BEGIN
    FOREACH role_name IN ARRAY ARRAY['PUBLIC','anon','authenticated','service_role'] LOOP
        IF role_name='PUBLIC' OR EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
            EXECUTE format('REVOKE ALL ON accounting.reporting_policy_versions,accounting.cash_flow_classifications FROM %s',CASE WHEN role_name='PUBLIC' THEN 'PUBLIC' ELSE quote_ident(role_name) END);
            EXECUTE format('REVOKE ALL ON FUNCTION accounting.reporting_cash_definition(text[]),accounting.guard_reporting_evidence(),accounting.require_reporting_evidence(jsonb,text[]),accounting.retain_reporting_policy(uuid,uuid,uuid,integer,jsonb,uuid),accounting.retain_cash_flow_classification(uuid,uuid,uuid,jsonb,uuid) FROM %s',CASE WHEN role_name='PUBLIC' THEN 'PUBLIC' ELSE quote_ident(role_name) END);
        END IF;
    END LOOP;
END; $$;
COMMIT;
