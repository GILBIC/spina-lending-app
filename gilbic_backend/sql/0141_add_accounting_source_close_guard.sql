BEGIN;

-- Initial defensive coverage only. No Treasury/Collector GL adapter exists yet.
-- Never infer a posting from an operational source_link, a settled status, or a
-- net-zero movement total. This inventory is evidence, not a financial total:
-- a cash event and its liability evidence can both describe the same money.
CREATE OR REPLACE FUNCTION accounting.period_source_blockers(p_period_id UUID)
RETURNS TABLE (
    source_type TEXT,
    source_id UUID,
    effective_date DATE,
    amount NUMERIC(18,2),
    reason TEXT,
    account_id UUID
)
LANGUAGE sql
VOLATILE
SET search_path = pg_catalog
AS $$
    WITH period AS (
        SELECT start_date, end_date
        FROM accounting.fiscal_periods WHERE id = p_period_id
    ), sources AS (
        -- An event is authoritative even if its movement lines, application,
        -- source link, journal draft or GL posting have never been prepared.
        SELECT 'treasury_event'::text AS source_type, event.id AS source_id,
            (event.effective_at AT TIME ZONE 'Asia/Manila')::date AS effective_date,
            (event.amount + event.fee)::numeric(18,2) AS amount,
            'treasury_gl_mapping_required'::text AS reason,
            event.account_id
        FROM treasury.events event
        UNION ALL
        SELECT 'treasury_correction', line.id,
            (line.effective_at AT TIME ZONE 'Asia/Manila')::date,
            line.signed_amount, 'treasury_correction_gl_mapping_required', line.account_id
        FROM treasury.movement_lines line WHERE line.component = 'correction'
        UNION ALL
        SELECT 'treasury_opening', opening.id,
            (opening.cutoff AT TIME ZONE 'Asia/Manila')::date,
            opening.amount, 'treasury_opening_gl_mapping_required', opening.account_id
        FROM treasury.opening_positions opening
        WHERE opening.status IN ('active', 'superseded') AND opening.amount <> 0
        UNION ALL
        SELECT 'collector_opening', opening.id,
            ((opening.payload->>'cutoff')::timestamptz AT TIME ZONE 'Asia/Manila')::date,
            (opening.payload->>'amount')::numeric(18,2), 'collector_opening_gl_mapping_required', opening.account_id
        FROM treasury.collector_openings opening
        WHERE opening.payload->>'status' = 'active'
        UNION ALL
        -- Opening entries retain their original cutoff. Other immutable entries
        -- have no reviewed GL recognition date yet, so the recorded business date
        -- is a conservative blocker, not an invented journal posting date.
        SELECT 'collector_entry', entry.id,
            (CASE WHEN entry.payload->>'kind' = 'opening'
                THEN coalesce((opening.payload->>'cutoff')::timestamptz, entry.created_at)
                ELSE coalesce(incoming.effective_at, outgoing.effective_at, entry.created_at)
             END AT TIME ZONE 'Asia/Manila')::date,
            (entry.payload->>'amount')::numeric(18,2), 'collector_entry_gl_mapping_required', entry.account_id
        FROM treasury.collector_entries entry
        JOIN treasury.collector_credits credit ON credit.id = entry.credit_id
        LEFT JOIN treasury.collector_openings opening ON opening.id = credit.opening_anchor_id
        LEFT JOIN treasury.collector_actions action ON action.id = (entry.payload->>'action_id')::uuid
        LEFT JOIN treasury.events outgoing ON outgoing.id = action.event_id
        LEFT JOIN treasury.events incoming ON incoming.id = (entry.payload->>'incoming_event_id')::uuid
        UNION ALL
        -- Include original recognition facts independently of their optional
        -- append-only entry so missing entry preparation cannot hide a liability.
        SELECT 'collector_credit', credit.id,
            (coalesce((opening.payload->>'cutoff')::timestamptz, credit.created_at)
                AT TIME ZONE 'Asia/Manila')::date,
            (credit.payload->>'recognized_amount')::numeric(18,2), 'collector_credit_gl_mapping_required', credit.account_id
        FROM treasury.collector_credits credit
        LEFT JOIN treasury.collector_openings opening ON opening.id = credit.opening_anchor_id
        UNION ALL
        SELECT 'collector_resolution', resolution.id,
            (resolution.created_at AT TIME ZONE 'Asia/Manila')::date,
            (resolution.payload->>'amount')::numeric(18,2), 'collector_resolution_gl_mapping_required', resolution.account_id
        FROM treasury.collector_resolutions resolution
        UNION ALL
        SELECT 'collector_settlement', settlement.id,
            ((settlement.payload->>'accepted_at')::timestamptz AT TIME ZONE 'Asia/Manila')::date,
            (settlement.payload->>'gross_obligation')::numeric(18,2), 'collector_settlement_gl_mapping_required', settlement.account_id
        FROM treasury.collector_settlements settlement
        -- An all-PASS settlement has no cash or liability effect. Gross-positive
        -- settlements still need reconciliation even when refunds net cash to0.
        WHERE settlement.event_id IS NOT NULL
           OR coalesce((settlement.payload->>'gross_obligation')::numeric, -1) <> 0
           OR coalesce((settlement.payload->>'physical_amount')::numeric, -1) <> 0
           OR coalesce((settlement.payload->>'authorized_credit_amount')::numeric, -1) <> 0
        UNION ALL
        SELECT 'collector_case', item.id,
            (coalesce((opening.payload->>'cutoff')::timestamptz,
                      (settlement.payload->>'accepted_at')::timestamptz, item.created_at)
                AT TIME ZONE 'Asia/Manila')::date,
            (item.payload->>'received_excess_amount')::numeric(18,2), 'collector_case_gl_mapping_required', item.account_id
        FROM treasury.collector_cases item
        LEFT JOIN treasury.collector_openings opening ON opening.id = item.opening_anchor_id
        LEFT JOIN treasury.collector_settlements settlement ON settlement.id = item.settlement_id
    )
    SELECT sources.source_type, sources.source_id, sources.effective_date, sources.amount, sources.reason, sources.account_id
    FROM sources CROSS JOIN period
    WHERE sources.effective_date BETWEEN period.start_date AND period.end_date
    ORDER BY sources.effective_date, sources.source_type, sources.source_id;
