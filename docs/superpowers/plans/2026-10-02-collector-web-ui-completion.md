# SPINA Collector Web UI Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development task-by-task. The owner selected Codex. Keep one shared-file integration owner; parallelize independent reviews, not competing edits. Track actual execution with checkboxes.

**Goal:** Complete every finding from both 2 October 2026 Collector reviews without changing protected financial outcomes.

**Architecture:** Repair the current ES modules, extracting bounded remittance/route controllers and adding a separate read-only schedule view. Retain one workspace guard, exact server state and unrelated draft/file nodes. Reuse coordinated shell lifecycle hooks, not another router or global state layer.

**Tech Stack:** Existing vanilla JavaScript, HTML/CSS, Node.js >=22, node:test, portal/PWA tooling and current FastAPI APIs. No new runtime dependency, backend endpoint or schema.

**Spec:** [2026-10-02-collector-web-ui-completion-design.md](../specs/2026-10-02-collector-web-ui-completion-design.md), revision 2.

**Handoff:** Documentation only, existing Draft PR #486, branch `plan/collector-web-ui-completion-20261002`. Main reviewed at `41a13eb59c9cc1b65a0a6a51f3b73db4a0895013`; previous docs head `20318a5e31f3dd8036fd5f40f7f210b174ed9e33`. Owner requested updating this PR with everything from the re-review. All product implementation/runtime acceptance remains pending. No new PR, automatic Codex invocation, application fix, merge or production operation is part of this update.

**Execution order:** 0 -> 1 -> 1A -> 2 -> 3 -> 4 -> 5 -> 6 -> 6A -> 6B -> 7 -> 7A -> 7B -> 7C -> 8. Original task IDs are retained so previous handoffs remain traceable. Added tasks are mandatory, not optional addenda. Task8 is final integration, after every insertion.

## Global constraints

- Preserve Collector navigation/IDs, pink/white route-first identity, area order, separate Regular/7x7 and Payment/Unable to pay.
- Keep API/query/body contracts, permissions, device sequences/UUIDs, route revisions, exact receipts, reviewed allocation hashes, borrower choices, corrections, attribution, custody and handover confirmations.
- Collector financial writes remain online-only, with one guard per mount. Routine refresh/navigation/GET/filter/lazy loading never resets uncertainty, creates a new retry identity or automatically repeats a financial request.
- Draft/file retention is mount-local only. No new localStorage/sessionStorage/IndexedDB/URL/PWA persistence. Denial, logout, expiry and identity/device/grant changes dispose private state. No longer-lived credentials.
- No new allocation/payoff/penalty/accounting engine or totals from visible rows. Keep exact decimal text; UI comparison may control disclosure only. Preserve Combined Pay Preview/Confirm and exact covered dates.
- No new backend endpoint/schema/grant, dependency/framework/router/global cache, offline outbox, native redesign, CI weakening, Master #296 edit, production credentials/transactions, actual capture, migration or delivery/deployment.
- Route GET can finalize elapsed schedules. All tests use in-process mocks or explicitly disposable fixtures, never production route probing under a read-only label.
- Coordinate shared app/ui/CSS/PWA/helpers with Management #485, Employee #487 and Client #488. Do not edit their plans/branches, import unmerged role-specific modules or overwrite WIP. Shared Employee work/pay belongs to #487; preserve its Collector integration.
- Keep #486 Draft/open/unmerged with automatic merge off. Do not mark ready or claim owner production/mobile acceptance. A docs-only Green is not implementation acceptance.

## Review focus

1. A resolved but empty/wrong-recipient/different-snapshot remittance response must not display success or unlock writes; no preview digest exists in the current POST body — Task1A.
2. Save succeeded/read failed, another dirty form or photo, changed route revision/date, and an uncertain write require different behavior — Task2 and Task5.
3. Hidden required fields, stale promise values, amount precision and Combined Pay flags must remain correct after type/amount/reason changes — Task4.
4. Route-view-only permissions, delayed/closed details, multiple same-date receipts, borrower-level repeated renewal flags and same-name clients must never select the wrong loan — Tasks6/6A/6B/7A.
5. Unknown notification metadata, wrong-recipient read results, loaded versus lifetime counts, and missing print/history contracts must remain honest and non-actionable where unsupported — Tasks7/7B/7C.

## File map

All asset basenames below are under `spina_portal/assets/`; tests are under `spina_portal/tests/`. Product modules added by this plan:
- `collector-remittance.js`: existing remittance presentation/read lifecycle plus complete evidence and verified submission.
- `collector-route-view.js`: existing ledger/attention/action extraction, keyed reconciliation, discovery and receipt detail.
- `collector-schedule-view.js`: read-only Collector schedule/payoff, independent of editors and Client APIs.

