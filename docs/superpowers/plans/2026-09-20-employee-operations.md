# Employee Operations Implementation Plan

> **For agentic workers:** Implement the approved specification continuously in this branch. The user requested one complete batch followed by combined tests. Independent client work may run in parallel with backend work after the API contract is frozen; do not pause for intermediate approval.

**Goal:** Deliver the approved three-person employee workflow on FastAPI/Postgres, Android and Web while preserving existing financial authority.
**Architecture:** Focused employee domain records in the existing private core schema, server-owned calculations and scoped transitions, existing authenticated clients. A finite typed employee command API is an application boundary, not a generic workflow engine. No new provider, live payment initiation or production DB use.
**Tech Stack:** Python/FastAPI/Pydantic/psycopg/Postgres; Flutter/Dart with existing protected device storage; vanilla JavaScript portal and node:test.
**Spec:** docs/superpowers/specs/2026-09-20-employee-operations.md

## Global Constraints

- Three employees, one combined Collector/office/staff-manager; one identity. No unrestricted Management membership for that worker.
- Eight compensated hours; daily-rate Sunday-Saturday payroll paid after Saturday shift. Employee-specific schedules and real rates are required setup.
- Owner can approve all; combined worker cannot approve any own correction/leave/shift/advance/payroll, irrespective of memberships.
- Good Performance Benefits100/day, prorated working minutes/480, no paid-leave credit, whole-week disqualification only on confirmed own shortage; no automatic wage deduction without lawful basis.
- Five ordinary paid leave days/service year after one year, preserved unused credits and separate special leave.
- Offline attendance/break capture only; durable account/device-bound outbox, stable IDs, original capture time, server acceptance and conflict review.
- Exact money arithmetic, versioned inputs, immutable payment/decision history, idempotency and atomic balance checks.
- No actual personal staff values seeded, no production migrations/payments, no PR437 mutation, no merge/deploy or frozen Master296 reorder.

## Review Focus

- Mixed memberships and own-record approval: deny self-approval at repository boundary, not just UI; prove loan approval remains absent from narrow staff-manager responsibility.
- Timeout after accepted write: same ID and payload returns prior result; changed payload/actor must reject. Pending events survive restart/account changes without cross-account upload.
- Saturday/cross-month payroll: accepted attendance and versioned rates only; do not treat missing configuration or pending corrections as zero pay; reconcile monthly totals without repeated deduction.
- False shortage and changed records after approval: restore benefit via adjustment; stale unpaid approvals invalidated; paid snapshots retained, recoveries never disguised as advances.
- Private data and offline errors: employee sees own data; staff review scope exact; revocation and uncertain delivery do not become silent success or duplicate financial action.

### Task 1: Backend employee application and contract
**Files:** new gilbic_backend/src/gilbic_backend/employee_operations.py, employee_operations_models.py, employee_operations_repository.py, employee_operations_api.py; migration gilbic_backend/sql/0128_add_employee_operations.sql; main.py router registration; backend tests test_employee_operations*.py; docs/superpowers/specs/2026-09-20-employee-api-contract.md.
**Interfaces:** GET /api/v1/employee-operations/workspace returns data with actor capability flags and visible employee profiles, attendance, requests, tasks, advances, payroll, shortages and accounting preparations. POST /api/v1/employee-operations/actions accepts a strict finite discriminated command with stable request_id and expected_version for updates; exact command shapes recorded in contract before client implementation. Auth uses authenticated_device_context; repository remains authoritative.
- [ ] Publish exact strict request/response contract and synthetic examples first.
- [ ] Add failing public domain tests for partial-day480/240 minutes, confirmed-shortage weekly loss, separate lawful recovery, principal caps, leave eligibility and duplicate/stale writes.
- [ ] Implement focused domain calculations/validation and Postgres transactional persistence, auditable history and row locks. Real statutory monthly inputs/coverage required; unknown configuration blocks affected calculation with a specific reason.
- [ ] Add API permission/strict-payload and real disposable Postgres persistence/security/idempotency cases, plus registration.
- [ ] Test each public seam, report commands/results and update contract for any necessary compatibility changes before clients consume them.

### Task 2: Android employee workflows and durable attendance
**Files:** new gilbic_mobile/lib/src/core/employee_operations/* and features/employee/employee_operations_page.dart; employee/collector/management dashboard navigation; tests employee_operations*_test.dart and existing dashboard tests.
**Interfaces:** consume exact Task1 contract through StaffOperationsClient; use existing session and DeviceIdentityProvider. Plain forms and readable records, no raw JSON input.
- [ ] Test pending attendance survives restart, binds account/device, dedups, refuses cross-account upload and handles rejected/uncertain sync.
- [ ] Add employee attendance/break actions, requests/tasks/leave/advances/payslips and scoped owner/manager preparation/review/setup forms matching server capability flags.
- [ ] Add protected durable outbox using existing dependency, retry when app reconnects/resumes while active; preserve pending errors, no financial actions queued.
- [ ] Wire Employee, Collector and Management entry points and combined office/collection access without client-side financial authority.
- [ ] Run meaningful repository/widget/navigation tests and Flutter analysis; record results.

### Task 3: Web employee and owner workflows
**Files:** new spina_portal/assets/employee-operations.js; relevant role workspace navigation; presenters as necessary; spina_portal/tests/employee-operations.test.mjs and integration tests.
**Interfaces:** consume Task1 contract via existing SpinaApi; separate DOM view lifecycle and safe escaped text, scoped capability flags. Web mutations online-only.
- [ ] Write failing renderer/action tests for own versus reviewer views, salary components, missing setup and rejected mutation feedback.
- [ ] Build named staff setup, time/review/task/leave/advance/shortage/payroll/payment/accounting forms and lists, with request IDs/versions and safe refresh after uncertain writes.
- [ ] Add role entry points retaining existing workspaces and link combined responsibilities without granting Management approval.
- [ ] Run portal tests/build/public-output checks; record results.

### Task 4: Integration, permission administration and combined verification
**Files:** existing auth/membership surfaces only where necessary; disposable runner migration list and CI; docs/state and focused integration tests.
- [ ] Review complete coverage of approved specification and client/backend contract; repair missing interfaces, never label an unsupported UI control implemented.
- [ ] Verify membership-preserving narrow responsibility grant and actual owner mapping. Existing loan approval/release/cash controls stay authoritative; add denied cases for combined membership and own-record review.
- [ ] Ensure new migration replays in disposable test setup and private-schema barrier applies.
- [ ] Run required complete backend, portal and Flutter suites, source lint/analysis and disposable financial tests, then independent review and fixes.
- [ ] Commit scoped changes, push separate feature branch and open draft dependent PR against priority-9/staff-android-completion. Document exact test evidence and pending real-device/production setup gates; no merge/deploy.

## Execution ledger

- 20 September: user Approve authorizes the recommendation and implementation. Separate feature/employee-operations branch created from verified f059b943; clean baseline evidence is existing CI35427733914,699Flutter/544Portal/2467Backend/742financialPostgres. No source changes at baseline.
- Planning decision: preserve the existing isolated spina-p9 worktree, switch to a new branch rather than creating another checkout; original PR437 branch remains at f059b943.
- Planning decision: independent backend/mobile/portal ownership allows useful parallel work. Root owns integration and whole-batch review; no repeated user approval gates.
