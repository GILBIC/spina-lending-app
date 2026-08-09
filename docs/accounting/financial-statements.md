# Financial Statements from the posted General Ledger

Status: **Accounting completion — read-only reporting slice**.

This stage adds Management financial statements derived only from posted General Ledger entries. It does not create, edit, post, reverse, or close any journal and it does not change operational lending records.

## Statement of Profit or Loss

For a selected fiscal period, the statement reports posted income and expense activity belonging to that period.

- Draft journals are excluded.
- Income accounts are presented as credit less debit.
- Expense accounts are presented as debit less credit.
- Net income is total income less total expenses.
- A future formal `period_close` journal is excluded from the selected-period Profit or Loss report so closing income and expense balances to retained earnings does not erase the historical period result.

## Statement of Financial Position

The statement is measured as of the selected fiscal period end date using cumulative posted General Ledger balances through that date.

- Asset accounts are presented as debit less credit.
- Liability and equity accounts are presented as credit less debit.
- Contra-asset account `1190 Allowance for Expected Credit Loss` therefore appears as a negative asset balance when it eventually contains a posted credit balance.
- Until formal period-closing journals are implemented, cumulative posted income less cumulative posted expenses is shown separately as **Unclosed earnings to date** and included in total equity so the accounting equation remains visible.
- After formal closing entries are later posted, the cumulative income/expense balances reduce and the corresponding amount moves into recorded equity/retained earnings through the General Ledger.

## Source and safety boundary

The only source is `accounting.journal_entries` with `status = 'posted'` and their protected journal lines. Operational loan balances, collection screens, cutover measurements, and workbook proposals are not mixed directly into these statements.

This slice does **not**:

- post the protected opening-balance workbook;
- enable automatic lending or collection accounting;
- post EIR accruals;
- quantify or post ECL account 1190;
- calculate or post tax entries;
- create formal period-closing entries; or
- alter any loan, payment, collection, remittance, journal, or fiscal-period record.

Those remain separate controlled accounting completion stages. This reporting layer can therefore be validated independently without changing the live accounting ledger.