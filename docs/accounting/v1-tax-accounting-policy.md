# SPINA V1 evidence-backed tax accounting policy — A6.2

Status: **draft accounting/tax control policy for Master #296 A6.2**. This document does not create a tax return, tax liability, tax payment, or live legal-book posting. Actual Philippine tax treatment must remain tied to retained current legal/BIR/registration evidence and Management/CPA review at the time of the transaction.

## Scope

A6.2 covers only the tax consequences that are directly attached to SPINA's already-protected V1 lending source events:

1. documentary stamp tax (DST) on the original issue of an in-scope loan debt instrument; and
2. percentage/gross-receipts tax on the supported taxable interest, commissions or discounts from lending receipts.

SPINA V1 does not create a new generic fee/processing/service/other-income source class merely to populate a tax base. Corporate income tax, payroll/compensation withholding, vendor withholding, and tax consequences of future expense/source-event classes are not inferred from the existing lending journals. Those items require their own authoritative source evidence and applicable policy before they can enter protected accounting.

## Current legal references retained by the policy design

The software must retain the exact rule evidence actually approved for the legal books. Current design references include:

- Republic Act No. 12214 (Capital Markets Efficiency Promotion Act), section 21 amending NIRC section 179 on documentary stamp tax on debt instruments. The current statutory structure taxes the original issue of a debt instrument at 0.75% of issue price and proportionately by term days / 365 for instruments with a term below one year, while imposing only one DST across the loan agreement/promissory note and related security contracts for the same loan.
- BIR percentage-tax guidance for other non-bank financial intermediaries not performing quasi-banking functions, which identifies interest, commissions and discounts from lending activities with remaining maturity of five years or less at 5%, subject to the taxpayer's actual registration/classification and any later legal change.
- BIR Form 2000 guidance for documentary stamp tax declarations/returns and retained proof of constructive affixture/payment when applicable.

These references are design inputs, not permission for SPINA to assume that a particular live taxpayer classification, exemption, tax rate, tax base, filing period, or payment amount applies. The protected live path must require the exact approved rule evidence used for that legal period.

## Permanent V1 boundaries

- `automatic_source_posting=false` remains mandatory.
- Tax evidence is separate from PFRS/EIR accounting evidence.
- A tax amount must never be fabricated because a loan or cash transaction exists.
- The existing General Journal remains the only General Journal. A6.2 must not create a parallel tax journal.
- Management must explicitly review evidence before any tax journal is prepared or posted.
- Posted tax accounting is immutable. A later correction is a new protected adjustment/reversal evidence event; historical evidence and journals are not rewritten.
- Closed-period controls apply to tax accounting exactly as they apply to other protected General Journal postings.

## Critical separation: PFRS EIR is not automatically the tax gross-receipts base

SPINA's protected Regular and 7x7 accounting layers use effective-interest accounting. The amount credited to accounting interest income or allocated to accrued-interest receivable is therefore an accounting measurement and may differ from the contractual/statutory receipt classification used for tax.

A6.2 must **not** calculate percentage/gross-receipts tax by simply reading account `4000 Interest Income - Regular`, account `4010 Interest Income - 7x7`, account `1120 Accrued Interest Receivable`, `accounting_eir_interest_received`, or another PFRS/EIR field.

Instead, every protected cash transaction that is included in the tax layer requires exact retained tax-allocation evidence identifying the supported taxable lending-receipt component and the non-taxable principal component. The allocation must reconcile to the exact protected non-voided cash transaction. If the contractual/statutory allocation is not proven, tax readiness is blocked and no tax amount is authoritative.

## Tax rule evidence

A tax calculation must reference immutable Management-approved rule evidence containing at least:

- tax type and rule key;
- effective date range;
- taxable or exempt treatment;
- exact rate when taxable;
- any applicable maturity boundary;
- legal/BIR source and retained source reference;
- SHA-256 digest of the retained rule evidence;
- substantive Management rationale; and
- actor/timestamp audit.

A later rule does not rewrite an earlier rule. New rule evidence supersedes the prior version explicitly.

## DST source evidence

A DST-ready loan requires all of the following to reconcile in one protected evidence record:

- exact SPINA loan and exact non-voided authoritative disbursement event;
- original issue/business date;
- issue price supported by the loan/disbursement evidence;
- exact contractual term in days from the protected loan dates;
- exact approved DST rule evidence effective on the issue date;
- retained loan/debt-instrument reference and SHA-256 digest;
- retained tax calculation reference and SHA-256 digest;
- exact calculated tax due, or explicit retained exemption evidence; and
- Management actor/timestamp audit.

For the current post-CMEPA taxable rule, the protected disposable calculation is:

`DST = issue price × 0.0075 × term_days / 365` when the term is below one year, otherwise `issue price × 0.0075`, rounded only under the approved deterministic currency policy.

The live implementation must not rely on this paragraph alone; it must consume the exact approved rule-evidence row effective for the transaction.

## Percentage/gross-receipts tax source evidence

For each exact non-voided protected `payment` or `advance` cash transaction included in the tax layer, Management must retain an immutable allocation showing:

- transaction, loan and client identity;
- collection date and exact source cash amount;
- supported taxable lending-receipt amount;
- supported non-taxable principal amount;
- proof that the two components exactly reconcile to source cash;
- exact approved percentage-tax rule evidence effective for that collection date;
- retained allocation evidence reference and SHA-256 digest; and
- Management rationale, actor and timestamp.

No tax is authoritative if the source is voided, the allocation does not reconcile, the tax rule is missing/stale for the transaction date, or the evidence is superseded.

## Protected accounting coordinates planned for A6.2

A6.2 will add dedicated posting accounts through a forward migration rather than rewriting the historical accounting-foundation migration:

- `5300 Percentage / Gross Receipts Tax Expense` — debit;
- `5310 Documentary Stamp Tax Expense` — debit;
- existing `2100 Tax Payables` — credit for the exact approved liability.

Tax settlement to BIR, when supported by retained payment/return evidence, will debit `2100 Tax Payables` and credit the exact approved real cash/bank account. Tax settlement must not be treated as another expense after the liability has already been recognized.

## Readiness before posting

The first A6.2 slice is evidence/readiness only. It must expose deterministic blockers and keep tax posting disabled. A later slice in the same A6.2 work may prepare and post only when:

- current source evidence is authoritative and not voided/superseded;
- the exact approved tax rule is effective for the source date;
- the tax base, rate, proration (if any), and tax due reconcile;
- the required fiscal period is open;
- protected tax expense/payable account identities remain active; and
- explicit Management confirmation matches the immutable evidence digest.

## Corrections and later filing evidence

A corrected or voided lending source does not silently mutate a prior tax record. The current evidence becomes stale and an explicit protected tax adjustment/reversal evidence event is required before period close. If a return has already been filed or paid, SPINA must retain the amended-return/credit/payment evidence rather than assuming that reversing the lending transaction automatically reverses tax legally.

## Gate A versus Gate C

A6.2 software acceptance uses synthetic/disposable tax rule, loan, cash-allocation, liability and settlement evidence. The approved live-schema installer must create no legal tax evidence, liability or payment merely by installing the capability.

At Gate C, actual taxes may be posted only from the company's actual registration/classification, actual transactions, retained tax calculations/returns/payment evidence, and the then-current approved rule evidence.