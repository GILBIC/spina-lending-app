# SPINA Platform Direction

**Decision date:** 2026-08-28 (Asia/Manila)

**Status:** Management-approved product direction; large implementation remains
paused until the written architecture and migration design are reviewed.

**Scope:** SPINA Desktop, Gilbic Mobile, public website, Client Web Portal, later
Staff Web Portal, shared backend, identity, records, accounting, and migration.

This document is the repository authority for intended future platform behavior.
It does not claim that planned behavior already exists. Merged code, migrations,
and tests remain the authority for current implemented behavior.

## Current behavior versus intended behavior

| Area | Current repository behavior | Intended platform behavior |
|---|---|---|
| Desktop | Current Python/Tkinter project contains mature office workflows, direct PostgreSQL access, and local `Admin`, `Encoder`, `Viewer`, `System` checks. | The current repository's Desktop evolves into the primary Management and Employee office platform, using protected FastAPI services and the new permission model. No old Desktop or portal is copied in as a replacement. |
| Backend | GitHub-first FastAPI implements an expanding authenticated API, with private `core`, `lending`, and `mobile` records and protected collection work. Coverage is incomplete across Desktop and future portals. | One shared FastAPI boundary owns application authorization, device enforcement, official workflow commands, and server-derived responses for every platform. |
| Identity and roles | Supabase authentication and canonical mobile roles exist, while Desktop still uses legacy local access profiles. | Supabase Auth proves identity; PostgreSQL and FastAPI derive the new Management, Employee, Collector, and Client roles, permissions, resource scope, and device state. |
| Mobile | Flutter has role routing and material Collector flows. Several Client, Employee, and Management destinations are incomplete or placeholders. | Client self-service, Collector field operations, selected Employee tools, and Management review/approval are delivered in controlled phases from the shared backend. |
| Website | No public-site or Client Web frontend package is present in this repository. Earlier Client/Staff portals are external/legacy until inventoried. | Phase 1 delivers the public website and secure responsive Client Web Portal. A selected Staff Web Portal comes later under separately approved scope. |
| Accounting | Protected accounting capabilities exist in slices, but a complete Employee preparation and financial-position workflow is not yet implemented across the platform. | Employees record and reconcile source transactions; the system validates double entry; Management reviews sensitive work; authorized users post; corrections use protected reversals and permanent audit evidence. |
| Office cash and new-client capacity | Protected disbursement, renewal, custody, remittance, and accounting evidence exists in bounded slices, but there is no dedicated authoritative working-fund reservation or new-client funding-capacity module. | One Office Working Fund tracks real cash by location/custodian. New Client Fund is a virtual allocation and server-derived capacity view; atomic reservations and an explainable Capacity Guard prevent overcommitment. |

## Product surfaces

### SPINA Desktop

SPINA Desktop is the primary office platform for Management and Employees.

Management responsibilities include lending, collections, cash custody,
remittance, approvals, collectors and areas, accounting review and posting,
reconciliation, ECL, statements, protected reversals, HR/payroll oversight,
client support oversight, user/permission/device administration, audit, backup,
and system administration.

Employee responsibilities are permission-specific and may include accounting
and bookkeeping, HR records, attendance, leave, payroll preparation, tasks,
client onboarding and documents, inquiries and support, follow-ups, renewals,
communication history, operational reports, and authorized remittance handling.
Accounting, HR, payroll, and client-relationship capabilities remain separable.
Management retains sensitive reviews and final authorization.

The new Desktop is the current repository's application evolved in place. Do
not copy the earlier Desktop or reconnect a legacy portal as a shortcut.

### Gilbic Mobile

- **Client:** own loans, balances, schedules, payment history, official
  receipts, payment updates, renewals, support, notifications, documents,
  profile, devices, and security. A Client cannot access another client or
  change official financial data.
- **Collector:** assigned or delegated routes, areas, clients, schedules,
  ledgers, Payment/ADV/PASS entry, official receipt results, visits, notes,
  concerns, temporary-area requests, custody, remittance and handover evidence,
  payment updates, renewal recommendations, and field coordination. Collector
  remains mobile-first and assignment-scoped.
- **Employee:** appropriate employee tools, notifications, attendance, payroll
  information, tasks, authorized remittance handling, and selected mobile-suited
  Accounting, HR, or Client Relationship functions.
