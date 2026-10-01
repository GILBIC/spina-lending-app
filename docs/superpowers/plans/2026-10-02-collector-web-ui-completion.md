# SPINA Collector Web UI Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to execute task-by-task. The owner selected Codex. Keep one integration owner for shared files; parallelize independent reviews, not competing edits. Track steps with checkboxes.

**Goal:** Complete every finding from the 2 October Collector Web UI review while retaining existing financial outcomes and safeguards.

**Architecture:** Repair existing vanilla-JavaScript modules in place. Extract remittance and route presentation/controllers, retain one mount-owned financial guard, and reconcile authoritative reads without reconstructing unrelated drafts. Add small optional shell lifecycle hooks only in coordination with Management PR #485.

**Tech Stack:** Current ES modules, HTML/CSS, Node.js >=22, built-in node:test, existing portal/PWA build and current FastAPI APIs. No new runtime dependency or backend endpoint.

**Spec:** [2026-10-02-collector-web-ui-completion-design.md](../specs/2026-10-02-collector-web-ui-completion-design.md).

**Handoff state:** Documentation only. Baseline main `41a13eb59c9cc1b65a0a6a51f3b73db4a0895013` after #484; #485 is a separate Management handoff. All implementation and runtime acceptance below are pending. The owner will start Codex on this PR branch. No automatic agent invocation, implementation, mark-ready, merge, deployment/delivery, migration or live operation is part of creating the plan.

## Global constraints

- Preserve current Collector navigation/IDs, pink/white route-first identity, authorized destinations, area order, separate Regular/7x7 and Payment/Unable to pay actions.
- Keep endpoint/query semantics, device sequence/transaction UUIDs, revisions, server receipt verification, allocation hashes, borrower choices, correction/custody locks and renewal confirmations.
- Collector financial writes remain online-only. One mounted workspace owns one guard. Routine refresh/filter/lazy load must not clear offline/uncertain locks or regenerate an ambiguous transaction identity. No automatic financial retry/outbox.
- Drafts remain in the current mounted session only; no new localStorage/sessionStorage/IndexedDB/URL/PWA persistence. Logout, identity/device/permission changes or expiry clear old state. Never extend credential/one-time-secret lifetime.
- Do not sum visible rows to invent financial totals, alter Regular/7x7 allocations, dates, PASS/ADV, tax/accounting/penalties, or bypass Combined Pay Preview/Confirm.
- No new framework, router/global store, generic reconciliation engine, endpoint, backend/schema change, dependency upgrade, CI weakening, Master #296 edit, real capture, production credential/transaction or delivery/deployment.
- Coordinate shared app/CSS/navigation/PWA edits with #485. Do not modify its Management plan or import its unmerged task modules. Keep both branches separate; record the owner/order for overlapping edits.
- Keep PR Draft/open/unmerged, automatic merge off. Do not mark ready or claim owner/production acceptance. Product implementation is a later owner-started Codex task.

## Review focus

1. Skipped, malformed, read-only and stale-date remittance reads must not impersonate a verified zero, empty recipient list or current submit authorization — Task 1.
2. Accepted write followed by read failure, simultaneous editors, changed revisions and date rollover must preserve truthful receipts without enabling duplicate/stale writes — Task 2.
3. Hidden required inputs, stale promise fields and preview flags must remain correct when amount/type/reason/borrower changes — Task 4.
4. Slow reads, offline during loading, same-user token refresh and account/permission changes must not resurrect controls or lose uncertainty locks — Task 5.
5. Same-name borrowers, two loans per borrower, restrictive filters and more returned history than initially visible must preserve exact identities and reachability — Tasks 6–7.

## File map

New focused product files, under `spina_portal/assets/`:
- `collector-remittance.js`: move existing remittance presentation/binding, explicit read states, local preview/recipient/history refresh and guarded submission. No second remittance wire contract.
- `collector-route-view.js`: move ledger/attention and route form binding; keyed row reconciliation, mobile attention markup, focus and filters. No new route financial model.

