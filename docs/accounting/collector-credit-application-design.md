# Collector credit applied to a later remittance — 0157

Status:0157 is implemented and verified locally for the scope below. Fresh-schema integration, original-flow regressions, real transaction races, populated database/private-file restore and both clients pass. It has not been deployed. Production application entry remains disabled unless its explicit feature flag is enabled after the release rehearsal.

## Starting point before 0157

Before 0157, `collector_surplus.py` recorded an exact Collector-owned application request against a submitted remittance and its source digest. Its `prepare` application branch returned `blocked_adapter` before changing credit capacity. Preview rejected an application reference, count recording did not retain it, and acceptance always stored `authorized_credit_amount = 0.00`. Those older requests remain intent, never proof of reservation or consumption.

The current 0138 schema allows application actions but not application credit entries. Its credit capacity equation already deducts `applied_amount`; immutable consumption evidence is missing. Existing loan collection journals have already debited 1020. The legacy remittance custody trigger marks the recipient as custodian of an accepted gross remittance, without distinguishing a physical handover from credit settlement.

## Exact settlement quantities

Let `G` be the sum of the exact protected Collector-cash collection constituents, `C` the independently reserved application amount, and `P` the actual count. Admission requires `0 < C <= G`, no refund release or retained-cash dispute, the same Collector and book/context, and `P >= G - C`. The actual excess is `E = P - (G - C)`. Zero-effect PASS constituents remain admissible only with zero amount, applied amount and unallocated amount.

Reservation changes available capacity only: outstanding stays unchanged, reserved increases by `C`, available decreases by `C`. It creates neither cash nor a liability journal. Cancellation before consumption releases that exact reservation without changing outstanding or cash.

At atomic acceptance, reserved decreases by `C`, applied increases by `C`, outstanding decreases by `C`, and available remains unchanged. Create exactly one immutable application entry and one settlement referencing that approved action. Only `P` creates a verified Treasury cash event; zero actual cash creates no event, source link or movement. Its physical source link is exactly `G - C`, plus a separate excess source link for `E` where positive. An all-credit acceptance (`C = G`, `P = 0`) remains an explicit zero-physical-cash settlement.

The total accounting effect is:

| Debit | Credit |
| --- | --- |
| Mapped receiving cash `P` (omit when zero) | 1020 Collector custody `G` |
| 2220 Collector credit payable `C` | 2210 unidentified excess `E` (omit when zero) |

No loan receivable, interest, income or additional Treasury receipt is recognized. The original collection proof stays unchanged. A new excess case contains `E`, not `P - G`.

## Approved dated posting shape

Cash keeps the immutable actual count/event Manila business date. Application consumption occurs only at the server-recorded accepted settlement time. Do not backdate a liability discharge to a prior count or create a later-dated cash receipt merely to combine the entries.

The selected design uses two separately retained accounting legs, even when the dates happen to match. The settlement cash leg is debit mapped cash `P`, credit 1020 `G - C`, credit 2210 `E`, on the count date. A new `credit_application` leg is debit 2220 `C`, credit 1020 `C`, on the accepted-at date, linked to the immutable application entry. With no physical cash, only the application leg has a journal; the zero-cash acceptance retains exact source proof. Existing accepted sources must never be silently redated.

## Protected operational path

1. Reuse the Collector-owned request and independent staff approval, tied to exact credit, pending remittance, Collector, recipient, amount and source digest. Require current originating and receiving account authority, the same context, an unfrozen original recognized credit, current positive capacity, and actual approval evidence. Initially allow one application action per remittance; a cancelled action can be replaced with a new explicit request. Never reuse an unrelated return reservation.
2. Persist an immutable application approval with originating/receiving account IDs, request ID, remittance ID, source digest, approved amount and evidence. The action is `reserved`, with no cash event. Use the existing capacity updater and preserve all positive-money and version constraints.
3. Add paired optional application ID/version to count recording, matching the existing preview/accept fields. Supplying only one value must fail. Count review retains the exact approval and remittance constituents; its review digest binds the selected approval and amount. The base remittance digest remains separately retained so approval and count do not circularly hash each other. Do not include unrelated mutable current credit capacity in immutable count identity.
4. Acceptance rechecks the approved action, current credit capacity, exact Collector and designated recipient, original count/digest/evidence, unmodified collection constituents and no competing legacy handover. It appends the application entry, creates actual cash/evidence links where present, updates credit/action/request state, appends settlement and excess facts, and closes custody in one Treasury transaction. A short count, cancelled reservation or stale source leaves every component unchanged.
5. Add protected custody-split facts for gross obligation, physical obligation, authorized retained credit, actual received cash and excess. The received status denotes a fully settled obligation; read/API/notification surfaces must not describe the full gross as physically received. Collector accountability is released only after the complete accepted split; no earlier request/reservation removes the gross from custody.

