# Mixed cash and noncash disclosure evidence — proposed 0158

Status: design only. The current report keeps `noncash_disclosure_status=mixed_transactions_require_review`. No migration, retained review API or completeness claim is implemented by this document.

## Scope and accounting basis

The current inventory omits every journal containing a selected cash account. That inventory cannot capture, for example, an asset acquired partly with cash and partly by assuming a borrowing. IAS 7 excludes noncash investing and financing transactions from cash flows and calls for separate disclosure. It also requires information about both cash and noncash changes in financing liabilities. Sources checked on 5 October 2026: the [IFRS Foundation IAS 7 overview](https://www.ifrs.org/issued-standards/list-of-standards/ias-7-statement-of-cash-flows/) and [IAS 7 paragraphs 43–44E](https://www.ifrs.org/content/dam/ifrs/publications/pdf-standards/english/2021/issued/part-a/ias-7-statement-of-cash-flows.pdf).

Implement complete reviewed coverage of the posted ledger, including mixed journals. This does not prove that all external transactions were recorded, choose actual tax facts, or complete every statutory note. Existing source-completeness and annual-package flags remain independent. The user delegated the software accounting design; no additional external design approval is required.

## Why an inferred noncash total is insufficient

For debit asset 1,000 / credit cash 400 / credit borrowing 600, the reviewed noncash acquisition is 600. Summing all noncash journal lines would double count it and incorrectly include the cash-funded asset component. In a larger compound journal even the minimum of noncash debits and credits does not uniquely identify the economics. Do not infer a disclosure from net cash or a balancing residual.

Use explicit retained component allocations. Every component links one debit line and one credit line in the same posted journal and carries a positive exact-cent amount. Across the review, each line must be allocated exactly once in total, with no over-allocation or remainder. This gives a balanced decomposition without fabricating another journal or cash event. Classification and supporting references express the actual economic interpretation and remain reviewable evidence.

## Retained contract

Reserve migration 0158 for immutable `accounting.journal_disclosure_reviews` and narrow private functions. A review binds the book, fiscal period, current reporting-policy version, posted journal identity and reversal relationship, complete ordered journal lines, semantic chart identities, actor, actual review timestamp, evidence reference, reason and version. Retain a stable canonical digest of that snapshot. Display names and retirement do not invalidate historical meaning; changed IDs/codes/system keys/account type/normal balance/posting role do.

Each allocation contains debit-line ID, credit-line ID, exact positive amount, a supported disclosure classification and an evidence reference. Supported noncash classifications should distinguish investing, financing, combined investing/financing, operating adjustments, and other documented reclassifications. Combined investing/financing is one component displayed with both labels, never added twice to a grand total. Avoid a grand noncash total across unrelated categories. Opening balances and formal closing transfers are separately identified and excluded from current-period transaction totals through protected source identity, including reversals of opening journals.

An allocation involving a selected cash line is a cash-connected component. It cannot also be reported as a noncash component. It must reconcile to that line's retained cash-flow allocations. Existing protected internal-transfer and Collector physical-principal checks remain authoritative; disclosure review cannot override a missing/corrected source proof, classify a credit application as a second physical cash event, or conceal a selected-cash movement.

The review is immutable, append-only and versioned. Exact request replay returns the same review; a changed request body conflicts. New revisions supersede only the selected review, preserving prior content and timestamps. A journal reversal is a different posted source requiring its own economic classification and explicit reference to the original; no automatic sign inversion may certify an unrelated replacement transaction.

## Coverage and concurrency

Read policy, reviews, journals, chart semantics, cash classifications and source proof within the existing repeatable-read statement snapshot. Reporting must include a candidate for every posted journal in the fiscal period, with explicit protected opening/close exclusions. An omitted review, changed policy, changed semantic chart, unclassified allocation, missing correction proof or new journal yields an exact coverage blocker. Zero activity is complete for the posted-ledger disclosure scope only when a valid current reporting policy exists.

Prepare/write uses current Management authority, the established period/book locks and optimistic review version. Recompute the bound source digest under those locks before inserting the new version. Use existing evidence validation and private grants. This is presentation evidence, not a new monetary posting; it cannot bypass journal admission or reopen a period. If post-close presentation review is supported, label its actual date and preserve the original closed review snapshot separately.

Financing-liability reconciliation must follow the retained financing-account policy and classify every change between opening and closing carrying balance into cash, noncash components and protected opening adjustments. It must equal the balance sheet and must not count the two sides of a debt-to-equity conversion as two liability changes. Keep payable control reconciliation separate: an unpaid reconciled liability is valid.

## API and clients

Expose reviewed component amounts, dates, account labels, policy/review version, permitted evidence references, coverage blockers and the financing rollforward. Omit private wallet/source snapshots, internal file locations and borrower dimensions not needed for reporting. Apply current authorization before aggregate totals and pagination.

Portal and Flutter should guide review by transaction: show the posted debit/credit lines, how much remains to be allocated, cash versus noncash portions, the chosen disclosure and its reason. Preserve explicit review/save, exact retry and recovery. A stale policy/source/version must request a new review; role/session changes clear all private state. Do not expose allocation IDs or implementation policy strings as the primary explanation.

## Behavioral verification

1. Asset 1,000 funded by cash 400 and borrowing 600: cash flow remains 400 and noncash acquisition is 600; no double count.
2. Pure borrowing-to-equity conversion, EIR accrual, ECL, regular receipt/application, owned transfer with fee, Collector handover and future credit application each keep their distinct economics.
3. Compound cash receipts/payments with zero net cash still retain gross cash flows. Allocation review cannot net them away.
4. Exact line coverage rejects duplicate/overlapping, missing, negative, fractional-cent, wrong-journal and wrong-side allocations; large exact amounts use Decimal/NUMERIC.
5. Policy changes, semantic recoding, new journals, corrections and reversals produce the appropriate current blockers; labels/retirement preserve valid retained history.
6. Positive/loss/zero-activity periods, opening and close entries, comparatives and financing-liability opening-to-closing reconciliation agree in one snapshot.
7. Simultaneous revision, post/close/source races, rollback after audit, exact retry, revoked authority and all-page privacy have real database proof.
8. Both clients reject malformed totals, recover the original request after a lost response, and clear state on role/session change. Fresh-schema populated restore preserves every review and its report output.

This design is not verification evidence. Implement and observe each baseline before marking the reporting task complete.
