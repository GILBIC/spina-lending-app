BEGIN;

CREATE SCHEMA IF NOT EXISTS mobile;
REVOKE ALL ON SCHEMA mobile FROM PUBLIC;

ALTER TABLE lending.loan_collection_state
    ADD COLUMN IF NOT EXISTS is_reconciled BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE lending.loan_collection_state
    ADD COLUMN IF NOT EXISTS state_version BIGINT NOT NULL DEFAULT 0
        CHECK (state_version >= 0);

CREATE SEQUENCE IF NOT EXISTS lending.collection_receipt_sequence
    AS BIGINT
    START WITH 1
    INCREMENT BY 1
    NO CYCLE;

CREATE TABLE IF NOT EXISTS lending.collection_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key UUID NOT NULL UNIQUE,
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    collector_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    registered_device_id UUID NOT NULL REFERENCES core.devices(id) ON DELETE RESTRICT,
    route_entry_id UUID NOT NULL,
    collection_date DATE NOT NULL,
    entry_type TEXT NOT NULL
        CHECK (entry_type IN ('payment', 'advance', 'pass')),
    amount NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (amount >= 0),
    advance_from DATE,
    advance_until DATE,
    recorded_at TIMESTAMPTZ NOT NULL,
    accepted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    device_sequence BIGINT NOT NULL CHECK (device_sequence > 0),
    note TEXT NOT NULL DEFAULT '',
    route_revision TEXT,
    previous_balance NUMERIC(18,2) NOT NULL CHECK (previous_balance >= 0),
    official_balance NUMERIC(18,2) NOT NULL CHECK (official_balance >= 0),
    pass_count_after INTEGER NOT NULL CHECK (pass_count_after >= 0),
    advance_until_after DATE,
    receipt_number TEXT NOT NULL UNIQUE,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (route_entry_id = loan_id),
    CHECK (
        (entry_type = 'pass' AND amount = 0
            AND advance_from IS NULL AND advance_until IS NULL)
        OR
        (entry_type = 'payment' AND amount > 0
            AND advance_from IS NULL AND advance_until IS NULL)
        OR
        (entry_type = 'advance' AND amount > 0
            AND advance_from IS NOT NULL AND advance_until IS NOT NULL
            AND advance_until >= advance_from)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS lending_collection_device_sequence_uidx
    ON lending.collection_transactions (registered_device_id, device_sequence);
CREATE UNIQUE INDEX IF NOT EXISTS lending_collection_one_pass_per_day_uidx
    ON lending.collection_transactions (loan_id, collection_date)
    WHERE entry_type = 'pass';
CREATE INDEX IF NOT EXISTS lending_collection_loan_date_idx
    ON lending.collection_transactions (loan_id, collection_date DESC, accepted_at DESC);
CREATE INDEX IF NOT EXISTS lending_collection_collector_date_idx
    ON lending.collection_transactions (collector_user_id, collection_date DESC);
CREATE INDEX IF NOT EXISTS lending_collection_client_date_idx
    ON lending.collection_transactions (client_id, collection_date DESC);

CREATE TABLE IF NOT EXISTS mobile.gilbic_collection_idempotency (
    idempotency_key UUID PRIMARY KEY,
    collector_account_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    registered_device_id UUID NOT NULL REFERENCES core.devices(id) ON DELETE RESTRICT,
    canonical_request_hash CHAR(64) NOT NULL,
    request_payload JSONB NOT NULL,
    result_status TEXT NOT NULL DEFAULT 'accepted'
        CHECK (result_status = 'accepted'),
    server_transaction_id UUID NOT NULL UNIQUE
        REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    receipt_number TEXT NOT NULL,
    official_balance NUMERIC(18,2) NOT NULL CHECK (official_balance >= 0),
    accepted_at TIMESTAMPTZ NOT NULL,
    route_revision TEXT,
    result_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (canonical_request_hash ~ '^[0-9a-f]{64}$')
);

CREATE INDEX IF NOT EXISTS mobile_collection_actor_date_idx
    ON mobile.gilbic_collection_idempotency (collector_account_id, accepted_at DESC);

COMMENT ON COLUMN lending.loan_collection_state.is_reconciled IS
    'True only after the remaining balance and collection state are verified against the authoritative SPINA source.';
COMMENT ON TABLE lending.collection_transactions IS
    'Official immutable payment, ADV, and PASS records accepted from Gilbic.';
COMMENT ON TABLE mobile.gilbic_collection_idempotency IS
    'Replayable successful mobile results stored in the same transaction as the official collection.';

COMMIT;
