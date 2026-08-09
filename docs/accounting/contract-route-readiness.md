# Stage 5E.4.5 — Collector contractual schedule readiness

## Purpose

Expose verified contractual schedule readiness to collectors without enabling or changing any live loan.

This stage is read-only. It does not create schedules, register contracts, allocate payments, change balances, write Default/Non-default, calculate ECL, populate account 1190, or post to the General Ledger.

## Route fields

The collector route now returns structured contract information for each active loan:

- whether contractual mobile allocation is enabled;
- whether the active schedule has a Stage 5E.4.3 verification registration;
- DPD data readiness status;
- payment frequency, contract reference, schedule version, and grace days;
- whether the operational balance equals the unpaid contractual schedule;
- whether all protected schedule/accounting readiness gates pass;
- DPD when the contractual dataset is ready;
- today's contractual scheduled amount and remaining unpaid amount;
- whether today's contractual installment is already fully covered;
- the next unpaid contractual due date and amount; and
- a collector-facing readiness message.

The same fields are preserved in the Flutter route model and offline route cache for display continuity.

## Pay-button safety

Existing legacy mobile collection behavior remains unchanged while `mobile_contract_schedule_allocation_enabled` is absent or false.

If Management explicitly enables contractual allocation in the future, the collector Pay action becomes available only when the same protected readiness conditions required by the Stage 5E.4.4 posting gate are satisfied. If the gate is incomplete, the route disables payment entry and explains the missing requirement before the collector attempts to submit.

## Collector guidance

The existing expanded loan details already display `collection_message`, so no new collector workflow is introduced in this stage. The message can now explain, as applicable:

- signed-contract schedule still required;
- Management verification still required;
- exact installments missing;
- prior payment allocation reconciliation required;
- operational/contractual balance mismatch;
- contract schedule ready but mobile contractual allocation not enabled;
- today's scheduled amount;
- today already covered by advance;
- next unpaid contractual installment; and
- contractual DPD when available.

## Safety boundary

At the live baseline established by Stage 5E.4.3, all seven current loans still have no verified contractual schedule. Therefore deploying this route-readiness code does not activate contractual collection or modify those loans.

A later controlled activation must still verify a real signed contract, reconcile the operational balance with the unpaid contractual schedule, and explicitly enable the feature only after the collector UI behavior has been reviewed.
