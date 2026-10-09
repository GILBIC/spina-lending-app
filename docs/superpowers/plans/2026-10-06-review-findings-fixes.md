# Repair the eight additional code-review findings

The user approved implementation with “okay fix”. Requirements are the four primary findings in each of the two retained reports at `C:/Users/pc/OneDrive/Documents/ChatGPT/Gilbic/artifacts/code-review-20261006/SPINA-code-review.md` and `SPINA-code-review-round2.md`. Base is `7e661549174297549bd51f6560713c3710d44e0a`, including the six earlier audit repairs and migration0141. Worktree: `C:/Users/pc/Documents/Codex/2026-09-19/continue-spina-if-you-have-some/spina-accounting-20261005`; branch `codex/review-fixes-20261006`.

## Global constraints

- Preserve the existing six audit repairs, permissions, exact command identities, immutable financial history, contract behavior and migration ordering.
- No production database/Auth calls, actual payments, borrower files, deployment, merge, phone operation or external messages. Only synthetic tests and unique disposable loopback databases owned by this task.
- Write behavioral regressions first, observe the original failure, then repair. Use actual application methods; substitute external boundaries only where necessary. Record commands, failures and passes in each task report.
- No speculative accounting expansion or unrelated visual redesign. The extreme-value money observation and corrupt-paper hardening note are outside these eight primary repairs.
- Only one implementer edits at a time. No worker subagents. Root coordinates integration, full suites, database execution, independent reviews and commits. Preserve unrelated files and prior checkpoints.
- Python runtime is `C:/Users/pc/Documents/Codex/2026-09-19/continue-spina-if-you-have-some/.venv/Scripts/python.exe`; set PYTHONPATH to `gilbic_backend/src;spina_backend_mobile/src;.`. Use default pytest import mode. Pinned Flutter3.44.7 is `C:/Users/pc/.codex/visualizations/2026/09/17/01a0af8a-29a3-7ba3-9f24-a4874a0c31b5/p10-flutter-3.44.7/bin/flutter.bat`; run from gilbic_mobile, concurrency1. Coordinate expensive tests through root.

## Task 1: Treasury exclusive debit use and transfer correction safety (R1, R5)

Read the Treasury findings in both review reports and the two retained Python probes. Scope: treasury_repository.py, treasury_disbursements.py, relevant Treasury tests; add a forward migration after0141 only if needed for authoritative concurrency guarantees.

- Prevent a refund from reusing a debit already committed to payroll, loan payout or another consuming source. Preserve legitimate exact idempotent replay. Audit the reciprocal paths so an event cannot become double-used by changing operation order, including transfers where relevant. Enforce checks under existing shared account/event locks and retain source evidence.
- Reject generic false-observation correction of either leg of a correlated transfer, including incomplete transfers, until a dedicated protected unwind exists. Preserve ordinary unlinked observation correction; do not invent a new transfer repair workflow or change real balances.
- Regressions must cover refund after disbursement, reverse order, same-command replay, both transfer sides, no writes on rejection, and successful unlinked correction. Use/reuse actual repository seams, with real disposable PostgreSQL tests for lock/schema behavior where supported. Root provides the test database; never use a discovered non-loopback URL.
- Run focused Treasury tests after each slice. Write the task report with RED/GREEN evidence, changed paths and limitations. Do not commit; root packages the working diff for task review.

## Task 2: Bound new single collections by Manila business date (R2)

Read R2 in the first review and reproduce_future_collection.py. Scope: authoritative single-collection admission/posting and existing tests.

- Reject a new collection dated after the current Asia/Manila business date before area transfers, financial writes or sequence consumption.
- Preserve exact committed idempotent replay across date changes. Preserve explicitly authorized historical behavior; do not retroactively reject an already-recorded command solely because the clock changed.
- Cover future date, Manila midnight boundary, current date, permitted historical date and exact replay. Do not add caller-controlled clock authority. Reuse the current combined-collection date rule when it is an appropriate server helper.
- Run focused single/combined admission, receipt and idempotency tests; report RED/GREEN evidence and any real database tests still needed. Do not commit.

