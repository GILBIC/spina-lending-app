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
- device registration and revocation records
- access-token refresh, `/me`, and logout endpoints
- management-only account invitation, role, account-status, and device administration
- immutable audit events for account and device administration actions

## Required environment variables

The backend does not commit live database or authentication credentials.

```text
GILBIC_DATABASE_URL=postgresql://...
GILBIC_SUPABASE_URL=https://<project-ref>.supabase.co
GILBIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
GILBIC_SUPABASE_SECRET_KEY=sb_secret_...
GILBIC_STAFF_INVITE_REDIRECT_URL=https://your-app.example/set-password
```

`GILBIC_SUPABASE_PUBLISHABLE_KEY` is used for normal authentication requests.

`GILBIC_SUPABASE_SECRET_KEY` is required only by trusted FastAPI server code that sends staff invitations through the Supabase Auth Admin API. It must never be placed in Gilbic Flutter, browser JavaScript, a public repository, logs, or screenshots.

The backend never uses Supabase `user_metadata` as an authorization source. Application roles and permissions remain authoritative in private `core.*` tables.

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

## Management administration routes

These routes require an authenticated account with the appropriate server-side management permission.

```text
GET   /api/v1/management/accounts
POST  /api/v1/management/accounts/invite
PATCH /api/v1/management/accounts/{user_id}/role
PATCH /api/v1/management/accounts/{user_id}/status
GET   /api/v1/management/accounts/{user_id}/devices
PATCH /api/v1/management/devices/{device_id}/status
```

Staff invitation rules:

- management supplies username, email, full name, and one staff role
- allowed invited roles are `collector`, `employee`, or `management`
- no password is collected by management
- Supabase sends the invite email and the invited person completes password setup
- roles are stored in `core.user_roles`, not Auth metadata
- the initiating management user is recorded in `core.audit_logs`

Account safety rules:

- management cannot demote its own account through the role endpoint
- management cannot lock or disable its own account through the status endpoint
- management cannot revoke a device belonging to its own current account through the device endpoint
- device records never expose the stored installation-ID hash to API clients

## Next order

1. Add per-request device enforcement so a revoked installation is rejected without waiting for the next login.
2. Add the collector route API against the new database.
3. Integrate the idempotent collection package in `spina_backend_mobile/`.
4. Add client, employee, and management mobile screens.
5. Add accounting, billing, taxation, risk, and compliance APIs.

The old local FastAPI project is not required for this backend. Features can be migrated into this backend one by one after review.