$$;

CREATE OR REPLACE FUNCTION accounting.assert_period_source_complete(p_period_id UUID)
RETURNS VOID
LANGUAGE plpgsql
VOLATILE
SET search_path = pg_catalog
AS $$
DECLARE
    blocker RECORD;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM accounting.fiscal_periods WHERE id = p_period_id) THEN
        RAISE EXCEPTION 'Accounting period was not found.';
    END IF;
    -- The fresh inventory query after obtaining the locks must see writers that
    -- committed before admission. A pre-existing repeatable-read snapshot cannot
    -- provide that guarantee. Statement reports can still use repeatable read.
    IF current_setting('transaction_isolation') <> 'read committed' THEN
        RAISE EXCEPTION 'Source-complete period close requires a READ COMMITTED transaction.';
    END IF;

    -- SHARE conflicts with actual source INSERT/UPDATE. Writers use different
    -- table orders, so never wait while holding a partial set of source locks:
    -- yield the close attempt, preserving the active actual-money transaction.
    -- The exception subtransaction releases every partially acquired lock.
    -- Retain locks to transaction end, including preparation and final close.
    -- No source insert trigger rejects actual-money evidence after the close:
    -- late evidence remains visible in period_source_blockers and close state.
    BEGIN
      LOCK TABLE
        treasury.collector_actions,
        treasury.collector_cases,
        treasury.collector_credits,
        treasury.collector_entries,
        treasury.collector_openings,
        treasury.collector_resolutions,
        treasury.collector_settlements,
        treasury.events,
        treasury.movement_lines,
        treasury.opening_positions
      IN SHARE MODE NOWAIT;
    EXCEPTION WHEN lock_not_available THEN
        RAISE EXCEPTION 'Source activity is in progress; retry period close.'
            USING ERRCODE = '23514';
    END;

    SELECT * INTO blocker FROM accounting.period_source_blockers(p_period_id) LIMIT 1;
    IF FOUND THEN
        -- Period-management permission does not grant private wallet history.
        -- Exact source details are available only through an authorized reader.
        RAISE EXCEPTION 'Accounting period has an unreconciled source; review authorized Treasury or Collector evidence.'
            USING ERRCODE = '23514';
    END IF;
END;
$$;

-- Preserve the existing ledger implementation without copying hundreds of lines.
-- The wrapper also validates idempotent preparation reads after late evidence.
DO $$
BEGIN
    IF to_regprocedure('accounting.prepare_period_close_ledger_snapshot(uuid,uuid)') IS NULL THEN
        ALTER FUNCTION accounting.prepare_period_close(UUID, UUID)
            RENAME TO prepare_period_close_ledger_snapshot;
    END IF;
END;
$$;
CREATE OR REPLACE FUNCTION accounting.prepare_period_close(p_period_id UUID, p_actor_user_id UUID)
RETURNS UUID
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    PERFORM accounting.require_period_close_management_actor(p_actor_user_id, 'accounting.period.close.prepare');
    PERFORM pg_advisory_xact_lock(hashtextextended('period-close:' || p_period_id::text, 0));
    PERFORM 1 FROM accounting.fiscal_periods WHERE id = p_period_id FOR UPDATE;
    PERFORM accounting.assert_period_source_complete(p_period_id);
    RETURN accounting.prepare_period_close_ledger_snapshot(p_period_id, p_actor_user_id);
