BEGIN;

DROP INDEX IF EXISTS lending.lending_client_renewal_one_pending_uidx;

CREATE UNIQUE INDEX IF NOT EXISTS lending_client_renewal_one_open_uidx
    ON lending.client_renewal_requests (client_id, loan_id)
    WHERE status IN ('pending', 'approved');

COMMIT;
