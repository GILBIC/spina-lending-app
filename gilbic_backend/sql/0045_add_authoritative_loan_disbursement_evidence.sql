BEGIN;

INSERT INTO core.permissions (code, description)
VALUES (
    'accounting.loan_disbursement.evidence.manage',
    'Register and void authoritative loan disbursement evidence without creating or posting accounting journals'
)
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code = 'accounting.loan_disbursement.evidence.manage'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS lending.loan_disbursement_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id UUID NOT NULL
        REFERENCES lending.loans(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL
        REFERENCES lending.clients(id) ON DELETE RESTRICT,
    event_kind TEXT NOT NULL
        CHECK (event_kind IN ('new_loan_release', 'renewal_release', 'restructure_release')),
    business_date DATE NOT NULL,
    disbursed_at TIMESTAMPTZ NOT NULL,
    cash_disbursed_amount NUMERIC(18,2) NOT NULL
        CHECK (cash_disbursed_amount >= 0),
    settlement_amount NUMERIC(18,2) NOT NULL DEFAULT 0
        CHECK (settlement_amount >= 0),
    other_deduction_amount NUMERIC(18,2) NOT NULL DEFAULT 0
        CHECK (other_deduction_amount >= 0),
    funding_account_system_key TEXT NOT NULL,
    external_reference TEXT NOT NULL,
    evidence_note TEXT NOT NULL DEFAULT '',
    principal_snapshot NUMERIC(18,2) NOT NULL CHECK (principal_snapshot > 0),
    date_released_snapshot DATE NOT NULL,
    loan_status_snapshot TEXT NOT NULL,
    recorded_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_voided BOOLEAN NOT NULL DEFAULT false,
    voided_by_user_id UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    voided_at TIMESTAMPTZ,
    void_reason TEXT,
    CHECK (btrim(funding_account_system_key) <> ''),
    CHECK (btrim(external_reference) <> ''),
    CHECK (
        cash_disbursed_amount + settlement_amount + other_deduction_amount > 0
    ),
    CHECK (
        (
            is_voided = false
            AND voided_by_user_id IS NULL
            AND voided_at IS NULL
            AND void_reason IS NULL
        )
        OR
        (
            is_voided = true
            AND voided_by_user_id IS NOT NULL
            AND voided_at IS NOT NULL
            AND btrim(coalesce(void_reason, '')) <> ''
        )
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS lending_one_active_disbursement_per_loan_uidx
    ON lending.loan_disbursement_events (loan_id)
    WHERE is_voided = false;
CREATE INDEX IF NOT EXISTS lending_loan_disbursement_events_date_idx
    ON lending.loan_disbursement_events (business_date DESC, recorded_at DESC);
CREATE INDEX IF NOT EXISTS lending_loan_disbursement_events_client_idx
    ON lending.loan_disbursement_events (client_id, business_date DESC);

CREATE OR REPLACE FUNCTION lending.guard_loan_disbursement_event_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF coalesce(
            current_setting('lending.loan_disbursement_evidence_insert_allowed', true),
            ''
        ) = 'on' THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'Loan disbursement evidence must be registered through the protected evidence function.';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Loan disbursement evidence is immutable and cannot be deleted.';
    END IF;

    IF coalesce(
        current_setting('lending.loan_disbursement_evidence_void_allowed', true),
        ''
    ) <> 'on' THEN
        RAISE EXCEPTION 'Loan disbursement evidence is immutable; use the protected void function.';
    END IF;

    IF OLD.is_voided = true THEN
        RAISE EXCEPTION 'Voided loan disbursement evidence is permanent.';
    END IF;

    IF NEW.id IS DISTINCT FROM OLD.id
       OR NEW.loan_id IS DISTINCT FROM OLD.loan_id
       OR NEW.client_id IS DISTINCT FROM OLD.client_id
       OR NEW.event_kind IS DISTINCT FROM OLD.event_kind
       OR NEW.business_date IS DISTINCT FROM OLD.business_date
       OR NEW.disbursed_at IS DISTINCT FROM OLD.disbursed_at
       OR NEW.cash_disbursed_amount IS DISTINCT FROM OLD.cash_disbursed_amount
       OR NEW.settlement_amount IS DISTINCT FROM OLD.settlement_amount
       OR NEW.other_deduction_amount IS DISTINCT FROM OLD.other_deduction_amount
       OR NEW.funding_account_system_key IS DISTINCT FROM OLD.funding_account_system_key
       OR NEW.external_reference IS DISTINCT FROM OLD.external_reference
       OR NEW.evidence_note IS DISTINCT FROM OLD.evidence_note
       OR NEW.principal_snapshot IS DISTINCT FROM OLD.principal_snapshot
       OR NEW.date_released_snapshot IS DISTINCT FROM OLD.date_released_snapshot
       OR NEW.loan_status_snapshot IS DISTINCT FROM OLD.loan_status_snapshot
       OR NEW.recorded_by_user_id IS DISTINCT FROM OLD.recorded_by_user_id
       OR NEW.recorded_at IS DISTINCT FROM OLD.recorded_at
       OR NEW.is_voided IS DISTINCT FROM true
       OR NEW.voided_by_user_id IS NULL
       OR NEW.voided_at IS NULL
       OR btrim(coalesce(NEW.void_reason, '')) = '' THEN
        RAISE EXCEPTION 'Protected loan disbursement void may change only the immutable void-state fields.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_loan_disbursement_event_guard
    ON lending.loan_disbursement_events;
CREATE TRIGGER lending_loan_disbursement_event_guard
BEFORE INSERT OR UPDATE OR DELETE ON lending.loan_disbursement_events
FOR EACH ROW EXECUTE FUNCTION lending.guard_loan_disbursement_event_write();

CREATE OR REPLACE FUNCTION accounting.record_loan_disbursement_evidence(
    p_loan_id UUID,
    p_actor_user_id UUID,
    p_event_kind TEXT,
    p_business_date DATE,
    p_disbursed_at TIMESTAMPTZ,
    p_cash_disbursed_amount NUMERIC,
    p_settlement_amount NUMERIC,
    p_other_deduction_amount NUMERIC,
    p_funding_account_system_key TEXT,
    p_external_reference TEXT,
    p_evidence_note TEXT DEFAULT ''
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    loan_row RECORD;
    account_row RECORD;
    existing_row lending.loan_disbursement_events%ROWTYPE;
    created_id UUID;
    normalized_kind TEXT := btrim(coalesce(p_event_kind, ''));
    normalized_account TEXT := btrim(coalesce(p_funding_account_system_key, ''));
    normalized_reference TEXT := btrim(coalesce(p_external_reference, ''));
    normalized_note TEXT := btrim(coalesce(p_evidence_note, ''));
    cash_amount NUMERIC(18,2) := round(coalesce(p_cash_disbursed_amount, 0), 2);
    settlement NUMERIC(18,2) := round(coalesce(p_settlement_amount, 0), 2);
    deduction NUMERIC(18,2) := round(coalesce(p_other_deduction_amount, 0), 2);
BEGIN
    IF normalized_kind NOT IN ('new_loan_release', 'renewal_release', 'restructure_release') THEN
        RAISE EXCEPTION 'Loan disbursement evidence requires an explicit supported release context.';
    END IF;
    IF p_business_date IS NULL OR p_disbursed_at IS NULL THEN
        RAISE EXCEPTION 'Loan disbursement business date and exact disbursement timestamp are required.';
    END IF;
    IF (p_disbursed_at AT TIME ZONE 'Asia/Manila')::date <> p_business_date THEN
        RAISE EXCEPTION 'Loan disbursement business date must match the Asia/Manila date of the exact disbursement timestamp.';
    END IF;
    IF cash_amount < 0 OR settlement < 0 OR deduction < 0
       OR cash_amount + settlement + deduction <= 0 THEN
        RAISE EXCEPTION 'Loan disbursement evidence amounts must be non-negative and contain positive total consideration.';
    END IF;
    IF normalized_reference = '' THEN
        RAISE EXCEPTION 'Loan disbursement evidence requires a reference or release-control identifier.';
    END IF;

    SELECT
        loan.id,
        loan.client_id,
        loan.principal,
        loan.date_released,
        loan.status
    INTO loan_row
    FROM lending.loans loan
    WHERE loan.id = p_loan_id
    FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Loan was not found.';
    END IF;

    SELECT
        account.system_key,
        account.account_type,
        account.is_active,
        account.is_posting
    INTO account_row
    FROM accounting.accounts account
    WHERE account.system_key = normalized_account
    FOR SHARE;

    IF NOT FOUND
       OR account_row.account_type <> 'asset'
       OR account_row.is_active = false
       OR account_row.is_posting = false
       OR normalized_account NOT IN (
            'cash_office',
            'cash_collector_custody',
            'cash_bank_gcash'
       ) THEN
        RAISE EXCEPTION 'Funding account must be an active approved SPINA cash posting account.';
    END IF;

    SELECT *
    INTO existing_row
    FROM lending.loan_disbursement_events event
    WHERE event.loan_id = p_loan_id
      AND event.is_voided = false
    FOR UPDATE;

    IF FOUND THEN
        IF existing_row.client_id = loan_row.client_id
           AND existing_row.event_kind = normalized_kind
           AND existing_row.business_date = p_business_date
           AND existing_row.disbursed_at = p_disbursed_at
           AND existing_row.cash_disbursed_amount = cash_amount
           AND existing_row.settlement_amount = settlement
           AND existing_row.other_deduction_amount = deduction
           AND existing_row.funding_account_system_key = normalized_account
           AND existing_row.external_reference = normalized_reference
           AND existing_row.evidence_note = normalized_note
           AND existing_row.principal_snapshot = loan_row.principal
           AND existing_row.date_released_snapshot = loan_row.date_released THEN
            RETURN existing_row.id;
        END IF;
        RAISE EXCEPTION 'This loan already has different active disbursement evidence; void it explicitly before registering a correction.';
    END IF;

    PERFORM set_config('lending.loan_disbursement_evidence_insert_allowed', 'on', true);
    INSERT INTO lending.loan_disbursement_events (
        loan_id,
        client_id,
        event_kind,
        business_date,
        disbursed_at,
        cash_disbursed_amount,
        settlement_amount,
        other_deduction_amount,
        funding_account_system_key,
        external_reference,
        evidence_note,
        principal_snapshot,
        date_released_snapshot,
        loan_status_snapshot,
        recorded_by_user_id
    )
    VALUES (
        p_loan_id,
        loan_row.client_id,
        normalized_kind,
        p_business_date,
        p_disbursed_at,
        cash_amount,
        settlement,
        deduction,
        normalized_account,
        normalized_reference,
        normalized_note,
        loan_row.principal,
        loan_row.date_released,
        loan_row.status,
        p_actor_user_id
    )
    RETURNING id INTO created_id;
    PERFORM set_config('lending.loan_disbursement_evidence_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs (
        actor_user_id,
        action,
        target_type,
        target_id,
        details
    )
    VALUES (
        p_actor_user_id,
        'accounting.loan_disbursement_evidence.recorded',
        'loan_disbursement_event',
        created_id,
        jsonb_build_object(
            'loan_id', p_loan_id::text,
            'event_kind', normalized_kind,
            'business_date', p_business_date,
            'cash_disbursed_amount', cash_amount,
            'settlement_amount', settlement,
            'other_deduction_amount', deduction,
            'funding_account_system_key', normalized_account,
            'external_reference', normalized_reference,
            'automatic_source_posting', false
        )
    );

    RETURN created_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.void_loan_disbursement_evidence(
    p_event_id UUID,
    p_actor_user_id UUID,
    p_reason TEXT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    event_row lending.loan_disbursement_events%ROWTYPE;
    normalized_reason TEXT := btrim(coalesce(p_reason, ''));
BEGIN
    IF length(normalized_reason) < 3 THEN
        RAISE EXCEPTION 'Enter a clear reason for voiding the loan disbursement evidence.';
    END IF;

    SELECT *
    INTO event_row
    FROM lending.loan_disbursement_events event
    WHERE event.id = p_event_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Loan disbursement evidence was not found.';
    END IF;
    IF event_row.is_voided THEN
        RAISE EXCEPTION 'Loan disbursement evidence was already voided.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM accounting.journal_entries journal
        WHERE journal.source_event_key = 'loan_disbursement:' || event_row.id::text
    ) THEN
        RAISE EXCEPTION 'Loan disbursement evidence already has accounting journal history; use the future protected accounting cancellation/reversal path.';
    END IF;

    PERFORM set_config('lending.loan_disbursement_evidence_void_allowed', 'on', true);
    UPDATE lending.loan_disbursement_events
    SET
        is_voided = true,
        voided_by_user_id = p_actor_user_id,
        voided_at = now(),
        void_reason = normalized_reason
    WHERE id = p_event_id;
    PERFORM set_config('lending.loan_disbursement_evidence_void_allowed', 'off', true);

    INSERT INTO core.audit_logs (
        actor_user_id,
        action,
        target_type,
        target_id,
        details
    )
    VALUES (
        p_actor_user_id,
        'accounting.loan_disbursement_evidence.voided',
        'loan_disbursement_event',
        p_event_id,
        jsonb_build_object(
            'loan_id', event_row.loan_id::text,
            'reason', normalized_reason,
            'automatic_source_posting', false
        )
    );
END;
$$;

CREATE OR REPLACE VIEW accounting.loan_disbursement_source_readiness AS
SELECT
    loan.id AS loan_id,
    loan.loan_number,
    loan.client_id,
    client.client_code,
    client.full_name AS client_name,
    loan_type.code AS loan_type_code,
    loan_type.name AS loan_type_name,
    loan_type.calculation_mode,
    loan.principal,
    loan.date_released,
    loan.status AS loan_status,
    event.id AS disbursement_event_id,
    event.event_kind,
    event.business_date,
    event.disbursed_at,
    event.cash_disbursed_amount,
    event.settlement_amount,
    event.other_deduction_amount,
    event.funding_account_system_key,
    event.external_reference,
    event.principal_snapshot,
    event.date_released_snapshot,
    event.loan_status_snapshot,
    CASE
        WHEN event.id IS NULL THEN 'missing_disbursement_evidence'
        WHEN event.client_id IS DISTINCT FROM loan.client_id
          OR event.principal_snapshot IS DISTINCT FROM loan.principal
          OR event.date_released_snapshot IS DISTINCT FROM loan.date_released
            THEN 'loan_changed_after_evidence'
        WHEN event.business_date IS DISTINCT FROM loan.date_released
            THEN 'release_date_mismatch'
        WHEN round(
            event.cash_disbursed_amount
            + event.settlement_amount
            + event.other_deduction_amount,
            2
        ) IS DISTINCT FROM round(event.principal_snapshot, 2)
            THEN 'unreconciled_release_components'
        WHEN event.event_kind <> 'new_loan_release'
            THEN 'renewal_or_restructure_policy_review'
        WHEN event.settlement_amount <> 0 OR event.other_deduction_amount <> 0
            THEN 'deduction_or_settlement_policy_review'
        WHEN loan_type.calculation_mode NOT IN ('fixed_daily', 'seven_by_seven')
            THEN 'loan_type_policy_review'
        ELSE 'source_evidence_ready'
    END AS readiness_status,
    'loan_disbursement:' || event.id::text AS source_event_key,
    false AS journal_lines_enabled,
    false AS automatic_source_posting
FROM lending.loans loan
JOIN lending.clients client ON client.id = loan.client_id
JOIN lending.loan_types loan_type ON loan_type.id = loan.loan_type_id
LEFT JOIN lending.loan_disbursement_events event
  ON event.loan_id = loan.id
 AND event.is_voided = false;

COMMENT ON TABLE lending.loan_disbursement_events IS
    'Authoritative explicit loan-funding evidence. A lending.loans row/date_released alone is never treated as proof that cash was disbursed.';
COMMENT ON VIEW accounting.loan_disbursement_source_readiness IS
    'Read-only Stage 5D.19 evidence gate. source_evidence_ready proves the operational funding event only; it does not authorize journal lines or automatic posting.';

COMMIT;
