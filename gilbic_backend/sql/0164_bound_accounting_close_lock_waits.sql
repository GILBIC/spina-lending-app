BEGIN;

-- The composed close stack acquires more source/proof locks than the original
-- Treasury guard. Preserve every existing source check and manifest, but yield
-- a close attempt before it can wait behind an active actual-money writer while
-- holding an earlier lock needed by that writer. Bound the entire lifecycle,
-- including actor, period and nested helper locks, rather than only its final
-- Treasury query. A failed protected call rolls back its partial locks, writes
-- and audit effects in the exception subtransaction.
--
-- This does not set a global/session timeout or change source writers. The
-- caller's exact prior lock_timeout is restored on success and every failure.
-- Existing NOWAIT admission remains in force. Historical implementation aliases
-- stay backend-private and retain all accounting policy/source validations.

DO $rename$ BEGIN
    IF to_regprocedure('accounting.set_fiscal_period_status_before_bounded_admission(uuid,text,uuid)') IS NULL THEN
        ALTER FUNCTION accounting.set_fiscal_period_status(UUID,TEXT,UUID) RENAME TO set_fiscal_period_status_before_bounded_admission;
    END IF;
END; $rename$;
CREATE OR REPLACE FUNCTION accounting.set_fiscal_period_status(p_period_id UUID,p_new_status TEXT,p_actor_user_id UUID)
RETURNS TEXT LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE prior_timeout TEXT := current_setting('lock_timeout'); result TEXT;
BEGIN
    PERFORM set_config('lock_timeout','1ms',true);
    BEGIN
        result := accounting.set_fiscal_period_status_before_bounded_admission(p_period_id,p_new_status,p_actor_user_id);
    EXCEPTION WHEN lock_not_available THEN
        PERFORM set_config('lock_timeout',prior_timeout,true);
        RAISE EXCEPTION 'Source activity is in progress; retry period close.' USING ERRCODE='23514';
    WHEN OTHERS THEN
        PERFORM set_config('lock_timeout',prior_timeout,true);
        RAISE;
    END;
    PERFORM set_config('lock_timeout',prior_timeout,true);
    RETURN result;
END;
$$;

DO $rename$ BEGIN
    IF to_regprocedure('accounting.prepare_period_close_before_bounded_admission(uuid,uuid)') IS NULL THEN
        ALTER FUNCTION accounting.prepare_period_close(UUID,UUID) RENAME TO prepare_period_close_before_bounded_admission;
    END IF;
END; $rename$;
CREATE OR REPLACE FUNCTION accounting.prepare_period_close(p_period_id UUID,p_actor_user_id UUID)
RETURNS UUID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE prior_timeout TEXT := current_setting('lock_timeout'); result UUID;
BEGIN
    PERFORM set_config('lock_timeout','1ms',true);
    BEGIN
        result := accounting.prepare_period_close_before_bounded_admission(p_period_id,p_actor_user_id);
    EXCEPTION WHEN lock_not_available THEN
        PERFORM set_config('lock_timeout',prior_timeout,true);
        RAISE EXCEPTION 'Source activity is in progress; retry period close.' USING ERRCODE='23514';
    WHEN OTHERS THEN
        PERFORM set_config('lock_timeout',prior_timeout,true);
        RAISE;
    END;
    PERFORM set_config('lock_timeout',prior_timeout,true);
    RETURN result;
END;
$$;

DO $rename$ BEGIN
    IF to_regprocedure('accounting.post_period_close_before_bounded_admission(uuid,uuid,text,text,numeric,text,date,text)') IS NULL THEN
        ALTER FUNCTION accounting.post_period_close(UUID,UUID,TEXT,TEXT,NUMERIC,TEXT,DATE,TEXT) RENAME TO post_period_close_before_bounded_admission;
    END IF;
END; $rename$;
CREATE OR REPLACE FUNCTION accounting.post_period_close(p_period_id UUID,p_actor_user_id UUID,p_confirmation_token TEXT,p_expected_close_digest TEXT,p_expected_net_income NUMERIC,p_expected_retained_earnings_account_code TEXT,p_expected_close_posting_date DATE,p_policy_version TEXT)
RETURNS UUID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE prior_timeout TEXT := current_setting('lock_timeout'); result UUID;
BEGIN
    PERFORM set_config('lock_timeout','1ms',true);
    BEGIN
        result := accounting.post_period_close_before_bounded_admission(p_period_id,p_actor_user_id,p_confirmation_token,p_expected_close_digest,p_expected_net_income,p_expected_retained_earnings_account_code,p_expected_close_posting_date,p_policy_version);
    EXCEPTION WHEN lock_not_available THEN
        PERFORM set_config('lock_timeout',prior_timeout,true);
        RAISE EXCEPTION 'Source activity is in progress; retry period close.' USING ERRCODE='23514';
    WHEN OTHERS THEN
        PERFORM set_config('lock_timeout',prior_timeout,true);
        RAISE;
    END;
    PERFORM set_config('lock_timeout',prior_timeout,true);
    RETURN result;
