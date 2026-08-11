BEGIN;

INSERT INTO core.permissions (code, description)
VALUES (
    'accounting.loan_renewal_execution.evidence.manage',
    'Register and void authoritative old-loan to new-loan renewal execution evidence without creating or posting accounting journals'
)
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code = 'accounting.loan_renewal_execution.evidence.manage'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS lending.loan_renewal_execution_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    old_loan_id UUID NOT NULL
        REFERENCES lending.loans(id) ON DELETE RESTRICT,
    new_loan_id UUID NOT NULL
        REFERENCES lending.loans(id) ON DELETE RESTRICT,
    disbursement_event_id UUID NOT NULL
        REFERENCES lending.loan_disbursement_events(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL
        REFERENCES lending.clients(id) ON DELETE RESTRICT,
    renewal_request_id UUID
        REFERENCES lending.client_renewal_requests(id) ON DELETE RESTRICT,
    business_date DATE NOT NULL,
    executed_at TIMESTAMPTZ NOT NULL,
    old_loan_settlement_amount NUMERIC(18,2) NOT NULL
        CHECK (old_loan_settlement_amount >= 0),
    external_reference TEXT NOT NULL,
    evidence_note TEXT NOT NULL DEFAULT '',
    old_loan_principal_snapshot NUMERIC(18,2) NOT NULL
        CHECK (old_loan_principal_snapshot > 0),
    old_loan_date_released_snapshot DATE NOT NULL,
    old_loan_status_snapshot TEXT NOT NULL,
    new_loan_principal_snapshot NUMERIC(18,2) NOT NULL
        CHECK (new_loan_principal_snapshot > 0),
    new_loan_date_released_snapshot DATE NOT NULL,
    new_loan_status_snapshot TEXT NOT NULL,
    recorded_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_voided BOOLEAN NOT NULL DEFAULT false,
    voided_by_user_id UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    voided_at TIMESTAMPTZ,
    void_reason TEXT,
    CHECK (old_loan_id <> new_loan_id),
    CHECK (btrim(external_reference) <> ''),
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
            AND length(btrim(coalesce(void_reason, ''))) >= 3
        )
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS lending_one_active_renewal_execution_per_old_loan_uidx
    ON lending.loan_renewal_execution_events (old_loan_id)
    WHERE is_voided = false;
CREATE UNIQUE INDEX IF NOT EXISTS lending_one_active_renewal_execution_per_new_loan_uidx
    ON lending.loan_renewal_execution_events (new_loan_id)
    WHERE is_voided = false;
CREATE UNIQUE INDEX IF NOT EXISTS lending_one_active_renewal_execution_per_disbursement_uidx
    ON lending.loan_renewal_execution_events (disbursement_event_id)
    WHERE is_voided = false;
CREATE UNIQUE INDEX IF NOT EXISTS lending_one_active_renewal_execution_per_request_uidx
    ON lending.loan_renewal_execution_events (renewal_request_id)
    WHERE is_voided = false AND renewal_request_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS lending_loan_renewal_execution_events_date_idx
    ON lending.loan_renewal_execution_events (business_date DESC, recorded_at DESC);
CREATE INDEX IF NOT EXISTS lending_loan_renewal_execution_events_client_idx
    ON lending.loan_renewal_execution_events (client_id, business_date DESC);