END;
$$;

-- Guard database entry points without duplicating the protected close lifecycle.
-- A failure of the final transition rolls back the close journal and its audit.
CREATE OR REPLACE FUNCTION accounting.guard_period_source_completeness()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    IF TG_TABLE_NAME = 'fiscal_periods' THEN
        IF NEW.status IN ('review', 'closed') AND NEW.status IS DISTINCT FROM OLD.status THEN
            PERFORM accounting.assert_period_source_complete(NEW.id);
        END IF;
    ELSE
        PERFORM accounting.assert_period_source_complete(NEW.fiscal_period_id);
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_period_source_transition_guard ON accounting.fiscal_periods;
CREATE TRIGGER accounting_period_source_transition_guard
BEFORE UPDATE ON accounting.fiscal_periods
FOR EACH ROW EXECUTE FUNCTION accounting.guard_period_source_completeness();

DROP TRIGGER IF EXISTS accounting_period_source_preparation_guard ON accounting.period_close_preparations;
CREATE TRIGGER accounting_period_source_preparation_guard
BEFORE INSERT ON accounting.period_close_preparations
FOR EACH ROW EXECUTE FUNCTION accounting.guard_period_source_completeness();

-- Also recheck at commit if the caller itself writes a source after its close
-- command within the same transaction. Other sessions remain serialized by the
-- relation locks; recording late evidence in a later transaction is permitted.
DROP TRIGGER IF EXISTS accounting_period_source_transition_commit_guard ON accounting.fiscal_periods;
CREATE CONSTRAINT TRIGGER accounting_period_source_transition_commit_guard
AFTER UPDATE ON accounting.fiscal_periods DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION accounting.guard_period_source_completeness();

DROP TRIGGER IF EXISTS accounting_period_source_preparation_commit_guard ON accounting.period_close_preparations;
CREATE CONSTRAINT TRIGGER accounting_period_source_preparation_commit_guard
AFTER INSERT ON accounting.period_close_preparations DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION accounting.guard_period_source_completeness();

-- Always derive late/history status from authoritative sources, including closed
-- periods. Do not rewrite immutable close snapshots when later evidence arrives.
CREATE OR REPLACE VIEW accounting.period_source_close_state WITH (security_invoker = true) AS
SELECT period.id AS fiscal_period_id,
       period.status AS fiscal_period_status,
       blockers.blocker_count,
       CASE WHEN blockers.blocker_count = 0 THEN 'initial_source_gate_clear'
            WHEN period.status = 'closed' THEN 'closed_source_review_required'
            ELSE 'blocked_unreconciled_sources' END AS source_close_status,
       'treasury_collector_initial_v1'::text AS coverage_policy,
       false AS comprehensive_source_coverage
FROM accounting.fiscal_periods period
CROSS JOIN LATERAL (
    SELECT count(*) AS blocker_count FROM accounting.period_source_blockers(period.id)
) blockers;

