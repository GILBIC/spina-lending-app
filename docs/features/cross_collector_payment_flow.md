# Cross-route Collector payment, custody and notification flow

## Purpose

Allow any authorized Collector to receive and post a protected payment for an active client outside that Collector's permanent route while preserving route ownership, recorder identity, cash accountability, custody history, receipts, corrections and audit evidence.

A convenience grant from the assigned Collector may surface clients/areas in **Other-Area Work**, but it is not required to search or post a cross-route payment.

## Covered-date calendar

- The payment screen opens one calendar dialog.
- Tapping a date toggles that date selected/unselected without closing the calendar.
- Multiple non-contiguous dates may be selected in the same dialog.
- Already-covered dates are visible and disabled.
- The selected-date count and suggested amount update immediately.
- Saving sends the exact selected dates; dates between selections are not automatically covered.
- One receipt may cover several scheduled dates, but it remains one physical cash receipt and must be remitted only once.

## Assignment ownership

- Every assigned area keeps its permanent assigned Collector.
- Another Collector may search and post an eligible cross-route payment through **Other Area Payment** without first receiving a delegated grant.
- A convenience grant only places selected clients/areas directly in **Other-Area Work**.
- Cross-route posting never silently changes the client's assigned area or assigned Collector.
- The posting Collector is permanently retained as the original recorder.
- The permanent assigned Collector's Daily Route must reflect the official transaction after refresh with recorder attribution so a duplicate client visit is not encouraged.

## Minimum cross-route client visibility

A visiting Collector may see only information needed to identify the client, verify the active loan and safely perform the current collection. Cross-route collection access does not automatically expose unrestricted historical/profile information.

Expanded sensitive access beyond the collection-relevant view is Management-only, scoped, time-limited, revocable and audited.

## Cross-route payment posting

When another Collector receives the client's payment:

1. The Collector searches for the client outside the permanent Daily Route, or opens the client from an approved convenience list.
2. The app clearly identifies the permanent assigned Collector/area.
3. The Collector records the amount and exact covered dates/payment type.
4. The server enforces every normal non-route financial safeguard: active account/device, collection permission, active client/loan, reconciled state, feature gates, current revision where required, chronological safety, allocation rules and idempotency.
5. Permanent route ownership itself is not a posting gate for another authorized Collector.
6. The server stores both the original recorder and assigned-Collector attribution.
7. The assigned Collector's Daily Route reflects the official result with full recorder/payment detail.
8. The linked client receives the official payment notification/receipt detail.
9. The collecting Collector's cash accountability increases immediately.

## Correction authority

Before remittance/lock, only the **original Collector recorder** may correct their own eligible transaction.

A pre-remittance correction requires a lightweight reason. The client is notified about the correction. The system permanently preserves what changed, who changed it, when and why.

The assigned Collector may review the cross-route transaction on their Daily Route but does not gain edit authority merely because they own that route.

Once the payment is included in a remittance/handoff submission, the Collector correction path is locked. After remittance, correction is Management-only and must preserve the original transaction plus linked correction/reversal/audit evidence.

## Cash responsibility

The person who physically receives the cash is initially responsible for that cash.

- **Own-route collection:** must ultimately be remitted to Management.
- **Cross-route collection:** may be remitted directly to Management or handed to the client's permanent assigned Collector.

Every accepted Pay immediately updates the collecting Collector's live cash accountability.

## Cross-route handoff to assigned Collector

A cross-route collecting Collector may send one itemized cash handoff to the assigned Collector.

Rules:

- one handoff may bundle several cross-route client payments only when they all belong to the same assigned Collector;
- different assigned Collectors require separate handoffs;
- Gilbic calculates the handoff total from the included payments; the total is not manually editable;
- while the handoff is a draft, the collecting Collector may add/remove eligible items;
- once sent and **Awaiting Acceptance**, included items are locked from Collector edits;
- the sender may cancel an awaiting handoff before acceptance, with audit history preserved;
- the assigned Collector can review every included payment before deciding;
- acceptance is **full amount only**; no partial acceptance;
- custody transfers only when the assigned Collector accepts;
- if rejected, a reason is required and full cash responsibility stays with the original collecting Collector;
- after rejection, the handoff may be corrected and resent without changing the underlying client-payment records;
- original recorder identity never changes.

