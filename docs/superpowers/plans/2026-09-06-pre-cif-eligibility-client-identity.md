# Pre-CIF Eligibility and Client Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the first approved #419 subsystem: lean pre-CIF applicant intake, four-requirement verification, Collector visit recording, audited Management bypass, and idempotent creation of one inactive `lending.clients` identity row at `eligible_for_cif`.

**Architecture:** Replace the unmerged direct Guest CIF/Loan Application staging model with one focused `lending.client_onboarding_applicants` pre-CIF record. Public intake stores only minimum contact/address data plus controlled evidence references; Collector, Employee/Office Staff, and Management act through permission-gated endpoints. Normal eligibility and Management bypass both converge on one transactional promotion helper that creates exactly one inactive Client row with no `core.users`, credentials, loan, schedule, journal, contract, disbursement, or release side effects.

**Tech Stack:** PostgreSQL, psycopg 3, FastAPI/Pydantic, pytest, existing `open_connection()`, existing `authenticated_device_context()`/Management auth dependencies, existing `core.audit_logs`.

**Spec:** `docs/superpowers/specs/2026-09-06-guest-cif-loan-application-design.md`

## Scope decomposition

This is **Plan 1** only. The approved spec is deliberately split so each subsystem is independently reviewable and testable.

- Plan 1 — this file: pre-CIF verification + Management bypass + stable inactive Client identity.
- Plan 2 — later: signed-out/status/Collector/Staff/Management Web + Mobile surfaces for Plan 1.
- Plan 3 — later: CIF lifecycle, baseline live face enrollment, five-year validity, re-verification, and activation of the inactive Client row.
- Plan 4 — later: per-loan application preparation/review and the Active-CIF gate.

Do not pull Plan 2-4 behavior into this implementation slice.

## Global Constraints

- Normal eligibility requires all four: eGov-verified National ID, eGov-verified TIN ID, accepted Meralco bill, and passed Collector residence visit.
- Management alone may bypass any or all four requirements.
- Every bypass requires the exact bypassed requirement set, a non-empty reason, Management actor, server timestamp, and an audit event.
- Collector cannot grant final eligibility or bypass requirements.
- Office Staff/Employee may approve only the normal all-four-passed path and cannot bypass.
- Before `eligible_for_cif`, do not create `lending.clients`, `core.users`, Client permissions, credentials, or financial records.
- At `eligible_for_cif`, create exactly one `lending.clients` row with `status='inactive'`, `user_id=NULL`, and one stable generated `client_code`.
- Client code for this slice is deterministic from the public reference: `APP-2026-000124` -> `CLIENT-2026-000124`.
- Eligibility does not activate the Client. CIF Plan 3 owns `inactive -> active` after CIF becomes Active.
- Do not collect loan amount/product/term/purpose/affordability or baseline face scan in this plan.
- Store controlled evidence references/verification status only; no raw government-ID image, raw bill image, raw face media/template, password, OTP, contacts list, or unnecessary ID values.
- Keep the existing `/api/v1/management/client-accounts` credential flow untouched.
- Development uses fake evidence references and test identities only. No live eGov/provider/evidence upload, production DB/Auth mutation, deployment, or release.
- Strict TDD: RED test first, observe the expected RED, then write the minimum GREEN implementation.

---

### Task 1: Replace the obsolete guest-loan persistence contract with the pre-CIF schema

**Files:**
- Delete: `gilbic_backend/tests/test_guest_loan_application_migration.py`
- Create: `gilbic_backend/tests/test_client_onboarding_migration.py`
- Modify after RED: `gilbic_backend/sql/0112_add_guest_loan_applications.sql`

**Interfaces:**
- Produces table: `lending.client_onboarding_applicants`.
- Produces sequence: `lending.client_onboarding_reference_seq`.
- Produces permissions:
  - `client_onboarding.requirement.review` -> Employee + Management
  - `client_onboarding.visit.record` -> Collector
  - `client_onboarding.bypass` -> Management

