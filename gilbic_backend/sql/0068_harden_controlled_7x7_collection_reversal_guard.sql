BEGIN;

-- Migration 0067 introduced the final fail-closed operational void guard for
-- posted protected 7x7 collections. Qualify the local UUID variables so PL/pgSQL
-- never has to resolve a name that is also a column on the reversal tables.
CREATE OR REPLACE FUNCTION accounting.guard_posted_seven_by_seven_collection_void()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    posted accounting.seven_by_seven_journal_postings%ROWTYPE;
    void_id UUID;
    matched_reversal_id UUID;
    matched_reversal_entry_id UUID;
    reversal_line_count INTEGER;
    reversal_exact_count INTEGER;
BEGIN
    IF OLD.is_voided = false AND NEW.is_voided = true THEN
        SELECT *
        INTO posted
        FROM accounting.seven_by_seven_journal_postings
        WHERE transaction_id = OLD.id;

        IF NOT FOUND THEN
            RETURN NEW;
        END IF;

        SELECT void_record.id
        INTO void_id
        FROM lending.collection_transaction_voids void_record
        WHERE void_record.transaction_id = OLD.id;

        IF void_id IS NULL THEN
            RAISE EXCEPTION 'An accounted 7x7 collection requires immutable collection-void evidence before it can be voided.';
        END IF;

        SELECT reversal.id, reversal.reversal_journal_entry_id
        INTO matched_reversal_id, matched_reversal_entry_id
        FROM accounting.seven_by_seven_journal_reversals reversal
        JOIN accounting.journal_entries journal
          ON journal.id = reversal.reversal_journal_entry_id
        WHERE reversal.transaction_id = OLD.id
          AND reversal.collection_void_id = void_id
          AND reversal.posting_id = posted.id
          AND reversal.original_journal_entry_id = posted.journal_entry_id
          AND reversal.expected_line_count = posted.coordinate_line_count
          AND reversal.total_debit = posted.total_debit
          AND reversal.total_credit = posted.total_credit
          AND journal.status = 'posted'
          AND journal.entry_number = reversal.reversal_entry_number
          AND journal.source_type = 'seven_by_seven_collection_reversal'
          AND journal.source_reference = void_id::text
          AND journal.source_event_key = reversal.reversal_source_event_key
          AND journal.reversal_of_entry_id = posted.journal_entry_id;

        IF matched_reversal_id IS NULL THEN
            RAISE EXCEPTION 'An accounted 7x7 collection cannot be voided until its protected reversing journal is posted and audited.';
        END IF;

        SELECT
            count(snapshot.line_number)::integer,
            count(snapshot.line_number) FILTER (
                WHERE EXISTS (
                    SELECT 1
                    FROM accounting.seven_by_seven_journal_posting_lines original
                    WHERE original.posting_id = posted.id
                      AND original.line_number = snapshot.line_number
                      AND original.journal_component = snapshot.journal_component
                      AND original.account_id = snapshot.account_id
                      AND original.account_system_key = snapshot.account_system_key
                      AND original.credit = snapshot.debit
                      AND original.debit = snapshot.credit
                      AND original.client_id = snapshot.client_id
                      AND original.loan_id = snapshot.loan_id
                )
                AND EXISTS (
                    SELECT 1
                    FROM accounting.journal_lines line
                    WHERE line.journal_entry_id = matched_reversal_entry_id
                      AND line.line_number = snapshot.line_number
                      AND line.account_id = snapshot.account_id
                      AND line.debit = snapshot.debit
                      AND line.credit = snapshot.credit
                      AND line.client_id = snapshot.client_id
                      AND line.loan_id = snapshot.loan_id
                )
            )::integer
        INTO reversal_line_count, reversal_exact_count
        FROM accounting.seven_by_seven_journal_reversal_lines snapshot
        WHERE snapshot.reversal_id = matched_reversal_id;

        IF reversal_line_count <> posted.coordinate_line_count
           OR reversal_exact_count <> posted.coordinate_line_count THEN
            RAISE EXCEPTION 'An accounted 7x7 collection cannot be voided because its protected reversal line audit is incomplete or not an exact debit/credit swap.';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION accounting.guard_posted_seven_by_seven_collection_void() IS
    'Fail-closed final operational void guard for posted protected 7x7 collections; requires one exact immutable controlled reversal and exact debit/credit-swapped line audit.';

COMMIT;