Existing bounded edits: `roles/collector.js` orchestration/guard/current snapshots; `collector-workflows.js` conditional fields and invalidation; `collector-other-area.js` onSaved/invalidation only; `collector-renewals.js` cash context, exact request opening and retry; `collector-workflow-contract.js` only a focused remittance matcher if that is its existing pattern; `app.js` optional mount hook; `ui.js`/`presenters.js` only shared-compatible formatting/navigation; `app.css` scoped presentation; `spina_portal/sw.js` new public-module membership in the same commit. Do not add another remittance recipient or payroll editor.

Read contracts before their task: `collector-contract.js`, `collector-workflow-contract.js`, `collector-write-guard.js`, `api.js`, `session-refresh.js`, `screen-sharing.js`, `account-credentials.js`, `employee-operations.js`; backend `remittance_api.py`, `remittance_review_repository.py`, `collector_route_api.py`, `collector_schedule_api.py`, `renewal_workflow_api.py`, `activity_notification_api.py` and actual notification producers. These backend files are read-only for this UI plan.

Test fixtures remain under tests and outside public dist. Previous conversation ZIPs are optional context, never assumed workspace files. Preserve existing tests; intentionally changed presentation assertions may be updated with behavioral proof, not weakened safety assertions.

## Shared interfaces for planned work

These are proposed interfaces, not existing-function claims. Reconcile names against live upstream at Task0 and update all consumers together.

- Read state `{status, data, error}`: `idle | loading | ready | error | unavailable | not_permitted`; skipped reads have null data, not an empty successful list.
- `mountCollectorRemittance({root, api, getSession, getRouteDate, guard, onSaved, signal}) -> {refresh(): Promise<void>, invalidatePreview(reason): void, openRecord(remittanceId): Promise<boolean>, dispose(): void}`. Constructor renders shell; activation triggers reads. openRecord resolves only current authorized history. All ordinary updates retain the same guard.
- `mountCollectorRouteView({routeRoot, attentionRoot, api, getSession, getRoute, guard, identity, onSaved, navigate, signal}) -> {applyRoute(route, {savedEntryIds = []} = {}): void, setUnavailable(error): void, focusEntry(id): boolean, openReceipt({routeEntryId, transactionId}): boolean, dispose(): void}`. Route input is the unfiltered server payload. New detail is not a financial editor.
- `onSaved(result, {source, entryIds = []}) -> Promise<void>` sources: collection, combined, covered-date, correction, remittance, other-area, renewal. Clear only confirmed submitted editor. Never infer target IDs from names.
- `registerRouteConsumer(onSnapshot) -> unsubscribe`: a tiny callback set in Collector orchestration, supplying the latest verified snapshot/invalidation to mounted children. Existing modules keep cleanup-function returns. No global event bus.
- Optional coordinated `registerWorkspaceHandle({activate(sectionId), refreshVisible(), dispose()})`: register only for the active mount; reject late registration. `getSession()` returns current shell authority, not a stale copy. Reuse a verified equivalent from #485/#487/#488. Keep privacy hooks before content changes.
- Additional detail/renewal/notification interfaces are defined in their tasks. Every hook unregisters on disposal; close/hidden state and stale generations prevent late focus or reopened panels.

## Task 0 — Baseline, ownership and requirement reconciliation

**Files:** Read both docs, applicable AGENTS.md, package.json, `.github/workflows/spina-ci.yml`, live Collector files/tests and related PR diffs.

- [ ] Check live main, #486 head/comments/files, open PRs, frozen #296, latest Notion and Create State project `69a61c48-f842-44ac-aa11-e987ffec4a36`. Read both original review and addendum5943559009. Do not mistake previous green documentation CI for implemented fixes.
- [ ] Use this same branch in an isolated worktree; confirm no WIP is discarded. Record integration ownership/order for overlapping app/ui/CSS/PWA/helpers with #485/#487/#488.
- [ ] Retain verified upstream fixes with tests instead of reverting/reimplementing them. Check named tests/interfaces and record any evolved equivalents in this plan.
- [ ] Run baseline checks only where equivalent exact-head evidence is absent. Separate inherited failures. Record starting SHA, task ownership, C1–C14 evidence map and next step in the PR.

## Task 1 — Truthful remittance states (C1)

**Files:** Create `collector-remittance.js`; edit `roles/collector.js`, `sw.js`; new `collector-remittance-state.test.mjs`.

**Interfaces:** Implement remittance handle and `remittanceSummaryMarkup(readState) -> string`. Dynamic permission/date comes from getters. Task1A adds evidence/matching before any completion claim for submission.

- [ ] Write `route_failure_skips_preview_without_zero_summary`, `history_only_never_calls_create_only_reads`, `create_only_does_not_call_ungranted_history`, `successful_zero_is_real`, `recipient_failure_differs_from_empty_success`, `missing_summary_is_unavailable`, `retry_keeps_note_and_valid_recipient`, `old_date_response_is_ignored`, `removed_recipient_requires_reselection`, `submit_requires_current_ready_inputs`.

