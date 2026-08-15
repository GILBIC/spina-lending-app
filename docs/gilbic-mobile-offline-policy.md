# Gilbic V1 mobile offline behavior

This document freezes the V1 offline boundary for the shared Android/iOS Gilbic app. FastAPI + PostgreSQL remain authoritative for authentication, permissions, balances, receipts, custody, approvals, requests, and accounting.

## Permanent V1 rules

- No mobile role may create a financial write while offline.
- No financial write is silently placed into an offline outbox.
- No financial write is automatically replayed after connectivity returns.
- A still-valid secure session may remain open through a temporary network outage, but server-authoritative refreshes and writes still require connectivity.
- Already-rendered values can remain visible in memory but must be treated as stale until refreshed.
- Only the Collector role has a supported persistent offline business-data cache in V1: the encrypted assigned-route snapshot.
- The Collector route cache is presentation-only, visibly labeled **Offline copy**, scoped to the authenticated user, and read-only.
- If a Collector explicitly submits a write while online and the network result is unknown, the app may offer **Retry same entry** only after explicit user action. That retry must reuse the original idempotency key and device sequence. This is not an offline queue or automatic replay.

## Role matrix

| Role | Supported offline data | Offline writes | Queue / automatic replay | Reconnect requirement |
|---|---|---|---|---|
| Management | No persistent business-data cache. Already-rendered screens may remain visible as stale UI state. | Block all approvals, client/loan changes, custody decisions, device actions, accounting/tax/ECL/close actions, posting and reversal. | None. | Refresh from the server before relying on current values or taking protected actions. |
| Employee | No persistent business-data cache. Already-rendered screens may remain visible as stale UI state. | Block attendance/time writes, requests, remittance receipt/acceptance, encoding/status work, support actions and any other authoritative operation. | None. | Reconnect before refreshing or changing employee/office/custody/support state. |
| Collector | Encrypted last successful assigned-route snapshot only. | Block Regular/7x7 collection, unable-to-pay, covered-date collection, correction, cross-area collection, remittance, custody transfer and all other financial writes from an Offline copy. | No queue or automatic replay. Explicit manual same-entry retry is allowed only for an already-attempted idempotent online submission with unknown result. | Reconnect and refresh the route before starting a new collection or correction. |
| Client | No persistent borrower financial-data cache. Already-rendered screens may remain visible as stale UI state. | Block renewal/support requests, payment-proof upload/re-upload/correction and any other evidence/request state change. | None. | Reconnect before refreshing loans/payments/receipts/notifications or submitting requests/evidence. |

## Collector cache boundary

The existing encrypted route cache remains the only V1 offline business-data store. It must not contain payment submissions, renewal requests, journal entries, billing records, tax records, locally calculated balances, or a pending-write outbox. See `docs/gilbic-mobile-encrypted-route-cache.md` for the storage and encryption contract.

A cached Collector route must continue to:

1. show **Offline copy** and last-sync time;
2. expose route presentation data only;
3. disable collection and correction entry points;
4. never recalculate balance or collection eligibility locally;
5. be cleared for the authenticated user on sign-out/terminal session invalidation according to the secure-session boundary.

## Failure and retry behavior

A failed financial request must surface a clear error and return control to the user. The app must not start a timer, background job, connectivity listener, outbox processor, or app-resume hook that replays the write automatically.

For Collector collection submission, the existing safe retry path retains the exact pending draft after an unknown network result. The user must explicitly confirm **Retry same entry**. The repeated request uses the same idempotency key and device sequence so the server can return duplicate/original-success semantics without creating another official transaction.

## Acceptance evidence required for C1

The permanent mobile validation must prove:

- every role policy declares offline financial writes blocked;
- every role policy declares silent queue and automatic financial replay forbidden;
- Collector is the only role with persistent offline business data;
- Collector Offline copy remains read-only;
- a failed Collector write does not replay after elapsed time;
- only explicit user retry causes the second request, and it reuses the same idempotency key/device sequence;
- the role-specific Offline & sync page is available from the shared app shell without a server fetch.

This policy is intentionally conservative for V1. Any future offline write/outbox design is V1.1+ and requires a separately reviewed server idempotency, conflict-resolution, encryption, revocation, stale-source, and replay contract before implementation.
