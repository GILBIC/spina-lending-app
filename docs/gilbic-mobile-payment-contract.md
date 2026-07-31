# Gilbic mobile collection submission contract

This document defines the first write-capable boundary between Gilbic and the SPINA FastAPI backend. It does not enable a payment screen or an offline write queue. It defines the protocol that must be implemented and verified before those features are exposed.

## Endpoint

```text
POST /api/mobile/v1/collector/collections
```

The path is configurable in Flutter through `GILBIC_PAYMENT_SUBMISSION_PATH`.

## Required authentication and headers

```text
Authorization: Bearer <session token>
Idempotency-Key: <client transaction ID>
X-Client-Transaction-Id: <same client transaction ID>
X-Device-Id: <registered device ID>
Content-Type: application/json
```

The backend must derive the collector account from the authenticated session. Flutter must not submit a trusted collector ID, role, permission, balance, interest calculation, or receipt number.

## Request body

```json
{
  "client_transaction_id": "6cb93829-dccd-4d43-a25c-a1f31859cc1b",
  "route_entry_id": "route-entry-304",
  "client_id": "client-304",
  "loan_id": "loan-815",
  "collection_date": "2026-07-31",
  "entry_type": "payment",
  "amount": 200.0,
  "advance_from": null,
  "advance_until": null,
  "recorded_at": "2026-07-31T05:15:00.000Z",
  "device_id": "collector-phone-15",
  "device_sequence": 45,
  "note": "Paid at home",
  "route_revision": "route-v3"
}
```

Supported `entry_type` values:

- `payment`: requires an amount greater than zero and no ADV dates.
- `advance`: requires an amount greater than zero plus `advance_from` and `advance_until`.
- `pass`: contains no amount and no ADV dates.

The server must validate all SPINA rules. Flutter validation only prevents clearly incomplete requests.

## Idempotency rule

`client_transaction_id`, `Idempotency-Key`, and `X-Client-Transaction-Id` must contain the same UUID value.

The client creates this key once when the collection draft is created. Every retry of that same collection must reuse the same key.

The backend must enforce a unique database constraint on the idempotency key. Recommended behavior:

1. No matching key exists: validate and post the collection in one database transaction.
2. Matching key exists with the same canonical request payload: return the original successful transaction and receipt with `duplicate: true`.
3. Matching key exists with a different payload: return HTTP `409` with code `idempotency_mismatch`.
4. The client loses the response after the server commits: the retry returns the original receipt instead of creating a second payment.

The server should store a canonical request hash with the idempotency record so mismatched reuse can be detected.

## Server transaction

A successful submission must be atomic. Within one PostgreSQL transaction, FastAPI should:

1. Authenticate the account and verify `collection.create` permission.
2. Verify the registered device and collector assignment.
3. Lock or otherwise protect the targeted loan and collection-day records.
4. Verify the route entry, route revision, collection date, and day-close state.
5. Recalculate eligibility, amount rules, ADV coverage, PASS rules, and official balance using SPINA server logic.
6. Create the payment, ADV, or PASS record.
7. Update the official loan balance and related collection records.
8. Create the receipt and audit log.
9. Save the idempotency result and canonical request hash.
10. Commit all records together.

A partial payment record without its balance update, receipt, audit record, and idempotency result must never be committed.

## Accepted response

Recommended status: HTTP `201`.

```json
{
  "success": true,
  "data": {
    "status": "accepted",
    "client_transaction_id": "6cb93829-dccd-4d43-a25c-a1f31859cc1b",
    "transaction_id": "collection-9001",
    "receipt_number": "OR-00009001",
    "official_balance": 4600.0,
    "accepted_at": "2026-07-31T05:16:02Z",
    "route_revision": "route-v4",
    "message": "Collection accepted"
  }
}
```

The mobile app must display the official server balance and receipt. It must not subtract the payment locally and treat that result as official.

## Duplicate replay response

Recommended status: HTTP `200`.

```json
{
  "success": true,
  "data": {
    "status": "duplicate",
    "duplicate": true,
    "client_transaction_id": "6cb93829-dccd-4d43-a25c-a1f31859cc1b",
    "transaction_id": "collection-9001",
    "receipt_number": "OR-00009001",
    "official_balance": 4600.0,
    "accepted_at": "2026-07-31T05:16:02Z",
    "message": "Previously accepted"
  }
}
```

A duplicate replay is a final success. The mobile app should remove the matching pending item only after saving this returned receipt information.

## Conflict response

Recommended status: HTTP `409`.

```json
{
  "success": false,
  "message": "The route changed after download.",
  "error": {
    "code": "stale_route"
  },
  "route_revision": "route-v4"
}
```

Recommended conflict codes:

- `idempotency_mismatch`
- `stale_route`
- `already_collected`
- `day_closed`
- `route_closed`
- `client_not_assigned`
- `collector_changed`
- `advance_overlap`
- `server_state_changed`

Conflicts must remain in a review state. The mobile app must not silently create a replacement transaction with a new idempotency key.

## Business-rule rejection

Recommended status: HTTP `422`.

Recommended codes:

- `loan_closed`
- `loan_not_found`
- `invalid_amount`
- `invalid_advance_range`
- `invalid_pass`
- `collection_date_not_allowed`
- `permission_denied`
- `device_not_registered`

Rejected entries require correction or staff review and must not be retried forever without a change.

## Authentication and server errors

- HTTP `401`: session expired or invalid.
- HTTP `403`: authenticated account lacks permission.
- HTTP `429`: temporary rate limit; retry the same key later.
- HTTP `500` or `503`: uncertain server outcome; query or retry using the same key.
- Network timeout or lost connection: uncertain outcome; retry using the same key.

A timeout does not prove failure. The server may already have committed the collection.

## Database boundary

The official PostgreSQL database should contain an idempotency table or equivalent fields with at least:

```text
idempotency_key          unique
collector_account_id
registered_device_id
canonical_request_hash
request_payload
result_status
server_transaction_id
receipt_number
official_balance
accepted_at
created_at
updated_at
```

The idempotency row and collection result must be written inside the same transaction.

## Mobile boundary in this milestone

Implemented now:

- typed payment, ADV, and PASS request models
- secure UUID version 4 idempotency key generator
- configurable FastAPI endpoint
- bearer-authenticated repository boundary
- accepted, duplicate, conflict, and rejected result models
- request and response compatibility tests
- network-error rule requiring reuse of the same key

Not implemented yet:

- collector payment form
- encrypted pending-payment queue
- automatic synchronization
- receipt screen
- conflict-review screen
- backend FastAPI route or PostgreSQL migration

The next milestone may add the encrypted pending-payment queue only after the live FastAPI backend implements this contract or its exact equivalent.
