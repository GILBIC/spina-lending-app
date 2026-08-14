# SPINA V1 evidence-backed tax accounting policy — A6.2

Status: **draft accounting/tax control policy for Master #296 A6.2**. Evidence/readiness, protected liability recognition, evidence-backed tax settlement, and the protected pre-close tax correction/reversal core are represented in the A6.2 branch. Additional-tax amendment payment, later tax-refund/credit realization, and the live-schema/control proof remain incomplete. This document does not itself create a tax return, tax liability, tax payment, tax adjustment, refund, credit, or live legal-book posting. Actual Philippine tax treatment must remain tied to retained current legal/BIR/registration evidence and Management/CPA review at the time of the transaction.

## Scope

A6.2 covers only tax consequences directly attached to SPINA's already-protected V1 lending source events:

1. documentary stamp tax (DST) on the original issue of an in-scope loan debt instrument; and
2. percentage/gross-receipts tax on supported taxable interest, commissions or discounts from lending receipts.

SPINA V1 does not invent a generic fee/processing/service/other-income source class to populate a tax base. Corporate income tax, payroll/compensation withholding, vendor withholding, and tax consequences of future expense/source-event classes require their own authoritative evidence and policy.

## Current legal references retained by the policy design

The software must retain the exact rule evidence actually approved for the legal books. Current design references include Republic Act No. 12214/CMEPA section 21 amending NIRC section 179 on DST on debt instruments, BIR percentage-tax guidance for other non-bank financial intermediaries not performing quasi-banking functions, and BIR Form 2000 guidance for DST declarations/returns and proof of payment/constructive affixture when applicable.

Those references are design inputs, not permission for SPINA to assume that a particular live taxpayer classification, exemption, rate, tax base, filing period, or payment amount applies. The protected live path must consume retained current rule evidence approved for the exact legal period.

## Permanent V1 boundaries

- `automatic_source_posting=false` remains mandatory.
- Tax evidence is separate from PFRS/EIR accounting evidence.
- A tax amount must never be fabricated merely because a loan or cash transaction exists.
- The existing General Journal remains the only General Journal; A6.2 creates no parallel tax journal.
- Management must explicitly review evidence before any protected tax journal is prepared or posted.
- Posted tax accounting is immutable. Corrections are new protected evidence and new journal events; historical evidence and journals are never rewritten.
- Closed-period controls apply to tax accounting. The current 0086 correction core deliberately refuses to reopen or silently alter a closed original liability period.

## Critical separation: PFRS EIR is not automatically the tax gross-receipts base

SPINA's protected Regular and 7x7 accounting layers use effective-interest accounting. Accounting interest income or accrued-interest amounts may differ from the contractual/statutory receipt classification used for tax.

A6.2 must **not** calculate percentage/gross-receipts tax by simply reading account `4000 Interest Income - Regular`, account `4010 Interest Income - 7x7`, account `1120 Accrued Interest Receivable`, `accounting_eir_interest_received`, or another PFRS/EIR field.

Every protected cash transaction included in the tax layer therefore requires retained tax-allocation evidence identifying the supported taxable lending-receipt component and non-taxable principal component. The allocation must reconcile exactly to the protected non-voided cash transaction.

## Tax rule evidence

A tax calculation references immutable Management-approved rule evidence containing at least the tax type/rule key, effective date range, taxable or exempt treatment, exact rate when taxable, any maturity boundary, legal/BIR source and retained reference, SHA-256 digest, substantive Management rationale, and actor/timestamp audit. A later rule explicitly supersedes the prior version rather than rewriting it.

## DST source evidence

A DST-ready loan requires the exact loan and non-voided authoritative disbursement event, original issue/business date, supported issue price, exact contractual term, effective approved DST rule evidence, retained instrument/calculation references and SHA-256 digests, exact calculated tax due or retained exemption evidence, and Management audit.

For the current post-CMEPA taxable design reference, the disposable calculation is:

`DST = issue price × 0.0075 × term_days / 365` when the term is below one year, otherwise `issue price × 0.0075`, rounded only under the approved deterministic currency policy.