END;
$$;

DO $rename$ BEGIN
    IF to_regprocedure('accounting.assert_period_source_complete_before_bounded_admission(uuid)') IS NULL THEN
        ALTER FUNCTION accounting.assert_period_source_complete(UUID) RENAME TO assert_period_source_complete_before_bounded_admission;
    END IF;
END; $rename$;
CREATE OR REPLACE FUNCTION accounting.assert_period_source_complete(p_period_id UUID)
RETURNS VOID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE prior_timeout TEXT := current_setting('lock_timeout');
BEGIN
    PERFORM set_config('lock_timeout','1ms',true);
    BEGIN
        PERFORM accounting.assert_period_source_complete_before_bounded_admission(p_period_id);
    EXCEPTION WHEN lock_not_available THEN
        PERFORM set_config('lock_timeout',prior_timeout,true);
        RAISE EXCEPTION 'Source activity is in progress; retry period close.' USING ERRCODE='23514';
    WHEN OTHERS THEN
        PERFORM set_config('lock_timeout',prior_timeout,true);
        RAISE;
    END;
    PERFORM set_config('lock_timeout',prior_timeout,true);
    RETURN;
END;
$$;

DO $rename$ BEGIN
    IF to_regprocedure('accounting.assert_period_legacy_source_complete_before_bounded_admission(uuid)') IS NULL THEN
        ALTER FUNCTION accounting.assert_period_legacy_source_complete(UUID) RENAME TO assert_period_legacy_source_complete_before_bounded_admission;
    END IF;
END; $rename$;
CREATE OR REPLACE FUNCTION accounting.assert_period_legacy_source_complete(p_period_id UUID)
RETURNS VOID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE prior_timeout TEXT := current_setting('lock_timeout');
BEGIN
    PERFORM set_config('lock_timeout','1ms',true);
    BEGIN
        PERFORM accounting.assert_period_legacy_source_complete_before_bounded_admission(p_period_id);
    EXCEPTION WHEN lock_not_available THEN
        PERFORM set_config('lock_timeout',prior_timeout,true);
        RAISE EXCEPTION 'Source activity is in progress; retry period close.' USING ERRCODE='23514';
    WHEN OTHERS THEN
        PERFORM set_config('lock_timeout',prior_timeout,true);
        RAISE;
    END;
    PERFORM set_config('lock_timeout',prior_timeout,true);
    RETURN;
END;
$$;

DO $rename$ BEGIN
    IF to_regprocedure('accounting.lock_period_review_manifest_sources_before_bounded_admission(uuid)') IS NULL THEN
        ALTER FUNCTION accounting.lock_period_review_manifest_sources(UUID) RENAME TO lock_period_review_manifest_sources_before_bounded_admission;
    END IF;
END; $rename$;
CREATE OR REPLACE FUNCTION accounting.lock_period_review_manifest_sources(p_period UUID)
RETURNS VOID LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE prior_timeout TEXT := current_setting('lock_timeout');
BEGIN
    PERFORM set_config('lock_timeout','1ms',true);
    BEGIN
        PERFORM accounting.lock_period_review_manifest_sources_before_bounded_admission(p_period);
    EXCEPTION WHEN lock_not_available THEN
        PERFORM set_config('lock_timeout',prior_timeout,true);
        RAISE EXCEPTION 'Source activity is in progress; retry period close.' USING ERRCODE='23514';
    WHEN OTHERS THEN
        PERFORM set_config('lock_timeout',prior_timeout,true);
        RAISE;
    END;
    PERFORM set_config('lock_timeout',prior_timeout,true);
    RETURN;
END;
$$;

-- Reassert the current private-view behavior after composed view replacements.
ALTER VIEW accounting.period_source_close_state SET (security_invoker=true);

DO $private$ DECLARE signature REGPROCEDURE; role_name TEXT; BEGIN
    FOR signature IN SELECT p.oid::regprocedure FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
      WHERE n.nspname='accounting' AND p.proname=ANY(ARRAY['set_fiscal_period_status','prepare_period_close','post_period_close','assert_period_source_complete','assert_period_legacy_source_complete','lock_period_review_manifest_sources','set_fiscal_period_status_before_bounded_admission','prepare_period_close_before_bounded_admission','post_period_close_before_bounded_admission','assert_period_source_complete_before_bounded_admission','assert_period_legacy_source_complete_before_bounded_admission','lock_period_review_manifest_sources_before_bounded_admission']) LOOP
        EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC',signature);
        FOREACH role_name IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
            IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
                EXECUTE format('REVOKE ALL ON FUNCTION %s FROM %I',signature,role_name);
            END IF;
        END LOOP;
    END LOOP;
END; $private$;

COMMENT ON FUNCTION accounting.lock_period_review_manifest_sources(UUID) IS
'Composed source locks with bounded admission. A busy writer rejects close with retryable23514; partial close locks and effects roll back and caller timeout is restored. No source or accounting completeness requirement is waived.';

COMMIT;
