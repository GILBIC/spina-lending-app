# SPINA Origination, Identity, Contract, and Payment Governance

**Date:** 2026-09-04  
**Status:** Approved architectural design, pending written-spec review  
**Target issues:** #394, #395, #396, #397, #398, #399, and #401  
**Explicit exclusion:** Master Issue #296 is not modified, closed, or used to authorize release by this work.

## Purpose

SPINA already has stable client and loan identifiers, protected collection
posting, idempotency, official receipts and balances, collector cash custody,
remittance controls, immutable contract-schedule registration, audit logs, and
a provider-neutral GCash boundary that defaults to disabled.

The missing capability is a controlled origination chain that connects:

1. a versioned Client Information Form (CIF);
2. restricted identity and residence-verification evidence;
3. a fresh Loan Application for every new loan and renewal;
4. counsel-approved contract and disclosure inputs;
5. a final signed document and verified schedule; and
6. an auditable payment-channel and collection-location decision.

This design adds that chain without replacing the existing financial ledger,
collection engine, schedule engine, remittance custody, or accounting controls.

## Scope decisions

- One stable `lending.clients.id` remains the client identity key. Names,
  phone numbers, addresses, and document references are attributes, never keys.
- The existing `core.client_registration_requests` workflow remains an account
  claim/linking workflow. It is not converted into a CIF.
- The office-facing implementation is added to `spina_portal`. Sensitive CIF
  administration is not added to Collector or Client mobile screens.
- FastAPI and PostgreSQL remain authoritative. Browser and Flutter clients do
  not infer eligibility, approval, legal clearance, payment authority, or
  collection state.
- All database changes are additive. Existing clients, loans, payments,
  contracts, schedules, receipts, and audit history remain valid.
- Migration numbers are not reserved in this document. Each implementation PR
  uses the next available monotonically increasing number from its current
  base, preventing collisions with concurrent work.
- No production migration, deployment, real identity document, legal approval,
  payment-provider activation, or loan release is authorized by this design.

## Architectural principles

### Versioned source records

CIFs, submitted Loan Applications, approved terms, contract contexts, signed
artifacts, legal clearances, and payment-channel authorizations are immutable
source records. Corrections create a new version or superseding record. The only
permitted mutation on an immutable version is an explicit lifecycle transition
such as Active to Superseded or Enabled to Suspended, recorded with an event.

### Deterministic time-based status

Time-based labels must not depend on a background task running exactly on time.
The CIF table records its durable lifecycle state (`draft`, `active`, or
`superseded`) and immutable effective/expiry timestamps. A canonical database
projection and domain function return the required public status:

- `Draft` before activation;
- `Active` until 90 days before expiry;
- `Expiring` during the final 90 days;
- `Expired` at or after expiry; and
- `Superseded` when replaced.

This prevents stale `Expiring` or `Expired` values while preserving the five
required user-visible states.

### Eligibility is separate from collection continuity

An Active or Expiring CIF may still be ineligible for new credit because of an
open early re-verification requirement. An Expired or Superseded CIF blocks new
application approval, contract finalization, and release. It never blocks:

- receipt of payment on an existing obligation;
- PASS/visit recording;
- a protected correction or reversal;
- collector cash accountability;
- remittance and acceptance; or
- client access to an existing statement or receipt.

### Fail-closed release gate

One backend release-gate service is reused by application approval, contract
execution, draft-loan creation, schedule registration, disbursement/release,
and company-GCash capability. A missing, expired, revoked, mismatched, or
ambiguous input produces no approval or release. UI hiding is never the gate.

### Restricted evidence is allowlisted, not redacted after retrieval

Ordinary APIs query only ordinary CIF fields. They never load a broad evidence
record and attempt to remove sensitive fields afterward. Restricted evidence
uses a separate schema, repository, permission set, serializer, and access log.
Contract compilation accepts an explicit allowlist of approved ordinary fields
and cannot receive restricted evidence objects.

## Component 1: Client Information Form lifecycle (#395)

### Data model

Add `lending.client_information_forms` with:

- immutable UUID primary key and unique CIF number;
- `client_id` foreign key and per-client form version;
- durable lifecycle state;
- `effective_at`, `expires_at`, and `supersedes_cif_id`;
- legal full name and other necessary personal identity fields;
- contact snapshot;
- structured present and permanent address snapshots;
- basic livelihood/employment snapshot, excluding affordability calculations;
- privacy-notice version and acknowledgment timestamp;
- client signature reference and SHA-256 digest;
- preparing, verifying, and approving user identifiers and timestamps;
- form-schema version and canonical source digest; and
- created/updated timestamps for the mutable Draft stage.