Existing edits, also under `spina_portal/assets/` unless stated:
- `roles/collector.js`: orchestration, one guard, current route snapshot, scoped refresh and lazy section registry.
- `collector-workflows.js`: progressive fields/Combined Pay layout and narrow route snapshot invalidation; keep protected helpers.
- `collector-other-area.js`, `collector-renewals.js`: bounded success/invalidation integration and status wording only; preserve their workflows.
- `app.js`: optional mounted-workspace hook in coordination with #485; `ui.js` only if existing navigation hooks cannot express exact-row navigation.
- `app.css`: Collector-scoped layout rules. Do not broadly rewrite global forms/tables.
- `spina_portal/sw.js`: add each new public module in the same commit if required by current shell conventions.

Read-only contract references: `collector-contract.js`, `collector-workflow-contract.js`, `collector-write-guard.js`, `presenters.js`, `screen-sharing.js`, `api.js`, `session-refresh.js`, `account-credentials.js`; `gilbic_backend/src/gilbic_backend/remittance_api.py`. Existing tests and actual applicable backend contracts govern validation. A narrow visibility integration for sharing may change only with direct regression proof; no broadened eligible surface.

Every test filename below is under `spina_portal/tests/`. Use existing helpers. New synthetic fixture code must remain under tests and outside public `dist`. No requirement to possess the previous conversation evidence archive.

## Shared interfaces for the planned extractions

These are proposed interfaces to implement, not functions claimed to exist already. Reconcile names with verified upstream work at Task 0; update all consumers together.

- Read state: `{status, data, error}`, status `idle | loading | ready | error | unavailable | not_permitted`; skipped reads carry null data, never empty-success fallback.
- `mountCollectorRemittance({root, api, getSession, getRouteDate, guard, onSaved, signal})` returns `{refresh(): Promise<void>, invalidatePreview(reason): void, dispose(): void}`. The constructor renders; activation invokes refresh. Preserve the existing remittance request body.
- `mountCollectorRouteView({routeRoot, attentionRoot, api, getSession, getRoute, guard, identity, onSaved, navigate, signal})` returns `{applyRoute(route, {savedEntryIds = []} = {}): void, setUnavailable(error): void, focusEntry(id): boolean, dispose(): void}`. `route` is the current server payload, not filtered rows. Rendering uses existing withAttention/presenter behavior.
- `onSaved(result, {source, entryIds = []}) -> Promise<void>` identifies the submitting module and known route IDs. Sources: `collection`, `combined`, `covered-date`, `correction`, `remittance`, `other-area`, `renewal`. Do not infer missing IDs from names; a full authorized route GET is safe when the affected subset is unknown. Each caller clears only its confirmed submitted editor.
- `registerRouteConsumer(onSnapshot) -> unsubscribe`: a tiny mount-local callback set owned by Collector orchestration. Supply the latest ready route at registration and later accepted reads; unregister on child disposal. Existing workflow mounts retain their cleanup-function return and may opt into this callback for safe review invalidation. No global event bus.
- Optional shell hook `registerWorkspaceHandle(handle)` accepts `{activate(sectionId): void, refreshVisible(): Promise<void>, dispose(): void}` for the current mount only. Reuse an equivalent verified #485 hook rather than installing a duplicate. `getSession()` reads current shell context, not a stale copied object. Keep existing sharing hooks before content changes.

## Task 0 — Baseline, isolation and shared-file ownership

**Files:** Read this spec/plan, applicable AGENTS.md, `package.json`, `.github/workflows/spina-ci.yml`, current Collector modules/tests and #485's live diff.

- [ ] Read live main, this PR head/open PRs, frozen #296, latest Notion and Create State project `69a61c48-f842-44ac-aa11-e987ffec4a36`. Separate actual implementation from a planning checkpoint.
- [ ] Use this PR branch in an isolated Codex worktree. Do not reset others' work, start a competing Collector PR, or silently stack on #485.
- [ ] Record ownership/order for app.js/ui.js/app.css/sw.js overlap. Continue role-specific work while any shared-file conflict is resolved. Reuse verified upstream fixes with evidence instead of rewriting them.
- [ ] Verify named paths and current test/build commands. Baseline tests run once when equivalent exact-head evidence is absent. Log inherited failures separately; do not weaken tests or repeatedly run unchanged full CI.
- [ ] Add an exact-SHA PR checkpoint. Commit subsequent product stages only after their red/green cycle and review.

