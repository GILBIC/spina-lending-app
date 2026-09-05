# Borrower Operational Schedule + Catch-up Implementation Plan

**Goal:** Make SPINA persist the borrower-caused operational schedule that Management approved: short/missed finalized dates move the remaining schedule forward, later normal catch-up can contract the remaining schedule, and Advance is unavailable while Past Due/borrower extension exists.

**Spec:** `docs/superpowers/specs/2026-09-04-borrower-operational-schedule-catchup-design.md`

**Base:** `main` at `ae01b75769836ecde5e30682c70505931bddb305`

**Branch:** `fix/operational-schedule-catchup`

**Test rule:** Every production-code behavior starts RED, then minimal GREEN, then refactor. Do not merge or deploy from a red state.

---

## Task 1 — Pure borrower shortfall forward-shift planner

**Files**
- Modify: `gilbic_backend/tests/test_rolling_schedule.py`
- Modify: `gilbic_backend/src/gilbic_backend/rolling_schedule.py`

**RED**
1. Add a test for Day 5 shortfall on a daily schedule that expects installment 5 and every later row to move one operational slot: D5→D6, D6→D7, D7→D8.
2. Run the focused test and prove it fails because the borrower-shift planner does not exist/does not return the required shifts.

**GREEN**
3. Add an immutable shift-result type and `plan_borrower_shortfall_shift(...)` pure function.
4. Reuse current ordered effective dates for interior rows; use cadence advancement only for the tail. Respect blocked dates for the tail and fail closed for unsupported/custom cadence.
5. Run focused + `test_rolling_schedule.py` tests.

**Additional RED/GREEN cases**
6. Partial row shifts exactly like a full miss.
7. Fully satisfied date produces no shifts.
8. Repeated miss of the already-shifted same installment moves it forward again.
9. 7x7 structural row threshold is the full agreed installment row, not interest only.
10. Existing installment IDs and contractual dates are unchanged.

---

## Task 2 — Pure catch-up contraction planner

**Files**
- Modify: `gilbic_backend/tests/test_rolling_schedule.py`
- Modify: `gilbic_backend/src/gilbic_backend/rolling_schedule.py`

**RED**
1. Add one-extension scenario where the current row is paid and one additional shifted future row becomes fully covered by normal catch-up.
2. Expect only the later remaining schedule to move back one existing operational slot and maturity to contract one slot.
3. Add partial catch-up case: a future row that is only partially covered must not contract the schedule yet.

**GREEN**
4. Add `plan_borrower_catchup_contraction(...)` that takes the current ordered schedule, number of active borrower slots, and number of newly completed catch-up rows.
5. Never move already-reached/settled history. Contract only later active rows and never remove more slots than are active.
6. Add multi-slot catch-up and No Collection/irregular operational-date regression cases.

---

## Task 3 — Protected Regular allocation understands catch-up before Advance

**Files**
- Modify: `gilbic_backend/tests/test_voluntary_extra_allocation.py`
- Modify: `gilbic_backend/src/gilbic_backend/contract_schedule_engine.py`
- Modify: `gilbic_backend/src/gilbic_backend/voluntary_extra_collection_posting.py`

**RED**
1. One active extension, current operational due ₱100, next shifted row ₱100, normal receipt ₱200: expect ₱100 current + ₱100 borrower catch-up, with no Advance/Principal Reduction choice required.
2. Normal ₱150: expect ₱100 current + ₱50 catch-up; no slot contraction yet.
3. Explicit Advance while an open Past Due/active borrower extension exists: reject with a stable business error.
4. Once active borrower extension is zero, preserve existing explicit Advance/Principal Reduction behavior.

**GREEN**
5. Add a distinct allocation basis for borrower catch-up in the protected planner/DB constraint migration.
6. Let Scheduled normal payment consume chronological catch-up rows up to the active borrower extension boundary.
7. Keep true excess fail-closed unless the existing explicit borrower extra intent is supplied.

---

## Task 4 — Versioned borrower schedule persistence

**Files**
- Create: next safely named SQL migration under `gilbic_backend/sql/` after verifying duplicate `0109_*` migration conventions.
- Create/Modify: migration tests under `gilbic_backend/tests/`
- Modify: `gilbic_backend/src/gilbic_backend/management_no_collection_repository.py` only where shared operational-version helpers can safely be extracted/reused.
- Create: `gilbic_backend/src/gilbic_backend/borrower_schedule_adjustment_repository.py`

