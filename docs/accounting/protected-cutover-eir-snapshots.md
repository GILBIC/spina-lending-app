# Protected per-loan cutover EIR snapshots

Status: **Stage 5D.2 protected accounting foundation**. Migration 0039 installs immutable snapshot controls only. It does not backfill existing preparations, prepare a journal, post a journal, create Default/ECL entries, or enable automatic source posting.

## Why this stage exists

The Stage 5D measurement function is intentionally read-only and recomputes a loan's cutover carrying amount from lending source rows. That is useful before opening-balance preparation, but it cannot remain the ledger anchor after a protected opening journal has been prepared: a later correction or void of pre-cutover source data could change a recomputed measurement while the already-prepared or posted General Ledger opening entry remains unchanged.

Migration 0039 therefore captures an immutable **per-loan cutover EIR snapshot in the same database transaction that inserts `accounting.opening_balance_journal_preparations`**.

## Transactional capture and source serialization

The preparation capture trigger acquires the lending `SHARE` table locks in the writer-compatible order used by collection posting:

- `lending.loan_collection_state`
- `lending.loans`
- `lending.loan_types`

Collection/payment/void/correction paths require conflicting write locks on those sources. Using the same state-before-loan order prevents a final-payment writer and snapshot capture from waiting on each other in reverse order. A source writer that commits first is visible to snapshot capture; a writer arriving after the snapshot locks waits until the preparation transaction completes.

After the locks are held, the trigger rechecks `accounting.loan_cutover_readiness`. A blocked active loan aborts snapshot capture and therefore rolls back the whole journal-preparation transaction.

## Snapshot evidence

For every active loan, the trigger calls the existing Stage 5D.1 `accounting.measure_loan_at_cutover(...)` function and stores an immutable row containing the cutover date, calculation mode, loan-policy version, measurement-policy version, release/maturity dates, principal/operational source values, solved EIR, contractual/actual cash references, effective-interest result, loan component, accrued-interest component, gross carrying amount, and measurement status/note.

Measured rows are constrained so:

`loan_component + accrued_interest_component = gross_carrying_amount`

and the solved daily EIR must be positive.

A separate immutable batch record stores the expected active-loan count and captured count. The two counts must be equal. Migration 0039 itself inserts neither a batch nor a snapshot row; capture happens only on a future protected preparation.

## Ledger-anchor reconciliation

`accounting.opening_balance_loan_snapshot_reconciliation` compares the protected loan snapshots with the prepared opening journal:

- fixed-daily measured loan components -> account 1100 `Loans Receivable - Regular`;
- measured 7x7 loan components -> account 1110 `Loans Receivable - 7x7`;
- measured accrued EIR components -> account 1120 `Accrued Interest Receivable`.

The snapshot batch becomes `ledger_anchor_ready` only when:

- expected, captured, and actual snapshot counts agree;
- every snapshot is `measured`;
- Regular snapshot total equals the prepared journal's 1100 balance;
- 7x7 snapshot total equals the prepared journal's 1110 balance; and
- accrued EIR snapshot total equals the prepared journal's 1120 balance.

A mismatch does **not** alter the journal or snapshot. It simply keeps downstream accounting automation blocked.

## Event-date EIR allocator behavior

Before opening-journal preparation, the allocator may still show its existing non-posting current-measurement preview.

After preparation:

- it never calls mutable Stage 5D remeasurement as the ledger anchor;
- it requires the immutable per-loan snapshot and snapshot-batch reconciliation;
- missing snapshot/batch -> `protected_cutover_snapshot_required`;
- unsupported snapshot policy -> `protected_cutover_snapshot_policy_mismatch`;
- unreconciled batch -> `protected_cutover_snapshot_not_reconciled`;
- only a reconciled protected snapshot may feed the read-only Regular event-date EIR cash allocator.

Even with a reconciled snapshot, the allocator remains `posting_eligible=false`. EIR accrual journals and source collection journals are separate later stages.

## Immutability and no backfill

Snapshot batch/row tables reject update/delete and reject direct inserts outside the protected preparation context. Existing preparations from before migration 0039 are deliberately not inferred or backfilled; they remain blocked until explicitly handled by a future controlled process.

## Deployment safety

The guarded main-only installer verifies that schema installation itself changes none of the following:

- loans or loan statuses;
- collection transactions;
- journal entries, lines, events, statuses, or numbers;
- opening workbook, preparation, or posting state;
- historical ECL labels;
- DPD/Default/ECL readiness state.

On first installation it additionally requires:

- `snapshot_batches = 0`
- `snapshot_rows = 0`

Automatic source posting remains disabled.

## Explicitly excluded

This stage does not backfill snapshots, create or post EIR accruals, create or post collection journals, approve 7x7 prepayment/modification accounting, extrapolate interest beyond maturity, change Default/ECL/1190, create tax entries, or alter lending balances.
