# Cash & GCash Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development task-by-task. Keep one integration owner for shared financial contracts and schemas. Steps use checkboxes; retain failing-test/passing-test evidence before marking implementation complete.

**Goal:** Implement manual owner-received GCash proof/verification, exact account movements, actual disbursement links and cash reconciliation across Web, Android and Desktop, without mistaking Collector attribution for cash custody.

**Architecture:** A bounded treasury subledger in the existing backend records each actual movement once. Existing private evidence, loan allocators, custody, release/payroll/expense services and explicit GL posting remain authoritative for their outcomes. All clients use the same role-scoped API; no second local money engine or wallet integration.

**Tech Stack:** Existing FastAPI/Pydantic/psycopg/PostgreSQL, Python >=3.11, ES-module portal, Flutter/Dart and the installed Windows Edge/Chrome portal. Reuse pinned CI/lockfiles; no upgrades. Baseline CI uses Python3.12, Node24 and Flutter3.44.7.

**Spec:** [2026-10-02-cash-gcash-control-reconciliation-design.md](../specs/2026-10-02-cash-gcash-control-reconciliation-design.md).

**Status:** Implemented candidate under final integrated verification. The owner explicitly included #490 in the current PR completion task. Baseline `41a13eb59c9cc1b65a0a6a51f3b73db4a0895013`; local integration includes #485–#489. The coverage ledger below supersedes the original planning statuses. The step checkboxes retain the original requested acceptance granularity and are not a blanket completion claim. Actual count, wallet balances and cutoff are not supplied; synthetic fixtures permit implementation, not real activation. Draft/open/unmerged; no production execution.

## Global constraints

- One verified movement, multiple links: proof review, loan application, draft and GL posting never duplicate cash.
- Owner-wallet GCash never increases Collector cash-to-remit. Recorder/reporter/verifier/holder/assigned Collector are different facts.
- Exact server money and current Regular/7x7/combined/ADV/extra-principal rules; no parallel allocator or invented rates/fees. `automatic_source_posting=false` stays.
- API and repository enforce actor/device/account/context/object scope. Client own claims, authorized Collector reporting, narrowly delegated staff; no Management-role shortcut.
- No wallet MPIN/OTP/password, scraping/SMS automation, provider capability bypass or actual money-sending integration.
- New additive migrations0136/0137, permissions and endpoints are implemented in this candidate. Test only on an explicitly disposable DB. Feature disabled/unconfigured initially; no real accounts, balances or blanket grants seeded.
- Owner/pre-registration records, synthetic data and future corporate books stay separate. Count is not automatic income/capital/equity. No deletion or guessed reclassification of history.
- Online-only financial commands and durable unchanged-request recovery. Keep Android protected attendance separate and retain file/mirror privacy rules.
- No new framework/global cache/persistence layer/distributed workflow engine/CSV parser/native iOS workstream/package/version/signing change.
- Coordinate actual shared diffs with485–489; same PR branch, one integration owner, no competing PR or reset/overwrite of others' work.
- Once new funded records exist, disabling entry must preserve source-aware reads, custody exclusions and reconciliation. Rollback must not run legacy code that treats wallet records as Collector cash. No destructive down migration or deletion to make downgrade pass.
- Keep Draft/open/unmerged. No mark-ready/merge/tag/delivery/deploy/live migration/production credentials or transactions/owner-device install/live sharing/Master acceptance changes.

## Review focus

1. One transfer reported by several actors/devices, rematched from history, charged fees and replayed after timeout must affect wallet/loan only once — Tasks2–5,7–8.
2. Crash or stale allocation after receipt verification must retain received/unapplied funds without fake custody; pending claims must not gain payment authority — Tasks3–5.
3. Cutoff-straddling transfers and pre-cutoff receipts applied later must not double openings or hide transit — Tasks2,6–8.
4. Verified debit lacking valid business approval must remain an exception, not disappear, imply approval or trigger resend — Tasks6–8.
5. Personal statements, restricted account grants, revoked identity/device and mismatched evidence must stay isolated through reads, exports, recovery and rollout/rollback — Tasks1,3,8–12.

## File and ownership map

