# Management Collector Route, Remittance, and Employee Activity Review Design

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

Management also receives a separate, permission-scoped Employee Activity
workspace under `People, access & requests`. It summarizes work employees have
performed or prepared across authorized domains and links Management to the
authoritative record and existing review flow. It is not an impersonation,
surveillance, payroll-disclosure, or second audit system.

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
- Employee work evidence is fragmented across domain records and
  `core.audit_logs`. Journals, remittances, renewals, corrections, and other
  records preserve actor, preparer, reviewer, or poster attribution where the
  module supports it, but Management has no unified Employee Activity list or
  per-employee work timeline.
- The existing Management `Alerts & activity` surface is recipient-scoped
  notification data. It is not a complete employee work ledger and must not be
  presented as one.

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
- Management opens `People, access & requests -> Employee activity` to see one
  compact row per active Employee, derived only from domains that the current
  Management user is authorized to review.
- Selecting an Employee opens a chronological, server-derived timeline of
  permitted Accounting, HR, Payroll, CRM/support, remittance/operations, and
  administration evidence. Each item links to the authoritative record or its
  protected review queue.
- Employee Activity never lets Management impersonate the Employee, silently
  modify an Employee draft, bypass maker-checker separation, or infer hidden
  work from redacted counts.

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

## Management Employee Activity Review

### Navigation and compact employee rows

Add one small `Employee activity` launcher under `People, access & requests`.
The first page provides a Philippine business-date range, Employee search,
closed domain/status filters, pull-to-refresh, and a visible server generation
time. It renders one compact row per active canonical Employee account:

```text
Employee Name · Accounting                         [Awaiting review]  >
Today 6 completed · 2 in progress · 1 awaiting Management
Last activity 10:42 AM · 1 item needs attention
```

The row displays only facts visible under the current Management user's exact
permissions:

- Employee display name and active organizational/function labels already
  authorized for staff administration;
- visible completed, in-progress, awaiting-review, and needs-attention counts;
- most recent visible activity time and domain;
- one server-derived status and explanatory message.

The backend returns no aggregate for a domain the Management user cannot
access. Flutter does not render a zero, redacted count, placeholder, or hidden
domain name because that would disclose the existence of protected work. This
is operational review, not productivity scoring; the row never ranks
employees, estimates effort, or makes disciplinary recommendations.

### Employee timeline

Selecting a row opens a chronological list of permitted evidence:

```text
Time | Domain | Action | Record/reference | Workflow state | Evidence | Review
```

Closed domain codes are `accounting`, `hr`, `payroll`, `crm_support`,
`remittance_operations`, and `administration`. Each timeline item includes:

- a stable server activity code and human-readable summary;
- authenticated actor and, when distinct, maker, checker, poster, or current
  assignee attribution;
- authoritative record type, opaque record ID, and safe display reference;
- business date, server timestamp, workflow state, and correction/reversal
  state;
- bounded evidence summary and an authorized link target;
- whether the item is informational, awaiting Management review, completed,
  or needs attention.

The link opens the owning domain's existing detail or protected approval flow.
The Employee Activity page never recreates the domain form or mutates its
record. Where no authorized destination exists yet, the item remains read-only
and explicitly says that detailed review is not currently available.

### Maker-checker and privacy controls

- The Employee remains the maker/preparer of work they recorded.
- Management may approve, reject, return, post, or request correction only
  through the owning module and only with that action's exact permission.
- The activity-review permission does not imply posting, payroll approval,
  remittance receipt, correction, reversal, user administration, or access to
  unrestricted client/employee content.
- A user cannot satisfy both maker and checker for the same protected workflow
  when the owning module prohibits self-approval.
- Corrections retain the original evidence and use the owning module's
  amendment, reversal, or supersession rules.
- Payroll amounts, medical/leave detail, disciplinary content, government IDs,
  support-message bodies, and client documents require their existing or newly
  approved exact domain permissions. Unauthorized domains and fields are
  omitted server-side.
- The system does not capture keystrokes, screenshots, background location,
  time-on-screen, or other invasive surveillance signals.

### Employee activity statuses

The backend derives one closed status from visible, authoritative work only:

- `no_activity` — no permitted activity exists in the selected range;
- `in_progress` — visible drafts or assigned work remain in progress;
- `awaiting_review` — at least one visible item awaits an authorized
  Management decision;
- `completed` — visible work exists and no visible item remains pending or in
  exception;
- `needs_attention` — a visible rejected, stale, unreconciled, failed, or
  correction-required item needs review.

