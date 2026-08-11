BEGIN;

-- Stage 5D.18 relies on the operational collection-void snapshot as the
-- immutable bridge between the borrower/loan correction and its accounting
-- reversal. Migration 0017 documented this table as append-only but did not yet
-- enforce that promise at the database boundary.
CREATE OR REPLACE FUNCTION lending.guard_collection_transaction_void_audit_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Collection void audit records are immutable.';
END;
$$;

DROP TRIGGER IF EXISTS lending_collection_transaction_void_audit_guard
    ON lending.collection_transaction_voids;
CREATE TRIGGER lending_collection_transaction_void_audit_guard
BEFORE UPDATE OR DELETE ON lending.collection_transaction_voids
FOR EACH ROW EXECUTE FUNCTION lending.guard_collection_transaction_void_audit_immutability();

-- Every operational false -> true void transition, accounted or not, must agree
-- exactly with the append-only void evidence inserted immediately before it in
-- the same PostgreSQL transaction. This closes direct-SQL/timestamp drift paths
-- before any accounting reversal is attempted.
CREATE OR REPLACE FUNCTION accounting.guard_collection_void_transition_evidence()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    void_record lending.collection_transaction_voids%ROWTYPE;
BEGIN
    IF OLD.is_voided = false AND NEW.is_voided = true THEN
        IF NEW.voided_at IS NULL
           OR NEW.voided_by_user_id IS NULL
           OR btrim(coalesce(NEW.void_reason, '')) = '' THEN
            RAISE EXCEPTION 'A collection void requires actor, reason, and timestamp evidence.';
        END IF;

        SELECT *
        INTO void_record
        FROM lending.collection_transaction_voids evidence
        WHERE evidence.transaction_id = OLD.id
        FOR SHARE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'A collection cannot be voided without immutable collection-void evidence.';
        END IF;

        IF void_record.voided_by_user_id IS DISTINCT FROM NEW.voided_by_user_id
           OR btrim(void_record.reason) IS DISTINCT FROM btrim(NEW.void_reason)
           OR void_record.voided_at IS DISTINCT FROM NEW.voided_at THEN
            RAISE EXCEPTION 'Collection void state does not exactly match its immutable void evidence.';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

-- PostgreSQL executes same-timing/event triggers alphabetically. Evidence must
-- be proven first, then the accounting reversal may be created, then the
-- accounted-source fail-closed guard from migration 0043 verifies completion.
DROP TRIGGER IF EXISTS accounting_00_regular_collection_void_reversal
    ON lending.collection_transactions;
DROP TRIGGER IF EXISTS accounting_00_collection_void_evidence_guard
    ON lending.collection_transactions;
DROP TRIGGER IF EXISTS accounting_01_regular_collection_void_reversal
    ON lending.collection_transactions;

CREATE TRIGGER accounting_00_collection_void_evidence_guard
BEFORE UPDATE OF is_voided ON lending.collection_transactions
FOR EACH ROW EXECUTE FUNCTION accounting.guard_collection_void_transition_evidence();

CREATE TRIGGER accounting_01_regular_collection_void_reversal
BEFORE UPDATE OF is_voided ON lending.collection_transactions
FOR EACH ROW EXECUTE FUNCTION accounting.perform_controlled_regular_collection_void_reversal();

COMMENT ON TABLE lending.collection_transaction_voids IS
    'Append-only immutable snapshots and balance-restoration evidence for Management collection voids.';

COMMIT;
