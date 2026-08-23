# Collector cross-route access and convenience grants

## Status

Management-approved foundation update, 2026-08-23.

This document supersedes the earlier rule that a temporary delegated-area grant was required before another Collector could search or collect a client outside their permanent route.

## Core rule

A Collector with normal collection permission may search for an active client outside their assigned route and may use the protected official collection flow without first receiving a temporary area grant.

The permanent assigned Collector remains the route owner. The Collector who physically receives and posts the payment remains the original recorder. Cross-route collection never reassigns the client, area, loan, or route.

Temporary area grants are now a **convenience/visibility feature only**. They make selected clients or areas appear proactively in the visiting Collector's **Other-Area Work** list so the Collector does not have to search manually.

A convenience grant is not a financial-posting permission gate.

## Permanent route ownership

Permanent assignment remains authoritative for:

- the client's normal Daily Route;
- route ownership and route administration;
- assigned-Collector visibility;
- renewal recommendation authority where policy requires the permanent assigned Collector;
- cross-route cash handoff destination;
- reporting and attribution.

Cross-route work does not transfer any of those responsibilities.

## Cross-route search and collection

A Collector with `collection.create` may:

1. search for an active client outside their permanent route;
2. view only the client/loan information needed to verify and perform the collection;
3. record an otherwise eligible Regular payment, covered dates/ADV, PASS/unable-to-pay, and any other mobile collection action that is independently enabled and protected for that loan type;
4. receive the official server result and receipt;
5. see that cash added to their own cash accountability immediately.

The server must continue to enforce all non-route collection safeguards, including:

- authenticated active Collector account;
- approved active financial-posting device;
- required collection permission;
- active client and loan;
- reconciled loan state;
- loan-type/mobile feature gates;
- current route/loan revision where required;
- chronological safeguards;
- idempotency and duplicate protection;
- accounting and allocation rules;
- correction/remittance lock state.

The only rule relaxed for cross-route work is the permanent-route ownership requirement itself.

## Convenience grants

The assigned Collector may grant another Collector convenience visibility over scope that the assigned Collector currently owns.

Supported convenience scope may include:

1. one client/sub-area/path;
2. one area plus descendants;
3. multiple owned paths; or
4. **All my assigned areas**.

**All my assigned areas never means every area in Gilbic.**

Convenience grants:

- never change permanent ownership;
- never grant unrestricted historical/client-profile access;
- never grant Management-only authority;
- may be revoked by the assigned Collector;
- may expire automatically;
- are audited;
- disappear from the visiting Collector's Other-Area Work list when revoked/expired/stale.

If a convenience grant expires or is revoked, the visiting Collector may still use normal protected cross-route search and collection. The grant affects convenience visibility only.

If route ownership changes, stale convenience grants must not silently follow the area to the new owner.

## Expanded sensitive access

If a visiting Collector needs information beyond the minimum collection-relevant client/loan data, that expanded access may be granted **only by Management**.

Expanded access must be:

- explicit;
- scoped;
- time-limited;
- revocable;
- audited;
- automatically expired;
- revalidated server-side.

When expanded access expires, sensitive/extra information becomes unavailable immediately. This does not remove the Collector's normal ability to search and collect cross-route using the minimum collection-relevant data.

## Assigned-route reflection

Any official cross-route payment, PASS, ADV/covered-date entry, or eligible correction must appear on the permanent assigned Collector's authoritative Daily Route after refresh.

The assigned route should show enough information to prevent duplicate visits and verify what happened, including as applicable:

- amount;
- payment/entry type;
- exact covered dates;
- official receipt/reference;
- original recorder;
- collection time;
- correction state;
- cash/remittance state.

The assigned Collector receives the official result as read-only history unless they were the original recorder of an eligible pre-remittance entry.

## Correction ownership

Before remittance/lock, Collector correction authority stays with the **original recorder** of the transaction. The assigned route owner does not gain edit authority merely because the client belongs to their route.

Once a transaction enters remittance, Collectors cannot edit it. Post-remittance correction is Management-only under the controlled correction/audit workflow.

## Cross-route cash custody

The Collector who physically receives the cash is initially responsible for it.

For own-route collections, cash must be remitted to Management.

For cross-route collections, the collecting Collector may either:

- remit the cash directly to Management; or
- hand it to the permanent assigned Collector.

A Collector-to-Collector handoff transfers custody only when the assigned Collector accepts the **full** handoff. No partial acceptance is allowed.

Cross-route handoffs may bundle several client payments when all included payments belong to the same assigned Collector. The handoff total is calculated by Gilbic from the included payments and is not manually editable. Payments belonging to different assigned Collectors must use separate handoffs.

The assigned Collector can review every included client payment before accepting or rejecting the bundle. Rejection requires a reason and leaves cash responsibility with the original collecting Collector. A rejected bundle may be corrected and resent without changing the underlying client payments.

## Other-Area Work

**Other-Area Work** remains useful as a convenience workspace for clients/areas deliberately surfaced by active convenience grants.

It is not the only route to cross-route collection.

A Collector may always use **Other Area Payment** search for a client outside their route when they have normal collection permission.

The convenience workspace should still show today's authoritative transaction state so a visiting Collector does not duplicate a client visit.

## Other-area collection summary

The collecting Collector may have a **My Other-Area Collections** summary derived from authoritative collection/remittance/custody records.

It may group by assigned Collector and area and show:

- client;
- loan type;
- receipt/reference;
- amount;
- recorder;
- collection time/date;
- remittance/handoff reference;
- current custody/remittance state.

This is a view over the official records, not a second financial ledger.

## Client and assigned-Collector notifications

A cross-route payment should notify the linked client and the assigned Collector with enough information to verify the transaction.

The assigned Collector should be able to see the full transaction detail from the Daily Route, including amount, receipt/reference, payment type, recorder, and correction information.

Management does not need a separate notification for every normal cross-route payment because Management can review each Collector's Daily Route and audit records before remittance.

## Android acceptance

Before cross-route access is considered complete, the exact Android candidate should prove:

- a Collector with `collection.create` can search another-route client without a convenience grant;
- the protected server posting path accepts that cross-route collection without bypassing non-route financial safeguards;
- a Collector without a convenience grant does not receive unrestricted full client history;
- convenience grants still populate Other-Area Work without changing route ownership;
- revoking/expiring a convenience grant removes proactive visibility but does not block normal cross-route search/posting;
- the assigned Collector's Daily Route reflects the official cross-route transaction with recorder attribution;
- original-recorder-only pre-remittance correction remains enforced;
- cross-route cash can go to Management or through a full-acceptance handoff to the assigned Collector;
- no duplicate financial write is created by route reflection, notifications, handoff, or remittance.
