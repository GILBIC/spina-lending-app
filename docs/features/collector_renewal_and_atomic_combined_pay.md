# Collector Renewal and Atomic Combined Pay

## Status

This document is the implementation contract for the Management-approved follow-up to CA4. The feature is not production-approved until exact-head CI, guarded PostgreSQL migration, Android acceptance, and authenticated Management emulator review are green.

## Atomic Regular + 7x7 Pay

When exactly one Regular loan and one protected 7x7 loan for the same client are both safely payable today, Daily Collection shows one `Pay` action. The Collector enters the physical cash received once; the phone does not calculate or submit two leg amounts.

The phone must send one combined request. It must never emulate combined Pay by sending two independent mobile requests.

During the coordinated rollout, the server also accepts the prior exact one-tap body that carried two positive leg amounts. It sums those values only as the physical cash total, discards the client-proposed split, and recomputes the 7x7-first allocation from current server state. Short or excess legacy totals still fail closed because they do not carry the new review evidence or borrower extra direction.

Rollout is backend-first. The new mobile flow must receive a successful, current `/combined/preview` before its save action becomes available; a missing, older, or invalid preview response leaves save disabled. This is the capability gate that prevents a new Android client from sending the one-total contract to an older server. During rollout and rollback, keep the new mobile release unavailable until the matching backend is healthy; do not roll the backend below this contract while that mobile release remains active.

Server requirements:

- one parent idempotency key;
- same authenticated Collector and registered device for both legs;
- same client and collection date;
- exactly two distinct loans: one Regular and one `seven_by_seven`;
- each loan reference must carry its current route revision, while the request carries one cash total;
- the server derives the complete collectible amount for each loan from current signed-schedule/operational evidence, with the existing server-daily fallback retained only for transitional loans that do not yet have a registered schedule;
- an assigned-route authorization check runs before either loan's financial details are returned;
- a registered Regular schedule is used only when the matching protected posting gate is active and reconciled; schedule-present-but-not-postable states fail closed, and Regular Advance/Principal Reduction are unavailable on daily-fallback loans;
- ordinary cash clears all collectible 7x7 Past Due and Due Today first, then Regular;
- the read-only `/combined/preview` response returns the proposed split and a hash of the exact server evidence;
- an exact total may submit immediately; a short or excess amount must resubmit the reviewed allocation hash;
- a partial Regular leg also requires the existing structured Past Due reason/promise evidence;
- cash above both collectible obligations remains unapplied until the borrower explicitly chooses `7x7 Advance`, `7x7 Extra Principal`, `Regular Advance`, or `Regular Principal Reduction`;
- even with a borrower choice, combined Pay rejects cash above the exact protected payoff or future-schedule capacity before save; it never accepts a reviewed split that would create unallocated cash;
- both official posting bridges execute in one PostgreSQL transaction;
- protected 7x7 allocation remains authoritative for the 7x7 leg;
- if either leg conflicts or rejects, neither leg persists;
- an uncertain retry reuses the same parent transaction key and returns the same official result;
- the parent and every leg preserve received, applied, and unallocated cash evidence plus protected product metadata; no response may claim full allocation while any receipt remains unallocated;
- exact scheduled success returns two official receipt numbers and refreshes the route.

A short payment can legitimately produce only one official loan receipt when the cash is not enough to finish the 7x7 collectible obligation. An excess payment can produce a third receipt when the chosen protected 7x7 extra action must remain separate from the scheduled 7x7 receipt. Every resulting receipt remains under the one parent idempotency key and one database transaction.

Ambiguous multiple-loan combinations that are not exactly one Regular plus one 7x7 must fail closed and must not be converted into multiple independent phone writes.

## Non-ADV excess payment policy

Management's current rule is that payment cash above the current scheduled amount has only two valid meanings in the normal Collector flow: explicit ADV for selected future dates, or principal/remaining-term reduction.

For a normal `PAYMENT` that is not ADV:

- the scheduled amount still determines when today's scheduled obligation is fully covered;
- any applied cash above that scheduled obligation reduces principal/remaining term instead of staying unresolved;
- the excess must not silently mark tomorrow or another future scheduled date as paid;
- Regular contractual allocation applies the scheduled portion first, then works backward from the contractual tail so the next normal collection date stays due;
- Regular fixed interest is not recalculated merely because principal is paid faster;
- protected 7x7 keeps fixed daily interest based on original principal, settles that interest first, then applies residual cash to principal;
- only cash beyond the exact remaining payoff may remain unallocated for review/cash-over handling;
- audit evidence records cash received, applied amount, unallocated amount, and `principal_extra_amount`.

The installed database allocation-basis label `voluntary_extra_tail` remains for compatibility with migration 0095. It now also represents automatic non-ADV principal-tail reduction even when the Collector did not explicitly choose a separate Voluntary Extra option.

## Renewal eligibility

