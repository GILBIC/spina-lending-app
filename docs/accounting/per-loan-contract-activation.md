# Stage 5E.4.6A — Per-loan contractual collection activation schema

## Purpose

Create the audit foundation needed to activate contractual mobile allocation for exactly one loan at a time instead of enabling an entire loan type.

The current Stage 5E.4.4 integration still reads the legacy loan-type setting `mobile_contract_schedule_allocation_enabled`. Stage 5E.4.6A does **not** change that application behavior yet. It installs only the protected database layer so the later wiring change can be deployed against an already-live schema.

## New immutable activation event log

Migration `0036_add_per_loan_contract_collection_activation.sql` adds:

- Management permission `lending.contract_collection.activate`;
- `lending.loan_contract_collection_activation_events`;
- `lending.loan_contract_collection_activation_state` latest-state view;
- insert validation that requires the schedule to belong to the same loan;
- activation validation that requires the current active schedule and a Stage 5E.4.3 verified signed-contract registration; and
- an update/delete guard so activation history is append-only.

Each later Management action will append either an `activate` or `deactivate` event. Deactivation will not erase earlier activation evidence.

## Live-install safety

The guarded live installer must create:

- **0 activation events**; and
- **0 active contractual-collection loans**.

It also proves that installation leaves unchanged:

- lending loan count and statuses;
- collection transactions;
- contractual schedules;
- contractual installments;
- installment payment allocations;
- verified schedule registrations;
- DPD readiness and delinquency state;
- historical ECL outcome labels; and
- journal entries.

Automatic Default remains false, ECL remains excluded/NULL, and accounting `ready_to_post` remains false.

## Why the schema is installed before application wiring

A real pilot must not rely on a broad product-level flag. The safest sequence is:

1. install this empty per-loan activation schema live;
2. verify all live counts remain unchanged;
3. change the collection posting gate and collector route to read the per-loan activation state;
4. add the explicit Management preview/activate/deactivate workflow; and only then
5. verify one real signed contract and activate one loan as a controlled pilot.

This ordering avoids deploying application code that depends on a table that has not yet been installed.

## Safety boundary

Stage 5E.4.6A does not:

- activate any loan;
- change `mobile_contract_schedule_allocation_enabled`;
- create or infer a contractual schedule;
- register a signed contract;
- allocate any payment;
- change a balance or loan status;
- write Default or Non-default;
- calculate PD, LGD, EAD, or ECL;
- populate account 1190; or
- create a General Ledger entry.