CREATE OR REPLACE FUNCTION lending.guard_loan_renewal_execution_event_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF coalesce(
            current_setting('lending.loan_renewal_execution_insert_allowed', true),
            ''
        ) = 'on' THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'Renewal execution evidence must be registered through the protected evidence function.';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Renewal execution evidence is immutable and cannot be deleted.';
    END IF;

    IF coalesce(
        current_setting('lending.loan_renewal_execution_void_allowed', true),
        ''
    ) <> 'on' THEN
        RAISE EXCEPTION 'Renewal execution evidence is immutable; use the protected void function.';
    END IF;

    IF OLD.is_voided = true THEN
        RAISE EXCEPTION 'Voided renewal execution evidence is permanent.';
    END IF;

    IF NEW.id IS DISTINCT FROM OLD.id
       OR NEW.old_loan_id IS DISTINCT FROM OLD.old_loan_id
       OR NEW.new_loan_id IS DISTINCT FROM OLD.new_loan_id
       OR NEW.disbursement_event_id IS DISTINCT FROM OLD.disbursement_event_id
       OR NEW.client_id IS DISTINCT FROM OLD.client_id
       OR NEW.renewal_request_id IS DISTINCT FROM OLD.renewal_request_id
       OR NEW.business_date IS DISTINCT FROM OLD.business_date
       OR NEW.executed_at IS DISTINCT FROM OLD.executed_at
       OR NEW.old_loan_settlement_amount IS DISTINCT FROM OLD.old_loan_settlement_amount
       OR NEW.external_reference IS DISTINCT FROM OLD.external_reference
       OR NEW.evidence_note IS DISTINCT FROM OLD.evidence_note
       OR NEW.old_loan_principal_snapshot IS DISTINCT FROM OLD.old_loan_principal_snapshot
       OR NEW.old_loan_date_released_snapshot IS DISTINCT FROM OLD.old_loan_date_released_snapshot
       OR NEW.old_loan_status_snapshot IS DISTINCT FROM OLD.old_loan_status_snapshot
       OR NEW.new_loan_principal_snapshot IS DISTINCT FROM OLD.new_loan_principal_snapshot
       OR NEW.new_loan_date_released_snapshot IS DISTINCT FROM OLD.new_loan_date_released_snapshot
       OR NEW.new_loan_status_snapshot IS DISTINCT FROM OLD.new_loan_status_snapshot
       OR NEW.recorded_by_user_id IS DISTINCT FROM OLD.recorded_by_user_id
       OR NEW.recorded_at IS DISTINCT FROM OLD.recorded_at
       OR NEW.is_voided IS DISTINCT FROM true
       OR NEW.voided_by_user_id IS NULL
       OR NEW.voided_at IS NULL
       OR length(btrim(coalesce(NEW.void_reason, ''))) < 3 THEN
        RAISE EXCEPTION 'Protected renewal execution void may change only the immutable void-state fields.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_loan_renewal_execution_event_guard
    ON lending.loan_renewal_execution_events;
CREATE TRIGGER lending_loan_renewal_execution_event_guard
BEFORE INSERT OR UPDATE OR DELETE ON lending.loan_renewal_execution_events
FOR EACH ROW EXECUTE FUNCTION lending.guard_loan_renewal_execution_event_write();

CREATE OR REPLACE FUNCTION lending.guard_linked_renewal_release_void()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.is_voided = false
       AND NEW.is_voided = true
       AND EXISTS (
           SELECT 1
           FROM lending.loan_renewal_execution_events execution
           WHERE execution.disbursement_event_id = OLD.id
             AND execution.is_voided = false
       ) THEN
        RAISE EXCEPTION 'Renewal disbursement evidence is linked to active renewal execution evidence; void the execution evidence first.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_loan_renewal_execution_release_void_guard
    ON lending.loan_disbursement_events;
CREATE TRIGGER lending_loan_renewal_execution_release_void_guard
BEFORE UPDATE OF is_voided ON lending.loan_disbursement_events
FOR EACH ROW EXECUTE FUNCTION lending.guard_linked_renewal_release_void();

