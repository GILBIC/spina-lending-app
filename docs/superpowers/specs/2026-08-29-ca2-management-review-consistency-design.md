# CA2 Management Review Consistency Design

**Date:** 2026-08-29

**Repository:** `GILBIC/spina-lending-app`

**Starting commit:** `99be748da8e08104d4aa6ea6d318805ba887e296`

**Branch:** `codex/ca2-management-review-consistency`

**Parent:** Draft PR #377, `codex/ca2-management-live-overview`

**Roadmap:** Frozen Master Issue #296, CA2 Management UI

## Outcome

Make every current state-changing Management workflow in the shared Flutter app
use one clear review pattern before Management commits an action. The pattern
must answer five operational questions:

1. What record or server source is being reviewed?
2. What is its current server-reported status?
3. What warnings or blockers are known?
4. What action may Management take next?
5. What exactly will happen if Management confirms that action?

This slice standardizes presentation and confirmation only. It does not create
a client-side workflow engine, grant permission, calculate a balance or
accounting result, change an API payload, or weaken the backend's final
revalidation. FastAPI and PostgreSQL remain authoritative. Flutter presents
facts received from the server and submits the same protected mutations that
exist at the starting commit.

## Current Behavior and Intended Behavior

### Current implemented behavior at the starting commit

- Management has separate mobile workflows for client registration, renewals,
  staff and devices, collection corrections, contract collection activation,
  No Collection, client support, accounting review, fiscal periods, General
  Journal, and opening balances.
- Protected actions already call FastAPI repositories, and the backend
  revalidates identity, active device, role, permission, record state, and
  request rules according to each endpoint.
- Many pages already show some useful detail or a confirmation dialog. The
  content and order differ by page: some lead with an internal status, some
  explain consequences only inside a dialog, and some leave the next permitted
  action to be inferred from enabled buttons.
- Pages define private notice cards, status labels, detail rows, and dialogs.
  There is no shared Management review component or explicit mutation-surface
  inventory, so later workflows can drift without a failing test.
- Several accounting screens appropriately explain that values are reference
  only or that posting is disabled, but primary copy still exposes internal
  stage names and implementation wording in places.
- Read-only Management pages such as the live overview, portfolio, loan
  operations, financial statements, accounting measurement, and the General
  Journal launcher do not themselves perform a protected mutation.

### Intended behavior after this slice

- Every known Management mutation surface displays the same five-part review
  structure, using screen-appropriate facts and plain language.
- The current status and review facts come from the record already returned by
  FastAPI. The UI does not infer missing eligibility, permissions, balances,
  readiness, or financial outcomes.
- The final action area states the exact immediate consequence next to the
  confirmation control. High-impact actions use a dedicated shared
  confirmation dialog; draft editing can place the same consequence contract
  inside its existing form to avoid double dialogs.
- Warnings are visually distinct from hard blockers. A blocker disables only
  the action the server data says is unavailable; it is not a substitute for
  backend authorization.
- Internal status codes, database field names, and implementation-stage labels
  are removed from primary instructions. Stable audit references and a raw
  server value may remain as secondary detail when needed for support or audit.
- Unknown or missing server facts are described honestly. The UI says that the
  information was not provided or that the status needs review; it never
  substitutes a favorable value.
- Existing repositories, endpoints, permissions, payloads, idempotency keys,
  uncertain-result recovery, refresh behavior, and server conflict handling
  remain intact.

### Intended future behavior outside this slice

Management and Employee functions must ultimately have functional capability
parity between SPINA Desktop and the shared mobile app, while using layouts
suited to each platform. The shared FastAPI backend, Supabase authentication,
PostgreSQL records, server-derived permissions, approved-device controls, and
permanent audit evidence remain common authority.

That wider direction includes complete accounting maker-checker controls,
assets/liabilities/equity, cash custody and reconciliation, New Client Fund,
renewal funding, smart new-client capacity recommendations, HR/payroll, client
relationship management, Client Web, selected Staff Web, iOS evidence, and
production release work. None of those unfinished domains is implemented or
declared complete by this presentation slice.

## Binding Decisions

- The shared pattern is a Flutter presentation component, not a workflow or
  authorization service.
