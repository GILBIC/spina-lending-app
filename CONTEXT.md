# SPINA Domain Context

This glossary defines stable business language across SPINA Desktop, Gilbic
Mobile, the website, FastAPI, PostgreSQL, GitHub planning, and project status. It
describes concepts, not current implementation details.

## People and access

### Management

A person entrusted with oversight, sensitive review, approval, final
authorization, and administration according to explicitly granted permissions.
Management membership does not by itself bypass maker-checker separation.

_Avoid:_ Owner as a universal technical superuser; Admin as its replacement.

### Employee

An office worker who performs authorized accounting, HR, payroll,
client-relationship, reporting, or remittance work. Employee capabilities are
separable and must be explicitly granted.

_Avoid:_ Encoder as a synonym; Staff as one all-access permission bundle.

### Collector

A field worker authorized to work only with assigned or explicitly delegated
routes, areas, clients, collections, custody, remittances, and field evidence.

### Client

A borrower who may use approved self-service workflows for their own account but
may not change official financial records.

### Permission

A server-defined capability granting one narrow action or read scope. A role is
a convenient grouping; authorization still evaluates active account,
permission, resource scope, and device state.

_Avoid:_ UI visibility as authorization; client-provided role metadata.

### Legacy access profile

One of the historical Desktop values `Admin`, `Encoder`, `Viewer`, or `System`.
It is retained only while a legacy account requires controlled cutover and for
historical audit evidence. It is not a canonical role, template, alias, or
source from which new permissions are inferred.

_Avoid:_ Legacy role template; automatic role mapping.

## Accounting and control

### Source transaction

The underlying business event and evidence from which journals, balances, and
Management views are derived.

### Maker

The authorized person who records or prepares a transaction and its supporting
evidence. For a sensitive entry, the maker cannot be its checker or final
poster.

### Checker

A distinct authorized person who reviews a prepared transaction, evidence, and
system validation before approval or posting. Sensitive entries require the
specified Management review.

### Authorized poster

The person with explicit permission to post an approved journal. This authority
is separate from preparation and is never inferred from a client application.

### Asset

A controlled economic resource, including cash, receivables, supplies,
equipment, vehicles, and other company property, recorded with evidence and the
custody or location facts required for reconciliation.

### Liability

A present company obligation, including supplier, employee, tax, accrual, and
loan obligations, supported by source evidence and due-state records.

### Equity

The residual interest after liabilities are deducted from assets, including
capital contributions, withdrawals or distributions, retained earnings, and
current profit or loss.

### Financial position

The system-derived view of posted assets, liabilities, and equity that must
satisfy `Assets = Liabilities + Equity`.

_Avoid:_ Manually entered dashboard total.

### Custody

Responsibility for cash or another asset while held by a bank, office, employee,
collector, or other approved custodian.

### Office Working Fund

The single official pool of company cash assigned to approved office-controlled
locations and custodians for routine operations.

_Avoid:_ Separate physical New Client Fund; manually maintained available cash.

### Cleared Office Cash

Office Working Fund cash supported by accepted custody and reconciliation
evidence before separate availability holds are deducted.

### Minimum Operating Reserve

The policy-protected portion of Cleared Office Cash that routine releases cannot
consume.

### Cash Reservation

An expiring, auditable commitment of an exact amount from the Office Working
Fund to one approved document version and purpose; it is not a cash movement or
general-ledger journal.

### Blocked Cash

The portion of Cleared Office Cash made unavailable by a discrepancy, expired
reconciliation window, hold, disputed evidence, or another protected
restriction.

### Spendable Office Cash

The server-derived amount remaining after the Minimum Operating Reserve, active
Cash Reservations, and Blocked Cash are deducted from Cleared Office Cash.

_Avoid:_ Employee-entered available balance; forecast collection treated as cash.

### New Client Fund

The Management-facing allocation and capacity view of Spendable Office Cash for
new-client releases; it is not a second physical pool, cash asset, or ledger
account.

### New Client Fund Capacity Guard

The deterministic server decision that combines an approved applicant's exact
cash requirement with liquidity, portfolio, and operating limits to return an
explainable Green, Amber, or Red funding result.

_Avoid:_ Credit score; autonomous loan approval; AI-created balance.

### Delegated Cash Authority

A versioned permission allowing a named person to prepare, hold, release, or
reconcile cash only within approved purpose, location, amount, period, and
separation-of-duty limits.

### Reconciliation

The controlled comparison of authoritative records, source evidence, custody,
and external or subledger totals, producing a resolved result or an explicit
discrepancy.

### Discrepancy

An unresolved difference that remains visible, assigned, and auditable until it
is investigated and resolved through an authorized workflow.

### Reversal

An append-only correction that neutralizes a posted entry without deleting or
overwriting the original evidence.

### Permanent audit evidence

Immutable or append-only evidence of who performed an action, under which
authority, on which record and device, when, with what reason, and with what
linked source and outcome identities.

### Official financial record

A server-authorized PostgreSQL record created or changed through a protected
workflow. Flutter state, Desktop widgets, browser metadata, caches, and legacy
portal records are not official merely because they display a value.
