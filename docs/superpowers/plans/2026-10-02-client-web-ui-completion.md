# SPINA Client Web UI Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement task-by-task after the owner starts Codex. Keep one integration owner for shared files. Steps use checkbox (`- [ ]`) syntax; every implementation task has its own test/review/commit cycle.

**Goal:** Complete the reviewed Client Web UI gaps without rebuilding the portal or changing lending/payment authority.

**Architecture:** Repair existing ES modules with explicit resource state, one per-loan schedule source, retained editor DOM, and local result refresh. Reuse current protected APIs, private document downloads, proof replay, renewal helpers, and the agreed optional shared shell lifecycle. Extract only a small mount-local read controller and focused transaction-detail rendering; no global store or new router.

**Tech Stack:** Existing vanilla JavaScript ES modules, HTML/CSS, Node.js >=22, node:test, current portal build/PWA tooling, and unchanged FastAPI/PostgreSQL APIs. Browser tests use synthetic data, not live borrower credentials or transactions.

**Spec:** [2026-10-02-client-web-ui-completion-design.md](../specs/2026-10-02-client-web-ui-completion-design.md).

**Status:** Planning-only handoff. Baseline main `41a13eb59c9cc1b65a0a6a51f3b73db4a0895013` after #484; all tasks below are pending Codex. No runtime checks or UI fixes are claimed by the documentation commit. The owner starts execution on this PR's branch; do not automatically invoke an agent or create a duplicate PR.

## Global constraints

- Preserve current pink/white branding, the 11 Client destinations, Regular/7x7 distinctions, and existing protected workflows. Other roles/native apps are regression surfaces, not redesign targets.
- Client sees only their own authorized records. Verify exact user/device/linked-borrower scope, IDs, capabilities, current versions and same-loan responses; clear private state on scope change/denial.
- Exact server money only. No payoff, penalty, principal/interest split, total, coverage, maturity or allocation invented from card values or balance differences. Filtering/display grouping is not financial calculation.
- No backend endpoint, schema or role grant, dependency/framework, global cache, generic persistence layer, or duplicate document generator.
- No new browser persistence for drafts, selected files, schedules, private downloads or credentials. Keep the actual File input node for unrelated refresh, not a serialized/repopulated FileList.
- Preserve online-only protected mutations, confirmations, duplicate-submit guards, exact pending proof/provider/request identities and uncertainty recovery. A refreshed view is not evidence that an unknown write failed.
- Proof submitted/reviewed, provider checkout, official payment, renewal approval, signing, cash receipt and activation remain separate states. Do not auto-trigger any mutation from navigation.
- Preserve intentional restrictions on public registration and Client password self-change/reset; keep account/device revocation safety and `automatic_source_posting=false`.
- Coordinate shared code with Management #485, Collector #486 and Employee #487 before overlapping edits. No WIP overwrite, unreviewed cherry-pick, competing shell hook or import of an unmerged role-specific controller.
- No production credentials/uploads/payments/signatures/cash confirmations/capture, migrations, delivery/deployment, mark-ready, merge, tag, or Master #296 acceptance edits. Keep this PR Draft/open/unmerged with automatic merge off.

## Review focus

1. Failed or wrong-loan schedules must not silently remove warnings or combine old summary/new detail; test in Task 1.
2. Retained File inputs and pending write identity must survive unrelated reads, while borrower/device/grant changes erase them; test in Tasks 2–3 and 5.
3. Long/ambiguous/non-contiguous schedule data and Manila rollover must not become guessed amounts or coverage; test in Tasks 4 and 6.
4. Notifications and downloads can reference obsolete/wrong records or hostile URLs; resolve only authorized IDs and test in Tasks 7–8.
5. Parallel role work, delayed mounts and refreshed tokens can produce duplicate callbacks or stale private screens; test lifecycle/privacy and all-role integration in Tasks 5 and 10.

## Files and interfaces

All asset basenames below are under `spina_portal/assets/`; tests are under `spina_portal/tests/` unless a full path is given.

