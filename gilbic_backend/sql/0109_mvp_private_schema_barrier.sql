BEGIN;

-- SPINA public clients authenticate through Supabase Auth but must reach lending,
-- accounting, device, and audit records only through the protected FastAPI API.
-- This migration is intentionally idempotent and does not change object owners,
-- RLS state, or the privileges of the database role used by the backend.
DO $spina_mvp_private_schema_barrier$
DECLARE
    target_schema text;
    target_role text;
    private_schemas constant text[] := ARRAY[
        'core',
        'lending',
        'accounting',
        'mobile'
    ];
    optional_client_roles constant text[] := ARRAY[
        'anon',
        'authenticated',
        'service_role'
    ];
BEGIN
    FOREACH target_schema IN ARRAY private_schemas
    LOOP
        CONTINUE WHEN to_regnamespace(target_schema) IS NULL;

        -- PUBLIC is always present. Revoke existing access to current objects.
        EXECUTE format(
            'REVOKE USAGE ON SCHEMA %I FROM PUBLIC',
            target_schema
        );
        EXECUTE format(
            'REVOKE CREATE ON SCHEMA %I FROM PUBLIC',
            target_schema
        );
        EXECUTE format(
            'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA %I FROM PUBLIC',
            target_schema
        );
        EXECUTE format(
            'REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA %I FROM PUBLIC',
            target_schema
        );
        EXECUTE format(
            'REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA %I FROM PUBLIC',
            target_schema
        );
        EXECUTE format(
            'REVOKE ALL PRIVILEGES ON ALL PROCEDURES IN SCHEMA %I FROM PUBLIC',
            target_schema
        );

        -- Preserve the same boundary for future objects created by the current
        -- migration/database owner. Migrations must continue to run as that owner.
        EXECUTE format(
            'ALTER DEFAULT PRIVILEGES IN SCHEMA %I REVOKE ALL PRIVILEGES ON TABLES FROM PUBLIC',
            target_schema
        );
        EXECUTE format(
            'ALTER DEFAULT PRIVILEGES IN SCHEMA %I REVOKE ALL PRIVILEGES ON SEQUENCES FROM PUBLIC',
            target_schema
        );
        EXECUTE format(
            'ALTER DEFAULT PRIVILEGES IN SCHEMA %I REVOKE ALL PRIVILEGES ON FUNCTIONS FROM PUBLIC',
            target_schema
        );

        -- Supabase roles are optional in ordinary disposable PostgreSQL. Apply the
        -- same revocation only when each role actually exists.
        FOR target_role IN
            SELECT role_name
            FROM unnest(optional_client_roles) AS requested(role_name)
            JOIN pg_roles ON pg_roles.rolname = requested.role_name
            ORDER BY role_name
        LOOP
            EXECUTE format(
                'REVOKE USAGE ON SCHEMA %I FROM %I',
                target_schema,
                target_role
            );
            EXECUTE format(
                'REVOKE CREATE ON SCHEMA %I FROM %I',
                target_schema,
                target_role
            );
            EXECUTE format(
                'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA %I FROM %I',
                target_schema,
                target_role
            );
            EXECUTE format(
                'REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA %I FROM %I',
                target_schema,
                target_role
            );
            EXECUTE format(
                'REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA %I FROM %I',
                target_schema,
                target_role
            );
            EXECUTE format(
                'REVOKE ALL PRIVILEGES ON ALL PROCEDURES IN SCHEMA %I FROM %I',
                target_schema,
                target_role
            );
            EXECUTE format(
                'ALTER DEFAULT PRIVILEGES IN SCHEMA %I REVOKE ALL PRIVILEGES ON TABLES FROM %I',
                target_schema,
                target_role
            );
            EXECUTE format(
                'ALTER DEFAULT PRIVILEGES IN SCHEMA %I REVOKE ALL PRIVILEGES ON SEQUENCES FROM %I',
                target_schema,
                target_role
            );
            EXECUTE format(
                'ALTER DEFAULT PRIVILEGES IN SCHEMA %I REVOKE ALL PRIVILEGES ON FUNCTIONS FROM %I',
                target_schema,
                target_role
            );
        END LOOP;
    END LOOP;
END
$spina_mvp_private_schema_barrier$;

COMMIT;
