BEGIN;

-- Slice 2: the Collector no longer chooses exact future covered dates for a
-- normal Regular payment. After Past Due and Due Today are satisfied, a
-- borrower-directed Advance is applied automatically to the oldest future
-- contractual obligation first. Keep the historical exact_covered_date basis
-- for old receipts and explicit legacy ADV evidence.
ALTER TABLE lending.loan_installment_payment_allocations
    DROP CONSTRAINT IF EXISTS loan_installment_payment_allocations_allocation_basis_check;

ALTER TABLE lending.loan_installment_payment_allocations
    ADD CONSTRAINT loan_installment_payment_allocations_allocation_basis_check
    CHECK (
        allocation_basis IN (
            'exact_covered_date',
            'oldest_due_first',
            'voluntary_extra_tail',
            'future_advance_oldest_first',
            'contract_reference',
            'manual_review'
        )
    );

COMMENT ON COLUMN lending.loan_installment_payment_allocations.allocation_basis IS
    'Protected allocation purpose. future_advance_oldest_first is borrower-directed Regular Advance applied to the oldest unpaid future contractual obligation; voluntary_extra_tail remains the historical label for explicit Principal Reduction from the contractual tail.';

COMMIT;
