BEGIN;

-- Master #296 A3: protected read-only quantitative ECL measurement.
--
-- This stage may persist an immutable calculation/audit snapshot, but it does
-- not create a journal, does not post account 1190, does not execute write-off
-- accounting, and does not enable automatic source posting.
--
-- Stage 1 uses a 12-month *credit-loss event horizon*. Expected cash receipts
-- are still evaluated over the relevant contractual life; cash flows are not
-- mechanically truncated at 12 months. Stage 2 and Stage 3 use lifetime ECL.
-- No PD x LGD shortcut, scenario probability, overlay, multiplier, cure rate or
-- recovery rate is invented by SPINA.

INSERT INTO core.permissions (code, description)
VALUES (
    'accounting.ecl.measurement.review',
    'Record immutable evidence-supported read-only quantitative ECL measurements without posting account 1190 or enabling automatic source posting'
)
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code = 'accounting.ecl.measurement.review'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

-- A forward-looking source is not current before its stated forecast period.
-- PR #345 already stored forecast_period_start; A3 makes the readiness boundary
-- use it explicitly before quantitative values can be consumed.
CREATE OR REPLACE VIEW accounting.ecl_forward_looking_evidence_status AS
SELECT
    evidence.*,
    revocation.id AS revocation_id,
    revocation.reason AS revocation_reason,
    revocation.revoked_by_user_id,
    revocation.revoked_at,
    EXISTS (
        SELECT 1
        FROM accounting.ecl_forward_looking_evidence later
        WHERE later.supersedes_evidence_id = evidence.id
    ) AS is_superseded,
    CASE
        WHEN revocation.id IS NOT NULL THEN 'revoked'
        WHEN EXISTS (
            SELECT 1
            FROM accounting.ecl_forward_looking_evidence later
            WHERE later.supersedes_evidence_id = evidence.id
        ) THEN 'superseded'
        WHEN current_date < evidence.effective_date
          OR current_date < evidence.forecast_period_start
            THEN 'not_yet_effective'
        WHEN current_date > evidence.forecast_period_end THEN 'stale'
        ELSE 'current'
    END AS evidence_status,
    (
        revocation.id IS NULL
        AND NOT EXISTS (
            SELECT 1
            FROM accounting.ecl_forward_looking_evidence later
            WHERE later.supersedes_evidence_id = evidence.id
        )
        AND current_date >= evidence.effective_date
        AND current_date >= evidence.forecast_period_start
        AND current_date <= evidence.forecast_period_end
    ) AS ready_for_new_measurement,
    false AS scenario_probability_defaulted,
    false AS multiplier_defaulted,
    false AS management_overlay_defaulted,
    false AS ecl_calculation_enabled,
    false AS account_1190_posting_enabled,
    false AS automatic_source_posting
FROM accounting.ecl_forward_looking_evidence evidence
LEFT JOIN accounting.ecl_forward_looking_evidence_revocations revocation
  ON revocation.evidence_id = evidence.id;

