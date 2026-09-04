# CIF Lifecycle and Restricted Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-class, versioned Client Information Form lifecycle and a separately permissioned restricted identity/residence evidence boundary for SPINA office and Management users.

**Architecture:** Extend the existing FastAPI/PostgreSQL authority with one additive migration, focused domain/repository/API modules, and a shared portal component used by Employee and Management workspaces. Ordinary CIF reads use only `lending`; restricted evidence uses a separate `restricted_identity` schema and repository, so ordinary serializers never retrieve sensitive evidence in the first place.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, psycopg 3, PostgreSQL, Node.js 22 ES modules, the existing static SPINA portal, pytest, Node test runner, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-04-origination-compliance-foundation-design.md`

## Global Constraints

- Do not modify Master Issue #296.
- Use one stable `lending.clients.id`; names, phone numbers, addresses, and evidence references are never identity keys.
- Keep `core.client_registration_requests` unchanged as an account-claim/linking workflow.
- All database changes are additive and use migration `0110_add_client_information_forms_and_restricted_evidence.sql`.
- No production migration, deployment, real identity document, raw signature image, legal approval, GCash activation, loan approval, contract finalization, disbursement, or release is authorized.
- An expired, superseded, or re-verification-due CIF never blocks collection, correction, reversal, remittance, receipt access, or statement access for an existing obligation.
- Ordinary APIs must not query or serialize restricted evidence.
- Raw evidence upload is unsupported. Only allowlisted metadata and an external restricted-object reference may be recorded.
- Never accept or store credentials, OTPs, MPINs, passwords, ATM details, phone contacts, full National ID numbers, or arbitrary provider payloads.
- Every write requires bearer authentication, an active registered device, an exact server permission, and an allowlisted role.
- Activated CIF content and all restricted evidence/review/access-event rows are immutable.
- Verification and activation use different users.
- Time-based CIF status is derived from durable state and timestamps; no scheduled job is required.
- Production `main` remains unchanged until a reviewed pull request is explicitly approved and merged.

---

### Task 1: Add domain status, digest, and masking rules

**Files:**
- Create: `gilbic_backend/src/gilbic_backend/cif_domain.py`
- Test: `gilbic_backend/tests/test_cif_domain.py`

**Interfaces:**
- Produces:
  - `CifLifecycleState = Literal["draft", "active", "superseded"]`
  - `CifPublicStatus = Literal["Draft", "Active", "Expiring", "Expired", "Superseded"]`
  - `derive_cif_public_status(*, lifecycle_state: str, effective_at: datetime | None, expires_at: datetime | None, as_of: datetime) -> CifPublicStatus`
  - `five_year_expiry(effective_at: datetime) -> datetime`
  - `canonical_cif_digest(payload: Mapping[str, object]) -> str`
  - `normalize_masked_reference(value: str) -> str`
  - `ALLOWED_REVERIFICATION_REASONS`
  - `ALLOWED_EVIDENCE_TYPES`
  - `ALLOWED_ACCESS_PURPOSES`

- [ ] **Step 1: Write failing domain tests**

Cover:
- Draft, Active, Expiring at exactly 90 days, Expired, and Superseded status.
- Leap-day five-year expiry.
- Stable SHA-256 output across mapping key order.
- Rejection of a masked reference containing six consecutive digits.
- Acceptance of `****-****-1234`.
- Exact allowlists for re-verification reason, evidence type, and access purpose.

Run:
```powershell
python -m pytest -q gilbic_backend/tests/test_cif_domain.py
```

Expected: collection fails because `gilbic_backend.cif_domain` does not exist.

- [ ] **Step 2: Implement the domain module**

Use timezone-aware datetimes. Compute Expiring as `expires_at - timedelta(days=90)`. Normalize digest input with `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=_json_default)` and return lowercase SHA-256 hex. `normalize_masked_reference` strips surrounding whitespace, rejects blank values, rejects values longer than 120 characters, rejects control characters, and rejects `\d{6,}`.

- [ ] **Step 3: Run the focused tests**

Run:
```powershell
python -m pytest -q gilbic_backend/tests/test_cif_domain.py
```

Expected: all domain tests pass.

- [ ] **Step 4: Commit**

```bash
git add gilbic_backend/src/gilbic_backend/cif_domain.py gilbic_backend/tests/test_cif_domain.py
git commit -m "feat: add CIF domain policies"
```

---

### Task 2: Add the additive PostgreSQL foundation

**Files:**
- Create: `gilbic_backend/sql/0110_add_client_information_forms_and_restricted_evidence.sql`
- Create: `gilbic_backend/tests/test_cif_restricted_evidence_migration.py`
- Create: `gilbic_backend/tests/test_cif_restricted_evidence_postgres.py`

**Interfaces:**
- Produces:
  - permissions `cif.view`, `cif.prepare`, `cif.verify`, `cif.approve`, `cif.reverification.manage`, `identity_evidence.view`, `identity_evidence.record`, `identity_evidence.review`
  - `lending.client_information_forms`
  - `lending.client_cif_reverification_requirements`
  - `lending.client_information_form_status`
  - private schema `restricted_identity`
  - `restricted_identity.cif_verification_evidence`
  - `restricted_identity.cif_verification_evidence_reviews`
  - `restricted_identity.evidence_access_events`
  - `restricted_identity.cif_verification_evidence_status`

- [ ] **Step 1: Write failing static migration tests**

Assert the migration:
- revokes PUBLIC access to `restricted_identity`;
- grants no `anon` or `authenticated` Data API access;
- creates the exact permissions and role mappings;
- creates a unique active-CIF index and a unique draft-CIF index per client;
- enforces five-year expiry;
- installs immutable guards;
- contains no raw-content, password, OTP, MPIN, ATM, contact-list, or provider-payload columns;
- creates separate evidence, review, and access-event tables;
- records `registered_device_id` and `purpose_code` on access events.

Run:
```powershell
python -m pytest -q gilbic_backend/tests/test_cif_restricted_evidence_migration.py
```

Expected: FAIL because migration 0110 does not exist.

- [ ] **Step 2: Write the migration**

`lending.client_information_forms` stores ordinary fields only. Use durable states `draft`, `active`, and `superseded`; a view derives the five public states and `is_eligible_for_new_credit`. Use partial unique indexes for one draft and one active CIF per client. Activated and superseded rows are immutable except the exact `active -> superseded` transition with unchanged source content.

`lending.client_cif_reverification_requirements` allows only `open -> resolved`, keeps the reason/severity immutable, and links resolution to a new CIF.

`restricted_identity.cif_verification_evidence`, its review table, and access events are append-only. Corrections use `supersedes_evidence_id`. Evidence rows store only allowlisted metadata, masked reference, external restricted-object reference, SHA-256 digest, retention class, retain-until date, and legal-hold state.

Assign Employee `cif.view` and `cif.prepare`. Assign Management all eight permissions.

- [ ] **Step 3: Write PostgreSQL constraint tests**

The test connects only when `GILBIC_TEST_DATABASE_URL` is available, applies migration 0110 idempotently, inserts synthetic users/clients, and proves:
- one active CIF and one draft CIF per client;
- cross-client supersession fails;
- exact five-year expiry is required;
- activated content cannot be edited or deleted;
- re-verification can only transition from open to resolved;
- evidence/review/access rows cannot be updated or deleted;
- PUBLIC has no schema privileges;
- the status view returns Active, Expiring, Expired, and Superseded correctly;
- no production or pre-existing rows are modified.

Run:
```powershell
python -m pytest -q gilbic_backend/tests/test_cif_restricted_evidence_migration.py gilbic_backend/tests/test_cif_restricted_evidence_postgres.py
```

Expected: PASS when PostgreSQL is available; the PostgreSQL module has one explicit skip only when `GILBIC_TEST_DATABASE_URL` is absent.

- [ ] **Step 4: Commit**

```bash
git add gilbic_backend/sql/0110_add_client_information_forms_and_restricted_evidence.sql gilbic_backend/tests/test_cif_restricted_evidence_migration.py gilbic_backend/tests/test_cif_restricted_evidence_postgres.py
git commit -m "feat: add CIF and restricted evidence schema"
```

---

### Task 3: Implement the ordinary CIF repository

**Files:**
- Create: `gilbic_backend/src/gilbic_backend/cif_repository.py`
- Test: `gilbic_backend/tests/test_cif_repository_postgres.py`

**Interfaces:**
- Produces:
  - `CifDraftData`
  - `CifClientSummary`
  - `ClientInformationFormRecord`
  - `CifReverificationRecord`
  - `CifError`, `CifNotFound`, `CifConflict`, `CifInvalid`
  - `PostgresCifRepository.search_clients(query: str, limit: int)`
  - `PostgresCifRepository.list_for_client(client_id: UUID)`
  - `PostgresCifRepository.get(cif_id: UUID)`
  - `PostgresCifRepository.create_draft(actor_user_id: UUID, client_id: UUID, draft: CifDraftData)`
  - `PostgresCifRepository.update_draft(actor_user_id: UUID, cif_id: UUID, expected_updated_at: datetime, draft: CifDraftData)`
  - `PostgresCifRepository.verify(actor_user_id: UUID, cif_id: UUID, expected_updated_at: datetime, review_note: str)`
  - `PostgresCifRepository.activate(actor_user_id: UUID, cif_id: UUID, expected_source_digest: str, review_note: str)`
  - `PostgresCifRepository.open_reverification(actor_user_id: UUID, client_id: UUID, reason: str, severity: str, note: str)`

- [ ] **Step 1: Write failing repository tests**

Use one PostgreSQL connection patched through `open_connection`. Cover:
- client search by code/name with deterministic ordering;
- draft version allocation and current-active supersession pointer;
- optimistic update conflict;
- updating a draft clears prior verification;
- verification computes and freezes the canonical digest;
- activation requires a verified draft and a different approver;
- activation supersedes the old active CIF and resolves open re-verification in one transaction;
- audit rows contain IDs, version, action, and reason codes but no address, signature reference, phone, or evidence data;
- expired/re-verification-due status does not modify existing loans or collections.

Run:
```powershell
python -m pytest -q gilbic_backend/tests/test_cif_repository_postgres.py
```

Expected: FAIL because `cif_repository.py` does not exist.

- [ ] **Step 2: Implement repository transactions**

Use `psycopg.rows.dict_row`, `open_connection`, client-scoped `FOR UPDATE` locks, and database constraint translation. Use the domain digest over ordinary source fields only. Every write inserts one safe `core.audit_logs` event. Never query `restricted_identity`.

- [ ] **Step 3: Run focused repository tests**

Run:
```powershell
python -m pytest -q gilbic_backend/tests/test_cif_repository_postgres.py
```

Expected: all available repository tests pass.

- [ ] **Step 4: Commit**

```bash
git add gilbic_backend/src/gilbic_backend/cif_repository.py gilbic_backend/tests/test_cif_repository_postgres.py
git commit -m "feat: implement CIF lifecycle repository"
```

---

### Task 4: Implement the restricted evidence repository

**Files:**
- Create: `gilbic_backend/src/gilbic_backend/restricted_identity_repository.py`
- Test: `gilbic_backend/tests/test_restricted_identity_repository_postgres.py`

**Interfaces:**
- Produces:
  - `RestrictedEvidenceData`
  - `RestrictedEvidenceRecord`
  - `RestrictedEvidenceReviewRecord`
  - `RestrictedIdentityError`, `RestrictedIdentityNotFound`, `RestrictedIdentityConflict`, `RestrictedIdentityInvalid`
  - `PostgresRestrictedIdentityRepository.list_for_cif(...)`
  - `PostgresRestrictedIdentityRepository.record(...)`
  - `PostgresRestrictedIdentityRepository.review(...)`

- [ ] **Step 1: Write failing repository tests**

Cover:
- fixed evidence-type and purpose allowlists;
- masked-reference validation;
- client/CIF consistency;
- superseding evidence must refer to the same client and CIF;
- reviewer differs from verifier;
- each list/record/review action writes an access event with actor, registered device, purpose, request ID, and evidence ID;
- safe audit details contain no external reference, digest, masked reference, outcome, or document dates;
- ordinary CIF repository source contains no `restricted_identity` query.

Run:
```powershell
python -m pytest -q gilbic_backend/tests/test_restricted_identity_repository_postgres.py
```

Expected: FAIL because the repository does not exist.

- [ ] **Step 2: Implement restricted operations**

Require a non-null registered device ID and valid purpose code at the repository boundary. Record only fixed metadata fields. Listing logs access for each returned evidence record in the same transaction. Reviews are immutable one-time decisions; corrected evidence is a new superseding row.

- [ ] **Step 3: Run focused repository tests**

Run:
```powershell
python -m pytest -q gilbic_backend/tests/test_restricted_identity_repository_postgres.py
```

Expected: all available repository tests pass.

- [ ] **Step 4: Commit**

```bash
git add gilbic_backend/src/gilbic_backend/restricted_identity_repository.py gilbic_backend/tests/test_restricted_identity_repository_postgres.py
git commit -m "feat: add restricted identity evidence repository"
```

---

### Task 5: Add permission-gated FastAPI contracts

**Files:**
- Create: `gilbic_backend/src/gilbic_backend/cif_api.py`
- Create: `gilbic_backend/src/gilbic_backend/restricted_identity_api.py`
- Modify: `gilbic_backend/src/gilbic_backend/main.py`
- Test: `gilbic_backend/tests/test_cif_api.py`
- Test: `gilbic_backend/tests/test_restricted_identity_api.py`

**Interfaces:**
- Produces ordinary routes:
  - `GET /api/v1/management/cif-clients?q=...`
  - `GET /api/v1/management/clients/{client_id}/cifs`
  - `POST /api/v1/management/clients/{client_id}/cifs`
  - `GET /api/v1/management/cifs/{cif_id}`
  - `PATCH /api/v1/management/cifs/{cif_id}`
  - `POST /api/v1/management/cifs/{cif_id}/verify`
  - `POST /api/v1/management/cifs/{cif_id}/activate`
  - `POST /api/v1/management/clients/{client_id}/cif-reverification`
- Produces restricted routes:
  - `GET /api/v1/management/cifs/{cif_id}/verification-evidence`
  - `POST /api/v1/management/cifs/{cif_id}/verification-evidence`
  - `POST /api/v1/management/verification-evidence/{evidence_id}/review`

- [ ] **Step 1: Write failing ordinary API tests**

Use dependency overrides for auth, accounts, and repository. Prove:
- Employee with `cif.view` can search and read;
- Employee with `cif.prepare` can create/update a draft;
- Employee cannot verify, activate, or open re-verification;
- Management still needs the exact permission for each action;
- Collector and Client are denied even if a fake session carries a permission;
- Pydantic rejects extra fields and malformed address/signature/digest values;
- responses expose status/eligibility but contain no restricted evidence keys;
- errors map to stable 404/409/422 responses.

- [ ] **Step 2: Write failing restricted API tests**

Prove:
- Management role, exact permission, registered device ID, and `X-Access-Purpose` are all required;
- Employee, Collector, and Client are denied;
- raw content, arbitrary metadata, OTP, password, full-number, and provider-payload fields are rejected as extra input;
- list/record/review payloads expose only the restricted allowlist;
- ordinary CIF routes never expose restricted metadata.

Run:
```powershell
python -m pytest -q gilbic_backend/tests/test_cif_api.py gilbic_backend/tests/test_restricted_identity_api.py
```

Expected: FAIL because routers do not exist.

- [ ] **Step 3: Implement strict API models and routers**

Use `ConfigDict(extra="forbid", str_strip_whitespace=True)`. Reuse `authenticated_device_context`. Ordinary read/prepare allows `employee` or `management`; verify/activate/re-verification and every restricted action require canonical `management`. Pass `actor.registered_device_id` into restricted repository methods. Do not add Mobile aliases for restricted evidence.

- [ ] **Step 4: Register both routers in `create_app()`**

Import and include `create_cif_router()` and `create_restricted_identity_router()` without changing any existing route.

- [ ] **Step 5: Run focused API tests**

Run:
```powershell
python -m pytest -q gilbic_backend/tests/test_cif_api.py gilbic_backend/tests/test_restricted_identity_api.py
```

Expected: all API tests pass.

- [ ] **Step 6: Commit**

```bash
git add gilbic_backend/src/gilbic_backend/cif_api.py gilbic_backend/src/gilbic_backend/restricted_identity_api.py gilbic_backend/src/gilbic_backend/main.py gilbic_backend/tests/test_cif_api.py gilbic_backend/tests/test_restricted_identity_api.py
git commit -m "feat: expose protected CIF administration APIs"
```

---

### Task 6: Add the shared office/Management portal surface

**Files:**
- Create: `spina_portal/assets/cif-management.js`
- Modify: `spina_portal/assets/roles/employee.js`
- Modify: `spina_portal/assets/roles/management.js`
- Create: `spina_portal/tests/cif-management.test.mjs`

**Interfaces:**
- Produces:
  - `cifWorkspaceMarkup({ permissions })`
  - `bindCifWorkspace(context)`
  - `loadCifWorkspace(context)`
- Consumes the API routes from Task 5.

- [ ] **Step 1: Write failing portal contract tests**

Prove:
- the shared component is imported by Employee and Management workspaces;
- navigation appears only with `cif.view`;
- draft forms appear only with `cif.prepare`;
- verify/activate controls appear only with their exact permissions;
- restricted evidence controls appear only with exact restricted permissions;
- rendered ordinary CIF markup contains no raw evidence, utility document, National ID number, external evidence reference, digest, or visit-photo field;
- the restricted form accepts only the allowlisted metadata and requires an access purpose;
- no Collector or Client role module imports the component.

Run:
```powershell
npm run test:portal -- --test-name-pattern="CIF"
```

Expected: FAIL because the shared module does not exist.

- [ ] **Step 2: Implement the shared component**

Provide client search, CIF version list, draft create/edit, verification, activation, and re-verification controls. Management users with restricted permissions receive a separate collapsed evidence panel. Keep form copy explicit that raw files and full ID numbers are prohibited. Use existing `escapeHtml`, `settledRequest`, `setButtonBusy`, `showToast`, and API client helpers.

- [ ] **Step 3: Integrate both workspaces**

Employee can search/read/prepare based on permissions. Management can additionally verify, activate, open re-verification, and manage restricted metadata. Existing workspace sections and actions remain unchanged.

- [ ] **Step 4: Run portal validation**

Run:
```powershell
npm run check:portal
npm run test:portal
npm run build
```

Expected: all portal checks, tests, and build pass.

- [ ] **Step 5: Commit**

```bash
git add spina_portal/assets/cif-management.js spina_portal/assets/roles/employee.js spina_portal/assets/roles/management.js spina_portal/tests/cif-management.test.mjs
git commit -m "feat: add office CIF administration workspace"
```

---

### Task 7: Complete cross-surface regression and security verification

**Files:**
- Modify only when a verified failure identifies a defect in a file already owned by Tasks 1–6.
- Update: `docs/superpowers/specs/2026-09-04-origination-compliance-foundation-design.md` only to record a concrete design correction discovered during implementation.

**Interfaces:**
- Produces a reviewable Draft PR that closes #395 and #396 only after merge.

- [ ] **Step 1: Run backend tests**

```powershell
python -m pytest -q gilbic_backend/tests spina_backend_mobile/tests
```

Expected: zero failures.

- [ ] **Step 2: Run portal checks**

```powershell
npm run check:portal
npm run test:portal
npm run build
```

Expected: zero failures and a successful build.

- [ ] **Step 3: Run source hygiene checks**

```powershell
python -m compileall -q gilbic_backend/src
git diff --check
git status --short
```

Expected: compilation succeeds, `git diff --check` emits no output, and only intended committed files exist.

- [ ] **Step 4: Push the exact branch and open a Draft PR**

The PR body must state:
- fixes #395 and #396;
- no production migration/deployment;
- no real identity data;
- no raw evidence upload;
- ordinary APIs never query the restricted schema;
- exact test commands and outcomes;
- issues remain open until the PR is approved and merged.

- [ ] **Step 5: Require all repository workflows on the exact head**

Verify the exact commit passes:
- Core Validation
- Code Quality
- Security & Compliance
- Reliability & Performance
- Financial & Database Validation
- Web, PC & Android Delivery when triggered

Do not claim completion from queued, in-progress, skipped-without-reason, or stale checks.

- [ ] **Step 6: Review the PR diff and discussion**

Confirm:
- no credential or real PII;
- no direct Data API grant;
- no ordinary serializer imports the restricted repository;
- no collection or correction route gained a CIF eligibility block;
- no legal, GCash, loan-approval, disbursement, or deployment behavior changed.

- [ ] **Step 7: Record the verified state**

Update Notion and Create State with the exact PR number, head SHA, passed checks, remaining approval boundary, and the fact that production remains unchanged.
