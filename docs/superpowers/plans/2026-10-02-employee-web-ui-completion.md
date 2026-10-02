# SPINA Employee Web UI Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development task-by-task. The owner selected Codex as executor. Use one integration owner for shared files; independent reviewers may run in parallel. Steps use checkbox syntax for tracking.

**Goal:** Complete the reviewed Employee Web actions, workday/pay navigation, draft safety, office continuity and payslip output without rebuilding payroll or broadening Employee authority.

**Architecture:** Retain the existing ES-module portal and Employee Operations command controller. Separate stable editors from refreshed records, expose mount-scoped refresh/view handles, reuse the shared shell lifecycle, and add only focused workday, office-case and payslip-print helpers. Preserve existing protected endpoints and exact server snapshots.

**Tech Stack:** Existing HTML/CSS/JavaScript, Node.js >=22, node:test and existing portal/PWA tooling. Current FastAPI/PostgreSQL contracts unchanged. Browser tests use synthetic data; printing uses the browser, not a new PDF package/service.

**Spec:** [Employee design and acceptance](../specs/2026-10-02-employee-web-ui-completion-design.md).

**Handoff state:** Documentation only. Main baseline `41a13eb59c9cc1b65a0a6a51f3b73db4a0895013` after #484; Management #485 and Collector #486 are separate workstreams. All implementation/runtime acceptance below is pending. The owner will start Codex on this PR's branch. No automatic invocation, merge, mark-ready, delivery, deployment, migration, production transaction/credential use, real capture or Master #296 acceptance change.

## Global constraints

- Preserve branding, existing permitted destinations, financial/payroll/attendance rules, exact server amounts/order/versions, actor/device scope and per-record allowed_actions. No new HR/lending engine, endpoint, grant, framework, global state/cache or browser persistence.
- Employee changes stay online-only on Web. Pending commands keep exact request_id/id/payload/expected_version; explicit check/retry is separate from ordinary refresh. An unconfirmed result is not rejected or successful. Never auto-replay a financial action.
- Preserve unrelated drafts, but not stale authority, passwords or one-time secrets. 401/403/logout/device/account/grant changes clear private state. Same-identity token renewal must not lose unresolved request identity.
- Preserve physical cash confirmation for acceptance, review/reason for rejection, custody evidence, first-loan document identity, independent payroll approvals, owner-only setup/payment/shortage controls, Cash Disbursement prepare-only and automatic_source_posting=false.
- Keep Employee Support's existing local updates. Do not copy the Management/Collector full-remount fix blindly into an already-local handler.
- Every shared-file change coordinates with live #485/#486; do not edit their branches/plans, import their unmerged role-specific helpers, overwrite WIP or introduce competing shell hooks. Other roles are regression surfaces.
- No real production data, wages, credentials or signed private URLs in fixtures/commits. No new capture-eligible region, test weakening, duplicate CI, v1.0 tag or owner acceptance claim.
- General borrower reports are an E9 contract/scope assessment with named follow-ups where needed, not implicit authorization to expose all borrowers. Payslip printing and existing first-loan downloads are bounded separately.

## Review focus

1. Mutation accepted but follow-up read fails; preserve the saved outcome and do not re-enable the same decision — Tasks 1–2.
2. Dirty editor vs changed record/version/permission, dynamic rows, midnight, and same-actor token renewal — Tasks 2–5.
3. Shared private workspace data must not mix employees, device-scoped request recovery, cash preparation or backup-role grants — Tasks 3–5.
4. Carried Office references and delayed responses must never expose an old borrower's data or reuse old release/print authority — Tasks 6–7.
5. Published/unpaid/stale payroll, long exact decimal text, print cancellation/logout, partial lists and 65 updates — Tasks 7–10.

## File map and interfaces

All asset basenames below are under `spina_portal/assets/`; all test basenames under `spina_portal/tests/`. New files are explicitly marked. Existing authoritative modules: `roles/employee.js`, `employee-operations.js`, `remittance-review.js`, `app.js`, `ui.js`, `app.css`, `presenters.js`, `cash-disbursement.js`, `office-onboarding.js`, `office-cif-selection.js`, `office-application-review.js`, `office-first-loan.js`. Update `spina_portal/sw.js` with new public modules in the same commit that imports them.

