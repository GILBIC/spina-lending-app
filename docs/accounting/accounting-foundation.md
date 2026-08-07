# SPINA accounting foundation

Status: **Stage 2 foundation**. This creates accounting structure and controls only. It does not convert existing lending records into journals and does not enable automatic posting.

## Chart of Accounts

The `accounting.accounts` table contains stable system keys for the initial SPINA chart, including separate cash custody, Regular and 7x7 receivables, accrued interest, ECL allowance, interest-income, liability, equity, and operating-expense accounts.

Account IDs are database-generated. Posting logic must use stable `system_key` values rather than hard-coded UUIDs.

## Fiscal periods

`accounting.fiscal_periods` supports `open`, `review`, and `closed` states. Periods cannot overlap. Once a period is closed, it is immutable. Stage 2 deliberately creates **no fiscal period automatically**; period configuration belongs to the controlled cutover workflow.

## General Journal

`accounting.journal_entries` and `accounting.journal_lines` provide the double-entry foundation.

A journal may be edited only while it is a draft. The database posting function refuses to post unless:

- the period is open;
- the posting date falls inside the period;
- there are at least two lines;
- every account is active and posting-enabled; and
- total debit equals total credit and is greater than zero.

Posted journal entries and their lines are immutable.

## Source-event idempotency

`source_event_key` is unique. Future automated posting must derive a deterministic source-event key from the underlying SPINA event so the same payment, release, remittance, correction, void, accrual, or other source event cannot be posted twice.

## Reversals

Posted entries are never edited or deleted to correct accounting. `accounting.create_reversal_draft(...)` creates a new draft with debit and credit sides reversed and permanently links it to the original posted journal. The reversal must then pass the normal posting controls.

## Cutover safety

Stage 2 does **not**:

- create an accounting period;
- create an opening-balance journal;
- post existing loans or collections;
- calculate Regular or 7x7 EIR schedules;
- calculate ECL;
- write off loans;
- close a fiscal period; or
- generate final financial statements.

The live lending subsystem remains the operational source of truth until a later, explicitly reviewed accounting cutover is completed.
