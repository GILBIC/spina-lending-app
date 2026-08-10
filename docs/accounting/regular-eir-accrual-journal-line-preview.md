# Read-only fiscal-period-aware Regular EIR accrual proposals

Status: **Stage 5D.7 backend-only accounting preview**. This slice creates no
migration, journal draft, posted General Ledger entry, lending mutation, or
automatic source posting.

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

The allocator rounds recognized EIR at the cash-event boundary using the existing
`ROUND_HALF_UP` convention. If an interval crosses fiscal periods, Stage 5D.7
applies the approved `regular_eir_period_split_v1` policy to the preserved exact
daily evidence. It exposes a reconciled allocation preview but still emits no
journal lines. Period-specific journal proposal and posting controls remain a
later protected stage.

If the allocator recognizes zero cents at a boundary, the result is
`no_eir_accrual_required`; no zero-value journal is proposed.

## Cross-period split evidence

When an interval crosses fiscal periods, the allocator preserves the exact,
unrounded EIR calculated for every elapsed calendar day. The preview groups that
evidence by fiscal period and reports:

- the exact accrual dates and day count assigned to each period;
- the period's unrounded EIR amount;
- a four-decimal audit-display amount that never replaces the exact value;
- that period's independently rounded cent amount;
- its whole-cent floor and exact fractional-cent remainder;
- deterministic allocation rank and awarded residual cent;
- its final two-decimal allocated PHP amount;
- the total of the independently rounded periods and their pre-allocation
  residual; and
- the final allocated total and zero unallocated residual.

The policy starts each positive period at its whole-cent floor. It awards the
remaining cent or cents in this order:

1. largest fractional-cent remainder;
2. larger exact period amount;
3. earlier fiscal-period start date; and
4. stable fiscal-period UUID.

The output is chronological and independent of input order. A residual may be
positive or negative when compared with independently rounding each period, but
the final allocated period total must equal the already-recognized cash-boundary
EIR cent exactly. `fiscal_period_split_allocation_preview_ready` therefore
requires `period_allocation_reconciled=true` and `unallocated_residual=0.00`.

Four decimals are display-only. Exact `Decimal` evidence remains the calculation
basis, while final PHP ledger candidates remain two decimals. No sub-cent amount
is carried into a later event, and no separate rounding account is introduced.

If any affected fiscal period is `review` or `closed`, the result is
`fiscal_period_split_period_not_open`. If exact daily coverage, period coverage,
or target reconciliation cannot be proven, the preview fails closed. None of
these paths proposes journal lines or claims posting eligibility.

The daily evidence is internal calculation support. The API exposes only the
period aggregates needed for review; it does not expose or persist a new lending
or accounting source record.

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
