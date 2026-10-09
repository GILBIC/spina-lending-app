BEGIN;

-- Credit and cash-refund evidence are separate immutable tables, but consume
-- the same exact posted Tax Recoverable. Their original mode-specific locks
-- cannot serialize that shared source. Guard both INSERT boundaries without
-- replacing the protected owners or changing their authorization, evidence,
-- derived amounts, idempotency, preparation or posting rules.
-- Take both table locks before installing the guards, so in-flight evidence
-- writers finish before the new boundary becomes visible atomically.
LOCK TABLE accounting.v1_tax_recoverable_credit_evidence,
    accounting.v1_tax_recoverable_refund_evidence IN SHARE ROW EXCLUSIVE MODE;

CREATE OR REPLACE FUNCTION accounting.guard_v1_tax_recoverable_realization()
RETURNS trigger
LANGUAGE plpgsql
VOLATILE
SET search_path = pg_catalog
AS $$
BEGIN
    -- A fresh opposite-evidence query after the wait must see the winner's
    -- commit. A pre-existing repeatable-read snapshot cannot provide that.
    -- Exact idempotent reads still return through the existing owner functions.
    IF current_setting('transaction_isolation') <> 'read committed' THEN
        RAISE EXCEPTION 'Tax Recoverable realization evidence requires a READ COMMITTED transaction.'
            USING ERRCODE = '23514';
    END IF;

    -- One transaction lock per authoritative adjustment posting, independent
    -- of realization mode, target return, evidence UUID or idempotency key.
    -- Do not upgrade the owners' existing FOR SHARE row locks here: concurrent
    -- upgrades could deadlock before either owner can finish its evidence.
    PERFORM pg_advisory_xact_lock(
        hashtextextended('v1-tax-recoverable-realization:' || NEW.adjustment_posting_id::text, 0)
    );

    -- These are separate statements after lock admission. VOLATILE under
    -- READ COMMITTED obtains a fresh snapshot, including a competing commit
    -- that occurred while this INSERT was waiting.
    IF TG_TABLE_NAME = 'v1_tax_recoverable_credit_evidence' THEN
        IF EXISTS (
            SELECT 1 FROM accounting.v1_tax_recoverable_refund_evidence refund
            WHERE refund.adjustment_posting_id = NEW.adjustment_posting_id
        ) THEN
            RAISE EXCEPTION 'This exact Tax Recoverable already has immutable cash-refund evidence and cannot also be applied as a tax credit.'
                USING ERRCODE = '23514';
        END IF;
    ELSIF TG_TABLE_NAME = 'v1_tax_recoverable_refund_evidence' THEN
        IF EXISTS (
            SELECT 1 FROM accounting.v1_tax_recoverable_credit_evidence credit
            WHERE credit.adjustment_posting_id = NEW.adjustment_posting_id
        ) THEN
            RAISE EXCEPTION 'This exact Tax Recoverable is reserved for protected tax-credit application; refund evidence would duplicate realization.'
                USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_v1_tax_recoverable_realization_guard
    ON accounting.v1_tax_recoverable_credit_evidence;
CREATE TRIGGER accounting_v1_tax_recoverable_realization_guard
BEFORE INSERT ON accounting.v1_tax_recoverable_credit_evidence
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_recoverable_realization();

DROP TRIGGER IF EXISTS accounting_v1_tax_recoverable_realization_guard
    ON accounting.v1_tax_recoverable_refund_evidence;
CREATE TRIGGER accounting_v1_tax_recoverable_realization_guard
BEFORE INSERT ON accounting.v1_tax_recoverable_refund_evidence
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_recoverable_realization();

REVOKE ALL ON FUNCTION accounting.guard_v1_tax_recoverable_realization() FROM PUBLIC;
DO $$
DECLARE
    client_role TEXT;
BEGIN
    FOR client_role IN
        SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated', 'service_role')
    LOOP
        EXECUTE format(
            'REVOKE ALL ON FUNCTION accounting.guard_v1_tax_recoverable_realization() FROM %I',
            client_role
        );
    END LOOP;
END;
$$;

COMMENT ON FUNCTION accounting.guard_v1_tax_recoverable_realization() IS
'Serializes new full Tax Recoverable credit/refund evidence by exact adjustment posting under READ COMMITTED. Existing immutable evidence and journals are not rewritten; pre-existing conflicting evidence requires separate accounting review.';

COMMIT;