```js
assert.equal(previewRequests.length, 0); // unavailable route date
assert.match(remittanceText, /Route date unavailable/);
assert.doesNotMatch(remittanceText, /₱0\.00/);
assert.match(remittanceSummaryMarkup({status:'ready',data:{
  total_amount:'0.00',transaction_count:0,client_count:0,unable_to_pay_count:0
},error:null}), /₱0\.00/);
```

- [ ] Run `node --test spina_portal/tests/collector-remittance-state.test.mjs`; verify expected missing/incorrect behavior, not a harness failure.
- [ ] Move original remittance renderer/binding, add independent read states/local retry, exact field validation and date/generation guards. Retain safe note/recipient; never fill missing counts or amounts with zeros. Each GET follows its actual permission; preserve POST body.
- [ ] Run new tests plus `collector-feedback.test.mjs`, `collector-write-guard.test.mjs`, `collector-workflow-contract.test.mjs` and affected PWA tests. Review/commit `fix(web): make Collector remittance states truthful`.

## Task 1A — Itemized remittance review and response confirmation (C9)

**Files:** `collector-remittance.js`, bounded `roles/collector.js`/`collector-workflow-contract.js`, scoped `app.css`; new `collector-remittance-evidence.test.mjs` and `collector-remittance-confirmation.test.mjs`.

**Interfaces:** `renderCollectorRemittanceEvidence(record, {history = false} = {}) -> string`; `collectorRemittanceResultMatches({collectorId, recipientId, collectionDate, preview}) -> (result) => boolean`. Validation consumes the API-unwrapped existing record. The controller stores only one in-memory reviewed preview and local acknowledgment, invalidating them when relevant source changes. No new wire field, request UUID or backend digest.

- [ ] Write tests for full included items and refunds, rejected-history reasons/timestamps, zero-refund versus missing-array states, duplicate item/release IDs, count mismatch, exact money, review invalidation on recipient/date/items change, and non-reviewable evidence disabling submit. Fixture: payments100.00 and50.00, refund35.00, server total115.00; all two receipt references and refund evidence visible. Assert total uses returned text even when row filtering is applied.
- [ ] Add `empty_resolved_result_is_uncertain`, `wrong_recipient_date_collector_is_not_success`, `snapshot_mismatch_does_not_repeat_post`, `terminal_result_requires_reconciliation`, `timeout_keeps_lock`, `failed_readback_does_not_clear_lock`, `verified_submit_preserves_saved_record`, `denial_clears_private_state`. Test matching status/identity/count/item/refund facts rather than truthiness:

```js
const matches=collectorRemittanceResultMatches(expectedReviewedContext);
assert.equal(matches({}), false);
assert.equal(matches({...confirmedRecord,recipient_user_id:otherRecipient}), false);
assert.equal(matches(confirmedRecord), true);
assert.equal(submissionPosts.length, 1);
assert.equal(successToasts.length, 0); // malformed outcome case
assert.equal(guard.locked, true);
```

- [ ] Run `node --test spina_portal/tests/collector-remittance-evidence.test.mjs spina_portal/tests/collector-remittance-confirmation.test.mjs`; record RED on old summary-only/unguarded success behavior.
- [ ] Render complete read-only evidence and local review checkbox without a second total input. Capture reviewed context, send unchanged body through existing guarded mutation pattern, and verify complete returned identity/snapshot before success. A differing snapshot may already be committed: preserve uncertainty and require explicit authoritative reconciliation, not rejection/automatic retry. Implement local history detail/openRecord with sender/recipient/status/timestamps/reason and no recipient action copied into sender controls.
- [ ] Run both suites plus Task1, existing feedback/write-guard/workflow-contract tests. Reproduce `{}` result, visible refund evidence and rejected reason in a synthetic browser. Review/commit `fix(web): verify Collector remittance evidence and confirmation`.

## Task 2 — Preserve drafts after verified actions (C2)

**Files:** Create `collector-route-view.js`; edit orchestration/remittance/workflow/other-area/renewal success hooks and `sw.js`; new `collector-local-refresh.test.mjs`.

**Interfaces:** Implement route handle, onSaved metadata, route-consumer registration and internal `refreshCollectorData(context, change) -> Promise<void>`. One accepted route read per refresh generation, no routine guard replacement.

- [ ] Write `payment_keeps_other_payment_and_remittance_nodes`, `accepted_save_read_failure_is_not_payment_failure`, `changed_revision_blocks_old_draft`, `new_day_does_not_retarget_old_input`, `shared_saved_callbacks_do_not_remount`, `busy_or_locked_guard_survives_refresh`, `unrelated_renewal_photo_survives`. Save one Regular row with a7x7 sibling and another borrower; assert one POST, exact other textarea/file-node retention and no repeat after GET failure.