- [ ] **Step 1: Replace the stale migration test with the failing pre-CIF contract**

```python
from pathlib import Path

SQL_PATH = Path(__file__).resolve().parents[1] / "sql" / "0112_add_guest_loan_applications.sql"


def test_pre_cif_onboarding_schema_and_permissions() -> None:
    sql = SQL_PATH.read_text(encoding="utf-8").lower()

    assert "create sequence if not exists lending.client_onboarding_reference_seq" in sql
    assert "create table if not exists lending.client_onboarding_applicants" in sql
    assert "requirements_incomplete" in sql
    assert "under_verification" in sql
    assert "eligible_for_cif" in sql
    assert "requirements_rejected" in sql
    assert "national_id_status" in sql
    assert "tin_id_status" in sql
    assert "meralco_bill_status" in sql
    assert "collector_visit_status" in sql
    assert "bypassed_requirements text[]" in sql
    assert "bypass_reason text" in sql
    assert "bypassed_by_user_id uuid" in sql
    assert "promoted_client_id uuid unique" in sql
    assert "client_onboarding.requirement.review" in sql
    assert "client_onboarding.visit.record" in sql
    assert "client_onboarding.bypass" in sql
    assert "('employee', 'client_onboarding.requirement.review')" in sql
    assert "('management', 'client_onboarding.requirement.review')" in sql
    assert "('collector', 'client_onboarding.visit.record')" in sql
    assert "('management', 'client_onboarding.bypass')" in sql
    assert "loan_application.manage" not in sql
    assert "baseline_face_scan" not in sql
    assert "requested_amount" not in sql
```

- [ ] **Step 2: Run the focused migration test and confirm RED**

Run:

```bash
python -m pytest gilbic_backend/tests/test_client_onboarding_migration.py -q
```

Expected: FAIL because the current unmerged `0112` still creates `lending.guest_loan_applications` and the old permission.

- [ ] **Step 3: Rewrite `0112` to the minimum pre-CIF schema**

Use this contract exactly; do not preserve obsolete loan/CIF fields because `0112` has never been merged to `main`:

