# Source-event accounting preview

## Purpose

This stage is a read-only bridge between authoritative lending events and future accounting automation. It does **not** create journal drafts, post General Ledger entries, change lending records, or enable automatic source posting.

The first supported source family is `lending.collection_transactions` because accepted collection rows are immutable operational cash events and Management voids have an explicit audited state.

## Collection cash is a valid source, but journal allocation is not guessed

A non-voided post-cutover `payment` or `advance` is an authoritative cash event. However, this stage deliberately does **not** emit debit/credit journal lines yet.

The Stage 5D EIR measurement engine carries each loan using accounting components:

- Regular loan component -> `loans_receivable_regular` (1100);
- 7x7 loan component -> `loans_receivable_7x7` (1110);
- accrued effective interest -> `accrued_interest_receivable` (1120).

The EIR engine applies cash to accrued effective interest first and then to the loan component. Therefore crediting the full operational collection amount directly to 1100 or 1110 would be unsafe whenever accrued EIR exists. PAYMENT/ADV is classified as `eir_allocation_required` until an event-date EIR allocation layer can determine the exact split and reconcile it to the carrying amount.

This also prevents contractual 7x7 interest from being mistaken for PFRS 9 EIR interest income.

`pass` is non-cash and never produces a journal proposal. Custom or unknown loan calculation modes remain `policy_review` instead of being guessed as Regular or 7x7.

## Cutover boundary

The preview uses the same current-workbook rule as the existing opening-balance workflow: the most recently created workbook (`created_at DESC`). It does not switch to a different workbook merely because another row has a later cutover date.

The opening-balance workbook stores a date, not a timestamp. To prevent double counting:

- source events before the cutover date are `pre_cutover` and are never proposed again;
- events on the cutover date are `cutover_date_review` because their order relative to the date-only opening snapshot cannot be proven;
- only events strictly after cutover can reach the EIR-allocation readiness stage.

If no opening-balance cutover exists, source-event mapping is blocked as `cutover_required`.

The preview also reports whether the opening-balance journal has actually posted, but this stage remains non-posting regardless of that state.

## Complete pagination

The API uses keyset pagination ordered by `(collection_date, accepted_at, transaction_id)` descending. It requests one extra row to determine `has_more` and returns an opaque `next_cursor` based on the last visible event. Supplying that cursor continues strictly after the prior page boundary, so more than 250 events on the same collection date remain reachable without duplicates or gaps caused by a date-only cursor.

Malformed cursors are rejected with a validation error rather than being treated as a new page.

## Deterministic identity and duplicates

Every collection uses the deterministic future accounting source key:

`collection:<collection_transaction_uuid>`

The preview checks `accounting.journal_entries.source_event_key`. If a draft or posted journal already exists, it reports `draft_exists` or `already_posted` rather than treating the source event as new.

## Voids and reversals

A voided collection is never silently treated as active cash:

- no accounting journal exists -> `voided_before_accounting`; no entry is needed;
- source journal is still draft -> `voided_draft_requires_cancel`; do not post it;
- source journal posted and no reversal exists -> `reversal_required`;
- reversal draft exists -> `reversal_draft_exists`;
- posted reversal exists -> `reversed`.

Future reversal automation must use the existing controlled `accounting.create_reversal_draft` mechanism. Posted entries remain immutable.

## Account configuration

The repository validates these stable accounting `system_key` values before reporting configuration ready for the future EIR allocation layer:

- `cash_collector_custody`
- `loans_receivable_regular`
- `loans_receivable_7x7`
- `accrued_interest_receivable`

They must exist and remain active posting accounts. UUIDs are never embedded as accounting mappings.

## Explicitly excluded from this slice

- collection journal-line allocation until event-date EIR allocation is proven;
- loan-release/disbursement journals: a `lending.loans` row and `date_released` alone do not prove the authoritative cash-disbursement event or funding account;
- renewal/restructure accounting: signed settlement/restructure treatment must be proven first;
- EIR accrual journal creation;
- remittance transfer accounting between Collector Custody, Office Cash, bank, or GCash;
- journal draft creation;
- automatic General Ledger posting;
- Default/ECL/1190 changes;
- tax entries.

Those source families will be introduced separately only after their evidence, account mapping, reversal behavior, fiscal-period handling, and reconciliation rules are supportable.
