BEGIN;

-- Master Issue #296: continue the 7x7 / EMER EIR/carrying-policy proof
-- without promoting the operational PHP 7-per-PHP 1,000 rule into accounting.
-- This slice records explicit evidence-backed Management conclusions for the
-- IFRS 9 business-model / SPPI classification gate and expected-life /
-- prepayment cash-flow policy. It creates no authoritative EIR, carrying
-- amount, journal line, or automatic posting.

INSERT INTO core.permissions (code, description)
VALUES (
    'accounting.7x7_classification_policy.manage',
    'Record or explicitly void immutable Management-reviewed 7x7 business-model, SPPI, measurement-category, expected-life and prepayment/EIR policy evidence without enabling accounting posting'
)
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code = 'accounting.7x7_classification_policy.manage'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE OR REPLACE FUNCTION accounting.seven_by_seven_policy_review_token(p_loan_id UUID)
RETURNS TEXT
LANGUAGE sql
STABLE
AS $$
    SELECT CASE
        WHEN readiness.base_no_prepayment_daily_eir_preview IS NOT NULL
         AND readiness.schedule_id IS NOT NULL
         AND readiness.policy_readiness_status <> 'contractual_cash_flow_readiness_required' THEN
            encode(
                sha256(
                    convert_to(
                        concat_ws(
                            '|',
                            'seven_by_seven_classification_policy_readiness_v1',
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
                            readiness.operational_daily_contractual_interest::text,
                            readiness.operational_daily_rate_on_original_principal::text,
                            readiness.base_no_prepayment_daily_eir_preview::text,
                            readiness.principal_prepayment_allowed::text,
                            readiness.principal_prepayment_changes_daily_interest::text,
                            readiness.validated_base_schedule_basis
                        ),
                        'UTF8'
                    )
                ),
                'hex'
            )
        ELSE NULL
    END
    FROM accounting.seven_by_seven_eir_carrying_policy_readiness readiness
    WHERE readiness.loan_id = p_loan_id;
$$;

