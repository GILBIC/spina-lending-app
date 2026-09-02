# Gilbic Cross-Platform App

Gilbic is the Flutter application for the SPINA lending platform. One codebase
supports Client, Collector, Employee, and Management experiences on Web,
Windows, Android, and iOS while FastAPI remains the only boundary allowed to
read or write official lending data.

## Current MVP milestone

The controlled cross-platform MVP extends the existing Android/iOS application
to Web and Windows without creating a second business or accounting path. The
shared SPINA design system keeps the approved pink-and-white identity while
allowing platform-appropriate navigation, safe areas, keyboard behavior, and
responsive layouts that do not change business rules.

Current role surfaces include:

- Management operational overview, protected review queues, reports,
  accounting launchers, people/access, notifications, and device administration
  according to exact server permissions.
- Employee workday, pay/request, office-function, update, account, and
  permission-scoped remittance groupings. Functions without an authoritative
  backend remain clearly marked unavailable.
- Collector online route, Regular and parity-approved 7x7 collection, ADV/PASS,
  corrections, other-area work, remittance/custody, official receipts, and a
  read-only offline route copy where supported.
- Client own-record loan status, balances, schedules/history, payments and
  official receipts, renewal status, support, notifications, and account/device
  security. Direct GCash payment remains non-interactive until a protected
  provider integration is approved and connected.

Collector financial writes are online-only on every platform. Android and iOS
retain the SQLCipher-encrypted route snapshot. Web and Windows use an in-memory,
online-session route snapshot for the MVP; it is cleared when the application
process ends and never becomes an official balance or receipt source.

## Prerequisites

- Flutter stable compatible with Dart `>=3.10.0 <4.0.0`
- Android Studio and Android SDK for Android builds
- Visual Studio with Desktop development with C++ for Windows builds
- macOS and Xcode for native iOS builds
- A reachable SPINA FastAPI URL

Generate Android, iOS, Web, and Windows platform folders from PowerShell:

```powershell
cd gilbic_mobile
.\tool\bootstrap_platforms.ps1
```

Run the Web client locally:

```powershell
flutter run -d chrome `
  --dart-define=GILBIC_API_URL=http://127.0.0.1:8000
```

Run the Windows client locally:

```powershell
flutter run -d windows `
  --dart-define=GILBIC_API_URL=http://127.0.0.1:8000
```

Run an Android emulator against a backend on the host machine:

```powershell
flutter run -d emulator-5554 `
  --dart-define=GILBIC_API_URL=http://10.0.2.2:8000
```

Run a physical phone on the same network:

```powershell
flutter run `
  --dart-define=GILBIC_API_URL=http://YOUR-COMPUTER-IP:8000
```

Production and shared review environments must use HTTPS. PostgreSQL passwords,
Supabase secret/service-role keys, payment-provider secrets, and webhook secrets
must never be placed in Flutter or committed to GitHub.

## FastAPI configuration

The GitHub-first backend exposes protected endpoints such as:

```text
POST /api/mobile/v1/auth/register
POST /api/mobile/v1/auth/login
POST /api/mobile/v1/auth/refresh
GET  /api/mobile/v1/auth/me
POST /api/mobile/v1/auth/logout
GET  /api/mobile/v1/collector/routes/today
POST /api/mobile/v1/collector/collections
```

The API base URL is supplied at build or run time:

```powershell
flutter build web --release `
  --dart-define=GILBIC_API_URL=https://YOUR-SPINA-API

flutter build windows --release `
  --dart-define=GILBIC_API_URL=https://YOUR-SPINA-API
```

## Online collection flow

1. The Collector opens an online route.
2. Gilbic verifies `collection.create` and the exact route permission.
3. The route entry must contain an active loan, current route revision, and
   server approval for mobile collection.
4. Offline route copies remain disabled for writes.
5. The Collector selects Payment, ADV, or PASS and confirms the entry.
6. Gilbic creates one transaction UUID and reserves one device sequence.
7. FastAPI validates session, device, permission, area, client, loan, route
   revision, idempotency key, device sequence, and calculation mode.
8. FastAPI atomically writes the collection, official balance, receipt, audit
   event, and replayable idempotency result.
9. Gilbic displays the server result and refreshes authoritative route state.

A network failure does not prove rejection. Retrying an unchanged form preserves
the same draft, transaction key, recorded time, and device sequence. Editing the
entry creates a new intent only after the uncertain prior result is reconciled.

## Safety boundaries

- FastAPI decides roles, permissions, route assignment, balances, receipts,
  loan status, ADV/PASS rules, and calculation support.
- Flutter never calculates or overwrites an official balance.
- Public registration cannot create Collector, Employee, or Management roles.
- The installation ID is app-generated; Gilbic does not collect IMEI, serial
  number, MAC address, advertising ID, or phone number as a device key.
- Cached routes remain presentation-only and read-only while offline.
- Unsupported loans remain visible but cannot be submitted.
- Regular and 7x7 remain distinct and use their protected server allocators.
- Automatic retry and offline collection synchronization remain disabled.

## Validation

From `gilbic_mobile`:

```powershell
flutter pub get
flutter analyze --fatal-infos
flutter test
flutter build web --release `
  --dart-define=GILBIC_API_URL=https://mvp-api.invalid
flutter build windows --release `
  --dart-define=GILBIC_API_URL=https://mvp-api.invalid
```

Android and Windows build proof runs on a Windows-capable runner. Web builds run
on a GitHub-hosted Linux runner. Shared iOS Dart behavior is tested everywhere;
native iOS compilation and signing evidence require macOS/Xcode and approved
Apple credentials.

## MVP boundary

The cross-platform branch is demo-only until the exact commit passes backend,
database, role-isolation, Web, Windows, Android, and available iOS evidence. It
does not authorize production data, live financial posting, real GCash
settlement, signing, store submission, deployment, merge, or legal go-live.
