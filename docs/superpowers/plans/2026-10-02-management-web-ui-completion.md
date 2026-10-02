# SPINA Management Web UI Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development task-by-task. The owner selected Codex. Keep one integration owner for shared Management/app/CSS/helper edits; independent reviews may run separately. Track steps with checkboxes.

**Goal:** Complete all original Management UI findings and the functional re-review without redesigning SPINA or changing protected financial rules.

**Architecture:** Repair the current ES modules. Keep mount-local portfolio/task controllers, connect the existing renewal terms/continuation APIs, reuse the shared recipient remittance component, and refresh affected regions without destroying unrelated drafts. No new framework, router, financial engine or backend endpoint.

**Tech Stack:** Existing ES modules, HTML/CSS, Node.js >=22, built-in node:test, current portal/PWA tooling and unchanged FastAPI/PostgreSQL contracts. Browser evidence uses synthetic data and available tooling, not new product dependencies.

**Spec:** [2026-10-02-management-web-ui-completion-design.md](../specs/2026-10-02-management-web-ui-completion-design.md), revision 2.

**State:** Planning-only update to existing Draft PR #485, branch `plan/management-web-ui-completion-20261002`. Prior planning head `7fdf54edad8186bd0dca6d7209aeac68dbce48e1`; reviewed main `41a13eb59c9cc1b65a0a6a51f3b73db4a0895013`. The owner asked to include everything from the re-review. No product fixes or runtime acceptance are implemented by this documentation update; the owner starts Codex separately.

**Execution order:** **0, 1, 1A, 1B, 1C, 2, 3, 4, 5, 5A, 6, 7, 7A, 7B, 7C, 7D, 8.** Original Tasks 0–8 remain; inserted stages are required before final verification. Inspect current upstream implementations before following a superseded interface literally.

## Global constraints

- Preserve Today / Clients & loans / Collections / Accounting / People & operations / Account, IDs, role precedence and pink/white identity. Reuse existing Office, employee, accounting, proof and credential workflows.
- No new framework/router/global store/persistence layer/virtual-list system, endpoint/schema/grant, financial calculation or speculative feature. Amounts/order/query/body semantics remain server-authoritative; never total partial cards.
- Financial writes stay online-only with duplicate/uncertainty, exact supported request identity, conflict/version, evidence and confirmation safeguards. Do not fabricate request UUID/digest/version fields or automatically repeat an ambiguous mutation.
- Retain safe draft/File nodes only within the current mount; no new browser/PWA/URL persistence. Text retention does not retain authority or extend secret lifetime. Auth/role/device/identity changes clear private data; token refresh must preserve established same-identity uncertain recovery.
- Cash Disbursement prepares an expense draft, not payment. Employee remains prepare-only; Management posting is separate; automatic_source_posting=false stays unchanged.
- Preserve borrower/email stale selection, one-time credentials, password-reset boundaries, journal deduplication/immutable posting/reversal, recipient-only custody and borrower-only signature/cash confirmation.
- Keep existing private-screen boundaries. No new capture-eligible detail/photo screens. Simulate sharing lifecycle; do not capture real screens.
- Coordinate shared app/ui/CSS/PWA/proof/remittance/Office/employee helpers with #486/#487/#488. Reuse one verified optional shell hook and shared receiver; no competing systems or overwritten WIP.
- No production credentials/uploads/financial probes, real approvals/cash/signatures, migrations, deployment/delivery, dependency upgrades, CI weakening, Master #296 edits, mark-ready or merge. Some GETs have financial side effects; tests are synthetic/disposable.
- End each product stage with failing-then-passing behavioral proof, review and a small commit. Do not push deliberately failing tests or repeat unchanged full CI merely for activity. Keep all unverified items explicit.

## Review focus

1. A resolved-but-malformed renewal/remittance response may represent an unknown committed result; preserve uncertainty rather than report success or create a new action — Tasks 1A–1C, 2.
2. Photo approval may activate immediately or save the review but remain CIF-blocked; confirmations/status must match actual endpoint effects — Task 1B.
3. Changing borrower/recipient/period/page during slow reads, while retaining drafts or token rotation, must not reuse old authority or mixed snapshots — Tasks 2–3, 5A, 7A.
4. Local navigation inside one top-level group can replace private content while capture is preparing; stop/invalidate before replacement and reject stale mounts — Tasks 3–5.
5. Duplicate-looking records, unknown enum values, limited queries and failed readback must remain truthful/reachable without inferred totals, history or permissions — Tasks 5A–7D.

## File map and shared interfaces

All asset basenames below refer to `spina_portal/assets/`; all test basenames to `spina_portal/tests/`. Applicable AGENTS.md and live files take precedence over stale line numbers.

Planned focused modules:
- `management-portfolio.js`: move portfolio helpers; own truthful state, paged search and loan detail.
- `management-workspace-tasks.js`: small Management-only activation/cleanup controller, not a generic application framework.
- `management-renewal-workflow.js`: authoritative renewal queue, terms and continuation presentation/commands. Do not duplicate Client/Collector signing or handover controls.

