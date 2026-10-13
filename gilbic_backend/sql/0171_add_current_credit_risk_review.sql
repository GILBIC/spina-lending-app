BEGIN;

-- Bind the explicit risk decision to the actual source shown in a current
-- fiscal-cutoff review. This adds no backdated labels or financial postings.
CREATE TABLE IF NOT EXISTS accounting.current_credit_risk_review_bindings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    book_id UUID NOT NULL REFERENCES accounting.book_identity(id) ON DELETE RESTRICT,
    fiscal_period_id UUID NOT NULL REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    source_digest TEXT NOT NULL CHECK (source_digest ~ '^[0-9a-f]{64}$'),
    source_snapshot JSONB NOT NULL CHECK (jsonb_typeof(source_snapshot)='object'),
    review_request JSONB NOT NULL CHECK (jsonb_typeof(review_request)='object'),
    actor_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    review_id BIGINT NOT NULL UNIQUE REFERENCES accounting.ecl_credit_risk_label_reviews(id) ON DELETE RESTRICT,
    retained_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (book_id,fiscal_period_id,loan_id,source_digest)
);
ALTER TABLE accounting.current_credit_risk_review_bindings ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE accounting.current_credit_risk_review_bindings FROM PUBLIC;
DROP TRIGGER IF EXISTS current_credit_risk_review_binding_immutable ON accounting.current_credit_risk_review_bindings;
CREATE TRIGGER current_credit_risk_review_binding_immutable
BEFORE UPDATE OR DELETE ON accounting.current_credit_risk_review_bindings
FOR EACH ROW EXECUTE FUNCTION accounting.guard_ecl_credit_risk_label_audit();
DROP TRIGGER IF EXISTS current_credit_risk_review_binding_no_truncate ON accounting.current_credit_risk_review_bindings;
CREATE TRIGGER current_credit_risk_review_binding_no_truncate
BEFORE TRUNCATE ON accounting.current_credit_risk_review_bindings
FOR EACH STATEMENT EXECUTE FUNCTION accounting.guard_ecl_credit_risk_label_audit();

CREATE OR REPLACE FUNCTION accounting.current_credit_risk_review_context(
    p_period_id UUID, p_loan_id UUID
)
RETURNS JSONB LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,accounting,lending
SET timezone='Asia/Manila'
AS $$
DECLARE
    book accounting.book_identity%ROWTYPE;
    period accounting.fiscal_periods%ROWTYPE;
    dpd accounting.loan_contract_dpd_assessment%ROWTYPE;
    prior_review accounting.ecl_credit_risk_label_reviews%ROWTYPE;
    inherited JSONB;
    inherited_review JSONB;
    actual_date DATE := (clock_timestamp() AT TIME ZONE 'Asia/Manila')::date;
    blockers JSONB := '[]'::jsonb;
    snapshot JSONB;
    digest_value TEXT;