- Each feature adapts its typed server response into review copy. A generic
  component must not interpret raw domain status strings or decide which action
  is permitted.
- The backend remains the final authority even when a button is enabled. Every
  mutation keeps its existing tap-time request and backend revalidation.
- No dashboard total, balance, eligibility, warning, accounting readiness, or
  approval result is calculated from unrelated Flutter state.
- Each action has a stable review-surface identifier used for widget keys and
  inventory tests. Identifiers are presentation/test contracts and are never
  sent to the backend as authority.
- Primary labels use plain operational or accounting language. Raw identifiers,
  UUIDs, idempotency keys, database codes, and audit references are secondary
  detail only and are not silently discarded where they are operationally
  necessary.
- An absent fact is not rendered as `No`, `Zero`, `Clear`, `Eligible`, or
  `Approved`. The page either omits optional detail or shows a neutral
  `Not provided by the server` message when the missing fact matters to the
  review.
- A server value unknown to the current client maps to `Status needs review`,
  with the escaped raw value available as secondary detail. It never maps to a
  known favorable state.
- Visual risk levels explain consequence; they do not change permissions,
  validation, authentication, step-up requirements, audit behavior, or API
  routing.
- Existing successful, failed, denied, stale, and uncertain-result outcomes
  keep their feature-specific recovery behavior.
- The implementation must not add a generic approval endpoint, local queue,
  second source of truth, or persistence of review data.

## Shared Review Contract

Add a small presentation module under
`gilbic_mobile/lib/src/features/management/review/`. It contains immutable
display types, the shared panel/dialog widgets, and the explicit surface
catalog. It must not import an HTTP repository or call an API.

### Presentation model

`ManagementReviewPresentation` contains only display-ready, non-authoritative
values supplied by the page:

- `surface` — one stable value from `ManagementMutationSurface`;
- `recordLabel` and `recordValue` — the human-recognizable record/source;
- `statusLabel` and optional `statusDetail` — a plain current server status;
- `facts` — zero or more concise label/value rows from the same server record;
- `warnings` — zero or more typed warning/blocker messages;
- `nextActionLabel` — the currently offered action in plain language;
- `consequence` — one precise sentence describing the immediate persisted or
  workflow effect of confirmation;
- `risk` — `routine`, `privileged`, or `protectedFinancial`, used only for
  presentation emphasis;
- `secondaryReferences` — optional audit/support identifiers shown below the
  operational content.

The constructor validates presentation invariants: record, status, next action,
and consequence cannot be blank; labels are not accepted as raw nullable facts;
and a blocking warning requires the final action to be disabled by the calling
page. It cannot validate domain eligibility or permissions.

`ManagementReviewWarning` distinguishes:

- `information` — context Management should know;
- `caution` — a consequence or discrepancy requiring attention;
- `blocker` — the currently loaded server record says the action cannot
  continue.

The page supplies these values from its typed domain model. The shared module
does not contain a switch over renewal, accounting, loan, staff, or support
status codes.

### Review panel

`ManagementReviewPanel` renders the five questions in this fixed order:

1. `Reviewing` — record/source and the most useful identifying facts;
2. `Current status` — plain status plus any secondary technical detail;
3. `Check before continuing` — warnings or a calm `No server warnings` state;
4. `Next action` — the action offered by the current workflow;
5. `If confirmed` — the exact consequence.

The panel receives no callback and cannot perform a mutation. It has a stable
key of `management-review-<surface-id>`. Existing action controls remain owned
by the page so permissions, progress, form validation, and repository calls do
not move into a generic abstraction.

### Confirmation content

`ManagementReviewConfirmation` reuses the same presentation model inside an
`AlertDialog` or existing edit form. A dedicated helper may return `true` or
`false`; it never invokes a repository. Confirmation content repeats the
record, current status, warnings, action, and exact consequence so Management
does not have to remember information hidden behind the dialog.

Risk affects wording and color only:

| Risk | Use | Required final-action treatment |
| --- | --- | --- |
| `routine` | Create or edit an unposted draft, save a response | Consequence beside the save action; a second modal is optional |
| `privileged` | Approve/reject registration, change staff access, activate a workflow, release a renewal | Explicit confirm/cancel choice with consequence visible |
| `protectedFinancial` | Void collection, post/cancel/reverse journal, post opening balance, protected correction | Dedicated confirmation, destructive or protected emphasis, and permanent-audit wording where the server contract provides it |