CREATE TABLE IF NOT EXISTS accounting.seven_by_seven_policy_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    schedule_id UUID NOT NULL REFERENCES lending.loan_contract_schedules(id) ON DELETE RESTRICT,
    schedule_version INTEGER NOT NULL CHECK (schedule_version > 0),
    review_token TEXT NOT NULL CHECK (review_token ~ '^[0-9a-f]{64}$'),
    readiness_policy_version TEXT NOT NULL CHECK (
        readiness_policy_version = 'seven_by_seven_classification_policy_readiness_v1'
    ),
    decision_policy_version TEXT NOT NULL CHECK (
        decision_policy_version = 'seven_by_seven_classification_policy_decision_v1'
    ),
    loan_number TEXT NOT NULL CHECK (btrim(loan_number) <> ''),
    principal NUMERIC(18,2) NOT NULL CHECK (principal > 0),
    date_released DATE NOT NULL,
    due_date DATE NOT NULL,
    term_days INTEGER NOT NULL CHECK (term_days > 0),
    contract_reference TEXT NOT NULL CHECK (btrim(contract_reference) <> ''),
    contract_evidence_reference TEXT NOT NULL CHECK (btrim(contract_evidence_reference) <> ''),
    operational_daily_contractual_interest NUMERIC(18,2) NOT NULL CHECK (
        operational_daily_contractual_interest >= 0
    ),
    operational_daily_rate_on_original_principal NUMERIC(24,12) NOT NULL CHECK (
        operational_daily_rate_on_original_principal >= 0
    ),
    base_no_prepayment_daily_eir_preview NUMERIC(24,12) NOT NULL CHECK (
        base_no_prepayment_daily_eir_preview > 0
    ),
    principal_prepayment_allowed BOOLEAN NOT NULL,
    principal_prepayment_changes_daily_interest BOOLEAN NOT NULL,
    validated_base_schedule_basis TEXT NOT NULL CHECK (btrim(validated_base_schedule_basis) <> ''),
    business_model_conclusion TEXT NOT NULL CHECK (
        business_model_conclusion IN ('held_to_collect', 'held_to_collect_and_sell', 'other')
    ),
    sppi_conclusion TEXT NOT NULL CHECK (sppi_conclusion IN ('passes', 'fails')),
    measurement_category TEXT NOT NULL CHECK (
        measurement_category IN ('amortised_cost', 'fvoci', 'fvpl')
    ),
    expected_cash_flow_policy TEXT NOT NULL CHECK (
        expected_cash_flow_policy IN (
            'verified_no_prepayment_schedule_is_expected_cash_flow_estimate',
            'separate_expected_prepayment_cash_flow_evidence_required'
        )
    ),
    expected_life_policy TEXT NOT NULL CHECK (
        expected_life_policy IN ('contractual_term', 'supported_shorter_expected_life')
    ),
    expected_life_days INTEGER NOT NULL CHECK (expected_life_days > 0),
    accounting_policy_reference TEXT NOT NULL CHECK (btrim(accounting_policy_reference) <> ''),
    classification_assessment JSONB NOT NULL CHECK (
        jsonb_typeof(classification_assessment) = 'object'
        AND classification_assessment <> '{}'::jsonb
    ),
    prepayment_expected_cash_flow_assessment JSONB NOT NULL CHECK (
        jsonb_typeof(prepayment_expected_cash_flow_assessment) = 'object'
        AND prepayment_expected_cash_flow_assessment <> '{}'::jsonb
    ),
    decision_rationale TEXT NOT NULL CHECK (length(btrim(decision_rationale)) >= 20),
    supporting_evidence_reference TEXT NOT NULL CHECK (btrim(supporting_evidence_reference) <> ''),
    reviewed_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (due_date > date_released),
    CHECK (
        (expected_life_policy = 'contractual_term' AND expected_life_days = term_days)
        OR
        (expected_life_policy = 'supported_shorter_expected_life' AND expected_life_days < term_days)
    ),
    CHECK (
        (sppi_conclusion = 'passes' AND business_model_conclusion = 'held_to_collect'
            AND measurement_category = 'amortised_cost')
        OR
        (sppi_conclusion = 'passes' AND business_model_conclusion = 'held_to_collect_and_sell'
            AND measurement_category = 'fvoci')
        OR
        (business_model_conclusion = 'other' AND measurement_category = 'fvpl')
        OR
        (sppi_conclusion = 'fails' AND measurement_category = 'fvpl')
    )
);

CREATE INDEX IF NOT EXISTS seven_by_seven_policy_decisions_loan_idx
    ON accounting.seven_by_seven_policy_decisions (loan_id, reviewed_at DESC);

