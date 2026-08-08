# Stage 5D — Accounting Loan Measurement Engine

Stage 5D derives read-only accounting measurement references for the protected opening-balance workbook. It does not post to the General Ledger and does not verify workbook lines.

## Regular loans

- Solve the daily effective interest rate from the contractual level-payment schedule: initial principal equals the present value of the 120 contractual daily installments.
- Accrue EIR from the release date to the selected cutover date.
- Apply actual non-voided cash on the recorded collection date. Advance coverage dates do not replace the accounting cash date.
- Split the measured carrying amount into an accounting loan component and an accrued-interest component for cutover reference.
- Operational remaining balance stays a source reference and is not treated as the PFRS amortized-cost carrying amount.

## 7x7 loans

- Solve the daily EIR from the validated base cash-flow schedule: fixed daily contractual interest based on original principal plus principal at maturity.
- For the current no-cash test loans, the solved daily EIR is validated from the contractual cash flows rather than assumed from the contractual charge.
- Contractual unpaid interest is shown separately from the EIR accrued-interest component so the accounting time-value effect is visible.
- A 7x7 loan with pre-cutover cash activity is marked `7x7_cash_flow_review_required`; principal-versus-interest allocation and any principal-prepayment modification must be reviewed before its EIR carrying amount is used.
- 7x7 mobile collection remains disabled.

## Cutover references

When every active loan is measured, Stage 5D exposes dynamic reference amounts for:

- `1100 Loans Receivable - Regular`: Regular accounting loan component.
- `1110 Loans Receivable - 7x7`: 7x7 accounting loan component.
- `1120 Accrued Interest Receivable`: accrued EIR component across measured loans.

These are references only. Stage 5D never copies them into proposed workbook debit/credit fields automatically.

## Explicitly excluded

- Expected credit loss measurement and posting.
- Tax accounting and book-to-tax reconciliation.
- Opening-journal creation or posting.
- Automatic loan/collection journal posting.
- Final financial statements.

The measurement policy version is `eir_cutover_v1`. A workbook can still move to review ready only through the Stage 5C verification and balancing controls.