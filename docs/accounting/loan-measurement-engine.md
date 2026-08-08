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

## Stage 5D.1 — cent reconciliation

Live validation on the 2026-08-08 cutover exposed a presentation-level rounding difference: the displayed `1100 + 1110 + 1120` components totaled ₱29,343.13 while the independently rounded gross carrying amount was ₱29,343.11. The underlying EIR equation remained correct; the difference came from rounding the loan and accrued-interest components independently before portfolio aggregation.

Stage 5D.1 keeps the existing EIR calculation and cash timing unchanged, preserves the independently rounded accrued-interest component and gross carrying amount, and assigns any cent rounding residual deterministically to the loan component. Therefore every measured loan must satisfy, to the cent:

`loan component + accrued-interest component = gross carrying amount`

The current cutover's reconciliation target is therefore:

- `1100 Loans Receivable - Regular`: ₱19,723.75
- `1110 Loans Receivable - 7x7`: ₱9,000.00
- `1120 Accrued Interest Receivable`: ₱619.36
- Gross carrying amount: ₱29,343.11
- Component variance: ₱0.00

The read-only `accounting.loan_measurement_reconciliation` view reports both per-loan and portfolio-level reconciliation status. This change does not modify workbook proposed amounts, ECL, opening-journal controls, or automatic source posting.

## Explicitly excluded

- Expected credit loss measurement and posting.
- Tax accounting and book-to-tax reconciliation.
- Opening-journal creation or posting.
- Automatic loan/collection journal posting.
- Final financial statements.

The measurement policy version remains `eir_cutover_v1` because Stage 5D.1 changes only cent presentation/reconciliation, not the EIR method or contractual cash-flow policy. A workbook can still move to review ready only through the Stage 5C verification and balancing controls.
