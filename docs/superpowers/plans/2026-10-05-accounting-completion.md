# SPINA Accounting Completion Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development for bounded implementation/review tasks or superpowers:executing-plans for tightly coupled work. Execute continuously within the user's authorization. Preserve completed evidence and never count planned work as implemented.

**Goal:** Close the identified accounting integration and completeness gaps while keeping owner and future corporate books separate.

**Architecture:** One protected General Ledger engine per isolated database/deployment. Explicit book and wallet mappings govern source-linked postings. Database-enforced completeness gates precede closing, and statement packs reconcile to the same consistent snapshot.

**Tech stack:** Existing PostgreSQL/Supabase private schemas, Python/FastAPI/psycopg, web Portal and Flutter consumers. No new external service or dependency is required by the initial protection stage.

**Spec:** ../specs/2026-10-05-accounting-completion-design.md

## Global constraints

- Preserve existing posted history, loan allocation/EIR authority, permissions and evidence.
- No production query/write, migration, activation, monetary action or deployment in this implementation run.
- Do not invent real book identities, amounts, tax classifications or CPA approval.
- Existing Office work remains untouched in its own checkout; all changes here are on codex/accounting-completion-20261005.
- Use exact Decimal/NUMERIC money; no binary float, balance plugs or automatic omission of unsupported sources.
- New private tables/functions must revoke PUBLIC/client access, pin search paths and require current Management authority.
- Tests use a new task-owned loopback PostgreSQL cluster; one heavy process at a time.

## Review focus

1. An operational event with no draft must still block close (Task 2/5).
2. Receipt plus application or payout plus completion must not double-count cash (Task 3).
3. An unpaid but correctly recognized liability is legitimate at period end (Task 4/5).
4. A corporate book must not absorb an owner-personal wallet or historical owner journals (Task 1/3).
5. Concurrent posting or closing must not produce mixed-snapshot statements or stale readiness (Task 0/5).

## Task 0 — Stable baseline and immediate report integrity

Files: financial_statements_repository.py, financial_statements_api.py, matching tests; program evidence under the task-owned checkpoint directory.

Interface: preserve load_statement_pack(period_id=...) and its existing response fields; establish a read-only REPEATABLE READ transaction before the first report query.

- [x] Add a two-connection regression where a journal commits between period and cumulative reads; assert one consistent snapshot.
- [x] Verify failure against baseline, implement transaction isolation, rerun focused report checks.
- [x] Make the response distinguish arithmetic balance from source-completeness/annual-reporting approval; do not claim missing components exist.
- [x] Record source, commands, results and commit the reviewed change.

## Task 1 — Book identity and isolated corporate deployment contract

Files: new accounting_book_repository.py, accounting_book_api.py, additive book-identity migration, tests; main.py route registration; deployment/runbook documentation.

Interfaces: get_book_identity(); configure_book_identity(kind, entity_label, evidence_reference, evidence_digest, actor_user_id); require_accounting_context(context_id) under the same transaction. One immutable identity per database; no actual identity seeded by migrations.

- [x] Prove unconfigured state, strict exact retry, changed-identity rejection, wrong-role rejection and immutable evidence.
- [x] Implement Management setup/read routes and database functions; expose the identity with reports without accepting a client-supplied connection string.
- [x] Prove owner/corporate/synthetic context matches, and reject owner-personal wallets in corporate books.
- [x] Document independent database, auth, private evidence, backup and period setup; verify two synthetic databases cannot read each other's business rows.
- [x] Add book identity to web/native accounting entry and report labels; test stale/unauthorized reads without data leakage.

## Task 2 — Immediate close protection and visible source inventory

Files: additive close-completeness migration; close API/repository; close screens; new PostgreSQL acceptance tests.

Interfaces: accounting.period_source_blockers(period_id) returns source_type, source_id, effective_date, amount, reason; accounting.assert_period_source_complete(period_id) raises on any blocking row.

- [x] Write failing tests for an actual Treasury event and Collector credit movement with no GL posting, including a source without any draft; zero PASS must not block.
- [x] Derive blockers from authoritative rows and the Asia/Manila business date. Initial unsupported adapters stay blocking; do not fabricate completion.
- [x] Enforce the guard in review/prepare/post and expose exact blockers to Management.
- [x] Prove transaction rollback, concurrent source/close ordering, backdated evidence and legitimate matched payable behavior.
- [x] Run existing period-close regression and record any compatibility change explicitly.

## Task 3 — Treasury receipt, application, payout and transfer journals

Files: new reviewed mapping and source-posting migrations/modules/APIs; existing collection and payout admission guards; tests for each source family.