Existing bounded edits: `roles/management.js`, `app.js`, `ui.js` only as needed, `management-devices.js`, `management-alerts-audit.js`, `management-financial-statements.js`, `remittance-review.js`, `payment-proofs.js`, `cash-disbursement.js` (markup only), `app.css`, narrowly `presenters.js`; `spina_portal/sw.js` for each new public module in the same commit. Keep `employee-operations.js`, Office workflows, collection/journal/accounting/credential protected modules intact except agreed integration hooks. A narrow `screen-sharing.js` hidden-child visibility correction requires direct tests, not broader eligibility.

Read-only backend references under `gilbic_backend/src/gilbic_backend/`: `renewal_api.py`, `renewal_repository.py`, `renewal_workflow_api.py`, `renewal_workflow_query_api.py`, `remittance_api.py`, `notification_api.py` if present (verify exact current notification handler path), `management_loan_api.py`, `management_loan_repository.py`, `financial_accounting_api.py`, `financial_statements_api.py`, `activity_notification_api.py`, `support_api.py`, `support_repository.py`, and proof/document contracts. No backend changes are implied by reading them.

Planned interfaces; update callers/tests together if equivalent verified upstream interfaces exist:
- `mountManagementPortfolio({root, api, signal, initialResult, getSession}) -> {refresh(): Promise<void>, dispose(): void}`. Optional initialResult keeps existing `{data,error}` shape. Task5A extends handle with `loadPage(offset): Promise<void>` and `openLoan(loanId): boolean`.
- `mountManagementRenewalWorkflow({root, api, getSession, signal, onSaved}) -> {refresh(): Promise<void>, openRequest(requestId): Promise<boolean>, isWritePending(): boolean, dispose(): void}`. Starts/render-loads on explicit refresh; Task3 controls first activation. onSaved is optional and never means full remount.
- `managementRenewalResultMatches(command, result) -> boolean`, command `{action, requestId, clientId, loanId, expected}`; action `terms | release-to-collector | proof-review | activate`, expected contains only actually submitted/action-specific fields. It verifies unwrapped results, not HTTP status alone.
- Extend existing `mountRemittanceReview(options) -> cleanup` compatibly using optional `getSession`, `onSaved`, `emptyMessage`, `registerHandle`; handle `{refresh(): Promise<void>, openRemittance(id): Promise<boolean>, isWritePending(): boolean}`. Preserve old Employee defaults and coordinate #487. Do not change cleanup-function return into an incompatible object.
- Internal `refreshManagementRegion(context, region) -> Promise<void>`, region `support | renewals | remittances | staff | overview | updates`; optional registrants for new modules, no global store. No mutation retry inside a refresh.
- `createManagementTaskController({root, signal, getSession, tasks, beforeTaskChange, afterTaskChange}) -> {activate(groupId, taskId?), refreshVisible(): Promise<void>, dispose(): void}`. Task records own current permission predicate, first-load/refresh/cleanup. Shell registration rejects stale mount handles. Other roles retain their established behavior.

## Task 0 — Reconcile baseline, evidence and ownership

**Files:** Read both revised documents, applicable AGENTS.md, current package/CI, original review and addendum `5943820685`.

- [ ] Fetch live main, #485 head/open PRs, frozen #296, latest Notion and Create State project `69a61c48-f842-44ac-aa11-e987ffec4a36`; compare implementation versus planning status.
- [ ] Use this PR's existing branch in an isolated worktree with a clean starting tree. Do not reset others' work, duplicate the PR or silently stack another planning branch.
- [ ] Inspect #486/#487/#488 diffs and record shared-file owner/order. In particular reconcile remittance-review with #487, proof retry with #488, and shell hook reuse across all roles.
- [ ] Verify endpoint handlers, payloads, current permissions and named test paths. Preserve valid upstream fixes and retain exact evidence rather than reimplementing them. Run baseline checks once only when equivalent exact-head evidence is absent; distinguish inherited failures.
- [ ] Record SHA, pending scope and limitations in #485. Product and owner acceptance remain unchecked.

## Task 1 — Truthful portfolio states and recovery (R1, retained)

**Files:** Create `management-portfolio.js`; edit `roles/management.js`, `sw.js`; new `management-portfolio-state.test.mjs`.
**Interfaces:** Implement portfolio handle and `managementPortfolioSummaryMarkup({status,summary}) -> string`, status loading/ready/error.

- [ ] Write `initial_failure_is_unavailable`, `search_recovery_updates_summary_and_rows`, `explicit_zero_is_valid`, `missing_fields_are_not_zero`, `filtered_rows_keep_global_summary`, `older_or_aborted_search_cannot_commit`. Fixture global summary:6 clients/10 loans/`12345.67` outstanding/1 overdue, independent of returned-card count; zero is separately explicit.

```js
assert.doesNotMatch(managementPortfolioSummaryMarkup({status:'error',summary:{}}), /₱0\.00/);
assert.match(managementPortfolioSummaryMarkup({status:'error',summary:{}}), /Portfolio summary unavailable/);
// Successful filtered recovery must show the returned 12345.67 summary, not sum the cards.
```

