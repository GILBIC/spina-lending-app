BEGIN;

-- This register attributes existing GL effects. It never creates or posts money.
DO $chart$
DECLARE definition RECORD; existing accounting.accounts%ROWTYPE;
BEGIN
    LOCK TABLE accounting.accounts IN SHARE ROW EXCLUSIVE MODE;
    FOR definition IN SELECT * FROM (VALUES
        ('2300','external_borrowings','External Borrowings'),
        ('2310','owner_borrowings','Repayable Owner and Related-Party Funding'),
        ('2320','funding_interest_payable','Accrued Funding Interest'),
        ('2330','wages_payable','Wages Payable'),
        ('2340','statutory_contributions_payable','Statutory Contributions Payable')
    ) AS definitions(code,system_key,name) LOOP
        SELECT * INTO existing FROM accounting.accounts
        WHERE code=definition.code OR system_key=definition.system_key;
        IF FOUND THEN
            IF existing.code<>definition.code OR existing.system_key<>definition.system_key
               OR existing.account_type<>'liability'
               OR existing.normal_balance<>'credit' OR NOT existing.is_posting
               OR (SELECT count(*) FROM accounting.accounts WHERE code=definition.code OR system_key=definition.system_key)<>1 THEN
                RAISE EXCEPTION 'Liability control chart collision at %; existing definitions cannot be overwritten.', definition.code;
            END IF;
        ELSE
            INSERT INTO accounting.accounts(code,system_key,name,account_type,normal_balance)
            VALUES(definition.code,definition.system_key,definition.name,'liability','credit');
        END IF;
    END LOOP;
    IF NOT EXISTS (SELECT 1 FROM accounting.accounts WHERE code='2000' AND system_key='accounts_payable'
        AND account_type='liability' AND normal_balance='credit' AND is_posting) THEN
        RAISE EXCEPTION 'Existing accounts payable control is incompatible.';
    END IF;
END;
$chart$;

-- Reconciliation depends on these seeded identities, including unregistered
-- posted balances. Retirement and display-name edits preserve their meaning.
CREATE OR REPLACE FUNCTION accounting.guard_liability_control_definition()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
    IF OLD.code IN ('2000','2300','2310','2320','2330','2340') THEN
        IF TG_OP='DELETE' THEN
            RAISE EXCEPTION 'Liability control definitions are immutable; retire the account instead.';
        END IF;
        IF ROW(NEW.id,NEW.code,NEW.system_key,NEW.account_type,NEW.normal_balance,NEW.is_posting)
           IS DISTINCT FROM ROW(OLD.id,OLD.code,OLD.system_key,OLD.account_type,OLD.normal_balance,OLD.is_posting) THEN
            RAISE EXCEPTION 'Liability control definitions are immutable; only display name and active status may change.';
        END IF;
    END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS liability_control_definition ON accounting.accounts;
CREATE TRIGGER liability_control_definition BEFORE UPDATE OR DELETE ON accounting.accounts
FOR EACH ROW EXECUTE FUNCTION accounting.guard_liability_control_definition();