**RED**
1. Migration contract tests require generic adjustment event date, borrower shortfall/catch-up adjustment types, active borrower extension slots, immutable adjustment item evidence, and catch-up allocation basis support.
2. PostgreSQL integration test proves one shortfall writes all moved row dates + version + slot count atomically.
3. Idempotent duplicate finalization does not add a second slot/event.
4. Catch-up transaction decrements slots and moves only later remaining rows transactionally.

**GREEN**
5. Generalize existing operational adjustment evidence without weakening No Collection semantics.
6. Lock active schedule/state and use expected operational version.
7. Preserve `loan_installment_operational_dates` as the one current effective-date authority.
8. Invalidate stale collection state/revisions after any effective-date mutation.

---

## Task 5 — Server-authoritative elapsed-date finalization without a new daily-close UI

**Files**
- Create: `gilbic_backend/src/gilbic_backend/borrower_schedule_finalization.py`
- Create: `gilbic_backend/tests/test_borrower_schedule_finalization.py`
- Modify only the proven server-owned operational integration point after repository search/tests identify it.

**RED**
1. Same-day partial payment is never finalized early.
2. An elapsed scheduled date with unresolved amount finalizes exactly once and persists one forward shift.
3. An elapsed date that was fully satisfied creates no borrower shift.
4. Repeated elapsed dates can shift the same unresolved installment repeatedly.

**GREEN**
5. Add idempotent finalizer from authoritative PostgreSQL aggregate allocation state.
6. Do not add a mandatory Open/Close Business Day workflow.
7. Do not mutate merely because a client opens View Schedule.
8. Wire the finalizer only at a proven server-owned operational boundary; document the boundary in tests.

---

## Task 6 — Persist catch-up contraction in the payment transaction

**Files**
- Modify: `gilbic_backend/src/gilbic_backend/voluntary_extra_collection_posting.py`
- Modify: `gilbic_backend/src/gilbic_backend/concurrent_receipt_collection_posting.py`
- Modify: `gilbic_backend/src/gilbic_backend/past_due_promise_progress.py` only if the new allocation basis must reduce existing Past Due evidence.
- Add/Modify PostgreSQL integration tests.

**RED**
1. Normal ₱200 on a one-slot extension posts current + catch-up allocation and contracts future schedule in one transaction.
2. Forced schedule-adjustment failure rolls back receipt allocation and schedule contraction together.
3. Catch-up reduces the matching open Past Due/promise balance without rewriting the original Past Due reason history.
4. Advance intent remains blocked until Past Due/borrower extension is gone.

**GREEN**
5. Apply Past Due progress to both required and borrower-catch-up allocation bases as appropriate.
6. Persist catch-up schedule contraction before transaction commit.
7. Record immutable catch-up evidence including source transaction and slot count before/after.

---

## Task 7 — Collector schedule uses persisted operational dates only

**Files**
- Modify: `gilbic_backend/src/gilbic_backend/collector_schedule_repository.py`
- Modify/add: Collector schedule repository tests.

**RED**
1. After Day 5 miss is persisted, Day 6 exposes only the shifted current obligation; it must not recreate old Past Due + original Due Today stacking.
2. After catch-up contraction, future maturity/rows reflect persisted effective dates.
3. No Collection rows remain separate and visible.

**GREEN**
4. Remove legacy rolling projection as a second authority for extension count/maturity where persisted operational state is available.
5. Read borrower extension slots and effective maturity from authoritative persisted state/rows.

---

## Task 8 — Shared client schedule read

**Files**
- Add a shared read repository/service under `gilbic_backend/src/gilbic_backend/` using the same operational installment source.
- Modify the existing client API module that currently returns raw `lending.loans.due_date` after locating its exact path on current head.
- Add backend API tests.

**RED/GREEN**
1. Client schedule is read-only `Payment Date -> Amount -> Status`, optional Details.
2. Regular and 7x7 remain separate.
3. Current operational maturity is exposed separately from contractual maturity.
4. Client cannot see another client's loan/schedule.
5. 7x7 client progress must not label principal-only movement as total `% paid`.

---

## Task 9 — Full verification and project-state synchronization

1. Run focused Python tests after every slice.
2. Run complete backend suite, quality checks, disposable PostgreSQL integration, portal/mobile tests affected by API changes, and exact-head `SPINA CI`.
3. Verify no production migration/deployment occurred from the feature branch.
4. Update Master Issue #296, Notion Current Project State, and Create State with exact branch/head, RED/GREEN evidence, remaining blockers, and next task.
5. Keep PR Draft until all Priority #1 acceptance evidence is green and reviewed.
