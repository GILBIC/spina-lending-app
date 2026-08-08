BEGIN;

INSERT INTO core.permissions (code, description)
VALUES (
    'accounting.cutover.manage',
    'Create and manage the protected opening-balance cutover workbook without posting it'
)
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code = 'accounting.cutover.manage'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.opening_balance_workbooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cutover_date DATE NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'review_ready')),
    profit_loss_policy_confirmed BOOLEAN NOT NULL DEFAULT false,
    profit_loss_policy_note TEXT,
    created_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    updated_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS accounting.opening_balance_workbook_lines (
    workbook_id UUID NOT NULL
        REFERENCES accounting.opening_balance_workbooks(id) ON DELETE RESTRICT,
    account_id UUID NOT NULL
        REFERENCES accounting.accounts(id) ON DELETE RESTRICT,
    source_reference_amount NUMERIC(18,2),
    source_basis TEXT NOT NULL,
    requirement_type TEXT NOT NULL
        CHECK (requirement_type IN (
            'manual_required',
            'reconciliation_required',
            'calculation_required',
            'assessment_required'
        )),
    guidance TEXT NOT NULL,
    proposed_debit NUMERIC(18,2),
    proposed_credit NUMERIC(18,2),
    verification_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (verification_status IN ('pending', 'verified')),
    evidence_note TEXT,
    updated_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (workbook_id, account_id),
    CHECK (proposed_debit IS NULL OR proposed_debit >= 0),
    CHECK (proposed_credit IS NULL OR proposed_credit >= 0),
    CHECK (NOT (
        coalesce(proposed_debit, 0) > 0
        AND coalesce(proposed_credit, 0) > 0
    ))
);

