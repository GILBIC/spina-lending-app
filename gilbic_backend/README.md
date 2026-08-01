# Gilbic Backend

This is the GitHub-first FastAPI backend for Gilbic.

## Current foundation

- FastAPI application factory
- PostgreSQL/Supabase connection through `GILBIC_DATABASE_URL`
- liveness endpoint: `/health/live`
- database readiness endpoint: `/health/ready`
- API metadata endpoint: `/api/v1/meta`
- private `core`, `lending`, and `mobile` schemas
- users, roles, permissions, devices, clients, loan types, and loans
- Supabase Auth password/session integration
- public Client-only registration
- username-or-email login compatibility for the Flutter app
- server-side roles and permissions
- device registration and revocation records
- per-request active-device enforcement for authenticated APIs
- access-token refresh, `/me`, and logout endpoints
- management-only account invitation, role, account-status, and device administration
- immutable audit events for account and device administration actions
- one-time local/server CLI for bootstrapping the first Management account
- Supabase/PostgreSQL-backed collector routes
- atomic and idempotent payment, ADV, and PASS collection writes
- exact decimal balance and receipt responses

## Local installation

The collection contract is a shared package in this monorepo. Install it before
the backend:

```bash
python -m pip install -e ./spina_backend_mobile
python -m pip install -e './gilbic_backend[test]'
```

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

`GILBIC_SUPABASE_SECRET_KEY` is required only by trusted FastAPI/server tooling that sends staff invitations through the Supabase Auth Admin API. It must never be placed in Gilbic Flutter, browser JavaScript, a public repository, logs, or screenshots.

The backend never uses Supabase `user_metadata` as an authorization source. Application roles and permissions remain authoritative in private `core.*` tables.

## First Management bootstrap

The normal management API cannot create the very first administrator because every management route already requires authenticated management permission. Gilbic therefore provides a local/server-only bootstrap command.

After installing the backend in a trusted environment with the required environment variables, run:

```powershell
gilbic-bootstrap-management `
  --username manager.one `
  --email manager@example.com `
  --full-name "Manager One" `
  --confirm-first-management
```

Bootstrap rules:

- there is no public bootstrap HTTP endpoint
- no password is accepted on the command line
- Supabase Auth sends an invitation so the administrator sets their own password
- the command uses a PostgreSQL advisory transaction lock to prevent two concurrent first managers
- the database re-checks that no Management role exists before committing
- the initial account is stored as `pending` until the invited administrator completes Auth setup and signs in
- the bootstrap event is written to `core.audit_logs` with no fake actor identity
- if the PostgreSQL write fails after an Auth invitation is created, Gilbic removes the newly invited Auth user before reporting failure
- once any Management account exists, the bootstrap command refuses to create another one; all additional staff must use the authenticated management API

`GILBIC_STAFF_INVITE_REDIRECT_URL`, when set, must be included in Supabase Auth's allowed Redirect URLs. Otherwise Supabase falls back to the configured Site URL.

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

## Per-request device enforcement

Login registers or refreshes an app installation in `core.devices`. Authenticated protected requests must then send both:

```text
Authorization: Bearer <access-token>
X-Device-Id: <raw app installation ID>
```

FastAPI validates the bearer token with Supabase Auth, loads the authoritative Gilbic account, hashes `X-Device-Id`, and requires a matching active device row for that account. The raw installation ID is request-only and is not stored in PostgreSQL collection records.

Enforcement rules:

- a missing or malformed device header is rejected
- an unknown installation must sign in before using protected APIs
- a revoked installation is rejected immediately even when its access token has not expired
- a locked or inactive account is rejected before permission checks
- successful protected requests update the device's `last_seen_at`
- refresh requests also require an active registered device, preventing a revoked installation from extending its session
- collector route, collection, employee, client, and management endpoints use the shared device guard

Logout remains available with a valid bearer session so a client can remove its local session even if device state changed.

## Collector route

```text
GET /api/v1/collector/routes/today
GET /api/mobile/v1/collector/routes/today
```

The route is filtered by server-side area assignments. Each loan entry includes an optimistic `route_revision` plus clear readiness fields:

- `can_collect_mobile`
- `can_enter_payment`
- `collection_message`

A collector can still see a loan that requires SPINA desktop handling. The API marks it as **Needs review** or **Desktop only** instead of silently removing it from the route.

## Official mobile collections

```text
POST /api/v1/collector/collections
POST /api/mobile/v1/collector/collections
```

Required headers:

```text
Authorization: Bearer <access-token>
Idempotency-Key: <one UUID for the draft>
X-Client-Transaction-Id: <the same UUID>
X-Device-Id: <registered installation ID>
X-Gilbic-Contract-Version: gilbic-collection-v1
```

One PostgreSQL transaction contains all official effects:

- payment, ADV, or PASS transaction
- authoritative `loan_collection_state` update
- receipt number
- loan status change to `paid` when the balance reaches zero
- audit event
- replayable idempotency result

If any step fails, all writes roll back together. Retrying the same request and UUID returns the original receipt without creating another payment. Reusing the UUID for changed data returns a conflict.

Additional safeguards:

- the current route revision must match the locked loan state
- one device sequence number can be used only once
- only one PASS can be recorded for a loan and date
- PASS is rejected when that date is already covered by ADV
- an amount above the official remaining balance is rejected
- only reconciled loan state can be changed
- raw installation IDs are not persisted
- money is returned as exact two-decimal strings

### Enabling a loan type safely

Mobile writes are disabled by default. A loan type must explicitly include:

```json
{
  "mobile_collections_enabled": true,
  "mobile_balance_mode": "direct_remaining_balance"
}
```

`direct_remaining_balance` means the reconciled server balance can safely be reduced by the accepted payment amount. Do not enable this for a loan type whose payment must be split between principal, interest, penalties, or another schedule unless that allocation has already been verified.

For 7x7, the fixed daily interest rule remains protected. Mobile payment and ADV should stay disabled until the dedicated 7x7 allocation strategy is implemented and tested against SPINA desktop results. PASS can be enabled only after the loan type itself is approved for mobile use.

User-facing outcomes use plain language:

- **Payment saved.**
- **ADV saved.**
- **PASS saved.**
- **Already recorded. No duplicate payment was created.**
- **Refresh the route and review the entry.**
- **Use the SPINA desktop app for this loan type.**

## Management administration routes

These routes require an authenticated active device and the appropriate server-side management permission.

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

1. Build the collector collection form with clear Payment, ADV, and PASS modes.
2. Add an encrypted offline outbox that reuses the original idempotency key and device sequence.
3. Implement and verify the dedicated 7x7 payment allocation strategy.
4. Add client, employee, and management mobile screens.
5. Add accounting, billing, taxation, risk, and compliance APIs.

The old local FastAPI project is not required for this backend. Features can be migrated into this backend one by one after review.
