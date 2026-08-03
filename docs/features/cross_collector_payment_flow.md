# Cross-collector payment and notification flow

## Purpose

Make covered-date entry faster and let an authorized collector receive a payment from a client outside that collector's assigned area without losing assignment ownership, accountability, or audit history.

## Covered-date calendar

- The payment screen opens one calendar dialog.
- Tapping a date toggles that date selected/unselected without closing the calendar.
- Multiple non-contiguous dates may be selected in the same dialog.
- Already-covered dates are visible and disabled.
- The selected-date count and suggested amount update immediately.
- Saving still sends the exact selected dates; dates between selections are not automatically covered.

## Assignment ownership

- Every active area has an assigned collector.
- The assigned collector remains the route owner for clients in that area.
- The assigned collector may correct eligible unlocked entries for that route.
- Another collector may post a payment only through the explicit **Other-area payment** flow.
- The posting collector is always retained as the original recorder in the immutable audit history.
- Cross-area posting never silently changes the client's assigned area or assigned collector.

## Cross-collector payment posting

When another collector receives the client's payment:

1. The collector searches for the client outside the daily assigned route.
2. The app clearly labels the client as belonging to another collector/area.
3. The collector records the amount and exact covered dates.
4. The server stores both:
   - `recorded_by_user_id`: the collector who physically received and posted the payment;
   - `assigned_collector_user_id`: the collector who owns the client's area at posting time.
5. The assigned collector receives a notification containing client, amount, covered dates, receipt number, and recorder name.
6. The client receives a payment-posted notification containing amount, covered dates, receipt number, and recorder name.

## Remittance destinations and custody

### Remitted to the assigned collector

- A cross-area collector may remit the affected payment to the client's assigned collector.
- The assigned collector receives a review notification.
- Acceptance performs a one-tap **Adopt into my route** action.
- Adoption does not create a duplicate payment and does not rewrite the original recorder.
- The payment becomes visible in the assigned collector's route/history with the original recorder attribution.
- Cash custody transfers to the assigned collector only after acceptance.

### Remitted to Management

- The payment transaction is permanently locked when included in the submitted remittance.
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
| Cross-area entry before remittance | Correct own entry before remittance | Review only | Audited adjustment only |
| Cross-area entry accepted by assigned collector | Read-only | Adopted read-only official entry | Audited adjustment only |
| Entry submitted/accepted by Management | Read-only | Read-only | Audited adjustment only |
| Management-direct payment | No collector edit | Read-only | Audited adjustment only |

No correction may erase the original recorder, receipt, previous snapshot, covered dates, remittance path, or custody history.

## Required implementation layers

- PostgreSQL migration for assignment snapshots, cross-area flags, adoption/custody fields, and generic payment activity notifications.
- Backend search endpoint for eligible other-area clients.
- Backend authorization and correction rules.
- Backend transactional notifications at posting, remittance submission, and acceptance.
- Flutter multi-select calendar dialog.
- Flutter other-area client search and warning screen.
- Flutter assigned-collector review/adopt action.
- Flutter client notification presentation.
- Backend and Flutter tests for every edit/custody branch.
