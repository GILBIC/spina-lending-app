# Source-event accounting preview

## Purpose

This stage is a read-only bridge between authoritative lending events and future accounting automation. It does **not** create journal drafts, post General Ledger entries, change lending records, or enable automatic source posting.

The first supported source family is `lending.collection_transactions` because accepted collection rows are immutable operational cash events and Management voids have an explicit audited state.

## Approved preview mapping

For a non-voided post-cutover `payment` or `advance`:

- debit `cash_collector_custody` for the exact accepted cash amount;
- credit `loans_receivable_regular` when the loan type uses `fixed_daily`;
- credit `loans_receivable_7x7` when the loan type uses `seven_by_seven`.

This is a cash / amortized-cost carrying-amount movement only. The collection amount is **not** treated as interest income. PFRS 9 EIR interest recognition remains a separate accounting event and will be implemented and reconciled separately.

`pass` is non-cash and never produces a journal proposal.

Custom or unknown loan calculation modes remain `policy_review` instead of being guessed as Regular or 7x7.

## Cutover boundary

The opening-balance workbook stores a date, not a timestamp. To prevent double counting:

- source events before the cutover date are `pre_cutover` and are never proposed again;
- events on the cutover date are `cutover_date_review` because their order relative to the date-only opening snapshot cannot be proven;
- only events strictly after cutover can reach `preview_ready`.

If no opening-balance cutover exists, source-event mapping is blocked as `cutover_required`.

The preview also reports whether the opening-balance journal has actually posted, but this stage remains non-posting regardless of that state.

## Deterministic identity and duplicates

Every collection uses the deterministic future accounting source key:

`collection:<collection_transaction_uuid>`

The preview checks `accounting.journal_entries.source_event_key`. If a draft or posted journal already exists, it reports `draft_exists` or `already_posted` rather than proposing a duplicate.

## Voids and reversals

A voided collection is never silently treated as active cash:

- no accounting journal exists -> `voided_before_accounting`; no entry is needed;
- source journal is still draft -> `voided_draft_requires_cancel`; do not post it;
- source journal posted and no reversal exists -> `reversal_required`;
- reversal draft exists -> `reversal_draft_exists`;
- posted reversal exists -> `reversed`.

Future reversal automation must use the existing controlled `accounting.create_reversal_draft` mechanism. Posted entries remain immutable.

## Account configuration

The repository validates these stable accounting `system_key` values before reporting configuration ready:

- `cash_collector_custody`
- `loans_receivable_regular`
- `loans_receivable_7x7`

They must exist and remain active posting accounts. UUIDs are never embedded as accounting mappings.

## Explicitly excluded from this slice

- loan-release/disbursement journals: a `lending.loans` row and `date_released` alone do not prove the authoritative cash-disbursement event or funding account;
- renewal/restructure accounting: signed settlement/restructure treatment must be proven first;
- EIR interest accrual;
- remittance transfer accounting between Collector Custody, Office Cash, bank, or GCash;
- journal draft creation;
- automatic General Ledger posting;
- Default/ECL/1190 changes;
- tax entries.

Those source families will be introduced separately only after their evidence, account mapping, reversal behavior, fiscal-period handling, and reconciliation rules are supportable.
