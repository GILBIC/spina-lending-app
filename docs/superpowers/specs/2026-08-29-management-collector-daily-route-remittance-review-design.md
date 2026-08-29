# Management Collector Daily Route and Remittance Review Design

**Date:** 2026-08-29

**Repository:** `GILBIC/spina-lending-app`

**Starting commit:** `3a525e00d132d84f03fc24869b9c2801ea1f0108`

**Branch:** `codex/ca2-management-review-consistency`

**Pull request:** Draft PR #378

**Roadmap:** Frozen Master Issue #296, Management mobile parity after CA2

## Outcome

Give Management one server-authoritative, row-based workspace for reviewing
every Collector's daily assigned route and reconciling the cash that each
Collector must remit. The first screen is one compact row per Collector and
business date. Selecting a row opens the assigned clients in route order,
recorded visit outcomes, official collection evidence, custody attribution,
and linked remittances before Management enters the existing protected
remittance decision flow.

The workspace is a review surface, not a second financial ledger. FastAPI and
PostgreSQL derive every count, status, and amount. Flutter never treats route
assignment, scheduled dues, receipts, custody, remittance totals, or
differences as locally authoritative.

This design also records the approved direction for the existing client list:
Management client search results become compact rows with separate Details and
Schedule-summary actions. That bounded presentation change remains a separate
delivery slice. A complete installment-by-installment client schedule is not
invented from current mobile fields and requires its own authoritative schedule
read contract.

## Current Implemented Behavior and Intended Behavior

### Current implemented behavior

- Management home exposes separate small launchers for `Collection oversight`
  and `Remittance requests` under `Collections & custody`.
- Collection oversight calls the Management Loan Operations API. It shows
  individual collection transactions across Collectors and summary totals for
  latest-day collections, unremitted cash, submitted remittances, received
  remittances, corrections, and voids.
- Collection oversight can search by client, receipt, loan, or Collector and
  filter transaction custody/remittance status. It does not group a complete
  assigned route by Collector and cannot identify assigned clients with no
  recorded outcome.
- Remittance requests shows remittance notifications addressed to the current
  user. Each submitted handover can open the existing full itemized remittance
  review and protected accept/reject flow.
- Remittance requests does not show Collectors who have not submitted, route
  coverage, clients without an outcome, or cash still held outside a submitted
  batch.
- The Collector `routes/today` API is scoped to the authenticated Collector's
  active assigned areas. It does not authorize Management to supply a Collector
  ID and read another person's route.
- Current area assignments are not a historical daily manifest. They can show
  today's current ownership but cannot reconstruct a past route safely after
  assignments, clients, loans, or schedules change.
- Collection transactions preserve assigned and recording attribution needed
  for official payments. Cross-route policy also requires cash responsibility
  to follow the person who physically received the cash.
- There is no standalone persisted visit-result record for a client contact
  that produces neither a payment nor a PASS transaction. Absence of a
  financial entry therefore cannot be called a completed visit.

### Intended behavior

- Management opens `Collections & custody -> Collector daily routes`.
- The page defaults to the current Philippine business date and displays one
  compact row per active Collector, including a Collector with no prepared
  route or no recorded activity.
- Each row separates assigned-route performance from physical cash custody.
  Cross-route payments must not make the assigned route disappear or assign
  cash to the wrong Collector.
- The row reports assigned clients, clients with an authoritative recorded
  outcome, payment/PASS/advance indicators, route-attributed collection total,
  cash currently under that Collector's custody, unremitted cash, submitted
  cash, received cash, and reconciliation state.
- Selecting the row opens every snapshotted route entry in authoritative route
  order and explains payment, PASS, ADV, visit result, receipt, original
  recorder, correction state, and cash/remittance state.
- A pending submitted remittance opens the existing complete itemized review.
  The row itself never accepts or rejects money.
- Management can review a historical business date only when an immutable daily
  route snapshot exists. The system never reconstructs a past route from the
  current assignment table and presents it as historical fact.