CREATE TABLE IF NOT EXISTS accounting.ecl_quantitative_measurements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    measurement_version INTEGER NOT NULL CHECK (measurement_version > 0),
    measurement_date DATE NOT NULL,
    stage_label TEXT NOT NULL CHECK (
        stage_label IN (
            'stage_1_12_month',
            'stage_2_lifetime',
            'stage_3_credit_impaired'
        )
    ),
    loss_horizon TEXT NOT NULL CHECK (loss_horizon IN ('12_month', 'lifetime')),
    schedule_id UUID NOT NULL
        REFERENCES lending.loan_contract_schedules(id) ON DELETE RESTRICT,
    schedule_version INTEGER NOT NULL CHECK (schedule_version > 0),
    contract_reference TEXT NOT NULL CHECK (btrim(contract_reference) <> ''),
    label_review_id BIGINT NOT NULL
        REFERENCES accounting.ecl_credit_risk_label_reviews(id) ON DELETE RESTRICT,
    label_review_version INTEGER NOT NULL CHECK (label_review_version > 0),
    original_eir_source_key TEXT NOT NULL CHECK (btrim(original_eir_source_key) <> ''),
    original_eir_policy_version TEXT NOT NULL CHECK (btrim(original_eir_policy_version) <> ''),
    original_daily_eir NUMERIC(24,12) NOT NULL CHECK (original_daily_eir > 0),
    original_initial_gross_carrying_amount NUMERIC(18,2) NOT NULL
        CHECK (original_initial_gross_carrying_amount > 0),
    forward_evidence_ids UUID[] NOT NULL CHECK (cardinality(forward_evidence_ids) > 0),
    input_snapshot JSONB NOT NULL CHECK (
        jsonb_typeof(input_snapshot) = 'object' AND input_snapshot <> '{}'::jsonb
    ),
    contractual_cash_flow_snapshot JSONB NOT NULL CHECK (
        jsonb_typeof(contractual_cash_flow_snapshot) = 'array'
    ),
    scenario_snapshot JSONB NOT NULL CHECK (
        jsonb_typeof(scenario_snapshot) = 'array'
        AND jsonb_array_length(scenario_snapshot) >= 2
    ),
    scenario_count INTEGER NOT NULL CHECK (scenario_count >= 2 AND scenario_count <= 20),
    probability_total NUMERIC(18,12) NOT NULL CHECK (
        probability_total = 1.000000000000
    ),
    contractual_cash_flow_pv NUMERIC(28,12) NOT NULL CHECK (contractual_cash_flow_pv >= 0),
    weighted_expected_cash_shortfall NUMERIC(28,12) NOT NULL CHECK (
        weighted_expected_cash_shortfall >= 0
    ),
    ecl_amount NUMERIC(18,2) NOT NULL CHECK (ecl_amount >= 0),
    calculation_policy_version TEXT NOT NULL CHECK (
        calculation_policy_version = 'loan_level_probability_weighted_discounted_cash_shortfall_v1'
    ),
    discount_basis TEXT NOT NULL CHECK (
        discount_basis = 'original_daily_eir_calendar_days_to_measurement_date'
    ),
    rounding_policy TEXT NOT NULL CHECK (
        rounding_policy = 'numeric_high_precision_final_currency_cent'
    ),
    calculation_digest TEXT NOT NULL CHECK (calculation_digest ~ '^[0-9a-f]{64}$'),
    review_rationale TEXT NOT NULL CHECK (length(btrim(review_rationale)) >= 20),
    reviewed_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (loan_id, measurement_version),
    UNIQUE (loan_id, measurement_date, calculation_digest)
);

CREATE INDEX IF NOT EXISTS ecl_quantitative_measurements_loan_date_idx
    ON accounting.ecl_quantitative_measurements (
        loan_id, measurement_date DESC, measurement_version DESC
    );

CREATE OR REPLACE FUNCTION accounting.guard_ecl_quantitative_measurement_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(
            current_setting('accounting.ecl_quantitative_measurement_insert_allowed', true),
            ''
       ) = 'on' THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'Quantitative ECL measurements are immutable and must use the protected Management measurement function.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_ecl_quantitative_measurement_guard
    ON accounting.ecl_quantitative_measurements;
CREATE TRIGGER accounting_ecl_quantitative_measurement_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.ecl_quantitative_measurements
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_quantitative_measurement_write();

