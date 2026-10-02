# Collector Excess and Surplus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:executing-plans or superpowers:subagent-driven-development task-by-task. Keep one integration owner for shared financial writers, schemas and transaction boundaries. Track the checkbox steps with actual evidence.

**Goal:** Record exact counted remittances, distinguish unidentified excess from genuine Collector credits, and settle or correct those credits without duplicate money or lost custody.

**Architecture:** Extend the existing Treasury service from PR #490 with a bounded counted-settlement and Collector-credit lifecycle. Reuse authenticated evidence, account movements, durable outcomes, protected source correction and explicit GL controls. Web, Android and installed Windows consume the same server contract; no second cashbook or allocator.

**Tech Stack:** Existing Python/FastAPI/Pydantic/psycopg/PostgreSQL; vanilla ES-module portal; Flutter/Dart; installed Windows portal. Use repository-pinned toolchains and lockfiles, no dependency/framework upgrades.

**Spec:** [2026-10-02-collector-excess-surplus-design.md](../specs/2026-10-02-collector-excess-surplus-design.md).

**Status:** Planning-only. Main baseline `41a13eb59c9cc1b65a0a6a51f3b73db4a0895013`; Treasury dependency inspected at #490 `a24d72baab623dbcce69f1a1c2d7316d1431b34f`. Every implementation checkbox is pending. The new branch `plan/collector-excess-surplus-20261002` contains this plan and specification only. Owner starts Codex separately; no actual count or financial mutation is performed by this handoff.

## Global constraints

- Separate from #490 and #485–#489. Default product dependency is reviewed #490 merged into main by separate authority; do not merge it yourself, overwrite its branch, duplicate Treasury or silently publish a stacked dependency diff. Report any approved alternate integration arrangement.
- Counted is not accepted; unidentified excess is not Collector credit. Required remittance is server-derived from current protected sources. Short physical count is rejected unless a separately authorized funding arrangement has already changed the explicit physical requirement.
- One actual cash/wallet movement, multiple links. Credit recognition, source allocation and GL posting create no duplicate movement.
- Genuine surplus is a Collector-specific amount due back; no income, automatic next-day/borrower/shortage/payroll offset or negative-credit plug. Explicit future application requires the spec's separate request/approval/custody contract.
- Exact PHP decimal text and existing amount ceilings, positive payment/credit amounts, zero permitted only for counts/observations. No new loan/EIR/tax/commission formula. `automatic_source_posting=false` remains.
- Preserve actual receipt dates, later correction/entry dates, immutable remittance/source evidence and protected historical/closed-period behavior. A blocked historical path is not permission to post today.
- Current actor/device/account/context/object permission checks apply to fresh writes, files and replay. Collector own-credit projection never grants account history. No self-recognition/self-approval or broad role grants.
- Additive migrations may be authored/tested on explicitly disposable DBs only. No real accounts/counts/credits seeded; production flags stay disabled/unconfigured.
- Financial writes online-only, durable unchanged-request recovery, private files and existing sharing exclusions. Do not add browser draft storage or another offline money outbox. Keep Android attendance policy unchanged.
- Keep Draft/open/unmerged; no mark-ready, merge, deployment/delivery, production migrations/transactions, owner-device installation, live capture or Master acceptance changes.

## Review focus

1. A count is greater than expected only because a borrower payment is missing; identify/correct its source instead of granting Collector ownership — Tasks2,3,6.
2. Response lost after cash acceptance or outgoing debit; recover the same phase without repeated cash or freed credit capacity — Tasks2,4,8.
3. Return, future application and reclassification compete for one partially settled credit; database capacity and consistent locks prevent double use — Tasks3–6.
4. Prior-day money, opening cash and closed reconciliations overlap; maintain dated source/custody links without double receipt or silent history rewrite — Tasks6–8.
5. Delegation revoked or a private wallet is used to repay a Collector; safe own-credit views/recovery must not reveal balances, third-party evidence or another Collector's credit — Tasks1,4,9–11.

## File ownership and interfaces

New focused backend modules under `gilbic_backend/src/gilbic_backend/`:
- `collector_settlement.py`: current settlement previews, count capture and atomic acceptance/custody linkage.
- `collector_surplus.py`: credit recognition, return/application reservation and settlement.
- `collector_surplus_resolution.py`: existing-source corrections, opening anchors and reclassification guards.
- `collector_surplus_reads.py`: scope-safe summaries, history and preview projections.

