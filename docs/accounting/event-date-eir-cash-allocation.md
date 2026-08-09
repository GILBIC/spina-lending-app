# Event-date EIR cash allocation

Status: **read-only accounting reference**. This stage creates no journal draft, posts no General Ledger entry, changes no lending record, and does not enable automatic source posting.

## Purpose

PR #280 proved that PAYMENT and ADV are authoritative operational cash events but cannot safely be credited entirely to Loans Receivable. Stage 5D / 5D.1 carries a measured loan as two accounting components:

- Regular loan component -> account 1100;
- 7x7 loan component -> account 1110;
- accrued effective interest -> account 1120.

Cash must therefore be split using the EIR carrying state rather than contractual payment labels.

This stage implements that split for **measured Regular `fixed_daily` loans only**.

## Regular roll-forward rule

Before a protected opening-balance journal has been prepared, the endpoint may provide a non-posting review reference from the current reconciled Stage 5D.1 cutover measurement:

1. Use the reconciled cutover gross carrying amount, accrued EIR component, loan component, and solved daily EIR.
2. For every elapsed calendar day after cutover, accrue effective interest on the current gross carrying amount before that day's cash is applied. This matches the Stage 5D event ordering.
3. PAYMENT and ADV use their actual `collection_date` as the accounting cash date. ADV covered dates do not move accounting cash timing.
4. Multiple cash events on the same date receive one daily EIR accrual, then are applied in deterministic `(accepted_at, transaction_id)` order.
5. At each cash-event boundary, directly round accrued EIR to cents and give the cent residual to the loan component so `gross = accrued EIR + loan component` exactly, matching the Stage 5D.1 reconciliation convention.
6. Recognized EIR totals are the sum of those cent-boundary accruals. Sub-cent amounts discarded when a boundary is reconciled cannot reappear later in the reported total.
7. Apply cash to accrued EIR first. Any remaining cash reduces the Regular loan component.

The read-only allocation therefore identifies a future collection journal split such as:

- debit Cash - Collector Custody for total accepted cash;
- credit Accrued Interest Receivable (1120) for the portion clearing already-accrued EIR;
- credit Loans Receivable - Regular (1100) for the remaining portion reducing the loan component.

**These lines are not created or posted in this stage.** A later protected stage must first create/post the corresponding EIR accrual (Dr 1120 / Cr 4000) and prove fiscal-period ordering, source concurrency, reversal handling, and idempotency before collection journals can become posting-eligible.

## Protected cutover anchor

The existing Stage 5D function is a measurement function: it recomputes from lending source rows. That is suitable for a pre-preparation review reference, but it is not a safe substitute for the immutable loan-level state that produced a protected opening journal.

Therefore this stage follows a fail-closed rule:

- before opening-journal preparation, the result is explicitly a read-only current-measurement reference;
- once `accounting.opening_balance_journal_preparations` contains the current workbook, the endpoint returns `protected_cutover_snapshot_required` and **does not call the mutable remeasurement path**;
- posting the opening journal does not relax that block;
- a later protected stage must persist and load an immutable per-loan cutover EIR snapshot before post-cutover allocations can be ledger-anchored.

This prevents a later correction or void of pre-cutover lending data from silently changing the opening loan state while the already-prepared or posted opening journal remains unchanged.

## Safety blockers

The allocator refuses to guess when any of these conditions apply:

- cutover measurement is missing, incomplete, or not `measured`;
- Stage 5D.1 components do not reconcile exactly to gross carrying amount;
- the protected opening journal has already been prepared but no immutable per-loan cutover snapshot exists;
- source cash is on or before the date-only cutover boundary;
- the loan is 7x7;
- the calculation mode is unsupported;
- cash exceeds the measured EIR carrying amount;
- cutover is after contractual maturity;
- a cash event is after contractual maturity;
- same-day cash exists on the date-only cutover boundary in the repository view;
- post-cutover source history exceeds 5,000 rows, in which case calculation blocks instead of truncating history.

## 7x7 remains blocked

7x7 contractual daily interest and PFRS 9 EIR are not assumed to be the same. A 7x7 cash payment can also alter the principal/prepayment profile used by the EIR cash-flow model. Until the modification/prepayment accounting policy is validated, the allocator returns `seven_by_seven_policy_review` and produces no split.

## Post-maturity rule

The original Regular EIR schedule is not extrapolated indefinitely beyond contractual maturity. Cash after the due date returns `post_maturity_review_required`. Credit deterioration, Stage 3 interest basis, ECL, restructuring, and write-off remain separate accounting decisions.

## API

Management can read one loan's reference through:

`GET /api/v1/management/financial-accounting/eir-cash-allocation/{loan_id}`

The mobile alias is read-only as well. Both require `accounting.view` and the Management role.

The response preserves decimal values as strings and explicitly reports:

- cutover and maturity dates;
- whether the protected opening journal has been prepared;
- whether the protected opening balance has actually posted;
- source-history completeness;
- opening and closing EIR components;
- EIR accrued between source events;
- cash allocated to accrued EIR versus the Regular loan component;
- `posting_eligible=false`;
- `automatic_source_posting_enabled=false`.

## Explicitly excluded

This stage does not persist the protected per-loan cutover snapshot, create EIR accrual journals, create collection journals, allocate 7x7 cash, extrapolate post-maturity interest, perform renewal/restructure accounting, create remittance-transfer entries, post Default/ECL/1190 entries, create tax entries, or enable automatic posting.