# Management Mobile CB1 Acceptance Matrix

## Purpose

This matrix is the automated evidence index for the CB1 Management Mobile
security and integrity requirement in Master Issue #296. It verifies reuse of
the shared backend, exact role and permission behavior, protected review
controls, retry/stale handling, and shared Android/iOS Flutter behavior.

This document does **not** replace the owning tests or PostgreSQL evidence. It
links them into one repeatable release pack and distinguishes current automated
proof from native-device, human-review, signing, merge, deployment, and
production gates.

## Current implemented behavior

| CB1 control | Automated proof | Current result |
|---|---|---|
| One backend authority | The dedicated Backend/Database workstream owns the permanent registered-route proof that every `/api/mobile/v1/management...` alias has one canonical `/api/v1/management...` peer with the identical handler object. This Mobile branch carries no backend route, schema, auth, SQL, or migration change. | Exact backend proof is a required integration dependency before broad CB1 can close; Mobile cannot satisfy it with UI tests. |
| Required Management families | The Mobile destination inventory requires representative dashboard, alerts/audit, client/loan, collection, Employee activity, renewal, support, accounting, statement, Trial Balance, close, ECL, capital, and tax destinations. Repository-level mock-HTTP tests prove client-registration list, candidate, approve, and reject requests use the canonical `/api/v1/management` paths and HTTP methods. | A missing Mobile destination or a client-registration repository path regression fails the Mobile pack. Backend route registration and authorization remain Backend-owned evidence. Mobile does not create a second client-approval business path. |
| Canonical role and dashboard permission | `management_dashboard_information_architecture_test.dart` renders the real `EnhancedRoleDashboard` with and without `management.dashboard.view` on Android and iOS targets. Existing API tests separately reject non-Management roles, absent approved-device identity, and missing action permissions. | The full Management command surface is available only to an allowed Management session; the denied session receives the restricted account/notification shell. |
| Exact launcher permissions | `role_dashboard_permission_navigation_test.dart` and the Management information-architecture tests exercise exact visibility plus tap-time rechecks for accounting, staff/device, renewal, support, remittance, collection, and other protected destinations. | A stale visible launcher cannot bypass the current session permission check. Server authorization remains mandatory. |
| Protected confirmation | `ManagementReviewPresentation.validated` requires one typed `ManagementMutationBinding`; raw mutation surfaces cannot be supplied by production callers. The binding enum is the single owner/surface/action/risk registry, and `management_review_surface_inventory_test.dart` structurally proves the 23 bindings are complete, ordered, unique, and one-to-one with the approved surfaces. Generic Android/iOS tests prove the shared review component renders every binding consistently; owning-page tests verify real evidence and cancellation/confirmation behavior. | Protected actions retain source facts, status, warnings, next action, consequence, risk treatment, and explicit confirmation. Read-only containers stay outside the mutation registry. Generic component parity is not represented as native or per-owner acceptance. |
| Stable uncertain retry | Period close, ECL allowance, ECL A5, initial capital, tax liability, and other owning page tests prove an uncertain retry reuses the same confirmation token or idempotency coordinate for the same immutable source. | A timeout does not silently create a new financial intent. |
| Stale or ambiguous result | Tax settlement/adjustment and Tax Recoverable page tests prove ambiguous writes lock further action until authoritative refresh. Other protected repositories revalidate exact digests, periods, accounts, amounts, and source identities. | Mobile cannot guess success, invent replacement coordinates, or continue from a possibly stale source. |
| Audit attribution and atomicity | The owning PostgreSQL suites for period close, ECL, initial capital, tax amendments, and Tax Recoverable verify actor attribution, immutable audit, exact retry behavior, and rollback on forced audit failure. Alerts & Audit uses allowlisted owning records and protected journal events. | A protected posting and its audit evidence succeed or roll back together; Mobile does not write audit rows directly. |
| Shared Android/iOS Flutter behavior | The Management information-architecture test derives the same 22 authorized launchers from one destination inventory and proves every launcher is present for an allowed session and absent for a denied session on Android and iOS platform targets. The review inventory separately proves typed binding-registry completeness and generic component parity for all 23 mutation surfaces. | Shared Dart/navigation/review behavior is proven without creating an iOS-only business path. Native Xcode/device evidence remains open. |