Bounded existing integration: `treasury_models.py`, `treasury_repository.py`, `treasury_authorization.py`, `treasury_api.py`, `treasury_disbursements.py`, `treasury_reconciliation.py`; `remittance_api.py`, `remittance_review_repository.py`, `notification_api.py`, their current receiving/custody/accounting helpers and source guards. Trace actual runtime functions before extraction; no HTTP-to-self or independent connection inside a financial phase. Preserve `TreasuryService.execute/replay/save_result` rather than introduce another executor.

Reserve the next unused numeric migration prefix in Task0 for the exact suffix `_add_collector_surplus.sql`, recording its full path before code. This is a deliberate concurrent-schema gate, not permission to overwrite0136/0137. New backend tests live under `gilbic_backend/tests/test_collector_surplus_*.py`.

Web: add `spina_portal/assets/collector-surplus.js`; extend existing `treasury-api.js`, `treasury-workspace.js`, `remittance-review.js` and authorized role registrations. Update `app.css`/`sw.js` only for required scoped presentation/public module membership. Tests under `spina_portal/tests/collector-surplus-*.test.mjs`.

Android: add `gilbic_mobile/lib/src/features/treasury/collector_surplus_page.dart`; extend existing `core/treasury/treasury_models.dart`, `treasury_repository.dart`, `features/treasury/treasury_workspace_page.dart` and live remittance/Collector destinations identified in Task0. Reuse existing API and encrypted attempt recovery. Tests under `gilbic_mobile/test/collector_surplus_*_test.dart`.

Windows: current `spina_pc` portal app mode reuses Web code/API. Do not create `spina_app/`, Tkinter cash control or a local financial database. Add focused Windows-runtime acceptance to existing Treasury Desktop tests discovered in Task0. Operating guide: `docs/operations/collector-surplus.md`; exact source/lock/contract map: `docs/operations/collector-surplus-contract-map.md`.

## Proposed strict contract — new work, not existing API

Reuse `/api/v1/treasury` and its current mobile aliases. New reads: `GET /collector-surplus/workspace`, `GET /collector-surplus/credits/{credit_id}`, `GET /collector-surplus/cases/{case_id}`, and `POST /collector-surplus/remittances/{remittance_id}/preview` (read-only server calculation). Lists default50/max100, deterministic ID/date order, server totals and has_more. Collector workspace derives own identity; a passed Collector ID cannot grant broader scope.

Reuse `POST /actions` and `GET /requests/{request_id}`. Add strict discriminated commands to `treasury_models.py`. Common fields retain `request_id`, `account_id`, `expected_version`; for these new actions, `expected_version` denotes the involved Treasury account version. Other source/count/credit/action versions are explicit fields. Use current `Money`, `PositiveMoney`, `Instant`, `Digest`, `Version` types and strict booleans. Authenticated actor/device/context and authoritative required amounts are never accepted from user claims.

| Action | Required additional data / result |
| --- | --- |
| `collector_count_record` | remittance_id, source_digest, counted_amount, counted_at, evidence_id, review_acknowledged; returns immutable count_id/version, server required and signed difference, no cash acceptance. |
| `collector_count_accept` | count_id/count_version, source_digest, physical_receipt_acknowledged, optional approved credit_application_id/version; returns actual accepted money, source/funding settlement, excess case and existing/new Treasury links atomically. |
| `collector_surplus_recognize` | case_id/case_version, amount, reviewed source digest, evidence_id, reason; returns same-Collector credit and remaining unidentified amount, zero new cash. |
| `collector_surplus_return_prepare` | credit_id/credit_version, amount, paying account, destination snapshot/evidence, reason; creates approved reservation only under independent authority. |
| `collector_surplus_return_record` | action_id/action_version, verified outgoing event_id/event_version, recipient_confirmation/evidence; links one actual payout, settles or leaves confirmation-pending/reserved. |
| `collector_surplus_application_prepare` | credit_id/version, target remittance, amount, Collector request/acknowledgment evidence, current source digest, reason; reserves approved same-Collector funding, no cash/credit settlement yet. |
| `collector_surplus_action_cancel` | action_id/version, evidence/reason; cancel only after proving no actual payout/uncertain result, releases reservation without altering money. |
| `collector_surplus_resolve_source` | case or credit target/version, existing correction/source identity and current protected preview digest, evidence/reason; uses source adapter, blocks unsupported historical/recovery cases. |
| `collector_surplus_opening_prepare` / `collector_surplus_opening_activate` | exact collector, opening_position_id/version, evidenced credit amount/cutoff, overlap review and reason; activation is owner-only, no new cash. |

