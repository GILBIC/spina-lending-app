# SPINA V1 A6.4 disposable accounting-cycle proof

## Purpose

Master #296 A6.4 is a release-validation requirement, not a new bookkeeping engine. The current protected accounting capabilities already exist through migration `0092`; A6.4 composes those capabilities on disposable books and proves that the resulting ledger and statements reconcile end to end.

No A6.4 production migration, synthetic opening-balance journal, automatic source posting, or second General Journal is introduced by this slice.

## Disposable cycle

The proof starts from a fresh loopback-only PostgreSQL database replayed through `0092` and uses rollback-isolated synthetic evidence. One Management-controlled period composes:

1. evidence-backed initial capital into Office Cash;
2. a protected new Regular loan disbursement;
3. an already-protected 7x7 collection source event with explicit Management journal posting;
4. Collector Custody remittance into Office Cash without income recognition;
5. independent evidence-backed lending percentage-tax recognition and exact Tax Payables settlement; and
6. formal review/period close with the exact period Profit or Loss transferred to `3100 Retained Earnings`.

The synthetic values exist only inside the disposable verifier and are never legal-book or production balances.

## Required reconciliation

Before close, the proof calculates the Trial Balance and Profit or Loss directly from posted General Journal lines. Total debit balances must equal total credit balances, and the formal close preparation's `net_income` must exactly equal that independently calculated Profit or Loss.

After close:

- Trial Balance remains balanced;
- all income and expense temporary balances are exactly zero;
- `3100 Retained Earnings` contains the exact period profit/loss transfer;
- Financial Position satisfies **Assets = Liabilities + Equity** from the same posted ledger;
- Collector Custody has no unexplained residual after the retained remittance transfer;
- `2100 Tax Payables` has no residual after the retained tax settlement;
- the fiscal period is protected `closed`.

## Integrity checks

The proof also fails if it finds:

- more than one posted journal for the same `source_event_key`;
- any unresolved draft journal at final reconciliation;
- any synthetic `opening_balance` journal;
- a journal event orphaned from its General Journal entry;
- a missing protected posting/audit row for the capital, release, 7x7 collection, remittance, tax liability, tax settlement, or formal close used by the cycle; or
- any composed path reporting `automatic_source_posting=true`.

Legitimate ending asset balances such as remaining loan receivables and cash are not treated as residual errors. A residual means an amount that should have cleared within the composed cycle, such as Collector Custody or Tax Payables, or a source/audit relationship that should reconcile exactly but does not.

## Gate rule

A6.4 stays unchecked until the exact PR head passes both the dedicated disposable accounting-cycle workflow and unified SPINA validation, the PR is merged, and the merged-main dedicated/unified proof is green. Only then may Master #296 A6.4 be marked complete and Section B begin.
