# Employee operations verification

This batch adds employee workflows to the existing backend, portal and Android
app. The approved scope and decisions are in
[the specification](superpowers/specs/2026-09-20-employee-operations.md);
[private setup](employee-operations-setup.md) describes activation prerequisites.

## Automated evidence

| Boundary | Proof |
| --- | --- |
| Owner, combined memberships and financial permissions | `test_employee_authorization.py` and `test_employee_authorization_postgres.py`: actual role mappings preserve Collector/Employee access, exclude loan approval, reject stale account/device authority and reuse existing unposted journal drafts. |
| Pay calculations and transport | `test_employee_operations.py` and `test_employee_operations_api.py`: exact amounts, partial days, holidays, overtime, leave eligibility, finite commands and controlled error/readback responses. |
| Persisted employee workflows | `test_employee_operations_postgres.py`: independent approvals, source versions, partial payments, benefit decisions, principal reservations, statutory allocations, leave conversion, history, private scope and immutable evidence. |
| Concurrent writes | `test_employee_operations_concurrency_postgres.py`: two actual database sessions prove one payout on replay/conflict and safe profile-update/attendance lock ordering. It uses and drops its own generated loopback database. |
| Web workflows | `employee-operations.test.mjs` and `employee-operations-contract.test.mjs`: real DOM submissions for all 30 actions, exact money text, online gating, uncertain outcomes, disposal, scoped history and daily attendance chains. |
| Android workflows | Employee repository, command, widget, navigation, outbox, storage and service tests: actual form submissions, verified membership choices, private-content clearing, atomic protected storage wiring, restart, account changes and renewed authentication. |

Independent review reproduced and verified fixes for existing-record reset
attempts, cross-domain history collisions and stale annual payroll reservations.
Further regressions cover restricted backup duties, repeated transfer references,
pending advance terms and conversion of a full five-day leave balance.

Both clients' 30 captured command bodies were checked against the backend's
`ACTION_ADAPTER`; their synthetic exports and run logs are recovery artifacts
outside the repository. They contain no real employee setup values.

## Combined checks

The existing SPINA CI workflow runs the full backend, portal and Flutter suites,
builds the Android package, and replays disposable financial checks. Its existing
onboarding database runner now includes migration 0128 and the employee database
and concurrency proofs. Migration 0113 is included before its dependent migrations.
No new deployment workflow or production test database is introduced.

Use the pull request's exact-head checks for final run status. Focused green tests
do not by themselves establish that the full candidate or device acceptance passed.
Existing repository-wide scanner findings remain separate from these regressions.

## Device acceptance still required

On the Android candidate build, verify clock-in/break/clock-out online and offline,
restart before synchronization, reconnect and observe one accepted event per tap.
Verify another account cannot send the first account's pending events, revoked
access pauses them, and a fresh authorized sign-in resumes the original binding.
Check the combined worker can use Collector/Office workspaces and cannot approve
their own payroll or a loan. Review an ordinary payslip and its linked adjustment
using synthetic data before entering actual private staff configuration.

Mocked native storage channels prove key and transaction wiring; they are not
physical-device encryption or acceptance evidence. This batch does not establish
lawful shortage deductions, initiate provider transfers, file agency returns,
deploy migrations or activate live payroll.
