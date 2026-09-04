# CIF and Restricted Evidence Foundation — Implementation Plan

> **Execution authority:** Management instructed the implementation owner to choose practical defaults and proceed, with later revision permitted. This plan does not authorize production deployment, real identity-document storage, loan release, GCash enablement, or legal conclusions.

**Goal:** Implement issues #395 and #396 as an additive, fail-closed backend and office-portal foundation: versioned Client Information Forms, deterministic public status, early re-verification, restricted verification-evidence metadata, immutable history, purpose-bound access logging, and ordinary-view exclusion.

**Architecture:** PostgreSQL is the source of truth. FastAPI repositories own transitions and authorization. Ordinary CIF data and restricted evidence use separate modules and database schemas. Browser code renders only server-authorized payloads. Existing account registration, client identity, loans, collections, schedules, accounting, and remittance logic remain unchanged.

**Technology:** PostgreSQL SQL migrations, Python 3.12, FastAPI, psycopg, Pydantic, pytest, vanilla portal JavaScript.

---

## Task 1 — Add red contract tests for the migration

**Create:**
- `gilbic_backend/tests/test_cif_restricted_evidence_migration.py`

**Tests first:**
- migration file exists at the next free number;
- creates `lending.client_information_forms`;
- enforces one durable active CIF per client;
- stores five-year effective/expiry timestamps and supersession link;
- creates append-only re-verification requirements and CIF events;
- creates private `restricted_identity` schema and revokes PUBLIC;
- creates evidence metadata and access-event tables;
- excludes generic/raw payload columns and credential-shaped fields;
- grants no direct schema/table privileges to ordinary application roles;
- installs immutability and cross-client/same-client guards;
- adds dedicated permissions and role mappings without widening Collector or Client access.

**Run:**
```bash
python -m pytest -q gilbic_backend/tests/test_cif_restricted_evidence_migration.py
```
Expected initial result: fail because the migration does not exist.

## Task 2 — Add the additive database migration

**Create:**
- `gilbic_backend/sql/0110_add_cif_and_restricted_identity_foundation.sql`

**Implement:**
- `lending.client_information_forms` with per-client version, unique CIF number, draft/active/superseded durable state, exact effective/expiry values, supersession, ordinary identity/contact/address/livelihood snapshots, acknowledgments, safe signature references/digests, workflow actors/timestamps, canonical digest, and draft revision;
- partial unique index for one active CIF per client;
- deferred or procedural same-client supersession validation;
- `lending.client_cif_reverification_requirements` with allowlisted reasons and append-only resolution evidence;
- `lending.client_cif_events` as immutable lifecycle/audit evidence;
- deterministic view `lending.client_information_form_status` returning Draft, Active, Expiring, Expired, or Superseded plus `is_eligible_for_new_credit`;
- private `restricted_identity` schema with PUBLIC revoked;
- metadata-only `restricted_identity.cif_verification_evidence` with allowlisted types/methods/results, masked reference, dates, digest/reference, retention, legal hold, verifier/reviewer, and supersession;
- immutable `restricted_identity.evidence_access_events` with purpose code, request ID, device, actor, action, and timestamp;
- update/delete guards for activated/superseded CIF records, verified evidence, events, and access logs;
- permissions: `cif.view`, `cif.prepare`, `cif.verify`, `cif.approve`, `cif.reverification.open`, `identity_evidence.view`, `identity_evidence.manage`;
- mappings limited to appropriate Employee/Management roles, never Client/Collector;
- comments documenting no raw file or secret storage.

**Run:** migration contract test until green.

## Task 3 — Add deterministic CIF domain tests and implementation

**Create:**
- `gilbic_backend/tests/test_cif_domain.py`
- `gilbic_backend/src/gilbic_backend/cif_domain.py`

**Tests first:**
- five-year expiry calculation including leap dates;
- Expiring begins exactly 90 days before expiry;
- Expired at the expiry instant;
- Superseded overrides time-derived labels;
- open re-verification makes an otherwise Active/Expiring CIF ineligible for new credit;
- Draft is never eligible;
- collections-continuity helper always allows existing-obligation payment/correction regardless of CIF state;
- invalid durable states or impossible timestamps fail closed.

**Run:**
```bash
python -m pytest -q gilbic_backend/tests/test_cif_domain.py
```
Verify red, then add the minimum domain implementation and re-run green.

## Task 4 — Add repository transition tests and implementation

**Create:**
- `gilbic_backend/tests/test_cif_repository.py`
- `gilbic_backend/src/gilbic_backend/cif_repository.py`

**Repository behavior:**
- list/get safe CIF records;
- create a Draft with next client-scoped version and generated CIF number;
- patch only Draft fields using optimistic draft revision;
- verify a complete Draft and freeze its digest;
- activate under client-scoped transaction lock;
- require verifier and approver to be different users;
- re-check the digest before activation;
- supersede prior active CIF atomically;
- set `effective_at` and exactly five-year `expires_at` server-side;
- open and resolve allowlisted re-verification requirements;
- reject cross-client supersession, stale revision, altered verified content, duplicate active version, and invalid transitions;
- write safe `core.audit_logs` and immutable CIF event rows in the same transaction.

**Test method:** use strict fake connection/cursor assertions for query/parameter order plus disposable-PostgreSQL coverage later. No production database is touched.