## Task 3: Preserve Client identity after uncertain local account commit (R6)

Read R6 in the extended report and round2-client-account-commit-repro.py. Scope: manual imported-borrower account API/repository and credential tests; preserve the existing first-loan workflow.

- Never delete Auth on an uncertain local commit. Keep cleanup for proven pre-commit domain failures where safe.
- Reconcile exact stored borrower/account/Auth identity after an uncertain exception when feasible. A committed account must remain accessible through normal account lookup/password reset even if the original response cannot be recovered. Do not falsely claim no account exists.
- Do not link identities by matching email alone or expose credentials in logs. Avoid a new provisioning framework if preserving the identity, exact readback and explicit existing-account recovery suffice. Document any still-uncertain case honestly; do not silently retry identity creation.
- Regressions: committed-but-ack-lost keeps identity and usable recovery; definite rejected precondition creates/deletes no wrong user; confirmed domain rollback compensation remains; ordinary success and first-loan reconciliation continue to work.
- Run focused account/credential tests and report RED/GREEN evidence. Do not commit.

## Task 4: Preserve Employee pending commands through compatible token refresh (R3)

Read R3 in the first review and spec-repro-employee-session.mjs. Scope: Portal employee-operations state/session identity, app mounting if required, existing tests.

- Bind retained uncertain commands to stable actor/device/authorization scope rather than transient session object identity. A token refresh for the same compatible context and workspace remount must recover the exact request/domain IDs.
- An actual identity/device change or loss of required permissions must clear private state and prevent replay under a new authority. Do not persist private command payloads to browser storage or introduce automatic financial retries.
- Cover same-context refresh/remount exact retry, different actor/device isolation, authority loss, and acknowledged completion removing pending state. Preserve existing logout cleanup.
- Run focused Employee/app tests and Portal module checks. Do not commit; report RED/GREEN evidence.

## Task 5: Complete native denial cleanup, cache fencing and payment validation (R4, R7, R8)

Read R4 in the first review and R7/R8 in the extended review, plus retained Flutter/Dart probes. Scope: Client Support/Renewal and Management staff-device pages; collector route cache/loader/app cleanup; payment response model/repository and affected tests.

- Clear private Support/Renewal models and paginated staff-device rows on401/403/426. Fence late reads and context changes using the existing pending-audit privacy patterns. Network errors may preserve the allowed stale model.
- A route read begun before logout or authorization denial cannot write private cache afterward or revive offline fallback. Fence persistence and readback, including delayed storage writes and new sessions for the same actor; widget mounted checks alone are insufficient. Preserve authorized offline read-only behavior and encrypted storage.
- Only confirm single collection accepted/duplicate after explicit final status, exact matching submitted identity and authoritative response facts required by its entry type. Empty/nonfinal/mismatched success is uncertain, retaining exact retry IDs. Do not require payment-only receipt facts from legitimate zero-cash PASS if the server contract differs. Cover actual server accepted/replay response shapes.
- Promote the retained failing probes into permanent tests with assertions for safe behavior. Cover later storage completion, logout/new session, denial/older success, ordinary offline fallback; malformed and valid payment responses and actual route UI pending identity preservation.
- Run scoped Flutter tests and analyzer while iterating; root runs full Flutter once integrated. Do not commit; report RED/GREEN evidence.

## Task 6: Integration and delivery

- Independently review each task's diff for requirements and quality, resolving important findings before proceeding.
- Run full Portal, backend and Flutter test commands plus applicable lint/analyzer and fresh disposable PostgreSQL financial regressions; record every failure, skip and limitation accurately. Avoid simultaneous heavy suites on this host.
- Review the complete eight-finding diff using separate Standards and Spec axes, repair confirmed gaps, then commit the reviewed work on the repair branch.
- Retain a release note mapping all eight findings to fixes/tests, compatibility and remaining deployment gates. No publish/deploy/merge is part of this request.
