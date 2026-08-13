# Protected ECL Allowance Posting — SPINA V1 A4

## Purpose

A4 turns an exact, currently-authoritative A3 quantitative ECL measurement into an accounting allowance only after explicit Management confirmation. It does not automate ECL posting and it does not implement later remeasurement, cure, write-off or recovery accounting.

The protected initial allowance entry is:

- **Debit 5000 — Credit Loss Expense**
- **Credit 1190 — Allowance for Expected Credit Loss**

The amount must equal the exact authoritative `ecl_amount` of the selected immutable quantitative ECL measurement.

## Initial allowance boundary

A4 is deliberately limited to an initial allowance where the protected per-loan balance of account 1190 is exactly **0.00**.

If a loan already has a non-zero protected allowance balance, a new or changed ECL measurement is not posted through this initial path. The queue must show that A5 remeasurement accounting is required. This prevents A4 from silently overwriting, doubling or reversing an existing allowance.

A zero authoritative ECL amount requires no allowance journal.

## Management confirmation sequence

1. A3 must show the loan as `measured_read_only` with a non-null current authoritative ECL amount.
2. The A4 queue exposes the exact measurement id/version/digest, measurement/posting date, open fiscal period, account 5000 id, account 1190 id, amount and current prior allowance balance.
3. Management confirms those exact coordinates and creates an immutable protected draft.
4. The draft contains exactly two loan/client-attributed lines: debit 5000 and credit 1190 for the same amount.
5. Management separately confirms the immutable preparation identity and posts it through the protected A4 posting function.
6. The posting transaction revalidates the measurement, period, accounts, amount, journal identity and prior allowance state before calling the common journal posting primitive.
7. Immutable posting and line audit snapshots are recorded in the same transaction.

No source event posts itself automatically. `automatic_source_posting=false` remains mandatory.

## Current measurement requirement

Preparation and posting both re-read the current A3 measurement queue. The selected measurement must still be the exact current authoritative measurement, including its calculation digest, measurement version, current credit-risk label/schedule state and current forward-looking evidence.

If A3 has become `new_measurement_required`, `measurement_required` or `input_blocked`, A4 must refuse the posting even when an older immutable measurement row still exists.

## Fiscal period and account controls

The posting date is the authoritative A3 measurement date. It must belong to the exact confirmed fiscal period and that period must still be open inside the posting transaction.

The protected account identities are revalidated inside the transaction:

- `5000 / credit_loss_expense` — active posting expense account with normal debit balance;
- `1190 / allowance_expected_credit_loss` — active posting asset contra-account with normal credit balance.

A changed, inactive, non-posting or wrong account blocks the transaction.

## General Journal and reversal boundary

Account 1190 becomes a protected source-controlled account in A4. Generic/manual journal lines cannot insert, edit or delete a 1190 line. Protected A4 drafts cannot be edited, deleted or posted through the generic General Journal posting action.

A posted A4 allowance journal also cannot be manually reversed through the General Journal. Controlled allowance remeasurement/decrease/reversal belongs to A5.

## Idempotency and audit

The preparation and posting records are immutable. Exact retry returns the existing immutable preparation/posting only when the stored source identity, journal, lines, tokens, accounts, amount and resulting allowance balance still agree.

A retry with a different confirmation token or changed coordinate is rejected rather than treated as the same operation.

The journal is posted and the immutable A4 posting audit is inserted in one PostgreSQL transaction. A forced posting-audit failure must therefore roll the journal back to its prior draft state and leave account 1190 unchanged.

## Safety flags

A4 may expose `account_1190_posting_enabled=true` only for this protected explicit Management path.

It does **not** enable automatic source posting, write-off accounting, ECL remeasurement or any invented quantitative assumption. `automatic_source_posting=false` remains the V1 rule.