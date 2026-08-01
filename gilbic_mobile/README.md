# Gilbic Mobile

Gilbic is the Android and iOS mobile application for the SPINA lending platform.
It uses one Flutter codebase with separate role experiences for clients,
collectors, employees, and management.

## Current milestone

- real username and password login through the GitHub-first Gilbic FastAPI backend
- Supabase Auth-backed sessions with backend-assigned Gilbic roles and permissions
- encrypted token and session storage through platform secure storage
- permanent app-generated installation ID stored separately from the login session
- Android/iOS platform and app-version metadata sent during login
- bearer-authenticated requests
- `X-Device-Id` sent on protected collector requests
- immediate server rejection after an installation is revoked
- read-only assigned collector route
- route revision and clear mobile-readiness information per loan
- SQLCipher-encrypted SQLite route snapshots
- offline fallback to the last route saved for the authenticated collector
- online/offline source label and last-synchronized timestamp
- per-user route-cache removal during sign-out
- typed payment, ADV, and PASS submission contract
- secure UUID version 4 idempotency keys
- accepted, duplicate, conflict, and rejected server-result models
- live FastAPI/PostgreSQL collection endpoint with atomic balance, receipt, audit, and idempotency writes
- automated authentication, device-identity, route, cache, payment-contract, and widget tests

The visual collector payment form and encrypted offline outbox remain disabled. The backend write boundary now exists, but the form will be enabled only after the collector experience clearly prevents unsupported loan types and makes retries easy to understand.

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

The GitHub-first backend exposes mobile compatibility endpoints including:

```text
POST /api/mobile/v1/auth/register
POST /api/mobile/v1/auth/login
POST /api/mobile/v1/auth/refresh
GET  /api/mobile/v1/auth/me
POST /api/mobile/v1/auth/logout
GET  /api/mobile/v1/collector/routes/today
POST /api/mobile/v1/collector/collections
```

The API address remains configurable with Dart defines so development, staging,
and production can use different servers without changing source code.

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

Production must use HTTPS. PostgreSQL/Supabase database credentials and secret
service-role keys must never be placed in Flutter. Gilbic sends authenticated
requests to FastAPI, and FastAPI remains the database and business-rule boundary.

## Installation identity

Gilbic does not use IMEI, advertising ID, serial number, phone number, or another
hardware identifier as its device key.

1. On first use, Gilbic generates a cryptographically random installation ID.
2. The ID is stored through platform secure storage.
3. The ID survives normal sign-out because it identifies the app installation,
   not the authenticated session.
4. Login sends the installation ID, platform (`android` or `ios`), and app
   version to FastAPI.
5. FastAPI hashes the installation ID before storing it in `core.devices`.
6. Protected requests send the raw installation ID only as `X-Device-Id`.
7. Collection records store the server-side device record ID, not the raw installation ID.
8. Management can revoke a registered installation without changing the user's password or affecting another approved device.

Reinstalling the application may create a new installation ID depending on the
platform's secure-storage lifecycle. The server therefore treats devices as
revocable installation registrations, not as permanent hardware identities.

## Collector route clarity

Each route entry can now include:

```text
route_revision
can_collect_mobile
can_enter_payment
collection_message
```

These fields keep the screen simple:

- **Ready for mobile collection** means the official state is reconciled.
- **Checking against SPINA records** means the collector should not enter a mobile transaction yet.
- **Use SPINA desktop** means the loan type or calculation is not enabled for mobile.
- A route entry remains visible even when mobile collection is unavailable, so the collector does not accidentally miss the client.

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
keeps the offline screen read-only until the encrypted outbox is implemented. A stale `route_revision` is rejected by the server with a clear instruction to refresh.

## Collection idempotency boundary

Every future payment, ADV, or PASS draft receives one UUID transaction key. The
same key is sent as `client_transaction_id`, `Idempotency-Key`, and
`X-Client-Transaction-Id`.

A retry must reuse that key. A successful replay returns the original server
transaction and receipt as a duplicate success. Reusing a key with changed data
returns a conflict. Network loss does not prove the server rejected the
collection, so generating a replacement key after a timeout is prohibited.

The server also requires:

- the latest route revision
- an active registered device
- an unused device sequence number
- a reconciled loan state
- a server-approved loan calculation mode

The full request, response, PostgreSQL transaction, duplicate, conflict, and
rejection rules are documented in `docs/gilbic-mobile-payment-contract.md`.

## Collector-friendly results

The app should translate server results into short actions:

- **Payment saved** — show the receipt and new balance.
- **ADV saved** — show the covered-through date and receipt.
- **PASS saved** — return to the route.
- **Already recorded** — show the original receipt; do not ask the collector to enter it again.
- **Refresh route** — reload the loan before retrying.
- **Use SPINA desktop** — do not expose technical calculation errors.
- **Device access removed** — sign out and ask Management to review the device.

Raw PostgreSQL, stack-trace, or API wording must never be shown to collectors.

## Accepted login response shape

```json
{
  "success": true,
  "data": {
    "access_token": "token",
    "refresh_token": "refresh-token",
    "user": {
      "id": "user-id",
      "username": "collector.one",
      "full_name": "Collector One",
      "role": "Collector",
      "permissions": ["route.view"],
      "device_registered": true
    }
  }
}
```

The parser retains compatibility with earlier SPINA response field names while
migration to the new backend is in progress.

## Security rules

- the server decides roles, permissions, route assignment, eligibility, balances, and receipts
- public registration cannot choose Collector, Employee, or Management roles
- collector routes are filtered by the authenticated collector on the server
- tokens, installation ID, and SQLCipher key use secure device storage
- mobile code never receives a PostgreSQL password or Supabase secret key
- device identifiers are app-generated and server-stored only as hashes or internal record IDs
- cached routes remain read-only and are removed for the account during sign-out
- payment retries reuse one idempotency key
- official balances and receipts come only from FastAPI
- unsupported calculation rules stay disabled instead of using a guessed formula

## Planned next milestone

1. build the simple Payment / ADV / PASS collector form
2. show route readiness and plain-language explanations in the form
3. add an encrypted offline outbox that preserves idempotency keys and device sequence numbers
4. implement and verify the dedicated 7x7 payment allocator
5. add client, employee, and management mobile screens
