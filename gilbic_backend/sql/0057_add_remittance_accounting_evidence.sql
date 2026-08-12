BEGIN;

INSERT INTO core.permissions (code, description)
VALUES (
    'accounting.remittance_transfer.evidence.manage',
    'Register and void authoritative remittance destination evidence without creating or posting accounting journals'
)
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code = 'accounting.remittance_transfer.evidence.manage'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.remittance_transfer_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    remittance_id UUID NOT NULL
        REFERENCES lending.collection_remittances(id) ON DELETE RESTRICT,
    destination_account_system_key TEXT NOT NULL
        CHECK (destination_account_system_key IN ('cash_office', 'cash_bank_gcash')),
    business_date DATE NOT NULL,
    transferred_at TIMESTAMPTZ NOT NULL,
    external_reference TEXT NOT NULL,
    evidence_note TEXT NOT NULL DEFAULT '',
    remittance_number_snapshot TEXT NOT NULL,
    collector_user_id_snapshot UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    recipient_user_id_snapshot UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    custody_user_id_snapshot UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    custody_transferred_at_snapshot TIMESTAMPTZ NOT NULL,
    collection_date_snapshot DATE NOT NULL,
    total_amount_snapshot NUMERIC(18,2) NOT NULL CHECK (total_amount_snapshot > 0),
    recorded_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_voided BOOLEAN NOT NULL DEFAULT false,
    voided_by_user_id UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    voided_at TIMESTAMPTZ,
    void_reason TEXT,
    CHECK (btrim(external_reference) <> ''),
    CHECK (
        (is_voided = false AND voided_by_user_id IS NULL AND voided_at IS NULL AND void_reason IS NULL)
        OR
        (is_voided = true AND voided_by_user_id IS NOT NULL AND voided_at IS NOT NULL AND btrim(coalesce(void_reason, '')) <> '')
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS accounting_one_active_remittance_transfer_evidence_uidx
    ON accounting.remittance_transfer_evidence (remittance_id)
    WHERE is_voided = false;
CREATE INDEX IF NOT EXISTS accounting_remittance_transfer_evidence_date_idx
    ON accounting.remittance_transfer_evidence (business_date DESC, recorded_at DESC);

CREATE OR REPLACE FUNCTION accounting.guard_remittance_transfer_evidence_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF coalesce(current_setting('accounting.remittance_transfer_evidence_insert_allowed', true), '') = 'on' THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'Remittance transfer evidence must be registered through the protected evidence function.';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Remittance transfer evidence is immutable and cannot be deleted.';
    END IF;

    IF coalesce(current_setting('accounting.remittance_transfer_evidence_void_allowed', true), '') <> 'on' THEN
        RAISE EXCEPTION 'Remittance transfer evidence is immutable; use the protected void function.';
    END IF;

    IF OLD.is_voided = true THEN
        RAISE EXCEPTION 'Voided remittance transfer evidence is permanent.';
    END IF;

    IF NEW.id IS DISTINCT FROM OLD.id
       OR NEW.remittance_id IS DISTINCT FROM OLD.remittance_id
       OR NEW.destination_account_system_key IS DISTINCT FROM OLD.destination_account_system_key
       OR NEW.business_date IS DISTINCT FROM OLD.business_date
       OR NEW.transferred_at IS DISTINCT FROM OLD.transferred_at
       OR NEW.external_reference IS DISTINCT FROM OLD.external_reference
       OR NEW.evidence_note IS DISTINCT FROM OLD.evidence_note
       OR NEW.remittance_number_snapshot IS DISTINCT FROM OLD.remittance_number_snapshot
       OR NEW.collector_user_id_snapshot IS DISTINCT FROM OLD.collector_user_id_snapshot
       OR NEW.recipient_user_id_snapshot IS DISTINCT FROM OLD.recipient_user_id_snapshot
       OR NEW.custody_user_id_snapshot IS DISTINCT FROM OLD.custody_user_id_snapshot
       OR NEW.custody_transferred_at_snapshot IS DISTINCT FROM OLD.custody_transferred_at_snapshot
       OR NEW.collection_date_snapshot IS DISTINCT FROM OLD.collection_date_snapshot
       OR NEW.total_amount_snapshot IS DISTINCT FROM OLD.total_amount_snapshot
       OR NEW.recorded_by_user_id IS DISTINCT FROM OLD.recorded_by_user_id
       OR NEW.recorded_at IS DISTINCT FROM OLD.recorded_at
       OR NEW.is_voided IS DISTINCT FROM true
       OR NEW.voided_by_user_id IS NULL
       OR NEW.voided_at IS NULL
       OR btrim(coalesce(NEW.void_reason, '')) = '' THEN
        RAISE EXCEPTION 'Protected remittance transfer evidence void may change only the immutable void-state fields.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_remittance_transfer_evidence_guard
    ON accounting.remittance_transfer_evidence;
CREATE TRIGGER accounting_remittance_transfer_evidence_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.remittance_transfer_evidence
FOR EACH ROW EXECUTE FUNCTION accounting.guard_remittance_transfer_evidence_write();

CREATE OR REPLACE FUNCTION accounting.record_remittance_transfer_evidence(
    p_remittance_id UUID,
    p_actor_user_id UUID,
    p_destination_account_system_key TEXT,
    p_business_date DATE,
    p_transferred_at TIMESTAMPTZ,
    p_external_reference TEXT,
    p_evidence_note TEXT DEFAULT ''
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    remittance_row RECORD;
    account_row RECORD;
    existing_row accounting.remittance_transfer_evidence%ROWTYPE;
    created_id UUID;
    normalized_account TEXT := btrim(coalesce(p_destination_account_system_key, ''));
    normalized_reference TEXT := btrim(coalesce(p_external_reference, ''));
    normalized_note TEXT := btrim(coalesce(p_evidence_note, ''));
BEGIN
    IF normalized_account NOT IN ('cash_office', 'cash_bank_gcash') THEN
        RAISE EXCEPTION 'Remittance destination must be explicitly evidenced as Cash - Office or Cash - Bank / GCash.';
    END IF;
    IF p_business_date IS NULL OR p_transferred_at IS NULL THEN
        RAISE EXCEPTION 'Remittance destination business date and exact transfer timestamp are required.';
    END IF;
    IF (p_transferred_at AT TIME ZONE 'Asia/Manila')::date <> p_business_date THEN
        RAISE EXCEPTION 'Remittance destination business date must match the Asia/Manila date of the exact transfer timestamp.';
    END IF;
    IF normalized_reference = '' THEN
        RAISE EXCEPTION 'Remittance destination evidence requires an external receipt, deposit, or office-control reference.';
    END IF;

    SELECT r.*
    INTO remittance_row
    FROM lending.collection_remittances r
    WHERE r.id = p_remittance_id
    FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Remittance was not found.';
    END IF;
    IF remittance_row.status <> 'received'
       OR remittance_row.received_at IS NULL
       OR remittance_row.received_by_user_id IS NULL
       OR remittance_row.custody_user_id IS NULL
       OR remittance_row.custody_transferred_at IS NULL THEN
        RAISE EXCEPTION 'Remittance must be received with complete custody-transfer evidence before accounting destination evidence can be registered.';
    END IF;
    IF remittance_row.received_by_user_id IS DISTINCT FROM remittance_row.recipient_user_id
       OR remittance_row.custody_user_id IS DISTINCT FROM remittance_row.recipient_user_id
       OR remittance_row.custody_transferred_at IS DISTINCT FROM remittance_row.received_at THEN
        RAISE EXCEPTION 'Remittance custody state is inconsistent with the protected acceptance evidence.';
    END IF;
    IF round(remittance_row.total_amount, 2) <= 0 THEN
        RAISE EXCEPTION 'Remittance transfer evidence requires a positive remittance amount.';
    END IF;
    IF p_transferred_at < remittance_row.custody_transferred_at THEN
        RAISE EXCEPTION 'Destination transfer evidence cannot precede protected remittance custody acceptance.';
    END IF;

    SELECT account.system_key, account.account_type, account.is_active, account.is_posting
    INTO account_row
    FROM accounting.accounts account
    WHERE account.system_key = normalized_account
    FOR SHARE;

    IF NOT FOUND
       OR account_row.account_type <> 'asset'
       OR account_row.is_active = false
       OR account_row.is_posting = false THEN
        RAISE EXCEPTION 'Remittance destination must be an active approved SPINA cash asset posting account.';
    END IF;

    SELECT *
    INTO existing_row
    FROM accounting.remittance_transfer_evidence evidence
    WHERE evidence.remittance_id = p_remittance_id
      AND evidence.is_voided = false
    FOR UPDATE;

    IF FOUND THEN
        IF existing_row.destination_account_system_key = normalized_account
           AND existing_row.business_date = p_business_date
           AND existing_row.transferred_at = p_transferred_at
           AND existing_row.external_reference = normalized_reference
           AND existing_row.evidence_note = normalized_note
           AND existing_row.remittance_number_snapshot = remittance_row.remittance_number
           AND existing_row.collector_user_id_snapshot = remittance_row.collector_user_id
           AND existing_row.recipient_user_id_snapshot = remittance_row.recipient_user_id
           AND existing_row.custody_user_id_snapshot = remittance_row.custody_user_id
           AND existing_row.custody_transferred_at_snapshot = remittance_row.custody_transferred_at
           AND existing_row.collection_date_snapshot = remittance_row.collection_date
           AND existing_row.total_amount_snapshot = round(remittance_row.total_amount, 2) THEN
            RETURN existing_row.id;
        END IF;
        RAISE EXCEPTION 'This remittance already has different active destination evidence; void it explicitly before registering a correction.';
    END IF;

    PERFORM set_config('accounting.remittance_transfer_evidence_insert_allowed', 'on', true);
    INSERT INTO accounting.remittance_transfer_evidence (
        remittance_id,
        destination_account_system_key,
        business_date,
        transferred_at,
        external_reference,
        evidence_note,
        remittance_number_snapshot,
        collector_user_id_snapshot,
        recipient_user_id_snapshot,
        custody_user_id_snapshot,
        custody_transferred_at_snapshot,
        collection_date_snapshot,
        total_amount_snapshot,
        recorded_by_user_id
    ) VALUES (
        p_remittance_id,
        normalized_account,
        p_business_date,
        p_transferred_at,
        normalized_reference,
        normalized_note,
        remittance_row.remittance_number,
        remittance_row.collector_user_id,
        remittance_row.recipient_user_id,
        remittance_row.custody_user_id,
        remittance_row.custody_transferred_at,
        remittance_row.collection_date,
        round(remittance_row.total_amount, 2),
        p_actor_user_id
    )
    RETURNING id INTO created_id;
    PERFORM set_config('accounting.remittance_transfer_evidence_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs (actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.remittance_transfer_evidence.recorded',
        'remittance_transfer_evidence',
        created_id,
        jsonb_build_object(
            'remittance_id', p_remittance_id::text,
            'destination_account_system_key', normalized_account,
            'amount', round(remittance_row.total_amount, 2),
            'external_reference', normalized_reference,
            'income_recognition', false,
            'automatic_source_posting', false
        )
    );

    RETURN created_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.void_remittance_transfer_evidence(
    p_evidence_id UUID,
    p_actor_user_id UUID,
    p_reason TEXT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    evidence_row accounting.remittance_transfer_evidence%ROWTYPE;
    normalized_reason TEXT := btrim(coalesce(p_reason, ''));
BEGIN
    IF length(normalized_reason) < 3 THEN
        RAISE EXCEPTION 'Enter a clear reason for voiding the remittance transfer evidence.';
    END IF;

    SELECT *
    INTO evidence_row
    FROM accounting.remittance_transfer_evidence evidence
    WHERE evidence.id = p_evidence_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Remittance transfer evidence was not found.';
    END IF;
    IF evidence_row.is_voided THEN
        RAISE EXCEPTION 'Remittance transfer evidence was already voided.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM accounting.journal_entries journal
        WHERE journal.source_event_key = 'remittance_transfer:' || evidence_row.remittance_id::text
    ) THEN
        RAISE EXCEPTION 'Remittance transfer evidence already has accounting journal history; use the future protected accounting reversal path.';
    END IF;

    PERFORM set_config('accounting.remittance_transfer_evidence_void_allowed', 'on', true);
    UPDATE accounting.remittance_transfer_evidence
    SET is_voided = true,
        voided_by_user_id = p_actor_user_id,
        voided_at = now(),
        void_reason = normalized_reason
    WHERE id = p_evidence_id;
    PERFORM set_config('accounting.remittance_transfer_evidence_void_allowed', 'off', true);

    INSERT INTO core.audit_logs (actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.remittance_transfer_evidence.voided',
        'remittance_transfer_evidence',
        p_evidence_id,
        jsonb_build_object(
            'remittance_id', evidence_row.remittance_id::text,
            'reason', normalized_reason,
            'automatic_source_posting', false
        )
    );
END;
$$;

CREATE OR REPLACE VIEW accounting.remittance_transfer_readiness AS
SELECT
    r.id AS remittance_id,
    r.remittance_number,
    r.collector_user_id,
    collector.full_name AS collector_name,
    r.recipient_user_id,
    recipient.full_name AS recipient_name,
    r.custody_user_id,
    custody.full_name AS custody_name,
    r.collection_date,
    r.status AS remittance_status,
    r.total_amount,
    r.received_at,
    r.custody_transferred_at,
    evidence.id AS transfer_evidence_id,
    evidence.destination_account_system_key,
    evidence.business_date,
    evidence.transferred_at,
    evidence.external_reference,
    CASE
        WHEN r.status <> 'received' THEN 'remittance_not_received'
        WHEN r.total_amount <= 0 THEN 'remittance_amount_invalid'
        WHEN r.received_at IS NULL
          OR r.received_by_user_id IS NULL
          OR r.custody_user_id IS NULL
          OR r.custody_transferred_at IS NULL
          OR r.received_by_user_id IS DISTINCT FROM r.recipient_user_id
          OR r.custody_user_id IS DISTINCT FROM r.recipient_user_id
          OR r.custody_transferred_at IS DISTINCT FROM r.received_at
            THEN 'custody_acceptance_incomplete'
        WHEN evidence.id IS NULL THEN 'missing_destination_evidence'
        WHEN evidence.remittance_number_snapshot IS DISTINCT FROM r.remittance_number
          OR evidence.collector_user_id_snapshot IS DISTINCT FROM r.collector_user_id
          OR evidence.recipient_user_id_snapshot IS DISTINCT FROM r.recipient_user_id
          OR evidence.custody_user_id_snapshot IS DISTINCT FROM r.custody_user_id
          OR evidence.custody_transferred_at_snapshot IS DISTINCT FROM r.custody_transferred_at
          OR evidence.collection_date_snapshot IS DISTINCT FROM r.collection_date
          OR evidence.total_amount_snapshot IS DISTINCT FROM round(r.total_amount, 2)
            THEN 'remittance_changed_after_evidence'
        WHEN evidence.transferred_at < r.custody_transferred_at
            THEN 'destination_transfer_precedes_custody'
        WHEN destination.system_key IS NULL
          OR destination.account_type <> 'asset'
          OR destination.is_active = false
          OR destination.is_posting = false
          OR evidence.destination_account_system_key NOT IN ('cash_office', 'cash_bank_gcash')
            THEN 'destination_account_invalid'
        ELSE 'transfer_coordinate_ready'
    END AS readiness_status,
    CASE WHEN evidence.id IS NOT NULL THEN 'remittance_transfer:' || r.id::text ELSE NULL END AS source_event_key,
    CASE
        WHEN evidence.id IS NOT NULL
         AND r.status = 'received'
         AND evidence.destination_account_system_key IN ('cash_office', 'cash_bank_gcash')
        THEN evidence.destination_account_system_key
        ELSE NULL
    END AS debit_account_system_key,
    CASE
        WHEN evidence.id IS NOT NULL
         AND r.status = 'received'
         AND evidence.destination_account_system_key IN ('cash_office', 'cash_bank_gcash')
        THEN 'cash_collector_custody'
        ELSE NULL
    END AS credit_account_system_key,
    CASE WHEN evidence.id IS NOT NULL THEN round(r.total_amount, 2) ELSE NULL END AS debit_amount,
    CASE WHEN evidence.id IS NOT NULL THEN round(r.total_amount, 2) ELSE NULL END AS credit_amount,
    false AS income_recognition,
    false AS journal_lines_enabled,
    false AS automatic_source_posting
FROM lending.collection_remittances r
JOIN core.users collector ON collector.id = r.collector_user_id
JOIN core.users recipient ON recipient.id = r.recipient_user_id
LEFT JOIN core.users custody ON custody.id = r.custody_user_id
LEFT JOIN accounting.remittance_transfer_evidence evidence
  ON evidence.remittance_id = r.id
 AND evidence.is_voided = false
LEFT JOIN accounting.accounts destination
  ON destination.system_key = evidence.destination_account_system_key;

COMMENT ON TABLE accounting.remittance_transfer_evidence IS
    'Immutable Management-reviewed evidence of the exact Office or Bank/GCash destination of a received collector remittance. Recipient acceptance alone never selects the accounting destination.';
COMMENT ON VIEW accounting.remittance_transfer_readiness IS
    'Read-only remittance custody-transfer accounting gate. Ready coordinates are Dr exact evidence-backed destination cash / Cr Cash - Collector Custody for the same amount; this asset-to-asset transfer is never income and does not authorize journal lines or automatic posting.';

COMMIT;
