# MVP Supabase Access Boundary

## Decision

Web, Windows app mode, Android, and iOS authenticate with Supabase-backed SPINA sessions but do not query `core`, `lending`, `accounting`, or `mobile` through the public Supabase Data API. All application and financial reads/writes pass through the GitHub-first FastAPI service, which revalidates the authenticated identity, active account, approved device, exact permission, authoritative PostgreSQL state, and protected operation controls.

Migration `0109_mvp_private_schema_barrier.sql` preserves this boundary for current and future tables, sequences, functions, and procedures. It revokes public-client schema/object access without changing database ownership, RLS state, backend-owner access, or financial rules.

## Live read-only evidence — 2026-09-03

The connected Supabase project reported an RLS-disabled advisory for 124 lending/accounting tables. RLS-disabled is an important warning if a schema is exposed, but it does not by itself prove that a role can reach a private schema.

Read-only privilege checks were therefore run against the connected project before any mutation:

- `anon`, `authenticated`, and `service_role` had no `USAGE` on `core`, `lending`, `accounting`, or `mobile`;
- `information_schema.role_table_grants` returned no table grants for those roles in the four schemas;
- `has_table_privilege` reported zero selectable or writable relations for `anon` and `authenticated` across the four schemas;
- `service_role` likewise had zero direct relation reads in those schemas;
- no schema-specific default ACL row existed for the four schemas.

The current project was therefore already fail-closed for direct public-client access at the time of review. Migration 0109 is defense in depth and a permanent regression boundary, not an emergency repair of confirmed public table access.

## Why RLS is not bulk-enabled here

Blindly enabling RLS on every existing financial table without matching policies could block the FastAPI database path or create inconsistent access behavior. The MVP instead preserves server-only schema access. Any future Data API exposure requires a separate reviewed design with:

1. explicit exposed-schema configuration;
2. least-privilege table grants;
3. RLS enabled before client access;
4. ownership predicates and `WITH CHECK` for writes;
5. no authorization from user-editable metadata;
6. tests for cross-client, cross-role, and cross-tenant denial.

## Remaining Supabase hardening

The Supabase security advisor also reports database functions with mutable `search_path`, `pg_net` in `public`, and leaked-password protection disabled. Those findings remain open security work. They are not bypassed by this MVP and must be resolved before production release.

## Validation and application rule

Run the disposable validator only against a loopback database whose name contains `test`, `mvp`, or `disposable`:

```powershell
$env:SPINA_ALLOW_DISPOSABLE_DATABASE = "1"
$env:GILBIC_TEST_DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:5432/spina_mvp_test"
python tools/run_mvp_private_schema_barrier_validation.py
```

The validator intentionally creates an unsafe baseline, applies migration 0109, verifies current and future object denial through `has_schema_privilege`, `has_table_privilege`, `has_sequence_privilege`, and `has_function_privilege`, proves the database owner still has access, then cleans up the disposable schemas and roles.

Do not apply migration 0109 to a protected project until the exact migration passes disposable PostgreSQL validation and the target project is backed up. Application should be through the repository migration process, not by copying an incomplete subset into the dashboard SQL editor.
