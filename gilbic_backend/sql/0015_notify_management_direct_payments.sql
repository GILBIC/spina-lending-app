BEGIN;

CREATE OR REPLACE FUNCTION core.create_management_direct_assignment_activity()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, core, lending
AS $$
DECLARE
    management_name TEXT;
    client_name TEXT;
    selected_dates TEXT;
    amount_text TEXT;
BEGIN
    IF NEW.collection_origin <> 'management_direct'
       OR NEW.assigned_collector_user_id IS NULL
       OR NEW.entry_type NOT IN ('payment', 'advance') THEN
        RETURN NEW;
    END IF;

    SELECT coalesce(
        nullif(btrim(user_account.full_name), ''),
        nullif(btrim(user_account.username), ''),
        'Management'
    )
    INTO management_name
    FROM core.users user_account
    WHERE user_account.id = NEW.collector_user_id;

    SELECT client.full_name
    INTO client_name
    FROM lending.clients client
    WHERE client.id = NEW.client_id;

    SELECT string_agg(value, ', ' ORDER BY value)
    INTO selected_dates
    FROM jsonb_array_elements_text(
        coalesce(NEW.details -> 'covered_dates', '[]'::jsonb)
    ) AS date_value(value);

    selected_dates := coalesce(nullif(selected_dates, ''), NEW.collection_date::text);
    amount_text := to_char(NEW.amount, 'FM999999999999990.00');

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
        'Management posted a direct payment',
        format(
            '%s posted PHP %s directly from %s for dates %s. Receipt %s. This entry is read-only to collectors.',
            coalesce(management_name, 'Management'),
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
            'recorder_name', management_name,
            'assigned_collector_user_id', NEW.assigned_collector_user_id,
            'collection_origin', NEW.collection_origin,
            'remaining_balance', to_char(NEW.official_balance, 'FM999999999999990.00'),
            'collector_editable', false
        )
    )
    ON CONFLICT DO NOTHING;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_management_direct_payment_activity
    ON lending.collection_transactions;
CREATE TRIGGER lending_management_direct_payment_activity
AFTER INSERT ON lending.collection_transactions
FOR EACH ROW
EXECUTE FUNCTION core.create_management_direct_assignment_activity();

COMMIT;