`TreasuryResult` remains the durable envelope; include exact action/request/target/account/context/actor/device/version and explicit disposition plus source/event/credit IDs and amounts. `status=saved` can mean a saved rejected count or reservation, NOT receipt/payout success. UI must check the specific returned disposition. Replays check current source/account/private-file permission as well as actor/device identity. Same account/reference/event cannot pay two credits. Source result checks apply to both remittance and notification entrypoints.

Internal handlers use `(service, conn, actor, command) -> dict`, where the outer Treasury executor owns transaction, audit and durable outcome. Read functions use `(service, conn, actor, ...)`. Do not commit inside handlers. Register and test the new outgoing source adapter `collector_surplus_return`; do not fabricate a borrower for an existing refund API.

## Task 0 — Reconcile dependency, runtime source graph and evidence

**Files:** Read both documents, live #490/#485–#489, current main/AGENTS/CI/lockfiles, Master296 comments, Notion and Create State. Create the contract map above during execution.

- [ ] Confirm clean isolated worktree on this new PR branch. Record exact dependency head/merge status and independent-review evidence. If dependency is unmerged, keep implementation unpublished on an isolated dependency fixture unless an explicit stack is approved; report the gate instead of replacing490. Never force-reset another worktree.
- [ ] Trace every receive path (ordinary and notification/mobile), Treasury movement/GL linkage, legacy remittance/cross-handoff locks, refunds, source correction and installed Windows registration. Identify what already records ordinary received cash so acceptance cannot duplicate it.
- [ ] Reserve migration filename and publish actual lock order, command limits, account/context/custody mapping, current runtime guard and UI registration files. Capture baseline focused tests or retained exact-head evidence; no old-head Green substituted for new work.
- [ ] Commit the source/contract map and checkpoint. The prior isolated Pydantic probe is reference only, not a passing implementation test.

## Task 1 — Contracts, authorization and bounded schema (S1,S4,S9)

**Files:** Treasury models/auth/dispatcher/API; additive migration; `test_collector_surplus_contract.py`, `test_collector_surplus_authorization.py`, `test_collector_surplus_postgres.py`.
**Interfaces:** Add the commands above to the strict union. Expose `collector_surplus_workspace(service, conn, actor, filters)`. Tables cover immutable counts/settlements, excess cases/resolution entries, credit entries and versioned reserved actions; reuse outcomes/events/evidence.

- [ ] Write failing tests: exact decimal count permits0 and rejects negative/float/extra precision; forged required_amount/actor/status rejected; ordinary Employee permission alone insufficient; designated receiver and account grant both required; own Collector read omits private wallet/others; self-recognition denied; same-key changed payload conflict; new-command replay after revocation denied. Verify explicit schema limits and reference constraints, no real seeds.
- [ ] Run `python -m pytest -q gilbic_backend/tests/test_collector_surplus_contract.py gilbic_backend/tests/test_collector_surplus_authorization.py`; record genuine missing-behavior failures, not fixture/import accidents as acceptance.
- [ ] Implement minimal strict types and capability `collector_surplus_contract_version=1`, default-disabled feature readiness requiring Treasury. Reuse existing owner/account scopes, durable executor and private evidence. Extend permission unions and bounded grant validation consistently; add no blanket grants.
- [ ] Pass focused tests plus actual disposable migration/role/FK/immutability tests. Commit `feat(treasury): define scoped Collector surplus contracts`.

## Task 2 — Counted acceptance and source-aware cash (S2,S3,S9)

**Files:** `collector_settlement.py`, receiving/notification adapters, Treasury dispatcher, custody/source guards; `test_collector_surplus_receiving.py` and Pg suite.
**Interfaces:** `settlement_preview(service, conn, actor, remittance_id, account_id, application_id=None)`; `record_count(service, conn, actor, command)`; `accept_count(service, conn, actor, command)`.