- [ ] Run `node --test spina_portal/tests/management-portfolio-state.test.mjs`; confirm expected behavior failures, not harness mistakes.
- [ ] Move existing helpers without copying them; implement dashes/loading/error/retry, exact field-presence validation, same-response summary/results update, preserved query/status, and last-request/abort guards. Keep Active portfolio · all clients separate from Search results. No new endpoint or financial sum.
- [ ] Run new tests plus `management-client-loan-grouping.test.mjs`, `presenters.test.mjs`, `business-formatting.test.mjs`, affected PWA checks; inspect recovery in browser.
- [ ] Review/commit `fix(web): keep portfolio summary truthful through recovery`.

## Task 1A — Correct renewal terms/review flow (R8, new)

**Files:** Create `management-renewal-workflow.js`; edit `roles/management.js`, `sw.js`; new `management-renewal-workflow.test.mjs`.
**Interfaces:** Implement renewal handle and result matcher above for terms. Read current richer queue/terms/legacy contracts first.

- [ ] Write `approval_never_calls_legacy_review`, `rich_queue_exposes_recommendation_terms_signers`, `missing_recommendation_blocks_decision`, `nonrecommendation_requires_override`, `rejection_requires_reason`, `office_processing_never_fakes_signatures`, `wrong_or_empty_result_is_not_success`, and `changed_request_requires_new_review`.
- [ ] Pin requested `12000.00`, approved `10000.00`, two same-name borrower fixtures with distinct IDs, and realistic signer/office-only alternatives. Assert POST path ends `/terms`, exact principal string and selected signer identities; no automatic true verification flags. Assert `managementRenewalResultMatches(command,{}) === false`; wrong request/loan/status is false; one correctly confirmed result triggers one local onSaved and no duplicate POST.
- [ ] Run `node --test spina_portal/tests/management-renewal-workflow.test.mjs`; reproduce the current legacy route before fixing it.
- [ ] Load `/api/v1/management/renewal-workflow?status=pending|approved|rejected`; preserve the limit200 boundary. Replace old approval form/handler with exact terms fields and current permission/readiness checks. Bind distinct request IDs, revalidate before confirmation, and validate same-record/action results. Preserve valid legacy rejection behavior by using the supported terms rejection rather than restoring legacy approvals. Unknown outcome locks this workflow for read reconciliation; no fresh command/automatic retry or full workspace remount.
- [ ] Run new suite, relevant role/navigation/local-update tests and backend renewal API tests in their established nonproduction environment. Test permission denial, double click, input change during read,500/timeout, and successful write followed by failed refresh. No source/backend guard is weakened.
- [ ] Commit `fix(web): connect Management renewal terms workflow`.

## Task 1B — Renewal continuation and private handover evidence (R8, new)

**Files:** Extend `management-renewal-workflow.js`; narrow API response-metadata support only if needed and reviewed; new `management-renewal-progression.test.mjs`.
**Interfaces:** Extend the same handle/result matcher; use existing release/proof-review/activate paths. No second renewal state engine.

- [ ] Write `release_uses_authoritative_execution_and_locked_money`, `missing_readiness_never_enables_release`, `client_sign_and_cash_confirm_are_not_management_actions`, `photo_is_private_current_and_disposed`, `proof_review_can_activate_without_second_post`, `saved_proof_review_can_remain_cif_blocked`, `stale_photo_or_terms_invalidates_confirmation`, and `ambiguous_continuation_stays_locked`.
- [ ] Pin locked offset `1500.00`, net `8500.00` without subtraction. Cover result branches proof approved + active, proof approved + ready_for_activation=false/message, and explicit later activate. Assert no automatic second `/activate`, no Client/Collector POSTs and no successful status from `{}`.
- [ ] Run `node --test spina_portal/tests/management-renewal-progression.test.mjs` to establish missing controls/behavior.
- [ ] Add explicit guarded actions at `/api/v1/management/renewals/{id}/release-to-collector`, `/proof-review`, `/activate`; display actual recommendation, borrower/signers/office-only, custody and activation blockers. View image through `/api/v1/renewals/{id}/handover-photo`, validating supported nonempty image type and current identity; use current version/hash metadata where accessible and revoke private object URLs on switch/denial/cleanup. Never bypass missing authoritative execution or calculate release amounts.
- [ ] Disclose proof approval's possible activation in confirmation; render actual returned activation or saved-review/CIF-blocked state. Latest-photo endpoint and review request do not guarantee an expected-version compare: inspect current contracts, revalidate available evidence, and record unresolvable concurrency limits under R14 without inventing request fields or claiming atomic pinning. Pending writes cannot be forgotten through navigation/Refresh.
- [ ] Run new suite plus Task1A and established renewal/CIF conflict/privacy/role tests; browser-check terms, locked/unlocked amounts, missing photo, office-only, declined and blocked activation with synthetic fixtures.
- [ ] Commit `feat(web): complete protected Management renewal progression`.

