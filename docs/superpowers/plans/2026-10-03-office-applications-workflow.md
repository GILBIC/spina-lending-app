# Office Applications Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Office applications safe to start/resume, clear to navigate and searchable through protected backend reads.

**Architecture:** Keep the four current Office modules and both role shells. Add a small mount-owned case coordinator and optional stage handles, then two bounded read endpoints using existing authorized intake/application sources. No new workflow database or frontend framework.

**Tech Stack:** Existing JavaScript ES modules/CSS, root npm/Node tooling, FastAPI, PostgreSQL/psycopg, pytest and the existing browser/disposable-database verification setup.

**Spec:** `docs/superpowers/specs/2026-10-03-office-applications-workflow-design.md` (read in full first).

**Status:** Implementation authorized on 4 October 2026 by “Go do it.” Codex is executing this plan on the same draft PR497; checked tasks have scoped evidence in the acceptance record. Remaining work is kept unchecked. Implementation does not authorize merge, deployment or production operations.

**Owner clarification, 4 October 2026:** “Also have a list so its easier to remember.” Tasks 6–8 must deliver a visible recent-intake list on entry and an explicit saved-application list, so staff can recognize and resume a case without remembering references. This is a requirement update, not completed implementation.

## Global Constraints

- Keep the six Management navigation groups and SPINA pink/white visual identity.
- First-loan intake and application remain office-controlled; no public applicant or Client self-application flow.
- Preserve existing role/device/object authorization, exact reference/version checks, and all protected write/uncertain-outcome locks.
- Application/CIF acknowledgment, Management approval, contract signing, release authorization, actual cash receipt and activation remain separate.
- No lending, allocation, interest, payroll, accounting or financial posting rule changes; `automatic_source_posting=false` remains unchanged.
- No new browser persistence of applicant records, search results, references, drafts, files or evidence; no sensitive data in URLs, analytics or logs.
- No new framework, dependency, global store, generic workflow engine or parallel database/source of truth.
- Do not modify frozen Master #296, other active PRs, production data, live permissions, feature enablement or deployment.
- Keep the PR draft/open/unmerged until separately authorized. A documentation or CI pass is not functional or visual acceptance.

## Review Focus

1. Candidate lookup returns after another edit or cancelled discard: new work and active identity must survive (Tasks 1–3).
2. A pending/uncertain write outlives a stage change or Refresh: original operation identity stays locked and no second write starts (Tasks 1–4).
3. One promoted client has several saved applications and versions: all application headers remain reachable and no implicit latest selection occurs (Tasks 6–7).
4. Permission/device revocation occurs between paginated reads or a delayed callback: current and detached private UI clears and nothing resurrects (Tasks 4, 6–8).
5. Long names/references, slash references and intermediate viewport widths: correct routing, unambiguous case context and readable keyboard operation (Tasks 3, 5–8).

## File and interface map

Existing paths are baseline references, not permission to refactor unrelated content:

| Area | Existing files to inspect/modify narrowly |
|---|---|
| Management Office assembly/navigation | `spina_portal/assets/roles/management.js`, `management-workspace-tasks.js` |
| Employee shared Office integration | `spina_portal/assets/employee-workspace.js`, `employee-office-case.js` |
| Intake/CIF state and forms | `office-onboarding.js`, `office-cif-selection.js`, `office-cif-correction.js`, `office-cif-workflow.js` under `spina_portal/assets/` |
| Application/release state and child editors | `office-application-review.js`, `office-application-entry.js`, `office-first-loan.js`, `office-evidence-capture.js` under the same assets directory |
| Styling/build | `spina_portal/assets/app.css`, `package.json`, `tools/check_portal_modules.mjs`, `tools/build_portal.mjs`; find current PWA asset/cache registry before changes |
| Protected reads | `gilbic_backend/src/gilbic_backend/client_onboarding_api.py`, `client_onboarding_repository.py`, `loan_application_api.py`, `loan_application_repository.py` |
| Data/verification references | `gilbic_backend/sql/0120_add_loan_application_history.sql`, `docs/operations/office-first-loan-verification.md`, `.github/workflows/spina-ci.yml` |

