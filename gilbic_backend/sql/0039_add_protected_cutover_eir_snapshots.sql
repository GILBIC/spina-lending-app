BEGIN;

-- Stage 5D.2: immutable per-loan EIR cutover evidence captured only when
-- Management prepares the protected opening-balance journal. This migration
-- creates schema/controls only. It deliberately backfills no historical
-- preparation and inserts zero snapshot rows by itself.

CREATE TABLE IF NOT EXISTS accounting.opening_balance_loan_snapshot_batches (
    workbook_id UUID PRIMARY KEY
        REFERENCES accounting.opening_balance_workbooks(id) ON DELETE RESTRICT,
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    measurement_policy_version TEXT NOT NULL,
    expected_active_loan_count BIGINT NOT NULL CHECK (expected_active_loan_count >= 0),
    captured_loan_count BIGINT NOT NULL CHECK (captured_loan_count >= 0),
    captured_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (btrim(measurement_policy_version) <> ''),
    CHECK (captured_loan_count = expected_active_loan_count)
);

CREATE TABLE IF NOT EXISTS accounting.opening_balance_loan_measurement_snapshots (
    workbook_id UUID NOT NULL
        REFERENCES accounting.opening_balance_workbooks(id) ON DELETE RESTRICT,
    journal_entry_id UUID NOT NULL
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL
        REFERENCES lending.loans(id) ON DELETE RESTRICT,
    cutover_date DATE NOT NULL,
    calculation_mode TEXT NOT NULL,
    loan_policy_version TEXT NOT NULL,
    measurement_policy_version TEXT NOT NULL,
    date_released DATE,
    due_date DATE,
    days_elapsed INTEGER,
    principal NUMERIC(18,2),
    operational_balance NUMERIC(18,2),
    daily_eir NUMERIC(18,12),
    daily_eir_percent NUMERIC(18,8),
    contractual_cash_due NUMERIC(18,2),
    actual_cash_received NUMERIC(18,2),
    effective_interest_income NUMERIC(18,2),
    loan_component NUMERIC(18,2),
    accrued_interest_component NUMERIC(18,2),
    gross_carrying_amount NUMERIC(18,2),
    contractual_unpaid_interest NUMERIC(18,2),
    measurement_status TEXT NOT NULL,
    measurement_note TEXT,
    captured_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (workbook_id, loan_id),
    UNIQUE (journal_entry_id, loan_id),
    CHECK (btrim(calculation_mode) <> ''),
    CHECK (btrim(loan_policy_version) <> ''),
    CHECK (btrim(measurement_policy_version) <> ''),
    CHECK (btrim(measurement_status) <> ''),
    CHECK (
        measurement_status <> 'measured'
        OR (
            daily_eir IS NOT NULL AND daily_eir > 0
            AND loan_component IS NOT NULL AND loan_component >= 0
            AND accrued_interest_component IS NOT NULL AND accrued_interest_component >= 0
            AND gross_carrying_amount IS NOT NULL AND gross_carrying_amount >= 0
            AND loan_component + accrued_interest_component = gross_carrying_amount
        )
    )
);

CREATE INDEX IF NOT EXISTS opening_balance_loan_snapshot_loan_idx
    ON accounting.opening_balance_loan_measurement_snapshots (loan_id, cutover_date);

CREATE OR REPLACE FUNCTION accounting.guard_opening_balance_loan_snapshot_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(
            current_setting('accounting.opening_balance_snapshot_write_allowed', true),
            ''
       ) = 'on'
       AND coalesce(
            current_setting('accounting.opening_balance_prepare_allowed', true),
            ''
       ) = 'on' THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'Protected opening-balance loan EIR snapshots are immutable and may only be captured during protected journal preparation.';
END;
$$;

DROP TRIGGER IF EXISTS opening_balance_loan_snapshot_batch_guard
    ON accounting.opening_balance_loan_snapshot_batches;
CREATE TRIGGER opening_balance_loan_snapshot_batch_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.opening_balance_loan_snapshot_batches
FOR EACH ROW EXECUTE FUNCTION accounting.guard_opening_balance_loan_snapshot_write();

DROP TRIGGER IF EXISTS opening_balance_loan_measurement_snapshot_guard
    ON accounting.opening_balance_loan_measurement_snapshots;
CREATE TRIGGER opening_balance_loan_measurement_snapshot_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.opening_balance_loan_measurement_snapshots
FOR EACH ROW EXECUTE FUNCTION accounting.guard_opening_balance_loan_snapshot_write();

CREATE OR REPLACE FUNCTION accounting.capture_opening_balance_loan_eir_snapshots()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    workbook_cutover_date DATE;
    blocked_count BIGINT;
    expected_count BIGINT;
    captured_count BIGINT;
