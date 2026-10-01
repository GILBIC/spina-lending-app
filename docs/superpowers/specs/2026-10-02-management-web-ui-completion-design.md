# SPINA Management Web UI Completion — Design and Acceptance

Date: 2 October 2026 (Asia/Manila)

## Status, ownership, and authority

**Planning only.** The owner requested: “Plan everything and create a pr i will make codex do this.” This change packages the complete Management Web re-review for owner-directed Codex implementation. It does not implement the fixes or authorize merging, marking ready, deployment, migrations, live financial operations, credentials, or screen capture. Keep the handoff PR Draft/open/unmerged. The owner will start Codex; do not automatically invoke an agent through PR comments.

Planning baseline: `GILBIC/spina-lending-app`, main `41a13eb59c9cc1b65a0a6a51f3b73db4a0895013`, after merged PR #484. No open PRs were returned at planning preflight. Re-read live main and open PRs before execution; this SHA is the reviewed baseline, not a claim that main never changes. Older PRs #466–#483 are integrated, not outstanding work. Frozen Master #296 stays unchanged.

Authorities, read before asking the owner to repeat decisions:
- [Frozen Master #296](https://github.com/GILBIC/spina-lending-app/issues/296).
- [Integrated release PR #484](https://github.com/GILBIC/spina-lending-app/pull/484).
- [Detailed re-review](https://github.com/GILBIC/spina-lending-app/pull/484#issuecomment-5942508315) and [earlier UI findings](https://github.com/GILBIC/spina-lending-app/issues/448#issuecomment-5942333897).
- [Notion Current Project State](https://www.notion.so/3cd5ade7bef48106b2c2ff97182001dd), latest dated Management UI checkpoint.
- Create State project `69a61c48-f842-44ac-aa11-e987ffec4a36`; semantic search can return older checkpoints, so compare with exact GitHub/Notion evidence.

The re-review used released code/CSS and synthetic records in local Chromium at 1440, 390, and 320px. It was not signed-in production acceptance, a live latency measurement, or a complete accessibility/security audit. The conversation evidence ZIP is optional reference, not a required file in Codex's workspace. Reproduce the scenarios below from source; never invent access to an unavailable artifact.

## Goal and approach

Make Management daily work accurate, state-preserving, readable on phones, and easy to reach without changing business outcomes. Preserve **Today / Clients & loans / Collections / Accounting / People & operations / Account** and the current pink/white visual identity.

Use targeted repairs to existing vanilla JavaScript modules, local task selection, and a small Management-scoped load/cleanup controller. Keep already-mounted task forms in place while switching views. Do not add a frontend framework, global state library, router, persistence layer, virtual-list framework, or backend endpoint. A visual-only patch would leave incorrect totals and lost drafts unresolved; a full redesign would duplicate working functionality and widen risk. The selected approach fixes those causes first and reuses existing components.

Implementation order: truthful portfolio states; local refresh; independent Today loading; Staff mobile/focus; local task navigation; long-list presentation; visual density; integrated verification. Each step must stand on an independently testable commit. Use one branch owner for the shared Management/app/CSS files rather than parallel agents editing those files simultaneously.

## Permanent boundaries

- Web Management is the change surface. Client, Employee, Collector, native Android/iOS, and Desktop are regression surfaces, not redesign targets.
- Keep endpoint paths/query semantics, server-side permissions, exact server amounts/order, and existing role precedence. No new financial arithmetic, inferred balance, penalty, schedule, tax/ECL rule, or total derived from a partial list.
- Financial writes remain online-only through their existing protected workflows. Keep duplicate-submit prevention, uncertain-result lockout, exact retry identity, version/conflict checks, confirmations, and source restrictions.
- Cash Disbursement prepares an expense draft; it does not send money. Employee remains prepare-only; Management posting stays separately permission-gated. `automatic_source_posting=false` remains unchanged.
- Keep one-time credentials, borrower/email stale-selection invalidation, password-reset separation, and identity/permission/logout cleanup. Never persist form contents, credentials, or new authenticated data in localStorage, sessionStorage, IndexedDB, URLs, or the service worker for this work.
- Preserve device approval/revocation safeguards, permanent audit evidence, journal deduplication, immutable posting/reversal behavior, and private-screen restrictions.
- No production writes, real credentials, screen sharing/capture, migrations, deployment/delivery runs, CI weakening, dependency upgrades, changes to Master #296, or expansion of capture-eligible screens.

## R1 — Truthful portfolio states and recovery

The current initial failure falls back to an empty summary and renders four zeros. A later successful Search updates only loan cards, leaving those zeros above real results. Repair both paths.

The existing `GET /api/v1/management/loans` response includes `summary` plus `loans`. In `management_loan_repository.py`, the summary query covers the whole active portfolio; `q`, `status`, `limit`, and `offset` apply to the separate loan-list query. Preserve that distinction. Label the summary **Active portfolio · all clients** and the list **Search results**. A paid-only search or no matching rows must not imply the active portfolio is empty.

On initial load/search/refresh: mark the summary Loading and show dashes, not fabricated zeros. On failure: show dashes and **Portfolio summary unavailable**, with a local retry preserving query/status. On a successful response: update both summary and results from that response. Validate displayed fields independently: missing/null/invalid count or money is unavailable; explicit server zero is valid. Preserve valid exact decimal strings through existing money presentation. Do not coerce missing fields using `?? 0` or `|| 0`.

Use last-request-wins and mount/session guards: a slower earlier search or response after logout must not overwrite the newer view. No success message should imply all records are shown when the endpoint returned a limited list. No new paging feature is required here.

Acceptance: failed initial read, successful recovery with ten sample loans, genuine all-zero success, missing summary/field, paid/no-match searches with nonzero portfolio summary, partial list, rapid searches, and late response after abort. Expected portfolio values come from fixture summary, never the sample cards.

## R2 — Preserve unrelated work across saves and refreshes

Ordinary navigation already preserves values; retain that behavior. Support save and Renewal review rebuild Management; Staff invitation uses the same pattern in current source. Replace these full remounts with affected-region refreshes. Clear only the successfully submitted form where appropriate. Keep unrelated draft nodes, search/status selections, Office intake references, local selected tasks, focus, and scroll context.

A successful mutation followed by a failed read must say the save succeeded but refreshing failed; do not present it as a failed mutation or offer a new duplicate submission. Refresh dashboard/queue counts from authoritative reads; never decrement or infer global totals locally. Refresh only the changed row when possible; preserve unsent text in other queue rows.

Routine data refresh, including the Management header Refresh action, must not silently discard drafts. Refresh read-only summaries/lists and relevant server-state checks while retaining unrelated inputs. Where an existing protected editor necessarily resets its own controls, require an explicit discard choice for dirty input; do not serialize every form into a generic cache. Logout, identity/device change, authorization change, or expiry must still dispose old state. Same-identity token rotation must not lose the existing Cash Disbursement uncertain-request recovery.

Acceptance: input a search value and intake reference; navigate; submit mocked Support, Renewal, and Staff invitation independently; values survive each save. Also cover another unsent support response, failed post-save refresh, manual Refresh, duplicate submission, and disposal.

## R3 — Load Today without waiting for other groups

Render the shell and placeholders immediately. Load account/profile and dashboard information independently; dashboard failure should not remove navigation or break Account. Today must not await loan operations, portfolio lists, statements, journals, trial balance, audit, staff, or other non-Today task loads. Use dashboard-provided queue metrics where available. Otherwise use neutral links or an explicit unavailable count, not zero from an unloaded queue.

Initialize non-Today groups/tasks on first activation, not merely hide already-eager data loads. A failing task gets a local retry; other groups remain usable. Deduplicate simultaneous activation loads. Keep loaded editor DOM during navigation. Scope load state, listeners, and results to the mounted account/permission session, and dispose all registered child cleanups on abort. Use current authority before delayed mounts; permission revocation or a new account cannot inherit a late response.

Acceptance: hold only loan operations indefinitely and confirm Today is usable; also hold accounting/staff/audit. Visit a group twice without duplicate mounting/listeners; fail one group and recover locally. No speculative hidden-screen refresh should recreate an unrelated form.

## R4 — Staff mobile readability and device focus

Reuse the existing `mobile-card-table` pattern below its current 680px breakpoint. Add explicit labels and a Staff-scoped class rather than changing all tables. On desktop retain the seven-column table. On phones prioritize name/status, role/device count, then a readable Manage devices or View account action. Username/email/date remain available without narrow character stacks. Do not shrink typography or touch targets to force columns to fit.

Preserve account IDs, selected-row state, exact server device count, permission-dependent action, and protected device reloads. Opening details moves focus to a focusable panel heading/Close control after current selection resolves, unless the user deliberately moved elsewhere during loading. Close returns focus to the originating visible control, or a sensible Staff heading if it no longer exists. Stale responses never steal focus. Busy controls and permission/error panels retain correct Close/recovery behavior.

Acceptance: desktop plus 390/320px; long names/emails; no device permission; rapid account selection; slow read with user focus moved; Close; mutation failure. No horizontal document overflow alone is not visual acceptance: manually inspect names, status, dates, and buttons.

## R5 — Local task navigation and precise destinations

Keep the six top-level labels and IDs. Add small permission-filtered local navigation within the three dense groups. Use the existing hide/show approach; do not create a second workspace or duplicate workflows.

| Group | Local tasks, default first permitted |
| --- | --- |
| Clients & loans | Portfolio; Office applications; Renewals; Payment evidence; Client accounts |
| People & operations | Staff & devices; Areas; Employee work; Client support; Alerts & audit |
| Accounting | Financial statements; Journal & Trial Balance; Cash Disbursement; Accounting workflows |

Office applications contains the existing four-step intake/CIF/application/first-loan workflow unchanged. Accounting workflows contains existing capital/source/tax/ECL/close controls unchanged; do not invent an Accounting Overview calculation. Preserve journal/trial-balance subviews, collection-action subviews, and existing guided Office reference revalidation.

All accessible destinations must be keyboard-operable with a clear selected state. Remember task choice only in the current mounted session. Open known alerts to the exact permitted local task: staff_devices -> Staff & devices; renewals -> Renewals; support -> Client support; client_registrations -> Client accounts; financial_accounting -> Accounting workflows. For remittance_review, resolve the existing authorized remittance surface instead of claiming a read-only history panel is a review action. If a precise permitted target is absent, show a read-only item or an honestly labeled group destination. Unknown codes remain noninteractive. No arbitrary URL, record ID, or permission inferred from a label.

Local navigation can change private content without changing the top-level ID. Before hiding/replacing a capture panel, stop or invalidate active/preparing capture through existing controls; re-evaluate eligibility after the change. Keep exact `data-screen-share-section` boundaries; never move a capture marker onto a whole group to make tests pass. Use mocked lifecycle tests, not a real capture session.

## R6 — Shorter visible lists without losing evidence

Retain all authorized loaded records and their server order/identity. No deduplication, deletion, new backend filtering contract, or inference about unloaded records.

Device details: retain All/Active/Pending/Revoked and counts. On first opening an account, default to Pending if any pending devices exist, otherwise Active if any active devices exist, otherwise All. Preserve the user's explicit filter through a status mutation/refresh, including an empty result. Render/show the first 10 matching rows and a **Show more** control adding up to 10; expose displayed/loaded counts. All eventually exposes every loaded record, including unknown statuses. Keep actions keyed to original identity, not a reindexed filtered subset.

Audit: use compact rows and optional expanded facts; start with 10 matching returned events and Show more in blocks of 10. Preserve severity, timestamps, maker/checker/reason, domain chips from visible_domains, the protected `window_days=30&limit=100` request, and permanent event identity. Distinguish loaded/visible counts from server authorized total and time window. Filter changes reset the display cap, not the data. Alerts and history remain distinct.

Acceptance: 36 devices with exactly two Pending; inspect all records via All/Show more; mutate after filtering and prove correct device ID. Audit snapshots of 0/12/100 events, duplicate-looking events, unknown domain, total greater than loaded count, and repeated filter/show-more actions.

## R7 — Targeted visual polish

Today: retain Portfolio and Collections information; prioritize nonzero Needs attention and useful work actions. Compact successfully loaded zero queues into a quiet summary/disclosure that still exposes their exact labels/counts. Unknown/unavailable is never folded into “nothing to do.” Do not invent charts or performance metrics.

Accounting: selecting the group must not mount/fetch the full Cash Disbursement editor unless that task is selected. Preserve the does-not-send-money explanation, Prepare draft label, pending recovery, receipt requirements, and separate journal posting. Give Purpose and Supporting evidence full-row width within the existing form layout; no file uploader or request-schema change is required.

Account: constrain profile content to a readable maximum width (target 720px, fluid on phones). Keep Workspace and Additional access distinct, and keep My password separate from higher-risk account reset. Do not hide actual authority cosmetically.

Shared styling: reuse colors, 48px baseline controls, spacing tokens, readable font sizes, reduced-motion behavior, and action hierarchy. Scope Management-specific density changes. Remove redundant nesting/copy only when it does not remove required warnings or status context. Verify Client/Employee/Collector screens after any shared CSS/module change.

## Release evidence and completion

Every implementation task requires a failing behavioral test before its fix, passing focused tests afterward, and a checkpoint tied to its exact commit. Existing presentation assertions may change to reflect intentional lazy/local navigation, but permission, identity, uncertainty, and privacy assertions must not be weakened.

Final evidence includes all six sections at 1440, 390, and 320px (18 layout samples), long and empty data, error/recovery, keyboard and 200% zoom checks, real browser screenshots, console results, and exact-head existing CI. Visual data is synthetic. Browser-automation limitations must be reported; a DOM string test is not a screenshot or production acceptance.

Before review completion, reconcile every requirement R1–R7 to tests and evidence; leave unverified items unchecked. Synchronize GitHub, Notion, and Create State with branch, SHA, outcomes, limitations, and next action. No merge/deploy or Master acceptance checkbox is authorized by completion of this plan.

Implementation checklist: [2026-10-02-management-web-ui-completion.md](../plans/2026-10-02-management-web-ui-completion.md).
