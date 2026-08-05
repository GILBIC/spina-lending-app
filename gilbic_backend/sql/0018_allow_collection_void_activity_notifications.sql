BEGIN;

ALTER TABLE core.activity_notifications
    DROP CONSTRAINT IF EXISTS activity_notifications_notification_type_check;

ALTER TABLE core.activity_notifications
    ADD CONSTRAINT activity_notifications_notification_type_check
    CHECK (
        notification_type = ANY (
            ARRAY[
                'cross_collection_posted'::TEXT,
                'cross_collection_remitted'::TEXT,
                'cross_collection_accepted'::TEXT,
                'client_payment_posted'::TEXT,
                'client_payment_remitted'::TEXT,
                'client_payment_accepted'::TEXT,
                'collector_payment_voided'::TEXT,
                'client_payment_voided'::TEXT
            ]
        )
    );

COMMIT;
