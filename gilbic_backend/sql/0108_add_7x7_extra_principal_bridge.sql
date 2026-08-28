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
