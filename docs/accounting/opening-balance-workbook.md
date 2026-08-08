# Stage 5C — Protected Opening Balance Workbook

Stage 5C converts the Stage 5B read-only cutover worksheet into a controlled Management workbook. It remains outside the General Ledger.

## Scope

- Management permission: `accounting.cutover.manage`.
- A workbook can be initialized only for a date inside an Open fiscal period and only when no active loan source is blocked.
- Initialization snapshots the 11 balance-sheet source-reference rows used by the Stage 5B cutover worksheet.
- Each line stores a proposed debit or credit, a verification status, and an evidence/reconciliation note.
- Verified lines require an explicit amount. Zero must be entered explicitly when the verified balance is zero.
- The P&L migration/conversion policy is confirmed separately with a policy note.
- Draft workbooks can move to Review ready only after all lines are verified, debit equals credit, the P&L policy is confirmed, the cutover date remains in an Open period, and no loan source is blocked.
- Review-ready workbooks are read-only until reopened to Draft.
- Workbook and line mutations must use protected database functions. Direct writes are rejected.
- Every workbook creation, line update, policy change, and status transition is audited. Audit rows are immutable.

## Explicitly disabled

Stage 5C does **not** create or post an opening journal. `ready_to_post`, opening-balance posting, and automatic source posting remain disabled. Loan EIR schedules, ECL measurement/posting, tax posting, and final financial statements remain later controlled stages.

The first controlled live test cutover date is `2026-08-08`. Initializing that workbook is a source snapshot only; it must not be treated as authorization to invent or post opening balances.