## Task 1 — Remittance read truth and safe recovery (C1)

**Files:** Create `collector-remittance.js`; edit `roles/collector.js`, `spina_portal/sw.js`; add `collector-remittance-state.test.mjs`. Preserve existing remittance feedback/guard tests.

**Interfaces:** Implement the remittance handle above and export `remittanceSummaryMarkup(readState) -> string` for independently testing ready versus unavailable metrics. Route/date/permissions are evaluated through getters at use time.

- [ ] Write the state tests with observable DOM and request counts:

```js
// Adapt fixture setup to existing test helpers; names below pin the cases.
// route_failure_skips_preview_without_zero_summary
assert.equal(previewRequests.length, 0);
assert.match(remittanceText, /Route date unavailable/);
assert.doesNotMatch(remittanceText, /₱0\.00/);
// history_only_never_calls_create_only_reads
assert.equal(previewRequests.length + recipientRequests.length, 0);
assert.match(remittanceText, /Remittance history only/);
// successful_zero_is_real; field presence is not truthiness
assert.match(remittanceSummaryMarkup({status: 'ready', data: {
  total_amount: '0.00', transaction_count: 0, client_count: 0,
  unable_to_pay_count: 0,
}, error: null}), /₱0\.00/);
```

Add `recipient_failure_differs_from_empty_success`, `missing_summary_is_unavailable`, `retry_keeps_note_and_valid_recipient`, `old_date_response_is_ignored`, `removed_recipient_requires_reselection`, and `submit_requires_current_ready_inputs`. For a ready fixture use date `2026-10-02`, amount `'12345.67'`, counts 12/6/1; fail one field without coercing it to zero. Backend summary/date fixtures must match the current contract.
- [ ] Run `node --test spina_portal/tests/collector-remittance-state.test.mjs`; confirm failures demonstrate existing behavior or missing planned module, not broken imports in the test harness.
- [ ] Move remittance rendering/binding intact, then add independent states/retries, exact field checks, current-date response guards and strict submit eligibility. Preserve note/valid recipient. Retain create-only preview/recipient permission; history stays independently usable. Unknown/negative/nonpositive totals cannot become an eligible submit by fallback. No totals from history/route.
- [ ] Run the new suite plus `collector-feedback.test.mjs`, `collector-write-guard.test.mjs`, `collector-workflow-contract.test.mjs`, and affected PWA tests. Expect zero failures, correct permission request counts and unchanged wire payload/financial locking.
- [ ] Review and commit `fix(web): make Collector remittance states truthful`.

## Task 2 — Keep drafts on successful writes and reconcile current route (C2)

**Files:** Create `collector-route-view.js`; edit `roles/collector.js`, bounded `collector-workflows.js`, `collector-other-area.js`, `collector-renewals.js`, remittance handle and `sw.js`; add `collector-local-refresh.test.mjs`.

**Interfaces:** Implement route handle, onSaved metadata and mount-local route-consumer registration above. Add internal `refreshCollectorData(context, change) -> Promise<void>` to Collector orchestration; one authoritative route read per accepted refresh generation. No guard replacement on routine refresh.

- [ ] Write `payment_keeps_other_payment_and_remittance_nodes`, `accepted_save_read_failure_is_not_payment_failure`, `changed_revision_blocks_old_draft`, `new_day_does_not_retarget_old_input`, `shared_saved_callbacks_do_not_remount`, and `busy_or_locked_guard_survives_refresh`. Pin a Regular and 7x7 pair for the same borrower plus a different borrower: save exactly one row, assert one POST, unchanged unrelated textarea DOM identity/text and no second POST after read failure.

```js
assert.strictEqual(findOtherNote(), otherNoteNode);
assert.equal(otherNoteNode.value, 'Return after lunch');
assert.strictEqual(findRemittanceNote(), remittanceNoteNode);
assert.equal(remittanceNoteNode.value, 'For office receipt');
assert.equal(collectionPosts.length, 1);
assert.match(savedRowText, /Receipt/);
```

