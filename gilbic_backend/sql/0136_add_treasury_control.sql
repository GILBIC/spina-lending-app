BEGIN;

-- Backend-only bounded ledger. No real wallet, opening balance or role grant.
CREATE SCHEMA IF NOT EXISTS treasury;
REVOKE ALL ON SCHEMA treasury FROM PUBLIC;
INSERT INTO core.permissions(code,description) VALUES
 ('treasury.account.manage','Manage explicitly scoped treasury accounts'),
 ('treasury.view','Read explicitly scoped treasury projections'),
 ('treasury.proof.submit.assigned','Report evidence for an authorized borrower'),
 ('treasury.proof.review','Review scoped evidence without certifying money'),
 ('treasury.receipt.verify','Manually verify recipient-side actual receipt'),
 ('treasury.payment.apply','Apply verified funds through protected allocations'),
 ('treasury.disbursement.record','Record evidenced actual outgoing movement'),
 ('treasury.transfer.record','Record evidenced tracked-account transfer legs'),
 ('treasury.reconcile','Match and close scoped account reconciliation'),
 ('treasury.adjust','Review restricted immutable-history corrections')
ON CONFLICT(code) DO NOTHING;

CREATE TABLE treasury.contexts (
 id uuid PRIMARY KEY, kind text NOT NULL CHECK(kind IN ('owner_operations','corporate_legal','synthetic')),
 created_by uuid NOT NULL REFERENCES core.users(id), created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE treasury.accounts (
 id uuid PRIMARY KEY, ledger_context_id uuid NOT NULL REFERENCES treasury.contexts(id),
 kind text NOT NULL CHECK(kind IN ('physical_cash','gcash','bank','transit')),
 currency text NOT NULL DEFAULT 'PHP' CHECK(currency='PHP'), alias text NOT NULL CHECK(length(alias) BETWEEN 1 AND 120),
 ownership text NOT NULL CHECK(ownership IN ('owner_personal','owner_business','corporate','synthetic')),
 custodian_user_id uuid NOT NULL REFERENCES core.users(id), masked_identifier text NOT NULL DEFAULT '',
 payment_instructions text NOT NULL DEFAULT '', designated_receiving boolean NOT NULL DEFAULT false,
 active boolean NOT NULL DEFAULT true, version bigint NOT NULL DEFAULT 1 CHECK(version>0),
 movement_watermark bigint NOT NULL DEFAULT 0 CHECK(movement_watermark>=0),
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(id,ledger_context_id)
);
CREATE TABLE treasury.account_access (
 account_id uuid NOT NULL REFERENCES treasury.accounts(id), user_id uuid NOT NULL REFERENCES core.users(id),
 permissions text[] NOT NULL, private_history boolean NOT NULL DEFAULT false, enabled boolean NOT NULL DEFAULT true,
 granted_by uuid NOT NULL REFERENCES core.users(id), updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(account_id,user_id)
);
CREATE TABLE treasury.evidence (
 id uuid PRIMARY KEY, account_id uuid NOT NULL REFERENCES treasury.accounts(id),
 uploaded_by uuid NOT NULL REFERENCES core.users(id), device_id uuid NOT NULL REFERENCES core.devices(id),
 purpose text NOT NULL CHECK(purpose IN ('claim','recipient','statement','opening','correction')),
 media_type text NOT NULL CHECK(media_type IN ('application/pdf','image/png','image/jpeg')),
 byte_count integer NOT NULL CHECK(byte_count BETWEEN 1 AND 10485760),
 sha256 text NOT NULL CHECK(sha256 ~ '^[a-f0-9]{64}$'), created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE treasury.opening_positions (
 id uuid PRIMARY KEY, account_id uuid NOT NULL, ledger_context_id uuid NOT NULL,
 cutoff timestamptz NOT NULL, amount numeric(18,2) NOT NULL CHECK(amount>=0),
 personal_amount numeric(18,2) CHECK(personal_amount>=0), third_party_amount numeric(18,2) CHECK(third_party_amount>=0),
 transit_amount numeric(18,2) CHECK(transit_amount>=0), evidence_id uuid NOT NULL REFERENCES treasury.evidence(id),
 reason text NOT NULL, status text NOT NULL CHECK(status IN ('draft','active','superseded')),
 version bigint NOT NULL DEFAULT 1 CHECK(version>0), supersedes_id uuid REFERENCES treasury.opening_positions(id),
 created_by uuid NOT NULL REFERENCES core.users(id), created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(account_id,ledger_context_id) REFERENCES treasury.accounts(id,ledger_context_id)
);
CREATE UNIQUE INDEX treasury_one_active_opening ON treasury.opening_positions(account_id) WHERE status='active';
CREATE TABLE treasury.events (
 id uuid PRIMARY KEY, account_id uuid NOT NULL, ledger_context_id uuid NOT NULL,
 provider text NOT NULL CHECK(length(btrim(provider)) BETWEEN 1 AND 200),
 reference text CHECK(reference IS NULL OR length(btrim(reference)) BETWEEN 1 AND 200),
 direction text NOT NULL CHECK(direction IN ('credit','debit')),
 amount numeric(18,2) NOT NULL CHECK(amount>0), fee numeric(18,2) NOT NULL DEFAULT 0 CHECK(fee>=0),
 effective_at timestamptz NOT NULL, observed_at timestamptz NOT NULL DEFAULT now(), verified_at timestamptz NOT NULL DEFAULT now(),
 recorded_at timestamptz NOT NULL DEFAULT now(), recorded_by_user_id uuid NOT NULL REFERENCES core.users(id),
 reported_by_user_id uuid REFERENCES core.users(id), verified_by_user_id uuid NOT NULL REFERENCES core.users(id),
 assigned_collector_user_id uuid REFERENCES core.users(id), device_id uuid NOT NULL REFERENCES core.devices(id),
 evidence_id uuid NOT NULL REFERENCES treasury.evidence(id), recipient_attestation text NOT NULL,
 classification text NOT NULL, reason text NOT NULL, version bigint NOT NULL DEFAULT 1 CHECK(version>0),
 UNIQUE(account_id,provider,reference), UNIQUE(id,account_id,ledger_context_id),
 FOREIGN KEY(account_id,ledger_context_id) REFERENCES treasury.accounts(id,ledger_context_id),
 CHECK(direction='debit' OR fee=0)
);
CREATE TABLE treasury.movement_lines (
 id uuid PRIMARY KEY, event_id uuid NOT NULL, account_id uuid NOT NULL, ledger_context_id uuid NOT NULL,
 component text NOT NULL CHECK(component IN ('principal','fee','correction')),
 signed_amount numeric(18,2) NOT NULL CHECK(signed_amount<>0), effective_at timestamptz NOT NULL,
 evidence_id uuid NOT NULL REFERENCES treasury.evidence(id), created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(event_id,account_id,ledger_context_id) REFERENCES treasury.events(id,account_id,ledger_context_id),
 UNIQUE(event_id,component)
);
CREATE TABLE treasury.event_revisions (
 id uuid PRIMARY KEY, event_id uuid NOT NULL REFERENCES treasury.events(id), version bigint NOT NULL CHECK(version>1),
 action text NOT NULL CHECK(action IN ('classify','correct')), classification text, reason text NOT NULL,
 evidence_id uuid REFERENCES treasury.evidence(id), actor_id uuid NOT NULL REFERENCES core.users(id),
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(event_id,version)
);
CREATE TABLE treasury.claims (
 id uuid PRIMARY KEY, account_id uuid NOT NULL, ledger_context_id uuid NOT NULL,
 client_id uuid NOT NULL REFERENCES lending.clients(id), submitted_by uuid NOT NULL REFERENCES core.users(id),
 version bigint NOT NULL DEFAULT 1 CHECK(version>0), status text NOT NULL DEFAULT 'pending_verification'
 CHECK(status IN ('pending_verification','correction_required','rejected','reviewed','received','partly_applied','recorded')),
 receipt_id uuid, created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(account_id,ledger_context_id) REFERENCES treasury.accounts(id,ledger_context_id)
);
CREATE TABLE treasury.claim_versions (
 id uuid PRIMARY KEY, claim_id uuid NOT NULL REFERENCES treasury.claims(id), version bigint NOT NULL CHECK(version>0),
 account_version bigint NOT NULL CHECK(account_version>0), loan_ids uuid[] NOT NULL,
 amount numeric(18,2) NOT NULL CHECK(amount>0), reference text NOT NULL,
    claimed_at timestamptz NOT NULL, sender_note text NOT NULL DEFAULT '', evidence_id uuid NOT NULL REFERENCES treasury.evidence(id),
 recipient_snapshot jsonb NOT NULL,
 submitted_by uuid NOT NULL REFERENCES core.users(id), created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(claim_id,version)
);
CREATE TABLE treasury.claim_reviews (
 id uuid PRIMARY KEY, claim_id uuid NOT NULL REFERENCES treasury.claims(id), claim_version bigint NOT NULL,
 decision text NOT NULL CHECK(decision IN ('reviewed','correction_required','rejected')), reason text NOT NULL,
 actor_id uuid NOT NULL REFERENCES core.users(id), created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE treasury.receipts (
 id uuid PRIMARY KEY, event_id uuid NOT NULL UNIQUE, account_id uuid NOT NULL, ledger_context_id uuid NOT NULL,
 client_id uuid NOT NULL REFERENCES lending.clients(id), amount numeric(18,2) NOT NULL CHECK(amount>0),
 applied_amount numeric(18,2) NOT NULL DEFAULT 0 CHECK(applied_amount>=0),
 refunded_amount numeric(18,2) NOT NULL DEFAULT 0 CHECK(refunded_amount>=0),
 version bigint NOT NULL DEFAULT 1 CHECK(version>0), effective_at timestamptz NOT NULL,
 FOREIGN KEY(event_id,account_id,ledger_context_id) REFERENCES treasury.events(id,account_id,ledger_context_id),
 CHECK(applied_amount+refunded_amount<=amount), UNIQUE(id,account_id,ledger_context_id)
);
ALTER TABLE treasury.claims ADD FOREIGN KEY(receipt_id) REFERENCES treasury.receipts(id);
CREATE TABLE treasury.applications (
 id uuid PRIMARY KEY, receipt_id uuid NOT NULL, account_id uuid NOT NULL, ledger_context_id uuid NOT NULL,
 amount numeric(18,2) NOT NULL CHECK(amount>0), status text NOT NULL CHECK(status IN ('active','reversed')),
 source_result jsonb NOT NULL, created_by uuid NOT NULL REFERENCES core.users(id), created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(receipt_id,account_id,ledger_context_id) REFERENCES treasury.receipts(id,account_id,ledger_context_id)
);
CREATE TABLE treasury.source_links (
 id uuid PRIMARY KEY, event_id uuid NOT NULL REFERENCES treasury.events(id), ledger_context_id uuid NOT NULL REFERENCES treasury.contexts(id),
 source_kind text NOT NULL, source_id uuid NOT NULL, source_version bigint NOT NULL CHECK(source_version>0),
 linked_amount numeric(18,2) NOT NULL CHECK(linked_amount>0), created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(source_kind,source_id,event_id)
);
CREATE TABLE treasury.transfers (
 id uuid PRIMARY KEY, ledger_context_id uuid NOT NULL REFERENCES treasury.contexts(id),
 source_account_id uuid NOT NULL REFERENCES treasury.accounts(id), destination_account_id uuid NOT NULL REFERENCES treasury.accounts(id),
 amount numeric(18,2) NOT NULL CHECK(amount>0), source_event_id uuid UNIQUE REFERENCES treasury.events(id),
 destination_event_id uuid UNIQUE REFERENCES treasury.events(id), version bigint NOT NULL DEFAULT 1 CHECK(version>0),
 created_at timestamptz NOT NULL DEFAULT now(), CHECK(source_account_id<>destination_account_id)
);
CREATE TABLE treasury.reconciliations (
 id uuid PRIMARY KEY, account_id uuid NOT NULL, ledger_context_id uuid NOT NULL,
 coverage_start timestamptz NOT NULL, cutoff timestamptz NOT NULL CHECK(cutoff>=coverage_start),
 actual_balance numeric(18,2) NOT NULL CHECK(actual_balance>=0), evidence_id uuid NOT NULL REFERENCES treasury.evidence(id),
 complete_history boolean NOT NULL, status text NOT NULL CHECK(status IN ('in_progress','balanced_unresolved','reconciled','superseded')),
 version bigint NOT NULL DEFAULT 1 CHECK(version>0), opening_id uuid REFERENCES treasury.opening_positions(id),
 movement_watermark bigint, expected_balance numeric(18,2), difference numeric(18,2),
 closed_snapshot jsonb, supersedes_id uuid REFERENCES treasury.reconciliations(id), requires_review boolean NOT NULL DEFAULT false,
 created_by uuid NOT NULL REFERENCES core.users(id), closed_by uuid REFERENCES core.users(id), closed_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(), FOREIGN KEY(account_id,ledger_context_id) REFERENCES treasury.accounts(id,ledger_context_id)
);
CREATE TABLE treasury.observations (
 id uuid PRIMARY KEY, reconciliation_id uuid NOT NULL REFERENCES treasury.reconciliations(id),
 provider text NOT NULL, reference text, direction text NOT NULL CHECK(direction IN ('credit','debit')),
 amount numeric(18,2) NOT NULL CHECK(amount>0), effective_at timestamptz NOT NULL
);
CREATE TABLE treasury.matches (
 id uuid PRIMARY KEY, reconciliation_id uuid NOT NULL REFERENCES treasury.reconciliations(id),
 observation_id uuid NOT NULL UNIQUE REFERENCES treasury.observations(id), event_id uuid NOT NULL REFERENCES treasury.events(id),
 component text NOT NULL CHECK(component IN ('total','principal','fee')), exception_reason text,
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(reconciliation_id,event_id,component)
);
CREATE TABLE treasury.outcomes (
 request_id uuid PRIMARY KEY, actor_id uuid NOT NULL REFERENCES core.users(id), device_id uuid NOT NULL REFERENCES core.devices(id),
 account_id uuid NOT NULL REFERENCES treasury.accounts(id), action text NOT NULL, payload_hash text NOT NULL,
 permission text NOT NULL, result jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);

-- Evidence/event/line originals and durable audit results cannot be rewritten.
CREATE FUNCTION treasury.reject_immutable_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Treasury original evidence/movement/outcome is immutable'; END $$;
CREATE FUNCTION treasury.guard_receipt_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' OR (to_jsonb(NEW)-ARRAY['applied_amount','refunded_amount','version']) IS DISTINCT FROM
   (to_jsonb(OLD)-ARRAY['applied_amount','refunded_amount','version']) OR NEW.version<>OLD.version+1 THEN
   RAISE EXCEPTION 'Receipt original account/borrower/amount/evidence is immutable';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER protect_receipt BEFORE UPDATE OR DELETE ON treasury.receipts FOR EACH ROW EXECUTE FUNCTION treasury.guard_receipt_change();
CREATE FUNCTION treasury.guard_application_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' OR (to_jsonb(NEW)-'status') IS DISTINCT FROM (to_jsonb(OLD)-'status') OR
   NOT (OLD.status='active' AND NEW.status='reversed') THEN
   RAISE EXCEPTION 'Application original funding/amount/source evidence is immutable';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER protect_application BEFORE UPDATE OR DELETE ON treasury.applications FOR EACH ROW EXECUTE FUNCTION treasury.guard_application_change();
CREATE FUNCTION treasury.guard_opening_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' OR (to_jsonb(NEW)-ARRAY['status','version']) IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['status','version'])
   OR NEW.version<>OLD.version+1 OR NOT ((OLD.status='draft' AND NEW.status='active') OR (OLD.status='active' AND NEW.status='superseded')) THEN
   RAISE EXCEPTION 'Opening original count/cutoff/evidence is immutable';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER protect_opening BEFORE UPDATE OR DELETE ON treasury.opening_positions FOR EACH ROW EXECUTE FUNCTION treasury.guard_opening_change();
CREATE FUNCTION treasury.guard_closed_reconciliation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Reconciliation history cannot be deleted'; END IF;
 IF OLD.closed_at IS NOT NULL AND (
   (to_jsonb(NEW)-ARRAY['status','requires_review']) IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['status','requires_review'])
   OR (OLD.requires_review AND NOT NEW.requires_review)
   OR (NEW.status<>OLD.status AND NOT (OLD.status='reconciled' AND NEW.status='superseded'))) THEN
   RAISE EXCEPTION 'Closed reconciliation snapshot is immutable; append a reviewed supersession';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER protect_closed_reconciliation BEFORE UPDATE OR DELETE ON treasury.reconciliations FOR EACH ROW EXECUTE FUNCTION treasury.guard_closed_reconciliation();
CREATE FUNCTION treasury.guard_source_context() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Source links cannot be rewritten'; END IF;
 IF NOT EXISTS(SELECT 1 FROM treasury.events WHERE id=NEW.event_id AND ledger_context_id=NEW.ledger_context_id)
   OR EXISTS(SELECT 1 FROM treasury.source_links WHERE source_kind=NEW.source_kind AND source_id=NEW.source_id AND ledger_context_id<>NEW.ledger_context_id) THEN
   RAISE EXCEPTION 'Source/event contexts conflict';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER protect_source_context BEFORE INSERT OR UPDATE OR DELETE ON treasury.source_links FOR EACH ROW EXECUTE FUNCTION treasury.guard_source_context();
DO $$ DECLARE table_name text; BEGIN
 FOREACH table_name IN ARRAY ARRAY['evidence','events','movement_lines','event_revisions','claim_versions','claim_reviews','observations','matches','outcomes'] LOOP
   EXECUTE format('CREATE TRIGGER immutable_original BEFORE UPDATE OR DELETE ON treasury.%I FOR EACH ROW EXECUTE FUNCTION treasury.reject_immutable_change()',table_name);
 END LOOP;
END $$;
DO $$ DECLARE table_name text; BEGIN
 FOR table_name IN SELECT tablename FROM pg_tables WHERE schemaname='treasury' LOOP
   EXECUTE format('ALTER TABLE treasury.%I ENABLE ROW LEVEL SECURITY',table_name);
   EXECUTE format('REVOKE ALL ON treasury.%I FROM PUBLIC',table_name);
 END LOOP;
 IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
   REVOKE ALL ON SCHEMA treasury FROM anon; REVOKE ALL ON ALL TABLES IN SCHEMA treasury FROM anon;
 END IF;
 IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
   REVOKE ALL ON SCHEMA treasury FROM authenticated; REVOKE ALL ON ALL TABLES IN SCHEMA treasury FROM authenticated;
 END IF;
END $$;
COMMIT;