The risk label must not imply that a routine action is unaudited or that a
protected action has stronger authorization than the endpoint actually
enforces.

## Authoritative Data Flow

For every workflow:

1. The page loads a typed record from its existing FastAPI repository.
2. Feature-local mapping converts only returned facts into plain review copy.
3. The shared panel renders that immutable presentation.
4. Management opens or reaches the final action control.
5. The shared confirmation content repeats the same record/status/consequence.
6. The page calls its existing repository method with the existing payload,
   token, device identifier, permission context, and idempotency behavior.
7. FastAPI revalidates the actor, active device, permission, record version or
   state, and domain rules.
8. The page refreshes from the server or enters its existing uncertain-result
   reconciliation path. It does not locally declare the official result.

A displayed review is advisory context for a server-authorized mutation, not a
reservation or lock. If the backend reports that the source changed or the
action is no longer permitted, the page says `This record changed or is no
longer ready for that action. Refresh and review the current server record.` It
must not retry a non-idempotent mutation with invented state.

Network failure before a confirmed result remains a failure or uncertain
outcome according to the existing repository contract. The shared component
must not turn it into success, queue the action offline, or alter the local
record.

## Mutation-Surface Inventory

`ManagementMutationSurface` and a const catalog enumerate every known
state-changing Management surface at the starting commit. The catalog records
the stable identifier, owning page, action names, and display risk. One page can
own more than one action while sharing a loaded review record.

| Surface ID | Owning page | Current actions in scope | Default risk |
| --- | --- | --- | --- |
| `client-registration` | `client_registration_approvals_page.dart` | Approve and link a client; reject a request | privileged |
| `renewal-workflow` | `management_renewal_requests_page.dart` | Record terms; reject; release to Collector; review proof; activate | privileged |
| `staff-invitation` | `management_staff_invite_page.dart` | Invite a staff account; reconcile an uncertain invitation | privileged |
| `staff-access` | `management_staff_detail_page.dart` | Change canonical role; change account status; approve/revoke device | privileged |
| `collection-void` | `management_collection_void_page.dart` | Void an eligible unlocked/unremitted collection | protected financial |
| `contract-collection` | `management_contract_collection_activation_page.dart` | Activate or deactivate per-loan mobile collection | privileged |
| `no-collection` | `management_no_collection_page.dart` | Declare No Collection; reverse a declaration | protected financial |
| `client-support` | `management_support_requests_page.dart` | Answer, resolve, or cancel a support request | routine |
| `ecl-outcome-review` | `management_ecl_outcome_review_page.dart` | Save a historical outcome-review version | privileged |
| `fiscal-period` | `management_financial_accounting_page.dart` | Create a fiscal period; change period status | protected financial |
| `general-journal` | `management_general_journal_page.dart` | Create/edit a draft; post; cancel; create reversal draft | protected financial |
| `opening-workbook` | `management_opening_balance_workbook_page.dart` | Initialize; edit line/policy; change workbook status | protected financial |
| `opening-journal` | `management_opening_balance_journal_page.dart` | Prepare draft; post opening journal | protected financial |

The default risk is the highest normal risk on the surface. Individual actions
may use a lower display risk when accurate, such as editing an unposted journal
draft, but may never reduce or bypass existing server protection.

`management_staff_devices_page.dart` is a read/search/navigation container at
the starting commit. Its actual invitation and account/device mutations occur
in the two inventoried child pages. Read-only Management pages are not forced
to show a mutation review panel.

Any new Management repository mutation added later must add a catalog entry or
an action under an existing surface and must add a focused test. The catalog is
not a permission registry and does not replace the backend permission matrix.

## Plain-Language Rules

Feature-local adapters translate known server values without changing meaning.
Examples of the required style are:

| Avoid as the primary message | Prefer as the primary message |
| --- | --- |
| `pending`, `review_ready`, `posted` | `Waiting for Management review`, `Ready for review`, `Posted to the General Ledger` |
| `Stage 5E.4` | `Historical credit-outcome review` |
| `status transition` | `Change the fiscal period from Open to Closed` |
| `mutation` | `Save`, `Approve`, `Post`, `Reverse`, or the exact action |
| `record UUID` | Client name, receipt number, journal number, period name, or another human-recognizable source |
| `409 conflict` | `The record changed. Refresh it before deciding.` |

The UI may show `Server status: review_ready`, a UUID, or an audit event ID as
secondary detail when it helps investigation. Technical data must be escaped
and must never be interpolated into an error in a way that exposes SQL, secrets,
tokens, device hashes, or records outside the actor's authorization.

Financial screens must distinguish clearly among:

- source/reference amounts;
- unposted draft amounts;
- posted General Ledger amounts;
- a review-ready state;
- an authorized posting action.

`Ready for review` must not be shortened to `Ready to post` unless the server
contract actually reports that posting is the next permitted action. The UI
does not claim that the accounting equation balances, that evidence is
complete, or that maker-checker approval occurred unless the response provides
that fact.

## Screen Integration Rules

- Put the review panel immediately before the page's action region or inside the
  selected-record detail used to launch the action. Long queues do not repeat a
  full panel on every collapsed row.
- Rebuild the presentation when a different server record is selected or a
  refresh completes. Do not retain the prior record's warnings or consequence.
- Keep text inputs, date pickers, line editors, and other feature-specific forms
  in their current pages. The shared component explains the decision but does
  not absorb domain forms.
- Keep existing button enablement and progress locking. A panel's blocker
  rendering does not become a new authorization decision.
- After success, reload the authoritative record before showing its new current
  status. A short success message may describe the server-confirmed result.
- After a permission denial or stale-state conflict, disable or leave the action
  according to current behavior and offer refresh/back navigation. Do not show
  the previous consequence as if it succeeded.
- Preserve existing invitation reconciliation and other uncertain-result flows.
  Their next action should be `Check the server result`, not `Invite again`.
- Never make protected financial posting available offline. Review content may
  remain visible during a transient connection loss, but the action follows the
  current online-only policy.

## Accessibility and Responsive Behavior

- The five review sections must remain in semantic reading order and expose
  meaningful labels to screen readers.
- Warnings and blockers use icon, heading, and text; color alone cannot carry
  meaning.
- Record values, consequences, and audit references wrap instead of truncating
  essential information.
- Dialogs and embedded forms must scroll at 360x640 logical pixels with 1.3x
  text scaling. The final action stays reachable without covering content.
- Buttons retain at least the current Material touch target. Destructive styling
  cannot reduce contrast or replace an explicit verb.
- Keyboard focus starts on review content or the first form field, never on a
  destructive confirmation by default.

## Test-First Delivery Plan

Implementation begins only after this written design and its later
implementation plan are approved. Tests are written to fail before production
changes.

### Shared component tests

Prove that:

- all five review sections render in the fixed order;
- record, status, warning/blocker, next action, and consequence are required and
  remain distinct;
- information, caution, and blocker semantics do not rely on color alone;
- secondary references are visually subordinate but readable;
- unknown/missing facts render neutrally and never become favorable facts;
- routine, privileged, and protected-financial confirmations display the exact
  supplied consequence and return only confirm/cancel;
- the component has no repository dependency and does not mutate on its own;
- 360x640 at 1.3x text scale scrolls without overflow or hidden actions;
- semantics identify the record, current status, warning severity, and final
  action.

### Inventory guard

Add `management_review_surface_inventory_test.dart` with an exact expected set
matching the table in this design. Each catalog entry includes its owning page
and actions. The catalog test plus the owning pages' focused widget tests prove:

- all 13 stable surface IDs exist exactly once;
- every catalog entry has a real owning-page widget test that drives the page to
  the relevant decision and observes its surface identifier on the rendered
  shared review component;
- no current Management page containing a protected repository write from the
  audited inventory is absent;
- read-only container/summary pages remain explicitly classified as read-only;
- a newly added surface changes the expected set and therefore requires review.

The catalog is a drift alarm, not a substitute for widget behavior or backend
authorization tests. The inventory gate runs the catalog test and all owning
page behavior tests together. It must not grep Dart source for symbol names,
because text presence would not prove that Management can reach or understand
the review.

