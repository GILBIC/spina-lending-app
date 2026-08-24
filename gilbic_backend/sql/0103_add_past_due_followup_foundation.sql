BEGIN;

-- Management-approved Past Due / promise-to-pay foundation.
-- This migration stores borrower follow-up evidence without creating a second
-- debt, scheduled obligation, penalty, or accounting posting.

CREATE TABLE IF NOT EXISTS lending.past_due_obligations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL
        REFERENCES lending.clients(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL
        REFERENCES lending.loans(id) ON DELETE RESTRICT,
    installment_id BIGINT
        REFERENCES lending.loan_contract_installments(id) ON DELETE RESTRICT,
    obligation_date DATE NOT NULL,
    original_past_due_amount NUMERIC(18,2) NOT NULL
        CHECK (original_past_due_amount > 0),
    remaining_past_due_amount NUMERIC(18,2) NOT NULL
        CHECK (remaining_past_due_amount >= 0),
    event_kind TEXT NOT NULL CHECK (
        event_kind IN ('unable_to_pay', 'partial_payment')
    ),
    source_transaction_id UUID
        REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    current_reason_code TEXT NOT NULL CHECK (
        current_reason_code IN (
            'no_cash',
            'client_absent',
            'business_slow',
            'sick_hospital',
            'emergency',
            'promised_to_pay_later',
            'other'
        )
    ),
    current_reason_note TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'paid')),
    created_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    CHECK (remaining_past_due_amount <= original_past_due_amount),
    CHECK (
        current_reason_code <> 'other'
        OR btrim(current_reason_note) <> ''
    ),
    CHECK (
        (status = 'open'
            AND remaining_past_due_amount > 0
            AND resolved_at IS NULL)
        OR
        (status = 'paid'
            AND remaining_past_due_amount = 0
            AND resolved_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS lending_past_due_obligation_client_open_idx
    ON lending.past_due_obligations(client_id, obligation_date DESC)
    WHERE status = 'open';
CREATE INDEX IF NOT EXISTS lending_past_due_obligation_loan_date_idx
    ON lending.past_due_obligations(loan_id, obligation_date DESC);
CREATE INDEX IF NOT EXISTS lending_past_due_obligation_reason_idx
    ON lending.past_due_obligations(current_reason_code, obligation_date DESC);
CREATE UNIQUE INDEX IF NOT EXISTS lending_past_due_obligation_source_installment_uidx
    ON lending.past_due_obligations(source_transaction_id, installment_id)
    WHERE source_transaction_id IS NOT NULL AND installment_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS lending_past_due_obligation_source_legacy_uidx
    ON lending.past_due_obligations(source_transaction_id, obligation_date)
    WHERE source_transaction_id IS NOT NULL AND installment_id IS NULL;

CREATE TABLE IF NOT EXISTS lending.past_due_reason_revisions (
    id BIGSERIAL PRIMARY KEY,
    past_due_obligation_id UUID NOT NULL
        REFERENCES lending.past_due_obligations(id) ON DELETE RESTRICT,
    previous_reason_code TEXT NOT NULL,
    new_reason_code TEXT NOT NULL,
    previous_reason_note TEXT NOT NULL DEFAULT '',
    new_reason_note TEXT NOT NULL DEFAULT '',
    correction_reason TEXT NOT NULL CHECK (btrim(correction_reason) <> ''),
    changed_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS lending_past_due_reason_revision_obligation_idx
    ON lending.past_due_reason_revisions(past_due_obligation_id, changed_at DESC);

CREATE TABLE IF NOT EXISTS lending.payment_promises (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL
        REFERENCES lending.clients(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL
        REFERENCES lending.loans(id) ON DELETE RESTRICT,
    promised_for_date DATE NOT NULL,
    initial_promised_amount NUMERIC(18,2) NOT NULL
        CHECK (initial_promised_amount > 0),
    promised_amount NUMERIC(18,2) NOT NULL
        CHECK (promised_amount > 0),
    remaining_promised_amount NUMERIC(18,2) NOT NULL
        CHECK (remaining_promised_amount >= 0),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'kept', 'partially_kept', 'not_kept')
    ),
    version BIGINT NOT NULL DEFAULT 1 CHECK (version > 0),
    created_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at TIMESTAMPTZ,
    CHECK (remaining_promised_amount <= promised_amount),
    CHECK (
        (status = 'pending' AND closed_at IS NULL)
        OR
        (status <> 'pending' AND closed_at IS NOT NULL)
    )
);

-- Collector UI intentionally shows only one current promise. Historical promises
-- and revisions remain queryable under Details / History.
CREATE UNIQUE INDEX IF NOT EXISTS lending_payment_promises_one_pending_client_uidx
    ON lending.payment_promises(client_id)
    WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS lending_payment_promises_route_followup_idx
    ON lending.payment_promises(promised_for_date, client_id)
    WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS lending_payment_promises_loan_history_idx
    ON lending.payment_promises(loan_id, created_at DESC);

CREATE TABLE IF NOT EXISTS lending.payment_promise_obligations (
    promise_id UUID NOT NULL
        REFERENCES lending.payment_promises(id) ON DELETE RESTRICT,
    past_due_obligation_id UUID NOT NULL
        REFERENCES lending.past_due_obligations(id) ON DELETE RESTRICT,
    target_amount NUMERIC(18,2) NOT NULL CHECK (target_amount > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (promise_id, past_due_obligation_id)
);

CREATE INDEX IF NOT EXISTS lending_payment_promise_obligation_due_idx
    ON lending.payment_promise_obligations(past_due_obligation_id, promise_id);

CREATE TABLE IF NOT EXISTS lending.payment_promise_revisions (
    id BIGSERIAL PRIMARY KEY,
    promise_id UUID NOT NULL
        REFERENCES lending.payment_promises(id) ON DELETE RESTRICT,
    previous_promised_for_date DATE NOT NULL,
    new_promised_for_date DATE NOT NULL,
    previous_promised_amount NUMERIC(18,2) NOT NULL
        CHECK (previous_promised_amount > 0),
    new_promised_amount NUMERIC(18,2) NOT NULL
        CHECK (new_promised_amount > 0),
    changed_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS lending_payment_promise_revision_history_idx
    ON lending.payment_promise_revisions(promise_id, changed_at DESC);

-- Promise links must stay on the same client/loan and may not promise more than
-- the current promise amount in aggregate. The promise is follow-up metadata;
-- it never changes the underlying Past Due balance itself.
CREATE OR REPLACE FUNCTION lending.guard_payment_promise_obligation_link()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, lending, core
AS $$
DECLARE
    promise_client_id UUID;
    promise_loan_id UUID;
    promise_amount NUMERIC(18,2);
    obligation_client_id UUID;
    obligation_loan_id UUID;
    target_elsewhere NUMERIC(18,2);
BEGIN
    SELECT client_id, loan_id, promised_amount
    INTO promise_client_id, promise_loan_id, promise_amount
    FROM lending.payment_promises
    WHERE id = NEW.promise_id
    FOR UPDATE;

    SELECT client_id, loan_id
    INTO obligation_client_id, obligation_loan_id
    FROM lending.past_due_obligations
    WHERE id = NEW.past_due_obligation_id;

    IF promise_client_id IS NULL OR obligation_client_id IS NULL THEN
        RAISE EXCEPTION 'Promise and Past Due obligation must exist before linking.';
    END IF;

    IF promise_client_id <> obligation_client_id
       OR promise_loan_id <> obligation_loan_id THEN
        RAISE EXCEPTION 'A payment promise may cover only Past Due obligations for the same client and loan.';
    END IF;

    SELECT coalesce(sum(target_amount), 0)
    INTO target_elsewhere
    FROM lending.payment_promise_obligations
    WHERE promise_id = NEW.promise_id
      AND (
          TG_OP = 'INSERT'
          OR past_due_obligation_id <> NEW.past_due_obligation_id
      );

    IF target_elsewhere + NEW.target_amount > promise_amount THEN
        RAISE EXCEPTION 'Promise obligation targets cannot exceed the current promised amount.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_payment_promise_obligation_link_guard
    ON lending.payment_promise_obligations;
CREATE TRIGGER lending_payment_promise_obligation_link_guard
BEFORE INSERT OR UPDATE ON lending.payment_promise_obligations
FOR EACH ROW EXECUTE FUNCTION lending.guard_payment_promise_obligation_link();

-- Revision rows are permanent audit evidence.
CREATE OR REPLACE FUNCTION lending.guard_followup_revision_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Past Due / promise revision history is immutable.';
END;
$$;

DROP TRIGGER IF EXISTS lending_past_due_reason_revision_guard
    ON lending.past_due_reason_revisions;
CREATE TRIGGER lending_past_due_reason_revision_guard
BEFORE UPDATE OR DELETE ON lending.past_due_reason_revisions
FOR EACH ROW EXECUTE FUNCTION lending.guard_followup_revision_immutability();

DROP TRIGGER IF EXISTS lending_payment_promise_revision_guard
    ON lending.payment_promise_revisions;
CREATE TRIGGER lending_payment_promise_revision_guard
BEFORE UPDATE OR DELETE ON lending.payment_promise_revisions
FOR EACH ROW EXECUTE FUNCTION lending.guard_followup_revision_immutability();

COMMENT ON TABLE lending.past_due_obligations IS
    'One operational Past Due record per missed/partial obligation. Reason history survives later payment.';
COMMENT ON TABLE lending.payment_promises IS
    'Borrower follow-up promises only. A promise never creates a second debt, scheduled obligation, penalty, or accounting entry.';
COMMENT ON TABLE lending.payment_promise_obligations IS
    'Internal mapping used so promise progress follows actual allocation against the Past Due obligations the borrower promised to pay.';

COMMIT;
