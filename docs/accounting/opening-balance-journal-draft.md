# Protected opening-balance journal draft

This stage adds a controlled bridge from the reviewed opening-balance cutover workbook to the General Ledger **without posting anything**.

## Preparation gate

Management may prepare one journal draft only when the workbook is `review_ready`. The protected database function rechecks that every workbook line remains explicitly verified with evidence and an explicit amount, debit equals credit, the P&L migration policy is confirmed, the cutover date remains in an open fiscal period, active loan cutover sources are not blocked, and every nonzero journal account remains active and posting-enabled.

The workbook row is locked before the existing preparation is checked, making repeat/concurrent requests idempotent. The journal uses `source_type=opening_balance` and `source_event_key=opening_balance:<workbook_id>`.

## Draft protection

The generated journal is a system draft. General Journal cannot edit, cancel, delete, or post it. Its lines and preparation link are immutable. A prepared workbook cannot be reopened to Draft, preventing workbook/journal drift.

The Management Opening Balance Journal screen requires explicit confirmation and clearly reports that General Ledger posting and automatic source posting are disabled. Protected opening-balance drafts are hidden from normal General Journal actions; a future posted opening-balance entry may still appear in journal history.

## Deployment safety

Migration `0037_add_opening_balance_journal_draft.sql` installs only permission, table, functions, triggers, and a read-only status view. It never calls the preparation function.

The main-only guarded installer compares loans, collection transactions, journal entries/lines, workbook state, historical ECL labels, and DPD/default/ECL readiness before and after installation. A pristine installation must produce zero preparation rows and zero opening-balance journals.

## Explicitly not enabled

- opening-balance posting
- automatic lending/source posting
- ECL measurement or account 1190 population
- default classification
- loan/payment/remittance mutation
- fiscal-period closing

A separate later stage must implement and validate protected posting before any opening-balance draft can enter the posted General Ledger.