- A missing visit result remains `Not recorded`; Flutter and the server do not
  infer that the Collector visited, skipped, or failed the client.

## Binding Domain Distinctions

The design preserves four identities that may legitimately differ:

1. **Assigned Collector** — permanent owner of the client's normal route and
   the person whose route contains the client.
2. **Original recorder** — authenticated user who posted the payment, PASS,
   ADV, or other official result.
3. **Current cash custodian** — person currently responsible for the physical
   cash after any accepted Collector-to-Collector handoff.
4. **Management receiver** — authorized person who accepts the remittance and
   takes custody for the office.

Route collection totals follow assigned-route attribution. Cash-held and
remittance totals follow current custody. A cross-route payment may therefore
increase one assigned route's collected total while increasing another
Collector's cash-held total. The backend explains the attribution in detail;
it never hides the difference by forcing the totals to match.

The following terms are also binding:

- **Assigned** means the client exists in the immutable daily route snapshot.
- **Recorded outcome** means the day has an official collection/PASS result or
  a separately recorded visit result for the route entry.
- **Payment client** means at least one non-voided cash receipt exists for the
  route client on the business date.
- **PASS client** means a non-voided structured unable-to-pay/PASS result exists
  for the route client on the business date.
- **Advance client** means an official payment allocation covers at least one
  future contractual date. It may also count as a payment client and is not
  added to payment counts as though it were a separate visit.
- **Not recorded** means no authoritative outcome exists. It does not assign
  fault or claim that no visit occurred.
- **Route-attributed collection** is official non-voided cash collected for
  clients in the assigned route, regardless of the original recorder.
- **Cash held** is official collection cash under the Collector's current
  custody, regardless of which assigned route owns the client.
- **Unremitted** is eligible cash held by the Collector that is neither locked
  in a submitted handover nor accepted by Management.
- **Difference** is a server-derived reconciliation exception between custody
  and linked remittance evidence. It is never `scheduled due minus cash paid`.

## Management Row Experience

### Navigation

Add one small `Collector routes` launcher to the existing `Collections &
custody` icon group. Keep `Collection oversight`, `Remittance requests`,
`Direct payment entry`, and `Void incorrect payment` because they remain
separate protected workflows.

The new page provides:

- business-date selector, defaulting to the current date in Asia/Manila;
- search by Collector or assigned area;
- status filters for `All`, `Needs attention`, `Ready to remit`, `Submitted`,
  `Received`, and `Missing route`;
- pull-to-refresh and a visible server generation time;
- one compact responsive row per Collector.

### Compact row

On mobile, the row uses three short lines plus a trailing review chevron:

```text
Collector Name                                      [Status]  >
Cardona, Morong        18/22 recorded   15 Pay · 3 PASS · 2 ADV
Route PHP 8,400 · Held PHP 8,100 · Unremitted PHP 3,100
```

The second line may wrap once on narrow or enlarged-text screens. The row
remains a single tap target with at least a 48 logical-pixel hit area. It is not
a large dashboard card. Desktop may render the same fields as table columns,
but field meanings and the backend contract remain identical.

The row's exact values are:

- Collector display name;
- ordered assigned areas from the daily snapshot;
- recorded-outcome client count over assigned-client count;
- payment-client, PASS-client, and advance-client counts;
- route-attributed collection total;
- cash currently held by the Collector;
- unremitted amount;
- submitted and received amounts when nonzero;
- one server-derived reconciliation status.

The row never displays `expected cash` because scheduled obligations are not
the same as cash physically received. Scheduled-due totals belong inside route
detail as operational context.

### Row statuses

The backend returns one closed status code and explanatory text:

- `missing_route` — no immutable daily snapshot exists;
- `not_started` — a route exists and has no recorded outcome or cash activity;
- `in_progress` — some assigned clients remain without an outcome;
- `ready_to_remit` — route activity exists and the Collector holds eligible
  unremitted cash with no reconciliation exception;
- `submitted` — eligible cash is locked in at least one submitted Management
  remittance and no exception is present;
