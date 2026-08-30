# CB1 Mobile Initial ECL Allowance Implementation Plan

**Goal:** Expose the existing protected initial ECL allowance prepare/post
workflow through a permission-scoped Gilbic Mobile Management workspace.

**Architecture:** Flutter consumes the existing mobile aliases in
`ecl_allowance_posting_api.py`. Exact server values flow through strict typed
models into the existing backend requests. No accounting rule, SQL, ECL
calculation, or state transition is copied into mobile.

**Spec:** `docs/superpowers/specs/2026-08-30-cb1-mobile-ecl-allowance.md`

## Constraints

- Preserve the exact backend permissions and approved-device enforcement.
- Keep monetary values as exact currency strings in mobile contracts.
- Use one stable token per action + authoritative digest after uncertain I/O.
- Reload after success instead of synthesizing queue state.
- Keep every non-actionable/A5/audit-incomplete state read-only.
- Do not change SQL, A5, tax, automatic posting, production data, deployment,
  signing, or release state.

## Task 1 — Typed queue and repository

**Files:**
- Create `gilbic_mobile/lib/src/core/management/ecl_allowance_posting.dart`.
- Create `gilbic_mobile/lib/src/core/management/ecl_allowance_posting_repository.dart`.
- Create `gilbic_mobile/test/ecl_allowance_posting_repository_test.dart`.

- [x] Write RED tests for strict queue parsing and exact prepare/post bodies.
- [x] Implement summary, permission, queue-item, action-receipt, and repository
      contracts against the existing mobile routes.
- [x] Prove invalid/incomplete action coordinates fail before network I/O.
- [x] Prove safe FastAPI detail/code propagation.
- [x] Run focused tests and commit the green contract layer.

## Task 2 — Protected Management queue

**Files:**
- Create `gilbic_mobile/lib/src/features/management/management_ecl_allowance_posting_page.dart`.
- Create `gilbic_mobile/test/management_ecl_allowance_posting_page_test.dart`.
- Modify the Management review surface catalog and inventory test.

- [x] Write RED widget tests for summary/status visibility, permission
      intersection, cancel/confirm, exact facts, same-token retry, and reload.
- [x] Add the protected review surface with actions `prepare` and `post`.
- [x] Implement the minimal filterable queue with explicit read-only states.
- [x] Generate separate secure preparation/post tokens and retain them only for
      an uncertain retry of the same snapshot.
- [x] Run focused tests and commit the green Management page.

## Task 3 — Financial Accounting integration

**Files:**
- Modify `management_financial_accounting_page.dart` and its widget test.

- [x] Write a RED navigation test for the `initial-ecl-allowance` launcher.
- [x] Add an injectable repository and open the exact protected page.
- [x] Preserve all existing Financial Accounting and formal period-close flows.
- [x] Run affected Management regressions and commit the integration.

## Task 4 — Verify and publish

- [x] Run focused repository/widget tests and strict Flutter analysis.
- [x] Run complete Flutter and backend suites; report configured skips.
- [x] Run Dart formatting and branch diff checks.
- [x] Review Standards and Spec separately.
- [ ] Commit these docs, push a branch stacked on Draft PR #383, and open a new
      Draft PR.
- [ ] Require exact-head CI, then update the PR, Master Issue #296, and Notion.
- [x] Do not check the whole CB1 box or merge/deploy/release.

## Local verification checkpoint

Recorded on 2026-08-30 PH against implementation head
`905b646af8fe75cc5a2c4885701896512760b833` before this documentation commit.

- Focused ECL/accounting tests: 18 passed after the final strict-summary review
  correction; the earlier combined review inventory run passed 22 checks.
- Flutter analyzer: no issues.
- Complete Flutter suite: 412 passed on the corrected implementation head.
- Complete backend suite: 1,282 passed, 188 configured skips. The backend tree
  did not change after this run. Warnings were the upstream Starlette/httpx
  deprecation and a non-functional local pytest-cache permission warning.
- Dart formatter: 9 touched source/test files checked, 0 changed.
- Standards review: corrected omission of the server-derived
  `preparation_blocked_count` and made the returned server filter fail closed.
- Spec review: no remaining blocker; the slice remains A4 initial allowance
  only and introduces no mobile ECL calculation, SQL, A5, automatic posting,
  production data, signing, deployment, or release action.
- The unrelated local deletion of `architecture-map.json` remains unstaged and
  outside this slice.
