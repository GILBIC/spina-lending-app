# SPINA Management Web UI Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. The owner selected Codex as executor. Keep one integration owner for shared Management/app/CSS files; use parallel reviewers only where useful. Steps use checkbox syntax for tracking.

**Goal:** Complete the released Management Web UI corrections without redesigning SPINA or changing financial behavior.

**Architecture:** Repair the existing vanilla-JavaScript portal in place. Separate portfolio presentation and a small Management task lifecycle from existing orchestration, keep mounted drafts during navigation, refresh only affected data, and preserve authorization/privacy teardown. Reuse current loaders, renderers, mobile table styling, and protected write modules.

**Tech Stack:** Existing ES modules, HTML/CSS, Node.js >=22, built-in node:test, existing portal build/PWA tooling, and current FastAPI/PostgreSQL APIs unchanged. Browser inspection uses available tooling and synthetic data; add no product dependency for the review.

**Spec:** [2026-10-02-management-web-ui-completion-design.md](../specs/2026-10-02-management-web-ui-completion-design.md).

**State:** Planning-only handoff. All implementation and runtime-verification boxes below are pending. Baseline `41a13eb59c9cc1b65a0a6a51f3b73db4a0895013` after PR #484. The owner authorized this plan and Draft PR and will separately start Codex. No implementation, merge, mark-ready, production mutation, migration, delivery, or deployment is performed by this planning change.

## Global constraints

- Preserve Today / Clients & loans / Collections / Accounting / People & operations / Account, their existing IDs, Management workspace precedence, and pink/white identity.
- No new frontend framework, global state library, router, persistence layer, virtual-list framework, backend endpoint, financial calculation, or speculative feature.
- Keep server permissions, endpoint/query semantics, exact server amounts/order, and read-only-versus-write boundaries. Never total a partial list.
- No new form/credential persistence in localStorage, sessionStorage, IndexedDB, URLs, or service-worker storage. Keep existing memory-only uncertain-request recovery and scope invalidation. Draft retention must not extend the lifetime of passwords or one-time secrets.
- Keep financial writes online-only; preserve duplicate-submit, uncertainty, idempotency, stale-version, source-type, confirmation, and journal-post/reversal safeguards.
- Cash Disbursement prepares an expense draft and does not send money. Employee stays prepare-only. `automatic_source_posting=false` remains unchanged.
- Preserve one-time credentials, stale borrower/email invalidation, logout/identity/device/permission cleanup, and exact private/capture-eligible boundaries.
- Web Management is the change surface. Other roles/platforms are regression surfaces, not redesign targets.
- No production writes/credentials/capture, migrations, dependency upgrades, CI weakening, Master #296 edits, delivery/deployment runs, automatic merge, or marking ready.
- Complete one task's red/green/review/commit before the next. Do not push deliberately failing tests to manufacture CI traffic. Never claim acceptance from old-head CI.

## Review focus

1. Delayed/malformed reads, successful recovery, and filtered/limited lists must not show false zeros or mix snapshots — Task 1.
2. Successful save plus failed refresh, another dirty queue row, manual Refresh, and token rotation must not discard work or authorize duplicate writes — Tasks 2–3.
3. Rapid navigation/account selection, slow focus transitions, and logout/permission changes must not deliver late results into another task/session — Tasks 3–4.
4. Local task changes inside one top-level group must preserve private-screen boundaries and invalidate capture before panel changes — Task 5.
5. Unknown statuses/domains, more server records than loaded records, filtered device mutations, and narrow/zoomed long content must remain truthful and reachable — Tasks 6–8.

## File map and ownership

Primary orchestration: `spina_portal/assets/roles/management.js`. Shell/lifecycle: `spina_portal/assets/app.js`; navigation: `spina_portal/assets/ui.js`. Prefer existing navigation callbacks over a new routing system.

Two planned focused product modules:
- `spina_portal/assets/management-portfolio.js`: portfolio summary/results and search/retry lifecycle; move related helpers rather than copy them.
- `spina_portal/assets/management-workspace-tasks.js`: Management-only activation, first-load deduplication, local task selection, cleanup. Not a reusable app framework.

