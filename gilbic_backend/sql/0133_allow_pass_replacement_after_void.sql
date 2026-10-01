BEGIN;

-- Retain voided receipts and their idempotency evidence while reserving each
-- loan/date slot only for an active Unable-to-pay entry. Run transactionally
-- with the ordinary migration runner so no unconstrained write gap is exposed.
drop index if exists lending.lending_collection_one_pass_per_day_uidx;

create unique index lending_collection_one_pass_per_day_uidx
    on lending.collection_transactions (loan_id, collection_date)
    where entry_type = 'pass' and is_voided = false;

COMMIT;