CREATE OR REPLACE FUNCTION accounting.record_loan_renewal_execution_evidence(
    p_old_loan_id UUID,
    p_new_loan_id UUID,
    p_disbursement_event_id UUID,
    p_actor_user_id UUID,
    p_business_date DATE,
    p_executed_at TIMESTAMPTZ,
    p_old_loan_settlement_amount NUMERIC,
    p_external_reference TEXT,
    p_evidence_note TEXT DEFAULT '',
    p_renewal_request_id UUID DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    old_loan RECORD;
    new_loan RECORD;
    release_event lending.loan_disbursement_events%ROWTYPE;
    request_row lending.client_renewal_requests%ROWTYPE;
    existing_row lending.loan_renewal_execution_events%ROWTYPE;
    created_id UUID;
    settlement_amount NUMERIC(18,2) := round(coalesce(p_old_loan_settlement_amount, 0), 2);
    normalized_reference TEXT := btrim(coalesce(p_external_reference, ''));
    normalized_note TEXT := btrim(coalesce(p_evidence_note, ''));
BEGIN
    IF p_old_loan_id IS NULL OR p_new_loan_id IS NULL OR p_old_loan_id = p_new_loan_id THEN
        RAISE EXCEPTION 'Renewal execution evidence requires distinct old and new loan identifiers.';
    END IF;
    IF p_disbursement_event_id IS NULL THEN
        RAISE EXCEPTION 'Renewal execution evidence requires the authoritative new-loan renewal disbursement event.';
    END IF;
    IF p_business_date IS NULL OR p_executed_at IS NULL THEN
        RAISE EXCEPTION 'Renewal execution business date and exact execution timestamp are required.';
    END IF;
    IF (p_executed_at AT TIME ZONE 'Asia/Manila')::date <> p_business_date THEN
        RAISE EXCEPTION 'Renewal execution business date must match the Asia/Manila date of the exact execution timestamp.';
    END IF;
    IF settlement_amount < 0 THEN
        RAISE EXCEPTION 'Old-loan settlement amount cannot be negative.';
    END IF;
    IF normalized_reference = '' THEN
        RAISE EXCEPTION 'Renewal execution evidence requires an office execution or release-control reference.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended('loan-renewal-execution:' || p_new_loan_id::text, 0)
    );

    SELECT
        loan.id,
        loan.client_id,
        loan.principal,
        loan.date_released,
        loan.status
    INTO old_loan
    FROM lending.loans loan
    WHERE loan.id = p_old_loan_id
    FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Old loan was not found.';
    END IF;

    SELECT
        loan.id,
        loan.client_id,
        loan.principal,
        loan.date_released,
        loan.status
    INTO new_loan
    FROM lending.loans loan
    WHERE loan.id = p_new_loan_id
    FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'New loan was not found.';
    END IF;

    IF old_loan.client_id IS DISTINCT FROM new_loan.client_id THEN
        RAISE EXCEPTION 'Renewal execution old and new loans must belong to the same client.';
    END IF;
    IF old_loan.date_released > new_loan.date_released THEN
        RAISE EXCEPTION 'Renewal execution old loan cannot be released after the new loan.';
    END IF;

    SELECT *
    INTO release_event
    FROM lending.loan_disbursement_events event
    WHERE event.id = p_disbursement_event_id
    FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Authoritative renewal disbursement evidence was not found.';
    END IF;
    IF release_event.is_voided THEN
        RAISE EXCEPTION 'Voided renewal disbursement evidence cannot support renewal execution evidence.';
    END IF;
    IF release_event.event_kind <> 'renewal_release' THEN
        RAISE EXCEPTION 'Renewal execution evidence requires a renewal_release disbursement event.';
    END IF;
    IF release_event.loan_id IS DISTINCT FROM p_new_loan_id
       OR release_event.client_id IS DISTINCT FROM new_loan.client_id THEN
        RAISE EXCEPTION 'Renewal disbursement evidence must identify the same new loan and client.';
    END IF;
    IF release_event.business_date IS DISTINCT FROM p_business_date THEN
        RAISE EXCEPTION 'Renewal execution business date must match the authoritative renewal disbursement business date.';
    END IF;
    IF round(release_event.settlement_amount, 2) IS DISTINCT FROM settlement_amount THEN
        RAISE EXCEPTION 'Old-loan settlement amount must exactly match the authoritative renewal disbursement settlement component.';
    END IF;
    IF round(
        release_event.cash_disbursed_amount
        + release_event.settlement_amount
        + release_event.other_deduction_amount,
        2
    ) IS DISTINCT FROM round(release_event.principal_snapshot, 2) THEN
        RAISE EXCEPTION 'Authoritative renewal disbursement components do not reconcile to the recorded new-loan principal snapshot.';
    END IF;
    IF release_event.principal_snapshot IS DISTINCT FROM new_loan.principal
       OR release_event.date_released_snapshot IS DISTINCT FROM new_loan.date_released THEN
        RAISE EXCEPTION 'New loan changed after the authoritative renewal disbursement evidence was recorded.';
    END IF;

    IF p_renewal_request_id IS NOT NULL THEN
        SELECT *
        INTO request_row
        FROM lending.client_renewal_requests request
        WHERE request.id = p_renewal_request_id
        FOR SHARE;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Linked client renewal request was not found.';
        END IF;
        IF request_row.status <> 'approved'
           OR request_row.client_id IS DISTINCT FROM new_loan.client_id
           OR request_row.loan_id IS DISTINCT FROM p_old_loan_id THEN
            RAISE EXCEPTION 'Linked client renewal request must be approved for the same client and old loan.';
        END IF;
    END IF;

    SELECT *
    INTO existing_row
    FROM lending.loan_renewal_execution_events event
    WHERE event.new_loan_id = p_new_loan_id
      AND event.is_voided = false
    FOR UPDATE;

    IF FOUND THEN
        IF existing_row.old_loan_id = p_old_loan_id
           AND existing_row.disbursement_event_id = p_disbursement_event_id
           AND existing_row.client_id = new_loan.client_id
           AND existing_row.renewal_request_id IS NOT DISTINCT FROM p_renewal_request_id
           AND existing_row.business_date = p_business_date
           AND existing_row.executed_at = p_executed_at
           AND existing_row.old_loan_settlement_amount = settlement_amount
           AND existing_row.external_reference = normalized_reference
           AND existing_row.evidence_note = normalized_note
           AND existing_row.old_loan_principal_snapshot = old_loan.principal
           AND existing_row.old_loan_date_released_snapshot = old_loan.date_released
           AND existing_row.new_loan_principal_snapshot = new_loan.principal
           AND existing_row.new_loan_date_released_snapshot = new_loan.date_released THEN
            RETURN existing_row.id;
        END IF;
        RAISE EXCEPTION 'This new loan already has different active renewal execution evidence; void it explicitly before registering a correction.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM lending.loan_renewal_execution_events event
        WHERE event.is_voided = false
          AND (
              event.old_loan_id = p_old_loan_id
              OR event.disbursement_event_id = p_disbursement_event_id
              OR (
                  p_renewal_request_id IS NOT NULL
                  AND event.renewal_request_id = p_renewal_request_id
              )
          )
    ) THEN
        RAISE EXCEPTION 'Old loan, renewal disbursement, or linked renewal request is already used by another active renewal execution.';
    END IF;

    PERFORM set_config('lending.loan_renewal_execution_insert_allowed', 'on', true);
    INSERT INTO lending.loan_renewal_execution_events (
        old_loan_id,
        new_loan_id,
        disbursement_event_id,
        client_id,
        renewal_request_id,
        business_date,
        executed_at,
        old_loan_settlement_amount,
        external_reference,
        evidence_note,
        old_loan_principal_snapshot,
        old_loan_date_released_snapshot,
        old_loan_status_snapshot,
        new_loan_principal_snapshot,
        new_loan_date_released_snapshot,
        new_loan_status_snapshot,
        recorded_by_user_id
    )
    VALUES (
        p_old_loan_id,
        p_new_loan_id,
        p_disbursement_event_id,
        new_loan.client_id,
        p_renewal_request_id,
        p_business_date,
        p_executed_at,
        settlement_amount,
        normalized_reference,
        normalized_note,
        old_loan.principal,
        old_loan.date_released,
        old_loan.status,
        new_loan.principal,
        new_loan.date_released,
        new_loan.status,
        p_actor_user_id
    )
    RETURNING id INTO created_id;
    PERFORM set_config('lending.loan_renewal_execution_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs (
        actor_user_id,
        action,
        target_type,
        target_id,
        details
    )
    VALUES (
        p_actor_user_id,
        'accounting.loan_renewal_execution_evidence.recorded',
        'loan_renewal_execution_event',
        created_id,
        jsonb_build_object(
            'old_loan_id', p_old_loan_id::text,
            'new_loan_id', p_new_loan_id::text,
            'disbursement_event_id', p_disbursement_event_id::text,
            'renewal_request_id', p_renewal_request_id::text,
            'business_date', p_business_date,
            'old_loan_settlement_amount', settlement_amount,
            'external_reference', normalized_reference,
            'journal_lines_enabled', false,
            'automatic_source_posting', false
        )
    );

    RETURN created_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.void_loan_renewal_execution_evidence(
    p_event_id UUID,
    p_actor_user_id UUID,
    p_reason TEXT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    event_row lending.loan_renewal_execution_events%ROWTYPE;
    normalized_reason TEXT := btrim(coalesce(p_reason, ''));
BEGIN
    IF length(normalized_reason) < 3 THEN
        RAISE EXCEPTION 'Enter a clear reason for voiding renewal execution evidence.';
    END IF;

    SELECT *
    INTO event_row
    FROM lending.loan_renewal_execution_events event
    WHERE event.id = p_event_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Renewal execution evidence was not found.';
    END IF;
    IF event_row.is_voided THEN
        RAISE EXCEPTION 'Renewal execution evidence was already voided.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM accounting.journal_entries journal
        WHERE journal.source_event_key = 'loan_renewal_execution:' || event_row.id::text
           OR journal.source_event_key = 'loan_disbursement:' || event_row.disbursement_event_id::text
           OR (
               journal.source_reference = event_row.id::text
               AND journal.source_type = 'loan_renewal_execution'
           )
    ) THEN
        RAISE EXCEPTION 'Renewal execution evidence already has accounting journal history; use the future protected accounting cancellation/reversal path.';
    END IF;

    PERFORM set_config('lending.loan_renewal_execution_void_allowed', 'on', true);
    UPDATE lending.loan_renewal_execution_events
    SET
        is_voided = true,
        voided_by_user_id = p_actor_user_id,
        voided_at = now(),
        void_reason = normalized_reason
    WHERE id = p_event_id;
    PERFORM set_config('lending.loan_renewal_execution_void_allowed', 'off', true);

    INSERT INTO core.audit_logs (
        actor_user_id,
        action,
        target_type,
        target_id,
        details
    )
    VALUES (
        p_actor_user_id,
        'accounting.loan_renewal_execution_evidence.voided',
        'loan_renewal_execution_event',
        p_event_id,
        jsonb_build_object(
            'old_loan_id', event_row.old_loan_id::text,
            'new_loan_id', event_row.new_loan_id::text,
            'disbursement_event_id', event_row.disbursement_event_id::text,
            'reason', normalized_reason,
            'journal_lines_enabled', false,
            'automatic_source_posting', false
        )
    );
