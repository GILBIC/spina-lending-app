BEGIN;

-- Master Issue #296 A1 hardening.
-- Migration 0070 accepted same-calendar-day cash recovery based on
-- collection_date alone. Recovery evidence must instead be strictly later than
-- the prior deteriorated Management review by the authoritative server
-- accepted_at timestamp. Keep this as a new migration so already-installed
-- 0070 databases receive the hardening without rewriting migration history.

CREATE OR REPLACE FUNCTION accounting.guard_ecl_cash_recovery_chronology()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    prior_review accounting.ecl_credit_risk_label_reviews%ROWTYPE;
    recovery_tx lending.collection_transactions%ROWTYPE;
BEGIN
    IF NEW.recovery_label <> 'cash_recovery_observed' THEN
        RETURN NEW;
    END IF;

    IF NEW.supersedes_review_id IS NULL OR NEW.recovery_transaction_id IS NULL THEN
        RAISE EXCEPTION 'Cash-recovery chronology requires the exact prior deteriorated review and protected recovery transaction.';
    END IF;

    SELECT *
    INTO prior_review
    FROM accounting.ecl_credit_risk_label_reviews review
    WHERE review.id = NEW.supersedes_review_id;

    IF prior_review.id IS NULL
       OR prior_review.loan_id <> NEW.loan_id
       OR NOT (
            prior_review.default_label
            OR prior_review.stage_label = 'stage_3_credit_impaired'
            OR prior_review.write_off_label = 'supported_no_reasonable_expectation_of_recovery'
       ) THEN
        RAISE EXCEPTION 'Cash-recovery chronology requires the immediately prior deteriorated review for the same loan.';
    END IF;

    SELECT *
    INTO recovery_tx
    FROM lending.collection_transactions transaction
    WHERE transaction.id = NEW.recovery_transaction_id;

    IF recovery_tx.id IS NULL
       OR recovery_tx.loan_id <> NEW.loan_id
       OR recovery_tx.is_voided
       OR recovery_tx.amount <= 0
       OR recovery_tx.entry_type NOT IN ('payment', 'advance')
       OR recovery_tx.accepted_at IS NULL
       OR recovery_tx.accepted_at <= prior_review.created_at THEN
        RAISE EXCEPTION 'Recovery transaction must be a later non-voided positive protected collection accepted after the prior deteriorated review.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS ecl_cash_recovery_chronology_guard
    ON accounting.ecl_credit_risk_label_reviews;
CREATE TRIGGER ecl_cash_recovery_chronology_guard
BEFORE INSERT ON accounting.ecl_credit_risk_label_reviews
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_cash_recovery_chronology();

COMMENT ON FUNCTION accounting.guard_ecl_cash_recovery_chronology() IS
    'Fail-closed ECL cash-recovery evidence guard. The exact same-loan protected positive collection must have an authoritative accepted_at timestamp strictly later than the prior deteriorated Management review; same-calendar-day ordering is never inferred.';

COMMIT;