New backend modules under `gilbic_backend/src/gilbic_backend/`: `treasury_models.py` (strict values/commands/results), `treasury_authorization.py` (owner/account/context scope and projections), `treasury_repository.py` (accounts/openings/events/links/durable outcomes), `treasury_claims.py` (structured evidence and verification), `treasury_collection_posting.py` (same-transaction integration, not formulas), `treasury_disbursements.py` (source execution/transfer adapters), `treasury_reconciliation.py` (observations/matching/close), `treasury_api.py` (authenticated routes). Keep these bounded; do not build a generic framework.

Reserve the next unused SQL prefixes in Task0 for additive treasury schema/access and collection funding/source guards under `gilbic_backend/sql/`. Record exact filenames before editing; do not modify already-applied migrations or guess a number that a concurrent PR uses.

Existing seams to trace: `client_payment_proof_api.py`, `client_payment_proof_repository.py`, `office_review_evidence_storage.py`, `request_auth.py`, `main.py`, `collection_api.py`, `collection_posting.py`, `concurrent_receipt_collection_posting.py`, `receipt_application.py`, `remittance_repository.py`, `remittance_review_repository.py`, `employee_operations_repository.py`, `employee_operations_payroll.py`, `regular_collection_journal_preview.py`, their downstream SQL/7x7/combined/release/refund/accounting paths, and `spina_backend_mobile/src/spina_mobile_collections/` executor/contracts. The base bridge alone is not the complete runtime chain.

New portal files: `spina_portal/assets/treasury-api.js`, `treasury-workspace.js`, `treasury-payment-claim.js`. Bounded integration into `assets/roles/{management,employee,collector,client}.js`, existing proof/cash-disbursement modules, `app.js`, `ui.js`, `app.css`, and `spina_portal/sw.js`. Inspect live485–488 diffs first; reuse compatible lifecycle hooks.

New Flutter files: `gilbic_mobile/lib/src/core/treasury/treasury_models.dart`, `treasury_repository.dart`; `features/treasury/treasury_workspace_page.dart`, `treasury_claim_page.dart`. Integrate current role/proof/photo/Employee/Collector views; coordinate489 and preserve464's restored Management layout.

New Desktop files: `spina_app/treasury_client.py`, `spina_app/treasury_presenter.py`, `spina_app/tabs/treasury.py`. Task0 must discover the live registration seam. `spina_app/tabs/cash_control.py` did not resolve at planning baseline; the old Wave77 document is a proposal, not implementation evidence. Do not create a guessed replacement Cash Control subsystem.

Test paths: backend `gilbic_backend/tests/test_treasury_*.py`; portal `spina_portal/tests/treasury-*.test.mjs`; native `gilbic_mobile/test/treasury_*_test.dart`; Desktop `tests/test_treasury_desktop.py`. Below these are proposed additions unless described as existing.

## Proposed API contract — must be implemented, not assumed available

Canonical base `/api/v1/treasury`; mobile aliases `/api/mobile/v1/treasury` may reuse the exact handlers. Desktop calls the canonical authenticated API, never direct financial SQL.

Reads: `GET /workspace` returns current actor/device, contract1, scoped capabilities/accounts and blockers; `GET /accounts/{id}/movements`, `/claims`, `/claims/{id}`, `/receipts/{id}`, `/reconciliations/{id}`; `GET /requests/{request_id}` returns only an authorized actor/account-scoped durable outcome. Lists use deterministic order, limit1..100/default50, offset0..100000, `has_more` and complete server totals. No silent truncation or totals from loaded cards.

`POST /actions` accepts a strict Pydantic discriminated union: **account_configure, account_grant, opening_prepare, opening_activate, claim_review, receipt_verify, receipt_apply, disbursement_record, transfer_record, movement_classify, movement_correct, receipt_application_reverse, reconciliation_observe, reconciliation_match, reconciliation_close, reconciliation_supersede**. Each model contains stable `request_id`, target/source IDs, expected versions and allowed action-specific data. Actor/device/context derives from authenticated records. No arbitrary method dispatch or client-set verified balance/holder/GL flag. Durable results serialize `{contract_version:1, request_id, action, status, target_id, version, result}`; ambiguous response is not success.

`POST /receipts/{id}/allocation-preview` performs no money write: it returns current authorized loan choices/versions, exact amounts/coverage/intents, receipt capacity and server digest. Apply consumes and validates it under locks. The source-specific exact amount limits are inherited from approved validators and published in the implemented schema, not loosened here.