Other bounded edits under `spina_portal/assets/`: `management-devices.js`, `management-alerts-audit.js`, `cash-disbursement.js` (markup/layout only), `app.css`, and `presenters.js` only for truthful Management state. Update `spina_portal/sw.js` in the same commit as any new module that requires shell membership. Other roles must retain existing behavior.

Read-only contract references: `gilbic_backend/src/gilbic_backend/management_loan_api.py`, `gilbic_backend/src/gilbic_backend/management_loan_repository.py`; under `spina_portal/assets/`, `management-general-journal.js`, `management-journal-actions.js`, `management-accounting.js`, `account-credentials.js`, `client-account-admin.js`, `screen-sharing.js`, `employee-operations.js`, `area-management.js`, and Office workflow modules. Do not rewrite protected workflows to simplify navigation. A narrow screen-sharing visibility correction is allowed only when hidden local tasks require it, with direct tests and no new eligible screen.

All `.test.mjs` names below are under `spina_portal/tests/`. Reuse its existing helpers; helper additions may supply fixture mechanics, not a second DOM framework. Asset basenames below refer to `spina_portal/assets/` unless stated otherwise.

## Task 0 — Establish the exact execution baseline

**Files:** Read this plan/spec, applicable `AGENTS.md`, `package.json`, `.github/workflows/spina-ci.yml`, and relevant tests. Do not change them merely to run the plan.

- [ ] Fetch live main, this PR head, open PRs, latest Notion Current State, and Create State project `69a61c48-f842-44ac-aa11-e987ffec4a36`. Review frozen Master #296 without editing it.
- [ ] Work on this PR's branch in an isolated Codex worktree. Confirm a clean tree. Do not reset someone else's work or create a duplicate implementation PR.
- [ ] Compare current files to baseline. For an upstream fix, reproduce its acceptance tests and retain evidence instead of reverting/reimplementing it. Reconcile changed interfaces without broadening scope.
- [ ] Inspect `package.json`; run baseline portal checks once if equivalent exact-head evidence is absent. Separate inherited failures from new failures; do not weaken assertions.
- [ ] Add a PR checkpoint with execution SHA, ownership, baseline results/limitations, and next task.

**Deliverable:** Reproducible starting point, not a product change. Once the owner starts Codex, no recurring approval of unchanged task details is needed.

## Task 1 — Truthful portfolio states and recovery (R1)

**Files:** Create `management-portfolio.js`; modify `roles/management.js` and `spina_portal/sw.js` as required; test `management-portfolio-state.test.mjs` (new) and `management-client-loan-grouping.test.mjs`.

**Interfaces:** `managementPortfolioSummaryMarkup({status, summary}) -> string`, status `loading | ready | error`. `mountManagementPortfolio({root, api, signal, initialResult}) -> {refresh(): Promise<void>, dispose(): void}`. Optional initialResult uses existing `{data, error}`; otherwise load the existing active-portfolio endpoint. Own only the portfolio panel. Move existing grouped-loan rendering intact, preserving escaping/type/identity behavior.

- [ ] Write `initial_failure_is_unavailable`, `search_recovery_updates_summary_and_rows`, `explicit_zero_is_valid`, `missing_fields_are_not_zero`, `filtered_rows_keep_global_summary`, and `older_or_aborted_search_cannot_commit`. Use summary `{active_client_count: 6, active_loan_count: 10, active_remaining_total: '12345.67', overdue_active_count: 1}` with fewer returned cards; a paid/no-match list can still have that nonzero active summary.

```js
assert.doesNotMatch(managementPortfolioSummaryMarkup({status: 'error', summary: {}}), /₱0\.00/);
assert.match(managementPortfolioSummaryMarkup({status: 'error', summary: {}}), /Portfolio summary unavailable/);
assert.match(managementPortfolioSummaryMarkup({status: 'ready', summary: {
  active_client_count: 0, active_loan_count: 0,
  active_remaining_total: '0.00', overdue_active_count: 0,
}}), /₱0\.00/);
```

- [ ] Run `node --test spina_portal/tests/management-portfolio-state.test.mjs`; confirm missing/incorrect behavior, not a harness failure.
- [ ] Move related helpers; implement Loading/dashes, error/retry, independent field validation, and summary/results refresh from each successful response. Label global summary **Active portfolio · all clients** and list **Search results**. The existing API returns global active summary separately from filtered/limited rows. Validate presence/shape before exact money formatting. Preserve query/status; add last-request and abort guards. No second endpoint or list summation.
- [ ] Run the new suite plus `management-client-loan-grouping.test.mjs`, `presenters.test.mjs`, `business-formatting.test.mjs`, and affected PWA tests. Inspect fail-then-search recovery in a local browser.
- [ ] Commit `fix(web): keep portfolio summary truthful through recovery`; record red/green evidence.

