BEGIN;

-- Master #296 A5 hardening: once a loan has been fully derecognized by the
-- protected A5 write-off path, no later A3 measurement, A4 allowance lifecycle,
-- A5 remeasurement, or normal Regular/7x7 collection accounting may recreate
-- a receivable or allowance. Later protected same-loan cash belongs only to the
-- A5 post-write-off recovery path. Automatic source posting remains disabled.

CREATE OR REPLACE FUNCTION accounting.guard_ecl_post_writeoff_loan_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM accounting.ecl_accounting_writeoffs writeoff
        WHERE writeoff.loan_id = NEW.loan_id
    ) THEN
        RAISE EXCEPTION 'Loan has been fully written off. New ECL measurement/allowance activity is blocked; later protected cash must use the A5 post-write-off recovery path.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_ecl_post_writeoff_measurement_guard
    ON accounting.ecl_quantitative_measurements;
CREATE TRIGGER accounting_ecl_post_writeoff_measurement_guard
BEFORE INSERT ON accounting.ecl_quantitative_measurements
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_post_writeoff_loan_insert();

DROP TRIGGER IF EXISTS accounting_ecl_post_writeoff_allowance_preparation_guard
    ON accounting.ecl_allowance_draft_preparations;
CREATE TRIGGER accounting_ecl_post_writeoff_allowance_preparation_guard
BEFORE INSERT ON accounting.ecl_allowance_draft_preparations
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_post_writeoff_loan_insert();

DROP TRIGGER IF EXISTS accounting_ecl_post_writeoff_allowance_posting_guard
    ON accounting.ecl_allowance_postings;
CREATE TRIGGER accounting_ecl_post_writeoff_allowance_posting_guard
BEFORE INSERT ON accounting.ecl_allowance_postings
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_post_writeoff_loan_insert();

DROP TRIGGER IF EXISTS accounting_ecl_post_writeoff_remeasurement_guard
    ON accounting.ecl_allowance_remeasurements;
CREATE TRIGGER accounting_ecl_post_writeoff_remeasurement_guard
BEFORE INSERT ON accounting.ecl_allowance_remeasurements
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_post_writeoff_loan_insert();

CREATE OR REPLACE FUNCTION accounting.guard_ecl_post_writeoff_collection_accounting()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_loan_id UUID;
BEGIN
    SELECT transaction_row.loan_id
      INTO target_loan_id
    FROM lending.collection_transactions transaction_row
    WHERE transaction_row.id = NEW.transaction_id;

    IF target_loan_id IS NOT NULL AND EXISTS (
        SELECT 1
        FROM accounting.ecl_accounting_writeoffs writeoff
        WHERE writeoff.loan_id = target_loan_id
    ) THEN
        RAISE EXCEPTION 'Loan has been fully written off. Normal Regular/7x7 collection accounting is blocked; later protected cash must use the A5 post-write-off recovery path.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_ecl_post_writeoff_regular_collection_guard
    ON accounting.regular_journal_posting_entries;
CREATE TRIGGER accounting_ecl_post_writeoff_regular_collection_guard
BEFORE INSERT ON accounting.regular_journal_posting_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_post_writeoff_collection_accounting();

DROP TRIGGER IF EXISTS accounting_ecl_post_writeoff_7x7_collection_guard
    ON accounting.seven_by_seven_journal_postings;
CREATE TRIGGER accounting_ecl_post_writeoff_7x7_collection_guard
BEFORE INSERT ON accounting.seven_by_seven_journal_postings
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_post_writeoff_collection_accounting();

COMMIT;
