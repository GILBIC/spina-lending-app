BEGIN;

CREATE TABLE IF NOT EXISTS mobile.gilbic_combined_collection_idempotency (
    idempotency_key UUID PRIMARY KEY,
    collector_account_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    registered_device_id UUID NOT NULL
        REFERENCES core.devices(id) ON DELETE RESTRICT,
    canonical_request_hash TEXT NOT NULL,
    request_payload JSONB NOT NULL,
    result_payload JSONB NOT NULL,
    accepted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS gilbic_combined_collection_actor_idx
    ON mobile.gilbic_combined_collection_idempotency
       (collector_account_id, accepted_at DESC);

COMMIT;