Once the assigned Collector accepts the cross-route cash, that cash becomes part of the assigned Collector's own amount to remit to Management.

## Remittance to Management

For cash still held by a Collector:

- the system derives the amount from authoritative recorded collections and accepted handoffs;
- the Collector does not invent a separate amount that can hide recorded cash;
- when the Collector sends the remittance, included transactions are locked from Collector editing;
- the Collector cannot cancel or edit an **Awaiting Management Acceptance** remittance;
- an authorized Management cash receiver reviews the Daily Route/itemized remittance and physically counts the cash;
- Management either **Accepts** or **Rejects with required reason**;
- cash responsibility clears only after Management accepts;
- shortages are not tolerated and must be rejected;
- accepted overages are recorded separately as **Cash Over — Pending Identification** under Management custody.

A Collector may remit during the day more than once, but every cash amount recorded in Gilbic remains in accountability until it is accepted by Management or validly transferred through a cross-route handoff.

## Remittance confirmation and history

When Management accepts a remittance, Gilbic creates a permanent in-app confirmation containing:

- unique remittance reference;
- Collector;
- total expected/accepted cash;
- included collection/handoff items;
- authorized Management receiver;
- submission and acceptance timestamps.

The confirmation is read-only after acceptance. A separate PDF is not required. Collectors retain Remittance History including accepted and rejected remittances; rejected items show the required rejection reason and resubmission linkage where applicable.

## Cash Over

If Management counts more cash than the system expected:

- the normal expected remittance may still be accepted;
- the Collector's expected cash responsibility clears;
- the excess moves into **Cash Over — Pending Identification** under Management custody;
- it remains linked to the original Collector/remittance for traceability but does not make the Collector appear short;
- only Management may resolve/assign the overage, with reason and audit trail;
- unidentified Cash Over remains pending until genuinely resolved and is never forced into a client account or income category.

If Management later proves a Cash Over was a real client payment that was never recorded, Gilbic creates a **new linked client-payment record** rather than rewriting the accepted remittance. Use the actual original collection date/time only when reliably known; never guess. Preserve the later Management-entry timestamp and notify the client.

## Client notifications

A linked client should be able to verify each posted payment with enough detail, including amount, payment type/covered dates, official receipt/reference, recorder and updated balance.

The client is also notified when an eligible Collector or Management correction changes a payment result.

Internal Management-only notes remain private; client-facing correction notifications use a client-safe reason/category.

## Assigned Collector visibility

When another Collector handles a client, the permanent assigned Collector should see the full transaction detail on the Daily Route, including:

- amount;
- official receipt/reference;
- Regular/7x7/ADV or other entry type;
- exact covered dates where applicable;
- original recorder;
- correction state;
- custody/remittance state.

Management does not require a separate notification for every ordinary cross-route payment because Management can review every Collector's Daily Route and audit records before remittance.

## Audit and deletion rules

Financial history is never hard-deleted merely because an entry was mistaken, corrected, rejected or cancelled.

Every financial action preserves actor, approved device, server timestamp, client/loan link, receipt/reference and linked correction/custody/remittance history. Audit logs are non-editable/non-deletable. Corrective actions add linked records/status rather than erasing history.

## Duplicate protection

All financial writes use server-side idempotency. Double taps, retries or uncertain network responses must never create duplicate payments/handoffs/remittances. When the phone loses the response after Pay, it first checks the server for the existing transaction before allowing a retry.

## Required implementation layers

- PostgreSQL assignment snapshots, cross-route flags, custody/remittance fields and activity notifications.
- Backend open cross-route search for Collectors with normal collection permission.
- Backend posting bridge that relaxes only the permanent-route ownership gate while preserving every other collection safeguard.
- Original-recorder-only pre-remittance correction authority.
- Assigned-route reflection with recorder/payment/custody attribution.
- Full-acceptance bundled cross-route handoff and Management remittance custody controls.
- Client and assigned-Collector notifications/views.
- Flutter Other Area Payment search plus optional convenience-list browsing.
- Backend/Flutter tests for posting, correction, handoff, remittance, custody and duplicate-protection branches.
