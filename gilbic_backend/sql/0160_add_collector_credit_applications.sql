BEGIN;

-- Retained Collector credit consumption and separately dated actual cash.
-- Operational entry remains behind SPINA_COLLECTOR_SURPLUS_APPLICATION_ENABLED.
-- Deployment requires the coordinated migration/evidence recovery procedure.
ALTER TABLE treasury.collector_entries DROP CONSTRAINT collector_entries_required;
ALTER TABLE treasury.collector_entries ADD CONSTRAINT collector_entries_required CHECK (
 payload ?& ARRAY['credit_id','kind','amount','action_id']
 AND jsonb_typeof(payload->'amount')='string'
 AND (payload->>'amount') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$'
 AND jsonb_typeof(payload->'kind')='string'
 AND payload->>'kind' IN('recognition','opening','return','return_reversal','application'));

CREATE TABLE treasury.collector_credit_applications (
 id UUID PRIMARY KEY REFERENCES treasury.collector_entries(id),
 action_id UUID NOT NULL UNIQUE REFERENCES treasury.collector_actions(id),
 credit_id UUID NOT NULL REFERENCES treasury.collector_credits(id),
 settlement_id UUID NOT NULL UNIQUE REFERENCES treasury.collector_settlements(id),
 count_id UUID NOT NULL UNIQUE REFERENCES treasury.collector_counts(id),
 remittance_id UUID NOT NULL UNIQUE REFERENCES lending.collection_remittances(id),
 origin_account_id UUID NOT NULL REFERENCES treasury.accounts(id),
 account_id UUID NOT NULL REFERENCES treasury.accounts(id),
 ledger_context_id UUID NOT NULL REFERENCES treasury.contexts(id),
 collector_user_id UUID NOT NULL REFERENCES core.users(id),
 amount NUMERIC(18,2) NOT NULL CHECK(amount>0),
 accepted_at TIMESTAMPTZ NOT NULL,
 approval_snapshot JSONB NOT NULL CHECK(jsonb_typeof(approval_snapshot)='object'),
 created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
 CHECK(accepted_at<=created_at),
 FOREIGN KEY(id,account_id,ledger_context_id,collector_user_id)
  REFERENCES treasury.collector_entries(id,account_id,ledger_context_id,collector_user_id),
 FOREIGN KEY(action_id,account_id,ledger_context_id,collector_user_id)
  REFERENCES treasury.collector_actions(id,account_id,ledger_context_id,collector_user_id),
 FOREIGN KEY(credit_id,origin_account_id,ledger_context_id,collector_user_id)
  REFERENCES treasury.collector_credits(id,account_id,ledger_context_id,collector_user_id),
 FOREIGN KEY(count_id,account_id,ledger_context_id,collector_user_id)
  REFERENCES treasury.collector_counts(id,account_id,ledger_context_id,collector_user_id),
 FOREIGN KEY(settlement_id,account_id,ledger_context_id,collector_user_id)
  REFERENCES treasury.collector_settlements(id,account_id,ledger_context_id,collector_user_id)
);
ALTER TABLE treasury.collector_credit_applications ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON treasury.collector_credit_applications FROM PUBLIC;
CREATE INDEX collector_credit_application_credit_idx ON treasury.collector_credit_applications(credit_id,accepted_at,id);
CREATE UNIQUE INDEX collector_application_live_remittance_idx ON treasury.collector_actions((payload->>'remittance_id'))
 WHERE payload->>'kind'='application' AND payload->>'status'<>'cancelled';
ALTER TABLE treasury.collector_actions ADD CONSTRAINT collector_application_approval_fields CHECK (
 payload->>'kind'<>'application' OR (
 payload ?& ARRAY['remittance_id','recipient_user_id','approved_by_user_id','source_digest','source_timezone']
 AND jsonb_typeof(payload->'remittance_id')='string'
 AND jsonb_typeof(payload->'recipient_user_id')='string'
 AND jsonb_typeof(payload->'approved_by_user_id')='string'
 AND jsonb_typeof(payload->'source_timezone')='string'
 AND jsonb_typeof(payload->'source_digest')='string'
 AND payload->>'source_digest' ~ '^[a-f0-9]{64}$'
 AND payload->'destination'='null'::jsonb
 AND payload->'event_id'='null'::jsonb
 AND payload->'event_version'='null'::jsonb
 AND payload->'acknowledgment_id'='null'::jsonb
 AND payload->>'status' IN('reserved','applied','cancelled')));