Use `TreasuryService.execute` request advisory locking and exact command hash replay. Extend `affected_accounts` for count review/acceptance so it discovers the approval's origin and receiving accounts before taking sorted wallet locks. Lock account rows, credit/request/action, remittance and source transactions in consistent order. The action/credit/remittance locks serialize competing return versus application reservations and two acceptances; unique action consumption and one settlement per remittance are the final duplicate barriers. Add all new immutable facts to `replay_scope`, evidence revalidation and source watermark changes. Existing append-only, capacity and expected-version guards remain active.

## Accounting admission and retained evidence

Operational approval and consumption require a current exact posted original recognition, with every retained evidence file checked against its digest. Staff detail, aggregate reads and exact request recovery require current explicit private grants to every contributing wallet, including for the configured owner. Safe own-Collector projections remain separate. A later source freeze retains accepted cash/credit facts while reopening current accounting proof.

Retain source IDs, public dates/amounts, both wallet scopes, exact count/approval/application entry, credit recognition origin, collection proof IDs, cash event/source links/movements where present, evidence digests, chart roles, mappings, book and prerequisite posting identities. Private constituent/borrower/file snapshots remain server-side. Prepare/post reuse 0152 exact request, same actor, live permission, file-byte validation, immutable confirmation and protected-journal rules. A current operational acceptance is not a GL posting; it remains a close blocker until every required leg has exact posted proof.

Credit recognition must remain exact after a legitimate later application. The existing 0152 blanket `applied_amount != 0` rejection and capacity reconstruction must be replaced by strict immutable operational application validation and subtraction of those entries. This must not require the later application GL journal to validate the earlier recognition: that would create a circular prerequisite. Historical recognition snapshots/digests exclude later legitimate consumption; new unposted application entries remain independently blocked. Corrections, fabricated entries, frozen/reclassified credit and unsupported historical openings remain blocked rather than retroactively normalized.

## Dated controls, privacy and close evidence

Add a positive debit-minus-credit 2220 movement `C` on the immutable accepted application date, with source identity equal to the application entry. Reservations never appear as dated liability movements. Preserve all unregistered-line counts, including zero-net entries. Match source inventory rows only to the exact count/application proof; unpaid remaining credit is valid when reconciled. Corrected constituents, approvals, source events, chart definitions or unknown application facts must reopen current proof and close coverage.

The schedule's current-capacity and dated scopes must authorize every application origin and receiving wallet before pagination, including zero-cash applications, inactive historical wallets and retained previous scopes. A denied wallet denies the aggregate generically. Its present action-wallet union filters to returns and requires extension.

Extend the existing manifest evidence/lock hooks compositionally. Include immutable approval, consumption, custody split, source/current proof, associated accounting preparation/posting and original recognition dependencies through the cutoff. An application added after a reviewed manifest or a changed retained source must stale that manifest. Retain the 0150 and 0152 predecessors; never replace their evidence with only application rows.

## Reporting boundary

The internal handover principal is exactly `G - C`, never gross `G`. Only the proven physical custody handover may pair between 1020 and mapped receiving cash. The `C` payable-settlement portion must not be labeled internal merely because it credits a cash-coded custody account. Keep exact selected-cash change visible and require an explicit valid reporting classification for any remaining cash line under the configured cash definition; do not synthesize a bank/Treasury payment or conceal the liability settlement. If 1020 is outside that cash definition, the noncash liability/custody settlement belongs in the retained noncash disclosure scope. Mixed cash/noncash disclosure remains explicit and never implies annual readiness.

Coordinate this with `read_internal_collector_cash`: it currently derives internal principal from retained gross. A 0157 proof must expose the actual physical principal and preserve the old source interpretation for pre-0157 settlements. Zero-cash credit application cannot fabricate an internal pair. Wrong or absent proof must leave the line unavailable/unclassified, never silently contribute zero.

## Behavioral test sequence

The initial regression file uses actual recorded excess, operational recognition, protected collection journals, Collector application requests and staff preparation. The initial baseline failed because the old blocked operational approval could not create a reserved action. No fake reservation, credit entry, cash event or accounting journal is inserted to bypass that missing phase.

Then cover reservation/cancellation with unchanged GL and cash, exact and excess partial counts, short-count rollback, full-credit zero-cash acceptance, exact source-linked entries and capacity, separate accounting prepare/post, dated control reconciliation, wrong Collector/account/context, duplicate/conflicting requests, concurrent competing reservations, same-request acceptance replay, stale source/evidence, private projection/revocation and zero-cash custody/reporting/manifest behavior. The service replay, real transaction races, date split, immutable facts and populated restore now have passing task-owned disposable-database runs recorded in the execution ledger. Full statutory accounting and unsupported historical sources remain outside this increment.