Planned focused helpers: **new** `employee-workday.js` (self-scoped summary/guidance), **new** `employee-office-case.js` (reference handoff/step navigation), **new** `employee-payslip-print.js` (one authorized snapshot's print projection/lifecycle). Do not split every control into a subsystem.

Read-only references: `gilbic_backend/src/gilbic_backend/remittance_api.py`, `remittance_review_repository.py`, `employee_operations_models.py`, `employee_operations_repository.py`; `docs/superpowers/specs/2026-09-20-employee-api-contract.md`; existing Office and document API implementations discovered by their current module paths. Never assume a payslip PDF or general Employee borrower-report endpoint exists.

Maintain existing `mountEmployeeOperations(...) -> dispose` return compatibility. Optional additions: `onController(handle)` and `onSnapshot(snapshot)` callbacks. The mount-owned handle is `{refresh(options?): Promise<void>, selectView(view): void, dispose(): void}`; view is `workday | tasks | timeoff | advances | payslips | other`; refresh options contain only `recover?: boolean`. Snapshot notifications occur only after the module's current identity/capability validation. No other module may treat the callback as an authorization grant.

The Employee role registers a shell handle with `{activate(sectionId): void, refreshVisible(): Promise<void>, dispose(): void}` through the single optional `registerWorkspaceHandle(handle)` contract. If #485/#486 already established an equivalent interface, record and use an adapter once, not a second registry. Registration belongs to the current mount AbortController; late handles are disposed. Keep the context's current session source synchronized across token renewal. Ordinary shell Refresh delegates to this handle; other roles retain their behavior until their own coordinated changes.

## Task 0 — Exact baseline and shared ownership

**Files:** Read this plan/spec, applicable AGENTS.md, `package.json`, `.github/workflows/spina-ci.yml`, current Employee tests and live #485/#486 diffs.

- [ ] Read live main and this PR head, open PRs, frozen #296, latest Notion checkpoint and Create State project `69a61c48-f842-44ac-aa11-e987ffec4a36`. Distinguish current implementation from old unavailable-API memories.
- [ ] Use this PR's existing branch in an isolated Codex worktree. Do not create a duplicate PR or discard another worker's changes. Record ownership/integration order for shared employee-operations/app/ui/CSS/PWA/Office files. Continue nonoverlapping tasks if a shared hunk is owned elsewhere.
- [ ] Confirm baseline checks once or reuse equivalent retained exact-head evidence. Validate each reviewed defect still exists. Existing upstream fixes need acceptance evidence, not reimplementation.
- [ ] Post execution SHA, baseline outcomes, shared ownership and next task. All later task completion is supported by exact commit/test evidence, not predictions.

## Task 1 — Remittance rejection, local retry and focus (E1)

**Files:** `remittance-review.js`, scoped `roles/employee.js`; **new** `employee-remittance-decisions.test.mjs`; existing `remittance-review.test.mjs`.

**Interfaces:** Extend mountRemittanceReview with optional `loadNotifications(): Promise<Notice[]>` and `onNoticesChanged(notices): void`, retaining cleanup return. Add exported pure `buildRemittanceRejection({record, actorId, reason, reviewed}) -> {path, options}` and `rejectedRemittanceMatches(result, record, actorId, reason) -> boolean`. The first requires verified submitted record/exact recipient, reviewed=true and trimmed 1–500 character reason; caller separately checks current permission and online/busy scope. Return method POST/body/financial:true, no new idempotency fields unsupported by the endpoint.

- [ ] Write tests `reject_requires_exact_recipient_permission_review_and_reason`, `reject_does_not_require_physical_receipt`, `accept_still_requires_both_checks`, `reject_uses_record_response_not_accept_notification_shape`, `accepted_rejection_then_read_failure_is_not_retryable_write`, `uncertain_outcome_locks_both_decisions`, `local_retry_and_focus_are_scoped`. Assert actual URL/body, one write on double click, wrong IDs/status/reason fail, late responses after Close/abort do not render, 401/403 remove private data.

```js
const action = buildRemittanceRejection({record, actorId, reason: ' Cash count differs ', reviewed: true});
assert.equal(action.path, `/api/v1/remittances/${record.remittance_id}/reject`);
assert.deepEqual(action.options.body, {review_acknowledged: true, reason: 'Cash count differs'});
assert.equal(action.options.financial, true);
assert.throws(() => buildRemittanceRejection({record, actorId, reason: ' ', reviewed: true}));
```

- [ ] Run `node --test spina_portal/tests/employee-remittance-decisions.test.mjs`; record a failure caused by missing behavior, not an invalid fixture.
- [ ] Add distinct Reject/reason UI with explicit confirmation naming the remittance and consequence; keep Accept/physical check unchanged. Use the real reject projection (IDs, status, reason, rejected_by_user_id/rejected_at), then reload notices. Separate saved outcome from failed notices refresh. Do not locally forge notification statuses. Implement local read retry and focus enter/return; retain generation, mutation lock and denial cleanup. Treat uncertain decisions as reconciliation, never automatic retry.
- [ ] Run the new and existing remittance suites. Browser-check accepted/rejected/read-only/wrong-recipient/failed-read states with mocked data. Verify reason and confirmation do not claim physical receipt.
- [ ] Commit `feat(web): complete protected Employee remittance decisions` with red/green evidence.

## Task 2 — Stable editors and draft-safe refresh (E2)

**Files:** `employee-operations.js`; **new** `employee-draft-refresh.test.mjs`; existing `employee-operations.test.mjs`, `employee-operations-contract.test.mjs`, `employee-payment-empty-state.test.mjs`.

**Interfaces:** Add optional onController/onSnapshot from the file map. Internally distinguish rendering record regions from private teardown; track `{action, employeeId, recordId, originalVersion}` for the editor and the independent immutable pending command. No generic page-wide form cache. The exported mount still returns its cleanup function for all current callers.

- [ ] Write `refresh_preserves_leave_editor_nodes`, `clock_in_preserves_unrelated_leave`, `advance_dynamic_rows_survive_read_refresh`, `own_editor_success_only_clears_that_editor`, `changed_version_blocks_retained_text`, `pending_payload_never_regenerates`, `same_scope_token_renewal_retains_pending`, `denied_or_changed_identity_clears_private_editor`. Assert node identity, reason/checkbox/row values, exact expected_version/request_id and no extra POST. Cover 422 vs 409, accepted action followed by failed GET, unmatched last_result, and Employee Support success preserving work.
- [ ] Run `node --test spina_portal/tests/employee-draft-refresh.test.mjs`; reproduce existing refresh/attendance reset failures.
- [ ] Keep editor DOM separate from routine record rendering. Only clear on its matching verified success, deliberate discard or security teardown. A changed record retains text visibly stale but cannot auto-adopt a version. Never clear an unrelated selected editor merely because attendance succeeded. Implement exact pending recovery across permitted same-scope refresh without introducing durable storage; scope invalidation stays fail-closed.
- [ ] Run the new suite and all three existing Employee suites. Check generic lock() combines availability policy with busy/offline/stale/pending instead of accidentally enabling a denied or stale control. Cancel editing must not clear an unresolved command. Dispose removes all listeners/data.
- [ ] Commit `fix(web): retain Employee drafts through safe refresh`.

## Task 3 — Independent tasks, safe header Refresh and no duplicate eager read (E3)

**Files:** `roles/employee.js`, coordinated `app.js`; optional `ui.js` adapter only; **new** `employee-lazy-loading.test.mjs`.

**Interfaces:** Internal `createEmployeeWorkspaceHandle(context) -> ShellHandle` uses the file-map interface, one mount-owned map of first-load promises/controllers and current permission predicates. No cross-role router/cache. Employee Operations onSnapshot feeds Today; its onController supplies view navigation and scoped refresh. Cash Disbursement retains its own current capability/recovery read on activation.

- [ ] Write `activity_delay_does_not_block_workday`, `remittance_or_support_failure_is_local`, `cash_not_mounted_on_startup`, `today_and_operations_share_one_validated_read`, `revisit_has_one_binding`, `header_refresh_preserves_dirty_editor`, `request_id_recovery_never_coalesces`, `old_handle_cannot_render_after_scope_change`. Assert first render/navigation before deferred secondary reads; exactly one initial plain Employee workspace request and no cash mounting until selected.
- [ ] Run `node --test spina_portal/tests/employee-lazy-loading.test.mjs`; confirm initial eager-blocking/duplicate patterns.
- [ ] Render stable section placeholders, mount workday source independently and defer secondary Office/remittance/Support/Updates/cash tasks. Read errors have local Retry. Use one coordinated optional shell handle registration; reject stale registration. Preserve sharing before/after hooks, current session, all cleanup and other roles. Header Refresh delegates to controllers; pending reconciliation is not silently converted to an ordinary reload.
- [ ] Run new suite, Employee integration suites and existing workspace/session/shell/privacy/PWA suites located during Task 0. Test token renewal, abort during lazy mount, role/grant changes and failed local retry. Do not remove cash's later recovery read to meet an artificial request-count target.
- [ ] Commit `perf(web): load Employee work independently of secondary queues`.

## Task 4 — Work/pay views, mobile records and clear self-cancellation (E4)

**Files:** `employee-operations.js`, `roles/employee.js`, scoped `app.css`; **new** `employee-work-pay-navigation.test.mjs`.

**Interfaces:** Add `presentation: 'default' | 'employee'` and `initialView` optional mount parameters. Defaults preserve other-role layout; Employee uses employee mode. Controller selectView uses the file-map enum. Record action lookup uses stable IDs, not filtered positions; preserve current recordAllowed/createAllowed enforcement.

- [ ] Write `all_authorized_collections_and_actions_remain_reachable`, `view_change_preserves_editor`, `attendance_filter_is_loaded_date_scope`, `payslips_shortcut_reuses_same_mount`, `self_cancel_has_no_approval_or_paid_minutes`, `repayment_cells_have_mobile_labels`, `reviewer_and_task_only_backup_keep_exact_visibility`. Pin six local views to the spec; 12 attendance days default to the current date without deleting other days. Test same-name staff and mixed self/other records.
- [ ] Run `node --test spina_portal/tests/employee-work-pay-navigation.test.mjs`; observe missing local-view/label behavior.
- [ ] Implement Workday/Tasks/Time off/Advances/Payslips/Other records and loaded date/range filter. Keep visible create actions for empty collections and remaining reviewer controls under granted Other records. Reuse the same Payslips panel for its direct navigation shortcut. Render repayment/installment data as labeled mobile cards without losing reference/amount/history. Rename only own permitted request cancellation to Cancel my request and omit irrelevant self-review fields; keep exact command semantics.
- [ ] Run focused suite plus existing Employee contract/empty-state and other-role tests. Inspect 1440/390/320 and 200% zoom for 12 days, long currency/references and expanded salary advances. Monetary digits must remain readable, not merely inside page bounds.
- [ ] Commit `feat(web): organize Employee work and pay into focused views`.

## Task 5 — Truthful Today and attendance guidance (E5)

**Files:** **new** `employee-workday.js`; `roles/employee.js`, `employee-operations.js`, `spina_portal/sw.js`; **new** `employee-workday-summary.test.mjs`.

**Interfaces:** `buildEmployeeWorkdaySummary({workspace, now}) -> {workDate, attendance, tasks, requests, payroll}`. Pure presentation, only a validated workspace. Each member carries availability/status and self-scoped record references; never salary arithmetic. `attendanceGuidance({events, employeeId, workDate}) -> {label, primaryActions, needsReview}` is a suggestion, not allowed_actions. Keep original event submission/sequence logic in Employee Operations.

- [ ] Write `summary_excludes_other_staff`, `missing_setup_is_not_zero_pay`, `no_event_is_no_record_not_absence`, `normal_chain_suggests_next_action`, `ambiguous_pending_or_cross_device_chain_needs_review`, `midnight_invalidates_yesterday_guidance`, `latest_payroll_uses_period_and_status_not_array_order`. Use now=`2026-10-02T00:00:00Z` (08:00 Manila); include yesterday/today events and a pending/conflicting event. Task/request counts must describe loaded self records, not all visible staff. Assert no summed payroll amount.
- [ ] Run `node --test spina_portal/tests/employee-workday-summary.test.mjs`; confirm missing summary behavior.
- [ ] Replace Connected functions with actor-specific workday/task/request/payslip information and links. Map clear normal event sequence to helpful primary actions while keeping contract-permitted alternate actions/correction available; never derive payroll or automatic attendance approval. Pending/conflicting chain shows Needs review. Preserve device UUID, sequence, captured_at and predecessor behavior. Date changes and stale data require current reads before guidance-driven actions.
- [ ] Run new suite and Employee Operations/contract tests including offline, pending retry, correction and role privacy. Verify global connection/busy unlock cannot enable a control that availability/grants disabled. Add the helper to the public/PWA module list in this commit.
- [ ] Commit `feat(web): show actionable Employee workday information`.

## Task 6 — Office-case handoff across existing steps (E6)

**Files:** **new** `employee-office-case.js`; `roles/employee.js`; minimal optional adapters to current Office modules only if their established input invalidation is insufficient; `spina_portal/sw.js`; **new** `employee-office-case-continuity.test.mjs`.

**Interfaces:** `bindEmployeeOfficeCase({root, navigate, signal}) -> {activate(step): void, dispose(): void}`; step `intake | cif | application | first-loan`. Use existing input names: intake/CIF applicationReference is the intake reference; application/first-loan intakeReference and applicationReference are separate fields. Parent maintains only these references and their relationship, not a second borrower/loan record.

- [ ] Write `next_step_prefills_empty_reference`, `nonempty_conflicting_case_requires_explicit_switch`, `changing_intake_invalidates_linked_application`, `reference_prefill_triggers_existing_invalidation`, `old_read_cannot_reveal_previous_client`, `no_continuation_auto_approves_or_releases`. Use intake `INTAKE-A` and loan application `APP-A`; switch to `INTAKE-B` while A's delayed request is unresolved. Assert no A PII/doc URL or mutation appears and unrelated leave/cash drafts survive case navigation.
- [ ] Run `node --test spina_portal/tests/employee-office-case-continuity.test.mjs`; confirm present reference-copy gap.
- [ ] Add repeated case strip/Next/Back using stable Employee Office IDs. Prefill only empty values and trigger input/change invalidation; target performs its protected reads. A confirmed switch clears dependent loaded state before assigning new references. Preserve existing document hashes/URLs cleanup, permissions, final approval and release/signature/evidence checks. No helper may bypass a module's validator.
- [ ] Run new suite and existing Office CIF/application/first-loan/identity/download suites discovered in Task 0. Verify Management Office usage remains unchanged and missing grants deny both navigation and API actions. Include the new module in PWA assets.
- [ ] Commit `feat(web): carry Employee office cases between verified steps`.

## Task 7 — Private, exact-snapshot payslip printing (E7)

**Files:** **new** `employee-payslip-print.js`; `employee-operations.js`, `roles/employee.js`, scoped `app.css`, `spina_portal/sw.js`; **new** `employee-payslip-print.test.mjs`.

**Interfaces:** `buildPayslipPrintMarkup({record, employeeName}) -> string` projects a validated authorized payroll record without recomputation. `mountEmployeePayslipPrint({root, getCurrentScope, loadWorkspace, signal, print = () => globalThis.print()}) -> {open(recordId, expectedVersion): Promise<void>, close(): void, dispose(): void}`. loadWorkspace performs a fresh protected read; do not treat current DOM/record ID as authority. open verifies scope, selected record membership/employee/version/published status and fields before creating the print region.

- [ ] Write `only_current_authorized_record_prints`, `version_change_requires_review`, `draft_stale_or_missing_fields_cannot_print`, `unpaid_approved_is_not_payment_receipt`, `exact_components_not_recomputed`, `print_contains_no_other_employee_or_credentials`, `cancel_afterprint_logout_clear_region`. Use gross `12500.00`, deductions `500.00`, net `12000.00`, paid `4000.00`, due `8000.00` and deduction component `-500.00`; assert their exact server strings/formatted equivalents, not calculated replacements. Reject wrong employee, offline/failed revalidation, missing status/amount, or blocking issues; include unknown component labels escaped as text.
- [ ] Run `node --test spina_portal/tests/employee-payslip-print.test.mjs`; confirm missing output behavior.
- [ ] Add Print payslip for eligible approved/partially_paid/paid records. Revalidate ID/version; on change return to review. Print one same-page isolated region with employee, period/type/status, ID/version, exact components/totals and Payroll record copy — not proof of payment. Preserve unpaid/due distinction. Use browser Print with optional browser Save as PDF; no imaginary PDF endpoint/library, signature or locally calculated pay. Exclude all other content in print CSS and remove temporary DOM/listeners on every close/security transition. Use existing privacy teardown before showing print content, without adding capture eligibility.
- [ ] Run focused/Employee/privacy tests. Inspect synthetic print preview at A4 and Letter using browser tooling, including long component labels and multi-page output. Do not print paper, use production payroll, or describe this as a signed backend PDF. Verify afterprint/cancel cleanup and normal UI restoration; the user controls any actual saved copy.
- [ ] Commit `feat(web): add private printable Employee payslip copies`.

## Task 8 — Complete Updates and remaining presentation polish (E8)

**Files:** `roles/employee.js`, bounded `employee-operations.js` labels and `app.css`; **new** `employee-updates-presentation.test.mjs`.

**Interfaces:** Keep activityRows and its backing authorized array; a scoped binder tracks displayLimit initially 50, increment 50. Do not copy notification data into a new global store or fabricate unread counts.

- [ ] Write `updates_65_show_50_then_all`, `today_count_is_loaded_not_unread`, `empty_error_and_denied_are_distinct`, `self_cancellation_copy_matches_actual_action`, `setup_warning_keeps_exact_diagnostics`. Assert item IDs/order remain unchanged, duplicate-looking events retained, count not silently truncated, and no additional endpoint invented.
- [ ] Run `node --test spina_portal/tests/employee-updates-presentation.test.mjs`; confirm silent 50-item cap/current copy failures.
- [ ] Add Showing X of Y loaded updates and Show more; retain server order, record identity and all returned items. Align labels and form hierarchy; keep setup details, read-only/denied messages and financial warnings. Make cash purpose/evidence widths consistent with the coordinated shared work, without duplicating #485's changes or modifying cash submission/recovery. Keep Account profile/device/password distinct.
- [ ] Run focused plus Employee/role-local-update/credential/cash safety tests. Inspect empty/65-update/long-text screens and all-role CSS smoke cases.
- [ ] Commit `style(web): clarify Employee updates and work controls`.

## Task 9 — Explicit reports/output permission matrix (E9)

**Files:** Append a verified matrix to this plan under Reports disposition; read existing report/document APIs, desktop report commands and grants. No new output endpoint or role grant is authorized by this task.

- [ ] Trace each requested output: own payroll (Task 7), locked first-loan packet (existing workflow), borrower statement, receipt search and collection/office report. Record exact source file/endpoint, response/output, current allowed actor/object scope, existing UI link, and remaining dependency. Repository-wide absence must be based on inspected routes/searches, not a guessed filename.
- [ ] Classify each as implemented here, already available, authorized existing link, or deferred pending specific scope/contract approval. Do not substitute Client-owned routes or Management role for ordinary Employee authority. Identify which borrowers/areas/documents are allowed before any new borrower-report surface.
- [ ] For an already-authorized existing output, add only a safe link to its existing workflow when needed; test exact permission/object guard. Otherwise record the smallest named follow-up and unresolved decision rather than building an unapproved report engine/hub. Keep this task's assessment distinct from delivery of a deferred feature.
- [ ] Review the matrix against current grants and E9 boundaries; record evidence. Commit `docs: map Employee reporting outputs and remaining scope gates`. Safe Tasks 1–8 can complete even when broader reporting awaits authorization.

## Task 10 — Integrated verification, public output and handoff (E10)

**Files:** Changed portal tests, fixture/helper only if necessary under `spina_portal/tests/fixtures/`; current build/module check tooling and `.github/workflows/spina-ci.yml` read/run, not weakened; this plan and PR checklist.

- [ ] Reconcile E1–E10 against actual implementation/evidence. Verify existing functions were retained, including Support local updates, all Employee Operations actions/history, role-limited Office workflows and cash preparation. Keep deferred report work explicitly deferred.
- [ ] Run the full portal suite once at final integration, then build without repeating tests. Public-output verification is the current inline CI step, not an assumed new script. Re-read package.json/CI if upstream changed:

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

Do not follow this with npm run build on the unchanged head because it repeats tests. Inspect public assets/PWA membership and coherent upgrade behavior separately; static patterns alone are not security acceptance.

- [ ] Run actual browser checks with synthetic APIs and blocked unexpected external/mutating requests. Capture E10's 33 core layouts at 1440/390/320 plus Area Management, changed work/pay views, remittance reject, payslip print preview, 65 Updates, self-only/reviewer/backup-limited and missing-setup cases. Exercise 200% zoom, keyboard/focus, reduced motion, long amounts/references, request races, stale versions, failed post-save read, offline and scope teardown. Report unavailable browser tooling honestly; DOM assertions alone are not visual acceptance.
- [ ] Prove protected behavior: remittance accept/reject identity/result/uncertainty; Employee exact request replay and stale version; attendance immutable chronology; payroll snapshot without local totals; denied print/no mixed staff data; Office pair/identity/hash invalidation; cash recovery; same-user token rotation vs other-device/user/grant cleanup; no new screen-capture eligibility. Smoke-check Management/Collector/Client on the actual combined shared-file integration head.
- [ ] Push only this branch and inspect existing exact-head CI: Backend, quality, and security; Portal, Flutter, and Android; Financial and disposable PostgreSQL. Preserve all jobs and checks. No unnecessary unchanged reruns; pending or failed checks are not Green. A docs-only Green never proves Employee implementation acceptance.
- [ ] Review final diff against scope/requirements with independent correctness/privacy review where available and actual browser inspection. Update PR body from planning-only only when code exists; keep Draft/open/unmerged and automatic merge off. Do not mark ready, merge, deploy, run delivery/migrations or claim owner production/mobile/physical-handover acceptance.
- [ ] Synchronize GitHub, latest Notion Current State and Create State after meaningful checkpoints with exact branch/head, task ledger, commands/results, CI IDs, screenshots, shared integration status, E9 decisions, limitations and next action. Report failed connectors and preserve a copyable checkpoint instead of claiming synchronization.

## Completion ledger

| Task | Planning state | Required proof |
| --- | --- | --- |
| 0 Baseline and ownership | Complete, coordinated by root | Existing isolated branch from `962ecec9`; root verified main `41a13eb5`, frozen #296 and external checkpoints; shared shell imported as `48fe109d` / `36c5bcaa` |
| 1 Remittance decisions | Implemented | `adeeaf01`, `bf329d30`, `ebc9cb4a`: separate accept/reject response validation, full evidence, own recipient, view-only history, read retry, shared uncertainty lock and focus |
| 2 Draft-safe records | Implemented | `55b22b6a`: actual editor nodes retained across reads and unrelated attendance; captured command/version preserved; changed authority erases data |
| 3 Independent loading | Implemented | `55b22b6a`, `65323c04`: one initial work read, lazy secondary tasks, one optional shell handle, local read refresh, stale live scope teardown |
| 4 Work/pay/mobile | Implemented | `55b22b6a`, `3d31fbb0`: six views, correct create-action partition, loaded attendance filtering, same Payslips mount, labeled repayment cards and own cancellation |
| 5 Today/guidance | Implemented | `55b22b6a`: self-scoped Today, Manila date, conservative event-chain guidance and latest published payroll; no local payroll arithmetic |
| 6 Office continuity | Implemented | `55b22b6a`: typed intake/application relationship, empty-only prefill, explicit conflicting-case switch, existing invalidation and validators |
| 7 Payslip output | Implemented | `55b22b6a`, `65323c04`: fresh own ID/version/status validation, exact snapshot, private temporary print region; A4/Letter browser-generated output each four pages |
| 8 Updates/polish | Implemented | `55b22b6a`: 50 then all 65 loaded Updates in server order, no invented unread count; distinct Account sections and preserved Support drafts |
| 9 Reports assessment | Complete; broader delivery deferred | Verified matrix below; no new general borrower/report authority or endpoint |
| 10 Integration/handoff | Local verification complete; root integration pending | Runtime `65323c04`: 176-module syntax check; 1,047/1,047 portal tests; build/public-output checks; 39 synthetic browser layouts. Root owns combined-head review, exact-head CI, push and external synchronization |

### Execution evidence and limits — 2026-10-02

The execution used equivalent behavioral test names grouped into `employee-remittance-decisions`, `employee-draft-refresh`, `employee-lazy-loading`, `employee-work-pay-navigation`, `employee-workday-summary`, `employee-office-case-continuity` and `employee-payslip-print` suites. Updates coverage is in the lazy-loading suite. The task bullets above retain the original proposed commands/commit boundaries as a planning reference; this ledger records the actual execution and pending integration steps.

Meaningful failing behavior preceded the product changes: receiver rejection/result/history validation, refresh node loss, eager secondary loading, missing local views/Today/Office continuity/print, stale live identity retaining a mounted editor, and incorrect Workday/Time off create placement. Focused suites passed after the fixes. The broad first run exposed inherited tests that assumed eager Employee mounting; fixture adaptations now activate the permitted section through the actual workspace handle/navigation and preserve the original request, authority, cleanup and exact payload assertions.

At runtime `65323c04`, `npm run check:portal` passed for 176 modules, `npm run test:portal` passed all 1,047 tests with no skips or failures, and `node tools/build_portal.mjs` passed. Public `index.html`, `assets/app.js` and `manifest.webmanifest` exist; there is no public tests directory or forbidden backend secret pattern; `git diff --check` passed. New PWA membership is limited to `employee-workspace.js`, `employee-workspace-content.js`, `employee-workday.js`, `employee-office-case.js` and `employee-payslip-print.js`; the shared cache version is left for root integration.

Synthetic browser evidence covers the 33 core layouts plus Payslips and Area Management at 1440/390/320 (39 total), all six work/pay views, expanded long exact repayment amounts, draft node retention through refresh/local navigation/attendance/Support save, 65 Updates, rejection without falsely acknowledging physical receipt, read-only rejected history, distinct intake/application references, 200% zoom/reduced motion and changed-identity teardown. No page errors or horizontal overflow occurred. Visual inspection found inherited sticky print headings overlapping long component labels; scoped print CSS fixes that defect. Browser-generated A4 and Letter PDFs each contain four pages, all exact server amounts/components, and none of the other staff/Support/credential/draft content. These are browser output checks, not physical paper, a native print-dialog/Save-as-PDF acceptance test or a signed backend payslip document.

Evidence is retained in `../checkpoints/current-prs-20261002/employee-report.md`, `employee-portal-tests-final.txt`, `employee-focused-tests.txt`, `employee-module-check.txt`, `employee-browser-check.mjs` and `employee-browser/`. The browser exercised representative authorized self-workflow data; reviewer/task-only backup/missing-setup, offline/uncertain/stale-version/race/failed-post-save-read cases have focused DOM/contract tests, not a separate visual claim for every state. Combined Management/Collector/Client code, remote CI and owner production/mobile/physical acceptance remain root-owned pending work. No production requests, real uploads/cash, actual capture, dependency upgrades, backend/grant expansion, persistence, push, merge, deployment or Master acceptance changes were performed.

## Reports disposition

This assessment does not grant general borrower reporting. The following mappings were verified against executable routes, repositories and current Web links. Own payslip Print is implemented; already available Office output is retained. No placeholder report button or substituted Client identity was added.

| Output | Verified source and contract | Current authority/object scope and existing UI | Disposition / smallest remaining decision |
| --- | --- | --- | --- |
| Own payroll copy | `employee_operations_api.py` GET `/api/v1/employee-operations/workspace`; repository capabilities/per-record actions and published payroll snapshot. `employee-payslip-print.js` re-reads before using one exact ID/version/components/gross/deductions/net/paid/due snapshot. | Current actor/device, linked employee, own payroll membership, approved/partially-paid/paid status, no blocking issues; print invalidates if refreshed authority or selected version changes. Employee Work/Payslips uses the same mount. | Implemented here as browser Print of a payroll record copy, explicitly not proof of payment. No new PDF endpoint or local payroll calculation. |
| Locked first-loan packet | `first_loan_document_api.py` GET `/api/v1/management/first-loans/{loan_id}/documents`; `first_loan_repository.py:packet_document` verifies the approved stored packet/document and exact content hash/length. Current pricing is separately revalidated for execution; the historical locked-PDF read does not claim that execution check. | Active Management or Employee and registered active device with `client_onboarding.requirement.review`; repository revalidates exact loan/document. `office-first-loan.js` already exposes guarded Download locked PDF packet. Generation POST is separately Management-only with `lending.first_loan.approve`. | Already available and retained in the existing Office workflow; no additional report hub/link/grant needed. |
| Borrower statement | `client_payment_api.py` GET `/api/v1/client/statement` returns own server statement; `client_document_api.py` GET `/api/v1/client/statement/document` renders its own record copy. The Client repository resolves the authenticated Client's linked borrower. | Active Client and registered device; Client-own portfolio, no employee-substituted borrower ID. Existing `client-statement.js` and native `client_statement_repository.dart` consume this contract. | Deferred Employee delivery. Owner must define eligible borrowers/areas and a bounded Employee read/output contract, grant, period and fields; Client impersonation is not a reuse path. |
| Receipt search | `collection_void_api.py` GET `/api/v1/management/collections/by-receipt/{receipt_number}` returns one candidate with exact transaction/client/loan/collector/date/entry/amount/coverage/balances/locked/voided facts. | Active registered actor with `collection.void.unremitted`; existing `management-collection-actions.js` and native `collection_void_repository.dart` use this correction workflow. Its authority also enables a separate protected financial void command. | Deferred ordinary Employee report access. Decide receipt/borrower/area scope and a read-only grant/contract without granting void authority solely to search receipts. |
| Collection/past-due reporting | `past_due_reporting_api.py` GET `/api/v1/management/past-due/reasons`, bounded dates/client/collector/area/reason/event limit; authoritative rows/totals. `management-past-due-report.js` is the existing Web read-only report. | Active registered actor with `management.dashboard.view`; existing Management surface. Employee Area Management retains only its already permitted area workflows. | Deferred broader Employee reporting. Decide authorized areas/borrowers/duties, period, fields and whether an approved scoped report contract can reuse this read. No role/grant expansion here. |
| Financial/office report totals | `financial_statements_api.py` GET `/api/v1/management/financial-accounting/statements`; server posted-General-Ledger statements, consumed by `management-financial-statements.js`. | Active registered actor with Management role and `accounting.view`; Management reporting. Office case modules keep their separately authorized review/locked-document outputs. | Deferred general Employee statements/reporting. Decide object/organization visibility and explicit accounting/report read permission; do not compute a substitute report in Employee JavaScript. |

Desktop trace: the current executable Windows delivery is `spina_pc/README.md`, `install_spina_pc.ps1` and its portal-URL test: secure Edge/Chrome app mode using the same portal/backend. It has no separate report-command engine. Repository-wide file searches found legacy documentation (`docs/reports-modularization-wave-80.md`, `docs/reports-pdf-error-visibility.md`) referring to removed `spina_app` and `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py`; those paths are absent in this checkout and were not recreated or treated as current authority. Current Web/native routes above are the grounded output map. This is E9 assessment completion; the deferred report features are not delivered.

## Copyable Codex task

Implement the Employee Web UI completion plan on this Draft PR's existing branch. Read this plan, its linked design, live main/open PRs, frozen Master #296, latest Notion checkpoint and Create State before editing. Complete Tasks 0–10 in order with failing behavioral tests before fixes, focused passing checks and reviewable commits. Coordinate shared employee-operations/app/ui/CSS/Office/PWA changes with Management #485 and Collector #486; do not overwrite their work or create a duplicate PR/router. Preserve server-authoritative amounts, capabilities/allowed_actions, exact request recovery, independent approvals, offline restrictions, cash custody and private-screen boundaries. Keep drafts without stale authority; print only one current authorized payslip without local payroll arithmetic or a fake PDF endpoint. Treat general reports as the explicit scope/permission assessment, not broad Employee access. Update the checklist and GitHub/Notion/Create State after meaningful progress. Keep this PR Draft/open/unmerged; no mark-ready, merge, deploy/delivery/migrations, production credentials or financial transactions, actual capture or Master acceptance changes. Finish with exact head, results, visual evidence, reports disposition, blocked/unverified items and next owner action.
