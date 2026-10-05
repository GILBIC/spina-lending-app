# Lending accounting design decisions

The user delegated accounting design and chart choices on 5 October 2026. These are implementation decisions, not invented company balances or an assertion that a particular statutory filing framework applies to an entity whose size/registration details have not been supplied.

## Design basis

Use accrual double-entry accounting, PHP exact cents for operational settlements, the existing protected effective-interest and expected-credit-loss measurement engines, and source-linked liability schedules. Target a reporting package capable of the existing full financial-instrument measurement model, retaining presentation/classification versions rather than silently switching to a simplified model. Do not reset historical EIR/ECL calculations or flatten contractual and carrying balances into one amount.

The IFRS Foundation describes the connection between effective-interest amortised-cost measurement and expected-credit-loss accounting in its [March 2018 interpretation](https://www.ifrs.org/news-and-events/updates/ifric/2018/ifric-update-march-2018/). [IFRS 18](https://www.ifrs.org/issued-standards/list-of-standards/ifrs-18-presentation-and-disclosure-in-financial-statements/) replaces IAS1 for annual periods beginning on or after 1 January 2027. Presentation policies therefore need effective dates; neither a2026 pack nor a future pack should automatically claim statutory compliance because totals balance.

## Control chart

Preserve existing account codes and historical posted classification. New definitions must be collision-checked, never overwritten to make a migration succeed. Wallet-to-GL mapping is explicit and versioned; cash wallet balances must reconcile individually even when aggregated into an existing cash control account.

| Account | Control purpose | Normal balance |
|---|---|---|
|1010/1020/1030 (existing)|Office cash / Collector custody / bank and wallet cash|Debit|
|1040 (proposed)|Transfer funds in transit|Debit|
|1050 (proposed)|Loan payout funds in transit|Debit|
|1060 (proposed)|Collector return funds in transit|Debit|
|1100/1110/1120/1190 (existing)|Regular /7x7 loan carrying balances, accrued interest and loss allowance|Existing protected policy|
|2000/2100 (existing)|Trade and other payables / tax payables|Credit|
|2200|Unapplied borrower funds|Credit|
|2210 (proposed)|Unidentified receipts pending attribution|Credit|
|2220 (proposed)|Amounts payable to Collectors|Credit|
|2230 (proposed)|Borrower refunds payable|Credit|
|2300 (proposed)|External borrowings|Credit|
|2310 (proposed)|Repayable owner or related-party funding|Credit|
|2320 (proposed)|Accrued funding interest|Credit|
|2330/2340 (proposed)|Payroll and statutory contribution liabilities|Credit|
|3000/3100 (existing)|Capital / retained earnings|Credit|
|5240 (existing)|Separately evidenced bank/wallet transaction fees|Debit|

“Proposed” means a reserved design coordinate, not an implemented migration or actual balance. Implement each account only with its protected source adapter and reconciliation tests. If existing private configuration uses a proposed code differently, reject and require an explicit noncolliding mapping; do not rewrite it.

## Journal rules

- Verified borrower receipt: cash debit, unapplied-funds credit. Existing credit events have zero fee by database constraint; do not invent a receipt fee.
- Loan application: unapplied-funds debit, exact protected lending/EIR credits. No second cash debit.
- Actual loan-payout debit: transit debit, cash credit; separate fee expense. Completion clears transit against the exact protected loan origination/renewal entry.
- Collector excess: cash receipt once, unidentified-liability credit. Recognition reclassifies that liability to Collector payable. Reservation is availability metadata, not another liability.
- Funding with a repayment obligation is borrowing, including owner funding. Capital requires a distinct contribution source. Interest/fee recognition follows its retained policy and contractual evidence.
- A genuine refund/return moves money and reduces the identified obligation once. Observation corrections, accounting reversals and actual returned money are different source families.
- Transfers between owned cash accounts are internal movements; separately dated legs reconcile through transit. Do not report them as income or expense.

Closing tests completeness, not whether liabilities equal zero. An unpaid but exactly reconciled liability is valid. Late cash evidence must remain recordable and visible against closed history; it cannot silently rewrite the closed journal or disappear because the accounting period is closed.

Actual company identity, cutover balances, wallets, financing contracts, tax registration/rates and retention evidence remain facts supplied to the system. No software migration invents them. This does not postpone implementation of the framework, chart, adapters or reports.