Signature references identify an approved signing repository object. Raw
signature images are not returned by ordinary CIF endpoints.

Add `lending.client_cif_reverification_requirements` as append-only workflow
records containing an allowlisted reason, severity, opened-by user, opened-at
time, status, resolution reference, and the CIF version that resolved it.
Allowed reasons include material identity change, address change, contact
change, document expiry, discrepancy, suspicious activity, and another
explicitly approved risk event.

### Constraints

- A unique partial index permits at most one durable `active` CIF per client.
- `expires_at` must equal `effective_at + five years` for an activated record.
- A CIF cannot supersede another client's CIF or itself.
- A draft may be edited only by an authorized preparer before verification.
- Verification freezes the content digest. A changed draft must be verified
  again before approval.
- Activation obtains a client-scoped database lock, validates completeness,
  requires verifier and approver to be different users, supersedes the prior
  active version, activates the new version, and resolves applicable open
  re-verification requirements in one transaction.
- Activated and superseded content is immutable. Corrections create a new CIF.
- Early re-verification blocks `is_eligible_for_new_credit` immediately but does
  not rewrite the historical CIF status.

### API contract

Office endpoints use the existing authentication and registered-device rules:

- `GET /api/v1/management/clients/{client_id}/cifs`
- `POST /api/v1/management/clients/{client_id}/cifs`
- `GET /api/v1/management/cifs/{cif_id}`
- `PATCH /api/v1/management/cifs/{cif_id}` for Draft only
- `POST /api/v1/management/cifs/{cif_id}/verify`
- `POST /api/v1/management/cifs/{cif_id}/activate`
- `POST /api/v1/management/clients/{client_id}/cif-reverification`

Responses include public status, eligibility, expiry timing, and safe ordinary
fields. They exclude restricted evidence and raw signatures.

### Permissions

Add independent permissions for CIF viewing, preparation, verification,
approval, and opening re-verification. The employee/office role may prepare;
Management may verify and approve. Database constraints enforce different
verifier and approver identities even when both users have Management access.
Clients and collectors receive none of these administration permissions.

## Component 2: Restricted verification-evidence custody (#396)

### Restricted storage boundary

Create a private `restricted_identity` schema with PUBLIC access revoked. Store
only necessary metadata in PostgreSQL. Raw files remain unsupported until an
approved encrypted repository, retention schedule, DPO-approved purpose, and
operational access-control review are configured.

Add `restricted_identity.cif_verification_evidence` with:

- CIF and client references;
- allowlisted evidence type: National ID Check/eVerify outcome, government-ID
  metadata, utility proof, residence visit, or approved exception;
- verification method and outcome;
- checked/document/expiry timestamps;
- masked reference only;
- verifier and final reviewer identifiers;
- external evidence reference and SHA-256 digest;
- retention class, retain-until date, and legal-hold state; and
- review state and superseding evidence reference.

The schema rejects fields intended to hold credentials, OTPs, MPINs,
passwords, ATM details, phone contacts, full National ID numbers, or arbitrary
provider payloads.

Add append-only `restricted_identity.evidence_access_events` recording actor,
evidence ID, action, approved purpose code, registered device, request ID, and
timestamp. Access logs contain no copied document content.

### Authorization and exposure

- Restricted endpoints require canonical Management role, active registered
  device, a dedicated evidence permission, and an allowlisted purpose code.
- Ordinary CIF, client, collector-route, application, contract, notification,
  and audit APIs never join the restricted schema.
- Collector route output may include only the minimum collection address and a
  verified/legacy/re-verification-due indicator. It never includes utility
  references, verification outcomes, visit evidence, photos, digests, or ID
  metadata.
- Contract and disclosure context is built from an explicit ordinary-field
  allowlist and has no dependency on the restricted repository class.
- Verified evidence metadata is immutable. A correction is a new superseding
  record.
- Material evidence exceptions require a separate Management reviewer from the
  original verifier.

## Component 3: Per-loan and per-renewal Loan Application (#399)

### Data model

Add `lending.loan_applications` for identity, lifecycle, requested terms, and
current affordability input. Every record has one `client_id`, one exact
`cif_id`, and kind `new_loan` or `renewal`. A renewal requires the prior loan ID.

Requested data includes current income and evidence references, essential
expenses, existing debt payments, disposable income, affordability assessment,
purpose, requested product, amount and term, staff recommendation, required
signer proposal, preparer, submitter, and timestamps.

Add an immutable one-to-one `lending.loan_application_decisions` record for an
approved or declined Management decision. Approved terms are stored only here:
approved product, principal, term, daily amount, pricing/tax rule references,
required signers, decision note, decision maker, timestamp, and canonical
approved-source digest. Contract code cannot read requested amount or term as
approved values.