## Task 2 — Local post-save refresh without losing drafts (R2)

**Files:** Modify `roles/management.js`; test `management-local-refresh.test.mjs` (new), `role-local-updates.test.mjs`, and relevant staff/queue suites.

**Interfaces:** Management-scoped `refreshManagementRegion(context, region) -> Promise<void>`, region `support | renewals | staff | overview`. Update only affected/read subregions using current API/session/abort context. Never call `mountManagementWorkspace` for these post-save updates. Keep the helper colocated; no global store.

- [ ] Write `support_save_preserves_unrelated_drafts`, `renewal_save_preserves_unrelated_drafts`, `staff_invite_preserves_unrelated_drafts`, `post_save_read_failure_does_not_report_write_failure`, and `other_dirty_queue_row_survives`. Assert node identity and values for search, Office intake, and another unsent support response; exactly one mocked mutation and relevant reads only.
- [ ] Run `node --test spina_portal/tests/management-local-refresh.test.mjs`; record expected reset failures.
- [ ] Replace the three full-remount success paths. Separate successful mutation from failed subsequent refresh; clear only the submitted form/row. Refresh counts from authoritative reads, never local subtraction. Reuse Task 1 refresh where needed. Dispose/rebind only replaced regions; preserve validations, confirmations, duplicate and uncertain-write safeguards.
- [ ] Run the new suite, `role-local-updates.test.mjs`, `staff-invite.test.mjs`, and `management-staff-devices-presentation.test.mjs`. Check duplicate clicks, failed refresh, and abort produce no extra handlers/writes.
- [ ] Commit `fix(web): preserve Management drafts after queue actions`.

## Task 3 — On-demand loading and safe header Refresh (R2–R3)

**Files:** Create `management-workspace-tasks.js`; modify `roles/management.js`, `app.js`, `spina_portal/sw.js` as needed; test `management-lazy-loading.test.mjs` (new), `workspace-lifecycle.test.mjs`, `session-refresh.test.mjs`, `shell.test.mjs`, and service-worker suites.

**Interfaces:** `createManagementTaskController({root, signal, getSession, tasks, beforeTaskChange, afterTaskChange}) -> {activate(groupId, taskId?), refreshVisible(): Promise<void>, dispose(): void}`. Task records contain id/group, current permission predicate, first-load/local-refresh functions, and cleanup. State/pending promises belong to the mount; deduplicate load/binding and retain retry. `getSession()` reads current authority, not a stale closure.

Add one optional shell handle registration guarded by the current AbortController. Existing onNavigate activates the handle with privacy hooks retained; Management header Refresh uses refreshVisible. Other roles keep existing behavior. Authentication/permission changes still fully dispose/remount. The mount receives a copied context: reject/dispose late handle registration from a superseded mount and ensure same-identity token refresh updates the session source for lazy mounts. Do not rely on mutating only the old copied context.

- [ ] Write `today_does_not_wait_for_loan_operations`, `today_does_not_wait_for_accounting_staff_or_audit`, `revisit_mounts_once`, `task_error_is_local_and_retryable`, `header_refresh_keeps_dirty_fields`, `expired_handle_cannot_register_or_render`, and `permission_change_clears_old_tasks`. Assert actual requests/DOM using deferred promises.
- [ ] Run `node --test spina_portal/tests/management-lazy-loading.test.mjs`; confirm eager-load/reset failures.
- [ ] Render stable groups/placeholders first, then account/dashboard independently. Move non-Today data AND module mounting to first activation. Use dashboard queue metrics or neutral/unavailable links, not unloaded zeros. Integrate Tasks 1–2 refreshes. Hide mounted forms rather than rebuild them. Header Refresh retains drafts; explicitly confirm discard only when an editor cannot safely refresh its own dirty input. Abort/dispose child work on scope change.
- [ ] Run listed lifecycle/session/shell/PWA suites plus the new tests. Cover uncertain Cash Disbursement across same-identity token rotation and invalidation on identity/device/permission change. Include new modules in public/PWA assets without caching protected responses.
- [ ] Commit `perf(web): load Management tasks only when needed`.

