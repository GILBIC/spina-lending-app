# Cross-Platform Four-Role MVP Design

## Status

Approved by Management on 2026-09-03 through the instruction to update and start, with the added non-negotiable requirement that Client, Employee, Collector, and Management must each receive a usable signed-in experience.

## Goal

Deliver one demonstrable SPINA MVP from the existing repository with a working hosted web/PWA surface, an installable Windows app-mode experience, existing Flutter Android/iOS builds, and one FastAPI/Supabase/PostgreSQL backend. The MVP is for controlled demo and acceptance data only; it is not legal-book or real-money production authorization.

## Delivery strategy

The three-day constraint requires reuse rather than rebuilding SPINA. The existing `gilbic_backend` remains the only application and financial API. The existing `gilbic_mobile` Flutter application remains the Android/iOS client. A new dependency-light responsive PWA provides the fastest usable Web and PC surface for all four roles and is installed on Windows through Microsoft Edge/Chrome app mode. The PWA calls the same canonical `/api/v1/...` endpoints as Flutter and never connects directly to lending or accounting tables.

The PWA is intentionally a separate presentation adapter, not a second backend or a second set of lending rules. Its responsibilities are authentication, role-aware navigation, safe form collection, clear result display, and session recovery. FastAPI/PostgreSQL remain authoritative for permissions, balances, receipts, route ownership, allocations, remittances, approvals, and audit evidence.

## Target surfaces

### Web and PC

Create `spina_portal/` as a static progressive web application containing:

- responsive login and optional Client registration;
- a shared shell with role, account, connectivity, refresh, and logout controls;
- Client dashboard and self-service views;
- Employee dashboard and permitted work views;
- Collector route, payment/PASS entry, receipt result, route refresh, and remittance links;
- Management overview, loan search, registration/renewal/support queues, alerts, and protected review links;
- installable manifest and service worker;
- a Windows PowerShell installer that creates an app-mode desktop shortcut to the configured portal URL.

The PWA uses browser `sessionStorage` for access/refresh session payloads and a privacy-preserving random device identifier in `localStorage`. No Supabase secret, service-role key, PostgreSQL URL, or financial record is stored in browser configuration.

### Android and iOS

Retain `gilbic_mobile/` as the native mobile client. The MVP adds repeatable platform/bootstrap and build documentation, but does not replace the existing role dashboards or protected repositories. Android must produce a review APK. iOS must produce a generated Xcode project and pass shared Flutter analysis/tests; native build/signing evidence is recorded only when macOS/Xcode and Apple credentials are available.

### Backend

Expose the existing `gilbic_backend.main:app` through a Vercel-compatible ASGI entrypoint. Add root dependency/config files and routing so the static PWA and `/api/v1/...` FastAPI routes can be deployed from the same repository or as two linked projects. The backend must keep:

- Supabase Auth session validation;
- PostgreSQL application role/permission authority;
- active-device enforcement;
- canonical `/api/v1/...` endpoints;
- server-side Regular/7x7 rules;
- idempotent Collector collection submission;
- explicit Management-protected review/posting boundaries;
- health and readiness endpoints.

## Four-role minimum usability

### Client

A Client can:

1. register an account for Management linking, or sign in with an approved account;
2. view only their own profile, active/history loans, Regular and 7x7 values, payment timeline, official receipts, notifications, and renewal/support status;
3. submit a renewal request or support request where the existing protected endpoint permits it;
4. view GCash instructions or the current provider-neutral disabled/coming-soon state.

A proof upload or checkout page never creates an official payment by itself.

### Employee

An Employee can:

1. sign in and see a dedicated Employee dashboard rather than a generic role placeholder;
2. open account/device state and notifications;
3. see only server-permitted office/support/remittance functions;
4. use any already-connected workflow granted by exact permission;
5. see unavailable HR/payroll/attendance functions honestly labeled unavailable rather than simulated.

Employee accounts never inherit Collector collection authority or Management approval/posting authority.

### Collector

A Collector can:

1. sign in on an approved device;
2. load the authoritative assigned route with area grouping and separate Regular/7x7 rows;
3. record an online Payment or unable-to-pay/PASS entry using the existing collection contract;
4. receive the official receipt/balance result and refresh the route;
5. identify entries still requiring attention and open remittance functions already supported by the backend;
6. see a clear read-only/offline state when the API is unavailable.

The web/PWA Collector flow uses a persistent per-device monotonic sequence and a UUID idempotency key. It does not automatically retry an uncertain financial request. A user must refresh/reconcile before another submission.

### Management

Management can:

1. sign in and load the server-authoritative portfolio/collection/custody/activity overview;
2. search/review clients and loans through existing Management endpoints;
3. review Client registrations, renewals, support, remittance, staff/device, and alert queues when exact permissions are present;
4. open existing protected accounting/review surfaces without introducing simplified bypass actions;
5. distinguish implemented, blocked, and unavailable modules.

## Security boundary

The connected Supabase project currently reports many lending/accounting tables without RLS. The MVP therefore must not use Supabase Data API table reads/writes from public clients. Before any demo identities or data are used, the deployment must apply or verify a reviewed private-schema barrier that revokes `anon` and `authenticated` usage/table/sequence privileges for `core`, `lending`, `accounting`, and `mobile`, while preserving backend/database-owner access.

Do not bulk-enable RLS without matching policies because that could break the existing backend. The immediate MVP control is private-schema revocation plus server-only access. The broader function `search_path`, extension placement, and leaked-password-protection findings remain separately tracked security hardening work.

## Data and environment

Only disposable/demo records are allowed. Environment secrets stay in deployment configuration:

- `GILBIC_DATABASE_URL`
- `GILBIC_SUPABASE_URL`
- `GILBIC_SUPABASE_PUBLISHABLE_KEY`
- `GILBIC_SUPABASE_SECRET_KEY`
- `GILBIC_CORS_ORIGINS`
- optional GCash provider variables, left disabled for this MVP

The browser receives only the public portal configuration: API base URL, environment label, and app version.

## Error handling

- 401: clear the session and return to login with an expired-session message.
- 403 `device_approval_required`: show that Management approval is needed; do not retain tokens.
- Other 403: display permission-denied copy without exposing server internals.
- 409 on financial writes: show the backend conflict and require route refresh/reconciliation.
- 422: show safe validation detail and keep the form editable.
- 503 readiness/auth/database: switch to read-only/unavailable state and offer retry.
- Network uncertainty after a Collector write: freeze the form, preserve the request identity, and require authoritative refresh before another attempt.

## Verification

The MVP is accepted only with fresh exact-commit evidence for:

- backend import and health smoke;
- FastAPI route/OpenAPI smoke;
- PWA static tests for login/session/role routing and Collector request formation;
- backend role/permission tests already owned by the repository;
- Flutter analysis and affected role tests;
- web root returning the login shell rather than 404;
- API health returning 200 and readiness reflecting database state;
- anonymous/public direct access to private financial schemas rejected;
- one demo cross-role flow: Collector payment -> official backend receipt -> Client timeline visibility -> Management overview/collection visibility;
- Windows app-mode installer generation;
- Android APK generation;
- iOS shared-code evidence, with native/signing limitations stated exactly.

## Explicit exclusions

This MVP does not authorize real borrower data, real cash collection, legal-book posting, tax filing, production accounting close, real GCash settlement, offline financial writes, Play Store/App Store approval, or a claim that all SPINA V1 release gates are complete.
