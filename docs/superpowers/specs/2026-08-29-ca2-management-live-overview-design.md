# CA2 Live Management Overview Design

**Date:** 2026-08-29

**Repository:** `GILBIC/spina-lending-app`

**Starting commit:** `cab5737bce8a8d79e052dda9149f3e5cee162e4b`

**Branch:** `codex/ca2-management-live-overview`

**Parent:** Draft PR #376, `codex/ca2-staff-device-admin`

**Roadmap:** Frozen Master Issue #296, CA2 and CB1

## Outcome

Turn the existing Management mobile dashboard into a live, read-only command
overview without making Flutter a source of financial or authorization truth.
An authenticated and approved Management device receives one coherent backend
snapshot containing the common portfolio and collection indicators it may see,
plus only those specialized work queues allowed by its exact server-derived
permissions. Each displayed metric opens an existing protected workflow.

This is a focused CA2 mobile checkpoint in the shared Flutter codebase. It does
not replace SPINA Desktop as the intended primary office platform, create a
second dashboard ledger, introduce financial policy thresholds, calculate New
Client Fund capacity, finish accounting, check CA2/CB1 complete, approve the
Android or iOS experience, merge a pull request, deploy, restart a protected
service, or mutate a protected/live database.

## Current Behavior and Intended Behavior

### Current implemented behavior at the starting commit

- `ManagementDashboard` is a purpose-grouped launcher with six sections and 21
  destinations. It does not request or display live counts or money totals.
- Loan Management already obtains an authoritative portfolio summary, and Loan
  Operations already obtains collection/remittance summary data, but those
  screens issue separate requests and represent different database reads.
- Renewal, remittance, account, device, support, registration, and notification
  workflows already have protected APIs and existing destination screens.
- Management launcher visibility is based on the permission set returned by the
  server at login, while every protected backend request revalidates identity,
  active device, role, and/or permission.
- There is no materialized Management-dashboard table and no migration reserved
  for this overview.

### Intended behavior after this slice

- The first dashboard content is a refreshable `Live overview` region above the
  existing launcher groups.
- One FastAPI request returns one PostgreSQL statement snapshot with a server
  timestamp and stable metric keys.
- Common lending and collection indicators require both the Management role and
  `management.dashboard.view`.
- Specialized queue metrics are omitted unless the actor also has the exact
  permission for their destination workflow.
- Nonzero queue values mean that work is waiting for attention. The system does
  not invent risk, cash, growth, or approval thresholds.
- Selecting a metric opens the existing protected workflow associated with its
  key; no dashboard card performs a financial or approval mutation.
- If the snapshot cannot load, the existing launcher groups remain usable and
  the overview shows an online-data warning with retry.

### Intended future behavior outside this slice

SPINA Desktop remains the intended primary Management and Employee office
platform. It will ultimately expose the authoritative financial position,
maker-checker accounting queues, cash by custodian/location, New Client Fund,
renewal funding, and safe new-client capacity recommendations. Those functions
depend on separately reviewed accounting, fund-allocation, liquidity-policy,
and migration designs. This mobile overview must later consume those backend
authorities; it must not estimate them from balances already available in
Flutter.

Desktop being the primary office platform does not make mobile a reduced role
model. SPINA adopts functional capability parity for Management and Employees:
every capability authorized in Desktop must ultimately have an equivalent in
the shared mobile app under the same canonical role and exact permission. The
presentation may differ by screen size and risk—a dense Desktop workspace may
become a guided mobile sequence—but both clients must call the same FastAPI
authority, act on the same PostgreSQL records, enforce the same maker-checker
boundary, and produce the same official outcome. Platform parity is delivered
incrementally and verified per workflow; it is not a reason to expose a legacy
local Desktop calculation or ship all unfinished modules in this checkpoint.

## Binding Decisions

- FastAPI remains the only application-data boundary. Flutter does not query
  PostgreSQL or Supabase administration data directly.
- PostgreSQL records remain authoritative for loans, balances, collections,
  remittances, requests, devices, and notifications. Supabase Auth proves
  identity but does not supply dashboard roles or totals.
- The endpoint requires the canonical `management` role and
  `management.dashboard.view`. Having a specialized permission alone does not
  grant dashboard access.
- The server, not the browser/mobile client, decides which specialized metrics
  are included. An unauthorized metric is absent from the response rather than
  returned as zero, null, redacted, or disabled.
