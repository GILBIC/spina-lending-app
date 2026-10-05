# Regular Treasury application: first original cash boundary

Migration 0155 implements the next bounded extension of 0146. The first actual
operational fixtures have demonstrated the missing behavior against the prior
schema. The new SQL is awaiting its PostgreSQL verification; the product-policy
projection has passed its unit tests. This document does not claim that all
Regular collections are supported.

## Supported source

Start with one original fixed-daily Regular loan, its exact protected legacy
greenfield disbursement, and its verified first signed contractual schedule.
The first positive cash event is one active operational Treasury application,
containing one fully allocated payment for that loan. The application's exact
receipt must already have0142 cash/unapplied-liability proof. Actual receipt and
application commands continue to record operational evidence without automatic
GL posting.

Application and receipt must have the same borrower, wallet, context and book;
the original verified receipt cannot be corrected, refunded or reused under a
different source. The application amount, protected collection amount, applied
amount and installment allocations must reconcile, with zero unallocated money.
Retain the active source, full original collection order, void/reversal evidence,
exact receipt proof and mapping, signed schedule and disbursement proof. Never
change funding_source to Collector cash to make a legacy preview admit it.

The application must fall after release and no later than original maturity.
When release and application fall in different fiscal periods, exact contiguous
0153 assessments must cover the original no-cash prefix through the day before
the application's open period. An unrecognized elapsed interval or changed
assessment blocks posting. No prefix is necessary when the release and
application belong to the same open period.

## Measurement and journal

The existing `allocate_event_date_eir_cash` function specifies Regular ordering,
cash allocation and cent residuals. Its first-event specialization compounds the
original initial carrying value at the original daily EIR through application
date, rounds cumulative interest once at that cash boundary, and allocates cash
first to accrued interest and then to1100 principal. SQL must independently
recompute this restricted formula from protected origin coordinates; it accepts
no user-provided rate, amount, split or carrying balance. Behavioral tests compare
it with the existing Python allocator and an independent Decimal calculation.

Fiscal assessments are recognition claims, not new economic carrying anchors.
The unrecognized interest is the original rounded cumulative interest at the
cash boundary less the cumulative interest already recognized by exact0153
claims. Never compound forward from the rounded1120 fiscal closing balance.
Only a real cash boundary applies the allocator's existing cent reset convention.

One atomic native application journal contains these nonzero coordinates:

- Dr2200 Unapplied Borrower Funds for the full applied receipt amount.
- Dr1120 / Cr4000 for unrecognized interest through application date.
- Cr1120 for the allocator's cash-to-accrued-interest amount.
- Cr1100 for its cash-to-loan-component amount.

The journal contains no1010/1020/1030 cash line. It does not alter1190 allowance;
that remains the exact previously recognized amount until a supported subsequent
assessment. Before posting, loan-attributed1100/1110/1120/1190 balances and every
contributing source identity must match origin plus retained prefix claims.
Equal-and-opposite unknown journals cannot be accepted merely because net sums
match. Borrower2200 must match retained receipt credits less exact application
consumption across all authorized database evidence; private cross-wallet detail
stays outside the public response.

## Extension and retained proof

Prefer the existing0146 preparation, token, audit and source-key machinery.
Add Regular-specific origin/coordinates helpers and dispatch the existing
`treasury_application_coordinates(UUID)` and origin by actual protected product.
Keep the7x7 implementation available under an explicit private alias. Existing
posted audits and completed exact retries remain immutable. A previously prepared
but unposted review whose versioned coordinates change must be reviewed again.

The153 generic journal guard must admit only an exact prepared Regular native
application with the same retained prefix claims. It must not disable its legacy
collection/manual guard or accept a source-type string alone. The existing0146
source guard, exact journal lines and deferred protected audit remain required.
0137's prohibition on Treasury money entering a Collector cash source stays
unchanged. New preparation/post operations retain READ COMMITTED source locks,
current Management/device/private-wallet authority, private evidence bytes,
same-actor confirmation, atomic journal/audit and exact completed retries.

Public review/preparation projection must include an explicit retained pair:
`product_model=fixed_daily` and
`accounting_policy_version=treasury_regular_original_first_cash_v1`.
The existing 7x7 path uses `product_model=seven_by_seven` with
`accounting_policy_version=treasury_seven_by_seven_application_v1`. Historical
0146 snapshots retain their original bytes; the public projection supplies this
known pair for their original 7x7-only policy. Portal and Flutter
validate each product's complete coordinates, including its1100/4000 or1110/4010
roles. Combining all allowable account codes into one whitelist is insufficient.
Raw origin, ledger, borrower aggregate and prefix snapshots stay private.

Posting status proves the exact native application and current origin semantics;
only that proof can clear its matching raw collection/application blockers.
Later genuine cash evidence remains appendable. Changed earlier evidence makes
the retained proof require correction review. Generic reversal or destructive
financial edits cannot erase the original accounting proof.

## Explicit later extensions

This first slice rejects previous positive cash events, including voided or
reversed history; cutover anchors; renewals/modifications; maturity extensions;
multiple-transaction applications; refunds/corrections; and mixed products.
Those rows remain visible to source completeness. It does not claim later
post-application period assessments are supported by153's no-cash policy.

A later cash transaction alone is excluded from an earlier application origin
and does not make that audit stale. Earlier cash appended after posting does
require correction review. This first policy also retains the current original
maturity and renewal evidence: a subsequent renewal, maturity change or new
contract version requires an explicit historical transition adapter and may
make the earlier proof correction-pending. Such operational facts remain
appendable; the first policy does not silently reinterpret the original terms.

Next, normalize native0154 borrower-completion proof into an original Regular
anchor only after its exact debit/completion audits, canonical original
disbursement coordinates, verified signed schedule and1100/1050 carrying match
are established. A source debit,1050 balance or loan metadata alone is not a
release anchor. Do not fabricate a legacy cash credit or weaken0139. Extend
153's original-anchor selection consciously for this same exact origin.

Then extend the causal chain across multiple real cash boundaries, preserving
the Python allocator's cent convention at each cash boundary, active legacy
collection/reversal evidence and exact native/legacy GL claims. Fiscal prefixes
between those cash events must subtract already recognized interval interest
without introducing another economic reset. Dedicated reversal and correction
adapters remain required before destructive changes to an accounted source.

## Initial behavioral proof

Tests create an actual verified receipt and use the existing protected Treasury
allocation command for the first Regular payment. They require: unchanged wallet
movements before/after application accounting; exact receipt2200 consumption;
agreement with the existing allocator; no GL draft on prepare; exact retry;
the62.58-versus62.57 fiscal-prefix regression; rejection of an unrecognized prior
cash source; and rejection of a missing/changed prefix or carrying control.
Post-then-stale-source, authority, evidence loss, generic source-key forgery,
deferred audit, truncation and two-connection races follow once this source is
observably valid. Existing7x7 and153 suites must remain green.