`POST /claims` and `/claims/{id}/versions` accept structured metadata plus validated private upload or authorized existing proof-version reference, using current upload conventions. Freeze exact media/body/metadata contract in Task1 and test both clients; do not assume the Client-only proof endpoint accepts Collector credentials. Private content reads are version/object scoped, not arbitrary URL/path fetches. Old proof APIs keep their evidence-only meaning with additive treasury links.

Verification and application use distinct durable phase IDs under one root attempt. One user confirmation may orchestrate them, but verified receipt remains durable if application fails. Current authorization is rechecked before replaying private results. Every write persists audit, outcome and its own state changes atomically; documented lock order must be compatible with existing loan/device/cash writers.

## Task 0 — Exact baseline, source graph and ownership

**Files:** Read spec, live refs/PRs, applicable AGENTS, Master296/later scope, Notion/Create State and CI/lockfiles. During implementation create `docs/operations/cash-gcash-control-contract-map.md`.

- [ ] Establish a clean isolated worktree on this PR branch. Check485–489 heads/diffs and record one owner/order for overlapping contracts. Preserve active work and reuse upstream fixes.
- [ ] Trace actual collection/combined/7x7 bridges, receipt/custody/refund/void triggers, dashboard/shortage totals, accounting prepare/post/reversal, release/payroll/expense execution and Desktop entrypoints. Record files/functions, source IDs, owner identity mechanism and transaction boundaries.
- [ ] Reserve migration prefixes/paths, document compatible lock order and the account/context binding policy. Inventory every consumer that assumes recorder equals cash holder. A source map is a deliverable, not permission to omit an integration.
- [ ] Run relevant baseline checks once or retain equivalent exact-head evidence. Separate inherited failures. Commit baseline/contract map and PR checkpoint; no production setup.

## Task 1 — Scoped accounts, strict contracts and readiness (C1,C2,C11)

**Files:** models/auth/repository/API, initial SQL, `main.py` and configuration; `test_treasury_contract.py`, `test_treasury_authorization.py`, `test_treasury_postgres.py`.
**Interfaces:** `TreasuryActor` from authenticated device context; `TreasuryService.execute(actor, command: TreasuryCommand) -> TreasuryResult`; `workspace(actor) -> TreasuryWorkspace`; `request_result(actor, request_id) -> TreasuryResult | None`. Internal helpers accept caller-owned connection; outer service owns commit/audit/outcome.

- [ ] Write failing tests: disabled_has_no_financial_effect; missing_owner_blocks_setup; permission_plus_account_scope_required; client_own_projection; collector_assignment_rechecked; personal_wallet_redacted; cross_context_link_rejected; changed_payload_same_request_conflicts; revoked_actor_cannot_replay. Assert actors cannot forge verifier/holder/settled status.
- [ ] Run `python -m pytest -q gilbic_backend/tests/test_treasury_contract.py gilbic_backend/tests/test_treasury_authorization.py`; failures must target missing behavior, not fixture errors.
- [ ] Implement contract1, scoped accounts/grants/context and additive schema constraints with no real defaults or blanket grants. Backend-only table access follows current conventions. Readiness stays disabled for production. Include safe old/new-client negotiation and strict media/metadata schemas.
- [ ] Pass focused/disposable migration/permission tests and retain outputs. Commit `feat(treasury): add scoped account and command contracts`.

## Task 2 — Exact movements and opening cutoff (C2,C3)

**Files:** repository/models/schema; `test_treasury_ledger.py`, `test_treasury_opening_postgres.py`.
**Interfaces:** `record_verified_event(conn, actor, event) -> TreasuryEvent`; `prepare_opening(actor, command) -> OpeningPreview`; `activate_opening(actor, command) -> OpeningPosition`; `account_snapshot(conn, account_id, cutoff) -> AccountSnapshot`. No loan/GL writes in these helpers.

- [ ] Write red tests: missing_opening_unavailable; explicit_zero_valid; opening_over_existing_history_rejected; precutoff_receipt_no_second_cash; duplicate_external_event_once; fee_components_not_double; unresolved_reference_not_auto_applied; personal_scope_enforced; opening_revision_retains_closed_evidence.
- [ ] Run `python -m pytest -q gilbic_backend/tests/test_treasury_ledger.py gilbic_backend/tests/test_treasury_opening_postgres.py` and confirm failures.
- [ ] Implement exact event/component identity, immutable opening revisions and C3 cutoff formula. Precutoff receipts retain positive application capacity with no new balance delta. No float, fake opening journal, inferred source of funds or balance plug. Verified unclassified events remain exceptions, not approved business payments.
- [ ] Prove10000+1000-2000-300-15=8685; observed8670 gives-15. Test source limits, calendar/instant rollover, unknown timing and repeat activation. Commit `feat(treasury): anchor exact movements to observed openings`.