CREATE OR REPLACE FUNCTION accounting.require_ecl_measurement_management_actor(
    p_actor_user_id UUID
)
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
          AND role_permission.permission_code = 'accounting.ecl.measurement.review'
    ) THEN
        RAISE EXCEPTION 'An active Management actor with accounting.ecl.measurement.review permission is required.';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.record_read_only_quantitative_ecl_measurement(
    p_loan_id UUID,
    p_measurement_date DATE,
    p_scenarios JSONB,
    p_review_rationale TEXT,
    p_actor_user_id UUID
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    readiness RECORD;
    regular_anchor RECORD;
    seven_anchor RECORD;
    scenario JSONB;
    flow JSONB;
    evidence_json JSONB;
    scenario_key TEXT;
    support_reference TEXT;
    scenario_rationale TEXT;
    probability_raw NUMERIC;
    probability NUMERIC(18,12);
    expected_date DATE;
    expected_amount_raw NUMERIC;
    expected_amount NUMERIC(18,2);
    expected_pv NUMERIC := 0;
    contractual_pv NUMERIC := 0;
    scenario_shortfall NUMERIC := 0;
    weighted_shortfall NUMERIC := 0;
    probability_total_value NUMERIC := 0;
    normalized_expected JSONB;
    normalized_scenarios JSONB := '[]'::jsonb;
    contractual_snapshot JSONB := '[]'::jsonb;
    input_snapshot JSONB;
    seen_scenario_keys TEXT[] := ARRAY[]::text[];
    seen_expected_dates DATE[];
    all_forward_evidence_ids UUID[] := ARRAY[]::uuid[];
    evidence_id UUID;
    forward_evidence_count INTEGER;
    scenario_count_value INTEGER;
    original_eir_source_key TEXT;
    original_eir_policy_version TEXT;
    original_daily_eir NUMERIC(24,12);
    original_initial_carrying NUMERIC(18,2);
    loss_horizon_value TEXT;
    calculation_digest_value TEXT;
    ecl_amount_value NUMERIC(18,2);
    next_version INTEGER;
    existing_id UUID;
    created_id UUID;
BEGIN
    PERFORM accounting.require_ecl_measurement_management_actor(p_actor_user_id);

    IF p_loan_id IS NULL THEN
        RAISE EXCEPTION 'Loan id is required for quantitative ECL measurement.';
    END IF;
    IF p_measurement_date IS NULL THEN
        RAISE EXCEPTION 'Measurement date is required.';
    END IF;
    IF p_measurement_date IS DISTINCT FROM current_date THEN
        RAISE EXCEPTION 'SPINA V1 read-only ECL measurement must use the current authoritative date; backdated reconstruction is not enabled.';
    END IF;
    IF length(btrim(coalesce(p_review_rationale, ''))) < 20 THEN
        RAISE EXCEPTION 'A substantive Management measurement rationale is required.';
    END IF;
    IF p_scenarios IS NULL OR jsonb_typeof(p_scenarios) <> 'array' THEN
        RAISE EXCEPTION 'Evidence-supported probability-weighted ECL scenarios must be supplied as an array.';
    END IF;

    scenario_count_value := jsonb_array_length(p_scenarios);
    IF scenario_count_value < 2 OR scenario_count_value > 20 THEN
        RAISE EXCEPTION 'Probability-weighted ECL requires between 2 and 20 explicit evidence-supported scenarios.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended('ecl-read-only-measurement:' || p_loan_id::text, 0)
    );

    PERFORM 1 FROM lending.loans WHERE id = p_loan_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Loan was not found.';
    END IF;

    SELECT * INTO readiness
    FROM accounting.ecl_quantitative_input_readiness
    WHERE loan_id = p_loan_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Quantitative ECL input-readiness row was not found.';
    END IF;
    IF NOT coalesce(readiness.quantitative_input_ready, false) THEN
        RAISE EXCEPTION 'Quantitative ECL input gate is blocked: %',
            array_to_string(readiness.blocker_codes, ', ');
    END IF;
    IF readiness.schedule_id IS NULL
       OR readiness.schedule_version IS NULL
       OR readiness.review_id IS NULL
       OR readiness.review_version IS NULL
       OR readiness.stage_label IS NULL THEN
        RAISE EXCEPTION 'Current protected schedule and credit-risk label snapshot are required.';
    END IF;

    loss_horizon_value := CASE readiness.stage_label
        WHEN 'stage_1_12_month' THEN '12_month'
        WHEN 'stage_2_lifetime' THEN 'lifetime'
        WHEN 'stage_3_credit_impaired' THEN 'lifetime'
        ELSE NULL
    END;
    IF loss_horizon_value IS NULL THEN
        RAISE EXCEPTION 'Supported Stage 1, Stage 2 or Stage 3 evidence is required.';
    END IF;

    IF readiness.calculation_mode = 'fixed_daily' THEN
        SELECT * INTO regular_anchor
        FROM accounting.greenfield_regular_eir_anchor_readiness anchor
        WHERE anchor.loan_id = p_loan_id
          AND anchor.readiness_status = 'greenfield_regular_eir_anchor_ready';
        IF NOT FOUND OR regular_anchor.daily_eir IS NULL OR regular_anchor.daily_eir <= 0 THEN
            RAISE EXCEPTION 'Current protected Regular original-EIR anchor is required.';
        END IF;
        original_eir_source_key := regular_anchor.anchor_source_key;
        original_eir_policy_version := regular_anchor.anchor_policy_version;
        original_daily_eir := regular_anchor.daily_eir;
        original_initial_carrying := regular_anchor.initial_gross_carrying_amount;
    ELSIF readiness.calculation_mode = 'seven_by_seven' THEN
        SELECT * INTO seven_anchor
        FROM accounting.seven_by_seven_eir_initial_carrying_anchor_status anchor
        WHERE anchor.loan_id = p_loan_id
          AND anchor.is_active
          AND anchor.schedule_id = readiness.schedule_id
          AND anchor.schedule_version = readiness.schedule_version
        ORDER BY anchor.reviewed_at DESC
        LIMIT 1;
        IF NOT FOUND
           OR seven_anchor.authoritative_daily_eir IS NULL
           OR seven_anchor.authoritative_daily_eir <= 0
           OR seven_anchor.recomputed_daily_eir IS DISTINCT FROM seven_anchor.authoritative_daily_eir THEN
            RAISE EXCEPTION 'Current protected 7x7 original-EIR/initial-carrying anchor is required.';
        END IF;
        original_eir_source_key := 'seven_by_seven_eir_initial_carrying_anchor:' || seven_anchor.id::text;
        original_eir_policy_version := seven_anchor.anchor_policy_version;
        original_daily_eir := seven_anchor.authoritative_daily_eir;
        original_initial_carrying := seven_anchor.authoritative_initial_gross_carrying_amount;
    ELSE
        RAISE EXCEPTION 'Unsupported ECL calculation mode.';
    END IF;

    WITH allocation_rollup AS (
        SELECT
            installment.id AS installment_id,
            coalesce(sum(allocation.amount_applied) FILTER (
                WHERE transaction.is_voided = false
            ), 0)::numeric(18,2) AS allocated_amount
        FROM lending.loan_contract_installments installment
        LEFT JOIN lending.loan_installment_payment_allocations allocation
          ON allocation.installment_id = installment.id
        LEFT JOIN lending.collection_transactions transaction
          ON transaction.id = allocation.transaction_id
        WHERE installment.schedule_id = readiness.schedule_id
        GROUP BY installment.id
    ), lines AS (
        SELECT
            installment.installment_number,
            installment.due_date,
            installment.contractual_amount::numeric(18,2) AS contractual_amount,
            coalesce(allocation.allocated_amount, 0)::numeric(18,2) AS allocated_amount,
            greatest(
                installment.contractual_amount - coalesce(allocation.allocated_amount, 0),
                0
            )::numeric(18,2) AS remaining_amount
        FROM lending.loan_contract_installments installment
        LEFT JOIN allocation_rollup allocation
          ON allocation.installment_id = installment.id
        WHERE installment.schedule_id = readiness.schedule_id
        ORDER BY installment.installment_number
    )
    SELECT
        coalesce(
            jsonb_agg(
                jsonb_build_object(
                    'installment_number', installment_number,
                    'due_date', due_date,
                    'contractual_amount', contractual_amount,
                    'allocated_amount', allocated_amount,
                    'remaining_amount', remaining_amount
                ) ORDER BY installment_number
            ),
            '[]'::jsonb
        ),
        coalesce(sum(
            remaining_amount / power(
                1 + original_daily_eir,
                greatest(due_date - p_measurement_date, 0)
            )
        ), 0)
    INTO contractual_snapshot, contractual_pv
    FROM lines;

    IF jsonb_array_length(contractual_snapshot) = 0 THEN
        RAISE EXCEPTION 'Verified contractual installment snapshot is required.';
    END IF;

    FOR scenario IN
        SELECT value FROM jsonb_array_elements(p_scenarios)
    LOOP
        IF jsonb_typeof(scenario) <> 'object' THEN
            RAISE EXCEPTION 'Every ECL scenario must be an object.';
        END IF;
        scenario_key := btrim(coalesce(scenario ->> 'scenario_key', ''));
        support_reference := btrim(coalesce(scenario ->> 'evidence_reference', ''));
        scenario_rationale := btrim(coalesce(scenario ->> 'management_rationale', ''));

        IF scenario_key = '' THEN
            RAISE EXCEPTION 'Every ECL scenario requires a stable scenario_key.';
        END IF;
        IF scenario_key = ANY(seen_scenario_keys) THEN
            RAISE EXCEPTION 'Duplicate ECL scenario_key: %', scenario_key;
        END IF;
        seen_scenario_keys := array_append(seen_scenario_keys, scenario_key);
        IF support_reference = '' OR length(scenario_rationale) < 20 THEN
            RAISE EXCEPTION 'Every scenario requires retained evidence reference and substantive Management rationale.';
        END IF;
        IF jsonb_typeof(scenario -> 'probability') IS DISTINCT FROM 'number' THEN
            RAISE EXCEPTION 'Every scenario requires an explicit numeric probability.';
        END IF;
        probability_raw := (scenario ->> 'probability')::numeric;
        IF probability_raw <= 0 OR probability_raw > 1 THEN
            RAISE EXCEPTION 'Scenario probability must be greater than zero and no more than one.';
        END IF;
        IF probability_raw IS DISTINCT FROM round(probability_raw, 12) THEN
            RAISE EXCEPTION 'Scenario probability supports at most 12 decimal places; silent probability rounding is not allowed.';
        END IF;
        probability := round(probability_raw, 12);
        probability_total_value := probability_total_value + probability;

        IF jsonb_typeof(scenario -> 'forward_evidence_ids') IS DISTINCT FROM 'array'
           OR jsonb_array_length(scenario -> 'forward_evidence_ids') = 0 THEN
            RAISE EXCEPTION 'Every numeric scenario requires at least one exact approved forward-looking evidence id.';
        END IF;

        forward_evidence_count := 0;
        FOR evidence_json IN
            SELECT value FROM jsonb_array_elements(scenario -> 'forward_evidence_ids')
        LOOP
            IF jsonb_typeof(evidence_json) IS DISTINCT FROM 'string' THEN
                RAISE EXCEPTION 'Forward-looking evidence ids must be UUID strings.';
            END IF;
            evidence_id := trim(both '"' from evidence_json::text)::uuid;
            IF NOT EXISTS (
                SELECT 1
                FROM accounting.ecl_forward_looking_evidence_status evidence
                WHERE evidence.id = evidence_id
                  AND evidence.ready_for_new_measurement
            ) THEN
                RAISE EXCEPTION 'Scenario forward-looking evidence % is not current and approved for a new measurement.', evidence_id;
            END IF;
            forward_evidence_count := forward_evidence_count + 1;
            IF NOT evidence_id = ANY(all_forward_evidence_ids) THEN
                all_forward_evidence_ids := array_append(all_forward_evidence_ids, evidence_id);
            END IF;
        END LOOP;
        IF forward_evidence_count = 0 THEN
            RAISE EXCEPTION 'Every scenario requires current approved forward-looking evidence.';
        END IF;

        IF jsonb_typeof(scenario -> 'expected_cash_flows') IS DISTINCT FROM 'array' THEN
            RAISE EXCEPTION 'Every scenario requires an expected_cash_flows array; an empty array explicitly represents no expected receipts.';
        END IF;

        seen_expected_dates := ARRAY[]::date[];
        expected_pv := 0;
        FOR flow IN
            SELECT value FROM jsonb_array_elements(scenario -> 'expected_cash_flows')
        LOOP
            IF jsonb_typeof(flow) <> 'object'
               OR flow ->> 'cash_date' IS NULL
               OR jsonb_typeof(flow -> 'amount') IS DISTINCT FROM 'number' THEN
                RAISE EXCEPTION 'Expected cash-flow lines require cash_date and numeric amount.';
            END IF;
            expected_date := (flow ->> 'cash_date')::date;
            expected_amount_raw := (flow ->> 'amount')::numeric;
            IF expected_date < p_measurement_date THEN
                RAISE EXCEPTION 'Expected cash receipt dates cannot precede the measurement date.';
            END IF;
            IF expected_date = ANY(seen_expected_dates) THEN
                RAISE EXCEPTION 'Expected cash receipt dates must be unique within a scenario.';
            END IF;
            seen_expected_dates := array_append(seen_expected_dates, expected_date);
            IF expected_amount_raw <= 0 THEN
                RAISE EXCEPTION 'Expected cash receipt amounts must be positive; use an empty array for no expected receipts.';
            END IF;
            IF expected_amount_raw IS DISTINCT FROM round(expected_amount_raw, 2) THEN
                RAISE EXCEPTION 'Expected cash receipts must use exact currency-cent precision.';
            END IF;
            expected_amount := round(expected_amount_raw, 2);
            expected_pv := expected_pv + expected_amount / power(
                1 + original_daily_eir,
                expected_date - p_measurement_date
            );
        END LOOP;

        SELECT coalesce(
            jsonb_agg(
                jsonb_build_object(
                    'cash_date', line.cash_date,
                    'amount', line.amount
                ) ORDER BY line.cash_date
            ),
            '[]'::jsonb
        )
        INTO normalized_expected
        FROM jsonb_to_recordset(scenario -> 'expected_cash_flows')
            AS line(cash_date DATE, amount NUMERIC(18,2));

        scenario_shortfall := greatest(contractual_pv - expected_pv, 0);
        weighted_shortfall := weighted_shortfall + probability * scenario_shortfall;

        normalized_scenarios := normalized_scenarios || jsonb_build_array(
            jsonb_build_object(
                'scenario_key', scenario_key,
                'probability', probability,
                'evidence_reference', support_reference,
                'management_rationale', scenario_rationale,
                'forward_evidence_ids', scenario -> 'forward_evidence_ids',
                'expected_cash_flows', normalized_expected,
                'expected_cash_flow_pv', round(expected_pv, 12),
                'cash_shortfall_pv', round(scenario_shortfall, 12)
            )
        );
    END LOOP;

    IF probability_total_value IS DISTINCT FROM 1.000000000000::numeric THEN
        RAISE EXCEPTION 'Scenario probabilities must sum exactly to 1.000000000000; received %.', probability_total_value;
    END IF;

    SELECT coalesce(jsonb_agg(value ORDER BY value ->> 'scenario_key'), '[]'::jsonb)
    INTO normalized_scenarios
    FROM jsonb_array_elements(normalized_scenarios);

    SELECT coalesce(array_agg(DISTINCT evidence_id ORDER BY evidence_id), ARRAY[]::uuid[])
    INTO all_forward_evidence_ids
    FROM unnest(all_forward_evidence_ids) AS evidence_id;

    IF cardinality(all_forward_evidence_ids) = 0 THEN
        RAISE EXCEPTION 'At least one exact forward-looking evidence version must support the measurement.';
    END IF;

    input_snapshot := jsonb_build_object(
        'loan_id', readiness.loan_id,
        'loan_number', readiness.loan_number,
        'calculation_mode', readiness.calculation_mode,
        'schedule_id', readiness.schedule_id,
        'schedule_version', readiness.schedule_version,
        'contract_reference', readiness.contract_reference,
        'dpd_data_status', readiness.dpd_data_status,
        'days_past_due', readiness.days_past_due,
        'credit_risk_review_id', readiness.review_id,
        'credit_risk_review_version', readiness.review_version,
        'stage_label', readiness.stage_label,
        'default_label', readiness.default_label,
        'write_off_label', readiness.write_off_label,
        'recovery_label', readiness.recovery_label,
        'loss_horizon', loss_horizon_value,
        'original_eir_source_key', original_eir_source_key,
        'original_eir_policy_version', original_eir_policy_version,
        'original_daily_eir', original_daily_eir,
        'original_initial_gross_carrying_amount', original_initial_carrying,
        'forward_evidence_ids', all_forward_evidence_ids,
        'contractual_schedule_dpd_ready', readiness.contractual_schedule_dpd_ready,
        'current_credit_risk_label_ready', readiness.current_credit_risk_label_ready,
        'original_eir_initial_carrying_ready', readiness.original_eir_initial_carrying_ready,
        'protected_collection_posting_reversal_history_ready', readiness.protected_collection_posting_reversal_history_ready,
        'authoritative_current_carrying_ready', readiness.authoritative_current_carrying_ready,
        'required_loss_recovery_writeoff_outcome_evidence_ready', readiness.required_loss_recovery_writeoff_outcome_evidence_ready,
        'approved_forward_looking_evidence_ready', readiness.approved_forward_looking_evidence_ready,
        'quantitative_input_ready', readiness.quantitative_input_ready
    );

    ecl_amount_value := round(weighted_shortfall, 2);
    calculation_digest_value := encode(
        sha256(
            convert_to(
                concat_ws(
                    '|',
                    'loan_level_probability_weighted_discounted_cash_shortfall_v1',
                    p_loan_id::text,
                    p_measurement_date::text,
                    input_snapshot::text,
                    contractual_snapshot::text,
                    normalized_scenarios::text,
                    round(contractual_pv, 12)::text,
                    round(weighted_shortfall, 12)::text,
                    ecl_amount_value::text
                ),
                'UTF8'
            )
        ),
        'hex'
    );

    SELECT id INTO existing_id
    FROM accounting.ecl_quantitative_measurements
    WHERE loan_id = p_loan_id
      AND measurement_date = p_measurement_date
      AND calculation_digest = calculation_digest_value;
    IF existing_id IS NOT NULL THEN
        RETURN existing_id;
    END IF;

    SELECT coalesce(max(measurement_version), 0) + 1
    INTO next_version
    FROM accounting.ecl_quantitative_measurements
    WHERE loan_id = p_loan_id;

    PERFORM set_config(
        'accounting.ecl_quantitative_measurement_insert_allowed',
        'on',
        true
    );

    INSERT INTO accounting.ecl_quantitative_measurements (
        loan_id, measurement_version, measurement_date, stage_label, loss_horizon,
        schedule_id, schedule_version, contract_reference,
        label_review_id, label_review_version,
        original_eir_source_key, original_eir_policy_version, original_daily_eir,
        original_initial_gross_carrying_amount, forward_evidence_ids,
        input_snapshot, contractual_cash_flow_snapshot, scenario_snapshot,
        scenario_count, probability_total, contractual_cash_flow_pv,
        weighted_expected_cash_shortfall, ecl_amount,
        calculation_policy_version, discount_basis, rounding_policy,
        calculation_digest, review_rationale, reviewed_by_user_id
    ) VALUES (
        p_loan_id, next_version, p_measurement_date, readiness.stage_label,
        loss_horizon_value, readiness.schedule_id, readiness.schedule_version,
        readiness.contract_reference, readiness.review_id, readiness.review_version,
        original_eir_source_key, original_eir_policy_version, original_daily_eir,
        original_initial_carrying, all_forward_evidence_ids,
        input_snapshot, contractual_snapshot, normalized_scenarios,
        scenario_count_value, probability_total_value,
        round(contractual_pv, 12), round(weighted_shortfall, 12), ecl_amount_value,
        'loan_level_probability_weighted_discounted_cash_shortfall_v1',
        'original_daily_eir_calendar_days_to_measurement_date',
        'numeric_high_precision_final_currency_cent',
        calculation_digest_value, btrim(p_review_rationale), p_actor_user_id
    )
    RETURNING id INTO created_id;

    PERFORM set_config(
        'accounting.ecl_quantitative_measurement_insert_allowed',
        'off',
        true
    );

    INSERT INTO core.audit_logs (actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.ecl.read_only_measurement.recorded',
        'ecl_quantitative_measurement',
        created_id,
        jsonb_build_object(
            'loan_id', p_loan_id::text,
            'measurement_date', p_measurement_date,
            'stage_label', readiness.stage_label,
            'loss_horizon', loss_horizon_value,
            'measurement_version', next_version,
            'calculation_digest', calculation_digest_value,
            'ecl_amount', ecl_amount_value,
            'account_1190_posting_enabled', false,
            'automatic_source_posting', false
        )
    );

    RETURN created_id;
