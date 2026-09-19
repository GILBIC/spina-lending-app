BEGIN;

-- Existing collections and historical/no-CIF Clients keep their existing
-- authorities. Only new credit transitions for CIF-enrolled Clients are gated.
CREATE OR REPLACE FUNCTION lending.require_current_cif_for_new_credit(p_client_id UUID)
RETURNS VOID
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
DECLARE
    client_status TEXT;
    current_cif lending.client_cif_versions%ROWTYPE;
    checked_at TIMESTAMPTZ;
BEGIN
    -- Serialize against initial CIF creation and successor/activation work.
    SELECT status INTO client_status
    FROM lending.clients WHERE id = p_client_id FOR UPDATE;

    IF NOT EXISTS (
        SELECT 1 FROM lending.client_cif_versions WHERE client_id = p_client_id
    ) THEN
        RETURN;
    END IF;

    BEGIN
        -- Some existing CIF writers lock CIF before Client. Fail closed on
        -- contention instead of waiting in the reverse lock order. A fresh
        -- request can re-read the completed change; no write is auto-replayed.
        SELECT * INTO current_cif
        FROM lending.client_cif_versions
        WHERE client_id = p_client_id AND is_current
        FOR SHARE NOWAIT;
    EXCEPTION WHEN lock_not_available THEN
        RAISE EXCEPTION 'CIF review is changing; refresh before approving or releasing new credit.'
            USING ERRCODE = '23514', CONSTRAINT = 'client_cif_new_credit_ready';
    END;

    checked_at := clock_timestamp();
    IF client_status IS DISTINCT FROM 'active'
       OR current_cif.id IS NULL
       OR current_cif.status IS DISTINCT FROM 'active'
       OR current_cif.activated_at IS NULL
       OR current_cif.activated_at > checked_at
       OR current_cif.expires_at IS NULL
       OR current_cif.expires_at <= checked_at
       OR current_cif.reverification_required_at IS NOT NULL
       OR current_cif.baseline_liveness_status IS DISTINCT FROM 'passed'
       OR btrim(coalesce(current_cif.baseline_face_scan_evidence_reference, '')) = '' THEN
        RAISE EXCEPTION 'New credit cannot be approved or released until the current CIF is active, valid and any required re-verification is complete.'
            USING ERRCODE = '23514', CONSTRAINT = 'client_cif_new_credit_ready';
    END IF;
    -- review_due_at alone is the non-blocking 90-day review reminder.
END;
$$;

CREATE OR REPLACE FUNCTION lending.guard_new_loan_cif_readiness()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status IN ('approved', 'active') THEN
            PERFORM lending.require_current_cif_for_new_credit(NEW.client_id);
        END IF;
    ELSIF (OLD.status IS DISTINCT FROM 'approved' AND NEW.status = 'approved')
       OR (OLD.status IN ('draft', 'approved', 'cancelled') AND NEW.status = 'active')
       OR (OLD.date_released IS NULL AND NEW.date_released IS NOT NULL)
       OR (OLD.client_id IS DISTINCT FROM NEW.client_id AND NEW.status IN ('approved', 'active')) THEN
        PERFORM lending.require_current_cif_for_new_credit(NEW.client_id);
    END IF;
    -- Existing paid/defaulted -> active servicing corrections are not approvals.
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_new_loan_cif_readiness ON lending.loans;
CREATE TRIGGER lending_new_loan_cif_readiness
BEFORE INSERT OR UPDATE OF status, date_released, client_id ON lending.loans
FOR EACH ROW EXECUTE FUNCTION lending.guard_new_loan_cif_readiness();

CREATE OR REPLACE FUNCTION lending.guard_renewal_cif_readiness()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status = 'approved'
           OR NEW.cash_released_to_collector_at IS NOT NULL
           OR NEW.cash_given_to_client_at IS NOT NULL
           OR NEW.activation_status = 'active' THEN
            PERFORM lending.require_current_cif_for_new_credit(NEW.client_id);
        END IF;
    ELSIF (OLD.status IS DISTINCT FROM 'approved' AND NEW.status = 'approved')
       OR (OLD.cash_released_to_collector_at IS NULL AND NEW.cash_released_to_collector_at IS NOT NULL)
       OR (OLD.cash_given_to_client_at IS NULL AND NEW.cash_given_to_client_at IS NOT NULL)
       OR (OLD.activation_status IS DISTINCT FROM 'active' AND NEW.activation_status = 'active')
       OR (OLD.client_id IS DISTINCT FROM NEW.client_id AND NEW.status = 'approved') THEN
        PERFORM lending.require_current_cif_for_new_credit(NEW.client_id);
    END IF;
    -- Receipt acknowledgments, proof review, rejection and cancellation remain
    -- available for cash already handed over; they do not issue new credit.
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_renewal_cif_readiness ON lending.client_renewal_requests;
CREATE TRIGGER lending_renewal_cif_readiness
BEFORE INSERT OR UPDATE OF status, cash_released_to_collector_at,
    cash_given_to_client_at, activation_status, client_id
ON lending.client_renewal_requests
FOR EACH ROW EXECUTE FUNCTION lending.guard_renewal_cif_readiness();

CREATE OR REPLACE FUNCTION lending.guard_credit_execution_cif_readiness()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    PERFORM lending.require_current_cif_for_new_credit(NEW.client_id);
    RETURN NEW;
END;
$$;

-- Existing protected financial functions remain the only write authorities.
-- Their exact idempotent retries return stored events before reaching INSERT;
-- void/reconciliation updates are intentionally outside these new gates.
DROP TRIGGER IF EXISTS lending_disbursement_cif_readiness ON lending.loan_disbursement_events;
CREATE TRIGGER lending_disbursement_cif_readiness
BEFORE INSERT ON lending.loan_disbursement_events
FOR EACH ROW EXECUTE FUNCTION lending.guard_credit_execution_cif_readiness();

DROP TRIGGER IF EXISTS lending_renewal_execution_cif_readiness ON lending.loan_renewal_execution_events;
CREATE TRIGGER lending_renewal_execution_cif_readiness
BEFORE INSERT ON lending.loan_renewal_execution_events
FOR EACH ROW EXECUTE FUNCTION lending.guard_credit_execution_cif_readiness();

REVOKE EXECUTE ON FUNCTION lending.require_current_cif_for_new_credit(UUID) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION lending.guard_new_loan_cif_readiness() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION lending.guard_renewal_cif_readiness() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION lending.guard_credit_execution_cif_readiness() FROM PUBLIC;

COMMIT;
