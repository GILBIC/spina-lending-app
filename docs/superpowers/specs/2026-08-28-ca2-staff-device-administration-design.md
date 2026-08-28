# CA2 Staff and Device Administration Design

**Date:** 2026-08-28

**Repository:** `GILBIC/spina-lending-app`

**Starting commit:** `e1c252899f0a7f5f1b8dfc65d31fa2c857e86183`

**Backend branch:** `codex/ca2-device-approval-api`

**Planned mobile branch:** `codex/ca2-staff-device-admin`

**Parent:** Draft PR #372, based on `codex/7x7-extra-principal-bridge`

**Roadmap:** Frozen Master Issue #296, CA2 and CB1

## Outcome

Add a protected Management staff-and-device administration flow that uses the
existing FastAPI, PostgreSQL, Supabase Auth, Flutter session, and permission
boundaries. Management can find staff, invite Collector/Employee/Management
accounts, review current account and device state, change another staff member's
role or account status, approve a pending Collector phone, revoke or explicitly
restore an eligible device, and see the authoritative result after each action.

The same work closes the recorded Collector replacement-phone security gap.
After a valid Collector password is presented, an unknown Android or iOS
installation is registered as `pending` and receives no usable Gilbic session
until an already-authorized Management device approves it. Approval activates
that phone and atomically revokes every other active Android/iOS phone for the
Collector, preserving the invariant that one Collector has at most one active
mobile financial-posting device.

This is an Android-first CA2 checkpoint implemented in the shared Flutter
codebase. It does not check CA2 or CB1 complete, approve the Android experience,
create an iOS archive, merge a pull request, deploy, restart a protected service,
or mutate a protected/live database.

## Source Precedence and Binding Decisions

When sources disagree, implementation follows this order:

1. the checked-out repository and live GitHub state;
2. the newest explicit Management decisions in `SPINA Project Memory`;
3. frozen Master Issue #296;
4. Create State as retrieval support only.

The following decisions are binding for this slice:

- FastAPI is the only application-data boundary. Flutter never reads or writes
  PostgreSQL or Supabase administration state directly.
- Supabase Auth proves identity and owns invitations/password sessions.
  `core.users`, `core.user_roles`, `core.role_permissions`, and `core.devices`
  remain authoritative for application access.
- Server permissions remain exact: `account.manage` owns invitations, roles, and
  account status; `device.manage` owns device visibility and device status.
- A launcher may be visible when either permission exists, but every individual
  action is hidden or disabled without its exact permission and is revalidated by
  FastAPI at request time.
- Staff roles remain exactly `collector`, `employee`, and `management`. Client
  registration/linking remains in the separate existing protected flow.
- Account statuses remain exactly `pending`, `active`, `inactive`, and `locked`
  as returned by the server. Mutations remain limited to `active`, `inactive`,
  and `locked`.
- Device statuses remain `pending`, `active`, and `revoked`. A pending device may
  be approved, an active device may be revoked, and a revoked device may be
  explicitly restored by Management after a separate warning.
- Management cannot demote, lock, disable, or revoke devices belonging to the
  currently acting Management account. The backend remains the final guard.
- Device identifiers and identifier hashes are private. The mobile repository
  retains the server device UUID only as an opaque action identity. The UI shows
  platform, app version, status, registration time, and last activity time; it
  does not display the UUID or any raw/hash identifier.
- The one-active-phone rule applies to Collector Android/iOS devices because
  those devices can perform field financial posting. Existing active Collector
  phones are preserved until a replacement is approved or Management revokes
  them. Web/desktop registrations and non-Collector roles keep their current
  registration behavior in this slice.
- The schema already permits `pending`, so no migration is required. Migration
  history remains untouched.
- Collector financial writes remain online-only under frozen V1 scope. Pending,
  revoked, and offline devices cannot queue or post financial work.

## Existing Protected Primitives

The implementation reuses these existing boundaries instead of creating a
parallel administration system:

- `gilbic_backend/src/gilbic_backend/auth_api.py` performs login/version checks
  and calls the account repository only after Supabase verifies credentials.
- `gilbic_backend/src/gilbic_backend/account_repository.py` owns account lookup,
  device hashing, device registration, and active-device enforcement.
- `gilbic_backend/src/gilbic_backend/request_auth.py` resolves authenticated
  device context and exact server permissions for protected requests.
- `gilbic_backend/src/gilbic_backend/management_api.py` exposes the existing
  account invite, role, account status, device list, and device status routes.
- `gilbic_backend/src/gilbic_backend/management_repository.py` owns transactional
  account/device updates and immutable `core.audit_logs` insertion.
- `gilbic_backend/sql/0001_core_lending_foundation.sql` already defines device
  status `pending`, `active`, and `revoked` plus unique user/device identity.