END;
$$;

CREATE OR REPLACE VIEW accounting.ecl_quantitative_measurement_queue AS
WITH latest_today AS (
    SELECT DISTINCT ON (measurement.loan_id)
        measurement.*
    FROM accounting.ecl_quantitative_measurements measurement
    WHERE measurement.measurement_date = current_date
    ORDER BY measurement.loan_id, measurement.measurement_version DESC
)
SELECT
    readiness.loan_id,
    readiness.loan_number,
    readiness.loan_status,
    readiness.loan_type_code,
    readiness.loan_type_name,
    readiness.calculation_mode,
    readiness.schedule_id,
    readiness.schedule_version,
    readiness.contract_reference,
    readiness.stage_label,
    readiness.review_id,
    readiness.review_version,
    readiness.blocker_codes,
    readiness.blockers,
    readiness.quantitative_input_ready,
    measurement.id AS measurement_id,
    measurement.measurement_version,
    measurement.measurement_date,
    measurement.loss_horizon,
    measurement.calculation_digest,
    CASE
        WHEN readiness.quantitative_input_ready = false THEN 'input_blocked'
        WHEN measurement.id IS NULL THEN 'measurement_required'
        WHEN measurement.schedule_id IS DISTINCT FROM readiness.schedule_id
          OR measurement.schedule_version IS DISTINCT FROM readiness.schedule_version
          OR measurement.label_review_id IS DISTINCT FROM readiness.review_id
          OR measurement.label_review_version IS DISTINCT FROM readiness.review_version
            THEN 'new_measurement_required'
        ELSE 'measured_read_only'
    END AS measurement_status,
    CASE
        WHEN readiness.quantitative_input_ready
         AND measurement.id IS NOT NULL
         AND measurement.schedule_id = readiness.schedule_id
         AND measurement.schedule_version = readiness.schedule_version
         AND measurement.label_review_id = readiness.review_id
         AND measurement.label_review_version = readiness.review_version
            THEN measurement.ecl_amount
        ELSE NULL::numeric(18,2)
    END AS authoritative_ecl_amount,
    true AS read_only_ecl_calculation_enabled,
    false AS account_1190_posting_enabled,
    false AS automatic_source_posting
