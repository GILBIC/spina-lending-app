# SPINA General Journal and Trial Balance

Status: **Stage 4 manual General Journal foundation**.

This stage enables controlled manual accounting journals and a Trial Balance based only on posted journal entries. It does not enable automatic loan, collection, remittance, EIR, ECL, tax, or opening-balance posting.

## Safety model

- A journal draft can only be created inside an **Open** fiscal period.
- A draft must contain at least two lines and must already balance before it can be saved.
- Only active posting accounts from the Chart of Accounts may be used.
- Posting requires an explicit confirmation.
- Posted entries and posted lines are immutable.
- Corrections to posted entries use reversal drafts; the original entry remains unchanged.
- A cancelled manual draft is removed from the working journal only after its lines and prior journal events are archived in an immutable cancellation-audit table.
- Closed or Review periods cannot receive journal postings.
- Fiscal-period closing continues to be blocked while draft journals remain.

## Trial Balance

The Trial Balance is computed only from **posted** journal entries. Drafts do not affect account balances. It can be viewed for all posted journals or filtered to one accounting period.

## Pre-cutover August reset

The August 2026 period was closed during the Stage 3 close-confirmation test while it still had zero journals. Migration `0023_reset_empty_august_2026_pre_cutover_period.sql` performs a one-time narrow reset only when that exact period is closed and contains zero journals. It archives the original period state and status-event history, removes the empty test period, and creates a replacement August 2026 period as Open.

The reset is a pre-cutover testing exception. It must not be used to reopen periods after real journal activity begins.

## Stage boundary

Still disabled after Stage 4:

- automatic Regular loan journal posting;
- automatic 7x7/EMER journal posting;
- accounting cutover/opening balances;
- PFRS effective-interest schedules;
- expected-credit-loss calculations and postings;
- tax posting and book-to-tax reconciliation; and
- final financial statements.
