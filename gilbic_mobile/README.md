# Gilbic Mobile

Gilbic is the Android and iOS mobile application for the SPINA lending platform.
It uses one Flutter codebase with separate role experiences for clients,
collectors, employees, and management.

## Current milestone

- real username and password login through FastAPI
- backend-assigned role mapping
- encrypted token and session storage through platform secure storage
- bearer-authenticated requests
- read-only assigned collector route
- SQLCipher-encrypted SQLite route snapshots
- offline fallback to the last route saved for the authenticated collector
- online/offline source label and last-synchronized timestamp
- per-user cache removal during sign-out
- compatibility with standard SPINA `{success, message, data}` responses
- compatibility parsing for the existing direct staff-session response fields
- automated authentication, route, cache, loader, and widget tests

No official loan, payment, accounting, billing, or tax record is written by this
milestone. The encrypted database contains only a read-only downloaded route
snapshot. Payment synchronization remains disabled.

## Prerequisites

- Flutter SDK
- Android Studio and an Android SDK for Android builds
- macOS and Xcode for compiling iOS builds

## Generate Android and iOS platform folders

From PowerShell:

```powershell
cd gilbic_mobile
.\tool\bootstrap_platforms.ps1
```

The bootstrap command creates the mobile platform folders and applies the
SQLCipher Android ProGuard keep rule. The Flutter source is shared between both
platforms. Android builds can run on Windows. The final iOS build must be
compiled on macOS with Xcode.

## FastAPI configuration

The default planned mobile endpoints are:

```text
POST /api/mobile/v1/auth/login
POST /api/mobile/v1/auth/logout
GET  /api/mobile/v1/collector/routes/today
```

The existing SPINA backend source is not stored in this GitHub repository. If
its current paths are different, set them with Dart defines when launching or
building Gilbic. No Dart source change is required.

Android emulator example:

```powershell
flutter run `
  --dart-define=GILBIC_API_URL=http://10.0.2.2:8000 `
  --dart-define=GILBIC_LOGIN_PATH=/staff/login `
  --dart-define=GILBIC_LOGOUT_PATH=/staff/logout `
  --dart-define=GILBIC_COLLECTOR_ROUTE_PATH=/staff/collector-route/today
```

Physical phone on the same network:

```powershell
flutter run `
  --dart-define=GILBIC_API_URL=http://YOUR-COMPUTER-IP:8000 `
  --dart-define=GILBIC_LOGIN_PATH=/staff/login `
  --dart-define=GILBIC_COLLECTOR_ROUTE_PATH=/staff/collector-route/today
```

Production must use HTTPS. PostgreSQL or Supabase credentials must never be
placed in Flutter. Gilbic sends authenticated requests to FastAPI, and FastAPI
remains the only database and business-rule boundary.

## Offline route behavior

1. Gilbic requests the assigned route from FastAPI.
2. A successful response is displayed and saved as an encrypted SQLite snapshot.
3. The SQLCipher password is generated randomly and stored separately through
   Android Keystore or Apple Keychain-backed secure storage.
4. If the next route request fails, Gilbic reads the most recent snapshot for
   that authenticated user.
5. Cached data is marked **Offline copy** and shows when it was last synchronized.
6. Signing out removes that account's route snapshot.

The cached route may be older than the official server data. Gilbic therefore
keeps the offline screen read-only and never recalculates balances locally.

## Accepted login response shapes

Preferred standard response:

```json
{
  "success": true,
  "data": {
    "access_token": "token",
    "refresh_token": "optional-token",
    "user": {
      "account_id": 42,
      "username": "collector.one",
      "full_name": "Collector One",
      "role": "Collector",
      "permissions": ["route.view"]
    }
  }
}
```

The compatibility parser also accepts direct fields such as `session_id`,
`account_id`, `full_name`, `username`, and `role` from the current web portal.

## Security rules

- the server decides the role, permissions, route assignment, and balances
- collector routes are filtered by the authenticated collector on the server
- tokens and the SQLCipher key are stored with secure device storage
- a route request sends `Authorization: Bearer <token>`
- mobile code never receives a PostgreSQL password
- the cached route is deleted for the account during sign-out
- all future payment writes require idempotency and server-side validation

## Planned next milestone

1. confirm the live FastAPI endpoint paths against the backend source
2. define an idempotent payment-submission contract
3. add an encrypted pending-payment queue only after conflict rules are approved
4. add synchronization receipts and end-of-day reconciliation