- [ ] Write tests `exact_count_accepts_once`, `short_count_persists_without_acceptance`, `over_count_creates_pending_case_not_credit`, `source_change_invalidates_digest`, `notification_receive_cannot_bypass_count`, `cash_receiver_cannot_choose_wallet_as_physical_location`, `wallet_client_payment_excluded`, and `audit_failure_rolls_back_receipt_and_custody`. For10000/10100 assert physical delta10100, case100, credit0; for9900 assert no accepted remittance/cash delta and shortage100 remains. Two attempts cannot accept the same remittance twice.
- [ ] Run `python -m pytest -q gilbic_backend/tests/test_collector_surplus_receiving.py`; retain expected failures. Run the live request-model comparison in the test harness rather than altering production.
- [ ] Implement immutable count records and atomic acceptance with exact source digest/versions, actual holder and evidence. Save rejected count separately from an accepted phase. Adapt legacy receive/notification handlers to fail closed when new count contract enabled; no assumed count fallback. Reuse ordinary cash links and append only the needed excess funding; verify aggregate cash equals actual once. Explicit custody exception covers retained disputed cash without clearing full obligation.
- [ ] Run focused Pg races, rollback, legacy feature-off and new-client/old-server tests. Verify one full-receipt projection, no duplicate ordinary cash event, no orphan count/case. Commit `feat(remittance): capture and verify actual received cash`.

## Task 3 — Identification and genuine Collector credit (S1,S3,S4)

**Files:** `collector_surplus.py`, reads, strict models and schema guards; `test_collector_surplus_credit.py` plus Pg cases.
**Interfaces:** `recognize_credit(service, conn, actor, command)`; `credit_projection(service, conn, actor, credit_id)`; `case_projection(service, conn, actor, case_id)`.

- [ ] Add tests: difference alone never recognizes ownership; credit100 from identified case100; partial recognition40 leaves unidentified60; unknown/source-conflicted case blocked; no self-approval; concurrent recognition cannot exceed case; Collector sees own history only; recognition has zero cash delta. Missing evidence remains blocked, not paid.
- [ ] Run `python -m pytest -q gilbic_backend/tests/test_collector_surplus_credit.py` and establish RED.
- [ ] Implement append-only resolution/credit entries and current-version projections, validated source review and exact capacity. Show pending identification separately from available credit. Do not infer entitlement from collector attribution alone or mutate original received amount.
- [ ] Pass focused/Pg capacity/privacy/immutability tests; commit `feat(treasury): track identified Collector credits`.

## Task 4 — Actual Cash/GCash returns and partial settlement (S5,S9)

**Files:** surplus handlers, `treasury_disbursements.py`, evidence/source checks; `test_collector_surplus_returns.py`, Pg race cases.
**Interfaces:** `prepare_return(...)`, `record_return(...)`, `cancel_action(...)` use standard handler signature; register existing Treasury outgoing-source adapter for `collector_surplus_return` with exact action/version/payee/capacity. No second money-transfer service.

- [ ] Test credit100/reserve40 leaves outstanding100 and available60; confirmed cash payout40 leaves credit60/cash-40; wallet payout60+fee2 leaves wallet-62/credit0 and office unchanged; unpaid approval has no movement; debit-before-confirmation preserves reservation; duplicate event across credits denied; concurrent return/application cannot overconsume; wrong collector/context/account denied; timeout recovers same command. Test provider-returned/failed payout with genuine incoming reversal evidence reopens only the justified credit, never deletes the original debit or posts income.
- [ ] Run `python -m pytest -q gilbic_backend/tests/test_collector_surplus_returns.py`; establish RED before implementation.
- [ ] Implement reservation, existing verified outgoing-event link and explicit settlement state. Return phase result distinguishes saved request, debited-unconfirmed and paid. Strict cancellation requires evidence of no debit and no uncertainty. Cross-account return locks original credit and paying account in canonical order. Require recipient evidence and current permissions; never borrow a Client refund identity. Record actual reversals as linked events/credit entries only after verification.
- [ ] Pass Pg duplicate/concurrency/audit-failure and private-event recovery tests. Commit `feat(treasury): settle Collector credits with evidenced returns`.

## Task 5 — Explicit same-Collector future application (S6)

**Files:** surplus handlers, settlement preview/acceptance and custody/accounting adapters; `test_collector_surplus_application.py`.
**Interfaces:** `prepare_application(...)`; Task2 preview accepts an approved reserved application; `accept_count` consumes it atomically with settlement. Application source describes authorized cash retained by Collector as credit repayment, not office cash.

