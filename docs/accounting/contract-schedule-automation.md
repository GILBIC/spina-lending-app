# Stage 5E.4.2 — Contract Schedule Generation & Payment Allocation

## Purpose

Stage 5E.4.2 builds the reusable live-loan automation layer on top of the Stage 5E.4.1 contractual DPD foundation.

The historical outcome-review screen remains primarily an ECL-calibration tool. This stage is different: it creates reusable contract-driven logic for current and future SPINA loans.

## Contract-driven schedule generation

The schedule generator accepts terms from the signed contract and produces exact installment dates and cent-exact amounts for:

- daily;
- weekly;
- semi-monthly, including schedules such as 15th/30th;
- monthly;
- balloon;
- custom explicit schedules.

The generator does not infer a schedule from a generic 120-day assumption. The caller must supply the signed-contract terms.

For semi-monthly and monthly schedules, month-end dates are clamped to the last valid calendar day. For example, a 15th/30th schedule produces February 15 and February 28/29 when the month has no 30th day.

## Automatic payment allocation

When no explicit contractual dates are selected, a payment is allocated to the oldest unpaid contractual installment and continues forward until the full transaction amount is applied.

This means:

- if today's installment was already paid in advance, another payment received today moves to the next unpaid contractual installment;
- a weekly loan advances to the next weekly contractual date, not the next calendar day;
- partial payments remain attached to the same contractual installment until it is fully covered;
- a payment cannot silently exceed the unpaid contractual schedule.

When explicit covered dates are supplied, every selected date must be an actual unpaid contractual due date. The allocator rejects non-contract dates and already-covered dates rather than guessing.

## Transactional service

`contract_schedule_service.py` provides two transaction-scoped operations:

1. `store_contract_schedule(...)` stores the signed-contract schedule and exact installment rows.
2. `allocate_collection_transaction(...)` locks an accepted collection transaction and applies it to contractual installments.

Re-running a fully allocated transaction is idempotent. A transaction with incomplete pre-existing allocations is blocked for review.

Renewals or restructures must explicitly supersede the previous schedule. The old schedule remains preserved as historical evidence.

## Test-first safety boundary

Stage 5E.4.2 is intentionally **not connected to the live collector posting path yet**.

The PostgreSQL test creates synthetic users, clients, loans, schedules, and collection transactions inside one transaction and ends with `ROLLBACK`. It verifies real database constraints and DPD behavior without changing production client data.

The test covers:

- schedule storage;
- duplicate active-schedule protection;
- automatic multi-installment allocation;
- payment received today when today's installment is already covered;
- idempotent allocation replay;
- DPD returning ready/0 after full contractual coverage;
- rejection of payment beyond the remaining contractual schedule.

Pure unit tests additionally cover daily, weekly, 15/30, monthly month-end, balloon, custom, cent rounding, partial payment, advance allocation, and invalid explicit dates.

## Still disabled

This stage does not yet:

- call the automation service from `PostgresCollectionPostingBridge`;
- alter existing live client schedules;
- backfill old loans automatically;
- write Default/Non-default outcomes;
- calculate PD, LGD, EAD, or ECL;
- populate account 1190;
- post a General Ledger journal.

## Next gate

After CI passes, the next safe gate is a guarded live installation of the Stage 5E.4.1 schema, followed by a feature-flagged connection of new/verified contract schedules to collection posting. Existing loans without verified contractual schedules must remain in `contract_schedule_required` rather than being guessed.