- One repository method executes one parameterized SQL statement. Its common
  table expressions aggregate existing authoritative tables and return one row.
  No materialized view, cache table, scheduled refresh, trigger, or migration is
  introduced.
- Counts and amounts are current snapshot facts, not manually entered dashboard
  totals. Monetary values use PostgreSQL numeric values serialized as decimal
  strings in Philippine pesos.
- `generated_at` is the database snapshot timestamp in UTC. Flutter uses it only
  to explain freshness and never advances it locally.
- Stable metric keys are an API contract. Flutter supplies labels, icons,
  presentation order, and destination mapping for known keys. Unknown keys are
  ignored safely and recorded in test-visible diagnostics; malformed known
  metrics fail the overview request.
- Zero is a legitimate authorized value and is shown. Omission means that the
  actor lacks the specialized permission or the key is unknown to that client.
- The endpoint returns aggregate facts only: no client names, user IDs, raw or
  hashed device identifiers, receipt numbers, support text, or request notes.
- No overview value authorizes a mutation. Destination APIs recheck the active
  device and exact permission at request time.
- The overview is online-only. Flutter does not persist, invent, queue, or use a
  stale snapshot as official current state.
- Management and Employee capability definitions are cross-platform. Desktop
  and mobile may use different layouts, but neither platform may define a
  different role, permission meaning, financial rule, approval result, or
  official record. A capability is considered cross-platform complete only
  after both clients pass the same backend contract and role/permission matrix.

## API Contract

Add one read-only router with the same canonical/mobile alias pattern used by
the current Management APIs:

- `GET /api/v1/management/dashboard-overview` — canonical documented route;
- `GET /api/mobile/v1/management/dashboard-overview` — compatibility alias,
  excluded from the generated schema.

The request has no query parameters or body. It requires `Authorization: Bearer
<token>` and `X-Device-Id`, resolved through `authenticated_device_context`.
After device authentication, the route explicitly checks the `management` role
and then checks `management.dashboard.view` against the returned server context.
Stable denials are:

- HTTP 401 for missing, invalid, or expired identity;
- HTTP 400 for a missing/invalid device header;
- HTTP 403 for a pending, revoked, or otherwise unauthorized device;
- HTTP 403 with `management_role_required` when the actor is not Management;
- HTTP 403 with `management_dashboard_permission_required` when the role is
  correct but `management.dashboard.view` is absent;
- HTTP 503 with a safe `management_overview_unavailable` message when the
  authoritative snapshot cannot be read.

The role and permission checks must be explicit and independently tested. The
API returns no partial payload after an authentication, authorization, parsing,
or database error.

### Response shape

```json
{
  "success": true,
  "data": {
    "generated_at": "2026-08-29T04:15:30.123456+00:00",
    "currency": "PHP",
    "metrics": [
      {
        "key": "portfolio.active_clients",
        "count": 128
      },
      {
        "key": "portfolio.outstanding_balance",
        "amount": "987654.32"
      },
      {
        "key": "collections.latest_day",
        "count": 94,
        "amount": "41250.00",
        "as_of_date": "2026-08-28"
      },
      {
        "key": "queues.remittances_assigned",
        "count": 3,
        "amount": "18500.00"
      }
    ]
  }
}
```

Each metric must contain exactly one known `key` and at least one of `count` or
`amount`. `count` is a nonnegative integer. `amount` is a nonnegative, fixed
decimal string without a currency symbol; the response-level currency applies
to every amount. `as_of_date` is present only where the metric describes a
specific business date. JSON numbers are never used for money.

The metrics array uses the fixed order in the following table. This order is
stable for existing keys, even though Flutter also maps by key.

## Metric Semantics and Permissions