## Task 1C — Actual recipient remittance workspace (R9, new)

**Files:** Edit `roles/management.js`, shared `remittance-review.js` only through #487 coordination, `management-alerts-audit.js`; new `management-remittance-workspace.test.mjs`; retain existing remittance tests.
**Interfaces:** Reuse/compatibly extend mountRemittanceReview and optional handle registration. No replacement custody workflow.

- [ ] Write `management_receiver_mounts_actual_review`, `view_only_has_history_without_decisions`, `wrong_recipient_or_sender_cannot_accept`, `all_payment_refund_evidence_is_required`, `accept_requires_review_and_physical_count`, `reject_requires_reason_not_false_receipt`, `accept_and_reject_validate_different_response_shapes`, `ambiguous_result_locks_both_decisions`, `local_retry_and_close_restore_focus`.
- [ ] Use valid UUIDs, two item amounts `100.00`/`50.00`, refund `35.00` and server total `115.00`; all IDs/evidence/covered dates must be visible. No local sum is asserted. Inject wrong-recipient notice, incomplete detail, wrong result/empty object, duplicate click and delayed response. Expect zero writes until proper confirmations; exactly one selected decision afterward.
- [ ] Run `node --test spina_portal/tests/management-remittance-workspace.test.mjs`; confirm the missing mounted review and Reject path.
- [ ] Mount recipient notices/history using existing `/notifications` and `/remittances` with actual grants. Preserve shared notification acceptance `/notifications/{id}/accept-remittance` and add/reuse record-shaped `/remittances/{id}/reject`; never POST both raw receive and notification accept. Check exact sender/recipient/remittance/notice/status/custody fields according to each handler. Rejection re-reads affected notices rather than pretending its response contains result.notification. Require review for both, physical count for Accept, reason for Reject; keep complete immutable history/rejection explanation and local Retry/focus.
- [ ] Retain one pending-decision lock, offline/denied cleanup and authoritative uncertain-result reconciliation; a local GET or Close does not authorize a new decision. Update affected UI only and call optional onSaved for current counts. Do not give Management another user's recipient authority or Collector sender self-acceptance.
- [ ] Run new and existing receiver/Employee/Collector tests with Task1A/1B/session/privacy regressions. Inspect full/rejected/read-only/failed detail at phone widths; no real handover.
- [ ] Commit `feat(web): mount protected Management remittance receiving`.

## Task 2 — Preserve drafts across local success updates (R2, retained)

**Files:** `roles/management.js`, registered renewal/remittance handles; new `management-local-refresh.test.mjs`; existing `role-local-updates.test.mjs`, staff tests.
**Interfaces:** Implement refreshManagementRegion, including new renewals/remittances callbacks, without a full mount or generic form cache.

- [ ] Write `support_save_preserves_unrelated_drafts`, `terms_save_preserves_unrelated_drafts`, `staff_invite_preserves_unrelated_drafts`, `remittance_save_preserves_unrelated_drafts`, `other_dirty_queue_row_survives`, `post_save_read_failure_is_not_write_failure`. Assert actual node identity/value for search, Office intake, another response and proof file input. Use confirmed terms contract, not imaginary legacy approval.
- [ ] Run `node --test spina_portal/tests/management-local-refresh.test.mjs`; reproduce root-remount losses.
- [ ] Replace remaining full-remount success paths; clear only confirmed submitted editor, retain other nodes/selection, refresh authoritative counts and invalidate stale reviewed state without reauthorizing it. Preserve exact pending commands and guard scope; separate saved/read-failed from unknown result. Bind each region once, manage cleanup and restore focus only when still intended.
- [ ] Run new tests with role-local-updates, staff-invite, management-staff-devices-presentation and inserted workflow suites. Test duplicate clicks, abort, changed version, removed permission and file retention. No second POST from a failed readback.
- [ ] Commit `fix(web): preserve Management drafts after queue actions`.

## Task 3 — On-demand groups and safe header Refresh (R2–R3, retained)

**Files:** Create `management-workspace-tasks.js`; edit `roles/management.js`, bounded `app.js`, `sw.js`; new `management-lazy-loading.test.mjs`.
**Interfaces:** Implement task controller above using an equivalent shared hook when available. Current getSession and abort-owning registration are required; copied mount context cannot remain the authority after token rotation.

- [ ] Write `today_does_not_wait_for_loan_operations`, `today_does_not_wait_for_secondary_workflows`, `revisit_mounts_once`, `task_error_is_local_and_retryable`, `header_refresh_keeps_dirty_fields`, `refresh_cannot_erase_pending_write`, `expired_handle_cannot_register_or_render`, `permission_change_clears_old_tasks`. Deferred requests assert visible Today AND absence of unopened-task reads.
- [ ] Run `node --test spina_portal/tests/management-lazy-loading.test.mjs`; confirm eager-load/reset failures.
- [ ] Render shell/placeholders first; account/dashboard independently. Lazy-load other data and mounts, including renewal/remittance, without recreating forms. Register cleanup/load/refresh/permission callbacks; read current session for later actions. Keep busy/uncertain flows intact through ordinary Refresh; explicit protected reconciliation remains separate. Do not zero unloaded metrics or clear locks by task switching.
- [ ] Run new tests with workspace-lifecycle, session-refresh, session-boundaries, shell, sharing and PWA tests. Test uncertain Cash Disbursement through same-identity token rotation, changed identity/device/grants and new lazy controls offline. Add public modules to current PWA convention without caching private responses.
- [ ] Commit `perf(web): load Management tasks only when needed`.