Proposed new files: `spina_portal/assets/office-case-context.js`, `office-application-finder.js`; matching tests `spina_portal/tests/office-case-context.test.mjs`, `office-application-finder.test.mjs`, `office-workflow-case-safety.test.mjs`, `office-workflow-layout.test.mjs`; backend tests `gilbic_backend/tests/test_office_application_search_api.py` and `test_office_application_search_repository.py`; evidence ledger `docs/reviews/2026-10-03-office-applications-acceptance.md`.

Do not add a new backend router/service merely for separation: extend the current onboarding router/repository unless a small existing helper is reusable. Keep SQL/private-route responsibilities in their current layer. Do not rewrite the broad role modules.

### Proposed minimal frontend seam

`createOfficeCaseContext({getSession, confirmDiscard, onChange}) -> coordinator` in `office-case-context.js`. The coordinator owns selection generation and the active verified context, not financial readiness or a copy of each form.

Existing mount functions gain optional `registerHandle(handle)` and `onContextChange(context)` arguments while retaining callable dispose return values. A registered stage handle exposes `getContext()`, `isDirty()`, `isWritePending()`, `isUncertain()`, `openCase(selection)`, `resetCase()`, `refreshReadOnly()` and `dispose()`. Existing names may be adapted internally, but the shared contract must be identical in both role bindings. `openCase` is a protected read; neither it nor stage navigation creates a draft on the server. `resetCase` is callable only after the coordinator accepts replacement and never bypasses pending/uncertain locks. Disposal remains unconditional for privacy.

Context fields: `mode` (`none`, `new-intake`, `saved-case`), `applicantId`, `intakeReference`, `clientId`, `applicationReference`, `applicationId`, `applicationVersionId`, `applicationSaved`, and current verified stage facts. Missing identities are null. Draft refs use `applicationSaved=false`. Facts carry source identity and cannot be mixed across clients/versions. Use the existing module snapshots rather than a second readiness store.

Coordinator operations: `registerStage(stage, handle)`, `getContext()`, `requestTransition({kind, targetStage, candidate}) -> Promise<boolean>`, `acceptVerifiedContext(context, generation) -> boolean`, and `dispose()`. Kinds are `navigate`, `open`, `new-intake`, `close`. A transition returns false without replacement when cancelled, stale, denied or locked. The caller must not navigate after false.

### Proposed backend seam

`PostgresClientOnboardingRepository.search_office_cases(*, actor_user_id, q, status, limit, cursor) -> dict` and `list_office_applications(*, actor_user_id, application_reference, limit, cursor) -> dict`. Routes and exact minimal response fields are specified in S4. Apply current API/device and repository authorization independently; a decoded cursor or frontend context never establishes authority. Reuse the existing private-route/no-store pattern for all responses, including validation errors.

## Task 0 — Reconcile authority and establish a reproducible baseline

**Files:** Read the spec/map above, current PR/main, #492, #494, active #496, frozen #296, latest Notion and the local continuation pointer. Preserve the owner's prior Create State refusal. Create the acceptance ledger only after execution begins.

- [x] In an isolated worktree on this PR branch, inspect existing changes and instructions. Do not reset/stash/remove another worker's changes. Record exact branch/head/main and overlap; preserve #496 and the Android → Cash/GCash → surplus workstream.
- [x] Resolve the actual Employee/Management handle and PWA seams; record source locations. Inspect the existing private route and request logging configuration before finalizing new search routes. Confirm that current table ownership and visibility match S4, without assuming absent creator/area scopes.
- [x] Run `npm test` once for the baseline, then `node tools/build_portal.mjs`. Capture existing failures as baseline failures, not feature regressions or silent skips. Read the current disposable Office verification runbook for real-database setup; use synthetic data only.
- [x] Add the two original source-review scenarios to the evidence ledger as NOT YET REPRODUCED. Map S1–S6 and Review Focus items to Tasks 1–9. Commit the baseline ledger with exact command outcomes, not successful-implementation claims.