## Exact automated pack

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  gilbic_backend\tests\test_client_registration_approval_api.py `
  gilbic_backend\tests\test_management_alerts_audit_api.py `
  gilbic_backend\tests\test_management_dashboard_overview_api.py `
  gilbic_backend\tests\test_management_employee_activity_api.py `
  gilbic_backend\tests\test_period_close_api_contract.py `
  gilbic_backend\tests\test_ecl_allowance_posting_api_contract.py `
  gilbic_backend\tests\test_ecl_a5_accounting_api_contract.py `
  gilbic_backend\tests\test_initial_capital_funding_api_contract.py `
  gilbic_backend\tests\test_v1_tax_evidence_api_contract.py `
  gilbic_backend\tests\test_v1_tax_liability_api_contract.py `
  gilbic_backend\tests\test_v1_tax_settlement_api_contract.py `
  gilbic_backend\tests\test_v1_tax_adjustment_api_contract.py `
  gilbic_backend\tests\test_v1_tax_additional_amendment_api_contract.py `
  gilbic_backend\tests\test_v1_tax_recoverable_refund_api_contract.py `
  gilbic_backend\tests\test_v1_tax_recoverable_credit_api_contract.py

Set-Location gilbic_mobile
flutter test `
  test\management_dashboard_information_architecture_test.dart `
  test\client_registration_review_repository_test.dart `
  test\client_registration_approvals_page_test.dart `
  test\role_dashboard_permission_navigation_test.dart `
  test\management_review_surface_inventory_test.dart `
  test\management_period_close_page_test.dart `
  test\management_ecl_allowance_posting_page_test.dart `
  test\management_ecl_a5_accounting_page_test.dart `
  test\management_initial_capital_funding_page_test.dart `
  test\management_tax_evidence_page_test.dart `
  test\management_tax_liability_page_test.dart `
  test\management_tax_settlement_adjustment_page_test.dart `
  test\management_additional_tax_page_test.dart `
  test\management_tax_recoverable_page_test.dart
```

The permanent Financial/Database workflow remains responsible for the disposable
PostgreSQL matrices, and the dedicated Backend/Database task owns the corrected
registered-route integrity proof. Do not substitute Mobile UI tests or skipped
local database tests for that exact-head backend evidence.

## Historical local verification checkpoint

On 2026-08-31, predecessor commit
`383b44d9894fd3fca3109eab06f14398a8dbd22e` passed **57 focused Flutter tests**,
the complete Mobile suite passed **495 tests**, and strict Flutter analysis
reported no issues. The touched Dart files required no formatter changes; diff
and scoped secret-pattern checks were clean. This immutable reference predates
the typed-binding and repository-request review corrections and is therefore
historical evidence only, not exact-head proof for the current branch. The Draft
PR must supply exact-head CI provenance before this acceptance slice can close.
Registered-route, backend authorization, disposable PostgreSQL, and integrated
stack proof remain owned by the Backend/Database and permanent CI workstreams.

## Intended future behavior and still-open gates

The following are not proven by Flutter target-platform widget tests or route
introspection and remain open until separately evidenced:

- Management visual/usability approval of the Android review build under CA2;
- Xcode compilation, iOS Simulator/device behavior, Apple signing, provisioning,
  archive creation, install/upgrade smoke tests, and Management iOS visual review;
- broad cross-role and cross-tenant acceptance under CB5;
- Backend custody review of the shared backend/auth/SQL delta currently carried
  by stacked base PR #391, plus the corrected registered-route integrity proof;
- exact stacked-base integration, merge/readiness decision, release-candidate
  environment, production migrations/data operations, deployment, signing, and
  the `v1.0` tag;
- any actual protected financial action against live or production records.

Direct Client GCash remains the non-interactive Xendit placeholder. Create State
is a resumed secondary continuity index; GitHub, repository documentation, and
authoritative server/PostgreSQL evidence remain controlling.