- **Management:** dashboards, alerts, review queues, approvals, lending and
  collection oversight, remittance, direct payments, protected corrections,
  renewals, support, account/device administration, and appropriate accounting
  review.

### Website

Phase 1 contains two related but separately secured surfaces:

1. A public website for company information, products, requirements, FAQs,
   contacts, and application inquiries.
2. A responsive Client Web Portal for own-account loans, balances, schedules,
   receipts, payment updates, renewals, support, documents, notifications, and
   account security.

A later Staff Web Portal may expose selected Employee and Management remote
workflows. It must not duplicate the full Desktop without separately approved
scope. Collector stays mobile-first unless an evidenced office workflow is
approved.

## New role and permission model

The canonical roles are Management, Employee, Collector, and Client, but roles
do not replace narrow permission checks. Permissions are designed from business
responsibilities in namespaces such as lending, collection, remittance,
accounting, asset, liability, equity, reconciliation, HR, payroll, client
relationship, reporting, approval, audit, device, backup, and system
administration.

The legacy Desktop profiles `Admin`, `Encoder`, `Viewer`, and `System` are not
mapped into the new model. They are not templates, aliases, default grants, or
inputs to permission calculation.

Safe cutover is account-by-account:

1. Inventory the legacy identity and its actual current duties.
2. Provision or link its Supabase identity and server account.
3. Have Management assign a canonical role and individual permissions from
   verified job responsibilities—not from the old profile name.
4. Enforce approved devices and resource scope where required.
5. Validate positive access and prohibited access with the user and reviewer.
6. Disable that account's legacy login only after acceptance evidence exists.
7. Retain the legacy identity, former profile, approvals, tests, and cutover time
   as historical audit evidence with no authorization effect.
8. Remove legacy enforcement code only after no active account depends on it and
   recovery evidence has been reviewed.

## Employee accounting and Management financial position

Employees record underlying transactions; they never type Management dashboard
totals. Authorized Employee responsibilities include:

- assets: cash on hand, collector custody, petty cash, banks, receivables,
  equipment, vehicles, supplies, and other company property;
- liabilities: suppliers, employee-related payables, taxes, accrued expenses,
  loans, and other obligations;
- equity: capital contributions, withdrawals or distributions, retained
  earnings, and current profit or loss;
- controls: source documents, custodian/location, condition where applicable,
  reconciliation, discrepancy reporting, and audit evidence.

Management views are derived from posted journals, protected subledgers, custody
events, reconciliations, and approved source records. They include total assets,
liabilities, and equity; the accounting equation; cash by bank, office,
employee, and collector; unremitted collector cash; receivables and arrears;
upcoming obligations; asset location, custodian, condition, and depreciation;
capital movements, retained earnings, and profitability; unreconciled balances;
and review/approval queues.

The mandatory maker-checker flow is:

1. An Employee or other authorized maker records or prepares the source
   transaction and evidence.
2. The server validates balanced double entry, scope, periods, references, and
   protected business rules.
3. Management reviews sensitive entries.
4. A distinct authorized person approves or posts according to permission and
   separation-of-duty policy.
5. Corrections create linked reversals and replacement entries; originals and
   audit evidence remain permanent.

Sensitive workflows fail closed when evidence, approval, period state,
reconciliation, or separation of duties is invalid.

## Office Working Fund and New Client Fund

SPINA uses one Office Working Fund for real company cash controlled by approved
office locations and custodians. Bank, approved GCash, safe, cashier drawer, and
employee custody remain individually visible and reconcilable. A transfer among
them changes custody, not profit or loss. Unremitted Collector Cash Custody is
excluded from cleared office availability until a protected handover or
remittance is accepted and reconciled.

New Client Fund is the Management-facing allocation and capacity view for
new-client releases inside that one fund. It is not separate physical money, a
second asset, or an editable dashboard total. Renewal net releases, new-client
releases, authorized obligations, and transfers use purpose-tagged Cash
Reservations against the same underlying cash.

The server derives:

`Spendable Office Cash = Cleared Office Cash - Minimum Operating Reserve - Active Cash Reservations - Blocked Cash`

