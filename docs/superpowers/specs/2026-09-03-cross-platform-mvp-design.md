# SPINA Three-Day Cross-Platform MVP Design

**Status:** Management approved on 2026-09-03 (Asia/Manila)

## Goal

Produce a demonstrable SPINA MVP from one exact GitHub revision that provides a working Web experience, Windows PC application, Android application, iOS project/build path, and one deployed FastAPI backend connected to the existing Supabase Auth and PostgreSQL authority.

The three-day target is a controlled MVP and acceptance package. It is not a legal go-live, production accounting close, app-store approval, real-money payment release, or claim that every historical Desktop feature has been migrated.

## Delivery boundary

The MVP is successful when all of the following are true from one exact commit:

1. The Web build opens a real SPINA login surface rather than a placeholder or 404.
2. The Windows build launches the same role-aware application shell.
3. An Android debug/review APK launches and reaches the authenticated shell.
4. The iOS runner is generated and the shared Dart tests pass; native Xcode build evidence is recorded only from macOS/Xcode.
5. The FastAPI backend exposes working liveness, readiness, metadata, authentication, and the bounded role workflows used by the MVP.
6. Management, Employee, Collector, and Client demo identities receive server-derived roles and permissions.
7. A demo Collector can load an assigned route and record an online payment through the existing protected collection endpoint.
8. The corresponding demo Client can read the resulting official transaction/receipt state, and Management can read the resulting collection state.
9. No browser, Windows, Android, or iOS client receives a Supabase secret/service-role key or direct write authority over financial tables.
10. Anonymous and ordinary authenticated Supabase Data API roles cannot directly read or mutate the private `core`, `lending`, `accounting`, or `mobile` schemas used by the application.

## Recommended architecture

### Shared client

Use the existing `gilbic_mobile/` Flutter codebase for four targets:

- Web/PWA
- Windows PC
- Android
- iOS

The user experience remains role-specific while reusing one theme, authentication flow, API models, permission checks, and business terminology. Responsive presentation may differ by screen size, but official values, permission meanings, protected confirmations, and workflow outcomes do not.

### Backend and data

Use the existing `gilbic_backend/` FastAPI application as the only application API. FastAPI validates Supabase Auth sessions, loads application roles and permissions from PostgreSQL, enforces approved-device policy where applicable, and invokes the existing protected lending/accounting repositories.

Supabase responsibilities:

- Supabase Auth: passwords, access/refresh sessions, identity lifecycle.
- Supabase PostgreSQL: authoritative application, lending, collection, audit, and accounting records.
- Supabase Storage: evidence uploads only where an existing protected workflow requires them.

Flutter and browser code never connect directly to private financial tables. They call FastAPI over HTTPS.

### Deployment

Deploy the FastAPI service from a dedicated Vercel project/entrypoint with environment-scoped secrets. Deploy the Web client separately from a verified Flutter Web build artifact. Windows, Android, and iOS builds use the same API base URL supplied with `--dart-define=GILBIC_API_URL=...`.

The current Vercel repository deployment that returns 404 is not treated as a working website. The MVP deployment must contain an actual backend or Web artifact and pass HTTP smoke tests.

## Platform storage policy

The current mobile route cache uses SQLCipher. That security behavior remains on Android and iOS.

- Android/iOS: encrypted SQLCipher route cache plus secure key storage.
- Web/Windows: online-only in-memory route cache for the MVP.
- Every platform: cached information is presentation-only and never becomes the source of an official balance or receipt.
- Every platform: Collector financial writes are blocked when the authoritative API is unavailable.

A platform factory selects the correct cache without importing mobile-only SQLCipher code into the Web compilation unit.

## Role scope

### Management

Include the existing server-authoritative overview, client/loan search, collection/remittance status, renewals, registration review, staff/device view, alerts/activity, and read-only accounting summary. Existing protected actions retain their exact evidence/review/confirmation controls. The MVP does not add a simplified parallel accounting writer.

### Employee

Include the grouped Employee dashboard, notifications, account/device state, and only those office/remittance/support functions already backed by FastAPI and granted by exact server permission. Unconnected HR, payroll, attendance, or office modules are labelled unavailable and do not create local records.

### Collector

Include assigned route, saved area ordering, Regular and 7x7 distinction, online Payment/ADV/PASS entry, official result/receipt, Master Review, and remittance status. No offline write queue is introduced. Combined Regular plus 7x7 collection remains server-authoritative and atomic where the existing endpoint is enabled.

### Client

Include own-account-only loan list/history, separate Regular and 7x7 balances, payment timeline, official receipts, notifications, renewal request/status, support, and profile/security. Payment proof or checkout initiation never creates an official payment. Direct GCash remains disabled or clearly marked unavailable until provider settlement verification exists.

## Security controls

### Client credentials