Primary existing files: `roles/client.js`, `client-schedule.js`, `client-statement.js`, `client-documents.js`, `client-gcash.js`, `payment-proofs.js`, plus narrow shared `app.js`, `ui.js`, `app.css`, `presenters.js`, and `spina_portal/sw.js` edits. Preserve existing exported helpers or update every consumer/test when an intentional interface changes.

Planned new product files:
- `client-workspace-state.js`: a small mount-local read lifecycle with explicit state and request generations. No session-independent cache.
- `client-payment-details.js`: exact payment detail markup and binding, reusing private download functions.

Existing read-only contract references: `gilbic_backend/src/gilbic_backend/client_loan_api.py`, `client_payment_api.py`, `client_document_api.py`, `activity_notification_api.py`, proof/renewal/Support repositories, and their current tests. Existing PDFs and first-loan document flows are not reimplemented. Inspect `client-gcash.js` and `payment-proofs.js` recovery before changing mounts.

### Shared read-state contract (introduced by Task 1)

`ReadState = {status: 'idle'|'loading'|'ready'|'error', data: unknown|null, error: Error|null, revision: number}`. Arrays are meaningful only for ready state. Failed refresh does not expose old data as current; a UI may retain a clearly labeled stale view with actions disabled, but may not silently treat it as fresh.

`createClientReadController({signal, isCurrent, onChange})` returns `{state(key), load(key, loader, {refresh=false}={}), invalidate(key), dispose()}`. `load` returns `Promise<ReadState>`, deduplicates an in-flight ordinary load, and commits only the newest request in the current scope. `loader` receives `{signal}`; all abort/listener state is owned by this mount. The only subscribers are explicit caller callbacks through onChange; this is not an event-bus framework.

## Task 0 — Reconcile execution baseline and shared ownership

**Files:** Read this spec/plan, applicable `AGENTS.md`, package scripts, existing tests, current CI, and #485–#487 diffs. Do not edit other plans.

- [ ] Fetch current main, this PR head/open PRs, frozen #296, latest Notion checkpoint and Create State project `69a61c48-f842-44ac-aa11-e987ffec4a36` before asking about prior decisions.
- [ ] Work on this PR's existing branch in an isolated Codex worktree. Confirm clean state; preserve other work and do not reset/force-push someone else's changes.
- [ ] Record one integration owner/order for shared app/ui/CSS/PWA/proof changes. Reuse an equivalent verified optional shell hook already implemented in the other workstreams. Continue nonoverlapping Client work while coordinating overlaps.
- [ ] Compare actual code with baseline. For an already fixed finding, run its acceptance case and record evidence instead of reverting/reimplementing it. Run baseline portal checks once if equivalent exact-head evidence is absent; distinguish inherited failures.
- [ ] Record execution SHA, ownership, baseline results/limitations and next task in the PR. Check existing notification producers and schedule status fixtures; do not guess their contracts.

## Task 1 — Correct payoff/schedule states and same-loan recovery (L1)

**Files:** Create `client-workspace-state.js`; modify `client-schedule.js`, `roles/client.js`, `spina_portal/sw.js` as required. Create `client-payoff-recovery.test.mjs`.

**Interfaces:** Implement the read controller above. In `client-schedule.js`, add `createClientScheduleController({api, reads, signal, isCurrent, onState}) -> {get(loanId), load(loanId, options?), dispose()}` using keys `schedule:<loanId>`. `bindClientScheduleButtons(context)` accepts `context.clientSchedules` and returns cleanup. `loadClientHomeObligationSchedules` must return per-loan ReadState values after this change; update its callers/tests together. Keep `formatAuthoritativeMoney` unchanged for other callers.

- [ ] Write failing tests `preload_error_is_visible`, `retry_updates_summary_and_detail`, `review_required_hides_confirmed_payoff`, `wrong_loan_and_late_result_rejected`, and `missing_money_is_not_zero`. Use exact fixture values and inspect both regions:

```js
assert.match(home.textContent, /Payoff information unavailable/);
// Resolve the same-loan retry with exact_payoff_total='2205.00',
// assessed_penalty_balance='105.00', and a known valid penalty status.
assert.match(home.textContent, /2,205/);
assert.match(panel.textContent, /2,205/);
assert.match(panel.textContent, /105/);
assert.equal(unrelatedLoanPanel.textContent, beforeUnrelated);
```

- [ ] Run `node --test spina_portal/tests/client-payoff-recovery.test.mjs` and verify failures reflect the actual omission/recovery defect, not a fixture/import mistake.
- [ ] Implement explicit per-loan Loading/error/ready state; validate exact loan_id, read_only response, rows and displayed field types. Render known payoff/review behavior in both summary/detail without arithmetic. Keep projected versus assessed labels; unknown/review-required cannot claim confirmed payoff. Add generation, abort and scope guards; route all schedule loads through this controller.
- [ ] Run the new suite and relevant existing `client-*.test.mjs` suites. Test true zeros, invalid money, Regular/7x7, all known penalty states, concurrent requests, logout and linked-borrower changes. Verify no duplicate requests for a simultaneous home/detail load.
- [ ] Commit `fix(web): recover Client payoff and schedule state consistently` with red/green evidence.

## Task 2 — Truthful dependent panels and first-load retry (L2)

**Files:** Modify `roles/client.js`, `client-documents.js`, `client-gcash.js`, `payment-proofs.js`; create `client-dependent-read-state.test.mjs`.

**Interfaces:** Pass optional `loansState`, `paymentsState`, and `onRetry(resourceKey)` to `mountClientDocuments`, preserving its cleanup return and existing arrays for compatible ready callers. Add `loansState` to Client-mode proof/Gcash bindings; Management proof mode remains unchanged. Add optional proof `registerHandle({refreshReadOnly, openRecord, isUncertain})`, keeping its existing callable cleanup return. The handle never exposes or clears the private attempt payload.

- [ ] Write `documents_loan_error_is_not_no_link`, `documents_payment_error_is_not_no_receipt`, `checkout_loan_error_is_not_empty`, `first_proof_error_has_retry`, and `retry_preserves_uncertain_attempt`. Assert the new retry makes one GET and zero POSTs, only updates its region, and leaves independently usable document controls intact. Cover missing/malformed capability and true empty success.
- [ ] Run `node --test spina_portal/tests/client-dependent-read-state.test.mjs`; verify baseline failures.
- [ ] Propagate L2 ReadState to dependent regions instead of bare fallback arrays. Keep proof error/status/retry mounted from startup. Distinguish disabled configuration from failed configuration. No checkout/new-proof action may use a guessed loan after failed loading; an authorized existing proof can still load history. Keep byte/type/size and exact replay validation. Do not replace the full Management proof UI to add Client retry.
- [ ] Run new tests and existing proof, Client documents, and GCash suites. Exercise denied access, stale IDs, uncertain POST and recovery. A read-only refresh cannot submit/retry a file or reset a provider intent.
- [ ] Commit `fix(web): distinguish Client unavailable and empty records`.

## Task 3 — Preserve drafts and files across successful actions (L3)

**Files:** Modify `roles/client.js`, targeted `payment-proofs.js` read/editor separation, and read-controller callbacks; create `client-draft-preservation.test.mjs`.

**Interfaces:** `refreshClientRegion(context, key) -> Promise<ReadState>` updates one known result region through Task 1 reads. Explicit keys are support, renewals, renewalWorkflow, loans, payments, statement, notifications and account. Mutations invalidate only their dependencies; a queue refresh never owns another form node. Proof `refreshReadOnly` from Task 2 declines unsafe replacement while its private attempt is uncertain.