Also test Combined/covered-date/correction, remittance, other-area and renewal callbacks separately; old hashes/selections must invalidate when their actual source revision changes, not on unrelated unchanged reads. Include duplicate clicks, removed authority, user focus moved and aborted reads.
- [ ] Run `node --test spina_portal/tests/collector-local-refresh.test.mjs`; observe current root-remount/draft loss.
- [ ] Extract existing ledger/attention/actions, reconcile by route_entry_id and update the submission map from accepted reads. Clear only submitted editor, keep other safe nodes/filter state, and invalidate changed financial drafts for explicit review. Keep one guard and listeners. Preserve verified receipt/status through post-save read errors; block stale/duplicate actions without creating retry writes. Route consumer callbacks preserve unrelated notes while invalidating stale combined/schedule/handover evidence.
- [ ] Run new tests with `collector-feedback.test.mjs`, `collector-workflows.test.mjs`, `collector-other-area.test.mjs`, `collector-renewals.test.mjs`, `collector-write-guard.test.mjs` and `role-local-updates.test.mjs`. Inspect the two-note/save scenario and focus in a synthetic browser. Expect one write, no lost unrelated notes, no stale permission reuse.
- [ ] Review and commit `fix(web): retain Collector drafts after verified saves`.

## Task 3 — Mobile Needs attention and focus consistency (C3)

**Files:** Edit `collector-route-view.js`, `roles/collector.js`, scoped `app.css`; add `collector-attention-mobile.test.mjs`.

**Interfaces:** Reuse route handle; do not change amount/model semantics. Keep `collector-master-review` ID while the heading reads Needs attention. Direct row navigation is added in Task 6.

- [ ] Write `attention_cards_have_explicit_labels`, `attention_preserves_exact_amount_and_ids`, `empty_success_differs_from_route_error`, and `normal_focus_return_does_not_steal_user_focus`. Assert borrower/area/loan/reason/amount labels, desktop table retention, and mobile-card class. Capture baseline actual browser layout at 390/320px before styling.
- [ ] Run `node --test spina_portal/tests/collector-attention-mobile.test.mjs`; confirm expected markup/focus failures.
- [ ] Apply the existing mobile-card pattern with Collector-scoped rules at the current breakpoint (verify 680px). Keep currency/digits together and long text readable, without hiding amounts, shrinking fonts or forcing horizontal page scroll. Preserve existing route cards and error/Cancel feedback. Keep 48px baseline controls and reduced motion.
- [ ] Run the new suite plus `collector-feedback.test.mjs`, `ui-busy-focus.test.mjs`, `role-daily-work.test.mjs` and `web-ui-hierarchy.test.mjs`. Inspect 1440/390/320 screenshots and keyboard order; overflow-only assertions are insufficient.
- [ ] Commit `fix(web): make Collector attention readable on phones`.

## Task 4 — Progressive payment details and Combined Pay hierarchy (C4)

**Files:** Edit `collector-workflows.js`, `collector-route-view.js`, scoped `app.css`; add `collector-payment-details.test.mjs`. Read, do not weaken, existing submission/preview contracts.

**Interfaces:** Keep `allocationField`, `followupFields`, `readFollowup` exports compatible. Add `bindCollectorPaymentDetails(form, {getEntry, getEntryType}) -> cleanup` for normal route forms. The binder controls disclosure/required state, not allocation. Combined Pay uses the existing preview flags for required detail and existing invalidation mechanism.

- [ ] Write `ordinary_payment_is_compact`, `short_regular_or_pass_reveals_reason`, `other_requires_explanation`, `promise_fields_follow_reason`, `hidden_promise_does_not_leak`, `unknown_obligation_keeps_options_available`, `voluntary_no_collection_is_reachable`, `server_error_reveals_invalid_field`, and `combined_preview_flags_reveal_required_details`. Use supplied obligation `'100.00'`, payments `'100.00'`/`'50.00'`/`'150.00'`; Unknown is not zero. Exact UI comparison must distinguish large cent values `'90071992547409.91'` and `'90071992547409.92'` without Number rounding.

```js
// After changing from promised_to_pay_later to no_cash:
assert.equal(readFollowup(form).promised_payment_date, null);
assert.equal(readFollowup(form).promised_amount, null);
// Changing cash or borrower invalidates the reviewed Combined Pay draft:
assert.equal(confirmButton.disabled, true);
assert.equal(financialPosts.length, 0);
```