## Task 4 — Staff mobile cards and device focus (R4, retained)

**Files:** `roles/management.js`, bounded `management-devices.js`, scoped `app.css`; new `management-staff-mobile-focus.test.mjs`.
**Interfaces:** Retain bindStaffDevices cleanup/mutation signatures; track exact opener and selection generation.

- [ ] Write mobile data-label, focus-open/Close, late-selection/no-focus-steal, account-only/no-device-request cases. Include removed opener, user focus moved while loading and error Close.
- [ ] Run `node --test spina_portal/tests/management-staff-mobile-focus.test.mjs`; capture current 390/320 layout before correction.
- [ ] Reuse 680px mobile-card pattern, retaining desktop columns/data/counts/IDs/selection and permission labels. Move/return focus only for current intended detail with visible-heading fallback. Keep confirmations/reloads/48px controls/error locks and readable typography.
- [ ] Run new tests with management-staff-devices-presentation, management-devices and ui-busy-focus; inspect1440/390/320 long names/emails and keyboard order. No-overflow alone does not pass.
- [ ] Commit `fix(web): make Staff devices usable on narrow screens`.

## Task 5 — Local tasks and true alert destinations (R5, retained/extended)

**Files:** task controller, `roles/management.js`, `management-alerts-audit.js`, narrow app/UI/CSS/sharing integration; new `management-task-navigation.test.mjs`.
**Interfaces:** Reuse activate(groupId,taskId); retain top-level data-nav-target and existing group IDs. Add explicit task allowlist and managementAlertTaskTarget(code), retaining compatible group-target return.

- [ ] Write unchanged-six-groups, local DOM retention/selection, staff/renewal/Support precise-link, `remittance_alert_reaches_recipient_review`, `unread_shortcut_reaches_personal_updates`, unauthorized/unknown target, keyboard and pre-DOM-change capture invalidation tests.
- [ ] Run `node --test spina_portal/tests/management-task-navigation.test.mjs`; confirm old broad-group destinations.
- [ ] Implement all spec R5 local tasks while preserving Office four steps, collection-action subviews, financial workflows and existing guards. A receiver's remittance alert now reaches Task1C; do not accept an honest fallback as completion when the real permitted view is required. My updates mounts when Task7B is available, never as audit. Unknown object identity is not guessed from label/name.
- [ ] Stop/invalidate active/preparing capture before local changes and re-evaluate exact eligibility. Never move capture markers to group ancestors. Test hidden children and stale loads using mocked tracks only.
- [ ] Run new tests plus workspace-navigation, management-office-guided-workflow, alerts/audit presentation, screen-sharing, credential/client-account and journal-deduplication regressions. Check every formerly reachable permitted workflow remains reachable.
- [ ] Commit `feat(web): add focused Management task navigation`.

## Task 5A — Loan detail and supported pagination (R10, new)

**Files:** `management-portfolio.js`, narrow orchestration/CSS; new `management-portfolio-detail-paging.test.mjs`.
**Interfaces:** Add handle loadPage(offset), openLoan(loanId), and `managementLoanDetailMarkup(loan) -> string`. No wider borrower endpoint.

- [ ] Write `next_page_reaches_loan_150`, `query_change_resets_offset`, `global_summary_is_not_filtered_total`, `failed_next_page_is_retryable`, `stale_page_cannot_replace_new_query`, `exact_loan_detail_shows_server_facts`, `same_names_and_two_loans_keep_identity`, `removed_or_denied_loan_clears_detail`.
- [ ] Fixture150 global/100 first-page/50 second-page; assert second GET limit=100&offset=100 with unchanged q/status, no financial arithmetic, exact IDs/order. Detail shows supplied paid amount/percentage, last-payment/ADV dates, PASS/payment counts and renewal status; null is unavailable, zero retained. View/Close never POSTs.
- [ ] Run `node --test spina_portal/tests/management-portfolio-detail-paging.test.mjs`; reproduce absence of paging/detail.
- [ ] Implement explicit Previous/Next pages using existing API and same-response R1 summary. Full page permits Next, short/empty page ends that query with usable Previous. Label page/returned count, not invented has_more/filtered total/lifetime completeness. Reset offset on changed query/status, guard races and failed page retry. Render read-only detail by exact loaded loan/client IDs, invalidate changed/removed scope, and manage focus. No name-fallback, Client/Collector API, default balance or computed paid percent.
- [ ] Run new tests with Task1, client-loan-grouping/presenters/navigation/role tests; inspect phone cards, long amounts, 100/50-page changes and concurrent refresh. Document offset paging's non-snapshot limitation.
- [ ] Commit `feat(web): expose Management loan detail and pagination`.

