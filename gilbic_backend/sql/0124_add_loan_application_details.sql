BEGIN;

-- Add optional declared employment/reference facts to new immutable versions.
-- Existing request/repayment snapshots and history triggers remain unchanged.
ALTER TABLE lending.loan_application_versions
    DROP CONSTRAINT IF EXISTS loan_application_versions_information_check;

ALTER TABLE lending.loan_application_versions
    ADD CONSTRAINT loan_application_versions_information_check CHECK (
        CASE WHEN jsonb_typeof(information) = 'object' THEN
            (
                jsonb_typeof(information -> 'request') = 'object'
                AND jsonb_typeof(information -> 'repayment') = 'object'
                AND information - 'request' - 'repayment' - 'details' = '{}'::jsonb
                AND (
                    NOT (information ? 'details')
                    OR (
                        jsonb_typeof(information -> 'details') = 'object'
                        AND information -> 'details' -> 'schema_version' = '1'::jsonb
                        AND jsonb_typeof(information -> 'details' -> 'employment') = 'object'
                        AND jsonb_typeof(information -> 'details' -> 'references') = 'array'
                        AND (information -> 'details') - 'schema_version' - 'employment' - 'references' = '{}'::jsonb
                    )
                )
            ) IS TRUE
        ELSE false END
    );

COMMIT;