```sql
BEGIN;

CREATE SEQUENCE IF NOT EXISTS lending.client_onboarding_reference_seq;

CREATE TABLE IF NOT EXISTS lending.client_onboarding_applicants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_reference TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'requirements_incomplete'
        CHECK (status IN (
            'requirements_incomplete',
            'under_verification',
            'eligible_for_cif',
            'requirements_rejected'
        )),
    full_name TEXT NOT NULL,
    phone_number TEXT NOT NULL,
    email TEXT,
    present_address TEXT NOT NULL,
    national_id_egov_evidence_reference TEXT NOT NULL,
    national_id_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (national_id_status IN ('pending', 'passed', 'failed')),
    tin_id_egov_evidence_reference TEXT NOT NULL,
    tin_id_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (tin_id_status IN ('pending', 'passed', 'failed')),
    meralco_bill_evidence_reference TEXT NOT NULL,
    meralco_bill_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (meralco_bill_status IN ('pending', 'passed', 'failed')),
    collector_visit_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (collector_visit_status IN ('pending', 'passed', 'failed')),
    collector_visit_evidence_reference TEXT,
    collector_visit_note TEXT NOT NULL DEFAULT '',
    collector_visit_by_user_id UUID REFERENCES core.users(id) ON DELETE SET NULL,
    collector_visit_completed_at TIMESTAMPTZ,
    eligibility_reviewed_by_user_id UUID REFERENCES core.users(id) ON DELETE SET NULL,
    eligibility_reviewed_at TIMESTAMPTZ,
    bypassed_requirements TEXT[] NOT NULL DEFAULT '{}'::text[],
    bypass_reason TEXT,
    bypassed_by_user_id UUID REFERENCES core.users(id) ON DELETE SET NULL,
    bypassed_at TIMESTAMPTZ,
    promoted_client_id UUID UNIQUE REFERENCES lending.clients(id) ON DELETE RESTRICT,
    privacy_consent BOOLEAN NOT NULL CHECK (privacy_consent),
    accuracy_declaration BOOLEAN NOT NULL CHECK (accuracy_declaration),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (btrim(application_reference) <> ''),
    CHECK (btrim(full_name) <> ''),
    CHECK (btrim(phone_number) <> ''),
    CHECK (btrim(present_address) <> ''),
    CHECK (
        cardinality(bypassed_requirements) = 0
        OR (
            btrim(coalesce(bypass_reason, '')) <> ''
            AND bypassed_by_user_id IS NOT NULL
            AND bypassed_at IS NOT NULL
        )
    ),
    CHECK (status <> 'eligible_for_cif' OR promoted_client_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS lending_client_onboarding_status_created_idx
    ON lending.client_onboarding_applicants(status, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS lending_client_onboarding_reference_lower_uidx
    ON lending.client_onboarding_applicants(lower(application_reference));

INSERT INTO core.permissions (code, description)
VALUES
    ('client_onboarding.requirement.review', 'Review normal pre-CIF onboarding requirements'),
    ('client_onboarding.visit.record', 'Record the Collector residence visit'),
    ('client_onboarding.bypass', 'Bypass pre-CIF requirements as Management')
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT r.id, p.code
FROM (VALUES
    ('employee', 'client_onboarding.requirement.review'),
    ('management', 'client_onboarding.requirement.review'),
    ('collector', 'client_onboarding.visit.record'),
    ('management', 'client_onboarding.bypass')
) AS mapping(role_code, permission_code)
JOIN core.roles r ON r.code = mapping.role_code
JOIN core.permissions p ON p.code = mapping.permission_code
ON CONFLICT DO NOTHING;

COMMIT;
```

- [ ] **Step 4: Re-run the migration contract GREEN**

```bash
python -m pytest gilbic_backend/tests/test_client_onboarding_migration.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the persistence reset**

```bash
git add gilbic_backend/sql/0112_add_guest_loan_applications.sql gilbic_backend/tests/test_client_onboarding_migration.py
git rm gilbic_backend/tests/test_guest_loan_application_migration.py
git commit -m "feat: reset onboarding persistence to pre-CIF gate"
```

---

### Task 2: Public lean applicant intake with zero private/financial side effects

**Files:**
- Delete: `gilbic_backend/tests/test_guest_loan_application_api.py`
- Create: `gilbic_backend/tests/test_client_onboarding_public_api.py`
- Create after RED: `gilbic_backend/src/gilbic_backend/client_onboarding_repository.py`
- Create after RED: `gilbic_backend/src/gilbic_backend/client_onboarding_api.py`
- Modify after RED: `gilbic_backend/src/gilbic_backend/main.py`

**Interfaces:**
- POST `/api/v1/public/onboarding/applicants`
- `PostgresClientOnboardingRepository.submit_applicant(...) -> ClientOnboardingRecord`
- Initial status is `requirements_incomplete`.
- Response contains only `application_reference`, `status`, `detail`.

- [ ] **Step 1: Write the RED public-intake API tests and remove the obsolete direct-loan test**

Request model fields must be exactly:

```python
class SubmitClientOnboardingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=2, max_length=200)
    phone_number: str = Field(min_length=7, max_length=40)
    email: str | None = Field(default=None, max_length=320)
    present_address: str = Field(min_length=5, max_length=500)
    national_id_egov_evidence_reference: str = Field(min_length=1, max_length=500)
    tin_id_egov_evidence_reference: str = Field(min_length=1, max_length=500)
    meralco_bill_evidence_reference: str = Field(min_length=1, max_length=500)
    privacy_consent: Literal[True]
    accuracy_declaration: Literal[True]