## Task 6 — Compact audit/device lists (R6, retained)

**Files:** `management-devices.js`, `management-alerts-audit.js`, parent state handoff; new `management-list-density.test.mjs`.
**Interfaces:** Extend bindManagedDevicePanel(root,options={}) -> cleanup compatibly; initialFilter/initialLimit/onStateChange retain deliberate filter. Audit uses local visible cap only.

- [ ] Write pending-two-of36, explicit-filter-after-status-change, All/Show-more-all36/order, filtered action-original-ID, unknown status reachability, audit-visible-vs-server-total and similar-events-distinct tests. Audit fixtures0/12/100; cap/increment10.
- [ ] Run `node --test spina_portal/tests/management-list-density.test.mjs`; confirm unbounded/default-state failures.
- [ ] Implement first-open Pending/Active/All precedence, explicit selection retention including empty,10-row batches and honest loaded counts. Audit disclosure retains full evidence/order/visible_domains and window_days=30&limit=100. Filter resets cap, not records; no deletion/dedup or inferred totals.
- [ ] Run device/audit suites and browser-check36th device, filtered correct action, duplicate-looking events and focus.
- [ ] Commit `refactor(web): compact Management audit and device lists`.

## Task 7 — Today, Cash Disbursement and Account density (R7, retained)

**Files:** `roles/management.js`, scoped `app.css`, cash markup only; new `management-ui-density.test.mjs`.
**Interfaces:** Existing metrics/task handles/field names; no new totals, upload or API.

- [ ] Write compact-but-accessible zero attention, unknown-not-zero, cash-editor-only-on-selection, full-row purpose/evidence and bounded-account-width tests. Preserve Workspace/Additional access, reset separation and does-not-send-money copy.
- [ ] Run `node --test spina_portal/tests/management-ui-density.test.mjs`; confirm baseline density failures.
- [ ] Apply R7 using existing tokens,48px controls and720px/fluid profile width. Do not remove warning/readiness text or pending recovery. Keep Employee prepare-only and separate journal posting.
- [ ] Run new tests with dashboard/accounting/cash-disbursement/workspace/account-security/hierarchy/credentials/client-account safety suites; inspect desktop/phone Today, Accounting, Account.
- [ ] Commit `style(web): refine Management density without changing workflows`.

## Task 7A — Financial statement periods and local recovery (R11, new)

**Files:** `management-financial-statements.js`, task/orchestration integration; new `management-financial-statement-periods.test.mjs`.
**Interfaces:** Backward-compatible `loadManagementFinancialStatements(api,{periodId=null}={})`; add `mountManagementFinancialStatements({root,api,getSession,signal,getAccountingOverview}) -> {refresh():Promise<void>,dispose():void}`. Injected optional overview loader reuses current safe mount data; default reads existing accounting overview, not a new endpoint.

- [ ] Write default-period-follows-response, selected-period-exact-request, period-A-cannot-overwrite-B, wrong-returned-period-rejected, no-period-vs-error, retry-preserves-selection and period-view-never-mutates cases. Two UUID periods have distinct exact fixture totals, including negative income where existing formatting permits.
- [ ] Run `node --test spina_portal/tests/management-financial-statement-periods.test.mjs`; observe missing selector behavior.
- [ ] Use `fiscal_periods` from `/api/v1/management/financial-accounting`; explicit selection calls `/statements?period_id=...` and validates returned pack.period.period_id. Keep default unparameterized behavior, actual label/date/status, dashes/loading/unavailable and local Retry. Share only safe reads, not full editor mounts. Do not invent GET fiscal-periods, create/reopen periods or mix totals across responses.
- [ ] Run new tests with existing financial-statements/accounting presentation/journal/export suites and Task3. Verify posted-ledger-only figures, excluded drafts, accounting.view boundary and no unrelated form loss.
- [ ] Commit `feat(web): select Management statement periods safely`.

## Task 7B — Personal Updates and owned record navigation (R12, new)

**Files:** `roles/management.js`, task/alert integration; extract `management-updates.js` only if needed to keep orchestration bounded, adding sw membership in same commit; new `management-updates.test.mjs`.
**Interfaces:** `mountManagementUpdates({root,api,getSession,signal,navigate,onRead}) -> {refresh():Promise<void>,dispose():void}` may be colocated; navigate accepts only allowlisted task + verified object ID. onRead refreshes dashboard metrics authoritatively.

