BEGIN;

-- Follow-up hardening for A6.2 tax-liability preparation. The original 0083
-- function used a local name that collided with journal_entries.source_event_key
-- under PostgreSQL's fail-closed PL/pgSQL ambiguity rules. Replace the function
-- with an explicitly named protected source key and tighten the evidence-pair
-- constraint. No journal, liability, settlement, or automatic posting is created
-- by installing this migration.

ALTER TABLE accounting.v1_tax_liability_preparations
    ADD CONSTRAINT v1_tax_liability_preparation_exact_evidence_ck
    CHECK (
        (
            tax_type = 'documentary_stamp_tax'
            AND dst_evidence_id IS NOT NULL
            AND dst_evidence_id = evidence_id
            AND percentage_evidence_id IS NULL
        )
        OR
        (
            tax_type = 'percentage_tax_lending'
            AND percentage_evidence_id IS NOT NULL
            AND percentage_evidence_id = evidence_id
            AND dst_evidence_id IS NULL
        )
    ) NOT VALID;

ALTER TABLE accounting.v1_tax_liability_preparations
    VALIDATE CONSTRAINT v1_tax_liability_preparation_exact_evidence_ck;

CREATE OR REPLACE FUNCTION accounting.prepare_v1_tax_liability_journal(
    p_tax_type TEXT,
    p_evidence_id UUID,
    p_actor_user_id UUID
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    normalized_tax_type TEXT := btrim(coalesce(p_tax_type, ''));
    existing accounting.v1_tax_liability_preparations%ROWTYPE;
    dst_evidence accounting.v1_dst_evidence%ROWTYPE;
    percentage_evidence accounting.v1_percentage_tax_evidence%ROWTYPE;
    loan_row lending.loans%ROWTYPE;
    event_row lending.loan_disbursement_events%ROWTYPE;
    transaction_row lending.collection_transactions%ROWTYPE;
    rule_row accounting.v1_tax_rule_evidence%ROWTYPE;
    expense_account accounting.accounts%ROWTYPE;
    payable_account accounting.accounts%ROWTYPE;
    period_row accounting.fiscal_periods%ROWTYPE;
    recognition_date DATE;
    tax_due NUMERIC(18,2);
    evidence_digest TEXT;
    source_loan_id UUID;
    source_client_id UUID;
    protected_source_event_key TEXT;
    journal_id UUID;
    expected_due NUMERIC(18,2);
    actual_term_days INTEGER;
    proration_days INTEGER;
    expected_expense_key TEXT;
    expected_expense_code TEXT;
BEGIN
    PERFORM accounting.require_v1_tax_management_actor(
        p_actor_user_id,
        'accounting.tax.liability.prepare'
    );

    IF normalized_tax_type NOT IN ('documentary_stamp_tax', 'percentage_tax_lending')
       OR p_evidence_id IS NULL THEN
        RAISE EXCEPTION 'Tax-liability preparation requires an exact supported tax type and evidence identifier.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended(
            'v1-tax-liability:' || normalized_tax_type || ':' || p_evidence_id::text,
            0
        )
    );

    SELECT * INTO existing
    FROM accounting.v1_tax_liability_preparations item
    WHERE item.tax_type = normalized_tax_type
      AND item.evidence_id = p_evidence_id;
    IF existing.id IS NOT NULL THEN
        RETURN existing.journal_entry_id;
    END IF;

    IF normalized_tax_type = 'documentary_stamp_tax' THEN
        SELECT * INTO dst_evidence
        FROM accounting.v1_dst_evidence item
        WHERE item.id = p_evidence_id
        FOR SHARE;
        IF dst_evidence.id IS NULL THEN
            RAISE EXCEPTION 'Current DST evidence was not found.';
        END IF;
        IF EXISTS (
            SELECT 1 FROM accounting.v1_dst_evidence later
            WHERE later.loan_id = dst_evidence.loan_id
              AND later.evidence_version > dst_evidence.evidence_version
        ) THEN
            RAISE EXCEPTION 'Selected DST evidence is superseded and cannot create a tax liability.';
        END IF;

        SELECT * INTO loan_row
        FROM lending.loans loan
        WHERE loan.id = dst_evidence.loan_id
        FOR SHARE;
        SELECT * INTO event_row
        FROM lending.loan_disbursement_events event
        WHERE event.id = dst_evidence.disbursement_event_id
        FOR SHARE;
        SELECT * INTO rule_row
        FROM accounting.v1_tax_rule_evidence rule
        WHERE rule.id = dst_evidence.rule_evidence_id
        FOR SHARE;

        IF loan_row.id IS NULL OR event_row.id IS NULL OR rule_row.id IS NULL
           OR event_row.is_voided
           OR event_row.loan_id <> loan_row.id
           OR event_row.client_id <> loan_row.client_id
           OR dst_evidence.client_id <> loan_row.client_id
           OR dst_evidence.issue_date <> event_row.business_date
           OR dst_evidence.issue_price <> event_row.principal_snapshot
           OR event_row.principal_snapshot <> loan_row.principal THEN
            RAISE EXCEPTION 'DST source coordinates no longer match the current protected loan/disbursement evidence.';
        END IF;

        actual_term_days := loan_row.due_date - loan_row.date_released;
        IF actual_term_days <= 0 OR dst_evidence.term_days <> actual_term_days
           OR rule_row.tax_type <> 'documentary_stamp_tax'
           OR dst_evidence.issue_date < rule_row.effective_from
           OR (
                rule_row.effective_to IS NOT NULL
                AND dst_evidence.issue_date > rule_row.effective_to
           )
           OR (
                rule_row.maturity_max_days IS NOT NULL
                AND actual_term_days > rule_row.maturity_max_days
           )
           OR EXISTS (
                SELECT 1 FROM accounting.v1_tax_rule_evidence later
                WHERE later.tax_type = rule_row.tax_type
                  AND later.rule_key = rule_row.rule_key
                  AND later.rule_version > rule_row.rule_version
                  AND later.effective_from <= dst_evidence.issue_date
                  AND (
                      later.effective_to IS NULL
                      OR dst_evidence.issue_date <= later.effective_to
                  )
           ) THEN
            RAISE EXCEPTION 'DST rule/term evidence is no longer current for liability recognition.';
        END IF;

        proration_days := CASE WHEN actual_term_days < 365 THEN actual_term_days ELSE 365 END;
        expected_due := CASE
            WHEN rule_row.treatment = 'exempt' THEN 0::numeric(18,2)
            ELSE round(
                dst_evidence.issue_price * rule_row.rate
                * proration_days::numeric / 365::numeric,
                2
            )
        END;
        IF dst_evidence.applied_rate <> rule_row.rate
           OR dst_evidence.proration_numerator <> proration_days
           OR dst_evidence.proration_denominator <> 365
           OR dst_evidence.tax_due <> expected_due THEN
            RAISE EXCEPTION 'DST tax liability no longer reconciles to exact current evidence.';
        END IF;

        recognition_date := dst_evidence.issue_date;
        tax_due := dst_evidence.tax_due;
        evidence_digest := dst_evidence.calculation_digest;
        source_loan_id := dst_evidence.loan_id;
        source_client_id := dst_evidence.client_id;
        expected_expense_key := 'documentary_stamp_tax_expense';
        expected_expense_code := '5310';
    ELSE
        SELECT * INTO percentage_evidence
        FROM accounting.v1_percentage_tax_evidence item
        WHERE item.id = p_evidence_id
        FOR SHARE;
        IF percentage_evidence.id IS NULL THEN
            RAISE EXCEPTION 'Current percentage-tax evidence was not found.';
        END IF;
        IF EXISTS (
            SELECT 1 FROM accounting.v1_percentage_tax_evidence later
            WHERE later.transaction_id = percentage_evidence.transaction_id
              AND later.evidence_version > percentage_evidence.evidence_version
        ) THEN
            RAISE EXCEPTION 'Selected percentage-tax evidence is superseded and cannot create a tax liability.';
        END IF;

        SELECT * INTO transaction_row
        FROM lending.collection_transactions transaction
        WHERE transaction.id = percentage_evidence.transaction_id
        FOR SHARE;
        SELECT * INTO loan_row
        FROM lending.loans loan
        WHERE loan.id = percentage_evidence.loan_id
        FOR SHARE;
        SELECT * INTO rule_row
        FROM accounting.v1_tax_rule_evidence rule
        WHERE rule.id = percentage_evidence.rule_evidence_id
        FOR SHARE;

        IF transaction_row.id IS NULL OR loan_row.id IS NULL OR rule_row.id IS NULL
           OR transaction_row.is_voided
           OR transaction_row.entry_type NOT IN ('payment', 'advance')
           OR transaction_row.amount <= 0
           OR transaction_row.loan_id <> percentage_evidence.loan_id
           OR transaction_row.client_id <> percentage_evidence.client_id
           OR transaction_row.collection_date <> percentage_evidence.collection_date
           OR transaction_row.amount <> percentage_evidence.source_cash_amount
           OR percentage_evidence.source_cash_amount
                <> percentage_evidence.taxable_lending_receipt_amount
                 + percentage_evidence.principal_receipt_amount
           OR NOT (
                EXISTS (
                    SELECT 1
                    FROM accounting.regular_journal_posting_entries posted
                    WHERE posted.transaction_id = transaction_row.id
                )
                OR EXISTS (
                    SELECT 1
                    FROM accounting.seven_by_seven_journal_postings posted
                    WHERE posted.transaction_id = transaction_row.id
                )
           ) THEN
            RAISE EXCEPTION 'Percentage-tax liability requires the exact current protected non-voided posted cash source and allocation.';
        END IF;

        IF rule_row.tax_type <> 'percentage_tax_lending'
           OR transaction_row.collection_date < rule_row.effective_from
           OR (
                rule_row.effective_to IS NOT NULL
                AND transaction_row.collection_date > rule_row.effective_to
           )
           OR (
                rule_row.maturity_max_days IS NOT NULL
                AND (loan_row.due_date - loan_row.date_released) > rule_row.maturity_max_days
           )
           OR EXISTS (
                SELECT 1 FROM accounting.v1_tax_rule_evidence later
                WHERE later.tax_type = rule_row.tax_type
                  AND later.rule_key = rule_row.rule_key
                  AND later.rule_version > rule_row.rule_version
                  AND later.effective_from <= transaction_row.collection_date
                  AND (
                      later.effective_to IS NULL
                      OR transaction_row.collection_date <= later.effective_to
                  )
           ) THEN
            RAISE EXCEPTION 'Percentage-tax rule evidence is no longer current for liability recognition.';
        END IF;

        expected_due := CASE
            WHEN rule_row.treatment = 'exempt' THEN 0::numeric(18,2)
            ELSE round(
                percentage_evidence.taxable_lending_receipt_amount * rule_row.rate,
                2
            )
        END;
        IF percentage_evidence.applied_rate <> rule_row.rate
           OR percentage_evidence.tax_due <> expected_due THEN
            RAISE EXCEPTION 'Percentage-tax liability no longer reconciles to exact current evidence.';
        END IF;

        recognition_date := percentage_evidence.collection_date;
        tax_due := percentage_evidence.tax_due;
        evidence_digest := percentage_evidence.allocation_digest;
        source_loan_id := percentage_evidence.loan_id;
        source_client_id := percentage_evidence.client_id;
        expected_expense_key := 'percentage_tax_lending_expense';
        expected_expense_code := '5300';
    END IF;

    IF tax_due <= 0 THEN
        RAISE EXCEPTION 'No positive V1 tax liability is required for zero tax due evidence.';
    END IF;
    IF evidence_digest !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Tax-liability preparation requires the exact retained evidence digest.';
    END IF;

    SELECT * INTO expense_account
    FROM accounting.accounts account
    WHERE account.system_key = expected_expense_key
    FOR SHARE;
    SELECT * INTO payable_account
    FROM accounting.accounts account
    WHERE account.system_key = 'tax_payables'
    FOR SHARE;

    IF expense_account.id IS NULL
       OR expense_account.code <> expected_expense_code
       OR expense_account.account_type <> 'expense'
       OR expense_account.normal_balance <> 'debit'
       OR NOT expense_account.is_active
       OR NOT expense_account.is_posting THEN
        RAISE EXCEPTION 'The exact dedicated V1 tax expense account is unavailable or no longer posting-ready.';
    END IF;
    IF payable_account.id IS NULL
       OR payable_account.code <> '2100'
       OR payable_account.account_type <> 'liability'
       OR payable_account.normal_balance <> 'credit'
       OR NOT payable_account.is_active
       OR NOT payable_account.is_posting THEN
        RAISE EXCEPTION 'Exact active Tax Payables account 2100 is required for V1 tax liability recognition.';
    END IF;

    SELECT * INTO period_row
    FROM accounting.fiscal_periods period
    WHERE period.status = 'open'
      AND recognition_date BETWEEN period.start_date AND period.end_date
    ORDER BY period.start_date DESC
    LIMIT 1
    FOR SHARE;
    IF period_row.id IS NULL THEN
        RAISE EXCEPTION 'Tax liability recognition date must be inside an open accounting period.';
    END IF;

    protected_source_event_key :=
        'v1_tax_liability:' || normalized_tax_type || ':' || p_evidence_id::text;

    IF EXISTS (
        SELECT 1 FROM accounting.journal_entries item
        WHERE item.source_event_key = protected_source_event_key
    ) THEN
        RAISE EXCEPTION 'The protected V1 tax-liability source identity is already occupied outside the preparation audit.';
    END IF;

    PERFORM set_config('accounting.v1_tax_liability_journal_prepare_allowed', 'on', true);
    INSERT INTO accounting.journal_entries (
        fiscal_period_id, posting_date, description, status, source_type,
        source_reference, source_event_key, created_by_user_id, updated_at
    ) VALUES (
        period_row.id,
        recognition_date,
        CASE
            WHEN normalized_tax_type = 'documentary_stamp_tax'
                THEN 'Documentary stamp tax liability from approved evidence'
            ELSE 'Percentage / gross receipts tax liability from approved evidence'
        END,
        'draft',
        'v1_tax_liability',
        normalized_tax_type || ':' || p_evidence_id::text,
        protected_source_event_key,
        p_actor_user_id,
        now()
    ) RETURNING id INTO journal_id;
    PERFORM set_config('accounting.v1_tax_liability_journal_prepare_allowed', 'off', true);

    PERFORM set_config('accounting.v1_tax_liability_journal_line_write_allowed', 'on', true);
    INSERT INTO accounting.journal_lines (
        journal_entry_id, line_number, account_id, description, debit, credit,
        client_id, loan_id
    ) VALUES
        (
            journal_id, 1, expense_account.id,
            CASE
                WHEN normalized_tax_type = 'documentary_stamp_tax'
                    THEN 'Documentary stamp tax expense'
                ELSE 'Percentage / gross receipts tax expense'
            END,
            tax_due, 0, source_client_id, source_loan_id
        ),
        (
            journal_id, 2, payable_account.id,
            'Tax payable recognized from exact approved V1 tax evidence',
            0, tax_due, source_client_id, source_loan_id
        );
    PERFORM set_config('accounting.v1_tax_liability_journal_line_write_allowed', 'off', true);

    INSERT INTO accounting.journal_events(
        journal_entry_id, event_type, actor_user_id, details
    ) VALUES (
        journal_id,
        'draft_created',
        p_actor_user_id,
        jsonb_build_object(
            'source_type', 'v1_tax_liability',
            'tax_type', normalized_tax_type,
            'evidence_id', p_evidence_id,
            'evidence_digest', evidence_digest,
            'recognition_date', recognition_date,
            'tax_due', tax_due,
            'expense_account_code', expense_account.code,
            'tax_payable_account_code', payable_account.code,
            'posting_enabled', false,
            'automatic_source_posting', false
        )
    );

    PERFORM set_config('accounting.v1_tax_liability_preparation_insert_allowed', 'on', true);
    INSERT INTO accounting.v1_tax_liability_preparations (
        tax_type, evidence_id, dst_evidence_id, percentage_evidence_id,
        journal_entry_id, source_event_key, recognition_date, tax_due,
        evidence_digest, expense_account_id, tax_payable_account_id,
        fiscal_period_id, prepared_by_user_id
    ) VALUES (
        normalized_tax_type,
        p_evidence_id,
        CASE WHEN normalized_tax_type = 'documentary_stamp_tax' THEN p_evidence_id ELSE NULL END,
        CASE WHEN normalized_tax_type = 'percentage_tax_lending' THEN p_evidence_id ELSE NULL END,
        journal_id,
        protected_source_event_key,
        recognition_date,
        tax_due,
        evidence_digest,
        expense_account.id,
        payable_account.id,
        period_row.id,
        p_actor_user_id
    );
    PERFORM set_config('accounting.v1_tax_liability_preparation_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.tax.liability.prepared',
        'v1_tax_liability',
        p_evidence_id,
        jsonb_build_object(
            'tax_type', normalized_tax_type,
            'journal_entry_id', journal_id,
            'source_event_key', protected_source_event_key,
            'recognition_date', recognition_date,
            'tax_due', tax_due,
            'evidence_digest', evidence_digest,
            'expense_account_code', expense_account.code,
            'tax_payable_account_code', payable_account.code,
            'automatic_source_posting', false
        )
    );

    RETURN journal_id;
END;
$$;

COMMIT;
