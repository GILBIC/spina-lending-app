# Verified receipt cash recognition

Migration 0142 implements the first Treasury source family. An explicitly reviewed,
original verified borrower receipt posts the full receipt amount as a debit to the
wallet's mapped cash account and a credit to **2200 Unapplied Borrower Funds**.
This recognizes cash custody and a borrower liability. It does not settle a loan,
recognize interest or fees, or establish income recognition under an EIR model.

An authorized Management user configures each wallet mapping with a retained
evidence reference and SHA-256 digest. Mapping versions are append-only, bound to
the database's immutable book identity, Treasury context, wallet ownership and
custodian, exact chart definitions, and authenticated actor. Physical cash maps to
1010 Cash – Office; GCash and bank wallets map to 1030 Cash – Bank / GCash.
The wallet remains separately identifiable in the immutable audit even when its
GL control account is shared. No wallet mapping or real business identity is
seeded. The migration only adds the deterministic 2200 chart definition, rejecting
a conflicting existing code or system key.

The receipt must have one matching principal movement, original classification
`borrower_receipt`, credit direction, zero fee, identical amount/context/account/
effective time, and retained recipient evidence. The original receipt must be
wholly unapplied and unrefunded, with no revisions, applications, transfer reuse
or other source links. The Treasury credit-event constraint already requires zero
fee. Other cash flows and fee recognition need separate reviewed adapters.

Review returns the exact source digest. Preparation retains that snapshot and a
confirmation token without creating a journal. Explicit confirmation rechecks
current active Management authority, registered device, global accounting and
Treasury permissions, and enabled private account access. It also verifies the
private evidence bytes against the retained digest and size before new posting.
Even a configured Treasury owner needs the explicit private grant for this adapter.
The original event's verifier is retained as evidence; it is distinct from the
current accounting actor's authority.

Posting locks the account, receipt/event and fiscal period, verifies the latest
mapping and exact source, and calls the existing protected GL posting engine in
the same transaction as the immutable audit. The date is the event's effective
date in Asia/Manila and must fall in an open period. Cash amounts stay NUMERIC in
PostgreSQL and Decimal/string at the backend boundary. The client cannot supply
journal amounts or posting accounts. Operational Treasury actions never invoke
this posting path automatically.

An exact committed retry returns the original journal after rechecking current
authorization and exact preparation/digest/token/actor. Later operational
application, mapping revisions, or missing retained files do not create a second
cash journal. A new posting still requires available verified evidence. Changed
requests conflict. Generic journal insertion, posting, cancellation and manual
reversal cannot replace the receipt adapter; a future protected correction adapter
is required to change recognized cash.

`accounting.treasury_receipt_posting_status` proves the exact posted two-line
journal, source key `treasury_receipt:<event UUID>`, preparation, book, borrower,
cash account, liability account and immutable audit. `exact_posted` is historical
cash recognition proof. `correction_pending` separately flags any later event
revision. Neither field proves loan application accounting. The 0137 collection
and 0139 loan-payout admission guards remain in force. Period close must continue
blocking unaccounted applications and unresolved corrections; this migration
does not alter period-close functions or source coverage itself.

The private API base is
`/api/v1/management/financial-accounting/treasury`, with the matching mobile alias:

- `GET/POST /accounts/{account_id}/cash-mapping`
- `GET /receipts/{receipt_id}/review?mapping_id=<UUID>`
- `POST /receipts/{receipt_id}/prepare`
- `GET /receipt-preparations/{preparation_id}`
- `POST /receipt-preparations/{preparation_id}/post`

The three source tables and status view are private. Browser/client/service roles
receive no table or function access. The backend uses its existing trusted database
connection; as with the existing journal engine, a database owner capable of
altering functions or disabling triggers remains an infrastructure trust boundary.
Private evidence retention, backups and isolated deployment credentials remain
operational requirements. These controls do not certify the contents of external
evidence or independently determine legal ownership.