```

The test must prove all of these are rejected as extra input: `requested_amount`, `requested_loan_type`, `loan_purpose`, `baseline_face_scan_evidence_reference`, `username`, `password`.

- [ ] **Step 2: Run RED**

```bash
python -m pytest gilbic_backend/tests/test_client_onboarding_public_api.py -q
```

Expected: FAIL because `gilbic_backend.client_onboarding_api` does not exist.

- [ ] **Step 3: Implement the repository submission path**

Use `open_connection()` and one sequence call:

```python
sequence_value = cursor.execute(
    "select nextval('lending.client_onboarding_reference_seq')"
).fetchone()[0]
application_reference = f"APP-{datetime.now(UTC).year}-{sequence_value:06d}"
```

Insert only the approved intake fields. Do not insert into `core.users`, `lending.clients`, or `lending.loans`.

- [ ] **Step 4: Implement the public FastAPI route and normalization**

Normalize with:

```python
def _normalize_text(value: str) -> str:
    return " ".join(value.split())


def _normalize_phone(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())
```

Email is trimmed/lowercased when present. Return HTTP 201:

```json
{
  "application_reference": "APP-2026-000124",
  "status": "requirements_incomplete",
  "detail": "Keep this application reference to check your onboarding status."
}
```

- [ ] **Step 5: Mount `create_client_onboarding_router()` in `main.py`**

Import it near the other Client/account routers and include it once in `create_app()`.

- [ ] **Step 6: Run focused GREEN**

```bash
python -m pytest gilbic_backend/tests/test_client_onboarding_public_api.py -q
```

- [ ] **Step 7: Commit public intake**

```bash
git add gilbic_backend/src/gilbic_backend/client_onboarding_repository.py gilbic_backend/src/gilbic_backend/client_onboarding_api.py gilbic_backend/src/gilbic_backend/main.py gilbic_backend/tests/test_client_onboarding_public_api.py
git rm gilbic_backend/tests/test_guest_loan_application_api.py
git commit -m "feat: add lean pre-CIF applicant intake"
```

---

### Task 3: Staff/Management document review and Collector residence-visit recording

**Files:**
- Create: `gilbic_backend/tests/test_client_onboarding_review_api.py`
- Modify after RED: `gilbic_backend/src/gilbic_backend/client_onboarding_api.py`
- Modify after RED: `gilbic_backend/src/gilbic_backend/client_onboarding_repository.py`

**Interfaces:**
- PATCH `/api/v1/management/onboarding/applicants/{applicant_id}/document-requirements`
- POST `/api/v1/collector/onboarding/applicants/{applicant_id}/visit`
- `review_document_requirements(actor_user_id, applicant_id, national_id_status, tin_id_status, meralco_bill_status)`
- `record_collector_visit(actor_user_id, applicant_id, result, note, evidence_reference)`

- [ ] **Step 1: RED authorization and state tests**

Document review body:

```python
class DocumentRequirementReviewRequest(StrictOnboardingRequest):
    national_id_status: Literal["passed", "failed"]
    tin_id_status: Literal["passed", "failed"]
    meralco_bill_status: Literal["passed", "failed"]
```

Collector visit body:

```python
class CollectorVisitRequest(StrictOnboardingRequest):
    result: Literal["passed", "failed"]
    note: str = Field(default="", max_length=500)
    evidence_reference: str | None = Field(default=None, max_length=500)
