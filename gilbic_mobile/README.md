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
- compatibility with standard SPINA `{success, message, data}` responses
- compatibility parsing for the existing direct staff-session response fields
- Client, Collector, Employee, and Management dashboards
- configurable API base URL and endpoint paths
- automated authentication, role, route, and widget tests

No official loan, payment, accounting, billing, or tax record is written by this
milestone. The collector route is deliberately read-only.

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

The Flutter source is shared between both platforms. Android builds can run on
Windows. The final iOS build must be compiled on macOS with Xcode.

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

- the server decides the role and permissions
- collector routes must be filtered by the authenticated collector on the server
- the token is stored using Android Keystore or Apple Keychain-backed storage
- a route request sends `Authorization: Bearer <token>`
- mobile code never receives a PostgreSQL password
- all future payment writes require idempotency and server-side validation

## Planned next milestone

1. confirm the live FastAPI endpoint paths against the backend source
2. add encrypted SQLite route caching
3. show offline and last-synchronized route status
4. add idempotent payment synchronization behind server validation