## Task 3 — Client and Collector evidence claims (C4,C11)

**Files:** claims/API/auth, bounded proof-service reuse; `test_treasury_claims_api.py`, `test_treasury_claims_postgres.py`.
**Interfaces:** `submit_claim(actor, metadata, evidence) -> Claim`; `append_claim_version(actor, claim_id, expected_version, metadata, evidence) -> Claim`; `review_claim(actor, command) -> Claim`. Existing private bytes/history remain reusable behind explicit scope policy.

- [ ] Write failures: own_client_upload; assigned_collector_without_impersonation; revoked_assignment_denied; employee_review_not_receipt_verification; duplicate_reports_link_one_receipt; conflicting_borrower_no_leak; third_party_sender_allowed; stale_version_denied; missing_tampered_file_denied; old_reviewed_not_paid; uncertain_upload_replay_once.
- [ ] Run both new suites with `python -m pytest -q` and record the red result.
- [ ] Implement structured claims, retained metadata/file versions and narrow staff access. A false first claim must not reserve someone else's receipt. Upload/review alone creates no wallet/collection/GL effect and no schedule/PASS adjustment. Keep correction reasons and original submitter; private statement is not Client-visible proof.
- [ ] Pass new and existing proof/privacy suites, asserting zero financial writes for evidence-only actions. Commit `feat(treasury): share scoped payment proof submissions`.

## Task 4 — Verify recipient receipt and apply safely (C5,C2)

**Files:** claims/repository/collection adapter and narrow runtime transaction seams; `test_treasury_receipt_verification.py`, `test_treasury_application_postgres.py`, `test_treasury_application_concurrency.py`.
**Interfaces:** `verify_receipt(actor, ReceiptVerify) -> VerifiedReceipt`; `preview_receipt_application(actor, receipt_id, choices) -> AllocationPreview`; `apply_receipt(actor, ReceiptApply) -> ApplicationResult`; internal `apply_in_transaction(conn, actor, preview, funding_context)` reuses protected allocation/receipt machinery with server-constructed funding context.

- [ ] Write failures: sender_photo_not_authority; verified_then_apply_failure_stays_unapplied; crash_between_phases_recovers; two_reviewers_once; Regular_7x7_atomic; later_cash_invalidates_preview; excess_not_silent_principal; stale_evidence_recipient_denied; late_date_unsupported_is_explicit; malformed_result_not_success.
- [ ] Run all three suites; concurrency/atomicity evidence must use a disposable PostgreSQL transaction, not mocks alone.
- [ ] Persist verified receipt once, then consume capacity through current protected allocators. Revalidate actor/account/context/receipt/loan/evidence versions, digest and intents under locks. No forged Collector session, made-up sequence, local formula or self-HTTP call that breaks atomicity. Application persists all official rows/source links/audit/outcome together; its rollback does not erase an earlier verified receipt.
- [ ] Prove simultaneous cash/Gcash, combined/partial application, refund capacity and unchanged-request recovery. Historical-date limitations leave visible unapplied funds. Commit `feat(treasury): apply verified receipts through protected allocations`.

## Task 5 — Correct custody and accounting sources everywhere (C6)

**Files:** typed funding schema/adapter, actual bridge/SQL hooks and all Task0 consumers; regular/7x7 GL preview/post/reversal. Tests `test_treasury_custody_postgres.py`, `test_treasury_accounting_sources.py`.
**Interfaces:** trusted `FundingSourceContext` binds event/receipt/account/context and custody category; `funding_for_collection(conn, transaction_id)` validates the stored source. Legacy cash callers keep their contract; public payloads cannot supply arbitrary verified funding.

