# CB1 Management Mobile Alerts and Audit Visibility

## Current gap

The Management dashboard already prioritizes live queue counts and labels its
first shortcut **Alerts & activity**, but that shortcut currently opens the
shared recipient-scoped **Payment Updates** inbox. That inbox is authoritative
for its own payment/remittance notifications, but it does not satisfy CB1's
required Management visibility over pending approvals, rejected remittances,
cash-custody changes, or protected financial actions.

Existing owning records and immutable audit evidence already contain the
required facts. This slice adds a read-only projection and a compact Mobile
review page; it does not create another notification store, workflow engine, or
financial authority.

## Implemented outcome for this slice

Management Mobile gains one **Alerts & activity** page with:

1. **Needs attention** rows derived from current owning records for assigned
   remittances, unresolved rejected remittances, protected renewals, staff and
   client registrations, pending staff devices, borrower support, and protected
   financial journal/audit inconsistencies.
2. **Recent audit activity** derived only from an explicit allowlist of account,
   device, renewal, support, remittance/custody, and protected journal events.
3. A separate **Payment updates** row that opens the existing recipient-scoped
   inbox and retains its existing read-receipt behavior.

The page is read-only. Every row links to an existing protected owning workflow
when the current session still has the required permission.

## Authority and derivation rules

- FastAPI and PostgreSQL remain authoritative. Flutter validates and renders
  the returned projection and never infers an approval, failure, custody state,
  journal state, or audit outcome.
- Pending approval counts come from the owning user, registration, device,
  renewal, and support records.
- Remittance submission, receipt/custody transfer, and rejection events come
  from `lending.collection_remittances` and its immutable review/rejection
  evidence. A rejection is an attention event; an unresolved rejection alert
  exists only while at least one original item remains unlocked and unremitted.
- Protected financial events come from `accounting.journal_events` joined to
  the current authoritative `accounting.journal_entries` row. No free-form
  event details are exposed as financial state.
- A protected financial audit-gap alert is derived only when an allowlisted
  posted protected journal lacks its required `posted` journal event.
- Account, device, renewal, and support audit rows use an explicit action
  allowlist and join the owning record for current state and safe display
  identity. Unknown actions and unknown protected source types are excluded.
- Raw `core.audit_logs.details`, support message/response text, client phone or
  document data, device identifiers, and unrestricted audit payloads are never
  returned.

## Role and permission contract

The endpoint requires all of:

- Supabase bearer authentication;
- an active approved device supplied through `X-Device-Id`;
- canonical `management` role; and
- `management.dashboard.view`.

Returned sections are independently reduced by server permissions:

- staff/client account approvals: `account.manage`;
- staff device activity: `device.manage`;
- renewal review: `renewal.manage`;
- borrower support: `support.manage`;
- remittance/custody: `remittance.view` (receipt actions still separately require
  `remittance.receive` in the owning workflow);
- protected financial activity: `accounting.view`.

Flutter intersects those server-returned navigation codes with the current
session permissions again at tap time. UI hiding is never authorization.

## API contract

Desktop and Mobile aliases call the same handler:

- `GET /api/v1/management/alerts-audit`
- `GET /api/mobile/v1/management/alerts-audit`

The response returns one generated timestamp, the visible domains, authoritative
attention rows, recent allowlisted events, a bounded event limit/window, and an
explicit read-only notice. There is no POST, PATCH, PUT, or DELETE endpoint.

## Mobile behavior

- Use compact list rows with a small number box, not large dashboard cards.
- Separate attention from recent history and make warning/critical states
  visually distinct without using raw database terminology.
- Preserve the last successful snapshot if refresh fails and show its timestamp.
- Reject malformed or weakened contracts before display.
- Opening a row never changes official state. Protected actions remain in their
  existing pages with their existing confirmation, idempotency, stale-source,
  audit, and server revalidation controls.

## Explicitly outside this slice

- New notification writes, push delivery, email/SMS, background polling, or a
  second notification backend.
- Any financial write, migration, production operation, automatic posting,
  approval, remittance receipt, reversal, or correction.
- Treating audit text as owning business state.
- Closing broad CB1, Android/iOS human acceptance, merge, deployment, signing,
  or release gates.