CREATE TABLE IF NOT EXISTS accounting.opening_balance_workbook_audit (
    id BIGSERIAL PRIMARY KEY,
    workbook_id UUID NOT NULL,
    account_code TEXT,
    event_type TEXT NOT NULL
        CHECK (event_type IN (
            'workbook_created',
            'line_updated',
            'policy_updated',
            'status_changed'
        )),
    actor_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    before_state JSONB,
    after_state JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS opening_balance_workbook_audit_workbook_idx
    ON accounting.opening_balance_workbook_audit (workbook_id, created_at DESC);

CREATE OR REPLACE FUNCTION accounting.guard_opening_balance_workbook_audit()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Opening-balance workbook audit records are immutable.';
END;
$$;

DROP TRIGGER IF EXISTS opening_balance_workbook_audit_guard
    ON accounting.opening_balance_workbook_audit;
CREATE TRIGGER opening_balance_workbook_audit_guard
BEFORE UPDATE OR DELETE ON accounting.opening_balance_workbook_audit
FOR EACH ROW EXECUTE FUNCTION accounting.guard_opening_balance_workbook_audit();

CREATE OR REPLACE FUNCTION accounting.guard_opening_balance_workbook_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF coalesce(
        current_setting('accounting.cutover_write_allowed', true),
        ''
    ) <> 'on' THEN
        RAISE EXCEPTION 'Opening-balance workbook changes must use the protected accounting functions.';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS opening_balance_workbooks_write_guard
    ON accounting.opening_balance_workbooks;
CREATE TRIGGER opening_balance_workbooks_write_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.opening_balance_workbooks
FOR EACH ROW EXECUTE FUNCTION accounting.guard_opening_balance_workbook_write();

DROP TRIGGER IF EXISTS opening_balance_workbook_lines_write_guard
    ON accounting.opening_balance_workbook_lines;
CREATE TRIGGER opening_balance_workbook_lines_write_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.opening_balance_workbook_lines
FOR EACH ROW EXECUTE FUNCTION accounting.guard_opening_balance_workbook_write();

DROP VIEW IF EXISTS accounting.opening_balance_cutover_summary;
DROP VIEW IF EXISTS accounting.opening_balance_cutover_worksheet;
DROP VIEW IF EXISTS accounting.opening_balance_cutover_source_reference;
DROP VIEW IF EXISTS accounting.cutover_readiness_summary;

CREATE VIEW accounting.opening_balance_cutover_source_reference AS
WITH source_values(
    account_code,
    source_reference_amount,
    source_basis,
    requirement_type,
    guidance
) AS (
    VALUES
        (
            '1010',
            NULL::numeric,
            'manual_required',
            'manual_required',
            'Enter the actual office cash count at the approved cutover date.'
        ),
        (
            '1020',
            (
                SELECT coalesce(sum(t.amount), 0)::numeric
                FROM lending.collection_transactions t
                WHERE t.is_voided = false
                  AND t.is_locked = false
                  AND t.remittance_id IS NULL
                  AND t.entry_type <> 'pass'
            ),
            'collection_custody_reference',
            'reconciliation_required',
            'Source reference is unlocked unremitted collection cash. Reconcile it to the physical collector-custody count before cutover.'
        ),
        (
            '1030',
            (
                SELECT coalesce(sum(r.total_amount), 0)::numeric
                FROM lending.collection_remittances r
                WHERE r.status = 'received'
            ),
            'received_remittance_reference',
            'reconciliation_required',
            'Received remittances are a custody reference only. Confirm whether each amount is in office cash, bank, or GCash before assigning an opening balance.'
        ),
        (
            '1100',
            (
                SELECT coalesce(sum(r.operational_balance), 0)::numeric
                FROM accounting.loan_cutover_readiness r
                WHERE r.status = 'active'
                  AND r.calculation_mode = 'fixed_daily'
            ),
            'regular_operational_reference',
            'calculation_required',
            'Operational Regular balance is reference-only. Derive the PFRS amortized-cost carrying amount using the effective-interest schedule before opening-balance posting.'
        ),
        (
            '1110',
            (
                SELECT coalesce(sum(r.operational_balance), 0)::numeric
                FROM accounting.loan_cutover_readiness r
                WHERE r.status = 'active'
                  AND r.calculation_mode = 'seven_by_seven'
            ),
            '7x7_principal_reference',
            'calculation_required',
            '7x7 principal outstanding is a source reference. Derive the accounting carrying amount from the validated contractual cash-flow schedule before posting.'
        ),
        (
            '1120',
            NULL::numeric,
            'accounting_schedule_required',
            'calculation_required',
            'Derive accrued interest receivable at the cutover date from the approved Regular and 7x7 accounting schedules. Do not reuse cash collected as income.'
        ),
        (
            '1190',
            NULL::numeric,
            'ecl_assessment_required',
            'assessment_required',
            'Complete the opening expected-credit-loss assessment separately from contractual interest and principal balances.'
        ),
        (
            '2000',
            NULL::numeric,
            'manual_required',
            'manual_required',
            'Enter verified accounts payable outstanding at the cutover date.'
        ),
        (
            '2100',
            NULL::numeric,
            'manual_required',
            'manual_required',
            'Enter verified tax liabilities at the cutover date. Tax accounting remains separate from PFRS loan measurement.'
        ),
        (
            '3000',
            NULL::numeric,
            'manual_required',
            'manual_required',
            'Enter verified contributed capital at the cutover date.'
        ),
        (
            '3100',
            NULL::numeric,
            'manual_required',
            'manual_required',
            'Enter verified retained earnings or the approved conversion balance after the cutover policy is finalized.'
        )
)
SELECT
    account.id AS account_id,
    account.code AS account_code,
    account.system_key,
    account.name AS account_name,
    account.account_type,
    account.normal_balance,
    source.source_reference_amount,
    source.source_basis,
    source.requirement_type,
    source.guidance
FROM source_values source
JOIN accounting.accounts account ON account.code = source.account_code
ORDER BY account.code;

CREATE OR REPLACE FUNCTION accounting.create_opening_balance_workbook(
    p_cutover_date DATE,
    p_actor_user_id UUID
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    new_workbook_id UUID;
    blocked_count BIGINT;
BEGIN
    IF p_cutover_date IS NULL THEN
        RAISE EXCEPTION 'Cutover date is required.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM accounting.opening_balance_workbooks
        WHERE cutover_date = p_cutover_date
    ) THEN
        RAISE EXCEPTION 'An opening-balance workbook already exists for this cutover date.';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM accounting.fiscal_periods
        WHERE status = 'open'
          AND p_cutover_date BETWEEN start_date AND end_date
    ) THEN
        RAISE EXCEPTION 'The cutover date must be inside an open accounting period.';
    END IF;

    SELECT count(*) FILTER (
        WHERE status = 'active' AND readiness_status = 'blocked'
    )
    INTO blocked_count
    FROM accounting.loan_cutover_readiness;

    IF blocked_count > 0 THEN
        RAISE EXCEPTION 'Blocked loan sources must be resolved before creating the opening-balance workbook.';
    END IF;

    PERFORM set_config('accounting.cutover_write_allowed', 'on', true);

    INSERT INTO accounting.opening_balance_workbooks (
        cutover_date,
        created_by_user_id,
        updated_by_user_id
    )
    VALUES (p_cutover_date, p_actor_user_id, p_actor_user_id)
    RETURNING id INTO new_workbook_id;

    INSERT INTO accounting.opening_balance_workbook_lines (
        workbook_id,
        account_id,
        source_reference_amount,
        source_basis,
        requirement_type,
        guidance,
        updated_by_user_id
    )
    SELECT
        new_workbook_id,
        source.account_id,
        source.source_reference_amount,
        source.source_basis,
        source.requirement_type,
        source.guidance,
        p_actor_user_id
    FROM accounting.opening_balance_cutover_source_reference source;

    INSERT INTO accounting.opening_balance_workbook_audit (
        workbook_id,
        event_type,
        actor_user_id,
        after_state
    )
    VALUES (
        new_workbook_id,
        'workbook_created',
        p_actor_user_id,
        jsonb_build_object(
            'cutover_date', p_cutover_date,
            'line_count', (
                SELECT count(*)
                FROM accounting.opening_balance_workbook_lines
                WHERE workbook_id = new_workbook_id
            ),
            'source_snapshot', (
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'account_code', account.code,
                        'source_reference_amount', line.source_reference_amount,
                        'source_basis', line.source_basis,
                        'requirement_type', line.requirement_type
                    ) ORDER BY account.code
                )
                FROM accounting.opening_balance_workbook_lines line
                JOIN accounting.accounts account ON account.id = line.account_id
                WHERE line.workbook_id = new_workbook_id
            )
        )
    );

    RETURN new_workbook_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.update_opening_balance_workbook_line(
    p_workbook_id UUID,
    p_account_code TEXT,
    p_proposed_debit NUMERIC,
    p_proposed_credit NUMERIC,
    p_verification_status TEXT,
    p_evidence_note TEXT,
    p_actor_user_id UUID
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    current_status TEXT;
    target_account_id UUID;
    before_row JSONB;
    normalized_note TEXT;
BEGIN
    SELECT status
    INTO current_status
    FROM accounting.opening_balance_workbooks
    WHERE id = p_workbook_id
    FOR UPDATE;

    IF current_status IS NULL THEN
        RAISE EXCEPTION 'Opening-balance workbook was not found.';
    END IF;
    IF current_status <> 'draft' THEN
        RAISE EXCEPTION 'Only a draft opening-balance workbook can be edited.';
    END IF;

    IF p_verification_status NOT IN ('pending', 'verified') THEN
        RAISE EXCEPTION 'Unsupported opening-balance verification status.';
    END IF;
    IF coalesce(p_proposed_debit, 0) < 0 OR coalesce(p_proposed_credit, 0) < 0 THEN
        RAISE EXCEPTION 'Opening-balance amounts cannot be negative.';
    END IF;
    IF coalesce(p_proposed_debit, 0) > 0 AND coalesce(p_proposed_credit, 0) > 0 THEN
        RAISE EXCEPTION 'An opening-balance line cannot contain both a debit and a credit amount.';
    END IF;

    normalized_note := nullif(btrim(coalesce(p_evidence_note, '')), '');
    IF p_verification_status = 'verified' THEN
        IF p_proposed_debit IS NULL AND p_proposed_credit IS NULL THEN
            RAISE EXCEPTION 'A verified opening-balance line requires an explicit amount, including zero when appropriate.';
        END IF;
        IF normalized_note IS NULL OR length(normalized_note) < 3 THEN
            RAISE EXCEPTION 'A verified opening-balance line requires a short evidence or reconciliation note.';
        END IF;
    END IF;

    SELECT line.account_id, to_jsonb(line)
    INTO target_account_id, before_row
    FROM accounting.opening_balance_workbook_lines line
    JOIN accounting.accounts account ON account.id = line.account_id
    WHERE line.workbook_id = p_workbook_id
      AND account.code = p_account_code;

    IF target_account_id IS NULL THEN
        RAISE EXCEPTION 'Opening-balance workbook account was not found.';
    END IF;

    PERFORM set_config('accounting.cutover_write_allowed', 'on', true);

    UPDATE accounting.opening_balance_workbook_lines
    SET proposed_debit = p_proposed_debit,
        proposed_credit = p_proposed_credit,
        verification_status = p_verification_status,
        evidence_note = normalized_note,
        updated_by_user_id = p_actor_user_id,
        updated_at = now()
    WHERE workbook_id = p_workbook_id
      AND account_id = target_account_id;

    UPDATE accounting.opening_balance_workbooks
    SET updated_by_user_id = p_actor_user_id,
        updated_at = now()
    WHERE id = p_workbook_id;

    INSERT INTO accounting.opening_balance_workbook_audit (
        workbook_id,
        account_code,
        event_type,
        actor_user_id,
        before_state,
        after_state
    )
    SELECT
        p_workbook_id,
        p_account_code,
        'line_updated',
        p_actor_user_id,
        before_row,
        to_jsonb(line)
    FROM accounting.opening_balance_workbook_lines line
    WHERE line.workbook_id = p_workbook_id
      AND line.account_id = target_account_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.update_opening_balance_workbook_policy(
    p_workbook_id UUID,
    p_confirmed BOOLEAN,
    p_policy_note TEXT,
    p_actor_user_id UUID
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    current_row accounting.opening_balance_workbooks%ROWTYPE;
    normalized_note TEXT;
BEGIN
    SELECT *
    INTO current_row
    FROM accounting.opening_balance_workbooks
    WHERE id = p_workbook_id
    FOR UPDATE;

    IF current_row.id IS NULL THEN
        RAISE EXCEPTION 'Opening-balance workbook was not found.';
    END IF;
    IF current_row.status <> 'draft' THEN
        RAISE EXCEPTION 'Only a draft opening-balance workbook can be edited.';
    END IF;

    normalized_note := nullif(btrim(coalesce(p_policy_note, '')), '');
    IF p_confirmed AND (normalized_note IS NULL OR length(normalized_note) < 5) THEN
        RAISE EXCEPTION 'Confirming the P&L migration policy requires a policy note.';
    END IF;

    PERFORM set_config('accounting.cutover_write_allowed', 'on', true);

    UPDATE accounting.opening_balance_workbooks
    SET profit_loss_policy_confirmed = p_confirmed,
        profit_loss_policy_note = normalized_note,
        updated_by_user_id = p_actor_user_id,
        updated_at = now()
    WHERE id = p_workbook_id;

    INSERT INTO accounting.opening_balance_workbook_audit (
        workbook_id,
        event_type,
        actor_user_id,
        before_state,
        after_state
    )
    SELECT
        p_workbook_id,
        'policy_updated',
        p_actor_user_id,
        to_jsonb(current_row),
        to_jsonb(workbook)
    FROM accounting.opening_balance_workbooks workbook
    WHERE workbook.id = p_workbook_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.set_opening_balance_workbook_status(
    p_workbook_id UUID,
    p_status TEXT,
    p_actor_user_id UUID
)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    current_row accounting.opening_balance_workbooks%ROWTYPE;
    line_count BIGINT;
    verified_count BIGINT;
    total_debit NUMERIC(18,2);
    total_credit NUMERIC(18,2);
    blocked_count BIGINT;
BEGIN
    IF p_status NOT IN ('draft', 'review_ready') THEN
        RAISE EXCEPTION 'Unsupported opening-balance workbook status.';
    END IF;

    SELECT *
    INTO current_row
    FROM accounting.opening_balance_workbooks
    WHERE id = p_workbook_id
    FOR UPDATE;

    IF current_row.id IS NULL THEN
        RAISE EXCEPTION 'Opening-balance workbook was not found.';
    END IF;
    IF current_row.status = p_status THEN
        RETURN current_row.status;
    END IF;
    IF current_row.status = 'draft' AND p_status <> 'review_ready' THEN
        RAISE EXCEPTION 'A draft opening-balance workbook can only move to review ready.';
    END IF;
    IF current_row.status = 'review_ready' AND p_status <> 'draft' THEN
        RAISE EXCEPTION 'A review-ready opening-balance workbook can only be reopened to draft.';
    END IF;

    IF p_status = 'review_ready' THEN
        SELECT
            count(*),
            count(*) FILTER (
                WHERE verification_status = 'verified'
                  AND (proposed_debit IS NOT NULL OR proposed_credit IS NOT NULL)
            ),
            coalesce(sum(coalesce(proposed_debit, 0)), 0),
            coalesce(sum(coalesce(proposed_credit, 0)), 0)
        INTO line_count, verified_count, total_debit, total_credit
        FROM accounting.opening_balance_workbook_lines
        WHERE workbook_id = p_workbook_id;

        IF line_count = 0 OR verified_count <> line_count THEN
            RAISE EXCEPTION 'Every opening-balance workbook line must be explicitly verified before review.';
        END IF;
        IF total_debit <= 0 OR abs(total_debit - total_credit) > 0.01 THEN
            RAISE EXCEPTION 'The opening-balance workbook must balance before review.';
        END IF;
        IF current_row.profit_loss_policy_confirmed = false THEN
            RAISE EXCEPTION 'Confirm the P&L migration policy before review.';
        END IF;
        IF NOT EXISTS (
            SELECT 1
            FROM accounting.fiscal_periods
            WHERE status = 'open'
              AND current_row.cutover_date BETWEEN start_date AND end_date
        ) THEN
            RAISE EXCEPTION 'The cutover date must remain inside an open accounting period before review.';
        END IF;

        SELECT count(*) FILTER (
            WHERE status = 'active' AND readiness_status = 'blocked'
        )
        INTO blocked_count
        FROM accounting.loan_cutover_readiness;
        IF blocked_count > 0 THEN
            RAISE EXCEPTION 'Blocked loan sources must be resolved before review.';
        END IF;
    END IF;

    PERFORM set_config('accounting.cutover_write_allowed', 'on', true);

    UPDATE accounting.opening_balance_workbooks
    SET status = p_status,
        updated_by_user_id = p_actor_user_id,
        updated_at = now()
    WHERE id = p_workbook_id;

    INSERT INTO accounting.opening_balance_workbook_audit (
        workbook_id,
        event_type,
        actor_user_id,
        before_state,
        after_state
    )
    SELECT
        p_workbook_id,
        'status_changed',
        p_actor_user_id,
        to_jsonb(current_row),
        to_jsonb(workbook)
    FROM accounting.opening_balance_workbooks workbook
    WHERE workbook.id = p_workbook_id;

    RETURN p_status;
END;
$$;

CREATE VIEW accounting.opening_balance_cutover_worksheet AS
WITH latest_workbook AS (
    SELECT *
    FROM accounting.opening_balance_workbooks
    ORDER BY created_at DESC
    LIMIT 1
), workbook_rows AS (
    SELECT
        workbook.id AS workbook_id,
        account.code AS account_code,
        account.system_key,
        account.name AS account_name,
        account.account_type,
        account.normal_balance,
        line.source_reference_amount,
        line.source_basis,
        line.requirement_type AS readiness_status,
        line.guidance,
        line.proposed_debit,
        line.proposed_credit,
        line.verification_status,
        line.evidence_note
    FROM latest_workbook workbook
    JOIN accounting.opening_balance_workbook_lines line
      ON line.workbook_id = workbook.id
    JOIN accounting.accounts account ON account.id = line.account_id
), source_rows AS (
    SELECT
        NULL::uuid AS workbook_id,
        source.account_code,
        source.system_key,
        source.account_name,
        source.account_type,
        source.normal_balance,
        source.source_reference_amount,
        source.source_basis,
        source.requirement_type AS readiness_status,
        source.guidance,
        NULL::numeric AS proposed_debit,
        NULL::numeric AS proposed_credit,
        'pending'::text AS verification_status,
        NULL::text AS evidence_note
    FROM accounting.opening_balance_cutover_source_reference source
    WHERE NOT EXISTS (SELECT 1 FROM latest_workbook)
)
SELECT * FROM workbook_rows
UNION ALL
SELECT * FROM source_rows
ORDER BY account_code;

CREATE VIEW accounting.opening_balance_cutover_summary AS
WITH latest_workbook AS (
    SELECT *
    FROM accounting.opening_balance_workbooks
    ORDER BY created_at DESC
    LIMIT 1
), line_summary AS (
    SELECT
        count(*) AS line_count,
        count(*) FILTER (WHERE source_reference_amount IS NOT NULL)
            AS source_reference_count,
        count(*) FILTER (WHERE readiness_status = 'manual_required')
            AS manual_required_count,
        count(*) FILTER (WHERE readiness_status = 'reconciliation_required')
            AS reconciliation_required_count,
        count(*) FILTER (WHERE readiness_status = 'calculation_required')
            AS calculation_required_count,
        count(*) FILTER (WHERE readiness_status = 'assessment_required')
            AS assessment_required_count,
        count(*) FILTER (
            WHERE verification_status = 'verified'
              AND (proposed_debit IS NOT NULL OR proposed_credit IS NOT NULL)
        ) AS verified_line_count,
        count(*) FILTER (
            WHERE verification_status <> 'verified'
               OR (proposed_debit IS NULL AND proposed_credit IS NULL)
        ) AS pending_line_count,
        coalesce(sum(coalesce(proposed_debit, 0)), 0)::numeric(18,2)
            AS total_debit,
        coalesce(sum(coalesce(proposed_credit, 0)), 0)::numeric(18,2)
            AS total_credit
    FROM accounting.opening_balance_cutover_worksheet
), blocker_summary AS (
    SELECT count(*) FILTER (
        WHERE status = 'active' AND readiness_status = 'blocked'
    ) AS blocked_count
    FROM accounting.loan_cutover_readiness
)
SELECT
    workbook.id AS workbook_id,
    workbook.cutover_date,
    coalesce(workbook.status, 'source_review_required')::text AS worksheet_status,
    line.line_count AS worksheet_line_count,
    line.source_reference_count,
    line.manual_required_count,
    line.reconciliation_required_count,
    line.calculation_required_count,
    line.assessment_required_count,
    coalesce(NOT workbook.profit_loss_policy_confirmed, true)
        AS profit_loss_migration_policy_required,
    coalesce(workbook.profit_loss_policy_confirmed, false)
        AS profit_loss_policy_confirmed,
    workbook.profit_loss_policy_note,
    line.verified_line_count,
    line.pending_line_count,
    line.total_debit,
    line.total_credit,
    abs(line.total_debit - line.total_credit)::numeric(18,2) AS balance_variance,
    (
        line.total_debit > 0
        AND abs(line.total_debit - line.total_credit) <= 0.01
    ) AS worksheet_balanced,
    (
        workbook.id IS NOT NULL
        AND workbook.status = 'draft'
        AND line.pending_line_count = 0
        AND line.total_debit > 0
        AND abs(line.total_debit - line.total_credit) <= 0.01
        AND workbook.profit_loss_policy_confirmed = true
        AND blocker.blocked_count = 0
    ) AS ready_for_review,
    false AS ready_to_post,
    false AS opening_balance_posting_enabled,
    false AS automatic_source_posting_enabled
FROM line_summary line
CROSS JOIN blocker_summary blocker
LEFT JOIN latest_workbook workbook ON true;

CREATE VIEW accounting.cutover_readiness_summary AS
WITH workbook AS (
    SELECT status
    FROM accounting.opening_balance_workbooks
    ORDER BY created_at DESC
    LIMIT 1
)
SELECT
    count(*) FILTER (WHERE readiness.status = 'active') AS active_loan_count,
    count(*) FILTER (
        WHERE readiness.status = 'active'
          AND readiness.readiness_status = 'source_ready'
    ) AS source_ready_count,
    0::bigint AS contract_validation_count,
    count(*) FILTER (
        WHERE readiness.status = 'active'
          AND readiness.readiness_status = 'blocked'
    ) AS blocked_count,
    EXISTS (SELECT 1 FROM workbook) AS opening_balances_configured,
    false AS automatic_source_posting_enabled,
    CASE
        WHEN count(*) FILTER (
            WHERE readiness.status = 'active'
              AND readiness.readiness_status = 'blocked'
        ) > 0 THEN 'blocked'
        WHEN NOT EXISTS (SELECT 1 FROM workbook)
            THEN 'opening_balances_required'
        WHEN (SELECT status FROM workbook) = 'review_ready'
            THEN 'opening_balance_review_ready'
        ELSE 'opening_balance_workbook_draft'
    END AS overall_status
FROM accounting.loan_cutover_readiness readiness;

COMMIT;