### Regular

Normal client `Request Renewal` becomes available once at least 50% of that Regular loan's total contractual balance has been paid. The total contractual balance is principal plus contractual interest/charges represented by the authoritative schedule or loan terms. Management may consider an earlier Regular renewal only through a separate controlled override path.

### 7x7

Regular and 7x7 renew independently. A 7x7 client may request consideration at any paid percentage, but every 7x7 renewal requires Management approval. Request availability is not automatic approval.

## Renewal authority chain

`Client Request → Permanently Assigned Collector Recommendation → Management Terms/Decision → Client Accept & Continue → Required Signer Verification/Signature → Authoritative Renewal Execution → Management Cash Release → Collector Cash Received → Collector Cash Given → Client Cash Confirmation → Handover Proof Review → Activation`

A temporary/delegated Collector cannot recommend for another Collector's permanent-area client.

## Collector UI

Daily Collection shows a `RENEWAL REQUESTED` badge for an assigned client with a pending/approved renewal workflow.

`More → Renewal requests` is the detailed Collector workspace. It shows:

- client, area, old loan, loan type, current principal and remaining balance;
- contractual total and paid percentage;
- client requested amount and note;
- `Recommend` / `Do Not Recommend` with structured reason;
- required explanation for `Do Not Recommend` and `Other`;
- Management-approved principal, but Collector cannot edit it;
- estimated net release until authoritative same-day execution locks the final amount;
- required signer readiness: own app, government ID, selfie/photo verification and own e-signature;
- `Office Processing Required` when remote signer requirements cannot be satisfied;
- locked cash custody steps;
- handover-photo submission/resubmission;
- `Awaiting Client Confirmation`, `Proof Under Review`, `Proof Correction Required`, and activation status.

## Management rules

Management alone selects the approved new principal. If Management approves against a `Do Not Recommend`, the override reason is mandatory and audited.

The normal approved-principal default may be the same as the old principal, but good/full-term performance may support an increase. This is a Management decision, never a Collector input.

Regular and 7x7 must stay independent unless a separate restructuring process is explicitly implemented.

## Signers and remote renewal

Every legally required signer must use their own GILBIC/SPINA account for remote renewal. The Collector cannot sign for another person.

Each required remote signer must have:

- their own linked app account;
- government-ID verification;
- selfie/photo identity verification;
- their own e-signature.

A supporting party may be borrower-only, guarantor, surety, or solidary co-maker as designated by Management. These labels are not interchangeable.

If any required signer cannot complete the remote flow, the request is `Office Processing Required` and remote signing/release stays blocked.

## Renewal settlement and cash

An approved renewal does not itself create a new collectible loan or settle the old one.

The authoritative renewal execution must explicitly prove:

`approved new principal = old-loan settlement + net cash released + approved other deductions`

Current policy is fail-closed for nonzero `other deductions` until Management defines and approves those deductions.

The old-loan settlement must be represented as a distinct renewal-offset/settlement event, not as Collector cash received.

The Collector normally records the old loan's ordinary same-day payment first. Final same-day old-loan settlement and net cash are then computed from authoritative execution evidence.

Management release locks the exact net cash amount. Later amount changes require controlled Management correction.

## Cash custody

Cash custody order is mandatory:

1. Management confirms Cash Released to Collector.
2. Collector independently confirms Cash Received.
3. Collector confirms Cash Given to Client.
4. Client independently confirms Cash Received.

The Collector can never perform the client's confirmation.

If cash was physically handed to the client but the client has not confirmed, status stays `Awaiting Client Confirmation` rather than failed release.

## Handover proof and activation

Collector handover photo is required. Management may `Approve Proof`, `Request New Photo`, or `Flag for Review`.

A rejected/insufficient photo after real cash handover does not automatically reverse the financial release. It becomes `Proof Correction Required` and requires resubmission.

The new loan remains `Released — Pending Management Verification` and is excluded from normal Daily Collection until all activation gates are complete.

Activation requires at minimum:

- client cash confirmation;
- approved handover proof;
- all required remote signers verified and signed;
- authoritative new loan linked;
- old loan fully settled/closed through the controlled renewal process.

If proof review delays overlap a scheduled date, the unactivated renewed loan must not be treated as an ordinary missed collection for the client.

## Release gate

Do not mark this feature complete, merge the PR, or enable it for production solely because code exists. Required evidence is:

1. exact-head backend and Flutter CI green;
2. disposable PostgreSQL atomicity + renewal-policy validation green;
3. guarded 0100/0101 migration applied and re-run idempotently on the acceptance database;
4. exact-head Android APK built and hash-verified;
5. authenticated emulator proves one-tap Regular+7x7 creates exactly two official receipts atomically;
6. authenticated renewal workflow proves assigned-Collector recommendation, Management terms, client/signers, custody, photo-proof and activation gates without bypasses.
