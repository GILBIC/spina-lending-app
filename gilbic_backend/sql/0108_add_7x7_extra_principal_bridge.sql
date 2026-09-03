BEGIN;

-- Complete the protected 7x7 Extra Principal evidence model without changing
-- any immutable receipt, signed schedule, adjustment, item, or Refund Due row
-- created by migration 0106. Reversals and cash releases are new append-only
-- facts; current state is derived from the full immutable history.

INSERT INTO core.permissions (code, description)
VALUES
    (
        'lending.extra_principal.reverse',
        'Reverse an eligible unremitted 7x7 Extra Principal receipt through the protected Management void workflow'
    ),
    (
        'lending.refund_due.approve',
        'Approve an itemized unused-Advance Refund Due without changing collector cash custody'
    ),
    (
        'lending.refund_due.release',
        'Record an approved physical unused-Advance refund release with immutable custody evidence'
    )
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM (VALUES
    ('management', 'lending.extra_principal.reverse'),
    ('management', 'lending.refund_due.approve'),
    ('management', 'lending.refund_due.release'),
    ('collector', 'lending.refund_due.release')
) AS mapping(role_code, permission_code)
JOIN core.roles role ON role.code = mapping.role_code
JOIN core.permissions permission ON permission.code = mapping.permission_code
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS lending.seven_by_seven_extra_principal_reversal_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key UUID NOT NULL UNIQUE,
    canonical_request_hash TEXT NOT NULL
        CHECK (canonical_request_hash ~ '^[0-9a-f]{64}$'),
    transaction_id UUID NOT NULL
        REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    adjustment_id UUID NOT NULL
        REFERENCES lending.seven_by_seven_extra_principal_adjustments(id)
        ON DELETE RESTRICT,
    requested_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    reason TEXT NOT NULL CHECK (btrim(reason) <> ''),
    outcome TEXT NOT NULL
        CHECK (outcome IN ('completed', 'blocked_refund_released')),
    collection_void_id UUID UNIQUE
        REFERENCES lending.collection_transaction_voids(id) ON DELETE RESTRICT,
    released_refund_amount NUMERIC(18,2) NOT NULL DEFAULT 0
        CHECK (released_refund_amount >= 0),
    result_payload JSONB NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (
            outcome = 'completed'
            AND collection_void_id IS NOT NULL
            AND released_refund_amount = 0
        )
        OR
        (
            outcome = 'blocked_refund_released'
            AND collection_void_id IS NULL
            AND released_refund_amount > 0
        )
    )
);

CREATE INDEX IF NOT EXISTS lending_7x7_extra_principal_reversal_request_adjustment_idx
    ON lending.seven_by_seven_extra_principal_reversal_requests(
        adjustment_id,
        requested_at DESC
    );

CREATE TABLE IF NOT EXISTS lending.seven_by_seven_extra_principal_reversals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reversal_request_id UUID NOT NULL UNIQUE
        REFERENCES lending.seven_by_seven_extra_principal_reversal_requests(id)
        ON DELETE RESTRICT,
    adjustment_id UUID NOT NULL UNIQUE
        REFERENCES lending.seven_by_seven_extra_principal_adjustments(id)
        ON DELETE RESTRICT,
    transaction_id UUID NOT NULL UNIQUE
        REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    collection_void_id UUID NOT NULL UNIQUE
        REFERENCES lending.collection_transaction_voids(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    schedule_id UUID NOT NULL
        REFERENCES lending.loan_contract_schedules(id) ON DELETE RESTRICT,
    expected_operational_version INTEGER NOT NULL
        CHECK (expected_operational_version >= 0),
    resulting_operational_version INTEGER NOT NULL
        CHECK (resulting_operational_version > 0),
    original_operational_principal NUMERIC(18,2) NOT NULL
        CHECK (original_operational_principal >= 0),
    reconstructed_operational_principal NUMERIC(18,2) NOT NULL
        CHECK (reconstructed_operational_principal >= 0),
    restored_active_advance NUMERIC(18,2) NOT NULL DEFAULT 0
        CHECK (restored_active_advance >= 0),
    cancelled_refund_due NUMERIC(18,2) NOT NULL DEFAULT 0
        CHECK (cancelled_refund_due >= 0),
    source_history_digest TEXT NOT NULL
        CHECK (source_history_digest ~ '^[0-9a-f]{64}$'),
    operational_state_digest TEXT NOT NULL
        CHECK (operational_state_digest ~ '^[0-9a-f]{64}$'),
    reversed_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    reason TEXT NOT NULL CHECK (btrim(reason) <> ''),
    reversed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        resulting_operational_version = expected_operational_version + 1
    )
);

CREATE INDEX IF NOT EXISTS lending_7x7_extra_principal_reversal_loan_idx
    ON lending.seven_by_seven_extra_principal_reversals(
        loan_id,
        reversed_at DESC
    );

CREATE TABLE IF NOT EXISTS lending.seven_by_seven_extra_principal_reversal_items (
    reversal_id UUID NOT NULL
        REFERENCES lending.seven_by_seven_extra_principal_reversals(id)
        ON DELETE RESTRICT,
    installment_id BIGINT NOT NULL
        REFERENCES lending.loan_contract_installments(id) ON DELETE RESTRICT,
    installment_number INTEGER NOT NULL CHECK (installment_number > 0),
    signed_amount NUMERIC(18,2) NOT NULL CHECK (signed_amount > 0),
    signed_principal NUMERIC(18,2) NOT NULL CHECK (signed_principal > 0),
    signed_interest NUMERIC(18,2) NOT NULL CHECK (signed_interest >= 0),
    prior_operational_amount NUMERIC(18,2) NOT NULL
        CHECK (prior_operational_amount >= 0),
    prior_operational_principal NUMERIC(18,2) NOT NULL
        CHECK (prior_operational_principal >= 0),
    prior_operational_interest NUMERIC(18,2) NOT NULL
        CHECK (prior_operational_interest >= 0),
    reconstructed_operational_amount NUMERIC(18,2) NOT NULL
        CHECK (reconstructed_operational_amount >= 0),
    reconstructed_operational_principal NUMERIC(18,2) NOT NULL
        CHECK (reconstructed_operational_principal >= 0),
    reconstructed_operational_interest NUMERIC(18,2) NOT NULL
        CHECK (reconstructed_operational_interest >= 0),
    prior_removed BOOLEAN NOT NULL,
    reconstructed_removed BOOLEAN NOT NULL,
    prior_active_advance NUMERIC(18,2) NOT NULL
        CHECK (prior_active_advance >= 0),
    reconstructed_active_advance NUMERIC(18,2) NOT NULL
        CHECK (reconstructed_active_advance >= 0),
    prior_active_refund_due NUMERIC(18,2) NOT NULL
        CHECK (prior_active_refund_due >= 0),
    reconstructed_active_refund_due NUMERIC(18,2) NOT NULL
        CHECK (reconstructed_active_refund_due >= 0),
    last_active_adjustment_id UUID
        REFERENCES lending.seven_by_seven_extra_principal_adjustments(id)
        ON DELETE RESTRICT,
    PRIMARY KEY (reversal_id, installment_id),
    CHECK (signed_amount = signed_principal + signed_interest),
    CHECK (
        prior_operational_amount
        = prior_operational_principal + prior_operational_interest
    ),
    CHECK (
        reconstructed_operational_amount
        = reconstructed_operational_principal
          + reconstructed_operational_interest
    ),
    CHECK (
        (
            prior_removed
            AND prior_operational_amount = 0
            AND prior_operational_principal = 0
            AND prior_operational_interest = 0
        )
        OR
        (
            NOT prior_removed
            AND prior_operational_amount > 0
            AND prior_operational_principal > 0
        )
    ),
    CHECK (
        (
            reconstructed_removed
            AND reconstructed_operational_amount = 0
            AND reconstructed_operational_principal = 0
            AND reconstructed_operational_interest = 0
        )
        OR
        (
            NOT reconstructed_removed
            AND reconstructed_operational_amount > 0
            AND reconstructed_operational_principal > 0
        )
    )
);

CREATE INDEX IF NOT EXISTS lending_7x7_extra_principal_reversal_item_installment_idx
    ON lending.seven_by_seven_extra_principal_reversal_items(
        installment_id,
        reversal_id
    );