Test payment/pass/advance switching, Cancel, a short 7x7 scenario without inventing Regular rules, extra borrower choice, and hidden required controls. A disclosure toggle alone must not call an API or approve a preview.
- [ ] Run `node --test spina_portal/tests/collector-payment-details.test.mjs`; confirm all-visible/stale-field behavior fails.
- [ ] Add compact amount/actions plus optional Note and Payment options and follow-up disclosures. Auto-reveal required exceptions only from known exact obligation/contract or authoritative preview flags. Preserve mandatory validation and null irrelevant promise fields. Give Combined identity/cash/choice/preview/action regions adequate width; keep Preview then Confirm, reviewed hash and exact wire values. No local split, auto-choice or one-tap bypass.
- [ ] Run new tests with `collector-contract.test.mjs`, `collector-workflow-contract.test.mjs`, `collector-workflows.test.mjs`, `collector-feedback.test.mjs` and `collector-other-area.test.mjs`. Inspect full/short/extra/pass/promise at phone widths, no inaccessible required input, and Combined Pay desktop width.
- [ ] Commit `refactor(web): simplify Collector payment detail presentation`.

## Task 5 — Independent route loading and guarded lazy sections (C5)

**Files:** Edit `roles/collector.js`, remittance/route integration and bounded `app.js` in coordination with #485; add `collector-lazy-loading.test.mjs`. Do not create another task framework.

**Interfaces:** Use optional registerWorkspaceHandle/getSession from Shared interfaces, or equivalent verified upstream hook. Collector handle owns a small section->loader/cleanup map inside collector.js. Header refresh calls refreshVisible for routine ready state; locked/uncertain state retains the explicit existing reconciliation path and communicates necessary reset.

- [ ] Write `route_renders_while_remittance_preview_is_pending`, `route_does_not_wait_for_history_or_activity`, `lazy_section_mounts_once`, `failed_section_retries_locally`, `routine_header_refresh_keeps_drafts`, `header_refresh_cannot_interrupt_financial_write`, `offline_before_lazy_mount_keeps_controls_locked`, `token_refresh_does_not_revive_old_permissions`, and `superseded_mount_cannot_register_or_render`. Use deferred reads; assert visible route and actual absence of unopened-screen requests, not just hidden DOM.
- [ ] Run `node --test spina_portal/tests/collector-lazy-loading.test.mjs`; confirm current coupled loading/reset behavior.
- [ ] Render shell first; load route/account independently and secondary modules on activation. Keep route failure distinct from empty route. Deduplicate reads/mounts, read current permission/session state, and cancel old generations. Use the same guard for late-mounted controls. Routine refresh preserves drafts/current view and invalidates required stale data. Offline/uncertain guard remains sticky until explicit safe recovery; no hidden reset by tab switch or successful GET. Keep sharing teardown before replacing captured content and all existing eligibility boundaries.
- [ ] Run new tests with `workspace-lifecycle.test.mjs`, `workspace-navigation.test.mjs`, `session-refresh.test.mjs`, `session-boundaries.test.mjs`, `collector-write-guard.test.mjs`, `screen-sharing.test.mjs` and `shell.test.mjs`. Smoke-check #485 Management hook and other roles. Blocked shared integration stays explicitly pending, not worked around by a second hook.
- [ ] Commit `perf(web): load Collector route independently of secondary work`.

## Task 6 — Route discovery and exact attention links (C6)

**Files:** Edit `collector-route-view.js`, narrow `roles/collector.js` navigation wiring and scoped `app.css`; add `collector-route-discovery.test.mjs`.

**Interfaces:** Add `filterCollectorEntries(entries, {query = '', area = '', status = 'all'}) -> entries` preserving original identity/order. Reuse route handle focusEntry(id). Area/status selectors and search operate on authorized loaded data only; DOM rows are hidden/shown, not rebuilt per keystroke.

