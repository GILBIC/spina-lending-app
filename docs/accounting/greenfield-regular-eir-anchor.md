# Stage 5D.25 — Greenfield Regular EIR anchor readiness

Status: **read-only accounting readiness foundation**. This stage creates no General Ledger journal, no opening-balance workbook, no lending source event, and no automatic source posting.

## Why this stage is required

SPINA V1 is being prepared for a new legal book set, so a legacy opening-balance cutover is not the normal source of the first Regular loan's amortized-cost state. The existing event-date EIR allocator was originally anchored to the protected cutover snapshot. That is safe for a converted portfolio, but it is not the correct greenfield anchor for a loan that was originated and posted inside SPINA after go-live.

A later Regular renewal cannot safely compare the old-loan settlement consideration with an operational balance or contractual payoff and call that the PFRS 9 carrying amount. The old loan first needs an accounting anchor derived from protected accounting history and exact contract cash flows.

Stage 5D.25 supplies that missing **greenfield initial anchor**. It does not yet calculate a renewal derecognition/modification result and does not create renewal journal coordinates.

## Required evidence

A row can become `greenfield_regular_eir_anchor_ready` only when all of these are true:

- the loan has an uncancelled Stage 5D.22 protected posted **pure new-Regular-loan disbursement**;
- the posted journal still matches the immutable Stage 5D.22 posting audit and the Stage 5D.19 release evidence;
- the initial posted amount is still exactly the protected pure-release principal amount;
- the debit remains `1100 Loans Receivable - Regular` and the credit remains the exact evidence-backed funding cash account;
- the current loan still matches the protected client, principal and release-date snapshots and remains `fixed_daily`;
- the loan has its original schedule version 1, with no superseded predecessor, registered from `signed_contract` evidence;
- the schedule effective date equals the protected release/posting date;
- every contractual installment is strictly after the release anchor;
- the verified contractual cash flows support a positive solved daily EIR; and
- there is no accepted PAYMENT/ADV before the release anchor and no same-day release cash whose ordering would have to be guessed.

The readiness view is `accounting.greenfield_regular_eir_anchor_readiness`.

## Initial carrying components

For this deliberately narrow pure-release path, the already-protected Stage 5D.22 journal is the initial ledger evidence:

- gross carrying amount: exact protected posted release amount;
- Regular loan component: same exact protected posted amount;
- accrued EIR component: zero at the release boundary.

This stage does not extend that rule to fees, deductions, settlement components, below-market terms, 7x7, renewal releases or restructures. Those cases remain blocked for separate accounting policy/evidence.

## EIR source

`accounting.solve_verified_contract_schedule_daily_eir(...)` solves the daily rate from the immutable verified signed-contract installments by discounting each exact contractual amount by elapsed calendar days from the protected release anchor.

The solver refuses to produce a rate when the schedule is not the registered original signed contract, contains nonfuture installments, has no installments, or does not produce contractual cash flows above the protected initial carrying amount.

For the normal Regular 120-day level-payment contract, the result is mathematically the same daily EIR as the existing level-payment solver when the verified signed schedule contains those same 120 daily cash flows. The source of evidence is stronger: the new path uses the actual registered contract schedule rather than reconstructing terms from generic loan-type assumptions.

## Same-day collection rule

PAYMENT or ADV recorded on the release date returns `same_day_collection_ordering_review`.

A date-only collection record does not prove whether cash was accepted before or after the exact release timestamp. Stage 5D.25 therefore refuses to guess the accounting order. A later stage may support same-day events only when authoritative timestamp/order evidence exists.

## API

Management can inspect readiness through:

`GET /api/v1/management/accounting/regular-greenfield-anchors/readiness`

The endpoint is read-only and requires `accounting.view`.

## Next accounting slice

After this anchor is proven, the next protected slice can connect post-release Regular EIR accrual/collection accounting to the greenfield anchor. Only after the old loan's ledger carrying amount is deterministically roll-forwardable to the renewal execution date should SPINA expose renewal accounting-treatment/carrying-amount coordinates.

## Explicitly excluded

Stage 5D.25 does **not**:

- create or post journal entries or lines;
- enable collection-journal integration from the greenfield anchor;
- enable automatic source posting;
- infer or create a signed-contract schedule;
- create an opening balance or legacy cutover state;
- calculate renewal derecognition/modification gain or loss;
- assume operational payoff equals accounting carrying amount;
- support renewal/restructure release EIR anchors;
- support fees, deductions, transaction-cost adjustments or other unsupported initial-recognition cases;
- support 7x7 accounting; or
- change ECL, tax, period-close or financial-statement policy.