CREATE FUNCTION treasury.collector_application_exact(p_id UUID) RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
 SELECT EXISTS(
 SELECT 1 FROM treasury.collector_credit_applications app
 JOIN treasury.collector_entries entry ON entry.id=app.id
 JOIN treasury.collector_actions action ON action.id=app.action_id
 JOIN treasury.collector_credits credit ON credit.id=app.credit_id
 JOIN treasury.collector_requests request ON request.id=(action.payload->>'collector_request_id')::uuid
 JOIN treasury.collector_counts counted ON counted.id=app.count_id
 JOIN treasury.collector_settlements settlement ON settlement.id=app.settlement_id
 JOIN lending.collection_remittances remittance ON remittance.id=app.remittance_id
 LEFT JOIN treasury.events event ON event.id=settlement.event_id
 LEFT JOIN treasury.collector_cases excess ON excess.settlement_id=settlement.id
 WHERE app.id=p_id
 AND app.amount<=remittance.total_amount
 AND entry.credit_id=app.credit_id AND entry.payload->>'kind'='application'
 AND entry.payload->>'action_id'=app.action_id::text
 AND entry.payload->>'settlement_id'=app.settlement_id::text
 AND (entry.payload->>'amount')::numeric=app.amount
 AND (entry.payload->>'accepted_at')::timestamptz=app.accepted_at
 AND entry.payload->>'evidence_id'=counted.evidence_id::text
 AND action.credit_id=app.credit_id AND action.payload->>'kind'='application'
 AND action.payload->>'status'='applied' AND action.event_id IS NULL
 AND action.version=(app.approval_snapshot->>'version')::integer+1
 AND app.approval_snapshot->>'status'='reserved'
 AND app.approval_snapshot->>'id'=action.id::text
 AND app.approval_snapshot->>'account_id'=app.account_id::text
 AND app.approval_snapshot->>'ledger_context_id'=app.ledger_context_id::text
 AND app.approval_snapshot->>'collector_user_id'=app.collector_user_id::text
 AND (app.approval_snapshot->>'created_at')::timestamptz=action.created_at
 AND action.created_at<=app.accepted_at
 AND (action.payload-ARRAY['status','event_id','event_version','acknowledgment_id','cancellation_evidence_id','cancellation_reason','reversed_amount'])=
  (app.approval_snapshot-ARRAY['id','version','account_id','ledger_context_id','collector_user_id','created_at','status','event_id','event_version','acknowledgment_id','cancellation_evidence_id','cancellation_reason','reversed_amount'])
 AND action.payload->>'origin_account_id'=app.origin_account_id::text
 AND action.payload->>'paying_account_id'=app.account_id::text
 AND action.payload->>'remittance_id'=app.remittance_id::text
 AND action.payload->>'recipient_user_id'=remittance.recipient_user_id::text
 AND action.payload->>'approved_by_user_id'<>app.collector_user_id::text
 AND action.payload->>'approved_by_user_id'=remittance.recipient_user_id::text
 AND (action.payload->>'amount')::numeric=app.amount
 AND request.credit_id=app.credit_id AND request.collector_user_id=app.collector_user_id
 AND request.payload->>'kind'='application' AND request.payload->>'status'='approved'
 AND request.payload->>'remittance_id'=app.remittance_id::text
 AND request.payload->>'source_digest'=action.payload->>'source_digest'
 AND (request.payload->>'amount')::numeric=app.amount
 AND counted.remittance_id=app.remittance_id AND settlement.remittance_id=app.remittance_id
 AND settlement.count_id=counted.id AND counted.collector_user_id=remittance.collector_user_id
 AND counted.payload->>'recipient_user_id'=remittance.recipient_user_id::text
 AND settlement.payload->>'recipient_user_id'=remittance.recipient_user_id::text
 AND counted.payload->'credit_application'=app.approval_snapshot
 AND counted.payload->>'credit_application_id'=app.action_id::text
 AND (counted.payload->>'credit_application_version')::integer=(app.approval_snapshot->>'version')::integer
 AND counted.payload->>'remittance_source_digest'=action.payload->>'source_digest'
 AND (counted.payload->>'authorized_credit_application')::numeric=app.amount
 AND (counted.payload->>'refund_due_total')::numeric=0
 AND (counted.payload->>'gross_obligation')::numeric=remittance.total_amount
 AND (counted.payload->>'physical_cash_required')::numeric=remittance.total_amount-app.amount
 AND (counted.payload->>'counted_amount')::numeric>=(counted.payload->>'physical_cash_required')::numeric
 AND counted.payload->>'disposition'='counted_ready'
 AND (counted.payload->>'difference')::numeric=(counted.payload->>'counted_amount')::numeric-(counted.payload->>'physical_cash_required')::numeric
 AND (counted.payload->>'counted_at')::timestamptz<=app.accepted_at
 AND (settlement.payload->>'accepted_at')::timestamptz=app.accepted_at
 AND (settlement.payload->>'authorized_credit_amount')::numeric=app.amount
 AND (settlement.payload->>'gross_obligation')::numeric=remittance.total_amount
 AND (settlement.payload->>'physical_amount')::numeric=(counted.payload->>'counted_amount')::numeric
 AND remittance.status='received' AND remittance.received_at=app.accepted_at
 AND remittance.received_by_user_id=remittance.recipient_user_id
 AND remittance.custody_user_id=remittance.recipient_user_id
 AND NOT EXISTS(SELECT 1 FROM lending.collection_remittance_refund_due_release_items WHERE remittance_id=app.remittance_id)
 AND NOT EXISTS(SELECT 1 FROM treasury.collector_exceptions WHERE payload->>'remittance_id'=app.remittance_id::text)
 AND ((counted.payload->>'difference')::numeric=0 AND excess.id IS NULL
   OR (counted.payload->>'difference')::numeric>0 AND excess.id IS NOT NULL
    AND (excess.payload->>'received_excess_amount')::numeric=(counted.payload->>'difference')::numeric)
 AND ((counted.payload->>'counted_amount')::numeric=0 AND event.id IS NULL
   OR (counted.payload->>'counted_amount')::numeric>0 AND event.id IS NOT NULL
    AND event.account_id=app.account_id AND event.ledger_context_id=app.ledger_context_id
    AND event.direction='credit' AND event.fee=0 AND event.amount=(counted.payload->>'counted_amount')::numeric
    AND event.version=1 AND event.verified_by_user_id IS NOT NULL
    AND event.verified_by_user_id=remittance.recipient_user_id
    AND event.evidence_id=counted.evidence_id
    AND event.recipient_attestation=counted.payload->>'recipient_attestation'
    AND event.effective_at=(counted.payload->>'counted_at')::timestamptz
    AND event.classification='collector_counted_receipt'
    AND NOT EXISTS(SELECT 1 FROM treasury.event_revisions WHERE event_id=event.id)
    AND (SELECT count(*) FROM treasury.movement_lines WHERE event_id=event.id)=1
    AND EXISTS(SELECT 1 FROM treasury.movement_lines WHERE event_id=event.id AND component='principal'
      AND signed_amount=event.amount AND account_id=app.account_id AND ledger_context_id=app.ledger_context_id
      AND effective_at=event.effective_at AND evidence_id=event.evidence_id)
    AND (SELECT count(*) FROM treasury.source_links WHERE event_id=event.id)=
      (CASE WHEN (counted.payload->>'physical_cash_required')::numeric>0 THEN 1 ELSE 0 END)
      +(CASE WHEN (counted.payload->>'difference')::numeric>0 THEN 1 ELSE 0 END)
    AND ((counted.payload->>'physical_cash_required')::numeric=0 OR EXISTS(
      SELECT 1 FROM treasury.source_links WHERE event_id=event.id AND source_kind='collector_remittance_physical'
      AND source_id=app.remittance_id AND linked_amount=(counted.payload->>'physical_cash_required')::numeric AND ledger_context_id=app.ledger_context_id))
    AND ((counted.payload->>'difference')::numeric=0 OR EXISTS(
      SELECT 1 FROM treasury.source_links WHERE event_id=event.id AND source_kind='collector_excess_pending'
      AND source_id=excess.id AND linked_amount=(counted.payload->>'difference')::numeric AND ledger_context_id=app.ledger_context_id)))
 );
$$;

CREATE FUNCTION treasury.collector_application_credit_valid(p_credit UUID) RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT EXISTS(SELECT 1 FROM treasury.collector_credits credit JOIN treasury.collector_cases excess ON excess.id=credit.case_id
 WHERE credit.id=p_credit AND credit.opening_anchor_id IS NULL AND excess.settlement_id IS NOT NULL
 AND (credit.payload->>'frozen')::boolean=false AND (credit.payload->>'reclassified_amount')::numeric=0
 AND (SELECT count(*) FROM treasury.collector_entries WHERE credit_id=credit.id AND payload->>'kind'='recognition')=1
 AND (credit.payload->>'recognized_amount')::numeric=(SELECT sum((payload->>'amount')::numeric) FROM treasury.collector_entries WHERE credit_id=credit.id AND payload->>'kind'='recognition')
 AND (credit.payload->>'applied_amount')::numeric=(SELECT coalesce(sum((payload->>'amount')::numeric),0) FROM treasury.collector_entries WHERE credit_id=credit.id AND payload->>'kind'='application')
 AND (credit.payload->>'returned_amount')::numeric=(SELECT coalesce(sum(CASE payload->>'kind' WHEN 'return' THEN (payload->>'amount')::numeric WHEN 'return_reversal' THEN -(payload->>'amount')::numeric ELSE 0 END),0) FROM treasury.collector_entries WHERE credit_id=credit.id)
 AND (credit.payload->>'outstanding_amount')::numeric=(SELECT coalesce(sum(CASE payload->>'kind' WHEN 'recognition' THEN (payload->>'amount')::numeric WHEN 'return_reversal' THEN (payload->>'amount')::numeric ELSE -(payload->>'amount')::numeric END),0) FROM treasury.collector_entries WHERE credit_id=credit.id)
 AND (credit.payload->>'reserved_amount')::numeric=(SELECT coalesce(sum((payload->>'amount')::numeric),0) FROM treasury.collector_actions WHERE credit_id=credit.id AND payload->>'status' IN('reserved','debited_confirmation_pending'))
 AND NOT EXISTS(SELECT 1 FROM treasury.collector_entries WHERE credit_id=credit.id AND payload->>'kind' NOT IN('recognition','return','return_reversal','application'))
 AND NOT EXISTS(SELECT 1 FROM treasury.collector_entries entry WHERE entry.credit_id=credit.id AND entry.payload->>'kind'='application' AND NOT treasury.collector_application_exact(entry.id)));
$$;

-- Conservation survives later frozen-source recovery; current posting proof still fails closed.
CREATE FUNCTION treasury.collector_application_capacity_exact(p_credit UUID) RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT EXISTS(SELECT 1 FROM treasury.collector_credits credit JOIN treasury.collector_cases excess ON excess.id=credit.case_id
 WHERE credit.id=p_credit AND credit.opening_anchor_id IS NULL AND excess.settlement_id IS NOT NULL

 AND (SELECT count(*) FROM treasury.collector_entries WHERE credit_id=credit.id AND payload->>'kind'='recognition')=1
 AND (credit.payload->>'recognized_amount')::numeric=(SELECT sum((payload->>'amount')::numeric) FROM treasury.collector_entries WHERE credit_id=credit.id AND payload->>'kind'='recognition')
 AND (credit.payload->>'applied_amount')::numeric=(SELECT coalesce(sum((payload->>'amount')::numeric),0) FROM treasury.collector_entries WHERE credit_id=credit.id AND payload->>'kind'='application')
 AND (credit.payload->>'returned_amount')::numeric=(SELECT coalesce(sum(CASE payload->>'kind' WHEN 'return' THEN (payload->>'amount')::numeric WHEN 'return_reversal' THEN -(payload->>'amount')::numeric ELSE 0 END),0) FROM treasury.collector_entries WHERE credit_id=credit.id)
 AND (credit.payload->>'outstanding_amount')::numeric=(SELECT coalesce(sum(CASE payload->>'kind' WHEN 'recognition' THEN (payload->>'amount')::numeric WHEN 'return_reversal' THEN (payload->>'amount')::numeric ELSE -(payload->>'amount')::numeric END),0) FROM treasury.collector_entries WHERE credit_id=credit.id)
 AND (credit.payload->>'reserved_amount')::numeric=(SELECT coalesce(sum((payload->>'amount')::numeric),0) FROM treasury.collector_actions WHERE credit_id=credit.id AND payload->>'status' IN('reserved','debited_confirmation_pending'))
 AND NOT EXISTS(SELECT 1 FROM treasury.collector_entries WHERE credit_id=credit.id AND payload->>'kind' NOT IN('recognition','return','return_reversal','application'))
 AND NOT EXISTS(SELECT 1 FROM treasury.collector_entries entry WHERE entry.credit_id=credit.id AND entry.payload->>'kind'='application' AND NOT EXISTS(SELECT 1 FROM treasury.collector_credit_applications app WHERE app.id=entry.id AND app.credit_id=entry.credit_id AND app.amount=(entry.payload->>'amount')::numeric AND app.action_id=(entry.payload->>'action_id')::uuid AND app.settlement_id=(entry.payload->>'settlement_id')::uuid)));