CREATE TABLE IF NOT EXISTS accounting.liability_obligations (
    id UUID PRIMARY KEY,
    book_id UUID NOT NULL REFERENCES accounting.book_identity(id),
    kind TEXT NOT NULL CHECK(kind IN ('trade_payable','borrowing_external','borrowing_owner','interest','wages','contrib')),
    counterparty TEXT NOT NULL CHECK(length(counterparty)>=1 AND length(counterparty)<=200 AND counterparty !~ '(^[[:space:]]|[[:space:]]$)'),
    due_date DATE,
    account_id UUID NOT NULL REFERENCES accounting.accounts(id),
    account_code TEXT NOT NULL CHECK(account_code IN ('2000','2300','2310','2320','2330','2340')),
    recognition_date DATE NOT NULL,
    recognized_amount NUMERIC(18,2) NOT NULL CHECK(recognized_amount>0),
    created_by_user_id UUID NOT NULL REFERENCES core.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS accounting.liability_line_claims (
    id UUID PRIMARY KEY,
    obligation_id UUID NOT NULL REFERENCES accounting.liability_obligations(id),
    book_id UUID NOT NULL REFERENCES accounting.book_identity(id),
    journal_line_id UUID NOT NULL UNIQUE REFERENCES accounting.journal_lines(id),
    kind TEXT NOT NULL CHECK(kind IN ('recognition','settlement','reversal')),
    reverses_claim_id UUID UNIQUE REFERENCES accounting.liability_line_claims(id),
    posting_date DATE NOT NULL,
    signed_amount NUMERIC(18,2) NOT NULL CHECK(signed_amount<>0),
    payload JSONB NOT NULL CHECK(jsonb_typeof(payload)='object'),
    created_by_user_id UUID NOT NULL REFERENCES core.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK((kind='reversal')=(reverses_claim_id IS NOT NULL)),
    CHECK(kind<>'recognition' OR signed_amount>0),
    CHECK(kind<>'settlement' OR signed_amount<0)
);
CREATE INDEX IF NOT EXISTS liability_claim_obligation_date ON accounting.liability_line_claims(obligation_id,posting_date);
ALTER TABLE accounting.liability_obligations ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounting.liability_line_claims ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION accounting.guard_liability_schedule_write()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
    IF TG_OP='INSERT' AND current_setting('accounting.liability_schedule_insert_allowed',true)='on' THEN RETURN NEW; END IF;
    RAISE EXCEPTION 'Liability schedule and retained source evidence are immutable; use protected registration.';
END;
$$;
DROP TRIGGER IF EXISTS liability_obligation_write ON accounting.liability_obligations;
CREATE TRIGGER liability_obligation_write BEFORE INSERT OR UPDATE OR DELETE ON accounting.liability_obligations
FOR EACH ROW EXECUTE FUNCTION accounting.guard_liability_schedule_write();
DROP TRIGGER IF EXISTS liability_obligation_truncate ON accounting.liability_obligations;
CREATE TRIGGER liability_obligation_truncate BEFORE TRUNCATE ON accounting.liability_obligations
FOR EACH STATEMENT EXECUTE FUNCTION accounting.guard_liability_schedule_write();
DROP TRIGGER IF EXISTS liability_claim_write ON accounting.liability_line_claims;
CREATE TRIGGER liability_claim_write BEFORE INSERT OR UPDATE OR DELETE ON accounting.liability_line_claims
FOR EACH ROW EXECUTE FUNCTION accounting.guard_liability_schedule_write();
DROP TRIGGER IF EXISTS liability_claim_truncate ON accounting.liability_line_claims;
CREATE TRIGGER liability_claim_truncate BEFORE TRUNCATE ON accounting.liability_line_claims
FOR EACH STATEMENT EXECUTE FUNCTION accounting.guard_liability_schedule_write();

CREATE OR REPLACE FUNCTION accounting.require_liability_actor(p_actor UUID,p_permission TEXT)
RETURNS VOID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
    IF p_permission NOT IN ('accounting.view','accounting.journal.manage') THEN RAISE EXCEPTION 'Unsupported liability permission.'; END IF;
    IF p_permission='accounting.journal.manage' AND current_setting('transaction_isolation')<>'read committed' THEN
        RAISE EXCEPTION 'Liability writes require READ COMMITTED so locked balances see prior commits.' USING ERRCODE='55000';
    END IF;
    PERFORM actor.id FROM core.users actor
    JOIN core.user_roles membership ON membership.user_id=actor.id
    JOIN core.roles role ON role.id=membership.role_id
    JOIN core.role_permissions permission ON permission.role_id=role.id
    WHERE actor.id=p_actor AND actor.status='active' AND role.code='management'
      AND permission.permission_code=p_permission FOR SHARE OF actor,membership,role,permission;
    IF NOT FOUND THEN RAISE EXCEPTION 'Current active Management accounting permission is required.' USING ERRCODE='42501'; END IF;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.validate_liability_payload(p_payload JSONB,p_keys TEXT[])
RETURNS VOID LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
    IF p_payload IS NULL OR jsonb_typeof(p_payload)<>'object' OR NOT p_payload ?& p_keys
       OR EXISTS (SELECT 1 FROM jsonb_object_keys(p_payload) key WHERE NOT key=ANY(p_keys)) THEN
        RAISE EXCEPTION 'Exact liability source coordinates and evidence fields are required.' USING ERRCODE='22023';
    END IF;
    IF p_payload->'reviewed' IS DISTINCT FROM 'true'::jsonb
       OR jsonb_typeof(p_payload->'expected_amount') IS DISTINCT FROM 'string'
       OR (p_payload->>'expected_amount') !~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$'
       OR (p_payload->>'expected_amount')::numeric<=0
       OR jsonb_typeof(p_payload->'evidence_reference') IS DISTINCT FROM 'string'
       OR length(p_payload->>'evidence_reference') NOT BETWEEN 1 AND 1000
       OR (p_payload->>'evidence_reference') ~ '(^[[:space:]]|[[:space:]]$)'
       OR jsonb_typeof(p_payload->'evidence_digest') IS DISTINCT FROM 'string'
       OR (p_payload->>'evidence_digest') !~ '^[0-9a-f]{64}$'
       OR jsonb_typeof(p_payload->'expected_source_type') IS DISTINCT FROM 'string'
       OR jsonb_typeof(p_payload->'expected_source_reference') NOT IN ('string','null') THEN
        RAISE EXCEPTION 'Reviewed exact-cent amount and retained liability evidence are required.' USING ERRCODE='22023';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.liability_source_line(p_payload JSONB)
RETURNS TABLE(journal_line_id UUID,journal_entry_id UUID,account_id UUID,account_code TEXT,
    posting_date DATE,debit NUMERIC,credit NUMERIC,line_number INTEGER,source_type TEXT,reversal_of_entry_id UUID)
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE source RECORD;
BEGIN
    SELECT line.id AS journal_line_id,line.journal_entry_id,line.account_id,account.code AS account_code,
           journal.posting_date,line.debit,line.credit,line.line_number,journal.source_type,journal.reversal_of_entry_id,
           journal.status,journal.source_reference,journal.source_event_key,line.client_id,line.loan_id,
           account.account_type,account.normal_balance,account.is_posting
    INTO source FROM accounting.journal_lines line
    JOIN accounting.journal_entries journal ON journal.id=line.journal_entry_id
    JOIN accounting.accounts account ON account.id=line.account_id
    WHERE line.id=(p_payload->>'journal_line_id')::uuid FOR SHARE OF line,journal,account;
    IF NOT FOUND OR source.status<>'posted' OR source.account_type<>'liability' OR source.normal_balance<>'credit'
       OR NOT source.is_posting OR source.account_code NOT IN ('2000','2300','2310','2320','2330','2340')
       OR source.client_id IS NOT NULL OR source.loan_id IS NOT NULL
       OR source.account_code IS DISTINCT FROM p_payload->>'expected_account_code'
       OR source.debit+source.credit IS DISTINCT FROM (p_payload->>'expected_amount')::numeric
       OR source.posting_date IS DISTINCT FROM (p_payload->>'expected_posting_date')::date
       OR source.source_type IS DISTINCT FROM p_payload->>'expected_source_type'
       OR source.source_reference IS DISTINCT FROM p_payload->>'expected_source_reference' THEN
        RAISE EXCEPTION 'Posted liability source coordinates do not match the reviewed line.' USING ERRCODE='55000';
    END IF;
    IF source.source_type='manual' THEN
        IF source.reversal_of_entry_id IS NOT NULL OR source.source_reference IS NOT NULL OR source.source_event_key IS NOT NULL THEN
            RAISE EXCEPTION 'Manual liability source cannot copy a managed source identity.' USING ERRCODE='55000';
        END IF;
    ELSIF source.source_type='opening_balance' THEN
        IF source.reversal_of_entry_id IS NOT NULL OR NOT EXISTS (
            SELECT 1 FROM accounting.opening_balance_journal_postings posting
            JOIN accounting.opening_balance_journal_preparations prep ON prep.workbook_id=posting.workbook_id
            WHERE posting.journal_entry_id=source.journal_entry_id AND prep.journal_entry_id=source.journal_entry_id
              AND source.source_reference=posting.workbook_id::text
              AND source.source_event_key='opening_balance:'||posting.workbook_id::text
        ) THEN RAISE EXCEPTION 'Protected opening liability posting evidence is required.' USING ERRCODE='55000'; END IF;
    ELSIF source.source_type IS DISTINCT FROM 'reversal' THEN
        RAISE EXCEPTION 'Managed liability source requires its dedicated accounting adapter.' USING ERRCODE='55000';
    END IF;
    RETURN QUERY SELECT source.journal_line_id,source.journal_entry_id,source.account_id,source.account_code,
        source.posting_date,source.debit,source.credit,source.line_number,source.source_type,source.reversal_of_entry_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.register_liability_obligation(p_request_id UUID,p_expected_book_id UUID,p_payload JSONB,p_actor_user_id UUID)
RETURNS UUID LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE book UUID; existing accounting.liability_line_claims%ROWTYPE; source RECORD;
    expected_code TEXT; prior_setting TEXT;
BEGIN
    PERFORM accounting.require_liability_actor(p_actor_user_id,'accounting.journal.manage');
    SELECT id INTO book FROM accounting.book_identity WHERE singleton;
    IF book IS NULL OR book IS DISTINCT FROM p_expected_book_id THEN RAISE EXCEPTION 'Accounting book does not match reviewed liability evidence.' USING ERRCODE='55000'; END IF;
    IF p_request_id IS NULL THEN RAISE EXCEPTION 'Liability request identity is required.' USING ERRCODE='22023'; END IF;
    PERFORM accounting.validate_liability_payload(p_payload,ARRAY['kind','counterparty','due_date','journal_line_id','expected_account_code','expected_amount','expected_posting_date','expected_source_type','expected_source_reference','evidence_reference','evidence_digest','reviewed']);
    expected_code := CASE p_payload->>'kind' WHEN 'trade_payable' THEN '2000' WHEN 'borrowing_external' THEN '2300'
        WHEN 'borrowing_owner' THEN '2310' WHEN 'interest' THEN '2320' WHEN 'wages' THEN '2330' WHEN 'contrib' THEN '2340' END;
    IF expected_code IS NULL OR jsonb_typeof(p_payload->'counterparty') IS DISTINCT FROM 'string'
       OR length(p_payload->>'counterparty') NOT BETWEEN 1 AND 200
       OR p_payload->>'counterparty' ~ '(^[[:space:]]|[[:space:]]$)'
       OR jsonb_typeof(p_payload->'due_date') NOT IN ('string','null') THEN
        RAISE EXCEPTION 'Supported liability kind, exact counterparty and due date are required.' USING ERRCODE='22023';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('liability-request:'||p_request_id::text,0));
    SELECT * INTO existing FROM accounting.liability_line_claims WHERE id=p_request_id;
    IF FOUND THEN
        IF existing.kind='recognition' AND existing.book_id=book AND existing.payload=p_payload AND existing.created_by_user_id=p_actor_user_id THEN RETURN existing.obligation_id; END IF;
        RAISE EXCEPTION 'Liability request conflict: retained coordinates, evidence or actor changed.' USING ERRCODE='55000';
    END IF;
    SELECT * INTO source FROM accounting.liability_source_line(p_payload);
    IF source.account_code<>expected_code OR source.credit<=0 OR source.debit<>0
       OR source.source_type NOT IN ('manual','opening_balance') OR source.reversal_of_entry_id IS NOT NULL THEN
        RAISE EXCEPTION 'Liability kind requires its exact original posted credit control line.' USING ERRCODE='55000';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('liability-line:'||source.journal_line_id::text,0));
    IF EXISTS (SELECT 1 FROM accounting.liability_line_claims WHERE journal_line_id=source.journal_line_id) THEN
        RAISE EXCEPTION 'Posted journal line is already claimed by the liability schedule.' USING ERRCODE='55000';
    END IF;
    prior_setting := current_setting('accounting.liability_schedule_insert_allowed',true);
    PERFORM set_config('accounting.liability_schedule_insert_allowed','on',true);
    INSERT INTO accounting.liability_obligations(id,book_id,kind,counterparty,due_date,account_id,account_code,recognition_date,recognized_amount,created_by_user_id)
    VALUES(p_request_id,book,p_payload->>'kind',p_payload->>'counterparty',(p_payload->>'due_date')::date,source.account_id,source.account_code,source.posting_date,source.credit,p_actor_user_id);
    INSERT INTO accounting.liability_line_claims(id,obligation_id,book_id,journal_line_id,kind,posting_date,signed_amount,payload,created_by_user_id)
    VALUES(p_request_id,p_request_id,book,source.journal_line_id,'recognition',source.posting_date,source.credit,p_payload,p_actor_user_id);
    PERFORM set_config('accounting.liability_schedule_insert_allowed',coalesce(prior_setting,''),true);
    INSERT INTO core.audit_logs(actor_user_id,action,target_type,target_id,details)
    VALUES(p_actor_user_id,'accounting.liability.registered','liability_obligation',p_request_id,jsonb_build_object('book_id',book,'journal_line_id',source.journal_line_id,'evidence_digest',p_payload->>'evidence_digest'));
    RETURN p_request_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.record_liability_movement(p_request_id UUID,p_expected_book_id UUID,p_payload JSONB,p_actor_user_id UUID)