- [ ] Write `support_keeps_renewal_and_proof_file`, `renewal_actions_preserve_support_and_file`, `accepted_save_failed_refresh_is_not_failed_save`, `typed_during_request_is_retained`, and `scope_change_clears_private_drafts`. Pin renewal amount `5000`, its message, proof note and a synthetic PNG. Assert File input node identity and selected File identity in a real browser, plus unchanged form nodes in DOM tests. Add a passing control for local Mark as read.
- [ ] Run `node --test spina_portal/tests/client-draft-preservation.test.mjs`; reproduce current full-remount resets.
- [ ] Replace routine post-success `mountClientWorkspace` calls with region updates. Cover Support and each renewal create/cancel/decision/sign/cash-confirm path, not just one button. Separate verified save success from failed subsequent reads. Keep dirty editors outside replaceable lists; reset only the submitted unchanged inputs. Invalidated eligibility/ownership disables the stale target and requires explicit revalidation, never a silent retarget. Pending proof/checkout identities and File bytes remain unchanged.
- [ ] Run new tests, existing Client renewal/security/notification/proof/Gcash suites and `role-local-updates.test.mjs` when present. Test intentional proof paging/Refresh/new submission with dirty input and discard confirmation, plus uncertainty lock. Test duplicate clicks and responses after abort. Focus follows a completed action only if still intended.
- [ ] Commit `fix(web): retain Client drafts and selected proof files`.

## Task 4 — Mobile Schedule/Statement and bounded schedule display (L4)

**Files:** Modify `client-schedule.js`, `client-statement.js`, scoped `app.css`; create `client-mobile-records.test.mjs`.

**Interfaces:** Extend `renderClientSchedule(schedule, {view='upcoming', today, visibleLimit=20}={})` while retaining compatibility for its original argument. Task 1's schedule controller/binder owns panel view, visible limit, Close and Refresh state. Statement remains a renderer of the supplied full authoritative data; no new query contract.

- [ ] Write `schedule_and_statement_have_mobile_labels`, `show_more_reaches_all_120_rows`, `history_retains_past_due_context`, `close_restores_focus_and_ignores_late_panel_result`, and `filter_does_not_rewrite_amounts_or_order`. Test 0/30/120 rows, equal-looking distinct records, unknown statuses, negative/large supported exact money and long notes. Verify initial cap20 then40; all120 reachable through repeated Show more.
- [ ] Run `node --test spina_portal/tests/client-mobile-records.test.mjs` and capture failing baseline phone layouts using synthetic data.
- [ ] Reuse labeled cards below the existing phone breakpoint, desktop tables otherwise. Keep amounts readable, all existing Statement fields and void flags. Implement Upcoming/History/All as date filters only; keep server past-due summary/link visible. Add Close/Collapse and separate Refresh, accessible selected state and count labels. Do not deduplicate rows, invent payment status or expand capture eligibility.
- [ ] Run focused tests and inspect actual 390/320/1440 screenshots, keyboard/Close focus, 200% zoom and reduced motion. Ensure Show more/filters do not detach unrelated drafts. No overflow-only acceptance.
- [ ] Commit `fix(web): make Client schedules and statements readable on phones`.

## Task 5 — Independent section loading and safe shell refresh (L5)

**Files:** Modify `roles/client.js`, `client-workspace-state.js`, bounded `app.js`/`ui.js` hook wiring only after coordination, and `spina_portal/sw.js`; create `client-independent-loading.test.mjs`.