### Lifecycle

Allowed application states are:

- `Draft`
- `Submitted`
- `Under Review`
- `Approved`
- `Declined`
- `Withdrawn`
- `Superseded`

Drafts are editable. Submission freezes the source digest. Any substantive
change after submission creates a superseding application instead of rewriting
the submitted record.

The transition rules are explicit:

- Draft to Submitted by an authorized preparer;
- Submitted to Under Review by Management;
- Under Review to Approved or Declined by a decision maker different from the
  submitter;
- Draft or Submitted to Withdrawn by an authorized actor; and
- any non-final version to Superseded when replaced by a new version.

A renewal always carries a fresh current affordability assessment. CIF
livelihood data alone is never accepted as the renewal assessment.

### Side-effect boundary

Creating, submitting, or reviewing an application does not create or update a
loan, schedule, journal, collection, disbursement, or payment. Approval itself
also does not create a loan. A separate contracting action may create one draft
loan shell only after the legal release gate is satisfied.

Until LEGAL-1 has active external evidence, the backend rejects transition to
Approved with a stable `legal_release_not_cleared` response. Synthetic tests
may use an isolated fake gate; production defaults remain closed.

## Component 4: Legal clearance and contract compiler (#397 and #398)

### External legal evidence registry

Add a private, metadata-only governance registry for these scopes:

- counsel loan agreement/disclosure approval;
- signer roles and acknowledgment approval;
- Privacy Act, AML/CDD, CIC, Truth in Lending, and retention review;
- FinLenD/OLP classification for the exact SPINA feature set;
- company-GCash channel clearance; and
- separate Management go-live authorization.

Each authorization records scope, exact feature-set version, external reference,
SHA-256 digest, issuer/approver identity, effective and expiry times, state, and
superseding/revocation event. It does not store invented legal conclusions.
There is at most one effective authorization for each scope and feature-set
version.

The software portion of #397 is complete when the registry and fail-closed gate
exist and are tested. The issue itself remains open until genuine signed
counsel, Compliance/DPO, regulatory-classification, and Management evidence is
entered through an authorized process. Code or synthetic fixtures cannot stand
in for that evidence.

### Counsel-template registry

Add `lending.contract_templates` containing template ID, document kinds,
version, source-object reference, template SHA-256, effective period, linked
legal authorization, approval state, and `is_executable`.

A synthetic test template is always `is_executable = false` and must render the
conspicuous mark:

> NON-EXECUTABLE — NOT LEGAL WORDING

No placeholder or synthetic template can be signed, finalized, registered as a
verified contract, or used for release.

### Versioned contract context

Add immutable contract-context records for:

- loan disclosure;
- draft contract;
- payment schedule;
- final signed contract; and
- signature/verification certificate.

Each context pins the exact client, CIF, approved application decision, draft
loan, product/pricing/tax rules, required signers, schedule, counsel template,
feature-set version, and canonical context digest. Context construction uses an
explicit ordinary-field allowlist and cannot import restricted evidence.

A changed CIF, approved term, signer requirement, schedule, rule, template, or
legal authorization produces a different digest. Prior non-final contexts are
marked Superseded through an immutable event and must be regenerated and
acknowledged. Final signed-document records and their signer evidence are
immutable.

### Contracting and release flow

1. A Loan Application is Approved only after the legal gate passes.
2. An explicit `begin contracting` action creates a single draft loan shell
   linked uniquely to the approved application. It creates no journal or
   disbursement.
3. The compiler creates disclosure, draft-contract, and schedule contexts.
4. Required acknowledgments and signatures are captured through approved
   references and digests.
5. A final signed-contract record is created and frozen.
6. The existing verified contract-schedule registration records the exact
   signed schedule and retains its existing immutability controls.
7. A separate release action revalidates every pinned source and existing
   disbursement/accounting gates before activating or releasing the loan.

Missing or stale input fails closed at every step. Existing loans and existing
collections remain unaffected by the new origination gate.

## Component 5: Payment channel and verified-residence policy (#394)

### Preserve the official collection authority

`lending.collection_transactions` remains the official payment/ADV/PASS
record. The design does not create a second payment ledger.

Add a required one-to-one `lending.collection_payment_contexts` record for every
new collection transaction. Existing transactions are explicitly marked as
legacy and are not assigned invented location or channel facts.

A migration adds a `requires_payment_context` marker to collection
transactions, backfills existing rows to false, and sets the default to true for
new rows. A deferred database constraint trigger rejects a new official
transaction at commit unless its context was inserted in the same transaction.
This protects every posting path, including Regular, 7x7, advance, voluntary
completion, correction replacement, and future verified company-GCash posting.

