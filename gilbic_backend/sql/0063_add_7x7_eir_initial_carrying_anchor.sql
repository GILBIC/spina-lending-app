BEGIN;

-- Master Issue #296: finish the protected 7x7 / EMER EIR-and-carrying-policy
-- proof before the separate preview/identity/draft/posting/reversal lifecycle.
--
-- Migration 0061 provides only a mathematical base EIR preview from a verified
-- signed-contract schedule. Migration 0062 records explicit Management
-- business-model/SPPI/measurement-category and expected-cash-flow policy
-- evidence. This migration allows a later explicit Management review to bind
-- that current policy evidence to an evidence-backed IFRS 9 initial gross
-- carrying amount and then solve the original daily EIR from the exact same
-- verified contractual schedule and that exact initial carrying amount.
--
-- The operational PHP 7-per-PHP 1,000 rule is never promoted by equality or by
-- assumption. No current carrying amount, journal line, posting or automatic
-- source posting is created here. Subsequent current carrying remains blocked
-- until the separate protected 7x7 accounting lifecycle reconciles actual
-- source cash and ledger history to this immutable initial anchor.

INSERT INTO core.permissions (code, description)
VALUES (
    'accounting.7x7_eir_anchor.manage',
    'Record or explicitly void immutable Management-reviewed 7x7 original-EIR and initial-gross-carrying anchor evidence without enabling journals or automatic posting'
)
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code = 'accounting.7x7_eir_anchor.manage'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE OR REPLACE FUNCTION accounting.seven_by_seven_eir_anchor_review_token(p_loan_id UUID)
RETURNS TEXT
LANGUAGE sql
STABLE
AS $$
    SELECT CASE
        WHEN readiness.classification_policy_evidence_ready_for_eir_promotion
         AND readiness.decision_id IS NOT NULL
         AND readiness.schedule_id IS NOT NULL
         AND readiness.current_policy_review_token IS NOT NULL
         AND readiness.base_no_prepayment_daily_eir_preview IS NOT NULL THEN
            encode(
                sha256(
                    convert_to(
                        concat_ws(
                            '|',
                            'seven_by_seven_eir_initial_carrying_anchor_readiness_v1',
                            readiness.loan_id::text,
                            readiness.loan_number,
                            readiness.loan_status,
                            readiness.principal::text,
                            readiness.date_released::text,
                            readiness.due_date::text,
                            readiness.term_days::text,
                            readiness.schedule_id::text,
                            readiness.schedule_version::text,
                            readiness.contract_reference,
                            readiness.evidence_reference,
                            readiness.decision_id::text,
                            readiness.current_policy_review_token,
                            readiness.business_model_conclusion,
                            readiness.sppi_conclusion,
                            readiness.measurement_category,
                            readiness.expected_cash_flow_policy,
                            readiness.expected_life_policy,
                            readiness.expected_life_days::text,
                            readiness.base_no_prepayment_daily_eir_preview::text
                        ),
                        'UTF8'
                    )
                ),
                'hex'
            )
        ELSE NULL
    END
    FROM accounting.seven_by_seven_classification_policy_readiness readiness
    WHERE readiness.loan_id = p_loan_id;
$$;

