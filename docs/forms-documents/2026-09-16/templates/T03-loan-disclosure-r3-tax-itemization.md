# T03 — Loan Disclosure Statement — R3 tax-itemization candidate

Status: **text-only controlled draft; not production-cleared**. This editing revision is not an issued borrower document or a formatted DOCX/PDF replacement.

Source review mirror: [2026-09-12 T03-loan-disclosure-r2.md](../../2026-09-12/templates/T03-loan-disclosure-r2.md). Original Git blob: `2c96c6be6759ae12b8a68843a7f083d9bbef6bef`.

Original print-layout source: `Templates/SPINA_Loan_Disclosure_R2_Black_White_Draft.docx`. Source DOCX SHA-256: `6799c8d555ea8a677723144a049c665f14580240bcee8d4917bc93753d6bb585`. Both the original review mirror and original DOCX remain unchanged.

## Scope and pending integration

This candidate carries the approved DST-upfront / GRT-in-repayments treatment from PR #420 [approval #5682053744](https://github.com/GILBIC/spina-lending-app/pull/420#issuecomment-5682053744). Only the relevant amount/itemization sections and editing-revision metadata change. Existing non-tax prose, execution controls and any embedded Annex A remain preserved. The final packet must still use one complete approved Annex A; this revision does not replace the accepted Regular Remaining Total Payable renderer with the older embedded summary.

**Source binding is not implemented.** The planned document context must retain `loan_version_reference`, `tax_rule_snapshot_reference` and `tax_calculation_reference` from the same authorized approved loan/disclosure snapshot. The helper also checks `tax_loan_version_reference` against `loan_version_reference`; matching supplied references alone do not authenticate ownership or provenance. Do not invent references to make a draft appear ready.

Planned shared token mapping to the existing `loan_document_tax_breakdown` inputs/output, not a new calculator:
- `{DST Upfront Amount}` uses supplied `dst_upfront`; `{GRT Recovery in Repayments}` uses supplied `grt_in_repayments`. Every repeat of a tax token denotes that same amount.
- `{Renewal Offset Amount}` uses supplied `renewal_offset`. The contractual-interest tokens use `contractual_interest`, excluding GRT recovery; `{Other Scheduled Charges}` uses `other_scheduled_charges`.
- Gross-principal tokens use `principal`. Document-specific deduction-total, net-proceeds and original-scheduled-total tokens use the reconciled `total_upfront_deductions`, `net_proceeds` and `total_scheduled_payable`, respectively. Different capitalization in preserved tokens is not permission to bind different values.
- Other upfront and scheduled charges require independently itemized authorized sources whose totals match the supplied aggregates. They must not hide DST, GRT or another separately displayed item. Classification displays reuse the same charge identities rather than create new collections.

Amount Financed, charge-classification totals, rates and EIR remain separate counsel/accounting-approved disclosure inputs; Amount Financed is not an alias for net cash. This candidate does not select rates, calculate tax/gross-up, allocate installments, decide early-settlement treatment or post accounting. A tax amount is explicitly zero only when the approved source says so; unresolved inputs are not zero. Existing optional fee rows do not authorize a new fee.

Formatted DOCX/PDF integration, exact Client/CIF/loan/approval/schedule/tax binding, signature/storage/retrieval and professional review remain pending. Passing text tests is not legal clearance or permission to issue or charge a real borrower. The following body retains draft instructions until a later controlled issuance step.

