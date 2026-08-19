BEGIN;

INSERT INTO core.permissions (code, description)
VALUES
    ('renewal.recommend.assigned', 'Recommend renewal for permanently assigned clients'),
    ('renewal.cash_custody.assigned', 'Confirm renewal cash custody for permanently assigned clients')
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code IN (
      'renewal.recommend.assigned',
      'renewal.cash_custody.assigned'
  )
WHERE role.code = 'collector'
ON CONFLICT DO NOTHING;

ALTER TABLE lending.client_renewal_requests
    ADD COLUMN IF NOT EXISTS collector_recommendation TEXT,
    ADD COLUMN IF NOT EXISTS collector_reason_code TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS collector_comment TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS recommended_by_user_id UUID
        REFERENCES core.users(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS recommended_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS approved_principal NUMERIC(18,2),
    ADD COLUMN IF NOT EXISTS management_override_reason TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS client_decision TEXT,
    ADD COLUMN IF NOT EXISTS client_decided_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS signer_readiness_status TEXT NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS office_processing_required BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS renewal_offset_amount NUMERIC(18,2),
    ADD COLUMN IF NOT EXISTS net_release_amount NUMERIC(18,2),
    ADD COLUMN IF NOT EXISTS amount_locked_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS cash_released_by_user_id UUID
        REFERENCES core.users(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS cash_released_to_collector_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS collector_cash_received_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS cash_given_to_client_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS client_cash_confirmed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS handover_proof_url TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS handover_proof_status TEXT NOT NULL DEFAULT 'not_submitted',
    ADD COLUMN IF NOT EXISTS activation_status TEXT NOT NULL DEFAULT 'not_released',
    ADD COLUMN IF NOT EXISTS new_loan_id UUID
        REFERENCES lending.loans(id) ON DELETE RESTRICT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'client_renewal_collector_recommendation_check'
    ) THEN
        ALTER TABLE lending.client_renewal_requests
            ADD CONSTRAINT client_renewal_collector_recommendation_check
            CHECK (collector_recommendation IS NULL OR collector_recommendation IN ('recommend', 'do_not_recommend'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'client_renewal_client_decision_check'
    ) THEN
        ALTER TABLE lending.client_renewal_requests
            ADD CONSTRAINT client_renewal_client_decision_check
            CHECK (client_decision IS NULL OR client_decision IN ('accepted', 'declined'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'client_renewal_signer_readiness_check'
    ) THEN
        ALTER TABLE lending.client_renewal_requests
            ADD CONSTRAINT client_renewal_signer_readiness_check
            CHECK (signer_readiness_status IN ('pending', 'ready', 'office_required'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'client_renewal_handover_proof_status_check'
    ) THEN
        ALTER TABLE lending.client_renewal_requests
            ADD CONSTRAINT client_renewal_handover_proof_status_check
            CHECK (handover_proof_status IN ('not_submitted', 'under_review', 'approved', 'correction_required', 'flagged'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'client_renewal_activation_status_check'
    ) THEN
        ALTER TABLE lending.client_renewal_requests
            ADD CONSTRAINT client_renewal_activation_status_check
            CHECK (activation_status IN ('not_released', 'released_pending_management', 'active'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS client_renewal_recommendation_queue_idx
    ON lending.client_renewal_requests
       (collector_recommendation, submitted_at DESC)
    WHERE status = 'pending';

COMMIT;
