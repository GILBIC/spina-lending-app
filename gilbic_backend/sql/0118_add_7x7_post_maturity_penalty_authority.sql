BEGIN;

-- Priority #6 Slice 6 establishes only the durable authority/evidence boundary
-- needed by the approved 7x7 post-maturity penalty design. This migration does
-- not calculate or accrue a penalty, create daily accrual rows, post accounting
-- entries, decide tax/EIR treatment, or retroactively charge legacy loans.

ALTER TABLE lending.seven_by_seven_pricing_compliance_reviews
    ADD COLUMN IF NOT EXISTS penalty_policy_version TEXT,
    ADD COLUMN IF NOT EXISTS penalty_monthly_rate NUMERIC(9,6),
    ADD COLUMN IF NOT EXISTS penalty_proration_days INTEGER,
    ADD COLUMN IF NOT EXISTS penalty_rate_ceiling NUMERIC(9,6),
    ADD COLUMN IF NOT EXISTS lifetime_nonprincipal_cost_ceiling NUMERIC(18,2),
    ADD COLUMN IF NOT EXISTS counted_nonprincipal_cost_at_contract_lock NUMERIC(18,2);

ALTER TABLE lending.seven_by_seven_pricing_compliance_reviews
    DROP CONSTRAINT IF EXISTS lending_7x7_pricing_compliance_penalty_authority_check;
ALTER TABLE lending.seven_by_seven_pricing_compliance_reviews
    ADD CONSTRAINT lending_7x7_pricing_compliance_penalty_authority_check
    CHECK (
        (
            penalty_policy_version IS NULL
            AND penalty_monthly_rate IS NULL
            AND penalty_proration_days IS NULL
            AND penalty_rate_ceiling IS NULL
            AND lifetime_nonprincipal_cost_ceiling IS NULL
            AND counted_nonprincipal_cost_at_contract_lock IS NULL
        )
        OR
        (
            penalty_policy_version IS NOT NULL
            AND btrim(penalty_policy_version) <> ''
            AND penalty_monthly_rate = 0.030000
            AND penalty_proration_days = 30
            AND penalty_rate_ceiling IS NOT NULL
            AND penalty_rate_ceiling > 0
            AND lifetime_nonprincipal_cost_ceiling IS NOT NULL
            AND lifetime_nonprincipal_cost_ceiling >= 0
            AND counted_nonprincipal_cost_at_contract_lock IS NOT NULL
            AND counted_nonprincipal_cost_at_contract_lock >= 0
            AND counted_nonprincipal_cost_at_contract_lock
                <= lifetime_nonprincipal_cost_ceiling
        )
    );

CREATE TABLE IF NOT EXISTS lending.seven_by_seven_penalty_assessments (
    id BIGSERIAL PRIMARY KEY,
    loan_id UUID NOT NULL
        REFERENCES lending.loans(id) ON DELETE RESTRICT,
    schedule_id UUID NOT NULL
        REFERENCES lending.loan_contract_schedules(id) ON DELETE RESTRICT,
    pricing_compliance_review_id BIGINT NOT NULL
        REFERENCES lending.seven_by_seven_pricing_compliance_reviews(id)
        ON DELETE RESTRICT,
    terms_fingerprint TEXT NOT NULL
        CHECK (terms_fingerprint ~ '^[0-9a-f]{64}$'),
    assessment_start_date DATE NOT NULL,
    assessed_through_date DATE NOT NULL,
    opening_penalty_base NUMERIC(18,2) NOT NULL
        CHECK (opening_penalty_base >= 0),
    calculation_evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    contractual_monthly_rate NUMERIC(9,6) NOT NULL
        CHECK (contractual_monthly_rate > 0),
    legal_rate_ceiling NUMERIC(9,6) NOT NULL
        CHECK (legal_rate_ceiling > 0),
    effective_monthly_rate NUMERIC(9,6) NOT NULL
        CHECK (
            effective_monthly_rate > 0
            AND effective_monthly_rate <= contractual_monthly_rate
            AND effective_monthly_rate <= legal_rate_ceiling
        ),
    penalty_proration_days INTEGER NOT NULL
        CHECK (penalty_proration_days > 0),
    theoretical_penalty_exact NUMERIC(30,12) NOT NULL
        CHECK (theoretical_penalty_exact >= 0),
    opening_cost_headroom NUMERIC(18,2) NOT NULL
        CHECK (opening_cost_headroom >= 0),
    assessed_penalty_amount NUMERIC(18,2) NOT NULL
        CHECK (assessed_penalty_amount > 0),
    source_transaction_id UUID NOT NULL
        REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (assessment_start_date <= assessed_through_date),
    CHECK (assessed_penalty_amount <= opening_cost_headroom),
    UNIQUE (loan_id, assessed_through_date),
    UNIQUE (source_transaction_id)
);

