BEGIN;

-- No real people, wage values, authority mappings or balances are seeded.
INSERT INTO core.permissions(code,description) VALUES
 ('employee_operations.manage','Review other employee records and prepare employee operations'),
 ('accounting.journal.prepare','Prepare and read accounting journal drafts without posting')
ON CONFLICT(code) DO NOTHING;
INSERT INTO core.roles(code,name,description) VALUES
 ('employee_manager','Staff Manager','Narrow employee responsibility; never grants loan approval or self approval')
ON CONFLICT(code) DO NOTHING;
INSERT INTO core.role_permissions(role_id,permission_code)
 SELECT r.id,p.code FROM core.roles r CROSS JOIN core.permissions p
 WHERE r.code='employee_manager' AND p.code IN ('employee_operations.manage','accounting.journal.prepare','accounting.view')
ON CONFLICT DO NOTHING;

-- Each table is a separate employee domain. Payloads are only produced from
-- strict finite application models; the API never accepts a generic record.
DO $$
DECLARE domain_table text;
BEGIN
 FOREACH domain_table IN ARRAY ARRAY[
  'employee_profiles','employee_schedules','employee_backups','employee_calendar',
  'employee_statutory_months','employee_statutory_remittances',
  'employee_attendance_events','employee_requests','employee_leave_ledger',
  'employee_tasks','employee_advances','employee_shortages','employee_payroll',
  'employee_payments','employee_payroll_history','employee_accounting_preparations'
 ] LOOP
  EXECUTE format('CREATE TABLE IF NOT EXISTS core.%I (
    id uuid PRIMARY KEY,
    employee_id uuid REFERENCES core.users(id) ON DELETE RESTRICT,
    version integer NOT NULL CHECK(version>0),
    status text NOT NULL CHECK(btrim(status)<>''''),
    payload jsonb NOT NULL CHECK(jsonb_typeof(payload)=''object''),
    created_by uuid NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
  )',domain_table);
  EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON core.%I(employee_id,created_at,id)',domain_table||'_employee_idx',domain_table);
  EXECUTE format('REVOKE ALL ON core.%I FROM PUBLIC',domain_table);
 END LOOP;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS employee_profiles_identity ON core.employee_profiles(employee_id);
CREATE UNIQUE INDEX IF NOT EXISTS employee_calendar_day ON core.employee_calendar((payload->>'work_date'));
CREATE UNIQUE INDEX IF NOT EXISTS employee_statutory_month_identity ON core.employee_statutory_months(employee_id,(payload->>'month'));
CREATE UNIQUE INDEX IF NOT EXISTS employee_schedule_effective ON core.employee_schedules(employee_id,(payload->>'effective_from'));
CREATE UNIQUE INDEX IF NOT EXISTS employee_payroll_period ON core.employee_payroll(employee_id,(payload->>'week_start'),(payload->>'payroll_kind'))
 WHERE NOT(payload ? 'original_payroll_id');

CREATE TABLE IF NOT EXISTS core.employee_profile_versions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 employee_id uuid NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
 profile_version integer NOT NULL CHECK(profile_version>0),
 effective_from date NOT NULL,
 payload jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(employee_id,profile_version)
);

CREATE TABLE IF NOT EXISTS core.employee_action_receipts (
 request_id uuid PRIMARY KEY,
 actor_user_id uuid NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
 actor_device_id uuid NOT NULL REFERENCES core.devices(id) ON DELETE RESTRICT,
 body_sha256 text NOT NULL CHECK(body_sha256 ~ '^[0-9a-f]{64}$'),
 result jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS core.employee_history (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 record_id uuid NOT NULL,
 domain text NOT NULL,
 employee_id uuid REFERENCES core.users(id) ON DELETE RESTRICT,
 version integer NOT NULL,
 action text NOT NULL,
 actor_user_id uuid NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
 actor_device_id uuid NOT NULL REFERENCES core.devices(id) ON DELETE RESTRICT,
 request_id uuid NOT NULL,
 before_state jsonb,
 after_state jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS employee_history_record ON core.employee_history(record_id,version);

CREATE OR REPLACE FUNCTION core.reject_employee_evidence_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Employee evidence is immutable'; END $$;
DO $$
DECLARE domain_table text;
BEGIN
 FOREACH domain_table IN ARRAY ARRAY['employee_action_receipts','employee_history','employee_profile_versions','employee_attendance_events','employee_payments','employee_statutory_remittances','employee_leave_ledger','employee_payroll_history'] LOOP
  EXECUTE format('DROP TRIGGER IF EXISTS employee_immutable ON core.%I',domain_table);
  EXECUTE format('CREATE TRIGGER employee_immutable BEFORE UPDATE OR DELETE ON core.%I FOR EACH ROW EXECUTE FUNCTION core.reject_employee_evidence_mutation()',domain_table);
  EXECUTE format('DROP TRIGGER IF EXISTS employee_no_truncate ON core.%I',domain_table);
  EXECUTE format('CREATE TRIGGER employee_no_truncate BEFORE TRUNCATE ON core.%I FOR EACH STATEMENT EXECUTE FUNCTION core.reject_employee_evidence_mutation()',domain_table);
  EXECUTE format('REVOKE ALL ON core.%I FROM PUBLIC',domain_table);
 END LOOP;
 -- Existing private-schema barrier revokes schema USAGE and application table
 -- privileges from anonymous/authenticated roles. Explicit per-table revocation
 -- also protects environments whose earlier default privileges were broader.
 FOR domain_table IN SELECT tablename FROM pg_tables WHERE schemaname='core' AND tablename LIKE 'employee\_%' ESCAPE '\' LOOP
  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
   EXECUTE format('REVOKE ALL ON core.%I FROM anon',domain_table);
  END IF;
  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
   EXECUTE format('REVOKE ALL ON core.%I FROM authenticated',domain_table);
  END IF;
 END LOOP;
END $$;
COMMIT;
