# SPINA Collector Web UI Completion — Design and Acceptance

Date: 2 October 2026, Asia/Manila.

## Status and authority

**Planning-only Codex handoff.** The owner requested: “Plan everything and create a pr i will make codex do this” immediately after the Collector website review. This document plans all findings in that review. The owner will start Codex; publishing the plan does not implement fixes or authorize automatic agent invocation, marking ready, merge, delivery, deployment, migrations, production credentials/transactions, or real screen capture. Keep the handoff PR Draft/open/unmerged until separately instructed.

Reviewed baseline: `GILBIC/spina-lending-app` main `41a13eb59c9cc1b65a0a6a51f3b73db4a0895013`, after merged PR #484. At planning preflight the only open PR was Management planning PR #485, head `7fdf54edad8186bd0dca6d7209aeac68dbce48e1`. These are snapshots, not assumptions for future execution.

Read before asking the owner to repeat decisions:
- [Collector review and reproductions](https://github.com/GILBIC/spina-lending-app/pull/484#issuecomment-5942786091).
- [Frozen Master #296](https://github.com/GILBIC/spina-lending-app/issues/296), unchanged by this work.
- [Integrated release #484](https://github.com/GILBIC/spina-lending-app/pull/484).
- [Separate Management handoff #485](https://github.com/GILBIC/spina-lending-app/pull/485).
- [Notion Current Project State](https://www.notion.so/3cd5ade7bef48106b2c2ff97182001dd), latest dated Collector checkpoint.
- Create State project `69a61c48-f842-44ac-aa11-e987ffec4a36`; check dates because semantic search can return older plans.

The prior review used exact-release assets, synthetic API responses, and local Chromium: eight sections at 1440/390/320px, plus focused error/loading/offline/draft checks. It was not production sign-in, measured live latency, a real payment, residence/photo/attendance acceptance, or a full security/accessibility audit. `SPINA_Collector_UI_Review_41a13eb5.zip` is an optional conversation artifact, not a dependency guaranteed to exist in Codex. Reproduce from repository source when absent.

## Goal, approach, and scope

Make everyday Collector work accurate, quick to locate, readable on phones, and resilient to refresh without discarding unrelated notes. Preserve the current pink/white identity, route-first layout, authorized destinations, area order, distinct Regular/7x7 rows, and Payment versus Unable to pay actions.

Selected approach: targeted repairs to existing ES modules. Extract a bounded remittance controller and a route view/controller from `roles/collector.js`; keep orchestration in that file and reuse existing financial helpers. A CSS-only patch would leave false states and lost drafts. A framework rewrite would duplicate working flows and interfere with PR #485. Neither is selected.

Scope includes truthful remittance states; local success refresh; phone attention cards; progressive payment/Combined Pay fields; independent route loading; route search and exact-row navigation; terminology/history display; integration evidence. No new lending product, backend endpoint, collection allocation engine, native app redesign, offline outbox, or generic state framework.

## Coordination with Management PR #485

Create this Collector handoff from current main, not stacked on the Management docs-only branch. Keep separate PR ownership and do not add Collector tasks to #485 or edit its plan. Role-specific code can proceed independently. Before touching `app.js`, `ui.js`, `app.css`, or `sw.js`, inspect the live #485 diff and record one owner/integration order for overlapping sections. Default: reuse Management's verified optional shell lifecycle hook if already available; otherwise add only the small optional hook described in the implementation plan and publish its interface for #485. Do not build two parallel routing/refresh systems or import an unmerged Management task module. Do not cherry-pick/rebase somebody else's WIP without agreed coordination. Resolve shared-file overlap before those edits, while continuing nonoverlapping work. Final integration must preserve both workstreams and have exact-head regression evidence.

## Permanent boundaries

- Keep current endpoint paths, request fields, query semantics, server permissions, device identity/sequence, route revisions, receipt verification, server allocation hash, correction locks, recorder attribution, remittance custody, and renewal handover confirmations.
- Collector financial writes remain online-only. Preserve the one-workspace write guard, duplicate-submit protection and uncertainty lock. A successful read or filter change must never unlock uncertain writes. No automatic financial retry/outbox or regenerated identity for an ambiguous result.
- Distinguish a routine data refresh from the existing explicit authoritative reconciliation/remount path. Normal success refresh keeps the same guard and unrelated draft nodes. Offline/uncertain recovery may require the established safe teardown; do not weaken it to promise universal draft preservation.
- Exact authoritative amounts remain decimal text. Do not derive remittance totals from route rows, history, or filters; do not change Regular/7x7 calculations, due dates, PASS/ADV policy, accounting or penalties. Exact comparison of entered amount with a supplied obligation may control disclosure only, never decide financial allocation.
- Drafts exist only within the current mounted session. No new localStorage/sessionStorage/IndexedDB/URL/service-worker persistence. Logout, identity/device/permission changes and session expiry clear old data; retained drafts do not extend password/one-time-secret lifetime.
- Preserve server-reviewed Combined Pay and borrower extra-allocation choices. This is not a literal one-tap payment implementation or permission to remove Preview/Confirm. No automatic promise, reason, or extra allocation.
- Private-screen/capture boundaries remain unchanged. Stop/invalidate existing sharing before replacing a captured panel; no new capture markers or expanded eligibility. Test with mocks only.
- No backend/schema/migration/financial-policy change, dependency upgrade, CI weakening, production operation, real capture, deployment/delivery, Master #296 rewrite or owner-acceptance checkmark is authorized.

## C1 — Truthful Remittance state and recovery

Current defects: a missing route date skips preview but renders four zero metrics; a history-only Collector sees the same false summary; recipient failure is shown as an empty eligible list. These are presentation failures, not proof of corrupt balances.

The existing `remittance_api.py` requires `remittance.create` for both `/api/v1/collector/remittances/preview` and `/recipients`. Respect this: history-only permission uses the existing history endpoint and no preview/recipient call. Do not broaden access.

Represent preview, recipients, and history independently. States: `idle`, `loading`, `ready`, `error`, `unavailable`, `not_permitted`. A ready empty recipient array differs from a failed recipient read. A skipped read is not ready. Missing/invalid required summary fields are unavailable, never zero. Ready decimal `'0.00'` and integer zero are valid.

Copy/behavior:
- Route date unavailable: **Route date unavailable — refresh the route to load a remittance summary.** Do not invent today's date from the browser.
- Read-only permission: **Remittance history only**; explain that preparation is not assigned. Do not render a fake cash preview or submit form.
- Preview failure: **Remittance summary unavailable** plus local Retry summary.
- Recipient failure: **Recipients could not load** plus Retry recipients.
- Successful empty recipients: **No eligible remittance recipient is available.** No submit.
- History failure: local error/retry; it must not erase an independently valid preview, or claim empty history.

Submit requires current permission, online/unlocked guard, known route date, matching ready preview date, valid exact required summary values, a positive authoritative total under the existing rule, and a selected recipient from the current successful list. New route/date/collector or a known collection change invalidates the old preview before submit. Preserve typed note and still-valid recipient while reloading; an invalidated recipient must require reselection rather than silently sending to another person. Late responses cannot overwrite a newer date or account. Keep existing server validation and wire body unchanged.

## C2 — Local success refresh, draft retention, and financial safety

After a verified Payment/Unable to pay/covered-date/correction/Combined Pay/other-area/renewal action or confirmed remittance success, refresh only affected data using existing reads. Remove ordinary `mountCollectorWorkspace` calls from successful action paths. All shared `onSaved` paths must be reviewed, not only the first payment button.

Refresh the authoritative route snapshot once, update the entry map used for later submissions, Today/attention display, and invalidate/reload remittance preview as needed. Reconcile existing rows by `route_entry_id`, with client/loan/date/revision checks; do not reindex actions by filtered position. Clear only the confirmed submitted editor. Preserve other form node identities, notes, filter/search selection and current section. Keep one set of listeners.

Retained inputs are not retained authorization. If another row's revision, ownership, status, collection date or collectibility changes, keep its unsent note visible but make that editor read-only with **Route changed — review again**. Never silently attach the new revision/date to an old reviewed draft. Removed/unauthorized rows must not remain actionable or expose now-forbidden data. Ordinary same-authority revision changes can retain text for review; identity/permission changes dispose it.

Combined/schedule/cross-area/renewal modules currently capture route data and reviewed previews. Give mounted consumers a narrow snapshot invalidation callback; invalidate old review hashes/schedule selections on authoritative changes without destroying unrelated notes. Require explicit reload/review before a changed draft submits. Keep the existing cleanup-return convention.

A verified saved result followed by refresh failure is **Saved; latest route/summary could not refresh**, not a failed payment. Preserve receipt evidence and disable a repeat of the committed action. Block financial actions that lack current required data until safe read recovery; do not automatically POST again. Unknown/5xx/unverified results retain existing guard locking and reconciliation behavior.

Focus returns to the saved row/status or a visible route heading only if the user has not moved elsewhere. No automatic jumping to another borrower or opening a new payment. Normal header Refresh preserves safe drafts; during an active write it is blocked/deferred. Explicit offline/uncertainty reconciliation and logout retain their stronger teardown rules, clearly announced rather than disguised as routine refresh.

## C3 — Readable Needs attention and accessible feedback

Keep its desktop table; below the existing mobile-card breakpoint use labeled cards. Display borrower, area, loan type, reason and exact amount without fragmented currency/digits. Use a clear action **Open loan in route** after C6, not an implicit financial action. Rename the visible **Master Review** heading to **Needs attention**, retaining `collector-master-review` for compatibility.

Reuse current focus styling, baseline 48px controls, explicit labels, visible error feedback and reduced-motion behavior. No text shrinking to fit five columns and no global table rewrite. Route cards already work and should not be rebuilt solely to match Management. Zero attention rows after a successful complete route read may show the existing clear state; a failed/missing route cannot.

## C4 — Progressive payment details without changing the contract

Normal Payment first exposes borrower/loan identity, the entered amount and Save official entry/Cancel. A quiet optional Note disclosure remains available. Offer a clear **Payment options and follow-up** disclosure so exceptions are always reachable even when automatic inference is impossible.

For known exact amounts, compare only to the server-supplied current unpaid obligation to decide visibility. Missing/malformed obligation is unknown, not zero; keep options accessible and let existing validation decide. Do not use display fallback daily amount to declare an obligation satisfied.

- Regular short payment or Unable to pay expands the reason section; maintain all current required/allowed follow-up rules.
- Selecting Other requires its existing explanation. Selecting Promised to pay later reveals and requires date/amount under the existing contract. Other reasons submit null promise fields; stale hidden promise values never leak into requests.
- Extra cash reveals allocation choices; retain explicit borrower intent and supported No Collection voluntary option. Do not automatically choose advance or principal reduction.
- Switching type/amount/reason updates `hidden`, `required` and submission semantics consistently. A server validation error must reveal and focus the relevant section; no invisible required control prevents correction.
- Retain in-session text while toggling details where safe, but submit only currently relevant fields through existing builders/readFollowup. Cancel retains established reset-and-return-focus behavior.

Combined Pay keeps Preview server allocation and Confirm reviewed payment. Give identity/total-cash/extra-choice wide rows, preview a full-width region, and readable action buttons. Use server preview flags `regular_past_due_followup_required` and `extra_choice_required` to expose missing detail; do not calculate the split locally. Any meaningful edit invalidates preview; changing only disclosure visibility must not approve or mutate a draft. Keep exact reviewed hash/identity verification. Covered dates/corrections retain their separate saved-schedule/locked-entry flow.

## C5 — Today/route independent of other screens

Render the shell/navigation promptly and start route and account reads independently. Display Today and assigned route once the route is available, without awaiting notifications, history, preview, recipients, renewal lists or employee tools. Hold a remittance preview indefinitely in the test: route work must still render. Route failure blocks only route-dependent financial work, with honest state; safe unrelated reads remain usable.

Load secondary screen data/module mounts on first activation, deduplicate in-flight loads and retry locally. Merely hiding eagerly fetched screens is not sufficient. Preserve loaded editor DOM during ordinary navigation, but invalidate changed reviewed financial inputs per C2. Keep all existing authorized destinations reachable; do not impose Management's six-group menu on Collector.

Use mount-owned cancellation/generations and a current-session getter. Do not let the copied mount context retain old permissions after token refresh. Navigation, refresh, offline/guard lock and every later lazy-mounted control must all respect the same workspace guard. Only explicit safe recovery creates a replacement guard; an ordinary task load cannot. Financial controls remain blocked offline even if navigator changes while a read is pending. Rapid switches, date rollover, logout and role/device revocation cannot resurrect old views or steal focus.

## C6 — Find an assigned borrower and open the exact loan

Add route-local text search over existing displayed borrower/loan identity fields, an Area selector from authorized route data, and a status filter: **All / Needs attention / Recorded today**. Default All; no new backend query, permission, sorting, pagination engine, or inferred collection status. Needs attention uses the existing unresolved predicate; Recorded today uses `processed_today === true` and may overlap with attention for short payments.

Filter the currently authorized loaded snapshot only. Preserve area order, row order, distinct Regular/7x7 IDs and edited row DOM. Show **Showing X of Y loaded loan entries**; area/Today/full-route counts remain based on the unfiltered authoritative snapshot and existing presenter semantics. Do not label it a distinct-client count or recalculate financial totals from visible matches. Distinguish No matches from Route unavailable; Clear filters restores all loaded entries.

An attention action navigates through the existing shell to `collector-route`, reveals the exact permitted `route_entry_id`, scrolls/focuses its identity/heading, and leaves payment unopened. If filters hide it, visibly clear the obstructing filters; show current filter state. Never guess from name alone (two borrowers may share names). A stale/missing/unauthorized ID shows **This route entry is no longer available. Refresh the route.** No write or out-of-route fetch occurs. Search/filter changes preserve drafts and do not unlock financial entry.

## C7 — Terminology, hierarchy, and complete returned history

Today overview heading becomes **Today**; the separate route remains **Today's route / Assigned area ledger**. Rename **Route clients / loans** to **Route loan entries**. Do not add an invented unique-client figure or alter expected-total logic as cosmetic work.

Remittance history and Updates keep current ordering and initially show up to 30 returned records. Add **Show more** in batches of 30 until all authorized returned items are accessible, with Showing X of Y loaded records. Do not claim all-time completeness, invent a server total/page cursor, or silently drop duplicate-looking audit/activity entries. Empty/error/permission states remain distinct. More rows never replace unrelated editors or change money summaries.

Humanize known renewal proof/status values, including `not_submitted` -> **Not submitted**, using explicit labels; unknown codes get a neutral readable fallback, not a successful/approved label. Keep original status values in API decisions and every release evidence/custody confirmation. Purposeful Collector-scoped spacing, readable Combined Pay widths and quieter secondary actions use existing tokens. Other-area, residence/visit, employee and account features are preservation/regression scope, not new workflows.

## C8 — Acceptance and handoff

Every stage uses failing behavioral tests before the fix, focused passing tests, a reviewable commit, and an exact-SHA checkpoint. Do not satisfy safety tests by weakening assertions. Real browser evidence must use actual modules/build assets and synthetic responses; no real payment, photo upload, capture or production credential.

Minimum layout matrix: Today, assigned route, Needs attention, Collections & corrections, Remittance, Other-area collection, Renewal handover, My account at 1440/390/320px = 24 samples. Also inspect changed Updates presentation, keyboard/200% zoom/reduced motion, long names/amounts, same-name clients, empty/large lists, and error/recovery. Smoke-check conditional residence and employee surfaces without claiming full operational acceptance. No-overflow or DOM string checks alone are not visual acceptance.

Final evidence covers ordinary and uncertain writes, offline during a request, stale revision/date, post-save read failure, field visibility transitions, exact filtered IDs, guarded lazy loads, logout/role changes, all-role shared-shell/CSS regression, PWA coherence and no public test fixtures. Use existing three required CI jobs on the final implementation head; do not duplicate unchanged validation. Green docs-only CI does not prove these fixes.

Synchronize this PR, Notion and Create State with exact branch/head, completed/pending tasks, commands, CI and evidence limitations. Report failed connectors rather than claiming synchronization. Keep the PR Draft/open/unmerged and leave owner acceptance and deployment to separate instruction.

Implementation checklist: [2026-10-02-collector-web-ui-completion.md](../plans/2026-10-02-collector-web-ui-completion.md).