```js
assert.strictEqual(findOtherNote(), otherNoteNode);
assert.equal(otherNoteNode.value,'Return after lunch');
assert.strictEqual(findRemittanceNote(), remittanceNoteNode);
assert.equal(remittanceNoteNode.value,'For office receipt');
assert.equal(collectionPosts.length,1);
assert.match(savedRowText,/Receipt/);
```

- [ ] Cover Combined/covered-date/correction/remittance/other-area/renewal callbacks, removed authority, obsolete hashes, user focus moved, aborted reads and multiple submit clicks. Run `node --test spina_portal/tests/collector-local-refresh.test.mjs`; confirm reset failures.
- [ ] Extract current ledger/attention/action logic; reconcile nodes by exact entry/client/loan/date/revision, update submission map, clear only submitted editor and mark changed other drafts read-only pending review. Preserve confirmed receipts during read failure; no automatic POST. Notify mounted consumers to invalidate only changed reviewed input. Keep one guard/listener set and safe current view/filter/photo selection.
- [ ] Run Task2 plus `collector-feedback.test.mjs`, `collector-workflows.test.mjs`, `collector-other-area.test.mjs`, `collector-renewals.test.mjs`, `collector-write-guard.test.mjs`, `role-local-updates.test.mjs`. Browser-check notes/photo/save/focus. Commit `fix(web): retain Collector drafts after verified saves`.

## Task 3 — Mobile Needs attention and focus (C3)

**Files:** `collector-route-view.js`, `roles/collector.js`, scoped `app.css`; new `collector-attention-mobile.test.mjs`.

**Interfaces:** Keep route handle/IDs and current model semantics; heading Needs attention retains collector-master-review. Task6 adds direct destinations.

- [ ] Add `attention_cards_have_explicit_labels`, `attention_preserves_exact_amount_and_ids`, `empty_success_differs_from_route_error`, `normal_focus_return_does_not_steal_user_focus`. Pin borrower/area/loan/reason/amount, desktop table and mobile-card class. Capture before screenshots390/320.
- [ ] Run `node --test spina_portal/tests/collector-attention-mobile.test.mjs`; verify RED.
- [ ] Reuse existing mobile-card pattern at current breakpoint (baseline680px); retain readable amounts/text,48px controls, reduced motion and Cancel/error focus. No shrinking type or whole-page horizontal scrolling.
- [ ] Run new suite plus `collector-feedback.test.mjs`, `ui-busy-focus.test.mjs`, `role-daily-work.test.mjs`, `web-ui-hierarchy.test.mjs`; inspect1440/390/320 and keyboard order. Commit `fix(web): make Collector attention readable on phones`.

## Task 4 — Progressive payment detail and Combined Pay (C4)

**Files:** `collector-workflows.js`, `collector-route-view.js`, scoped `app.css`; new `collector-payment-details.test.mjs`.

**Interfaces:** Keep allocationField/followupFields/readFollowup compatible. Add `bindCollectorPaymentDetails(form, {getEntry, getEntryType}) -> cleanup`, controlling visibility/required state only. Combined uses existing preview flags and invalidation.

- [ ] Write `ordinary_payment_is_compact`, `short_regular_or_pass_reveals_reason`, `other_requires_explanation`, `promise_fields_follow_reason`, `hidden_promise_does_not_leak`, `unknown_obligation_keeps_options_available`, `voluntary_no_collection_is_reachable`, `server_error_reveals_invalid_field`, `combined_preview_flags_reveal_required_details`. Use supplied100.00 versus100.00/50.00/150.00 and compare90071992547409.91 versus90071992547409.92 exactly, without Number rounding. Test7x7 short input without invented Regular rules.

```js
assert.equal(readFollowup(form).promised_payment_date,null); // changed away from promise
assert.equal(readFollowup(form).promised_amount,null);
assert.equal(confirmButton.disabled,true); // changed cash/borrower after preview
assert.equal(financialPosts.length,0);
```

- [ ] Run `node --test spina_portal/tests/collector-payment-details.test.mjs`; observe all-visible/stale-field RED.
- [ ] Add compact normal amount/actions and optional Note/options/follow-up. Reveal required exceptions using known exact obligation or server flags, clear irrelevant payload fields and expose invalid required controls. Give Combined identity/cash/choice/preview/actions wide readable regions. Keep reviewed hash, explicit extra choice and Preview/Confirm; no local split or one-tap bypass.
- [ ] Run new suite plus collector-contract/workflow-contract/workflows/feedback/other-area tests. Inspect full/short/extra/pass/promise and Cancel at phone widths and Combined desktop. Commit `refactor(web): simplify Collector payment detail presentation`.

## Task 5 — Independent route and guarded lazy loading (C5)