CREATE TABLE IF NOT EXISTS lending.loan_unused_advance_refund_due_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key UUID NOT NULL UNIQUE,
    canonical_request_hash TEXT NOT NULL
        CHECK (canonical_request_hash ~ '^[0-9a-f]{64}$'),
    adjustment_id UUID NOT NULL
        REFERENCES lending.seven_by_seven_extra_principal_adjustments(id)
        ON DELETE RESTRICT,
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    approved_amount NUMERIC(18,2) NOT NULL CHECK (approved_amount > 0),
    approved_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    reason TEXT NOT NULL CHECK (btrim(reason) <> ''),
    authority_reference TEXT NOT NULL
        CHECK (btrim(authority_reference) <> ''),
    approved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    result_payload JSONB NOT NULL,
    UNIQUE (id, adjustment_id)
);

CREATE INDEX IF NOT EXISTS lending_refund_due_approval_adjustment_idx
    ON lending.loan_unused_advance_refund_due_approvals(
        adjustment_id,
        approved_at DESC
    );

CREATE TABLE IF NOT EXISTS lending.loan_unused_advance_refund_due_approval_items (
    approval_id UUID NOT NULL,
    adjustment_id UUID NOT NULL,
    installment_id BIGINT NOT NULL,
    amount_approved NUMERIC(18,2) NOT NULL CHECK (amount_approved > 0),
    PRIMARY KEY (approval_id, adjustment_id, installment_id),
    FOREIGN KEY (approval_id, adjustment_id)
        REFERENCES lending.loan_unused_advance_refund_due_approvals(id, adjustment_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (adjustment_id, installment_id)
        REFERENCES lending.loan_unused_advance_refund_dues(
            adjustment_id,
            installment_id
        )
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS lending_refund_due_approval_item_due_idx
    ON lending.loan_unused_advance_refund_due_approval_items(
        adjustment_id,
        installment_id,
        approval_id
    );

CREATE TABLE IF NOT EXISTS lending.loan_unused_advance_refund_due_releases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key UUID NOT NULL UNIQUE,
    canonical_request_hash TEXT NOT NULL
        CHECK (canonical_request_hash ~ '^[0-9a-f]{64}$'),
    approval_id UUID NOT NULL
        REFERENCES lending.loan_unused_advance_refund_due_approvals(id)
        ON DELETE RESTRICT,
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    assigned_collector_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    released_amount NUMERIC(18,2) NOT NULL CHECK (released_amount > 0),
    released_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    released_at TIMESTAMPTZ NOT NULL,
    evidence_reference TEXT NOT NULL
        CHECK (btrim(evidence_reference) <> ''),
    evidence_digest TEXT NOT NULL
        CHECK (evidence_digest ~ '^[0-9a-f]{64}$'),
    result_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (id, approval_id)
);

CREATE INDEX IF NOT EXISTS lending_refund_due_release_approval_idx
    ON lending.loan_unused_advance_refund_due_releases(
        approval_id,
        released_at DESC
    );
CREATE INDEX IF NOT EXISTS lending_refund_due_release_collector_idx
    ON lending.loan_unused_advance_refund_due_releases(
        assigned_collector_user_id,
        released_at DESC
    );

CREATE TABLE IF NOT EXISTS lending.loan_unused_advance_refund_due_release_items (
    release_id UUID NOT NULL,
    approval_id UUID NOT NULL,
    adjustment_id UUID NOT NULL,
    installment_id BIGINT NOT NULL,
    amount_released NUMERIC(18,2) NOT NULL CHECK (amount_released > 0),
    PRIMARY KEY (release_id, adjustment_id, installment_id),
    FOREIGN KEY (release_id, approval_id)
        REFERENCES lending.loan_unused_advance_refund_due_releases(id, approval_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (approval_id, adjustment_id, installment_id)
        REFERENCES lending.loan_unused_advance_refund_due_approval_items(
            approval_id,
            adjustment_id,
            installment_id
        )
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS lending_refund_due_release_item_due_idx
    ON lending.loan_unused_advance_refund_due_release_items(
        adjustment_id,
        installment_id,
        release_id
    );

CREATE TABLE IF NOT EXISTS lending.collection_remittance_refund_due_release_items (
    remittance_id UUID NOT NULL
        REFERENCES lending.collection_remittances(id) ON DELETE RESTRICT,
    release_id UUID NOT NULL,
    approval_id UUID NOT NULL,
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    released_at TIMESTAMPTZ NOT NULL,
    amount_released NUMERIC(18,2) NOT NULL CHECK (amount_released > 0),
    release_snapshot JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (remittance_id, release_id),
    FOREIGN KEY (release_id, approval_id)
        REFERENCES lending.loan_unused_advance_refund_due_releases(id, approval_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS lending_remittance_refund_release_idx
    ON lending.collection_remittance_refund_due_release_items(
        release_id,
        remittance_id
    );

-- A successful reconstruction can legitimately restore an installment to its
-- signed state when no earlier active Extra Principal adjustment remains.
ALTER TABLE lending.loan_installment_operational_amounts
    ALTER COLUMN last_extra_principal_adjustment_id DROP NOT NULL;

CREATE OR REPLACE FUNCTION lending.guard_7x7_bridge_append_only()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    required_session_setting TEXT;
BEGIN
    required_session_setting := TG_ARGV[0];

    IF TG_OP = 'INSERT' THEN
        IF current_setting(required_session_setting, true) IS DISTINCT FROM 'on' THEN
            RAISE EXCEPTION
                'Protected 7x7 bridge evidence may only be inserted by its controlled transaction-local writer.'
                USING ERRCODE = '42501';
        END IF;
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'Protected 7x7 bridge evidence is append-only.'
        USING ERRCODE = '55000';
END;
$$;

DROP TRIGGER IF EXISTS lending_7x7_extra_principal_reversal_request_guard
    ON lending.seven_by_seven_extra_principal_reversal_requests;
CREATE TRIGGER lending_7x7_extra_principal_reversal_request_guard
BEFORE INSERT OR UPDATE OR DELETE
ON lending.seven_by_seven_extra_principal_reversal_requests
FOR EACH ROW EXECUTE FUNCTION lending.guard_7x7_bridge_append_only(
    'spina.extra_principal_reversal_write'
);

DROP TRIGGER IF EXISTS lending_7x7_extra_principal_reversal_guard
    ON lending.seven_by_seven_extra_principal_reversals;
CREATE TRIGGER lending_7x7_extra_principal_reversal_guard
BEFORE INSERT OR UPDATE OR DELETE
ON lending.seven_by_seven_extra_principal_reversals
FOR EACH ROW EXECUTE FUNCTION lending.guard_7x7_bridge_append_only(
    'spina.extra_principal_reversal_write'
);

DROP TRIGGER IF EXISTS lending_7x7_extra_principal_reversal_item_guard
    ON lending.seven_by_seven_extra_principal_reversal_items;
CREATE TRIGGER lending_7x7_extra_principal_reversal_item_guard
BEFORE INSERT OR UPDATE OR DELETE
ON lending.seven_by_seven_extra_principal_reversal_items
FOR EACH ROW EXECUTE FUNCTION lending.guard_7x7_bridge_append_only(
    'spina.extra_principal_reversal_write'
);

DROP TRIGGER IF EXISTS lending_refund_due_approval_guard
    ON lending.loan_unused_advance_refund_due_approvals;
CREATE TRIGGER lending_refund_due_approval_guard
BEFORE INSERT OR UPDATE OR DELETE
ON lending.loan_unused_advance_refund_due_approvals
FOR EACH ROW EXECUTE FUNCTION lending.guard_7x7_bridge_append_only(
    'spina.refund_due_approval_write'
);

DROP TRIGGER IF EXISTS lending_refund_due_approval_item_guard
    ON lending.loan_unused_advance_refund_due_approval_items;
CREATE TRIGGER lending_refund_due_approval_item_guard
BEFORE INSERT OR UPDATE OR DELETE
ON lending.loan_unused_advance_refund_due_approval_items
FOR EACH ROW EXECUTE FUNCTION lending.guard_7x7_bridge_append_only(
    'spina.refund_due_approval_write'
);

DROP TRIGGER IF EXISTS lending_refund_due_release_guard
    ON lending.loan_unused_advance_refund_due_releases;
CREATE TRIGGER lending_refund_due_release_guard
BEFORE INSERT OR UPDATE OR DELETE
ON lending.loan_unused_advance_refund_due_releases
FOR EACH ROW EXECUTE FUNCTION lending.guard_7x7_bridge_append_only(
    'spina.refund_due_release_write'
);

DROP TRIGGER IF EXISTS lending_refund_due_release_item_guard
    ON lending.loan_unused_advance_refund_due_release_items;
CREATE TRIGGER lending_refund_due_release_item_guard
BEFORE INSERT OR UPDATE OR DELETE
ON lending.loan_unused_advance_refund_due_release_items
FOR EACH ROW EXECUTE FUNCTION lending.guard_7x7_bridge_append_only(
    'spina.refund_due_release_write'
);

DROP TRIGGER IF EXISTS lending_remittance_refund_due_release_item_guard
    ON lending.collection_remittance_refund_due_release_items;
CREATE TRIGGER lending_remittance_refund_due_release_item_guard
BEFORE INSERT OR UPDATE OR DELETE
ON lending.collection_remittance_refund_due_release_items
FOR EACH ROW EXECUTE FUNCTION lending.guard_7x7_bridge_append_only(
    'spina.refund_due_remittance_write'
);

CREATE OR REPLACE FUNCTION lending.validate_refund_due_remittance_item()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    release_record record;
    remittance_record record;
    active_allocated NUMERIC(18,2);
BEGIN
    SELECT
        release.approval_id,
        release.client_id,
        release.loan_id,
        release.assigned_collector_user_id,
        release.released_at,
        release.released_amount
    INTO release_record
    FROM lending.loan_unused_advance_refund_due_releases release
    WHERE release.id = NEW.release_id
    FOR UPDATE;

    SELECT remittance.collector_user_id, remittance.status
    INTO remittance_record
    FROM lending.collection_remittances remittance
    WHERE remittance.id = NEW.remittance_id
    FOR KEY SHARE;

    IF NOT FOUND
       OR release_record.approval_id IS NULL
       OR release_record.approval_id <> NEW.approval_id
       OR release_record.client_id <> NEW.client_id
       OR release_record.loan_id <> NEW.loan_id
       OR release_record.released_at <> NEW.released_at
       OR release_record.assigned_collector_user_id
          <> remittance_record.collector_user_id
       OR remittance_record.status <> 'submitted' THEN
        RAISE EXCEPTION
            'Refund Due remittance line must preserve the exact release and Collector custody identity.';
    END IF;

    SELECT coalesce(sum(item.amount_released), 0)::numeric(18,2)
    INTO active_allocated
    FROM lending.collection_remittance_refund_due_release_items item
    JOIN lending.collection_remittances remittance
      ON remittance.id = item.remittance_id
    WHERE item.release_id = NEW.release_id
      AND NOT EXISTS (
          SELECT 1
          FROM lending.collection_remittance_rejections rejection
          WHERE rejection.remittance_id = remittance.id
      );

    IF active_allocated + NEW.amount_released > release_record.released_amount THEN
        RAISE EXCEPTION
            'Refund Due remittance lines cannot exceed the immutable physical release.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_remittance_refund_due_release_item_validate
    ON lending.collection_remittance_refund_due_release_items;
CREATE TRIGGER lending_remittance_refund_due_release_item_validate
BEFORE INSERT
ON lending.collection_remittance_refund_due_release_items
FOR EACH ROW EXECUTE FUNCTION lending.validate_refund_due_remittance_item();

CREATE OR REPLACE FUNCTION lending.replay_seven_by_seven_extra_principal(
    p_schedule_id UUID,
    p_excluded_adjustment_id UUID DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
VOLATILE
AS $$
DECLARE
    installment_ids BIGINT[];
    installment_numbers INTEGER[];
    effective_due_dates DATE[];
    signed_amounts NUMERIC(18,2)[];
    signed_principals NUMERIC(18,2)[];
    signed_interests NUMERIC(18,2)[];
    operational_amounts NUMERIC(18,2)[];
    operational_principals NUMERIC(18,2)[];
    operational_interests NUMERIC(18,2)[];
    removed_rows BOOLEAN[];
    last_adjustment_ids UUID[];
    active_adjustment_ids UUID[] := ARRAY[]::UUID[];
    event_record RECORD;
    prior_collection_date DATE;
    reduction_left NUMERIC(18,2);
    principal_removed NUMERIC(18,2);
    future_principal NUMERIC(18,2) := 0;
    row_index INTEGER;
    event_touched BOOLEAN;
    events_text TEXT := '';
    signed_text TEXT := '';
    operational_text TEXT := '';
    active_ids_text TEXT := '';
    source_payload_text TEXT;
    operational_payload_text TEXT;
    source_digest TEXT;
    operational_digest TEXT;
BEGIN
    SELECT
        array_agg(installment.id ORDER BY installment.effective_due_date,
            installment.installment_number, installment.id),
        array_agg(installment.installment_number ORDER BY
            installment.effective_due_date, installment.installment_number,
            installment.id),
        array_agg(installment.effective_due_date ORDER BY
            installment.effective_due_date, installment.installment_number,
            installment.id),
        array_agg(installment.contractual_amount ORDER BY
            installment.effective_due_date, installment.installment_number,
            installment.id),
        array_agg(installment.principal_component ORDER BY
            installment.effective_due_date, installment.installment_number,
            installment.id),
        array_agg(installment.interest_component ORDER BY
            installment.effective_due_date, installment.installment_number,
            installment.id)
    INTO
        installment_ids,
        installment_numbers,
        effective_due_dates,
        signed_amounts,
        signed_principals,
        signed_interests
    FROM lending.loan_contract_installments_operational installment
    WHERE installment.schedule_id = p_schedule_id;

    IF coalesce(cardinality(installment_ids), 0) = 0 THEN
        RAISE EXCEPTION
            'The immutable signed 7x7 schedule has no installments to replay.';
    END IF;

    operational_amounts := signed_amounts;
    operational_principals := signed_principals;
    operational_interests := signed_interests;
    removed_rows := array_fill(false, ARRAY[cardinality(installment_ids)]);
    last_adjustment_ids := array_fill(
        NULL::UUID,
        ARRAY[cardinality(installment_ids)]
    );

    FOR event_record IN
        SELECT
            adjustment.id,
            adjustment.transaction_id,
            adjustment.principal_reduction,
            adjustment.resulting_operational_version,
            transaction.collection_date,
            transaction.is_voided
        FROM lending.seven_by_seven_extra_principal_adjustments adjustment
        JOIN lending.collection_transactions transaction
          ON transaction.id = adjustment.transaction_id
        LEFT JOIN lending.seven_by_seven_extra_principal_reversals reversal
          ON reversal.adjustment_id = adjustment.id
        WHERE adjustment.schedule_id = p_schedule_id
          AND reversal.id IS NULL
          AND (
              p_excluded_adjustment_id IS NULL
              OR adjustment.id <> p_excluded_adjustment_id
          )
        ORDER BY adjustment.resulting_operational_version, adjustment.id
    LOOP
        IF event_record.is_voided THEN
            RAISE EXCEPTION
                'Active Extra Principal history contains a voided source without reversal evidence.';
        END IF;
        IF event_record.principal_reduction <= 0 THEN
            RAISE EXCEPTION
                'Active Extra Principal history contains an invalid reduction.';
        END IF;
        IF prior_collection_date IS NOT NULL
           AND event_record.collection_date < prior_collection_date THEN
            RAISE EXCEPTION
                'Active Extra Principal history contains non-chronological receipt dates.';
        END IF;
        prior_collection_date := event_record.collection_date;
        active_adjustment_ids := array_append(
            active_adjustment_ids,
            event_record.id
        );
        IF events_text <> '' THEN
            events_text := events_text || ',';
            active_ids_text := active_ids_text || ',';
        END IF;
        events_text := events_text || format(
            '{"adjustment_id":"%s","collection_date":"%s",'
            || '"principal_reduction":"%s",'
            || '"resulting_operational_version":%s,'
            || '"transaction_id":"%s"}',
            event_record.id,
            event_record.collection_date,
            to_char(
                event_record.principal_reduction,
                'FM999999999999990.00'
            ),
            event_record.resulting_operational_version,
            event_record.transaction_id
        );
        active_ids_text := active_ids_text || format('"%s"', event_record.id);

        reduction_left := event_record.principal_reduction;
        event_touched := false;
        FOR row_index IN REVERSE
            array_upper(installment_ids, 1)..array_lower(installment_ids, 1)
        LOOP
            IF NOT removed_rows[row_index]
               AND effective_due_dates[row_index]
                   > event_record.collection_date THEN
                event_touched := true;
                principal_removed := least(
                    operational_principals[row_index],
                    reduction_left
                );
                operational_principals[row_index] :=
                    operational_principals[row_index] - principal_removed;
                reduction_left := reduction_left - principal_removed;
                last_adjustment_ids[row_index] := event_record.id;
                IF operational_principals[row_index] = 0 THEN
                    operational_amounts[row_index] := 0;
                    operational_interests[row_index] := 0;
                    removed_rows[row_index] := true;
                ELSE
                    operational_interests[row_index] :=
                        signed_interests[row_index];
                    operational_amounts[row_index] :=
                        operational_principals[row_index]
                        + operational_interests[row_index];
                END IF;
            END IF;
        END LOOP;
        IF NOT event_touched THEN
            RAISE EXCEPTION
                'An active Extra Principal event has no eligible future signed tail.';
        END IF;
        IF reduction_left <> 0 THEN
            RAISE EXCEPTION
                'Active Extra Principal history exceeds the eligible future principal.';
        END IF;
    END LOOP;

    FOR row_index IN array_lower(installment_ids, 1)..array_upper(installment_ids, 1)
    LOOP
        IF signed_text <> '' THEN
            signed_text := signed_text || ',';
            operational_text := operational_text || ',';
        END IF;
        signed_text := signed_text || format(
            '{"effective_due_date":"%s","installment_id":%s,'
            || '"installment_number":%s,"signed_amount":"%s",'
            || '"signed_interest":"%s","signed_principal":"%s"}',
            effective_due_dates[row_index],
            installment_ids[row_index],
            installment_numbers[row_index],
            to_char(signed_amounts[row_index], 'FM999999999999990.00'),
            to_char(signed_interests[row_index], 'FM999999999999990.00'),
            to_char(signed_principals[row_index], 'FM999999999999990.00')
        );
        operational_text := operational_text || format(
            '{"effective_due_date":"%s","installment_id":%s,'
            || '"installment_number":%s,"last_active_adjustment_id":%s,'
            || '"operational_amount":"%s","operational_interest":"%s",'
            || '"operational_principal":"%s","removed":%s,'
            || '"signed_amount":"%s","signed_interest":"%s",'
            || '"signed_principal":"%s"}',
            effective_due_dates[row_index],
            installment_ids[row_index],
            installment_numbers[row_index],
            CASE
                WHEN last_adjustment_ids[row_index] IS NULL THEN 'null'
                ELSE format('"%s"', last_adjustment_ids[row_index])
            END,
            to_char(operational_amounts[row_index], 'FM999999999999990.00'),
            to_char(operational_interests[row_index], 'FM999999999999990.00'),
            to_char(operational_principals[row_index], 'FM999999999999990.00'),
            CASE WHEN removed_rows[row_index] THEN 'true' ELSE 'false' END,
            to_char(signed_amounts[row_index], 'FM999999999999990.00'),
            to_char(signed_interests[row_index], 'FM999999999999990.00'),
            to_char(signed_principals[row_index], 'FM999999999999990.00')
        );
        future_principal :=
            future_principal + operational_principals[row_index];
    END LOOP;

    source_payload_text := format(
        '{"events":[%s],"signed_installments":[%s]}',
        events_text,
        signed_text
    );
    operational_payload_text := format(
        '{"active_adjustment_ids":[%s],"installments":[%s]}',
        active_ids_text,
        operational_text
    );
    source_digest := encode(
        sha256(convert_to(source_payload_text, 'UTF8')),
        'hex'
    );
    operational_digest := encode(
        sha256(convert_to(operational_payload_text, 'UTF8')),
        'hex'
    );

    RETURN jsonb_build_object(
        'source_history_digest', source_digest,
        'operational_state_digest', operational_digest,
        'future_principal', to_char(
            future_principal,
            'FM999999999999990.00'
        ),
        'source_payload', source_payload_text::JSONB,
        'operational_payload', operational_payload_text::JSONB
    );
END;
$$;

-- Forward writes must still match one immutable adjustment item. A reversal
-- temporarily enables a narrower transaction-local path and is followed by an
-- independent full-history guard before the source transaction can be voided.
CREATE OR REPLACE FUNCTION lending.validate_loan_installment_operational_amount()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    item_record record;
BEGIN
    IF current_setting(
        'spina.extra_principal_reconstruction_write',
        true
    ) = 'on' THEN
        RETURN NEW;
    END IF;

    SELECT
        item.new_operational_amount,
        item.new_operational_principal_component,
        item.new_operational_interest_component,
        item.removed_from_operational_schedule
    INTO item_record
    FROM lending.seven_by_seven_extra_principal_adjustment_items item
    WHERE item.adjustment_id = NEW.last_extra_principal_adjustment_id
      AND item.installment_id = NEW.installment_id;

    IF NOT FOUND
       OR item_record.new_operational_amount <> NEW.operational_amount
       OR item_record.new_operational_principal_component
          <> NEW.operational_principal_component
       OR item_record.new_operational_interest_component
          <> NEW.operational_interest_component
       OR item_record.removed_from_operational_schedule
          <> NEW.removed_from_operational_schedule THEN
        RAISE EXCEPTION
            'Operational installment amount must match its immutable 7x7 Extra Principal adjustment item.';
    END IF;

    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION lending.reverse_seven_by_seven_extra_principal_for_void(
    p_transaction_id UUID,
    p_collection_void_id UUID,
    p_actor_user_id UUID,
    p_reason TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    target lending.seven_by_seven_extra_principal_adjustments%ROWTYPE;
    request_record lending.seven_by_seven_extra_principal_reversal_requests%ROWTYPE;
    existing_reversal lending.seven_by_seven_extra_principal_reversals%ROWTYPE;
    operational_state lending.loan_schedule_operational_state%ROWTYPE;
    void_record lending.collection_transaction_voids%ROWTYPE;
    current_replay JSONB;
    reconstructed_replay JSONB;
    final_replay JSONB;
    reversal_id UUID := gen_random_uuid();
    current_row_count INTEGER;
    expected_row_count INTEGER;
    mismatch_count INTEGER;
    released_refund_amount NUMERIC(18,2);
    prior_active_advance NUMERIC(18,2);
    reconstructed_active_advance NUMERIC(18,2);
    cancelled_refund_due NUMERIC(18,2);
BEGIN
    SELECT * INTO target
    FROM lending.seven_by_seven_extra_principal_adjustments adjustment
    WHERE adjustment.transaction_id = p_transaction_id;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended(
        'refund-due-adjustment:' || target.id::TEXT,
        0
    ));

    SELECT * INTO void_record
    FROM lending.collection_transaction_voids void_evidence
    WHERE void_evidence.id = p_collection_void_id
      AND void_evidence.transaction_id = p_transaction_id
    FOR KEY SHARE;
    IF NOT FOUND
       OR void_record.voided_by_user_id <> p_actor_user_id
       OR void_record.reason <> p_reason THEN
        RAISE EXCEPTION
            'Extra Principal reversal requires exact immutable collection-void evidence.';
    END IF;

    SELECT * INTO request_record
    FROM lending.seven_by_seven_extra_principal_reversal_requests request
    WHERE request.transaction_id = p_transaction_id
      AND request.adjustment_id = target.id
      AND request.collection_void_id = p_collection_void_id
      AND request.outcome = 'completed'
    FOR UPDATE;
    IF NOT FOUND
       OR request_record.requested_by_user_id <> p_actor_user_id
       OR request_record.reason <> p_reason THEN
        RAISE EXCEPTION
            'Extra Principal reversal requires an exact completed idempotent request.';
    END IF;

    SELECT * INTO existing_reversal
    FROM lending.seven_by_seven_extra_principal_reversals reversal
    WHERE reversal.adjustment_id = target.id
    FOR KEY SHARE;
    IF FOUND THEN
        IF existing_reversal.transaction_id <> p_transaction_id
           OR existing_reversal.collection_void_id <> p_collection_void_id
           OR existing_reversal.reversal_request_id <> request_record.id
           OR existing_reversal.reversed_by_user_id <> p_actor_user_id
           OR existing_reversal.reason <> p_reason THEN
            RAISE EXCEPTION
                'Stored Extra Principal reversal evidence conflicts with this void.';
        END IF;
        RETURN existing_reversal.id;
    END IF;

    PERFORM release.id
    FROM lending.loan_unused_advance_refund_due_releases release
    JOIN lending.loan_unused_advance_refund_due_approvals approval
      ON approval.id = release.approval_id
    WHERE approval.adjustment_id = target.id
    ORDER BY release.id
    FOR UPDATE OF release;
    SELECT coalesce(sum(release.released_amount), 0)::numeric(18,2)
    INTO released_refund_amount
    FROM lending.loan_unused_advance_refund_due_releases release
    JOIN lending.loan_unused_advance_refund_due_approvals approval
      ON approval.id = release.approval_id
    WHERE approval.adjustment_id = target.id;
    IF released_refund_amount > 0 THEN
        RAISE EXCEPTION
            'Physical Refund Due cash was already released; automatic Extra Principal reversal is blocked.';
    END IF;

    SELECT * INTO operational_state
    FROM lending.loan_schedule_operational_state state
    WHERE state.schedule_id = target.schedule_id
    FOR UPDATE;
    IF NOT FOUND
       OR operational_state.operational_version
          <> target.resulting_operational_version THEN
        RAISE EXCEPTION
            'Extra Principal reversal operational schedule version is stale.';
    END IF;

    PERFORM installment.id
    FROM lending.loan_contract_installments installment
    WHERE installment.schedule_id = target.schedule_id
    ORDER BY installment.id
    FOR UPDATE;
    PERFORM operational.installment_id
    FROM lending.loan_installment_operational_amounts operational
    JOIN lending.loan_contract_installments installment
      ON installment.id = operational.installment_id
    WHERE installment.schedule_id = target.schedule_id
    ORDER BY operational.installment_id
    FOR UPDATE OF operational;
    PERFORM adjustment.id
    FROM lending.seven_by_seven_extra_principal_adjustments adjustment
    WHERE adjustment.schedule_id = target.schedule_id
    ORDER BY adjustment.resulting_operational_version, adjustment.id
    FOR UPDATE;

    current_replay := lending.replay_seven_by_seven_extra_principal(
        target.schedule_id,
        NULL
    );
    expected_row_count := jsonb_array_length(
        current_replay -> 'operational_payload' -> 'installments'
    );
    SELECT count(*)::INTEGER INTO current_row_count
    FROM lending.loan_contract_installments_operational installment
    WHERE installment.schedule_id = target.schedule_id;
    SELECT count(*)::INTEGER INTO mismatch_count
    FROM jsonb_array_elements(
        current_replay -> 'operational_payload' -> 'installments'
    ) expected
    JOIN lending.loan_contract_installments_operational actual
      ON actual.id = (expected ->> 'installment_id')::BIGINT
    WHERE actual.schedule_id = target.schedule_id
      AND (
          actual.effective_due_date
              <> (expected ->> 'effective_due_date')::DATE
          OR actual.operational_amount
              <> (expected ->> 'operational_amount')::NUMERIC
          OR actual.operational_principal_component
              <> (expected ->> 'operational_principal')::NUMERIC
          OR actual.operational_interest_component
              <> (expected ->> 'operational_interest')::NUMERIC
          OR actual.removed_from_operational_schedule
              <> (expected ->> 'removed')::BOOLEAN
          OR actual.last_extra_principal_adjustment_id IS DISTINCT FROM
              (expected ->> 'last_active_adjustment_id')::UUID
      );
    IF current_row_count <> expected_row_count OR mismatch_count <> 0 THEN
        RAISE EXCEPTION
            'Persisted 7x7 operational state does not match immutable active Extra Principal history.';
    END IF;

    reconstructed_replay := lending.replay_seven_by_seven_extra_principal(
        target.schedule_id,
        target.id
    );

    WITH schedule_rows AS (
        SELECT installment.id AS installment_id
        FROM lending.loan_contract_installments installment
        WHERE installment.schedule_id = target.schedule_id
    ), gross AS (
        SELECT
            schedule_row.installment_id,
            coalesce(sum(allocation.amount_applied) FILTER (
                WHERE transaction.is_voided = false
                  AND allocation.allocation_basis
                      = 'future_advance_oldest_first'
            ), 0)::numeric(18,2) AS gross_advance
        FROM schedule_rows schedule_row
        LEFT JOIN lending.loan_installment_payment_allocations allocation
          ON allocation.installment_id = schedule_row.installment_id
        LEFT JOIN lending.collection_transactions transaction
          ON transaction.id = allocation.transaction_id
        GROUP BY schedule_row.installment_id
    ), prior_refund AS (
        SELECT
            schedule_row.installment_id,
            coalesce(sum(refund.amount_due) FILTER (
                WHERE reversal.id IS NULL
            ), 0)::numeric(18,2) AS amount_due
        FROM schedule_rows schedule_row
        LEFT JOIN lending.loan_unused_advance_refund_dues refund
          ON refund.installment_id = schedule_row.installment_id
        LEFT JOIN lending.seven_by_seven_extra_principal_adjustments adjustment
          ON adjustment.id = refund.adjustment_id
         AND adjustment.schedule_id = target.schedule_id
        LEFT JOIN lending.seven_by_seven_extra_principal_reversals reversal
          ON reversal.adjustment_id = adjustment.id
        GROUP BY schedule_row.installment_id
    ), reconstructed_refund AS (
        SELECT
            schedule_row.installment_id,
            coalesce(sum(refund.amount_due) FILTER (
                WHERE reversal.id IS NULL
                  AND adjustment.id <> target.id
            ), 0)::numeric(18,2) AS amount_due
        FROM schedule_rows schedule_row
        LEFT JOIN lending.loan_unused_advance_refund_dues refund
          ON refund.installment_id = schedule_row.installment_id
        LEFT JOIN lending.seven_by_seven_extra_principal_adjustments adjustment
          ON adjustment.id = refund.adjustment_id
         AND adjustment.schedule_id = target.schedule_id
        LEFT JOIN lending.seven_by_seven_extra_principal_reversals reversal
          ON reversal.adjustment_id = adjustment.id
        GROUP BY schedule_row.installment_id
    )
    SELECT
        coalesce(sum(greatest(gross.gross_advance - prior_refund.amount_due, 0)), 0),
        coalesce(sum(greatest(
            gross.gross_advance - reconstructed_refund.amount_due,
            0
        )), 0),
        coalesce((
            SELECT sum(refund.amount_due)
            FROM lending.loan_unused_advance_refund_dues refund
            WHERE refund.adjustment_id = target.id
        ), 0)
    INTO
        prior_active_advance,
        reconstructed_active_advance,
        cancelled_refund_due
    FROM gross
    JOIN prior_refund USING (installment_id)
    JOIN reconstructed_refund USING (installment_id);

    PERFORM set_config('spina.extra_principal_reversal_write', 'on', true);
    INSERT INTO lending.seven_by_seven_extra_principal_reversals (
        id,
        reversal_request_id,
        adjustment_id,
        transaction_id,
        collection_void_id,
        loan_id,
        schedule_id,
        expected_operational_version,
        resulting_operational_version,
        original_operational_principal,
        reconstructed_operational_principal,
        restored_active_advance,
        cancelled_refund_due,
        source_history_digest,
        operational_state_digest,
        reversed_by_user_id,
        reason,
        reversed_at
    ) VALUES (
        reversal_id,
        request_record.id,
        target.id,
        p_transaction_id,
        p_collection_void_id,
        target.loan_id,
        target.schedule_id,
        operational_state.operational_version,
        operational_state.operational_version + 1,
        (current_replay ->> 'future_principal')::NUMERIC,
        (reconstructed_replay ->> 'future_principal')::NUMERIC,
        reconstructed_active_advance - prior_active_advance,
        cancelled_refund_due,
        reconstructed_replay ->> 'source_history_digest',
        reconstructed_replay ->> 'operational_state_digest',
        p_actor_user_id,
        p_reason,
        void_record.voided_at
    );

    WITH prior_rows AS (
        SELECT value AS row
        FROM jsonb_array_elements(
            current_replay -> 'operational_payload' -> 'installments'
        ) value
    ), reconstructed_rows AS (
        SELECT value AS row
        FROM jsonb_array_elements(
            reconstructed_replay -> 'operational_payload' -> 'installments'
        ) value
    ), gross AS (
        SELECT
            installment.id AS installment_id,
            coalesce(sum(allocation.amount_applied) FILTER (
                WHERE transaction.is_voided = false
                  AND allocation.allocation_basis
                      = 'future_advance_oldest_first'
            ), 0)::numeric(18,2) AS gross_advance
        FROM lending.loan_contract_installments installment
        LEFT JOIN lending.loan_installment_payment_allocations allocation
          ON allocation.installment_id = installment.id
        LEFT JOIN lending.collection_transactions transaction
          ON transaction.id = allocation.transaction_id
        WHERE installment.schedule_id = target.schedule_id
        GROUP BY installment.id
    ), prior_refund AS (
        SELECT
            installment.id AS installment_id,
            coalesce(sum(refund.amount_due) FILTER (
                WHERE reversal.id IS NULL OR adjustment.id = target.id
            ), 0)::numeric(18,2) AS amount_due
        FROM lending.loan_contract_installments installment
        LEFT JOIN lending.loan_unused_advance_refund_dues refund
          ON refund.installment_id = installment.id
        LEFT JOIN lending.seven_by_seven_extra_principal_adjustments adjustment
          ON adjustment.id = refund.adjustment_id
         AND adjustment.schedule_id = target.schedule_id
        LEFT JOIN lending.seven_by_seven_extra_principal_reversals reversal
          ON reversal.adjustment_id = adjustment.id
        WHERE installment.schedule_id = target.schedule_id
        GROUP BY installment.id
    ), reconstructed_refund AS (
        SELECT
            installment.id AS installment_id,
            coalesce(sum(refund.amount_due) FILTER (
                WHERE reversal.id IS NULL
                  AND adjustment.id <> target.id
            ), 0)::numeric(18,2) AS amount_due
        FROM lending.loan_contract_installments installment
        LEFT JOIN lending.loan_unused_advance_refund_dues refund
          ON refund.installment_id = installment.id
        LEFT JOIN lending.seven_by_seven_extra_principal_adjustments adjustment
          ON adjustment.id = refund.adjustment_id
         AND adjustment.schedule_id = target.schedule_id
        LEFT JOIN lending.seven_by_seven_extra_principal_reversals reversal
          ON reversal.adjustment_id = adjustment.id
        WHERE installment.schedule_id = target.schedule_id
        GROUP BY installment.id
    )
    INSERT INTO lending.seven_by_seven_extra_principal_reversal_items (
        reversal_id,
        installment_id,
        installment_number,
        signed_amount,
        signed_principal,
        signed_interest,
        prior_operational_amount,
        prior_operational_principal,
        prior_operational_interest,
        reconstructed_operational_amount,
        reconstructed_operational_principal,
        reconstructed_operational_interest,
        prior_removed,
        reconstructed_removed,
        prior_active_advance,
        reconstructed_active_advance,
        prior_active_refund_due,
        reconstructed_active_refund_due,
        last_active_adjustment_id
    )
    SELECT
        reversal_id,
        (reconstructed.row ->> 'installment_id')::BIGINT,
        (reconstructed.row ->> 'installment_number')::INTEGER,
        (reconstructed.row ->> 'signed_amount')::NUMERIC,
        (reconstructed.row ->> 'signed_principal')::NUMERIC,
        (reconstructed.row ->> 'signed_interest')::NUMERIC,
        (prior.row ->> 'operational_amount')::NUMERIC,
        (prior.row ->> 'operational_principal')::NUMERIC,
        (prior.row ->> 'operational_interest')::NUMERIC,
        (reconstructed.row ->> 'operational_amount')::NUMERIC,
        (reconstructed.row ->> 'operational_principal')::NUMERIC,
        (reconstructed.row ->> 'operational_interest')::NUMERIC,
        (prior.row ->> 'removed')::BOOLEAN,
        (reconstructed.row ->> 'removed')::BOOLEAN,
        greatest(gross.gross_advance - prior_refund.amount_due, 0),
        greatest(gross.gross_advance - reconstructed_refund.amount_due, 0),
        prior_refund.amount_due,
        reconstructed_refund.amount_due,
        (reconstructed.row ->> 'last_active_adjustment_id')::UUID
    FROM reconstructed_rows reconstructed
    JOIN prior_rows prior
      ON (prior.row ->> 'installment_id')::BIGINT
         = (reconstructed.row ->> 'installment_id')::BIGINT
    JOIN gross
      ON gross.installment_id
         = (reconstructed.row ->> 'installment_id')::BIGINT
    JOIN prior_refund USING (installment_id)
    JOIN reconstructed_refund USING (installment_id);

    PERFORM set_config(
        'spina.extra_principal_reconstruction_write',
        'on',
        true
    );
    INSERT INTO lending.loan_installment_operational_amounts (
        installment_id,
        operational_amount,
        operational_principal_component,
        operational_interest_component,
        removed_from_operational_schedule,
        last_extra_principal_adjustment_id,
        updated_by_user_id,
        updated_at
    )
    SELECT
        (row ->> 'installment_id')::BIGINT,
        (row ->> 'operational_amount')::NUMERIC,
        (row ->> 'operational_principal')::NUMERIC,
        (row ->> 'operational_interest')::NUMERIC,
        (row ->> 'removed')::BOOLEAN,
        (row ->> 'last_active_adjustment_id')::UUID,
        p_actor_user_id,
        void_record.voided_at
    FROM jsonb_array_elements(
        reconstructed_replay -> 'operational_payload' -> 'installments'
    ) row
    ON CONFLICT (installment_id) DO UPDATE
    SET operational_amount = excluded.operational_amount,
        operational_principal_component =
            excluded.operational_principal_component,
        operational_interest_component =
            excluded.operational_interest_component,
        removed_from_operational_schedule =
            excluded.removed_from_operational_schedule,
        last_extra_principal_adjustment_id =
            excluded.last_extra_principal_adjustment_id,
        updated_by_user_id = excluded.updated_by_user_id,
        updated_at = excluded.updated_at;
    PERFORM set_config(
        'spina.extra_principal_reconstruction_write',
        'off',
        true
    );

    UPDATE lending.loan_schedule_operational_state state
    SET operational_version = operational_state.operational_version + 1,
        updated_by_user_id = p_actor_user_id,
        updated_at = void_record.voided_at
    WHERE state.schedule_id = target.schedule_id
      AND state.operational_version = operational_state.operational_version;
    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Extra Principal reversal lost the operational version lock.';
    END IF;

    final_replay := lending.replay_seven_by_seven_extra_principal(
        target.schedule_id,
        NULL
    );
    IF final_replay ->> 'source_history_digest'
           <> reconstructed_replay ->> 'source_history_digest'
       OR final_replay ->> 'operational_state_digest'
           <> reconstructed_replay ->> 'operational_state_digest' THEN
        RAISE EXCEPTION
            'Extra Principal reversal replay digest changed during reconstruction.';
    END IF;

    RETURN reversal_id;
END;
$$;

CREATE OR REPLACE FUNCTION lending.perform_seven_by_seven_extra_principal_void_reversal()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    void_id UUID;
BEGIN
    IF OLD.is_voided = false
       AND NEW.is_voided = true
       AND EXISTS (
           SELECT 1
           FROM lending.seven_by_seven_extra_principal_adjustments adjustment
           WHERE adjustment.transaction_id = OLD.id
       ) THEN
        SELECT void_evidence.id INTO void_id
        FROM lending.collection_transaction_voids void_evidence
        WHERE void_evidence.transaction_id = OLD.id;
        IF void_id IS NULL THEN
            RAISE EXCEPTION
                'Extra Principal reversal requires immutable collection-void evidence.';
        END IF;
        PERFORM lending.reverse_seven_by_seven_extra_principal_for_void(
            OLD.id,
            void_id,
            NEW.voided_by_user_id,
            NEW.void_reason
        );
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION lending.guard_seven_by_seven_extra_principal_void_reversal()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target lending.seven_by_seven_extra_principal_adjustments%ROWTYPE;
    reversal lending.seven_by_seven_extra_principal_reversals%ROWTYPE;
    replayed JSONB;
    item_count INTEGER;
    matched_item_count INTEGER;
    installment_count INTEGER;
    mismatch_count INTEGER;
    current_version INTEGER;
BEGIN
    IF OLD.is_voided = false AND NEW.is_voided = true THEN
        SELECT * INTO target
        FROM lending.seven_by_seven_extra_principal_adjustments adjustment
        WHERE adjustment.transaction_id = OLD.id;
        IF NOT FOUND THEN
            RETURN NEW;
        END IF;

        SELECT reversal_row.* INTO reversal
        FROM lending.seven_by_seven_extra_principal_reversals reversal_row
        JOIN lending.seven_by_seven_extra_principal_reversal_requests request
          ON request.id = reversal_row.reversal_request_id
        JOIN lending.collection_transaction_voids void_evidence
          ON void_evidence.id = reversal_row.collection_void_id
        WHERE reversal_row.adjustment_id = target.id
          AND reversal_row.transaction_id = OLD.id
          AND reversal_row.reversed_by_user_id = NEW.voided_by_user_id
          AND reversal_row.reason = NEW.void_reason
          AND request.outcome = 'completed'
          AND request.collection_void_id = reversal_row.collection_void_id
          AND request.requested_by_user_id = NEW.voided_by_user_id
          AND request.reason = NEW.void_reason
          AND void_evidence.transaction_id = OLD.id
          AND void_evidence.voided_by_user_id = NEW.voided_by_user_id
          AND void_evidence.reason = NEW.void_reason;
        IF NOT FOUND THEN
            RAISE EXCEPTION
                'Extra Principal source cannot be voided without exact immutable operational reversal evidence.';
        END IF;

        replayed := lending.replay_seven_by_seven_extra_principal(
            target.schedule_id,
            NULL
        );
        IF replayed ->> 'source_history_digest'
               <> reversal.source_history_digest
           OR replayed ->> 'operational_state_digest'
               <> reversal.operational_state_digest THEN
            RAISE EXCEPTION
                'Extra Principal reversal evidence does not match immutable replay.';
        END IF;

        SELECT count(*)::INTEGER INTO installment_count
        FROM lending.loan_contract_installments installment
        WHERE installment.schedule_id = target.schedule_id;
        SELECT count(*)::INTEGER INTO item_count
        FROM lending.seven_by_seven_extra_principal_reversal_items item
        WHERE item.reversal_id = reversal.id;
        SELECT
            count(operational.installment_id)::INTEGER,
            count(*) FILTER (
                WHERE operational.installment_id IS NOT NULL
                  AND (
                      operational.operational_amount
                          <> item.reconstructed_operational_amount
                      OR operational.operational_principal_component
                          <> item.reconstructed_operational_principal
                      OR operational.operational_interest_component
                          <> item.reconstructed_operational_interest
                      OR operational.removed_from_operational_schedule
                          <> item.reconstructed_removed
                      OR operational.last_extra_principal_adjustment_id
                          IS DISTINCT FROM item.last_active_adjustment_id
                  )
            )::INTEGER
        INTO matched_item_count, mismatch_count
        FROM lending.seven_by_seven_extra_principal_reversal_items item
        LEFT JOIN lending.loan_installment_operational_amounts operational
          ON operational.installment_id = item.installment_id
        WHERE item.reversal_id = reversal.id;
        SELECT state.operational_version INTO current_version
        FROM lending.loan_schedule_operational_state state
        WHERE state.schedule_id = target.schedule_id;
        IF item_count <> installment_count
           OR matched_item_count <> installment_count
           OR mismatch_count <> 0
           OR current_version <> reversal.resulting_operational_version THEN
            RAISE EXCEPTION
                'Extra Principal operational reconstruction is incomplete or stale.';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_01a_extra_principal_operational_reversal
    ON lending.collection_transactions;
CREATE TRIGGER accounting_01a_extra_principal_operational_reversal
BEFORE UPDATE OF is_voided ON lending.collection_transactions
FOR EACH ROW EXECUTE FUNCTION lending.perform_seven_by_seven_extra_principal_void_reversal();

DROP TRIGGER IF EXISTS accounting_01b_extra_principal_operational_reversal_guard
    ON lending.collection_transactions;
CREATE TRIGGER accounting_01b_extra_principal_operational_reversal_guard
BEFORE UPDATE OF is_voided ON lending.collection_transactions
FOR EACH ROW EXECUTE FUNCTION lending.guard_seven_by_seven_extra_principal_void_reversal();

CREATE OR REPLACE VIEW lending.seven_by_seven_extra_principal_reversal_status AS
WITH blocked AS (
    SELECT
        request.adjustment_id,
        count(*)::INTEGER AS blocked_request_count,
        max(request.requested_at) AS last_blocked_at,
        max(request.released_refund_amount)::numeric(18,2)
            AS last_blocking_released_refund_amount
    FROM lending.seven_by_seven_extra_principal_reversal_requests request
    WHERE request.outcome = 'blocked_refund_released'
    GROUP BY request.adjustment_id
)
SELECT
    adjustment.id AS adjustment_id,
    adjustment.transaction_id,
    adjustment.loan_id,
    adjustment.schedule_id,
    reversal.id AS reversal_id,
    reversal.reversal_request_id,
    reversal.collection_void_id,
    reversal.reversed_at,
    reversal.reversed_by_user_id,
    (reversal.id IS NOT NULL) AS is_reversed,
    (reversal.id IS NULL) AS is_active,
    coalesce(blocked.blocked_request_count, 0) AS blocked_request_count,
    blocked.last_blocked_at,
    coalesce(
        blocked.last_blocking_released_refund_amount,
        0
    )::numeric(18,2) AS last_blocking_released_refund_amount
FROM lending.seven_by_seven_extra_principal_adjustments adjustment
LEFT JOIN lending.seven_by_seven_extra_principal_reversals reversal
  ON reversal.adjustment_id = adjustment.id
LEFT JOIN blocked
  ON blocked.adjustment_id = adjustment.id;

CREATE OR REPLACE VIEW lending.loan_unused_advance_refund_due_status AS
WITH approvals AS (
    SELECT
        item.adjustment_id,
        item.installment_id,
        sum(item.amount_approved)::numeric(18,2) AS approved_amount
    FROM lending.loan_unused_advance_refund_due_approval_items item
    GROUP BY item.adjustment_id, item.installment_id
), releases AS (
    SELECT
        item.adjustment_id,
        item.installment_id,
        sum(item.amount_released)::numeric(18,2) AS released_amount,
        max(release.released_at) AS last_released_at
    FROM lending.loan_unused_advance_refund_due_release_items item
    JOIN lending.loan_unused_advance_refund_due_releases release
      ON release.id = item.release_id
    GROUP BY item.adjustment_id, item.installment_id
)
SELECT
    refund.adjustment_id,
    refund.installment_id,
    adjustment.loan_id,
    adjustment.schedule_id,
    adjustment.transaction_id,
    refund.amount_due AS classified_amount,
    (reversal.id IS NOT NULL) AS is_reversed,
    CASE
        WHEN reversal.id IS NULL THEN refund.amount_due
        ELSE 0
    END::numeric(18,2) AS active_classified_amount,
    coalesce(approvals.approved_amount, 0)::numeric(18,2)
        AS approved_amount,
    coalesce(releases.released_amount, 0)::numeric(18,2)
        AS released_amount,
    CASE
        WHEN reversal.id IS NOT NULL THEN 0
        ELSE greatest(
            refund.amount_due - coalesce(releases.released_amount, 0),
            0
        )
    END::numeric(18,2) AS outstanding_refund_due,
    CASE
        WHEN reversal.id IS NOT NULL THEN 0
        ELSE greatest(
            least(
                refund.amount_due,
                coalesce(approvals.approved_amount, 0)
            ) - coalesce(releases.released_amount, 0),
            0
        )
    END::numeric(18,2) AS approved_unreleased_amount,
    coalesce(releases.released_amount, 0)::numeric(18,2)
        AS reversal_blocking_amount,
    releases.last_released_at,
    reversal.reversed_at
FROM lending.loan_unused_advance_refund_dues refund
JOIN lending.seven_by_seven_extra_principal_adjustments adjustment
  ON adjustment.id = refund.adjustment_id
LEFT JOIN lending.seven_by_seven_extra_principal_reversals reversal
  ON reversal.adjustment_id = refund.adjustment_id
LEFT JOIN approvals
  ON approvals.adjustment_id = refund.adjustment_id
 AND approvals.installment_id = refund.installment_id
LEFT JOIN releases
  ON releases.adjustment_id = refund.adjustment_id
 AND releases.installment_id = refund.installment_id;

-- Gross historical Advance stays immutable. A Refund Due reduces active Advance
-- only while its originating Extra Principal adjustment remains active.
CREATE OR REPLACE VIEW lending.loan_installment_active_advance AS
WITH gross AS (
    SELECT
        installment.id AS installment_id,
        coalesce(sum(allocation.amount_applied) FILTER (
            WHERE transaction.is_voided = false
              AND allocation.allocation_basis = 'future_advance_oldest_first'
        ), 0)::numeric(18,2) AS gross_advance_allocated
    FROM lending.loan_contract_installments installment
    LEFT JOIN lending.loan_installment_payment_allocations allocation
      ON allocation.installment_id = installment.id
    LEFT JOIN lending.collection_transactions transaction
      ON transaction.id = allocation.transaction_id
    GROUP BY installment.id
), active_refunds AS (
    SELECT
        status.installment_id,
        sum(status.active_classified_amount)::numeric(18,2)
            AS refund_due_total
    FROM lending.loan_unused_advance_refund_due_status status
    GROUP BY status.installment_id
)
SELECT
    gross.installment_id,
    gross.gross_advance_allocated,
    coalesce(active_refunds.refund_due_total, 0)::numeric(18,2)
        AS refund_due_total,
    greatest(
        gross.gross_advance_allocated
        - coalesce(active_refunds.refund_due_total, 0),
        0
    )::numeric(18,2) AS active_advance_allocated
FROM gross
LEFT JOIN active_refunds
  ON active_refunds.installment_id = gross.installment_id;

-- Extra Principal remains an ordinary immutable collection source for the
-- existing protected 7x7 accounting lifecycle. This view does not invent a new
-- account, journal, or automatic posting rule. It proves the source identity,
-- exposes whether current coordinates are available, and leaves preparation /
-- posting as explicit Management actions.
CREATE OR REPLACE VIEW accounting.seven_by_seven_extra_principal_accounting_readiness AS
WITH coordinate_summary AS (
    SELECT
        coordinate.transaction_id,
        count(*)::integer AS coordinate_line_count,
        bool_and(coordinate.coordinate_preview_ready) AS all_coordinates_ready,
        sum(coordinate.debit)::numeric(18,2) AS total_debit,
        sum(coordinate.credit)::numeric(18,2) AS total_credit
    FROM accounting.seven_by_seven_source_event_journal_coordinate_preview coordinate
    GROUP BY coordinate.transaction_id
)
SELECT
    adjustment.id AS adjustment_id,
    adjustment.transaction_id,
    adjustment.loan_id,
    adjustment.schedule_id,
    accounting.seven_by_seven_collection_source_event_key(
        adjustment.transaction_id
    ) AS source_event_key,
    transaction.amount AS source_cash_amount,
    adjustment.principal_reduction,
    coalesce(
        nullif(transaction.details ->> 'interest_contribution', ''),
        transaction.details ->> 'seven_by_seven_interest_paid'
    ) AS interest_contribution,
    coalesce(
        nullif(transaction.details ->> 'principal_extra_amount', ''),
        transaction.details ->> 'seven_by_seven_principal_paid'
    ) AS principal_contribution,
    inventory.is_active_positive_cash_event,
    inventory.active_positive_cash_events_on_date,
    coalesce(coordinate.coordinate_line_count, 0) AS coordinate_line_count,
    coalesce(coordinate.all_coordinates_ready, false) AS coordinates_ready,
    coordinate.total_debit,
    coordinate.total_credit,
    prepared.id AS journal_preparation_id,
    posted.id AS journal_posting_id,
    (
        inventory.transaction_id = adjustment.transaction_id
        AND inventory.loan_id = adjustment.loan_id
        AND inventory.source_event_key
            = accounting.seven_by_seven_collection_source_event_key(
                adjustment.transaction_id
            )
        AND inventory.is_active_positive_cash_event
        AND transaction.entry_type = 'payment'
        AND transaction.is_voided = false
        AND transaction.amount = adjustment.principal_reduction
        AND transaction.details ->> 'payment_allocation_intent'
            = 'extra_as_principal_reduction'
        AND coalesce(
            nullif(transaction.details ->> 'interest_contribution', ''),
            transaction.details ->> 'seven_by_seven_interest_paid'
        ) = '0.00'
        AND coalesce(
            nullif(transaction.details ->> 'principal_extra_amount', ''),
            transaction.details ->> 'seven_by_seven_principal_paid'
        ) = to_char(adjustment.principal_reduction, 'FM999999999999990.00')
    ) AS source_evidence_ready,
    CASE
        WHEN posted.id IS NOT NULL THEN 'posted'
        WHEN prepared.id IS NOT NULL THEN 'prepared_not_posted'
        WHEN coalesce(coordinate.coordinate_line_count, 0) > 0
         AND coalesce(coordinate.all_coordinates_ready, false)
         AND coordinate.total_debit = coordinate.total_credit
            THEN 'ready_for_management_draft'
        WHEN inventory.transaction_id IS NOT NULL
            THEN 'management_accounting_review_required'
        ELSE 'source_evidence_mismatch'
    END AS accounting_status,
    false AS automatic_source_posting
FROM lending.seven_by_seven_extra_principal_adjustments adjustment
JOIN lending.collection_transactions transaction
  ON transaction.id = adjustment.transaction_id
LEFT JOIN accounting.seven_by_seven_collection_source_inventory inventory
  ON inventory.transaction_id = adjustment.transaction_id
LEFT JOIN coordinate_summary coordinate
  ON coordinate.transaction_id = adjustment.transaction_id
LEFT JOIN accounting.seven_by_seven_journal_draft_preparations prepared
  ON prepared.transaction_id = adjustment.transaction_id
LEFT JOIN accounting.seven_by_seven_journal_postings posted
  ON posted.transaction_id = adjustment.transaction_id;

COMMENT ON TABLE lending.seven_by_seven_extra_principal_reversal_requests IS
    'Terminal immutable exact-retry evidence for completed or released-refund-blocked 7x7 Extra Principal reversal requests.';
COMMENT ON TABLE lending.seven_by_seven_extra_principal_reversals IS
    'Immutable successful reconstruction header for one reversed 7x7 Extra Principal adjustment and its protected collection void.';
COMMENT ON TABLE lending.seven_by_seven_extra_principal_reversal_items IS
    'Immutable per-installment before/after reconstruction evidence for a successful 7x7 Extra Principal reversal.';
COMMENT ON TABLE lending.loan_unused_advance_refund_due_approvals IS
    'Immutable Management authorization header for an itemized unused-Advance Refund Due; approval does not release cash.';
COMMENT ON TABLE lending.loan_unused_advance_refund_due_approval_items IS
    'Immutable per-classification allocation of a Refund Due approval, preventing ambiguous partial approval across installments.';
COMMENT ON TABLE lending.loan_unused_advance_refund_due_releases IS
    'Immutable physical cash-release header tied to prior approval, collector custody, and external evidence.';
COMMENT ON TABLE lending.loan_unused_advance_refund_due_release_items IS
    'Immutable per-classification allocation of physically released Refund Due cash.';
COMMENT ON TABLE lending.collection_remittance_refund_due_release_items IS
    'Immutable, separately itemized cash-outflow evidence included in a Collector remittance without changing the original receipt or Refund Due release.';
COMMENT ON VIEW lending.loan_unused_advance_refund_due_status IS
    'Derived Refund Due lifecycle by original classification: classified, approved, released, outstanding, reversed, and reversal-blocking amounts.';
COMMENT ON VIEW lending.seven_by_seven_extra_principal_reversal_status IS
    'Derived active/reversed state and permanent blocked-attempt evidence for every 7x7 Extra Principal adjustment.';
COMMENT ON VIEW lending.loan_installment_active_advance IS
    'Current installment-specific Advance: immutable gross verified Advance less Refund Due classifications from active Extra Principal adjustments only.';
COMMENT ON VIEW accounting.seven_by_seven_extra_principal_accounting_readiness IS
    'Read-only Extra Principal source identity and current protected 7x7 journal readiness. Accounting remains explicit Management preparation/posting and automatic source posting is always false.';

COMMIT;
