BEGIN;

-- Priority #6: preserve the approved product invariant that one Client may
-- have at most one active 7x7 loan, while an active Regular loan may coexist.
-- Existing duplicate active 7x7 state is not guessed or auto-repaired.
DO $$
BEGIN
    IF EXISTS (
        SELECT loan.client_id
        FROM lending.loans AS loan
        JOIN lending.loan_types AS loan_type
          ON loan_type.id = loan.loan_type_id
        WHERE loan.status = 'active'
          AND loan_type.calculation_mode = 'seven_by_seven'
        GROUP BY loan.client_id
        HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION
            'Priority #6 one-active-7x7 invariant cannot be installed: duplicate active seven_by_seven loans already exist for at least one client.';
    END IF;
END
$$;

CREATE OR REPLACE FUNCTION lending.guard_one_active_seven_by_seven_loan()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    new_calculation_mode TEXT;
    conflicting_loan_id UUID;
BEGIN
    -- Serialize the invariant per Client so concurrent activation/creation
    -- attempts cannot both pass the check.
    PERFORM pg_advisory_xact_lock(
        hashtextextended(
            'lending.one-active-seven-by-seven:' || NEW.client_id::text,
            0
        )
    );

    SELECT loan_type.calculation_mode
    INTO new_calculation_mode
    FROM lending.loan_types AS loan_type
    WHERE loan_type.id = NEW.loan_type_id;

    -- The existing FK remains authoritative for a missing loan type. This
    -- guard applies only to an active seven_by_seven loan.
    IF NEW.status <> 'active'
       OR new_calculation_mode IS DISTINCT FROM 'seven_by_seven' THEN
        RETURN NEW;
    END IF;

    SELECT loan.id
    INTO conflicting_loan_id
    FROM lending.loans AS loan
    JOIN lending.loan_types AS loan_type
      ON loan_type.id = loan.loan_type_id
    WHERE loan.client_id = NEW.client_id
      AND loan.status = 'active'
      AND loan_type.calculation_mode = 'seven_by_seven'
      AND loan.id <> NEW.id
    ORDER BY loan.id
    LIMIT 1;

    IF conflicting_loan_id IS NOT NULL THEN
        RAISE EXCEPTION
            'Client % already has active seven_by_seven loan %; a second active 7x7 loan is not allowed.',
            NEW.client_id,
            conflicting_loan_id
            USING ERRCODE = '23505';
    END IF;

    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS lending_one_active_seven_by_seven_loan_guard
    ON lending.loans;
CREATE TRIGGER lending_one_active_seven_by_seven_loan_guard
BEFORE INSERT OR UPDATE OF client_id, loan_type_id, status ON lending.loans
FOR EACH ROW
EXECUTE FUNCTION lending.guard_one_active_seven_by_seven_loan();

COMMIT;