- [ ] Write `search_and_area_keep_server_order`, `status_predicates_match_existing_attention`, `two_loans_and_same_names_keep_distinct_ids`, `filter_preserves_unsaved_form_node`, `attention_reveals_exact_hidden_row_without_payment`, `stale_target_never_falls_back_to_name`, and `filter_counts_do_not_change_route_totals`. Pin All/Needs attention/Recorded today; a short recorded payment may appear in both latter sets. Twelve rows across six clients still count as 12 loan entries.

```js
assert.deepEqual(filtered.map(x => x.route_entry_id), expectedOriginalIds);
assert.strictEqual(noteAfterFilter, noteBeforeFilter);
assert.equal(financialPosts.length, 0); // search, clear and attention links are read/navigation only
assert.equal(targetForm.hidden, true); // focusing a loan never opens a payment
```

- [ ] Run `node --test spina_portal/tests/collector-route-discovery.test.mjs`; record missing filter/per-row navigation failures.
- [ ] Add small search, Area and status controls with Clear filters and Showing X of Y loaded loan entries. Keep existing full-route summaries separate. Attention links use existing shell navigation, exact route IDs, visible filter clearing when necessary, and focus on the target identity. Missing or unauthorized target gets a safe message, never a name-based substitute or broader lookup. Do not rewrite area order or financial metrics.
- [ ] Run new tests plus `presenters.test.mjs`, `workspace-navigation.test.mjs`, `collector-contract.test.mjs`, `collector-write-guard.test.mjs` and Task 2/3 tests. Inspect a long route, same-name clients, empty matches, offline search and keyboard focus.
- [ ] Commit `feat(web): add Collector route search and exact attention links`.

## Task 7 — Copy, renewal status and complete loaded history (C7)

**Files:** Edit `roles/collector.js`, `collector-remittance.js`, `collector-renewals.js`, bounded `app.css`; add `collector-copy-history.test.mjs`.

**Interfaces:** Preserve server status codes/actions. A local display helper maps known tokens to labels only. History/update renderer accepts visibleLimit=30; Show more adds 30 up to the loaded list length. Preserve identity/order and mounted controls; do not introduce backend pagination.

- [ ] Write `today_and_route_headings_are_distinct`, `route_count_is_labeled_loan_entries`, `known_renewal_status_is_humanized`, `unknown_status_never_looks_approved`, `history_31st_and_61st_records_are_reachable`, `updates_keep_duplicate_looking_records`, and `display_limit_is_not_server_total`. Fixtures contain 65 ordered records: 30 initially, 60 after first Show more, all 65 after second; zero/failure remain distinct. Assert currency and wire enum values unchanged.
- [ ] Run `node --test spina_portal/tests/collector-copy-history.test.mjs`; confirm old headings/tokens/silent slicing failures.
- [ ] Apply C7 copy and 30-row incremental display with loaded-record counts, keeping all returned records accessible. Humanize not_submitted as Not submitted and known statuses without changing API predicates. Apply only Collector-specific spacing; preserve visit, handover, receipt, custody, correction and uncertainty instructions.
- [ ] Run new tests plus `collector-renewals.test.mjs`, `collector-other-area.test.mjs`, `role-daily-work.test.mjs`, `web-ui-hierarchy.test.mjs`, and applicable remittance tests. Inspect Updates and renewal cases at 1440/390/320; no clipped actions or false-completeness statement.
- [ ] Commit `style(web): clarify Collector labels and loaded history`.

## Task 8 — Integrated proof, source review and handoff (C8)

**Files:** Existing portal test/build tooling, `.github/workflows/spina-ci.yml` (read/run, not weaken), this checklist, and synthetic fixtures under tests only.

- [ ] Reconcile C1–C8 and every review finding with actual tests/screenshots. Check the final diff against scope, including all former full-remount onSaved paths. Record optional feature/connector/browser limitations rather than marking them complete.
- [ ] Run final full portal checks once, then build without repeating them. Current baseline package and CI provide these Bash commands; verify their current form before use:

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

Do not subsequently run npm run build on the same unchanged head because its script repeats tests. The public-output check is inline CI, not a claimed standalone checker script. Inspect asset membership/fixtures and PWA coherence in addition to this baseline pattern scan.

