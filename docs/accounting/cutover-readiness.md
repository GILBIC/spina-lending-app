# SPINA Accounting Cutover Readiness

Status: **Stage 5A pre-cutover readiness only**.

This stage does not post opening balances and does not enable automatic lending journals. It normalizes contract metadata that is already fixed by the approved product rules, exposes a database readiness view, and hardens reversal controls before any accounting cutover is attempted.

Stage 5A is database/backend accounting preparation only and does not require an APK change. The existing mobile accounting screens remain valid while the source data is prepared for the later cutover worksheet and automated-posting stages.

## Regular

- Product rule: fixed 20% contractual interest over the configured 120-day term.
- Existing Regular loan rows with a null `interest_rate` are normalized to 20% only when the loan type is `fixed_daily` and named `Regular`.
- Every normalization is copied first into the immutable `accounting.loan_contract_metadata_audit` table.
- A Regular source loan is considered source-ready only when its interest rate is valid, its daily amount is positive, its due date matches the configured term, and `daily_amount × term_days` agrees with `principal + fixed contract interest`.
- Official interest income will still use the PFRS effective-interest method. The 20% contract rate is not automatically treated as the accounting effective interest rate.

## 7x7 / EMER

The agreed operational metadata is preserved on the loan type:

- daily interest is separate from principal;
- daily interest is based on original principal until principal reaches zero;
- mobile 7x7 collection remains disabled;
- PFRS effective-interest posting remains disabled until the contractual principal repayment/maturity cash-flow schedule is explicitly validated.

A 7x7 source loan can pass its operational source checks while still remaining in `contract_schedule_validation_required` status for financial-accounting cutover.

## Opening balances

Opening balances remain **not configured**. SPINA must not create a loan-only opening journal because a valid opening balance sheet also requires the actual cash/bank, liabilities, capital, retained earnings, and other balances at the cutover date.

`accounting.cutover_readiness_summary` therefore keeps both:

- `opening_balances_configured = false`
- `automatic_source_posting_enabled = false`

until a later controlled stage.

## Reversal hardening

A posted journal can have one reversal. A reversal journal itself cannot be reversed again. Further corrections must be recorded as a new documented journal entry so the original journal and its reversal remain intact in the permanent audit trail.