- [ ] Write own-recipient-mark-read-local, wrong-id/user-result-not-read, already-read/double-click,65-records30/60/65, personal-updates-not-audit, verified-remittance/renewal-target, unknown-metadata-neutral, drafts-and-locks-survive and late-response-disposed tests.
- [ ] Run `node --test spina_portal/tests/management-updates.test.mjs`; confirm missing surface/actions.
- [ ] Mount Account > My updates with `/activity-notifications` and exact-ID `/read` POST. Validate returned owner/read fields and update one row/focus only. Keep API limit-only behavior, loaded/unread/global counts separate, local Retry and all returned events. Resolve related objects through actual authorized data; missing metadata is a documented limitation, not guessed URLs or automatic decisions.
- [ ] Run new tests plus Client local notification safety, task-navigation/session/sharing/audit suites; prove marking personal updates never mutates permanent audit evidence or unlocks pending financial actions.
- [ ] Commit `feat(web): add Management personal Updates`.

## Task 7C — Payment-proof retry and Support history (R13, new)

**Files:** shared `payment-proofs.js` with #488 coordination, `roles/management.js`/Support region; new `management-queue-recovery.test.mjs`.
**Interfaces:** Keep proof mount's cleanup-function return. Optional handle registration can expose guarded refresh without recreating active proof form. Support local loader accepts `{status,limit:100,offset}` and owns current request generation.

- [ ] Write first-proof-error-has-retry, proof-retry-is-GET-only, uncertain-review-blocks-refresh, Client-file-retained-on-unrelated-action, Support-history-status/query, dirty-response-survives-unrelated-refresh, changed-state-cannot-review-stale, and denied-is-not-empty tests.
- [ ] Run `node --test spina_portal/tests/management-queue-recovery.test.mjs`; confirm missing local recovery/navigation.
- [ ] Keep error/status root and Retry after the first proof read failure; replay current GET only when safe, preserving paging, exact versions/content, uncertainty and no-payment-posted boundary. Support statuses at baseline are open/answered/resolved/cancelled; use existing API filter/limit/offset, default open, reset offset on filter. Actions stay answered/resolved only where currently valid; history does not grant editing. Retain unrelated draft nodes, with explicit discard for unavoidable dirty same-editor switch. R8 handles renewal status/history; do not create a second legacy queue.
- [ ] Run new tests with existing proof Client/Management uncertainty, content/history/paging, Support/local-update and inserted renewal tests. Assert no endpoint/permission expansion or automatic retry of writes.
- [ ] Commit `fix(web): recover Management queues without losing work`.

## Task 7D — Explicit borrower/output/integration gap matrix (R14, new)

**Files:** This plan's scope-disposition section and, during execution if needed, `docs/reviews/2026-10-02-management-output-scope.md` (not public assets). Backend and other-role contracts are read-only references.
**Interfaces:** Evidence matrix columns: surface/output; current endpoint/source; exact permission/object scope; fields/limits; implement-now or follow-up; test/evidence/blocker.

- [ ] Map borrower detail, broader schedules/statements/receipt/issued documents, statement print packs, current accounting-review ZIP, renewal office/execution/photo concurrency and unsupported notification metadata. Include Employee #487/shared receiver integration status.
- [ ] Verify each proposed link/output against actual endpoint and object authorization. Existing outputs are marked existing; absent contracts are explicit gaps, not invented Client/Collector reuse. Record the smallest follow-up needed for a genuine blocked requirement.
- [ ] Review UI inventory for fake buttons, disabled placeholders labeled complete, inferred financial values and duplicated employee/report engines. Require negative tests for unsupported/denied destinations.
- [ ] Update dispositions with exact evidence. No new endpoint/grant/report generator or plan rewrite is implied. Keep any unresolved R8 photo/execution or other safety blocker visible rather than marking the whole workflow accepted.
- [ ] Commit `docs: map Management report and contract boundaries` only with actual evidence from execution.

## Task 8 — Integrated proof and synchronized handoff (R1–R14, retained/expanded)

**Files:** Current tests/build tooling, `.github/workflows/spina-ci.yml` (read/run, not weaken), this ledger; synthetic browser fixtures only under tests and never dist.

- [ ] Reconcile every original/addendum requirement with tests, runtime/browser evidence or an explicit R14 contract-gap disposition. Distinguish real implementation results from previous review mocks; legacy approval error reproduction is not a successful new terms test.
- [ ] Run final portal checks once, then build without retesting the same unchanged tree. Verify current commands/inline public-output CI first:

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

Do not subsequently run npm run build on the unchanged head: it repeats tests. Public-output verification is inline CI, not an imagined checker script. Inspect actual assets/caches/fixtures as well as secret patterns.

