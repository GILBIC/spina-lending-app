BEGIN;

-- Master Issue #296: protected evidence-backed staging/default/write-off/recovery
-- labels. This migration deliberately records classification evidence only. It
-- does not calculate ECL, does not post account 1190, does not execute a
-- write-off, and does not enable automatic source posting.

INSERT INTO core.permissions (code, description)
VALUES (
    'accounting.ecl.credit_risk_label.review',
    'Review and record evidence-backed ECL stage, default, write-off-support, recovery and cure labels without calculating or posting ECL'
)
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code = 'accounting.ecl.credit_risk_label.review'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.ecl_credit_risk_label_reviews (
    id BIGSERIAL PRIMARY KEY,
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    review_version INTEGER NOT NULL CHECK (review_version > 0),
    stage_label TEXT NOT NULL CHECK (
        stage_label IN (
            'stage_1_12_month',
            'stage_2_lifetime',
            'stage_3_credit_impaired'
        )
    ),
    default_label BOOLEAN NOT NULL,
    write_off_label TEXT NOT NULL DEFAULT 'none' CHECK (
        write_off_label IN (
            'none',
            'supported_no_reasonable_expectation_of_recovery'
        )
    ),
    recovery_label TEXT NOT NULL DEFAULT 'none' CHECK (
        recovery_label IN (
            'none',
            'cash_recovery_observed',
            'cured'
        )
    ),
    primary_evidence_basis TEXT NOT NULL CHECK (
        primary_evidence_basis IN (
            'contractual_dpd',
            'protected_collection_history',
            'verified_source_document',
            'verified_qualitative_credit_event',
            'authoritative_external_evidence'
        )
    ),
    evidence_reference TEXT NOT NULL,
    review_note TEXT NOT NULL,
    snapshot_schedule_id UUID NOT NULL
        REFERENCES lending.loan_contract_schedules(id) ON DELETE RESTRICT,
    snapshot_schedule_version INTEGER NOT NULL CHECK (snapshot_schedule_version > 0),
    snapshot_days_past_due INTEGER NOT NULL CHECK (snapshot_days_past_due >= 0),
    snapshot_due_unpaid_amount NUMERIC(18,2) NOT NULL CHECK (snapshot_due_unpaid_amount >= 0),
    snapshot_thirty_day_backstop BOOLEAN NOT NULL,
    snapshot_ninety_day_backstop BOOLEAN NOT NULL,
    snapshot_dpd_risk_band TEXT NOT NULL CHECK (
        snapshot_dpd_risk_band IN (
            'current',
            'past_due_1_29',
            'past_due_30_89',
            'past_due_90_plus'
        )
    ),
    sicr_backstop_rebutted BOOLEAN NOT NULL DEFAULT false,
    default_backstop_rebutted BOOLEAN NOT NULL DEFAULT false,
    rebuttal_evidence_reference TEXT,
    rebuttal_note TEXT,
    write_off_evidence_reference TEXT,
    write_off_note TEXT,
    recovery_transaction_id UUID
        REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    reviewer_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    supersedes_review_id BIGINT
        REFERENCES accounting.ecl_credit_risk_label_reviews(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (loan_id, review_version),
    CHECK (btrim(evidence_reference) <> ''),
    CHECK (btrim(review_note) <> ''),
    CHECK (
        (recovery_label = 'cash_recovery_observed' AND recovery_transaction_id IS NOT NULL)
        OR (recovery_label <> 'cash_recovery_observed' AND recovery_transaction_id IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS ix_ecl_credit_risk_label_reviews_loan_created
    ON accounting.ecl_credit_risk_label_reviews(loan_id, review_version DESC);
CREATE INDEX IF NOT EXISTS ix_ecl_credit_risk_label_reviews_recovery_tx
    ON accounting.ecl_credit_risk_label_reviews(recovery_transaction_id)
    WHERE recovery_transaction_id IS NOT NULL;

CREATE OR REPLACE FUNCTION accounting.guard_ecl_credit_risk_label_audit()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'ECL credit-risk label review records are immutable.';
END;
$$;

DROP TRIGGER IF EXISTS ecl_credit_risk_label_audit_guard
    ON accounting.ecl_credit_risk_label_reviews;
CREATE TRIGGER ecl_credit_risk_label_audit_guard
BEFORE UPDATE OR DELETE ON accounting.ecl_credit_risk_label_reviews
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_credit_risk_label_audit();

CREATE OR REPLACE FUNCTION accounting.review_ecl_credit_risk_labels(
    p_loan_id UUID,
    p_stage_label TEXT,
    p_default_label BOOLEAN,
    p_write_off_label TEXT,
    p_recovery_label TEXT,
    p_primary_evidence_basis TEXT,
    p_evidence_reference TEXT,
    p_review_note TEXT,
    p_sicr_backstop_rebutted BOOLEAN,
    p_default_backstop_rebutted BOOLEAN,
    p_rebuttal_evidence_reference TEXT,
    p_rebuttal_note TEXT,
    p_write_off_evidence_reference TEXT,
    p_write_off_note TEXT,
    p_recovery_transaction_id UUID,
    p_actor_user_id UUID
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    dpd accounting.loan_contract_dpd_assessment%ROWTYPE;
    prior_review accounting.ecl_credit_risk_label_reviews%ROWTYPE;
    normalized_stage TEXT;
    normalized_write_off TEXT;
    normalized_recovery TEXT;
    normalized_basis TEXT;
    normalized_evidence_reference TEXT;
    normalized_review_note TEXT;
    normalized_rebuttal_reference TEXT;
    normalized_rebuttal_note TEXT;
    normalized_write_off_reference TEXT;
    normalized_write_off_note TEXT;
    current_risk_band TEXT;
    prior_review_id BIGINT;
    next_version INTEGER;
    recovery_tx lending.collection_transactions%ROWTYPE;
    new_review_id BIGINT;
    locked_loan_id UUID;
BEGIN
    normalized_stage := lower(trim(coalesce(p_stage_label, '')));
    normalized_write_off := lower(trim(coalesce(p_write_off_label, '')));
    normalized_recovery := lower(trim(coalesce(p_recovery_label, '')));
    normalized_basis := lower(trim(coalesce(p_primary_evidence_basis, '')));
    normalized_evidence_reference := trim(coalesce(p_evidence_reference, ''));
    normalized_review_note := trim(coalesce(p_review_note, ''));
    normalized_rebuttal_reference := trim(coalesce(p_rebuttal_evidence_reference, ''));
    normalized_rebuttal_note := trim(coalesce(p_rebuttal_note, ''));
    normalized_write_off_reference := trim(coalesce(p_write_off_evidence_reference, ''));
    normalized_write_off_note := trim(coalesce(p_write_off_note, ''));

    IF p_loan_id IS NULL THEN
        RAISE EXCEPTION 'Loan id is required.';
    END IF;
    IF normalized_stage NOT IN (
        'stage_1_12_month',
        'stage_2_lifetime',
        'stage_3_credit_impaired'
    ) THEN
        RAISE EXCEPTION 'A supported ECL stage label is required.';
    END IF;
    IF p_default_label IS NULL THEN
        RAISE EXCEPTION 'An explicit reviewed default/non-default label is required.';
    END IF;
    IF normalized_write_off NOT IN (
        'none',
        'supported_no_reasonable_expectation_of_recovery'
    ) THEN
        RAISE EXCEPTION 'A supported write-off label is required.';
    END IF;
    IF normalized_recovery NOT IN ('none', 'cash_recovery_observed', 'cured') THEN
        RAISE EXCEPTION 'A supported recovery/cure label is required.';
    END IF;
    IF normalized_basis NOT IN (
        'contractual_dpd',
        'protected_collection_history',
        'verified_source_document',
        'verified_qualitative_credit_event',
        'authoritative_external_evidence'
    ) THEN
        RAISE EXCEPTION 'A supported primary evidence basis is required.';
    END IF;
    IF normalized_evidence_reference = '' THEN
        RAISE EXCEPTION 'Evidence reference is required.';
    END IF;
    IF normalized_review_note = '' THEN
        RAISE EXCEPTION 'Review note is required.';
    END IF;
    IF p_actor_user_id IS NULL THEN
        RAISE EXCEPTION 'Reviewer user id is required.';
    END IF;

    SELECT loan.id
    INTO locked_loan_id
    FROM lending.loans loan
    WHERE loan.id = p_loan_id
    FOR UPDATE;

    IF locked_loan_id IS NULL THEN
        RAISE EXCEPTION 'Loan was not found.';
    END IF;

    SELECT *
    INTO dpd
    FROM accounting.loan_contract_dpd_assessment assessment
    WHERE assessment.loan_id = p_loan_id;

    IF coalesce(dpd.dpd_data_status, '') <> 'ready'
       OR dpd.schedule_id IS NULL
       OR dpd.schedule_version IS NULL
       OR dpd.days_past_due IS NULL THEN
        RAISE EXCEPTION 'Contract-driven DPD evidence must be ready before ECL credit-risk labels can be reviewed.';
    END IF;

    current_risk_band := CASE
        WHEN dpd.days_past_due >= 90 THEN 'past_due_90_plus'
        WHEN dpd.days_past_due >= 30 THEN 'past_due_30_89'
        WHEN dpd.days_past_due > 0 THEN 'past_due_1_29'
        ELSE 'current'
    END;

    IF normalized_stage = 'stage_1_12_month' AND p_default_label THEN
        RAISE EXCEPTION 'Stage 1 cannot be recorded with a reviewed default label.';
    END IF;

    IF dpd.thirty_day_sicr_backstop_reached
       AND normalized_stage = 'stage_1_12_month'
       AND NOT coalesce(p_sicr_backstop_rebutted, false) THEN
        RAISE EXCEPTION 'Stage 1 at or beyond the 30-DPD SICR backstop requires an explicit rebuttal supported by separate evidence.';
    END IF;
    IF coalesce(p_sicr_backstop_rebutted, false)
       AND NOT dpd.thirty_day_sicr_backstop_reached THEN
        RAISE EXCEPTION 'The 30-DPD SICR backstop cannot be rebutted before it is reached.';
    END IF;

    IF dpd.ninety_day_default_backstop_reached
       AND NOT p_default_label
       AND NOT coalesce(p_default_backstop_rebutted, false) THEN
        RAISE EXCEPTION 'A non-default label at or beyond the 90-DPD default backstop requires an explicit rebuttal supported by separate evidence.';
    END IF;
    IF coalesce(p_default_backstop_rebutted, false)
       AND NOT dpd.ninety_day_default_backstop_reached THEN
        RAISE EXCEPTION 'The 90-DPD default backstop cannot be rebutted before it is reached.';
    END IF;

    IF coalesce(p_sicr_backstop_rebutted, false)
       OR coalesce(p_default_backstop_rebutted, false) THEN
        IF normalized_rebuttal_reference = '' OR normalized_rebuttal_note = '' THEN
            RAISE EXCEPTION 'Backstop rebuttal requires a separate evidence reference and rationale.';
        END IF;
        IF normalized_basis = 'contractual_dpd' THEN
            RAISE EXCEPTION 'Contractual DPD alone cannot be the separate evidence used to rebut a DPD backstop.';
        END IF;
    ELSIF normalized_rebuttal_reference <> '' OR normalized_rebuttal_note <> '' THEN
        RAISE EXCEPTION 'Rebuttal evidence cannot be supplied unless a DPD backstop is explicitly rebutted.';
    END IF;

    IF dpd.days_past_due < 30
       AND normalized_stage IN ('stage_2_lifetime', 'stage_3_credit_impaired')
       AND normalized_basis = 'contractual_dpd' THEN
        RAISE EXCEPTION 'A Stage 2 or Stage 3 label before the 30-DPD backstop requires separately evidenced qualitative or other credit-risk information.';
    END IF;

    IF dpd.days_past_due < 90
       AND p_default_label
       AND normalized_basis = 'contractual_dpd' THEN
        RAISE EXCEPTION 'A default label before the 90-DPD backstop requires separately evidenced default information.';
    END IF;

    IF normalized_write_off = 'supported_no_reasonable_expectation_of_recovery' THEN
        IF normalized_stage <> 'stage_3_credit_impaired' OR NOT p_default_label THEN
            RAISE EXCEPTION 'Write-off support requires a reviewed Stage 3 default state.';
        END IF;
        IF normalized_write_off_reference = '' OR normalized_write_off_note = '' THEN
            RAISE EXCEPTION 'Write-off support requires explicit no-reasonable-expectation-of-recovery evidence and rationale.';
        END IF;
        IF normalized_basis = 'contractual_dpd' THEN
            RAISE EXCEPTION 'Contractual DPD alone cannot support a write-off conclusion.';
        END IF;
    ELSIF normalized_write_off_reference <> '' OR normalized_write_off_note <> '' THEN
        RAISE EXCEPTION 'Write-off evidence cannot be supplied when the write-off-support label is none.';
    END IF;

    SELECT *
    INTO prior_review
    FROM accounting.ecl_credit_risk_label_reviews review
    WHERE review.loan_id = p_loan_id
    ORDER BY review.review_version DESC
    LIMIT 1;

    prior_review_id := prior_review.id;
    next_version := coalesce(prior_review.review_version, 0) + 1;

    IF normalized_recovery = 'cash_recovery_observed' THEN
        IF prior_review_id IS NULL
           OR NOT (
                prior_review.default_label
                OR prior_review.stage_label = 'stage_3_credit_impaired'
                OR prior_review.write_off_label = 'supported_no_reasonable_expectation_of_recovery'
           ) THEN
            RAISE EXCEPTION 'Cash-recovery labeling requires a prior reviewed default, Stage 3, or write-off-support state.';
        END IF;
        IF p_recovery_transaction_id IS NULL THEN
            RAISE EXCEPTION 'Cash-recovery labeling requires the exact protected collection transaction.';
        END IF;

        SELECT *
        INTO recovery_tx
        FROM lending.collection_transactions transaction
        WHERE transaction.id = p_recovery_transaction_id;

        IF recovery_tx.id IS NULL
           OR recovery_tx.loan_id <> p_loan_id
           OR recovery_tx.is_voided
           OR recovery_tx.amount <= 0
           OR recovery_tx.entry_type NOT IN ('payment', 'advance')
           OR recovery_tx.collection_date < prior_review.created_at::date THEN
            RAISE EXCEPTION 'Recovery transaction must be a later non-voided positive protected collection for the same loan.';
        END IF;
    ELSIF p_recovery_transaction_id IS NOT NULL THEN
        RAISE EXCEPTION 'A recovery transaction can be supplied only for cash-recovery-observed labeling.';
    END IF;

    IF normalized_recovery = 'cured' THEN
        IF prior_review_id IS NULL
           OR NOT (
                prior_review.default_label
                OR prior_review.stage_label = 'stage_3_credit_impaired'
                OR prior_review.write_off_label = 'supported_no_reasonable_expectation_of_recovery'
           ) THEN
            RAISE EXCEPTION 'Cure labeling requires a prior reviewed default, Stage 3, or write-off-support state.';
        END IF;
        IF p_default_label OR normalized_stage = 'stage_3_credit_impaired' THEN
            RAISE EXCEPTION 'A cured label requires the current review to be non-default and no longer Stage 3.';
        END IF;
        IF normalized_basis = 'contractual_dpd' THEN
            RAISE EXCEPTION 'Contractual DPD alone cannot prove a cure.';
        END IF;
    END IF;

    INSERT INTO accounting.ecl_credit_risk_label_reviews (
        loan_id,
        review_version,
        stage_label,
        default_label,
        write_off_label,
        recovery_label,
        primary_evidence_basis,
        evidence_reference,
        review_note,
        snapshot_schedule_id,
        snapshot_schedule_version,
        snapshot_days_past_due,
        snapshot_due_unpaid_amount,
        snapshot_thirty_day_backstop,
        snapshot_ninety_day_backstop,
        snapshot_dpd_risk_band,
        sicr_backstop_rebutted,
        default_backstop_rebutted,
        rebuttal_evidence_reference,
        rebuttal_note,
        write_off_evidence_reference,
        write_off_note,
        recovery_transaction_id,
        reviewer_user_id,
        supersedes_review_id
    )
    VALUES (
        p_loan_id,
        next_version,
        normalized_stage,
        p_default_label,
        normalized_write_off,
        normalized_recovery,
        normalized_basis,
        normalized_evidence_reference,
        normalized_review_note,
        dpd.schedule_id,
        dpd.schedule_version,
        dpd.days_past_due,
        dpd.due_unpaid_amount,
        dpd.thirty_day_sicr_backstop_reached,
        dpd.ninety_day_default_backstop_reached,
        current_risk_band,
        coalesce(p_sicr_backstop_rebutted, false),
        coalesce(p_default_backstop_rebutted, false),
        nullif(normalized_rebuttal_reference, ''),
        nullif(normalized_rebuttal_note, ''),
        nullif(normalized_write_off_reference, ''),
        nullif(normalized_write_off_note, ''),
        p_recovery_transaction_id,
        p_actor_user_id,
        prior_review_id
    )
    RETURNING id INTO new_review_id;

    RETURN new_review_id;
END;
$$;

CREATE OR REPLACE VIEW accounting.ecl_credit_risk_label_policy_v1 AS
SELECT
    'ecl_credit_risk_labels_v1'::text AS policy_version,
    true AS explicit_management_review_required,
    'stage_1_12_month'::text AS stage_1_label,
    'stage_2_lifetime'::text AS stage_2_label,
    'stage_3_credit_impaired'::text AS stage_3_label,
    true AS thirty_dpd_sicr_backstop_rebuttable,
    true AS ninety_dpd_default_backstop_rebuttable,
    true AS qualitative_evidence_can_require_earlier_stage_or_default,
    'supported_no_reasonable_expectation_of_recovery'::text AS write_off_support_label,
    true AS write_off_support_is_not_write_off_execution,
    true AS cure_requires_explicit_review,
    true AS cash_recovery_requires_exact_protected_transaction,
    false AS automatic_staging_enabled,
    false AS automatic_default_enabled,
    false AS automatic_write_off_enabled,
    false AS automatic_recovery_enabled,
    false AS quantitative_ecl_ready,
    false AS ecl_calculation_enabled,
    false AS account_1190_posting_enabled,
    false AS automatic_source_posting;

CREATE OR REPLACE VIEW accounting.ecl_credit_risk_label_queue AS
WITH latest_review AS (
    SELECT DISTINCT ON (review.loan_id)
        review.*,
        reviewer.full_name AS reviewer_name
    FROM accounting.ecl_credit_risk_label_reviews review
    LEFT JOIN core.users reviewer ON reviewer.id = review.reviewer_user_id
    ORDER BY review.loan_id, review.review_version DESC
), current_dpd AS (
    SELECT
        assessment.*,
        CASE
            WHEN assessment.dpd_data_status <> 'ready' OR assessment.days_past_due IS NULL
                THEN NULL::text
            WHEN assessment.days_past_due >= 90 THEN 'past_due_90_plus'
            WHEN assessment.days_past_due >= 30 THEN 'past_due_30_89'
            WHEN assessment.days_past_due > 0 THEN 'past_due_1_29'
            ELSE 'current'
        END AS current_dpd_risk_band
    FROM accounting.loan_contract_dpd_assessment assessment
)
SELECT
    dpd.loan_id,
    dpd.loan_number,
    dpd.loan_status,
    dpd.schedule_id,
    dpd.schedule_version,
    dpd.contract_reference,
    dpd.dpd_data_status,
    dpd.days_past_due,
    dpd.due_unpaid_amount,
    dpd.thirty_day_sicr_backstop_reached,
    dpd.ninety_day_default_backstop_reached,
    dpd.current_dpd_risk_band,
    review.id AS review_id,
    review.review_version,
    review.stage_label,
    review.default_label,
    review.write_off_label,
    review.recovery_label,
    review.primary_evidence_basis,
    review.evidence_reference,
    review.review_note,
    review.sicr_backstop_rebutted,
    review.default_backstop_rebutted,
    review.rebuttal_evidence_reference,
    review.rebuttal_note,
    review.write_off_evidence_reference,
    review.write_off_note,
    review.recovery_transaction_id,
    review.reviewer_user_id,
    review.reviewer_name,
    review.created_at AS reviewed_at,
    CASE
        WHEN dpd.dpd_data_status <> 'ready' THEN false
        WHEN review.id IS NULL THEN false
        WHEN review.snapshot_schedule_id <> dpd.schedule_id THEN false
        WHEN review.snapshot_schedule_version <> dpd.schedule_version THEN false
        WHEN review.snapshot_dpd_risk_band <> dpd.current_dpd_risk_band THEN false
        ELSE true
    END AS current_label_ready,
    CASE
        WHEN dpd.dpd_data_status <> 'ready' THEN 'dpd_data_required'
        WHEN review.id IS NULL THEN 'label_review_required'
        WHEN review.snapshot_schedule_id <> dpd.schedule_id
          OR review.snapshot_schedule_version <> dpd.schedule_version
          OR review.snapshot_dpd_risk_band <> dpd.current_dpd_risk_band
            THEN 'label_refresh_required'
        ELSE 'label_reviewed'
    END AS label_review_status,
    false AS quantitative_ecl_ready,
    false AS ecl_calculation_enabled,
    false AS account_1190_posting_enabled,
    false AS automatic_source_posting
FROM current_dpd dpd
LEFT JOIN latest_review review ON review.loan_id = dpd.loan_id;

CREATE OR REPLACE VIEW accounting.ecl_credit_risk_label_summary AS
SELECT
    count(*)::bigint AS loan_count,
    count(*) FILTER (WHERE dpd_data_status = 'ready')::bigint AS dpd_ready_count,
    count(*) FILTER (WHERE label_review_status = 'dpd_data_required')::bigint AS dpd_data_required_count,
    count(*) FILTER (WHERE label_review_status = 'label_review_required')::bigint AS label_review_required_count,
    count(*) FILTER (WHERE label_review_status = 'label_refresh_required')::bigint AS label_refresh_required_count,
    count(*) FILTER (WHERE current_label_ready)::bigint AS current_label_ready_count,
    count(*) FILTER (WHERE current_label_ready AND stage_label = 'stage_1_12_month')::bigint AS stage_1_count,
    count(*) FILTER (WHERE current_label_ready AND stage_label = 'stage_2_lifetime')::bigint AS stage_2_count,
    count(*) FILTER (WHERE current_label_ready AND stage_label = 'stage_3_credit_impaired')::bigint AS stage_3_count,
    count(*) FILTER (WHERE current_label_ready AND default_label)::bigint AS default_count,
    count(*) FILTER (
        WHERE current_label_ready
          AND write_off_label = 'supported_no_reasonable_expectation_of_recovery'
    )::bigint AS write_off_supported_count,
    count(*) FILTER (
        WHERE current_label_ready AND recovery_label = 'cash_recovery_observed'
    )::bigint AS cash_recovery_observed_count,
    count(*) FILTER (
        WHERE current_label_ready AND recovery_label = 'cured'
    )::bigint AS cured_count,
    false AS quantitative_ecl_ready,
    NULL::numeric(18,2) AS ecl_amount,
    false AS ecl_calculation_enabled,
    false AS account_1190_posting_enabled,
    false AS automatic_source_posting
FROM accounting.ecl_credit_risk_label_queue;

COMMENT ON TABLE accounting.ecl_credit_risk_label_reviews IS
    'Immutable Management-reviewed ECL stage/default/write-off-support/recovery/cure evidence. Labels do not calculate ECL or execute a write-off.';
COMMENT ON FUNCTION accounting.review_ecl_credit_risk_labels(UUID, TEXT, BOOLEAN, TEXT, TEXT, TEXT, TEXT, TEXT, BOOLEAN, BOOLEAN, TEXT, TEXT, TEXT, TEXT, UUID, UUID) IS
    'Protected Management function for evidence-backed ECL credit-risk labels. 30/90-DPD backstops remain rebuttable and DPD alone cannot prove rebuttal, early deterioration, write-off support or cure.';
COMMENT ON VIEW accounting.ecl_credit_risk_label_policy_v1 IS
    'V1 ECL label governance. All labels require explicit Management review; automation, quantitative ECL, account 1190 posting and automatic source posting remain disabled.';
COMMENT ON VIEW accounting.ecl_credit_risk_label_queue IS
    'Current-loan ECL label queue. Reviews become stale when the authoritative schedule changes or DPD crosses the current/1-29/30-89/90+ evidence band.';
COMMENT ON VIEW accounting.ecl_credit_risk_label_summary IS
    'Current protected ECL label readiness summary. No ECL amount or journal posting is enabled.';

COMMIT;