CREATE TABLE IF NOT EXISTS accounting.seven_by_seven_eir_initial_carrying_anchors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    policy_decision_id UUID NOT NULL
        REFERENCES accounting.seven_by_seven_policy_decisions(id) ON DELETE RESTRICT,
    schedule_id UUID NOT NULL REFERENCES lending.loan_contract_schedules(id) ON DELETE RESTRICT,
    schedule_version INTEGER NOT NULL CHECK (schedule_version > 0),
    anchor_review_token TEXT NOT NULL CHECK (anchor_review_token ~ '^[0-9a-f]{64}$'),
    policy_decision_review_token TEXT NOT NULL CHECK (
        policy_decision_review_token ~ '^[0-9a-f]{64}$'
    ),
    anchor_policy_version TEXT NOT NULL CHECK (
        anchor_policy_version = 'seven_by_seven_eir_initial_carrying_anchor_v1'
    ),
    loan_number TEXT NOT NULL CHECK (btrim(loan_number) <> ''),
    principal NUMERIC(18,2) NOT NULL CHECK (principal > 0),
    date_released DATE NOT NULL,
    due_date DATE NOT NULL,
    term_days INTEGER NOT NULL CHECK (term_days > 0),
    contract_reference TEXT NOT NULL CHECK (btrim(contract_reference) <> ''),
    contract_evidence_reference TEXT NOT NULL CHECK (btrim(contract_evidence_reference) <> ''),
    business_model_conclusion TEXT NOT NULL CHECK (business_model_conclusion = 'held_to_collect'),
    sppi_conclusion TEXT NOT NULL CHECK (sppi_conclusion = 'passes'),
    measurement_category TEXT NOT NULL CHECK (measurement_category = 'amortised_cost'),
    expected_cash_flow_policy TEXT NOT NULL CHECK (
        expected_cash_flow_policy = 'verified_no_prepayment_schedule_is_expected_cash_flow_estimate'
    ),
    expected_life_policy TEXT NOT NULL CHECK (expected_life_policy = 'contractual_term'),
    expected_life_days INTEGER NOT NULL CHECK (expected_life_days = term_days),
    principal_base_daily_eir_preview NUMERIC(24,12) NOT NULL CHECK (
        principal_base_daily_eir_preview > 0
    ),
    authoritative_initial_gross_carrying_amount NUMERIC(18,2) NOT NULL CHECK (
        authoritative_initial_gross_carrying_amount > 0
    ),
    initial_measurement_basis TEXT NOT NULL CHECK (
        initial_measurement_basis = 'management_evidence_backed_ifrs9_initial_measurement'
    ),
    initial_measurement_assessment JSONB NOT NULL CHECK (
        jsonb_typeof(initial_measurement_assessment) = 'object'
        AND initial_measurement_assessment <> '{}'::jsonb
        AND initial_measurement_assessment ? 'fair_value_basis'
        AND initial_measurement_assessment ? 'transaction_costs_assessment'
        AND initial_measurement_assessment ? 'integral_fees_assessment'
        AND initial_measurement_assessment ? 'source_documents'
    ),
    initial_measurement_evidence_reference TEXT NOT NULL CHECK (
        btrim(initial_measurement_evidence_reference) <> ''
    ),
    authoritative_daily_eir NUMERIC(24,12) NOT NULL CHECK (authoritative_daily_eir > 0),
    authoritative_daily_eir_percent NUMERIC(24,8) NOT NULL CHECK (
        authoritative_daily_eir_percent > 0
    ),
    eir_difference_from_principal_base_preview NUMERIC(24,12) NOT NULL,
    review_rationale TEXT NOT NULL CHECK (length(btrim(review_rationale)) >= 20),
    reviewed_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (due_date > date_released)
);

CREATE INDEX IF NOT EXISTS seven_by_seven_eir_anchor_loan_idx
    ON accounting.seven_by_seven_eir_initial_carrying_anchors (loan_id, reviewed_at DESC);