The New Client Fund Capacity Guard evaluates a credit-approved applicant's exact
net cash requirement against this headroom, a conservative policy-horizon
forecast, portfolio limits, and Collector/route operating capacity. It returns
an explainable Green, Amber, or Red result. Green can reserve cash within valid
delegation; Amber requires Management review; Red blocks funding and identifies
the failed controls. Reservation is atomic so concurrent approvals cannot spend
the same money. Credit approval remains separate, all limits are versioned
Management policy, and AI cannot approve a client or override an official
balance.

The detailed current-versus-target contract, lifecycle, delegation, accounting,
and test requirements are in
[`2026-08-28-office-working-fund-and-new-client-fund-design.md`](../superpowers/specs/2026-08-28-office-working-fund-and-new-client-fund-design.md).

## Shared authority and security

- The GitHub-first `gilbic_backend` FastAPI service is the shared application
  boundary.
- Supabase Auth owns passwords and sessions, not application authorization.
- PostgreSQL owns official users, roles, permissions, device status, business
  records, journals, receipts, custody, approvals, and audit evidence.
- The server derives roles, permissions, balances, receipts, and official
  results. Flutter, Tkinter, browser metadata, caches, and local role flags do
  not.
- Approved-device enforcement applies by policy to sensitive and field access.
- Every protected mutation records actor, authority, device where applicable,
  source identity, reason, time, and linked outcome.
- Earlier Client/Staff portals and their backends remain external until
  inventoried and migrated feature-by-feature. They cannot become a second
  authority.

## Delivery phases and release order

### Phase 0 — architecture approval and inventory

Approve this written model; inventory current Desktop accesses, legacy portals,
data sources, active users, deployed environments, and incomplete UI routes.
Large implementation remains paused in this phase.

### Phase 1 — shared authorization foundation

Approve the clean permission catalog, separation-of-duty matrix, device rules,
audit contract, and account-cutover evidence. Implement and test these in
FastAPI/PostgreSQL without deriving grants from legacy profiles.

### Phase 2 — authoritative data and accounting foundation

Inventory and reconcile Desktop data into protected server records. Add source
transactions, journal preparation/review/posting/reversal, evidence, asset and
custody registers, liabilities, equity movements, reconciliation, discrepancy,
derived financial-position contracts, the Office Working Fund, Cash
Reservations, and the New Client Fund Capacity Guard. Rehearse migration and
recovery with non-production copies.

### Phase 3 — current Desktop migration

Move the current repository's Desktop workflows behind shared APIs by bounded
domain, starting with identity/read models before protected commands. Pilot new
accounts, verify parity and prohibited access, cut over account-by-account, and
retire local role enforcement only after zero-dependency evidence.

### Phase 4 — V1 surface delivery lanes and website Phase 1

Run independently gated lanes on the shared backend:

- complete the Management, Employee, Collector, and Client mobile experiences on
  Android first for Management UI review, then carry the approved system and
  workflows to iOS with parity evidence;
- complete Collector mobile assignment-scoped field workflows, receipts, visit
  evidence, temporary-area authorization, custody, remittance, handover,
  updates, and renewal coordination;
- deliver the responsive Client Web Portal using own-record scope,
  device/session policy, and official server results;
- deliver the approved public information and application-inquiry website as
  the other half of website Phase 1, after GitHub planning records whether that
  public surface is a V1 blocker or a separately scheduled release item.

Master Issue #296 currently makes all four Android/iOS role experiences and the
Client Web Portal V1 blockers and controls their exact release order. Collector
online-write and fail-closed rules remain until any future offline-write design
is separately approved and proven. Useful legacy portal behavior may be
inventoried, but neither its authority nor its backend is copied.

### Phase 5 — selected Staff Web Portal and legacy retirement

Define and approve a separate remote-work scope, then expose selected Employee
and Management workflows. Do not reproduce the entire Desktop automatically.
Retire legacy portals, local access enforcement, and transitional direct-write
paths only after their active dependencies reach zero and retained evidence is
accepted.

These phases are dependency boundaries, not permission to reorder the active PR
stack. Within every release slice, order is backend contract and migration,
automated security/financial tests, client integration, data rehearsal, UAT,
controlled pilot, then production release. No phase may bypass the gates and
release definitions in Master Issue #296.

## Approval boundary

This direction authorizes documentation and planning alignment only. It does not
authorize a large implementation wave, merging a Draft PR, deployment, service
restart, protected database migration, production data change, or final release.