RETURNS UUID LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE book UUID; existing accounting.liability_line_claims%ROWTYPE; obligation accounting.liability_obligations%ROWTYPE;
    original accounting.liability_line_claims%ROWTYPE; original_line accounting.journal_lines%ROWTYPE;
    source RECORD; delta NUMERIC(18,2); original_id UUID; prior_setting TEXT;
BEGIN
    PERFORM accounting.require_liability_actor(p_actor_user_id,'accounting.journal.manage');
    SELECT id INTO book FROM accounting.book_identity WHERE singleton;
    IF book IS NULL OR book IS DISTINCT FROM p_expected_book_id THEN RAISE EXCEPTION 'Accounting book does not match reviewed liability evidence.' USING ERRCODE='55000'; END IF;
    IF p_request_id IS NULL THEN RAISE EXCEPTION 'Liability request identity is required.' USING ERRCODE='22023'; END IF;
    PERFORM accounting.validate_liability_payload(p_payload,ARRAY['obligation_id','kind','reverses_claim_id','journal_line_id','expected_account_code','expected_amount','expected_posting_date','expected_source_type','expected_source_reference','evidence_reference','evidence_digest','reviewed']);
    IF p_payload->>'kind' NOT IN ('settlement','reversal') OR p_payload->>'kind' IS NULL THEN RAISE EXCEPTION 'Supported liability movement is required.' USING ERRCODE='22023'; END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('liability-request:'||p_request_id::text,0));
    SELECT * INTO existing FROM accounting.liability_line_claims WHERE id=p_request_id;
    IF FOUND THEN
        IF existing.kind<>'recognition' AND existing.book_id=book AND existing.payload=p_payload AND existing.created_by_user_id=p_actor_user_id THEN RETURN existing.id; END IF;
        RAISE EXCEPTION 'Liability request conflict: retained coordinates, evidence or actor changed.' USING ERRCODE='55000';
    END IF;
    SELECT * INTO obligation FROM accounting.liability_obligations WHERE id=(p_payload->>'obligation_id')::uuid FOR UPDATE;
    IF NOT FOUND OR obligation.book_id<>book THEN RAISE EXCEPTION 'Liability obligation is unavailable for this book.' USING ERRCODE='55000'; END IF;
    SELECT * INTO source FROM accounting.liability_source_line(p_payload);
    IF source.account_id<>obligation.account_id OR source.posting_date<obligation.recognition_date THEN
        RAISE EXCEPTION 'Liability movement account or date differs from its obligation.' USING ERRCODE='55000';
    END IF;
    original_id := (p_payload->>'reverses_claim_id')::uuid;
    IF p_payload->>'kind'='settlement' THEN
        IF original_id IS NOT NULL OR source.source_type<>'manual' OR source.reversal_of_entry_id IS NOT NULL OR source.debit<=0 OR source.credit<>0 THEN
            RAISE EXCEPTION 'Settlement requires a reviewed original manual liability debit line.' USING ERRCODE='55000';
        END IF;
        delta := -source.debit;
    ELSE
        SELECT * INTO original FROM accounting.liability_line_claims WHERE id=original_id;
        IF NOT FOUND OR original.obligation_id<>obligation.id OR original.kind='reversal' OR source.posting_date<original.posting_date THEN
            RAISE EXCEPTION 'Exact original liability claim is required for reversal.' USING ERRCODE='55000';
        END IF;
        SELECT * INTO original_line FROM accounting.journal_lines WHERE id=original.journal_line_id;
        IF source.source_type<>'reversal' OR source.reversal_of_entry_id IS DISTINCT FROM original_line.journal_entry_id
           OR source.line_number<>original_line.line_number OR source.account_id<>original_line.account_id
           OR source.debit<>original_line.credit OR source.credit<>original_line.debit
           OR EXISTS (SELECT 1 FROM accounting.liability_line_claims WHERE reverses_claim_id=original_id) THEN
            RAISE EXCEPTION 'Liability reversal must claim the exact unclaimed inverted original journal line.' USING ERRCODE='55000';
        END IF;
        delta := -original.signed_amount;
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('liability-line:'||source.journal_line_id::text,0));
    IF EXISTS (SELECT 1 FROM accounting.liability_line_claims WHERE journal_line_id=source.journal_line_id) THEN
        RAISE EXCEPTION 'Posted journal line is already claimed by the liability schedule.' USING ERRCODE='55000';
    END IF;
    IF EXISTS (
        SELECT 1 FROM (
            SELECT sum(sum(amount)) OVER (ORDER BY effective_date) AS running
            FROM (SELECT posting_date AS effective_date,signed_amount AS amount FROM accounting.liability_line_claims WHERE obligation_id=obligation.id
                UNION ALL SELECT source.posting_date,delta) facts GROUP BY effective_date
        ) balances WHERE running<0
    ) THEN RAISE EXCEPTION 'Liability movement would exceed the obligation or create a negative historical balance.' USING ERRCODE='55000'; END IF;
    prior_setting := current_setting('accounting.liability_schedule_insert_allowed',true);
    PERFORM set_config('accounting.liability_schedule_insert_allowed','on',true);
    INSERT INTO accounting.liability_line_claims(id,obligation_id,book_id,journal_line_id,kind,reverses_claim_id,posting_date,signed_amount,payload,created_by_user_id)
    VALUES(p_request_id,obligation.id,book,source.journal_line_id,p_payload->>'kind',original_id,source.posting_date,delta,p_payload,p_actor_user_id);
    PERFORM set_config('accounting.liability_schedule_insert_allowed',coalesce(prior_setting,''),true);
    INSERT INTO core.audit_logs(actor_user_id,action,target_type,target_id,details)
    VALUES(p_actor_user_id,'accounting.liability.movement_recorded','liability_obligation',obligation.id,jsonb_build_object('claim_id',p_request_id,'journal_line_id',source.journal_line_id,'kind',p_payload->>'kind','evidence_digest',p_payload->>'evidence_digest'));
    RETURN p_request_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.liability_control_schedule(p_as_of DATE)
