# Collector surplus source and contract map

Recorded 2 October 2026. Implementation dependency: Treasury PR490 at
`08c31edd2bc05d8dbe05b73934acff0fb52e746d`. The isolated PR491 fixture starts at
`565d9283b194f8eafb243346f05823483a5d7586`; the additive command contract starts at
`abce583d`. This map describes source seams and review requirements. It is not a
claim that later acceptance checks have passed.

The integration owner explicitly selected a dependent Draft PR against490,
preserving490 and main. Neither branch may be merged or deployed by this work.
The original default prerequisite of490 merged into main is replaced only for
this documented review arrangement, not for production rollout.

## Runtime and receiving graph

Ordinary and mobile remittance receive handlers in `remittance_api.py`, and
notification acceptance handlers in `notification_api.py`, call
`PostgresReviewedRemittanceRepository.confirm_received`. The reviewed repository
normally owns its connection and transaction. Counted acceptance must instead
use a caller-owned adapter inside `TreasuryService.execute`; an independent
connection or HTTP call would allow partial financial commits.

Migration0010 moves accepted remittance custody to the designated recipient and
completes the pending notification inside the status-update transaction. It does
not create a Treasury event. Consequently a new accepted physical count needs
one full cash receipt event, with ordinary-obligation and excess classifications
linked to that event. Recording ordinary cash and then recording the full count
would double-count money. Legacy source and refund snapshots remain immutable.

Both legacy receiving repositories and every ordinary/notification/mobile entry
must reject acknowledgment-only acceptance when the counted contract is required.
Disabling new surplus entry must not revive an old acceptance bypass for retained
surplus state. Historical accepted rows have no invented count.

Legacy rejection unlocks source records and describes responsibility as returned
to the Collector. A short count alone neither accepts the remittance nor proves
physical cash was returned. Actual retained cash needs its separate evidenced
custody exception. Rejection cannot erase an unresolved retained exception.

Ordinary and cross-remittance submitters consume protected Collector-cash source
rows and refund-release snapshots. Recipient-wallet-funded borrower collections
remain excluded by0137. Source attribution, actual recorder and accepted holder
are separate facts; role or equal amounts cannot substitute for custody evidence.

## One financial boundary

`treasury_repository.py` owns execute/replay, request hashes, current authority,
account versions, audit and durable outcomes. Handlers receive its existing
connection and never commit themselves. Existing Treasury events, movements,
evidence and source links remain the cashbook. Additive migration
`gilbic_backend/sql/0138_add_collector_surplus.sql` is reserved for bounded counts,
settlements, cases, credits, requests, reserved actions and custody exceptions.
It must not seed real accounts, amounts or blanket grants.

`treasury_disbursements.py` records independently verified actual debits and fees.
Collector returns use dedicated source adapters, never a fabricated borrower or
refund. Intent, independent reservation approval, actual debit, recipient
acknowledgment and staff settlement are distinct phases. A lost response or an
unconfirmed debit retains its request/capacity; it does not authorize another
payout or cancellation.

`treasury_reconciliation.py` uses account watermarks and immutable close
snapshots. Cash-neutral purpose changes still need correct review invalidation.
Restore and runtime compatibility checks must include all new tables and private
files. An old binary must not reinterpret retained counts or credits as ordinary
cash-only remittances.

## Lock and authority review

Existing Treasury order is active user/device checks, request advisory lock,
account advisory locks and rows, current account grants, replay/version checks,
then handler sources and audit/outcome. Account transfers order all accounts by
UUID. New handlers must discover immutable origin/paying account identities and
acquire those accounts in canonical order before credit/action/source locks.
Concurrent recognition, return, cancellation and reclassification consume the
same locked capacity. Immutable settlement/event/request uniqueness is required
in addition to unchanged-request recovery.

Legacy submitters serialize Collector/date before collection/refund rows; legacy
receive/reject starts with the remittance row. Protected borrower correction and
allocation have their own advisory-before-source-row order. A new adapter must
not reverse these orders or claim safety without two-connection evidence.

Staff action permission, per-account grant, current context and exact target
authority are all required. Receiving additionally requires the designated
recipient and real physical-cash account holder. Recognition and approval cannot
be performed by the credited Collector. Owner-only opening anchors do not add
cash. Four bounded surplus grants extend the existing union without granting
them to all Employees or Collectors.

Own requests and acknowledgments derive Collector identity and origin context
from the target credit/exception and authenticated actor. They deliberately have
no wallet account/version inputs or account-history grant. Replay must recheck
that same current object scope. Own projections and exports omit private wallet
history, evidence and unrelated actors; staff projections also remain scoped.

## Frozen client interface

See [API contract](collector-surplus-api-contract.md) and its generated
[command schema](collector-surplus-command-schema.json). Version1 capability,
server money strings, explicit dispositions and exact actor/device/target/version
bindings are required. `saved` is not synonymous with received, recognized or
paid. Zero is valid for an observation; amounts are never calculated with client
floating point. Unknown/malformed financial results retain recovery locks.

Web integrates `collector-surplus.js` into existing Treasury role tasks and the
shared `remittance-review.js`. Employee and Management already use the same
receive component. Collector gets an own-credit destination; Client gets no
Collector-credit authority. Treasury and older role tasks must share uncertainty
gating so a new panel cannot bypass an unresolved submission in its sibling.

Android extends the existing Treasury models/repository/encrypted submitted
attempt journal and remittance/notification routes. It does not add another
outbox. Current-session permission changes clear private state; reviewed file
bytes and unchanged requests retain their exact ownership through recovery.
Installed Windows uses `spina_pc` portal app mode and the same server contract.

All count, evidence, case, credit and payout panels are private and excluded from
screen sharing before they appear. Existing capture allowlists must not expand.
API/evidence/export responses remain authenticated and uncached. Browser drafts
stay in mounted memory; only already-submitted native attempts use the existing
encrypted recovery store.

## Explicit adapter boundaries

Current protected collection correction rejects locked/remitted or schedule-backed
history, and protected Treasury posting validates the current route date. The
existing receipt event has a one-receipt event identity; arbitrary borrower
portions cannot reuse a full accepted remittance by inventing extra cash events.
Historical correction must remain an explicit execution blocker until a real
dated, protected funding adapter proves the result.

Likewise, legacy custody and GL readers assume the received remittance gross
amount. A100 credit plus900 actual cash against a1000 obligation cannot be
reported as1000 physical cash. Future credit application
and unmapped GL execution must return precise blockers until their canonical
adapters exist. Requests may record intent; blocked execution must not reserve,
apply, post today, invent an opening amount or claim successful settlement.

The retained-cash inclusion adapter now links an existing physical dispute event
and a separately counted additional receipt to the same original remittance.
It requires explicit current exception selection and no return reservation.
Only the additional count creates an inflow; the held amount becomes included
in settlement within the same transaction. This does not implement Collector
credit application or change borrower collections/GL authority.

## Evidence ownership

The retained dependency run37000064830 passed all12 jobs; this proves490 only.
Task0 Treasury contract/ledger baseline passed5 tests. The initial additive
contract had two meaningful missing-action failures followed by10 passing checks.
New PostgreSQL migration, authority, capacity races, rollback, restore and
platform evidence must be recorded separately against491 source. Mocked UI
fixtures, screenshots and a healthy API are not financial or security acceptance.