`needs_attention` wins over `awaiting_review`, which wins over `in_progress`,
which wins over `completed`. Status describes workflow state, not employee
quality, attendance, compensation, or financial authorization.

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

### Employee Activity API

Add canonical Management routes with mobile aliases excluded from generated
schema:

- `GET /api/v1/management/employee-activity`
- `GET /api/mobile/v1/management/employee-activity`
- `GET /api/v1/management/employee-activity/{employee_user_id}`
- `GET /api/mobile/v1/management/employee-activity/{employee_user_id}`

List query parameters are `date_from`, `date_to`, optional `q`, optional closed
`domain`, optional closed `status`, `limit`, and `offset`. The maximum date
range is bounded by server policy. Detail uses the opaque Employee user UUID
plus the same bounded date/domain filters; it does not accept an arbitrary
role, permission, table, or SQL expression from the client.

The list returns server generation time, effective date range, and compact
Employee rows. The detail returns the selected row facts and a paginated
timeline whose items contain `activity_code`, `domain`, `occurred_at`,
`business_date`, safe record identity, workflow state, visible actor roles,
bounded evidence, and an authorized navigation target. New activity codes are
registered centrally; unknown codes fail closed in clients rather than being
mislabelled.

Counts, status, summaries, and timeline items are calculated only after domain
authorization. A hidden domain contributes nothing to the response and cannot
be inferred from totals. The APIs never return passwords, tokens, raw device
identifiers, private authentication metadata, unrestricted HR/payroll/CRM
content, or audit payload fields not approved for Management display.

## Authentication, Permissions, and Privacy

Every route requires bearer authentication, active account, active approved
device, canonical `management` role, and a new exact
`collection.route.review` permission. Seed the permission for Management only.
Do not grant it to Employee, Collector, or Client by default.

Employee Activity additionally requires canonical `management` role and a new
exact `employee.activity.review` permission. That permission authorizes only
the normalized list/timeline shell. Each source item also requires the exact
owning-domain view permission; links and protected actions require their
existing action permissions. Seed `employee.activity.review` for Management
only, but do not use it to grant all HR, Payroll, Accounting, CRM, remittance,
or administration data automatically.

Additional rules are:

- linked remittance summaries require `remittance.view`;
- opening a full remittance continues to require its existing view scope;
- acceptance/rejection continues to require `remittance.receive` and recipient
  authority;
- route review permission never grants payment creation, correction, void,
  route administration, account management, or unrestricted CRM access;
- a future Employee route-review workflow requires its own separately approved
  role/resource-scope contract; this Management endpoint is not opened merely
  by granting an Employee the permission string;
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

### Employee Activity read model

Create a focused, read-only Employee Activity module instead of expanding
`core.audit_logs` into a business workflow engine. The read model normalizes
approved evidence from two sources:

1. owning-domain records that already preserve maker, actor, reviewer, poster,
   assignee, status, and reversal/correction evidence; and
2. `core.audit_logs` entries whose registered action code and safe detail
   projection are explicitly approved for Management display.

A central activity registry maps each stable activity code to its domain,
source projection, timestamp semantics, safe summary builder, workflow status,
required domain view permission, and optional navigation target. Unregistered
audit actions and free-form payload fields are excluded. The read model does
not copy all business data into a new authoritative ledger and does not treat
an audit log string as proof of a business state that must be derived from the
owning record.

Employee population comes from active canonical Employee accounts, not legacy
Desktop role names. A later organizational-assignment model may add team or
department scope, but it must not silently infer reporting lines from activity
history. List counts and the timeline use the same permission-filtered event
projection and one coherent PostgreSQL statement snapshot per request.

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
- Employee Activity load failure shows no employee counts or timeline and
  leaves other Management launchers usable.
- An Employee with no visible activity is labelled `No permitted activity in
  this range`; the UI does not imply the Employee performed no work.
- A source item with a missing registered projection, malformed relationship,
  or revoked domain permission is omitted or fails the affected response
  according to server policy; Flutter never fabricates a summary.
- A permission change takes effect on the next request. The app does not retain
  protected activity in a persistent cross-session cache.
- Opening a linked record refreshes through the owning module, whose current
  permission and stale-state checks remain authoritative.

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

Opening Employee Activity does not create a false employee work event.
Security telemetry may record that Management accessed a protected domain,
subject to the platform's approved access-audit policy, but it is kept separate
from the Employee's business activity timeline. Any approval, rejection,
posting, return, amendment, reversal, payroll action, or remittance decision is
audited by the owning module and retains both maker and checker attribution.

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
- Employee Activity permission seed is additive and rerunnable;
- the Employee Activity projection includes only registered source/action
  codes, preserves actor/maker/checker identity, and derives business state
  from the owning record rather than free-form audit text;