| Metric key | Returned value | Authoritative source and exact meaning | Additional permission | Destination |
| --- | --- | --- | --- | --- |
| `portfolio.active_clients` | `count` | Distinct client IDs among loans whose normalized status is `active` | none | Loan Management |
| `portfolio.active_loans` | `count` | Loans whose normalized status is `active` | none | Loan Management |
| `portfolio.overdue_loans` | `count` | Active loans with due date before PostgreSQL `current_date` and authoritative remaining balance greater than zero | none | Loan Management |
| `portfolio.outstanding_balance` | `amount` | Sum of authoritative remaining balance for active loans, falling back to principal only under the existing loan-state rule | none | Loan Management |
| `collections.latest_day` | `count`, `amount`, optional `as_of_date` | Non-voided, non-PASS entries on the latest collection date; amount excludes PASS | none | Loan Operations |
| `collections.unremitted` | `count`, `amount` | Non-voided, unlocked collection transactions not attached to a remittance; amount excludes PASS | none | Loan Operations |
| `queues.remittances_assigned` | `count`, `amount` | Submitted, not received, unrejected remittances whose recipient user is the actor | `remittance.receive` | Remittance Review |
| `queues.renewals_protected` | `count` | Renewal requests whose status is `pending`, matching the default protected Management renewal-workflow query | `renewal.manage` | Renewal Management |
| `queues.staff_registrations` | `count` | Application users in `pending` status with a canonical staff role | `account.manage` | Staff & Devices |
| `queues.client_registrations` | `count` | Client registration requests whose status is `pending` | `account.manage` | Client Registrations |
| `queues.collector_mobile_devices` | `count` | Pending Android/iOS devices owned by an account with the Collector role | `device.manage` | Staff & Devices |
| `queues.borrower_support` | `count` | Client support requests in `open` or `answered` status | `support.manage` | Client Support |
| `activity.unread` | `count` | Unread activity notifications whose recipient user is the actor | none | Activity & Alerts |

`none` in the additional-permission column means the metric is part of the
baseline already protected by Management role plus
`management.dashboard.view`; it does not mean public access.

The protected-renewal count must match the existing Management renewal-workflow
query's `status = 'pending'` predicate. The overview does not add eligibility,
signer, release, activation, or funding interpretations to that queue.

For `collections.latest_day`, an empty collection table returns `count: 0`,
`amount: "0.00"`, and omits `as_of_date`. For all other authorized metrics,
empty authoritative sets return explicit zeros. Negative counts or monetary
totals are invalid for this overview and cause a safe server error rather than a
misleading card.

## Backend Design

Create a focused `management_dashboard_overview_api.py` and
`management_dashboard_overview_repository.py`. The router owns authentication,
role/permission enforcement, safe error translation, and serialization. The
repository owns the one-statement snapshot and returns immutable typed records;
it knows nothing about HTTP or Flutter labels.

The repository method receives:

- `actor_user_id` for assigned-remittance and unread-notification scoping;
- booleans for `remittance.receive`, `renewal.manage`, `account.manage`,
  `device.manage`, and `support.manage`.

The SQL statement uses CTEs for portfolio, latest collection date/summary,
unremitted collections, and each authorized queue. Specialized CTE predicates
are gated by their boolean parameter and return `NULL` when permission is absent.
The payload builder adds a specialized metric only when its flag is true and its
typed value is non-null. This makes omission a backend guarantee and avoids
zero-filled inference.

The read runs through one `open_connection()` context and one `cursor.execute()`
call. PostgreSQL's statement-level snapshot supplies coherence under the normal
transaction isolation level. The query must not lock application rows, update
last-seen fields, write an audit entry, or call another repository that opens a
second connection.

The implementation may extract shared SQL predicate constants/helpers only
when doing so reduces drift without changing existing endpoint responses. It
must not rewrite the current Loan Management, Loan Operations, renewal,
remittance, account, device, support, or notification APIs as part of this
slice.

Register the router once in `main.py`. Both route decorators must invoke the
same function and repository dependency so canonical and mobile paths cannot
diverge.

## Flutter Design

Add immutable domain types in the existing Management core boundary:

- `ManagementDashboardOverview` with UTC `generatedAt`, currency, and known
  metrics;
- `ManagementDashboardMetric` with a validated key, optional count/amount/date,
  and contract validation;
- a closed metric-key mapping used for label, icon, emphasis, and destination.

Add an injectable `ManagementDashboardOverviewRepository` plus its HTTP
implementation. It loads the current installation identity, sends the bearer
token and `X-Device-Id`, calls exactly
`/api/mobile/v1/management/dashboard-overview`, accepts only the documented
success envelope, parses money as a decimal-safe display value, and preserves
safe FastAPI error messages. It performs no financial calculation, role
inference, thresholding, metric fabrication, or local persistence.

Convert `ManagementDashboard` to stateful overview loading while retaining the
existing exhaustive launcher registry and destination switch. The page:

1. renders the title and existing launcher groups immediately;
2. starts one overview request when the dashboard is first displayed;
3. shows compact skeletons only inside the overview region;
4. replaces them with grouped fact and attention cards on success;
5. exposes pull-to-refresh and an explicit retry action;
6. shows the server `generated_at` time as `Updated ...`;
7. preserves launchers with an inline online-data warning on failure.

The metric presentation has two small groups:

- `Today & portfolio` for common portfolio/collection facts;
- `Needs attention` for nonzero queue and unread-activity metrics.

Authorized zero queue metrics render one calm `No pending items` state rather
than many zero cards. Portfolio facts still render at zero. An actor with no
specialized permissions sees only baseline facts and actor-specific unread
activity; the UI does not claim that hidden queues are empty.

Every known metric has one exact destination from the table above. A card tap
reuses the same navigation function and tap-time permission check as the
corresponding launcher. Money/date formatting is presentation-only and cannot
change the underlying value.

The repository currently has a protected Past Due reporting API but no dedicated
Management Past Due mobile screen. Therefore the overdue metric opens the
existing Loan Management screen, where active overdue loans are already visible.
A dedicated Past Due Management screen remains a later cross-platform parity
slice and is not invented inside this overview checkpoint.

### Refresh and stale-response protection

The dashboard assigns a monotonically increasing request generation before each
load. Only the latest generation may replace displayed state. Pull-to-refresh
or retry can supersede an earlier request; a late response is ignored. While a
refresh is in flight, the last successfully displayed snapshot may remain
visible with a progress indicator, but it is visibly marked as refreshing and
is never persisted across a fresh dashboard/session. A failed refresh keeps the
last snapshot labeled with its original server time and shows a retryable
warning; an initial failure shows no totals.

Authentication/session-expiry and revoked-device failures continue through the
existing global handling. A 403 within the overview says that current server
access no longer permits live Management data and leaves safe navigation/back
actions available. Malformed 2xx data is an error, never an empty overview.

## Security and Privacy Review Rules

- API and repository tests must prove both Management role and dashboard
  permission. Flutter visibility tests are defense in depth only.
- Specialized permission combinations are tested individually and in mixtures;
  the response must contain no key, count, amount, or placeholder for an
  unauthorized domain.
- Actor-scoped SQL always uses the authenticated application user UUID, never a
  caller-supplied query value.
- Aggregate responses contain no direct identifiers or free text. Error
  responses do not interpolate SQL, IDs, names, balances, or support content.
- The endpoint is read-only and intentionally creates no audit event. Existing
  destination reads/mutations retain their own audit rules.
- The overview does not expose raw browser/mobile metadata and does not treat
  Flutter's cached permission set as authority.
- Existing legacy Client/Staff portals remain external/legacy until inventoried
  and migrated; this endpoint does not reconnect them or create another backend.

## Test-First Delivery Plan

### Backend red-green coverage

Tests fail before production changes and then prove:

- canonical and mobile alias paths return the same response shape;
- valid bearer identity and active device are required;
- a non-Management actor with the dashboard permission is denied;
- Management without `management.dashboard.view` is denied;
- baseline-only Management receives exactly the seven baseline metrics;
- each specialized permission adds only its authorized metric(s), including the
  two separate `account.manage` queues;
- unauthorized specialized metrics are absent, never zero/null placeholders;
- remittance totals are actor-recipient scoped, submitted, unreceived, and
  unrejected;
- unread activity is actor-recipient scoped;
- Collector pending-device count excludes web/desktop devices, non-Collector
  owners, active devices, and revoked devices;
- staff and client pending registrations use their separate authoritative
  tables and do not double-count;
- support includes exactly `open` and `answered`;
- renewal count matches the existing protected workflow predicate;
- loan, overdue, outstanding, latest-day, PASS, void, locked, and remittance
  semantics match the metric table;
- empty data produces documented zero/date behavior;
- monetary values are fixed decimal strings and never floating-point JSON;
- one repository call executes one SQL statement and returns one generated UTC
  timestamp;
- database failures produce the safe availability response with no partial
  data;
- the router is registered once and both decorators share one implementation.

Repository behavior is verified against disposable PostgreSQL fixtures, not
only a fake repository. API authorization and serialization use focused fakes.
The complete backend suite and migration/bootstrap tests must remain green;
tests confirm that no migration was added.