$$;

CREATE FUNCTION treasury.guard_collector_credit_application_fact() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN RAISE EXCEPTION 'Accepted Collector credit applications are immutable'; END $$;
CREATE TRIGGER collector_credit_application_immutable BEFORE UPDATE OR DELETE ON treasury.collector_credit_applications
 FOR EACH ROW EXECUTE FUNCTION treasury.guard_collector_credit_application_fact();
CREATE TRIGGER collector_credit_application_no_truncate BEFORE TRUNCATE ON treasury.collector_credit_applications
 FOR EACH STATEMENT EXECUTE FUNCTION treasury.reject_collector_truncate();

CREATE FUNCTION treasury.assert_collector_credit_application() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE application_id UUID; selected_credit UUID;
BEGIN
 IF TG_TABLE_NAME='collector_credit_applications' THEN application_id:=NEW.id; selected_credit:=NEW.credit_id;
 ELSIF TG_TABLE_NAME='collector_entries' AND NEW.payload->>'kind'='application' THEN application_id:=NEW.id; selected_credit:=NEW.credit_id;
 ELSIF TG_TABLE_NAME='collector_settlements' AND (NEW.payload->>'authorized_credit_amount')::numeric>0 THEN
  SELECT id,credit_id INTO application_id,selected_credit FROM treasury.collector_credit_applications WHERE settlement_id=NEW.id;
  IF application_id IS NULL THEN RAISE EXCEPTION 'Accepted credit requires one exact immutable application'; END IF;
 ELSIF TG_TABLE_NAME='collector_credits' THEN
  IF (NEW.payload->>'applied_amount')::numeric=0 AND NOT EXISTS(SELECT 1 FROM treasury.collector_actions WHERE credit_id=NEW.id AND payload->>'kind'='application') THEN RETURN NULL; END IF;
  selected_credit:=NEW.id;
 ELSE RETURN NULL; END IF;
 IF application_id IS NOT NULL AND NOT treasury.collector_application_exact(application_id) THEN RAISE EXCEPTION 'Collector credit consumption does not match its approved accepted custody'; END IF;
 IF selected_credit IS NOT NULL AND NOT (CASE WHEN TG_TABLE_NAME='collector_credits' THEN treasury.collector_application_capacity_exact(selected_credit) ELSE treasury.collector_application_credit_valid(selected_credit) END) THEN RAISE EXCEPTION 'Collector credit capacity does not match immutable consumption'; END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER collector_application_exact_check AFTER INSERT ON treasury.collector_credit_applications
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION treasury.assert_collector_credit_application();
CREATE CONSTRAINT TRIGGER collector_application_entry_check AFTER INSERT ON treasury.collector_entries
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION treasury.assert_collector_credit_application();
CREATE CONSTRAINT TRIGGER collector_application_settlement_check AFTER INSERT ON treasury.collector_settlements
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION treasury.assert_collector_credit_application();
CREATE CONSTRAINT TRIGGER collector_application_capacity_check AFTER INSERT OR UPDATE ON treasury.collector_credits
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION treasury.assert_collector_credit_application();

CREATE FUNCTION treasury.collector_credit_application_ready() RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$ SELECT true $$;

REVOKE ALL ON FUNCTION treasury.collector_application_exact(UUID),treasury.collector_application_credit_valid(UUID),treasury.collector_application_capacity_exact(UUID),
 treasury.guard_collector_credit_application_fact(),treasury.assert_collector_credit_application(),treasury.collector_credit_application_ready() FROM PUBLIC;
DO $$ DECLARE role_name TEXT; BEGIN
 FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
   EXECUTE format('REVOKE ALL ON treasury.collector_credit_applications FROM %I',role_name);
   EXECUTE format('REVOKE ALL ON FUNCTION treasury.collector_application_exact(UUID),treasury.collector_application_credit_valid(UUID),treasury.collector_application_capacity_exact(UUID),treasury.guard_collector_credit_application_fact(),treasury.assert_collector_credit_application(),treasury.collector_credit_application_ready() FROM %I',role_name);
  END IF;
 END LOOP;
END $$;

-- Accounting admission for retained applications. Existing sources keep their
-- original snapshots; later legitimate consumption is validated independently.
ALTER TABLE accounting.collector_liability_preparations DROP CONSTRAINT collector_liability_preparations_source_kind_check;
ALTER TABLE accounting.collector_liability_preparations ADD CONSTRAINT collector_liability_preparations_source_kind_check
 CHECK(source_kind IN ('settlement','recognition','return_debit','return_confirmation','return_reversal','credit_application'));
CREATE OR REPLACE FUNCTION accounting.collector_liability_accounts(p_kind TEXT,p_source UUID)
RETURNS UUID[] LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE result UUID[];
BEGIN
 IF p_kind='settlement' THEN
  SELECT ARRAY[s.account_id]||coalesce(ARRAY[app.origin_account_id],ARRAY[]::uuid[]) INTO result
  FROM treasury.collector_settlements s LEFT JOIN treasury.collector_credit_applications app ON app.settlement_id=s.id WHERE s.id=p_source;
 ELSIF p_kind='return_debit' THEN
  SELECT ARRAY[account_id,(payload->>'origin_account_id')::uuid] INTO result FROM treasury.collector_actions WHERE id=p_source;
 ELSIF p_kind IN ('recognition','return_confirmation','return_reversal','credit_application') THEN
  SELECT ARRAY[entry.account_id,credit.account_id] INTO result
  FROM treasury.collector_entries entry JOIN treasury.collector_credits credit ON credit.id=entry.credit_id WHERE entry.id=p_source;
 ELSE RAISE EXCEPTION 'Unsupported Collector accounting source family.' USING ERRCODE='22023'; END IF;
 IF result IS NULL THEN RAISE EXCEPTION 'Private Collector accounting source is unavailable.' USING ERRCODE='42501'; END IF;
 RETURN ARRAY(SELECT DISTINCT item FROM unnest(result) item WHERE item IS NOT NULL ORDER BY item);
END $$;

CREATE FUNCTION accounting.collector_application_collection_proof(p_id UUID) RETURNS VOID
LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
DECLARE app treasury.collector_credit_applications%ROWTYPE; counted treasury.collector_counts%ROWTYPE;
 remittance lending.collection_remittances%ROWTYPE; gross NUMERIC; collector UUID; day DATE;
 item RECORD; current_source RECORD; proof BOOLEAN;