BEGIN
    SELECT * INTO book FROM accounting.book_identity WHERE singleton;
    SELECT * INTO period FROM accounting.fiscal_periods WHERE id=p_period_id;
    SELECT * INTO dpd FROM accounting.loan_contract_dpd_assessment WHERE loan_id=p_loan_id;
    SELECT * INTO prior_review FROM accounting.ecl_credit_risk_label_reviews
      WHERE loan_id=p_loan_id ORDER BY review_version DESC LIMIT 1;
    inherited := accounting.native_renewal_inherited_credit_review(p_loan_id);
    inherited_review := inherited->'risk_review';
    IF book.id IS NULL THEN blockers := blockers || '"book_identity_required"'::jsonb; END IF;
    IF period.id IS NULL OR period.status <> 'open' THEN
        blockers := blockers || '"open_period_required"'::jsonb;
    END IF;
    IF period.end_date IS DISTINCT FROM actual_date
       OR actual_date IS DISTINCT FROM current_date THEN
        blockers := blockers || '"actual_current_cutoff_required"'::jsonb;
    END IF;
    IF dpd.loan_id IS NULL OR dpd.dpd_data_status IS DISTINCT FROM 'ready' THEN
        blockers := blockers || '"current_contractual_dpd_required"'::jsonb;
    END IF;
    -- Private source facts include row identities, not merely aggregate money.
    -- The API projects an allowlist and never exposes this snapshot.
    snapshot := jsonb_build_object(
        'policy_version','actual_current_credit_risk_review_v1',
        'as_of_date',actual_date,'book',to_jsonb(book),'period',to_jsonb(period),
        'loan',(SELECT to_jsonb(l) FROM lending.loans l WHERE l.id=p_loan_id),
        'dpd',to_jsonb(dpd),'prior_review',CASE WHEN prior_review.id IS NOT NULL THEN to_jsonb(prior_review) ELSE NULL END,
        'inherited_review_source',inherited,
        'schedule',(SELECT to_jsonb(s) FROM lending.loan_contract_schedules s WHERE s.id=dpd.schedule_id),
        'installments',coalesce((SELECT jsonb_agg(to_jsonb(i) ORDER BY i.id)
            FROM lending.loan_contract_installments_operational i WHERE i.schedule_id=dpd.schedule_id),'[]'::jsonb),
        'collections',coalesce((SELECT jsonb_agg(to_jsonb(t) ORDER BY t.id)
            FROM lending.collection_transactions t WHERE t.loan_id=p_loan_id),'[]'::jsonb),
        'allocations',coalesce((SELECT jsonb_agg(to_jsonb(a) ORDER BY a.id)
            FROM lending.loan_installment_payment_allocations a
            JOIN lending.loan_contract_installments i ON i.id=a.installment_id
            WHERE i.schedule_id=dpd.schedule_id),'[]'::jsonb),
        'active_advance',coalesce((SELECT jsonb_agg(to_jsonb(a) ORDER BY a.installment_id)
            FROM lending.loan_installment_active_advance a
            JOIN lending.loan_contract_installments i ON i.id=a.installment_id
            WHERE i.schedule_id=dpd.schedule_id),'[]'::jsonb),
        'extra_principal',coalesce((SELECT jsonb_agg(to_jsonb(a) ORDER BY a.id)
            FROM lending.seven_by_seven_extra_principal_adjustments a WHERE a.loan_id=p_loan_id),'[]'::jsonb),
        'operational_state',(SELECT to_jsonb(s) FROM lending.loan_schedule_operational_state s WHERE s.schedule_id=dpd.schedule_id),
        'schedule_adjustments',coalesce((SELECT jsonb_agg(to_jsonb(a) ORDER BY a.id)
            FROM lending.loan_schedule_adjustments a WHERE a.loan_id=p_loan_id),'[]'::jsonb)
    );
    digest_value := encode(sha256(convert_to(snapshot::text,'UTF8')),'hex');
    RETURN jsonb_build_object(
        'book_id',book.id,'period_id',p_period_id,'loan_id',p_loan_id,
        'ready',jsonb_array_length(blockers)=0,'blockers',blockers,
        'as_of_date',actual_date,
        'source_digest',CASE WHEN jsonb_array_length(blockers)=0 THEN digest_value ELSE NULL END,
        'schedule_id',dpd.schedule_id,'schedule_version',dpd.schedule_version,
        'days_past_due',dpd.days_past_due,'due_unpaid_amount',dpd.due_unpaid_amount,
        'thirty_day_sicr_backstop_reached',dpd.thirty_day_sicr_backstop_reached,
        'ninety_day_default_backstop_reached',dpd.ninety_day_default_backstop_reached,
        'prior_review',CASE WHEN prior_review.id IS NOT NULL THEN jsonb_build_object(
            'id',prior_review.id,'review_version',prior_review.review_version,
            'stage_label',prior_review.stage_label,'default_label',prior_review.default_label,
            'write_off_label',prior_review.write_off_label,'recovery_label',prior_review.recovery_label,
            'reviewed_at',to_char(prior_review.created_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"')
        ) ELSE NULL END,
        'inherited_review',CASE WHEN inherited_review IS NOT NULL THEN jsonb_build_object(
            'id',inherited_review->'id','review_version',inherited_review->'review_version',
            'loan_id',inherited_review->'loan_id','stage_label',inherited_review->'stage_label',
            'default_label',inherited_review->'default_label',
            'write_off_label',inherited_review->'write_off_label',
            'recovery_label',inherited_review->'recovery_label',
            'reviewed_at',to_char((inherited_review->>'created_at')::timestamptz AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"')
        ) ELSE NULL END,
        'snapshot',snapshot
    );
END;
$$;

CREATE OR REPLACE FUNCTION accounting.retain_current_credit_risk_review(
    p_period_id UUID,p_loan_id UUID,p_book_id UUID,p_source_digest TEXT,
    p_review JSONB,p_actor_user_id UUID
)
RETURNS BIGINT LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,accounting,lending,core
SET timezone='Asia/Manila'
SET lock_timeout='5s'
AS $$
DECLARE
    authorized UUID;
    source JSONB;
    prior_binding accounting.current_credit_risk_review_bindings%ROWTYPE;
    retained_id BIGINT;
    retained_at TIMESTAMPTZ;
    key TEXT;
    required_keys TEXT[] := ARRAY[
        'stage_label','default_label','write_off_label','recovery_label',
        'primary_evidence_basis','evidence_reference','review_note',
        'sicr_backstop_rebutted','default_backstop_rebutted'];
    optional_keys TEXT[] := ARRAY[
        'rebuttal_evidence_reference','rebuttal_note','write_off_evidence_reference',
        'write_off_note','recovery_transaction_id'];
BEGIN
    IF current_setting('transaction_isolation') <> 'read committed' THEN
        RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Current risk review requires READ COMMITTED.';
    END IF;
    SELECT actor.id INTO authorized
    FROM core.users actor
    JOIN core.user_roles membership ON membership.user_id=actor.id
    JOIN core.roles role ON role.id=membership.role_id
    JOIN core.role_permissions permission ON permission.role_id=role.id
    WHERE actor.id=p_actor_user_id AND actor.status='active' AND role.code='management'
      AND permission.permission_code='accounting.ecl.credit_risk_label.review'
    FOR SHARE OF actor,membership,role,permission;
    IF authorized IS NULL THEN
        RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='Current Management risk-review permission is required.';
    END IF;
    IF p_book_id IS NULL OR p_period_id IS NULL OR p_loan_id IS NULL
       OR p_source_digest IS NULL OR p_source_digest !~ '^[0-9a-f]{64}$'
       OR p_review IS NULL OR jsonb_typeof(p_review) <> 'object'
       OR NOT p_review ?& required_keys
       OR EXISTS(SELECT 1 FROM jsonb_object_keys(p_review) k WHERE NOT k=ANY(required_keys||optional_keys)) THEN
        RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='Exact source identity and explicit risk fields are required.';
    END IF;
    FOREACH key IN ARRAY ARRAY['default_label','sicr_backstop_rebutted','default_backstop_rebutted'] LOOP
        IF jsonb_typeof(p_review->key) IS DISTINCT FROM 'boolean' THEN
            RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='Risk decisions require strict boolean labels.';
        END IF;
    END LOOP;
    FOREACH key IN ARRAY ARRAY['stage_label','write_off_label','recovery_label','primary_evidence_basis','evidence_reference','review_note'] LOOP
        IF jsonb_typeof(p_review->key) IS DISTINCT FROM 'string' OR btrim(p_review->>key)='' THEN
            RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='Explicit nonempty risk decision text is required.';
        END IF;
    END LOOP;
    FOREACH key IN ARRAY optional_keys LOOP
        IF p_review ? key AND jsonb_typeof(p_review->key) NOT IN ('string','null') THEN
            RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='Optional evidence fields must be text or null.';
        END IF;
    END LOOP;
    IF length(p_review->>'evidence_reference')>300 OR length(p_review->>'review_note')>1200
       OR length(p_review->>'rebuttal_evidence_reference')>300 OR length(p_review->>'rebuttal_note')>1200
       OR length(p_review->>'write_off_evidence_reference')>300 OR length(p_review->>'write_off_note')>1200 THEN
        RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='Risk evidence exceeds its allowed length.';
    END IF;
    -- Freeze every base table used by DPD, operational overlays and recovery
    -- validation; the shared source is re-read after these locks are obtained.
    -- Keep the shared assessment lock order before the label-writer lock.
    -- Its journal lock also serializes callers before a SHARE-to-writer upgrade.
    PERFORM accounting.lock_elapsed_assessment_sources();
    LOCK TABLE accounting.native_renewal_measurement_reviews,
        accounting.native_regular_asset_lineage,accounting.renewal_treatment_decisions,
        accounting.renewal_treatment_decision_voids,treasury.evidence,
        lending.loan_collection_state IN SHARE MODE;
    LOCK TABLE accounting.book_identity,accounting.fiscal_periods,lending.loans,
        lending.loan_contract_schedules,lending.loan_contract_installments,
        lending.collection_transactions,lending.loan_installment_payment_allocations,
        lending.loan_unused_advance_refund_dues,lending.loan_installment_operational_dates,
        lending.loan_installment_operational_amounts,lending.loan_schedule_operational_state,
        lending.loan_schedule_adjustments,lending.loan_schedule_adjustment_items,
        lending.seven_by_seven_extra_principal_adjustments IN SHARE MODE;
    LOCK TABLE accounting.ecl_credit_risk_label_reviews,
        accounting.current_credit_risk_review_bindings IN SHARE ROW EXCLUSIVE MODE;
    source := accounting.current_credit_risk_review_context(p_period_id,p_loan_id);
    IF source->>'book_id' IS DISTINCT FROM p_book_id::text OR source->>'ready' IS DISTINCT FROM 'true' THEN
        RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='A configured book and open actual current cutoff are required.';
    END IF;
    SELECT * INTO prior_binding FROM accounting.current_credit_risk_review_bindings
      WHERE book_id=p_book_id AND fiscal_period_id=p_period_id
        AND loan_id=p_loan_id AND source_digest=p_source_digest;
    IF prior_binding.id IS NOT NULL THEN
        IF prior_binding.actor_user_id=p_actor_user_id AND prior_binding.review_request=p_review
           AND (prior_binding.source_snapshot-'prior_review')=((source->'snapshot')-'prior_review')
           AND source#>>'{prior_review,id}'=prior_binding.review_id::text THEN
            RETURN prior_binding.review_id;
        END IF;
        RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Retained review retry differs or has been superseded; reload.';
    END IF;
    IF source->>'source_digest' IS DISTINCT FROM p_source_digest THEN
        RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Risk source changed after it was reviewed; reload.';
    END IF;
    retained_id := accounting.review_ecl_credit_risk_labels(
        p_loan_id,p_review->>'stage_label',(p_review->>'default_label')::boolean,
        p_review->>'write_off_label',p_review->>'recovery_label',p_review->>'primary_evidence_basis',
        p_review->>'evidence_reference',p_review->>'review_note',
        (p_review->>'sicr_backstop_rebutted')::boolean,(p_review->>'default_backstop_rebutted')::boolean,
        p_review->>'rebuttal_evidence_reference',p_review->>'rebuttal_note',
        p_review->>'write_off_evidence_reference',p_review->>'write_off_note',
        (p_review->>'recovery_transaction_id')::uuid,p_actor_user_id
    );
    SELECT created_at INTO retained_at FROM accounting.ecl_credit_risk_label_reviews WHERE id=retained_id;
    IF (retained_at AT TIME ZONE 'Asia/Manila')::date IS DISTINCT FROM (source->>'as_of_date')::date
       OR (clock_timestamp() AT TIME ZONE 'Asia/Manila')::date IS DISTINCT FROM (source->>'as_of_date')::date THEN
        RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Business date changed during review; reload in a new transaction.';
    END IF;
    INSERT INTO accounting.current_credit_risk_review_bindings(
        book_id,fiscal_period_id,loan_id,source_digest,source_snapshot,review_request,actor_user_id,review_id
    ) VALUES(p_book_id,p_period_id,p_loan_id,p_source_digest,source->'snapshot',p_review,p_actor_user_id,retained_id);
    RETURN retained_id;
END;
$$;

REVOKE ALL ON FUNCTION accounting.current_credit_risk_review_context(UUID,UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION accounting.retain_current_credit_risk_review(UUID,UUID,UUID,TEXT,JSONB,UUID) FROM PUBLIC;
DO $$
DECLARE role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
        IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
            EXECUTE format('REVOKE ALL ON TABLE accounting.current_credit_risk_review_bindings FROM %I',role_name);
            EXECUTE format('REVOKE ALL ON FUNCTION accounting.current_credit_risk_review_context(UUID,UUID) FROM %I',role_name);
            EXECUTE format('REVOKE ALL ON FUNCTION accounting.retain_current_credit_risk_review(UUID,UUID,UUID,TEXT,JSONB,UUID) FROM %I',role_name);
        END IF;
    END LOOP;
END $$;
COMMIT;
