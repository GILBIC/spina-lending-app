# Whole-code review findings repair plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Correct all seven findings from the 9 October whole-code review without weakening existing authorization, retry, custody or financial contracts.

**Architecture:** Keep server-owned money and business dates in the existing backend owners. Protect native private state and uncertain writes across their actual lifetime. Validate Portal final acknowledgements before consuming drafts. Reuse existing domain/protection interfaces; avoid unrelated refactors.

**Tech Stack:** Python3.12/PostgreSQL18; Flutter3.44.7/Dart; Node22+ browser JavaScript.

**Spec:** `C:/Users/pc/OneDrive/Documents/ChatGPT/Gilbic/artifacts/code-review-20261009-bfd33ff7/SPINA-code-review.md`, with each finding's linked domain requirements. This plan implements F1–F5 and S1–S2; the user authorized all seven with “Fix”.

## Global Constraints

- Work only in `C:/Users/pc/Documents/Codex/2026-09-19/continue-spina-if-you-have-some/spina-accounting-20261005`, existing isolated branch `codex/review-fixes-20261006`; starting HEAD `bfd33ff7cdef94c1c7ff7ca0d13af38b8ac4c1db`.
- Preserve all eight previously repaired cases, exact-command replay, private server authority, approved-device checks and online-only financial writes.
- No live database/Auth/provider/customer/file/phone operation, production deployment, push, merge or external messaging. Use synthetic local fixtures. Never read secret .env files or expose credentials.
- Do not modify earlier review artifacts or another plan's workspace. Current plan scratch belongs under `.superpowers/sdd/2026-10-09-review-findings-fixes/`; controller archives final evidence separately.
- One implementation subagent at a time; no subagents from implementers/reviewers. Controller owns full suites and PostgreSQL start/stop; one Flutter process at a time. Coordinate focused Flutter runs with controller.
- Root runtime: `../.venv/Scripts/python.exe`; Node `C:/Program Files/nodejs/node.exe`; Flutter `C:/Users/pc/.codex/visualizations/2026/09/17/01a0af8a-29a3-7ba3-9f24-a4874a0c31b5/p10-flutter-3.44.7/bin/flutter.bat`. Do not install/upgrade dependencies.
- New regressions must fail against the starting implementation for the expected behavior, then pass with the fix. Existing review probes are evidence and may be adapted into portable tracked tests. Keep platform skips and existing lint baselines explicit.
- Run focused verification per slice, then full backend/Portal/Flutter suites and native analyzer after integration. Make local task commits after focused checks and independent review; controller owns final delivery commit/docs. Do not claim full-suite completion from focused runs.

## Review Focus

- F1/F2: partial or historical bindings, corrected events and stale/closed sessions must not bypass custody or statement coverage; preserve exact replay and valid unbound correction.
- S1/S2: UTC midnight boundaries, zero and interest-bearing Regular loans, 7x7, voided receipts, extra principal and unavailable contractual schedules must not invent paid cash or dates.
- F3: late reads after authoritative denial, a changed session/scope and preexisting dialogs must not resurrect private state/actions; ordinary transient network errors may retain compatible read-only state.
- F4: in-flight or lost-ack writes followed by Back/reopen cannot regain write authority; safe record reads and authorized reconciliation must remain possible.
- F5: malformed/mismatched final facts, duplicate status, legitimate zero-PASS and combined-leg membership must retain exact pending identity and avoid false Saved; valid accepted results retain existing local refresh behavior.

### Task 1: Backend custody, reconciliation and authoritative projections

**Findings:** F1, F2, S1, S2. Read the spec report and the linked exact backend requirements for these only.

**Files:** Primary owners `gilbic_backend/src/gilbic_backend/treasury_repository.py`, `treasury_reconciliation.py`, `area_management_api.py`, `management_loan_repository.py`; reuse existing shared clock/projection helpers if suitable. Add a narrow helper only when required to share authoritative behavior. Tests live under `gilbic_backend/tests/`, including existing Treasury reconciliation/Collector surplus, area-management and Management portfolio tests. Avoid client source edits.

