# Manual Cash & GCash Control

This candidate records manually verified movements and relates them to existing
protected loan and employee workflows. It does not connect to a wallet provider or
send money. Production entry remains disabled and no real opening has been supplied.

## Work in separate phases

1. A Client submits their own claim, or an authorized Collector submits for a currently
   assigned borrower. The private proof and its retained versions are evidence only.
2. An authorized recipient verifies the actual received movement against recipient-side
   evidence. This creates one receipt, independently of whether a loan can accept it.
3. The server previews the existing Regular, 7x7 or combined allocation. Applying that
   exact current preview records the official loan payment atomically. A failed or
   unsupported allocation leaves the verified amount visibly received and unapplied.
4. Account movements are matched to manual observations and closed against an exact
   cutoff and coverage. A matching closing balance alone does not resolve missing rows.

Wallet-funded payments affect official loan totals but do not create Collector cash
to hand over. The recorder, borrower assignment, recipient and cash holder remain
separate facts. Reversing a loan application does not refund a wallet. An actual refund
requires its own verified outgoing movement and original-receipt capacity.

## Authority and private information

The existing configured owner identity is used; Management role alone is not owner
authority. Non-owner actions require current device, account and purpose permissions.
Client and Collector claim views do not grant access to recipient wallet history.
Evidence and reconciliation exports are private, authenticated and version-bound;
there are no public evidence links. Revocation applies to reads and recovery as well
as fresh writes. Treasury screens are excluded from permitted screen-sharing regions.

The website and installed Windows portal use the same API. Android uses the same
strict command contract and encrypted attempt recovery. Offline financial submission
is unavailable. After an uncertain response, recover or retry the unchanged request;
do not create another payment attempt merely because the result is not yet known.

## Supported source execution and explicit limits

Protected employee payroll and salary-advance payout adapters have synthetic database
acceptance. Actual debits, fees, refunds and the two independently verified sides of
an own-account transfer are retained without creating income or duplicate money.
An observed unauthorized debit remains an exception, not a completed business payment.

Existing cash-only loan release, renewal and expense completion remain blocked for
wallet settlement until their approved source contracts support it. Recording an
actual movement does not fabricate signatures, cash acknowledgments or GL posting.
Wallet-funded collection journals remain blocked where the account/context mapping
has not been approved. Existing automatic source posting stays disabled.

## Future activation requirements

Deployment requires the additive migrations `0136_add_treasury_control.sql` and
`0137_add_collection_funding_source.sql`. Runtime preflight requires the private
Treasury schema and active funding/custody guards. Entry additionally requires
`SPINA_TREASURY_ENABLED=true` and the existing `SPINA_EMPLOYEE_OWNER_USER_ID`.
Neither setting nor a synthetic test is owner activation acceptance.

Before real entry, record the intended holder, masked receiving alias, permitted use,
narrow delegates, common cutoff, observed cash by custodian and account balances.
Review existing-history overlap, personal portions and all unapplied/pending/transit
items. Missing values remain unavailable; never invent a zero or an opening journal.
No provider passwords, PINs, OTPs or real financial evidence belong in repository files.

## Recovery and rollback

Full backup/restore must include Treasury tables and the existing private evidence
store. The recovery drill validates linked claims, protected loan application, actual
refund, transfer and reconciliation together, and rejects missing or changed bytes.

Turning off new Treasury entry retains source-aware loan/custody reads. The first
future Treasury-aware deployment installs a persistent startup guard that rejects
older cash-only releases, even before wallet-funded rows exist. An incompatible
rollback leaves the API stopped and requires a source-aware recovery release. Do not
remove this guard or downgrade/delete financial history to force a restart. See the
[contract map](cash-gcash-control-contract-map.md) for files and lock ordering.

## Verification status

The [implementation plan](../superpowers/plans/2026-10-02-cash-gcash-control-reconciliation.md)
contains the current coverage ledger. Local synthetic database, browser, installed
Windows portal and native widget evidence are separate from exact-head CI, physical
phone acceptance and production readiness. Draft PR completion does not deploy or
activate this feature.
