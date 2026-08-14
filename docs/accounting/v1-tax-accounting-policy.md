# SPINA V1 evidence-backed tax accounting policy — A6.2

Status: **draft accounting/tax control policy for Master #296 A6.2**. Evidence/readiness, protected liability recognition, and evidence-backed tax settlement capabilities are now represented in the A6.2 branch. Protected tax adjustment/reversal execution and the live-schema/control proof remain incomplete. This document does not itself create a tax return, tax liability, tax payment, or live legal-book posting. Actual Philippine tax treatment must remain tied to retained current legal/BIR/registration evidence and Management/CPA review at the time of the transaction.

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

## Protected liability accounting coordinates

A6.2 adds the dedicated posting accounts through a forward migration rather than rewriting the historical accounting-foundation migration:

- `5300 Percentage / Gross Receipts Tax Expense` — debit;
- `5310 Documentary Stamp Tax Expense` — debit;
- existing `2100 Tax Payables` — credit for the exact approved liability.

A positive current tax-evidence item may create only one protected General Journal draft for the exact evidence identity. Preparation revalidates the authoritative source event, current approved tax rule, tax amount, dedicated expense account, `2100 Tax Payables`, and the open fiscal period containing the tax-recognition date. Zero-tax evidence creates no fake zero-value General Journal entry.

Posting requires a separate Management permission and exact confirmation of the evidence digest, tax due, expense/payable account codes, posting date, and fiscal period. The posting function revalidates all source, rule, evidence, account, period, journal and line coordinates inside the same database statement before delegating to the existing protected General Journal posting primitive. The exact journal must remain two balanced lines: debit the dedicated tax expense and credit `2100 Tax Payables`. Generic/manual posting and manual reversal of that protected system journal are rejected.

The protected posting audit is immutable and exact retry identity is required. A forced audit failure after the journal-post operation must roll the entire database statement back so no posted journal can exist without its immutable protected tax-posting audit.

## Evidence/readiness versus liability recognition

Migration `0082` is evidence/readiness only and never posts. It continues to expose `tax_posting_enabled=false` because evidence capture itself is not a posting workflow.

Migration `0083`, hardened by `0084`, is a separate protected Management-confirmed liability-recognition capability. It may prepare/post only from positive current evidence that passes every source/rule/period/account revalidation gate. Its queue exposes `protected_tax_liability_posting_enabled=true`. The liability-recognition layer itself does not infer filing or payment and never enables automatic source posting.

A posted liability whose source/rule/evidence is later superseded or otherwise ceases to be current is not mutated. It is surfaced as requiring protected adjustment/reversal review while the newer evidence remains a separate immutable item.

## Protected return and payment evidence

Migration `0085` adds a separate protected tax-settlement capability. A tax return is not inferred merely because one or more tax liabilities have been posted. Management must retain immutable return/filing evidence identifying:

- tax type;
- exact return period;
- filing date;
- declared tax due;
- return and retained evidence references;
- SHA-256 evidence digest and substantive note; and
- the exact immutable V1 tax-liability posting IDs included in that return.

Every selected liability must remain an exact current protected posted liability of the same tax type and inside the retained return period. The declared tax due must exactly equal the sum of those immutable liability postings. A tax-liability posting may belong to only one retained V1 return evidence record. Exact idempotent retry is required.

Payment evidence is also separate from filing evidence. Management must retain the exact payment date, amount, payment reference, evidence reference/digest/note, and the actual SPINA payment cash account. V1 permits only full settlement of the retained declared tax due; partial payment requires a later explicit policy instead of being inferred. The approved V1 payment accounts are:

- `1010 Cash - Office`; or
- `1030 Cash - Bank / GCash`.

Collector custody is not an approved tax-payment account. Payment evidence does not itself post the General Journal and does not rewrite tax expense.

## Protected tax settlement accounting coordinates

A current exact return plus retained full-payment evidence may prepare one protected General Journal settlement draft. Preparation revalidates every retained return liability, the declared/payment amount, `2100 Tax Payables`, the exact approved `1010` or `1030` cash account, and the open fiscal period containing the payment date.

The settlement journal is exactly:

- **Dr `2100 Tax Payables`** for the retained payment amount; and
- **Cr the exact approved `1010 Cash - Office` or `1030 Cash - Bank / GCash` account** for the same amount.

Settlement does **not** debit `5300` or `5310` again, because the expense was already recognized when the liability was posted.

Posting requires a separate Management permission and exact confirmation of the retained return digest, payment digest, payment amount, payable/cash account codes, posting date, fiscal period and settlement policy version. The protected function revalidates the exact return composition, payment evidence, accounts, open period, journal identity and two-line coordinates before delegating to the existing General Journal posting primitive.

Generic/manual posting bypass is rejected. Manual General Journal reversal of a protected settlement is rejected. Exact immutable retry identity is enforced. A forced audit failure after the underlying journal post must roll the full database statement back so no posted settlement journal can exist without its immutable protected settlement audit.

The settlement queue exposes `tax_settlement_enabled=true`, while `tax_adjustment_reversal_enabled=false` and `automatic_source_posting=false` remain explicit. If an already-settled return later contains a liability that is no longer current, the settlement is surfaced as requiring protected adjustment/reversal review; historical evidence and posted journals remain unchanged.

## Corrections and later filing evidence

A corrected or voided lending source does not silently mutate a prior tax record. The current evidence becomes stale and an explicit protected tax adjustment/reversal evidence event is required before period close. If a return has already been filed or paid, SPINA must retain the amended-return/credit/payment evidence rather than assuming that reversing the lending transaction automatically reverses tax legally.

The liability-recognition queue may flag a posted item as `posted_adjustment_review_required`, and the settlement queue may flag a paid return as `settled_adjustment_review_required`. Neither status is itself a reversal and neither changes General Journal history. The protected adjustment/reversal path must preserve the original liability and settlement postings and create separately audited correcting accounting events from retained legal/filing/payment evidence.

## Gate A versus Gate C

A6.2 software acceptance uses synthetic/disposable tax rule, loan, cash-allocation, liability, return and settlement evidence. The approved live-schema installer must create no legal tax evidence, liability, return, payment or settlement merely by installing the capability.

At Gate C, actual taxes may be posted only from the company's actual registration/classification, actual transactions, retained tax calculations/returns/payment evidence, and the then-current approved rule evidence.