- `gilbic_backend/sql/0003_add_management_administration.sql` already grants
  `account.manage` and `device.manage` and creates administration audit storage.
- `gilbic_mobile/lib/src/core/auth/user_session.dart` owns the server-derived
  role and permission set.
- `gilbic_mobile/lib/src/core/device/device_identity.dart` owns the
  privacy-preserving installation identity.
- `gilbic_mobile/lib/src/core/network/spina_api.dart` owns safe response/error
  parsing.
- `gilbic_mobile/lib/src/features/management/management_dashboard.dart` owns the
  exhaustive Management launcher registry and tap-time permission recheck.
- Existing Management repositories/pages establish authenticated HTTP, loading,
  error, empty, confirmation, refresh, and test-injection patterns.

## Delivery Shape

The work is split into two stacked Draft pull requests so the security boundary
can be reviewed independently from the mobile presentation:

1. `codex/ca2-device-approval-api` is based on exact commit `e1c25289` and targets
   `codex/ca2-management-command-center`. It contains this design, the backend
   Collector device-approval lifecycle, staff search/filter support, backend
   tests, and architecture documentation updates.
2. `codex/ca2-staff-device-admin` starts from the final exact backend head and
   targets `codex/ca2-device-approval-api`. It contains typed Flutter models,
   repository methods, Management pages, dashboard wiring, mobile tests, and the
   Android review artifact.

Both pull requests remain Draft and unmerged. No implementation commit is added
to Draft PR #372.

## Backend Account Directory

`GET /api/v1/management/accounts` remains the canonical staff directory. It is
extended with optional query parameters while preserving existing callers:

- `q`: case-insensitive name, username, or email search, trimmed and bounded;
- `role`: one exact staff role;
- `status`: one exact account status;
- `staff_only`: boolean; the mobile administration screen always sends `true`;
- existing `limit` and `offset` pagination remain bounded to 1–200 and nonnegative.

The route accepts an actor with `account.manage` or `device.manage`. This is
necessary because a device-only administrator must be able to find the account
whose devices they are authorized to manage. The response stays privacy-safe and
contains only the existing account-administration fields. `auth_user_id` is not
needed by Flutter and is removed from the mobile-facing payload; Supabase
identity remains a server concern.

Filtering is performed in PostgreSQL before pagination. `staff_only=true`
requires at least one of the three staff roles and therefore never turns this
screen into a second client-account workflow. Ordering stays deterministic by
creation time, username, and user UUID so page boundaries do not drift when
names match.

The four mutation routes retain exact permissions:

- `POST /api/v1/management/accounts/invite` — `account.manage`;
- `PATCH /api/v1/management/accounts/{user_id}/role` — `account.manage`;
- `PATCH /api/v1/management/accounts/{user_id}/status` — `account.manage`;
- `GET /api/v1/management/accounts/{user_id}/devices` and
  `PATCH /api/v1/management/devices/{device_id}/status` — `device.manage`.

Invitation continues to create a Supabase invitation without a password and then
creates the pending application profile. Existing compensation deletes the
invited Supabase identity when application-profile creation fails. The mobile UI
does not claim an invitation completed after a network-uncertain response; it
refreshes the authoritative directory before enabling a second submission with
the same username/email.

## Collector Device-Approval Lifecycle

### Login classification

The account repository determines the user's current roles before changing an
unknown device:

1. Supabase successfully verifies username/password.
2. FastAPI locks and loads the application account and roles.
3. Existing active device: update metadata/last-seen and return the normal
   session.
4. Existing revoked device: return the existing revoked-device denial.
5. Existing pending Collector mobile device: return HTTP 403 with stable code
   `device_approval_required` and a nontechnical message explaining that
   Management must approve this phone.
6. Unknown Collector Android/iOS device: insert it as `pending`, commit that
   registration, then return the same HTTP 403. The denial must not roll back the
   pending record.
7. Unknown device for a non-Collector role or a non-mobile platform: preserve
   current active registration behavior.

The API never returns the Supabase access/refresh tokens when device approval is
required, and Flutter never persists a session from that response. A repeated
login from the same pending phone reuses its unique device row and does not
create duplicates.

### Management approval, revocation, and restore

`set_device_status` locks the target user before locking device rows. Every code
path uses that order to prevent cross-request deadlocks.

- Pending to active is an explicit approval.
- Active to revoked is an explicit revocation.
- Revoked to active is an explicit restore and uses different warning copy from
  first approval.
- A request setting the current status again returns the same current record
  without another status-change audit entry.
- For a Collector Android/iOS activation, the transaction activates the target
  and revokes every other active Android/iOS device for that Collector before it
  commits.
- For other roles/platforms, only the selected device changes.
- Self-device revocation remains blocked for the acting Management account.

