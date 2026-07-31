# Gilbic encrypted collector route cache

This milestone gives authenticated collectors read-only access to the last successfully downloaded route when the SPINA FastAPI server cannot be reached.

## Runtime flow

1. Gilbic requests the assigned route through the authenticated FastAPI endpoint.
2. A successful response is displayed as **Online route**.
3. The route snapshot is serialized and stored in a SQLCipher-encrypted SQLite database.
4. The database password is generated from 32 random bytes and stored separately through platform secure storage.
5. A failed network request attempts to load the snapshot for the authenticated user.
6. A recovered snapshot is displayed as **Offline copy** with its last-synchronized timestamp.
7. Signing out deletes that user's cached route snapshot.

## Storage boundary

The encrypted database contains only downloaded route presentation data:

- route date and collector name
- assigned areas
- route entries and client display names
- server-returned loan type, daily amount, balance, status, PASS count, ADV coverage, last-payment date, and note
- synchronization timestamp

It does not contain a PostgreSQL password, FastAPI business logic, locally calculated balances, payment submissions, renewal requests, journal entries, billing records, or tax records.

## Authority rules

- FastAPI remains the authority for authentication, collector assignment, permissions, balances, ADV/PASS rules, and route content.
- Gilbic does not recalculate balances or collection eligibility from cached data.
- Cached information is visibly marked as offline and may be stale.
- The offline route remains read-only.
- No payment is queued or synchronized by this milestone.

## Encryption and key management

- Route snapshots are stored with the `sqflite_sqlcipher` Flutter plugin.
- The SQLCipher password is not hard-coded in Dart source.
- `SecureRouteCacheKeyStore` generates a random 256-bit password on first use.
- The password is stored through `flutter_secure_storage`, which uses the supported secure storage mechanism of the mobile platform.
- Route rows are separated by authenticated `user_id`.
- Account sign-out removes the matching route row.

## Android platform setup

SQLCipher classes must be retained when Android release shrinking is enabled. `tool/bootstrap_platforms.ps1` creates `android/app/proguard-rules.pro`, adds the SQLCipher keep rule, and links that file from the generated Android app build configuration.

## Failure behavior

- Network succeeds and cache succeeds: show the live route and update the snapshot.
- Network succeeds and cache fails: show the live route with a warning that offline storage was not updated.
- Network fails and a snapshot exists: show the offline copy and synchronization time.
- Network fails and no snapshot exists: show the existing connection error and retry action.
- Cache decoding fails: do not display corrupted cached data; preserve the original network failure.

## Validation

The permanent Gilbic workflow runs strict Flutter analysis and tests for:

- route serialization round trips
- per-user cache write, read, and clear behavior
- successful network download and cache replacement
- offline fallback when the server fails
- network failure propagation when no cache exists
- live display when cache persistence fails
- online and offline route status widgets
- existing authentication and route-response compatibility
- clean committed tree

## Next boundary

The next write-capable mobile milestone must begin with a reviewed FastAPI idempotency and conflict-resolution contract. An encrypted pending-payment queue must not be added before the server contract is confirmed.
