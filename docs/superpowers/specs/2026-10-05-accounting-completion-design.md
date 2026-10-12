# SPINA accounting completion design

User instruction: **“Plan everything and fix.”** This specification implements the findings in the 5 October accounting-readiness review. Implementation is authorized; production activation and the truth of actual opening balances are separate matters.

**10 October correction:** The owner explicitly said, “i did not have any books,” and approved the S04 repair. The earlier description of an existing owner book was an incorrect assumption. Implement first-book setup using verified available records. Separate deployment boundaries apply only if there are actually separate entities to record; they do not imply an existing business, ledger, opening balance or prior period.

## Outcome and acceptance

SPINA must account for actual cash once, retain amounts owed as liabilities, reconcile lending/custody/Treasury sources to the existing General Ledger, prevent an incomplete period from closing, and provide a complete accountant-reviewable reporting package. A balanced trial balance is one invariant, not an assertion of completeness or statutory compliance.

There are six staged deliverables. Each has its own tests and review. A partially implemented stage must remain visibly incomplete; the program is complete only when all software gates pass. The user explicitly delegated framework/chart design on 5 October 2026 ("No need, you can do it"). Engineering does not wait for external policy approval. Actual book identity, opening amounts, tax facts and production release remain separate verified inputs and must never be fabricated. Independent review is part of statutory-use acceptance, not a reason to leave software design unfinished.

## A. Separate books

Use one accounting identity per database/deployment. The current schema has globally unique account keys, global fiscal-period date exclusions, date-only journal/reversal selection and cumulative queries across all journals. A book selector or adding book_id to a few tables would not isolate the many existing protected functions. Configure the first book for the verified actual entity. If a separate entity later needs its own book, use a separately configured database running the same reviewed code. No automatic copying, transfer or relabelling of transactions between entities.

Introduce a protected singleton book identity: kind owner_operations, corporate_legal or synthetic; retained entity label, evidence reference/digest, actor and timestamps. No migration invents an actual company identity or opening amount. Unconfigured books remain visible as unconfigured. New Treasury accounting requires an explicit configured identity. A Treasury context must have exactly the same kind as the accounting book; personal-owner wallets cannot enter corporate books as company cash. A corporate deployment requires its own database, authentication/authorization data and private evidence storage. A future in-app switch must select a separately authenticated deployment; it must not pass a client-chosen database connection or SQL schema.

## B. Source-linked Treasury accounting

Reuse accounting.journal_entries, journal_lines, posted-entry protections and post_journal_entry. Add explicit reviewed mapping from each Treasury account/context to the posting cash account and required clearing accounts. Mapping changes may not rewrite prior journals. Preparations pin mapping versions, source IDs/versions/digests, date, exact amounts, accounts and the selected period. Posting must revalidate all coordinates under locks and commit journal plus posting audit atomically. Retry uses the original identity; changed inputs conflict.

Cash accounting follows actual movement evidence, not approval or source-link completion:

- Verified borrower receipt: debit actual mapped cash, credit unapplied borrower funds. Application then reduces that liability and the appropriate loan carrying balance using the protected lending allocation/EIR coordinates; never debit cash twice.
- Loan payout: actual verified debit moves cash into disbursement transit; completion clears transit using the exact loan disbursement/renewal accounting coordinates. Unconfirmed delivery remains a visible asset/exception, not a second payment or fabricated borrower receipt.
- Transfers: source debit moves into transit; confirmed destination clears transit. Own transfers are not income. Separately evidenced fees are expenses.
- Unknown receipts and outflows retain an explicitly approved clearing classification; no guessed loan, income, expense or legal ownership.
- Corrections distinguish source reallocation, erroneous observation reversal, actual external refund and GL reversal. None rewrites posted history or releases an already consumed identity for silent reuse.

The 0137/0139 guards remain until exact, tested adapter authorization replaces them. A blanket session flag must not create a generic bypass. Cash receipts and their applications must not consume the same accounting event twice. Both legacy protected journals and new bridge journals must appear in completeness reconciliation.

## C. Liabilities

Retain generic Accounts Payable and protected Tax Payables, and add approved control accounts/schedules for Collector payable, unidentified receipts and unapplied borrower money. Company borrowings, shareholder funding, interest payable, wages/statutory accruals and borrower refunds need explicit source-backed classification; repayable funding must not be posted as capital merely because the owner supplied it.