- [ ] Test default-disabled application; required Collector request and independent approval; wrong collector/borrower/payroll/old-shortage targets blocked; gross1000/approved100/physical900 clears funded settlement with office+900 and credit-100, not cash+1000; unapproved900 and approved-but-count890 rejected; cancellation/stale source releases no consumed credit; concurrent return cannot consume reserved100; lost result does not apply twice.
- [ ] Run `python -m pytest -q gilbic_backend/tests/test_collector_surplus_application.py`; establish RED.
- [ ] Implement separate opt-in funding preview/reservation and exact gross/physical/retained-cash contract. All affected custody/history/GL consumers must represent the non-cash credit settlement honestly. No generic checkbox or changing expected cash to conceal shortage. Where a required adapter is unavailable, ship a tested explicit execution blocker and report this path incomplete; do not claim full application acceptance.
- [ ] Pass focused/Pg funded-settlement, role and legacy compatibility tests. Commit `feat(treasury): control explicit Collector credit application`.

## Task 6 — Forgotten borrower sources and reclassification (S7)

**Files:** `collector_surplus_resolution.py`, current protected correction/allocation services, funding and history projections; `test_collector_surplus_resolution.py`.
**Interfaces:** `resolve_source(...)` consumes a verified existing correction/source preview; transaction-level adapter retains caller's connection and exact dates. No fabricated Collector session, new allocator or direct balance edit.

- [ ] Test forgotten prior-day100 still in Collector custody; accepted excess100 later identified as borrower payment; prior-day100 plus actual today100 remain two source dates; no today's payment when absent; corrected due10100 makes surplus0; office cash already received never increases twice; old PASS/remittance snapshots remain immutable; late-date unsupported path blocks rather than applies today. Test partially returned40 before100 reclassification returns recovery-decision-required with traceable amounts, not negative credit or wage deduction.
- [ ] Run `python -m pytest -q gilbic_backend/tests/test_collector_surplus_resolution.py`; establish RED plus baseline protected chronology checks.
- [ ] Implement exact-source linking and capacity-limited resolution using existing historical correction and funding evidence. Revalidate all downstream receipt/loan/custody links under locks. Store unresolved/recovery exceptions without falsely cancelling actual borrower receipt or inventing a recovery asset. Expose a specific blocker when a safe adapter is absent.
- [ ] Pass real Pg protected allocator/history/rollback tests and explicit blocked cases. Commit `feat(treasury): resolve excess through protected source corrections`.

## Task 7 — Opening credit anchors and protected accounting (S8)

**Files:** resolution handlers, Treasury openings/reconciliation, protected accounting source maps; `test_collector_surplus_opening_accounting.py`.
**Interfaces:** `prepare_opening_credit(...)`, `activate_opening_credit(...)`; source projections for recognition/return/application/reclassification with explicit mapping readiness, no automatic GL posts.

- [ ] Test opening cash10100 already includes credit100: activation adds no cash and prevents duplicate historical import; missing actual figures stay unavailable; reactivation conflicts; wrong context denied. Assert recognition is not income, return principal not generic expense, no Collector-custody debit for owner-wallet sources, and GL posting/reversal causes zero extra subledger cash. Test closed-period/superseded-opening blockers and opening-source overlap.
- [ ] Run `python -m pytest -q gilbic_backend/tests/test_collector_surplus_opening_accounting.py`; establish RED.
- [ ] Implement owner-only evidenced anchors/current versions and protected source keys using actual configured accounts. Keep context/legal treatment and mapping blockers explicit, with no guessed2xxx account, funding journal or new loan/EIR formula. Include liabilities/unidentified/reserved subsets in available-cash presentation without subtracting or adding them twice.
- [ ] Pass focused/Pg opening/context/journal-source tests. Commit `feat(treasury): anchor Collector credits without duplicating cash`.

## Task 8 — Reconciliation, audit, recovery and safe disable (S9)

**Files:** Treasury reconciliation/recovery/restore manifests and compatibility guard; `test_collector_surplus_recovery.py`; existing disposable restore runner.
**Interfaces:** use existing durable outcomes/account watermark; extend restored source manifest to counts/cases/credits/actions/evidence and all linked movements.

