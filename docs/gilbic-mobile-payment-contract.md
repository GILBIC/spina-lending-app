# Gilbic mobile collection submission contract

This document defines the write-capable boundary between Gilbic and the SPINA FastAPI backend. The backend route, PostgreSQL transaction, device enforcement, and idempotency storage are implemented. The visual payment form and encrypted offline outbox remain disabled until their user experience is complete.

## Endpoints

```text
POST /api/v1/collector/collections
POST /api/mobile/v1/collector/collections
```

The mobile path is configurable in Flutter through `GILBIC_PAYMENT_SUBMISSION_PATH`.

## Required authentication and headers

```text
Authorization: Bearer <session token>
Idempotency-Key: <client transaction ID>
X-Client-Transaction-Id: <same client transaction ID>
X-Device-Id: <raw installation ID registered during login>
X-Gilbic-Contract-Version: gilbic-collection-v1
Content-Type: application/json
```

The backend derives the collector account and internal device record from the authenticated session and device header. Flutter must not submit a trusted collector ID, role, permission, balance, interest calculation, or receipt number. The raw installation ID is used to bind the request and is not stored in official collection records.

## Request body

```json
{
  "client_transaction_id": "6cb93829-dccd-4d43-a25c-a1f31859cc1b",
  "route_entry_id": "44444444-4444-4444-8444-444444444444",
  "client_id": "33333333-3333-4333-8333-333333333333",
  "loan_id": "44444444-4444-4444-8444-444444444444",
  "collection_date": "2026-08-01",
  "entry_type": "payment",
  "amount": "200.00",
  "advance_from": null,
  "advance_until": null,
  "recorded_at": "2026-08-01T02:29:00.000Z",
  "device_id": "gilbic-installation-one",
  "device_sequence": 8,
  "note": "Paid at home",
  "route_revision": "loan:44444444-4444-4444-8444-444444444444:v7"
}
```

Supported `entry_type` values:

- `payment`: requires an amount greater than zero and no ADV dates.
- `advance`: requires an amount greater than zero plus `advance_from` and `advance_until`.
- `pass`: contains no amount and no ADV dates.

The server validates all official SPINA rules. Flutter validation only prevents clearly incomplete requests.

## Route revision

Every route entry contains a revision derived from the locked loan state:

```text
loan:<loan UUID>:v<state version>
```

The request must include that exact value. A changed balance, PASS count, ADV state, or other official update increments the version. A stale revision returns HTTP `409` and tells the collector to refresh the route.

## Idempotency rule

`client_transaction_id`, `Idempotency-Key`, and `X-Client-Transaction-Id` must contain the same UUID value.

The client creates this key once when the collection draft is created. Every retry of that same collection reuses the same key.

The backend behavior is:

1. No matching key exists: validate and post the collection in one database transaction.
2. Matching key exists with the same canonical request payload: return the original successful transaction and receipt with `duplicate: true`.
3. Matching key exists with a different payload or owner: return HTTP `409` with code `idempotency_mismatch`.
4. The client loses the response after the server commits: the retry returns the original receipt instead of creating a second payment.

The server stores a SHA-256 canonical request hash. The stored request payload omits the raw installation ID.

## Device sequence

Each installation keeps a positive, increasing `device_sequence`. The pair `(registered_device_id, device_sequence)` is unique in PostgreSQL. Reusing a sequence with a new transaction key returns `device_sequence_reused`.

The future encrypted outbox must preserve both the original idempotency key and device sequence across every retry.

## Server transaction

A successful submission is atomic. Within one PostgreSQL transaction, FastAPI:

1. Authenticates the account and verifies `collection.create` permission.
2. Resolves and rechecks the active registered device.
3. Locks the idempotency key, device sequence, loan, and collection date.
4. Verifies collector area assignment, client status, loan status, route entry, and route revision.
5. Requires a reconciled `loan_collection_state`.
6. Requires the loan type to be explicitly approved for mobile collection.
7. Applies payment, ADV, or PASS rules to the authoritative state.
8. Creates the immutable collection transaction and receipt.
9. Updates balance, PASS count, ADV coverage, and state version.
10. Marks the loan `paid` when the balance reaches zero.
11. Creates the audit event.
12. Saves the replayable idempotency result and canonical request hash.
13. Commits all records together.

A partial transaction without its balance update, receipt, audit record, and idempotency result is never committed.

## Loan readiness

Mobile writes are disabled by default. A loan must have:

```text
loan_collection_state.is_reconciled = true
```

The loan type must explicitly contain:

```json
{
  "mobile_collections_enabled": true,
  "mobile_balance_mode": "direct_remaining_balance"
}
```

`direct_remaining_balance` is required for payment and ADV. It means subtracting the accepted amount from the reconciled official balance is the verified rule for that loan type.

Do not enable direct balance mode for a loan requiring principal/interest/penalty allocation unless that allocator is already verified. The 7x7 fixed daily interest rule remains disabled for mobile payment and ADV until its dedicated allocation strategy is implemented and tested against SPINA desktop results.

## Accepted response

Status: HTTP `201`.

```json
{
  "success": true,
  "data": {
    "status": "accepted",
    "duplicate": false,
    "client_transaction_id": "6cb93829-dccd-4d43-a25c-a1f31859cc1b",
    "transaction_id": "55555555-5555-4555-8555-555555555555",
    "receipt_number": "GBC-20260801-00000001",
    "official_balance": "800.00",
    "accepted_at": "2026-08-01T02:30:00.000000Z",
    "route_revision": "loan:44444444-4444-4444-8444-444444444444:v8",
    "message": "Payment saved."
  }
}
```

Money is returned as an exact two-decimal string. The mobile app displays the official server balance and receipt. It never subtracts the payment locally and treats that result as official.

## Duplicate replay response

Status: HTTP `200`.

```json
{
  "success": true,
  "data": {
    "status": "duplicate",
    "duplicate": true,
    "client_transaction_id": "6cb93829-dccd-4d43-a25c-a1f31859cc1b",
    "transaction_id": "55555555-5555-4555-8555-555555555555",
    "receipt_number": "GBC-20260801-00000001",
    "official_balance": "800.00",
    "accepted_at": "2026-08-01T02:30:00.000000Z",
    "route_revision": "loan:44444444-4444-4444-8444-444444444444:v8",
    "message": "Already recorded. No duplicate payment was created."
  }
}
```

A duplicate replay is a final success. The mobile app saves and displays the original receipt, then removes the matching pending item.

## Conflict response

Status: HTTP `409`.

Important conflict codes:

- `idempotency_mismatch`
- `route_revision_changed`
- `device_sequence_reused`
- `pass_already_recorded`

Conflicts remain in a review state. The mobile app does not silently create a replacement transaction with a new idempotency key.

## Business-rule rejection

Status: HTTP `422` unless authentication or permission rules require another status.

Important codes:

- `route_revision_required`
- `loan_not_found`
- `loan_not_active`
- `client_not_active`
- `route_not_assigned`
- `loan_state_not_reconciled`
- `loan_type_mobile_disabled`
- `loan_calculation_not_ready`
- `amount_exceeds_balance`
- `advance_already_covers_date`
- `collection_date_out_of_order`
- `device_not_registered`

The API returns plain-language messages such as **Refresh the route**, **Use the SPINA desktop app**, or **This date is already covered by ADV**. Raw database errors and stack traces are not user-facing messages.

## Authentication and server errors

- HTTP `401`: session expired or invalid.
- HTTP `403`: account, permission, or device access is not valid.
- HTTP `429`: temporary rate limit; retry the same key later.
- HTTP `500` or `503`: uncertain server outcome; retry using the same key.
- Network timeout or lost connection: uncertain outcome; retry using the same key.

A timeout does not prove failure. The server may already have committed the collection.

## Database boundary

Official records are stored in:

```text
lending.collection_transactions
lending.loan_collection_state
mobile.gilbic_collection_idempotency
core.audit_logs
```

Important unique boundaries include:

```text
idempotency_key
registered_device_id + device_sequence
loan_id + collection_date for PASS
receipt_number
```

The idempotency row and official collection result are written inside the same transaction.

## Current mobile boundary

Implemented:

- typed payment, ADV, and PASS request models
- secure UUID version 4 idempotency key generator
- configurable FastAPI endpoint
- bearer and active-device authorization
- route revisions and readiness metadata
- accepted, duplicate, conflict, and rejected result models
- atomic PostgreSQL collection, balance, receipt, audit, and idempotency writes
- network-error rule requiring reuse of the same key and sequence
- backend and contract tests

Still disabled in the app:

- collector collection form
- encrypted pending-collection outbox
- automatic synchronization
- receipt screen
- conflict-review screen
- dedicated 7x7 payment allocator

The next milestone is the simple collector form, followed by the encrypted outbox.