Interfaces: immutable mapping version; prepare_source_journal(source_type, source_id, expected_source_digest, mapping_version, actor); post_source_journal(preparation_id, confirmation_token, actor). Functions return existing exact results on identical retry and reject changed coordinates.

- [x] Specify deterministic line coordinates for the supported receipt, application, payout/transit, completion, transfer and fee paths; record wider product/correction extensions separately.
- [ ] Add a genuine RED test for each flow, duplicate/retry conflict, stale mapping/source and audit rollback.
- [ ] Implement one family at a time using existing protected journal/loan measurement routines. Replace 0137/0139 admission blocks only for the exact reviewed adapter.
- [ ] Add explicit prepare/review/post Management actions and private-state recovery; do not auto-post from collection operations.
- [ ] Reconcile source inventory to posting audit; preserve blocked status for any still unsupported correction case.

## Task 4 — Collector and other liability control schedules

Files: new Collector accounting adapter/queue, liability register and protected posting functions, web/native review screens and tests.

Consumes: Task 1 book identity; Task 3 mapping/posting identity. Produces per-source liability movement and aggregate control-account reconciliation.

- [x] Prove excess cash once, unidentified liability, credit reclassification, partial return, separate fees, incoming reversal and reservation-without-double-liability.
- [x] Implement immutable source-linked accounting and exact outstanding control balances for the supported source families.
- [x] Provide evidence-backed non-Collector liability recognition/settlement with counterparty, source, due date and account classification. Repayable owner funding remains distinct from capital.
- [x] Implement Collector future applications with exact reservations, actual cash/credit splits, separate dated postings, private scopes, both clients and restore verification (0157).
- [ ] Implement remaining historical corrections as separately reviewed adapters; retain their blockers until their tests pass.
- [ ] Verify legitimate unpaid balances can close when reconciled and no operational record disappears after settlement/reversal.

## Task 5 — Complete source reconciliation and closing snapshots

Files: extend Task 2 inventory/guards and close tests; EIR/ECL/tax assessment readiness integration.

- [x] Inventory active/voided collections, release/renewal/remittance, Treasury and liability sources without relying solely on prepared queues; unsupported sources remain explicit blockers.
- [ ] Reconcile exact source effects and date/book scope to posted entries and required assessment evidence.
- [x] Pin the inventory digest at review; revalidate at prepare/post under a consistent source lock order. Surface late changes without reopening history.
- [x] Reject missing/unmapped/stale obligations but permit matched unpaid liabilities, nonfinancial PASS and disclosed valid transit.
- [ ] Test failure after audit write, simultaneous close/source mutation and returned-to-open review handling.

## Task 6 — Reporting package

Files: financial_statements_repository.py/API, focused reporting modules, retained classification/note evidence migrations, Portal/Flutter statements and tests.

- [x] Add explicit cash/cash-equivalent and cash-flow category policies, with unavailable status for unclassified activity.
- [ ] Build cash-flow and changes-in-equity statements, including profit/loss, retained-earnings transfers, owner funding/withdrawals, noncash items, fees, internal transfers and reversals.
- [x] Add comparative periods and retained Management-reviewed notes/policy references without claiming external approval. The user delegated the accounting design.
- [x] Verify cash-flow ending cash equals GL cash; equity rollforward equals financial position; all sections share one snapshot and book identity.
- [ ] Test positive/loss/zero-activity periods, retired accounts, malformed data and role/session changes in web/native clients.

## Task 7 — Current-schema integration, recovery and release evidence

Files: tools/run_accounting_cycle_disposable_postgres_validation.py or a distinct current-schema successor; integrated tests; existing CI workflow; readiness/runbook documents.

- [x] Keep the bounded 0092 proof, and add explicit current-schema verifiers with no silent skips and loopback-only enforcement, including fresh 0154 close and restore.
- [ ] Compose all supported sources from Tasks 1–6 on fresh synthetic books and independently reconcile GL/cash/loan/liability/statement totals.
- [x] Prove duplicate/race/rollback/access controls and populated private-evidence backup/restore for the verified supported flows; repeat relevant proofs for each new adapter.
- [ ] Run focused tests, full required CI checks on the final source, client checks and one independent whole-change review; repair actionable findings.
- [x] Preserve a concrete rollout/forward-recovery plan. Keep actual entity/tax facts, opening figures and production parallel-close evidence as activation requirements. The delegated accounting design proceeds without an external design-approval gate. See `docs/accounting/accounting-release-and-recovery.md`; this does not certify the unfinished software work.

## Progress and evidence

The authoritative execution ledger is `docs/reviews/2026-10-05-accounting-completion-progress.md`. Checkboxes above are implementation targets, not claims of completion. Record completed task commits and remaining blockers there after each verified increment.
