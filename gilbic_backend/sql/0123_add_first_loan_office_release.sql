BEGIN;

-- Existing shared loan states remain authoritative. Unreleased approvals must
-- not manufacture a cash-release date. Existing dated loan rows remain valid.
ALTER TABLE lending.loans ALTER COLUMN date_released DROP NOT NULL;
ALTER TABLE lending.loans ALTER COLUMN due_date DROP NOT NULL;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='first_loan_unreleased_dates') THEN
        ALTER TABLE lending.loans ADD CONSTRAINT first_loan_unreleased_dates CHECK (
            (date_released IS NOT NULL AND due_date IS NOT NULL)
            OR (date_released IS NULL AND due_date IS NULL AND status IN ('draft','approved','cancelled'))
        ) NOT VALID;
    END IF;
END $$;

INSERT INTO core.permissions(code,description) VALUES
 ('lending.first_loan.approve','Approve exact first-loan terms and authorize office release'),
 ('lending.first_loan.release','Record protected first-loan office signing and cash handoff')
ON CONFLICT(code) DO NOTHING;
INSERT INTO core.role_permissions(role_id,permission_code)
SELECT r.id,p.code FROM core.roles r CROSS JOIN core.permissions p
WHERE (r.code='management' AND p.code='lending.first_loan.approve')
   OR (r.code IN ('employee','management') AND p.code='lending.first_loan.release')
ON CONFLICT DO NOTHING;

