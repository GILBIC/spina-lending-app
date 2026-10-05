# Treasury application accounting: first supported family

Migration 0146 recognizes a reviewed application of money whose original receipt
has already been posted by 0142. It supports one active application containing
exactly one positive 7x7 payment or advance, with its entire amount allocated to
one loan. Applying money operationally does not create an accounting journal.

The existing signed-contract schedule, classification decision, initial carrying
anchor and `preview_seven_by_seven_source_event_accounting` remain the EIR
measurement authority. The adapter uses their existing journal coordinate
preview. It replaces that preview's collector cash debit with a debit to 2200
Unapplied Borrower Funds; it preserves the derived accrued interest, interest
income and principal coordinates. The application journal contains no cash
account. The original verified receipt remains the single recognition of cash.

## Admission and review

The original receipt needs an exact immutable 0142 posting audit, compatible book
identity, no correction revision, and no refund. The application must reconcile
to the receipt's current operational applied amount and identify an exact retained
collection with Treasury receipt funding. The collection's amount and allocated
amount must equal the application amount, with zero unallocated amount.

Both ends of the EIR interval must be within one open fiscal period. Posted
loan-attributed 1110 and 1120 balances must equal the EIR engine's opening
components exactly. Every previous positive loan collection needs an exact
posted protected legacy or application audit. A later loan journal blocks a
backdated application until a correction workflow exists. An unposted prior
collection cannot be silently incorporated into the current journal.

The borrower's posted 2200 control balance must equal the retained receipt
credits less prior application debits as of the application date. Unregistered
manual effects in that borrower control require reconciliation, even when they
offset to zero. The complete control ledger evidence is pinned in the review.
1110 and 1120 must retain their asset/debit roles and 4010 its income/credit role,
matching the existing protected 7x7 posting semantics.

Initial loan carrying amounts therefore require retained posted evidence with
loan attribution. The existing manual journal constructor does not retain loan
or client IDs passed inside its line JSON. Its current form alone cannot provide
this admission evidence. The tests create an explicitly attributed synthetic
draft opening before its protected post; migration 0146 creates no opening
journals, real balances, wallet mappings or book identity.

Review produces a digest of the exact source, receipt cash proof, original
liability mapping, current receipt version, protected EIR measurement, all journal
coordinates and prior ledger evidence. Preparation stores this immutable review
and an opaque confirmation token, without creating a GL draft. Posting requires
the same actor, digest and token, rechecks current evidence, and atomically posts
the journal with its audit using the existing generic posting engine. A matching
retry returns the original journal. Different confirmations or stale evidence
cannot create another posting.

The backend checks the current registered device, active Management membership,
`accounting.journal.manage`, current Treasury view permission and explicit private
access to the source account. It verifies retained private receipt file bytes on
new review, preparation and posting. An exact completed retry can return the
retained audit even if the file later becomes unavailable. SQL tables and entry
points are private and do not grant access to browser or public roles.

## Corrections and deferred families

`accounting.treasury_application_posting_status` distinguishes exact historical
posted evidence from `correction_pending`, which compares the retained source and
EIR origin with the current origin. Later cash evidence can still be appended.
Changes to the retained GL account identity, code, system key, type, normal
balance or posting role also require correction review. A later display-name
change or account retirement preserves historical posting proof.
If earlier-dated evidence changes the EIR sequence, the earlier posted audit
remains visible and correction is required. An exact posting retry does not
re-recognize cash or recalculate that historical journal.

Destructive reversal or financial edits of an accounted application or its own
collection are rejected until a protected accounting correction adapter exists.
The generic manual reversal path cannot reverse these system journals. This
restriction does not suppress new cash receipts or new collection inserts.

Regular loans, multiple-transaction applications, extra-principal adjustments,
penalties, unallocated amounts, refunds, corrected receipts, reversals,
cross-period EIR recognition, and unsupported or stale contract/classification
evidence remain explicit blockers. The existing 0137 prohibition on posting a
Treasury-funded collection through a collector cash source key remains intact.
0146 does not relabel a Treasury source or loosen the 0139 accounting controls.

The adapter uses READ COMMITTED and locks the wallet, retained sources, fiscal
period, chart and ledger while preparing or posting. Contending protected writers
may require a retry; a deadlock or serialization failure rolls back and is
reported as a conflict. This first adapter is deliberately conservative about
admission when prior accounting needs reconciliation.

## Integration contract

Register `create_treasury_application_accounting_router()` from
`treasury_application_accounting_api.py`. Both web and mobile prefixes expose:

- `GET /management/financial-accounting/treasury/applications/{id}/review`
- `POST /management/financial-accounting/treasury/applications/{id}/prepare`
  with `source_digest` and `request_id`.
- `GET /management/financial-accounting/treasury/application-preparations/{id}`
- `POST /management/financial-accounting/treasury/application-preparations/{id}/post`
  with `source_digest`, `confirmation_token` and strict boolean `confirm: true`.

Review returns exact decimal strings. Preparation and its GET return
`{preparation, posting}`; posting adds `journal_entry_id`. The outer API envelope
is the existing `{data: ...}` response, with `Cache-Control: no-store`.
No endpoint accepts journal amounts, account selection, loan selection or actor
identity from the request body.

Public responses contain only the selected source identity, date and amount,
approved journal lines and chart display names, confirmation coordinates and
posting status. The full origin, EIR measurement inputs, evidence metadata, loan
ledger and borrower-wide liability reconciliation remain inside the private
database snapshot and backend revalidation. Access to one wallet never exposes
the other wallets' individual ledger evidence through this review API.

SQL entry points are `treasury_application_coordinates(UUID)`,
`prepare_treasury_application(UUID,TEXT,UUID,UUID)` and
`post_treasury_application(UUID,TEXT,TEXT,UUID)`. The immutable status view exposes
application, transaction, receipt, Treasury account, book, loan, journal and
preparation IDs, source digest, event, posting date, amount, `exact_posted` and
`correction_pending`. Close composition must require both exact proof and no
pending correction before clearing the matching application or collection. A
receipt's cash proof cannot clear its unapplied-funds or loan allocation duties.
