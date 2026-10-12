BEGIN;

-- Source completeness starts from raw operations, never from prepared queues.
-- This layer deliberately remains separate from 0141's private-wallet inventory.
CREATE OR REPLACE FUNCTION accounting.legacy_journal_reversal_exact(p_original UUID, p_reversal UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SET search_path = pg_catalog AS $$
    SELECT EXISTS (
        SELECT 1 FROM accounting.journal_entries original
        JOIN accounting.journal_entries reversal ON reversal.id = p_reversal
        JOIN accounting.fiscal_periods period ON period.id = reversal.fiscal_period_id
        WHERE original.id = p_original AND original.status = 'posted'
          AND reversal.status = 'posted' AND reversal.reversal_of_entry_id = original.id
          AND reversal.posting_date BETWEEN period.start_date AND period.end_date
          AND (SELECT count(*) FROM accounting.journal_lines WHERE journal_entry_id = original.id) > 1
          AND (SELECT count(*) FROM accounting.journal_lines WHERE journal_entry_id = original.id)
            = (SELECT count(*) FROM accounting.journal_lines WHERE journal_entry_id = reversal.id)
          AND NOT EXISTS (
              SELECT 1 FROM accounting.journal_lines line WHERE line.journal_entry_id = original.id
              AND NOT EXISTS (
                  SELECT 1 FROM accounting.journal_lines swapped
                  WHERE swapped.journal_entry_id = reversal.id
                    AND swapped.line_number = line.line_number AND swapped.account_id = line.account_id
                    AND swapped.client_id IS NOT DISTINCT FROM line.client_id
                    AND swapped.loan_id IS NOT DISTINCT FROM line.loan_id
                    AND swapped.debit = line.credit AND swapped.credit = line.debit
              )
          )
    );
$$;

-- Regular posting audits retain the approved set identity, not individual line
-- snapshots. Reconcile the complete immutable set, its source coordinates and
-- permitted ledger pattern. EIR calculation authority remains the protected
-- posting workflow; the close guard must not invent a replacement EIR engine.
CREATE OR REPLACE FUNCTION accounting.legacy_regular_collection_posted_exact(p_transaction_id UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SET search_path = pg_catalog AS $$
    SELECT EXISTS (
        SELECT 1 FROM lending.collection_transactions source
        JOIN accounting.regular_journal_draft_preparations prepared ON prepared.transaction_id = source.id
        JOIN accounting.regular_journal_posting_sets posting
          ON posting.loan_id = prepared.loan_id AND posting.review_set_fingerprint = prepared.review_set_fingerprint
        WHERE source.id = p_transaction_id AND prepared.loan_id = source.loan_id
          AND posting.expected_transaction_count = prepared.expected_set_transaction_count
          AND posting.expected_transaction_count = (
              SELECT count(*) FROM accounting.regular_journal_draft_preparations item
              WHERE item.loan_id = posting.loan_id AND item.review_set_fingerprint = posting.review_set_fingerprint)
          AND posting.expected_entry_count = (
              SELECT sum(item.expected_entry_count) FROM accounting.regular_journal_draft_preparations item
              WHERE item.loan_id = posting.loan_id AND item.review_set_fingerprint = posting.review_set_fingerprint)
          AND posting.expected_entry_count = (
              SELECT count(*) FROM accounting.regular_journal_posting_entries item WHERE item.posting_set_id = posting.id)
          AND prepared.expected_entry_count = (
              SELECT count(*) FROM accounting.regular_journal_draft_preparation_entries item WHERE item.preparation_id = prepared.id)
          AND prepared.expected_entry_count = (
              SELECT count(*) FROM accounting.regular_journal_posting_entries item
              WHERE item.posting_set_id = posting.id AND item.preparation_id = prepared.id AND item.transaction_id = source.id)
          AND 1 = (SELECT count(*) FROM accounting.regular_journal_draft_preparation_entries item
                   WHERE item.preparation_id = prepared.id AND item.entry_type = 'collection')
          AND NOT EXISTS (
              SELECT 1 FROM accounting.regular_journal_draft_preparation_entries entry
              LEFT JOIN accounting.regular_journal_posting_entries audit
                ON audit.posting_set_id = posting.id AND audit.preparation_id = prepared.id
               AND audit.transaction_id = source.id AND audit.sequence_order = entry.sequence_order
               AND audit.journal_entry_id = entry.journal_entry_id AND audit.source_event_key = entry.source_event_key
              LEFT JOIN accounting.journal_entries journal ON journal.id = entry.journal_entry_id
              LEFT JOIN accounting.fiscal_periods period ON period.id = journal.fiscal_period_id
              LEFT JOIN LATERAL (
                  SELECT count(*) AS line_count, sum(line.debit) AS debit, sum(line.credit) AS credit,
                      bool_and(line.client_id IS NOT DISTINCT FROM source.client_id
                          AND line.loan_id IS NOT DISTINCT FROM source.loan_id
                          AND CASE WHEN entry.entry_type = 'collection' THEN
                              ((account.system_key = 'cash_collector_custody' AND line.debit = source.applied_amount AND line.credit = 0)
                               OR (account.system_key IN ('accrued_interest_receivable','loans_receivable_regular') AND line.credit > 0 AND line.debit = 0))
                          ELSE ((account.system_key = 'accrued_interest_receivable' AND line.debit > 0 AND line.credit = 0)
                               OR (account.system_key = 'interest_income_regular' AND line.credit > 0 AND line.debit = 0)) END) AS lines_valid
                  FROM accounting.journal_lines line JOIN accounting.accounts account ON account.id = line.account_id
                  WHERE line.journal_entry_id = journal.id
              ) totals ON true
              WHERE entry.preparation_id = prepared.id
                AND (audit.journal_entry_id IS NULL OR journal.status IS DISTINCT FROM 'posted'
                  OR journal.entry_number IS DISTINCT FROM audit.entry_number
                  OR journal.source_event_key IS DISTINCT FROM entry.source_event_key
                  OR journal.posting_date NOT BETWEEN period.start_date AND period.end_date
                  OR totals.lines_valid IS DISTINCT FROM true OR totals.line_count < 2
                  OR totals.debit IS DISTINCT FROM totals.credit OR totals.debit <= 0
                  OR CASE WHEN entry.entry_type = 'collection' THEN
                      journal.source_type IS DISTINCT FROM 'collection'
                      OR journal.source_reference IS DISTINCT FROM source.id::text
                      OR journal.source_event_key IS DISTINCT FROM 'collection:' || source.id::text
                      OR journal.posting_date IS DISTINCT FROM source.collection_date
                      OR totals.debit IS DISTINCT FROM source.applied_amount
                      OR totals.line_count > 3
                  ELSE journal.source_type IS DISTINCT FROM 'regular_eir_accrual'
                      OR journal.source_reference IS DISTINCT FROM source.id::text || ':fiscal_period:' || journal.fiscal_period_id::text
                      OR journal.source_event_key IS DISTINCT FROM 'eir_accrual:collection:' || source.id::text || ':fiscal_period:' || journal.fiscal_period_id::text
                      OR journal.posting_date > source.collection_date OR totals.line_count <> 2 END)
          )
    );
$$;

CREATE OR REPLACE FUNCTION accounting.legacy_regular_collection_reversed_exact(p_transaction_id UUID, p_cutoff DATE)
RETURNS BOOLEAN LANGUAGE sql STABLE SET search_path = pg_catalog AS $$
    SELECT EXISTS (
        SELECT 1 FROM accounting.regular_journal_reversal_sets reversal
        JOIN lending.collection_transaction_voids void ON void.id = reversal.collection_void_id
        JOIN accounting.regular_journal_draft_preparations prepared ON prepared.transaction_id = reversal.transaction_id
        WHERE reversal.transaction_id = p_transaction_id AND void.transaction_id = p_transaction_id
          AND reversal.posting_date <= p_cutoff
          AND reversal.expected_entry_count = prepared.expected_entry_count
          AND reversal.reversed_entry_count = prepared.expected_entry_count
          AND reversal.expected_entry_count = (SELECT count(*) FROM accounting.regular_journal_reversal_entries item WHERE item.reversal_set_id = reversal.id)
          AND NOT EXISTS (
              SELECT 1 FROM accounting.regular_journal_posting_entries original
              LEFT JOIN accounting.regular_journal_reversal_entries item
                ON item.reversal_set_id = reversal.id AND item.original_journal_entry_id = original.journal_entry_id
               AND item.preparation_id = original.preparation_id AND item.sequence_order = original.sequence_order
              LEFT JOIN accounting.journal_entries journal ON journal.id = item.reversal_journal_entry_id
              WHERE original.preparation_id = prepared.id AND (
                  original.posting_set_id IS DISTINCT FROM reversal.posting_set_id
                  OR item.original_entry_number IS DISTINCT FROM original.entry_number
                  OR item.original_source_event_key IS DISTINCT FROM original.source_event_key
                  OR journal.entry_number IS DISTINCT FROM item.reversal_entry_number
                  OR journal.source_type IS DISTINCT FROM 'regular_collection_void_reversal'
                  OR journal.source_reference IS DISTINCT FROM void.id::text
                  OR journal.source_event_key IS DISTINCT FROM item.reversal_source_event_key
                  OR item.reversal_source_event_key IS DISTINCT FROM 'regular-collection-void-reversal:' || void.id::text || ':' || original.journal_entry_id::text
                  OR journal.posting_date IS DISTINCT FROM reversal.posting_date
                  OR NOT accounting.legacy_journal_reversal_exact(original.journal_entry_id, item.reversal_journal_entry_id))
          )
    );
$$;

CREATE OR REPLACE FUNCTION accounting.legacy_two_line_posted_exact(
    p_journal UUID, p_source_key TEXT, p_source_type TEXT, p_reference TEXT,
    p_date DATE, p_period UUID, p_debit UUID, p_credit UUID, p_amount NUMERIC,
    p_client UUID, p_loan UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SET search_path = pg_catalog AS $$
    SELECT EXISTS (
        SELECT 1 FROM accounting.journal_entries journal
        JOIN accounting.fiscal_periods period ON period.id = journal.fiscal_period_id
        WHERE journal.id = p_journal AND journal.status = 'posted'
          AND journal.source_event_key = p_source_key AND journal.source_type = p_source_type
          AND journal.source_reference = p_reference AND journal.posting_date = p_date
          AND journal.fiscal_period_id = p_period AND p_date BETWEEN period.start_date AND period.end_date
          AND p_amount > 0 AND p_debit <> p_credit
          AND 2 = (SELECT count(*) FROM accounting.journal_lines WHERE journal_entry_id = journal.id)
          AND EXISTS (SELECT 1 FROM accounting.journal_lines line WHERE line.journal_entry_id = journal.id
                      AND line.line_number = 1 AND line.account_id = p_debit AND line.debit = p_amount AND line.credit = 0
                      AND line.client_id IS NOT DISTINCT FROM p_client AND line.loan_id IS NOT DISTINCT FROM p_loan)
          AND EXISTS (SELECT 1 FROM accounting.journal_lines line WHERE line.journal_entry_id = journal.id
                      AND line.line_number = 2 AND line.account_id = p_credit AND line.credit = p_amount AND line.debit = 0
                      AND line.client_id IS NOT DISTINCT FROM p_client AND line.loan_id IS NOT DISTINCT FROM p_loan)
    );
$$;

-- Normalize retained tax evidence without a current_date/open-period predicate.
CREATE OR REPLACE VIEW accounting.legacy_tax_evidence_sources AS
SELECT 'documentary_stamp_tax'::text AS tax_type, evidence.id AS evidence_id,
    evidence.disbursement_event_id AS source_id, evidence.loan_id, evidence.client_id,
    evidence.issue_date AS recognition_date, evidence.tax_due, evidence.calculation_digest AS evidence_digest,
    evidence.evidence_version
FROM accounting.v1_dst_evidence evidence
UNION ALL
SELECT 'percentage_tax_lending', evidence.id, evidence.transaction_id, evidence.loan_id, evidence.client_id,
    evidence.collection_date, evidence.tax_due, evidence.allocation_digest, evidence.evidence_version
FROM accounting.v1_percentage_tax_evidence evidence;

CREATE OR REPLACE FUNCTION accounting.legacy_tax_liability_posted_exact(p_tax_type TEXT, p_evidence UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SET search_path = pg_catalog AS $$
    SELECT EXISTS (
        SELECT 1 FROM accounting.legacy_tax_evidence_sources evidence
        JOIN accounting.v1_tax_liability_preparations prepared
          ON prepared.tax_type = evidence.tax_type AND prepared.evidence_id = evidence.evidence_id
        JOIN accounting.v1_tax_liability_postings posting ON posting.preparation_id = prepared.id
        JOIN accounting.journal_entries journal ON journal.id = prepared.journal_entry_id
        JOIN accounting.accounts expense ON expense.id = prepared.expense_account_id
        JOIN accounting.accounts payable ON payable.id = prepared.tax_payable_account_id
        WHERE evidence.tax_type = p_tax_type AND evidence.evidence_id = p_evidence
          AND prepared.recognition_date = evidence.recognition_date AND prepared.tax_due = evidence.tax_due
          AND prepared.evidence_digest = evidence.evidence_digest
          AND prepared.source_event_key = 'v1_tax_liability:' || evidence.tax_type || ':' || evidence.evidence_id::text
          AND posting.journal_entry_id = prepared.journal_entry_id AND journal.entry_number = posting.entry_number
          AND posting.confirmed_evidence_digest = evidence.evidence_digest AND posting.confirmed_tax_due = evidence.tax_due
          AND posting.confirmed_expense_account_id = prepared.expense_account_id
          AND posting.confirmed_tax_payable_account_id = prepared.tax_payable_account_id
          AND posting.confirmed_posting_date = prepared.recognition_date AND posting.confirmed_fiscal_period_id = prepared.fiscal_period_id
          AND expense.system_key = CASE WHEN evidence.tax_type = 'documentary_stamp_tax'
              THEN 'documentary_stamp_tax_expense' ELSE 'percentage_tax_lending_expense' END
          AND payable.system_key = 'tax_payables'
          AND accounting.legacy_two_line_posted_exact(journal.id, prepared.source_event_key, 'v1_tax_liability',
              evidence.tax_type || ':' || evidence.evidence_id::text, evidence.recognition_date, prepared.fiscal_period_id,
              prepared.expense_account_id, prepared.tax_payable_account_id, evidence.tax_due, evidence.client_id, evidence.loan_id)
    );
$$;

-- Start every branch with immutable actual payment/adjustment evidence, so a
-- missing draft cannot remove the source. Status labels and period openness are
-- irrelevant after posting: retained coordinates and exact lines are the proof.
CREATE OR REPLACE VIEW accounting.legacy_tax_movement_proof AS
SELECT 'tax_payment'::text AS source_type, source.id AS source_id, source.payment_date AS effective_date,
    source.payment_amount AS amount,
    coalesce(posting.id IS NOT NULL
      AND prepared.tax_return_id = source.tax_return_id AND prepared.payment_date = source.payment_date
      AND prepared.payment_amount = source.payment_amount AND source.payment_amount = tax_return.declared_tax_due
      AND prepared.payment_evidence_digest = source.evidence_digest AND prepared.return_evidence_digest = tax_return.evidence_digest
      AND prepared.source_event_key = 'v1_tax_settlement:' || source.id::text
      AND posting.payment_evidence_id = source.id AND posting.tax_return_id = source.tax_return_id
      AND posting.journal_entry_id = prepared.journal_entry_id AND journal.entry_number = posting.entry_number
      AND (posting.confirmed_return_evidence_digest, posting.confirmed_payment_evidence_digest,
           posting.confirmed_payment_amount, posting.confirmed_tax_payable_account_id, posting.confirmed_cash_account_id,
           posting.confirmed_posting_date, posting.confirmed_fiscal_period_id)
        = (tax_return.evidence_digest, source.evidence_digest, source.payment_amount, prepared.tax_payable_account_id,
           prepared.cash_account_id, source.payment_date, prepared.fiscal_period_id)
      AND payable.system_key = 'tax_payables' AND cash.system_key = source.cash_account_system_key
      AND accounting.legacy_two_line_posted_exact(journal.id, prepared.source_event_key, 'v1_tax_settlement', source.id::text,
          source.payment_date, prepared.fiscal_period_id, prepared.tax_payable_account_id, prepared.cash_account_id,
          source.payment_amount, NULL, NULL), false) AS posted_exact
FROM accounting.v1_tax_payment_evidence source
JOIN accounting.v1_tax_return_evidence tax_return ON tax_return.id = source.tax_return_id
LEFT JOIN accounting.v1_tax_settlement_preparations prepared ON prepared.payment_evidence_id = source.id
LEFT JOIN accounting.v1_tax_settlement_postings posting ON posting.preparation_id = prepared.id
LEFT JOIN accounting.journal_entries journal ON journal.id = prepared.journal_entry_id
LEFT JOIN accounting.accounts payable ON payable.id = prepared.tax_payable_account_id
LEFT JOIN accounting.accounts cash ON cash.id = prepared.cash_account_id
UNION ALL
SELECT 'tax_adjustment', source.id, source.adjustment_date, source.adjustment_amount,
    coalesce(posting.id IS NOT NULL AND original.tax_due = source.original_tax_due
      AND original_posting.journal_entry_id = source.original_liability_journal_entry_id
      AND accounting.legacy_tax_liability_posted_exact(source.tax_type, source.original_evidence_id)
      AND prepared.original_liability_journal_entry_id = source.original_liability_journal_entry_id
      AND prepared.adjustment_kind = source.adjustment_kind AND prepared.posting_date = source.adjustment_date
      AND prepared.adjustment_amount = source.adjustment_amount
      AND prepared.source_event_key = 'v1_tax_adjustment:' || source.id::text
      AND posting.adjustment_evidence_id = source.id AND posting.tax_liability_posting_id = source.tax_liability_posting_id
      AND posting.journal_entry_id = prepared.journal_entry_id AND journal.entry_number = posting.entry_number
      AND (posting.confirmed_evidence_digest, posting.confirmed_original_tax_due, posting.confirmed_replacement_tax_due,
           posting.confirmed_adjustment_amount, posting.confirmed_debit_account_id, posting.confirmed_credit_account_id,
           posting.confirmed_posting_date, posting.confirmed_fiscal_period_id)
        = (source.evidence_digest, source.original_tax_due, source.replacement_tax_due, source.adjustment_amount,
           prepared.debit_account_id, prepared.credit_account_id, source.adjustment_date, prepared.fiscal_period_id)
      AND debit.system_key = CASE WHEN source.adjustment_kind = 'reverse_unsettled_liability' THEN 'tax_payables' ELSE 'tax_recoverable' END
      AND credit.system_key = CASE WHEN source.tax_type = 'documentary_stamp_tax' THEN 'documentary_stamp_tax_expense' ELSE 'percentage_tax_lending_expense' END
      AND journal.reversal_of_entry_id IS NOT DISTINCT FROM
          CASE WHEN source.adjustment_kind = 'reverse_unsettled_liability' THEN source.original_liability_journal_entry_id END
      AND accounting.legacy_two_line_posted_exact(journal.id, prepared.source_event_key, 'v1_tax_adjustment', source.id::text,
          source.adjustment_date, prepared.fiscal_period_id, prepared.debit_account_id, prepared.credit_account_id,
          source.adjustment_amount, original.client_id, original.loan_id), false)
FROM accounting.v1_tax_adjustment_evidence source
LEFT JOIN accounting.legacy_tax_evidence_sources original ON original.tax_type = source.tax_type AND original.evidence_id = source.original_evidence_id
LEFT JOIN accounting.v1_tax_liability_postings original_posting ON original_posting.id = source.tax_liability_posting_id
LEFT JOIN accounting.v1_tax_adjustment_preparations prepared ON prepared.adjustment_evidence_id = source.id
LEFT JOIN accounting.v1_tax_adjustment_postings posting ON posting.preparation_id = prepared.id
LEFT JOIN accounting.journal_entries journal ON journal.id = prepared.journal_entry_id
LEFT JOIN accounting.accounts debit ON debit.id = prepared.debit_account_id
LEFT JOIN accounting.accounts credit ON credit.id = prepared.credit_account_id
UNION ALL
SELECT 'tax_additional_liability', source.id, source.recognition_date, source.additional_tax_due,
    coalesce(posting.id IS NOT NULL AND original.tax_due = source.original_item_tax_due
      AND accounting.legacy_tax_liability_posted_exact(source.tax_type, source.original_evidence_id)
      AND prepared.recognition_date = source.recognition_date AND prepared.additional_tax_due = source.additional_tax_due
      AND prepared.source_event_key = 'v1_tax_additional_liability:' || source.id::text
      AND posting.amendment_evidence_id = source.id AND posting.journal_entry_id = prepared.journal_entry_id
      AND journal.entry_number = posting.entry_number
      AND (posting.confirmed_evidence_digest, posting.confirmed_original_declared_tax_due, posting.confirmed_revised_declared_tax_due,
           posting.confirmed_original_item_tax_due, posting.confirmed_replacement_item_tax_due, posting.confirmed_additional_tax_due,
           posting.confirmed_expense_account_id, posting.confirmed_tax_payable_account_id,
           posting.confirmed_posting_date, posting.confirmed_fiscal_period_id)
        = (source.evidence_digest, source.original_declared_tax_due, source.revised_declared_tax_due,
           source.original_item_tax_due, source.replacement_item_tax_due, source.additional_tax_due,
           prepared.expense_account_id, prepared.tax_payable_account_id, source.recognition_date, prepared.fiscal_period_id)
      AND expense.system_key = CASE WHEN source.tax_type = 'documentary_stamp_tax' THEN 'documentary_stamp_tax_expense' ELSE 'percentage_tax_lending_expense' END
      AND payable.system_key = 'tax_payables'
      AND accounting.legacy_two_line_posted_exact(journal.id, prepared.source_event_key, 'v1_tax_additional_liability', source.id::text,
          source.recognition_date, prepared.fiscal_period_id, prepared.expense_account_id, prepared.tax_payable_account_id,
          source.additional_tax_due, original.client_id, original.loan_id), false)
FROM accounting.v1_tax_additional_amendment_evidence source
LEFT JOIN accounting.legacy_tax_evidence_sources original ON original.tax_type = source.tax_type AND original.evidence_id = source.original_evidence_id
LEFT JOIN accounting.v1_tax_additional_liability_preparations prepared ON prepared.amendment_evidence_id = source.id
LEFT JOIN accounting.v1_tax_additional_liability_postings posting ON posting.preparation_id = prepared.id
LEFT JOIN accounting.journal_entries journal ON journal.id = prepared.journal_entry_id
LEFT JOIN accounting.accounts expense ON expense.id = prepared.expense_account_id
LEFT JOIN accounting.accounts payable ON payable.id = prepared.tax_payable_account_id
UNION ALL
SELECT 'tax_additional_payment', source.id, source.payment_date, source.payment_amount,
    coalesce(posting.id IS NOT NULL AND source.payment_amount = amendment.payment_required_amount
      AND prepared.amendment_evidence_id = source.amendment_evidence_id AND prepared.payment_date = source.payment_date
      AND prepared.payment_amount = source.payment_amount AND prepared.payment_evidence_digest = source.evidence_digest
      AND prepared.amendment_evidence_digest = amendment.evidence_digest
      AND prepared.additional_liability_confirmation_digest = liability.confirmation_digest
      AND prepared.source_event_key = 'v1_tax_additional_settlement:' || source.id::text
      AND posting.payment_evidence_id = source.id AND posting.amendment_evidence_id = source.amendment_evidence_id
      AND posting.additional_liability_posting_id = prepared.additional_liability_posting_id
      AND posting.journal_entry_id = prepared.journal_entry_id AND journal.entry_number = posting.entry_number
      AND (posting.confirmed_amendment_evidence_digest, posting.confirmed_additional_liability_confirmation_digest,
           posting.confirmed_payment_evidence_digest, posting.confirmed_payment_amount, posting.confirmed_tax_payable_account_id,
           posting.confirmed_cash_account_id, posting.confirmed_posting_date, posting.confirmed_fiscal_period_id)
        = (amendment.evidence_digest, liability.confirmation_digest, source.evidence_digest, source.payment_amount,
           prepared.tax_payable_account_id, prepared.cash_account_id, source.payment_date, prepared.fiscal_period_id)
      AND payable.system_key = 'tax_payables' AND cash.system_key = source.cash_account_system_key
      AND accounting.legacy_two_line_posted_exact(journal.id, prepared.source_event_key, 'v1_tax_additional_settlement', source.id::text,
          source.payment_date, prepared.fiscal_period_id, prepared.tax_payable_account_id, prepared.cash_account_id,
          source.payment_amount, NULL, NULL), false)
FROM accounting.v1_tax_additional_payment_evidence source
JOIN accounting.v1_tax_additional_amendment_evidence amendment ON amendment.id = source.amendment_evidence_id
LEFT JOIN accounting.v1_tax_additional_settlement_preparations prepared ON prepared.payment_evidence_id = source.id
LEFT JOIN accounting.v1_tax_additional_liability_postings liability ON liability.id = prepared.additional_liability_posting_id
LEFT JOIN accounting.v1_tax_additional_settlement_postings posting ON posting.preparation_id = prepared.id
LEFT JOIN accounting.journal_entries journal ON journal.id = prepared.journal_entry_id
LEFT JOIN accounting.accounts payable ON payable.id = prepared.tax_payable_account_id
LEFT JOIN accounting.accounts cash ON cash.id = prepared.cash_account_id
UNION ALL
SELECT 'tax_refund', source.id, source.refund_date, source.refund_amount,
    coalesce(posting.id IS NOT NULL AND source.refund_amount = adjustment.adjustment_amount
      AND prepared.posting_date = source.refund_date AND prepared.refund_amount = source.refund_amount
      AND prepared.cash_account_id = source.cash_account_id
      AND prepared.source_event_key = 'v1_tax_recoverable_refund:' || source.id::text
      AND posting.refund_evidence_id = source.id AND posting.adjustment_posting_id = source.adjustment_posting_id
      AND posting.journal_entry_id = prepared.journal_entry_id AND journal.entry_number = posting.entry_number
      AND (posting.confirmed_evidence_digest, posting.confirmed_refund_amount, posting.confirmed_cash_account_id,
           posting.confirmed_tax_recoverable_account_id, posting.confirmed_posting_date, posting.confirmed_fiscal_period_id)
        = (source.evidence_digest, source.refund_amount, source.cash_account_id,
           prepared.tax_recoverable_account_id, source.refund_date, prepared.fiscal_period_id)
      AND recoverable.system_key = 'tax_recoverable'
      AND accounting.legacy_two_line_posted_exact(journal.id, prepared.source_event_key, 'v1_tax_recoverable_refund', source.id::text,
          source.refund_date, prepared.fiscal_period_id, prepared.cash_account_id, prepared.tax_recoverable_account_id,
          source.refund_amount, original.client_id, original.loan_id), false)
FROM accounting.v1_tax_recoverable_refund_evidence source
JOIN accounting.v1_tax_adjustment_evidence adjustment ON adjustment.id = source.adjustment_evidence_id
LEFT JOIN accounting.legacy_tax_evidence_sources original ON original.tax_type = adjustment.tax_type AND original.evidence_id = adjustment.original_evidence_id
LEFT JOIN accounting.v1_tax_recoverable_refund_preparations prepared ON prepared.refund_evidence_id = source.id
LEFT JOIN accounting.v1_tax_recoverable_refund_postings posting ON posting.preparation_id = prepared.id
LEFT JOIN accounting.journal_entries journal ON journal.id = prepared.journal_entry_id
LEFT JOIN accounting.accounts recoverable ON recoverable.id = prepared.tax_recoverable_account_id
UNION ALL
SELECT 'tax_credit_application', source.id, source.application_date, source.credit_amount,
    coalesce(posting.id IS NOT NULL AND source.credit_amount = adjustment.adjustment_amount
      AND source.credit_amount = tax_return.declared_tax_due AND source.tax_type = tax_return.tax_type
      AND prepared.posting_date = source.application_date AND prepared.credit_amount = source.credit_amount
      AND prepared.source_event_key = 'v1_tax_recoverable_credit:' || source.id::text
      AND posting.credit_evidence_id = source.id AND posting.adjustment_posting_id = source.adjustment_posting_id
      AND posting.target_tax_return_id = source.target_tax_return_id
      AND posting.journal_entry_id = prepared.journal_entry_id AND journal.entry_number = posting.entry_number
      AND (posting.confirmed_evidence_digest, posting.confirmed_credit_amount, posting.confirmed_tax_payable_account_id,
           posting.confirmed_tax_recoverable_account_id, posting.confirmed_posting_date, posting.confirmed_fiscal_period_id)
        = (source.evidence_digest, source.credit_amount, prepared.tax_payable_account_id,
           prepared.tax_recoverable_account_id, source.application_date, prepared.fiscal_period_id)
      AND payable.system_key = 'tax_payables' AND recoverable.system_key = 'tax_recoverable'
      AND accounting.legacy_two_line_posted_exact(journal.id, prepared.source_event_key, 'v1_tax_recoverable_credit_application', source.id::text,
          source.application_date, prepared.fiscal_period_id, prepared.tax_payable_account_id, prepared.tax_recoverable_account_id,
          source.credit_amount, NULL, NULL), false)
FROM accounting.v1_tax_recoverable_credit_evidence source
JOIN accounting.v1_tax_adjustment_evidence adjustment ON adjustment.id = source.adjustment_evidence_id
JOIN accounting.v1_tax_return_evidence tax_return ON tax_return.id = source.target_tax_return_id
LEFT JOIN accounting.v1_tax_recoverable_credit_preparations prepared ON prepared.credit_evidence_id = source.id
LEFT JOIN accounting.v1_tax_recoverable_credit_postings posting ON posting.preparation_id = prepared.id
LEFT JOIN accounting.journal_entries journal ON journal.id = prepared.journal_entry_id
LEFT JOIN accounting.accounts payable ON payable.id = prepared.tax_payable_account_id
LEFT JOIN accounting.accounts recoverable ON recoverable.id = prepared.tax_recoverable_account_id;

CREATE OR REPLACE FUNCTION accounting.period_legacy_assessment_blockers(p_period_id UUID)
RETURNS TABLE(source_type TEXT, source_id UUID, effective_date DATE, amount NUMERIC(18,2), reason TEXT, account_id UUID)
LANGUAGE sql VOLATILE SET search_path = pg_catalog AS $$
    WITH period AS (SELECT start_date, end_date FROM accounting.fiscal_periods WHERE id = p_period_id),
    loan_controls AS (
        SELECT line.loan_id, account.code, sum(line.debit-line.credit)::numeric(18,2) AS amount
        FROM accounting.journal_entries journal JOIN accounting.journal_lines line ON line.journal_entry_id = journal.id
        JOIN accounting.accounts account ON account.id = line.account_id CROSS JOIN period
        WHERE journal.status = 'posted' AND journal.posting_date <= period.end_date
          AND account.system_key IN ('loans_receivable_regular','loans_receivable_7x7','accrued_interest_receivable')
          AND line.loan_id IS NOT NULL GROUP BY line.loan_id, account.code
    ), carrying AS (
        -- A credit in one control cannot erase another control's debit, nor can
        -- a net-zero loan hide a borrower credit or allocation error.
        SELECT loan_id, sum(amount)::numeric(18,2) AS amount FROM loan_controls
        WHERE amount > 0 GROUP BY loan_id
    ), unallocated AS (
        SELECT account.id, sum(line.debit-line.credit)::numeric(18,2) AS amount
        FROM accounting.journal_entries journal JOIN accounting.journal_lines line ON line.journal_entry_id = journal.id
        JOIN accounting.accounts account ON account.id = line.account_id CROSS JOIN period
        WHERE journal.status = 'posted' AND journal.posting_date <= period.end_date
          AND account.system_key IN ('loans_receivable_regular','loans_receivable_7x7','accrued_interest_receivable')
          AND line.loan_id IS NULL GROUP BY account.id HAVING sum(line.debit-line.credit) <> 0
    ), tax_sources AS (
        SELECT 'tax_dst'::text AS source_type, 'documentary_stamp_tax'::text AS tax_type,
            source.id AS source_id, source.business_date AS effective_date, source.loan_id, source.client_id,
            evidence.id AS evidence_id, evidence.tax_due, evidence.rule_evidence_id, evidence.evidence_version,
            evidence.issue_date = source.business_date AND evidence.disbursement_event_id = source.id
              AND evidence.loan_id = source.loan_id AND evidence.client_id = source.client_id
              AND evidence.issue_price = source.principal_snapshot
              AND evidence.term_days = loan.due_date - loan.date_released AS source_exact,
            wallet.account_id,
            source.is_voided AND (source.voided_at AT TIME ZONE 'Asia/Manila')::date <= period.end_date AS void_at_cutoff
        FROM lending.loan_disbursement_events source JOIN lending.loans loan ON loan.id = source.loan_id CROSS JOIN period
        LEFT JOIN LATERAL (SELECT item.* FROM accounting.v1_dst_evidence item
                           WHERE item.loan_id = source.loan_id ORDER BY item.evidence_version DESC LIMIT 1) evidence ON true
        LEFT JOIN treasury.loan_payouts wallet ON wallet.loan_id = source.loan_id AND wallet.status <> 'cancelled'
        WHERE source.business_date BETWEEN period.start_date AND period.end_date
          AND (NOT source.is_voided OR (source.voided_at AT TIME ZONE 'Asia/Manila')::date > period.end_date
            OR EXISTS (SELECT 1 FROM accounting.v1_tax_liability_preparations item
                       JOIN accounting.v1_tax_liability_postings audit ON audit.preparation_id = item.id
                       JOIN accounting.v1_dst_evidence old ON old.id = item.evidence_id
                       WHERE old.disbursement_event_id = source.id))
        UNION ALL
        SELECT 'tax_percentage', 'percentage_tax_lending', source.id, source.collection_date, source.loan_id, source.client_id,
            evidence.id, evidence.tax_due, evidence.rule_evidence_id, evidence.evidence_version,
            evidence.collection_date = source.collection_date AND evidence.loan_id = source.loan_id
              AND evidence.client_id = source.client_id AND evidence.source_cash_amount = source.amount
              AND evidence.source_cash_amount = evidence.taxable_lending_receipt_amount + evidence.principal_receipt_amount,
            source.funding_account_id,
            source.is_voided AND (source.voided_at AT TIME ZONE 'Asia/Manila')::date <= period.end_date
        FROM lending.collection_transactions source CROSS JOIN period
        LEFT JOIN LATERAL (SELECT item.* FROM accounting.v1_percentage_tax_evidence item
                           WHERE item.transaction_id = source.id ORDER BY item.evidence_version DESC LIMIT 1) evidence ON true
        WHERE source.collection_date BETWEEN period.start_date AND period.end_date AND source.amount > 0
          AND (NOT source.is_voided OR (source.voided_at AT TIME ZONE 'Asia/Manila')::date > period.end_date
            OR EXISTS (SELECT 1 FROM accounting.v1_tax_liability_preparations item
                       JOIN accounting.v1_tax_liability_postings audit ON audit.preparation_id = item.id
                       JOIN accounting.v1_percentage_tax_evidence old ON old.id = item.evidence_id
                       WHERE old.transaction_id = source.id))
    ), tax_state AS (
        SELECT source.*,
            rule.tax_type = source.tax_type AND source.effective_date >= rule.effective_from
              AND (rule.effective_to IS NULL OR source.effective_date <= rule.effective_to)
              AND NOT EXISTS (SELECT 1 FROM accounting.v1_tax_rule_evidence later
                  WHERE later.tax_type = rule.tax_type AND later.rule_key = rule.rule_key AND later.rule_version > rule.rule_version
                    AND source.effective_date >= later.effective_from
                    AND (later.effective_to IS NULL OR source.effective_date <= later.effective_to)) AS rule_exact,
            accounting.legacy_tax_liability_posted_exact(source.tax_type, source.evidence_id) AS posted_exact,
            EXISTS (SELECT 1 FROM accounting.legacy_tax_evidence_sources old
                    JOIN accounting.v1_tax_liability_preparations prepared ON prepared.tax_type = old.tax_type AND prepared.evidence_id = old.evidence_id
                    JOIN accounting.v1_tax_liability_postings posting ON posting.preparation_id = prepared.id
                    WHERE old.tax_type = source.tax_type AND old.source_id = source.source_id
                      AND old.evidence_id <> source.evidence_id
                      AND NOT EXISTS (SELECT 1 FROM accounting.v1_tax_adjustment_evidence adjustment
                          JOIN accounting.legacy_tax_movement_proof proof ON proof.source_type = 'tax_adjustment' AND proof.source_id = adjustment.id
                          WHERE adjustment.tax_liability_posting_id = posting.id AND adjustment.replacement_evidence_id = source.evidence_id
                            AND proof.posted_exact AND proof.effective_date <= period.end_date)
                      AND NOT EXISTS (SELECT 1 FROM accounting.v1_tax_additional_amendment_evidence amendment
                          JOIN accounting.legacy_tax_movement_proof proof ON proof.source_type = 'tax_additional_liability' AND proof.source_id = amendment.id
                          WHERE amendment.tax_liability_posting_id = posting.id AND amendment.replacement_evidence_id = source.evidence_id
                            AND proof.posted_exact AND proof.effective_date <= period.end_date)) AS earlier_posted_evidence,
            EXISTS (SELECT 1 FROM accounting.v1_tax_adjustment_evidence adjustment
                    JOIN accounting.legacy_tax_movement_proof proof ON proof.source_type = 'tax_adjustment' AND proof.source_id = adjustment.id
                    WHERE adjustment.tax_type = source.tax_type AND adjustment.replacement_evidence_id = source.evidence_id
                      AND adjustment.adjustment_kind = 'recognize_settled_tax_recoverable'
                      AND adjustment.replacement_tax_due = source.tax_due AND proof.posted_exact AND proof.effective_date <= period.end_date)
              OR EXISTS (SELECT 1 FROM accounting.v1_tax_additional_amendment_evidence amendment
                    JOIN accounting.legacy_tax_movement_proof proof ON proof.source_type = 'tax_additional_liability' AND proof.source_id = amendment.id
                    WHERE amendment.tax_type = source.tax_type AND amendment.replacement_evidence_id = source.evidence_id
                      AND amendment.replacement_item_tax_due = source.tax_due AND proof.posted_exact AND proof.effective_date <= period.end_date) AS covered_by_adjustment
        FROM tax_sources source CROSS JOIN period LEFT JOIN accounting.v1_tax_rule_evidence rule ON rule.id = source.rule_evidence_id
    )
    SELECT 'eir_period_end'::text, carrying.loan_id, period.end_date, carrying.amount,
        'eir_asof_source_reconciliation_required'::text, NULL::uuid FROM carrying CROSS JOIN period
    UNION ALL
    SELECT 'ecl_period_end', carrying.loan_id, period.end_date, carrying.amount,
        CASE WHEN EXISTS (SELECT 1 FROM accounting.ecl_quantitative_measurements measurement
                          WHERE measurement.loan_id = carrying.loan_id AND measurement.measurement_date = period.end_date)
             THEN 'ecl_asof_source_reconciliation_required' ELSE 'ecl_reporting_date_measurement_required' END, NULL::uuid
    FROM carrying CROSS JOIN period
    UNION ALL
    SELECT 'loan_control_balance', unallocated.id, period.end_date, unallocated.amount,
        'unallocated_control_balance', NULL::uuid FROM unallocated CROSS JOIN period
    UNION ALL
    SELECT 'loan_control_balance', control.loan_id, period.end_date, control.amount,
        'negative_' || control.code || '_balance_requires_borrower_credit_review', NULL::uuid
    FROM loan_controls control CROSS JOIN period WHERE control.amount < 0
    UNION ALL
    SELECT source.source_type, source.source_id, source.effective_date, source.tax_due,
        CASE WHEN source.evidence_id IS NULL THEN 'tax_source_evidence_required'
             WHEN source.void_at_cutoff THEN 'voided_source_tax_adjustment_required'
             WHEN source.source_exact IS DISTINCT FROM true THEN 'tax_source_evidence_changed'
             WHEN source.rule_exact IS DISTINCT FROM true THEN 'tax_rule_evidence_not_current'
             WHEN source.earlier_posted_evidence THEN 'tax_adjustment_reconciliation_required'
             ELSE 'tax_liability_protected_posting_incomplete' END, source.account_id
    FROM tax_state source WHERE source.evidence_id IS NULL OR source.void_at_cutoff
        OR source.source_exact IS DISTINCT FROM true OR source.rule_exact IS DISTINCT FROM true
        OR source.earlier_posted_evidence OR (source.tax_due > 0 AND NOT source.posted_exact AND NOT source.covered_by_adjustment)
    UNION ALL
    SELECT movement.source_type, movement.source_id, movement.effective_date, movement.amount,
        'tax_movement_protected_posting_incomplete', NULL::uuid
    FROM accounting.legacy_tax_movement_proof movement CROSS JOIN period
    WHERE movement.effective_date BETWEEN period.start_date AND period.end_date AND NOT movement.posted_exact;
$$;

CREATE OR REPLACE FUNCTION accounting.period_legacy_source_blockers(p_period_id UUID)
RETURNS TABLE(source_type TEXT, source_id UUID, effective_date DATE, amount NUMERIC(18,2), reason TEXT, account_id UUID)
LANGUAGE sql VOLATILE SET search_path = pg_catalog AS $$
    WITH period AS (
        SELECT start_date, end_date FROM accounting.fiscal_periods WHERE id = p_period_id
    ), collection_state AS (
        SELECT source.*, period.start_date, period.end_date,
            (source.voided_at AT TIME ZONE 'Asia/Manila')::date AS void_date,
            source.is_voided AND (source.voided_at AT TIME ZONE 'Asia/Manila')::date <= period.end_date
              AND EXISTS (SELECT 1 FROM lending.collection_transaction_voids void
                          WHERE void.transaction_id = source.id AND void.voided_at = source.voided_at) AS void_at_cutoff,
            EXISTS (SELECT 1 FROM accounting.journal_entries journal
                    WHERE journal.source_event_key = 'collection:' || source.id::text
                       OR journal.source_event_key LIKE 'eir_accrual:collection:' || source.id::text || '%')
              OR EXISTS (SELECT 1 FROM accounting.regular_journal_draft_preparations prepared WHERE prepared.transaction_id = source.id)
              OR EXISTS (SELECT 1 FROM accounting.seven_by_seven_journal_draft_preparations prepared WHERE prepared.transaction_id = source.id) AS has_accounting,
            accounting.legacy_regular_collection_posted_exact(source.id)
              OR EXISTS (SELECT 1 FROM accounting.seven_by_seven_journal_posting_status audit
                         JOIN accounting.journal_entries journal ON journal.id = audit.journal_entry_id
                         JOIN accounting.fiscal_periods assigned ON assigned.id = journal.fiscal_period_id
                         WHERE audit.transaction_id = source.id AND audit.posted_audit_exact
                           AND audit.loan_id = source.loan_id AND audit.client_id = source.client_id
                           AND audit.source_cash_amount = source.applied_amount AND audit.posting_date = source.collection_date
                           AND journal.posting_date = audit.posting_date AND journal.fiscal_period_id = audit.fiscal_period_id
                           AND journal.posting_date BETWEEN assigned.start_date AND assigned.end_date) AS posted_exact,
            accounting.legacy_regular_collection_reversed_exact(source.id, period.end_date)
              OR EXISTS (SELECT 1 FROM accounting.seven_by_seven_journal_reversal_status audit
                         JOIN accounting.journal_entries journal ON journal.id = audit.reversal_journal_entry_id
                         WHERE audit.transaction_id = source.id AND audit.reversal_audit_exact
                           AND audit.reversal_posting_date <= period.end_date
                           AND journal.posting_date = audit.reversal_posting_date
                           AND accounting.legacy_journal_reversal_exact(audit.original_journal_entry_id, audit.reversal_journal_entry_id)) AS reversed_exact
        FROM lending.collection_transactions source CROSS JOIN period
        WHERE source.collection_date BETWEEN period.start_date AND period.end_date
           OR (source.voided_at AT TIME ZONE 'Asia/Manila')::date BETWEEN period.start_date AND period.end_date
    ), collection_blockers AS (
        SELECT 'collection'::text AS source_type, source.id AS source_id,
            CASE WHEN source.collection_date BETWEEN source.start_date AND source.end_date THEN source.collection_date ELSE source.void_date END AS effective_date,
            source.amount, CASE
                WHEN source.funding_source = 'treasury_receipt' THEN 'treasury_collection_application_mapping_required'
                WHEN source.amount <> source.applied_amount + source.unallocated_amount THEN 'collection_allocation_inconsistent'
                WHEN source.unallocated_amount > 0 THEN 'collection_unallocated_liability_mapping_required'
                WHEN source.entry_type = 'pass' THEN 'nonfinancial_collection_has_accounting'
                WHEN source.void_at_cutoff THEN 'collection_void_accounting_incomplete'
                ELSE 'collection_protected_posting_incomplete' END AS reason,
            source.funding_account_id AS account_id
        FROM collection_state source
        WHERE NOT (
            (source.entry_type = 'pass' AND source.amount = 0 AND source.applied_amount = 0 AND source.unallocated_amount = 0 AND NOT source.has_accounting)
            OR (source.void_at_cutoff AND NOT source.has_accounting AND source.funding_source = 'collector_cash')
            OR (source.funding_source = 'collector_cash' AND source.amount > 0
                AND source.amount = source.applied_amount AND source.unallocated_amount = 0 AND source.posted_exact
                AND (NOT source.void_at_cutoff OR source.reversed_exact))
        )
    ), release_state AS (
        SELECT source.*, period.start_date, period.end_date, cancellation.reversal_posting_date,
            wallet.account_id,
            EXISTS (SELECT 1 FROM accounting.loan_disbursement_journal_posting_status audit
                    JOIN accounting.journal_entries journal ON journal.id = audit.journal_entry_id
                    JOIN accounting.fiscal_periods assigned ON assigned.id = journal.fiscal_period_id
                    WHERE audit.disbursement_event_id = source.id AND audit.posted_audit_exact
                      AND audit.loan_id = source.loan_id AND audit.client_id = source.client_id
                      AND audit.amount = source.cash_disbursed_amount AND source.principal_snapshot = audit.amount
                      AND source.settlement_amount = 0 AND source.other_deduction_amount = 0
                      AND source.event_kind = 'new_loan_release' AND audit.posting_date = source.business_date
                      AND audit.credit_account_system_key = source.funding_account_system_key
                      AND audit.debit_account_system_key = 'loans_receivable_regular'
                      AND journal.source_type = 'loan_disbursement' AND journal.source_reference = source.id::text
                      AND journal.source_event_key = 'loan_disbursement:' || source.id::text
                      AND journal.posting_date = audit.posting_date AND journal.fiscal_period_id = audit.fiscal_period_id
                      AND journal.posting_date BETWEEN assigned.start_date AND assigned.end_date) AS posted_exact,
            EXISTS (SELECT 1 FROM accounting.loan_disbursement_cancellation_status audit
                    JOIN accounting.journal_entries journal ON journal.id = audit.reversal_journal_entry_id
                    WHERE audit.disbursement_event_id = source.id AND audit.cancelled_reversal_audit_exact
                      AND audit.reversal_posting_date <= period.end_date AND journal.posting_date = audit.reversal_posting_date
                      AND journal.source_type = 'loan_disbursement_cancellation_reversal'
                      AND accounting.legacy_journal_reversal_exact(audit.original_journal_entry_id, audit.reversal_journal_entry_id)) AS reversed_exact,
            EXISTS (SELECT 1 FROM accounting.loan_disbursement_journal_draft_preparations prepared WHERE prepared.disbursement_event_id = source.id)
              OR EXISTS (SELECT 1 FROM accounting.journal_entries journal WHERE journal.source_event_key = 'loan_disbursement:' || source.id::text) AS has_accounting
        FROM lending.loan_disbursement_events source CROSS JOIN period
        LEFT JOIN lending.loan_disbursement_cancellations cancellation ON cancellation.disbursement_event_id = source.id
        LEFT JOIN treasury.loan_payouts wallet ON wallet.loan_id = source.loan_id AND wallet.status <> 'cancelled'
        WHERE source.business_date BETWEEN period.start_date AND period.end_date
           OR cancellation.reversal_posting_date BETWEEN period.start_date AND period.end_date
           OR (source.voided_at AT TIME ZONE 'Asia/Manila')::date BETWEEN period.start_date AND period.end_date
    ), release_blockers AS (
        SELECT 'loan_disbursement', source.id,
            CASE WHEN source.business_date BETWEEN source.start_date AND source.end_date THEN source.business_date
                 ELSE coalesce(source.reversal_posting_date, (source.voided_at AT TIME ZONE 'Asia/Manila')::date) END,
            source.cash_disbursed_amount, CASE WHEN source.account_id IS NOT NULL THEN 'treasury_loan_payout_mapping_required'
                WHEN source.event_kind <> 'new_loan_release' THEN 'renewal_execution_posting_required'
                WHEN source.reversal_posting_date <= source.end_date THEN 'loan_disbursement_reversal_incomplete'
                ELSE 'loan_disbursement_protected_posting_incomplete' END, source.account_id
        FROM release_state source WHERE NOT (
            (source.is_voided AND (source.voided_at AT TIME ZONE 'Asia/Manila')::date <= source.end_date
               AND NOT source.has_accounting AND source.account_id IS NULL)
            OR (source.account_id IS NULL AND source.posted_exact
                AND (source.reversal_posting_date IS NULL OR source.reversal_posting_date > source.end_date OR source.reversed_exact)
                AND (NOT source.is_voided OR (source.voided_at AT TIME ZONE 'Asia/Manila')::date > source.end_date OR source.reversed_exact))
        )
    ), remittance_state AS (
        SELECT source.*, period.start_date, period.end_date,
            coalesce(source.custody_transferred_at, source.received_at) AS custody_date,
            evidence.id AS evidence_id, evidence.business_date AS transfer_date,
            EXISTS (SELECT 1 FROM accounting.remittance_transfer_journal_status audit
                    JOIN accounting.journal_entries journal ON journal.id = audit.journal_entry_id
                    JOIN accounting.fiscal_periods assigned ON assigned.id = journal.fiscal_period_id
                    WHERE audit.remittance_id = source.id AND audit.transfer_evidence_id = evidence.id
                      AND audit.posted_audit_exact AND audit.amount = source.total_amount
                      AND audit.posting_date = evidence.business_date
                      AND journal.posting_date = audit.posting_date AND journal.fiscal_period_id = audit.fiscal_period_id
                      AND journal.posting_date BETWEEN assigned.start_date AND assigned.end_date
                      AND (audit.reversal_id IS NULL OR audit.reversal_posting_date > period.end_date)
                      AND audit.debit_account_system_key = evidence.destination_account_system_key
                      AND audit.credit_account_system_key = 'cash_collector_custody'
                      AND evidence.total_amount_snapshot = source.total_amount
                      AND evidence.collector_user_id_snapshot = source.collector_user_id
                      AND evidence.recipient_user_id_snapshot = source.recipient_user_id
                      AND evidence.custody_user_id_snapshot = source.custody_user_id
                      AND evidence.custody_transferred_at_snapshot = source.custody_transferred_at
                      AND evidence.collection_date_snapshot = source.collection_date
                      AND evidence.remittance_number_snapshot = source.remittance_number
                      AND evidence.transferred_at >= source.custody_transferred_at
                      AND evidence.business_date <= period.end_date) AS posted_exact
        FROM lending.collection_remittances source CROSS JOIN period
        LEFT JOIN accounting.remittance_transfer_evidence evidence ON evidence.remittance_id = source.id
          AND (NOT evidence.is_voided OR (evidence.voided_at AT TIME ZONE 'Asia/Manila')::date > period.end_date)
        WHERE source.status = 'received' AND source.total_amount > 0
          AND ((coalesce(source.custody_transferred_at, source.received_at) AT TIME ZONE 'Asia/Manila')::date BETWEEN period.start_date AND period.end_date
            OR evidence.business_date BETWEEN period.start_date AND period.end_date
            OR EXISTS (SELECT 1 FROM accounting.remittance_transfer_journal_status audit
                       WHERE audit.remittance_id = source.id AND audit.reversal_posting_date BETWEEN period.start_date AND period.end_date))
    ), sources AS (
        SELECT * FROM collection_blockers
        UNION ALL SELECT * FROM release_blockers
        UNION ALL SELECT * FROM accounting.period_legacy_assessment_blockers(p_period_id)
        UNION ALL
        SELECT 'remittance_transfer', source.id,
            CASE WHEN (source.custody_date AT TIME ZONE 'Asia/Manila')::date BETWEEN source.start_date AND source.end_date
                 THEN (source.custody_date AT TIME ZONE 'Asia/Manila')::date ELSE coalesce(source.transfer_date, source.end_date) END,
            source.total_amount, 'remittance_transfer_protected_posting_incomplete', NULL::uuid
        FROM remittance_state source WHERE NOT source.posted_exact
        UNION ALL
        SELECT 'loan_renewal_execution', source.id, source.business_date, source.old_loan_settlement_amount,
            'renewal_execution_posting_required', wallet.account_id
        FROM lending.loan_renewal_execution_events source CROSS JOIN period
        LEFT JOIN treasury.loan_payouts wallet ON wallet.loan_id = source.new_loan_id AND wallet.status <> 'cancelled'
        WHERE source.business_date BETWEEN period.start_date AND period.end_date
          AND (NOT source.is_voided OR (source.voided_at AT TIME ZONE 'Asia/Manila')::date > period.end_date)
        UNION ALL
        -- These are actual custody observations before a disbursement/execution
        -- adapter exists. An approved request alone is never an actual source.
        SELECT 'renewal_cash_custody', source.id, (movement.effective_at AT TIME ZONE 'Asia/Manila')::date,
            source.net_release_amount, 'renewal_cash_custody_mapping_required', wallet.account_id
        FROM lending.client_renewal_requests source CROSS JOIN period
        CROSS JOIN LATERAL (VALUES (source.cash_released_to_collector_at), (source.collector_cash_received_at),
                                  (source.cash_given_to_client_at), (source.client_cash_confirmed_at)) movement(effective_at)
        LEFT JOIN treasury.loan_payouts wallet ON wallet.renewal_request_id = source.id AND wallet.status <> 'cancelled'
        WHERE (movement.effective_at AT TIME ZONE 'Asia/Manila')::date BETWEEN period.start_date AND period.end_date
    )
    SELECT DISTINCT sources.source_type, sources.source_id, sources.effective_date,
        sources.amount::numeric(18,2), sources.reason, sources.account_id FROM sources
    ORDER BY sources.effective_date, sources.source_type, sources.source_id;
$$;

CREATE OR REPLACE FUNCTION accounting.assert_period_legacy_source_complete(p_period_id UUID)
RETURNS VOID LANGUAGE plpgsql VOLATILE SET search_path = pg_catalog AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM accounting.fiscal_periods WHERE id = p_period_id) THEN
        RAISE EXCEPTION 'Accounting period was not found.';
    END IF;
    IF current_setting('transaction_isolation') <> 'read committed' THEN
        RAISE EXCEPTION 'Source-complete period close requires a READ COMMITTED transaction.';
    END IF;
    -- Fixed order for all legacy entry points, retained until transaction end.
    -- A wait is followed by a fresh VOLATILE source query. Late actual-money
    -- recording stays possible after a successful close and remains reportable.
    LOCK TABLE
        lending.client_renewal_requests, lending.collection_remittances,
        lending.collection_transaction_voids, lending.collection_transactions,
        lending.loan_disbursement_cancellations, lending.loan_disbursement_events,
        lending.loan_renewal_execution_events, lending.loans,
        accounting.accounts, accounting.fiscal_periods, accounting.journal_entries, accounting.journal_lines,
        accounting.loan_disbursement_journal_draft_preparations,
        accounting.loan_disbursement_journal_postings, accounting.loan_disbursement_journal_reversals,
        accounting.regular_journal_draft_preparations, accounting.regular_journal_draft_preparation_entries,
        accounting.regular_journal_posting_sets, accounting.regular_journal_posting_entries,
        accounting.regular_journal_reversal_sets, accounting.regular_journal_reversal_entries,
        accounting.remittance_transfer_evidence, accounting.remittance_transfer_journal_preparations,
        accounting.remittance_transfer_journal_postings, accounting.remittance_transfer_journal_reversals,
        accounting.seven_by_seven_journal_draft_preparations,
        accounting.seven_by_seven_journal_postings, accounting.seven_by_seven_journal_posting_lines,
        accounting.seven_by_seven_journal_reversals, accounting.seven_by_seven_journal_reversal_lines,
        accounting.ecl_quantitative_measurements,
        accounting.v1_tax_rule_evidence, accounting.v1_dst_evidence, accounting.v1_percentage_tax_evidence,
        accounting.v1_tax_liability_preparations, accounting.v1_tax_liability_postings,
        accounting.v1_tax_return_evidence, accounting.v1_tax_return_liability_items,
        accounting.v1_tax_payment_evidence, accounting.v1_tax_settlement_preparations, accounting.v1_tax_settlement_postings,
        accounting.v1_tax_adjustment_evidence, accounting.v1_tax_adjustment_preparations, accounting.v1_tax_adjustment_postings,
        accounting.v1_tax_additional_amendment_evidence, accounting.v1_tax_additional_liability_preparations, accounting.v1_tax_additional_liability_postings,
        accounting.v1_tax_additional_payment_evidence, accounting.v1_tax_additional_settlement_preparations, accounting.v1_tax_additional_settlement_postings,
        accounting.v1_tax_recoverable_refund_evidence, accounting.v1_tax_recoverable_refund_preparations, accounting.v1_tax_recoverable_refund_postings,
        accounting.v1_tax_recoverable_credit_evidence, accounting.v1_tax_recoverable_credit_preparations, accounting.v1_tax_recoverable_credit_postings,
        treasury.loan_payouts
    IN SHARE MODE;
    IF EXISTS (SELECT 1 FROM accounting.period_legacy_source_blockers(p_period_id)) THEN
        RAISE EXCEPTION 'Accounting period has an unreconciled legacy source; review authorized lending and accounting evidence.' USING ERRCODE = '23514';
    END IF;
END;
$$;

DO $$ BEGIN
    IF to_regprocedure('accounting.prepare_period_close_initial_source_snapshot(uuid,uuid)') IS NULL THEN
        ALTER FUNCTION accounting.prepare_period_close(UUID, UUID) RENAME TO prepare_period_close_initial_source_snapshot;
    END IF;
END; $$;
CREATE OR REPLACE FUNCTION accounting.prepare_period_close(p_period_id UUID, p_actor_user_id UUID)
RETURNS UUID LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    PERFORM accounting.require_period_close_management_actor(p_actor_user_id, 'accounting.period.close.prepare');
    PERFORM pg_advisory_xact_lock(hashtextextended('period-close:' || p_period_id::text, 0));
    PERFORM 1 FROM accounting.fiscal_periods WHERE id = p_period_id FOR UPDATE;
    PERFORM accounting.assert_period_legacy_source_complete(p_period_id);
    RETURN accounting.prepare_period_close_initial_source_snapshot(p_period_id, p_actor_user_id);
END;
$$;

CREATE OR REPLACE FUNCTION accounting.guard_period_legacy_source_completeness()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF TG_TABLE_NAME = 'fiscal_periods' THEN
        IF NEW.status IN ('review','closed') AND NEW.status IS DISTINCT FROM OLD.status THEN
            PERFORM accounting.assert_period_legacy_source_complete(NEW.id);
        END IF;
    ELSE
        PERFORM accounting.assert_period_legacy_source_complete(NEW.fiscal_period_id);
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS accounting_period_legacy_transition_guard ON accounting.fiscal_periods;
CREATE TRIGGER accounting_period_legacy_transition_guard BEFORE UPDATE ON accounting.fiscal_periods
FOR EACH ROW EXECUTE FUNCTION accounting.guard_period_legacy_source_completeness();
DROP TRIGGER IF EXISTS accounting_period_legacy_preparation_guard ON accounting.period_close_preparations;
CREATE TRIGGER accounting_period_legacy_preparation_guard BEFORE INSERT ON accounting.period_close_preparations
FOR EACH ROW EXECUTE FUNCTION accounting.guard_period_legacy_source_completeness();
DROP TRIGGER IF EXISTS accounting_period_legacy_transition_commit_guard ON accounting.fiscal_periods;
CREATE CONSTRAINT TRIGGER accounting_period_legacy_transition_commit_guard AFTER UPDATE ON accounting.fiscal_periods
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION accounting.guard_period_legacy_source_completeness();
DROP TRIGGER IF EXISTS accounting_period_legacy_preparation_commit_guard ON accounting.period_close_preparations;
CREATE CONSTRAINT TRIGGER accounting_period_legacy_preparation_commit_guard AFTER INSERT ON accounting.period_close_preparations
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION accounting.guard_period_legacy_source_completeness();

DO $$ DECLARE role_name text; function_name text; BEGIN
    FOREACH role_name IN ARRAY ARRAY['PUBLIC','anon','authenticated'] LOOP
        IF role_name = 'PUBLIC' OR EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            FOREACH function_name IN ARRAY ARRAY[
                'legacy_journal_reversal_exact(uuid,uuid)', 'legacy_regular_collection_posted_exact(uuid)',
                'legacy_regular_collection_reversed_exact(uuid,date)', 'period_legacy_source_blockers(uuid)',
                'legacy_two_line_posted_exact(uuid,text,text,text,date,uuid,uuid,uuid,numeric,uuid,uuid)',
                'legacy_tax_liability_posted_exact(text,uuid)', 'period_legacy_assessment_blockers(uuid)',
                'assert_period_legacy_source_complete(uuid)', 'guard_period_legacy_source_completeness()',
                'prepare_period_close_initial_source_snapshot(uuid,uuid)', 'prepare_period_close(uuid,uuid)'] LOOP
                EXECUTE format('REVOKE ALL ON FUNCTION accounting.%s FROM %s', function_name,
                    CASE WHEN role_name = 'PUBLIC' THEN 'PUBLIC' ELSE quote_ident(role_name) END);
            END LOOP;
            EXECUTE format('REVOKE ALL ON accounting.legacy_tax_evidence_sources, accounting.legacy_tax_movement_proof FROM %s',
                CASE WHEN role_name = 'PUBLIC' THEN 'PUBLIC' ELSE quote_ident(role_name) END);
        END IF;
    END LOOP;
END; $$;

COMMENT ON FUNCTION accounting.period_legacy_source_blockers(UUID) IS
'Raw legacy lending/custody and tax source reconciliation, with explicit period-end EIR/ECL assessment blockers. Treasury account_id remains internal authorization scope. Does not certify as-of measurement completeness or require valid unpaid liabilities to be zero.';

COMMIT;
