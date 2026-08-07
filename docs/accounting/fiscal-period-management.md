# SPINA fiscal period management

Status: **Stage 3 fiscal-period controls**. This stage manages accounting calendar periods only. It does not enable General Journal posting, automatic loan accounting, opening balances, EIR schedules, ECL, or financial statements.

## Period lifecycle

A new fiscal period is created as **Open**.

Supported transitions are:

- Open → Review
- Review → Open
- Review → Closed

A period cannot move directly from Open to Closed. Closed periods are immutable and cannot be reopened.

## Close control

The mobile Management flow requires an explicit close confirmation. The backend also requires `confirm_close=true` before it will attempt a close.

At the database layer, a period cannot close while draft journal entries remain in that period. This control is already active even though General Journal posting is not yet exposed in the application.

## Non-overlap protection

Fiscal periods cannot overlap. Stage 3 retains the trigger-level check from the accounting foundation and adds a database exclusion constraint so concurrent period creation cannot bypass the non-overlap rule.

## Authorization and audit trail

Management users require the `accounting.period.manage` permission to create or transition periods.

`accounting.fiscal_period_events` permanently records period creation and status transitions with the acting user and timestamp.

## Stage boundary

Stage 3 does **not**:

- create accounting periods automatically;
- create opening balances;
- create, edit, or post journal entries from the mobile application;
- convert current lending balances into accounting balances;
- calculate Regular or 7x7 effective-interest schedules;
- calculate ECL or write-offs; or
- produce a Trial Balance or final financial statements.

The first live period should therefore be created only as a controlled accounting-calendar test until the later cutover and journal-posting stages are approved.