**Interfaces:** The agreed shell offers an optional mount-owned `registerWorkspaceHandle({activate(sectionId), refreshVisible(), dispose()})` (reuse the verified equivalent from #485–#487 rather than adding an alias registry). Client implementation lives in `roles/client.js`. It reads current identity via a fresh scope/session callback, not the copied startup context, and rejects late registrations after mount abort. The read controller carries no authority across mounts.

- [ ] Write `updates_statement_and_7x7_do_not_block_shell`, `one_loan_loads_while_another_waits`, `revisit_mounts_once`, `header_refresh_preserves_drafts`, and `old_scope_cannot_register_or_render`. Deferred promises must prove actual request timing and rendered content. Test same-user token refresh separately from user/device/permission/linked-client changes.
- [ ] Run `node --test spina_portal/tests/client-independent-loading.test.mjs`; verify initial Promise.all blockage.
- [ ] Render stable placeholders and independently available account/loan data before secondary reads. Schedule loads update loan summaries individually. Lazy-load actual module work/reads on first section activation; retain its editor DOM thereafter. Header Refresh invokes safe read refresh, leaving uncertainty state and files intact. Existing private-screen stop/eligibility callbacks run before any protected DOM switch; do not move a capture marker to a broader root. All child cleanups, download aborts and observers belong to the mount.
- [ ] Run new tests and existing navigation, session-refresh, workspace-lifecycle, screen-sharing and PWA suites. Inspect shared-role diffs. Ensure all new modules are shipped coherently and protected responses never enter shell cache.
- [ ] Commit `perf(web): load Client sections without blocking core records`.

## Task 6 — Next-installment guidance from saved schedule rows (L6)

**Files:** Modify `client-schedule.js` and `roles/client.js`; create `client-installment-guidance.test.mjs`.

**Interfaces:** `clientInstallmentGuidance({loan, scheduleState, today}) -> {status, selectedRow, pastDueAmount, pastDueCount, message}`. This selects/display-projects authoritative data; it never returns a calculated sum. `today` is explicit Manila YYYY-MM-DD for deterministic tests. Keep the agreed installment and selected-row remaining amount separately labeled.

- [ ] Write `today_partial_uses_returned_remaining`, `future_does_not_hide_past_due`, `coverage_is_not_inferred_from_range`, `unknown_or_ambiguous_rows_do_not_guess`, and `manila_rollover_marks_stale`. Base normal fixtures on actual backend test statuses `Due Today` and `Scheduled`; add any other collectible status only when its executable producer proves that meaning. Verify a loan daily amount `100.00` and row remaining `40.00` display as different facts, not recomputed debt.
- [ ] Run `node --test spina_portal/tests/client-installment-guidance.test.mjs`; observe missing guidance.
- [ ] Implement the L6 selector: valid today row first, otherwise earliest later known unpaid collectible row; ambiguous/missing inputs show Open schedule for the current amount. Keep server past due separate, exact row coverage, no-collection/paid indicators and L1 warnings. Day rollover requires refresh before presenting a new current-day amount; do not shift an old snapshot. No active loans requires a verified successful portfolio, not an error fallback.
- [ ] Run new and existing Client schedule/presenter tests. Browser-check partially paid, covered, no-collection, past-due, no future row, unknown state, different browser timezone and midnight. Confirm no extra independent schedule request or provider action.
- [ ] Commit `feat(web): show Client installment guidance from saved schedules`.

## Task 7 — Exact transaction details and existing PDF shortcuts (L7)

**Files:** Create `client-payment-details.js`; modify `roles/client.js`, `client-documents.js`, narrowly `client-statement.js`, and PWA membership; create `client-payment-details.test.mjs` and `client-contextual-documents.test.mjs`.

**Interfaces:** `renderClientPaymentDetails(payment) -> string` and `bindClientPaymentDetails({root, paymentsState, onDownload, signal}) -> cleanup`. Add `downloadClientRecordCopy({api, kind, transactionId, signal, saveFile}) -> Promise<void>` in `client-documents.js`, with kind only statement/payment. Reuse requirePrivateFile/savePrivateFile; caller validates transaction membership. Allowed endpoints are `/api/v1/client/statement/document` and `/api/v1/client/payments/{transactionId}/document` only. Original issued-document paths remain unchanged.

- [ ] Write tests proving exact collector/time/covered_dates/previous_balance/official_balance/note/origin/void fields, same-record download, no arithmetic and no auto-download. Use a large supported decimal string to catch Number conversion. Assert wrong-ID/denied/empty/wrong-MIME/aborted responses do not produce a download. Include a voided copy label and no false filtered-statement claim.
- [ ] Run `node --test spina_portal/tests/client-payment-details.test.mjs spina_portal/tests/client-contextual-documents.test.mjs`; confirm missing actions.
- [ ] Implement a readable detail disclosure with appropriate focus and exact transaction identity. Use only returned facts; missing optional data is Not recorded. Add Statement and payment-context download buttons through the shared helper, not duplicate PDF code. Keep current copies distinct from immutable originals and private temporary URLs revoked. Do not map balance differences to principal/interest/extra cash.
- [ ] Run new and existing document/Client-payment tests, plus the existing backend document-rendering tests with disposable fixtures as needed for output checks. Validate synthetic PDF content/layout through the available PDF tooling; record a blocked content check honestly. Verify another borrower cannot access the selected ID under existing authenticated tests.
- [ ] Commit `feat(web): connect Client payment details and record downloads`.

## Task 8 — Complete Updates and safe related-record actions (L8)

**Files:** Modify notification markup/bindings in `roles/client.js`; use proof handle from Task 2 and payment detail from Task 7; create `client-update-actions.test.mjs`. Contract references: `activity_notification_api.py` and actual producers, read-only.

**Interfaces:** `clientNotificationTarget(notification, authorizedRecords, producerMap) -> {sectionId, recordId, kind}|null`, with fixed Client section IDs and an explicit producer map verified from executable code. It is not a URL router. Use top-level transaction_id only for a transaction present in the current authorized payments. Proof/renewal/Support metadata keys are enabled only when producer evidence and owned-record resolution agree; unsupported mappings stay absent and documented.

- [ ] Write `all_65_loaded_updates_reachable`, `mark_read_keeps_forms_and_order`, `transaction_link_opens_exact_owned_record`, `missing_unknown_or_hostile_target_stays_read_only`, and `no_implicit_write_on_navigation`. Start with30, then60, then65 items. Pin malicious URLs/message UUIDs, wrong recipient, missing/deleted target, same names, and record outside first visible page. List actual producer type/key mappings in test fixtures; an empty/unsupported mapping must never pass as full deep-link completion.
- [ ] Run `node --test spina_portal/tests/client-update-actions.test.mjs`; verify display-cap/action gaps.
- [ ] Implement Show more30 and honest loaded/unread-among-loaded labels. Preserve authoritative order, distinct IDs and existing Mark as read request/result checks. Navigate only after safe owned-record resolution; use an honestly labeled section link only for a verified category without precise metadata. Unknown entries stay text. Do not invent an offset parameter for the current limit-only notification API or auto-mark read on opening a destination.
- [ ] Run new and existing local-update/notification/proof/renewal/security tests. Record unsupported producer metadata as a follow-up contract gap without changing backend/grants or silently omitting it from the completion report.
- [ ] Commit `feat(web): make Client updates complete and safely actionable`.

## Task 9 — Renewal next-action hierarchy and copy polish (L9)

**Files:** Modify existing renewal renderers/binders in `roles/client.js` and scoped `app.css`; create `client-renewal-presentation.test.mjs`.

**Interfaces:** `clientRenewalPresentation({eligibilityState, requestsState, workflowState, selectedRequestId, view}) -> view model`, view current/eligibility/history. Join request/progress only by exact request_id and preserve source uncertainty. Continue using existing requestClientRenewal* action helpers and exact endpoint/payload/confirmation contracts.

- [ ] Write `one_request_one_current_card`, `workflow_error_cannot_look_completed`, `borrower_only_actions_keep_readiness_checks`, and `cash_confirmed_is_not_active`. Cover all L9 states, cancellation/decline, office-only processing, other signers, exact net/offset amounts, unknown readiness tokens and stale selected request. Include keyboard and local view changes preserving other drafts.
- [ ] Run `node --test spina_portal/tests/client-renewal-presentation.test.mjs`; confirm current repeated/technical presentation.
- [ ] Implement compact Current requests/Eligibility/History presentation, clear next step, and human-readable labels without hiding authoritative notes. Do not duplicate action bindings, infer approvals, or auto-sign/confirm. Keep cancellation only when allowed and all actual confirmations. Unknown/stale workflow remains neutral and refreshable. Reduce redundant copy only where no safety/financial meaning is lost.
- [ ] Run new and existing renewal-workflow/credentials/privacy suites; inspect phone/desktop states and no borrower/loan mixing. Use mocked action responses only; test payment-proof/provider wording still distinguishes official payments.
- [ ] Commit `style(web): clarify Client renewal progress and next actions`.

## Task 10 — Integrated evidence, CI and handoff (L10)

**Files:** Changed tests, this checklist, current build/PWA assets and CI instructions. Add a synthetic fixture under `spina_portal/tests/fixtures/client-ui-completion.html` only if existing fixtures cannot cover the matrix; fixtures/docs must not enter public output.

- [ ] Reconcile every L1–L10 paragraph to code/tests/evidence and record remaining field/producer gaps. Label baseline observations separately from new results. No blanket completion from a docs-only CI or the earlier review archive.
- [ ] Run focused suites during iteration; final integration runs the complete portal suite once, then builds without repeating it. Recheck current scripts/CI first. At the reviewed baseline use:

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

Do not follow this with npm run build on an unchanged head; it repeats the tests. Public-output checks are inline in existing CI, not a presumed separate checker file. Inspect full asset/PWA membership and upgrade behavior in addition to these patterns.

- [ ] Use actual built modules and synthetic APIs; block unexpected network and all real mutation/provider/capture actions. Capture all 11 L10 section IDs at1440/390/320 (33 core samples), expanded schedules30/120, details, proof file/correction, all renewal stages, failed/disabled capability and document output. Inspect text, long exact money, focus/keyboard, 200% zoom, reduced motion, empty/error/recovery and console/request results. No horizontal overflow alone is not acceptance.
- [ ] Prove own-data/permission regression with existing tests for another Client and unauthorized loan/payment/document/proof/renewal/notification IDs, changed linked borrower, revoked device, expired session, late response and same-user token refresh. Prove proof exact replay/file preservation, private-download cleanup, no checkout-success-to-official-payment shortcut, no registration/self-password expansion, and no new screen-capture boundary. Test helper behavior with mocks/disposable fixtures, not real signatures/cash/credentials.
- [ ] Review shared integration with #485–#487; smoke-check Management/Employee/Collector on the actual integration head. Confirm one shell handle, no duplicate listeners/reads, no lost role changes, and all current private modules/cleanups intact.
- [ ] Push this branch; inspect existing exact-head CI jobs: **Backend, quality, and security**, **Portal, Flutter, and Android**, **Financial and disposable PostgreSQL**. Retain run IDs and status. No duplicate workflow, unchanged rerun or weakening of checks. Pending/Red is not Green.
- [ ] Update PR body from planning-only only after code exists; retain Draft/open/unmerged with automatic merge disabled. Report exact head, completed requirements, test/browser/PDF/CI results, verified integration and unverified/deferred notification/field mappings. Do not claim owner production/native-device acceptance or tag/merge/deploy.
- [ ] Synchronize GitHub, Notion Current State and Create State after meaningful progress. Include branch/SHA, task ledger, commands/results, CI IDs, artifacts, limitations and next action. Disclose a failed connector and keep a copyable checkpoint; never claim a sync that did not occur.

## Completion ledger

| Task | Planning state | Required proof |
| --- | --- | --- |
| 0 Baseline/ownership | Pending Codex | Current refs, shared owner/order, baseline checks |
| 1 Payoff/schedule | Implemented:71fbbf3e | Error/recovery, exact loan and values, review-required/races |
| 2 Dependent reads | Implemented:d30a325c | Failed versus empty, local retries, capability/replay safety |
| 3 Draft/file retention | Implemented:9f973a74 | Node/File identity, save/read separation, stale/scope cleanup |
| 4 Mobile/long records | Implemented:9f973a74 | Readable phone values, all120 rows, Close/filter focus |
| 5 Independent loading | Implemented:9f973a74 + shared shell70426697 | Deferred reads, current scope, safe Refresh and shared hook |
| 6 Installment guidance | Implemented:9f973a74 | No arithmetic, row semantics, coverage and Manila rollover |
| 7 Details/downloads | Implemented:9f973a74 | Exact transaction, existing private PDFs, content/ownership |
| 8 Updates/actions | Implemented:9f973a74; metadata gaps recorded | All65, safe targets, producer mapping and explicit gaps |
| 9 Renewal presentation | Implemented:9f973a74 | Distinct stages, exact request join, confirmed actions |
| 10 Integrated acceptance | Local portal/build/browser/PDF verified; root integration/CI/sync pending | Portal/PWA/privacy/browser/PDF, exact-head CI, sync |

## Explicit scope dispositions

Existing statement/payment PDFs are reused, not missing backend work. Live payment-provider enablement/settlement is outside this UI task. If a detailed allocation field or proof/renewal/Support notification identifier is not returned by a verified contract, document the exact gap and required follow-up approval; do not derive it or expose another role's endpoint. Public registration and Client password self-service remain restricted. These dispositions must appear in the final execution report, not be hidden as completed UI features.

## Copyable Codex task

Implement Client Web UI completion on this Draft PR's existing branch. Read this plan and its linked design, live main/open PRs, frozen Master #296, latest Notion checkpoint and Create State before editing. Complete Tasks0–10 in order with failing behavioral tests before fixes, focused passing checks and reviewable commits. Coordinate shared app/ui/CSS/PWA/proof changes with #485–#487; do not overwrite their work, create a duplicate PR or add another router. Preserve own-data authority, exact server money, per-loan identity, proof/provider/official-payment distinctions, pending-request recovery, confirmations, credential restrictions and private-screen boundaries. Keep drafts/File inputs without new browser persistence; reuse existing PDF endpoints. Make unsupported notification/transaction metadata an explicit contract gap rather than a guessed shortcut. Update this checklist and GitHub/Notion/Create State after meaningful progress. Keep Draft/open/unmerged: no mark-ready, merge, deployment/delivery/migrations, production credentials/uploads/payments, real renewal signing/cash confirmation/capture, or Master acceptance changes. Finish with exact head, results, visual/document evidence, integration status, remaining gaps and next owner action.

## Implementation checkpoint — 2 October 2026

Product execution commits:71fbbf3e, d30a325c, 9f973a74; optional shared shell imported as70426697. Mount-local resource state, schedule/payoff recovery, retained forms/files, lazy reads, mobile records, saved-row guidance, exact payment details/current PDF shortcuts, progressive Updates and one-card renewal hierarchy are implemented. Local evidence:1042 portal tests before shared shell;16 focused shell/lifecycle/loading tests after import. Synthetic Chromium33 core samples (11 destinations ×1440/390/320), schedule20→120, Close focus, real File identity across proof GET/Support/renewal actions, payment details, Updates65,200%zoom/reduced motion and changed-account disposal passed without console errors. Existing Client PDF/document/payment/loan backend tests66 passed; synthetic voided PDF exact text and rendered layout checked.

The root integration owner handles combined-role review, final cache version, exact-head remote CI, PR push/body and external checkpoints. This checkpoint does not mark integrated acceptance complete. Detailed local ledger/artifacts are retained by the root under checkpoints/current-prs-20261002/client-report.md and client-browser/. No production/native acceptance, merge/deploy/mark-ready or Master296 edits occurred.

Contract gaps: only client_payment_posted (SQL0013) and client_payment_voided (collection_void_repository) have verified transaction shortcuts. Proof/renewal/Support notification IDs require an approved producer contract; arbitrary metadata and URLs remain read-only. Missing financial allocation fields remain Not recorded; existing current PDFs are reused. Provider enablement/settlement, public registration and Client self-password service remain outside scope.