REVOKE ALL ON FUNCTION accounting.period_source_blockers(UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION accounting.assert_period_source_complete(UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION accounting.guard_period_source_completeness() FROM PUBLIC;
REVOKE ALL ON FUNCTION accounting.prepare_period_close_ledger_snapshot(UUID, UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION accounting.prepare_period_close(UUID, UUID) FROM PUBLIC;
REVOKE ALL ON accounting.period_source_close_state FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON FUNCTION accounting.period_source_blockers(UUID),
            accounting.assert_period_source_complete(UUID), accounting.guard_period_source_completeness(),
            accounting.prepare_period_close_ledger_snapshot(UUID, UUID), accounting.prepare_period_close(UUID, UUID) FROM anon;
        REVOKE ALL ON accounting.period_source_close_state FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON FUNCTION accounting.period_source_blockers(UUID),
            accounting.assert_period_source_complete(UUID), accounting.guard_period_source_completeness(),
            accounting.prepare_period_close_ledger_snapshot(UUID, UUID), accounting.prepare_period_close(UUID, UUID) FROM authenticated;
        REVOKE ALL ON accounting.period_source_close_state FROM authenticated;
    END IF;
END;
$$;

COMMENT ON FUNCTION accounting.period_source_blockers(UUID) IS
'Initial Treasury/Collector completeness blockers only, scoped to Manila source dates. Missing legacy lending/EIR/ECL/tax reconciliation remains explicit. Amounts are evidence amounts, not an additive financial total. Prior-period outstanding balances are not themselves blockers.';
COMMENT ON VIEW accounting.period_source_close_state IS
'Live narrow source-coverage status, including late evidence affecting immutable closed periods. initial_source_gate_clear does not certify complete accounting readiness.';

-- Preserve the existing API shape while making aggregate readiness truthful.
CREATE OR REPLACE VIEW accounting.period_close_queue AS
SELECT
    period.id AS fiscal_period_id,
    period.label,
    period.start_date,
    period.end_date,
    period.status AS fiscal_period_status,
    period.closed_by_user_id,
    period.closed_at,
    preparation.id AS preparation_id,
    preparation.journal_entry_id,
    preparation.temporary_account_count,
    preparation.net_income,
    preparation.retained_earnings_balance_before,
    preparation.close_digest,
    posting.id AS close_posting_id,
    posting.entry_number AS closing_entry_number,
    posting.retained_earnings_balance_after,
    CASE
        WHEN coverage.blocker_count > 0 AND period.status = 'closed' THEN 'blocked_closed_source_review_required'
        WHEN coverage.blocker_count > 0 THEN 'blocked_unreconciled_sources'
        WHEN period.status = 'closed' AND posting.id IS NOT NULL THEN 'closed_protected'
        WHEN period.status = 'closed' THEN 'closed_legacy_without_protected_close_audit'
        WHEN period.status = 'open' AND draft_state.draft_count > 0 THEN 'blocked_open_drafts'
        WHEN period.status = 'open' THEN 'ready_for_review'
        WHEN period.status = 'review' AND preparation.id IS NULL AND draft_state.draft_count > 0 THEN 'blocked_review_drafts'
        WHEN period.status = 'review' AND preparation.id IS NULL THEN 'ready_to_prepare'
        WHEN period.status = 'review' AND preparation.id IS NOT NULL THEN 'prepared_confirmation_required'
        ELSE 'blocked_unknown_state'
    END AS close_status,
    CASE
        WHEN coverage.blocker_count > 0 AND period.status = 'closed' THEN 'This period remains closed. Later Treasury or Collector evidence requires accounting review; the original close is unchanged.'
        WHEN coverage.blocker_count > 0 THEN 'Treasury or Collector sources have no supported General Ledger reconciliation. Review the authorized source evidence before closing.'
        WHEN period.status = 'closed' AND posting.id IS NOT NULL THEN NULL
        WHEN period.status = 'closed' THEN 'This period predates protected A6.3 close audit; it remains immutable and is not retroactively rewritten.'
        WHEN period.status = 'open' AND draft_state.draft_count > 0 THEN 'Resolve every journal draft before moving the period to review.'
        WHEN period.status = 'open' THEN 'Move the period to review to freeze ordinary posting before formal close preparation.'
        WHEN period.status = 'review' AND preparation.id IS NULL AND draft_state.draft_count > 0 THEN 'Unexpected review-period drafts must be resolved before close preparation.'
        WHEN period.status = 'review' AND preparation.id IS NOT NULL THEN 'Exact Management confirmation is required to post retained earnings and atomically close the period.'
        ELSE NULL
    END AS close_blocker,
    true AS protected_period_close_enabled,
    true AS retained_earnings_close_enabled,
    true AS closed_period_posting_protection_enabled,
    false AS period_reopen_enabled,
    false AS automatic_source_posting
FROM accounting.fiscal_periods period
JOIN accounting.period_source_close_state coverage ON coverage.fiscal_period_id = period.id
LEFT JOIN accounting.period_close_preparations preparation
  ON preparation.fiscal_period_id = period.id
LEFT JOIN accounting.period_close_postings posting
  ON posting.fiscal_period_id = period.id
LEFT JOIN LATERAL (
    SELECT count(*)::integer AS draft_count
    FROM accounting.journal_entries journal
    WHERE journal.fiscal_period_id = period.id
      AND journal.status = 'draft'
) draft_state ON true;

CREATE OR REPLACE VIEW accounting.period_close_summary AS
SELECT
    count(*)::bigint AS period_count,
    count(*) FILTER (WHERE close_status = 'ready_for_review')::bigint AS ready_for_review_count,
    count(*) FILTER (WHERE close_status = 'ready_to_prepare')::bigint AS ready_to_prepare_count,
    count(*) FILTER (WHERE close_status = 'prepared_confirmation_required')::bigint AS prepared_count,
    count(*) FILTER (WHERE fiscal_period_status = 'closed' AND close_posting_id IS NOT NULL)::bigint AS protected_closed_count,
    count(*) FILTER (WHERE close_status LIKE 'blocked_%')::bigint AS blocked_count,
    coalesce(sum(net_income) FILTER (WHERE fiscal_period_status = 'closed' AND close_posting_id IS NOT NULL), 0)::numeric(18,2) AS closed_net_income_total,
    true AS protected_period_close_enabled,
    true AS retained_earnings_close_enabled,
    true AS closed_period_posting_protection_enabled,
    false AS period_reopen_enabled,
    false AS automatic_source_posting
FROM accounting.period_close_queue;


COMMIT;