- [ ] Write failures: owner_gcash_excluded_from_remittance; employee_recorder_not_holder; cross_route_gcash_not_cash; note_text_no_reclassification; wallet_source_not_1020; legacy_cash_unchanged; pre_registration_not_legal_GL; apply_then_GL_no_double_cash; void_not_automatic_refund.
- [ ] Run `python -m pytest -q gilbic_backend/tests/test_treasury_custody_postgres.py gilbic_backend/tests/test_treasury_accounting_sources.py`; inspect actual source/custody rows.
- [ ] Make funding available within the posting transaction before source/audit/accounting classification. Never insert fake cash then patch it. Update all inventoried predicates/projections, including cross-area/refund/shortage and actual-cash totals. GL mapping remains explicit; personal/unmapped source blocks with explanation, not guessed1030/1020. No accounting-calculation changes.
- [ ] Prove cash3000+appliedGCash1200+pending400 = official4200/cashdue3000, with legacy cash and refund fixtures, spoofed/absent metadata, and both product paths. Feature remains disabled until application and source handling pass together. Commit `fix(treasury): separate wallet receipts from Collector custody`.

## Task 6 — Actual outgoing payments and transfers (C7,C8)

**Files:** disbursement adapters/repository/models and traced source services; `test_treasury_disbursements_postgres.py`, `test_treasury_transfers_postgres.py`.
**Interfaces:** `record_disbursement(actor, DisbursementRecord) -> TreasuryEvent`; `record_transfer(actor, TransferRecord) -> TransferResult`; `link_existing_source(conn, event_id, source_kind, source_id, expected_version)` validates existing source without granting its approval.

- [ ] Write failures: approved_unpaid_zero_debit; expense_and_journal_one_debit; payroll_owner_rule; unauthorized_actual_debit_visible_exception; wrong_payee_amount_version_denied; release_signing_office_rules_retained; partial_payout_capacity; debited_destination_pending; own_transfer_no_income; fee_components; cutoff_straddle; private_spend_not_business_expense.
- [ ] Run both suites on disposable DB and confirm failures.
- [ ] Connect source-specific authorization and real execution evidence. Actual debit reduces wallet even before destination acknowledgment, without completing borrower/custody steps falsely. Unapproved observations stay exceptions. Pair transfer legs at real times with transit and responsibility distinct; no double-held money or invented fee/reservation.
- [ ] Prove later statement matching and GL posting don't duplicate cash; timeout/cancel cannot resend. An unsupported cash-only release contract must be safely extended with tests or shown blocked, never given fictional cash confirmation. Commit `feat(treasury): reconcile actual outgoing payments and transfers`.

## Task 7 — Match transactions and close reconciliations (C9)

**Files:** reconciliation/API/repository; `test_treasury_reconciliation.py`, `test_treasury_reconciliation_postgres.py`.
**Interfaces:** `observe_statement(actor, command) -> Observation`; `match_observation(actor, command) -> Match`; `preview_reconciliation(actor, account_id, cutoff) -> ReconciliationPreview`; `close_reconciliation(actor, command) -> ReconciliationResult`. Close validates opening/account/movement watermark under transaction locks.

- [ ] Write failures: zero_difference_with_offsetting_missing_rows_not_reconciled; match_existing_event_no_new_cash; component_matched_once; net_gross_fee_duplicate_block; timezone_cutoff_match; close_vs_new_entry_conflict; partial_history_not_complete; unmatched_ledger_entry; pending_destination_separate; late_event_supersedes; variance_no_auto_expense.
- [ ] Run `python -m pytest -q gilbic_backend/tests/test_treasury_reconciliation.py gilbic_backend/tests/test_treasury_reconciliation_postgres.py` and confirm failures.
- [ ] Implement manual observations plus private history attachment, deterministic pagination and server totals. Statement entry alone does not authorize a loan payment. Close only the exact declared coverage with valid cash matches/balance; wallet reconciliation may coexist with a separately visible loan-purpose or destination exception. No balance-edit/forced-adjustment control.
- [ ] Test matching/concurrency/coverage and immutable closed snapshots. Late/backdated evidence creates reviewed supersession and flags later dependent closes. Commit `feat(treasury): add evidence-backed account reconciliation`.

## Task 8 — Corrections, recovery, backup and safe rollback (C8,C11)

**Files:** narrow service/adapter changes and existing backup/release guards; `test_treasury_reversals_postgres.py`, `test_treasury_recovery_postgres.py`.
**Interfaces:** `correct_movement(actor, command) -> CorrectionResult`; `reverse_application(actor, command) -> ApplicationResult`. Actual provider refund/reversal is a separate verified event linked to original identity, not inferred from loan/GL changes.

