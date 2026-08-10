# Regular accounting sequence preview (Stage 5D.6)

## Decision

Stage 5D.6 adds a backend-only, read-only sequence preview for each proven
Regular cash event. It composes the existing EIR accrual and collection
journal-line previews into the accounting order already required by Stage 5D:

1. recognize the event-boundary EIR accrual; then
2. record the matching collection against the updated carrying components.

This stage does not create a journal draft, post an entry, mutate lending data,
or enable automatic source posting.

## Deterministic identity and order

For transaction UUID `<transaction_id>`, the only accepted identities are:

- collection source: `collection:<transaction_id>`;
- EIR accrual source: `eir_accrual:collection:<transaction_id>`; and
- sequence: `regular_accounting_sequence:collection:<transaction_id>`.

The accrual and collection must have the same transaction UUID, collection /
posting date, and recognized EIR amount. A positive EIR amount produces order 1
`eir_accrual` and order 2 `collection`. A zero-cent EIR boundary produces only
order 1 `collection`, because no accrual journal is required.

## All-or-none safety contract

`regular_accounting_sequence_preview_ready` is returned only when:

- both source previews explicitly remain `posting_eligible=false`;
- the collection preview is ready, balanced, uses the protected Regular account
  keys, and reconciles exactly to accepted cash;
- a positive EIR preview is ready, balanced, belongs wholly to one open fiscal
  period, and reconciles exactly to Dr accrued interest / Cr Regular interest
  income; or
- a zero EIR preview explicitly reports `no_eir_accrual_required`, has no lines,
  and reconciles to zero.

Any inconsistent identity, date, amount, line set, balance, period state, or
posting flag returns `regular_accounting_sequence_preview_blocked` with an empty
`ordered_entries` array. An underlying blocker is retained as `blocker_code` so
Management can see why the whole sequence stayed unavailable.

In particular, Stage 5D.7's
`fiscal_period_split_allocation_preview_ready` remains blocked from the sequence.
Its exact daily and deterministically allocated per-period evidence may be
inspected in the underlying EIR preview, but the sequence does not treat evidence
as journal lines and never exposes a partial collection sequence.

## Explicit exclusions

Stage 5D.6 changes none of the following:

- no journal draft or posting endpoint;
- no automatic source posting;
- no lending source write or collection behavior change;
- no Default, ECL, account 1190, 7x7, tax, or remittance policy change;
- no cross-period journal-line generation or posting; and
- no UI or database migration.