The context records:

- transaction, client, loan, collector, device, and route references;
- channel: collector cash, company GCash, approved other, or no-payment visit;
- location basis: verified residence, approved location, remote company
  channel, or controlled legacy obligation;
- exact CIF version or approved location-exception reference when applicable;
- policy version and policy decision;
- collector custody amount;
- provider/intent reference for company GCash;
- recorded and accepted timestamps; and
- safe audit reason code.

The official transaction continues to own exact amount, allocation, receipt,
previous/resulting balance, collector identity, and accepted time. Remittance
records continue to own later custody transfer and acceptance.

### Cash and location rules

- Collector cash at the last verified residence is the default for an assigned
  route.
- An alternative physical collection location requires an active immutable
  Management-approved exception with client, optional loan/collector scope,
  reason, valid period, approver, and revocation history.
- A current Active CIF is preferred, but CIF expiry never prevents payment of
  an existing obligation. The system references the last verified immutable CIF
  and records `controlled_legacy_obligation` or `reverification_due` without
  weakening route, identity, receipt, custody, or remittance checks.
- PASS records use `no_payment_visit`, custody amount zero, and the same
  location-policy decision.
- Corrections and reversals retain the original context and create explicit
  replacement/reversal links; they never rewrite the original context.

### Company GCash

Add a provider-neutral payment-channel authorization record containing company
merchant evidence reference/digest, provider identity, settlement-verifier
version, reconciliation-procedure version, legal authorization, Management
enablement, effective period, and state.

GCash capability is available only when all of these are true:

- the technical gateway reports checkout capability;
- the account is an approved company merchant/provider account;
- signed settlement verification is available;
- reconciliation controls are approved;
- the legal/FinLenD/OLP gate is active; and
- Management has explicitly enabled the channel.

Personal employee or collector GCash is structurally unsupported. Requests do
not accept a destination number, personal wallet, or collector-supplied
credential. The only permitted destination is the configured company provider
represented by the active authorization.

Creating or completing checkout never creates an official payment. A verified
provider event must pass the existing protected collection/accounting workflow
and insert an official transaction plus `company_gcash` context. Collector cash
custody is zero for that transaction.

Until the external provider and legal requirements are approved, the current
`disabled` behavior remains authoritative and is covered by tests.

### Offline behavior

Offline official capture is not enabled by this program. The route copy remains
read-only. Network retries continue to use existing idempotency controls. If a
future decision authorizes offline capture, it requires a separate design with
provisional local status, signed sync evidence, duplicate prevention, and no
local claim of an official receipt or balance.

## Portal and client-surface behavior

### Office portal

Add focused office pages for:

- CIF list, public status, expiry, and eligibility;
- Draft preparation, verification, activation, and re-verification;
- restricted evidence metadata review behind a separate permission and purpose
  prompt;
- Loan Application preparation and Management review;
- legal-clearance and template readiness summaries;
- non-executable contract preview and source-version diagnostics; and
- payment-channel authorization/readiness.

The portal preserves the last successful safe snapshot on refresh failure and
shows its timestamp. It never caches raw restricted evidence.

### Collector surfaces

Collector route and collection submission receive only:

- the minimum collection address needed for the assigned route;
- verified, legacy, or re-verification-due indicator;
- active approved alternative-location instruction when applicable; and
- the server-selected payment/location policy options.

Collectors cannot browse CIFs, evidence, legal records, Loan Applications, or
contract source contexts. Cash is the locked default channel. Personal GCash is
not an input option.

### Client surfaces

No new identity-evidence administration is added to the Client portal or mobile
application in this program. Existing loan, balance, receipt, statement,
renewal-status, support, and notification access remains unchanged. Company
GCash stays unavailable until every server gate passes.

## Error handling and concurrency

- Authentication or registered-device failures use the existing 401/403
  contracts before record lookup.
- Invalid state transitions, stale source digests, duplicate Active CIFs,
  reused application approvals, and mismatched idempotency keys return 409 with
  stable safe error codes.
- Missing external legal, template, settlement, or Management enablement
  returns a fail-closed 409 or 503 according to whether the dependency is a
  business-state conflict or unavailable external capability.
- Validation errors never echo full identity values, evidence references,
  addresses, provider payloads, or credentials.
- Client-scoped locks protect CIF activation. Application transition locks
  protect maker-checker and single-decision constraints. Contract finalization
  locks the application, draft loan, schedule, and pinned source rows.
- Payment-context enforcement is deferred to transaction commit so every
  posting implementation can insert transaction and context atomically in
  either order.