- `received` — all submitted cash for the reviewed day is accepted and no
  remaining eligible cash or exception is present;
- `needs_attention` — custody, route, void/correction, missing evidence, or
  remittance linkage requires review.

`needs_attention` wins over every positive state. Status is explanatory, not a
financial authorization and not a Collector performance score.

## Collector Detail and Remittance Review

Selecting a row opens a read-only detail page with two sections.

### Route activity

The route section renders one compact client row in snapshotted route order:

```text
Client / code | Area | Scheduled | Outcome | Amount | Receipt | Recorder | >
```

Selecting a client row exposes:

- loan number/type and authoritative daily schedule context;
- official remaining balance and state version where already permitted;
- payment, PASS, ADV, or explicit visit result;
- exact covered dates for applicable payments;
- official receipt/reference and server timestamp;
- original recorder when cross-route work occurred;
- correction, void, lock, custody, and remittance state;
- client concern or operational note under its own permission and privacy rule.

The detail page labels entries without an outcome `Not recorded`. It does not
create a PASS, note, payment, or visit on Management's behalf.

### Cash and remittance

The cash section separates:

- cash this Collector physically recorded;
- cash accepted from another Collector;
- cash handed to another Collector and accepted;
- current cash held;
- eligible unremitted cash;
- submitted Management remittances;
- accepted/rejected Management remittances;
- cash-over or other reconciliation exceptions when those protected records
  exist.

Each remittance row shows reference, collection date, total, item/client count,
submission time, handover evidence state, recipient, and current status. A
pending row has one `Review remittance` action that navigates to the existing
full itemized review. Acceptance/rejection remains full-review only and keeps
the current acknowledgement, physical-count, reason, permission, custody, and
audit safeguards.

No quick accept, swipe action, inline amount edit, or bulk decision is added.

## Daily Route Snapshot and Visit Evidence

### Why a snapshot is required

`lending.collector_area_assignments` represents current assignment, not an
immutable historical manifest. A correct route review must preserve who and
what was assigned for the business date even after an area, client, loan,
schedule, or Collector changes. Past routes must not be regenerated from
current state.

### Additive PostgreSQL records

Introduce additive tables with guarded, idempotent migrations:

- `lending.collector_daily_routes`
  - route-day UUID;
  - Philippine business date;
  - assigned Collector user UUID;
  - snapshot version and source digest;
  - prepared server timestamp and preparing actor/process;
  - status fields that never overwrite financial records;
  - unique key on business date, Collector, and snapshot version.
- `lending.collector_daily_route_entries`
  - route-day UUID and stable entry UUID;
  - route sequence and area sequence;
  - snapshotted area label, client UUID, and loan UUID;
  - schedule/loan evidence references and authoritative scheduled amount for
    the date;
  - assignment and loan-state version evidence;
  - immutable creation metadata.
- `lending.collector_route_visit_results`
  - visit-result UUID, route entry, business date, and authenticated actor;
  - closed result code for nonfinancial visit outcomes;
  - server timestamp, approved device, optional structured concern category,
    and bounded note;
  - links to an official transaction when a financial result exists;
  - append-only correction/reversal linkage rather than destructive updates.

The migration does not backfill invented historical routes. Existing past
dates remain explicitly unavailable unless authoritative legacy evidence is
later inventoried and imported through a separately reviewed migration.

### Route preparation

The backend provides one idempotent route-day preparation service. The
Management list starts from every active Collector account and left-joins any
prepared manifest, so an unprepared Collector appears as `missing_route`
instead of disappearing. Preparation follows this exact order:

1. the Collector `routes/today` request idempotently ensures only the
   authenticated Collector's current-day snapshot before returning the route;
2. the Management list remains read-only and reports every missing snapshot;
3. Management may use the explicit protected `Prepare missing routes` action
   to snapshot the remaining active Collectors for the current business date;
4. no API prepares or rewrites a past date automatically.