## Task 5 — Add restricted evidence repository tests and implementation

**Create:**
- `gilbic_backend/tests/test_restricted_identity_repository.py`
- `gilbic_backend/src/gilbic_backend/restricted_identity_repository.py`

**Repository behavior:**
- accept only allowlisted evidence types, outcomes, purpose codes, retention classes, and SHA-256 digests;
- normalize and validate masked references;
- reject apparent full identifiers, credentials, OTP/MPIN/password/ATM/contact-list fields, arbitrary provider payloads, and raw bytes;
- create metadata evidence with client/CIF consistency check;
- record every read/list/create/review/supersede action in `evidence_access_events` in the same transaction;
- require a different final reviewer for exception evidence;
- return only the explicit safe metadata contract;
- never expose storage credentials or raw evidence content.

## Task 6 — Add authorization/API tests and routers

**Create:**
- `gilbic_backend/tests/test_cif_api.py`
- `gilbic_backend/tests/test_restricted_identity_api.py`
- `gilbic_backend/src/gilbic_backend/cif_api.py`
- `gilbic_backend/src/gilbic_backend/restricted_identity_api.py`

**Modify:**
- `gilbic_backend/src/gilbic_backend/main.py`

**CIF endpoints:**
- `GET /api/v1/management/clients/{client_id}/cifs`
- `POST /api/v1/management/clients/{client_id}/cifs`
- `GET /api/v1/management/cifs/{cif_id}`
- `PATCH /api/v1/management/cifs/{cif_id}`
- `POST /api/v1/management/cifs/{cif_id}/verify`
- `POST /api/v1/management/cifs/{cif_id}/activate`
- `POST /api/v1/management/clients/{client_id}/cif-reverification`

**Restricted endpoints:**
- `GET /api/v1/management/cifs/{cif_id}/verification-evidence`
- `POST /api/v1/management/cifs/{cif_id}/verification-evidence`
- `POST /api/v1/management/verification-evidence/{evidence_id}/review`
- `POST /api/v1/management/verification-evidence/{evidence_id}/supersede`

**Authorization:**
- canonical Management/Employee role as appropriate;
- active registered device;
- exact permission per endpoint;
- required `X-Evidence-Purpose` and `X-Request-Id` for restricted evidence;
- no Client or Collector access;
- stable safe error codes;
- no raw exception, SQL, internal schema, digest source, or sensitive data in errors.

**Response tests:** assert restricted fields never appear in ordinary CIF payloads, and ordinary client/collector APIs remain unchanged.

## Task 7 — Add office-portal workflow and tests

**Create:**
- `spina_portal/assets/cif-management.js`
- `spina_portal/tests/cif-management.test.js`

**Modify:**
- the owning Management/Office role module and route presenter discovered from current `main`;
- portal asset registration only where required.

**UI:**
- client lookup and CIF version list;
- clear status/expiry/re-verification indicators;
- Draft editor for ordinary fields;
- verify and activate actions shown only when session permission permits;
- separate restricted evidence drawer requiring an explicit purpose choice;
- metadata-only display with masked references;
- no raw upload control while restricted file storage is disabled;
- no Collector/Client navigation entry;
- stale revision and fail-closed server errors remain visible and do not discard the last safe view.

## Task 8 — Add disposable PostgreSQL acceptance validation

**Create:**
- `tools/run_0110_cif_restricted_identity_disposable_postgres_validation.py`
- `.github/workflows/cif-restricted-identity-disposable-postgres.yml`

**Validate on a disposable database:**
- migration applies from the repository migration sequence;
- one active CIF constraint under concurrent activation;
- exact five-year expiry and 90-day status projection;
- cross-client supersession rejected;
- activated CIF content immutable;
- early re-verification changes eligibility but not collection continuity;
- restricted schema inaccessible to PUBLIC/ordinary roles;
- safe metadata create/read emits access logs;
- raw/credential-shaped data rejected;
- exception verifier/reviewer separation;
- repeat migration is idempotent where repository convention requires it;
- no row exists outside synthetic fixtures.

## Task 9 — Full regression and review

**Run:**
```bash
python -m pytest -q gilbic_backend/tests
python -m ruff check gilbic_backend/src gilbic_backend/tests tools
python -m mypy gilbic_backend/src
node --test spina_portal/tests/*.test.js
```
Then rely on the repository's complete PR workflow set for Flutter, portal, backend, security, reliability, and financial/database validation.

**Review checklist:**
- no migration/deployment command aimed at production;
- no real client identity data;
- no raw evidence upload/storage;
- no Client/Collector permission widening;
- no collection, 7x7, accounting, remittance, or GCash behavior change;
- no legal conclusion or placeholder contract execution;
- all changed paths are within the approved foundation scope.

## Task 10 — PR and issue evidence

- Create one Draft PR from a fresh implementation branch based on current `main`.
- Link `Closes #395` and `Closes #396`, but keep the PR Draft until all exact-head checks are green.
- Add red/green test evidence, disposable-PostgreSQL result, permission matrix, sensitive-field exclusion evidence, and changed-path manifest.
- Do not merge without a later explicit Management approval.
- Do not close #395/#396 manually before merge; GitHub closes them only when the verified PR reaches `main`.