BEGIN
 SELECT * INTO app FROM treasury.collector_credit_applications WHERE id=p_id;
 IF app.id IS NULL OR NOT treasury.collector_application_exact(app.id) THEN
  RAISE EXCEPTION 'Exact immutable accepted Collector application required.' USING ERRCODE='55000'; END IF;
 SELECT * INTO counted FROM treasury.collector_counts WHERE id=app.count_id;
 SELECT * INTO remittance FROM lending.collection_remittances WHERE id=app.remittance_id;
 gross:=remittance.total_amount; collector:=app.collector_user_id;
 day:=((counted.payload->>'counted_at')::timestamptz AT TIME ZONE 'Asia/Manila')::date;
 IF EXISTS(SELECT 1 FROM accounting.remittance_transfer_journal_preparations WHERE remittance_id=app.remittance_id)
  OR EXISTS(SELECT 1 FROM accounting.journal_entries WHERE source_type='remittance_transfer' AND source_reference=app.remittance_id::text) THEN
  RAISE EXCEPTION 'Competing Collector remittance accounting is not supported.' USING ERRCODE='55000'; END IF;
  IF gross<>(SELECT coalesce(sum(i.amount),0) FROM lending.collection_remittance_items i WHERE i.remittance_id=remittance.id)
   OR jsonb_typeof(counted.payload#>'{source_snapshot,items}') IS DISTINCT FROM 'array'
   OR jsonb_array_length(counted.payload#>'{source_snapshot,items}')<>(SELECT count(*) FROM lending.collection_remittance_items WHERE remittance_id=remittance.id) THEN
   RAISE EXCEPTION 'Collector count source constituents changed.' USING ERRCODE='55000';
  END IF;
  FOR item IN SELECT i.*,to_jsonb(t) AS current_collection FROM lending.collection_remittance_items i
   JOIN lending.collection_transactions t ON t.id=i.transaction_id WHERE i.remittance_id=remittance.id ORDER BY i.transaction_id LOOP
   SELECT * INTO current_source FROM lending.collection_transactions WHERE id=item.transaction_id;
   IF current_source.is_voided OR NOT current_source.is_locked OR current_source.funding_source<>'collector_cash'
    OR current_source.remittance_id IS DISTINCT FROM remittance.id OR current_source.amount<>item.amount
    OR current_source.amount<>current_source.applied_amount OR current_source.unallocated_amount<>0
    OR current_source.collection_date<>item.collection_date OR current_source.collection_date>day
    OR current_source.collector_user_id<>collector
    OR NOT ((current_source.entry_type='pass' AND current_source.amount=0)
      OR (current_source.entry_type IN ('payment','advance') AND current_source.amount>0)) OR NOT EXISTS(
      SELECT 1 FROM jsonb_array_elements(counted.payload#>'{source_snapshot,items}') retained
      WHERE retained->>'transaction_id'=item.transaction_id::text AND (retained->>'amount')::numeric=item.amount
       AND (retained->>'collection_date')::date=item.collection_date AND (retained->>'edit_version')::integer=current_source.edit_version) THEN
    RAISE EXCEPTION 'Collector count source collection changed or is unsupported.' USING ERRCODE='55000';
   END IF;
   IF current_source.entry_type='pass' THEN
    IF EXISTS(SELECT 1 FROM accounting.journal_entries WHERE source_type='collection' AND source_reference=item.transaction_id::text) THEN
     RAISE EXCEPTION 'A zero-effect Collector PASS must not have a collection cash journal.' USING ERRCODE='55000'; END IF;
    CONTINUE;
   END IF;
   proof:=false;
   IF EXISTS(SELECT 1 FROM accounting.regular_journal_draft_preparations WHERE transaction_id=item.transaction_id) THEN
    proof:=accounting.legacy_regular_collection_posted_exact(item.transaction_id);
   ELSIF EXISTS(SELECT 1 FROM accounting.seven_by_seven_journal_postings WHERE transaction_id=item.transaction_id) THEN
    SELECT EXISTS(SELECT 1 FROM accounting.seven_by_seven_journal_posting_status p WHERE p.transaction_id=item.transaction_id
      AND p.posted_audit_exact AND p.source_cash_amount=item.amount AND p.posting_date=item.collection_date) INTO proof;
   END IF;
   IF NOT proof THEN RAISE EXCEPTION 'Exact posted Collector custody collection proof is required before count accounting.' USING ERRCODE='55000'; END IF;
  END LOOP;

END $$;

CREATE OR REPLACE FUNCTION accounting.collector_liability_origin(p_kind TEXT,p_source UUID,p_mapping_ids JSONB DEFAULT NULL)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
DECLARE
 app treasury.collector_credit_applications%ROWTYPE; credit_used NUMERIC:=0; physical_principal NUMERIC:=0;
 s treasury.collector_settlements%ROWTYPE; counted treasury.collector_counts%ROWTYPE;
 excess treasury.collector_cases%ROWTYPE; credit treasury.collector_credits%ROWTYPE;
 entry treasury.collector_entries%ROWTYPE; action treasury.collector_actions%ROWTYPE;
 acknowledgment treasury.collector_acknowledgments%ROWTYPE; resolution treasury.collector_resolutions%ROWTYPE;
 event treasury.events%ROWTYPE; remittance lending.collection_remittances%ROWTYPE;
 mapping accounting.treasury_cash_mappings%ROWTYPE; wallet treasury.accounts%ROWTYPE;
 period accounting.fiscal_periods%ROWTYPE; book accounting.book_identity%ROWTYPE;
 selected_wallet UUID; account_ids UUID[]; collector UUID; cash UUID; custody UUID; unidentified UUID; payable UUID; transit UUID; fees UUID;
 day DATE; amount NUMERIC; fee NUMERIC:=0; gross NUMERIC:=0; excess_amount NUMERIC:=0;
 source_facts JSONB:='{}'; prerequisites JSONB:='[]'; evidence JSONB:='[]'; mappings JSONB:='{}';
 lines JSONB; line_values JSONB:='[]'; dependency JSONB; item RECORD; current_source RECORD; proof BOOLEAN; count_entries BIGINT;
BEGIN
 account_ids:=accounting.collector_liability_accounts(p_kind,p_source);
 SELECT * INTO book FROM accounting.book_identity WHERE singleton;
 IF book.id IS NULL THEN RAISE EXCEPTION 'Accounting book identity is required.' USING ERRCODE='55000'; END IF;
 IF p_kind='settlement' THEN
  SELECT * INTO s FROM treasury.collector_settlements WHERE id=p_source;
  SELECT * INTO counted FROM treasury.collector_counts WHERE id=s.count_id;
  SELECT * INTO remittance FROM lending.collection_remittances WHERE id=s.remittance_id;
  SELECT * INTO excess FROM treasury.collector_cases WHERE settlement_id=s.id;
  selected_wallet:=s.account_id; collector:=s.collector_user_id; amount:=(s.payload->>'physical_amount')::numeric;
  gross:=(s.payload->>'gross_obligation')::numeric; credit_used:=(s.payload->>'authorized_credit_amount')::numeric;
  physical_principal:=gross-credit_used; excess_amount:=amount-physical_principal;
  IF credit_used>0 THEN
   SELECT * INTO app FROM treasury.collector_credit_applications WHERE settlement_id=s.id;
   IF app.id IS NULL OR NOT treasury.collector_application_exact(app.id) THEN RAISE EXCEPTION 'Exact immutable accepted credit application required.' USING ERRCODE='55000'; END IF;
  END IF;
  SELECT * INTO event FROM treasury.events WHERE id=s.event_id;
  day:=(event.effective_at AT TIME ZONE 'Asia/Manila')::date;
  IF event.id IS NULL OR remittance.status<>'received' OR counted.payload->>'disposition' IS DISTINCT FROM 'counted_ready'
   OR NOT s.payload ?& ARRAY['physical_amount','gross_obligation','authorized_credit_amount']
   OR NOT counted.payload ?& ARRAY['refund_due_total','physical_cash_required','gross_obligation','counted_amount','difference','counted_at']
   OR amount<=0 OR gross<=0 OR excess_amount<0 OR remittance.total_amount<>gross
   OR credit_used<0 OR credit_used>gross OR counted.payload->>'refund_due_total'<>'0.00'
   OR (counted.payload->>'physical_cash_required')::numeric<>physical_principal OR (counted.payload->>'gross_obligation')::numeric<>gross
   OR (counted.payload->>'counted_amount')::numeric<>amount OR (counted.payload->>'difference')::numeric<>excess_amount
   OR (counted.payload->>'counted_at')::timestamptz<>event.effective_at
   OR event.direction<>'credit' OR event.classification<>'collector_counted_receipt' OR event.fee<>0 OR event.amount<>amount
   OR counted.account_id<>s.account_id OR counted.collector_user_id<>collector OR counted.evidence_id<>event.evidence_id
   OR EXISTS(SELECT 1 FROM lending.collection_remittance_refund_due_release_items WHERE remittance_id=remittance.id)
   OR EXISTS(SELECT 1 FROM treasury.collector_exceptions WHERE payload->>'remittance_id'=remittance.id::text)
   OR EXISTS(SELECT 1 FROM accounting.remittance_transfer_journal_preparations WHERE remittance_id=remittance.id)
   OR EXISTS(SELECT 1 FROM accounting.journal_entries WHERE source_type='remittance_transfer' AND source_reference=remittance.id::text)
   OR (excess_amount>0 AND (excess.id IS NULL OR (excess.payload->>'received_excess_amount')::numeric<>excess_amount))
   OR (excess_amount=0 AND excess.id IS NOT NULL) THEN
   RAISE EXCEPTION 'Collector count requires exact original cash, unnetted collections and no competing remittance accounting.' USING ERRCODE='55000';
  END IF;
  IF gross<>(SELECT coalesce(sum(i.amount),0) FROM lending.collection_remittance_items i WHERE i.remittance_id=remittance.id)
   OR jsonb_typeof(counted.payload#>'{source_snapshot,items}') IS DISTINCT FROM 'array'
   OR jsonb_array_length(counted.payload#>'{source_snapshot,items}')<>(SELECT count(*) FROM lending.collection_remittance_items WHERE remittance_id=remittance.id) THEN
   RAISE EXCEPTION 'Collector count source constituents changed.' USING ERRCODE='55000';
  END IF;
  FOR item IN SELECT i.*,to_jsonb(t) AS current_collection FROM lending.collection_remittance_items i
   JOIN lending.collection_transactions t ON t.id=i.transaction_id WHERE i.remittance_id=remittance.id ORDER BY i.transaction_id LOOP
   SELECT * INTO current_source FROM lending.collection_transactions WHERE id=item.transaction_id;
   IF current_source.is_voided OR NOT current_source.is_locked OR current_source.funding_source<>'collector_cash'
    OR current_source.remittance_id IS DISTINCT FROM remittance.id OR current_source.amount<>item.amount
    OR current_source.amount<>current_source.applied_amount OR current_source.unallocated_amount<>0
    OR current_source.collection_date<>item.collection_date OR current_source.collection_date>day
    OR current_source.collector_user_id<>collector
    OR NOT ((current_source.entry_type='pass' AND current_source.amount=0)
      OR (current_source.entry_type IN ('payment','advance') AND current_source.amount>0)) OR NOT EXISTS(
      SELECT 1 FROM jsonb_array_elements(counted.payload#>'{source_snapshot,items}') retained
      WHERE retained->>'transaction_id'=item.transaction_id::text AND (retained->>'amount')::numeric=item.amount
       AND (retained->>'collection_date')::date=item.collection_date AND (retained->>'edit_version')::integer=current_source.edit_version) THEN
    RAISE EXCEPTION 'Collector count source collection changed or is unsupported.' USING ERRCODE='55000';
   END IF;
   IF current_source.entry_type='pass' THEN
    IF EXISTS(SELECT 1 FROM accounting.journal_entries WHERE source_type='collection' AND source_reference=item.transaction_id::text) THEN
     RAISE EXCEPTION 'A zero-effect Collector PASS must not have a collection cash journal.' USING ERRCODE='55000'; END IF;
    CONTINUE;
   END IF;
   proof:=false;
   IF EXISTS(SELECT 1 FROM accounting.regular_journal_draft_preparations WHERE transaction_id=item.transaction_id) THEN
    proof:=accounting.legacy_regular_collection_posted_exact(item.transaction_id);
   ELSIF EXISTS(SELECT 1 FROM accounting.seven_by_seven_journal_postings WHERE transaction_id=item.transaction_id) THEN
    SELECT EXISTS(SELECT 1 FROM accounting.seven_by_seven_journal_posting_status p WHERE p.transaction_id=item.transaction_id
      AND p.posted_audit_exact AND p.source_cash_amount=item.amount AND p.posting_date=item.collection_date) INTO proof;
   END IF;
   IF NOT proof THEN RAISE EXCEPTION 'Exact posted Collector custody collection proof is required before count accounting.' USING ERRCODE='55000'; END IF;
  END LOOP;
  IF (SELECT count(*) FROM treasury.source_links WHERE event_id=event.id)<>(CASE WHEN physical_principal>0 THEN 1 ELSE 0 END)+(CASE WHEN excess_amount>0 THEN 1 ELSE 0 END)
   OR (physical_principal>0 AND NOT EXISTS(SELECT 1 FROM treasury.source_links WHERE event_id=event.id AND source_kind='collector_remittance_physical'
    AND source_id=remittance.id AND linked_amount=physical_principal AND ledger_context_id=s.ledger_context_id))
   OR (excess_amount>0 AND NOT EXISTS(SELECT 1 FROM treasury.source_links WHERE event_id=event.id AND source_kind='collector_excess_pending'
    AND source_id=excess.id AND linked_amount=excess_amount AND ledger_context_id=s.ledger_context_id)) THEN
   RAISE EXCEPTION 'Collector accepted cash source links do not match.' USING ERRCODE='55000';
  END IF;
  source_facts:=jsonb_build_object('settlement',to_jsonb(s),'count',to_jsonb(counted),
    'remittance_id',remittance.id,'case_id',excess.id,'gross',gross::text,'excess',excess_amount::text,
    'constituents',(SELECT jsonb_agg(jsonb_build_object('item',to_jsonb(i),'transaction',to_jsonb(t)) ORDER BY i.transaction_id)
      FROM lending.collection_remittance_items i JOIN lending.collection_transactions t ON t.id=i.transaction_id WHERE i.remittance_id=remittance.id));
  custody:=accounting.collector_gl_account('1020','cash_collector_custody','asset','debit');
  unidentified:=accounting.collector_gl_account('2210','unidentified_collector_excess','liability','credit');
  IF physical_principal>0 THEN line_values:=jsonb_build_array(jsonb_build_object('account_id',custody,'debit','0.00','credit',physical_principal::numeric(18,2)::text)); END IF;
  IF credit_used>0 THEN source_facts:=source_facts||jsonb_build_object('physical_principal',physical_principal::numeric(18,2)::text,'application',to_jsonb(app)); END IF;
  IF excess_amount>0 THEN line_values:=line_values||jsonb_build_array(jsonb_build_object('account_id',unidentified,'debit','0.00','credit',excess_amount::text)); END IF;
 ELSE
  IF p_kind='return_debit' THEN
   SELECT * INTO action FROM treasury.collector_actions WHERE id=p_source;
   SELECT * INTO credit FROM treasury.collector_credits WHERE id=action.credit_id;
  ELSE
   SELECT * INTO entry FROM treasury.collector_entries WHERE id=p_source;
   SELECT * INTO credit FROM treasury.collector_credits WHERE id=entry.credit_id;
   IF entry.payload->>'kind' IS DISTINCT FROM (CASE p_kind WHEN 'recognition' THEN 'recognition' WHEN 'return_confirmation' THEN 'return' WHEN 'credit_application' THEN 'application' ELSE 'return_reversal' END) THEN
    RAISE EXCEPTION 'Collector entry does not match the reviewed accounting family.' USING ERRCODE='55000';
   END IF;
   IF p_kind<>'recognition' THEN SELECT * INTO action FROM treasury.collector_actions WHERE id=(entry.payload->>'action_id')::uuid; END IF;
  END IF;
  SELECT * INTO excess FROM treasury.collector_cases WHERE id=credit.case_id;
  IF credit.id IS NULL OR credit.opening_anchor_id IS NOT NULL OR excess.settlement_id IS NULL
   OR (credit.payload->>'frozen')::boolean OR (credit.payload->>'reclassified_amount')::numeric<>0 OR ((credit.payload->>'applied_amount')::numeric<>0 AND NOT treasury.collector_application_credit_valid(credit.id)) THEN
   RAISE EXCEPTION 'Collector credit requires original accepted excess; historical opening or source correction is unsupported.' USING ERRCODE='55000';
  END IF;
  IF (excess.payload->>'unidentified_amount')::numeric IS DISTINCT FROM
    (excess.payload->>'received_excess_amount')::numeric-(SELECT coalesce(sum((payload->>'amount')::numeric),0) FROM treasury.collector_resolutions WHERE case_id=excess.id)
   OR (credit.payload->>'outstanding_amount')::numeric IS DISTINCT FROM
    (SELECT coalesce(sum(CASE payload->>'kind' WHEN 'recognition' THEN (payload->>'amount')::numeric WHEN 'return' THEN -(payload->>'amount')::numeric WHEN 'return_reversal' THEN (payload->>'amount')::numeric WHEN 'application' THEN -(payload->>'amount')::numeric ELSE 0 END),0) FROM treasury.collector_entries WHERE credit_id=credit.id) THEN
   RAISE EXCEPTION 'Collector liability capacity does not reconcile to immutable entries.' USING ERRCODE='55000';
  END IF;
  collector:=credit.collector_user_id; selected_wallet:=coalesce(action.account_id,credit.account_id);
  payable:=accounting.collector_gl_account('2220','collector_credit_payable','liability','credit');
  source_facts:=jsonb_build_object('credit_id',credit.id,'case_id',credit.case_id,'recognized_amount',credit.payload->>'recognized_amount');
  IF p_kind='recognition' THEN
   amount:=(entry.payload->>'amount')::numeric; day:=(entry.created_at AT TIME ZONE 'Asia/Manila')::date;
   SELECT * INTO resolution FROM treasury.collector_resolutions WHERE case_id=excess.id AND payload->>'credit_id'=credit.id::text;
   IF resolution.id IS NULL OR resolution.payload->>'kind'<>'collector_credit' OR (resolution.payload->>'amount')::numeric<>amount
    OR (credit.payload->>'recognized_amount')::numeric<>amount OR resolution.evidence_id IS DISTINCT FROM (entry.payload->>'evidence_id')::uuid
    OR (SELECT count(*) FROM treasury.collector_entries WHERE credit_id=credit.id AND payload->>'kind'='recognition')<>1
    OR (SELECT count(*) FROM treasury.collector_resolutions WHERE payload->>'credit_id'=credit.id::text)<>1 THEN
    RAISE EXCEPTION 'Collector recognition requires one exact immutable resolution.' USING ERRCODE='55000';
   END IF;
   dependency:=accounting.collector_liability_prerequisite('settlement',excess.settlement_id,day);
   unidentified:=accounting.collector_gl_account('2210','unidentified_collector_excess','liability','credit');
   line_values:=jsonb_build_array(jsonb_build_object('account_id',unidentified,'debit',amount::text,'credit','0.00'),jsonb_build_object('account_id',payable,'debit','0.00','credit',amount::text));
   source_facts:=source_facts||jsonb_build_object('entry',to_jsonb(entry),'resolution',to_jsonb(resolution));
   evidence:=evidence||jsonb_build_array((SELECT to_jsonb(e) FROM treasury.evidence e WHERE id=resolution.evidence_id AND account_id=credit.account_id AND purpose='recipient'));
  ELSIF p_kind='credit_application' THEN
   SELECT * INTO app FROM treasury.collector_credit_applications WHERE id=entry.id;
   IF app.id IS NULL OR NOT treasury.collector_application_credit_valid(credit.id) THEN
    RAISE EXCEPTION 'Exact immutable consumed Collector credit is required.' USING ERRCODE='55000'; END IF;
   SELECT * INTO s FROM treasury.collector_settlements WHERE id=app.settlement_id;
   SELECT * INTO counted FROM treasury.collector_counts WHERE id=app.count_id;
   SELECT * INTO remittance FROM lending.collection_remittances WHERE id=app.remittance_id;
   amount:=app.amount; day:=(app.accepted_at AT TIME ZONE 'Asia/Manila')::date;
   PERFORM accounting.collector_application_collection_proof(app.id);
   SELECT id INTO item FROM treasury.collector_entries WHERE credit_id=credit.id AND payload->>'kind'='recognition';
   dependency:=accounting.collector_liability_prerequisite('recognition',item.id,day);
   custody:=accounting.collector_gl_account('1020','cash_collector_custody','asset','debit');
   line_values:=jsonb_build_array(jsonb_build_object('account_id',payable,'debit',amount::numeric(18,2)::text,'credit','0.00'),
    jsonb_build_object('account_id',custody,'debit','0.00','credit',amount::numeric(18,2)::text));
   source_facts:=source_facts||jsonb_build_object('entry',to_jsonb(entry),'application',to_jsonb(app),
    'settlement',to_jsonb(s),'count',to_jsonb(counted),'remittance_id',app.remittance_id,
    'constituents',(SELECT jsonb_agg(jsonb_build_object('item',to_jsonb(i),'transaction',to_jsonb(t)) ORDER BY i.transaction_id)
      FROM lending.collection_remittance_items i JOIN lending.collection_transactions t ON t.id=i.transaction_id WHERE i.remittance_id=app.remittance_id));
   evidence:=evidence||jsonb_build_array(
     (SELECT to_jsonb(e) FROM treasury.evidence e WHERE id=counted.evidence_id AND account_id=app.account_id AND purpose='recipient'),
     (SELECT to_jsonb(e) FROM treasury.evidence e WHERE id=action.evidence_id AND account_id=app.account_id AND purpose='recipient'));
  ELSE
   IF action.id IS NULL OR action.credit_id<>credit.id OR action.payload->>'kind'<>'return'
    OR action.payload->>'origin_account_id'<>credit.account_id::text OR action.collector_user_id<>collector
    OR action.ledger_context_id<>credit.ledger_context_id OR action.event_id IS NULL
    OR action.payload->>'status' NOT IN ('debited_confirmation_pending','paid','partly_reversed','reversed') THEN
    RAISE EXCEPTION 'An exact approved actual Collector return debit is required.' USING ERRCODE='55000';
   END IF;
   SELECT * INTO event FROM treasury.events WHERE id=CASE WHEN p_kind='return_reversal' THEN (entry.payload->>'incoming_event_id')::uuid ELSE action.event_id END;
   amount:=CASE WHEN p_kind='return_reversal' THEN (entry.payload->>'amount')::numeric ELSE (action.payload->>'amount')::numeric END;
   day:=(event.effective_at AT TIME ZONE 'Asia/Manila')::date; fee:=event.fee;
   transit:=accounting.collector_gl_account('1060','collector_return_in_transit','asset','debit');
   source_facts:=source_facts||jsonb_build_object('action_id',action.id,'approved_action',action.payload-ARRAY['status','event_id','event_version','acknowledgment_id','reversed_amount'],
     'event_id',action.event_id,'event_version',action.payload->>'event_version');
   evidence:=evidence||jsonb_build_array((SELECT to_jsonb(e) FROM treasury.evidence e WHERE id=action.evidence_id AND account_id=action.account_id AND purpose='recipient'));
   IF p_kind='return_debit' THEN
    IF event.direction<>'debit' OR event.amount<>amount OR event.classification<>'verified_unclassified'
     OR NOT EXISTS(SELECT 1 FROM treasury.source_links WHERE event_id=event.id AND source_id=action.id AND source_kind='collector_surplus_return'
      AND linked_amount=amount AND ledger_context_id=action.ledger_context_id)
     OR (SELECT count(*) FROM treasury.source_links WHERE event_id=event.id)<>1 THEN
     RAISE EXCEPTION 'Exact actual Collector return principal, fee and source link are required.' USING ERRCODE='55000';
    END IF;
    SELECT id INTO item FROM treasury.collector_entries WHERE credit_id=credit.id AND payload->>'kind'='recognition';
    dependency:=accounting.collector_liability_prerequisite('recognition',item.id,day);
    line_values:=jsonb_build_array(jsonb_build_object('account_id',transit,'debit',amount::text,'credit','0.00'));
    IF fee>0 THEN fees:=accounting.collector_gl_account('5240','bank_charges_expense','expense','debit');
     line_values:=line_values||jsonb_build_array(jsonb_build_object('account_id',fees,'debit',fee::text,'credit','0.00')); END IF;
   ELSIF p_kind='return_confirmation' THEN
    SELECT * INTO acknowledgment FROM treasury.collector_acknowledgments WHERE id=(action.payload->>'acknowledgment_id')::uuid;
    IF action.payload->>'status' NOT IN ('paid','partly_reversed','reversed') OR acknowledgment.id IS NULL
     OR acknowledgment.action_id<>action.id OR acknowledgment.collector_user_id<>collector
     OR acknowledgment.payload->>'confirmation'<>'received' OR acknowledgment.payload->>'event_id'<>event.id::text
     OR (acknowledgment.payload->>'reviewed_amount')::numeric<>amount OR (entry.payload->>'amount')::numeric<>amount
     OR (acknowledgment.payload->>'acknowledged_at')::timestamptz<event.effective_at
     OR (acknowledgment.payload->>'acknowledged_at')::timestamptz>entry.created_at
     OR (SELECT count(*) FROM treasury.collector_entries WHERE payload->>'action_id'=action.id::text AND payload->>'kind'='return')<>1 THEN
     RAISE EXCEPTION 'An exact immutable received Collector acknowledgment is required.' USING ERRCODE='55000';
    END IF;
    day:=((acknowledgment.payload->>'acknowledged_at')::timestamptz AT TIME ZONE 'Asia/Manila')::date; fee:=0;
    dependency:=accounting.collector_liability_prerequisite('return_debit',action.id,day);
    line_values:=jsonb_build_array(jsonb_build_object('account_id',payable,'debit',amount::text,'credit','0.00'),jsonb_build_object('account_id',transit,'debit','0.00','credit',amount::text));
    source_facts:=source_facts||jsonb_build_object('entry',to_jsonb(entry),'acknowledgment',to_jsonb(acknowledgment));
   ELSE
    IF event.direction<>'credit' OR event.amount<>amount OR fee<>0 OR event.classification<>'collector_return_reversal'
     OR NOT EXISTS(SELECT 1 FROM treasury.source_links WHERE event_id=event.id AND source_id=action.id AND source_kind='collector_surplus_return_reversal'
       AND linked_amount=amount AND ledger_context_id=action.ledger_context_id)
     OR (SELECT count(*) FROM treasury.source_links WHERE event_id=event.id)<>1
     OR (SELECT coalesce(sum((payload->>'amount')::numeric),0) FROM treasury.collector_entries WHERE payload->>'action_id'=action.id::text AND payload->>'kind'='return_reversal')>(action.payload->>'amount')::numeric THEN
     RAISE EXCEPTION 'Exact actual incoming Collector reversal is required.' USING ERRCODE='55000';
    END IF;
    SELECT id INTO item FROM treasury.collector_entries WHERE payload->>'action_id'=action.id::text AND payload->>'kind'='return';
    dependency:=accounting.collector_liability_prerequisite('return_confirmation',item.id,day);
    line_values:=jsonb_build_array(jsonb_build_object('account_id',payable,'debit','0.00','credit',amount::text));
    source_facts:=source_facts||jsonb_build_object('entry',to_jsonb(entry));
   END IF;
  END IF;
  prerequisites:=prerequisites||jsonb_build_array(dependency-'evidence'); evidence:=evidence||coalesce(dependency->'evidence','[]');
 END IF;
 -- Common event proof. A confirmation retains the same event as evidence but
 -- has no cash-event claim and cannot recognize that cash a second time.
 IF event.id IS NOT NULL THEN
  IF event.version<>1 OR event.account_id<>selected_wallet OR event.amount<>amount OR event.verified_by_user_id IS NULL
   OR event.effective_at>clock_timestamp()
   OR btrim(coalesce(event.recipient_attestation,''))='' OR EXISTS(SELECT 1 FROM treasury.event_revisions WHERE event_id=event.id)
   OR (SELECT count(*) FROM treasury.movement_lines WHERE event_id=event.id)<>(CASE WHEN event.fee>0 THEN 2 ELSE 1 END)
   OR NOT EXISTS(SELECT 1 FROM treasury.movement_lines WHERE event_id=event.id AND component='principal'
     AND signed_amount=CASE event.direction WHEN 'credit' THEN event.amount ELSE -event.amount END
     AND account_id=event.account_id AND ledger_context_id=event.ledger_context_id AND effective_at=event.effective_at AND evidence_id=event.evidence_id)
   OR (event.fee>0 AND NOT EXISTS(SELECT 1 FROM treasury.movement_lines WHERE event_id=event.id AND component='fee' AND signed_amount=-event.fee
     AND account_id=event.account_id AND ledger_context_id=event.ledger_context_id AND effective_at=event.effective_at AND evidence_id=event.evidence_id)) THEN
   RAISE EXCEPTION 'Collector source event or exact cash movement evidence changed.' USING ERRCODE='55000';
  END IF;
  source_facts:=source_facts||jsonb_build_object('event',to_jsonb(event),'source_links',(SELECT jsonb_agg(to_jsonb(l) ORDER BY l.id) FROM treasury.source_links l WHERE event_id=event.id),
    'movement_lines',(SELECT jsonb_agg(to_jsonb(l) ORDER BY l.id) FROM treasury.movement_lines l WHERE event_id=event.id));
  evidence:=evidence||jsonb_build_array((SELECT to_jsonb(e) FROM treasury.evidence e WHERE id=event.evidence_id AND account_id=event.account_id AND purpose='recipient'));
 END IF;
 FOREACH selected_wallet IN ARRAY account_ids LOOP
  SELECT * INTO wallet FROM treasury.accounts WHERE id=selected_wallet;
  SELECT * INTO mapping FROM accounting.treasury_cash_mappings WHERE treasury_account_id=selected_wallet
   AND (p_mapping_ids IS NULL OR id=(p_mapping_ids->>selected_wallet::text)::uuid) ORDER BY version DESC LIMIT 1;
  IF mapping.id IS NULL OR mapping.book_id<>book.id OR mapping.ledger_context_id<>wallet.ledger_context_id
   OR (mapping.wallet_snapshot-'active') IS DISTINCT FROM (accounting.treasury_gl_wallet_snapshot(selected_wallet)-'active')
   OR (mapping.cash_snapshot-ARRAY['name','is_active']) IS DISTINCT FROM (accounting.treasury_gl_account_snapshot(mapping.cash_account_id)-ARRAY['name','is_active']) THEN
   RAISE EXCEPTION 'Current reviewed Collector cash mapping is required.' USING ERRCODE='55000';
  END IF;
  mappings:=mappings||jsonb_build_object(selected_wallet::text,mapping.id);
  IF selected_wallet=(CASE WHEN p_kind='settlement' THEN s.account_id WHEN p_kind='recognition' THEN credit.account_id ELSE action.account_id END) THEN cash:=mapping.cash_account_id; END IF;
 END LOOP;
 selected_wallet:=CASE WHEN p_kind='settlement' THEN s.account_id WHEN p_kind='recognition' THEN credit.account_id ELSE action.account_id END;
 IF p_kind IN ('settlement','return_reversal') THEN line_values:=jsonb_build_array(jsonb_build_object('account_id',cash,'debit',amount::text,'credit','0.00'))||line_values;
 ELSIF p_kind='return_debit' THEN line_values:=line_values||jsonb_build_array(jsonb_build_object('account_id',cash,'debit','0.00','credit',(amount+fee)::text)); END IF;
 SELECT jsonb_agg(value||jsonb_build_object('line_number',ordinality,'account_code',a.code,
   'account_snapshot',accounting.treasury_gl_account_snapshot(a.id)-ARRAY['name','is_active']) ORDER BY ordinality)
 INTO lines FROM jsonb_array_elements(line_values) WITH ORDINALITY JOIN accounting.accounts a ON a.id=(value->>'account_id')::uuid;
 IF lines IS NULL OR jsonb_array_length(lines)<2 OR (SELECT sum((value->>'debit')::numeric-(value->>'credit')::numeric) FROM jsonb_array_elements(lines))<>0 THEN
  RAISE EXCEPTION 'Exact balanced Collector journal coordinates are required.' USING ERRCODE='55000'; END IF;
 SELECT jsonb_agg(value ORDER BY value->>'id') INTO evidence FROM (SELECT DISTINCT value FROM jsonb_array_elements(evidence)) retained;
 IF evidence IS NULL OR EXISTS(SELECT 1 FROM jsonb_array_elements(evidence) e WHERE e='null'::jsonb
  OR NOT e ?& ARRAY['id','sha256','byte_count'] OR e->>'byte_count' IS NULL OR (e->>'byte_count')::bigint<=0
  OR e->>'sha256' IS NULL OR e->>'sha256' !~ '^[0-9a-f]{64}$') THEN
  RAISE EXCEPTION 'Retained private Collector evidence is required.' USING ERRCODE='55000'; END IF;
 SELECT * INTO period FROM accounting.fiscal_periods WHERE day BETWEEN start_date AND end_date;
 IF period.id IS NULL OR day IS NULL OR day>(clock_timestamp() AT TIME ZONE 'Asia/Manila')::date
  OR amount IS NULL OR amount<=0 OR fee IS NULL OR fee<0 THEN
  RAISE EXCEPTION 'Collector evidence requires an actual positive amount and dated fiscal period.' USING ERRCODE='55000'; END IF;
 RETURN jsonb_build_object('book_id',book.id,'source_kind',p_kind,'source_id',p_source,'treasury_account_id',selected_wallet,
  'account_ids',to_jsonb(account_ids),'collector_user_id',collector,'fiscal_period_id',period.id,'posting_date',day,
  'amount',amount::numeric(18,2)::text,'fee',fee::numeric(18,2)::text,'cash_event_id',CASE WHEN p_kind IN ('settlement','return_debit','return_reversal') THEN event.id END,
  'mapping_ids',mappings,'source_facts',source_facts,'prerequisites',prerequisites,'evidence',evidence,'lines',lines);
END $$;

CREATE OR REPLACE FUNCTION accounting.lock_collector_liability_sources()
RETURNS VOID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF current_setting('transaction_isolation')<>'read committed' THEN
  RAISE EXCEPTION 'Collector accounting requires READ COMMITTED.' USING ERRCODE='55000'; END IF;
 LOCK TABLE lending.collection_remittances,lending.collection_remittance_items,lending.collection_transactions,
  lending.collection_remittance_refund_due_release_items,accounting.accounts,accounting.fiscal_periods,
  accounting.regular_journal_draft_preparations,accounting.regular_journal_draft_preparation_entries,
  accounting.regular_journal_posting_sets,accounting.regular_journal_posting_entries,
  accounting.seven_by_seven_journal_postings,accounting.seven_by_seven_journal_posting_lines,
  accounting.remittance_transfer_journal_preparations,accounting.remittance_transfer_journal_postings,
  treasury.collector_credit_applications,treasury.collector_requests,treasury.collector_counts,treasury.collector_settlements,treasury.collector_cases,treasury.collector_credits,
  treasury.collector_entries,treasury.collector_resolutions,treasury.collector_actions,treasury.collector_acknowledgments,
  treasury.collector_exceptions,treasury.evidence,treasury.events,treasury.event_revisions,treasury.movement_lines,treasury.source_links,
  accounting.treasury_cash_mappings
 IN SHARE MODE;
 LOCK TABLE accounting.journal_entries,accounting.journal_lines,
  accounting.collector_liability_preparations,accounting.collector_liability_postings IN SHARE ROW EXCLUSIVE MODE;
END $$;

ALTER FUNCTION accounting.collector_source_exact(TEXT,UUID,DATE) RENAME TO collector_source_before_application_exact;
CREATE FUNCTION accounting.collector_source_exact(p_type TEXT,p_source UUID,p_cutoff DATE)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 WITH application AS (
  SELECT app.*,s.event_id FROM treasury.collector_credit_applications app
  JOIN treasury.collector_settlements s ON s.id=app.settlement_id
  WHERE CASE p_type WHEN 'collector_entry' THEN app.id=p_source
    WHEN 'collector_settlement' THEN app.settlement_id=p_source
    WHEN 'remittance_transfer' THEN app.remittance_id=p_source ELSE false END
 ), proof AS (
  SELECT app.* FROM application app JOIN accounting.collector_liability_posting_status status
   ON status.source_kind='credit_application' AND status.source_id=app.id
  WHERE status.exact_posted AND NOT status.correction_pending AND status.posting_date<=p_cutoff
 )
 SELECT CASE WHEN EXISTS(SELECT 1 FROM application) THEN EXISTS(SELECT 1 FROM proof app
  WHERE p_type='collector_entry' OR app.event_id IS NULL OR
   accounting.collector_source_before_application_exact('collector_settlement',app.settlement_id,p_cutoff))
 ELSE accounting.collector_source_before_application_exact(p_type,p_source,p_cutoff) END;
$$;

ALTER FUNCTION accounting.collector_control_movements() RENAME TO collector_control_before_application_movements;
CREATE FUNCTION accounting.collector_control_movements()
RETURNS TABLE(account_code TEXT,effective_date DATE,signed_amount NUMERIC,source_type TEXT,source_id UUID,account_id UUID)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT * FROM accounting.collector_control_before_application_movements()
 UNION ALL SELECT '2220'::text,(coalesce(app.accepted_at,entry.created_at) AT TIME ZONE 'Asia/Manila')::date,
  (entry.payload->>'amount')::numeric,'collector_entry'::text,entry.id,entry.account_id
 FROM treasury.collector_entries entry LEFT JOIN treasury.collector_credit_applications app ON app.id=entry.id
 WHERE entry.payload->>'kind'='application';
$$;

ALTER FUNCTION accounting.period_review_additional_evidence(UUID) RENAME TO period_review_before_credit_application_evidence;
CREATE FUNCTION accounting.period_review_additional_evidence(p_period UUID)
RETURNS JSONB LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
 SELECT accounting.period_review_before_credit_application_evidence(p_period)||
  CASE WHEN count(app.id)=0 THEN '{}'::jsonb ELSE jsonb_build_object('collector_credit_applications',
    jsonb_agg(to_jsonb(app) ORDER BY app.id)) END
 FROM treasury.collector_credit_applications app JOIN accounting.fiscal_periods period ON period.id=p_period
 WHERE (app.accepted_at AT TIME ZONE 'Asia/Manila')::date<=period.end_date;
$$;
ALTER FUNCTION accounting.lock_period_review_additional_sources() RENAME TO lock_period_review_before_credit_application_sources;
CREATE FUNCTION accounting.lock_period_review_additional_sources()
RETURNS VOID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 PERFORM accounting.lock_period_review_before_credit_application_sources();
 LOCK TABLE treasury.collector_credit_applications,treasury.collector_requests IN SHARE MODE;
END $$;

DO $$ DECLARE role_name TEXT; item RECORD; BEGIN
 FOREACH role_name IN ARRAY ARRAY['PUBLIC','anon','authenticated','service_role'] LOOP
  IF role_name='PUBLIC' OR EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
   FOR item IN SELECT oid::regprocedure::text signature FROM pg_proc WHERE pronamespace='accounting'::regnamespace
    AND (proname LIKE '%collector%' OR proname LIKE '%credit_application%' OR proname IN ('period_review_additional_evidence','lock_period_review_additional_sources')) LOOP
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM %s',item.signature,CASE WHEN role_name='PUBLIC' THEN 'PUBLIC' ELSE quote_ident(role_name) END);
   END LOOP;
  END IF;
 END LOOP;
END $$;

-- Acceptance settles the obligation. Only its retained physical count is cash.
CREATE OR REPLACE FUNCTION core.complete_remittance_acceptance_notification()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE accepted treasury.collector_settlements%ROWTYPE; counted treasury.collector_counts%ROWTYPE;
BEGIN
 IF OLD.status='submitted' AND NEW.status='received' THEN
  SELECT * INTO accepted FROM treasury.collector_settlements WHERE remittance_id=NEW.id;
  SELECT * INTO counted FROM treasury.collector_counts WHERE id=accepted.count_id;
  UPDATE core.user_notifications SET status='accepted',read_at=coalesce(read_at,NEW.received_at),accepted_at=NEW.received_at,
   title=CASE WHEN (accepted.payload->>'authorized_credit_amount')::numeric>0 THEN 'Remittance settled' ELSE title END,
   message=CASE WHEN (accepted.payload->>'authorized_credit_amount')::numeric>0 THEN format(
    'Settled obligation: PHP %s. Actual cash received: PHP %s; credit applied: PHP %s; cash excess: PHP %s.',
    accepted.payload->>'gross_obligation',accepted.payload->>'physical_amount',accepted.payload->>'authorized_credit_amount',counted.payload->>'difference') ELSE message END
  WHERE remittance_id=NEW.id AND recipient_user_id=NEW.recipient_user_id;
 END IF;
 RETURN NEW;
END $$;
COMMENT ON COLUMN lending.collection_remittances.custody_user_id IS
 'Recipient accountable for the accepted remittance. For a retained credit application, collector_settlements separates actual received cash from credit settling the gross obligation.';
COMMIT;