Public Flutter and browser builds may receive only public configuration such as the API URL. They must not receive:

- Supabase secret/service-role key
- PostgreSQL connection string
- webhook secret
- provider API secret
- private signing material

### Supabase Data API barrier

The existing architecture treats `core`, `lending`, `accounting`, and `mobile` as private server-owned schemas. The MVP therefore adds a reviewed migration that revokes schema/table/sequence access for `anon` and `authenticated` across those schemas and applies matching default privileges.

The migration is committed and validated against a disposable database before any protected/live application. It is not auto-applied to production merely by opening or merging a pull request.

### Authorization

- Supabase identity alone is insufficient.
- FastAPI resolves the canonical application user, role, permissions, account status, and applicable device state.
- UI hiding is presentation only; every protected endpoint enforces authorization again.
- Client records are restricted to the linked borrower identity.
- Employee, Collector, Client, and Management data must not cross role/tenant boundaries.

### Financial integrity

- PostgreSQL and existing protected server rules remain authoritative.
- No Flutter-derived balance, allocation, receipt, journal, tax, ECL, or period-close result is official.
- Collection retries preserve the original idempotency identity after an uncertain result.
- `automatic_source_posting=false` remains unchanged.
- Demo data is labelled and isolated from legal/production books.

## Backend entrypoint and configuration

Add a deployable ASGI entrypoint that imports `gilbic_backend.main:app` without duplicating router registration. The deployment declares the backend package dependencies and exposes:

- `GET /health/live`
- `GET /health/ready`
- `GET /api/v1/meta`

Configuration continues through `GILBIC_` environment variables. CORS allows only explicit local-development and deployed Web origins. Wildcard credentialed CORS is prohibited.

## Error handling

All clients show simple, role-appropriate states for:

- initial loading
- no data
- offline/unreachable API
- expired session
- revoked/unapproved device
- permission denied
- update required
- stale route or uncertain financial result

A temporary network failure does not destroy a still-valid session. A terminal authentication/device failure clears the session and role-scoped local cache. A financial timeout never assumes success and never generates a replacement idempotency identity without authoritative reconciliation.

## Verification strategy

### Backend

- Unit/API tests for deployable entrypoint and health routes.
- Existing authentication, role, device, collection, client-isolation, receipt, and Management tests.
- Disposable PostgreSQL proof for the Data API access barrier.
- OpenAPI route uniqueness and import smoke test.

### Flutter

- Platform-policy unit tests proving Android/iOS choose encrypted cache and Web/Windows choose online-only memory cache.
- Existing complete Flutter test suite.
- Strict analyzer and formatter checks.
- Web compilation smoke.
- Windows compilation smoke on the self-hosted Windows runner.
- Android APK build and ABI verification.
- Shared Android/iOS target-platform widget tests.
- Native iOS build only from macOS/Xcode; absence of macOS evidence is reported rather than inferred.

### End-to-end

Use disposable/demo records to prove:

1. Management, Employee, Collector, and Client login.
2. Role-specific navigation and API denial outside permission.
3. Collector route load.
4. One protected demo payment.
5. Official receipt/balance response.
6. Client sees its own resulting timeline/receipt.
7. Management sees the resulting collection state.
8. Another client and a generic Employee cannot access the transaction.

## Three-day sequence

### Day 1 — foundation

- Isolated MVP branch and Draft PR.
- Approved design and implementation plans.
- Platform-safe cache/storage composition.
- Web/Windows runner generation and build workflows.
- Deployable FastAPI entrypoint and HTTP smoke tests.
- Reviewed private-schema access-barrier migration and disposable tests.

### Day 2 — vertical slice

- Hosted backend configuration.
- Four controlled demo identities and labelled demo records.
- Role login/navigation verification.
- Collector route/payment/receipt flow.
- Client own-timeline/receipt view.
- Management resulting-state view.

### Day 3 — release evidence

- Complete backend and Flutter suites.
- Web, Windows, Android builds.
- iOS shared-code proof and native evidence when macOS is available.
- Deployment smoke tests.
- Exact commit, version, hashes, demo instructions, limitations, rollback notes, and synchronized GitHub/Notion/Create State checkpoint.

## Explicit non-goals

The MVP does not include real production borrowers, actual legal-book opening entries, actual tax filings, production period close, real GCash settlement, offline financial posting, full HR/payroll, migration of every legacy Tkinter screen, store approval, or an unsupported claim of signed iOS distribution.

## Authority and change control

This MVP branch is stacked on the exact PR #392 head to reuse the latest reviewed Mobile work. It remains Draft and must not be merged, deployed to a production environment, or used for real financial activity merely because an MVP test passes.

GitHub code, repository documentation, FastAPI/PostgreSQL state, CI evidence, and retained approvals remain authoritative. Notion and Create State are continuity indexes only.