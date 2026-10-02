# SPINA Employee Web UI Completion — Design and Acceptance

Date: 2 October 2026 (Asia/Manila).

## Status and authority

**Planning-only, owner-started Codex handoff.** The owner requested “Plan everything and create a pr i will make codex do this” after the Employee UI/missing-function review. This document covers every finding from that review, including a separately gated reports-scope assessment. Creating this plan does not implement changes or start Codex. Keep the handoff PR Draft/open/unmerged; no mark-ready, merge, delivery, deployment, migrations, production credentials/transactions, actual screen capture, or owner-acceptance changes are authorized here.

Reviewed baseline: `GILBIC/spina-lending-app` main `41a13eb59c9cc1b65a0a6a51f3b73db4a0895013`, following merged PR #484. At preflight, separate Management #485 and Collector #486 planning PRs were open. Recheck their actual heads and diffs before execution; the baseline is not an assumption about future main.

Read first:
- [Employee review and evidence limits](https://github.com/GILBIC/spina-lending-app/pull/484#issuecomment-5942998232).
- [Frozen Master #296](https://github.com/GILBIC/spina-lending-app/issues/296), unchanged by this plan.
- [Release #484](https://github.com/GILBIC/spina-lending-app/pull/484), [Management #485](https://github.com/GILBIC/spina-lending-app/pull/485), [Collector #486](https://github.com/GILBIC/spina-lending-app/pull/486).
- [Notion Current Project State](https://www.notion.so/3cd5ade7bef48106b2c2ff97182001dd), latest Employee checkpoint.
- Create State project `69a61c48-f842-44ac-aa11-e987ffec4a36`. Older memory saying Employee APIs do not exist is superseded by current source.
- Existing `docs/superpowers/specs/2026-09-20-employee-api-contract.md` and its executable backend models/repository.

The prior review inspected synthetic data in local Chromium: 11 sections at 1440/390/320px and focused forms/error/draft tests. It did not establish signed-in production, physical cash handover, real payroll/payment, complete office/backup-role/device acceptance, or a complete security audit. The optional conversation ZIP `SPINA_Employee_UI_Review_41a13eb5.zip` may not exist in Codex; reproduce the documented scenarios from the repository instead of depending on it.

## Goal and chosen approach

Complete the existing Employee experience: truthful actionable workday information, safe remittance decisions, retained unfinished work, readable work/pay records, connected office-case steps, and usable payslip output. Keep current branding and working APIs. Attendance, leave, tasks, advances, shortages, payroll data/history, Office modules, cash-draft preparation, accounts and permissions already exist.

Use targeted ES-module changes and scoped presentation helpers. A CSS-only pass misses rejection/draft/recovery gaps; a new HR system or global state framework duplicates protected logic. The selected approach keeps the current Employee Operations controller and financial contracts, separates its editor from refreshed read regions, and reuses the shared shell lifecycle rather than building another router.

This work changes Web Employee presentation and narrowly shared components, not lending/payroll formulas or native apps. Broader borrower reports are assessed explicitly in E9; they are not silently added to Employee authority.

## Shared-file coordination

Create this PR from main, separately from #485/#486. Do not edit those plans or branches. Before editing `employee-operations.js`, shared Office modules, `remittance-review.js`, `app.js`, `ui.js`, `app.css`, `presenters.js`, `cash-disbursement.js`, or `sw.js`, inspect both live PR diffs and record one integration owner/order for overlapping hunks. Employee-only tests and modules can proceed independently.

Reuse an equivalent verified optional shell registration/navigation/refresh hook when available. Do not import an unmerged Management-specific task module or build three competing refresh systems. Do not cherry-pick/rebase another executor's unreviewed work or overwrite it. Shared fixes must preserve Management/Collector behavior, grants, recovery and cleanup. A small optional Employee presentation mode may organize the shared work/pay component without forcing a new layout on other roles.

## Permanent boundaries

- Exact server money, versions, IDs, actor/device identity, per-record `allowed_actions`, capabilities and existing permission checks remain authoritative. UI hiding is not authorization.
- No new financial/payroll/leave/attendance calculation engine, backend endpoint, schema change, role grant, dependency/framework, generic cache or persistence layer. Never infer wages or remittance totals from visible rows.
- Employee Operations mutations and financial actions remain online-only on Web. Preserve stable `request_id`, domain `id`, `expected_version`, exact retry payloads and actor/device-bound result recovery. No automatic replay/outbox; absence of `last_result` is unconfirmed, not failure or success.
- Routine refresh must not erase dirty input, but retained input is not renewed authorization. Stale versions, lost grants, identity/device changes, denied access and logout still invalidate commands and clear private state.
- No new localStorage/sessionStorage/IndexedDB/service-worker storage of drafts, payroll snapshots, case references or credentials. Do not extend the lifetime of one-time passwords. Printing is user-initiated and private, not a new public artifact route.
- Cash Disbursement is an expense-draft preparation, not a transfer or posting. Owner salary payments/shortage decisions/setup, independent approvals and `automatic_source_posting=false` remain unchanged. Do not add payment-proof review to Employee by changing its default Management grant.
- Preserve remittance item/refund review, physical receipt confirmation on acceptance, immutable financial evidence, locked first-loan documents and narrow screen-sharing boundaries. No actual capture or production operation for tests.
- Keep existing work/Office destinations reachable. Do not discard returned history, silently classify unloaded work as empty, weaken tests, rerun unchanged CI for ceremony, or mark Master #296 acceptance from synthetic UI checks.

## E1 — Complete protected remittance decisions, retry and focus

Retain the current accept endpoint and `acceptedResult` contract. Add **Reject remittance** beside, but visually distinct from, acceptance. Require a current verified submitted remittance belonging to the exact recipient, `remittance.view` plus `remittance.receive`, full item/refund review acknowledgment, and a trimmed reason of 1–500 characters. Rejection must NOT require asserting that cash was physically received; acceptance still requires both review and physical-count confirmations.

Call existing `POST /api/v1/remittances/{remittance_id}/reject` with `{review_acknowledged:true, reason}` and `financial:true`. The response is the remittance record, NOT the notification-shaped accept response. Verify matching remittance/collector/recipient IDs, rejected status, rejection reason, rejected-by actor and timestamp against the actual API projection. Refresh notifications from the protected read; never fabricate a new notification/custody outcome or decrement an inferred global total.

Accept/reject share one submission lock. A verified save followed by a failed refresh reports **Rejection saved; notices could not refresh**, not a failed write. Uncertain, malformed or 5xx outcomes lock repeat decisions until authoritative reconciliation; no automatic rejection retry. 401/403 clear private review; stale/non-submitted/wrong-recipient detail cannot submit. Local retry reads exact current records and never unlocks an unresolved mutation merely because a GET returned.

Add retry for initial notification failure and detail failure. Errors, no pending notices, and no permission remain distinct. Open review focuses its heading or first review control if the user has not intentionally moved; Close restores the exact opener or a visible notices heading. Late results never steal focus. Clear reason/acknowledgments on selection change/close/disposal. Preserve the full item and refund list.

## E2 — Preserve drafts without weakening Employee Operations recovery

Routine **Refresh employee records**, header Refresh, attendance success, task updates and other unrelated successes must retain an open leave/shift/advance/editor's fields, dynamic rows, selected view and focus. Employee Support already updates locally; preserve that behavior.

Keep the active editor DOM stable while replacing read-only regions where possible. Store any necessary small editor state in mount memory, keyed by action, employee, stable record ID and original version—not collection index. Only a verified success for that exact submitted editor clears it. Opening another editor or leaving the page through an action that really discards work requires a clear discard choice; logout/authority loss clears without retaining private drafts.

Refresh capabilities/allowed actions and records independently of draft text. When the edited record/version changes, retain text as an explicitly stale draft but block submitting it until the user reloads/reconciles against the new record. Do not silently substitute a newer expected_version. Unauthorized/removed records clear private data instead of retaining a stale draft.

Keep the immutable pending command separate from editable draft state. Unknown outcomes retain exactly the original command and request identity. Check saved result uses `workspace?request_id=...`; unmatched/null results remain unresolved. The same unchanged retry remains an explicit protected action, not a routine refresh side effect. Same actor/device token renewal must not lose an unresolved command; a different account/device/permission scope must not inherit it. Attendance IDs, captured time, sequence and predecessor never regenerate during retry.

## E3 — Independent loading and honest refresh state

Render navigation and task placeholders immediately. Today/workday information and account loading do not await activity notifications, Support, remittance notices or Office modules. Load secondary tasks on first activation and use local loading/error/retry, retaining mounted editor DOM on ordinary navigation. Reject late results from old mounts/identities; deduplicate concurrent activation, not unrelated protected requests.

Use the existing Employee Operations workspace read as the one source for work/pay and Today's summary. Do not fetch it a second time just for dashboard cards. Mount Cash Disbursement only when opened; its later capability/recovery read is legitimate and must remain. This avoids the duplicated eager startup without introducing a cross-module global cache. Any request with `request_id` is recovery-specific and must never be coalesced with an ordinary workspace read.

Header Refresh delegates to a current mount-owned handle. Routine refresh preserves unrelated drafts. Pending-write reconciliation stays explicit. No unloaded queue becomes zero and no old data is presented as freshly verified. Session/device/permission changes still tear down the prior scope. Coordinate the optional shell hook with #485/#486 and retain existing privacy hooks before DOM changes.

## E4 — Focused work/pay navigation and readable records

Keep `employee-operations` as the stable main destination, labeled **My work & pay**, with local views **Workday / Tasks / Time off / Advances / Payslips / Other records**. Add a direct **Payslips** shortcut to the same existing Payslips view, not a second mount/read. Keep create actions visible even when their collections are empty. Extra reviewer/setup actions appear only from current capabilities/allowed actions; never omit authorized work simply because it is not personal self-service.

Map attendance/day review and effective schedule to Workday; tasks to Tasks; leave/shift/overtime/conversion requests, leave balances and leave ledger to Time off; advances/installments/repayments to Advances; payroll, actual payment evidence and verified payroll history to Payslips; shortages and remaining authorized profiles/backup/calendar/statutory/accounting preparations to Other records. Provide a reviewer-focused grouping within Other records where granted. Preserve record history and every authorized action; no new permission-by-label logic.

Workday defaults to the current Manila date. Add date/range filtering over authorized loaded attendance records and an All loaded dates option; no invented server paging or hidden historical deletion. Say **No record for this date** rather than absent/unpaid. History counts are loaded counts, not company-wide totals. Scope self summaries to the signed-in employee even when a manager sees others' records.

Use existing responsive card patterns for repayment/installment and other affected tables. At 390/320px, amounts remain readable, long references wrap inside their cell, and dates/times have clear labels. Preserve exact decimal signs and full values; do not shrink fonts to force a desktop table onto a phone. Retain 48px baseline controls and keyboard focus. Pending self-cancellation becomes **Cancel my request**, with only the server-permitted cancelled transition and reason; it must not reveal approve/reject or reviewed-payable fields for self-approval.

## E5 — A useful, truthful Today and attendance guidance

Replace the development-oriented Connected functions tile with **My workday**, **My tasks**, **My requests**, and **Latest payslip** summaries/links derived from the validated Employee Operations workspace. Other permitted office/remittance/support links remain. Failed/not-loaded/setup-missing values use explicit states, never fabricated zero pay or no-work claims. Task/request counts describe the actor's authorized loaded records; task due dates come from their actual payload, not assumed fields. Latest payroll follows actual period/type/status, not array index or summing amounts.

Show the current/latest same-day attendance event and server day-review status separately. A normal clear chain may emphasize the likely next action: no events -> Clock in; clock_in/break_end -> Start break and Clock out; break_start -> End break; clock_out -> Day recorded. This is guidance, NOT a second attendance validator or authorization grant. Server capability remains required. Ambiguous, pending-review, conflicting, cross-device or incomplete data shows **Needs review** and the existing correction path; do not fabricate a clean shift or suppress valid exceptional review submissions. Keep alternate actual-time actions reachable where current contracts permit them, with clear warnings, never auto-submit.

Use Asia/Manila dates and offset-aware ordering; preserve the existing server-reviewed event chain, device-specific sequence, immutable events and correction flow. Do not calculate payable hours/salary or introduce an offline Web attendance queue. A midnight/date change invalidates yesterday's next-action suggestion and requires current data.

## E6 — Connect the existing Office case steps

Preserve `employee-onboarding`, `employee-cif-review`, `employee-application-review`, and `employee-first-loan`. Add a compact shared step/context strip and Next/Back links through the existing modules. Do not duplicate forms or grant Employee final Management approvals.

Carry intake/application references only within the current mount. Intake uses `applicationReference` in Office intake and CIF; application review and first-loan use `intakeReference` plus the separate loan `applicationReference`. Label these clearly. Typed references are unverified until existing protected reads validate them. Prefill an empty target field, dispatch existing input/change invalidation, and let the target revalidate. Never silently overwrite a conflicting nonempty target; use an explicit switch-case/discard choice.

Changing intake invalidates its linked application and downstream loaded identity, document URLs, review/approval/signature/release state before any new read. Keep stale-response guards. Never take the first borrower with the same name or treat carried text as authority. Preserve exact locked-document downloads, first-loan permissions, witness/receipt/identity evidence and explicit financial confirmations. Case continuation does not auto-approve, auto-release, upload evidence or trigger capture.

## E7 — Direct payslip access and bounded printable output

Payroll breakdown/history are already implemented. Add direct access through E4 and a **Print payslip** action for an exact authorized payroll record with a usable published status (`approved`, `partially_paid`, `paid`), no blocking issues and valid identity/version/amount fields. Draft/rejected/stale/incomplete records remain readable as their actual status but cannot masquerade as a final payslip. No dedicated PDF endpoint is assumed.

Use a print-specific projection of the exact server snapshot: Employee name, payroll ID/version, payroll kind and period, status, returned component labels/amounts, gross/deductions/net, completed-payment total and balance due. No local payroll, tax, contribution, balance or component-total arithmetic. Preserve negative deductions and exact decimal strings. State **Payroll record copy — not proof of payment**; an approved unpaid record must visibly show its unpaid/due state. Never invent an employer registration number, signature, bank detail or approval.

Before printing, revalidate scope and the selected payroll ID/version through a current authorized read. A changed version must be reviewed again, not silently printed; no authorization during a failed/offline/stale read. Render only the selected record in an isolated same-page print region and use the browser's Print flow (which may offer Save as PDF). Do not label this a generated/signed backend PDF. No public route, external print provider, or new PDF library is needed.

Print CSS must exclude other employees, unrelated page panels, raw workspace JSON, passwords and hidden forms. Clear the temporary region on afterprint, cancel/back, close, logout/disposal or authorization change; do not keep a detached secret-bearing window. The user controls any local saved/printed copy; already printed paper/PDF cannot be revoked by the app. Keep private-screen eligibility unchanged and invalidate existing sharing before exposing a print view through its existing lifecycle hooks.

## E8 — Complete Updates and focused copy/focus polish

Updates initially shows 50 authorized returned items with **Showing X of Y loaded updates**, then Show more in batches of 50. For 65 records the first view says 50 of 65, the next exposes all 65 in server order. Do not call returned records unread unless the server supplies that status. Today and Updates must agree about loaded versus visible count. No new remote paging API.

Humanize known Employee status/action text while preserving exact state meaning. Keep read-only, not configured, denied and failed distinct. Keep setup diagnostics available under the existing disclosure; missing setup is not zero pay. Preserve account/device/password separation and local Support updates. Review long form labels, nested borders and Cash Disbursement field widths without replacing financial wording or reviewer controls.

## E9 — Reports and printing scope assessment, not implicit new access

The planning request includes this gap, but it does not choose which borrowers an Employee may access. Produce a repository-grounded output/permission matrix before proposing a general reports center. This task is complete when the matrix and explicit unresolved decisions are recorded, not when unauthorized report buttons are invented.

| Output | Boundary in this handoff |
| --- | --- |
| Own authorized payroll | E7 implements browser Print from the existing scoped payroll snapshot. |
| Locked first-loan contract packet | Reuse the current selected-case download and exact document checks; do not regenerate it from browser fields. |
| Borrower statement and receipt search | Inspect current backend, desktop parity and grants. Document exact eligible role, object scope, endpoint/output and missing dependency. No client impersonation or reuse of client-own-data routes with substituted IDs. |
| Collection/office reports | Map current protected read/output sources and allowed Employee duties; retain server totals. A new endpoint/grant or broader borrower visibility needs separate owner approval. |
| Payment-proof review, salary payment and final posting | Current Management/owner restrictions remain; these are not missing Employee controls to unlock. |

A reports/print hub is not a requirement to create a duplicate copy of every report. Link already authorized existing outputs where it removes a real navigation gap; otherwise record a named follow-up with the precise missing contract and scope decision. Do not block the safe E1–E8 implementation on a new reporting subsystem. Do not mark deferred report implementation as delivered.

## E10 — Evidence and completion

Every fix starts with a failing behavioral regression and ends with focused passing checks and a reviewable commit. Reuse existing Employee/remittance/Office/session/privacy/PWA tests and the standard three CI jobs. Source-string assertions alone are insufficient for draft/focus/async behavior. Existing tests may reflect changed presentation, but permission/recovery/financial assertions cannot be weakened.

Recreate 11 core Employee sections at 1440/390/320px (33 layout samples): Today, Work & pay, Cash Disbursement, Office intake, CIF, Application, First-loan work, Remittance, Client support, Updates, Account. Additionally cover Area Management when authorized, each changed work/pay view, rejection, printed payslip, self-only/reviewer/backup-limited roles, and denied/setup-missing cases. Use only synthetic/disposable records. Test 200% zoom, keyboard/focus, long amounts/references, delayed/failed/recovering reads, offline events, concurrent clicks, role/session changes and 65 Updates.

Inspect the final public build and service-worker assets; no fixtures, private payroll snapshots or credentials in public output. Actual financial/capture/production/device/office acceptance is not claimed from synthetic layouts. Record exact implementation head, results, pending limitations, shared integration order and E9 decisions in GitHub, Notion and Create State. Leave unavailable checks explicit. Keep the PR Draft/open/unmerged; no acceptance box on Master #296 is automatically completed.

Execution checklist: [2026-10-02-employee-web-ui-completion.md](../plans/2026-10-02-employee-web-ui-completion.md).