**Files:** `roles/collector.js`, remittance/route handles, bounded coordinated `app.js`; new `collector-lazy-loading.test.mjs`.

**Interfaces:** Reuse optional mount handle/getSession; keep a small section-loader/cleanup map inside Collector orchestration. Ordinary refreshVisible retains drafts; explicit uncertain reconciliation verifies status before replacing/resetting its guard and explains necessary teardown.

- [ ] Write `route_renders_while_remittance_preview_is_pending`, `route_does_not_wait_for_history_or_activity`, `lazy_section_mounts_once`, `failed_section_retries_locally`, `routine_header_refresh_keeps_drafts`, `header_refresh_cannot_interrupt_financial_write`, `offline_before_lazy_mount_keeps_controls_locked`, `token_refresh_does_not_revive_old_permissions`, `superseded_mount_cannot_register_or_render`. Assert actual request absence for unopened tasks using deferred promises.
- [ ] Run `node --test spina_portal/tests/collector-lazy-loading.test.mjs`; confirm coupled/reset RED.
- [ ] Render shell and route/account independently; lazy-load secondary data and modules. Deduplicate, retry locally and cancel stale mounts; preserve same guard for later controls. Route failure is not an empty route. Ordinary GET/tab switches never reconcile uncertain money; a remittance malformed response stays blocked until explicit verified recovery. Keep existing sharing teardown/eligibility around content changes.
- [ ] Run new tests plus workspace-lifecycle/navigation, session-refresh/boundaries, collector-write-guard, screen-sharing and shell tests. Smoke-check all role hooks. Commit `perf(web): load Collector route independently of secondary work`.

## Task 6 — Route search and exact attention links (C6)

**Files:** `collector-route-view.js`, orchestration and scoped `app.css`; new `collector-route-discovery.test.mjs`.

**Interfaces:** `filterCollectorEntries(entries, {query = '', area = '', status = 'all'}) -> entries`, preserving original identity/order; route handle focusEntry(id). Hide/show nodes, not recreate on search.

- [ ] Write `search_and_area_keep_server_order`, `status_predicates_match_existing_attention`, `two_loans_and_same_names_keep_distinct_ids`, `filter_preserves_unsaved_form_node`, `attention_reveals_exact_hidden_row_without_payment`, `stale_target_never_falls_back_to_name`, `filter_counts_do_not_change_route_totals`. Twelve rows/six clients count as12 loan entries; short paid row may be both recorded and attention.

```js
assert.deepEqual(filtered.map(x=>x.route_entry_id),expectedOriginalIds);
assert.strictEqual(noteAfterFilter,noteBeforeFilter);
assert.equal(financialPosts.length,0);
assert.equal(targetForm.hidden,true);
```

- [ ] Run `node --test spina_portal/tests/collector-route-discovery.test.mjs`; confirm missing navigation/filter RED.
- [ ] Add search/Area/status/Clear filters and loaded counts. Keep full-route financial summary independent. Navigate/focus only exact authorized entries, visibly reset obstructing filters and do not open payment. Missing target gets safe text, not broader lookup.
- [ ] Run new suite plus presenters/workspace-navigation/collector-contract/write-guard and Tasks2/3. Browser-check same-name/empty/offline/long route. Commit `feat(web): add Collector route search and exact attention links`.

## Task 6A — Independent read-only schedule/payoff (C10)

**Files:** Create `collector-schedule-view.js`; edit `collector-route-view.js`, orchestration, scoped `app.css` and `sw.js`; new `collector-readonly-schedule.test.mjs`.

**Interfaces:** `mountCollectorScheduleView({root, api, getSession, getRoute, signal}) -> {open({routeEntryId, loanId, opener}): Promise<void>, refresh(): Promise<void>, close(): void, dispose(): void}`. Route entry/loan must belong to current assigned snapshot. The read controller does not call guard.begin/finish/unlock or mount the editable workflow.

- [ ] Write `route_view_only_can_open_schedule`, `view_never_opens_payment`, `schedule_matches_loan_client_and_scope`, `payoff_and_assessed_projected_penalty_are_distinct`, `review_required_suppresses_confirmed_payoff`, `close_ignores_delayed_response`, `removed_assignment_clears_detail`, `all_reaches_every_same_date_row`, `readonly_refresh_does_not_unlock_financial_guard`. Include as_of/base/updated maturity, contract/frequency, past-due/ADV/promise facts, exact2205.00 and105.00, malformed/missing money,30/120 rows and same-name borrowers.
- [ ] Run `node --test spina_portal/tests/collector-readonly-schedule.test.mjs`; confirm absent viewer/omitted data RED.
- [ ] Add route View schedule under route.view; request only the current Collector schedule endpoint. Validate matching IDs and available required contract fields; render exact server summary and rows, desktop/mobile, Close, Current & upcoming/History/All,30-row increments. Use server as_of_date for view filters, no repayment calculation. Preserve same-date distinct rows and unknown values in All. Keep private/online/stale labels, abort and focus safeguards. Read-only viewing never bypasses an uncertainty lock.
- [ ] Run new suite plus collector-workflow-contract/workflows/write-guard, navigation and privacy tests. Inspect expanded payoff/review cases at1440/390/320 and120 rows. Commit `feat(web): add read-only Collector schedule and payoff detail`.