BEGIN
    -- Preparation has already created the protected journal inside this same
    -- transaction. Acquire the same source serialization boundary used by the
    -- protected posting workflow before capturing the loan-level ledger anchor.
    -- Collection/payment/void/correction writers require ROW EXCLUSIVE locks on
    -- these lending tables, so they either commit before this snapshot and are
    -- visible here, or wait until the whole preparation transaction commits.
    LOCK TABLE
        lending.loans,
        lending.loan_types,
        lending.loan_collection_state
    IN SHARE MODE;

    SELECT workbook.cutover_date
    INTO workbook_cutover_date
    FROM accounting.opening_balance_workbooks workbook
    WHERE workbook.id = NEW.workbook_id;

    IF workbook_cutover_date IS NULL THEN
        RAISE EXCEPTION 'Opening-balance workbook disappeared during protected snapshot capture.';
    END IF;

    SELECT count(*) FILTER (
        WHERE readiness.status = 'active'
          AND readiness.readiness_status = 'blocked'
    )
    INTO blocked_count
    FROM accounting.loan_cutover_readiness readiness;

    IF blocked_count > 0 THEN
        RAISE EXCEPTION 'Blocked loan sources must be resolved before protected loan EIR snapshot capture.';
    END IF;

    SELECT count(*)
    INTO expected_count
    FROM accounting.loan_cutover_readiness readiness
    WHERE readiness.status = 'active';

    PERFORM set_config(
        'accounting.opening_balance_snapshot_write_allowed',
        'on',
        true
    );

    INSERT INTO accounting.opening_balance_loan_measurement_snapshots (
        workbook_id,
        journal_entry_id,
        loan_id,
        cutover_date,
        calculation_mode,
        loan_policy_version,
        measurement_policy_version,
        date_released,
        due_date,
        days_elapsed,
        principal,
        operational_balance,
        daily_eir,
        daily_eir_percent,
        contractual_cash_due,
        actual_cash_received,
        effective_interest_income,
        loan_component,
        accrued_interest_component,
        gross_carrying_amount,
        contractual_unpaid_interest,
        measurement_status,
        measurement_note,
        captured_by_user_id
    )
    SELECT
        NEW.workbook_id,
        NEW.journal_entry_id,
        measurement.loan_id,
        workbook_cutover_date,
        measurement.calculation_mode,
        coalesce(nullif(btrim(measurement.policy_version), ''), 'unversioned'),
        'eir_cutover_v1',
        measurement.date_released,
        measurement.due_date,
        measurement.days_elapsed,
        measurement.principal,
        measurement.operational_balance,
        measurement.daily_eir,
        measurement.daily_eir_percent,
        measurement.contractual_cash_due,
        measurement.actual_cash_received,
        measurement.effective_interest_income,
        measurement.loan_component,
        measurement.accrued_interest_component,
        measurement.gross_carrying_amount,
        measurement.contractual_unpaid_interest,
        measurement.measurement_status,
        measurement.measurement_note,
        NEW.prepared_by_user_id
    FROM accounting.loan_cutover_readiness readiness
    CROSS JOIN LATERAL accounting.measure_loan_at_cutover(
        readiness.loan_id,
        workbook_cutover_date
    ) measurement
    WHERE readiness.status = 'active'
    ORDER BY measurement.loan_id;

    GET DIAGNOSTICS captured_count = ROW_COUNT;

    IF captured_count <> expected_count THEN
        RAISE EXCEPTION 'Protected loan EIR snapshot count does not match the active loan source count.';
    END IF;

    INSERT INTO accounting.opening_balance_loan_snapshot_batches (
        workbook_id,
        journal_entry_id,
        measurement_policy_version,
        expected_active_loan_count,
        captured_loan_count,
        captured_by_user_id
    )
    VALUES (
        NEW.workbook_id,
        NEW.journal_entry_id,
        'eir_cutover_v1',
        expected_count,
        captured_count,
        NEW.prepared_by_user_id
    );

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_opening_balance_loan_snapshot_capture
    ON accounting.opening_balance_journal_preparations;
CREATE TRIGGER accounting_opening_balance_loan_snapshot_capture
BEFORE INSERT ON accounting.opening_balance_journal_preparations
FOR EACH ROW EXECUTE FUNCTION accounting.capture_opening_balance_loan_eir_snapshots();

