# Read-only fiscal-period-aware Regular EIR accrual proposals

Status: **backend-only accounting preview**. This slice creates no migration,
journal draft, posted General Ledger entry, lending mutation, or automatic source
posting.

## Purpose

The event-date allocator reports the exact cent of effective interest recognized
before each supported Regular PAYMENT/ADV. This preview maps that proven amount
to balanced lines without creating an accounting record:

- debit 1120 `accrued_interest_receivable`;
- credit 4000 `interest_income_regular`.

Its deterministic source identity is
`eir_accrual:collection:<collection_transaction_uuid>`. The related collection
entry keeps its existing `collection:<collection_transaction_uuid>` identity and
must follow the accrual in any later protected posting workflow.

## Fiscal-period gate

The recognized EIR interval is `(prior cash boundary, current collection date]`.
Lines appear only when one **open** fiscal period covers every calendar day in
that interval.

The current allocator rounds recognized EIR at the cash-event boundary. If an
interval crosses fiscal periods, this preview returns
`fiscal_period_split_required` and no lines. It does not guess how to divide an
already-rounded boundary amount. A later policy must prove daily/period boundary
rounding before split-period proposals are allowed.

If the allocator recognizes zero cents at a boundary, the result is
`no_eir_accrual_required`; no zero-value journal is proposed.

## Protected gates

The proposal also requires:

- complete ready Regular EIR allocation;
- posted protected opening-balance journal;
- available and reconciled immutable per-loan cutover snapshot;
- complete post-cutover source history;
- active posting accounts 1120 and 4000;
- no existing EIR accrual draft/posted journal or reversal;
- no collection journal state that improperly precedes the required accrual; and
- a non-voided supported event.

Every result remains `posting_eligible=false`. No write endpoint, UI control,
draft, posting, Default/ECL/1190 behavior, 7x7 policy, tax entry, or remittance
accounting is added.
