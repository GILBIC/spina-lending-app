# Gilbic Backend

This is the GitHub-first FastAPI backend for Gilbic.

## Current foundation

- FastAPI application factory
- PostgreSQL/Supabase connection through `GILBIC_DATABASE_URL`
- liveness endpoint: `/health/live`
- database readiness endpoint: `/health/ready`
- API metadata endpoint: `/api/v1/meta`
- private `core` and `lending` schemas
- users, roles, permissions, devices, clients, loan types, and loans
- Supabase Auth password/session integration
- public Client-only registration
- username-or-email login compatibility for the Flutter app
- server-side roles and permissions
- optional device registration and revocation checks
- access-token refresh, `/me`, and logout endpoints

## Required environment variables

The backend does not commit live database or authentication credentials.

```text
GILBIC_DATABASE_URL=postgresql://...
GILBIC_SUPABASE_URL=https://<project-ref>.supabase.co
GILBIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
```

`GILBIC_SUPABASE_PUBLISHABLE_KEY` is the Supabase publishable client key. Never put a Supabase secret/service-role key in Gilbic Flutter.

## Authentication routes

Canonical routes:

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/refresh
GET  /api/v1/auth/me
POST /api/v1/auth/logout
```

Compatibility aliases are also provided under `/api/mobile/v1/auth/*` so the existing Flutter login contract does not need to change immediately.

Public registration always creates a `client` role. Collector, Employee, and Management roles are assigned only from trusted server-side administration.

Supabase Auth owns password hashing and authentication sessions. The private Gilbic `core.users`, `core.user_roles`, `core.role_permissions`, and `core.devices` tables remain authoritative for application access.

## Next order

1. Give Flutter a stable installation/device identifier during login.
2. Add management-only account provisioning and role assignment.
3. Add collector route API against the new database.
4. Integrate the idempotent collection package in `spina_backend_mobile/`.
5. Add client, employee, and management APIs.
6. Add accounting, billing, taxation, risk, and compliance APIs.

The old local FastAPI project is not required for this backend. Features can be migrated into this backend one by one after review.
