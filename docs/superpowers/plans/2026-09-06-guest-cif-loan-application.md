# Guest CIF + Loan Application Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the approved #419 pre-account borrower application flow without restoring Client self-registration or creating loans/accounting records.

**Architecture:** A new `lending.guest_loan_applications` staging table owns guest intake and review state. Public submission/status APIs and Management review APIs use one focused repository; approval promotes exactly one official `lending.clients` row, after which the already-merged Client-account endpoint remains the only credential creator.

**Tech Stack:** PostgreSQL, psycopg 3, FastAPI/Pydantic, pytest, vanilla ES portal tests, Flutter/Dart tests.

**Spec:** `docs/superpowers/specs/2026-09-06-guest-cif-loan-application-design.md`

## Current checkpoint — 2026-09-06

Task 1 is complete and exact-head SPINA CI #1860 is fully green on `7831035fbe68341a55fb13e669606d66d7f90d5f`. Task 2 has entered RED on `08b0728c8924cab811878cc65146b5e8c8a5b059` with focused public guest-submission API contract tests; the guest API/repository are intentionally not implemented yet.

## Global Constraints

- Do not create `core.users` or Client permissions from public guest submission.
- Do not create `lending.loans`, schedules, journals, contracts, disbursements, or releases from #419.
- Keep CIF lean; do not restore the abandoned overbuilt CIF.
- Store only identity/selfie evidence references in the normal application row; no raw binary evidence or unnecessary government-ID values.
- Public status is reference + verified one-time challenge, never reference-only.
- Review/decision is Management-only in this version.
- Reuse `/api/v1/management/client-accounts` for credentials after borrower promotion; do not duplicate Auth logic.
- Development uses fake applicant/evidence/OTP values only. No production deployment, live credential delivery, live applicant communication, live DB/Auth mutation, or real identity upload.
- TDD is strict RED -> GREEN for every behavior.

---

### Task 1: Guest application persistence boundary

**Files:**
- Create: `gilbic_backend/tests/test_guest_loan_application_migration.py`
- Create after RED is verified: `gilbic_backend/sql/0112_add_guest_loan_applications.sql`

**Interfaces:**
- Produces: `lending.guest_loan_applications` and `lending.guest_loan_application_reference_seq`.
- Produces permission: `loan_application.manage`, Management only.

- [x] **Step 1: Add the failing migration contract test**

```python
from pathlib import Path

SQL_PATH = Path(__file__).resolve().parents[1] / "sql" / "0112_add_guest_loan_applications.sql"


def test_guest_application_is_pre_account_and_management_reviewed() -> None:
    sql = SQL_PATH.read_text(encoding="utf-8").lower()
    assert "create table if not exists lending.guest_loan_applications" in sql
    assert "guest_loan_application_reference_seq" in sql
    assert "application_reference text not null unique" in sql
    assert "status in ('submitted', 'under_review', 'approved', 'rejected')" in sql
    assert "promoted_client_id uuid unique" in sql
    assert "references lending.clients(id)" in sql
    assert "reviewed_by_user_id uuid" in sql
    assert "references core.users(id)" in sql
    assert "user_id uuid" not in sql.replace("reviewed_by_user_id uuid", "")
    assert "client.credential.manage" not in sql
    assert "loan_application.manage" in sql
    assert "('management', 'loan_application.manage')" in sql
    assert "('employee', 'loan_application.manage')" not in sql
    assert "('collector', 'loan_application.manage')" not in sql
    assert "('client', 'loan_application.manage')" not in sql
```

- [x] **Step 2: Run only the test and verify RED**

Run: `python -m pytest gilbic_backend/tests/test_guest_loan_application_migration.py -q`

Expected: FAIL because `0112_add_guest_loan_applications.sql` does not exist.

- [x] **Step 3: Add the minimum additive migration**

Create one idempotent `BEGIN/COMMIT` migration with these columns:

```sql
CREATE SEQUENCE IF NOT EXISTS lending.guest_loan_application_reference_seq;

CREATE TABLE IF NOT EXISTS lending.guest_loan_applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_reference TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'submitted'
        CHECK (status IN ('submitted', 'under_review', 'approved', 'rejected')),
    full_name TEXT NOT NULL,
    phone_number TEXT NOT NULL,
    email TEXT,
    present_address TEXT NOT NULL,
    permanent_address TEXT NOT NULL,
    livelihood_type TEXT NOT NULL,
    livelihood_details TEXT,
    declared_monthly_income NUMERIC(18,2) NOT NULL CHECK (declared_monthly_income >= 0),
    declared_monthly_expenses NUMERIC(18,2) NOT NULL CHECK (declared_monthly_expenses >= 0),
    declared_monthly_debt_payments NUMERIC(18,2) NOT NULL CHECK (declared_monthly_debt_payments >= 0),
    requested_loan_type TEXT NOT NULL CHECK (requested_loan_type IN ('regular', '7x7')),
    requested_amount NUMERIC(18,2) NOT NULL CHECK (requested_amount > 0),
    requested_term_days INTEGER NOT NULL CHECK (requested_term_days > 0),
    loan_purpose TEXT NOT NULL,
    national_id_evidence_reference TEXT NOT NULL,
    tin_id_evidence_reference TEXT NOT NULL,
    selfie_evidence_reference TEXT NOT NULL,
    privacy_consent BOOLEAN NOT NULL CHECK (privacy_consent),
    accuracy_declaration BOOLEAN NOT NULL CHECK (accuracy_declaration),
    applicant_status_note TEXT,
    internal_review_note TEXT,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    review_started_at TIMESTAMPTZ,
    reviewed_at TIMESTAMPTZ,
    reviewed_by_user_id UUID REFERENCES core.users(id) ON DELETE SET NULL,
    promoted_client_id UUID UNIQUE REFERENCES lending.clients(id) ON DELETE RESTRICT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (btrim(application_reference) <> ''),
    CHECK (btrim(full_name) <> ''),
    CHECK (btrim(phone_number) <> '')
);
```

Add indexes on `(status, submitted_at DESC)` and lower-cased application reference, then add `loan_application.manage` to `core.permissions` and only the Management role.

- [x] **Step 4: Re-run migration contract test**

