# Office-Only CIF + First-Loan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Use strict RED -> GREEN TDD for every behavior change.

**Goal:** Continue verified Priority #4 Plan 1 into the Management-approved office-only first-loan flow without reviving public new-applicant self-service or creating duplicate Area, schedule, accounting, Auth, or workflow engines.

**Architecture:** Keep verified `lending.client_onboarding_applicants` as the pre-CIF eligibility record and keep its four-requirement / Management-bypass / idempotent inactive-Client promotion authority unchanged. First, retire the superseded public intake route and make intake Staff-assisted behind the existing authenticated-device boundary. Then add a lean versioned CIF and baseline live-face evidence boundary, separate applicant CIF/application confirmation from loan contract signing, reuse the existing loan/schedule/account authorities for Management-approved first-loan terms and office release, and trigger the existing Client-account lifecycle only after successful actual release.

**Tech Stack:** PostgreSQL, psycopg 3, FastAPI/Pydantic, pytest, existing SPINA auth/device/account repositories, existing loan/schedule/accounting services, vanilla portal tests, Flutter/Dart tests.

**Authoritative spec:** `docs/superpowers/specs/2026-09-10-office-only-cif-first-loan-design.md`

## Verified starting point

- Priority #4 Plan 1 is already verified complete at `c1d071168c4d5e6e8bfea4f0e0bd9ed8d986e836` / SPINA CI #1889.
- The office-only design was approved by Management on 2026-09-10.
- Documentation head `4d0c1d07ced0b1b8ebb35f2cfeb7526bf00ca495` passed SPINA CI #2007 across all three required lanes.
- Preserve Plan 1 authority: normal eligibility requires eGov National ID + eGov TIN ID + accepted Meralco bill + passed Collector residence visit; only Management may bypass; eligibility creates exactly one inactive `lending.clients` identity with `user_id=NULL` and no loan/Auth/schedule/accounting side effects.

## Global constraints

- Brand-new applicants do not self-start or continue first-loan application/CIF work on public Web/Mobile.
- No public reference/OTP status continuation for brand-new applicants in V1.
- Office Staff/Employee owns interview and encoding; Collector owns only the approved residence-visit duty for first-loan onboarding.
- Collector cannot own office encoding, final eligibility, bypass, first-loan approval, or first-loan release.
- CIF stays lean and versioned; no raw biometric template, raw government-ID media, contact-list scraping, or unnecessary ID values.
- Baseline live-face/liveness belongs to CIF after pre-CIF eligibility, not to the four pre-CIF requirements.
- Application/CIF confirmation is distinct from Management loan approval, locked contract signing, and actual release.
- Management owns exact-term approval and explicit release authorization.
- First-loan signing and cash handoff are office-only. No mandatory face+money photo.
- Actual successful release is all-or-nothing for financial state, uses the actual release date for the authoritative schedule, and triggers the existing managed Client-account lifecycle idempotently.
- Do not create a second routing engine, schedule engine, accounting engine, authentication system, or generic workflow/form-builder.
- Do not finalize lawyer-dependent disclosure/contract wording in code; maintain a template/integration boundary.
- No live eGov, biometric, OTP, SMS, payment-provider, production DB/Auth, real applicant, or real cash mutation in development.
- PR remains Draft/open/unmerged until explicit Management integration approval.

---

### Task 1: Retire public intake and enforce office-only Staff-assisted intake

**Files:**
- Create RED first: `gilbic_backend/tests/test_client_onboarding_office_intake_api.py`
- Remove after RED is proven: `gilbic_backend/tests/test_client_onboarding_public_api.py`
- Modify after RED: `gilbic_backend/src/gilbic_backend/client_onboarding_api.py`
- Keep repository behavior unless a focused test proves a change is required: `gilbic_backend/src/gilbic_backend/client_onboarding_repository.py`