```

Tests must prove:
- Employee + `client_onboarding.requirement.review` can review documents.
- Management + that permission can review documents.
- Collector and Client cannot review documents.
- Collector + `client_onboarding.visit.record` can record the visit.
- Employee, Management, and Client cannot use the Collector visit endpoint.
- Both protected routes require active device context.

- [ ] **Step 2: Run RED**

```bash
python -m pytest gilbic_backend/tests/test_client_onboarding_review_api.py -q
```

Expected: FAIL because the protected routes do not exist.

- [ ] **Step 3: Implement document review**

Use `authenticated_device_context()` with permission `client_onboarding.requirement.review`, then require role `employee` or `management`. Persist the three statuses, reviewer actor, and `updated_at`. Set applicant status to `requirements_rejected` if any reviewed document is `failed`; otherwise use `under_verification` until final eligibility.

Audit one row:

```text
action      = client_onboarding.documents_reviewed
target_type = client_onboarding_applicant
target_id   = applicant_id
details     = {national_id_status, tin_id_status, meralco_bill_status}
```

Do not put evidence references in audit details.

- [ ] **Step 4: Implement Collector visit recording**

Require permission `client_onboarding.visit.record` and role `collector`. Store result, actor, server completion timestamp, normalized note, optional controlled evidence reference, and audit:

```text
action      = client_onboarding.collector_visit_recorded
target_type = client_onboarding_applicant
target_id   = applicant_id
details     = {result}
```

A failed visit may set `requirements_rejected`; a later passed re-visit may return the applicant to `under_verification` unless already `eligible_for_cif`.

- [ ] **Step 5: Run focused GREEN**

```bash
python -m pytest gilbic_backend/tests/test_client_onboarding_review_api.py -q
```

- [ ] **Step 6: Commit review/visit behavior**

```bash
git add gilbic_backend/src/gilbic_backend/client_onboarding_api.py gilbic_backend/src/gilbic_backend/client_onboarding_repository.py gilbic_backend/tests/test_client_onboarding_review_api.py
git commit -m "feat: add pre-CIF requirement and residence review"
```

---

### Task 4: Normal eligibility creates one inactive Client identity atomically

**Files:**
- Create: `gilbic_backend/tests/test_client_onboarding_eligibility_api.py`
- Create: `gilbic_backend/tests/test_client_onboarding_promotion_postgres.py`
- Modify after RED: `gilbic_backend/src/gilbic_backend/client_onboarding_api.py`
- Modify after RED: `gilbic_backend/src/gilbic_backend/client_onboarding_repository.py`

**Interfaces:**
- POST `/api/v1/management/onboarding/applicants/{applicant_id}/eligibility`
- `approve_normal_eligibility(actor_user_id, applicant_id) -> ClientOnboardingRecord`
- Successful record exposes `promoted_client_id` internally; public intake/status never exposes it.

- [ ] **Step 1: RED API tests for the normal eligibility gate**

Prove:
- Employee/Management with `client_onboarding.requirement.review` are allowed.
- Any one non-passed requirement returns 409 and creates no Client.
- Collector/Client are denied.
- A fully passed applicant returns `eligible_for_cif` and one `client_id`.

- [ ] **Step 2: RED PostgreSQL atomic/idempotency test**

Seed an applicant with all four statuses `passed`, call repository approval twice, and assert:

```python
assert first.promoted_client_id == second.promoted_client_id
assert client_row["status"] == "inactive"
assert client_row["user_id"] is None
assert client_row["client_code"] == "CLIENT-2026-000124"
assert core_user_count_delta == 0
assert loan_count_delta == 0
assert matching_client_count == 1
```

- [ ] **Step 3: Implement one transaction with `SELECT ... FOR UPDATE`**

Inside `approve_normal_eligibility()`:

```sql
select *
from lending.client_onboarding_applicants
where id = %s
for update
```

If already `eligible_for_cif` with `promoted_client_id`, return the existing record unchanged.

Require all four statuses to equal `passed`. Generate:

```python
client_code = application_reference.replace("APP-", "CLIENT-", 1)
```

Insert:

```sql
insert into lending.clients (
    client_code, full_name, phone_number, area, status, user_id
) values (%s, %s, %s, %s, 'inactive', null)
returning id
```

Use `present_address` as the temporary `area` value only for this onboarding slice; Plan 3 may later normalize the routing/area field during CIF review without changing `client_id`.

Then update the onboarding row to `eligible_for_cif`, set `promoted_client_id`, reviewer actor/time, and write audit rows `client_onboarding.eligibility_approved` and `client_onboarding.client_created` in the same transaction.

- [ ] **Step 4: Run GREEN**

```bash
python -m pytest gilbic_backend/tests/test_client_onboarding_eligibility_api.py gilbic_backend/tests/test_client_onboarding_promotion_postgres.py -q
```

- [ ] **Step 5: Commit normal promotion**

```bash
git add gilbic_backend/src/gilbic_backend/client_onboarding_api.py gilbic_backend/src/gilbic_backend/client_onboarding_repository.py gilbic_backend/tests/test_client_onboarding_eligibility_api.py gilbic_backend/tests/test_client_onboarding_promotion_postgres.py
git commit -m "feat: promote eligible applicant to inactive Client"
```

---

### Task 5: Management-only audited bypass converges on the same promotion path

**Files:**
- Create: `gilbic_backend/tests/test_client_onboarding_bypass_api.py`
- Modify: `gilbic_backend/tests/test_client_onboarding_promotion_postgres.py`
- Modify after RED: `gilbic_backend/src/gilbic_backend/client_onboarding_api.py`
- Modify after RED: `gilbic_backend/src/gilbic_backend/client_onboarding_repository.py`

**Interfaces:**
- POST `/api/v1/management/onboarding/applicants/{applicant_id}/eligibility/bypass`
- `bypass_and_approve_eligibility(actor_user_id, applicant_id, bypassed_requirements, reason)`

- [ ] **Step 1: RED bypass policy tests**

Request:

```python
class ManagementBypassRequest(StrictOnboardingRequest):
    bypassed_requirements: list[
        Literal["national_id", "tin_id", "meralco_bill", "collector_visit"]
    ] = Field(min_length=1, max_length=4)
    reason: str = Field(min_length=3, max_length=500)