FROM accounting.ecl_quantitative_input_readiness readiness
LEFT JOIN latest_today measurement
  ON measurement.loan_id = readiness.loan_id;

CREATE OR REPLACE VIEW accounting.ecl_quantitative_measurement_summary AS
SELECT
    count(*)::bigint AS loan_count,
    count(*) FILTER (WHERE quantitative_input_ready)::bigint AS input_ready_count,
    count(*) FILTER (WHERE measurement_status = 'input_blocked')::bigint AS input_blocked_count,
    count(*) FILTER (WHERE measurement_status = 'measurement_required')::bigint AS measurement_required_count,
    count(*) FILTER (WHERE measurement_status = 'new_measurement_required')::bigint AS new_measurement_required_count,
    count(*) FILTER (WHERE measurement_status = 'measured_read_only')::bigint AS measured_count,
    coalesce(sum(authoritative_ecl_amount), 0)::numeric(18,2) AS authoritative_ecl_total,
    true AS read_only_ecl_calculation_enabled,
    false AS account_1190_posting_enabled,
    false AS automatic_source_posting
FROM accounting.ecl_quantitative_measurement_queue;

COMMENT ON TABLE accounting.ecl_quantitative_measurements IS
'Immutable A3 read-only ECL snapshots. Each record pins exact protected schedule/label/EIR/forward-evidence versions, contractual and expected cash-flow scenarios, probability weights, discount basis, deterministic digest and final currency-cent ECL. It is not an allowance posting.';

COMMENT ON FUNCTION accounting.record_read_only_quantitative_ecl_measurement(
    UUID, DATE, JSONB, TEXT, UUID
) IS
'Protected Management A3 measurement using probability-weighted discounted expected cash shortfalls and the applicable original daily EIR. Stage 1 is a 12-month credit-loss-event horizon, not a 12-month cash-flow truncation. Blocked inputs produce no measurement.';

COMMENT ON VIEW accounting.ecl_quantitative_measurement_queue IS
'Read-only A3 queue. Blocked/incomplete loans always expose authoritative_ecl_amount NULL. Account 1190 and automatic source posting remain disabled.';

COMMIT;