RETURNS TABLE(obligation_id UUID,book_id UUID,kind TEXT,counterparty TEXT,due_date DATE,account_code TEXT,
    recognition_date DATE,recognized_amount NUMERIC,outstanding_amount NUMERIC,evidence_reference TEXT,evidence_digest TEXT)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
    SELECT obligation.id,obligation.book_id,obligation.kind,obligation.counterparty,obligation.due_date,obligation.account_code,
        obligation.recognition_date,obligation.recognized_amount,sum(claim.signed_amount),
        recognition.payload->>'evidence_reference',recognition.payload->>'evidence_digest'
    FROM accounting.liability_obligations obligation
    JOIN accounting.liability_line_claims recognition ON recognition.id=obligation.id AND recognition.kind='recognition'
    JOIN accounting.liability_line_claims claim ON claim.obligation_id=obligation.id AND claim.posting_date<=p_as_of
    WHERE obligation.recognition_date<=p_as_of
    GROUP BY obligation.id,recognition.payload ORDER BY obligation.account_code,obligation.recognition_date,obligation.id;
$$;

CREATE OR REPLACE FUNCTION accounting.liability_control_reconciliation(p_as_of DATE)
RETURNS TABLE(account_code TEXT,ledger_balance NUMERIC,schedule_balance NUMERIC,difference NUMERIC,unregistered_line_count BIGINT)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
    SELECT account.code,coalesce(ledger.amount,0),coalesce(schedule.amount,0),coalesce(ledger.amount,0)-coalesce(schedule.amount,0),coalesce(ledger.unregistered,0)
    FROM accounting.accounts account
    LEFT JOIN LATERAL (
        SELECT sum(line.credit-line.debit) AS amount,count(*) FILTER(WHERE claim.id IS NULL) AS unregistered
        FROM accounting.journal_lines line JOIN accounting.journal_entries journal ON journal.id=line.journal_entry_id
        LEFT JOIN accounting.liability_line_claims claim ON claim.journal_line_id=line.id
        WHERE line.account_id=account.id AND journal.status='posted' AND journal.posting_date<=p_as_of
    ) ledger ON true
    LEFT JOIN LATERAL (
        SELECT sum(item.outstanding_amount) AS amount FROM accounting.liability_control_schedule(p_as_of) item WHERE item.account_code=account.code
    ) schedule ON true
    WHERE account.code IN ('2000','2300','2310','2320','2330','2340') ORDER BY account.code;
