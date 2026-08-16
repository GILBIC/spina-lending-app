BEGIN;

-- Voluntary extra is not ADV. It reduces the contractual balance from the tail
-- while leaving the next normal collection date due. Keep the existing
-- allocation table and extend its protected basis vocabulary rather than
-- creating a second balance ledger.
ALTER TABLE lending.loan_installment_payment_allocations
    DROP CONSTRAINT IF EXISTS loan_installment_payment_allocations_allocation_basis_check;

ALTER TABLE lending.loan_installment_payment_allocations
    ADD CONSTRAINT loan_installment_payment_allocations_allocation_basis_check
    CHECK (
        allocation_basis IN (
            'exact_covered_date',
            'oldest_due_first',
            'voluntary_extra_tail',
            'contract_reference',
            'manual_review'
        )
    );

COMMENT ON COLUMN lending.loan_installment_payment_allocations.allocation_basis IS
    'Allocation purpose. voluntary_extra_tail means borrower-chosen extra cash that shortens the remaining term from the tail and is not ADV / a future covered-date instruction.';

COMMIT;