- All mutation endpoints use explicit request IDs or idempotency keys where a
  network retry could repeat a write.

## Audit model

Every preparation, verification, approval, decline, supersession,
re-verification, legal authorization, template approval, context generation,
context invalidation, signing/finalization, location exception, channel
activation/suspension, and payment-policy decision produces an allowlisted
`core.audit_logs` action.

Restricted evidence access additionally writes the dedicated restricted access
log. Ordinary audit projections expose safe action, record identity, actor,
time, and current owning state; they never expose document content, raw address,
full ID reference, signature, provider secret, or unrestricted details JSON.

## Testing and acceptance evidence

### Database and domain tests

- schema constraints, immutable guards, and permission grants;
- one Active CIF under concurrent activation attempts;
- exact five-year expiry and 90-day Expiring calculation;
- early re-verification eligibility blocking;
- activated/superseded CIF immutability;
- evidence type allowlist and forbidden-field absence;
- restricted access-log creation and role denial;
- Loan Application transitions and maker-checker enforcement;
- requested-versus-approved isolation;
- fresh renewal affordability requirement;
- synthetic-template non-executable enforcement;
- source pinning and contract-context invalidation;
- final signed-document immutability;
- external legal-gate default denial;
- required payment context across every official posting path;
- verified-residence, approved-location, legacy-obligation, PASS, correction,
  and reversal behavior;
- cash custody and remittance reconciliation; and
- disabled, personal-wallet-denied, and unverified-settlement GCash cases.

### API authorization and privacy tests

- client and collector denial for CIF and evidence administration;
- office preparer versus Management verifier/approver boundaries;
- restricted evidence permission and purpose-code enforcement;
- contract/compiler payload contains no restricted evidence;
- ordinary logs and error messages contain no sensitive values;
- stale digest and duplicate retry behavior; and
- expired CIF blocks new approval/release but not existing-loan collection.

### UI tests

- office CIF status and expiry display;
- Draft edit versus frozen version behavior;
- verification/activation confirmation and conflict refresh;
- restricted evidence separation and no browser persistence;
- Loan Application requested/approved separation;
- legal-gate and non-executable preview messaging;
- collector cash/location defaults; and
- no personal GCash destination field.

### Regression tests

Run the existing backend, portal, Flutter, collection, 7x7, schedule,
correction/reversal, remittance, accounting, receipt, notification, and
cross-platform smoke suites. New controls may not alter historical official
balances or introduce a second financial authority.

## Delivery sequence

### PR 1 — CIF and restricted evidence

Implements #395 and #396: schema, services, office APIs, portal UI, permissions,
audit, privacy, and disposable PostgreSQL evidence.

### PR 2 — Loan Application lifecycle

Implements #399: schema, services, office APIs, portal UI, maker-checker,
affordability, active-CIF gating, and default legal denial.

### PR 3 — Legal gate and contract compiler

Implements the software boundary for #397 and completes #398: legal metadata
registry, template registry, non-executable preview, context pinning,
invalidation, signed-artifact immutability, draft-loan contracting action, and
release revalidation. #397 remains open for real external evidence.

### PR 4 — Payment channel and verified residence

Implements #394: required payment context, verified-residence/default-cash
policy, approved location exceptions, legacy-obligation collection continuity,
GCash authorization gate, custody/remittance evidence, and all posting-path
regressions.

### Issue #401 disposition

Close #401 as `not_planned`. It remains a preserved optional research proposal,
not a V1 blocker. No attestation provider, cloud account, key, credential,
custodian, trust root, challenge ledger, retention policy, or external verifier
is provisioned. Reopening requires a new explicit Management decision; this
design does not reference or modify #296 to authorize that work.

## Completion and issue closure

- Close #395 and #396 only after PR 1 acceptance evidence passes.
- Close #399 only after PR 2 acceptance evidence passes.
- Close #398 only after PR 3 acceptance evidence passes.
- Keep #397 open until genuine external legal, regulatory, privacy/compliance,
  and Management evidence exists, even after its software gate is complete.
- Close #394 only after PR 4 acceptance evidence passes; GCash may remain
  disabled when no approved provider/legal authorization exists.
- Close #401 as `not_planned` after this written design is accepted.
- Leave #296 untouched.

## No-go boundaries

This program does not authorize production use, real client-data migration,
real evidence upload, raw biometric storage, a payment provider, personal
wallet use, legal wording, OLP/FinLenD classification, loan approval, contract
execution, disbursement, release, app-store publication, deployment, or an
emergency override. Every such action requires its existing or newly defined
separate authorization and must fail closed when evidence is missing.