CREATE OR REPLACE VIEW accounting.opening_balance_loan_snapshot_reconciliation AS
WITH snapshot_totals AS (
    SELECT
        batch.workbook_id,
        batch.journal_entry_id,
        batch.measurement_policy_version,
        batch.expected_active_loan_count,
        batch.captured_loan_count,
        count(snapshot.loan_id)::bigint AS actual_snapshot_count,
        count(snapshot.loan_id) FILTER (
            WHERE snapshot.measurement_status <> 'measured'
        )::bigint AS review_required_count,
        coalesce(sum(snapshot.loan_component) FILTER (
            WHERE snapshot.measurement_status = 'measured'
              AND snapshot.calculation_mode = 'fixed_daily'
        ), 0)::numeric(18,2) AS regular_loan_component,
        coalesce(sum(snapshot.loan_component) FILTER (
            WHERE snapshot.measurement_status = 'measured'
              AND snapshot.calculation_mode = 'seven_by_seven'
        ), 0)::numeric(18,2) AS seven_by_seven_loan_component,
        coalesce(sum(snapshot.accrued_interest_component) FILTER (
            WHERE snapshot.measurement_status = 'measured'
        ), 0)::numeric(18,2) AS accrued_interest_component
    FROM accounting.opening_balance_loan_snapshot_batches batch
    LEFT JOIN accounting.opening_balance_loan_measurement_snapshots snapshot
      ON snapshot.workbook_id = batch.workbook_id
     AND snapshot.journal_entry_id = batch.journal_entry_id
    GROUP BY
        batch.workbook_id,
        batch.journal_entry_id,
        batch.measurement_policy_version,
        batch.expected_active_loan_count,
        batch.captured_loan_count
), journal_totals AS (
    SELECT
        batch.workbook_id,
        coalesce(sum(line.debit - line.credit) FILTER (
            WHERE account.system_key = 'loans_receivable_regular'
        ), 0)::numeric(18,2) AS journal_regular_loan_component,
        coalesce(sum(line.debit - line.credit) FILTER (
            WHERE account.system_key = 'loans_receivable_7x7'
        ), 0)::numeric(18,2) AS journal_seven_by_seven_loan_component,
        coalesce(sum(line.debit - line.credit) FILTER (
            WHERE account.system_key = 'accrued_interest_receivable'
        ), 0)::numeric(18,2) AS journal_accrued_interest_component
    FROM accounting.opening_balance_loan_snapshot_batches batch
    LEFT JOIN accounting.journal_lines line
      ON line.journal_entry_id = batch.journal_entry_id
    LEFT JOIN accounting.accounts account
      ON account.id = line.account_id
    GROUP BY batch.workbook_id
)
SELECT
    snapshot.workbook_id,
    snapshot.journal_entry_id,
    snapshot.measurement_policy_version,
    snapshot.expected_active_loan_count,
    snapshot.captured_loan_count,
    snapshot.actual_snapshot_count,
    snapshot.review_required_count,
    snapshot.regular_loan_component,
    snapshot.seven_by_seven_loan_component,
    snapshot.accrued_interest_component,
    journal.journal_regular_loan_component,
    journal.journal_seven_by_seven_loan_component,
    journal.journal_accrued_interest_component,
    (
        snapshot.expected_active_loan_count = snapshot.captured_loan_count
        AND snapshot.captured_loan_count = snapshot.actual_snapshot_count
        AND snapshot.review_required_count = 0
        AND snapshot.regular_loan_component = journal.journal_regular_loan_component
        AND snapshot.seven_by_seven_loan_component = journal.journal_seven_by_seven_loan_component
        AND snapshot.accrued_interest_component = journal.journal_accrued_interest_component
    ) AS ledger_anchor_ready,
    CASE
        WHEN snapshot.expected_active_loan_count <> snapshot.captured_loan_count
          OR snapshot.captured_loan_count <> snapshot.actual_snapshot_count
            THEN 'Protected loan snapshot count does not match the captured active-loan batch.'
        WHEN snapshot.review_required_count > 0
            THEN 'One or more protected loan snapshots still require accounting measurement review.'
        WHEN snapshot.regular_loan_component <> journal.journal_regular_loan_component
            THEN 'Protected Regular loan snapshot total does not match opening journal account 1100.'
        WHEN snapshot.seven_by_seven_loan_component <> journal.journal_seven_by_seven_loan_component
            THEN 'Protected 7x7 loan snapshot total does not match opening journal account 1110.'
        WHEN snapshot.accrued_interest_component <> journal.journal_accrued_interest_component
            THEN 'Protected accrued EIR snapshot total does not match opening journal account 1120.'
        ELSE NULL
    END AS ledger_anchor_blocker
FROM snapshot_totals snapshot
JOIN journal_totals journal
  ON journal.workbook_id = snapshot.workbook_id;

COMMENT ON TABLE accounting.opening_balance_loan_snapshot_batches IS
    'Immutable batch evidence captured transactionally when a protected opening-balance journal is prepared; migration 0039 performs no backfill.';
COMMENT ON TABLE accounting.opening_balance_loan_measurement_snapshots IS
    'Immutable per-loan Stage 5D.1 cutover EIR measurement evidence captured in the same transaction as protected opening-journal preparation.';
COMMENT ON VIEW accounting.opening_balance_loan_snapshot_reconciliation IS
    'Fail-closed reconciliation of immutable per-loan cutover EIR snapshots to opening journal accounts 1100, 1110, and 1120.';

COMMIT;