```

Tests must prove:
- Management role + `client_onboarding.bypass` is required.
- Employee with normal review permission receives 403.
- Collector receives 403.
- Empty/whitespace reason returns 422 before repository access.
- Duplicate bypass names are rejected/normalized to one unique set.
- The supplied bypass set must equal the current set of requirements that are not `passed`; omitting one non-passed requirement returns 409.
- Already-passed requirements cannot be falsely marked bypassed.
- If all four already passed, bypass returns 409 and instructs the caller to use normal eligibility.

- [ ] **Step 2: Run RED**

```bash
python -m pytest gilbic_backend/tests/test_client_onboarding_bypass_api.py -q
```

- [ ] **Step 3: Implement Management role/permission guard and repository bypass**

Lock the row, calculate:

```python
non_passed = {
    name
    for name, status in {
        "national_id": row["national_id_status"],
        "tin_id": row["tin_id_status"],
        "meralco_bill": row["meralco_bill_status"],
        "collector_visit": row["collector_visit_status"],
    }.items()
    if status != "passed"
}
```

Require `set(bypassed_requirements) == non_passed`.

Store the sorted requirement list, normalized reason, actor, and server timestamp. Write audit:

```text
action      = client_onboarding.requirements_bypassed
target_type = client_onboarding_applicant
target_id   = applicant_id
details     = {bypassed_requirements, reason}
```

Then call the same locked promotion helper used by Task 4. Do not change missing/failed requirement statuses to `passed`; the bypass record is the exception evidence.

- [ ] **Step 4: Extend PostgreSQL proof**

With all four requirements still pending, bypass all four and assert one inactive Client exists, the onboarding row keeps each requirement status as `pending`, and the bypass audit contains the exact set/reason/actor without raw evidence references.

- [ ] **Step 5: Run GREEN**

```bash
python -m pytest gilbic_backend/tests/test_client_onboarding_bypass_api.py gilbic_backend/tests/test_client_onboarding_promotion_postgres.py -q
```

- [ ] **Step 6: Commit bypass behavior**

```bash
git add gilbic_backend/src/gilbic_backend/client_onboarding_api.py gilbic_backend/src/gilbic_backend/client_onboarding_repository.py gilbic_backend/tests/test_client_onboarding_bypass_api.py gilbic_backend/tests/test_client_onboarding_promotion_postgres.py
git commit -m "feat: add audited Management pre-CIF bypass"
```

---

### Task 6: Exact subsystem verification and handoff to Plan 2/3

**Files:**
- Modify only after evidence is green: this plan checkbox/status section, GitHub #419/PR #420 metadata, Notion current-state checkpoint, Create State context.

**Interfaces:**
- No new product behavior.
- Produces a verified backend boundary for the later UI/CIF plans.

- [ ] **Step 1: Run every focused pre-CIF test**

```bash
python -m pytest \
  gilbic_backend/tests/test_client_onboarding_migration.py \
  gilbic_backend/tests/test_client_onboarding_public_api.py \
  gilbic_backend/tests/test_client_onboarding_review_api.py \
  gilbic_backend/tests/test_client_onboarding_eligibility_api.py \
  gilbic_backend/tests/test_client_onboarding_bypass_api.py \
  gilbic_backend/tests/test_client_onboarding_promotion_postgres.py -q