-- Configured, controlled legal-template boundary. No counsel approval is seeded.
CREATE TABLE IF NOT EXISTS lending.first_loan_document_templates (
 version TEXT PRIMARY KEY CHECK(btrim(version)<>''),
 content_sha256 TEXT NOT NULL CHECK(content_sha256 ~ '^[0-9a-f]{64}$'),
 approved_for_execution BOOLEAN NOT NULL DEFAULT false,
 is_active BOOLEAN NOT NULL DEFAULT true,
 configured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS lending.first_loan_approvals (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 request_id UUID NOT NULL UNIQUE,
 loan_id UUID NOT NULL UNIQUE REFERENCES lending.loans(id) ON DELETE RESTRICT,
 client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
 application_version_id UUID NOT NULL REFERENCES lending.loan_application_versions(id) ON DELETE RESTRICT,
 cif_version_id UUID NOT NULL REFERENCES lending.client_cif_versions(id) ON DELETE RESTRICT,
 template_version TEXT NOT NULL REFERENCES lending.first_loan_document_templates(version) ON DELETE RESTRICT,
 packet JSONB NOT NULL CHECK(jsonb_typeof(packet)='object'),
 packet_hash TEXT NOT NULL CHECK(packet_hash ~ '^[0-9a-f]{64}$'),
 approved_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
 approved_device_id UUID NOT NULL REFERENCES core.devices(id) ON DELETE RESTRICT,
 approved_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS lending.first_loan_decisions (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), request_id UUID NOT NULL UNIQUE,
 application_version_id UUID NOT NULL REFERENCES lending.loan_application_versions(id) ON DELETE RESTRICT,
 loan_id UUID REFERENCES lending.loans(id) ON DELETE RESTRICT,
 decision TEXT NOT NULL CHECK(decision IN ('rejected','approval_cancelled')),
 reason TEXT NOT NULL CHECK(btrim(reason)<>''),
 actor_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
 recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS lending.first_loan_packet_documents (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 loan_id UUID NOT NULL UNIQUE REFERENCES lending.first_loan_approvals(loan_id) ON DELETE RESTRICT,
 packet_hash TEXT NOT NULL,
 content_sha256 TEXT NOT NULL CHECK(content_sha256 ~ '^[0-9a-f]{64}$'),
 byte_count INTEGER NOT NULL CHECK(byte_count>0 AND byte_count<=10485760),
 storage_key UUID NOT NULL UNIQUE,
 pricing_snapshot JSONB NOT NULL CHECK(jsonb_typeof(pricing_snapshot)='object'),
 generated_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
 generated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS lending.first_loan_authorizations (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), request_id UUID NOT NULL UNIQUE,
 loan_id UUID NOT NULL REFERENCES lending.first_loan_approvals(loan_id) ON DELETE RESTRICT,
 packet_hash TEXT NOT NULL,
 authorized_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
 authorized_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS lending.first_loan_authorization_revocations (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), request_id UUID NOT NULL UNIQUE,
 authorization_id UUID NOT NULL UNIQUE REFERENCES lending.first_loan_authorizations(id) ON DELETE RESTRICT,
 reason TEXT NOT NULL CHECK(btrim(reason)<>''),
 revoked_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
 revoked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS lending.first_loan_releases (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), request_id UUID NOT NULL UNIQUE,
 loan_id UUID NOT NULL UNIQUE REFERENCES lending.first_loan_approvals(loan_id) ON DELETE RESTRICT,
 authorization_id UUID NOT NULL REFERENCES lending.first_loan_authorizations(id) ON DELETE RESTRICT,
 packet_hash TEXT NOT NULL,
 contract_evidence_reference TEXT NOT NULL CHECK(btrim(contract_evidence_reference)<>''),
 cash_evidence_reference TEXT NOT NULL CHECK(btrim(cash_evidence_reference)<>''),
 cash_amount NUMERIC(18,2) NOT NULL CHECK(cash_amount>0),
 receipt_reference TEXT NOT NULL UNIQUE,
 schedule_id UUID NOT NULL REFERENCES lending.loan_contract_schedules(id) ON DELETE RESTRICT,
 disbursement_event_id UUID NOT NULL REFERENCES lending.loan_disbursement_events(id) ON DELETE RESTRICT,
 released_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
 released_device_id UUID NOT NULL REFERENCES core.devices(id) ON DELETE RESTRICT,
 released_at TIMESTAMPTZ NOT NULL,
 receipt JSONB NOT NULL CHECK(jsonb_typeof(receipt)='object')
);
CREATE TABLE IF NOT EXISTS lending.first_loan_credential_intents (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 client_id UUID NOT NULL UNIQUE REFERENCES lending.clients(id) ON DELETE RESTRICT,
 loan_id UUID NOT NULL UNIQUE REFERENCES lending.loans(id) ON DELETE RESTRICT,
 release_id UUID NOT NULL UNIQUE REFERENCES lending.first_loan_releases(id) ON DELETE RESTRICT,
 email TEXT NOT NULL CHECK(btrim(email)<>''),
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','processing','completed','reconciliation_required')),
 auth_user_id UUID UNIQUE, linked_user_id UUID REFERENCES core.users(id) ON DELETE RESTRICT,
 username TEXT, last_error_code TEXT,
 attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count>=0),
 requested_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 completed_at TIMESTAMPTZ
);

DO $$ DECLARE t TEXT; BEGIN
 FOREACH t IN ARRAY ARRAY['first_loan_approvals','first_loan_decisions','first_loan_packet_documents','first_loan_authorizations','first_loan_authorization_revocations','first_loan_releases'] LOOP
   EXECUTE format('DROP TRIGGER IF EXISTS first_loan_immutable ON lending.%I',t);
   EXECUTE format('CREATE TRIGGER first_loan_immutable BEFORE UPDATE OR DELETE ON lending.%I FOR EACH ROW EXECUTE FUNCTION lending.reject_loan_application_history_mutation()',t);
   EXECUTE format('DROP TRIGGER IF EXISTS first_loan_no_truncate ON lending.%I',t);
   EXECUTE format('CREATE TRIGGER first_loan_no_truncate BEFORE TRUNCATE ON lending.%I FOR EACH STATEMENT EXECUTE FUNCTION lending.reject_loan_application_history_mutation()',t);
 END LOOP;
END $$;

CREATE OR REPLACE FUNCTION lending.guard_first_loan_locked_terms() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM lending.first_loan_approvals WHERE loan_id=OLD.id)
 AND (NEW.client_id,NEW.loan_type_id,NEW.principal,NEW.daily_amount,NEW.interest_rate,NEW.loan_number)
 IS DISTINCT FROM (OLD.client_id,OLD.loan_type_id,OLD.principal,OLD.daily_amount,OLD.interest_rate,OLD.loan_number) THEN
   RAISE EXCEPTION 'First-loan approved terms are immutable' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS first_loan_locked_terms ON lending.loans;
