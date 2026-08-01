BEGIN;

CREATE INDEX IF NOT EXISTS mobile_collection_registered_device_idx
    ON mobile.gilbic_collection_idempotency (registered_device_id);

COMMIT;
