# SPINA Management Web UI Completion — Design and Acceptance

Date: 2 October 2026 (Asia/Manila). **Revision 2: original UI review plus functional re-review.**

## Status, ownership, and authority

**Planning only, on existing Draft PR #485.** The owner first requested “Plan everything and create a pr i will make codex do this” and, after the functional re-review, “Update the current pr and include thing everything.” This revision incorporates every finding from both reviews into the same design, implementation checklist and acceptance ledger. The owner will start Codex separately. Publishing this revision does not implement fixes, start an agent, mark ready, merge, deploy, run migrations or authorize production operations. Keep #485 Draft/open/unmerged with automatic merge off.

Reviewed main: `41a13eb59c9cc1b65a0a6a51f3b73db4a0895013`, after merged #484. Previous planning head: `7fdf54edad8186bd0dca6d7209aeac68dbce48e1`. Same branch: `plan/management-web-ui-completion-20261002`. Original requirements R1–R7 and Tasks 0–8 are retained; new R8–R14 and inserted tasks are mandatory before final Task 8. Older integrated PRs #466–#484 are not outstanding implementations. Frozen Master #296 is unchanged.

Read before asking the owner to repeat decisions:
- [Frozen Master #296](https://github.com/GILBIC/spina-lending-app/issues/296) and [release #484](https://github.com/GILBIC/spina-lending-app/pull/484).
- [Original detailed review](https://github.com/GILBIC/spina-lending-app/pull/484#issuecomment-5942508315), [earlier error findings](https://github.com/GILBIC/spina-lending-app/issues/448#issuecomment-5942333897), and [functional re-review addendum](https://github.com/GILBIC/spina-lending-app/pull/485#issuecomment-5943820685).
- [Notion Current Project State](https://www.notion.so/3cd5ade7bef48106b2c2ff97182001dd), newest Management checkpoint.
- Create State project `69a61c48-f842-44ac-aa11-e987ffec4a36`; semantic results may be older than exact GitHub/Notion evidence.
- Separate Collector #486, Employee #487, and Client #488 workstreams. Recheck live heads/diffs before execution rather than assuming their planning state persists.

Review evidence was local Chromium with released assets and synthetic responses, including 18 core layouts at 1440/390/320px. It was not signed-in production acceptance, a live latency measurement, physical cash acceptance, real renewal approval/signing/release, a document export, or complete security/native acceptance. `SPINA_Management_Functional_ReReview_41a13eb5.zip` and previous review archives are optional conversation artifacts, not guaranteed Codex workspace files. Reproduce the documented cases when absent.

## Goal, selected approach, and coordination

Make Management work accurate, complete for existing protected workflows, state-preserving, readable on phones and easy to reach. Preserve **Today / Clients & loans / Collections / Accounting / People & operations / Account**, their IDs and the pink/white identity. Reuse guided Office intake/CIF/application/first-loan, proof review, account/device/credential controls, collection/void/history/past-due, accounting/capital/tax/ECL/close/journal/statements/export, Employee Operations, Support and Area Management. Source presence is not full acceptance.

Selected approach: targeted existing ES-module changes, focused renewal and remittance integration, and small mount-local controllers. A CSS-only patch leaves false results and unusable workflows. A framework/router/accounting rewrite duplicates working behavior. Neither is selected.

Keep this branch separate. Before editing shared `app.js`, `ui.js`, `app.css`, `payment-proofs.js`, `remittance-review.js`, Employee/Office helpers or `sw.js`, inspect #486/#487/#488 and record one integration owner/order. In particular reuse Employee #487's verified remittance Reject/recovery work when available; do not create a competing receiver implementation. Reuse one compatible optional shell lifecycle hook, not a fourth routing/refresh registry. Do not import unmerged role-specific controllers or overwrite another executor's work. Continue nonoverlapping tasks while a shared dependency is resolved, but leave integration acceptance pending.

## Permanent boundaries

- Web Management is the change surface; other roles, Desktop and native Android/iOS are regression surfaces, not redesign targets.
- Keep endpoint paths, query/body semantics, server RBAC and object scope, exact decimal money, source ordering and role precedence. No new endpoint/schema/grant, financial calculator, inferred balance/allocation, penalty/schedule/tax/ECL policy or partial-list total.
- Protected writes remain online-only. Keep confirmations, duplicate-submit locks, exact supported retry identity, expected-version/conflict checks, uncertain-result reconciliation, independent approvals and immutable financial/audit records. A resolved promise is not verified success. Do not invent request UUID/digest/version fields a contract does not accept.
- Cash Disbursement prepares an expense draft; it does not send money. Employee stays prepare-only and Management posting remains separately gated. `automatic_source_posting=false` remains unchanged.
- Drafts and selected files remain only in the current mounted session; no new localStorage/sessionStorage/IndexedDB/URL/service-worker persistence. Retained text is not retained authorization. Logout, role/device/identity change or expiry disposes private data; ordinary token rotation must not erase existing uncertain-request recovery. Do not extend password/one-time-secret lifetime.
- Preserve borrower/email stale-selection invalidation, device protections, password/reset separation, journal deduplication, posting/reversal rules and private-screen boundaries. New private detail/photo panels are not capture-eligible by default.
- No real credentials, payments, cash receipt, signatures, photo/proof uploads, screen sharing/capture, migrations, delivery/deployment, dependency upgrades, CI weakening or Master acceptance edits. Some GETs can finalize financial state; use synthetic/disposable fixtures, not production probes.

## R1 — Truthful portfolio states and recovery (retained)

The initial failed loan read renders four false zeros; a later successful Search replaces cards without updating that summary. Fix both. The existing `GET /api/v1/management/loans` returns global active `summary` separately from filtered/paged `loans`. Label them **Active portfolio · all clients** and **Search results**. A paid/no-match search is not an empty active portfolio.

Loading shows dashes and Loading. Failure shows dashes, **Portfolio summary unavailable** and local Retry preserving query/status/page. Success updates summary and results from the accepted response. Validate fields independently: null/missing/invalid is unavailable; explicit zero is real. Preserve exact decimal strings; no `?? 0` or `|| 0` missing-value substitution. Last-request and mount/session guards reject earlier or aborted responses. Limited rows are not all records. R10 now adds the previously omitted paging requirement.

Acceptance: initial failure; recovery with ten sample loans; true zero; missing fields; paid/no-match with nonzero global summary; partial pages; rapid searches and logout during a read. Expected totals come from fixture summary, never cards.

## R2 — Preserve unrelated work through saves and refresh (retained, extended)

Ordinary navigation already preserves inputs. Replace Support, renewal and staff-invitation full-workspace success remounts with affected-region refresh. Apply the same rule to new R8/R9 actions. Clear only the confirmed submitted editor; retain other draft nodes, file inputs, search/status/page, Office references, local task selection, focus and scroll context.

Distinguish **Saved; refresh failed** from failed or uncertain mutation. Preserve confirmed result evidence and do not offer a duplicate write. Refresh dashboard/global counts from authoritative reads, not local arithmetic. Preserve another queue row's unsent response. Changed versions/permissions/readiness invalidate actions without silently attaching a new review version to an old draft.

Routine header/local Refresh retains unrelated inputs and does not replace workflow locks. While a write is in flight, block/defer destructive refresh. If a dirty same-task form cannot safely refresh, require a deliberate discard choice; never use that as permission to discard an uncertain command. Explicit reconciliation is distinct from ordinary refresh and remains blocked until current authoritative evidence resolves the outcome. Authentication/authority changes retain stronger teardown rules.

Acceptance: search + intake + another support draft + selected proof file survive unrelated verified Support/renewal/staff/remittance actions; same-record conflict; mutation success/read failure; manual Refresh; double click; abort; same-user token refresh; identity/permission change. Do not manufacture successful legacy renewal approval fixtures: use R8's real terms contract.

## R3 — Independent Today and guarded task loading (retained)

Render shell/placeholders promptly; load account and dashboard independently. Today never awaits loan operations, portfolio lists, statements, journals, trial balance, audit, staff, renewals, remittance, personal Updates or proof lists. Use authoritative dashboard queue metrics or explicit unavailable counts/neutral links, not zeros from unopened tasks.

Load secondary data AND module mounts on first activation. Deduplicate activation reads/listeners, retry locally and retain mounted editors through navigation. Use current session getters, per-mount generations/abort and child cleanup. Late data cannot cross identity or permission boundaries. New renewal/remittance controls must obey current online/uncertainty state even if mounted after a lock. Initial account/dashboard failure must not destroy unrelated authorized read navigation.

## R4 — Staff phone readability and device focus (retained)

Reuse `mobile-card-table` below the existing 680px breakpoint with Staff-scoped labels/classes; retain the seven desktop columns. Phone cards prioritize name/status, role/device count and readable Manage devices/View account. Keep username/email/date accessible without shrinking fonts or 48px controls. Preserve exact IDs/counts, selected row and permission-specific actions.

Opening current device detail moves focus into its heading/Close only if the user has not deliberately moved elsewhere. Close returns to the exact opener or visible Staff heading. Late responses cannot steal focus. Test long names/emails, 390/320px, read-only account access, rapid selection, busy/error/denied states and opener removal. No-overflow alone is not readable UI acceptance.

## R5 — Focused local tasks and precise destinations (retained, extended)

Keep six top-level groups and IDs. Use local permission-filtered hide/show views, not duplicated workflows:

| Group | Local tasks; first permitted is default |
| --- | --- |
| Clients & loans | Portfolio; Office applications; Renewals; Payment evidence; Client accounts |
| Collections | Collection actions; Loan operations & history; Past-due report; Remittance review |
| Accounting | Financial statements; Journal & Trial Balance; Cash Disbursement; Accounting workflows |
| People & operations | Staff & devices; Areas; Employee work; Client support; Alerts & audit |
| Account | Profile & security; My updates |

Preserve the four guided Office steps and reference revalidation, existing collection-action subviews, journal/TB controls, and accounting capital/source/tax/ECL/close workflows. No new financial Overview calculation. Task choice stays mount-local and keyboard-operable with clear selected state.

Map known alert codes to actual tasks: staff_devices -> Staff & devices; renewals -> Renewals; support -> Client support; client_registrations -> Client accounts; financial_accounting -> Accounting workflows; remittance_review -> R9's recipient remittance queue. A permitted receiver must reach real review, not a collection-history placeholder. Wrong/absent authority gets an honest unavailable/read-only destination. Unknown codes are noninteractive; do not invent object IDs or URL targets. Personal unread shortcuts go to My updates, not audit.

Before hiding/replacing an active or preparing captured panel, stop/invalidate existing capture and re-evaluate eligibility. Preserve exact `data-screen-share-section` markers; never move one to the group ancestor or make new private financial/photo panels eligible. Test mocked tracks/visibility, not real capture.

## R6 — Compact audit/device presentation, evidence retained (retained)

Keep all authorized loaded records and original order/identity. Device filters remain All/Active/Pending/Revoked with counts. First account-open defaults Pending if present, else Active if present, else All; explicit selection persists through refresh even if empty. Show 10 matching rows, add 10 per Show more and label visible/loaded counts. All reaches unknown statuses. Actions retain original device identity after filtering.

Audit uses compact rows and expanded facts, first 10 matching events then batches of 10. Preserve severity, timestamps, maker/checker/reason, `visible_domains`, `window_days=30&limit=100`, and immutable event identity. Filter resets cap, not data. Distinguish server authorized total/time window from loaded/visible rows. Do not delete or deduplicate similar-looking evidence. Test 36 devices/two Pending; audit 0/12/100, unknown domain and server total greater than loaded.

## R7 — Targeted density and copy polish (retained)

Today keeps Portfolio/Collections and prioritizes nonzero attention/useful actions; verified zero queues become compact but remain accessible. Unavailable never becomes nothing to do. Do not invent metrics/charts. Cash Disbursement mounts only on task selection; retain Prepare draft, does-not-send-money wording, receipt requirements, uncertainty recovery and separate posting. Purpose/evidence fields use full-row width; no new uploader/schema.

Account profile targets max-width 720px, fluid on phones; keep Workspace/Additional access and My password/admin reset distinct. Reuse colors/spacing/48px controls/readable typography/reduced motion and primary/secondary hierarchy. Remove only redundant nesting/copy, not warnings or status. Shared CSS/helper changes require other-role regression.

## R8 — Real Management renewal workflow and verified decisions (new)

Stop offering approval through legacy `POST /api/v1/management/renewals/{id}/review`; its repository explicitly refuses approval. Do not weaken that backend guard. Use `GET /api/v1/management/renewal-workflow?status=pending|approved|rejected` and protected `POST /api/v1/management/renewals/{id}/terms`, under current `renewal.manage` authority.

Render borrower/loan/request identity, requested/current amounts, Collector recommendation/reason/comment, client message, approved terms, override/review note, signers and readiness, office-processing, locked offset/net cash, custody/photo/activation states. Missing money/readiness is unavailable, not zero/approved. The richer query is capped at 200 per status at baseline, not lifetime history. Show returned-count limitations without invented offset support.

Terms form: approved principal (exact decimal input), required signer parties/account identities, office-processing choice, review note and override reason where required. Missing Collector recommendation blocks decision; do_not_recommend requires actual Management override explanation. Rejection requires reason. Signer identity verification is an explicit evidence-backed act, never a default checked flag; do not guess account IDs from names or mark absent evidence verified. Preserve own-account signing and borrower-only acceptance/cash confirmation. Office-processing shows the existing boundary, not a new remote bypass.

Connect authorized continuation using existing release-to-collector, handover-photo view, proof-review and activate contracts. Validate prerequisites and returned same-request state; never calculate offset/net locally. Cash lock requires authoritative execution; missing execution/CIF/readiness gets a truthful blocker. Proof viewing is private and current-request scoped; no external storage or shareable URL. Clear/revoke photo objects on switch, denial and disposal.

**Important existing behavior:** approving handover proof can call `_try_activate` inside the backend. Confirmation must disclose that approval may also activate if requirements pass. Do not promise review-only effects or automatically call activate again. A successful photo review can remain activation-blocked after CIF changes; show saved review plus the separate blocker. Explicit Activate is only for eligible pending activation, with a separate deliberate action.

Before each consequential action, re-read the appropriate authorized request/evidence and invalidate changed terms/selection/confirmation. Do not claim a client-side read atomically pins a server revision. Current endpoints do not all accept expected versions/request UUIDs, and latest-photo review has version/concurrency limits; do not invent request fields. Map exact available metadata and disclose an unresolvable pinning gap under R14 instead of faking proof certainty.

Verify response request ID, borrower/loan identity, expected action-specific status/fields and exact approved amount where applicable. `{}`, wrong ID, contradictory status, timeout/5xx or unknown outcomes must not announce approval/release, discard the attempt or automatically POST again. Retain blocked state and reconcile by authoritative read; a read that cannot disambiguate remains blocked. Mere HTTP success is insufficient. Keep later borrower/signature/custody/activation events independent.

Acceptance covers recommended/not-recommended/missing recommendation, principal/signers/override, office-only, same-name borrowers, all statuses, malformed results, concurrent change, double click, denied/offline, saved review/CIF activation blocker, proof approval with/without activation, private photo disposal and no auto-repeat.

## R9 — Management recipient remittance review and history (new)

Mount the existing shared `remittance-review.js` path inside Collections for the actual permitted receiver; role registry metadata is not a screen. Reuse authorized `/api/v1/notifications` and `/api/v1/remittances` reads. Distinguish `remittance.view` from `remittance.receive`; view-only has history, not receive controls. Current shared review requires both and exact actor-recipient identity. A Management role is not authority to receive for another recipient or accept its own outgoing cash.

Use the existing notification acceptance contract `/api/v1/notifications/{id}/accept-remittance` when reusing the receiver component, and the existing `/api/v1/remittances/{id}/reject` for rejection. Do not issue both notification acceptance and raw receive for one action. Acceptance returns notification-shaped custody confirmation; rejection returns a remittance record. Validate them separately. Retain raw receive as an existing backend capability, not a second UI path.

Load and verify the complete matching pending record: sender/recipient/date, exact total/counts, all payment items/receipts/covered dates, refund outflows/evidence, notes and saved status/history. Missing/malformed/inconsistent evidence blocks decisions; it is not empty. No local sum, second manually entered remitted total or shortage tolerance is introduced.

Both decisions require full-evidence review acknowledgment. **Accept cash custody** additionally requires the user to confirm physically receiving/counting cash equal to the server total. **Reject remittance** requires a reason, but never requires falsely affirming receipt of matching cash. Close is not Reject. Confirmations invalidate on different record, changed evidence or authority. Sender responsibility is not cleared until verified server acceptance.

Use one decision lock for Accept/Reject. Wrong identity/status, `{}`, timeout or ambiguous outcome blocks both; do not auto-retry or switch decisions. Reconcile exact notice/remittance status with current reads; failure or ambiguity stays locked. Verified success updates only affected notice/detail/counts; preserve unrelated drafts. Show submitted/reviewed/received/rejected times and reason without changing immutable history. Add initial/detail local retry and open/Close focus restoration, respecting user movement.

Coordinate extension with Employee #487 and Collector #486; keep the shared cleanup return and other-role behavior compatible. Collector sender review does not gain receiver authority. Notifications/records not belonging to the actor remain nonactionable even if injected in fixtures.

## R10 — Loan detail and complete supported portfolio browsing (new)

Add View loan details from the exact loaded `loan_id`/`client_id`, not borrower-name fallback. Display existing API facts: principal/balance/agreed daily amount, paid amount/percentage, release/due/last-payment/ADV dates, PASS and payment counts, renewal status, loan/client status and source state version when useful. Missing values are unavailable; no local percent or balance calculation. Keep cards compact and detail mobile-readable with Close/focus. Refresh invalidates a changed/removed selection. Viewing never opens an editor or grants broader borrower access.

Add Previous/Next page with explicit `limit=100` and `offset` using the existing query/status contract (max limit 200, not a reason to request everything). Changing query/status resets offset to zero. Fewer than 100 returned rows ends that query page chain; a full page may offer Next, and an empty next page remains honest/recoverable with Previous. No invented total/has_more/cursor; global active summary is not a filtered-results total. Show current page and number of returned loan entries, preserve server order/IDs, update R1 summary from each accepted response and reject stale searches/pages. Offset paging is not a stable snapshot under concurrent writes; disclose changed results and provide fresh search/refresh.

Test 150 global loans with 100 then 50 returned, zero/paid/no-match, failed next page, rapid queries, repeated names, two loans/client, missing detail fields and removal/denial. Broader borrower schedule/statement/document controls are R14 contract assessment, not Client/Collector endpoint reuse.

## R11 — Financial statement period selection and local recovery (new)

Extend the existing statements loader to accept `period_id`; reuse authorized `fiscal_periods` from `GET /api/v1/management/financial-accounting` rather than inventing a GET fiscal-periods endpoint. The statements API still requires Management plus `accounting.view`. Share an existing successful read within the mount when safe, without eagerly mounting the full accounting editor.

Default selection follows the returned default statement's period; explicit selection loads `/api/v1/management/financial-accounting/statements?period_id={uuid}`. Show period label/dates/status from the returned pack. Validate response period equals explicit selection; Loading/unavailable replaces current-looking figures during switches, with local Retry preserving selection. Late period A cannot overwrite B. No-period, denied and removed-period states are distinct; no auto-create/reopen or writes.

Keep posted-General-Ledger-only totals, exact amounts, draft exclusion, closed-period rules and existing financial statements/journal/TB/export. A period selector does not deliver a new printable statement pack. R14 maps additional output requirements.

## R12 — Personal Updates separate from audit (new)

Add My updates inside Account and a truthful Today unread shortcut without adding a seventh top-level group. Use own-recipient `GET /api/v1/activity-notifications` and `/api/v1/activity-notifications/{id}/read`. Initial load is local/on demand, not a Today prerequisite. Validate notification/recipient/read state and update the affected row only; failed or wrong-user result is not success. Audit is permanent evidence and is never marked read in place of personal updates.

Show 30 loaded records then batches of 30, preserving all distinct returned items/order; fixture 65 progresses 30/60/65. Baseline API is limit-only (default100/max200); do not invent offset paging or lifetime completeness. Visible/loaded/unread-among-loaded and authoritative dashboard unread totals are distinct. Refresh global metrics authoritatively, not by assuming the loaded list is complete.

Related-record links require verified producer type/metadata and current authorized object resolution. Remittance goes to the actual recipient queue; loan/renewal/Support uses exact owned/permitted IDs. Unknown/malformed/absent target stays neutral or an honestly labeled queue link, never arbitrary URLs or a financial action. Retain draft nodes, guard locks and focus on local reads/mark-read/navigation; abort across scope change.

## R13 — Local proof retry and supported queue history (new)

Initial Management payment-proof list failure must retain a local Retry control. Keep paging/current-version review/correction history, no-payment-posted wording, byte/file validation, role mode and exact uncertain-submission lock. Retry replays a read only; it cannot clear an unresolved review or remount a dirty editor. Coordinate `payment-proofs.js` with #488 and preserve Client upload/file behavior.

Renewal status/history is covered by R8's richer pending/approved/rejected query. Support adds local status filtering/paging from actual `SupportStatus` and existing Management support API; map the executable allowed values before binding controls, with no invented all-status query. Preserve current review actions, another row's unfinished response and changed-state checks. History is read-only unless the backend currently authorizes an action. Unknown/failed/denied is not an empty queue. Refresh, filter changes and selected-object links follow R2, including deliberate discard for unavoidable same-editor replacement.

## R14 — Borrower/report/output and integration gap register (new)

Complete an evidence-backed matrix: requested screen/output; existing endpoint/source; exact role/permission and object scope; available fields; implement-now versus blocked/follow-up; tests/evidence. Cover Management borrower details, broader schedules/statements/receipts/issued documents, financial-statement print packs, existing accounting-review ZIP, renewal office-processing/execution/photo-version limits, receiver-vs-sender remittance actions, unsupported notification identifiers and shared Employee work/pay.

Existing supplied-field details, pagination, periods, renewal workflow, remittance receiving, personal Updates and local recovery above are required implementations—not optional assessments. For a missing broader output contract or unsafe metadata/version gap, record the precise blocker and smallest proposed follow-up. Do not create fake buttons, reuse Client-only/assigned-Collector APIs, query financial tables directly, expand grants or claim that a disabled stub is completion. No new endpoint/backend change is authorized by this planning revision. Share Employee work/pay improvements from #487 rather than rebuilding them inside Management.

## Integrated acceptance and handoff

Every original R1–R7 and new R8–R14 needs an explicit implementation/test or documented contract-gap disposition. Task IDs remain stable with inserted stages. Product stages use failing behavioral tests, focused passing checks, reviewable commits and exact-SHA checkpoints. Do not weaken identity/permission/uncertainty assertions or count an old docs-only Green as implementation evidence.

Keep 18 core layouts (six groups at1440/390/320) and add renewal terms/all continuations and blocked states, full remittance evidence/rejection/history, paged loan detail, periods, Updates and failed-proof retry at those widths. Include long names/money, 36 devices/two Pending, 100 audit records, 150-loan paging, 65 updates, empty/malformed/error cases, keyboard/Close/focus,200% zoom/reduced motion. Browser screenshot/no-overflow alone is not functional/security acceptance.

Test exact malformed-response behavior, selected-record changes during reads/confirmations, proof-review automatic activation semantics, recipient mismatches, online-only/uncertain locks, same-user token refresh, authority teardown, privacy and other-role shared-shell/CSS/helper/PWA regression. Use mock/disposable data, never live financial probes. Verify public output contains no private/test data and new modules upgrade coherently.

Run existing portal/build/public-output checks and the three required CI jobs on the actual final integration head without duplicate unchanged validation. Keep pending/blocked items explicit. Synchronize GitHub, Notion and Create State with exact branch/head, completed/pending stages, checks, evidence, R14 dispositions and next action; disclose failed connectors. No merge, mark-ready, deploy or Master acceptance is authorized.

Implementation checklist: [2026-10-02-management-web-ui-completion.md](../plans/2026-10-02-management-web-ui-completion.md).
