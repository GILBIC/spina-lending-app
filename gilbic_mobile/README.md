# Gilbic Mobile

Gilbic is the Android and iOS mobile application for the SPINA lending platform.
It uses one Flutter codebase with separate role experiences for clients,
collectors, employees, and management.

## Foundation included

- Material 3 application shell
- development login and role preview
- Client, Collector, Employee, and Management dashboards
- configurable FastAPI base URL
- session-storage boundary
- offline synchronization database boundary
- role and widget tests

No official loan, payment, or accounting data is written by this foundation.
The real authentication and collection endpoints will be connected in later
milestones.

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

## Run against the local SPINA FastAPI server

Android emulator:

```powershell
flutter run --dart-define=GILBIC_API_URL=http://10.0.2.2:8000
```

Physical phone on the same network:

```powershell
flutter run --dart-define=GILBIC_API_URL=http://YOUR-COMPUTER-IP:8000
```

Production will use an HTTPS API address. Database credentials must never be
placed in Flutter. Gilbic communicates with FastAPI, and FastAPI communicates
with PostgreSQL or Supabase PostgreSQL.

## Planned next milestone

1. map the existing FastAPI authentication response
2. replace development login with real authentication
3. store tokens using secure device storage
4. download a read-only collector route
5. add encrypted SQLite route caching and synchronization status