CREATE TABLE IF NOT EXISTS accounting.seven_by_seven_eir_initial_carrying_anchor_voids (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    anchor_id UUID NOT NULL UNIQUE
        REFERENCES accounting.seven_by_seven_eir_initial_carrying_anchors(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    void_reason TEXT NOT NULL CHECK (length(btrim(void_reason)) >= 3),
    voided_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    voided_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION accounting.guard_seven_by_seven_eir_anchor_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(current_setting('accounting.seven_by_seven_eir_anchor_insert_allowed', true), '') = 'on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION '7x7 original-EIR/initial-carrying anchor evidence is immutable and must use the protected Management review function.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_seven_by_seven_eir_anchor_guard
    ON accounting.seven_by_seven_eir_initial_carrying_anchors;
CREATE TRIGGER accounting_seven_by_seven_eir_anchor_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.seven_by_seven_eir_initial_carrying_anchors
FOR EACH ROW EXECUTE FUNCTION accounting.guard_seven_by_seven_eir_anchor_write();

CREATE OR REPLACE FUNCTION accounting.guard_seven_by_seven_eir_anchor_void_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(current_setting('accounting.seven_by_seven_eir_anchor_void_insert_allowed', true), '') = 'on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION '7x7 original-EIR/initial-carrying anchor void evidence is immutable and must use the protected void function.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_seven_by_seven_eir_anchor_void_guard
    ON accounting.seven_by_seven_eir_initial_carrying_anchor_voids;
CREATE TRIGGER accounting_seven_by_seven_eir_anchor_void_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.seven_by_seven_eir_initial_carrying_anchor_voids
FOR EACH ROW EXECUTE FUNCTION accounting.guard_seven_by_seven_eir_anchor_void_write();

CREATE OR REPLACE FUNCTION accounting.require_7x7_eir_anchor_management_actor(p_actor_user_id UUID)
RETURNS VOID
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    IF p_actor_user_id IS NULL OR NOT EXISTS (
        SELECT 1
        FROM core.users actor
        JOIN core.user_roles user_role ON user_role.user_id = actor.id
        JOIN core.role_permissions role_permission ON role_permission.role_id = user_role.role_id
        WHERE actor.id = p_actor_user_id
          AND actor.status = 'active'
          AND role_permission.permission_code = 'accounting.7x7_eir_anchor.manage'
    ) THEN
        RAISE EXCEPTION 'An active Management actor with accounting.7x7_eir_anchor.manage permission is required.';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.record_seven_by_seven_eir_initial_carrying_anchor(
    p_loan_id UUID,
    p_anchor_review_token TEXT,
    p_initial_gross_carrying_amount NUMERIC,
    p_initial_measurement_basis TEXT,
    p_initial_measurement_assessment JSONB,
    p_initial_measurement_evidence_reference TEXT,
    p_review_rationale TEXT,
    p_actor_user_id UUID
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    source_row RECORD;
    existing_row accounting.seven_by_seven_eir_initial_carrying_anchors%ROWTYPE;
    current_anchor_review_token TEXT;
    promoted_daily_eir NUMERIC(24,12);
    normalized_measurement_basis TEXT := btrim(coalesce(p_initial_measurement_basis, ''));
    normalized_evidence_reference TEXT := btrim(coalesce(p_initial_measurement_evidence_reference, ''));
    normalized_rationale TEXT := btrim(coalesce(p_review_rationale, ''));
    created_id UUID;
BEGIN
    PERFORM accounting.require_7x7_eir_anchor_management_actor(p_actor_user_id);

    IF p_loan_id IS NULL THEN
        RAISE EXCEPTION '7x7 original-EIR/initial-carrying anchor requires an exact loan identifier.';
    END IF;
    IF coalesce(p_anchor_review_token, '') !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION '7x7 EIR anchor requires the exact current 64-character review token.';
    END IF;
    IF p_initial_gross_carrying_amount IS NULL OR p_initial_gross_carrying_amount <= 0 THEN
        RAISE EXCEPTION 'A positive evidence-backed IFRS 9 initial gross carrying amount is required.';
    END IF;
    IF normalized_measurement_basis IS DISTINCT FROM 'management_evidence_backed_ifrs9_initial_measurement' THEN
        RAISE EXCEPTION 'Unsupported 7x7 initial measurement basis.';
    END IF;
    IF p_initial_measurement_assessment IS NULL
       OR jsonb_typeof(p_initial_measurement_assessment) <> 'object'
       OR p_initial_measurement_assessment = '{}'::jsonb
       OR NOT (p_initial_measurement_assessment ? 'fair_value_basis')
       OR NOT (p_initial_measurement_assessment ? 'transaction_costs_assessment')
       OR NOT (p_initial_measurement_assessment ? 'integral_fees_assessment')
       OR NOT (p_initial_measurement_assessment ? 'source_documents') THEN
        RAISE EXCEPTION 'Initial measurement assessment must explicitly document fair value, transaction costs, integral fees and source documents.';
    END IF;
    IF normalized_evidence_reference = '' OR length(normalized_rationale) < 20 THEN
        RAISE EXCEPTION 'Substantive initial-measurement evidence reference and Management rationale are required.';
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended('seven-by-seven-eir-anchor:' || p_loan_id::text, 0));

    SELECT readiness.*,
           accounting.seven_by_seven_eir_anchor_review_token(readiness.loan_id) AS current_anchor_review_token
    INTO source_row
    FROM accounting.seven_by_seven_classification_policy_readiness readiness
    WHERE readiness.loan_id = p_loan_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION '7x7 classification-policy readiness row was not found.';
    END IF;
    IF NOT source_row.classification_policy_evidence_ready_for_eir_promotion
       OR source_row.decision_id IS NULL
       OR source_row.measurement_category IS DISTINCT FROM 'amortised_cost'
       OR source_row.business_model_conclusion IS DISTINCT FROM 'held_to_collect'
       OR source_row.sppi_conclusion IS DISTINCT FROM 'passes'
       OR source_row.expected_cash_flow_policy IS DISTINCT FROM 'verified_no_prepayment_schedule_is_expected_cash_flow_estimate'
       OR source_row.expected_life_policy IS DISTINCT FROM 'contractual_term'
       OR source_row.expected_life_days IS DISTINCT FROM source_row.term_days THEN
        RAISE EXCEPTION 'Current evidence-backed 7x7 amortised-cost classification and contractual-term expected-cash-flow policy are required before EIR promotion.';
    END IF;

    current_anchor_review_token := source_row.current_anchor_review_token;
    IF current_anchor_review_token IS NULL
       OR current_anchor_review_token IS DISTINCT FROM p_anchor_review_token THEN
        RAISE EXCEPTION '7x7 EIR anchor review token is stale or does not match the current authoritative contract/policy evidence.';
    END IF;

    promoted_daily_eir := accounting.solve_verified_schedule_daily_eir_preview(
        source_row.schedule_id,
        p_initial_gross_carrying_amount
    );
    IF promoted_daily_eir IS NULL OR promoted_daily_eir <= 0 THEN
        RAISE EXCEPTION 'The verified signed-contract schedule cannot solve an EIR from the evidence-backed initial gross carrying amount.';
    END IF;

    SELECT anchor.*
    INTO existing_row
    FROM accounting.seven_by_seven_eir_initial_carrying_anchors anchor
    LEFT JOIN accounting.seven_by_seven_eir_initial_carrying_anchor_voids voided
      ON voided.anchor_id = anchor.id
    WHERE anchor.loan_id = p_loan_id AND voided.id IS NULL
    ORDER BY anchor.reviewed_at DESC
    LIMIT 1
    FOR UPDATE OF anchor;

    IF FOUND THEN
        IF existing_row.policy_decision_id = source_row.decision_id
           AND existing_row.schedule_id = source_row.schedule_id
           AND existing_row.schedule_version = source_row.schedule_version
           AND existing_row.anchor_review_token = p_anchor_review_token
           AND existing_row.authoritative_initial_gross_carrying_amount = round(p_initial_gross_carrying_amount, 2)
           AND existing_row.initial_measurement_basis = normalized_measurement_basis
           AND existing_row.initial_measurement_assessment = p_initial_measurement_assessment
           AND existing_row.initial_measurement_evidence_reference = normalized_evidence_reference
           AND existing_row.authoritative_daily_eir = promoted_daily_eir
           AND existing_row.review_rationale = normalized_rationale
           AND existing_row.reviewed_by_user_id = p_actor_user_id THEN
            RETURN existing_row.id;
        END IF;
        RAISE EXCEPTION 'Different active 7x7 original-EIR/initial-carrying anchor evidence already exists; void it explicitly before recording a correction.';
    END IF;

    PERFORM set_config('accounting.seven_by_seven_eir_anchor_insert_allowed', 'on', true);
    INSERT INTO accounting.seven_by_seven_eir_initial_carrying_anchors (
        loan_id, policy_decision_id, schedule_id, schedule_version,
        anchor_review_token, policy_decision_review_token, anchor_policy_version,
        loan_number, principal, date_released, due_date, term_days,
        contract_reference, contract_evidence_reference,
        business_model_conclusion, sppi_conclusion, measurement_category,
        expected_cash_flow_policy, expected_life_policy, expected_life_days,
        principal_base_daily_eir_preview,
        authoritative_initial_gross_carrying_amount,
        initial_measurement_basis, initial_measurement_assessment,
        initial_measurement_evidence_reference,
        authoritative_daily_eir, authoritative_daily_eir_percent,
        eir_difference_from_principal_base_preview,
        review_rationale, reviewed_by_user_id
    ) VALUES (
        source_row.loan_id, source_row.decision_id, source_row.schedule_id,
        source_row.schedule_version, p_anchor_review_token,
        source_row.decision_review_token,
        'seven_by_seven_eir_initial_carrying_anchor_v1',
        source_row.loan_number, source_row.principal, source_row.date_released,
        source_row.due_date, source_row.term_days, source_row.contract_reference,
        source_row.evidence_reference, source_row.business_model_conclusion,
        source_row.sppi_conclusion, source_row.measurement_category,
        source_row.expected_cash_flow_policy, source_row.expected_life_policy,
        source_row.expected_life_days, source_row.base_no_prepayment_daily_eir_preview,
        round(p_initial_gross_carrying_amount, 2), normalized_measurement_basis,
        p_initial_measurement_assessment, normalized_evidence_reference,
        promoted_daily_eir, round(promoted_daily_eir * 100, 8),
        promoted_daily_eir - source_row.base_no_prepayment_daily_eir_preview,
        normalized_rationale, p_actor_user_id
    ) RETURNING id INTO created_id;
    PERFORM set_config('accounting.seven_by_seven_eir_anchor_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs (actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.7x7_eir_initial_carrying_anchor.recorded',
        'seven_by_seven_eir_initial_carrying_anchor',
        created_id,
        jsonb_build_object(
            'loan_id', p_loan_id::text,
            'policy_decision_id', source_row.decision_id::text,
            'initial_gross_carrying_amount', round(p_initial_gross_carrying_amount, 2),
            'authoritative_daily_eir', promoted_daily_eir,
            'current_carrying_amount_ready', false,
            'journal_lines_enabled', false,
            'automatic_source_posting', false
        )
    );

    RETURN created_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.void_seven_by_seven_eir_initial_carrying_anchor(
    p_anchor_id UUID,
    p_actor_user_id UUID,
    p_reason TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    anchor_row accounting.seven_by_seven_eir_initial_carrying_anchors%ROWTYPE;
    existing_void accounting.seven_by_seven_eir_initial_carrying_anchor_voids%ROWTYPE;
    normalized_reason TEXT := btrim(coalesce(p_reason, ''));
    created_id UUID;
BEGIN
    PERFORM accounting.require_7x7_eir_anchor_management_actor(p_actor_user_id);
    IF length(normalized_reason) < 3 THEN
        RAISE EXCEPTION 'Enter a clear reason for voiding the 7x7 original-EIR/initial-carrying anchor.';
    END IF;

    SELECT * INTO anchor_row
    FROM accounting.seven_by_seven_eir_initial_carrying_anchors
    WHERE id = p_anchor_id
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION '7x7 original-EIR/initial-carrying anchor was not found.';
    END IF;

    SELECT * INTO existing_void
    FROM accounting.seven_by_seven_eir_initial_carrying_anchor_voids
    WHERE anchor_id = p_anchor_id
    FOR UPDATE;
    IF FOUND THEN
        IF existing_void.voided_by_user_id = p_actor_user_id
           AND existing_void.void_reason = normalized_reason THEN
            RETURN existing_void.id;
        END IF;
        RAISE EXCEPTION '7x7 original-EIR/initial-carrying anchor was already voided with different evidence.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM accounting.journal_entries journal
        WHERE journal.source_reference = p_anchor_id::text
           OR journal.source_event_key = '7x7_eir_anchor:' || anchor_row.loan_id::text
    ) THEN
        RAISE EXCEPTION '7x7 EIR anchor already has protected accounting journal history; use the future controlled correction/reversal path.';
    END IF;

    PERFORM set_config('accounting.seven_by_seven_eir_anchor_void_insert_allowed', 'on', true);
    INSERT INTO accounting.seven_by_seven_eir_initial_carrying_anchor_voids (
        anchor_id, loan_id, void_reason, voided_by_user_id
    ) VALUES (
        p_anchor_id, anchor_row.loan_id, normalized_reason, p_actor_user_id
    ) RETURNING id INTO created_id;
    PERFORM set_config('accounting.seven_by_seven_eir_anchor_void_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs (actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.7x7_eir_initial_carrying_anchor.voided',
        'seven_by_seven_eir_initial_carrying_anchor',
        p_anchor_id,
        jsonb_build_object(
            'loan_id', anchor_row.loan_id::text,
            'reason', normalized_reason,
            'journal_lines_enabled', false,
            'automatic_source_posting', false
        )
    );

    RETURN created_id;
END;
$$;

CREATE OR REPLACE VIEW accounting.seven_by_seven_eir_initial_carrying_anchor_status AS
SELECT
    anchor.*,
    voided.id AS void_id,
    voided.void_reason,
    voided.voided_by_user_id,
    voided.voided_at,
    (voided.id IS NULL) AS is_active,
    accounting.solve_verified_schedule_daily_eir_preview(
        anchor.schedule_id,
        anchor.authoritative_initial_gross_carrying_amount
    ) AS recomputed_daily_eir,
    false AS current_carrying_amount_ready,
    false AS journal_lines_enabled,
    false AS automatic_source_posting
FROM accounting.seven_by_seven_eir_initial_carrying_anchors anchor
LEFT JOIN accounting.seven_by_seven_eir_initial_carrying_anchor_voids voided
  ON voided.anchor_id = anchor.id;

CREATE OR REPLACE VIEW accounting.seven_by_seven_eir_initial_carrying_readiness AS
SELECT
    readiness.loan_id,
    readiness.loan_number,
    readiness.loan_status,
    readiness.loan_type_code,
    readiness.loan_type_name,
    readiness.principal,
    readiness.date_released,
    readiness.due_date,
    readiness.term_days,
    readiness.schedule_id,
    readiness.schedule_version,
    readiness.contract_reference,
    readiness.evidence_reference,
    readiness.decision_id AS policy_decision_id,
    readiness.decision_review_token AS policy_decision_review_token,
    readiness.business_model_conclusion,
    readiness.sppi_conclusion,
    readiness.measurement_category,
    readiness.expected_cash_flow_policy,
    readiness.expected_life_policy,
    readiness.expected_life_days,
    readiness.base_no_prepayment_daily_eir_preview AS principal_base_daily_eir_preview,
    readiness.classification_policy_evidence_ready_for_eir_promotion,
    accounting.seven_by_seven_eir_anchor_review_token(readiness.loan_id) AS current_anchor_review_token,
    anchor.id AS anchor_id,
    anchor.anchor_review_token,
    anchor.initial_measurement_basis,
    anchor.initial_measurement_assessment,
    anchor.initial_measurement_evidence_reference,
    anchor.authoritative_daily_eir,
    anchor.authoritative_daily_eir_percent,
    anchor.authoritative_initial_gross_carrying_amount,
    anchor.eir_difference_from_principal_base_preview,
    anchor.review_rationale,
    anchor.reviewed_by_user_id,
    anchor.reviewed_at,
    anchor.recomputed_daily_eir,
    (anchor.id IS NOT NULL) AS active_anchor_exists,
    (
        anchor.id IS NOT NULL
        AND anchor.anchor_review_token = accounting.seven_by_seven_eir_anchor_review_token(readiness.loan_id)
        AND anchor.policy_decision_id = readiness.decision_id
        AND anchor.schedule_id = readiness.schedule_id
        AND anchor.schedule_version = readiness.schedule_version
    ) AS active_anchor_is_current,
    (
        anchor.id IS NOT NULL
        AND anchor.recomputed_daily_eir IS NOT NULL
        AND anchor.authoritative_daily_eir = anchor.recomputed_daily_eir
    ) AS anchor_eir_reconciles,
    (
        anchor.id IS NOT NULL
        AND anchor.anchor_review_token = accounting.seven_by_seven_eir_anchor_review_token(readiness.loan_id)
        AND anchor.policy_decision_id = readiness.decision_id
        AND anchor.schedule_id = readiness.schedule_id
        AND anchor.schedule_version = readiness.schedule_version
        AND anchor.recomputed_daily_eir IS NOT NULL
        AND anchor.authoritative_daily_eir = anchor.recomputed_daily_eir
    ) AS eir_policy_ready,
    (
        anchor.id IS NOT NULL
        AND anchor.anchor_review_token = accounting.seven_by_seven_eir_anchor_review_token(readiness.loan_id)
        AND anchor.recomputed_daily_eir IS NOT NULL
        AND anchor.authoritative_daily_eir = anchor.recomputed_daily_eir
    ) AS initial_carrying_amount_ready,
    NULL::numeric(18,2) AS authoritative_current_gross_carrying_amount,
    false AS current_carrying_amount_ready,
    false AS carrying_amount_ready,
    (
        anchor.id IS NOT NULL
        AND anchor.anchor_review_token = accounting.seven_by_seven_eir_anchor_review_token(readiness.loan_id)
        AND anchor.recomputed_daily_eir IS NOT NULL
        AND anchor.authoritative_daily_eir = anchor.recomputed_daily_eir
    ) AS carrying_policy_ready,
    false AS journal_lines_enabled,
    false AS automatic_source_posting,
    CASE
        WHEN NOT readiness.classification_policy_evidence_ready_for_eir_promotion
            THEN readiness.classification_policy_readiness_status
        WHEN accounting.seven_by_seven_eir_anchor_review_token(readiness.loan_id) IS NULL
            THEN 'eir_anchor_review_token_unavailable'
        WHEN anchor.id IS NULL
            THEN 'management_initial_measurement_and_eir_anchor_required'
        WHEN anchor.anchor_review_token IS DISTINCT FROM accounting.seven_by_seven_eir_anchor_review_token(readiness.loan_id)
            THEN 'stale_eir_initial_carrying_anchor_requires_new_review'
        WHEN anchor.policy_decision_id IS DISTINCT FROM readiness.decision_id
          OR anchor.schedule_id IS DISTINCT FROM readiness.schedule_id
          OR anchor.schedule_version IS DISTINCT FROM readiness.schedule_version
            THEN 'eir_initial_carrying_anchor_source_identity_mismatch'
        WHEN anchor.recomputed_daily_eir IS NULL
          OR anchor.authoritative_daily_eir IS DISTINCT FROM anchor.recomputed_daily_eir
            THEN 'eir_initial_carrying_anchor_reconciliation_failed'
        ELSE 'eir_initial_carrying_anchor_ready_for_7x7_accounting_lifecycle'
    END AS eir_initial_carrying_readiness_status
FROM accounting.seven_by_seven_classification_policy_readiness readiness
LEFT JOIN LATERAL (
    SELECT status.*
    FROM accounting.seven_by_seven_eir_initial_carrying_anchor_status status
    WHERE status.loan_id = readiness.loan_id AND status.is_active
    ORDER BY status.reviewed_at DESC
    LIMIT 1
) anchor ON true;

CREATE OR REPLACE VIEW accounting.seven_by_seven_eir_initial_carrying_summary AS
SELECT
    count(*)::bigint AS seven_by_seven_loan_count,
    count(*) FILTER (WHERE classification_policy_evidence_ready_for_eir_promotion)::bigint
        AS classification_policy_ready_count,
    count(*) FILTER (WHERE active_anchor_exists)::bigint AS active_anchor_count,
    count(*) FILTER (WHERE active_anchor_is_current)::bigint AS current_anchor_count,
    count(*) FILTER (WHERE anchor_eir_reconciles)::bigint AS eir_reconciled_count,
    count(*) FILTER (WHERE eir_policy_ready)::bigint AS eir_policy_ready_count,
    count(*) FILTER (WHERE initial_carrying_amount_ready)::bigint AS initial_carrying_ready_count,
    count(*) FILTER (
        WHERE eir_initial_carrying_readiness_status = 'eir_initial_carrying_anchor_ready_for_7x7_accounting_lifecycle'
    )::bigint AS accounting_lifecycle_ready_count,
    false AS current_carrying_amount_ready,
    false AS journal_lines_enabled,
    false AS automatic_source_posting
FROM accounting.seven_by_seven_eir_initial_carrying_readiness;

COMMENT ON VIEW accounting.seven_by_seven_eir_initial_carrying_readiness IS
    'Protected 7x7 original-EIR and initial-gross-carrying promotion/reconciliation boundary. It binds current immutable Management policy evidence to an evidence-backed initial carrying amount and recomputes original EIR from the exact verified schedule. Current carrying, journals and automatic posting remain disabled pending the separate 7x7 accounting lifecycle.';

COMMIT;