The live implementation must not rely on this paragraph alone; it consumes the exact approved rule-evidence row effective for the transaction.

## Percentage/gross-receipts tax source evidence

For each exact non-voided protected `payment` or `advance` cash transaction included in the tax layer, Management retains immutable allocation evidence showing transaction/loan/client identity, collection date and source cash amount, supported taxable lending-receipt amount, supported principal amount, exact reconciliation to source cash, effective approved percentage-tax rule evidence, retained reference/digest, and Management audit.

No tax is authoritative if the source is voided, the allocation fails to reconcile, the rule is missing/stale, or the evidence is superseded.

## Protected liability accounting coordinates

A6.2 adds dedicated posting accounts through forward migrations:

- `5300 Percentage / Gross Receipts Tax Expense` — debit;
- `5310 Documentary Stamp Tax Expense` — debit; and
- existing `2100 Tax Payables` — credit for the exact approved liability.

A positive current evidence item may create only one protected General Journal draft. Preparation and posting revalidate the protected source, rule, evidence digest/amount, dedicated expense account, `2100`, recognition date, exact open fiscal period, journal identity, and balanced two-line coordinates. Zero-tax evidence creates no fake zero-value journal.

The liability journal is exactly **Dr dedicated tax expense / Cr 2100 Tax Payables**. Generic/manual posting and manual reversal are rejected. Exact immutable retry identity is enforced and forced post-audit failure must roll the entire database statement back.

Migration `0082` is evidence/readiness only. Migration `0083`, hardened by `0084`, is protected Management-confirmed liability recognition. A posted liability whose source/rule/evidence later becomes stale is surfaced as `posted_adjustment_review_required`; it is never mutated.

## Protected return and payment evidence

Migration `0085` adds protected return/payment settlement. A return is not inferred merely because liabilities were posted. Management retains immutable return/filing evidence identifying tax type, return period, filing date, declared tax due, retained references/digest/note, and the exact immutable V1 liability posting IDs included.

Every selected liability must remain an exact current protected posted liability of the same tax type and inside the retained return period. Declared tax due must equal the exact sum of those postings. A liability posting can belong to only one retained V1 return.

Payment evidence is separate. V1 settlement requires exact full payment of the retained declared tax due; partial payment is not inferred. Approved payment accounts are:

- `1010 Cash - Office`; or
- `1030 Cash - Bank / GCash`.

Collector custody is not an approved tax-payment account.

## Protected tax settlement accounting coordinates

A current exact return plus retained full-payment evidence may prepare one settlement draft. The settlement journal is exactly:

- **Dr `2100 Tax Payables`**; and
- **Cr the exact approved `1010 Cash - Office` or `1030 Cash - Bank / GCash` account**.

Settlement never re-debits `5300` or `5310`, because expense was already recognized at liability posting. Posting requires separate Management permission and exact confirmation of return digest, payment digest, amount, payable/cash accounts, posting date, fiscal period, and policy version. Manual bypass/reversal is rejected, retry identity is immutable, and forced audit failure must roll the complete statement back.

If a settled return later contains a liability whose evidence became stale, it is surfaced as `settled_adjustment_review_required`; original return/payment/settlement history remains immutable.

## Protected pre-close tax correction/reversal core

Migration `0086` introduces the first executable correction layer. It intentionally supports only correction cases whose accounting consequence can be proven from one exact stale posted liability and one exact newer current evidence record for the **same protected source, loan, client and tax type**.

The correction evidence record is immutable and Management-approved. It stores the original liability posting, original and replacement evidence identities, original and replacement tax due, adjustment amount, correction date, retained reference/digest/note, actor/timestamp, and any exact original settlement history. The amount is derived by the protected database function from source evidence; the API does not accept an arbitrary accounting amount.

The replacement evidence must be newer, current, unposted and exact for the same protected source. If those coordinates change before preparation or posting, the adjustment fails closed.

### Unpaid stale liability — full reversal only