```

Expected: all pass; PostgreSQL test may skip only when `GILBIC_TEST_DATABASE_URL` is absent locally, but exact-head hosted disposable PostgreSQL must run before this slice is called complete.

- [ ] **Step 2: Run the repository's normal backend validation available in the environment**

At minimum:

```bash
python -m pytest gilbic_backend/tests -q
```

Do not accept new failures outside the intended TDD RED commit.

- [ ] **Step 3: Push exact head and use the existing CI handoff rule**

Do not poll continuously. Wait for Management/user to report **Red** or **All green**, then inspect the exact-head SPINA CI once.

Required hosted lanes before this subsystem is accepted:
- Backend, quality, and security
- Portal, Flutter, and Android
- Financial and disposable PostgreSQL

- [ ] **Step 4: Verify release boundaries from PostgreSQL evidence**

For both normal eligibility and Management bypass, prove:
- exactly one `lending.client_onboarding_applicants` row;
- exactly one linked `lending.clients` row with `inactive` + `user_id NULL`;
- zero new `core.users` rows;
- zero new `core.user_roles` rows;
- zero new `lending.loans` rows;
- bypass audit details contain no raw evidence references, passwords, OTPs, or biometric data.

- [ ] **Step 5: Synchronize project records**

Update GitHub #419, Draft PR #420, Notion, and Create State with the exact commit/CI result and explicitly state that UI, CIF activation/face enrollment, five-year CIF lifecycle, public verified status lookup, and loan application/review remain for subsequent plans.

- [ ] **Step 6: Stop before Plan 2/3 implementation**

Do not merge, deploy, create live applicant data, call live eGov/biometric providers, create production Auth users, or proceed into CIF/loan implementation without the next approved plan/Management gate.

## Self-review completed

- Spec coverage for this plan: pre-CIF intake, four requirements, Collector-only visit recording, Staff/Management normal review, Management-only audited bypass, and one inactive stable Client identity are covered.
- Intentionally deferred from this plan: public OTP/status lookup, all Web/Mobile UI, CIF content/baseline face scan, five-year CIF lifecycle/re-verification, Client activation, loan application/review, contract/release, credentials, and renewal execution.
- No placeholder tasks are present.
- Shared interface names are consistent: `ClientOnboardingRecord`, `PostgresClientOnboardingRepository`, `create_client_onboarding_router()`, `promoted_client_id`, and the three permission codes above.
- The existing merged credential flow remains untouched and continues to require an active unlinked borrower at its own later lifecycle gate.