## Task 1 — Reproduce replacement defects and add the small context boundary

**Files:** New `office-case-context.js`, `office-case-context.test.mjs`, `office-workflow-case-safety.test.mjs`; existing intake and both navigation bindings.
**Consumes:** Existing mounted forms, session getter and pending/uncertain state.
**Produces:** Coordinator contract above with two verified regression reproductions.

- [x] Write failing tests `lookup_edit_keeps_unsaved_intake_and_file`, `new_intake_never_carries_previous_case_to_cif`, `cancel_discard_keeps_exact_dom_and_selection`, and `stale_lookup_cannot_commit_replacement`. Assert both unchanged form values/File identity and absence of unintended API writes; test actual module bindings, not a lookalike implementation.
- [x] Run `node --test spina_portal/tests/office-case-context.test.mjs spina_portal/tests/office-workflow-case-safety.test.mjs`. Record each expected product failure; an import/harness failure is not proof of the reported bug.
- [x] Implement only mount-owned context, generation/owner checks and the explicit transition contract. Preserve callable cleanups and reference matching from #492. Do not copy private form payloads into the coordinator.
- [x] Rerun the focused tests and existing Office tests. Demonstrate failure against the preceding source and pass against the fix. Commit `fix: isolate Office case context from lookup text` with evidence.

## Task 2 — Protect intake/CIF drafts and isolate New intake

**Files:** `office-onboarding.js`, `office-cif-selection.js`, affected child CIF editors, both navigation bindings and Task 1 tests.
**Consumes:** Coordinator and stage registration.
**Produces:** Verified intake/CIF contexts and deliberate replacement without lost drafts.

- [x] Add RED tests for typing then blurring lookup, Open/New/Close with unsaved text/checkboxes/files, cancelling discard, empty Clear search, candidate 404/network failure, and further edits during an outstanding lookup. Assert failed target reads do not destroy the old authorized draft.
- [x] Add RED tests for `new_intake_detaches_all_old_stage_handoffs`, same-case Back/Next retaining children, and a successful save followed by failed reload preserving its known reference. Add a late-response case after logout/denial.
- [x] Separate search editing from invalidation. Add New/Continue/Close semantics and dirty tracking at form owners; commit case replacement only after successful identity validation and a current discard decision. Starting New clears old handoff identity, not just the visible field. Privacy disposal stays unconditional.
- [x] Run Task 1/2 tests plus `node --test spina_portal/tests/office-onboarding-workspace.test.mjs`. Run relevant existing CIF/Employee cases discovered in Task 0; record exact files/counts. Commit `fix: preserve Office drafts during deliberate case changes`.

## Task 3 — Carry verified application context and render truthful guidance

**Files:** `office-application-review.js`, `office-application-entry.js`, `office-first-loan.js`, `roles/management.js`, `employee-office-case.js`, `employee-workspace.js`; Task 1 tests.
**Consumes:** Verified intake/client identity, explicit application selection, current saved-version responses.
**Produces:** Persistent private case banner, consistent four-stage navigation, preserved draft reference behavior.

- [x] Add RED tests for mismatched intake/client/application pairs, different destination work, two applications for one client, generated-but-unsaved references, manual later-stage resume, and stage selection not marking earlier requirements complete.
- [x] Add RED tests for banner status belonging to the correct source/version, missing stage status displaying Not loaded, unknown status not appearing successful, and source identity changing during a delayed read. Retain #492/#494 generated-reference and conflict tests.
- [x] Publish context only from verified module responses. Render S3 banner and S1 stage labels with existing private-panel protections. Back/Next remain reads/navigation; no auto-create/save/confirm/approve/release. Preserve protected details when the user returns to the same case.
- [x] Run both role integration tests and synthetic browser checks for new → saved intake → CIF → selected application → first-loan read. Assert zero implicit writes, correct selected identities and retained actual File objects. Commit `feat: guide Office work with verified case context`.

