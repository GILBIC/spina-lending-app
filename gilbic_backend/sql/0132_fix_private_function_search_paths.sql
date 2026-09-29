BEGIN;

-- Keep existing qualified app-object references and trusted extension lookup.
-- public holds pgcrypto in disposable PostgreSQL; extensions holds it on Supabase.
-- Both must deny object creation to public application roles. pg_catalog is first,
-- pg_temp last, and caller-controlled/$user schemas are never searched.
-- Existing explicit function paths, bodies, owners and ACLs remain unchanged.
DO $spina_private_function_paths$
DECLARE
    shared_schema record;
    client_role record;
    routine record;
BEGIN
    FOR shared_schema IN
        SELECT oid, nspname FROM pg_catalog.pg_namespace
        WHERE nspname IN ('public', 'extensions')
    LOOP
        IF pg_catalog.has_schema_privilege('public', shared_schema.oid, 'CREATE') THEN
            RAISE EXCEPTION 'Untrusted CREATE on shared schema %', shared_schema.nspname;
        END IF;
        FOR client_role IN
            SELECT rolname FROM pg_catalog.pg_roles
            WHERE rolname IN ('anon', 'authenticated', 'service_role')
        LOOP
            IF pg_catalog.has_schema_privilege(client_role.rolname, shared_schema.oid, 'CREATE') THEN
                RAISE EXCEPTION 'Untrusted CREATE on shared schema %', shared_schema.nspname;
            END IF;
        END LOOP;
    END LOOP;

    FOR routine IN
        SELECT n.nspname, p.proname, pg_catalog.pg_get_function_identity_arguments(p.oid) AS arguments
        FROM pg_catalog.pg_proc p
        JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname IN ('core', 'lending', 'accounting', 'mobile')
          AND p.prokind IN ('f', 'p')
          AND NOT EXISTS (
              SELECT 1 FROM pg_catalog.unnest(p.proconfig) AS config(value)
              WHERE config.value LIKE 'search_path=%'
          )
        ORDER BY n.nspname, p.proname, p.oid
    LOOP
        EXECUTE pg_catalog.format(
            'ALTER ROUTINE %I.%I(%s) SET search_path TO pg_catalog, public, extensions, pg_temp',
            routine.nspname, routine.proname, routine.arguments
        );
    END LOOP;
END
$spina_private_function_paths$;

COMMIT;
