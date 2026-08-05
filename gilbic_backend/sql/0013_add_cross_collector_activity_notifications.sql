BEGIN;

ALTER TABLE lending.collection_transactions
    ADD COLUMN IF NOT EXISTS assigned_collector_user_id UUID
        REFERENCES core.users(id) ON DELETE RESTRICT;
ALTER TABLE lending.collection_transactions
    ADD COLUMN IF NOT EXISTS assignment_area TEXT NOT NULL DEFAULT '';
ALTER TABLE lending.collection_transactions
    ADD COLUMN IF NOT EXISTS collection_origin TEXT NOT NULL DEFAULT 'unassigned_intake';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'collection_transactions_origin_check'
          AND conrelid = 'lending.collection_transactions'::regclass
    ) THEN
        ALTER TABLE lending.collection_transactions
            ADD CONSTRAINT collection_transactions_origin_check
            CHECK (
                collection_origin IN (
                    'assigned_route',
                    'cross_collector',
                    'management_direct',
                    'unassigned_intake'
                )
            );
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS lending_collection_transactions_assigned_collector_idx
    ON lending.collection_transactions (
        assigned_collector_user_id,
        collection_date DESC,
        accepted_at DESC
    )
    WHERE assigned_collector_user_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS lending.collection_assignment_reviews (
    transaction_id UUID PRIMARY KEY
        REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    assigned_collector_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    accepted_remittance_id UUID NOT NULL
        REFERENCES lending.collection_remittances(id) ON DELETE RESTRICT,
    reviewed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS lending_collection_assignment_reviews_collector_idx
    ON lending.collection_assignment_reviews (
        assigned_collector_user_id,
        reviewed_at DESC
    );

CREATE TABLE IF NOT EXISTS core.activity_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    sender_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    notification_type TEXT NOT NULL
        CHECK (
            notification_type IN (
                'cross_collection_posted',
                'cross_collection_remitted',
                'cross_collection_accepted',
                'client_payment_posted',
                'client_payment_remitted',
                'client_payment_accepted'
            )
        ),
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    transaction_id UUID
        REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    remittance_id UUID
        REFERENCES lending.collection_remittances(id) ON DELETE RESTRICT,
    client_id UUID REFERENCES lending.clients(id) ON DELETE RESTRICT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_read BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    read_at TIMESTAMPTZ,
    CHECK (btrim(title) <> ''),
    CHECK (btrim(message) <> ''),
    CHECK (
        (is_read = false AND read_at IS NULL)
        OR
        (is_read = true AND read_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS core_activity_notifications_recipient_idx
    ON core.activity_notifications (
        recipient_user_id,
        is_read,
        created_at DESC,
        id DESC
    );
CREATE UNIQUE INDEX IF NOT EXISTS core_activity_notifications_transaction_uidx
    ON core.activity_notifications (
        recipient_user_id,
        notification_type,
        transaction_id
    )
    WHERE transaction_id IS NOT NULL AND remittance_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS core_activity_notifications_remittance_uidx
    ON core.activity_notifications (
        recipient_user_id,
        notification_type,
        transaction_id,
        remittance_id
    )
    WHERE transaction_id IS NOT NULL AND remittance_id IS NOT NULL;

CREATE OR REPLACE FUNCTION lending.capture_collection_assignment()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, lending, core
AS $$
DECLARE
    client_area TEXT;
    route_owner UUID;
    actor_is_management BOOLEAN;
BEGIN
    SELECT coalesce(client.area, '')
    INTO client_area
    FROM lending.clients client
    WHERE client.id = NEW.client_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'The client for this collection does not exist.'
            USING ERRCODE = '23503';
    END IF;

    SELECT assignment.collector_user_id
    INTO route_owner
    FROM lending.collector_area_assignments assignment
    WHERE assignment.is_active = true
      AND lower(btrim(assignment.area)) = lower(btrim(client_area))
    ORDER BY assignment.sort_order, assignment.id
    LIMIT 1;

    SELECT EXISTS (
        SELECT 1
        FROM core.user_roles user_role
        JOIN core.roles role ON role.id = user_role.role_id
        WHERE user_role.user_id = NEW.collector_user_id
          AND role.code = 'management'
    )
    INTO actor_is_management;

    NEW.assignment_area := client_area;
    NEW.assigned_collector_user_id := route_owner;

    IF actor_is_management THEN
        NEW.collection_origin := 'management_direct';
    ELSIF route_owner IS NULL THEN
        NEW.collection_origin := 'unassigned_intake';
    ELSIF route_owner = NEW.collector_user_id THEN
        NEW.collection_origin := 'assigned_route';
    ELSE
        NEW.collection_origin := 'cross_collector';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_collection_assignment_capture
    ON lending.collection_transactions;
CREATE TRIGGER lending_collection_assignment_capture
BEFORE INSERT ON lending.collection_transactions
FOR EACH ROW
EXECUTE FUNCTION lending.capture_collection_assignment();

WITH assignment_snapshot AS (
    SELECT
        transaction.id,
        coalesce(client.area, '') AS assignment_area,
        (
            SELECT assignment.collector_user_id
            FROM lending.collector_area_assignments assignment
            WHERE assignment.is_active = true
              AND lower(btrim(assignment.area)) = lower(btrim(coalesce(client.area, '')))
            ORDER BY assignment.sort_order, assignment.id
            LIMIT 1
        ) AS assigned_collector_user_id,
        EXISTS (
            SELECT 1
            FROM core.user_roles user_role
            JOIN core.roles role ON role.id = user_role.role_id
            WHERE user_role.user_id = transaction.collector_user_id
              AND role.code = 'management'
        ) AS actor_is_management
    FROM lending.collection_transactions transaction
    JOIN lending.clients client ON client.id = transaction.client_id
)
UPDATE lending.collection_transactions transaction
SET assigned_collector_user_id = snapshot.assigned_collector_user_id,
    assignment_area = snapshot.assignment_area,
    collection_origin = CASE
        WHEN snapshot.actor_is_management THEN 'management_direct'
        WHEN snapshot.assigned_collector_user_id IS NULL THEN 'unassigned_intake'
        WHEN snapshot.assigned_collector_user_id = transaction.collector_user_id
            THEN 'assigned_route'
        ELSE 'cross_collector'
    END
FROM assignment_snapshot snapshot
WHERE snapshot.id = transaction.id;

CREATE OR REPLACE FUNCTION core.create_collection_posted_activity()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, core, lending
AS $$
DECLARE
    recorder_name TEXT;
    assigned_name TEXT;
    client_user_id UUID;
    client_name TEXT;
    selected_dates TEXT;
    amount_text TEXT;
BEGIN
    IF NEW.entry_type NOT IN ('payment', 'advance') THEN
        RETURN NEW;
    END IF;

    SELECT coalesce(nullif(btrim(user_account.full_name), ''), user_account.username)
    INTO recorder_name
    FROM core.users user_account
    WHERE user_account.id = NEW.collector_user_id;

    SELECT client.user_id, client.full_name
    INTO client_user_id, client_name
    FROM lending.clients client
    WHERE client.id = NEW.client_id;

    IF NEW.assigned_collector_user_id IS NOT NULL THEN
        SELECT coalesce(nullif(btrim(user_account.full_name), ''), user_account.username)
        INTO assigned_name
        FROM core.users user_account
        WHERE user_account.id = NEW.assigned_collector_user_id;
    END IF;

    SELECT string_agg(value, ', ' ORDER BY value)
    INTO selected_dates
    FROM jsonb_array_elements_text(
        coalesce(NEW.details -> 'covered_dates', '[]'::jsonb)
    ) AS date_value(value);

    selected_dates := coalesce(nullif(selected_dates, ''), NEW.collection_date::text);
    amount_text := to_char(NEW.amount, 'FM999999999999990.00');

    IF NEW.collection_origin = 'cross_collector'
       AND NEW.assigned_collector_user_id IS NOT NULL
       AND NEW.assigned_collector_user_id <> NEW.collector_user_id THEN
        INSERT INTO core.activity_notifications (
            recipient_user_id,
            sender_user_id,
            notification_type,
            title,
            message,
            transaction_id,
            client_id,
            metadata
        ) VALUES (
            NEW.assigned_collector_user_id,
            NEW.collector_user_id,
            'cross_collection_posted',
            'Payment recorded by another collector',
            format(
                '%s recorded PHP %s from %s for dates %s. Receipt %s. Review the remittance destination before accepting custody.',
                coalesce(recorder_name, 'Another collector'),
                amount_text,
                client_name,
                selected_dates,
                NEW.receipt_number
            ),
            NEW.id,
            NEW.client_id,
            jsonb_build_object(
                'receipt_number', NEW.receipt_number,
                'amount', amount_text,
                'covered_dates', coalesce(NEW.details -> 'covered_dates', '[]'::jsonb),
                'recorder_user_id', NEW.collector_user_id,
                'recorder_name', recorder_name,
                'assigned_collector_user_id', NEW.assigned_collector_user_id,
                'assigned_collector_name', assigned_name,
                'collection_origin', NEW.collection_origin,
                'remaining_balance', to_char(NEW.official_balance, 'FM999999999999990.00')
            )
        )
        ON CONFLICT DO NOTHING;
    END IF;

    IF client_user_id IS NOT NULL THEN
        INSERT INTO core.activity_notifications (
            recipient_user_id,
            sender_user_id,
            notification_type,
            title,
            message,
            transaction_id,
            client_id,
            metadata
        ) VALUES (
            client_user_id,
            NEW.collector_user_id,
            'client_payment_posted',
            'Your payment was posted',
            format(
                '%s posted your PHP %s payment for dates %s. Receipt %s. Remaining balance PHP %s.',
                coalesce(recorder_name, 'SPINA staff'),
                amount_text,
                selected_dates,
                NEW.receipt_number,
                to_char(NEW.official_balance, 'FM999999999999990.00')
            ),
            NEW.id,
            NEW.client_id,
            jsonb_build_object(
                'receipt_number', NEW.receipt_number,
                'amount', amount_text,
                'covered_dates', coalesce(NEW.details -> 'covered_dates', '[]'::jsonb),
                'recorder_user_id', NEW.collector_user_id,
                'recorder_name', recorder_name,
                'collection_origin', NEW.collection_origin,
                'remaining_balance', to_char(NEW.official_balance, 'FM999999999999990.00')
            )
        )
        ON CONFLICT DO NOTHING;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_collection_posted_activity
    ON lending.collection_transactions;
CREATE TRIGGER lending_collection_posted_activity
AFTER INSERT ON lending.collection_transactions
FOR EACH ROW
EXECUTE FUNCTION core.create_collection_posted_activity();

CREATE OR REPLACE FUNCTION core.create_collection_remitted_activity()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, core, lending
AS $$
DECLARE
    remittance_record lending.collection_remittances%ROWTYPE;
    transaction_record lending.collection_transactions%ROWTYPE;
    client_user_id UUID;
    client_name TEXT;
    collector_name TEXT;
    recipient_name TEXT;
    amount_text TEXT;
BEGIN
    SELECT *
    INTO remittance_record
    FROM lending.collection_remittances
    WHERE id = NEW.remittance_id;

    SELECT *
    INTO transaction_record
    FROM lending.collection_transactions
    WHERE id = NEW.transaction_id;

    SELECT client.user_id, client.full_name
    INTO client_user_id, client_name
    FROM lending.clients client
    WHERE client.id = NEW.client_id;

    SELECT coalesce(nullif(btrim(user_account.full_name), ''), user_account.username)
    INTO collector_name
    FROM core.users user_account
    WHERE user_account.id = remittance_record.collector_user_id;

    SELECT coalesce(nullif(btrim(user_account.full_name), ''), user_account.username)
    INTO recipient_name
    FROM core.users user_account
    WHERE user_account.id = remittance_record.recipient_user_id;

    amount_text := to_char(NEW.amount, 'FM999999999999990.00');

    IF transaction_record.assigned_collector_user_id IS NOT NULL
       AND transaction_record.assigned_collector_user_id <> transaction_record.collector_user_id THEN
        INSERT INTO core.activity_notifications (
            recipient_user_id,
            sender_user_id,
            notification_type,
            title,
            message,
            transaction_id,
            remittance_id,
            client_id,
            metadata
        ) VALUES (
            transaction_record.assigned_collector_user_id,
            remittance_record.collector_user_id,
            'cross_collection_remitted',
            'Other-collector payment was remitted',
            format(
                '%s remitted %s''s PHP %s payment to %s under remittance %s. It is awaiting acceptance.',
                coalesce(collector_name, 'Another collector'),
                client_name,
                amount_text,
                coalesce(recipient_name, 'the selected recipient'),
                remittance_record.remittance_number
            ),
            NEW.transaction_id,
            NEW.remittance_id,
            NEW.client_id,
            jsonb_build_object(
                'receipt_number', NEW.receipt_number,
                'remittance_number', remittance_record.remittance_number,
                'amount', amount_text,
                'recipient_user_id', remittance_record.recipient_user_id,
                'recipient_name', recipient_name,
                'awaiting_acceptance', true
            )
        )
        ON CONFLICT DO NOTHING;
    END IF;

    IF client_user_id IS NOT NULL THEN
        INSERT INTO core.activity_notifications (
            recipient_user_id,
            sender_user_id,
            notification_type,
            title,
            message,
            transaction_id,
            remittance_id,
            client_id,
            metadata
        ) VALUES (
            client_user_id,
            remittance_record.collector_user_id,
            'client_payment_remitted',
            'Your payment was remitted',
            format(
                '%s remitted your receipt %s to %s under remittance %s. It is awaiting acceptance.',
                coalesce(collector_name, 'SPINA staff'),
                NEW.receipt_number,
                coalesce(recipient_name, 'the selected recipient'),
                remittance_record.remittance_number
            ),
            NEW.transaction_id,
            NEW.remittance_id,
            NEW.client_id,
            jsonb_build_object(
                'receipt_number', NEW.receipt_number,
                'remittance_number', remittance_record.remittance_number,
                'amount', amount_text,
                'recipient_user_id', remittance_record.recipient_user_id,
                'recipient_name', recipient_name,
                'awaiting_acceptance', true
            )
        )
        ON CONFLICT DO NOTHING;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_collection_remitted_activity
    ON lending.collection_remittance_items;
CREATE TRIGGER lending_collection_remitted_activity
AFTER INSERT ON lending.collection_remittance_items
FOR EACH ROW
EXECUTE FUNCTION core.create_collection_remitted_activity();

CREATE OR REPLACE FUNCTION core.create_collection_accepted_activity()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, core, lending
AS $$
DECLARE
    item RECORD;
    client_user_id UUID;
    client_name TEXT;
    recipient_name TEXT;
    assigned_name TEXT;
    amount_text TEXT;
BEGIN
    IF OLD.status <> 'submitted' OR NEW.status <> 'received' THEN
        RETURN NEW;
    END IF;

    SELECT coalesce(nullif(btrim(user_account.full_name), ''), user_account.username)
    INTO recipient_name
    FROM core.users user_account
    WHERE user_account.id = NEW.recipient_user_id;

    FOR item IN
        SELECT
            remittance_item.transaction_id,
            remittance_item.client_id,
            remittance_item.amount,
            remittance_item.receipt_number,
            transaction.assigned_collector_user_id,
            transaction.collector_user_id
        FROM lending.collection_remittance_items remittance_item
        JOIN lending.collection_transactions transaction
          ON transaction.id = remittance_item.transaction_id
        WHERE remittance_item.remittance_id = NEW.id
    LOOP
        SELECT client.user_id, client.full_name
        INTO client_user_id, client_name
        FROM lending.clients client
        WHERE client.id = item.client_id;

        amount_text := to_char(item.amount, 'FM999999999999990.00');

        IF item.assigned_collector_user_id IS NOT NULL THEN
            SELECT coalesce(nullif(btrim(user_account.full_name), ''), user_account.username)
            INTO assigned_name
            FROM core.users user_account
            WHERE user_account.id = item.assigned_collector_user_id;
        ELSE
            assigned_name := NULL;
        END IF;

        IF item.assigned_collector_user_id IS NOT NULL
           AND item.assigned_collector_user_id <> item.collector_user_id THEN
            INSERT INTO core.activity_notifications (
                recipient_user_id,
                sender_user_id,
                notification_type,
                title,
                message,
                transaction_id,
                remittance_id,
                client_id,
                metadata
            ) VALUES (
                item.assigned_collector_user_id,
                NEW.recipient_user_id,
                'cross_collection_accepted',
                'Other-collector payment was accepted',
                format(
                    '%s accepted %s''s receipt %s under remittance %s. Cash custody is now with %s.',
                    coalesce(recipient_name, 'The selected recipient'),
                    client_name,
                    item.receipt_number,
                    NEW.remittance_number,
                    coalesce(recipient_name, 'the selected recipient')
                ),
                item.transaction_id,
                NEW.id,
                item.client_id,
                jsonb_build_object(
                    'receipt_number', item.receipt_number,
                    'remittance_number', NEW.remittance_number,
                    'amount', amount_text,
                    'custody_user_id', NEW.recipient_user_id,
                    'custody_name', recipient_name,
                    'accepted_at', NEW.received_at
                )
            )
            ON CONFLICT DO NOTHING;
        END IF;

        IF NEW.recipient_user_id = item.assigned_collector_user_id THEN
            INSERT INTO lending.collection_assignment_reviews (
                transaction_id,
                assigned_collector_user_id,
                accepted_remittance_id,
                reviewed_at
            ) VALUES (
                item.transaction_id,
                NEW.recipient_user_id,
                NEW.id,
                NEW.received_at
            )
            ON CONFLICT (transaction_id) DO NOTHING;
        END IF;

        IF client_user_id IS NOT NULL THEN
            INSERT INTO core.activity_notifications (
                recipient_user_id,
                sender_user_id,
                notification_type,
                title,
                message,
                transaction_id,
                remittance_id,
                client_id,
                metadata
            ) VALUES (
                client_user_id,
                NEW.recipient_user_id,
                'client_payment_accepted',
                'Your payment remittance was accepted',
                format(
                    '%s accepted your receipt %s under remittance %s. Cash custody is now with %s.',
                    coalesce(recipient_name, 'SPINA staff'),
                    item.receipt_number,
                    NEW.remittance_number,
                    coalesce(recipient_name, 'the selected recipient')
                ),
                item.transaction_id,
                NEW.id,
                item.client_id,
                jsonb_build_object(
                    'receipt_number', item.receipt_number,
                    'remittance_number', NEW.remittance_number,
                    'amount', amount_text,
                    'custody_user_id', NEW.recipient_user_id,
                    'custody_name', recipient_name,
                    'accepted_at', NEW.received_at
                )
            )
            ON CONFLICT DO NOTHING;
        END IF;
    END LOOP;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_collection_accepted_activity
    ON lending.collection_remittances;
CREATE TRIGGER lending_collection_accepted_activity
AFTER UPDATE OF status ON lending.collection_remittances
FOR EACH ROW
EXECUTE FUNCTION core.create_collection_accepted_activity();

COMMENT ON COLUMN lending.collection_transactions.assigned_collector_user_id IS
    'Snapshot of the active route owner when the payment was posted. The recorder identity remains in collector_user_id.';
COMMENT ON COLUMN lending.collection_transactions.collection_origin IS
    'How the payment entered SPINA: assigned route, another collector, Management direct, or no active route owner.';
COMMENT ON TABLE lending.collection_assignment_reviews IS
    'One-time adoption/review marker created when the assigned collector accepts a cross-collector remittance. No duplicate collection transaction is created.';
COMMENT ON TABLE core.activity_notifications IS
    'Informational collector and client notifications for payment posting, remittance submission, and accepted cash custody.';

COMMIT;
