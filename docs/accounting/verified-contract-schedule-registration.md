# Stage 5E.4.3 — Verified Contract Schedule Registration

## Purpose

Stage 5E.4.3 turns the Stage 5E.4.1/5E.4.2 contractual schedule engine into a controlled Management workflow for real loans.

The rule is explicit: **the signed borrower contract is the source of the payment schedule**. SPINA does not infer a live loan schedule from the old generic 120-day/daily convention.

## Workflow

1. Management enters the exact signed-contract terms.
2. SPINA generates a **preview only** showing every due date and installment amount.
3. Management compares the preview with the signed contract.
4. Registration requires an explicit confirmation plus a documentary evidence reference and verification note.
5. The exact schedule and an immutable verification record are stored together in one database transaction.

Supported frequencies remain:

- daily;
- weekly;
- semi-monthly such as 15th/30th;
- monthly;
- balloon;
- custom exact contractual dates.

## Permission

Registration requires `lending.contract_schedule.manage`, assigned to the Management role. Preview remains Management-only but is read-only.

## Evidence

Allowed evidence bases are:

- `signed_contract`;
- `signed_renewal_contract`;
- `signed_restructure_contract`.

The audit stores only an evidence reference and verification note. It does not store government-ID images, ID numbers, face-recognition images, or raw biometric data.

## Immutability

After registration:

- the verification record cannot be updated or deleted;
- installment rows cannot be updated or deleted;
- contractual schedule terms cannot be edited or deleted;
- the only allowed schedule mutation is `active -> superseded` for a later verified contract version.

A corrected contract is therefore represented by a new schedule version rather than rewriting history.

## Supersession safety

Stage 5E.4.3 refuses to supersede an active schedule that already has installment payment allocations. A later restructure/reallocation workflow must reconcile those allocations explicitly first. This prevents a new schedule from silently detaching historical cash from its original contractual basis.

## Still disabled

This stage does **not**:

- backfill any existing live loan;
- infer a schedule from loan type or legacy defaults;
- connect the collector posting path automatically;
- rewrite existing payment allocations;
- change `lending.loans.status`;
- write Default/Non-default labels;
- calculate PD, LGD, EAD, or ECL;
- populate account 1190;
- post a General Ledger journal.

## Test boundary

The PostgreSQL scenario test creates only synthetic users, clients, loans, schedules, and payments inside a transaction and ends with `ROLLBACK`. It verifies:

- explicit confirmation is mandatory;
- no schedule is written when confirmation is absent;
- signed-contract evidence is recorded;
- registration evidence is immutable;
- a payment still allocates through the Stage 5E.4.2 engine;
- a schedule with payment allocations cannot be superseded silently;
- DPD remains calculation-only and Default/ECL/GL controls remain off.

## Next gate

After branch CI passes, merge the code, then run a guarded live installation of migration `0035`. The existing live loans must remain unchanged until Management verifies their actual signed-contract terms one loan at a time.
