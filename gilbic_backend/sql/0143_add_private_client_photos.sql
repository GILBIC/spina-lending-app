BEGIN;

-- Portraits are independent of CIF liveness, signatures and financial records.
CREATE TABLE IF NOT EXISTS lending.client_photos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    version INTEGER NOT NULL CHECK (version > 0),
    uploaded_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    request_id UUID NOT NULL,
    expected_version INTEGER NOT NULL CHECK (expected_version = version - 1),
    request_sha256 TEXT NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
    content_type TEXT NOT NULL CHECK (content_type = 'image/jpeg'),
    byte_size INTEGER NOT NULL CHECK (byte_size > 0 AND byte_size <= 5242880),
    photo_data BYTEA NOT NULL CHECK (octet_length(photo_data) = byte_size),
    UNIQUE (client_id, version),
    UNIQUE (uploaded_by_user_id, request_id)
);

CREATE OR REPLACE FUNCTION lending.guard_client_photo_history()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    RAISE EXCEPTION 'Client photo history cannot be changed; upload a new version.';
END;
$$;
DROP TRIGGER IF EXISTS client_photo_history_immutable ON lending.client_photos;
CREATE TRIGGER client_photo_history_immutable
    BEFORE UPDATE OR DELETE ON lending.client_photos
    FOR EACH ROW EXECUTE FUNCTION lending.guard_client_photo_history();
DROP TRIGGER IF EXISTS client_photo_history_no_truncate ON lending.client_photos;
CREATE TRIGGER client_photo_history_no_truncate
    BEFORE TRUNCATE ON lending.client_photos
    FOR EACH STATEMENT EXECUTE FUNCTION lending.guard_client_photo_history();

-- Only the trusted backend may read bytes; clients never receive public URLs.
ALTER TABLE lending.client_photos ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON lending.client_photos FROM PUBLIC;
REVOKE ALL ON FUNCTION lending.guard_client_photo_history() FROM PUBLIC;
DO $$
DECLARE client_role TEXT;
BEGIN
    FOREACH client_role IN ARRAY ARRAY['anon','authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=client_role) THEN
            EXECUTE format('REVOKE ALL ON lending.client_photos FROM %I', client_role);
            EXECUTE format('REVOKE ALL ON FUNCTION lending.guard_client_photo_history() FROM %I', client_role);
        END IF;
    END LOOP;
END;
$$;

COMMIT;