- [ ] Test force failure after movement/before credit or audit/outcome rolls back accepted phase; same-key changed count conflicts; denied replay stays private; two account lock order avoids deadlock; reclassification changes review state of affected closed reconciliations without rewriting snapshots; feature disable retains visible credit and frozen uncertain return; rollback guard rejects incompatible release. Restore case with partial payout/credit application/source resolution and exact evidence bytes.
- [ ] Run `python -m pytest -q gilbic_backend/tests/test_collector_surplus_recovery.py`; record RED and disposable prerequisites.
- [ ] Complete transaction/uniqueness guards, result-phase validation, source-aware kill switch and read/restore compatibility. Distinguish a real cash movement from reclassification, reconciliation and GL events. No background financial retries, removed lock or destructive down migration to make rollback work.
- [ ] Pass parallel Pg races, forced rollback, same-source reconciliation and full synthetic restore. Commit `fix(treasury): preserve surplus integrity through retries and recovery`.

## Task 9 — Web receiver and own-Collector interfaces (S10)

**Files:** new `collector-surplus.js`, existing Treasury API/workspace and remittance-review module, role registrations, scoped CSS and PWA; `collector-surplus-contract.test.mjs`, `collector-surplus-workspace.test.mjs`.
**Interfaces:** `mountCollectorSurplus({root, api, session, signal}) -> dispose`; public read/command helpers call the versioned backend and existing request recovery. Current receiver uses snapshot/count/accept phases, not a second ledger.

- [ ] Write behavioral tests for count equality/over/short, unavailable preview, stale digest, pending-not-spendable, partial return, correct Cash/GCash account, exact result IDs/dispositions, same-actor recovery, another unfinished form/file retained, logout/permission cleanup and own-credit privacy. Old/new server capability mismatch must disable unsupported actions, not fall back to boolean acceptance.
- [ ] Run `node --test spina_portal/tests/collector-surplus-*.test.mjs`; establish RED.
- [ ] Implement permission-filtered local views and exact confirmation wording. Separate unresolved, outstanding and reserved totals. Collector return/application requests cannot self-approve. Preserve full evidence/history, selected task and focus, no wallet history in own-credit views or notifications. Stop sharing before private panels; no broadened capture markers or browser persistence.
- [ ] Pass new and existing Treasury/remittance/role/private-sharing suites; inspect1440/390/320px actual browser layouts using synthetic data. Verify all returned history via paging. Commit `feat(web): present counted remittance and Collector credit history`.

## Task 10 — Android and installed Windows parity (S10)

**Files:** new native page and existing Treasury model/repository/workspace/role registration; `collector_surplus_contract_test.dart`, `collector_surplus_page_test.dart`; Windows portal smoke coverage.
**Interfaces:** native strict DTOs mirror current backend enum/decimal/date/result fields; reuse encrypted attempt recovery and existing file-picking controls. Windows calls the same Web API without extra runtime money logic.

- [ ] Test exact count/credit/payout parsing, unconfirmed results, denied evidence/photo access, immutable reviewed file bytes, own-history privacy, multiple role authority and larger-text amount readability. Assert wrong returned recipient/account/credit rejected and no hidden financial retry after resume.
- [ ] Run focused native tests under actual `SpinaTheme.light` and analyzer; establish RED before changes. No claim of an emulator run from widget tests.
- [ ] Add native screen/actions and existing role entries without altering restored Management design or Collector one-tap payments. Use contract capability and existing private-file/security handling. Windows reuses portal; do not recreate retired Tkinter modules.
- [ ] Pass native tests, verify production-theme scale/money layouts and actual available Android/Windows synthetic flows. Record missing emulator/TalkBack/physical acceptance explicitly. Commit `feat(android): add protected Collector credit and count views`.

## Task 11 — End-to-end evidence, exports and independent review (S1–S12)

**Files:** all focused tests plus `test_collector_surplus_end_to_end.py`, operating/contract maps and private authorized export wiring.

- [ ] Run exact, over, short, unknown, genuine credit, missing borrower, cash return, GCash return+fee, future application, opening and recovery scenarios through actual disposable Pg services. Prove balances, credit capacity, source IDs and history in one integrated evidence ledger; include independent two-connection contention and audit failure. No mocks as substitutes for posting proof.
- [ ] Capture Web views for receiver count, pending case, recognition, own credit, partial return, uncertain return, application, history, correction blocker and opening at1440/390/320px (30 named samples). Native capture count, own credit and return at320/360/412 and text1.0/1.3/2.0 (27 named configurations) plus errors/keyboard. Windows checks receiver/Collector/history with same server amounts. These are required execution evidence, not completed by this plan.
- [ ] Verify private report includes expected/corrected/gross funding, physical accepted, pending identified portions, credits/returns/applications/reservations, source dates and actual accounts; own-Collector report redacts wallet and others. Reconciliation/GL/source subsets do not sum as extra money. Use existing private output patterns; no public export URL.
- [ ] Independent reviewer checks false ownership, duplicate cash, bypass receiving path, invalid source/custody mappings, reference replay, partial payout reclassification and privacy. Fix substantive findings with focused tests before closing evidence gaps. No source/evidence claims based only on previous PR prose.
- [ ] Commit evidence references and operating guide with tested versus blocked dispositions. Do not mark unsupported application/historical/GL paths completed.