- [ ] Write failures: reallocation_no_wallet_delta; void_leaves_unapplied; actual_refund_once; false_verification_unwind_retains_evidence; protected_GL_reversal; reference_not_reusable_after_reversal; audit_result_failure_rollback; restart_same_request; unavailable_private_bytes_fail; restore_all_links; disabled_entry_preserves_funding_reads; legacy_rollback_with_wallet_rows_rejected.
- [ ] Run the two suites red, including disposable corruption/repeated restore and feature-disable/downgrade cases.
- [ ] Implement restricted reasoned corrections, current versions and immutable originals. Keep application reversal, erroneous observation correction, real refund and GL reversal separate. Add new evidence/link tables to backup/restore manifests and compatibility checks. Disabling feature blocks new work but preserves proper existing balances/custody; no destructive down-migration or legacy reinterpretation.
- [ ] Verify grant/account changes invalidate previews, denied replay redacts private evidence and no real references appear in logs. Commit `fix(treasury): preserve correction and recovery integrity`.

## Task 9 — Web role workflows (C10)

**Files:** new portal modules and bounded shared integrations. Tests `treasury-api.test.mjs`, `treasury-workspace.test.mjs`, `treasury-claim.test.mjs`, `treasury-privacy.test.mjs`.
**Interfaces:** `createTreasuryClient(api)` validates current contract/request/action/target/version; `mountTreasuryWorkspace({root, api, session, signal}) -> cleanup`; `mountTreasuryClaim({root, api, session, signal, borrowerContext}) -> cleanup`. Reuse integrated shell lifecycle, no new global registry.

- [ ] Write failures: both_submitters_same_service; specific_wallet_not_1030; verify_apply_partial_visible; save_preserves_other_file_node; stale_session_no_render; delegated_staff_no_wallet_history; exact_retry_only; unavailable_not_zero; no_double_cash; unpaid_draft_not_paid; notifications_exact_target; mobile_amount_reference_readable.
- [ ] Run `node --test spina_portal/tests/treasury-*.test.mjs` or explicit filenames when glob expansion is unavailable; confirm behavior failures.
- [ ] Add account/review/movement/transfer/reconciliation/exception views under existing navigation and scoped Client/Collector proof actions. Keep cash Pay and existing permissions. Show manual verification, timestamps/coverage and honest partial states; preserve draft/File nodes and uncertain commands without new persistence. Recipient statements stay private.
- [ ] Pass focused/shared tests; inspect synthetic1440/390/320 layouts, long lists/amounts, keyboard/focus/error/recovery. Verify public/PWA output excludes fixtures/private files and protected-response caching. Commit `feat(web): expose scoped Cash and GCash workflows`.

## Task 10 — Android same-contract workflows (C10,C11)

**Files:** new typed treasury models/repository/shared pages and role/proof/ledger integration; `treasury_repository_test.dart`, `treasury_workflows_test.dart`, `treasury_privacy_test.dart`.
**Interfaces:** typed `TreasuryRepository` follows contract1; pages receive unchanged session/device provider and injectable fake repository. Exact API money remains decimal text/minor units, not formatting output reused as arithmetic.

- [ ] Write failures: client_own_claim; collector_camera_claim; typed_channel_not_notes; partial_phase_result; denied_scope_cleanup; no_private_statement_mirror; photo_recovery_same_claim; offline_no_post; server_cash_totals_match; large_text_preserves_amount_actions.
- [ ] Run focused native tests with pinned SDK/production theme; missing SDK is blocked, not Green.
- [ ] Integrate current picker recovery/navigation and Employee modules, preserving489/464 and Collector one-tap/atomic cash behavior. No whole-wallet visibility for Collector. Status recovery preserves exact attempt/file version; no automatic financial upload/post after restart.
- [ ] Inspect320/360/412 widths and1.0/1.3/2.0 text scale for new views/affected homes, keyboard/images/error/access states. Native evidence is distinct from Web; reuse generated-host packaging. Commit `feat(android): add manual GCash and cash-control views`.

## Task 11 — Desktop and report source parity (C6,C10)

**Files:** Desktop adapter/presenter/tab and actual registration/report seams from Task0; `tests/test_treasury_desktop.py`.
**Interfaces:** `DesktopTreasuryClient` uses existing authenticated API transport where available; `TreasuryPresenter` renders immutable server snapshots. No local loan/cash-authority calculations or direct financial SQL; unavailable transport fails closed.

