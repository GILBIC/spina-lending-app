# SPINA loan accounting policy baseline

Status: **business-rule baseline for Financial Accounting design**. This document does not activate accounting posting and does not replace external CPA/auditor review of PFRS, tax, lending-contract, or regulatory treatment.

## Separation of systems

SPINA lending operations remain the source of truth for borrower contracts, collection balances, receipts, remittances, PASS/ADV behavior, corrections, and voids.

The future Financial Accounting journal will be the source of truth for general-ledger balances and financial statements. Operational balances must not be overwritten merely to force an accounting result, and accounting entries must retain a source link back to the underlying SPINA transaction.

## Regular loan

Business baseline:

- Contract term: 120 days.
- Fixed contractual interest: 20% of principal for the agreed Regular-loan contract.
- Contractual daily collection remains an operational lending value.
- The full fixed interest is not recognized as accounting income on the release date.
- The official accounting layer is intended to recognize interest using an effective-interest schedule for an amortized-cost loan.
- Cash payment and accounting interest recognition are separate events: cash collection reduces the loan carrying amount while earned interest is recognized according to the accounting schedule.
- Missed cash payments do not by themselves reverse interest already earned. Credit deterioration is handled separately through impairment / expected-credit-loss accounting.
- The original contractual interest schedule does not automatically continue forever after the contractual term.

### Regular renewal

A renewal must preserve the old loan and create a separate new loan. The old loan is settled first; the new loan starts a new accounting schedule.

Where the signed contract makes the remaining contractual balance payable on renewal, the operational renewal may deduct that old contractual payoff from the new loan proceeds. The accounting layer compares the consideration used to settle the old loan with the old loan's carrying amount and records the resulting derecognition effect in the old loan. The new loan's fixed interest is not recognized again on day one.

Illustrative agreed business example:

- Old principal: PHP 5,000.
- Fixed interest: PHP 1,000 (20%).
- Total contractual payments: PHP 6,000.
- Client has already paid PHP 3,000.
- Remaining contractual payoff: PHP 3,000.
- New renewal principal: PHP 5,000.
- Cash released to client: PHP 2,000, assuming the contract requires the full remaining PHP 3,000 payoff and no rebate applies.

The Financial Accounting posting engine must not be enabled until the exact signed-contract treatment of early settlement / renewal and any required rebate is confirmed.

## EMER / 7x7 loan

Business baseline:

- Current configured term: 120 days.
- Daily interest: PHP 7 per PHP 1,000 of **original principal**.
- The daily interest amount stays based on original principal even when principal has partially declined.
- Daily interest stops when principal reaches zero, subject to the written contract and applicable rules.
- Interest and principal are separate components.
- A payment first settles accrued unpaid contractual interest. Any excess reduces principal.

Example for a PHP 3,000 7x7 loan:

- Daily contractual interest = PHP 21.
- If the client pays PHP 21, principal remains PHP 3,000.
- If the client pays PHP 50, PHP 21 settles contractual interest and PHP 29 reduces principal.
- After that PHP 50 payment, principal is PHP 2,971 but the next contractual daily interest remains PHP 21 under the agreed business rule.

Accounting baseline:

- On release: principal is the operational loan receivable source and cash is released.
- The operational subledger tracks contractual daily interest earned/accrued, interest collected, principal collected, and principal outstanding separately.
- Collection of contractual interest already recognized in the accounting journal must not recognize the same income twice.
- Before official PFRS journal posting is enabled, SPINA must derive and validate the effective-interest schedule from the actual 7x7 contractual cash flows. The operational PHP 21-per-day example must not automatically be assumed to equal official PFRS interest income if the EIR calculation produces a different allocation.
- If collectibility deteriorates, impairment / expected credit loss is assessed separately from the contractual borrower balance.

### 7x7 renewal

The agreed operational formula is:

**Cash release = new principal - old principal outstanding - accrued unpaid contractual interest**

Already-paid principal and already-paid interest are not deducted again.

Example:

- New principal: PHP 3,000.
- Old principal outstanding: PHP 1,260.
- Accrued unpaid contractual interest: PHP 0.
- Cash released: PHP 1,740.

If accrued unpaid contractual interest is PHP 84, cash released becomes PHP 1,656.

The old 7x7 loan is closed as settled by renewal and preserved for audit. The new loan starts separately with a new contractual daily-interest schedule based on its own original principal. The official accounting treatment of the new loan remains subject to its validated effective-interest schedule.

## Default, impairment, and write-off

Default does not erase prior accounting history. Principal and earned unpaid amounts remain receivables until collection, settlement, or write-off. The future accounting layer must separately track expected credit loss / impairment and must not treat a mere operational default flag as an automatic tax bad-debt deduction.

No automatic journal, EIR posting engine, ECL model, tax deduction, write-off, or period-close logic is activated by the first Financial Accounting control-center release.
