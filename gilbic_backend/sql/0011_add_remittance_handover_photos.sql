BEGIN;

CREATE TABLE IF NOT EXISTS lending.remittance_handover_photos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    remittance_id UUID NOT NULL
        REFERENCES lending.collection_remittances(id) ON DELETE RESTRICT,
    version INTEGER NOT NULL CHECK (version > 0),
    uploaded_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    original_filename TEXT NOT NULL DEFAULT '',
    content_type TEXT NOT NULL
        CHECK (content_type IN ('image/jpeg', 'image/png', 'image/webp')),
    byte_size INTEGER NOT NULL CHECK (byte_size > 0 AND byte_size <= 5242880),
    sha256_hex TEXT NOT NULL CHECK (sha256_hex ~ '^[0-9a-f]{64}$'),
    photo_data BYTEA NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (remittance_id, version),
    UNIQUE (remittance_id, sha256_hex)
);

CREATE INDEX IF NOT EXISTS remittance_handover_photos_latest_idx
    ON lending.remittance_handover_photos (remittance_id, version DESC);

CREATE OR REPLACE FUNCTION lending.guard_remittance_handover_photo()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    remittance_status TEXT;
    remittance_collector UUID;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'Handover photo versions are immutable. Upload a new version before acceptance instead.'
            USING ERRCODE = '55000';
    END IF;

    SELECT status, collector_user_id
    INTO remittance_status, remittance_collector
    FROM lending.collection_remittances
    WHERE id = NEW.remittance_id
    FOR UPDATE;

    IF remittance_status IS NULL THEN
        RAISE EXCEPTION 'Remittance was not found.'
            USING ERRCODE = '23503';
    END IF;

    IF remittance_status <> 'submitted' THEN
        RAISE EXCEPTION 'Handover evidence is locked after remittance acceptance.'
            USING ERRCODE = '55000';
    END IF;

    IF NEW.uploaded_by_user_id IS DISTINCT FROM remittance_collector THEN
        RAISE EXCEPTION 'Only the collector who submitted the remittance may upload handover evidence.'
            USING ERRCODE = '42501';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_remittance_handover_photo_guard
    ON lending.remittance_handover_photos;
CREATE TRIGGER lending_remittance_handover_photo_guard
BEFORE INSERT OR UPDATE OR DELETE ON lending.remittance_handover_photos
FOR EACH ROW
EXECUTE FUNCTION lending.guard_remittance_handover_photo();

COMMENT ON TABLE lending.remittance_handover_photos IS
    'Immutable versioned photos supplied by the collector as optional evidence of the physical cash handover.';
COMMENT ON COLUMN lending.remittance_handover_photos.photo_data IS
    'Private image bytes. Access is only through authenticated remittance participant APIs.';

COMMIT;