Preparing a route is operational metadata, not a payment or balance mutation.
The actor/process and server time are audit-visible. Once official activity is
linked to a route day, assignment entries are immutable. An emergency same-day
assignment correction creates a new snapshot version with explicit reason and
preserves the prior manifest and linked evidence.

### Visit-result precedence

The read model applies deterministic precedence:

1. a non-voided official financial/PASS transaction is the authoritative
   collection outcome;
2. a linked corrected outcome supersedes display of the prior value but keeps
   both records visible in audit detail;
3. an explicit nonfinancial visit result applies only when no official
   financial/PASS result exists for that route client and date;
4. absence of both is `not_recorded`.

Collector Flutter may later expose structured visit-result capture from the
assigned route. That write requires a separate test-first slice, exact
permission, active approved device, idempotency, and audit evidence. Management
review does not fabricate the missing result.

## API Contract

Add canonical Management routes with mobile aliases excluded from generated
schema:

- `GET /api/v1/management/collector-daily-routes`
- `GET /api/mobile/v1/management/collector-daily-routes`
- `GET /api/v1/management/collector-daily-routes/{route_day_id}`
- `GET /api/mobile/v1/management/collector-daily-routes/{route_day_id}`
- `POST /api/v1/management/collector-daily-routes/prepare`
- `POST /api/mobile/v1/management/collector-daily-routes/prepare`

List query parameters are `date`, optional `q`, optional closed `status`,
`limit`, and `offset`. The date is a Philippine business date and defaults to
the server's current Asia/Manila date. Detail takes only the opaque route-day
UUID; the server resolves its date and Collector.

The prepare body contains the current Philippine business date and a bounded
reason. The server rejects past/future dates, duplicate generation side
effects, and preparation after an incompatible route version has official
activity. Normal duplicate calls return the existing snapshot result.

### List response shape

```json
{
  "success": true,
  "data": {
    "business_date": "2026-08-29",
    "generated_at": "2026-08-29T04:20:30.123456+00:00",
    "currency": "PHP",
    "rows": [
      {
        "route_day_id": "uuid",
        "collector_name": "Collector One",
        "areas": ["Cardona", "Morong"],
        "assigned_client_count": 22,
        "recorded_client_count": 18,
        "payment_client_count": 15,
        "pass_client_count": 3,
        "advance_client_count": 2,
        "route_collection_total": "8400.00",
        "cash_held_total": "8100.00",
        "unremitted_total": "3100.00",
        "submitted_total": "5000.00",
        "received_total": "0.00",
        "status": "submitted",
        "status_message": "One remittance awaits Management review."
      }
    ]
  }
}
```

Money is always a nonnegative fixed decimal string with response-level PHP
currency. Counts are nonnegative integers. Names and areas are display fields;
opaque user IDs are not required in the list payload. Unknown status codes fail
closed in Flutter rather than displaying a misleading state.

Detail returns the row facts plus ordered route entries, custody movements,
reconciliation exceptions, and linked remittance summaries. It does not return
government IDs, passwords, auth metadata, unrestricted CRM notes, raw device
identifiers, or unrelated client history.

## Authentication, Permissions, and Privacy

Every route requires bearer authentication, active account, active approved
device, canonical `management` role, and a new exact
`collection.route.review` permission. Seed the permission for Management only.
Do not grant it to Employee, Collector, or Client by default.

Additional rules are:

- linked remittance summaries require `remittance.view`;
- opening a full remittance continues to require its existing view scope;
- acceptance/rejection continues to require `remittance.receive` and recipient
  authority;
- route review permission never grants payment creation, correction, void,
  route administration, account management, or unrestricted CRM access;
- a future Employee assignment can receive `collection.route.review`
  explicitly without receiving `remittance.receive`;
- the backend omits or denies protected detail; Flutter visibility is defense
  in depth only;
- error responses never interpolate client names, balances, Collector IDs,
  route contents, or SQL details.

The Management list is online-only. Flutter does not cache a route snapshot as
official review evidence. Collector offline route caching remains separately
encrypted and scoped to the authenticated Collector; it is not reused for
Management review.