CREATE INDEX IF NOT EXISTS lending_7x7_penalty_assessment_loan_period_idx
    ON lending.seven_by_seven_penalty_assessments (
        loan_id,
        assessment_start_date,
        assessed_through_date,
        id
    );

CREATE TABLE IF NOT EXISTS lending.seven_by_seven_penalty_payment_allocations (
    id BIGSERIAL PRIMARY KEY,
    loan_id UUID NOT NULL
        REFERENCES lending.loans(id) ON DELETE RESTRICT,
    transaction_id UUID NOT NULL
        REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    amount_applied NUMERIC(18,2) NOT NULL CHECK (amount_applied > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (transaction_id)
);

CREATE INDEX IF NOT EXISTS lending_7x7_penalty_payment_loan_idx
    ON lending.seven_by_seven_penalty_payment_allocations (loan_id, id);

CREATE OR REPLACE FUNCTION lending.guard_7x7_penalty_evidence_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '7x7 post-maturity penalty evidence is immutable; record new audited evidence instead.';
END;
$$;

DROP TRIGGER IF EXISTS lending_7x7_penalty_assessment_immutability_guard
    ON lending.seven_by_seven_penalty_assessments;
CREATE TRIGGER lending_7x7_penalty_assessment_immutability_guard
BEFORE UPDATE OR DELETE ON lending.seven_by_seven_penalty_assessments
FOR EACH ROW EXECUTE FUNCTION lending.guard_7x7_penalty_evidence_immutability();

DROP TRIGGER IF EXISTS lending_7x7_penalty_payment_immutability_guard
    ON lending.seven_by_seven_penalty_payment_allocations;
CREATE TRIGGER lending_7x7_penalty_payment_immutability_guard
BEFORE UPDATE OR DELETE ON lending.seven_by_seven_penalty_payment_allocations
FOR EACH ROW EXECUTE FUNCTION lending.guard_7x7_penalty_evidence_immutability();

-- Replace the original contractual-installment allocation guard so the receipt's
-- authoritative loan-applied amount cannot be consumed twice across contractual
-- installment evidence and the separate penalty evidence. Raw receipt cash is
-- intentionally not the limit: migration 0096 made applied_amount authoritative.
CREATE OR REPLACE FUNCTION lending.guard_loan_installment_payment_allocation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    installment_loan_id UUID;
    transaction_loan_id UUID;
    transaction_applied_amount NUMERIC(18,2);
    transaction_voided BOOLEAN;
    installment_allocated_elsewhere NUMERIC(18,2);
    penalty_allocated NUMERIC(18,2);
BEGIN
    SELECT schedule.loan_id
    INTO installment_loan_id
    FROM lending.loan_contract_installments installment
    JOIN lending.loan_contract_schedules schedule
      ON schedule.id = installment.schedule_id
    WHERE installment.id = NEW.installment_id;

    SELECT receipt.loan_id, receipt.applied_amount, receipt.is_voided
    INTO transaction_loan_id, transaction_applied_amount, transaction_voided
    FROM lending.collection_transactions receipt
    WHERE receipt.id = NEW.transaction_id
    FOR UPDATE;

    IF installment_loan_id IS NULL OR transaction_loan_id IS NULL THEN
        RAISE EXCEPTION 'Installment and collection transaction must exist before payment allocation.';
    END IF;

    IF installment_loan_id <> transaction_loan_id THEN
        RAISE EXCEPTION 'Payment allocation must stay within the same loan.';
    END IF;

    IF transaction_voided THEN
        RAISE EXCEPTION 'A voided collection transaction cannot be allocated to a contractual installment.';
    END IF;

    SELECT coalesce(sum(allocation.amount_applied), 0)
    INTO installment_allocated_elsewhere
    FROM lending.loan_installment_payment_allocations allocation
    WHERE allocation.transaction_id = NEW.transaction_id
      AND (TG_OP = 'INSERT' OR allocation.id <> NEW.id);

    SELECT coalesce(sum(allocation.amount_applied), 0)
    INTO penalty_allocated
    FROM lending.seven_by_seven_penalty_payment_allocations allocation
    WHERE allocation.transaction_id = NEW.transaction_id;

    IF installment_allocated_elsewhere
       + penalty_allocated
       + NEW.amount_applied > transaction_applied_amount THEN
        RAISE EXCEPTION 'Contractual installment plus penalty allocations cannot exceed the collection transaction applied amount.';
    END IF;

    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION lending.guard_7x7_penalty_payment_allocation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    transaction_loan_id UUID;
    transaction_applied_amount NUMERIC(18,2);
    transaction_voided BOOLEAN;
    transaction_entry_type TEXT;
    installment_allocated NUMERIC(18,2);
    penalty_allocated_elsewhere NUMERIC(18,2);
    assessed_penalty NUMERIC(18,2);
    paid_penalty_elsewhere NUMERIC(18,2);
BEGIN
    SELECT
        receipt.loan_id,
        receipt.applied_amount,
        receipt.is_voided,
        receipt.entry_type
    INTO
        transaction_loan_id,
        transaction_applied_amount,
        transaction_voided,
        transaction_entry_type
    FROM lending.collection_transactions receipt
    WHERE receipt.id = NEW.transaction_id
    FOR UPDATE;

    IF transaction_loan_id IS NULL THEN
        RAISE EXCEPTION 'Collection transaction must exist before penalty allocation.';
    END IF;

    IF NEW.loan_id <> transaction_loan_id THEN
        RAISE EXCEPTION 'Penalty payment allocation must stay within the same loan.';
    END IF;

    IF transaction_voided THEN
        RAISE EXCEPTION 'A voided collection transaction cannot be allocated to penalty.';
    END IF;

    IF transaction_entry_type <> 'payment' THEN
        RAISE EXCEPTION 'Only a payment collection transaction may settle an assessed 7x7 penalty.';
    END IF;

    SELECT coalesce(sum(allocation.amount_applied), 0)
    INTO installment_allocated
    FROM lending.loan_installment_payment_allocations allocation
    WHERE allocation.transaction_id = NEW.transaction_id;

    SELECT coalesce(sum(allocation.amount_applied), 0)
    INTO penalty_allocated_elsewhere
    FROM lending.seven_by_seven_penalty_payment_allocations allocation
    WHERE allocation.transaction_id = NEW.transaction_id
      AND (TG_OP = 'INSERT' OR allocation.id <> NEW.id);

    IF installment_allocated
       + penalty_allocated_elsewhere
       + NEW.amount_applied > transaction_applied_amount THEN
        RAISE EXCEPTION 'Contractual installment plus penalty allocations cannot exceed the collection transaction applied amount.';
    END IF;

    SELECT coalesce(sum(assessment.assessed_penalty_amount), 0)
    INTO assessed_penalty
    FROM lending.seven_by_seven_penalty_assessments assessment
    WHERE assessment.loan_id = NEW.loan_id;

    SELECT coalesce(sum(allocation.amount_applied), 0)
    INTO paid_penalty_elsewhere
    FROM lending.seven_by_seven_penalty_payment_allocations allocation
    JOIN lending.collection_transactions paid_receipt
      ON paid_receipt.id = allocation.transaction_id
    WHERE allocation.loan_id = NEW.loan_id
      AND paid_receipt.is_voided = false
      AND (TG_OP = 'INSERT' OR allocation.id <> NEW.id);

    IF paid_penalty_elsewhere + NEW.amount_applied > assessed_penalty THEN
        RAISE EXCEPTION 'Penalty payment allocations cannot exceed assessed penalty outstanding.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_7x7_penalty_payment_allocation_guard
    ON lending.seven_by_seven_penalty_payment_allocations;
CREATE TRIGGER lending_7x7_penalty_payment_allocation_guard
BEFORE INSERT ON lending.seven_by_seven_penalty_payment_allocations
FOR EACH ROW EXECUTE FUNCTION lending.guard_7x7_penalty_payment_allocation();

CREATE OR REPLACE VIEW accounting.seven_by_seven_penalty_evidence AS
WITH assessed AS (
    SELECT
        assessment.loan_id,
        coalesce(sum(assessment.assessed_penalty_amount), 0)::numeric(18,2)
            AS assessed_penalty,
        max(assessment.assessed_through_date) AS assessed_through_date
    FROM lending.seven_by_seven_penalty_assessments assessment
    GROUP BY assessment.loan_id
), paid AS (
    SELECT
        allocation.loan_id,
        coalesce(sum(allocation.amount_applied) FILTER (
            WHERE receipt.is_voided = false
        ), 0)::numeric(18,2) AS penalty_paid
    FROM lending.seven_by_seven_penalty_payment_allocations allocation
    JOIN lending.collection_transactions receipt
      ON receipt.id = allocation.transaction_id
    GROUP BY allocation.loan_id
)
SELECT
    loan.id AS loan_id,
    loan.loan_number,
    coalesce(assessed.assessed_penalty, 0)::numeric(18,2) AS assessed_penalty,
    coalesce(paid.penalty_paid, 0)::numeric(18,2) AS penalty_paid,
    greatest(
        coalesce(assessed.assessed_penalty, 0)
        - coalesce(paid.penalty_paid, 0),
        0
    )::numeric(18,2) AS penalty_outstanding,
    assessed.assessed_through_date,
    false AS ready_to_post
FROM lending.loans loan
LEFT JOIN assessed ON assessed.loan_id = loan.id
LEFT JOIN paid ON paid.loan_id = loan.id;

COMMENT ON COLUMN lending.seven_by_seven_pricing_compliance_reviews.penalty_policy_version IS
    'Optional exact-term 7x7 penalty-policy version. Legacy review rows may remain NULL and are penalty-ineligible.';
COMMENT ON COLUMN lending.seven_by_seven_pricing_compliance_reviews.penalty_monthly_rate IS
    'Approved contractual simple monthly penalty rate for the exact reviewed 7x7 terms; this authority does not itself accrue a charge.';
COMMENT ON COLUMN lending.seven_by_seven_pricing_compliance_reviews.penalty_rate_ceiling IS
    'Terms-bound applicable legal penalty-rate ceiling supplied by reviewed compliance evidence; no universal numeric ceiling is inferred here.';
COMMENT ON COLUMN lending.seven_by_seven_pricing_compliance_reviews.lifetime_nonprincipal_cost_ceiling IS
    'Terms-bound lifetime non-principal cost ceiling amount used only when the exact signed-policy authority is complete.';
COMMENT ON TABLE lending.seven_by_seven_penalty_assessments IS
    'Immutable aggregate 7x7 post-maturity penalty assessment evidence frozen only at a real financial boundary; not a daily accrual ledger.';
COMMENT ON TABLE lending.seven_by_seven_penalty_payment_allocations IS
    'Immutable aggregate application of an official payment receipt to already assessed 7x7 penalty after contractual interest and principal allocation.';
COMMENT ON VIEW accounting.seven_by_seven_penalty_evidence IS
    'Read-only assessed/paid/outstanding 7x7 penalty evidence. ready_to_post remains false; this view does not decide journal, tax, EIR, or income-recognition policy.';

COMMIT;