- [ ] Write failures: no_SQL_money_write; API_account_cutoff_match; forecast_not_actual; counted_cash_no_collection_doubleadd; owner_wallet_zero_collector_cash; cross_role_receipt_consistent; private_export_scope; API_failure_not_zero; no_source_spoof; retained_print_geometry.
- [ ] Run `python -m pytest -q tests/test_treasury_desktop.py` red using fake transport; verify true startup bindings, not proposed archived files.
- [ ] Wire backend Cash & GCash Control and source-aware collection/remittance/cash reports. Keep forecasting labeled planning-only. Preserve established print layouts and immutable receipts except needed truthful source labels; don't issue false cash-custody acknowledgments.
- [ ] Pass tests plus actual Windows/Tkinter synthetic smoke/print-preview where available. Record missing platform/printer evidence honestly. Commit `feat(desktop): align cash control and reports with treasury sources`.

## Task 12 — Integrated acceptance and owner setup handoff (C1–C12)

**Files:** all new suites, current runtime/CI/recovery manifests as needed without weakening, `docs/operations/cash-gcash-control.md`, contract map and this checklist.

- [ ] Run full disposable chain: fixture accounts/opening; duplicate Client/Collector claim; delegated proof review; recipient verification; Regular/7x7 application; route/client/receipt funding; cash payment and cash-only remittance; actual expense/payroll/release/fee/transfer/refund; statement matches and exact cutoff close. Verify same source/results on Web/Android/Desktop and protected GL disposition, including rollback/race/denied cases.
- [ ] Prove precutoff allocation without wallet inflow, failed allocation retaining receipt, unauthorized observed debit, transit at cutoff, fee duplicates, historical-date blocker, versioned close correction and source-aware feature-disable rollback. No fake funds, automatic GL plug or conversion of historical Reviewed proof.
- [ ] Run full current checks with actual CI prerequisites on the integrated head. Baseline pattern:

```sh
python -m pytest -q gilbic_backend/tests spina_backend_mobile/tests
npm run check:portal
npm run test:portal
node tools/build_portal.mjs
(cd gilbic_mobile && flutter pub get --enforce-lockfile && flutter analyze --fatal-infos && flutter test)
python -m pytest -q tests/test_treasury_desktop.py
git diff --check
```

Required DB tests must actually use approved disposable DSN/migrations; collect skipped reasons and never report skipped DB proof as success. Follow the existing financial/disposable-PostgreSQL workflow for its exact fixture runner. Reuse public-output secret checks/generated Android host. Do not repeat unchanged successful full suites only for receipts or trigger delivery.

- [ ] Retain exact SHA, commands/results, DB/race/rollback evidence, cross-role views, private exports, reports and restore checks. Web, Android/native, actual Windows and physical-device evidence are separate statuses. Real balances/wallet data never enter public artifacts.
- [ ] Keep production feature disabled until intended adapters, custody/accounting-source/permission tests, cross-surface behavior and owner readiness pass. Missing actual count is a setup gate, not permission to invent one. Private owner checklist: holder/alias/permitted use, owner/delegates, common cutoff, counted cash by custodian, wallet/bank observations, personal/third-party portions, existing-history overlap and pending/unapplied/transit details. No real count is recorded by this PR.
- [ ] Map unsupported legal-book ownership or payout-source contracts explicitly and keep those actions blocked. A generic manual note is not a completed adapter. Pre-registration recordkeeping is not lending authorization and cannot silently become corporate books.
- [ ] Inspect existing exact-head jobs **Backend, quality, and security**, **Portal, Flutter, and Android**, **Financial and disposable PostgreSQL**; retain run IDs, no duplicate workflows/weakening. Pending/Red and docs-only Green are not implementation acceptance.
- [ ] Review spec/task/test coverage and integrated diff. Change PR description from planning-only only when product commits exist; keep Draft/open/unmerged. Sync exact SHA, outcomes, platform blockers, pending count/configuration and next action to GitHub/Notion/Create State; disclose failed connectors. No automatic release/deploy/production migration/activation.

## Coverage ledger

