# Read-only protected Regular collection journal-line proposals

Status: **backend-only accounting preview**. This slice creates no migration,
journal draft, posted General Ledger entry, lending mutation, or automatic source
posting.

## Purpose

The source-event preview already proves deterministic collection identity and
void/duplicate state. The event-date EIR allocator now proves the exact cash split
for measured Regular loans, and Stage 5D.2 provides the immutable ledger anchor
after opening-journal preparation. This slice connects those read-only references
without crossing into journal creation.

## Protected gates

Lines are exposed only when all of the following are true:

- the complete EIR allocation result is ready;
- the protected opening-balance journal is posted;
- the immutable per-loan snapshot exists and its batch reconciles;
- post-cutover source history is complete;
- accounts 1020, 1100, and 1120 exist as active posting accounts;
- the deterministic collection source key has no draft or posted journal;
- no reversal state exists; and
- the collection is an active supported Regular PAYMENT/ADV.

Voided events, 7x7, cutover-date cash, post-maturity cash, cash above carrying
amount, unsupported modes, incomplete source history, missing accounts, and
unexpected journal/reversal states remain fail-closed with no proposed lines.

## Read-only collection lines

For one accepted Regular collection:

- debit 1020 `cash_collector_custody` for total cash;
- credit 1120 `accrued_interest_receivable` for cash clearing accrued EIR;
- credit 1100 `loans_receivable_regular` for cash reducing the loan component.

Zero-value credit lines are omitted. Total debit and total credit must reconcile
exactly to cents. Every preview remains `posting_eligible=false`.

## Required earlier EIR accrual

The API separately reports
`required_eir_accrual_before_collection`, sourced from the allocator's
`effective_interest_accrued_since_prior_event`.

That amount is not turned into Dr 1120 / Cr 4000 lines here. Fiscal-period-aware
EIR accrual proposals, deterministic accrual identity, reversal behavior, draft
creation, and protected posting are separate later stages. A balanced collection
preview is therefore accounting evidence, not permission to post.

## API and safety boundary

The existing Management EIR allocation response includes
`collection_journal_previews`. It remains a GET-only endpoint protected by the
Management role and `accounting.view`.

This slice does not add a write endpoint, UI control, database object, automatic
posting flag, Default/ECL/1190 behavior, 7x7 policy, remittance accounting, tax
entry, or production data change.