## Task 4 — Staff phone layout and device-panel focus (R4)

**Files:** Modify `roles/management.js`, `management-devices.js` as needed, and `app.css`; test `management-staff-mobile-focus.test.mjs` (new), `management-staff-devices-presentation.test.mjs`, `management-devices.test.mjs`, `ui-busy-focus.test.mjs`.

**Interfaces:** Retain `bindStaffDevices(context, accounts)` cleanup and device mutation signatures. Add Staff-specific mobile class/data labels. Track exact opener and selection generation for focus.

- [ ] Write `staff_cells_have_mobile_labels`, `device_open_moves_focus_when_still_intended`, `device_close_restores_opener`, `late_selection_does_not_steal_focus`, and `account_only_permission_never_loads_devices`. Include user focus moved during loading, removed opener, revoked device, and error Close.
- [ ] Run `node --test spina_portal/tests/management-staff-mobile-focus.test.mjs`; observe failures and capture 390/320px synthetic baseline.
- [ ] Reuse mobile-card styling at the existing 680px breakpoint. Retain desktop columns, exact data/IDs, selected row, and permission-dependent action. Move focus after current detail load only when still intended; Close returns to opener or visible Staff heading. Keep protected confirmations/reloads, busy/error locking, and readable 48px controls.
- [ ] Run listed suites. Inspect desktop/390/320 screenshots, long names/emails, tab order and focus. No one-character columns or font shrinking; overflow checks alone do not pass.
- [ ] Commit `fix(web): make Staff devices usable on narrow screens`.

## Task 5 — Local task selection and precise alert navigation (R5)

**Files:** Modify `management-workspace-tasks.js`, `roles/management.js`, `management-alerts-audit.js`, bounded `app.js` wiring and `app.css`; narrowly correct `screen-sharing.js` visibility only if required. Test `management-task-navigation.test.mjs` (new), `workspace-navigation.test.mjs`, `management-office-guided-workflow.test.mjs`, `management-alerts-audit-presentation.test.mjs`, `screen-sharing.test.mjs`.

**Interfaces:** Reuse Task 3 activate(groupId, taskId?). Retain top-level data-nav-target; add an explicit Management task allowlist. Preserve `managementAlertNavigationTarget` group return for compatibility; add `managementAlertTaskTarget(code) -> taskId | null`. Unknown/absent targets must not become arbitrary links.

- [ ] Write `six_top_groups_are_unchanged`, `local_tasks_preserve_dom_and_selection`, `staff_alert_opens_staff_not_audit`, `renewal_and_support_alerts_open_their_task`, `unauthorized_or_unknown_target_is_not_actionable`, and `local_switch_invalidates_capture_before_dom_change`. Pin task menus/defaults to the spec; test same-group navigation, delayed loads, permission removal, keyboard use, hidden focus.
- [ ] Run `node --test spina_portal/tests/management-task-navigation.test.mjs` and existing navigation tests; confirm missing behavior.
- [ ] Implement permission-filtered local tasks for Clients & loans, People & operations, and Accounting. Keep Office's four steps together with existing reference revalidation. Reuse protected modules, not duplicate editors or new accounting overview calculations. Deep-link known alerts to permitted actual tasks. For remittance review, inspect the existing surface and use an honest read-only/group fallback when no exact authorized review target exists.
- [ ] Wire existing sharing teardown/eligibility around local switches: stop/invalidate active/preparing capture BEFORE hiding/replacing its panel. Never promote capture markers to whole groups. Test mocked tracks/frames and hidden-child visibility; do not start real capture.
- [ ] Run listed suites plus client-account/credential safety, client-loan grouping, and journal-deduplication tests. Every formerly reachable permitted workflow stays reachable.
- [ ] Commit `feat(web): add focused Management task navigation`.

## Task 6 — Compact audit/device lists with full evidence retained (R6)

**Files:** Modify `management-devices.js`, `management-alerts-audit.js`, and narrow `roles/management.js` state handoff; test `management-list-density.test.mjs` (new) plus device/audit suites.