CREATE TABLE IF NOT EXISTS accounting.seven_by_seven_policy_decision_voids (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID NOT NULL UNIQUE
        REFERENCES accounting.seven_by_seven_policy_decisions(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    void_reason TEXT NOT NULL CHECK (length(btrim(void_reason)) >= 3),
    voided_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    voided_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION accounting.guard_seven_by_seven_policy_decision_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(
            current_setting('accounting.seven_by_seven_policy_decision_insert_allowed', true),
            ''
       ) = 'on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION '7x7 classification/EIR policy decision evidence is immutable and must use the protected Management-reviewed decision function.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_seven_by_seven_policy_decision_guard
    ON accounting.seven_by_seven_policy_decisions;
CREATE TRIGGER accounting_seven_by_seven_policy_decision_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.seven_by_seven_policy_decisions
FOR EACH ROW EXECUTE FUNCTION accounting.guard_seven_by_seven_policy_decision_write();

CREATE OR REPLACE FUNCTION accounting.guard_seven_by_seven_policy_decision_void_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(
            current_setting('accounting.seven_by_seven_policy_decision_void_insert_allowed', true),
            ''
       ) = 'on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION '7x7 classification/EIR policy void evidence is immutable and must use the protected void function.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_seven_by_seven_policy_decision_void_guard
    ON accounting.seven_by_seven_policy_decision_voids;
CREATE TRIGGER accounting_seven_by_seven_policy_decision_void_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.seven_by_seven_policy_decision_voids
FOR EACH ROW EXECUTE FUNCTION accounting.guard_seven_by_seven_policy_decision_void_write();

CREATE OR REPLACE FUNCTION accounting.require_7x7_policy_management_actor(p_actor_user_id UUID)
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
          AND role_permission.permission_code = 'accounting.7x7_classification_policy.manage'
    ) THEN
        RAISE EXCEPTION 'An active Management actor with accounting.7x7_classification_policy.manage permission is required.';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.record_seven_by_seven_policy_decision(
    p_loan_id UUID,
    p_review_token TEXT,
    p_business_model_conclusion TEXT,
    p_sppi_conclusion TEXT,
    p_measurement_category TEXT,
    p_expected_cash_flow_policy TEXT,
    p_expected_life_policy TEXT,
    p_expected_life_days INTEGER,
    p_accounting_policy_reference TEXT,
    p_classification_assessment JSONB,
    p_prepayment_expected_cash_flow_assessment JSONB,
    p_decision_rationale TEXT,
    p_supporting_evidence_reference TEXT,
    p_actor_user_id UUID
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    source_row RECORD;
    existing_row accounting.seven_by_seven_policy_decisions%ROWTYPE;
    created_id UUID;
    current_token TEXT;
    expected_measurement_category TEXT;
    normalized_policy_reference TEXT := btrim(coalesce(p_accounting_policy_reference, ''));
    normalized_rationale TEXT := btrim(coalesce(p_decision_rationale, ''));
    normalized_support_reference TEXT := btrim(coalesce(p_supporting_evidence_reference, ''));
BEGIN
    PERFORM accounting.require_7x7_policy_management_actor(p_actor_user_id);

    IF p_loan_id IS NULL THEN
        RAISE EXCEPTION '7x7 classification/EIR policy decision requires an exact loan identifier.';
    END IF;
    IF coalesce(p_review_token, '') !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION '7x7 classification/EIR policy decision requires the exact current 64-character review token.';
    END IF;
    IF p_business_model_conclusion NOT IN ('held_to_collect', 'held_to_collect_and_sell', 'other') THEN
        RAISE EXCEPTION 'Unsupported 7x7 business-model conclusion.';
    END IF;
    IF p_sppi_conclusion NOT IN ('passes', 'fails') THEN
        RAISE EXCEPTION '7x7 SPPI conclusion must be an explicit passes or fails decision.';
    END IF;
    IF p_expected_cash_flow_policy NOT IN (
        'verified_no_prepayment_schedule_is_expected_cash_flow_estimate',
        'separate_expected_prepayment_cash_flow_evidence_required'
    ) THEN
        RAISE EXCEPTION 'Unsupported 7x7 expected-cash-flow/prepayment policy.';
    END IF;
    IF p_expected_life_policy NOT IN ('contractual_term', 'supported_shorter_expected_life') THEN
        RAISE EXCEPTION 'Unsupported 7x7 expected-life policy.';
    END IF;
    IF normalized_policy_reference = ''
       OR length(normalized_rationale) < 20
       OR normalized_support_reference = '' THEN
        RAISE EXCEPTION 'Substantive accounting policy reference, rationale and supporting evidence are required.';
    END IF;
    IF p_classification_assessment IS NULL
       OR jsonb_typeof(p_classification_assessment) <> 'object'
       OR p_classification_assessment = '{}'::jsonb THEN
        RAISE EXCEPTION 'A non-empty business-model/SPPI classification assessment object is required.';
    END IF;
    IF p_prepayment_expected_cash_flow_assessment IS NULL
       OR jsonb_typeof(p_prepayment_expected_cash_flow_assessment) <> 'object'
       OR p_prepayment_expected_cash_flow_assessment = '{}'::jsonb THEN
        RAISE EXCEPTION 'A non-empty expected-life/prepayment cash-flow assessment object is required.';
    END IF;

    IF p_business_model_conclusion = 'other' OR p_sppi_conclusion = 'fails' THEN
        expected_measurement_category := 'fvpl';
    ELSIF p_business_model_conclusion = 'held_to_collect' THEN
        expected_measurement_category := 'amortised_cost';
    ELSE
        expected_measurement_category := 'fvoci';
    END IF;
    IF p_measurement_category IS DISTINCT FROM expected_measurement_category THEN
        RAISE EXCEPTION 'Measurement category is inconsistent with the explicit business-model and SPPI conclusions.';
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended('seven-by-seven-policy:' || p_loan_id::text, 0));

    SELECT readiness.*,
           accounting.seven_by_seven_policy_review_token(readiness.loan_id) AS current_review_token
    INTO source_row
    FROM accounting.seven_by_seven_eir_carrying_policy_readiness readiness
    WHERE readiness.loan_id = p_loan_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION '7x7 EIR/carrying policy readiness row was not found.';
    END IF;
    IF source_row.policy_readiness_status = 'contractual_cash_flow_readiness_required'
       OR source_row.base_no_prepayment_daily_eir_preview IS NULL
       OR source_row.schedule_id IS NULL THEN
        RAISE EXCEPTION 'Verified 7x7 signed-contract cash-flow readiness and a solved mathematical base EIR preview are required before policy review.';
    END IF;

    current_token := source_row.current_review_token;
    IF current_token IS NULL OR current_token IS DISTINCT FROM p_review_token THEN
        RAISE EXCEPTION '7x7 classification/EIR policy review token is stale or does not match current authoritative contract readiness.';
    END IF;

    IF coalesce(p_expected_life_days, 0) <= 0 THEN
        RAISE EXCEPTION 'A positive evidence-backed expected life in days is required.';
    END IF;
    IF p_expected_life_policy = 'contractual_term'
       AND p_expected_life_days IS DISTINCT FROM source_row.term_days THEN
        RAISE EXCEPTION 'Contractual-term expected-life policy must use the exact contractual term days.';
    END IF;
    IF p_expected_life_policy = 'supported_shorter_expected_life'
       AND p_expected_life_days >= source_row.term_days THEN
        RAISE EXCEPTION 'Supported-shorter expected life must be shorter than the contractual term.';
    END IF;

    SELECT decision.*
    INTO existing_row
    FROM accounting.seven_by_seven_policy_decisions decision
    LEFT JOIN accounting.seven_by_seven_policy_decision_voids voided ON voided.decision_id = decision.id
    WHERE decision.loan_id = p_loan_id AND voided.id IS NULL
    ORDER BY decision.reviewed_at DESC
    LIMIT 1
    FOR UPDATE OF decision;

    IF FOUND THEN
        IF existing_row.schedule_id = source_row.schedule_id
           AND existing_row.schedule_version = source_row.schedule_version
           AND existing_row.review_token = p_review_token
           AND existing_row.business_model_conclusion = p_business_model_conclusion
           AND existing_row.sppi_conclusion = p_sppi_conclusion
           AND existing_row.measurement_category = p_measurement_category
           AND existing_row.expected_cash_flow_policy = p_expected_cash_flow_policy
           AND existing_row.expected_life_policy = p_expected_life_policy
           AND existing_row.expected_life_days = p_expected_life_days
           AND existing_row.accounting_policy_reference = normalized_policy_reference
           AND existing_row.classification_assessment = p_classification_assessment
           AND existing_row.prepayment_expected_cash_flow_assessment = p_prepayment_expected_cash_flow_assessment
           AND existing_row.decision_rationale = normalized_rationale
           AND existing_row.supporting_evidence_reference = normalized_support_reference
           AND existing_row.reviewed_by_user_id = p_actor_user_id THEN
            RETURN existing_row.id;
        END IF;
        RAISE EXCEPTION 'Different active 7x7 classification/EIR policy evidence already exists; void it explicitly before recording a correction.';
    END IF;

    PERFORM set_config('accounting.seven_by_seven_policy_decision_insert_allowed', 'on', true);
    INSERT INTO accounting.seven_by_seven_policy_decisions (
        loan_id, schedule_id, schedule_version, review_token,
        readiness_policy_version, decision_policy_version,
        loan_number, principal, date_released, due_date, term_days,
        contract_reference, contract_evidence_reference,
        operational_daily_contractual_interest,
        operational_daily_rate_on_original_principal,
        base_no_prepayment_daily_eir_preview,
        principal_prepayment_allowed, principal_prepayment_changes_daily_interest,
        validated_base_schedule_basis,
        business_model_conclusion, sppi_conclusion, measurement_category,
        expected_cash_flow_policy, expected_life_policy, expected_life_days,
        accounting_policy_reference, classification_assessment,
        prepayment_expected_cash_flow_assessment, decision_rationale,
        supporting_evidence_reference, reviewed_by_user_id
    ) VALUES (
        source_row.loan_id, source_row.schedule_id, source_row.schedule_version, p_review_token,
        'seven_by_seven_classification_policy_readiness_v1',
        'seven_by_seven_classification_policy_decision_v1',
        source_row.loan_number, source_row.principal, source_row.date_released,
        source_row.due_date, source_row.term_days, source_row.contract_reference,
        source_row.evidence_reference, source_row.operational_daily_contractual_interest,
        source_row.operational_daily_rate_on_original_principal,
        source_row.base_no_prepayment_daily_eir_preview,
        source_row.principal_prepayment_allowed,
        source_row.principal_prepayment_changes_daily_interest,
        source_row.validated_base_schedule_basis,
        p_business_model_conclusion, p_sppi_conclusion, p_measurement_category,
        p_expected_cash_flow_policy, p_expected_life_policy, p_expected_life_days,
        normalized_policy_reference, p_classification_assessment,
        p_prepayment_expected_cash_flow_assessment, normalized_rationale,
        normalized_support_reference, p_actor_user_id
    ) RETURNING id INTO created_id;
    PERFORM set_config('accounting.seven_by_seven_policy_decision_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs (actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.7x7_classification_policy.recorded',
        'seven_by_seven_policy_decision',
        created_id,
        jsonb_build_object(
            'loan_id', p_loan_id::text,
            'business_model_conclusion', p_business_model_conclusion,
            'sppi_conclusion', p_sppi_conclusion,
            'measurement_category', p_measurement_category,
            'expected_cash_flow_policy', p_expected_cash_flow_policy,
            'authoritative_eir_enabled', false,
            'journal_lines_enabled', false,
            'automatic_source_posting', false
        )
    );

    RETURN created_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.void_seven_by_seven_policy_decision(
    p_decision_id UUID,
    p_actor_user_id UUID,
    p_reason TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    decision_row accounting.seven_by_seven_policy_decisions%ROWTYPE;
    existing_void accounting.seven_by_seven_policy_decision_voids%ROWTYPE;
    normalized_reason TEXT := btrim(coalesce(p_reason, ''));
    created_id UUID;
BEGIN
    PERFORM accounting.require_7x7_policy_management_actor(p_actor_user_id);
    IF length(normalized_reason) < 3 THEN
        RAISE EXCEPTION 'Enter a clear reason for voiding 7x7 classification/EIR policy evidence.';
    END IF;

    SELECT * INTO decision_row
    FROM accounting.seven_by_seven_policy_decisions
    WHERE id = p_decision_id
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION '7x7 classification/EIR policy evidence was not found.';
    END IF;

    SELECT * INTO existing_void
    FROM accounting.seven_by_seven_policy_decision_voids
    WHERE decision_id = p_decision_id
    FOR UPDATE;
    IF FOUND THEN
        IF existing_void.voided_by_user_id = p_actor_user_id
           AND existing_void.void_reason = normalized_reason THEN
            RETURN existing_void.id;
        END IF;
        RAISE EXCEPTION '7x7 classification/EIR policy evidence was already voided with different evidence.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM accounting.journal_entries journal
        WHERE journal.source_reference = p_decision_id::text
    ) THEN
        RAISE EXCEPTION '7x7 policy evidence already has protected accounting journal history; use the future controlled accounting correction/reversal path.';
    END IF;

    PERFORM set_config('accounting.seven_by_seven_policy_decision_void_insert_allowed', 'on', true);
    INSERT INTO accounting.seven_by_seven_policy_decision_voids (
        decision_id, loan_id, void_reason, voided_by_user_id
    ) VALUES (
        p_decision_id, decision_row.loan_id, normalized_reason, p_actor_user_id
    ) RETURNING id INTO created_id;
    PERFORM set_config('accounting.seven_by_seven_policy_decision_void_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs (actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.7x7_classification_policy.voided',
        'seven_by_seven_policy_decision',
        p_decision_id,
        jsonb_build_object(
            'loan_id', decision_row.loan_id::text,
            'reason', normalized_reason,
            'journal_lines_enabled', false,
            'automatic_source_posting', false
        )
    );
    RETURN created_id;
END;
$$;

CREATE OR REPLACE VIEW accounting.seven_by_seven_policy_decision_status AS
SELECT
    decision.*,
    voided.id AS void_id,
    voided.void_reason,
    voided.voided_by_user_id,
    voided.voided_at,
    (voided.id IS NULL) AS is_active,
    false AS authoritative_eir_enabled,
    false AS authoritative_carrying_amount_enabled,
    false AS journal_lines_enabled,
    false AS automatic_source_posting
FROM accounting.seven_by_seven_policy_decisions decision
LEFT JOIN accounting.seven_by_seven_policy_decision_voids voided
  ON voided.decision_id = decision.id;

CREATE OR REPLACE VIEW accounting.seven_by_seven_classification_policy_readiness AS
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
    readiness.operational_daily_contractual_interest,
    readiness.operational_daily_rate_on_original_principal,
    readiness.base_no_prepayment_daily_eir_preview,
    readiness.base_no_prepayment_daily_eir_percent,
    readiness.operational_rate_matches_base_math_preview,
    readiness.principal_prepayment_allowed,
    readiness.principal_prepayment_changes_daily_interest,
    readiness.validated_base_schedule_basis,
    readiness.policy_readiness_status AS prior_policy_readiness_status,
    readiness.policy_note AS prior_policy_note,
    accounting.seven_by_seven_policy_review_token(readiness.loan_id) AS current_policy_review_token,
    decision.id AS decision_id,
    decision.review_token AS decision_review_token,
    decision.business_model_conclusion,
    decision.sppi_conclusion,
    decision.measurement_category,
    decision.expected_cash_flow_policy,
    decision.expected_life_policy,
    decision.expected_life_days,
    decision.accounting_policy_reference,
    decision.classification_assessment,
    decision.prepayment_expected_cash_flow_assessment,
    decision.decision_rationale,
    decision.supporting_evidence_reference,
    decision.reviewed_by_user_id,
    decision.reviewed_at,
    (decision.id IS NOT NULL) AS active_policy_decision_exists,
    (
        decision.id IS NOT NULL
        AND decision.review_token = accounting.seven_by_seven_policy_review_token(readiness.loan_id)
    ) AS active_policy_decision_is_current,
    (
        decision.id IS NOT NULL
        AND decision.review_token = accounting.seven_by_seven_policy_review_token(readiness.loan_id)
    ) AS business_model_classification_concluded,
    (
        decision.id IS NOT NULL
        AND decision.review_token = accounting.seven_by_seven_policy_review_token(readiness.loan_id)
    ) AS sppi_classification_concluded,
    (
        decision.id IS NOT NULL
        AND decision.review_token = accounting.seven_by_seven_policy_review_token(readiness.loan_id)
    ) AS expected_cash_flow_policy_approved,
    (
        decision.id IS NOT NULL
        AND decision.review_token = accounting.seven_by_seven_policy_review_token(readiness.loan_id)
        AND decision.measurement_category = 'amortised_cost'
    ) AS amortised_cost_path_supported,
    (
        decision.id IS NOT NULL
        AND decision.review_token = accounting.seven_by_seven_policy_review_token(readiness.loan_id)
        AND decision.measurement_category = 'amortised_cost'
        AND decision.expected_cash_flow_policy = 'verified_no_prepayment_schedule_is_expected_cash_flow_estimate'
        AND decision.expected_life_policy = 'contractual_term'
        AND decision.expected_life_days = readiness.term_days
    ) AS classification_policy_evidence_ready_for_eir_promotion,
    NULL::numeric(24,12) AS authoritative_daily_eir,
    NULL::numeric(18,2) AS authoritative_initial_gross_carrying_amount,
    NULL::numeric(18,2) AS authoritative_current_gross_carrying_amount,
    false AS eir_policy_ready,
    false AS carrying_amount_ready,
    false AS journal_lines_enabled,
    false AS automatic_source_posting,
    CASE
        WHEN readiness.policy_readiness_status = 'contractual_cash_flow_readiness_required'
            THEN 'contractual_cash_flow_readiness_required'
        WHEN readiness.base_no_prepayment_daily_eir_preview IS NULL
            THEN 'base_eir_preview_not_solved'
        WHEN decision.id IS NULL
            THEN 'management_classification_policy_evidence_required'
        WHEN decision.review_token IS DISTINCT FROM accounting.seven_by_seven_policy_review_token(readiness.loan_id)
            THEN 'stale_management_policy_evidence_requires_new_review'
        WHEN decision.measurement_category = 'fvpl'
            THEN 'fvpl_measurement_path_requires_separate_accounting_design'
        WHEN decision.measurement_category = 'fvoci'
            THEN 'fvoci_measurement_path_requires_separate_accounting_design'
        WHEN decision.expected_cash_flow_policy = 'separate_expected_prepayment_cash_flow_evidence_required'
            THEN 'expected_prepayment_cash_flow_evidence_required'
        WHEN decision.expected_life_policy = 'supported_shorter_expected_life'
            THEN 'shorter_expected_life_cash_flow_evidence_required'
        ELSE 'classification_policy_evidence_ready_for_eir_promotion_review'
    END AS classification_policy_readiness_status
FROM accounting.seven_by_seven_eir_carrying_policy_readiness readiness
LEFT JOIN LATERAL (
    SELECT status.*
    FROM accounting.seven_by_seven_policy_decision_status status
    WHERE status.loan_id = readiness.loan_id AND status.is_active
    ORDER BY status.reviewed_at DESC
    LIMIT 1
) decision ON true;

CREATE OR REPLACE VIEW accounting.seven_by_seven_classification_policy_summary AS
SELECT
    count(*)::bigint AS seven_by_seven_loan_count,
    count(*) FILTER (WHERE active_policy_decision_exists)::bigint AS active_policy_decision_count,
    count(*) FILTER (WHERE active_policy_decision_is_current)::bigint AS current_policy_decision_count,
    count(*) FILTER (WHERE business_model_classification_concluded)::bigint AS business_model_concluded_count,
    count(*) FILTER (WHERE sppi_classification_concluded)::bigint AS sppi_concluded_count,
    count(*) FILTER (WHERE expected_cash_flow_policy_approved)::bigint AS expected_cash_flow_policy_approved_count,
    count(*) FILTER (WHERE amortised_cost_path_supported)::bigint AS amortised_cost_path_supported_count,
    count(*) FILTER (WHERE classification_policy_evidence_ready_for_eir_promotion)::bigint AS eir_promotion_review_ready_count,
    count(*) FILTER (
        WHERE classification_policy_readiness_status = 'expected_prepayment_cash_flow_evidence_required'
    )::bigint AS expected_prepayment_cash_flow_evidence_required_count,
    false AS authoritative_eir_enabled,
    false AS authoritative_carrying_amount_enabled,
    false AS eir_policy_ready,
    false AS carrying_amount_ready,
    false AS journal_lines_enabled,
    false AS automatic_source_posting
FROM accounting.seven_by_seven_classification_policy_readiness;

COMMIT;