**Interfaces:** Preserve existing API shapes except additive fields needed internally; all writes remain inside existing protected transactions. Consume existing current-account locks, Collector retained event bindings, collection server business clock, applied payment records and authoritative contractual schedule sources. No schema change should be necessary; justify any unavoidable migration before writing one.

- [x] Adapt real-SQL F1/F2 review probes into tracked regressions. Obtain controller's fresh owned loopback schema0141 connection from the task workspace; do not start an old cluster. Add positive/replay controls, invalid match preview/close checks, and retained-binding guards for the actual supported Collector lifecycle.
- [x] Demonstrate red, then prevent generic corrections from erasing retained Collector custody; preserve legitimate unbound correction and exact replay. Treat authoritative historical bindings conservatively unless an established protected unwind explicitly releases them.
- [x] Revalidate reconciliation matches against currently valid in-scope movements; preserve immutable historical matches and prevent closing a session with invalid matched statement rows. Provide a supported path to a new/replacement reconciliation rather than destructive match rewriting.
- [x] Add UTC/Manila boundary API tests, use the explicit shared Manila business-date authority for both transfer preview and commit. Do not fix this by changing host TZ or the entire application's clock semantics.
- [x] Add product-aware Management paid projection regressions: Regular principal5000 + interest1000, applied100 => paid100 and1.7%; zero/7x7/voided-payment controls. Derive actual applied amounts and contractual denominator from the established owner (inspect Renewal and state posting). Do not turn money into floats or infer cash from principal-minus-contractual-balance. Make missing-data behavior consistent with the existing authoritative owner.
- [x] Run focused backend/API/unit and fresh-DB suites plus changed-file quality checks. Self-review, prepare diff, and report paths/commands/results/concerns under this task workspace. Do not run the full backend suite; controller performs the integration gate once.
- [x] Controller reviews the task against spec and quality; resolve findings, then create a scoped local commit.

### Task 2: Native private-state denial and Office uncertainty lifetime

**Findings:** F3, F4, plus the native consumer of S2's corrected nullable paid percentage. Read the spec report and relevant Android/private-view and native Office contracts.

**Files:** Denial owners `gilbic_mobile/lib/src/features/remittance/{remittance_photo_viewer_page,remittance_history_page}.dart`, `features/notifications/remittance_notifications_page.dart`, `features/renewals/renewal_signature_tasks_page.dart`, `features/client/client_renewal_workflow_page.dart`, `features/collector/collector_renewal_requests_page.dart`. Office owners `features/office/office_widgets.dart`, `office_workspace_page.dart`, intake/review page as needed, `core/office/office_operation.dart` or an appropriately scoped existing owner. Tests under `gilbic_mobile/test/`. No backend/Portal source edits.

**Interfaces:** Use established session authorization scope and recovery patterns. Preserve compatible token refresh; session replacement/denial must revoke private state. For Office, preserve exact command or an explicit workspace-held unknown-outcome state; no automatic write replay and no invented outcome. Safe read-only reconciliation must remain accessible. Use the narrowest lifetime owner that survives ordinary Back/reopen and is cleared on authority teardown.

Task1 produces actual `paid_amount` and nullable `paid_percent`: missing/nonpositive contractual total means unknown percentage, as in Renewal, not invented zero. Update `gilbic_mobile/lib/src/core/management/management_loan.dart` and `features/management/management_loan_portfolio_page.dart` to accept/render that unknown value while retaining valid portfolio records and actual paid amounts. Portal already renders the nullable percentage as unavailable. An arbitrary successful Office reference lookup is not proof that an unknown create resolved; do not silently clear that attempt based on a different record.

