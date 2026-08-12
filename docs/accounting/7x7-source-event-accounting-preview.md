# 7x7 source-event accounting preview and identity

## Master checklist scope

This is the first protected sub-slice of the remaining Master Issue #296 item:

> Add protected 7x7 preview/identity/draft/posting/reversal and regression parity before enabling 7x7 accounting.

This slice is deliberately **read-only**. The parent checklist item remains incomplete until protected draft, posting, reversal and final source/ledger reconciliation are proven.

## Source-event identity

A normal 7x7 collection accounting source event is one active, non-voided PostgreSQL `lending.collection_transactions` row with lowercase `entry_type` `payment` or `advance` and a positive amount.

The deterministic source event key is:

`collection:<collection_transaction_uuid>`

`pass` has no accounting cash event. Voided payment/advance rows are excluded from the normal forward preview. A future protected accounting reversal must reverse exact protected journal history; this layer does not fabricate a reversal transaction.

Desktop has one effective payment per loan/calendar date. If PostgreSQL contains more than one active positive payment/advance for the same loan/date, the accounting path fails closed as `same_day_multiple_financial_source_events`; it does not use timestamps, device sequence or UUID order as an invented financial chronology.

Cash on or before the 0063 initial-anchor release date also fails closed because this slice has no authoritative intraday ordering between initial recognition and collection.

## Accounting EIR roll-forward

The accounting preview starts from the immutable 0063 evidence-backed initial gross carrying amount and authoritative original daily EIR.

For each valid source cash date, it:

1. accrues effective interest on opening gross carrying for elapsed days;
2. adds that accrual to the existing accrued-EIR component;
3. applies cash first to accrued accounting EIR interest;
4. applies the remaining cash to the 7x7 loan carrying component;
5. proves closing gross carrying equals closing accrued-EIR plus closing 7x7-loan component.

The operational PHP 7-per-PHP 1,000 rule is never used in this accounting calculation.

## Desktop regression parity

A separate read-only parity function reproduces the protected Desktop `allocate_x7_payments` rule:

- fixed daily interest from the recorded/original principal;
- every started PHP 1,000 uses the loan type's `daily_interest_per_1000`;
- the first operational gap starts from `payment_start - 1 day`;
- fixed-interest arrears are cleared first;
- remaining cash reduces operational principal;
- operational principal never changes the fixed daily-interest basis during the loan cycle.

The parity view compares that operational allocation with accounting EIR allocation event by event. A difference is evidence that the two measurement systems are distinct; it is **not** an error and never causes operational allocation to substitute for accounting.

## Read-only journal coordinates

When an event has a valid accounting measurement preview and exactly one open fiscal period, the coordinate preview uses existing active posting accounts:

- EIR accrual: **Dr 1120 Accrued Interest Receivable / Cr 4010 Interest Income - 7x7**
- cash collection: **Dr 1020 Cash - Collector Custody**
- cash allocation credits: **Cr 1120 Accrued Interest Receivable** for accounting EIR interest received and **Cr 1110 Loans Receivable - 7x7** for the remaining accounting carrying component received.

These are coordinates only. No journal entry or journal line is created.

## Fail-closed boundary

This slice keeps all of the following disabled:

- authoritative current gross carrying amount;
- Management journal draft;
- journal-line creation;
- posting or reversal;
- automatic source posting.

`authoritative_current_gross_carrying_amount=NULL`, `authoritative_current_carrying_amount_ready=false`, `journal_draft_enabled=false`, `journal_lines_enabled=false`, and `automatic_source_posting=false`.

The next sub-slice may build a stale-safe Management-confirmed draft only from exact event review tokens and the protected coordinate preview. Current carrying must not become authoritative until protected posting and exact source/ledger reconciliation are complete.