### Flutter red-green coverage

Tests fail before production changes and then prove:

- exact URL, bearer/device headers, success-envelope parsing, decimal handling,
  optional date handling, and safe error messages;
- malformed known metrics, negative values, missing values, duplicate known
  keys, invalid currency, and invalid timestamps fail closed;
- unknown future metric keys do not crash or fabricate a card;
- initial loading affects only the overview region;
- baseline facts, nonzero attention queues, all-zero attention state, and
  permission-omitted queues render correctly;
- initial error, retry, refresh, failed refresh, and session/device failures are
  distinct and recoverable;
- a superseded late response cannot replace newer overview state;
- every metric key maps to the exact existing protected destination;
- card and launcher navigation share tap-time permission enforcement;
- the existing six launcher groups and all 21 destinations remain reachable
  when the overview fails;
- 360x640 and larger layouts at 1.3x text scale scroll without overflow;
- prior Management navigation, staff/device administration, auth parity,
  account settings, and online-only policy tests remain green.

## Verification and Release Evidence

Before the stacked Draft pull request is described as exact-head green:

- run changed-Python compile/syntax checks;
- run focused backend unit/API/disposable-PostgreSQL tests;
- run the complete backend suite and repository-required lint/format/type/static
  controls;
- run focused Flutter model/repository/widget/navigation/layout tests;
- run full `flutter test` and `flutter analyze --fatal-infos`;
- obtain independent specification and code/standards reviews with no unresolved
  Critical or Important finding;
- inspect the exact diff for PII, permission omission, SQL statement count, and
  scope drift;
- push the exact commit and wait for all five permanent CI lanes on that same
  head;
- build a debug Android review APK from the exact head, record size and SHA-256,
  install it in the emulator, and prove cold launch has no fatal exception;
- perform authenticated Management acceptance only with an authorized review
  account/device; if unavailable, keep that acceptance gate explicitly open.

The pull request stays Draft and targets Draft PR #376's branch. The artifact is
an unsigned/debug review build. No merge, iOS signing/archive, production
signing, distribution, deployment, protected-service restart, or protected/live
database action is authorized by this design.

## Alternatives Rejected

### Flutter composes existing APIs

Calling Loan Management, Loan Operations, remittance, renewal, account, device,
support, and notification endpoints from the dashboard would produce snapshots
from different times, add mobile latency and failure modes, and increase the
chance that a client accidentally requests or infers an unauthorized queue.

### Dashboard/materialized tables

Persisting derived dashboard totals would require refresh policy, reconciliation,
staleness controls, migration, and new audit questions while authoritative
tables already support the small aggregate snapshot. That complexity is not
justified for this read-only slice.

### Client-defined thresholds or recommendations

Coloring counts by invented limits or estimating whether cash is sufficient for
new clients would mix presentation with unapproved liquidity policy. New Client
Fund and renewal-fund recommendations require a separately approved server-side
domain model using available cash, reserved obligations, expected collections,
risk buffers, and lending policy.

## Scope Boundaries and Remaining V1 Work

This design deliberately does not:

- create or calculate New Client Fund, renewal fund, liquidity buffers, or a
  smart new-client capacity recommendation;
- add assets/liabilities/equity, cash by custodian, depreciation, ECL,
  profitability, reconciliation, or journal-approval totals;
- add mutation shortcuts, bulk approvals, protected corrections, or reversals;
- add offline financial posting, a financial outbox, quarantined recovery, or
  background retry;
- add PIN/biometric step-up authentication;
- duplicate Desktop workflows on the website or reconnect a legacy portal;
- implement every remaining Desktop-equivalent Management and Employee mobile
  workflow in this dashboard checkpoint; those parity slices remain required
  V1 roadmap work rather than optional mobile enhancements;
- change loan, collection, remittance, renewal, account, device, support, or
  notification state semantics;
- claim Android/iOS acceptance or check a Master Issue checkbox from automated
  tests alone.

After this checkpoint, CA2 still requires authenticated Android Management
acceptance, broader review-screen consistency, the remaining usability decision,
and iOS evidence. CB1 still requires the complete operational/accounting
overview, protected approval queues, audit visibility, cross-platform
permission/idempotency/stale-source proof, and production acceptance. The wider
Master Issue #296 objective remains active.