END;
$$;

CREATE OR REPLACE VIEW accounting.loan_renewal_execution_source_readiness AS
SELECT
    release_event.id AS disbursement_event_id,
    release_event.loan_id AS new_loan_id,
    new_loan.loan_number AS new_loan_number,
    execution.id AS renewal_execution_event_id,
    execution.old_loan_id,
    old_loan.loan_number AS old_loan_number,
    release_event.client_id,
    client.client_code,
    client.full_name AS client_name,
    execution.renewal_request_id,
    request.status AS renewal_request_status,
    new_type.code AS new_loan_type_code,
    new_type.name AS new_loan_type_name,
    new_type.calculation_mode AS new_loan_calculation_mode,
    new_loan.principal AS new_loan_principal,
    old_loan.principal AS old_loan_principal,
    release_event.business_date AS release_business_date,
    release_event.disbursed_at,
    release_event.cash_disbursed_amount,
    release_event.settlement_amount,
    release_event.other_deduction_amount,
    release_event.funding_account_system_key,
    release_event.external_reference AS release_external_reference,
    execution.business_date AS execution_business_date,
    execution.executed_at,
    execution.old_loan_settlement_amount,
    execution.external_reference AS execution_external_reference,
    CASE
        WHEN execution.id IS NULL
            THEN 'missing_renewal_execution_evidence'
        WHEN execution.old_loan_id = execution.new_loan_id
            THEN 'invalid_same_loan_linkage'
        WHEN execution.new_loan_id IS DISTINCT FROM release_event.loan_id
          OR execution.disbursement_event_id IS DISTINCT FROM release_event.id
            THEN 'release_linkage_mismatch'
        WHEN execution.client_id IS DISTINCT FROM release_event.client_id
          OR old_loan.client_id IS DISTINCT FROM release_event.client_id
          OR new_loan.client_id IS DISTINCT FROM release_event.client_id
            THEN 'client_mismatch'
        WHEN execution.business_date IS DISTINCT FROM release_event.business_date
            THEN 'execution_date_mismatch'
        WHEN execution.old_loan_settlement_amount IS DISTINCT FROM release_event.settlement_amount
            THEN 'settlement_mismatch'
        WHEN execution.old_loan_principal_snapshot IS DISTINCT FROM old_loan.principal
          OR execution.old_loan_date_released_snapshot IS DISTINCT FROM old_loan.date_released
          OR execution.new_loan_principal_snapshot IS DISTINCT FROM new_loan.principal
          OR execution.new_loan_date_released_snapshot IS DISTINCT FROM new_loan.date_released
            THEN 'loan_changed_after_execution_evidence'
        WHEN release_event.principal_snapshot IS DISTINCT FROM new_loan.principal
          OR release_event.date_released_snapshot IS DISTINCT FROM new_loan.date_released
            THEN 'new_loan_changed_after_disbursement_evidence'
        WHEN release_event.business_date IS DISTINCT FROM new_loan.date_released
            THEN 'release_date_mismatch'
        WHEN round(
            release_event.cash_disbursed_amount
            + release_event.settlement_amount
            + release_event.other_deduction_amount,
            2
        ) IS DISTINCT FROM round(release_event.principal_snapshot, 2)
            THEN 'unreconciled_release_components'
        WHEN execution.renewal_request_id IS NOT NULL
             AND (
                 request.id IS NULL
                 OR request.status <> 'approved'
                 OR request.client_id IS DISTINCT FROM execution.client_id
                 OR request.loan_id IS DISTINCT FROM execution.old_loan_id
             )
            THEN 'renewal_request_mismatch'
        WHEN release_event.other_deduction_amount <> 0
            THEN 'deduction_policy_review'
        WHEN new_type.calculation_mode = 'seven_by_seven'
            THEN 'seven_by_seven_policy_review'
        WHEN new_type.calculation_mode <> 'fixed_daily'
            THEN 'loan_type_policy_review'
        ELSE 'renewal_execution_evidence_ready'
    END AS readiness_status,
    CASE
        WHEN execution.id IS NULL THEN NULL
        ELSE 'loan_renewal_execution:' || execution.id::text
    END AS source_event_key,
    false AS journal_lines_enabled,
    false AS automatic_source_posting