The activation transaction writes one `device.status_change` audit for the
selected device with previous/new status and one
`device.replacement_auto_revoke` audit for each displaced Collector phone. All
rows preserve actor, target, affected user, platform, and timestamp through the
existing immutable audit boundary. No raw installation identity is included.

The one-active-phone invariant is checked again from locked database rows before
commit. Concurrent approvals may both be processed serially, but the final
committed state always has at most one active Collector Android/iOS device; the
response for each request reflects the state established by its transaction.

## Flutter Domain and Repository Boundaries

Create focused immutable domain types in
`gilbic_mobile/lib/src/core/management/management_administration.dart`:

- `ManagementStaffAccount` for the privacy-safe staff summary;
- `ManagementDevice` for one registered device;
- `ManagementStaffPage` for one paginated account result;
- enums or validated value objects for staff role, account status, and device
  status, while retaining unknown response values as fail-closed parse errors.

Create
`gilbic_mobile/lib/src/core/management/management_administration_repository.dart`
with an injectable interface and HTTP implementation. It loads the installation
identity once per page session and sends bearer token plus `X-Device-Id` on every
request. Methods are narrow and map one-to-one to the protected operations:

- search/list staff with query, role, status, limit, and offset;
- invite staff;
- change another staff account's role;
- change another staff account's status;
- load devices for one staff account;
- set one device's status.

The repository parses only documented fields, rejects malformed successful
payloads, preserves safe FastAPI error details, and converts transport failures
to clear online-only messages. It performs no authorization, role inference,
device selection, optimistic official-state calculation, or database logic.

## Management User Experience

### Dashboard entry

Keep the six purpose groups introduced at `e1c25289`. Rename the existing
`Renewals & support` group to `People, access & requests`, and place a new
`Staff & devices` launcher first in that group. Existing renewals, support, and
client-registration launchers remain separate.

The launcher is visible when the current session has `account.manage` or
`device.manage`. The exhaustive `_ManagementAction` switch gains one explicit
destination and its launcher test gains one exact mapping. Tap-time permission
recheck uses the same any-permission rule before navigation.

### Staff directory page

`ManagementStaffDevicesPage` provides:

- a clear title and short explanation that server permissions control actions;
- debounced server search by name, username, or email;
- role and account-status filter chips/dropdowns;
- pull-to-refresh and explicit `Load more` pagination;
- staff cards showing name, username, role, status chip, and registered-device
  count;
- `Invite staff` only with `account.manage`;
- loading, empty, filtered-empty, offline/error, and permission-denied states
  with an obvious next action.

Search/filter changes reset offset and discard prior pages. A late response for
an older query is ignored. Duplicate accounts are de-duplicated by server user
UUID when pages are appended. The page never silently treats a partial page as a
complete directory.

### Staff detail page

`ManagementStaffDetailPage` starts from the selected server summary and reloads
the authoritative account/device state after every successful mutation. It
shows:

- full name, username, optional email only when returned, exact role/status,
  created/updated timestamps, and device count;
- account actions only with `account.manage`;
- device section/actions only with `device.manage`;
- platform, app version, status, registered time, and last-seen time for each
  device;
- no raw installation identity and no visible server UUID;
- an explanation when one permission is absent instead of exposing a dead
  control.

The acting account is recognized by `session.userId`. Role changes and
inactive/locked actions are disabled for that account with the same explanation
as the backend rule. Device mutations are disabled for the acting account
because the current backend safely rejects self-device revocation at account
scope.

### Invitations and confirmations

The invitation form requires username, email, full name, and one staff role. It
never asks Management to create or view a password. Client is not an option.
Successful invitation returns to/refreshed directory state; uncertain network
results require refresh before another submission.

Role, account-status, device-approval, device-revocation, and device-restore
actions each use a purpose-specific confirmation. The confirmation shows the
person, current state, requested state, and practical consequence. Collector
device approval explicitly says that other active Collector phones will be
revoked. Destructive controls use the design system's destructive styling and
are disabled while their request is in flight.

## Data Flow

1. Dashboard checks the locally cached server permission set for visibility and
   again on tap.
2. The page loads the installation identity and calls the protected directory
   endpoint.
3. FastAPI validates bearer identity, active calling device, and at least one
   administration permission before querying staff.
4. The detail page calls exact-permission endpoints for mutations and device
   reads.
5. FastAPI locks and revalidates authoritative rows, commits the state/audit
   transaction, and returns the persisted record.
6. Flutter reloads the affected directory/detail/device state and renders only
   the server response.

No administration action is cached for offline execution, queued, automatically
retried, or considered successful from local state alone.

## Failure and Recovery Semantics

- Missing/expired authentication follows the existing session-expiry flow.
- Revoked calling device follows the existing revoked-device flow and clears the
  unusable session.
