# SPINA Collector Web UI Completion — Design and Acceptance

Date: 2 October 2026, Asia/Manila. Revision 2: complete original review plus re-review addendum.

## Status and authority

**Planning-only Codex handoff, updated in existing PR #486.** The owner originally requested “Plan everything and create a pr i will make codex do this” and, after the second Collector review, instructed “Update the current pr and include thing everything”. This revision incorporates every finding from both reviews into explicit requirements and acceptance. It does not implement the fixes or start Codex. Keep PR #486 Draft/open/unmerged, with automatic merge off. No mark-ready, merge, delivery/deployment, migrations, production credentials/transactions, actual screen capture, or Master acceptance changes are authorized by this planning update.

Reviewed main: `41a13eb59c9cc1b65a0a6a51f3b73db4a0895013`, following merged #484. Original Collector planning head: `20318a5e31f3dd8036fd5f40f7f210b174ed9e33`. At revision preflight, #486 still contained only its two Markdown files; Management #485, Employee #487 and Client #488 were separate open planning workstreams. Re-read live references before execution, not these snapshots alone.

Authorities, before asking the owner to repeat decisions:
- [Original Collector review](https://github.com/GILBIC/spina-lending-app/pull/484#issuecomment-5942786091).
- [Collector re-review and missing-function addendum](https://github.com/GILBIC/spina-lending-app/pull/486#issuecomment-5943559009).
- [Frozen Master #296](https://github.com/GILBIC/spina-lending-app/issues/296), unchanged here, and [release #484](https://github.com/GILBIC/spina-lending-app/pull/484).
- Related role handoffs [#485](https://github.com/GILBIC/spina-lending-app/pull/485), [#487](https://github.com/GILBIC/spina-lending-app/pull/487), [#488](https://github.com/GILBIC/spina-lending-app/pull/488).
- [Notion Current Project State](https://www.notion.so/3cd5ade7bef48106b2c2ff97182001dd), latest Collector checkpoint; Create State project `69a61c48-f842-44ac-aa11-e987ffec4a36`.

The reviews used exact-release public assets and synthetic responses in local Chromium at 1440/390/320px. The re-review retained 24 baseline layouts and added nine focused check groups. Neither review was signed-in production, actual cash/payment/photo/visit/capture/PDF acceptance, a live latency measure, or a full security audit. The optional conversation archives `SPINA_Collector_UI_Review_41a13eb5.zip` and `SPINA_Collector_UI_ReReview_41a13eb5.zip` are not assumed to exist in Codex. Reproduce the documented cases from source. This revision performs documentation/source-contract review only; prior reproduction evidence is not a newly fixed test result.

## Goal, approach and coordination

Make daily Collector work truthful, draft-safe, phone-readable and easy to navigate. Preserve pink/white route-first presentation, existing destinations/IDs, server area order, distinct Regular/7x7 entries, and Payment versus Unable to pay. Reuse collection/ADV/Combined Pay/correction/other-area/renewal/visit/account functions and the shared Employee Operations module; they are not missing systems.

Selected approach: targeted ES-module changes. Extract bounded remittance and route controllers, add a Collector-only read-only schedule view, and retain one workspace financial guard. CSS alone does not fix false states or lost drafts. A new framework/global store/router would duplicate working code and conflict with the other role PRs. No new lending product, endpoint, collection calculator, native redesign or offline outbox is selected.

Work on `plan/collector-web-ui-completion-20261002` in PR #486, not another PR or another role's branch. Before overlapping `app.js`, `ui.js`, `app.css`, `sw.js`, `presenters.js`, `employee-operations.js` or other shared helpers, inspect the actual #485/#487/#488 diffs and record one integration owner/order. Reuse an equivalent verified optional shell hook instead of building another refresh registry; do not import an unmerged Management-specific controller. Do not reset, force-push, cherry-pick or rebase another executor's unreviewed work without agreed coordination. Role-specific work can proceed while shared integration is resolved. Employee work/pay changes belong to #487; this PR verifies the Collector mount still works. Final combined shared-file integration needs exact-head regression evidence.

## Permanent boundaries

- Keep current APIs, request/query semantics, server permissions, device identities/sequences, transaction UUIDs, route revisions, exact receipt verification, allocation hashes, recorder attribution, custody locks and handover confirmations. UI visibility is not authority.
- Collector financial writes remain online-only. One mounted workspace owns one guard. Routine refresh, navigation, filtering, a successful GET or lazy mounting must not clear an uncertain/offline financial lock. No automatic financial retry, new outbox or new identity for an ambiguous submission.
- Distinguish ordinary refresh from explicit reconciliation. Ordinary success retains the guard and unrelated safe input. Existing stronger teardown may be necessary for offline/uncertain recovery; explain that reset rather than disguising it as normal refresh. An ambiguous remittance cannot become repeatable merely by remounting.
- Exact money remains server decimal text. No remittance totals from visible rows, payoff/penalty calculation, local Combined Pay split, revised due dates/PASS/ADV rules, tax/accounting change, or client-side estimate of release cash. Exact amount comparison may control disclosure, not allocation.
- Drafts and selected files remain within the current mount only. No new localStorage/sessionStorage/IndexedDB/URL/service-worker persistence. Logout, expiry, denied access, identity/device/permission changes clear private state. Retained text does not renew a stale version or extend credential/one-time-secret lifetime.
- Preserve borrower extra-allocation choices and Combined Pay Preview/Confirm. A detail link, notification or search result never starts a payment, signs for a borrower, confirms cash or approves an action.
- Preserve narrow private-screen/capture boundaries. Stop/invalidate sharing before replacing or hiding a captured panel. New schedule, receipt and renewal detail is private by default; no eligibility expansion or broader capture marker. Test with mocked tracks only.
- No backend/schema/migration, role grant, dependency upgrade, CI weakening, Master rewrite, production operation, real capture, delivery or deployment. The Collector route GET can finalize elapsed schedules; do not probe it against production as if it were a harmless UI read.

## C1 — Truthful Remittance reads and recovery

Represent preview, recipients and history independently with `idle | loading | ready | error | unavailable | not_permitted`. A skipped read is not a successful empty response. Missing/invalid summary fields are unavailable; explicit decimal zero and integer zero are valid.

The preview and recipient endpoints require `remittance.create`; history requires `remittance.view`. Evaluate each permission, not a broad inferred role. History-only users must not gain creation-only data. A create-only user must not be sent to a history read without its grant; show its permission state honestly.

Required messages/actions:
- Missing authoritative route date: **Route date unavailable — refresh the route to load a remittance summary.** Do not substitute the browser date.
- History-only: **Remittance history only**, without fake metrics or a submit form.
- Preview error: **Remittance summary unavailable** and Retry summary.
- Recipients error: **Recipients could not load** and Retry recipients.
- Ready empty recipient list: **No eligible remittance recipient is available.** This is not an error fallback.
- History error: local error/retry without erasing a separately valid preview.

Submit requires current creation permission, online/unlocked guard, a known route date, a matching verified preview, valid required counts/amounts, the existing positive-total rule, and an explicitly selected recipient from the successful current list. C9 adds evidence review and response confirmation. Preserve the typed note and still-valid selected recipient during reads. Removal of a recipient requires reselection, not an automatic substitute. Date/account changes invalidate previous results; slower old responses cannot overwrite newer ones.

## C2 — Local success refresh and draft retention

Replace ordinary successful full-workspace remounts for Payment/Unable to pay, covered dates, correction, Combined Pay, other-area collection, renewal and remittance with affected-data refresh. Review every shared `onSaved` path, not only Payment.

Refresh the authoritative route once per refresh generation, update the entry map, Today/attention and dependent remittance state, and reconcile rows by `route_entry_id`. Check client/loan/date/revision identity. Clear only the confirmed submitted editor. Retain unrelated form nodes, notes, selected renewal photo, search/filter/section selection and current focus where safe. Never rebuild file-input nodes and pretend the selection was preserved.

Retained input is not retained authorization. If another row changes revision, ownership, date, status or collectibility, preserve its safe note only for review and disable the old command with **Route changed — review again**. Never attach a new revision/date to an old draft silently. Remove newly forbidden private data. Child workflow consumers receive a narrow snapshot invalidation callback; old combined hashes and schedule selections require explicit re-review when their inputs change.

A verified saved result plus failed follow-up read is **Saved; latest route/summary could not refresh**, not failed payment. Preserve the receipt/status, block repetition of the committed action, and block work needing missing current state. Do not POST again automatically. Unknown, 5xx or mismatched results use existing guard reconciliation, strengthened by C9 for remittance.

Return focus to the saved row/status or a visible heading only when the user has not moved elsewhere. Do not jump to the next borrower or open a new payment. Routine header Refresh retains safe drafts and cannot interrupt an active write. Identity/permission teardown and explicit reconciliation retain their stronger rules.

## C3 — Readable Needs attention and feedback

Retain the desktop table; below the current mobile-card breakpoint use explicit borrower, area, loan, reason and amount labels. Keep currency readable as a unit and long names/notes legible. Rename the heading **Master Review** to **Needs attention**, retaining `collector-master-review`. C6 supplies **Open loan in route** without opening a financial form.

Reuse existing 48px baseline controls, focus styling, error feedback and reduced motion. Do not shrink fonts to squeeze five columns. Existing route cards are a useful baseline, not a redesign target. A clear/empty attention result requires a successful route read, not fallback empty data. No-horizontal-overflow alone is not visual acceptance.

## C4 — Progressive payment fields and Combined Pay

Ordinary Payment first shows borrower/loan identity, amount and Save official entry/Cancel. Optional Note and **Payment options and follow-up** disclosures keep exceptions reachable. Compare only valid exact entered and server-supplied unpaid amounts to control disclosure; an unknown obligation is not zero and the daily-amount fallback is not proof of settlement.

- Short Regular payment or Unable to pay exposes the current required reason/follow-up controls; do not invent Regular rules for 7x7.
- Other retains its explanation requirement. Promised to pay later exposes the required promise date/amount. Other reasons send null promise fields; hidden old values must not leak.
- Extra cash exposes explicit borrower allocation choices, including the supported voluntary No Collection option. Never automatically choose advance/principal reduction.
- Changing entry type, amount or reason keeps `hidden`, `required`, field validation and payload semantics aligned. A server error reveals/focuses the relevant field. Cancel retains reset-and-focus behavior.

Combined Pay retains server allocation Preview followed by Confirm, exact review hash and identity checks. Use server `regular_past_due_followup_required` and `extra_choice_required` flags; never infer the split. Give identity, total cash, extra choice, preview and actions adequate width. Meaningful edits invalidate preview, while a disclosure toggle alone never approves or mutates a draft. Covered-date selection and correction remain their existing protected workflows, separate from C10 viewing.

## C5 — Independent Today/route loading

Render shell/navigation promptly; load account and route independently. Today and route must not wait for history, remittance preview/recipients, Updates, renewal or employee-tool reads. Route failure blocks route-dependent actions with truthful state, not safe unrelated screens.

Secondary modules/data load on first activation with deduplicated in-flight work, local retry, and mount-owned cancellation/generations. Hiding eagerly fetched screens is insufficient. Revisit preserves mounted editors. Use current-session getters; copied contexts and token refresh must not retain stale authority. Late-mounted controls inherit the same guard and offline state. Ordinary task reads cannot create a replacement guard. Rapid navigation, date rollover, permission/device changes or logout cannot restore old content or steal focus.

## C6 — Route search and exact destinations

Search authorized displayed borrower/loan fields, with Area and **All / Needs attention / Recorded today** filters. Preserve server area/row order and separate Regular/7x7 IDs. Needs attention uses the existing unresolved predicate; Recorded today uses `processed_today === true`, so a short payment can appear in both categories.

Show **Showing X of Y loaded loan entries**. Keep full-route financial figures/counts separate from filtered matches; twelve loans across six clients are twelve loan entries. Distinguish No matches from Route unavailable. Hide/show existing rows instead of recreating drafts per keystroke.

Attention actions navigate to `collector-route` and the exact still-authorized `route_entry_id`, visibly clear obstructing filters if necessary, and focus the row identity. Payment stays closed. Never match only by a person's name. A missing/stale/unauthorized target says **This route entry is no longer available. Refresh the route.** No broader lookup/write is triggered. C11/C12 add similarly exact receipt/renewal destinations.

## C7 — Terminology, layout and complete loaded lists

Overview is **Today**; route remains **Today's route / Assigned area ledger**. Rename **Route clients / loans** to **Route loan entries**. Do not change expected-total semantics as cosmetic work.

Remittance history and Updates initially display 30 returned records; Show more adds 30 until all authorized loaded records are accessible. Preserve order and duplicate-looking records with distinct IDs. Show visible/loaded counts, not an invented lifetime total or paging cursor. History details include C9 evidence; Updates actions follow C13.

Humanize known status codes (`not_submitted` -> **Not submitted**) through explicit display mappings. Unknown values get neutral labels, not success/approval. Keep raw codes for API predicates. Scope spacing/form width/action hierarchy to Collector; preserve all warnings, custody/receipt/correction instructions and conditional visit/account surfaces.

## C9 — Complete remittance evidence and verified submission (new)

C1's summary is not enough to constitute review. Show the complete authorized `items` and `refund_due_releases` from the existing preview, including borrower/loan/type, exact amount, receipt, collection date, exact covered dates, notes where returned, refund amount, evidence reference and release time. Display authoritative total and refund total separately. Validate arrays, identity uniqueness and declared counts; an omitted or inconsistent required evidence collection is unavailable, not empty. Do not calculate net cash from the rows, hide a refund as a payment, or add a second manually entered total.

Use a review disclosure with the full list and an explicit **I reviewed the included payments and refund cash outflows** checkbox before submitting. This is local UI acknowledgment, not a new request field or proof that physical cash was received. Do not enforce scroll-tracking as supposed evidence of reading. Changing date/recipient, underlying preview items/amounts, or a known collection/refund invalidates acknowledgment. Keep note text where safe. Submission remains disabled if evidence is incomplete or C1/guard requirements fail.

The existing POST body remains `{recipient_user_id, collection_date, note}`. After API envelope unwrapping, a success must be a usable remittance record: nonempty valid `remittance_id`/number, matching collector and selected recipient, matching date, status `submitted`, valid returned amounts/counts and complete item/refund facts consistent with the reviewed preview. Match IDs and authoritative fields, never recompute the total. A known already-terminal result is reconciled and explained, not blindly described as a new submission.

The current contract does not submit a preview digest or a client-generated remittance request UUID. Do not invent one or claim that UI acknowledgment atomically freezes the backend snapshot. If the returned snapshot differs, the server may already have committed: preserve the result as unconfirmed/mismatched, lock for reconciliation and read its authoritative state. Do not label it a rejected write, regenerate a request, unlock, or automatically resubmit. An empty object, missing/incorrect identity, wrong recipient/date/collector, malformed status or timeout is never success. Use **Submission could not be confirmed — check its status before trying again.** If current APIs cannot disambiguate a request safely, keep it blocked and record the limitation instead of guessing.

Provide history detail with the same saved item/refund evidence, note, submitted/reviewed/received/rejected timestamps and rejection reason when returned. Pending does not transfer custody; Rejected does not delete the snapshot. Missing optional historical facts are **Not recorded**, not invented values. Sender-side detail is read-only: do not copy Employee/recipient Accept/Reject into it or grant the sender self-acceptance. Current recipient workflows remain independent.

Acceptance includes two payments `'100.00'` and `'50.00'`, refund `'35.00'`, server total `'115.00'`, both receipt IDs and refund evidence visible; rejected history reason visible; zero/refund-free cases; complete counts; changed preview; `{}` response with no success toast/remount/unlock; mismatched/duplicate IDs, stale date, denied access, concurrent collection, terminal status and timeout/read failure. No real remittance is made.

## C10 — Full read-only Collector schedule/payoff (new)

Add **View schedule** on an authorized route loan independently of `collection.create` or correction permission. Use `GET /api/v1/collector/loans/{loan_id}/schedule` under existing `route.view` and server assignment scope; never borrow the Client endpoint. Same-loan/client IDs, schedule identity/version, `read_only`, current route scope and response generation must match. Do not require opening an editor or acquiring a write operation merely to inspect a schedule.

Show loan/borrower/type, server `as_of_date`, contract reference/frequency, base and updated maturity, extension/status, past due, exact returned row amounts, paid/prepaid/remaining fields and available principal/interest/promise/reason facts. Show payoff, projected versus assessed penalty and the Management-review-required explanation. Review-required or unsupported/missing authoritative fields cannot become a confirmed payoff or zero. Exact payoff `'2205.00'` and assessed penalty `'105.00'` are fixture values, not calculations.

Use desktop table/mobile labeled rows, a Close/Collapse action and **Current & upcoming / History / All** views based on server dates. Default Current & upcoming, initially 30 matching returned rows and Show more in batches of 30. Past-due/promise summary remains visible even if older rows are in History. All exposes every returned row in original order; do not discard same-date rows or treat filtered rows as a complete financial total. Date-view filtering is display-only; unknown dates/statuses stay reachable in All with a neutral indication.

Opening, refreshing, filtering and closing are read-only; no form is created, no allocation hash approved and no guard lock cleared. An existing uncertain-write lock stays visible. Offline cannot fetch a fresh schedule or claim an old response is current. Scope loss clears private details. Return focus to the exact opener when appropriate; late responses do not reopen a closed panel or steal focus. Cover route-view-only, other-collector denied access, 30/120 rows, gaps, no-collection/ADV, promise states, unknown/missing money and review-required cases.

## C11 — Persistent today-receipt detail (new)

Expose **View today's receipts** from each row with valid returned `today_receipts`. List every distinct returned transaction by identity, not just `today_transaction_id`. Display receipt number, exact amount/type, collector, accepted time, notes, covered dates and lock state exactly where supplied. A temporary save toast remains feedback, not the only way to find the receipt.

The route payload is the current authorized source. Do not invent previous balances, allocations, printable receipts or a lifetime transaction history. Distinguish absent/unavailable receipt detail from a confirmed zero-record result. If only an incomplete legacy summary is available, show its supplied facts and an honest unavailable detail message.

Read-only detail remains available for a permitted row recorded by another collector, while editing remains forbidden. Keep direct Management/cross-collector origin and custody messages supplied by the route. No row/name fallback, auto-opened correction or new permission. Multiple receipts survive local updates/filtering; changed scope invalidates the open detail. Newer receipts should replace stale lists only from verified authoritative refresh. C14 separately assesses older history and output contracts.

## C12 — Renewal route badges and full cash context (new)

Use `renewal_requested`/`renewal_requests` to show **Renewal requested** with the precise request's status/type. Route metadata is grouped per borrower and may repeat on both Regular/7x7 rows; match `request.loan_id` to the relevant row, not whichever row appears first. When several valid requests exist, show a chooser with exact loan/request IDs. A true flag with missing identity is a neutral badge without a fabricated action.

A badge opens the exact permitted request in `collector-renewals` using its existing assigned queue and current renewal permissions. No recommendation/cash control appears to a route-view-only account. Missing queue access or a removed request yields an honest read-only/unavailable state, not broader access. Preserve any other draft/photo and require deliberate discard before replacing a dirty same-task editor.

Show server requested amount, approved principal, old-loan offset (`renewal_offset_amount`), net release and `amount_locked_at`, plus available client message, recommendation/reason/comment, Management review note, borrower decision, signer readiness, office-processing requirement, cash stages, handover proof and activation. A nullable value is Unavailable, not zero; a valid zero offset is zero. Approved principal is not net cash. Without an authoritative lock, label release cash not final/awaiting amount lock; never subtract principal and balance locally or invent an estimate.

Prioritize current status and next permitted action. Preserve `collectorRenewalActions`, server revalidation, recommendation reasons, independent borrower ID/selfie/signing, Collector cash received/given checks, borrower-only cash receipt confirmation, photo limits and Management activation. Add local Retry for initial/read errors; retry/refresh preserves safe drafts and the common guard. No blanket true/approved interpretation of unknown statuses.

Acceptance: requested `'12000.00'`, approved `'10000.00'`, offset `'1500.00'`, net `'8500.00'` all labeled; locked versus unlocked, zero offset, missing money, declined/office-processing branches, two loans/same names, repeated borrower-level badges, stale/missing request, denied role, failed read recovery, selected photo retention and no automatic financial action.

## C13 — Collector Updates actions (new)

Add own-recipient **Mark as read** through the existing activity API. Validate notification ID and returned identity/recipient/read status before changing that row/count; update locally, preserve unrelated forms and focus, and never touch the financial guard or an unresolved request. Failed reads/mutations remain visible and retryable without pretending success. Distinguish visible records, loaded records and unread records among those loaded.

Related-record actions require an explicit mapping of actual notification producers, type/metadata fields and Collector-authorized destination. Use top-level transaction/remittance IDs or verified producer metadata only after resolving against accessible route receipts, remittances or assigned renewals. Unknown type, malformed metadata, absent target or denied record gets a neutral message/group link with honest wording, never an arbitrary URL or name-based lookup. Navigation cannot accept cash, recommend a renewal or start a payment. Do not claim Support/proof/general borrower notification routing if no Collector contract exists.

Retain C7's 30/60/65 fixture progression and every distinct loaded record. The activity endpoint is limit-only (baseline default100, maximum200); Show more exposes returned records, not lifetime completeness. Do not invent offset paging or fetch more pages from guessed parameters. Test read failure, already-read, repeated clicks, wrong-user result, unknown metadata, same-name records, late response, denial and locked/offline state.

## C14 — Older history, outputs and nonduplicated scope (new)

Include an explicit output/permission matrix in execution evidence: requested surface, current endpoint/source, exact permission and object scope, current UI, implement-now versus follow-up, and acceptance evidence. Cover saved today receipts, older Collector collections, remittance history/detail, printed route ledger, receipt/remittance copies and employee work/pay.

Today receipts and remittance/schedule/renewal details above are implementation requirements using existing APIs. General older-history or print/report centers are not assumed implemented or authorized by this document. Where no verified Collector-scoped endpoint or approved output contract exists, record the precise gap and proposed follow-up, without a fake button, Client-only API, new backend endpoint or broader grant. No actual private PDF output is required in this planning update. Recipient acceptance/rejection stays in its protected role workflow; shared Employee work/pay improvements are coordinated with #487, not recreated here.

## C8 — Integrated acceptance and handoff

C1–C7 remain required; C9–C14 are mandatory additions, not optional notes. Existing task IDs stay stable; the implementation plan inserts 1A, 6A, 6B, 7A, 7B and 7C before final Task8. Every product stage requires a failing behavioral test, focused passing checks, reviewable commit and exact-SHA checkpoint. No test weakening or manufactured green evidence.

Core matrix remains Today, route, Needs attention, Collections & corrections, Remittance, Other-area collection, Renewal handover and My account at1440/390/320 =24 layouts. Add expanded remittance items/refunds/rejected detail, read-only schedule30/120 rows, multiple receipt detail, renewal badge and amount states, and actionable Updates at the same widths; inspect200% zoom, keyboard/focus, reduced motion, long text/money, empty data, permission-limited users and loaded-list limits. Include conditional residence/employee regression without claiming full production/physical acceptance.

Explicit regression cases: malformed remittance resolves to uncertainty; no silent guard reset; full evidence review cannot be bypassed by local navigation; regular/7x7 exact receipts, partial/extra/ADV/correction; stale revision/date/preview, failed post-save read; local draft/photo retention; route-view-only schedule; multi-receipt/renewal exact IDs; notification producer/recipient scope; all-role shared-shell/CSS/PWA and capture-boundary safety. Network requests must be synthetic/disposable, including route GET side effects. Screenshots/DOM overflow checks alone are not full acceptance.

Run existing portal/build/public-output checks and the existing three required CI jobs on the final actual implementation/integration head. Do not duplicate unchanged CI. Pending/Red is not Green; docs-only Green does not prove fixes. Finish with requirement-to-evidence mapping, C14 dispositions, precise unverified items and updated GitHub/Notion/Create State. Report failed connectors explicitly. Leave PR Draft/open/unmerged and owner acceptance/deployment for separate instruction.

Implementation: [2026-10-02-collector-web-ui-completion.md](../plans/2026-10-02-collector-web-ui-completion.md).