## Task 12 — Final exact-head validation and handoff (S12)

- [ ] Verify dependency/integration status and final changed-file scope. Follow current locked CI prerequisites and run the established suites once on the integrated head, for example:

```sh
python -m pytest -q gilbic_backend/tests spina_backend_mobile/tests
npm run check:portal
npm run test:portal
node tools/build_portal.mjs
(cd gilbic_mobile && flutter pub get --enforce-lockfile && flutter analyze --fatal-infos && flutter test)
git diff --check
```

- [ ] Use the real disposable PostgreSQL DSN/migration chain and existing finance validators; skipped database tests are not passing posting evidence. Reuse current public-output/security/generated-host/restore checks. Do not create duplicate CI or rerun identical full suites just for receipts.
- [ ] Inspect the three existing required exact-head jobs: **Backend, quality, and security**; **Portal, Flutter, and Android**; **Financial and disposable PostgreSQL**. Retain actual run/job/SHA evidence. Old dependency CI or docs-only Green is not this feature's acceptance.
- [ ] Review coverage below and record blocked adapters/platform evidence separately. Leave real setup, opening credits, permissions and production feature flags untouched. Keep source-aware recovery guard; no incompatible downgrade or disposal of evidence.
- [ ] Update this PR from planning-only only after product commits exist; keep Draft/open/unmerged and automatic merge off. Synchronize GitHub, latest Notion checkpoint and Create State with exact head, dependency status, completed/remaining tasks, tests, screenshots/private-safe evidence and next owner action. Disclose failed connectors. No merge/deploy/live migration/Master checkbox changes.

## Coverage ledger at handoff

| Task | Coverage | Status |
| --- | --- | --- |
| 0 | Dependency and source/lock ownership | Pending Codex |
| 1 | S1/S4/S9 schema, exact contracts and authority | Not implemented |
| 2 | S2/S3 actual count/acceptance/cash once | Not implemented |
| 3 | S1/S3/S4 identification and credit | Not implemented |
| 4 | S5 return/reservation/recovery | Not implemented |
| 5 | S6 explicit application | Not implemented; opt-in adapter gate |
| 6 | S7 source corrections/reclassification | Not implemented; historical adapter gate |
| 7 | S8 opening and accounting | Not implemented; real mapping/count gate |
| 8 | S9 reconciliation/backup/rollback integrity | Not implemented |
| 9 | S10 Web and own-Collector scope | Not implemented |
| 10 | S10 Android/Windows parity | Not implemented |
| 11 | S11 and S1–S12 integrated evidence | Not run |
| 12 | S12 exact-head CI and handoff | Not run |

## Copyable Codex task

Implement this new Collector Excess/Surplus PR on branch `plan/collector-excess-surplus-20261002`. Read this plan/spec, original September9 decisions, latest Notion/Create State and live main/#490/#485–#489. It is a separate dependent workstream, not permission to overwrite or merge490. Resolve the reviewed Treasury dependency first; no duplicate cashbook or unapproved stacked diff. Follow Tasks0–12 with test-first small commits. Distinguish counted/accepted, pending identification, genuine credit, forgotten borrower money and wallet variance. Record full actual receipt once; protect shortage rejection, credit capacity, partial Cash/GCash returns, explicitly approved same-Collector application, original dates and safe source reclassification. Preserve exact money/permissions/independent approvals/financial recovery/GL/privacy. Prove real disposable Pg races/rollback, Web/Android/installed Windows and private reports; report blocked historical/application/GL/platform evidence honestly. Never invent balances, grants or real opening credits. Update exact-head evidence and GitHub/Notion/Create State. Keep Draft/open/unmerged; no mark-ready/merge/deploy/live migrations/real money/provider connection/owner-device install/live capture/Master acceptance changes. Finish with head, dependency, results, completed/blocked tasks and next owner action.