## Task 4 — Lock uncertain writes and complete privacy/refresh integration

**Files:** Existing Office child modules, both role controllers, coordinator and Task 1 tests. Modify shared write guard only when needed for this Office integration, not as a general refactor.
**Consumes:** Existing request/retry identities and read-only recovery.
**Produces:** All entry, navigation, refresh and replacement paths respect operation ownership.

- [ ] Add RED tests for delayed intake submit plus New/Open/Close/Refresh, uncertain first-loan outcome plus stage change, successful write followed by failed read, cancelled dirty-dialog plus current write, and a response arriving after owner/permission changes.
- [ ] Make coordinator transitions consult every affected stage's pending/uncertain handle. Keep the original operation recoverable and block conflicting writes; a search result is not resolution of an uncertain command. Ordinary same-case navigation may retain a pending view only when existing policy permits and never clears its lock.
- [ ] Ensure 401/403/device/session loss clears banner, visible/hidden/detached forms, files, finder and child controllers; late callbacks cannot recreate them. Read-only refresh must preserve unfinished work and moved focus. Protect global shell Refresh, not just local buttons.
- [ ] Run all Office tests, relevant shared role/write/privacy tests and `npm test`. Inspect no newly added persistence or permission widening. Commit `fix: retain Office write locks and private-state cleanup`.

## Task 5 — Refine responsive entry/navigation without a shell redesign

**Files:** `spina_portal/assets/app.css`, scoped Office markup, `office-workflow-layout.test.mjs`.
**Consumes:** Working S1–S3 markup and registered case context.
**Produces:** Readable entry/editor layouts at desktop, intermediate and phone widths.

- [ ] Capture failing/awkward baseline entry states at 997×857 and 1024px, including wrapped task/stage labels. Add layout assertions for overflow, visible selected-case identity and reachable primary controls.
- [ ] Apply scoped spacing, restrained borders, compact task navigation and a deliberate four-column/2×2 stage layout. Keep six Management groups, readable inputs and focus. Adjust the sidebar only when measurement justifies it; then verify all role shells.
- [ ] Build with `node tools/build_portal.mjs` and inspect actual browser layouts at 1440/1280/1024/997/768/390/320, 200% zoom, keyboard and reduced motion. Include long names/references and error/blocker messages. Do not accept a hidden panel screenshot as visible-destination evidence.
- [ ] Run layout/role tests and commit `style: simplify Office applications entry and intermediate layouts` with dated synthetic captures.

## Task 6 — Add protected intake search and application-list reads

**Files:** `client_onboarding_api.py`, `client_onboarding_repository.py`; reuse authorization/private-route helpers from existing application API/repository; new `test_office_application_search_api.py`, `test_office_application_search_repository.py`. Index migration only if justified under S4.
**Consumes:** Existing intake/application headers, versions, promoted-client relationship, current office permission.
**Produces:** The two S4 read contracts, not a workflow/approval API.