**Interfaces:** Extend `bindManagedDevicePanel(root, options = {}) -> cleanup` while preserving its function return. Options carry initialFilter/initialLimit and onStateChange for explicit selection retention in the parent; update all call sites together. Keep original device ID/index mapping. Audit binding holds its own matching-count/visible-limit state without a remote store.

- [ ] Write `pending_default_shows_two_of_36`, `explicit_filter_survives_status_refresh`, `all_show_more_reaches_all_36_in_order`, `filtered_action_uses_original_device_id`, `unknown_device_is_reachable_in_all`, `audit_visible_count_is_not_server_total`, and `similar_events_remain_distinct`. Pin initial/increment to 10; cover 0/12/100 audit events and server total exceeding loaded rows.
- [ ] Run `node --test spina_portal/tests/management-list-density.test.mjs`; record unbounded/default-state failures.
- [ ] On first account open choose Pending if present, otherwise Active if present, otherwise All. Preserve explicit filter on refresh even when now empty. Show 10 matching rows, add up to 10 with Show more, and display loaded/visible counts. Filter changes reset cap, not data. Audit disclosure retains all evidence/server order, visible_domains, and `window_days=30&limit=100`. No deletion, deduplication, local inference about unloaded records, or refetch loop.
- [ ] Run new and existing device/audit tests; in browser reach the 36th device, inspect duplicate-looking events, and mutate a filtered fixture device using its original ID. Check focus and filter retention.
- [ ] Commit `refactor(web): compact Management audit and device lists`.

## Task 7 — Today, Accounting, and Account visual density (R7)

**Files:** Modify `roles/management.js`, scoped `app.css`, Cash Disbursement markup only as needed; test `management-ui-density.test.mjs` (new), `management-dashboard-presentation.test.mjs`, `accounting-presentation.test.mjs`, `cash-disbursement-workspace.test.mjs`, `cash-disbursement.test.mjs`, `my-account-security-presentation.test.mjs`.

**Interfaces:** Reuse metric renderers, task handles, and field names. No new totals, upload control, cash endpoint, or password API.

- [ ] Write `zero_attention_is_compact_but_available`, `unavailable_attention_is_not_zero`, `cash_editor_mounts_only_when_selected`, `cash_purpose_and_evidence_use_wide_fields`, and `account_profile_has_bounded_width`. Preserve Workspace/Additional access, password/reset separation, and draft/does-not-send-money wording.
- [ ] Run `node --test spina_portal/tests/management-ui-density.test.mjs`; confirm current density/auto-mount failures.
- [ ] Compact successful zero queues with labels/counts still reachable; move work actions higher. Mount Cash Disbursement on task selection, retaining its protected workflow/recovery. Give purpose/evidence full-row width. Target 720px max profile width, fluid on phones. Reuse spacing/tokens/button hierarchy and 48px controls; remove only redundant nesting/copy, not required warning/status text.
- [ ] Run listed suites plus `web-ui-hierarchy.test.mjs`, `account-credentials.test.mjs`, and `client-account-safety-presentation.test.mjs`. Preserve Employee prepare-only and uncertain retry in the shared cash module. Inspect desktop/phone Today, Accounting, Account.
- [ ] Commit `style(web): refine Management density without changing workflows`.

## Task 8 — Integrated verification, evidence, and handoff (R1–R7)

**Files:** Changed tests, existing `tools/check_portal_modules.mjs`, `tools/build_portal.mjs`, and the **Verify public portal output** step in `.github/workflows/spina-ci.yml` (run/reuse, do not weaken). Update this checklist. Use `spina_portal/tests/fixtures/management-ui-completion.html` and a synthetic helper only if no equivalent fixture exists; they must not enter public output.

- [ ] Map every R1–R7 requirement to tests/browser evidence. Separate baseline observations from actual new results. Dynamically reproduce both Support and Renewal; the earlier review submitted only mocked Support.
- [ ] At final integration run the full portal checks once, then build without repeating them. The public-output check is inline in current CI, not a separate checker file. Use Bash (or the exact equivalent in the executor environment):

```sh
set -euo pipefail
npm run check:portal
npm run test:portal
node tools/build_portal.mjs
test -f dist/index.html
test -f dist/assets/app.js
test -f dist/manifest.webmanifest
test ! -d dist/tests
if grep -R -E 'GILBIC_(DATABASE_URL|SUPABASE_SECRET_KEY)|service_role|postgresql://' dist; then
  echo 'Public portal output contains a forbidden backend secret pattern.'
  exit 1
fi
git diff --check
```