## Backend Read Model and Reconciliation

Create focused API, repository, and service modules rather than adding more
responsibilities to the existing Loan Operations repository. The list query
uses the immutable route-day tables as its population and joins authoritative
transactions, covered-date allocations, correction/void state, custody
movements, and remittances.

The repository must derive route and custody totals separately:

- route totals join by snapshotted assigned client/loan ownership;
- original-recorder evidence comes from official transaction actor fields;
- custody totals use current custody/handover records;
- submitted/received totals use linked Management remittances;
- rejected remittances do not clear custody;
- PASS and voided entries never increase cash;
- one receipt bundled in one remittance is counted once even when it covers
  multiple contractual dates;
- corrected/voided history remains visible but only the current official state
  contributes to totals;
- accepted Collector-to-Collector handoffs transfer custody but do not change
  assigned-route collection attribution;
- cash over remains a separate protected exception and is not forced into a
  client, route, or income total.

The list read uses one coherent PostgreSQL statement snapshot. Detail may use a
separate request and snapshot because it is explicitly refreshed before any
remittance decision. The existing remittance mutation performs its own fresh
server checks and never trusts row totals supplied by Flutter.

## Failure and Stale-State Behavior

- Initial load failure shows no totals and leaves other Management launchers
  usable.
- Refresh failure may retain the last in-memory result with its original server
  time and a visible stale warning; it is not persisted across sessions.
- A missing route is an explicit row/status, not a zero-filled normal route.
- A malformed money, count, date, status, or item relationship fails the
  affected response; Flutter does not coerce it to zero.
- Late refresh responses cannot replace a newer date/filter request.
- Opening a row refreshes detail from the backend. Opening remittance review
  refreshes the remittance again through the existing repository.
- If assignment, custody, transaction, or remittance evidence changes after
  display, protected actions reject stale evidence and require refresh.
- Historical dates without a snapshot display `No authoritative route
  snapshot` and never fall back to current assignments.

## Audit Rules

Read-only list/detail access does not write a financial audit event. The
following actions remain auditable:

- route-day preparation and snapshot version replacement;
- assignment correction reason and actor;
- visit-result creation/correction/reversal;
- collection correction/void;
- Collector-to-Collector handoff submission/decision;
- Management remittance review acknowledgement, acceptance, rejection,
  physical-count evidence, and custody transfer;
- protected reconciliation/cash-over resolution.

No route, visit, transaction, custody, remittance, or audit history is
hard-deleted merely because it was wrong, superseded, rejected, or corrected.

## Test-First Delivery

### Migration and PostgreSQL tests

Prove:

- guarded migration is additive and rerunnable;
- one current-day manifest is created idempotently per Collector/version;
- route order, area order, client, loan, schedule, assignment, and state
  evidence are preserved;
- existing dates are not backfilled with invented routes;
- a route with official activity cannot be silently rewritten;
- emergency replacement preserves the old version and requires reason/actor;
- visit results are append-only and obey precedence with official payments,
  PASS, corrections, and voids;
- cross-route recorder and assigned-route attribution remain distinct;
- Collector-to-Collector acceptance transfers custody without changing route
  ownership;
- rejected and submitted remittances retain custody correctly;
- route, held, unremitted, submitted, received, and exception totals reconcile
  exactly with no double-counted covered dates or bundled receipts.

### FastAPI tests

Prove:

- canonical and mobile aliases have identical contracts;
- active identity and approved device are required;
- canonical Management role and exact `collection.route.review` are both
  required;
- `remittance.view` controls linked remittance visibility;
- `remittance.receive` is not implied by route review;
- current Asia/Manila date default is independent of host timezone;
- search, status, date, limit, and offset are parameterized and bounded;
- every active Collector appears, including missing/no-activity route states;
- list/detail money is serialized as exact decimal strings;
- historical missing snapshots fail explicitly;
- prepare is current-day-only, idempotent, reasoned, and audited;
- response and error bodies contain no prohibited identity/device/auth data;
- database errors return safe service-unavailable responses with no partial
  totals.