- [ ] Capture18 core layouts (six groups at1440/390/320) plus new terms/signers/office/locked/proof/activation states, complete remittance evidence/Accept/Reject/history, loan100+50/detail, two statement periods, Updates30/60/65 and failed proof Retry. Include36 devices/two Pending,100 audit records, long names/money, zero/empty/malformed/error, keyboard/Close/focus,200% zoom and reduced motion. Use actual built modules and synthetic responses; block unexpected network and mutating calls. No-overflow/DOM assertions alone do not establish readability.
- [ ] Prove wrong/empty financial results never show success; physical receipt and borrower/signature boundaries; full-evidence confirmation; backend proof-review activation semantics; pending-command/duplicate/uncertainty handling; saved/read-failed separation; stale IDs/versions/periods/pages; file/draft retention; offline during load/write; token/identity/device/grant teardown; private photo/object cleanup; mocked capture boundaries. No live route/financial GET probes or production operations.
- [ ] Integrate shared #486/#487/#488 work through agreed ownership and smoke-check other roles. Confirm existing Office, employee, proof, accounting/journal/receipt/custody safeguards; coherent PWA upgrade with new modules, no private/test files/caches and no duplicated shell handlers. Final tested SHA includes actual integrated code.
- [ ] Push only this branch; inspect current exact-head required jobs **Backend, quality, and security**, **Portal, Flutter, and Android**, **Financial and disposable PostgreSQL**. No duplicate workflows/unchanged reruns; retain SHA/run IDs/results. Pending/Red and docs-only Green are not implementation acceptance.
- [ ] Review final code/spec/coverage with an independent reviewer when available. Update PR from planning-only only after product commits exist; keep Draft/open/unmerged. No mark-ready/merge/tag/deploy/delivery/migration/Master acceptance.
- [ ] Sync GitHub, latest Notion and Create State with exact branch/head, completed/pending tasks, commands/results, CI, visual evidence, shared integration, R14 gaps and next action. Disclose unavailable connectors and keep a copyable checkpoint; never claim a sync that failed.

## Coverage and completion ledger

All implementation and assessment below is pending at this revision. Replace status with exact evidence during execution, not predictions.

| Requirement / task | Required coverage | State |
| --- | --- | --- |
| Task0 | Live refs, original/addendum and shared ownership | Pending Codex |
| R1 / Task1 | False-zero error/recovery, global summary, races | Not implemented |
| R8 / Task1A | Real rich renewal queue/terms, exact results, no legacy approval | Not implemented |
| R8 / Task1B | Custody/proof/activation and private evidence/uncertainty | Not implemented |
| R9 / Task1C | Actual recipient review, full evidence, Accept/Reject, exact-result checks | Not implemented |
| R2 / Task2 | Draft/File identity, scoped success updates and pending recovery | Not implemented |
| R3 / Task3 | Independent Today, lazy loads, safe Refresh/session cleanup | Not implemented |
| R4 / Task4 | Staff390/320 readability, device permissions and focus | Not implemented |
| R5 / Task5 | Six groups, precise task destinations and private boundaries | Not implemented |
| R10 / Task5A | Exact loan detail,100+50 pagination and global-summary separation | Not implemented |
| R6 / Task6 | All device/audit evidence reachable, original IDs/order | Not implemented |
| R7 / Task7 | Today/cash/account density with protected flows unchanged | Not implemented |
| R11 / Task7A | Authorized periods, response matching and local retry | Not implemented |
| R12 / Task7B | Own Updates/Mark read, safe destinations,30/60/65 | Not implemented |
| R13 / Task7C | Proof initial retry, Support history and draft/uncertainty protection | Not implemented |
| R14 / Task7D | Borrower/output/metadata/version limits explicitly mapped | Pending assessment |
| Task8 | Full checks,18 core plus new views, other roles/privacy/PWA/exact-head CI | Not run |

## Scope dispositions to complete during execution

Statements/journal/TB/accounting-review ZIP and guided Office/employee systems already exist; do not rebuild them. Supplied-field loan details, existing pagination/periods, true renewal/recipient flows, personal Updates and local recovery are mandatory. Broader borrower reports/print packs, missing notification identifiers and unpinnable latest-photo or execution prerequisites require an evidence-backed gap entry, not a fictional endpoint, guessed amount or claimed-complete stub. Owner Red/Green feedback must be checked against the actual PR head/jobs before continuing.

## Copyable Codex task

Implement the UPDATED revision2 Management completion plan in existing Draft PR #485 on `plan/management-web-ui-completion-20261002`. Fetch the latest head; do not use only the original7fdf54ed snapshot. Read both revised documents, original reviews, functional addendum5943820685, live main/open PRs, frozen Master296, latest Notion and Create State. Execute0,1,1A,1B,1C,2,3,4,5,5A,6,7,7A,7B,7C,7D,8, preserving all original tasks. Use failing behavioral tests before fixes and small reviewed passing commits. Coordinate shared receiver/proof/app/ui/CSS/PWA/employee work with486/487/488; no duplicate PR/router or overwritten WIP. Connect real renewal terms/continuation and recipient remittance review with exact result/authority/uncertainty handling; include detail/paging/periods/Updates/recovery and all UI fixes. Preserve exact server money, independent borrower/recipient actions, online-only safeguards, private boundaries and draft/File nodes without new persistence or stale authorization. Reuse existing outputs; map unsupported contracts explicitly. Update evidence and GitHub/Notion/Create State after meaningful progress. Leave485 Draft/open/unmerged; no mark-ready/merge/deployment/delivery/migrations/production credentials/financial probes/payments/photos/signatures/cash receipt/real capture/Master acceptance. Finish with exact head, results, visual evidence, integration status, scope gaps and blocked/unverified acceptance.
