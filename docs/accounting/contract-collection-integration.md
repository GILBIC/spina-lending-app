# Stage 5E.4.4 — Contract-aware collection integration

## Purpose

Stage 5E.4.4 connects the existing official mobile collection transaction to the verified contractual schedule engine without changing any live loan automatically.

The integration is **dormant by default**. A loan type enters contractual allocation only when its settings explicitly contain:

```json
{
  "mobile_contract_schedule_allocation_enabled": true
}
```

No migration or deployment in this stage turns that setting on.

## Activation gates

Even when the setting is enabled, a collection is contract-aware only when all of the following are true:

1. the loan has one active contractual schedule;
2. that schedule has a Stage 5E.4.3 verification registration backed by signed-contract evidence;
3. `accounting.loan_contract_dpd_assessment.dpd_data_status = 'ready'`;
4. the operational remaining balance exactly equals the unpaid contractual schedule amount;
5. automatic Default remains off;
6. ECL remains excluded with no ECL amount; and
7. accounting `ready_to_post` remains false.

If any gate fails, SPINA rejects the contract-aware collection rather than guessing a schedule, allocation, balance, Default status, or accounting result.

The strict balance equality is intentional. Existing mobile `direct_remaining_balance` logic may represent a different balance basis from a signed contractual schedule. Contract allocation must not activate until those two sources are reconciled.

## Payment behavior

### Normal cash payment

A normal payment is allocated to the **oldest unpaid contractual installment**, not automatically to the calendar date on which the collector received the money.

This means that when today's installment was already covered by ADV, another payment received today moves to the next unpaid contractual installment.

Partial payments are allowed. A legacy `collection_covered_dates` row is added only after the touched contractual installment becomes fully paid. A partial allocation therefore does not falsely mark the entire due date as covered.

### ADV

ADV uses exact contractual installment dates only.

- The mobile request must provide explicit `covered_dates`.
- Every selected date must be a real unpaid contractual due date.
- The first/last ADV bounds must match the first/last selected contractual dates.
- The ADV amount must fully cover the remaining amount of all selected installments.
- SPINA does not expand the bounds into every calendar date between them.

A partial or irregular amount should use the normal/manual payment path so the allocator can apply it deterministically to unpaid installments.

### Unable to pay / PASS

PASS is valid only when an unpaid contractual installment is actually due on the collection date.

Therefore:

- an ADV-covered day does not create PASS;
- a weekly borrower does not create PASS on non-weekly due dates;
- a semi-monthly borrower does not create PASS on ordinary days;
- a monthly borrower does not create PASS on non-due days; and
- a day with no scheduled installment can simply have no cash received without being delinquent.

## Atomic transaction boundary

The existing official collection bridge still owns device checks, route checks, balance update, receipt, audit, idempotency, and collection transaction creation.

Contract-aware validation and installment allocation execute inside the **same PostgreSQL transaction**. If contractual allocation or any postcondition fails, the official collection write rolls back too.

The transaction records the schedule ID/version, contract reference, payment frequency, allocation plan, and fully covered contractual dates in protected transaction/audit details.

## Void and correction behavior

Installment allocation rows remain immutable evidence.

When an unremitted contract-aware collection is wrong:

1. void the receipt; then
2. record the corrected collection again.

The standard correction endpoint refuses direct edits of a collection that has contractual allocation or contract-validation metadata. This prevents amount/type/date edits from leaving stale schedule evidence.

Voiding a collection does not delete its historical allocation evidence. Instead, future allocation and DPD calculations ignore allocations whose collection transaction is voided. The voided receipt therefore stops consuming contractual installment capacity while preserving its audit history.

## Safety boundaries

Stage 5E.4.4 does not:

- enable the feature flag for any current live loan type;
- create or infer a contractual schedule;
- register a signed contract;
- backfill historical allocations;
- change the seven currently unverified live loans;
- automatically write Default or Non-default;
- calculate PD, LGD, EAD, or ECL;
- populate account 1190;
- create a General Ledger posting; or
- change the 30-day/90-day rebuttable-backstop policy.

## Next gate

After backend CI is green, the next controlled phase is to expose contractual schedule state in the collector route/mobile UI. Only after a real loan's signed contract is verified and its balance basis is reconciled should Management explicitly enable contract-aware collection for the applicable loan type or a narrower future per-loan activation control.