FROM lending.loan_disbursement_events release_event
JOIN lending.loans new_loan
  ON new_loan.id = release_event.loan_id
JOIN lending.clients client
  ON client.id = release_event.client_id
JOIN lending.loan_types new_type
  ON new_type.id = new_loan.loan_type_id
LEFT JOIN lending.loan_renewal_execution_events execution
  ON execution.disbursement_event_id = release_event.id
 AND execution.is_voided = false
LEFT JOIN lending.loans old_loan
  ON old_loan.id = execution.old_loan_id
LEFT JOIN lending.client_renewal_requests request
  ON request.id = execution.renewal_request_id
WHERE release_event.event_kind = 'renewal_release'
  AND release_event.is_voided = false;

COMMENT ON TABLE lending.loan_renewal_execution_events IS
    'Immutable authoritative evidence linking one old loan to one new loan for an executed renewal. Client renewal requests and loan rows alone are never treated as execution proof. Loan status snapshots are audit context only; ordinary later lifecycle status changes do not invalidate the execution evidence.';
COMMENT ON VIEW accounting.loan_renewal_execution_source_readiness IS
    'Evidence-only renewal execution readiness. This stage never creates journal lines and never enables automatic source posting.';
COMMENT ON FUNCTION lending.guard_linked_renewal_release_void() IS
    'Prevents authoritative renewal release evidence from being voided while active renewal execution evidence still depends on it.';
COMMENT ON FUNCTION accounting.record_loan_renewal_execution_evidence(
    UUID, UUID, UUID, UUID, DATE, TIMESTAMPTZ, NUMERIC, TEXT, TEXT, UUID
) IS
    'Protected Management evidence registration for executed renewals. It requires an active renewal_release disbursement event, exact old-loan settlement linkage, same-client old/new loans, and optional approved client request linkage. It does not create journals.';
COMMENT ON FUNCTION accounting.void_loan_renewal_execution_evidence(UUID, UUID, TEXT) IS
    'Protected evidence-only void. It preserves the original row and refuses to void after accounting journal history exists.';

COMMIT;
