# Stage 5E.4.1 — Contractual Schedule & DPD Foundation

## Purpose

SPINA must measure delinquency against the payment dates and amounts in the borrower's actual contract. A borrower on daily terms, weekly terms, semi-monthly terms, monthly terms, a balloon structure, or a custom schedule must not be measured using one generic 120-day daily assumption.

This stage adds the data foundation for contract-driven Days Past Due (DPD). It is intentionally read-only from an accounting-classification perspective: it does not write Default/Non-default labels, ECL, write-offs, or General Ledger journals.

## Contract is the primary schedule evidence

Each active schedule stores a `contract_reference`. The exact installment dates and amounts live in `lending.loan_contract_installments`.

Supported contractual payment frequencies:

- `daily`
- `weekly`
- `semi_monthly`
- `monthly`
- `balloon`
- `custom`

A schedule can also store a contractual grace period. DPD starts only after the contractual due date plus that stored grace period.

Renewals and restructures must create a new schedule version rather than erase the old contractual schedule. The signed contract remains the primary financial evidence. Government-ID and face/liveness verification can support borrower identity/consent in the later evidence viewer, but they are not themselves payment-schedule or default evidence.

## Exact payment application

DPD must not guess how cash was applied. `lending.loan_installment_payment_allocations` links a non-voided collection transaction to the contractual installment it paid.

Allowed allocation bases are:

- `exact_covered_date`
- `oldest_due_first`
- `contract_reference`
- `manual_review`

The database prevents an allocation from crossing to another loan and prevents total allocations from exceeding the collection transaction amount.

The later automatic allocator can use the contractual frequency and existing exact covered-date information where appropriate. Stage 5E.4.1 does not silently backfill payment allocations or reinterpret old ADV/PASS data.

## DPD readiness states

`accounting.loan_contract_dpd_assessment` returns one of:

- `contract_schedule_required` — no active signed-contract schedule is recorded.
- `contract_installments_required` — schedule header exists but exact contractual installments are missing.
- `payment_allocation_required` — eligible non-voided payment/advance cash is not fully allocated to installments.
- `ready` — DPD can be calculated from complete contractual schedule and payment application data.

When ready, DPD is measured from the earliest unpaid contractual due date after any contractual grace period.

## PFRS 9 backstop flags

The DPD assessment exposes:

- `thirty_day_sicr_backstop_reached`
- `ninety_day_default_backstop_reached`

These are policy/backstop flags only. They do not automatically write a credit classification in this stage. Any later automated policy engine must preserve documented rebuttal/override support and immutable evidence.

## Safety boundaries

Stage 5E.4.1 does **not**:

- infer historical schedules from generic product assumptions;
- mark any of the historical 919 reviewable episodes Default or Non-default;
- unblock the 73 source-review-required historical episodes;
- change `lending.loans.status`;
- calculate PD, LGD, EAD, or ECL;
- populate account 1190;
- create a write-off;
- create or post a General Ledger journal.

## Next implementation slice

After this foundation passes CI, the next safe slice is a controlled schedule authoring/generation and payment-allocation engine:

1. create schedules from the signed loan contract for daily/weekly/semi-monthly/monthly/balloon/custom terms;
2. automatically generate exact installment rows;
3. allocate accepted non-voided payments using the contract/payment-allocation policy;
4. expose DPD to Management;
5. only then connect the 30/90-day policy engine with controlled rebuttal/override evidence.