- [x] Adapt review widget probes to tracked tests, then add actual mounted-page tests for all six affected denial owners, late-read fencing, session/scope replacement and mutation denial where applicable. Initial red evidence exists in the review; run new tracked regressions red before the relevant edit.
- [x] Clear protected models/bytes/actions on401/403/426, invalidate pending reads, and prevent stale completions/dialog actions from restoring authorization. Apply the established recovery UI rather than leaving a private image under an error. Preserve safe transient-error handling.
- [x] Reproduce Office initial uncertain create, Back/reopen and duplicate attempt with actual workspace/form. Implement durable authorized-workspace uncertainty or a bounded navigation protection plus reachable authoritative reconciliation; it must cover ordinary app-bar/system Back and in-flight completion. Avoid a permanently trapped screen or silently discarded unknown outcome.
- [x] Add successful read/reconciliation, compatible refresh and authority teardown controls appropriate to the chosen existing owner. Verify legitimate new intake after a resolved outcome without permitting blind duplicate writes.
- [x] Add Management model/widget tests for nullable paid percentage (unavailable message, no fabricated zero/progress bar, rest of portfolio remains usable) and corrected known1.7%/100.00 values; coordinate with Task1's shared projection output.
- [x] Run focused widget/core tests using pinned Flutter only, format changed files and run analyzer. Controller owns final full native suite; do not start concurrent Flutter processes.
- [x] Self-review, report commands/results/concerns, then controller task review and scoped local commit.

### Task 3: Portal canonical final payment confirmation

**Finding:** F5 (remaining Portal surface related to native R8).

**Files:** `spina_portal/assets/collector-workflow-contract.js`, `collector-route-view.js`, other shared result consumers such as `collector-workflows.js` as required by shared validator scope; tests under `spina_portal/tests/` using the actual workspace handler. Consult shared payment contract and current repaired Dart parser for canonical final facts. No backend/native source edits.

**Interfaces:** Single-entry accepted/duplicate confirmation must match the exact submitted command UUID and contain a nonblank opaque server transaction ID, canonical nonnegative exact money and a valid accepted timestamp; PAY/ADV require a receipt, and legitimate zero-PASS follows the server contract. Combined responses follow their distinct existing API: validate all and only the expected nonzero posted components once against the retained authoritative reviewed allocation (including same-loan scheduled/extra components and omitted zero allocations), canonical amounts/balances/receipts, command identity and review hash. Combined responses do not contain an accepted timestamp; do not invent or require one. Unknown/malformed2xx stays uncertain and retains the exact submitted request, identity, draft and note across ordinary refresh/direct-submit attempts for that authorized workspace lifetime. Preserve the existing reconciliation lock and guidance; no new replay UI or automatic write is required.

- [x] Adapt review's real-workspace Node probe into portable tracked tests. Demonstrate valid control and red malformed2xx cases (missing/invalid transaction, balance, time, mismatched command); include duplicate, zero-PASS and shared combined result consumers where affected.
- [x] Implement narrow canonical result validation and keep saved/editor-clear transitions behind it. Preserve pending command identity and typed note on uncertainty, maintain reconciliation lock, and keep valid success/local refresh behavior intact.
- [x] Run focused tests and module checks, then full Portal suite (fast enough to run here; controller can reuse this result if no later Portal code changes). Self-review and report exact evidence.
- [x] Controller task review, fix findings and create a scoped local commit.

## Final integration and delivery

- [x] Rerun the seven original symptom families with corrected expectations and retained positive controls; full backend/Portal/native tests and native analyzer; fresh synthetic SQL Treasury and affected projection/date coverage.
- [x] Compare changed-file Python diagnostics to starting commit instead of silently claiming a preexisting lint baseline is clean. Run git diff --check and capture exact final provenance.
- [x] Independent whole-change Standards and Spec reviews. Resolve material issues; preserve evidence and concrete limitations. No new feature scope.
- [x] Add a concise release repair record with seven-finding mapping, test results and limits. Preserve all Ruling lines and task evidence outside scratch before cleanup. Leave user-visible source on the repair branch, with local commits only; do not merge, push or deploy.
