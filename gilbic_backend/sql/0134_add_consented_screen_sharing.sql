BEGIN;
INSERT INTO core.permissions(code,description) VALUES
 ('screen_share.view','View an eligible Spina work screen with a visible Management viewing indicator')
ON CONFLICT(code) DO NOTHING;
INSERT INTO core.role_permissions(role_id,permission_code)
 SELECT id,'screen_share.view' FROM core.roles WHERE code='management'
ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS core.screen_share_sessions (
 id uuid PRIMARY KEY,
 process_id uuid NOT NULL,
 viewer_user_id uuid NOT NULL REFERENCES core.users(id),
 viewer_device_id uuid NOT NULL REFERENCES core.devices(id),
 holder_user_id uuid NOT NULL REFERENCES core.users(id),
 holder_device_id uuid NOT NULL REFERENCES core.devices(id),
 state text NOT NULL CHECK(state IN ('pending','active','stopped','declined','expired')),
 generation bigint NOT NULL DEFAULT 1 CHECK(generation>0),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 expires_at timestamptz NOT NULL,
 lease_expires_at timestamptz,
 ended_reason text,
 last_sequence bigint NOT NULL DEFAULT 0 CHECK(last_sequence>=0),
 last_frame_at timestamptz,
 CHECK(viewer_user_id<>holder_user_id),
 CHECK((state IN ('pending','active') AND ended_reason IS NULL) OR (state IN ('stopped','declined','expired') AND ended_reason IS NOT NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS screen_share_viewer_live ON core.screen_share_sessions(viewer_device_id) WHERE state IN ('pending','active');
CREATE UNIQUE INDEX IF NOT EXISTS screen_share_holder_live ON core.screen_share_sessions(holder_device_id) WHERE state IN ('pending','active');
CREATE INDEX IF NOT EXISTS screen_share_request_rate ON core.screen_share_sessions(viewer_user_id,created_at);
REVOKE ALL ON core.screen_share_sessions FROM PUBLIC;
DO $$ DECLARE client_role text; BEGIN
 FOREACH client_role IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=client_role) THEN
   EXECUTE format('REVOKE ALL ON core.screen_share_sessions FROM %I',client_role);
  END IF;
 END LOOP;
END $$;
COMMIT;