**Interfaces:**
- Remove POST `/api/v1/public/onboarding/applicants` completely; do not leave a compatibility alias.
- Protected office intake: POST `/api/v1/management/onboarding/applicants`.
- Reuse `authenticated_device_context()` and existing `client_onboarding.requirement.review` permission so no new permission/schema churn is introduced merely to move the intake boundary.
- Allow only `employee` or `management` roles even if another role is accidentally granted the permission.
- Reuse existing strict `SubmitClientOnboardingRequest` fields and normalization.
- Response remains minimal: `application_reference`, `status`, `detail`; the detail must not tell the applicant to check a public status flow.

- [x] **Step 1: Write the strict RED office-intake contract.** Prove public intake is absent, Employee/Management + permission + active device can encode, Collector cannot encode even if granted the permission, missing permission is denied, and active device context is required.
- [ ] **Step 2: Verify RED on exact head.** Expected failure is the existing public route still returning 201 and the protected office route not existing yet.
- [ ] **Step 3: Make the minimum API change.** Move submission to the protected office path, call `authenticated_device_context()`, enforce Employee/Management role, preserve strict input and repository behavior, and use an office-only response detail.
- [ ] **Step 4: Remove the superseded public-intake test rather than weakening it into an alias expectation.**
- [ ] **Step 5: Run focused GREEN plus existing eligibility/review/bypass tests.**
- [ ] **Step 6: Run disposable PostgreSQL onboarding validation to prove zero Client/Auth/loan side effects before eligibility and unchanged idempotent promotion at eligibility.**

Do not add Web/Mobile application forms in this task.

---

### Task 2: Add lean versioned CIF + baseline live-face enrollment boundary

**Files:**
- RED migration/API/repository tests first under `gilbic_backend/tests/`.
- Create migration using reserved follow-on number `gilbic_backend/sql/0114_add_client_cif_first_loan_foundation.sql` to avoid colliding with Priority #5's already-used 0113 migration line.
- Create focused CIF repository/API modules under `gilbic_backend/src/gilbic_backend/` only after RED.
- Extend disposable PostgreSQL validation only after focused behavior is Green.

**Minimum data contract:**
- CIF row is keyed to stable `client_id`; names are never identity keys.
- Preserve immutable historical versions; one current operational version at a time.
- Store only lean identity/contact/residence/supporting facts required by the approved CIF plus controlled evidence references.
- Store baseline live-face evidence reference + liveness result/status; no raw biometric template in relational tables.
- Five-year validity; `expiring` window begins 90 days before expiry.
- Re-verification flags can block new loans/renewals but do not disable existing collections/payments/portal servicing.

- [ ] RED schema tests prove version/history constraints, five-year/90-day lifecycle fields, baseline evidence/liveness boundary, and absence of password/raw-biometric fields.
- [ ] RED repository/API tests prove only an already `eligible_for_cif` stable Client can begin CIF work.
- [ ] Employee/Management may encode; Collector/Client may not own CIF encoding.
- [ ] CIF activation requires the approved required checks plus passed baseline liveness.
- [ ] Activation changes the existing Client from inactive to active exactly once; it must not create Auth credentials, loans, schedules, journals, or disbursements.
- [ ] Disposable PostgreSQL proof preserves prior CIF versions and one current version.

No live biometric provider is added; tests use controlled fake evidence references/results.

---

### Task 3: Staff review summary + applicant CIF/application confirmation

**Files:**
- Backend tests first for read-only summary, corrections, and confirmation.
- Minimal Staff portal surface only after backend contract is Green.

**Behavior:**
- Staff prepares CIF plus first-loan application facts in office using the stable Client identity.
- Applicant receives a read-only review summary in office.
- Staff may correct data before confirmation.
- Confirmation records server timestamp and Staff witness/actor.
- Confirmation is immutable evidence of applicant information review only; it must not approve the loan, sign the final contract, release cash, create credentials, or start a schedule.

- [ ] RED tests prove confirmation cannot occur before required CIF/application information is complete.
- [ ] RED tests prove post-confirmation corrections create a new review/confirmation cycle rather than silently mutating signed facts.
- [ ] RED tests prove Collector cannot encode or confirm the office application.
- [ ] GREEN implementation remains narrow and audited.