| Task | Required coverage | Handoff status |
| --- | --- | --- |
| 0 | Live graph/Desktop seam/migration paths/ownership | Complete: [contract map](../../operations/cash-gcash-control-contract-map.md), reserved0136/0137, integrated485–489; installed Windows portal is the live Desktop seam. |
| 1 | C1/C2/C11 scoped accounts/context/contracts | Implemented; strict16 commands, disabled setup, current actor/device/account permissions and private projections tested. Final revoked-view repair under verification. |
| 2 | C2/C3 exact events and observed opening | Implemented; exact decimal movement components, observed opening, duplicate/reference and pre-cutoff boundaries in Treasury ledger/PostgreSQL tests. No real opening supplied. |
| 3 | C4/C11 both submitters/evidence/privacy | Implemented; own Client and canonical assigned/delegated Collector claims, private immutable versions, upload/replay integrity and revoked authority tested. |
| 4 | C5 verification/protected allocation | Implemented; actual Regular/7x7/combined scheduled/ADV/principal engines, digest/stale checks, concurrent same-request outcome, component rollback and protected reversal tested. |
| 5 | C6 custody/remittance/GL sources | Implemented;0137 trusted funding before notices, immutable source, cash-only custody/readers and blocked unmapped GL. Funding and legacy-reader regressions tested. |
| 6 | C7/C8 actual payouts/transfers/fees/personal | Implemented manual movement and transfer controls; real protected Payroll/Advance adapters proven. Cash-only expense/release/renewal source completion remains explicitly blocked, as allowed by Task6; no claim of full payout-source parity. |
| 7 | C9 transaction and balance reconciliation | Implemented; exact component matching, balanced-unresolved distinction, immutable close and private export tested. Final close/write race, dependent supersession and Manila cutoff tests passing; final combined run pending. |
| 8 | C8/C11 correction/recovery/backup/rollback | Implemented; immutable corrections, replay, actual refund, restored funded application/transfer/close/private bytes proven. Runtime preflight and persistent incompatible-rollback guard tested without host deployment. |
| 9 | C10 Web four-role scope/parity | Implemented;1,227 portal tests,230 syntax modules/build, actual browser14 behavior checks/12 layouts; final independent privacy/recovery findings being closed. |
| 10 | C10/C11 native Android | Implemented typed contract and four role entries; final camera/recovery/matrix/analyzer/full-suite verification in progress. |
| 11 | C6/C10 Desktop/reports | Installed Windows portal reuses canonical API; all four roles tested in actual Edge app mode. Private reconciliation export and source labels tested. No retired Tkinter replacement or physical printer acceptance. |
| 12 | C1–C12 DB/UI/platform/integration/readiness | Fresh schema0137+59 Treasury tests,79 Treasury/recovery checks,116 allocator/funding/preflight checks and restored225 table fingerprints passed. Full backend/native and exact-head CI pending; no new scanner fingerprints. Supported-source scope and physical acceptance remain explicit. |
| Owner count | Actual opening/aliases/cutoff/permitted use | Not supplied; never guess. Feature remains disabled/unconfigured. |

Current operation and recovery instructions: [cash-gcash-control.md](../../operations/cash-gcash-control.md).
The intentionally blocked cash-only source contracts mean the Task12 expense/release
completion chain is not represented as passing. Backend synthetic acceptance, native
widgets, Windows browser evidence, physical device acceptance and production rollout
are separate statuses. Final CI must be checked on the published implementation head.

## Owner-started Codex task

Implement the linked Cash & GCash Control design and Tasks0–12 on this planning PR's branch. Read both documents and latest GitHub/Notion/Create State/485–489 first. Preserve manual recipient-side verification, Client and authorized-Collector proof entry, narrow employee authority, one movement with multiple links, typed destination, existing allocators, financial recovery and private/legal-book boundaries. Include actual disbursements/transfers/fees/refunds/personal items and full transaction/cutoff matching, not only proof upload or UI totals. Keep received-unapplied/debited-unconfirmed visible; no double opening, forced balance plug or fake Collector custody. Use test-first verified commits, real disposable PostgreSQL concurrency/rollback proof, source-aware safe disable/rollback and same-contract Web/Android/Desktop reporting. Never invent owner counts or publish real wallet data. Update evidence and GitHub/Notion/Create State after meaningful progress. Leave Draft/open/unmerged and production unconfigured; no merge/mark-ready/deploy/live migration/provider integration/real transactions/owner-device install/live capture/Master acceptance. Finish with exact SHA, results, source parity, native/Windows evidence and honest remaining gaps/owner inputs.
