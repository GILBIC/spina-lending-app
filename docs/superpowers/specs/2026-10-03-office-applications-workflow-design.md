# Office Applications: Case Safety, Guided Intake and Search

## Status and owner intent

Design approved for implementation on 4 October 2026, Asia/Manila, when the owner said “Go do it.” The original 3 October request was: “Plan everything and make a PR for this and codex will do it,” following the Office applications screenshot review. Codex is implementing this design on the same draft PR497. The companion plan and acceptance record distinguish completed, reviewed work from remaining implementation and validation. This does not authorize a merge or deployment.

Goal: let authorized Management and Employee/Office Staff start or resume office-controlled applications without losing unfinished work, confusing applicants, inventing reference numbers, or treating navigation as approval. Include the review's protected search/queue enhancement as a separately testable backend-backed phase, not a pretend frontend-only search.

Owner clarification, 4 October 2026: “Also have a list so its easier to remember.” Staff must be able to recognize and reopen saved cases from a visible list without recalling or first entering a reference. This clarifies the existing finder requirement; its implementation is included in the approved work.

Reviewed baseline: `0a576036c9a4b3cfca59ce8120abc86f351ee778` on `GILBIC/spina-lending-app/main`; tree `1484df47171406a359a373a61bba173c6f4a1b94`. [Source review](https://github.com/GILBIC/spina-lending-app/pull/492#issuecomment-5963411048). Management #492 and the shared Employee #494 handoff are already merged. Notion records website #492–495 deployed; this planning session did not independently test signed-in production. Android follow-through #496 is a separate active draft and must not be modified or absorbed. Frozen Master #296 remains unchanged.

## Existing behavior and evidence

| Finding | Source at the reviewed baseline | Disposition |
|---|---|---|
| Lookup input/change clears current intake/review content | `spina_portal/assets/office-onboarding.js`, `invalidate`, `replaceCase`, lookup event bindings | Reproduce and protect deliberate replacement, without weakening privacy teardown |
| New intake resets the case but retains the prior lookup reference | Same module, `renderIntake`; `spina_portal/assets/roles/management.js`, `referencesFor` | Isolate unsaved new intake from old verified identity |
| Matching reference carry, generated application draft references and conflicting-case preservation already exist | #492; `office-application-review.js`; Management workflow binder | Preserve and extend, do not rebuild as missing features |
| Employee uses the same four Office modules with its own navigation binding | `employee-workspace.js`, `employee-office-case.js` | Share case-safety semantics without replacing the Employee shell |
| CIF selection also invalidates children on reference input/change | `office-cif-selection.js` | Cover the adjacent replacement path in the same safety work |
| Intake has exact-reference reads, not general search | `client_onboarding_api.py`, `client_onboarding_repository.py`, #492 scope notes | Add explicit protected reads in the search phase |
| Application headers and immutable versions are separate records | `loan_application_repository.py`, SQL `0120_add_loan_application_history.sql` | Never collapse multiple saved applications into an assumed latest application |
| Actual portal tooling is root npm plus Node scripts | `package.json`, `.github/workflows/spina-ci.yml` | Reuse existing checks; no new framework or duplicate pipeline |

The two reported defects are source-reviewed risks, not proven production incidents or demonstrated backend authorization bypasses. Codex must retain genuine failing-before/fixed-after evidence.

## Global constraints

- Keep the six Management navigation groups and SPINA pink/white visual identity.
- First-loan intake and application remain office-controlled; no public applicant or Client self-application flow.
- Preserve existing role/device/object authorization, exact reference/version checks, and all protected write/uncertain-outcome locks.
- Application/CIF acknowledgment, Management approval, contract signing, release authorization, actual cash receipt and activation remain separate.
- No lending, allocation, interest, payroll, accounting or financial posting rule changes; `automatic_source_posting=false` remains unchanged.
- No new browser persistence of applicant records, search results, references, drafts, files or evidence; no sensitive data in URLs, analytics or logs.
- No new framework, dependency, global store, generic workflow engine or parallel database/source of truth.
- Do not modify frozen Master #296, other active PRs, production data, live permissions, feature enablement or deployment.
- Keep the PR draft/open/unmerged until separately authorized. A documentation or CI pass is not functional or visual acceptance.

## S1. Entry and layout

Keep Clients & loans as the parent destination. Office applications opens a task-oriented entry view with one prominent `New office intake` action and a separate `Continue existing intake` exact-reference form. New-intake helper copy: `Start an intake for an applicant visiting the office. SPINA assigns the intake reference after the record is saved.` Continue helper: `Enter a saved office intake reference to continue this case.`

`Clear search` only empties search text/results. `Close case` changes the active case and invokes replacement protection. Do not use one generic Clear button for both. Hide or disable irrelevant empty actions with a readable explanation where needed. Creating a form is not saving an intake; reference allocation remains the existing server operation.

After the backend search phase, include a compact paginated `Find an intake or application` list in the entry view. Search uses the server; exact-reference continuation remains available when the queue has a recoverable failure. Opening a case collapses the finder to a `Change case` action rather than placing a long list above the editor. Returning to the finder retains its in-memory query/page and focus, but does not silently close a dirty case.

Show `Recent office intakes` automatically when an authorized user opens the Office entry view, using the first server page with an empty query. Staff must not need to type, remember a reference, or press Search to see saved cases. Each row shows applicant name, phone, intake reference, actual intake status, last updated time and a clearly labeled `Continue` action. Keep names and references visible and distinguish applicants with the same name. Label the order `Newest intakes first`, consistent with S4's creation-time pagination; the displayed last-updated time does not change that ordering. Search by name, phone, intake or saved application reference, an intake-status filter and explicit pagination refine this list. Loading, no saved intakes, no search matches and read failure are distinct states.

After opening an intake with a verified client, show its S4 `Applications for this client` list with saved application reference, latest saved version when available and an explicit open action. Do not require staff to recall an application reference, silently select an application or present an intake status as loan approval. Keep the recent-list query/page in memory when returning through `Change case`; replacement and unfinished-work protections still apply.

Do not show all four forms at once. Keep the four recognizable stages: `Intake & requirements`, `Client information (CIF)`, `Loan application`, `Approval & release`. Use a compact secondary task navigation for Clients & loans; do not shrink text until labels fit. Prefer scoped CSS changes. Only adjust shared shell/sidebar breakpoints when measured overflow cannot be fixed in Office content, and then smoke-test all roles.

## S2. Selected case, drafts and replacement

Search text, a candidate lookup, the active verified case and an unsaved new intake are distinct states. No workflow navigation may infer the active identity by reading editable lookup fields.

Use one small mount-owned Office case coordinator shared by the Management and Employee bindings. Keep actual forms/files in their existing mounted modules. Add optional stage-handle registration to the existing mount functions while retaining their callable disposal contracts for other consumers, including Collector residence visits.

The coordinator tracks a monotonically increasing selection generation, owner/session identity, active stage and a minimal case context. Context contains verified applicant/intake/client identities when available and an explicitly selected application identity/version when available. A generated but unsaved application reference is tagged as a draft reference; it is never presented as a saved record. Context is cleared on disposal/denial and is never stored in localStorage, sessionStorage or IndexedDB.

Replacement rules:

| Event | Required behavior |
|---|---|
| Edit lookup or queue search text | Preserve current draft, selected case and controls; do not open or mutate anything |
| Navigate between stages of the same case | Retain forms, File objects and deliberate focus; no automatic save, submit or approval |
| Open a different case, New intake, Close case, replace an already populated destination | Check pending/uncertain writes first; then explicitly confirm discarding unfinished work |
| Cancel discard | Keep exact values, selected files, identity and stage; return focus to the initiating control |
| Candidate lookup fails, mismatches, or loses its selection generation | Do not replace or erase the existing authorized case; show a local failure; a 401/403 invokes privacy cleanup instead |
| Lookup succeeds after the user edits again | Recheck dirty state/generation before committing replacement; old consent to discard must not discard newer edits |
| Start New intake | Detach the old case identity from all stage handoffs; show `New intake — not yet saved`; leave downstream case-specific actions unavailable until their identities are verified |
| Save succeeds but the following read fails | Distinguish the verified saved result from the failed read; preserve the original identity and offer read-only recovery |
| Save outcome is uncertain or a write is pending | Keep original operation/retry identity and block conflicting New/Open/Close/discard actions; navigation must not unlock a second write |
| Access denial, logout, account change, abort, page disposal | Clear private DOM, files, context, queue and child controllers immediately; late responses must remain inert |

Use `You have unsaved changes. Keep editing or discard changes?` for a normal replacement decision. A pending/uncertain financial or intake operation is not discardable by this dialog. Preserve the existing recovery path; search results alone cannot prove that an ambiguous intake submission succeeded, and may not unlock resubmission.

Dirty tracking includes values, checkboxes, selections, child correction forms and selected files. Compare against the appropriate loaded/saved baseline; do not mark a read-only panel dirty. A same-case refresh cannot remove a draft or replace its live File objects. Native browser reload protection may use the existing leave guard only while dirty/pending; no autosave or durable offline queue is introduced.

## S3. Context banner and truthful stage guidance

A compact private banner above the active stage shows applicant name, verified intake reference, explicitly selected application reference when present, and stage-specific server-returned status. Before selection show `No intake selected`. Unknown fields show `Not loaded` or `Unavailable`, never success, zero or complete. A generated application reference is labeled `Draft reference — not saved`.

An intake status and an application/first-loan status must remain separately labeled; intake `eligible_for_cif` does not imply loan approval. A saved application version proves only that version exists. Display exact returned versions and reasons when relevant. Derive no financial amount or readiness from partial display data.

The active-stage accent means `Viewing`, not completed. Completion/blocker indicators come only from the existing verified stage responses. Where no aggregate stage contract exists, say the status is not loaded and offer to open that stage; do not create a second readiness calculator. Preserve manual resumption of an existing later-stage case through protected lookup, including an explicit application choice. Back/Next only navigate; all write buttons remain explicit.

Source identities must agree before showing linked stage facts. Changing intake clears or detaches incompatible downstream selections only through deliberate replacement. Never transfer an application reference across a different client/intake merely because input strings or names look similar.

## S4. Protected finder and saved-application selection

This is a new read contract, not an existing endpoint claim. Implement it as a separately testable phase using current repositories and private-route patterns. Preserve existing POST and exact-reference routes.

### Intake search

Proposed route: `GET /api/v1/management/onboarding/applicants`.

Inputs: `q` (trimmed, empty or 3–200 characters), optional `status` restricted to the existing four intake statuses, `limit` (default 25, range 1–100), optional opaque `cursor` (maximum 2048 characters). Empty query lists recent authorized intakes. Search case-insensitive applicant name/intake reference and linked saved application reference; phone-like queries also compare normalized phone digits. Escape SQL LIKE metacharacters so `%` and `_` are literal input. Parameterize all values and use fixed ordering/columns.

Return `{items, next_cursor, has_more, as_of}`. Each item contains only `applicant_id`, `intake_reference` (mapped from the existing intake `application_reference`), `client_id` or null, `full_name`, `phone_number`, `intake_status`, `created_at`, and `updated_at`. No addresses, ID/evidence references, consent documents, financial amounts or unsaved drafts in the list projection. Deduplicate by applicant ID; using EXISTS for application-reference matching must not fan out one intake into many rows.

Order by intake `created_at DESC, id DESC`; page with the immutable tuple and read `limit + 1`. Cursor decoding is strict and bounded, and binds to the normalized query/status scope. Cursor data is not authorization: every page rechecks the current actor, device, role, permission and repository visibility. Use the same active Employee/Management office authorization as current case reads; do not add company-wide grants or infer a nonexistent area/creator restriction. Tests must prove visibility is no broader than the existing authorized reads.

`as_of` is the time of that response, not a multi-page database snapshot promise. New rows require Refresh; concurrent status changes may affect membership. Use explicit page navigation and stable identity, reset cursor on filter changes, and never claim a complete global count from a page.

### Applications for a selected client

Proposed route: `GET /api/v1/management/onboarding/applicants/by-reference/{application_reference:path}/applications`, with the same bounded limit/cursor rules. Preserve slash-containing references by testing route ordering and encoding alongside `/case` and `/cif-client`.

Resolve the exact authorized intake and its saved `promoted_client_id`; select application headers using that verified client relationship. Do not join by names, phone, a generated-reference prefix or a guessed latest record. Label the panel `Applications for this client`: client linkage does not invent an exclusive application-to-intake association absent from the database.

Return one row per application header, not per version: `application_id`, `application_reference`, `client_id`, `created_at`, and latest saved `application_version_id`, `version_number`, `recorded_at` when available. Do not invent a loan-approval status on the application header. Use immutable header ordering and a bounded current-version lookup. A not-yet-promoted intake returns an authorized empty application list with its verified intake context, not a made-up client.

Selecting a row is explicit even when there is one result; multiple applications remain independently reachable. Opening a row verifies the intake/client/application pair through existing protected detail readers before enabling stage work. Not found/changed/denied results cannot silently fall back to a different application.

### Privacy, performance and scope

Use the existing authenticated device context, private/no-store response behavior and repository-level active-role/permission check. Return no private data in success or error caches; validation errors must also be no-store. Clear loaded results on denial/account change; protect the queue/banner with the existing private-screen/capture boundary, without adding capture eligibility.

No public search, bulk export, batch approval, automatic duplicate merge, assignment system, global status counters, materialized workflow table or browser database. Search terms must not enter browser navigation URLs or analytics; inspect request logging/redaction so names/phones are not recorded in access logs. Reuse current privacy routing; stop for a narrowly scoped privacy fix if query parameters are logged unredacted.

Start with existing tables/indexes. Measure a synthetic query plan including name, phone and application-reference cases. Add only a justified index migration if evidence shows it necessary; select the next free migration number at execution time and never modify historical migrations. No new extension, trigger, SECURITY DEFINER function, live grant or data backfill is justified by this finder.

Aggregate queues such as `Ready for release` are not invented from the four intake states. The finder shows actual intake state and explicit saved applications; full approval/release state remains in the existing selected-case workflow. Extending cross-case readiness requires its own authoritative contract and recorded approval, not silent expansion of this plan.

## S5. Responsive and accessible acceptance

Verify actual built production modules using synthetic accounts and records. Core viewports: 1440, 1280, 1024, the supplied 997×857 condition, 768, 390 and 320 CSS pixels. Test browser 200% zoom, keyboard-only operation and reduced motion. Keep readable typography and approximately 44-pixel primary touch controls as a design target; do not claim formal accessibility certification from these checks.

At intermediate desktop widths the top task navigation and four stages must not push the small entry form far below the heading. Use restrained card borders/pink accents, compact heading spacing and a deliberate 2×2 stage arrangement when four columns cease to fit. Phone lists become labeled cards; do not allow page-wide horizontal overflow or hide application IDs behind clipping. Long names, long references, validation messages and returned blockers must wrap without overlapping actions. Use visible focus, properly associated labels, polite read feedback and focus-safe errors. Do not mislabel button groups as ARIA tabs without implementing tab keyboard behavior.

Validate Management and Employee Office flows, plus smoke tests for Collector/Client shells and Collector residence visits when shared code/CSS changes. Do not change Android #496 or claim phone/emulator/physical cash acceptance from browser screenshots.

List acceptance: in both authorized Office roles, open the entry view and resume a synthetic saved case from the visible first page without typing any reference. Repeat with duplicate names, a name search, a later page and a client with multiple saved applications. Verify the exact selected case/application, distinct loading/empty/error states, retained finder position and draft protection. At narrow widths use labeled cards with a visible Continue action.

## S6. Completion and exclusions

Complete means both safety regressions reproduced and repaired; preserved #492/#494 behavior; truthful new/continue entry and case context; protected finder/picker with real database tests; responsive/browser/privacy acceptance; and exact-implementation-head CI evidence. Every task needs evidence rather than checked boxes based on planning.

The implementation belongs on this same branch/PR. Its acceptance record must distinguish synthetic browser and disposable-database checks from production or physical acceptance. No money movement, production setup, merge or deployment is included. Preserve this design and the companion task ledger, and synchronize meaningful progress to GitHub, Notion and the local continuation pointer without overwriting concurrent work. The owner's prior refusal of Create State remains in effect.