### Focused page tests

Extend the existing page tests to prove, for every catalog entry:

- selecting a record shows `management-review-<surface-id>`;
- current server status and identifying source are visible in plain language;
- warnings/blockers come only from the fixture's returned facts;
- the next action and exact consequence match the selected action;
- confirmation does not call the repository when cancelled;
- confirmation calls the same repository method and preserves the same payload
  when accepted;
- a backend denial, stale conflict, malformed response, or uncertain result
  does not appear as success;
- success refreshes or reconciles from the server;
- existing permission hiding/disablement remains intact;
- small-screen/larger-text layouts do not overflow.

Accounting fixtures additionally prove that reference, draft, review-ready,
and posted states are not mislabeled. Collection void, No Collection, journal
posting/cancellation/reversal, fiscal-period changes, and opening-balance
posting retain permanent-audit or reversal wording only where the current
server contract guarantees it.

### Regression verification

Before the Draft pull request is described as exact-head green:

- run focused shared-component, inventory, and all modified page tests;
- run full `flutter test` and `flutter analyze --fatal-infos`;
- inspect the exact diff for client-side authority, raw status leakage,
  over-disclosure, payload changes, and mutation coverage;
- obtain independent specification and code/standards review with no unresolved
  Critical or Important finding;
- push the exact commit and wait for all permanent CI lanes on that same head;
- build a debug Android review APK from the exact head, record its SHA-256 and
  size, install it, and prove cold launch without a fatal exception;
- leave authenticated Management usability acceptance open until an authorized
  Management account/device performs it.

Backend tests are rerun if implementation touches a shared API contract. If the
Flutter work discovers that a required fact or consequence cannot be stated
truthfully from the current response, implementation stops and the design is
revised; Flutter must not fabricate the missing fact.

## Migration and Compatibility

This change has no database or API migration. It preserves existing routes,
request/response shapes, role and permission names, idempotency behavior, and
audit events. Existing legacy Desktop roles are neither reused nor mapped by
this slice; the product direction is a new canonical role/permission design,
with any legacy removal handled by a separately approved safe migration plan.

Existing tests that locate action keys remain valid. The implementation adds
stable review keys without renaming backend fields or changing external
contracts. A page can migrate one tested surface at a time on the child branch,
but the Draft PR is not ready for review until the entire catalog is covered so
the app does not ship a mixed Management decision pattern.

## Alternatives Rejected

### Page-by-page copy edits

Editing each page's private cards and dialogs independently would improve some
screens but keep the source of drift. It would not provide a stable five-part
contract or a failing inventory test when a new mutation surface is added.

### Client-side workflow engine

A generic engine that interprets domain statuses, calculates eligibility, or
selects next actions would duplicate FastAPI authority and make Flutter a
second rules system. The shared component therefore accepts display-ready facts
and leaves every domain decision in its existing feature and backend.

### One universal approval API

Wrapping unrelated actions in a new generic approval endpoint would erase
domain-specific validation, payloads, maker-checker rules, idempotency, and
audit meaning. Existing protected endpoints remain separate.

## Scope Boundaries and Remaining Gates

This design deliberately does not:

- change a FastAPI route, PostgreSQL record, Supabase role, device policy,
  permission, idempotency key, audit event, or financial rule;
- implement missing maker-checker backend states or claim current workflows
  already meet every intended accounting control;
- calculate New Client Fund, renewal fund, cash available for lending, or smart
  new-client capacity;
- implement Employee, Collector, Client, Desktop, Client Web, or Staff Web
  workflows;
- create offline mutation queues or reconnect legacy external portals;
- approve Management usability, Android release, iOS release, merge, deploy,
  restart a protected service, or mutate protected/live data;
- check CA2 or Master Issue #296 complete from automated tests alone.

After this slice, CA2 still requires authenticated Android Management review and
approval, the remaining explicit usability decision, and iOS evidence. All
later CA3-CA7, Client Web, accounting, infrastructure, data migration,
production engineering, security, backup/restore, monitoring, and release
acceptance dependencies remain open in the frozen Master Issue order.