## Task 6B — Reopen today's exact receipts (C11)

**Files:** `collector-route-view.js`, scoped `app.css`; new `collector-route-receipts.test.mjs`.

**Interfaces:** Implement route handle openReceipt({routeEntryId, transactionId}) and `renderCollectorReceiptDetails(entry) -> string` from current authorized today_receipts. Optional transaction selection must resolve within that row's returned receipt list; never find by name/index after filtering.

- [ ] Write `all_today_receipts_survive_save_toast`, `same_day_multiple_ids_not_collapsed`, `other_collector_receipt_is_readonly`, `no_inferred_balance_or_allocation`, `missing_details_are_not_zero_receipts`, `late_or_removed_row_cannot_open`, `filter_and_refresh_keep_exact_receipt`, `close_restores_correct_row`. Fixture includes two transaction IDs and distinct receipts on one loan, notes, noncontiguous dates, accepted times, lock and cross-collector facts.
- [ ] Run `node --test spina_portal/tests/collector-route-receipts.test.mjs`; confirm missing persistent detail RED.
- [ ] Add labeled read-only receipt disclosure and exact transaction selection. Preserve all returned records/order, existing origin/custody explanation and edit prohibitions. Show only supplied amounts/fields; no Client document endpoint, invented previous balance, lifetime history or print promise. Reconcile lists from verified route refresh and clear denied detail.
- [ ] Run new suite plus Tasks2/6 and collector correction/other-area/feedback tests. Browser-check multiple receipts/long references and keyboard Close. Commit `feat(web): expose saved Collector receipt details on the route`.

## Task 7 — Copy and all loaded history (C7)

**Files:** orchestration, remittance/renewal renderers, scoped `app.css`; new `collector-copy-history.test.mjs`.

**Interfaces:** Known-status display mapping only; visibleLimit30 and Show more+30. Retain server code/identity/order and mounted controls. No backend pagination invention.

- [ ] Write `today_and_route_headings_are_distinct`, `route_count_is_labeled_loan_entries`, `known_renewal_status_is_humanized`, `unknown_status_never_looks_approved`, `history_31st_and_61st_records_are_reachable`, `updates_keep_duplicate_looking_records`, `display_limit_is_not_server_total`.65 records progress30->60->65, with zero/error separate and exact wire enums unchanged.
- [ ] Run `node --test spina_portal/tests/collector-copy-history.test.mjs`; confirm silent slicing/copy RED.
- [ ] Apply Today/route/loan-entry labels,30-row incremental display and loaded counts. Keep C9 history details reachable for every record. Humanize known codes only; preserve warnings and conditional visit/employee/account controls.
- [ ] Run new suite plus collector-renewals/other-area, daily-work/UI hierarchy and remittance suites. Commit `style(web): clarify Collector labels and loaded history`.

## Task 7A — Route renewal badges, amount context and retry (C12)

**Files:** `collector-route-view.js`, `collector-renewals.js`, orchestration, scoped `app.css`; new `collector-renewal-context.test.mjs`.

**Interfaces:** `collectorRouteRenewals(entry) -> requests` matches request.loan_id to entry.loan_id, retaining distinct request IDs. Preserve mountCollectorRenewals cleanup-function return; add optional `registerHandle(handle)` with `{openRequest(requestId): Promise<boolean>, refresh(): Promise<void>}` and unregister on cleanup. Navigation uses current assigned queue and permission; no imported Management/Client controller.

- [ ] Write `renewal_badge_targets_exact_loan_request`, `borrower_level_flags_do_not_attach_to_wrong_sibling`, `missing_flag_identity_is_noninteractive`, `permission_revocation_removes_action`, `requested_approved_offset_net_all_show`, `unlocked_cash_never_looks_final`, `zero_offset_is_valid`, `unknown_money_is_unavailable`, `management_note_and_next_stage_show`, `local_retry_preserves_other_photo`, `badge_open_does_not_recommend_or_confirm`.
- [ ] Pin requested12000.00/approved10000.00/offset1500.00/net8500.00 with/without amount_locked_at. Include same-name clients, two loans, multiple requests, true flag without data, declined/office processing, cash/sign/photo/activation phases and failed GET. Run `node --test spina_portal/tests/collector-renewal-context.test.mjs`; confirm missing contexts/badge/retry RED.
- [ ] Add exact route badge/request chooser and queue-focused navigation. Render labeled returned cash fields, lock state, messages/recommendation/Management note and next allowed action. Never infer net cash or grant signing/receipt authority. Add local retry, stale-generation guards, dirty-editor discard choice only when unavoidable, and exact photo-node preservation for unrelated updates. Keep existing recommendation/physical checkbox/8MB JPEG PNG WebP constraints and server revalidation unchanged.
- [ ] Run new suite plus collector-renewals/write-guard, Tasks2/6 and relevant Client renewal tests for shared invariants. Browser-check amount/badge/error scenarios. Commit `feat(web): connect Collector renewal context and route actions`.