- [x] Write RED API tests for both routes, valid Employee/Management, missing permission, wrong role, inactive actor, revoked device, denied repository read, unpromoted intake, 404, encoded slash references and private/no-store validation errors. Assert no new write capability or data mutation.
- [x] Write RED repository/database tests for name/phone/intake/application reference search; 0/1/25/26/60 records; identical timestamps; escaped `%`/`_`/quotes and injection-shaped input; invalid/oversized/mismatched cursors; status/limit boundaries; duplicate names; multiple applications and versions; and current authorization on every page. Assert exact allowed projection and no duplicate intake/application headers.
- [x] Prove an empty-query first page returns recent authorized intakes in creation-time order, including name, phone, reference, actual intake status and updated time. Verify later edits do not silently change the documented ordering and no saved application is selected by default.
- [x] Implement `search_office_cases` and `list_office_applications` using fixed parameterized SQL, active-role/permission checks and bounded tuple pagination. Add GET routes without changing current POST or greedy exact-reference behavior. Reject invalid shapes rather than silently broadening the search.
- [x] Apply the existing private-route no-store behavior to success, denial, not found and validation errors. Verify access-log/query redaction. Do not release a search route that logs names/phones unredacted or exposes evidence/financial payloads.
- [x] Run `python -m pytest -q gilbic_backend/tests/test_office_application_search_api.py gilbic_backend/tests/test_office_application_search_repository.py` under the existing backend PYTHONPATH/environment. Run real PostgreSQL cases against the explicitly disposable Office database using the current verification runbook. Conditional skips are not database proof.
- [x] Inspect synthetic query plans for each search class, including many applications per client; no per-row API/SQL fanout. Add an index only with recorded need and next-free migration number; prove no source-row changes and preserve private grants. Commit `feat: add protected Office intake and application search`.

## Task 7 — Connect the finder and explicit saved-application picker

**Files:** New `office-application-finder.js`, `office-application-finder.test.mjs`; coordinator and both role bindings; scoped CSS.
**Consumes:** Task 6 responses and coordinator `requestTransition`.
**Produces:** `mountOfficeApplicationFinder({root, api, getSession, signal, onChooseCase, onChooseApplication})` with callable disposal and read-only refresh.

- [ ] Add RED tests for independent loading/error/empty/not-found/denied states, server paging and filter reset, query normalization, bad response shape, older response after a new search, application list pagination and keyboard focus recovery. No totals may be inferred from loaded rows.
- [ ] Add RED integration tests for choosing case B while A is dirty, cancelled replacement, failed target revalidation, several saved applications for one client, exact application-version handoff, revoked access between pages, and unsaved draft refs absent from saved search results.
- [ ] Add RED tests for the recent list loading on Office entry without typing or pressing Search, visible row identity/status/updated time/Continue controls, distinct no-intakes versus no-matches states, duplicate-name selection, and returning to the same finder page. Cover Management and Employee entry bindings.
- [ ] Mount the finder when the Office entry view opens and load its empty-query first page automatically after authorization. Render `Recent office intakes`, `Newest intakes first` and the S1 row fields/Continue action. Open uses the existing protected readers and shared replacement guard; exact-reference continuation remains functional. Render only S4's returned fields and status labels. Show saved applications for the selected verified client; application selection is explicit, never automatic latest/first matching name.
- [ ] Preserve in-memory query/page on returning to the finder, with Clear search independent of Close case. Failure of a later page leaves prior authorized rows with a clear incomplete/read-failed notice; denial clears everything. Clear private results on disposal and mark panels private for existing screen-viewing controls.
- [ ] Run finder, case safety, both role and real-browser tests; commit `feat: find and resume exact Office applications`.

## Task 8 — Complete whole-flow browser, regression and PWA acceptance

**Files:** Existing tests/build/cache registry; `docs/reviews/2026-10-03-office-applications-acceptance.md`.
**Consumes:** Implemented Tasks 1–7.
**Produces:** Exact-source acceptance matrix and release-safe public asset graph.