- hidden domains contribute no rows, counts, timestamps, or status clues;
- corrected, reversed, rejected, superseded, and posted work retains permanent
  evidence without duplicate current-state counts.

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
- canonical and mobile Employee Activity aliases have identical contracts;
- canonical Management role and exact `employee.activity.review` are both
  required for the Employee Activity shell;
- every activity item additionally requires its registered domain view
  permission, and action permissions are never implied;
- date range, Employee search, domain, status, limit, and offset filters are
  bounded and parameterized;
- list counts, row status, timeline items, and last-activity timestamps contain
  visible-domain evidence only;
- inactive/non-Employee targets, unknown activity codes, malformed source
  relationships, and revoked permissions fail closed without protected data;
- maker-checker attribution remains distinct and self-approval rules remain in
  the owning workflow;
- sensitive payroll, HR, CRM, authentication, and device fields are absent
  without their exact authorization.

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
- `Employee activity` appears only with the exact shell permission;
- compact Employee rows render at 360 logical pixels with enlarged text and no
  productivity score or hidden-domain placeholder;
- row counts, statuses, timestamps, and timeline order are rendered from the
  server without local recomputation;
- domain/date/status/search filters reject stale responses and preserve server
  scope;
- an authorized timeline link opens the owning module, while an unauthorized
  or unavailable destination remains read-only;
- no employee record, draft, approval, or audit entry is mutated by opening a
  row or timeline item;
- protected Employee Activity data is not persisted across sessions.

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
- one active Employee with visible work in each initially registered domain;
- one Employee with no permitted activity in the selected range;
- one maker-checker item awaiting Management and one completed posted item;
- one rejected/corrected/reversed item that needs attention;
- one Management identity that can see the Employee Activity shell but lacks
  Payroll and HR domain access, proving no count or timestamp leakage;
- one fully unauthorized Management identity and one Employee identity.

Management emulator review must verify the compact row, route order, client
detail, custody separation, and transition to full remittance review. It must
also verify Employee row/timeline filtering, owning-record navigation, and
maker-checker separation without exposing a hidden domain. It must not accept
real money, write a live database, mark CA2 approved, merge the Draft PR, or
deploy production.

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
7. **Employee Activity registry and permissions** — add the shell permission,
   closed activity/domain codes, safe source projections, field allowlists, and
   permission-filtered normalization tests without copying business authority.
8. **Employee Activity read APIs** — add canonical/mobile list and timeline
   contracts with compact Employee rows, visible-domain aggregation, stable
   pagination/filtering, and owning-record navigation metadata.
9. **Employee Activity mobile and Desktop parity** — add the small Management
   launcher, compact rows, timeline filters, and safe record navigation using
   the same API/read model on both platforms.
10. **Client-row slice** — implement the separately approved compact client row
   using current authoritative detail/schedule-summary fields; add a full
   schedule action only after its schedule-read contract is separately
   approved and tested.
11. **Acceptance and guarded rollout** — exact-head tests, Draft PR review,
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
- Do not rank Employees, calculate productivity scores, or infer performance,
  attendance, misconduct, or compensation from the activity timeline.
- Do not capture keystrokes, screenshots, background location, time-on-screen,
  or other surveillance signals.
- Do not use `employee.activity.review` to bypass owning-domain permissions,
  maker-checker separation, protected actions, or sensitive HR/payroll/CRM
  field controls.
- Do not copy every domain record into a second Employee Activity authority or
  treat free-form audit text as the official business state.
- Do not let Management impersonate an Employee or silently edit an Employee's
  draft from the review workspace.
- Do not change accounting posting, New Client Fund, renewal funding, ECL,
  payroll, or other unrelated platform modules in this delivery.

## Approval Record

The Collector daily-route/remittance row architecture, compact client-row
direction, and permission-scoped Employee Activity architecture were approved
in the project review on 2026-08-29. The approved Employee Activity direction
is a separate Management workspace, uses authoritative domain/audit evidence,
requires domain permissions, preserves maker-checker controls, and excludes
impersonation and invasive surveillance.

## Approval Boundary

Approval of this design authorizes writing an implementation plan only. It does
not authorize code implementation, live migration, production data access,
service deployment, PR merge, CA2 approval, or remittance decisions. Those
remain separately reviewed and explicitly authorized steps.