## Task 7B — Local read status and verified Update destinations (C13)

**Files:** orchestration and a bounded Collector activity binder colocated there; shared ui only if necessary; new `collector-notification-actions.test.mjs`.

**Interfaces:** `collectorNotificationTarget(notice, {route, renewals, remittances, session}) -> {sectionId, recordId, routeEntryId?} | null`; `bindCollectorActivity({root, api, getSession, getTargets, navigate, signal}) -> cleanup`. Navigation delegates to verified route receipt/remittance/renewal handles. This is not a global router.

- [ ] Inspect activity_notification_api and each selected producer; record a finite type/metadata-to-destination matrix. Implement only demonstrated fields and accessible targets. Unknown metadata is not a guessed UUID/URL; unsupported kinds stay noninteractive or honestly labeled group-only.
- [ ] Add `mark_read_updates_only_own_notice`, `wrong_recipient_result_is_not_read`, `failed_or_duplicate_click_is_safe`, `read_preserves_other_drafts_and_guard`, `receipt_and_renewal_links_resolve_exact_record`, `unknown_metadata_never_becomes_url`, `denied_target_does_not_broaden_read`, `late_read_after_logout_is_ignored`. Reuse65 records for30/60/65 and unread-among-loaded counts. No action initiates payment/handover/recommendation.
- [ ] Run `node --test spina_portal/tests/collector-notification-actions.test.mjs`; confirm text-only/missing action RED.
- [ ] Add Mark as read via current own-recipient API, exact response verification, local feedback/focus and retry. Use verified target allowlist only. Respect baseline limit-only endpoint (default100/max200); Show more exposes loaded items, not fabricated pages/lifetime totals. Never reset or acquire the financial write guard for a read marker.
- [ ] Run new suite plus Task7, session/navigation/privacy and Client notification regression when shared helpers change. Commit `feat(web): add safe Collector update actions`.

## Task 7C — History, printing and related-role scope disposition (C14)

**Files:** Update this plan's completion/evidence ledger or a bounded documentation section in this PR. Read actual endpoint/permission/output contracts; no product API/grant creation.

**Deliverable:** A matrix containing requested surface, current source/endpoint, exact permission/object scope, current user access, implemented-here versus follow-up, and supporting test/evidence. Include today's receipts, older collections, remittance history/detail, printable route ledger, receipt/remittance copies and Employee work/pay.

- [ ] Map existing sources and grants from executable code, not stale memory. Note route GET's finalization side effects; a live read probe is not authorized evidence.
- [ ] Mark C9–C13 implemented only when their actual UI/tests pass. Record missing older-history/print contracts explicitly, with next required scope decision; no fake output button, Client-only API or silently expanded borrower access. Recipient actions stay with their protected recipient workflow.
- [ ] Coordinate shared Employee work/pay with #487 and verify its Collector mount as regression, not a duplicate implementation. Record unknown/absent notification metadata with the same honest disposition.
- [ ] Review the matrix against the original review/addendum so no finding disappears as a cosmetic-only task. Commit documentation evidence with the next verified product checkpoint or `docs: record Collector output and permission dispositions`.

## Task 8 — Integrated proof and synchronized handoff (C1–C14)

**Files:** Existing tests/build/tooling, this checklist and synthetic test fixtures. `.github/workflows/spina-ci.yml` is a read/run reference, not a target for weakening.

- [ ] Reconcile the coverage table below to actual tests/screenshots, including all original tasks and new insertions. Review every success callback for destructive remount and every failure for false-empty/unlocked behavior. Unsupported C14 scope stays explicit, not falsely complete.
- [ ] Run final full portal checks once then build without repeating them. Verify current package/CI first; baseline Bash commands are:

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

Do not run npm run build again on an unchanged head: it repeats tests. Public-output verification is inline CI, not an imagined checker script. Inspect modules, fixtures, credentials and protected-response caching as well as string patterns.