CREATE TRIGGER first_loan_locked_terms BEFORE UPDATE ON lending.loans
FOR EACH ROW EXECUTE FUNCTION lending.guard_first_loan_locked_terms();

CREATE OR REPLACE FUNCTION lending.guard_first_loan_unreleased_schedule() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM lending.first_loan_approvals a JOIN lending.loans l ON l.id=a.loan_id
           WHERE a.loan_id=NEW.loan_id AND (l.status='approved' OR l.date_released IS NULL)) THEN
   RAISE EXCEPTION 'First-loan schedules activate only in the protected cash-release transaction' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS first_loan_unreleased_schedule ON lending.loan_contract_schedules;
CREATE TRIGGER first_loan_unreleased_schedule BEFORE INSERT OR UPDATE ON lending.loan_contract_schedules
FOR EACH ROW EXECUTE FUNCTION lending.guard_first_loan_unreleased_schedule();

CREATE OR REPLACE FUNCTION lending.guard_first_loan_release_transition() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM lending.first_loan_approvals WHERE loan_id=NEW.id)
 AND EXISTS(SELECT 1 FROM lending.loans WHERE id=NEW.id AND (status NOT IN ('approved','cancelled') OR date_released IS NOT NULL))
 AND NOT EXISTS(SELECT 1 FROM lending.first_loan_releases WHERE loan_id=NEW.id) THEN
   RAISE EXCEPTION 'First-loan activation requires the complete recorded cash-release transaction' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS first_loan_release_transition ON lending.loans;
CREATE CONSTRAINT TRIGGER first_loan_release_transition AFTER UPDATE ON lending.loans
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION lending.guard_first_loan_release_transition();

CREATE OR REPLACE FUNCTION lending.guard_first_loan_disbursement_integrity() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
 IF TG_OP='INSERT' AND EXISTS(SELECT 1 FROM lending.first_loan_approvals a JOIN lending.loans l ON l.id=a.loan_id
     WHERE a.loan_id=NEW.loan_id AND (l.status='approved' OR l.date_released IS NULL)) THEN
   RAISE EXCEPTION 'First-loan disbursement requires the protected office release transaction' USING ERRCODE='23514';
 END IF;
 IF TG_OP='UPDATE' AND NEW.is_voided AND EXISTS(SELECT 1 FROM lending.first_loan_releases WHERE disbursement_event_id=OLD.id) THEN
   RAISE EXCEPTION 'First-loan released cash requires a dedicated complete release reversal' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS first_loan_disbursement_integrity ON lending.loan_disbursement_events;
CREATE TRIGGER first_loan_disbursement_integrity BEFORE INSERT OR UPDATE ON lending.loan_disbursement_events
FOR EACH ROW EXECUTE FUNCTION lending.guard_first_loan_disbursement_integrity();

REVOKE ALL ON lending.first_loan_document_templates,lending.first_loan_approvals,
 lending.first_loan_decisions,lending.first_loan_packet_documents,lending.first_loan_authorizations,lending.first_loan_authorization_revocations,
 lending.first_loan_releases,lending.first_loan_credential_intents FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION lending.guard_first_loan_locked_terms() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION lending.guard_first_loan_unreleased_schedule() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION lending.guard_first_loan_release_transition() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION lending.guard_first_loan_disbursement_integrity() FROM PUBLIC;
COMMIT;
