BEGIN;

-- This migration records an explicit Management accounting-policy decision for
-- a renewal only after the read-only treatment-readiness evidence has been
-- reviewed. It deliberately creates no treatment journal coordinates and does
-- not infer modification versus derecognition from a quantitative percentage.

INSERT INTO core.permissions (code, description)
VALUES (
    'accounting.renewal_treatment_decision.manage',
    'Record or explicitly void immutable Management-reviewed renewal modification-versus-derecognition decision evidence without creating journal lines or enabling automatic posting'
)
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code = 'accounting.renewal_treatment_decision.manage'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.renewal_treatment_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    renewal_execution_event_id UUID NOT NULL
        REFERENCES lending.loan_renewal_execution_events(id) ON DELETE RESTRICT,
    old_loan_id UUID NOT NULL
        REFERENCES lending.loans(id) ON DELETE RESTRICT,
    new_loan_id UUID NOT NULL
        REFERENCES lending.loans(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL
        REFERENCES lending.clients(id) ON DELETE RESTRICT,
    renewal_business_date DATE NOT NULL,
    readiness_review_token TEXT NOT NULL,
    readiness_policy_version TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (
        decision IN ('modification_no_derecognition', 'derecognition')
    ),
    decision_policy_version TEXT NOT NULL,
    accounting_policy_reference TEXT NOT NULL,
    qualitative_assessment JSONB NOT NULL,
    decision_rationale TEXT NOT NULL,
    supporting_evidence_reference TEXT NOT NULL,
    old_gross_carrying_amount NUMERIC(18,2) NOT NULL CHECK (
        old_gross_carrying_amount > 0
    ),
    original_daily_eir NUMERIC(24,12) NOT NULL CHECK (original_daily_eir > 0),
    renewal_cash_disbursed_amount NUMERIC(18,2) NOT NULL CHECK (
        renewal_cash_disbursed_amount >= 0
    ),
    renewal_settlement_amount NUMERIC(18,2) NOT NULL CHECK (
        renewal_settlement_amount >= 0
    ),
    renewal_other_deduction_amount NUMERIC(18,2) NOT NULL CHECK (
        renewal_other_deduction_amount >= 0
    ),
    schedule_id UUID NOT NULL
        REFERENCES lending.loan_contract_schedules(id) ON DELETE RESTRICT,
    schedule_version INTEGER NOT NULL CHECK (schedule_version > 0),
    contract_reference TEXT NOT NULL,
    contract_evidence_reference TEXT NOT NULL,
    installment_count INTEGER NOT NULL CHECK (installment_count > 0),
    contractual_cash_total NUMERIC(18,2) NOT NULL CHECK (contractual_cash_total > 0),
    present_value_at_original_eir NUMERIC(18,2) NOT NULL CHECK (
        present_value_at_original_eir > 0
    ),
    present_value_change_amount NUMERIC(18,2) NOT NULL,
    present_value_change_percent NUMERIC(18,6) NOT NULL CHECK (
        present_value_change_percent >= 0
    ),
    reviewed_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (old_loan_id <> new_loan_id),
    CHECK (readiness_review_token ~ '^[0-9a-f]{64}$'),
    CHECK (readiness_policy_version = 'renewal_accounting_treatment_readiness_v1'),
    CHECK (decision_policy_version = 'renewal_treatment_decision_evidence_v1'),
    CHECK (btrim(accounting_policy_reference) <> ''),
    CHECK (jsonb_typeof(qualitative_assessment) = 'object'),
    CHECK (qualitative_assessment <> '{}'::jsonb),
    CHECK (length(btrim(decision_rationale)) >= 20),
    CHECK (btrim(supporting_evidence_reference) <> ''),
    CHECK (btrim(contract_reference) <> ''),
    CHECK (btrim(contract_evidence_reference) <> ''),
    CHECK (renewal_other_deduction_amount = 0)
);

CREATE INDEX IF NOT EXISTS renewal_treatment_decisions_event_idx
    ON accounting.renewal_treatment_decisions
       (renewal_execution_event_id, reviewed_at DESC);