- [ ] Capture actual built UI at1440/390/320 for eight baseline sections=24 layouts. Add complete remittance preview/rejected detail, read-only schedules30/120, multiple receipts, renewal badge/all amount phases and actionable Updates at the same widths. Exercise200% zoom, keyboard/Close/focus, reduced motion, long names/amounts/references, same-date/same-name records, valid zeros, empty/malformed/error and permission-limited cases. Use synthetic fixtures and block unexpected network/mutations. A screenshot or no-overflow assertion alone is not security/functional acceptance.
- [ ] Prove regular/7x7/ADV/Combined/correction/other-area regression, exact receipt/result matching, malformed-remittance lock, full evidence/refund display, stale preview/revision/date, failed readback, one guard, offline during writes/loads, no unintended duplicate action, retained notes/files, read-only route permission, renewal independent confirmation, own-notification resolution, session/device/grant teardown and private-screen boundaries with mocks only.
- [ ] Integrate shared changes through agreed #485/#487/#488 ownership. Smoke-check Management/Employee/Client and conditional residence/employee mounts; do not claim full visit/payroll/native/physical acceptance. Verify public assets/PWA coherent upgrade and absence of private/test data. Final tested SHA must contain actual integrated shared edits.
- [ ] Push only this branch and inspect exact-head existing CI jobs: **Backend, quality, and security**; **Portal, Flutter, and Android**; **Financial and disposable PostgreSQL**. Record run IDs; no duplicate workflows or unchanged reruns merely for evidence. Pending/Red is not Green and old-head success is not this candidate.
- [ ] Review final code/spec/evidence, update PR from planning-only only after product commits exist, and leave Draft/open/unmerged. No mark-ready, merge, v1.0 tag, Master acceptance, production operations, deployment/delivery or migrations.
- [ ] Sync GitHub, latest Notion and Create State with branch/SHA, task evidence, CI, screenshots, related-role integration, C14/metadata gaps and next action. Disclose failed connectors and preserve exact copyable checkpoint. Owner Red/Green feedback must be verified against live matching commit/jobs.

## Coverage and completion ledger

Every row is pending implementation or assessment at this revision. Replace status with exact evidence only after execution.

| Requirement / task | Coverage | Status |
| --- | --- | --- |
| Task0 | Live refs, original/addendum reconciliation and shared ownership | Pending Codex |
| C1 / Task1 | Remittance skipped/read-only/error/zero/retry and date/recipient checks | Not implemented |
| C9 / Task1A | Full items/refunds, history reason, reviewed snapshot, malformed-result reconciliation | Not implemented |
| C2 / Task2 | Draft/photo nodes, save/read separation, revisions, one guard | Not implemented |
| C3 / Task3 | Phone Needs attention, labels, exact amount and focus | Not implemented |
| C4 / Task4 | Compact payment, conditional promise/extra, reviewed Combined Pay | Not implemented |
| C5 / Task5 | Independent route, guarded lazy tasks, header Refresh/session/privacy | Not implemented |
| C6 / Task6 | Ordered search/filters and exact nonfinancial row navigation | Not implemented |
| C10 / Task6A | Route-view-only full schedule/maturity/past-due/payoff/promise | Not implemented |
| C11 / Task6B | All today's receipts, read-only attribution and exact identity | Not implemented |
| C7 / Task7 | Clear headings/counts/status and30/60/65 loaded records | Not implemented |
| C12 / Task7A | Exact renewal route badge, requested/approved/offset/net/lock/note/retry | Not implemented |
| C13 / Task7B | Own-recipient Mark read, verified destinations and preserved guard/drafts | Not implemented |
| C14 / Task7C | Older-history/print/recipient/Employee boundaries and explicit gaps | Pending assessment |
| C8 / Task8 | Full regression,24 core plus expanded layouts, exact-head CI and handoff | Not run |

## Copyable Codex task

Implement the UPDATED revision2 Collector completion plan in existing Draft PR #486 on `plan/collector-web-ui-completion-20261002`. Fetch the latest head first; do not use only the original20318a5e planning snapshot. Read both revised documents, original review and addendum5943559009, live main/open PRs, frozen Master296, latest Notion and Create State. Follow 0,1,1A,2,3,4,5,6,6A,6B,7,7A,7B,7C,8 in order. Preserve every original task and all new evidence/confirmation, schedule/payoff, receipt, renewal and Update requirements. Use failing behavioral tests before fixes and small passing commits. Coordinate shared code with485/487/488; no duplicate PR/router or overwritten WIP. Keep exact money, assigned-data scope, one guard, online-only writes, confirmed result/identity checks, uncertain reconciliation and borrower/custody/privacy rules. Keep safe draft/File nodes without new storage or stale authority. No invented totals, preview digest/API fields, allocation, permissions, notification targets or Client-only print endpoints. Record older-history/output gaps through Task7C, not fake completion. Update evidence and GitHub/Notion/Create State after meaningful progress. Leave486 Draft/open/unmerged; no mark-ready/merge/deploy/delivery/migrations/production credentials/payments/photo/cash/signing/real capture/Master acceptance. Finish with exact head, results, visual evidence, scope dispositions, blocked/unverified items and next owner action.