---

### Task 4: First-loan application and Management exact-term approval

Before production code, inspect the existing loan creation/approval/schedule contracts on the live branch and reuse them. Do not create a parallel loan state machine just because this onboarding stream needs an `Approved / Pending Release` phase.

**Behavior:**
- Active CIF is required before Management can approve a first loan.
- Management approves/rejects exact authoritative amount, rate, term/schedule basis, and allowed fees.
- Approval stores an immutable borrower/CIF/application snapshot for the loan.
- Approval does not activate the schedule or create Client credentials.
- A locked disclosure/contract payload is generated from the approved terms through a replaceable legal-template boundary.
- If the current shared loan model cannot represent approved-but-not-released without schedule activation, stop and add the smallest compatible state extension under its own RED test rather than introducing a second loan engine.

- [ ] RED role/permission tests prove Collector/Employee cannot approve.
- [ ] RED state tests prove approval uses exact terms and cannot be silently edited afterward.
- [ ] RED snapshot tests prove later CIF changes cannot rewrite approved/released historical evidence.

---

### Task 5: Management release authorization + atomic office cash release

Before implementation, inspect and reuse existing disbursement, schedule, receipt, accounting, and Client-account services.

**Required release gates:**
- exact locked contract version signed by the named borrower;
- valid non-revoked Management release authorization for the exact approved loan;
- authorized Employee/Office Staff release actor with active device context;
- borrower confirmation of exact cash received;
- authoritative server release date/time and official receipt evidence.

**Effects:**
- all-or-nothing financial release transition;
- loan becomes Released only on successful actual handoff;
- schedule starts from actual release date using existing authoritative schedule rules;
- no face+money photo requirement for first-loan office release;
- failed/cancelled/blocked handoff remains Approved/Pending Release and creates no schedule/credentials/partial cash state;
- after committed release, invoke the existing Client-account lifecycle idempotently/retry-safely so one permanent Client account is created/linked and future loans reuse it. Do not attempt a fake distributed transaction with the external Auth provider.

- [ ] RED tests prove stale/revoked/mismatched authorization blocks release.
- [ ] RED tests prove Employee cannot change approved financial terms at release.
- [ ] RED PostgreSQL tests prove no partial financial state on failure and correct actual-release-date schedule on success.
- [ ] RED idempotency tests prove repeated release/account-trigger calls do not duplicate loan, schedule, receipt, Auth-link request, or Client account linkage.

---

### Task 6: Staff UI, post-release Client view, and full exact-head verification

**Staff UI:**
- office intake, requirement review, CIF encoding, applicant review/confirmation, Management approval, locked contract handoff, release authorization/status, and receipt handoff only as permitted by role.
- Do not add a generic workflow builder or duplicate business logic in JavaScript/Flutter.

**Client Web/Mobile:**
- signed-out surface must not expose Apply, applicant status continuation, or self-registration for brand-new Clients.
- after SPINA creates/links the Client account, authenticated servicing may show server-authoritative loan amount, actual release date, first payment date, required payment amount, and schedule as read-only values.

**Verification:**
- [ ] focused backend tests Green;
- [ ] focused portal tests Green;
- [ ] focused Flutter tests Green;
- [ ] disposable PostgreSQL onboarding/CIF/first-loan proof Green;
- [ ] full exact-head SPINA CI Green across Backend/quality/security, Portal/Flutter/Android, and Financial/disposable PostgreSQL;
- [ ] synchronize PR #420, Master #296, Notion current state, and Create State/handoff if available;
- [ ] keep PR Draft/open/unmerged until explicit Management integration approval.

## Low-friction execution protocol

After each strict test-only head, perform one exact-head CI read and stop. Management may answer only **Red** or **Green / All green**. On Red, inspect the exact matching failure and add only the minimum production correction. On Green, independently verify the exact matching head/checks before advancing. Re-read the live PR head immediately before every Git write to avoid overwriting concurrent work.