CREATE TABLE IF NOT EXISTS accounting.renewal_treatment_decision_voids (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID NOT NULL UNIQUE
        REFERENCES accounting.renewal_treatment_decisions(id) ON DELETE RESTRICT,
    renewal_execution_event_id UUID NOT NULL
        REFERENCES lending.loan_renewal_execution_events(id) ON DELETE RESTRICT,
    void_reason TEXT NOT NULL CHECK (length(btrim(void_reason)) >= 3),
    voided_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    voided_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION accounting.guard_renewal_treatment_decision_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(
            current_setting('accounting.renewal_treatment_decision_insert_allowed', true),
            ''
       ) = 'on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Renewal treatment decision evidence is immutable and must use the protected Management-reviewed decision function.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_renewal_treatment_decision_guard
    ON accounting.renewal_treatment_decisions;
CREATE TRIGGER accounting_renewal_treatment_decision_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.renewal_treatment_decisions
FOR EACH ROW EXECUTE FUNCTION accounting.guard_renewal_treatment_decision_write();

CREATE OR REPLACE FUNCTION accounting.guard_renewal_treatment_decision_void_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(
            current_setting('accounting.renewal_treatment_decision_void_insert_allowed', true),
            ''
       ) = 'on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Renewal treatment decision void evidence is immutable and must use the protected void function.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_renewal_treatment_decision_void_guard
    ON accounting.renewal_treatment_decision_voids;
CREATE TRIGGER accounting_renewal_treatment_decision_void_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.renewal_treatment_decision_voids
FOR EACH ROW EXECUTE FUNCTION accounting.guard_renewal_treatment_decision_void_write();

CREATE OR REPLACE FUNCTION accounting.record_renewal_treatment_decision(
    p_renewal_execution_event_id UUID,
    p_old_loan_id UUID,
    p_new_loan_id UUID,
    p_client_id UUID,
    p_renewal_business_date DATE,
    p_readiness_review_token TEXT,
    p_readiness_policy_version TEXT,
    p_decision TEXT,
    p_decision_policy_version TEXT,
    p_accounting_policy_reference TEXT,
    p_qualitative_assessment JSONB,
    p_decision_rationale TEXT,
    p_supporting_evidence_reference TEXT,
    p_old_gross_carrying_amount NUMERIC,
    p_original_daily_eir NUMERIC,
    p_renewal_cash_disbursed_amount NUMERIC,
    p_renewal_settlement_amount NUMERIC,
    p_renewal_other_deduction_amount NUMERIC,
    p_schedule_id UUID,
    p_schedule_version INTEGER,
    p_contract_reference TEXT,
    p_contract_evidence_reference TEXT,
    p_installment_count INTEGER,
    p_contractual_cash_total NUMERIC,
    p_present_value_at_original_eir NUMERIC,
    p_present_value_change_amount NUMERIC,
    p_present_value_change_percent NUMERIC,
    p_actor_user_id UUID
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    source_row RECORD;
    schedule_rollup RECORD;
    existing_row accounting.renewal_treatment_decisions%ROWTYPE;
    created_id UUID;
    normalized_policy_reference TEXT := btrim(coalesce(p_accounting_policy_reference, ''));
    normalized_rationale TEXT := btrim(coalesce(p_decision_rationale, ''));
    normalized_support_reference TEXT := btrim(coalesce(p_supporting_evidence_reference, ''));
    normalized_contract_reference TEXT := btrim(coalesce(p_contract_reference, ''));
    normalized_contract_evidence_reference TEXT := btrim(coalesce(p_contract_evidence_reference, ''));
    old_carrying NUMERIC(18,2) := round(coalesce(p_old_gross_carrying_amount, 0), 2);
    cash_amount NUMERIC(18,2) := round(coalesce(p_renewal_cash_disbursed_amount, 0), 2);
    settlement_amount NUMERIC(18,2) := round(coalesce(p_renewal_settlement_amount, 0), 2);
    deduction_amount NUMERIC(18,2) := round(coalesce(p_renewal_other_deduction_amount, 0), 2);
    contractual_total NUMERIC(18,2) := round(coalesce(p_contractual_cash_total, 0), 2);
    pv_amount NUMERIC(18,2) := round(coalesce(p_present_value_at_original_eir, 0), 2);
    pv_change NUMERIC(18,2) := round(coalesce(p_present_value_change_amount, 0), 2);
    pv_change_percent NUMERIC(18,6) := round(coalesce(p_present_value_change_percent, 0), 6);
BEGIN
    IF p_renewal_execution_event_id IS NULL
       OR p_old_loan_id IS NULL
       OR p_new_loan_id IS NULL
       OR p_client_id IS NULL
       OR p_renewal_business_date IS NULL
       OR p_actor_user_id IS NULL THEN
        RAISE EXCEPTION 'Renewal treatment decision requires exact renewal, loan, client, date and Management actor identifiers.';
    END IF;
    IF p_old_loan_id = p_new_loan_id THEN
        RAISE EXCEPTION 'Renewal treatment decision requires distinct old and new loans.';
    END IF;
    IF coalesce(p_readiness_review_token, '') !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Renewal treatment decision requires the exact current readiness review token.';
    END IF;
    IF p_readiness_policy_version IS DISTINCT FROM 'renewal_accounting_treatment_readiness_v1' THEN
        RAISE EXCEPTION 'Unsupported renewal treatment readiness policy version.';
    END IF;
    IF p_decision_policy_version IS DISTINCT FROM 'renewal_treatment_decision_evidence_v1' THEN
        RAISE EXCEPTION 'Unsupported renewal treatment decision evidence policy version.';
    END IF;
    IF p_decision NOT IN ('modification_no_derecognition', 'derecognition') THEN
        RAISE EXCEPTION 'Renewal treatment decision must be an explicit reviewed modification_no_derecognition or derecognition decision.';
    END IF;
    IF normalized_policy_reference = '' THEN
        RAISE EXCEPTION 'Accounting policy reference is required for the renewal treatment decision.';
    END IF;
    IF p_qualitative_assessment IS NULL
       OR jsonb_typeof(p_qualitative_assessment) <> 'object'
       OR p_qualitative_assessment = '{}'::jsonb THEN
        RAISE EXCEPTION 'A non-empty qualitative accounting assessment object is required.';
    END IF;
    IF length(normalized_rationale) < 20 THEN
        RAISE EXCEPTION 'Enter a substantive rationale for the explicit renewal accounting treatment decision.';
    END IF;
    IF normalized_support_reference = '' THEN
        RAISE EXCEPTION 'Supporting accounting evidence reference is required.';
    END IF;
    IF old_carrying <= 0 OR coalesce(p_original_daily_eir, 0) <= 0 THEN
        RAISE EXCEPTION 'Authoritative old-loan carrying amount and original EIR are required.';
    END IF;
    IF cash_amount < 0 OR settlement_amount < 0 OR deduction_amount <> 0 THEN
        RAISE EXCEPTION 'Renewal treatment decision evidence requires non-negative cash/settlement and zero unresolved deductions.';
    END IF;
    IF p_schedule_id IS NULL OR coalesce(p_schedule_version, 0) <= 0 THEN
        RAISE EXCEPTION 'Exact verified renewal schedule identity is required.';
    END IF;
    IF normalized_contract_reference = '' OR normalized_contract_evidence_reference = '' THEN
        RAISE EXCEPTION 'Verified renewal contract and evidence references are required.';
    END IF;
    IF coalesce(p_installment_count, 0) <= 0 OR contractual_total <= 0 OR pv_amount <= 0 THEN
        RAISE EXCEPTION 'Positive verified renewal contractual cash-flow and present-value evidence is required.';
    END IF;
    IF pv_change_percent < 0 THEN
        RAISE EXCEPTION 'Informational present-value difference percentage cannot be negative.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended('renewal-treatment-decision:' || p_renewal_execution_event_id::text, 0)
    );

    SELECT
        execution.old_loan_id,
        execution.new_loan_id,
        execution.client_id,
        execution.business_date,
        execution.is_voided AS execution_is_voided,
        release.event_kind,
        release.business_date AS release_business_date,
        release.is_voided AS release_is_voided,
        release.cash_disbursed_amount,
        release.settlement_amount,
        release.other_deduction_amount,
        loan_type.calculation_mode,
        schedule.id AS schedule_id,
        schedule.schedule_version,
        schedule.status AS schedule_status,
        schedule.contract_reference,
        schedule.effective_from,
        registration.evidence_basis,
        registration.evidence_reference
    INTO source_row
    FROM lending.loan_renewal_execution_events execution
    JOIN lending.loan_disbursement_events release
      ON release.id = execution.disbursement_event_id
    JOIN lending.loans new_loan
      ON new_loan.id = execution.new_loan_id
    JOIN lending.loan_types loan_type
      ON loan_type.id = new_loan.loan_type_id
    JOIN lending.loan_contract_schedules schedule
      ON schedule.id = p_schedule_id
     AND schedule.loan_id = execution.new_loan_id
    JOIN lending.loan_contract_schedule_registrations registration
      ON registration.schedule_id = schedule.id
    WHERE execution.id = p_renewal_execution_event_id
    FOR SHARE OF execution, release, new_loan, loan_type, schedule, registration;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Authoritative renewal execution and verified renewal contract evidence were not found.';
    END IF;
    IF source_row.execution_is_voided OR source_row.release_is_voided THEN
        RAISE EXCEPTION 'Voided renewal execution or release evidence cannot support an accounting treatment decision.';
    END IF;
    IF source_row.old_loan_id IS DISTINCT FROM p_old_loan_id
       OR source_row.new_loan_id IS DISTINCT FROM p_new_loan_id
       OR source_row.client_id IS DISTINCT FROM p_client_id
       OR source_row.business_date IS DISTINCT FROM p_renewal_business_date THEN
        RAISE EXCEPTION 'Renewal treatment decision identifiers do not match authoritative renewal execution evidence.';
    END IF;
    IF source_row.event_kind IS DISTINCT FROM 'renewal_release'
       OR source_row.release_business_date IS DISTINCT FROM p_renewal_business_date THEN
        RAISE EXCEPTION 'Renewal treatment decision requires matching active renewal_release evidence.';
    END IF;
    IF source_row.calculation_mode IS DISTINCT FROM 'fixed_daily' THEN
        RAISE EXCEPTION 'Renewal treatment decision v1 supports only Regular fixed-daily renewals.';
    END IF;
    IF round(source_row.cash_disbursed_amount, 2) IS DISTINCT FROM cash_amount
       OR round(source_row.settlement_amount, 2) IS DISTINCT FROM settlement_amount
       OR round(source_row.other_deduction_amount, 2) IS DISTINCT FROM deduction_amount THEN
        RAISE EXCEPTION 'Renewal treatment decision cash components do not match authoritative release evidence.';
    END IF;
    IF source_row.schedule_id IS DISTINCT FROM p_schedule_id
       OR source_row.schedule_version IS DISTINCT FROM p_schedule_version
       OR source_row.schedule_status IS DISTINCT FROM 'active'
       OR source_row.effective_from IS DISTINCT FROM p_renewal_business_date
       OR btrim(source_row.contract_reference) IS DISTINCT FROM normalized_contract_reference
       OR source_row.evidence_basis IS DISTINCT FROM 'signed_renewal_contract'
       OR btrim(source_row.evidence_reference) IS DISTINCT FROM normalized_contract_evidence_reference THEN
        RAISE EXCEPTION 'Renewal treatment decision schedule snapshot does not match the active verified signed renewal contract.';
    END IF;

    SELECT
        count(*)::integer AS installment_count,
        coalesce(sum(installment.contractual_amount), 0)::numeric(18,2) AS contractual_cash_total,
        count(*) FILTER (
            WHERE installment.due_date <= p_renewal_business_date
        )::integer AS nonfuture_count
    INTO schedule_rollup
    FROM lending.loan_contract_installments installment
    WHERE installment.schedule_id = p_schedule_id;

    IF schedule_rollup.installment_count IS DISTINCT FROM p_installment_count
       OR schedule_rollup.contractual_cash_total IS DISTINCT FROM contractual_total
       OR schedule_rollup.nonfuture_count <> 0 THEN
        RAISE EXCEPTION 'Renewal treatment decision contractual cash-flow snapshot does not match the verified future renewal schedule.';
    END IF;

    SELECT decision.*
    INTO existing_row
    FROM accounting.renewal_treatment_decisions decision
    LEFT JOIN accounting.renewal_treatment_decision_voids voided
      ON voided.decision_id = decision.id
    WHERE decision.renewal_execution_event_id = p_renewal_execution_event_id
      AND voided.id IS NULL
    ORDER BY decision.reviewed_at DESC
    LIMIT 1
    FOR UPDATE OF decision;

    IF FOUND THEN
        IF existing_row.old_loan_id = p_old_loan_id
           AND existing_row.new_loan_id = p_new_loan_id
           AND existing_row.client_id = p_client_id
           AND existing_row.renewal_business_date = p_renewal_business_date
           AND existing_row.readiness_review_token = p_readiness_review_token
           AND existing_row.readiness_policy_version = p_readiness_policy_version
           AND existing_row.decision = p_decision
           AND existing_row.decision_policy_version = p_decision_policy_version
           AND existing_row.accounting_policy_reference = normalized_policy_reference
           AND existing_row.qualitative_assessment = p_qualitative_assessment
           AND existing_row.decision_rationale = normalized_rationale
           AND existing_row.supporting_evidence_reference = normalized_support_reference
           AND existing_row.old_gross_carrying_amount = old_carrying
           AND existing_row.original_daily_eir = p_original_daily_eir
           AND existing_row.renewal_cash_disbursed_amount = cash_amount
           AND existing_row.renewal_settlement_amount = settlement_amount
           AND existing_row.renewal_other_deduction_amount = deduction_amount
           AND existing_row.schedule_id = p_schedule_id
           AND existing_row.schedule_version = p_schedule_version
           AND existing_row.contract_reference = normalized_contract_reference
           AND existing_row.contract_evidence_reference = normalized_contract_evidence_reference
           AND existing_row.installment_count = p_installment_count
           AND existing_row.contractual_cash_total = contractual_total
           AND existing_row.present_value_at_original_eir = pv_amount
           AND existing_row.present_value_change_amount = pv_change
           AND existing_row.present_value_change_percent = pv_change_percent
           AND existing_row.reviewed_by_user_id = p_actor_user_id THEN
            RETURN existing_row.id;
        END IF;
        RAISE EXCEPTION 'Different active renewal treatment decision evidence already exists; void it explicitly before recording a correction.';
    END IF;

    PERFORM set_config('accounting.renewal_treatment_decision_insert_allowed', 'on', true);
    INSERT INTO accounting.renewal_treatment_decisions (
        renewal_execution_event_id,
        old_loan_id,
        new_loan_id,
        client_id,
        renewal_business_date,
        readiness_review_token,
        readiness_policy_version,
        decision,
        decision_policy_version,
        accounting_policy_reference,
        qualitative_assessment,
        decision_rationale,
        supporting_evidence_reference,
        old_gross_carrying_amount,
        original_daily_eir,
        renewal_cash_disbursed_amount,
        renewal_settlement_amount,
        renewal_other_deduction_amount,
        schedule_id,
        schedule_version,
        contract_reference,
        contract_evidence_reference,
        installment_count,
        contractual_cash_total,
        present_value_at_original_eir,
        present_value_change_amount,
        present_value_change_percent,
        reviewed_by_user_id
    )
    VALUES (
        p_renewal_execution_event_id,
        p_old_loan_id,
        p_new_loan_id,
        p_client_id,
        p_renewal_business_date,
        p_readiness_review_token,
        p_readiness_policy_version,
        p_decision,
        p_decision_policy_version,
        normalized_policy_reference,
        p_qualitative_assessment,
        normalized_rationale,
        normalized_support_reference,
        old_carrying,
        p_original_daily_eir,
        cash_amount,
        settlement_amount,
        deduction_amount,
        p_schedule_id,
        p_schedule_version,
        normalized_contract_reference,
        normalized_contract_evidence_reference,
        p_installment_count,
        contractual_total,
        pv_amount,
        pv_change,
        pv_change_percent,
        p_actor_user_id
    )
    RETURNING id INTO created_id;
    PERFORM set_config('accounting.renewal_treatment_decision_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs (
        actor_user_id,
        action,
        target_type,
        target_id,
        details
    )
    VALUES (
        p_actor_user_id,
        'accounting.renewal_treatment_decision.recorded',
        'renewal_treatment_decision',
        created_id,
        jsonb_build_object(
            'renewal_execution_event_id', p_renewal_execution_event_id::text,
            'old_loan_id', p_old_loan_id::text,
            'new_loan_id', p_new_loan_id::text,
            'decision', p_decision,
            'readiness_review_token', p_readiness_review_token,
            'present_value_change_percent', pv_change_percent,
            'automatic_classification_enabled', false,
            'quantitative_threshold_decisive', false,
            'journal_lines_enabled', false,
            'automatic_source_posting', false
        )
    );

    RETURN created_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.void_renewal_treatment_decision(
    p_decision_id UUID,
    p_actor_user_id UUID,
    p_reason TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    decision_row accounting.renewal_treatment_decisions%ROWTYPE;
    existing_void accounting.renewal_treatment_decision_voids%ROWTYPE;
    normalized_reason TEXT := btrim(coalesce(p_reason, ''));
    created_id UUID;
BEGIN
    IF length(normalized_reason) < 3 THEN
        RAISE EXCEPTION 'Enter a clear reason for voiding renewal treatment decision evidence.';
    END IF;

    SELECT *
    INTO decision_row
    FROM accounting.renewal_treatment_decisions decision
    WHERE decision.id = p_decision_id
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Renewal treatment decision evidence was not found.';
    END IF;

    SELECT *
    INTO existing_void
    FROM accounting.renewal_treatment_decision_voids voided
    WHERE voided.decision_id = p_decision_id
    FOR UPDATE;
    IF FOUND THEN
        IF existing_void.voided_by_user_id = p_actor_user_id
           AND existing_void.void_reason = normalized_reason THEN
            RETURN existing_void.id;
        END IF;
        RAISE EXCEPTION 'Renewal treatment decision evidence was already voided with different evidence.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM accounting.journal_entries journal
        WHERE journal.source_reference = p_decision_id::text
          AND journal.source_type IN (
              'renewal_modification',
              'renewal_derecognition'
          )
    ) THEN
        RAISE EXCEPTION 'Renewal treatment decision already has protected accounting journal history; use the future controlled treatment correction/reversal path.';
    END IF;

    PERFORM set_config('accounting.renewal_treatment_decision_void_insert_allowed', 'on', true);
    INSERT INTO accounting.renewal_treatment_decision_voids (
        decision_id,
        renewal_execution_event_id,
        void_reason,
        voided_by_user_id
    )
    VALUES (
        p_decision_id,
        decision_row.renewal_execution_event_id,
        normalized_reason,
        p_actor_user_id
    )
    RETURNING id INTO created_id;
    PERFORM set_config('accounting.renewal_treatment_decision_void_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs (
        actor_user_id,
        action,
        target_type,
        target_id,
        details
    )
    VALUES (
        p_actor_user_id,
        'accounting.renewal_treatment_decision.voided',
        'renewal_treatment_decision',
        p_decision_id,
        jsonb_build_object(
            'renewal_execution_event_id', decision_row.renewal_execution_event_id::text,
            'decision', decision_row.decision,
            'reason', normalized_reason,
            'journal_lines_enabled', false,
            'automatic_source_posting', false
        )
    );

    RETURN created_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.guard_renewal_execution_treatment_decision_history()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.is_voided = false AND NEW.is_voided = true
       AND EXISTS (
            SELECT 1
            FROM accounting.renewal_treatment_decisions decision
            LEFT JOIN accounting.renewal_treatment_decision_voids voided
              ON voided.decision_id = decision.id
            WHERE decision.renewal_execution_event_id = OLD.id
              AND voided.id IS NULL
       ) THEN
        RAISE EXCEPTION 'Renewal execution evidence has an active reviewed accounting treatment decision; void the decision evidence first.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_renewal_execution_treatment_decision_history_guard
    ON lending.loan_renewal_execution_events;
CREATE TRIGGER lending_renewal_execution_treatment_decision_history_guard
BEFORE UPDATE ON lending.loan_renewal_execution_events
FOR EACH ROW EXECUTE FUNCTION accounting.guard_renewal_execution_treatment_decision_history();

CREATE OR REPLACE VIEW accounting.renewal_treatment_decision_status AS
SELECT
    decision.id AS decision_id,
    decision.renewal_execution_event_id,
    decision.old_loan_id,
    old_loan.loan_number AS old_loan_number,
    decision.new_loan_id,
    new_loan.loan_number AS new_loan_number,
    decision.client_id,
    client.client_code,
    client.full_name AS client_name,
    decision.renewal_business_date,
    decision.readiness_review_token,
    decision.readiness_policy_version,
    decision.decision,
    decision.decision_policy_version,
    decision.accounting_policy_reference,
    decision.qualitative_assessment,
    decision.decision_rationale,
    decision.supporting_evidence_reference,
    decision.old_gross_carrying_amount,
    decision.original_daily_eir,
    decision.renewal_cash_disbursed_amount,
    decision.renewal_settlement_amount,
    decision.renewal_other_deduction_amount,
    decision.schedule_id,
    decision.schedule_version,
    decision.contract_reference,
    decision.contract_evidence_reference,
    decision.installment_count,
    decision.contractual_cash_total,
    decision.present_value_at_original_eir,
    decision.present_value_change_amount,
    decision.present_value_change_percent,
    decision.reviewed_by_user_id,
    decision.reviewed_at,
    voided.id AS void_id,
    voided.void_reason,
    voided.voided_by_user_id,
    voided.voided_at,
    (voided.id IS NULL) AS is_active,
    false AS automatic_classification_enabled,
    false AS quantitative_threshold_decisive,
    false AS journal_lines_enabled,
    false AS automatic_source_posting
FROM accounting.renewal_treatment_decisions decision
JOIN lending.loans old_loan ON old_loan.id = decision.old_loan_id
JOIN lending.loans new_loan ON new_loan.id = decision.new_loan_id
JOIN lending.clients client ON client.id = decision.client_id
LEFT JOIN accounting.renewal_treatment_decision_voids voided
  ON voided.decision_id = decision.id;

COMMIT;