```text
LOAN DISCLOSURE STATEMENT

SYSTEM-ALIGNED DRAFT FOR COUNSEL / ACCOUNTING REVIEW

Working template: SPINA fills all braced fields from the same locked Management-approved loan. No borrower values, charges or signatures are invented. Do not sign or issue this draft while placeholders or required reviews remain unresolved.

Loan Account No. | {Loan Account No.}
Disclosure Date / Time | {Recorded Disclosure Date/Time and Time Zone}

I. BORROWER INFORMATION

Borrower | {Borrower Full Name}
Address | {Borrower Address}
Contact Number | {Registered Contact Number}
Email Address | {Registered Email or Not Provided}

II. LOAN INFORMATION

Type of Loan | {Exact Approved Loan Type}
Purpose | {Approved Loan Purpose}
Loan Date | {Approved Loan Date}
Contractual / Original Maturity Date | {Contractual Maturity Date}
Contractual Loan Term | {Exact Approved Term}
Number of Installments | {Approved Installment Count}
First Payment Date | {Approved First Payment Date}
Payment Frequency | {Exact Approved Payment Frequency}

III. LOAN AMOUNT

A. Principal / Gross Loan and Amount Financed

Principal / Gross Loan Amount | PHP {Approved Gross Principal}
Amount Financed | PHP {Authoritative Amount Financed}

The separate Gross Principal, Amount Financed and Net Amount to Be Released fields must be reconciled by the counsel/accounting-approved disclosure calculation. Staff must not independently calculate or override these amounts.

III. LOAN AMOUNT (continued)

B. Deductions from Loan Proceeds

Deduction | Amount
Processing / Service Fee | {Exact Amount or None / PHP 0.00}
Documentary Stamp Tax (DST) - upfront | PHP {DST Upfront Amount}
Renewal Offset (not a tax) | PHP {Renewal Offset Amount}
Notarial Fee | {Exact Amount or None / PHP 0.00}
Other Lawful Upfront Deduction (excluding DST, renewal offset and separately listed fees) - {Charge Name} | {Exact Amount or None / PHP 0.00}
TOTAL DEDUCTIONS | PHP {Total Approved Deductions}

Applicable DST borne by the Borrower is separately itemized upfront. A renewal offset is the separately approved settlement amount applied to the prior loan, not a tax or an additional fee. Each other deduction is counted once and must identify its approved source; a generic charge row must not repeat a separately listed amount.

C. Net Proceeds

Gross Loan Amount | PHP {Approved Gross Principal}
Less: Total Deductions | PHP {Total Approved Deductions}
NET AMOUNT TO BE RELEASED | PHP {Authorized Net Proceeds}

Only charges properly disclosed and legally chargeable to the Borrower shall be deducted from the loan proceeds. The net amount stated here is authorized for release; this Disclosure is not proof that the Borrower received cash.

IV. INTEREST AND FINANCE CHARGES

Contractual Interest Rate / Period | {Exact Approved Rate and Stated Period}
Fixed Daily Interest - 7x7 only | PHP {Fixed Daily Interest} / {Not Applicable for Regular}
Method of Interest Computation | {Exact Approved Computation Method}
Total Contractual Interest (excluding GRT recovery) | PHP {Total Contractual Interest}

For a 7x7 Cash Loan, 60 calendar days is a default target only. The agreed daily payment determines the complete contractual schedule before approval and signing. Contractual Maturity is the last installment date in that exact signed schedule, not automatically Day 60. Contractual interest stops at Contractual Maturity, or earlier payoff as applicable; any permitted post-maturity penalty is separate from contractual interest. The fixed daily amount and total contractual interest must match the same signed Schedule of Payments.

Internal pricing control: insert only the exact approved and validated loan-specific interest amount, rate and period from the authoritative schedule/disclosure calculation. A default product target is not a universal rate or an EIR. Pricing and counsel/accounting checks must pass before contract lock.

Finance Charge | Amount
Interest (excluding GRT recovery) | PHP {Total Contractual Interest}
Passed-on Gross Receipts Tax (GRT) - within agreed repayments | PHP {GRT Recovery in Repayments}
Processing / Service Fee | {Exact Finance Charge or None / PHP 0.00}
Other Finance Charge (excluding interest, GRT recovery and separately listed fees) - {Charge Name} | {Exact Amount or None / PHP 0.00}
TOTAL FINANCE CHARGES | PHP {Total Finance Charges}

Passed-on GRT is included within the agreed repayments, not deducted upfront and not added on top of the agreed installment. Repeated disclosure of the same DST or GRT amount does not create another charge.

Finance Charge / Amount Financed | {Finance Charge Percentage} %
Simple Annual Rate | {Required Calculated Rate} % / {Not Applicable, if lawful}
Effective Interest Rate (EIR) | {Required Calculated EIR} % per {Stated Period}

V. NON-FINANCE CHARGES

Non-Finance Charge | Amount
Documentary Stamp Tax (DST) - same upfront amount, not an additional charge | PHP {DST Upfront Amount}
Notarial Fee | {Exact Amount or None / PHP 0.00}
Insurance | {Exact Amount or None / PHP 0.00}
Other - {Charge Name} | {Exact Amount or None / PHP 0.00}
TOTAL NON-FINANCE CHARGES | PHP {Total Non-Finance Charges}

Counsel/accounting must confirm each charge classification for the applicable loan. A charge appearing both in the deductions breakdown and in a charge classification is the same charge, not a second charge. SPINA must reconcile prepaid and scheduled amounts without double counting.

VI. TOTAL AMOUNT PAYABLE

Principal / Gross Loan Amount | PHP {Approved Gross Principal}
Total Contractual Interest (excluding GRT recovery) | PHP {Total Contractual Interest}
Passed-on Gross Receipts Tax (GRT) - within agreed repayments | PHP {GRT Recovery in Repayments}
Other Scheduled Charges (excluding interest and GRT recovery) | PHP {Other Scheduled Charges}
TOTAL PAYABLE UNDER ORIGINAL SCHEDULE | PHP {Authoritative Scheduled Total}

This repayment breakdown counts each scheduled component once. Upfront deductions and the full finance/non-finance classification totals shown above are not added again. Amount Financed and EIR retain their separate approved disclosure meanings; they are not calculated by this table or substituted for net cash. The scheduled total must reconcile with the same approved Agreement and complete Schedule of Payments without silently changing the agreed installment or term.

The total shown is based on the original contractual Schedule of Payments and the same approved disclosure calculation. The current operational schedule may later extend or contract to reflect actual posted payments, missed payments, prepayments or other permitted transactions. It does not by itself amend the signed principal, interest method/basis, agreed installment amount, charges or Contractual Maturity. The Current Operational Finish remains separate from Contractual Maturity.

VII. PAYMENT TERMS

Installment Amount | PHP {Agreed Installment Amount}
Number of Installments | {Approved Installment Count}
First Payment Due | {Approved First Payment Date}
Contractual / Original Maturity Date | {Contractual Maturity Date}

The complete contractual repayment schedule, including all continuation pages, is attached as Annex A - Schedule of Payments. It must be generated, locked and made available for borrower review and signing before cash release, using the same approved loan/packet version.

Payment Allocation

Regular: oldest Past Due scheduled obligations first; then Due Today; then true excess only through the authorized Advance or Principal Reduction path.

7x7: oldest Past Due Interest; Today's Interest; oldest Past Due Principal; Today's Principal; then Advance.

For 7x7, Extra Principal, when allowed, is separate from Advance and may be applied only after all current and past-due interest is fully satisfied. Any unapplied excess that cannot be applied to a surviving scheduled obligation is handled through the disclosed Refund Due process and is not silently netted.

Generation control: print the allocation wording for the exact approved product. Allocation is system-controlled; Collector/Staff cannot freely choose or override its order.

VIII. LATE PAYMENT CHARGES

Late Payment Charge | {Locked Charge Rule / None - PHP 0.00}
Penalty Rate | {Locked Rate and Period / None - 0%}
Other Default Charge | {Locked Other Charge / None - PHP 0.00}

Any late payment charge or penalty shall be imposed only as stated in the Loan Agreement, this Disclosure Statement and applicable law. No such charge applies where the issued Disclosure states None / zero.

Generation control: select the exact charge branch for this loan before signing. State its rate/amount, overdue base, trigger, accrual period, partial-month convention and applicable caps. A post-maturity 7x7 charge begins only after the signed Contractual Maturity, not merely after Day 60 or a pre-maturity missed installment. No generic choices or handwritten charge may remain in the issued document.

INTERNAL 7x7 BRANCH CONTROL - The recorded product direction is 3% per month, simple/non-compounding, not automatic permission to charge. Select only for an eligible loan whose signed rule, overdue base, partial-month convention, legal/cost caps and server enforcement are complete. Unresolved checks block penalty use. Valid no-charge loans print None / PHP 0.00; historical None/zero contracts are unchanged. Remove this note before issuance.

IX. PREPAYMENT

The Borrower may prepay all or part of the Loan in accordance with the Loan Agreement and applicable law.

Prepayment Charge | None / PHP 0.00

A different prepayment charge may appear only when its exact lawful amount/basis was separately approved and disclosed in the same locked packet before signing.

X. BORROWER'S RIGHT TO INFORMATION

The Borrower may request information regarding the current outstanding balance; payments received; payment history; interest charged; lawful fees and charges; current amount due; and updated payment schedule. The Lender shall maintain appropriate records of the Loan transaction and payments.

XI. BORROWER'S ACKNOWLEDGMENT

I acknowledge that:

1. I received this Loan Disclosure Statement before consummation/release of the Loan and was informed of the amount financed, net proceeds, interest rate, finance charges and all applicable fees, charges, penalties and other amounts payable.

2. I received the complete Schedule of Payments and understand the total amount payable under the original contractual schedule.

3. I understand the consequences of late payment and default, as well as the rules regarding prepayment.

I confirm that I was given an opportunity to review and ask questions concerning the terms of the Loan. This acknowledgment is not a confirmation that cash has been received.

Borrower Printed Name | {Borrower Full Name}
Borrower Signature / Recorded Signing Date | ________________________  /  ______________
Lender / Management Approver | {Controlled Company Name / Authenticated Approver}
Position / Approval Reference | {Authenticated Position / Locked Approval Ref.}
Approved At / Execution Evidence | {Server Timestamp / Authorized Evidence Ref.}

The lender-side execution/approval record is generated from the authenticated Management approver and exact locked packet. The fields above do not create a signature or authorize an unauthenticated signature image. Borrower execution is recorded separately.

Privacy reference: personal data is handled under SPINA's separate Privacy Notice and, where applicable, Consent and Authorization Form, with reference to RA 10173 (Data Privacy Act of 2012), its IRR and applicable NPC issuances. This disclosure acknowledgment is not consent to optional processing.
```
