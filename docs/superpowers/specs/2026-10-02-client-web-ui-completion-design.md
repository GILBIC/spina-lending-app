# SPINA Client Web UI Completion — Design and Acceptance

Date: 2 October 2026 (Asia/Manila).

## Status, authority, and evidence

**Planning-only, owner-started Codex handoff.** The owner requested “Plan everything and create a pr i will make codex do this” after the Client website review. This specification covers every review finding. The owner will start Codex separately; publishing these documents does not implement fixes, invoke an agent, approve a release, or authorize production operations. Keep the handoff PR Draft/open/unmerged, with automatic merge disabled.

Reviewed baseline: `GILBIC/spina-lending-app` main `41a13eb59c9cc1b65a0a6a51f3b73db4a0895013`, after merged PR #484. Management #485, Collector #486, and Employee #487 are separate workstreams. Recheck their live heads and current main before execution; these references are snapshots, not future assumptions.

Read before asking the owner to repeat decisions:
- [Client review and reproduction scope](https://github.com/GILBIC/spina-lending-app/pull/484#issuecomment-5943307098).
- [Frozen Master #296](https://github.com/GILBIC/spina-lending-app/issues/296), unchanged by this work.
- [Released integration #484](https://github.com/GILBIC/spina-lending-app/pull/484) and related [#485](https://github.com/GILBIC/spina-lending-app/pull/485), [#486](https://github.com/GILBIC/spina-lending-app/pull/486), [#487](https://github.com/GILBIC/spina-lending-app/pull/487).
- [Notion Current Project State](https://www.notion.so/3cd5ade7bef48106b2c2ff97182001dd), latest Client checkpoint.
- Create State project `69a61c48-f842-44ac-aa11-e987ffec4a36`.
- Existing `docs/superpowers/specs/2026-09-05-client-account-credential-lifecycle-design.md`, the 7x7 post-maturity specification, and executable Client APIs.

The previous review used released assets and synthetic records in local Chromium: 11 sections at 1440/390/320px, plus expanded schedules and focused error/loading/draft tests. It was not production sign-in, a real payment/proof upload, renewal signing, cash receipt, provider settlement, actual PDF-content validation, or a complete security audit. `SPINA_Client_UI_Review_41a13eb5.zip` is an optional conversation artifact, not a file assumed to exist in Codex. Reproduce the written scenarios from current source when it is absent.

## Goal and selected approach

Make the existing Client portal truthful about unavailable data, readable on phones, resilient to routine refresh, and clear about the borrower's next action. Preserve pink/white branding, separate Regular/7x7 information, existing navigation destinations, own-data boundaries, and protected workflows.

Use targeted changes to the existing ES modules: one small mount-local read controller, a shared per-loan schedule controller, and focused payment-detail presentation. Keep forms mounted while updating read regions. A CSS-only pass cannot correct false-empty/payoff states or lost files. A framework/router rewrite would duplicate existing functions and conflict with three other role workstreams. Neither is selected.

Already implemented, to preserve: loans/schedules, receipts/voids, Statement, original issued documents and record-copy PDFs, proof upload/correction/history/paging, renewal request/cancel/decision/own-sign/cash-confirm/progress, Support, local notification-read updates, account/device controls, and capability-gated GCash controls. This is not a new lending, checkout, document-generation, or authentication system.

## Coordination and change boundaries

Create the Client PR from main, not stacked on a planning branch. Do not modify the other three plans or branches. Before shared `app.js`, `ui.js`, `app.css`, `presenters.js`, `payment-proofs.js`, or `sw.js` edits, inspect #485–#487 and record one integration owner/order for overlapping changes. Client-only work can continue independently. Reuse an equivalent verified optional shell lifecycle hook; do not build a fourth refresh registry or import an unmerged Management-specific controller. Never overwrite another executor's uncommitted work.

- No new backend endpoint, schema, role grant, framework, dependency upgrade, global cache, financial calculator, or native-app redesign.
- Display server money exactly through existing decimal-text formatters. No subtraction of balances to infer allocations, no payoff/interest/penalty recomputation, and no total from a filtered or partial list.
- Loading, failed, unrequested, disabled, and genuinely empty data are different. Missing fields never silently become zero, paid, eligible, linked, or complete.
- Client access stays limited to the signed-in borrower's own authorized records. Validate target IDs, same-loan responses, account/device scope, and current capabilities; hiding controls is not authorization.
- Preserve online-only protected mutations, duplicate-submit protection, exact replay identities, uncertain-outcome recovery, stale versions/hashes, confirmations, and server decisions. A GET success or view switch cannot reset a pending submission.
- No new localStorage/sessionStorage/IndexedDB/service-worker persistence for drafts, File objects, schedules, credentials, or downloaded private documents. Retain file-input DOM nodes instead of attempting to repopulate a file input. Logout, expiry, device/account/grant changes and denied access clear private state.
- Proof submitted/reviewed, provider checkout completed, official payment recorded, loan approved, signed, cash received, and activated remain distinct states. No browser action may manufacture official payment/activation.
- Public registration and Client self-password change/reset remain restricted by the approved policy. Do not add them as missing features. Preserve other-device revocation checks and current-device/session cleanup.
- No real payments, credentials, document uploads, provider checkout, renewal signatures, cash confirmations, screen capture, migrations, delivery/deployment runs, automatic merge, mark-ready, or Master #296 acceptance changes in this handoff.

## L1 — Truthful same-loan payoff and schedule recovery

The active-7x7 preload currently swallows failures. A later successful View schedule still omits the payoff/penalty/review fields. Use one per-loan result state for the home summary, loan card, and expanded schedule.

The current `/api/v1/client/loans/{loan_id}/schedule` supplies `loan_id`, `read_only`, contractual/operational maturity, `past_due_amount`, `past_due_count`, `penalty_status`, `projected_penalty`, `assessed_penalty_balance`, `penalty_base`, `remaining_cost_headroom`, `exact_payoff_total`, `management_review_required_reason`, and rows. Validate the expected loan and required shape before displaying a response. Keep field-level missing data unavailable rather than fabricating a zero.

On initial load/refresh show Loading; on failure show **Payoff information unavailable** with a local Retry. A successful retry or View schedule updates all views of that same loan from the new result. An older request cannot overwrite a newer one, and a late response cannot render after scope disposal.

Retain existing status semantics. For `management_review_required`, prominently show the returned reason and do not show a confirmed payoff. For known ordinary payoff states (`projected`, `penalty_outstanding`, `cap_exhausted`), present valid returned amounts without recalculation; label projected penalty as not yet assessed and distinguish it from assessed penalty balance. Unknown status is not permission to display a confirmed payoff. Preserve applicable Regular/7x7 differences and contractual versus operational maturity. Detailed context may be disclosed without hiding warnings.

Acceptance fixture: a failed initial 7x7 read followed by same-loan success with `exact_payoff_total: '2205.00'` and `assessed_penalty_balance: '105.00'` must update summary and expanded detail. Also test review-required, genuine zero, missing amount, invalid money, wrong loan, unknown status, concurrent refresh, abort and account switch. These are fixture values, not production balances.

## L2 — Propagate failures and offer local retry

Documents currently turns a failed loans read into No linked loan and a failed payments read into No official payment. Conditional checkout turns the failed loans read into No active loan. Carry resource state as well as arrays into dependent components.

Documents has independent statement-download, issued-loan, and payment-copy regions. A failed list must not erase an unrelated working region. Missing loans disable new loan selection and explain the read failure; they do not change whether an independently authorized statement-copy request can be made. Never show a payment-copy action for an unverified transaction ID.

Payment options must distinguish unavailable configuration, explicitly disabled capability, unavailable loan list, and a successful empty eligible list. Do not enable checkout from a cached capability or failed source. Do not discard a pending provider intent during unrelated refresh.

Payment proof must retain an error/status region and Retry even when its first list request fails. Retrying a read must not submit a file. Existing version, file-type, size, paging, authorized content download, and same-submission replay safeguards remain. A loans error must prevent a new proof being retargeted to a guessed/default loan; independently authorized existing proof detail/history can still work.

Acceptance includes each failed resource independently, correct zero/empty success, disabled upload/checkout, recovery with previous input preserved, and 401/403 disposal. Local retries must not produce duplicate handlers or silently clear a pending upload.

## L3 — Preserve unrelated drafts and distinguish save from refresh

Replace full Client remounts after Support, renewal creation/cancellation/decision/signature/cash confirmation with affected-region refresh where the account/authority has not changed. Preserve unrelated Support and renewal text, selected proof File input, proof note, chosen loan, open schedule, filters and current section. Only clear the form whose verified submission completed, and do not erase text the user edited during its request.

Routine header/section Refresh is a read operation, not permission to discard all drafts. Keep dirty form nodes separate from replaceable result lists. An intentional action within a proof editor that must replace a dirty draft requires explicit discard confirmation; it must not bypass existing uncertain-submission locks. Preserve the already-local Mark as read behavior.

A successful mutation followed by failed list refresh is **Saved; refreshing records failed**, not a failed save inviting another submission. A timeout/unverified response remains unconfirmed; use existing same-identity replay/reconciliation where supported, never invent a new request ID or automatic retry. Retained input does not retain eligibility: if its loan/request changes, mark the draft stale, prevent submission, and require explicit revalidation. Scope/permission denial still clears private state.

Acceptance: fill renewal amount `5000` and message, proof note and a selected synthetic PNG; submit mocked Support through the real handler; unrelated values AND File input identity survive. Test other listed actions separately, failed post-save read, rapid submits, typing during request, proof paging/Refresh/new submission, and unchanged Mark as read. Restore focus near the completed action only if the user has not moved elsewhere.

## L4 — Readable mobile schedules and statements; manageable length

Reuse existing labeled mobile-card patterns below the current phone breakpoint. Keep desktop tables, readable type and current control-size tokens. Schedule cards prioritize date, required installment, remaining amount, status and note. Statement loan/payment cards must retain every currently displayed field, exact money, dates, loan identity and void indicators. Avoid generic table CSS that changes other roles.

Expanded schedules need a Close/Collapse action that returns focus to the opener, a separate Refresh, and local **Upcoming / History / All** views. Upcoming means returned rows dated on/after the displayed Manila date, not a new financial status. History means earlier dates; past-due totals and a link to relevant rows stay visible even while Upcoming is selected. All remains available, including unknown-status rows. Show up to 20 matching rows initially, with **Show more** in increments of 20; identify displayed versus loaded row counts. Preserve row identity/order and exact returned dates; no deduplication or removal of equal-looking entries. If there are no upcoming rows, say so without implying the loan is paid.

Closing the schedule invalidates pending panel rendering/focus; it need not destroy a verified read shared with the loan summary. Disclosure changes must preserve private-screen boundaries. No new printable schedule/PDF endpoint is required.

Acceptance: 0/30/120 rows, long notes, exact decimals, unknown statuses, 390/320 widths, 200% zoom and keyboard focus. Reach all 120 loaded rows. A page without horizontal overflow can still fail visual readability.

## L5 — Core information loads independently

Mount the shell and all existing section placeholders promptly. Load account and loans independently, render available data, then load each active loan's schedule without blocking the other loan or the shell. Nonessential Statement, payments, renewal/history, Support, proof and provider panels initialize on first activation; Updates may load separately but cannot hold the root. Actual reads AND expensive module mounts must be deferred, not only hidden.

Use mount-local deduplication for concurrent reads, current-session access for delayed mounts, last-request-wins, and complete cleanup. Reuse the verified optional shell handle from other role work when present. Ordinary Refresh updates read regions while preserving L3; authentication/device/role changes still fully dispose. A copied mount context must not retain an obsolete session after token rotation. Do not create a Client-only alternate authentication or service-worker system.

Acceptance: hold only Updates, Statement, 7x7 schedule, proof or GCash requests indefinitely; shell and independent loan remain usable. Revisit a section without duplicate first-load/listeners. One failing panel recovers locally; no response from an old account, denied session or superseded mount appears later.

## L6 — Useful installment guidance without a new allocator

Today should prioritize each active loan's next relevant schedule information and verified exceptions, not a wall of counts. Reuse L1's validated schedule state; no second fetch/calculator for the same loan.

Show the agreed installment amount from the loan separately from the remaining amount on a specific saved row. With unambiguous returned dates/status, show the row dated today, otherwise the earliest later unpaid collectible row, plus the server's separate past-due amount/count when present. The date grouping uses Asia/Manila; label the displayed date, and mark data stale/reload on day rollover rather than rolling an old snapshot forward. Select a row only; never sum, project or reallocate amounts. Unknown/ambiguous/incomplete rows yield **Open schedule for the current amount**, not a guessed due value.

Coverage must come from authoritative row status/details or explicit returned evidence. Do not convert an ADV start/end range into assumed coverage of every intermediate day; non-contiguous coverage stays exact. A zero remaining installment is not zero total debt. No upcoming rows is not paid-off unless the server state establishes that. Review-required/payoff-unavailable warnings from L1 stay prominent.

Acceptance: due today, partially paid, already-covered, no-collection, no today row with future row, past due plus future row, paid loan, missing/ambiguous row, non-contiguous coverage, unknown status, local-browser timezone differing from Manila, and midnight rollover. Use exact backend status vocabulary; document unsupported projections instead of guessing.

## L7 — Payment details and contextual existing downloads

Add **View payment details** for an exact authorized transaction. The current payment API already returns collector, collection date, recorded time, covered dates, previous and official balance, note, origin, status, void date/reason, edit version, and remittance facts. Display useful returned facts without inventing a principal/interest split, extra amount, or historical correction timeline not supplied by the API. Keep internal custody separate from whether the client's official payment is recorded.

Put **Download statement copy (PDF)** on Statement and **Download payment record copy (PDF)** beside the corresponding payment/detail, reusing the existing protected endpoints and private download validation. Keep Documents as the central archive; do not implement a second PDF generator. The existing whole-account statement download must not be relabeled as filtered if local UI filters are added.

Original released packets remain immutable originals; current record copies may reflect corrections/voids and must say so. Downloads are explicit user actions, checked for valid ID/nonempty expected MIME and canceled/cleaned on scope change. Never follow a notification-supplied arbitrary URL or expose a public file route.

Acceptance: same-name loans, wrong/stale transaction, voided record/reason, large exact decimal, sparse optional facts, ownership denial, malformed/empty/wrong-MIME file, aborted download and matching transaction-to-copy. Verify actual synthetic record-copy content/layout when testing download integration; an HTTP200 or mocked Blob alone is not PDF acceptance.

## L8 — Complete and safely actionable Updates

Show 30 returned notifications initially and **Show more** in increments of 30; all 65 returned fixture items must be reachable, in server order. The current API defaults to limit100/max200 and does not return offset paging or a lifetime total. Label counts as **loaded updates** and, where useful, **unread among loaded updates**. Do not claim complete lifetime history or add an invented offset parameter.

Keep local Mark as read, verified identity/result, focus and draft preservation. A record shortcut is a read/navigation action only; it never marks read automatically, pays, cancels, signs or confirms cash.

The current payload includes `notification_id`, `recipient_user_id`, `transaction_id`, `client_id`, `notification_type`, and `metadata`. An exact transaction shortcut may use `transaction_id` only after finding the authorized payment in the current own-data read. For proof/renewal/Support, inspect executable producers and pin their actual type/metadata keys in tests; only documented identifiers resolved through current own-data APIs can open a specific record. Never infer IDs from message text, use `remittance_id` to expose staff custody screens, or accept arbitrary URLs. When only a verified category is available, label a section link honestly; unknown or unverifiable targets remain read-only text. Missing producer metadata is an explicit deferred contract gap, not permission to add an endpoint/grant or claim complete deep linking.

Acceptance: 0/30/65/100/200 returned items, duplicate-looking distinct IDs, read failure, mismatched recipient, wrong target, absent metadata, unknown type, malicious URL/text, deleted record, and link to a record outside the first visible page. Revalidate before rendering details.

## L9 — Clear renewal progress and safe presentation

Within the existing Renewal requests section, offer **Current requests / Eligibility / History** local views or equivalent compact disclosure. Prioritize the selected request's status and next permitted action. Do not display the same request twice as separate request/progress cards: combine only by exact request ID, never loan number/name. Preserve all source facts and history; when sources disagree or one fails, show unavailable/stale workflow instead of merging an apparently completed state.

Humanize readiness tokens without altering payloads or granting actions. Keep separate approval, borrower acceptance, required signer verification, borrower signing, physical cash confirmation, Management proof verification and activation. Retain Office Processing Required, other signers using their own accounts, rejection/cancellation notes, exact old-loan settlement/net values, and the rule that a renewed loan is not collectible before verified activation. Unknown tokens get a neutral label/details, not a green completion badge. Navigation itself never invokes an action.

Acceptance: pending/cancelled/rejected, approved awaiting borrower decision, accepted awaiting verification, office-only, other signers incomplete, cash marked given but not received, client cash confirmed but not active, active, failed workflow read and concurrent state change. Preserve helper contracts and confirmation prompts; test through mocks only.

## L10 — Integrated evidence and completion definition

The core visual matrix is the 11 existing section IDs: `client-overview`, `client-loans`, `client-renewals`, `client-payment-instructions`, `client-payment-proofs`, `client-support`, `client-payments`, `client-statement`, `client-documents`, `client-updates`, `client-account`. Capture each at 1440/390/320px (33 initial samples), plus expanded 30/120-row schedules, payment details, renewal states, proof correction/file drafts, disabled/enabled synthetic capabilities and document output. Verify long text/money, empty/error/recovery, focus, keyboard, 200% zoom and reduced motion. Screenshots alone do not prove ownership or financial safety.

Run the existing portal/module/build/public-output/PWA checks, focused regression tests throughout, and the three required CI jobs on the exact implementation head. Reuse unchanged successful evidence; no duplicate workflows or weakened checks. Use synthetic/disposable data and existing authenticated own-data tests, including another client/user/device, revoked access and late responses. No real credentials, upload, checkout, signing or physical receipt for the test evidence.

Map L1–L10 to exact tests/commits/screenshots. Explicitly record any deferred notification/transaction-field contract gap and any unavailable browser/PDF verification; do not hide it behind an overall Green. Keep owner production/native-device acceptance separate.

After meaningful progress synchronize GitHub, Notion and Create State with branch/head, completed/pending tasks, commands/results, CI IDs, shared integration status, limitations and next action. Report a failed connector rather than claiming synchronization. Leave the PR Draft/open/unmerged until separately authorized.

Implementation checklist: [2026-10-02-client-web-ui-completion.md](../plans/2026-10-02-client-web-ui-completion.md).