### Flutter tests

Prove:

- `Collector routes` appears only with the exact permission;
- a 360-pixel phone with enlarged text renders compact rows without overflow;
- rows display assigned/recorded, Pay/PASS/ADV, route, held, and unremitted
  fields without local recomputation;
- row statuses and messages map from the closed backend codes;
- route entries retain server route order and show `Not recorded` honestly;
- cross-route entries show original recorder and separate custody attribution;
- missing route, empty route, load failure, stale refresh, unknown status, and
  malformed payload states fail safely;
- tapping Review opens current detail, and tapping a remittance opens the
  existing full protected review rather than accepting inline;
- stale responses cannot replace a newer date or filter;
- unauthorized remittance detail and action controls are absent;
- no mutation occurs from list/row expansion.

### Acceptance review

Use disposable PostgreSQL and local auth/backend only. The review dataset must
include:

- one ordinary assigned-route payment;
- one PASS;
- one ADV allocation;
- one assigned client with no recorded outcome;
- one cross-route payment held by the visiting Collector;
- one accepted Collector-to-Collector handoff;
- one unremitted Collector balance;
- one submitted Management remittance;
- one accepted and one rejected remittance;
- one correction or void requiring attention;
- one active Collector with a missing/no-activity route.

Management emulator review must verify the compact row, route order, client
detail, custody separation, and transition to full remittance review. It must
not accept real money, write a live database, mark CA2 approved, merge the Draft
PR, or deploy production.

## Phased Implementation and Release Order

1. **Authoritative route-day foundation** — additive permission, snapshot,
   entry, visit-result, version, and audit schema with disposable PostgreSQL
   tests.
2. **Route preparation and Collector alignment** — idempotent current-day
   preparation, Collector route reads from the same manifest, and safe handling
   for missing/emergency versions.
3. **Visit-result capture** — structured Collector nonfinancial visit outcomes
   with active-device, permission, idempotency, and append-only evidence.
4. **Management read APIs** — list/detail read models with route/custody
   separation and permission matrix.
5. **Management mobile rows** — compact dashboard launcher, list rows, filters,
   route detail, and safe remittance navigation.
6. **Desktop parity** — consume the same APIs/read model in the primary office
   platform using a denser table, without a second calculation path.
7. **Client-row slice** — implement the separately approved compact client row
   using current authoritative detail/schedule-summary fields; add a full
   schedule action only after its schedule-read contract is separately
   approved and tested.
8. **Acceptance and guarded rollout** — exact-head tests, Draft PR review,
   disposable migration rehearsal, authenticated local emulator/Desktop
   review, then separately authorized production migration and release.

Each phase remains incomplete until its exact tests and review evidence pass.
No phase authorizes production mutation, PR merge, or platform approval on its
own.

## Non-Goals

- Do not calculate official balances, schedules, cash, route status, or
  remittance differences in Flutter or Desktop UI.
- Do not reuse the Collector's encrypted offline cache as Management evidence.
- Do not let Management impersonate a Collector or call a Collector-scoped
  route endpoint with a supplied user ID.
- Do not treat scheduled due as cash expected or as a shortage.
- Do not accept/reject remittance from a summary row.
- Do not merge assigned Collector, original recorder, custodian, and Management
  receiver identities.
- Do not reconnect legacy local Client/Staff portals or Desktop JSON/PDF route
  files as a second authority.
- Do not invent historical route snapshots or installment schedules.
- Do not score Collector performance or automate disciplinary conclusions from
  missing outcomes.
- Do not change accounting posting, New Client Fund, renewal funding, ECL,
  payroll, or other unrelated platform modules in this delivery.

## Approval Boundary

Approval of this design authorizes writing an implementation plan only. It does
not authorize code implementation, live migration, production data access,
service deployment, PR merge, CA2 approval, or remittance decisions. Those
remain separately reviewed and explicitly authorized steps.
