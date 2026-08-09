# Protected opening-balance journal posting

## Purpose

This stage permits Management to post the already prepared opening-balance journal to the General Ledger through one explicit protected workflow. It does not enable automatic source-event posting and it does not create or post any journal during migration deployment.

## Two separate Management decisions

1. **Prepare Draft** copies the fully reviewed opening-balance workbook into one immutable system-generated draft.
2. **Post to General Ledger** is a second action with a separate confirmation and separate permission (`accounting.opening_balance.post`).

Preparing a draft never implies approval to post it.

## Posting revalidation

Immediately before posting, the database locks and revalidates the workbook, prepared journal, and fiscal period. Posting is blocked unless all of the following remain true:

- the workbook is still `review_ready`;
- the P&L cutover policy remains confirmed;
- every workbook line remains explicitly verified with an amount and evidence note;
- the workbook is exactly balanced to the cent and has at least two nonzero lines;
- every nonzero account remains an active posting account;
- the protected journal identity still matches the workbook (`source_type`, source reference, and deterministic source event key);
- the journal posting date still equals the approved cutover date;
- the journal line count, debit/credit totals, account IDs, and per-account amounts exactly match the reviewed workbook in both directions;
- the cutover fiscal period remains open;
- there are no active blocked loan cutover sources.

### Source-readiness serialization

Before the final source-readiness query, the protected posting transaction acquires `SHARE` table locks on `lending.loans`, `lending.loan_types`, and `lending.loan_collection_state` and holds them through commit. Normal collection/correction writers require conflicting write locks on these tables. Therefore:

- if a source-changing writer commits first, the posting transaction sees that new state before deciding whether it can post;
- if the posting transaction obtains the source locks first, the writer must wait until the opening journal has committed or rolled back.

This prevents a concurrent collection void/correction from changing the cutover source-readiness state between the final check and the irreversible journal commit.

### Exact confirmation values

The API requires the journal ID and exact debit/credit totals that Management just reviewed. The backend exposes PostgreSQL decimal totals as strings and the mobile client preserves those strings without converting them to IEEE-754 floating-point values for confirmation or display. The POST request sends the exact decimal strings back to the API, which parses them as `Decimal` and compares them exactly. A changed journal ID or total is rejected as stale and must be refreshed.

## Ledger controls

The protected function does not implement a parallel ledger. It calls the existing `accounting.post_journal_entry` function after enabling the opening-balance-specific posting guard for that transaction. The normal General Journal posting route remains unable to post an opening-balance draft.

A successful post:

- receives the standard immutable `JE-YYYYMM-########` entry number;
- records the posting user/time on the journal;
- appends a `posted` journal event identifying `protected_posting=true` and `automatic_source_posting=false`;
- inserts one immutable opening-balance posting audit row;
- is idempotent: repeating the protected request returns the same posted entry and does not create another posting record/event.

After posting, corrections must use a controlled reversal rather than editing or deleting the posted entry. The UI only reports the opening balance as Posted when the protected posting audit exists.

## Deployment safety

Migration `0038_add_protected_opening_balance_journal_posting.sql` installs only permission/schema/function/view/trigger controls. The guarded live installer compares loans, collection transactions, journal counts/statuses/numbers/lines, workbook/preparation state, historical ECL review labels, and DPD/default/ECL readiness before and after installation.

On first installation it must prove:

- zero opening-balance posting audit rows were created;
- no draft journal changed to posted;
- no entry number was generated;
- no loan or collection transaction changed;
- no workbook or prepared draft changed;
- no Default/ECL readiness state changed.

## Explicitly still disabled

- automatic source-event posting;
- automatic loan/default classification;
- automatic ECL measurement or account 1190 population;
- automatic fiscal-period closing;
- automatic opening-balance preparation or posting.