- [ ] Run real browser tests with actual built modules and synthetic API fixtures; reject unexpected external/mutating requests. Capture the C8 eight-section matrix at 1440/390/320 (24 screenshots), plus changed Updates and conditional-surface smoke checks. Cover normal/short/extra/pass/promise, explicit-zero/error/read-only states, same-name clients, long money/labels, 65 history records, keyboard/200% zoom/reduced motion, offline, delayed reads, and post-save recovery. Check readability, not merely overflow. Record exact SHA and secret-free console/request results.
- [ ] Verify all protected regressions: duplicate/uncertain results, accepted receipt match, one workspace guard, offline during writes, current route/date/revision, server-reviewed Combined Pay, correction ownership/custody, cross-area attribution, renewal confirmation, account/logout scope and existing screen privacy. Use mocks/disposable fixtures only. Do not infer residence/photo/attendance/full device acceptance from layout samples.
- [ ] Inspect Client/Employee/Management smoke checks and integrate shared #485 changes through agreed ownership. Confirm no conflicting refresh handlers, PWA assets omitted, extra access, public fixtures, or stale captured screens. Final tested integration head must include all actual reviewed code, not just one old branch.
- [ ] Commit/push only this Collector branch. Read existing exact-head CI results: Backend, quality, and security; Portal, Flutter, and Android; Financial and disposable PostgreSQL. No duplicate workflows or unnecessary unchanged re-runs. Docs-only Green is not implementation acceptance. Pending/Red stays explicit.
- [ ] Update PR body/checklists with exact implemented head, requirements, commands/results, browser evidence and limitations. Keep Draft/open/unmerged with no automatic merge. Do not mark ready, tag v1.0, change Master acceptance, run delivery/migrations/deploy or production operations.
- [ ] Synchronize GitHub, Notion Current State and Create State after meaningful checkpoints. Include exact branch/head, completed/pending stages, CI run IDs and next action. Failed connector: disclose it and retain the exact copyable checkpoint; never claim a sync that did not occur.

## Completion ledger

| Stage | State at planning handoff | Required proof |
| --- | --- | --- |
| 0 Baseline/ownership | Pending Codex | Live refs, test baseline, shared-file owner/order |
| 1 Remittance truth | Not implemented | Skipped/read-only/error/zero/recovery and submit guards |
| 2 Draft-safe refresh | Not implemented | Node retention, receipt/read failure, stale revision and one guard |
| 3 Mobile attention | Not implemented | Readable 390/320 currency, labels, focus |
| 4 Payment details | Not implemented | Conditional validity/payload, exact comparisons, server preview |
| 5 Independent loading | Not implemented | Deferred reads, offline/lazy/session/header refresh safety |
| 6 Route discovery | Not implemented | Exact IDs/order, no unintended writes, unchanged summaries |
| 7 Copy/history | Not implemented | All 65 returned records reachable, neutral labels |
| 8 Integration | Not run | Full tests, 24 layouts, all-role/privacy/PWA, exact-head CI |

Update with commit/evidence references, not predictions. When the owner reports only Red or Green, verify the matching exact GitHub head and required jobs before proceeding.

## Copyable Codex task

Implement this Collector Web UI completion plan on this Draft PR's existing branch. Read the linked design, Tasks 0–8, live GitHub/open PRs, frozen Master #296, latest Notion checkpoint and Create State before editing. Coordinate shared app/navigation/CSS/PWA ownership with Management PR #485; do not add Collector scope to that PR, import unmerged Management modules, overwrite other work or create a duplicate Collector PR. Use failing behavioral tests before each fix, small passing commits and the specified browser checks with synthetic data. Preserve route-first design, exact server amounts, Regular/7x7 rules, borrower choices, online-only writes, one guard, receipt/hash verification, uncertain-result reconciliation, privacy and identity cleanup. Keep drafts only within the current session; never persist new financial drafts or weaken locks to retain them. Complete all reviewed remittance, draft, mobile, payment-form, loading, discovery, copy and history tasks. Update the checklist and GitHub/Notion/Create State with exact-head evidence. Leave the PR Draft/open/unmerged; no mark-ready/merge/deploy/delivery/migration/production credential or transaction/real capture. Finish with exact SHA, results, remaining or blocked acceptance, and next owner action.