- `device_approval_required` keeps the user signed out and tells them to ask
  Management to approve the phone, then retry login.
- HTTP 403 inside administration states that current server permissions no
  longer allow the action and offers refresh/back navigation.
- HTTP 404 after selecting an account/device reports that the record is no
  longer available and refreshes the directory.
- HTTP 409 preserves the server conflict explanation, leaves controls enabled
  after the request ends, and reloads current state before another decision.
- A network failure after an uncertain mutation never produces a local success.
  The UI reloads before enabling the same action again.
- Malformed 2xx data is treated as a server-response error, not an empty list or
  successful mutation.
- Permission loss between launcher visibility and request execution remains
  safe because FastAPI is authoritative.

## Testing and Evidence

### Backend red-green coverage

Tests must fail before production changes and then prove:

- account directory access with `account.manage` only and `device.manage` only;
- denial without either permission;
- staff-only search, role/status filters, stable pagination, and bounded inputs;
- valid Collector credentials register an unknown Android/iOS phone as pending;
- the pending row commits even though login returns 403;
- pending retry reuses one row and never returns tokens;
- existing active and revoked device login behavior does not regress;
- non-Collector and non-mobile registration behavior remains compatible;
- pending approval activates the target and revokes all other active Collector
  phones atomically;
- revoked-device restore uses the same one-active Collector invariant;
- Management self-account/device protections remain enforced;
- device actions require `device.manage`; account mutations require
  `account.manage`;
- audit rows contain previous/new state and replacement revocations without
  identifier hashes;
- concurrent approvals leave at most one active Collector mobile device;
- forced audit failure rolls back every device status change;
- the full existing auth, account, management, collection, and backend suites do
  not regress.

Repository behavior must be proven against disposable PostgreSQL, not only fake
API repositories. Migration/bootstrap tests confirm no schema change is needed.

### Flutter red-green coverage

Tests must prove:

- exact repository URLs, headers, query encoding, bodies, parsing, and safe error
  messages;
- the launcher appears for either administration permission and is absent for
  neither;
- exact launcher-to-page mapping and tap-time stale-permission denial;
- account-only and device-only controls expose no unauthorized action;
- loading, normal, empty, filtered-empty, error, and retry states;
- late search responses cannot replace a newer query;
- pagination appends without duplicates;
- invitation validation and no Client role option;
- self-account actions are disabled;
- every mutation shows the correct source/current/next-state confirmation;
- Collector approval warns that the former active phone will be revoked;
- successful mutations reload authoritative state;
- uncertain network outcomes never render success;
- pending-device login wording is nontechnical and no session is persisted;
- 360x640 layout at 1.3x text scale remains scrollable without overflow;
- all prior Management navigation, permissions, auth parity, account settings,
  and offline-policy tests remain green.

### Release evidence

Before either Draft PR is described as exact-head green:

- run changed-Python syntax/compile checks;
- run focused backend unit/API/PostgreSQL/concurrency tests;
- run the complete backend suite and repository-required lint/format/type/static
  controls;
- run focused Flutter tests, full `flutter test`, and
  `flutter analyze --fatal-infos`;
- obtain an independent code/spec review with no unresolved Critical or
  Important finding;
- push each exact commit and wait for all five required permanent CI lanes on
  that same head;
- build a debug Android review APK from the exact mobile head, record size and
  SHA-256, install it in the emulator, and prove cold launch has no fatal
  exception;
- perform authenticated Management acceptance only with an authorized review
  account/device; if credentials are unavailable, record that gate as open.

The Android artifact remains an unsigned/debug review build. iOS signing,
production signing, store distribution, deployment, protected-service restart,
and protected/live database actions require separate authorization and are not
performed by this design.

## Scope Boundaries and Remaining V1 Work

This design deliberately does not:

- add an offline financial outbox, quarantined recovery, or background retry;
- add PIN/biometric step-up authentication, which is a separate cross-role
  security design;
- expose raw device identifiers or Supabase administration credentials;
- create a generic audit-log browser or mark CB1 audit visibility complete;
- claim exact idempotency for every nonfinancial staff mutation; the broader CB1
  idempotency/stale-source acceptance remains open and must be closed before V1;
- change Client registration/linking, Employee features, Collector collection
  rules, accounting, Desktop, Client Web, iOS signing, or production operations;
- check any frozen Master Issue checkbox based only on automated tests.

After this checkpoint, CA2 still requires live dashboard priority counts,
broader review-screen consistency, authenticated Android Management approval,
and the remaining CA2 usability decision. CB1 still requires the full
Management operational overview, protected queue coverage, notification/audit
visibility, cross-platform permission/idempotency/stale-source proof, and iOS
acceptance. The wider Master Issue #296 objective remains active after both
Draft PRs are complete.