$$;

REVOKE ALL ON accounting.liability_obligations,accounting.liability_line_claims FROM PUBLIC;
REVOKE ALL ON FUNCTION accounting.guard_liability_control_definition(),accounting.guard_liability_schedule_write(),accounting.require_liability_actor(UUID,TEXT),
    accounting.validate_liability_payload(JSONB,TEXT[]),accounting.liability_source_line(JSONB),
    accounting.register_liability_obligation(UUID,UUID,JSONB,UUID),accounting.record_liability_movement(UUID,UUID,JSONB,UUID),
    accounting.liability_control_schedule(DATE),accounting.liability_control_reconciliation(DATE) FROM PUBLIC;
DO $private$
DECLARE client_role TEXT;
BEGIN
    FOR client_role IN SELECT rolname FROM pg_roles WHERE rolname IN ('anon','authenticated','service_role') LOOP
        EXECUTE format('REVOKE ALL ON accounting.liability_obligations,accounting.liability_line_claims FROM %I',client_role);
        EXECUTE format('REVOKE ALL ON FUNCTION accounting.guard_liability_control_definition(),accounting.guard_liability_schedule_write(),accounting.require_liability_actor(UUID,TEXT),accounting.validate_liability_payload(JSONB,TEXT[]),accounting.liability_source_line(JSONB),accounting.register_liability_obligation(UUID,UUID,JSONB,UUID),accounting.record_liability_movement(UUID,UUID,JSONB,UUID),accounting.liability_control_schedule(DATE),accounting.liability_control_reconciliation(DATE) FROM %I',client_role);
    END LOOP;
END;
$private$;

COMMENT ON TABLE accounting.liability_line_claims IS 'Immutable attribution of existing posted generic liability lines. No journal posting or cash action. Managed Treasury/Collector/tax controls require dedicated adapters.';
COMMIT;
