# Cross-collector payment and notification flow

## Purpose

Make covered-date entry faster and let an authorized collector receive a payment from a client outside that collector's assigned area without losing assignment ownership, accountability, custody history, or audit evidence.

## Covered-date calendar

- The payment screen opens one calendar dialog.
- Tapping a date toggles that date selected/unselected without closing the calendar.
- Multiple non-contiguous dates may be selected in the same dialog.
- Already-covered dates are visible and disabled.
- The selected-date count and suggested amount update immediately.
- Saving sends the exact selected dates; dates between selections are not automatically covered.

## Assignment ownership

- Every active area has an assigned collector.
- The assigned collector remains the route owner for clients in that area.
- Another collector may post a payment only through the explicit **Other-area payment** flow.
- The posting collector is always retained as the original recorder in the immutable audit history.
- Cross-area posting never silently changes the client's assigned area or assigned collector.
- Before remittance, both the original recorder and the assigned route owner may correct an eligible unlocked cross-area receipt.
- Shared edit authority is accountability authority only; it never creates a second payment or rewrites who originally received the money.

## Cross-collector payment posting

When another collector receives the client's payment:

1. The collector searches for the client outside the daily assigned route.
2. The app clearly labels the client as belonging to another collector/area.
3. The collector records the amount and exact covered dates.
4. The server stores both:
   - `collector_user_id`: the collector who physically received and posted the payment;
   - `assigned_collector_user_id`: the collector who owns the client's area at posting time.
5. The assigned collector receives a notification containing client, amount, covered dates, receipt number, and recorder name.
6. The client receives a payment-posted notification containing amount, covered dates, receipt number, and recorder name.
7. The assigned route may display every same-day receipt separately, including recorder, amount, lock status, and covered dates. Multiple collectors receiving portions of one day's amount remain separate official receipts rather than being merged or duplicated.

## Remittance destinations and custody

### Remitted to the assigned collector

- A cross-area collector may remit the affected payment to the client's assigned collector.
- Submission immediately locks every included payment against Collector edits while acceptance is pending.
- The assigned collector receives a review notification.
- Acceptance performs the custody/adoption action without creating a duplicate payment and without rewriting the original recorder.
- The payment remains visible in the assigned collector's route/history with the original recorder attribution.
- Cash custody transfers to the assigned collector only after acceptance.

### Remitted to Management

- The payment transaction is permanently locked to Collector editing when included in the submitted remittance.
- After Management accepts the remittance, cash custody belongs to Management.
- The assigned collector may view the payment and its audit trail but cannot change, delete, copy, or replace it.
- This locks only the payment transaction. It does not freeze the entire client profile or unrelated future collections.

### Payment received directly by Management

- The record is marked `management_direct`.
- It is immutable to collectors from creation.
- The assigned collector receives a read-only notification.
- The client receives a payment-posted notification showing that Management recorded the payment.

## Client notifications

A linked client account receives server-generated notifications for:

1. **Payment posted**
   - amount;
   - exact covered dates;
   - official receipt number;
   - who recorded it;
   - remaining balance.

2. **Payment remitted**
   - remittance number;
   - who remitted it;
   - intended recipient (assigned collector or Management);
   - status `awaiting acceptance`.

3. **Remittance accepted**
   - who accepted custody;
   - acceptance timestamp;
   - final custody label.

Notifications are in-app records generated inside the same PostgreSQL transaction as the official action. Failure to create the required notification must roll back the payment/remittance action rather than leaving inconsistent status.

## Edit and correction matrix

| Situation | Original recorder | Assigned collector | Management |
|---|---:|---:|---:|
| Assigned collector's own unlocked entry | Correct before remittance | Correct before remittance | Audited adjustment only |
| Cross-area entry before remittance | Correct before remittance | Correct before remittance | Audited adjustment only |
| Cross-area entry submitted for remittance | Read-only | Read-only | Audited adjustment only |
| Cross-area entry accepted by assigned collector | Read-only | Read-only official entry | Audited adjustment only |
| Entry submitted/accepted by Management | Read-only | Read-only | Audited adjustment only |
| Management-direct payment | No collector edit | Read-only | Audited adjustment only |

A Collector correction must carry the route revision the Collector actually reviewed. The server serializes the transaction edit and rejects a stale revision if another payment or correction changed the loan first. This prevents two Collectors from silently overwriting one another.

The current safe in-place correction path applies only while the target receipt is still the latest state-changing entry for that loan. If a later receipt already changed the loan, correction fails closed and requires a protected void/repost or Management correction workflow instead of ad-hoc replay of downstream balances.

No correction may erase the original recorder, receipt, previous snapshot, covered dates, remittance path, custody history, or the identity of the person who performed the correction.

## Required implementation layers

- PostgreSQL assignment snapshots, cross-area flags, custody fields, and generic payment activity notifications.
- Backend search endpoint for eligible other-area clients.
- Backend authorization allowing the original recorder and assigned owner to correct only eligible unlocked cross-area entries.
- Optimistic route-revision protection plus transactional row/advisory locking for concurrent corrections.
- Backend transactional notifications at posting, remittance submission, and acceptance.
- Flutter multi-select calendar dialog.
- Flutter other-area client search and warning screen.
- Flutter route visibility for same-day receipt attribution and assigned-owner correction access.
- Flutter client notification presentation.
- Backend and Flutter tests for every edit/custody branch.
