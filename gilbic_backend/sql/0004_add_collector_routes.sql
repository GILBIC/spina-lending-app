BEGIN;

CREATE TABLE IF NOT EXISTS lending.collector_area_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collector_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    area TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0 CHECK (sort_order >= 0),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (btrim(area) <> '')
);

CREATE UNIQUE INDEX IF NOT EXISTS lending_collector_area_user_lower_uidx
    ON lending.collector_area_assignments (collector_user_id, lower(area));
CREATE INDEX IF NOT EXISTS lending_collector_area_active_order_idx
    ON lending.collector_area_assignments (collector_user_id, is_active, sort_order);

CREATE TABLE IF NOT EXISTS lending.loan_collection_state (
    loan_id UUID PRIMARY KEY REFERENCES lending.loans(id) ON DELETE CASCADE,
    remaining_balance NUMERIC(18,2) NOT NULL CHECK (remaining_balance >= 0),
    pass_count INTEGER NOT NULL DEFAULT 0 CHECK (pass_count >= 0),
    last_payment_date DATE,
    advance_until DATE,
    note TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS lending_loan_collection_state_advance_idx
    ON lending.loan_collection_state(advance_until)
    WHERE advance_until IS NOT NULL;

INSERT INTO lending.loan_collection_state (loan_id, remaining_balance)
SELECT l.id, l.principal
FROM lending.loans l
ON CONFLICT (loan_id) DO NOTHING;

COMMIT;
