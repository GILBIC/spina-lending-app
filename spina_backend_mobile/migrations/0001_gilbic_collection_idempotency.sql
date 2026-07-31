BEGIN;

CREATE SCHEMA IF NOT EXISTS mobile;

CREATE TABLE IF NOT EXISTS mobile.gilbic_collection_idempotency (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    idempotency_key UUID NOT NULL,
    collector_account_id TEXT NOT NULL,
    registered_device_id TEXT NOT NULL,
    canonical_request_hash CHAR(64) NOT NULL,
    request_payload JSONB NOT NULL,
    result_status TEXT NOT NULL,
    server_transaction_id TEXT NOT NULL,
    receipt_number TEXT NOT NULL,
    official_balance NUMERIC(18, 2) NOT NULL,
    accepted_at TIMESTAMPTZ NOT NULL,
    route_revision TEXT,
    result_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT gilbic_collection_idempotency_key_unique
        UNIQUE (idempotency_key),
    CONSTRAINT gilbic_collection_hash_format
        CHECK (canonical_request_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT gilbic_collection_result_status
        CHECK (result_status IN ('accepted')),
    CONSTRAINT gilbic_collection_official_balance_nonnegative
        CHECK (official_balance >= 0)
);

CREATE INDEX IF NOT EXISTS gilbic_collection_idempotency_actor_idx
    ON mobile.gilbic_collection_idempotency (
        collector_account_id,
        accepted_at DESC
    );

CREATE INDEX IF NOT EXISTS gilbic_collection_idempotency_transaction_idx
    ON mobile.gilbic_collection_idempotency (server_transaction_id);

COMMENT ON TABLE mobile.gilbic_collection_idempotency IS
    'Successful Gilbic collection submissions and their replayable results. '
    'Rows must be inserted in the same transaction as the official SPINA '
    'collection, balance update, receipt, and audit log.';

COMMENT ON COLUMN mobile.gilbic_collection_idempotency.idempotency_key IS
    'Client-generated UUID reused for every retry of one collection draft.';

COMMENT ON COLUMN mobile.gilbic_collection_idempotency.canonical_request_hash IS
    'SHA-256 of the normalized gilbic-collection-v1 request body.';

COMMIT;