Re-read current CI if it changed. Do not follow with npm run build on the same unchanged head: package.json repeats tests there. A syntax pass is not behavioral verification. Inspect public files in addition to the secret-pattern scan.

- [ ] Use actual built assets with synthetic API fixtures and block unexpected external/mutating requests. Capture six sections at 1440/390/320px: 18 samples. Include 36 devices, 100 audit events, long names/amounts, empty/zero, missing fields, delayed/failed reads, recovery, and 200% zoom. Inspect text, controls, labels, tab/focus order, reduced motion, and overflow. Preserve secret-free console/request logs. Report browser limitations honestly; DOM-only tests are not visual acceptance.
- [ ] Run privacy/role regression: mocked capture boundaries on local switches; unauthorized tasks and API rejection; no cross-account late data; logout/device/permission teardown; online-only writes; uncertain cash retry across token refresh; exact journal evidence/post/reversal; one-time credentials; borrower/email stale-selection. Smoke-check Client/Employee/Collector after shared CSS/app changes.
- [ ] Verify new modules in build/PWA assets, coherent service-worker upgrades, and absence of fixtures/docs/secrets/protected-response cache. Retain production/offline protection.
- [ ] Commit/push only this branch; inspect existing exact-head CI. Required jobs remain **Backend, quality, and security**, **Portal, Flutter, and Android**, **Financial and disposable PostgreSQL**. No duplicate workflows or rerunning unchanged successful runs merely to generate receipts. Pending/Red is not Green; retain run IDs/SHA.
- [ ] Review final diff against spec and file scope. A reviewer checks correctness/privacy and browser review checks usability. Leave owner production/device acceptance unclaimed. Change PR description from planning-only to implementation candidate only when code exists; keep Draft/open/unmerged with automatic merge off.
- [ ] Synchronize PR, Notion Current State, and Create State with exact SHA, completed/pending tasks, commands/results, CI, screenshots, limitations, and next action. When a connector fails, retain an exact copyable checkpoint and disclose the failed sync. Stop before merge/mark-ready/deploy.

## Completion ledger

| Task | Status at handoff | Required evidence |
| --- | --- | --- |
| 0 Baseline | Pending Codex | Current refs, ownership, baseline checks |
| 1 Portfolio | Not implemented | Failure/recovery, global summary, races |
| 2 Local refresh | Not implemented | Draft node retention, save/read separation |
| 3 On-demand loading | Not implemented | Independent Today, session/Refresh safety |
| 4 Staff/mobile/focus | Not implemented | Readable 390/320 screenshots, focus |
| 5 Local tasks | Not implemented | Reachability, precise links, private boundaries |
| 6 List density | Not implemented | All records reachable, correct IDs/counts |
| 7 Visual polish | Not implemented | Screenshots, protected-flow regressions |
| 8 Integrated acceptance | Not run | Full checks, 18 samples, exact-head CI, handoff |

Update cells with evidence/commit links, not predictions. Green must identify exact PR head and required jobs. The owner may report Red or Green; verify the matching live GitHub result before continuing.

## Copyable Codex task

Implement the Management Web UI completion plan on this Draft PR's branch. Read this plan and its linked design, live main/open PRs, frozen Master #296, latest Notion checkpoint, and Create State before editing. Follow Tasks 0–8 in order with failing behavioral tests before each fix and focused passing checks afterward. Keep the six-group layout, financial/auth/privacy safeguards, and exact server values. Use this branch, not a duplicate PR; do not parallelize edits to shared Management/app/CSS files. Avoid over-engineering/new frameworks/endpoints. Preserve unrelated in-session drafts without new browser persistence or longer secret lifetimes. Prove error/recovery, delayed loading, mobile/focus, task-navigation/private boundaries, long-list, and all-role regressions using synthetic data. Update this checklist and GitHub/Notion/Create State after meaningful progress. Leave the PR Draft/open/unmerged. Do not mark ready, merge, deploy, run delivery/migrations, access production credentials, make real financial writes, or start screen capture. Finish with exact head, results, blocked/remaining acceptance, and next owner action.
