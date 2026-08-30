# Gilbic Mobile

Gilbic is the Flutter mobile application for the SPINA lending platform. One
codebase supports Client, Collector, Employee, and Management experiences while
FastAPI remains the only boundary allowed to read or write official lending data.

## Current milestone

One Flutter codebase now provides separate Management, Employee, Collector,
and Client experiences for Android and iOS. The shared SPINA design system keeps
the approved pink-and-white identity while allowing platform-native navigation,
safe-area, keyboard, and title behavior that does not change business rules.

Current role surfaces include:

- Management operational overview, protected review queues, reports,
  accounting launchers, people/access, notifications, and device administration
  according to exact server permissions.
- Employee workday, pay/request, office-function, update, account, and
  permission-scoped remittance groupings. Functions without an authoritative
  backend remain clearly marked unavailable.
- Collector online route, Regular and parity-approved 7x7 collection, ADV/PASS,
  corrections, other-area work, remittance/custody, official receipts, and a
  SQLCipher-encrypted read-only offline route copy.
- Client own-record loan status, balances, schedules/history, payments and
  official receipts, renewal status, support, notifications, and account/device
  security. Direct GCash payment is a non-interactive placeholder until the
  protected Xendit integration is approved and connected.

The encrypted payment outbox remains disabled. Offline route copies are
read-only, and no financial write is queued or automatically submitted while
offline.

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
4. Offline route copies remain disabled for writes. Only loans explicitly
   enabled by the protected server collection gate can be submitted.
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
- 7x7 Payment, ADV, and PASS use the same parity-proven server allocator and
  remain subject to the protected server feature gate.
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

Follow the frozen order in GitHub Master Issue #296:

1. Finish CA6 iOS UI parity evidence on macOS/Xcode without redesigning the
   shared Android role experience.
2. Complete the remaining CB Management and Employee authoritative workflows.
3. Run Collector, Client, cross-role, and cross-platform integrity acceptance.
4. Produce production-signed Android/iOS builds only from the exact validated
   release commit under the documented release and rollback procedures.

An encrypted offline financial-write outbox remains V1.1+ scope.
