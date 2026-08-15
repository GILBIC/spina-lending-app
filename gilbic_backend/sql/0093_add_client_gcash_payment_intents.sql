create table if not exists lending.client_gcash_payment_intents (
    id uuid primary key default gen_random_uuid(),
    client_id uuid not null references lending.clients(id),
    created_by_user_id uuid not null,
    provider text not null,
    provider_mode text not null check (provider_mode in ('sandbox', 'live')),
    provider_reference text,
    idempotency_key text not null,
    status text not null default 'created' check (
        status in (
            'created',
            'provider_pending',
            'paid_verified',
            'failed',
            'expired',
            'cancelled'
        )
    ),
    currency text not null default 'PHP' check (currency = 'PHP'),
    amount numeric(18,2) not null check (amount > 0),
    checkout_url text,
    qr_value text,
    provider_payload jsonb not null default '{}'::jsonb,
    provider_status_payload jsonb not null default '{}'::jsonb,
    expires_at timestamptz,
    verified_paid_at timestamptz,
    official_collection_transaction_id uuid
        references lending.collection_transactions(id),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (created_by_user_id, idempotency_key)
);

create unique index if not exists uq_client_gcash_provider_reference
    on lending.client_gcash_payment_intents(provider, provider_reference)
    where provider_reference is not null;

create index if not exists ix_client_gcash_intents_client_created
    on lending.client_gcash_payment_intents(client_id, created_at desc);

create table if not exists lending.client_gcash_payment_intent_allocations (
    intent_id uuid not null references lending.client_gcash_payment_intents(id),
    loan_id uuid not null references lending.loans(id),
    amount numeric(18,2) not null check (amount > 0),
    created_at timestamptz not null default now(),
    primary key (intent_id, loan_id)
);

comment on table lending.client_gcash_payment_intents is
    'Provider-neutral client GCash checkout intents. Creating an intent never records an official loan payment. Only a separately verified provider event may advance to protected collection/accounting processing.';

comment on column lending.client_gcash_payment_intents.official_collection_transaction_id is
    'Nullable linkage populated only by a future protected verified-payment posting workflow; provider checkout completion alone must never populate this directly.';