Collector count acceptance records cash once. Unidentified excess remains a liability pending identification. Recognition of a Collector credit reclassifies that liability without another cash entry. An actual return reduces cash and the liability once; fees are separate; a genuine returned-payment reversal restores the appropriate liability once. Reserved amounts remain part of outstanding liability, not a second liability. A valid unpaid liability does not itself block close; an unreconciled liability does.

Historical credit application and correction adapters that are currently unsupported must remain blocked until implemented and tested. No software completion claim may quietly omit them.

## D. Completeness and closing

Produce a source inventory from authoritative events, including events that never generated a draft. For each in-scope source, report the exact matching posted accounting effect or a concrete blocker. Include collections/voids, disbursements/renewals, remittance, Treasury actual movements and corrections, Collector credit movements, required EIR/ECL assessments and approved tax obligations. Zero-valued PASS and other nonfinancial events must not create fake journal requirements.

The first protective increment must refuse closing any period with Treasury movements or Collector accounting sources that the existing ledger cannot reconcile. Do not allow a checkbox to waive an unexplained amount. The final gate uses completed adapters and permits valid outstanding liabilities whose source schedules equal their GL control balances.

Enforce at database review transition, preparation and final close, not only in UI. Guard concurrent/backdated source insertion and changes using a consistent lock strategy, revalidate at commit, retain the reviewed inventory digest, and surface late changes without silently altering closed history. Existing posted periods remain immutable. Dates use the SPINA business timezone Asia/Manila and explicit cutover scope.

## E. Reporting

Read each statement pack from one repeatable-read, read-only snapshot. Include posted-only profit/loss and financial position; add a cash-flow statement with explicit reviewed cash/cash-equivalent and cash-flow classifications, changes in equity, comparative period data and accountant-reviewed disclosure/policy notes. Do not infer all cash movements as operating, classify every lending advance as investing, or treat a capital injection as income. Exclude intra-cash transfers without hiding separately evidenced fees. Show unclassified cash activity as an unresolved reporting item, not zero.

Retained earnings closing transfers must not duplicate current-period profit in changes in equity. Reversed entries, loss periods, no-activity periods and historical retired accounts must reconcile. Financial reports display book identity, period, provisional/final-review status, source completeness and missing reporting evidence. Accountant policy and notes are retained as evidence; software does not assert PFRS compliance without the applicable framework and review.

## F. Verification and release

Extend the integrated verifier through the latest migration; keep older bounded verifiers for historical regression. In a fresh loopback-only synthetic database prove opening/capital, Regular and 7x7 disbursement/collection, actual wallet receipt/application, payout/transit completion, renewals, remittance, excess/credit/return, fees, reversal, liabilities, impairment, tax and formal close. Independently reconcile source schedules, wallet balances, GL, profit, equity and cash-flow totals. Exercise duplicate replay, changed payload, two-connection races, rollback after audit failure, access denial and evidence/private-file loss.

Run one heavy local database suite at a time on this low-memory host. Never use production endpoints or existing production-restore clusters. Production readiness additionally requires real book identities, accounts, permissions, opening figures, policy/CPA review, backup restore, retained regulatory evidence and an independently reconciled parallel close. Deploying software must not enable money-entry features or manufacture those inputs.

## Alternatives considered

1. Add an in-app book selector over the current tables: rejected because it leaves existing reads/writes cross-book.
2. Rewrite every protected function for shared-database multi-tenancy: possible future project, but unnecessary for the first-book requirement.
3. Configure one database for the actual entity and reuse the reviewed accounting engine: selected. Additional entities, if any, require independent setup and operations.

## References

- IFRS Foundation: [IAS 1](https://www.ifrs.org/issued-standards/list-of-standards/ias-1-presentation-of-financial-statements/) and [IAS 7](https://www.ifrs.org/issued-standards/list-of-standards/ias-7-statement-of-cash-flows/). Applicability and policy choices require company-specific review.
- Supabase: [RLS and grants](https://supabase.com/docs/guides/database/postgres/row-level-security). New private accounting tables deny client Data API access and preserve authenticated backend authorization.
