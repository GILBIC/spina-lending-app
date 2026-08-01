# Gilbic Mobile

Gilbic is the Flutter mobile application for the SPINA lending platform. One
codebase supports Client, Collector, Employee, and Management experiences while
FastAPI remains the only boundary allowed to read or write official lending data.

## Current milestone

The Collector experience now includes:

- Supabase Auth-backed login with backend-assigned roles and permissions
- a permanent app-generated installation ID stored in secure storage
- per-request active-device enforcement through `X-Device-Id`
- an assigned daily route with server balances and route revisions
- a SQLCipher-encrypted offline route snapshot
- clear **Online route** and **Offline copy** labels
- an online-only Payment / ADV / PASS entry form
- confirmation before submission
- one UUID idempotency key reused after an uncertain network result
- a persistent per-device collection sequence
- accepted, duplicate, conflict, and rejected server results
- official receipt number and balance display from FastAPI
- automatic route refresh after a successful entry

The encrypted payment outbox remains disabled. Offline route copies are
read-only, and 7x7 collection remains blocked until the dedicated allocator is
implemented and verified.

## Prerequisites

- Flutter 3.44.7
- Android Studio and Android SDK for Android builds
- macOS and Xcode for final iOS builds

Generate Android and iOS platform folders from PowerShell:

```powershell
cd gilbic_mobile
.\tool\bootstrap_platforms.ps1
```

## FastAPI configuration

The GitHub-first backend exposes these mobile endpoints:

```text
POST /api/mobile/v1/auth/register
POST /api/mobile/v1/auth/login
POST /api/mobile/v1/auth/refresh
GET  /api/mobile/v1/auth/me
POST /api/mobile/v1/auth/logout
GET  /api/mobile/v1/collector/routes/today
POST /api/mobile/v1/collector/collections
```

Android emulator example:

```powershell
flutter run `
  --dart-define=GILBIC_API_URL=http://10.0.2.2:8000
```

Physical phone on the same network:

```powershell
flutter run `
  --dart-define=GILBIC_API_URL=http://YOUR-COMPUTER-IP:8000
```

Production must use HTTPS. PostgreSQL passwords and Supabase secret keys must
never be placed in Flutter or committed to GitHub.

## Online collection flow

1. The collector opens an online route.
2. Gilbic verifies the account has `collection.create` permission.
3. The route entry must contain an active loan, route revision, and server
   approval for mobile collection.
4. Offline route copies and 7x7 loans remain disabled.
5. The collector selects Payment, ADV, or PASS and confirms the entry.
6. Gilbic creates one UUID transaction key and reserves one device sequence.
7. FastAPI validates the session, device, permission, area, client, loan,
   route revision, idempotency key, device sequence, and calculation mode.
8. FastAPI atomically writes the collection, official balance, receipt, audit
   event, and replayable idempotency result.
9. Gilbic shows the server result and refreshes the route after success.

A network failure does not prove rejection. Retrying without changing the form
reuses the same draft, transaction key, recorded time, and device sequence. If
the collector edits the entry, Gilbic discards the uncertain draft and creates
a new transaction identity on the next submission.

## Safety boundaries

- FastAPI decides roles, permissions, route assignment, balances, receipts,
  loan status, ADV/PASS rules, and calculation support.
- Flutter never calculates or overwrites an official balance.
- Public registration cannot create Collector, Employee, or Management roles.
- The installation ID is app-generated; Gilbic does not collect IMEI, serial
  number, MAC address, advertising ID, or phone number as a device key.
- The backend stores the registered-device record rather than the raw
  installation ID in collection transactions.
- Cached routes remain read-only.
- Unsupported loans remain visible but cannot be submitted from mobile.
- 7x7 Payment, ADV, and PASS remain disabled in mobile until dedicated rules
  are verified.
- Automatic retry and offline collection synchronization remain disabled.

## Validation

From `gilbic_mobile`:

```powershell
flutter pub get
flutter analyze --fatal-infos
flutter test
```

The owner-only GitHub workflow runs the same analysis and tests against the
exact pull-request head on the Windows self-hosted runner.

## Next milestone

1. Build an encrypted offline collection outbox that preserves the original
   transaction key, payload, and device sequence.
2. Add explicit manual retry and conflict-resolution screens.
3. Implement and verify the dedicated 7x7 allocator before enabling 7x7.
4. Add collector end-of-day totals and cash accountability.
