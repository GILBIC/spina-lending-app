DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'core_users_external_auth_fkey'
          AND conrelid = 'core.users'::regclass
    ) THEN
        ALTER TABLE core.users
        ADD CONSTRAINT core_users_external_auth_fkey
        FOREIGN KEY (external_auth_id)
        REFERENCES auth.users(id)
        ON DELETE SET NULL;
    END IF;
END
$$;

COMMENT ON COLUMN core.users.external_auth_id IS
    'Supabase Auth user ID. Roles and permissions remain authoritative in core.* tables.';
