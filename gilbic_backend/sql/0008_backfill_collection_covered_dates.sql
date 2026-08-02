BEGIN;

INSERT INTO lending.collection_covered_dates (
    transaction_id,
    loan_id,
    covered_date
)
SELECT
    transaction.id,
    transaction.loan_id,
    covered_day::date
FROM lending.collection_transactions AS transaction
CROSS JOIN LATERAL generate_series(
    CASE
        WHEN transaction.entry_type = 'payment'
            THEN transaction.collection_date
        ELSE coalesce(transaction.advance_from, transaction.collection_date)
    END::timestamp,
    CASE
        WHEN transaction.entry_type = 'payment'
            THEN transaction.collection_date
        ELSE coalesce(transaction.advance_until, transaction.collection_date)
    END::timestamp,
    interval '1 day'
) AS covered_day
WHERE transaction.entry_type IN ('payment', 'advance')
ON CONFLICT DO NOTHING;

COMMIT;