- [ ] Run `npm test` once, followed by `node tools/build_portal.mjs`; do not use `npm run build` immediately after npm test because it repeats the same tests. Verify public output exists, no tests/fixtures/docs or forbidden backend secret patterns ship, and every required new module is in the correct PWA graph. Update the existing cache version only as required by actual changed assets.
- [ ] Run the current Office/CIF/application/first-loan backend suite and real disposable PostgreSQL integration. Ensure new database tests are actually included in the existing runner; extend its test selection if necessary rather than creating a duplicate workflow. No grant, lending or accounting behavior may regress.
- [ ] Browser matrix, both Management and Employee: empty entry, new dirty intake, loaded case, discard confirm/cancel, failed replacement, case A → new intake → later stage, same-case draft/File retention, multiple applications, saved-versus-failed-read, pending/uncertain write, denied/expired session, stale delayed response and search page 2. Test normal/long text at all seven S5 widths; zoom/keyboard/reduced-motion for representative entry, editor and picker states.
- [ ] Demonstrate the owner's list workflow in both Office roles: open Office, see saved applicants without typing, identify a case by name/reference, Continue, explicitly choose its saved application and return to the retained list. Include duplicate names, later pages, empty/read-failure states and visible mobile-card actions; capture synthetic evidence and confirm no implicit write.
- [ ] Include wrong-role/no-permission variants and Collector residence-visit regression; smoke-test Collector/Client shells when shared code/CSS changed. Use actual built production navigation and synthetic fixtures. Record browser errors, unexpected requests, visibility assertions and source SHA with each capture set.
- [ ] Visually inspect representative captures, not only screenshot counts. Distinguish mocked browser evidence, real disposable-backend evidence and unperformed authenticated production/physical acceptance. Commit `test: verify Office case safety search and responsive workflows`.

## Task 9 — Review, exact-head CI and durable Codex handoff

**Files:** This plan, the acceptance ledger and PR description/comments. Do not modify other PR workstreams or frozen Master #296.

- [ ] Conduct a fresh whole-change review for spec coverage, identity/permission boundaries, transition races, pending writes, paging and minimality. Resolve findings with RED→GREEN evidence; retain failed attempts as dated evidence.
- [ ] Push to this same branch/PR. Let existing CI run; verify the exact implementation head and required `Backend, quality, and security`, `Portal, Flutter, and Android`, and `Financial and disposable PostgreSQL` gates. Reuse the same qualifying run; no weakened gate, duplicate suite or planning-head Green as implementation acceptance.
- [ ] Update every task with actual commit/test/browser/database evidence. Update GitHub, append a targeted Notion checkpoint and update the local continuation pointer with exact head, remaining tasks and any blockers. Preserve the owner's Create State refusal and other chats' newer records; report a failed sync honestly.
- [ ] Keep draft/open/unmerged. Report implemented versus unimplemented scope, exact CI state and remaining manual acceptance. No merge, deploy, migration on a live database, provider/financial operation, feature activation or owner-device installation without separate authorization.

## Requirement coverage and stop conditions

S1 → Tasks 2, 3, 5, 7; S2 → Tasks 1–4; S3 → Task 3; S4 → Tasks 6–7; S5 → Tasks 5, 8; S6 → Tasks 8–9. Review Focus 1 → Tasks 1–3; 2 → Tasks 1–4; 3 → Tasks 6–7; 4 → Tasks 4, 6–8; 5 → Tasks 3, 5–8.

Stop and record the narrow issue when live code changes the approved case/permission/source relationship, a necessary contract would widen authority or add new business rules, migration numbering conflicts, another worker owns the same files, or a pending operation cannot retain its existing safe recovery. Do not omit a planned requirement and label the whole PR complete. Queue implementation is included, but cross-case approval/readiness aggregation is explicitly not invented.

## Copyable Codex task

Implement this Office applications PR on its existing branch. Read the design and plan, current main/active PRs, frozen Master #296, latest Notion and the local continuation pointer first. Complete Tasks 0–9 with test-first small commits. Preserve #492/#494 reference behavior, add verified case/draft safety, new-or-continue entry, truthful context/stages, responsive layouts and the two protected finder reads with explicit saved-application selection. Keep existing private data and uncertain-write controls; do not add a framework or new financial path. Do not touch Android #496 or reinterpret this as authority to merge/deploy/enable production. Record exact-head evidence and keep GitHub/Notion/local continuation synchronized, preserving the owner's prior Create State refusal. Leave the PR draft/open/unmerged and report any unimplemented requirement plainly.