Run: `python -m pytest gilbic_backend/tests/test_guest_loan_application_migration.py -q`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add gilbic_backend/tests/test_guest_loan_application_migration.py gilbic_backend/sql/0112_add_guest_loan_applications.sql
git commit -m "feat: add guest loan application persistence"
```

---

### Task 2: Public guest submission

**Files:**
- Create: `gilbic_backend/src/gilbic_backend/guest_loan_application_repository.py`
- Create: `gilbic_backend/src/gilbic_backend/guest_loan_application_api.py`
- Create: `gilbic_backend/tests/test_guest_loan_application_api.py`
- Create: `gilbic_backend/tests/test_guest_loan_application_repository_postgres.py`
- Modify: `gilbic_backend/src/gilbic_backend/main.py`

**Interfaces:**
- Produces: POST `/api/v1/public/loan-applications`.
- Produces: `GuestLoanApplicationRepository.submit(...) -> GuestLoanApplicationRecord`.
- Submission response contains only `application_reference`, `status`, `detail`.

- [x] **Step 1: Write failing API tests** proving strict input, normalized email/phone/text, fake evidence references accepted, and no Auth/Client dependency is called.
- [ ] **Step 2: Verify RED** with `python -m pytest gilbic_backend/tests/test_guest_loan_application_api.py -q`.
- [ ] **Step 3: Implement repository reference generation** using one PostgreSQL `nextval('lending.guest_loan_application_reference_seq')` and `APP-{UTC_YEAR}-{sequence:06d}`; insert the submitted row in one transaction.
- [ ] **Step 4: Implement strict Pydantic request** with bounded strings, positive requested amount/term, non-negative affordability values, required `privacy_consent=True`, required `accuracy_declaration=True`, and `requested_loan_type` normalized to `regular` or `7x7`.
- [ ] **Step 5: Mount the router** in `main.py` and return HTTP 201 with no authentication or device requirement.
- [ ] **Step 6: Add disposable PostgreSQL repository test** proving one submission creates exactly one guest row and zero `core.users`, zero `lending.clients`, and zero `lending.loans` rows.
- [ ] **Step 7: Run focused tests GREEN** and commit `feat: add public guest loan submission`.

---

### Task 3: Verified safe status lookup

**Files:**
- Create: `gilbic_backend/src/gilbic_backend/application_status_verifier.py`
- Modify: `gilbic_backend/src/gilbic_backend/guest_loan_application_api.py`
- Modify: `gilbic_backend/src/gilbic_backend/guest_loan_application_repository.py`
- Create/modify: `gilbic_backend/tests/test_guest_loan_application_status_api.py`

**Interfaces:**
- Produces: POST `/api/v1/public/loan-applications/status-challenges`.
- Produces: POST `/api/v1/public/loan-applications/status`.
- `ApplicationStatusVerifier.issue(reference, destination_hint) -> challenge_id`.
- `ApplicationStatusVerifier.verify(challenge_id, code) -> bool`.

- [ ] **Step 1: RED tests** prove reference-only lookup does not exist, invalid challenge/code reveals no application, and verified lookup returns only `application_reference`, `status`, `submitted_at`, `reviewed_at`, `applicant_status_note`.
- [ ] **Step 2: Implement an injectable verifier protocol** plus a disabled default adapter that returns 503 when no approved provider is configured. Tests override the dependency with an in-memory fake; no live SMS/email is sent.
- [ ] **Step 3: Add repository safe-status projection** that never selects evidence refs, affordability values, internal notes, reviewer ID, promoted client ID, or credentials.
- [ ] **Step 4: Run focused status tests GREEN** and commit `feat: add verified guest application status lookup`.

---

### Task 4: Management review and idempotent borrower promotion

**Files:**
- Modify: `gilbic_backend/src/gilbic_backend/guest_loan_application_api.py`
- Modify: `gilbic_backend/src/gilbic_backend/guest_loan_application_repository.py`
- Create: `gilbic_backend/tests/test_management_guest_loan_application_api.py`
- Create: `gilbic_backend/tests/test_guest_loan_application_promotion_postgres.py`

**Interfaces:**
- Produces Management list/detail endpoints under `/api/v1/management/loan-applications`.
- Produces POST `/api/v1/management/loan-applications/{application_id}/review`.
- Produces POST `/api/v1/management/loan-applications/{application_id}/decision` with `{decision: approve|reject, applicant_status_note, internal_review_note}`.
- Approval returns `promoted_client_id`; rejection returns none.

- [ ] **Step 1: RED authorization tests** prove Management + `loan_application.manage` is required and Employee/Collector/Client are denied.
- [ ] **Step 2: RED transition tests** prove submitted -> under_review -> approved/rejected only, and a decided row cannot be decided again.
- [ ] **Step 3: RED PostgreSQL promotion test** calls approval twice and proves at most one `lending.clients` row exists for the guest application.
- [ ] **Step 4: Implement review transition** with `SELECT ... FOR UPDATE`, reviewer/timestamps, and `core.audit_logs` entries.
- [ ] **Step 5: Implement approval promotion** inside the same PostgreSQL transaction. Generate `client_code` as `CLIENT-` plus the numeric tail of `application_reference` left-padded to six digits; copy only `full_name`, `phone_number`, and a route/area value when a reviewed area is later present. Do not create a user or loan. Store the resulting `promoted_client_id` back on the application.
- [ ] **Step 6: Implement rejection** with safe applicant note + internal note and no borrower/account creation.
- [ ] **Step 7: Run focused API/PostgreSQL tests GREEN** and commit `feat: add management guest application review`.

---

### Task 5: Signed-out Web and Mobile entry surfaces

**Files:**
- Modify: `spina_portal/index.html`
- Modify: `spina_portal/assets/app.js`
- Modify: `spina_portal/assets/app.css`
- Create: `spina_portal/assets/guest-loan-application.js`
- Create: `spina_portal/tests/guest-loan-application.test.mjs`
- Modify: `gilbic_mobile/lib/src/features/auth/login_page.dart`
- Create: `gilbic_mobile/lib/src/features/auth/guest_loan_application_page.dart`
- Create: `gilbic_mobile/lib/src/features/auth/guest_application_status_page.dart`
- Create/modify: `gilbic_mobile/test/guest_loan_application_test.dart`

**Interfaces:**
- Signed-out surface exposes exactly `Sign in`, `Apply for a loan`, `Check application status`.
- Web/Mobile form submits only the public API fields from Task 2.
- Status page uses Task 3 challenge + verification flow.

- [ ] **Step 1: RED Web tests** assert the three entry actions and no Client self-registration action.
- [ ] **Step 2: Add minimal Web form/status panels** using existing portal components and `SpinaApi`; no framework or new design system.
- [ ] **Step 3: RED Flutter tests** assert the same three actions and navigation.
- [ ] **Step 4: Add minimal Flutter pages** using existing API/config/session conventions; do not persist sensitive evidence values beyond the active form submission.
- [ ] **Step 5: Run Node and Flutter focused tests GREEN** and commit `feat: add guest application entry surfaces`.

---

### Task 6: Management UI handoff and full verification

**Files:**
- Create: `spina_portal/assets/management-loan-applications.js`
- Modify: `spina_portal/assets/roles.js`
- Create: `spina_portal/tests/management-loan-applications.test.mjs`
- Create: `gilbic_mobile/lib/src/features/management/management_loan_applications_page.dart`
- Create/modify: `gilbic_mobile/test/management_loan_applications_test.dart`
- Update: `docs/superpowers/plans/2026-09-06-guest-cif-loan-application.md` checkboxes/status only after evidence is green.

**Interfaces:**
- Management can list/open/review/approve/reject.
- Approved item exposes a handoff to the existing Client-account creation workflow using `promoted_client_id`; it does not implement a second credential creator.

- [ ] **Step 1: RED UI policy tests** prove non-Management roles cannot see/execute the review surface.
- [ ] **Step 2: Implement minimal review queue/detail/actions** and handoff to existing Client-account administration.
- [ ] **Step 3: Run all focused backend/portal/Flutter tests**.
- [ ] **Step 4: Run disposable PostgreSQL proof** for submit -> review -> approve -> single borrower, with zero user/loan side effects before the separate account step.
- [ ] **Step 5: Run the repository's normal unified validation locally when available, then rely on exact-head SPINA CI for hosted proof.**
- [ ] **Step 6: Update GitHub #419, Notion current-state checkpoint, and Create State with the exact head/CI state. No merge until explicit Management approval.**