If the stale posted liability has **no tax payment evidence**, V1 may fully reverse the original posted tax liability while the original liability fiscal period remains open and contains the adjustment date.

The protected correction journal is exactly:

- **Dr `2100 Tax Payables`** for the full original posted liability; and
- **Cr the original dedicated `5300` or `5310` tax expense** for the same amount.

This journal carries `reversal_of_entry_id` to the exact original V1 tax-liability journal. Manual General Journal reversal remains blocked; the reference is permitted only inside the protected tax-adjustment preparation session.

This core deliberately performs a **full reversal** rather than posting only a delta. After reversal, the exact newer current evidence may proceed through the normal protected liability workflow for its supported amount. That keeps the original wrong liability and its correction explicit rather than mutating history.

If payment evidence appears before adjustment preparation/posting, the unpaid reversal path is blocked.

### Already-settled stale liability — supported tax decrease

If the original liability was already fully settled, the cash payment is historical fact and must not be silently reversed. When exact newer current evidence proves a lower tax amount, V1 recognizes only the supported decrease as a recoverable asset:

- **Dr `1130 Tax Recoverable`** for `original tax due − replacement tax due`; and
- **Cr the original dedicated `5300` or `5310` tax expense** for the same amount.

The original `Dr 2100 / Cr cash` settlement remains posted and unchanged. `1130 Tax Recoverable` is only accounting recognition of the supported overpayment/correction position; it is **not** proof that BIR has granted a refund or tax credit.

To prevent double counting, once a settled-tax-recoverable adjustment is posted, the exact replacement evidence is surfaced as `covered_by_settled_adjustment` and cannot create a second full protected liability through the normal preparation path.

A settled item whose stale liabilities all have posted protected adjustments is surfaced as `settled_adjustment_recorded`. If adjustment evidence exists but not every stale settled liability is posted, it remains `settled_adjustment_in_progress`.

### Adjustment posting controls

The protected adjustment draft/post lifecycle revalidates the stale original liability, exact replacement evidence, original settlement when applicable, open original fiscal period, debit/credit accounts, journal identity and two-line balance. It requires action-specific Management permissions, explicit confirmation, SHA-256 evidence confirmation, exact amounts/accounts/date/period, immutable retry identity, and a protected posting audit.

Generic/manual posting is rejected. Adjustment journals and audit rows are immutable. A forced audit failure after the General Journal post must roll the entire statement back so no posted adjustment can exist without its immutable protected audit.

`tax_adjustment_reversal_enabled=true` therefore means **this narrow protected pre-close correction core is enabled**. It does not mean every possible tax amendment/refund case is implemented.

## Remaining correction boundaries after 0086

The following are intentionally **not inferred by the 0086 core** and still require separate retained-evidence workflows before A6.2 is complete:

1. **Additional tax after filing/payment** — where replacement evidence proves tax greater than the original settled amount. SPINA must retain amended-return/additional-assessment and payment evidence before recognizing/posting the extra payable/payment.
2. **Refund or tax-credit realization** — `1130 Tax Recoverable` is not cleared merely because it exists. A later refund receipt or legally usable tax-credit application requires retained authority/reference evidence and an exact protected realization/application journal.
3. **Closed-period corrections** — 0086 refuses to alter a closed original period. Any later-period correction treatment requires an explicit accounting/tax policy rather than silently reopening history.
4. **Partial tax payments** — remain outside V1 settlement until an explicit policy and exact evidence model are approved.

These boundaries are deliberate fail-closed controls, not missing automatic behavior.

## Gate A versus Gate C

A6.2 software acceptance uses synthetic/disposable tax rule, loan, cash-allocation, liability, return, payment, settlement and adjustment evidence. Installing the capability on the approved live database must create **no** legal tax evidence, liability, return, payment, settlement, adjustment, refund or credit and must preserve existing protected history.

At Gate C, actual tax accounting may post only from the company's actual registration/classification, actual transactions, retained tax calculations/returns/payment/correction evidence, and then-current approved rule evidence.
